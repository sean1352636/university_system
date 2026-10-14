"""Persistence for degree-apprenticeship associations (never academic data)."""

from __future__ import annotations

from typing import Any

from education_system.systems.apprenticeships.domain.degree_apprenticeships.links import (
    DegreeApprenticeshipLink,
    DegreeApprenticeshipProgramme,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    connect,
    init_db,
)


def _programme(row: Any) -> DegreeApprenticeshipProgramme:
    return DegreeApprenticeshipProgramme(
        apprenticeship_programme_id=row["apprenticeship_programme_id"],
        university_degree_program_id=row["university_degree_program_id"],
        credits_required=row["credits_required"],
        integration_type=row["integration_type"],
        active=bool(row["active"]),
    )


def _link(row: Any) -> DegreeApprenticeshipLink:
    return DegreeApprenticeshipLink(
        link_id=row["link_id"], apprentice_id=row["apprentice_id"],
        journey_id=row["journey_id"], university_student_id=row["university_student_id"],
        university_degree_program_id=row["university_degree_program_id"],
        status=row["status"], reconciliation_state=row["reconciliation_state"],
        linked_at=row["linked_at"],
        last_academic_sync_at=row["last_academic_sync_at"],
    )


def save_programme_mapping(payload: dict[str, Any]) -> DegreeApprenticeshipProgramme:
    init_db()
    with connect() as conn:
        conn.execute(
            """INSERT INTO degree_apprenticeship_programmes
                 (apprenticeship_programme_id, university_degree_program_id,
                  credits_required, integration_type, active)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(apprenticeship_programme_id) DO UPDATE SET
                 university_degree_program_id=excluded.university_degree_program_id,
                 credits_required=excluded.credits_required,
                 integration_type=excluded.integration_type,
                 active=excluded.active, updated_at=datetime('now')""",
            (payload["apprenticeship_programme_id"], payload["university_degree_program_id"],
             payload.get("credits_required"), payload["integration_type"],
             int(payload.get("active", True))),
        )
    result = get_programme_mapping(payload["apprenticeship_programme_id"])
    assert result is not None
    return result


def get_programme_mapping(programme_id: int) -> DegreeApprenticeshipProgramme | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM degree_apprenticeship_programmes WHERE apprenticeship_programme_id=?",
            (programme_id,),
        ).fetchone()
    return _programme(row) if row else None


def list_programme_mappings() -> list[DegreeApprenticeshipProgramme]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM degree_apprenticeship_programmes "
            "ORDER BY apprenticeship_programme_id"
        ).fetchall()
    return [_programme(row) for row in rows]


def upsert_pending_link(payload: dict[str, Any]) -> DegreeApprenticeshipLink:
    init_db()
    with connect() as conn:
        conn.execute(
            """INSERT INTO degree_apprenticeship_links
                 (apprentice_id, journey_id, university_student_id,
                  university_degree_program_id, status, reconciliation_state)
               VALUES (?, ?, ?, ?, 'Pending', 'Pending')
               ON CONFLICT(apprentice_id) DO UPDATE SET
                 journey_id=excluded.journey_id,
                 university_student_id=excluded.university_student_id,
                 university_degree_program_id=excluded.university_degree_program_id,
                 status='Pending', reconciliation_state='Pending',
                 updated_at=datetime('now')""",
            (payload["apprentice_id"], payload["journey_id"],
             payload["university_student_id"], payload["university_degree_program_id"]),
        )
    result = get_link(payload["apprentice_id"])
    assert result is not None
    return result


def activate_link(apprentice_id: int) -> DegreeApprenticeshipLink:
    init_db()
    with connect() as conn:
        conn.execute(
            """UPDATE degree_apprenticeship_links
                  SET status='Active', reconciliation_state='In Sync',
                      linked_at=COALESCE(linked_at, datetime('now')),
                      updated_at=datetime('now') WHERE apprentice_id=?""",
            (apprentice_id,),
        )
    result = get_link(apprentice_id)
    assert result is not None
    return result


def record_academic_sync(apprentice_id: int) -> DegreeApprenticeshipLink:
    """Record a successful read without copying university-owned data."""
    init_db()
    with connect() as conn:
        cur = conn.execute(
            """UPDATE degree_apprenticeship_links
                  SET last_academic_sync_at=datetime('now'),
                      reconciliation_state='In Sync', updated_at=datetime('now')
                WHERE apprentice_id=? AND status='Active'""",
            (apprentice_id,),
        )
        if cur.rowcount == 0:
            raise ValueError(f"No active degree apprenticeship link for {apprentice_id}")
    result = get_link(apprentice_id)
    assert result is not None
    return result


def get_link(apprentice_id: int) -> DegreeApprenticeshipLink | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM degree_apprenticeship_links WHERE apprentice_id=?",
            (apprentice_id,),
        ).fetchone()
    return _link(row) if row else None


def list_links() -> list[DegreeApprenticeshipLink]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM degree_apprenticeship_links ORDER BY apprentice_id"
        ).fetchall()
    return [_link(row) for row in rows]


def apprentice_journey_id(apprentice_id: int) -> str | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT journey_id FROM apprentices WHERE apprentice_id=?", (apprentice_id,)
        ).fetchone()
    return row["journey_id"] if row else None


def set_apprentice_journey_id(apprentice_id: int, journey_id: str) -> None:
    """Stamp a canonical identity, refusing to assign it to two people."""
    init_db()
    with connect() as conn:
        collision = conn.execute(
            "SELECT apprentice_id FROM apprentices WHERE journey_id=? AND apprentice_id<>?",
            (journey_id, apprentice_id),
        ).fetchone()
        if collision:
            raise ValueError(
                f"Journey {journey_id} is already linked to apprentice {collision['apprentice_id']}"
            )
        cur = conn.execute(
            "UPDATE apprentices SET journey_id=?, updated_at=datetime('now') WHERE apprentice_id=?",
            (journey_id, apprentice_id),
        )
        if cur.rowcount == 0:
            raise ValueError(f"No apprentice with id {apprentice_id}")


def get_link_by_journey(journey_id: str) -> DegreeApprenticeshipLink | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM degree_apprenticeship_links WHERE journey_id=?", (journey_id,)
        ).fetchone()
    return _link(row) if row else None


def project_academic_progress(apprentice_id: int, event_id: str, payload: dict[str, Any]) -> None:
    """Apply an idempotent university-owned snapshot to the dashboard projection."""
    init_db()
    with connect() as conn:
        existing = conn.execute(
            "SELECT 1 FROM degree_academic_progress_projection WHERE source_event_id=?",
            (event_id,),
        ).fetchone()
        if existing:
            return
        conn.execute(
            """INSERT INTO degree_academic_progress_projection
                 (apprentice_id, university_student_id, university_degree_program_id,
                  degree_program_code, degree_program_name, registration_status,
                  credits_earned, credits_required, modules_completed,
                  academic_standing, university_gateway_confirmed,
                  degree_outcome, degree_awarded_at,
                  source_event_id, source_occurred_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(apprentice_id) DO UPDATE SET
                 university_student_id=excluded.university_student_id,
                 university_degree_program_id=excluded.university_degree_program_id,
                 degree_program_code=COALESCE(excluded.degree_program_code, degree_program_code),
                 degree_program_name=COALESCE(excluded.degree_program_name, degree_program_name),
                 registration_status=COALESCE(excluded.registration_status, registration_status),
                 credits_earned=excluded.credits_earned,
                 credits_required=excluded.credits_required,
                 modules_completed=excluded.modules_completed,
                 academic_standing=COALESCE(excluded.academic_standing, academic_standing),
                 university_gateway_confirmed=excluded.university_gateway_confirmed,
                 degree_outcome=COALESCE(excluded.degree_outcome, degree_outcome),
                 degree_awarded_at=COALESCE(excluded.degree_awarded_at, degree_awarded_at),
                 source_event_id=excluded.source_event_id,
                 source_occurred_at=excluded.source_occurred_at,
                 updated_at=datetime('now')""",
            (apprentice_id, payload["university_student_id"],
             payload["university_degree_program_id"], payload.get("degree_program_code"),
             payload.get("degree_program_name"), payload.get("registration_status"),
             float(payload.get("credits_earned") or 0),
             float(payload.get("credits_required") or 0),
             int(payload.get("modules_completed") or 0), payload.get("academic_standing"),
             int(bool(payload.get("university_gateway_confirmed"))),
             payload.get("degree_outcome"), payload.get("degree_awarded_at"),
             event_id, payload.get("occurred_at")),
        )
        conn.execute(
            """UPDATE degree_apprenticeship_links
                  SET last_academic_sync_at=datetime('now'), updated_at=datetime('now')
                WHERE apprentice_id=?""", (apprentice_id,)
        )


def academic_projection(apprentice_id: int) -> dict[str, Any] | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM degree_academic_progress_projection WHERE apprentice_id=?",
            (apprentice_id,),
        ).fetchone()
    return dict(row) if row else None


def set_reconciliation(apprentice_id: int, state: str) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            """UPDATE degree_apprenticeship_links
                  SET reconciliation_state=?, updated_at=datetime('now')
                WHERE apprentice_id=?""", (state, apprentice_id)
        )
