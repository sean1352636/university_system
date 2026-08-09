"""Staff records for the FE College system.

FE staffing is more varied than a school's: alongside full-time lecturers a
college runs sessional tutors paid by the hour and industry assessors who visit
workplaces. The record therefore carries a contracted-hours figure rather than
assuming a full-time teaching load.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from education_system.systems.fe_college.config import (
    EMPLOYMENT_STATUSES,
    FULL_TIME_TEACHING_HOURS,
    STAFF_ROLES,
)
from education_system.systems.fe_college.domain.students.models import (
    ValidationError,
    parse_date,
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Roles that may be timetabled to teach a class. A technician or an
# administrator has a college account but must not appear in the teacher picker.
TEACHING_ROLES = frozenset({
    "Lecturer", "Assessor", "Course Leader", "Curriculum Manager", "Head of Department",
})


@dataclass
class Staff:
    """A member of college staff."""

    staff_id: str
    first_name: str
    last_name: str
    email: str
    role: str = "Lecturer"
    department: str = ""
    employment_status: str = "Full-time"
    contracted_hours: float = FULL_TIME_TEACHING_HOURS
    phone: str = ""
    room: str = ""
    start_date: date | None = None
    end_date: date | None = None
    is_safeguarding_lead: bool = False
    is_exams_officer: bool = False
    dbs_checked: bool = False
    qualifications: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def display_name(self) -> str:
        return f"{self.full_name} ({self.staff_id})"

    @property
    def is_active(self) -> bool:
        return self.employment_status != "Left"

    @property
    def can_teach(self) -> bool:
        return self.is_active and self.role in TEACHING_ROLES

    def validate(self) -> None:
        if not self.staff_id.strip():
            raise ValidationError("Staff ID is required")
        if not self.first_name.strip():
            raise ValidationError("First name is required")
        if not self.last_name.strip():
            raise ValidationError("Last name is required")
        if not self.email.strip():
            raise ValidationError("Email is required")
        if not _EMAIL_RE.match(self.email.strip()):
            raise ValidationError(f"'{self.email}' is not a valid email address")
        if self.role not in STAFF_ROLES:
            raise ValidationError(f"Unknown role '{self.role}'")
        if self.employment_status not in EMPLOYMENT_STATUSES:
            raise ValidationError(f"Unknown employment status '{self.employment_status}'")
        if self.contracted_hours < 0:
            raise ValidationError("Contracted hours cannot be negative")
        if self.contracted_hours > 60:
            raise ValidationError("Contracted hours cannot exceed 60 per week")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("Leaving date cannot be before the start date")
        if self.employment_status == "Left" and self.end_date is None:
            raise ValidationError("A leaver must have a leaving date")

    def to_row(self) -> dict:
        return {
            "staff_id": self.staff_id.strip(),
            "first_name": self.first_name.strip(),
            "last_name": self.last_name.strip(),
            "email": self.email.strip().lower(),
            "role": self.role,
            "department": self.department.strip(),
            "employment_status": self.employment_status,
            "contracted_hours": float(self.contracted_hours),
            "phone": self.phone.strip(),
            "room": self.room.strip(),
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "is_safeguarding_lead": 1 if self.is_safeguarding_lead else 0,
            "is_exams_officer": 1 if self.is_exams_officer else 0,
            "dbs_checked": 1 if self.dbs_checked else 0,
            "qualifications": self.qualifications.strip(),
            "notes": self.notes.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "Staff":
        d = dict(row)
        return cls(
            staff_id=d.get("staff_id") or "",
            first_name=d.get("first_name") or "",
            last_name=d.get("last_name") or "",
            email=d.get("email") or "",
            role=d.get("role") or "Lecturer",
            department=d.get("department") or "",
            employment_status=d.get("employment_status") or "Full-time",
            contracted_hours=float(d.get("contracted_hours") or 0),
            phone=d.get("phone") or "",
            room=d.get("room") or "",
            start_date=parse_date(d.get("start_date")),
            end_date=parse_date(d.get("end_date")),
            is_safeguarding_lead=bool(d.get("is_safeguarding_lead")),
            is_exams_officer=bool(d.get("is_exams_officer")),
            dbs_checked=bool(d.get("dbs_checked")),
            qualifications=d.get("qualifications") or "",
            notes=d.get("notes") or "",
            created_at=d.get("created_at") or "",
            updated_at=d.get("updated_at") or "",
        )


def next_staff_id(existing: list[str]) -> str:
    """Return the next free ``STF-nnnn`` reference."""
    used = [
        int(sid[4:]) for sid in existing
        if sid.startswith("STF-") and sid[4:].isdigit()
    ]
    return f"STF-{(max(used) + 1 if used else 1):04d}"


__all__ = ["TEACHING_ROLES", "Staff", "next_staff_id"]
