"""Special consideration applications.

A special consideration application asks the board to adjust a
candidate's marks for one component because of illness, bereavement
or another circumstance at the time of the exam. One row per candidate
per component; the board's outcome is recorded when it comes back.

JCQ: applications must reach the board within
:data:`SUBMIT_WITHIN_DAYS` days of the last component in the subject;
late ones are flagged.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.domain.assessment.exams_office import store
from education_system.systems.sixth_form.domain.assessment.exams_office.store import (
    ValidationError,
)

logger = logging.getLogger(__name__)

# JCQ: within seven days of the last assessment in the subject.
SUBMIT_WITHIN_DAYS: int = 7

REASON_CATEGORIES: tuple[str, ...] = (
    "Illness (temporary)",
    "Long-term illness or condition",
    "Injury",
    "Bereavement",
    "Domestic crisis",
    "Serious disturbance during the exam",
    "Accident or incident on the day",
    "Absent with acceptable reason (enhanced grading)",
    "Other",
)

STATUSES: tuple[str, ...] = (
    "Draft", "Submitted", "Outcome received", "Withdrawn")

OUTCOMES: tuple[str, ...] = (
    "Pending", "Allowance applied", "No allowance (no effect on grade)",
    "Not eligible", "Enhanced grade awarded", "Rejected")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS exams_special_consideration (
    sc_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id       TEXT NOT NULL,
    entry_id         INTEGER,
    exam_board       TEXT,
    component_code   TEXT NOT NULL,
    season           TEXT NOT NULL,
    year             INTEGER NOT NULL,
    reason_category  TEXT NOT NULL,
    details          TEXT,
    evidence         TEXT,
    incident_date    TEXT,
    status           TEXT NOT NULL DEFAULT 'Draft',
    submitted_date   TEXT,
    submitted_by     TEXT,
    board_reference  TEXT,
    board_outcome    TEXT NOT NULL DEFAULT 'Pending',
    outcome_date     TEXT,
    allowance_pct    REAL,
    notes            TEXT,
    created_by       TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    UNIQUE(student_id, component_code, season, year),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (entry_id) REFERENCES exam_entries(entry_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_exams_sc_series ON exams_special_consideration(year, season);
"""


def init_db() -> None:
    store.ensure("special_consideration", _SCHEMA)


@dataclass
class Application:
    sc_id: int
    student_id: str
    entry_id: int | None
    exam_board: str | None
    component_code: str
    season: str
    year: int
    reason_category: str
    details: str | None
    evidence: str | None
    incident_date: str | None
    status: str
    submitted_date: str | None
    submitted_by: str | None
    board_reference: str | None
    board_outcome: str
    outcome_date: str | None
    allowance_pct: float | None
    notes: str | None
    created_by: str | None
    created_at: str | None
    updated_at: str | None
    full_name: str | None = None
    deadline: str | None = None

    @property
    def late(self) -> bool:
        if not self.deadline:
            return False
        when = self.submitted_date or (store.today() if self.status == "Draft" else None)
        return bool(when and when > self.deadline)


_FIELDS = ("sc_id", "student_id", "entry_id", "exam_board", "component_code",
           "season", "year", "reason_category", "details", "evidence",
           "incident_date", "status", "submitted_date", "submitted_by",
           "board_reference", "board_outcome", "outcome_date", "allowance_pct",
           "notes", "created_by", "created_at", "updated_at")


def deadline_for(student_id: str, component_code: str, season: str, year: int) -> str | None:
    """Last timetabled paper in the component's subject + the JCQ window."""
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _entries,
    )
    from education_system.systems.sixth_form.domain.assessment.exams_office import (
        timetable,
    )
    entries = _entries.list_entries(student_id=student_id, season=season, year=int(year))
    entry = next((e for e in entries if e.paper_code == component_code), None)
    if entry is None:
        return None
    same_subject = {e.paper_code for e in entries if e.subject == entry.subject}
    dates = [p.exam_date for p in timetable.list_papers(season=season, year=year)
             if p.component_code in same_subject]
    if not dates:
        return None
    last = _dt.date.fromisoformat(max(dates))
    return (last + _dt.timedelta(days=SUBMIT_WITHIN_DAYS)).isoformat()


def _app(r, names: dict[str, str] | None = None) -> Application:
    a = Application(**{k: r[k] for k in _FIELDS})
    a.full_name = (names or {}).get(a.student_id)
    try:
        a.deadline = deadline_for(a.student_id, a.component_code, a.season, a.year)
    except Exception:
        logger.exception("Special consideration deadline lookup failed")
    return a


def save_application(data: dict[str, Any], *, sc_id: int | None = None) -> Application:
    init_db()
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _entries,
    )
    sid = store.student(data.get("student_id"))
    season, year = store.season_year(data.get("season"), data.get("year"))
    comp = (store.text(data.get("component_code"), "Component code", limit=24,
                       required=True) or "").upper()
    entry = next((e for e in _entries.list_entries(student_id=sid, season=season, year=year)
                  if e.paper_code == comp), None)
    if entry is None:
        raise ValidationError(f"{sid} has no {season} {year} entry for {comp}")
    status = store.choice(data.get("status"), "Status", STATUSES, default="Draft")
    outcome = store.choice(data.get("board_outcome"), "Board outcome", OUTCOMES,
                           default="Pending")
    submitted = store.date(data.get("submitted_date"), "Submitted date")
    if status in ("Submitted", "Outcome received") and not submitted:
        submitted = store.today()
    outcome_date = store.date(data.get("outcome_date"), "Outcome date")
    if outcome != "Pending":
        status = "Outcome received" if status != "Withdrawn" else status
        outcome_date = outcome_date or store.today()
    allowance = data.get("allowance_pct")
    allowance_v = None
    if allowance not in (None, ""):
        try:
            allowance_v = round(float(allowance), 1)
        except (TypeError, ValueError):
            raise ValidationError("Allowance % must be a number") from None
        if not 0 <= allowance_v <= 5:
            raise ValidationError("JCQ allowances run from 0% to 5%")
    vals = (sid, entry.entry_id, entry.exam_board, comp, season, year,
            store.choice(data.get("reason_category"), "Reason category", REASON_CATEGORIES),
            store.text(data.get("details"), "Details", limit=2000),
            store.text(data.get("evidence"), "Evidence", limit=1000),
            store.date(data.get("incident_date"), "Incident date"),
            status, submitted,
            store.text(data.get("submitted_by"), "Submitted by", limit=120)
            or (store.actor() if submitted else None),
            store.text(data.get("board_reference"), "Board reference", limit=60),
            outcome, outcome_date, allowance_v,
            store.text(data.get("notes"), "Notes", limit=1000))
    try:
        with store.connect() as conn:
            if sc_id is None:
                cur = conn.execute(
                    """INSERT INTO exams_special_consideration
                           (student_id, entry_id, exam_board, component_code, season,
                            year, reason_category, details, evidence, incident_date,
                            status, submitted_date, submitted_by, board_reference,
                            board_outcome, outcome_date, allowance_pct, notes,
                            created_by)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (*vals, store.actor()))
                sc_id = int(cur.lastrowid)
            else:
                conn.execute(
                    """UPDATE exams_special_consideration SET
                           student_id = ?, entry_id = ?, exam_board = ?,
                           component_code = ?, season = ?, year = ?,
                           reason_category = ?, details = ?, evidence = ?,
                           incident_date = ?, status = ?, submitted_date = ?,
                           submitted_by = ?, board_reference = ?, board_outcome = ?,
                           outcome_date = ?, allowance_pct = ?, notes = ?,
                           updated_at = datetime('now')
                       WHERE sc_id = ?""", (*vals, sc_id))
            conn.commit()
    except store.IntegrityError as e:
        raise ValidationError(
            f"{sid} already has a special consideration application for {comp}") from e
    out = get_application(sc_id)
    assert out is not None
    logger.info("Saved special consideration #%d (%s %s)", sc_id, sid, comp)
    return out


def get_application(sc_id: int) -> Application | None:
    init_db()
    with store.connect() as conn:
        r = conn.execute("SELECT * FROM exams_special_consideration WHERE sc_id = ?",
                         (sc_id,)).fetchone()
    return _app(r, store.student_names()) if r else None


def list_applications(*, season: str | None = None, year: int | None = None,
                      student_id: str | None = None,
                      status: str | None = None) -> list[Application]:
    init_db()
    clauses, args = [], []
    for col, val in (("season", season), ("student_id", student_id), ("status", status)):
        if val:
            clauses.append(f"{col} = ?")
            args.append(val)
    if year is not None:
        clauses.append("year = ?")
        args.append(int(year))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    names = store.student_names()
    with store.connect() as conn:
        rows = conn.execute(f"SELECT * FROM exams_special_consideration {where} "
                            "ORDER BY year DESC, season, student_id, component_code",
                            args).fetchall()
    return [_app(r, names) for r in rows]


def delete_application(sc_id: int) -> bool:
    init_db()
    with store.connect() as conn:
        cur = conn.execute("DELETE FROM exams_special_consideration WHERE sc_id = ?",
                           (sc_id,))
        conn.commit()
    return bool(cur.rowcount)
