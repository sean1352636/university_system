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

#: The canonical key for each system, in launcher/report order.
#: API role checks use this list: a URL prefix that doesn't resolve to one of
#: these keys falls back to the user's best role in any system.
CANONICAL_SYSTEMS: tuple[str, ...] = (
    "nursery",
    "primary",
    "secondary",
    "sixth_form",
    "fe_college",
    "apprenticeships",
    "university",
    "special_education",
    "adult_education",
    "alternative_provision",
    "training_provider",
    "local_authority",
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
    "fecollege": "fe_college",
    "fe-college": "fe_college",
    "apprentice": "apprenticeships",
    "apprenticeship": "apprenticeships",
    "send": "special_education",
    "specialeducation": "special_education",
    "special-education": "special_education",
    "adult": "adult_education",
    "adulteducation": "adult_education",
    "adult-education": "adult_education",
    "community_learning": "adult_education",
    "ap": "alternative_provision",
    "alternativeprovision": "alternative_provision",
    "alternative-provision": "alternative_provision",
    "pru": "alternative_provision",
    "tp": "training_provider",
    "trainingprovider": "training_provider",
    "training-provider": "training_provider",
    "la": "local_authority",
    "localauthority": "local_authority",
    "local-authority": "local_authority",
    "la_education": "local_authority",
}


def canonical_system_key(key: str | None) -> str | None:
    """Return the canonical system key for *key* (or *key* unchanged if it is
    already canonical / unknown). ``None`` and empty stay as-is."""
    if not key:
        return key
    k = str(key).strip().lower()
    return _ALIASES.get(k, k)


def is_known_system(key: str | None) -> bool:
    """True if *key* (after normalisation) is one of the canonical systems."""
    return canonical_system_key(key) in CANONICAL_SYSTEMS
