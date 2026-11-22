"""Suspensions and permanent exclusions notified by schools (Suspension and
permanent exclusion guidance, 2023/24).

Rules:

* a suspension is in half days and a child can't be suspended for more than
  45 school days in one school year;
* a permanent exclusion is reviewed by the governing board within 15 school
  days of the notice; the parent can then ask for an independent review
  within 15 school days of the board's decision;
* from the sixth school day of a permanent exclusion (or of a suspension of
  more than five days) the authority (or school) must provide full-time
  education - the due list shows it until it is recorded;
* an exclusion the board upholds takes the child off that school's roll
  (education "Not in education" until a new place is found).
"""

from __future__ import annotations

from datetime import date, timedelta

from education_system.systems.local_authority.core import dates
from education_system.systems.local_authority.core import records as r
from education_system.systems.local_authority.core.records import (
    Field,
    RecordType,
    ValidationError,
)
from education_system.systems.local_authority.infrastructure import database as db
from education_system.systems.local_authority.modules import children, schools

KINDS = ("Suspension", "Permanent exclusion")
REASONS = ("Physical assault against a pupil", "Physical assault against an adult",
           "Verbal abuse or threatening behaviour against a pupil",
           "Verbal abuse or threatening behaviour against an adult",
           "Use or threat of use of an offensive weapon or prohibited item", "Bullying",
           "Racist abuse", "Abuse against sexual orientation or gender identity",
           "Abuse relating to disability", "Inappropriate use of social media or online "
           "technology", "Damage", "Theft", "Drug and alcohol related", "Sexual misconduct",
           "Persistent or general disruptive behaviour", "Other")
OUTCOMES = ("Awaiting review", "Upheld", "Reinstated", "Withdrawn by school")
MAX_SUSPENSION_DAYS = 45.0
REVIEW_DAYS = 15


def sixth_day(row: dict) -> date | None:
    start = r.to_date(row.get("start_date"))
    if start is None:
        return None
    if row.get("kind") == "Suspension" and float(row.get("days") or 0) <= 5:
        return None
    return dates.school_day(start, 6)


def review_due(row: dict) -> date | None:
    notified = r.to_date(row.get("notified_on"))
    if row.get("kind") != KINDS[1] or notified is None:
        return None
    return dates.school_day(notified + timedelta(days=1), REVIEW_DAYS)


def suspension_days(child_id: int, on: date, excluding: int | None = None) -> float:
    ys = dates.school_year_start(on).isoformat()
    ye = date(dates.school_year_start(on).year + 1, 8, 31).isoformat()
    with db.connect() as conn:
        return float(conn.execute(
            "SELECT COALESCE(SUM(days), 0) FROM exclusions WHERE learner_id = ? AND "
            "kind = 'Suspension' AND COALESCE(outcome, '') != 'Withdrawn by school' AND "
            "start_date BETWEEN ? "
            "AND ? AND id IS NOT ?", (child_id, ys, ye, excluding)).fetchone()[0])


def _check_exclusion(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    start = r.to_date(merged.get("start_date"))
    if merged.get("kind") == "Suspension":
        days = float(merged.get("days") or 0)
        if days <= 0 or days * 2 != int(days * 2):
            raise ValidationError("A suspension is a number of days, in halves (e.g. 1.5).")
        used = suspension_days(int(merged["learner_id"]), start or date.today(),
                               (old or {}).get("id"))
        if used + days > MAX_SUSPENSION_DAYS:
            raise ValidationError(f"That takes the child to {used + days:g} days of suspension "
                                  f"this school year; the limit is {MAX_SUSPENSION_DAYS:g}.")
        if merged.get("outcome") != "Withdrawn by school":
            values["outcome"] = None   # only a permanent exclusion is reviewed
        values["irp_requested_on"] = None
    else:
        values["days"] = None
        notified = r.to_date(merged.get("notified_on"))
        if notified is None:
            raise ValidationError("Give the date the authority was notified.")
        if merged.get("outcome") in ("Upheld", "Reinstated"):
            review = r.to_date(merged.get("review_on"))
            if review is None:
                raise ValidationError("Give the date of the governing board's review.")
            if review > date.today():
                raise ValidationError("The board's review hasn't happened yet.")
        irp = r.to_date(merged.get("irp_requested_on"))
        review = r.to_date(merged.get("review_on"))
        if irp and (merged.get("outcome") != "Upheld" or not review):
            raise ValidationError("An independent review follows the board upholding the "
                                  "exclusion.")
        if irp and review and irp > dates.school_day(review + timedelta(days=1), 15):
            raise ValidationError("An independent review must be asked for within 15 school "
                                  "days of the board's decision.")
    if start and start > date.today() + timedelta(days=30):
        raise ValidationError("That start date is too far ahead.")


def _after_exclusion(conn, row: dict, old: dict | None) -> None:
    if row["kind"] == KINDS[1] and row["outcome"] == "Upheld" and \
            (old or {}).get("outcome") != "Upheld":
        conn.execute("UPDATE learners SET education = 'Not in education', school_id = NULL, "
                     "updated_at = datetime('now') WHERE id = ? AND school_id IS ?",
                     (row["learner_id"], row["school_id"]))


def _flag(row: dict) -> str:
    if row.get("kind") == KINDS[1] and row.get("outcome") == "Awaiting review":
        due = review_due(row)
        return (f"Board review by {dates.uk(due)}" + (" - OVERDUE" if due and due <
                                                     date.today() else "")) if due else ""
    day6 = sixth_day(row)
    if day6 and not row.get("provision_from"):
        return f"Provision from {dates.uk(day6)}" + (" - NOT RECORDED" if day6 <= date.today()
                                                     else "")
    return ""


EXCLUSIONS = RecordType(
    after_commit=children.platform_hook("exclusion_saved"),
    key="exclusions", title="Suspensions & Exclusions", singular="exclusion",
    order_by="start_date DESC, id DESC", check=_check_exclusion,
    after_save=_after_exclusion, filters=("kind", "outcome"),
    describe=lambda row: f"{row.get('kind')}: {children.child_name(row.get('learner_id'))}",
    computed=(("School", lambda row: schools.school_name(row.get("school_id"))),
              ("Next step", _flag)),
    fields=(
        Field("learner_id", "Child", "learner", required=True),
        Field("school_id", "School", "ref", ref="schools", required=True),
        Field("kind", "Type", "choice", KINDS, required=True),
        Field("start_date", "Starts", "date", required=True),
        Field("days", "Days (suspension)", "number"),
        Field("reason", "Reason", "choice", REASONS, required=True, listed=False),
        Field("notified_on", "LA notified", "date", listed=False),
        Field("review_on", "Governing board review", "date", listed=False),
        Field("outcome", "Outcome", "choice", OUTCOMES, default="Awaiting review"),
        Field("irp_requested_on", "Independent review requested", "date", listed=False),
        Field("provision_from", "Full-time provision from", "date", listed=False,
              help="From the sixth school day"),
        Field("provision", "Provision arranged", listed=False),
        Field("notes", "Notes", "long", listed=False),
        # Set by the platform for a notification from a linked school.
        Field("source_system", "Notified by (platform)", form=False, listed=False),
        Field("transition_id", "Platform notification", form=False, listed=False),
    ),
)
