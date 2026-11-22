"""Pupil records for the Secondary School System (Years 7-11).

Create, read, update and delete, with the rules the GUI and CLI share:

* **Who** - anyone with a staff role can read; only roles in
  :data:`access.PUPIL_EDITORS` can create, change or delete. The check is made
  here as well as in the screens, so no screen can skip it.
* **UPN** - optional (a new arrival may not have one yet) but, when given,
  must be a well-formed 13-character UPN with the correct DfE check letter,
  and unique.
* **Leavers** - a pupil who leaves is marked ``left`` with a leaving date and
  reason, and keeps their record. Delete is for records created in error: it
  needs a reason, and the audit trail keeps a copy of what was removed.
* **Audit** - every create, update and delete writes a row to
  ``pupil_audit`` saying who did it and what changed.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import re
from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields
from typing import Any, Iterator

from education_system.systems.secondary.core.permissions.access import SEN_EDITORS, SEND_EDITORS, Principal
from education_system.systems.secondary.core.academic_calendar.school_year import (  # noqa: F401 - P.academic_year_start
    academic_year_start,
)
from education_system.systems.secondary.core.exceptions.errors import (  # noqa: F401 - P.<Error>
    NotFound,
    PermissionDenied,
    ValidationError,
)
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

logger = logging.getLogger(__name__)

YEAR_GROUPS: tuple[int, ...] = (7, 8, 9, 10, 11)
#: The same five options as every other system's add form. The census takes
#: F/M only; the other three go to it blank and are flagged (see census.py).
GENDERS: tuple[str, ...] = ("Female", "Male", "Non-binary", "Other", "Prefer not to say")
ROLL_STATUSES: tuple[str, ...] = ("on_roll", "left")
ROLL_STATUS_LABELS = {"on_roll": "On roll", "left": "Left"}
#: DfE SEN provision codes.
SEN_STATUSES: dict[str, str] = {
    "N": "No special educational need",
    "K": "SEN support",
    "E": "EHC plan",
}
LEAVING_REASONS: tuple[str, ...] = (
    "End of Year 11",
    "Moved to another school",
    "Moved away",
    "Elective home education",
    "Permanent exclusion",
    "Other",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pupils (
    pupil_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    admission_no      TEXT UNIQUE,
    upn               TEXT UNIQUE,
    legal_first_name  TEXT NOT NULL,
    middle_names      TEXT,
    legal_last_name   TEXT NOT NULL,
    preferred_name    TEXT,
    date_of_birth     TEXT NOT NULL,
    gender            TEXT NOT NULL CHECK (gender IN ('Female', 'Male', 'Non-binary', 'Other',
                                                  'Prefer not to say')),
    year_group        INTEGER NOT NULL CHECK (year_group BETWEEN 7 AND 11),
    form_group        TEXT,
    admission_date    TEXT NOT NULL,
    roll_status       TEXT NOT NULL DEFAULT 'on_roll'
                      CHECK (roll_status IN ('on_roll', 'left')),
    leaving_date      TEXT,
    leaving_reason    TEXT,
    address_line1     TEXT,
    address_line2     TEXT,
    town              TEXT,
    postcode          TEXT,
    sen_status        TEXT NOT NULL DEFAULT 'N' CHECK (sen_status IN ('N', 'K', 'E')),
    fsm_eligible      INTEGER NOT NULL DEFAULT 0 CHECK (fsm_eligible IN (0, 1)),
    eal               INTEGER NOT NULL DEFAULT 0 CHECK (eal IN (0, 1)),
    notes             TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    created_by        TEXT,
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by        TEXT
);
CREATE INDEX IF NOT EXISTS ix_pupils_name ON pupils (legal_last_name, legal_first_name);
CREATE INDEX IF NOT EXISTS ix_pupils_year ON pupils (roll_status, year_group, form_group);

-- No foreign key to pupils: the trail must outlive a deleted record.
CREATE TABLE IF NOT EXISTS pupil_audit (
    audit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id   INTEGER NOT NULL,
    action     TEXT NOT NULL CHECK (action IN ('create', 'update', 'delete')),
    actor      TEXT NOT NULL,
    at         TEXT NOT NULL DEFAULT (datetime('now')),
    detail     TEXT
);
CREATE INDEX IF NOT EXISTS ix_pupil_audit_pupil ON pupil_audit (pupil_id, at);
"""

database.register_schema("pupils", _SCHEMA)


def gender_choice(value: Any) -> str:
    """*value* as one of :data:`GENDERS` when it matches one (any case), else
    the text as given so the rules can report it."""
    text = " ".join(str(value or "").split())
    return next((g for g in GENDERS if g.lower() == text.lower()), text)


_OLD_GENDER_CHECK = re.compile(r"CHECK\s*\(\s*gender\s+IN\s*\(\s*'Female'\s*,\s*'Male'\s*\)\s*\)")
_GENDER_CHECK = ("CHECK (gender IN ('Female', 'Male', 'Non-binary', 'Other', "
                 "'Prefer not to say'))")


def _widen_gender_check(conn) -> None:
    """Databases made before the five gender options carry a Female/Male-only
    CHECK, which SQLite can't alter in place. Rebuild ``pupils`` with the
    wider rule (SQLite's documented copy-and-rename): foreign keys off for
    the swap, the same columns and rows, the indexes re-created, then a
    foreign-key check before committing. Does nothing once done."""
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' "
                       "AND name = 'pupils'").fetchone()
    if not row or not _OLD_GENDER_CHECK.search(row[0]):
        return
    new_sql = _OLD_GENDER_CHECK.sub(_GENDER_CHECK, row[0])
    new_sql = re.sub(r'^CREATE TABLE\s+(?:IF NOT EXISTS\s+)?"?pupils"?',
                     "CREATE TABLE pupils__gender5", new_sql, count=1)
    indexes = [r[0] for r in conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index' AND tbl_name = 'pupils' "
        "AND sql IS NOT NULL")]
    conn.commit()
    # Only new breakage counts: a violation already in the file elsewhere
    # must not block the upgrade for ever.
    before = {tuple(r) for r in conn.execute("PRAGMA foreign_key_check")}
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("BEGIN")
        conn.execute("DROP TABLE IF EXISTS pupils__gender5")
        conn.execute(new_sql)
        conn.execute("INSERT INTO pupils__gender5 SELECT * FROM pupils")
        conn.execute("DROP TABLE pupils")
        conn.execute("ALTER TABLE pupils__gender5 RENAME TO pupils")
        for ddl in indexes:
            conn.execute(ddl)
        new = {tuple(r) for r in conn.execute("PRAGMA foreign_key_check")} - before
        if new:
            raise database.IntegrityError(f"would break {len(new)} foreign key(s)")
        conn.commit()
        logger.info("pupils: gender rule widened to the five options")
    except Exception:
        # Leave the old table as it was; saving a pupil with one of the new
        # options is refused by the old rule until this succeeds.
        conn.rollback()
        logger.exception("pupils: could not widen the gender rule; left unchanged")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


database.register_upgrade("pupils.gender_five_options", _widen_gender_check)


class DuplicatePupil(ValueError):
    """A pupil with the same legal name and date of birth already exists.

    Raised by :func:`create_pupil` unless ``allow_duplicate=True``, so a
    double-entered record or a re-imported file is caught.
    """

    def __init__(self, existing: "Pupil"):
        self.existing = existing
        super().__init__(
            f"{existing.full_name} (born {existing.date_of_birth}) is already "
            f"recorded as {existing.admission_no}.")


@dataclass(frozen=True)
class Pupil:
    pupil_id: int
    admission_no: str
    upn: str | None
    legal_first_name: str
    middle_names: str | None
    legal_last_name: str
    preferred_name: str | None
    date_of_birth: str
    gender: str
    year_group: int
    form_group: str | None
    admission_date: str
    roll_status: str
    leaving_date: str | None
    leaving_reason: str | None
    address_line1: str | None
    address_line2: str | None
    town: str | None
    postcode: str | None
    sen_status: str
    fsm_eligible: bool
    eal: bool
    notes: str | None
    created_at: str
    created_by: str | None
    updated_at: str
    updated_by: str | None

    @property
    def full_name(self) -> str:
        return f"{self.legal_first_name} {self.legal_last_name}"

    @property
    def display_name(self) -> str:
        """Preferred first name if there is one, as staff would say it."""
        first = self.preferred_name or self.legal_first_name
        return f"{first} {self.legal_last_name}"

    @property
    def roll_status_label(self) -> str:
        return ROLL_STATUS_LABELS.get(self.roll_status, self.roll_status)

    @property
    def sen_label(self) -> str:
        return SEN_STATUSES.get(self.sen_status, self.sen_status)


#: Fields a caller may set. Everything else is managed here.
EDITABLE_FIELDS: tuple[str, ...] = (
    "upn", "legal_first_name", "middle_names", "legal_last_name", "preferred_name",
    "date_of_birth", "gender", "year_group", "form_group", "admission_date",
    "roll_status", "leaving_date", "leaving_reason",
    "address_line1", "address_line2", "town", "postcode",
    "sen_status", "fsm_eligible", "eal", "notes",
)


# ── UPN ──────────────────────────────────────────────────────────────

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


# ── Year group from date of birth ────────────────────────────────────

def expected_year_group(date_of_birth: str, today: _dt.date | None = None) -> int:
    """National Curriculum year for a child born on *date_of_birth*.

    A child's year is set by their age on 31 August before the academic year
    starts: aged 11 then means Year 7.
    """
    dob = _dt.date.fromisoformat(date_of_birth)
    start = academic_year_start(today)
    cutoff = _dt.date(start.year, 8, 31)
    age = cutoff.year - dob.year - ((cutoff.month, cutoff.day) < (dob.month, dob.day))
    return age - 4


def year_group_warning(date_of_birth: str, year_group: int,
                       today: _dt.date | None = None) -> str | None:
    """A note when the chosen year group isn't the pupil's age-expected one.

    Not an error - pupils are sometimes taught out of their year group - but
    worth confirming before saving.
    """
    try:
        expected = expected_year_group(date_of_birth, today)
    except ValueError:
        return None
    if expected == int(year_group):
        return None
    return (f"A pupil born on {date_of_birth} would normally be in Year {expected}, "
            f"not Year {year_group}.")


# ── Validation ───────────────────────────────────────────────────────

_POSTCODE_RE = re.compile(r"^[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}$")


def _clean_text(value: Any, limit: int = 100) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text[:limit] if text else None


_TRUE = {"1", "true", "yes", "y"}
_FALSE = {"0", "false", "no", "n", ""}


def _as_bool(value: Any, label: str, problems: list[str]) -> bool:
    """Strict yes/no: anything unrecognised is a problem, not a silent 'no'."""
    if value is None or isinstance(value, bool):
        return bool(value)
    if isinstance(value, int):
        if value in (0, 1):
            return bool(value)
    else:
        text = str(value).strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
    problems.append(f"{label} must be yes or no")
    return False


def _parse_date(value: Any, label: str, problems: list[str]) -> str | None:
    text = _clean_text(value, 10)
    if not text:
        return None
    try:
        return _dt.date.fromisoformat(text).isoformat()
    except ValueError:
        problems.append(f"{label} must be a date in the form YYYY-MM-DD")
        return None


def _validate(data: dict[str, Any], *, today: _dt.date | None = None) -> dict[str, Any]:
    """Return a clean copy of *data* or raise :class:`ValidationError`."""
    today = today or _dt.date.today()
    problems: list[str] = []
    out: dict[str, Any] = {}

    unknown = set(data) - set(EDITABLE_FIELDS)
    if unknown:
        problems.append(f"Unknown field(s): {', '.join(sorted(unknown))}")

    for key, label in (("legal_first_name", "Legal first name"),
                       ("legal_last_name", "Legal last name")):
        out[key] = _clean_text(data.get(key))
        if not out[key]:
            problems.append(f"{label} is required")
    out["middle_names"] = _clean_text(data.get("middle_names"))
    out["preferred_name"] = _clean_text(data.get("preferred_name"))

    upn = _clean_text(data.get("upn"), 20)
    upn = upn.replace(" ", "").upper() if upn else None
    if upn:
        problem = upn_problem(upn)
        if problem:
            problems.append(problem)
    out["upn"] = upn

    dob = _parse_date(data.get("date_of_birth"), "Date of birth", problems)
    if dob is None and not any(p.startswith("Date of birth") for p in problems):
        problems.append("Date of birth is required")
    out["date_of_birth"] = dob

    gender = gender_choice(data.get("gender"))
    if gender not in GENDERS:
        problems.append(f"Gender must be one of: {', '.join(GENDERS)}")
    out["gender"] = gender

    try:
        year = int(data.get("year_group"))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        year = None
    if year not in YEAR_GROUPS:
        problems.append("Year group must be 7, 8, 9, 10 or 11")
    out["year_group"] = year

    form = _clean_text(data.get("form_group"), 10)
    out["form_group"] = form.upper() if form else None

    admission = _parse_date(data.get("admission_date"), "Admission date", problems)
    if admission is None and not any(p.startswith("Admission date") for p in problems):
        admission = today.isoformat()
    if admission and dob:
        # Judged at admission, not today, so a leaver's record stays
        # editable years after they've left.
        born, joined = _dt.date.fromisoformat(dob), _dt.date.fromisoformat(admission)
        age = joined.year - born.year - ((joined.month, joined.day) < (born.month, born.day))
        if admission < dob:
            problems.append("Admission date can't be before the date of birth")
        elif not 9 <= age <= 17:
            problems.append(
                f"A pupil aged {age} on their admission date doesn't fit Years 7-11")
    out["admission_date"] = admission

    status = _clean_text(data.get("roll_status"), 10) or "on_roll"
    if status not in ROLL_STATUSES:
        problems.append("Roll status must be on_roll or left")
    out["roll_status"] = status
    leaving_date = _parse_date(data.get("leaving_date"), "Leaving date", problems)
    leaving_reason = _clean_text(data.get("leaving_reason"))
    if status == "left":
        if not leaving_date:
            problems.append("A pupil who has left needs a leaving date")
        elif admission and leaving_date < admission:
            problems.append("Leaving date can't be before the admission date")
        if not leaving_reason:
            problems.append("A pupil who has left needs a leaving reason")
    else:
        # Back on roll: the old leaving details no longer apply.
        leaving_date, leaving_reason = None, None
    out["leaving_date"], out["leaving_reason"] = leaving_date, leaving_reason

    out["address_line1"] = _clean_text(data.get("address_line1"))
    out["address_line2"] = _clean_text(data.get("address_line2"))
    out["town"] = _clean_text(data.get("town"))
    postcode = _clean_text(data.get("postcode"), 10)
    if postcode:
        postcode = postcode.upper()
        if not _POSTCODE_RE.match(postcode):
            problems.append("Postcode doesn't look like a UK postcode")
        elif " " not in postcode:
            postcode = f"{postcode[:-3]} {postcode[-3:]}"
    out["postcode"] = postcode

    sen = (_clean_text(data.get("sen_status"), 1) or "N").upper()
    if sen not in SEN_STATUSES:
        problems.append("SEN status must be N, K or E")
    out["sen_status"] = sen
    out["fsm_eligible"] = _as_bool(data.get("fsm_eligible"), "Free school meals", problems)
    out["eal"] = _as_bool(data.get("eal"), "English as an additional language", problems)
    out["notes"] = _clean_text(data.get("notes"), 2000)

    if problems:
        raise ValidationError(problems)
    return out


# ── Helpers ──────────────────────────────────────────────────────────

_PUPIL_FIELDS = tuple(f.name for f in fields(Pupil))


def _row_to_pupil(row) -> Pupil:
    values = {k: row[k] for k in _PUPIL_FIELDS}
    values["fsm_eligible"] = bool(values["fsm_eligible"])
    values["eal"] = bool(values["eal"])
    return Pupil(**values)


def _require_editor(actor: Principal) -> None:
    if not actor.can_edit_pupils:
        raise PermissionDenied(
            "Your account can view pupil records but not change them.")


def _audit(conn, pupil_id: int, action: str, actor: Principal, detail: dict) -> None:
    conn.execute(
        "INSERT INTO pupil_audit (pupil_id, action, actor, detail) VALUES (?, ?, ?, ?)",
        (pupil_id, action, actor.username or "unknown",
         json.dumps(detail, default=str, sort_keys=True)))


def _upn_taken(conn, upn: str | None, exclude_id: int | None = None) -> bool:
    if not upn:
        return False
    row = conn.execute(
        "SELECT pupil_id FROM pupils WHERE upn = ? AND pupil_id IS NOT ?",
        (upn, exclude_id)).fetchone()
    return row is not None


@contextmanager
def _logged(action: str, actor: Principal, target: Any = None) -> Iterator[None]:
    """Log a refused or failed write; the caller logs success itself."""
    try:
        yield
    except PermissionDenied:
        activity_log.record(action, target=target, outcome="denied", principal=actor)
        raise
    except ValidationError as e:
        activity_log.record(action, target=target, outcome="invalid", principal=actor,
                            problems=len(e.problems))
        raise
    except DuplicatePupil as e:
        activity_log.record(action, target=target, outcome="possible_duplicate",
                            principal=actor, existing=e.existing.admission_no)
        raise
    except NotFound:
        activity_log.record(action, target=target, outcome="not_found", principal=actor)
        raise
    except Exception as e:
        activity_log.record(action, target=target, outcome="error", principal=actor,
                            error=type(e).__name__)
        raise


# ── Create ───────────────────────────────────────────────────────────

def create_pupil(data: dict[str, Any], *, actor: Principal,
                 allow_duplicate: bool = False) -> Pupil:
    """Add a pupil. Raises :class:`ValidationError`, :class:`PermissionDenied`
    or :class:`DuplicatePupil` (same legal name and date of birth)."""
    with _logged("pupil.create", actor):
        pupil = _create(data, actor, allow_duplicate)
    activity_log.record("pupil.create", target=pupil.admission_no, principal=actor,
                        year_group=pupil.year_group,
                        duplicate_confirmed="yes" if allow_duplicate else None)
    return pupil


def _create(data: dict[str, Any], actor: Principal, allow_duplicate: bool) -> Pupil:
    _require_editor(actor)
    clean = _validate(data)
    with database.connect() as conn:
        if _upn_taken(conn, clean["upn"]):
            raise ValidationError([f"UPN {clean['upn']} is already recorded for another pupil"])
        if not allow_duplicate:
            row = conn.execute(
                "SELECT * FROM pupils WHERE lower(legal_first_name) = lower(?) "
                "AND lower(legal_last_name) = lower(?) AND date_of_birth = ?",
                (clean["legal_first_name"], clean["legal_last_name"],
                 clean["date_of_birth"])).fetchone()
            if row is not None:
                raise DuplicatePupil(_row_to_pupil(row))
        cols = list(clean)
        cur = conn.execute(
            f"INSERT INTO pupils ({', '.join(cols)}, created_by, updated_by) "
            f"VALUES ({', '.join('?' for _ in cols)}, ?, ?)",
            [int(v) if isinstance(v, bool) else v for v in clean.values()]
            + [actor.username, actor.username])
        pupil_id = cur.lastrowid
        conn.execute("UPDATE pupils SET admission_no = ? WHERE pupil_id = ?",
                     (f"SEC{pupil_id:06d}", pupil_id))
        _audit(conn, pupil_id, "create", actor, clean)
        row = conn.execute("SELECT * FROM pupils WHERE pupil_id = ?", (pupil_id,)).fetchone()
    return _row_to_pupil(row)


# ── Add Pupil: parent / carer and medical / care notes ───────────────
#
# Add Pupil asks the same things as the primary school's: as well as the
# pupil record it takes the first parent/carer and any medical/care notes.
# They are not pupil columns here - the contact becomes the pupil's
# priority-1 row in ``pupil_contacts`` (:mod:`contacts`) and the notes a
# medical-register entry (:mod:`modules.medical.domain.medical`), so they show
# and are edited where staff already look for them.

#: The parent/carer details Add Pupil asks for.
ADMISSION_CONTACT_FIELDS: tuple[str, ...] = ("full_name", "relationship", "phone", "email")
#: The medical-register condition free-text care notes are filed under.
CARE_NOTES_CONDITION = "Other"
_CARE_NOTES_LIMIT = 2000


def _admission_contact(contact: dict[str, Any] | None) -> dict[str, Any] | None:
    """The contact row to add, or ``None`` when nothing was entered."""
    if not contact:
        return None
    picked = {k: contact.get(k) for k in ADMISSION_CONTACT_FIELDS}
    if not any(str(v or "").strip() for v in picked.values()):
        return None
    return {**picked, "priority": 1, "parental_responsibility": True}


def check_admission_extras(data: dict[str, Any], contact: dict[str, Any] | None,
                           medical_notes: str | None) -> None:
    """Every problem with the pupil, parent/carer and notes at once, before
    anything is saved (so a bad e-mail can't leave a pupil half-added)."""
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    problems: list[str] = []
    try:
        _validate(data)
    except ValidationError as e:
        problems += e.problems
    row = _admission_contact(contact)
    if row is not None:
        try:
            C.validate(row)
        except ValidationError as e:
            problems += [f"Parent / carer: {p}" for p in e.problems]
    if medical_notes and len(medical_notes.strip()) > _CARE_NOTES_LIMIT:
        problems.append(f"Medical / care notes must be {_CARE_NOTES_LIMIT} characters or fewer")
    if problems:
        raise ValidationError(problems)


def record_admission_extras(pupil_id: int, *, contact: dict[str, Any] | None,
                            medical_notes: str | None, actor: Principal) -> list[str]:
    """Save the parent/carer and care notes for a just-added pupil. Returns
    what could not be saved (the pupil itself is already in)."""
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    warnings: list[str] = []
    row = _admission_contact(contact)
    if row is not None:
        try:
            C.add_contact(pupil_id, row, actor=actor)
        except Exception as e:  # noqa: BLE001 - reported, the pupil is saved
            warnings.append(f"The parent / carer was not saved: {e} - add them in "
                            "the pupil's Contacts section.")
    notes = (medical_notes or "").strip()[:_CARE_NOTES_LIMIT]
    if notes:
        try:
            from education_system.systems.secondary.modules.medical.domain import medical as M
            M.add_condition({"pupil_id": pupil_id, "condition": CARE_NOTES_CONDITION,
                             "notes": notes}, actor=actor)
        except Exception as e:  # noqa: BLE001 - reported, the pupil is saved
            warnings.append(f"The medical / care notes were not saved: {e} - add them "
                            "on the Medical screen.")
    return warnings


def create_pupil_with_family(data: dict[str, Any], *, actor: Principal,
                             contact: dict[str, Any] | None = None,
                             medical_notes: str | None = None,
                             allow_duplicate: bool = False) -> tuple[Pupil, list[str]]:
    """Add Pupil: the pupil, then their first parent/carer and any medical /
    care notes. Everything is checked first; returns ``(pupil, warnings)``
    where warnings say what (if anything) didn't save after the pupil did.
    Raises like :func:`create_pupil`, including :class:`DuplicatePupil`."""
    _require_editor(actor)
    check_admission_extras(data, contact, medical_notes)
    pupil = create_pupil(data, actor=actor, allow_duplicate=allow_duplicate)
    return pupil, record_admission_extras(pupil.pupil_id, contact=contact,
                                          medical_notes=medical_notes, actor=actor)


# ── Read ─────────────────────────────────────────────────────────────

def get_pupil(pupil_id: int) -> Pupil | None:
    with database.connect() as conn:
        row = conn.execute("SELECT * FROM pupils WHERE pupil_id = ?",
                           (int(pupil_id),)).fetchone()
    return _row_to_pupil(row) if row else None


def find_by_reference(ref: str) -> Pupil | None:
    """Look a pupil up by admission number, UPN or internal id."""
    ref = (ref or "").strip().upper()
    if not ref:
        return None
    with database.connect() as conn:
        row = conn.execute(
            "SELECT * FROM pupils WHERE admission_no = ? OR upn = ? "
            "OR CAST(pupil_id AS TEXT) = ?", (ref, ref, ref)).fetchone()
    return _row_to_pupil(row) if row else None


def list_pupils(*, search: str | None = None, year_group: int | None = None,
                form_group: str | None = None,
                roll_status: str | None = "on_roll") -> list[Pupil]:
    """Pupils in surname order. *roll_status* ``None`` includes leavers.

    *search* matches any part of the legal, middle or preferred names, the
    admission number or the UPN.
    """
    where, params = [], []
    if roll_status:
        where.append("roll_status = ?")
        params.append(roll_status)
    if year_group:
        where.append("year_group = ?")
        params.append(int(year_group))
    if form_group:
        where.append("upper(form_group) = upper(?)")
        params.append(form_group.strip())
    for term in (search or "").split():
        like = f"%{term}%"
        where.append(
            "(legal_first_name LIKE ? OR legal_last_name LIKE ? OR middle_names LIKE ? "
            "OR preferred_name LIKE ? OR admission_no LIKE ? OR upn LIKE ?)")
        params.extend([like] * 6)
    sql = "SELECT * FROM pupils"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY legal_last_name COLLATE NOCASE, legal_first_name COLLATE NOCASE"
    with database.connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_pupil(r) for r in rows]


def form_groups_in_use() -> list[str]:
    """Distinct form groups on pupil records, for filter dropdowns."""
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT form_group FROM pupils WHERE form_group IS NOT NULL "
            "ORDER BY form_group").fetchall()
    return [r[0] for r in rows]


def history(pupil_id: int) -> list[dict[str, Any]]:
    """Audit trail for one pupil, newest first."""
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT action, actor, at, detail FROM pupil_audit WHERE pupil_id = ? "
            "ORDER BY audit_id DESC", (int(pupil_id),)).fetchall()
    return [dict(r) for r in rows]


# ── Update ───────────────────────────────────────────────────────────

def update_pupil(pupil_id: int, changes: dict[str, Any], *, actor: Principal) -> Pupil:
    """Apply *changes* (any subset of :data:`EDITABLE_FIELDS`) to a pupil.

    Fields not mentioned keep their current values, so a caller can't blank
    a field by leaving it out. To clear an optional field pass ``""``.
    """
    return update_pupil_detailed(pupil_id, changes, actor=actor)[0]


def update_pupil_detailed(pupil_id: int, changes: dict[str, Any], *,
                          actor: Principal) -> tuple[Pupil, list[str]]:
    """:func:`update_pupil`, also returning the names of the fields that changed."""
    with _logged("pupil.update", actor, target=_ref(pupil_id)):
        pupil, changed = _update(pupil_id, changes, actor)
    activity_log.record("pupil.update", target=pupil.admission_no, principal=actor,
                        outcome="ok" if changed else "no_change", fields=changed or None)
    if "roll_status" in changed:
        # A leaver's login closes; a pupil back on roll gets theirs back.
        # (Lazy import: pupil_accounts imports this module.)
        from education_system.systems.secondary.modules.pupils.domain import pupil_accounts
        if pupil.roll_status == "left":
            pupil_accounts.close_for_leaver(pupil.pupil_id, actor=actor,
                                            left_on=pupil.leaving_date or "")
        else:
            pupil_accounts.reopen_for_pupil(pupil.pupil_id, actor=actor)
    return pupil, list(changed)


def _ref(pupil_id: int) -> str:
    """Admission number for log lines, falling back to the raw id."""
    try:
        pupil = get_pupil(pupil_id)
    except Exception:
        pupil = None
    return pupil.admission_no if pupil else f"id:{pupil_id}"


def _update(pupil_id: int, changes: dict[str, Any],
            actor: Principal) -> tuple[Pupil, list[str]]:
    _require_editor(actor)
    current = get_pupil(pupil_id)
    if current is None:
        raise NotFound(f"No pupil with id {pupil_id}")
    merged = {k: getattr(current, k) for k in EDITABLE_FIELDS}
    merged.update(changes)
    clean = _validate(merged)
    before = {k: getattr(current, k) for k in EDITABLE_FIELDS}
    diff = {k: {"from": before[k], "to": v} for k, v in clean.items() if before[k] != v}
    if not diff:
        return current, []
    with database.connect() as conn:
        if _upn_taken(conn, clean["upn"], exclude_id=current.pupil_id):
            raise ValidationError([f"UPN {clean['upn']} is already recorded for another pupil"])
        sets = ", ".join(f"{k} = ?" for k in clean)
        conn.execute(
            f"UPDATE pupils SET {sets}, updated_at = datetime('now'), updated_by = ? "
            "WHERE pupil_id = ?",
            [int(v) if isinstance(v, bool) else v for v in clean.values()]
            + [actor.username, current.pupil_id])
        _audit(conn, current.pupil_id, "update", actor, diff)
        row = conn.execute("SELECT * FROM pupils WHERE pupil_id = ?",
                           (current.pupil_id,)).fetchone()
    return _row_to_pupil(row), sorted(diff)


def can_set_sen_status(actor: Principal) -> bool:
    """Pupil record editors, and the SENCO (SEN / SEND editors) for this one field."""
    return actor.can_edit_pupils or actor.role in SEN_EDITORS or actor.role in SEND_EDITORS


def set_sen_status(pupil_id: int, status: str, *, actor: Principal) -> Pupil:
    """Change only the census SEN status (N / K / E). The SENCO may do this
    without being a pupil record editor; audited like any other update."""
    with _logged("pupil.sen_status", actor, target=_ref(pupil_id)):
        if not can_set_sen_status(actor):
            raise PermissionDenied("Only the SENCO or a pupil record editor can change "
                                   "the SEN status.")
        current = get_pupil(pupil_id)
        if current is None:
            raise NotFound(f"No pupil with id {pupil_id}")
        new = (_clean_text(status, 1) or "").upper()
        if new not in SEN_STATUSES:
            raise ValidationError(["SEN status must be N, K or E"])
        if new != current.sen_status:
            with database.connect() as conn:
                conn.execute("UPDATE pupils SET sen_status = ?, updated_at = datetime('now'), "
                             "updated_by = ? WHERE pupil_id = ?",
                             (new, actor.username, current.pupil_id))
                _audit(conn, current.pupil_id, "update", actor,
                       {"sen_status": {"from": current.sen_status, "to": new}})
    activity_log.record("pupil.sen_status", target=current.admission_no, principal=actor,
                        outcome="ok" if new != current.sen_status else "no_change")
    return get_pupil(current.pupil_id)  # type: ignore[return-value]


# ── Delete ───────────────────────────────────────────────────────────

def delete_pupil(pupil_id: int, *, actor: Principal, reason: str) -> Pupil:
    """Remove a record created in error. Returns what was removed.

    Pupils who leave should be marked as left instead (see
    :func:`update_pupil`), which keeps their history. A reason is required
    and a full copy of the record is kept in the audit trail.
    """
    with _logged("pupil.delete", actor, target=_ref(pupil_id)):
        removed = _delete(pupil_id, actor, reason)
    activity_log.record("pupil.delete", target=removed.admission_no, principal=actor)
    # Their login goes with the record (lazy import: pupil_accounts imports this module).
    from education_system.systems.secondary.modules.pupils.domain import pupil_accounts
    pupil_accounts.remove_for_pupil(removed.pupil_id, actor=actor)
    return removed


def _delete(pupil_id: int, actor: Principal, reason: str) -> Pupil:
    _require_editor(actor)
    reason = _clean_text(reason, 500) or ""
    if not reason:
        raise ValidationError(["A reason is required to delete a pupil record"])
    current = get_pupil(pupil_id)
    if current is None:
        raise NotFound(f"No pupil with id {pupil_id}")
    try:
        with database.connect() as conn:
            conn.execute("DELETE FROM pupils WHERE pupil_id = ?", (current.pupil_id,))
            _audit(conn, current.pupil_id, "delete", actor,
                   {"reason": reason, "record": asdict(current)})
    except database.IntegrityError:
        # Statutory records (attendance registers, safeguarding, medical,
        # exclusions ...) point at the pupil and must not go with it.
        raise ValidationError(["This pupil has statutory records (attendance or "
                               "safeguarding), which must be kept - mark them as left "
                               "instead of deleting the record"]) from None
    return current
