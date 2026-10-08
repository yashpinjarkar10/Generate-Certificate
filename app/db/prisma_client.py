"""
Prisma Database Client and helper functions for PostgreSQL.
"""
from datetime import datetime, date
from typing import Any, Dict, List, Optional
from prisma import Prisma

# Singleton Prisma instance
prisma_db = Prisma()


async def connect_prisma() -> None:
    """Connect Prisma client to PostgreSQL if not already connected."""
    if not prisma_db.is_connected():
        await prisma_db.connect()


async def disconnect_prisma() -> None:
    """Disconnect Prisma client from PostgreSQL."""
    if prisma_db.is_connected():
        await prisma_db.disconnect()


def _ensure_datetime(val: Any) -> datetime:
    """Helper to convert date or ISO string to datetime for Prisma."""
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime.combine(val, datetime.min.time())
    if isinstance(val, str):
        return datetime.fromisoformat(val)
    raise ValueError(f"Cannot convert {val} of type {type(val)} to datetime")


async def create_job_with_certificates(
    job_id: str,
    total: int,
    certificates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Create a new job and its associated certificates atomically."""
    await connect_prisma()

    # Create Job record
    job = await prisma_db.job.create(
        data={
            "job_id": job_id,
            "status": "queued",
            "total": total,
            "completed": 0,
            "failed": 0,
        }
    )

    # Create associated Certificate records
    cert_creates = [
        {
            "certificate_id": cert["certificate_id"],
            "job_id": job_id,
            "name": cert["name"],
            "course": cert["course"],
            "date": _ensure_datetime(cert["date"]),
            "status": "pending",
        }
        for cert in certificates
    ]

    if cert_creates:
        await prisma_db.certificate.create_many(data=cert_creates)

    return {
        "job_id": job.job_id,
        "status": job.status,
        "total": job.total,
        "completed": job.completed,
        "failed": job.failed,
    }


async def get_job_by_id(job_id: str) -> Optional[Dict[str, Any]]:
    """Fetch job metadata and progress by job_id."""
    await connect_prisma()
    job = await prisma_db.job.find_unique(where={"job_id": job_id})
    if not job:
        return None
    return {
        "job_id": job.job_id,
        "status": job.status,
        "total": job.total,
        "completed": job.completed,
        "failed": job.failed,
    }


async def get_certificates_by_job_id(job_id: str) -> List[Dict[str, Any]]:
    """Fetch all certificates belonging to a job."""
    await connect_prisma()
    certs = await prisma_db.certificate.find_many(where={"job_id": job_id})
    return [
        {
            "certificate_id": c.certificate_id,
            "job_id": c.job_id,
            "name": c.name,
            "course": c.course,
            "date": c.date.isoformat(),
            "status": c.status,
            "url": c.url,
            "error": c.error,
        }
        for c in certs
    ]


async def get_pending_certificates_for_job(job_id: str) -> List[Dict[str, Any]]:
    """Fetch all pending certificates to be processed by worker."""
    await connect_prisma()
    certs = await prisma_db.certificate.find_many(
        where={"job_id": job_id, "status": "pending"}
    )
    return [
        {
            "certificate_id": c.certificate_id,
            "job_id": c.job_id,
            "name": c.name,
            "course": c.course,
            "date": c.date,
            "status": c.status,
        }
        for c in certs
    ]


async def get_certificate_by_id(job_id: str, certificate_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single certificate by job_id and certificate_id."""
    await connect_prisma()
    cert = await prisma_db.certificate.find_first(
        where={
            "job_id": job_id,
            "certificate_id": certificate_id,
        }
    )
    if not cert:
        return None
    return {
        "certificate_id": cert.certificate_id,
        "job_id": cert.job_id,
        "name": cert.name,
        "course": cert.course,
        "date": cert.date.isoformat(),
        "status": cert.status,
        "url": cert.url,
        "error": cert.error,
    }


async def update_certificate_success(certificate_id: str, url: str) -> None:
    """Update certificate status to 'completed' with URL."""
    await connect_prisma()
    await prisma_db.certificate.update(
        where={"certificate_id": certificate_id},
        data={"status": "completed", "url": url},
    )


async def update_certificate_failure(certificate_id: str, error: str) -> None:
    """Update certificate status to 'failed' with error message."""
    await connect_prisma()
    await prisma_db.certificate.update(
        where={"certificate_id": certificate_id},
        data={"status": "failed", "error": error},
    )


async def increment_job_progress(
    job_id: str,
    completed_inc: int = 0,
    failed_inc: int = 0,
) -> None:
    """Increment completed or failed counts for a job."""
    await connect_prisma()
    update_data: Dict[str, Any] = {}
    if completed_inc:
        update_data["completed"] = {"increment": completed_inc}
    if failed_inc:
        update_data["failed"] = {"increment": failed_inc}

    if update_data:
        await prisma_db.job.update(
            where={"job_id": job_id},
            data=update_data,
        )


async def update_job_status(job_id: str, status: str) -> Optional[Dict[str, Any]]:
    """Update overall status of a job (e.g. cancelled, processing, completed, failed)."""
    await connect_prisma()
    job = await prisma_db.job.update(
        where={"job_id": job_id},
        data={"status": status},
    )
    if not job:
        return None
    return {
        "job_id": job.job_id,
        "status": job.status,
    }
