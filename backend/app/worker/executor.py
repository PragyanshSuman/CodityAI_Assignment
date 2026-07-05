"""
Worker Engine — Executor
Runs jobs with timeout enforcement. Simulates job execution
(in production, dispatches to actual handler functions/microservices).
"""
import asyncio
import logging
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Optional

import asyncpg

from app.database import get_pool
from app.worker.retry_engine import handle_job_failure, handle_job_success

logger = logging.getLogger(__name__)


# Registry of handler functions — extend this to add real job handlers
JOB_HANDLERS = {}


def register_handler(name: str):
    """Decorator to register a job handler function."""
    def decorator(fn):
        JOB_HANDLERS[name] = fn
        return fn
    return decorator


@register_handler("default")
async def default_handler(payload: dict) -> dict:
    """Default no-op handler. Replace with real business logic."""
    await asyncio.sleep(0.1)
    return {"status": "ok", "payload_received": payload}


@register_handler("email.send_welcome")
async def send_welcome_email(payload: dict) -> dict:
    await asyncio.sleep(0.2)
    return {"sent": True, "to": payload.get("user_id")}


@register_handler("report.generate")
async def generate_report(payload: dict) -> dict:
    await asyncio.sleep(1.0)
    return {"report_url": f"https://storage.example.com/reports/{payload.get('report_id')}.pdf"}


async def execute_job(job: dict, worker_id: str):
    """
    Execute a single job:
    1. Create an execution record
    2. Mark job as running
    3. Run the handler with timeout
    4. Record result / failure
    5. Trigger retry engine or success handler
    """
    pool = await get_pool()
    job_id = str(job["id"])
    queue_id = str(job["queue_id"])
    execution_id = str(uuid.uuid4())
    start_time = time.monotonic()
    started_at = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        # Create execution record
        await conn.execute(
            """INSERT INTO job_executions (id, job_id, worker_id, attempt_number, status, started_at)
               VALUES ($1, $2, $3, $4, 'running', $5)""",
            execution_id, job_id, worker_id, job.get("attempt_count", 1), started_at,
        )
        # Mark job as running
        await conn.execute(
            "UPDATE jobs SET status = 'running', started_at = $2 WHERE id = $1",
            job_id, started_at,
        )

    # Log job start
    await _write_log(execution_id, job_id, "info", f"Job started by worker {worker_id}")

    handler_name = job.get("handler", "default")
    handler = JOB_HANDLERS.get(handler_name, default_handler)
    payload = job.get("payload", {})
    timeout = job.get("timeout_seconds", 300)

    try:
        result = await asyncio.wait_for(handler(payload), timeout=timeout)
        duration_ms = int((time.monotonic() - start_time) * 1000)

        async with pool.acquire() as conn:
            await conn.execute(
                """UPDATE job_executions
                   SET status = 'completed', completed_at = NOW(),
                       duration_ms = $2, result = $3
                   WHERE id = $1""",
                execution_id, duration_ms, dict(result) if result else {},
            )

        await _write_log(execution_id, job_id, "info", f"Job completed in {duration_ms}ms")
        await handle_job_success(job_id, result)
        logger.info(f"Job {job_id} completed successfully in {duration_ms}ms")

    except asyncio.TimeoutError:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        error_msg = f"Job timed out after {timeout}s"
        await _write_log(execution_id, job_id, "error", error_msg)
        async with pool.acquire() as conn:
            await conn.execute(
                """UPDATE job_executions
                   SET status = 'timed_out', completed_at = NOW(), duration_ms = $2,
                       error_type = 'TimeoutError', error_message = $3
                   WHERE id = $1""",
                execution_id, duration_ms, error_msg,
            )
        await handle_job_failure(job_id, queue_id, error_msg, "TimeoutError")
        logger.warning(f"Job {job_id} timed out")

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        error_msg = str(e)
        error_stack = traceback.format_exc()
        error_type = type(e).__name__
        await _write_log(execution_id, job_id, "error", f"Job failed: {error_msg}", {"traceback": error_stack})
        async with pool.acquire() as conn:
            await conn.execute(
                """UPDATE job_executions
                   SET status = 'failed', completed_at = NOW(), duration_ms = $2,
                       error_type = $3, error_message = $4, error_stack = $5
                   WHERE id = $1""",
                execution_id, duration_ms, error_type, error_msg, error_stack,
            )
        await handle_job_failure(job_id, queue_id, error_msg, error_type, error_stack)
        logger.error(f"Job {job_id} failed: {error_msg}")


async def _write_log(execution_id: str, job_id: str, level: str, message: str, data: dict = None):
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO job_logs (execution_id, job_id, level, message, data) VALUES ($1, $2, $3, $4, $5)",
                execution_id, job_id, level, message, data,
            )
    except Exception as e:
        logger.warning(f"Failed to write job log: {e}")
