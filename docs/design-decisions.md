# Design Decisions

## 1. Atomic Job Claiming with `SELECT FOR UPDATE SKIP LOCKED`

**Problem**: Multiple workers polling the same queue will try to claim the same job simultaneously, leading to duplicate execution.

**Solution**: PostgreSQL's `SELECT FOR UPDATE SKIP LOCKED` acquires a row-level lock atomically. Any row already locked by another transaction is skipped automatically — no explicit distributed lock needed.

```sql
SELECT id, handler, payload FROM jobs
WHERE queue_id = $1 AND status = 'pending'
ORDER BY priority DESC, created_at ASC
LIMIT $2
FOR UPDATE SKIP LOCKED
```

**Trade-off**: Slightly higher DB load vs. application-level locking. The benefit is correctness guaranteed at the database layer — the application can crash mid-claim and the transaction rolls back automatically.

---

## 2. FastAPI + asyncpg over Django/SQLAlchemy

**Choice**: FastAPI with raw asyncpg queries.

**Rationale**:
- asyncpg is 3-5× faster than psycopg2 (C-optimized, binary protocol)
- Raw SQL allows fine-grained control over `FOR UPDATE SKIP LOCKED` and partial indexes
- FastAPI's async architecture matches the polling/heartbeat workload
- Auto-generated Swagger UI satisfies the API documentation requirement

**Trade-off**: More boilerplate than ORM — acceptable given the performance requirements.

---

## 3. Token Bucket Rate Limiting (DB-backed)

**Choice**: Store token buckets in PostgreSQL (`rate_limit_buckets` table).

**Rationale**: For a single-region deployment, DB-backed rate limiting is simpler than Redis and avoids an extra dependency. The token bucket row is updated within the same `SELECT FOR UPDATE` transaction as job claiming, ensuring atomic check-and-consume.

**Trade-off**: Does not scale across multi-region deployments. For global scale, Redis or a distributed rate limiter (e.g., Cloudflare's Durable Objects) would be used.

---

## 4. Job Status FSM

```
pending → scheduled → claimed → running → completed
                                        ↘ failed → (retry) → pending
                                                  → dead_letter
                      ↓
                   cancelled
```

**Design**: Explicit state machine enforced at the application layer. Status transitions are validated before every update. This makes illegal transitions (e.g., `completed → running`) impossible.

---

## 5. Partitioned Tables for Observability Data

`job_executions` and `job_logs` are range-partitioned by year. This means:
- Dropping old data is O(1) (`DROP TABLE job_executions_2024`)
- Queries against recent data only scan current partition
- pg_dump of historical data is independent of current operational data

---

## 6. Worker Heartbeat + Stale Recovery

Workers send heartbeats every 5s. The scheduler loop (running on each worker) checks for workers whose `last_heartbeat_at < NOW() - 30s` and:
1. Marks them as `offline`
2. Re-queues their `claimed`/`running` jobs back to `pending` with decremented `attempt_count`

This self-healing mechanism requires no external coordinator.

---

## 7. Recurring Job Pattern

Recurring jobs don't create a single DB record that runs forever. Instead:
- Each execution creates a new `jobs` row as the "next instance"
- The previous instance is marked `completed` with `next_run_at` set

This provides a full audit trail of every cron execution while keeping the jobs table from growing unboundedly per schedule.

---

## 8. Multi-tenancy Model

```
Organization → Project → Queue → Job
```

Every resource is scoped to a project. RBAC roles (owner/admin/member/viewer) are attached at the organization level and cascade to all contained resources. API keys are project-scoped, allowing service accounts with minimal blast radius.

---

## 9. WebSocket Architecture

A single shared `ConnectionManager` broadcasts events to all connected dashboard clients. Events are emitted from:
- Job routers (on create, cancel, retry)
- Worker engine (on claim, complete, fail, recover)

This provides real-time updates without polling. The WebSocket ping/pong keeps connections alive through load balancers.

---

## 10. Idempotency Keys

Jobs submitted with `idempotency_key` are deduplicated via a partial unique index. Clients can safely retry submission on network failures — the same job object is returned for duplicate submissions. Keys are scoped per queue to prevent cross-queue collisions.
