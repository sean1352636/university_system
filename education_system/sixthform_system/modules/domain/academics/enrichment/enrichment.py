"""Enrichments — extra-curricular activities and student sign-ups.

One ``enrichment_activities`` row per offering (club, squad,
programme — debate society, DofE Gold, chess, Drama Production, etc.)
and a ``enrichment_enrolments`` row per student who has signed up.

Capacity is enforced if set: signing up an extra student when the
activity is already at capacity raises ``ValidationError``.

Cascade: deleting an activity removes its enrolments; deleting a
student removes their enrolment rows.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any
from education_system.sixthform_system.core import paths
from education_system.sixthform_system.modules.domain.academics.enrichment import (
    enrichment as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.ENRICHMENTS_DB


CATEGORIES: tuple[str, ...] = (
    "Sports",
    "Arts & Music",
    "Academic",
    "Languages",
    "STEM Club",
    "Debate / Public Speaking",
    "Service & Charity",
    "Leadership",
    "Wellbeing",
    "Outdoor / DofE",
    "Cultural",
    "Volunteering",
    "Career / Industry",
    "Other",
)
DEFAULT_CATEGORY: str = "Other"

DAYS: tuple[str, ...] = (
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
    "Saturday", "Sunday", "Various",
)

ACTIVITY_STATUSES: tuple[str, ...] = (
    "Open", "Full", "Waitlist", "Closed", "Archived", "Draft",
)
DEFAULT_ACTIVITY_STATUS: str = "Open"

ENROLMENT_STATUSES: tuple[str, ...] = (
    "Active", "Withdrawn", "Completed", "On Hold", "Removed",
)
DEFAULT_ENROLMENT_STATUS: str = "Active"
ACTIVE_ENROLMENT_STATUSES: tuple[str, ...] = ("Active",)

YEAR_GROUPS: tuple[str, ...] = (
    "Year 12", "Year 13", "Mixed", "All",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}(:\d{2})?$")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS enrichment_activities (
    activity_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL UNIQUE,
    category         TEXT NOT NULL DEFAULT 'Other',
    description      TEXT,
    day_of_week      TEXT,
    start_time       TEXT,
    end_time         TEXT,
    location         TEXT,
    lead_staff       TEXT,
    capacity         INTEGER,
    year_group       TEXT,
    term             TEXT,
    cost             REAL,
    status           TEXT NOT NULL DEFAULT 'Open',
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS enrichment_enrolments (
    enrolment_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id      INTEGER NOT NULL,
    student_id       TEXT NOT NULL,
    joined_on        TEXT,
    status           TEXT NOT NULL DEFAULT 'Active',
    role             TEXT,
    sessions_attended INTEGER NOT NULL DEFAULT 0,
    last_attended    TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (activity_id) REFERENCES enrichment_activities(activity_id)
        ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE,
    UNIQUE (activity_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_en_cat    ON enrichment_activities(category);
CREATE INDEX IF NOT EXISTS idx_en_day    ON enrichment_activities(day_of_week);
CREATE INDEX IF NOT EXISTS idx_en_status ON enrichment_activities(status);
CREATE INDEX IF NOT EXISTS idx_enr_act   ON enrichment_enrolments(activity_id);
CREATE INDEX IF NOT EXISTS idx_enr_stu   ON enrichment_enrolments(student_id);
CREATE INDEX IF NOT EXISTS idx_enr_stat  ON enrichment_enrolments(status);
"""


@dataclass
class Activity:
    activity_id: int
    name: str
    category: str
    description: str | None
    day_of_week: str | None
    start_time: str | None
    end_time: str | None
    location: str | None
    lead_staff: str | None
    capacity: int | None
    year_group: str | None
    term: str | None
    cost: float | None
    status: str
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def time_label(self) -> str:
        if self.start_time and self.end_time:
            return f"{self.start_time[:5]}–{self.end_time[:5]}"
        if self.start_time:
            return self.start_time[:5]
        return "—"

    @property
    def when_label(self) -> str:
        bits = []
        if self.day_of_week:
            bits.append(self.day_of_week)
        if self.start_time:
            bits.append(self.time_label)
        return " · ".join(bits) if bits else "—"


@dataclass
class Enrolment:
    enrolment_id: int
    activity_id: int
    student_id: str
    joined_on: str | None
    status: str
    role: str | None
    sessions_attended: int
    last_attended: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_ENROLMENT_STATUSES


@dataclass
class ActivityDetail:
    activity: Activity
    enrolments: list[Enrolment] = field(default_factory=list)

    @property
    def total_enrolments(self) -> int:
        return len(self.enrolments)

    @property
    def active_count(self) -> int:
        return sum(1 for e in self.enrolments if e.is_active)

    @property
    def remaining_capacity(self) -> int | None:
        if self.activity.capacity is None:
            return None
        return max(0, self.activity.capacity - self.active_count)

    @property
    def is_full(self) -> bool:
        return (self.activity.capacity is not None
                and self.active_count >= self.activity.capacity)


@dataclass
class ActivityRow:
    activity: Activity
    total: int = 0
    active: int = 0


@dataclass
class EnrolmentRow:
    enrolment: Enrolment
    student_name: str
    activity_name: str


@dataclass
class Summary:
    total_activities: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    by_day: dict[str, int]
    open_count: int
    total_enrolments: int
    active_enrolments: int
    students_engaged: int        # distinct student ids with Active enrolment
    full_activities: int


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
    logger.debug("Enrichment schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_activity(r: sqlite3.Row) -> Activity:
    return Activity(
        activity_id=r["activity_id"], name=r["name"],
        category=r["category"], description=r["description"],
        day_of_week=r["day_of_week"],
        start_time=r["start_time"], end_time=r["end_time"],
        location=r["location"], lead_staff=r["lead_staff"],
        capacity=r["capacity"], year_group=r["year_group"],
        term=r["term"], cost=r["cost"], status=r["status"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_enrolment(r: sqlite3.Row) -> Enrolment:
    return Enrolment(
        enrolment_id=r["enrolment_id"],
        activity_id=r["activity_id"],
        student_id=r["student_id"], joined_on=r["joined_on"],
        status=r["status"], role=r["role"],
        sessions_attended=r["sessions_attended"],
        last_attended=r["last_attended"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str, *,
                    required: bool = False) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate_time(value: Any, label: str) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        return None
    s = str(value).strip()
    if not _TIME_RE.match(s):
        raise ValidationError(f"{label} must be HH:MM")
    if len(s) == 5:
        s = s + ":00"
    try:
        _dt.time.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real time") from None
    return s


def _validate_activity_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["name"] = _require(payload.get("name"), "Name").strip()

    cat = (payload.get("category") or DEFAULT_CATEGORY).strip()
    if cat not in CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(CATEGORIES)}")
    out["category"] = cat

    day = (payload.get("day_of_week") or "").strip()
    if day and day not in DAYS:
        raise ValidationError(
            f"Day must be one of: {', '.join(DAYS)}")
    out["day_of_week"] = day or None

    out["start_time"] = _validate_time(payload.get("start_time"),
                                            "Start time")
    out["end_time"]   = _validate_time(payload.get("end_time"),
                                            "End time")
    if (out["start_time"] and out["end_time"]
            and out["end_time"] <= out["start_time"]):
        raise ValidationError(
            "End time must be after start time")

    out["location"]   = (payload.get("location") or "").strip() or None
    out["lead_staff"] = (payload.get("lead_staff")
                            or "").strip() or None
    out["term"]       = (payload.get("term") or "").strip() or None
    out["description"] = (payload.get("description")
                            or "").strip() or None
    out["notes"]       = (payload.get("notes") or "").strip() or None

    cap = payload.get("capacity")
    if cap in (None, ""):
        out["capacity"] = None
    else:
        try:
            n = int(cap)
        except (TypeError, ValueError):
            raise ValidationError(
                "Capacity must be a whole number") from None
        if n < 0:
            raise ValidationError("Capacity cannot be negative")
        out["capacity"] = n

    year = (payload.get("year_group") or "").strip()
    if year and year not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of: "
            f"{', '.join(YEAR_GROUPS)}")
    out["year_group"] = year or None

    cost = payload.get("cost")
    if cost in (None, ""):
        out["cost"] = None
    else:
        try:
            f = float(cost)
        except (TypeError, ValueError):
            raise ValidationError("Cost must be a number") from None
        if f < 0:
            raise ValidationError("Cost cannot be negative")
        out["cost"] = f

    status = (payload.get("status") or DEFAULT_ACTIVITY_STATUS).strip()
    if status not in ACTIVITY_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(ACTIVITY_STATUSES)}")
    out["status"] = status
    return out


def _validate_enrolment_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    aid = payload.get("activity_id")
    if aid in (None, ""):
        raise ValidationError("Activity id is required")
    try:
        out["activity_id"] = int(aid)
    except (TypeError, ValueError):
        raise ValidationError(
            "Activity id must be a number") from None
    if get_activity(out["activity_id"]) is None:
        raise ValidationError(f"No activity #{out['activity_id']}")

    sid = _require(payload.get("student_id"), "Student").strip()
    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    out["student_id"] = sid

    out["joined_on"] = _validate_date(payload.get("joined_on"),
                                          "Joined on")
    status = (payload.get("status") or DEFAULT_ENROLMENT_STATUS).strip()
    if status not in ENROLMENT_STATUSES:
        raise ValidationError(
            f"Enrolment status must be one of: "
            f"{', '.join(ENROLMENT_STATUSES)}")
    out["status"] = status

    out["role"] = (payload.get("role") or "").strip() or None
    sa = payload.get("sessions_attended")
    if sa in (None, ""):
        out["sessions_attended"] = 0
    else:
        try:
            n = int(sa)
        except (TypeError, ValueError):
            raise ValidationError(
                "Sessions attended must be a whole number") from None
        if n < 0:
            raise ValidationError(
                "Sessions attended cannot be negative")
        out["sessions_attended"] = n
    out["last_attended"] = _validate_date(
        payload.get("last_attended"), "Last attended")
    out["notes"] = (payload.get("notes") or "").strip() or None

    if not out["joined_on"]:
        out["joined_on"] = _dt.date.today().isoformat()
    return out


# ── Activity CRUD ─────────────────────────────────────────────────

def create_activity(payload: dict[str, Any]) -> Activity:
    init_db()
    p = _validate_activity_payload(payload)
    with _connect() as conn:
        if conn.execute(
                "SELECT 1 FROM enrichment_activities WHERE name = ?",
                (p["name"],)).fetchone():
            raise ValidationError(
                f"An activity named {p['name']!r} already exists")
        cur = conn.execute(
            """INSERT INTO enrichment_activities
                   (name, category, description, day_of_week,
                    start_time, end_time, location, lead_staff,
                    capacity, year_group, term, cost, status, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["name"], p["category"], p["description"],
             p["day_of_week"], p["start_time"], p["end_time"],
             p["location"], p["lead_staff"], p["capacity"],
             p["year_group"], p["term"], p["cost"], p["status"],
             p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_activity(new_id)
    assert out is not None
    logger.info("Created activity #%d %r (%s, %s)",
                new_id, p["name"], p["category"], p["status"])
    return out


def get_activity(activity_id: int) -> Activity | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM enrichment_activities "
            "WHERE activity_id = ?",
            (activity_id,)).fetchone()
        return _row_activity(r) if r else None


def get_activity_by_name(name: str) -> Activity | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM enrichment_activities WHERE name = ?",
            (name.strip(),)).fetchone()
        return _row_activity(r) if r else None


def list_activities(
    *,
    category: str | None = None,
    status: str | None = None,
    day_of_week: str | None = None,
    year_group: str | None = None,
    open_only: bool = False,
    search: str | None = None,
) -> list[Activity]:
    init_db()
    clauses, args = [], []
    if category:
        if category not in CATEGORIES:
            raise ValidationError(
                f"Category must be one of: {', '.join(CATEGORIES)}")
        clauses.append("category = ?")
        args.append(category)
    if status:
        if status not in ACTIVITY_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(ACTIVITY_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if day_of_week:
        if day_of_week not in DAYS:
            raise ValidationError(
                f"Day must be one of: {', '.join(DAYS)}")
        clauses.append("day_of_week = ?")
        args.append(day_of_week)
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year group must be one of: "
                f"{', '.join(YEAR_GROUPS)}")
        clauses.append("year_group = ?")
        args.append(year_group)
    if open_only:
        clauses.append("status IN ('Open', 'Waitlist')")
    if search:
        s = f"%{search.strip()}%"
        clauses.append(
            "(name LIKE ? OR description LIKE ? OR lead_staff LIKE ?)")
        args.extend([s, s, s])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM enrichment_activities {where} "
           "ORDER BY CASE day_of_week "
           "  WHEN 'Monday'    THEN 1 "
           "  WHEN 'Tuesday'   THEN 2 "
           "  WHEN 'Wednesday' THEN 3 "
           "  WHEN 'Thursday'  THEN 4 "
           "  WHEN 'Friday'    THEN 5 "
           "  WHEN 'Saturday'  THEN 6 "
           "  WHEN 'Sunday'    THEN 7 "
           "  WHEN 'Various'   THEN 8 "
           "  ELSE 9 END, "
           "start_time ASC, name ASC")
    with _connect() as conn:
        return [_row_activity(r)
                for r in conn.execute(sql, args).fetchall()]


def list_activities_with_detail(**kwargs) -> list[ActivityRow]:
    rows = list_activities(**kwargs)
    if not rows:
        return []
    out: list[ActivityRow] = []
    with _connect() as conn:
        for a in rows:
            stats = conn.execute(
                f"SELECT COUNT(*) total, "
                f"  SUM(CASE WHEN status IN "
                f"    ({','.join('?' * len(ACTIVE_ENROLMENT_STATUSES))}) "
                f"    THEN 1 ELSE 0 END) AS active "
                f"FROM enrichment_enrolments WHERE activity_id = ?",
                (*ACTIVE_ENROLMENT_STATUSES, a.activity_id)).fetchone()
            out.append(ActivityRow(
                activity=a,
                total=stats["total"] or 0,
                active=stats["active"] or 0,
            ))
    return out


def get_activity_detail(activity_id: int) -> ActivityDetail | None:
    init_db()
    a = get_activity(activity_id)
    if a is None:
        return None
    enrolments = list_enrolments(activity_id=activity_id)
    return ActivityDetail(activity=a, enrolments=enrolments)


def update_activity(activity_id: int,
                    payload: dict[str, Any]) -> Activity:
    init_db()
    existing = get_activity(activity_id)
    if existing is None:
        raise ValidationError(f"No activity #{activity_id}")
    merged = {
        "name":        payload.get("name", existing.name),
        "category":    payload.get("category", existing.category),
        "description": payload.get("description",
                                    existing.description),
        "day_of_week": payload.get("day_of_week",
                                    existing.day_of_week),
        "start_time":  payload.get("start_time", existing.start_time),
        "end_time":    payload.get("end_time", existing.end_time),
        "location":    payload.get("location", existing.location),
        "lead_staff":  payload.get("lead_staff", existing.lead_staff),
        "capacity":    payload.get("capacity", existing.capacity),
        "year_group":  payload.get("year_group", existing.year_group),
        "term":        payload.get("term", existing.term),
        "cost":        payload.get("cost", existing.cost),
        "status":      payload.get("status", existing.status),
        "notes":       payload.get("notes", existing.notes),
    }
    p = _validate_activity_payload(merged)
    with _connect() as conn:
        row = conn.execute(
            "SELECT activity_id FROM enrichment_activities "
            "WHERE name = ?", (p["name"],)).fetchone()
        if row and row["activity_id"] != activity_id:
            raise ValidationError(
                f"An activity named {p['name']!r} already exists")
        conn.execute(
            """UPDATE enrichment_activities SET
                   name = ?, category = ?, description = ?,
                   day_of_week = ?, start_time = ?, end_time = ?,
                   location = ?, lead_staff = ?, capacity = ?,
                   year_group = ?, term = ?, cost = ?, status = ?,
                   notes = ?, updated_at = datetime('now')
               WHERE activity_id = ?""",
            (p["name"], p["category"], p["description"],
             p["day_of_week"], p["start_time"], p["end_time"],
             p["location"], p["lead_staff"], p["capacity"],
             p["year_group"], p["term"], p["cost"], p["status"],
             p["notes"], activity_id),
        )
        conn.commit()
    out = get_activity(activity_id)
    assert out is not None
    return out


def set_activity_status(activity_id: int, status: str) -> Activity:
    return update_activity(activity_id, {"status": status})


def delete_activity(activity_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM enrichment_activities WHERE activity_id = ?",
            (activity_id,))
        conn.commit()
        if cur.rowcount:
            logger.info(
                "Deleted activity #%d (cascade: enrolments)",
                activity_id)
            return True
        return False


# ── Enrolment CRUD ────────────────────────────────────────────────

def _check_capacity(activity_id: int) -> None:
    a = get_activity(activity_id)
    if a is None or a.capacity is None:
        return
    detail = get_activity_detail(activity_id)
    if detail and detail.is_full:
        raise ValidationError(
            f"Activity is at capacity ({a.capacity}). "
            "Consider waitlisting or increasing capacity.")


def sign_up(activity_id: int, student_id: str, *,
             role: str | None = None,
             joined_on: str | None = None) -> Enrolment:
    _check_capacity(activity_id)
    return create_enrolment({
        "activity_id": activity_id,
        "student_id": student_id,
        "joined_on": joined_on,
        "role": role,
        "status": DEFAULT_ENROLMENT_STATUS,
    })


def create_enrolment(payload: dict[str, Any]) -> Enrolment:
    init_db()
    p = _validate_enrolment_payload(payload)
    with _connect() as conn:
        if conn.execute(
                "SELECT 1 FROM enrichment_enrolments "
                "WHERE activity_id = ? AND student_id = ?",
                (p["activity_id"], p["student_id"])).fetchone():
            raise ValidationError(
                f"Student {p['student_id']} is already enrolled "
                f"on activity #{p['activity_id']}")
        cur = conn.execute(
            """INSERT INTO enrichment_enrolments
                   (activity_id, student_id, joined_on, status,
                    role, sessions_attended, last_attended, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["activity_id"], p["student_id"], p["joined_on"],
             p["status"], p["role"], p["sessions_attended"],
             p["last_attended"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_enrolment(new_id)
    assert out is not None
    logger.info("Created enrolment #%d (student=%s, activity=%d)",
                new_id, p["student_id"], p["activity_id"])
    return out


def get_enrolment(enrolment_id: int) -> Enrolment | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM enrichment_enrolments "
            "WHERE enrolment_id = ?",
            (enrolment_id,)).fetchone()
        return _row_enrolment(r) if r else None


def list_enrolments(
    *,
    activity_id: int | None = None,
    student_id: str | None = None,
    status: str | None = None,
    active_only: bool = False,
) -> list[Enrolment]:
    init_db()
    clauses, args = [], []
    if activity_id is not None:
        clauses.append("activity_id = ?")
        args.append(int(activity_id))
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if status:
        if status not in ENROLMENT_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(ENROLMENT_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if active_only:
        ph = ",".join("?" * len(ACTIVE_ENROLMENT_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(ACTIVE_ENROLMENT_STATUSES)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM enrichment_enrolments {where} "
           "ORDER BY activity_id ASC, student_id ASC")
    with _connect() as conn:
        return [_row_enrolment(r)
                for r in conn.execute(sql, args).fetchall()]


def list_enrolments_with_detail(**kwargs) -> list[EnrolmentRow]:
    rows = list_enrolments(**kwargs)
    if not rows:
        return []
    from education_system.sixthform_system.modules.domain.students.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name
              for s in _students.list_students()}
    acts = {a.activity_id: a.name for a in list_activities()}
    return [EnrolmentRow(
        enrolment=e,
        student_name=names.get(e.student_id, "(unknown)"),
        activity_name=acts.get(e.activity_id, f"#{e.activity_id}"),
    ) for e in rows]


def update_enrolment(enrolment_id: int,
                     payload: dict[str, Any]) -> Enrolment:
    init_db()
    existing = get_enrolment(enrolment_id)
    if existing is None:
        raise ValidationError(f"No enrolment #{enrolment_id}")
    merged = {
        "activity_id":       existing.activity_id,
        "student_id":        existing.student_id,
        "joined_on":         payload.get("joined_on",
                                          existing.joined_on),
        "status":            payload.get("status", existing.status),
        "role":              payload.get("role", existing.role),
        "sessions_attended": payload.get("sessions_attended",
                                          existing.sessions_attended),
        "last_attended":     payload.get("last_attended",
                                          existing.last_attended),
        "notes":             payload.get("notes", existing.notes),
    }
    p = _validate_enrolment_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE enrichment_enrolments SET
                   joined_on = ?, status = ?, role = ?,
                   sessions_attended = ?, last_attended = ?,
                   notes = ?, updated_at = datetime('now')
               WHERE enrolment_id = ?""",
            (p["joined_on"], p["status"], p["role"],
             p["sessions_attended"], p["last_attended"],
             p["notes"], enrolment_id),
        )
        conn.commit()
    out = get_enrolment(enrolment_id)
    assert out is not None
    return out


def set_enrolment_status(enrolment_id: int, status: str) -> Enrolment:
    return update_enrolment(enrolment_id, {"status": status})


def withdraw(enrolment_id: int) -> Enrolment:
    return set_enrolment_status(enrolment_id, "Withdrawn")


def complete(enrolment_id: int) -> Enrolment:
    return set_enrolment_status(enrolment_id, "Completed")


def record_attendance(enrolment_id: int, *,
                       sessions: int = 1,
                       when: str | None = None) -> Enrolment:
    existing = get_enrolment(enrolment_id)
    if existing is None:
        raise ValidationError(f"No enrolment #{enrolment_id}")
    return update_enrolment(enrolment_id, {
        "sessions_attended": existing.sessions_attended + sessions,
        "last_attended": when or _dt.date.today().isoformat(),
    })


def delete_enrolment(enrolment_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM enrichment_enrolments "
            "WHERE enrolment_id = ?",
            (enrolment_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted enrolment #%d", enrolment_id)
            return True
        return False


# ── Summary ───────────────────────────────────────────────────────

def summary() -> Summary:
    init_db()
    activities = list_activities()
    by_status = {s: 0 for s in ACTIVITY_STATUSES}
    by_cat = {c: 0 for c in CATEGORIES}
    by_day: dict[str, int] = {d: 0 for d in DAYS}
    by_day["—"] = 0
    open_count = 0
    full_count = 0
    for a in activities:
        by_status[a.status] = by_status.get(a.status, 0) + 1
        by_cat[a.category] = by_cat.get(a.category, 0) + 1
        key = a.day_of_week or "—"
        by_day[key] = by_day.get(key, 0) + 1
        if a.status == "Open":
            open_count += 1
        d = get_activity_detail(a.activity_id)
        if d and d.is_full:
            full_count += 1

    with _connect() as conn:
        tot = conn.execute(
            "SELECT COUNT(*) FROM enrichment_enrolments"
        ).fetchone()[0]
        active = conn.execute(
            f"SELECT COUNT(*) FROM enrichment_enrolments "
            f"WHERE status IN "
            f"({','.join('?' * len(ACTIVE_ENROLMENT_STATUSES))})",
            ACTIVE_ENROLMENT_STATUSES).fetchone()[0]
        students_engaged = conn.execute(
            f"SELECT COUNT(DISTINCT student_id) "
            f"FROM enrichment_enrolments WHERE status IN "
            f"({','.join('?' * len(ACTIVE_ENROLMENT_STATUSES))})",
            ACTIVE_ENROLMENT_STATUSES).fetchone()[0]

    # Drop the zero buckets for cleanliness
    by_day = {k: v for k, v in by_day.items() if v}
    return Summary(
        total_activities=len(activities),
        by_status=by_status,
        by_category=by_cat,
        by_day=by_day,
        open_count=open_count,
        total_enrolments=tot,
        active_enrolments=active,
        students_engaged=students_engaged,
        full_activities=full_count,
    )
