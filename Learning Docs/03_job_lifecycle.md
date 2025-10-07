# 03 Job Lifecycle and Data Flow

Last Updated: 2025-10-07 (commit a6e34c0)

## High-Level Flow
`
Client -> Gateway (/jobs) -> Postgres (job record) -> Celery enqueue ->
Worker (standard/heavy/gpu/symbolic) -> SafeEvaluator or SymbolicEngine ->
Result persisted -> Redis/WebSocket notification -> Client polling/WebSocket
`

## Submission Path
1. **Inbound request** (POST /jobs)
   - Request validated by JobSubmissionRequest (mode, priority, symbolic payload).
   - API key authentication (security.require_api_key) loads hashed key, checks expiry.
   - Policy engine (policy.evaluate_submission) loads tenant policy snapshot from
     Redis or Postgres, enforces queue allowlist, runtime limits, banned patterns,
     quotas.
2. **Job persistence** (jobs.create_job)
   - Normalises priority, deduplicates tags, records initial status (queued by default).
   - For mode=symbolic the request payload is hashed to form a cache key.
3. **Queue selection**
   - Policy / request metadata map to queue names:
     - Standard lane: calculator-jobs.
     - Heavy CPU lane: calculator-jobs-heavy.
     - GPU lane: calculator-jobs-gpu.
     - Symbolic lane: calculator-jobs-symbolic.
4. **Enqueue**
   - Celery task process_job or process_symbolic_job invoked with job ID,
     policy snapshot, OTEL context. Redis broker holds task until worker picks it
     up.
5. **Response**
   - Gateway returns 202 Accepted with job metadata, WebSocket URL, and Links
     (self, poll, result, ws). If symbolic cache hit exists, result payload is
     attached immediately and job marked succeeded.

## Worker Execution
- **Standard/Heavy/GPU**: Worker fetches job from Postgres, rebuilds context,
  streams evaluation to SafeEvaluator via gRPC, captures result or error.
- **Symbolic**: Worker checks Redis/Postgres cache (symbolic_cache_entries),
  otherwise posts to Symbolic Engine REST endpoint. Numeric verification runs if
  configured (randomised substitution) and flags outcomes.
- **Telemetry**: Worker attaches OTEL spans (queue wait, execution time) and
  increments Prometheus metrics for enqueues, retries, failures, runtime.

## Completion
1. Worker updates job status (STATUS_RUNNING -> STATUS_SUCCEEDED/FAILED) in
   Postgres with timezone-aware timestamps (utcnow() helper).
2. Result payload (or error) cached in Redis with TTL for fast polling.
3. WebSocket broadcaster publishes update on channel job.notification_namespace:job_id.
4. Rate limiter counters updated (per API key/job type) for quota tracking.
5. Audit log entry inserted for compliance (available for future governance layer).

## Failure Modes
- **Policy rejection**: Gateway returns 403 with policy.violations details.
- **Queue saturation**: If queue depth exceeds configured max_queue_size, API
  returns 429 with retry hints.
- **Worker failure**: Celery retry/backoff triggered, calculator_gateway_jobs_failed_total
  increments, job stays queued until retry window exhausted then marked ailed.
- **Symbolic verification mismatch**: Job marked succeeded with
  erification_passed=False and erification_error detailing mismatch; payload
  still returned but flagged for review.

## Polling and WebSockets
- **GET /jobs/{id}**: Returns merged view (Postgres state + cached payload) with
  policy metadata, queue, verification info.
- **WebSocket /ws/jobs/{id}**: Streams state transitions. Requires same API key
  header used for submission.

## Data Schema (jobs table)
| Field | Purpose |
|-------|---------|
| id (UUID) | Job identifier (string UUID4). |
| tenant | API key owner (maps to policy context). |
| status | queued, unning, succeeded, ailed. |
| input_expression | Original user expression (bounded length). |
| context | JSON of variable assignments. |
| result_payload | JSON result (cached). |
| error | Error payload if failed. |
| priority/requested_priority | Normalised vs requested priority. |
| queue_name | Queue actually used (after policy override). |
| symbolic_payload | Serialized symbolic request (if any). |
| symbolic_cache_key | SHA-256 hash for cache lookups. |
| verification_passed/error | Numeric verification outcome. |
| created_at/started_at/completed_at | UTC timestamps via helper. |

## Why This Flow
- Durable job metadata in Postgres allows recovery after worker crashes and
  supports audit/compliance needs.
- Redis cache + WebSocket reduces polling pressure and provides near-real-time
  updates to UI clients.
- Separate queues isolate workload characteristics (latency-critical vs heavy
  vs GPU vs symbolic) enabling targeted scaling and policies.
- Verification path for symbolic operations prevents silent algebra errors when
  user context is numeric.

## Update Checklist
- Expand queue table when adding new lanes (e.g., ML inference).
- Document new job fields or policy metadata as migrations land.
- Record new failure/retry behaviours (e.g., cancellation) once implemented.
- Refresh flow diagram when architecture shifts (e.g., message bus introduction).

## Open Questions
- Should we persist WebSocket event history for replay after disconnects?
- Do we need tenant-configurable retry policies in addition to global settings?
