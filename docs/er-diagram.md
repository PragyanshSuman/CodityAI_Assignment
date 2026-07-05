# Entity-Relationship Diagram

## Tables Overview

```
users (id, email, password_hash, full_name, is_active, is_superuser)
  │
  ├─► organizations (id, name, slug, created_by→users)
  │     │
  │     ├─► organization_members (org_id→orgs, user_id→users, role)  [RBAC]
  │     │
  │     └─► projects (id, org_id→orgs, name, slug, created_by→users)
  │           │
  │           ├─► api_keys (project_id→projects, key_hash, key_prefix)
  │           │
  │           └─► queues (id, project_id→projects, name, slug, priority,
  │                 │     concurrency_limit, rate_limit_per_minute, retry_policy_id→retry_policies,
  │                 │     is_paused, is_active)
  │                 │
  │                 ├─► jobs (id, queue_id→queues, batch_id→batch_jobs,
  │                 │   │    name, job_type, handler, payload, status, priority,
  │                 │   │    max_attempts, attempt_count, timeout_seconds,
  │                 │   │    scheduled_at, cron_expression, next_run_at,
  │                 │   │    claimed_by→workers, idempotency_key, tags, metadata)
  │                 │   │
  │                 │   ├─► job_dependencies (job_id→jobs, depends_on_job_id→jobs)
  │                 │   │
  │                 │   ├─► job_executions (job_id→jobs, worker_id→workers,
  │                 │   │   attempt_number, status, duration_ms, error_*)
  │                 │   │     └─► job_logs (execution_id→job_executions, level, message)
  │                 │   │
  │                 │   └─► dead_letter_queue (job_id→jobs, queue_id→queues,
  │                 │         final_error, total_attempts, ai_failure_summary)
  │                 │
  │                 ├─► batch_jobs (queue_id→queues, total_jobs, completed_jobs)
  │                 │
  │                 ├─► queue_stats_snapshots (queue_id→queues, counts, metrics)
  │                 │
  │                 └─► rate_limit_buckets (queue_id→queues, tokens, refill_rate)
  │
retry_policies (id, name, strategy, max_attempts, initial_delay_seconds,
                max_delay_seconds, multiplier, jitter)

workers (id, name, hostname, pid, status, capabilities, max_concurrency,
         current_jobs, last_heartbeat_at)
  └─► worker_heartbeats (worker_id→workers, status, memory_mb, cpu_percent)

events (entity_type, entity_id, event_type, actor_id, data)  [audit log]
distributed_locks (lock_key, owner, expires_at)
scheduled_jobs (queue_id→queues, cron_expression, next_run_at)
```

## Key Design Decisions

### Primary Keys
All tables use UUID primary keys (`gen_random_uuid()`) for:
- Distributed-safe ID generation (no coordination needed)
- No information leakage about record counts
- Easy cross-service correlation

### Partitioning
`job_executions` and `job_logs` are range-partitioned by `created_at` by year.
This ensures `DELETE` of old data is instant (drop partition) and queries
against recent data hit only one partition.

### Critical Index
```sql
CREATE INDEX idx_jobs_poll ON jobs(queue_id, status, priority DESC, scheduled_at ASC NULLS FIRST)
WHERE deleted_at IS NULL;
```
This single composite index powers the worker's polling query with O(log n) lookups.

### Idempotency
```sql
CREATE UNIQUE INDEX idx_jobs_idempotency ON jobs(queue_id, idempotency_key)
WHERE idempotency_key IS NOT NULL AND deleted_at IS NULL;
```
Prevents duplicate job creation for clients that retry submissions.

### Soft Deletes
`jobs.deleted_at` allows cancelled jobs to be preserved for audit trails while
being excluded from all active queries via `WHERE deleted_at IS NULL` predicates.

### Cascading
- Deleting org → cascades to members, projects
- Deleting project → cascades to queues
- Deleting queue → cascades to jobs (via FK with ON DELETE CASCADE)
- Workers going offline → jobs SET NULL on `claimed_by` (recovered by scheduler)
