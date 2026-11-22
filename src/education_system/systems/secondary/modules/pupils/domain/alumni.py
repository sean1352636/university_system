"""Alumni: former pupils the school keeps in touch with.

Rules shared by the GUI and CLI:

* **From a leaver** (:func:`add_from_pupil`) - only a pupil who is off roll
  can become an alumnus. Their pupil record is *kept* (the old system deleted
  it); the alumni record copies name, date of birth, admission number, leaving
  date and the academic year they left, so it survives the pupil record being
  removed later. :func:`add_leavers` does a whole year's leavers at once.
* **Without a pupil record** (:func:`create_alumnus`) - for people who left
  before the school used this system. Same name + date of birth is refused as
  a likely duplicate unless confirmed.
* **Contact consent** - nobody is e-mailed unless they agreed. Turning consent
  on needs the date and how it was given; turning it off is always allowed.
  Only ``active`` alumni with consent and a personal e-mail are e-mailed
  (:func:`send_email`), and every e-mail says how to stop receiving them.
* **Status** - ``active`` / ``inactive`` / ``deceased``; moving to inactive or
  deceased needs a reason.
* **Delete** - for an erasure request or a record made in error; needs a
  reason. The audit trail only ever holds field *names*, never values, so a
  deleted alumnus leaves no personal data behind.

Only roles that may open the "Alumni" menu entry may use this (the check is
made here, not just in the screens).
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from dataclasses import dataclass, fields
from typing import Any

from education_system.systems.secondary.modules.admissions.domain import admissions as A
from education_system.systems.secondary.modules.pupils.domain import enrolment as EN
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

MENU_LABEL = "Alumni"
#: Pupils' school addresses close when they leave (see pupil_accounts).
SCHOOL_EMAIL_DOMAIN = "secondarysch.uk"

STATUSES: tuple[str, ...] = ("active", "inactive", "deceased")
STATUS_LABELS = {"active": "Active", "inactive": "Inactive", "deceased": "Deceased"}

ACTIVITIES: tuple[str, ...] = (
    "Sixth form or college",
    "University",
    "Apprenticeship",
    "Employed",
    "Self-employed",
    "Armed forces",
    "Gap year / travelling",
    "Looking for work",
    "Other",
)

CONSENT_SOURCES: tuple[str, ...] = (
    "Leavers' form", "E-mail", "Phone", "In person", "Online form", "Other",
)

EDITABLE_FIELDS: tuple[str, ...] = (
    "first_name", "last_name", "preferred_name", "date_of_birth", "leaving_year",
    "last_year_group", "email", "phone", "town", "current_activity", "organisation",
    "course_or_role", "can_help", "contact_consent", "consent_date", "consent_source",
    "notes",
)

FIELD_LABELS = {
    "first_name": "First name", "last_name": "Last name", "preferred_name": "Preferred name",
    "date_of_birth": "Date of birth", "leaving_year": "Year left",
    "last_year_group": "Last year group", "email": "Personal e-mail", "phone": "Phone",
    "town": "Town", "current_activity": "Now doing", "organisation": "Organisation",
    "course_or_role": "Course or job", "can_help": "Happy to help the school",
    "contact_consent": "Agreed to be contacted", "consent_date": "Consent date",
    "consent_source": "Consent given by", "notes": "Notes",
}

#: Placeholders allowed in an alumni e-mail.
PLACEHOLDERS: dict[str, str] = {
    "first_name": "Their preferred or first name",
    "name": "Their preferred first name and surname",
    "leaving_year": "The academic year they left",
}

UNSUBSCRIBE_FOOTER = (
    "\n\n--\nYou are receiving this because you agreed to hear from the school as a "
    "former pupil. To stop, reply to this e-mail or contact the school office.")

_SCHEMA = """
-- No foreign key to pupils: an alumnus outlives the pupil record.
CREATE TABLE IF NOT EXISTS alumni (
    alumni_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_ref       TEXT UNIQUE,
    pupil_id         INTEGER UNIQUE,
    admission_no     TEXT,
    first_name       TEXT NOT NULL,
    last_name        TEXT NOT NULL,
    preferred_name   TEXT,
    date_of_birth    TEXT,
    leaving_year     TEXT NOT NULL,
    last_year_group  INTEGER CHECK (last_year_group IS NULL OR last_year_group BETWEEN 7 AND 11),
    leaving_date     TEXT,
    email            TEXT,
    phone            TEXT,
    town             TEXT,
    current_activity TEXT,
    organisation     TEXT,
    course_or_role   TEXT,
    can_help         INTEGER NOT NULL DEFAULT 0 CHECK (can_help IN (0, 1)),
    contact_consent  INTEGER NOT NULL DEFAULT 0 CHECK (contact_consent IN (0, 1)),
    consent_date     TEXT,
    consent_source   TEXT,
    status           TEXT NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active', 'inactive', 'deceased')),
    status_reason    TEXT,
    notes            TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    created_by       TEXT,
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by       TEXT
);
CREATE INDEX IF NOT EXISTS ix_alumni_year ON alumni (leaving_year, last_name);

-- Field names only, never values: nothing personal survives a delete.
CREATE TABLE IF NOT EXISTS alumni_audit (
    audit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    alumni_id  INTEGER NOT NULL,
    alumni_ref TEXT,
    action     TEXT NOT NULL,
    actor      TEXT NOT NULL,
    detail     TEXT,
    at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_alumni_audit ON alumni_audit (alumni_id, audit_id);
"""

database.register_schema("alumni", _SCHEMA)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound


class DuplicateAlumnus(ValueError):
    """Someone with the same name and date of birth is already an alumnus."""

    def __init__(self, existing: Alumnus):
        super().__init__(f"{existing.display_name} ({existing.alumni_ref}) is already an "
                         "alumnus with the same name and date of birth")
        self.existing = existing


@dataclass(frozen=True)
class Alumnus:
    alumni_id: int
    alumni_ref: str
    pupil_id: int | None
    admission_no: str | None
    first_name: str
    last_name: str
    preferred_name: str | None
    date_of_birth: str | None
    leaving_year: str
    last_year_group: int | None
    leaving_date: str | None
    email: str | None
    phone: str | None
    town: str | None
    current_activity: str | None
    organisation: str | None
    course_or_role: str | None
    can_help: int
    contact_consent: int
    consent_date: str | None
    consent_source: str | None
    status: str
    status_reason: str | None
    notes: str | None
    created_at: str
    created_by: str | None
    updated_at: str
    updated_by: str | None

    @property
    def display_name(self) -> str:
        return f"{self.preferred_name or self.first_name} {self.last_name}"

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, self.status)

    @property
    def can_contact(self) -> bool:
        return bool(self.status == "active" and self.contact_consent and self.email)

    @property
    def contact_problem(self) -> str | None:
        """Why this alumnus won't be e-mailed (None if they will)."""
        if self.status != "active":
            return self.status_label
        if not self.contact_consent:
            return "No consent"
        if not self.email:
            return "No e-mail"
        return None


_FIELDS = tuple(f.name for f in fields(Alumnus))


def _row(r) -> Alumnus:
    return Alumnus(**{k: r[k] for k in _FIELDS})


# ── Helpers ─────────────────────────────────────────────────────────

def _require(actor: Principal, action: str, target: Any = None) -> None:
    if not actor.can_open(MENU_LABEL):
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise PermissionDenied("Your account doesn't have access to Alumni.")


def _audit(conn, a_id: int, ref: str | None, action: str, actor: Principal,
           detail: dict | None = None) -> None:
    conn.execute("INSERT INTO alumni_audit (alumni_id, alumni_ref, action, actor, detail) "
                 "VALUES (?, ?, ?, ?, ?)",
                 (a_id, ref, action, actor.username or "unknown",
                  json.dumps(detail, sort_keys=True) if detail else None))


_YEAR_RE = re.compile(r"^(\d{4})/(\d{2})$")


def year_of(date: str) -> str:
    """Academic year label ("2026/27") a date falls in."""
    return A.academic_year_label(P.academic_year_start(_dt.date.fromisoformat(date)).year)


def leaving_year_choices(today: _dt.date | None = None) -> list[str]:
    """This year back ten years, plus any older years already recorded."""
    start = P.academic_year_start(today).year
    years = {A.academic_year_label(y) for y in range(start - 10, start + 1)}
    with database.connect() as conn:
        years |= {r[0] for r in conn.execute("SELECT DISTINCT leaving_year FROM alumni")}
    return sorted(years, reverse=True)


def _validate(data: dict[str, Any], *, today: _dt.date, creating: bool) -> dict[str, Any]:
    problems: list[str] = []
    unknown = set(data) - set(EDITABLE_FIELDS)
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")
    out: dict[str, Any] = {}
    for key in ("first_name", "last_name"):
        if key in data or creating:
            out[key] = P._clean_text(data.get(key))
            if not out[key]:
                problems.append(f"{FIELD_LABELS[key]} is required")
    for key, limit in (("preferred_name", 100), ("town", 80), ("organisation", 120),
                       ("course_or_role", 120), ("notes", 2000)):
        if key in data:
            out[key] = P._clean_text(data.get(key), limit)
    if "date_of_birth" in data:
        dob = P._parse_date(data.get("date_of_birth"), "Date of birth", problems)
        if dob and dob > today.isoformat():
            problems.append("Date of birth can't be in the future")
        out["date_of_birth"] = dob
    if "leaving_year" in data or creating:
        year = P._clean_text(data.get("leaving_year"), 7)
        m = _YEAR_RE.match(year or "")
        if not m or (int(m.group(1)) + 1) % 100 != int(m.group(2)):
            problems.append("Year left must be an academic year like 2025/26")
        elif year > A.current_academic_year(today):
            problems.append("Year left can't be in the future")
        out["leaving_year"] = year
    if "last_year_group" in data:
        raw = data.get("last_year_group")
        if raw in (None, ""):
            out["last_year_group"] = None
        else:
            try:
                out["last_year_group"] = int(raw)
            except (TypeError, ValueError):
                out["last_year_group"] = None
            if out["last_year_group"] not in P.YEAR_GROUPS:
                problems.append("Last year group must be 7 to 11")
    if "email" in data:
        email = P._clean_text(data.get("email"), 254)
        email = email.lower() if email else None
        if email and not C.valid_email(email):
            problems.append("The e-mail address doesn't look right")
        if email and email.endswith("@" + SCHOOL_EMAIL_DOMAIN):
            problems.append("Use a personal e-mail - the school address closes when they leave")
        out["email"] = email
    if "phone" in data:
        phone = P._clean_text(data.get("phone"), 20)
        if phone and not C._PHONE_RE.match(phone):
            problems.append("The phone number doesn't look right")
        out["phone"] = phone
    if "current_activity" in data:
        act = P._clean_text(data.get("current_activity"), 60)
        if act and act not in ACTIVITIES:
            problems.append("Now doing must be one of: " + ", ".join(ACTIVITIES))
        out["current_activity"] = act
    for key in ("can_help", "contact_consent"):
        if key in data:
            out[key] = int(P._as_bool(data.get(key), FIELD_LABELS[key], problems))
    if "consent_date" in data:
        d = P._parse_date(data.get("consent_date"), "Consent date", problems)
        if d and d > today.isoformat():
            problems.append("Consent date can't be in the future")
        out["consent_date"] = d
    if "consent_source" in data:
        src = P._clean_text(data.get("consent_source"), 40)
        if src and src not in CONSENT_SOURCES:
            problems.append("Consent given by must be one of: " + ", ".join(CONSENT_SOURCES))
        out["consent_source"] = src
    if problems:
        raise ValidationError(problems)
    return out


def _check_consent(record: dict[str, Any]) -> None:
    """Consent on needs when and how; consent off clears both."""
    if record.get("contact_consent"):
        problems = []
        if not record.get("consent_date"):
            problems.append("Give the date they agreed to be contacted")
        if not record.get("consent_source"):
            problems.append("Say how they agreed to be contacted")
        if problems:
            raise ValidationError(problems)
    else:
        record["consent_date"] = None
        record["consent_source"] = None


def _insert(conn, record: dict[str, Any], actor: Principal) -> int:
    record = {**record, "created_by": actor.username, "updated_by": actor.username}
    cols = list(record)
    a_id = conn.execute(f"INSERT INTO alumni ({', '.join(cols)}) VALUES "
                        f"({', '.join('?' for _ in cols)})", list(record.values())).lastrowid
    ref = f"AL{a_id:06d}"
    conn.execute("UPDATE alumni SET alumni_ref = ? WHERE alumni_id = ?", (ref, a_id))
    _audit(conn, a_id, ref, "create", actor,
           {"from_pupil": record.get("pupil_id") is not None,
            "fields": sorted(k for k, v in record.items() if v not in (None, "", 0)
                             and k in EDITABLE_FIELDS)})
    return int(a_id)


# ── Read ─────────────────────────────────────────────────────────────

def get_alumnus(alumni_id: int) -> Alumnus | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM alumni WHERE alumni_id = ?",
                         (int(alumni_id),)).fetchone()
    return _row(r) if r else None


def for_pupil(pupil_id: int) -> Alumnus | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM alumni WHERE pupil_id = ?", (int(pupil_id),)).fetchone()
    return _row(r) if r else None


def find_by_reference(ref: str) -> Alumnus | None:
    """An alumni ref (AL000001) or the admission number they had."""
    ref = (ref or "").strip().upper()
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM alumni WHERE upper(alumni_ref) = ? OR "
                         "upper(admission_no) = ?", (ref, ref)).fetchone()
    return _row(r) if r else None


def list_alumni(*, search: str | None = None, status: str | None = None,
                leaving_year: str | None = None, activity: str | None = None,
                contactable: bool | None = None, can_help: bool | None = None,
                ) -> list[Alumnus]:
    """Alumni, newest year first then surname. All filters optional."""
    where, params = [], []
    if status:
        where.append("status = ?")
        params.append(status)
    if leaving_year:
        where.append("leaving_year = ?")
        params.append(leaving_year)
    if activity:
        where.append("current_activity = ?")
        params.append(activity)
    if can_help is not None:
        where.append("can_help = ?")
        params.append(int(can_help))
    if search and search.strip():
        like = f"%{search.strip().lower()}%"
        where.append("(lower(first_name) LIKE ? OR lower(last_name) LIKE ? OR "
                     "lower(coalesce(preferred_name, '')) LIKE ? OR lower(alumni_ref) LIKE ? "
                     "OR lower(coalesce(admission_no, '')) LIKE ? OR "
                     "lower(coalesce(email, '')) LIKE ? OR lower(coalesce(organisation, '')) "
                     "LIKE ?)")
        params += [like] * 7
    sql = "SELECT * FROM alumni" + (" WHERE " + " AND ".join(where) if where else "")
    sql += " ORDER BY leaving_year DESC, last_name COLLATE NOCASE, first_name COLLATE NOCASE"
    with database.connect() as conn:
        rows = [_row(r) for r in conn.execute(sql, params)]
    if contactable is not None:
        rows = [a for a in rows if a.can_contact == contactable]
    return rows


def history(alumni_id: int) -> list[dict[str, Any]]:
    with database.connect() as conn:
        rows = conn.execute("SELECT * FROM alumni_audit WHERE alumni_id = ? "
                            "ORDER BY audit_id DESC", (int(alumni_id),)).fetchall()
    return [{"at": r["at"], "actor": r["actor"], "action": r["action"],
             "detail": json.loads(r["detail"]) if r["detail"] else {}} for r in rows]


@dataclass(frozen=True)
class Summary:
    total: int
    by_status: dict[str, int]
    by_year: dict[str, int]
    contactable: int
    can_help: int


def summary() -> Summary:
    rows = list_alumni()
    by_status = {s: 0 for s in STATUSES}
    by_year: dict[str, int] = {}
    for a in rows:
        by_status[a.status] = by_status.get(a.status, 0) + 1
        by_year[a.leaving_year] = by_year.get(a.leaving_year, 0) + 1
    return Summary(len(rows), by_status, dict(sorted(by_year.items(), reverse=True)),
                   sum(a.can_contact for a in rows), sum(bool(a.can_help) for a in rows))


@dataclass(frozen=True)
class PupilLink:
    """What the alumni screens show about the linked pupil record."""

    pupil: P.Pupil | None
    post16_destination: str | None
    note: str | None


def pupil_link(alumnus: Alumnus) -> PupilLink:
    if alumnus.pupil_id is None:
        return PupilLink(None, None, "Added without a pupil record")
    pupil = P.get_pupil(alumnus.pupil_id)
    if pupil is None:
        return PupilLink(None, None, "The pupil record has since been removed")
    dest = next((lv.post16_destination for lv in EN.leaving_history(pupil.pupil_id)
                 if lv.post16_destination), None)
    note = "Back on roll - check whether this alumni record is still wanted" \
        if pupil.roll_status == "on_roll" else None
    return PupilLink(pupil, dest, note)


def leavers_not_alumni(*, academic_year: str | None = None,
                       reasons: tuple[str, ...] | None = None,
                       search: str | None = None) -> list[P.Pupil]:
    """Pupils off roll who don't have an alumni record yet."""
    with database.connect() as conn:
        linked = {r[0] for r in conn.execute(
            "SELECT pupil_id FROM alumni WHERE pupil_id IS NOT NULL")}
    out = []
    for p in P.list_pupils(roll_status="left", search=search or None):
        if p.pupil_id in linked or not p.leaving_date:
            continue
        if academic_year and year_of(p.leaving_date) != academic_year:
            continue
        if reasons and p.leaving_reason not in reasons:
            continue
        out.append(p)
    return sorted(out, key=lambda p: (p.leaving_date or "", p.legal_last_name), reverse=True)


# ── Create ───────────────────────────────────────────────────────────

def _from_pupil_record(pupil: P.Pupil) -> dict[str, Any]:
    return {
        "pupil_id": pupil.pupil_id, "admission_no": pupil.admission_no,
        "first_name": pupil.legal_first_name, "last_name": pupil.legal_last_name,
        "preferred_name": pupil.preferred_name, "date_of_birth": pupil.date_of_birth,
        "leaving_year": year_of(pupil.leaving_date),  # type: ignore[arg-type]
        "last_year_group": pupil.year_group, "leaving_date": pupil.leaving_date,
        "town": pupil.town,
    }


def add_from_pupil(pupil_id: int, extras: dict[str, Any] | None = None, *,
                   actor: Principal, today: _dt.date | None = None) -> Alumnus:
    """Make an alumnus of a pupil who has left. The pupil record is kept.
    *extras* may set the contact / now-doing / consent fields."""
    today = today or _dt.date.today()
    _require(actor, "alumni.create", f"pupil:{pupil_id}")
    pupil = P.get_pupil(pupil_id)
    if pupil is None:
        activity_log.record("alumni.create", target=f"pupil:{pupil_id}", outcome="not_found",
                            principal=actor)
        raise NotFound(f"No pupil with id {pupil_id}")
    problems = []
    if pupil.roll_status != "left" or not pupil.leaving_date:
        problems.append(f"{pupil.display_name} is still on roll - record them as a leaver "
                        "first (Enrolment & Leavers)")
    existing = for_pupil(pupil_id)
    if existing:
        problems.append(f"{pupil.display_name} is already an alumnus ({existing.alumni_ref})")
    extras = dict(extras or {})
    bad = set(extras) & {"first_name", "last_name", "date_of_birth", "leaving_year",
                         "last_year_group"}
    if bad:
        problems.append("Name, date of birth and year left come from the pupil record")
    if problems:
        activity_log.record("alumni.create", target=pupil.admission_no, outcome="invalid",
                            principal=actor, problems=len(problems))
        raise ValidationError(problems)
    try:
        clean = _validate(extras, today=today, creating=False)
        record = {**_from_pupil_record(pupil), **{k: v for k, v in clean.items()
                                                  if v not in (None, "")}}
        record.setdefault("contact_consent", 0)
        _check_consent(record)
    except ValidationError as e:
        activity_log.record("alumni.create", target=pupil.admission_no, outcome="invalid",
                            principal=actor, problems=len(e.problems))
        raise
    with database.connect() as conn:
        a_id = _insert(conn, record, actor)
    activity_log.record("alumni.create", target=f"alumni:{a_id}", principal=actor,
                        pupil=pupil.admission_no)
    return get_alumnus(a_id)  # type: ignore[return-value]


def add_leavers(academic_year: str, *, actor: Principal,
                reasons: tuple[str, ...] = (EN.END_OF_Y11,)) -> list[Alumnus]:
    """Make alumni of every leaver of *academic_year* (by default the end of
    Year 11 leavers) who isn't one yet. Consent starts off: no one is e-mailed
    until they agree."""
    _require(actor, "alumni.add_leavers", academic_year)
    pupils = leavers_not_alumni(academic_year=academic_year, reasons=reasons)
    with database.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        linked = {r[0] for r in conn.execute(
            "SELECT pupil_id FROM alumni WHERE pupil_id IS NOT NULL")}
        ids = [_insert(conn, {**_from_pupil_record(p), "contact_consent": 0}, actor)
               for p in pupils if p.pupil_id not in linked]
    activity_log.record("alumni.add_leavers", target=academic_year, principal=actor,
                        added=len(ids))
    return [get_alumnus(i) for i in ids]  # type: ignore[misc]


def create_alumnus(data: dict[str, Any], *, actor: Principal, allow_duplicate: bool = False,
                   today: _dt.date | None = None) -> Alumnus:
    """Add a former pupil who has no pupil record in this system."""
    today = today or _dt.date.today()
    _require(actor, "alumni.create", "new")
    try:
        record = _validate(data, today=today, creating=True)
        record.setdefault("contact_consent", 0)
        _check_consent(record)
    except ValidationError as e:
        activity_log.record("alumni.create", outcome="invalid", principal=actor,
                            problems=len(e.problems))
        raise
    if not allow_duplicate and record.get("date_of_birth"):
        with database.connect() as conn:
            r = conn.execute(
                "SELECT * FROM alumni WHERE lower(first_name) = ? AND lower(last_name) = ? "
                "AND date_of_birth = ?", (record["first_name"].lower(),
                                          record["last_name"].lower(),
                                          record["date_of_birth"])).fetchone()
        if r:
            activity_log.record("alumni.create", outcome="possible_duplicate",
                                principal=actor, existing=r["alumni_ref"])
            raise DuplicateAlumnus(_row(r))
    with database.connect() as conn:
        a_id = _insert(conn, record, actor)
    activity_log.record("alumni.create", target=f"alumni:{a_id}", principal=actor)
    return get_alumnus(a_id)  # type: ignore[return-value]


# ── Update / status / delete ─────────────────────────────────────────

def _get_or_raise(alumni_id: int, action: str, actor: Principal) -> Alumnus:
    a = get_alumnus(alumni_id)
    if a is None:
        activity_log.record(action, target=f"alumni:{alumni_id}", outcome="not_found",
                            principal=actor)
        raise NotFound(f"No alumnus with id {alumni_id}")
    return a


def update_alumnus(alumni_id: int, changes: dict[str, Any], *, actor: Principal,
                   today: _dt.date | None = None) -> tuple[Alumnus, list[str]]:
    """Change some fields; returns (alumnus, changed field names). For one
    linked to a pupil record, name / date of birth / year left can't change
    here - correct the pupil record instead."""
    today = today or _dt.date.today()
    target = f"alumni:{alumni_id}"
    _require(actor, "alumni.update", target)
    current = _get_or_raise(alumni_id, "alumni.update", actor)
    try:
        if current.pupil_id is not None:
            locked = {k for k in ("first_name", "last_name", "date_of_birth", "leaving_year",
                                  "last_year_group") if k in changes
                      and str(changes[k] or "") != str(getattr(current, k) or "")}
            if locked:
                raise ValidationError([
                    "Name, date of birth and year left come from the pupil record: "
                    + ", ".join(FIELD_LABELS[k] for k in sorted(locked))])
        clean = _validate(changes, today=today, creating=False)
        merged = {k: getattr(current, k) for k in EDITABLE_FIELDS}
        merged.update(clean)
        if "contact_consent" in clean and clean["contact_consent"] and \
                not current.contact_consent and "consent_date" not in clean:
            merged["consent_date"] = None  # a fresh agreement needs its own date
        _check_consent(merged)
    except ValidationError as e:
        activity_log.record("alumni.update", target=target, outcome="invalid", principal=actor,
                            problems=len(e.problems))
        raise
    changed = sorted(k for k in EDITABLE_FIELDS if merged.get(k) != getattr(current, k))
    if changed:
        with database.connect() as conn:
            conn.execute(f"UPDATE alumni SET {', '.join(f'{k} = ?' for k in changed)}, "
                         "updated_at = datetime('now'), updated_by = ? WHERE alumni_id = ?",
                         [merged[k] for k in changed] + [actor.username, alumni_id])
            _audit(conn, alumni_id, current.alumni_ref, "update", actor, {"fields": changed})
    activity_log.record("alumni.update", target=target, principal=actor,
                        outcome="ok" if changed else "no_change", fields=changed or None)
    return get_alumnus(alumni_id), changed  # type: ignore[return-value]


def set_status(alumni_id: int, status: str, *, actor: Principal,
               reason: str | None = None) -> Alumnus:
    target = f"alumni:{alumni_id}"
    _require(actor, "alumni.status", target)
    current = _get_or_raise(alumni_id, "alumni.status", actor)
    problems = []
    reason = P._clean_text(reason, 300)
    if status not in STATUSES:
        problems.append("Status must be one of: " + ", ".join(STATUS_LABELS.values()))
    elif status == current.status:
        problems.append(f"Already {current.status_label.lower()}")
    elif status != "active" and not reason:
        problems.append(f"Say why the record is being marked {STATUS_LABELS[status].lower()}")
    if problems:
        activity_log.record("alumni.status", target=target, outcome="invalid", principal=actor,
                            problems=len(problems))
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("UPDATE alumni SET status = ?, status_reason = ?, updated_at = "
                     "datetime('now'), updated_by = ? WHERE alumni_id = ?",
                     (status, reason, actor.username, alumni_id))
        _audit(conn, alumni_id, current.alumni_ref, "status", actor,
               {"from": current.status, "to": status})
    activity_log.record("alumni.status", target=target, principal=actor, status=status)
    return get_alumnus(alumni_id)  # type: ignore[return-value]


def delete_alumnus(alumni_id: int, *, actor: Principal, reason: str) -> Alumnus:
    """Remove an alumni record (erasure request / made in error). The pupil
    record, if any, is not touched."""
    target = f"alumni:{alumni_id}"
    _require(actor, "alumni.delete", target)
    current = _get_or_raise(alumni_id, "alumni.delete", actor)
    reason = P._clean_text(reason, 300) or ""
    if not reason:
        activity_log.record("alumni.delete", target=target, outcome="invalid", principal=actor)
        raise ValidationError(["Say why the record is being deleted"])
    with database.connect() as conn:
        conn.execute("DELETE FROM alumni WHERE alumni_id = ?", (alumni_id,))
        _audit(conn, alumni_id, current.alumni_ref, "delete", actor, {"reason": reason})
    activity_log.record("alumni.delete", target=target, principal=actor)
    return current


# ── E-mail ───────────────────────────────────────────────────────────

_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_]+)\}")


def personalise(text: str, a: Alumnus) -> str:
    values = {"first_name": a.preferred_name or a.first_name, "name": a.display_name,
              "leaving_year": a.leaving_year}
    return _PLACEHOLDER_RE.sub(lambda m: values.get(m.group(1), m.group(0)), text)


@dataclass(frozen=True)
class EmailPlan:
    """Who an alumni e-mail would reach, before anything is saved."""

    recipients: list[Alumnus]
    skipped: list[tuple[Alumnus, str]]


def plan_email(alumni_ids: list[int]) -> EmailPlan:
    to, skipped, seen = [], [], set()
    for a_id in dict.fromkeys(alumni_ids):
        a = get_alumnus(a_id)
        if a is None:
            continue
        problem = a.contact_problem
        if problem is None and a.email in seen:
            problem = "Same e-mail as another alumnus"
        if problem:
            skipped.append((a, problem))
        else:
            seen.add(a.email)
            to.append(a)
    return EmailPlan(to, skipped)


def send_email(subject: str, body: str, alumni_ids: list[int], *,
               actor: Principal) -> tuple[int, EmailPlan]:
    """Save a personalised e-mail to the chosen alumni who can be contacted
    (others are skipped and reported). Returns (message_id, plan); the caller
    runs ``email_outbox.deliver(message_id)`` next."""
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    _require(actor, "alumni.email", f"{len(alumni_ids)} chosen")
    subject = " ".join((subject or "").split())
    body = (body or "").replace("\r\n", "\n").strip()
    problems = []
    if not subject:
        problems.append("A subject is required")
    elif len(subject) > E.MAX_SUBJECT:
        problems.append(f"The subject is too long (over {E.MAX_SUBJECT} characters)")
    if not body:
        problems.append("The message is empty")
    elif len(body) > E.MAX_BODY:
        problems.append(f"The message is too long (over {E.MAX_BODY} characters)")
    bad = sorted({m for m in _PLACEHOLDER_RE.findall(subject + body) if m not in PLACEHOLDERS})
    if bad:
        problems.append("Unknown placeholder(s): " + ", ".join("{" + b + "}" for b in bad)
                        + ". Allowed: " + ", ".join("{" + k + "}" for k in PLACEHOLDERS))
    plan = plan_email(alumni_ids)
    if not plan.recipients and not problems:
        problems.append("None of the chosen alumni can be e-mailed (they need to be active, "
                        "have agreed to be contacted and have an e-mail address)")
    if problems:
        activity_log.record("alumni.email", outcome="invalid", principal=actor,
                            problems=len(problems))
        raise ValidationError(problems)
    n = len(plan.recipients)
    message_id = E.save_prepared(
        "alumni", f"{n} alumn{'us' if n == 1 else 'i'}", subject, body,
        [(a.email, a.display_name, personalise(subject, a),  # type: ignore[misc]
          personalise(body, a) + UNSUBSCRIBE_FOOTER) for a in plan.recipients], actor=actor)
    with database.connect() as conn:
        for a in plan.recipients:
            _audit(conn, a.alumni_id, a.alumni_ref, "email", actor,
                   {"message_id": message_id})
    activity_log.record("alumni.email", target=f"message:{message_id}", principal=actor,
                        recipients=n, skipped=len(plan.skipped) or None)
    return message_id, plan
