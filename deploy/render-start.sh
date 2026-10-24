#!/usr/bin/env bash
set -euo pipefail
python manage.py migrate --noinput
python manage.py run_analysis_worker &
worker_pid=$!
gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-10000}" --workers 1 --threads 4 --timeout 120 &
web_pid=$!
trap 'kill "$worker_pid" "$web_pid" 2>/dev/null || true; wait 2>/dev/null || true' TERM INT EXIT
wait -n "$worker_pid" "$web_pid"
