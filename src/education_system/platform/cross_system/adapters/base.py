"""The contract each education system implements to join a transition.

The point of the adapter is containment. Without one, a nursery→primary
progression means nursery code importing primary's database module, and
sixth_form→university means the college knowing the shape of the
university's applicant table. Five systems and eight boundaries is a lot
of places for that coupling to grow.

With one, the platform orchestrates and each system answers four
questions about *itself only*:

``create_applicant``   here is a handover — make me a pending admission
``create_enrolment``   the offer was accepted — make the local learner id
``export_handover``    this learner is leaving — what may I release?
``close_enrolment``    they have gone — close the local record

An adapter never talks to another system's adapter. The workflow in
``transitions`` is what connects them, and it addresses each by its
system key.

Subclass :class:`PhaseAdapter`, implement the four methods, and register
the instance::

    from education_system.platform.cross_system.adapters import registry

    class PrimaryAdapter(PhaseAdapter):
        system = "primary"
        ...

    registry.register(PrimaryAdapter())

Unimplemented methods raise :class:`AdapterNotImplemented` rather than
returning ``None``, so a half-wired system fails loudly at the boundary
instead of silently dropping a learner mid-transfer.
"""

from __future__ import annotations

import abc
import logging
from typing import Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class AdapterError(RuntimeError):
    """An adapter could not carry out a request."""


class AdapterNotImplemented(AdapterError, NotImplementedError):
    """This system has not implemented that side of the contract yet."""


@dataclass
class HandoverRequest:
    """What the platform passes into ``create_applicant``."""

    journey_id: str
    source_system: str
    destination_system: str
    payload: dict = field(default_factory=dict)
    transition_id: str | None = None
    consent_reference: str | None = None
    year_group: str | None = None
    institution_id: str | None = None

    def get(self, key: str, default: Any = None) -> Any:
        return self.payload.get(key, default)

    @property
    def boundary(self) -> str:
        return f"{self.source_system}->{self.destination_system}"


@dataclass
class ApplicantResult:
    """What ``create_applicant`` returns."""

    local_applicant_id: str
    institution_id: str | None = None
    year_group: str | None = None
    notes: str | None = None


@dataclass
class EnrolmentResult:
    """What ``create_enrolment`` returns."""

    local_student_id: str
    institution_id: str | None = None
    year_group: str | None = None
    start_date: str | None = None
    notes: str | None = None


@dataclass
class ExportResult:
    """What ``export_handover`` returns.

    ``record`` is keyed by the boundary's :class:`~..handover.HandoverSpec`
    field keys. The adapter gathers, the platform filters — an adapter
    should return everything it holds for those keys and let
    ``handover.build_handover`` apply consent and strip restricted
    fields, rather than each system reimplementing that policy.
    """

    record: dict = field(default_factory=dict)
    safeguarding_reference: str | None = None
    local_student_id: str | None = None


class PhaseAdapter(abc.ABC):
    """One education system's side of the transition contract."""

    #: The system key this adapter serves — one of the five phase keys,
    #: matching ``identity_service.SYSTEM_SLOTS``.
    system: str = ""

    def __init__(self) -> None:
        if not self.system:
            raise AdapterError(
                f"{type(self).__name__} must set a class-level `system` key")

    # ── Destination side ────────────────────────────────────────────

    def create_applicant(self, handover: HandoverRequest) -> ApplicantResult:
        """Create a pending admission record from an approved handover.

        Called at workflow step 3. Must be idempotent on
        ``handover.journey_id``: a redelivered bus event has to find the
        existing applicant rather than create a second one.
        """
        raise AdapterNotImplemented(
            f"{self.system} cannot yet receive applicants "
            f"({type(self).__name__}.create_applicant)")

    def create_enrolment(self, journey_id: str,
                         application_id: str | None = None,
                         **details: Any) -> EnrolmentResult:
        """Turn an accepted applicant into a local enrolled learner.

        Called at workflow step 6, and this — not the applicant record —
        is what mints the system's local student id. Must be idempotent
        on ``journey_id``.
        """
        raise AdapterNotImplemented(
            f"{self.system} cannot yet create enrolments "
            f"({type(self).__name__}.create_enrolment)")

    # ── Source side ─────────────────────────────────────────────────

    def export_handover(self, local_student_id: str,
                        consent: bool | set[str] | None = None,
                        *, destination_system: str | None = None
                        ) -> ExportResult:
        """Gather the information this system holds for a departing
        learner, keyed by the boundary spec's field keys.

        Called at workflow step 5. Consent is passed through so an
        adapter may skip an expensive lookup it knows will be withheld;
        the authoritative filtering happens in ``handover.build_handover``.
        """
        raise AdapterNotImplemented(
            f"{self.system} cannot yet export handovers "
            f"({type(self).__name__}.export_handover)")

    def close_enrolment(self, local_student_id: str,
                        reason: str, **details: Any) -> None:
        """Close the local record when a learner leaves.

        Called at workflow step 7. Must not delete: the local record is
        marked as left/transferred so the system's own history, statutory
        returns and audit trail stay intact.
        """
        raise AdapterNotImplemented(
            f"{self.system} cannot yet close enrolments "
            f"({type(self).__name__}.close_enrolment)")

    # ── Capability reporting ────────────────────────────────────────

    def capabilities(self) -> dict[str, bool]:
        """Which sides of the contract this adapter actually implements.

        Lets a dashboard show that, say, primary can receive but not yet
        export, instead of that only surfacing when a transfer fails.
        """
        out = {}
        for name in ("create_applicant", "create_enrolment",
                     "export_handover", "close_enrolment"):
            own = getattr(type(self), name, None)
            base = getattr(PhaseAdapter, name, None)
            out[name] = own is not None and own is not base
        return out

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        done = sum(self.capabilities().values())
        return f"<{type(self).__name__} system={self.system} {done}/4>"


__all__ = [
    "AdapterError",
    "AdapterNotImplemented",
    "HandoverRequest",
    "ApplicantResult",
    "EnrolmentResult",
    "ExportResult",
    "PhaseAdapter",
]
