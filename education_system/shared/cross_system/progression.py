"""Cross-system student progression pipeline.

Generalises the sixth-form → university intake (see
``university_system/.../admissions/sixthform_intake.py``) to *every*
adjacent phase of the journey::

    nursery → primary → school → college → university

Two responsibilities live here:

1. **The spine** — :func:`register_local_student` best-effort registers a
   pupil into the canonical ``student_journey`` registry the moment it is
   created, so every record carries a stable cross-system identity from
   day one. Because the registry matches on (first_name, last_name,
   date_of_birth), the *same* person created in two systems lands on the
   *same* ``journey_id`` automatically — that is what links the phases.

2. **The pipeline** — a transfer flow calls :func:`announce_progression`
   after it has moved a pupil up a phase; that anchors the journey, links
   both slots, records the transition, and publishes a durable
   ``student.progression.completed`` event. Each consumer system runs a
   :class:`ProgressionIntake` that *idempotently* admits the pupil into
   its own roll if it isn't there already — the cross-process / API path.

Everything here is best-effort: a registry or bus failure is logged but
never propagates, so a pupil/transfer is never left half-applied.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from education_system.shared.cross_system import identity_service
from education_system.shared.integrations import cross_system_bus

logger = logging.getLogger(__name__)

# Canonical phase order (auth seed keys, matching identity_service.SYSTEM_SLOTS).
PHASE_ORDER: tuple[str, ...] = ("nursery", "primary", "school",
                                "college", "university")


def next_phase(system: str) -> str | None:
    """The system a pupil progresses *to* after ``system`` (or None)."""
    try:
        i = PHASE_ORDER.index(system)
    except ValueError:
        return None
    return PHASE_ORDER[i + 1] if i + 1 < len(PHASE_ORDER) else None


def previous_phase(system: str) -> str | None:
    """The system a pupil progresses *from* into ``system`` (or None)."""
    try:
        i = PHASE_ORDER.index(system)
    except ValueError:
        return None
    return PHASE_ORDER[i - 1] if i > 0 else None


# ---------------------------------------------------------------------------
# 1) The spine — register-on-create
# ---------------------------------------------------------------------------

def register_local_student(
    system: str,
    *,
    student_id: str,
    first_name: str | None,
    last_name: str | None,
    date_of_birth: str | None,
    pk: int | None = None,
    nhs_number: str | None = None,
    upn: str | None = None,
    db_path: str | None = None,
) -> str | None:
    """Best-effort: ensure a canonical journey exists for a freshly created
    local pupil/student and link this system's slot to it.

    Returns the ``journey_id``, or ``None`` if registration was skipped
    (no name + DOB to anchor identity) or failed. **Never raises** — the
    caller's record has already been written and must stand regardless.
    """
    if not (first_name and last_name and date_of_birth):
        logger.debug(
            "Journey registration skipped for %s/%s — needs name + DOB "
            "to anchor a canonical identity", system, student_id)
        return None
    try:
        jid = identity_service.get_or_create_journey(
            first_name=first_name, last_name=last_name,
            date_of_birth=date_of_birth, system=system,
            student_id=student_id, pk=pk, nhs_number=nhs_number,
            upn=upn, db_path=db_path)
        logger.debug("Registered %s/%s into journey %s",
                     system, student_id, jid)
        return jid
    except Exception:
        logger.exception(
            "Journey registration failed for %s/%s (record still "
            "created)", system, student_id)
        return None


# ---------------------------------------------------------------------------
# 2a) Producer side — publish + announce
# ---------------------------------------------------------------------------

def publish_progression(
    *,
    journey_id: str,
    source_system: str,
    source_module: str,
    target_system: str | None = None,
    actor_user_id: int | None = None,
    db_path: str | None = None,
    **payload,
) -> str | None:
    """Best-effort publish of ``student.progression.completed``.

    ``target_system`` defaults to the phase after ``source_system``.
    Returns the bus ``event_id`` or ``None``.
    """
    target = target_system or next_phase(source_system)
    if target is None:
        logger.debug("No phase after %s — not publishing progression",
                     source_system)
        return None
    try:
        return cross_system_bus.publish_cross_system(
            cross_system_bus.EVENT_STUDENT_PROGRESSION_COMPLETED,
            source_system=source_system, source_module=source_module,
            journey_id=journey_id, target_system=target,
            actor_user_id=actor_user_id, db_path=db_path, **payload)
    except Exception:
        logger.exception(
            "Progression publish failed (%s → %s, journey %s)",
            source_system, target, journey_id)
        return None


def announce_progression(
    *,
    source_system: str,
    source_module: str,
    first_name: str | None,
    last_name: str | None,
    date_of_birth: str | None,
    source_student_id: str,
    target_student_id: str | None = None,
    actor_user_id: int | None = None,
    reason: str | None = None,
    db_path: str | None = None,
    **extra_payload,
) -> str | None:
    """Announce that a pupil has progressed to the next phase.

    Call this *after* a transfer flow has synchronously created the pupil
    in the next system (``target_student_id`` set) — or on its own to
    drive a purely event-based progression (``target_student_id`` None,
    leaving the :class:`ProgressionIntake` to create the record).

    Anchors the canonical journey on the source, links the target slot
    when known, records the transition, and publishes the durable event.
    Returns the ``journey_id`` or ``None``. **Never raises.**
    """
    target_system = next_phase(source_system)
    if not (first_name and last_name and date_of_birth):
        logger.info(
            "Progression announce skipped for %s — needs name + DOB to "
            "anchor a canonical identity", source_student_id)
        return None
    try:
        journey_id = identity_service.get_or_create_journey(
            first_name=first_name, last_name=last_name,
            date_of_birth=date_of_birth, system=source_system,
            student_id=source_student_id, db_path=db_path)
        if target_system and target_student_id:
            identity_service.link_system(
                journey_id, target_system, student_id=target_student_id,
                set_current=True, db_path=db_path)
            identity_service.record_transition(
                journey_id, from_system=source_system,
                to_system=target_system, actor_user_id=actor_user_id,
                reason=reason or f"{source_system} → {target_system} transfer",
                db_path=db_path)
        publish_progression(
            journey_id=journey_id, source_system=source_system,
            source_module=source_module, target_system=target_system,
            actor_user_id=actor_user_id, db_path=db_path,
            first_name=first_name, last_name=last_name,
            date_of_birth=date_of_birth,
            source_student_id=source_student_id,
            target_student_id=target_student_id, **extra_payload)
        logger.info(
            "Announced progression %s → %s for %s (journey %s)",
            source_system, target_system, source_student_id, journey_id)
        return journey_id
    except Exception:
        logger.exception(
            "Progression announce failed for %s (transfer still "
            "applied)", source_student_id)
        return None


# ---------------------------------------------------------------------------
# 2b) Consumer side — a reusable, idempotent intake
# ---------------------------------------------------------------------------

# admit(journey_id, payload) -> new local student_id, or None to skip.
AdmitFn = Callable[[str, dict], "str | None"]


class ProgressionIntake:
    """Idempotent bus consumer that admits a progressing pupil into one
    system's roll.

    Generalises ``sixthform_intake`` so each phase needs only supply an
    ``admit`` callback that creates its own kind of local record from the
    event payload; the linking, transition audit and idempotency are
    handled here.
    """

    def __init__(
        self,
        consumer_system: str,
        admit: AdmitFn,
        *,
        handler_name: str,
        from_system: str | None = None,
        db_path: str | None = None,
    ) -> None:
        if consumer_system not in identity_service.SYSTEM_SLOTS:
            raise ValueError(f"Unknown consumer system {consumer_system!r}")
        self.consumer_system = consumer_system
        self.admit = admit
        self.handler_name = handler_name
        self.from_system = from_system or previous_phase(consumer_system)
        # In production every system shares the single default auth.db, so
        # this stays None. Tests pass an isolated path that the registry
        # writes in ``handle`` must honour too, not just the poller.
        self.db_path = db_path
        self._registered = False

    def handle(self, envelope: dict) -> None:
        """Bus handler: admit the pupil if not already present."""
        # Progression events are always explicitly addressed; ignore any
        # that aren't for us so co-located intakes (same process) don't
        # cross-admit each other's pupils.
        target = envelope.get("target_system")
        if target is not None and target != self.consumer_system:
            return

        journey_id = envelope.get("journey_id")
        payload = envelope.get("payload") or {}
        if not journey_id:
            logger.warning(
                "Progression event %s has no journey_id — ignoring",
                envelope.get("event_id"))
            return

        journey = identity_service.get(journey_id, db_path=self.db_path)
        _pk_col, id_col = identity_service.SYSTEM_SLOTS[self.consumer_system]
        if journey and journey.get(id_col):
            logger.info(
                "Journey %s already in %s as %s — skipping intake",
                journey_id, self.consumer_system, journey[id_col])
            return

        local_id = self.admit(journey_id, payload)
        if not local_id:
            return

        identity_service.link_system(
            journey_id, self.consumer_system,
            student_id=local_id, set_current=True, db_path=self.db_path)
        identity_service.record_transition(
            journey_id, from_system=self.from_system,
            to_system=self.consumer_system,
            reason=f"{self.from_system or '?'} progression intake (bus)",
            db_path=self.db_path)
        logger.info("Admitted journey %s into %s as %s",
                    journey_id, self.consumer_system, local_id)

    def register(self) -> None:
        """Idempotently subscribe this intake to the bus."""
        if self._registered:
            return
        cross_system_bus.subscribe(
            cross_system_bus.EVENT_STUDENT_PROGRESSION_COMPLETED,
            self.handle, handler_name=self.handler_name)
        self._registered = True
        logger.debug("Registered %s progression intake", self.consumer_system)

    def drain(self, *, db_path: str | None = None) -> int:
        """Process any pending progression events for this system. Safe to
        call repeatedly; returns the number of (event, handler) dispatches."""
        self.register()
        return cross_system_bus.poll_and_dispatch(
            self.consumer_system, db_path=db_path or self.db_path)


__all__ = [
    "PHASE_ORDER",
    "next_phase",
    "previous_phase",
    "register_local_student",
    "publish_progression",
    "announce_progression",
    "ProgressionIntake",
]
