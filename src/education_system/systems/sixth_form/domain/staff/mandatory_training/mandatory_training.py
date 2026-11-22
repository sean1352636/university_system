"""Staff mandatory-training matrix for the Sixth Form System.

Which training each member of staff must hold, when they last did it and
when it runs out. Three things are configured by HR (or an admin):

* ``training_types`` — KCSIE annual read, safeguarding levels, DSL
  training, Prevent, first aid, fire marshal… each with a renewal period
  in months (none = once only) and how early "due soon" starts.
* ``training_requirements`` — who needs it: ``All staff``, a job role
  (``Role: Teacher``), a designation (``Designation: DSL`` / ``Tutor`` /
  ``Examiner``) or one named person (``Staff: T1234567`` — e.g. the fire
  marshals and first aiders).
* ``training_cpd_links`` — CPD activities that count as a type: once a
  member of staff's record on a linked activity is Attended/Completed in
  :mod:`..cpd`, the matrix counts it. Nothing is copied, so the CPD record
  stays the single source.

Completion evidence therefore comes from four places, and the matrix
takes the latest:

1. ``training_completions`` here (date, provider, certificate/evidence
   note, who recorded it; archived with a reason, never deleted);
2. linked CPD records (:mod:`..cpd`);
3. Prevent training records (:mod:`safeguarding.prevent_duty`) for any
   type whose evidence source is ``prevent`` — recording a completion of
   such a type writes the Prevent record, so there is one Prevent register;
4. the HR record's safeguarding-training dates (:mod:`..staff_hr`) for a
   type whose evidence source is ``hr_safeguarding``.

Each staff × type cell is Done, Due soon, Overdue or Missing (or blank
when not required). :func:`install_default_types` adds a standard UK list
of types and requirements on request — that is configuration, not data,
and nothing is recorded as completed.

Access: configuring types, recording completions and the whole-staff
matrix need ``HR``. Anyone with a staff record can see their own status
(:func:`my_status`).
"""

from __future__ import annotations

import calendar
import datetime as _dt
import logging
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator

from education_system import paths
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_STUDENTS_DB

DONE = "Done"
DUE_SOON = "Due soon"
OVERDUE = "Overdue"
MISSING = "Missing"
NOT_REQUIRED = ""
CELL_STATES: tuple[str, ...] = (DONE, DUE_SOON, OVERDUE, MISSING)

SOURCE_RECORD = "Training record"
SOURCE_CPD = "CPD"
SOURCE_PREVENT = "Prevent register"
SOURCE_HR = "HR record"

EVIDENCE_SOURCES: tuple[str, ...] = ("", "prevent", "hr_safeguarding")
EVIDENCE_SOURCE_LABELS = {"": "Training records / CPD only",
                          "prevent": "Also Prevent register",
                          "hr_safeguarding": "Also HR safeguarding dates"}

ALL_STAFF = "All staff"
DESIGNATIONS: tuple[str, ...] = ("DSL", "Tutor", "Examiner")
DEFAULT_DUE_SOON_DAYS = 60

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CODE_RE = re.compile(r"^[A-Z0-9_]{2,24}$")

#: A standard UK sixth-form list (type code, name, renewal months or None,
#: evidence source, requirements). Installed only on request.
DEFAULT_TRAINING_TYPES: tuple[tuple[str, str, int | None, str,
                                    tuple[str, ...]], ...] = (
    ("KCSIE", "KCSIE Part 1 — annual read and sign", 12, "",
     (ALL_STAFF,)),
    ("SG_L1", "Safeguarding — whole-staff (Level 1)", 12,
     "hr_safeguarding", (ALL_STAFF,)),
    ("SG_L2", "Safeguarding — Level 2 (pastoral staff)", 36, "",
     ("Role: Tutor", "Role: Head of Year", "Role: Pastoral Manager",
      "Role: Counsellor", "Role: Head of Sixth Form", "Designation: Tutor")),
    ("SG_L3", "Safeguarding — Level 3 (DSL / deputies)", 24, "",
     ("Designation: DSL",)),
    ("DSL", "Designated Safeguarding Lead training", 24, "",
     ("Designation: DSL",)),
    ("PREVENT", "Prevent duty awareness", 24, "prevent", (ALL_STAFF,)),
    ("ONLINE", "Online safety", 12, "", (ALL_STAFF,)),
    ("GDPR", "Data protection (UK GDPR)", 12, "", (ALL_STAFF,)),
    ("FIRE", "Fire safety awareness", 12, "", (ALL_STAFF,)),
    ("HS_IND", "Health & safety induction", None, "", (ALL_STAFF,)),
    ("FIRST_AID", "First aid at work", 36, "", ()),
    ("FIRE_MARSHAL", "Fire marshal / warden", 36, "", ()),
    ("SAFER_REC", "Safer recruitment", 60, "",
     ("Role: Principal", "Role: Vice Principal",
      "Role: Head of Sixth Form")),
    ("MANUAL", "Manual handling", 36, "", ("Role: Caretaker",)),
    ("ASBESTOS", "Asbestos awareness", 12, "", ("Role: Caretaker",)),
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS training_types (
    type_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    code           TEXT NOT NULL UNIQUE,
    name           TEXT NOT NULL,
    renewal_months INTEGER,
    due_soon_days  INTEGER NOT NULL DEFAULT 60,
    evidence_source TEXT NOT NULL DEFAULT '',
    description    TEXT,
    active         INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_training_types_name
    ON training_types(LOWER(name));

CREATE TABLE IF NOT EXISTS training_requirements (
    requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    type_id        INTEGER NOT NULL,
    applies_to     TEXT NOT NULL,
    created_at     TEXT DEFAULT (datetime('now')),
    UNIQUE(type_id, applies_to),
    FOREIGN KEY (type_id) REFERENCES training_types(type_id)
);

CREATE TABLE IF NOT EXISTS training_completions (
    completion_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id        TEXT NOT NULL,
    type_id         INTEGER NOT NULL,
    completed_on    TEXT NOT NULL,
    expires_on      TEXT,
    provider        TEXT,
    evidence        TEXT,
    recorded_by     TEXT,
    archived_at     TEXT,
    archived_by     TEXT,
    archived_reason TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (type_id) REFERENCES training_types(type_id)
);
CREATE INDEX IF NOT EXISTS idx_trc_staff ON training_completions(staff_id);
CREATE INDEX IF NOT EXISTS idx_trc_type  ON training_completions(type_id);

CREATE TABLE IF NOT EXISTS training_cpd_links (
    activity_id INTEGER NOT NULL,
    type_id     INTEGER NOT NULL,
    created_at  TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (activity_id, type_id),
    FOREIGN KEY (type_id) REFERENCES training_types(type_id)
);
"""


class ValidationError(ValueError):
    pass


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class TrainingType:
    type_id: int
    code: str
    name: str
    renewal_months: int | None
    due_soon_days: int
    evidence_source: str
    description: str | None
    active: bool
    created_at: str
    updated_at: str
    requirements: list[str] = field(default_factory=list)

    @property
    def renewal_label(self) -> str:
        if not self.renewal_months:
            return "Once"
        if self.renewal_months % 12 == 0:
            n = self.renewal_months // 12
            return "Annual" if n == 1 else f"Every {n} years"
        return f"Every {self.renewal_months} months"


@dataclass
class Completion:
    completion_id: int
    staff_id: str
    type_id: int
    completed_on: str
    expires_on: str | None
    provider: str | None
    evidence: str | None
    recorded_by: str | None
    archived_at: str | None
    archived_by: str | None
    archived_reason: str | None
    created_at: str


@dataclass
class Evidence:
    """One piece of evidence for a staff × type cell, from any source."""
    source: str
    ref: str
    staff_id: str
    type_id: int
    completed_on: str
    expires_on: str | None
    provider: str | None = None
    evidence: str | None = None


@dataclass
class Cell:
    staff_id: str
    staff_name: str
    type_id: int
    type_name: str
    required: bool
    state: str
    latest: Evidence | None = None

    @property
    def expires_on(self) -> str | None:
        return self.latest.expires_on if self.latest else None

    @property
    def completed_on(self) -> str | None:
        return self.latest.completed_on if self.latest else None

    def days_left(self, today: _dt.date | None = None) -> int | None:
        if not self.expires_on:
            return None
        return (_dt.date.fromisoformat(self.expires_on)
                - (today or _dt.date.today())).days


@dataclass
class TypeCompliance:
    type_id: int
    name: str
    required: int = 0
    done: int = 0
    due_soon: int = 0
    overdue: int = 0
    missing: int = 0

    @property
    def percent(self) -> float | None:
        if not self.required:
            return None
        return round(100 * (self.done + self.due_soon) / self.required, 1)


# ── DB plumbing ─────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[_sql.Connection]:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Mandatory training schema ready at %s", DB_PATH)
    _DB_READY = True


def _type(r: _sql.Row, reqs: list[str] | None = None) -> TrainingType:
    return TrainingType(
        type_id=r["type_id"], code=r["code"], name=r["name"],
        renewal_months=r["renewal_months"],
        due_soon_days=r["due_soon_days"],
        evidence_source=r["evidence_source"] or "",
        description=r["description"], active=bool(r["active"]),
        created_at=r["created_at"], updated_at=r["updated_at"],
        requirements=list(reqs or []))


def _completion(r: _sql.Row) -> Completion:
    return Completion(**{k: r[k] for k in Completion.__dataclass_fields__})


# ── Helpers ─────────────────────────────────────────────────────────

def _text(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _require(v: Any, label: str) -> str:
    s = _text(v)
    if not s:
        raise ValidationError(f"{label} is required")
    return s


def _date(v: Any, label: str, *, required: bool = False) -> str | None:
    s = _text(v)
    if not s:
        if required:
            raise ValidationError(f"{label} is required")
        return None
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _int(v: Any, label: str, *, minimum: int = 0,
         allow_blank: bool = True) -> int | None:
    if v in (None, ""):
        if allow_blank:
            return None
        raise ValidationError(f"{label} is required")
    try:
        n = int(str(v).strip())
    except ValueError:
        raise ValidationError(f"{label} must be a whole number") from None
    if n < minimum:
        raise ValidationError(f"{label} must be at least {minimum}")
    return n


def add_months(d: str, months: int) -> str:
    base = _dt.date.fromisoformat(d)
    m = base.month - 1 + months
    y, m = base.year + m // 12, m % 12 + 1
    day = min(base.day, calendar.monthrange(y, m)[1])
    return _dt.date(y, m, day).isoformat()


def _need_hr(action: str) -> access.Principal:
    p = access.current()
    p.require(access.HR, action)
    return p


def _staff_module():
    from education_system.systems.sixth_form.domain.staff import (
        staff as _staff,
    )
    return _staff


def _validate_staff(staff_id: Any) -> str:
    sid = _require(staff_id, "Staff member")
    if _staff_module().get_staff(sid) is None:
        raise ValidationError(f"No staff member with id {sid}")
    return sid


def requirement_targets() -> list[str]:
    """Every ``applies_to`` value a requirement may take (except the
    per-person ``Staff: <id>`` form)."""
    return ([ALL_STAFF]
            + [f"Role: {r}" for r in _staff_module().ROLES]
            + [f"Designation: {d}" for d in DESIGNATIONS])


def _validate_target(v: Any) -> str:
    s = _require(v, "Applies to")
    if s.lower() == ALL_STAFF.lower():
        return ALL_STAFF
    kind, _, rest = s.partition(":")
    kind, rest = kind.strip().lower(), rest.strip()
    if kind == "role":
        for r in _staff_module().ROLES:
            if r.lower() == rest.lower():
                return f"Role: {r}"
        raise ValidationError(f"Unknown job role '{rest}'")
    if kind == "designation":
        for d in DESIGNATIONS:
            if d.lower() == rest.lower():
                return f"Designation: {d}"
        raise ValidationError(
            f"Designation must be one of: {', '.join(DESIGNATIONS)}")
    if kind == "staff":
        return f"Staff: {_validate_staff(rest)}"
    raise ValidationError(
        "Applies to must be 'All staff', 'Role: <job role>', "
        "'Designation: DSL/Tutor/Examiner' or 'Staff: <staff id>'")


def _applies(target: str, s: Any) -> bool:
    if target == ALL_STAFF:
        return True
    kind, _, rest = target.partition(": ")
    if kind == "Role":
        return s.role == rest
    if kind == "Staff":
        return s.staff_id == rest
    if rest == "DSL":
        return bool(s.is_dsl) or s.role in ("Safeguarding Lead (DSL)",
                                            "Deputy DSL")
    if rest == "Tutor":
        return bool(s.is_tutor) or s.role == "Tutor"
    if rest == "Examiner":
        return bool(s.is_examiner)
    return False


# ── Training types ──────────────────────────────────────────────────

def _requirements_map(conn: _sql.Connection) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    for r in conn.execute("SELECT type_id, applies_to FROM "
                          "training_requirements ORDER BY applies_to"):
        out.setdefault(r["type_id"], []).append(r["applies_to"])
    return out


def list_types(*, active_only: bool = False) -> list[TrainingType]:
    init_db()
    sql = "SELECT * FROM training_types"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY name COLLATE NOCASE"
    with _connect() as conn:
        reqs = _requirements_map(conn)
        return [_type(r, reqs.get(r["type_id"]))
                for r in conn.execute(sql).fetchall()]


def get_type(type_id: int) -> TrainingType | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM training_types WHERE type_id=?",
                         (int(type_id),)).fetchone()
        if r is None:
            return None
        return _type(r, _requirements_map(conn).get(r["type_id"]))


def _require_type(type_id: Any) -> TrainingType:
    try:
        t = get_type(int(type_id))
    except (TypeError, ValueError):
        raise ValidationError("Training type is required") from None
    if t is None:
        raise ValidationError(f"No training type #{type_id}")
    return t


def _type_payload(payload: dict[str, Any],
                  existing: TrainingType | None) -> dict[str, Any]:
    def get(k: str) -> Any:
        return payload.get(k, getattr(existing, k) if existing else None)
    code = _require(get("code"), "Code").upper().replace(" ", "_")
    if not _CODE_RE.match(code):
        raise ValidationError("Code must be 2-24 letters, digits or _")
    src = _text(get("evidence_source")) or ""
    if src not in EVIDENCE_SOURCES:
        raise ValidationError("Evidence source must be blank, 'prevent' or "
                              "'hr_safeguarding'")
    due_soon = _int(get("due_soon_days"), "Due-soon warning (days)")
    return {
        "code": code,
        "name": _require(get("name"), "Name"),
        "renewal_months": _int(get("renewal_months"),
                               "Renewal period (months)", minimum=1),
        "due_soon_days": (DEFAULT_DUE_SOON_DAYS if due_soon is None
                          else due_soon),
        "evidence_source": src,
        "description": _text(get("description")),
        "active": 0 if get("active") is False else 1,
    }


def create_type(payload: dict[str, Any]) -> TrainingType:
    _need_hr("configure mandatory training")
    init_db()
    p = _type_payload(payload, None)
    with _connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO training_types (code, name, renewal_months, "
                "due_soon_days, evidence_source, description, active) "
                "VALUES (:code, :name, :renewal_months, :due_soon_days, "
                ":evidence_source, :description, :active)", p)
        except _sql.IntegrityError:
            raise ValidationError("A training type with that code or name "
                                  "already exists") from None
        new_id = cur.lastrowid
    for target in payload.get("requirements") or ():
        add_requirement(new_id, target)
    return _require_type(new_id)


def update_type(type_id: int, payload: dict[str, Any]) -> TrainingType:
    _need_hr("configure mandatory training")
    existing = _require_type(type_id)
    p = _type_payload(payload, existing)
    p["type_id"] = existing.type_id
    with _connect() as conn:
        try:
            conn.execute(
                "UPDATE training_types SET code=:code, name=:name, "
                "renewal_months=:renewal_months, "
                "due_soon_days=:due_soon_days, "
                "evidence_source=:evidence_source, "
                "description=:description, active=:active, "
                "updated_at=datetime('now') WHERE type_id=:type_id", p)
        except _sql.IntegrityError:
            raise ValidationError("A training type with that code or name "
                                  "already exists") from None
    return _require_type(existing.type_id)


def delete_type(type_id: int) -> bool:
    """Remove a type set up by mistake. One with completions recorded is
    deactivated instead — the records are evidence."""
    _need_hr("configure mandatory training")
    t = _require_type(type_id)
    with _connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM training_completions "
                         "WHERE type_id=?", (t.type_id,)).fetchone()[0]
        if n:
            raise ValidationError(f"{t.name} has {n} completion record(s) "
                                  "— deactivate it instead")
        conn.execute("DELETE FROM training_requirements WHERE type_id=?",
                     (t.type_id,))
        conn.execute("DELETE FROM training_cpd_links WHERE type_id=?",
                     (t.type_id,))
        cur = conn.execute("DELETE FROM training_types WHERE type_id=?",
                           (t.type_id,))
    return bool(cur.rowcount)


def add_requirement(type_id: int, applies_to: str) -> TrainingType:
    _need_hr("configure mandatory training")
    t = _require_type(type_id)
    target = _validate_target(applies_to)
    with _connect() as conn:
        conn.execute("INSERT OR IGNORE INTO training_requirements "
                     "(type_id, applies_to) VALUES (?, ?)",
                     (t.type_id, target))
    return _require_type(t.type_id)


def remove_requirement(type_id: int, applies_to: str) -> TrainingType:
    _need_hr("configure mandatory training")
    t = _require_type(type_id)
    with _connect() as conn:
        conn.execute("DELETE FROM training_requirements WHERE type_id=? "
                     "AND applies_to=?", (t.type_id, applies_to))
    return _require_type(t.type_id)


def set_requirements(type_id: int, targets: Iterable[str]) -> TrainingType:
    """Replace who needs a type with exactly ``targets``."""
    _need_hr("configure mandatory training")
    t = _require_type(type_id)
    clean = sorted({_validate_target(x) for x in targets if _text(x)})
    with _connect() as conn:
        conn.execute("DELETE FROM training_requirements WHERE type_id=?",
                     (t.type_id,))
        conn.executemany("INSERT INTO training_requirements (type_id, "
                         "applies_to) VALUES (?, ?)",
                         [(t.type_id, x) for x in clean])
    return _require_type(t.type_id)


def install_default_types() -> list[TrainingType]:
    """Add the standard UK list (types + requirements) for any code not
    already present. Existing types are left exactly as configured."""
    _need_hr("configure mandatory training")
    have = {t.code for t in list_types()}
    made = []
    for code, name, months, src, reqs in DEFAULT_TRAINING_TYPES:
        if code in have:
            continue
        try:
            made.append(create_type({
                "code": code, "name": name, "renewal_months": months,
                "evidence_source": src, "requirements": reqs}))
        except ValidationError as e:
            logger.warning("Default training type %s skipped: %s", code, e)
    return made


# ── CPD links ───────────────────────────────────────────────────────

def _cpd():
    from education_system.systems.sixth_form.domain.staff.cpd import cpd
    return cpd


def link_cpd_activity(activity_id: int, type_id: int) -> None:
    """Count attendance at a CPD activity as completing a training type."""
    _need_hr("link CPD to mandatory training")
    t = _require_type(type_id)
    if _cpd().get_activity(int(activity_id)) is None:
        raise ValidationError(f"No CPD activity #{activity_id}")
    with _connect() as conn:
        conn.execute("INSERT OR IGNORE INTO training_cpd_links "
                     "(activity_id, type_id) VALUES (?, ?)",
                     (int(activity_id), t.type_id))


def unlink_cpd_activity(activity_id: int, type_id: int) -> bool:
    _need_hr("link CPD to mandatory training")
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM training_cpd_links WHERE "
                           "activity_id=? AND type_id=?",
                           (int(activity_id), int(type_id)))
    return bool(cur.rowcount)


def list_cpd_links() -> list[dict[str, Any]]:
    """``{activity_id, activity, date, type_id, type}`` rows."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT l.activity_id, l.type_id, t.name FROM "
            "training_cpd_links l JOIN training_types t "
            "ON t.type_id = l.type_id ORDER BY t.name").fetchall()
    out = []
    for r in rows:
        a = _cpd().get_activity(r["activity_id"])
        out.append({"activity_id": r["activity_id"],
                    "activity": a.title if a else "(deleted activity)",
                    "date": a.activity_date if a else None,
                    "type_id": r["type_id"], "type": r["name"]})
    return out


# ── Completions ─────────────────────────────────────────────────────

def _expiry(t: TrainingType, completed_on: str,
            override: str | None) -> str | None:
    if override:
        return override
    return add_months(completed_on, t.renewal_months) \
        if t.renewal_months else None


def record_completion(payload: dict[str, Any]) -> Evidence:
    """Record that a member of staff completed a training type.

    For a type whose evidence source is ``prevent`` the record is written
    to the Prevent training register instead, so Prevent training lives
    in one place.
    """
    p = _need_hr("record staff training")
    init_db()
    sid = _validate_staff(payload.get("staff_id"))
    t = _require_type(payload.get("type_id"))
    done = _date(payload.get("completed_on"), "Completed on",
                 required=True)
    if done > _dt.date.today().isoformat():
        raise ValidationError("Completed on cannot be in the future")
    exp = _date(payload.get("expires_on"), "Expires on")
    if exp and exp <= done:
        raise ValidationError("Expires on must be after the completion date")
    exp = _expiry(t, done, exp)
    provider = _text(payload.get("provider"))
    evidence = _text(payload.get("evidence"))
    if t.evidence_source == "prevent":
        from education_system.systems.sixth_form.domain.safeguarding.prevent_duty import (
            prevent_duty as _prevent,
        )
        ptype = _text(payload.get("prevent_type")) or "Prevent Awareness"
        rec = _prevent.create_training({
            "staff_id": sid, "training_type": ptype,
            "completed_date": done, "expiry_date": exp,
            "provider": provider, "certificate_ref": evidence,
            "notes": f"Recorded from mandatory training by "
                     f"{p.staff_name or p.username}"})
        return Evidence(SOURCE_PREVENT, f"prevent:{rec.training_id}", sid,
                        t.type_id, done, exp, provider, evidence)
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO training_completions (staff_id, type_id, "
            "completed_on, expires_on, provider, evidence, recorded_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sid, t.type_id, done, exp, provider, evidence,
             p.staff_name or p.username or None))
        cid = cur.lastrowid
    logger.info("Training %s recorded for %s (%s)", t.code, sid, done)
    return Evidence(SOURCE_RECORD, f"record:{cid}", sid, t.type_id, done,
                    exp, provider, evidence)


def list_completions(*, staff_id: str | None = None,
                     type_id: int | None = None,
                     include_archived: bool = False) -> list[Completion]:
    p = access.current()
    if not p.can(access.HR) and not (staff_id and staff_id == p.staff_id):
        p.require(access.HR, "staff training records")
    init_db()
    clauses, args = [], []
    if staff_id:
        clauses.append("staff_id = ?")
        args.append(staff_id.strip())
    if type_id is not None:
        clauses.append("type_id = ?")
        args.append(int(type_id))
    if not include_archived:
        clauses.append("archived_at IS NULL")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [_completion(r) for r in conn.execute(
            f"SELECT * FROM training_completions{where} "  # DBW001: literal clauses
            "ORDER BY completed_on DESC, completion_id DESC",
            args).fetchall()]


def archive_completion(completion_id: int, reason: str) -> None:
    """Take a mistaken record off the matrix, keeping it as evidence."""
    p = _need_hr("record staff training")
    why = _require(reason, "Reason")
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE training_completions SET archived_at=datetime('now'), "
            "archived_by=?, archived_reason=? WHERE completion_id=? "
            "AND archived_at IS NULL",
            (p.staff_name or p.username, why, int(completion_id)))
    if not cur.rowcount:
        raise ValidationError(f"No current training record #{completion_id}")


# ── Evidence gathering (all four sources) ───────────────────────────

def _gather(types: list[TrainingType],
            staff_ids: set[str]) -> dict[tuple[str, int], list[Evidence]]:
    out: dict[tuple[str, int], list[Evidence]] = {}
    by_id = {t.type_id: t for t in types}

    def add(e: Evidence) -> None:
        if e.staff_id in staff_ids and e.type_id in by_id:
            out.setdefault((e.staff_id, e.type_id), []).append(e)

    with _connect() as conn:
        for r in conn.execute("SELECT * FROM training_completions WHERE "
                              "archived_at IS NULL"):
            add(Evidence(SOURCE_RECORD, f"record:{r['completion_id']}",
                         r["staff_id"], r["type_id"], r["completed_on"],
                         r["expires_on"], r["provider"], r["evidence"]))
        links: dict[int, list[int]] = {}
        for r in conn.execute("SELECT activity_id, type_id FROM "
                              "training_cpd_links"):
            links.setdefault(r["activity_id"], []).append(r["type_id"])

    if links:
        try:
            cpd = _cpd()
            for rec in cpd.list_records():
                if rec.activity_id not in links or rec.status not in (
                        "Attended", "Completed"):
                    continue
                act = cpd.get_activity(rec.activity_id)
                done = (rec.attended_on
                        or (act.end_date or act.activity_date if act
                            else None) or rec.booked_on)
                for tid in links[rec.activity_id]:
                    t = by_id.get(tid)
                    if t:
                        add(Evidence(SOURCE_CPD, f"cpd:{rec.record_id}",
                                     rec.staff_id, tid, done,
                                     _expiry(t, done, None),
                                     act.provider if act else None,
                                     rec.certificate_ref))
        except Exception:
            logger.exception("Could not read CPD records for the matrix")

    prevent_types = [t for t in types if t.evidence_source == "prevent"]
    if prevent_types:
        try:
            from education_system.systems.sixth_form.domain.safeguarding.prevent_duty import (
                prevent_duty as _prevent,
            )
            for rec in _prevent.list_training():
                for t in prevent_types:
                    add(Evidence(SOURCE_PREVENT, f"prevent:{rec.training_id}",
                                 rec.staff_id, t.type_id, rec.completed_date,
                                 _expiry(t, rec.completed_date,
                                         rec.expiry_date),
                                 rec.provider, rec.certificate_ref))
        except Exception:
            logger.exception("Could not read Prevent training for the matrix")

    hr_types = [t for t in types if t.evidence_source == "hr_safeguarding"]
    if hr_types:
        try:
            from education_system.systems.sixth_form.domain.staff.staff_hr import (
                staff_hr as _hr,
            )
            for rec in _hr.list_records():
                if not rec.safeguarding_training_on:
                    continue
                for t in hr_types:
                    add(Evidence(SOURCE_HR, f"hr:{rec.record_id}",
                                 rec.staff_id, t.type_id,
                                 rec.safeguarding_training_on,
                                 _expiry(t, rec.safeguarding_training_on,
                                         rec.safeguarding_expires_on)))
        except Exception:
            logger.exception("Could not read HR safeguarding dates")
    return out


def _best(evidence: list[Evidence]) -> Evidence | None:
    """The evidence that keeps the member of staff in date longest."""
    if not evidence:
        return None
    return max(evidence, key=lambda e: (e.expires_on or "9999-12-31",
                                        e.completed_on))


def _state(t: TrainingType, e: Evidence | None, today: str) -> str:
    if e is None:
        return MISSING
    if not e.expires_on:
        return DONE
    if e.expires_on < today:
        return OVERDUE
    soon = (_dt.date.fromisoformat(today)
            + _dt.timedelta(days=t.due_soon_days)).isoformat()
    return DUE_SOON if e.expires_on <= soon else DONE


def _cells(staff_rows: list[Any], types: list[TrainingType],
           *, today: str | None = None,
           include_not_required: bool = True) -> list[list[Cell]]:
    day = today or _dt.date.today().isoformat()
    ev = _gather(types, {s.staff_id for s in staff_rows})
    out = []
    for s in staff_rows:
        row = []
        for t in types:
            required = any(_applies(x, s) for x in t.requirements)
            e = _best(ev.get((s.staff_id, t.type_id), []))
            if not required and not include_not_required:
                continue
            state = _state(t, e, day) if required else (
                NOT_REQUIRED if e is None else _state(t, e, day))
            row.append(Cell(s.staff_id, s.full_name, t.type_id, t.name,
                            required, state, e))
        out.append(row)
    return out


def _staff_rows(department: str | None = None,
                role: str | None = None) -> list[Any]:
    return [s for s in _staff_module().list_staff(active_only=True)
            if (not department or s.department == department)
            and (not role or s.role == role)]


def matrix(*, department: str | None = None, role: str | None = None,
           type_ids: Iterable[int] | None = None
           ) -> tuple[list[TrainingType], list[list[Cell]]]:
    """Active staff × active training types. HR only."""
    _need_hr("the staff training matrix")
    types = list_types(active_only=True)
    if type_ids:
        wanted = {int(x) for x in type_ids}
        types = [t for t in types if t.type_id in wanted]
    return types, _cells(_staff_rows(department, role), types)


def expiring(*, within_days: int = 30, include_overdue: bool = True,
             include_missing: bool = False,
             department: str | None = None) -> list[Cell]:
    """Required training running out in the next ``within_days`` days
    (and, optionally, already overdue or never done), soonest first."""
    _need_hr("training expiry reports")
    if within_days < 0 or within_days > 3650:
        raise ValidationError("Days must be between 0 and 3650")
    today = _dt.date.today()
    cutoff = (today + _dt.timedelta(days=within_days)).isoformat()
    out = []
    for row in _cells(_staff_rows(department), list_types(active_only=True),
                      include_not_required=False):
        for c in row:
            if c.state == MISSING:
                if include_missing:
                    out.append(c)
            elif c.state == OVERDUE:
                if include_overdue:
                    out.append(c)
            elif c.expires_on and c.expires_on <= cutoff:
                out.append(c)
    return sorted(out, key=lambda c: (c.expires_on or "0000", c.staff_name))


def staff_status(staff_id: str) -> list[Cell]:
    """Every required (or evidenced) type for one person. HR, or the
    person themselves."""
    p = access.current()
    if not (p.staff_id and p.staff_id == staff_id):
        p.require(access.HR, "another member of staff's training")
    s = _staff_module().get_staff(staff_id)
    if s is None:
        raise ValidationError(f"No staff member with id {staff_id}")
    row = _cells([s], list_types(active_only=True))[0]
    return [c for c in row if c.required or c.latest]


def my_status() -> list[Cell]:
    p = access.current()
    if not p.staff_id:
        raise ValidationError("Your login is not linked to a staff record")
    return staff_status(p.staff_id)


def evidence_for(staff_id: str, type_id: int) -> list[Evidence]:
    """All evidence behind one cell, newest first."""
    p = access.current()
    if not (p.staff_id and p.staff_id == staff_id):
        p.require(access.HR, "another member of staff's training")
    t = _require_type(type_id)
    ev = _gather([t], {staff_id}).get((staff_id, t.type_id), [])
    return sorted(ev, key=lambda e: e.completed_on, reverse=True)


def compliance_by_type(*, department: str | None = None
                       ) -> list[TypeCompliance]:
    _need_hr("training compliance")
    types = list_types(active_only=True)
    out = {t.type_id: TypeCompliance(t.type_id, t.name) for t in types}
    for row in _cells(_staff_rows(department), types,
                      include_not_required=False):
        for c in row:
            tc = out[c.type_id]
            tc.required += 1
            if c.state == DONE:
                tc.done += 1
            elif c.state == DUE_SOON:
                tc.due_soon += 1
            elif c.state == OVERDUE:
                tc.overdue += 1
            else:
                tc.missing += 1
    return list(out.values())


COMPLIANCE_ITEM_TITLE = "Mandatory staff training"


def update_compliance_register() -> Any:
    """Write the matrix's headline into the governance compliance register
    (one "Training" item), so governors see it with everything else."""
    _need_hr("training compliance")
    from education_system.systems.sixth_form.domain.governance.compliance import (
        compliance as _comp,
    )
    rows = compliance_by_type()
    gaps = [r for r in rows if r.overdue or r.missing]
    required = sum(r.required for r in rows)
    ok = sum(r.done + r.due_soon for r in rows)
    lines = [f"{ok}/{required} required trainings in date "
             f"({_dt.date.today().isoformat()})."]
    lines += [f"{r.name}: {r.overdue} overdue, {r.missing} missing"
              for r in gaps][:20]
    today = _dt.date.today().isoformat()
    payload = {"category": "Training", "title": COMPLIANCE_ITEM_TITLE,
               "status": "Action required" if gaps else "Compliant",
               "frequency": "Termly", "last_review": today,
               "next_review": (_dt.date.today()
                               + _dt.timedelta(days=120)).isoformat(),
               "notes": "\n".join(lines)[:1000]}
    existing = [i for i in _comp.list_items(category="Training")
                if i.title == COMPLIANCE_ITEM_TITLE]
    if existing:
        return _comp.update_item(existing[0].item_id, payload)
    return _comp.create_item(payload)
