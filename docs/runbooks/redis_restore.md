# Redis Restore Runbook

Redis powers the async job cache and pub/sub bus. After an outage or data loss, follow these steps to restore service safely.

## 1. Identify available persistence files

* Locate the most recent RDB snapshot (`dump.rdb`) or AOF log (`appendonly.aof`) from the backup store.
* Verify file integrity before applying it to production.

```sh
redis-check-rdb dump.rdb
redis-check-aof --fix appendonly.aof
```

## 2. Prepare a staging instance

* Launch a disposable Redis container and copy the RDB/AOF into `/data`.
* Start Redis with both persistence modes enabled to rebuild from the restored data.

```sh
redis-server --dir /data --dbfilename dump.rdb --appendonly yes --appendfilename appendonly.aof
```

* Validate key shapes and TTL expectations:

```sh
redis-cli --scan | head -n 20
redis-cli -n 0 TTL "job:{job_id}"
```

## 3. Promote to production

1. Stop writers to the production Redis (scale gateway + worker deployments to zero).
2. Replace the production data directory with the validated snapshot.
3. Start Redis, then redeploy workers followed by gateways so Celery re-subscribes to channels.

## 4. Post-restore hygiene

* Clear out stale cache entries older than their TTL to avoid presenting outdated job payloads.
* Rebuild warm caches by polling `/jobs/{id}` for critical tenants.
* Monitor `queue_depth`, `jobs_in_progress`, and `job_wait_time_seconds` to ensure the system resumes normal throughput.

> **TTL note:** restoring an RDB snapshot resets expiration timers based on snapshot time. Expect a rush of expiration events; consider temporarily increasing Redis memory limits to absorb the burst.
