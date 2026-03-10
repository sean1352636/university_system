"""
Dentist/Dental Clinic Module

Provides comprehensive dental clinic management including
appointments, treatments, patient records, and billing with
email and finance integration.
"""

from education_system.university_system.modules.domain.dentist.gui.dentist_gui import (
    DentistGUI,
    launch_dentist_gui
)
from education_system.university_system.modules.domain.dentist.services.dentist_core import (
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
    'DentistGUI',
    'launch_dentist_gui',
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
