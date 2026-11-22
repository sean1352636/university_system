"""Referrals into AP and the risk assessment done before (and during) a placement.

Rules:

* a referral can't be dated in the future, and a pupil has at most one open
  referral (New, Triage or Waiting list) at a time;
* an exclusion referral (permanent exclusion or a long suspension) needs the
  first day of the exclusion: the local authority (permanent exclusion) or
  school (suspension) must arrange full-time education from the **sixth
  school day**, which is worked out and tracked until a placement starts;
* a decision (Accepted, Declined, Withdrawn) is dated, and a decline needs a
  reason; a decided referral can only be reopened to the Waiting list;
* a risk assessment's overall rating is the highest of its areas; a High
  rating needs control measures; a new current assessment supersedes the old.
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

REASONS = ("Permanent exclusion", "Suspension (sixth-day provision)",
           "At risk of permanent exclusion", "Health needs (unable to attend school)",
           "Managed move", "No school place", "Other")
EXCLUSION_REASONS = frozenset(REASONS[:2])
STATUSES = ("New", "Triage", "Waiting list", "Accepted", "Declined", "Withdrawn")
OPEN = frozenset({"New", "Triage", "Waiting list"})
DECIDED = frozenset({"Accepted", "Declined", "Withdrawn"})
RISK = ("Low", "Medium", "High")
RISK_AREAS = (("risk_to_self", "Risk to self"), ("risk_to_others", "Risk to other pupils"),
              ("risk_to_staff", "Risk to staff"), ("absconding", "Absconding"),
              ("exploitation", "Exploitation (CCE / CSE)"))


def _today() -> str:
    return date.today().isoformat()


def sixth_day(row: dict) -> date | None:
    """When full-time provision must start for an exclusion referral."""
    start = r.to_date(row.get("excluded_from"))
    if row.get("reason") not in EXCLUSION_REASONS or start is None:
        return None
    return dates.school_day(start, 6)


def _check_referral(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    received = r.to_date(merged.get("received"))
    if received and received > date.today():
        raise ValidationError("A referral can't be dated in the future.")
    if merged.get("reason") in EXCLUSION_REASONS and not merged.get("excluded_from"):
        raise ValidationError("Give the first day of the exclusion: provision has to start "
                              "by the sixth school day.")
    new, was = merged.get("status"), (old or {}).get("status")
    if new in DECIDED and new != was:
        if not merged.get("decision_date"):
            values["decision_date"] = _today()
        if new == "Declined" and not merged.get("decision_reason"):
            raise ValidationError("Give the reason for declining the referral.")
    if was in DECIDED and new != was and new != "Waiting list":
        article = "An" if was[0] in "AEIOU" else "A"
        raise ValidationError(f"{article} {was.lower()} referral can only be reopened to the "
                              "Waiting list.")
    if new in OPEN:
        values["decision_date"] = None if was in DECIDED else merged.get("decision_date")
        with db.connect() as conn:
            clash = conn.execute(
                "SELECT received FROM referrals WHERE learner_id = ? AND status IN "
                "('New', 'Triage', 'Waiting list') AND id IS NOT ?",
                (merged["learner_id"], (old or {}).get("id"))).fetchone()
        if clash:
            raise ValidationError("This pupil already has an open referral (received "
                                  f"{dates.uk(r.to_date(clash[0]))}). Update that one.")
    decided = r.to_date(values.get("decision_date", merged.get("decision_date")))
    if decided and received and decided < received:
        raise ValidationError("The decision can't be before the referral was received.")
    if merged.get("transition_id") and was in DECIDED and new != was:
        raise ValidationError("This referral came from a school on the platform and has "
                              "been decided there: the school would have to refer again.")


def has_active_placement(learner_id: int, by: date | None = None) -> bool:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM placements WHERE learner_id = ? AND status IN ('Active', 'Ended') "
            "AND start_date <= ?", (learner_id, (by or date.max).isoformat())).fetchone()
    return row is not None


def day6_flag(row: dict) -> str:
    due = sixth_day(row)
    if due is None or row.get("status") in ("Declined", "Withdrawn"):
        return ""
    if has_active_placement(row["learner_id"], due):
        return f"{dates.uk(due)} met"
    late = date.today() > due
    return f"{dates.uk(due)}{' - OVERDUE' if late else ''}"


SOURCES = {"primary": "Primary School", "secondary": "Secondary School"}


def _platform_hook(row: dict, old: dict | None) -> list[str] | None:
    from education_system.systems.alternative_provision.infrastructure import platform_link
    return platform_link.referral_saved(row, old)


def source_label(row: dict) -> str:
    system = row.get("source_system")
    return f"{SOURCES.get(system, system)} (linked)" if system else ""


REFERRALS = RecordType(
    key="referrals", title="Referrals", singular="referral",
    order_by="received DESC, id DESC", check=_check_referral,
    after_commit=_platform_hook,
    filters=("status", "reason"),
    describe=lambda row: f"{row.get('learner_name') or ''}: {row.get('reason')} "
                         f"({row.get('status')})",
    computed=(("Sixth day", day6_flag), ("Linked school", source_label)),
    fields=(
        Field("learner_id", "Pupil", "learner", required=True),
        Field("received", "Received", "date", required=True, default=_today),
        Field("referred_by", "Referred by", required=True,
              help="School or local authority team"),
        Field("referrer_name", "Referrer's name", listed=False),
        Field("referrer_contact", "Referrer's phone / e-mail", listed=False),
        Field("reason", "Reason", "choice", REASONS, required=True),
        Field("excluded_from", "Exclusion starts", "date",
              help="First day of the exclusion (exclusion referrals only)"),
        Field("summary", "Background", "long", listed=False),
        Field("previous_provision", "Previous provision / schools", "long", listed=False),
        Field("status", "Status", "choice", STATUSES, required=True, default="New"),
        Field("decision_date", "Decided", "date", listed=False),
        Field("decision_by", "Decided by", listed=False),
        Field("decision_reason", "Decision reason", "long", listed=False),
        # Referrals sent by a school on the platform (platform.cross_system.ap_referrals).
        Field("registration", "Registration", "choice", ("Dual", "Sole"), listed=False,
              help="Dual: stays on the school's roll; Sole: comes off it"),
        Field("source_system", "Referring system", form=False, listed=False),
        Field("transition_id", "Platform transfer", form=False, listed=False),
        Field("consent_to_share", "Parent consented to share SEN / medical", "bool",
              form=False, listed=False),
        Field("safeguarding_ref", "Safeguarding file reference", form=False, listed=False),
    ),
)


def _check_risk(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    levels = [merged.get(name) or "Low" for name, _ in RISK_AREAS]
    values["overall"] = max(levels, key=RISK.index)
    if values["overall"] == "High" and not merged.get("controls"):
        raise ValidationError("A High risk needs the control measures recorded.")
    done, review = r.to_date(merged.get("assessed_on")), r.to_date(merged.get("review_date"))
    if done and done > date.today():
        raise ValidationError("An assessment can't be dated in the future.")
    if done and review and review <= done:
        raise ValidationError("The review date must be after the assessment.")
    if done and not review:
        values["review_date"] = dates.add_months(done, 3).isoformat()


def _after_risk(conn, row: dict, _old: dict | None) -> None:
    if row["status"] == "Current":
        conn.execute("UPDATE risk_assessments SET status = 'Superseded', updated_at = "
                     "datetime('now') WHERE learner_id = ? AND id != ? AND status = 'Current'",
                     (row["learner_id"], row["id"]))


RISK_ASSESSMENTS = RecordType(
    key="risk_assessments", title="Risk Assessments", singular="risk assessment",
    order_by="assessed_on DESC, id DESC", check=_check_risk, after_save=_after_risk,
    filters=("overall", "status"),
    describe=lambda row: f"{row.get('assessed_on')} - {row.get('overall')} risk",
    fields=(
        Field("learner_id", "Pupil", "learner", required=True),
        Field("assessed_on", "Assessed", "date", required=True, default=_today),
        Field("assessed_by", "Assessed by"),
        *(Field(name, label, "choice", RISK, required=True, default="Low", listed=False)
          for name, label in RISK_AREAS),
        Field("overall", "Overall", form=False),
        Field("triggers", "Known triggers", "long", listed=False),
        Field("controls", "Control measures", "long", listed=False,
              help="Required for a High rating"),
        Field("review_date", "Review by", "date",
              help="Left blank: three months after the assessment"),
        Field("status", "Status", "choice", ("Current", "Superseded"), required=True,
              default="Current"),
    ),
)


def current_risk(learner_id: int) -> dict | None:
    rows = r.list_records(RISK_ASSESSMENTS, learner_id=learner_id,
                          equals={"status": "Current"})
    return rows[0] if rows else None
