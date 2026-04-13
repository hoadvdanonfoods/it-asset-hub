#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p .run

PID_FILE=".run/it_asset_hub.pid"
LOG_FILE=".run/it_asset_hub.log"

if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${OLD_PID}" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "Already running with PID $OLD_PID"
    exit 0
  fi
fi

nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010 >> "$LOG_FILE" 2>&1 < /dev/null &
PID=$!
echo "$PID" > "$PID_FILE"
sleep 2

if kill -0 "$PID" 2>/dev/null; then
  echo "Started IT Asset Hub with PID $PID"
  echo "Log: $LOG_FILE"
else
  echo "Failed to start. Check log: $LOG_FILE" >&2
  exit 1
fi
