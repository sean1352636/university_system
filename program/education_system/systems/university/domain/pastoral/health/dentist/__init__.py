"""
Dentist/Dental Clinic Module

Provides comprehensive dental clinic management including
appointments, treatments, patient records, and billing with
email and finance integration.
"""

from education_system.systems.university.domain.pastoral.health.dentist.services.dentist_core import (
    PatientManager,
    AppointmentManager,
    TreatmentManager,
    PrescriptionManager,
    TransactionManager,
    ReportManager,
    init_dentist_db,
    TREATMENT_TYPES,
    DENTIST_STAFF
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
    'DENTIST_STAFF'
]
