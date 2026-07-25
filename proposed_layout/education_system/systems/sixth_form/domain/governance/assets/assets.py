"""Assets data layer for the Sixth Form System.

Fixed-asset register with two tables:

* ``assets`` — one row per fixed asset. Carries identification
  (tag, name, category, manufacturer, model, serial), physical
  location (location + room), ownership (custodian = staff),
  acquisition data (purchase_date, cost, supplier, warranty),
  depreciation parameters, current condition + status, optional
  disposal info, and audit dates.
* ``asset_maintenance`` — service / inspection / PAT / repair
  log entries for an asset. Cascade-delete with the parent.

Book value (computed on the fly via :func:`book_value`):

* "None"          → returns ``purchase_cost``.
* "Straight Line" → cost − (cost − residual) * y / life
* "Reducing Balance" → cost * (1 − r) ** y,
                       where r = 1 − (residual / cost) ** (1 / life)

Years-in-service ``y`` is clamped to ``[0, useful_life_years]`` and
the result is clamped to ``>= residual_value``.

Custodian is a staff FK (ON DELETE SET NULL). Student FK is not
used — assets belong to the institution, not pupils.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date as _date
from decimal import Decimal, InvalidOperation
from typing import Any
from education_system.systems.sixth_form.infrastructure import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.ASSETS_DB

CATEGORIES: tuple[str, ...] = (
    "Laptop", "Desktop", "Tablet", "Monitor", "Projector",
    "Printer", "Network Equipment", "Server", "Audio/Visual",
    "Lab Equipment", "Science Equipment", "Sports Equipment",
    "Musical Instrument", "Furniture", "Kitchen Equipment",
    "Vehicle", "Tool", "Book/Resource", "Software License",
    "Other",
)
DEFAULT_CATEGORY: str = "Other"

CONDITIONS: tuple[str, ...] = (
    "New", "Excellent", "Good", "Fair", "Poor", "Damaged",
)
DEFAULT_CONDITION: str = "Good"

STATUSES: tuple[str, ...] = (
    "In Use", "In Storage", "On Loan", "Awaiting Repair",
    "In Repair", "Retired", "Disposed", "Lost/Stolen",
)
DEFAULT_STATUS: str = "In Use"
DISPOSED_STATUSES: tuple[str, ...] = ("Disposed", "Lost/Stolen")

DEPRECIATION_METHODS: tuple[str, ...] = (
    "Straight Line", "Reducing Balance", "None",
)
DEFAULT_DEPRECIATION_METHOD: str = "Straight Line"

DISPOSAL_METHODS: tuple[str, ...] = (
    "Sold", "Donated", "Recycled", "Scrapped",
    "Lost", "Stolen", "Other",
)

SERVICE_TYPES: tuple[str, ...] = (
    "Inspection", "Routine Service", "Calibration", "Repair",
    "Software Update", "PAT Test", "Cleaning",
    "Replacement Parts", "Other",
)
DEFAULT_SERVICE_TYPE: str = "Inspection"

MAINTENANCE_OUTCOMES: tuple[str, ...] = (
    "Completed", "Failed", "Partial", "Scheduled", "Cancelled",
)
DEFAULT_MAINTENANCE_OUTCOME: str = "Completed"

CURRENCY_SYMBOL: str = "£"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-_/]{0,31}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    asset_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_tag            TEXT NOT NULL UNIQUE,
    name                 TEXT NOT NULL,
    category             TEXT NOT NULL DEFAULT 'Other',
    manufacturer         TEXT,
    model                TEXT,
    serial_number        TEXT,
    location             TEXT NOT NULL,
    room                 TEXT,
    custodian_id         TEXT,
    purchase_date        TEXT,
    purchase_cost        REAL,
    supplier             TEXT,
    warranty_expiry      TEXT,
    useful_life_years    INTEGER,
    depreciation_method  TEXT NOT NULL DEFAULT 'Straight Line',
    residual_value       REAL NOT NULL DEFAULT 0,
    condition            TEXT NOT NULL DEFAULT 'Good',
    status               TEXT NOT NULL DEFAULT 'In Use',
    disposal_date        TEXT,
    disposal_method      TEXT,
    disposal_proceeds    REAL,
    last_audit_date      TEXT,
    next_audit_due       TEXT,
    notes                TEXT,
    created_at           TEXT DEFAULT (datetime('now')),
    updated_at           TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (custodian_id) REFERENCES staff(staff_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS asset_maintenance (
    maintenance_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id          INTEGER NOT NULL,
    service_date      TEXT NOT NULL,
    service_type      TEXT NOT NULL DEFAULT 'Inspection',
    performed_by      TEXT,
    staff_id          TEXT,
    cost              REAL,
    outcome           TEXT NOT NULL DEFAULT 'Completed',
    next_service_due  TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
        ON DELETE CASCADE,
    FOREIGN KEY (staff_id) REFERENCES staff(staff_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_assets_tag       ON assets(asset_tag);
CREATE INDEX IF NOT EXISTS idx_assets_category  ON assets(category);
CREATE INDEX IF NOT EXISTS idx_assets_status    ON assets(status);
CREATE INDEX IF NOT EXISTS idx_assets_location  ON assets(location);
CREATE INDEX IF NOT EXISTS idx_assets_custodian ON assets(custodian_id);
CREATE INDEX IF NOT EXISTS idx_amaint_asset     ON asset_maintenance(asset_id);
CREATE INDEX IF NOT EXISTS idx_amaint_date      ON asset_maintenance(service_date);
"""


@dataclass
class Asset:
    asset_id: int
    asset_tag: str
    name: str
    category: str
    manufacturer: str | None
    model: str | None
    serial_number: str | None
    location: str
    room: str | None
    custodian_id: str | None
    purchase_date: str | None
    purchase_cost: float | None
    supplier: str | None
    warranty_expiry: str | None
    useful_life_years: int | None
    depreciation_method: str
    residual_value: float
    condition: str
    status: str
    disposal_date: str | None
    disposal_method: str | None
    disposal_proceeds: float | None
    last_audit_date: str | None
    next_audit_due: str | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_disposed(self) -> bool:
        return self.status in DISPOSED_STATUSES

    @property
    def is_active(self) -> bool:
        return self.status not in (
            "Retired", "Disposed", "Lost/Stolen")

    @property
    def warranty_expired(self) -> bool:
        if not self.warranty_expiry:
            return False
        return self.warranty_expiry < _date.today().isoformat()

    @property
    def audit_overdue(self) -> bool:
        if not self.next_audit_due:
            return False
        return (self.next_audit_due < _date.today().isoformat()
                and self.is_active)


@dataclass
class MaintenanceEntry:
    maintenance_id: int
    asset_id: int
    service_date: str
    service_type: str
    performed_by: str | None
    staff_id: str | None
    cost: float | None
    outcome: str
    next_service_due: str | None
    notes: str | None
    created_at: str
    updated_at: str


@dataclass
class AssetView:
    asset: Asset
    maintenance_count: int
    last_service_date: str | None
    custodian_name: str | None
    current_book_value: float
    age_days: int


@dataclass
class Summary:
    total_assets: int
    by_category: dict[str, int]
    by_status: dict[str, int]
    by_condition: dict[str, int]
    by_location: list[tuple[str, int]]
    total_purchase_cost: float
    total_book_value: float
    count_overdue_service: int
    count_warranty_expired: int
    count_due_for_audit: int


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
    from education_system.systems.sixth_form.domain.staff import (
        staff as _staff,
    )
    _staff.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Assets schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_asset(r: sqlite3.Row) -> Asset:
    return Asset(
        asset_id=r["asset_id"], asset_tag=r["asset_tag"],
        name=r["name"], category=r["category"],
        manufacturer=r["manufacturer"], model=r["model"],
        serial_number=r["serial_number"],
        location=r["location"], room=r["room"],
        custodian_id=r["custodian_id"],
        purchase_date=r["purchase_date"],
        purchase_cost=r["purchase_cost"], supplier=r["supplier"],
        warranty_expiry=r["warranty_expiry"],
        useful_life_years=r["useful_life_years"],
        depreciation_method=r["depreciation_method"],
        residual_value=r["residual_value"] or 0.0,
        condition=r["condition"], status=r["status"],
        disposal_date=r["disposal_date"],
        disposal_method=r["disposal_method"],
        disposal_proceeds=r["disposal_proceeds"],
        last_audit_date=r["last_audit_date"],
        next_audit_due=r["next_audit_due"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_maint(r: sqlite3.Row) -> MaintenanceEntry:
    return MaintenanceEntry(
        maintenance_id=r["maintenance_id"],
        asset_id=r["asset_id"],
        service_date=r["service_date"],
        service_type=r["service_type"],
        performed_by=r["performed_by"],
        staff_id=r["staff_id"], cost=r["cost"],
        outcome=r["outcome"],
        next_service_due=r["next_service_due"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def _require(v, label: str):
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        raise ValidationError(f"{label} is required")
    return v


def _validate_amount(v: Any, label: str, *,
                       required: bool = False,
                       allow_zero: bool = True) -> float | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    try:
        d = Decimal(str(v))
    except (InvalidOperation, TypeError):
        raise ValidationError(f"{label} must be a number") from None
    if d.as_tuple().exponent < -2:
        raise ValidationError(
            f"{label} must have at most 2 decimal places")
    if d < 0:
        raise ValidationError(f"{label} cannot be negative")
    if not allow_zero and d == 0:
        raise ValidationError(f"{label} cannot be zero")
    return float(d.quantize(Decimal("0.01")))


def _validate_date(v: Any, label: str, *,
                    required: bool = False) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    s = str(v).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} must be a valid date") from None
    return s


def _validate_staff(v: Any) -> str | None:
    if v in (None, "") or (isinstance(v, str) and not v.strip()):
        return None
    sid = str(v).strip().upper()
    from education_system.systems.sixth_form.domain.staff import (
        staff as _staff,
    )
    if _staff.get_staff(sid) is None:
        raise ValidationError(f"No staff with id {sid}")
    return sid


def _validate_asset_payload(d: dict[str, Any],
                              *, existing_id: int | None = None
                              ) -> dict[str, Any]:
    out: dict[str, Any] = {}

    tag = _require(d.get("asset_tag"), "Asset tag")
    tag = str(tag).strip()
    if not _TAG_RE.match(tag):
        raise ValidationError(
            "Asset tag must be 1..32 chars of letters/digits/-_/")
    # Uniqueness check (case-sensitive at DB level).
    with _connect() as conn:
        r = conn.execute(
            "SELECT asset_id FROM assets WHERE asset_tag = ?",
            (tag,)).fetchone()
    if r and r["asset_id"] != existing_id:
        raise ValidationError(f"Asset tag '{tag}' is already in use")
    out["asset_tag"] = tag

    out["name"] = str(_require(d.get("name"), "Name")).strip()

    cat = (d.get("category") or DEFAULT_CATEGORY).strip()
    if cat not in CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(CATEGORIES)}")
    out["category"] = cat

    for k in ("manufacturer", "model", "serial_number",
                "room", "supplier", "notes"):
        v = d.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None

    out["location"] = str(
        _require(d.get("location"), "Location")).strip()

    out["custodian_id"] = _validate_staff(d.get("custodian_id"))

    out["purchase_date"] = _validate_date(
        d.get("purchase_date"), "Purchase date")
    out["warranty_expiry"] = _validate_date(
        d.get("warranty_expiry"), "Warranty expiry")
    out["last_audit_date"] = _validate_date(
        d.get("last_audit_date"), "Last audit date")
    out["next_audit_due"] = _validate_date(
        d.get("next_audit_due"), "Next audit due")

    out["purchase_cost"] = _validate_amount(
        d.get("purchase_cost"), "Purchase cost")
    out["residual_value"] = _validate_amount(
        d.get("residual_value"), "Residual value") or 0.0

    if out["purchase_cost"] is None and out["residual_value"] > 0:
        raise ValidationError(
            "Residual value requires a purchase cost")
    if (out["purchase_cost"] is not None
            and out["residual_value"] > out["purchase_cost"]):
        raise ValidationError(
            "Residual value cannot exceed purchase cost")
    if (out["purchase_cost"] is not None
            and not out["purchase_date"]):
        raise ValidationError(
            "Purchase date is required when purchase cost is set")

    life_raw = d.get("useful_life_years")
    if life_raw in (None, ""):
        out["useful_life_years"] = None
    else:
        try:
            life = int(life_raw)
        except (TypeError, ValueError):
            raise ValidationError(
                "Useful life must be a whole number") from None
        if life < 1 or life > 50:
            raise ValidationError(
                "Useful life must be between 1 and 50 years")
        out["useful_life_years"] = life

    method = (d.get("depreciation_method")
                or DEFAULT_DEPRECIATION_METHOD).strip()
    if method not in DEPRECIATION_METHODS:
        raise ValidationError(
            "Depreciation method must be one of: "
            f"{', '.join(DEPRECIATION_METHODS)}")
    out["depreciation_method"] = method

    cond = (d.get("condition") or DEFAULT_CONDITION).strip()
    if cond not in CONDITIONS:
        raise ValidationError(
            f"Condition must be one of: {', '.join(CONDITIONS)}")
    out["condition"] = cond

    status = (d.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    # Disposal fields only valid for disposed/lost statuses.
    disp_date = _validate_date(
        d.get("disposal_date"), "Disposal date")
    disp_method_raw = (d.get("disposal_method") or "").strip()
    disp_proceeds = _validate_amount(
        d.get("disposal_proceeds"), "Disposal proceeds")
    if status in DISPOSED_STATUSES:
        if disp_method_raw and disp_method_raw not in DISPOSAL_METHODS:
            raise ValidationError(
                "Disposal method must be one of: "
                f"{', '.join(DISPOSAL_METHODS)}")
        out["disposal_date"] = disp_date
        out["disposal_method"] = disp_method_raw or None
        out["disposal_proceeds"] = disp_proceeds
    else:
        if disp_date or disp_method_raw or disp_proceeds is not None:
            raise ValidationError(
                "Disposal fields are only valid when status is "
                "Disposed or Lost/Stolen")
        out["disposal_date"] = None
        out["disposal_method"] = None
        out["disposal_proceeds"] = None

    return out


def _validate_maint_payload(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["service_date"] = _validate_date(
        d.get("service_date") or _date.today().isoformat(),
        "Service date", required=True)

    stype = (d.get("service_type") or DEFAULT_SERVICE_TYPE).strip()
    if stype not in SERVICE_TYPES:
        raise ValidationError(
            "Service type must be one of: "
            f"{', '.join(SERVICE_TYPES)}")
    out["service_type"] = stype

    out["performed_by"] = (
        d.get("performed_by") or "").strip() or None
    out["staff_id"] = _validate_staff(d.get("staff_id"))
    out["cost"] = _validate_amount(d.get("cost"), "Cost")

    outcome = (d.get("outcome")
                  or DEFAULT_MAINTENANCE_OUTCOME).strip()
    if outcome not in MAINTENANCE_OUTCOMES:
        raise ValidationError(
            "Outcome must be one of: "
            f"{', '.join(MAINTENANCE_OUTCOMES)}")
    out["outcome"] = outcome

    out["next_service_due"] = _validate_date(
        d.get("next_service_due"), "Next service due")
    out["notes"] = (d.get("notes") or "").strip() or None
    return out


# ── Asset CRUD ───────────────────────────────────────────────────

def create_asset(d: dict[str, Any]) -> Asset:
    init_db()
    p = _validate_asset_payload(d)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO assets (
                  asset_tag, name, category, manufacturer, model,
                  serial_number, location, room, custodian_id,
                  purchase_date, purchase_cost, supplier,
                  warranty_expiry, useful_life_years,
                  depreciation_method, residual_value,
                  condition, status, disposal_date, disposal_method,
                  disposal_proceeds, last_audit_date, next_audit_due,
                  notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (p["asset_tag"], p["name"], p["category"],
             p["manufacturer"], p["model"], p["serial_number"],
             p["location"], p["room"], p["custodian_id"],
             p["purchase_date"], p["purchase_cost"], p["supplier"],
             p["warranty_expiry"], p["useful_life_years"],
             p["depreciation_method"], p["residual_value"],
             p["condition"], p["status"], p["disposal_date"],
             p["disposal_method"], p["disposal_proceeds"],
             p["last_audit_date"], p["next_audit_due"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_asset(new_id)
    assert out is not None
    logger.info("Created asset #%d %s (%s)",
                new_id, p["asset_tag"], p["category"])
    return out


def get_asset(asset_id: int) -> Asset | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM assets WHERE asset_id = ?",
            (asset_id,)).fetchone()
        return _row_asset(r) if r else None


def get_by_tag(asset_tag: str) -> Asset | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM assets WHERE asset_tag = ?",
            ((asset_tag or "").strip(),)).fetchone()
        return _row_asset(r) if r else None


def list_assets(*,
                  category: str | None = None,
                  status: str | None = None,
                  location: str | None = None,
                  custodian_id: str | None = None,
                  condition: str | None = None,
                  search: str | None = None,
                  ) -> list[Asset]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if category:
        if category not in CATEGORIES:
            raise ValidationError(
                f"Category must be one of: {', '.join(CATEGORIES)}")
        clauses.append("category = ?")
        args.append(category)
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if condition:
        if condition not in CONDITIONS:
            raise ValidationError(
                f"Condition must be one of: {', '.join(CONDITIONS)}")
        clauses.append("condition = ?")
        args.append(condition)
    if location:
        clauses.append("location LIKE ?")
        args.append(f"%{location.strip()}%")
    if custodian_id:
        clauses.append("custodian_id = ?")
        args.append(custodian_id.strip().upper())
    if search:
        like = f"%{search.strip()}%"
        clauses.append(
            "(asset_tag LIKE ? OR name LIKE ? OR manufacturer LIKE ? "
            " OR model LIKE ? OR serial_number LIKE ?)")
        args.extend([like, like, like, like, like])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM assets {where} "
           "ORDER BY category, asset_tag, asset_id")
    with _connect() as conn:
        return [_row_asset(r)
                 for r in conn.execute(sql, args).fetchall()]


def update_asset(asset_id: int, d: dict[str, Any]) -> Asset:
    init_db()
    existing = get_asset(asset_id)
    if existing is None:
        raise ValidationError(f"No asset #{asset_id}")
    merged = {
        "asset_tag":           d.get("asset_tag", existing.asset_tag),
        "name":                d.get("name", existing.name),
        "category":            d.get("category", existing.category),
        "manufacturer":        d.get("manufacturer",
                                       existing.manufacturer),
        "model":               d.get("model", existing.model),
        "serial_number":       d.get("serial_number",
                                       existing.serial_number),
        "location":            d.get("location", existing.location),
        "room":                d.get("room", existing.room),
        "custodian_id":        d.get("custodian_id",
                                       existing.custodian_id),
        "purchase_date":       d.get("purchase_date",
                                       existing.purchase_date),
        "purchase_cost":       d.get("purchase_cost",
                                       existing.purchase_cost),
        "supplier":            d.get("supplier", existing.supplier),
        "warranty_expiry":     d.get("warranty_expiry",
                                       existing.warranty_expiry),
        "useful_life_years":   d.get("useful_life_years",
                                       existing.useful_life_years),
        "depreciation_method": d.get("depreciation_method",
                                       existing.depreciation_method),
        "residual_value":      d.get("residual_value",
                                       existing.residual_value),
        "condition":           d.get("condition", existing.condition),
        "status":              d.get("status", existing.status),
        "disposal_date":       d.get("disposal_date",
                                       existing.disposal_date),
        "disposal_method":     d.get("disposal_method",
                                       existing.disposal_method),
        "disposal_proceeds":   d.get("disposal_proceeds",
                                       existing.disposal_proceeds),
        "last_audit_date":     d.get("last_audit_date",
                                       existing.last_audit_date),
        "next_audit_due":      d.get("next_audit_due",
                                       existing.next_audit_due),
        "notes":               d.get("notes", existing.notes),
    }
    p = _validate_asset_payload(merged, existing_id=asset_id)
    with _connect() as conn:
        conn.execute(
            """UPDATE assets SET
                  asset_tag=?, name=?, category=?, manufacturer=?,
                  model=?, serial_number=?, location=?, room=?,
                  custodian_id=?, purchase_date=?, purchase_cost=?,
                  supplier=?, warranty_expiry=?, useful_life_years=?,
                  depreciation_method=?, residual_value=?,
                  condition=?, status=?, disposal_date=?,
                  disposal_method=?, disposal_proceeds=?,
                  last_audit_date=?, next_audit_due=?, notes=?,
                  updated_at=datetime('now')
               WHERE asset_id=?""",
            (p["asset_tag"], p["name"], p["category"],
             p["manufacturer"], p["model"], p["serial_number"],
             p["location"], p["room"], p["custodian_id"],
             p["purchase_date"], p["purchase_cost"], p["supplier"],
             p["warranty_expiry"], p["useful_life_years"],
             p["depreciation_method"], p["residual_value"],
             p["condition"], p["status"], p["disposal_date"],
             p["disposal_method"], p["disposal_proceeds"],
             p["last_audit_date"], p["next_audit_due"], p["notes"],
             asset_id),
        )
        conn.commit()
    out = get_asset(asset_id)
    assert out is not None
    logger.info("Updated asset #%d (status=%s)",
                asset_id, out.status)
    return out


def set_status(asset_id: int, status: str) -> Asset:
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    existing = get_asset(asset_id)
    if existing is None:
        raise ValidationError(f"No asset #{asset_id}")
    payload: dict[str, Any] = {"status": status}
    # If we're leaving disposed status, clear disposal fields so the
    # disposal-fields-vs-status validation passes.
    if (status not in DISPOSED_STATUSES
            and existing.status in DISPOSED_STATUSES):
        payload["disposal_date"] = None
        payload["disposal_method"] = None
        payload["disposal_proceeds"] = None
    return update_asset(asset_id, payload)


def delete_asset(asset_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM assets WHERE asset_id = ?", (asset_id,))
        conn.commit()
        if cur.rowcount:
            logger.info(
                "Deleted asset #%d (and its maintenance log)",
                asset_id)
            return True
        return False


# ── Maintenance CRUD ─────────────────────────────────────────────

def add_maintenance(asset_id: int,
                       d: dict[str, Any]) -> MaintenanceEntry:
    init_db()
    if get_asset(asset_id) is None:
        raise ValidationError(f"No asset #{asset_id}")
    p = _validate_maint_payload(d)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO asset_maintenance (
                  asset_id, service_date, service_type,
                  performed_by, staff_id, cost, outcome,
                  next_service_due, notes,
                  created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (asset_id, p["service_date"], p["service_type"],
             p["performed_by"], p["staff_id"], p["cost"],
             p["outcome"], p["next_service_due"], p["notes"]),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = get_maintenance(new_id)
    assert out is not None
    logger.info("Added maintenance #%d on asset %d (%s)",
                new_id, asset_id, p["service_type"])
    return out


def get_maintenance(maintenance_id: int) -> MaintenanceEntry | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM asset_maintenance "
            "WHERE maintenance_id = ?",
            (maintenance_id,)).fetchone()
        return _row_maint(r) if r else None


def list_maintenance(*,
                          asset_id: int | None = None,
                          service_type: str | None = None,
                          outcome: str | None = None,
                          date_from: str | None = None,
                          date_to: str | None = None,
                          ) -> list[MaintenanceEntry]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if asset_id is not None:
        clauses.append("asset_id = ?")
        args.append(asset_id)
    if service_type:
        if service_type not in SERVICE_TYPES:
            raise ValidationError(
                f"Service type must be one of: "
                f"{', '.join(SERVICE_TYPES)}")
        clauses.append("service_type = ?")
        args.append(service_type)
    if outcome:
        if outcome not in MAINTENANCE_OUTCOMES:
            raise ValidationError(
                "Outcome must be one of: "
                f"{', '.join(MAINTENANCE_OUTCOMES)}")
        clauses.append("outcome = ?")
        args.append(outcome)
    if date_from:
        clauses.append("service_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("service_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (f"SELECT * FROM asset_maintenance {where} "
           "ORDER BY service_date DESC, maintenance_id DESC")
    with _connect() as conn:
        return [_row_maint(r)
                 for r in conn.execute(sql, args).fetchall()]


def update_maintenance(maintenance_id: int,
                          d: dict[str, Any]) -> MaintenanceEntry:
    init_db()
    existing = get_maintenance(maintenance_id)
    if existing is None:
        raise ValidationError(
            f"No maintenance entry #{maintenance_id}")
    merged = {
        "service_date":     d.get("service_date",
                                    existing.service_date),
        "service_type":     d.get("service_type",
                                    existing.service_type),
        "performed_by":     d.get("performed_by",
                                    existing.performed_by),
        "staff_id":         d.get("staff_id", existing.staff_id),
        "cost":             d.get("cost", existing.cost),
        "outcome":          d.get("outcome", existing.outcome),
        "next_service_due": d.get("next_service_due",
                                    existing.next_service_due),
        "notes":            d.get("notes", existing.notes),
    }
    p = _validate_maint_payload(merged)
    with _connect() as conn:
        conn.execute(
            """UPDATE asset_maintenance SET
                  service_date=?, service_type=?, performed_by=?,
                  staff_id=?, cost=?, outcome=?,
                  next_service_due=?, notes=?,
                  updated_at=datetime('now')
               WHERE maintenance_id=?""",
            (p["service_date"], p["service_type"],
             p["performed_by"], p["staff_id"], p["cost"],
             p["outcome"], p["next_service_due"], p["notes"],
             maintenance_id),
        )
        conn.commit()
    out = get_maintenance(maintenance_id)
    assert out is not None
    logger.info("Updated maintenance #%d", maintenance_id)
    return out


def delete_maintenance(maintenance_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM asset_maintenance "
            "WHERE maintenance_id = ?", (maintenance_id,))
        conn.commit()
        if cur.rowcount:
            logger.info("Deleted maintenance #%d", maintenance_id)
            return True
        return False


# ── Book value & views ───────────────────────────────────────────

def book_value(asset: Asset, *,
                  as_of: _date | None = None) -> float:
    """Compute current book value for an asset.

    Returns ``purchase_cost`` if depreciation is "None" or required
    parameters are missing. Otherwise applies the selected schedule.
    Result is clamped to ``>= residual_value`` and ``<= purchase_cost``.
    """
    cost = asset.purchase_cost
    if cost is None or cost <= 0:
        return 0.0
    residual = float(asset.residual_value or 0.0)
    method = asset.depreciation_method
    if method == "None" or not asset.useful_life_years \
            or not asset.purchase_date:
        return round(cost, 2)
    today = as_of or _date.today()
    try:
        pd = _date.fromisoformat(asset.purchase_date)
    except ValueError:
        return round(cost, 2)
    years = max(0.0, (today - pd).days / 365.25)
    life = float(asset.useful_life_years)
    y = min(years, life)
    if method == "Straight Line":
        depreciable = max(0.0, cost - residual)
        value = cost - depreciable * (y / life)
    elif method == "Reducing Balance":
        if residual <= 0 or residual >= cost:
            # Fall back to a 25% reducing balance default if the
            # rate is undefined (residual=0 or >= cost).
            r = 0.25
        else:
            r = 1.0 - (residual / cost) ** (1.0 / life)
        value = cost * ((1.0 - r) ** y)
    else:
        value = cost
    value = max(residual, min(cost, value))
    return round(value, 2)


def _custodian_names() -> dict[str, str]:
    from education_system.systems.sixth_form.domain.staff import (
        staff as _staff,
    )
    try:
        rows = _staff.list_staff()
    except Exception:
        return {}
    return {s.staff_id: s.full_name for s in rows}


def _maint_aggregates() -> dict[int, tuple[int, str | None]]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT asset_id, COUNT(*) AS n,
                       MAX(service_date) AS last_date
                FROM asset_maintenance GROUP BY asset_id"""
        ).fetchall()
    return {r["asset_id"]: (r["n"], r["last_date"]) for r in rows}


def view_asset(asset_id: int) -> AssetView | None:
    a = get_asset(asset_id)
    if a is None:
        return None
    agg = _maint_aggregates().get(asset_id, (0, None))
    names = _custodian_names()
    age_days = 0
    if a.purchase_date:
        try:
            pd = _date.fromisoformat(a.purchase_date)
            age_days = max(0, (_date.today() - pd).days)
        except ValueError:
            age_days = 0
    return AssetView(
        asset=a,
        maintenance_count=agg[0],
        last_service_date=agg[1],
        custodian_name=(names.get(a.custodian_id)
                          if a.custodian_id else None),
        current_book_value=book_value(a),
        age_days=age_days,
    )


def list_views(**kwargs) -> list[AssetView]:
    assets = list_assets(**kwargs)
    if not assets:
        return []
    agg = _maint_aggregates()
    names = _custodian_names()
    today = _date.today()
    out: list[AssetView] = []
    for a in assets:
        n, last = agg.get(a.asset_id, (0, None))
        age = 0
        if a.purchase_date:
            try:
                pd = _date.fromisoformat(a.purchase_date)
                age = max(0, (today - pd).days)
            except ValueError:
                age = 0
        out.append(AssetView(
            asset=a, maintenance_count=n,
            last_service_date=last,
            custodian_name=(names.get(a.custodian_id)
                              if a.custodian_id else None),
            current_book_value=book_value(a, as_of=today),
            age_days=age,
        ))
    return out


# ── Summary ──────────────────────────────────────────────────────

def summary() -> Summary:
    init_db()
    views = list_views()
    by_category: dict[str, int] = {c: 0 for c in CATEGORIES}
    by_status: dict[str, int] = {s: 0 for s in STATUSES}
    by_condition: dict[str, int] = {c: 0 for c in CONDITIONS}
    location_counts: dict[str, int] = {}
    total_cost = 0.0
    total_book = 0.0
    overdue_service = 0
    warranty_exp = 0
    audit_due = 0
    today = _date.today().isoformat()
    for v in views:
        a = v.asset
        by_category[a.category] = by_category.get(a.category, 0) + 1
        by_status[a.status] = by_status.get(a.status, 0) + 1
        by_condition[a.condition] = (
            by_condition.get(a.condition, 0) + 1)
        location_counts[a.location] = (
            location_counts.get(a.location, 0) + 1)
        if a.purchase_cost:
            total_cost += a.purchase_cost
        total_book += v.current_book_value
        if (v.last_service_date is None
                and a.is_active and a.purchase_date
                and a.purchase_date < today):
            # Active asset with no maintenance ever → overdue if more
            # than a year old. Simple proxy; staff can tune later.
            try:
                pd = _date.fromisoformat(a.purchase_date)
                if (_date.today() - pd).days > 365:
                    overdue_service += 1
            except ValueError:
                pass
        if a.warranty_expired and a.is_active:
            warranty_exp += 1
        if a.audit_overdue:
            audit_due += 1

    top_locations = sorted(location_counts.items(),
                              key=lambda kv: -kv[1])[:10]

    return Summary(
        total_assets=len(views),
        by_category=by_category,
        by_status=by_status,
        by_condition=by_condition,
        by_location=top_locations,
        total_purchase_cost=round(total_cost, 2),
        total_book_value=round(total_book, 2),
        count_overdue_service=overdue_service,
        count_warranty_expired=warranty_exp,
        count_due_for_audit=audit_due,
    )


__all__ = [
    "CATEGORIES", "DEFAULT_CATEGORY",
    "CONDITIONS", "DEFAULT_CONDITION",
    "STATUSES", "DEFAULT_STATUS", "DISPOSED_STATUSES",
    "DEPRECIATION_METHODS", "DEFAULT_DEPRECIATION_METHOD",
    "DISPOSAL_METHODS",
    "SERVICE_TYPES", "DEFAULT_SERVICE_TYPE",
    "MAINTENANCE_OUTCOMES", "DEFAULT_MAINTENANCE_OUTCOME",
    "CURRENCY_SYMBOL",
    "ValidationError",
    "Asset", "MaintenanceEntry", "AssetView", "Summary",
    "init_db",
    "create_asset", "get_asset", "get_by_tag", "list_assets",
    "update_asset", "set_status", "delete_asset",
    "view_asset", "list_views",
    "add_maintenance", "get_maintenance", "list_maintenance",
    "update_maintenance", "delete_maintenance",
    "book_value", "summary",
]
