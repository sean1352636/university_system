"""Pupils: the record on the AP roll, and their parents, carers and contacts.

The table is called ``learners`` because the record kit joins every pupil-owned
record to it; everything a user sees says "pupil".

Rules:

* a pupil reference ``AP`` + six digits is given automatically;
* pupils are 4 to 19; a second record with the same name and date of birth is
  refused as a likely duplicate;
* the UPN is the DfE 13-character Unique Pupil Number: its check letter is
  verified (a temporary UPN, ending in a letter, is accepted as it is) and it
  is unique;
* the year group may be at most one year away from the pupil's age group
  (pupils in AP are sometimes taught out of year);
* status only moves along :data:`STATUS_MOVES`; a pupil with an active
  placement can't be marked as having left; leaving sets a leaving date;
  archiving keeps the previous status so a restore puts it back;
* one main contact per pupil, and a person the pupil must not be released to
  can't be the main contact.
"""

from __future__ import annotations

import re
from datetime import date

from education_system.systems.alternative_provision.core import dates
from education_system.systems.alternative_provision.core import records as r
from education_system.systems.alternative_provision.core.records import (
    Field,
    RecordType,
    ValidationError,
)
from education_system.systems.alternative_provision.infrastructure import database as db

GENDERS = ("Female", "Male", "Non-binary", "Other", "Prefer not to say")
YEAR_GROUPS = ("Reception",) + tuple(f"Year {n}" for n in range(1, 14))
SEN_STATUSES = ("No SEN", "SEN Support", "EHC plan", "EHC needs assessment")
SOCIAL_CARE = ("None known", "Early help", "Child in need", "Child protection plan")
REGISTRATION = ("Sole registration (on our roll)", "Dual registration (main roll elsewhere)")
STATUSES = ("Referred", "On roll", "Reintegrated", "Left", "Archived")
#: Allowed status changes (Archived is reachable from any status; leaving it
#: restores the status it had before).
STATUS_MOVES = {
    "Referred": {"On roll", "Left"},
    "On roll": {"Reintegrated", "Left"},
    "Reintegrated": {"On roll", "Left"},   # a reintegration that breaks down
    "Left": {"On roll"},
    "Archived": set(),
}
LEAVING_STATUSES = frozenset({"Reintegrated", "Left"})
RELATIONSHIPS = ("Mother", "Father", "Step-parent", "Foster carer", "Kinship carer",
                 "Grandparent", "Sibling", "Other relative", "Social worker",
                 "Residential key worker", "Other")

_NAME = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ' .\-]+$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^\+?[0-9 ()-]{7,20}$")
_POSTCODE = re.compile(r"^([A-Z]{1,2}\d[A-Z\d]?) ?(\d[A-Z]{2})$")
_UPN = re.compile(r"^[A-Z]\d{11}[0-9A-Z]$")
_UPN_LETTERS = "ABCDEFGHJKLMNPQRTUVWXYZ"   # check letters (no I, O, S)
MIN_AGE, MAX_AGE = 4, 19


def _today() -> str:
    return date.today().isoformat()


# ── field checks (shared with other areas) ──────────────────────────

def check_email(values: dict, key: str = "email") -> None:
    if values.get(key):
        values[key] = values[key].lower()
        if not _EMAIL.match(values[key]):
            raise ValidationError("That e-mail address doesn't look right.")


def check_phone(values: dict, key: str = "phone") -> None:
    if values.get(key) and not _PHONE.match(values[key]):
        raise ValidationError("A phone number is 7-20 digits (spaces, brackets, + and - "
                              "allowed).")


def check_postcode(values: dict, key: str = "postcode") -> None:
    if values.get(key):
        m = _POSTCODE.match(values[key].upper().replace(" ", ""))
        if not m:
            raise ValidationError("That isn't a UK postcode (e.g. SW1A 1AA).")
        values[key] = f"{m.group(1)} {m.group(2)}"


def upn_ok(upn: str) -> bool:
    """DfE UPN: check letter, then 12 characters. Digits 2-13 are weighted
    2-13, summed, and the remainder mod 23 picks the check letter. A temporary
    UPN (13th character a letter) has no check letter to verify."""
    if not _UPN.match(upn):
        return False
    if upn[-1].isalpha():
        return True
    total = sum(int(ch) * weight for weight, ch in enumerate(upn[1:], start=2))
    return _UPN_LETTERS[total % 23] == upn[0]


def year_group_for(dob: date, on: date) -> str:
    """The National Curriculum year for a child born on *dob*, in the school
    year containing *on* (age on the 31 August before it: 4 = Reception)."""
    year_start = on.year if on.month >= 9 else on.year - 1
    age = dates.age_on(dob, date(year_start, 8, 31))
    n = age - 4
    if n <= 0:
        return "Reception"
    return f"Year {min(n, 13)}"


def _year_index(year: str) -> int:
    return 0 if year == "Reception" else int(year.split()[1])


def _next_ref(conn) -> str:
    n = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM learners").fetchone()[0]
    while True:
        ref = f"AP{n:06d}"
        if conn.execute("SELECT 1 FROM learners WHERE pupil_ref = ?", (ref,)).fetchone() is None:
            return ref
        n += 1


def _check_pupil(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    for key, label in (("first_name", "First name"), ("last_name", "Last name"),
                       ("preferred_name", "Preferred name")):
        if values.get(key) and not _NAME.match(values[key]):
            raise ValidationError(f"{label} may contain only letters, spaces, hyphens, "
                                  "apostrophes and full stops.")
    check_postcode(values)
    if values.get("upn"):
        values["upn"] = values["upn"].replace(" ", "").upper()
        if not upn_ok(values["upn"]):
            raise ValidationError("That isn't a valid UPN: 13 characters, a check letter "
                                  "then 12 digits (a temporary UPN ends in a letter).")
    dob = r.to_date(r.parse_date(merged.get("dob")))
    if dob:
        if dob > date.today():
            raise ValidationError("Date of birth can't be in the future.")
        age = dates.age_on(dob, date.today())
        if not MIN_AGE <= age <= MAX_AGE:
            raise ValidationError(f"That gives an age of {age}; the AP roll is for pupils "
                                  f"aged {MIN_AGE} to {MAX_AGE}.")
        year = merged.get("year_group")
        if year and ("dob" in values or "year_group" in values):
            expected = year_group_for(dob, date.today())
            if abs(_year_index(year) - _year_index(expected)) > 1:
                raise ValidationError(f"{year} doesn't fit that date of birth (age group "
                                      f"{expected}). A pupil can be at most one year out of "
                                      "their age group.")
    own_id = (old or {}).get("id")
    with db.connect() as conn:
        if values.get("upn"):
            clash = conn.execute("SELECT pupil_ref FROM learners WHERE upn = ? AND id IS NOT ?",
                                 (values["upn"], own_id)).fetchone()
            if clash:
                raise ValidationError(f"That UPN is already on pupil {clash[0]}.")
        if any(k in values for k in ("first_name", "last_name", "dob")) and dob:
            dupe = conn.execute(
                "SELECT pupil_ref FROM learners WHERE first_name = ? COLLATE NOCASE AND "
                "last_name = ? COLLATE NOCASE AND dob = ? AND id IS NOT ?",
                (merged.get("first_name"), merged.get("last_name"), dob.isoformat(),
                 own_id)).fetchone()
            if dupe:
                raise ValidationError(f"A pupil with the same name and date of birth is "
                                      f"already on record ({dupe[0]}). Check it isn't the "
                                      "same child.")
        if old is None:
            values["pupil_ref"] = _next_ref(conn)
    new, was = values.get("status"), (old or {}).get("status")
    if old is None and new not in (None, "Referred", "On roll"):
        raise ValidationError("A new pupil starts as Referred or On roll.")
    if old is not None and new and new != was:
        if new == "Archived":
            values["status_before_archive"] = was
        elif was == "Archived":
            if new != old.get("status_before_archive"):
                raise ValidationError(f"Restoring puts the record back to "
                                      f"'{old.get('status_before_archive') or 'Referred'}'.")
        elif new not in STATUS_MOVES.get(was, set()):
            raise ValidationError(f"A pupil can't go from {was} to {new}.")
        if new in LEAVING_STATUSES:
            with db.connect() as conn:
                live = conn.execute("SELECT COUNT(*) FROM placements WHERE learner_id = ? AND "
                                    "status = 'Active'", (old["id"],)).fetchone()[0]
            if live:
                raise ValidationError(f"End the pupil's active placement{'s' if live > 1 else ''}"
                                      " first (a completed reintegration plan does this).")
        if new in LEAVING_STATUSES and not merged.get("leave_date"):
            values["leave_date"] = _today()
        if new == "On roll" and was in LEAVING_STATUSES:
            values["leave_date"] = None
        if new == "On roll" and not merged.get("start_date"):
            values["start_date"] = _today()
    start, left = r.to_date(merged.get("start_date")), r.to_date(values.get("leave_date",
                                                                         merged.get("leave_date")))
    if start and left and left < start:
        raise ValidationError("The leaving date can't be before the start date.")


def platform_hook(name: str):
    """A hook from infrastructure.platform_link (imported late: it reaches the
    platform's transfer queue, which this module must not load at import)."""
    def hook(row: dict, old: dict | None) -> list[str] | None:
        from education_system.systems.alternative_provision.infrastructure import platform_link
        return getattr(platform_link, name)(row, old)
    return hook


def pupil_label(row: dict) -> str:
    return (f"{row.get('last_name', '')}, {row.get('preferred_name') or row.get('first_name', '')}"
            f" ({row.get('pupil_ref') or 'new'})")


#: Kept under this name: the shared kit, reports and pages call it.
learner_label = pupil_label


LEARNERS = RecordType(
    key="learners", title="Pupil Directory", singular="pupil",
    order_by="last_name, first_name", check=_check_pupil, describe=pupil_label,
    after_commit=platform_hook("pupil_saved"),
    filters=("status", "year_group", "sen_status"),
    fields=(
        Field("pupil_ref", "Ref", form=False),
        Field("first_name", "First name", required=True),
        Field("last_name", "Last name", required=True),
        Field("preferred_name", "Preferred name", listed=False),
        Field("dob", "Date of birth", "date", required=True),
        Field("gender", "Gender", "choice", GENDERS, required=True, listed=False),
        Field("upn", "UPN", listed=False, help="Unique Pupil Number, 13 characters"),
        Field("year_group", "Year", "choice", YEAR_GROUPS, required=True),
        Field("home_school", "Home / main school",
              help="The mainstream school the pupil came from or is dual registered with"),
        Field("local_authority", "Local authority", listed=False),
        Field("registration", "Registration", "choice", REGISTRATION, listed=False,
              default=REGISTRATION[0]),
        Field("sen_status", "SEN", "choice", SEN_STATUSES, required=True, default="No SEN"),
        Field("looked_after", "Looked after (CLA)", "bool", listed=False),
        Field("social_care", "Social care", "choice", SOCIAL_CARE, default="None known",
              listed=False),
        Field("pupil_premium", "Pupil premium", "bool", listed=False),
        Field("free_school_meals", "Free school meals", "bool", listed=False),
        Field("eal", "English as an additional language", "bool", listed=False),
        Field("medical_notes", "Medical needs / alerts", "long", listed=False),
        Field("key_worker", "Key worker"),
        Field("address_line1", "Address", listed=False),
        Field("town", "Town", listed=False),
        Field("postcode", "Postcode", listed=False),
        Field("start_date", "Started", "date", listed=False),
        Field("leave_date", "Left", "date", listed=False),
        Field("status", "Status", "choice", STATUSES, required=True, default="Referred"),
        Field("status_before_archive", "Status before archive", form=False, listed=False),
        Field("notes", "Notes", "long", listed=False),
        # Set when a linked school referred the pupil (platform learner journey).
        Field("journey_id", "Platform journey", form=False, listed=False),
    ),
)


def _check_contact(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    check_email(values)
    check_phone(values)
    if merged.get("is_primary") and merged.get("no_contact"):
        raise ValidationError("Someone the pupil must not be released to can't be the main "
                              "contact.")
    if merged.get("is_primary") and not (merged.get("phone") or merged.get("email")):
        raise ValidationError("The main contact needs a phone number or an e-mail address.")


def _after_contact(conn, row: dict, _old: dict | None) -> None:
    if row.get("is_primary"):   # only one main contact per pupil
        conn.execute("UPDATE contacts SET is_primary = 0, updated_at = datetime('now') "
                     "WHERE learner_id = ? AND id != ? AND is_primary = 1",
                     (row["learner_id"], row["id"]))


CONTACTS = RecordType(
    key="contacts", title="Parents, Carers & Contacts", singular="contact",
    order_by="learner_id, is_primary DESC, name", check=_check_contact,
    after_save=_after_contact,
    describe=lambda row: f"{row.get('name')} ({row.get('relationship')})",
    fields=(
        Field("learner_id", "Pupil", "learner", required=True),
        Field("name", "Name", required=True),
        Field("relationship", "Relationship", "choice", RELATIONSHIPS, required=True),
        Field("parental_responsibility", "Parental responsibility", "bool", default=1),
        Field("phone", "Phone"),
        Field("email", "E-mail"),
        Field("lives_with", "Pupil lives with them", "bool", listed=False),
        Field("is_primary", "Main contact", "bool", default=0,
              help="Only one main contact per pupil"),
        Field("no_contact", "Must NOT be released to / contacted", "bool", default=0,
              help="e.g. a court order - record the details in the notes"),
        Field("notes", "Notes", "long", listed=False),
    ),
)


def active_learners() -> list[dict]:
    return [x for x in r.list_records(LEARNERS) if x["status"] != "Archived"]


def on_roll() -> list[dict]:
    return r.list_records(LEARNERS, equals={"status": "On roll"})


def learner_options(include_archived: bool = False) -> list[tuple[int, str]]:
    rows = r.list_records(LEARNERS) if include_archived else active_learners()
    return [(row["id"], pupil_label(row)) for row in rows]


def set_status(conn, learner_id: int, status: str, *, only_if: str | tuple[str, ...],
               on: str | None = None, actor: str = "system", why: str = "") -> bool:
    """Move a pupil's status inside another save's transaction (and log it).

    *on* (ISO date, default today) is when it happened: going on roll moves
    the start date back to it if needed; leaving sets the leaving date to it.
    """
    allowed = (only_if,) if isinstance(only_if, str) else only_if
    marks = ", ".join("?" for _ in allowed)
    when = on or _today()
    extra, extra_args = "", []
    if status in LEAVING_STATUSES:
        extra, extra_args = ", leave_date = ?", [when]
    elif status == "On roll":
        extra = (", start_date = CASE WHEN start_date IS NULL OR start_date > ? THEN ? "
                 "ELSE start_date END, leave_date = NULL")
        extra_args = [when, when]
    cur = conn.execute(f"UPDATE learners SET status = ?{extra}, updated_at = datetime('now') "
                       f"WHERE id = ? AND status IN ({marks})",
                       (status, *extra_args, learner_id, *allowed))
    if cur.rowcount:
        conn.execute("INSERT INTO history (actor, record_type, record_id, learner_id, action, "
                     "summary) VALUES (?, 'learners', ?, ?, 'updated', ?)",
                     (actor, learner_id, learner_id,
                      f"Status set to {status}{(' - ' + why) if why else ''}"))
    return bool(cur.rowcount)


def main_contact(learner_id: int) -> dict | None:
    rows = r.list_records(CONTACTS, learner_id=learner_id)
    return next((c for c in rows if c.get("is_primary")), None)
