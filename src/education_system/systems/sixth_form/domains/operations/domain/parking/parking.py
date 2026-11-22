"""Parking permits data layer for the Sixth Form System.

Two tables:

* ``parking_spaces``  — car park + space number (unique together) and a
  space type (Staff / Student / Disabled / Visitor / EV).
* ``parking_permits`` — one permit per vehicle per holder. The holder is
  *exactly one* of a member of staff or a student (CHECK constraint).
  Vehicle registration is stored normalised (upper case, no spaces).

A permit may be allocated a space. An active permit holds its space
exclusively (partial unique index); permits past their expiry date are
flipped to Expired by :func:`expire_lapsed` before any space check, so a
lapsed permit never blocks a space.

Space rules: Visitor spaces are never allocated to permits; Staff and
Student spaces go to the matching holder type; Disabled spaces need a
Blue Badge permit. EV spaces are open to any holder.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from education_system.systems.sixth_form.infrastructure import database as _sql
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system import paths

logger = logging.getLogger(__name__)

# Same file as the staff and students tables the permit FKs point at.
DB_PATH = paths.SIXTH_FORM_STUDENTS_DB

SPACE_TYPES: tuple[str, ...] = ("Staff", "Student", "Disabled", "Visitor", "EV")
DEFAULT_SPACE_TYPE = "Staff"

HOLDER_TYPES: tuple[str, ...] = ("Staff", "Student")

PERMIT_TYPES: tuple[str, ...] = (
    "Annual", "Term", "Temporary", "Blue Badge", "Car Share")
DEFAULT_PERMIT_TYPE = "Annual"

ACTIVE = "Active"
REVOKED = "Revoked"
EXPIRED = "Expired"
STATUSES: tuple[str, ...] = (ACTIVE, REVOKED, EXPIRED)

PERMIT_PREFIX = "PK"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Loose UK registration check: current (AB12CDE), prefix (A123BCD),
# suffix (ABC123D), dateless and NI plates all fit 2-8 alphanumerics
# containing at least one letter and one digit.
_REG_RE = re.compile(r"^(?=.*[A-Z])(?=.*\d)[A-Z0-9]{2,8}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS parking_spaces (
    space_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    car_park      TEXT NOT NULL,
    space_number  TEXT NOT NULL,
    space_type    TEXT NOT NULL DEFAULT 'Staff',
    active        INTEGER NOT NULL DEFAULT 1,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(car_park, space_number)
);

CREATE TABLE IF NOT EXISTS parking_permits (
    permit_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    permit_number  TEXT NOT NULL UNIQUE,
    holder_type    TEXT NOT NULL,
    staff_id       TEXT,
    student_id     TEXT,
    vehicle_reg    TEXT NOT NULL,
    vehicle_make   TEXT,
    vehicle_colour TEXT,
    permit_type    TEXT NOT NULL DEFAULT 'Annual',
    issued_on      TEXT NOT NULL,
    expires_on     TEXT NOT NULL,
    space_id       INTEGER,
    status         TEXT NOT NULL DEFAULT 'Active',
    revoked_on     TEXT,
    revoked_reason TEXT,
    issued_by      TEXT,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now')),
    CHECK ((staff_id IS NULL) <> (student_id IS NULL)),
    FOREIGN KEY (staff_id)   REFERENCES staff(staff_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE,
    FOREIGN KEY (space_id)   REFERENCES parking_spaces(space_id)
);

CREATE INDEX IF NOT EXISTS idx_pk_permit_reg    ON parking_permits(vehicle_reg);
CREATE INDEX IF NOT EXISTS idx_pk_permit_expiry ON parking_permits(expires_on);
CREATE INDEX IF NOT EXISTS idx_pk_permit_staff  ON parking_permits(staff_id);
CREATE INDEX IF NOT EXISTS idx_pk_permit_student ON parking_permits(student_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pk_space_one_active
    ON parking_permits(space_id)
    WHERE status = 'Active' AND space_id IS NOT NULL;
"""


class ValidationError(ValueError):
    pass


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Space:
    space_id: int
    car_park: str
    space_number: str
    space_type: str
    active: bool
    notes: str | None
    created_at: str
    updated_at: str
    permit_number: str | None = None   # active permit holding it, if any

    @property
    def label(self) -> str:
        return f"{self.car_park} {self.space_number}"

    @property
    def is_free(self) -> bool:
        return self.active and not self.permit_number


@dataclass
class Permit:
    permit_id: int
    permit_number: str
    holder_type: str
    staff_id: str | None
    student_id: str | None
    vehicle_reg: str
    vehicle_make: str | None
    vehicle_colour: str | None
    permit_type: str
    issued_on: str
    expires_on: str
    space_id: int | None
    status: str
    revoked_on: str | None
    revoked_reason: str | None
    issued_by: str | None
    notes: str | None
    created_at: str
    updated_at: str
    holder_name: str | None = None
    space_label: str | None = None

    @property
    def holder_id(self) -> str:
        return self.staff_id or self.student_id or ""

    @property
    def is_active(self) -> bool:
        return (self.status == ACTIVE
                and self.expires_on >= _dt.date.today().isoformat())

    def days_to_expiry(self, today: _dt.date | None = None) -> int:
        d = today or _dt.date.today()
        return (_dt.date.fromisoformat(self.expires_on) - d).days


@dataclass
class ParkingSummary:
    spaces: int = 0
    free_spaces: int = 0
    by_space_type: dict[str, int] = field(default_factory=dict)
    free_by_type: dict[str, int] = field(default_factory=dict)
    permits: int = 0
    active_permits: int = 0
    staff_permits: int = 0
    student_permits: int = 0
    expiring_soon: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    by_permit_type: dict[str, int] = field(default_factory=dict)


# ── DB plumbing ─────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[_sql.Connection]:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    from education_system.systems.sixth_form.domain.staff import (
        staff as _staff,
    )
    _students.init_db()
    _staff.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Parking schema ready at %s", DB_PATH)
    _DB_READY = True


def _space(r: _sql.Row) -> Space:
    keys = r.keys()
    return Space(
        space_id=r["space_id"], car_park=r["car_park"],
        space_number=r["space_number"], space_type=r["space_type"],
        active=bool(r["active"]), notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
        permit_number=r["permit_number"] if "permit_number" in keys
        else None)


def _permit(r: _sql.Row) -> Permit:
    keys = r.keys()
    name = None
    if "holder_first" in keys:
        name = " ".join(p for p in (r["holder_first"], r["holder_last"])
                        if p) or None
    label = None
    if "car_park" in keys and r["car_park"]:
        label = f"{r['car_park']} {r['space_number']}"
    return Permit(
        permit_id=r["permit_id"], permit_number=r["permit_number"],
        holder_type=r["holder_type"], staff_id=r["staff_id"],
        student_id=r["student_id"], vehicle_reg=r["vehicle_reg"],
        vehicle_make=r["vehicle_make"],
        vehicle_colour=r["vehicle_colour"],
        permit_type=r["permit_type"], issued_on=r["issued_on"],
        expires_on=r["expires_on"], space_id=r["space_id"],
        status=r["status"], revoked_on=r["revoked_on"],
        revoked_reason=r["revoked_reason"], issued_by=r["issued_by"],
        notes=r["notes"], created_at=r["created_at"],
        updated_at=r["updated_at"], holder_name=name, space_label=label)


# ── Validation helpers ──────────────────────────────────────────────

def _text(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _require(v: Any, label: str) -> str:
    s = _text(v)
    if not s:
        raise ValidationError(f"{label} is required")
    return s


def _date(v: Any, label: str, *, required: bool = False) -> str | None:
    s = _text(v)
    if not s:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _choice(v: Any, options: tuple[str, ...], label: str,
            default: str | None = None) -> str:
    s = _text(v) or default
    for o in options:
        if s and s.lower() == o.lower():
            return o
    raise ValidationError(f"{label} must be one of: {', '.join(options)}")


def normalise_reg(v: Any) -> str:
    """``ab12 cde`` -> ``AB12CDE``; raises if it cannot be a UK plate."""
    s = re.sub(r"[\s\-]", "", str(v or "")).upper()
    if not s:
        raise ValidationError("Vehicle registration is required")
    if not _REG_RE.match(s):
        raise ValidationError(
            f"'{v}' does not look like a UK registration "
            "(2-8 letters and digits, at least one of each)")
    return s


def _holder(payload: dict[str, Any]) -> tuple[str, str | None, str | None]:
    htype = _choice(payload.get("holder_type"), HOLDER_TYPES, "Holder type")
    staff_id = _text(payload.get("staff_id"))
    student_id = _text(payload.get("student_id"))
    # Accept a generic holder_id too, routed by holder_type.
    hid = _text(payload.get("holder_id"))
    if hid:
        if htype == "Staff":
            staff_id = staff_id or hid
        else:
            student_id = student_id or hid
    if htype == "Staff":
        student_id = None
        if not staff_id:
            raise ValidationError("Staff member is required")
        staff_id = staff_id.upper()
        from education_system.systems.sixth_form.domain.staff import (
            staff as _staff,
        )
        if _staff.get_staff(staff_id) is None:
            raise ValidationError(f"No staff with id {staff_id}")
    else:
        staff_id = None
        if not student_id:
            raise ValidationError("Student is required")
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        if _students.get_student(student_id) is None:
            raise ValidationError(f"No student with id {student_id}")
    return htype, staff_id, student_id


# ── Spaces ──────────────────────────────────────────────────────────

_SPACE_SELECT = (
    "SELECT s.*, p.permit_number FROM parking_spaces s "
    "LEFT JOIN parking_permits p ON p.space_id = s.space_id "
    "AND p.status = 'Active'")


def create_space(payload: dict[str, Any]) -> Space:
    init_db()
    car_park = _require(payload.get("car_park"), "Car park")
    number = _require(payload.get("space_number"), "Space number")
    stype = _choice(payload.get("space_type"), SPACE_TYPES, "Space type",
                    DEFAULT_SPACE_TYPE)
    with _connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO parking_spaces (car_park, space_number, "
                "space_type, active, notes) VALUES (?, ?, ?, ?, ?)",
                (car_park, number, stype,
                 0 if payload.get("active") is False else 1,
                 _text(payload.get("notes"))))
        except _sql.IntegrityError:
            raise ValidationError(
                f"Space {number} already exists in {car_park}") from None
        new_id = cur.lastrowid
    out = get_space(new_id)
    assert out is not None
    return out


def add_spaces(car_park: str, first: int, count: int, *,
               space_type: str = DEFAULT_SPACE_TYPE,
               prefix: str = "") -> list[Space]:
    """Number a run of spaces in a car park; existing numbers are skipped."""
    if count < 1 or count > 500:
        raise ValidationError("Count must be between 1 and 500")
    made: list[Space] = []
    for n in range(first, first + count):
        try:
            made.append(create_space({"car_park": car_park,
                                      "space_number": f"{prefix}{n}",
                                      "space_type": space_type}))
        except ValidationError as e:
            if "already exists" not in str(e):
                raise
    return made


def update_space(space_id: int, payload: dict[str, Any]) -> Space:
    existing = get_space(space_id)
    if existing is None:
        raise ValidationError(f"No parking space #{space_id}")
    car_park = _require(payload.get("car_park", existing.car_park),
                        "Car park")
    number = _require(payload.get("space_number", existing.space_number),
                      "Space number")
    stype = _choice(payload.get("space_type", existing.space_type),
                    SPACE_TYPES, "Space type")
    active = bool(payload.get("active", existing.active))
    if existing.permit_number:
        if not active:
            raise ValidationError(
                f"Space is held by permit {existing.permit_number} — "
                "move the permit first")
        if stype != existing.space_type:
            holder = get_permit_by_number(existing.permit_number)
            if holder is not None:
                _check_space_fits(holder.holder_type, holder.permit_type,
                                  stype)
    with _connect() as conn:
        try:
            conn.execute(
                "UPDATE parking_spaces SET car_park=?, space_number=?, "
                "space_type=?, active=?, notes=?, "
                "updated_at=datetime('now') WHERE space_id=?",
                (car_park, number, stype, 1 if active else 0,
                 _text(payload.get("notes", existing.notes)), space_id))
        except _sql.IntegrityError:
            raise ValidationError(
                f"Space {number} already exists in {car_park}") from None
    out = get_space(space_id)
    assert out is not None
    return out


def get_space(space_id: int) -> Space | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(f"{_SPACE_SELECT} WHERE s.space_id=?",
                         (space_id,)).fetchone()
    return _space(r) if r else None


def list_spaces(*, car_park: str | None = None,
                space_type: str | None = None,
                free_only: bool = False,
                active_only: bool = False) -> list[Space]:
    init_db()
    expire_lapsed()
    clauses: list[str] = []
    args: list[Any] = []
    if car_park:
        clauses.append("LOWER(s.car_park) = LOWER(?)")
        args.append(car_park.strip())
    if space_type:
        clauses.append("s.space_type = ?")
        args.append(_choice(space_type, SPACE_TYPES, "Space type"))
    if active_only or free_only:
        clauses.append("s.active = 1")
    if free_only:
        clauses.append("p.permit_id IS NULL")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"{_SPACE_SELECT}{where} ORDER BY s.car_park COLLATE NOCASE, "
           "LENGTH(s.space_number), s.space_number")
    with _connect() as conn:
        return [_space(r) for r in conn.execute(sql, args).fetchall()]


def car_parks() -> list[str]:
    init_db()
    with _connect() as conn:
        return [r[0] for r in conn.execute(
            "SELECT DISTINCT car_park FROM parking_spaces "
            "ORDER BY car_park COLLATE NOCASE").fetchall()]


def delete_space(space_id: int) -> bool:
    """Remove a space no permit has ever pointed at; otherwise deactivate."""
    init_db()
    with _connect() as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM parking_permits WHERE space_id=?",
            (space_id,)).fetchone()[0]
        if n:
            raise ValidationError(
                "Permits reference this space — deactivate it instead")
        cur = conn.execute("DELETE FROM parking_spaces WHERE space_id=?",
                           (space_id,))
    return bool(cur.rowcount)


def _check_space_fits(holder_type: str, permit_type: str,
                      space_type: str) -> None:
    if space_type == "Visitor":
        raise ValidationError("Visitor spaces are not allocated to permits")
    if space_type in ("Staff", "Student") and space_type != holder_type:
        raise ValidationError(
            f"A {space_type} space cannot go to a {holder_type} permit")
    if space_type == "Disabled" and permit_type != "Blue Badge":
        raise ValidationError("Disabled spaces need a Blue Badge permit")


def _validate_space_for(space_id: Any, holder_type: str,
                        permit_type: str,
                        permit_id: int | None = None) -> int | None:
    if space_id in (None, ""):
        return None
    try:
        sid = int(space_id)
    except (TypeError, ValueError):
        raise ValidationError("Space must be a number") from None
    space = get_space(sid)
    if space is None:
        raise ValidationError(f"No parking space #{sid}")
    if not space.active:
        raise ValidationError(f"Space {space.label} is not in use")
    _check_space_fits(holder_type, permit_type, space.space_type)
    if space.permit_number:
        holder = get_permit_by_number(space.permit_number)
        if holder is not None and holder.permit_id != permit_id:
            raise ValidationError(
                f"Space {space.label} is already held by permit "
                f"{space.permit_number}")
    return sid


# ── Permits ─────────────────────────────────────────────────────────

_PERMIT_SELECT = (
    "SELECT p.*, sp.car_park, sp.space_number, "
    "COALESCE(st.first_name, su.first_name) AS holder_first, "
    "COALESCE(st.last_name, su.last_name) AS holder_last "
    "FROM parking_permits p "
    "LEFT JOIN parking_spaces sp ON sp.space_id = p.space_id "
    "LEFT JOIN staff st ON st.staff_id = p.staff_id "
    "LEFT JOIN students su ON su.student_id = p.student_id")


def next_permit_number(year: int | None = None) -> str:
    """``PK-2026-0001``: sequence per calendar year of issue."""
    init_db()
    y = year or _dt.date.today().year
    stem = f"{PERMIT_PREFIX}-{y}-"
    with _connect() as conn:
        rows = conn.execute(
            "SELECT permit_number FROM parking_permits "
            "WHERE permit_number LIKE ?", (f"{stem}%",)).fetchall()
    seq = 0
    for (num,) in rows:
        tail = num[len(stem):]
        if tail.isdigit():
            seq = max(seq, int(tail))
    return f"{stem}{seq + 1:04d}"


def default_expiry(issued_on: str, permit_type: str) -> str:
    """Annual/Blue Badge/Car Share: the next 31 August; Term: +4 months;
    Temporary: +14 days."""
    d = _dt.date.fromisoformat(issued_on)
    if permit_type == "Temporary":
        return (d + _dt.timedelta(days=14)).isoformat()
    if permit_type == "Term":
        month = d.month + 4
        year = d.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        return _dt.date(year, month, min(d.day, 28)).isoformat()
    year = d.year if d < _dt.date(d.year, 8, 31) else d.year + 1
    return _dt.date(year, 8, 31).isoformat()


def issue_permit(payload: dict[str, Any]) -> Permit:
    init_db()
    expire_lapsed()
    htype, staff_id, student_id = _holder(payload)
    reg = normalise_reg(payload.get("vehicle_reg"))
    ptype = _choice(payload.get("permit_type"), PERMIT_TYPES,
                    "Permit type", DEFAULT_PERMIT_TYPE)
    issued = (_date(payload.get("issued_on"), "Issued on")
              or _dt.date.today().isoformat())
    expires = (_date(payload.get("expires_on"), "Expires on")
               or default_expiry(issued, ptype))
    if expires < issued:
        raise ValidationError("Expiry is before the issue date")
    space_id = _validate_space_for(payload.get("space_id"), htype, ptype)
    with _connect() as conn:
        dup = conn.execute(
            "SELECT permit_number FROM parking_permits WHERE vehicle_reg=? "
            "AND status='Active' AND expires_on >= ?",
            (reg, _dt.date.today().isoformat())).fetchone()
        if dup:
            raise ValidationError(
                f"{reg} already has active permit {dup[0]}")
    number = next_permit_number(int(issued[:4]))
    with _connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO parking_permits (permit_number, holder_type, "
                "staff_id, student_id, vehicle_reg, vehicle_make, "
                "vehicle_colour, permit_type, issued_on, expires_on, "
                "space_id, status, issued_by, notes) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (number, htype, staff_id, student_id, reg,
                 _text(payload.get("vehicle_make")),
                 _text(payload.get("vehicle_colour")), ptype, issued,
                 expires, space_id, ACTIVE,
                 _text(payload.get("issued_by")),
                 _text(payload.get("notes"))))
        except _sql.IntegrityError as e:
            raise ValidationError(
                f"Could not issue permit: {e}") from None
        new_id = cur.lastrowid
    logger.info("Issued parking permit %s to %s %s (%s)", number, htype,
                staff_id or student_id, reg)
    out = get_permit(new_id)
    assert out is not None
    return out


def update_permit(permit_id: int, payload: dict[str, Any]) -> Permit:
    """Edit vehicle details, permit type, dates or notes. The holder is
    fixed — issue a new permit for a different person."""
    existing = _require_permit(permit_id)
    reg = normalise_reg(payload.get("vehicle_reg", existing.vehicle_reg))
    ptype = _choice(payload.get("permit_type", existing.permit_type),
                    PERMIT_TYPES, "Permit type")
    issued = _date(payload.get("issued_on", existing.issued_on),
                   "Issued on", required=True)
    expires = _date(payload.get("expires_on", existing.expires_on),
                    "Expires on", required=True)
    if expires < issued:
        raise ValidationError("Expiry is before the issue date")
    space_id = existing.space_id
    if "space_id" in payload:
        space_id = _validate_space_for(payload.get("space_id"),
                                       existing.holder_type, ptype,
                                       permit_id)
    elif space_id is not None and ptype != existing.permit_type:
        space = get_space(space_id)
        if space is not None:
            _check_space_fits(existing.holder_type, ptype, space.space_type)
    with _connect() as conn:
        conn.execute(
            "UPDATE parking_permits SET vehicle_reg=?, vehicle_make=?, "
            "vehicle_colour=?, permit_type=?, issued_on=?, expires_on=?, "
            "space_id=?, notes=?, updated_at=datetime('now') "
            "WHERE permit_id=?",
            (reg, _text(payload.get("vehicle_make", existing.vehicle_make)),
             _text(payload.get("vehicle_colour", existing.vehicle_colour)),
             ptype, issued, expires, space_id,
             _text(payload.get("notes", existing.notes)), permit_id))
    return _require_permit(permit_id)


def assign_space(permit_id: int, space_id: int | None) -> Permit:
    """Move a permit to a space (or off any space with ``None``)."""
    p = _require_permit(permit_id)
    if p.status != ACTIVE:
        raise ValidationError(f"Permit {p.permit_number} is {p.status}")
    expire_lapsed()
    sid = _validate_space_for(space_id, p.holder_type, p.permit_type,
                              permit_id)
    with _connect() as conn:
        try:
            conn.execute(
                "UPDATE parking_permits SET space_id=?, "
                "updated_at=datetime('now') WHERE permit_id=?",
                (sid, permit_id))
        except _sql.IntegrityError:
            raise ValidationError("That space was just taken") from None
    return _require_permit(permit_id)


def revoke_permit(permit_id: int, *, reason: str,
                  revoked_on: str | None = None) -> Permit:
    p = _require_permit(permit_id)
    if p.status != ACTIVE:
        raise ValidationError(f"Permit {p.permit_number} is {p.status}")
    why = _require(reason, "Reason")
    on = _date(revoked_on, "Revoked on") or _dt.date.today().isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE parking_permits SET status=?, revoked_on=?, "
            "revoked_reason=?, updated_at=datetime('now') "
            "WHERE permit_id=?", (REVOKED, on, why, permit_id))
    logger.info("Revoked parking permit %s: %s", p.permit_number, why)
    return _require_permit(permit_id)


def renew_permit(permit_id: int, *, expires_on: str | None = None,
                 keep_space: bool = True) -> Permit:
    """Extend an active or expired permit to a new expiry date (default:
    the next period for its type, counted from today or the old expiry,
    whichever is later). Revoked permits are not renewed."""
    p = _require_permit(permit_id)
    if p.status == REVOKED:
        raise ValidationError("A revoked permit cannot be renewed — "
                              "issue a new one")
    base = max(p.expires_on, _dt.date.today().isoformat())
    new_exp = (_date(expires_on, "New expiry")
               or default_expiry(base, p.permit_type))
    if new_exp <= p.expires_on:
        raise ValidationError("New expiry must be after the current one")
    space_id = p.space_id if keep_space else None
    if space_id is not None and p.status == EXPIRED:
        # The space may have gone to someone else while it was lapsed.
        space = get_space(space_id)
        if space is None or space.permit_number:
            space_id = None
    with _connect() as conn:
        conn.execute(
            "UPDATE parking_permits SET status=?, expires_on=?, "
            "space_id=?, updated_at=datetime('now') WHERE permit_id=?",
            (ACTIVE, new_exp, space_id, permit_id))
    logger.info("Renewed parking permit %s to %s", p.permit_number, new_exp)
    return _require_permit(permit_id)


def expire_lapsed(today: str | None = None) -> int:
    """Flip Active permits past their expiry to Expired (frees spaces)."""
    init_db()
    day = today or _dt.date.today().isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE parking_permits SET status=?, "
            "updated_at=datetime('now') "
            "WHERE status=? AND expires_on < ?", (EXPIRED, ACTIVE, day))
    if cur.rowcount:
        logger.info("Expired %d lapsed parking permit(s)", cur.rowcount)
    return cur.rowcount


def _require_permit(permit_id: int) -> Permit:
    p = get_permit(permit_id)
    if p is None:
        raise ValidationError(f"No parking permit #{permit_id}")
    return p


def get_permit(permit_id: int) -> Permit | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(f"{_PERMIT_SELECT} WHERE p.permit_id=?",
                         (permit_id,)).fetchone()
    return _permit(r) if r else None


def get_permit_by_number(permit_number: str) -> Permit | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(f"{_PERMIT_SELECT} WHERE p.permit_number=?",
                         ((permit_number or "").strip().upper(),)
                         ).fetchone()
    return _permit(r) if r else None


def find_by_reg(reg: str) -> list[Permit]:
    """Every permit ever issued for a plate, newest first — the question
    asked when an unknown car is parked in the staff car park."""
    norm = re.sub(r"[\s\-]", "", str(reg or "")).upper()
    if not norm:
        return []
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            f"{_PERMIT_SELECT} WHERE p.vehicle_reg LIKE ? "
            "ORDER BY p.issued_on DESC", (f"%{norm}%",)).fetchall()
    return [_permit(r) for r in rows]


def list_permits(*, holder_type: str | None = None,
                 staff_id: str | None = None,
                 student_id: str | None = None,
                 status: str | None = None,
                 permit_type: str | None = None,
                 car_park: str | None = None,
                 active_only: bool = False) -> list[Permit]:
    init_db()
    expire_lapsed()
    clauses: list[str] = []
    args: list[Any] = []
    if holder_type:
        clauses.append("p.holder_type = ?")
        args.append(_choice(holder_type, HOLDER_TYPES, "Holder type"))
    if staff_id:
        clauses.append("p.staff_id = ?")
        args.append(staff_id.strip().upper())
    if student_id:
        clauses.append("p.student_id = ?")
        args.append(student_id.strip())
    if status:
        clauses.append("p.status = ?")
        args.append(_choice(status, STATUSES, "Status"))
    if active_only:
        clauses.append("p.status = 'Active'")
    if permit_type:
        clauses.append("p.permit_type = ?")
        args.append(_choice(permit_type, PERMIT_TYPES, "Permit type"))
    if car_park:
        clauses.append("LOWER(sp.car_park) = LOWER(?)")
        args.append(car_park.strip())
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"{_PERMIT_SELECT}{where} ORDER BY "
           "CASE p.status WHEN 'Active' THEN 0 ELSE 1 END, "
           "p.expires_on, p.permit_number")
    with _connect() as conn:
        return [_permit(r) for r in conn.execute(sql, args).fetchall()]


def expiring_soon(days: int = 30) -> list[Permit]:
    today = _dt.date.today()
    horizon = (today + _dt.timedelta(days=max(0, days))).isoformat()
    return [p for p in list_permits(active_only=True)
            if p.expires_on <= horizon]


def delete_permit(permit_id: int) -> bool:
    """Remove a permit entered by mistake (prefer revoke for real ones)."""
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM parking_permits WHERE permit_id=?",
                           (permit_id,))
    return bool(cur.rowcount)


# ── Summary ─────────────────────────────────────────────────────────

def summary(*, expiring_days: int = 30) -> ParkingSummary:
    init_db()
    out = ParkingSummary(
        by_space_type={t: 0 for t in SPACE_TYPES},
        free_by_type={t: 0 for t in SPACE_TYPES},
        by_status={s: 0 for s in STATUSES},
        by_permit_type={t: 0 for t in PERMIT_TYPES})
    for s in list_spaces(active_only=True):
        out.spaces += 1
        out.by_space_type[s.space_type] += 1
        if s.is_free:
            out.free_spaces += 1
            out.free_by_type[s.space_type] += 1
    for p in list_permits():
        out.permits += 1
        out.by_status[p.status] = out.by_status.get(p.status, 0) + 1
        if p.status == ACTIVE:
            out.active_permits += 1
            out.by_permit_type[p.permit_type] = (
                out.by_permit_type.get(p.permit_type, 0) + 1)
            if p.holder_type == "Staff":
                out.staff_permits += 1
            else:
                out.student_permits += 1
    out.expiring_soon = len(expiring_soon(expiring_days))
    return out
