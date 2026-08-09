"""CSV exchange and printable sheets for the Sixth Form Calendar.

Sibling to :mod:`calendar`. Three paper-shaped jobs:

* **CSV out** (:func:`export_csv`) — the current filter set as a
  spreadsheet, because the deputy head plans September in Excel and
  no view will change that.
* **CSV in** (:func:`import_csv`) — the whole year's fixture list in
  one go. Always runs as a *dry run first*: the validate pass reads
  every row and reports per-row errors before a single write, so
  "row 47 has February 30th" is a report line, not half an import.
* **Print** (:func:`day_sheet`, :func:`term_sheet`) — the reception
  desk's day list and the staffroom wall's term-at-a-glance, as
  monospace text. Paper is a first-class interface in a college.

The CSV dialect is the obvious one: a header row of
:data:`CSV_COLUMNS`, comma-separated, quoted as needed. Excel's
re-save of our own export round-trips.
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import logging
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as core,
)

logger = logging.getLogger(__name__)

ValidationError = core.ValidationError

CSV_COLUMNS: tuple[str, ...] = (
    "title", "event_type", "start_date", "end_date", "start_time",
    "end_time", "all_day", "location", "organiser", "audience",
    "status", "capacity", "rsvp_required", "cost", "department",
    "visibility", "description", "notes",
)

_TRUTHY = {"1", "true", "yes", "y"}


@dataclass
class RowError:
    row: int                 # 1-based, counting the header as row 1
    message: str

    @property
    def label(self) -> str:
        return f"Row {self.row}: {self.message}"


@dataclass
class ImportReport:
    dry_run: bool
    valid: int = 0
    created: int = 0
    errors: list[RowError] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.errors

    @property
    def summary(self) -> str:
        mode = "dry run" if self.dry_run else "import"
        return (f"{mode}: {self.valid} valid row(s), "
                f"{self.created} created, {len(self.errors)} error(s)")


# ── CSV out ─────────────────────────────────────────────────────────

def export_csv(events: list[core.Event]) -> str:
    """The given events as CSV text, one row per event."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for e in events:
        writer.writerow([
            e.title, e.event_type, e.start_date, e.end_date,
            (e.start_time or "")[:5], (e.end_time or "")[:5],
            "yes" if e.all_day else "no",
            e.location or "", e.organiser or "", e.audience,
            e.status,
            e.capacity if e.capacity is not None else "",
            "yes" if e.rsvp_required else "no",
            f"{e.cost:.2f}" if e.cost is not None else "",
            e.department or "", e.visibility,
            e.description or "", e.notes or "",
        ])
    return buf.getvalue()


def export_filtered_csv(**filters: Any) -> str:
    """:func:`calendar.list_events` filters in, CSV text out."""
    return export_csv(core.list_events(**filters))


# ── CSV in ──────────────────────────────────────────────────────────

def _row_payload(row: dict[str, str]) -> dict[str, Any]:
    get = lambda k: (row.get(k) or "").strip()  # noqa: E731
    payload: dict[str, Any] = {
        "title": get("title"),
        "event_type": get("event_type") or core.DEFAULT_EVENT_TYPE,
        "start_date": get("start_date"),
        "end_date": get("end_date") or None,
        "start_time": get("start_time") or None,
        "end_time": get("end_time") or None,
        "all_day": get("all_day").lower() in _TRUTHY,
        "location": get("location") or None,
        "organiser": get("organiser") or None,
        "audience": get("audience") or core.DEFAULT_AUDIENCE,
        "status": get("status") or core.DEFAULT_STATUS,
        "capacity": get("capacity") or None,
        "rsvp_required": get("rsvp_required").lower() in _TRUTHY,
        "cost": get("cost") or None,
        "department": get("department") or None,
        "visibility": get("visibility") or core.DEFAULT_VISIBILITY,
        "description": get("description") or None,
        "notes": get("notes") or None,
    }
    return payload


def import_csv(text: str, *, dry_run: bool = True,
               actor: str | None = None) -> ImportReport:
    """Validate (and unless ``dry_run``, create) events from CSV.

    The intended shape is two calls: once with ``dry_run=True`` to
    get the error report in front of a human, then — only when it
    comes back clean — once with ``dry_run=False``. The write pass
    validates again anyway; a file with errors imports none of its
    rows rather than some of them.
    """
    report = ImportReport(dry_run=dry_run)
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        report.errors.append(RowError(1, "No header row"))
        return report
    unknown = [c for c in reader.fieldnames
               if c and c.strip() and c.strip() not in CSV_COLUMNS]
    if "title" not in [c.strip() for c in reader.fieldnames if c]:
        report.errors.append(RowError(
            1, "Header must include at least 'title' and "
               "'start_date'"))
        return report
    if unknown:
        report.errors.append(RowError(
            1, f"Unknown column(s): {', '.join(unknown)}"))

    payloads: list[dict[str, Any]] = []
    for i, row in enumerate(reader, start=2):
        payload = _row_payload(row)
        try:
            core._validate_payload(payload)
        except ValidationError as e:
            report.errors.append(RowError(i, str(e)))
            continue
        payloads.append(payload)
        report.valid += 1

    if dry_run or report.errors:
        return report
    for payload in payloads:
        core.create_event(payload, actor=actor)
        report.created += 1
    logger.info("CSV import: %s", report.summary)
    return report


# ── Print ───────────────────────────────────────────────────────────

def day_sheet(date_iso: str) -> str:
    """Reception's one-pager: everything happening on a date."""
    s = core._validate_date(date_iso, "Date")
    day = _dt.date.fromisoformat(s)
    rows = [e for e in core.events_on(s)
            if e.status not in ("Cancelled", "Draft")]
    lines = [
        f"{day.strftime('%A %d %B %Y')} — Events",
        "=" * 58,
    ]
    if not rows:
        lines.append("(nothing scheduled)")
    for e in rows:
        where = f"  {e.location}" if e.location else ""
        lines.append(f"{e.time_label:<13} {e.title}{where}")
        extra = []
        if e.organiser:
            extra.append(f"organiser: {e.organiser}")
        if e.audience != "All":
            extra.append(f"for: {e.audience}")
        if extra:
            lines.append(f"{'':13} ({', '.join(extra)})")
    lines.append("")
    lines.append(f"Printed {_dt.date.today().isoformat()} — "
                 "the calendar is always the latest word.")
    return "\n".join(lines)


def term_sheet(date_from: str, date_to: str, *,
               audience: str | None = None) -> str:
    """The staffroom wall: a date-grouped listing for a range."""
    df = core._validate_date(date_from, "date_from")
    dt2 = core._validate_date(date_to, "date_to")
    rows = core.list_events(date_from=df, date_to=dt2,
                            audience=audience)
    rows = [e for e in rows if e.status not in ("Cancelled", "Draft")]
    head = f"Events {df} → {dt2}"
    if audience:
        head += f" — {audience}"
    lines = [head, "=" * max(58, len(head))]
    if not rows:
        lines.append("(nothing scheduled)")
    current = None
    for e in rows:
        if e.start_date != current:
            current = e.start_date
            day = _dt.date.fromisoformat(current)
            lines.append("")
            lines.append(day.strftime("%A %d %B"))
            lines.append("-" * 24)
        where = f"  {e.location}" if e.location else ""
        span = (f" (until {e.end_date})" if e.is_multiday else "")
        lines.append(f"  {e.time_label:<13} {e.title}{where}{span}")
    return "\n".join(lines)
