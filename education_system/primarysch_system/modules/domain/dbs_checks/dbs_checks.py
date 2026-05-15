"""DBS Checks data layer for Primary School System.

Single-table register of DBS checks. One row per check per staff
member (FK cascade). Distinct from the personal DBS fields on the
HR record — this is the *register* that the safeguarding /
compliance lead maintains for SCR (single central record) audits.

Tracks level (Basic / Standard / Enhanced / Enhanced with Barred
List), DBS Update Service subscription, sign-off and full
expiry / renewal workflow.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system.primarysch_system.core import paths as _paths

logger = logging.getLogger(__name__)

LEVELS: tuple[str, ...] = (
    "Basic",
    "Standard",
    "Enhanced",
    "Enhanced with Barred List",
    "Enhanced — Children's Barred List",
    "Enhanced — Adults' Barred List",
)
DEFAULT_LEVEL = "Enhanced with Barred List"

CERTIFICATE_TYPES: tuple[str, ...] = (
    "Original Seen",
    "Photocopy on File",
    "Update Service Check",
    "DBS Portal",
    "Other",
)
DEFAULT_CERTIFICATE_TYPE = "Original Seen"

STATUSES: tuple[str, ...] = (
    "Applied",
    "Pending",
    "Awaiting Certificate",
    "Cleared",
    "Cleared (with information)",
    "Refused",
    "Lapsed",
    "Renewing",
    "Update Service Active",
)
DEFAULT_STATUS = "Applied"


class ValidationError(Exception):
    pass


@dataclass
class DBSCheck:
    check_id: int
    staff_id: str
    dbs_number: str | None
    level: str
    applied_on: str | None
    issued_on: str | None
    expires_on: str | None
    certificate_type: str
    certificate_seen_on: str | None
    update_service_subscribed: bool
    update_service_id: str | None
    last_update_check_on: str | None
    next_update_check_due: str | None
    portability_check: bool
    risk_assessment_required: bool
    risk_assessment_completed_on: str | None
    risk_assessment_outcome: str | None
    signed_off_by: str | None
    signed_off_on: str | None
    notes: str | None
    status: str
    created_on: str
    updated_on: str

    @property
    def is_active(self) -> bool:
        return self.status in ("Cleared",
                                       "Cleared (with information)",
                                       "Update Service Active")

    @property
    def is_expired(self) -> bool:
        if not self.expires_on or not self.is_active:
            return False
        return self.expires_on < _dt.date.today().isoformat()

    @property
    def expiring_soon(self) -> bool:
        """Within 90 days of expiry."""
        if (not self.expires_on or not self.is_active
                or self.is_expired):
            return False
        try:
            exp = _dt.date.fromisoformat(self.expires_on)
        except ValueError:
            return False
        days = (exp - _dt.date.today()).days
        return 0 <= days <= 90

    @property
    def update_check_overdue(self) -> bool:
        if (not self.update_service_subscribed
                or not self.next_update_check_due):
            return False
        return self.next_update_check_due < _dt.date.today().isoformat()


@dataclass
class DBSSummary:
    total: int = 0
    active: int = 0
    cleared: int = 0
    pending: int = 0
    renewing: int = 0
    expired: int = 0
    expiring_soon: int = 0
    update_check_overdue: int = 0
    update_service_subscribed: int = 0
    risk_assessment_pending: int = 0
    unsigned: int = 0
    distinct_staff: int = 0
    by_level: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    by_certificate_type: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.DBS_CHECKS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dbs_checks (
                check_id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id TEXT NOT NULL,
                dbs_number TEXT,
                level TEXT NOT NULL,
                applied_on TEXT,
                issued_on TEXT,
                expires_on TEXT,
                certificate_type TEXT NOT NULL,
                certificate_seen_on TEXT,
                update_service_subscribed INTEGER NOT NULL DEFAULT 0,
                update_service_id TEXT,
                last_update_check_on TEXT,
                next_update_check_due TEXT,
                portability_check INTEGER NOT NULL DEFAULT 0,
                risk_assessment_required INTEGER NOT NULL DEFAULT 0,
                risk_assessment_completed_on TEXT,
                risk_assessment_outcome TEXT,
                signed_off_by TEXT,
                signed_off_on TEXT,
                notes TEXT,
                status TEXT NOT NULL,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL,
                FOREIGN KEY(staff_id) REFERENCES staff(staff_id)
                  ON DELETE CASCADE
            )
        """)


def _check_date(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{label} must be YYYY-MM-DD")


def _staff_exists(staff_id: str) -> bool:
    with _connect() as conn:
        try:
            row = conn.execute(
                "SELECT 1 FROM staff WHERE staff_id=?",
                (staff_id,)).fetchone()
        except sqlite3.OperationalError:
            return False
    return row is not None


def _validate_payload(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["staff_id"] = (out.get("staff_id") or "").strip()
    if not out["staff_id"]:
        raise ValidationError("Staff is required")
    if not _staff_exists(out["staff_id"]):
        raise ValidationError(
            f"No staff with id {out['staff_id']}")

    level = (out.get("level") or DEFAULT_LEVEL).strip()
    if level not in LEVELS:
        raise ValidationError(
            f"Level must be one of: {', '.join(LEVELS)}")
    out["level"] = level

    ct = (out.get("certificate_type")
            or DEFAULT_CERTIFICATE_TYPE).strip()
    if ct not in CERTIFICATE_TYPES:
        raise ValidationError(
            f"Certificate type must be one of: "
            f"{', '.join(CERTIFICATE_TYPES)}")
    out["certificate_type"] = ct

    status = (out.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    for label, key in (
            ("Applied on",          "applied_on"),
            ("Issued on",           "issued_on"),
            ("Expires on",          "expires_on"),
            ("Certificate seen on", "certificate_seen_on"),
            ("Last update check",   "last_update_check_on"),
            ("Next update check",   "next_update_check_due"),
            ("Risk assessment on",  "risk_assessment_completed_on"),
            ("Signed off on",       "signed_off_on"),
    ):
        _check_date(label, out.get(key))

    if (out.get("issued_on") and out.get("expires_on")
            and out["expires_on"] < out["issued_on"]):
        raise ValidationError(
            "Expires on must be on or after issued on")

    for k in ("dbs_number", "update_service_id",
               "risk_assessment_outcome",
               "signed_off_by", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("applied_on", "issued_on", "expires_on",
               "certificate_seen_on", "last_update_check_on",
               "next_update_check_due",
               "risk_assessment_completed_on", "signed_off_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v
    for k in ("update_service_subscribed", "portability_check",
               "risk_assessment_required"):
        out[k] = bool(out.get(k))
    return out


def _row(r: sqlite3.Row) -> DBSCheck:
    return DBSCheck(
        check_id=r["check_id"],
        staff_id=r["staff_id"],
        dbs_number=r["dbs_number"],
        level=r["level"],
        applied_on=r["applied_on"],
        issued_on=r["issued_on"],
        expires_on=r["expires_on"],
        certificate_type=r["certificate_type"],
        certificate_seen_on=r["certificate_seen_on"],
        update_service_subscribed=bool(
            r["update_service_subscribed"]),
        update_service_id=r["update_service_id"],
        last_update_check_on=r["last_update_check_on"],
        next_update_check_due=r["next_update_check_due"],
        portability_check=bool(r["portability_check"]),
        risk_assessment_required=bool(
            r["risk_assessment_required"]),
        risk_assessment_completed_on=r[
            "risk_assessment_completed_on"],
        risk_assessment_outcome=r["risk_assessment_outcome"],
        signed_off_by=r["signed_off_by"],
        signed_off_on=r["signed_off_on"],
        notes=r["notes"],
        status=r["status"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_check(payload: dict[str, Any]) -> DBSCheck:
    init_db()
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO dbs_checks (
              staff_id, dbs_number, level,
              applied_on, issued_on, expires_on,
              certificate_type, certificate_seen_on,
              update_service_subscribed, update_service_id,
              last_update_check_on, next_update_check_due,
              portability_check, risk_assessment_required,
              risk_assessment_completed_on,
              risk_assessment_outcome,
              signed_off_by, signed_off_on, notes, status,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["staff_id"], p["dbs_number"], p["level"],
            p["applied_on"], p["issued_on"], p["expires_on"],
            p["certificate_type"], p["certificate_seen_on"],
            1 if p["update_service_subscribed"] else 0,
            p["update_service_id"],
            p["last_update_check_on"],
            p["next_update_check_due"],
            1 if p["portability_check"] else 0,
            1 if p["risk_assessment_required"] else 0,
            p["risk_assessment_completed_on"],
            p["risk_assessment_outcome"],
            p["signed_off_by"], p["signed_off_on"],
            p["notes"], p["status"], now, now,
        ))
        new_id = cur.lastrowid
    return get_check(new_id)


def update_check(check_id: int,
                     payload: dict[str, Any]) -> DBSCheck:
    init_db()
    if get_check(check_id) is None:
        raise ValidationError(f"No check with id {check_id}")
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE dbs_checks SET
              staff_id=?, dbs_number=?, level=?,
              applied_on=?, issued_on=?, expires_on=?,
              certificate_type=?, certificate_seen_on=?,
              update_service_subscribed=?, update_service_id=?,
              last_update_check_on=?, next_update_check_due=?,
              portability_check=?, risk_assessment_required=?,
              risk_assessment_completed_on=?,
              risk_assessment_outcome=?,
              signed_off_by=?, signed_off_on=?, notes=?, status=?,
              updated_on=?
            WHERE check_id=?
        """, (
            p["staff_id"], p["dbs_number"], p["level"],
            p["applied_on"], p["issued_on"], p["expires_on"],
            p["certificate_type"], p["certificate_seen_on"],
            1 if p["update_service_subscribed"] else 0,
            p["update_service_id"],
            p["last_update_check_on"],
            p["next_update_check_due"],
            1 if p["portability_check"] else 0,
            1 if p["risk_assessment_required"] else 0,
            p["risk_assessment_completed_on"],
            p["risk_assessment_outcome"],
            p["signed_off_by"], p["signed_off_on"],
            p["notes"], p["status"], now, check_id,
        ))
    return get_check(check_id)


def delete_check(check_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM dbs_checks WHERE check_id=?",
            (check_id,))
        return cur.rowcount > 0


def get_check(check_id: int) -> DBSCheck | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM dbs_checks WHERE check_id=?",
            (check_id,)).fetchone()
        return _row(r) if r else None


def latest_for_staff(staff_id: str) -> DBSCheck | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM dbs_checks WHERE staff_id=? "
            "ORDER BY COALESCE(issued_on, applied_on, '') "
            "DESC, check_id DESC LIMIT 1",
            (staff_id,)).fetchone()
        return _row(r) if r else None


def list_checks(*,
                     staff_id: str | None = None,
                     level: str | None = None,
                     status: str | None = None,
                     certificate_type: str | None = None,
                     active_only: bool = False,
                     expired: bool = False,
                     expiring_soon: bool = False,
                     update_check_overdue: bool = False,
                     update_service_only: bool = False,
                     unsigned: bool = False,
                     risk_assessment_pending: bool = False,
                     ) -> list[DBSCheck]:
    init_db()
    sql = "SELECT * FROM dbs_checks WHERE 1=1"
    params: list[Any] = []
    if staff_id:
        sql += " AND staff_id=?"
        params.append(staff_id)
    if level:
        sql += " AND level=?"
        params.append(level)
    if status:
        sql += " AND status=?"
        params.append(status)
    if certificate_type:
        sql += " AND certificate_type=?"
        params.append(certificate_type)
    if active_only:
        sql += (" AND status IN "
                  "('Cleared','Cleared (with information)',"
                  "'Update Service Active')")
    today = _dt.date.today().isoformat()
    if expired:
        sql += (" AND expires_on IS NOT NULL"
                  " AND expires_on < ?"
                  " AND status IN "
                  "('Cleared','Cleared (with information)',"
                  "'Update Service Active')")
        params.append(today)
    if expiring_soon:
        soon = (_dt.date.today()
                  + _dt.timedelta(days=90)).isoformat()
        sql += (" AND expires_on IS NOT NULL"
                  " AND expires_on >= ?"
                  " AND expires_on <= ?"
                  " AND status IN "
                  "('Cleared','Cleared (with information)',"
                  "'Update Service Active')")
        params.extend([today, soon])
    if update_check_overdue:
        sql += (" AND update_service_subscribed=1"
                  " AND next_update_check_due IS NOT NULL"
                  " AND next_update_check_due < ?")
        params.append(today)
    if update_service_only:
        sql += " AND update_service_subscribed=1"
    if unsigned:
        sql += " AND (signed_off_by IS NULL OR signed_off_by='')"
    if risk_assessment_pending:
        sql += (" AND risk_assessment_required=1"
                  " AND risk_assessment_completed_on IS NULL")
    sql += (" ORDER BY COALESCE(expires_on, '') ASC,"
              " check_id DESC")
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row(r) for r in rows]


def checks_for_staff(staff_id: str) -> list[DBSCheck]:
    return list_checks(staff_id=staff_id)


# ── Workflow ──────────────────────────────────────────────

def _to_dict(c: DBSCheck) -> dict[str, Any]:
    return {
        "staff_id": c.staff_id,
        "dbs_number": c.dbs_number,
        "level": c.level,
        "applied_on": c.applied_on,
        "issued_on": c.issued_on,
        "expires_on": c.expires_on,
        "certificate_type": c.certificate_type,
        "certificate_seen_on": c.certificate_seen_on,
        "update_service_subscribed": c.update_service_subscribed,
        "update_service_id": c.update_service_id,
        "last_update_check_on": c.last_update_check_on,
        "next_update_check_due": c.next_update_check_due,
        "portability_check": c.portability_check,
        "risk_assessment_required": c.risk_assessment_required,
        "risk_assessment_completed_on":
            c.risk_assessment_completed_on,
        "risk_assessment_outcome": c.risk_assessment_outcome,
        "signed_off_by": c.signed_off_by,
        "signed_off_on": c.signed_off_on,
        "notes": c.notes,
        "status": c.status,
    }


def issue_certificate(check_id: int, *,
                          dbs_number: str,
                          issued_on: str | None = None,
                          expires_on: str | None = None
                          ) -> DBSCheck:
    if not dbs_number:
        raise ValidationError("DBS number is required")
    c = get_check(check_id)
    if c is None:
        raise ValidationError(f"No check with id {check_id}")
    data = _to_dict(c)
    data["dbs_number"] = dbs_number
    data["issued_on"] = (issued_on
                              or _dt.date.today().isoformat())
    if expires_on:
        data["expires_on"] = expires_on
    data["status"] = "Cleared"
    return update_check(check_id, data)


def see_certificate(check_id: int, *,
                         seen_on: str | None = None
                         ) -> DBSCheck:
    c = get_check(check_id)
    if c is None:
        raise ValidationError(f"No check with id {check_id}")
    data = _to_dict(c)
    data["certificate_seen_on"] = (seen_on
                                         or _dt.date.today().isoformat())
    return update_check(check_id, data)


def subscribe_update_service(check_id: int, *,
                                  update_id: str | None = None,
                                  next_check_due: str | None = None
                                  ) -> DBSCheck:
    c = get_check(check_id)
    if c is None:
        raise ValidationError(f"No check with id {check_id}")
    data = _to_dict(c)
    data["update_service_subscribed"] = True
    if update_id:
        data["update_service_id"] = update_id
    if next_check_due:
        data["next_update_check_due"] = next_check_due
    if c.status == "Cleared":
        data["status"] = "Update Service Active"
    return update_check(check_id, data)


def record_update_check(check_id: int, *,
                             checked_on: str | None = None,
                             next_check_due: str | None = None
                             ) -> DBSCheck:
    c = get_check(check_id)
    if c is None:
        raise ValidationError(f"No check with id {check_id}")
    data = _to_dict(c)
    data["last_update_check_on"] = (checked_on
                                          or _dt.date.today().isoformat())
    if next_check_due:
        data["next_update_check_due"] = next_check_due
    else:
        # default to +12 months from last check
        try:
            base = _dt.date.fromisoformat(
                data["last_update_check_on"])
            data["next_update_check_due"] = (
                (base + _dt.timedelta(days=365)).isoformat())
        except ValueError:
            pass
    return update_check(check_id, data)


def complete_risk_assessment(check_id: int, *,
                                  outcome: str,
                                  completed_on: str | None = None
                                  ) -> DBSCheck:
    if not outcome:
        raise ValidationError(
            "Risk assessment outcome is required")
    c = get_check(check_id)
    if c is None:
        raise ValidationError(f"No check with id {check_id}")
    data = _to_dict(c)
    data["risk_assessment_outcome"] = outcome
    data["risk_assessment_completed_on"] = (
        completed_on or _dt.date.today().isoformat())
    return update_check(check_id, data)


def sign_off(check_id: int, *,
                 signed_off_by: str,
                 signed_off_on: str | None = None
                 ) -> DBSCheck:
    if not signed_off_by:
        raise ValidationError("Signed-off by is required")
    c = get_check(check_id)
    if c is None:
        raise ValidationError(f"No check with id {check_id}")
    data = _to_dict(c)
    data["signed_off_by"] = signed_off_by
    data["signed_off_on"] = (signed_off_on
                                  or _dt.date.today().isoformat())
    return update_check(check_id, data)


def mark_lapsed(check_id: int) -> DBSCheck:
    c = get_check(check_id)
    if c is None:
        raise ValidationError(f"No check with id {check_id}")
    return update_check(check_id,
                              {**_to_dict(c), "status": "Lapsed"})


def start_renewal(check_id: int) -> DBSCheck:
    c = get_check(check_id)
    if c is None:
        raise ValidationError(f"No check with id {check_id}")
    return update_check(check_id,
                              {**_to_dict(c), "status": "Renewing"})


def set_status(check_id: int, new_status: str) -> DBSCheck:
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    c = get_check(check_id)
    if c is None:
        raise ValidationError(f"No check with id {check_id}")
    return update_check(check_id,
                              {**_to_dict(c), "status": new_status})


# ── Summary ──────────────────────────────────────────────

def summary() -> DBSSummary:
    rows = list_checks()
    out = DBSSummary(total=len(rows))
    if not rows:
        return out
    today = _dt.date.today().isoformat()
    soon = (_dt.date.today()
              + _dt.timedelta(days=90)).isoformat()
    staff: set[str] = set()
    for c in rows:
        staff.add(c.staff_id)
        if c.is_active:
            out.active += 1
        if c.status in ("Cleared",
                              "Cleared (with information)"):
            out.cleared += 1
        if c.status in ("Applied", "Pending",
                              "Awaiting Certificate"):
            out.pending += 1
        if c.status == "Renewing":
            out.renewing += 1
        if c.update_service_subscribed:
            out.update_service_subscribed += 1
        if (c.is_active and c.expires_on
                and c.expires_on < today):
            out.expired += 1
        if (c.is_active and c.expires_on
                and today <= c.expires_on <= soon):
            out.expiring_soon += 1
        if c.update_check_overdue:
            out.update_check_overdue += 1
        if (c.risk_assessment_required
                and not c.risk_assessment_completed_on):
            out.risk_assessment_pending += 1
        if not c.signed_off_by:
            out.unsigned += 1
        out.by_level[c.level] = (
            out.by_level.get(c.level, 0) + 1)
        out.by_status[c.status] = (
            out.by_status.get(c.status, 0) + 1)
        out.by_certificate_type[c.certificate_type] = (
            out.by_certificate_type.get(
                c.certificate_type, 0) + 1)
    out.distinct_staff = len(staff)
    return out


__all__ = [
    "LEVELS", "DEFAULT_LEVEL",
    "CERTIFICATE_TYPES", "DEFAULT_CERTIFICATE_TYPE",
    "STATUSES", "DEFAULT_STATUS",
    "ValidationError",
    "DBSCheck", "DBSSummary",
    "init_db",
    "create_check", "update_check", "delete_check",
    "get_check", "list_checks", "checks_for_staff",
    "latest_for_staff",
    "issue_certificate", "see_certificate",
    "subscribe_update_service", "record_update_check",
    "complete_risk_assessment", "sign_off",
    "mark_lapsed", "start_renewal", "set_status",
    "summary",
]
