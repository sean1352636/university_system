"""Formal letters as PDF files (Support to Study outcomes, DSA, PEEPs).

A letter is written to ``var/data/university/exports/pdf/wellbeing/`` and the
path returned; the caller records it against its case. Nothing is sent: the
letter is a file for staff to give or e-mail to the student.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path


def letters_dir() -> Path:
    from education_system.paths import UNIVERSITY_EXPORTS_PDF_DIR
    path = Path(UNIVERSITY_EXPORTS_PDF_DIR) / "wellbeing"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe(text) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(text or "")).strip("_")[:60] or "letter"


def write_letter(*, reference: str, recipient: str, subject: str, paragraphs: list[str],
                 signatory: str, address_lines: list[str] | None = None,
                 out_dir: Path | None = None) -> str:
    """Write a one-to-two page letter; returns the PDF's path.

    Raises ``ValueError`` when reportlab is not installed (the screen shows
    it as it is)."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError:
        raise ValueError("Letters need the reportlab package (pip install reportlab).") \
            from None
    from xml.sax.saxutils import escape

    folder = out_dir or letters_dir()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = Path(folder) / f"{_safe(reference)}_{stamp}.pdf"
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    story = [Paragraph("<b>University Student Services</b>", styles["Title"]),
             Spacer(1, 6 * mm),
             Paragraph(date.today().strftime("%d %B %Y"), body),
             Paragraph(f"Reference: {escape(reference)}", body),
             Spacer(1, 4 * mm),
             Paragraph(escape(recipient), body)]
    for line in address_lines or []:
        story.append(Paragraph(escape(line), body))
    story += [Spacer(1, 6 * mm), Paragraph(f"<b>{escape(subject)}</b>", styles["Heading3"]),
              Spacer(1, 2 * mm)]
    for para in paragraphs:
        for chunk in str(para or "").split("\n\n"):
            if chunk.strip():
                story.append(Paragraph(escape(chunk.strip()).replace("\n", "<br/>"), body))
                story.append(Spacer(1, 3 * mm))
    story += [Spacer(1, 6 * mm), Paragraph("Yours sincerely,", body), Spacer(1, 10 * mm),
              Paragraph(escape(signatory), body)]
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
                      topMargin=20 * mm, bottomMargin=20 * mm,
                      title=subject).build(story)
    return str(path)
