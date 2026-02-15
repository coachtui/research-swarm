release: prisma generate --schema=db/schema.prisma
web: uvicorn api.index:app --host 0.0.0.0 --port $PORT
