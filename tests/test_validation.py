"""
Tests for input validation (JSON and CSV) on Certificate Generation API.
"""
from datetime import date
import io
import pytest
from app.api.schema import CertificateRequest, GenerateCertificateRequest
from app.api.routes import parse_csv_certificates
from pydantic import ValidationError


def test_name_compulsory_and_course_date_optional():
    """Verify name is compulsory, while course and date default to Python and today's date."""
    cert = CertificateRequest(name="John Doe")
    assert cert.name == "John Doe"
    assert cert.course == "Python"
    assert cert.date == date.today()


def test_empty_name_rejected():
    """Empty string or whitespace for recipient name must raise ValidationError."""
    with pytest.raises(ValidationError):
        CertificateRequest(name="   ")


def test_empty_course_and_date_fall_back_to_defaults():
    """Empty course or date fall back to 'Python' and today's date."""
    cert = CertificateRequest(name="Alice", course="", date=None)
    assert cert.name == "Alice"
    assert cert.course == "Python"
    assert cert.date == date.today()


def test_empty_certificates_list_rejected():
    """Empty certificates list must raise ValidationError."""
    with pytest.raises(ValidationError):
        GenerateCertificateRequest(certificates=[])


def test_parse_csv_certificates_any_column_order():
    """CSV parsing succeeds with columns in arbitrary order and optional columns missing."""
    csv_content = b"""date,name
2026-05-15,Michael Scott
2026-06-20,Jim Halpert
"""
    results = parse_csv_certificates(csv_content)
    assert len(results) == 2
    assert results[0].name == "Michael Scott"
    assert results[0].course == "Python"  # default
    assert results[0].date == date(2026, 5, 15)

    assert results[1].name == "Jim Halpert"
    assert results[1].course == "Python"


def test_parse_csv_certificates_only_name_column():
    """CSV with only 'name' column succeeds with all defaults applied."""
    csv_content = b"""name
Pam Beesly
Dwight Schrute
"""
    results = parse_csv_certificates(csv_content)
    assert len(results) == 2
    assert results[0].name == "Pam Beesly"
    assert results[0].course == "Python"
    assert results[0].date == date.today()


def test_parse_csv_missing_name_column_raises():
    """CSV missing compulsory 'name' column raises HTTP 400."""
    csv_content = b"""course,date
React,2026-10-07
"""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        parse_csv_certificates(csv_content)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_api_rejects_empty_payload(client):
    """API endpoint returns 422 on empty JSON payload."""
    response = await client.post("/api/v1/generate-certificate", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_api_rejects_empty_certificates_list(client):
    """API endpoint returns 422 when certificates list is empty."""
    response = await client.post(
        "/api/v1/generate-certificate",
        json={"certificates": []},
    )
    assert response.status_code == 422
