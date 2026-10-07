from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from app.config import settings


class CertificateGenerationError(Exception):
    pass


def generate_certificate_pdf(
    *,
    output_path: Path,
    recipient_name: str,
    course_name: str,
    event_date: str,
    force_failure: bool = False,
) -> None:
    """Render a single certificate PDF from the predefined template."""
    if force_failure:
        raise CertificateGenerationError("Simulated generation failure")

    if recipient_name.strip().upper() == "FAIL GENERATION":
        raise CertificateGenerationError("Recipient flagged for generation failure")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    width, height = landscape(letter)
    c = canvas.Canvas(str(output_path), pagesize=(width, height))

    border_margin = 0.5 * inch
    c.setStrokeColor(colors.HexColor("#1a365d"))
    c.setLineWidth(3)
    c.rect(border_margin, border_margin, width - 2 * border_margin, height - 2 * border_margin)

    c.setFillColor(colors.HexColor("#1a365d"))
    c.setFont("Helvetica-Bold", 36)
    c.drawCentredString(width / 2, height - 1.5 * inch, settings.template_title)

    c.setFont("Helvetica", 18)
    c.setFillColor(colors.black)
    c.drawCentredString(width / 2, height - 2.2 * inch, settings.template_subtitle)

    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(width / 2, height / 2 + 0.2 * inch, recipient_name)

    c.setFont("Helvetica", 16)
    c.drawCentredString(width / 2, height / 2 - 0.6 * inch, f"has successfully completed")
    c.drawCentredString(width / 2, height / 2 - 1.0 * inch, course_name)

    c.setFont("Helvetica-Oblique", 14)
    c.drawCentredString(width / 2, 1.5 * inch, f"Date: {event_date}")

    c.showPage()
    c.save()
