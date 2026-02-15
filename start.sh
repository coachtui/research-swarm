#!/bin/bash
set -e

echo "Generating Prisma client..."
prisma generate --schema=db/schema.prisma

echo "Starting uvicorn server..."
exec uvicorn api.index:app --host 0.0.0.0 --port $PORT
