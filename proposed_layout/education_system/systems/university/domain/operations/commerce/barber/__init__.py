"""
Barber Shop Module

Provides comprehensive barber shop management including
appointments, services, staff, and transaction management
with email and finance integration.
"""

from education_system.systems.university.interfaces.gui.operations.commerce.barber.barber_gui import (
    BarberGUI,
    launch_barber_gui
)
from education_system.systems.university.domain.operations.commerce.barber.services.barber_core import (
    ServiceManager,
    StaffManager,
    AppointmentManager,
    TransactionManager,
    ReportManager,
    init_barber_db,
    SERVICE_TYPES,
    APPOINTMENT_STATUSES,
    TIME_SLOTS
)

__all__ = [
    'BarberGUI',
    'launch_barber_gui',
    'ServiceManager',
    'StaffManager',
    'AppointmentManager',
    'TransactionManager',
    'ReportManager',
    'init_barber_db',
    'SERVICE_TYPES',
    'APPOINTMENT_STATUSES',
    'TIME_SLOTS'
]
