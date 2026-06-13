"""Library reporting & analytics (items 42, 44, 45, 46, 32).

Read-only aggregations over loans, books, fines and enrolments. The
``*_csv`` helpers render any of the row-dict reports to CSV text for
export.
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import logging

from education_system.sixthform_system.modules.domain.academics.library import (
    library as _lib,
    library_catalog as _catalog,
    library_fines as _fines,
)

logger = logging.getLogger(__name__)


def _today() -> _dt.date:
    return _dt.date.today()


# ── Borrowing popularity (item 42) ────────────────────────────────

def most_borrowed(*, limit: int = 10,
                  since: str | None = None) -> list[dict]:
    rows = _catalog.popular(limit=limit, since=since)
    return [{"book_id": b.book_id, "title": b.title,
             "author": b.author or "", "loans": n} for b, n in rows]


def least_borrowed(*, limit: int = 10) -> list[dict]:
    _lib.init_db()
    with _lib._connect() as conn:
        rows = conn.execute(
            "SELECT b.book_id, b.title, b.author, "
            "COUNT(l.loan_id) AS n FROM library_books b "
            "LEFT JOIN library_loans l ON l.book_id = b.book_id "
            "GROUP BY b.book_id ORDER BY n ASC, b.title LIMIT ?",
            (int(limit),)).fetchall()
    return [{"book_id": r["book_id"], "title": r["title"],
             "author": r["author"] or "", "loans": r["n"]}
            for r in rows]


def never_borrowed() -> list[dict]:
    return [{"book_id": b.book_id, "title": b.title,
             "author": b.author or ""}
            for b in _catalog.never_borrowed()]


# ── Overdue aging (item 44) ───────────────────────────────────────

def overdue_aging() -> dict[str, dict]:
    """Bucket currently-overdue active loans by how late they are."""
    buckets = {
        "1-7": {"count": 0, "loans": []},
        "8-30": {"count": 0, "loans": []},
        "30+": {"count": 0, "loans": []},
    }
    for loan in _lib.list_loans(overdue_only=True):
        days = loan.days_overdue
        key = "1-7" if days <= 7 else ("8-30" if days <= 30 else "30+")
        buckets[key]["count"] += 1
        buckets[key]["loans"].append(
            {"loan_id": loan.loan_id, "student_id": loan.student_id,
             "book_id": loan.book_id, "due_on": loan.due_on,
             "days_overdue": days})
    return buckets


# ── Borrowers by cohort (item 45) ─────────────────────────────────

def _latest_enrolment_map() -> dict[str, dict]:
    """student_id -> {year_group, tutor_group} for their most recent
    enrolment (by academic_year)."""
    _lib.init_db()
    with _lib._connect() as conn:
        try:
            rows = conn.execute(
                "SELECT student_id, year_group, tutor_group, "
                "academic_year FROM enrolments "
                "ORDER BY student_id, academic_year").fetchall()
        except Exception:
            return {}
    latest: dict[str, dict] = {}
    for r in rows:
        latest[r["student_id"]] = {
            "year_group": r["year_group"],
            "tutor_group": r["tutor_group"]}
    return latest


def _borrowers_by(field: str) -> list[dict]:
    enrol = _latest_enrolment_map()
    counts: dict[str, set] = {}
    for loan in _lib.list_loans(active_only=True):
        info = enrol.get(loan.student_id)
        key = (str(info[field]) if info and info.get(field) is not None
               else "(unknown)")
        counts.setdefault(key, set()).add(loan.student_id)
    return [{field: k, "borrowers": len(v)}
            for k, v in sorted(counts.items())]


def borrowers_by_year_group() -> list[dict]:
    return _borrowers_by("year_group")


def borrowers_by_tutor_group() -> list[dict]:
    return _borrowers_by("tutor_group")


# ── Usage trends & fines collected (item 46) ──────────────────────

def usage_trends(*, months: int = 12) -> list[dict]:
    """Loans issued per calendar month over the last ``months``."""
    _lib.init_db()
    with _lib._connect() as conn:
        rows = conn.execute(
            "SELECT substr(loaned_on, 1, 7) AS ym, "
            "COUNT(*) AS n FROM library_loans "
            "GROUP BY ym ORDER BY ym DESC LIMIT ?",
            (int(months),)).fetchall()
    return [{"month": r["ym"], "loans": r["n"]}
            for r in reversed(rows)]


def fines_collected(*, since: str | None = None) -> dict:
    """Totals of fine amounts raised / paid / waived / outstanding."""
    raised = paid = waived = outstanding = 0.0
    for f in _fines.list_fines():
        if since and (f.created_at or "") < since:
            continue
        raised += f.amount
        paid += f.amount_paid
        waived += f.amount_waived
        outstanding += f.outstanding
    return {"raised": round(raised, 2), "paid": round(paid, 2),
            "waived": round(waived, 2),
            "outstanding": round(outstanding, 2)}


# ── Subject-area gap (item 32) ────────────────────────────────────

def subject_gap_report() -> list[dict]:
    """Compare how many titles the library holds per subject against how
    many students are studying that subject, to guide purchasing.

    Book ``subject_area`` is free text and student subjects are A-Level
    names, so matching is best-effort on an exact (case-insensitive)
    name. ``students_per_title`` highlights under-served subjects."""
    _lib.init_db()
    with _lib._connect() as conn:
        book_rows = conn.execute(
            "SELECT subject_area, COUNT(*) AS n FROM library_books "
            "WHERE subject_area IS NOT NULL "
            "GROUP BY subject_area").fetchall()
        stu_rows = conn.execute(
            "SELECT subject FROM ("
            "  SELECT subject_1 AS subject FROM students "
            "  UNION ALL SELECT subject_2 FROM students "
            "  UNION ALL SELECT subject_3 FROM students) "
            "WHERE subject IS NOT NULL AND subject != ''").fetchall()
    titles = {}
    for r in book_rows:
        titles[r["subject_area"].strip().lower()] = (
            r["subject_area"], r["n"])
    students: dict[str, int] = {}
    for r in stu_rows:
        key = r["subject"].strip().lower()
        students[key] = students.get(key, 0) + 1

    keys = set(titles) | set(students)
    out = []
    for k in keys:
        label = titles.get(k, (None, 0))[0] or k.title()
        n_titles = titles.get(k, (None, 0))[1]
        n_students = students.get(k, 0)
        ratio = (round(n_students / n_titles, 1) if n_titles
                 else None)
        out.append({"subject": label, "titles": n_titles,
                    "students": n_students,
                    "students_per_title": ratio})

    def _severity(d: dict) -> float:
        # Subjects with students but no titles are the worst gap.
        if d["titles"] == 0:
            return float("inf") if d["students"] else -1.0
        return d["students_per_title"] or 0.0

    out.sort(key=_severity, reverse=True)
    return out


# ── CSV export (item 46) ──────────────────────────────────────────

def to_csv(rows: list[dict]) -> str:
    """Render a list of uniform row dicts to CSV text."""
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def export_csv(rows: list[dict], path: str) -> str:
    """Write rows to ``path`` as CSV; returns the path."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(to_csv(rows))
    logger.info("Exported %d rows to %s", len(rows), path)
    return path


# ── Dashboard (item 47) ───────────────────────────────────────────

def dashboard(*, due_soon_days: int | None = None) -> dict:
    """At-a-glance figures for the library landing screen: what needs
    actioning today plus headline totals."""
    from education_system.sixthform_system.modules.domain.academics.library import (
        library_settings as _settings,
        library_reservations as _holds,
    )
    today = _today().isoformat()
    window = (due_soon_days if due_soon_days is not None
              else int(_settings.get_setting("due_soon_days")))
    horizon = (_today() + _dt.timedelta(days=window)).isoformat()

    active = _lib.list_loans(active_only=True)
    due_soon = sum(1 for l in active if today <= l.due_on <= horizon)
    overdue = sum(1 for l in active if l.due_on < today)
    ready = _holds.list_reservations(status="Ready")
    expiring = sum(1 for r in ready
                   if r.expires_on and r.expires_on <= today)
    waiting = len(_holds.list_reservations(status="Waiting"))
    outstanding = _fines.list_fines(open_only=True)
    summ = _lib.summary()

    return {
        "active_loans": summ.active_loans,
        "overdue_loans": overdue,
        "due_soon": due_soon,
        "holds_ready": len(ready),
        "holds_expiring_today": expiring,
        "holds_waiting": waiting,
        "open_fines": len(outstanding),
        "outstanding_total": round(
            sum(f.outstanding for f in outstanding), 2),
        "total_books": summ.total_books,
        "copies_on_loan": summ.copies_on_loan,
    }
