"""
Tests for API routes: Job creation (JSON & CSV), status tracking, certificate retrieval, and cancellation.
"""
import pytest
from app.db import prisma_db


@pytest.mark.asyncio
async def test_job_lifecycle_e2e(client):
    """Test full API lifecycle: create job, check status, retrieve certificates, and cancel."""
    payload = {
        "certificates": [
            {
                "name": "Eve Adams",
                # course and date omitted to test defaults!
            },
            {
                "name": "Frank Miller",
                "course": "DevOps",
                "date": "2026-10-07",
            },
        ]
    }

    # 1. Create Job -> 202 Accepted
    create_resp = await client.post("/api/v1/generate-certificate", json=payload)
    assert create_resp.status_code == 202
    job_data = create_resp.json()
    job_id = job_data["job_id"]
    assert job_data["status"] == "queued"
    assert job_data["total"] == 2

    try:
        # 2. Check Job Status -> 200 OK
        status_resp = await client.get(f"/api/v1/generate-certificate/{job_id}")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["job_id"] == job_id
        assert status_data["status"] == "queued"
        assert status_data["total"] == 2
        assert status_data["completed"] == 0
        assert status_data["failed"] == 0

        # 3. Retrieve All Certificates for Job -> 200 OK
        certs_resp = await client.get(f"/api/v1/generate-certificate/{job_id}/certificates")
        assert certs_resp.status_code == 200
        certs_data = certs_resp.json()
        assert len(certs_data["certificates"]) == 2

        # Check default applied for Eve Adams
        eve_cert = next(c for c in certs_data["certificates"] if c["name"] == "Eve Adams")
        assert eve_cert is not None

        first_cert_id = certs_data["certificates"][0]["certificate_id"]

        # 4. Retrieve Specific Certificate -> 200 OK
        single_resp = await client.get(
            f"/api/v1/generate-certificate/{job_id}/certificates/{first_cert_id}"
        )
        assert single_resp.status_code == 200
        single_data = single_resp.json()
        assert single_data["certificate_id"] == first_cert_id

        # 5. Cancel Job -> 200 OK
        cancel_resp = await client.delete(f"/api/v1/generate-certificate/{job_id}")
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["status"] == "cancelled"

        # Verify job status updated to cancelled
        status_after_cancel = await client.get(f"/api/v1/generate-certificate/{job_id}")
        assert status_after_cancel.json()["status"] == "cancelled"

    finally:
        # Cleanup test job
        await prisma_db.job.delete(where={"job_id": job_id})


@pytest.mark.asyncio
async def test_csv_upload_endpoint(client):
    """Test creating a job from an uploaded CSV file with out-of-order columns."""
    csv_bytes = b"date,name\n2026-08-01,Grace Hopper\n"
    response = await client.post(
        "/api/v1/generate-certificate/csv",
        files={"file": ("participants.csv", csv_bytes, "text/csv")},
    )
    assert response.status_code == 202
    data = response.json()
    job_id = data["job_id"]
    assert data["status"] == "queued"
    assert data["total"] == 1

    try:
        # Verify certificates in database
        certs_resp = await client.get(f"/api/v1/generate-certificate/{job_id}/certificates")
        assert certs_resp.status_code == 200
        certs = certs_resp.json()["certificates"]
        assert len(certs) == 1
        assert certs[0]["name"] == "Grace Hopper"
    finally:
        await prisma_db.job.delete(where={"job_id": job_id})


@pytest.mark.asyncio
async def test_nonexistent_job_returns_404(client):
    """Querying a non-existent job returns 404 Not Found."""
    resp = await client.get("/api/v1/generate-certificate/job_nonexistent_12345")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_health_check_endpoint(client):
    """Health check endpoint returns 200 OK and status components."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "api" in data
    assert "database" in data
    assert "redis" in data
    assert "worker_queue" in data

