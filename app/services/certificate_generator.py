"""
Certificate PDF Generator using ReportLab.
Renders an elegant predefined landscape certificate template with recipient details.
"""
import io
from datetime import datetime, date
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas


def generate_certificate_pdf(
    name: str,
    course: str,
    issue_date: str | date | datetime,
    certificate_id: str,
) -> bytes:
    """Generate an in-memory PDF certificate for a recipient.

    Args:
        name: Recipient full name
        course: Course title
        issue_date: Date of completion (string or date object)
        certificate_id: Unique certificate tracking ID

    Returns:
        Raw PDF file bytes
    """
    buffer = io.BytesIO()
    width, height = landscape(A4)  # 841.89 x 595.27 points

    c = canvas.Canvas(buffer, pagesize=landscape(A4))

    # --- Decorative Borders ---
    # Outer dark blue border
    c.setStrokeColor(colors.HexColor("#1E3A8A"))
    c.setLineWidth(4)
    c.rect(20, 20, width - 40, height - 40)

    # Inner gold border
    c.setStrokeColor(colors.HexColor("#D97706"))
    c.setLineWidth(1.5)
    c.rect(28, 28, width - 56, height - 56)

    # Corner decorations
    c.setStrokeColor(colors.HexColor("#D97706"))
    c.setLineWidth(2)
    corner_len = 25
    # Top-left
    c.line(35, height - 35, 35 + corner_len, height - 35)
    c.line(35, height - 35, 35, height - 35 - corner_len)
    # Top-right
    c.line(width - 35, height - 35, width - 35 - corner_len, height - 35)
    c.line(width - 35, height - 35, width - 35, height - 35 - corner_len)
    # Bottom-left
    c.line(35, 35, 35 + corner_len, 35)
    c.line(35, 35, 35, 35 + corner_len)
    # Bottom-right
    c.line(width - 35, 35, width - 35 - corner_len, 35)
    c.line(width - 35, 35, width - 35, 35 + corner_len)

    # --- Header ---
    c.setFillColor(colors.HexColor("#1E3A8A"))
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(width / 2.0, height - 100, "CERTIFICATE OF COMPLETION")

    c.setFillColor(colors.HexColor("#6B7280"))
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(width / 2.0, height - 130, "THIS CERTIFICATE IS PROUDLY PRESENTED TO")

    # --- Recipient Name ---
    c.setFillColor(colors.HexColor("#111827"))
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(width / 2.0, height - 200, name)

    # Underline accent for name
    c.setStrokeColor(colors.HexColor("#D97706"))
    c.setLineWidth(1.5)
    c.line(width / 2.0 - 180, height - 215, width / 2.0 + 180, height - 215)

    # --- Description & Course ---
    c.setFillColor(colors.HexColor("#4B5563"))
    c.setFont("Helvetica", 14)
    c.drawCentredString(width / 2.0, height - 260, "for successfully completing the course")

    c.setFillColor(colors.HexColor("#1E3A8A"))
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width / 2.0, height - 300, course)

    # --- Footer Info ---
    # Format date string
    if isinstance(issue_date, (datetime, date)):
        date_str = issue_date.strftime("%B %d, %Y")
    else:
        date_str = str(issue_date)

    # Left: Date Issued
    c.setFillColor(colors.HexColor("#374151"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(70, 95, f"Date Issued: {date_str}")

    # Right: Certificate Verification ID
    c.drawRightString(width - 70, 95, f"Certificate ID: {certificate_id}")

    # Signature line in center
    c.setStrokeColor(colors.HexColor("#9CA3AF"))
    c.setLineWidth(1)
    c.line(width / 2.0 - 100, 105, width / 2.0 + 100, 105)
    c.setFont("Helvetica", 11)
    c.setFillColor(colors.HexColor("#6B7280"))
    c.drawCentredString(width / 2.0, 90, "Authorized Signature")

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer.getvalue()
