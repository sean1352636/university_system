"""Write a generated financial aid report to disk as CSV, text or PDF.

Lifted from the admin portal's report-export mixin so the CLI can export the
same reports to the same formats. The GUI keeps only the file-chooser.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

REPORT_FORMATS: tuple[str, ...] = ("csv", "txt", "pdf")


def default_report_filename(filename_base: str, fmt: str) -> str:
    """``<base>_<timestamp>.<fmt>`` — the name the GUI pre-fills in its dialog."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{filename_base}_{timestamp}.{fmt}"


def _write_csv(report_text: str, path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        for line in report_text.split("\n"):
            writer.writerow([line])


def _write_txt(report_text: str, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(report_text)


def _write_pdf(report_text: str, path: Path) -> None:
    # reportlab is an optional dependency; the ImportError surfaces to the caller.
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    doc = SimpleDocTemplate(
        str(path), pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18
    )
    style = ParagraphStyle(
        "ReportStyle", parent=getSampleStyleSheet()["Normal"], fontName="Courier",
        fontSize=9, leading=12, alignment=TA_LEFT, spaceAfter=6,
    )
    story = []
    for line in report_text.split("\n"):
        if line.strip():
            safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(safe, style))
        else:
            story.append(Spacer(1, 0.1 * inch))
    doc.build(story)


_WRITERS = {"csv": _write_csv, "txt": _write_txt, "pdf": _write_pdf}


def write_report_file(report_text: str, path: str | Path, fmt: str | None = None) -> Path:
    """Save ``report_text`` at ``path``; the format comes from ``fmt`` or the suffix.

    Raises ``ValueError`` for an unknown format and ``ImportError`` when PDF is
    requested without reportlab installed.
    """
    target = Path(path)
    chosen = (fmt or target.suffix.lstrip(".") or "txt").lower()
    writer = _WRITERS.get(chosen)
    if writer is None:
        raise ValueError(f"Unsupported report format {chosen!r}; use one of {REPORT_FORMATS}")
    if not target.suffix:
        target = target.with_suffix(f".{chosen}")
    target.parent.mkdir(parents=True, exist_ok=True)
    writer(report_text, target)
    return target


__all__ = ["REPORT_FORMATS", "default_report_filename", "write_report_file"]
