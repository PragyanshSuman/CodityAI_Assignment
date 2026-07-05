"""
Worker Engine — Main Worker Loop
Orchestrates all worker components with graceful shutdown.
"""
import asyncio
import logging
import os
import signal
import socket
import uuid
from datetime import datetime, timezone

import psutil

from app.database import get_pool, create_pool
from app.worker.poller import claim_jobs, release_job
from app.worker.executor import execute_job
from app.worker.scheduler import promote_scheduled_jobs, recover_stale_worker_jobs, take_queue_stats_snapshot
from app.config import settings

logger = logging.getLogger(__name__)

WORKER_ID = str(uuid.uuid4())
MAX_CONCURRENCY = int(os.environ.get("WORKER_MAX_CONCURRENCY", "10"))
POLL_INTERVAL = settings.WORKER_POLL_INTERVAL
HEARTBEAT_INTERVAL = settings.WORKER_HEARTBEAT_INTERVAL

_shutdown_event = asyncio.Event()
_active_tasks: set = set()


async def register_self():
    """Register this worker process in the database."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO workers (id, name, hostname, ip_address, pid, max_concurrency, status)
               VALUES ($1, $2, $3, $4, $5, $6, 'active')
               ON CONFLICT (id) DO UPDATE SET status = 'active', last_heartbeat_at = NOW()""",
            WORKER_ID,
            f"worker-{WORKER_ID[:8]}",
            socket.gethostname(),
            socket.gethostbyname(socket.gethostname()),
            os.getpid(),
            MAX_CONCURRENCY,
        )
    logger.info(f"Worker {WORKER_ID} registered")


async def send_heartbeat():
    """Send a heartbeat to indicate this worker is alive."""
    process = psutil.Process()
    pool = await get_pool()
    async with pool.acquire() as conn:
        active_task_count = len(_active_tasks)
        await conn.execute(
            """UPDATE workers SET last_heartbeat_at = NOW(), current_jobs = $2,
               status = CASE WHEN $2 > 0 THEN 'active' ELSE 'idle' END
               WHERE id = $1""",
            WORKER_ID, active_task_count,
        )
        await conn.execute(
            """INSERT INTO worker_heartbeats (worker_id, status, current_jobs, memory_mb, cpu_percent)
               VALUES ($1, $2, $3, $4, $5)""",
            WORKER_ID,
            'active' if active_task_count > 0 else 'idle',
            active_task_count,
            process.memory_info().rss / 1024 / 1024,
            process.cpu_percent(interval=None),
        )


async def heartbeat_loop():
    """Continuously send heartbeats while worker is alive."""
    while not _shutdown_event.is_set():
        try:
            await send_heartbeat()
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
        await asyncio.sleep(HEARTBEAT_INTERVAL)


async def scheduler_loop():
    """Continuously promote scheduled jobs and recover stale workers."""
    snapshot_counter = 0
    while not _shutdown_event.is_set():
        try:
            promoted = await promote_scheduled_jobs()
            workers_recovered, jobs_recovered = await recover_stale_worker_jobs()
            if promoted > 0:
                logger.info(f"Promoted {promoted} scheduled jobs")
            if jobs_recovered > 0:
                logger.info(f"Recovered {jobs_recovered} jobs from {workers_recovered} stale workers")

            snapshot_counter += 1
            if snapshot_counter >= 30:  # Every 30 seconds
                await take_queue_stats_snapshot()
                snapshot_counter = 0

        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        await asyncio.sleep(1)


async def poll_loop():
    """Main polling loop: claim and execute jobs."""
    while not _shutdown_event.is_set():
        try:
            available_slots = MAX_CONCURRENCY - len(_active_tasks)
            if available_slots > 0:
                jobs = await claim_jobs(WORKER_ID, max_jobs=available_slots)
                for job in jobs:
                    if _shutdown_event.is_set():
                        await release_job(str(job["id"]), WORKER_ID)
                        break
                    task = asyncio.create_task(execute_job(job, WORKER_ID))
                    _active_tasks.add(task)
                    task.add_done_callback(_active_tasks.discard)
        except Exception as e:
            logger.error(f"Poll loop error: {e}")
        await asyncio.sleep(POLL_INTERVAL)


async def graceful_shutdown():
    """Wait for in-flight jobs to finish before exiting."""
    logger.info(f"Graceful shutdown initiated. Waiting for {len(_active_tasks)} active jobs...")
    _shutdown_event.set()

    # Mark worker as draining
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE workers SET status = 'draining', shutdown_at = NOW() WHERE id = $1",
            WORKER_ID,
        )

    # Wait for active tasks to complete (up to 30s)
    if _active_tasks:
        try:
            await asyncio.wait_for(
                asyncio.gather(*_active_tasks, return_exceptions=True),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for jobs to finish; forcing shutdown")

    # Mark worker as offline
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE workers SET status = 'offline' WHERE id = $1", WORKER_ID
        )
    logger.info("Worker shutdown complete")


async def run_worker():
    """Entry point for the worker process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    # Initialize DB pool
    await create_pool()
    await register_self()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(graceful_shutdown()))
        except NotImplementedError:
            pass  # Windows doesn't support add_signal_handler

    logger.info(f"Worker {WORKER_ID} started (max_concurrency={MAX_CONCURRENCY})")

    await asyncio.gather(
        heartbeat_loop(),
        scheduler_loop(),
        poll_loop(),
    )


if __name__ == "__main__":
    asyncio.run(run_worker())
