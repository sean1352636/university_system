"""Learners (delegates): anyone booked onto a course, self-funded or sent by
an employer client.

Rules:

* a learner reference ``TP`` + six digits is given automatically;
* learners are 14 or over; e-mail, phone and UK postcode are checked;
* the e-mail is unique, and a second record with the same name and date of
  birth is refused as a likely duplicate;
* the ULN (optional, for accredited qualifications) must pass its check digit;
* archiving keeps the record; an archived learner can't be booked.
"""

from __future__ import annotations

import re
from datetime import date

from education_system.systems.training_provider.core import dates
from education_system.systems.training_provider.core import records as r
from education_system.systems.training_provider.core.records import (
    Field,
    RecordType,
    ValidationError,
)
from education_system.systems.training_provider.infrastructure import database as db

STATUSES = ("Active", "Archived")
FUNDING = ("Employer", "Self-funded", "Funded (grant / skills fund)")

_NAME = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ' .\-]+$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^\+?[0-9 ()-]{7,20}$")
_POSTCODE = re.compile(r"^([A-Z]{1,2}\d[A-Z\d]?) ?(\d[A-Z]{2})$")
_ULN = re.compile(r"^\d{10}$")
MIN_AGE = 14


def _today() -> str:
    return date.today().isoformat()


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


def uln_check_digit_ok(uln: str) -> bool:
    """ULN check digit: weights 10..2 over the first nine digits; 10 - (sum mod 11)."""
    if not _ULN.match(uln):
        return False
    total = sum(int(d) * w for d, w in zip(uln[:9], range(10, 1, -1)))
    check = 10 - (total % 11)
    return check != 10 and int(uln[9]) == check


def _next_ref(conn) -> str:
    n = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM learners").fetchone()[0]
    while True:
        ref = f"TP{n:06d}"
        if conn.execute("SELECT 1 FROM learners WHERE learner_ref = ?", (ref,)).fetchone() is None:
            return ref
        n += 1


def _check_learner(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    for key, label in (("first_name", "First name"), ("last_name", "Last name")):
        if values.get(key) and not _NAME.match(values[key]):
            raise ValidationError(f"{label} may contain only letters, spaces, hyphens, "
                                  "apostrophes and full stops.")
    check_email(values)
    check_phone(values)
    check_phone(values, "emergency_phone")
    check_postcode(values)
    if values.get("uln"):
        values["uln"] = values["uln"].replace(" ", "")
        if not uln_check_digit_ok(values["uln"]):
            raise ValidationError("The ULN must be a valid 10-digit Unique Learner Number.")
    dob = r.to_date(r.parse_date(merged.get("dob")))
    if dob:
        if dob > date.today():
            raise ValidationError("Date of birth can't be in the future.")
        age = dates.age_on(dob, date.today())
        if age < MIN_AGE:
            raise ValidationError(f"That gives an age of {age}; learners must be {MIN_AGE} or "
                                  "over.")
        if age > 110:
            raise ValidationError("That date of birth gives an age that isn't plausible.")
    if merged.get("funding") == "Employer" and not merged.get("client_id"):
        raise ValidationError("Choose the employer, or set funding to Self-funded.")
    own_id = (old or {}).get("id")
    with db.connect() as conn:
        if values.get("email"):
            clash = conn.execute("SELECT learner_ref FROM learners WHERE email = ? AND "
                                 "id IS NOT ?", (values["email"], own_id)).fetchone()
            if clash:
                raise ValidationError(f"That e-mail is already on learner {clash[0]}.")
        if any(k in values for k in ("first_name", "last_name", "dob")) and dob:
            dupe = conn.execute(
                "SELECT learner_ref FROM learners WHERE first_name = ? COLLATE NOCASE AND "
                "last_name = ? COLLATE NOCASE AND dob = ? AND id IS NOT ?",
                (merged.get("first_name"), merged.get("last_name"), dob.isoformat(),
                 own_id)).fetchone()
            if dupe:
                raise ValidationError(f"A learner with the same name and date of birth is "
                                      f"already on record ({dupe[0]}). Check it isn't the "
                                      "same person.")
        if old is None:
            values["learner_ref"] = _next_ref(conn)


def platform_hook(name: str):
    """An ``after_commit`` hook from ``infrastructure.platform_link`` (loaded
    on first save, so the record types don't import the platform)."""
    def hook(row: dict, old: dict | None):
        from education_system.systems.training_provider.infrastructure import platform_link
        return getattr(platform_link, name)(row, old)
    hook.__name__ = name
    return hook


def learner_label(row: dict) -> str:
    return (f"{row.get('last_name', '')}, {row.get('first_name', '')}"
            f" ({row.get('learner_ref') or 'new'})")


LEARNERS = RecordType(
    key="learners", title="Learner Directory", singular="learner",
    order_by="last_name, first_name", check=_check_learner, describe=learner_label,
    filters=("status", "funding"),
    fields=(
        Field("learner_ref", "Ref", form=False),
        Field("first_name", "First name", required=True),
        Field("last_name", "Last name", required=True),
        Field("dob", "Date of birth", "date", listed=False,
              help="Needed for accredited qualifications"),
        Field("email", "E-mail"),
        Field("phone", "Phone"),
        Field("funding", "Funding", "choice", FUNDING, required=True, default="Self-funded"),
        Field("client_id", "Employer", "ref", ref="clients", on_delete="SET NULL"),
        Field("job_title", "Job title", listed=False),
        Field("address_line1", "Address", listed=False),
        Field("town", "Town", listed=False),
        Field("postcode", "Postcode", listed=False),
        Field("uln", "ULN", listed=False, help="Unique Learner Number, 10 digits"),
        Field("support_needs", "Support needs / adjustments", "long", listed=False),
        Field("emergency_contact", "Emergency contact", listed=False),
        Field("emergency_phone", "Emergency phone", listed=False),
        Field("marketing_consent", "Happy to hear about courses", "bool", default=0,
              listed=False),
        Field("status", "Status", "choice", STATUSES, required=True, default="Active"),
        Field("notes", "Notes", "long", listed=False),
        # Set by the platform for a learner an apprenticeship provider or FE
        # college sent, or who went on to one through it.
        Field("journey_id", "Platform journey", form=False, listed=False),
    ),
)


def active_learners() -> list[dict]:
    return r.list_records(LEARNERS, equals={"status": "Active"})


def learner_options(include_archived: bool = False) -> list[tuple[int, str]]:
    rows = r.list_records(LEARNERS) if include_archived else active_learners()
    return [(row["id"], learner_label(row)) for row in rows]
