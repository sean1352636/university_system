"""Safeguarding: concerns, missing-from-education episodes and the other
professionals working with a pupil.

Rules (Keeping Children Safe in Education and the missing children guidance):

* a concern can't be dated in the future; it is seen by the DSL before it
  can be closed, and closing needs the outcome; an action that refers the
  child on (social care, police, LADO, Prevent, early help) needs the
  referral date;
* a missing episode can't end before it starts; a child who returns gets a
  **return interview within 72 hours**, which is tracked until it's done.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from education_system.systems.alternative_provision.core import dates
from education_system.systems.alternative_provision.core import records as r
from education_system.systems.alternative_provision.core.records import (
    Field,
    RecordType,
    ValidationError,
)
from education_system.systems.alternative_provision.modules import learners

CATEGORIES = ("Physical abuse", "Emotional abuse", "Sexual abuse", "Neglect",
              "Child criminal exploitation", "Child sexual exploitation",
              "County lines / gangs", "Radicalisation", "Domestic abuse", "Online safety",
              "Child-on-child abuse", "Self-harm / suicidal thoughts", "Substance misuse",
              "Missing from education", "Other")
ACTIONS = ("Monitor in school", "Early help", "Referral to children's social care",
           "Police", "LADO (concern about an adult)", "Prevent / Channel",
           "No further action")
REFERRING = frozenset({"Early help", "Referral to children's social care", "Police",
                       "LADO (concern about an adult)", "Prevent / Channel"})
AGENCIES = ("Children's social care", "Early help", "CAMHS", "Youth justice service",
            "Police", "School nurse / health", "Educational psychology", "Virtual school",
            "SEN team", "Youth service", "Housing", "Voluntary sector", "Other")
RETURN_INTERVIEW_HOURS = 72


def _today() -> str:
    return date.today().isoformat()


def _check_concern(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    on = r.to_date(merged.get("raised_on"))
    if on and on > date.today():
        raise ValidationError("A concern can't be dated in the future.")
    if merged.get("action") in REFERRING and not merged.get("referral_date"):
        raise ValidationError(f"Give the date of the {merged['action'].lower()} referral.")
    ref = r.to_date(merged.get("referral_date"))
    if ref and on and ref < on:
        raise ValidationError("The referral can't be before the concern was raised.")
    if merged.get("status") == "Closed":
        if not merged.get("dsl_reviewed_by"):
            raise ValidationError("The DSL has to review a concern before it is closed.")
        if not merged.get("outcome"):
            raise ValidationError("Record the outcome before closing the concern.")


CONCERNS = RecordType(
    key="safeguarding", title="Safeguarding Concerns", singular="safeguarding concern",
    order_by="raised_on DESC, id DESC", check=_check_concern,
    filters=("category", "action", "status"),
    describe=lambda row: f"{row.get('raised_on')} {row.get('category')} ({row.get('status')})",
    fields=(
        Field("learner_id", "Pupil", "learner", required=True),
        Field("raised_on", "Raised", "date", required=True, default=_today),
        Field("raised_by", "Raised by", required=True),
        Field("category", "Category", "choice", CATEGORIES, required=True),
        Field("details", "What was seen or said", "long", required=True,
              help="Facts and the child's own words"),
        Field("dsl_reviewed_by", "Reviewed by DSL"),
        Field("action", "Action", "choice", ACTIONS),
        Field("referral_date", "Referred on", "date", listed=False),
        Field("referral_ref", "Referral reference", listed=False),
        Field("outcome", "Outcome", "long", listed=False),
        Field("status", "Status", "choice", ("Open", "Closed"), required=True, default="Open"),
    ),
)


def _when(day: str | None, time: str | None) -> datetime | None:
    d = r.to_date(day)
    if d is None:
        return None
    try:
        hh, mm = (int(x) for x in (time or "00:00").split(":"))
        return datetime(d.year, d.month, d.day, hh, mm)
    except ValueError:
        raise ValidationError("Times are 24-hour HH:MM (e.g. 14:30).") from None


def interview_due(row: dict) -> datetime | None:
    back = _when(row.get("returned_on"), row.get("returned_at"))
    return back + timedelta(hours=RETURN_INTERVIEW_HOURS) if back else None


def _check_missing(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    gone = _when(merged.get("missing_on"), merged.get("missing_at"))
    back = _when(merged.get("returned_on"), merged.get("returned_at"))
    if gone and gone > datetime.now():
        raise ValidationError("A missing episode can't start in the future.")
    if gone and back and back < gone:
        raise ValidationError("The child can't return before they went missing.")
    done = r.to_date(merged.get("interview_on"))
    if done and not back:
        raise ValidationError("A return interview is recorded after the child returns.")
    if done and back and done < back.date():
        raise ValidationError("The return interview can't be before the child returned.")


def _interview_flag(row: dict) -> str:
    due = interview_due(row)
    if due is None:
        return "Still missing"
    done = r.to_date(row.get("interview_on"))
    if done:
        return "Done" + (" (late)" if done > due.date() else "")
    return f"Due {dates.uk(due.date())}" + (" - OVERDUE" if datetime.now() > due else "")


MISSING = RecordType(
    key="missing_episodes", title="Missing Episodes", singular="missing episode",
    order_by="missing_on DESC, id DESC", check=_check_missing,
    describe=lambda row: f"Missing {row.get('missing_on')}",
    computed=(("Return interview", _interview_flag),),
    fields=(
        Field("learner_id", "Pupil", "learner", required=True),
        Field("missing_on", "Went missing", "date", required=True, default=_today),
        Field("missing_at", "Time", default="09:00", listed=False),
        Field("circumstances", "Circumstances", "long", listed=False),
        Field("reported_to_police", "Reported to police", "bool"),
        Field("police_ref", "Police reference", listed=False),
        Field("parents_told", "Parents / carers told", "bool", default=1, listed=False),
        Field("returned_on", "Returned", "date"),
        Field("returned_at", "Time back", listed=False),
        Field("interview_on", "Return interview", "date", listed=False),
        Field("interview_by", "Interview by", listed=False),
        Field("notes", "Notes", "long", listed=False),
    ),
)


def _check_professional(values: dict, old: dict | None) -> None:  # noqa: ARG001
    learners.check_email(values)
    learners.check_phone(values)


PROFESSIONALS = RecordType(
    key="professionals", title="Professionals Involved", singular="professional",
    order_by="learner_id, agency", check=_check_professional, filters=("agency",),
    describe=lambda row: f"{row.get('name')} ({row.get('agency')})",
    fields=(
        Field("learner_id", "Pupil", "learner", required=True),
        Field("agency", "Agency", "choice", AGENCIES, required=True),
        Field("name", "Name", required=True),
        Field("role", "Role"),
        Field("phone", "Phone"),
        Field("email", "E-mail"),
        Field("involvement", "Involvement (plan / order)", listed=False,
              help="e.g. child protection plan, referral order"),
        Field("active", "Currently involved", "bool", default=1),
    ),
)
