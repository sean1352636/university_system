"""Admissions: applications for a place, from received to admitted.

Routes
    ``normal_round`` - the Year 7 intake, applied for through the local
    authority; ``in_year`` - any other time, Years 7-11.

Places
    Each academic year and year group has a Published Admission Number (PAN).
    Places used = offers outstanding + offers accepted (+ pupils on roll in
    that year group, for the current academic year). A pupil whose EHC plan
    names the school must be admitted, and an upheld appeal is binding, so
    both are offered even when the year group is full.

Oversubscription order (School Admissions Code, typical published criteria)
    1. EHC plan naming the school (admitted, not ranked)
    2. Looked-after and previously looked-after children
    3. Siblings of pupils on roll
    4. Everyone else
    Within a criterion, nearest home first (unknown distance last), then
    earliest application.

Status flow (see :data:`TRANSITIONS`)::

    received ─┬─ offered ─┬─ accepted ── admitted
              │           ├─ declined
              ├─ waiting_list ─ offered
              └─ refused ── appeal_lodged ─┬─ offered (upheld)
                                           └─ appeal_dismissed
    (withdrawn from any open status)

Every change is written to ``application_events`` and the activity log (by
reference number only), and the parent is e-mailed at each decision from the
JSON templates in ``resources/email_templates/admission_*.json``. Admitting
creates the pupil record, their login and school e-mail (with the welcome
e-mail) and adds the parent as their first contact.

Only roles allowed to open the "Admissions" menu entry (``access.RESTRICTED``)
may use any of this - applications hold looked-after and SEN details.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import re
from contextlib import contextmanager
from dataclasses import dataclass, field, fields
from typing import Any, Iterator

from education_system.systems.secondary.modules.communication.domain import email_outbox as E
from education_system.systems.secondary.modules.communication.domain import email_templates
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.core.academic_calendar.school_year import label as academic_year_label
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

logger = logging.getLogger(__name__)

MENU_LABEL = "Admissions"
OFFER_DAYS = 14

ROUTES: dict[str, str] = {"normal_round": "Year 7 normal round", "in_year": "In-year"}
LOOKED_AFTER: dict[str, str] = {
    "no": "No",
    "current": "Looked after",
    "previous": "Previously looked after",
}

STATUS_LABELS: dict[str, str] = {
    "received": "Received",
    "offered": "Offered",
    "waiting_list": "Waiting list",
    "refused": "Refused",
    "accepted": "Accepted",
    "declined": "Declined",
    "admitted": "Admitted",
    "withdrawn": "Withdrawn",
    "appeal_lodged": "Appeal lodged",
    "appeal_dismissed": "Appeal dismissed",
}
TRANSITIONS: dict[str, frozenset[str]] = {
    "received": frozenset({"offered", "waiting_list", "refused", "withdrawn"}),
    "waiting_list": frozenset({"offered", "withdrawn"}),
    "offered": frozenset({"accepted", "declined", "withdrawn"}),
    "accepted": frozenset({"admitted", "withdrawn"}),
    "refused": frozenset({"appeal_lodged", "waiting_list", "withdrawn"}),
    "appeal_lodged": frozenset({"offered", "appeal_dismissed", "withdrawn"}),
    "appeal_dismissed": frozenset({"waiting_list", "withdrawn"}),
    "declined": frozenset(),
    "admitted": frozenset(),
    "withdrawn": frozenset(),
}
OPEN_STATUSES = frozenset(s for s, nxt in TRANSITIONS.items() if nxt)
#: Statuses that hold a place against the PAN.
HOLDING_PLACE = ("offered", "accepted")

CRITERIA: dict[int, str] = {
    0: "EHC plan names the school",
    1: "Looked after / previously looked after",
    2: "Sibling on roll",
    3: "Other applicants",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS admission_places (
    academic_year TEXT NOT NULL,
    year_group    INTEGER NOT NULL CHECK (year_group BETWEEN 7 AND 11),
    pan           INTEGER NOT NULL CHECK (pan BETWEEN 0 AND 1000),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by    TEXT,
    PRIMARY KEY (academic_year, year_group)
);

CREATE TABLE IF NOT EXISTS applications (
    application_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    reference            TEXT UNIQUE,
    route                TEXT NOT NULL CHECK (route IN ('normal_round', 'in_year')),
    academic_year        TEXT NOT NULL,
    year_group           INTEGER NOT NULL CHECK (year_group BETWEEN 7 AND 11),
    legal_first_name     TEXT NOT NULL,
    middle_names         TEXT,
    legal_last_name      TEXT NOT NULL,
    preferred_name       TEXT,
    date_of_birth        TEXT NOT NULL,
    gender               TEXT NOT NULL,
    upn                  TEXT,
    current_school       TEXT,
    address_line1        TEXT,
    address_line2        TEXT,
    town                 TEXT,
    postcode             TEXT,
    distance_km          REAL,
    sen_status           TEXT NOT NULL DEFAULT 'N' CHECK (sen_status IN ('N', 'K', 'E')),
    ehcp_names_school    INTEGER NOT NULL DEFAULT 0 CHECK (ehcp_names_school IN (0, 1)),
    looked_after         TEXT NOT NULL DEFAULT 'no'
                         CHECK (looked_after IN ('no', 'current', 'previous')),
    sibling_admission_no TEXT,
    parent_name          TEXT NOT NULL,
    parent_relationship  TEXT NOT NULL,
    parent_email         TEXT,
    parent_phone         TEXT,
    received_date        TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'received',
    offer_expires        TEXT,
    offered_by_appeal    INTEGER NOT NULL DEFAULT 0,
    decision_note        TEXT,
    admitted_pupil_id    INTEGER,
    notes                TEXT,
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    created_by           TEXT,
    updated_at           TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by           TEXT
);
CREATE INDEX IF NOT EXISTS ix_applications_intake
    ON applications (academic_year, year_group, status);
CREATE INDEX IF NOT EXISTS ix_applications_child
    ON applications (legal_last_name, legal_first_name, date_of_birth);

-- No foreign key: the history stays if an application is ever removed.
CREATE TABLE IF NOT EXISTS application_events (
    event_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    at             TEXT NOT NULL DEFAULT (datetime('now')),
    actor          TEXT,
    action         TEXT NOT NULL,
    from_status    TEXT,
    to_status      TEXT,
    note           TEXT,
    detail         TEXT
);
CREATE INDEX IF NOT EXISTS ix_application_events_app ON application_events (application_id);
"""

database.register_schema("admissions", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


class DuplicateApplication(ValueError):
    def __init__(self, existing: "Application"):
        self.existing = existing
        super().__init__(f"{existing.child_name} (born {existing.date_of_birth}) already has "
                         f"an open application for {existing.academic_year}: "
                         f"{existing.reference} ({existing.status_label}).")


# ── Academic years ───────────────────────────────────────────────────

_YEAR_RE = re.compile(r"^(\d{4})/(\d{2})$")


def current_academic_year(today: _dt.date | None = None) -> str:
    return academic_year_label(P.academic_year_start(today).year)


def next_academic_year(today: _dt.date | None = None) -> str:
    return academic_year_label(P.academic_year_start(today).year + 1)


def academic_year_choices(today: _dt.date | None = None) -> list[str]:
    start = P.academic_year_start(today).year
    return [academic_year_label(y) for y in (start - 1, start, start + 1, start + 2)]


def year_start_date(academic_year: str) -> _dt.date:
    m = _YEAR_RE.match(academic_year or "")
    if not m:
        raise ValueError(academic_year)
    return _dt.date(int(m.group(1)), 9, 1)


def _valid_year(text: str) -> bool:
    m = _YEAR_RE.match(text or "")
    return bool(m) and (int(m.group(1)) + 1) % 100 == int(m.group(2))


# ── Model ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Application:
    application_id: int
    reference: str
    route: str
    academic_year: str
    year_group: int
    legal_first_name: str
    middle_names: str | None
    legal_last_name: str
    preferred_name: str | None
    date_of_birth: str
    gender: str
    upn: str | None
    current_school: str | None
    address_line1: str | None
    address_line2: str | None
    town: str | None
    postcode: str | None
    distance_km: float | None
    sen_status: str
    ehcp_names_school: bool
    looked_after: str
    sibling_admission_no: str | None
    parent_name: str
    parent_relationship: str
    parent_email: str | None
    parent_phone: str | None
    received_date: str
    status: str
    offer_expires: str | None
    offered_by_appeal: bool
    decision_note: str | None
    admitted_pupil_id: int | None
    notes: str | None
    created_at: str
    created_by: str | None
    updated_at: str
    updated_by: str | None

    @property
    def child_name(self) -> str:
        return f"{self.preferred_name or self.legal_first_name} {self.legal_last_name}"

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, self.status)

    @property
    def route_label(self) -> str:
        return ROUTES.get(self.route, self.route)

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    @property
    def criterion(self) -> int:
        if self.ehcp_names_school:
            return 0
        if self.looked_after in {"current", "previous"}:
            return 1
        if self.sibling_admission_no:
            return 2
        return 3

    @property
    def criterion_label(self) -> str:
        return CRITERIA[self.criterion]

    def rank_key(self) -> tuple:
        distance = self.distance_km if self.distance_km is not None else float("inf")
        return (self.criterion, distance, self.received_date, self.application_id)

    def next_statuses(self) -> frozenset[str]:
        return TRANSITIONS.get(self.status, frozenset())


_FIELDS = tuple(f.name for f in fields(Application))

EDITABLE_FIELDS: tuple[str, ...] = (
    "route", "academic_year", "year_group",
    "legal_first_name", "middle_names", "legal_last_name", "preferred_name",
    "date_of_birth", "gender", "upn", "current_school",
    "address_line1", "address_line2", "town", "postcode", "distance_km",
    "sen_status", "ehcp_names_school", "looked_after", "sibling_admission_no",
    "parent_name", "parent_relationship", "parent_email", "parent_phone",
    "received_date", "notes",
)

#: Readable names for the history and change lists.
FIELD_LABELS: dict[str, str] = {
    "route": "Route", "academic_year": "Academic year", "year_group": "Year group",
    "legal_first_name": "Legal first name", "middle_names": "Middle names",
    "legal_last_name": "Legal last name", "preferred_name": "Preferred name",
    "date_of_birth": "Date of birth", "gender": "Gender", "upn": "UPN",
    "current_school": "Current school", "address_line1": "Address line 1",
    "address_line2": "Address line 2", "town": "Town", "postcode": "Postcode",
    "distance_km": "Distance (km)", "sen_status": "SEN",
    "ehcp_names_school": "EHC plan names this school", "looked_after": "Looked after",
    "sibling_admission_no": "Sibling on roll", "parent_name": "Parent/carer name",
    "parent_relationship": "Relationship", "parent_email": "Parent e-mail",
    "parent_phone": "Parent phone", "received_date": "Date received", "notes": "Notes",
}


def _row(r) -> Application:
    values = {k: r[k] for k in _FIELDS}
    values["ehcp_names_school"] = bool(values["ehcp_names_school"])
    values["offered_by_appeal"] = bool(values["offered_by_appeal"])
    return Application(**values)


# ── Validation ───────────────────────────────────────────────────────

def _validate(data: dict[str, Any], *, today: _dt.date | None = None) -> dict[str, Any]:
    today = today or _dt.date.today()
    problems: list[str] = []
    unknown = set(data) - set(EDITABLE_FIELDS)
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    clean = P._clean_text
    out: dict[str, Any] = {}

    route = clean(data.get("route"), 20) or "in_year"
    if route not in ROUTES:
        problems.append("Route must be normal_round or in_year")
    out["route"] = route
    year_text = clean(data.get("academic_year"), 7) or ""
    if not _valid_year(year_text):
        problems.append("Academic year must look like 2026/27")
    out["academic_year"] = year_text
    try:
        year_group = int(data.get("year_group"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        year_group = None
    if year_group not in P.YEAR_GROUPS:
        problems.append("Year group must be 7, 8, 9, 10 or 11")
    elif route == "normal_round" and year_group != 7:
        problems.append("The normal admissions round is for Year 7 only - use in-year")
    out["year_group"] = year_group

    for key, label in (("legal_first_name", "Legal first name"),
                       ("legal_last_name", "Legal last name")):
        value = clean(data.get(key))
        if not value:
            problems.append(f"{label} is required")
        out[key] = value
    out["middle_names"] = clean(data.get("middle_names"))
    out["preferred_name"] = clean(data.get("preferred_name"))

    dob = P._parse_date(data.get("date_of_birth"), "Date of birth", problems)
    if dob is None and not any(p.startswith("Date of birth") for p in problems):
        problems.append("Date of birth is required")
    if dob and _valid_year(year_text):
        start = year_start_date(year_text)
        born = _dt.date.fromisoformat(dob)
        age = start.year - born.year - ((start.month, start.day) < (born.month, born.day))
        if not 10 <= age <= 16:
            problems.append(f"A child aged {age} on 1 September {start.year} doesn't fit "
                            "Years 7-11")
    out["date_of_birth"] = dob

    gender = P.gender_choice(clean(data.get("gender"), 20) or "")
    if gender not in P.GENDERS:
        problems.append(f"Gender must be one of: {', '.join(P.GENDERS)}")
    out["gender"] = gender

    upn = (clean(data.get("upn"), 13) or "").upper() or None
    if upn:
        bad = P.upn_problem(upn)
        if bad:
            problems.append(bad)
    out["upn"] = upn
    out["current_school"] = clean(data.get("current_school"))
    out["address_line1"] = clean(data.get("address_line1"))
    out["address_line2"] = clean(data.get("address_line2"))
    out["town"] = clean(data.get("town"))
    postcode = (clean(data.get("postcode"), 10) or "").upper() or None
    if postcode:
        if not P._POSTCODE_RE.match(postcode):
            problems.append("Postcode doesn't look like a UK postcode")
        elif " " not in postcode:
            postcode = f"{postcode[:-3]} {postcode[-3:]}"
    out["postcode"] = postcode
    raw_distance = data.get("distance_km")
    distance = None
    if raw_distance not in (None, ""):
        try:
            distance = round(float(raw_distance), 3)
            if not 0 <= distance <= 200:
                raise ValueError
        except (TypeError, ValueError):
            problems.append("Distance must be a number of kilometres from 0 to 200")
            distance = None
    out["distance_km"] = distance

    sen = (clean(data.get("sen_status"), 1) or "N").upper()
    if sen not in P.SEN_STATUSES:
        problems.append("SEN status must be N, K or E")
    out["sen_status"] = sen
    ehcp = P._as_bool(data.get("ehcp_names_school"), "EHC plan names this school", problems)
    if ehcp and sen != "E":
        problems.append("Only a child with an EHC plan (SEN status E) can have one naming "
                        "this school")
    out["ehcp_names_school"] = ehcp
    looked_after = (clean(data.get("looked_after"), 10) or "no").lower()
    if looked_after not in LOOKED_AFTER:
        problems.append("Looked after must be no, current or previous")
    out["looked_after"] = looked_after
    sibling = (clean(data.get("sibling_admission_no"), 12) or "").upper() or None
    if sibling:
        found = P.find_by_reference(sibling)
        if found is None or found.roll_status != "on_roll":
            problems.append(f"No pupil on roll with admission number {sibling}")
        else:
            sibling = found.admission_no
    out["sibling_admission_no"] = sibling

    out["parent_name"] = clean(data.get("parent_name"))
    if not out["parent_name"]:
        problems.append("Parent/carer name is required")
    relationship = clean(data.get("parent_relationship"), 20) or ""
    match = [r for r in C.RELATIONSHIPS if r.lower() == relationship.lower()]
    if not match:
        problems.append("Relationship must be one of: " + ", ".join(C.RELATIONSHIPS))
    out["parent_relationship"] = match[0] if match else relationship
    email = (clean(data.get("parent_email"), 254) or "").lower() or None
    if email and not C.valid_email(email):
        problems.append("Parent e-mail address doesn't look right")
    out["parent_email"] = email
    phone = clean(data.get("parent_phone"), 20)
    if phone and not C._PHONE_RE.match(phone):
        problems.append("Parent phone number doesn't look right")
    out["parent_phone"] = phone
    if not email and not phone:
        problems.append("Give a parent e-mail address or phone number")

    received = P._parse_date(data.get("received_date"), "Date received", problems)
    if received is None and not any(p.startswith("Date received") for p in problems):
        received = today.isoformat()
    if received and received > today.isoformat():
        problems.append("Date received can't be in the future")
    out["received_date"] = received
    out["notes"] = clean(data.get("notes"), 2000)
    if problems:
        raise ValidationError(problems)
    return out


def year_group_warning(app: Application | dict) -> str | None:
    """A note when the child's age doesn't match the year group applied for
    (allowed - out-of-cohort requests happen - but worth a second look)."""
    get = app.get if isinstance(app, dict) else lambda k: getattr(app, k)
    dob, year, group = get("date_of_birth"), get("academic_year"), get("year_group")
    try:
        expected = P.expected_year_group(str(dob), today=year_start_date(str(year)))
        group = int(group)
    except (TypeError, ValueError):
        return None
    if expected == group:
        return None
    return (f"By date of birth this child would be in Year {expected} in {year}, "
            f"not Year {group}.")


# ── Plumbing ─────────────────────────────────────────────────────────

def _require(actor: Principal, action: str, target: str | None = None) -> None:
    if not actor.can_open(MENU_LABEL):
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Your account doesn't have access to Admissions.")


@contextmanager
def _logged(action: str, actor: Principal, target: str | None) -> Iterator[None]:
    try:
        yield
    except PermissionDenied:
        raise  # already logged by _require
    except ValidationError as e:
        activity_log.record(action, target=target, outcome="invalid", principal=actor,
                            problems=len(e.problems))
        raise
    except DuplicateApplication as e:
        activity_log.record(action, target=target, outcome="possible_duplicate",
                            principal=actor, existing=e.existing.reference)
        raise
    except P.DuplicatePupil as e:
        activity_log.record(action, target=target, outcome="possible_duplicate_pupil",
                            principal=actor, existing=e.existing.admission_no)
        raise
    except NotFound:
        activity_log.record(action, target=target, outcome="not_found", principal=actor)
        raise
    except Exception as e:
        activity_log.record(action, target=target, outcome="error", principal=actor,
                            error=type(e).__name__)
        raise


def _event(conn, app_id: int, actor: Principal, action: str, from_status: str | None,
           to_status: str | None, note: str | None = None, detail: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO application_events (application_id, actor, action, from_status, "
        "to_status, note, detail) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (app_id, actor.username, action, from_status, to_status, note,
         json.dumps(detail, default=str) if detail else None))


def _ref_for(application_id: int) -> str:
    app = get_application(application_id)
    return app.reference if app else f"id:{application_id}"


# ── Read ─────────────────────────────────────────────────────────────

def get_application(application_id: int) -> Application | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM applications WHERE application_id = ?",
                         (int(application_id),)).fetchone()
    return _row(r) if r else None


def find_by_reference(reference: str) -> Application | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM applications WHERE reference = ? COLLATE NOCASE",
                         ((reference or "").strip(),)).fetchone()
    return _row(r) if r else None


def list_applications(*, academic_year: str | None = None, year_group: int | None = None,
                      status: str | None = None, search: str | None = None,
                      open_only: bool = False) -> list[Application]:
    """Applications, in oversubscription order within each intake."""
    sql = "SELECT * FROM applications WHERE 1 = 1"
    params: list[Any] = []
    if academic_year:
        sql += " AND academic_year = ?"
        params.append(academic_year)
    if year_group:
        sql += " AND year_group = ?"
        params.append(int(year_group))
    if status:
        sql += " AND status = ?"
        params.append(status)
    if search:
        like = f"%{search.strip()}%"
        sql += (" AND (legal_first_name LIKE ? OR legal_last_name LIKE ? OR preferred_name "
                "LIKE ? OR reference LIKE ? OR parent_name LIKE ? OR postcode LIKE ?)")
        params += [like] * 6
    with database.connect() as conn:
        rows = [_row(r) for r in conn.execute(sql, params).fetchall()]
    if open_only:
        rows = [a for a in rows if a.is_open]
    return sorted(rows, key=lambda a: (a.academic_year, a.year_group) + a.rank_key())


def waiting_list(academic_year: str, year_group: int) -> list[Application]:
    """The waiting list for one intake, in order (position 1 first)."""
    return [a for a in list_applications(academic_year=academic_year, year_group=year_group)
            if a.status == "waiting_list"]


def waiting_position(app: Application) -> int | None:
    if app.status != "waiting_list":
        return None
    for i, other in enumerate(waiting_list(app.academic_year, app.year_group), 1):
        if other.application_id == app.application_id:
            return i
    return None


def ranked_ahead(app: Application) -> list[Application]:
    """Waiting or unallocated applications for the same intake ranked above *app*."""
    key = app.rank_key()
    return [a for a in list_applications(academic_year=app.academic_year,
                                         year_group=app.year_group)
            if a.status in {"received", "waiting_list"}
            and a.application_id != app.application_id and a.rank_key() < key]


def history(application_id: int) -> list[dict]:
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM application_events WHERE application_id = ? ORDER BY event_id",
            (int(application_id),)).fetchall()
    out = []
    for r in rows:
        entry = dict(r)
        entry["detail"] = json.loads(r["detail"]) if r["detail"] else None
        out.append(entry)
    return out


# ── Places ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Places:
    academic_year: str
    year_group: int
    pan: int | None
    on_roll: int
    offered: int
    accepted: int

    @property
    def used(self) -> int:
        return self.on_roll + self.offered + self.accepted

    @property
    def available(self) -> int | None:
        return None if self.pan is None else max(self.pan - self.used, 0)

    @property
    def over_by(self) -> int:
        return 0 if self.pan is None else max(self.used - self.pan, 0)


def get_pan(academic_year: str, year_group: int) -> int | None:
    with database.connect() as conn:
        r = conn.execute("SELECT pan FROM admission_places WHERE academic_year = ? AND "
                         "year_group = ?", (academic_year, int(year_group))).fetchone()
    return r[0] if r else None


def set_pan(academic_year: str, year_group: int, pan: int, *, actor: Principal) -> None:
    target = f"{academic_year} Y{year_group}"
    _require(actor, "admission.places", target)
    problems = []
    if not _valid_year(academic_year):
        problems.append("Academic year must look like 2026/27")
    if year_group not in P.YEAR_GROUPS:
        problems.append("Year group must be 7-11")
    try:
        pan = int(pan)
        if not 0 <= pan <= 1000:
            raise ValueError
    except (TypeError, ValueError):
        problems.append("The admission number must be a whole number from 0 to 1000")
    if problems:
        activity_log.record("admission.places", target=target, outcome="invalid",
                            principal=actor, problems=len(problems))
        raise ValidationError(problems)
    old = get_pan(academic_year, year_group)
    with database.connect() as conn:
        conn.execute(
            "INSERT INTO admission_places (academic_year, year_group, pan, updated_by) "
            "VALUES (?, ?, ?, ?) ON CONFLICT (academic_year, year_group) DO UPDATE SET "
            "pan = excluded.pan, updated_at = datetime('now'), updated_by = excluded.updated_by",
            (academic_year, int(year_group), pan, actor.username))
    activity_log.record("admission.places", target=target, principal=actor,
                        old=old, new=pan)


def places(academic_year: str, year_group: int) -> Places:
    with database.connect() as conn:
        counts = dict(conn.execute(
            "SELECT status, COUNT(*) FROM applications WHERE academic_year = ? AND "
            "year_group = ? AND status IN ('offered', 'accepted') GROUP BY status",
            (academic_year, int(year_group))).fetchall())
    on_roll = 0
    if academic_year == current_academic_year():
        on_roll = len(P.list_pupils(year_group=int(year_group)))
    return Places(academic_year, int(year_group), get_pan(academic_year, year_group),
                  on_roll, counts.get("offered", 0), counts.get("accepted", 0))


# ── E-mails to parents ───────────────────────────────────────────────

def _email_parent(app: Application, template: str, actor: Principal,
                  extra: dict[str, Any] | None = None) -> tuple[int | None, str]:
    """Queue *template* to the parent. ``(message_id, note)``; never raises."""
    if not app.parent_email:
        activity_log.record("admission.email", target=app.reference, outcome="no_address",
                            principal=actor, template=template)
        return None, "no parent e-mail address - contact the family by phone"
    values = {
        "parent_name": app.parent_name,
        "child_first_name": app.preferred_name or app.legal_first_name,
        "child_name": app.child_name,
        "application_ref": app.reference,
        "year_group": app.year_group,
        "academic_year": app.academic_year,
        "route": app.route_label,
    }
    values.update(extra or {})
    try:
        subject, body = email_templates.load_template(template).render(values)
        message_id = E.send_to_address(app.parent_email, app.parent_name, subject, body,
                                       actor=actor, kind=f"admission:{template}",
                                       label=f"{template.replace('_', ' ')} to parent of "
                                             f"{app.reference}")
    except Exception as e:  # noqa: BLE001 - the decision stands; report the e-mail
        logger.exception("Admissions e-mail failed")
        activity_log.record("admission.email", target=app.reference, outcome="error",
                            principal=actor, template=template, error=type(e).__name__)
        return None, f"the e-mail to the parent could not be prepared: {e}"
    return message_id, "e-mail to parent queued"


def _nice_date(iso: str | None) -> str:
    if not iso:
        return ""
    d = _dt.date.fromisoformat(iso)
    return f"{d.day} {d:%B %Y}"


@dataclass
class Outcome:
    """The result of a change. Deliver ``message_ids`` next (the GUI does it
    off the Tk thread); ``notes`` are for the member of staff."""

    application: Application
    message_ids: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    pupil: P.Pupil | None = None
    login: Any = None  # pupil_accounts.NewAccount when a pupil was admitted

    def add_email(self, result: tuple[int | None, str]) -> None:
        message_id, note = result
        if message_id is not None:
            self.message_ids.append(message_id)
        self.notes.append(note)


# ── Create / edit ────────────────────────────────────────────────────

def _duplicate_of(conn, clean: dict, exclude_id: int | None = None) -> Application | None:
    rows = conn.execute(
        "SELECT * FROM applications WHERE lower(legal_first_name) = lower(?) AND "
        "lower(legal_last_name) = lower(?) AND date_of_birth = ? AND academic_year = ? "
        "AND application_id IS NOT ?",
        (clean["legal_first_name"], clean["legal_last_name"], clean["date_of_birth"],
         clean["academic_year"], exclude_id)).fetchall()
    for r in rows:
        app = _row(r)
        if app.is_open:
            return app
    return None


def create_application(data: dict[str, Any], *, actor: Principal,
                       allow_duplicate: bool = False) -> Outcome:
    """Record a new application and e-mail the parent an acknowledgement.

    Raises :class:`DuplicateApplication` if the same child already has an
    open application for that year (pass ``allow_duplicate=True`` to go on).
    """
    _require(actor, "admission.create", "new")
    with _logged("admission.create", actor, "new"):
        clean = _validate(data)
        with database.connect() as conn:
            if not allow_duplicate:
                existing = _duplicate_of(conn, clean)
                if existing:
                    raise DuplicateApplication(existing)
            cols = list(clean)
            cur = conn.execute(
                f"INSERT INTO applications ({', '.join(cols)}, created_by, updated_by) "
                f"VALUES ({', '.join('?' for _ in cols)}, ?, ?)",
                [int(v) if isinstance(v, bool) else v for v in clean.values()]
                + [actor.username, actor.username])
            app_id = cur.lastrowid
            reference = f"APP{app_id:05d}"
            conn.execute("UPDATE applications SET reference = ? WHERE application_id = ?",
                         (reference, app_id))
            _event(conn, app_id, actor, "create", None, "received")
    app = get_application(app_id)
    assert app is not None
    activity_log.record("admission.create", target=app.reference, principal=actor,
                        route=app.route, year_group=app.year_group,
                        academic_year=app.academic_year)
    outcome = Outcome(app)
    outcome.add_email(_email_parent(app, "admission_received", actor, {
        "received_date": _nice_date(app.received_date)}))
    return outcome


def update_application(application_id: int, changes: dict[str, Any], *,
                       actor: Principal) -> tuple[Application, list[str]]:
    """Change an open application's details. Returns it and the changed fields."""
    target = _ref_for(application_id)
    _require(actor, "admission.update", target)
    with _logged("admission.update", actor, target):
        current = get_application(application_id)
        if current is None:
            raise NotFound(f"No application with id {application_id}")
        if not current.is_open:
            raise ValidationError([f"A {current.status_label.lower()} application can't be "
                                   "changed"])
        if current.status in {"offered", "accepted"} and any(
                k in changes and str(changes[k]) != str(getattr(current, k))
                for k in ("academic_year", "year_group")):
            raise ValidationError(["Withdraw the offer before moving the application to a "
                                   "different year"])
        merged = {k: getattr(current, k) for k in EDITABLE_FIELDS}
        merged.update(changes)
        clean = _validate(merged)
        changed = sorted(k for k, v in clean.items() if getattr(current, k) != v)
        if changed:
            with database.connect() as conn:
                conn.execute(
                    f"UPDATE applications SET {', '.join(f'{k} = ?' for k in changed)}, "
                    "updated_at = datetime('now'), updated_by = ? WHERE application_id = ?",
                    [int(clean[k]) if isinstance(clean[k], bool) else clean[k]
                     for k in changed] + [actor.username, current.application_id])
                _event(conn, current.application_id, actor, "update", current.status,
                       current.status, detail={"fields": changed})
    activity_log.record("admission.update", target=target, principal=actor,
                        outcome="ok" if changed else "no_change", fields=changed or None)
    return get_application(application_id), changed  # type: ignore[return-value]


# ── Status changes ───────────────────────────────────────────────────

def _move(app: Application, to_status: str, actor: Principal, action: str, *,
          note: str | None = None, extra_sql: str = "", extra_params: tuple = ()) -> Application:
    if to_status not in app.next_statuses():
        raise ValidationError([f"A {app.status_label.lower()} application can't be moved to "
                               f"{STATUS_LABELS[to_status].lower()}"])
    with database.connect() as conn:
        cur = conn.execute(
            f"UPDATE applications SET status = ?, decision_note = ?{extra_sql}, "
            "updated_at = datetime('now'), updated_by = ? "
            "WHERE application_id = ? AND status = ?",
            (to_status, note, *extra_params, actor.username, app.application_id, app.status))
        if cur.rowcount != 1:
            raise ValidationError(["The application was changed by someone else - "
                                   "reopen it and try again"])
        _event(conn, app.application_id, actor, action, app.status, to_status, note)
    activity_log.record(f"admission.{action}", target=app.reference, principal=actor,
                        from_status=app.status, to_status=to_status)
    return get_application(app.application_id)  # type: ignore[return-value]


def _load(application_id: int, actor: Principal, action: str) -> Application:
    target = _ref_for(application_id)
    _require(actor, f"admission.{action}", target)
    app = get_application(application_id)
    if app is None:
        activity_log.record(f"admission.{action}", target=target, outcome="not_found",
                            principal=actor)
        raise NotFound(f"No application with id {application_id}")
    return app


def offer(application_id: int, *, actor: Principal, days: int = OFFER_DAYS,
          by_appeal: bool = False, note: str | None = None) -> Outcome:
    """Offer a place. Refused when the year group is full, unless the child's EHC
    plan names the school or an appeal was upheld."""
    app = _load(application_id, actor, "offer")
    with _logged("admission.offer", actor, app.reference):
        if by_appeal and app.status != "appeal_lodged":
            raise ValidationError(["Only an application with an appeal lodged can be offered "
                                   "by appeal"])
        if app.status == "appeal_lodged" and not by_appeal:
            raise ValidationError(["Record the appeal outcome to offer this place"])
        p = places(app.academic_year, app.year_group)
        if not (app.ehcp_names_school or by_appeal):
            ahead = ranked_ahead(app)
            if ahead:
                raise ValidationError([
                    f"{ahead[0].reference} ({ahead[0].criterion_label}) is ranked "
                    f"higher and still waiting - places must be offered in order "
                    f"({len(ahead)} ahead). Offer theirs first, or use Allocate places"])
            if p.pan is None:
                raise ValidationError([f"Set the admission number for Year {app.year_group} "
                                       f"in {app.academic_year} first (Places)"])
            if not p.available:
                raise ValidationError([f"Year {app.year_group} is full for {app.academic_year} "
                                       f"({p.used} of {p.pan} places used). Put the "
                                       "application on the waiting list instead"])
        try:
            days = int(days)
            if not 1 <= days <= 60:
                raise ValueError
        except (TypeError, ValueError):
            raise ValidationError(["Reply-by must be between 1 and 60 days"]) from None
        expires = (_dt.date.today() + _dt.timedelta(days=days)).isoformat()
        reason = note or ("Appeal upheld" if by_appeal else
                          "EHC plan names the school" if app.ehcp_names_school else None)
        moved = _move(app, "offered", actor, "appeal_upheld" if by_appeal else "offer",
                      note=reason, extra_sql=", offer_expires = ?, offered_by_appeal = ?",
                      extra_params=(expires, 1 if by_appeal else 0))
    outcome = Outcome(moved)
    outcome.add_email(_email_parent(moved, "admission_offer", actor, {
        "offer_expires": _nice_date(expires),
        "start_date": _nice_date(_start_date_for(moved).isoformat())}))
    return outcome


def _start_date_for(app: Application) -> _dt.date:
    start = year_start_date(app.academic_year)
    return max(start, _dt.date.today()) if app.route == "in_year" else start


def put_on_waiting_list(application_id: int, *, actor: Principal,
                        note: str | None = None) -> Outcome:
    app = _load(application_id, actor, "waiting_list")
    with _logged("admission.waiting_list", actor, app.reference):
        moved = _move(app, "waiting_list", actor, "waiting_list", note=note,
                      extra_sql=", offer_expires = NULL")
    outcome = Outcome(moved)
    outcome.add_email(_email_parent(moved, "admission_waiting_list", actor, {
        "waiting_position": waiting_position(moved) or "-"}))
    return outcome


def refuse(application_id: int, *, actor: Principal, reason: str) -> Outcome:
    """Refuse a place. A reason is required: it goes to the parent with their
    right of appeal."""
    app = _load(application_id, actor, "refuse")
    with _logged("admission.refuse", actor, app.reference):
        reason = P._clean_text(reason, 500) or ""
        if not reason:
            raise ValidationError(["Give the reason for refusing - the parent is told it"])
        if app.ehcp_names_school:
            raise ValidationError(["A child whose EHC plan names the school must be "
                                   "admitted - they can't be refused a place"])
        moved = _move(app, "refused", actor, "refuse", note=reason)
    outcome = Outcome(moved)
    outcome.add_email(_email_parent(moved, "admission_refused", actor, {"reason": reason}))
    return outcome


def record_acceptance(application_id: int, *, actor: Principal) -> Outcome:
    app = _load(application_id, actor, "accept")
    with _logged("admission.accept", actor, app.reference):
        moved = _move(app, "accepted", actor, "accept", note="Parent accepted the offer")
    return Outcome(moved)


def record_decline(application_id: int, *, actor: Principal, note: str | None = None) -> Outcome:
    app = _load(application_id, actor, "decline")
    with _logged("admission.decline", actor, app.reference):
        moved = _move(app, "declined", actor, "decline",
                      note=P._clean_text(note, 500) or "Parent declined the offer")
    return Outcome(moved)


def withdraw(application_id: int, *, actor: Principal, reason: str) -> Outcome:
    app = _load(application_id, actor, "withdraw")
    with _logged("admission.withdraw", actor, app.reference):
        reason = P._clean_text(reason, 500) or ""
        if not reason:
            raise ValidationError(["Give a reason for withdrawing the application"])
        moved = _move(app, "withdrawn", actor, "withdraw", note=reason)
    return Outcome(moved)


def lodge_appeal(application_id: int, *, actor: Principal, note: str | None = None) -> Outcome:
    app = _load(application_id, actor, "appeal")
    with _logged("admission.appeal", actor, app.reference):
        moved = _move(app, "appeal_lodged", actor, "appeal",
                      note=P._clean_text(note, 500) or "Appeal lodged")
    return Outcome(moved)


def decide_appeal(application_id: int, *, upheld: bool, actor: Principal,
                  note: str | None = None) -> Outcome:
    """Record the appeal panel's decision. Upheld = offer the place (binding,
    even if the year group is full)."""
    if upheld:
        return offer(application_id, actor=actor, by_appeal=True,
                     note=P._clean_text(note, 500) or "Appeal upheld")
    app = _load(application_id, actor, "appeal_dismissed")
    with _logged("admission.appeal_dismissed", actor, app.reference):
        moved = _move(app, "appeal_dismissed", actor, "appeal_dismissed",
                      note=P._clean_text(note, 500) or "Appeal dismissed")
    outcome = Outcome(moved)
    outcome.add_email(_email_parent(moved, "admission_appeal_dismissed", actor))
    return outcome


def lapse_expired_offers(*, actor: Principal, today: _dt.date | None = None) -> list[Application]:
    """Mark offers with no reply by their reply-by date as declined."""
    _require(actor, "admission.lapse")
    cutoff = (today or _dt.date.today()).isoformat()
    with database.connect() as conn:
        rows = [_row(r) for r in conn.execute(
            "SELECT * FROM applications WHERE status = 'offered' AND offer_expires < ? "
            # An EHC plan naming the school means it must admit: follow those up instead.
            "AND ehcp_names_school = 0", (cutoff,)).fetchall()]
    lapsed = []
    for app in rows:
        try:
            lapsed.append(_move(app, "declined", actor, "lapse",
                                note=f"Offer lapsed - no reply by {_nice_date(app.offer_expires)}"))
        except ValidationError:
            continue  # changed meanwhile
    activity_log.record("admission.lapse", principal=actor, lapsed=len(lapsed))
    return lapsed


# ── Allocation ───────────────────────────────────────────────────────

@dataclass
class Allocation:
    academic_year: str
    year_group: int
    offered: list[Application] = field(default_factory=list)
    waiting: list[Application] = field(default_factory=list)
    message_ids: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def allocation_preview(academic_year: str, year_group: int) -> tuple[list[Application],
                                                                     list[Application]]:
    """Who :func:`allocate` would offer and who would wait, without changing anything."""
    candidates = [a for a in list_applications(academic_year=academic_year,
                                               year_group=year_group)
                  if a.status in {"received", "waiting_list"}]
    p = places(academic_year, year_group)
    free = p.available or 0
    offer_list, wait_list = [], []
    # EHC plans first: they are always admitted, and they do take places.
    candidates.sort(key=lambda a: not a.ehcp_names_school)
    for app in candidates:  # otherwise already in oversubscription order
        if app.ehcp_names_school:
            offer_list.append(app)
            free -= 1
        elif free > 0:
            offer_list.append(app)
            free -= 1
        else:
            wait_list.append(app)
    return offer_list, wait_list


def allocate(academic_year: str, year_group: int, *, actor: Principal) -> Allocation:
    """Offer the free places in oversubscription order and put everyone else
    on the waiting list. EHC plans naming the school are always offered."""
    target = f"{academic_year} Y{year_group}"
    _require(actor, "admission.allocate", target)
    if get_pan(academic_year, year_group) is None:
        activity_log.record("admission.allocate", target=target, outcome="invalid",
                            principal=actor)
        raise ValidationError([f"Set the admission number for Year {year_group} in "
                               f"{academic_year} first (Places)"])
    offer_list, wait_list = allocation_preview(academic_year, year_group)
    result = Allocation(academic_year, year_group)
    for app in offer_list:
        try:
            o = offer(app.application_id, actor=actor)
        except ValidationError as e:
            result.notes.append(f"{app.reference}: {e}")
            continue
        result.offered.append(o.application)
        result.message_ids += o.message_ids
        result.notes += [f"{app.reference}: {n}" for n in o.notes if n.startswith(("no ", "the "))]
    for app in wait_list:
        if app.status == "waiting_list":
            result.waiting.append(app)
            continue
        o = put_on_waiting_list(app.application_id, actor=actor,
                                note="No place left at allocation")
        result.waiting.append(o.application)
        result.message_ids += o.message_ids
        result.notes += [f"{app.reference}: {n}" for n in o.notes if n.startswith(("no ", "the "))]
    activity_log.record("admission.allocate", target=target, principal=actor,
                        offered=len(result.offered), waiting=len(result.waiting))
    return result


# ── Admit ────────────────────────────────────────────────────────────

def admit(application_id: int, *, actor: Principal, admission_date: str | None = None,
          form_group: str | None = None, allow_duplicate: bool = False) -> Outcome:
    """Turn an accepted application into a pupil on roll.

    Creates the pupil record, their login and school e-mail (with the
    welcome e-mail), adds the parent as their first contact, and e-mails the
    parent to confirm. The admission date can't be in the future: admit a
    child on (or after) their first day. Raises :class:`pupils.DuplicatePupil`
    if a pupil with the same name and date of birth exists.
    """
    app = _load(application_id, actor, "admit")
    with _logged("admission.admit", actor, app.reference):
        if app.status != "accepted":
            raise ValidationError(["Only an accepted offer can be admitted - record the "
                                   "parent's acceptance first"])
        if not actor.can_edit_pupils:
            raise PermissionDenied("Your account can't create pupil records.")
        today = _dt.date.today()
        date = admission_date or today.isoformat()
        try:
            date = _dt.date.fromisoformat(date).isoformat()
        except ValueError:
            raise ValidationError(["Admission date must be a date in the form YYYY-MM-DD"]) \
                from None
        if date > today.isoformat():
            raise ValidationError(["The admission date can't be in the future - admit the "
                                   "pupil on their first day"])
        if date < year_start_date(app.academic_year).isoformat():
            raise ValidationError([f"This place is for {app.academic_year}; the admission "
                                   f"date can't be before 1 September "
                                   f"{year_start_date(app.academic_year).year}"])
        pupil = P.create_pupil({
            "legal_first_name": app.legal_first_name, "middle_names": app.middle_names,
            "legal_last_name": app.legal_last_name, "preferred_name": app.preferred_name,
            "date_of_birth": app.date_of_birth, "gender": app.gender, "upn": app.upn,
            "year_group": app.year_group, "form_group": form_group or None,
            "admission_date": date, "address_line1": app.address_line1,
            "address_line2": app.address_line2, "town": app.town, "postcode": app.postcode,
            "sen_status": app.sen_status,
        }, actor=actor, allow_duplicate=allow_duplicate)
        moved = _move(app, "admitted", actor, "admit",
                      note=f"Admitted as {pupil.admission_no}",
                      extra_sql=", admitted_pupil_id = ?", extra_params=(pupil.pupil_id,))
    outcome = Outcome(moved, pupil=pupil)
    try:
        C.add_contact(pupil.pupil_id, {
            "full_name": app.parent_name, "relationship": app.parent_relationship,
            "priority": 1, "email": app.parent_email, "phone": app.parent_phone,
            "parental_responsibility": True, "receives_email": bool(app.parent_email),
        }, actor=actor)
        outcome.notes.append("parent added as the first contact")
    except Exception as e:  # noqa: BLE001
        logger.exception("Adding parent contact failed")
        outcome.notes.append(f"the parent couldn't be added as a contact: {e}")
    from education_system.systems.secondary.modules.pupils.domain import pupil_accounts
    try:
        login = pupil_accounts.create_for_pupil(pupil.pupil_id, actor=actor)
        outcome.login = login
        if login.welcome_message_id is not None:
            outcome.message_ids.append(login.welcome_message_id)
        if login.welcome_error:
            outcome.notes.append(f"the pupil's welcome e-mail failed: {login.welcome_error}")
    except Exception as e:  # noqa: BLE001
        logger.exception("Creating login for admitted pupil failed")
        outcome.notes.append(f"the pupil's login couldn't be created ({e}) - use Create "
                             "login on their profile")
    school_email = outcome.login.account.school_email if outcome.login else ""
    outcome.add_email(_email_parent(moved, "admission_place_confirmed", actor, {
        "admission_no": pupil.admission_no,
        "start_date": _nice_date(date),
        "form_group": pupil.form_group or "to be confirmed",
        "school_email": school_email or "to be confirmed",
    }))
    return outcome


# ── Dashboard ────────────────────────────────────────────────────────

def open_counts() -> dict[str, int]:
    with database.connect() as conn:
        rows = conn.execute("SELECT status, COUNT(*) FROM applications GROUP BY status")
        counts = dict(rows.fetchall())
    return {s: counts.get(s, 0) for s in STATUS_LABELS}
