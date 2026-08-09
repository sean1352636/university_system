"""Event names and versioned integration payload contracts."""
from __future__ import annotations
from typing import Any, Literal, NotRequired, TypedDict
from education_system.systems.university.services.events.in_process import (
    EVENT_CASE_OPENED, EVENT_CERT_CHANGED, EVENT_CHARGE_RAISED,
    EVENT_COURSE_CHANGED, EVENT_ENROLMENT_CHANGED, EVENT_EXAM_CHANGED,
    EVENT_INCIDENT_LOGGED, EVENT_MODULE_SCHEDULE_CHANGED,
    EVENT_SELECTION_CHANGED, EVENT_STAFF_AVAILABILITY_CHANGED,
    EVENT_TERM_CHANGED,
)

CONTRACT_VERSION = 1

class IntegrationPayloadV1(TypedDict, total=False):
    contract_version: Literal[1]
    action: str
    student_id: str
    course_code: str
    source: str

EventPayload = IntegrationPayloadV1 | dict[str, Any]

__all__ = [name for name in globals() if name.startswith("EVENT_")] + [
    "CONTRACT_VERSION", "IntegrationPayloadV1", "EventPayload",
]
