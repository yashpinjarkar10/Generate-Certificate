# Certificate producer service - enqueues ARQ jobs
from arq.connections import ArqRedis


async def enqueue_certificate_job(
    redis_pool: ArqRedis,
    job_id: str,
):
    """Enqueue a certificate generation job into ARQ Redis.

    Args:
        redis_pool: ARQ Redis connection pool
        job_id: Application-generated job ID

    Raises:
        Exception: If enqueueing fails (caller handles and returns 500)
    """
    await redis_pool.enqueue_job(
        "generate_certificates",
        job_id,
        _job_id=job_id,
    )