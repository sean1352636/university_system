"""Student data layer for the Sixth Form System.

Owns the local SQLite DB (``data/sixthform.db``), the student_id /
sixth-form-email generation rules, the A-Level subject list, and the
CRUD functions used by the GUI panels.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any
from education_system import paths
from education_system.systems.sixth_form.domain.learners.students.student_profile import (
    ETHNICITY_LABELS,
    ValidationError,
    ADDRESS_LINE_FIELDS,
    GENDER_CODES,
    _validate_profile,
    gender_code,
    normalise_relationship,
    validate_upn,
)

logger = logging.getLogger(__name__)

# Re-exported so existing references to ``students.DB_PATH`` keep working.
# Tests that need an isolated DB still rebind this module attribute.
DB_PATH = paths.SIXTH_FORM_STUDENTS_DB

EMAIL_DOMAIN = "sixthform.ac.uk"
ID_PREFIX = "C"
ID_DIGITS = 7

A_LEVEL_SUBJECTS: list[str] = [
    "Mathematics",
    "Further Mathematics",
    "English Literature",
    "English Language",
    "Physics",
    "Chemistry",
    "Biology",
    "History",
    "Geography",
    "Economics",
    "Business Studies",
    "Accounting",
    "Psychology",
    "Sociology",
    "Computer Science",
    "Art and Design",
    "Music",
    "French",
    "Spanish",
    "German",
    "Religious Studies",
    "Politics",
    "Philosophy",
    "Media Studies",
    "Drama and Theatre",
    "Physical Education",
    "Law",
]

_PHONE_RE = re.compile(r"^[0-9 +()\-]{6,20}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Sixth-form system maps to the seeded shared-auth system_key "sixth_form".
AUTH_SYSTEM_KEY = "sixth_form"
AUTH_ROLE = "student"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    student_id                  TEXT PRIMARY KEY,
    first_name                  TEXT NOT NULL,
    middle_name                 TEXT,
    last_name                   TEXT NOT NULL,
    title                       TEXT,
    gender                      TEXT,
    date_of_birth               TEXT,
    phone                       TEXT,
    email                       TEXT NOT NULL UNIQUE,
    emergency_contact_name      TEXT,
    emergency_contact_phone     TEXT,
    emergency_contact_relation  TEXT,
    subject_1                   TEXT,
    subject_2                   TEXT,
    subject_3                   TEXT,
    status                      TEXT NOT NULL DEFAULT 'Active',
    created_at                  TEXT DEFAULT (datetime('now'))
);
"""

# Optional fields useful for university-system handover. Title/gender
# match the university CRUD's allowed values verbatim so an import can
# be a straight copy.
TITLES: tuple[str, ...] = ("Mr", "Ms", "Mrs", "Dr", "Prof")
GENDERS: tuple[str, ...] = GENDER_CODES  # stored values; the form shows GENDER_OPTIONS

# Student-record lifecycle. ``Active`` is the default; ``Inactive``
# covers temporary breaks (illness, year-out), ``Suspended`` is
# disciplinary, ``Left`` is anyone who has gone (transferred,
# withdrawn, or finished). Distinct from enrolment status, which is
# per-academic-year on the ``enrolments`` table.
STATUSES: tuple[str, ...] = ("Active", "Inactive", "Suspended", "Left")
DEFAULT_STATUS: str = "Active"
#: Statuses that are still on roll. ``Left`` is the only one that is not.
ON_ROLL_STATUSES: tuple[str, ...] = ("Active", "Inactive", "Suspended")

#: Youngest and oldest believable learner, in years, when a date of birth
#: is entered. Outside this it is almost certainly a typing slip.
MIN_AGE, MAX_AGE = 14, 99

# Columns added alongside the original schema, with what the record
# history calls them. ``leaving_*`` are written by withdraw/reinstate,
# never by the form.
_PROFILE_FIELDS: tuple[tuple[str, str], ...] = (
    ("preferred_name",  "Preferred name"),
    ("pronouns",        "Pronouns"),
    ("address",         "Home address"),
    ("address_line1",   "Address line 1"),
    ("address_line2",   "Address line 2"),
    ("town",            "Town"),
    ("postcode",        "Postcode"),
    ("previous_school", "Previous school"),
    ("ethnicity",       "Ethnicity"),
    ("nationality",     "Nationality"),
    ("first_language",  "First language"),
    ("start_date",      "Start date"),
    ("leaving_date",    "Leaving date"),
    ("leaving_reason",  "Leaving reason"),
    # Staff notes on the record. Not in the learner's update e-mail.
    ("notes",           "Notes"),
)
_FORM_PROFILE_FIELDS: tuple[str, ...] = tuple(
    k for k, _l in _PROFILE_FIELDS if not k.startswith("leaving_"))

# Who changed what on a student record, and when. Deliberately no foreign
# key to ``students``: the row that says a record was deleted has to
# outlive the record, and a cascade would take the history with it.
_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS student_record_history (
    history_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  TEXT NOT NULL,
    at          TEXT NOT NULL DEFAULT (datetime('now')),
    changed_by  TEXT,
    field       TEXT NOT NULL,
    old_value   TEXT,
    new_value   TEXT,
    note        TEXT
);
CREATE INDEX IF NOT EXISTS idx_srh_student ON student_record_history(student_id, at);
"""


@dataclass
class Student:
    student_id: str
    first_name: str
    middle_name: str | None
    last_name: str
    phone: str | None
    email: str
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    emergency_contact_relation: str | None
    subject_1: str | None
    subject_2: str | None
    subject_3: str | None
    title: str | None = None
    gender: str | None = None
    date_of_birth: str | None = None
    status: str = "Active"
    #: Set once the onward transfer has been announced successfully. The
    #: transfer's own completion marker — ``status`` cannot serve as one,
    #: because 'Left' also means withdrawn or finished.
    transferred_at: str | None = None
    #: Unique Learner Number (LRS, 10 digits with check digit).
    uln: str | None = None
    #: JCQ Unique Candidate Identifier (13 chars, format-checked only).
    uci: str | None = None
    #: 4-digit centre candidate number.
    candidate_number: str | None = None
    #: The learner's own address, as opposed to the college one.
    personal_email: str | None = None
    preferred_name: str | None = None
    pronouns: str | None = None
    #: Home address, one line per line of the address (postcode separate).
    address: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    town: str | None = None
    postcode: str | None = None
    previous_school: str | None = None
    #: ILR ethnicity code; see ``ETHNICITIES``.
    ethnicity: str | None = None
    nationality: str | None = None
    first_language: str | None = None
    #: When the learner started at the college, and when and why they left.
    start_date: str | None = None
    leaving_date: str | None = None
    leaving_reason: str | None = None
    notes: str | None = None

    @property
    def display_name(self) -> str:
        """The name to call the learner by: preferred first name if held."""
        return f"{self.preferred_name or self.first_name} {self.last_name}".strip()

    @property
    def ethnicity_label(self) -> str | None:
        return ETHNICITY_LABELS.get(self.ethnicity or "", self.ethnicity)

    @property
    def on_roll(self) -> bool:
        return self.status in ON_ROLL_STATUSES

    @property
    def transfer_complete(self) -> bool:
        """Whether this student's onward transfer was announced."""
        return bool(self.transferred_at)

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.middle_name or "", self.last_name]
        return " ".join(p for p in parts if p).strip()

    @property
    def subjects(self) -> list[str]:
        return [s for s in (self.subject_1, self.subject_2, self.subject_3) if s]


# ── DB plumbing ──────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    """Apply the schema once per process and log it once.

    Subsequent calls are cheap no-ops so callers can safely guard
    every entry point with ``init_db()`` without spamming the log.

    Also installs the persistent log handler on first call so that
    every subsequent ``logger.info/warning/...`` from sixth-form
    modules is captured to the ``system_logs`` table.
    """
    global _DB_READY
    if _DB_READY:
        return
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        # Backfill columns added after the original schema shipped.
        # SQLite's ADD COLUMN is the only safe migration here — we
        # check PRAGMA table_info to make it idempotent.
        existing_cols = {
            r["name"] for r in conn.execute(
                "PRAGMA table_info(students)").fetchall()
        }
        for col, ddl in (
                ("title",         "TEXT"),
                ("gender",        "TEXT"),
                ("date_of_birth", "TEXT"),
                ("status",        "TEXT NOT NULL DEFAULT 'Active'"),
                # When the onward transfer completed end to end. Deliberately
                # not derivable from ``status``: 'Left' covers transferred,
                # withdrawn *and* finished, so it cannot answer "has this
                # student's transfer been announced?" — see mark_transferred.
                ("transferred_at", "TEXT"),
                # Learner identifiers for the ILR / census and exam
                # entries — see qualifications.identifiers.
                ("uln",              "TEXT"),
                ("uci",              "TEXT"),
                ("candidate_number", "TEXT"),
                # The form and the validator always took a personal email,
                # but there was no column, so every one typed in was
                # validated and then dropped on the floor.
                ("personal_email",   "TEXT"),
                # Profile, address, census and start/leave fields — see
                # _PROFILE_FIELDS. Admissions conversion and the census
                # return both read these and used to find nothing.
                *((col, "TEXT") for col, _label in _PROFILE_FIELDS),
        ):
            if col not in existing_cols:
                conn.execute(
                    f"ALTER TABLE students ADD COLUMN {col} {ddl}")
                logger.info("Sixth-form students: added column %s", col)
        conn.executescript(_HISTORY_SCHEMA)
        conn.commit()
    # Wire up the persistent log table before we emit our own first
    # "ready" message so even that lands in the audit trail.
    try:
        from education_system.systems.sixth_form.infrastructure import log_store
        log_store.install()
    except Exception:
        logger.exception("Could not install persistent log handler")
    logger.info("Sixth form students DB ready at %s", DB_PATH)
    _DB_READY = True


def _row_to_student(row: sqlite3.Row) -> Student:
    return Student(
        student_id=row["student_id"],
        first_name=row["first_name"],
        middle_name=row["middle_name"],
        last_name=row["last_name"],
        phone=row["phone"],
        email=row["email"],
        emergency_contact_name=row["emergency_contact_name"],
        emergency_contact_phone=row["emergency_contact_phone"],
        emergency_contact_relation=row["emergency_contact_relation"],
        subject_1=row["subject_1"],
        subject_2=row["subject_2"],
        subject_3=row["subject_3"],
        title=(row["title"] if "title" in row.keys() else None),
        gender=(row["gender"] if "gender" in row.keys() else None),
        date_of_birth=(row["date_of_birth"]
                        if "date_of_birth" in row.keys() else None),
        status=(row["status"] if "status" in row.keys() else "Active") or "Active",
        transferred_at=(row["transferred_at"]
                        if "transferred_at" in row.keys() else None),
        uln=(row["uln"] if "uln" in row.keys() else None),
        uci=(row["uci"] if "uci" in row.keys() else None),
        candidate_number=(row["candidate_number"]
                          if "candidate_number" in row.keys() else None),
        personal_email=(row["personal_email"]
                        if "personal_email" in row.keys() else None),
        **{col: (row[col] if col in row.keys() else None)
           for col, _label in _PROFILE_FIELDS},
    )


# ── Generators ──────────────────────────────────────────────────────

def generate_student_id() -> str:
    """Return a fresh, unused id like 'C1470977' (C + 7 digits)."""
    init_db()
    with _connect() as conn:
        for attempt in range(50):
            n = random.randint(10 ** (ID_DIGITS - 1), 10 ** ID_DIGITS - 1)
            sid = f"{ID_PREFIX}{n}"
            row = conn.execute(
                "SELECT 1 FROM students WHERE student_id = ?", (sid,)
            ).fetchone()
            if row is None:
                if attempt == 0:
                    logger.debug("Allocated student id %s on first attempt", sid)
                else:
                    logger.info(
                        "Allocated student id %s after %d collisions",
                        sid, attempt)
                return sid
            if attempt == 25:
                logger.warning(
                    "Student-id allocator hit %d collisions — namespace "
                    "may be getting crowded", attempt)
    logger.error("Exhausted 50 attempts allocating a unique student id")
    raise RuntimeError("Could not allocate a unique student id after 50 tries")


def generate_sixthform_email(student_id: str) -> str:
    return f"{student_id.lower()}@{EMAIL_DOMAIN}"


# ── Validation ──────────────────────────────────────────────────────

def _require(value: str | None, label: str) -> str:
    if not value or not value.strip():
        raise ValidationError(f"{label} is required")
    return value.strip()


def _require_writer(action: str, *, lifecycle: bool = False) -> None:
    """Writes need ``students.manage`` (status changes also accept
    ``admissions``, whose enrolment withdrawals mark a learner Left).
    Reads are open; nobody signed in and no system actor is refused."""
    from education_system.systems.sixth_form.domain.admissions import _guard
    _guard.require_any(("students.manage", "admissions") if lifecycle
                       else ("students.manage",), action)


def _validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["first_name"] = _require(data.get("first_name"), "First name")
    out["middle_name"] = (data.get("middle_name") or "").strip() or None
    out["last_name"] = _require(data.get("last_name"), "Last name")

    title = (data.get("title") or "").strip() or None
    if title is not None and title not in TITLES:
        raise ValidationError(
            f"Title must be one of: {', '.join(TITLES)}")
    out["title"] = title

    out["gender"] = gender_code(data.get("gender"))

    dob = (data.get("date_of_birth") or "").strip() or None
    if dob is not None:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", dob):
            raise ValidationError(
                "Date of birth must be YYYY-MM-DD")
        try:
            born = _dt.date.fromisoformat(dob)
        except ValueError:
            raise ValidationError(
                "Date of birth is not a real calendar date") from None
        today = _dt.date.today()
        if born > today:
            raise ValidationError("Date of birth is in the future")
        age = today.year - born.year - ((today.month, today.day)
                                        < (born.month, born.day))
        if not MIN_AGE <= age <= MAX_AGE:
            raise ValidationError(
                f"Date of birth gives an age of {age}; a learner must be "
                f"between {MIN_AGE} and {MAX_AGE}. Check the year.")
    out["date_of_birth"] = dob

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    phone = (data.get("phone") or "").strip()
    if phone and not _PHONE_RE.match(phone):
        raise ValidationError("Phone number contains invalid characters")
    out["phone"] = phone or None

    personal_email = (data.get("personal_email") or "").strip()
    if personal_email and not _EMAIL_RE.match(personal_email):
        raise ValidationError("Personal email is not a valid address")
    out["personal_email"] = personal_email or None

    out["emergency_contact_name"] = (
        data.get("emergency_contact_name") or "").strip() or None
    ec_phone = (data.get("emergency_contact_phone") or "").strip()
    if ec_phone and not _PHONE_RE.match(ec_phone):
        raise ValidationError(
            "Emergency contact phone contains invalid characters")
    out["emergency_contact_phone"] = ec_phone or None
    out["emergency_contact_relation"] = normalise_relationship(
        data.get("emergency_contact_relation"))

    out.update(_validate_profile(data))

    subjects = [
        (data.get("subject_1") or "").strip(),
        (data.get("subject_2") or "").strip(),
        (data.get("subject_3") or "").strip(),
    ]
    chosen = [s for s in subjects if s]
    # The three slots are now mirrors of the learner's first three active
    # A-level aims (qualifications.learning_aims). A learner on a BTEC, a
    # T Level or a two-A-level programme legitimately has fewer than
    # three, so the old "exactly three" rule would refuse their record;
    # the slots only have to be distinct, known subjects.
    if len(set(chosen)) != len(chosen):
        raise ValidationError("A-Level subjects must be distinct")
    # Validate against the live subjects table (source of truth) but
    # fall back to the seed list if the table isn't there yet (e.g.
    # during unit tests that don't import the subjects module).
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import subjects as _subjects
        for s in chosen:
            if not _subjects.is_valid_subject(s):
                raise ValidationError(f"Unknown A-Level subject: {s}")
    except ImportError:
        for s in chosen:
            if s not in A_LEVEL_SUBJECTS:
                raise ValidationError(f"Unknown A-Level subject: {s}")
    out["subject_1"], out["subject_2"], out["subject_3"] = subjects
    return out


# ── UPN ─────────────────────────────────────────────────────────────

def _ensure_upn_store() -> None:
    """Create the UPN link table if no CTF work has run yet."""
    from education_system.systems.sixth_form.domain.operations.integrations import ctf
    ctf.store.init_db()


def get_upn(student_id: str) -> str | None:
    """The learner's UPN. Held once, in the CTF UPN link table."""
    from education_system.systems.sixth_form.domain.operations.integrations import ctf
    try:
        return ctf.upn_for_student(student_id)
    except Exception:
        logger.debug("No UPN lookup for %s", student_id, exc_info=True)
        return None


def upns_by_student() -> dict[str, str]:
    """Every learner's UPN keyed by student id, for list and search views."""
    from education_system.systems.sixth_form.domain.operations.integrations import ctf
    try:
        return ctf.upns_by_student()
    except Exception:
        logger.debug("No UPN lookup", exc_info=True)
        return {}


def set_upn(student_id: str, upn: str | None, *, source: str = "manual",
            by: str | None = None) -> str | None:
    """Set, change or (with None) clear the learner's UPN."""
    _require_writer("changing a student's UPN")
    new = validate_upn(upn)
    old = get_upn(student_id)
    if new == old:
        return new
    from education_system.systems.sixth_form.domain.operations.integrations import ctf
    try:
        ctf.set_student_upn(student_id, new, source=source)
    except ValueError as e:
        raise ValidationError(str(e)) from None
    record_history(student_id, "UPN", old, new, changed_by=by)
    return new


# ── Login account provisioning ──────────────────────────────────────
#
# Each student gets a row in the shared `auth.db` so they can sign in
# through the universal login. Username == student_id, password is
# derived from the first name. We write directly via the schema-level
# hash helper (same path used by the seeded demo accounts) — going
# through `UserAuth.create_user` would fail strength validation, the
# same trade-off the seed already makes.

def _temporary_password() -> str:
    """A random temporary password (it used to be first name + "123456")."""
    from education_system.systems.sixth_form.domain.learners.students import new_learner
    return new_learner.temporary_password()


def _provision_login_account(student: Student, password: str) -> None:
    """Create a sign-in row in the shared auth DB for this student.

    Idempotent: if the username already exists we leave the row alone
    (don't reset their password) and just make sure the system mapping
    is present.
    """
    from education_system.platform.identity.auth.db import connect as _auth_connect
    from education_system.platform.identity.auth.password_manager import hash_password

    pw_hash = hash_password(password)
    display = student.full_name

    try:
        with _auth_connect() as conn:
            row = conn.execute(
                "SELECT id FROM users WHERE username = ?", (student.student_id,)
            ).fetchone()
            if row is None:
                cur = conn.execute(
                    "INSERT INTO users (username, password_hash, display_name, email) "
                    "VALUES (?, ?, ?, ?)",
                    (student.student_id, pw_hash, display, student.email),
                )
                user_id = cur.lastrowid
                logger.info(
                    "Provisioned login account for student %s (auth user_id=%d)",
                    student.student_id, user_id,
                )
            else:
                user_id = row["id"]
                logger.debug(
                    "Login account already exists for %s — leaving password intact",
                    student.student_id,
                )
            conn.execute(
                "INSERT OR IGNORE INTO user_systems (user_id, system_key, role) "
                "VALUES (?, ?, ?)",
                (user_id, AUTH_SYSTEM_KEY, AUTH_ROLE),
            )
            conn.commit()
    except Exception:
        logger.exception(
            "Failed to provision login account for student %s", student.student_id,
        )
        raise


def _deprovision_login_account(student_id: str, email: str | None = None) -> None:
    """Revoke the shared-auth login for a deleted student.

    Many tables in the shared auth DB reference ``users(id)`` without
    ``ON DELETE CASCADE``, so a plain ``DELETE FROM users`` would fail
    on FK constraints (or orphan sessions/MFA secrets). Instead we
    disable foreign keys for this one transaction and clear the rows
    we created — ``user_systems`` and the ``users`` row itself. Best
    effort: errors are logged but not re-raised so a missing shared
    DB never blocks the student delete.
    """
    from education_system.platform.identity.auth.db import connect as _auth_connect
    try:
        with _auth_connect() as conn:
            row = conn.execute(
                "SELECT id FROM users WHERE username = ? OR username = ?",
                (student_id, (email or "")),
            ).fetchone()
            if row is None:
                logger.debug(
                    "No login account to deprovision for %s", student_id)
                return
            user_id = row["id"]
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.execute("DELETE FROM user_systems WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM mfa_secrets WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM password_history WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM security_questions WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            logger.info(
                "Deprovisioned login account for student %s (auth user_id=%d)",
                student_id, user_id,
            )
    except Exception:
        logger.exception(
            "Failed to deprovision login account for %s — leaving row in place",
            student_id,
        )


# ── CRUD ────────────────────────────────────────────────────────────

class PossibleDuplicate(ValidationError):
    """The new record looks like a student who is already on file."""

    def __init__(self, matches: list["Student"]) -> None:
        self.matches = matches
        names = "; ".join(f"{m.student_id} {m.full_name} ({m.status})"
                          for m in matches[:5])
        super().__init__(f"This looks like an existing student: {names}")


def _name_key(value: str | None) -> str:
    import unicodedata
    text = unicodedata.normalize("NFKD", value or "")
    return "".join(c for c in text if c.isalnum()).casefold()


def find_possible_duplicates(*, first_name: str | None, last_name: str | None,
                             date_of_birth: str | None = None,
                             personal_email: str | None = None,
                             uln: str | None = None, upn: str | None = None,
                             exclude: str | None = None) -> list[Student]:
    """Students who are probably the same person.

    A match is the same first and last name (ignoring case, spaces and
    accents) *and* date of birth, or the same personal email, ULN or UPN.
    A name alone is not enough: two learners can share one.
    """
    init_db()
    first, last = _name_key(first_name), _name_key(last_name)
    email = (personal_email or "").strip().casefold()
    found: dict[str, Student] = {}
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM students").fetchall()
    for r in rows:
        st = _row_to_student(r)
        if st.student_id == exclude:
            continue
        same_person = (
            (date_of_birth and st.date_of_birth == date_of_birth
             and _name_key(st.first_name) == first
             and _name_key(st.last_name) == last)
            or (email and (st.personal_email or "").casefold() == email)
            or (uln and st.uln == uln))
        if same_person:
            found[st.student_id] = st
    if upn:
        try:
            from education_system.systems.sixth_form.domain.operations.integrations import ctf
            holder = ctf.student_for_upn(upn)
        except Exception:
            holder = None
        if holder and holder != exclude and holder not in found:
            st = get_student(holder)
            if st is not None:
                found[holder] = st
    return list(found.values())


def create_student(data: dict[str, Any], *, allow_duplicate: bool = False,
                   password: str | None = None) -> Student:
    """Insert a new student. Returns the persisted `Student` (with
    auto-generated `student_id` and sixth-form email).

    Raises :class:`PossibleDuplicate` when the details match a student
    already on file (see :func:`find_possible_duplicates`). Pass
    ``allow_duplicate=True`` once a person has confirmed it is someone
    else; automated intake passes it and the match is noted in the new
    record's history for staff to check. *password* is the new login's
    temporary password (random if not given; the welcome e-mail has it).
    """
    _require_writer("adding students")
    init_db()
    # PII-safe entry log: record only WHICH fields the caller supplied,
    # never the values, so the trail is useful for debugging without
    # leaking names/phone numbers into log aggregation.
    logger.debug(
        "create_student called with fields: %s",
        sorted(k for k, v in data.items() if v not in (None, "")))
    try:
        payload = _validate_payload(data)
        upn = validate_upn(data.get("upn"))
    except ValidationError as e:
        logger.warning("create_student validation failed: %s", e)
        raise
    payload["start_date"] = payload["start_date"] or _dt.date.today().isoformat()
    payload["leaving_date"] = payload["leaving_reason"] = None
    matches = find_possible_duplicates(
        first_name=payload["first_name"], last_name=payload["last_name"],
        date_of_birth=payload["date_of_birth"],
        personal_email=payload["personal_email"], upn=upn,
        uln=(str(data.get("uln") or "").strip() or None))
    if matches and not allow_duplicate:
        logger.warning("create_student refused: %d possible duplicate(s)",
                       len(matches))
        raise PossibleDuplicate(matches)
    sid = generate_student_id()
    email = generate_sixthform_email(sid)
    try:
        with _connect() as conn:
            columns = (
                "student_id", "first_name", "middle_name", "last_name",
                "title", "gender", "date_of_birth", "phone", "email",
                "emergency_contact_name", "emergency_contact_phone",
                "emergency_contact_relation",
                "subject_1", "subject_2", "subject_3",
                "status", "personal_email",
                *(c for c, _l in _PROFILE_FIELDS),
            )
            values = {**payload, "student_id": sid, "email": email}
            conn.execute(
                f"INSERT INTO students ({', '.join(columns)}) "
                f"VALUES ({', '.join('?' for _c in columns)})",
                tuple(values[c] for c in columns),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        logger.exception(
            "INSERT failed for new student id=%s (likely a duplicate "
            "student_id or email collision)", sid)
        raise
    student = get_student(sid)
    assert student is not None
    record_history(sid, "record", note="Record created")
    if matches:
        record_history(
            sid, "record", changed_by=None,
            note="Possible duplicate of " + ", ".join(
                m.student_id for m in matches) + " - check and merge if so")
    if upn:
        try:
            set_upn(sid, upn, source="record")
        except ValidationError as e:
            logger.warning("UPN for new student %s not stored: %s", sid, e)
    logger.info(
        "Created student %s (%s, email=%s, subjects=%s)",
        student.student_id, student.full_name, student.email, student.subjects,
    )
    _sync_learning_aims(student.student_id, previous_subjects=[])
    password = password or _temporary_password()
    _provision_login_account(student, password)
    _send_welcome_email(student, password)
    # Anchor a canonical journey_id so this student links to the same
    # person in the secondary/university systems (best-effort; matched on
    # name + DOB).
    try:
        from education_system.platform.cross_system import person, progression
        jid = progression.register_local_student(
            "sixth_form", student_id=student.student_id,
            first_name=student.first_name, last_name=student.last_name,
            date_of_birth=student.date_of_birth)
        if jid:
            person.link_local_record("sixth_form", student.student_id, jid)
    except Exception:
        logger.debug("Journey registration skipped for student %s",
                     student.student_id, exc_info=True)
    # After registration, so the journey exists: link the student's own
    # login (username = student id) to it. Best-effort, never raises.
    from education_system.platform.cross_system import login_links
    login_links.try_sync_username(student.student_id)
    return student


def _send_welcome_email(student: Student, password: str) -> None:
    """Drop a welcome email into the student's inbox.

    Best-effort: any failure is logged but never blocks student
    creation — the record is more important than the welcome message.
    """
    try:
        from education_system.systems.sixth_form import SYSTEM_NAME
        from education_system.systems.sixth_form.domains.communications.domain.messages import (
            email_templates,
        )
        subjects = list(student.subjects) + ["", "", ""]
        msg = email_templates.send_from_template(
            "welcome_student",
            {
                "system_name": SYSTEM_NAME,
                "student_id":  student.student_id,
                "first_name":  student.first_name,
                "last_name":   student.last_name,
                "full_name":   student.full_name,
                "email":       student.email,
                "password":    password,
                "subject_1":   subjects[0],
                "subject_2":   subjects[1],
                "subject_3":   subjects[2],
            },
            # The personal address when held: the college inbox can't be
            # opened without the password this message carries.
            to_name=student.full_name,
            to_address=student.personal_email or student.email,
            student_id=student.student_id,
        )
        logger.info(
            "Welcome email delivered to student %s (message #%d, to=%s)",
            student.student_id, msg.message_id, student.email)
    except Exception:
        logger.exception(
            "Welcome email could not be sent to %s — student record was "
            "still created", student.student_id)


def get_student(student_id: str) -> Student | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
    if row is None:
        logger.debug("get_student(%s) -> miss", student_id)
        return None
    return _row_to_student(row)


def list_students() -> list[Student]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM students ORDER BY last_name, first_name"
        ).fetchall()
    logger.debug("list_students -> %d row(s)", len(rows))
    return [_row_to_student(r) for r in rows]


def list_year_13_students() -> list[Student]:
    """Return sixth-form students whose latest enrolment is Year 13 and
    still active (status='Enrolled').

    Joins the ``students`` table to the ``enrolments`` table on
    ``student_id`` and filters to ``year_group=13``. If a student has
    multiple Year 13 rows across academic years we take the most
    recent. Used by the university-system import flow to surface
    leavers ready to be admitted onto a course.
    """
    init_db()
    # Ensure enrolments schema exists so the JOIN doesn't fail when
    # this is called before the enrolments module has been touched
    # this process.
    try:
        from education_system.systems.sixth_form.domain.admissions.enrolments import (
            enrolments as _enrolments,
        )
        _enrolments.init_db()
        year = _enrolments.current_academic_year()
        first = int(year[:4]) - 1
        years = (year, f"{first}/{str(first + 1)[-2:]}")
    except Exception:
        logger.exception(
            "list_year_13_students: could not init enrolments schema")
        return []
    # A live (not archived) Year 13 row of this academic year — or of the
    # one just ended, for an import over the summer before rollover — and
    # no later non-archived year for the learner.
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT s.*
              FROM students AS s
             WHERE s.status = 'Active'
               AND s.student_id IN (
                       SELECT e.student_id
                         FROM enrolments AS e
                        WHERE e.year_group = 13
                          AND e.status = 'Enrolled'
                          AND e.archived_at IS NULL
                          AND e.academic_year IN (?, ?)
                          AND NOT EXISTS (
                              SELECT 1 FROM enrolments AS l
                               WHERE l.student_id = e.student_id
                                 AND l.archived_at IS NULL
                                 AND l.academic_year > e.academic_year)
                   )
             ORDER BY s.last_name, s.first_name
            """, years,
        ).fetchall()
    logger.debug("list_year_13_students -> %d row(s)", len(rows))
    return [_row_to_student(r) for r in rows]


def search_students(query: str) -> list[Student]:
    """Match against student_id, names (preferred name too), either email,
    phone, ULN, UCI, candidate number, UPN, postcode or previous school.
    "Jane Smith" matches on first + last name too."""
    init_db()
    raw = (query or "").strip()
    if not raw:
        logger.debug("search_students called with empty query")
    q = f"%{raw}%"
    # Phone numbers are stored as typed ("07700 900123"), so compare with
    # the spaces taken out of both sides.
    digits = f"%{raw.replace(' ', '')}%"
    _ensure_upn_store()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM students
            WHERE student_id LIKE ?
               OR first_name LIKE ?
               OR middle_name LIKE ?
               OR last_name LIKE ?
               OR (first_name || ' ' || last_name) LIKE ?
               OR email LIKE ?
               OR personal_email LIKE ?
               OR REPLACE(phone, ' ', '') LIKE ?
               OR uln LIKE ?
               OR uci LIKE ?
               OR candidate_number LIKE ?
               OR preferred_name LIKE ?
               OR (preferred_name || ' ' || last_name) LIKE ?
               OR REPLACE(postcode, ' ', '') LIKE ?
               OR previous_school LIKE ?
               OR student_id IN (SELECT student_id FROM ctf_upn_links
                                 WHERE upn LIKE ?)
            ORDER BY last_name, first_name
            """,
            (q, q, q, q, q, q, q, digits, q, q, q, q, q, digits, q, q),
        ).fetchall()
    logger.debug(
        "search_students(query_len=%d) -> %d match(es)", len(raw), len(rows))
    return [_row_to_student(r) for r in rows]


#: The columns a record edit writes: everything the form and the
#: profile hold. ID, college email, status side effects, identifiers and
#: the transfer marker have their own functions.
_EDITABLE_COLUMNS: tuple[str, ...] = (
    "first_name", "middle_name", "last_name", "title", "gender",
    "date_of_birth", "phone",
    "emergency_contact_name", "emergency_contact_phone",
    "emergency_contact_relation",
    "subject_1", "subject_2", "subject_3",
    "status", "personal_email",
    *(c for c, _l in _PROFILE_FIELDS),
)


def _payload_of(student: Student) -> dict[str, Any]:
    return {c: getattr(student, c, None) for c in _EDITABLE_COLUMNS}


def update_student(student_id: str, data: dict[str, Any]) -> Student:
    """Update editable fields. ID and sixth-form email are immutable.

    A key left out of *data* keeps its current value, so a caller that
    only knows some fields (CTF import, bulk edits, the cross-system
    adapter) cannot blank the rest; pass ``""`` to clear one. ``"upn"``
    in *data* is stored through :func:`set_upn`.
    """
    _require_writer("changing student records")
    init_db()
    logger.debug(
        "update_student(%s) called with fields: %s",
        student_id,
        sorted(k for k, v in data.items() if v not in (None, "")))
    before = get_student(student_id)
    if before is not None:
        # The edit form has no status field (status changes have side
        # effects and go through set_status / withdraw_student), so the
        # current status is kept rather than the validator's "Active"
        # default quietly putting a departed learner back on roll.
        # Whichever form of the address the caller sent wins: lines rebuild
        # ``address``, a plain ``address`` (CTF, bulk) is split into lines.
        stale = (("address",) if any(k in data for k in ADDRESS_LINE_FIELDS)
                 else ADDRESS_LINE_FIELDS if "address" in data else ())
        data = {**{k: v for k, v in _payload_of(before).items() if k not in stale},
                **{k: v for k, v in data.items()
                   if not (k == "status" and not (v or "").strip())}}
    try:
        payload = _validate_payload(data)
        upn_given = "upn" in data
        upn = validate_upn(data.get("upn")) if upn_given else None
    except ValidationError as e:
        logger.warning("update_student(%s) validation failed: %s", student_id, e)
        raise
    if before is None:
        logger.warning(
            "update_student(%s): no existing row — UPDATE will be a no-op "
            "and will raise", student_id)
    if upn_given and upn:
        holder = find_possible_duplicates(first_name=None, last_name=None,
                                          upn=upn, exclude=student_id)
        if holder:
            raise ValidationError(
                f"UPN {upn} already belongs to {holder[0].student_id} "
                f"{holder[0].full_name}")
    with _connect() as conn:
        cur = conn.execute(
            f"UPDATE students SET {', '.join(f'{c} = ?' for c in _EDITABLE_COLUMNS)} "
            "WHERE student_id = ?",
            (*(payload[c] for c in _EDITABLE_COLUMNS), student_id),
        )
        if cur.rowcount == 0:
            logger.warning("update_student called for unknown id %s", student_id)
            raise ValidationError(f"No student with id {student_id}")
        conn.commit()
    if upn_given:
        set_upn(student_id, upn)
    _sync_learning_aims(
        student_id,
        previous_subjects=(before.subjects if before is not None else []))
    student = get_student(student_id)
    assert student is not None
    if before is not None:
        for attr, label in _HISTORY_FIELDS:
            old_v, new_v = getattr(before, attr, None), getattr(student, attr, None)
            if (old_v or "") != (new_v or ""):
                record_history(student_id, label, old_v, new_v)
        changes = _diff_student(before, student)
        if changes:
            # Field names only (no values) — audit-friendly but PII-safe.
            logger.info(
                "Updated student %s — changed fields: %s",
                student_id, ", ".join(label for label, _o, _n in changes))
            _send_update_email(before, student, changes=changes)
        else:
            logger.info(
                "Updated student %s — no tracked fields changed",
                student_id)
    else:
        logger.info("Updated student %s", student_id)
    return student


def _sync_learning_aims(student_id: str, *, previous_subjects: list[str]) -> None:
    """Turn the form's subject slots into learning aims (and back).

    Best-effort like the other post-save steps: the record itself has
    been saved, and a failure here is logged loudly rather than undoing
    it. See ``learning_aims.on_student_saved`` for the rules.
    """
    try:
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            learning_aims,
        )
        learning_aims.on_student_saved(
            student_id, previous_subjects=previous_subjects)
    except Exception:
        logger.exception(
            "Could not reconcile learning aims for %s with the subject "
            "slots just saved", student_id)


def set_identifiers(student_id: str, *, uln: str | None = None,
                    uci: str | None = None,
                    candidate_number: str | None = None) -> Student:
    """Set (or clear, with "") the ULN, UCI and candidate number.

    ``None`` leaves a field unchanged. A ULN is held to the LRS check
    digit; a UCI to the JCQ format only (see qualifications.identifiers).
    Two learners may not share a ULN or a UCI.
    """
    _require_writer("changing a student's identifiers")
    init_db()
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        identifiers,
    )
    existing = get_student(student_id)
    if existing is None:
        raise ValidationError(f"No student with id {student_id}")
    values = {
        "uln": existing.uln, "uci": existing.uci,
        "candidate_number": existing.candidate_number,
    }
    try:
        if uln is not None:
            values["uln"] = identifiers.validate_uln(uln)
        if uci is not None:
            values["uci"] = identifiers.validate_uci(uci)
        if candidate_number is not None:
            values["candidate_number"] = identifiers.validate_candidate_number(
                candidate_number)
    except ValueError as e:
        raise ValidationError(str(e)) from None
    with _connect() as conn:
        for col in ("uln", "uci"):
            if values[col]:
                clash = conn.execute(
                    f"SELECT student_id FROM students WHERE {col} = ? "
                    "AND student_id != ?", (values[col], student_id)).fetchone()
                if clash:
                    raise ValidationError(
                        f"{col.upper()} {values[col]} already belongs to "
                        f"{clash['student_id']}")
        conn.execute(
            "UPDATE students SET uln = ?, uci = ?, candidate_number = ? "
            "WHERE student_id = ?",
            (values["uln"], values["uci"], values["candidate_number"],
             student_id))
        conn.commit()
    logger.info("Updated identifiers for %s (fields: %s)", student_id,
                ", ".join(k for k, v in (("uln", uln), ("uci", uci),
                                         ("candidate_number", candidate_number))
                          if v is not None) or "none")
    out = get_student(student_id)
    assert out is not None
    return out


def find_by_uln(uln: str) -> Student | None:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM students WHERE uln = ?",
                           ((uln or "").strip(),)).fetchone()
    return _row_to_student(row) if row else None


_TRACKED_UPDATE_FIELDS: tuple[tuple[str, str], ...] = (
    ("first_name",                 "First name"),
    ("middle_name",                "Middle name"),
    ("last_name",                  "Last name"),
    ("phone",                      "Phone"),
    ("emergency_contact_name",     "Emergency contact name"),
    ("emergency_contact_phone",    "Emergency contact phone"),
    ("emergency_contact_relation", "Emergency contact relation"),
    ("subject_1",                  "A-Level subject 1"),
    ("subject_2",                  "A-Level subject 2"),
    ("subject_3",                  "A-Level subject 3"),
)


# Everything the record history keeps — the update e-mail above is a
# narrower list on purpose, so a learner is not mailed their own date of
# birth every time somebody corrects it.
_HISTORY_FIELDS: tuple[tuple[str, str], ...] = (
    ("title",                      "Title"),
    *_TRACKED_UPDATE_FIELDS[:3],
    ("gender",                     "Gender"),
    ("date_of_birth",              "Date of birth"),
    *_TRACKED_UPDATE_FIELDS[3:],
    ("personal_email",             "Personal email"),
    ("status",                     "Status"),
    *_PROFILE_FIELDS,
)


def _diff_student(before: Student, after: Student) -> list[tuple[str, str, str]]:
    """Return [(label, old, new), ...] for fields that actually changed."""
    out: list[tuple[str, str, str]] = []
    for attr, label in _TRACKED_UPDATE_FIELDS:
        old_v = getattr(before, attr, None)
        new_v = getattr(after, attr, None)
        if (old_v or "") != (new_v or ""):
            out.append((label, str(old_v) if old_v else "(empty)",
                                str(new_v) if new_v else "(empty)"))
    return out


def _send_update_email(before: Student, after: Student, *,
                       changes: list[tuple[str, str, str]] | None = None) -> None:
    """Email the student a summary of what changed in their record.

    No-op if nothing tracked actually changed. Best-effort: failure
    never blocks the update itself.
    """
    if changes is None:
        changes = _diff_student(before, after)
    if not changes:
        logger.debug(
            "Update email skipped for %s — diff is empty",
            after.student_id)
        return
    try:
        import datetime as _dt
        from education_system.systems.sixth_form import SYSTEM_NAME
        from education_system.systems.sixth_form.domains.communications.domain.messages import (
            email_templates,
        )
        change_lines = "\n".join(
            f"  • {label}:\n      was: {old}\n      now: {new}"
            for label, old, new in changes
        )
        msg = email_templates.send_from_template(
            "student_record_updated",
            {
                "system_name": SYSTEM_NAME,
                "student_id":  after.student_id,
                "first_name":  after.first_name,
                "full_name":   after.full_name,
                "updated_at":  _dt.datetime.now().strftime(
                    "%Y-%m-%d %H:%M"),
                "changes":     change_lines,
            },
            to_name=after.full_name,
            to_address=after.email,
            student_id=after.student_id,
        )
        logger.info(
            "Update email delivered to student %s (message #%d, %d "
            "change(s))",
            after.student_id, msg.message_id, len(changes))
    except Exception:
        logger.exception(
            "Update email could not be sent to %s — the record update "
            "itself succeeded", after.student_id)


# Where transfer notifications land. Override at runtime via the
# ``EDU_SIXTHFORM_ADMIN_EMAIL`` environment variable if your school
# routes admin mail somewhere other than the default.
SIXTHFORM_ADMIN_EMAIL_DEFAULT = "admin@sixthform.ac.uk"


def _sixthform_admin_email() -> str:
    return os.environ.get(
        "EDU_SIXTHFORM_ADMIN_EMAIL",
        SIXTHFORM_ADMIN_EMAIL_DEFAULT,
    ).strip() or SIXTHFORM_ADMIN_EMAIL_DEFAULT



def disable_leaver_login(student_id: str) -> bool:
    """Disable a leaver's login — but only once it holds nothing.

    Public because it has two callers with different timing:
    :func:`mark_transferred` when the learner is handed over, and the
    university when it confirms their place — which comes first, and is
    the point the platform now treats as the end of their sixth form.

    :func:`_revoke_sixth_form_access` above deliberately stopped doing
    this, and the reason is still good: shared auth means the row behind
    a student id is a *person*, who may also hold a parent-portal role, a
    part-time staff grant or superadmin. Blanket-disabling took all of
    that with it, and put their MFA enrolment and recovery codes out of
    reach.

    So the account is disabled only when the sixth form was the last
    thing on it. A leaver with no memberships can otherwise still sign in
    and reach nothing, which is a live credential for somebody who has
    gone — and that is what this closes.

    The university does not reuse this login: its import provisions a
    fresh one under the university student id, so disabling here cannot
    lock a learner out of the system they just moved to.

    Best-effort: logged, never raised, so the transfer continues.
    """
    from education_system.platform.identity.auth.db import connect as _auth_connect
    from education_system.platform.identity.auth.role_manager import RoleManager
    try:
        with _auth_connect() as conn:
            row = conn.execute(
                "SELECT id, is_active FROM users WHERE username = ?",
                (student_id,)).fetchone()
            if row is None:
                logger.warning(
                    "Disable leaver account: no auth account for %s",
                    student_id)
                return False
            user_id = int(row["id"])

        remaining = [s["system_key"] for s in RoleManager().get_user_systems(user_id)]
        if remaining:
            # Somebody who is more than this learner. Leave them alone.
            logger.info(
                "Leaver account %s (user_id=%s) kept active — still holds %s",
                student_id, user_id, ", ".join(remaining))
            return False

        with _auth_connect() as conn:
            conn.execute("UPDATE users SET is_active = 0, "
                         "updated_at = datetime('now') WHERE id = ?",
                         (user_id,))
            conn.execute("UPDATE sessions SET is_active = 0 WHERE user_id = ?",
                         (user_id,))
            conn.commit()
        logger.info(
            "Disabled leaver account %s (user_id=%s) — no memberships left",
            student_id, user_id)
        return True
    except Exception:
        logger.exception(
            "Could not disable the leaver account for %s "
            "(the transfer itself is unaffected)", student_id)
        return False



def _siblings_still_needing_access(conn) -> str:
    """SQL counting the *other* learners keeping a parent account open.

    Bound to ``(account_id, student_id)``. A sibling counts as still
    needing the portal unless they have left — or hold a confirmed UCAS
    place, which is the point this system now treats as the end of their
    sixth form. Without that second clause two siblings confirmed in the
    same cycle would hold each other's parent account open forever: each
    is excluded from their own call and ``Active`` in the other's.

    Falls back to the status test alone on a database with no UCAS
    tables, where the question cannot be asked.
    """
    has_ucas = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
        "AND name='ucas_applications'").fetchone()[0]
    base = """SELECT COUNT(*) FROM parent_student_links AS l
                JOIN students AS s ON s.student_id = l.student_id
               WHERE l.account_id = ? AND l.student_id != ?
                 AND s.status != 'Left'"""
    if not has_ucas:
        return base
    return base + """
                 AND NOT EXISTS (SELECT 1 FROM ucas_applications AS a
                                  WHERE a.student_id = l.student_id
                                    AND a.status IN ('Confirmed'))"""


def disable_orphaned_parent_logins(student_id: str) -> list[str]:
    """Disable parent logins that exist only for this learner.

    A parent account is parent-portal-local — its own username, password
    and ``is_active`` — and links to learners through
    ``parent_student_links``. Crucially the link is many-to-many: one
    account commonly covers siblings.

    So an account is disabled only when *every* learner it can see has
    gone. Disabling on the first child to leave would cut a parent off
    from a sibling still on roll, which is a worse failure than leaving a
    login open a little too long.

    The learner this is called for is excluded from that count rather
    than assumed to be ``Left``. It runs at two moments now — when the
    university confirms a place, where they are still very much on roll,
    and again at handover — and keying on their own status would have
    meant the confirmation call could never close anything.

    Returns the usernames disabled. Best-effort; never raises.
    """
    disabled: list[str] = []
    try:
        with _connect() as conn:
            # Queried directly rather than through ``parent_portal``,
            # whose ``init_db`` cannot run against a database whose
            # ``parent_student_links`` predates its ``contact_id``
            # column — which is the shape actually in the field. Calling
            # it here would take this whole review down with it.
            have = {r["name"] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND "
                "name IN ('parent_accounts','parent_student_links')")}
            if len(have) < 2:
                logger.info(
                    "No parent-portal tables on this database — nothing to "
                    "review for %s", student_id)
                return disabled
            accounts = conn.execute(
                "SELECT DISTINCT account_id FROM parent_student_links "
                "WHERE student_id = ?", (student_id,)).fetchall()
            for row in accounts:
                account_id = row["account_id"]
                still_active = conn.execute(
                    _siblings_still_needing_access(conn),
                    (account_id, student_id)).fetchone()[0]
                if still_active:
                    logger.info(
                        "Parent account #%s kept active — %d other learner(s) "
                        "still on roll", account_id, still_active)
                    continue
                cur = conn.execute(
                    "UPDATE parent_accounts SET is_active = 0 "
                    "WHERE account_id = ? AND is_active = 1", (account_id,))
                if cur.rowcount:
                    name = conn.execute(
                        "SELECT username FROM parent_accounts WHERE account_id = ?",
                        (account_id,)).fetchone()
                    disabled.append(name["username"] if name else str(account_id))
            conn.commit()
        if disabled:
            logger.info(
                "Disabled %d parent account(s) after %s left: %s",
                len(disabled), student_id, ", ".join(disabled))
        return disabled
    except Exception:
        logger.exception(
            "Could not review parent accounts for %s "
            "(the transfer itself is unaffected)", student_id)
        return disabled



def _close_sixth_form_enrolment(student_id: str,
                                moved_by: str | None, *,
                                status: str = "transferred",
                                reason: str | None = None) -> bool:
    """Close the learner's cross-system sixth-form enrolment.

    The progression board's Submit button tells the user "this closes
    their sixth-form enrolment", and ``university_progression.submit``
    says the same in its docstring — but nothing did it. The
    ``learner_enrolment`` row stayed ``active`` with no end date, so a
    learner who had left the college was still, to every cross-system
    reader, enrolled at it.

    Closed as ``transferred`` rather than ``completed``: they are leaving
    mid-phase for somewhere else, which is exactly the distinction that
    status exists to draw.

    Best-effort, like every other step after the status flip — a learner
    who has gone must not be held back by a bookkeeping row.
    """
    try:
        from education_system.platform.cross_system import (
            enrolments as _enrolments,
            identity_service as _identity,
        )
        journey = _identity.find_by_student("sixth_form", student_id)
        if not journey:
            logger.info(
                "No cross-system journey for %s — no enrolment to close",
                student_id)
            return False
        journey_id = journey.get("journey_id")
        current = _enrolments.current_enrolment(journey_id, "sixth_form")
        if current is None:
            logger.info(
                "No open sixth-form enrolment on journey %s to close",
                journey_id)
            return False
        _enrolments.close_enrolment(
            current["enrolment_id"], status=status,
            reason=(reason or "Transferred out of the sixth form")
                   + (f" by {moved_by}" if moved_by else ""))
        logger.info(
            "Closed sixth-form enrolment %s for %s as %s",
            current["enrolment_id"], student_id, status)
        return True
    except Exception:
        logger.exception(
            "Could not close the sixth-form enrolment for %s "
            "(the transfer itself is unaffected)", student_id)
        return False


def _revoke_sixth_form_access(student_id: str) -> bool:
    """End the learner's sixth-form membership, leaving the person intact.

    Authentication is shared across every system, so the account behind a
    sixth-form student id is a *person*, not a sixth-form login. It may
    also carry a parent-portal role, a part-time staff grant, or
    superadmin. This used to run ``UPDATE users SET is_active = 0``, which
    disabled all of that — the person could no longer sign in anywhere,
    and their MFA enrolment, recovery codes and password history went out
    of reach with them.

    What actually ends at a transfer is one membership: the
    ``user_systems`` row for ``sixth_form``. Credentials, MFA secret,
    recovery codes and security questions are deliberately untouched, so a
    learner moving up a phase keeps the identity they already have rather
    than needing a new one.

    Live sessions are still revoked. A session issued before the change
    carries the old membership set, so it has to be re-minted — but that
    is a re-login, not a lockout: the same password and the same second
    factor still work.

    Note that revoking the last membership does not itself block sign-in;
    the shared login returns an empty systems list rather than refusing.
    A leaver with nothing left can authenticate and reach nothing, which
    is the intended "no access" state and is what lets the university
    grant them access later without reviving a disabled account.

    Returns True if a sixth-form membership was removed. Best-effort:
    errors are logged, never raised, so the transfer continues.
    """
    from education_system.platform.identity.auth.db import connect as _auth_connect
    from education_system.platform.identity.auth.role_manager import RoleManager
    from education_system.platform.kernel.core.system_keys import canonical_system_key
    try:
        with _auth_connect() as conn:
            row = conn.execute(
                "SELECT id FROM users WHERE username = ?", (student_id,)
            ).fetchone()
        if row is None:
            logger.warning(
                "Revoke sixth-form access: no auth account for %s", student_id)
            return False
        user_id = int(row["id"])

        system_key = canonical_system_key("sixth_form")
        roles = RoleManager()
        had_access = roles.get_user_role_for_system(user_id, system_key) is not None
        roles.revoke_system_access(user_id, system_key)

        # Re-mint sessions against the new membership set.
        with _auth_connect() as conn:
            conn.execute(
                "UPDATE sessions SET is_active = 0 WHERE user_id = ?",
                (user_id,),
            )
            conn.commit()

        remaining = [s["system_key"] for s in roles.get_user_systems(user_id)]
        logger.info(
            "Revoked sixth-form access for %s (user_id=%s); account remains "
            "active with %s", student_id, user_id,
            ", ".join(remaining) if remaining
            else "no remaining system access")
        return had_access
    except Exception:
        logger.exception(
            "Failed to revoke sixth-form access for %s", student_id)
        return False


# ── Record history ──────────────────────────────────────────────────

def _actor() -> str | None:
    """The signed-in username, for the history's "changed by" column."""
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        return access.current().username or None
    except Exception:
        return None


def record_history(student_id: str, field: str, old_value: Any = None,
                   new_value: Any = None, *, changed_by: str | None = None,
                   note: str | None = None) -> None:
    """Append one line to a student's record history. Never raises: a
    history failure is logged loudly but must not undo the change it
    describes."""
    try:
        init_db()
        with _connect() as conn:
            conn.execute(
                "INSERT INTO student_record_history "
                "(student_id, changed_by, field, old_value, new_value, note) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (student_id, changed_by or _actor(), field,
                 None if old_value in (None, "") else str(old_value),
                 None if new_value in (None, "") else str(new_value),
                 note))
            conn.commit()
    except sqlite3.Error:
        logger.exception("Could not record history for %s (%s)",
                         student_id, field)


def list_history(student_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
    """Newest first: ``history_id``, ``at``, ``changed_by``, ``field``,
    ``old_value``, ``new_value``, ``note``."""
    init_db()
    with _connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT history_id, at, changed_by, field, old_value, new_value, note "
            "FROM student_record_history WHERE student_id = ? "
            "ORDER BY history_id DESC LIMIT ?", (student_id, int(limit)))]


#: History labels a person can put back, and the column each one is.
_REVERTIBLE: dict[str, str] = {
    label: attr for attr, label in _HISTORY_FIELDS
    if attr not in ("status", "leaving_date", "leaving_reason")}


def can_revert(entry: dict[str, Any]) -> bool:
    """Whether a history line is a field edit :func:`revert_history` undoes."""
    return entry.get("field") in _REVERTIBLE or entry.get("field") in ("Status", "UPN")


def revert_history(history_id: int, *, by: str | None = None) -> Student:
    """Put one field back to the value it had before a recorded change.

    The revert is itself an edit — validated, written through the normal
    path and recorded in the history — so it can be reverted in turn. A
    status change goes back through :func:`set_status` (with its side
    effects); the UPN through :func:`set_upn`.
    """
    _require_writer("reverting student record changes")
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM student_record_history WHERE history_id = ?",
            (int(history_id),)).fetchone()
    if row is None:
        raise ValidationError(f"No history entry {history_id}")
    student = get_student(row["student_id"])
    if student is None:
        raise ValidationError(f"No student with id {row['student_id']}")
    field, old = row["field"], row["old_value"]
    note = f"Reverted change of {row['at']}"
    if field == "Status":
        if not old:
            raise ValidationError("That status change has no earlier value")
        return set_status(student.student_id, old, reason=note, by=by)
    if field == "UPN":
        set_upn(student.student_id, old, by=by)
        out = get_student(student.student_id)
        assert out is not None
        return out
    attr = _REVERTIBLE.get(field)
    if attr is None:
        raise ValidationError(f"{field} changes cannot be reverted here")
    current = getattr(student, attr, None)
    if (current or "") != (row["new_value"] or ""):
        raise ValidationError(
            f"{field} has been changed again since; revert the later change "
            "first or edit the record")
    return update_student(student.student_id, {attr: old or ""})


# ── Linked records ──────────────────────────────────────────────────
#
# Every feature's tables live in the same sixthform.db as ``students``,
# and most of them reference it ``ON DELETE CASCADE``. Deleting a student
# row therefore deletes their safeguarding concerns, medical records,
# attendance, exam entries and the rest with it — 60-odd tables. The
# few that hold ``student_id`` without a foreign key are orphaned
# instead. Either way the history is gone, so a delete is only safe for a
# record with nothing attached: one entered by mistake.

#: Tables that describe the student record rather than belong to it,
#: plus the learning aims, which are the record's own subject slots (every
#: new student gets them from the form) and go with it, and the UPN link,
#: which is where the record's own UPN is held.
_NOT_LINKED_RECORDS: frozenset[str] = frozenset({
    "students", "student_record_history", "system_logs",
    "sensitive_access_log", "search_history", "search_audit",
    "learning_aims", "learning_aim_changes", "ctf_upn_links",
})


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def linked_record_counts(student_id: str) -> dict[str, int]:
    """``{table: rows}`` for every table whose rows a delete would lose.

    Found by reading the schema, so a feature added later is covered
    without being listed here: every table that references ``students``
    with a cascading (or restricting) foreign key, and every table with
    a ``student_id`` column and no foreign key, whose rows a delete would
    orphan. A ``SET NULL`` reference (messages, receipts) survives the
    delete with the link cleared, so it does not count.
    """
    init_db()
    out: dict[str, int] = {}
    with _connect() as conn:
        targets: dict[str, set[str]] = {}
        survives: set[tuple[str, str]] = set()
        for t, col, on_delete in conn.execute(
                "SELECT m.name, f.\"from\", f.on_delete FROM sqlite_master m "
                "JOIN pragma_foreign_key_list(m.name) f "
                "WHERE m.type = 'table' AND f.\"table\" = 'students'"):
            if str(on_delete).upper() in ("SET NULL", "SET DEFAULT"):
                survives.add((t, col))
            else:
                targets.setdefault(t, set()).add(col)
        for (t,) in conn.execute(
                "SELECT m.name FROM sqlite_master m "
                "JOIN pragma_table_info(m.name) c "
                "WHERE m.type = 'table' AND c.name = 'student_id'"):
            if (t, "student_id") not in survives:
                targets.setdefault(t, set()).add("student_id")
        for table, cols in sorted(targets.items()):
            if table in _NOT_LINKED_RECORDS or table.startswith("sqlite_"):
                continue
            where = " OR ".join(f"{_quote_ident(c)} = ?" for c in sorted(cols))
            try:
                # db-audit: ignore[DBW001] - table and column names come from sqlite_master/pragma and are quoted
                n = conn.execute(
                    f"SELECT COUNT(*) FROM {_quote_ident(table)} WHERE {where}",
                    (student_id,) * len(cols)).fetchone()[0]
            except sqlite3.Error:
                logger.exception("Could not count %s rows for %s",
                                 table, student_id)
                continue
            if n:
                out[table] = int(n)
    return out


def describe_linked_records(counts: dict[str, int]) -> list[str]:
    """``["Attendance records: 140", ...]`` for a confirmation message."""
    return [f"{t.replace('_', ' ').capitalize()}: {n}"
            for t, n in sorted(counts.items(), key=lambda kv: -kv[1])]


class StudentHasRecords(ValidationError):
    """Refused: deleting this student would destroy their records."""

    def __init__(self, student_id: str, counts: dict[str, int]):
        self.student_id = student_id
        self.counts = counts
        super().__init__(
            f"{student_id} has {sum(counts.values())} linked record(s) in "
            f"{len(counts)} area(s). Deleting the student would delete them "
            f"too — mark the student as left instead.")


# ── Status changes ──────────────────────────────────────────────────

def _set_leaving(student: Student, when: str | None, reason: str | None,
                 by: str | None) -> None:
    """Write (or with None, clear) the record's leaving date and reason."""
    with _connect() as conn:
        conn.execute("UPDATE students SET leaving_date = ?, leaving_reason = ? "
                     "WHERE student_id = ?", (when, reason, student.student_id))
        conn.commit()
    for label, old, new in (("Leaving date", student.leaving_date, when),
                            ("Leaving reason", student.leaving_reason, reason)):
        if (old or "") != (new or ""):
            record_history(student.student_id, label, old, new, changed_by=by)


def _set_status_row(student_id: str, status: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE students SET status = ? WHERE student_id = ?",
                     (status, student_id))
        conn.commit()


def set_status(student_id: str, status: str, *, reason: str | None = None,
               by: str | None = None) -> Student:
    """Change a student's record status.

    ``Left`` goes through :func:`withdraw_student`, which needs a reason,
    and moving a ``Left`` student back on roll goes through
    :func:`reinstate_student`: both have side effects (enrolment, login,
    tutor group) that a bare status flip would skip.
    """
    _require_writer("changing a student's status", lifecycle=True)
    init_db()
    status = (status or "").strip()
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of: {', '.join(STATUSES)}")
    student = get_student(student_id)
    if student is None:
        raise ValidationError(f"No student with id {student_id}")
    if status == student.status:
        return student
    if status == "Left":
        return withdraw_student(student_id, reason=reason or "", by=by)
    if student.status == "Left":
        return reinstate_student(student_id, status=status, reason=reason, by=by)
    _set_status_row(student_id, status)
    record_history(student_id, "Status", student.status, status,
                   changed_by=by, note=reason)
    logger.info("Student %s status %s -> %s", student_id, student.status, status)
    out = get_student(student_id)
    assert out is not None
    return out


def withdraw_student(student_id: str, *, reason: str,
                     leaving_date: str | None = None,
                     by: str | None = None,
                     withdrawal_reason: str | None = None,
                     withdrawal_detail: str | None = None) -> Student:
    """Mark a student as having left without transferring onward.

    The withdrawal counterpart of :func:`mark_transferred`, and what the
    directory's Delete now offers instead of destroying the record:

      1. ``status`` → ``Left`` (with the reason in the record history);
      2. open local enrolments close through
         ``enrolments.leaving.learner_left`` — withdrawn with the ILR
         ``withdrawal_reason`` (default 98, not known) so their learning
         aims end on the leaving date, or completed for a Year 13 leaving
         in the summer term — plus class groups, exam entries, bursary;
      3. leaves the tutor group (the group is kept in the history, so a
         reinstatement can put them back);
      4. the cross-system sixth-form enrolment closes as ``withdrawn``;
      5. the sixth-form login membership ends, the account is disabled if
         nothing else is on it, and parent logins kept only for this
         learner close with it.

    Every record — attendance, behaviour, safeguarding, exams — stays.
    Steps 2–5 are best-effort and logged, like mark_transferred's.
    """
    _require_writer("withdrawing students", lifecycle=True)
    init_db()
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("A reason for leaving is required")
    if leaving_date:
        try:
            _dt.date.fromisoformat(leaving_date)
        except ValueError:
            raise ValidationError("Leaving date must be YYYY-MM-DD") from None
    student = get_student(student_id)
    if student is None:
        raise ValidationError(f"No student with id {student_id}")
    by = by or _actor()
    when = leaving_date or _dt.date.today().isoformat()
    note = f"{reason} (left {when})"

    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        leaving as _leaving,
    )
    _leaving.check_allowed()   # before anything changes
    if student.status != "Left":
        _set_status_row(student_id, "Left")
        record_history(student_id, "Status", student.status, "Left",
                       changed_by=by, note=note)
    _set_leaving(student, when, reason, by)
    logger.info("Withdrew student %s (%s): %s", student_id,
                student.full_name, reason)

    closed = _leaving.learner_left(student_id, leaving_date=when,
                                   reason_code=withdrawal_reason,
                                   detail=withdrawal_detail or reason)
    for line in closed.lines():
        record_history(student_id, "Enrolment", None, None, changed_by=by,
                       note=line)

    try:
        from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
            tutor_groups as _tutor_groups,
        )
        group = _tutor_groups.group_for_student(student_id)
        if group is not None and _tutor_groups.unassign_student(student_id):
            record_history(student_id, "Tutor group", group.tutor_group_id,
                           None, changed_by=by,
                           note=f"Left tutor group {group.name}")
    except Exception:
        logger.exception("Could not take %s out of their tutor group", student_id)

    _close_sixth_form_enrolment(student_id, by, status="withdrawn",
                                reason=f"Withdrew from the sixth form: {reason}")
    _revoke_sixth_form_access(student_id)
    disable_leaver_login(student_id)
    disable_orphaned_parent_logins(student_id)
    from education_system.systems.sixth_form.domain.learners.exit_interviews import exit_interviews
    exit_interviews.on_withdrawal(student_id, when, reason)  # pending exit interview; never raises

    out = get_student(student_id)
    assert out is not None
    return out


def reinstate_student(student_id: str, *, status: str = DEFAULT_STATUS,
                      reason: str | None = None,
                      by: str | None = None) -> Student:
    """Put a student who left back on roll.

    Restores the sixth-form login (membership and, if it was disabled at
    leaving, the account) and the tutor group they left, when it still
    exists. Enrolments are not reopened: the year they come back to is a
    decision for the Enrolment screen, not a guess made here.
    """
    _require_writer("reinstating students", lifecycle=True)
    init_db()
    if status not in ON_ROLL_STATUSES:
        raise ValidationError(
            f"Reinstate to one of: {', '.join(ON_ROLL_STATUSES)}")
    student = get_student(student_id)
    if student is None:
        raise ValidationError(f"No student with id {student_id}")
    if student.status != "Left":
        return set_status(student_id, status, reason=reason, by=by)
    by = by or _actor()
    _set_status_row(student_id, status)
    record_history(student_id, "Status", "Left", status, changed_by=by,
                   note=reason or "Reinstated")
    _set_leaving(student, None, None, by)
    logger.info("Reinstated student %s as %s", student_id, status)

    try:
        # Only creates a login if theirs is gone; an existing one (and its
        # password) is kept and just re-enabled below.
        _provision_login_account(student, _temporary_password())
        from education_system.platform.identity.auth.db import connect as _auth_connect
        with _auth_connect() as conn:
            cur = conn.execute(
                "UPDATE users SET is_active = 1, updated_at = datetime('now') "
                "WHERE username = ? AND is_active = 0", (student_id,))
            conn.commit()
        if cur.rowcount:
            logger.info("Re-enabled the login of reinstated student %s", student_id)
    except Exception:
        logger.exception("Could not restore the login of %s", student_id)

    try:
        from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
            tutor_groups as _tutor_groups,
        )
        if _tutor_groups.group_for_student(student_id) is None:
            last = next((h for h in list_history(student_id)
                         if h["field"] == "Tutor group" and h["old_value"]), None)
            if last is not None:
                group = _tutor_groups.get_group(int(last["old_value"]))
                if group is not None:
                    _tutor_groups.assign_student(student_id, group.tutor_group_id)
                    record_history(student_id, "Tutor group", None,
                                   group.tutor_group_id, changed_by=by,
                                   note=f"Back in tutor group {group.name}")
    except Exception:
        logger.exception("Could not restore the tutor group of %s", student_id)

    out = get_student(student_id)
    assert out is not None
    return out


# ── Delete ──────────────────────────────────────────────────────────

def delete_student(student_id: str, *, force: bool = False) -> bool:
    """Delete a student record entered by mistake.

    Refused with :class:`StudentHasRecords` when anything is attached to
    the student (see :func:`linked_record_counts`), because the cascade
    would delete it too. A learner who has gone is marked as left with
    :func:`withdraw_student` instead. ``force`` exists for programmatic
    clean-up of a record whose attachments are known to be disposable;
    no screen passes it.
    """
    _require_writer("deleting students")
    init_db()
    # Capture identifying details before the row is gone so the log
    # message names the person and the audit trail is meaningful even
    # after the record no longer exists.
    snapshot = get_student(student_id)
    if snapshot is not None and not force:
        counts = linked_record_counts(student_id)
        if counts:
            logger.warning("Refused to delete %s: %d linked record(s)",
                           student_id, sum(counts.values()))
            raise StudentHasRecords(student_id, counts)
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM students WHERE student_id = ?", (student_id,)
        )
        conn.commit()
        deleted = cur.rowcount > 0
    if deleted:
        record_history(student_id, "record", note=(
            f"Record deleted ({snapshot.full_name})" if snapshot is not None
            else "Record deleted"))
        if snapshot is not None:
            logger.info(
                "Deleted student %s (%s, email=%s)",
                student_id, snapshot.full_name, snapshot.email)
        else:
            # Theoretically reachable if a concurrent writer inserted
            # the row between snapshot and DELETE — log it so the
            # mismatch is visible.
            logger.info(
                "Deleted student %s (no snapshot — race?)", student_id)
        _deprovision_login_account(
            student_id,
            email=snapshot.email if snapshot is not None else None,
        )
    else:
        logger.warning("delete_student called for unknown id %s", student_id)
    return deleted
