"""
Barber Shop Module

Provides comprehensive barber shop management including
appointments, services, staff, and transaction management
with email and finance integration.
"""

from university_system.modules.domain.barber.gui.barber_gui import (
    BarberGUI,
    launch_barber_gui
)
from university_system.modules.domain.barber.services.barber_core import (
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
