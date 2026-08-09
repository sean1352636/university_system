"""University dental-clinic domain API."""

from .constants import APPOINTMENT_SLOTS, DENTIST_STAFF, TREATMENT_TYPES
from .models import Appointment, Patient, Payment, Treatment
from .services.dentist_core import (
    AppointmentManager,
    PatientManager,
    PrescriptionManager,
    ReportManager,
    TransactionManager,
    TreatmentManager,
    init_dentist_db,
)

__all__ = [
    "Appointment",
    "Patient",
    "Payment",
    "Treatment",
    "AppointmentManager",
    "PatientManager",
    "PrescriptionManager",
    "ReportManager",
    "TransactionManager",
    "TreatmentManager",
    "init_dentist_db",
    "APPOINTMENT_SLOTS",
    "DENTIST_STAFF",
    "TREATMENT_TYPES",
]
