"""Rooms — the teaching spaces a timetable is placed into.

FE rooms are not interchangeable: a hairdressing salon, a motor-vehicle
workshop and an IT suite each suit particular courses, so a room carries a type
that the timetable screen filters on before offering it.
"""

from __future__ import annotations

from dataclasses import dataclass

from education_system.systems.fe_college.config import ROOM_TYPES
from education_system.systems.fe_college.domain.students.models import ValidationError

ROOM_STATUSES = ("available", "in_maintenance", "closed")


@dataclass
class Room:
    """One teaching space."""

    room_id: str
    name: str
    room_type: str = "Classroom"
    capacity: int = 0
    building: str = ""
    floor: str = ""
    campus: str = "Main Campus"
    status: str = "available"
    has_projector: bool = True
    is_accessible: bool = True
    notes: str = ""

    @property
    def display_name(self) -> str:
        return f"{self.room_id} — {self.name} ({self.room_type}, {self.capacity})"

    @property
    def is_bookable(self) -> bool:
        return self.status == "available"

    def fits(self, headcount: int) -> bool:
        """Whether a group of ``headcount`` fits — a hard capacity limit.

        Room capacities in a college are fire-safety limits, not guidance, so
        this is a strict comparison.
        """
        return self.capacity > 0 and headcount <= self.capacity

    def validate(self) -> None:
        if not self.room_id.strip():
            raise ValidationError("Room code is required")
        if not self.name.strip():
            raise ValidationError("Room name is required")
        if self.room_type not in ROOM_TYPES:
            raise ValidationError(f"Unknown room type '{self.room_type}'")
        if self.status not in ROOM_STATUSES:
            raise ValidationError(f"Unknown room status '{self.status}'")
        if self.capacity < 0:
            raise ValidationError("Room capacity cannot be negative")

    def to_row(self) -> dict:
        return {
            "room_id": self.room_id.strip().upper(),
            "name": self.name.strip(),
            "room_type": self.room_type,
            "capacity": int(self.capacity),
            "building": self.building.strip(),
            "floor": self.floor.strip(),
            "campus": self.campus.strip(),
            "status": self.status,
            "has_projector": 1 if self.has_projector else 0,
            "is_accessible": 1 if self.is_accessible else 0,
            "notes": self.notes.strip(),
        }

    @classmethod
    def from_row(cls, row) -> "Room":
        d = dict(row)
        return cls(
            room_id=d.get("room_id") or "",
            name=d.get("name") or "",
            room_type=d.get("room_type") or "Classroom",
            capacity=int(d.get("capacity") or 0),
            building=d.get("building") or "",
            floor=d.get("floor") or "",
            campus=d.get("campus") or "Main Campus",
            status=d.get("status") or "available",
            has_projector=bool(d.get("has_projector", 1)),
            is_accessible=bool(d.get("is_accessible", 1)),
            notes=d.get("notes") or "",
        )


__all__ = ["ROOM_STATUSES", "Room"]
