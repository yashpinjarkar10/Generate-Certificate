"""
Certificate Generator API Routes
"""
import csv
import io
import uuid
from typing import List
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from arq.connections import ArqRedis

from app.api.schema import (
    CertificateRequest,
    GenerateCertificateRequest,
    GenerateCertificateResponse,
    JobStatusResponse,
    CertificatesResponse,
    CertificateResponse,
    CancelJobResponse,
)
from app.db import (
    create_job_with_certificates,
    get_job_by_id,
    get_certificates_by_job_id,
    get_certificate_by_id,
    update_job_status,
)
from app.queue.redis import get_redis_pool
from app.services.certificate_producer import enqueue_certificate_job

router = APIRouter(
    prefix="/api/v1/generate-certificate",
    tags=["generate-certificate"],
)


def parse_csv_certificates(file_bytes: bytes) -> List[CertificateRequest]:
    """Parse CSV data where columns can be in any order.

    Rules:
      - 'name' column is compulsory.
      - 'course' and 'date' columns are optional (default to 'Python' and today's date).
      - Headers are case-insensitive ('Name', 'COURSE', 'date', etc.).
    """
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file must be UTF-8 encoded text.",
        )

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is empty or missing headers.",
        )

    # Normalize header names to lowercase
    header_map = {col.strip().lower(): col for col in reader.fieldnames if col}
    if "name" not in header_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV must contain a compulsory 'name' column.",
        )

    name_col = header_map["name"]
    course_col = header_map.get("course")
    date_col = header_map.get("date")

    certificates: List[CertificateRequest] = []
    for row_idx, row in enumerate(reader, start=2):
        raw_name = (row.get(name_col) or "").strip()
        if not raw_name:
            continue

        raw_course = (row.get(course_col) or "").strip() if course_col else None
        raw_date = (row.get(date_col) or "").strip() if date_col else None

        item: dict = {"name": raw_name}
        if raw_course:
            item["course"] = raw_course
        if raw_date:
            item["date"] = raw_date

        try:
            certificates.append(CertificateRequest(**item))
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid data at row {row_idx}: {str(err)}",
            )

    if not certificates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV contains no valid recipient records with non-empty 'name'.",
        )

    return certificates


# 1. Create certificate generation job (JSON payload)
@router.post(
    "",
    response_model=GenerateCertificateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_certificate_job(
    request: GenerateCertificateRequest,
    redis_pool: ArqRedis = Depends(get_redis_pool),
):
    """Create a bulk certificate generation job from JSON.

    Flow:
        1. Validate request body (Pydantic: name compulsory, course/date optional)
        2. Generate unique job_id and certificate_ids
        3. Step A: Save initial status to Database (Prisma PostgreSQL)
        4. Step B: Put task in queue (Redis / ARQ)
        5. Step C: Return 202 Accepted immediately
    """
    job_id = f"job_{uuid.uuid4().hex[:8]}"

    certificates_data = []
    for cert in request.certificates:
        cert_dict = cert.model_dump(mode="json")
        cert_dict["certificate_id"] = f"cert_{uuid.uuid4().hex[:8]}"
        certificates_data.append(cert_dict)

    # Step A: Save initial status to Database (Prisma PostgreSQL)
    try:
        await create_job_with_certificates(
            job_id=job_id,
            total=len(certificates_data),
            certificates=certificates_data,
        )
    except Exception as db_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while saving job: {str(db_err)}",
        )

    # Step B: Put task in queue (Redis / ARQ)
    try:
        await enqueue_certificate_job(
            redis_pool=redis_pool,
            job_id=job_id,
        )
    except Exception as queue_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue certificate job: {str(queue_err)}",
        )

    # Step C: Return 202 Accepted immediately
    return GenerateCertificateResponse(
        job_id=job_id,
        status="queued",
        total=len(certificates_data),
    )


# 1b. Create certificate generation job from CSV upload
@router.post(
    "/csv",
    response_model=GenerateCertificateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_certificate_job_from_csv(
    file: UploadFile = File(..., description="CSV file with columns name, course, and date (any order)"),
    redis_pool: ArqRedis = Depends(get_redis_pool),
):
    """Create a bulk certificate generation job from an uploaded CSV file.

    CSV specifications:
      - 'name' column is compulsory.
      - 'course' and 'date' columns are optional in any order (defaults to 'Python' and today).
    """
    file_bytes = await file.read()
    certificates = parse_csv_certificates(file_bytes)

    # Re-use generation flow with parsed certificates
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    certificates_data = []
    for cert in certificates:
        cert_dict = cert.model_dump(mode="json")
        cert_dict["certificate_id"] = f"cert_{uuid.uuid4().hex[:8]}"
        certificates_data.append(cert_dict)

    # Step A: Save initial status to Database
    try:
        await create_job_with_certificates(
            job_id=job_id,
            total=len(certificates_data),
            certificates=certificates_data,
        )
    except Exception as db_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while saving job: {str(db_err)}",
        )

    # Step B: Put task in queue
    try:
        await enqueue_certificate_job(
            redis_pool=redis_pool,
            job_id=job_id,
        )
    except Exception as queue_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue certificate job: {str(queue_err)}",
        )

    # Step C: Return 202 Accepted
    return GenerateCertificateResponse(
        job_id=job_id,
        status="queued",
        total=len(certificates_data),
    )


# 2. Check job status/progress
@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def check_certificate_job(job_id: str):
    """Check job status and current generation progress."""
    job = await get_job_by_id(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    return JobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        total=job["total"],
        completed=job["completed"],
        failed=job["failed"],
    )


# 3. Get all generated certificates
@router.get(
    "/{job_id}/certificates",
    response_model=CertificatesResponse,
    status_code=status.HTTP_200_OK,
)
async def get_certificates(job_id: str):
    """Get all certificates belonging to a job with their generation status."""
    job = await get_job_by_id(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    certificates = await get_certificates_by_job_id(job_id)

    return CertificatesResponse(
        job_id=job["job_id"],
        status=job["status"],
        total=job["total"],
        completed=job["completed"],
        failed=job["failed"],
        certificates=[
            CertificateResponse(
                certificate_id=c["certificate_id"],
                name=c["name"],
                status=c["status"],
                url=c.get("url"),
            )
            for c in certificates
        ],
    )


# 4. Get a specific certificate
@router.get(
    "/{job_id}/certificates/{certificate_id}",
    response_model=CertificateResponse,
    status_code=status.HTTP_200_OK,
)
async def get_specific_certificate(
    job_id: str,
    certificate_id: str,
):
    """Get a specific certificate record by job_id and certificate_id."""
    certificate = await get_certificate_by_id(job_id, certificate_id)
    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found",
        )

    return CertificateResponse(
        certificate_id=certificate["certificate_id"],
        name=certificate["name"],
        status=certificate["status"],
        url=certificate.get("url"),
    )


# 5. Cancel a job
@router.delete(
    "/{job_id}",
    response_model=CancelJobResponse,
    status_code=status.HTTP_200_OK,
)
async def cancel_certificate_job(job_id: str):
    """Cancel a certificate generation job."""
    job = await get_job_by_id(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    await update_job_status(job_id, status="cancelled")

    return CancelJobResponse(job_id=job_id, status="cancelled")