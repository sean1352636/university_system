"""Domain layer for Child Directory (Nursery System).

Owns the children-on-roll records, which live in the ``pupils`` table of the
shared nursery DB (``nursery_system/data/nursery.db`` — see
``core/database.py``). The cross-system superadmin dashboard counts the same
``pupils`` table, so this module reads and writes it directly rather than
creating its own.

Follows the 4-layer pattern used across the other systems: validation +
SQLite access here, CLI in ``children_cli.py``, Tk GUI in ``children_views.py``.

Every public function initialises the schema (idempotent), logs at the
appropriate level and raises :class:`ValidationError` for bad form input so
the interface layers can show a friendly message.
"""

from __future__ import annotations

import datetime as _dt
import logging
import random
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.nursery.domain.learners.leavers.leavers import (
    REASONS as _LEAVER_REASONS,
)
from education_system.systems.nursery.infrastructure.database import (
    PUPILS_PARITY_COLUMNS,
    connect,
    init_db,
)

logger = logging.getLogger(__name__)

FEATURE_NAME = "Child Directory"
CATEGORY = "Children & Admissions"

ID_PREFIX = "NCH"
ID_DIGITS = 3

# Early Years settings group children into age-banded rooms. These are the
# defaults offered in the UI; the field accepts free text so a setting can use
# its own room names.
ROOMS = ("Baby Room", "Toddler Room", "Preschool Room")

# Funded-hours entitlements a UK nursery handles (15/30 hours, 2-year-old
# funding) plus an unfunded/private option. Empty = not yet recorded.
FUNDED_HOURS_OPTIONS = (
    "",
    "15 hours",
    "30 hours",
    "2-year-old funding",
    "Private (unfunded)",
)

STATUSES = ("active", "left")

# The roll status the primary and secondary schools show. The nursery keeps
# ``status`` (active/left) as the stored flag — admissions, enrolment and
# leavers write it directly — and presents it under the same labels.
ON_ROLL = "on_roll"
ROLL_STATUSES = (ON_ROLL, "left")
ROLL_STATUS_LABELS = {"applicant": "Applicant", ON_ROLL: "On roll", "left": "Left"}
_STATUS_FOR_ROLL = {ON_ROLL: "active", "left": "left"}
_ROLL_FOR_STATUS = {"active": ON_ROLL, "left": "left"}

# The child record asks the same things as the primary and secondary
# schools' Add Pupil (identity, address, needs, parent/carer, medical). The
# fixed lists match their values so a child reads the same after the move to
# Reception; they are copied, not imported, because systems never import
# each other.
#: The same five options as every other system's add form.
GENDERS = ("Female", "Male", "Non-binary", "Other", "Prefer not to say")
#: DfE SEN provision codes (same labels as the primary/secondary systems).
SEN_STATUSES: dict[str, str] = {
    "N": "No special educational need",
    "K": "SEN support",
    "E": "EHC plan",
}
#: Why a child left — the nursery leavers register's own list (primary's
#: list is about Year 6, which a nursery never has).
LEAVING_REASONS = tuple(_LEAVER_REASONS)
PARENT_RELATIONSHIPS = (
    "Mother", "Father", "Carer", "Guardian", "Grandparent", "Social worker", "Other",
)

_POSTCODE_RE = re.compile(r"^[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}$")

#: The parity columns, in the order create/update write them.
_PARITY_FIELDS = tuple(name for name, _decl in PUPILS_PARITY_COLUMNS
                       if name not in ("left_date", "exit_reason"))
_BOOL_FIELDS = ("fsm_eligible", "eal")

_PHONE_RE = re.compile(r"^[0-9 +()\-]{6,20}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DOB_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(ValueError):
    """Raised for invalid child-form input."""


@dataclass
class Child:
    pupil_id: str
    first_name: str
    last_name: str
    date_of_birth: str | None
    room: str | None
    key_person: str | None
    funded_hours: str | None
    start_date: str | None
    parent_name: str | None
    parent_phone: str | None
    parent_email: str | None
    allergies: str | None
    medical_notes: str | None
    status: str
    # Resolved display name of the key person (joined from ``staff``); not a
    # stored column, populated only by reads that ask for it.
    key_person_name: str | None = None
    # Parity with the primary/secondary pupil record (2026-11-05).
    middle_names: str | None = None
    preferred_name: str | None = None
    gender: str | None = None
    upn: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    town: str | None = None
    postcode: str | None = None
    sen_status: str | None = None
    fsm_eligible: bool = False
    eal: bool = False
    notes: str | None = None
    parent_relationship: str | None = None
    left_date: str | None = None
    exit_reason: str | None = None

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
    def admission_date(self) -> str | None:
        """The nursery's start date, under the schools' name for it."""
        return self.start_date

    @property
    def roll_status(self) -> str:
        return _ROLL_FOR_STATUS.get(self.status, self.status)

    @property
    def roll_status_label(self) -> str:
        return ROLL_STATUS_LABELS.get(self.roll_status, self.roll_status)

    @property
    def sen_label(self) -> str:
        if not self.sen_status:
            return "Not recorded"
        return SEN_STATUSES.get(self.sen_status, self.sen_status)


def _ensure_schema() -> None:
    """Create (and demo-seed) the nursery tables if needed. Idempotent."""
    try:
        init_db()
    except sqlite3.Error:
        logger.exception("Failed to initialise nursery DB for child directory")
        raise


def _row(r: sqlite3.Row) -> Child:
    keys = r.keys()
    return Child(
        pupil_id=r["pupil_id"],
        first_name=r["first_name"],
        last_name=r["last_name"],
        date_of_birth=r["date_of_birth"],
        room=r["room"],
        key_person=r["key_person"],
        funded_hours=r["funded_hours"],
        start_date=r["start_date"],
        parent_name=r["parent_name"],
        parent_phone=r["parent_phone"],
        parent_email=r["parent_email"],
        allergies=r["allergies"],
        medical_notes=r["medical_notes"],
        status=r["status"],
        key_person_name=r["key_person_name"] if "key_person_name" in keys else None,
        **{name: (bool(r[name]) if name in _BOOL_FIELDS else r[name])
           for name in _PARITY_FIELDS if name in keys},
        # Leaving details only describe a child who has left. A leaver
        # recorded through the leavers register (which flips ``status``
        # directly) supplies them when the child row has none.
        left_date=(_first(r, "left_date", "leaver_date")
                   if r["status"] == "left" else None),
        exit_reason=(_first(r, "exit_reason", "leaver_reason")
                     if r["status"] == "left" else None),
    )


def _first(r: sqlite3.Row, *names: str) -> str | None:
    keys = r.keys()
    for name in names:
        if name in keys and r[name]:
            return r[name]
    return None


# Read query that joins the key person's name for display. Kept in one place so
# list/get/search all present the same shape.
_SELECT = """
SELECT p.*,
       TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, ''))
           AS key_person_name,
       (SELECT lv.leaving_date FROM leavers lv WHERE lv.pupil_id = p.pupil_id
         ORDER BY lv.created_at DESC, lv.leaver_id DESC LIMIT 1) AS leaver_date,
       (SELECT lv.reason FROM leavers lv WHERE lv.pupil_id = p.pupil_id
         ORDER BY lv.created_at DESC, lv.leaver_id DESC LIMIT 1) AS leaver_reason
FROM pupils p
LEFT JOIN staff s ON s.staff_id = p.key_person
"""


# ── Validation ───────────────────────────────────────────────────────────────

class DuplicateChild(ValidationError):
    """A child with the same name and date of birth is already recorded.

    Raised by :func:`create_child` only when ``check_duplicate=True`` (the
    Add Child screens), so a double-entered child is caught; the screen asks
    and retries with the check off."""

    def __init__(self, existing: "Child"):
        self.existing = existing
        super().__init__(
            f"{existing.full_name} (born {existing.date_of_birth}) is already "
            f"recorded as {existing.pupil_id}.")


def _require(value: str | None, label: str) -> str:
    if not value or not str(value).strip():
        raise ValidationError(f"{label} is required")
    return str(value).strip()


def _opt(value: str | None) -> str | None:
    v = (value or "").strip()
    return v or None


# ── UPN (DfE unique pupil number) ────────────────────────────────────────────
# Ported from the primary school's check (systems never import each other).
# A nursery class in a school, or a funded child, may already have one.

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
    if code in SEN_STATUSES and (len(raw) == 1 or raw[1:].lstrip()[:1] in ("-", "–")):
        return code
    raise ValidationError("SEN status must be N, K or E")


def _status_from(data: dict[str, Any]) -> tuple[str, bool]:
    """``(status, from_roll)``: the stored active/left flag from either the
    schools' ``roll_status`` (on_roll/left — the Add/Edit forms) or the
    nursery's own ``status`` (active/left — older callers). ``from_roll``
    is True when the form's roll status set it, which is when leaving
    details are required."""
    roll = str(data.get("roll_status") or "").strip().lower()
    if roll:
        if roll not in _STATUS_FOR_ROLL:
            raise ValidationError(
                f"Roll status must be one of {', '.join(ROLL_STATUSES)}")
        return _STATUS_FOR_ROLL[roll], True
    status = str(data.get("status") or "active").strip().lower()
    if status in _STATUS_FOR_ROLL:          # "on_roll" passed as status
        status = _STATUS_FOR_ROLL[status]
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    return status, False


def _validate(data: dict[str, Any], *, complete: bool = False) -> dict[str, Any]:
    """A clean copy of *data*, or :class:`ValidationError`.

    Always returns the original nursery fields. The parity fields (see
    :data:`_PARITY_FIELDS`) and the leaving details appear only when *data*
    carries them, so an older caller that passes the original keys never
    wipes them. ``complete=True`` (the Add Child screens) also requires date
    of birth and gender, as the primary and secondary schools do.
    ``admission_date`` is accepted as the schools' name for ``start_date``.
    """
    out: dict[str, Any] = {}
    out["first_name"] = _require(data.get("first_name"), "First name")
    out["last_name"] = _require(data.get("last_name"), "Last name")

    dob = _date(data.get("date_of_birth"), "Date of birth")
    if complete and not dob:
        raise ValidationError("Date of birth is required")
    out["date_of_birth"] = dob

    out["room"] = _opt(data.get("room"))
    out["key_person"] = _opt(data.get("key_person"))

    funded = (data.get("funded_hours") or "").strip()
    if funded and funded not in FUNDED_HOURS_OPTIONS:
        raise ValidationError(
            "Funded hours must be one of: "
            + ", ".join(o for o in FUNDED_HOURS_OPTIONS if o)
        )
    out["funded_hours"] = funded or None

    start_raw = data.get("start_date")
    if not str(start_raw or "").strip():
        start_raw = data.get("admission_date")
    start = _date(start_raw, "Start date")
    if start and dob and start < dob:
        raise ValidationError("Start date can't be before the date of birth")
    out["start_date"] = start

    out["parent_name"] = _opt(data.get("parent_name"))

    pphone = (data.get("parent_phone") or "").strip()
    if pphone and not _PHONE_RE.match(pphone):
        raise ValidationError("Parent phone contains invalid characters")
    out["parent_phone"] = pphone or None

    pemail = (data.get("parent_email") or "").strip().lower()
    if pemail and (len(pemail) > 254 or not _EMAIL_RE.match(pemail)):
        raise ValidationError("Parent email is not a valid address")
    out["parent_email"] = pemail or None

    out["allergies"] = _opt(data.get("allergies"))
    out["medical_notes"] = _opt(data.get("medical_notes"))

    status, from_roll = _status_from(data)
    out["status"] = status

    # ── Parity fields: written only when given ──
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
    if "sen_status" in data:
        sen = _text(data.get("sen_status"), 40)
        out["sen_status"] = _sen_code(sen) if sen else None
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

    # ── Leaving details ──
    if status == "left":
        if "left_date" in data or "exit_reason" in data or from_roll:
            left_date = _date(data.get("left_date"), "Leaving date")
            reason = _text(data.get("exit_reason"))
            if from_roll:
                if not left_date:
                    raise ValidationError("A child who has left needs a leaving date")
                if not reason:
                    raise ValidationError("A child who has left needs a leaving reason")
            if left_date and out["start_date"] and left_date < out["start_date"]:
                raise ValidationError("Leaving date can't be before the start date")
            out["left_date"], out["exit_reason"] = left_date, reason
    else:
        # Back on roll: old leaving details no longer apply.
        out["left_date"], out["exit_reason"] = None, None
    return out


# ── ID allocation ────────────────────────────────────────────────────────────

def generate_child_id() -> str:
    """Allocate a unique ``NCH###`` id, widening past the demo range if full."""
    _ensure_schema()
    try:
        with connect() as conn:
            existing = {
                r[0] for r in conn.execute("SELECT pupil_id FROM pupils").fetchall()
            }
    except sqlite3.Error:
        logger.exception("Could not read existing child ids")
        raise

    # Prefer the next sequential id (NCH001, NCH002, …) for tidy demo data.
    seq = 1
    while f"{ID_PREFIX}{seq:0{ID_DIGITS}d}" in existing:
        seq += 1
    if seq < 10 ** ID_DIGITS:
        return f"{ID_PREFIX}{seq:0{ID_DIGITS}d}"

    # Sequential range exhausted — fall back to random allocation.
    for attempt in range(50):
        n = random.randint(10 ** (ID_DIGITS - 1), 10 ** (ID_DIGITS + 2) - 1)
        cid = f"{ID_PREFIX}{n}"
        if cid not in existing:
            logger.info("Allocated child id %s after sequential range full", cid)
            return cid
    logger.error("Exhausted attempts allocating a unique child id")
    raise RuntimeError("Could not allocate a unique child id")


# ── Reads ────────────────────────────────────────────────────────────────────

def list_children(*, include_left: bool = False) -> list[Child]:
    _ensure_schema()
    sql = _SELECT
    params: tuple[Any, ...] = ()
    if not include_left:
        sql += " WHERE p.status = ?"
        params = ("active",)
    sql += " ORDER BY p.room, p.last_name, p.first_name"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("list_children failed")
        raise
    logger.debug("list_children(include_left=%s) -> %d row(s)",
                 include_left, len(rows))
    return [_row(r) for r in rows]


def get_child(pupil_id: str) -> Child | None:
    _ensure_schema()
    try:
        with connect() as conn:
            row = conn.execute(
                _SELECT + " WHERE p.pupil_id = ?", (pupil_id,)
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_child(%s) failed", pupil_id)
        raise
    if row is None:
        logger.debug("get_child(%s) -> miss", pupil_id)
        return None
    return _row(row)


def search_children(query: str, *, include_left: bool = True) -> list[Child]:
    _ensure_schema()
    raw = (query or "").strip()
    like = f"%{raw}%"
    sql = _SELECT + """
        WHERE (p.pupil_id LIKE ?
            OR p.first_name LIKE ?
            OR p.last_name LIKE ?
            OR p.room LIKE ?
            OR p.parent_name LIKE ?
            OR p.parent_email LIKE ?
            OR p.preferred_name LIKE ?
            OR p.upn LIKE ?)
    """
    params: list[Any] = [like] * 8
    if not include_left:
        sql += " AND p.status = ?"
        params.append("active")
    sql += " ORDER BY p.room, p.last_name, p.first_name"
    try:
        with connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        logger.exception("search_children(query_len=%d) failed", len(raw))
        raise
    logger.debug("search_children(query_len=%d) -> %d match(es)", len(raw), len(rows))
    return [_row(r) for r in rows]


def list_key_person_choices() -> list[tuple[str, str]]:
    """Return ``(staff_id, "Name (id)")`` pairs for key-person pickers."""
    _ensure_schema()
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT staff_id, first_name, last_name FROM staff "
                "ORDER BY last_name, first_name"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_key_person_choices failed")
        raise
    return [
        (r["staff_id"],
         f"{r['first_name']} {r['last_name']} ({r['staff_id']})")
        for r in rows
    ]


# ── Writes ───────────────────────────────────────────────────────────────────

#: The nursery's original columns, always written by create/update.
_BASE_FIELDS = ("first_name", "last_name", "date_of_birth", "room", "key_person",
                "funded_hours", "start_date", "parent_name", "parent_phone",
                "parent_email", "allergies", "medical_notes", "status")


def _upn_taken(conn: sqlite3.Connection, upn: str | None,
               exclude_id: str | None = None) -> bool:
    if not upn:
        return False
    return conn.execute(
        "SELECT 1 FROM pupils WHERE upn = ? AND pupil_id IS NOT ?",
        (upn, exclude_id)).fetchone() is not None


def find_duplicate(first_name: str, last_name: str,
                   date_of_birth: str | None) -> Child | None:
    """A child already recorded with this name and date of birth."""
    if not (first_name and last_name and date_of_birth):
        return None
    _ensure_schema()
    with connect() as conn:
        row = conn.execute(
            _SELECT + " WHERE lower(p.first_name) = lower(?) "
            "AND lower(p.last_name) = lower(?) AND p.date_of_birth = ?",
            (first_name.strip(), last_name.strip(), date_of_birth)).fetchone()
    return _row(row) if row is not None else None


def create_child(data: dict[str, Any], *, complete: bool = False,
                 check_duplicate: bool = False) -> Child:
    """Create a child on roll.

    The Add Child screens pass ``complete=True`` (date of birth and gender
    required, as in the primary and secondary schools; the start date
    defaults to today) and ``check_duplicate=True`` (:class:`DuplicateChild`
    when the same name and date of birth is already recorded). Admissions,
    enrolment, the API and seeding keep the original, looser rules."""
    _ensure_schema()
    logger.debug("create_child called with fields: %s",
                 sorted(k for k, v in data.items() if v not in (None, "")))
    try:
        payload = _validate(data, complete=complete)
        if complete and not payload["start_date"]:
            payload["start_date"] = _dt.date.today().isoformat()
            if payload["date_of_birth"] and payload["start_date"] < payload["date_of_birth"]:
                raise ValidationError("Start date can't be before the date of birth")
    except ValidationError as e:
        logger.warning("create_child validation failed: %s", e)
        raise
    if check_duplicate:
        dup = find_duplicate(payload["first_name"], payload["last_name"],
                             payload["date_of_birth"])
        if dup is not None:
            logger.info("create_child: possible duplicate of %s", dup.pupil_id)
            raise DuplicateChild(dup)
    cid = generate_child_id()
    extras = {name: payload.get(name) for name in _PARITY_FIELDS}
    for name in _BOOL_FIELDS:
        extras[name] = int(bool(extras[name]))
    extras["left_date"] = payload.get("left_date")
    extras["exit_reason"] = payload.get("exit_reason")
    cols = ("pupil_id", *_BASE_FIELDS, *extras)
    values = (cid, *(payload[c] for c in _BASE_FIELDS), *extras.values())
    try:
        with connect() as conn:
            if _upn_taken(conn, extras.get("upn")):
                raise ValidationError(
                    f"UPN {extras['upn']} is already recorded for another child")
            conn.execute(
                f"INSERT INTO pupils ({', '.join(cols)}) "  # nosec B608 - constant columns
                f"VALUES ({', '.join('?' for _ in cols)})",
                values,
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        logger.exception("INSERT failed for new child id=%s", cid)
        raise ValidationError(f"Could not create child — {e}") from e
    except sqlite3.Error:
        logger.exception("Database error creating child id=%s", cid)
        raise
    child = get_child(cid)
    assert child is not None
    logger.info("Created child %s (%s, room %s)",
                child.pupil_id, child.full_name, child.room or "-")
    # Register into the canonical cross-system identity registry so the
    # child has a stable journey_id from day one (best-effort).
    try:
        from education_system.platform.cross_system import person, progression
        jid = progression.register_local_student(
            "nursery", student_id=child.pupil_id,
            first_name=child.first_name, last_name=child.last_name,
            date_of_birth=child.date_of_birth)
        if jid:
            person.link_local_record("nursery", child.pupil_id, jid)
    except Exception:
        logger.debug("Journey registration skipped for child %s",
                     child.pupil_id, exc_info=True)
    return child


def update_child(pupil_id: str, data: dict[str, Any], *,
                 complete: bool = False) -> Child:
    """Change a child. A key the caller leaves out keeps its stored value —
    the original fields are filled from the record before validation, and
    the parity fields and leaving details are written only when given — so
    an older caller (the API, a partial update) never wipes anything, and
    never puts a leaver back on roll by omitting ``status``."""
    _ensure_schema()
    logger.debug("update_child(%s) called with fields: %s", pupil_id,
                 sorted(k for k, v in data.items() if v not in (None, "")))
    current = get_child(pupil_id)
    if current is None:
        logger.warning("update_child called for unknown id %s", pupil_id)
        raise ValidationError(f"No child with id {pupil_id}")
    merged = dict(data)
    if "admission_date" in merged and "start_date" not in merged:
        merged["start_date"] = merged["admission_date"]
    for key in _BASE_FIELDS:
        if key == "status" and "roll_status" in merged:
            continue
        merged.setdefault(key, getattr(current, key))
    if (merged.get("status") == "left" and "roll_status" not in merged
            and current.status == "left"):
        # Still left: keep the recorded leaving details unless replaced.
        merged.setdefault("left_date", current.left_date)
        merged.setdefault("exit_reason", current.exit_reason)
    try:
        payload = _validate(merged, complete=complete)
    except ValidationError as e:
        logger.warning("update_child(%s) validation failed: %s", pupil_id, e)
        raise
    if payload["start_date"] is None and current.start_date:
        # The start date is kept once known; blank means "unchanged".
        payload["start_date"] = current.start_date
    cols = list(_BASE_FIELDS)
    cols += [name for name in (*_PARITY_FIELDS, "left_date", "exit_reason")
             if name in payload]
    values = [int(bool(payload[c])) if c in _BOOL_FIELDS else payload[c]
              for c in cols]
    try:
        with connect() as conn:
            if "upn" in payload and _upn_taken(conn, payload["upn"], pupil_id):
                raise ValidationError(
                    f"UPN {payload['upn']} is already recorded for another child")
            cur = conn.execute(
                f"UPDATE pupils SET {', '.join(f'{c} = ?' for c in cols)} "  # nosec B608 - constant columns
                "WHERE pupil_id = ?",
                (*values, pupil_id),
            )
            if cur.rowcount == 0:
                logger.warning("update_child called for unknown id %s", pupil_id)
                raise ValidationError(f"No child with id {pupil_id}")
            conn.commit()
    except sqlite3.IntegrityError as e:
        logger.exception("UPDATE failed for child id=%s", pupil_id)
        raise ValidationError(f"Could not update child — {e}") from e
    except sqlite3.Error:
        logger.exception("Database error updating child id=%s", pupil_id)
        raise
    child = get_child(pupil_id)
    assert child is not None
    logger.info("Updated child %s (%s)", pupil_id, child.full_name)
    return child


def delete_child(pupil_id: str) -> bool:
    _ensure_schema()
    snapshot = get_child(pupil_id)
    try:
        with connect() as conn:
            cur = conn.execute(
                "DELETE FROM pupils WHERE pupil_id = ?", (pupil_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Database error deleting child id=%s", pupil_id)
        raise
    if deleted:
        who = snapshot.full_name if snapshot else "(no snapshot — race?)"
        logger.info("Deleted child %s (%s)", pupil_id, who)
    else:
        logger.warning("delete_child called for unknown id %s", pupil_id)
    return deleted


def set_status(pupil_id: str, status: str, *, left_date: str | None = None,
               exit_reason: str | None = None) -> Child:
    """Mark a child active/left without re-validating the whole record.

    *status* is the nursery's ``active``/``left`` (the schools' ``on_roll``
    is accepted too). Leaving records ``left_date`` (default: the one
    already held, else today) and ``exit_reason`` (default: the one already
    held); coming back on roll clears both."""
    _ensure_schema()
    status = (status or "").strip().lower()
    status = _STATUS_FOR_ROLL.get(status, status)
    if status not in STATUSES:
        raise ValidationError(f"Status must be one of {', '.join(STATUSES)}")
    when = _date(left_date, "Leaving date")
    reason = _text(exit_reason)
    try:
        with connect() as conn:
            if status == "left":
                cur = conn.execute(
                    "UPDATE pupils SET status = ?, "
                    "left_date = COALESCE(?, left_date, ?), "
                    "exit_reason = COALESCE(?, exit_reason) WHERE pupil_id = ?",
                    (status, when, _dt.date.today().isoformat(), reason, pupil_id),
                )
            else:
                cur = conn.execute(
                    "UPDATE pupils SET status = ?, left_date = NULL, "
                    "exit_reason = NULL WHERE pupil_id = ?",
                    (status, pupil_id),
                )
            if cur.rowcount == 0:
                raise ValidationError(f"No child with id {pupil_id}")
            conn.commit()
    except sqlite3.Error:
        logger.exception("Database error setting status for child id=%s", pupil_id)
        raise
    child = get_child(pupil_id)
    assert child is not None
    logger.info("Set child %s status -> %s", pupil_id, status)
    return child
