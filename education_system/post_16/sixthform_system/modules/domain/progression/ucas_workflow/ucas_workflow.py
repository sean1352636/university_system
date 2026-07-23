"""End-to-end UCAS application workflow for the Sixth Form System.

The UCAS pieces already live in separate modules — applications,
references, personal statements, predicted grades — but nothing ties
them into a single tracked pipeline with deadlines and sign-offs. This
module is that connective layer.

For each (student, cycle year) it materialises an ordered **pipeline**
of stages:

    1. ucas_registered      (auto — from ucas_applications)
    2. predicted_grades     (auto — all A-Level subjects have a grade)
    3. statement_drafted    (auto — a personal statement exists)
    4. statement_approved   (auto — statement status Approved/Final)
    5. reference_requested  (auto — academic_references requested)
    6. reference_submitted  (auto — academic_references submitted)
    7. tutor_check          (manual sign-off)
    8. application_submitted(auto — ucas_applications submitted)

**Auto** stages are recomputed from the live domain tables every time
the pipeline is read, so they're never stale. **Manual** stages carry a
sign-off (who + when) and persist. Each stage has an optional due date
so the workflow doubles as a deadline tracker.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass
from typing import Any, Callable

from education_system.post_16.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.UCAS_WORKFLOW_DB

STATUSES: tuple[str, ...] = ("Pending", "In Progress", "Complete", "N/A")
_COMPLETE = "Complete"


@dataclass(frozen=True)
class StageDef:
    key: str
    label: str
    auto: bool


# Pipeline definition (display order). ``auto`` stages are derived from
# other modules; the rest are manual sign-offs.
STAGE_DEFS: tuple[StageDef, ...] = (
    StageDef("ucas_registered", "Registered on UCAS", True),
    StageDef("predicted_grades", "Predicted grades entered", True),
    StageDef("statement_drafted", "Personal statement drafted", True),
    StageDef("statement_approved", "Personal statement approved", True),
    StageDef("reference_requested", "Reference requested", True),
    StageDef("reference_submitted", "Reference submitted", True),
    StageDef("tutor_check", "Tutor final check", False),
    StageDef("application_submitted", "Application submitted to UCAS", True),
)
_DEF_BY_KEY = {d.key: d for d in STAGE_DEFS}


def default_cycle_year() -> int:
    """UCAS cycle a Year 13 applies in. Sept onward → next calendar year."""
    today = _dt.date.today()
    return today.year + 1 if today.month >= 9 else today.year


# ── DB plumbing ──────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_SCHEMA = """
CREATE TABLE IF NOT EXISTS ucas_workflow_stages (
    stage_row_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL,
    cycle_year    INTEGER NOT NULL,
    stage_key     TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'Pending',
    due_date      TEXT,
    signed_off_by TEXT,
    signed_off_at TEXT,
    notes         TEXT,
    updated_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(student_id, cycle_year, stage_key),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ucasw_student ON ucas_workflow_stages(student_id, cycle_year);
"""

_DB_READY = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.post_16.sixthform_system.modules.domain.students.students import students as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    _DB_READY = True
    logger.debug("UCAS-workflow schema ready at %s", DB_PATH)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


# ── Auto-derivation from sibling modules ─────────────────────────────

def _auto_status(conn: sqlite3.Connection, student_id: str, cycle_year: int,
                 key: str) -> str:
    if key == "ucas_registered":
        if _table_exists(conn, "ucas_applications"):
            r = conn.execute(
                "SELECT 1 FROM ucas_applications WHERE student_id=? AND cycle_year=?",
                (student_id, cycle_year)).fetchone()
            return _COMPLETE if r else "Pending"
        return "Pending"

    if key == "application_submitted":
        if _table_exists(conn, "ucas_applications"):
            r = conn.execute(
                "SELECT status, submitted_at FROM ucas_applications "
                "WHERE student_id=? AND cycle_year=?",
                (student_id, cycle_year)).fetchone()
            if r and (r["submitted_at"] or (r["status"] or "").lower() in ("submitted", "complete")):
                return _COMPLETE
            return "In Progress" if r else "Pending"
        return "Pending"

    if key == "predicted_grades":
        subs = conn.execute(
            "SELECT subject_1, subject_2, subject_3 FROM students WHERE student_id=?",
            (student_id,)).fetchone()
        wanted = [s for s in (subs["subject_1"], subs["subject_2"], subs["subject_3"])
                  if s] if subs else []
        if not wanted or not _table_exists(conn, "predicted_grades"):
            return "Pending"
        have = {r["subject"] for r in conn.execute(
            "SELECT subject FROM predicted_grades WHERE student_id=?", (student_id,))}
        covered = sum(1 for s in wanted if s in have)
        if covered == len(wanted):
            return _COMPLETE
        return "In Progress" if covered else "Pending"

    if key in ("statement_drafted", "statement_approved"):
        if not _table_exists(conn, "personal_statements"):
            return "Pending"
        r = conn.execute(
            "SELECT status FROM personal_statements WHERE student_id=? "
            "ORDER BY updated_at DESC LIMIT 1", (student_id,)).fetchone()
        if not r:
            return "Pending"
        if key == "statement_drafted":
            return _COMPLETE
        return _COMPLETE if (r["status"] or "").lower() in ("approved", "final", "submitted") \
            else "In Progress"

    if key in ("reference_requested", "reference_submitted"):
        if not _table_exists(conn, "academic_references"):
            return "Pending"
        r = conn.execute(
            "SELECT status, submitted_at FROM academic_references WHERE student_id=? "
            "ORDER BY updated_at DESC LIMIT 1", (student_id,)).fetchone()
        if not r:
            return "Pending"
        if key == "reference_requested":
            return _COMPLETE
        return _COMPLETE if (r["submitted_at"] or (r["status"] or "").lower() in
                             ("submitted", "complete", "sent")) else "In Progress"

    return "Pending"


# ── Pipeline operations ──────────────────────────────────────────────

def _ensure_rows(conn: sqlite3.Connection, student_id: str, cycle_year: int) -> None:
    for d in STAGE_DEFS:
        conn.execute(
            "INSERT OR IGNORE INTO ucas_workflow_stages "
            "(student_id, cycle_year, stage_key, status) VALUES (?,?,?, 'Pending')",
            (student_id, cycle_year, d.key))


def get_pipeline(student_id: str, cycle_year: int | None = None) -> dict[str, Any]:
    """Return the full pipeline for a student, syncing auto stages.

    Manual stages keep their stored status/sign-off; auto stages are
    overwritten from live data unless a user explicitly set them to
    'N/A'.
    """
    init_db()
    cycle_year = cycle_year or default_cycle_year()
    with _connect() as conn:
        srow = conn.execute(
            "SELECT first_name, last_name FROM students WHERE student_id=?",
            (student_id,)).fetchone()
        if not srow:
            raise ValueError(f"Unknown student: {student_id}")
        _ensure_rows(conn, student_id, cycle_year)
        # Sync auto stages.
        for d in STAGE_DEFS:
            if not d.auto:
                continue
            cur = conn.execute(
                "SELECT status FROM ucas_workflow_stages "
                "WHERE student_id=? AND cycle_year=? AND stage_key=?",
                (student_id, cycle_year, d.key)).fetchone()
            if cur and cur["status"] == "N/A":
                continue
            new_status = _auto_status(conn, student_id, cycle_year, d.key)
            conn.execute(
                "UPDATE ucas_workflow_stages SET status=?, updated_at=datetime('now') "
                "WHERE student_id=? AND cycle_year=? AND stage_key=?",
                (new_status, student_id, cycle_year, d.key))
        conn.commit()
        rows = {r["stage_key"]: r for r in conn.execute(
            "SELECT * FROM ucas_workflow_stages WHERE student_id=? AND cycle_year=?",
            (student_id, cycle_year))}

    stages = []
    for d in STAGE_DEFS:
        r = rows[d.key]
        stages.append({
            "key": d.key, "label": d.label, "auto": d.auto,
            "status": r["status"], "due_date": r["due_date"],
            "signed_off_by": r["signed_off_by"], "signed_off_at": r["signed_off_at"],
            "notes": r["notes"],
        })
    done = sum(1 for s in stages if s["status"] in (_COMPLETE, "N/A"))
    return {
        "student_id": student_id,
        "full_name": f"{srow['first_name']} {srow['last_name']}".strip(),
        "cycle_year": cycle_year,
        "stages": stages,
        "complete": done, "total": len(stages),
        "percent": round(100.0 * done / len(stages)),
    }


class ValidationError(ValueError):
    """Raised for invalid workflow input."""


def set_stage(student_id: str, stage_key: str, *, cycle_year: int | None = None,
              status: str | None = None, signed_off_by: str | None = None,
              due_date: str | None = None, notes: str | None = None) -> None:
    """Update a manual stage (or override an auto one to N/A).

    Auto stages may only be set to 'N/A' (to skip them) — any other
    status is recomputed on the next read, so writing it is pointless
    and rejected to avoid confusing staff.
    """
    init_db()
    cycle_year = cycle_year or default_cycle_year()
    if stage_key not in _DEF_BY_KEY:
        raise ValidationError(f"Unknown stage: {stage_key}")
    if status is not None and status not in STATUSES:
        raise ValidationError(f"Status must be one of: {', '.join(STATUSES)}")
    d = _DEF_BY_KEY[stage_key]
    if d.auto and status not in (None, "N/A", "Pending"):
        raise ValidationError(
            f"'{d.label}' is auto-derived; you can only mark it N/A to skip it.")
    if due_date:
        try:
            _dt.date.fromisoformat(due_date)
        except ValueError:
            raise ValidationError("due_date must be ISO format YYYY-MM-DD")

    signed_at = _dt.datetime.now().isoformat(timespec="seconds") \
        if (status == _COMPLETE and signed_off_by) else None
    with _connect() as conn:
        _ensure_rows(conn, student_id, cycle_year)
        sets, params = [], []
        if status is not None:
            sets.append("status=?"); params.append(status)
        if signed_off_by is not None:
            sets.append("signed_off_by=?"); params.append(signed_off_by or None)
        if signed_at is not None:
            sets.append("signed_off_at=?"); params.append(signed_at)
        if due_date is not None:
            sets.append("due_date=?"); params.append(due_date or None)
        if notes is not None:
            sets.append("notes=?"); params.append(notes or None)
        if not sets:
            return
        sets.append("updated_at=datetime('now')")
        params += [student_id, cycle_year, stage_key]
        conn.execute(
            f"UPDATE ucas_workflow_stages SET {', '.join(sets)} "
            "WHERE student_id=? AND cycle_year=? AND stage_key=?", params)
        conn.commit()


def overview(cycle_year: int | None = None, *, applicants_only: bool = True) -> list[dict[str, Any]]:
    """Per-student completion summary for the cohort, ordered by progress.

    With ``applicants_only`` (default), only students that already have a
    UCAS application row for the cycle are included — that's the natural
    applicant cohort. Otherwise every active student is shown.
    """
    init_db()
    cycle_year = cycle_year or default_cycle_year()
    with _connect() as conn:
        if applicants_only and _table_exists(conn, "ucas_applications"):
            ids = [r["student_id"] for r in conn.execute(
                "SELECT DISTINCT student_id FROM ucas_applications WHERE cycle_year=?",
                (cycle_year,))]
        else:
            ids = [r["student_id"] for r in conn.execute(
                "SELECT student_id FROM students WHERE COALESCE(status,'Active')='Active'")]
    out = []
    for sid in ids:
        try:
            p = get_pipeline(sid, cycle_year)
        except ValueError:
            continue
        next_stage = next((s["label"] for s in p["stages"]
                           if s["status"] not in (_COMPLETE, "N/A")), "All done")
        out.append({
            "student_id": sid, "full_name": p["full_name"],
            "percent": p["percent"], "complete": p["complete"],
            "total": p["total"], "next_stage": next_stage,
        })
    out.sort(key=lambda r: r["percent"])
    return out
