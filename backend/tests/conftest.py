import pytest
import asyncio
import asyncpg
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import get_pool
import os

# Test database URL — use a separate test DB
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/codityai_test"
)

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
def auth_headers(test_client):
    """Register and login a test user, return auth headers."""
    import asyncio
    async def _get_headers():
        # Register
        await test_client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "password": "testpass123",
            "full_name": "Test User"
        })
        # Login
        resp = await test_client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "testpass123"
        })
        token = resp.json().get("access_token", "")
        return {"Authorization": f"Bearer {token}"}
    return asyncio.get_event_loop().run_until_complete(_get_headers())
