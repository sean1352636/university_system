"""Behaviour-log data layer for the Sixth Form System.

One row per pastoral entry, positive or negative. Each entry records:

* what happened (entry_type, category, description),
* how severe it was (severity, points),
* who logged it and where,
* what action was taken,
* whether follow-up is needed and whether parents have been contacted.

Cascade: deleting a student wipes their behaviour entries.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.sixthform_system.core import paths
from education_system.sixthform_system.modules.domain.pastoral.behaviour import behaviour as data

logger = logging.getLogger(__name__)

DB_PATH = paths.BEHAVIOUR_DB

ENTRY_TYPES: tuple[str, ...] = ("Positive", "Negative")

SEVERITIES: tuple[str, ...] = ("Low", "Medium", "High")

POSITIVE_CATEGORIES: tuple[str, ...] = (
    "Excellent Work", "Participation", "Helpfulness", "Leadership",
    "Improvement", "Achievement", "Attendance", "Effort",
    "Community Contribution", "Other",
)

NEGATIVE_CATEGORIES: tuple[str, ...] = (
    "Lateness", "Punctuality", "Uniform", "Disruption", "Bullying",
    "Honesty", "Disrespect", "Missed Detention", "Vandalism",
    "Mobile Phone", "Plagiarism", "Truancy", "Other",
)

# Convenience: union for filter combos.
ALL_CATEGORIES: tuple[str, ...] = tuple(
    sorted(set(POSITIVE_CATEGORIES) | set(NEGATIVE_CATEGORIES)))

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS behaviour_entries (
    entry_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id         TEXT NOT NULL,
    entry_date         TEXT NOT NULL,
    entry_type         TEXT NOT NULL,
    category           TEXT NOT NULL,
    severity           TEXT,
    points             INTEGER NOT NULL DEFAULT 0,
    location           TEXT,
    description        TEXT NOT NULL,
    recorded_by        TEXT,
    action_taken       TEXT,
    follow_up_required INTEGER NOT NULL DEFAULT 0,
    follow_up_date     TEXT,
    parent_contacted   INTEGER NOT NULL DEFAULT 0,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bh_student  ON behaviour_entries(student_id);
CREATE INDEX IF NOT EXISTS idx_bh_date     ON behaviour_entries(entry_date);
CREATE INDEX IF NOT EXISTS idx_bh_type     ON behaviour_entries(entry_type);
CREATE INDEX IF NOT EXISTS idx_bh_category ON behaviour_entries(category);
"""


@dataclass
class BehaviourEntry:
    entry_id: int
    student_id: str
    entry_date: str
    entry_type: str
    category: str
    severity: str | None
    points: int
    location: str | None
    description: str
    recorded_by: str | None
    action_taken: str | None
    follow_up_required: bool
    follow_up_date: str | None
    parent_contacted: bool
    created_at: str
    updated_at: str


@dataclass
class EntryRow:
    entry: BehaviourEntry
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
    from education_system.sixthform_system.modules.domain.students.students import students as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Behaviour schema ready at %s", DB_PATH)

    _DB_READY = True


def _row(r: sqlite3.Row) -> BehaviourEntry:
    return BehaviourEntry(
        entry_id=r["entry_id"], student_id=r["student_id"],
        entry_date=r["entry_date"], entry_type=r["entry_type"],
        category=r["category"], severity=r["severity"],
        points=r["points"], location=r["location"],
        description=r["description"], recorded_by=r["recorded_by"],
        action_taken=r["action_taken"],
        follow_up_required=bool(r["follow_up_required"]),
        follow_up_date=r["follow_up_date"],
        parent_contacted=bool(r["parent_contacted"]),
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for any invalid behaviour input."""


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
    return s


def _coerce_bool(value: Any) -> int:
    if isinstance(value, str):
        return 1 if value.strip().lower() in ("1", "true", "yes", "y", "on") else 0
    return 1 if bool(value) else 0


def _validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    sid = _require(data.get("student_id"), "Student ID").strip()
    from education_system.sixthform_system.modules.domain.students.students import students as _students
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    out["student_id"] = sid

    out["entry_date"] = _validate_date(
        _require(data.get("entry_date"), "Entry date"), "Entry date")

    etype = _require(data.get("entry_type"), "Entry type").strip()
    if etype not in ENTRY_TYPES:
        raise ValidationError(
            f"Entry type must be one of: {', '.join(ENTRY_TYPES)}")
    out["entry_type"] = etype

    category = _require(data.get("category"), "Category").strip()
    allowed = (POSITIVE_CATEGORIES if etype == "Positive"
               else NEGATIVE_CATEGORIES)
    if category not in allowed:
        raise ValidationError(
            f"Category for {etype} entries must be one of: "
            f"{', '.join(allowed)}")
    out["category"] = category

    severity = (data.get("severity") or "").strip()
    if etype == "Negative":
        if not severity:
            raise ValidationError(
                "Severity is required for negative entries")
        if severity not in SEVERITIES:
            raise ValidationError(
                f"Severity must be one of: {', '.join(SEVERITIES)}")
        out["severity"] = severity
    else:
        # Positive: severity is optional, but if set must be valid.
        if severity and severity not in SEVERITIES:
            raise ValidationError(
                f"Severity must be one of: {', '.join(SEVERITIES)} (or blank)")
        out["severity"] = severity or None

    points = data.get("points")
    if points in (None, ""):
        # Sensible defaults: +5 positive, -5/-10/-20 by severity.
        if etype == "Positive":
            out["points"] = 5
        else:
            out["points"] = {"Low": -5, "Medium": -10, "High": -20}.get(
                out["severity"], -5)
    else:
        try:
            out["points"] = int(points)
        except (TypeError, ValueError):
            raise ValidationError("Points must be a whole number") from None

    out["description"] = _require(
        data.get("description"), "Description").strip()

    out["follow_up_date"] = _validate_date(
        data.get("follow_up_date"), "Follow-up date")
    out["follow_up_required"] = _coerce_bool(
        data.get("follow_up_required"))
    out["parent_contacted"] = _coerce_bool(data.get("parent_contacted"))

    out["location"]     = (data.get("location") or "").strip() or None
    out["recorded_by"]  = (data.get("recorded_by") or "").strip() or None
    out["action_taken"] = (data.get("action_taken") or "").strip() or None
    return out


# ── CRUD ───────────────────────────────────────────────────────────

def create_entry(data: dict[str, Any]) -> BehaviourEntry:
    init_db()
    try:
        p = _validate_payload(data)
    except ValidationError as e:
        logger.warning("create_entry validation failed: %s", e)
        raise
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO behaviour_entries
                   (student_id, entry_date, entry_type, category, severity,
                    points, location, description, recorded_by,
                    action_taken, follow_up_required, follow_up_date,
                    parent_contacted, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["student_id"], p["entry_date"], p["entry_type"],
             p["category"], p["severity"], p["points"],
             p["location"], p["description"], p["recorded_by"],
             p["action_taken"], p["follow_up_required"],
             p["follow_up_date"], p["parent_contacted"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_entry(new_id)
    assert out is not None
    logger.info(
        "Created behaviour entry #%d for %s "
        "(%s, %s, severity=%s, points=%d)",
        new_id, p["student_id"], p["entry_type"], p["category"],
        p["severity"] or "—", p["points"],
    )
    return out


def get_entry(entry_id: int) -> BehaviourEntry | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM behaviour_entries WHERE entry_id = ?",
            (entry_id,),
        ).fetchone()
        return _row(r) if r else None


def list_entries(
    *,
    student_id: str | None = None,
    entry_type: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    recorded_by_like: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    follow_up_required: bool | None = None,
) -> list[BehaviourEntry]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if entry_type:
        if entry_type not in ENTRY_TYPES:
            raise ValidationError(
                f"Entry type must be one of: {', '.join(ENTRY_TYPES)}")
        clauses.append("entry_type = ?")
        args.append(entry_type)
    if category:
        clauses.append("category = ?")
        args.append(category)
    if severity:
        if severity not in SEVERITIES:
            raise ValidationError(
                f"Severity must be one of: {', '.join(SEVERITIES)}")
        clauses.append("severity = ?")
        args.append(severity)
    if recorded_by_like:
        clauses.append("recorded_by LIKE ?")
        args.append(f"%{recorded_by_like.strip()}%")
    if date_from:
        clauses.append("entry_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("entry_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    if follow_up_required is not None:
        clauses.append("follow_up_required = ?")
        args.append(1 if follow_up_required else 0)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM behaviour_entries {where} "
           "ORDER BY entry_date DESC, entry_id DESC")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def entries_for_student(student_id: str) -> list[BehaviourEntry]:
    return list_entries(student_id=student_id)


def list_entries_with_detail(**kwargs) -> list[EntryRow]:
    rows = list_entries(**kwargs)
    if not rows:
        return []
    from education_system.sixthform_system.modules.domain.students.students import students as _students
    names = {s.student_id: s.full_name for s in _students.list_students()}
    return [EntryRow(entry=e,
                      student_name=names.get(e.student_id, "(unknown)"))
            for e in rows]


def update_entry(entry_id: int, data: dict[str, Any]) -> BehaviourEntry:
    init_db()
    existing = get_entry(entry_id)
    if existing is None:
        logger.warning("update_entry: unknown id %d", entry_id)
        raise ValidationError(f"No entry with id {entry_id}")
    p = _validate_payload({
        "student_id":        existing.student_id,
        "entry_date":        data.get("entry_date", existing.entry_date),
        "entry_type":        data.get("entry_type", existing.entry_type),
        "category":          data.get("category", existing.category),
        "severity":          data.get("severity", existing.severity),
        "points":            data.get("points", existing.points),
        "location":          data.get("location", existing.location),
        "description":       data.get("description", existing.description),
        "recorded_by":       data.get("recorded_by", existing.recorded_by),
        "action_taken":      data.get("action_taken", existing.action_taken),
        "follow_up_required": data.get("follow_up_required",
                                        existing.follow_up_required),
        "follow_up_date":    data.get("follow_up_date",
                                       existing.follow_up_date),
        "parent_contacted":  data.get("parent_contacted",
                                       existing.parent_contacted),
    })
    with _connect() as conn:
        conn.execute(
            """UPDATE behaviour_entries SET
                   entry_date = ?, entry_type = ?, category = ?,
                   severity = ?, points = ?, location = ?,
                   description = ?, recorded_by = ?, action_taken = ?,
                   follow_up_required = ?, follow_up_date = ?,
                   parent_contacted = ?, updated_at = datetime('now')
               WHERE entry_id = ?""",
            (p["entry_date"], p["entry_type"], p["category"],
             p["severity"], p["points"], p["location"],
             p["description"], p["recorded_by"], p["action_taken"],
             p["follow_up_required"], p["follow_up_date"],
             p["parent_contacted"], entry_id),
        )
        conn.commit()
    out = get_entry(entry_id)
    assert out is not None
    logger.info("Updated behaviour entry #%d (points=%d, follow_up=%s)",
                entry_id, out.points, out.follow_up_required)
    return out


def delete_entry(entry_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM behaviour_entries WHERE entry_id = ?",
            (entry_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted behaviour entry #%d", entry_id)
            return True
        logger.warning("delete_entry: unknown id %d", entry_id)
        return False


# ── Summaries ─────────────────────────────────────────────────────

@dataclass
class StudentBehaviourSummary:
    student_id: str
    total_entries: int
    positive_count: int
    negative_count: int
    net_points: int
    open_follow_ups: int


def per_student_summary(student_id: str) -> StudentBehaviourSummary:
    rows = entries_for_student(student_id)
    pos = sum(1 for r in rows if r.entry_type == "Positive")
    neg = sum(1 for r in rows if r.entry_type == "Negative")
    net = sum(r.points for r in rows)
    open_fu = sum(1 for r in rows if r.follow_up_required)
    return StudentBehaviourSummary(
        student_id=student_id, total_entries=len(rows),
        positive_count=pos, negative_count=neg,
        net_points=net, open_follow_ups=open_fu,
    )


@dataclass
class Summary:
    total: int
    by_type: dict[str, int]
    by_category: dict[str, int]
    by_severity: dict[str, int]
    net_points: int
    follow_ups_open: int
    upcoming_follow_ups: int  # follow_up_date within window
    parents_contacted: int
    top_students_by_count: list[tuple[str, int]]  # (student_id, count)


def summary(
    *,
    upcoming_window_days: int = 14,
    top_n: int = 10,
) -> Summary:
    import datetime as _dt
    init_db()
    rows = list_entries()
    today = _dt.date.today().isoformat()
    cutoff = (_dt.date.today() + _dt.timedelta(days=upcoming_window_days)
              ).isoformat()

    by_type = {t: 0 for t in ENTRY_TYPES}
    by_category: dict[str, int] = {}
    by_severity = {s: 0 for s in SEVERITIES}
    net_points = 0
    follow_ups_open = 0
    upcoming = 0
    parents = 0
    per_student_count: dict[str, int] = {}
    for r in rows:
        by_type[r.entry_type] = by_type.get(r.entry_type, 0) + 1
        by_category[r.category] = by_category.get(r.category, 0) + 1
        if r.severity:
            by_severity[r.severity] = by_severity.get(r.severity, 0) + 1
        net_points += r.points
        if r.follow_up_required:
            follow_ups_open += 1
            if r.follow_up_date and today <= r.follow_up_date <= cutoff:
                upcoming += 1
        if r.parent_contacted:
            parents += 1
        per_student_count[r.student_id] = per_student_count.get(
            r.student_id, 0) + 1
    top = sorted(per_student_count.items(),
                 key=lambda kv: -kv[1])[:top_n]
    return Summary(
        total=len(rows), by_type=by_type, by_category=by_category,
        by_severity=by_severity, net_points=net_points,
        follow_ups_open=follow_ups_open,
        upcoming_follow_ups=upcoming,
        parents_contacted=parents,
        top_students_by_count=top,
    )
