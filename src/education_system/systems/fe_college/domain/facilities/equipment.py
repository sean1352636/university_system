"""Equipment — the kit a college lends and has to keep safe.

Two concerns the model has to carry: loans (who has the laptop) and
inspections (when was the lathe last checked). Both drive the admin
facilities screen, and an overdue inspection is a compliance issue rather
than an inconvenience.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from education_system.systems.fe_college.domain.students.models import (
    optional_ref,
    ValidationError,
    parse_date,
)

EQUIPMENT_CATEGORIES = (
    "IT / Laptop",
    "Workshop machinery",
    "Salon equipment",
    "Catering equipment",
    "Laboratory equipment",
    "Audio-visual",
    "Sports equipment",
    "Assistive technology",
)

EQUIPMENT_STATUSES = ("available", "on_loan", "in_repair", "quarantined", "written_off")

# Categories that must be safety-inspected, with the inspection interval.
INSPECTION_INTERVALS_DAYS = {
    "Workshop machinery": 180,
    "Catering equipment": 365,
    "Laboratory equipment": 365,
    "Salon equipment": 365,
}


@dataclass
class Equipment:
    """One asset the college owns."""

    asset_id: str
    name: str
    category: str = "IT / Laptop"
    status: str = "available"
    room_id: str = ""
    serial_number: str = ""
    purchased_on: date | None = None
    last_inspected: date | None = None
    loaned_to: str = ""              # student_id or staff_id
    loan_due: date | None = None
    notes: str = ""

    @property
    def requires_inspection(self) -> bool:
        return self.category in INSPECTION_INTERVALS_DAYS

    @property
    def next_inspection_due(self) -> date | None:
        if not self.requires_inspection or self.last_inspected is None:
            return None
        return self.last_inspected + timedelta(
            days=INSPECTION_INTERVALS_DAYS[self.category]
        )

    def is_inspection_overdue(self, on: date | None = None) -> bool:
        """Whether a safety inspection is past due.

        Kit that needs inspecting but has *never* been inspected counts as
        overdue — an absent record is the most dangerous case, not the safest.
        """
        if not self.requires_inspection:
            return False
        if self.last_inspected is None:
            return True
        due = self.next_inspection_due
        return due is not None and due < (on or date.today())

    def is_loan_overdue(self, on: date | None = None) -> bool:
        return bool(
            self.status == "on_loan" and self.loan_due and self.loan_due < (on or date.today())
        )

    @property
    def is_usable(self) -> bool:
        return self.status == "available" and not self.is_inspection_overdue()

    def validate(self) -> None:
        if not self.asset_id.strip():
            raise ValidationError("Asset tag is required")
        if not self.name.strip():
            raise ValidationError("Equipment name is required")
        if self.category not in EQUIPMENT_CATEGORIES:
            raise ValidationError(f"Unknown equipment category '{self.category}'")
        if self.status not in EQUIPMENT_STATUSES:
            raise ValidationError(f"Unknown equipment status '{self.status}'")
        if self.status == "on_loan" and not self.loaned_to.strip():
            raise ValidationError("Equipment on loan must record who has it")
        if self.status != "on_loan" and self.loaned_to.strip():
            raise ValidationError(
                "Only equipment marked 'on_loan' can have a borrower — return it first"
            )

    def to_row(self) -> dict:
        return {
            "asset_id": self.asset_id.strip().upper(),
            "name": self.name.strip(),
            "category": self.category,
            "status": self.status,
            "room_id": optional_ref(self.room_id.upper()),
            "serial_number": self.serial_number.strip(),
            "purchased_on": self.purchased_on.isoformat() if self.purchased_on else None,
            "last_inspected": self.last_inspected.isoformat() if self.last_inspected else None,
            "loaned_to": self.loaned_to.strip(),
            "loan_due": self.loan_due.isoformat() if self.loan_due else None,
            "notes": self.notes.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "Equipment":
        d = dict(row)
        return cls(
            asset_id=d.get("asset_id") or "",
            name=d.get("name") or "",
            category=d.get("category") or EQUIPMENT_CATEGORIES[0],
            status=d.get("status") or "available",
            room_id=d.get("room_id") or "",
            serial_number=d.get("serial_number") or "",
            purchased_on=parse_date(d.get("purchased_on")),
            last_inspected=parse_date(d.get("last_inspected")),
            loaned_to=d.get("loaned_to") or "",
            loan_due=parse_date(d.get("loan_due")),
            notes=d.get("notes") or "",
        )


__all__ = [
    "EQUIPMENT_CATEGORIES",
    "EQUIPMENT_STATUSES",
    "INSPECTION_INTERVALS_DAYS",
    "Equipment",
]
