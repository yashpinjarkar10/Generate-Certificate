"""
Tests for worker fault tolerance and individual certificate failure isolation.
Requirement: A failure while generating one certificate should not prevent
other valid certificates in the same job from being generated.
"""
from unittest.mock import patch
import pytest
from app.db import (
    prisma_db,
    create_job_with_certificates,
    get_job_by_id,
    get_certificates_by_job_id,
)
from app.queue.arq_worker import generate_certificates


@pytest.mark.asyncio
async def test_worker_handles_individual_certificate_failure():
    """Verify one failing certificate does not abort the entire batch."""
    job_id = "test_fault_isolation_job"
    certs = [
        {
            "certificate_id": "cert_fail_01",
            "name": "Broken User",
            "course": "Error Course",
            "date": "2026-10-07",
        },
        {
            "certificate_id": "cert_success_02",
            "name": "Good User",
            "course": "Valid Course",
            "date": "2026-10-07",
        },
    ]

    # Create job in database
    await create_job_with_certificates(job_id=job_id, total=2, certificates=certs)

    def mock_pdf_generator(name, course, issue_date, certificate_id):
        if certificate_id == "cert_fail_01":
            raise RuntimeError("Simulated render engine crash for this recipient!")
        return b"%PDF-1.4 Mock valid certificate"

    try:
        with patch(
            "app.queue.arq_worker.generate_certificate_pdf",
            side_effect=mock_pdf_generator,
        ), patch(
            "app.queue.arq_worker.upload_certificate_pdf",
            return_value="https://mock-s3.com/cert_success_02.pdf",
        ):
            result = await generate_certificates({}, job_id)

        # Worker should finish processing both
        assert result["completed"] == 1
        assert result["failed"] == 1

        # Check job in database
        job = await get_job_by_id(job_id)
        assert job["completed"] == 1
        assert job["failed"] == 1
        assert job["status"] == "completed"

        # Check individual certificates in database
        db_certs = await get_certificates_by_job_id(job_id)
        cert_map = {c["certificate_id"]: c for c in db_certs}

        # Failed certificate
        assert cert_map["cert_fail_01"]["status"] == "failed"
        assert "Simulated render engine crash" in cert_map["cert_fail_01"]["error"]

        # Successful certificate
        assert cert_map["cert_success_02"]["status"] == "completed"
        assert cert_map["cert_success_02"]["url"] == "https://mock-s3.com/cert_success_02.pdf"

    finally:
        await prisma_db.job.delete(where={"job_id": job_id})
