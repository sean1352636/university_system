"""Support and welfare: learning support plans, adult safeguarding concerns,
and feedback (compliments, complaints and appeals)."""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.adult_education.core import records as r
from education_system.systems.adult_education.core.records import Field, RecordType, ValidationError

#: Complaints are answered within this many days.
COMPLAINT_RESPONSE_DAYS = 10


def _today() -> str:
    return date.today().isoformat()


def _span(start: str, end: str):
    def check(values: dict, old: dict | None) -> None:
        merged = {**(old or {}), **values}
        a, b = r.to_date(r.parse_date(merged.get(start))), r.to_date(r.parse_date(merged.get(end)))
        if a and b and b < a:
            raise ValidationError("The later date can't be before the earlier one.")
    return check


def _review_flag(row: dict) -> str:
    due = r.to_date(row.get("review_date"))
    if row.get("status") != "Active" or not due:
        return ""
    days = (due - date.today()).days
    return f"Overdue {-days}d" if days < 0 else ("Due soon" if days <= 14 else "")


SUPPORT = RecordType(
    key="support_plans", title="Learning Support", singular="support plan",
    order_by="status, review_date", check=_span("start_date", "review_date"),
    filters=("need", "status"), computed=(("Review", _review_flag),),
    describe=lambda row: str(row.get("need")),
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("need", "Need", "choice",
              ("Dyslexia / SpLD", "Mental health", "Physical disability", "Hearing",
               "Vision", "Autism", "Learning difficulty", "Digital access", "Language",
               "Medical", "Other"), required=True),
        Field("support", "Support agreed", "long", required=True),
        Field("adjustments", "Exam / classroom adjustments", "long", listed=False),
        Field("provided_by", "Provided by"),
        Field("start_date", "Start", "date", default=_today),
        Field("review_date", "Review", "date"),
        Field("status", "Status", "choice", ("Active", "Ended"), required=True,
              default="Active"),
    ),
)


def _check_concern(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    if merged.get("status") == "Closed":
        values.setdefault("closed_on", merged.get("closed_on") or _today())
        if not merged.get("action_taken"):
            raise ValidationError("Record the action taken before closing a concern.")
    _span("raised_on", "closed_on")(values, old)


SAFEGUARDING = RecordType(
    key="safeguarding", title="Safeguarding Concerns", singular="concern",
    order_by="status DESC, raised_on DESC", check=_check_concern,
    filters=("category", "status"),
    describe=lambda row: f"{row.get('category')} ({row.get('raised_on')})",
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("raised_on", "Raised", "date", required=True, default=_today),
        Field("raised_by", "Raised by", required=True),
        Field("category", "Category", "choice",
              ("Physical abuse", "Emotional / psychological", "Sexual abuse", "Neglect",
               "Self-neglect", "Domestic abuse", "Financial / material", "Modern slavery",
               "Discriminatory", "Radicalisation (Prevent)", "Mental health crisis", "Other"),
              required=True),
        Field("details", "What happened", "long", required=True),
        Field("action_taken", "Action taken", "long", listed=False),
        Field("referred_to", "Referred to", "choice",
              ("Not referred", "Local authority adult social care", "Police", "Prevent",
               "GP / health", "Other agency")),
        Field("designated_lead", "Designated lead"),
        Field("status", "Status", "choice", ("Open", "Monitoring", "Closed"), required=True,
              default="Open"),
        Field("closed_on", "Closed", "date", listed=False),
    ),
)


def _check_feedback(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    if merged.get("status") in ("Resolved", "Upheld", "Not upheld"):
        values.setdefault("closed_on", merged.get("closed_on") or _today())
        if merged.get("kind") in ("Complaint", "Appeal") and not merged.get("response"):
            raise ValidationError("Record the response before closing a complaint or appeal.")
    _span("received_on", "closed_on")(values, old)


def _response_due(row: dict) -> str:
    got = r.to_date(row.get("received_on"))
    if row.get("kind") not in ("Complaint", "Appeal") or row.get("status") != "Open" or not got:
        return ""
    due = got + timedelta(days=COMPLAINT_RESPONSE_DAYS)
    days = (due - date.today()).days
    return f"Overdue {-days}d" if days < 0 else f"Reply in {days}d"


FEEDBACK = RecordType(
    key="feedback", title="Feedback & Complaints", singular="feedback item",
    order_by="status, received_on DESC", check=_check_feedback, filters=("kind", "status"),
    computed=(("Response", _response_due),),
    describe=lambda row: f"{row.get('kind')}: {row.get('about')}",
    fields=(
        Field("learner_id", "Learner", "learner", help="Leave blank if anonymous"),
        Field("kind", "Type", "choice", ("Compliment", "Complaint", "Suggestion", "Appeal",
                                         "Survey comment"), required=True),
        Field("about", "About", required=True),
        Field("received_on", "Received", "date", required=True, default=_today),
        Field("details", "Details", "long", listed=False),
        Field("status", "Status", "choice", ("Open", "Resolved", "Upheld", "Not upheld"),
              required=True, default="Open"),
        Field("response", "Our response", "long", listed=False),
        Field("closed_on", "Closed", "date", listed=False),
    ),
)
