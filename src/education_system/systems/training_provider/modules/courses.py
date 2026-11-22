"""The course catalogue, trainers (and what they're approved to deliver), and venues.

Rules:

* course codes are unique and upper-cased; an accredited qualification
  names its awarding body; certificate validity is 0-120 months and the pass
  mark 0-100%;
* a trainer's DBS check is renewed every three years; a trainer approval
  (the awarding body / internal sign-off to deliver a course) can expire;
* venue capacity is at least 1.
"""

from __future__ import annotations

from datetime import date

from education_system.systems.training_provider.core import dates
from education_system.systems.training_provider.core import records as r
from education_system.systems.training_provider.core.records import (
    Field,
    RecordType,
    ValidationError,
)
from education_system.systems.training_provider.modules import learners

CATEGORIES = ("Health & safety", "First aid", "Fire safety", "Food safety",
              "Construction (CSCS / CITB)", "Security (SIA)", "Care & health",
              "IT & digital", "Management & leadership", "Customer service",
              "Education & training", "Other")
KINDS = ("Accredited qualification", "Non-accredited / CPD")
AWARDING_BODIES = ("City & Guilds", "Highfield", "NCFE", "Pearson", "Qualsafe", "QA Level",
                   "First Aid Awards", "CITB", "NEBOSH", "IOSH", "RSPH", "Other")
LEVELS = ("Entry", "Level 1", "Level 2", "Level 3", "Level 4", "Level 5", "Level 6",
          "Level 7", "Not levelled")
DELIVERY = ("Classroom", "Virtual classroom", "Blended", "E-learning", "On-site at client")
TRAINER_KINDS = ("Employed", "Associate / freelance")
DBS_YEARS = 3
VENUE_KINDS = ("Our training centre", "Client site", "Hired venue", "Online")


def _check_course(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    if values.get("code"):
        values["code"] = values["code"].upper().replace(" ", "")
    if merged.get("kind") == KINDS[0] and not merged.get("awarding_body"):
        raise ValidationError("An accredited qualification needs its awarding body.")
    months = merged.get("valid_months")
    if months is not None and not 0 <= int(months) <= 120:
        raise ValidationError("Certificate validity is 0-120 months (0 = doesn't expire).")
    mark = merged.get("pass_mark")
    if mark is not None and not 0 <= float(mark) <= 100:
        raise ValidationError("The pass mark is a percentage, 0-100.")
    if float(merged.get("duration_days") or 0) <= 0:
        raise ValidationError("Give the course length in days (halves allowed).")
    if merged.get("max_delegates") is not None and int(merged["max_delegates"]) < 1:
        raise ValidationError("A course takes at least one learner.")
    if merged.get("min_delegates") and merged.get("max_delegates") and \
            int(merged["min_delegates"]) > int(merged["max_delegates"]):
        raise ValidationError("The minimum can't be more than the maximum.")


def course_label(row: dict) -> str:
    return f"{row.get('code')} {row.get('title')}"


COURSES = RecordType(
    key="courses", title="Course Catalogue", singular="course", order_by="code",
    check=_check_course, filters=("category", "kind", "status"), describe=course_label,
    fields=(
        Field("code", "Code", required=True),
        Field("title", "Title", required=True),
        Field("category", "Category", "choice", CATEGORIES, required=True),
        Field("kind", "Type", "choice", KINDS, required=True, default=KINDS[1]),
        Field("awarding_body", "Awarding body", "choice", AWARDING_BODIES, listed=False),
        Field("level", "Level", "choice", LEVELS, default="Not levelled", listed=False),
        Field("delivery", "Delivery", "choice", DELIVERY, required=True, default="Classroom"),
        Field("duration_days", "Days", "number", required=True, default=1),
        Field("guided_hours", "Guided learning hours", "number", listed=False),
        Field("cpd_hours", "CPD hours", "number", listed=False),
        Field("min_delegates", "Min learners", "int", listed=False,
              help="Below this a session is flagged as under-booked"),
        Field("max_delegates", "Max learners", "int", required=True, default=12),
        Field("min_age", "Minimum age", "int", listed=False),
        Field("price", "Price per learner", "money", required=True),
        Field("pass_mark", "Pass mark %", "number", listed=False),
        Field("valid_months", "Certificate valid (months)", "int", default=0, listed=False,
              help="0 = doesn't expire; e.g. 36 for First Aid at Work"),
        Field("full_attendance", "Full attendance needed to pass", "bool", default=1,
              listed=False),
        Field("prerequisites", "Prerequisites", "long", listed=False),
        Field("description", "Description", "long", listed=False),
        Field("status", "Status", "choice", ("Active", "Retired"), required=True,
              default="Active"),
    ),
)


def _check_trainer(values: dict, old: dict | None) -> None:  # noqa: ARG001
    learners.check_email(values)
    learners.check_phone(values)
    dbs = r.to_date(values.get("dbs_date"))
    if dbs and dbs > date.today():
        raise ValidationError("The DBS check date can't be in the future.")


def dbs_due(row: dict) -> date | None:
    d = r.to_date(row.get("dbs_date"))
    return dates.add_months(d, 12 * DBS_YEARS) if d else None


def _dbs_flag(row: dict) -> str:
    due = dbs_due(row)
    if due is None:
        return "No DBS recorded"
    return dates.uk(due) + (" - OVERDUE" if due < date.today() else "")


TRAINERS = RecordType(
    key="trainers", title="Trainers", singular="trainer", order_by="name",
    check=_check_trainer, filters=("kind", "status"),
    describe=lambda row: row.get("name") or "trainer",
    computed=(("DBS renewal", _dbs_flag),),
    fields=(
        Field("name", "Name", required=True),
        Field("kind", "Contract", "choice", TRAINER_KINDS, required=True, default="Employed"),
        Field("email", "E-mail"),
        Field("phone", "Phone"),
        Field("day_rate", "Day rate", "money", listed=False,
              help="Associates: what we pay per delivery day"),
        Field("teaching_qualification", "Teaching qualification", listed=False,
              help="e.g. Level 3 Award in Education and Training"),
        Field("assessor_qualified", "Qualified assessor", "bool", listed=False),
        Field("iqa_qualified", "Qualified IQA", "bool", listed=False),
        Field("dbs_date", "DBS check", "date", listed=False),
        Field("status", "Status", "choice", ("Active", "Inactive"), required=True,
              default="Active"),
    ),
)


def _check_approval(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    on, until = r.to_date(merged.get("approved_on")), r.to_date(merged.get("expires_on"))
    if on and until and until <= on:
        raise ValidationError("An approval expires after it was given.")


def _approval_flag(row: dict) -> str:
    until = r.to_date(row.get("expires_on"))
    if until is None:
        return "No expiry"
    return dates.uk(until) + (" - EXPIRED" if until < date.today() else "")


APPROVALS = RecordType(
    key="trainer_approvals", title="Trainer Approvals", singular="trainer approval",
    order_by="expires_on, id", check=_check_approval,
    describe=lambda row: f"Approval #{row.get('id')}",
    computed=(("Valid until", _approval_flag),),
    fields=(
        Field("trainer_id", "Trainer", "ref", ref="trainers", required=True,
              on_delete="CASCADE"),
        Field("course_id", "Course", "ref", ref="courses", required=True, on_delete="CASCADE"),
        Field("approved_on", "Approved", "date", required=True),
        Field("approved_by", "Approved by", help="Awarding body or internal sign-off"),
        Field("expires_on", "Expires", "date"),
        Field("evidence", "Evidence / reference", listed=False),
    ),
)


def approved(trainer_id: int, course_id: int, on: date) -> bool:
    for a in r.list_records(APPROVALS, equals={"trainer_id": trainer_id,
                                               "course_id": course_id}):
        start, until = r.to_date(a["approved_on"]), r.to_date(a.get("expires_on"))
        if start and start <= on and (until is None or on <= until):
            return True
    return False


def _check_venue(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    learners.check_postcode(values)
    if merged.get("capacity") is not None and int(merged["capacity"]) < 1:
        raise ValidationError("Capacity must be at least 1.")


VENUES = RecordType(
    key="venues", title="Venues", singular="venue", order_by="name", check=_check_venue,
    filters=("kind",), describe=lambda row: row.get("name") or "venue",
    fields=(
        Field("name", "Name", required=True),
        Field("kind", "Type", "choice", VENUE_KINDS, required=True, default=VENUE_KINDS[0]),
        Field("address_line1", "Address", listed=False),
        Field("postcode", "Postcode"),
        Field("capacity", "Capacity", "int"),
        Field("accessible", "Step-free access", "bool", default=1),
        Field("cost_per_day", "Cost per day", "money", listed=False),
        Field("notes", "Notes", "long", listed=False),
    ),
)
