#!/bin/bash
set -e

echo "Python version:"
python3 --version

echo "Installing Python dependencies with uv..."
uv pip install --system --no-cache-dir --reinstall-package pydantic-core -r requirements-vercel.txt

echo "Verifying installations..."
python3 -c "import pydantic_core; print(f'pydantic_core: OK')"
python3 -c "import pydantic; print(f'pydantic: OK')"
python3 -c "import prisma; print(f'prisma: {prisma.__version__}')"

echo "Generating Prisma client..."
python3 -m prisma generate --schema=db/schema.prisma

echo "Build complete!"
