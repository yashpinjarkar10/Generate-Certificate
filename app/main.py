"""
Entry point for Certificate Generator API.
Run with: uvicorn app.main:app --reload
"""
import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
from app.api.routes import router

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[Startup] Initializing Certificate Generator API...")

    db_url = os.getenv("DATABASE_URL")
    redis_url = os.getenv("REDIS_URL")

    if not db_url:
        logger.warning("[Startup] WARNING: DATABASE_URL environment variable is not set!")
    if not redis_url and not os.getenv("REDIS_HOST"):
        logger.warning("[Startup] WARNING: REDIS_URL environment variable is not set!")

    from app.queue.redis import create_redis_pool
    from app.db import connect_prisma, disconnect_prisma

    # Connect to PostgreSQL via Prisma
    try:
        await connect_prisma()
        logger.info("[Startup] Connected to PostgreSQL via Prisma.")
    except Exception as e:
        logger.error(f"[Startup] Failed to connect to database: {e}")
        raise

    # Create ARQ Redis pool during startup and cleanup on shutdown
    try:
        async with create_redis_pool(app):
            logger.info("[Startup] Connected to ARQ Redis pool.")
            yield
    finally:
        # Disconnect Prisma on shutdown
        await disconnect_prisma()
        logger.info("[Shutdown] Disconnected database. Shutdown complete.")


app = FastAPI(
    title="Bulk Certificate Generator API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


# Mount static frontend dashboard if directory exists
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)