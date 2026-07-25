"""Staff Directory data layer for the Nursery System (Early Years / EYFS).

One record per practitioner / manager / support-staff member. Operates on the
shared ``staff`` table created and seeded in ``core/database.py`` — the same
table the cross-system superadmin dashboard counts — so the columns here match
that Early-Years schema exactly (room, paediatric-first-aid and DBS flags
rather than the school-style department / tutor / examiner fields).

Auto-allocates a sequential ``staff_id`` like ``NST005`` and a derived work
email ``nst005@nursery.local``. No login auto-provisioning happens here — staff
user accounts are administered separately via the shared auth system.
"""

from __future__ import annotations

import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system.systems.nursery.infrastructure import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.STAFF_DB
ID_PREFIX = "NST"
ID_DIGITS = 3
EMAIL_DOMAIN = "nursery.local"

# Early Years job roles. The demo seed uses "Nursery Manager", "Room Leader"
# and "Nursery Practitioner" — kept here so editing seeded rows validates.
ROLES: tuple[str, ...] = (
    "Nursery Manager", "Deputy Manager", "Room Leader",
    "Early Years Educator", "Nursery Practitioner", "Apprentice Practitioner",
    "Nursery Assistant", "Bank Staff", "SENCO", "Deputy SENCO",
    "Cook", "Administrator", "Other",
)
DEFAULT_ROLE: str = "Nursery Practitioner"

# Age-banded rooms / areas a practitioner can be assigned to. Offered in the
# UI but stored as free text, so a setting can use its own room names.
ROOMS: tuple[str, ...] = (
    "Baby Room", "Toddler Room", "Preschool Room",
    "Whole Setting", "Kitchen", "Office",
)

EMPLOYMENT_STATUSES: tuple[str, ...] = (
    "Full-time", "Part-time", "Apprentice", "Bank/Casual", "Agency",
    "Probation", "Maternity Cover", "On Leave", "Left",
)
DEFAULT_EMPLOYMENT_STATUS: str = "Full-time"
ACTIVE_STATUSES: tuple[str, ...] = tuple(
    s for s in EMPLOYMENT_STATUSES if s != "Left")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^[+0-9 ()\-]{5,25}$")

# Mirrors ``core/database.py`` _STAFF_SCHEMA so a fresh DB and this module
# agree. CREATE ... IF NOT EXISTS no-ops against the table the core bootstrap
# already created.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS staff (
    staff_id                  TEXT PRIMARY KEY,
    first_name                TEXT NOT NULL,
    last_name                 TEXT NOT NULL,
    title                     TEXT,
    role                      TEXT NOT NULL DEFAULT 'Nursery Practitioner',
    room                      TEXT,
    employment_status         TEXT NOT NULL DEFAULT 'Full-time',
    email                     TEXT NOT NULL,
    work_phone                TEXT,
    start_date                TEXT,
    end_date                  TEXT,
    is_dsl                    INTEGER NOT NULL DEFAULT 0,
    is_paediatric_first_aider INTEGER NOT NULL DEFAULT 0,
    dbs_checked               INTEGER NOT NULL DEFAULT 0,
    qualifications            TEXT,
    notes                     TEXT,
    created_at                TEXT DEFAULT (datetime('now')),
    updated_at                TEXT DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_nursery_staff_email ON staff(email);
CREATE INDEX IF NOT EXISTS idx_nursery_staff_role         ON staff(role);
CREATE INDEX IF NOT EXISTS idx_nursery_staff_status       ON staff(employment_status);
"""


@dataclass
class Staff:
    staff_id: str
    first_name: str
    last_name: str
    title: str | None
    role: str
    room: str | None
    employment_status: str
    email: str
    work_phone: str | None
    start_date: str | None
    end_date: str | None
    is_dsl: bool
    is_paediatric_first_aider: bool
    dbs_checked: bool
    qualifications: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def full_name(self) -> str:
        parts = [p for p in (self.title, self.first_name, self.last_name) if p]
        return " ".join(parts)

    @property
    def is_active(self) -> bool:
        return self.employment_status in ACTIVE_STATUSES


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
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Staff schema ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row) -> Staff:
    return Staff(
        staff_id=r["staff_id"], first_name=r["first_name"],
        last_name=r["last_name"], title=r["title"], role=r["role"],
        room=r["room"], employment_status=r["employment_status"],
        email=r["email"], work_phone=r["work_phone"],
        start_date=r["start_date"], end_date=r["end_date"],
        is_dsl=bool(r["is_dsl"]),
        is_paediatric_first_aider=bool(r["is_paediatric_first_aider"]),
        dbs_checked=bool(r["dbs_checked"]),
        qualifications=r["qualifications"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── ID + email helpers ────────────────────────────────────────────

def generate_staff_id() -> str:
    """Allocate a unique ``NST###`` id, widening past the demo range if full."""
    init_db()
    with _connect() as conn:
        existing = {
            r[0] for r in conn.execute("SELECT staff_id FROM staff").fetchall()
        }
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"
    for _ in range(50):
        n = random.randint(10 ** ID_DIGITS, 10 ** (ID_DIGITS + 3) - 1)
        sid = f"{ID_PREFIX}{n}"
        if sid not in existing:
            return sid
    raise RuntimeError("Could not allocate a unique staff id")


def generate_staff_email(staff_id: str) -> str:
    return f"{staff_id.lower()}@{EMAIL_DOMAIN}"


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(v, label: str):
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        raise ValidationError(f"{label} is required")
    return v


def _validate_date(v: Any, label: str) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        return None
    s = str(v).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _validate_phone(v: Any, label: str) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        return None
    s = str(v).strip()
    if not _PHONE_RE.match(s):
        raise ValidationError(
            f"{label} can only contain digits, spaces, +, (), and -")
    return s


def _validate_email(v: Any) -> str:
    s = _require(v, "Email").strip()
    if not _EMAIL_RE.match(s):
        raise ValidationError("Email is not a valid address")
    return s.lower()


def _validate_role(v: Any) -> str:
    s = _require(v, "Role").strip()
    if s not in ROLES:
        raise ValidationError(f"Role must be one of: {', '.join(ROLES)}")
    return s


def _validate_employment_status(v: Any) -> str:
    s = _require(v, "Employment status").strip()
    if s not in EMPLOYMENT_STATUSES:
        raise ValidationError(
            f"Employment status must be one of: "
            f"{', '.join(EMPLOYMENT_STATUSES)}")
    return s


def _validate_payload(data: dict[str, Any], *,
                      existing: Staff | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["first_name"] = _require(data.get("first_name"), "First name").strip()
    out["last_name"]  = _require(data.get("last_name"), "Last name").strip()
    out["title"]      = (data.get("title") or "").strip() or None

    out["role"]              = _validate_role(data.get("role") or DEFAULT_ROLE)
    out["room"]              = (data.get("room") or "").strip() or None
    out["employment_status"] = _validate_employment_status(
        data.get("employment_status") or DEFAULT_EMPLOYMENT_STATUS)

    out["work_phone"] = _validate_phone(data.get("work_phone"), "Work phone")
    out["start_date"] = _validate_date(data.get("start_date"), "Start date")
    out["end_date"]   = _validate_date(data.get("end_date"), "End date")
    if out["start_date"] and out["end_date"] \
            and out["end_date"] < out["start_date"]:
        raise ValidationError("End date cannot be before start date")

    out["is_dsl"]                    = bool(data.get("is_dsl"))
    out["is_paediatric_first_aider"] = bool(data.get("is_paediatric_first_aider"))
    out["dbs_checked"]               = bool(data.get("dbs_checked"))
    out["qualifications"] = (data.get("qualifications") or "").strip() or None
    out["notes"]          = (data.get("notes") or "").strip() or None
    return out


# ── CRUD ──────────────────────────────────────────────────────────

def create_staff(data: dict[str, Any]) -> Staff:
    init_db()
    try:
        p = _validate_payload(data)
    except ValidationError as e:
        logger.warning("create_staff validation failed: %s", e)
        raise
    sid = generate_staff_id()
    email = data.get("email") or generate_staff_email(sid)
    email = _validate_email(email)
    with _connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM staff WHERE email = ?", (email,)).fetchone()
        if exists:
            raise ValidationError(
                f"A staff member with email {email} already exists")
        conn.execute(
            """INSERT INTO staff (
                   staff_id, first_name, last_name, title, role, room,
                   employment_status, email, work_phone, start_date, end_date,
                   is_dsl, is_paediatric_first_aider, dbs_checked,
                   qualifications, notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (sid, p["first_name"], p["last_name"], p["title"],
             p["role"], p["room"], p["employment_status"],
             email, p["work_phone"], p["start_date"], p["end_date"],
             int(p["is_dsl"]), int(p["is_paediatric_first_aider"]),
             int(p["dbs_checked"]), p["qualifications"], p["notes"]),
        )
        conn.commit()
    out = get_staff(sid)
    assert out is not None
    logger.info("Created staff %s (%s %s, %s)",
                sid, out.first_name, out.last_name, out.role)
    # Register into the shared cross-system staff directory so a person who
    # works across systems is one HR identity (best-effort; never blocks).
    try:
        from education_system.platform.identity.staff_directory import (
            staff_directory_service,
        )
        staff_directory_service.register_local_staff(
            "nursery", staff_id=sid, first_name=out.first_name,
            last_name=out.last_name, email=out.email, role=out.role)
    except Exception:
        logger.debug("Staff directory registration skipped for %s", sid,
                     exc_info=True)
    return out


def get_staff(staff_id: str) -> Staff | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM staff WHERE staff_id = ?",
            (staff_id.strip().upper(),)).fetchone()
        return _row(r) if r else None


def list_staff(
    *,
    role: str | None = None,
    room: str | None = None,
    employment_status: str | None = None,
    is_dsl: bool | None = None,
    is_paediatric_first_aider: bool | None = None,
    dbs_checked: bool | None = None,
    active_only: bool = False,
) -> list[Staff]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if role:
        if role not in ROLES:
            raise ValidationError(f"Role must be one of: {', '.join(ROLES)}")
        clauses.append("role = ?")
        args.append(role)
    if room:
        clauses.append("room = ?")
        args.append(room)
    if employment_status:
        if employment_status not in EMPLOYMENT_STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(EMPLOYMENT_STATUSES)}")
        clauses.append("employment_status = ?")
        args.append(employment_status)
    if is_dsl is not None:
        clauses.append("is_dsl = ?")
        args.append(int(is_dsl))
    if is_paediatric_first_aider is not None:
        clauses.append("is_paediatric_first_aider = ?")
        args.append(int(is_paediatric_first_aider))
    if dbs_checked is not None:
        clauses.append("dbs_checked = ?")
        args.append(int(dbs_checked))
    if active_only:
        ph = ",".join("?" * len(ACTIVE_STATUSES))
        clauses.append(f"employment_status IN ({ph})")
        args.extend(ACTIVE_STATUSES)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM staff {where} "
           "ORDER BY last_name, first_name, staff_id")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def search_staff(q: str) -> list[Staff]:
    init_db()
    q = (q or "").strip()
    if not q:
        return list_staff()
    like = f"%{q}%"
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM staff
                WHERE staff_id LIKE ?
                   OR first_name LIKE ?
                   OR last_name  LIKE ?
                   OR email      LIKE ?
                   OR role       LIKE ?
                   OR room       LIKE ?
                ORDER BY last_name, first_name""",
            (like, like, like, like, like, like),
        ).fetchall()
    return [_row(r) for r in rows]


def update_staff(staff_id: str, data: dict[str, Any]) -> Staff:
    init_db()
    existing = get_staff(staff_id)
    if existing is None:
        raise ValidationError(f"No staff with id {staff_id}")
    merged = {
        "first_name":        data.get("first_name", existing.first_name),
        "last_name":         data.get("last_name", existing.last_name),
        "title":             data.get("title", existing.title),
        "role":              data.get("role", existing.role),
        "room":              data.get("room", existing.room),
        "employment_status": data.get("employment_status",
                                      existing.employment_status),
        "work_phone":        data.get("work_phone", existing.work_phone),
        "start_date":        data.get("start_date", existing.start_date),
        "end_date":          data.get("end_date", existing.end_date),
        "is_dsl":            data.get("is_dsl", existing.is_dsl),
        "is_paediatric_first_aider": data.get(
            "is_paediatric_first_aider", existing.is_paediatric_first_aider),
        "dbs_checked":       data.get("dbs_checked", existing.dbs_checked),
        "qualifications":    data.get("qualifications", existing.qualifications),
        "notes":             data.get("notes", existing.notes),
    }
    p = _validate_payload(merged, existing=existing)
    email = data.get("email", existing.email)
    email = _validate_email(email)
    with _connect() as conn:
        if email != existing.email:
            clash = conn.execute(
                "SELECT 1 FROM staff WHERE email = ? AND staff_id <> ?",
                (email, existing.staff_id)).fetchone()
            if clash:
                raise ValidationError(
                    f"Another staff member already has email {email}")
        conn.execute(
            """UPDATE staff SET
                  first_name=?, last_name=?, title=?, role=?, room=?,
                  employment_status=?, email=?, work_phone=?, start_date=?,
                  end_date=?, is_dsl=?, is_paediatric_first_aider=?,
                  dbs_checked=?, qualifications=?, notes=?,
                  updated_at=datetime('now')
               WHERE staff_id=?""",
            (p["first_name"], p["last_name"], p["title"], p["role"],
             p["room"], p["employment_status"], email, p["work_phone"],
             p["start_date"], p["end_date"], int(p["is_dsl"]),
             int(p["is_paediatric_first_aider"]), int(p["dbs_checked"]),
             p["qualifications"], p["notes"], existing.staff_id),
        )
        conn.commit()
    out = get_staff(existing.staff_id)
    assert out is not None
    logger.info("Updated staff %s", existing.staff_id)
    return out


def mark_left(staff_id: str, end_date: str | None = None) -> Staff:
    """Convenience: set employment_status='Left' + end_date."""
    import datetime as _dt
    end = end_date or _dt.date.today().isoformat()
    return update_staff(staff_id, {"employment_status": "Left",
                                   "end_date": end})


def delete_staff(staff_id: str) -> bool:
    init_db()
    sid = staff_id.strip().upper()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM staff WHERE staff_id = ?", (sid,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted staff %s", sid)
            return True
        return False


# ── Summary ───────────────────────────────────────────────────────

@dataclass
class Summary:
    total: int
    active: int
    left: int
    dsls: int
    paediatric_first_aiders: int
    dbs_checked: int
    by_role: dict[str, int]
    by_room: dict[str, int]
    by_status: dict[str, int]
    # EYFS welfare warnings — e.g. no DSL or no paediatric first aider on roll.
    welfare_warnings: list[str]


# Roles a registered setting must have filled (a manager and a SENCO). DSL and
# paediatric first aid are tracked as flags, not roles, and warned on below.
_CRITICAL_ROLES: tuple[str, ...] = ("Nursery Manager", "SENCO")


def summary() -> Summary:
    init_db()
    rows = list_staff()
    active = [s for s in rows if s.is_active]
    by_role = {r: 0 for r in ROLES}
    by_room: dict[str, int] = {}
    by_status = {s: 0 for s in EMPLOYMENT_STATUSES}
    dsls = pfas = dbs = 0
    for s in rows:
        by_role[s.role] = by_role.get(s.role, 0) + 1
        room = s.room or "(unassigned)"
        by_room[room] = by_room.get(room, 0) + 1
        by_status[s.employment_status] = (
            by_status.get(s.employment_status, 0) + 1)
        if s.is_active:
            if s.is_dsl:
                dsls += 1
            if s.is_paediatric_first_aider:
                pfas += 1
            if s.dbs_checked:
                dbs += 1

    active_roles = {s.role for s in active}
    warnings: list[str] = []
    if dsls == 0:
        warnings.append("No active Designated Safeguarding Lead (DSL)")
    if pfas == 0:
        warnings.append("No active paediatric first aider on roll")
    for r in _CRITICAL_ROLES:
        if r not in active_roles:
            warnings.append(f"No active {r}")

    return Summary(
        total=len(rows),
        active=len(active),
        left=sum(1 for s in rows if s.employment_status == "Left"),
        dsls=dsls, paediatric_first_aiders=pfas, dbs_checked=dbs,
        by_role=by_role, by_room=by_room, by_status=by_status,
        welfare_warnings=warnings,
    )
