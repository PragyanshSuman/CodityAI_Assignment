from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


class JobCreate(BaseModel):
    name: Optional[str] = None
    job_type: str = Field(default='immediate')
    handler: str = Field(default='default', min_length=1)
    payload: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=5, ge=1, le=10)
    max_attempts: int = Field(default=3, ge=1, le=50)
    timeout_seconds: int = Field(default=300, ge=1, le=86400)
    scheduled_at: Optional[datetime] = None
    cron_expression: Optional[str] = None
    idempotency_key: Optional[str] = Field(None, max_length=255)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    dependency_job_ids: List[uuid.UUID] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Send Welcome Email",
                "job_type": "immediate",
                "handler": "email.send_welcome",
                "payload": {"user_id": "abc123", "template": "welcome"},
                "priority": 7,
                "max_attempts": 3,
                "timeout_seconds": 60
            }
        }


class BatchJobCreate(BaseModel):
    name: Optional[str] = None
    jobs: List[JobCreate] = Field(min_length=1, max_length=1000)


class JobUpdate(BaseModel):
    priority: Optional[int] = Field(None, ge=1, le=10)
    max_attempts: Optional[int] = Field(None, ge=1, le=50)
    timeout_seconds: Optional[int] = Field(None, ge=1, le=86400)


class JobExecutionResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    worker_id: Optional[uuid.UUID]
    attempt_number: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    error_type: Optional[str]
    error_message: Optional[str]
    result: Optional[Dict[str, Any]]
    created_at: datetime


class JobLogResponse(BaseModel):
    id: int
    execution_id: uuid.UUID
    job_id: uuid.UUID
    level: str
    message: str
    data: Optional[Dict[str, Any]]
    logged_at: datetime


class JobResponse(BaseModel):
    id: uuid.UUID
    queue_id: uuid.UUID
    batch_id: Optional[uuid.UUID]
    name: Optional[str]
    job_type: str
    handler: str
    payload: Dict[str, Any]
    status: str
    priority: int
    max_attempts: int
    attempt_count: int
    timeout_seconds: int
    scheduled_at: Optional[datetime]
    cron_expression: Optional[str]
    next_run_at: Optional[datetime]
    claimed_at: Optional[datetime]
    claimed_by: Optional[uuid.UUID]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    idempotency_key: Optional[str]
    tags: List[str]
    metadata: Dict[str, Any]
    created_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime


class JobDetailResponse(JobResponse):
    executions: List[JobExecutionResponse] = Field(default_factory=list)
    logs: List[JobLogResponse] = Field(default_factory=list)


class DLQEntryResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    queue_id: uuid.UUID
    final_error: Optional[str]
    total_attempts: int
    moved_at: datetime
    resolved_at: Optional[datetime]
    resolution: Optional[str]
    ai_failure_summary: Optional[str]
    job: Optional[JobResponse] = None


class JobListResponse(BaseModel):
    items: List[JobResponse]
    total: int
    page: int
    page_size: int
    pages: int
