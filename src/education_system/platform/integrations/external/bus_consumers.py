"""Central registry of cross-system bus consumers.

The durable bus (:mod:`cross_system_bus`) only dispatches to *registered*
in-process handlers. Historically each system registered its own intake
consumer ad-hoc at startup. This module is the single place that knows,
for a given system, every handler it should run — progression intake plus
the cross-cutting consumers (safeguarding, notifications, webhooks, the
calendar) — so both the launcher and the background drainer can wire a
system up with one call.

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
    "apprenticeships": [
        "education_system.systems.apprenticeships.infrastructure.integrations.degree_events:register_consumers",
    ],
    "primary": [
        "education_system.systems.primary.domain.learners.pupils.primary_intake:register_intake_consumer",
    ],
    "secondary": [
        "education_system.systems.secondary.domain.admissions.secondary_intake:register_intake_consumer",
    ],
    "sixth_form": [
        "education_system.systems.sixth_form.domain.admissions.college_intake:register_intake_consumer",
        # University UCAS decisions + enrolments -> the sixth form's own rows.
        "education_system.systems.sixth_form.domain.progression.university.ucas_events:register_consumers",
        # University enrolled / progressed / withdrawn -> KS5 destinations.
        "education_system.systems.sixth_form.domain.progression.destinations.university_confirmations:register_consumers",
    ],
    "university": [
        "education_system.systems.university.domains.admissions.domain.sixthform_intake:register_intake_consumer",
        "education_system.systems.university.services.bus.degree_apprenticeship_events:register_consumers",
    ],
}

# Cross-cutting consumers registered for *every* system. All of them are
# idempotent per event across systems (a broadcast event is dispatched once
# per running system), which is what makes it safe to run them everywhere.
_SHARED_REGISTRARS: list[str] = [
    "education_system.platform.governance.safeguarding.alert_service:register_consumer",
    # Every catalogued event -> matching webhook subscriptions (ids only).
    "education_system.platform.integrations.webhooks.bus_forwarder:register_consumer",
    # Transfer steps -> in-app / email notifications for the people involved.
    "education_system.platform.features.notifications.event_notifications:register_consumer",
    # Dead letters -> superadmin notifications (the bus's alert hook).
    "education_system.platform.features.notifications.event_notifications:register_delivery_alerts",
    # Transition effective dates and reminders -> the shared calendar.
    "education_system.platform.features.calendar.transition_sync:register_consumer",
]

#: Handler names of the shared consumers that are safe to run over events
#: addressed to *any* system (see :func:`bus_drainer.drain_platform_once`).
#: Intake handlers are deliberately not here: they create local records and
#: must only ever run in their own system.
SHARED_HANDLER_NAMES: frozenset[str] = frozenset({
    "platform.integrations.webhooks.bus_forwarder",
    "platform.features.notifications.event_notifications",
    "platform.features.calendar.transition_sync",
})

#: The consumer-system name the platform drainer records receipts under.
PLATFORM_CONSUMER = "platform"


def _invoke(ref: str) -> bool:
    module_path, _, func = ref.partition(":")
    try:
        module = importlib.import_module(module_path)
        getattr(module, func)()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("Consumer registrar %s skipped: %s", ref, exc)
        return False


def register_shared_consumers() -> int:
    """Register only the cross-cutting consumers. Idempotent."""
    return sum(1 for ref in _SHARED_REGISTRARS if _invoke(ref))


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


def intake_registrars(system: str) -> list[str]:
    """The intake registrars configured for *system* (for status screens)."""
    return list(_INTAKE_REGISTRARS.get(system, []))


__all__ = [
    "PLATFORM_CONSUMER",
    "SHARED_HANDLER_NAMES",
    "intake_registrars",
    "register_consumers",
    "register_shared_consumers",
]
