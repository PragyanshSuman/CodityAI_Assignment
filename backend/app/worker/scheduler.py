"""
Worker Engine — Scheduler
Promotes delayed/scheduled jobs whose scheduled_at <= NOW() to 'pending'.
Also detects stale workers (no heartbeat) and re-queues their claimed jobs.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from app.database import get_pool
from app.websocket.manager import broadcast_event

logger = logging.getLogger(__name__)

STALE_WORKER_SECONDS = 30


async def promote_scheduled_jobs():
    """Move scheduled jobs that are due to 'pending' status."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """UPDATE jobs SET status = 'pending', scheduled_at = NULL
               WHERE status = 'scheduled'
                 AND scheduled_at <= NOW()
                 AND deleted_at IS NULL
               RETURNING id, queue_id""",
        )
        for row in rows:
            logger.info(f"Promoted scheduled job {row['id']} to pending")
            await broadcast_event("job.promoted", {"job_id": str(row["id"]), "queue_id": str(row["queue_id"])})
    return len(rows)


async def recover_stale_worker_jobs():
    """
    Detect workers whose heartbeat is stale and re-queue their jobs.
    This is the dead worker recovery mechanism.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        stale_cutoff = datetime.now(timezone.utc) - timedelta(seconds=STALE_WORKER_SECONDS)

        # Mark stale workers as offline
        stale_workers = await conn.fetch(
            """UPDATE workers SET status = 'offline', shutdown_at = NOW()
               WHERE status IN ('active','idle')
                 AND last_heartbeat_at < $1
               RETURNING id, name""",
            stale_cutoff,
        )

        recovered = 0
        for worker in stale_workers:
            logger.warning(f"Worker {worker['name']} ({worker['id']}) is stale, recovering its jobs")
            # Re-queue claimed/running jobs from stale workers
            rows = await conn.fetch(
                """UPDATE jobs SET status = 'pending', claimed_by = NULL, claimed_at = NULL,
                                   started_at = NULL,
                                   attempt_count = GREATEST(0, attempt_count - 1)
                   WHERE claimed_by = $1 AND status IN ('claimed', 'running')
                   RETURNING id""",
                str(worker["id"]),
            )
            recovered += len(rows)
            for row in rows:
                await broadcast_event("job.recovered", {"job_id": str(row["id"]), "worker_id": str(worker["id"])})

        return len(stale_workers), recovered


async def take_queue_stats_snapshot():
    """Periodically snapshot queue statistics for metrics/history."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        queues = await conn.fetch("SELECT id FROM queues WHERE is_active = TRUE")
        for queue in queues:
            qid = str(queue["id"])
            row = await conn.fetchrow(
                """SELECT
                    COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                    COUNT(*) FILTER (WHERE status = 'running') AS running,
                    COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                    COUNT(*) FILTER (WHERE status = 'failed') AS failed,
                    COUNT(*) FILTER (WHERE status = 'dead_letter') AS dead_letter
                   FROM jobs WHERE queue_id = $1 AND deleted_at IS NULL""",
                qid,
            )
            await conn.execute(
                """INSERT INTO queue_stats_snapshots
                   (queue_id, pending_count, running_count, completed_count, failed_count, dead_letter_count)
                   VALUES ($1,$2,$3,$4,$5,$6)""",
                qid, row["pending"], row["running"], row["completed"], row["failed"], row["dead_letter"],
            )
