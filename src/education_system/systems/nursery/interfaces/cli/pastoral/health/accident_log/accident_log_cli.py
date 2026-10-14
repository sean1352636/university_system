"""CLI flow for the Accident & Incident Log (Nursery System).

Delegates to the shared Accident / Incident register CLI (``accident_report``):
the Daily-Care "Log" and the Compliance "Report" are two doors onto the same
``accident_records`` register.
"""

from __future__ import annotations

import logging

from education_system.systems.nursery.domain.pastoral.health.accident_report import (
    accident_report_cli as _impl,
)

logger = logging.getLogger(__name__)


def run(auth=None) -> None:
    """Entry point for the Accident & Incident Log CLI screen."""
    _impl.run(auth=auth)


def dispatch(label: str) -> bool:
    if label != "Accident & Incident Log":
        return False
    run()
    return True
