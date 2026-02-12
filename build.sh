#!/bin/bash
set -e

echo "Python version:"
python3 --version

echo "Upgrading pip, setuptools, and wheel..."
pip install --upgrade pip setuptools wheel

echo "Installing requirements with force reinstall..."
pip install -r requirements-vercel.txt --no-cache-dir --force-reinstall

echo "Verifying installations..."
python3 -c "import pydantic_core; print(f'pydantic_core: OK')"
python3 -c "import pydantic; print(f'pydantic version: {pydantic.__version__}')"
python3 -c "import prisma; print(f'prisma version: {prisma.__version__}')"

echo "Generating Prisma client..."
python3 -m prisma generate --schema=db/schema.prisma

echo "Build complete!"
