"""Needs profile: each identified need, by the SEND Code of Practice's four broad areas."""

from __future__ import annotations

from datetime import date

from education_system.systems.special_education.core import records as r
from education_system.systems.special_education.core.records import Field, RecordType, ValidationError

AREAS = (
    "Communication and interaction",
    "Cognition and learning",
    "Social, emotional and mental health",
    "Sensory and/or physical",
)


def _check(values: dict, old: dict | None) -> None:
    merged = {**(old or {}), **values}
    if merged.get("diagnosis_date") and not merged.get("diagnosed"):
        values["diagnosed"] = 1
    d = r.to_date(r.parse_date(merged.get("diagnosis_date")))
    if d and d > date.today():
        raise ValidationError("Diagnosis date can't be in the future.")


NEEDS = RecordType(
    key="needs", title="Needs Profile", singular="need", order_by="learner_id, area",
    check=_check, filters=("area", "status"),
    describe=lambda row: f"{row.get('need')} ({row.get('area')})",
    fields=(
        Field("learner_id", "Learner", "learner", required=True),
        Field("area", "Broad area of need", "choice", AREAS, required=True),
        Field("need", "Need", required=True, help="e.g. dyslexia, anxiety, hearing loss"),
        Field("description", "How it affects learning", "long", listed=False),
        Field("what_helps", "What helps", "long", listed=False),
        Field("diagnosed", "Formal diagnosis", "bool"),
        Field("diagnosed_by", "Diagnosed by", listed=False),
        Field("diagnosis_date", "Diagnosis date", "date", listed=False),
        Field("identified_on", "Identified", "date", default=lambda: date.today().isoformat()),
        Field("status", "Status", "choice", ("Current", "Resolved"), required=True,
              default="Current"),
    ),
)
