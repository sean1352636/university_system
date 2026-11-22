"""ID cards data layer for the Sixth Form System.

One table, ``id_cards``: a photo ID card issued to exactly one student
or member of staff (CHECK constraint). Card numbers are deterministic —
``SF-<year>-<seq>`` with the sequence counted per year of issue.

Lifecycle::

    Active ──lost/stolen──▶ Lost      (replacement issued, charge raised)
           ──damaged etc.─▶ Replaced  (replacement issued)
           ──cancel──────▶ Cancelled
           ──past expiry─▶ Expired   (:func:`expire_lapsed`)

A holder has at most one Active card (partial unique indexes). The
replacement links back through ``replaced_card_id`` and carries the
charge (default from ``id_card_settings``; waived for a name change or
photo update unless one is given).

Every newly issued card starts in the print queue (``Awaiting Print``)
until :func:`mark_printed`. ``photo_ref`` is just the path/reference to
the photo held elsewhere — this module stores it, nothing more.
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

# Same file as the staff and students tables the FKs point at.
DB_PATH = paths.SIXTH_FORM_STUDENTS_DB

HOLDER_TYPES: tuple[str, ...] = ("Student", "Staff")

ACTIVE = "Active"
LOST = "Lost"
REPLACED = "Replaced"
CANCELLED = "Cancelled"
EXPIRED = "Expired"
STATUSES: tuple[str, ...] = (ACTIVE, LOST, REPLACED, CANCELLED, EXPIRED)

AWAITING_PRINT = "Awaiting Print"
PRINTED = "Printed"
PRINT_STATUSES: tuple[str, ...] = (AWAITING_PRINT, PRINTED)

REPLACEMENT_REASONS: tuple[str, ...] = (
    "Lost", "Stolen", "Damaged", "Name Change", "Photo Update", "Other")
# Reasons where the old card is out there somewhere (status Lost).
_LOST_REASONS = ("Lost", "Stolen")
# Reasons that are the college's doing or a legal change: no charge by
# default.
_FREE_REASONS = ("Name Change", "Photo Update")

CARD_PREFIX = "SF"
DEFAULT_REPLACEMENT_CHARGE = 5.00
DEFAULT_STAFF_VALIDITY_YEARS = 3

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS id_cards (
    card_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    card_number      TEXT NOT NULL UNIQUE,
    holder_type      TEXT NOT NULL,
    student_id       TEXT,
    staff_id         TEXT,
    photo_ref        TEXT,
    issued_on        TEXT NOT NULL,
    expires_on       TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'Active',
    replaced_card_id INTEGER,
    replacement_reason TEXT,
    charge           REAL NOT NULL DEFAULT 0,
    charge_paid      INTEGER NOT NULL DEFAULT 0,
    charge_paid_on   TEXT,
    print_status     TEXT NOT NULL DEFAULT 'Awaiting Print',
    printed_on       TEXT,
    printed_by       TEXT,
    status_changed_on TEXT,
    status_reason    TEXT,
    issued_by        TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    CHECK ((staff_id IS NULL) <> (student_id IS NULL)),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE CASCADE,
    FOREIGN KEY (replaced_card_id) REFERENCES id_cards(card_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_idc_expiry ON id_cards(expires_on);
CREATE INDEX IF NOT EXISTS idx_idc_print  ON id_cards(print_status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_idc_one_active_student
    ON id_cards(student_id) WHERE status = 'Active' AND student_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_idc_one_active_staff
    ON id_cards(staff_id) WHERE status = 'Active' AND staff_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS id_card_settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
"""


class ValidationError(ValueError):
    pass


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class IdCard:
    card_id: int
    card_number: str
    holder_type: str
    student_id: str | None
    staff_id: str | None
    photo_ref: str | None
    issued_on: str
    expires_on: str
    status: str
    replaced_card_id: int | None
    replacement_reason: str | None
    charge: float
    charge_paid: bool
    charge_paid_on: str | None
    print_status: str
    printed_on: str | None
    printed_by: str | None
    status_changed_on: str | None
    status_reason: str | None
    issued_by: str | None
    notes: str | None
    created_at: str
    updated_at: str
    holder_name: str | None = None

    @property
    def holder_id(self) -> str:
        return self.student_id or self.staff_id or ""

    @property
    def charge_outstanding(self) -> bool:
        return self.charge > 0 and not self.charge_paid


@dataclass
class IdCardSummary:
    total: int = 0
    active: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    by_holder_type: dict[str, int] = field(default_factory=dict)
    awaiting_print: int = 0
    expiring_30: int = 0
    replacements: int = 0
    charges_outstanding: float = 0.0
    charges_collected: float = 0.0
    no_photo: int = 0
    students_without_card: int = 0


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
    logger.debug("ID cards schema ready at %s", DB_PATH)
    _DB_READY = True


_SELECT = (
    "SELECT c.*, COALESCE(su.first_name, st.first_name) AS h_first, "
    "COALESCE(su.last_name, st.last_name) AS h_last FROM id_cards c "
    "LEFT JOIN students su ON su.student_id = c.student_id "
    "LEFT JOIN staff st ON st.staff_id = c.staff_id")


def _row(r: _sql.Row) -> IdCard:
    return IdCard(
        card_id=r["card_id"], card_number=r["card_number"],
        holder_type=r["holder_type"], student_id=r["student_id"],
        staff_id=r["staff_id"], photo_ref=r["photo_ref"],
        issued_on=r["issued_on"], expires_on=r["expires_on"],
        status=r["status"], replaced_card_id=r["replaced_card_id"],
        replacement_reason=r["replacement_reason"],
        charge=float(r["charge"] or 0), charge_paid=bool(r["charge_paid"]),
        charge_paid_on=r["charge_paid_on"],
        print_status=r["print_status"], printed_on=r["printed_on"],
        printed_by=r["printed_by"],
        status_changed_on=r["status_changed_on"],
        status_reason=r["status_reason"], issued_by=r["issued_by"],
        notes=r["notes"], created_at=r["created_at"],
        updated_at=r["updated_at"],
        holder_name=" ".join(p for p in (r["h_first"], r["h_last"]) if p)
        or None)


# ── Validation helpers ──────────────────────────────────────────────

def _text(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


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


def _money(v: Any, label: str) -> float:
    if v in (None, ""):
        return 0.0
    try:
        f = round(float(v), 2)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number") from None
    if f < 0:
        raise ValidationError(f"{label} cannot be negative")
    return f


def _choice(v: Any, options: tuple[str, ...], label: str,
            default: str | None = None) -> str:
    s = _text(v) or default
    for o in options:
        if s and s.lower() == o.lower():
            return o
    raise ValidationError(f"{label} must be one of: {', '.join(options)}")


def _holder(holder_type: Any, holder_id: Any
            ) -> tuple[str, str | None, str | None]:
    htype = _choice(holder_type, HOLDER_TYPES, "Holder type")
    hid = _text(holder_id)
    if not hid:
        raise ValidationError(f"{htype} is required")
    if htype == "Staff":
        hid = hid.upper()
        from education_system.systems.sixth_form.domain.staff import (
            staff as _staff,
        )
        if _staff.get_staff(hid) is None:
            raise ValidationError(f"No staff with id {hid}")
        return htype, None, hid
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(hid) is None:
        raise ValidationError(f"No student with id {hid}")
    return htype, hid, None


# ── Settings ────────────────────────────────────────────────────────

def _get_setting(key: str, default: str) -> str:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT value FROM id_card_settings WHERE key=?",
                         (key,)).fetchone()
    return r[0] if r else default


def _set_setting(key: str, value: str) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO id_card_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value))


def replacement_charge() -> float:
    try:
        return float(_get_setting("replacement_charge",
                                  str(DEFAULT_REPLACEMENT_CHARGE)))
    except ValueError:
        return DEFAULT_REPLACEMENT_CHARGE


def set_replacement_charge(amount: Any) -> float:
    value = _money(amount, "Replacement charge")
    _set_setting("replacement_charge", f"{value:.2f}")
    logger.info("ID card replacement charge set to %.2f", value)
    return value


def staff_validity_years() -> int:
    try:
        return int(_get_setting("staff_validity_years",
                                str(DEFAULT_STAFF_VALIDITY_YEARS)))
    except ValueError:
        return DEFAULT_STAFF_VALIDITY_YEARS


def set_staff_validity_years(years: Any) -> int:
    try:
        n = int(years)
    except (TypeError, ValueError):
        raise ValidationError("Validity must be a whole number of years") \
            from None
    if not 1 <= n <= 10:
        raise ValidationError("Validity must be between 1 and 10 years")
    _set_setting("staff_validity_years", str(n))
    return n


# ── Numbering and expiry ────────────────────────────────────────────

def next_card_number(year: int | None = None) -> str:
    """``SF-2026-00001``: sequence per calendar year of issue."""
    init_db()
    y = year or _dt.date.today().year
    stem = f"{CARD_PREFIX}-{y}-"
    with _connect() as conn:
        rows = conn.execute("SELECT card_number FROM id_cards "
                            "WHERE card_number LIKE ?",
                            (f"{stem}%",)).fetchall()
    seq = max((int(n[len(stem):]) for (n,) in rows
               if n[len(stem):].isdigit()), default=0)
    return f"{stem}{seq + 1:05d}"


def default_expiry(holder_type: str, issued_on: str,
                   student_id: str | None = None) -> str:
    """Students: 31 August at the end of a two-year course counted from
    the academic year of issue (override ``expires_on`` for a one-year
    student). Staff: issue date + the validity setting."""
    d = _dt.date.fromisoformat(issued_on)
    if holder_type == "Staff":
        years = staff_validity_years()
        try:
            return d.replace(year=d.year + years).isoformat()
        except ValueError:      # 29 February
            return (d.replace(day=28, year=d.year + years)).isoformat()
    start = d.year if d.month >= 9 else d.year - 1
    return _dt.date(start + 2, 8, 31).isoformat()


# ── Issue / update ──────────────────────────────────────────────────

def issue_card(holder_type: str, holder_id: str, *,
               photo_ref: str | None = None,
               issued_on: str | None = None,
               expires_on: str | None = None,
               issued_by: str | None = None,
               notes: str | None = None,
               _replaces: tuple[int, str, float] | None = None) -> IdCard:
    """Issue a new card. A holder who already has an Active card must
    have it replaced (:func:`replace_card`) or cancelled first."""
    init_db()
    htype, student_id, staff_id = _holder(holder_type, holder_id)
    issued = (_date(issued_on, "Issued on")
              or _dt.date.today().isoformat())
    expires = (_date(expires_on, "Expires on")
               or default_expiry(htype, issued, student_id))
    if expires <= issued:
        raise ValidationError("Expiry must be after the issue date")
    existing = card_for(htype, holder_id)
    if existing is not None and (_replaces is None
                                 or existing.card_id != _replaces[0]):
        raise ValidationError(
            f"{existing.holder_name or holder_id} already has active card "
            f"{existing.card_number} — replace or cancel it first")
    number = next_card_number(int(issued[:4]))
    replaced_id, reason, charge = _replaces or (None, None, 0.0)
    with _connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO id_cards (card_number, holder_type, "
                "student_id, staff_id, photo_ref, issued_on, expires_on, "
                "status, replaced_card_id, replacement_reason, charge, "
                "print_status, issued_by, notes) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (number, htype, student_id, staff_id, _text(photo_ref),
                 issued, expires, ACTIVE, replaced_id, reason, charge,
                 AWAITING_PRINT, _text(issued_by), _text(notes)))
        except _sql.IntegrityError as e:
            raise ValidationError(f"Could not issue card: {e}") from None
        new_id = cur.lastrowid
    logger.info("Issued ID card %s to %s %s", number, htype,
                student_id or staff_id)
    out = get_card(new_id)
    assert out is not None
    return out


def update_card(card_id: int, payload: dict[str, Any]) -> IdCard:
    """Edit the photo reference, expiry or notes. A new photo on a card
    already printed puts it back in the print queue."""
    c = _require_card(card_id)
    photo = _text(payload.get("photo_ref", c.photo_ref))
    expires = _date(payload.get("expires_on", c.expires_on), "Expires on",
                    required=True)
    if expires <= c.issued_on:
        raise ValidationError("Expiry must be after the issue date")
    reprint = (photo != c.photo_ref or expires != c.expires_on) \
        and c.print_status == PRINTED and c.status == ACTIVE
    with _connect() as conn:
        conn.execute(
            "UPDATE id_cards SET photo_ref=?, expires_on=?, notes=?, "
            "print_status=CASE WHEN ? THEN ? ELSE print_status END, "
            "updated_at=datetime('now') WHERE card_id=?",
            (photo, expires, _text(payload.get("notes", c.notes)),
             1 if reprint else 0, AWAITING_PRINT, card_id))
    return _require_card(card_id)


def replace_card(card_id: int, *, reason: str = "Lost",
                 charge: float | None = None,
                 photo_ref: str | None = None,
                 issued_by: str | None = None,
                 notes: str | None = None) -> IdCard:
    """Retire an Active card and issue its replacement in one step.

    The old card becomes Lost (lost / stolen) or Replaced (anything
    else). The new card keeps the holder and the old expiry (unless that
    has passed) and carries the charge: the configured replacement
    charge by default, nothing for a name change or photo update.
    """
    old = _require_card(card_id)
    if old.status != ACTIVE:
        raise ValidationError(f"Card {old.card_number} is {old.status}")
    why = _choice(reason, REPLACEMENT_REASONS, "Reason", "Lost")
    amount = (_money(charge, "Charge") if charge is not None
              else (0.0 if why in _FREE_REASONS else replacement_charge()))
    today = _dt.date.today().isoformat()
    new_status = LOST if why in _LOST_REASONS else REPLACED
    with _connect() as conn:
        conn.execute(
            "UPDATE id_cards SET status=?, status_changed_on=?, "
            "status_reason=?, updated_at=datetime('now') WHERE card_id=?",
            (new_status, today, why, card_id))
    expires = old.expires_on if old.expires_on > today else None
    try:
        new = issue_card(
            old.holder_type, old.holder_id,
            photo_ref=photo_ref if photo_ref is not None else old.photo_ref,
            expires_on=expires, issued_by=issued_by,
            notes=notes or f"Replaces {old.card_number} ({why})",
            _replaces=(card_id, why, amount))
    except Exception:
        # Put the old card back rather than leave the holder with none.
        with _connect() as conn:
            conn.execute(
                "UPDATE id_cards SET status=?, status_changed_on=NULL, "
                "status_reason=NULL WHERE card_id=?", (ACTIVE, card_id))
        raise
    logger.info("Card %s %s; replacement %s (charge %.2f)",
                old.card_number, new_status.lower(), new.card_number, amount)
    return new


def report_lost(card_id: int, *, replace: bool = True,
                charge: float | None = None,
                stolen: bool = False) -> IdCard:
    """Record a lost (or stolen) card; by default issue the replacement
    straight away and return it. With ``replace=False`` the old card is
    marked Lost and returned — issue a new one later."""
    reason = "Stolen" if stolen else "Lost"
    if replace:
        return replace_card(card_id, reason=reason, charge=charge)
    c = _require_card(card_id)
    if c.status != ACTIVE:
        raise ValidationError(f"Card {c.card_number} is {c.status}")
    with _connect() as conn:
        conn.execute(
            "UPDATE id_cards SET status=?, status_changed_on=?, "
            "status_reason=?, updated_at=datetime('now') WHERE card_id=?",
            (LOST, _dt.date.today().isoformat(), reason, card_id))
    return _require_card(card_id)


def record_charge_paid(card_id: int, *,
                       paid_on: str | None = None) -> IdCard:
    c = _require_card(card_id)
    if c.charge <= 0:
        raise ValidationError("There is no charge on this card")
    if c.charge_paid:
        raise ValidationError("The charge is already paid")
    on = _date(paid_on, "Paid on") or _dt.date.today().isoformat()
    with _connect() as conn:
        conn.execute("UPDATE id_cards SET charge_paid=1, charge_paid_on=?, "
                     "updated_at=datetime('now') WHERE card_id=?",
                     (on, card_id))
    return _require_card(card_id)


def cancel_card(card_id: int, *, reason: str) -> IdCard:
    """Withdraw a card (leaver, issued in error)."""
    c = _require_card(card_id)
    if c.status != ACTIVE:
        raise ValidationError(f"Card {c.card_number} is {c.status}")
    why = _text(reason)
    if not why:
        raise ValidationError("Reason is required")
    with _connect() as conn:
        conn.execute(
            "UPDATE id_cards SET status=?, status_changed_on=?, "
            "status_reason=?, updated_at=datetime('now') WHERE card_id=?",
            (CANCELLED, _dt.date.today().isoformat(), why, card_id))
    return _require_card(card_id)


def expire_lapsed(today: str | None = None) -> int:
    init_db()
    day = today or _dt.date.today().isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE id_cards SET status=?, status_changed_on=?, "
            "status_reason='Past expiry', updated_at=datetime('now') "
            "WHERE status=? AND expires_on < ?", (EXPIRED, day, ACTIVE, day))
    return cur.rowcount


# ── Printing ────────────────────────────────────────────────────────

def print_queue() -> list[IdCard]:
    """Active cards awaiting print, oldest first — the printing list."""
    return [c for c in list_cards(status=ACTIVE,
                                  print_status=AWAITING_PRINT)][::-1]


def mark_printed(card_ids: list[int], *,
                 printed_by: str | None = None) -> int:
    init_db()
    ids = [int(i) for i in card_ids]
    if not ids:
        return 0
    ph = ",".join("?" * len(ids))
    with _connect() as conn:
        cur = conn.execute(
            f"UPDATE id_cards SET print_status=?, printed_on=?, "
            f"printed_by=?, updated_at=datetime('now') "
            f"WHERE card_id IN ({ph}) AND status=?",
            (PRINTED, _dt.date.today().isoformat(), _text(printed_by),
             *ids, ACTIVE))
    logger.info("Marked %d ID card(s) printed", cur.rowcount)
    return cur.rowcount


def reprint(card_id: int) -> IdCard:
    c = _require_card(card_id)
    if c.status != ACTIVE:
        raise ValidationError(f"Card {c.card_number} is {c.status}")
    with _connect() as conn:
        conn.execute("UPDATE id_cards SET print_status=?, "
                     "updated_at=datetime('now') WHERE card_id=?",
                     (AWAITING_PRINT, card_id))
    return _require_card(card_id)


# ── Reads ───────────────────────────────────────────────────────────

def _require_card(card_id: int) -> IdCard:
    c = get_card(card_id)
    if c is None:
        raise ValidationError(f"No ID card #{card_id}")
    return c


def get_card(card_id: int) -> IdCard | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(f"{_SELECT} WHERE c.card_id=?",
                         (card_id,)).fetchone()
    return _row(r) if r else None


def get_card_by_number(card_number: str) -> IdCard | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(f"{_SELECT} WHERE c.card_number=?",
                         ((card_number or "").strip().upper(),)).fetchone()
    return _row(r) if r else None


def card_for(holder_type: str, holder_id: str) -> IdCard | None:
    """The holder's Active card, if any."""
    init_db()
    col = "staff_id" if holder_type == "Staff" else "student_id"
    hid = (holder_id or "").strip()
    if holder_type == "Staff":
        hid = hid.upper()
    with _connect() as conn:
        r = conn.execute(f"{_SELECT} WHERE c.{col}=? AND c.status=?",
                         (hid, ACTIVE)).fetchone()
    return _row(r) if r else None


def history_for(holder_type: str, holder_id: str) -> list[IdCard]:
    col = "staff_id" if holder_type == "Staff" else "student_id"
    hid = (holder_id or "").strip()
    if holder_type == "Staff":
        hid = hid.upper()
    init_db()
    with _connect() as conn:
        return [_row(r) for r in conn.execute(
            f"{_SELECT} WHERE c.{col}=? ORDER BY c.issued_on DESC, "
            "c.card_id DESC", (hid,)).fetchall()]


def list_cards(*, holder_type: str | None = None,
               status: str | None = None,
               print_status: str | None = None,
               name_like: str | None = None,
               charges_outstanding: bool = False) -> list[IdCard]:
    init_db()
    expire_lapsed()
    clauses: list[str] = []
    args: list[Any] = []
    if holder_type:
        clauses.append("c.holder_type = ?")
        args.append(_choice(holder_type, HOLDER_TYPES, "Holder type"))
    if status:
        clauses.append("c.status = ?")
        args.append(_choice(status, STATUSES, "Status"))
    if print_status:
        clauses.append("c.print_status = ?")
        args.append(_choice(print_status, PRINT_STATUSES, "Print status"))
    if name_like:
        like = f"%{name_like.strip()}%"
        clauses.append(
            "(COALESCE(su.first_name, st.first_name) || ' ' || "
            "COALESCE(su.last_name, st.last_name) LIKE ? "
            "OR c.card_number LIKE ? OR c.student_id LIKE ? "
            "OR c.staff_id LIKE ?)")
        args.extend([like, like, like, like])
    if charges_outstanding:
        clauses.append("c.charge > 0 AND c.charge_paid = 0")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [_row(r) for r in conn.execute(
            f"{_SELECT}{where} ORDER BY c.issued_on DESC, c.card_id DESC",
            args).fetchall()]


def expiring(days: int = 30) -> list[IdCard]:
    horizon = (_dt.date.today()
               + _dt.timedelta(days=max(0, days))).isoformat()
    rows = [c for c in list_cards(status=ACTIVE) if c.expires_on <= horizon]
    rows.sort(key=lambda c: c.expires_on)
    return rows


def students_without_card() -> list[tuple[str, str]]:
    """(student_id, name) for enrolled students with no Active card."""
    init_db()
    with _connect() as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(students)")}
        status_clause = ""
        if "status" in cols:
            status_clause = ("AND COALESCE(s.status, 'Active') "
                             "IN ('Active', 'Enrolled') ")
        rows = conn.execute(
            "SELECT s.student_id, s.first_name, s.last_name FROM students s "
            "WHERE NOT EXISTS (SELECT 1 FROM id_cards c WHERE "
            "c.student_id = s.student_id AND c.status = 'Active') "
            f"{status_clause}ORDER BY s.last_name, s.first_name").fetchall()
    return [(r[0], f"{r[1]} {r[2]}".strip()) for r in rows]


def delete_card(card_id: int) -> bool:
    """Remove a card issued in error and never printed."""
    c = _require_card(card_id)
    if c.print_status == PRINTED:
        raise ValidationError("A printed card is cancelled, not deleted")
    with _connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM id_cards "
                         "WHERE replaced_card_id=?", (card_id,)).fetchone()[0]
        if n:
            raise ValidationError("Another card replaces this one")
        cur = conn.execute("DELETE FROM id_cards WHERE card_id=?",
                           (card_id,))
    return bool(cur.rowcount)


# ── Summary ─────────────────────────────────────────────────────────

def summary() -> IdCardSummary:
    out = IdCardSummary(by_status={s: 0 for s in STATUSES},
                        by_holder_type={h: 0 for h in HOLDER_TYPES})
    for c in list_cards():
        out.total += 1
        out.by_status[c.status] = out.by_status.get(c.status, 0) + 1
        if c.status == ACTIVE:
            out.active += 1
            out.by_holder_type[c.holder_type] += 1
            if c.print_status == AWAITING_PRINT:
                out.awaiting_print += 1
            if not c.photo_ref:
                out.no_photo += 1
        if c.replaced_card_id:
            out.replacements += 1
        if c.charge > 0:
            if c.charge_paid:
                out.charges_collected += c.charge
            else:
                out.charges_outstanding += c.charge
    out.expiring_30 = len(expiring(30))
    out.students_without_card = len(students_without_card())
    out.charges_outstanding = round(out.charges_outstanding, 2)
    out.charges_collected = round(out.charges_collected, 2)
    return out
