# WebSocket Notifications Runbook

This runbook documents the recovery workflow when job update WebSocket notifications stall or deliver stale payloads.

## 1. Validate Redis channels

```sh
redis-cli -n 0 PUBSUB CHANNELS "jobs:*"
redis-cli -n 0 PUBSUB NUMSUB "jobs:{job_id}"
redis-cli -n 0 GET "job:{job_id}" | jq .
```

* `PUBSUB CHANNELS` should list the per-job topics; if empty while jobs are running, workers are not publishing updates.
* `PUBSUB NUMSUB` confirms the number of active subscribers for the affected job. Zero indicates gateway instances lost their subscriptions.
* `GET job:{job_id}` validates the hydrated cache payload that gateway serves on reconnect.

## 2. Confirm Celery workers before restarting

```sh
celery -A services.gateway.app.task_queue inspect active_queues
celery -A services.gateway.app.task_queue inspect active
celery -A services.gateway.app.task_queue inspect reserved
```

* All gateway workers should report the `calculator` queue.
* `inspect active` and `inspect reserved` must be non-empty for inflight jobs; if empty, workers may be disconnected or out of memory.

Only after verifying the above should you restart the missing worker pods or processes. Prefer targeted restarts to avoid interrupting healthy workers.

## 3. Post-restart checks

* Re-run the Redis checks to ensure subscribers and messages flow.
* Verify Grafana's *WS Clients & Send Errors* panel (fed by `ws_clients` and `ws_send_errors_total`) shows recovering clients.
* Tail the gateway logs for `websocket` errors to catch payload encoding problems early.
