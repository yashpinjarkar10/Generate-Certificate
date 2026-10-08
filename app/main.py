"""
Entry point for Certificate Generator API.
Run with: uvicorn app.main:app --reload
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn
from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.queue.redis import create_redis_pool
    from app.db import connect_prisma, disconnect_prisma

    # Connect to PostgreSQL via Prisma
    await connect_prisma()

    # Create ARQ Redis pool during startup and cleanup on shutdown
    async with create_redis_pool(app):
        yield

    # Disconnect Prisma on shutdown
    await disconnect_prisma()


app = FastAPI(lifespan=lifespan)
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)