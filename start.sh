#!/usr/bin/env bash
set -euo pipefail

echo "[startup] Starting Research Swarm API..."
echo "[startup] PORT=${PORT:-<missing>}"

# Fail fast if Railway didn't inject PORT
: "${PORT:?PORT is not set}"

# ── WeasyPrint runtime: ensure apt-installed shared libs are visible ──────────
# libgobject, libpango, libcairo etc. live in /usr/lib/x86_64-linux-gnu when
# installed via apt, but Nix-managed Python may not see them via ldconfig.
export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/usr/lib:/usr/local/lib:${LD_LIBRARY_PATH:-}"
ldconfig /usr/lib/x86_64-linux-gnu /usr/lib /usr/local/lib 2>/dev/null || true

# ── Database migrations ────────────────────────────────────────────────────────
# Migrations are NOT run here to avoid blocking the healthcheck window.
# Run new migrations manually before deploying:
#   railway run python -m prisma migrate deploy --schema=db/schema.prisma
# Or via Railway's pre-deploy command (set in the Railway dashboard).
# prisma generate runs at BUILD time (buildCommand in railway.toml).

# ── Start server ──────────────────────────────────────────────────────────────
# Use explicit venv path — do not rely on PATH in Railway's nixpacks runtime.
# --proxy-headers: trust X-Forwarded-* headers from Railway's reverse proxy.
# --workers 2: one worker handles health/short requests, one handles analyses.
echo "[startup] Starting uvicorn..."
exec /opt/venv/bin/uvicorn api.index:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --workers 2 \
    --proxy-headers
