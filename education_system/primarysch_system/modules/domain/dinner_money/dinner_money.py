"""Dinner money data layer.

Pupil meal accounts are modelled as a signed-amount ledger. Each row
in ``dinner_money_ledger`` is one credit or charge on a pupil's
account:

* ``amount_pence > 0`` — money added (top-up, refund, adjustment)
* ``amount_pence < 0`` — money taken (meal charge, debit adjustment)

A pupil's *balance* is simply the sum of their ledger rows. Positive
balance = in credit; negative = owing money.

Daily meal charges can be recorded individually or via
``charge_meal()`` which writes a single dated ``charge`` row tagged
with a ``meal_type`` for reporting. Free-school-meal pupils still get
rows logged (with zero charge) so the meal register is complete.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.primarysch_system.modules.domain.pupils import (
    pupils as pupils_data,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
    Pupil, ValidationError, YEAR_GROUPS,
    _connect as _pupils_connect, _DOB_RE,
)

logger = logging.getLogger(__name__)

KINDS: tuple[str, ...] = ("charge", "credit", "refund", "adjustment")
KIND_LABELS: dict[str, str] = {
    "charge":     "Charge (meal / debit)",
    "credit":     "Top-up / credit",
    "refund":     "Refund (out, positive amount on the account)",
    "adjustment": "Manual adjustment",
}
# Sign convention: positive amounts go to the account (credit), negative
# come off it (charge).
POSITIVE_KINDS = {"credit", "refund"}
NEGATIVE_KINDS = {"charge"}
# adjustment can be either sign — caller decides.

MEAL_TYPES: tuple[str, ...] = (
    "hot", "packed", "fsm", "uifsm", "absent", "other",
)
MEAL_TYPE_LABELS: dict[str, str] = {
    "hot":    "Hot school meal",
    "packed": "Packed lunch (logged, usually £0)",
    "fsm":    "Free School Meal (£0)",
    "uifsm":  "Universal Infant FSM (Reception–Y2, £0)",
    "absent": "Not at school / no meal",
    "other":  "Other / specify in notes",
}

_ACADEMIC_YEAR_RE = re.compile(r"^\d{4}(-\d{2}|-\d{4})?$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dinner_money_ledger (
    entry_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id        TEXT NOT NULL,
    entry_date      TEXT NOT NULL,
    kind            TEXT NOT NULL,
    meal_type       TEXT,
    amount_pence    INTEGER NOT NULL,
    description     TEXT,
    recorded_by     TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_dm_pupil ON dinner_money_ledger(pupil_id, entry_date DESC);
CREATE INDEX IF NOT EXISTS idx_dm_date  ON dinner_money_ledger(entry_date DESC);
CREATE INDEX IF NOT EXISTS idx_dm_kind  ON dinner_money_ledger(kind);
"""


@dataclass
class LedgerEntry:
    entry_id: int
    pupil_id: str
    entry_date: str
    kind: str
    meal_type: str | None
    amount_pence: int
    description: str | None
    recorded_by: str | None
    notes: str | None
    created_at: str | None = None

    @property
    def amount_display(self) -> str:
        sign = "-" if self.amount_pence < 0 else ""
        abs_p = abs(self.amount_pence)
        pounds = abs_p // 100
        pence = abs_p % 100
        return f"{sign}£{pounds}.{pence:02d}"


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    pupils_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise dinner_money_ledger table")
        raise
    logger.info("Primary dinner_money_ledger table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> LedgerEntry:
    return LedgerEntry(
        entry_id=r["entry_id"],
        pupil_id=r["pupil_id"],
        entry_date=r["entry_date"],
        kind=r["kind"],
        meal_type=r["meal_type"],
        amount_pence=r["amount_pence"],
        description=r["description"],
        recorded_by=r["recorded_by"],
        notes=r["notes"],
        created_at=r["created_at"],
    )


def _pounds_to_pence(raw: Any) -> int:
    """Parse a £-string or float into pence. ``None``/blank -> 0."""
    if raw in (None, ""):
        return 0
    if isinstance(raw, (int, float)):
        return int(round(float(raw) * 100))
    s = str(raw).strip().lstrip("£")
    if not s:
        return 0
    try:
        return int(round(float(s) * 100))
    except ValueError as e:
        raise ValidationError(f"Amount {raw!r} is not a number") from e


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid = (data.get("pupil_id") or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    out["pupil_id"] = pid
    dt = (data.get("entry_date") or "").strip()
    if dt and not _DOB_RE.match(dt):
        raise ValidationError("Entry date must be YYYY-MM-DD")
    out["entry_date"] = dt or None
    kind = (data.get("kind") or "").strip().lower()
    if not kind:
        raise ValidationError("Kind is required")
    if kind not in KINDS:
        raise ValidationError(f"Kind must be one of {', '.join(KINDS)}")
    out["kind"] = kind
    mt = (data.get("meal_type") or "").strip().lower()
    if mt:
        if mt not in MEAL_TYPES:
            raise ValidationError(
                f"Meal type must be one of {', '.join(MEAL_TYPES)}")
    out["meal_type"] = mt or None
    # Amount: accept either pence (int) or pounds (string/float).
    if "amount_pence" in data and data["amount_pence"] not in (None, ""):
        try:
            pence = int(data["amount_pence"])
        except (TypeError, ValueError) as e:
            raise ValidationError("amount_pence must be an integer") from e
    else:
        pence = _pounds_to_pence(data.get("amount_pounds"))
    if pence == 0 and kind != "charge":
        # An adjustment of 0 is meaningless; a credit of 0 is suspicious.
        # A 'charge' of 0 is allowed (e.g. logged FSM lunch).
        raise ValidationError("Amount cannot be zero for this kind")
    if abs(pence) > 100_000:
        raise ValidationError(
            "Amount must be between -£1000 and £1000")
    # Apply the sign rule when the caller passed an unsigned amount.
    if kind in NEGATIVE_KINDS and pence > 0:
        pence = -pence
    if kind in POSITIVE_KINDS and pence < 0:
        pence = abs(pence)
    out["amount_pence"] = pence
    out["description"] = (data.get("description") or "").strip() or None
    out["recorded_by"] = (data.get("recorded_by") or "").strip() or None
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def record(data: dict[str, Any]) -> LedgerEntry:
    init_db()
    payload = _validate(data)
    if pupils_data.get_pupil(payload["pupil_id"]) is None:
        raise ValidationError(f"No pupil with id {payload['pupil_id']}")
    try:
        with _connect() as conn:
            dt = payload["entry_date"] or conn.execute(
                "SELECT date('now')").fetchone()[0]
            cur = conn.execute(
                """INSERT INTO dinner_money_ledger
                       (pupil_id, entry_date, kind, meal_type, amount_pence,
                        description, recorded_by, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["pupil_id"], dt, payload["kind"],
                 payload["meal_type"], payload["amount_pence"],
                 payload["description"], payload["recorded_by"],
                 payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to record ledger entry")
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info("DM #%d: pupil %s %s %s (%s)",
                rec.entry_id, rec.pupil_id, rec.kind,
                rec.amount_display, rec.entry_date)
    return rec


def charge_meal(pupil_id: str, *, entry_date: str | None = None,
                meal_type: str = "hot",
                amount_pounds: Any = None,
                amount_pence: int | None = None,
                description: str | None = None,
                recorded_by: str | None = None,
                notes: str | None = None) -> LedgerEntry:
    """Convenience: record a single meal charge."""
    payload: dict[str, Any] = {
        "pupil_id": pupil_id,
        "entry_date": entry_date,
        "kind": "charge",
        "meal_type": meal_type,
        "description": description or _default_meal_description(meal_type),
        "recorded_by": recorded_by,
        "notes": notes,
    }
    if amount_pence is not None:
        payload["amount_pence"] = amount_pence
    else:
        payload["amount_pounds"] = amount_pounds
    return record(payload)


def _default_meal_description(meal_type: str) -> str:
    return {
        "hot":    "Hot school meal",
        "packed": "Packed lunch (logged)",
        "fsm":    "Free school meal",
        "uifsm":  "UIFSM lunch",
        "absent": "Absent — no meal",
        "other":  "Meal entry",
    }.get(meal_type, "Meal entry")


def credit(pupil_id: str, *, amount_pounds: Any = None,
           amount_pence: int | None = None,
           entry_date: str | None = None,
           description: str | None = None,
           recorded_by: str | None = None,
           notes: str | None = None) -> LedgerEntry:
    """Convenience: add a top-up to the pupil's account."""
    payload: dict[str, Any] = {
        "pupil_id": pupil_id,
        "entry_date": entry_date,
        "kind": "credit",
        "description": description or "Top-up",
        "recorded_by": recorded_by,
        "notes": notes,
    }
    if amount_pence is not None:
        payload["amount_pence"] = amount_pence
    else:
        payload["amount_pounds"] = amount_pounds
    return record(payload)


def get(entry_id: int) -> LedgerEntry | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM dinner_money_ledger WHERE entry_id = ?",
                (entry_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get DM(%s) failed", entry_id)
        raise
    return _row(r) if r else None


def update(entry_id: int, data: dict[str, Any]) -> LedgerEntry:
    init_db()
    existing = get(entry_id)
    if existing is None:
        raise ValidationError(f"No entry #{entry_id}")
    merged = {
        "pupil_id":     data.get("pupil_id", existing.pupil_id),
        "entry_date":   data.get("entry_date", existing.entry_date),
        "kind":         data.get("kind", existing.kind),
        "meal_type":    data.get("meal_type", existing.meal_type),
        "amount_pence": data.get("amount_pence", existing.amount_pence),
        "description":  data.get("description", existing.description),
        "recorded_by":  data.get("recorded_by", existing.recorded_by),
        "notes":        data.get("notes", existing.notes),
    }
    if "amount_pounds" in data and "amount_pence" not in data:
        merged["amount_pounds"] = data["amount_pounds"]
        merged.pop("amount_pence", None)
    payload = _validate(merged)
    if pupils_data.get_pupil(payload["pupil_id"]) is None:
        raise ValidationError(f"No pupil with id {payload['pupil_id']}")
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE dinner_money_ledger SET
                       pupil_id = ?, entry_date = ?, kind = ?,
                       meal_type = ?, amount_pence = ?, description = ?,
                       recorded_by = ?, notes = ?
                   WHERE entry_id = ?""",
                (payload["pupil_id"], payload["entry_date"] or existing.entry_date,
                 payload["kind"], payload["meal_type"],
                 payload["amount_pence"], payload["description"],
                 payload["recorded_by"], payload["notes"], entry_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update DM #%d", entry_id)
        raise
    rec = get(entry_id)
    assert rec is not None
    logger.info("Updated DM #%d", entry_id)
    return rec


def delete(entry_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM dinner_money_ledger WHERE entry_id = ?",
                (entry_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete DM #%d", entry_id)
        raise
    if deleted:
        logger.info("Deleted DM #%d", entry_id)
    return deleted


def list_entries(
    *, pupil_id: str | None = None,
    kind: str | None = None,
    meal_type: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int | None = None,
) -> list[tuple[LedgerEntry, Pupil | None]]:
    init_db()
    if kind is not None and kind not in KINDS:
        raise ValidationError(f"Kind filter must be one of {', '.join(KINDS)}")
    if meal_type is not None and meal_type not in MEAL_TYPES:
        raise ValidationError(
            f"Meal-type filter must be one of {', '.join(MEAL_TYPES)}")
    for k, v in (("from_date", from_date), ("to_date", to_date)):
        if v and not _DOB_RE.match(v):
            raise ValidationError(f"{k} must be YYYY-MM-DD")
    where: list[str] = []
    params: list[Any] = []
    if pupil_id:
        where.append("pupil_id = ?")
        params.append(pupil_id.strip())
    if kind:
        where.append("kind = ?")
        params.append(kind)
    if meal_type:
        where.append("meal_type = ?")
        params.append(meal_type)
    if from_date:
        where.append("entry_date >= ?")
        params.append(from_date)
    if to_date:
        where.append("entry_date <= ?")
        params.append(to_date)
    sql = "SELECT * FROM dinner_money_ledger"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY entry_date DESC, entry_id DESC"
    if limit is not None and limit > 0:
        sql += f" LIMIT {int(limit)}"
    try:
        with _connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_entries failed")
        raise
    out: list[tuple[LedgerEntry, Pupil | None]] = []
    for r in rows:
        e = _row(r)
        out.append((e, pupils_data.get_pupil(e.pupil_id)))
    return out


def pupil_balance(pupil_id: str) -> int:
    """Return the pupil's running balance, in pence."""
    init_db()
    if pupils_data.get_pupil(pupil_id) is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT COALESCE(SUM(amount_pence), 0) AS bal "
                "FROM dinner_money_ledger WHERE pupil_id = ?",
                (pupil_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("pupil_balance(%s) failed", pupil_id)
        raise
    return int(r["bal"])


def pupil_statement(pupil_id: str) -> dict[str, Any]:
    init_db()
    if pupils_data.get_pupil(pupil_id) is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM dinner_money_ledger WHERE pupil_id = ? "
                "ORDER BY entry_date, entry_id",
                (pupil_id,),
            ).fetchall()
    except sqlite3.Error:
        logger.exception("pupil_statement(%s) failed", pupil_id)
        raise
    entries = [_row(r) for r in rows]
    total_credits = sum(e.amount_pence for e in entries if e.amount_pence > 0)
    total_charges = sum(-e.amount_pence for e in entries if e.amount_pence < 0)
    balance = sum(e.amount_pence for e in entries)
    return {
        "pupil_id": pupil_id,
        "entries": entries,
        "total_credits_pence": total_credits,
        "total_charges_pence": total_charges,
        "balance_pence": balance,
    }


def balances(
    *, year_group: str | None = None,
    owing_only: bool = False,
    limit: int | None = None,
) -> list[tuple[Pupil, int]]:
    """Return [(Pupil, balance_pence), ...] sorted by balance ascending
    (most-owed first when owing_only is true).
    """
    init_db()
    if year_group is not None and year_group not in YEAR_GROUPS:
        raise ValidationError(
            f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT pupil_id, COALESCE(SUM(amount_pence), 0) AS bal "
                "FROM dinner_money_ledger GROUP BY pupil_id"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("balances() failed")
        raise
    out: list[tuple[Pupil, int]] = []
    for r in rows:
        p = pupils_data.get_pupil(r["pupil_id"])
        if p is None:
            continue
        if year_group and p.year_group != year_group:
            continue
        bal = int(r["bal"])
        if owing_only and bal >= 0:
            continue
        out.append((p, bal))
    out.sort(key=lambda t: t[1])  # most-owed first
    if limit is not None and limit > 0:
        out = out[:limit]
    return out


def summary(
    *, from_date: str | None = None,
    to_date: str | None = None,
) -> dict[str, Any]:
    init_db()
    for k, v in (("from_date", from_date), ("to_date", to_date)):
        if v and not _DOB_RE.match(v):
            raise ValidationError(f"{k} must be YYYY-MM-DD")
    where: list[str] = []
    params: list[Any] = []
    if from_date:
        where.append("entry_date >= ?")
        params.append(from_date)
    if to_date:
        where.append("entry_date <= ?")
        params.append(to_date)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    try:
        with _connect() as conn:
            total_credits = conn.execute(
                f"SELECT COALESCE(SUM(amount_pence), 0) "
                f"FROM dinner_money_ledger{clause} "
                f"{'AND' if clause else 'WHERE'} amount_pence > 0",
                tuple(params),
            ).fetchone()[0]
            total_charges = conn.execute(
                f"SELECT COALESCE(SUM(-amount_pence), 0) "
                f"FROM dinner_money_ledger{clause} "
                f"{'AND' if clause else 'WHERE'} amount_pence < 0",
                tuple(params),
            ).fetchone()[0]
            entries = conn.execute(
                f"SELECT COUNT(*) FROM dinner_money_ledger{clause}",
                tuple(params),
            ).fetchone()[0]
            by_meal = {
                r["meal_type"]: r["n"]
                for r in conn.execute(
                    f"SELECT meal_type, COUNT(*) AS n "
                    f"FROM dinner_money_ledger{clause} "
                    f"{'AND' if clause else 'WHERE'} meal_type IS NOT NULL "
                    f"GROUP BY meal_type",
                    tuple(params),
                ).fetchall()
            }
            net_balance = conn.execute(
                f"SELECT COALESCE(SUM(amount_pence), 0) "
                f"FROM dinner_money_ledger{clause}",
                tuple(params),
            ).fetchone()[0]
    except sqlite3.Error:
        logger.exception("summary failed")
        raise
    pupils_with_balance = balances()
    owing = sum(1 for _p, b in pupils_with_balance if b < 0)
    in_credit = sum(1 for _p, b in pupils_with_balance if b > 0)
    total_owed = sum(-b for _p, b in pupils_with_balance if b < 0)
    return {
        "entries": entries,
        "total_credits_pence": int(total_credits),
        "total_charges_pence": int(total_charges),
        "net_pence": int(net_balance),
        "by_meal_type": {m: by_meal.get(m, 0) for m in MEAL_TYPES},
        "pupils_with_balance": len(pupils_with_balance),
        "pupils_owing": owing,
        "pupils_in_credit": in_credit,
        "total_owed_pence": int(total_owed),
    }


def format_pence(pence: int) -> str:
    sign = "-" if pence < 0 else ""
    abs_p = abs(int(pence))
    return f"{sign}£{abs_p // 100}.{abs_p % 100:02d}"
