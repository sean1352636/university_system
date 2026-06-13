"""Staff HR schemas — orchestrator and public-API shim.

The DDL itself now lives in six domain-aligned modules in this package:

    staff_hr_core_schemas.py        leave, time, training, appraisals,
                                    profiles, documents, onboarding,
                                    contracts, exit
    staff_hr_academic_schemas.py    teaching, research, supervisions,
                                    curriculum, sabbaticals, mentoring,
                                    peer review
    staff_hr_workload_schemas.py    schedules, teaching load, cover,
                                    workload norms
    staff_hr_finance_schemas.py     payroll, expenses, travel, grants
    staff_hr_facilities_schemas.py  access, assets, lab/equipment booking
    staff_hr_governance_schemas.py  committees, recruitment, grievance,
                                    disciplinary, KPIs, IP, comm hub,
                                    directory

This module preserves the historical import path so existing callers keep
working: ``init_staff_hr_schemas`` plus the dropdown lookup helpers
(``get_departments``, ``get_employment_types``, ``get_program_types``,
``get_observation_types``) are re-exported here.
"""
from __future__ import annotations

from .staff_hr_academic_schemas import (
    _init_academic_schemas,
    get_observation_types,
    get_program_types,
)
from .staff_hr_core_schemas import (
    _init_core_schemas,
    get_employment_types,
)
from .staff_hr_facilities_schemas import (
    _init_facilities_schemas,
    generate_asset_tag,
    get_asset_conditions,
    get_asset_statuses,
    get_depreciation_methods,
    get_issue_severities,
    get_issue_types,
    get_maintenance_categories,
    get_maintenance_types,
    get_request_types,
    get_request_urgencies,
)
from .staff_hr_finance_schemas import _init_finance_schemas
from .staff_hr_governance_schemas import (
    _init_governance_schemas,
    get_committee_types,
    get_departments,
    get_interview_types,
    get_job_types,
)
from .staff_hr_workload_schemas import _init_workload_schemas


def init_staff_hr_schemas() -> None:
    """Initialise every Staff HR database table in a single call.

    Idempotent (every statement is CREATE TABLE IF NOT EXISTS). Safe to
    call repeatedly at startup.
    """
    _init_core_schemas()
    _init_academic_schemas()
    _init_workload_schemas()
    _init_finance_schemas()
    _init_facilities_schemas()
    _init_governance_schemas()
    print("Staff HR schemas initialized successfully")


# Backward-compatible aliases — older callers still import these names.
# Both call the full init because the per-sprint slice is no longer
# meaningful and CREATE TABLE IF NOT EXISTS makes redundant calls cheap.
init_all_staff_hr_schemas = init_staff_hr_schemas
init_staff_hr_v2_schemas = init_staff_hr_schemas


__all__ = [
    "init_staff_hr_schemas",
    "init_all_staff_hr_schemas",
    "init_staff_hr_v2_schemas",
    # Lookup helpers re-exported for external callers.
    "get_departments",
    "get_employment_types",
    "get_program_types",
    "get_observation_types",
    "get_committee_types",
    "get_job_types",
    "get_interview_types",
    "get_asset_statuses",
    "get_asset_conditions",
    "get_issue_types",
    "get_issue_severities",
    "get_maintenance_types",
    "get_maintenance_categories",
    "get_request_types",
    "get_request_urgencies",
    "get_depreciation_methods",
    "generate_asset_tag",
]
