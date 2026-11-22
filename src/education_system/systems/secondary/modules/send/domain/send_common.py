"""Shared helpers for the SEND modules (:mod:`send`, :mod:`send_access`):
who may change things, the audit trail, and field cleaning."""

from __future__ import annotations

import calendar
import datetime as _dt
import json
from typing import Any

from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import SEND_EDITORS, STAFF_ROLES, Principal
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

_SCHEMA = """
CREATE TABLE IF NOT EXISTS send_audit (
    audit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id   INTEGER,
    item       TEXT NOT NULL,
    item_id    INTEGER,
    action     TEXT NOT NULL,
    detail     TEXT,
    actor      TEXT NOT NULL,
    at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_send_audit_pupil ON send_audit (pupil_id);
"""
database.register_schema("send_audit", _SCHEMA)


PUPIL_COLS = ("p.legal_last_name, p.legal_first_name, p.preferred_name, p.admission_no, "
               "p.year_group AS pupil_year")


def _name(r) -> str:
    return f"{r['legal_last_name']}, {r['preferred_name'] or r['legal_first_name']}"


def _make(cls, r):
    extra = {"pupil_name", "admission_no", "pupil_year"}
    vals = {k: r[k] for k in cls.__dataclass_fields__ if k not in extra}
    for k in ("exam_only", "in_ehcp"):
        if k in vals:
            vals[k] = bool(vals[k])
    if "pupil_name" in cls.__dataclass_fields__:
        vals.update(pupil_name=_name(r), admission_no=r["admission_no"],
                    pupil_year=r["pupil_year"])
    return cls(**vals)


# ── Who may do what ──────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in SEND_EDITORS


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"send.{action}", target=target, outcome="denied", principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, target, "Only staff can see the SEND register.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        _deny(actor, action, target, "Only the SENCO can change the SEND register.")


def _audit(conn, actor: Principal, item: str, action: str, *, pupil_id: int | None,
           item_id: int | None = None, **detail: Any) -> None:
    conn.execute("INSERT INTO send_audit (pupil_id, item, item_id, action, detail, actor) "
                 "VALUES (?, ?, ?, ?, ?, ?)",
                 (pupil_id, item, item_id, action,
                  json.dumps(detail, default=str) if detail else None,
                  actor.username or "unknown"))


def history(pupil_id: int | None = None, *, limit: int = 300) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM send_audit", []
    if pupil_id is not None:
        sql += " WHERE pupil_id = ?"
        params.append(int(pupil_id))
    with database.connect() as conn:
        return [{"at": r["at"], "pupil_id": r["pupil_id"], "item": r["item"],
                 "item_id": r["item_id"], "action": r["action"], "actor": r["actor"],
                 "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, int(limit)))]


# ── Cleaning ─────────────────────────────────────────────────────────

def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _date(value: Any, label: str, problems: list[str]) -> str | None:
    if _blank(value):
        return None
    try:
        return _dt.date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None


def _choice(value: Any, options: tuple[str, ...], label: str, problems: list[str],
            default: str | None) -> str | None:
    v = str(value or "").strip()
    if not v:
        return default
    hit = next((o for o in options if o.lower() == v.lower()), None)
    if hit is None:
        problems.append(f"{label} must be one of {', '.join(options)}")
        return default
    return hit


def _text(value: Any, limit: int) -> str | None:
    return (str(value or "").strip()[:limit]) or None


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y")
    return bool(value)


def _number(value: Any, label: str, problems: list[str], *, lo: float = 0,
            hi: float = 1_000_000, whole: bool = False) -> float | None:
    if _blank(value):
        return None
    try:
        n = float(str(value).strip().lstrip("£").replace(",", ""))
    except ValueError:
        problems.append(f"{label} must be a number")
        return None
    if whole and n != int(n):
        problems.append(f"{label} must be a whole number")
    if not lo <= n <= hi:
        problems.append(f"{label} must be between {lo:g} and {hi:g}")
    return int(n) if whole else n


def _pupil(ref: Any) -> P.Pupil | None:
    if _blank(ref):
        return None
    if isinstance(ref, int) or str(ref).strip().isdigit():
        return P.get_pupil(int(ref))
    return P.find_by_reference(str(ref).strip())


def _need_pupil(ref: Any) -> P.Pupil:
    p = _pupil(ref)
    if p is None:
        raise ValidationError(["Pupil ID is required" if _blank(ref) else f"No pupil {ref}"])
    return p


def add_months(day: str | _dt.date, months: int) -> _dt.date:
    d = _dt.date.fromisoformat(str(day)) if not isinstance(day, _dt.date) else day
    m = d.month - 1 + months
    y, m = d.year + m // 12, m % 12 + 1
    return _dt.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _plus(day: str, days: int) -> str:
    return (_dt.date.fromisoformat(day) + _dt.timedelta(days=days)).isoformat()


