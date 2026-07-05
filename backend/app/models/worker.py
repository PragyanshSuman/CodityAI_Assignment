from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


class WorkerRegister(BaseModel):
    name: Optional[str] = None
    hostname: Optional[str] = None
    max_concurrency: int = Field(default=10, ge=1, le=500)
    capabilities: List[str] = Field(default_factory=list)


class WorkerHeartbeat(BaseModel):
    status: str = Field(default='active')
    current_jobs: int = Field(default=0, ge=0)
    memory_mb: Optional[float] = None
    cpu_percent: Optional[float] = None


class WorkerResponse(BaseModel):
    id: uuid.UUID
    name: Optional[str]
    hostname: Optional[str]
    ip_address: Optional[str]
    pid: Optional[int]
    status: str
    capabilities: List[str]
    max_concurrency: int
    current_jobs: int
    started_at: datetime
    last_heartbeat_at: datetime
    shutdown_at: Optional[datetime]
    is_healthy: bool = False


class WorkerHeartbeatRecord(BaseModel):
    id: int
    worker_id: uuid.UUID
    status: Optional[str]
    current_jobs: Optional[int]
    memory_mb: Optional[float]
    cpu_percent: Optional[float]
    recorded_at: datetime
