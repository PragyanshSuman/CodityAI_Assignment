from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List
import asyncpg
import uuid
import socket
import os
from datetime import datetime, timezone, timedelta

from app.database import get_db
from app.dependencies import get_current_user
from app.models.worker import WorkerRegister, WorkerHeartbeat, WorkerResponse, WorkerHeartbeatRecord

router = APIRouter(prefix="/workers", tags=["Workers"])

STALE_THRESHOLD_SECONDS = 30


@router.post("/register", response_model=WorkerResponse, status_code=201)
async def register_worker(body: WorkerRegister, request: Request, db=Depends(get_db), user=Depends(get_current_user)):
    client_ip = request.client.host if request.client else None
    worker = await db.fetchrow(
        """INSERT INTO workers (name, hostname, ip_address, pid, max_concurrency, capabilities)
           VALUES ($1, $2, $3, $4, $5, $6)
           RETURNING id, name, hostname, ip_address, pid, status, capabilities, max_concurrency,
                     current_jobs, started_at, last_heartbeat_at, shutdown_at""",
        body.name or f"worker-{uuid.uuid4().hex[:8]}",
        body.hostname or socket.gethostname(),
        client_ip, os.getpid(),
        body.max_concurrency, body.capabilities,
    )
    result = dict(worker)
    result["is_healthy"] = True
    return result


@router.post("/{worker_id}/heartbeat", response_model=WorkerResponse)
async def worker_heartbeat(worker_id: uuid.UUID, body: WorkerHeartbeat, db=Depends(get_db)):
    """No auth required for heartbeat — workers use their ID."""
    async with db.transaction():
        worker = await db.fetchrow(
            """UPDATE workers SET last_heartbeat_at = NOW(), status = $2, current_jobs = $3
               WHERE id = $1 AND status != 'offline'
               RETURNING id, name, hostname, ip_address, pid, status, capabilities,
                         max_concurrency, current_jobs, started_at, last_heartbeat_at, shutdown_at""",
            str(worker_id), body.status, body.current_jobs,
        )
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found or offline")

        await db.execute(
            """INSERT INTO worker_heartbeats (worker_id, status, current_jobs, memory_mb, cpu_percent)
               VALUES ($1, $2, $3, $4, $5)""",
            str(worker_id), body.status, body.current_jobs, body.memory_mb, body.cpu_percent,
        )
    result = dict(worker)
    result["is_healthy"] = True
    return result


@router.get("", response_model=List[WorkerResponse])
async def list_workers(db=Depends(get_db), user=Depends(get_current_user)):
    stale_cutoff = datetime.now(timezone.utc) - timedelta(seconds=STALE_THRESHOLD_SECONDS)
    rows = await db.fetch(
        """SELECT id, name, hostname, ip_address, pid, status, capabilities, max_concurrency,
                  current_jobs, started_at, last_heartbeat_at, shutdown_at
           FROM workers WHERE status != 'offline' ORDER BY started_at DESC""",
    )
    result = []
    for r in rows:
        w = dict(r)
        w["is_healthy"] = w["last_heartbeat_at"] and w["last_heartbeat_at"].replace(tzinfo=timezone.utc) > stale_cutoff
        result.append(w)
    return result


@router.get("/{worker_id}", response_model=WorkerResponse)
async def get_worker(worker_id: uuid.UUID, db=Depends(get_db), user=Depends(get_current_user)):
    stale_cutoff = datetime.now(timezone.utc) - timedelta(seconds=STALE_THRESHOLD_SECONDS)
    row = await db.fetchrow(
        """SELECT id, name, hostname, ip_address, pid, status, capabilities, max_concurrency,
                  current_jobs, started_at, last_heartbeat_at, shutdown_at
           FROM workers WHERE id = $1""",
        str(worker_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Worker not found")
    w = dict(row)
    w["is_healthy"] = w["last_heartbeat_at"] and w["last_heartbeat_at"].replace(tzinfo=timezone.utc) > stale_cutoff
    return w


@router.post("/{worker_id}/shutdown", status_code=200)
async def shutdown_worker(worker_id: uuid.UUID, db=Depends(get_db), user=Depends(get_current_user)):
    await db.execute(
        "UPDATE workers SET status = 'draining', shutdown_at = NOW() WHERE id = $1",
        str(worker_id),
    )
    return {"message": "Worker shutdown initiated"}


@router.get("/{worker_id}/heartbeats", response_model=List[WorkerHeartbeatRecord])
async def get_worker_heartbeats(
    worker_id: uuid.UUID,
    limit: int = 50,
    db=Depends(get_db),
    user=Depends(get_current_user),
):
    rows = await db.fetch(
        """SELECT id, worker_id, status, current_jobs, memory_mb, cpu_percent, recorded_at
           FROM worker_heartbeats WHERE worker_id = $1 ORDER BY recorded_at DESC LIMIT $2""",
        str(worker_id), limit,
    )
    return [dict(r) for r in rows]
