from app.db.prisma_client import (
    prisma_db,
    connect_prisma,
    disconnect_prisma,
    create_job_with_certificates,
    get_job_by_id,
    get_certificates_by_job_id,
    get_pending_certificates_for_job,
    get_certificate_by_id,
    update_certificate_success,
    update_certificate_failure,
    increment_job_progress,
    update_job_status,
)

__all__ = [
    "prisma_db",
    "connect_prisma",
    "disconnect_prisma",
    "create_job_with_certificates",
    "get_job_by_id",
    "get_certificates_by_job_id",
    "get_pending_certificates_for_job",
    "get_certificate_by_id",
    "update_certificate_success",
    "update_certificate_failure",
    "increment_job_progress",
    "update_job_status",
]
