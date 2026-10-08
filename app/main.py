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


app = FastAPI(
    title="Bulk Certificate Generator API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health", tags=["health"])
async def health_check():
    """System health check endpoint verifying API, PostgreSQL (Prisma), and Redis connectivity."""
    from app.db import prisma_db
    from app.queue.redis import get_redis_settings
    from arq import create_pool

    db_status = "healthy"
    try:
        if not prisma_db.is_connected():
            await prisma_db.connect()
        await prisma_db.job.count()
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    redis_status = "healthy"
    worker_status = "ready"
    try:
        pool = await create_pool(get_redis_settings())
        await pool.ping()
        # Check if ARQ worker has registered its heartbeat in Redis
        health_key = await pool.get(b"arq:health-check")
        worker_status = "active" if health_key else "waiting_for_jobs"
        await pool.aclose()
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"

    overall = "healthy" if db_status == "healthy" and redis_status == "healthy" else "degraded"
    return {
        "status": overall,
        "api": "healthy",
        "database": db_status,
        "redis": redis_status,
        "worker_queue": worker_status,
    }


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)