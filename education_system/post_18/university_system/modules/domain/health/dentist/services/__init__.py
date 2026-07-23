"""Dentist/Dental Clinic Core Services Module"""

from education_system.post_18.university_system.modules.domain.health.dentist.services.dentist_core import (
    PatientManager,
    AppointmentManager,
    TreatmentManager,
    PrescriptionManager,
    TransactionManager,
    ReportManager,
    init_dentist_db,
    TREATMENT_TYPES,
    DENTIST_STAFF,
    APPOINTMENT_SLOTS
)

__all__ = [
    'PatientManager',
    'AppointmentManager',
    'TreatmentManager',
    'PrescriptionManager',
    'TransactionManager',
    'ReportManager',
    'init_dentist_db',
    'TREATMENT_TYPES',
    'DENTIST_STAFF',
    'APPOINTMENT_SLOTS'
]
