"""HTTP API surface for the University system, one package per domain.

``ALL_BLUEPRINTS`` is the university mount's entry point in
``platform/delivery/api/registry.py``. The surface was removed deliberately on
2026-09-08 to be rebuilt module by module; all ten domains are now wired.

Distinct from ``education_system.platform.delivery.api.university``, which is
the shared kernel library (auth, pagination, validators) these routes import.
"""

from education_system.api.university.academics import (
    DOMAIN_BLUEPRINTS as _academics_blueprints,
)
from education_system.api.university.admissions import (
    DOMAIN_BLUEPRINTS as _admissions_blueprints,
)
from education_system.api.university.assessment import (
    DOMAIN_BLUEPRINTS as _assessment_blueprints,
)
from education_system.api.university.finance import (
    DOMAIN_BLUEPRINTS as _finance_blueprints,
)
from education_system.api.university.governance import (
    DOMAIN_BLUEPRINTS as _governance_blueprints,
)
from education_system.api.university.learners import (
    DOMAIN_BLUEPRINTS as _learners_blueprints,
)
from education_system.api.university.operations import (
    DOMAIN_BLUEPRINTS as _operations_blueprints,
)
from education_system.api.university.pastoral import (
    DOMAIN_BLUEPRINTS as _pastoral_blueprints,
)
from education_system.api.university.progression import (
    DOMAIN_BLUEPRINTS as _progression_blueprints,
)
from education_system.api.university.staff import (
    DOMAIN_BLUEPRINTS as _staff_blueprints,
)

#: Every mounted university blueprint, in mount order.
ALL_BLUEPRINTS = [
    *_academics_blueprints,
    *_admissions_blueprints,
    *_assessment_blueprints,
    *_finance_blueprints,
    *_governance_blueprints,
    *_learners_blueprints,
    *_operations_blueprints,
    *_pastoral_blueprints,
    *_progression_blueprints,
    *_staff_blueprints,
]

__all__ = ["ALL_BLUEPRINTS"]
