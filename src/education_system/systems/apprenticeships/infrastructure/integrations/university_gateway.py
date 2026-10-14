"""Read-only boundary onto university-owned degree information.

The gateway deliberately exposes summaries, not write methods. Apprenticeships
may display and reconcile academic progress, but the university remains the
only owner of registration, credits, results and degree completion.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system import paths


class UniversityGatewayError(ValueError):
    """The requested university registration cannot be resolved safely."""


@dataclass(frozen=True)
class UniversityRegistration:
    student_id: str
    journey_id: str | None
    student_name: str
    student_status: str | None
    degree_program_id: int
    degree_program_code: str
    degree_program_name: str
    credits_required: float
    credits_earned: float
    academic_status: str | None
    completion_percentage: float


class UniversityGateway:
    """Queries the canonical university database without mutating it."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or paths.UNIVERSITY_DEFAULT_DB_PATH)

    def registration(self, student_id: str, degree_program_id: int) -> UniversityRegistration:
        if not self.db_path.exists():
            raise UniversityGatewayError(f"University database not found at {self.db_path}")
        uri = f"file:{self.db_path.resolve()}?mode=ro"
        try:
            conn = sqlite3.connect(uri, uri=True)
            conn.row_factory = sqlite3.Row
            try:
                student = conn.execute(
                    """SELECT student_id, first_name, last_name, status, journey_id
                         FROM students WHERE student_id=?""", (student_id,)
                ).fetchone()
                degree = conn.execute(
                    """SELECT program_id, program_code, program_name, total_credits_required
                         FROM degree_programs WHERE program_id=? AND is_active=1""",
                    (degree_program_id,),
                ).fetchone()
                progress = conn.execute(
                    """SELECT total_credits_earned, completion_percentage, status
                         FROM student_degree_progress
                        WHERE student_id=? AND program_id=?
                        ORDER BY last_updated DESC LIMIT 1""",
                    (student_id, degree_program_id),
                ).fetchone()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise UniversityGatewayError(f"University academic record is unavailable: {exc}") from exc
        if student is None:
            raise UniversityGatewayError(f"No university student {student_id}")
        if degree is None:
            raise UniversityGatewayError(f"No active university degree programme {degree_program_id}")
        return UniversityRegistration(
            student_id=str(student["student_id"]), journey_id=student["journey_id"],
            student_name=f"{student['first_name']} {student['last_name']}".strip(),
            student_status=student["status"], degree_program_id=int(degree["program_id"]),
            degree_program_code=str(degree["program_code"]),
            degree_program_name=str(degree["program_name"]),
            credits_required=float(degree["total_credits_required"] or 0),
            credits_earned=float(progress["total_credits_earned"] or 0) if progress else 0.0,
            academic_status=progress["status"] if progress else None,
            completion_percentage=float(progress["completion_percentage"] or 0) if progress else 0.0,
        )


def as_dict(registration: UniversityRegistration) -> dict[str, Any]:
    """Stable presentation shape for CLI, GUI and eventual API callers."""
    return {name: getattr(registration, name) for name in registration.__dataclass_fields__}
