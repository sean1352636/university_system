"""Completion of Procedures (CoP) letters, as the OIA expects them.

When a student has exhausted the university's internal complaints or academic
appeals procedure, the OIA's Good Practice Framework requires a Completion of
Procedures letter. The OIA's guidance lists what it must contain, and this
module produces exactly that:

* the student's name (and student number),
* the university's case reference,
* a summary of the complaint or appeal,
* the issues the university considered,
* the outcome and the date of the final decision,
* that the internal procedures are complete, and
* that the student may complain to the OIA, and the deadline to do so:
  **12 months** from the date of the letter.

The letter is rendered to PDF (reportlab) and written under the university
exports directory; nothing is sent from here. Callers record when it was issued
and may attach it to an outbox e-mail.

This module never touches the database.
"""

from __future__ import annotations

import html
import io
import re
from calendar import monthrange
from datetime import date, datetime
from pathlib import Path

#: The OIA accepts a complaint within 12 months of the CoP letter's date.
OIA_WINDOW_MONTHS = 12
OIA_WEBSITE = "www.oiahe.org.uk"
CASE_KINDS = {"appeal": "academic appeal", "complaint": "complaint"}
#: The fields the OIA's template needs; a letter missing any is refused.
REQUIRED = ("student_name", "case_ref", "case_kind", "summary", "issues", "outcome",
            "final_decision_date")


def _as_date(value, label: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"{label} must be a date (YYYY-MM-DD)") from None


def add_months(start: date, months: int) -> date:
    """``start`` plus whole months, clamped to the month's last day (29 Feb -> 28 Feb)."""
    month_index = start.month - 1 + months
    year, month = start.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(start.day, monthrange(year, month)[1]))


def oia_deadline(issued_on) -> date:
    """The last day the student may bring the complaint to the OIA."""
    return add_months(_as_date(issued_on, "Issue date"), OIA_WINDOW_MONTHS)


def build(*, student_name: str, student_id: str = "", case_ref: str, case_kind: str,
          summary: str, issues, outcome: str, final_decision_date, issued_on=None,
          issued_by: str = "", institution: str | None = None) -> dict:
    """The letter's content as a dict (validated); render it with :func:`render_pdf`."""
    if case_kind not in CASE_KINDS:
        raise ValueError(f"case_kind must be one of {', '.join(CASE_KINDS)}")
    issue_list = [str(i).strip() for i in (issues or []) if str(i).strip()] \
        if not isinstance(issues, str) else \
        [line.strip(" -•\t") for line in issues.splitlines() if line.strip(" -•\t")]
    letter = {
        "institution": institution or _institution(),
        "student_name": (student_name or "").strip(),
        "student_id": (student_id or "").strip(),
        "case_ref": (case_ref or "").strip(),
        "case_kind": case_kind,
        "summary": (summary or "").strip(),
        "issues": issue_list,
        "outcome": (outcome or "").strip(),
        "final_decision_date": _as_date(final_decision_date, "Date of final decision"),
        "issued_on": _as_date(issued_on or date.today(), "Issue date"),
        "issued_by": (issued_by or "").strip(),
    }
    missing = [k for k in REQUIRED if not letter[k]]
    if missing:
        raise ValueError("A Completion of Procedures letter needs: "
                         + ", ".join(m.replace("_", " ") for m in missing))
    if letter["final_decision_date"] > letter["issued_on"]:
        raise ValueError("The final decision cannot post-date the letter")
    letter["oia_deadline"] = oia_deadline(letter["issued_on"])
    return letter


def _institution() -> str:
    try:
        from education_system.systems.university.infrastructure.institution_settings import (
            get_institution_name,
        )
        return get_institution_name()
    except Exception:
        return "The University"


def _long(d: date) -> str:
    return f"{d.day} {d.strftime('%B %Y')}"


def paragraphs(letter: dict) -> list[tuple[str, str]]:
    """The letter body as ``(style, text)`` pairs, shared by PDF and text output."""
    kind = CASE_KINDS[letter["case_kind"]]
    who = letter["student_name"] + (f" ({letter['student_id']})" if letter["student_id"] else "")
    out = [
        ("title", "Completion of Procedures Letter"),
        ("body", f"Date of this letter: {_long(letter['issued_on'])}"),
        ("body", f"Student: {who}"),
        ("body", f"Our reference: {letter['case_ref']}"),
        ("head", f"Summary of the {kind}"),
        ("body", letter["summary"]),
        ("head", "Issues considered"),
    ]
    out += [("bullet", issue) for issue in letter["issues"]]
    out += [
        ("head", "Outcome"),
        ("body", letter["outcome"]),
        ("body", f"Date of the final decision: {_long(letter['final_decision_date'])}"),
        ("head", "Completion of internal procedures"),
        ("body", f"{letter['institution']} has now completed its internal procedures for your "
                 f"{kind}. This letter is your Completion of Procedures letter."),
        ("body", "If you are dissatisfied with the outcome you may be able to ask the Office of "
                 "the Independent Adjudicator for Higher Education (OIA) to review your "
                 f"{kind}. Further information is at {OIA_WEBSITE}."),
        ("body", "The OIA must receive your complaint form within 12 months of the date of this "
                 f"letter, that is by {_long(letter['oia_deadline'])}. Please send a copy of "
                 "this letter with your complaint form."),
    ]
    if letter["issued_by"]:
        out.append(("body", f"Issued by: {letter['issued_by']}, on behalf of "
                            f"{letter['institution']}"))
    return out


def render_text(letter: dict) -> str:
    lines = [letter["institution"], ""]
    for style, text in paragraphs(letter):
        if style == "title":
            lines += [text.upper(), ""]
        elif style == "head":
            lines += ["", text, "-" * len(text)]
        else:
            lines.append(("  - " if style == "bullet" else "") + text)
    return "\n".join(lines) + "\n"


def render_pdf(letter: dict) -> bytes:
    """The letter as PDF bytes. Raises ValueError when reportlab is missing."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError:
        raise ValueError("PDF letters need the reportlab package") from None
    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=f"Completion of Procedures "
                                                       f"{letter['case_ref']}")
    story = [Paragraph(html.escape(letter["institution"]), styles["Heading2"])]
    style_map = {"title": styles["Title"], "head": styles["Heading3"],
                 "body": styles["BodyText"], "bullet": styles["BodyText"]}
    for style, text in paragraphs(letter):
        body = html.escape(text)
        story.append(Paragraph(f"&bull; {body}" if style == "bullet" else body,
                               style_map[style]))
        if style == "body":
            story.append(Spacer(1, 4))
    doc.build(story)
    return buffer.getvalue()


def default_directory() -> Path:
    from education_system.paths import UNIVERSITY_EXPORTS_PDF_DIR
    return UNIVERSITY_EXPORTS_PDF_DIR / "completion_of_procedures"


def save_pdf(letter: dict, directory: Path | str | None = None) -> Path:
    """Write the PDF and return its path (one file per case reference)."""
    folder = Path(directory) if directory else default_directory()
    folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", letter["case_ref"])[:80] or "case"
    path = folder / f"COP-{letter['case_kind']}-{safe}.pdf"
    path.write_bytes(render_pdf(letter))
    return path


__all__ = ["OIA_WINDOW_MONTHS", "add_months", "build", "oia_deadline", "paragraphs",
           "render_pdf", "render_text", "save_pdf", "default_directory"]
