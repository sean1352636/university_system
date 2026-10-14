"""Sign-offs for emails built in code rather than from a template.

Email *templates* already resolve the institution: ``template_utils``
injects ``institution_name`` from ``get_institution_name()``, so renaming
the institution in Branding & Customization updates every templated
message.

Messages assembled as f-strings in Python bypass that, and a couple of
dozen of them signed off with a hardcoded "University …" — so a Teesside
student received "Best regards, University Examination Office" while
every templated email said "Teesside University". These helpers give the
code-built messages the same source of truth.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

__all__ = ["institution_name", "office_name", "sign_off"]

#: Used only when the institution genuinely cannot be resolved — a
#: missing table or an unreadable database. Deliberately neutral rather
#: than a guess at the institution.
_FALLBACK = "the University"


def institution_name() -> str:
    """The configured institution name, or a neutral fallback."""
    try:
        from education_system.systems.university.infrastructure.institution_settings import (
            get_institution_name,
        )
        return (get_institution_name() or "").strip() or _FALLBACK
    except Exception:
        logger.debug("Could not resolve the institution name", exc_info=True)
        return _FALLBACK


def office_name(office: str) -> str:
    """'Examination Office' -> 'Teesside University Examination Office'.

    An office already carrying the institution's name is returned as-is,
    so nothing reads "Teesside University Teesside University Library".
    """
    name = institution_name()
    office = (office or "").strip()
    if not office:
        return name
    if name.lower() in office.lower():
        return office
    return f"{name} {office}"


def sign_off(office: str = "", greeting: str = "Best regards") -> str:
    """The closing lines of a code-built email.

    Returns e.g. ``"\\n\\nBest regards,\\nTeesside University Examination
    Office"`` — the leading blank line included, so call sites append it
    directly to the body.
    """
    return f"\n\n{greeting},\n{office_name(office)}"
