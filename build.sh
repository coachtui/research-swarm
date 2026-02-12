#!/bin/bash
set -e

echo "Python version:"
python3 --version

echo "Upgrading pip..."
python3 -m pip install --upgrade pip

echo "Installing dependencies with pre-built wheels only..."
python3 -m pip install -r requirements-vercel.txt --only-binary :all: --no-cache-dir

echo "Verifying installations..."
python3 -c "import pydantic; print(f'pydantic: {pydantic.__version__}')"
python3 -c "import prisma; print(f'prisma: {prisma.__version__}')"

echo "Generating Prisma client..."
python3 -m prisma generate --schema=db/schema.prisma

echo "Build complete!"
