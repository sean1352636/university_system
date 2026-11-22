"""Where learners are heading: learning goals (with reviews) and destinations.

Goal rules carried over from the old Learners area: a new goal's target date
can't be in the past; a learner has at most :data:`MAX_OPEN_GOALS` open
goals; withdrawing needs a reason; achieving sets progress to 100%; a closed
goal can't be reviewed; a review moves the goal's progress (100% achieves it,
anything above 0 starts it).
"""

from __future__ import annotations

from datetime import date

from education_system.systems.adult_education.core import records as r
from education_system.systems.adult_education.core.records import Field, RecordType, ValidationError
from education_system.systems.adult_education.infrastructure import database as db

MAX_OPEN_GOALS = 10
GOAL_STATUSES = ("Not started", "In progress", "Achieved", "Withdrawn")
CLOSED = frozenset({"Achieved", "Withdrawn"})


def _today() -> str:
    return date.today().isoformat()


def _check_goal(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    target = r.to_date(r.parse_date(merged.get("target_date")))
    if old is None:
        if target and target < date.today():
            raise ValidationError("A new goal's target date can't be in the past.")
        with db.connect() as conn:
            n = conn.execute("SELECT COUNT(*) FROM goals WHERE learner_id = ? AND status IN "
                             "('Not started', 'In progress')",
                             (merged["learner_id"],)).fetchone()[0]
        if n >= MAX_OPEN_GOALS:
            raise ValidationError(f"A learner can have at most {MAX_OPEN_GOALS} open goals. "
                                  "Close one first.")
    progress = int(merged.get("progress") or 0)
    if not 0 <= progress <= 100:
        raise ValidationError("Progress is a percentage from 0 to 100.")
    status, was = merged.get("status"), (old or {}).get("status")
    if status == "Achieved":
        values["progress"] = 100
        if was != "Achieved":
            values["achieved_on"] = _today()
    elif status == "Withdrawn" and not merged.get("withdrawn_reason"):
        raise ValidationError("Give the reason the goal was withdrawn.")
    elif was == "Achieved" and status != "Achieved":   # reopened
        values["achieved_on"] = None
        if progress >= 100:
            values["progress"] = 90
    elif status == "Not started" and progress > 0:
        values["status"] = "In progress"


def _goal_flag(row: dict) -> str:
    target = r.to_date(row.get("target_date"))
    if row.get("status") in CLOSED or not target:
        return ""
    days = (target - date.today()).days
    return f"Overdue {-days}d" if days < 0 else ("Due soon" if days <= 14 else "")


GOALS = RecordType(
    key="goals", title="Learning Goals", singular="goal", order_by="status, target_date",
    check=_check_goal, filters=("category", "status"), computed=(("Target", _goal_flag),),
    describe=lambda row: f"{row.get('title')} ({row.get('progress') or 0}%)",
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("title", "Goal", required=True),
        Field("category", "Category", "choice", ("Employment", "Qualification", "Skills",
                                                 "Personal development", "Progression",
                                                 "Wellbeing"), required=True),
        Field("description", "Details", "long", listed=False),
        Field("target_date", "Target date", "date"),
        Field("status", "Status", "choice", GOAL_STATUSES, required=True,
              default="Not started"),
        Field("progress", "Progress %", "int", default=0),
        Field("achieved_on", "Achieved", "date", form=False),
        Field("withdrawn_reason", "Withdrawn because", listed=False),
    ),
)


def _check_review(values: dict, old: dict | None) -> None:
    gid = values.get("goal_id") or (old or {}).get("goal_id")
    goal = r.get(GOALS, int(gid)) if gid else None
    if goal is None:
        raise ValidationError("Choose the goal.")
    values["learner_id"] = goal["learner_id"]
    if goal["status"] in CLOSED and old is None:
        raise ValidationError("This goal is closed. Reopen it to record a review.")
    merged = {**(old or {}), **values}
    progress = int(merged.get("progress") or 0)
    if not 0 <= progress <= 100:
        raise ValidationError("Progress is a percentage from 0 to 100.")
    on = r.to_date(r.parse_date(merged.get("reviewed_on")))
    if on and on < date.fromisoformat(goal["created_at"][:10]):
        raise ValidationError("A review can't be before the goal was set.")


def _after_review(conn, row: dict, _old: dict | None) -> None:
    progress = int(row["progress"])
    if progress >= 100:
        conn.execute("UPDATE goals SET progress = 100, status = 'Achieved', achieved_on = ?, "
                     "updated_at = datetime('now') WHERE id = ?", (row["reviewed_on"], row["goal_id"]))
    else:
        conn.execute("UPDATE goals SET progress = ?, status = CASE WHEN status = 'Not started' "
                     "AND ? > 0 THEN 'In progress' ELSE status END, updated_at = datetime('now')"
                     " WHERE id = ?", (progress, progress, row["goal_id"]))


GOAL_REVIEWS = RecordType(
    key="goal_reviews", title="Goal Reviews", singular="goal review",
    order_by="reviewed_on DESC, id DESC", check=_check_review, after_save=_after_review,
    describe=lambda row: f"Review {row.get('reviewed_on')} ({row.get('progress')}%)",
    fields=(
        Field("goal_id", "Goal", "ref", ref="goals", required=True, on_delete="CASCADE"),
        Field("learner_id", "Learner", "learner", form=False),
        Field("reviewed_on", "Reviewed", "date", required=True, default=_today),
        Field("progress", "Progress %", "int", required=True),
        Field("comment", "Comment", "long", required=True),
        Field("reviewed_by", "Reviewed by"),
    ),
)


def _check_destination(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    on = r.to_date(r.parse_date(merged.get("recorded_on")))
    if on and on > date.today():
        raise ValidationError("A destination is recorded after it happens.")


DESTINATIONS = RecordType(
    key="destinations", title="Progression & Destinations", singular="destination",
    order_by="recorded_on DESC", check=_check_destination, filters=("destination",),
    describe=lambda row: str(row.get("destination")),
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("recorded_on", "Recorded", "date", required=True, default=_today),
        Field("destination", "Destination", "choice",
              ("Into employment", "Better job / promotion", "Self-employment",
               "Further learning (adult education)", "FE college", "Apprenticeship",
               "Higher education", "Volunteering", "Not in work or learning", "Unknown"),
              required=True),
        Field("details", "Details"),
        Field("source", "How we know", "choice", ("Learner", "Employer", "Follow-up survey",
                                                  "Tutor")),
    ),
)
