"""Behaviour incidents (including any use of reasonable force) and suspensions /
permanent exclusions from the AP setting.

Rules:

* incidents can't be dated in the future; one where **reasonable force** was
  used needs what happened, the staff involved and - before it is closed -
  the date the parent or carer was told;
* a suspension is for a number of school days (halves allowed) and a pupil
  can't be suspended for more than **45 school days in a school year**;
* every suspension / exclusion needs the date parents were notified (it
  must be "without delay"), and the reason from the DfE list;
* a confirmed permanent exclusion takes the pupil off roll (status Left)
  and ends their placements; a suspension of more than five days is
  flagged for sixth-day provision.
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

KINDS = ("Disruption", "Defiance / refusal", "Verbal abuse", "Physical assault (pupil)",
         "Physical assault (adult)", "Damage to property", "Absconding / leaving site",
         "Bullying", "Discriminatory abuse", "Drugs or alcohol", "Weapon", "Theft",
         "Self-harm", "Online / social media", "Sexual behaviour", "Other")
SEVERITY = ("Low", "Medium", "High")
EXCLUSION_REASONS = (
    "Physical assault against a pupil", "Physical assault against an adult",
    "Verbal abuse or threatening behaviour against a pupil",
    "Verbal abuse or threatening behaviour against an adult",
    "Use or threat of use of an offensive weapon or prohibited item", "Bullying",
    "Racist abuse", "Abuse against sexual orientation or gender identity",
    "Abuse relating to disability", "Inappropriate use of social media or online technology",
    "Wilful and repeated transgression of protective measures", "Damage", "Theft",
    "Drug and alcohol related", "Sexual misconduct", "Persistent or general disruptive "
    "behaviour", "Other")
MAX_SUSPENSION_DAYS = 45.0


def _today() -> str:
    return date.today().isoformat()


def _check_incident(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    on = r.to_date(merged.get("incident_date"))
    if on and on > date.today():
        raise ValidationError("An incident can't be dated in the future.")
    if merged.get("reasonable_force"):
        if not merged.get("force_details") or not merged.get("force_staff"):
            raise ValidationError("Reasonable force was used: record what happened and the "
                                  "staff involved.")
        told = r.to_date(merged.get("parent_informed"))
        if merged.get("status") == "Closed" and not told:
            raise ValidationError("Record when the parent or carer was told about the use of "
                                  "force before closing the incident.")
        if told and on and told < on:
            raise ValidationError("Parents can't be told before the incident happened.")


def _force_flag(row: dict) -> str:
    if not row.get("reasonable_force"):
        return ""
    return "Force used" + ("" if row.get("parent_informed") else " - parent not told yet")


INCIDENTS = RecordType(
    key="incidents", title="Behaviour Incidents", singular="incident",
    order_by="incident_date DESC, id DESC", check=_check_incident,
    filters=("kind", "severity", "status"),
    describe=lambda row: f"{row.get('incident_date')} {row.get('kind')} ({row.get('severity')})",
    computed=(("Force", _force_flag),),
    fields=(
        Field("learner_id", "Pupil", "learner", required=True),
        Field("incident_date", "Date", "date", required=True, default=_today),
        Field("incident_time", "Time", listed=False),
        Field("location", "Where", listed=False),
        Field("kind", "Type", "choice", KINDS, required=True),
        Field("severity", "Severity", "choice", SEVERITY, required=True, default="Low"),
        Field("description", "What happened", "long", required=True),
        Field("action_taken", "Action taken", "long", listed=False),
        Field("reported_by", "Reported by", listed=False),
        Field("injury", "Anyone injured", "bool", listed=False),
        Field("reasonable_force", "Reasonable force used", "bool", default=0, listed=False),
        Field("force_details", "Force: what was done and why", "long", listed=False),
        Field("force_staff", "Force: staff involved", listed=False),
        Field("parent_informed", "Parent / carer told", "date", listed=False),
        Field("status", "Status", "choice", ("Open", "Closed"), required=True, default="Open"),
    ),
)


def suspended_days(learner_id: int, year_start: date, *, exclude_id: int | None = None) -> float:
    end = date(year_start.year + 1, 8, 31)
    with db.connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(days), 0) FROM suspensions WHERE learner_id = ? AND "
            "kind = 'Suspension' AND start_date BETWEEN ? AND ? AND status != 'Withdrawn' "
            "AND id IS NOT ?", (learner_id, year_start.isoformat(), end.isoformat(),
                                exclude_id)).fetchone()
    return float(row[0])


def _check_suspension(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    start = r.to_date(merged.get("start_date"))
    told = r.to_date(merged.get("parent_notified"))
    if merged.get("kind") == "Suspension":
        days = float(merged.get("days") or 0)
        if days <= 0 or (days * 2) % 1:
            raise ValidationError("A suspension is a number of school days (halves allowed).")
        if start and merged.get("status") != "Withdrawn":
            ys = dates.school_year_start(start)
            already = suspended_days(int(merged["learner_id"]), ys,
                                     exclude_id=(old or {}).get("id"))
            if already + days > MAX_SUSPENSION_DAYS:
                raise ValidationError(f"That would make {already + days:g} days of suspension "
                                      f"this school year; the limit is {MAX_SUSPENSION_DAYS:g}.")
        if start:
            values["return_date"] = dates.school_day(start, int(days + 0.5) + 1).isoformat()
    else:
        values["days"] = None
        values["return_date"] = None
    if told and start and (told - start).days > 1:
        raise ValidationError("Parents must be told without delay - at the latest the day "
                              "after the decision.")


def _after_suspension(conn, row: dict, old: dict | None) -> None:
    if (row["kind"] == "Permanent exclusion" and row["status"] == "Confirmed"
            and (old or {}).get("status") != "Confirmed"):
        learners.set_status(conn, row["learner_id"], "Left", only_if=("On roll", "Referred"),
                            on=row["start_date"], why="permanently excluded")
        ended = conn.execute(
            "UPDATE placements SET status = 'Ended', end_date = ?, end_reason = "
            "'Permanently excluded', updated_at = datetime('now') WHERE learner_id = ? AND "
            "status IN ('Active', 'Planned')", (row["start_date"], row["learner_id"])).rowcount
        if ended:
            conn.execute("INSERT INTO history (actor, record_type, record_id, learner_id, "
                         "action, summary) VALUES ('system', 'placements', ?, ?, 'updated', ?)",
                         (row["id"], row["learner_id"],
                          f"{ended} placement(s) ended: permanently excluded"))


def _sixth_day(row: dict) -> str:
    if row.get("kind") == "Permanent exclusion":
        start = r.to_date(row.get("start_date"))
        return dates.uk(dates.school_day(start, 6)) if start else ""
    if float(row.get("days") or 0) > 5:
        start = r.to_date(row.get("start_date"))
        return dates.uk(dates.school_day(start, 6)) if start else ""
    return ""


SUSPENSIONS = RecordType(
    key="suspensions", title="Suspensions & Exclusions", singular="suspension / exclusion",
    order_by="start_date DESC, id DESC", check=_check_suspension,
    after_save=_after_suspension, filters=("kind", "status"),
    after_commit=learners.platform_hook("suspension_saved"),
    describe=lambda row: f"{row.get('kind')} from {row.get('start_date')}",
    computed=(("Provision from", _sixth_day),),
    fields=(
        Field("learner_id", "Pupil", "learner", required=True),
        Field("kind", "Type", "choice", ("Suspension", "Permanent exclusion"), required=True,
              default="Suspension"),
        Field("start_date", "Starts", "date", required=True, default=_today),
        Field("days", "School days", "number", help="Suspensions only; halves allowed"),
        Field("return_date", "Returns", "date", form=False),
        Field("reason", "Reason", "choice", EXCLUSION_REASONS, required=True),
        Field("details", "Details", "long", listed=False),
        Field("decided_by", "Decided by (headteacher)", required=True, listed=False),
        Field("parent_notified", "Parents told", "date", required=True, default=_today,
              listed=False),
        Field("la_notified", "Local authority / home school told", "bool", listed=False),
        Field("reintegration_meeting", "Reintegration meeting", "date", listed=False),
        Field("status", "Status", "choice", ("Confirmed", "Under review", "Withdrawn"),
              required=True, default="Confirmed"),
    ),
)
