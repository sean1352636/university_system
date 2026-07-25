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
from education_system.systems.sixth_form.infrastructure import paths
from education_system.systems.sixth_form.domain.academics.cover import (
    cover as data,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.COVER_DB


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
    paths.ensure_directories()
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
    logger.debug("Cover schema ready at %s", DB_PATH)

    _DB_READY = True


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
    _stamp_agency_use(p)
    out = get_request(new_id)
    assert out is not None
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
    _stamp_agency_use(p)
    out = get_request(cover_id)
    assert out is not None
    logger.info("Updated cover #%d (status=%s, type=%s)",
                cover_id, out.status, out.cover_type)
    return out


def set_status(cover_id: int, status: str) -> CoverRequest:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    return update_request(cover_id, {"status": status})


def allocate(cover_id: int, *,
              cover_type: str = "Internal",
              cover_staff: str | None = None,
              agency_id: int | None = None,
              agency_teacher: str | None = None) -> CoverRequest:
    payload: dict[str, Any] = {
        "cover_type": cover_type,
        "cover_staff": cover_staff,
        "agency_id": agency_id,
        "agency_teacher": agency_teacher,
        "status": "Allocated",
        "allocated_on": _dt.date.today().isoformat(),
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


def cancel(cover_id: int) -> CoverRequest:
    return set_status(cover_id, "Cancelled")


def delete_request(cover_id: int) -> bool:
    init_db()
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
