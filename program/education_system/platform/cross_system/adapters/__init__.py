"""Per-system adapters for the cross-system transition workflow.

See :mod:`.base` for the contract and :mod:`.registry` for lookup.
"""

from education_system.platform.cross_system.adapters.base import (
    AdapterError,
    AdapterNotImplemented,
    ApplicantResult,
    EnrolmentResult,
    ExportResult,
    HandoverRequest,
    PhaseAdapter,
)

__all__ = [
    "AdapterError",
    "AdapterNotImplemented",
    "ApplicantResult",
    "EnrolmentResult",
    "ExportResult",
    "HandoverRequest",
    "PhaseAdapter",
]
