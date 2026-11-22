"""Device loans for the Sixth Form System.

Builds on the fixed-asset register (:mod:`...operations.domain.assets.assets`):
a loan device **is** an asset — tag, make, model, serial, condition and
status stay there, and the asset's status follows the loan (On Loan /
In Storage / Awaiting Repair / Lost/Stolen). This module adds:

* ``loan_devices`` — which assets are in the loan pool, with what goes
  out with them (charger, accessories), the pool name and the usual
  loan length;
* ``device_loans`` — one row per loan to a student or a member of staff:
  issue / due / return dates, condition out and in, charger out and
  back, an optional link to the bursary award that funds it, the AUP
  acceptance it was issued against, and lost / damaged handling with
  any charge and whether it was paid or waived.

Rules enforced on issue: the device is in the pool and usable, it has
no open loan (partial unique index), the borrower exists (a student must
be on roll), the borrower has accepted the **current** IT acceptable-use
policy version (:mod:`.acceptable_use`), a student holds one device at a
time unless ``allow_second`` is given, and a bursary award must be the
student's own and approved.

Loans are history and are never cascaded away: the student FK has no
ON DELETE action, so the student delete guard counts them.

Permissions: managing the pool and issuing / returning loans need
``operations``. :func:`loans_for_student` lets a student see their own.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from education_system import paths
from education_system.systems.sixth_form.domains.operations.domain.device_loans import (
    acceptable_use as aup,
)
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_STUDENTS_DB

STUDENT = aup.STUDENT
STAFF = aup.STAFF
BORROWER_TYPES = aup.USER_TYPES

ON_LOAN = "On Loan"
RETURNED = "Returned"
RETURNED_DAMAGED = "Returned Damaged"
LOST = "Lost"
LOAN_STATUSES: tuple[str, ...] = (ON_LOAN, RETURNED, RETURNED_DAMAGED, LOST)

CHARGE_NONE = "None"
CHARGE_DUE = "Due"
CHARGE_PAID = "Paid"
CHARGE_WAIVED = "Waived"
CHARGE_STATUSES: tuple[str, ...] = (CHARGE_NONE, CHARGE_DUE, CHARGE_PAID,
                                    CHARGE_WAIVED)

DEFAULT_POOL = "General"
DEFAULT_LOAN_DAYS = 14
DEFAULT_CATEGORY = "Laptop"

#: Asset statuses a device cannot be lent from.
_UNUSABLE = ("Awaiting Repair", "In Repair", "Retired", "Disposed",
             "Lost/Stolen")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS loan_devices (
    asset_id           INTEGER PRIMARY KEY,
    loan_pool          TEXT NOT NULL DEFAULT 'General',
    includes_charger   INTEGER NOT NULL DEFAULT 1,
    accessories        TEXT,
    default_loan_days  INTEGER NOT NULL DEFAULT 14,
    loanable           INTEGER NOT NULL DEFAULT 1,
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
);

CREATE TABLE IF NOT EXISTS device_loans (
    loan_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id               INTEGER NOT NULL,
    borrower_type          TEXT NOT NULL,
    student_id             TEXT,
    staff_id               TEXT,
    issued_on              TEXT NOT NULL,
    due_on                 TEXT NOT NULL,
    returned_on            TEXT,
    condition_out          TEXT NOT NULL,
    condition_in           TEXT,
    charger_issued         INTEGER NOT NULL DEFAULT 0,
    charger_returned       INTEGER,
    accessories_issued     TEXT,
    bursary_funded         INTEGER NOT NULL DEFAULT 0,
    bursary_application_id INTEGER,
    aup_acceptance_id      INTEGER,
    aup_version            TEXT,
    status                 TEXT NOT NULL DEFAULT 'On Loan',
    lost_on                TEXT,
    damage_notes           TEXT,
    charge_amount          REAL NOT NULL DEFAULT 0,
    charge_status          TEXT NOT NULL DEFAULT 'None',
    charge_settled_on      TEXT,
    charge_note            TEXT,
    extended_count         INTEGER NOT NULL DEFAULT 0,
    issued_by              TEXT,
    returned_to            TEXT,
    notes                  TEXT,
    created_at             TEXT DEFAULT (datetime('now')),
    updated_at             TEXT DEFAULT (datetime('now')),
    CHECK ((borrower_type = 'Student' AND student_id IS NOT NULL
            AND staff_id IS NULL)
        OR (borrower_type = 'Staff' AND staff_id IS NOT NULL
            AND student_id IS NULL)),
    FOREIGN KEY (asset_id)   REFERENCES assets(asset_id),
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (bursary_application_id)
        REFERENCES bursary_applications(application_id) ON DELETE SET NULL,
    FOREIGN KEY (aup_acceptance_id)
        REFERENCES aup_acceptances(acceptance_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dl_one_open
    ON device_loans(asset_id) WHERE status = 'On Loan';
CREATE INDEX IF NOT EXISTS idx_dl_student ON device_loans(student_id);
CREATE INDEX IF NOT EXISTS idx_dl_staff   ON device_loans(staff_id);
CREATE INDEX IF NOT EXISTS idx_dl_due     ON device_loans(due_on);
"""


class ValidationError(ValueError):
    pass


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class LoanDevice:
    asset_id: int
    asset_tag: str
    name: str
    category: str
    manufacturer: str | None
    model: str | None
    serial_number: str | None
    location: str
    condition: str
    asset_status: str
    loan_pool: str
    includes_charger: bool
    accessories: str | None
    default_loan_days: int
    loanable: bool
    notes: str | None
    open_loan_id: int | None = None
    borrower: str | None = None
    due_on: str | None = None

    @property
    def label(self) -> str:
        return f"{self.asset_tag} {self.name}"

    @property
    def available(self) -> bool:
        return (self.loanable and self.open_loan_id is None
                and self.asset_status not in _UNUSABLE)


@dataclass
class Loan:
    loan_id: int
    asset_id: int
    borrower_type: str
    student_id: str | None
    staff_id: str | None
    issued_on: str
    due_on: str
    returned_on: str | None
    condition_out: str
    condition_in: str | None
    charger_issued: bool
    charger_returned: bool | None
    accessories_issued: str | None
    bursary_funded: bool
    bursary_application_id: int | None
    aup_acceptance_id: int | None
    aup_version: str | None
    status: str
    lost_on: str | None
    damage_notes: str | None
    charge_amount: float
    charge_status: str
    charge_settled_on: str | None
    charge_note: str | None
    extended_count: int
    issued_by: str | None
    returned_to: str | None
    notes: str | None
    created_at: str
    updated_at: str
    asset_tag: str | None = None
    device_name: str | None = None
    borrower_name: str | None = None

    @property
    def borrower_id(self) -> str:
        return self.student_id or self.staff_id or ""

    @property
    def is_open(self) -> bool:
        return self.status == ON_LOAN

    def is_overdue(self, as_of: str | None = None) -> bool:
        day = as_of or _dt.date.today().isoformat()
        return self.is_open and self.due_on < day

    @property
    def device_label(self) -> str:
        return f"{self.asset_tag or f'#{self.asset_id}'} {self.device_name or ''}".strip()


@dataclass
class LoanSummary:
    devices: int = 0
    available: int = 0
    on_loan: int = 0
    unusable: int = 0
    overdue: int = 0
    bursary_funded_open: int = 0
    lost: int = 0
    damaged: int = 0
    charges_due: float = 0.0
    charges_paid: float = 0.0
    by_pool: dict[str, dict[str, int]] = field(default_factory=dict)
    aup_version: str | None = None
    students_without_aup: int = 0


# ── Plumbing ────────────────────────────────────────────────────────

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


_DB_READY = False


def _assets():
    from education_system.systems.sixth_form.domains.operations.domain.assets import (
        assets as _a,
    )
    return _a


def _bursaries():
    from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
        bursaries as _b,
    )
    return _b


def _access():
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    _assets().init_db()          # assets + staff
    _bursaries().init_db()       # bursary_applications + students
    aup.init_db()                # policies + aup_acceptances
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    _DB_READY = True


def _require_ops(action: str) -> Any:
    access = _access()
    p = access.current()
    p.require(access.OPERATIONS, action)
    return p


def _who(p: Any) -> str | None:
    return p.staff_name or p.username or None


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


def _int(v: Any, label: str, lo: int, hi: int, default: int) -> int:
    if v in (None, ""):
        return default
    try:
        n = int(str(v).strip())
    except ValueError:
        raise ValidationError(f"{label} must be a whole number") from None
    if not lo <= n <= hi:
        raise ValidationError(f"{label} must be between {lo} and {hi}")
    return n


def _choice(v: Any, options: tuple[str, ...], label: str,
            default: str | None = None) -> str:
    s = _text(v) or default
    for o in options:
        if s and s.lower() == o.lower():
            return o
    raise ValidationError(f"{label} must be one of: {', '.join(options)}")


def _bool(v: Any, default: bool) -> bool:
    if v is None or v == "":
        return default
    if isinstance(v, str):
        return v.strip().lower() in ("1", "y", "yes", "true", "on")
    return bool(v)


def conditions() -> tuple[str, ...]:
    return _assets().CONDITIONS


# ── Devices ─────────────────────────────────────────────────────────

_DEVICE_SELECT = """
SELECT a.asset_id, a.asset_tag, a.name, a.category, a.manufacturer,
       a.model, a.serial_number, a.location, a.condition,
       a.status AS asset_status, d.loan_pool, d.includes_charger,
       d.accessories, d.default_loan_days, d.loanable, d.notes,
       l.loan_id AS open_loan_id, l.due_on,
       COALESCE(s.first_name || ' ' || s.last_name,
                sf.first_name || ' ' || sf.last_name,
                l.student_id, l.staff_id) AS borrower
FROM loan_devices d
JOIN assets a ON a.asset_id = d.asset_id
LEFT JOIN device_loans l ON l.asset_id = d.asset_id AND l.status = 'On Loan'
LEFT JOIN students s ON s.student_id = l.student_id
LEFT JOIN staff sf ON sf.staff_id = l.staff_id
"""


def _device(r: _sql.Row) -> LoanDevice:
    return LoanDevice(
        asset_id=r["asset_id"], asset_tag=r["asset_tag"], name=r["name"],
        category=r["category"], manufacturer=r["manufacturer"],
        model=r["model"], serial_number=r["serial_number"],
        location=r["location"], condition=r["condition"],
        asset_status=r["asset_status"], loan_pool=r["loan_pool"],
        includes_charger=bool(r["includes_charger"]),
        accessories=r["accessories"],
        default_loan_days=int(r["default_loan_days"]),
        loanable=bool(r["loanable"]), notes=r["notes"],
        open_loan_id=r["open_loan_id"], due_on=r["due_on"],
        borrower=r["borrower"])


def _profile_values(payload: dict[str, Any],
                    existing: LoanDevice | None) -> dict[str, Any]:
    def g(k: str, dflt: Any) -> Any:
        return payload.get(k, getattr(existing, k) if existing else dflt)
    return {
        "loan_pool": _text(g("loan_pool", DEFAULT_POOL)) or DEFAULT_POOL,
        "includes_charger": 1 if _bool(g("includes_charger", True), True)
        else 0,
        "accessories": _text(g("accessories", None)),
        "default_loan_days": _int(g("default_loan_days", DEFAULT_LOAN_DAYS),
                                  "Usual loan length (days)", 1, 400,
                                  DEFAULT_LOAN_DAYS),
        "loanable": 1 if _bool(g("loanable", True), True) else 0,
        "notes": _text(g("notes", None)),
    }


def add_to_pool(asset_id: int, payload: dict[str, Any] | None = None
                ) -> LoanDevice:
    """Put an existing asset into the loan pool."""
    init_db()
    _require_ops("manage loan devices")
    asset = _assets().get_asset(int(asset_id))
    if asset is None:
        raise ValidationError(f"No asset #{asset_id}")
    if asset.is_disposed or asset.status == "Retired":
        raise ValidationError(f"Asset {asset.asset_tag} is {asset.status}")
    v = _profile_values(payload or {}, None)
    with _connect() as conn:
        try:
            conn.execute(
                "INSERT INTO loan_devices (asset_id, loan_pool, "
                "includes_charger, accessories, default_loan_days, loanable,"
                " notes) VALUES (?,?,?,?,?,?,?)",
                (asset.asset_id, v["loan_pool"], v["includes_charger"],
                 v["accessories"], v["default_loan_days"], v["loanable"],
                 v["notes"]))
        except _sql.IntegrityError:
            raise ValidationError(
                f"{asset.asset_tag} is already in the loan pool") from None
    return _require_device(asset.asset_id)


_ASSET_KEYS = ("asset_tag", "name", "category", "manufacturer", "model",
               "serial_number", "location", "room", "purchase_date",
               "purchase_cost", "supplier", "warranty_expiry", "condition")


def register_device(payload: dict[str, Any]) -> LoanDevice:
    """Create the asset (status In Storage) and add it to the pool."""
    init_db()
    _require_ops("register loan devices")
    asset_payload = {k: payload.get(k) for k in _ASSET_KEYS
                     if k in payload}
    asset_payload.setdefault("category", DEFAULT_CATEGORY)
    asset_payload["status"] = "In Storage"
    _profile_values(payload, None)      # validate before creating anything
    asset = _assets().create_asset(asset_payload)
    try:
        return add_to_pool(asset.asset_id, payload)
    except Exception:
        _assets().delete_asset(asset.asset_id)
        raise


def update_device(asset_id: int, payload: dict[str, Any]) -> LoanDevice:
    """Change the pool details and/or the asset's own details."""
    d = _require_device(asset_id)
    _require_ops("manage loan devices")
    asset_changes = {k: payload[k] for k in _ASSET_KEYS if k in payload}
    if asset_changes:
        _assets().update_asset(d.asset_id, asset_changes)
    v = _profile_values(payload, d)
    with _connect() as conn:
        conn.execute(
            "UPDATE loan_devices SET loan_pool=?, includes_charger=?, "
            "accessories=?, default_loan_days=?, loanable=?, notes=?, "
            "updated_at=datetime('now') WHERE asset_id=?",
            (v["loan_pool"], v["includes_charger"], v["accessories"],
             v["default_loan_days"], v["loanable"], v["notes"], d.asset_id))
    return _require_device(asset_id)


def remove_from_pool(asset_id: int) -> bool:
    """Take a device out of the pool. One with loan history is marked
    not loanable instead (its loans point at it); the asset itself stays
    in the register either way. Returns True when the row was removed."""
    d = _require_device(asset_id)
    _require_ops("manage loan devices")
    if d.open_loan_id:
        raise ValidationError(f"{d.label} is on loan — return it first")
    with _connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM device_loans WHERE asset_id=?",
                         (d.asset_id,)).fetchone()[0]
        if n:
            conn.execute("UPDATE loan_devices SET loanable=0, "
                         "updated_at=datetime('now') WHERE asset_id=?",
                         (d.asset_id,))
            return False
        conn.execute("DELETE FROM loan_devices WHERE asset_id=?",
                     (d.asset_id,))
    return True


def send_for_repair(asset_id: int, *, notes: str | None = None,
                    repaired: bool = False) -> LoanDevice:
    """Mark a device Awaiting Repair (or back In Storage once fixed,
    logging the repair in the asset maintenance log)."""
    d = _require_device(asset_id)
    _require_ops("manage loan devices")
    if d.open_loan_id:
        raise ValidationError(f"{d.label} is on loan — return it first")
    a = _assets()
    if repaired:
        a.add_maintenance(d.asset_id, {
            "service_date": _dt.date.today().isoformat(),
            "service_type": "Repair", "outcome": "Completed",
            "notes": _text(notes)})
        a.update_asset(d.asset_id, {"status": "In Storage",
                                    "condition": "Good"})
    else:
        a.update_asset(d.asset_id, {"status": "Awaiting Repair"})
    return _require_device(asset_id)


def get_device(asset_id: int) -> LoanDevice | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(f"{_DEVICE_SELECT} WHERE d.asset_id=?",
                         (int(asset_id),)).fetchone()
    return _device(r) if r else None


def _require_device(asset_id: int) -> LoanDevice:
    d = get_device(asset_id)
    if d is None:
        raise ValidationError(f"Asset #{asset_id} is not in the loan pool")
    return d


def list_devices(*, pool: str | None = None, available_only: bool = False,
                 on_loan_only: bool = False,
                 search: str | None = None) -> list[LoanDevice]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if pool:
        clauses.append("d.loan_pool = ?")
        args.append(pool.strip())
    if on_loan_only:
        clauses.append("l.loan_id IS NOT NULL")
    if search:
        like = f"%{search.strip()}%"
        clauses.append("(a.asset_tag LIKE ? OR a.name LIKE ? OR "
                       "a.serial_number LIKE ? OR a.model LIKE ?)")
        args += [like] * 4
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = [_device(r) for r in conn.execute(
            f"{_DEVICE_SELECT}{where} ORDER BY d.loan_pool, a.asset_tag",
            args).fetchall()]
    return [d for d in rows if d.available] if available_only else rows


def pools() -> list[str]:
    init_db()
    with _connect() as conn:
        return [r[0] for r in conn.execute(
            "SELECT DISTINCT loan_pool FROM loan_devices ORDER BY 1")]


def assets_not_in_pool() -> list[Any]:
    """Register assets that could be added (not disposed / retired)."""
    init_db()
    with _connect() as conn:
        pooled = {r[0] for r in conn.execute(
            "SELECT asset_id FROM loan_devices")}
    return [a for a in _assets().list_assets()
            if a.asset_id not in pooled and a.is_active]


# ── Loans ───────────────────────────────────────────────────────────

_LOAN_SELECT = """
SELECT l.*, a.asset_tag, a.name AS device_name,
       COALESCE(s.first_name || ' ' || s.last_name,
                sf.first_name || ' ' || sf.last_name) AS borrower_name
FROM device_loans l
JOIN assets a ON a.asset_id = l.asset_id
LEFT JOIN students s ON s.student_id = l.student_id
LEFT JOIN staff sf ON sf.staff_id = l.staff_id
"""


def _loan(r: _sql.Row) -> Loan:
    return Loan(
        loan_id=r["loan_id"], asset_id=r["asset_id"],
        borrower_type=r["borrower_type"], student_id=r["student_id"],
        staff_id=r["staff_id"], issued_on=r["issued_on"], due_on=r["due_on"],
        returned_on=r["returned_on"], condition_out=r["condition_out"],
        condition_in=r["condition_in"],
        charger_issued=bool(r["charger_issued"]),
        charger_returned=(None if r["charger_returned"] is None
                          else bool(r["charger_returned"])),
        accessories_issued=r["accessories_issued"],
        bursary_funded=bool(r["bursary_funded"]),
        bursary_application_id=r["bursary_application_id"],
        aup_acceptance_id=r["aup_acceptance_id"],
        aup_version=r["aup_version"], status=r["status"],
        lost_on=r["lost_on"], damage_notes=r["damage_notes"],
        charge_amount=float(r["charge_amount"] or 0),
        charge_status=r["charge_status"],
        charge_settled_on=r["charge_settled_on"],
        charge_note=r["charge_note"],
        extended_count=int(r["extended_count"] or 0),
        issued_by=r["issued_by"], returned_to=r["returned_to"],
        notes=r["notes"], created_at=r["created_at"],
        updated_at=r["updated_at"], asset_tag=r["asset_tag"],
        device_name=r["device_name"], borrower_name=r["borrower_name"])


def _validate_bursary(application_id: Any, student_id: str | None
                      ) -> int | None:
    if application_id in (None, ""):
        return None
    try:
        app_id = int(application_id)
    except (TypeError, ValueError):
        raise ValidationError("Bursary award must be an application number"
                              ) from None
    if student_id is None:
        raise ValidationError("Only a student's loan can be bursary funded")
    app = _bursaries().get_application(app_id)
    if app is None:
        raise ValidationError(f"No bursary application #{app_id}")
    if app.student_id != student_id:
        raise ValidationError(
            f"Bursary application #{app_id} belongs to another student")
    if not app.is_approved:
        raise ValidationError(
            f"Bursary application #{app_id} is {app.status}, not approved")
    return app_id


def bursary_awards_for(student_id: str) -> list[Any]:
    """Approved bursary applications a loan could be linked to."""
    return _bursaries().list_applications(student_id=student_id,
                                          approved_only=True)


def issue_loan(asset_id: int, payload: dict[str, Any]) -> Loan:
    """Lend a pool device.

    ``payload``: ``borrower_type`` (Student / Staff), ``student_id`` or
    ``staff_id``, ``issued_on`` (today), ``due_on`` (issued + the
    device's usual loan length), ``condition_out`` (the asset's current
    condition), ``charger_issued`` (the device default), accessories,
    ``bursary_application_id`` (implies bursary funded) or
    ``bursary_funded``, ``allow_second``, ``notes``.
    """
    init_db()
    p = _require_ops("issue device loans")
    d = _require_device(asset_id)
    if not d.loanable:
        raise ValidationError(f"{d.label} is not available for loan")
    if d.open_loan_id:
        raise ValidationError(f"{d.label} is already on loan to {d.borrower}")
    if d.asset_status in _UNUSABLE:
        raise ValidationError(f"{d.label} is {d.asset_status}")

    btype = _choice(payload.get("borrower_type"), BORROWER_TYPES,
                    "Borrower type", STUDENT)
    pid_raw = payload.get("student_id" if btype == STUDENT else "staff_id") \
        or payload.get("borrower_id")
    btype, pid, name = aup.resolve_person(btype, pid_raw)
    if btype == STUDENT:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _st,
        )
        s = _st.get_student(pid)
        if s is not None and not s.on_roll:
            raise ValidationError(f"{name} is not on roll ({s.status})")
    else:
        from education_system.systems.sixth_form.domain.staff import (
            staff as _staff,
        )
        st = _staff.get_staff(pid)
        if st is not None and not st.is_active:
            raise ValidationError(f"{name} is {st.employment_status}")

    acceptance = aup.require_current_acceptance(btype, pid)

    issued = _date(payload.get("issued_on"), "Issued on") \
        or _dt.date.today().isoformat()
    due = _date(payload.get("due_on"), "Due on") or (
        _dt.date.fromisoformat(issued)
        + _dt.timedelta(days=d.default_loan_days)).isoformat()
    if due < issued:
        raise ValidationError("Due date is before the issue date")
    cond = _choice(payload.get("condition_out"), conditions(),
                   "Condition out", d.condition)
    charger = _bool(payload.get("charger_issued"), d.includes_charger)
    bursary_app = _validate_bursary(payload.get("bursary_application_id"),
                                    pid if btype == STUDENT else None)
    funded = bursary_app is not None or _bool(payload.get("bursary_funded"),
                                              False)
    if funded and btype != STUDENT:
        raise ValidationError("Only a student's loan can be bursary funded")

    with _connect() as conn:
        col = "student_id" if btype == STUDENT else "staff_id"
        held = conn.execute(
            f"SELECT l.loan_id, a.asset_tag FROM device_loans l JOIN assets "
            f"a ON a.asset_id=l.asset_id WHERE l.{col}=? AND "
            "l.status='On Loan'", (pid,)).fetchall()
        if held and btype == STUDENT and not payload.get("allow_second"):
            raise ValidationError(
                f"{name} already has device {held[0]['asset_tag']} on loan")
        try:
            cur = conn.execute(
                "INSERT INTO device_loans (asset_id, borrower_type, "
                "student_id, staff_id, issued_on, due_on, condition_out, "
                "charger_issued, accessories_issued, bursary_funded, "
                "bursary_application_id, aup_acceptance_id, aup_version, "
                "status, issued_by, notes) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (d.asset_id, btype, pid if btype == STUDENT else None,
                 pid if btype == STAFF else None, issued, due, cond,
                 1 if charger else 0,
                 _text(payload.get("accessories_issued", d.accessories)),
                 1 if funded else 0, bursary_app, acceptance.acceptance_id,
                 acceptance.version, ON_LOAN, _who(p),
                 _text(payload.get("notes"))))
        except _sql.IntegrityError:
            raise ValidationError(f"{d.label} is already on loan") from None
        new_id = cur.lastrowid
    _assets().update_asset(d.asset_id, {"status": "On Loan",
                                        "condition": cond})
    logger.info("Device %s lent to %s %s until %s (loan #%d)",
                d.asset_tag, btype, pid, due, new_id)
    return _require_loan(new_id)


def extend_loan(loan_id: int, due_on: str, *,
                reason: str | None = None) -> Loan:
    _require_ops("extend device loans")
    ln = _require_loan(loan_id)
    if not ln.is_open:
        raise ValidationError("Only an open loan can be extended")
    new_due = _date(due_on, "New due date", required=True)
    if new_due <= ln.due_on:
        raise ValidationError("The new due date must be after the current "
                              f"one ({ln.due_on})")
    note = f"extended to {new_due}" + (f": {reason.strip()}"
                                      if reason and reason.strip() else "")
    with _connect() as conn:
        conn.execute(
            "UPDATE device_loans SET due_on=?, extended_count="
            "extended_count+1, notes=COALESCE(notes || '; ', '') || ?, "
            "updated_at=datetime('now') WHERE loan_id=?",
            (new_due, note, loan_id))
    return _require_loan(loan_id)


def return_loan(loan_id: int, *, returned_on: str | None = None,
                condition_in: str | None = None,
                charger_returned: bool | None = None,
                damage_notes: str | None = None,
                charge_amount: Any = None,
                notes: str | None = None) -> Loan:
    """Book a device back in. A Damaged return needs notes, sends the
    asset to Awaiting Repair and can raise a charge; otherwise the asset
    goes back In Storage in the condition recorded."""
    p = _require_ops("return device loans")
    ln = _require_loan(loan_id)
    if not ln.is_open:
        raise ValidationError(f"Loan #{loan_id} is {ln.status}")
    on = _date(returned_on, "Returned on") or _dt.date.today().isoformat()
    if on < ln.issued_on:
        raise ValidationError("Return date is before the issue date")
    cond = _choice(condition_in, conditions(), "Condition in",
                   ln.condition_out)
    damaged = cond == "Damaged"
    dmg = _text(damage_notes)
    if damaged and not dmg:
        raise ValidationError("Describe the damage")
    charger_back = (ln.charger_issued if charger_returned is None
                    else bool(charger_returned))
    if not ln.charger_issued:
        charger_back = None
    charge = _money(charge_amount, "Charge")
    status = RETURNED_DAMAGED if damaged else RETURNED
    with _connect() as conn:
        conn.execute(
            "UPDATE device_loans SET status=?, returned_on=?, condition_in=?,"
            " charger_returned=?, damage_notes=?, charge_amount=?, "
            "charge_status=?, returned_to=?, "
            "notes=CASE WHEN ? IS NULL THEN notes "
            "ELSE COALESCE(notes || '; ', '') || ? END, "
            "updated_at=datetime('now') WHERE loan_id=?",
            (status, on, cond,
             None if charger_back is None else int(charger_back), dmg,
             charge, CHARGE_DUE if charge else CHARGE_NONE, _who(p),
             _text(notes), _text(notes), loan_id))
    _assets().update_asset(ln.asset_id, {
        "status": "Awaiting Repair" if damaged else "In Storage",
        "condition": cond})
    return _require_loan(loan_id)


def report_lost(loan_id: int, *, lost_on: str | None = None,
                charge_amount: Any = None,
                notes: str | None = None) -> Loan:
    """The borrower has lost the device (or it was stolen). The asset is
    marked Lost/Stolen in the register."""
    _require_ops("record lost devices")
    ln = _require_loan(loan_id)
    if not ln.is_open:
        raise ValidationError(f"Loan #{loan_id} is {ln.status}")
    on = _date(lost_on, "Lost on") or _dt.date.today().isoformat()
    if on < ln.issued_on:
        raise ValidationError("Lost date is before the issue date")
    charge = _money(charge_amount, "Charge")
    with _connect() as conn:
        conn.execute(
            "UPDATE device_loans SET status=?, lost_on=?, charge_amount=?, "
            "charge_status=?, damage_notes=COALESCE(?, damage_notes), "
            "updated_at=datetime('now') WHERE loan_id=?",
            (LOST, on, charge, CHARGE_DUE if charge else CHARGE_NONE,
             _text(notes), loan_id))
    _assets().update_asset(ln.asset_id, {
        "status": "Lost/Stolen", "disposal_date": on,
        "disposal_method": "Lost"})
    return _require_loan(loan_id)


def mark_found(loan_id: int, *, returned_on: str | None = None,
               condition_in: str | None = None,
               notes: str | None = None) -> Loan:
    """A lost device has turned up: close the loan as returned and put
    the asset back In Storage. A charge already raised is left for the
    office to waive or keep."""
    p = _require_ops("record found devices")
    ln = _require_loan(loan_id)
    if ln.status != LOST:
        raise ValidationError("Only a lost device can be marked found")
    on = _date(returned_on, "Returned on") or _dt.date.today().isoformat()
    cond = _choice(condition_in, conditions(), "Condition in",
                   ln.condition_out)
    note = "found after being reported lost" + (
        f": {notes.strip()}" if notes and notes.strip() else "")
    with _connect() as conn:
        conn.execute(
            "UPDATE device_loans SET status=?, returned_on=?, condition_in=?,"
            " returned_to=?, notes=COALESCE(notes || '; ', '') || ?, "
            "updated_at=datetime('now') WHERE loan_id=?",
            (RETURNED_DAMAGED if cond == "Damaged" else RETURNED, on, cond,
             _who(p), note, loan_id))
    a = _assets()
    a.set_status(ln.asset_id, "In Storage")
    a.update_asset(ln.asset_id, {
        "condition": cond,
        "status": "Awaiting Repair" if cond == "Damaged" else "In Storage"})
    return _require_loan(loan_id)


def record_charge_paid(loan_id: int, *, paid_on: str | None = None) -> Loan:
    _require_ops("record device charges")
    ln = _require_loan(loan_id)
    if ln.charge_status != CHARGE_DUE:
        raise ValidationError(f"Charge is {ln.charge_status}, not Due")
    on = _date(paid_on, "Paid on") or _dt.date.today().isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE device_loans SET charge_status=?, charge_settled_on=?, "
            "updated_at=datetime('now') WHERE loan_id=?",
            (CHARGE_PAID, on, loan_id))
    return _require_loan(loan_id)


def waive_charge(loan_id: int, reason: str) -> Loan:
    _require_ops("waive device charges")
    ln = _require_loan(loan_id)
    if ln.charge_status != CHARGE_DUE:
        raise ValidationError(f"Charge is {ln.charge_status}, not Due")
    why = _text(reason)
    if not why:
        raise ValidationError("Give a reason for waiving the charge")
    with _connect() as conn:
        conn.execute(
            "UPDATE device_loans SET charge_status=?, charge_settled_on=?, "
            "charge_note=?, updated_at=datetime('now') WHERE loan_id=?",
            (CHARGE_WAIVED, _dt.date.today().isoformat(), why, loan_id))
    return _require_loan(loan_id)


def set_charge(loan_id: int, amount: Any, *, note: str | None = None
               ) -> Loan:
    """Raise or change the charge on a closed loan (e.g. once the repair
    quote is in)."""
    _require_ops("set device charges")
    ln = _require_loan(loan_id)
    if ln.is_open:
        raise ValidationError("Return the device or report it lost first")
    if ln.charge_status in (CHARGE_PAID, CHARGE_WAIVED):
        raise ValidationError(f"The charge is already {ln.charge_status}")
    amt = _money(amount, "Charge")
    with _connect() as conn:
        conn.execute(
            "UPDATE device_loans SET charge_amount=?, charge_status=?, "
            "charge_note=COALESCE(?, charge_note), "
            "updated_at=datetime('now') WHERE loan_id=?",
            (amt, CHARGE_DUE if amt else CHARGE_NONE, _text(note), loan_id))
    return _require_loan(loan_id)


def cancel_loan(loan_id: int) -> bool:
    """Delete a loan issued in error — only while open and on the day it
    was issued; afterwards return it instead so the history stands."""
    _require_ops("cancel device loans")
    ln = _require_loan(loan_id)
    if not ln.is_open or ln.issued_on != _dt.date.today().isoformat() \
            or ln.created_at[:10] != _dt.date.today().isoformat():
        raise ValidationError("Only a loan issued today in error can be "
                              "cancelled — book it back in instead")
    with _connect() as conn:
        cur = conn.execute("DELETE FROM device_loans WHERE loan_id=?",
                           (loan_id,))
    _assets().update_asset(ln.asset_id, {"status": "In Storage"})
    return bool(cur.rowcount)


def get_loan(loan_id: int) -> Loan | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(f"{_LOAN_SELECT} WHERE l.loan_id=?",
                         (int(loan_id),)).fetchone()
    return _loan(r) if r else None


def _require_loan(loan_id: int) -> Loan:
    ln = get_loan(loan_id)
    if ln is None:
        raise ValidationError(f"No device loan #{loan_id}")
    return ln


def list_loans(*, student_id: str | None = None,
               staff_id: str | None = None,
               asset_id: int | None = None,
               status: str | None = None,
               open_only: bool = False,
               bursary_only: bool = False,
               charge_status: str | None = None) -> list[Loan]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("l.student_id = ?")
        args.append(student_id.strip())
    if staff_id:
        clauses.append("l.staff_id = ?")
        args.append(staff_id.strip().upper())
    if asset_id is not None:
        clauses.append("l.asset_id = ?")
        args.append(int(asset_id))
    if status:
        clauses.append("l.status = ?")
        args.append(_choice(status, LOAN_STATUSES, "Status"))
    if open_only:
        clauses.append("l.status = 'On Loan'")
    if bursary_only:
        clauses.append("l.bursary_funded = 1")
    if charge_status:
        clauses.append("l.charge_status = ?")
        args.append(_choice(charge_status, CHARGE_STATUSES, "Charge"))
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [_loan(r) for r in conn.execute(
            f"{_LOAN_SELECT}{where} ORDER BY l.status <> 'On Loan', "
            "l.due_on, l.loan_id DESC", args).fetchall()]


def overdue_loans(*, as_of: str | None = None) -> list[Loan]:
    day = _date(as_of, "As of") or _dt.date.today().isoformat()
    return [ln for ln in list_loans(open_only=True) if ln.due_on < day]


def device_history(asset_id: int) -> list[Loan]:
    return list_loans(asset_id=asset_id)


def loans_for_student(student_id: str) -> list[Loan]:
    """A student's loans, open first (for the student portal). The
    signed-in user must be the student or staff who may see them."""
    access = _access()
    p = access.current()
    sid = _text(student_id)
    if not sid:
        raise ValidationError("Student is required")
    if not access.can_see_student(p, sid):
        raise access.AccessDenied(
            f"{p.username or 'This account'} may not see another "
            "student's device loans.")
    return list_loans(student_id=sid)


def loans_for_staff(staff_id: str) -> list[Loan]:
    return list_loans(staff_id=staff_id)


def summary(*, as_of: str | None = None) -> LoanSummary:
    out = LoanSummary()
    for d in list_devices():
        out.devices += 1
        pool = out.by_pool.setdefault(d.loan_pool, {
            "Devices": 0, "Available": 0, "On loan": 0, "Unusable": 0})
        pool["Devices"] += 1
        if d.open_loan_id:
            out.on_loan += 1
            pool["On loan"] += 1
        elif d.available:
            out.available += 1
            pool["Available"] += 1
        else:
            out.unusable += 1
            pool["Unusable"] += 1
    day = _date(as_of, "As of") or _dt.date.today().isoformat()
    for ln in list_loans():
        if ln.is_open:
            out.overdue += ln.due_on < day
            out.bursary_funded_open += ln.bursary_funded
        out.lost += ln.status == LOST
        out.damaged += ln.status == RETURNED_DAMAGED
        if ln.charge_status == CHARGE_DUE:
            out.charges_due += ln.charge_amount
        elif ln.charge_status == CHARGE_PAID:
            out.charges_paid += ln.charge_amount
    out.charges_due = round(out.charges_due, 2)
    out.charges_paid = round(out.charges_paid, 2)
    cur = aup.current_aup()
    out.aup_version = cur.version if cur else None
    out.students_without_aup = len(aup.outstanding(STUDENT)) if cur else 0
    return out
