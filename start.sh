#!/bin/bash
set -e

# ── Log DB target (host + database name only — no credentials) ────────────────
python3 - <<'PYEOF'
import os, urllib.parse
url = os.getenv("DATABASE_URL", "")
try:
    p = urllib.parse.urlparse(url)
    db_name = p.path.lstrip("/") or "(unknown)"
    print(f"[startup] DB target: {p.hostname}/{db_name}")
except Exception:
    print("[startup] DB target: (could not parse DATABASE_URL)")
PYEOF

# ── Apply pending database migrations ─────────────────────────────────────────
# Fail the deploy if any migration cannot be applied.
# `prisma` here is the Python-bundled CLI (prisma-client-py v5.x).
# For local dev use `python -m prisma migrate deploy` — do NOT use `npx prisma`
# which fetches the Node.js CLI v7+ which has an incompatible schema format.
echo "[startup] Applying database migrations..."
prisma migrate deploy --schema=db/schema.prisma
echo "[startup] Migrations applied."

# NOTE: prisma generate runs in buildCommand (railway.toml) at image-build time.
# Do NOT run it here — downloading the engine binary at startup delays uvicorn
# past Railway's 30s healthcheck window.

# ── WeasyPrint runtime: ensure apt-installed shared libs are visible ──────────
# libgobject, libpango, libcairo etc. live in /usr/lib/x86_64-linux-gnu when
# installed via apt, but Nix-managed Python may not see them via ldconfig.
export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/usr/lib:/usr/local/lib:${LD_LIBRARY_PATH:-}"
ldconfig /usr/lib/x86_64-linux-gnu /usr/lib /usr/local/lib 2>/dev/null || true

# ── Start server ──────────────────────────────────────────────────────────────
echo "[startup] Starting uvicorn..."
exec uvicorn api.index:app --host 0.0.0.0 --port "$PORT" --workers 2
