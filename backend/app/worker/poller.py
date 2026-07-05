"""
Worker Engine — Poller
Atomically claims jobs from queues using SELECT FOR UPDATE SKIP LOCKED.
This guarantees zero duplicate execution even with many concurrent workers.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

import asyncpg

from app.database import get_pool
from app.websocket.manager import broadcast_event

logger = logging.getLogger(__name__)


async def claim_jobs(worker_id: str, max_jobs: int = 10) -> list:
    """
    Atomically claim up to max_jobs pending jobs across all queues.
    Uses SELECT FOR UPDATE SKIP LOCKED to prevent duplicate claims.
    Returns list of claimed job dicts.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Get all active, non-paused queues ordered by priority
            queues = await conn.fetch(
                """SELECT id, concurrency_limit, is_paused
                   FROM queues WHERE is_active = TRUE AND is_paused = FALSE
                   ORDER BY priority DESC"""
            )

            claimed = []
            for queue in queues:
                if len(claimed) >= max_jobs:
                    break

                # Count currently running jobs in this queue
                running = await conn.fetchval(
                    "SELECT COUNT(*) FROM jobs WHERE queue_id = $1 AND status = 'running'",
                    str(queue["id"]),
                )
                available_slots = queue["concurrency_limit"] - (running or 0)
                if available_slots <= 0:
                    continue

                # Check rate limiting
                can_claim = await _check_rate_limit(conn, str(queue["id"]))
                if not can_claim:
                    continue

                limit = min(available_slots, max_jobs - len(claimed))

                # Atomic claim: FOR UPDATE SKIP LOCKED prevents any other worker
                # from claiming the same rows simultaneously
                jobs = await conn.fetch(
                    """SELECT id, queue_id, name, handler, payload, priority,
                              max_attempts, attempt_count, timeout_seconds,
                              cron_expression, job_type
                       FROM jobs
                       WHERE queue_id = $1
                         AND status = 'pending'
                         AND deleted_at IS NULL
                         AND (scheduled_at IS NULL OR scheduled_at <= NOW())
                         AND NOT EXISTS (
                             SELECT 1 FROM job_dependencies jd
                             JOIN jobs dep ON dep.id = jd.depends_on_job_id
                             WHERE jd.job_id = jobs.id
                               AND dep.status NOT IN ('completed')
                         )
                       ORDER BY priority DESC, created_at ASC
                       LIMIT $2
                       FOR UPDATE SKIP LOCKED""",
                    str(queue["id"]), limit,
                )

                for job in jobs:
                    # Mark as claimed in same transaction
                    await conn.execute(
                        """UPDATE jobs SET status = 'claimed', claimed_by = $2,
                                          claimed_at = NOW(), attempt_count = attempt_count + 1
                           WHERE id = $1""",
                        str(job["id"]), worker_id,
                    )
                    claimed.append(dict(job))

            return claimed


async def _check_rate_limit(conn: asyncpg.Connection, queue_id: str) -> bool:
    """
    Token bucket rate limiting check-and-consume.
    Returns True if a token is available, False if rate limited.
    """
    bucket = await conn.fetchrow(
        "SELECT tokens, max_tokens, refill_rate, last_refill_at FROM rate_limit_buckets WHERE queue_id = $1 FOR UPDATE",
        queue_id,
    )
    if not bucket:
        return True  # No rate limit configured

    now = datetime.now(timezone.utc)
    elapsed = (now - bucket["last_refill_at"].replace(tzinfo=timezone.utc)).total_seconds()
    new_tokens = min(bucket["max_tokens"], bucket["tokens"] + elapsed * bucket["refill_rate"])

    if new_tokens < 1.0:
        return False  # Rate limited

    await conn.execute(
        "UPDATE rate_limit_buckets SET tokens = $2, last_refill_at = $3 WHERE queue_id = $1",
        queue_id, new_tokens - 1.0, now,
    )
    return True


async def release_job(job_id: str, worker_id: str):
    """Re-queue a job that couldn't be executed (e.g. worker shutdown)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE jobs SET status = 'pending', claimed_by = NULL, claimed_at = NULL,
                              attempt_count = GREATEST(0, attempt_count - 1)
               WHERE id = $1 AND claimed_by = $2 AND status = 'claimed'""",
            job_id, worker_id,
        )
