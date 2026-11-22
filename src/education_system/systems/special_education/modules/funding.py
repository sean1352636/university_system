"""High-needs funding and transitions between settings."""

from __future__ import annotations

from datetime import date

from education_system.systems.special_education.core import records as r
from education_system.systems.special_education.core.records import Field, RecordType, ValidationError


def _today() -> str:
    return date.today().isoformat()


def _check_funding(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    start = r.to_date(r.parse_date(merged.get("start_date")))
    end = r.to_date(r.parse_date(merged.get("end_date")))
    if start and end and end < start:
        raise ValidationError("The end date can't be before the start date.")
    if merged.get("status") == "Agreed" and not merged.get("amount_per_year"):
        raise ValidationError("Agreed funding needs the annual amount.")


FUNDING = RecordType(
    key="funding", title="High Needs Funding", singular="funding award",
    order_by="status, start_date DESC", check=_check_funding,
    filters=("funding_type", "status"),
    describe=lambda row: f"{row.get('funding_type')} {r.fmt(FUNDING.fields_by_name['amount_per_year'], row.get('amount_per_year'))}",
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("funding_type", "Type", "choice",
              ("Top-up (element 3)", "Personal budget", "Direct payment",
               "Exceptional needs funding", "Other"), required=True),
        Field("local_authority", "Local authority"),
        Field("reference", "LA reference", listed=False),
        Field("amount_per_year", "Per year", "money"),
        Field("start_date", "From", "date", required=True, default=_today),
        Field("end_date", "To", "date"),
        Field("status", "Status", "choice", ("Requested", "Agreed", "Refused", "Ended"),
              required=True, default="Requested"),
    ),
)


def _check_transition(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    if merged.get("status") == "Completed" and not merged.get("transition_date"):
        raise ValidationError("A completed transition needs its date.")


TRANSITIONS = RecordType(
    key="transitions", title="Transitions & Preparing for Adulthood", singular="transition",
    order_by="status, transition_date", check=_check_transition,
    filters=("transition_type", "status"),
    describe=lambda row: f"{row.get('transition_type')} → {row.get('to_setting') or '?'}",
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("transition_type", "Type", "choice",
              ("Phase transfer", "School move", "Post-16", "Post-19 / adult services",
               "Preparing for adulthood"), required=True),
        Field("from_setting", "From"),
        Field("to_setting", "To"),
        Field("consultation_sent", "Consultation sent", "date", listed=False),
        Field("transition_date", "Moves on", "date"),
        Field("status", "Status", "choice", ("Planning", "Consulting", "Agreed", "Completed"),
              required=True, default="Planning"),
        Field("plan", "Transition plan", "long", listed=False),
    ),
)
