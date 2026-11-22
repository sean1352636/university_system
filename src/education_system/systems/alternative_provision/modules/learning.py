"""Teaching and support: plans, baseline and progress, qualifications and
wellbeing interventions.

Rules:

* a plan's review date comes after its start; a Personal Education Plan
  (PEP) is only for looked-after pupils, and is reviewed termly (the review
  is set to no more than 4 months ahead);
* a pupil has one baseline per subject, recorded before any progress check;
* a qualification marked Achieved needs its result; a sat or achieved entry
  can't have an exam date in the future;
* an intervention can't end before it starts, and a completed one needs its
  outcome.
"""

from __future__ import annotations

from datetime import date

from education_system.systems.alternative_provision.core import dates
from education_system.systems.alternative_provision.core import records as r
from education_system.systems.alternative_provision.core.records import (
    Field,
    RecordType,
    ValidationError,
)
from education_system.systems.alternative_provision.infrastructure import database as db
from education_system.systems.alternative_provision.modules import learners

PLAN_KINDS = ("Individual learning plan", "Pastoral support plan", "Behaviour support plan",
              "Personal education plan (PEP)", "Health care / medical plan")
SUBJECTS = ("English", "Maths", "Science", "Reading age", "Spelling age", "PSHE / SEMH",
            "Vocational", "Other")
CHECKS = ("Baseline", "Progress check", "End of placement")
QUALIFICATIONS = ("GCSE", "Functional Skills", "Entry Level Certificate", "BTEC",
                  "Vocational award", "Arts Award", "ASDAN", "Other")
QUAL_STATUSES = ("Planned", "Entered", "Sat", "Achieved", "Not achieved", "Withdrawn")
INTERVENTIONS_KINDS = ("Mentoring", "Counselling", "CAMHS", "Speech and language therapy",
                       "Educational psychologist", "Occupational therapy", "Youth work",
                       "Family support", "Careers guidance", "Substance misuse service",
                       "Other")
INTERVENTION_STATUSES = ("Referred", "Active", "Completed", "Declined", "Stopped")


def _today() -> str:
    return date.today().isoformat()


def _a(word: str) -> str:
    return f"{'an' if word[:1] in 'AEIOU' else 'a'} {word}"


def _check_plan(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    start, review = r.to_date(merged.get("start_date")), r.to_date(merged.get("review_date"))
    if start and review and review <= start:
        raise ValidationError("The review date must be after the plan starts.")
    if merged.get("kind") == PLAN_KINDS[3]:
        pupil = r.get(learners.LEARNERS, int(merged["learner_id"]))
        if pupil and not pupil.get("looked_after"):
            raise ValidationError("A Personal Education Plan is for looked-after pupils. Tick "
                                  "'Looked after' on the pupil's record first.")
        if start and review and review > dates.add_months(start, 4):
            raise ValidationError("A PEP is reviewed every term: set the review within four "
                                  "months.")


def _plan_flag(row: dict) -> str:
    due = r.to_date(row.get("review_date"))
    if not due or row.get("status") != "Active":
        return ""
    return dates.uk(due) + (" - OVERDUE" if due < date.today() else "")


PLANS = RecordType(
    key="plans", title="Learning & Support Plans", singular="plan",
    order_by="start_date DESC, id DESC", check=_check_plan, filters=("kind", "status"),
    describe=lambda row: f"{row.get('kind')} from {row.get('start_date')}",
    computed=(("Review due", _plan_flag),),
    fields=(
        Field("learner_id", "Pupil", "learner", required=True),
        Field("kind", "Plan", "choice", PLAN_KINDS, required=True),
        Field("start_date", "Starts", "date", required=True, default=_today),
        Field("targets", "Targets", "long", required=True),
        Field("strategies", "Strategies / support", "long", listed=False),
        Field("pupil_view", "Pupil's view", "long", listed=False),
        Field("review_date", "Review by", "date", required=True),
        Field("review_notes", "Review notes", "long", listed=False),
        Field("status", "Status", "choice", ("Active", "Completed", "Ended"), required=True,
              default="Active"),
    ),
)


def _check_progress(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    on = r.to_date(merged.get("assessed_on"))
    if on and on > date.today():
        raise ValidationError("An assessment can't be dated in the future.")
    with db.connect() as conn:
        base = conn.execute(
            "SELECT id, assessed_on FROM progress WHERE learner_id = ? AND subject = ? AND "
            "kind = 'Baseline' AND id IS NOT ?",
            (merged["learner_id"], merged.get("subject"), (old or {}).get("id"))).fetchone()
    if merged.get("kind") == "Baseline" and base:
        raise ValidationError(f"There is already {_a(merged['subject'])} baseline. Record "
                              "a progress check instead.")
    if merged.get("kind") != "Baseline":
        if not base:
            raise ValidationError(f"Record {_a(merged.get('subject') or '')} baseline first.")
        if on and on < r.to_date(base[1]):
            raise ValidationError("A progress check can't be before the baseline.")


PROGRESS = RecordType(
    key="progress", title="Baseline & Progress", singular="assessment",
    order_by="assessed_on DESC, id DESC", check=_check_progress,
    filters=("subject", "kind"),
    describe=lambda row: f"{row.get('subject')} {row.get('kind')}: {row.get('result')}",
    fields=(
        Field("learner_id", "Pupil", "learner", required=True),
        Field("subject", "Subject", "choice", SUBJECTS, required=True),
        Field("kind", "Type", "choice", CHECKS, required=True, default="Baseline"),
        Field("assessed_on", "Date", "date", required=True, default=_today),
        Field("result", "Result / working at", required=True,
              help="e.g. 'Year 5 expected', 'Reading age 9y 4m', 'Entry 3'"),
        Field("score", "Score (if any)", "number", listed=False),
        Field("comment", "Comment", "long", listed=False),
    ),
)


def _check_qualification(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    if merged.get("status") == "Achieved" and not merged.get("result"):
        raise ValidationError("Record the result for an achieved qualification.")
    exam = r.to_date(merged.get("exam_date"))
    if merged.get("status") in ("Sat", "Achieved", "Not achieved") and exam and \
            exam > date.today():
        raise ValidationError("The exam date is in the future, so it can't be sat yet.")


QUALIFICATIONS_RT = RecordType(
    key="qualifications", title="Qualifications & Exams", singular="qualification",
    order_by="exam_date DESC, id DESC", check=_check_qualification,
    filters=("qualification", "status"),
    describe=lambda row: f"{row.get('qualification')} {row.get('subject')} "
                         f"({row.get('status')})",
    fields=(
        Field("learner_id", "Pupil", "learner", required=True),
        Field("qualification", "Qualification", "choice", QUALIFICATIONS, required=True),
        Field("subject", "Subject", required=True),
        Field("level", "Level / tier"),
        Field("awarding_body", "Awarding body", listed=False),
        Field("entered_on", "Entered", "date", listed=False),
        Field("exam_date", "Exam / completion date", "date"),
        Field("access_arrangements", "Access arrangements", listed=False),
        Field("status", "Status", "choice", QUAL_STATUSES, required=True, default="Planned"),
        Field("result", "Result / grade"),
    ),
)


def _check_intervention(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    start, end = r.to_date(merged.get("start_date")), r.to_date(merged.get("end_date"))
    if start and end and end < start:
        raise ValidationError("An intervention can't end before it starts.")
    if merged.get("status") in ("Completed", "Stopped") and not merged.get("outcome"):
        raise ValidationError("Record the outcome.")
    if merged.get("status") in ("Completed", "Stopped") and not end:
        values["end_date"] = _today()


INTERVENTIONS = RecordType(
    key="interventions", title="Wellbeing Interventions", singular="intervention",
    order_by="start_date DESC, id DESC", check=_check_intervention,
    filters=("kind", "status"),
    describe=lambda row: f"{row.get('kind')} ({row.get('status')})",
    fields=(
        Field("learner_id", "Pupil", "learner", required=True),
        Field("kind", "Intervention", "choice", INTERVENTIONS_KINDS, required=True),
        Field("provider", "Delivered by"),
        Field("start_date", "Starts", "date", default=_today),
        Field("end_date", "Ends", "date"),
        Field("sessions", "Sessions", "int", listed=False),
        Field("status", "Status", "choice", INTERVENTION_STATUSES, required=True,
              default="Referred"),
        Field("outcome", "Outcome", "long", listed=False),
    ),
)
