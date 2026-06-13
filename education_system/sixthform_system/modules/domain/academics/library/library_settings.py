"""Library settings & loan policies.

Two stores, both created by ``library.init_db``:

* ``library_settings`` — a typed key/value bag for library-wide knobs
  (loan limit, fine rate/cap, hold-shelf expiry, issue-blocking
  thresholds). Defaults live in :data:`SETTING_DEFAULTS`; a key that has
  never been set falls back to its default rather than erroring.
* ``library_loan_policies`` — one row per item type giving the loan
  length, renewal cap and whether the type is borrowable at all. Seeded
  on first run from ``library._DEFAULT_POLICY``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from education_system.sixthform_system.modules.domain.academics.library import (
    library as _lib,
)

logger = logging.getLogger(__name__)

ValidationError = _lib.ValidationError

# key -> (default_value, python_type)
SETTING_DEFAULTS: dict[str, tuple[object, type]] = {
    "loan_limit_per_student":     (10, int),
    "fine_daily_rate":            (0.10, float),
    "fine_max_per_loan":          (10.00, float),
    "damaged_fee":                (5.00, float),
    "lost_fee":                   (15.00, float),
    "hold_shelf_days":            (7, int),
    "due_soon_days":              (2, int),
    "block_issue_fine_threshold": (5.00, float),
    "block_issue_on_overdue":     (True, bool),
}


def _parse(raw: str, typ: type) -> object:
    if typ is bool:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if typ is int:
        return int(float(raw))
    if typ is float:
        return float(raw)
    return raw


def _dump(value: object, typ: type) -> str:
    if typ is bool:
        return "1" if value else "0"
    return str(value)


def get_setting(key: str) -> object:
    if key not in SETTING_DEFAULTS:
        raise ValidationError(f"Unknown library setting: {key}")
    default, typ = SETTING_DEFAULTS[key]
    _lib.init_db()
    with _lib._connect() as conn:
        row = conn.execute(
            "SELECT value FROM library_settings WHERE key = ?",
            (key,)).fetchone()
    if row is None:
        return default
    try:
        return _parse(row["value"], typ)
    except (TypeError, ValueError):
        return default


def set_setting(key: str, value: object) -> None:
    if key not in SETTING_DEFAULTS:
        raise ValidationError(f"Unknown library setting: {key}")
    _default, typ = SETTING_DEFAULTS[key]
    try:
        coerced = _parse(str(value), typ) if not isinstance(value, typ) \
            else value
    except (TypeError, ValueError):
        raise ValidationError(
            f"{key} must be a {typ.__name__}") from None
    if typ in (int, float) and coerced < 0:  # type: ignore[operator]
        raise ValidationError(f"{key} cannot be negative")
    _lib.init_db()
    with _lib._connect() as conn:
        conn.execute(
            "INSERT INTO library_settings (key, value, updated_at) "
            "VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(key) DO UPDATE SET "
            "value = excluded.value, updated_at = datetime('now')",
            (key, _dump(coerced, typ)))
        conn.commit()
    logger.info("Library setting %s set to %r", key, coerced)


def all_settings() -> dict[str, object]:
    return {k: get_setting(k) for k in SETTING_DEFAULTS}


# ── Loan policies ─────────────────────────────────────────────────

@dataclass
class LoanPolicy:
    item_type: str
    loan_days: int
    max_renewals: int
    borrowable: bool


def _row_policy(r) -> LoanPolicy:
    return LoanPolicy(
        item_type=r["item_type"], loan_days=r["loan_days"],
        max_renewals=r["max_renewals"],
        borrowable=bool(r["borrowable"]))


def get_policy(item_type: str) -> LoanPolicy:
    """Policy for an item type, falling back to the Book defaults."""
    _lib.init_db()
    with _lib._connect() as conn:
        row = conn.execute(
            "SELECT * FROM library_loan_policies WHERE item_type = ?",
            (item_type,)).fetchone()
    if row is not None:
        return _row_policy(row)
    days, renewals, borrowable = _lib._DEFAULT_POLICY.get(
        item_type, (_lib.DEFAULT_LOAN_DAYS, _lib.MAX_RENEWALS, 1))
    return LoanPolicy(item_type, days, renewals, bool(borrowable))


def list_policies() -> list[LoanPolicy]:
    _lib.init_db()
    with _lib._connect() as conn:
        rows = conn.execute(
            "SELECT * FROM library_loan_policies "
            "ORDER BY item_type").fetchall()
    return [_row_policy(r) for r in rows]


def set_policy(item_type: str, *, loan_days: int | None = None,
               max_renewals: int | None = None,
               borrowable: bool | None = None) -> LoanPolicy:
    if item_type not in _lib.ITEM_TYPES:
        raise ValidationError(
            f"Item type must be one of: {', '.join(_lib.ITEM_TYPES)}")
    current = get_policy(item_type)
    days = current.loan_days if loan_days is None else int(loan_days)
    rens = current.max_renewals if max_renewals is None \
        else int(max_renewals)
    borrow = current.borrowable if borrowable is None else bool(borrowable)
    if days < 0:
        raise ValidationError("loan_days cannot be negative")
    if rens < 0:
        raise ValidationError("max_renewals cannot be negative")
    _lib.init_db()
    with _lib._connect() as conn:
        conn.execute(
            "INSERT INTO library_loan_policies "
            "(item_type, loan_days, max_renewals, borrowable) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(item_type) DO UPDATE SET "
            "loan_days = excluded.loan_days, "
            "max_renewals = excluded.max_renewals, "
            "borrowable = excluded.borrowable",
            (item_type, days, rens, 1 if borrow else 0))
        conn.commit()
    logger.info("Loan policy for %s set (days=%d, renewals=%d, "
                "borrowable=%s)", item_type, days, rens, borrow)
    return get_policy(item_type)
