"""
Tests for PDF certificate rendering with ReportLab.
"""
from datetime import date
from app.services.certificate_generator import generate_certificate_pdf


def test_generate_certificate_pdf_valid():
    """Verify PDF generates valid binary content with PDF magic header."""
    pdf_bytes = generate_certificate_pdf(
        name="Charlie Brown",
        course="Distributed Systems",
        issue_date=date(2026, 10, 7),
        certificate_id="cert_test_999",
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    # Every valid PDF file starts with %PDF- header
    assert pdf_bytes.startswith(b"%PDF-")


def test_generate_certificate_pdf_with_string_date():
    """Verify PDF generator accepts string date formats."""
    pdf_bytes = generate_certificate_pdf(
        name="Diana Prince",
        course="AI Engineering",
        issue_date="2026-10-07",
        certificate_id="cert_test_888",
    )

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")
