# Queue Recovery Runbook

Follow these steps when the calculator queue accumulates a large backlog or misroutes priorities.

## 1. Assess depth and priorities

* Review Grafana's *Queue Depth* panel (driven by `queue_depth`).
* Query Postgres for pending jobs ordered by priority to ensure the scheduler honours tenant SLAs.

```sql
SELECT id, status, priority, created_at
FROM jobs
WHERE status = 'queued'
ORDER BY priority DESC, created_at ASC
LIMIT 50;
```

## 2. Clear failed queue entries

If Celery moved tasks to the `celery` retry queue or dead-lettered them, drain the stale entries after capturing metrics.

```sh
celery -A services.gateway.app.task_queue inspect active_queues
celery -A services.gateway.app.task_queue purge -Q calculator --force
```

## 3. Route urgent workloads to a priority queue

Temporarily direct high-SLO workloads to a dedicated queue while the default queue drains.

```sh
export CALCULATOR_QUEUE_OVERRIDE=calculator-priority
celery -A services.gateway.app.task_queue control add_consumer calculator-priority --destination=worker@%h
```

Update the gateway configuration (`JOB_QUEUE_NAME`) and redeploy once the queue is stable.

## 4. Scale workers

```sh
# Docker Compose
DOCKER_DEFAULT_PLATFORM=linux/amd64 docker compose up -d --scale worker=4

# Kubernetes
kubectl scale deployment calculator-worker --replicas=6
kubectl autoscale deployment calculator-worker --cpu-percent=70 --min=2 --max=10
```

Monitor `celery_task_runtime_seconds` P95 and `job_wait_time_seconds` P95 during the scaling operation. Revert overrides when backlog falls below alert thresholds.
