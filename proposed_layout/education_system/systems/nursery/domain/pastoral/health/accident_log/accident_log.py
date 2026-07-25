"""Domain layer for the Accident & Incident Log (Nursery System).

The day-to-day operational view of the same statutory register that the
Compliance & Reports "Accident / Incident Report" reports on. Rather than
duplicate the logic, this re-exports the ``accident_report`` domain layer (which
owns the ``accident_records`` table); the two menu entries are just different
doors onto the same record-keeping.
"""

from __future__ import annotations

from education_system.systems.nursery.domain.pastoral.health.accident_report.accident_report import (  # noqa: F401
    RECORD_TYPES,
    SEVERITIES,
    STATUSES,
    AccidentRecord,
    ValidationError,
    create_record,
    delete_record,
    get_record,
    list_pupil_choices,
    list_records,
    list_staff_choices,
    set_status,
    summary,
    update_record,
)

FEATURE_NAME = "Accident & Incident Log"
CATEGORY = "Daily Care & Routines"
