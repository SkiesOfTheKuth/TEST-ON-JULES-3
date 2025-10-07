#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="/app:${PYTHONPATH:-}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8082}" --log-level info
