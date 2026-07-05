from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from typing import List, Optional
import asyncpg
import uuid
from datetime import datetime, timezone

from app.database import get_db
from app.dependencies import get_current_user
from app.models.job import (
    JobCreate, BatchJobCreate, JobResponse, JobDetailResponse,
    JobListResponse, DLQEntryResponse, JobExecutionResponse, JobLogResponse
)
from app.websocket.manager import broadcast_event
from croniter import croniter

router = APIRouter(tags=["Jobs"])


async def _check_queue_write(queue_id: uuid.UUID, user_id: str, db):
    row = await db.fetchrow(
        """SELECT q.id, q.is_paused, q.concurrency_limit, q.retry_policy_id, m.role
           FROM queues q
           JOIN projects p ON p.id = q.project_id
           JOIN organization_members m ON m.org_id = p.org_id
           WHERE q.id = $1 AND m.user_id = $2 AND q.is_active = TRUE""",
        str(queue_id), user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Queue not found")
    if row["role"] not in ('owner', 'admin', 'member'):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return row


async def _check_job_access(job_id: uuid.UUID, user_id: str, db):
    row = await db.fetchrow(
        """SELECT j.*, m.role FROM jobs j
           JOIN queues q ON q.id = j.queue_id
           JOIN projects p ON p.id = q.project_id
           JOIN organization_members m ON m.org_id = p.org_id
           WHERE j.id = $1 AND m.user_id = $2 AND j.deleted_at IS NULL""",
        str(job_id), user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return row


def _determine_initial_status(job: JobCreate) -> tuple:
    """Returns (status, scheduled_at, next_run_at) based on job type."""
    now = datetime.now(timezone.utc)
    if job.job_type == 'immediate':
        return 'pending', None, None
    elif job.job_type == 'delayed':
        if not job.scheduled_at:
            raise HTTPException(status_code=400, detail="delayed jobs require scheduled_at")
        return 'scheduled', job.scheduled_at, None
    elif job.job_type == 'scheduled':
        if not job.scheduled_at:
            raise HTTPException(status_code=400, detail="scheduled jobs require scheduled_at")
        return 'scheduled', job.scheduled_at, None
    elif job.job_type == 'recurring':
        if not job.cron_expression:
            raise HTTPException(status_code=400, detail="recurring jobs require cron_expression")
        try:
            cron = croniter(job.cron_expression, now)
            next_run = cron.get_next(datetime)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid cron expression: {job.cron_expression}")
        return 'scheduled', next_run, next_run
    elif job.job_type == 'batch':
        return 'pending', None, None
    return 'pending', None, None


# ── CREATE JOB ──────────────────────────────────────────────────
@router.post("/queues/{queue_id}/jobs", response_model=JobResponse, status_code=201)
async def create_job(queue_id: uuid.UUID, body: JobCreate, db=Depends(get_db), user=Depends(get_current_user)):
    queue = await _check_queue_write(queue_id, str(user["id"]), db)

    # Idempotency check
    if body.idempotency_key:
        existing = await db.fetchrow(
            "SELECT id FROM jobs WHERE queue_id = $1 AND idempotency_key = $2 AND deleted_at IS NULL",
            str(queue_id), body.idempotency_key,
        )
        if existing:
            return await db.fetchrow(_JOB_SELECT + " WHERE j.id = $1", str(existing["id"]))

    status, scheduled_at, next_run_at = _determine_initial_status(body)
    max_attempts = body.max_attempts

    # Use queue's retry policy if not overridden
    if queue["retry_policy_id"] and body.max_attempts == 3:
        policy = await db.fetchrow("SELECT max_attempts FROM retry_policies WHERE id = $1", str(queue["retry_policy_id"]))
        if policy:
            max_attempts = policy["max_attempts"]

    async with db.transaction():
        job = await db.fetchrow(
            """INSERT INTO jobs
               (queue_id, name, job_type, handler, payload, status, priority, max_attempts,
                timeout_seconds, scheduled_at, cron_expression, next_run_at, idempotency_key,
                tags, metadata, created_by)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
               RETURNING *""",
            str(queue_id), body.name, body.job_type, body.handler,
            dict(body.payload), status, body.priority, max_attempts,
            body.timeout_seconds, scheduled_at, body.cron_expression, next_run_at,
            body.idempotency_key, body.tags, dict(body.metadata), str(user["id"]),
        )

        # Create dependencies if any
        for dep_id in body.dependency_job_ids:
            await db.execute(
                "INSERT INTO job_dependencies (job_id, depends_on_job_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                str(job["id"]), str(dep_id),
            )

        # If has dependencies, mark as pending until deps complete
        if body.dependency_job_ids:
            await db.execute("UPDATE jobs SET status = 'pending' WHERE id = $1", str(job["id"]))

    await broadcast_event("job.created", {"job_id": str(job["id"]), "queue_id": str(queue_id), "status": status})
    return dict(job)


# ── BATCH CREATE ─────────────────────────────────────────────────
@router.post("/queues/{queue_id}/jobs/batch", status_code=201)
async def create_batch_jobs(queue_id: uuid.UUID, body: BatchJobCreate, db=Depends(get_db), user=Depends(get_current_user)):
    queue = await _check_queue_write(queue_id, str(user["id"]), db)

    async with db.transaction():
        batch = await db.fetchrow(
            """INSERT INTO batch_jobs (queue_id, name, total_jobs, created_by)
               VALUES ($1, $2, $3, $4) RETURNING id, name, total_jobs, status, created_at""",
            str(queue_id), body.name, len(body.jobs), str(user["id"]),
        )
        job_ids = []
        for job_body in body.jobs:
            job_body.job_type = 'batch'
            status, scheduled_at, next_run_at = _determine_initial_status(job_body)
            job = await db.fetchrow(
                """INSERT INTO jobs (queue_id, batch_id, name, job_type, handler, payload, status, priority,
                   max_attempts, timeout_seconds, scheduled_at, tags, metadata, created_by)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14) RETURNING id""",
                str(queue_id), str(batch["id"]), job_body.name, 'batch', job_body.handler,
                dict(job_body.payload), 'pending', job_body.priority, job_body.max_attempts,
                job_body.timeout_seconds, scheduled_at, job_body.tags, dict(job_body.metadata), str(user["id"]),
            )
            job_ids.append(str(job["id"]))

    return {"batch_id": str(batch["id"]), "job_ids": job_ids, "total": len(job_ids)}


# ── LIST JOBS ────────────────────────────────────────────────────
_JOB_SELECT = """SELECT j.id, j.queue_id, j.batch_id, j.name, j.job_type, j.handler,
    j.payload, j.status, j.priority, j.max_attempts, j.attempt_count, j.timeout_seconds,
    j.scheduled_at, j.cron_expression, j.next_run_at, j.claimed_at, j.claimed_by,
    j.started_at, j.completed_at, j.result, j.error_message, j.idempotency_key,
    j.tags, j.metadata, j.created_by, j.created_at, j.updated_at
FROM jobs j"""


@router.get("/queues/{queue_id}/jobs", response_model=JobListResponse)
async def list_jobs(
    queue_id: uuid.UUID,
    status: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    await db.fetchrow(
        """SELECT q.id FROM queues q
           JOIN projects p ON p.id = q.project_id
           JOIN organization_members m ON m.org_id = p.org_id
           WHERE q.id = $1 AND m.user_id = $2""",
        str(queue_id), str(user["id"]),
    )
    filters = ["j.queue_id = $1", "j.deleted_at IS NULL"]
    values = [str(queue_id)]
    idx = 2
    if status:
        filters.append(f"j.status = ${idx}"); values.append(status); idx += 1
    if job_type:
        filters.append(f"j.job_type = ${idx}"); values.append(job_type); idx += 1

    where = " AND ".join(filters)
    total = await db.fetchval(f"SELECT COUNT(*) FROM jobs j WHERE {where}", *values)
    offset = (page - 1) * page_size
    rows = await db.fetch(
        f"{_JOB_SELECT} WHERE {where} ORDER BY j.priority DESC, j.created_at DESC LIMIT ${idx} OFFSET ${idx+1}",
        *values, page_size, offset,
    )
    import math
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 0,
    }


@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
async def get_job(job_id: uuid.UUID, db=Depends(get_db), user=Depends(get_current_user)):
    row = await _check_job_access(job_id, str(user["id"]), db)
    job = dict(row)
    executions = await db.fetch(
        """SELECT id, job_id, worker_id, attempt_number, status, started_at, completed_at,
                  duration_ms, error_type, error_message, result, created_at
           FROM job_executions WHERE job_id = $1 ORDER BY attempt_number""",
        str(job_id),
    )
    logs = await db.fetch(
        "SELECT id, execution_id, job_id, level, message, data, logged_at FROM job_logs WHERE job_id = $1 ORDER BY logged_at DESC LIMIT 100",
        str(job_id),
    )
    job["executions"] = [dict(e) for e in executions]
    job["logs"] = [dict(l) for l in logs]
    return job


@router.post("/jobs/{job_id}/retry", response_model=JobResponse)
async def retry_job(job_id: uuid.UUID, db=Depends(get_db), user=Depends(get_current_user)):
    row = await _check_job_access(job_id, str(user["id"]), db)
    if row["status"] not in ('failed', 'cancelled', 'dead_letter'):
        raise HTTPException(status_code=400, detail=f"Cannot retry job in status '{row['status']}'")

    async with db.transaction():
        # Remove from DLQ if applicable
        await db.execute("DELETE FROM dead_letter_queue WHERE job_id = $1", str(job_id))
        job = await db.fetchrow(
            f"""UPDATE jobs SET status = 'pending', attempt_count = 0, error_message = NULL,
                claimed_by = NULL, claimed_at = NULL, started_at = NULL, completed_at = NULL
               WHERE id = $1 RETURNING *""",
            str(job_id),
        )

    await broadcast_event("job.retried", {"job_id": str(job_id)})
    return dict(job)


@router.delete("/jobs/{job_id}", status_code=204)
async def cancel_job(job_id: uuid.UUID, db=Depends(get_db), user=Depends(get_current_user)):
    row = await _check_job_access(job_id, str(user["id"]), db)
    if row["status"] in ('completed', 'dead_letter'):
        raise HTTPException(status_code=400, detail="Cannot cancel a completed or dead-lettered job")
    await db.execute(
        "UPDATE jobs SET status = 'cancelled', deleted_at = NOW() WHERE id = $1", str(job_id)
    )
    await broadcast_event("job.cancelled", {"job_id": str(job_id)})


@router.get("/jobs/{job_id}/logs", response_model=List[JobLogResponse])
async def get_job_logs(
    job_id: uuid.UUID,
    level: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    await _check_job_access(job_id, str(user["id"]), db)
    filters = ["job_id = $1"]
    values = [str(job_id)]
    idx = 2
    if level:
        filters.append(f"level = ${idx}"); values.append(level); idx += 1
    rows = await db.fetch(
        f"SELECT id, execution_id, job_id, level, message, data, logged_at FROM job_logs WHERE {' AND '.join(filters)} ORDER BY logged_at DESC LIMIT ${idx}",
        *values, limit,
    )
    return [dict(r) for r in rows]


# ── DEAD LETTER QUEUE ────────────────────────────────────────────
@router.get("/queues/{queue_id}/dlq", response_model=List[DLQEntryResponse])
async def get_dlq(
    queue_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    await db.fetchrow(
        """SELECT q.id FROM queues q
           JOIN projects p ON p.id = q.project_id
           JOIN organization_members m ON m.org_id = p.org_id
           WHERE q.id = $1 AND m.user_id = $2""",
        str(queue_id), str(user["id"]),
    )
    offset = (page - 1) * page_size
    rows = await db.fetch(
        """SELECT d.id, d.job_id, d.queue_id, d.final_error, d.total_attempts,
                  d.moved_at, d.resolved_at, d.resolution, d.ai_failure_summary
           FROM dead_letter_queue d
           WHERE d.queue_id = $1 AND d.resolved_at IS NULL
           ORDER BY d.moved_at DESC LIMIT $2 OFFSET $3""",
        str(queue_id), page_size, offset,
    )
    return [dict(r) for r in rows]


@router.post("/dlq/{dlq_id}/retry", status_code=200)
async def retry_dlq_entry(dlq_id: uuid.UUID, db=Depends(get_db), user=Depends(get_current_user)):
    entry = await db.fetchrow("SELECT * FROM dead_letter_queue WHERE id = $1", str(dlq_id))
    if not entry:
        raise HTTPException(status_code=404, detail="DLQ entry not found")

    async with db.transaction():
        await db.execute(
            "UPDATE dead_letter_queue SET resolved_at = NOW(), resolution = 'retried' WHERE id = $1",
            str(dlq_id),
        )
        job = await db.fetchrow(
            "UPDATE jobs SET status = 'pending', attempt_count = 0, error_message = NULL, claimed_by = NULL WHERE id = $1 RETURNING *",
            str(entry["job_id"]),
        )
    await broadcast_event("job.retried", {"job_id": str(entry["job_id"])})
    return {"message": "Job re-queued", "job_id": str(entry["job_id"])}


@router.delete("/dlq/{dlq_id}", status_code=204)
async def discard_dlq_entry(dlq_id: uuid.UUID, db=Depends(get_db), user=Depends(get_current_user)):
    await db.execute(
        "UPDATE dead_letter_queue SET resolved_at = NOW(), resolution = 'discarded' WHERE id = $1",
        str(dlq_id),
    )
