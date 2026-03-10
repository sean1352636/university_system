"""Nail Bar/Salon Core Services Module"""

from education_system.university_system.modules.domain.nailbar.services.nailbar_core import (
    TreatmentManager,
    TechnicianManager,
    AppointmentManager,
    TransactionManager,
    ReportManager,
    init_nailbar_db,
    TREATMENT_CATEGORIES,
    APPOINTMENT_STATUSES,
    TIME_SLOTS
)

__all__ = [
    'TreatmentManager',
    'TechnicianManager',
    'AppointmentManager',
    'TransactionManager',
    'ReportManager',
    'init_nailbar_db',
    'TREATMENT_CATEGORIES',
    'APPOINTMENT_STATUSES',
    'TIME_SLOTS'
]
