"""KS5 Destinations data layer.

One table: ``dest_records`` — keyed by ``(student_id, checkpoint)``.

The DfE KS5 destination measure expects three captures per leaver:

* **LEAVING**     — destination confirmed at the point of leaving
                    sixth form (the statutory entry).
* **PLUS_6**      — follow-up six months after leaving.
* **PLUS_12**     — follow-up twelve months after leaving (the
                    sustained-destination measure).

Each row records the destination type (HE / FE / Apprenticeship /
Employment / Training / Gap Year / NEET / Unknown), institution or
employer name, course or role, study level, salary band, when and
how it was confirmed, and free-text notes.

Cascade: deleting a student wipes their destination records.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.DESTINATIONS_DB

CHECKPOINTS: tuple[str, ...] = (
    "LEAVING", "PLUS_6", "PLUS_12",
)
CHECKPOINT_LABELS: dict[str, str] = {
    "LEAVING": "At point of leaving",
    "PLUS_6":  "+6 months",
    "PLUS_12": "+12 months",
}
DEFAULT_CHECKPOINT: str = "LEAVING"

DESTINATION_TYPES: tuple[str, ...] = (
    "Higher Education",
    "Further Education",
    "Apprenticeship",
    "Employment",
    "Training",
    "Gap Year",
    "NEET",
    "Unknown",
)
DEFAULT_DESTINATION_TYPE: str = "Unknown"

STUDY_LEVELS: tuple[str, ...] = (
    "Foundation", "Level 3", "Level 4", "Level 5", "Level 6",
    "Level 7", "Other",
)

CONFIRMED_VIA: tuple[str, ...] = (
    "UCAS Track", "Email", "Phone", "Parent", "Survey",
    "In Person", "Other",
)

SALARY_BANDS: tuple[str, ...] = (
    "Under £15k", "£15k–£20k", "£20k–£25k", "£25k–£30k",
    "£30k+", "Unpaid", "Not disclosed",
)

# DfE-style buckets used for the "is this destination sustained?"
# headline measure: HE/FE/Apprenticeship/Employment/Training count as
# positive sustained destinations; Gap Year is neutral; NEET/Unknown
# count negatively.
POSITIVE_TYPES = frozenset({
    "Higher Education", "Further Education", "Apprenticeship",
    "Employment", "Training",
})

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dest_records (
    record_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id         TEXT NOT NULL,
    checkpoint         TEXT NOT NULL,
    destination_type   TEXT NOT NULL DEFAULT 'Unknown',
    institution        TEXT,
    course             TEXT,
    study_level        TEXT,
    employer           TEXT,
    role               TEXT,
    salary_band        TEXT,
    start_date         TEXT,
    confirmed_via      TEXT,
    confirmed_date     TEXT,
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    UNIQUE (student_id, checkpoint),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dest_student     ON dest_records(student_id);
CREATE INDEX IF NOT EXISTS idx_dest_checkpoint  ON dest_records(checkpoint);
CREATE INDEX IF NOT EXISTS idx_dest_type        ON dest_records(destination_type);
"""


@dataclass
class DestinationRecord:
    record_id: int
    student_id: str
    checkpoint: str
    destination_type: str
    institution: str | None
    course: str | None
    study_level: str | None
    employer: str | None
    role: str | None
    salary_band: str | None
    start_date: str | None
    confirmed_via: str | None
    confirmed_date: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_positive(self) -> bool:
        return self.destination_type in POSITIVE_TYPES

    def display_target(self) -> str:
        """One-line description of where the student went."""
        bits: list[str] = []
        if self.institution:
            bits.append(self.institution)
        if self.course:
            bits.append(self.course)
        if self.employer:
            bits.append(self.employer)
        if self.role:
            bits.append(self.role)
        return " · ".join(bits) or "—"


@dataclass
class DestinationRow:
    record: DestinationRecord
    student_name: str


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Destinations schema ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row) -> DestinationRecord:
    return DestinationRecord(
        record_id=r["record_id"], student_id=r["student_id"],
        checkpoint=r["checkpoint"],
        destination_type=r["destination_type"],
        institution=r["institution"], course=r["course"],
        study_level=r["study_level"],
        employer=r["employer"], role=r["role"],
        salary_band=r["salary_band"], start_date=r["start_date"],
        confirmed_via=r["confirmed_via"],
        confirmed_date=r["confirmed_date"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for invalid destinations input."""


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real calendar date") from None
    return s


def _validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    sid = _require(data.get("student_id"), "Student ID").strip()
    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    out["student_id"] = sid

    cp = (data.get("checkpoint") or DEFAULT_CHECKPOINT).strip().upper()
    if cp not in CHECKPOINTS:
        raise ValidationError(
            f"Checkpoint must be one of: {', '.join(CHECKPOINTS)}")
    out["checkpoint"] = cp

    dtype = (data.get("destination_type") or DEFAULT_DESTINATION_TYPE).strip()
    if dtype not in DESTINATION_TYPES:
        raise ValidationError(
            f"Destination type must be one of: {', '.join(DESTINATION_TYPES)}")
    out["destination_type"] = dtype

    level = (data.get("study_level") or "").strip() or None
    if level is not None and level not in STUDY_LEVELS:
        raise ValidationError(
            f"Study level must be one of: {', '.join(STUDY_LEVELS)}")
    out["study_level"] = level

    via = (data.get("confirmed_via") or "").strip() or None
    if via is not None and via not in CONFIRMED_VIA:
        raise ValidationError(
            f"Confirmed via must be one of: {', '.join(CONFIRMED_VIA)}")
    out["confirmed_via"] = via

    salary = (data.get("salary_band") or "").strip() or None
    if salary is not None and salary not in SALARY_BANDS:
        raise ValidationError(
            f"Salary band must be one of: {', '.join(SALARY_BANDS)}")
    out["salary_band"] = salary

    out["start_date"]     = _validate_date(
        data.get("start_date"), "Start date")
    out["confirmed_date"] = _validate_date(
        data.get("confirmed_date"), "Confirmed date")
    out["institution"] = (data.get("institution") or "").strip() or None
    out["course"]      = (data.get("course") or "").strip() or None
    out["employer"]    = (data.get("employer") or "").strip() or None
    out["role"]        = (data.get("role") or "").strip() or None
    out["notes"]       = (data.get("notes") or "").strip() or None
    return out


# ── CRUD ─────────────────────────────────────────────────────────

def save_record(data: dict[str, Any]) -> DestinationRecord:
    """Upsert keyed on (student_id, checkpoint)."""
    init_db()
    p = _validate_payload(data)
    with _connect() as conn:
        conn.execute(
            """INSERT INTO dest_records
                   (student_id, checkpoint, destination_type,
                    institution, course, study_level,
                    employer, role, salary_band, start_date,
                    confirmed_via, confirmed_date, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))
               ON CONFLICT(student_id, checkpoint) DO UPDATE SET
                   destination_type = excluded.destination_type,
                   institution      = excluded.institution,
                   course           = excluded.course,
                   study_level      = excluded.study_level,
                   employer         = excluded.employer,
                   role             = excluded.role,
                   salary_band      = excluded.salary_band,
                   start_date       = excluded.start_date,
                   confirmed_via    = excluded.confirmed_via,
                   confirmed_date   = excluded.confirmed_date,
                   notes            = excluded.notes,
                   updated_at       = datetime('now')""",
            (p["student_id"], p["checkpoint"], p["destination_type"],
             p["institution"], p["course"], p["study_level"],
             p["employer"], p["role"], p["salary_band"],
             p["start_date"], p["confirmed_via"],
             p["confirmed_date"], p["notes"]),
        )
        conn.commit()
        r = conn.execute(
            "SELECT * FROM dest_records "
            "WHERE student_id = ? AND checkpoint = ?",
            (p["student_id"], p["checkpoint"]),
        ).fetchone()
    assert r is not None
    out = _row(r)
    logger.info(
        "Saved destination for %s @ %s = %s (%s)",
        out.student_id, out.checkpoint, out.destination_type,
        out.display_target(),
    )
    return out


def get_record(record_id: int) -> DestinationRecord | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM dest_records WHERE record_id = ?",
            (record_id,),
        ).fetchone()
        return _row(r) if r else None


def get_record_for(student_id: str,
                    checkpoint: str) -> DestinationRecord | None:
    init_db()
    if checkpoint not in CHECKPOINTS:
        raise ValidationError(
            f"Checkpoint must be one of: {', '.join(CHECKPOINTS)}")
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM dest_records "
            "WHERE student_id = ? AND checkpoint = ?",
            (student_id.strip(), checkpoint),
        ).fetchone()
        return _row(r) if r else None


def records_for_student(student_id: str) -> list[DestinationRecord]:
    init_db()
    order_case = " ".join(
        f"WHEN '{c}' THEN {i}" for i, c in enumerate(CHECKPOINTS))
    sql = (
        "SELECT * FROM dest_records WHERE student_id = ? "
        f"ORDER BY CASE checkpoint {order_case} END"
    )
    with _connect() as conn:
        return [_row(r)
                for r in conn.execute(sql, (student_id.strip(),)).fetchall()]


def list_records(
    *,
    checkpoint: str | None = None,
    destination_type: str | None = None,
    student_id: str | None = None,
) -> list[DestinationRecord]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if checkpoint:
        if checkpoint not in CHECKPOINTS:
            raise ValidationError(
                f"Checkpoint must be one of: {', '.join(CHECKPOINTS)}")
        clauses.append("checkpoint = ?")
        args.append(checkpoint)
    if destination_type:
        if destination_type not in DESTINATION_TYPES:
            raise ValidationError(
                f"Destination type must be one of: {', '.join(DESTINATION_TYPES)}")
        clauses.append("destination_type = ?")
        args.append(destination_type)
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM dest_records {where} "
           "ORDER BY student_id, checkpoint")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def list_records_with_detail(**kwargs) -> list[DestinationRow]:
    rows = list_records(**kwargs)
    if not rows:
        return []
    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name for s in _students.list_students()}
    return [DestinationRow(record=r,
                            student_name=names.get(r.student_id, "(unknown)"))
            for r in rows]


def delete_record(record_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM dest_records WHERE record_id = ?",
            (record_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted destination record #%d", record_id)
            return True
        logger.warning("delete_record: unknown id %d", record_id)
        return False


def students_missing_at(checkpoint: str) -> list[str]:
    """Return student-ids of leavers (any student in the students
    table) without a destination record at ``checkpoint``."""
    init_db()
    if checkpoint not in CHECKPOINTS:
        raise ValidationError(
            f"Checkpoint must be one of: {', '.join(CHECKPOINTS)}")
    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    have: set[str] = set()
    with _connect() as conn:
        for r in conn.execute(
                "SELECT student_id FROM dest_records WHERE checkpoint = ?",
                (checkpoint,)).fetchall():
            have.add(r["student_id"])
    return [s.student_id for s in _students.list_students()
            if s.student_id not in have]


# ── Summary ──────────────────────────────────────────────────────

@dataclass
class DestinationsSummary:
    total_records: int
    by_checkpoint: dict[str, int]
    by_destination_type: dict[str, int]
    by_level_at_leaving: dict[str, int]  # HE study levels at LEAVING
    positive_at_leaving: int
    positive_at_plus_6: int
    positive_at_plus_12: int
    students_with_leaving: int
    students_missing_leaving: int


def summary() -> DestinationsSummary:
    init_db()
    records = list_records()
    by_checkpoint = {c: 0 for c in CHECKPOINTS}
    by_type = {d: 0 for d in DESTINATION_TYPES}
    by_level = {l: 0 for l in STUDY_LEVELS}
    pos = {c: 0 for c in CHECKPOINTS}
    students_at_leaving: set[str] = set()
    for r in records:
        by_checkpoint[r.checkpoint] += 1
        by_type[r.destination_type] = by_type.get(
            r.destination_type, 0) + 1
        if r.checkpoint == "LEAVING" and r.study_level:
            by_level[r.study_level] = by_level.get(r.study_level, 0) + 1
        if r.checkpoint == "LEAVING":
            students_at_leaving.add(r.student_id)
        if r.is_positive:
            pos[r.checkpoint] += 1
    missing = len(students_missing_at("LEAVING"))
    return DestinationsSummary(
        total_records=len(records),
        by_checkpoint=by_checkpoint,
        by_destination_type=by_type,
        by_level_at_leaving=by_level,
        positive_at_leaving=pos["LEAVING"],
        positive_at_plus_6=pos["PLUS_6"],
        positive_at_plus_12=pos["PLUS_12"],
        students_with_leaving=len(students_at_leaving),
        students_missing_leaving=missing,
    )
