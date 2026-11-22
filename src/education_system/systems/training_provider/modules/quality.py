"""Quality: teaching observations, internal quality assurance (IQA) sampling
of assessment decisions, and learner feedback / complaints.

Rules:

* an observation graded Requires improvement or Inadequate needs actions
  and a re-observation within 3 months; otherwise the next one is due in 12;
* the IQA can't sample their own assessment decision and must be a qualified
  IQA; a decision Not agreed needs the action taken;
* a complaint gets a response within 10 working days; feedback can only be
  Resolved with a response recorded.
"""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.training_provider.core import dates
from education_system.systems.training_provider.core import records as r
from education_system.systems.training_provider.core.records import (
    Field,
    RecordType,
    ValidationError,
)
from education_system.systems.training_provider.modules import assessment, courses, sessions

GRADES = ("Outstanding", "Good", "Requires improvement", "Inadequate")
WEAK = GRADES[2:]
REOBSERVE_MONTHS = 3
OBSERVE_MONTHS = 12
IQA_DECISIONS = ("Agreed", "Not agreed")
FEEDBACK_KINDS = ("Course evaluation", "Compliment", "Complaint", "Suggestion")
FEEDBACK_STATUSES = ("Open", "Resolved")
COMPLAINT_DAYS = 10


def _check_observation(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    on = r.to_date(merged.get("observed_on"))
    if on and on > date.today():
        raise ValidationError("An observation can't be dated in the future.")
    weak = merged.get("grade") in WEAK
    if weak and not merged.get("actions"):
        raise ValidationError(f"A grade of {merged['grade']} needs the agreed actions.")
    if on:
        limit = dates.add_months(on, REOBSERVE_MONTHS if weak else OBSERVE_MONTHS)
        nxt = r.to_date(merged.get("next_due"))
        if nxt is None or "grade" in values and (old or {}).get("grade") != merged.get("grade"):
            values["next_due"] = limit.isoformat()
        elif nxt > limit:
            raise ValidationError(f"The next observation must be by {dates.uk(limit)}.")
    if merged.get("session_id") and merged.get("trainer_id"):
        s = r.get(sessions.SESSIONS, int(merged["session_id"]))
        if s and s.get("trainer_id") and s["trainer_id"] != int(merged["trainer_id"]):
            raise ValidationError("That session was taught by a different trainer.")


OBSERVATIONS = RecordType(
    key="observations", title="Teaching Observations", singular="observation",
    order_by="observed_on DESC, id DESC", check=_check_observation, filters=("grade",),
    describe=lambda row: f"Observation #{row.get('id')} ({row.get('grade')})",
    fields=(
        Field("trainer_id", "Trainer", "ref", ref="trainers", required=True,
              on_delete="CASCADE"),
        Field("session_id", "Session", "ref", ref="sessions", on_delete="SET NULL"),
        Field("observed_on", "Observed", "date", required=True),
        Field("observer", "Observer", required=True),
        Field("grade", "Grade", "choice", GRADES, required=True),
        Field("strengths", "Strengths", "long", listed=False),
        Field("actions", "Actions agreed", "long", listed=False),
        Field("next_due", "Next observation", "date"),
    ),
)


def latest_observation(trainer_id: int) -> dict | None:
    rows = r.list_records(OBSERVATIONS, equals={"trainer_id": trainer_id})
    return rows[0] if rows else None


def _check_iqa(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    result = r.get(assessment.RESULTS, int(merged["result_id"])) \
        if merged.get("result_id") else None
    if result is None:
        raise ValidationError("Choose the assessment decision sampled.")
    iqa = r.get(courses.TRAINERS, int(merged["iqa_id"]))
    if result.get("assessor_id") == iqa["id"]:
        raise ValidationError("An IQA can't sample their own assessment decision.")
    if not iqa.get("iqa_qualified"):
        raise ValidationError(f"{iqa['name']} isn't recorded as a qualified IQA.")
    on = r.to_date(merged.get("sampled_on"))
    if on and on > date.today():
        raise ValidationError("The sample can't be dated in the future.")
    assessed = r.to_date(result.get("assessed_on"))
    if on and assessed and on < assessed:
        raise ValidationError("The sample can't be before the assessment.")
    if merged.get("decision") == "Not agreed" and not merged.get("action"):
        raise ValidationError("A decision not agreed needs the action taken.")


IQA_SAMPLES = RecordType(
    key="iqa_samples", title="IQA Sampling", singular="IQA sample",
    order_by="sampled_on DESC, id DESC", check=_check_iqa, filters=("decision",),
    describe=lambda row: f"IQA sample #{row.get('id')} ({row.get('decision')})",
    computed=(("Decision sampled",
               lambda row: assessment.RESULTS.label_for(
                   r.get(assessment.RESULTS, row["result_id"]) or {})),),
    fields=(
        Field("result_id", "Assessment decision", "ref", ref="results", required=True,
              on_delete="CASCADE"),
        Field("iqa_id", "IQA", "ref", ref="trainers", required=True),
        Field("sampled_on", "Sampled", "date", required=True),
        Field("decision", "Decision", "choice", IQA_DECISIONS, required=True,
              default="Agreed"),
        Field("comments", "Comments", "long", listed=False),
        Field("action", "Action taken", "long", listed=False),
    ),
)


def sample_rate() -> float | None:
    """% of assessment decisions that have been IQA sampled."""
    results = r.list_records(assessment.RESULTS)
    if not results:
        return None
    sampled = {s["result_id"] for s in r.list_records(IQA_SAMPLES)}
    return round(100 * sum(x["id"] in sampled for x in results) / len(results))


def response_due(row: dict) -> date | None:
    got = r.to_date(row.get("received_on"))
    if row.get("kind") != "Complaint" or got is None:
        return None
    return dates.school_day(got + timedelta(days=1), COMPLAINT_DAYS)


def _due_flag(row: dict) -> str:
    due = response_due(row)
    if due is None or row.get("status") == "Resolved":
        return ""
    return dates.uk(due) + (" - OVERDUE" if due < date.today() else "")


def _check_feedback(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    rating = merged.get("rating")
    if rating is not None and not 1 <= int(rating) <= 5:
        raise ValidationError("The rating is 1 (poor) to 5 (excellent).")
    got = r.to_date(merged.get("received_on"))
    if got and got > date.today():
        raise ValidationError("Feedback can't be received in the future.")
    if merged.get("status") == "Resolved":
        if not merged.get("response"):
            raise ValidationError("Record the response before resolving.")
        if not merged.get("responded_on"):
            values["responded_on"] = date.today().isoformat()
    responded = r.to_date(values.get("responded_on", merged.get("responded_on")))
    if responded and got and responded < got:
        raise ValidationError("The response can't be before it was received.")


FEEDBACK = RecordType(
    key="feedback", title="Feedback & Complaints", singular="feedback",
    order_by="received_on DESC, id DESC", check=_check_feedback,
    filters=("kind", "status"),
    describe=lambda row: f"{row.get('kind')} #{row.get('id')}",
    computed=(("Response due", _due_flag),),
    fields=(
        Field("learner_id", "Learner", "learner"),
        Field("session_id", "Session", "ref", ref="sessions", on_delete="SET NULL"),
        Field("client_id", "Client", "ref", ref="clients", on_delete="SET NULL"),
        Field("received_on", "Received", "date", required=True),
        Field("kind", "Type", "choice", FEEDBACK_KINDS, required=True,
              default=FEEDBACK_KINDS[0]),
        Field("rating", "Rating (1-5)", "int"),
        Field("comments", "Comments", "long", required=True, listed=False),
        Field("response", "Our response", "long", listed=False),
        Field("responded_on", "Responded", "date", listed=False),
        Field("status", "Status", "choice", FEEDBACK_STATUSES, required=True, default="Open"),
    ),
)


def average_rating(session_id: int | None = None) -> float | None:
    rows = [f for f in r.list_records(FEEDBACK)
            if f.get("rating") and (session_id is None or f.get("session_id") == session_id)]
    if not rows:
        return None
    return round(sum(int(f["rating"]) for f in rows) / len(rows), 1)
