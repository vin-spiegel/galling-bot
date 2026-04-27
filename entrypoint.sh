#!/bin/bash
set -e

echo "[entrypoint] Starting xvfb..."
Xvfb :99 -screen 0 1280x800x24 -ac &
XVFB_PID=$!
sleep 2

if ! kill -0 $XVFB_PID 2>/dev/null; then
    echo "[entrypoint] ERROR: Xvfb failed to start"
    exit 1
fi

echo "[entrypoint] Xvfb started (PID=$XVFB_PID)"
export DISPLAY=:99

echo "[entrypoint] Running bot..."
python -u src/run_once.py
EXIT_CODE=$?

echo "[entrypoint] Bot finished with exit code $EXIT_CODE"
kill $XVFB_PID 2>/dev/null || true
exit $EXIT_CODE
