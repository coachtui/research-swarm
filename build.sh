#!/bin/bash
set -e

echo "Python version:"
python3 --version

echo "Installing dependencies..."
uv pip install --target .vercel_python_packages -r requirements-vercel.txt --no-cache-dir --reinstall

export PYTHONPATH=".vercel_python_packages:$PYTHONPATH"

echo "Verifying installations..."
python3 -c "import pydantic; print(f'Pydantic v{pydantic.__version__}')"
python3 -c "import prisma; print(f'Prisma: {prisma.__version__}')"

echo "Generating Prisma client..."
python3 -m prisma generate --schema=db/schema.prisma

echo "Build complete!"
