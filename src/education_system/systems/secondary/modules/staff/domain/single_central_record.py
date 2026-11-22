"""The single central record (KCSIE): pre-appointment checks for everyone
who works in the school.

**People.** One row per person: staff, supply staff, volunteers, governors,
contractors and trainees, with their post, start and leaving dates and the
facts that decide which checks they need (a teaching post, a leadership post
or governor - section 128, regulated activity, lived or worked overseas,
childcare where disqualification is relevant). Staff are keyed on their
secondary login (:func:`accounts.staff_logins`); anyone else is a free-text
name. Supply staff link to cover's ``supply_staff`` roster, so the cover
manager's "DBS cleared" flag and the SCR agree (:func:`sync_supply`, and a
DBS check saved here updates the roster).

**Checks.** Identity, qualifications, enhanced DBS, children's barred list,
prohibition from teaching, section 128, overseas checks, right to work,
references, medical fitness, disqualification by association and (supply)
the agency's written confirmation - each with its status, the date, who
checked, the document / certificate reference, issue and expiry dates and
notes. DBS checks keep every field of the old DBS register (level, number,
applied / issued, certificate seen, Update Service id and checks, portability,
risk assessment, sign-off) and its actions (issue certificate, mark seen,
subscribe to the Update Service, record an update check, complete the risk
assessment, sign off, mark lapsed, start renewal, change status).

**What it shows.** For each person, the state of every check they need:
ok, missing, pending, expired, expiring, overdue (an Update Service check)
or a problem (refused / concern). :func:`problems` lists what needs doing
across the school, :func:`reminders` what falls due soon, and the record
exports as CSV and as text for an inspection.

**Who.** Everything is for :data:`SCR_EDITORS` (the label is admin-only).
The activity log gets ids only.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import cover as CV  # registers the FK target
from education_system.systems.secondary.modules.staff.domain import staff_directory as SD
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import COVER_EDITORS, SCR_EDITORS, Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

CATEGORIES: tuple[str, ...] = ("Staff", "Supply", "Volunteer", "Governor", "Contractor",
                               "Trainee")
DBS = "DBS"
CHECK_TYPES: tuple[str, ...] = (
    "Identity", "Qualifications", DBS, "Barred list", "Prohibition from teaching",
    "Section 128", "Overseas", "Right to work", "References", "Medical fitness",
    "Disqualification by association", "Agency confirmation")
STATUSES: tuple[str, ...] = ("Not started", "Requested", "Pending", "Clear",
                             "Clear with information", "Concern", "Not required")
#: The old DBS register's statuses (DBS checks use these).
DBS_STATUSES: tuple[str, ...] = ("Applied", "Pending", "Awaiting Certificate", "Cleared",
                                 "Cleared (with information)", "Refused", "Lapsed", "Renewing",
                                 "Update Service Active")
DEFAULT_DBS_STATUS = "Applied"
LEVELS: tuple[str, ...] = ("Basic", "Standard", "Enhanced", "Enhanced with Barred List",
                           "Enhanced — Children's Barred List",
                           "Enhanced — Adults' Barred List")
DEFAULT_LEVEL = "Enhanced with Barred List"
CERTIFICATE_TYPES: tuple[str, ...] = ("Original Seen", "Photocopy on File",
                                      "Update Service Check", "DBS Portal", "Other")
DEFAULT_CERTIFICATE_TYPE = "Original Seen"
OK = frozenset({"Clear", "Clear with information", "Not required", "Cleared",
                "Cleared (with information)", "Update Service Active"})
DBS_ACTIVE = frozenset({"Cleared", "Cleared (with information)", "Update Service Active"})
BAD = frozenset({"Concern", "Refused", "Lapsed"})
STATES: tuple[str, ...] = ("ok", "missing", "pending", "expiring", "expired", "overdue",
                           "problem")
EXPIRING_DAYS = 90
UPDATE_CHECK_DAYS = 365

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scr_people (
    person_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name          TEXT NOT NULL,
    username           TEXT,
    category           TEXT NOT NULL DEFAULT 'Staff',
    role_title         TEXT,
    agency_name        TEXT,
    supply_id          INTEGER REFERENCES supply_staff (supply_id) ON DELETE SET NULL,
    start_date         TEXT,
    end_date           TEXT,
    teaching_role      INTEGER NOT NULL DEFAULT 0,
    leadership_role    INTEGER NOT NULL DEFAULT 0,
    regulated_activity INTEGER NOT NULL DEFAULT 1,
    lived_overseas     INTEGER NOT NULL DEFAULT 0,
    childcare_relevant INTEGER NOT NULL DEFAULT 0,
    notes              TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    created_by         TEXT,
    updated_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by         TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_scr_people_username
    ON scr_people (lower(username)) WHERE username IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_scr_people_supply
    ON scr_people (supply_id) WHERE supply_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS scr_checks (
    check_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id         INTEGER NOT NULL REFERENCES scr_people (person_id) ON DELETE CASCADE,
    check_type        TEXT NOT NULL,
    status            TEXT NOT NULL,
    checked_on        TEXT,
    checked_by        TEXT,
    reference         TEXT,
    issued_on         TEXT,
    expires_on        TEXT,
    notes             TEXT,
    dbs_level         TEXT,
    dbs_number        TEXT,
    applied_on        TEXT,
    certificate_type  TEXT,
    certificate_seen_on TEXT,
    update_service_subscribed INTEGER NOT NULL DEFAULT 0,
    update_service_id TEXT,
    last_update_check_on TEXT,
    next_update_check_due TEXT,
    portability_check INTEGER NOT NULL DEFAULT 0,
    risk_assessment_required INTEGER NOT NULL DEFAULT 0,
    risk_assessment_completed_on TEXT,
    risk_assessment_outcome TEXT,
    signed_off_by     TEXT,
    signed_off_on     TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    created_by        TEXT,
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by        TEXT
);
CREATE INDEX IF NOT EXISTS ix_scr_checks_person ON scr_checks (person_id, check_type);
CREATE TABLE IF NOT EXISTS scr_audit (
    audit_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER,
    check_id  INTEGER,
    action    TEXT NOT NULL,
    actor     TEXT NOT NULL,
    detail    TEXT,
    at        TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("single_central_record", _SCHEMA)

# A staff record with these can't be deleted (Staff Directory marks them as left).
SD.register_login_reference("scr_people", "username", "single central record entry")


# ── Records ──────────────────────────────────────────────────────────

PERSON_FIELDS = ("full_name", "username", "category", "role_title", "agency_name",
                 "supply_id", "start_date", "end_date", "teaching_role", "leadership_role",
                 "regulated_activity", "lived_overseas", "childcare_relevant", "notes")
_PERSON_BOOLS = ("teaching_role", "leadership_role", "regulated_activity", "lived_overseas",
                 "childcare_relevant")
CHECK_FIELDS = ("check_type", "status", "checked_on", "checked_by", "reference", "issued_on",
                "expires_on", "notes", "dbs_level", "dbs_number", "applied_on",
                "certificate_type", "certificate_seen_on", "update_service_subscribed",
                "update_service_id", "last_update_check_on", "next_update_check_due",
                "portability_check", "risk_assessment_required",
                "risk_assessment_completed_on", "risk_assessment_outcome", "signed_off_by",
                "signed_off_on")
_CHECK_BOOLS = ("update_service_subscribed", "portability_check", "risk_assessment_required")
_CHECK_DATES = {"checked_on": "Checked on", "issued_on": "Issued on",
                "expires_on": "Expires on", "applied_on": "Applied on",
                "certificate_seen_on": "Certificate seen on",
                "last_update_check_on": "Last update check",
                "next_update_check_due": "Next update check",
                "risk_assessment_completed_on": "Risk assessment on",
                "signed_off_on": "Signed off on"}


@dataclass(frozen=True)
class Person:
    person_id: int
    full_name: str
    username: str | None
    category: str
    role_title: str | None
    agency_name: str | None
    supply_id: int | None
    start_date: str | None
    end_date: str | None
    teaching_role: bool
    leadership_role: bool
    regulated_activity: bool
    lived_overseas: bool
    childcare_relevant: bool
    notes: str | None
    created_at: str
    created_by: str | None
    updated_at: str
    updated_by: str | None

    @property
    def is_current(self) -> bool:
        return not self.end_date or self.end_date >= _today().isoformat()

    @property
    def has_started(self) -> bool:
        return not self.start_date or self.start_date <= _today().isoformat()


@dataclass(frozen=True)
class Check:
    check_id: int
    person_id: int
    check_type: str
    status: str
    checked_on: str | None
    checked_by: str | None
    reference: str | None
    issued_on: str | None
    expires_on: str | None
    notes: str | None
    dbs_level: str | None
    dbs_number: str | None
    applied_on: str | None
    certificate_type: str | None
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
    created_at: str
    created_by: str | None
    updated_at: str
    updated_by: str | None
    person_name: str = ""

    # the old DBS register's names
    @property
    def staff_id(self) -> str:
        return self.person_name

    @property
    def level(self) -> str | None:
        return self.dbs_level

    @property
    def is_active(self) -> bool:
        return self.status in DBS_ACTIVE if self.check_type == DBS else self.status in OK

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_on and self.is_active
                    and self.expires_on < _today().isoformat())

    @property
    def expiring_soon(self) -> bool:
        if not self.expires_on or not self.is_active or self.is_expired:
            return False
        return (_dt.date.fromisoformat(self.expires_on) - _today()).days <= EXPIRING_DAYS

    @property
    def update_check_overdue(self) -> bool:
        return bool(self.update_service_subscribed and self.next_update_check_due
                    and self.next_update_check_due < _today().isoformat())

    @property
    def risk_pending(self) -> bool:
        return self.risk_assessment_required and not self.risk_assessment_completed_on

    @property
    def unsigned(self) -> bool:
        return not self.signed_off_by

    @property
    def state(self) -> str:
        if self.status in BAD:
            return "problem"
        if not self.is_active:
            return "pending"
        if self.is_expired:
            return "expired"
        if self.update_check_overdue:
            return "overdue"
        if self.expiring_soon:
            return "expiring"
        return "ok"


def _person_row(r) -> Person:
    out = {k: r[k] for k in Person.__dataclass_fields__}
    for k in _PERSON_BOOLS:
        out[k] = bool(out[k])
    return Person(**out)


def _check_row(r) -> Check:
    out = {k: r[k] for k in Check.__dataclass_fields__ if k != "person_name"}
    for k in _CHECK_BOOLS:
        out[k] = bool(out[k])
    return Check(**out, person_name=r["person_name"])


_CHECK_SELECT = ("SELECT c.*, p.full_name AS person_name FROM scr_checks c "
                 "JOIN scr_people p USING (person_id)")


# ── Who may do what ──────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in SCR_EDITORS


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        activity_log.record(f"scr.{action}", target=target, outcome="denied",
                            principal=actor)
        raise PermissionDenied("Only the single central record administrators can do that.")


def _audit(conn, action: str, actor: Principal, *, person_id: int | None = None,
           check_id: int | None = None, **detail: Any) -> None:
    conn.execute("INSERT INTO scr_audit (person_id, check_id, action, actor, detail) "
                 "VALUES (?, ?, ?, ?, ?)",
                 (person_id, check_id, action, actor.username or "unknown",
                  json.dumps(detail, default=str, sort_keys=True) if detail else None))


def history(person_id: int | None = None, *, check_id: int | None = None,
            limit: int = 200) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM scr_audit", []
    if check_id is not None:
        sql += " WHERE check_id = ?"
        params.append(int(check_id))
    elif person_id is not None:
        sql += " WHERE person_id = ?"
        params.append(int(person_id))
    with database.connect() as conn:
        return [{"at": r["at"], "actor": r["actor"], "action": r["action"],
                 "person_id": r["person_id"], "check_id": r["check_id"],
                 "detail": json.loads(r["detail"]) if r["detail"] else {}}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, int(limit)))]


# ── Cleaning ─────────────────────────────────────────────────────────

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


def _text(value: Any, limit: int) -> str | None:
    return (str(value).strip()[:limit] or None) if value not in (None, "") else None


def _login(username: str) -> dict | None:
    try:
        logins = accounts.staff_logins()
    except Exception:  # noqa: BLE001 - auth.db unreadable: names still work
        logins = []
    return next((t for t in logins if t["username"].lower() == username.strip().lower()), None)


def _clean_person(data: dict[str, Any], current: Person | None) -> dict[str, Any]:
    problems: list[str] = []
    unknown = set(data) - set(PERSON_FIELDS)
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    merged = {k: getattr(current, k) for k in PERSON_FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in PERSON_FIELDS})
    out: dict[str, Any] = {}
    out["category"] = _choice(merged.get("category"), CATEGORIES, "Category", problems,
                              "Staff")
    out["username"] = _text(merged.get("username"), 100)
    name = P._clean_text(merged.get("full_name"), 120)
    if out["username"]:
        login = _login(out["username"])
        if login is None:
            problems.append(f"'{out['username']}' isn't a secondary staff login")
        else:
            out["username"] = login["username"]
            name = name or login["display_name"]
    sid = merged.get("supply_id")
    out["supply_id"] = None
    if sid not in (None, ""):
        try:
            s = CV.get_supply(int(sid))
            out["supply_id"] = s.supply_id
            name = name or s.full_name
            merged["agency_name"] = merged.get("agency_name") or s.agency_name
        except (ValueError, TypeError, CV.NotFound):
            problems.append(f"No supply staff #{sid}")
    if out["supply_id"] and out["category"] != "Supply":
        problems.append("Only supply staff link to the supply roster")
    if not name:
        problems.append("Name is required")
    out["full_name"] = name
    out["role_title"] = _text(merged.get("role_title"), 100)
    out["agency_name"] = _text(merged.get("agency_name"), 100)
    out["start_date"] = _date(merged.get("start_date"), "Start date", problems)
    out["end_date"] = _date(merged.get("end_date"), "Leaving date", problems)
    if out["start_date"] and out["end_date"] and out["end_date"] < out["start_date"]:
        problems.append("The leaving date is before the start date")
    for k in _PERSON_BOOLS:
        v = merged.get(k)
        if v is None:
            v = k == "regulated_activity"
        out[k] = P._as_bool(v, k.replace("_", " ").capitalize(), problems)
    out["notes"] = _text(merged.get("notes"), 2000)
    if problems:
        raise ValidationError(problems)
    return out


def _clean_check(data: dict[str, Any], current: Check | None, actor: Principal
                 ) -> dict[str, Any]:
    problems: list[str] = []
    unknown = set(data) - set(CHECK_FIELDS)
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    merged = {k: getattr(current, k) for k in CHECK_FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in CHECK_FIELDS})
    out: dict[str, Any] = {}
    ctype = _choice(merged.get("check_type"), CHECK_TYPES, "Check", problems, None)
    if ctype is None and not problems:
        problems.append("Choose the check")
    out["check_type"] = ctype
    dbs = ctype == DBS
    out["status"] = _choice(merged.get("status"), DBS_STATUSES if dbs else STATUSES,
                            "Status", problems, DEFAULT_DBS_STATUS if dbs else "Pending")
    for k, label in _CHECK_DATES.items():
        out[k] = _date(merged.get(k), label, problems)
    today = _today().isoformat()
    for k in ("checked_on", "issued_on", "applied_on", "certificate_seen_on",
              "last_update_check_on", "risk_assessment_completed_on", "signed_off_on"):
        if out[k] and out[k] > today:
            problems.append(f"{_CHECK_DATES[k]} can't be in the future")
    for k in _CHECK_BOOLS:
        out[k] = P._as_bool(merged.get(k) or False, k.replace("_", " ").capitalize(), problems)
    for k, n in (("checked_by", 100), ("reference", 100), ("notes", 2000),
                 ("update_service_id", 40), ("risk_assessment_outcome", 500),
                 ("signed_off_by", 100)):
        out[k] = _text(merged.get(k), n)
    ok = out["status"] in OK
    if ok and out["status"] != "Not required":
        out["checked_on"] = out["checked_on"] or today
        out["checked_by"] = out["checked_by"] or actor.username
    if out["issued_on"] and out["expires_on"] and out["expires_on"] < out["issued_on"]:
        problems.append("Expires on must be on or after issued on")
    out["dbs_level"] = out["dbs_number"] = out["certificate_type"] = None
    if dbs:
        out["dbs_level"] = _choice(merged.get("dbs_level"), LEVELS, "Level", problems,
                                   DEFAULT_LEVEL)
        out["certificate_type"] = _choice(merged.get("certificate_type"), CERTIFICATE_TYPES,
                                          "Certificate type", problems,
                                          DEFAULT_CERTIFICATE_TYPE)
        num = re.sub(r"\s", "", str(merged.get("dbs_number") or ""))
        if num and not re.fullmatch(r"\d{12}", num):
            problems.append("A DBS certificate number is 12 digits")
        out["dbs_number"] = num or None
        if out["status"] in DBS_ACTIVE and not (out["dbs_number"] and out["issued_on"]):
            problems.append("A cleared DBS needs the certificate number and issue date")
        if out["update_service_subscribed"] and out["last_update_check_on"] and \
                not out["next_update_check_due"]:
            out["next_update_check_due"] = (_dt.date.fromisoformat(out["last_update_check_on"])
                                            + _dt.timedelta(days=UPDATE_CHECK_DAYS)).isoformat()
    elif any(merged.get(k) not in (None, "", False) for k in (
            "dbs_level", "dbs_number", "update_service_id")):
        problems.append("DBS details belong on a DBS check")
    if out["risk_assessment_completed_on"] and not out["risk_assessment_outcome"]:
        problems.append("Risk assessment outcome is required")
    if out["signed_off_on"] and not out["signed_off_by"]:
        out["signed_off_by"] = actor.username
    if problems:
        raise ValidationError(problems)
    return out


# ── People ───────────────────────────────────────────────────────────

def get_person(person_id: int) -> Person:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM scr_people WHERE person_id = ?",
                         (int(person_id),)).fetchone()
    if r is None:
        raise NotFound(f"No person #{person_id}")
    return _person_row(r)


def find_person(username: str) -> Person | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM scr_people WHERE lower(username) = lower(?)",
                         (username.strip(),)).fetchone()
    return _person_row(r) if r else None


def list_people(*, actor: Principal, category: str | None = None,
                current_only: bool = True, search: str | None = None) -> list[Person]:
    _require_editor(actor, "list")
    where, params = [], []
    if category:
        where.append("category = ?")
        params.append(category)
    if current_only:
        where.append("(end_date IS NULL OR end_date >= ?)")
        params.append(_today().isoformat())
    if search:
        where.append("(lower(full_name) LIKE lower(?) OR lower(username) LIKE lower(?) OR "
                     "lower(role_title) LIKE lower(?))")
        params += [f"%{search.strip()}%"] * 3
    sql = "SELECT * FROM scr_people" + (" WHERE " + " AND ".join(where) if where else "")
    with database.connect() as conn:
        return [_person_row(r) for r in conn.execute(
            sql + " ORDER BY category, full_name COLLATE NOCASE", params)]


def create_person(data: dict[str, Any], *, actor: Principal) -> Person:
    _require_editor(actor, "person_create")
    clean = _clean_person(data, None)
    try:
        with database.connect() as conn:
            cols = list(clean)
            pid = conn.execute(
                f"INSERT INTO scr_people ({', '.join(cols)}, created_by, updated_by) "  # nosec B608 - fixed columns
                f"VALUES ({', '.join('?' * len(cols))}, ?, ?)",
                (*[int(v) if k in _PERSON_BOOLS else v for k, v in clean.items()],
                 actor.username, actor.username)).lastrowid
            _audit(conn, "person_create", actor, person_id=pid, category=clean["category"])
    except database.IntegrityError:
        raise ValidationError(["That login or supply person is already on the record"]) \
            from None
    activity_log.record("scr.person_create", target=f"scr:{pid}", principal=actor)
    return get_person(pid)


def update_person(person_id: int, changes: dict[str, Any], *, actor: Principal) -> Person:
    _require_editor(actor, "person_update", f"scr:{person_id}")
    cur = get_person(person_id)
    clean = _clean_person(changes, cur)
    diff = {k: v for k, v in clean.items() if getattr(cur, k) != v}
    if diff:
        try:
            with database.connect() as conn:
                conn.execute(
                    f"UPDATE scr_people SET {', '.join(f'{k} = ?' for k in diff)}, "  # nosec B608 - keys from _clean_person
                    "updated_at = datetime('now'), updated_by = ? WHERE person_id = ?",
                    (*[int(v) if k in _PERSON_BOOLS else v for k, v in diff.items()],
                     actor.username, cur.person_id))
                _audit(conn, "person_update", actor, person_id=cur.person_id,
                       fields=sorted(diff))
        except database.IntegrityError:
            raise ValidationError(["That login or supply person is already on the record"]) \
                from None
        activity_log.record("scr.person_update", target=f"scr:{cur.person_id}",
                            principal=actor, fields=sorted(diff))
    return get_person(cur.person_id)


def record_leaving(person_id: int, *, actor: Principal, end_date: Any = None) -> Person:
    """They have left: the record is kept (KCSIE) but drops off the current list."""
    return update_person(person_id, {"end_date": end_date or _today().isoformat()},
                         actor=actor)


def delete_person(person_id: int, *, actor: Principal) -> None:
    """Only someone added in error (no checks recorded) - otherwise record leaving."""
    _require_editor(actor, "person_delete", f"scr:{person_id}")
    p = get_person(person_id)
    with database.connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM scr_checks WHERE person_id = ?",
                         (p.person_id,)).fetchone()[0]
        if n:
            raise ValidationError([f"{p.full_name} has {n} check(s) on record - record "
                                   "their leaving date instead"])
        conn.execute("DELETE FROM scr_people WHERE person_id = ?", (p.person_id,))
        _audit(conn, "person_delete", actor, person_id=p.person_id)
    activity_log.record("scr.person_delete", target=f"scr:{p.person_id}", principal=actor)


def missing_people(*, actor: Principal) -> dict[str, list]:
    """Staff logins and active supply staff with no SCR entry:
    {'logins': [login dict], 'supply': [cover.Supply]}."""
    _require_editor(actor, "missing")
    with database.connect() as conn:
        names = {r[0].lower() for r in conn.execute(
            "SELECT username FROM scr_people WHERE username IS NOT NULL")}
        sids = {r[0] for r in conn.execute(
            "SELECT supply_id FROM scr_people WHERE supply_id IS NOT NULL")}
    try:
        logins = accounts.staff_logins()
    except Exception:  # noqa: BLE001
        logins = []
    return {"logins": [t for t in logins if t["username"].lower() not in names],
            "supply": [s for s in CV.list_supply(active_only=True) if s.supply_id not in sids]}


def add_from_logins(*, actor: Principal) -> int:
    """Add every secondary staff login missing from the record (category Staff)."""
    n = 0
    for t in missing_people(actor=actor)["logins"]:
        create_person({"username": t["username"], "category": "Staff"}, actor=actor)
        n += 1
    return n


def sync_supply(*, actor: Principal) -> int:
    """Add every active supply person (cover's roster) missing from the record,
    with their DBS as the roster has it (as a check to confirm)."""
    n = 0
    for s in missing_people(actor=actor)["supply"]:
        p = create_person({"category": "Supply", "supply_id": s.supply_id,
                           "role_title": s.role, "teaching_role":
                           s.role == "Supply teacher"}, actor=actor)
        if s.dbs_cleared:
            add_check(p.person_id, {"check_type": DBS, "status": "Pending",
                                    "notes": f"Roster says DBS seen {s.dbs_checked_on} - "
                                             "confirm the certificate"}, actor=actor)
        n += 1
    return n


# ── Which checks each person needs ───────────────────────────────────

def required_checks(p: Person) -> tuple[str, ...]:
    """The checks KCSIE asks for, for this person."""
    c = p.category
    need = ["Identity"]
    works = c in ("Staff", "Supply", "Trainee") or (
        c in ("Volunteer", "Contractor") and p.regulated_activity)
    if works or c == "Governor":
        need.append(DBS)
    if works:
        need.append("Barred list")
    if p.teaching_role and c in ("Staff", "Supply", "Trainee"):
        need += ["Qualifications", "Prohibition from teaching"]
    if c == "Governor" or p.leadership_role:
        need.append("Section 128")
    if p.lived_overseas:
        need.append("Overseas")
    if c == "Staff":
        need += ["Right to work", "References", "Medical fitness"]
    elif c == "Volunteer":
        need.append("References")
    if p.childcare_relevant:
        need.append("Disqualification by association")
    if c == "Supply":
        need.append("Agency confirmation")
    return tuple(t for t in CHECK_TYPES if t in need)


# ── Checks ───────────────────────────────────────────────────────────

def get_check(check_id: int) -> Check:
    with database.connect() as conn:
        r = conn.execute(_CHECK_SELECT + " WHERE c.check_id = ?", (int(check_id),)).fetchone()
    if r is None:
        raise NotFound(f"No check #{check_id}")
    return _check_row(r)


def list_checks(*, actor: Principal, person_id: int | None = None,
                check_type: str | None = None, level: str | None = None,
                status: str | None = None, certificate_type: str | None = None,
                search: str | None = None, active_only: bool = False, expired: bool = False,
                expiring_soon: bool = False, update_check_overdue: bool = False,
                update_service_only: bool = False, unsigned: bool = False,
                risk_assessment_pending: bool = False) -> list[Check]:
    """Checks with the old DBS register's filters (soonest expiry first)."""
    _require_editor(actor, "checks")
    where, params = [], []
    for col, val in (("c.person_id", person_id), ("c.check_type", check_type),
                     ("c.dbs_level", level), ("c.status", status),
                     ("c.certificate_type", certificate_type)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if search:
        where.append("(lower(p.full_name) LIKE lower(?) OR lower(p.username) LIKE lower(?))")
        params += [f"%{search.strip()}%"] * 2
    sql = _CHECK_SELECT + (" WHERE " + " AND ".join(where) if where else "")
    with database.connect() as conn:
        rows = [_check_row(r) for r in conn.execute(
            sql + " ORDER BY COALESCE(c.expires_on, '9999') ASC, c.check_id DESC", params)]
    flags = ((active_only, lambda c: c.is_active), (expired, lambda c: c.is_expired),
             (expiring_soon, lambda c: c.expiring_soon),
             (update_check_overdue, lambda c: c.update_check_overdue),
             (update_service_only, lambda c: c.update_service_subscribed),
             (unsigned, lambda c: c.unsigned),
             (risk_assessment_pending, lambda c: c.risk_pending))
    return [c for c in rows if all(fn(c) for on, fn in flags if on)]


def checks_for_person(person_id: int, *, actor: Principal) -> list[Check]:
    return list_checks(actor=actor, person_id=person_id)


def _latest(checks: list[Check]) -> dict[str, Check]:
    out: dict[str, Check] = {}
    for c in sorted(checks, key=lambda c: (c.checked_on or c.issued_on or c.created_at[:10],
                                           c.check_id)):
        out[c.check_type] = c
    return out


def _sync_supply_dbs(p: Person, c: Check, actor: Principal) -> None:
    """Keep the cover roster's DBS flag in step with the SCR (cover refuses
    to assign supply staff without it)."""
    if c.check_type != DBS or not p.supply_id or actor.role not in COVER_EDITORS:
        return
    s = CV.get_supply(p.supply_id)
    if c.is_active and (not s.dbs_cleared or s.dbs_checked_on != (c.checked_on or c.issued_on)):
        CV.update_supply(s.supply_id, {"dbs_cleared": True,
                                       "dbs_checked_on": c.checked_on or c.issued_on},
                         actor=actor)
    elif c.status in BAD and s.dbs_cleared:
        CV.update_supply(s.supply_id, {"dbs_cleared": False, "dbs_checked_on": None},
                         actor=actor)


def add_check(person_id: int, data: dict[str, Any], *, actor: Principal) -> Check:
    """Record a check (a renewal is a new check; the latest one counts)."""
    _require_editor(actor, "check_create", f"scr:{person_id}")
    p = get_person(person_id)
    clean = _clean_check(data, None, actor)
    with database.connect() as conn:
        cols = list(clean)
        cid = conn.execute(
            f"INSERT INTO scr_checks (person_id, {', '.join(cols)}, created_by, updated_by) "  # nosec B608 - fixed columns
            f"VALUES (?, {', '.join('?' * len(cols))}, ?, ?)",
            (p.person_id, *[int(v) if k in _CHECK_BOOLS else v for k, v in clean.items()],
             actor.username, actor.username)).lastrowid
        _audit(conn, "check_create", actor, person_id=p.person_id, check_id=cid,
               type=clean["check_type"], status=clean["status"])
    activity_log.record("scr.check_create", target=f"scr:{p.person_id}", principal=actor,
                        check=cid)
    c = get_check(cid)
    _sync_supply_dbs(p, c, actor)
    return c


def update_check(check_id: int, changes: dict[str, Any], *, actor: Principal) -> Check:
    _require_editor(actor, "check_update", f"check:{check_id}")
    cur = get_check(check_id)
    clean = _clean_check(changes, cur, actor)
    diff = {k: v for k, v in clean.items() if getattr(cur, k) != v}
    if diff:
        with database.connect() as conn:
            conn.execute(
                f"UPDATE scr_checks SET {', '.join(f'{k} = ?' for k in diff)}, "  # nosec B608 - keys from _clean_check
                "updated_at = datetime('now'), updated_by = ? WHERE check_id = ?",
                (*[int(v) if k in _CHECK_BOOLS else v for k, v in diff.items()],
                 actor.username, cur.check_id))
            _audit(conn, "check_update", actor, person_id=cur.person_id,
                   check_id=cur.check_id, fields=sorted(diff))
        activity_log.record("scr.check_update", target=f"check:{cur.check_id}",
                            principal=actor, fields=sorted(diff))
    c = get_check(cur.check_id)
    _sync_supply_dbs(get_person(c.person_id), c, actor)
    return c


def delete_check(check_id: int, *, actor: Principal) -> None:
    _require_editor(actor, "check_delete", f"check:{check_id}")
    c = get_check(check_id)
    with database.connect() as conn:
        conn.execute("DELETE FROM scr_checks WHERE check_id = ?", (c.check_id,))
        _audit(conn, "check_delete", actor, person_id=c.person_id, check_id=c.check_id,
               type=c.check_type)
    activity_log.record("scr.check_delete", target=f"check:{c.check_id}", principal=actor)


def _dbs(check_id: int) -> Check:
    c = get_check(check_id)
    if c.check_type != DBS:
        raise ValidationError(["That isn't a DBS check"])
    return c


# The old DBS register's actions.

def issue_certificate(check_id: int, *, dbs_number: str, actor: Principal,
                      issued_on: Any = None, expires_on: Any = None) -> Check:
    _dbs(check_id)
    if not (dbs_number or "").strip():
        raise ValidationError(["DBS number is required"])
    vals: dict[str, Any] = {"dbs_number": dbs_number, "status": "Cleared",
                            "issued_on": issued_on or _today().isoformat()}
    if expires_on:
        vals["expires_on"] = expires_on
    return update_check(check_id, vals, actor=actor)


def see_certificate(check_id: int, *, actor: Principal, seen_on: Any = None) -> Check:
    _dbs(check_id)
    return update_check(check_id, {"certificate_seen_on": seen_on or _today().isoformat(),
                                   "checked_on": seen_on or _today().isoformat(),
                                   "checked_by": actor.username}, actor=actor)


def subscribe_update_service(check_id: int, *, actor: Principal, update_id: str | None = None,
                             next_check_due: Any = None) -> Check:
    c = _dbs(check_id)
    vals: dict[str, Any] = {"update_service_subscribed": True}
    if update_id:
        vals["update_service_id"] = update_id
    vals["next_update_check_due"] = next_check_due or c.next_update_check_due or (
        _today() + _dt.timedelta(days=UPDATE_CHECK_DAYS)).isoformat()
    if c.status == "Cleared":
        vals["status"] = "Update Service Active"
    return update_check(check_id, vals, actor=actor)


def record_update_check(check_id: int, *, actor: Principal, checked_on: Any = None,
                        next_check_due: Any = None) -> Check:
    """An Update Service status check (default next one: 12 months on)."""
    c = _dbs(check_id)
    if not c.update_service_subscribed:
        raise ValidationError(["They aren't on the Update Service - subscribe first"])
    probs: list[str] = []
    on = _date(checked_on, "Checked on", probs) or _today().isoformat()
    if probs:
        raise ValidationError(probs)
    nxt = next_check_due or (_dt.date.fromisoformat(on)
                             + _dt.timedelta(days=UPDATE_CHECK_DAYS)).isoformat()
    return update_check(check_id, {"last_update_check_on": on, "next_update_check_due": nxt,
                                   "checked_on": on, "checked_by": actor.username},
                        actor=actor)


def complete_risk_assessment(check_id: int, *, outcome: str, actor: Principal,
                             completed_on: Any = None) -> Check:
    if not (outcome or "").strip():
        raise ValidationError(["Risk assessment outcome is required"])
    return update_check(check_id, {"risk_assessment_outcome": outcome,
                                   "risk_assessment_required": True,
                                   "risk_assessment_completed_on":
                                       completed_on or _today().isoformat()}, actor=actor)


def sign_off(check_id: int, *, signed_off_by: str, actor: Principal,
             signed_off_on: Any = None) -> Check:
    if not (signed_off_by or "").strip():
        raise ValidationError(["Signed-off by is required"])
    return update_check(check_id, {"signed_off_by": signed_off_by,
                                   "signed_off_on": signed_off_on or _today().isoformat()},
                        actor=actor)


def mark_lapsed(check_id: int, *, actor: Principal) -> Check:
    _dbs(check_id)
    return update_check(check_id, {"status": "Lapsed"}, actor=actor)


def start_renewal(check_id: int, *, actor: Principal) -> Check:
    _dbs(check_id)
    return update_check(check_id, {"status": "Renewing"}, actor=actor)


def set_status(check_id: int, new_status: str, *, actor: Principal) -> Check:
    return update_check(check_id, {"status": new_status}, actor=actor)


# ── The record ───────────────────────────────────────────────────────

def person_status(p: Person, checks: list[Check] | None = None) -> dict[str, dict[str, Any]]:
    """{check type: {'state', 'check'}} for every check this person needs."""
    if checks is None:
        with database.connect() as conn:
            checks = [_check_row(r) for r in conn.execute(
                _CHECK_SELECT + " WHERE c.person_id = ?", (p.person_id,))]
    latest = _latest(checks)
    return {t: {"state": latest[t].state if t in latest else "missing",
                "check": latest.get(t)} for t in required_checks(p)}


def record(*, actor: Principal, category: str | None = None, current_only: bool = True,
           search: str | None = None, problems_only: bool = False
           ) -> list[tuple[Person, dict[str, dict[str, Any]]]]:
    """The single central record: each person with the state of their checks."""
    people = list_people(actor=actor, category=category, current_only=current_only,
                         search=search)
    by_person: dict[int, list[Check]] = {}
    for c in list_checks(actor=actor):
        by_person.setdefault(c.person_id, []).append(c)
    out = []
    for p in people:
        st = person_status(p, by_person.get(p.person_id, []))
        if problems_only and all(v["state"] == "ok" for v in st.values()):
            continue
        out.append((p, st))
    return out


def problems(*, actor: Principal) -> list[dict[str, Any]]:
    """What needs doing, worst first: {'person', 'check', 'state', 'detail'}.
    Missing checks matter most once someone has started. Also supply staff the
    cover roster calls DBS-cleared with no cleared DBS on the record."""
    order = {"problem": 0, "missing": 1, "expired": 2, "overdue": 3, "pending": 4,
             "expiring": 5}
    out = []
    for p, st in record(actor=actor):
        for t, v in st.items():
            if v["state"] == "ok":
                continue
            c = v["check"]
            detail = {"missing": "not recorded" + ("" if p.has_started else
                                                   f" (starts {p.start_date})"),
                      "expired": f"expired {c.expires_on}" if c else "",
                      "overdue": f"Update Service check due {c.next_update_check_due}"
                      if c else "",
                      "expiring": f"expires {c.expires_on}" if c else "",
                      "pending": c.status if c else "",
                      "problem": c.status if c else ""}[v["state"]]
            rank = order[v["state"]] + (0 if p.has_started else 10)
            out.append({"person": p, "check": t, "state": v["state"], "detail": detail,
                        "rank": rank})
        if p.supply_id and st.get(DBS, {}).get("state") != "ok":
            s = CV.get_supply(p.supply_id)
            if s.dbs_cleared:
                out.append({"person": p, "check": DBS, "state": "problem", "rank": 0,
                            "detail": "cover roster says DBS cleared - no cleared DBS here"})
    return sorted(out, key=lambda x: (x["rank"], x["person"].full_name.lower(), x["check"]))


def reminders(*, actor: Principal, within_days: int = 30) -> list[dict[str, Any]]:
    """Renewals falling due within *within_days* (or overdue): Update Service
    checks and expiry dates (e.g. right to work). Soonest first."""
    horizon = (_today() + _dt.timedelta(days=int(within_days))).isoformat()
    out = []
    current = {p.person_id: p for p in list_people(actor=actor)}
    for p_id, checks in _group(list_checks(actor=actor)).items():
        if p_id not in current:
            continue
        for c in _latest(checks).values():
            if c.update_service_subscribed and c.next_update_check_due and \
                    c.next_update_check_due <= horizon:
                out.append({"person": current[p_id], "check": c, "due": c.next_update_check_due,
                            "what": "Update Service status check"})
            if c.expires_on and c.is_active and c.expires_on <= horizon:
                out.append({"person": current[p_id], "check": c, "due": c.expires_on,
                            "what": f"{c.check_type} expires"})
    return sorted(out, key=lambda x: (x["due"], x["person"].full_name.lower()))


def _group(checks: list[Check]) -> dict[int, list[Check]]:
    out: dict[int, list[Check]] = {}
    for c in checks:
        out.setdefault(c.person_id, []).append(c)
    return out


def summary(*, actor: Principal) -> dict[str, Any]:
    """The old DBS summary plus the record's totals."""
    dbs = list_checks(actor=actor, check_type=DBS)
    rows = record(actor=actor)
    states = Counter(v["state"] for _p, st in rows for v in st.values())
    return {"people": len(rows), "complete": sum(1 for _p, st in rows
                                                 if all(v["state"] == "ok"
                                                        for v in st.values())),
            "states": dict(states), "by_category": dict(Counter(p.category for p, _s in rows)),
            "dbs_total": len(dbs), "dbs_active": sum(1 for c in dbs if c.is_active),
            "dbs_pending": sum(1 for c in dbs if c.status in ("Applied", "Pending",
                                                               "Awaiting Certificate")),
            "dbs_renewing": sum(1 for c in dbs if c.status == "Renewing"),
            "dbs_expired": sum(1 for c in dbs if c.is_expired),
            "dbs_expiring_soon": sum(1 for c in dbs if c.expiring_soon),
            "update_check_overdue": sum(1 for c in dbs if c.update_check_overdue),
            "update_service_subscribed": sum(1 for c in dbs if c.update_service_subscribed),
            "risk_assessment_pending": sum(1 for c in dbs if c.risk_pending),
            "unsigned": sum(1 for c in dbs if c.unsigned),
            "by_level": dict(Counter(c.dbs_level for c in dbs)),
            "by_status": dict(Counter(c.status for c in dbs)),
            "by_certificate_type": dict(Counter(c.certificate_type for c in dbs))}


# ── For inspection ───────────────────────────────────────────────────

def export_csv(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    """One row per person; for each check: status, date, who checked, reference."""
    rows = record(actor=actor, **filters)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        head = ["name", "username", "category", "post", "agency", "start", "left"]
        for t in CHECK_TYPES:
            head += [f"{t}: status", f"{t}: date", f"{t}: checked by", f"{t}: reference"]
        head += ["DBS: level", "DBS: number", "DBS: issued", "DBS: update service",
                 "DBS: last update check", "outstanding"]
        w.writerow(head)
        for p, st in rows:
            line = [_safe(p.full_name), _safe(p.username), p.category, _safe(p.role_title),
                    _safe(p.agency_name), p.start_date or "", p.end_date or ""]
            for t in CHECK_TYPES:
                v = st.get(t)
                c = v["check"] if v else None
                line += ["n/a" if v is None else (c.status if c else "MISSING"),
                         (c.checked_on or "") if c else "", _safe(c.checked_by) if c else "",
                         _safe(c.reference or c.dbs_number) if c else ""]
            d = st.get(DBS, {}).get("check")
            line += [d.dbs_level if d else "", _safe(d.dbs_number) if d else "",
                     d.issued_on or "" if d else "",
                     ("yes" if d.update_service_subscribed else "no") if d else "",
                     (d.last_update_check_on or "") if d else "",
                     "; ".join(f"{t} {v['state']}" for t, v in st.items()
                               if v["state"] != "ok")]
            w.writerow(line)
    activity_log.record("scr.export", principal=actor, rows=len(rows))
    return len(rows)


def scr_text(*, actor: Principal, **filters: Any) -> str:
    """The record as text, for printing at an inspection."""
    rows = record(actor=actor, **filters)
    out = [f"Single Central Record - printed {_today():%d %B %Y}", ""]
    for p, st in rows:
        out.append(f"{p.full_name}  [{p.category}]" + (f"  {p.role_title}" if p.role_title
                                                        else "")
                   + (f"  agency: {p.agency_name}" if p.agency_name else "")
                   + (f"  started {p.start_date}" if p.start_date else ""))
        for t, v in st.items():
            c = v["check"]
            mark = {"ok": "ok", "missing": "MISSING", "pending": "pending",
                    "expiring": "expiring", "expired": "EXPIRED", "overdue": "OVERDUE",
                    "problem": "PROBLEM"}[v["state"]]
            extra = ""
            if c:
                extra = f"{c.status:<26} {c.checked_on or '':<10} by {c.checked_by or '-':<14}"
                if c.check_type == DBS:
                    extra += (f" {c.dbs_level or ''} no. {c.dbs_number or '-'} issued "
                              f"{c.issued_on or '-'}"
                              + (f", Update Service checked {c.last_update_check_on or '-'}"
                                 if c.update_service_subscribed else ""))
                elif c.reference:
                    extra += f" ref {c.reference}"
                if c.expires_on:
                    extra += f" expires {c.expires_on}"
            out.append(f"    {t:<32} {mark:<9} {extra}".rstrip())
        out.append("")
    if not rows:
        out.append("(nobody on the record)")
    activity_log.record("scr.print", principal=actor, rows=len(rows))
    return "\n".join(out) + "\n"
