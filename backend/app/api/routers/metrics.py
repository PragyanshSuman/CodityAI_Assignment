from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from typing import List
import asyncpg

from app.database import get_db
from app.dependencies import get_current_user
from app.models.metrics import MetricsOverview, SystemOverview, QueueMetrics, ThroughputDataPoint

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("/overview", response_model=MetricsOverview)
async def get_metrics_overview(db=Depends(get_db), user=Depends(get_current_user)):
    # System-wide job counts
    job_counts = await db.fetchrow(
        """SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'pending') AS pending,
            COUNT(*) FILTER (WHERE status = 'running') AS running,
            COUNT(*) FILTER (WHERE status = 'completed') AS completed,
            COUNT(*) FILTER (WHERE status = 'failed') AS failed,
            COUNT(*) FILTER (WHERE status = 'dead_letter') AS dead_letter
           FROM jobs WHERE deleted_at IS NULL"""
    )
    active_workers = await db.fetchval(
        "SELECT COUNT(*) FROM workers WHERE status IN ('active','idle') AND last_heartbeat_at > NOW() - INTERVAL '30 seconds'"
    )
    queue_counts = await db.fetchrow(
        "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE is_paused) AS paused FROM queues WHERE is_active = TRUE"
    )
    perf = await db.fetchrow(
        """SELECT
            AVG(duration_ms) AS avg_exec_ms,
            COUNT(*) FILTER (WHERE status = 'completed' AND started_at > NOW() - INTERVAL '1 minute') AS jpm
           FROM job_executions WHERE started_at > NOW() - INTERVAL '1 hour'"""
    )
    completed = job_counts["completed"] or 0
    failed = job_counts["failed"] or 0
    total_terminal = completed + failed
    success_rate = (completed / total_terminal * 100) if total_terminal > 0 else 100.0

    system = SystemOverview(
        total_jobs=job_counts["total"],
        pending_jobs=job_counts["pending"],
        running_jobs=job_counts["running"],
        completed_jobs=completed,
        failed_jobs=failed,
        dead_letter_jobs=job_counts["dead_letter"],
        active_workers=active_workers or 0,
        total_queues=queue_counts["total"],
        paused_queues=queue_counts["paused"],
        jobs_per_minute=float(perf["jpm"] or 0),
        avg_execution_time_ms=perf["avg_exec_ms"],
        success_rate=round(success_rate, 2),
    )

    # Per-queue metrics
    queue_rows = await db.fetch(
        """SELECT
            q.id, q.name, q.is_paused,
            COUNT(j.id) FILTER (WHERE j.status = 'pending') AS pending_count,
            COUNT(j.id) FILTER (WHERE j.status = 'running') AS running_count,
            COUNT(j.id) FILTER (WHERE j.status = 'completed') AS completed_count,
            COUNT(j.id) FILTER (WHERE j.status = 'failed') AS failed_count,
            COUNT(j.id) FILTER (WHERE j.status = 'dead_letter') AS dead_letter_count
           FROM queues q
           LEFT JOIN jobs j ON j.queue_id = q.id AND j.deleted_at IS NULL
           WHERE q.is_active = TRUE
           GROUP BY q.id, q.name, q.is_paused
           ORDER BY (COUNT(j.id) FILTER (WHERE j.status IN ('pending','running'))) DESC"""
    )
    queues = [
        QueueMetrics(
            queue_id=r["id"],
            queue_name=r["name"],
            pending_count=r["pending_count"] or 0,
            running_count=r["running_count"] or 0,
            completed_count=r["completed_count"] or 0,
            failed_count=r["failed_count"] or 0,
            dead_letter_count=r["dead_letter_count"] or 0,
            avg_wait_time_ms=None,
            avg_execution_time_ms=None,
            throughput_per_minute=None,
            is_paused=r["is_paused"],
        )
        for r in queue_rows
    ]

    # Throughput history (last 60 minutes, 5-min buckets)
    throughput_rows = await db.fetch(
        """SELECT
            date_trunc('minute', completed_at) - (EXTRACT(MINUTE FROM completed_at)::int % 5) * INTERVAL '1 minute' AS bucket,
            COUNT(*) FILTER (WHERE status = 'completed') AS completed,
            COUNT(*) FILTER (WHERE status = 'failed') AS failed,
            COUNT(*) AS total
           FROM jobs
           WHERE completed_at > NOW() - INTERVAL '60 minutes' AND deleted_at IS NULL
           GROUP BY bucket ORDER BY bucket"""
    )
    throughput_history = [
        ThroughputDataPoint(
            timestamp=r["bucket"],
            completed=r["completed"] or 0,
            failed=r["failed"] or 0,
            total=r["total"] or 0,
        )
        for r in throughput_rows
    ]

    return MetricsOverview(system=system, queues=queues, throughput_history=throughput_history)


@router.get("/queues/{queue_id}")
async def get_queue_metrics(queue_id: str, db=Depends(get_db), user=Depends(get_current_user)):
    rows = await db.fetch(
        """SELECT pending_count, running_count, completed_count, failed_count,
                  avg_execution_time_ms, throughput_per_minute, recorded_at
           FROM queue_stats_snapshots
           WHERE queue_id = $1 ORDER BY recorded_at DESC LIMIT 60""",
        queue_id,
    )
    return [dict(r) for r in rows]
