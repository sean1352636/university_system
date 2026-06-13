"""Analytics & reporting helpers for the Sixth Form Academic Year.

Pure functions on top of the data layer — no UI dependencies. Each
function returns plain dicts / dataclasses suitable for CLI, API,
or GUI consumption. CSV/PDF writers are provided as convenience but
also pure (they take an open file or path).

Covers suggestion items 9-16:
* per-term teaching-days CSV
* year-over-year teaching-day delta
* 5-year week heatmap (52 cols)
* INSET-days tally + trend
* bank-holiday weekday distribution
* term-length variance check
* per-month teaching-day series (for embedding under heatmap)
* one-page year-planner PDF (text-mode fallback when reportlab is absent)
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import logging
from dataclasses import dataclass
from typing import Any
from education_system.sixthform_system.modules.domain.academics.academic_year import (
    academic_year as data,
)
from education_system.sixthform_system.modules.domain.academics.academic_year.academic_year import (
    AcademicYear,
    Break,
    Term,
)

logger = logging.getLogger(__name__)

WEEKS_PER_YEAR = 53  # ISO weeks can hit 53 in some years


# ── Per-term teaching-days CSV ────────────────────────────────────

@dataclass
class TermStat:
    year_id: int
    year_name: str
    term_id: int
    term_name: str
    calendar_days: int
    teaching_days: int
    weekends: int
    inset_days: int


def per_term_stats(year_id: int | None = None) -> list[TermStat]:
    """Stats for every term in one year (or all years if year_id=None)."""
    years = ([data.get_year(year_id)] if year_id is not None
              else data.list_years())
    out: list[TermStat] = []
    for y in years:
        if y is None:
            continue
        breaks = data.list_breaks(year_id=y.year_id)
        for t in data.list_terms(year_id=y.year_id):
            td = data.teaching_days_in(
                y.year_id, date_from=t.start_date, date_to=t.end_date)
            try:
                s = _dt.date.fromisoformat(t.start_date)
                e = _dt.date.fromisoformat(t.end_date)
            except ValueError:
                continue
            we = 0
            inset = 0
            cur, one = s, _dt.timedelta(days=1)
            while cur <= e:
                if cur.weekday() >= 5:
                    we += 1
                iso = cur.isoformat()
                for b in breaks:
                    if b.type == "INSET" and b.start_date <= iso <= b.end_date:
                        inset += 1
                        break
                cur += one
            out.append(TermStat(
                year_id=y.year_id, year_name=y.name,
                term_id=t.term_id, term_name=t.name,
                calendar_days=t.day_count,
                teaching_days=td,
                weekends=we,
                inset_days=inset,
            ))
    return out


def write_per_term_csv(path: str, stats: list[TermStat]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["year_id", "year_name", "term_id", "term_name",
                      "calendar_days", "teaching_days", "weekends",
                      "inset_days"])
        for s in stats:
            w.writerow([s.year_id, s.year_name, s.term_id, s.term_name,
                          s.calendar_days, s.teaching_days, s.weekends,
                          s.inset_days])


# ── Year-over-year delta ─────────────────────────────────────────

@dataclass
class YearDelta:
    year_id: int
    name: str
    teaching_days: int
    delta_vs_prev: int | None     # days vs prior year, None for the first
    delta_pct: float | None       # % change vs prior, None for the first


def year_over_year_deltas() -> list[YearDelta]:
    """One row per year, oldest first. ``delta_vs_prev`` is teaching-day
    change against the chronologically previous year."""
    years = sorted(data.list_years(), key=lambda y: y.start_date)
    out: list[YearDelta] = []
    prev: int | None = None
    for y in years:
        try:
            td = data.teaching_days_in(y.year_id)
        except Exception:
            td = 0
        if prev is None:
            out.append(YearDelta(y.year_id, y.name, td, None, None))
        else:
            d = td - prev
            pct = (100.0 * d / prev) if prev else 0.0
            out.append(YearDelta(y.year_id, y.name, td, d, pct))
        prev = td
    return out


# ── 52-week heatmap across N years ───────────────────────────────

def week_heatmap(years: int = 5) -> list[dict[str, Any]]:
    """Per-year list of week→teaching-day counts. Useful for a
    52×N heat-grid render."""
    rows = data.list_years()
    rows.sort(key=lambda y: y.start_date, reverse=True)
    rows = rows[:years]
    out: list[dict[str, Any]] = []
    for y in rows:
        try:
            ys = _dt.date.fromisoformat(y.start_date)
            ye = _dt.date.fromisoformat(y.end_date)
        except ValueError:
            continue
        breaks = data.list_breaks(year_id=y.year_id)
        bset: set[str] = set()
        for b in breaks:
            try:
                bs = _dt.date.fromisoformat(b.start_date)
                be = _dt.date.fromisoformat(b.end_date)
            except ValueError:
                continue
            cur, one = bs, _dt.timedelta(days=1)
            while cur <= be:
                bset.add(cur.isoformat())
                cur += one
        weeks: dict[int, int] = {}
        cur, one = ys, _dt.timedelta(days=1)
        while cur <= ye:
            if cur.weekday() < 5 and cur.isoformat() not in bset:
                iso_week = cur.isocalendar()[1]
                weeks[iso_week] = weeks.get(iso_week, 0) + 1
            cur += one
        out.append({
            "year_id":   y.year_id,
            "name":      y.name,
            "weeks":     [weeks.get(w, 0) for w in range(1, WEEKS_PER_YEAR + 1)],
        })
    return out


# ── INSET tally + trend ──────────────────────────────────────────

def inset_tally() -> list[dict[str, Any]]:
    """One row per year, sorted oldest-first, with INSET-day total."""
    years = sorted(data.list_years(), key=lambda y: y.start_date)
    out = []
    for y in years:
        breaks = data.list_breaks(year_id=y.year_id, type="INSET")
        n = sum(b.day_count for b in breaks)
        out.append({"year_id": y.year_id, "name": y.name,
                      "inset_days": n})
    return out


# ── Bank holiday weekday distribution ────────────────────────────

def bank_holiday_weekday_stats(year_id: int | None = None
                                  ) -> dict[str, int]:
    """Count of bank-holiday day-of-week occurrences. Mondays are
    structurally interesting because they shift teaching-day counts
    asymmetrically across timetable cycles."""
    counts = {d: 0 for d in
                ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")}
    breaks = data.list_breaks(year_id=year_id, type="Bank Holiday")
    for b in breaks:
        try:
            cur = _dt.date.fromisoformat(b.start_date)
            end = _dt.date.fromisoformat(b.end_date)
        except ValueError:
            continue
        one = _dt.timedelta(days=1)
        while cur <= end:
            counts[cur.strftime("%a")] += 1
            cur += one
    return counts


# ── Term-length variance check ───────────────────────────────────

def term_length_variance(year_id: int,
                            tolerance_weeks: float = 2.0
                            ) -> list[dict[str, Any]]:
    """Flag whole terms (Autumn/Spring/Summer) that differ from each
    other's average by more than ``tolerance_weeks``. Half-term names
    are ignored."""
    terms = [t for t in data.list_terms(year_id=year_id)
              if t.name in ("Autumn", "Spring", "Summer")]
    if not terms:
        return []
    avg = sum(t.day_count for t in terms) / len(terms)
    tol_days = tolerance_weeks * 7
    out = []
    for t in terms:
        diff = t.day_count - avg
        out.append({
            "term_id":  t.term_id,
            "name":     t.name,
            "days":     t.day_count,
            "diff_days": round(diff, 1),
            "flagged":  abs(diff) > tol_days,
        })
    return out


# ── Per-month teaching-day series ────────────────────────────────

def per_month_teaching_days(year_id: int) -> list[dict[str, Any]]:
    year = data.get_year(year_id)
    if year is None:
        return []
    try:
        ys = _dt.date.fromisoformat(year.start_date)
        ye = _dt.date.fromisoformat(year.end_date)
    except ValueError:
        return []
    breaks = data.list_breaks(year_id=year_id)
    bset: set[str] = set()
    for b in breaks:
        try:
            bs = _dt.date.fromisoformat(b.start_date)
            be = _dt.date.fromisoformat(b.end_date)
        except ValueError:
            continue
        cur, one = bs, _dt.timedelta(days=1)
        while cur <= be:
            bset.add(cur.isoformat())
            cur += one
    months: dict[tuple[int, int], int] = {}
    cur, one = ys, _dt.timedelta(days=1)
    while cur <= ye:
        key = (cur.year, cur.month)
        if cur.weekday() < 5 and cur.isoformat() not in bset:
            months[key] = months.get(key, 0) + 1
        else:
            months.setdefault(key, 0)
        cur += one
    out = []
    for (yr, mo), n in sorted(months.items()):
        out.append({
            "year":  yr, "month": mo,
            "label": _dt.date(yr, mo, 1).strftime("%b %Y"),
            "teaching_days": n,
        })
    return out


# ── One-page year-planner PDF (or text fallback) ─────────────────

def year_planner_text(year_id: int) -> str:
    """Plain-text year planner. Used as the body of the PDF too."""
    year = data.get_year(year_id)
    if year is None:
        return "(no such year)"
    summ = data.year_summary(year_id)
    lines = []
    lines.append(f"ACADEMIC YEAR PLANNER — {year.name}")
    lines.append("=" * 60)
    lines.append(f"Range          : {year.start_date} → {year.end_date}")
    lines.append(f"Status         : {year.status}"
                  + (f"  (current)" if year.is_current else ""))
    lines.append(f"Total days     : {year.day_count}")
    lines.append(f"Teaching days  : {summ.teaching_days}")
    lines.append(f"Non-teaching   : {summ.non_teaching_days}")
    lines.append(f"Weekend days   : {summ.weekend_days}")
    lines.append("")
    lines.append(f"TERMS  ({len(summ.terms)})")
    lines.append("-" * 60)
    for t in summ.terms:
        td = data.teaching_days_in(
            year_id, date_from=t.start_date, date_to=t.end_date)
        lines.append(
            f"  #{t.term_id:>3}  {t.name:<14}  "
            f"{t.start_date} → {t.end_date}  "
            f"{t.day_count:>4}d ({td} teaching)")
    lines.append("")
    lines.append(f"BREAKS  ({len(summ.breaks)})")
    lines.append("-" * 60)
    for b in summ.breaks:
        lines.append(
            f"  #{b.break_id:>3}  {b.name[:24]:<24}  "
            f"{b.start_date} → {b.end_date}  "
            f"{b.day_count:>3}d  {b.type}")
    lines.append("")
    var = term_length_variance(year_id)
    if any(v["flagged"] for v in var):
        lines.append("WARNINGS")
        lines.append("-" * 60)
        for v in var:
            if v["flagged"]:
                lines.append(
                    f"  {v['name']} differs from mean by "
                    f"{v['diff_days']:+.0f} days")
        lines.append("")
    return "\n".join(lines)


def write_year_planner_pdf(year_id: int, path: str) -> str:
    """Write a 1-page year planner to ``path``.

    Uses reportlab if installed; otherwise writes a .txt fallback and
    returns its actual path so the caller can show the right message.
    """
    body = year_planner_text(year_id)
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as _rl_canvas
    except ImportError:
        # Fallback — write a plain text file alongside.
        txt_path = path.rsplit(".", 1)[0] + ".txt"
        with open(txt_path, "w", encoding="utf-8") as fh:
            fh.write(body)
        logger.info("reportlab missing — wrote %s instead of PDF", txt_path)
        return txt_path
    c = _rl_canvas.Canvas(path, pagesize=A4)
    c.setFont("Courier", 9)
    width, height = A4
    x = 36
    y = height - 36
    for line in body.splitlines():
        if y < 36:
            c.showPage()
            c.setFont("Courier", 9)
            y = height - 36
        c.drawString(x, y, line[:120])
        y -= 11
    c.save()
    return path
