"""Cross-system database registry: which DB, order and learner table per system.

Part of :mod:`education_system.paths`; import names from the package, not from here.
"""

from __future__ import annotations

from pathlib import Path

from education_system.paths.platform_shared import (
    PLATFORM_AUTH_DB_FILE,
)
from education_system.paths.systems.nursery import (
    NURSERY_DB,
)
from education_system.paths.systems.primary import (
    PRIMARY_PUPILS_DB,
)
from education_system.paths.systems.secondary import (
    SECONDARY_PUPILS_DB,
)
from education_system.paths.systems.sixth_form import (
    SIXTH_FORM_STUDENTS_DB,
)
from education_system.paths.systems.university import (
    UNIVERSITY_DEFAULT_DB_PATH,
)
from education_system.paths.systems.fe_college import (
    FE_COLLEGE_DB,
)
from education_system.paths.systems.apprenticeships import (
    APPRENTICESHIPS_DB,
)

# ═════════════════════════════════════════════════════════════════════
# Cross-system database registry (formerly kernel/database/paths.py)
# ═════════════════════════════════════════════════════════════════════

# Every shared service that queries across systems resolves database files
# through this registry rather than computing paths independently.
PLATFORM_AUTH_DB: Path = PLATFORM_AUTH_DB_FILE

SYSTEM_DB_PATHS: dict[str, Path] = {
    "nursery": NURSERY_DB,
    "primary": PRIMARY_PUPILS_DB,
    "secondary": SECONDARY_PUPILS_DB,
    "sixth_form": SIXTH_FORM_STUDENTS_DB,
    "fe_college": FE_COLLEGE_DB,
    "apprenticeships": APPRENTICESHIPS_DB,
    "university": UNIVERSITY_DEFAULT_DB_PATH,
}

# Display / iteration order. This is a reading order, not a progression
# chain: fe_college and apprenticeships are post-16 alternatives that sit
# beside sixth form, not stations between it and university. The chain of
# *recommended* next phases lives in cross_system.progression.PHASE_ORDER,
# which deliberately still names only the five linear phases.
SYSTEM_ORDER: list[str] = [
    "nursery", "primary", "secondary", "sixth_form", "fe_college",
    "apprenticeships", "university",
]

SYSTEM_LABELS: dict[str, str] = {
    "nursery": "Nursery",
    "primary": "Primary School",
    "secondary": "Secondary School",
    "sixth_form": "Sixth Form College",
    "fe_college": "FE College",
    "apprenticeships": "Apprenticeships",
    "university": "University",
}

# Where each system keeps its learner rows: system key -> (table, id column).
#
# Cross-cutting services (GDPR erasure and SAR, retention, the analytics
# warehouse, the single student view) have to open a system's database and
# find its learners without importing that system. They previously each
# carried their own copy of the rule as ``"pupils" if primary else
# "students"``, which quietly assumed every non-primary system uses a
# ``students``/``student_id`` pair. Apprenticeships does not — it has
# ``apprentices``/``apprentice_id`` — so the assumption now has to be
# stated in one place rather than re-derived in seven.
SYSTEM_LEARNER_TABLE: dict[str, tuple[str, str]] = {
    "nursery": ("pupils", "pupil_id"),
    "primary": ("pupils", "pupil_id"),
    "secondary": ("pupils", "pupil_id"),
    "sixth_form": ("students", "student_id"),
    "fe_college": ("students", "student_id"),
    "apprenticeships": ("apprentices", "apprentice_id"),
    "university": ("students", "student_id"),
}


def learner_table(system: str) -> tuple[str, str]:
    """The ``(table, id_column)`` holding ``system``'s learner records.

    Falls back to the historical ``students``/``student_id`` guess for an
    unregistered key, so a caller handed an unknown system degrades to the
    old behaviour instead of raising.
    """
    return SYSTEM_LEARNER_TABLE.get(system, ("students", "student_id"))
