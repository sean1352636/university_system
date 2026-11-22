"""Cover — per-absence cover requests for the Sixth Form System.

One row per absent teacher × date (or per period block). The workflow is:

    Open → Allocated → Confirmed → Completed
                      ↘ Cancelled
                      ↘ Class Split (lessons folded into other groups)
                      ↘ Self-Study (students study independently)

``cover_type`` records how the gap is being filled:

    Internal     — covered by another in-house teacher
    Agency       — covered by a supply agency (set ``agency_id`` too)
    Class Split  — students re-distributed across other lessons
    Self-Study   — supervised independent study
    Cancelled    — lesson cancelled / not happening

When ``cover_type='Agency'``, ``agency_id`` must reference a known row
in ``cover_agencies`` and the agency's ``last_used_on`` is auto-stamped
on save.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system import paths
from education_system.systems.sixth_form.domain.academics.cover import (
    cover as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_COVER_DB


ABSENCE_REASONS: tuple[str, ...] = (
    "Sickness",
    "Personal",
    "Bereavement",
    "Training / CPD",
    "External Meeting",
    "Trip Cover",
    "INSET",
    "Other",
)
DEFAULT_REASON: str = "Sickness"

COVER_TYPES: tuple[str, ...] = (
    "Internal",
    "Agency",
    "Class Split",
    "Self-Study",
    "Cancelled",
)
DEFAULT_COVER_TYPE: str = "Internal"

STATUSES: tuple[str, ...] = (
    "Open", "Allocated", "Confirmed", "Completed",
    "Cancelled", "Class Split", "Self-Study",
)
DEFAULT_STATUS: str = "Open"
OPEN_STATUSES: tuple[str, ...] = ("Open", "Allocated")

YEAR_GROUPS: tuple[str, ...] = ("Year 12", "Year 13", "Mixed")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS cover_requests (
    cover_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    absent_teacher  TEXT NOT NULL,
    absent_reason   TEXT,
    absent_date     TEXT NOT NULL,
    periods         TEXT,
    subject         TEXT,
    class_group_id  INTEGER,
    class_group_label TEXT,
    year_group      TEXT,
    room            TEXT,
    cover_type      TEXT NOT NULL DEFAULT 'Internal',
    cover_staff     TEXT,
    agency_id       INTEGER,
    agency_teacher  TEXT,
    status          TEXT NOT NULL DEFAULT 'Open',
    requested_on    TEXT,
    allocated_on    TEXT,
    confirmed_on    TEXT,
    completed_on    TEXT,
    cost            REAL,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cv_date     ON cover_requests(absent_date);
CREATE INDEX IF NOT EXISTS idx_cv_status   ON cover_requests(status);
CREATE INDEX IF NOT EXISTS idx_cv_teacher  ON cover_requests(absent_teacher);
CREATE INDEX IF NOT EXISTS idx_cv_agency   ON cover_requests(agency_id);
CREATE INDEX IF NOT EXISTS idx_cv_type     ON cover_requests(cover_type);
"""


# Added after the first release — applied with ALTER TABLE.
#   slot_id          the timetabled lesson (timetable_slots) being covered
#   staff_absence_id the staff_absences row that created the request
#   staff_id         the absent teacher's staff id, when known
#   source           how the row arrived: manual / staff_absence /
#                    attendance_cover
_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("slot_id", "INTEGER"),
    ("staff_absence_id", "INTEGER"),
    ("staff_id", "TEXT"),
    ("source", "TEXT"),
)


@dataclass
class CoverRequest:
    cover_id: int
    absent_teacher: str
    absent_reason: str | None
    absent_date: str
    periods: str | None
    subject: str | None
    class_group_id: int | None
    class_group_label: str | None
    year_group: str | None
    room: str | None
    cover_type: str
    cover_staff: str | None
    agency_id: int | None
    agency_teacher: str | None
    status: str
    requested_on: str | None
    allocated_on: str | None
    confirmed_on: str | None
    completed_on: str | None
    cost: float | None
    notes: str | None
    created_at: str
    updated_at: str
    slot_id: int | None = None
    staff_absence_id: int | None = None
    staff_id: str | None = None
    source: str | None = None

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    @property
    def cover_label(self) -> str:
        if self.cover_type == "Agency":
            return (f"Agency: {self.agency_teacher or '?'}"
                    + (f" (#{self.agency_id})"
                        if self.agency_id else ""))
        if self.cover_type == "Internal":
            return f"Internal: {self.cover_staff or '—'}"
        return self.cover_type


@dataclass
class CoverRow:
    request: CoverRequest
    agency_name: str | None = None


@dataclass
class Summary:
    total: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    by_reason: dict[str, int]
    open_count: int
    today_count: int
    this_week_count: int
    upcoming: int
    total_cost: float
    top_absent_teachers: dict[str, int]


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        existing = {r[1] for r in conn.execute(
            "PRAGMA table_info(cover_requests)").fetchall()}
        for col, decl in _NEW_COLUMNS:
            if col not in existing:
                conn.execute(
                    f"ALTER TABLE cover_requests ADD COLUMN {col} {decl}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cv_absence "
                     "ON cover_requests(staff_absence_id)")
        try:
            # One cover request per timetabled lesson per date.
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_cv_slot_date "
                "ON cover_requests(slot_id, absent_date) "
                "WHERE slot_id IS NOT NULL")
        except sqlite3.IntegrityError:
            logger.warning("cover_requests has duplicate (slot, date) "
                           "rows; unique index not created")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cv_slot_date_nu "
                         "ON cover_requests(slot_id, absent_date)")
        conn.commit()
    logger.debug("Cover schema ready at %s", DB_PATH)

    _DB_READY = True
    try:
        import_register_cover()
    except Exception:
        logger.exception("Could not fold attendance_cover rows into "
                         "cover_requests")


def _row(r: sqlite3.Row) -> CoverRequest:
    return CoverRequest(
        cover_id=r["cover_id"],
        absent_teacher=r["absent_teacher"],
        absent_reason=r["absent_reason"],
        absent_date=r["absent_date"], periods=r["periods"],
        subject=r["subject"],
        class_group_id=r["class_group_id"],
        class_group_label=r["class_group_label"],
        year_group=r["year_group"], room=r["room"],
        cover_type=r["cover_type"], cover_staff=r["cover_staff"],
        agency_id=r["agency_id"],
        agency_teacher=r["agency_teacher"],
        status=r["status"], requested_on=r["requested_on"],
        allocated_on=r["allocated_on"],
        confirmed_on=r["confirmed_on"],
        completed_on=r["completed_on"],
        cost=r["cost"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
        slot_id=_opt(r, "slot_id"),
        staff_absence_id=_opt(r, "staff_absence_id"),
        staff_id=_opt(r, "staff_id"),
        source=_opt(r, "source"),
    )


def _opt(r: sqlite3.Row, key: str) -> Any:
    try:
        return r[key]
    except (IndexError, KeyError):
        return None


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


def _validate_class_group(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        gid = int(value)
    except (TypeError, ValueError):
        raise ValidationError(
            "class_group_id must be a number") from None
    try:
        from education_system.systems.sixth_form.domain.academics.class_groups import (
            class_groups as _cg,
        )
        if _cg.get_group(gid) is None:
            raise ValidationError(f"No class group with id {gid}")
    except ValidationError:
        raise
    except Exception:
        pass
    return gid


def _validate_agency(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        aid = int(value)
    except (TypeError, ValueError):
        raise ValidationError(
            "agency_id must be a number") from None
    from education_system.systems.sixth_form.domain.academics.cover_agency import (
        cover_agency as _ag,
    )
    if _ag.get_agency(aid) is None:
        raise ValidationError(f"No cover agency with id {aid}")
    return aid


def _validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["absent_teacher"] = _require(payload.get("absent_teacher"),
                                          "Absent teacher").strip()

    reason = (payload.get("absent_reason") or "").strip()
    if reason and reason not in ABSENCE_REASONS:
        raise ValidationError(
            f"Reason must be one of: {', '.join(ABSENCE_REASONS)}")
    out["absent_reason"] = reason or None

    out["absent_date"] = _validate_date(payload.get("absent_date"),
                                            "Absent date",
                                            required=True)

    out["periods"]      = (payload.get("periods") or "").strip() or None
    out["subject"]      = (payload.get("subject") or "").strip() or None
    out["class_group_id"] = _validate_class_group(
        payload.get("class_group_id"))
    out["class_group_label"] = (payload.get("class_group_label")
                                  or "").strip() or None
    year = (payload.get("year_group") or "").strip()
    if year and year not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of: {', '.join(YEAR_GROUPS)}")
    out["year_group"] = year or None
    out["room"] = (payload.get("room") or "").strip() or None

    ctype = (payload.get("cover_type") or DEFAULT_COVER_TYPE).strip()
    if ctype not in COVER_TYPES:
        raise ValidationError(
            f"Cover type must be one of: {', '.join(COVER_TYPES)}")
    out["cover_type"] = ctype
    out["cover_staff"] = (payload.get("cover_staff") or "").strip() or None
    out["agency_id"]   = _validate_agency(payload.get("agency_id"))
    out["agency_teacher"] = (payload.get("agency_teacher")
                                or "").strip() or None
    if ctype == "Agency" and out["agency_id"] is None:
        raise ValidationError(
            "agency_id is required when cover_type='Agency'")
    if ctype != "Agency":
        # Soft-clear agency fields when cover_type changed away.
        out["agency_id"] = None
        out["agency_teacher"] = None

    status = (payload.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    out["requested_on"] = _validate_date(payload.get("requested_on"),
                                              "Requested on")
    out["allocated_on"] = _validate_date(payload.get("allocated_on"),
                                              "Allocated on")
    out["confirmed_on"] = _validate_date(payload.get("confirmed_on"),
                                              "Confirmed on")
    out["completed_on"] = _validate_date(payload.get("completed_on"),
                                              "Completed on")

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

    out["notes"] = (payload.get("notes") or "").strip() or None

    today = _dt.date.today().isoformat()
    if status == "Allocated" and not out["allocated_on"]:
        out["allocated_on"] = today
    if status == "Confirmed" and not out["confirmed_on"]:
        out["confirmed_on"] = today
    if status == "Completed" and not out["completed_on"]:
        out["completed_on"] = today
    if not out["requested_on"]:
        out["requested_on"] = today
    return out


# ── CRUD ──────────────────────────────────────────────────────────

def create_request(payload: dict[str, Any]) -> CoverRequest:
    init_db()
    p = _validate_payload(payload)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO cover_requests
                   (absent_teacher, absent_reason, absent_date,
                    periods, subject, class_group_id,
                    class_group_label, year_group, room, cover_type,
                    cover_staff, agency_id, agency_teacher, status,
                    requested_on, allocated_on, confirmed_on,
                    completed_on, cost, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["absent_teacher"], p["absent_reason"],
             p["absent_date"], p["periods"], p["subject"],
             p["class_group_id"], p["class_group_label"],
             p["year_group"], p["room"], p["cover_type"],
             p["cover_staff"], p["agency_id"],
             p["agency_teacher"], p["status"],
             p["requested_on"], p["allocated_on"],
             p["confirmed_on"], p["completed_on"],
             p["cost"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    try:
        _set_links(new_id, payload)
    except ValidationError:
        # The lesson already has a request: do not leave a half-linked
        # duplicate behind.
        with _connect() as conn:
            conn.execute("DELETE FROM cover_requests WHERE cover_id = ?",
                         (new_id,))
            conn.commit()
        raise
    _stamp_agency_use(p)
    out = get_request(new_id)
    assert out is not None
    if payload.get("_sync", True):
        _sync_register(out)
    logger.info(
        "Created cover #%d for %s on %s (type=%s, status=%s)",
        new_id, p["absent_teacher"], p["absent_date"],
        p["cover_type"], p["status"])
    return out


def _stamp_agency_use(p: dict[str, Any]) -> None:
    if p["cover_type"] != "Agency" or p["agency_id"] is None:
        return
    try:
        from education_system.systems.sixth_form.domain.academics.cover_agency import (
            cover_agency as _ag,
        )
        _ag.record_use(p["agency_id"], when=p["absent_date"])
    except Exception:
        logger.exception(
            "Could not stamp last_used_on for agency #%s",
            p["agency_id"])


def get_request(cover_id: int) -> CoverRequest | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM cover_requests WHERE cover_id = ?",
            (cover_id,)).fetchone()
        return _row(r) if r else None


def list_requests(
    *,
    status: str | None = None,
    cover_type: str | None = None,
    absent_teacher: str | None = None,
    subject_like: str | None = None,
    agency_id: int | None = None,
    open_only: bool = False,
    today_only: bool = False,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[CoverRequest]:
    init_db()
    clauses, args = [], []
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if cover_type:
        if cover_type not in COVER_TYPES:
            raise ValidationError(
                f"Cover type must be one of: "
                f"{', '.join(COVER_TYPES)}")
        clauses.append("cover_type = ?")
        args.append(cover_type)
    if absent_teacher:
        clauses.append("absent_teacher LIKE ?")
        args.append(f"%{absent_teacher.strip()}%")
    if subject_like:
        clauses.append("subject LIKE ?")
        args.append(f"%{subject_like.strip()}%")
    if agency_id is not None:
        clauses.append("agency_id = ?")
        args.append(int(agency_id))
    if open_only:
        ph = ",".join("?" * len(OPEN_STATUSES))
        clauses.append(f"status IN ({ph})")
        args.extend(OPEN_STATUSES)
    if today_only:
        clauses.append("absent_date = ?")
        args.append(_dt.date.today().isoformat())
    if date_from:
        clauses.append("absent_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("absent_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM cover_requests {where} "
           "ORDER BY absent_date ASC, "
           "CASE status "
           "  WHEN 'Open'        THEN 0 "
           "  WHEN 'Allocated'   THEN 1 "
           "  WHEN 'Confirmed'   THEN 2 "
           "  WHEN 'Completed'   THEN 3 "
           "  WHEN 'Class Split' THEN 4 "
           "  WHEN 'Self-Study'  THEN 5 "
           "  WHEN 'Cancelled'   THEN 6 "
           "  ELSE 7 END, "
           "cover_id ASC")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def list_requests_with_detail(**kwargs) -> list[CoverRow]:
    rows = list_requests(**kwargs)
    if not rows:
        return []
    from education_system.systems.sixth_form.domain.academics.cover_agency import (
        cover_agency as _ag,
    )
    agencies: dict[int, str] = {a.agency_id: a.name
                                  for a in _ag.list_agencies()}
    return [CoverRow(request=r,
                      agency_name=agencies.get(r.agency_id)
                                    if r.agency_id else None)
            for r in rows]


def update_request(cover_id: int,
                   payload: dict[str, Any]) -> CoverRequest:
    init_db()
    existing = get_request(cover_id)
    if existing is None:
        raise ValidationError(f"No cover request #{cover_id}")
    merged = {
        "absent_teacher":    payload.get("absent_teacher",
                                          existing.absent_teacher),
        "absent_reason":     payload.get("absent_reason",
                                          existing.absent_reason),
        "absent_date":       payload.get("absent_date",
                                          existing.absent_date),
        "periods":           payload.get("periods", existing.periods),
        "subject":           payload.get("subject", existing.subject),
        "class_group_id":    payload.get("class_group_id",
                                          existing.class_group_id),
        "class_group_label": payload.get("class_group_label",
                                          existing.class_group_label),
        "year_group":        payload.get("year_group",
                                          existing.year_group),
        "room":              payload.get("room", existing.room),
        "cover_type":        payload.get("cover_type",
                                          existing.cover_type),
        "cover_staff":       payload.get("cover_staff",
                                          existing.cover_staff),
        "agency_id":         payload.get("agency_id",
                                          existing.agency_id),
        "agency_teacher":    payload.get("agency_teacher",
                                          existing.agency_teacher),
        "status":            payload.get("status", existing.status),
        "requested_on":      payload.get("requested_on",
                                          existing.requested_on),
        "allocated_on":      payload.get("allocated_on",
                                          existing.allocated_on),
        "confirmed_on":      payload.get("confirmed_on",
                                          existing.confirmed_on),
        "completed_on":      payload.get("completed_on",
                                          existing.completed_on),
        "cost":              payload.get("cost", existing.cost),
        "notes":             payload.get("notes", existing.notes),
    }
    p = _validate_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE cover_requests SET
                   absent_teacher = ?, absent_reason = ?,
                   absent_date = ?, periods = ?, subject = ?,
                   class_group_id = ?, class_group_label = ?,
                   year_group = ?, room = ?, cover_type = ?,
                   cover_staff = ?, agency_id = ?, agency_teacher = ?,
                   status = ?, requested_on = ?, allocated_on = ?,
                   confirmed_on = ?, completed_on = ?, cost = ?,
                   notes = ?, updated_at = datetime('now')
               WHERE cover_id = ?""",
            (p["absent_teacher"], p["absent_reason"],
             p["absent_date"], p["periods"], p["subject"],
             p["class_group_id"], p["class_group_label"],
             p["year_group"], p["room"], p["cover_type"],
             p["cover_staff"], p["agency_id"],
             p["agency_teacher"], p["status"],
             p["requested_on"], p["allocated_on"],
             p["confirmed_on"], p["completed_on"],
             p["cost"], p["notes"], cover_id),
        )
        conn.commit()
    _set_links(cover_id, payload)
    _stamp_agency_use(p)
    out = get_request(cover_id)
    assert out is not None
    if payload.get("_sync", True):
        _sync_register(out)
    logger.info("Updated cover #%d (status=%s, type=%s)",
                cover_id, out.status, out.cover_type)
    return out


def set_status(cover_id: int, status: str, *,
               _sync: bool = True) -> CoverRequest:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return update_request(cover_id, {"status": status, "_sync": _sync})


def allocate(cover_id: int, *,
              cover_type: str = "Internal",
              cover_staff: str | None = None,
              agency_id: int | None = None,
              agency_teacher: str | None = None,
              check_free: bool = False,
              _sync: bool = True) -> CoverRequest:
    """Put cover against a request. With ``check_free=True`` an internal
    cover teacher who is timetabled, absent or already covering in that
    lesson's period is refused."""
    if check_free and cover_type == "Internal" and cover_staff:
        req = get_request(cover_id)
        if req is not None:
            busy = busy_reason(cover_staff, req)
            if busy:
                raise ValidationError(f"{cover_staff} is not free: {busy}")
    payload: dict[str, Any] = {
        "cover_type": cover_type,
        "cover_staff": cover_staff,
        "agency_id": agency_id,
        "agency_teacher": agency_teacher,
        "status": "Allocated",
        "allocated_on": _dt.date.today().isoformat(),
        "_sync": _sync,
    }
    return update_request(cover_id, payload)


def confirm(cover_id: int) -> CoverRequest:
    return set_status(cover_id, "Confirmed")


def complete(cover_id: int, *,
              cost: float | None = None) -> CoverRequest:
    payload: dict[str, Any] = {"status": "Completed"}
    if cost is not None:
        payload["cost"] = cost
    return update_request(cover_id, payload)


def cancel(cover_id: int, *, _sync: bool = True) -> CoverRequest:
    return set_status(cover_id, "Cancelled", _sync=_sync)


def delete_request(cover_id: int, *, _sync: bool = True) -> bool:
    init_db()
    existing = get_request(cover_id)
    if _sync and existing is not None and existing.slot_id:
        try:
            ac = _register_module()
            row = (ac.cover_for(existing.slot_id, existing.absent_date)
                   if same_database(ac.DB_PATH) else None)
            if row is not None:
                ac.delete_cover(row.cover_id, _sync=False)
        except Exception:
            logger.exception("Could not remove register cover for #%d",
                             cover_id)
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM cover_requests WHERE cover_id = ?",
            (cover_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted cover #%d", cover_id)
            return True
        return False


# ── Summary ───────────────────────────────────────────────────────

def summary(*, upcoming_window_days: int = 14) -> Summary:
    init_db()
    today_date = _dt.date.today()
    today = today_date.isoformat()
    horizon = (today_date
                + _dt.timedelta(days=upcoming_window_days)).isoformat()
    monday = today_date - _dt.timedelta(days=today_date.weekday())
    sunday = monday + _dt.timedelta(days=6)

    rows = list_requests()
    by_status = {s: 0 for s in STATUSES}
    by_type   = {t: 0 for t in COVER_TYPES}
    by_reason = {r: 0 for r in ABSENCE_REASONS}
    by_teacher: dict[str, int] = {}
    open_count = 0
    today_count = 0
    week_count = 0
    upcoming = 0
    total_cost = 0.0
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        by_type[r.cover_type] = by_type.get(r.cover_type, 0) + 1
        if r.absent_reason:
            by_reason[r.absent_reason] = by_reason.get(
                r.absent_reason, 0) + 1
        by_teacher[r.absent_teacher] = by_teacher.get(
            r.absent_teacher, 0) + 1
        if r.is_open:
            open_count += 1
            if today <= r.absent_date <= horizon:
                upcoming += 1
        if r.absent_date == today:
            today_count += 1
        if monday.isoformat() <= r.absent_date <= sunday.isoformat():
            week_count += 1
        if r.cost is not None:
            total_cost += r.cost

    top_teachers = dict(sorted(by_teacher.items(),
                                  key=lambda kv: kv[1],
                                  reverse=True)[:10])

    return Summary(
        total=len(rows),
        by_status=by_status,
        by_type=by_type,
        by_reason=by_reason,
        open_count=open_count,
        today_count=today_count,
        this_week_count=week_count,
        upcoming=upcoming,
        total_cost=round(total_cost, 2),
        top_absent_teachers=top_teachers,
    )


# ── Links (slot / staff absence) ──────────────────────────────────

def _set_links(cover_id: int, payload: dict[str, Any]) -> None:
    """Store the link columns a caller passed (others are left alone)."""
    fields: dict[str, Any] = {}
    if "slot_id" in payload:
        v = payload.get("slot_id")
        fields["slot_id"] = int(v) if v not in (None, "") else None
    if "staff_absence_id" in payload:
        v = payload.get("staff_absence_id")
        fields["staff_absence_id"] = int(v) if v not in (None, "") else None
    if "staff_id" in payload:
        fields["staff_id"] = (payload.get("staff_id") or "").strip() or None
    if "source" in payload:
        fields["source"] = (payload.get("source") or "").strip() or None
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    with _connect() as conn:
        try:
            conn.execute(f"UPDATE cover_requests SET {sets} "
                         "WHERE cover_id = ?", (*fields.values(), cover_id))
        except sqlite3.IntegrityError:
            raise ValidationError(
                "That lesson already has a cover request on that date"
            ) from None
        conn.commit()


def request_for_slot(slot_id: int, date: str) -> CoverRequest | None:
    """The cover request for one timetabled lesson on one date."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM cover_requests WHERE slot_id = ? "
            "AND absent_date = ? ORDER BY cover_id DESC LIMIT 1",
            (int(slot_id), _validate_date(date, "Date", required=True))
        ).fetchone()
    return _row(r) if r else None


def requests_for_absence(absence_id: int) -> list[CoverRequest]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM cover_requests WHERE staff_absence_id = ? "
            "ORDER BY absent_date, periods, cover_id",
            (int(absence_id),)).fetchall()
    return [_row(r) for r in rows]


def cover_progress(absence_id: int) -> dict[str, int]:
    """Status counts of the cover requests one absence created."""
    out: dict[str, int] = {}
    for r in requests_for_absence(absence_id):
        out[r.status] = out.get(r.status, 0) + 1
    return out


# ── The register's view of cover (attendance_cover) ───────────────
#
# cover_requests is the one cover store. attendance_cover (owned by the
# attendance registers) answers "who may take this register"; it is
# kept in step with cover_requests in both directions — every write on
# either side mirrors to the other with ``_sync=False`` so it does not
# bounce back.

#: attendance_cover.REASONS -> ABSENCE_REASONS
_REGISTER_TO_COVER_REASON = {
    "Illness": "Sickness",
    "Medical appointment": "Personal",
    "Training / CPD": "Training / CPD",
    "Trip": "Trip Cover",
    "Meeting": "External Meeting",
    "Compassionate": "Bereavement",
    "Exam duty": "Other",
    "Other": "Other",
}
_COVER_TO_REGISTER_REASON = {
    "Sickness": "Illness",
    "Personal": "Other",
    "Bereavement": "Compassionate",
    "Training / CPD": "Training / CPD",
    "External Meeting": "Meeting",
    "Trip Cover": "Trip",
    "INSET": "Training / CPD",
    "Other": "Other",
}
#: staff_absence.ABSENCE_TYPES -> ABSENCE_REASONS
_ABSENCE_TYPE_TO_REASON = {
    "Sickness": "Sickness",
    "Sickness — Long Term": "Sickness",
    "Medical Appointment": "Personal",
    "Hospital Appointment": "Personal",
    "Bereavement": "Bereavement",
    "Compassionate": "Bereavement",
}


def _register_module():
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_cover as _ac,
    )
    return _ac


def same_database(other_db_path: Any) -> bool:
    """True when ``other_db_path`` is the file cover_requests lives in.
    The two-way mirrors only run then — in production every sixth-form
    store is one file; a test that redirects one module but not the
    other must not have the mirror write into the real database."""
    import os
    try:
        return (os.path.realpath(str(other_db_path))
                == os.path.realpath(str(DB_PATH)))
    except (TypeError, ValueError):
        return False


def _cover_teacher(req: CoverRequest) -> str | None:
    if req.status not in ("Allocated", "Confirmed", "Completed"):
        return None
    if req.cover_type == "Internal":
        return req.cover_staff
    if req.cover_type == "Agency":
        return req.agency_teacher
    return None


def _sync_register(req: CoverRequest) -> None:
    """Mirror one cover request onto the register cover table."""
    if not req.slot_id:
        return
    try:
        ac = _register_module()
        if not same_database(ac.DB_PATH):
            logger.debug("Register cover lives in another database; "
                         "cover #%d not mirrored", req.cover_id)
            return
        if req.status in ("Cancelled", "Class Split"):
            row = ac.cover_for(req.slot_id, req.absent_date)
            if row is not None and row.is_live:
                ac.cancel(row.cover_id, reason=f"Cover #{req.cover_id} "
                          f"{req.status.lower()}", _sync=False)
            return
        ac.arrange(
            req.slot_id, req.absent_date,
            absent_teacher=req.absent_teacher,
            cover_teacher=_cover_teacher(req),
            reason=_COVER_TO_REGISTER_REASON.get(
                req.absent_reason or "Other", "Other"),
            room=req.room, notes=f"Cover request #{req.cover_id}",
            _sync=False)
    except Exception:
        logger.exception("Could not mirror cover #%d to the register",
                         req.cover_id)


def upsert_for_slot(slot_id: int, date: str, *,
                    absent_teacher: str | None,
                    cover_teacher: str | None,
                    register_reason: str | None,
                    room: str | None,
                    register_state: str) -> CoverRequest:
    """Called by attendance_cover after its own write: make the
    cover_requests row for (slot, date) say the same thing."""
    init_db()
    existing = request_for_slot(slot_id, date)
    if register_state == "Cancelled":
        if existing is not None and existing.status not in (
                "Cancelled", "Completed"):
            return cancel(existing.cover_id, _sync=False)
        if existing is not None:
            return existing
    if register_state == "Cancelled":
        status = "Cancelled"
    else:
        status = "Allocated" if cover_teacher else "Open"
    reason = _REGISTER_TO_COVER_REASON.get(register_reason or "Other",
                                           "Other")
    if existing is None:
        details = _lesson_details(slot_id)
        return create_request({
            "absent_teacher": absent_teacher or details.get("teacher")
            or "Unknown",
            "absent_reason": reason, "absent_date": date,
            "room": room or details.get("room"),
            "periods": details.get("periods"),
            "subject": details.get("subject"),
            "class_group_id": details.get("class_group_id"),
            "class_group_label": details.get("class_group_label"),
            "year_group": details.get("year_group"),
            "cover_type": "Internal", "cover_staff": cover_teacher,
            "status": status, "slot_id": slot_id,
            "source": "attendance_cover", "_sync": False,
        })
    payload: dict[str, Any] = {"_sync": False}
    if absent_teacher:
        payload["absent_teacher"] = absent_teacher
    if room:
        payload["room"] = room
    if cover_teacher:
        same = (existing.cover_type == "Internal"
                and (existing.cover_staff or "").lower()
                == cover_teacher.lower())
        if not (same and existing.status in ("Confirmed", "Completed")):
            payload.update(cover_type="Internal", cover_staff=cover_teacher,
                           status="Allocated")
    elif existing.status in ("Cancelled",):
        payload["status"] = "Open"
    return update_request(existing.cover_id, payload)


def import_register_cover() -> int:
    """Fold attendance_cover rows that predate the link into
    cover_requests (idempotent — a lesson already present is skipped).
    Reads attendance_cover read-only."""
    import sys
    mod = sys.modules.get("education_system.systems.sixth_form.domain."
                          "academics.attendance.attendance_cover")
    db = str(getattr(mod, "DB_PATH", None)
             or paths.SIXTH_FORM_ATTENDANCE_DB)
    try:
        src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return 0
    src.row_factory = sqlite3.Row
    try:
        if not src.execute("SELECT 1 FROM sqlite_master WHERE type='table'"
                           " AND name='attendance_cover'").fetchone():
            return 0
        rows = src.execute("SELECT * FROM attendance_cover").fetchall()
    except sqlite3.Error:
        return 0
    finally:
        src.close()
    with _connect() as conn:
        have = {(r[0], r[1]) for r in conn.execute(
            "SELECT slot_id, absent_date FROM cover_requests "
            "WHERE slot_id IS NOT NULL").fetchall()}
    added = 0
    for r in rows:
        if (r["slot_id"], r["date"]) in have:
            continue
        try:
            upsert_for_slot(r["slot_id"], r["date"],
                            absent_teacher=r["absent_teacher"],
                            cover_teacher=r["cover_teacher"],
                            register_reason=r["reason"], room=r["room"],
                            register_state=r["state"])
            added += 1
        except ValidationError as e:
            logger.warning("Register cover #%s not imported: %s",
                           r["cover_id"], e)
    if added:
        logger.info("Imported %d attendance_cover row(s) into "
                    "cover_requests", added)
    return added


# ── Timetable look-ups ────────────────────────────────────────────

def _lesson_details(slot_id: int) -> dict[str, Any]:
    """Group, subject, room, period and usual teacher for one slot."""
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _tt,
    )
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    from education_system.systems.sixth_form.domain.academics.courses import (
        courses as _crs,
    )
    slot = _tt.get_slot(int(slot_id))
    if slot is None:
        return {}
    group = _cg.get_group(slot.group_id)
    course = _crs.get_course(group.course_id) if group else None
    year = None
    if course is not None and getattr(course, "year_group", None):
        year = f"Year {course.year_group}" \
            if f"Year {course.year_group}" in YEAR_GROUPS else None
    return {
        "slot": slot,
        "day": slot.day, "period": slot.period,
        "periods": str(slot.period),
        "room": slot.room or (group.room if group else None),
        "class_group_id": slot.group_id,
        "class_group_label": group.group_name if group else None,
        "subject": (course.subject if course else None),
        "year_group": year,
        "teacher": ((group.teacher if group and group.teacher else None)
                    or (course.teacher if course else None)),
    }


def staff_aliases(staff_obj: Any) -> set[str]:
    """The strings a timetable might use for one member of staff —
    lower-cased (class group / course ``teacher`` is free text)."""
    out: set[str] = set()
    first = (getattr(staff_obj, "first_name", "") or "").strip()
    last = (getattr(staff_obj, "last_name", "") or "").strip()
    title = (getattr(staff_obj, "title", "") or "").strip()
    for s in (f"{first} {last}", f"{title} {last}" if title else "",
              f"{title} {first} {last}" if title else "",
              getattr(staff_obj, "staff_id", "") or "",
              (getattr(staff_obj, "email", "") or "").split("@")[0]):
        s = " ".join(s.split())
        if s:
            out.add(s.lower())
    return out


def _resolve_staff(who: str) -> Any:
    """A staff record from an id or a name; None if not found."""
    from education_system.systems.sixth_form.domain.staff import (
        staff as _staff,
    )
    s = (who or "").strip()
    if not s:
        return None
    hit = _staff.get_staff(s.upper())
    if hit is not None:
        return hit
    want = " ".join(s.split()).lower()
    for st in _staff.list_staff():
        if want in staff_aliases(st):
            return st
    return None


def slots_for_staff(staff_obj: Any) -> list[Any]:
    """Every timetable slot this member of staff normally teaches."""
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as _tt,
    )
    seen: dict[int, Any] = {}
    for alias in staff_aliases(staff_obj):
        for slot in _tt.list_slots(teacher=alias):
            seen[slot.slot_id] = slot
    return sorted(seen.values(), key=lambda s: (s.day, s.period))


def _closed_by_calendar(day: _dt.date) -> bool:
    """True when the academic calendar has the college closed that day.
    No calendar for the date means 'open' (weekdays only)."""
    try:
        from education_system.systems.sixth_form.domain.academics.academic_year import (
            academic_year as _ay,
        )
        iso = day.isoformat()
        for y in _ay.list_years():
            if y.start_date <= iso <= y.end_date:
                return _ay.teaching_days_in(
                    y.year_id, date_from=iso, date_to=iso,
                    half_days=True) == 0
    except Exception:
        logger.debug("Academic calendar unavailable for %s", day,
                     exc_info=True)
    return False


def school_days(date_from: str, date_to: str) -> list[str]:
    start = _dt.date.fromisoformat(date_from)
    end = _dt.date.fromisoformat(date_to)
    out: list[str] = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5 and not _closed_by_calendar(cur):
            out.append(cur.isoformat())
        cur += _dt.timedelta(days=1)
    return out


# ── Staff absence → cover requests ────────────────────────────────

#: How far ahead an open absence creates cover requests. Long absences
#: are extended day by day by :func:`sync_open_absences`.
ABSENCE_HORIZON_DAYS: int = 14


@dataclass
class AbsenceSync:
    absence_id: int
    created: int = 0
    reopened: int = 0
    cancelled: int = 0
    lessons_found: int = 0
    note: str | None = None


def _absence_last_day(a: Any) -> str | None:
    """Last day off (inclusive); None for open-ended."""
    back = a.actual_return or a.expected_return
    if not back:
        return None
    last = _dt.date.fromisoformat(back) - _dt.timedelta(days=1)
    return max(last.isoformat(), a.absence_date)


def sync_absence(absence: Any, *, today: str | None = None) -> AbsenceSync:
    """Make cover_requests match one staff absence: a request for every
    timetabled lesson the teacher misses (from today, up to the horizon),
    and open requests cancelled for days no longer covered by the
    absence. Idempotent."""
    init_db()
    if isinstance(absence, int):
        from education_system.systems.sixth_form.domain.staff.staff_absence import (
            staff_absence as _sa,
        )
        absence = _sa.get_absence(absence)
        if absence is None:
            raise ValidationError("No such staff absence")
    res = AbsenceSync(absence_id=absence.absence_id)
    now = today or _dt.date.today().isoformat()
    existing = requests_for_absence(absence.absence_id)

    wants_cover = (absence.status != "Cancelled"
                   and absence.cover_required
                   and absence.cover_source not in ("Not Required",
                                                    "Cancelled"))
    first = max(absence.absence_date, now)
    last_day = _absence_last_day(absence)
    horizon = (_dt.date.fromisoformat(first)
               + _dt.timedelta(days=ABSENCE_HORIZON_DAYS - 1)).isoformat()
    upto = min(last_day, horizon) if last_day else horizon
    if absence.status in ("Returned", "Closed") and not last_day:
        upto = absence.absence_date

    def _outside(d: str) -> bool:
        return (d < absence.absence_date
                or (last_day is not None and d > last_day)
                or (absence.status in ("Returned", "Closed")
                    and absence.actual_return is not None
                    and d >= absence.actual_return))

    # Cancel what no longer applies (never touches past or finished rows).
    for r in existing:
        if r.status not in OPEN_STATUSES or r.absent_date < now:
            continue
        if not wants_cover or _outside(r.absent_date):
            cancel(r.cover_id)
            res.cancelled += 1
    if not wants_cover:
        res.note = "Absence does not need cover"
        return res

    st = _resolve_staff(absence.staff_id)
    if st is None:
        res.note = f"No staff record {absence.staff_id}"
        return res
    slots = slots_for_staff(st)
    if not slots or first > upto:
        res.note = ("No timetabled lessons for this teacher"
                    if not slots else "No school days left to cover")
        return res
    by_day: dict[int, list[Any]] = {}
    for sl in slots:
        by_day.setdefault(sl.day, []).append(sl)
    name = " ".join(f"{st.first_name} {st.last_name}".split())
    reason = _ABSENCE_TYPE_TO_REASON.get(absence.absence_type, "Other")
    for d in school_days(first, upto):
        if _outside(d):
            continue
        day_no = _dt.date.fromisoformat(d).weekday() + 1
        for sl in by_day.get(day_no, []):
            res.lessons_found += 1
            have = request_for_slot(sl.slot_id, d)
            if have is not None:
                if (have.status == "Cancelled"
                        and have.staff_absence_id == absence.absence_id):
                    set_status(have.cover_id, "Open")
                    res.reopened += 1
                elif have.staff_absence_id is None:
                    _set_links(have.cover_id, {
                        "staff_absence_id": absence.absence_id,
                        "staff_id": st.staff_id})
                continue
            det = _lesson_details(sl.slot_id)
            create_request({
                "absent_teacher": name, "absent_reason": reason,
                "absent_date": d, "periods": det.get("periods"),
                "subject": det.get("subject"),
                "class_group_id": det.get("class_group_id"),
                "class_group_label": det.get("class_group_label"),
                "year_group": det.get("year_group"),
                "room": det.get("room"), "cover_type": "Internal",
                "status": "Open",
                "notes": f"From staff absence #{absence.absence_id} "
                         f"({absence.absence_type})",
                "slot_id": sl.slot_id,
                "staff_absence_id": absence.absence_id,
                "staff_id": st.staff_id, "source": "staff_absence",
            })
            res.created += 1
    logger.info("Absence #%d cover sync: %d created, %d reopened, "
                "%d cancelled", absence.absence_id, res.created,
                res.reopened, res.cancelled)
    return res


def sync_open_absences(*, today: str | None = None) -> list[AbsenceSync]:
    """Run :func:`sync_absence` over every open staff absence — extends
    long absences into the rolling horizon. Safe to run daily."""
    from education_system.systems.sixth_form.domain.staff.staff_absence import (
        staff_absence as _sa,
    )
    out: list[AbsenceSync] = []
    for a in _sa.list_absences():
        if a.is_open:
            out.append(sync_absence(a, today=today))
    return out


# ── Who is free to cover ──────────────────────────────────────────

#: Roles that can stand in front of a class.
COVER_ROLES: tuple[str, ...] = (
    "Cover Teacher", "Teacher", "Subject Lead", "Head of Department",
    "Head of Year", "Head of Sixth Form", "Tutor", "Vice Principal",
)


@dataclass
class CoverSuggestion:
    staff_id: str
    name: str
    role: str
    department: str
    same_department: bool
    recent_cover: int

    @property
    def label(self) -> str:
        bits = [self.role, self.department]
        if self.same_department:
            bits.append("same subject")
        bits.append(f"{self.recent_cover} cover(s) in last 30 days")
        return f"{self.name} ({self.staff_id}) — " + ", ".join(bits)


def _periods_of(req: CoverRequest) -> set[int]:
    out: set[int] = set()
    for tok in re.split(r"[,\s;/-]+", req.periods or ""):
        tok = tok.strip().upper().lstrip("P")
        if tok.isdigit():
            out.add(int(tok))
    return out


def _absent_on(staff_id: str, day: str) -> bool:
    from education_system.systems.sixth_form.domain.staff.staff_absence import (
        staff_absence as _sa,
    )
    for a in _sa.list_absences(staff_id=staff_id):
        if a.status == "Cancelled" or a.absence_date > day:
            continue
        last = _absence_last_day(a)
        if last is None:
            if a.is_open or a.absence_date == day:
                return True
        elif day <= last:
            return True
    return False


def busy_reason(who: str, req: CoverRequest) -> str | None:
    """Why ``who`` cannot cover ``req`` — or None when they are free."""
    st = _resolve_staff(who)
    if st is None:
        return None   # an outside name: nothing to check against
    aliases = staff_aliases(st)
    if req.absent_teacher and \
            " ".join(req.absent_teacher.split()).lower() in aliases:
        return "they are the absent teacher"
    if _absent_on(st.staff_id, req.absent_date):
        return f"absent on {req.absent_date}"
    periods = _periods_of(req)
    day_no = _dt.date.fromisoformat(req.absent_date).weekday() + 1
    for sl in slots_for_staff(st):
        if sl.day == day_no and (not periods or sl.period in periods):
            return f"teaching period {sl.period}"
    for other in list_requests(date_from=req.absent_date,
                               date_to=req.absent_date):
        if other.cover_id == req.cover_id or other.status not in (
                "Allocated", "Confirmed", "Completed"):
            continue
        if (other.cover_staff or "").lower() not in aliases:
            continue
        if not periods or not _periods_of(other) or \
                periods & _periods_of(other):
            return f"already covering #{other.cover_id}"
    return None


def suggest_cover_staff(cover_id: int, *, limit: int = 15
                        ) -> list[CoverSuggestion]:
    """Staff free at that lesson's time, best first: same subject, then
    whoever has covered least in the last 30 days."""
    from education_system.systems.sixth_form.domain.staff import (
        staff as _staff,
    )
    req = get_request(cover_id)
    if req is None:
        raise ValidationError(f"No cover request #{cover_id}")
    since = (_dt.date.fromisoformat(req.absent_date)
             - _dt.timedelta(days=30)).isoformat()
    load: dict[str, int] = {}
    for r in list_requests(date_from=since, date_to=req.absent_date):
        if r.status in ("Allocated", "Confirmed", "Completed") \
                and r.cover_staff:
            k = r.cover_staff.lower()
            load[k] = load.get(k, 0) + 1
    subject = (req.subject or "").lower()
    out: list[CoverSuggestion] = []
    for st in _staff.list_staff(active_only=True):
        if st.role not in COVER_ROLES:
            continue
        if busy_reason(st.staff_id, req):
            continue
        aliases = staff_aliases(st)
        dept = (st.department or "").lower()
        same = bool(subject and dept and (dept in subject or subject in dept))
        out.append(CoverSuggestion(
            staff_id=st.staff_id,
            name=" ".join(f"{st.first_name} {st.last_name}".split()),
            role=st.role, department=st.department,
            same_department=same,
            recent_cover=sum(load.get(a, 0) for a in aliases)))
    out.sort(key=lambda c: (not c.same_department, c.recent_cover,
                            c.role != "Cover Teacher", c.name))
    return out[:limit]
