"""SEN Support plans: the graduated approach (assess - plan - do - review).

A plan has targets and reviews. Rules:

* one *Active* plan per learner at a time;
* a plan's next review defaults to 12 weeks after it starts (about termly);
* saving a review moves the plan's next review date on, and an outcome of
  "Close - needs met" closes the plan.
"""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.special_education.core import records as r
from education_system.systems.special_education.core.records import Field, RecordType, ValidationError
from education_system.systems.special_education.infrastructure import database as db

REVIEW_INTERVAL = timedelta(weeks=12)
PROGRESS = ("Not started", "Emerging", "Developing", "Secure", "Achieved")
REVIEW_OUTCOMES = ("Continue", "Revise plan", "Close - needs met",
                   "Request EHC needs assessment")


def _today() -> str:
    return date.today().isoformat()


def _check_plan(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    start = r.to_date(r.parse_date(merged.get("start_date")))
    review = r.to_date(r.parse_date(merged.get("review_date")))
    if start and not review:
        values["review_date"] = (start + REVIEW_INTERVAL).isoformat()
    elif start and review and review < start:
        raise ValidationError("The review date can't be before the plan starts.")
    if merged.get("status") == "Active":
        with db.connect() as conn:
            other = conn.execute(
                "SELECT title FROM support_plans WHERE learner_id = ? AND status = 'Active' "
                "AND id IS NOT ?", (merged.get("learner_id"), (old or {}).get("id"))).fetchone()
        if other:
            raise ValidationError(f"This learner already has an active plan ('{other[0]}'). "
                                  "Close it before making another one active.")


PLANS = RecordType(
    key="support_plans", title="SEN Support Plans", singular="support plan",
    order_by="status, review_date", check=_check_plan, filters=("status",),
    describe=lambda row: (f"{row.get('learner_name') or ''} - {row.get('title')} "
                          f"({row.get('status')})").strip(" -"),
    computed=(("Review", lambda row: _review_flag(row)),),
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("title", "Plan title", required=True, default="SEN Support Plan"),
        Field("start_date", "Start", "date", required=True, default=_today),
        Field("review_date", "Next review", "date",
              help="Left blank: 12 weeks after the start"),
        Field("plan_lead", "Plan lead"),
        Field("status", "Status", "choice", ("Draft", "Active", "Closed"), required=True,
              default="Draft"),
        Field("outcomes", "Outcomes we want", "long", listed=False),
        Field("strategies", "Strategies & adjustments", "long", listed=False),
        Field("parent_views", "Parent / carer views", "long", listed=False),
        Field("learner_views", "Learner views", "long", listed=False),
    ),
)


def _review_flag(row: dict) -> str:
    if row.get("status") != "Active" or not row.get("review_date"):
        return ""
    days = (date.fromisoformat(row["review_date"]) - date.today()).days
    return f"Overdue {-days}d" if days < 0 else ("Due" if days <= 14 else "")


def _plan_learner(values: dict, old: dict | None) -> None:
    """Targets and reviews take their learner from the plan."""
    plan_id = values.get("plan_id") or (old or {}).get("plan_id")
    plan = r.get(PLANS, int(plan_id)) if plan_id else None
    if plan is None:
        raise ValidationError("Choose the support plan.")
    values["learner_id"] = plan["learner_id"]
    return plan


def _check_target(values: dict, old: dict | None) -> None:
    _plan_learner(values, old)


TARGETS = RecordType(
    key="plan_targets", title="Targets & Outcomes", singular="target",
    order_by="plan_id, due_date", check=_check_target, filters=("progress",),
    describe=lambda row: (row.get("target") or "")[:60],
    fields=(
        Field("plan_id", "Support plan", "ref", ref="support_plans", required=True,
              on_delete="CASCADE"),
        Field("learner_id", "Learner", "learner", form=False),
        Field("target", "Target", "long", required=True),
        Field("baseline", "Starting point", "long", listed=False),
        Field("success_criteria", "We'll know it's met when", "long", listed=False),
        Field("responsible", "Who"),
        Field("due_date", "By", "date"),
        Field("progress", "Progress", "choice", PROGRESS, required=True, default="Not started"),
    ),
)


def _check_review(values: dict, old: dict | None) -> None:
    plan = _plan_learner(values, old)
    merged = {**(old or {}), **values}
    held = r.to_date(r.parse_date(merged.get("review_date")))
    nxt = r.to_date(r.parse_date(merged.get("next_review")))
    start = r.to_date(plan.get("start_date"))
    if held and start and held < start:
        raise ValidationError("A review can't be held before the plan started.")
    if held and nxt and nxt <= held:
        raise ValidationError("The next review must be after this one.")
    if held and not nxt and merged.get("outcome") != "Close - needs met":
        values["next_review"] = (held + REVIEW_INTERVAL).isoformat()


def _after_review(conn, row: dict, _old: dict | None) -> None:
    if row["outcome"] == "Close - needs met":
        conn.execute("UPDATE support_plans SET status = 'Closed', "
                     "updated_at = datetime('now') WHERE id = ?", (row["plan_id"],))
    elif row.get("next_review"):
        conn.execute("UPDATE support_plans SET review_date = ?, updated_at = datetime('now') "
                     "WHERE id = ?", (row["next_review"], row["plan_id"]))


REVIEWS = RecordType(
    key="plan_reviews", title="Plan Reviews", singular="plan review",
    order_by="review_date DESC", check=_check_review, after_save=_after_review,
    filters=("outcome",),
    describe=lambda row: f"Review {r.fmt(REVIEWS.fields_by_name['review_date'], row.get('review_date'))}",
    fields=(
        Field("plan_id", "Support plan", "ref", ref="support_plans", required=True,
              on_delete="CASCADE"),
        Field("learner_id", "Learner", "learner", form=False),
        Field("review_date", "Held on", "date", required=True, default=_today),
        Field("attendees", "Who attended"),
        Field("progress_summary", "Progress", "long", listed=False),
        Field("outcome", "Outcome", "choice", REVIEW_OUTCOMES, required=True),
        Field("next_review", "Next review", "date",
              help="Left blank: 12 weeks after this review"),
    ),
)
