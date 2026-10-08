"""
ARQ Worker Module for Background Certificate Processing.
Run with: uv run python -m arq app.queue.arq_worker.WorkerSettings
"""
import os
import asyncio
import logging
from typing import Any, Dict
from app.queue.redis import get_redis_settings
from app.db import (
    connect_prisma,
    disconnect_prisma,
    get_job_by_id,
    get_pending_certificates_for_job,
    update_certificate_success,
    update_certificate_failure,
    increment_job_progress,
    update_job_status,
)
from app.services.certificate_generator import generate_certificate_pdf
from app.services.storage_service import upload_certificate_pdf

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def _handle_render_health_probe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Handle HTTP health checks from Render port scanner."""
    try:
        await reader.read(1024)
        body = b'{"status":"healthy","service":"arq_worker"}'
        resp = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n"
            b"Connection: close\r\n\r\n" + body
        )
        writer.write(resp)
        await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def startup(ctx: Dict[str, Any]) -> None:
    """Connect to database when worker starts and bind to PORT if running as Render Web Service."""
    logger.info("[ARQ Worker] Initializing worker and connecting to PostgreSQL via Prisma...")
    await connect_prisma()

    # If running as a Web Service on Render, PORT is set in environment.
    # Bind an HTTP health probe on 0.0.0.0:$PORT so Render's port scan passes immediately.
    port_env = os.getenv("PORT")
    if port_env:
        try:
            port = int(port_env)
            server = await asyncio.start_server(_handle_render_health_probe, "0.0.0.0", port)
            ctx["health_server"] = server
            logger.info(f"[ARQ Worker] Bound health listener to 0.0.0.0:{port} for Render port scanner.")
        except Exception as e:
            logger.warning(f"[ARQ Worker] Could not start health listener on port {port_env}: {e}")


async def shutdown(ctx: Dict[str, Any]) -> None:
    """Disconnect database when worker stops and close health probe server."""
    logger.info("[ARQ Worker] Shutting down worker and disconnecting Prisma...")
    server = ctx.get("health_server")
    if server:
        server.close()
        try:
            await server.wait_closed()
        except Exception:
            pass
    await disconnect_prisma()


async def generate_certificates(ctx: Dict[str, Any], job_id: str) -> Dict[str, Any]:
    """Consumer function to process bulk certificates for a given job.

    Workflow:
      1. Fetch job record and verify it exists and is not cancelled.
      2. Mark job status as 'processing'.
      3. Fetch all pending certificate rows for this job.
      4. For each recipient:
          - Check if cancellation was requested mid-job.
          - Generate elegant PDF in memory via ReportLab.
          - Upload PDF to S3 bucket and receive presigned URL.
          - Mark certificate 'completed' and increment 'completed' count.
          - Catch errors per-recipient so one failure does not halt the batch.
      5. Mark final job status ('completed' or 'failed').
    """
    logger.info(f"[ARQ Worker] Starting processing for job_id={job_id}")

    # 1. Fetch job record
    job = await get_job_by_id(job_id)
    if not job:
        logger.warning(f"[ARQ Worker] Job {job_id} not found in database. Exiting.")
        return {"job_id": job_id, "status": "not_found"}

    # 2. Check if cancelled before starting
    if job["status"] == "cancelled":
        logger.info(f"[ARQ Worker] Job {job_id} was cancelled before execution. Exiting.")
        return {"job_id": job_id, "status": "cancelled"}

    # 3. Mark job as processing
    await update_job_status(job_id, status="processing")

    # 4. Fetch pending certificates
    pending_certs = await get_pending_certificates_for_job(job_id)
    logger.info(f"[ARQ Worker] Job {job_id}: Found {len(pending_certs)} certificates to generate.")

    # 5. Process each recipient
    for cert in pending_certs:
        # Check if job was cancelled while in progress
        current_job = await get_job_by_id(job_id)
        if current_job and current_job["status"] == "cancelled":
            logger.info(f"[ARQ Worker] Job {job_id} was cancelled during batch. Halting loop.")
            break

        cert_id = cert["certificate_id"]
        try:
            # Generate PDF bytes
            pdf_bytes = generate_certificate_pdf(
                name=cert["name"],
                course=cert["course"],
                issue_date=cert["date"],
                certificate_id=cert_id,
            )

            # Upload to S3 bucket
            s3_key = f"certificates/{job_id}/{cert_id}.pdf"
            download_url = upload_certificate_pdf(s3_key, pdf_bytes)

            # Mark completed in DB
            await update_certificate_success(cert_id, url=download_url)
            await increment_job_progress(job_id, completed_inc=1)
            logger.info(f"[ARQ Worker] Successfully generated cert {cert_id} for '{cert['name']}'")

        except Exception as exc:
            # Individual recipient failure isolation
            logger.error(f"[ARQ Worker] Failed to generate cert {cert_id}: {exc}")
            await update_certificate_failure(cert_id, error=str(exc))
            await increment_job_progress(job_id, failed_inc=1)

    # 6. Finalize job status
    final_job = await get_job_by_id(job_id)
    if final_job and final_job["status"] != "cancelled":
        if final_job["completed"] == 0 and final_job["failed"] > 0:
            final_status = "failed"
        else:
            final_status = "completed"
        await update_job_status(job_id, status=final_status)
        logger.info(f"[ARQ Worker] Job {job_id} finalized with status={final_status}")

    return {
        "job_id": job_id,
        "completed": final_job["completed"] if final_job else 0,
        "failed": final_job["failed"] if final_job else 0,
    }


class WorkerSettings:
    """ARQ Worker configuration settings."""
    functions = [generate_certificates]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = get_redis_settings()
    max_jobs = 10
    job_timeout = 600  # 10 minutes timeout