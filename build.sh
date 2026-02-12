#!/bin/bash
set -e

echo "Python version:"
python3 --version

echo "Installing dependencies..."
uv pip install --system -r requirements-vercel.txt

echo "Verifying installations..."
python3 -c "import pydantic; print(f'pydantic: {pydantic.__version__}')"
python3 -c "import prisma; print(f'prisma: {prisma.__version__}')"

echo "Generating Prisma client..."
python3 -m prisma generate --schema=db/schema.prisma

echo "Build complete!"
