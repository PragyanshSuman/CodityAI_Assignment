"""
FastAPI Application Entry Point
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import create_pool, close_pool, get_pool
from app.websocket.manager import manager

from app.api.routers import auth, organizations, queues, jobs, workers, metrics

logger = logging.getLogger(__name__)

# ── Lifespan ─────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logger.info("Starting Distributed Job Scheduler API")
    await create_pool()
    logger.info("Database pool created")
    yield
    await close_pool()
    logger.info("Shutdown complete")


# ── App ──────────────────────────────────────────────────────────
app = FastAPI(
    title="Distributed Job Scheduler",
    description="""
# Distributed Job Scheduler API

Production-grade distributed job scheduling platform with:
- **Authentication** — JWT-based auth with refresh tokens
- **Organizations & Projects** — Multi-tenant with RBAC
- **Queues** — Priority, concurrency limits, rate limiting, pause/resume
- **Jobs** — Immediate, delayed, scheduled, recurring (cron), and batch jobs
- **Workers** — Auto-registered with heartbeat monitoring
- **Dead Letter Queue** — Permanent failure handling with AI summaries
- **Real-time** — WebSocket updates for live dashboard

## Job Lifecycle
`pending → scheduled → claimed → running → completed | failed → dead_letter`

## Retry Strategies
- Fixed delay
- Linear backoff
- Exponential backoff (with optional jitter)
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global Error Handler ─────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )

# ── Routers ──────────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(organizations.router, prefix=API_PREFIX)
app.include_router(queues.router, prefix=API_PREFIX)
app.include_router(jobs.router, prefix=API_PREFIX)
app.include_router(workers.router, prefix=API_PREFIX)
app.include_router(metrics.router, prefix=API_PREFIX)

# ── WebSocket ────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back ping/pong for keep-alive
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ── Health & Info ────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health():
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"
    return {"status": "ok", "db": db_status, "version": "1.0.0"}


@app.get("/", tags=["System"])
async def root():
    return {
        "name": "Distributed Job Scheduler",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
