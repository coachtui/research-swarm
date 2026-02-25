#!/bin/bash
set -e

# WeasyPrint runtime: ensure apt-installed shared libs (libgobject, libpango,
# libcairo etc.) are visible to ctypes.util.find_library even when Nix
# manages the Python binary with its own LD_LIBRARY_PATH.
export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/usr/lib:${LD_LIBRARY_PATH:-}"

echo "Generating Prisma client..."
prisma generate --schema=db/schema.prisma

echo "Starting uvicorn server..."
exec uvicorn api.index:app --host 0.0.0.0 --port $PORT
