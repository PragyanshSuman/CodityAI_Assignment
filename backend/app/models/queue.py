from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


class RetryPolicyCreate(BaseModel):
    name: Optional[str] = None
    strategy: str = Field(default='exponential')
    max_attempts: int = Field(default=3, ge=1, le=50)
    initial_delay_seconds: int = Field(default=60, ge=0)
    max_delay_seconds: Optional[int] = Field(default=3600, ge=0)
    multiplier: float = Field(default=2.0, ge=1.0)
    jitter: bool = False

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Fast Retry",
                "strategy": "exponential",
                "max_attempts": 5,
                "initial_delay_seconds": 30,
                "max_delay_seconds": 1800,
                "multiplier": 2.0,
                "jitter": True
            }
        }


class RetryPolicyResponse(BaseModel):
    id: uuid.UUID
    name: Optional[str]
    strategy: str
    max_attempts: int
    initial_delay_seconds: int
    max_delay_seconds: Optional[int]
    multiplier: float
    jitter: bool
    created_at: datetime


class QueueCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=100, pattern=r'^[a-z0-9-]+$')
    description: Optional[str] = None
    priority: int = Field(default=5, ge=1, le=10)
    concurrency_limit: int = Field(default=10, ge=1, le=1000)
    rate_limit_per_minute: Optional[int] = Field(default=None, ge=1)
    retry_policy_id: Optional[uuid.UUID] = None


class QueueUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=10)
    concurrency_limit: Optional[int] = Field(None, ge=1, le=1000)
    rate_limit_per_minute: Optional[int] = None
    retry_policy_id: Optional[uuid.UUID] = None


class QueueResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    slug: str
    description: Optional[str]
    priority: int
    concurrency_limit: int
    rate_limit_per_minute: Optional[int]
    retry_policy_id: Optional[uuid.UUID]
    is_paused: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class QueueStats(BaseModel):
    queue_id: uuid.UUID
    pending_count: int
    running_count: int
    completed_count: int
    failed_count: int
    dead_letter_count: int
    avg_wait_time_ms: Optional[float]
    avg_execution_time_ms: Optional[float]
    throughput_per_minute: Optional[float]
