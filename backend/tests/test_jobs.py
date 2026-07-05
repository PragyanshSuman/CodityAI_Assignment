import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


async def _get_auth_token(client: AsyncClient, email="jobs_test@example.com") -> str:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "password123"})
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    return resp.json()["access_token"]


async def _setup_queue(client: AsyncClient, token: str) -> tuple:
    """Create org → project → queue, return (org_id, project_id, queue_id)."""
    import uuid
    suffix = uuid.uuid4().hex[:6]
    headers = {"Authorization": f"Bearer {token}"}

    org = (await client.post("/api/v1/orgs", json={"name": "Test Org", "slug": f"test-org-{suffix}"}, headers=headers)).json()
    project = (await client.post(f"/api/v1/orgs/{org['id']}/projects", json={"name": "Test Project", "slug": f"test-proj-{suffix}"}, headers=headers)).json()
    queue = (await client.post(f"/api/v1/projects/{project['id']}/queues", json={
        "name": "Test Queue", "slug": f"test-q-{suffix}", "concurrency_limit": 5
    }, headers=headers)).json()
    return org["id"], project["id"], queue["id"]


@pytest.mark.asyncio
async def test_create_immediate_job():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_auth_token(client, "imm@example.com")
        _, _, queue_id = await _setup_queue(client, token)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post(f"/api/v1/queues/{queue_id}/jobs", json={
            "name": "Test Job",
            "job_type": "immediate",
            "handler": "default",
            "payload": {"key": "value"},
            "priority": 7,
        }, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["job_type"] == "immediate"
        assert data["priority"] == 7


@pytest.mark.asyncio
async def test_create_delayed_job():
    from datetime import datetime, timezone, timedelta
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_auth_token(client, "delayed@example.com")
        _, _, queue_id = await _setup_queue(client, token)
        headers = {"Authorization": f"Bearer {token}"}

        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        resp = await client.post(f"/api/v1/queues/{queue_id}/jobs", json={
            "job_type": "delayed",
            "handler": "default",
            "payload": {},
            "scheduled_at": future,
        }, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["status"] == "scheduled"


@pytest.mark.asyncio
async def test_create_recurring_job():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_auth_token(client, "recur@example.com")
        _, _, queue_id = await _setup_queue(client, token)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post(f"/api/v1/queues/{queue_id}/jobs", json={
            "job_type": "recurring",
            "handler": "default",
            "payload": {},
            "cron_expression": "*/5 * * * *",
        }, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "scheduled"
        assert data["cron_expression"] == "*/5 * * * *"


@pytest.mark.asyncio
async def test_invalid_cron_expression():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_auth_token(client, "badcron@example.com")
        _, _, queue_id = await _setup_queue(client, token)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post(f"/api/v1/queues/{queue_id}/jobs", json={
            "job_type": "recurring",
            "handler": "default",
            "payload": {},
            "cron_expression": "not-a-cron",
        }, headers=headers)
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_idempotency_key_deduplication():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_auth_token(client, "idem@example.com")
        _, _, queue_id = await _setup_queue(client, token)
        headers = {"Authorization": f"Bearer {token}"}

        job_data = {
            "job_type": "immediate",
            "handler": "default",
            "payload": {"order": 1},
            "idempotency_key": "order-12345",
        }
        resp1 = await client.post(f"/api/v1/queues/{queue_id}/jobs", json=job_data, headers=headers)
        resp2 = await client.post(f"/api/v1/queues/{queue_id}/jobs", json=job_data, headers=headers)

        assert resp1.status_code == 201
        assert resp2.status_code == 201
        # Same job returned for duplicate key
        assert resp1.json()["id"] == resp2.json()["id"]


@pytest.mark.asyncio
async def test_batch_job_creation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_auth_token(client, "batch@example.com")
        _, _, queue_id = await _setup_queue(client, token)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post(f"/api/v1/queues/{queue_id}/jobs/batch", json={
            "name": "Test Batch",
            "jobs": [
                {"handler": "default", "payload": {"i": i}} for i in range(5)
            ]
        }, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["total"] == 5
        assert len(data["job_ids"]) == 5


@pytest.mark.asyncio
async def test_list_jobs_with_pagination():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_auth_token(client, "listjobs@example.com")
        _, _, queue_id = await _setup_queue(client, token)
        headers = {"Authorization": f"Bearer {token}"}

        for i in range(5):
            await client.post(f"/api/v1/queues/{queue_id}/jobs", json={
                "handler": "default", "payload": {"i": i}
            }, headers=headers)

        resp = await client.get(f"/api/v1/queues/{queue_id}/jobs?page=1&page_size=3", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["page_size"] == 3
        assert len(data["items"]) <= 3


@pytest.mark.asyncio
async def test_cancel_job():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_auth_token(client, "cancel@example.com")
        _, _, queue_id = await _setup_queue(client, token)
        headers = {"Authorization": f"Bearer {token}"}

        job = (await client.post(f"/api/v1/queues/{queue_id}/jobs", json={
            "handler": "default", "payload": {}
        }, headers=headers)).json()

        resp = await client.delete(f"/api/v1/jobs/{job['id']}", headers=headers)
        assert resp.status_code == 204
