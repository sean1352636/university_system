"""Move a nursery child into the Primary School System.

The nursery's natural leaving destination is Reception (year ``R``) at a
primary school. This module mirrors the primary→secondary
``secondary_transfer`` flow: it reads the child, creates the matching primary
pupil record, and takes the child off the nursery roll — all with rollback if
any step fails.

Unlike the secondary transfer, primary pupils do not get an auth login
(Reception children don't sign in), so no auth user is created here.

The nursery child is kept (status set to ``left``) rather than deleted, so the
EYFS record survives for safeguarding/audit and the move is reversible from the
directory's "Show leavers" view.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from education_system.nursery_system.modules.domain.children import children
from education_system.nursery_system.modules.domain.children.children import (
    ValidationError,
)
from education_system.primarysch_system.modules.domain.pupils import (
    pupils as primary_pupils,
)

logger = logging.getLogger(__name__)

# Reception is the first primary year and the standard nursery leaving point.
DEFAULT_YEAR_GROUP = "R"


@dataclass(frozen=True)
class PrimaryTransferResult:
    source_child_id: str
    primary_pupil_id: str
    primary_email: str
    year_group: str


def primary_year_groups() -> tuple[str, ...]:
    """The primary school's valid year groups (R, 1–6)."""
    return primary_pupils.YEAR_GROUPS


def _merge_medical(child: children.Child) -> str | None:
    """Fold the nursery allergies field into medical notes.

    Primary pupils have no separate allergies column, so we must not lose that
    safeguarding-relevant information on the way across.
    """
    parts: list[str] = []
    if child.allergies:
        parts.append(f"Allergies: {child.allergies.strip()}")
    if child.medical_notes:
        parts.append(child.medical_notes.strip())
    return "\n".join(parts) or None


def move_to_primary_school(
    child_id: str,
    *,
    year_group: str | None = None,
    class_name: str | None = None,
) -> PrimaryTransferResult:
    """Move a nursery child into the primary system and take them off roll.

    Creates a primary pupil from the child's details, then marks the nursery
    child as ``left``. If taking the child off roll fails, the newly created
    primary pupil is rolled back so the move is all-or-nothing.
    """
    child_id = (child_id or "").strip()
    if not child_id:
        raise ValidationError("Child ID is required")

    child = children.get_child(child_id)
    if child is None:
        raise ValidationError(f"No child with id {child_id}")
    if child.status == "left":
        raise ValidationError(
            f"{child.full_name} ({child_id}) has already left the nursery"
        )

    year = (year_group or DEFAULT_YEAR_GROUP).strip() or DEFAULT_YEAR_GROUP
    if year not in primary_pupils.YEAR_GROUPS:
        raise ValidationError(
            "Year group must be one of " + ", ".join(primary_pupils.YEAR_GROUPS)
        )

    pupil = None
    try:
        pupil = primary_pupils.create_pupil(
            {
                "first_name": child.first_name,
                "last_name": child.last_name,
                "year_group": year,
                "class_name": class_name or "",
                "date_of_birth": child.date_of_birth or "",
                "parent_name": child.parent_name or "",
                "parent_phone": child.parent_phone or "",
                "medical_notes": _merge_medical(child) or "",
            }
        )
        children.set_status(child_id, "left")
    except Exception:
        logger.exception("Primary transfer failed for child %s", child_id)
        if pupil is not None:
            try:
                primary_pupils.delete_pupil(pupil.pupil_id)
            except Exception:
                logger.warning(
                    "Rollback could not delete primary pupil %s",
                    pupil.pupil_id,
                    exc_info=True,
                )
        raise

    assert pupil is not None
    logger.info(
        "Moved nursery child %s to primary pupil %s (year %s)",
        child.pupil_id,
        pupil.pupil_id,
        year,
    )
    # Link the canonical journey across both phases, record the transition
    # and publish a durable progression event (best-effort; never raises).
    try:
        from education_system.shared.cross_system import progression
        progression.announce_progression(
            source_system="nursery",
            source_module="nursery_system.children.primary_transfer",
            first_name=child.first_name, last_name=child.last_name,
            date_of_birth=child.date_of_birth,
            source_student_id=child.pupil_id,
            target_student_id=pupil.pupil_id,
            year_group=year)
    except Exception:
        logger.debug("Cross-system progression announce skipped for "
                     "child %s", child.pupil_id, exc_info=True)
    return PrimaryTransferResult(
        source_child_id=child.pupil_id,
        primary_pupil_id=pupil.pupil_id,
        primary_email=pupil.email,
        year_group=year,
    )
