"""
Staff HR Management Module

Provides comprehensive HR management features including:
- Leave Management
- Time & Attendance
- Training & Certifications
- Performance Appraisals
- Onboarding & Offboarding
"""

from education_system.university_system.infrastructure.database.schemas.staff_hr_schemas_all import (
    init_staff_hr_schemas,
)

__all__ = [
    'init_staff_hr_schemas',
]
