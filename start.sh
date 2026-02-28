#!/usr/bin/env bash
set -e

# WeasyPrint shared libs (needed when PDF routes are first invoked)
export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/usr/lib:/usr/local/lib:${LD_LIBRARY_PATH:-}"

# Use python -m uvicorn (bypasses the script shebang — more reliable on nixpacks).
# Single worker: keeps startup fast; avoids per-worker module re-import overhead.
# ${PORT:-8000}: fallback in case Railway doesn't inject PORT.
exec /opt/venv/bin/python -m uvicorn api.index:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}"
