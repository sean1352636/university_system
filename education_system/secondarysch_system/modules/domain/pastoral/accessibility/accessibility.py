"""Accessibility data layer for the Secondary School System.

One row per ``accessibility_arrangements`` entry. Captures the
reasonable-adjustment / exam-access category, who approved it, an
``exam_only`` flag distinguishing arrangements that apply only during
formal exams from those that apply day-to-day, and a status workflow
(Proposed → Active → Expired / Withdrawn).
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

ARRANGEMENT_TYPES: tuple[str, ...] = (
    "Reasonable adjustment",
    "Exam access arrangement",
    "Physical access",
    "Sensory access",
    "Communication support",
    "Medical / health",
    "Other")
DEFAULT_TYPE: str = "Reasonable adjustment"

# Common categories — schools can also enter free-text via "Other".
CATEGORIES: tuple[str, ...] = (
    "Extra time (25%)", "Extra time (50%)", "Rest breaks",
    "Word processor", "Modified papers", "Coloured overlays",
    "Reader", "Scribe", "Quiet room",
    "Prompter", "Wheelchair access / ramp",
    "Hearing loop / FM system", "Large print",
    "Assistive technology", "Sign-language support",
    "Toilet pass", "Medical break", "Other")
DEFAULT_CATEGORY: str = "Extra time (25%)"

STATUSES: tuple[str, ...] = (
    "Proposed", "Active", "Expired", "Withdrawn", "Under review")
DEFAULT_STATUS: str = "Proposed"

EVIDENCE_SOURCES: tuple[str, ...] = (
    "EHCP", "SEND assessment", "Medical letter",
    "Educational psychologist report", "JCQ Form 8",
    "Teacher recommendation", "Parent request", "Other")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accessibility_arrangements (
    arrangement_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id           TEXT NOT NULL,
    arrangement_type   TEXT NOT NULL DEFAULT 'Reasonable adjustment',
    category           TEXT NOT NULL,
    description        TEXT,
    exam_only          INTEGER NOT NULL DEFAULT 0,
    start_date         TEXT NOT NULL DEFAULT (date('now')),
    end_date           TEXT,
    status             TEXT NOT NULL DEFAULT 'Proposed',
    evidence_source    TEXT,
    evidence_reference TEXT,
    approved_by        TEXT,
    approval_date      TEXT,
    review_date        TEXT,
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_acc_pupil
    ON accessibility_arrangements(pupil_id);
CREATE INDEX IF NOT EXISTS idx_acc_status
    ON accessibility_arrangements(status);
CREATE INDEX IF NOT EXISTS idx_acc_exam
    ON accessibility_arrangements(exam_only);
"""


@dataclass
class Arrangement:
    arrangement_id: int
    pupil_id: str
    arrangement_type: str
    category: str
    description: str | None
    exam_only: bool
    start_date: str
    end_date: str | None
    status: str
    evidence_source: str | None
    evidence_reference: str | None
    approved_by: str | None
    approval_date: str | None
    review_date: str | None
    notes: str | None
    pupil_name: str | None = None
    pupil_year: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def expired(self) -> bool:
        if not self.end_date or self.status != "Active":
            return False
        try:
            return _dt.date.fromisoformat(self.end_date) < _dt.date.today()
        except ValueError:
            return False


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise accessibility table")
        raise
    logger.info("Secondary accessibility table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> Arrangement:
    keys = r.keys()
    return Arrangement(
        arrangement_id=r["arrangement_id"], pupil_id=r["pupil_id"],
        arrangement_type=r["arrangement_type"],
        category=r["category"], description=r["description"],
        exam_only=bool(r["exam_only"]),
        start_date=r["start_date"], end_date=r["end_date"],
        status=r["status"],
        evidence_source=r["evidence_source"],
        evidence_reference=r["evidence_reference"],
        approved_by=r["approved_by"],
        approval_date=r["approval_date"],
        review_date=r["review_date"], notes=r["notes"],
        pupil_name=r["pupil_name"] if "pupil_name" in keys else None,
        pupil_year=r["pupil_year"] if "pupil_year" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_date(value: Any, label: str, *,
                   required: bool = True) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        if required:
            return _dt.date.today().isoformat()
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid = (data.get("pupil_id") or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    from education_system.secondarysch_system.modules.domain.pupils.pupils import (
        pupils as pupils_data,
    )
    if pupils_data.get_pupil(pid) is None:
        raise ValidationError(f"No pupil with id {pid}")
    out["pupil_id"] = pid

    atype = (data.get("arrangement_type") or DEFAULT_TYPE).strip()
    if atype not in ARRANGEMENT_TYPES:
        raise ValidationError(
            f"Arrangement type must be one of "
            f"{', '.join(ARRANGEMENT_TYPES)}")
    out["arrangement_type"] = atype

    cat = (data.get("category") or "").strip()
    if not cat:
        raise ValidationError("Category is required")
    if len(cat) > 64:
        raise ValidationError("Category must be 64 chars or fewer")
    out["category"] = cat

    out["description"] = (data.get("description") or "").strip() or None

    exam_only = data.get("exam_only")
    out["exam_only"] = bool(exam_only)

    out["start_date"] = _validate_date(data.get("start_date"),
                                         "Start date")
    out["end_date"]   = _validate_date(data.get("end_date"),
                                         "End date", required=False)
    if out["end_date"] and out["end_date"] < out["start_date"]:
        raise ValidationError("End date cannot be before start date")

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status

    src = (data.get("evidence_source") or "").strip()
    if src and src not in EVIDENCE_SOURCES:
        raise ValidationError(
            f"Evidence source must be one of "
            f"{', '.join(EVIDENCE_SOURCES)}")
    out["evidence_source"] = src or None
    out["evidence_reference"] = (
        data.get("evidence_reference") or "").strip() or None

    out["approved_by"]   = (data.get("approved_by") or "").strip() or None
    out["approval_date"] = _validate_date(
        data.get("approval_date"), "Approval date", required=False)
    out["review_date"]   = _validate_date(
        data.get("review_date"), "Review date", required=False)
    out["notes"]         = (data.get("notes") or "").strip() or None

    if status == "Active" and not out["approved_by"]:
        raise ValidationError(
            "Approved by is required when status is Active")
    if (out["approval_date"]
            and out["approval_date"] < out["start_date"]):
        raise ValidationError(
            "Approval date cannot be before start date")
    return out


def create(data: dict[str, Any]) -> Arrangement:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO accessibility_arrangements
                       (pupil_id, arrangement_type, category,
                        description, exam_only, start_date, end_date,
                        status, evidence_source, evidence_reference,
                        approved_by, approval_date, review_date, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["pupil_id"], payload["arrangement_type"],
                 payload["category"], payload["description"],
                 1 if payload["exam_only"] else 0,
                 payload["start_date"], payload["end_date"],
                 payload["status"], payload["evidence_source"],
                 payload["evidence_reference"],
                 payload["approved_by"], payload["approval_date"],
                 payload["review_date"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create accessibility arrangement")
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info(
        "Created accessibility arrangement #%d pupil=%s "
        "type=%s category=%r exam_only=%s status=%s",
        rec.arrangement_id, rec.pupil_id, rec.arrangement_type,
        rec.category, rec.exam_only, rec.status)
    return rec


def get(arrangement_id: int) -> Arrangement | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT a.*,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM accessibility_arrangements a
                   LEFT JOIN pupils p ON p.pupil_id = a.pupil_id
                   WHERE a.arrangement_id = ?""",
                (arrangement_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", arrangement_id)
        raise
    return _row(r) if r else None


def list_arrangements(*, pupil_id: str | None = None,
                      year_group: str | None = None,
                      arrangement_type: str | None = None,
                      status: str | None = None,
                      exam_only: bool | None = None,
                      category: str | None = None
                      ) -> list[Arrangement]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if pupil_id:
        where.append("a.pupil_id = ?")
        params.append(pupil_id.strip())
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("p.year_group = ?")
        params.append(year_group)
    if arrangement_type:
        if arrangement_type not in ARRANGEMENT_TYPES:
            raise ValidationError(
                f"Type filter must be one of "
                f"{', '.join(ARRANGEMENT_TYPES)}")
        where.append("a.arrangement_type = ?")
        params.append(arrangement_type)
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(STATUSES)}")
        where.append("a.status = ?")
        params.append(status)
    if exam_only is not None:
        where.append("a.exam_only = ?")
        params.append(1 if exam_only else 0)
    if category:
        where.append("a.category = ?")
        params.append(category)
    sql = ("""SELECT a.*,
                     (p.first_name || ' ' || p.last_name) AS pupil_name,
                     p.year_group AS pupil_year
              FROM accessibility_arrangements a
              LEFT JOIN pupils p ON p.pupil_id = a.pupil_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY a.start_date DESC, a.arrangement_id DESC"
    try:
        with _connect() as conn:
            return [_row(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_arrangements failed")
        raise


def update(arrangement_id: int,
           data: dict[str, Any]) -> Arrangement:
    init_db()
    existing = get(arrangement_id)
    if existing is None:
        raise ValidationError(
            f"No accessibility arrangement #{arrangement_id}")
    merged = {k: data.get(k, getattr(existing, k))
              for k in ("pupil_id", "arrangement_type", "category",
                         "description", "exam_only", "start_date",
                         "end_date", "status", "evidence_source",
                         "evidence_reference", "approved_by",
                         "approval_date", "review_date", "notes")}
    payload = _validate(merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE accessibility_arrangements SET
                       pupil_id = ?, arrangement_type = ?, category = ?,
                       description = ?, exam_only = ?, start_date = ?,
                       end_date = ?, status = ?, evidence_source = ?,
                       evidence_reference = ?, approved_by = ?,
                       approval_date = ?, review_date = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE arrangement_id = ?""",
                (payload["pupil_id"], payload["arrangement_type"],
                 payload["category"], payload["description"],
                 1 if payload["exam_only"] else 0,
                 payload["start_date"], payload["end_date"],
                 payload["status"], payload["evidence_source"],
                 payload["evidence_reference"],
                 payload["approved_by"], payload["approval_date"],
                 payload["review_date"], payload["notes"],
                 arrangement_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to update arrangement #%d", arrangement_id)
        raise
    rec = get(arrangement_id)
    assert rec is not None
    logger.info(
        "Updated accessibility arrangement #%d (status %s)",
        rec.arrangement_id, rec.status)
    return rec


def set_status(arrangement_id: int, status: str) -> Arrangement:
    return update(arrangement_id, {"status": status})


def delete(arrangement_id: int) -> bool:
    init_db()
    existing = get(arrangement_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM accessibility_arrangements "
                "WHERE arrangement_id = ?", (arrangement_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception(
            "Failed to delete arrangement #%d", arrangement_id)
        raise
    if deleted:
        logger.info(
            "Deleted accessibility arrangement #%d (pupil %s)",
            arrangement_id, existing.pupil_id)
    return deleted


def pupil_arrangements(pupil_id: str,
                        *, active_only: bool = False
                        ) -> list[Arrangement]:
    rows = list_arrangements(pupil_id=pupil_id)
    if active_only:
        rows = [r for r in rows if r.status == "Active"]
    return rows


def expired_arrangements() -> list[Arrangement]:
    """Return Active arrangements whose ``end_date`` is in the past."""
    return [r for r in list_arrangements(status="Active")
            if r.expired]


def cohort_summary(*, year_group: str | None = None) -> dict[str, Any]:
    rows = list_arrangements(year_group=year_group)
    return {
        "total":          len(rows),
        "by_type":        dict(Counter(r.arrangement_type for r in rows)),
        "by_status":      dict(Counter(r.status for r in rows)),
        "by_category":    dict(Counter(r.category for r in rows)),
        "exam_only":      sum(1 for r in rows if r.exam_only),
        "active":         sum(1 for r in rows if r.status == "Active"),
        "expired_active": sum(1 for r in rows if r.expired),
    }
