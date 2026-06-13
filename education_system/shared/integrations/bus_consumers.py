"""Central registry of cross-system bus consumers.

The durable bus (:mod:`cross_system_bus`) only dispatches to *registered*
in-process handlers. Historically each system registered its own intake
consumer ad-hoc at startup. This module is the single place that knows,
for a given system, every handler it should run — progression intake plus
the cross-cutting consumers (safeguarding, …) — so both the launcher and
the background drainer can wire a system up with one call.

``register_consumers(system)`` is idempotent and best-effort: a consumer
that fails to import (e.g. an optional subsystem isn't installed) is
logged and skipped rather than blocking the others.
"""

from __future__ import annotations

import importlib
import logging

logger = logging.getLogger(__name__)

# system -> list of "module:function" intake registrars (each idempotent).
_INTAKE_REGISTRARS: dict[str, list[str]] = {
    "primary": [
        "education_system.primarysch_system.modules.domain.pupils.primary_intake:register_intake_consumer",
    ],
    "school": [
        "education_system.secondarysch_system.modules.domain.pupils.secondary_intake:register_intake_consumer",
    ],
    "college": [
        "education_system.sixthform_system.modules.domain.students.college_intake:register_intake_consumer",
    ],
    "university": [
        "education_system.university_system.modules.domain.admissions.sixthform_intake:register_intake_consumer",
    ],
}

# Cross-cutting consumers registered for *every* system.
_SHARED_REGISTRARS: list[str] = [
    "education_system.shared.safeguarding.alert_service:register_consumer",
]


def _invoke(ref: str) -> bool:
    module_path, _, func = ref.partition(":")
    try:
        module = importlib.import_module(module_path)
        getattr(module, func)()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("Consumer registrar %s skipped: %s", ref, exc)
        return False


def register_consumers(system: str) -> int:
    """Register every bus consumer relevant to ``system``. Idempotent.

    Returns the number of registrars that ran successfully.
    """
    count = 0
    for ref in _INTAKE_REGISTRARS.get(system, []) + _SHARED_REGISTRARS:
        if _invoke(ref):
            count += 1
    logger.debug("Registered %d consumer(s) for %s", count, system)
    return count


__all__ = ["register_consumers"]
