"""School requests: what a linked school asked the SEND service for.

A Primary or Secondary school on the platform sends a request
(``platform.cross_system.send_referrals``): SEND advice and support, or an
EHC needs assessment request. The SEND adapter puts the pupil on the
register (or finds them) and records the request here; an assessment
request also opens an EHCP at *Requested* (:mod:`modules.ehcp`), whose
stages then go back to the school.

A request can also be recorded by hand (a school not on the platform, a
phone call): it is the same record without a platform link.
"""

from __future__ import annotations

from datetime import date

from education_system.systems.special_education.core import records as r
from education_system.systems.special_education.core.records import Field, RecordType, ValidationError

ADVICE = "SEND advice and support"
EHCNA = "EHC needs assessment request"
KINDS = (ADVICE, EHCNA, "Other")
STATUSES = ("New", "In progress", "Done")
SOURCES = {"primary": "Primary School", "secondary": "Secondary School"}


def _today() -> str:
    return date.today().isoformat()


def _check(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    received = r.to_date(r.parse_date(merged.get("received")))
    if received and received > date.today():
        raise ValidationError("The date received can't be in the future.")
    if merged.get("status") == "Done" and not merged.get("outcome"):
        raise ValidationError("Say what was done before closing the request.")


def _source_label(row: dict) -> str:
    return SOURCES.get(row.get("source_system") or "", "")


SCHOOL_REQUESTS = RecordType(
    key="school_requests", title="School Requests", singular="school request",
    order_by="received DESC, id DESC", check=_check, filters=("request", "status"),
    describe=lambda row: (f"{row.get('learner_name') or 'Request'} - "
                          f"{row.get('request') or ''} ({row.get('status')})"),
    computed=(("Linked school", _source_label),),
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("received", "Received", "date", required=True, default=_today),
        Field("school", "From school / setting", required=True),
        Field("request", "Request", "choice", KINDS, required=True, default=ADVICE),
        Field("referrer", "Referred by (name)"),
        Field("summary", "Why", "long", listed=False),
        Field("tried", "What the school has tried", "long", listed=False),
        Field("status", "Status", "choice", STATUSES, required=True, default="New"),
        Field("outcome", "Outcome", "long", listed=False),
        # Set by the platform for a linked school's request.
        Field("source_system", "Linked school", form=False, listed=False),
        Field("transition_id", "Platform request", form=False, listed=False),
        Field("consent_to_share", "Parent consented to sharing", "bool", form=False,
              listed=False),
        Field("safeguarding_ref", "Safeguarding file reference", form=False, listed=False),
    ),
)


def for_transition(transition_id: str) -> dict | None:
    rows = r.list_records(SCHOOL_REQUESTS, equals={"transition_id": transition_id})
    return rows[0] if rows else None
