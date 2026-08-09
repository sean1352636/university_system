"""Year-group enrolment helpers for the Primary School System."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from education_system.systems.primary.domain.learners.pupils import pupils as data
from education_system.systems.primary.domain.learners.pupils.pupils import (
    Pupil, ValidationError, YEAR_GROUPS,
)

logger = logging.getLogger(__name__)

FINAL_YEAR = "6"


def roll_by_year() -> dict[str, list[Pupil]]:
    pupils = data.list_pupils()
    grouped: dict[str, list[Pupil]] = {y: [] for y in YEAR_GROUPS}
    for p in pupils:
        grouped.setdefault(p.year_group, []).append(p)
    logger.debug("roll_by_year -> %s",
                 {y: len(v) for y, v in grouped.items()})
    return grouped


def _bump_class(old_year: str, new_year: str, name: str | None) -> str | None:
    """Replace the leading digit run on a class name with ``new_year``
    so the class follows the pupil into the new year
    (e.g. ``3A`` → ``4A``). If the year hasn't changed, or the class
    has no leading-digit prefix, returns the name untouched."""
    if not name or old_year == new_year:
        return name
    i = 0
    while i < len(name) and name[i].isdigit():
        i += 1
    if i == 0:
        return name
    return new_year + name[i:]


def move_pupil(pupil_id: str, new_year: str,
               new_class: str | None = None) -> Pupil:
    if new_year not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of {', '.join(YEAR_GROUPS)}")
    existing = data.get_pupil(pupil_id)
    if existing is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    resolved_class = (
        new_class if new_class is not None
        else _bump_class(existing.year_group, new_year, existing.class_name)
    )
    fields = {
        "first_name":    existing.first_name,
        "last_name":     existing.last_name,
        "year_group":    new_year,
        "class_name":    resolved_class,
        "date_of_birth": existing.date_of_birth,
        "parent_name":   existing.parent_name,
        "parent_phone":  existing.parent_phone,
        "medical_notes": existing.medical_notes,
        "send_status":   existing.send_status,
    }
    updated = data.update_pupil(pupil_id, fields)
    logger.info("Moved pupil %s from year %s to year %s",
                pupil_id, existing.year_group, updated.year_group)
    return updated


def _next_year(year: str) -> str | None:
    if year not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of {', '.join(YEAR_GROUPS)}")
    idx = YEAR_GROUPS.index(year)
    if year == FINAL_YEAR or idx == len(YEAR_GROUPS) - 1:
        return None
    return YEAR_GROUPS[idx + 1]


def promote_year(from_year: str, *, dry_run: bool = False) -> dict[str, Any]:
    if from_year not in YEAR_GROUPS:
        raise ValidationError(
            f"Year group must be one of {', '.join(YEAR_GROUPS)}")
    to_year = _next_year(from_year)
    pupils = [p for p in data.list_pupils() if p.year_group == from_year]
    summary: dict[str, Any] = {
        "from_year": from_year,
        "to_year":   to_year,
        "count":     0,
        "pupils":    [],
        "leavers":   [],
    }
    if to_year is None:
        summary["leavers"] = pupils
        logger.info("promote_year(%s): %d leaver(s) — not modified",
                    from_year, len(pupils))
        return summary
    if dry_run:
        summary["count"] = len(pupils)
        summary["pupils"] = pupils
        logger.debug("promote_year(%s) dry-run: %d pupil(s)",
                     from_year, len(pupils))
        return summary
    moved: list[Pupil] = []
    for p in pupils:
        try:
            moved.append(move_pupil(p.pupil_id, to_year))
        except (ValidationError, sqlite3.Error):
            logger.exception("Failed to promote pupil %s", p.pupil_id)
            raise
    summary["count"] = len(moved)
    summary["pupils"] = moved
    logger.info("Promoted %d pupil(s) from year %s to year %s",
                len(moved), from_year, to_year)
    return summary


def leavers() -> list[Pupil]:
    return [p for p in data.list_pupils() if p.year_group == FINAL_YEAR]
