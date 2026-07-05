"""
Worker Engine — Retry Engine
Implements fixed, linear, and exponential backoff strategies.
Moves jobs to Dead Letter Queue after exhausting all attempts.
"""
import logging
import math
import random
from datetime import datetime, timezone, timedelta

from app.database import get_pool
from app.websocket.manager import broadcast_event

logger = logging.getLogger(__name__)


async def compute_next_delay(queue_id: str, attempt_number: int) -> timedelta:
    """Compute the delay before the next retry based on the queue's retry policy."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        policy = await conn.fetchrow(
            """SELECT rp.strategy, rp.initial_delay_seconds, rp.max_delay_seconds,
                      rp.multiplier, rp.jitter
               FROM queues q
               LEFT JOIN retry_policies rp ON rp.id = q.retry_policy_id
               WHERE q.id = $1""",
            queue_id,
        )

    if not policy or not policy["strategy"]:
        # Default: exponential 2x, base 30s, max 3600s
        delay = min(30 * (2 ** attempt_number), 3600)
        return timedelta(seconds=delay)

    strategy = policy["strategy"]
    initial = policy["initial_delay_seconds"] or 60
    max_delay = policy["max_delay_seconds"] or 3600
    multiplier = policy["multiplier"] or 2.0
    jitter = policy["jitter"] or False

    if strategy == "fixed":
        delay = initial
    elif strategy == "linear":
        delay = initial * attempt_number
    elif strategy == "exponential":
        delay = initial * (multiplier ** (attempt_number - 1))
    else:
        delay = initial

    delay = min(delay, max_delay)

    if jitter:
        delay = delay * (0.5 + random.random() * 0.5)

    return timedelta(seconds=int(delay))


async def handle_job_failure(job_id: str, queue_id: str, error_message: str, error_type: str = None, error_stack: str = None):
    """
    Handle a failed job execution:
    - If more attempts remain: schedule retry with backoff
    - If exhausted: move to Dead Letter Queue
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        job = await conn.fetchrow(
            "SELECT id, attempt_count, max_attempts FROM jobs WHERE id = $1",
            job_id,
        )
        if not job:
            return

        if job["attempt_count"] < job["max_attempts"]:
            # Schedule retry
            delay = await compute_next_delay(queue_id, job["attempt_count"])
            retry_at = datetime.now(timezone.utc) + delay

            await conn.execute(
                """UPDATE jobs SET status = 'scheduled', scheduled_at = $2,
                                  error_message = $3, claimed_by = NULL, claimed_at = NULL,
                                  started_at = NULL
                   WHERE id = $1""",
                job_id, retry_at, error_message,
            )
            logger.info(f"Job {job_id} scheduled for retry at {retry_at} (attempt {job['attempt_count']}/{job['max_attempts']})")
            await broadcast_event("job.retry_scheduled", {
                "job_id": job_id,
                "retry_at": retry_at.isoformat(),
                "attempt": job["attempt_count"],
            })
        else:
            # Move to Dead Letter Queue
            async with conn.transaction():
                await conn.execute(
                    "UPDATE jobs SET status = 'dead_letter', error_message = $2 WHERE id = $1",
                    job_id, error_message,
                )
                await conn.execute(
                    """INSERT INTO dead_letter_queue (job_id, queue_id, final_error, total_attempts)
                       VALUES ($1, $2, $3, $4)
                       ON CONFLICT DO NOTHING""",
                    job_id, queue_id, error_message, job["max_attempts"],
                )

            logger.warning(f"Job {job_id} moved to DLQ after {job['max_attempts']} attempts")
            await broadcast_event("job.dead_letter", {"job_id": job_id, "queue_id": queue_id})


async def handle_job_success(job_id: str, result: dict = None):
    """Mark job as completed, handle recurring job rescheduling."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        job = await conn.fetchrow(
            "SELECT id, job_type, cron_expression FROM jobs WHERE id = $1", job_id
        )
        if not job:
            return

        if job["job_type"] == "recurring" and job["cron_expression"]:
            # Schedule next run
            from croniter import croniter
            from datetime import datetime
            now = datetime.now(timezone.utc)
            try:
                cron = croniter(job["cron_expression"], now)
                next_run = cron.get_next(datetime)
                await conn.execute(
                    """UPDATE jobs SET status = 'completed', completed_at = NOW(), result = $2,
                                      next_run_at = $3
                       WHERE id = $1""",
                    job_id, dict(result) if result else {}, next_run,
                )
                # Create next instance
                new_job = await conn.fetchrow(
                    """INSERT INTO jobs (queue_id, name, job_type, handler, payload, status,
                                        priority, max_attempts, timeout_seconds, cron_expression,
                                        scheduled_at, next_run_at)
                       SELECT queue_id, name, job_type, handler, payload, 'scheduled',
                              priority, max_attempts, timeout_seconds, cron_expression,
                              $2, $2 FROM jobs WHERE id = $1
                       RETURNING id""",
                    job_id, next_run,
                )
                logger.info(f"Recurring job {job_id} rescheduled → {next_run}, new instance: {new_job['id']}")
            except Exception as e:
                logger.error(f"Failed to reschedule recurring job {job_id}: {e}")
        else:
            await conn.execute(
                "UPDATE jobs SET status = 'completed', completed_at = NOW(), result = $2 WHERE id = $1",
                job_id, dict(result) if result else {},
            )

        # Update batch progress if applicable
        batch_id = await conn.fetchval("SELECT batch_id FROM jobs WHERE id = $1", job_id)
        if batch_id:
            await conn.execute(
                """UPDATE batch_jobs SET completed_jobs = completed_jobs + 1,
                   status = CASE WHEN completed_jobs + failed_jobs + 1 = total_jobs THEN 'completed' ELSE status END
                   WHERE id = $1""",
                str(batch_id),
            )

    await broadcast_event("job.completed", {"job_id": job_id})
