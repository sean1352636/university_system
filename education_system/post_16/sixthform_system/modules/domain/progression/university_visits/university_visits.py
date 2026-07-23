"""University Visits data layer for the Sixth Form System.

Two tables:

* ``university_visits`` — one row per trip to a university (open day,
  taster day, applicant visit day, UCAS fair, campus tour).
* ``university_visit_attendees`` — many-to-many between visits and
  students with a per-student ``attended`` flag and optional notes.

Cascade: deleting a visit wipes its attendee rows; deleting a student
wipes their attendee rows but leaves the visits themselves intact.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.post_16.sixthform_system.core import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.UNIVERSITY_VISITS_DB

VISIT_TYPES: tuple[str, ...] = (
    "Open Day", "Taster Day", "Applicant Visit Day",
    "UCAS Fair", "Campus Tour", "Subject Masterclass", "Other",
)
DEFAULT_VISIT_TYPE: str = "Open Day"

TRANSPORT_MODES: tuple[str, ...] = (
    "Coach", "Minibus", "Train", "Independent Travel", "Other",
)
DEFAULT_TRANSPORT: str = "Coach"

VISIT_STATUSES: tuple[str, ...] = (
    "Planning", "Confirmed", "Completed", "Cancelled",
)
DEFAULT_VISIT_STATUS: str = "Planning"

YEAR_GROUPS: tuple[str, ...] = ("Year 12", "Year 13", "Mixed")
DEFAULT_YEAR_GROUP: str = "Year 12"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS university_visits (
    visit_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    university_name     TEXT    NOT NULL,
    visit_type          TEXT    NOT NULL DEFAULT 'Open Day',
    visit_date          TEXT    NOT NULL,
    departure_time      TEXT,
    return_time         TEXT,
    location            TEXT,
    year_group          TEXT    NOT NULL DEFAULT 'Year 12',
    organiser_staff_id  TEXT,
    transport           TEXT    NOT NULL DEFAULT 'Coach',
    cost_per_student    REAL    NOT NULL DEFAULT 0,
    capacity            INTEGER,
    status              TEXT    NOT NULL DEFAULT 'Planning',
    notes               TEXT,
    -- cross-system link: campus_tours.tour_id in the university system DB,
    -- populated by crm_link.push_visit_to_university_crm.
    campus_tour_id      INTEGER,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS university_visit_attendees (
    attendee_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id     INTEGER NOT NULL,
    student_id   TEXT    NOT NULL,
    attended     INTEGER NOT NULL DEFAULT 0,
    notes        TEXT,
    -- cross-system link: admission_prospects.prospect_id in the university DB.
    prospect_id  INTEGER,
    created_at   TEXT DEFAULT (datetime('now')),
    UNIQUE (visit_id, student_id),
    FOREIGN KEY (visit_id) REFERENCES university_visits(visit_id)
        ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_univisits_date    ON university_visits(visit_date);
CREATE INDEX IF NOT EXISTS idx_univisits_status  ON university_visits(status);
CREATE INDEX IF NOT EXISTS idx_univisits_year    ON university_visits(year_group);
CREATE INDEX IF NOT EXISTS idx_univ_att_student  ON university_visit_attendees(student_id);
CREATE INDEX IF NOT EXISTS idx_univ_att_visit    ON university_visit_attendees(visit_id);
"""


@dataclass
class UniversityVisit:
    visit_id: int
    university_name: str
    visit_type: str
    visit_date: str
    departure_time: str | None
    return_time: str | None
    location: str | None
    year_group: str
    organiser_staff_id: str | None
    transport: str
    cost_per_student: float
    capacity: int | None
    status: str
    notes: str | None
    campus_tour_id: int | None
    created_at: str
    updated_at: str


@dataclass
class VisitAttendee:
    attendee_id: int
    visit_id: int
    student_id: str
    attended: bool
    notes: str | None
    prospect_id: int | None
    created_at: str


@dataclass
class VisitRow:
    visit: UniversityVisit
    attendee_count: int


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def _ensure_column(conn: sqlite3.Connection, table: str,
                   column: str, ddl: str) -> None:
    cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.post_16.sixthform_system.modules.domain.students.students import students as _students
    _students.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        # Backfill the cross-system link columns on databases that pre-date them.
        _ensure_column(conn, "university_visits",
                       "campus_tour_id", "campus_tour_id INTEGER")
        _ensure_column(conn, "university_visit_attendees",
                       "prospect_id", "prospect_id INTEGER")
    logger.debug("University-visits schema ready at %s", DB_PATH)
    _DB_READY = True


def _opt(row: sqlite3.Row, key: str):
    """Optional column getter — tolerates older DBs missing newer columns."""
    try:
        return row[key]
    except (IndexError, KeyError):
        return None


def _row_visit(r: sqlite3.Row) -> UniversityVisit:
    return UniversityVisit(
        visit_id=r["visit_id"],
        university_name=r["university_name"],
        visit_type=r["visit_type"],
        visit_date=r["visit_date"],
        departure_time=r["departure_time"],
        return_time=r["return_time"],
        location=r["location"],
        year_group=r["year_group"],
        organiser_staff_id=r["organiser_staff_id"],
        transport=r["transport"],
        cost_per_student=r["cost_per_student"],
        capacity=r["capacity"],
        status=r["status"],
        notes=r["notes"],
        campus_tour_id=_opt(r, "campus_tour_id"),
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _row_attendee(r: sqlite3.Row) -> VisitAttendee:
    return VisitAttendee(
        attendee_id=r["attendee_id"],
        visit_id=r["visit_id"],
        student_id=r["student_id"],
        attended=bool(r["attended"]),
        notes=r["notes"],
        prospect_id=_opt(r, "prospect_id"),
        created_at=r["created_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for invalid university-visit input."""


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str, *, required: bool = False) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_time(value: Any, label: str) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    s = str(value).strip()
    if not _TIME_RE.match(s):
        raise ValidationError(f"{label} must be HH:MM")
    return s


def _validate_visit_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    out["university_name"] = _require(
        data.get("university_name"), "University name").strip()

    vtype = (data.get("visit_type") or DEFAULT_VISIT_TYPE).strip()
    if vtype not in VISIT_TYPES:
        raise ValidationError(
            f"Visit type must be one of: {', '.join(VISIT_TYPES)}")
    out["visit_type"] = vtype

    out["visit_date"] = _validate_date(
        data.get("visit_date"), "Visit date", required=True)
    out["departure_time"] = _validate_time(
        data.get("departure_time"), "Departure time")
    out["return_time"] = _validate_time(
        data.get("return_time"), "Return time")

    yg = (data.get("year_group") or DEFAULT_YEAR_GROUP).strip()
    if yg not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of: {', '.join(YEAR_GROUPS)}")
    out["year_group"] = yg

    transport = (data.get("transport") or DEFAULT_TRANSPORT).strip()
    if transport not in TRANSPORT_MODES:
        raise ValidationError(
            f"Transport must be one of: {', '.join(TRANSPORT_MODES)}")
    out["transport"] = transport

    status = (data.get("status") or DEFAULT_VISIT_STATUS).strip()
    if status not in VISIT_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(VISIT_STATUSES)}")
    out["status"] = status

    cost = data.get("cost_per_student", 0)
    if cost in (None, ""):
        cost = 0
    try:
        cost = float(cost)
    except (TypeError, ValueError):
        raise ValidationError("Cost per student must be a number") from None
    if cost < 0:
        raise ValidationError("Cost per student cannot be negative")
    out["cost_per_student"] = round(cost, 2)

    cap = data.get("capacity")
    if cap in (None, ""):
        out["capacity"] = None
    else:
        try:
            cap_int = int(cap)
        except (TypeError, ValueError):
            raise ValidationError("Capacity must be a whole number") from None
        if cap_int <= 0:
            raise ValidationError("Capacity must be positive")
        out["capacity"] = cap_int

    out["location"]           = (data.get("location") or "").strip() or None
    out["organiser_staff_id"] = (data.get("organiser_staff_id") or "").strip() or None
    out["notes"]              = (data.get("notes") or "").strip() or None
    return out


# ── Visit CRUD ────────────────────────────────────────────────────

def create_visit(data: dict[str, Any]) -> UniversityVisit:
    init_db()
    p = _validate_visit_payload(data)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO university_visits
                   (university_name, visit_type, visit_date,
                    departure_time, return_time, location,
                    year_group, organiser_staff_id, transport,
                    cost_per_student, capacity, status, notes,
                    created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["university_name"], p["visit_type"], p["visit_date"],
             p["departure_time"], p["return_time"], p["location"],
             p["year_group"], p["organiser_staff_id"], p["transport"],
             p["cost_per_student"], p["capacity"], p["status"],
             p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_visit(new_id)
    assert out is not None
    logger.info(
        "Created university visit #%d to %s on %s (%s, %s)",
        new_id, p["university_name"], p["visit_date"],
        p["visit_type"], p["status"],
    )
    return out


def get_visit(visit_id: int) -> UniversityVisit | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM university_visits WHERE visit_id = ?",
            (visit_id,),
        ).fetchone()
        return _row_visit(r) if r else None


def list_visits(
    *,
    university_like: str | None = None,
    visit_type: str | None = None,
    year_group: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[UniversityVisit]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if university_like:
        clauses.append("university_name LIKE ?")
        args.append(f"%{university_like.strip()}%")
    if visit_type:
        if visit_type not in VISIT_TYPES:
            raise ValidationError(
                f"Visit type must be one of: {', '.join(VISIT_TYPES)}")
        clauses.append("visit_type = ?")
        args.append(visit_type)
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year group must be one of: {', '.join(YEAR_GROUPS)}")
        clauses.append("year_group = ?")
        args.append(year_group)
    if status:
        if status not in VISIT_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(VISIT_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if date_from:
        clauses.append("visit_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("visit_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM university_visits {where} "
           "ORDER BY visit_date DESC, visit_id DESC")
    with _connect() as conn:
        return [_row_visit(r) for r in conn.execute(sql, args).fetchall()]


def list_visits_with_detail(**kwargs) -> list[VisitRow]:
    visits = list_visits(**kwargs)
    if not visits:
        return []
    with _connect() as conn:
        counts = dict(conn.execute(
            "SELECT visit_id, COUNT(*) FROM university_visit_attendees "
            "GROUP BY visit_id"
        ).fetchall())
    return [VisitRow(visit=v, attendee_count=counts.get(v.visit_id, 0))
            for v in visits]


def update_visit(visit_id: int, data: dict[str, Any]) -> UniversityVisit:
    init_db()
    existing = get_visit(visit_id)
    if existing is None:
        raise ValidationError(f"No university visit with id {visit_id}")
    merged = {
        "university_name":    data.get("university_name", existing.university_name),
        "visit_type":         data.get("visit_type", existing.visit_type),
        "visit_date":         data.get("visit_date", existing.visit_date),
        "departure_time":     data.get("departure_time", existing.departure_time),
        "return_time":        data.get("return_time", existing.return_time),
        "location":           data.get("location", existing.location),
        "year_group":         data.get("year_group", existing.year_group),
        "organiser_staff_id": data.get("organiser_staff_id",
                                       existing.organiser_staff_id),
        "transport":          data.get("transport", existing.transport),
        "cost_per_student":   data.get("cost_per_student",
                                       existing.cost_per_student),
        "capacity":           data.get("capacity", existing.capacity),
        "status":             data.get("status", existing.status),
        "notes":              data.get("notes", existing.notes),
    }
    p = _validate_visit_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE university_visits SET
                   university_name = ?, visit_type = ?, visit_date = ?,
                   departure_time = ?, return_time = ?, location = ?,
                   year_group = ?, organiser_staff_id = ?, transport = ?,
                   cost_per_student = ?, capacity = ?, status = ?,
                   notes = ?, updated_at = datetime('now')
               WHERE visit_id = ?""",
            (p["university_name"], p["visit_type"], p["visit_date"],
             p["departure_time"], p["return_time"], p["location"],
             p["year_group"], p["organiser_staff_id"], p["transport"],
             p["cost_per_student"], p["capacity"], p["status"],
             p["notes"], visit_id),
        )
        conn.commit()
    out = get_visit(visit_id)
    assert out is not None
    logger.info("Updated university visit #%d (%s, status=%s)",
                visit_id, out.visit_date, out.status)
    return out


def delete_visit(visit_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM university_visits WHERE visit_id = ?",
            (visit_id,),
        )
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted university visit #%d", visit_id)
            return True
        return False


# ── Attendees ─────────────────────────────────────────────────────

def list_attendees(visit_id: int) -> list[VisitAttendee]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM university_visit_attendees "
            "WHERE visit_id = ? ORDER BY student_id",
            (visit_id,),
        ).fetchall()
        return [_row_attendee(r) for r in rows]


def visits_for_student(student_id: str) -> list[UniversityVisit]:
    """All visits a particular student is signed up for, newest first."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT v.* FROM university_visits v
               JOIN university_visit_attendees a
                 ON a.visit_id = v.visit_id
               WHERE a.student_id = ?
               ORDER BY v.visit_date DESC, v.visit_id DESC""",
            (student_id.strip(),),
        ).fetchall()
        return [_row_visit(r) for r in rows]


def add_attendee(visit_id: int, student_id: str,
                 *, attended: bool = False,
                 notes: str | None = None) -> VisitAttendee:
    init_db()
    sid = _require(student_id, "Student ID").strip()
    if get_visit(visit_id) is None:
        raise ValidationError(f"No university visit with id {visit_id}")
    from education_system.post_16.sixthform_system.modules.domain.students.students import students as _students
    if _students.get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    capacity = get_visit(visit_id).capacity  # type: ignore[union-attr]
    if capacity is not None:
        current = len(list_attendees(visit_id))
        if current >= capacity:
            raise ValidationError(
                f"Visit #{visit_id} is at capacity ({capacity})")
    with _connect() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO university_visit_attendees
                       (visit_id, student_id, attended, notes, created_at)
                   VALUES (?, ?, ?, ?, datetime('now'))""",
                (visit_id, sid, 1 if attended else 0,
                 (notes or "").strip() or None),
            )
            conn.commit()
            new_id = cur.lastrowid
        except sqlite3.IntegrityError:
            raise ValidationError(
                f"{sid} is already on visit #{visit_id}") from None
        r = conn.execute(
            "SELECT * FROM university_visit_attendees WHERE attendee_id = ?",
            (new_id,),
        ).fetchone()
    logger.info("Added %s to university visit #%d", sid, visit_id)
    return _row_attendee(r)


def set_attendance(attendee_id: int, attended: bool,
                    *, notes: str | None = None) -> VisitAttendee | None:
    init_db()
    with _connect() as conn:
        if notes is None:
            conn.execute(
                """UPDATE university_visit_attendees
                   SET attended = ? WHERE attendee_id = ?""",
                (1 if attended else 0, attendee_id),
            )
        else:
            conn.execute(
                """UPDATE university_visit_attendees
                   SET attended = ?, notes = ? WHERE attendee_id = ?""",
                (1 if attended else 0, notes.strip() or None, attendee_id),
            )
        conn.commit()
        r = conn.execute(
            "SELECT * FROM university_visit_attendees WHERE attendee_id = ?",
            (attendee_id,),
        ).fetchone()
        return _row_attendee(r) if r else None


def get_visit_link(visit_id: int) -> int | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT campus_tour_id FROM university_visits WHERE visit_id = ?",
            (visit_id,),
        ).fetchone()
        return r["campus_tour_id"] if r else None


def set_visit_link(visit_id: int, campus_tour_id: int) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            "UPDATE university_visits SET campus_tour_id = ?, "
            "updated_at = datetime('now') WHERE visit_id = ?",
            (campus_tour_id, visit_id),
        )
        conn.commit()


def get_attendee_link(attendee_id: int) -> int | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT prospect_id FROM university_visit_attendees "
            "WHERE attendee_id = ?",
            (attendee_id,),
        ).fetchone()
        return r["prospect_id"] if r else None


def set_attendee_link(attendee_id: int, prospect_id: int) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            "UPDATE university_visit_attendees SET prospect_id = ? "
            "WHERE attendee_id = ?",
            (prospect_id, attendee_id),
        )
        conn.commit()


def remove_attendee(attendee_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM university_visit_attendees WHERE attendee_id = ?",
            (attendee_id,),
        )
        conn.commit()
        return cur.rowcount > 0


# ── Summary ───────────────────────────────────────────────────────

@dataclass
class VisitsSummary:
    total_visits: int
    total_attendees: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    by_year_group: dict[str, int]
    upcoming_visits: int       # visit_date in next N days, not Cancelled
    students_attended: int     # distinct students with attended=True


def summary(*, upcoming_window_days: int = 30) -> VisitsSummary:
    import datetime as _dt
    init_db()
    today = _dt.date.today()
    upcoming_cutoff = (today + _dt.timedelta(days=upcoming_window_days)
                       ).isoformat()
    today_iso = today.isoformat()

    visits = list_visits()
    by_status = {s: 0 for s in VISIT_STATUSES}
    by_type   = {t: 0 for t in VISIT_TYPES}
    by_year   = {y: 0 for y in YEAR_GROUPS}
    upcoming = 0
    for v in visits:
        by_status[v.status] = by_status.get(v.status, 0) + 1
        by_type[v.visit_type] = by_type.get(v.visit_type, 0) + 1
        by_year[v.year_group] = by_year.get(v.year_group, 0) + 1
        if (v.status != "Cancelled"
                and today_iso <= v.visit_date <= upcoming_cutoff):
            upcoming += 1

    with _connect() as conn:
        total_att = conn.execute(
            "SELECT COUNT(*) FROM university_visit_attendees"
        ).fetchone()[0]
        students_attended = conn.execute(
            "SELECT COUNT(DISTINCT student_id) "
            "FROM university_visit_attendees WHERE attended = 1"
        ).fetchone()[0]

    return VisitsSummary(
        total_visits=len(visits),
        total_attendees=total_att,
        by_status=by_status,
        by_type=by_type,
        by_year_group=by_year,
        upcoming_visits=upcoming,
        students_attended=students_attended,
    )
