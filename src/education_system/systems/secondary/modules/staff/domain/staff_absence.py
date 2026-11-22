"""Staff absence: the HR view of the one absence store that makes cover.

**One store.** Every absence is a row in ``cover_absences``
(:mod:`modules.curriculum.domain.cover`): its dates and periods find the
teacher's lessons and make the cover requests. This module never writes that
table itself - it creates, changes, cancels and deletes absences through
cover's own functions, so cover is made exactly as the Cover screen makes it.
The HR details sit beside it in ``staff_absence_details`` (keyed on
``absence_id``); an absence recorded on the Cover screen simply has no
details yet and is shown with sensible defaults until HR fills them in.

Kept from the old Staff Absence tracker: absence date, expected and actual
return, type, reason, notified on / method / by, certificate type and date,
cover required / source / arranged by / notes, the flags (critical, parents
informed, SLT informed, return-to-work required), the return-to-work meeting
and who held it, days lost, status (Reported, Confirmed, Active, Returned,
Closed, Cancelled) and notes; the old actions (Confirm, Arrange cover, Record
return, Complete RTW, Close, Cancel, Change status, Delete) and the old lists
(active today, open, critical, cover outstanding, return overdue, RTW
overdue) and summary.

New:

* **Types** from the HR list (sickness, medical appointment, compassionate,
  dependant care, training / CPD, school business, jury service, maternity /
  paternity, unpaid ...) with paid / unpaid, self-certificate or fit note
  (with its dates) and the return-to-work interview notes.
* **Requests.** Staff ask for planned absence (:func:`request_absence`);
  :data:`STAFF_ABSENCE_EDITORS` approve or decline it. Approving records the
  absence (and so its cover). Staff report their own sickness with
  :func:`report_sickness`. Both are for the staff portal (My Day).
* **Sickness record** per person over a rolling 12 months: episodes, days,
  the Bradford factor (S x S x D) and the trigger points (3 episodes, 8 days
  or a Bradford score - changeable in the settings).
* Return-to-work interviews outstanding, fit notes needed, a calendar by
  date, reports by type / department / month / person, and CSV export.

**Privacy.** The reason text, certificates and return-to-work notes are only
for HR and the person themselves; the cover screen sees only the reason
category. The activity log gets ids and usernames, never reasons or health
details.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import cover as CV  # registers the FK target
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
from education_system.systems.secondary.modules.staff.domain import staff_directory as SD
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import (
    STAFF_ABSENCE_EDITORS,
    STAFF_ROLES,
    Principal,
)
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

SICKNESS = "Sickness"
LONG_SICKNESS = "Sickness — Long Term"
ABSENCE_TYPES: tuple[str, ...] = (
    SICKNESS, LONG_SICKNESS, "Medical Appointment", "Hospital Appointment", "Bereavement",
    "Compassionate", "Dependant Care", "Domestic Emergency", "Childcare Emergency",
    "Training / CPD", "School Business", "Jury Service", "Public Duty", "Maternity",
    "Paternity", "Shared Parental / Adoption", "Unpaid Leave", "Strike", "Bad Weather",
    "Travel Disruption", "Other")
DEFAULT_ABSENCE_TYPE = SICKNESS
SICKNESS_TYPES = frozenset({SICKNESS, LONG_SICKNESS})
#: Types recorded over long spans (cover may run for up to cover.MAX_LONG_ABSENCE_DAYS).
LONG_TERM_TYPES = frozenset({LONG_SICKNESS, "Maternity", "Paternity",
                             "Shared Parental / Adoption"})
UNPAID_BY_DEFAULT = frozenset({"Unpaid Leave", "Strike"})
#: Absence type -> the reason category the cover screen shows (never health details).
_COVER_REASON = {SICKNESS: "Illness", LONG_SICKNESS: "Illness",
                 "Medical Appointment": "Illness", "Hospital Appointment": "Illness",
                 "Training / CPD": "Training / CPD", "School Business": "Meeting",
                 "Bereavement": "Personal / family", "Compassionate": "Personal / family",
                 "Dependant Care": "Personal / family",
                 "Domestic Emergency": "Personal / family",
                 "Childcare Emergency": "Personal / family", "Maternity": "Personal / family",
                 "Paternity": "Personal / family",
                 "Shared Parental / Adoption": "Personal / family"}
#: Cover reason -> the type an absence made on the Cover screen is shown as.
_TYPE_FROM_REASON = {"Illness": SICKNESS, "Training / CPD": "Training / CPD",
                     "School trip": "School Business", "Meeting": "School Business",
                     "Exam duty": "School Business", "Personal / family": "Compassionate",
                     "Other": "Other"}

NOTIFICATION_METHODS: tuple[str, ...] = ("Phone Call", "Text", "Email", "In Person",
                                         "Via Manager", "Not Recorded")
DEFAULT_NOTIFICATION_METHOD = "Phone Call"
CERTIFICATE_TYPES: tuple[str, ...] = ("Self-Cert", "Fit Note", "Medical Cert",
                                      "Hospital Letter", "Not Required")
DEFAULT_CERTIFICATE_TYPE = "Self-Cert"
FIT_NOTE_TYPES = frozenset({"Fit Note", "Medical Cert", "Hospital Letter"})
SELF_CERT_DAYS = 7     # calendar days of sickness a self-certificate covers
COVER_SOURCES: tuple[str, ...] = ("Internal", "Supply Agency", "Class Split",
                                  "Cover Supervisor", "Cancelled", "Not Required", "Pending")
DEFAULT_COVER_SOURCE = "Pending"
STATUSES: tuple[str, ...] = ("Reported", "Confirmed", "Active", "Returned", "Closed",
                             "Cancelled")
DEFAULT_STATUS = "Reported"
OPEN = frozenset({"Reported", "Confirmed", "Active"})
REQUEST_STATUSES: tuple[str, ...] = ("Requested", "Approved", "Declined", "Withdrawn")
REPORT_GROUPS: tuple[str, ...] = ("type", "department", "month", "person")
DEFAULT_SETTINGS = {"trigger_episodes": 3, "trigger_days": 8, "bradford_trigger": 200,
                    "rtw_overdue_days": 7}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS staff_absence_requests (
    request_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_name      TEXT NOT NULL,
    staff_username  TEXT,
    start_date      TEXT NOT NULL,
    end_date        TEXT NOT NULL,
    from_period     INTEGER,
    to_period       INTEGER,
    absence_type    TEXT NOT NULL,
    paid            INTEGER NOT NULL DEFAULT 1,
    reason          TEXT,
    status          TEXT NOT NULL DEFAULT 'Requested'
                    CHECK (status IN ('Requested', 'Approved', 'Declined', 'Withdrawn')),
    requested_by    TEXT,
    requested_at    TEXT NOT NULL DEFAULT (datetime('now')),
    decided_by      TEXT,
    decided_at      TEXT,
    decision_note   TEXT,
    absence_id      INTEGER REFERENCES cover_absences (absence_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_staff_absence_requests_status
    ON staff_absence_requests (status, start_date);
CREATE TABLE IF NOT EXISTS staff_absence_details (
    absence_id          INTEGER PRIMARY KEY
                        REFERENCES cover_absences (absence_id) ON DELETE CASCADE,
    absence_type        TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'Reported' CHECK (status IN
                        ('Reported', 'Confirmed', 'Active', 'Returned', 'Closed', 'Cancelled')),
    paid                INTEGER NOT NULL DEFAULT 1,
    reason              TEXT,
    notified_on         TEXT,
    notification_method TEXT NOT NULL DEFAULT 'Phone Call',
    notified_by         TEXT,
    certificate_type    TEXT NOT NULL DEFAULT 'Self-Cert',
    cert_received_on    TEXT,
    fit_note_from       TEXT,
    fit_note_to         TEXT,
    expected_return     TEXT,
    actual_return       TEXT,
    cover_required      INTEGER NOT NULL DEFAULT 1,
    cover_source        TEXT NOT NULL DEFAULT 'Pending',
    cover_arranged_by   TEXT,
    cover_notes         TEXT,
    critical            INTEGER NOT NULL DEFAULT 0,
    parents_informed    INTEGER NOT NULL DEFAULT 0,
    slt_informed        INTEGER NOT NULL DEFAULT 0,
    rtw_required        INTEGER NOT NULL DEFAULT 0,
    rtw_meeting_on      TEXT,
    rtw_completed_by    TEXT,
    rtw_notes           TEXT,
    days_lost           REAL CHECK (days_lost IS NULL OR days_lost >= 0),
    request_id          INTEGER REFERENCES staff_absence_requests (request_id)
                        ON DELETE SET NULL,
    approved_by         TEXT,
    approved_at         TEXT,
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    created_by          TEXT,
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by          TEXT
);
CREATE TABLE IF NOT EXISTS staff_absence_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS staff_absence_audit (
    audit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    absence_id INTEGER,
    request_id INTEGER,
    action     TEXT NOT NULL,
    actor      TEXT NOT NULL,
    detail     TEXT,
    at         TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("staff_absence", _SCHEMA)

# A staff record with these can't be deleted (Staff Directory marks them as left).
SD.register_login_reference("cover_absences", "teacher_username", "absence(s)")
SD.register_login_reference("staff_absence_requests", "staff_username", "absence request(s)")


# ── Records ──────────────────────────────────────────────────────────

DETAIL_FIELDS = ("absence_type", "status", "paid", "reason", "notified_on",
                 "notification_method", "notified_by", "certificate_type", "cert_received_on",
                 "fit_note_from", "fit_note_to", "expected_return", "actual_return",
                 "cover_required", "cover_source", "cover_arranged_by", "cover_notes",
                 "critical", "parents_informed", "slt_informed", "rtw_required",
                 "rtw_meeting_on", "rtw_completed_by", "rtw_notes", "days_lost", "notes")
_BOOLS = ("paid", "cover_required", "critical", "parents_informed", "slt_informed",
          "rtw_required")
_DATES = {"notified_on": "Notified on", "cert_received_on": "Certificate received",
          "fit_note_from": "Fit note from", "fit_note_to": "Fit note to",
          "expected_return": "Expected return", "actual_return": "Actual return",
          "rtw_meeting_on": "RTW meeting on"}
#: Fields that live on the cover absence (changing them moves the cover).
COVER_FIELDS = ("staff_name", "staff_username", "start_date", "end_date", "from_period",
                "to_period")


@dataclass(frozen=True)
class Record:
    absence_id: int
    staff_name: str
    staff_username: str | None
    start_date: str
    end_date: str
    from_period: int | None
    to_period: int | None
    cover_reason: str
    cover_status: str
    has_details: bool
    absence_type: str
    status: str
    paid: bool
    reason: str | None
    notified_on: str | None
    notification_method: str
    notified_by: str | None
    certificate_type: str
    cert_received_on: str | None
    fit_note_from: str | None
    fit_note_to: str | None
    expected_return: str | None
    actual_return: str | None
    cover_required: bool
    cover_source: str
    cover_arranged_by: str | None
    cover_notes: str | None
    critical: bool
    parents_informed: bool
    slt_informed: bool
    rtw_required: bool
    rtw_meeting_on: str | None
    rtw_completed_by: str | None
    rtw_notes: str | None
    days_lost: float | None
    request_id: int | None
    approved_by: str | None
    approved_at: str | None
    notes: str | None
    created_at: str
    created_by: str | None
    cover_pending: int = 0
    cover_total: int = 0

    # the old names
    @property
    def absence_date(self) -> str:
        return self.start_date

    @property
    def staff_id(self) -> str:
        return self.staff_username or self.staff_name

    @property
    def person_key(self) -> str:
        return person_key(self.staff_name, self.staff_username)

    @property
    def is_sickness(self) -> bool:
        return self.absence_type in SICKNESS_TYPES

    @property
    def is_open(self) -> bool:
        return self.status in OPEN

    @property
    def is_active(self) -> bool:
        return self.status == "Active"

    @property
    def partial_day(self) -> bool:
        return self.start_date == self.end_date and (self.from_period is not None or
                                                     self.to_period is not None)

    @property
    def periods_label(self) -> str:
        if self.from_period is None and self.to_period is None:
            return "all day"
        return f"P{self.from_period or 1}-P{self.to_period or len(TT.periods())}"

    @property
    def dates_label(self) -> str:
        return self.start_date if self.start_date == self.end_date else \
            f"{self.start_date} to {self.end_date}"

    @property
    def days(self) -> float:
        """Working days lost: the recorded figure, else weekdays in the dates."""
        if self.days_lost is not None:
            return float(self.days_lost)
        return working_days(self.start_date, self.end_date, partial=self.partial_day)

    @property
    def cover_outstanding(self) -> bool:
        if not self.is_open or not self.cover_required:
            return False
        return self.cover_pending > 0 or (self.cover_total == 0 and
                                          self.cover_source == "Pending")

    @property
    def rtw_outstanding(self) -> bool:
        return (self.rtw_required and not self.rtw_meeting_on and self.status != "Cancelled"
                and bool(self.actual_return or self.status in ("Returned", "Closed")))

    @property
    def rtw_overdue(self) -> bool:
        if not self.rtw_outstanding or not self.actual_return:
            return False
        limit = int(settings()["rtw_overdue_days"])  # cached per database
        return (_today() - _dt.date.fromisoformat(self.actual_return)).days > limit

    @property
    def return_overdue(self) -> bool:
        return bool(self.is_open and self.expected_return and not self.actual_return
                    and self.expected_return < _today().isoformat())

    @property
    def calendar_days(self) -> int:
        return (_dt.date.fromisoformat(self.end_date)
                - _dt.date.fromisoformat(self.start_date)).days + 1

    @property
    def fit_note_needed(self) -> bool:
        """Sickness over 7 calendar days needs a fit note (not a self-certificate)."""
        return (self.is_sickness and self.status != "Cancelled"
                and self.calendar_days > SELF_CERT_DAYS
                and not (self.certificate_type in FIT_NOTE_TYPES and self.cert_received_on))

    @property
    def flags(self) -> list[str]:
        out = []
        if self.critical and self.is_open:
            out.append("CRIT")
        if self.cover_outstanding:
            out.append("COVER")
        if self.return_overdue:
            out.append("RET")
        if self.rtw_overdue:
            out.append("RTW")
        elif self.rtw_outstanding:
            out.append("rtw")
        if self.fit_note_needed:
            out.append("FIT")
        return out


@dataclass(frozen=True)
class Request:
    request_id: int
    staff_name: str
    staff_username: str | None
    start_date: str
    end_date: str
    from_period: int | None
    to_period: int | None
    absence_type: str
    paid: bool
    reason: str | None
    status: str
    requested_by: str | None
    requested_at: str
    decided_by: str | None
    decided_at: str | None
    decision_note: str | None
    absence_id: int | None

    @property
    def dates_label(self) -> str:
        return self.start_date if self.start_date == self.end_date else \
            f"{self.start_date} to {self.end_date}"

    @property
    def days(self) -> float:
        return working_days(self.start_date, self.end_date,
                            partial=self.start_date == self.end_date and (
                                self.from_period is not None or self.to_period is not None))


_SELECT = """
SELECT a.absence_id, a.teacher_name AS staff_name, a.teacher_username AS staff_username,
       a.start_date, a.end_date, a.from_period, a.to_period, a.reason AS cover_reason,
       a.status AS cover_status, a.created_at AS a_created_at, a.created_by AS a_created_by,
       d.*, d.absence_id AS detail_id
FROM cover_absences a LEFT JOIN staff_absence_details d ON d.absence_id = a.absence_id
"""


def _defaults(cover_reason: str, cancelled: bool) -> dict[str, Any]:
    t = _TYPE_FROM_REASON.get(cover_reason, "Other")
    sick = t in SICKNESS_TYPES
    return {"absence_type": t, "status": "Cancelled" if cancelled else "Active", "paid": True,
            "notification_method": "Not Recorded",
            "certificate_type": DEFAULT_CERTIFICATE_TYPE if sick else "Not Required",
            "cover_required": True, "cover_source": DEFAULT_COVER_SOURCE,
            "rtw_required": sick}


def _row(r, cover: dict[int, dict[str, int]] | None = None) -> Record:
    has = r["detail_id"] is not None
    vals: dict[str, Any] = {k: r[k] for k in DETAIL_FIELDS}
    if not has:
        vals = {k: None for k in DETAIL_FIELDS}
        vals.update({k: False for k in _BOOLS})
        vals.update(_defaults(r["cover_reason"], r["cover_status"] == "cancelled"))
    elif r["cover_status"] == "cancelled":
        vals["status"] = "Cancelled"
    for k in _BOOLS:
        vals[k] = bool(vals[k])
    counts = (cover or {}).get(r["absence_id"], {})
    return Record(absence_id=r["absence_id"], staff_name=r["staff_name"],
                  staff_username=r["staff_username"], start_date=r["start_date"],
                  end_date=r["end_date"], from_period=r["from_period"],
                  to_period=r["to_period"], cover_reason=r["cover_reason"],
                  cover_status=r["cover_status"], has_details=has, **vals,
                  request_id=r["request_id"] if has else None,
                  approved_by=r["approved_by"] if has else None,
                  approved_at=r["approved_at"] if has else None,
                  created_at=r["a_created_at"], created_by=r["a_created_by"],
                  cover_pending=counts.get("Pending", 0),
                  cover_total=sum(n for s, n in counts.items() if s != "Cancelled"))


def _request_row(r) -> Request:
    out = {k: r[k] for k in Request.__dataclass_fields__}
    out["paid"] = bool(out["paid"])
    return Request(**out)


# ── Helpers ──────────────────────────────────────────────────────────

def person_key(name: str | None, username: str | None) -> str:
    return (username or "").strip().lower() or f"name:{(name or '').strip().lower()}"


def working_days(start: str | _dt.date, end: str | _dt.date, *, partial: bool = False,
                 lo: _dt.date | None = None, hi: _dt.date | None = None) -> float:
    """Weekdays from *start* to *end* (clipped to *lo*..*hi*); a part day is 0.5."""
    s = start if isinstance(start, _dt.date) else _dt.date.fromisoformat(str(start))
    e = end if isinstance(end, _dt.date) else _dt.date.fromisoformat(str(end))
    s, e = max(s, lo) if lo else s, min(e, hi) if hi else e
    if e < s:
        return 0.0
    n = sum(1 for i in range((e - s).days + 1) if (s + _dt.timedelta(days=i)).weekday() < 5)
    return 0.5 if partial and n else float(n)


def is_editor(actor: Principal) -> bool:
    return actor.role in STAFF_ABSENCE_EDITORS


def _same(a: str | None, b: str | None) -> bool:
    return bool(a) and bool(b) and a.strip().lower() == b.strip().lower()


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"staff_absence.{action}", target=target, outcome="denied",
                        principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, target, "Only school staff can use staff absence.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        _deny(actor, action, target, "Only HR (the staff absence lead) can do that.")


def _mine(actor: Principal, username: str | None) -> bool:
    return _same(actor.username, username)


def _audit(conn, action: str, actor: Principal, *, absence_id: int | None = None,
           request_id: int | None = None, **detail: Any) -> None:
    conn.execute("INSERT INTO staff_absence_audit (absence_id, request_id, action, actor, "
                 "detail) VALUES (?, ?, ?, ?, ?)",
                 (absence_id, request_id, action, actor.username or "unknown",
                  json.dumps(detail, default=str, sort_keys=True) if detail else None))


def history(absence_id: int | None = None, *, request_id: int | None = None,
            limit: int = 200) -> list[dict[str, Any]]:
    """HR changes (newest first), with cover's own audit for the absence."""
    sql, params = "SELECT * FROM staff_absence_audit", []
    if absence_id is not None:
        sql += " WHERE absence_id = ?"
        params.append(int(absence_id))
    elif request_id is not None:
        sql += " WHERE request_id = ?"
        params.append(int(request_id))
    with database.connect() as conn:
        out = [{"at": r["at"], "actor": r["actor"], "action": r["action"],
                "detail": json.loads(r["detail"]) if r["detail"] else {}}
               for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                     (*params, int(limit)))]
    if absence_id is not None:
        out += [{**h, "action": f"cover.{h['action']}"}
                for h in CV.history(absence_id=absence_id, limit=limit)]
        out.sort(key=lambda h: h["at"], reverse=True)
    return out


def _text(value: Any, limit: int) -> str | None:
    return (str(value).strip()[:limit] or None) if value not in (None, "") else None


def _date(value: Any, label: str, problems: list[str]) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, _dt.date):
        return value.isoformat()
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
        problems.append(f"{label} must be one of: {', '.join(options)}")
        return default
    return hit


def _prev_weekday(d: _dt.date) -> _dt.date:
    d -= _dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= _dt.timedelta(days=1)
    return d


# ── Staff ────────────────────────────────────────────────────────────

def staff_choices() -> list[dict[str, Any]]:
    """Staff logins, then names on recorded absences with no login:
    [{username, name, email}] by name."""
    people = {t["username"].lower(): {"username": t["username"],
                                      "name": t["display_name"] or t["username"],
                                      "email": t.get("email")}
              for t in TG.teacher_choices()}
    names = {p["name"].lower() for p in people.values()}
    with database.connect() as conn:
        for (n,) in conn.execute("SELECT DISTINCT teacher_name FROM cover_absences WHERE "
                                 "teacher_username IS NULL OR teacher_username = ''"):
            if n and n.lower() not in names:
                names.add(n.lower())
                people[f"name:{n.lower()}"] = {"username": None, "name": n, "email": None}
    return sorted(people.values(), key=lambda p: p["name"].lower())


def departments() -> dict[str, str]:
    """person key -> department: the person's department in the Staff
    Directory (their primary one), else the subject department (else subject)
    of the teaching groups they teach most this year."""
    counts: dict[str, Counter] = {}
    try:
        groups = TG.info(TG.list_groups())
    except Exception:  # noqa: BLE001 - no timetable data yet: only the directory
        groups = []
    for gi in groups:
        g = gi.group
        if not (g.teacher_username or g.teacher_name):
            continue
        dept = gi.subject.department or gi.subject.name
        counts.setdefault(person_key(g.teacher_name, g.teacher_username), Counter())[dept] += 1
    out = {k: c.most_common(1)[0][0] for k, c in counts.items()}
    out.update(_directory_departments())
    return out


def _directory_departments() -> dict[str, str]:
    """person key -> department from the Staff Directory's current
    memberships (a primary membership wins)."""
    from education_system.systems.secondary.modules.staff.domain import departments as DEP
    try:
        staff = {m.staff_id: m for m in SD.list_staff()}
        out: dict[str, str] = {}
        primary: set[str] = set()
        for d in DEP.list_departments(active_only=True):
            for mem in DEP.list_memberships(d.department_id, current_only=True):
                m = staff.get(mem.staff_id)
                if m is None:
                    continue
                key = person_key(m.full_name, m.username)
                if key not in primary:
                    out[key] = d.name
                if mem.is_primary:
                    primary.add(key)
        return out
    except Exception:  # noqa: BLE001 - no directory yet: the teaching-group guess stands
        return {}


def department_of(rec: Record, depts: dict[str, str] | None = None) -> str:
    d = depts if depts is not None else departments()
    return d.get(rec.person_key) or "(no department)"


# ── Settings ─────────────────────────────────────────────────────────

_settings_cache: dict[str, dict[str, int]] = {}


def settings() -> dict[str, int]:
    key = str(database.db_path())
    if key in _settings_cache:
        return dict(_settings_cache[key])
    out = dict(DEFAULT_SETTINGS)
    with database.connect() as conn:
        for k, v in conn.execute("SELECT key, value FROM staff_absence_settings"):
            if k in out and str(v).isdigit():
                out[k] = int(v)
    _settings_cache[key] = out
    return dict(out)


def set_settings(changes: dict[str, Any], *, actor: Principal) -> dict[str, int]:
    """Trigger points (episodes, days, Bradford score) and when an RTW is overdue."""
    _require_editor(actor, "settings")
    limits = {"trigger_episodes": (1, 50), "trigger_days": (1, 365),
              "bradford_trigger": (1, 100000), "rtw_overdue_days": (0, 90)}
    problems, clean = [], {}
    for k, v in changes.items():
        if k not in limits:
            problems.append(f"Unknown setting {k}")
            continue
        if v in (None, ""):
            continue
        lo, hi = limits[k]
        try:
            n = int(str(v).strip())
        except ValueError:
            n = lo - 1
        if not lo <= n <= hi:
            problems.append(f"{k.replace('_', ' ').capitalize()} must be from {lo} to {hi}")
        clean[k] = n
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        for k, n in clean.items():
            conn.execute("INSERT INTO staff_absence_settings (key, value) VALUES (?, ?) ON "
                         "CONFLICT (key) DO UPDATE SET value = excluded.value", (k, str(n)))
        _audit(conn, "settings", actor, **clean)
    _settings_cache.pop(str(database.db_path()), None)
    activity_log.record("staff_absence.settings", principal=actor, fields=sorted(clean))
    return settings()


# ── Reading ──────────────────────────────────────────────────────────

def _fetch(where: str = "", params: tuple = ()) -> list[Record]:
    with database.connect() as conn:
        rows = conn.execute(_SELECT + where + " ORDER BY a.start_date DESC, a.absence_id DESC",
                            params).fetchall()
    cover = CV.cover_by_absence([r["absence_id"] for r in rows]) if rows else {}
    return [_row(r, cover) for r in rows]


def get(absence_id: int) -> Record:
    rows = _fetch(" WHERE a.absence_id = ?", (int(absence_id),))
    if not rows:
        raise NotFound(f"No absence #{absence_id}")
    return rows[0]


def get_absence(absence_id: int, *, actor: Principal) -> Record:
    """One absence, for HR or the person themselves."""
    _require_staff(actor, "view", f"absence:{absence_id}")
    rec = get(absence_id)
    if not is_editor(actor) and not _mine(actor, rec.staff_username):
        _deny(actor, "view", f"absence:{absence_id}", "You can see only your own absences.")
    return rec


def list_absences(*, actor: Principal, staff: str | None = None,
                  absence_type: str | None = None, status: str | None = None,
                  cover_source: str | None = None, department: str | None = None,
                  open_only: bool = False, active_today: bool = False,
                  critical_only: bool = False, cover_outstanding: bool = False,
                  rtw_overdue: bool = False, rtw_outstanding: bool = False,
                  return_overdue: bool = False, fit_note_needed: bool = False,
                  sickness_only: bool = False, include_cancelled: bool = True,
                  date_from: Any = None, date_to: Any = None) -> list[Record]:
    """Absences, newest first. HR sees everyone; other staff only their own.
    The old filters are kept (staff, type, status, cover source, open, active
    today, critical, cover outstanding, RTW overdue, return overdue, dates);
    the dates find absences overlapping them."""
    _require_staff(actor, "list")
    problems: list[str] = []
    where, params = [], []
    lo = _date(date_from, "From", problems)
    hi = _date(date_to, "To", problems)
    if problems:
        raise ValidationError(problems)
    if lo:
        where.append("a.end_date >= ?")
        params.append(lo)
    if hi:
        where.append("a.start_date <= ?")
        params.append(hi)
    if staff:
        where.append("(lower(a.teacher_name) = lower(?) OR lower(a.teacher_username) = "
                     "lower(?))")
        params += [staff.strip()] * 2
    if not is_editor(actor):
        where.append("lower(a.teacher_username) = lower(?)")
        params.append(actor.username or "")
    rows = _fetch(" WHERE " + " AND ".join(where) if where else "", tuple(params))
    today = _today().isoformat()
    depts = departments() if department else {}

    def keep(r: Record) -> bool:
        checks = (
            (absence_type, lambda: r.absence_type == absence_type),
            (status, lambda: r.status == status),
            (cover_source, lambda: r.cover_source == cover_source),
            (department, lambda: department_of(r, depts) == department),
            (open_only, lambda: r.is_open),
            (active_today, lambda: r.is_open and r.start_date <= today <= r.end_date
             and not (r.actual_return and r.actual_return <= today)),
            (critical_only, lambda: r.critical),
            (cover_outstanding, lambda: r.cover_outstanding),
            (rtw_overdue, lambda: r.rtw_overdue), (rtw_outstanding, lambda: r.rtw_outstanding),
            (return_overdue, lambda: r.return_overdue),
            (fit_note_needed, lambda: r.fit_note_needed),
            (sickness_only, lambda: r.is_sickness),
            (not include_cancelled, lambda: r.status != "Cancelled"))
        return all(fn() for flag, fn in checks if flag)
    return [r for r in rows if keep(r)]


def absences_for_staff(staff: str, *, actor: Principal) -> list[Record]:
    return list_absences(actor=actor, staff=staff)


def on_date(day: Any, *, actor: Principal) -> list[Record]:
    """Who is off on *day* (not cancelled; returned staff drop off)."""
    problems: list[str] = []
    d = _date(day or _today(), "Date", problems)
    if problems:
        raise ValidationError(problems)
    return [r for r in list_absences(actor=actor, date_from=d, date_to=d,
                                     include_cancelled=False)
            if not (r.actual_return and r.actual_return <= d)]


def calendar(year: int, month: int, *, actor: Principal) -> dict[str, list[Record]]:
    """{date: [absences that day]} for every day of the month."""
    first = _dt.date(int(year), int(month), 1)
    last = _dt.date(first.year + (first.month == 12), first.month % 12 + 1, 1) - \
        _dt.timedelta(days=1)
    rows = list_absences(actor=actor, date_from=first, date_to=last, include_cancelled=False)
    out: dict[str, list[Record]] = {}
    d = first
    while d <= last:
        iso = d.isoformat()
        out[iso] = [r for r in rows if r.start_date <= iso <= r.end_date
                    and not (r.actual_return and r.actual_return <= iso)]
        d += _dt.timedelta(days=1)
    return out


# ── Cleaning ─────────────────────────────────────────────────────────

def _clean_details(data: dict[str, Any], current: Record | None, problems: list[str]
                   ) -> dict[str, Any]:
    merged = {k: getattr(current, k) for k in DETAIL_FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in DETAIL_FIELDS})
    out: dict[str, Any] = {}
    out["absence_type"] = _choice(merged.get("absence_type"), ABSENCE_TYPES, "Absence type",
                                  problems, DEFAULT_ABSENCE_TYPE)
    sick = out["absence_type"] in SICKNESS_TYPES
    out["status"] = _choice(merged.get("status"), STATUSES, "Status", problems,
                            DEFAULT_STATUS)
    out["notification_method"] = _choice(merged.get("notification_method"),
                                         NOTIFICATION_METHODS, "Notification method",
                                         problems, DEFAULT_NOTIFICATION_METHOD)
    out["certificate_type"] = _choice(merged.get("certificate_type"), CERTIFICATE_TYPES,
                                      "Certificate type", problems,
                                      DEFAULT_CERTIFICATE_TYPE if sick else "Not Required")
    out["cover_source"] = _choice(merged.get("cover_source"), COVER_SOURCES, "Cover source",
                                  problems, DEFAULT_COVER_SOURCE)
    for k, label in _DATES.items():
        out[k] = _date(merged.get(k), label, problems)
    for k in _BOOLS:
        v = merged.get(k)
        if v is None and k == "paid":
            v = out["absence_type"] not in UNPAID_BY_DEFAULT
        elif v is None and k == "cover_required":
            v = True
        elif v is None and k == "rtw_required":
            v = sick
        out[k] = P._as_bool(v, k.replace("_", " ").capitalize(), problems)
    for k, n in (("reason", 1000), ("notified_by", 100), ("cover_arranged_by", 100),
                 ("cover_notes", 1000), ("rtw_completed_by", 100), ("rtw_notes", 2000),
                 ("notes", 2000)):
        out[k] = _text(merged.get(k), n)
    dl = merged.get("days_lost")
    out["days_lost"] = None
    if dl not in (None, ""):
        try:
            out["days_lost"] = round(float(str(dl).strip()), 1)
            if not 0 <= out["days_lost"] <= 400:
                raise ValueError
        except ValueError:
            problems.append("Days lost must be a number from 0 to 400")
            out["days_lost"] = None
    if out["fit_note_from"] and out["fit_note_to"] and out["fit_note_to"] < out["fit_note_from"]:
        problems.append("The fit note ends before it starts")
    if out["rtw_meeting_on"] and out["rtw_meeting_on"] > _today().isoformat():
        problems.append("Record the return-to-work meeting once it has happened")
    if out["rtw_meeting_on"] and not out["rtw_completed_by"]:
        problems.append("Say who held the return-to-work meeting")
    if out["status"] == "Returned" and not out["actual_return"]:
        problems.append("Record the actual return date")
    return out


def _clean_cover(data: dict[str, Any], current: Record | None, problems: list[str]
                 ) -> dict[str, Any]:
    """The cover absence's fields (cover re-checks them when it saves)."""
    merged = {k: getattr(current, k) for k in COVER_FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in COVER_FIELDS})
    s = _date(merged.get("start_date") or (None if current else _today()), "First day",
              problems)
    if s is None and not any(p.startswith("First day") for p in problems):
        problems.append("First day is required")
    e = _date(merged.get("end_date"), "Last day", problems)
    exp = _date(data.get("expected_return") if "expected_return" in data else
                (current.expected_return if current else None), "Expected return", problems)
    if s and not e:
        e = s
        if exp and exp > s:
            e = max(s, _prev_weekday(_dt.date.fromisoformat(exp)).isoformat())
    if s and exp and exp < s:
        problems.append("Expected return can't be before the first day")
    out = {"teacher_name": P._clean_text(merged.get("staff_name"), 100),
           "teacher_username": P._clean_text(merged.get("staff_username"), 100),
           "start_date": s, "end_date": e,
           "from_period": merged.get("from_period") if merged.get("from_period") != "" else None,
           "to_period": merged.get("to_period") if merged.get("to_period") != "" else None}
    if not out["teacher_name"] and not out["teacher_username"]:
        problems.append("Who is away? Choose a member of staff")
    return out


def _upsert_details(conn, absence_id: int, clean: dict[str, Any], actor: Principal,
                    extra: dict[str, Any] | None = None) -> None:
    vals = {**clean, **(extra or {})}
    vals = {k: (int(v) if k in _BOOLS else v) for k, v in vals.items()}
    cols = list(vals)
    conn.execute(
        f"INSERT INTO staff_absence_details (absence_id, {', '.join(cols)}, created_by, "  # nosec B608 - fixed columns
        f"updated_by) VALUES (?, {', '.join('?' * len(cols))}, ?, ?) ON CONFLICT (absence_id) "
        f"DO UPDATE SET {', '.join(f'{c} = excluded.{c}' for c in cols)}, "
        "updated_at = datetime('now'), updated_by = excluded.updated_by",
        (absence_id, *vals.values(), actor.username, actor.username))


# ── Recording ────────────────────────────────────────────────────────

def create_absence(data: dict[str, Any], *, actor: Principal) -> tuple[Record, int]:
    """Record an absence (HR for anyone; staff their own, today or later) and
    make cover for its lessons. Returns (record, lessons covered)."""
    _require_staff(actor, "create")
    problems: list[str] = []
    cover = _clean_cover(data, None, problems)
    details = _clean_details(data, None, problems)
    if not is_editor(actor):
        if not _mine(actor, cover["teacher_username"]):
            problems.append("You can record your own absence; HR records other people's")
        if details["status"] not in ("Reported",):
            details["status"] = "Reported"
    if problems:
        raise ValidationError(problems)
    cover["reason"] = _COVER_REASON.get(details["absence_type"], "Other")
    a, lessons = CV.create_absence(cover, actor=actor,
                                   long_term=details["absence_type"] in LONG_TERM_TYPES)
    try:
        with database.connect() as conn:
            _upsert_details(conn, a.absence_id, details, actor,
                            extra=data.get("_extra") if isinstance(data.get("_extra"), dict)
                            else None)
            _audit(conn, "create", actor, absence_id=a.absence_id,
                   type=details["absence_type"], lessons=lessons)
    except Exception:
        if CV.can_record_any_absence(actor):   # undo: no cover without its HR record
            CV.delete_absence(a.absence_id, actor=actor)
        else:
            CV.cancel_absence(a.absence_id, actor=actor)
        raise
    activity_log.record("staff_absence.create", target=f"absence:{a.absence_id}",
                        principal=actor, lessons=lessons)
    return get(a.absence_id), lessons


def update_absence(absence_id: int, changes: dict[str, Any], *, actor: Principal
                   ) -> tuple[Record, int, int]:
    """The old Edit: HR details and the dates (cover follows the dates).
    Returns (record, cover added, cover cancelled)."""
    cur = get(absence_id)
    _require_editor(actor, "update", f"absence:{absence_id}")
    problems: list[str] = []
    unknown = set(changes) - set(DETAIL_FIELDS) - set(COVER_FIELDS)
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    details = _clean_details(changes, cur, problems)
    cover = _clean_cover(changes, cur, problems)
    if cur.status == "Cancelled" and details["status"] != "Cancelled":
        problems.append("This absence was cancelled - record a new one")
    if problems:
        raise ValidationError(problems)
    if details["status"] == "Cancelled" and cur.status != "Cancelled":
        cancel(absence_id, actor=actor)
        cur = get(absence_id)
    added = cancelled = 0
    cover_changes = {k: v for k, v in cover.items()
                     if v != getattr(cur, {"teacher_name": "staff_name",
                                           "teacher_username": "staff_username"}.get(k, k))}
    reason = _COVER_REASON.get(details["absence_type"], "Other")
    if reason != cur.cover_reason:
        cover_changes["reason"] = reason
    if cover_changes and cur.cover_status == "active":
        _a, added, cancelled = CV.update_absence(
            absence_id, cover_changes, actor=actor,
            long_term=details["absence_type"] in LONG_TERM_TYPES)
    changed = sorted(k for k in DETAIL_FIELDS if details[k] != getattr(cur, k))
    if changed or not cur.has_details:
        with database.connect() as conn:
            _upsert_details(conn, absence_id, details, actor)
            _audit(conn, "update", actor, absence_id=absence_id, fields=changed,
                   cover=sorted(cover_changes))
    activity_log.record("staff_absence.update", target=f"absence:{absence_id}",
                        principal=actor, fields=changed, added=added, cancelled=cancelled)
    return get(absence_id), added, cancelled


def _set(absence_id: int, actor: Principal, action: str, **values: Any) -> Record:
    """Change some HR fields (through the full checks)."""
    rec, _a, _c = update_absence(absence_id, values, actor=actor)
    with database.connect() as conn:
        _audit(conn, action, actor, absence_id=absence_id)
    return rec


def report_sickness(*, actor: Principal, start_date: Any = None, expected_return: Any = None,
                    staff_username: str | None = None, staff_name: str | None = None,
                    reason: str | None = None,
                    notification_method: str | None = None) -> tuple[Record, int]:
    """Staff report their own sickness (from today); HR can report anyone's.
    Cover is made for today (to the day before the expected return)."""
    who = staff_username if (staff_username or staff_name) and is_editor(actor) \
        else actor.username
    data = {"staff_username": who, "staff_name": staff_name if is_editor(actor) else None,
            "start_date": start_date or _today(), "expected_return": expected_return,
            "absence_type": SICKNESS, "status": "Reported", "reason": reason,
            "notified_on": _today(), "notified_by": actor.username,
            "notification_method": notification_method or (
                "Not Recorded" if is_editor(actor) else "Email"),
            "certificate_type": "Self-Cert", "rtw_required": True}
    return create_absence(data, actor=actor)


def confirm(absence_id: int, *, actor: Principal) -> Record:
    """The old Confirm: Reported -> Active, otherwise Confirmed."""
    cur = get(absence_id)
    return _set(absence_id, actor, "confirm",
                status="Active" if cur.status == "Reported" else "Confirmed")


def arrange_cover(absence_id: int, *, source: str, actor: Principal,
                  arranged_by: str | None = None, notes: str | None = None) -> Record:
    """The old Arrange cover (how it's covered; the lessons are on the Cover screen)."""
    vals: dict[str, Any] = {"cover_source": source}
    if source not in COVER_SOURCES:
        raise ValidationError([f"Cover source must be one of: {', '.join(COVER_SOURCES)}"])
    if arranged_by:
        vals["cover_arranged_by"] = arranged_by
    if notes:
        vals["cover_notes"] = notes
    return _set(absence_id, actor, "arrange_cover", **vals)


def extend(absence_id: int, *, actor: Principal, last_day: Any = None,
           expected_return: Any = None) -> tuple[Record, int, int]:
    """Still off: move the last day (cover is added for the extra lessons)."""
    problems: list[str] = []
    exp = _date(expected_return, "Expected return", problems)
    last = _date(last_day, "Last day", problems)
    if not exp and not last:
        problems.append("Give the new last day or the expected return")
    if problems:
        raise ValidationError(problems)
    cur = get(absence_id)
    if not last:
        last = max(cur.start_date, _prev_weekday(_dt.date.fromisoformat(exp)).isoformat())
    changes: dict[str, Any] = {"end_date": last}
    if exp:
        changes["expected_return"] = exp
    return update_absence(absence_id, changes, actor=actor)


def record_return(absence_id: int, *, actor: Principal, returned_on: Any = None,
                  days_lost: Any = None) -> tuple[Record, int, int]:
    """The old Record return. The last day moves to the day before they came
    back (cover after it is cancelled; added if they were off longer)."""
    cur = get(absence_id)
    problems: list[str] = []
    back = _date(returned_on, "Returned on", problems) or _today().isoformat()
    if problems:
        raise ValidationError(problems)
    if back < cur.start_date:
        raise ValidationError(["They can't come back before the absence started"])
    last = cur.end_date if cur.partial_day else max(
        cur.start_date, (_dt.date.fromisoformat(back) - _dt.timedelta(days=1)).isoformat())
    changes: dict[str, Any] = {"actual_return": back, "status": "Returned", "end_date": last}
    if days_lost not in (None, ""):
        changes["days_lost"] = days_lost
    rec, added, cancelled = update_absence(absence_id, changes, actor=actor)
    with database.connect() as conn:
        _audit(conn, "return", actor, absence_id=absence_id, added=added, cancelled=cancelled)
    return rec, added, cancelled


def complete_rtw(absence_id: int, *, completed_by: str, actor: Principal,
                 meeting_on: Any = None, notes: str | None = None) -> Record:
    """The old Complete RTW, with the interview notes."""
    _require_editor(actor, "rtw", f"absence:{absence_id}")
    problems: list[str] = []
    if not (completed_by or "").strip():
        problems.append("Completed-by is required")
    when = _date(meeting_on, "Meeting on", problems) or _today().isoformat()
    cur = get(absence_id)
    if when < cur.start_date:
        problems.append("The meeting can't be before the absence started")
    if problems:
        raise ValidationError(problems)
    if not cur.actual_return:      # they are back if the meeting happened
        record_return(absence_id, actor=actor, returned_on=when)
    vals: dict[str, Any] = {"rtw_completed_by": completed_by, "rtw_meeting_on": when,
                            "rtw_required": True}
    if notes:
        vals["rtw_notes"] = notes
    return _set(absence_id, actor, "rtw", **vals)


def record_certificate(absence_id: int, *, actor: Principal, certificate_type: str,
                       received_on: Any = None, fit_from: Any = None,
                       fit_to: Any = None) -> Record:
    """Self-certificate or fit note received (with the fit note's dates)."""
    return _set(absence_id, actor, "certificate", certificate_type=certificate_type,
                cert_received_on=received_on or _today().isoformat(),
                fit_note_from=fit_from, fit_note_to=fit_to)


def close(absence_id: int, *, actor: Principal) -> Record:
    """The old Close (a sickness absence needs its return-to-work interview first)."""
    cur = get(absence_id)
    if cur.status == "Cancelled":
        raise ValidationError(["This absence was cancelled"])
    if cur.rtw_required and not cur.rtw_meeting_on and cur.is_sickness:
        raise ValidationError(["Hold the return-to-work interview first (Complete RTW)"])
    vals: dict[str, Any] = {"status": "Closed"}
    if not cur.actual_return:
        vals["actual_return"] = (_dt.date.fromisoformat(cur.end_date)
                                 + _dt.timedelta(days=1)).isoformat()
    return _set(absence_id, actor, "close", **vals)


def cancel(absence_id: int, *, actor: Principal) -> Record:
    """The old Cancel: the absence and its open cover are cancelled. Staff can
    cancel their own."""
    cur = get(absence_id)
    _require_staff(actor, "cancel", f"absence:{absence_id}")
    if not is_editor(actor) and not _mine(actor, cur.staff_username):
        _deny(actor, "cancel", f"absence:{absence_id}",
              "Only HR can cancel someone else's absence.")
    if cur.status == "Cancelled":
        raise ValidationError(["This absence is already cancelled"])
    n = CV.cancel_absence(absence_id, actor=actor) if cur.cover_status == "active" else 0
    details = _clean_details({"status": "Cancelled"}, cur, [])
    with database.connect() as conn:
        _upsert_details(conn, absence_id, details, actor)
        _audit(conn, "cancel", actor, absence_id=absence_id, covers=n)
    activity_log.record("staff_absence.cancel", target=f"absence:{absence_id}",
                        principal=actor, covers=n)
    return get(absence_id)


def set_status(absence_id: int, new_status: str, *, actor: Principal) -> Record:
    """The old Change status."""
    probs: list[str] = []
    st = _choice(new_status, STATUSES, "Status", probs, None)
    if probs or not st:
        raise ValidationError(probs or ["Choose a status"])
    if st == "Cancelled":
        return cancel(absence_id, actor=actor)
    if st == "Closed":
        return close(absence_id, actor=actor)
    if st == "Returned" and not get(absence_id).actual_return:
        return record_return(absence_id, actor=actor)[0]
    return _set(absence_id, actor, "status", status=st)


def delete(absence_id: int, *, actor: Principal) -> int:
    """The old Delete: only an absence recorded in error, whose cover never
    happened. Returns how many cover requests went with it."""
    cur = get(absence_id)
    _require_editor(actor, "delete", f"absence:{absence_id}")
    with database.connect() as conn:
        _audit(conn, "delete", actor, absence_id=absence_id, start=cur.start_date,
               end=cur.end_date)
    n = CV.delete_absence(absence_id, actor=actor)
    activity_log.record("staff_absence.delete", target=f"absence:{absence_id}",
                        principal=actor, covers=n)
    return n


# ── Requests for planned absence ─────────────────────────────────────

def get_request(request_id: int) -> Request:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM staff_absence_requests WHERE request_id = ?",
                         (int(request_id),)).fetchone()
    if r is None:
        raise NotFound(f"No request #{request_id}")
    return _request_row(r)


def list_requests(*, actor: Principal, status: str | None = None, staff: str | None = None
                  ) -> list[Request]:
    """Requests, waiting ones first. Staff see their own."""
    _require_staff(actor, "requests")
    where, params = [], []
    if status:
        where.append("status = ?")
        params.append(status)
    if staff:
        where.append("(lower(staff_name) = lower(?) OR lower(staff_username) = lower(?))")
        params += [staff.strip()] * 2
    if not is_editor(actor):
        where.append("lower(staff_username) = lower(?)")
        params.append(actor.username or "")
    sql = "SELECT * FROM staff_absence_requests" + (" WHERE " + " AND ".join(where)
                                                   if where else "")
    with database.connect() as conn:
        return [_request_row(r) for r in conn.execute(
            sql + " ORDER BY status != 'Requested', start_date DESC, request_id DESC", params)]


def request_absence(data: dict[str, Any], *, actor: Principal) -> Request:
    """Staff ask for planned absence (any type but sickness); HR may ask on
    someone's behalf. Nothing is covered until it is approved."""
    _require_staff(actor, "request")
    problems: list[str] = []
    username = P._clean_text(data.get("staff_username"), 100)
    name = P._clean_text(data.get("staff_name"), 100)
    if not is_editor(actor) or not (username or name):
        username = actor.username
    if username:
        login = next((t for t in TG.teacher_choices() if _same(t["username"], username)), None)
        if login is None:
            problems.append(f"'{username}' isn't a secondary staff login")
        else:
            username, name = login["username"], name or login["display_name"]
    if not name:
        problems.append("Who is the request for?")
    s = _date(data.get("start_date"), "First day", problems)
    e = _date(data.get("end_date"), "Last day", problems) or s
    if s is None and not any(p.startswith("First day") for p in problems):
        problems.append("First day is required")
    if s and e and e < s:
        problems.append("The last day is before the first day")
    if s and e and (_dt.date.fromisoformat(e) - _dt.date.fromisoformat(s)).days > \
            CV.MAX_LONG_ABSENCE_DAYS:
        problems.append(f"At most {CV.MAX_LONG_ABSENCE_DAYS} days at a time")
    if s and not is_editor(actor) and s < _today().isoformat():
        problems.append("Ask before the day - HR records past absence")
    n = len(TT.periods()) or 10
    periods = []
    for key, label in (("from_period", "From period"), ("to_period", "To period")):
        v = data.get(key)
        if v in (None, ""):
            periods.append(None)
            continue
        try:
            p = int(str(v).strip())
            if not 1 <= p <= n:
                raise ValueError
            periods.append(p)
        except ValueError:
            problems.append(f"{label} must be from 1 to {n}")
            periods.append(None)
    if periods[0] and periods[1] and periods[1] < periods[0]:
        problems.append("The last period is before the first")
    atype = _choice(data.get("absence_type"), ABSENCE_TYPES, "Absence type", problems, None)
    if not atype:
        problems.append("Choose the type of absence")
    elif atype in SICKNESS_TYPES:
        problems.append("Sickness isn't requested - report it on the day")
    paid = data.get("paid")
    paid = P._as_bool(paid, "Paid", problems) if paid not in (None, "") else \
        atype not in UNPAID_BY_DEFAULT
    if not problems and s and e:
        with database.connect() as conn:
            clash = conn.execute(
                "SELECT request_id FROM staff_absence_requests WHERE status = 'Requested' AND "
                "start_date <= ? AND end_date >= ? AND (lower(staff_name) = lower(?) OR "
                "lower(staff_username) = lower(?))", (e, s, name, username or "")).fetchone()
        if clash:
            problems.append(f"There is already a request for those dates (#{clash[0]})")
        elif CV.list_absences(date_from=s, date_to=e, teacher=username or name):
            problems.append("An absence is already recorded in those dates")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        rid = conn.execute(
            "INSERT INTO staff_absence_requests (staff_name, staff_username, start_date, "
            "end_date, from_period, to_period, absence_type, paid, reason, requested_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, username, s, e, periods[0], periods[1], atype, int(paid),
             _text(data.get("reason"), 1000), actor.username)).lastrowid
        _audit(conn, "request", actor, request_id=rid, type=atype)
    activity_log.record("staff_absence.request", target=f"request:{rid}", principal=actor)
    return get_request(rid)


def approve_request(request_id: int, *, actor: Principal, note: str | None = None
                    ) -> tuple[Request, Record, int]:
    """Approve a request: the absence is recorded and its cover made.
    Returns (request, absence, lessons covered)."""
    rq = get_request(request_id)
    _require_editor(actor, "approve", f"request:{request_id}")
    if rq.status != "Requested":
        raise ValidationError([f"This request is {rq.status.lower()}"])
    if _mine(actor, rq.staff_username):
        raise ValidationError(["Someone else must approve your own request"])
    rec, lessons = create_absence(
        {"staff_name": rq.staff_name, "staff_username": rq.staff_username,
         "start_date": rq.start_date, "end_date": rq.end_date,
         "from_period": rq.from_period, "to_period": rq.to_period,
         "absence_type": rq.absence_type, "paid": rq.paid, "reason": rq.reason,
         "status": "Confirmed", "notification_method": "Not Recorded",
         "certificate_type": "Not Required", "rtw_required": False,
         "notified_on": rq.requested_at[:10], "notified_by": rq.requested_by,
         "_extra": {"request_id": rq.request_id, "approved_by": actor.username,
                    "approved_at": _dt.datetime.now().isoformat(timespec="seconds")}},
        actor=actor)
    with database.connect() as conn:
        conn.execute("UPDATE staff_absence_requests SET status = 'Approved', decided_by = ?, "
                     "decided_at = datetime('now'), decision_note = ?, absence_id = ? "
                     "WHERE request_id = ?",
                     (actor.username, _text(note, 500), rec.absence_id, rq.request_id))
        _audit(conn, "approve", actor, request_id=rq.request_id, absence_id=rec.absence_id)
    activity_log.record("staff_absence.approve", target=f"request:{rq.request_id}",
                        principal=actor, absence=rec.absence_id, lessons=lessons)
    return get_request(rq.request_id), rec, lessons


def decline_request(request_id: int, *, actor: Principal, note: str) -> Request:
    rq = get_request(request_id)
    _require_editor(actor, "decline", f"request:{request_id}")
    if rq.status != "Requested":
        raise ValidationError([f"This request is {rq.status.lower()}"])
    if not (note or "").strip():
        raise ValidationError(["Say why the request is declined"])
    with database.connect() as conn:
        conn.execute("UPDATE staff_absence_requests SET status = 'Declined', decided_by = ?, "
                     "decided_at = datetime('now'), decision_note = ? WHERE request_id = ?",
                     (actor.username, _text(note, 500), rq.request_id))
        _audit(conn, "decline", actor, request_id=rq.request_id)
    activity_log.record("staff_absence.decline", target=f"request:{rq.request_id}",
                        principal=actor)
    return get_request(rq.request_id)


def withdraw_request(request_id: int, *, actor: Principal) -> Request:
    """The person (or HR) takes back a request that hasn't been decided."""
    rq = get_request(request_id)
    _require_staff(actor, "withdraw", f"request:{request_id}")
    if not is_editor(actor) and not _mine(actor, rq.staff_username):
        _deny(actor, "withdraw", f"request:{request_id}", "That isn't your request.")
    if rq.status != "Requested":
        raise ValidationError([f"This request is {rq.status.lower()} - "
                               + ("cancel the absence instead" if rq.status == "Approved"
                                  else "nothing to withdraw")])
    with database.connect() as conn:
        conn.execute("UPDATE staff_absence_requests SET status = 'Withdrawn', decided_by = ?, "
                     "decided_at = datetime('now') WHERE request_id = ?",
                     (actor.username, rq.request_id))
        _audit(conn, "withdraw", actor, request_id=rq.request_id)
    activity_log.record("staff_absence.withdraw", target=f"request:{rq.request_id}",
                        principal=actor)
    return get_request(rq.request_id)


# ── Sickness record, Bradford factor, triggers ───────────────────────

def sickness_record(staff: str, *, actor: Principal, today: _dt.date | None = None
                    ) -> dict[str, Any]:
    """One person's sickness over the rolling 12 months to *today*:
    {'episodes', 'days', 'bradford', 'triggers', 'absences', 'all'}."""
    day = today or _today()
    lo = day - _dt.timedelta(days=364)
    everything = [r for r in list_absences(actor=actor, staff=staff) if r.is_sickness
                  and r.status != "Cancelled"]
    window = [r for r in everything if r.end_date >= lo.isoformat()
              and r.start_date <= day.isoformat()]
    days = 0.0
    for r in window:
        if r.days_lost is not None and r.start_date >= lo.isoformat():
            days += float(r.days_lost)
        else:
            days += working_days(r.start_date, min(r.end_date, day.isoformat()),
                                 partial=r.partial_day, lo=lo, hi=day)
    s = len(window)
    return {"episodes": s, "days": days, "bradford": round(s * s * days, 1),
            "triggers": _triggers(s, days), "absences": window, "all": everything,
            "from": lo.isoformat(), "to": day.isoformat()}


def _triggers(episodes: int, days: float) -> list[str]:
    st = settings()
    out = []
    if episodes >= st["trigger_episodes"]:
        out.append(f"{episodes} episodes (trigger {st['trigger_episodes']})")
    if days >= st["trigger_days"]:
        out.append(f"{days:g} days (trigger {st['trigger_days']})")
    b = episodes * episodes * days
    if b >= st["bradford_trigger"]:
        out.append(f"Bradford {b:g} (trigger {st['bradford_trigger']})")
    return out


def sickness_overview(*, actor: Principal, today: _dt.date | None = None,
                      triggered_only: bool = False) -> list[dict[str, Any]]:
    """Everyone with sickness in the rolling 12 months, highest Bradford first:
    {'staff', 'username', 'episodes', 'days', 'bradford', 'triggers', 'department'}."""
    _require_editor(actor, "sickness")
    day = today or _today()
    lo = (day - _dt.timedelta(days=364)).isoformat()
    people: dict[str, Record] = {}
    for r in list_absences(actor=actor, sickness_only=True, include_cancelled=False,
                           date_from=lo, date_to=day):
        people.setdefault(r.person_key, r)
    depts = departments()
    out = []
    for key, r in people.items():
        rec = sickness_record(r.staff_username or r.staff_name, actor=actor, today=day)
        if triggered_only and not rec["triggers"]:
            continue
        out.append({"staff": r.staff_name, "username": r.staff_username,
                    "episodes": rec["episodes"], "days": rec["days"],
                    "bradford": rec["bradford"], "triggers": rec["triggers"],
                    "department": department_of(r, depts)})
    return sorted(out, key=lambda x: (-x["bradford"], x["staff"].lower()))


# ── Summaries and reports ────────────────────────────────────────────

def summary(*, actor: Principal) -> dict[str, Any]:
    """The old summary (total, open, active today, cover outstanding, critical
    open, RTW overdue, return overdue, awaiting certificate, parents pending,
    distinct staff, total days lost, by type / status / cover source) plus
    requests waiting, RTW interviews outstanding and fit notes needed."""
    rows = list_absences(actor=actor)
    today = _today().isoformat()
    live = [r for r in rows if r.status != "Cancelled"]
    return {
        "total": len(rows), "open": sum(1 for r in rows if r.is_open),
        "active_today": sum(1 for r in rows if r.is_open and r.start_date <= today
                            <= r.end_date),
        "cover_outstanding": sum(1 for r in rows if r.cover_outstanding),
        "critical_open": sum(1 for r in rows if r.critical and r.is_open),
        "rtw_overdue": sum(1 for r in rows if r.rtw_overdue),
        "rtw_outstanding": sum(1 for r in rows if r.rtw_outstanding),
        "return_overdue": sum(1 for r in rows if r.return_overdue),
        "awaiting_cert": sum(1 for r in rows if r.fit_note_needed),
        "parents_pending": sum(1 for r in rows if r.is_open and not r.parents_informed),
        "distinct_staff": len({r.person_key for r in live}),
        "total_days_lost": round(sum(r.days for r in live), 1),
        "requests_waiting": len(list_requests(actor=actor, status="Requested")),
        "by_type": dict(Counter(r.absence_type for r in rows)),
        "by_status": dict(Counter(r.status for r in rows)),
        "by_cover_source": dict(Counter(r.cover_source for r in rows))}


def report(*, by: str = "type", actor: Principal, date_from: Any = None,
           date_to: Any = None) -> list[dict[str, Any]]:
    """Absence (not cancelled) grouped by type, department, month or person:
    {'group', 'absences', 'days', 'sickness_days', 'people', 'unpaid_days'}."""
    _require_editor(actor, "report")
    if by not in REPORT_GROUPS:
        raise ValidationError([f"Group by one of {', '.join(REPORT_GROUPS)}"])
    depts = departments() if by == "department" else {}
    groups: dict[str, list[Record]] = {}
    for r in list_absences(actor=actor, include_cancelled=False, date_from=date_from,
                           date_to=date_to):
        key = {"type": lambda: r.absence_type, "department": lambda: department_of(r, depts),
               "month": lambda: r.start_date[:7], "person": lambda: r.staff_name}[by]()
        groups.setdefault(key, []).append(r)
    return sorted(({"group": g, "absences": len(v), "days": round(sum(r.days for r in v), 1),
                    "sickness_days": round(sum(r.days for r in v if r.is_sickness), 1),
                    "unpaid_days": round(sum(r.days for r in v if not r.paid), 1),
                    "people": len({r.person_key for r in v})} for g, v in groups.items()),
                  key=lambda x: (x["group"] if by == "month" else "", -x["days"], x["group"]))


def export_csv(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    """The absences (old filters apply) as CSV. HR only - it holds reasons."""
    _require_editor(actor, "export")
    rows = list_absences(actor=actor, **filters)
    depts = departments()
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "staff", "username", "department", "type", "paid", "first_day",
                    "last_day", "periods", "expected_return", "actual_return", "days",
                    "status", "reason", "notified_on", "notification_method", "certificate",
                    "certificate_received", "fit_note_from", "fit_note_to", "cover_required",
                    "cover_source", "cover_lessons", "cover_pending", "rtw_required",
                    "rtw_meeting_on", "rtw_completed_by", "approved_by", "flags", "notes"])
        for r in rows:
            w.writerow([r.absence_id, _safe(r.staff_name), _safe(r.staff_username),
                        _safe(department_of(r, depts)), r.absence_type,
                        "yes" if r.paid else "no", r.start_date, r.end_date, r.periods_label,
                        r.expected_return or "", r.actual_return or "", r.days, r.status,
                        _safe(r.reason), r.notified_on or "", r.notification_method,
                        r.certificate_type, r.cert_received_on or "", r.fit_note_from or "",
                        r.fit_note_to or "", "yes" if r.cover_required else "no",
                        r.cover_source, r.cover_total, r.cover_pending,
                        "yes" if r.rtw_required else "no", r.rtw_meeting_on or "",
                        _safe(r.rtw_completed_by), _safe(r.approved_by), ",".join(r.flags),
                        _safe(r.notes)])
    activity_log.record("staff_absence.export", principal=actor, rows=len(rows))
    return len(rows)


# ── For the staff portal (My Day) ────────────────────────────────────

def my_absence(principal: Principal) -> dict[str, Any]:
    """{'off_now': my absences covering today or later, 'requests': my
    requests (waiting first), 'rtw_due': my returns awaiting the interview}."""
    today = _today().isoformat()
    mine = list_absences(actor=principal, staff=principal.username, include_cancelled=False)
    return {"off_now": [r for r in mine if r.end_date >= today and r.is_open],
            "requests": list_requests(actor=principal, staff=principal.username)[:10],
            "rtw_due": [r for r in mine if r.rtw_outstanding]}
