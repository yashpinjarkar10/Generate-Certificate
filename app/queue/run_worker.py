"""
Runner for ARQ Background Worker with an HTTP health check listener.
"""
import os
import asyncio
import logging
from contextlib import asynccontextmanager
import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from arq.worker import create_worker
from app.queue.arq_worker import WorkerSettings

logger = logging.getLogger("worker_runner")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: Starlette):
    logger.info("[Worker Runner] Initializing ARQ worker...")
    worker = create_worker(WorkerSettings)
    app.state.worker = worker

    # Start ARQ worker as an asyncio background task in the running event loop
    worker_task = asyncio.create_task(worker.async_run())
    app.state.worker_task = worker_task
    logger.info("[Worker Runner] ARQ worker task successfully spawned in background.")

    try:
        yield
    finally:
        logger.info("[Worker Runner] Shutting down ARQ worker...")
        try:
            await worker.close()
        except Exception as e:
            logger.warning(f"[Worker Runner] Error closing worker: {e}")
        
        worker_task.cancel()
        try:
            await worker_task
        except (asyncio.CancelledError, Exception):
            pass
        logger.info("[Worker Runner] ARQ worker shutdown complete.")


async def health(request):
    """Health check endpoint to satisfy Render's port scanner and monitor worker status."""
    task = getattr(app.state, "worker_task", None)
    is_running = task is not None and not task.done()
    return JSONResponse(
        {
            "status": "healthy" if is_running else "degraded",
            "service": "arq_background_worker",
            "worker_running": is_running,
        },
        status_code=200 if is_running else 503,
    )


routes = [
    Route("/", health, methods=["GET"]),
    Route("/health", health, methods=["GET"]),
]

app = Starlette(routes=routes, lifespan=lifespan)


def main():
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"[Worker Runner] Starting worker health server on 0.0.0.0:{port}...")
    uvicorn.run("app.queue.run_worker:app", host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
