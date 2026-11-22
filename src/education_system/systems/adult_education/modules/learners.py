"""Learners: the record, emergency contacts, ID checks and prior qualifications.

Rules carried over from the old Adult Education Learners area:

* a learner reference ``AE`` + six digits is given automatically;
* names are letters, spaces, hyphens, apostrophes and full stops; e-mail,
  phone and UK postcode are checked (postcodes are tidied to ``AB1 2CD``);
* the ULN must pass its check digit and the NI number its format;
  ULN, NI number and e-mail are unique across learners;
* learners are 16 or over (adult education), and a second record with the
  same name and date of birth is refused as a likely duplicate;
* status only moves along :data:`STATUS_MOVES`; archiving keeps the previous
  status so a restore puts it back;
* an expired document can't be verified, a decided ID check can't be changed,
  and a rejection needs a reason.
"""

from __future__ import annotations

import re
from datetime import date

from education_system.systems.adult_education.core import dates
from education_system.systems.adult_education.core import records as r
from education_system.systems.adult_education.core.records import Field, RecordType, ValidationError
from education_system.systems.adult_education.infrastructure import database as db

GENDERS = ("Female", "Male", "Non-binary", "Other", "Prefer not to say")
TITLES = ("Mr", "Mrs", "Miss", "Ms", "Mx", "Dr", "Prof")
RELATIONSHIPS = ("Parent", "Carer", "Guardian", "Partner", "Spouse", "Sibling",
                 "Grandparent", "Other relative", "Friend", "Other")
STATUSES = ("Enquiry", "Active", "On a break", "Withdrawn", "Completed", "Archived")
#: Allowed status changes (Archived is reachable from any status; leaving it
#: restores the status it had before).
STATUS_MOVES = {
    "Enquiry": {"Active", "Withdrawn"},
    "Active": {"On a break", "Withdrawn", "Completed"},
    "On a break": {"Active", "Withdrawn"},
    "Withdrawn": {"Active"},
    "Completed": {"Active"},
    "Archived": set(),
}
EMPLOYMENT = ("Employed", "Self-employed", "Unemployed (looking for work)",
              "Not working and not looking", "Retired")
LEVELS = ("Entry 1", "Entry 2", "Entry 3", "Level 1", "Level 2", "Level 3", "Level 4",
          "Level 5", "Level 6", "Level 7", "Level 8")
LEVEL_RANK = {lv: i for i, lv in enumerate(LEVELS)}
ID_DOCUMENTS = ("Passport", "Photocard driving licence", "National identity card",
                "Biometric residence permit", "Birth certificate", "Utility bill",
                "Bank statement", "Council tax bill", "Benefit letter")
PHOTO_ID = frozenset(ID_DOCUMENTS[:4])
ADDRESS_PROOF = frozenset({"Utility bill", "Bank statement", "Council tax bill",
                           "Benefit letter", "Photocard driving licence"})

_NAME = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ' .\-]+$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^\+?[0-9 ()-]{7,20}$")
_POSTCODE = re.compile(r"^([A-Z]{1,2}\d[A-Z\d]?) ?(\d[A-Z]{2})$")
_ULN = re.compile(r"^\d{10}$")
_NI = re.compile(r"^(?!BG|GB|NK|KN|TN|NT|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z]\d{6}[A-D]$")
MIN_AGE, MAX_AGE = 16, 110


def _today() -> str:
    return date.today().isoformat()


# ── field checks (shared with other areas) ──────────────────────────

def check_email(values: dict, key: str = "email") -> None:
    if values.get(key):
        values[key] = values[key].strip().lower()
        if not _EMAIL.match(values[key]):
            raise ValidationError(f"'{values[key]}' isn't a valid e-mail address.")


def check_phone(values: dict, key: str = "phone") -> None:
    value = values.get(key)
    if value:
        digits = re.sub(r"\D", "", value)
        if not _PHONE.match(value) or not 10 <= len(digits) <= 13:
            raise ValidationError(f"'{value}' isn't a valid phone number.")


def check_postcode(values: dict, key: str = "postcode") -> None:
    value = values.get(key)
    if value:
        m = _POSTCODE.match(value.upper().replace("  ", " ").strip())
        if not m:
            raise ValidationError(f"'{value}' isn't a valid UK postcode.")
        values[key] = f"{m.group(1)} {m.group(2)}"


def uln_check_digit_ok(uln: str) -> bool:
    """Weighted sum of the first nine digits (weights 10..2) mod 11; 10 minus
    the remainder is the tenth digit (a remainder of 0 is invalid)."""
    digits = [int(c) for c in uln]
    remainder = sum(d * w for d, w in zip(digits[:9], range(10, 1, -1))) % 11
    return remainder != 0 and 10 - remainder == digits[9]


def _next_ref(conn) -> str:
    n = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM learners").fetchone()[0]
    while True:
        ref = f"AE{n:06d}"
        if conn.execute("SELECT 1 FROM learners WHERE learner_ref = ?", (ref,)).fetchone() is None:
            return ref
        n += 1


def _check_learner(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    for key, label in (("first_name", "First name"), ("last_name", "Last name"),
                       ("preferred_name", "Preferred name")):
        if values.get(key) and not _NAME.match(values[key]):
            raise ValidationError(f"{label} may contain only letters, spaces, hyphens, "
                                  "apostrophes and full stops.")
    check_email(values)
    check_phone(values)
    check_postcode(values)
    if values.get("uln"):
        values["uln"] = values["uln"].replace(" ", "")
        if not _ULN.match(values["uln"]) or not uln_check_digit_ok(values["uln"]):
            raise ValidationError("The ULN must be a valid 10-digit Unique Learner Number.")
    if values.get("ni_number"):
        values["ni_number"] = values["ni_number"].replace(" ", "").upper()
        if not _NI.match(values["ni_number"]):
            raise ValidationError("That isn't a valid National Insurance number "
                                  "(e.g. QQ123456C).")
    dob = r.to_date(r.parse_date(merged.get("dob")))
    if dob:
        age = dates.age_on(dob, date.today())
        if dob > date.today():
            raise ValidationError("Date of birth can't be in the future.")
        if age < MIN_AGE:
            raise ValidationError(f"That gives an age of {age}; adult education is for "
                                  f"learners aged {MIN_AGE} and over.")
        if age > MAX_AGE:
            raise ValidationError("That date of birth gives an age that isn't plausible.")
    own_id = (old or {}).get("id")
    with db.connect() as conn:
        for key, label in (("uln", "ULN"), ("ni_number", "NI number"), ("email", "e-mail")):
            if values.get(key):
                clash = conn.execute(f"SELECT learner_ref FROM learners WHERE {key} = ? "
                                     "COLLATE NOCASE AND id IS NOT ?",
                                     (values[key], own_id)).fetchone()
                if clash:
                    raise ValidationError(f"That {label} is already on learner {clash[0]}.")
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
    new, was = values.get("status"), (old or {}).get("status")
    if old is None and new not in (None, "Enquiry", "Active"):
        raise ValidationError("A new learner starts as an Enquiry or Active.")
    if old is not None and new and new != was:
        if new == "Archived":
            values["status_before_archive"] = was
        elif was == "Archived":
            if new != old.get("status_before_archive"):
                raise ValidationError(f"Restoring puts the record back to "
                                      f"'{old.get('status_before_archive') or 'Enquiry'}'.")
        elif new not in STATUS_MOVES.get(was, set()):
            raise ValidationError(f"A learner can't go from {was} to {new}.")


def platform_hook(name: str):
    """An ``after_commit`` hook from ``infrastructure.platform_link`` (loaded
    on first save, so the record types don't import the platform)."""
    def hook(row: dict, old: dict | None):
        from education_system.systems.adult_education.infrastructure import platform_link
        return getattr(platform_link, name)(row, old)
    hook.__name__ = name
    return hook


def learner_label(row: dict) -> str:
    return (f"{row.get('last_name', '')}, {row.get('preferred_name') or row.get('first_name', '')}"
            f" ({row.get('learner_ref') or 'new'})")


LEARNERS = RecordType(
    key="learners", title="Learner Directory", singular="learner",
    order_by="last_name, first_name", check=_check_learner, describe=learner_label,
    filters=("status", "employment_status"),
    fields=(
        Field("learner_ref", "Ref", form=False),
        Field("title", "Title", "choice", TITLES, listed=False),
        Field("first_name", "First name", required=True),
        Field("last_name", "Last name", required=True),
        Field("preferred_name", "Preferred name", listed=False),
        Field("dob", "Date of birth", "date", required=True),
        Field("gender", "Gender", "choice", GENDERS, required=True, listed=False),
        Field("email", "E-mail"),
        Field("phone", "Phone"),
        Field("address_line1", "Address", listed=False),
        Field("address_line2", "Address line 2", listed=False),
        Field("town", "Town", listed=False),
        Field("postcode", "Postcode"),
        Field("uln", "ULN", listed=False, help="Unique Learner Number, 10 digits"),
        Field("ni_number", "NI number", listed=False),
        Field("employment_status", "Employment", "choice", EMPLOYMENT),
        Field("has_learning_difficulty", "Learning difficulty / disability", "bool",
              listed=False),
        Field("support_needs", "Support needs", "long", listed=False),
        Field("contact_by_email", "Contact by e-mail", "bool", default=1, listed=False),
        Field("contact_by_phone", "Contact by phone", "bool", default=1, listed=False),
        Field("contact_by_post", "Contact by post", "bool", default=1, listed=False),
        Field("contact_by_sms", "Contact by text", "bool", default=0, listed=False),
        Field("status", "Status", "choice", STATUSES, required=True, default="Enquiry"),
        Field("status_before_archive", "Status before archive", form=False, listed=False),
        Field("notes", "Notes", "long", listed=False),
        # Set by the platform for a learner FE College referred or who went on
        # to FE / university through it.
        Field("journey_id", "Platform journey", form=False, listed=False),
    ),
)


def _check_contact(values: dict, old: dict | None) -> None:
    check_email(values)
    check_phone(values)
    merged = {**(old or {}), **values}
    if not (merged.get("phone") or merged.get("email")):
        raise ValidationError("Give at least a phone number or an e-mail address.")


def _after_contact(conn, row: dict, _old: dict | None) -> None:
    if row.get("is_primary"):   # one main contact per learner
        conn.execute("UPDATE contacts SET is_primary = 0 WHERE learner_id = ? AND id <> ?",
                     (row["learner_id"], row["id"]))


CONTACTS = RecordType(
    key="contacts", title="Emergency Contacts", singular="contact",
    order_by="learner_id, is_primary DESC, name", check=_check_contact,
    after_save=_after_contact,
    describe=lambda row: f"{row.get('name')} ({row.get('relationship')})",
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("name", "Name", required=True),
        Field("relationship", "Relationship", "choice", RELATIONSHIPS, required=True),
        Field("phone", "Phone"),
        Field("email", "E-mail"),
        Field("is_emergency", "Emergency contact", "bool", default=1),
        Field("is_primary", "Main contact", "bool", default=0,
              help="Only one main contact per learner"),
        Field("notes", "Notes", "long", listed=False),
    ),
)


def _check_identity(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    was = (old or {}).get("status")
    new = merged.get("status")
    if was in ("Verified", "Rejected") and new != was:
        raise ValidationError(f"This check has already been {was.lower()}; record a new "
                              "check instead.")
    if values.get("reference_last4") and not re.fullmatch(r"[A-Za-z0-9]{1,4}",
                                                          values["reference_last4"]):
        raise ValidationError("Only keep the last 4 letters/digits of the document number.")
    expiry = r.to_date(r.parse_date(merged.get("expiry_date")))
    issued = r.to_date(r.parse_date(merged.get("issue_date")))
    if issued and expiry and expiry < issued:
        raise ValidationError("A document can't expire before it was issued.")
    if new == "Verified" and was != "Verified":
        if expiry and expiry < date.today():
            raise ValidationError("The document has expired, so it can't be verified. "
                                  "Ask for an in-date document.")
        values.setdefault("checked_on", _today())
    if new == "Rejected" and was != "Rejected":
        if not merged.get("rejection_reason"):
            raise ValidationError("Give the reason the document was rejected.")
        values.setdefault("checked_on", _today())


def _id_flag(row: dict) -> str:
    expiry = r.to_date(row.get("expiry_date"))
    if row.get("status") != "Verified" or not expiry:
        return ""
    days = (expiry - date.today()).days
    return "Expired - overdue" if days < 0 else (f"Expires in {days}d" if days <= 60 else "")


IDENTITY = RecordType(
    key="identity_checks", title="Identity Checks", singular="identity check",
    order_by="id DESC", check=_check_identity, filters=("document_type", "status"),
    computed=(("Expiry", _id_flag),),
    describe=lambda row: f"{row.get('document_type')} ({row.get('status')})",
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("document_type", "Document", "choice", ID_DOCUMENTS, required=True),
        Field("reference_last4", "Last 4 of number", listed=False,
              help="Never store the full document number"),
        Field("issuing_country", "Issued by", listed=False),
        Field("issue_date", "Issued", "date", listed=False),
        Field("expiry_date", "Expires", "date"),
        Field("status", "Status", "choice", ("Pending", "Verified", "Rejected"),
              required=True, default="Pending"),
        Field("checked_by", "Checked by"),
        Field("checked_on", "Checked on", "date"),
        Field("rejection_reason", "Rejection reason", listed=False),
    ),
)


def identity_status(learner_id: int) -> dict:
    """Has the learner a verified, in-date photo ID and proof of address?"""
    rows = r.list_records(IDENTITY, learner_id=learner_id, equals={"status": "Verified"})
    good = [x for x in rows if not (x.get("expiry_date") and
                                    date.fromisoformat(x["expiry_date"]) < date.today())]
    return {"photo_id": any(x["document_type"] in PHOTO_ID for x in good),
            "address": any(x["document_type"] in ADDRESS_PROOF for x in good)}


PASS_GRADES = {"4", "5", "6", "7", "8", "9", "A*", "A", "B", "C", "PASS", "MERIT",
               "DISTINCTION"}


def _check_qualification(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    got = r.to_date(r.parse_date(merged.get("date_achieved")))
    if got and got > date.today():
        raise ValidationError("Date achieved can't be in the future.")


PRIOR = RecordType(
    key="prior_qualifications", title="Prior Qualifications", singular="qualification",
    order_by="learner_id, date_achieved DESC", check=_check_qualification,
    filters=("level", "evidence_status"),
    describe=lambda row: f"{row.get('title')} ({row.get('level')})",
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("title", "Qualification", required=True, help="e.g. GCSE English Language"),
        Field("level", "Level", "choice", LEVELS, required=True),
        Field("subject", "Subject"),
        Field("awarding_body", "Awarding body", listed=False),
        Field("date_achieved", "Achieved", "date"),
        Field("grade", "Grade"),
        Field("is_full_level", "Full level", "bool",
              help="A full Level 2/3 (e.g. 5 GCSEs, an A-level pair) for funding rules"),
        Field("evidence_status", "Evidence", "choice", ("Not checked", "Verified", "Rejected"),
              required=True, default="Not checked"),
    ),
)


def prior_summary(learner_id: int) -> dict:
    """Highest level held and GCSE English/maths (rejected evidence doesn't count)."""
    rows = [q for q in r.list_records(PRIOR, learner_id=learner_id)
            if q.get("evidence_status") != "Rejected"]

    def held(words: tuple[str, ...]) -> bool:
        return any(any(w in f"{q.get('subject') or ''} {q['title']}".lower() for w in words)
                   and LEVEL_RANK.get(q["level"], -1) >= LEVEL_RANK["Level 2"]
                   and (not q.get("grade") or q["grade"].strip().upper() in PASS_GRADES)
                   for q in rows)

    highest = max(rows, key=lambda q: LEVEL_RANK.get(q["level"], -1), default=None)
    return {"highest_level": highest["level"] if highest else None,
            "gcse_english": held(("english",)), "gcse_maths": held(("math", "numeracy"))}


def active_learners() -> list[dict]:
    return [x for x in r.list_records(LEARNERS) if x["status"] != "Archived"]


def learner_options(include_archived: bool = False) -> list[tuple[int, str]]:
    rows = r.list_records(LEARNERS) if include_archived else active_learners()
    return [(row["id"], learner_label(row)) for row in rows]


def set_status(conn, learner_id: int, status: str, *, only_if: str) -> None:
    """Knock-on status change from another area (inside its transaction)."""
    conn.execute("UPDATE learners SET status = ?, updated_at = datetime('now') "
                 "WHERE id = ? AND status = ?", (status, learner_id, only_if))
