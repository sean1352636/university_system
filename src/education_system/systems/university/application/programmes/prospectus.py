"""What this university publishes about itself to the systems that feed it.

A sixth form filling in a UCAS choice needs two facts that only the
university can answer: what it calls itself, and which courses it is
actually recruiting to. Both existed already — the name in
``infrastructure.institution_settings``, the catalogue in the Academics
slice's ``admissions_selection`` — but every consumer reached in and took
them for itself, so "our name" and "our courses" had as many answers as
there were callers.

This module is the one published answer. It is an *application port* in
the sense the slice-boundary rules mean: cross-domain work goes through a
port, not through an import of another domain's internals. Academics
still owns the catalogue and infrastructure still owns the settings — this
composes them and is the only thing outside the university that anyone
should call.

Nothing here raises. A caller running without the university installed,
or against a database that has never had a course in it, gets an empty
catalogue and a ``None`` name — which is what the sixth form's free-text
fields already fall back to.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__all__ = ["PublishedCourse", "institution_name", "published_courses"]


@dataclass(frozen=True)
class PublishedCourse:
    """One course this university is recruiting to."""

    code: str
    name: str
    min_tariff: int = 0
    duration: str = ""

    @property
    def label(self) -> str:
        """``"Computer Science (CS1)"`` — what a picker row reads as."""
        return f"{self.name} ({self.code})"


def institution_name() -> str | None:
    """What this university calls itself, or ``None`` if it cannot say.

    Reads the admin-editable institution setting rather than the
    ``UNIVERSITY_NAME`` environment default, because the setting is what
    an administrator actually changed and the env var is only its
    fallback.
    """
    try:
        from education_system.systems.university.infrastructure import (
            institution_settings,
        )
        name = institution_settings.get_setting("institution_name")
    except Exception:
        logger.debug("Could not read the institution name", exc_info=True)
        return None
    return (str(name or "")).strip() or None


def published_courses() -> list[PublishedCourse]:
    """Active courses, name-sorted. Empty on any failure.

    Reads through Academics' own ``list_active_courses`` rather than
    querying the ``courses`` table: that function already drops withdrawn
    courses, deduplicates by code and copes with both the ``course_code``
    and ``code`` column spellings the table has carried. Re-querying by
    hand here would be a second, quietly different answer to the same
    question.
    """
    try:
        from education_system.systems.university.domains.admissions.domain.services.admissions_selection import (
            list_active_courses,
        )
        rows = list_active_courses()
    except Exception:
        logger.info("Course catalogue unavailable", exc_info=True)
        return []

    out: list[PublishedCourse] = []
    for row in rows:
        code = str(row.get("code") or "").strip()
        if not code:
            continue
        try:
            min_tariff = int(row.get("min_tariff") or 0)
        except (TypeError, ValueError):
            min_tariff = 0
        out.append(PublishedCourse(
            code=code,
            name=str(row.get("name") or code).strip() or code,
            min_tariff=min_tariff,
            duration=str(row.get("duration") or ""),
        ))
    out.sort(key=lambda c: c.name.lower())
    logger.debug("Publishing %d course(s)", len(out))
    return out
