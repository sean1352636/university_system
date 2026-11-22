"""The SEND register: learners, their contacts and the learner's own voice."""

from __future__ import annotations

import re
from datetime import date

from education_system.systems.special_education.core import records as r
from education_system.systems.special_education.core.records import Field, RecordType, ValidationError
from education_system.systems.special_education.infrastructure import database as db

SEN_STATUSES = ("SEN Support", "EHCP", "Monitoring", "No longer SEN")
#: DfE school census primary-need codes.
NEEDS = (
    "SpLD - Specific learning difficulty",
    "MLD - Moderate learning difficulty",
    "SLD - Severe learning difficulty",
    "PMLD - Profound & multiple learning difficulty",
    "SEMH - Social, emotional & mental health",
    "SLCN - Speech, language & communication needs",
    "HI - Hearing impairment",
    "VI - Visual impairment",
    "MSI - Multi-sensory impairment",
    "PD - Physical disability",
    "ASD - Autistic spectrum disorder",
    "OTH - Other difficulty/disability",
    "NSA - SEN support but no specialist assessment",
)
YEAR_GROUPS = ("Nursery", "Reception", *(f"Year {n}" for n in range(1, 15)), "Post-19")
_UPN = re.compile(r"^[A-Z][0-9]{11}[0-9A-Z]$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _today() -> str:
    return date.today().isoformat()


def platform_hook(name: str):
    """An ``after_commit`` hook from ``infrastructure.platform_link`` (loaded
    on first save, so the record types don't import the platform)."""
    def hook(row: dict, old: dict | None):
        from education_system.systems.special_education.infrastructure import platform_link
        return getattr(platform_link, name)(row, old)
    hook.__name__ = name
    return hook


def _check_learner(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    if values.get("upn"):
        values["upn"] = values["upn"].upper().replace(" ", "")
        if not _UPN.match(values["upn"]):
            raise ValidationError("A UPN is 13 characters: a letter, 11 digits, then a digit "
                                  "or letter (e.g. A123456789012).")
        with db.connect() as conn:
            clash = conn.execute("SELECT first_name || ' ' || last_name FROM learners "
                                 "WHERE upn = ? AND id IS NOT ?",
                                 (values["upn"], (old or {}).get("id"))).fetchone()
        if clash:
            raise ValidationError(f"UPN {values['upn']} already belongs to {clash[0]}.")
    dob = r.to_date(r.parse_date(merged.get("dob")))
    if dob and dob > date.today():
        raise ValidationError("Date of birth can't be in the future.")
    identified = r.to_date(r.parse_date(merged.get("date_identified")))
    if dob and identified and identified < dob:
        raise ValidationError("Date identified can't be before the date of birth.")
    if merged.get("secondary_need") and merged.get("secondary_need") == merged.get("primary_need"):
        raise ValidationError("Secondary need should differ from the primary need.")


LEARNERS = RecordType(
    key="learners", title="SEND Register", singular="learner",
    order_by="last_name, first_name",
    describe=lambda row: (f"{row.get('last_name', '')}, {row.get('first_name', '')}"
                          f"{' (' + row['year_group'] + ')' if row.get('year_group') else ''}"),
    check=_check_learner, after_commit=platform_hook("learner_saved"),
    filters=("sen_status", "primary_need", "year_group", "status"),
    fields=(
        Field("first_name", "First name", required=True),
        Field("last_name", "Last name", required=True),
        Field("preferred_name", "Preferred name", listed=False),
        Field("dob", "Date of birth", "date", required=True),
        Field("upn", "UPN", listed=False, help="Unique pupil number, if known"),
        Field("gender", "Gender", "choice", ("Female", "Male", "Other", "Not stated"),
              listed=False),
        Field("year_group", "Year group", "choice", YEAR_GROUPS),
        Field("setting", "School / setting"),
        Field("sen_status", "SEN status", "choice", SEN_STATUSES, required=True,
              default="SEN Support", help="Set to EHCP automatically when a final plan is issued"),
        Field("primary_need", "Primary need", "choice", NEEDS),
        Field("secondary_need", "Secondary need", "choice", NEEDS, listed=False),
        Field("key_worker", "Key worker"),
        Field("date_identified", "Date identified", "date", listed=False, default=_today),
        Field("status", "Record status", "choice", ("Active", "Archived"), required=True,
              default="Active", listed=False),
        Field("notes", "Notes", "long", listed=False),
        # Set by the platform when a linked school sends a request.
        Field("journey_id", "Platform journey", form=False, listed=False),
    ),
)


def _check_contact(values: dict, old: dict | None) -> None:
    email = values.get("email")
    if email and not _EMAIL.match(email):
        raise ValidationError(f"'{email}' doesn't look like an e-mail address.")
    merged = {**(old or {}), **values}
    if not (merged.get("phone") or merged.get("email")):
        raise ValidationError("Give at least a phone number or an e-mail address.")


CONTACTS = RecordType(
    key="contacts", title="Parents & Carers", singular="contact", order_by="learner_id, name",
    check=_check_contact, filters=("relationship",),
    describe=lambda row: f"{row.get('name')} ({row.get('relationship') or 'contact'})",
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("name", "Name", required=True),
        Field("relationship", "Relationship", "choice",
              ("Mother", "Father", "Carer", "Guardian", "Foster carer", "Grandparent",
               "Social worker", "Advocate", "Other"), required=True),
        Field("parental_responsibility", "Parental responsibility", "bool", default=1),
        Field("phone", "Phone"),
        Field("email", "E-mail"),
        Field("preferred_contact", "Prefers", "choice", ("Phone", "E-mail", "Letter", "Text")),
        Field("needs_interpreter", "Needs interpreter", "bool", listed=False),
        Field("notes", "Notes", "long", listed=False),
    ),
)

LEARNER_VOICE = RecordType(
    key="learner_voice", title="Learner Voice", singular="learner voice entry",
    order_by="recorded_on DESC, id DESC", filters=("method",),
    describe=lambda row: f"{row.get('learner_name', '')} {r.fmt(LEARNER_VOICE.fields[1], row.get('recorded_on'))}",
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("recorded_on", "Date", "date", required=True, default=_today),
        Field("method", "How captured", "choice",
              ("Conversation", "Questionnaire", "Symbols / drawing", "Observation",
               "Advocate", "Video / audio")),
        Field("views", "What the learner told us", "long", required=True),
        Field("aspirations", "Hopes & aspirations", "long"),
        Field("recorded_by", "Recorded by"),
    ),
)


def active_learners() -> list[dict]:
    return r.list_records(LEARNERS, equals={"status": "Active"})


def learner_options(include_archived: bool = False) -> list[tuple[int, str]]:
    rows = r.list_records(LEARNERS) if include_archived else active_learners()
    return [(row["id"], LEARNERS.label_for(row)) for row in rows]


def set_sen_status(conn, learner_id: int, status: str, *, only_if: str | None = None) -> None:
    """Knock-on update from another area (inside that area's transaction)."""
    sql = "UPDATE learners SET sen_status = ?, updated_at = datetime('now') WHERE id = ?"
    args: list = [status, learner_id]
    if only_if is not None:
        sql += " AND sen_status = ?"
        args.append(only_if)
    conn.execute(sql, args)
