"""
Degree Audit & Academic Advising Service Module

This module provides degree progress tracking, prerequisite validation,
what-if scenarios, and graduation audits.
"""

from education_system.university_system.modules.domain.academics.services.degree_audit.degree_audit_core import (
    DegreeProgramManager,
    DegreeProgressManager,
    WhatIfScenarioManager,
    AdvisingAppointmentManager,
    GraduationAuditManager,
)

__all__ = [
    'DegreeProgramManager',
    'DegreeProgressManager',
    'WhatIfScenarioManager',
    'AdvisingAppointmentManager',
    'GraduationAuditManager',
]
