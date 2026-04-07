"""
Dentist/Dental Clinic Module

Provides comprehensive dental clinic management including
appointments, treatments, patient records, and billing with
email and finance integration.
"""

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


def __getattr__(name):
    """Lazy import for GUI classes to avoid circular imports."""
    if name in ('DentistGUI', 'launch_dentist_gui'):
        from education_system.university_system.modules.domain.health.gui.health_portal.dentist_gui import (
            DentistGUI,
            launch_dentist_gui
        )
        return DentistGUI if name == 'DentistGUI' else launch_dentist_gui
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
