"""Staff HR data layer for Primary School System.

Two tables:
- `staff_hr_records`: one row per staff member (FK cascade on staff)
  with employment status, salary scale, DBS / right-to-work /
  safeguarding training expiry tracking, performance review
  scheduling and FTE working pattern.
- `staff_hr_events`: HR events log (annual leave, sick days,
  parental leave, training, TOIL, etc.) tied to a staff_id with
  optional days/hours.
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

EMPLOYMENT_STATUSES: tuple[str, ...] = (
    "Permanent",
    "Fixed Term",
    "Temporary",
    "Supply",
    "Casual",
    "Probation",
    "Notice",
    "Left",
)
DEFAULT_EMPLOYMENT_STATUS = "Permanent"

CONTRACT_TYPES: tuple[str, ...] = (
    "Full-time",
    "Part-time",
    "Term-time",
    "Compressed Hours",
    "Job Share",
    "Zero Hours",
    "Sessional",
    "Other",
)
DEFAULT_CONTRACT_TYPE = "Full-time"

SALARY_SCALES: tuple[str, ...] = (
    "MPS", "UPS", "Leadership", "TLR",
    "Support Staff", "Administrative",
    "Technician", "Premises",
    "Senior Leader", "Other",
)
DEFAULT_SALARY_SCALE = "MPS"

EVENT_TYPES: tuple[str, ...] = (
    "Annual Leave",
    "Sick Leave",
    "Parental Leave",
    "Compassionate Leave",
    "Unpaid Leave",
    "Training / CPD",
    "TOIL",
    "Jury Service",
    "Public Duty",
    "Other",
)
DEFAULT_EVENT_TYPE = "Annual Leave"

EVENT_STATUSES: tuple[str, ...] = (
    "Requested",
    "Approved",
    "Taken",
    "Declined",
    "Cancelled",
)
DEFAULT_EVENT_STATUS = "Requested"


class ValidationError(Exception):
    pass


@dataclass
class HRRecord:
    record_id: int
    staff_id: str
    employment_status: str
    contract_type: str
    fte_percent: float
    salary_scale: str
    spine_point: str | None
    salary_amount: float | None
    holiday_entitlement_days: float | None
    start_date: str
    probation_end: str | None
    contract_end: str | None
    end_date: str | None
    dbs_number: str | None
    dbs_issued_on: str | None
    dbs_expires_on: str | None
    right_to_work_checked: bool
    right_to_work_checked_on: str | None
    safeguarding_training_on: str | None
    safeguarding_expires_on: str | None
    last_review_on: str | None
    next_review_due: str | None
    pension_enrolled: bool
    union_member: str | None
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_active(self) -> bool:
        return self.employment_status not in ("Left",)

    @property
    def dbs_expired(self) -> bool:
        if not self.dbs_expires_on:
            return False
        return self.dbs_expires_on < _dt.date.today().isoformat()

    @property
    def safeguarding_expired(self) -> bool:
        if not self.safeguarding_expires_on:
            return False
        return (self.safeguarding_expires_on
                  < _dt.date.today().isoformat())

    @property
    def review_overdue(self) -> bool:
        if not self.next_review_due or not self.is_active:
            return False
        return self.next_review_due < _dt.date.today().isoformat()

    @property
    def probation_ending_soon(self) -> bool:
        if (self.employment_status != "Probation"
                or not self.probation_end):
            return False
        today = _dt.date.today()
        try:
            pe = _dt.date.fromisoformat(self.probation_end)
        except ValueError:
            return False
        return 0 <= (pe - today).days <= 30


@dataclass
class HREvent:
    event_id: int
    staff_id: str
    event_type: str
    event_status: str
    start_date: str
    end_date: str | None
    days: float | None
    hours: float | None
    reason: str | None
    notes: str | None
    approved_by: str | None
    approved_on: str | None
    created_on: str
    updated_on: str


@dataclass
class StaffHRSummary:
    total_records: int = 0
    active_records: int = 0
    on_probation: int = 0
    probation_ending_soon: int = 0
    dbs_expired: int = 0
    safeguarding_expired: int = 0
    reviews_overdue: int = 0
    right_to_work_missing: int = 0
    total_events: int = 0
    sick_events_open: int = 0
    annual_leave_taken_days: float = 0.0
    sick_taken_days: float = 0.0
    by_employment_status: dict[str, int] = field(default_factory=dict)
    by_contract_type: dict[str, int] = field(default_factory=dict)
    by_scale: dict[str, int] = field(default_factory=dict)
    by_event_type: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.STAFF_HR_DB)
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
            CREATE TABLE IF NOT EXISTS staff_hr_records (
                record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id TEXT NOT NULL UNIQUE,
                employment_status TEXT NOT NULL,
                contract_type TEXT NOT NULL,
                fte_percent REAL NOT NULL DEFAULT 100,
                salary_scale TEXT NOT NULL,
                spine_point TEXT,
                salary_amount REAL,
                holiday_entitlement_days REAL,
                start_date TEXT NOT NULL,
                probation_end TEXT,
                contract_end TEXT,
                end_date TEXT,
                dbs_number TEXT,
                dbs_issued_on TEXT,
                dbs_expires_on TEXT,
                right_to_work_checked INTEGER NOT NULL DEFAULT 0,
                right_to_work_checked_on TEXT,
                safeguarding_training_on TEXT,
                safeguarding_expires_on TEXT,
                last_review_on TEXT,
                next_review_due TEXT,
                pension_enrolled INTEGER NOT NULL DEFAULT 1,
                union_member TEXT,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL,
                FOREIGN KEY(staff_id) REFERENCES staff(staff_id)
                  ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS staff_hr_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_status TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT,
                days REAL,
                hours REAL,
                reason TEXT,
                notes TEXT,
                approved_by TEXT,
                approved_on TEXT,
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


# ── HR records ────────────────────────────────────────────────

def _validate_record(p: dict[str, Any], *,
                          existing_id: int | None = None
                          ) -> dict[str, Any]:
    out = dict(p)
    out["staff_id"] = (out.get("staff_id") or "").strip()
    if not out["staff_id"]:
        raise ValidationError("Staff is required")
    if not _staff_exists(out["staff_id"]):
        raise ValidationError(
            f"No staff with id {out['staff_id']}")

    es = (out.get("employment_status") or "").strip()
    if es not in EMPLOYMENT_STATUSES:
        raise ValidationError(
            f"Employment status must be one of: "
            f"{', '.join(EMPLOYMENT_STATUSES)}")
    out["employment_status"] = es

    ct = (out.get("contract_type") or DEFAULT_CONTRACT_TYPE).strip()
    if ct not in CONTRACT_TYPES:
        raise ValidationError(
            f"Contract type must be one of: "
            f"{', '.join(CONTRACT_TYPES)}")
    out["contract_type"] = ct

    scale = (out.get("salary_scale")
               or DEFAULT_SALARY_SCALE).strip()
    if scale not in SALARY_SCALES:
        raise ValidationError(
            f"Salary scale must be one of: "
            f"{', '.join(SALARY_SCALES)}")
    out["salary_scale"] = scale

    out["start_date"] = (out.get("start_date") or "").strip()
    if not out["start_date"]:
        raise ValidationError("Start date is required")
    _check_date("Start date",                out["start_date"])
    _check_date("Probation end",             out.get("probation_end"))
    _check_date("Contract end",              out.get("contract_end"))
    _check_date("End date",                  out.get("end_date"))
    _check_date("DBS issued on",             out.get("dbs_issued_on"))
    _check_date("DBS expires on",            out.get("dbs_expires_on"))
    _check_date("Right-to-work checked on",
                  out.get("right_to_work_checked_on"))
    _check_date("Safeguarding training on",
                  out.get("safeguarding_training_on"))
    _check_date("Safeguarding expires on",
                  out.get("safeguarding_expires_on"))
    _check_date("Last review on",            out.get("last_review_on"))
    _check_date("Next review due",           out.get("next_review_due"))

    try:
        fte = float(out.get("fte_percent") or 100)
    except (TypeError, ValueError):
        raise ValidationError(
            "FTE percent must be a number 0-100")
    if not (0 < fte <= 100):
        raise ValidationError(
            "FTE percent must be between 0 (exclusive) and 100")
    out["fte_percent"] = fte

    for key in ("salary_amount", "holiday_entitlement_days"):
        v = out.get(key)
        if v in (None, ""):
            out[key] = None
        else:
            try:
                out[key] = float(v)
            except (TypeError, ValueError):
                raise ValidationError(
                    f"{key.replace('_', ' ')} must be a number")
            if out[key] < 0:
                raise ValidationError(
                    f"{key.replace('_', ' ')} must be >= 0")

    for k in ("spine_point", "dbs_number", "union_member",
               "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("probation_end", "contract_end", "end_date",
               "dbs_issued_on", "dbs_expires_on",
               "right_to_work_checked_on",
               "safeguarding_training_on",
               "safeguarding_expires_on",
               "last_review_on", "next_review_due"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v
    out["right_to_work_checked"] = bool(
        out.get("right_to_work_checked"))
    out["pension_enrolled"] = bool(
        out.get("pension_enrolled", True))

    # Uniqueness of staff_id (one HR record per staff)
    with _connect() as conn:
        row = conn.execute(
            "SELECT record_id FROM staff_hr_records "
            "WHERE staff_id=?", (out["staff_id"],)).fetchone()
    if row and row["record_id"] != existing_id:
        raise ValidationError(
            f"Staff {out['staff_id']} already has an HR record")
    return out


def _row_record(r: sqlite3.Row) -> HRRecord:
    return HRRecord(
        record_id=r["record_id"],
        staff_id=r["staff_id"],
        employment_status=r["employment_status"],
        contract_type=r["contract_type"],
        fte_percent=r["fte_percent"],
        salary_scale=r["salary_scale"],
        spine_point=r["spine_point"],
        salary_amount=r["salary_amount"],
        holiday_entitlement_days=r["holiday_entitlement_days"],
        start_date=r["start_date"],
        probation_end=r["probation_end"],
        contract_end=r["contract_end"],
        end_date=r["end_date"],
        dbs_number=r["dbs_number"],
        dbs_issued_on=r["dbs_issued_on"],
        dbs_expires_on=r["dbs_expires_on"],
        right_to_work_checked=bool(r["right_to_work_checked"]),
        right_to_work_checked_on=r["right_to_work_checked_on"],
        safeguarding_training_on=r["safeguarding_training_on"],
        safeguarding_expires_on=r["safeguarding_expires_on"],
        last_review_on=r["last_review_on"],
        next_review_due=r["next_review_due"],
        pension_enrolled=bool(r["pension_enrolled"]),
        union_member=r["union_member"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_record(payload: dict[str, Any]) -> HRRecord:
    init_db()
    p = _validate_record(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO staff_hr_records (
              staff_id, employment_status, contract_type,
              fte_percent, salary_scale, spine_point,
              salary_amount, holiday_entitlement_days,
              start_date, probation_end, contract_end, end_date,
              dbs_number, dbs_issued_on, dbs_expires_on,
              right_to_work_checked, right_to_work_checked_on,
              safeguarding_training_on, safeguarding_expires_on,
              last_review_on, next_review_due,
              pension_enrolled, union_member, notes,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["staff_id"], p["employment_status"], p["contract_type"],
            p["fte_percent"], p["salary_scale"], p["spine_point"],
            p["salary_amount"], p["holiday_entitlement_days"],
            p["start_date"], p["probation_end"],
            p["contract_end"], p["end_date"],
            p["dbs_number"], p["dbs_issued_on"],
            p["dbs_expires_on"],
            1 if p["right_to_work_checked"] else 0,
            p["right_to_work_checked_on"],
            p["safeguarding_training_on"],
            p["safeguarding_expires_on"],
            p["last_review_on"], p["next_review_due"],
            1 if p["pension_enrolled"] else 0,
            p["union_member"], p["notes"], now, now,
        ))
        new_id = cur.lastrowid
    return get_record(new_id)


def update_record(record_id: int,
                       payload: dict[str, Any]) -> HRRecord:
    init_db()
    if get_record(record_id) is None:
        raise ValidationError(f"No HR record with id {record_id}")
    p = _validate_record(payload, existing_id=record_id)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE staff_hr_records SET
              staff_id=?, employment_status=?, contract_type=?,
              fte_percent=?, salary_scale=?, spine_point=?,
              salary_amount=?, holiday_entitlement_days=?,
              start_date=?, probation_end=?, contract_end=?,
              end_date=?,
              dbs_number=?, dbs_issued_on=?, dbs_expires_on=?,
              right_to_work_checked=?, right_to_work_checked_on=?,
              safeguarding_training_on=?, safeguarding_expires_on=?,
              last_review_on=?, next_review_due=?,
              pension_enrolled=?, union_member=?, notes=?,
              updated_on=?
            WHERE record_id=?
        """, (
            p["staff_id"], p["employment_status"], p["contract_type"],
            p["fte_percent"], p["salary_scale"], p["spine_point"],
            p["salary_amount"], p["holiday_entitlement_days"],
            p["start_date"], p["probation_end"],
            p["contract_end"], p["end_date"],
            p["dbs_number"], p["dbs_issued_on"],
            p["dbs_expires_on"],
            1 if p["right_to_work_checked"] else 0,
            p["right_to_work_checked_on"],
            p["safeguarding_training_on"],
            p["safeguarding_expires_on"],
            p["last_review_on"], p["next_review_due"],
            1 if p["pension_enrolled"] else 0,
            p["union_member"], p["notes"], now, record_id,
        ))
    return get_record(record_id)


def delete_record(record_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM staff_hr_records WHERE record_id=?",
            (record_id,))
        return cur.rowcount > 0


def get_record(record_id: int) -> HRRecord | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM staff_hr_records WHERE record_id=?",
            (record_id,)).fetchone()
        return _row_record(r) if r else None


def get_record_for_staff(staff_id: str) -> HRRecord | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM staff_hr_records WHERE staff_id=?",
            (staff_id,)).fetchone()
        return _row_record(r) if r else None


def list_records(*,
                      employment_status: str | None = None,
                      contract_type: str | None = None,
                      salary_scale: str | None = None,
                      active_only: bool = False,
                      probation_only: bool = False,
                      dbs_expired: bool = False,
                      safeguarding_expired: bool = False,
                      reviews_overdue: bool = False,
                      rtw_missing: bool = False,
                      ) -> list[HRRecord]:
    init_db()
    sql = "SELECT * FROM staff_hr_records WHERE 1=1"
    params: list[Any] = []
    if employment_status:
        sql += " AND employment_status=?"
        params.append(employment_status)
    if contract_type:
        sql += " AND contract_type=?"
        params.append(contract_type)
    if salary_scale:
        sql += " AND salary_scale=?"
        params.append(salary_scale)
    if active_only:
        sql += " AND employment_status != 'Left'"
    if probation_only:
        sql += " AND employment_status='Probation'"
    today = _dt.date.today().isoformat()
    if dbs_expired:
        sql += (" AND dbs_expires_on IS NOT NULL"
                  " AND dbs_expires_on < ?"
                  " AND employment_status != 'Left'")
        params.append(today)
    if safeguarding_expired:
        sql += (" AND safeguarding_expires_on IS NOT NULL"
                  " AND safeguarding_expires_on < ?"
                  " AND employment_status != 'Left'")
        params.append(today)
    if reviews_overdue:
        sql += (" AND next_review_due IS NOT NULL"
                  " AND next_review_due < ?"
                  " AND employment_status != 'Left'")
        params.append(today)
    if rtw_missing:
        sql += (" AND right_to_work_checked=0"
                  " AND employment_status != 'Left'")
    sql += " ORDER BY staff_id ASC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_record(r) for r in rows]


def _to_record_dict(r: HRRecord) -> dict[str, Any]:
    return {
        "staff_id": r.staff_id,
        "employment_status": r.employment_status,
        "contract_type": r.contract_type,
        "fte_percent": r.fte_percent,
        "salary_scale": r.salary_scale,
        "spine_point": r.spine_point,
        "salary_amount": r.salary_amount,
        "holiday_entitlement_days": r.holiday_entitlement_days,
        "start_date": r.start_date,
        "probation_end": r.probation_end,
        "contract_end": r.contract_end,
        "end_date": r.end_date,
        "dbs_number": r.dbs_number,
        "dbs_issued_on": r.dbs_issued_on,
        "dbs_expires_on": r.dbs_expires_on,
        "right_to_work_checked": r.right_to_work_checked,
        "right_to_work_checked_on": r.right_to_work_checked_on,
        "safeguarding_training_on": r.safeguarding_training_on,
        "safeguarding_expires_on": r.safeguarding_expires_on,
        "last_review_on": r.last_review_on,
        "next_review_due": r.next_review_due,
        "pension_enrolled": r.pension_enrolled,
        "union_member": r.union_member,
        "notes": r.notes,
    }


def record_review(record_id: int, *,
                       reviewed_on: str | None = None,
                       next_review_due: str | None = None
                       ) -> HRRecord:
    r = get_record(record_id)
    if r is None:
        raise ValidationError(f"No HR record with id {record_id}")
    data = _to_record_dict(r)
    data["last_review_on"] = (reviewed_on
                                   or _dt.date.today().isoformat())
    if next_review_due is not None:
        data["next_review_due"] = next_review_due
    return update_record(record_id, data)


def renew_dbs(record_id: int, *,
                  number: str,
                  issued_on: str | None = None,
                  expires_on: str | None = None) -> HRRecord:
    if not number:
        raise ValidationError("DBS number is required")
    r = get_record(record_id)
    if r is None:
        raise ValidationError(f"No HR record with id {record_id}")
    data = _to_record_dict(r)
    data["dbs_number"] = number
    data["dbs_issued_on"] = (issued_on
                                  or _dt.date.today().isoformat())
    if expires_on:
        data["dbs_expires_on"] = expires_on
    return update_record(record_id, data)


def mark_safeguarding_completed(
        record_id: int, *,
        trained_on: str | None = None,
        expires_on: str | None = None) -> HRRecord:
    r = get_record(record_id)
    if r is None:
        raise ValidationError(f"No HR record with id {record_id}")
    data = _to_record_dict(r)
    data["safeguarding_training_on"] = (
        trained_on or _dt.date.today().isoformat())
    if expires_on:
        data["safeguarding_expires_on"] = expires_on
    return update_record(record_id, data)


def set_employment_status(record_id: int,
                                new_status: str) -> HRRecord:
    if new_status not in EMPLOYMENT_STATUSES:
        raise ValidationError(
            f"Employment status must be one of: "
            f"{', '.join(EMPLOYMENT_STATUSES)}")
    r = get_record(record_id)
    if r is None:
        raise ValidationError(f"No HR record with id {record_id}")
    return update_record(record_id,
                              {**_to_record_dict(r),
                                "employment_status": new_status})


def mark_left(record_id: int, *,
                  end_date: str | None = None) -> HRRecord:
    r = get_record(record_id)
    if r is None:
        raise ValidationError(f"No HR record with id {record_id}")
    data = _to_record_dict(r)
    data["employment_status"] = "Left"
    data["end_date"] = (end_date
                            or _dt.date.today().isoformat())
    return update_record(record_id, data)


# ── HR events ────────────────────────────────────────────────

def _validate_event(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["staff_id"] = (out.get("staff_id") or "").strip()
    if not out["staff_id"]:
        raise ValidationError("Staff is required")
    if not _staff_exists(out["staff_id"]):
        raise ValidationError(
            f"No staff with id {out['staff_id']}")
    et = (out.get("event_type") or "").strip()
    if et not in EVENT_TYPES:
        raise ValidationError(
            f"Event type must be one of: "
            f"{', '.join(EVENT_TYPES)}")
    out["event_type"] = et
    status = (out.get("event_status")
                or DEFAULT_EVENT_STATUS).strip()
    if status not in EVENT_STATUSES:
        raise ValidationError(
            f"Event status must be one of: "
            f"{', '.join(EVENT_STATUSES)}")
    out["event_status"] = status
    out["start_date"] = (out.get("start_date") or "").strip()
    if not out["start_date"]:
        raise ValidationError("Start date is required")
    _check_date("Start date",   out["start_date"])
    _check_date("End date",     out.get("end_date"))
    _check_date("Approved on",  out.get("approved_on"))
    if (out.get("end_date") and out["end_date"]
            < out["start_date"]):
        raise ValidationError(
            "End date must be on or after start date")
    for key in ("days", "hours"):
        v = out.get(key)
        if v in (None, ""):
            out[key] = None
        else:
            try:
                out[key] = float(v)
            except (TypeError, ValueError):
                raise ValidationError(
                    f"{key} must be a number")
            if out[key] < 0:
                raise ValidationError(f"{key} must be >= 0")
    for k in ("reason", "notes", "approved_by"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("end_date", "approved_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v
    return out


def _row_event(r: sqlite3.Row) -> HREvent:
    return HREvent(
        event_id=r["event_id"],
        staff_id=r["staff_id"],
        event_type=r["event_type"],
        event_status=r["event_status"],
        start_date=r["start_date"],
        end_date=r["end_date"],
        days=r["days"],
        hours=r["hours"],
        reason=r["reason"],
        notes=r["notes"],
        approved_by=r["approved_by"],
        approved_on=r["approved_on"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_event(payload: dict[str, Any]) -> HREvent:
    init_db()
    p = _validate_event(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO staff_hr_events (
              staff_id, event_type, event_status,
              start_date, end_date, days, hours,
              reason, notes, approved_by, approved_on,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["staff_id"], p["event_type"], p["event_status"],
            p["start_date"], p["end_date"], p["days"], p["hours"],
            p["reason"], p["notes"], p["approved_by"],
            p["approved_on"], now, now,
        ))
        new_id = cur.lastrowid
    return get_event(new_id)


def update_event(event_id: int,
                      payload: dict[str, Any]) -> HREvent:
    init_db()
    if get_event(event_id) is None:
        raise ValidationError(f"No event with id {event_id}")
    p = _validate_event(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE staff_hr_events SET
              staff_id=?, event_type=?, event_status=?,
              start_date=?, end_date=?, days=?, hours=?,
              reason=?, notes=?, approved_by=?, approved_on=?,
              updated_on=?
            WHERE event_id=?
        """, (
            p["staff_id"], p["event_type"], p["event_status"],
            p["start_date"], p["end_date"], p["days"], p["hours"],
            p["reason"], p["notes"], p["approved_by"],
            p["approved_on"], now, event_id,
        ))
    return get_event(event_id)


def delete_event(event_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM staff_hr_events WHERE event_id=?",
            (event_id,))
        return cur.rowcount > 0


def get_event(event_id: int) -> HREvent | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM staff_hr_events WHERE event_id=?",
            (event_id,)).fetchone()
        return _row_event(r) if r else None


def list_events(*,
                     staff_id: str | None = None,
                     event_type: str | None = None,
                     event_status: str | None = None,
                     date_from: str | None = None,
                     date_to: str | None = None,
                     ) -> list[HREvent]:
    init_db()
    sql = "SELECT * FROM staff_hr_events WHERE 1=1"
    params: list[Any] = []
    if staff_id:
        sql += " AND staff_id=?"
        params.append(staff_id)
    if event_type:
        sql += " AND event_type=?"
        params.append(event_type)
    if event_status:
        sql += " AND event_status=?"
        params.append(event_status)
    if date_from:
        _check_date("From", date_from)
        sql += " AND start_date >= ?"
        params.append(date_from)
    if date_to:
        _check_date("To", date_to)
        sql += " AND start_date <= ?"
        params.append(date_to)
    sql += " ORDER BY start_date DESC, event_id DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_event(r) for r in rows]


def _to_event_dict(e: HREvent) -> dict[str, Any]:
    return {
        "staff_id": e.staff_id,
        "event_type": e.event_type,
        "event_status": e.event_status,
        "start_date": e.start_date,
        "end_date": e.end_date,
        "days": e.days,
        "hours": e.hours,
        "reason": e.reason,
        "notes": e.notes,
        "approved_by": e.approved_by,
        "approved_on": e.approved_on,
    }


def approve_event(event_id: int, *,
                       approved_by: str,
                       approved_on: str | None = None) -> HREvent:
    if not approved_by:
        raise ValidationError("Approved by is required")
    e = get_event(event_id)
    if e is None:
        raise ValidationError(f"No event with id {event_id}")
    data = _to_event_dict(e)
    data["event_status"] = "Approved"
    data["approved_by"] = approved_by
    data["approved_on"] = (approved_on
                                or _dt.date.today().isoformat())
    return update_event(event_id, data)


def decline_event(event_id: int) -> HREvent:
    e = get_event(event_id)
    if e is None:
        raise ValidationError(f"No event with id {event_id}")
    return update_event(event_id,
                              {**_to_event_dict(e),
                                "event_status": "Declined"})


def mark_taken(event_id: int) -> HREvent:
    e = get_event(event_id)
    if e is None:
        raise ValidationError(f"No event with id {event_id}")
    return update_event(event_id,
                              {**_to_event_dict(e),
                                "event_status": "Taken"})


# ── Summary ───────────────────────────────────────────────────────

def summary() -> StaffHRSummary:
    records = list_records()
    events = list_events()
    out = StaffHRSummary(
        total_records=len(records),
        active_records=sum(1 for r in records if r.is_active),
    )
    for r in records:
        if r.employment_status == "Probation":
            out.on_probation += 1
            if r.probation_ending_soon:
                out.probation_ending_soon += 1
        if r.dbs_expired:
            out.dbs_expired += 1
        if r.safeguarding_expired:
            out.safeguarding_expired += 1
        if r.review_overdue:
            out.reviews_overdue += 1
        if (r.is_active and not r.right_to_work_checked):
            out.right_to_work_missing += 1
        out.by_employment_status[r.employment_status] = (
            out.by_employment_status.get(
                r.employment_status, 0) + 1)
        out.by_contract_type[r.contract_type] = (
            out.by_contract_type.get(r.contract_type, 0) + 1)
        out.by_scale[r.salary_scale] = (
            out.by_scale.get(r.salary_scale, 0) + 1)
    for e in events:
        out.total_events += 1
        out.by_event_type[e.event_type] = (
            out.by_event_type.get(e.event_type, 0) + 1)
        if (e.event_type == "Sick Leave"
                and e.event_status not in ("Cancelled",
                                                  "Declined")):
            if e.event_status != "Taken":
                out.sick_events_open += 1
            if e.days:
                out.sick_taken_days += e.days
        if (e.event_type == "Annual Leave"
                and e.event_status == "Taken"
                and e.days):
            out.annual_leave_taken_days += e.days
    out.annual_leave_taken_days = round(
        out.annual_leave_taken_days, 1)
    out.sick_taken_days = round(out.sick_taken_days, 1)
    return out


__all__ = [
    "EMPLOYMENT_STATUSES", "DEFAULT_EMPLOYMENT_STATUS",
    "CONTRACT_TYPES", "DEFAULT_CONTRACT_TYPE",
    "SALARY_SCALES", "DEFAULT_SALARY_SCALE",
    "EVENT_TYPES", "DEFAULT_EVENT_TYPE",
    "EVENT_STATUSES", "DEFAULT_EVENT_STATUS",
    "ValidationError",
    "HRRecord", "HREvent", "StaffHRSummary",
    "init_db",
    "create_record", "update_record", "delete_record",
    "get_record", "get_record_for_staff", "list_records",
    "record_review", "renew_dbs",
    "mark_safeguarding_completed",
    "set_employment_status", "mark_left",
    "create_event", "update_event", "delete_event",
    "get_event", "list_events",
    "approve_event", "decline_event", "mark_taken",
    "summary",
]
