"""Referrals from FE College: adults a linked college sent to this service.

FE College refers an adult through the platform
(``platform.cross_system.adult_education_applications``): to a community
English, maths, ESOL or digital skills course, or a part-time course. The
adult education adapter finds the learner (or adds them as an Enquiry)
and records the referral here. The service works it like an enquiry:

* **Declined** or **Withdrawn** (with the reason) goes back to the college;
* enrolling the learner on a class (:mod:`modules.enrolments`) marks the
  referral **Enrolled** and tells the college - the FE place stays open.

A referral can also be recorded by hand (a college not on the platform):
it is the same record without a platform link.
"""

from __future__ import annotations

from datetime import date

from education_system.systems.adult_education.core import records as r
from education_system.systems.adult_education.core.records import Field, RecordType, ValidationError
from education_system.systems.adult_education.modules import learners

STATUSES = ("New", "Contacted", "Booked on IAG", "Enrolled", "Declined", "Withdrawn")
OPEN_STATUSES = ("New", "Contacted", "Booked on IAG")
CLOSED_STATUSES = ("Declined", "Withdrawn")
SOURCES = {"fe_college": "FE College"}


def _today() -> str:
    return date.today().isoformat()


def _check(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    received = r.to_date(r.parse_date(merged.get("received")))
    if received and received > date.today():
        raise ValidationError("The date received can't be in the future.")
    if merged.get("status") in CLOSED_STATUSES and not (merged.get("decision_reason")
                                                         or "").strip():
        raise ValidationError(f"Say why the referral is {merged['status'].lower()} - the "
                              "college is told.")
    was = (old or {}).get("status")
    if was in ("Enrolled", *CLOSED_STATUSES) and merged.get("status") != was and \
            merged.get("transition_id"):
        raise ValidationError(f"This referral is {was.lower()} and the college has been "
                              "told. Record a new referral instead.")


def _source_label(row: dict) -> str:
    return SOURCES.get(row.get("source_system") or "", "")


FE_REFERRALS = RecordType(
    key="fe_referrals", title="Referrals from FE College", singular="referral",
    order_by="received DESC, id DESC", check=_check, filters=("status",),
    after_commit=learners.platform_hook("referral_saved"),
    describe=lambda row: (f"{row.get('course') or 'Referral'} ({row.get('status')})"),
    computed=(("Linked college", _source_label),),
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("received", "Received", "date", required=True, default=_today),
        Field("college", "From college", required=True, default="FE College"),
        Field("course", "Course or subject asked for", required=True),
        Field("course_id", "Our course", "ref", ref="courses", listed=False),
        Field("reason", "Reason", "long", listed=False),
        Field("intended_start", "Intended start", "date"),
        Field("referrer", "Referred by (name)", listed=False),
        Field("status", "Status", "choice", STATUSES, required=True, default="New"),
        Field("decision_reason", "Declined / withdrawn because", listed=False),
        # Set by the platform for a linked college's referral.
        Field("source_system", "Linked college", form=False, listed=False),
        Field("transition_id", "Platform referral", form=False, listed=False),
        Field("consent_to_share", "Learner consented to sharing", "bool", form=False,
              listed=False),
        Field("safeguarding_ref", "Safeguarding file reference", form=False, listed=False),
    ),
)


def for_transition(transition_id: str) -> dict | None:
    rows = r.list_records(FE_REFERRALS, equals={"transition_id": transition_id})
    return rows[0] if rows else None


def open_linked(learner_id: int) -> list[dict]:
    """The learner's open referrals from a linked college."""
    return [x for x in r.list_records(FE_REFERRALS, learner_id=learner_id)
            if x.get("transition_id") and x.get("status") in OPEN_STATUSES]
