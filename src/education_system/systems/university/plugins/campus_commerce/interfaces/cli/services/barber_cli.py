"""Compatibility façade for the split implementation."""

from . import barber_cli_shared as _shared
from .barber_cli_shared import *  # noqa: F401,F403

from .barber_cli_parts import print_header as _part_1
print_header = _part_1.print_header
_shared.print_header = print_header
_shared.__all__.append("print_header") if "print_header" not in _shared.__all__ else None

from .barber_cli_parts import print_subheader as _part_2
print_subheader = _part_2.print_subheader
_shared.print_subheader = print_subheader
_shared.__all__.append("print_subheader") if "print_subheader" not in _shared.__all__ else None

from .barber_cli_parts import get_current_user as _part_3
get_current_user = _part_3.get_current_user
_shared.get_current_user = get_current_user
_shared.__all__.append("get_current_user") if "get_current_user" not in _shared.__all__ else None

from .barber_cli_parts import is_staff_or_admin as _part_4
is_staff_or_admin = _part_4.is_staff_or_admin
_shared.is_staff_or_admin = is_staff_or_admin
_shared.__all__.append("is_staff_or_admin") if "is_staff_or_admin" not in _shared.__all__ else None

from .barber_cli_parts import view_services as _part_5
view_services = _part_5.view_services
_shared.view_services = view_services
_shared.__all__.append("view_services") if "view_services" not in _shared.__all__ else None

from .barber_cli_parts import add_service as _part_6
add_service = _part_6.add_service
_shared.add_service = add_service
_shared.__all__.append("add_service") if "add_service" not in _shared.__all__ else None

from .barber_cli_parts import update_service as _part_7
update_service = _part_7.update_service
_shared.update_service = update_service
_shared.__all__.append("update_service") if "update_service" not in _shared.__all__ else None

from .barber_cli_parts import toggle_service_availability as _part_8
toggle_service_availability = _part_8.toggle_service_availability
_shared.toggle_service_availability = toggle_service_availability
_shared.__all__.append("toggle_service_availability") if "toggle_service_availability" not in _shared.__all__ else None

from .barber_cli_parts import view_staff as _part_9
view_staff = _part_9.view_staff
_shared.view_staff = view_staff
_shared.__all__.append("view_staff") if "view_staff" not in _shared.__all__ else None

from .barber_cli_parts import view_staff_schedules as _part_10
view_staff_schedules = _part_10.view_staff_schedules
_shared.view_staff_schedules = view_staff_schedules
_shared.__all__.append("view_staff_schedules") if "view_staff_schedules" not in _shared.__all__ else None

from .barber_cli_parts import staff_performance_metrics as _part_11
staff_performance_metrics = _part_11.staff_performance_metrics
_shared.staff_performance_metrics = staff_performance_metrics
_shared.__all__.append("staff_performance_metrics") if "staff_performance_metrics" not in _shared.__all__ else None

from .barber_cli_parts import book_appointment as _part_12
book_appointment = _part_12.book_appointment
_shared.book_appointment = book_appointment
_shared.__all__.append("book_appointment") if "book_appointment" not in _shared.__all__ else None

from .barber_cli_parts import view_my_appointments as _part_13
view_my_appointments = _part_13.view_my_appointments
_shared.view_my_appointments = view_my_appointments
_shared.__all__.append("view_my_appointments") if "view_my_appointments" not in _shared.__all__ else None

from .barber_cli_parts import cancel_appointment as _part_14
cancel_appointment = _part_14.cancel_appointment
_shared.cancel_appointment = cancel_appointment
_shared.__all__.append("cancel_appointment") if "cancel_appointment" not in _shared.__all__ else None

from .barber_cli_parts import reschedule_appointment as _part_15
reschedule_appointment = _part_15.reschedule_appointment
_shared.reschedule_appointment = reschedule_appointment
_shared.__all__.append("reschedule_appointment") if "reschedule_appointment" not in _shared.__all__ else None

from .barber_cli_parts import check_in_appointment as _part_16
check_in_appointment = _part_16.check_in_appointment
_shared.check_in_appointment = check_in_appointment
_shared.__all__.append("check_in_appointment") if "check_in_appointment" not in _shared.__all__ else None

from .barber_cli_parts import complete_appointment as _part_17
complete_appointment = _part_17.complete_appointment
_shared.complete_appointment = complete_appointment
_shared.__all__.append("complete_appointment") if "complete_appointment" not in _shared.__all__ else None

from .barber_cli_parts import daily_schedule as _part_18
daily_schedule = _part_18.daily_schedule
_shared.daily_schedule = daily_schedule
_shared.__all__.append("daily_schedule") if "daily_schedule" not in _shared.__all__ else None

from .barber_cli_parts import revenue_report as _part_19
revenue_report = _part_19.revenue_report
_shared.revenue_report = revenue_report
_shared.__all__.append("revenue_report") if "revenue_report" not in _shared.__all__ else None

from .barber_cli_parts import service_popularity_report as _part_20
service_popularity_report = _part_20.service_popularity_report
_shared.service_popularity_report = service_popularity_report
_shared.__all__.append("service_popularity_report") if "service_popularity_report" not in _shared.__all__ else None

from .barber_cli_parts import customer_retention_stats as _part_21
customer_retention_stats = _part_21.customer_retention_stats
_shared.customer_retention_stats = customer_retention_stats
_shared.__all__.append("customer_retention_stats") if "customer_retention_stats" not in _shared.__all__ else None

from .barber_cli_parts import services_menu as _part_22
services_menu = _part_22.services_menu
_shared.services_menu = services_menu
_shared.__all__.append("services_menu") if "services_menu" not in _shared.__all__ else None

from .barber_cli_parts import staff_menu as _part_23
staff_menu = _part_23.staff_menu
_shared.staff_menu = staff_menu
_shared.__all__.append("staff_menu") if "staff_menu" not in _shared.__all__ else None

from .barber_cli_parts import appointments_menu as _part_24
appointments_menu = _part_24.appointments_menu
_shared.appointments_menu = appointments_menu
_shared.__all__.append("appointments_menu") if "appointments_menu" not in _shared.__all__ else None

from .barber_cli_parts import reports_menu as _part_25
reports_menu = _part_25.reports_menu
_shared.reports_menu = reports_menu
_shared.__all__.append("reports_menu") if "reports_menu" not in _shared.__all__ else None

from .barber_cli_parts import barber_menu as _part_26
barber_menu = _part_26.barber_menu
_shared.barber_menu = barber_menu
_shared.__all__.append("barber_menu") if "barber_menu" not in _shared.__all__ else None

from .barber_cli_parts import launch_barber_cli as _part_27
launch_barber_cli = _part_27.launch_barber_cli
_shared.launch_barber_cli = launch_barber_cli
_shared.__all__.append("launch_barber_cli") if "launch_barber_cli" not in _shared.__all__ else None

_exports = {name: globals()[name] for name in ['add_service', 'appointments_menu', 'barber_menu', 'book_appointment', 'cancel_appointment', 'check_in_appointment', 'complete_appointment', 'customer_retention_stats', 'daily_schedule', 'get_current_user', 'is_staff_or_admin', 'launch_barber_cli', 'print_header', 'print_subheader', 'reports_menu', 'reschedule_appointment', 'revenue_report', 'service_popularity_report', 'services_menu', 'staff_menu', 'staff_performance_metrics', 'toggle_service_availability', 'update_service', 'view_my_appointments', 'view_services', 'view_staff', 'view_staff_schedules']}
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8, _part_9, _part_10, _part_11, _part_12, _part_13, _part_14, _part_15, _part_16, _part_17, _part_18, _part_19, _part_20, _part_21, _part_22, _part_23, _part_24, _part_25, _part_26, _part_27]:
    _module.__dict__.update(_exports)


# Keep extracted callables synchronized with compatibility-module globals.
for _module in [_part_1, _part_2, _part_3, _part_4, _part_5, _part_6, _part_7, _part_8, _part_9, _part_10, _part_11, _part_12, _part_13, _part_14, _part_15, _part_16, _part_17, _part_18, _part_19, _part_20, _part_21, _part_22, _part_23, _part_24, _part_25, _part_26, _part_27]:
    _module.__dict__.update({name: value for name, value in globals().items() if not name.startswith("__")})

__all__ = ['add_service', 'appointments_menu', 'barber_menu', 'book_appointment', 'cancel_appointment', 'check_in_appointment', 'complete_appointment', 'customer_retention_stats', 'daily_schedule', 'get_current_user', 'is_staff_or_admin', 'launch_barber_cli', 'print_header', 'print_subheader', 'reports_menu', 'reschedule_appointment', 'revenue_report', 'service_popularity_report', 'services_menu', 'staff_menu', 'staff_performance_metrics', 'toggle_service_availability', 'update_service', 'view_my_appointments', 'view_services', 'view_staff', 'view_staff_schedules']

if __name__ == "__main__":
    barber_menu()
