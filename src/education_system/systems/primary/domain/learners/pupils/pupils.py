"""Pupil data layer for the Primary School System.

Reads the primary school DB named by ``paths.PRIMARY_PUPILS_DB``. Year
groups are R (Reception) through 6. Pupil IDs use the ``P`` prefix.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import random
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system import paths

logger = logging.getLogger(__name__)

# Anchored on the single paths module, not on __file__. This module used
# to compute `parents[3] / "data"`, which resolved inside the package —
# a location that stopped existing when the repo moved out of the home
# directory and var/ became a sibling of src/. It did not fail loudly:
# sqlite3 simply created a new empty primary.db next to the source and
# every pupil and leaver read came back empty, while the real data sat
# untouched in var/data/primary/. Every other primary module already
# reads paths.PRIMARY_*; this one was the last holdout.
DB_PATH = paths.PRIMARY_PUPILS_DB
_DATA_DIR = DB_PATH.parent

ID_PREFIX = "P"
ID_DIGITS = 7
YEAR_GROUPS = ("R", "1", "2", "3", "4", "5", "6")
EMAIL_DOMAIN = "primaryschool.local"

_PHONE_RE = re.compile(r"^[0-9 +()\-]{6,20}$")
_DOB_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Where a pupil stands on the school roll. ``applicant`` is a place held for
# a child arriving through a cross-system transfer who has not started;
# ``left`` is a pupil who has moved on — kept, never deleted, so the
# school's own history and statutory returns stay intact.
ON_ROLL = "on_roll"
ROLL_STATUSES = ("applicant", ON_ROLL, "left")
ROLL_STATUS_LABELS = {"applicant": "Applicant", ON_ROLL: "On roll", "left": "Left"}

# The pupil record asks the same things as the secondary school's Add Pupil
# (identity, school, address, needs, parent/carer, medical). The fixed lists
# below match the secondary system's values so a record reads the same on
# both sides of the Year 6 -> Year 7 handover; they are copied, not
# imported, because systems never import each other.
#: The same five options as every other system's add form.
GENDERS = ("Female", "Male", "Non-binary", "Other", "Prefer not to say")
#: DfE SEN provision codes (same labels as the secondary system).
SEN_STATUSES: dict[str, str] = {
    "N": "No special educational need",
    "K": "SEN support",
    "E": "EHC plan",
}
LEAVING_REASONS = (
    "End of Year 6",
    "Moved to another school",
    "Moved away",
    "Elective home education",
    "Permanent exclusion",
    "Other",
)
PARENT_RELATIONSHIPS = (
    "Mother", "Father", "Carer", "Guardian", "Grandparent", "Social worker", "Other",
)

_POSTCODE_RE = re.compile(r"^[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}$")
# Same shape the admissions form accepts, so an enrolled application's
# parent e-mail always carries across.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class Pupil:
    pupil_id: str
    first_name: str
    last_name: str
    year_group: str
    class_name: str | None
    date_of_birth: str | None
    email: str
    parent_name: str | None
    parent_phone: str | None
    medical_notes: str | None
    send_status: str | None
    roll_status: str = ON_ROLL
    journey_id: str | None = None
    left_date: str | None = None
    exit_reason: str | None = None
    middle_names: str | None = None
    preferred_name: str | None = None
    gender: str | None = None
    upn: str | None = None
    admission_date: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    town: str | None = None
    postcode: str | None = None
    sen_status: str | None = None
    fsm_eligible: bool = False
    eal: bool = False
    notes: str | None = None
    parent_relationship: str | None = None
    parent_email: str | None = None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def display_name(self) -> str:
        """Preferred first name if there is one, as staff would say it."""
        return f"{self.preferred_name or self.first_name} {self.last_name}".strip()

    @property
    def legal_name(self) -> str:
        return " ".join(x for x in (self.first_name, self.middle_names,
                                    self.last_name) if x)

    @property
    def sen_label(self) -> str:
        if not self.sen_status:
            return "Not recorded"
        return SEN_STATUSES.get(self.sen_status, self.sen_status)

    @property
    def roll_status_label(self) -> str:
        return ROLL_STATUS_LABELS.get(self.roll_status, self.roll_status)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS pupils (
    pupil_id        TEXT PRIMARY KEY,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    year_group      TEXT NOT NULL,
    class_name      TEXT,
    date_of_birth   TEXT,
    email           TEXT NOT NULL UNIQUE,
    parent_name     TEXT,
    parent_phone    TEXT,
    medical_notes   TEXT,
    send_status     TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    roll_status     TEXT NOT NULL DEFAULT 'on_roll',
    journey_id      TEXT,
    left_date       TEXT,
    exit_reason     TEXT,
    middle_names    TEXT,
    preferred_name  TEXT,
    gender          TEXT,
    upn             TEXT,
    admission_date  TEXT,
    address_line1   TEXT,
    address_line2   TEXT,
    town            TEXT,
    postcode        TEXT,
    sen_status      TEXT,
    fsm_eligible    INTEGER NOT NULL DEFAULT 0,
    eal             INTEGER NOT NULL DEFAULT 0,
    notes           TEXT,
    parent_relationship TEXT,
    parent_email    TEXT
);
"""

# Parity with the secondary school's pupil record (2026-11-05): the columns
# both systems' Add Pupil now ask for.
_PARITY_COLUMNS = (
    ("middle_names", "TEXT"),
    ("preferred_name", "TEXT"),
    ("gender", "TEXT"),
    ("upn", "TEXT"),
    ("admission_date", "TEXT"),
    ("address_line1", "TEXT"),
    ("address_line2", "TEXT"),
    ("town", "TEXT"),
    ("postcode", "TEXT"),
    ("sen_status", "TEXT"),
    ("fsm_eligible", "INTEGER NOT NULL DEFAULT 0"),
    ("eal", "INTEGER NOT NULL DEFAULT 0"),
    ("notes", "TEXT"),
    ("parent_relationship", "TEXT"),
    ("parent_email", "TEXT"),
)

# Columns added after the table first shipped; existing databases gain them
# on the next init_db().
_ADDED_COLUMNS = (
    ("roll_status", "TEXT NOT NULL DEFAULT 'on_roll'"),
    ("journey_id", "TEXT"),
    ("left_date", "TEXT"),
    ("exit_reason", "TEXT"),
    *_PARITY_COLUMNS,
)

#: The parity columns, in the order create/update write them.
_PARITY_FIELDS = tuple(name for name, _decl in _PARITY_COLUMNS)
_BOOL_FIELDS = ("fsm_eligible", "eal")


def _migrate(conn: sqlite3.Connection) -> None:
    have = {row[1] for row in conn.execute("PRAGMA table_info(pupils)")}
    for name, decl in _ADDED_COLUMNS:
        if name not in have:
            conn.execute(f"ALTER TABLE pupils ADD COLUMN {name} {decl}")  # nosec B608 - constant
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_primary_pupils_journey "
        "ON pupils(journey_id) WHERE journey_id IS NOT NULL")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_primary_pupils_upn "
        "ON pupils(upn) WHERE upn IS NOT NULL")
    # SEN status for records made before it existed: derived from the old
    # yes/no SEND flag so the two never disagree.
    conn.execute(
        "UPDATE pupils SET sen_status = CASE lower(send_status) "
        "WHEN 'yes' THEN 'K' WHEN 'no' THEN 'N' END "
        "WHERE sen_status IS NULL AND lower(send_status) IN ('yes', 'no')")


class ValidationError(ValueError):
    """Raised for invalid pupil-form input."""


class DuplicatePupil(ValidationError):
    """A pupil with the same name and date of birth is already recorded.

    Raised by :func:`create_pupil` only when ``check_duplicate=True`` (the
    Add Pupil screens), so a double-entered child is caught; the screen asks
    and retries with the check off."""

    def __init__(self, existing: "Pupil"):
        self.existing = existing
        super().__init__(
            f"{existing.full_name} (born {existing.date_of_birth}) is already "
            f"recorded as {existing.pupil_id}.")


def _connect() -> sqlite3.Connection:
    os.makedirs(_DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
            _migrate(conn)
    except sqlite3.Error:
        logger.exception("Failed to initialise primary pupils DB at %s", DB_PATH)
        raise
    logger.info("Primary pupils DB ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row) -> Pupil:
    keys = r.keys()
    return Pupil(
        pupil_id=r["pupil_id"],
        first_name=r["first_name"],
        last_name=r["last_name"],
        year_group=r["year_group"],
        class_name=r["class_name"],
        date_of_birth=r["date_of_birth"],
        email=r["email"],
        parent_name=r["parent_name"],
        parent_phone=r["parent_phone"],
        medical_notes=r["medical_notes"],
        send_status=r["send_status"],
        roll_status=(r["roll_status"] if "roll_status" in keys else None) or ON_ROLL,
        journey_id=r["journey_id"] if "journey_id" in keys else None,
        left_date=r["left_date"] if "left_date" in keys else None,
        exit_reason=r["exit_reason"] if "exit_reason" in keys else None,
        **{name: (bool(r[name]) if name in _BOOL_FIELDS else r[name])
           for name in _PARITY_FIELDS if name in keys},
    )


def generate_pupil_id() -> str:
    init_db()
    with _connect() as conn:
        for attempt in range(50):
            n = random.randint(10 ** (ID_DIGITS - 1), 10 ** ID_DIGITS - 1)
            pid = f"{ID_PREFIX}{n}"
            if conn.execute(
                "SELECT 1 FROM pupils WHERE pupil_id = ?", (pid,)
            ).fetchone() is None:
                if attempt > 0:
                    logger.info("Allocated pupil id %s after %d collisions",
                                pid, attempt)
                return pid
            if attempt == 25:
                logger.warning("Pupil-id allocator hit %d collisions", attempt)
    logger.error("Exhausted 50 attempts allocating a unique pupil id")
    raise RuntimeError("Could not allocate a unique pupil id after 50 tries")


def _generate_email(pupil_id: str) -> str:
    return f"{pupil_id.lower()}@{EMAIL_DOMAIN}"


def _require(value: str | None, label: str) -> str:
    if not value or not str(value).strip():
        raise ValidationError(f"{label} is required")
    return str(value).strip()


# ── UPN (DfE unique pupil number) ────────────────────────────────────
# Ported from the secondary system's check (systems never import each other).

#: DfE check-letter alphabet (no I, O or S).
_UPN_LETTERS = "ABCDEFGHJKLMNPQRTUVWXYZ"


def upn_check_letter(body: str) -> str:
    """The DfE check letter for the 12 characters after it.

    Each character in positions 2-13 is multiplied by its position, the
    products are summed, and the remainder mod 23 picks the letter. A letter
    in position 13 (a temporary UPN) counts as its index in the alphabet.
    """
    if len(body) != 12:
        raise ValueError("UPN body must be 12 characters")
    total = 0
    for weight, ch in enumerate(body, start=2):
        total += weight * (int(ch) if ch.isdigit() else _UPN_LETTERS.index(ch))
    return _UPN_LETTERS[total % 23]


def upn_problem(upn: str) -> str | None:
    """Why *upn* is not a valid UPN, or ``None`` if it is."""
    if len(upn) != 13:
        return "UPN must be 13 characters"
    first, middle, last = upn[0], upn[1:12], upn[12]
    if first not in _UPN_LETTERS:
        return "UPN must start with a check letter (A-Z, not I, O or S)"
    if not middle.isdigit():
        return "UPN characters 2-12 must be digits"
    if not (last.isdigit() or last in _UPN_LETTERS):
        return "UPN character 13 must be a digit or a letter (not I, O or S)"
    if upn_check_letter(upn[1:]) != first:
        return "UPN check letter doesn't match - please re-check the number"
    return None


# ── Validation ───────────────────────────────────────────────────────

_TRUE = {"1", "true", "yes", "y"}
_FALSE = {"0", "false", "no", "n", ""}


def _text(value: Any, limit: int = 100) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text[:limit] if text else None


def _as_bool(value: Any, label: str) -> bool:
    """Strict yes/no: anything unrecognised is an error, not a silent 'no'."""
    if value is None or isinstance(value, bool):
        return bool(value)
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    text = str(value).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    raise ValidationError(f"{label} must be yes or no")


def _date(value: Any, label: str) -> str | None:
    text = (str(value).strip() if value is not None else "")
    if not text:
        return None
    if not _DOB_RE.match(text):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        return _dt.date.fromisoformat(text).isoformat()
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None


def _sen_code(raw: str) -> str:
    """N/K/E from a code, a label, or "K - SEN support" as a picker shows it."""
    raw = raw.strip()
    code = raw[:1].upper()
    by_label = {label.lower(): k for k, label in SEN_STATUSES.items()}
    if raw.lower() in by_label:
        return by_label[raw.lower()]
    if code in SEN_STATUSES and (len(raw) == 1 or raw[1:].lstrip()[:1] in ("-", "\u2013")):
        return code
    raise ValidationError("SEN status must be N, K or E")


def _sen_from(data: dict[str, Any], current: Pupil | None
              ) -> tuple[bool, str | None, str | None]:
    """``(given, sen_status, send_status)`` from *data*.

    ``sen_status`` (N/K/E) is the record; ``send_status`` stays the derived
    yes/no ("yes" for K or E) that older screens read. A caller that only
    knows the yes/no flag still works: "yes" keeps a current K/E (or means
    K), "no" means N. ``given`` is False when neither key was passed, so an
    update leaves the stored values alone."""
    if "sen_status" in data and _text(data.get("sen_status"), 40):
        code = _sen_code(str(data.get("sen_status")))
        return True, code, "yes" if code in ("K", "E") else "no"
    if "send_status" in data:
        send = (data.get("send_status") or "").strip().lower()
        if send and send not in ("yes", "no"):
            raise ValidationError("SEND status must be 'yes' or 'no'")
        if not send:
            return True, None, None
        now = current.sen_status if current is not None else None
        if send == "yes":
            return True, (now if now in ("K", "E") else "K"), "yes"
        return True, "N", "no"
    if "sen_status" in data:          # given but blank: not recorded
        return True, None, None
    return False, None, None


def _validate(data: dict[str, Any], *, current: Pupil | None = None,
              complete: bool = False) -> dict[str, Any]:
    """A clean copy of *data*, or :class:`ValidationError`.

    Always returns the original fields. The parity fields (see
    :data:`_PARITY_FIELDS`), ``roll_status``, ``left_date`` and
    ``exit_reason`` appear only when *data* carries them, so an older caller
    that passes the original nine keys never wipes them. ``complete=True``
    (the Add Pupil screens) also requires date of birth and gender, as the
    secondary school does."""
    out: dict[str, Any] = {}
    out["first_name"] = _require(data.get("first_name"), "First name")
    out["last_name"] = _require(data.get("last_name"), "Last name")
    yg = _require(data.get("year_group"), "Year group")
    if yg not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of {', '.join(YEAR_GROUPS)}")
    out["year_group"] = yg
    out["class_name"] = (data.get("class_name") or "").strip() or None
    dob = (data.get("date_of_birth") or "").strip()
    if dob and not _DOB_RE.match(dob):
        raise ValidationError("Date of birth must be YYYY-MM-DD")
    if dob:
        dob = _date(dob, "Date of birth") or ""
    if complete and not dob:
        raise ValidationError("Date of birth is required")
    out["date_of_birth"] = dob or None
    out["parent_name"] = (data.get("parent_name") or "").strip() or None
    pphone = (data.get("parent_phone") or "").strip()
    if pphone and not _PHONE_RE.match(pphone):
        raise ValidationError("Parent phone contains invalid characters")
    out["parent_phone"] = pphone or None
    out["medical_notes"] = (data.get("medical_notes") or "").strip() or None
    given, sen, send = _sen_from(data, current)
    out["send_status"] = send
    if given:
        out["sen_status"] = sen

    if "middle_names" in data:
        out["middle_names"] = _text(data.get("middle_names"))
    if "preferred_name" in data:
        out["preferred_name"] = _text(data.get("preferred_name"))
    if "gender" in data or complete:
        gender = _text(data.get("gender"), 20)
        if gender:  # any case: "non-binary" -> "Non-binary"
            gender = next((g for g in GENDERS if g.lower() == gender.lower()), gender)
        if gender is None and complete:
            raise ValidationError("Gender is required")
        if gender is not None and gender not in GENDERS:
            raise ValidationError(f"Gender must be one of: {', '.join(GENDERS)}")
        out["gender"] = gender
    if "upn" in data:
        upn = _text(data.get("upn"), 20)
        upn = upn.replace(" ", "").upper() if upn else None
        if upn:
            problem = upn_problem(upn)
            if problem:
                raise ValidationError(problem)
        out["upn"] = upn
    if "admission_date" in data:
        admission = _date(data.get("admission_date"), "Admission date")
        if admission and out["date_of_birth"] and admission < out["date_of_birth"]:
            raise ValidationError("Admission date can't be before the date of birth")
        out["admission_date"] = admission
    for key in ("address_line1", "address_line2", "town"):
        if key in data:
            out[key] = _text(data.get(key))
    if "postcode" in data:
        postcode = _text(data.get("postcode"), 10)
        if postcode:
            postcode = postcode.upper()
            if not _POSTCODE_RE.match(postcode):
                raise ValidationError("Postcode doesn't look like a UK postcode")
            if " " not in postcode:
                postcode = f"{postcode[:-3]} {postcode[-3:]}"
        out["postcode"] = postcode
    if "fsm_eligible" in data:
        out["fsm_eligible"] = _as_bool(data.get("fsm_eligible"), "Free school meals")
    if "eal" in data:
        out["eal"] = _as_bool(data.get("eal"), "English as an additional language")
    if "notes" in data:
        out["notes"] = _text(data.get("notes"), 2000)
    if "parent_relationship" in data:
        rel = _text(data.get("parent_relationship"), 40)
        if rel:
            rel = next((r for r in PARENT_RELATIONSHIPS if r.lower() == rel.lower()), rel)
        out["parent_relationship"] = rel
    if "parent_email" in data:
        email = (data.get("parent_email") or "").strip().lower() or None
        if email and (len(email) > 254 or not _EMAIL_RE.match(email)):
            raise ValidationError("Parent e-mail address doesn't look right")
        out["parent_email"] = email

    if "roll_status" in data and (data.get("roll_status") or "").strip():
        status = str(data.get("roll_status")).strip()
        if status not in ROLL_STATUSES:
            raise ValidationError(
                f"Roll status must be one of {', '.join(ROLL_STATUSES)}")
        out["roll_status"] = status
        left_date = _date(data.get("left_date"), "Leaving date")
        reason = _text(data.get("exit_reason"))
        if status == "left":
            if not left_date:
                raise ValidationError("A pupil who has left needs a leaving date")
            if out.get("admission_date") and left_date < out["admission_date"]:
                raise ValidationError("Leaving date can't be before the admission date")
            if not reason:
                raise ValidationError("A pupil who has left needs a leaving reason")
        else:
            # Back on roll (or an applicant): old leaving details no longer apply.
            left_date, reason = None, None
        out["left_date"], out["exit_reason"] = left_date, reason
    return out


def _upn_taken(conn: sqlite3.Connection, upn: str | None,
               exclude_id: str | None = None) -> bool:
    if not upn:
        return False
    return conn.execute(
        "SELECT 1 FROM pupils WHERE upn = ? AND pupil_id IS NOT ?",
        (upn, exclude_id)).fetchone() is not None


def find_duplicate(first_name: str, last_name: str,
                   date_of_birth: str | None) -> Pupil | None:
    """A pupil already recorded with this name and date of birth."""
    if not (first_name and last_name and date_of_birth):
        return None
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM pupils WHERE lower(first_name) = lower(?) "
            "AND lower(last_name) = lower(?) AND date_of_birth = ?",
            (first_name.strip(), last_name.strip(), date_of_birth)).fetchone()
    return _row(row) if row is not None else None


def create_pupil(data: dict[str, Any], *, roll_status: str | None = None,
                 journey_id: str | None = None, complete: bool = False,
                 check_duplicate: bool = False) -> Pupil:
    """Create a pupil. ``roll_status='applicant'`` holds a place for a child
    arriving through a cross-system transfer; ``journey_id`` stamps the
    canonical journey so a redelivered transfer finds this row.

    The Add Pupil screens pass ``complete=True`` (date of birth and gender
    required, as in the secondary school) and ``check_duplicate=True``
    (:class:`DuplicatePupil` when the same name and date of birth is already
    recorded). The admission date defaults to today."""
    init_db()
    logger.debug("create_pupil called with fields: %s",
                 sorted(k for k, v in data.items() if v not in (None, "")))
    try:
        payload = _validate(data, complete=complete)
    except ValidationError as e:
        logger.warning("create_pupil validation failed: %s", e)
        raise
    roll_status = roll_status or payload.pop("roll_status", None) or ON_ROLL
    payload.pop("roll_status", None)
    if roll_status not in ROLL_STATUSES:
        raise ValidationError(
            f"Roll status must be one of {', '.join(ROLL_STATUSES)}")
    if roll_status == "left" and not payload.get("left_date"):
        raise ValidationError("A pupil who has left needs a leaving date")
    left_date = payload.pop("left_date", None) if roll_status == "left" else None
    exit_reason = payload.pop("exit_reason", None) if roll_status == "left" else None
    payload.pop("left_date", None)
    payload.pop("exit_reason", None)
    payload.setdefault("admission_date", None)
    payload["admission_date"] = (payload["admission_date"]
                                 or _dt.date.today().isoformat())
    if (payload.get("date_of_birth")
            and payload["admission_date"] < payload["date_of_birth"]):
        raise ValidationError("Admission date can't be before the date of birth")
    extras = {name: payload.get(name) for name in _PARITY_FIELDS}
    for name in _BOOL_FIELDS:
        extras[name] = int(bool(extras[name]))
    if check_duplicate:
        dup = find_duplicate(payload["first_name"], payload["last_name"],
                             payload["date_of_birth"])
        if dup is not None:
            logger.info("create_pupil: possible duplicate of %s", dup.pupil_id)
            raise DuplicatePupil(dup)
    pid = generate_pupil_id()
    email = _generate_email(pid)
    cols = ("pupil_id", "first_name", "last_name", "year_group", "class_name",
            "date_of_birth", "email", "parent_name", "parent_phone",
            "medical_notes", "send_status", "roll_status", "journey_id",
            "left_date", "exit_reason", *extras)
    values = (pid, payload["first_name"], payload["last_name"],
              payload["year_group"], payload["class_name"],
              payload["date_of_birth"], email, payload["parent_name"],
              payload["parent_phone"], payload["medical_notes"],
              payload["send_status"], roll_status, journey_id,
              left_date, exit_reason, *extras.values())
    try:
        with _connect() as conn:
            if _upn_taken(conn, extras.get("upn")):
                raise ValidationError(
                    f"UPN {extras['upn']} is already recorded for another pupil")
            conn.execute(
                f"INSERT INTO pupils ({', '.join(cols)}) "  # nosec B608 - constant columns
                f"VALUES ({', '.join('?' for _ in cols)})",
                values,
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        logger.exception("INSERT failed for new pupil id=%s (collision?)", pid)
        raise ValidationError(f"Could not create pupil — {e}") from e
    except sqlite3.Error:
        logger.exception("Database error creating pupil id=%s", pid)
        raise
    pupil = get_pupil(pid)
    assert pupil is not None
    logger.info("Created pupil %s (%s, year %s)",
                pupil.pupil_id, pupil.full_name, pupil.year_group)
    # Anchor a canonical journey_id so this pupil links to the same person
    # in the nursery/secondary systems (best-effort; matched on name+DOB).
    try:
        from education_system.platform.cross_system import person, progression
        jid = progression.register_local_student(
            "primary", student_id=pupil.pupil_id,
            first_name=pupil.first_name, last_name=pupil.last_name,
            date_of_birth=pupil.date_of_birth)
        if jid:
            person.link_local_record("primary", pupil.pupil_id, jid)
    except Exception:
        logger.debug("Journey registration skipped for pupil %s",
                     pupil.pupil_id, exc_info=True)
    # A login named after this pupil (made before the pupil record) is
    # linked now that the journey exists. Best-effort, never raises.
    from education_system.platform.cross_system import login_links
    for name in (pupil.pupil_id, getattr(pupil, "email", None)):
        login_links.try_sync_username(name)
    return pupil


def get_pupil(pupil_id: str) -> Pupil | None:
    init_db()
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT * FROM pupils WHERE pupil_id = ?", (pupil_id,)
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_pupil(%s) failed", pupil_id)
        raise
    if row is None:
        logger.debug("get_pupil(%s) -> miss", pupil_id)
        return None
    return _row(row)


def find_by_journey(journey_id: str) -> Pupil | None:
    """The pupil stamped with a canonical journey, whatever their roll status."""
    if not journey_id:
        return None
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM pupils WHERE journey_id = ?", (journey_id,)
        ).fetchone()
    return _row(row) if row is not None else None


def set_roll_status(pupil_id: str, roll_status: str, *,
                    left_date: str | None = None,
                    exit_reason: str | None = None) -> Pupil:
    """Move a pupil on or off roll. Never deletes the row."""
    if roll_status not in ROLL_STATUSES:
        raise ValidationError(
            f"Roll status must be one of {', '.join(ROLL_STATUSES)}")
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE pupils SET roll_status = ?, left_date = ?, exit_reason = ? "
            "WHERE pupil_id = ?",
            (roll_status, left_date if roll_status == "left" else None,
             exit_reason if roll_status == "left" else None, pupil_id))
        if cur.rowcount == 0:
            raise ValidationError(f"No pupil with id {pupil_id}")
        conn.commit()
    pupil = get_pupil(pupil_id)
    assert pupil is not None
    logger.info("Pupil %s roll status -> %s", pupil_id, roll_status)
    return pupil


def list_pupils(*, include_off_roll: bool = False) -> list[Pupil]:
    """Pupils on roll. ``include_off_roll`` adds applicants and leavers."""
    init_db()
    where = "" if include_off_roll else "WHERE roll_status = 'on_roll' "
    try:
        with _connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM pupils {where}"  # nosec B608 - constant fragment
                "ORDER BY year_group, last_name, first_name"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_pupils failed")
        raise
    logger.debug("list_pupils -> %d row(s)", len(rows))
    return [_row(r) for r in rows]


def search_pupils(query: str, *, include_off_roll: bool = False) -> list[Pupil]:
    init_db()
    raw = (query or "").strip()
    q = f"%{raw}%"
    roll = "" if include_off_roll else "AND roll_status = 'on_roll' "
    try:
        with _connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM pupils
                WHERE (pupil_id LIKE ?
                   OR first_name LIKE ?
                   OR last_name LIKE ?
                   OR email LIKE ?
                   OR class_name LIKE ?)
                {roll}
                ORDER BY year_group, last_name, first_name
                """,  # nosec B608 - constant fragment
                (q, q, q, q, q),
            ).fetchall()
    except sqlite3.Error:
        logger.exception("search_pupils(query_len=%d) failed", len(raw))
        raise
    logger.debug("search_pupils(query_len=%d) -> %d match(es)", len(raw), len(rows))
    return [_row(r) for r in rows]


def update_pupil(pupil_id: str, data: dict[str, Any], *,
                 complete: bool = False) -> Pupil:
    """Change a pupil. The original fields are always written; the parity
    fields, roll status and leaving details only when *data* carries them,
    so an older caller passing just the original keys never wipes them."""
    init_db()
    logger.debug("update_pupil(%s) called with fields: %s", pupil_id,
                 sorted(k for k, v in data.items() if v not in (None, "")))
    current = get_pupil(pupil_id)
    try:
        payload = _validate(data, current=current, complete=complete)
    except ValidationError as e:
        logger.warning("update_pupil(%s) validation failed: %s", pupil_id, e)
        raise
    if current is None:
        logger.warning("update_pupil called for unknown id %s", pupil_id)
        raise ValidationError(f"No pupil with id {pupil_id}")
    if (payload.get("admission_date") and payload.get("date_of_birth")
            and payload["admission_date"] < payload["date_of_birth"]):
        raise ValidationError("Admission date can't be before the date of birth")
    if "admission_date" in payload and not payload["admission_date"]:
        # The admission date is kept once known; blank means "unchanged".
        payload.pop("admission_date")
    cols = ["first_name", "last_name", "year_group", "class_name",
            "date_of_birth", "parent_name", "parent_phone", "medical_notes",
            "send_status"]
    cols += [name for name in (*_PARITY_FIELDS, "roll_status", "left_date",
                               "exit_reason") if name in payload]
    values = [int(bool(payload[c])) if c in _BOOL_FIELDS else payload[c]
              for c in cols]
    try:
        with _connect() as conn:
            if "upn" in payload and _upn_taken(conn, payload["upn"], pupil_id):
                raise ValidationError(
                    f"UPN {payload['upn']} is already recorded for another pupil")
            cur = conn.execute(
                f"UPDATE pupils SET {', '.join(f'{c} = ?' for c in cols)} "  # nosec B608 - constant columns
                "WHERE pupil_id = ?",
                (*values, pupil_id),
            )
            if cur.rowcount == 0:
                logger.warning("update_pupil called for unknown id %s", pupil_id)
                raise ValidationError(f"No pupil with id {pupil_id}")
            conn.commit()
    except sqlite3.IntegrityError as e:
        logger.exception("UPDATE failed for pupil id=%s", pupil_id)
        raise ValidationError(f"Could not update pupil — {e}") from e
    except sqlite3.Error:
        logger.exception("Database error updating pupil id=%s", pupil_id)
        raise
    pupil = get_pupil(pupil_id)
    assert pupil is not None
    logger.info("Updated pupil %s (%s, year %s)",
                pupil_id, pupil.full_name, pupil.year_group)
    return pupil


def delete_pupil(pupil_id: str) -> bool:
    init_db()
    snapshot = get_pupil(pupil_id)
    try:
        with _connect() as conn:
            cur = conn.execute("DELETE FROM pupils WHERE pupil_id = ?", (pupil_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting pupil id=%s", pupil_id)
        raise
    if deleted:
        if snapshot is not None:
            logger.info("Deleted pupil %s (%s)", pupil_id, snapshot.full_name)
        else:
            logger.info("Deleted pupil %s (no snapshot — race?)", pupil_id)
    else:
        logger.warning("delete_pupil called for unknown id %s", pupil_id)
    return deleted
