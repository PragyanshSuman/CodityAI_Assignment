import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_register_success():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/register", json={
            "email": "newuser@example.com",
            "password": "password123",
            "full_name": "New User"
        })
        assert resp.status_code in (201, 409)  # 409 if already exists from previous run


@pytest.mark.asyncio
async def test_register_duplicate_email():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        data = {"email": "dup@example.com", "password": "password123"}
        await client.post("/api/v1/auth/register", json=data)
        resp = await client.post("/api/v1/auth/register", json=data)
        assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_success():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/register", json={
            "email": "login@example.com", "password": "mypassword"
        })
        resp = await client.post("/api/v1/auth/login", json={
            "email": "login@example.com", "password": "mypassword"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/login", json={
            "email": "login@example.com", "password": "wrongpassword"
        })
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/register", json={
            "email": "me@example.com", "password": "password123", "full_name": "Me User"
        })
        login = await client.post("/api/v1/auth/login", json={
            "email": "me@example.com", "password": "password123"
        })
        token = login.json()["access_token"]
        resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_me_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/auth/register", json={
            "email": "refresh@example.com", "password": "password123"
        })
        login = await client.post("/api/v1/auth/login", json={
            "email": "refresh@example.com", "password": "password123"
        })
        refresh_token = login.json()["refresh_token"]
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
