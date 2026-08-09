"""Teaching workload — hours assigned against hours contracted.

The workload report is the one screen a curriculum manager looks at every week,
so the arithmetic lives here rather than in a view: assigned teaching hours per
week, compared to the contracted figure, banded into under-used / balanced /
over-allocated.
"""

from __future__ import annotations

from dataclasses import dataclass

from education_system.systems.fe_college.config import FULL_TIME_TEACHING_HOURS

# Tolerance around the contracted figure that still counts as "balanced".
# Timetables never land exactly on a contracted number, and flagging a lecturer
# half an hour over would make the report useless.
_TOLERANCE_HOURS = 2.0


@dataclass(frozen=True)
class Workload:
    """One member of staff's assigned teaching load for a week."""

    staff_id: str
    staff_name: str = ""
    contracted_hours: float = FULL_TIME_TEACHING_HOURS
    assigned_hours: float = 0.0
    class_count: int = 0
    course_count: int = 0

    @property
    def variance(self) -> float:
        """Assigned minus contracted; positive means over-allocated."""
        return round(self.assigned_hours - self.contracted_hours, 2)

    @property
    def utilisation_pct(self) -> float | None:
        """Assigned as a share of contracted; None on a zero contract.

        Sessional staff can legitimately hold a zero contract (paid per hour as
        work arises), and dividing by it would crash the report.
        """
        if self.contracted_hours <= 0:
            return None
        return round(self.assigned_hours / self.contracted_hours * 100, 1)

    @property
    def band(self) -> str:
        if self.contracted_hours <= 0:
            return "sessional"
        v = self.variance
        if v > _TOLERANCE_HOURS:
            return "over-allocated"
        if v < -_TOLERANCE_HOURS:
            return "under-allocated"
        return "balanced"

    @property
    def is_over_allocated(self) -> bool:
        return self.band == "over-allocated"


def summarise(workloads: list[Workload]) -> dict[str, float | int]:
    """Department-level totals for the workload report header."""
    if not workloads:
        return {
            "staff": 0, "assigned_hours": 0.0, "contracted_hours": 0.0,
            "over_allocated": 0, "under_allocated": 0, "utilisation_pct": 0.0,
        }
    assigned = sum(w.assigned_hours for w in workloads)
    contracted = sum(w.contracted_hours for w in workloads)
    return {
        "staff": len(workloads),
        "assigned_hours": round(assigned, 1),
        "contracted_hours": round(contracted, 1),
        "over_allocated": sum(1 for w in workloads if w.band == "over-allocated"),
        "under_allocated": sum(1 for w in workloads if w.band == "under-allocated"),
        "utilisation_pct": round(assigned / contracted * 100, 1) if contracted else 0.0,
    }


__all__ = ["Workload", "summarise"]
