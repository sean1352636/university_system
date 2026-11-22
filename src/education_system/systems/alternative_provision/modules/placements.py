"""Providers, placements and placement reviews.

Rules (from the DfE alternative provision and exclusion guidance):

* a provider's quality-assurance visit is due every 12 months; registered
  status follows its type (PRUs, AP academies and independent schools are
  registered, the others aren't);
* a new placement can't go to a provider that is rated Inadequate, suspended
  or closed, or that is already full;
* an **unregistered** provider can't be used for 18 hours a week or more -
  at that point it would have to register as an independent school;
* a pupil's active placements can't add up to more than 32.5 hours a week;
* a placement of under 25 hours a week is a **part-time timetable**: it needs
  a reason and a review date no more than six weeks after it starts, so it
  stays temporary;
* an Active placement has started (start date not in the future) and puts a
  Referred pupil on roll; ending one needs an end date and a reason;
* placements are reviewed every six weeks (or the gap set on the placement);
  a review sets the next one.
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

KINDS = ("Pupil referral unit", "AP academy / free school", "Registered independent school",
         "Unregistered AP provider", "Online / remote provider", "Tuition service")
REGISTERED_KINDS = frozenset(KINDS[:3])
OFSTED = ("Outstanding", "Good", "Requires improvement", "Inadequate", "Not inspected")
PROVIDER_STATUSES = ("Active", "Suspended", "Closed")
QA_MONTHS = 12

FULL_TIME_HOURS = 25.0
MAX_HOURS = 32.5
UNREGISTERED_LIMIT = 18.0
PART_TIME_REVIEW_WEEKS = 6
STATUSES = ("Planned", "Active", "Ended")
END_REASONS = ("Reintegrated to mainstream", "Moved to another provider",
               "Moved to special school", "Moved out of area", "Finished Year 11 / post-16",
               "Placement broke down", "Permanently excluded", "Other")
COMMISSIONERS = ("Home school", "Local authority", "Our own PRU / AP school")


def _today() -> str:
    return date.today().isoformat()


# ── providers ───────────────────────────────────────────────────────

def _check_provider(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    learners.check_email(values)
    learners.check_phone(values)
    learners.check_postcode(values)
    values["registered"] = 1 if merged.get("kind") in REGISTERED_KINDS else 0
    qa = r.to_date(merged.get("qa_visit"))
    if qa and qa > date.today():
        raise ValidationError("The last QA visit can't be in the future.")
    cap = merged.get("capacity")
    if cap is not None and old is not None and "capacity" in values:
        used = active_count(old["id"])
        if int(cap) < used:
            placed = "1 pupil is" if used == 1 else f"{used} pupils are"
            raise ValidationError(f"{placed} placed there now, so capacity can't be "
                                  f"below {used}.")


def qa_due(row: dict) -> date | None:
    qa = r.to_date(row.get("qa_visit"))
    return dates.add_months(qa, QA_MONTHS) if qa else None


def _qa_flag(row: dict) -> str:
    due = qa_due(row)
    if due is None:
        return "No QA visit yet" if row.get("status") == "Active" else ""
    return dates.uk(due) + (" - OVERDUE" if due < date.today() else "")


def active_count(provider_id: int) -> int:
    with db.connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM placements WHERE provider_id = ? AND "
                            "status = 'Active'", (provider_id,)).fetchone()[0]


PROVIDERS = RecordType(
    key="providers", title="Provider Directory", singular="provider",
    order_by="name", check=_check_provider, filters=("kind", "status", "ofsted"),
    describe=lambda row: f"{row.get('name')} ({row.get('kind')})",
    computed=(("Placed", lambda row: str(active_count(row["id"]))), ("QA due", _qa_flag)),
    fields=(
        Field("name", "Name", required=True),
        Field("kind", "Type", "choice", KINDS, required=True),
        Field("registered", "Registered school", "bool", form=False),
        Field("urn", "URN / UKPRN", listed=False),
        Field("ofsted", "Ofsted", "choice", OFSTED, default="Not inspected"),
        Field("contact", "Contact", listed=False),
        Field("phone", "Phone", listed=False),
        Field("email", "E-mail", listed=False),
        Field("address_line1", "Address", listed=False),
        Field("postcode", "Postcode", listed=False),
        Field("offer", "What they offer", "long", listed=False),
        Field("capacity", "Places", "int"),
        Field("daily_rate", "Daily rate", "money"),
        Field("qa_visit", "Last QA visit", "date", listed=False),
        Field("checks_confirmed", "Staff checks confirmed (DBS, KCSIE)", "bool", listed=False),
        Field("status", "Status", "choice", PROVIDER_STATUSES, required=True, default="Active"),
    ),
)


# ── placements ──────────────────────────────────────────────────────

def _check_placement(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    provider = r.get(PROVIDERS, int(merged["provider_id"])) if merged.get("provider_id") else None
    if provider is None:
        raise ValidationError("Choose the provider.")
    hours = float(merged.get("hours_per_week") or 0)
    if hours <= 0 or hours > MAX_HOURS:
        raise ValidationError(f"Hours a week must be above 0 and at most {MAX_HOURS:g}.")
    days = merged.get("days_per_week")
    if days is not None and not 0 < float(days) <= 5:
        raise ValidationError("Days a week is between 0.5 and 5.")
    if merged.get("daily_rate") in (None, "") and provider.get("daily_rate"):
        values["daily_rate"] = provider["daily_rate"]
    start = r.to_date(merged.get("start_date"))
    new, was = merged.get("status"), (old or {}).get("status")
    provider_changed = old is None or "provider_id" in values and \
        int(values["provider_id"]) != old.get("provider_id")
    if provider_changed or (new == "Active" and was != "Active"):
        if provider["status"] != "Active":
            raise ValidationError(f"{provider['name']} is {provider['status'].lower()}: it "
                                  "can't take new placements.")
        if provider.get("ofsted") == "Inadequate":
            raise ValidationError(f"{provider['name']} is rated Inadequate: it can't take new "
                                  "placements.")
        cap = provider.get("capacity")
        if new == "Active" and cap is not None and active_count(provider["id"]) >= int(cap):
            raise ValidationError(f"{provider['name']} is full ({cap} places).")
    if not provider.get("registered") and hours >= UNREGISTERED_LIMIT:
        raise ValidationError(f"{provider['name']} is not a registered school, so it can't be "
                              f"used for {UNREGISTERED_LIMIT:g} hours a week or more (it would "
                              "need to register as an independent school).")
    if hours < FULL_TIME_HOURS:
        if not merged.get("part_time_reason"):
            raise ValidationError(f"Under {FULL_TIME_HOURS:g} hours a week is a part-time "
                                  "timetable: give the reason.")
        review = r.to_date(merged.get("part_time_review"))
        if start and not review:
            review = dates.add_weeks(start, PART_TIME_REVIEW_WEEKS)
            values["part_time_review"] = review.isoformat()
        if start and review and review > dates.add_weeks(start, PART_TIME_REVIEW_WEEKS):
            raise ValidationError("A part-time timetable has to be reviewed within "
                                  f"{PART_TIME_REVIEW_WEEKS} weeks of the start.")
    else:
        values["part_time_review"] = None
    if new == "Active":
        if start and start > date.today():
            raise ValidationError("A placement starting in the future is Planned, not Active.")
        with db.connect() as conn:
            other = conn.execute(
                "SELECT COALESCE(SUM(hours_per_week), 0) FROM placements WHERE learner_id = ? "
                "AND status = 'Active' AND id IS NOT ?",
                (merged["learner_id"], (old or {}).get("id"))).fetchone()[0]
        if other + hours > MAX_HOURS:
            raise ValidationError(f"With the pupil's other placements ({other:g} hours) that "
                                  f"is more than {MAX_HOURS:g} hours a week.")
    if new == "Ended":
        if not merged.get("end_date"):
            values["end_date"] = _today()
        if not merged.get("end_reason"):
            raise ValidationError("Give the reason the placement ended.")
    elif was == "Ended":
        values["end_date"] = None
    end = r.to_date(values.get("end_date", merged.get("end_date")))
    planned = r.to_date(merged.get("planned_end"))
    if start and end and end < start:
        raise ValidationError("A placement can't end before it starts.")
    if start and planned and planned < start:
        raise ValidationError("The planned end can't be before the start.")
    if start and not merged.get("next_review"):
        weeks = int(merged.get("review_weeks") or 6)
        values["next_review"] = dates.add_weeks(start, weeks).isoformat()


def _after_placement(conn, row: dict, old: dict | None) -> None:
    if row["status"] == "Active" and (old or {}).get("status") != "Active":
        learners.set_status(conn, row["learner_id"], "On roll", only_if="Referred",
                            on=row["start_date"], why="placement started")


def placement_label(row: dict) -> str:
    provider = r.get(PROVIDERS, row["provider_id"]) if row.get("provider_id") else None
    return (f"{row.get('learner_name') or ''}: {provider['name'] if provider else 'provider'} "
            f"from {dates.uk(r.to_date(row.get('start_date')))} ({row.get('status')})")


def weekly_cost(row: dict) -> float:
    days = float(row.get("days_per_week") or 5)
    return round(days * float(row.get("daily_rate") or 0), 2)


def _timetable(row: dict) -> str:
    hours = float(row.get("hours_per_week") or 0)
    text = f"{hours:g}h"
    if hours < FULL_TIME_HOURS:
        review = r.to_date(row.get("part_time_review"))
        text += " part-time"
        if review and row.get("status") == "Active":
            text += f", review {dates.uk(review)}" + (" OVERDUE" if review < date.today() else "")
    return text


def _review_flag(row: dict) -> str:
    due = r.to_date(row.get("next_review"))
    if due is None or row.get("status") != "Active":
        return ""
    return dates.uk(due) + (" - OVERDUE" if due < date.today() else "")


PLACEMENTS = RecordType(
    key="placements", title="Placements", singular="placement",
    order_by="start_date DESC, id DESC", check=_check_placement, after_save=_after_placement,
    after_commit=learners.platform_hook("placement_saved"),
    filters=("status", "commissioned_by"), describe=placement_label,
    computed=(("Timetable", _timetable), ("Next review", _review_flag),
              ("Cost / week", lambda row: f"£{weekly_cost(row):,.2f}" if row.get("daily_rate")
               else "")),
    fields=(
        Field("learner_id", "Pupil", "learner", required=True),
        Field("provider_id", "Provider", "ref", ref="providers", required=True),
        Field("referral_id", "Referral", "ref", ref="referrals", listed=False,
              on_delete="SET NULL"),
        Field("start_date", "Start", "date", required=True, default=_today),
        Field("planned_end", "Planned end", "date", listed=False),
        Field("days_per_week", "Days a week", "number", default=5, listed=False),
        Field("hours_per_week", "Hours a week", "number", required=True, default=25,
              help=f"Under {FULL_TIME_HOURS:g} is a part-time timetable"),
        Field("part_time_reason", "Part-time reason", "long", listed=False),
        Field("part_time_review", "Part-time review by", "date", listed=False,
              help=f"Within {PART_TIME_REVIEW_WEEKS} weeks of the start"),
        Field("registration", "Registration", "choice",
              ("Single registration", "Dual registration"), default="Single registration",
              listed=False),
        Field("commissioned_by", "Commissioned by", "choice", COMMISSIONERS,
              default=COMMISSIONERS[0]),
        Field("commissioner", "Commissioner (school / LA name)", listed=False),
        Field("daily_rate", "Daily rate", "money", listed=False,
              help="Left blank: the provider's rate"),
        Field("review_weeks", "Review every (weeks)", "int", default=6, listed=False),
        Field("next_review", "Next review", "date", form=False, listed=False),
        Field("status", "Status", "choice", STATUSES, required=True, default="Planned"),
        Field("end_date", "Ended", "date", listed=False),
        Field("end_reason", "End reason", "choice", END_REASONS, listed=False),
    ),
)


def _placement_learner(values: dict, old: dict | None) -> dict:
    pid = values.get("placement_id") or (old or {}).get("placement_id")
    row = r.get(PLACEMENTS, int(pid)) if pid else None
    if row is None:
        raise ValidationError("Choose the placement.")
    values["learner_id"] = row["learner_id"]
    return row


def _check_review(values: dict, old: dict | None) -> None:
    placement = _placement_learner(values, old)
    merged = {**(old or {}), **values}
    on = r.to_date(merged.get("review_date"))
    start = r.to_date(placement.get("start_date"))
    if on and on > date.today():
        raise ValidationError("A review can't be recorded for a future date.")
    if on and start and on < start:
        raise ValidationError("The review can't be before the placement started.")
    att = merged.get("attendance_pct")
    if att is not None and float(att) > 100:
        raise ValidationError("Attendance is a percentage, 0-100.")
    nxt = r.to_date(merged.get("next_review"))
    if on and not nxt and merged.get("outcome") != "End placement":
        weeks = int(placement.get("review_weeks") or 6)
        values["next_review"] = dates.add_weeks(on, weeks).isoformat()
    elif on and nxt and nxt <= on:
        raise ValidationError("The next review must be after this one.")


def _after_review(conn, row: dict, _old: dict | None) -> None:
    conn.execute("UPDATE placements SET next_review = ?, updated_at = datetime('now') "
                 "WHERE id = ?", (row.get("next_review"), row["placement_id"]))


PLACEMENT_REVIEWS = RecordType(
    key="placement_reviews", title="Placement Reviews", singular="placement review",
    order_by="review_date DESC, id DESC", check=_check_review, after_save=_after_review,
    filters=("outcome", "progress"),
    describe=lambda row: f"{row.get('review_date')} review - {row.get('outcome')}",
    fields=(
        Field("placement_id", "Placement", "ref", ref="placements", required=True,
              on_delete="CASCADE"),
        Field("learner_id", "Pupil", "learner", form=False),
        Field("review_date", "Review date", "date", required=True, default=_today),
        Field("attended_by", "Attended by", listed=False),
        Field("attendance_pct", "Attendance %", "number"),
        Field("progress", "Progress", "choice", ("Good", "Some", "Little", "None"),
              required=True),
        Field("behaviour", "Behaviour and engagement", "long", listed=False),
        Field("pupil_view", "Pupil's view", "long", listed=False),
        Field("parent_view", "Parent / carer's view", "long", listed=False),
        Field("outcome", "Outcome", "choice", ("Continue", "Change hours", "Plan reintegration",
                                               "Change provider", "End placement"),
              required=True, default="Continue"),
        Field("actions", "Actions", "long", listed=False),
        Field("next_review", "Next review", "date",
              help="Left blank: the placement's review gap"),
    ),
)


def active_placements(learner_id: int | None = None) -> list[dict]:
    return r.list_records(PLACEMENTS, learner_id=learner_id, equals={"status": "Active"})


def placement_options(learner_id: int | None = None) -> list[tuple[int, str]]:
    return [(row["id"], placement_label(row)) for row in
            r.list_records(PLACEMENTS, learner_id=learner_id)]


def days_in(row: dict, start: date, end: date) -> float:
    """Placement days between *start* and *end* (weekdays the placement ran,
    scaled by its days a week)."""
    s = max(start, r.to_date(row.get("start_date")) or start)
    e = min(end, r.to_date(row.get("end_date")) or end)
    if e < s:
        return 0.0
    per_week = float(row.get("days_per_week") or 5)
    return round(dates.weekdays_between(s, e) * per_week / 5, 1)

