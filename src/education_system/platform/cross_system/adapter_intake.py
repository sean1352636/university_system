"""Drain progression events into a system through its registered adapter.

:class:`~.progression.ProgressionIntake` handles the identity side of an
arriving learner — matching the journey, linking the slot, writing the
transition audit — but it needs an ``admit`` callback to create the local
record, and every system has so far written its own
(``college_intake``, ``secondary_intake``, ``primary_intake``).

A system that implements the :class:`~.adapters.base.PhaseAdapter`
contract has already answered that question in ``create_applicant``, so it
should not have to answer it twice. This module builds the intake from the
adapter:

    intake = adapter_intake.for_system("apprenticeships")
    intake.drain()

which is what the launcher calls at startup. Everything the bespoke
intakes do — idempotency, slot linking, the audit row — still happens;
the only difference is where the local record comes from.

A system with no registered adapter gets no intake, and that is a normal
answer rather than an error: its events simply stay on the durable bus
until the system that can handle them starts up.
"""

from __future__ import annotations

import logging

from education_system.platform.cross_system import identity_service
from education_system.platform.cross_system.adapters import registry
from education_system.platform.cross_system.adapters.base import HandoverRequest
from education_system.platform.cross_system.progression import (
    AdmitFn,
    ProgressionIntake,
)

logger = logging.getLogger(__name__)


def _handover_from_event(consumer_system: str, journey_id: str,
                         payload: dict) -> HandoverRequest:
    """Rebuild the adapter's input from a bus payload.

    The approved handover itself is deliberately *not* on the bus — see
    ``transitions.approve_handover``, which keeps SEND and medical detail
    out of long-lived, broadly readable bus rows. What arrives here is the
    event payload. A caller that needs the handover reads it back with
    ``transitions.get_handover_for`` (role- and purpose-gated, and
    audited), using the transition id carried below.
    """
    return HandoverRequest(
        journey_id=journey_id,
        source_system=payload.get("source_system") or "",
        destination_system=consumer_system,
        payload=payload,
        transition_id=payload.get("transition_id"),
        consent_reference=payload.get("consent_reference"),
        year_group=payload.get("year_group"),
        institution_id=payload.get("institution_id"),
    )


def _admit_via_adapter(consumer_system: str) -> AdmitFn:
    """Build the ``admit`` callback for ``consumer_system``'s intake."""

    def admit(journey_id: str, payload: dict) -> str | None:
        adapter = registry.get(consumer_system)
        if adapter is None:
            logger.debug(
                "No adapter registered for %s — leaving journey %s on the "
                "bus for whichever process can handle it",
                consumer_system, journey_id)
            return None

        handover = _handover_from_event(consumer_system, journey_id, payload)

        # Fill in identity from the canonical record when the event did not
        # carry it. The bus payload is whatever the producer chose to
        # include; the journey always knows the learner's legal name and
        # DOB, and an adapter cannot create a record without them.
        merged = dict(payload)
        try:
            from education_system.platform.cross_system import person as _person
            demographics = _person.demographics(journey_id)
            if demographics:
                merged.setdefault("first_name",
                                  demographics.get("legal_first_name"))
                merged.setdefault("last_name",
                                  demographics.get("legal_last_name"))
                merged.setdefault("date_of_birth",
                                  demographics.get("date_of_birth"))
                merged.setdefault("upn", demographics.get("upn"))
        except Exception:
            logger.debug("Could not read demographics for journey %s",
                         journey_id, exc_info=True)
        handover.payload = merged

        try:
            result = adapter.create_applicant(handover)
        except Exception:
            # Never propagate: this runs inside a bus dispatch, and one
            # unadmittable learner must not stop the rest of the queue.
            # The event stays unacked and is retried on the next drain.
            logger.exception(
                "%s adapter could not admit journey %s (from %s)",
                consumer_system, journey_id, handover.source_system or "?")
            return None

        logger.info("Admitted journey %s into %s as %s via %s",
                    journey_id, consumer_system, result.local_applicant_id,
                    type(adapter).__name__)
        return result.local_applicant_id

    return admit


_intakes: dict[str, ProgressionIntake] = {}


def for_system(consumer_system: str, *, db_path: str | None = None,
               from_system: str | None = None) -> ProgressionIntake | None:
    """The adapter-backed intake for ``consumer_system``, or ``None``.

    ``None`` when the system has no journey slot — the intake would have
    nowhere to record the arrival. Cached per system so repeated launches
    in one process reuse the same bus subscription.
    """
    if consumer_system not in identity_service.SYSTEM_SLOTS:
        logger.debug("%s has no journey slot — no adapter intake",
                     consumer_system)
        return None
    cached = _intakes.get(consumer_system)
    if cached is not None and db_path is None:
        return cached
    intake = ProgressionIntake(
        consumer_system,
        _admit_via_adapter(consumer_system),
        handler_name=f"{consumer_system}_adapter_intake",
        from_system=from_system,
        db_path=db_path,
    )
    if db_path is None:
        _intakes[consumer_system] = intake
    return intake


def drain(consumer_system: str, *, db_path: str | None = None) -> int:
    """Drain pending progression events for one system. Never raises.

    Returns the number of (event, handler) dispatches, or 0 if the system
    has no intake or the bus could not be reached.
    """
    intake = for_system(consumer_system, db_path=db_path)
    if intake is None:
        return 0
    try:
        n = intake.drain(db_path=db_path)
    except Exception:
        logger.exception("%s adapter intake drain failed", consumer_system)
        return 0
    if n:
        logger.info("Admitted %d transfer(s) into %s from the bus",
                    n, consumer_system)
    return n


def reset_for_test() -> None:
    """Test-only: drop the cached intakes between cases."""
    _intakes.clear()


__all__: list[str] = ["for_system", "drain", "reset_for_test"]
