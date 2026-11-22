"""Who is involved: external professionals, referrals to them, and meetings."""

from __future__ import annotations

import re
from datetime import date

from education_system.systems.special_education.core import records as r
from education_system.systems.special_education.core.records import Field, RecordType, ValidationError

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ROLES = ("Educational psychologist", "Speech & language therapist", "Occupational therapist",
         "Physiotherapist", "CAMHS", "Specialist teacher (sensory)", "Specialist teacher (other)",
         "Paediatrician", "School nurse", "Social worker", "LA SEN caseworker", "Other")


def _today() -> str:
    return date.today().isoformat()


def _check_professional(values: dict, _old: dict | None) -> None:
    if values.get("email") and not _EMAIL.match(values["email"]):
        raise ValidationError(f"'{values['email']}' doesn't look like an e-mail address.")


PROFESSIONALS = RecordType(
    key="professionals", title="Professionals Directory", singular="professional",
    order_by="name", check=_check_professional, filters=("role",),
    describe=lambda row: f"{row.get('name')} ({row.get('role')})",
    fields=(
        Field("name", "Name", required=True),
        Field("role", "Role", "choice", ROLES, required=True),
        Field("organisation", "Organisation"),
        Field("phone", "Phone"),
        Field("email", "E-mail"),
        Field("notes", "Notes", "long", listed=False),
    ),
)


def _check_involvement(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    referred = r.to_date(r.parse_date(merged.get("referred_on")))
    report = r.to_date(r.parse_date(merged.get("report_received")))
    if referred and report and report < referred:
        raise ValidationError("A report can't arrive before the referral.")


INVOLVEMENT = RecordType(
    key="involvement", title="Referrals & Involvement", singular="referral",
    order_by="status, referred_on DESC", check=_check_involvement, filters=("status",),
    describe=lambda row: f"Referral {row.get('referred_on')}",
    computed=(("Waiting", lambda row: (f"{(date.today() - date.fromisoformat(row['referred_on'])).days}d"
                                       if row.get("status") in ("Referred", "Waiting list")
                                       and row.get("referred_on") else "")),),
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("professional_id", "Professional", "ref", ref="professionals", required=True),
        Field("referred_on", "Referred", "date", required=True, default=_today),
        Field("reason", "Reason", "long", listed=False),
        Field("status", "Status", "choice", ("Referred", "Waiting list", "Active", "Discharged",
                                             "Declined"), required=True, default="Referred"),
        Field("report_received", "Report received", "date"),
        Field("recommendations", "Recommendations", "long", listed=False),
    ),
)


def _check_meeting(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    held = r.to_date(r.parse_date(merged.get("meeting_date")))
    nxt = r.to_date(r.parse_date(merged.get("next_meeting")))
    if held and nxt and nxt <= held:
        raise ValidationError("The next meeting must be after this one.")


MEETINGS = RecordType(
    key="meetings", title="Meetings", singular="meeting", order_by="meeting_date DESC",
    check=_check_meeting, filters=("meeting_type",),
    describe=lambda row: f"{row.get('meeting_type')} {row.get('meeting_date')}",
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("meeting_date", "Date", "date", required=True, default=_today),
        Field("meeting_type", "Type", "choice",
              ("Support plan review", "EHCP annual review", "Multi-agency (TAC / MDT)",
               "Parent / carer meeting", "Transition meeting", "Other"), required=True),
        Field("attendees", "Attendees"),
        Field("notes", "Notes", "long", listed=False),
        Field("actions", "Actions agreed", "long", listed=False),
        Field("next_meeting", "Next meeting", "date"),
    ),
)
