"""Canonical system-key normalisation.

The five education systems historically accumulated several names for the same
system — most notably the Sixth Form College keyed ``college`` in auth but
``sixthform`` in routes/package, and the Secondary School keyed ``school`` in
auth but ``secondary`` in the package/flag and several dashboards. This module
is the single source of truth: everything that compares or stores a system key
normalises through :func:`canonical_system_key` first, so old (``college`` /
``school`` / ``sixthform``) and new (``sixth_form`` / ``secondary``) values all
resolve to one canonical identifier.

Canonical keys match the plan's naming standard:
``nursery`` · ``primary`` · ``secondary`` · ``sixth_form`` · ``university``.
"""

from __future__ import annotations

#: The canonical key for each of the five systems, in launcher/report order.
CANONICAL_SYSTEMS: tuple[str, ...] = (
    "nursery",
    "primary",
    "secondary",
    "sixth_form",
    "university",
)

#: Legacy / alternate spellings → canonical key. Kept permanently so existing
#: databases, JWTs and hardcoded call sites keep resolving during and after the
#: rename. URL prefixes (e.g. ``sixth-form``) are included so route paths map too.
_ALIASES: dict[str, str] = {
    "school": "secondary",
    "secondary_school": "secondary",
    "college": "sixth_form",
    "sixthform": "sixth_form",
    "sixth-form": "sixth_form",
    "sixthform_college": "sixth_form",
}


def canonical_system_key(key: str | None) -> str | None:
    """Return the canonical system key for *key* (or *key* unchanged if it is
    already canonical / unknown). ``None`` and empty stay as-is."""
    if not key:
        return key
    k = str(key).strip().lower()
    return _ALIASES.get(k, k)


def is_known_system(key: str | None) -> bool:
    """True if *key* (after normalisation) is one of the five systems."""
    return canonical_system_key(key) in CANONICAL_SYSTEMS
