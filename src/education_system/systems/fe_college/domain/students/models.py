"""Learner records — the core entity of the FE College system.

An FE learner differs from a school pupil in ways the schema has to carry:
they may be an adult with no parent contact, they hold a Unique Learner Number
(ULN) rather than a UPN, and their funding stream (16-18 vs adult) determines
which statutory return they appear on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from education_system.systems.fe_college.config import (
    ACTIVE_STUDENT_STATUSES,
    LEARNER_TYPES,
    MODES_OF_STUDY,
    STUDENT_STATUSES,
)


class ValidationError(ValueError):
    """Raised when a learner record fails a domain rule.

    Deliberately a ``ValueError`` subclass so interface code that only catches
    ``ValueError`` still surfaces a usable message.
    """


# A ULN is a 10-digit number issued by the Learning Records Service. We accept
# a blank one (applicants often have not been issued theirs yet) but reject a
# malformed one, because a wrong ULN silently corrupts the funding return.
_ULN_RE = re.compile(r"^\d{10}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def parse_date(value: str | date | None) -> date | None:
    """Parse an ISO date, returning None for blank input.

    Raises ValidationError on a non-empty value that isn't an ISO date, so a
    typo in a GUI field is reported rather than silently stored as NULL.
    """
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise ValidationError(f"'{value}' is not a valid date (expected YYYY-MM-DD)") from exc


def optional_ref(value: str) -> str | None:
    """Normalise a blank foreign-key reference to NULL.

    SQLite treats ``''`` as a value rather than a missing one, so writing an
    empty string into an optional reference column (an unassigned tutor, an
    unbooked room) fails the foreign-key check instead of simply recording
    that nothing is referenced. Every optional FK goes through here.
    """
    text = (value or "").strip()
    return text or None


def age_on(dob: date | None, on: date | None = None) -> int | None:
    """Age in whole years on ``on`` (default today), or None without a DOB."""
    if dob is None:
        return None
    ref = on or date.today()
    return ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))


@dataclass
class Student:
    """A learner on roll (or an applicant who is not yet).

    ``student_id`` is the college's own reference (e.g. ``FE24-0001``);
    ``uln`` is the national identifier used on funding returns.
    """

    student_id: str
    first_name: str
    last_name: str
    date_of_birth: date | None = None
    uln: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""
    postcode: str = ""
    learner_type: str = LEARNER_TYPES[0]
    mode_of_study: str = MODES_OF_STUDY[0]
    status: str = "applicant"
    tutor_group: str = ""
    personal_tutor: str = ""          # staff_id of the assigned personal tutor
    start_date: date | None = None
    end_date: date | None = None
    prior_attainment: str = ""
    has_ehcp: bool = False            # Education, Health and Care Plan
    learning_support: str = ""
    emergency_contact_name: str = ""
    emergency_contact_phone: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    # ── Derived ────────────────────────────────────────────────────────────

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def display_name(self) -> str:
        """Name with the college reference, as shown in pickers and headers."""
        return f"{self.full_name} ({self.student_id})"

    @property
    def age(self) -> int | None:
        return age_on(self.date_of_birth)

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STUDENT_STATUSES

    @property
    def is_adult_learner(self) -> bool:
        """19+ on entry — drives the Adult Skills Fund stream, not 16-18."""
        a = age_on(self.date_of_birth, self.start_date or date.today())
        return a is not None and a >= 19

    # ── Rules ──────────────────────────────────────────────────────────────

    def validate(self) -> None:
        """Raise ValidationError if this record breaks a domain rule."""
        if not self.student_id.strip():
            raise ValidationError("Student ID is required")
        if not self.first_name.strip():
            raise ValidationError("First name is required")
        if not self.last_name.strip():
            raise ValidationError("Last name is required")
        if self.status not in STUDENT_STATUSES:
            raise ValidationError(
                f"Unknown status '{self.status}' — expected one of {', '.join(STUDENT_STATUSES)}"
            )
        if self.learner_type not in LEARNER_TYPES:
            raise ValidationError(f"Unknown learner type '{self.learner_type}'")
        if self.mode_of_study not in MODES_OF_STUDY:
            raise ValidationError(f"Unknown mode of study '{self.mode_of_study}'")
        if self.uln and not _ULN_RE.match(self.uln.strip()):
            raise ValidationError("ULN must be exactly 10 digits")
        if self.email and not _EMAIL_RE.match(self.email.strip()):
            raise ValidationError(f"'{self.email}' is not a valid email address")
        if self.date_of_birth and self.date_of_birth > date.today():
            raise ValidationError("Date of birth cannot be in the future")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date cannot be before the start date")
        # An FE college may enrol from 14 (school-link provision) upwards.
        # Anything younger is a data-entry error, not a real learner.
        a = age_on(self.date_of_birth, self.start_date or date.today())
        if a is not None and a < 14:
            raise ValidationError(
                f"Learner would be {a} on entry — FE enrolment starts at 14"
            )

    # ── Serialisation ──────────────────────────────────────────────────────

    def to_row(self) -> dict:
        """Flatten to the column dict the repository writes."""
        return {
            "student_id": self.student_id.strip(),
            "first_name": self.first_name.strip(),
            "last_name": self.last_name.strip(),
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "uln": self.uln.strip(),
            "email": self.email.strip(),
            "phone": self.phone.strip(),
            "address": self.address.strip(),
            "postcode": self.postcode.strip().upper(),
            "learner_type": self.learner_type,
            "mode_of_study": self.mode_of_study,
            "status": self.status,
            "tutor_group": self.tutor_group.strip(),
            "personal_tutor": optional_ref(self.personal_tutor),
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "prior_attainment": self.prior_attainment.strip(),
            "has_ehcp": 1 if self.has_ehcp else 0,
            "learning_support": self.learning_support.strip(),
            "emergency_contact_name": self.emergency_contact_name.strip(),
            "emergency_contact_phone": self.emergency_contact_phone.strip(),
            "notes": self.notes.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "Student":
        """Build from a ``sqlite3.Row`` (or any mapping)."""
        d = dict(row)
        return cls(
            student_id=d.get("student_id") or "",
            first_name=d.get("first_name") or "",
            last_name=d.get("last_name") or "",
            date_of_birth=parse_date(d.get("date_of_birth")),
            uln=d.get("uln") or "",
            email=d.get("email") or "",
            phone=d.get("phone") or "",
            address=d.get("address") or "",
            postcode=d.get("postcode") or "",
            learner_type=d.get("learner_type") or LEARNER_TYPES[0],
            mode_of_study=d.get("mode_of_study") or MODES_OF_STUDY[0],
            status=d.get("status") or "applicant",
            tutor_group=d.get("tutor_group") or "",
            personal_tutor=d.get("personal_tutor") or "",
            start_date=parse_date(d.get("start_date")),
            end_date=parse_date(d.get("end_date")),
            prior_attainment=d.get("prior_attainment") or "",
            has_ehcp=bool(d.get("has_ehcp")),
            learning_support=d.get("learning_support") or "",
            emergency_contact_name=d.get("emergency_contact_name") or "",
            emergency_contact_phone=d.get("emergency_contact_phone") or "",
            notes=d.get("notes") or "",
            created_at=d.get("created_at") or "",
            updated_at=d.get("updated_at") or "",
        )


def next_student_id(existing: list[str], year: int | None = None) -> str:
    """Return the next free ``FE<yy>-<nnnn>`` reference for the intake year.

    Sequence numbers restart each academic year, so the reference itself tells
    an administrator which cohort a learner belongs to.
    """
    yy = f"{(year or date.today().year) % 100:02d}"
    prefix = f"FE{yy}-"
    used = [
        int(sid[len(prefix):])
        for sid in existing
        if sid.startswith(prefix) and sid[len(prefix):].isdigit()
    ]
    return f"{prefix}{(max(used) + 1 if used else 1):04d}"


__all__ = [
    "Student",
    "ValidationError",
    "age_on",
    "next_student_id",
    "parse_date",
]
