"""Term planning and calendar import helpers for the Sixth Form academic year.

Pure date logic (no screens): rolling a year forward, classifying terms,
suggesting splits and half-terms, UK bank holidays and a minimal ICS reader.
Used by the Academic Year window, its CLI and the argv entry point; moved
here from the window's tab modules so the domain layer need not import them.
"""
from __future__ import annotations

import datetime as _dt

from education_system.systems.sixth_form.domain.academics.academic_year.academic_year import (
    AcademicYear,
    Term,
)


def _shift_iso(date_iso: str, days: int) -> str:
    return (_dt.date.fromisoformat(date_iso)
             + _dt.timedelta(days=days)).isoformat()


def _bump_year_name(name: str) -> str:
    """Best-effort: bump trailing year tokens in a name like '2025/26'
    → '2026/27'. Falls back to appending ' (copy)' if no pattern matches."""
    import re as _re
    m = _re.search(r"(\d{4})\s*/\s*(\d{2,4})\s*$", name)
    if m:
        y1 = int(m.group(1)) + 1
        g2 = m.group(2)
        if len(g2) == 2:
            y2 = (int(g2) + 1) % 100
            tail = f"{y1}/{y2:02d}"
        else:
            tail = f"{y1}/{int(g2) + 1}"
        return name[:m.start()] + tail
    m = _re.search(r"(\d{4})\s*-\s*(\d{2,4})\s*$", name)
    if m:
        y1 = int(m.group(1)) + 1
        g2 = m.group(2)
        if len(g2) == 2:
            y2 = (int(g2) + 1) % 100
            tail = f"{y1}-{y2:02d}"
        else:
            tail = f"{y1}-{int(g2) + 1}"
        return name[:m.start()] + tail
    m = _re.search(r"(\d{4})\s*$", name)
    if m:
        return name[:m.start()] + str(int(m.group(1)) + 1)
    return f"{name} (copy)"[:32]


def _iso(d: _dt.date) -> str:
    return d.isoformat()


def _classify_terms(year: AcademicYear,
                     terms: list[Term]) -> dict[int, str]:
    """Return {term_id: status} where status is 'ok', 'outside',
    'overlap', or 'gap-before'. 'gap-before' means a gap exists between
    the previous term's end and this term's start (info, not an error)."""
    out: dict[int, str] = {}
    ordered = sorted(terms, key=lambda t: t.start_date)
    prev_end: str | None = None
    for t in ordered:
        if (t.start_date < year.start_date
                or t.end_date > year.end_date
                or t.end_date < t.start_date):
            out[t.term_id] = "outside"
        elif prev_end is not None and t.start_date <= prev_end:
            out[t.term_id] = "overlap"
        elif prev_end is not None:
            try:
                gap = (_dt.date.fromisoformat(t.start_date)
                       - _dt.date.fromisoformat(prev_end)).days
                out[t.term_id] = "gap-before" if gap > 14 else "ok"
            except ValueError:
                out[t.term_id] = "ok"
        else:
            out[t.term_id] = "ok"
        if t.end_date > (prev_end or ""):
            prev_end = t.end_date
    return out


_STATUS_BADGES: dict[str, str] = {
    "ok":         "✓ ok",
    "outside":    "✗ outside year",
    "overlap":    "⚠ overlaps prev",
    "gap-before": "⚠ gap before",
}


def _split_even_three(year: AcademicYear) -> list[tuple[str, str, str]]:
    """Return [(name, start_iso, end_iso)] for Autumn/Spring/Summer
    splitting the year roughly into thirds on Mondays/Fridays."""
    start = _dt.date.fromisoformat(year.start_date)
    end = _dt.date.fromisoformat(year.end_date)
    total = (end - start).days
    third = total // 3
    a_end = start + _dt.timedelta(days=third)
    s_start = a_end + _dt.timedelta(days=1)
    s_end = start + _dt.timedelta(days=2 * third)
    su_start = s_end + _dt.timedelta(days=1)
    return [
        ("Autumn", _iso(start),    _iso(a_end)),
        ("Spring", _iso(s_start), _iso(s_end)),
        ("Summer", _iso(su_start), _iso(end)),
    ]


def _suggest_halfterms(year_id: int, terms: list[Term]
                        ) -> list[tuple[str, str, str]]:
    """For each whole-term name (Autumn/Spring/Summer), suggest a
    week-long half-term break starting at the midpoint Monday.
    Returns [(name, start_iso, end_iso)] — caller filters existing."""
    out: list[tuple[str, str, str]] = []
    for t in terms:
        if t.name not in ("Autumn", "Spring", "Summer"):
            continue
        try:
            s = _dt.date.fromisoformat(t.start_date)
            e = _dt.date.fromisoformat(t.end_date)
        except ValueError:
            continue
        mid = s + (e - s) // 2
        # Snap back to Monday
        mid -= _dt.timedelta(days=mid.weekday())
        end = mid + _dt.timedelta(days=4)  # Mon..Fri
        if mid < s or end > e:
            continue
        out.append((f"{t.name} Half-Term", _iso(mid), _iso(end)))
    return out


def _uk_bank_holidays(start: _dt.date, end: _dt.date
                       ) -> list[tuple[str, str]]:
    """Return [(name, iso_date)] for UK England & Wales bank holidays
    falling in [start, end]. Hard-coded table — easier than depending
    on an external feed."""
    table: dict[int, list[tuple[str, str]]] = {
        2024: [("New Year's Day", "2024-01-01"),
               ("Good Friday", "2024-03-29"),
               ("Easter Monday", "2024-04-01"),
               ("Early May Bank Holiday", "2024-05-06"),
               ("Spring Bank Holiday", "2024-05-27"),
               ("Summer Bank Holiday", "2024-08-26"),
               ("Christmas Day", "2024-12-25"),
               ("Boxing Day", "2024-12-26")],
        2025: [("New Year's Day", "2025-01-01"),
               ("Good Friday", "2025-04-18"),
               ("Easter Monday", "2025-04-21"),
               ("Early May Bank Holiday", "2025-05-05"),
               ("Spring Bank Holiday", "2025-05-26"),
               ("Summer Bank Holiday", "2025-08-25"),
               ("Christmas Day", "2025-12-25"),
               ("Boxing Day", "2025-12-26")],
        2026: [("New Year's Day", "2026-01-01"),
               ("Good Friday", "2026-04-03"),
               ("Easter Monday", "2026-04-06"),
               ("Early May Bank Holiday", "2026-05-04"),
               ("Spring Bank Holiday", "2026-05-25"),
               ("Summer Bank Holiday", "2026-08-31"),
               ("Christmas Day", "2026-12-25"),
               ("Boxing Day (Sub.)", "2026-12-28")],
        2027: [("New Year's Day", "2027-01-01"),
               ("Good Friday", "2027-03-26"),
               ("Easter Monday", "2027-03-29"),
               ("Early May Bank Holiday", "2027-05-03"),
               ("Spring Bank Holiday", "2027-05-31"),
               ("Summer Bank Holiday", "2027-08-30"),
               ("Christmas Day (Sub.)", "2027-12-27"),
               ("Boxing Day (Sub.)", "2027-12-28")],
    }
    out: list[tuple[str, str]] = []
    for y in range(start.year, end.year + 1):
        for name, iso in table.get(y, []):
            try:
                d = _dt.date.fromisoformat(iso)
            except ValueError:
                continue
            if start <= d <= end:
                out.append((name, iso))
    return out


def _parse_ics(text: str) -> list[tuple[str, str, str]]:
    """Minimal ICS reader. Returns [(summary, start_iso, end_iso)] from
    VEVENTs with VALUE=DATE DTSTART/DTEND. DTEND is exclusive in iCal —
    we shift it back by one day to be inclusive."""
    out: list[tuple[str, str, str]] = []
    blocks = []
    cur: list[str] = []
    inside = False
    # Unfold line continuations (lines starting with space/tab continue
    # the previous line per RFC 5545).
    raw_lines = text.splitlines()
    folded: list[str] = []
    for ln in raw_lines:
        if ln.startswith((" ", "\t")) and folded:
            folded[-1] += ln[1:]
        else:
            folded.append(ln)
    for ln in folded:
        if ln.startswith("BEGIN:VEVENT"):
            inside = True
            cur = []
        elif ln.startswith("END:VEVENT"):
            inside = False
            blocks.append(cur)
        elif inside:
            cur.append(ln)

    for block in blocks:
        summary = ""
        start = ""
        end = ""
        for ln in block:
            if ln.startswith("SUMMARY:"):
                summary = ln[len("SUMMARY:"):].strip() or "Imported"
            elif ln.startswith("DTSTART"):
                v = ln.split(":", 1)[-1].strip()
                v = v[:8]
                if len(v) == 8 and v.isdigit():
                    start = f"{v[:4]}-{v[4:6]}-{v[6:8]}"
            elif ln.startswith("DTEND"):
                v = ln.split(":", 1)[-1].strip()
                v = v[:8]
                if len(v) == 8 and v.isdigit():
                    end = f"{v[:4]}-{v[4:6]}-{v[6:8]}"
        if not start:
            continue
        if end:
            try:
                end = _shift_iso(end, -1)
            except Exception:
                end = start
        else:
            end = start
        out.append((summary or "Imported", start, end))
    return out
