from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid


class SystemOverview(BaseModel):
    total_jobs: int
    pending_jobs: int
    running_jobs: int
    completed_jobs: int
    failed_jobs: int
    dead_letter_jobs: int
    active_workers: int
    total_queues: int
    paused_queues: int
    jobs_per_minute: float
    avg_execution_time_ms: Optional[float]
    success_rate: float


class ThroughputDataPoint(BaseModel):
    timestamp: datetime
    completed: int
    failed: int
    total: int


class QueueMetrics(BaseModel):
    queue_id: uuid.UUID
    queue_name: str
    pending_count: int
    running_count: int
    completed_count: int
    failed_count: int
    dead_letter_count: int
    avg_wait_time_ms: Optional[float]
    avg_execution_time_ms: Optional[float]
    throughput_per_minute: Optional[float]
    is_paused: bool


class MetricsOverview(BaseModel):
    system: SystemOverview
    queues: List[QueueMetrics]
    throughput_history: List[ThroughputDataPoint]
