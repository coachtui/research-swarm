#!/usr/bin/env bash
set -e

# Ensure we run with the same virtualenv used during build.
if [[ -x "/opt/venv/bin/python" ]]; then
    export VIRTUAL_ENV="/opt/venv"
    export PATH="/opt/venv/bin:${PATH}"
    PYTHON_BIN="/opt/venv/bin/python"
else
    PYTHON_BIN="$(command -v python)"
fi

# Diagnostics — visible in Railway deployment logs.
echo "[start.sh] PWD=$(pwd) PORT=${PORT:-unset}"
echo "[start.sh] python=${PYTHON_BIN:-NOT_FOUND}"
echo "[start.sh] uvicorn=$(${PYTHON_BIN} -m uvicorn --version 2>/dev/null || echo NOT_FOUND)"

# WeasyPrint shared libs (needed when PDF routes are first invoked).
# Use parameter expansion without trailing colon: only append if non-empty.
export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/usr/lib:/usr/local/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

echo "[start.sh] starting uvicorn on 0.0.0.0:${PORT:-8000}"
exec "${PYTHON_BIN}" -m uvicorn api.index:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}"
