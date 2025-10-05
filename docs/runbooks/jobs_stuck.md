# Jobs Stuck Runbook

Use this guide when queued jobs stop progressing or remain in `running` for longer than SLO targets.

## 1. Detect

* Check Grafana for a rising `jobs_in_progress` gauge and stagnant `jobs_enqueued_total` rate.
* Inspect traces in Tempo for spans with unusually high `worker_process_ms` or repeated `outcome=retry` annotations.
* Review `queue_depth` for the affected queue; values above steady-state indicate backlog.

## 2. Diagnose the backlog

```sh
celery -A services.gateway.app.task_queue inspect active
celery -A services.gateway.app.task_queue inspect reserved
celery -A services.gateway.app.task_queue inspect scheduled
```

* `inspect active` shows tasks currently executing; confirm job IDs match the stuck ones.
* `inspect reserved` reveals tasks the worker has pre-fetched but not started.
* `inspect scheduled` surfaces delayed retries—if this grows, increase worker count or backoff window.

## 3. Safe cancel or retry

```sh
celery -A services.gateway.app.task_queue control revoke <task_id> --terminate --signal=SIGTERM
celery -A services.gateway.app.task_queue control retry <task_id>
```

* Use `revoke` with `--terminate` only after confirming the evaluator is idempotent; otherwise finish the calculation manually.
* `control retry` requeues the task immediately; monitor `job_wait_time_seconds` histogram to ensure it re-enters the queue.

## 4. Purge the queue (last resort)

```sh
celery -A services.gateway.app.task_queue purge -Q calculator
```

* Always take a Redis RDB/AOF snapshot before purging.
* Notify tenants—purging discards queued jobs permanently. After purge, repopulate cache entries via `/jobs/{id}` polling to rebuild state.
