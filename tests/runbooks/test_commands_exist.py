from pathlib import Path

RUNBOOK_COMMANDS = {
    "websocket_notifications.md": [
        "redis-cli -n 0 PUBSUB CHANNELS \"jobs:*\"",
        "redis-cli -n 0 PUBSUB NUMSUB \"jobs:{job_id}\"",
        "redis-cli -n 0 GET \"job:{job_id}\" | jq .",
        "celery -A services.gateway.app.task_queue inspect active_queues",
        "celery -A services.gateway.app.task_queue inspect active",
        "celery -A services.gateway.app.task_queue inspect reserved",
    ],
    "jobs_stuck.md": [
        "celery -A services.gateway.app.task_queue inspect active",
        "celery -A services.gateway.app.task_queue control revoke <task_id> --terminate --signal=SIGTERM",
        "celery -A services.gateway.app.task_queue purge -Q calculator",
    ],
    "queue_recovery.md": [
        "celery -A services.gateway.app.task_queue purge -Q calculator --force",
        "docker compose up -d --scale worker=4",
        "kubectl scale deployment calculator-worker",
    ],
    "redis_restore.md": [
        "redis-check-rdb dump.rdb",
        "redis-check-aof --fix appendonly.aof",
        "redis-server --dir /data --dbfilename dump.rdb --appendonly yes --appendfilename appendonly.aof",
    ],
}


def test_runbooks_include_required_commands() -> None:
    base = Path("docs/runbooks")
    for name, commands in RUNBOOK_COMMANDS.items():
        content = (base / name).read_text(encoding="utf-8")
        for command in commands:
            assert command in content, f"Expected `{command}` in {name}"
