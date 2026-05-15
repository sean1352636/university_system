"""Staff Wellbeing data layer for Primary School System.

Per-staff wellbeing entries: 1:1 check-ins, survey responses,
concern flags, workload reviews, EAP/OH referrals. Confidential by
default — visible only to wellbeing staff. FK cascade on staff.

Captures Likert ratings (mood / stress / workload pressure 1-5),
concern flag chips, action plan and follow-up workflow.
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

ENTRY_TYPES: tuple[str, ...] = (
    "1:1 Check-In",
    "Wellbeing Survey",
    "Concern Flagged",
    "EAP Referral",
    "Counselling Referral",
    "Occupational Health Referral",
    "Workload Review",
    "Stress Risk Assessment",
    "Mental Health First Aid Contact",
    "Sickness Trigger Review",
    "Self-Submitted",
    "Other",
)
DEFAULT_ENTRY_TYPE = "1:1 Check-In"

CONCERN_FLAGS: tuple[str, ...] = (
    "Workload",
    "Work-Life Balance",
    "Relationships at Work",
    "Health",
    "Mental Health",
    "Family / Caring",
    "Bereavement",
    "Financial",
    "Housing",
    "Discrimination",
    "Bullying",
    "Pupil Behaviour",
    "Other",
)

LIKERTS: tuple[int, ...] = (1, 2, 3, 4, 5)
_LIKERT_LABELS = {
    1: "Very Low", 2: "Low", 3: "Moderate",
    4: "High", 5: "Very High",
}


def likert_label(v: int | None) -> str:
    if v is None:
        return "—"
    return _LIKERT_LABELS.get(v, "Unknown")


ACTION_TYPES: tuple[str, ...] = (
    "Signposted to EAP",
    "Workload Adjusted",
    "Mentor Assigned",
    "Occupational Health Referral",
    "GP Advised",
    "Support Plan Created",
    "Phased Return Discussed",
    "Reasonable Adjustments",
    "Mediation Offered",
    "External Counselling",
    "No Action Required",
    "Other",
)

STATUSES: tuple[str, ...] = (
    "Recorded",
    "Reviewing",
    "Action Plan Set",
    "Monitoring",
    "Resolved",
    "Closed",
)
DEFAULT_STATUS = "Recorded"


class ValidationError(Exception):
    pass


@dataclass
class WellbeingEntry:
    entry_id: int
    staff_id: str
    entry_date: str
    entry_type: str
    confidential: bool
    anonymous: bool
    recorded_by: str | None
    mood: int | None
    stress: int | None
    workload_pressure: int | None
    job_satisfaction: int | None
    energy: int | None
    concern_flags: str | None
    presenting_issue: str | None
    summary_notes: str | None
    actions_taken: str | None
    action_type: str | None
    referred_to: str | None
    follow_up_due: str | None
    follow_up_done_on: str | None
    support_plan: str | None
    consent_to_share: bool
    status: str
    closed_on: str | None
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_open(self) -> bool:
        return self.status not in ("Resolved", "Closed")

    @property
    def follow_up_overdue(self) -> bool:
        if (not self.is_open or not self.follow_up_due
                or self.follow_up_done_on):
            return False
        return self.follow_up_due < _dt.date.today().isoformat()

    @property
    def concern_flag_list(self) -> list[str]:
        if not self.concern_flags:
            return []
        return [c.strip() for c in self.concern_flags.split(",")
                  if c.strip()]

    @property
    def average_score(self) -> float | None:
        scores = [s for s in (self.mood, self.stress,
                                  self.workload_pressure,
                                  self.job_satisfaction,
                                  self.energy)
                    if s is not None]
        if not scores:
            return None
        return round(sum(scores) / len(scores), 2)

    @property
    def at_risk(self) -> bool:
        """Stress >= 4 OR workload_pressure >= 4 OR mood <= 2."""
        return (
            (self.stress is not None and self.stress >= 4)
            or (self.workload_pressure is not None
                  and self.workload_pressure >= 4)
            or (self.mood is not None and self.mood <= 2))


@dataclass
class WellbeingSummary:
    total: int = 0
    open_count: int = 0
    at_risk: int = 0
    follow_up_overdue: int = 0
    referrals_made: int = 0
    distinct_staff: int = 0
    average_mood: float | None = None
    average_stress: float | None = None
    average_workload: float | None = None
    average_satisfaction: float | None = None
    average_energy: float | None = None
    by_type: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    by_action: dict[str, int] = field(default_factory=dict)
    by_concern_flag: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.STAFF_WELLBEING_DB)
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
            CREATE TABLE IF NOT EXISTS staff_wellbeing_entries (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                entry_type TEXT NOT NULL,
                confidential INTEGER NOT NULL DEFAULT 1,
                anonymous INTEGER NOT NULL DEFAULT 0,
                recorded_by TEXT,
                mood INTEGER,
                stress INTEGER,
                workload_pressure INTEGER,
                job_satisfaction INTEGER,
                energy INTEGER,
                concern_flags TEXT,
                presenting_issue TEXT,
                summary_notes TEXT,
                actions_taken TEXT,
                action_type TEXT,
                referred_to TEXT,
                follow_up_due TEXT,
                follow_up_done_on TEXT,
                support_plan TEXT,
                consent_to_share INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                closed_on TEXT,
                notes TEXT,
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


def _check_likert(label: str, v: Any) -> int | None:
    if v in (None, ""):
        return None
    try:
        iv = int(v)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be 1-5")
    if iv not in LIKERTS:
        raise ValidationError(f"{label} must be 1-5")
    return iv


def _validate_payload(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["staff_id"] = (out.get("staff_id") or "").strip()
    if not out["staff_id"]:
        raise ValidationError("Staff is required")
    if not _staff_exists(out["staff_id"]):
        raise ValidationError(
            f"No staff with id {out['staff_id']}")

    out["entry_date"] = (out.get("entry_date") or "").strip()
    if not out["entry_date"]:
        out["entry_date"] = _dt.date.today().isoformat()
    _check_date("Entry date",      out["entry_date"])
    _check_date("Follow-up due",   out.get("follow_up_due"))
    _check_date("Follow-up done",  out.get("follow_up_done_on"))
    _check_date("Closed on",       out.get("closed_on"))

    et = (out.get("entry_type") or "").strip()
    if et not in ENTRY_TYPES:
        raise ValidationError(
            f"Entry type must be one of: "
            f"{', '.join(ENTRY_TYPES)}")
    out["entry_type"] = et

    status = (out.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    for key in ("mood", "stress", "workload_pressure",
                  "job_satisfaction", "energy"):
        out[key] = _check_likert(key.replace("_", " ").title(),
                                       out.get(key))

    cf = out.get("concern_flags")
    if cf is None:
        out["concern_flags"] = None
    elif isinstance(cf, (list, tuple)):
        for c in cf:
            if c not in CONCERN_FLAGS:
                raise ValidationError(
                    f"Concern flag {c!r} is not recognised")
        out["concern_flags"] = ", ".join(cf) if cf else None
    elif isinstance(cf, str):
        parts = [c.strip() for c in cf.split(",")
                   if c.strip()]
        for c in parts:
            if c not in CONCERN_FLAGS:
                raise ValidationError(
                    f"Concern flag {c!r} is not recognised")
        out["concern_flags"] = ", ".join(parts) or None

    at = out.get("action_type")
    if at and at.strip():
        at = at.strip()
        if at not in ACTION_TYPES:
            raise ValidationError(
                f"Action type must be one of: "
                f"{', '.join(ACTION_TYPES)}")
        out["action_type"] = at
    else:
        out["action_type"] = None

    for k in ("recorded_by", "presenting_issue",
               "summary_notes", "actions_taken",
               "referred_to", "support_plan", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("follow_up_due", "follow_up_done_on", "closed_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v
    out["confidential"] = bool(out.get("confidential", True))
    out["anonymous"] = bool(out.get("anonymous"))
    out["consent_to_share"] = bool(out.get("consent_to_share"))
    return out


def _row(r: sqlite3.Row) -> WellbeingEntry:
    return WellbeingEntry(
        entry_id=r["entry_id"],
        staff_id=r["staff_id"],
        entry_date=r["entry_date"],
        entry_type=r["entry_type"],
        confidential=bool(r["confidential"]),
        anonymous=bool(r["anonymous"]),
        recorded_by=r["recorded_by"],
        mood=r["mood"],
        stress=r["stress"],
        workload_pressure=r["workload_pressure"],
        job_satisfaction=r["job_satisfaction"],
        energy=r["energy"],
        concern_flags=r["concern_flags"],
        presenting_issue=r["presenting_issue"],
        summary_notes=r["summary_notes"],
        actions_taken=r["actions_taken"],
        action_type=r["action_type"],
        referred_to=r["referred_to"],
        follow_up_due=r["follow_up_due"],
        follow_up_done_on=r["follow_up_done_on"],
        support_plan=r["support_plan"],
        consent_to_share=bool(r["consent_to_share"]),
        status=r["status"],
        closed_on=r["closed_on"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_entry(payload: dict[str, Any]) -> WellbeingEntry:
    init_db()
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO staff_wellbeing_entries (
              staff_id, entry_date, entry_type, confidential,
              anonymous, recorded_by,
              mood, stress, workload_pressure,
              job_satisfaction, energy,
              concern_flags, presenting_issue, summary_notes,
              actions_taken, action_type, referred_to,
              follow_up_due, follow_up_done_on, support_plan,
              consent_to_share, status, closed_on, notes,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["staff_id"], p["entry_date"], p["entry_type"],
            1 if p["confidential"] else 0,
            1 if p["anonymous"] else 0, p["recorded_by"],
            p["mood"], p["stress"], p["workload_pressure"],
            p["job_satisfaction"], p["energy"],
            p["concern_flags"], p["presenting_issue"],
            p["summary_notes"], p["actions_taken"],
            p["action_type"], p["referred_to"],
            p["follow_up_due"], p["follow_up_done_on"],
            p["support_plan"],
            1 if p["consent_to_share"] else 0,
            p["status"], p["closed_on"], p["notes"], now, now,
        ))
        new_id = cur.lastrowid
    return get_entry(new_id)


def update_entry(entry_id: int,
                      payload: dict[str, Any]) -> WellbeingEntry:
    init_db()
    if get_entry(entry_id) is None:
        raise ValidationError(f"No entry with id {entry_id}")
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE staff_wellbeing_entries SET
              staff_id=?, entry_date=?, entry_type=?,
              confidential=?, anonymous=?, recorded_by=?,
              mood=?, stress=?, workload_pressure=?,
              job_satisfaction=?, energy=?,
              concern_flags=?, presenting_issue=?, summary_notes=?,
              actions_taken=?, action_type=?, referred_to=?,
              follow_up_due=?, follow_up_done_on=?, support_plan=?,
              consent_to_share=?, status=?, closed_on=?, notes=?,
              updated_on=?
            WHERE entry_id=?
        """, (
            p["staff_id"], p["entry_date"], p["entry_type"],
            1 if p["confidential"] else 0,
            1 if p["anonymous"] else 0, p["recorded_by"],
            p["mood"], p["stress"], p["workload_pressure"],
            p["job_satisfaction"], p["energy"],
            p["concern_flags"], p["presenting_issue"],
            p["summary_notes"], p["actions_taken"],
            p["action_type"], p["referred_to"],
            p["follow_up_due"], p["follow_up_done_on"],
            p["support_plan"],
            1 if p["consent_to_share"] else 0,
            p["status"], p["closed_on"], p["notes"],
            now, entry_id,
        ))
    return get_entry(entry_id)


def delete_entry(entry_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM staff_wellbeing_entries WHERE entry_id=?",
            (entry_id,))
        return cur.rowcount > 0


def get_entry(entry_id: int) -> WellbeingEntry | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM staff_wellbeing_entries "
            "WHERE entry_id=?", (entry_id,)).fetchone()
        return _row(r) if r else None


def list_entries(*,
                      staff_id: str | None = None,
                      entry_type: str | None = None,
                      status: str | None = None,
                      action_type: str | None = None,
                      open_only: bool = False,
                      at_risk_only: bool = False,
                      follow_up_overdue: bool = False,
                      with_concern_flag: str | None = None,
                      date_from: str | None = None,
                      date_to: str | None = None,
                      ) -> list[WellbeingEntry]:
    init_db()
    sql = "SELECT * FROM staff_wellbeing_entries WHERE 1=1"
    params: list[Any] = []
    if staff_id:
        sql += " AND staff_id=?"
        params.append(staff_id)
    if entry_type:
        sql += " AND entry_type=?"
        params.append(entry_type)
    if status:
        sql += " AND status=?"
        params.append(status)
    if action_type:
        sql += " AND action_type=?"
        params.append(action_type)
    if open_only:
        sql += " AND status NOT IN ('Resolved','Closed')"
    if at_risk_only:
        sql += (" AND ((stress IS NOT NULL AND stress >= 4)"
                  " OR (workload_pressure IS NOT NULL"
                  " AND workload_pressure >= 4)"
                  " OR (mood IS NOT NULL AND mood <= 2))")
    if follow_up_overdue:
        today = _dt.date.today().isoformat()
        sql += (" AND follow_up_due IS NOT NULL"
                  " AND follow_up_due < ?"
                  " AND follow_up_done_on IS NULL"
                  " AND status NOT IN ('Resolved','Closed')")
        params.append(today)
    if with_concern_flag:
        sql += " AND concern_flags LIKE ?"
        params.append(f"%{with_concern_flag}%")
    if date_from:
        _check_date("From", date_from)
        sql += " AND entry_date >= ?"
        params.append(date_from)
    if date_to:
        _check_date("To", date_to)
        sql += " AND entry_date <= ?"
        params.append(date_to)
    sql += " ORDER BY entry_date DESC, entry_id DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row(r) for r in rows]


def entries_for_staff(staff_id: str) -> list[WellbeingEntry]:
    return list_entries(staff_id=staff_id)


# ── Workflow ──────────────────────────────────────────────

def _to_dict(e: WellbeingEntry) -> dict[str, Any]:
    return {
        "staff_id": e.staff_id,
        "entry_date": e.entry_date,
        "entry_type": e.entry_type,
        "confidential": e.confidential,
        "anonymous": e.anonymous,
        "recorded_by": e.recorded_by,
        "mood": e.mood,
        "stress": e.stress,
        "workload_pressure": e.workload_pressure,
        "job_satisfaction": e.job_satisfaction,
        "energy": e.energy,
        "concern_flags": e.concern_flags,
        "presenting_issue": e.presenting_issue,
        "summary_notes": e.summary_notes,
        "actions_taken": e.actions_taken,
        "action_type": e.action_type,
        "referred_to": e.referred_to,
        "follow_up_due": e.follow_up_due,
        "follow_up_done_on": e.follow_up_done_on,
        "support_plan": e.support_plan,
        "consent_to_share": e.consent_to_share,
        "status": e.status,
        "closed_on": e.closed_on,
        "notes": e.notes,
    }


def set_action_plan(entry_id: int, *,
                         action_type: str,
                         actions_taken: str,
                         support_plan: str | None = None,
                         follow_up_due: str | None = None,
                         referred_to: str | None = None
                         ) -> WellbeingEntry:
    if action_type not in ACTION_TYPES:
        raise ValidationError(
            f"Action type must be one of: "
            f"{', '.join(ACTION_TYPES)}")
    if not actions_taken:
        raise ValidationError("Actions taken is required")
    e = get_entry(entry_id)
    if e is None:
        raise ValidationError(f"No entry with id {entry_id}")
    data = _to_dict(e)
    data["action_type"] = action_type
    data["actions_taken"] = actions_taken
    if support_plan is not None:
        data["support_plan"] = support_plan
    if follow_up_due is not None:
        data["follow_up_due"] = follow_up_due
    if referred_to is not None:
        data["referred_to"] = referred_to
    data["status"] = "Action Plan Set"
    return update_entry(entry_id, data)


def complete_follow_up(entry_id: int, *,
                            done_on: str | None = None,
                            notes: str | None = None
                            ) -> WellbeingEntry:
    e = get_entry(entry_id)
    if e is None:
        raise ValidationError(f"No entry with id {entry_id}")
    data = _to_dict(e)
    data["follow_up_done_on"] = (done_on
                                       or _dt.date.today().isoformat())
    if notes:
        existing = data["notes"] or ""
        prefix = (existing + "\n") if existing else ""
        data["notes"] = (
            prefix
            + f"{_dt.date.today().isoformat()} follow-up: "
            f"{notes}")
    if data["status"] == "Action Plan Set":
        data["status"] = "Monitoring"
    return update_entry(entry_id, data)


def resolve(entry_id: int) -> WellbeingEntry:
    e = get_entry(entry_id)
    if e is None:
        raise ValidationError(f"No entry with id {entry_id}")
    data = _to_dict(e)
    data["status"] = "Resolved"
    data["closed_on"] = (data["closed_on"]
                              or _dt.date.today().isoformat())
    return update_entry(entry_id, data)


def close_entry(entry_id: int) -> WellbeingEntry:
    e = get_entry(entry_id)
    if e is None:
        raise ValidationError(f"No entry with id {entry_id}")
    data = _to_dict(e)
    data["status"] = "Closed"
    data["closed_on"] = (data["closed_on"]
                              or _dt.date.today().isoformat())
    return update_entry(entry_id, data)


def set_status(entry_id: int, new_status: str) -> WellbeingEntry:
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    e = get_entry(entry_id)
    if e is None:
        raise ValidationError(f"No entry with id {entry_id}")
    return update_entry(entry_id,
                              {**_to_dict(e), "status": new_status})


# ── Summary ──────────────────────────────────────────────

def summary() -> WellbeingSummary:
    rows = list_entries()
    out = WellbeingSummary(total=len(rows))
    if not rows:
        return out
    mood: list[int] = []
    stress: list[int] = []
    workload: list[int] = []
    sat: list[int] = []
    energy: list[int] = []
    staff: set[str] = set()
    for e in rows:
        staff.add(e.staff_id)
        if e.is_open:
            out.open_count += 1
        if e.at_risk:
            out.at_risk += 1
        if e.follow_up_overdue:
            out.follow_up_overdue += 1
        if e.entry_type in ("EAP Referral",
                                  "Counselling Referral",
                                  "Occupational Health Referral"):
            out.referrals_made += 1
        if e.mood is not None:
            mood.append(e.mood)
        if e.stress is not None:
            stress.append(e.stress)
        if e.workload_pressure is not None:
            workload.append(e.workload_pressure)
        if e.job_satisfaction is not None:
            sat.append(e.job_satisfaction)
        if e.energy is not None:
            energy.append(e.energy)
        out.by_type[e.entry_type] = (
            out.by_type.get(e.entry_type, 0) + 1)
        out.by_status[e.status] = (
            out.by_status.get(e.status, 0) + 1)
        if e.action_type:
            out.by_action[e.action_type] = (
                out.by_action.get(e.action_type, 0) + 1)
        for flag in e.concern_flag_list:
            out.by_concern_flag[flag] = (
                out.by_concern_flag.get(flag, 0) + 1)
    out.distinct_staff = len(staff)
    if mood:
        out.average_mood = round(sum(mood) / len(mood), 2)
    if stress:
        out.average_stress = round(sum(stress) / len(stress), 2)
    if workload:
        out.average_workload = round(
            sum(workload) / len(workload), 2)
    if sat:
        out.average_satisfaction = round(sum(sat) / len(sat), 2)
    if energy:
        out.average_energy = round(sum(energy) / len(energy), 2)
    return out


__all__ = [
    "ENTRY_TYPES", "DEFAULT_ENTRY_TYPE",
    "CONCERN_FLAGS",
    "LIKERTS", "likert_label",
    "ACTION_TYPES",
    "STATUSES", "DEFAULT_STATUS",
    "ValidationError",
    "WellbeingEntry", "WellbeingSummary",
    "init_db",
    "create_entry", "update_entry", "delete_entry",
    "get_entry", "list_entries", "entries_for_staff",
    "set_action_plan", "complete_follow_up",
    "resolve", "close_entry", "set_status",
    "summary",
]
