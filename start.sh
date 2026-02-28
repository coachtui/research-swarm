#!/usr/bin/env bash
set -e

# Diagnostics — visible in Railway deployment logs.
echo "[start.sh] PWD=$(pwd) PORT=${PORT:-unset}"
echo "[start.sh] python=$(which python 2>/dev/null || echo NOT_FOUND)"
echo "[start.sh] uvicorn=$(python -m uvicorn --version 2>/dev/null || echo NOT_FOUND)"

# WeasyPrint shared libs (needed when PDF routes are first invoked).
# Use parameter expansion without trailing colon: only append if non-empty.
export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/usr/lib:/usr/local/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

echo "[start.sh] starting uvicorn on 0.0.0.0:${PORT:-8000}"
exec python -m uvicorn api.index:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}"
