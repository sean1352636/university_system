"""What is provided: the provision map, equipment, and health & care plans."""

from __future__ import annotations

from datetime import date

from education_system.systems.special_education.core import records as r
from education_system.systems.special_education.core.records import Field, RecordType, ValidationError
from education_system.systems.special_education.modules.needs import AREAS


def _today() -> str:
    return date.today().isoformat()


def _check_span(start_key: str, end_key: str):
    def check(values: dict, old: dict | None) -> None:
        merged = {**(old or {}), **values}
        start = r.to_date(r.parse_date(merged.get(start_key)))
        end = r.to_date(r.parse_date(merged.get(end_key)))
        if start and end and end < start:
            raise ValidationError("The end date can't be before the start date.")
    return check


def _check_provision(values: dict, old: dict | None) -> None:
    _check_span("start_date", "end_date")(values, old)
    merged = {**(old or {}), **values}
    end = r.to_date(r.parse_date(merged.get("end_date")))
    if end and end < date.today() and merged.get("status") == "Active":
        values["status"] = "Ended"


PROVISION = RecordType(
    key="provision", title="Provision Map", singular="provision",
    order_by="status, learner_id", check=_check_provision,
    filters=("provision_type", "area", "status", "funded_by"),
    describe=lambda row: f"{row.get('name')} ({row.get('provision_type')})",
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("name", "Provision", required=True, help="e.g. Precision teaching, SaLT block"),
        Field("provision_type", "Type", "choice",
              ("Small-group intervention", "1:1 support", "In-class support", "Therapy",
               "Specialist teaching", "Mentoring / counselling", "Other"), required=True),
        Field("area", "Area of need", "choice", AREAS),
        Field("provider", "Delivered by"),
        Field("frequency", "Frequency", help="e.g. 3 × 20 min a week"),
        Field("hours_per_week", "Hours / week", "number"),
        Field("cost_per_week", "Cost / week", "money"),
        Field("funded_by", "Funded by", "choice",
              ("Notional SEN budget", "Top-up funding", "Pupil Premium", "Health", "Other"),
              listed=False),
        Field("start_date", "Start", "date", default=_today),
        Field("end_date", "End", "date"),
        Field("status", "Status", "choice", ("Planned", "Active", "Ended"), required=True,
              default="Active"),
        Field("impact", "Impact", "long", listed=False),
    ),
)

EQUIPMENT = RecordType(
    key="equipment", title="Equipment & Assistive Technology", singular="item",
    order_by="status, review_date", check=_check_span("provided_on", "review_date"),
    filters=("category", "status"),
    describe=lambda row: str(row.get("item")),
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("item", "Item", required=True),
        Field("category", "Category", "choice",
              ("Assistive technology", "Communication aid (AAC)", "Mobility",
               "Seating / posture", "Sensory", "Hearing / vision", "Other"), required=True),
        Field("owner", "Owned by", "choice", ("School/setting", "Local authority", "Health",
                                              "Family")),
        Field("serial", "Serial / asset no.", listed=False),
        Field("provided_on", "Provided", "date", default=_today),
        Field("review_date", "Review", "date"),
        Field("status", "Status", "choice", ("In use", "Needs repair", "Returned"),
              required=True, default="In use"),
    ),
)

HEALTH_PLANS = RecordType(
    key="health_plans", title="Medical & Care Plans", singular="care plan",
    order_by="status, review_date", check=_check_span("start_date", "review_date"),
    filters=("plan_type", "status"),
    describe=lambda row: str(row.get("plan_type")),
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("plan_type", "Plan", "choice",
              ("Individual healthcare plan", "Medication", "Allergy / anaphylaxis",
               "Personal / intimate care", "Emergency protocol", "Moving & handling",
               "Positive behaviour support"), required=True),
        Field("summary", "Summary", "long", required=True),
        Field("responsible", "Responsible"),
        Field("start_date", "Start", "date", default=_today),
        Field("review_date", "Review", "date"),
        Field("status", "Status", "choice", ("Active", "Ended"), required=True,
              default="Active"),
    ),
)
