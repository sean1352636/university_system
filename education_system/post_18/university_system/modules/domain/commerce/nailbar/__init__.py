"""
Nail Bar/Salon Module

Provides comprehensive nail bar/salon management including
treatments, appointments, technicians, and transaction management
with email and finance integration.
"""

from education_system.post_18.university_system.modules.domain.commerce.nailbar.gui.nailbar_gui import (
    NailBarGUI,
    launch_nailbar_gui
)
from education_system.post_18.university_system.modules.domain.commerce.nailbar.services.nailbar_core import (
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
    'NailBarGUI',
    'launch_nailbar_gui',
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
