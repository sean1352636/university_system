"""Safeguarding-log data layer for the Sixth Form System.

UK schools must keep auditable records of safeguarding concerns. This
module models the records a KCSIE-compliant file needs:

* ``safeguarding_concerns`` — one row per concern, with category,
  risk level, status, DSL notification and referral fields, plus name /
  date-of-birth snapshots so the record stays readable after the
  learner leaves, an adult-safeguarding flag for learners aged 18+, a
  restricted-notes level and body-map reference fields.
* ``safeguarding_updates`` — chronological notes attached to a concern,
  so the file shows what happened next. Entries are retracted (struck
  through with a reason), never deleted.
* ``safeguarding_concern_students`` — further learners linked to one
  concern (e.g. child-on-child abuse involving several students).
* ``safeguarding_prevent_links`` — a Prevent concern (separate store,
  :mod:`prevent_duty`) linked to a safeguarding concern. The link is a
  read-through; the two stores are never merged.

Referrals, plans (CP / CIN / early help), the LADO register and file
transfers live in :mod:`safeguarding_casework`.

**Access control is enforced here.** Reading or changing the record
needs ``access.SAFEGUARDING`` (admin, DSL, deputy DSL or an explicit
grant); every read and write is written to the sensitive-access log.
*Reporting* a concern is open to any member of staff and to system
callers (KCSIE: anyone can report) — :func:`create_concern` and
:func:`report_concern` need no capability, but the reporter cannot read
the file back.

Retention: concerns are never deleted. ``delete_concern`` closes the
concern as "Closed — Retained" with a reason, who and when. Deleting a
student no longer touches their concerns — the old ``ON DELETE CASCADE``
is removed by a one-off rebuild (see :mod:`_retention`).
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any, Iterator
from education_system import paths
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.domain.safeguarding import _retention

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_SAFEGUARDING_DB

#: Area name used in the sensitive-access log.
AREA = "safeguarding"

CONCERN_TYPES: tuple[str, ...] = (
    "Disclosure", "Observation", "Allegation",
    "Third-party report", "Self-disclosure", "Other",
)

CATEGORIES: tuple[str, ...] = (
    "Physical", "Emotional", "Sexual", "Neglect",
    "Online/Cyber", "Bullying", "Mental Health", "Self-harm",
    "Substance Misuse", "Radicalisation / Prevent",
    "Domestic", "FGM", "Child Sexual Exploitation",
    "Child Criminal Exploitation", "Missing Education",
    # KCSIE 2024 categories added alongside the originals.
    "County Lines", "Honour-Based Abuse",
    "Child-on-Child (Peer-on-Peer) Abuse", "Serious Violence",
    "Online Safety", "Domestic Abuse", "Forced Marriage",
    "Radicalisation",
    "Other",
)

#: Free-text categories other modules send, mapped onto the list above.
_CATEGORY_ALIASES: dict[str, str] = {
    "attendance": "Missing Education",
    "cme": "Missing Education",
    "children missing education": "Missing Education",
    "peer-on-peer abuse": "Child-on-Child (Peer-on-Peer) Abuse",
    "child-on-child abuse": "Child-on-Child (Peer-on-Peer) Abuse",
    "cce": "Child Criminal Exploitation",
    "cse": "Child Sexual Exploitation",
    "hba": "Honour-Based Abuse",
    "prevent": "Radicalisation / Prevent",
}

RISK_LEVELS: tuple[str, ...] = ("Low", "Medium", "High", "Critical")

#: The status a concern moves to instead of being deleted.
ARCHIVED_STATUS: str = "Closed — Retained"

STATUSES: tuple[str, ...] = (
    "Open", "Under Investigation", "Resolved", "Closed", "Escalated",
    ARCHIVED_STATUS,
)
DEFAULT_STATUS: str = "Open"

# These count as "active" when computing dashboards.
OPEN_STATUSES: tuple[str, ...] = (
    "Open", "Under Investigation", "Escalated",
)

AGENCIES: tuple[str, ...] = (
    "Children's Social Care", "MASH", "LADO", "Police",
    "CAMHS", "NSPCC", "Local Authority", "Health Visitor",
    "Early Help", "School Nurse",
    "Adult Social Care", "Channel",
    "Other",
)

#: Who to refer to, by age (Care Act 2014 for adults at risk).
CHILD_AGENCIES: tuple[str, ...] = (
    "MASH", "Children's Social Care", "Early Help", "Police",
    "CAMHS", "Channel",
)
ADULT_AGENCIES: tuple[str, ...] = (
    "Adult Social Care", "Police", "Channel", "CAMHS",
)
ADULT_AGE: int = 18

#: Restricted-notes levels. "Restricted" notes are visible to the DSL
#: (designation) and administrators only, not deputies or grants.
ACCESS_LEVELS: tuple[str, ...] = ("Standard", "Restricted")

LINK_ROLES: tuple[str, ...] = (
    "Also involved", "Alleged victim", "Alleged perpetrator",
    "Witness", "Sibling", "Other",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# DDL templates: ``{name}`` is the table name (or the rebuild temp name).
_CONCERNS_DDL = """
CREATE TABLE IF NOT EXISTS {name} (
    concern_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id          TEXT NOT NULL,
    concern_date        TEXT NOT NULL,
    reported_date       TEXT NOT NULL,
    concern_type        TEXT NOT NULL,
    category            TEXT NOT NULL,
    risk_level          TEXT NOT NULL,
    reported_by         TEXT NOT NULL,
    description         TEXT NOT NULL,
    action_taken        TEXT,
    dsl_notified        INTEGER NOT NULL DEFAULT 0,
    dsl_name            TEXT,
    dsl_notified_at     TEXT,
    parents_informed    INTEGER NOT NULL DEFAULT 0,
    parents_informed_at TEXT,
    external_agencies   TEXT,
    referral_made       INTEGER NOT NULL DEFAULT 0,
    referral_date       TEXT,
    referral_ref        TEXT,
    status              TEXT NOT NULL DEFAULT 'Open',
    follow_up_date      TEXT,
    notes               TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now')),
    student_name        TEXT,
    student_dob         TEXT,
    adult_safeguarding  INTEGER NOT NULL DEFAULT 0,
    access_level        TEXT NOT NULL DEFAULT 'Standard',
    restricted_notes    TEXT,
    body_map_ref        TEXT,
    body_map_notes      TEXT,
    archived_reason     TEXT,
    archived_by         TEXT,
    archived_at         TEXT,
    reported_by_username TEXT
)
"""

_UPDATES_DDL = """
CREATE TABLE IF NOT EXISTS {name} (
    update_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    concern_id    INTEGER NOT NULL,
    update_date   TEXT NOT NULL,
    update_text   TEXT NOT NULL,
    updated_by    TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    retracted         INTEGER NOT NULL DEFAULT 0,
    retracted_reason  TEXT,
    retracted_by      TEXT,
    retracted_at      TEXT,
    FOREIGN KEY (concern_id) REFERENCES safeguarding_concerns(concern_id)
)
"""

#: Columns added after the first release, for DBs that already have the
#: tables without them (``ALTER TABLE ADD COLUMN``).
_CONCERN_NEW_COLUMNS: dict[str, str] = {
    "student_name": "TEXT",
    "student_dob": "TEXT",
    "adult_safeguarding": "INTEGER NOT NULL DEFAULT 0",
    "access_level": "TEXT NOT NULL DEFAULT 'Standard'",
    "restricted_notes": "TEXT",
    "body_map_ref": "TEXT",
    "body_map_notes": "TEXT",
    "archived_reason": "TEXT",
    "archived_by": "TEXT",
    "archived_at": "TEXT",
    "reported_by_username": "TEXT",
}
_UPDATE_NEW_COLUMNS: dict[str, str] = {
    "retracted": "INTEGER NOT NULL DEFAULT 0",
    "retracted_reason": "TEXT",
    "retracted_by": "TEXT",
    "retracted_at": "TEXT",
}

_EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS safeguarding_concern_students (
    link_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    concern_id   INTEGER NOT NULL,
    student_id   TEXT NOT NULL,
    student_name TEXT,
    link_role    TEXT NOT NULL DEFAULT 'Also involved',
    added_by     TEXT,
    added_at     TEXT NOT NULL DEFAULT (datetime('now')),
    removed_by   TEXT,
    removed_at   TEXT,
    removed_reason TEXT,
    FOREIGN KEY (concern_id) REFERENCES safeguarding_concerns(concern_id)
);

CREATE TABLE IF NOT EXISTS safeguarding_prevent_links (
    link_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    concern_id         INTEGER NOT NULL,
    prevent_concern_id INTEGER NOT NULL,
    linked_by          TEXT,
    linked_at          TEXT NOT NULL DEFAULT (datetime('now')),
    note               TEXT,
    UNIQUE (concern_id, prevent_concern_id),
    FOREIGN KEY (concern_id) REFERENCES safeguarding_concerns(concern_id)
);

CREATE INDEX IF NOT EXISTS idx_sgc_student  ON safeguarding_concerns(student_id);
CREATE INDEX IF NOT EXISTS idx_sgc_status   ON safeguarding_concerns(status);
CREATE INDEX IF NOT EXISTS idx_sgc_risk     ON safeguarding_concerns(risk_level);
CREATE INDEX IF NOT EXISTS idx_sgc_category ON safeguarding_concerns(category);
CREATE INDEX IF NOT EXISTS idx_sgu_concern  ON safeguarding_updates(concern_id);
CREATE INDEX IF NOT EXISTS idx_sgcs_concern ON safeguarding_concern_students(concern_id);
CREATE INDEX IF NOT EXISTS idx_sgcs_student ON safeguarding_concern_students(student_id);
CREATE INDEX IF NOT EXISTS idx_sgpl_concern ON safeguarding_prevent_links(concern_id);
CREATE INDEX IF NOT EXISTS idx_sgpl_prevent ON safeguarding_prevent_links(prevent_concern_id);
"""

# Kept for callers that read the schema text.
_SCHEMA = (_CONCERNS_DDL.format(name="safeguarding_concerns") + ";\n"
           + _UPDATES_DDL.format(name="safeguarding_updates") + ";\n"
           + _EXTRA_SCHEMA)

# Old rows get a name snapshot from the students table when rebuilt.
_NAME_SNAPSHOT_SQL = (
    "(SELECT TRIM(s.first_name || ' ' || COALESCE(s.middle_name || ' ', '') "
    "|| s.last_name) FROM students s WHERE s.student_id = old.student_id)")
_DOB_SNAPSHOT_SQL = (
    "(SELECT s.date_of_birth FROM students s "
    "WHERE s.student_id = old.student_id)")


@dataclass
class Concern:
    concern_id: int
    student_id: str
    concern_date: str
    reported_date: str
    concern_type: str
    category: str
    risk_level: str
    reported_by: str
    description: str
    action_taken: str | None
    dsl_notified: bool
    dsl_name: str | None
    dsl_notified_at: str | None
    parents_informed: bool
    parents_informed_at: str | None
    external_agencies: str | None
    referral_made: bool
    referral_date: str | None
    referral_ref: str | None
    status: str
    follow_up_date: str | None
    notes: str | None
    created_at: str
    updated_at: str
    student_name: str | None = None
    student_dob: str | None = None
    adult_safeguarding: bool = False
    access_level: str = "Standard"
    restricted_notes: str | None = None
    body_map_ref: str | None = None
    body_map_notes: str | None = None
    archived_reason: str | None = None
    archived_by: str | None = None
    archived_at: str | None = None

    @property
    def is_archived(self) -> bool:
        return self.status == ARCHIVED_STATUS

    @property
    def age_at_concern(self) -> int | None:
        return age_on(self.student_dob, self.concern_date)

    @property
    def suggested_agencies(self) -> tuple[str, ...]:
        return ADULT_AGENCIES if self.adult_safeguarding else CHILD_AGENCIES


@dataclass
class Update:
    update_id: int
    concern_id: int
    update_date: str
    update_text: str
    updated_by: str | None
    created_at: str
    retracted: bool = False
    retracted_reason: str | None = None
    retracted_by: str | None = None
    retracted_at: str | None = None


@dataclass
class ConcernRow:
    concern: Concern
    student_name: str
    update_count: int


@dataclass
class LinkedStudent:
    link_id: int
    concern_id: int
    student_id: str
    student_name: str | None
    link_role: str
    added_by: str | None
    added_at: str


@dataclass
class ReportReceipt:
    """What a non-DSL reporter gets back: proof of filing, not the file."""
    concern_id: int
    student_id: str
    reported_at: str
    reported_by: str
    adult_safeguarding: bool
    message: str


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    _students.init_db()
    with _connect() as conn:
        conn.execute(_CONCERNS_DDL.format(name="safeguarding_concerns"))
        conn.execute(_UPDATES_DDL.format(name="safeguarding_updates"))
    # One-off retention rebuilds: drop ON DELETE CASCADE (backs up first).
    _retention.rebuild_table(
        DB_PATH, "safeguarding_concerns", _CONCERNS_DDL,
        label="safeguarding_retention",
        extra_copy={"student_name": _NAME_SNAPSHOT_SQL,
                    "student_dob": _DOB_SNAPSHOT_SQL})
    _retention.rebuild_table(
        DB_PATH, "safeguarding_updates", _UPDATES_DDL,
        label="safeguarding_retention")
    with _connect() as conn:
        _retention.add_missing_columns(
            conn, "safeguarding_concerns", _CONCERN_NEW_COLUMNS)
        _retention.add_missing_columns(
            conn, "safeguarding_updates", _UPDATE_NEW_COLUMNS)
        conn.executescript(_EXTRA_SCHEMA)
        # Backfill name / DOB snapshots for rows written before they existed.
        conn.execute(
            "UPDATE safeguarding_concerns AS old SET "
            f"student_name = COALESCE(student_name, {_NAME_SNAPSHOT_SQL}), "
            f"student_dob = COALESCE(student_dob, {_DOB_SNAPSHOT_SQL}) "
            "WHERE student_name IS NULL OR student_dob IS NULL")
        # Adult flag for rows written before it existed (age at concern).
        conn.execute(
            "UPDATE safeguarding_concerns SET adult_safeguarding = 1 "
            "WHERE adult_safeguarding = 0 AND student_dob IS NOT NULL "
            "AND date(student_dob, '+18 years') <= date(concern_date)")
        conn.commit()
    logger.debug("Safeguarding schema ready at %s", DB_PATH)

    _DB_READY = True


def _row_concern(r: sqlite3.Row) -> Concern:
    keys = r.keys()

    def opt(k: str, default: Any = None) -> Any:
        return r[k] if k in keys else default

    return Concern(
        concern_id=r["concern_id"], student_id=r["student_id"],
        concern_date=r["concern_date"], reported_date=r["reported_date"],
        concern_type=r["concern_type"], category=r["category"],
        risk_level=r["risk_level"], reported_by=r["reported_by"],
        description=r["description"], action_taken=r["action_taken"],
        dsl_notified=bool(r["dsl_notified"]), dsl_name=r["dsl_name"],
        dsl_notified_at=r["dsl_notified_at"],
        parents_informed=bool(r["parents_informed"]),
        parents_informed_at=r["parents_informed_at"],
        external_agencies=r["external_agencies"],
        referral_made=bool(r["referral_made"]),
        referral_date=r["referral_date"], referral_ref=r["referral_ref"],
        status=r["status"], follow_up_date=r["follow_up_date"],
        notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
        student_name=opt("student_name"), student_dob=opt("student_dob"),
        adult_safeguarding=bool(opt("adult_safeguarding", 0)),
        access_level=opt("access_level") or "Standard",
        restricted_notes=opt("restricted_notes"),
        body_map_ref=opt("body_map_ref"),
        body_map_notes=opt("body_map_notes"),
        archived_reason=opt("archived_reason"),
        archived_by=opt("archived_by"), archived_at=opt("archived_at"),
    )


def _row_update(r: sqlite3.Row) -> Update:
    keys = r.keys()
    return Update(
        update_id=r["update_id"], concern_id=r["concern_id"],
        update_date=r["update_date"], update_text=r["update_text"],
        updated_by=r["updated_by"], created_at=r["created_at"],
        retracted=bool(r["retracted"]) if "retracted" in keys else False,
        retracted_reason=r["retracted_reason"] if "retracted_reason" in keys else None,
        retracted_by=r["retracted_by"] if "retracted_by" in keys else None,
        retracted_at=r["retracted_at"] if "retracted_at" in keys else None,
    )


# ── Access control ────────────────────────────────────────────────

AccessDenied = access.AccessDenied


def _principal(principal: access.Principal | None) -> access.Principal:
    return principal if principal is not None else access.current()


def _actor(p: access.Principal) -> str:
    return p.staff_name or p.username or "System"


def require_dsl(principal: access.Principal | None = None, *,
                action: str = "view",
                student_id: str | None = None,
                record_ref: str | None = None) -> access.Principal:
    """Check SAFEGUARDING, log the access (allowed or refused), return p."""
    p = _principal(principal)
    if not p.can(access.SAFEGUARDING):
        access.log_sensitive_access(p, AREA, action, student_id=student_id,
                                    record_ref=record_ref, allowed=False)
        logger.warning("Safeguarding %s refused for %s", action,
                       p.username or "anonymous")
        raise access.AccessDenied(
            f"{p.username or 'This account'} is not allowed to read or "
            "change safeguarding records. Use 'Report a concern' to "
            "pass a worry to the DSL.")
    access.log_sensitive_access(p, AREA, action, student_id=student_id,
                                record_ref=record_ref)
    return p


def can_read(principal: access.Principal | None = None) -> bool:
    return _principal(principal).can(access.SAFEGUARDING)


def can_see_restricted(principal: access.Principal | None = None) -> bool:
    """Restricted notes: the DSL designation or an administrator only."""
    p = _principal(principal)
    return p.is_admin or "dsl" in p.designations \
        or p.job_role == "Safeguarding Lead (DSL)"


@contextlib.contextmanager
def acting_as(principal: access.Principal) -> Iterator[access.Principal]:
    """Temporarily make *principal* the session principal (tests, jobs)."""
    before = access.current()
    access.set_current(principal)
    try:
        yield principal
    finally:
        access.set_current(before)


def _redact(c: Concern, p: access.Principal) -> Concern:
    if c.restricted_notes and not can_see_restricted(p):
        c.restricted_notes = "[restricted — DSL only]"
    return c


def _ref(concern_id: int) -> str:
    return f"concern:{concern_id}"


# ── Validation ────────────────────────────────────────────────────

class ValidationError(ValueError):
    """Raised for any invalid safeguarding input."""


def _require(value, label: str):
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{label} is required")
    return value


def _validate_date(value: Any, label: str) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    return s


def _coerce_bool(value: Any) -> int:
    if isinstance(value, str):
        return 1 if value.strip().lower() in ("1", "true", "yes", "y", "on") else 0
    return 1 if bool(value) else 0


def normalise_category(value: Any) -> str:
    s = (str(value or "")).strip()
    if s in CATEGORIES:
        return s
    alias = _CATEGORY_ALIASES.get(s.lower())
    if alias:
        return alias
    raise ValidationError(
        f"Category must be one of: {', '.join(CATEGORIES)}")


def age_on(dob: str | None, on: str | None = None) -> int | None:
    """Whole years between *dob* and *on* (today by default)."""
    if not dob:
        return None
    try:
        born = _dt.date.fromisoformat(str(dob)[:10])
        ref = _dt.date.fromisoformat(on[:10]) if on else _dt.date.today()
    except ValueError:
        return None
    years = ref.year - born.year - ((ref.month, ref.day) < (born.month, born.day))
    return years


def student_age(student_id: str, on: str | None = None) -> int | None:
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    s = _students.get_student(student_id)
    return age_on(getattr(s, "date_of_birth", None), on) if s else None


def is_adult_learner(student_id: str, on: str | None = None) -> bool:
    age = student_age(student_id, on)
    return age is not None and age >= ADULT_AGE


def suggested_agencies(student_id: str, on: str | None = None) -> tuple[str, ...]:
    """Adult social care (Care Act 2014) for 18+, children's services otherwise."""
    return ADULT_AGENCIES if is_adult_learner(student_id, on) else CHILD_AGENCIES


def agency_warning(student_id: str, agency: str,
                   on: str | None = None) -> str | None:
    """A warning when the chosen agency does not match the learner's age."""
    age = student_age(student_id, on)
    if age is None:
        return None
    if age >= ADULT_AGE and agency in ("MASH", "Children's Social Care",
                                       "Early Help"):
        return (f"This learner is {age}. Concerns about adults at risk go to "
                "Adult Social Care under the Care Act 2014, not children's "
                "services.")
    if age < ADULT_AGE and agency == "Adult Social Care":
        return (f"This learner is {age}, so is still a child: refer to "
                "MASH / Children's Social Care.")
    return None


def _validate_concern_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    sid = _require(data.get("student_id"), "Student ID").strip()
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    student = _students.get_student(sid)
    if student is None and not data.get("_existing"):
        raise ValidationError(f"No student with id {sid}")
    out["student_id"] = sid
    out["_student"] = student

    out["concern_date"] = _validate_date(
        _require(data.get("concern_date"), "Concern date"), "Concern date")
    out["reported_date"] = _validate_date(
        _require(data.get("reported_date"), "Reported date"),
        "Reported date")
    if out["reported_date"] < out["concern_date"]:
        raise ValidationError(
            "Reported date cannot be before the concern date")

    ctype = _require(data.get("concern_type"), "Concern type").strip()
    if ctype not in CONCERN_TYPES:
        raise ValidationError(
            f"Concern type must be one of: {', '.join(CONCERN_TYPES)}")
    out["concern_type"] = ctype

    out["category"] = normalise_category(
        _require(data.get("category"), "Category"))

    risk = _require(data.get("risk_level"), "Risk level").strip()
    if risk not in RISK_LEVELS:
        raise ValidationError(
            f"Risk level must be one of: {', '.join(RISK_LEVELS)}")
    out["risk_level"] = risk

    out["reported_by"] = _require(
        data.get("reported_by"), "Reported by").strip()
    out["description"] = _require(
        data.get("description"), "Description").strip()

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    out["dsl_notified"] = _coerce_bool(data.get("dsl_notified"))
    out["dsl_name"] = (data.get("dsl_name") or "").strip() or None
    out["dsl_notified_at"] = _validate_date(
        data.get("dsl_notified_at"), "DSL notified at")
    out["parents_informed"] = _coerce_bool(data.get("parents_informed"))
    out["parents_informed_at"] = _validate_date(
        data.get("parents_informed_at"), "Parents informed at")
    out["referral_made"] = _coerce_bool(data.get("referral_made"))
    out["referral_date"] = _validate_date(
        data.get("referral_date"), "Referral date")
    out["follow_up_date"] = _validate_date(
        data.get("follow_up_date"), "Follow-up date")

    # Sanity: if dsl_notified is False but dsl_notified_at is set, clear it.
    if not out["dsl_notified"]:
        out["dsl_notified_at"] = None
    if not out["parents_informed"]:
        out["parents_informed_at"] = None
    if not out["referral_made"]:
        out["referral_date"] = None

    # External agencies: free-text comma-separated. Optionally normalise
    # against AGENCIES — but staff may write site-specific names, so
    # we don't reject unknowns.
    out["external_agencies"] = (
        data.get("external_agencies") or "").strip() or None
    out["referral_ref"] = (data.get("referral_ref") or "").strip() or None
    out["action_taken"] = (data.get("action_taken") or "").strip() or None
    out["notes"]        = (data.get("notes") or "").strip() or None

    level = (data.get("access_level") or "Standard").strip()
    if level not in ACCESS_LEVELS:
        raise ValidationError(
            f"Access level must be one of: {', '.join(ACCESS_LEVELS)}")
    out["access_level"] = level
    out["restricted_notes"] = (
        data.get("restricted_notes") or "").strip() or None
    if out["restricted_notes"]:
        out["access_level"] = "Restricted"
    out["body_map_ref"] = (data.get("body_map_ref") or "").strip() or None
    out["body_map_notes"] = (
        data.get("body_map_notes") or "").strip() or None
    return out


def _validate_update_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["update_date"] = _validate_date(
        _require(data.get("update_date"), "Update date"), "Update date")
    out["update_text"] = _require(
        data.get("update_text"), "Update text").strip()
    out["updated_by"] = (data.get("updated_by") or "").strip() or None
    return out


def _system_report_defaults(data: dict[str, Any],
                            p: access.Principal) -> dict[str, Any]:
    """Fill what a reporter or another module may leave out.

    The attendance bridge sends ``summary`` / ``details`` and a category
    such as "Attendance"; staff using *Report a concern* give only the
    essentials. Neither should fail validation for want of a date.
    """
    d = dict(data)
    today = _dt.date.today().isoformat()
    if not d.get("description"):
        parts = [d.get("summary"), d.get("details")]
        d["description"] = "\n".join(str(x).strip() for x in parts if x) or ""
    d.setdefault("concern_date", None)
    d["concern_date"] = d.get("concern_date") or today
    d["reported_date"] = d.get("reported_date") or today
    d["concern_type"] = d.get("concern_type") or (
        "Observation" if d.get("summary") else "Disclosure")
    d["risk_level"] = d.get("risk_level") or "Medium"
    d["reported_by"] = (d.get("reported_by") or "").strip() or _actor(p)
    return d


# ── Concern CRUD ──────────────────────────────────────────────────

def _get_concern(concern_id: int) -> Concern | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM safeguarding_concerns WHERE concern_id = ?",
            (concern_id,),
        ).fetchone()
        return _row_concern(r) if r else None


def create_concern(data: dict[str, Any], *,
                   principal: access.Principal | None = None,
                   publish: bool = True) -> Concern:
    """File a concern. No capability needed: anyone may report.

    System callers (the attendance bridge, bulk operations) also come
    through here. The access log records who filed it. ``publish=False``
    keeps the concern off the cross-system register until the DSL has
    looked at it (used for learner-raised reports).
    """
    init_db()
    p = _principal(principal)
    try:
        payload = _validate_concern_payload(_system_report_defaults(data, p))
    except ValidationError as e:
        logger.warning("create_concern validation failed: %s", e)
        raise
    student = payload.pop("_student")
    student_name = student.full_name if student else None
    student_dob = getattr(student, "date_of_birth", None) if student else None
    age = age_on(student_dob, payload["concern_date"])
    adult = 1 if age is not None and age >= ADULT_AGE else 0
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO safeguarding_concerns
                   (student_id, concern_date, reported_date, concern_type,
                    category, risk_level, reported_by, description,
                    action_taken, dsl_notified, dsl_name, dsl_notified_at,
                    parents_informed, parents_informed_at,
                    external_agencies, referral_made, referral_date,
                    referral_ref, status, follow_up_date, notes,
                    created_at, updated_at,
                    student_name, student_dob, adult_safeguarding,
                    access_level, restricted_notes, body_map_ref,
                    body_map_notes, reported_by_username)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, ?, datetime('now'), datetime('now'),
                       ?, ?, ?, ?, ?, ?, ?, ?)""",
            (payload["student_id"], payload["concern_date"],
             payload["reported_date"],
             payload["concern_type"], payload["category"],
             payload["risk_level"],
             payload["reported_by"], payload["description"],
             payload["action_taken"],
             payload["dsl_notified"], payload["dsl_name"],
             payload["dsl_notified_at"],
             payload["parents_informed"], payload["parents_informed_at"],
             payload["external_agencies"], payload["referral_made"],
             payload["referral_date"], payload["referral_ref"],
             payload["status"],
             payload["follow_up_date"], payload["notes"],
             student_name, student_dob, adult, payload["access_level"],
             payload["restricted_notes"], payload["body_map_ref"],
             payload["body_map_notes"], p.username or None),
        )
        conn.commit()
        new_id = cur.lastrowid
    out = _get_concern(new_id)
    assert out is not None
    access.log_sensitive_access(p, AREA, "create",
                                student_id=out.student_id,
                                record_ref=_ref(new_id))
    logger.info(
        "Created safeguarding concern #%d for %s "
        "(%s, risk=%s, status=%s, dsl=%s, referral=%s, adult=%s)",
        new_id, payload["student_id"], payload["category"],
        payload["risk_level"], payload["status"], payload["dsl_notified"],
        payload["referral_made"], bool(adult),
    )
    # Mirror onto the cross-system safeguarding register so a flag raised
    # in sixth form is visible at university intake (best-effort).
    if not publish:
        return out
    try:
        from education_system.platform.governance.safeguarding import alert_service
        alert_service.raise_flag_for_local_concern(
            "sixth_form", out.student_id, category=out.category,
            severity=out.risk_level, summary=out.category,
            source_ref=str(out.concern_id), raised_by=out.reported_by)
    except Exception:
        logger.debug("Cross-system safeguarding publish skipped for #%s",
                     out.concern_id, exc_info=True)
    return out


def report_concern(student_id: str, description: str, *,
                   category: str = "Other",
                   concern_type: str = "Disclosure",
                   risk_level: str = "Medium",
                   concern_date: str | None = None,
                   action_taken: str | None = None,
                   reported_by: str | None = None,
                   principal: access.Principal | None = None,
                   ) -> ReportReceipt:
    """Any member of staff passes a worry to the DSL.

    Files a concern marked *not yet seen by the DSL* and returns a
    receipt. The reporter cannot open the record afterwards.
    """
    p = _principal(principal)
    c = create_concern({
        "student_id": student_id,
        "description": description,
        "category": category,
        "concern_type": concern_type,
        "risk_level": risk_level,
        "concern_date": concern_date,
        "action_taken": action_taken,
        "reported_by": reported_by,
        "status": "Open",
        "dsl_notified": False,
    }, principal=p)
    msg = (f"Concern #{c.concern_id} has been passed to the Designated "
           "Safeguarding Lead. If a learner is in immediate danger, call "
           "999 and tell the DSL in person now.")
    if c.adult_safeguarding:
        msg += (" This learner is 18 or over: the DSL will consider an "
                "adult social care referral (Care Act 2014).")
    return ReportReceipt(
        concern_id=c.concern_id, student_id=c.student_id,
        reported_at=c.created_at, reported_by=c.reported_by,
        adult_safeguarding=c.adult_safeguarding, message=msg)


def my_reports(principal: access.Principal | None = None) -> list[ReportReceipt]:
    """The reporter's own receipts (id, date) — no content."""
    init_db()
    p = _principal(principal)
    if not p.username:
        return []
    with _connect() as conn:
        rows = conn.execute(
            "SELECT concern_id, student_id, created_at, reported_by, "
            "adult_safeguarding FROM safeguarding_concerns "
            "WHERE reported_by_username = ? ORDER BY concern_id DESC",
            (p.username,)).fetchall()
    return [ReportReceipt(
        concern_id=r["concern_id"], student_id=r["student_id"],
        reported_at=r["created_at"], reported_by=r["reported_by"],
        adult_safeguarding=bool(r["adult_safeguarding"]),
        message="Filed with the DSL") for r in rows]


# ── A learner raises a concern (student portal) ──────────────────

#: What the learner picks, mapped onto the concern categories above.
LEARNER_TOPICS: dict[str, str] = {
    "Bullying or harassment": "Bullying",
    "Something online": "Online Safety",
    "Feeling unsafe at home": "Domestic Abuse",
    "Someone is hurting me or a friend": "Physical",
    "Unwanted sexual behaviour": "Sexual",
    "Mental health or self-harm": "Mental Health",
    "Drugs, alcohol or being pressured into crime": "Child Criminal Exploitation",
    "Extremist views": "Radicalisation / Prevent",
    "Something else": "Other",
}

#: Who the worry is about.
LEARNER_SUBJECTS: tuple[str, ...] = ("Me", "Someone else", "I'd rather not say")

LEARNER_RECEIPT_MESSAGE = (
    "Thank you for telling us. Your report has gone to the college's "
    "Designated Safeguarding Lead, who will follow it up. If you or anyone "
    "else is in immediate danger, call 999 now, and tell a member of staff "
    "in person.")


def report_concern_as_learner(principal: access.Principal, description: str, *,
                              topic: str = "Something else",
                              about: str = "Me",
                              unsafe_now: bool = False) -> ReportReceipt:
    """A signed-in learner passes a worry to the DSL.

    The concern is filed on the learner's own record (the only student
    id a learner holds), says who it is about in the description, and is
    marked not yet seen by the DSL — exactly as a staff *Report a
    concern*. It is not mirrored to the cross-system register until the
    DSL has reviewed it. The learner gets a receipt and cannot read the
    record, or any other safeguarding data, back.
    """
    if principal is None or not principal.is_student or not principal.student_id:
        raise ValidationError("Only a signed-in learner can report this way.")
    if topic not in LEARNER_TOPICS:
        raise ValidationError(f"Choose one of: {', '.join(LEARNER_TOPICS)}")
    if about not in LEARNER_SUBJECTS:
        raise ValidationError(f"Choose one of: {', '.join(LEARNER_SUBJECTS)}")
    text = (description or "").strip()
    if not text:
        raise ValidationError("Tell us what has happened or what you are worried about.")
    if len(text) > 5000:
        raise ValidationError("Please keep it under 5000 characters.")
    header = (f"[Raised by the learner through the student portal. "
              f"About: {about}. Topic: {topic}."
              + (" The learner said they do not feel safe right now." if unsafe_now else "")
              + "]")
    c = create_concern({
        "student_id": principal.student_id,
        "description": f"{header}\n\n{text}",
        "category": LEARNER_TOPICS[topic],
        "concern_type": "Self-disclosure" if about == "Me" else "Third-party report",
        "risk_level": "High" if unsafe_now else "Medium",
        "reported_by": f"{principal.username} (learner)",
        "status": "Open",
        "dsl_notified": False,
    }, principal=principal, publish=False)
    logger.info("Learner-raised safeguarding concern #%d filed (about=%s)",
                c.concern_id, about)
    return ReportReceipt(
        concern_id=c.concern_id, student_id=c.student_id,
        reported_at=c.created_at, reported_by=c.reported_by,
        adult_safeguarding=c.adult_safeguarding,
        message=LEARNER_RECEIPT_MESSAGE)


def get_concern(concern_id: int, *,
                principal: access.Principal | None = None) -> Concern | None:
    c = _get_concern(concern_id)
    p = require_dsl(principal, action="view",
                    student_id=c.student_id if c else None,
                    record_ref=_ref(concern_id))
    return _redact(c, p) if c else None


def _list_concerns(
    *,
    student_id: str | None = None,
    risk_level: str | None = None,
    status: str | None = None,
    category: str | None = None,
    reported_by_like: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    open_only: bool = False,
    include_archived: bool = True,
    include_linked: bool = True,
) -> list[Concern]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        if include_linked:
            clauses.append(
                "(student_id = ? OR concern_id IN (SELECT concern_id FROM "
                "safeguarding_concern_students WHERE student_id = ? "
                "AND removed_at IS NULL))")
            args.extend([student_id.strip(), student_id.strip()])
        else:
            clauses.append("student_id = ?")
            args.append(student_id.strip())
    if risk_level:
        if risk_level not in RISK_LEVELS:
            raise ValidationError(
                f"Risk level must be one of: {', '.join(RISK_LEVELS)}")
        clauses.append("risk_level = ?")
        args.append(risk_level)
    if status:
        if status not in STATUSES:
            raise ValidationError(
                f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if category:
        clauses.append("category = ?")
        args.append(normalise_category(category))
    if reported_by_like:
        clauses.append("reported_by LIKE ?")
        args.append(f"%{reported_by_like.strip()}%")
    if date_from:
        clauses.append("concern_date >= ?")
        args.append(_validate_date(date_from, "date_from"))
    if date_to:
        clauses.append("concern_date <= ?")
        args.append(_validate_date(date_to, "date_to"))
    if open_only:
        placeholders = ",".join("?" * len(OPEN_STATUSES))
        clauses.append(f"status IN ({placeholders})")
        args.extend(OPEN_STATUSES)
    if not include_archived:
        clauses.append("status <> ?")
        args.append(ARCHIVED_STATUS)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    # Sort: open & high-risk first, then by recency.
    sql = (
        f"SELECT * FROM safeguarding_concerns {where} "  # DBW001: where is built from fixed clauses
        "ORDER BY "
        "  CASE risk_level WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 "
        "                  WHEN 'Medium' THEN 2 ELSE 3 END, "
        "  CASE WHEN status IN ('Open','Under Investigation','Escalated') "
        "       THEN 0 ELSE 1 END, "
        "  concern_date DESC, concern_id DESC"
    )
    with _connect() as conn:
        return [_row_concern(r) for r in conn.execute(sql, args).fetchall()]


def list_concerns(
    *,
    student_id: str | None = None,
    risk_level: str | None = None,
    status: str | None = None,
    category: str | None = None,
    reported_by_like: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    open_only: bool = False,
    include_archived: bool = True,
    include_linked: bool = True,
    principal: access.Principal | None = None,
) -> list[Concern]:
    p = require_dsl(principal, action="list", student_id=student_id)
    rows = _list_concerns(
        student_id=student_id, risk_level=risk_level, status=status,
        category=category, reported_by_like=reported_by_like,
        date_from=date_from, date_to=date_to, open_only=open_only,
        include_archived=include_archived, include_linked=include_linked)
    return [_redact(c, p) for c in rows]


def concerns_for_student(student_id: str, *,
                         principal: access.Principal | None = None
                         ) -> list[Concern]:
    return list_concerns(student_id=student_id, principal=principal)


def list_unreviewed(*, principal: access.Principal | None = None
                    ) -> list[Concern]:
    """Reports the DSL has not yet acknowledged (dsl_notified = 0)."""
    p = require_dsl(principal, action="list-unreviewed")
    return [_redact(c, p) for c in _list_concerns()
            if not c.dsl_notified and c.status in OPEN_STATUSES]


def acknowledge_report(concern_id: int, *,
                       principal: access.Principal | None = None) -> Concern:
    """The DSL marks a report as seen (DSL notified = yes, today)."""
    c = _get_concern(concern_id)
    if c is None:
        raise ValidationError(f"No concern with id {concern_id}")
    p = require_dsl(principal, action="acknowledge",
                    student_id=c.student_id, record_ref=_ref(concern_id))
    return update_concern(concern_id, {
        "dsl_notified": True,
        "dsl_name": c.dsl_name or _actor(p),
        "dsl_notified_at": c.dsl_notified_at or _dt.date.today().isoformat(),
    }, principal=p)


def list_concerns_with_detail(**kwargs) -> list[ConcernRow]:
    principal = kwargs.pop("principal", None)
    rows = list_concerns(principal=principal, **kwargs)
    if not rows:
        return []
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    names = {s.student_id: s.full_name for s in _students.list_students()}
    counts = _update_counts()
    out: list[ConcernRow] = []
    for c in rows:
        out.append(ConcernRow(
            concern=c,
            student_name=(names.get(c.student_id) or c.student_name
                          or "(left — no record)"),
            update_count=counts.get(c.concern_id, 0),
        ))
    return out


def update_concern(concern_id: int, data: dict[str, Any], *,
                   principal: access.Principal | None = None) -> Concern:
    init_db()
    existing = _get_concern(concern_id)
    if existing is None:
        logger.warning("update_concern: unknown id %d", concern_id)
        raise ValidationError(f"No concern with id {concern_id}")
    p = require_dsl(principal, action="update",
                    student_id=existing.student_id,
                    record_ref=_ref(concern_id))
    # A non-DSL-designation reader sees restricted notes redacted; never
    # let that placeholder overwrite the real text.
    restricted = data.get("restricted_notes", existing.restricted_notes)
    if not can_see_restricted(p):
        restricted = existing.restricted_notes
    payload = _validate_concern_payload({
        "_existing":           True,
        "student_id":          existing.student_id,
        "concern_date":        data.get("concern_date", existing.concern_date),
        "reported_date":       data.get("reported_date", existing.reported_date),
        "concern_type":        data.get("concern_type", existing.concern_type),
        "category":            data.get("category", existing.category),
        "risk_level":          data.get("risk_level", existing.risk_level),
        "reported_by":         data.get("reported_by", existing.reported_by),
        "description":         data.get("description", existing.description),
        "action_taken":        data.get("action_taken", existing.action_taken),
        "dsl_notified":        data.get("dsl_notified", existing.dsl_notified),
        "dsl_name":            data.get("dsl_name", existing.dsl_name),
        "dsl_notified_at":     data.get("dsl_notified_at",
                                        existing.dsl_notified_at),
        "parents_informed":    data.get("parents_informed",
                                        existing.parents_informed),
        "parents_informed_at": data.get("parents_informed_at",
                                        existing.parents_informed_at),
        "external_agencies":   data.get("external_agencies",
                                        existing.external_agencies),
        "referral_made":       data.get("referral_made", existing.referral_made),
        "referral_date":       data.get("referral_date", existing.referral_date),
        "referral_ref":        data.get("referral_ref", existing.referral_ref),
        "status":              data.get("status", existing.status),
        "follow_up_date":      data.get("follow_up_date",
                                        existing.follow_up_date),
        "notes":               data.get("notes", existing.notes),
        "access_level":        data.get("access_level", existing.access_level),
        "restricted_notes":    restricted,
        "body_map_ref":        data.get("body_map_ref", existing.body_map_ref),
        "body_map_notes":      data.get("body_map_notes",
                                        existing.body_map_notes),
    })
    payload.pop("_student", None)
    # Re-opening an archived concern clears the archive stamp.
    archived = (existing.archived_reason, existing.archived_by,
                existing.archived_at)
    if existing.is_archived and payload["status"] != ARCHIVED_STATUS:
        archived = (None, None, None)
    with _connect() as conn:
        conn.execute(
            """UPDATE safeguarding_concerns SET
                   concern_date = ?, reported_date = ?, concern_type = ?,
                   category = ?, risk_level = ?, reported_by = ?,
                   description = ?, action_taken = ?,
                   dsl_notified = ?, dsl_name = ?, dsl_notified_at = ?,
                   parents_informed = ?, parents_informed_at = ?,
                   external_agencies = ?, referral_made = ?,
                   referral_date = ?, referral_ref = ?, status = ?,
                   follow_up_date = ?, notes = ?,
                   access_level = ?, restricted_notes = ?,
                   body_map_ref = ?, body_map_notes = ?,
                   archived_reason = ?, archived_by = ?, archived_at = ?,
                   updated_at = datetime('now')
               WHERE concern_id = ?""",
            (payload["concern_date"], payload["reported_date"],
             payload["concern_type"],
             payload["category"], payload["risk_level"],
             payload["reported_by"],
             payload["description"], payload["action_taken"],
             payload["dsl_notified"], payload["dsl_name"],
             payload["dsl_notified_at"],
             payload["parents_informed"], payload["parents_informed_at"],
             payload["external_agencies"], payload["referral_made"],
             payload["referral_date"], payload["referral_ref"],
             payload["status"],
             payload["follow_up_date"], payload["notes"],
             payload["access_level"], payload["restricted_notes"],
             payload["body_map_ref"], payload["body_map_notes"],
             *archived, concern_id),
        )
        conn.commit()
    out = _get_concern(concern_id)
    assert out is not None
    logger.info(
        "Updated safeguarding concern #%d (status=%s, risk=%s)",
        concern_id, out.status, out.risk_level,
    )
    return _redact(out, p)


def archive_concern(concern_id: int, *, reason: str,
                    archived_by: str | None = None,
                    principal: access.Principal | None = None) -> Concern:
    """Close a concern as retained. The record and chronology stay."""
    init_db()
    existing = _get_concern(concern_id)
    if existing is None:
        raise ValidationError(f"No concern with id {concern_id}")
    p = require_dsl(principal, action="archive",
                    student_id=existing.student_id,
                    record_ref=_ref(concern_id))
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("A reason is required to close a concern")
    who = (archived_by or "").strip() or _actor(p)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute(
            "UPDATE safeguarding_concerns SET status = ?, "
            "archived_reason = ?, archived_by = ?, archived_at = ?, "
            "updated_at = datetime('now') WHERE concern_id = ?",
            (ARCHIVED_STATUS, reason, who, now, concern_id))
        conn.execute(
            "INSERT INTO safeguarding_updates (concern_id, update_date, "
            "update_text, updated_by, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            (concern_id, now[:10],
             f"Closed — retained. Reason: {reason}", who))
        conn.commit()
    logger.info("Archived safeguarding concern #%d (%s, by %s)",
                concern_id, reason, who)
    out = _get_concern(concern_id)
    assert out is not None
    return _redact(out, p)


def delete_concern(concern_id: int, *, reason: str | None = None,
                   principal: access.Principal | None = None) -> bool:
    """Retained for old callers: archives, never deletes (KCSIE)."""
    if _get_concern(concern_id) is None:
        logger.warning("delete_concern: unknown id %d", concern_id)
        return False
    archive_concern(
        concern_id,
        reason=(reason or "Closed from the delete action — record retained"),
        principal=principal)
    return True


# ── Chronology / update CRUD ──────────────────────────────────────

def add_update(concern_id: int, data: dict[str, Any], *,
               principal: access.Principal | None = None) -> Update:
    init_db()
    c = _get_concern(concern_id)
    if c is None:
        raise ValidationError(f"No concern with id {concern_id}")
    p = require_dsl(principal, action="add-update",
                    student_id=c.student_id, record_ref=_ref(concern_id))
    data = dict(data)
    data["updated_by"] = (data.get("updated_by") or "").strip() or _actor(p)
    try:
        payload = _validate_update_payload(data)
    except ValidationError as e:
        logger.warning("add_update validation failed for #%d: %s",
                       concern_id, e)
        raise
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO safeguarding_updates
                   (concern_id, update_date, update_text, updated_by,
                    created_at)
               VALUES (?, ?, ?, ?, datetime('now'))""",
            (concern_id, payload["update_date"], payload["update_text"],
             payload["updated_by"]),
        )
        conn.commit()
        new_id = cur.lastrowid
        # Touch the parent's updated_at so the directory shows freshness.
        conn.execute(
            "UPDATE safeguarding_concerns SET updated_at = datetime('now') "
            "WHERE concern_id = ?", (concern_id,),
        )
        conn.commit()
    out = _get_update(new_id)
    assert out is not None
    logger.info(
        "Added safeguarding update #%d to concern #%d (%s, by %s)",
        new_id, concern_id, payload["update_date"],
        payload["updated_by"] or "—",
    )
    return out


def _get_update(update_id: int) -> Update | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM safeguarding_updates WHERE update_id = ?",
            (update_id,),
        ).fetchone()
        return _row_update(r) if r else None


def get_update(update_id: int, *,
               principal: access.Principal | None = None) -> Update | None:
    u = _get_update(update_id)
    require_dsl(principal, action="view-update",
                record_ref=_ref(u.concern_id) if u else None)
    return u


def _list_updates(concern_id: int) -> list[Update]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM safeguarding_updates WHERE concern_id = ? "
            "ORDER BY update_date, update_id",
            (concern_id,),
        ).fetchall()
        return [_row_update(r) for r in rows]


def list_updates(concern_id: int, *,
                 principal: access.Principal | None = None) -> list[Update]:
    c = _get_concern(concern_id)
    require_dsl(principal, action="list-updates",
                student_id=c.student_id if c else None,
                record_ref=_ref(concern_id))
    return _list_updates(concern_id)


def _update_counts() -> dict[int, int]:
    init_db()
    with _connect() as conn:
        return {int(r[0]): int(r[1]) for r in conn.execute(
            "SELECT concern_id, COUNT(*) FROM safeguarding_updates "
            "GROUP BY concern_id")}


def count_updates(concern_id: int, *,
                  principal: access.Principal | None = None) -> int:
    require_dsl(principal, action="count-updates",
                record_ref=_ref(concern_id))
    return _update_counts().get(concern_id, 0)


def edit_update(update_id: int, data: dict[str, Any], *,
                principal: access.Principal | None = None) -> Update:
    init_db()
    existing = _get_update(update_id)
    if existing is None:
        raise ValidationError(f"No update with id {update_id}")
    require_dsl(principal, action="edit-update",
                record_ref=_ref(existing.concern_id))
    if existing.retracted:
        raise ValidationError("A retracted entry cannot be edited")
    payload = _validate_update_payload({
        "update_date": data.get("update_date", existing.update_date),
        "update_text": data.get("update_text", existing.update_text),
        "updated_by":  data.get("updated_by", existing.updated_by),
    })
    with _connect() as conn:
        conn.execute(
            "UPDATE safeguarding_updates SET update_date = ?, "
            "update_text = ?, updated_by = ? WHERE update_id = ?",
            (payload["update_date"], payload["update_text"],
             payload["updated_by"], update_id),
        )
        conn.commit()
    logger.info("Edited safeguarding update #%d", update_id)
    out = _get_update(update_id)
    assert out is not None
    return out


def retract_update(update_id: int, *, reason: str,
                   principal: access.Principal | None = None) -> Update:
    """Strike an entry through. Its text stays on the file."""
    init_db()
    existing = _get_update(update_id)
    if existing is None:
        raise ValidationError(f"No update with id {update_id}")
    p = require_dsl(principal, action="retract-update",
                    record_ref=_ref(existing.concern_id))
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("A reason is required to retract an entry")
    with _connect() as conn:
        conn.execute(
            "UPDATE safeguarding_updates SET retracted = 1, "
            "retracted_reason = ?, retracted_by = ?, "
            "retracted_at = datetime('now') WHERE update_id = ?",
            (reason, _actor(p), update_id))
        conn.commit()
    logger.info("Retracted safeguarding update #%d (%s)", update_id, reason)
    out = _get_update(update_id)
    assert out is not None
    return out


def delete_update(update_id: int, *, reason: str | None = None,
                  principal: access.Principal | None = None) -> bool:
    """Retained for old callers: retracts, never deletes."""
    if _get_update(update_id) is None:
        return False
    retract_update(update_id,
                   reason=reason or "Retracted from the delete action",
                   principal=principal)
    return True


# ── Linked students ───────────────────────────────────────────────

def link_student(concern_id: int, student_id: str, *,
                 link_role: str = "Also involved",
                 principal: access.Principal | None = None) -> LinkedStudent:
    init_db()
    c = _get_concern(concern_id)
    if c is None:
        raise ValidationError(f"No concern with id {concern_id}")
    p = require_dsl(principal, action="link-student",
                    student_id=student_id, record_ref=_ref(concern_id))
    if link_role not in LINK_ROLES:
        raise ValidationError(
            f"Link role must be one of: {', '.join(LINK_ROLES)}")
    sid = (student_id or "").strip()
    if sid == c.student_id:
        raise ValidationError("That learner is already the subject of "
                              "this concern")
    from education_system.systems.sixth_form.domain.learners.students import students as _students
    s = _students.get_student(sid)
    if s is None:
        raise ValidationError(f"No student with id {sid}")
    with _connect() as conn:
        dup = conn.execute(
            "SELECT link_id FROM safeguarding_concern_students "
            "WHERE concern_id = ? AND student_id = ? AND removed_at IS NULL",
            (concern_id, sid)).fetchone()
        if dup:
            raise ValidationError("That learner is already linked")
        cur = conn.execute(
            "INSERT INTO safeguarding_concern_students "
            "(concern_id, student_id, student_name, link_role, added_by) "
            "VALUES (?, ?, ?, ?, ?)",
            (concern_id, sid, s.full_name, link_role, _actor(p)))
        conn.commit()
        link_id = cur.lastrowid
    logger.info("Linked %s to safeguarding concern #%d", sid, concern_id)
    return next(x for x in _linked(concern_id) if x.link_id == link_id)


def _linked(concern_id: int) -> list[LinkedStudent]:
    init_db()
    with _connect() as conn:
        return [LinkedStudent(
            link_id=r["link_id"], concern_id=r["concern_id"],
            student_id=r["student_id"], student_name=r["student_name"],
            link_role=r["link_role"], added_by=r["added_by"],
            added_at=r["added_at"]) for r in conn.execute(
                "SELECT * FROM safeguarding_concern_students "
                "WHERE concern_id = ? AND removed_at IS NULL "
                "ORDER BY link_id", (concern_id,))]


def linked_students(concern_id: int, *,
                    principal: access.Principal | None = None
                    ) -> list[LinkedStudent]:
    require_dsl(principal, action="list-linked", record_ref=_ref(concern_id))
    return _linked(concern_id)


def unlink_student(link_id: int, *, reason: str,
                   principal: access.Principal | None = None) -> bool:
    """Mark a link as removed (kept for the audit trail)."""
    init_db()
    p = require_dsl(principal, action="unlink-student",
                    record_ref=f"link:{link_id}")
    if not (reason or "").strip():
        raise ValidationError("A reason is required to remove a link")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE safeguarding_concern_students SET removed_at = "
            "datetime('now'), removed_by = ?, removed_reason = ? "
            "WHERE link_id = ? AND removed_at IS NULL",
            (_actor(p), reason.strip(), link_id))
        conn.commit()
        return bool(cur.rowcount)


# ── Restricted notes / body map / attachments ────────────────────

def set_restricted_notes(concern_id: int, notes: str | None, *,
                         principal: access.Principal | None = None) -> Concern:
    p = _principal(principal)
    if not can_see_restricted(p):
        require_dsl(p, action="restricted-notes-refused",
                    record_ref=_ref(concern_id))
        raise access.AccessDenied(
            "Only the DSL can write restricted notes.")
    return update_concern(concern_id, {
        "restricted_notes": notes or "",
        "access_level": "Restricted" if (notes or "").strip() else "Standard",
    }, principal=p)


def set_body_map(concern_id: int, *, body_map_ref: str | None,
                 body_map_notes: str | None,
                 principal: access.Principal | None = None) -> Concern:
    """Record where a body map lives (file / attachment id) and what it shows."""
    return update_concern(concern_id, {
        "body_map_ref": body_map_ref or "",
        "body_map_notes": body_map_notes or "",
    }, principal=principal)


def add_attachment(concern_id: int, *, title: str, file_ref: str,
                   category: str = "Evidence",
                   file_name: str | None = None,
                   description: str | None = None,
                   principal: access.Principal | None = None):
    """Attach a file reference via the shared attachments register.

    Always stored as *Confidential*, PII, against entity type
    "Safeguarding" and the concern id — never the learner's name.
    """
    c = _get_concern(concern_id)
    if c is None:
        raise ValidationError(f"No concern with id {concern_id}")
    p = require_dsl(principal, action="add-attachment",
                    student_id=c.student_id, record_ref=_ref(concern_id))
    from education_system.systems.sixth_form.domains.communications.domain.attachments import (
        attachments as _att,
    )
    try:
        return _att.create_attachment({
            "entity_type": "Safeguarding",
            "entity_id": str(concern_id),
            "title": title,
            "description": description,
            "category": category,
            "visibility": "Confidential",
            "file_ref": file_ref,
            "file_name": file_name,
            "uploaded_by": _actor(p),
            "contains_pii": True,
        })
    except _att.ValidationError as e:
        raise ValidationError(str(e)) from e


def list_attachments(concern_id: int, *,
                     principal: access.Principal | None = None) -> list:
    require_dsl(principal, action="list-attachments",
                record_ref=_ref(concern_id))
    from education_system.systems.sixth_form.domains.communications.domain.attachments import (
        attachments as _att,
    )
    return _att.attachments_for("Safeguarding", str(concern_id))


# ── Prevent links (read-through, separate stores) ─────────────────

def link_prevent_concern(concern_id: int, prevent_concern_id: int, *,
                         note: str | None = None,
                         principal: access.Principal | None = None) -> None:
    init_db()
    c = _get_concern(concern_id)
    if c is None:
        raise ValidationError(f"No concern with id {concern_id}")
    p = require_dsl(principal, action="link-prevent",
                    student_id=c.student_id, record_ref=_ref(concern_id))
    from education_system.systems.sixth_form.domain.safeguarding.prevent_duty import (
        prevent_duty as _pd,
    )
    pc = _pd._get_concern(int(prevent_concern_id))
    if pc is None:
        raise ValidationError(f"No Prevent concern #{prevent_concern_id}")
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO safeguarding_prevent_links "
            "(concern_id, prevent_concern_id, linked_by, note) "
            "VALUES (?, ?, ?, ?)",
            (concern_id, int(prevent_concern_id), _actor(p),
             (note or "").strip() or None))
        conn.commit()
    logger.info("Linked Prevent concern #%s to safeguarding concern #%d",
                prevent_concern_id, concern_id)


def unlink_prevent_concern(concern_id: int, prevent_concern_id: int, *,
                           principal: access.Principal | None = None) -> bool:
    """Remove a mistaken link. Neither record is touched."""
    init_db()
    require_dsl(principal, action="unlink-prevent",
                record_ref=_ref(concern_id))
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM safeguarding_prevent_links WHERE concern_id = ? "
            "AND prevent_concern_id = ?", (concern_id, int(prevent_concern_id)))
        conn.commit()
        return bool(cur.rowcount)


def _prevent_ids(concern_id: int) -> list[int]:
    init_db()
    with _connect() as conn:
        return [int(r[0]) for r in conn.execute(
            "SELECT prevent_concern_id FROM safeguarding_prevent_links "
            "WHERE concern_id = ? ORDER BY link_id", (concern_id,))]


def prevent_links(concern_id: int, *,
                  principal: access.Principal | None = None) -> list:
    """The linked Prevent concerns themselves (read from their store)."""
    require_dsl(principal, action="list-prevent-links",
                record_ref=_ref(concern_id))
    from education_system.systems.sixth_form.domain.safeguarding.prevent_duty import (
        prevent_duty as _pd,
    )
    out = []
    for pid in _prevent_ids(concern_id):
        pc = _pd._get_concern(pid)
        if pc is not None:
            out.append(pc)
    return out


# ── Chronology & access log ──────────────────────────────────────

def student_chronology(student_id: str, *,
                       principal: access.Principal | None = None) -> list:
    """Every dated entry on a learner's file, oldest first.

    See :func:`safeguarding_casework.student_chronology`.
    """
    from education_system.systems.sixth_form.domain.safeguarding import (
        safeguarding_casework as _cw,
    )
    return _cw.student_chronology(student_id, principal=principal)


def who_viewed(*, concern_id: int | None = None,
               student_id: str | None = None, limit: int = 500,
               principal: access.Principal | None = None) -> list[dict]:
    """Who opened or changed a record, newest first (DSL only)."""
    require_dsl(principal, action="view-access-log",
                student_id=student_id,
                record_ref=_ref(concern_id) if concern_id else None)
    if concern_id is not None:
        # Some concern-level reads log only the record ref, so scan the
        # area rather than filtering by learner.
        ref = _ref(concern_id)
        rows = access.list_sensitive_access(area=AREA, limit=max(limit, 5000))
        return [r for r in rows if r.get("record_ref") == ref][:limit]
    return access.list_sensitive_access(
        student_id=student_id, area=AREA, limit=limit)


# ── Summary ───────────────────────────────────────────────────────

@dataclass
class Summary:
    total: int
    open_count: int
    by_status: dict[str, int]
    by_risk: dict[str, int]
    by_category: dict[str, int]
    dsl_notified: int
    parents_informed: int
    referrals: int
    upcoming_follow_ups: int     # follow_up_date within window
    overdue_follow_ups: int      # follow_up_date < today, status still open
    high_risk_open: int          # High or Critical & still open
    unreviewed_reports: int = 0  # filed but DSL not yet notified
    adult_open: int = 0          # open concerns about learners 18+
    archived: int = 0            # Closed — Retained


def summary(*, upcoming_window_days: int = 14,
            principal: access.Principal | None = None) -> Summary:
    require_dsl(principal, action="summary")
    rows = _list_concerns()
    today = _dt.date.today().isoformat()
    cutoff = (_dt.date.today() + _dt.timedelta(days=upcoming_window_days)
              ).isoformat()

    by_status = {s: 0 for s in STATUSES}
    by_risk = {r: 0 for r in RISK_LEVELS}
    by_category: dict[str, int] = {}
    open_count = 0
    dsl = 0
    parents = 0
    refs = 0
    upcoming = 0
    overdue = 0
    high_open = 0
    unreviewed = 0
    adult_open = 0
    archived = 0
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        by_risk[r.risk_level] = by_risk.get(r.risk_level, 0) + 1
        by_category[r.category] = by_category.get(r.category, 0) + 1
        is_open = r.status in OPEN_STATUSES
        if is_open:
            open_count += 1
            if not r.dsl_notified:
                unreviewed += 1
            if r.adult_safeguarding:
                adult_open += 1
        if r.is_archived:
            archived += 1
        if r.dsl_notified:
            dsl += 1
        if r.parents_informed:
            parents += 1
        if r.referral_made:
            refs += 1
        if r.risk_level in ("High", "Critical") and is_open:
            high_open += 1
        if r.follow_up_date and is_open:
            if r.follow_up_date < today:
                overdue += 1
            elif r.follow_up_date <= cutoff:
                upcoming += 1
    return Summary(
        total=len(rows), open_count=open_count,
        by_status=by_status, by_risk=by_risk, by_category=by_category,
        dsl_notified=dsl, parents_informed=parents, referrals=refs,
        upcoming_follow_ups=upcoming, overdue_follow_ups=overdue,
        high_risk_open=high_open, unreviewed_reports=unreviewed,
        adult_open=adult_open, archived=archived,
    )
