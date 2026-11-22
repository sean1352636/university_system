"""Moving on: reintegration into mainstream school, and destinations.

Rules:

* a pupil has one open reintegration plan (Planning or Phased return);
* a phased return needs its start date; Completed needs the full return
  date (not before the phased start) - it then marks the pupil Reintegrated
  and ends their active placements; a plan that broke down needs the reason;
* follow-up checks are due 6 and 12 weeks after the full return;
* a destination can't be dated in the future; "NEET" is flagged for
  follow-up.
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

STATUSES = ("Planning", "Phased return", "Completed", "Broke down", "Cancelled")
OPEN = frozenset({"Planning", "Phased return"})
READINESS = ("Not ready", "Nearly ready", "Ready")
#: How a linked pupil goes back (ap_referrals.ENDINGS); the last means the
#: platform only closes the AP record.
RETURN_TO = ("Home school (dual registration)", "Primary School (new admission)",
             "Secondary School (new admission)", "A school not on the platform")
FOLLOW_UP_WEEKS = (6, 12)
DESTINATIONS = ("Mainstream school", "Special school", "Another AP provider", "Sixth form",
                "FE college", "Apprenticeship", "Traineeship / supported internship",
                "Employment with training", "Employment without training", "NEET",
                "Moved out of area", "Elective home education", "Unknown")


def _today() -> str:
    return date.today().isoformat()


def _check_plan(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    new = merged.get("status")
    phased, full = r.to_date(merged.get("phased_start")), r.to_date(merged.get("full_return"))
    if new == "Phased return" and not phased:
        raise ValidationError("Give the date the phased return starts.")
    if new == "Completed":
        if not full:
            raise ValidationError("Give the date of the full return to school.")
        if full > date.today():
            raise ValidationError("The full return hasn't happened yet - keep the plan as a "
                                  "Phased return until then.")
    if phased and full and full < phased:
        raise ValidationError("The full return can't be before the phased return starts.")
    if new == "Broke down" and not merged.get("outcome"):
        raise ValidationError("Record why the reintegration broke down.")
    if new in OPEN:
        with db.connect() as conn:
            clash = conn.execute("SELECT 1 FROM reintegration WHERE learner_id = ? AND status "
                                 "IN ('Planning', 'Phased return') AND id IS NOT ?",
                                 (merged["learner_id"], (old or {}).get("id"))).fetchone()
        if clash:
            raise ValidationError("This pupil already has an open reintegration plan.")


def _after_plan(conn, row: dict, old: dict | None) -> None:
    if row["status"] == "Completed" and (old or {}).get("status") != "Completed":
        learners.set_status(conn, row["learner_id"], "Reintegrated", only_if="On roll",
                            on=row["full_return"], why=f"returned to {row.get('target_school')}")
        ended = conn.execute(
            "UPDATE placements SET status = 'Ended', end_date = ?, end_reason = "
            "'Reintegrated to mainstream', updated_at = datetime('now') WHERE learner_id = ? "
            "AND status IN ('Active', 'Planned')",
            (row["full_return"], row["learner_id"])).rowcount
        if ended:
            conn.execute("INSERT INTO history (actor, record_type, record_id, learner_id, "
                         "action, summary) VALUES ('system', 'placements', ?, ?, 'updated', ?)",
                         (row["id"], row["learner_id"],
                          f"{ended} placement(s) ended: reintegrated to mainstream"))


def follow_ups(row: dict) -> list[date]:
    full = r.to_date(row.get("full_return"))
    return [dates.add_weeks(full, w) for w in FOLLOW_UP_WEEKS] if full else []


def _follow_flag(row: dict) -> str:
    if row.get("status") != "Completed":
        return ""
    done = int(row.get("follow_ups_done") or 0)
    due = follow_ups(row)
    if done >= len(due):
        return "Done"
    nxt = due[done]
    return f"{FOLLOW_UP_WEEKS[done]}-week {dates.uk(nxt)}" + (
        " - OVERDUE" if nxt < date.today() else "")


REINTEGRATION = RecordType(
    key="reintegration", title="Reintegration Plans", singular="reintegration plan",
    order_by="plan_date DESC, id DESC", check=_check_plan, after_save=_after_plan,
    after_commit=learners.platform_hook("reintegration_saved"),
    filters=("status", "readiness"),
    describe=lambda row: f"Return to {row.get('target_school')} ({row.get('status')})",
    computed=(("Follow-up", _follow_flag),),
    fields=(
        Field("learner_id", "Pupil", "learner", required=True),
        Field("plan_date", "Planned", "date", required=True, default=_today),
        Field("target_school", "Returning to", required=True),
        Field("return_to", "Where on the platform", "choice", RETURN_TO,
              default=RETURN_TO[0], listed=False,
              help="For a pupil a linked school referred: how they go back"),
        Field("school_contact", "School contact", listed=False),
        Field("readiness", "Readiness", "choice", READINESS, required=True,
              default="Not ready"),
        Field("support_package", "Support package", "long", listed=False,
              help="What the school and AP will put in place"),
        Field("transition_meeting", "Transition meeting", "date", listed=False),
        Field("phased_start", "Phased return starts", "date"),
        Field("full_return", "Full return", "date"),
        Field("status", "Status", "choice", STATUSES, required=True, default="Planning"),
        Field("follow_ups_done", "Follow-ups done", "int", default=0, listed=False,
              help="6- and 12-week checks after the full return"),
        Field("outcome", "Outcome / notes", "long", listed=False),
    ),
)


def _check_destination(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    on = r.to_date(merged.get("recorded_on"))
    if on and on > date.today():
        raise ValidationError("A destination can't be dated in the future.")


DESTINATIONS_RT = RecordType(
    key="destinations", title="Destinations", singular="destination",
    order_by="recorded_on DESC, id DESC", check=_check_destination,
    filters=("destination",),
    describe=lambda row: f"{row.get('destination')} ({row.get('recorded_on')})",
    computed=(("Follow up", lambda row: "NEET - follow up" if row.get("destination") == "NEET"
               else ""),),
    fields=(
        Field("learner_id", "Pupil", "learner", required=True),
        Field("recorded_on", "Date", "date", required=True, default=_today),
        Field("destination", "Destination", "choice", DESTINATIONS, required=True),
        Field("provider", "School / college / employer"),
        Field("confirmed", "Confirmed", "bool", default=0),
        Field("notes", "Notes", "long", listed=False),
    ),
)


def latest_destinations() -> dict[int, str]:
    out: dict[int, str] = {}
    for row in sorted(r.list_records(DESTINATIONS_RT), key=lambda x: (x["recorded_on"], x["id"])):
        out[row["learner_id"]] = row["destination"]
    return out
