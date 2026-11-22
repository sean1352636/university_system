"""Children and young people known to the authority, and their parents and
carers. (The table is named ``learners`` because the record kit joins on it.)

Rules:

* a reference ``LA`` + six digits is given automatically;
* ages 0-25 (SEND duties run to 25); the date of birth is required, and a
  second record with the same name and date of birth is refused as a likely
  duplicate;
* the UPN (when known) must pass the DfE check letter;
* a child recorded as at school, in alternative provision or an early years
  setting names that setting; the national curriculum year is worked out
  from the date of birth, never typed;
* archiving keeps the record.

Parents/carers: one main contact per child, who must be reachable and can't
be someone the child must not be released to.
"""

from __future__ import annotations

import re
from datetime import date

from education_system.systems.local_authority.core import dates
from education_system.systems.local_authority.core import records as r
from education_system.systems.local_authority.core.records import (
    Field,
    RecordType,
    ValidationError,
)
from education_system.systems.local_authority.infrastructure import database as db

STATUSES = ("Resident", "Moved out of area", "Archived")
EDUCATION = ("At school", "Early years setting", "Alternative provision",
             "Elective home education", "Not in education", "Post-16 / college",
             "Not yet school age")
NEEDS_SETTING = frozenset({"At school", "Early years setting", "Alternative provision"})
SEN_STATUSES = ("No SEN", "SEN Support", "EHC needs assessment", "EHC plan")
SOCIAL_CARE = ("None known", "Early help", "Child in need", "Child protection plan",
               "Looked after")
RELATIONSHIPS = ("Mother", "Father", "Step-parent", "Foster carer", "Kinship carer",
                 "Grandparent", "Sibling", "Other relative", "Social worker", "Other")
MAX_AGE = 25
#: Compulsory school age: from the term after the 5th birthday to the last
#: Friday in June of the school year the child turns 16 (approximated here
#: by the school year: Reception's summer term to Year 11).
CSA_YEARS = frozenset({"Year " + str(n) for n in range(1, 12)})

_NAME = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ' .\-]+$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^\+?[0-9 ()-]{7,20}$")
_POSTCODE = re.compile(r"^([A-Z]{1,2}\d[A-Z\d]?) ?(\d[A-Z]{2})$")
_UPN = re.compile(r"^[A-Z]\d{11}[0-9A-Z]$")
_UPN_LETTERS = "ABCDEFGHJKLMNPQRTUVWXYZ"   # check letters (no I, O, S)


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


def year_group(dob: date | None, on: date | None = None) -> str:
    """The National Curriculum year for a child born on *dob* in the school
    year containing *on* (age on the 31 August before it: 4 = Reception)."""
    if dob is None:
        return ""
    on = on or date.today()
    age = dates.age_on(dob, date(dates.school_year_start(on).year, 8, 31))
    if age < 4:
        return "Pre-school"
    if age == 4:
        return "Reception"
    return f"Year {age - 4}" if age <= 17 else "Post-18"


def compulsory_school_age(row: dict, on: date | None = None) -> bool:
    return year_group(r.to_date(row.get("dob")), on) in CSA_YEARS


def _next_ref(conn) -> str:
    n = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM learners").fetchone()[0]
    while True:
        ref = f"LA{n:06d}"
        if conn.execute("SELECT 1 FROM learners WHERE child_ref = ?", (ref,)).fetchone() is None:
            return ref
        n += 1


def _check_child(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    for key, label in (("first_name", "First name"), ("last_name", "Last name"),
                       ("preferred_name", "Preferred name")):
        if values.get(key) and not _NAME.match(values[key]):
            raise ValidationError(f"{label} may contain only letters, spaces, hyphens, "
                                  "apostrophes and full stops.")
    check_postcode(values)
    if values.get("upn"):
        values["upn"] = values["upn"].upper().replace(" ", "")
        if not upn_ok(values["upn"]):
            raise ValidationError("The UPN must be 13 characters with a valid check letter.")
    dob = r.to_date(merged.get("dob"))
    if dob is None:
        raise ValidationError("Date of birth is required.")
    if dob > date.today():
        raise ValidationError("Date of birth can't be in the future.")
    if dates.age_on(dob, date.today()) > MAX_AGE:
        raise ValidationError(f"The authority's education duties run to age {MAX_AGE}.")
    if merged.get("education") in NEEDS_SETTING and not merged.get("school_id"):
        raise ValidationError(f"{merged['education']}: choose the school or setting.")
    if merged.get("education") in ("Elective home education", "Not in education",
                                   "Not yet school age"):
        values["school_id"] = None
    own_id = (old or {}).get("id")
    with db.connect() as conn:
        if any(k in values for k in ("first_name", "last_name", "dob")):
            dupe = conn.execute(
                "SELECT child_ref FROM learners WHERE first_name = ? COLLATE NOCASE AND "
                "last_name = ? COLLATE NOCASE AND dob = ? AND id IS NOT ?",
                (merged.get("first_name"), merged.get("last_name"), dob.isoformat(),
                 own_id)).fetchone()
            if dupe:
                raise ValidationError("A child with the same name and date of birth is "
                                      f"already on record ({dupe[0]}). Check it isn't the "
                                      "same child.")
        if values.get("upn"):
            clash = conn.execute("SELECT child_ref FROM learners WHERE upn = ? AND id IS NOT ?",
                                 (values["upn"], own_id)).fetchone()
            if clash:
                raise ValidationError(f"That UPN is already on child {clash[0]}.")
        if old is None:
            values["child_ref"] = _next_ref(conn)


def platform_hook(name: str):
    """An ``after_commit`` hook from ``infrastructure.platform_link`` (loaded
    on first save, so the record types don't import the platform)."""
    def hook(row: dict, old: dict | None):
        from education_system.systems.local_authority.infrastructure import platform_link
        return getattr(platform_link, name)(row, old)
    hook.__name__ = name
    return hook


def child_label(row: dict) -> str:
    return (f"{row.get('last_name', '')}, {row.get('first_name', '')}"
            f" ({row.get('child_ref') or '?'})")


learner_label = child_label   # the record kit's name for it


CHILDREN = RecordType(
    key="learners", title="Children & Young People", singular="child",
    order_by="last_name, first_name", check=_check_child,
    filters=("education", "sen_status", "status"), describe=child_label,
    computed=(("Year", lambda row: year_group(r.to_date(row.get("dob")))),),
    fields=(
        Field("child_ref", "Ref", form=False),
        Field("first_name", "First name", required=True),
        Field("last_name", "Last name", required=True),
        Field("preferred_name", "Preferred name", listed=False),
        Field("dob", "Date of birth", "date", required=True),
        Field("gender", "Gender", "choice", ("Female", "Male", "Other / not given"),
              listed=False),
        Field("upn", "UPN", listed=False),
        Field("education", "Education", "choice", EDUCATION, required=True,
              default="At school"),
        Field("school_id", "School / setting", "ref", ref="schools", on_delete="SET NULL"),
        Field("sen_status", "SEN", "choice", SEN_STATUSES, required=True, default="No SEN"),
        Field("social_care", "Social care", "choice", SOCIAL_CARE, default="None known",
              listed=False),
        Field("free_school_meals", "Free school meals", "bool", listed=False),
        Field("eal", "English as an additional language", "bool", listed=False),
        Field("address_line1", "Address", listed=False),
        Field("town", "Town", listed=False),
        Field("postcode", "Postcode"),
        Field("status", "Status", "choice", STATUSES, required=True, default="Resident"),
        Field("notes", "Notes", "long", listed=False),
        Field("journey_id", "Platform journey", form=False, listed=False),
    ),
)
LEARNERS = CHILDREN   # the record kit's name for it


def _check_contact(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    check_email(values)
    check_phone(values)
    check_postcode(values)
    if merged.get("is_primary") and merged.get("no_contact"):
        raise ValidationError("Someone the child must not be released to can't be the main "
                              "contact.")
    if merged.get("is_primary") and not (merged.get("phone") or merged.get("email")):
        raise ValidationError("The main contact needs a phone number or an e-mail address.")


def _after_contact(conn, row: dict, _old: dict | None) -> None:
    if row.get("is_primary"):   # only one main contact per child
        conn.execute("UPDATE contacts SET is_primary = 0, updated_at = datetime('now') "
                     "WHERE learner_id = ? AND id != ? AND is_primary = 1",
                     (row["learner_id"], row["id"]))


CONTACTS = RecordType(
    key="contacts", title="Parents & Carers", singular="contact",
    order_by="learner_id, is_primary DESC, name", check=_check_contact,
    after_save=_after_contact,
    describe=lambda row: f"{row.get('name')} ({row.get('relationship')})",
    fields=(
        Field("learner_id", "Child", "learner", required=True),
        Field("name", "Name", required=True),
        Field("relationship", "Relationship", "choice", RELATIONSHIPS, required=True),
        Field("parental_responsibility", "Parental responsibility", "bool", default=1),
        Field("phone", "Phone"),
        Field("email", "E-mail"),
        Field("address_line1", "Address", listed=False,
              help="If different from the child's"),
        Field("postcode", "Postcode", listed=False),
        Field("is_primary", "Main contact", "bool", default=0,
              help="Only one main contact per child"),
        Field("no_contact", "Must NOT be released to / contacted", "bool", default=0,
              help="e.g. a court order - record the details in the notes"),
        Field("notes", "Notes", "long", listed=False),
    ),
)


def active_learners() -> list[dict]:
    return [c for c in r.list_records(CHILDREN) if c["status"] != "Archived"]


def learner_options(include_archived: bool = False) -> list[tuple[int, str]]:
    rows = r.list_records(CHILDREN) if include_archived else active_learners()
    return [(row["id"], child_label(row)) for row in rows]


def main_contact(child_id: int) -> dict | None:
    rows = r.list_records(CONTACTS, learner_id=child_id)
    return next((c for c in rows if c.get("is_primary")), None)


def child_name(child_id: int | None) -> str:
    row = r.get(CHILDREN, child_id) if child_id else None
    return f"{row['first_name']} {row['last_name']}" if row else "Child"
