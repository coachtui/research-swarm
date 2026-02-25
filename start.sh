#!/bin/bash
set -e

# WeasyPrint runtime: ensure apt-installed shared libs (libgobject, libpango,
# libcairo etc.) are visible to ctypes.util.find_library even when Nix
# manages the Python binary with its own LD_LIBRARY_PATH.
export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/usr/lib:/usr/local/lib:${LD_LIBRARY_PATH:-}"

# Refresh ldconfig cache at startup so /etc/ld.so.cache includes apt libs.
# The build-time ldconfig (nixpacks.toml cmds) may not persist correctly.
ldconfig /usr/lib/x86_64-linux-gnu /usr/lib /usr/local/lib 2>/dev/null || true

echo "Generating Prisma client..."
prisma generate --schema=db/schema.prisma

echo "Starting uvicorn server..."
exec uvicorn api.index:app --host 0.0.0.0 --port $PORT
