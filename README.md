<div align="center">

# 🚀 Distributed Job Scheduler

### Production-Grade Async Task Execution Platform

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-5-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

**Codity.AI Intern Assignment — Backend Engineering Track**

*Submitted by: Pragyansh Suman | RA2311026010734*

[Live Demo](#-running-the-project) · [API Docs](http://localhost:8000/docs) · [Architecture](#-architecture) · [Features](#-features)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Architecture](#-architecture)
- [Database Schema](#-database-schema)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [API Reference](#-api-reference)
- [Dashboard Pages](#-dashboard-pages)
- [Worker Engine](#-worker-engine)
- [Design Decisions](#-design-decisions)
- [Running Tests](#-running-tests)

---

## 🎯 Overview

A **production-grade distributed job scheduling platform** capable of reliably executing asynchronous background jobs across multiple concurrent workers. Built for the Codity.AI intern assignment, this platform mirrors real-world systems like Celery, BullMQ, and AWS SQS.

The system evaluates:
- ✅ **Backend Engineering** — FastAPI + asyncio + asyncpg with full async I/O
- ✅ **Database Design** — 20-table PostgreSQL schema with partitioning, partial indexes, and triggers
- ✅ **Concurrency** — Atomic job claiming via `SELECT FOR UPDATE SKIP LOCKED`
- ✅ **Reliability** — Retry strategies, DLQ, stale worker recovery, graceful shutdown
- ✅ **API Design** — 25+ REST endpoints with full Pydantic validation + Swagger docs
- ✅ **Full-Stack** — React dashboard with live WebSocket updates

---

## ✨ Features

### Core Requirements (All Implemented)

| Feature | Description | Status |
|---------|-------------|--------|
| **Authentication** | JWT register/login/refresh with bcrypt password hashing | ✅ |
| **Multi-tenancy** | Organization → Project → Queue → Job hierarchy | ✅ |
| **RBAC** | Owner / Admin / Member / Viewer roles per organization | ✅ |
| **Queue Configuration** | Priority, concurrency limits, rate limiting, retry policy | ✅ |
| **Queue Control** | Pause / Resume queues with live effect | ✅ |
| **Queue Statistics** | Per-queue metrics snapshots with history | ✅ |
| **Immediate Jobs** | Submit and execute right away | ✅ |
| **Delayed Jobs** | Execute after a specified delay (seconds) | ✅ |
| **Scheduled Jobs** | Execute at a specific UTC datetime | ✅ |
| **Recurring Jobs** | Cron expressions (e.g., `0 9 * * 1-5`) | ✅ |
| **Batch Jobs** | Submit multiple jobs atomically under one batch | ✅ |
| **Worker Polling** | Atomic claiming via `SKIP LOCKED`, no duplicate execution | ✅ |
| **Concurrent Execution** | Workers run multiple jobs concurrently via asyncio | ✅ |
| **Heartbeats** | Workers send heartbeats every 5s, tracked in DB | ✅ |
| **Graceful Shutdown** | SIGTERM handler drains in-flight jobs before exit | ✅ |
| **Job Lifecycle** | Full FSM: pending → claimed → running → completed/failed | ✅ |
| **Retry Strategies** | Fixed, Linear, Exponential backoff with optional jitter | ✅ |
| **Dead Letter Queue** | Failed jobs moved to DLQ with full error context | ✅ |
| **Execution Logs** | Per-attempt log lines with level (debug/info/warn/error) | ✅ |
| **API Keys** | Project-scoped keys for programmatic job submission | ✅ |
| **Idempotency Keys** | Prevent duplicate job submission via unique DB constraint | ✅ |
| **Workflow Dependencies** | DAG chains — Job B waits for Job A to complete | ✅ |
| **WebSocket Events** | Real-time dashboard updates on all job state changes | ✅ |
| **Metrics API** | System overview, per-queue stats, throughput history | ✅ |
| **Rate Limiting** | Token bucket per queue (DB-backed) | ✅ |
| **Stale Worker Recovery** | Auto-detect and re-queue jobs from crashed workers | ✅ |

---

## 🛠 Tech Stack

### Backend
| Layer | Technology | Why |
|-------|------------|-----|
| HTTP Framework | **FastAPI** | Async-native, auto Swagger/OpenAPI docs, Pydantic v2 |
| Database Driver | **asyncpg** | 3-5× faster than psycopg2, binary protocol, native async |
| Database | **PostgreSQL 17** | SKIP LOCKED, partitioning, advisory locks |
| Auth | **python-jose (JWT)** | Stateless access + refresh token pair |
| Password Hashing | **passlib + bcrypt** | Adaptive cost factor, industry standard |
| Settings | **pydantic-settings** | Type-safe env var loading |
| Cron Parsing | **croniter** | Parse & compute cron next-run-at |
| Concurrency | **asyncio** | Cooperative multitasking without GIL contention |
| Tests | **pytest + pytest-asyncio** | Async test support |

### Frontend
| Layer | Technology | Why |
|-------|------------|-----|
| Framework | **React 18** | Component-based, hook-driven state |
| Build Tool | **Vite 5** | Sub-second HMR, fast production builds |
| Charts | **Recharts** | Composable, responsive SVG charts |
| Icons | **lucide-react** | Clean, tree-shakeable icon set |
| Routing | **react-router-dom v6** | Declarative nested routes |
| HTTP Client | **Fetch API (native)** | No extra deps |
| Styling | **Vanilla CSS** | Full control, zero runtime cost |

---

## 🏗 Architecture

```
╔══════════════════════════════════════════════════════════════════════╗
║                        SYSTEM ARCHITECTURE                          ║
╚══════════════════════════════════════════════════════════════════════╝

  ┌─────────────────────────────────────────────┐
  │          React Dashboard  (Port 5173)        │
  │  Overview │ Jobs │ Queues │ Workers │ DLQ    │
  │  Metrics  │ Settings │ Login/Register        │
  └─────────────────────┬───────────────────────┘
                        │  REST + WebSocket
                        ▼
  ┌─────────────────────────────────────────────┐
  │       FastAPI API Server  (Port 8000)        │
  │                                              │
  │  Routers:                                    │
  │  ├── /auth      — JWT auth, user profile     │
  │  ├── /orgs      — Org CRUD + members         │
  │  ├── /queues    — Queue control + stats      │
  │  ├── /jobs      — All job types + DLQ        │
  │  ├── /workers   — Registry + heartbeat       │
  │  ├── /metrics   — System stats + history     │
  │  └── /ws        — WebSocket broadcast        │
  │                                              │
  │  Middleware: JWT, CORS, RBAC                 │
  └─────────────────────┬───────────────────────┘
                        │ asyncpg (binary protocol)
                        ▼
  ┌─────────────────────────────────────────────┐
  │           PostgreSQL 17                      │
  │                                              │
  │  20 tables  │  22 indexes  │  6 triggers    │
  │  Year-partitioned job_executions             │
  │  SELECT FOR UPDATE SKIP LOCKED               │
  │  Partial indexes for fast polling            │
  └─────────────────────┬───────────────────────┘
                        │ polls every 1s
                        ▼
  ┌─────────────────────────────────────────────┐
  │       Worker Engine  (n instances)           │
  │                                              │
  │  ├── Scheduler Loop  — promote delayed/cron  │
  │  │                     recover stale workers │
  │  ├── Poller Loop     — atomic SKIP LOCKED    │
  │  ├── Executor        — run jobs, timeout     │
  │  ├── Heartbeat       — every 5s to DB        │
  │  └── Retry Engine    — backoff + DLQ logic   │
  └─────────────────────────────────────────────┘
```

### Job State Machine

```
                   ┌──────────┐
         ┌────────►│ PENDING  │◄──── retry
         │         └────┬─────┘
    cancelled            │  scheduler promotes
         │         ┌────▼─────┐
         │         │SCHEDULED │  (delayed / cron)
         │         └────┬─────┘
         │              │  worker claims
         │         ┌────▼─────┐
         │         │ CLAIMED  │
         │         └────┬─────┘
         │              │  execution starts
         │         ┌────▼─────┐
         │         │ RUNNING  │
         │         └────┬─────┘
         │        ┌─────┴──────┐
         │   ┌────▼────┐  ┌────▼────┐
         │   │COMPLETED│  │ FAILED  │──► (max attempts)──► DEAD_LETTER
         │   └─────────┘  └────┬────┘
         │                     │  retry delay
         └─────────────────────┘
```

---

## 🗄 Database Schema

```sql
-- Core hierarchy
users ──► organizations ──► organization_members (RBAC)
                       └──► projects ──► api_keys
                                    └──► queues ──► retry_policies
                                               └──► jobs ──► job_executions (partitioned)
                                                         ├──► job_logs      (partitioned)
                                                         ├──► job_dependencies (DAG)
                                                         └──► dead_letter_queue

-- Supporting tables
workers ──► worker_heartbeats
queues  ──► queue_stats_snapshots
queues  ──► rate_limit_buckets
queues  ──► scheduled_jobs (cron definitions)

-- Infrastructure
distributed_locks
events (audit log)
```

### Critical Index — Powers All Worker Polling

```sql
CREATE INDEX idx_jobs_poll ON jobs(queue_id, status, priority DESC, scheduled_at ASC NULLS FIRST)
    WHERE deleted_at IS NULL;
```

This single composite partial index makes the polling query O(log n) regardless of table size.

### Idempotency Key Constraint

```sql
CREATE UNIQUE INDEX idx_jobs_idempotency ON jobs(queue_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL AND deleted_at IS NULL;
```

---

## 📁 Project Structure

```
CodityAI/
├── README.md
├── .gitignore
├── RA2311026010734.html          ← Assignment report (print to PDF)
│
├── backend/
│   ├── requirements.txt
│   ├── .env                      ← (gitignored — copy from .env.example)
│   ├── .env.example
│   ├── app/
│   │   ├── main.py               ← FastAPI app, lifespan, routers, CORS
│   │   ├── config.py             ← pydantic-settings env config
│   │   ├── database.py           ← asyncpg pool + get_db dependency
│   │   ├── dependencies.py       ← JWT auth, RBAC factory, bcrypt
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── routers/
│   │   │       ├── auth.py           ← register, login, refresh, /me
│   │   │       ├── organizations.py  ← org CRUD + members + projects + keys
│   │   │       ├── queues.py         ← queue CRUD + pause/resume + stats
│   │   │       ├── jobs.py           ← all job types + batch + DLQ + logs
│   │   │       ├── workers.py        ← register + heartbeat + list
│   │   │       └── metrics.py        ← system overview + throughput
│   │   ├── models/
│   │   │   ├── auth.py
│   │   │   ├── organization.py
│   │   │   ├── queue.py
│   │   │   ├── job.py
│   │   │   ├── worker.py
│   │   │   └── metrics.py
│   │   ├── websocket/
│   │   │   └── manager.py        ← ConnectionManager, broadcast
│   │   └── worker/
│   │       ├── main.py           ← orchestrates all loops, graceful shutdown
│   │       ├── poller.py         ← SELECT FOR UPDATE SKIP LOCKED
│   │       ├── executor.py       ← run job, timeout, write logs
│   │       ├── scheduler.py      ← promote delayed/cron + stale recovery
│   │       └── retry_engine.py   ← backoff strategies + DLQ placement
│   ├── migrations/
│   │   └── 001_initial.sql       ← full 20-table schema
│   └── tests/
│       ├── conftest.py
│       ├── test_auth.py          ← 8 auth endpoint tests
│       └── test_jobs.py          ← 8 job lifecycle tests
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js            ← proxy /api and /ws to :8000
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx               ← routing, auth guards, WS integration
│       ├── index.css             ← full design system (dark glassmorphism)
│       ├── pages/
│       │   ├── Login.jsx         ← register/login toggle
│       │   ├── Overview.jsx      ← stat cards + charts + queue health
│       │   ├── Queues.jsx        ← create/manage queues + submit jobs
│       │   ├── Jobs.jsx          ← explorer + detail drawer + logs
│       │   ├── Workers.jsx       ← monitor + utilization + shutdown
│       │   ├── DeadLetter.jsx    ← DLQ retry/discard manager
│       │   ├── Metrics.jsx       ← analytics + throughput charts
│       │   └── Settings.jsx      ← orgs + projects + API keys + policies
│       ├── components/
│       │   ├── Sidebar.jsx
│       │   ├── Badge.jsx
│       │   └── Toast.jsx
│       ├── hooks/
│       │   └── useWebSocket.js   ← auto-reconnect + ping/pong
│       ├── services/
│       │   └── api.js            ← 40+ endpoint client (no extra deps)
│       └── context/
│           └── AuthContext.jsx   ← JWT persistence + login/logout
│
└── docs/
    ├── er-diagram.md
    └── design-decisions.md
```

---

## 🚀 Getting Started

### Prerequisites

- Python **3.10+**
- Node.js **18+** and npm
- PostgreSQL **14+** (tested with 17)

### 1. Clone the Repository

```bash
git clone https://github.com/PragyanshSuman/CodityAI_Assignment.git
cd CodityAI_Assignment
```

### 2. Database Setup

```bash
# Create the database
psql -U postgres -c "CREATE DATABASE codityai;"

# Apply the full schema (20 tables, triggers, indexes, partitions)
psql -U postgres -d codityai -f backend/migrations/001_initial.sql
```

### 3. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate
# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env    # Windows
# cp .env.example .env    # Mac/Linux

# Edit .env with your database credentials
# DATABASE_URL="postgresql://postgres:YOUR_PASSWORD@localhost:5432/codityai"
```

### 4. Start the API Server

```bash
# Inside backend/ with venv activated
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **API Base URL:** `http://localhost:8000/api/v1`
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

### 5. Start the Worker Engine

Open a **new terminal** (venv activated):

```bash
cd backend
python -m app.worker.main
```

The worker will:
1. Register itself in the database
2. Begin sending heartbeats every 5 seconds
3. Poll for pending jobs every second
4. Process jobs concurrently up to `WORKER_MAX_CONCURRENCY`

### 6. Start the Frontend Dashboard

Open a **third terminal**:

```bash
cd frontend
npm install
npm run dev
```

- **Dashboard:** `http://localhost:5173`

---

## 📖 API Reference

Full interactive documentation available at `http://localhost:8000/docs` when the server is running.

### Authentication

```http
POST   /api/v1/auth/register        # Create account
POST   /api/v1/auth/login           # Get JWT tokens
POST   /api/v1/auth/refresh         # Rotate tokens
GET    /api/v1/auth/me              # Get current user
```

### Organizations & Projects

```http
POST   /api/v1/orgs                 # Create organization
GET    /api/v1/orgs                 # List your organizations
GET    /api/v1/orgs/{id}            # Get organization details
POST   /api/v1/orgs/{id}/members    # Invite member with role
DELETE /api/v1/orgs/{id}/members/{user_id}  # Remove member
POST   /api/v1/orgs/{id}/projects   # Create project
GET    /api/v1/orgs/{id}/projects   # List projects
POST   /api/v1/projects/{id}/api-keys  # Generate API key
```

### Queue Management

```http
POST   /api/v1/projects/{id}/queues  # Create queue
GET    /api/v1/projects/{id}/queues  # List queues
GET    /api/v1/queues/{id}           # Queue details
PUT    /api/v1/queues/{id}           # Update queue config
DELETE /api/v1/queues/{id}           # Delete queue
POST   /api/v1/queues/{id}/pause     # Pause (stops claiming)
POST   /api/v1/queues/{id}/resume    # Resume paused queue
GET    /api/v1/queues/{id}/stats     # Live metrics
GET    /api/v1/retry-policies        # List retry policies
```

### Job Submission

#### Immediate Job
```bash
curl -X POST http://localhost:8000/api/v1/queues/{queue_id}/jobs \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Send Welcome Email",
    "job_type": "immediate",
    "handler": "emails.send_welcome",
    "payload": {"user_id": "abc123", "email": "user@example.com"},
    "priority": 8,
    "max_attempts": 3
  }'
```

#### Delayed Job
```bash
curl -X POST http://localhost:8000/api/v1/queues/{queue_id}/jobs \
  -d '{
    "name": "Follow-up Email",
    "job_type": "delayed",
    "handler": "emails.send_followup",
    "payload": {"user_id": "abc123"},
    "delay_seconds": 3600
  }'
```

#### Scheduled Job (exact datetime)
```bash
curl -X POST http://localhost:8000/api/v1/queues/{queue_id}/jobs \
  -d '{
    "name": "Midnight Report",
    "job_type": "scheduled",
    "handler": "reports.generate",
    "scheduled_at": "2026-07-05T00:00:00Z"
  }'
```

#### Recurring Cron Job
```bash
curl -X POST http://localhost:8000/api/v1/queues/{queue_id}/jobs \
  -d '{
    "name": "Daily Digest",
    "job_type": "recurring",
    "handler": "emails.daily_digest",
    "cron_expression": "0 9 * * 1-5",
    "max_attempts": 3,
    "priority": 7
  }'
```

#### Batch Job
```bash
curl -X POST http://localhost:8000/api/v1/queues/{queue_id}/jobs/batch \
  -d '{
    "batch_name": "Image Processing Pipeline",
    "jobs": [
      {"name": "resize-a", "handler": "img.resize", "payload": {"src": "a.png"}},
      {"name": "resize-b", "handler": "img.resize", "payload": {"src": "b.png"}}
    ]
  }'
```

#### Job with Idempotency Key
```bash
curl -X POST http://localhost:8000/api/v1/queues/{queue_id}/jobs \
  -d '{
    "name": "Charge Payment",
    "handler": "payments.charge",
    "payload": {"order_id": "ORD-999", "amount": 1999},
    "idempotency_key": "payment-ORD-999-attempt-1"
  }'
```

### Job Control

```http
GET    /api/v1/queues/{id}/jobs        # List jobs (paginated + filtered)
GET    /api/v1/jobs/{id}               # Job detail + executions + logs
POST   /api/v1/jobs/{id}/retry         # Manual retry
DELETE /api/v1/jobs/{id}              # Cancel job
GET    /api/v1/queues/{id}/dlq         # Dead letter queue
POST   /api/v1/dlq/{id}/retry         # Re-enqueue from DLQ
DELETE /api/v1/dlq/{id}               # Discard permanently
```

### Workers & Metrics

```http
POST   /api/v1/workers/register        # Register worker
POST   /api/v1/workers/{id}/heartbeat  # Send heartbeat
GET    /api/v1/workers                 # List active workers
GET    /api/v1/metrics/overview        # System stats
WS     /ws                             # Real-time event stream
```

---

## 🖥 Dashboard Pages

| Page | Route | Description |
|------|-------|-------------|
| **Login** | `/login` | Register or sign in. Persists JWT to localStorage. |
| **Overview** | `/` | Stat cards (total jobs, active workers, success rate). Pie chart by status. Queue health table. All live via WebSocket. |
| **Queue Manager** | `/queues` | Create queues with priority/concurrency/rate-limit settings. Pause/resume. Submit jobs of any type from UI. |
| **Job Explorer** | `/jobs` | Paginated, filterable job list. Click to open detail drawer — execution history, error stack traces, full log output. |
| **Worker Monitor** | `/workers` | All registered workers with heartbeat age, CPU/memory bars, concurrency utilization. Graceful shutdown button. |
| **Dead Letter Queue** | `/dlq` | Permanently failed jobs. Retry (re-enqueue) or Discard actions. Shows total attempts and final error. |
| **Metrics** | `/metrics` | Throughput area chart (last 60 min). Bar chart of job distribution by queue. Success rate table. |
| **Settings** | `/settings` | Manage orgs, invite members, create projects, generate/revoke API keys, configure retry policies. |

### Real-Time WebSocket Events

The dashboard maintains a persistent WebSocket connection that receives push events:

| Event | Trigger |
|-------|---------|
| `job.created` | New job submitted |
| `job.claimed` | Worker picked up a job |
| `job.completed` | Job finished successfully |
| `job.failed` | Job execution failed |
| `job.dead_letter` | Job moved to DLQ |
| `job.recovered` | Stale worker's job re-queued |
| `worker.registered` | New worker came online |
| `worker.offline` | Worker heartbeat timed out |
| `queue.paused` | Queue paused |
| `queue.resumed` | Queue resumed |

---

## ⚙️ Worker Engine

The worker is a standalone Python process (`python -m app.worker.main`) that runs four concurrent asyncio loops:

### 1. Heartbeat Loop (every 5s)
Sends CPU, memory, and current job count to `worker_heartbeats` table. Updates `workers.last_heartbeat_at`.

### 2. Scheduler Loop (every 5s)
- **Promotes delayed jobs:** Sets jobs whose `scheduled_at <= NOW()` from `scheduled` → `pending`
- **Promotes cron jobs:** Computes `next_run_at` via `croniter` and creates new job instances
- **Stale worker recovery:** Finds workers with `last_heartbeat_at < NOW() - 30s`, marks them `offline`, re-queues their jobs

### 3. Poller Loop (every 1s)
Atomically claims up to `(max_concurrency - current_jobs)` jobs:

```sql
-- Runs inside a transaction
UPDATE jobs SET status = 'claimed', claimed_by = $1, claimed_at = NOW()
WHERE id IN (
    SELECT id FROM jobs
    WHERE queue_id = $2
      AND status = 'pending'
      AND (scheduled_at IS NULL OR scheduled_at <= NOW())
      AND deleted_at IS NULL
    ORDER BY priority DESC, created_at ASC
    LIMIT $3
    FOR UPDATE SKIP LOCKED
)
RETURNING *
```

### 4. Executor
For each claimed job, spawns an asyncio task that:
1. Creates a `job_executions` record
2. Runs the handler function with a timeout (`asyncio.wait_for`)
3. Writes success/failure to the execution record and job_logs
4. Calls the retry engine on failure

### Retry Engine
```
attempt_count < max_attempts?
  YES → compute_delay(strategy, attempt, initial, multiplier, jitter)
        → reschedule job to pending with next_run_at
  NO  → move to dead_letter_queue table
        → mark job status = 'dead_letter'
```

### Graceful Shutdown
```
SIGTERM received
  → Stop polling for new jobs
  → Wait for current jobs to complete (up to 30s)
  → Send final heartbeat with status = 'offline'
  → Close DB connection pool
  → Exit
```

---

## 🔬 Design Decisions

### Why `SELECT FOR UPDATE SKIP LOCKED`?

Multiple workers polling the same queue would naively race to claim the same jobs, resulting in duplicate execution. PostgreSQL's `FOR UPDATE SKIP LOCKED` acquires row-level locks atomically. Rows locked by another transaction are skipped instantly — no waiting, no coordination, no Redis required.

This is the same technique used by Sidekiq Pro (Ruby), pg-boss (Node.js), and River (Go).

### Why asyncpg over SQLAlchemy?

Raw asyncpg with manual SQL gives:
- Direct control over `FOR UPDATE SKIP LOCKED` syntax
- 3-5× throughput over ORM-generated queries
- Full control over partial index hints
- Binary wire protocol vs. text (faster for large JSONB payloads)

### Why PostgreSQL over Redis for the queue?

| | PostgreSQL | Redis |
|--|----------|-------|
| Durability | Fsync'd WAL — zero data loss | Depends on AOF/RDB config |
| Query power | Full SQL, joins, aggregates | Limited |
| Consistency | ACID transactions | Eventual (cluster mode) |
| Observability | Query `SELECT` to inspect | Requires special commands |
| Infra cost | 1 dependency | 2 dependencies |

For a platform that needs audit logs, per-job execution records, and complex queries (stats aggregations), PostgreSQL is the right choice.

### Partitioned Tables

`job_executions` and `job_logs` are partitioned by year. Benefits:
- **Instant data purge:** `DROP TABLE job_executions_2024` — no `DELETE` scans
- **Query locality:** Active queries only scan this year's partition
- **pg_dump isolation:** Back up 2026 data independently of 2025

---

## 🧪 Running Tests

```bash
cd backend
.\venv\Scripts\activate

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_auth.py -v
pytest tests/test_jobs.py -v

# Run with coverage report
pytest tests/ --cov=app --cov-report=term-missing
```

**Test coverage includes:**
- User registration and duplicate email detection
- Login with valid/invalid credentials
- JWT token refresh
- Get current user (`/me`)
- Submit all 5 job types (immediate, delayed, scheduled, recurring, batch)
- Idempotency key deduplication
- Job cancellation
- Paginated job listing

---

## 📄 Environment Variables

```bash
# backend/.env
DATABASE_URL="postgresql://postgres:password@localhost:5432/codityai"
TEST_DATABASE_URL="postgresql://postgres:password@localhost:5432/codityai_test"
SECRET_KEY="your-256-bit-secret-key-here"
LOG_LEVEL="INFO"

# Worker settings
WORKER_MAX_CONCURRENCY=10
WORKER_POLL_INTERVAL=1.0       # seconds between polls
WORKER_HEARTBEAT_INTERVAL=5.0  # seconds between heartbeats
```

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with ❤️ for Codity.AI**

*Pragyansh Suman | RA2311026010734*

[⬆ Back to Top](#-distributed-job-scheduler)

</div>
