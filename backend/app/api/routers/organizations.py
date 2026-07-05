from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
import asyncpg
import uuid

from app.database import get_db
from app.dependencies import get_current_user
from app.models.organization import (
    OrgCreate, OrgUpdate, OrgResponse,
    MemberInvite, MemberResponse,
    ProjectCreate, ProjectUpdate, ProjectResponse,
    ApiKeyCreate, ApiKeyResponse, ApiKeyCreatedResponse,
)
import secrets
import hashlib

router = APIRouter(tags=["Organizations & Projects"])


# ── ORGANIZATIONS ────────────────────────────────────────────────
@router.post("/orgs", response_model=OrgResponse, status_code=201)
async def create_org(body: OrgCreate, db=Depends(get_db), user=Depends(get_current_user)):
    existing = await db.fetchrow("SELECT id FROM organizations WHERE slug = $1", body.slug)
    if existing:
        raise HTTPException(status_code=409, detail="Slug already taken")

    org = await db.fetchrow(
        """INSERT INTO organizations (name, slug, description, created_by)
           VALUES ($1, $2, $3, $4)
           RETURNING id, name, slug, description, created_by, created_at, updated_at""",
        body.name, body.slug, body.description, str(user["id"]),
    )
    # Auto-add creator as owner
    await db.execute(
        "INSERT INTO organization_members (org_id, user_id, role) VALUES ($1, $2, 'owner')",
        str(org["id"]), str(user["id"]),
    )
    return dict(org)


@router.get("/orgs", response_model=List[OrgResponse])
async def list_orgs(db=Depends(get_db), user=Depends(get_current_user)):
    rows = await db.fetch(
        """SELECT o.id, o.name, o.slug, o.description, o.created_by, o.created_at, o.updated_at
           FROM organizations o
           JOIN organization_members m ON m.org_id = o.id
           WHERE m.user_id = $1
           ORDER BY o.created_at DESC""",
        str(user["id"]),
    )
    return [dict(r) for r in rows]


@router.get("/orgs/{org_id}", response_model=OrgResponse)
async def get_org(org_id: uuid.UUID, db=Depends(get_db), user=Depends(get_current_user)):
    org = await db.fetchrow(
        """SELECT o.id, o.name, o.slug, o.description, o.created_by, o.created_at, o.updated_at
           FROM organizations o
           JOIN organization_members m ON m.org_id = o.id
           WHERE o.id = $1 AND m.user_id = $2""",
        str(org_id), str(user["id"]),
    )
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return dict(org)


@router.patch("/orgs/{org_id}", response_model=OrgResponse)
async def update_org(org_id: uuid.UUID, body: OrgUpdate, db=Depends(get_db), user=Depends(get_current_user)):
    row = await db.fetchrow(
        "SELECT role FROM organization_members WHERE org_id = $1 AND user_id = $2",
        str(org_id), str(user["id"]),
    )
    if not row or row["role"] not in ('owner', 'admin'):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = [f"{k} = ${i+2}" for i, k in enumerate(updates)]
    values = list(updates.values())
    org = await db.fetchrow(
        f"UPDATE organizations SET {', '.join(set_clauses)} WHERE id = $1 RETURNING id, name, slug, description, created_by, created_at, updated_at",
        str(org_id), *values,
    )
    return dict(org)


@router.delete("/orgs/{org_id}", status_code=204)
async def delete_org(org_id: uuid.UUID, db=Depends(get_db), user=Depends(get_current_user)):
    row = await db.fetchrow(
        "SELECT role FROM organization_members WHERE org_id = $1 AND user_id = $2",
        str(org_id), str(user["id"]),
    )
    if not row or row["role"] != 'owner':
        raise HTTPException(status_code=403, detail="Only owner can delete organization")
    await db.execute("DELETE FROM organizations WHERE id = $1", str(org_id))


# ── MEMBERS ──────────────────────────────────────────────────────
@router.get("/orgs/{org_id}/members", response_model=List[MemberResponse])
async def list_members(org_id: uuid.UUID, db=Depends(get_db), user=Depends(get_current_user)):
    _check_member(await db.fetchrow(
        "SELECT role FROM organization_members WHERE org_id = $1 AND user_id = $2",
        str(org_id), str(user["id"]),
    ))
    rows = await db.fetch(
        "SELECT id, org_id, user_id, role, joined_at FROM organization_members WHERE org_id = $1",
        str(org_id),
    )
    return [dict(r) for r in rows]


@router.post("/orgs/{org_id}/members", response_model=MemberResponse, status_code=201)
async def invite_member(org_id: uuid.UUID, body: MemberInvite, db=Depends(get_db), user=Depends(get_current_user)):
    row = await db.fetchrow(
        "SELECT role FROM organization_members WHERE org_id = $1 AND user_id = $2",
        str(org_id), str(user["id"]),
    )
    if not row or row["role"] not in ('owner', 'admin'):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    invitee = await db.fetchrow("SELECT id FROM users WHERE email = $1", body.user_email)
    if not invitee:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        member = await db.fetchrow(
            """INSERT INTO organization_members (org_id, user_id, role, invited_by)
               VALUES ($1, $2, $3, $4)
               RETURNING id, org_id, user_id, role, joined_at""",
            str(org_id), str(invitee["id"]), body.role, str(user["id"]),
        )
        return dict(member)
    except Exception:
        raise HTTPException(status_code=409, detail="User already a member")


def _check_member(row):
    if not row:
        raise HTTPException(status_code=403, detail="Not a member of this organization")


# ── PROJECTS ──────────────────────────────────────────────────────
@router.post("/orgs/{org_id}/projects", response_model=ProjectResponse, status_code=201)
async def create_project(org_id: uuid.UUID, body: ProjectCreate, db=Depends(get_db), user=Depends(get_current_user)):
    row = await db.fetchrow(
        "SELECT role FROM organization_members WHERE org_id = $1 AND user_id = $2",
        str(org_id), str(user["id"]),
    )
    if not row or row["role"] not in ('owner', 'admin', 'member'):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    try:
        project = await db.fetchrow(
            """INSERT INTO projects (org_id, name, slug, description, created_by)
               VALUES ($1, $2, $3, $4, $5)
               RETURNING id, org_id, name, slug, description, created_by, created_at, updated_at""",
            str(org_id), body.name, body.slug, body.description, str(user["id"]),
        )
        return dict(project)
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="Slug already taken in this organization")


@router.get("/orgs/{org_id}/projects", response_model=List[ProjectResponse])
async def list_projects(org_id: uuid.UUID, db=Depends(get_db), user=Depends(get_current_user)):
    _check_member(await db.fetchrow(
        "SELECT role FROM organization_members WHERE org_id = $1 AND user_id = $2",
        str(org_id), str(user["id"]),
    ))
    rows = await db.fetch(
        "SELECT id, org_id, name, slug, description, created_by, created_at, updated_at FROM projects WHERE org_id = $1 ORDER BY created_at DESC",
        str(org_id),
    )
    return [dict(r) for r in rows]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: uuid.UUID, db=Depends(get_db), user=Depends(get_current_user)):
    project = await db.fetchrow(
        """SELECT p.id, p.org_id, p.name, p.slug, p.description, p.created_by, p.created_at, p.updated_at
           FROM projects p
           JOIN organization_members m ON m.org_id = p.org_id
           WHERE p.id = $1 AND m.user_id = $2""",
        str(project_id), str(user["id"]),
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return dict(project)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: uuid.UUID, body: ProjectUpdate, db=Depends(get_db), user=Depends(get_current_user)):
    project = await _get_project_with_auth(project_id, user["id"], db, min_role=('owner', 'admin', 'member'))
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    set_clauses = [f"{k} = ${i+2}" for i, k in enumerate(updates)]
    p = await db.fetchrow(
        f"UPDATE projects SET {', '.join(set_clauses)} WHERE id = $1 RETURNING id, org_id, name, slug, description, created_by, created_at, updated_at",
        str(project_id), *list(updates.values()),
    )
    return dict(p)


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: uuid.UUID, db=Depends(get_db), user=Depends(get_current_user)):
    await _get_project_with_auth(project_id, user["id"], db, min_role=('owner', 'admin'))
    await db.execute("DELETE FROM projects WHERE id = $1", str(project_id))


async def _get_project_with_auth(project_id, user_id, db, min_role=('owner', 'admin', 'member', 'viewer')):
    project = await db.fetchrow(
        """SELECT p.id, p.org_id, m.role FROM projects p
           JOIN organization_members m ON m.org_id = p.org_id
           WHERE p.id = $1 AND m.user_id = $2""",
        str(project_id), str(user_id),
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project["role"] not in min_role:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return project


# ── API KEYS ──────────────────────────────────────────────────────
@router.post("/projects/{project_id}/api-keys", response_model=ApiKeyCreatedResponse, status_code=201)
async def create_api_key(project_id: uuid.UUID, body: ApiKeyCreate, db=Depends(get_db), user=Depends(get_current_user)):
    await _get_project_with_auth(project_id, user["id"], db, min_role=('owner', 'admin'))
    raw_key = "cai_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:10]
    row = await db.fetchrow(
        """INSERT INTO api_keys (project_id, name, key_hash, key_prefix, created_by, expires_at)
           VALUES ($1, $2, $3, $4, $5, $6)
           RETURNING id, project_id, name, key_prefix, is_active, last_used_at, expires_at, created_at""",
        str(project_id), body.name, key_hash, key_prefix, str(user["id"]), body.expires_at,
    )
    result = dict(row)
    result["raw_key"] = raw_key
    return result


@router.get("/projects/{project_id}/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys(project_id: uuid.UUID, db=Depends(get_db), user=Depends(get_current_user)):
    await _get_project_with_auth(project_id, user["id"], db)
    rows = await db.fetch(
        "SELECT id, project_id, name, key_prefix, is_active, last_used_at, expires_at, created_at FROM api_keys WHERE project_id = $1 ORDER BY created_at DESC",
        str(project_id),
    )
    return [dict(r) for r in rows]


@router.delete("/projects/{project_id}/api-keys/{key_id}", status_code=204)
async def delete_api_key(project_id: uuid.UUID, key_id: uuid.UUID, db=Depends(get_db), user=Depends(get_current_user)):
    await _get_project_with_auth(project_id, user["id"], db, min_role=('owner', 'admin'))
    await db.execute("DELETE FROM api_keys WHERE id = $1 AND project_id = $2", str(key_id), str(project_id))
