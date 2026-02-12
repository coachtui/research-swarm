#!/bin/bash
set -e

echo "Python version:"
python3 --version

echo "Installing dependencies..."
pip install -r requirements-vercel.txt --no-cache-dir

echo "Verifying installations..."
python3 -c "import pydantic; print(f'Pydantic v{pydantic.__version__} - Pure Python (no Rust)')"
python3 -c "import prisma; print(f'Prisma: {prisma.__version__}')"

echo "Generating Prisma client..."
python3 -m prisma generate --schema=db/schema.prisma

echo "Build complete!"
