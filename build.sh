#!/bin/bash
set -e

echo "Installing Python dependencies..."
pip install --break-system-packages --no-cache-dir -r requirements-vercel.txt

echo "Verifying Prisma installation..."
python3 -c "import prisma; print(f'Prisma installed: {prisma.__version__}')"

echo "Generating Prisma client..."
python3 -m prisma generate --schema=db/schema.prisma

echo "Build complete!"
