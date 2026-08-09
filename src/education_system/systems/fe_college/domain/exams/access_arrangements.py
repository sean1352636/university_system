"""Access arrangements — reasonable adjustments for assessment.

JCQ rules require every arrangement to be evidenced, approved before the exam,
and reviewed each series. The extra-time calculation is the one piece of
arithmetic here: it is a percentage of the paper's duration, and getting it
wrong is a reportable malpractice issue.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from education_system.systems.fe_college.domain.students.models import (
    optional_ref,
    ValidationError,
    parse_date,
)

# Arrangement -> the extra-time percentage it carries (0 where it grants none).
ARRANGEMENT_TYPES = {
    "25% extra time": 25,
    "50% extra time": 50,
    "Reader": 0,
    "Scribe": 0,
    "Word processor": 0,
    "Separate room": 0,
    "Rest breaks": 0,
    "Coloured overlay": 0,
    "Prompter": 0,
    "Practical assistant": 0,
    "Bilingual dictionary": 0,
}

APPROVAL_STATUSES = ("requested", "evidence_pending", "approved", "declined", "expired")

EVIDENCE_TYPES = (
    "Specialist assessor report",
    "Educational psychologist report",
    "Medical evidence",
    "EHC Plan",
    "History of need / normal way of working",
)


@dataclass
class AccessArrangement:
    """One approved (or pending) adjustment for one learner."""

    arrangement_id: int | None
    student_id: str
    arrangement_type: str
    status: str = "requested"
    evidence_type: str = ""
    approved_by: str = ""            # staff_id, normally the exams officer
    approved_on: date | None = None
    valid_until: date | None = None
    notes: str = ""

    @property
    def extra_time_pct(self) -> int:
        return ARRANGEMENT_TYPES.get(self.arrangement_type, 0)

    def is_valid(self, on: date | None = None) -> bool:
        """Whether this arrangement may be applied to a sitting."""
        if self.status != "approved":
            return False
        if self.valid_until is None:
            return True
        return (on or date.today()) <= self.valid_until

    def validate(self) -> None:
        if not self.student_id.strip():
            raise ValidationError("An access arrangement needs a student")
        if self.arrangement_type not in ARRANGEMENT_TYPES:
            raise ValidationError(f"Unknown arrangement type '{self.arrangement_type}'")
        if self.status not in APPROVAL_STATUSES:
            raise ValidationError(f"Unknown approval status '{self.status}'")
        if self.evidence_type and self.evidence_type not in EVIDENCE_TYPES:
            raise ValidationError(f"Unknown evidence type '{self.evidence_type}'")
        if self.status == "approved":
            # JCQ requires evidence on file and a named approver before an
            # arrangement is applied — an unevidenced adjustment is malpractice.
            if not self.evidence_type:
                raise ValidationError("An approved arrangement must record its evidence")
            if not self.approved_by.strip():
                raise ValidationError("An approved arrangement must record who approved it")
            if self.approved_on is None:
                raise ValidationError("An approved arrangement must record the approval date")

    def to_row(self) -> dict:
        return {
            "student_id": self.student_id.strip(),
            "arrangement_type": self.arrangement_type,
            "status": self.status,
            "evidence_type": self.evidence_type,
            "approved_by": optional_ref(self.approved_by),
            "approved_on": self.approved_on.isoformat() if self.approved_on else None,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "notes": self.notes.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "AccessArrangement":
        d = dict(row)
        return cls(
            arrangement_id=d.get("arrangement_id"),
            student_id=d.get("student_id") or "",
            arrangement_type=d.get("arrangement_type") or next(iter(ARRANGEMENT_TYPES)),
            status=d.get("status") or "requested",
            evidence_type=d.get("evidence_type") or "",
            approved_by=d.get("approved_by") or "",
            approved_on=parse_date(d.get("approved_on")),
            valid_until=parse_date(d.get("valid_until")),
            notes=d.get("notes") or "",
        )


def adjusted_duration(base_minutes: int, arrangements: list[AccessArrangement],
                      on: date | None = None) -> int:
    """Exam duration in minutes after applying valid extra-time arrangements.

    Extra time does not stack: a learner holding both 25% and 50% gets 50%, the
    higher of the two, per JCQ rules. Rounded up to the whole minute, because
    rounding a candidate's time *down* would disadvantage them.
    """
    if base_minutes <= 0:
        return 0
    pct = max(
        (a.extra_time_pct for a in arrangements if a.is_valid(on)),
        default=0,
    )
    return base_minutes + math.ceil(base_minutes * pct / 100)


__all__ = [
    "APPROVAL_STATUSES",
    "ARRANGEMENT_TYPES",
    "EVIDENCE_TYPES",
    "AccessArrangement",
    "adjusted_duration",
]
