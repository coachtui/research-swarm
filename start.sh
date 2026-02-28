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

# NOTE: LD_LIBRARY_PATH is intentionally NOT set here.
# Setting it to standard system lib paths (/usr/lib/x86_64-linux-gnu etc.) triggers a
# glibc/vDSO dlopen bug: "error while loading shared libraries: __vdso_time: invalid mode
# for dlopen(): Invalid argument" — Python crashes before uvicorn binds the port.
# WeasyPrint's apt-installed shared libs are found via ldconfig (registered in nixpacks.toml).
# api/index.py has a ctypes.util.find_library filesystem-fallback patch for remaining cases.

echo "[start.sh] starting uvicorn on 0.0.0.0:${PORT:-8000}"
exec "${PYTHON_BIN}" -m uvicorn api.index:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}"
