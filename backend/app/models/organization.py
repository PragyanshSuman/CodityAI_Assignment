from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


class OrgCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=100, pattern=r'^[a-z0-9-]+$')
    description: Optional[str] = None


class OrgUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None


class OrgResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: Optional[str]
    created_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime


class MemberInvite(BaseModel):
    user_email: str
    role: str = Field(default='member')

    class Config:
        json_schema_extra = {
            "example": {"user_email": "dev@example.com", "role": "member"}
        }


class MemberResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    joined_at: datetime


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=100, pattern=r'^[a-z0-9-]+$')
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    slug: str
    description: Optional[str]
    created_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    expires_at: Optional[datetime] = None


class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    key_prefix: str
    is_active: bool
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Returned only once on creation — includes the raw key."""
    raw_key: str
