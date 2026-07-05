from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
import asyncpg
import uuid

from app.database import get_db
from app.dependencies import get_current_user
from app.models.queue import QueueCreate, QueueUpdate, QueueResponse, QueueStats, RetryPolicyCreate, RetryPolicyResponse
from app.websocket.manager import broadcast_event

router = APIRouter(tags=["Queues"])


async def _check_project_access(project_id: uuid.UUID, user_id: str, db, min_role=('owner', 'admin', 'member', 'viewer')):
    row = await db.fetchrow(
        """SELECT m.role FROM projects p
           JOIN organization_members m ON m.org_id = p.org_id
           WHERE p.id = $1 AND m.user_id = $2""",
        str(project_id), user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    if row["role"] not in min_role:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return row["role"]


async def _check_queue_access(queue_id: uuid.UUID, user_id: str, db, min_role=('owner', 'admin', 'member', 'viewer')):
    row = await db.fetchrow(
        """SELECT q.id, q.project_id, m.role FROM queues q
           JOIN projects p ON p.id = q.project_id
           JOIN organization_members m ON m.org_id = p.org_id
           WHERE q.id = $1 AND m.user_id = $2""",
        str(queue_id), user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Queue not found")
    if row["role"] not in min_role:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return row


# ── RETRY POLICIES ──────────────────────────────────────────────
@router.get("/retry-policies", response_model=List[RetryPolicyResponse])
async def list_retry_policies(db=Depends(get_db), user=Depends(get_current_user)):
    rows = await db.fetch("SELECT * FROM retry_policies ORDER BY created_at")
    return [dict(r) for r in rows]


@router.post("/retry-policies", response_model=RetryPolicyResponse, status_code=201)
async def create_retry_policy(body: RetryPolicyCreate, db=Depends(get_db), user=Depends(get_current_user)):
    row = await db.fetchrow(
        """INSERT INTO retry_policies (name, strategy, max_attempts, initial_delay_seconds, max_delay_seconds, multiplier, jitter)
           VALUES ($1, $2, $3, $4, $5, $6, $7)
           RETURNING *""",
        body.name, body.strategy, body.max_attempts, body.initial_delay_seconds,
        body.max_delay_seconds, body.multiplier, body.jitter,
    )
    return dict(row)


# ── QUEUES ──────────────────────────────────────────────────────
@router.post("/projects/{project_id}/queues", response_model=QueueResponse, status_code=201)
async def create_queue(project_id: uuid.UUID, body: QueueCreate, db=Depends(get_db), user=Depends(get_current_user)):
    await _check_project_access(project_id, str(user["id"]), db, min_role=('owner', 'admin', 'member'))

    try:
        queue = await db.fetchrow(
            """INSERT INTO queues (project_id, name, slug, description, priority, concurrency_limit, rate_limit_per_minute, retry_policy_id)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
               RETURNING id, project_id, name, slug, description, priority, concurrency_limit, rate_limit_per_minute, retry_policy_id, is_paused, is_active, created_at, updated_at""",
            str(project_id), body.name, body.slug, body.description,
            body.priority, body.concurrency_limit, body.rate_limit_per_minute,
            str(body.retry_policy_id) if body.retry_policy_id else None,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="Queue slug already exists in this project")

    # Initialize rate limit bucket if needed
    if body.rate_limit_per_minute:
        await db.execute(
            """INSERT INTO rate_limit_buckets (queue_id, tokens, max_tokens, refill_rate)
               VALUES ($1, $2, $2, $3) ON CONFLICT DO NOTHING""",
            str(queue["id"]), float(body.rate_limit_per_minute),
            body.rate_limit_per_minute / 60.0,
        )

    await broadcast_event("queue.created", dict(queue))
    return dict(queue)


@router.get("/projects/{project_id}/queues", response_model=List[QueueResponse])
async def list_queues(project_id: uuid.UUID, db=Depends(get_db), user=Depends(get_current_user)):
    await _check_project_access(project_id, str(user["id"]), db)
    rows = await db.fetch(
        """SELECT id, project_id, name, slug, description, priority, concurrency_limit,
                  rate_limit_per_minute, retry_policy_id, is_paused, is_active, created_at, updated_at
           FROM queues WHERE project_id = $1 AND is_active = TRUE ORDER BY priority DESC, name""",
        str(project_id),
    )
    return [dict(r) for r in rows]


@router.get("/queues/{queue_id}", response_model=QueueResponse)
async def get_queue(queue_id: uuid.UUID, db=Depends(get_db), user=Depends(get_current_user)):
    await _check_queue_access(queue_id, str(user["id"]), db)
    queue = await db.fetchrow(
        "SELECT id, project_id, name, slug, description, priority, concurrency_limit, rate_limit_per_minute, retry_policy_id, is_paused, is_active, created_at, updated_at FROM queues WHERE id = $1",
        str(queue_id),
    )
    return dict(queue)


@router.patch("/queues/{queue_id}", response_model=QueueResponse)
async def update_queue(queue_id: uuid.UUID, body: QueueUpdate, db=Depends(get_db), user=Depends(get_current_user)):
    await _check_queue_access(queue_id, str(user["id"]), db, min_role=('owner', 'admin', 'member'))
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    set_clauses = [f"{k} = ${i+2}" for i, k in enumerate(updates)]
    queue = await db.fetchrow(
        f"UPDATE queues SET {', '.join(set_clauses)} WHERE id = $1 RETURNING id, project_id, name, slug, description, priority, concurrency_limit, rate_limit_per_minute, retry_policy_id, is_paused, is_active, created_at, updated_at",
        str(queue_id), *list(updates.values()),
    )
    await broadcast_event("queue.updated", dict(queue))
    return dict(queue)


@router.post("/queues/{queue_id}/pause", response_model=QueueResponse)
async def pause_queue(queue_id: uuid.UUID, db=Depends(get_db), user=Depends(get_current_user)):
    await _check_queue_access(queue_id, str(user["id"]), db, min_role=('owner', 'admin', 'member'))
    queue = await db.fetchrow(
        "UPDATE queues SET is_paused = TRUE WHERE id = $1 RETURNING id, project_id, name, slug, description, priority, concurrency_limit, rate_limit_per_minute, retry_policy_id, is_paused, is_active, created_at, updated_at",
        str(queue_id),
    )
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")
    await broadcast_event("queue.paused", {"queue_id": str(queue_id)})
    return dict(queue)


@router.post("/queues/{queue_id}/resume", response_model=QueueResponse)
async def resume_queue(queue_id: uuid.UUID, db=Depends(get_db), user=Depends(get_current_user)):
    await _check_queue_access(queue_id, str(user["id"]), db, min_role=('owner', 'admin', 'member'))
    queue = await db.fetchrow(
        "UPDATE queues SET is_paused = FALSE WHERE id = $1 RETURNING id, project_id, name, slug, description, priority, concurrency_limit, rate_limit_per_minute, retry_policy_id, is_paused, is_active, created_at, updated_at",
        str(queue_id),
    )
    await broadcast_event("queue.resumed", {"queue_id": str(queue_id)})
    return dict(queue)


@router.delete("/queues/{queue_id}", status_code=204)
async def delete_queue(queue_id: uuid.UUID, db=Depends(get_db), user=Depends(get_current_user)):
    await _check_queue_access(queue_id, str(user["id"]), db, min_role=('owner', 'admin'))
    await db.execute("UPDATE queues SET is_active = FALSE WHERE id = $1", str(queue_id))


@router.get("/queues/{queue_id}/stats", response_model=QueueStats)
async def get_queue_stats(queue_id: uuid.UUID, db=Depends(get_db), user=Depends(get_current_user)):
    await _check_queue_access(queue_id, str(user["id"]), db)
    row = await db.fetchrow(
        """SELECT
            COUNT(*) FILTER (WHERE status = 'pending') AS pending_count,
            COUNT(*) FILTER (WHERE status = 'running') AS running_count,
            COUNT(*) FILTER (WHERE status = 'completed') AS completed_count,
            COUNT(*) FILTER (WHERE status = 'failed') AS failed_count,
            COUNT(*) FILTER (WHERE status = 'dead_letter') AS dead_letter_count
           FROM jobs WHERE queue_id = $1 AND deleted_at IS NULL""",
        str(queue_id),
    )
    perf = await db.fetchrow(
        """SELECT
            AVG(EXTRACT(EPOCH FROM (started_at - created_at)) * 1000) AS avg_wait_time_ms,
            AVG(duration_ms) AS avg_execution_time_ms
           FROM job_executions
           WHERE job_id IN (SELECT id FROM jobs WHERE queue_id = $1)
             AND status = 'completed'
             AND started_at > NOW() - INTERVAL '1 hour'""",
        str(queue_id),
    )
    throughput = await db.fetchval(
        """SELECT COUNT(*) FROM jobs
           WHERE queue_id = $1 AND status = 'completed'
             AND completed_at > NOW() - INTERVAL '1 minute'""",
        str(queue_id),
    )
    return {
        "queue_id": queue_id,
        "pending_count": row["pending_count"],
        "running_count": row["running_count"],
        "completed_count": row["completed_count"],
        "failed_count": row["failed_count"],
        "dead_letter_count": row["dead_letter_count"],
        "avg_wait_time_ms": perf["avg_wait_time_ms"] if perf else None,
        "avg_execution_time_ms": perf["avg_execution_time_ms"] if perf else None,
        "throughput_per_minute": float(throughput or 0),
    }
