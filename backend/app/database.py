import asyncpg
from app.config import settings
from typing import Optional

pool: Optional[asyncpg.Pool] = None


async def create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(
        dsn=settings.DATABASE_URL,
        min_size=5,
        max_size=20,
        command_timeout=60,
    )


async def get_pool() -> asyncpg.Pool:
    global pool
    if pool is None:
        pool = await create_pool()
    return pool


async def close_pool():
    global pool
    if pool:
        await pool.close()
        pool = None


async def get_db():
    """FastAPI dependency — yields a connection from the pool."""
    p = await get_pool()
    async with p.acquire() as conn:
        yield conn
