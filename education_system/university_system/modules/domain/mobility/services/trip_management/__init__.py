# trip_management package - split from trip_management.py
# All public names are re-exported here for backwards compatibility.

from education_system.university_system.modules.domain.mobility.services.trip_management._common import set_auth, PDF_AVAILABLE, CALENDAR_AVAILABLE, HAS_AUTH

from education_system.university_system.infrastructure.database.db import get_connection

try:
    from education_system.university_system.core.activity_logger import log_activity
except ImportError:
    def log_activity(*args, **kwargs):
        pass

from education_system.university_system.modules.domain.mobility.services.trip_management.database import get_db_connection, safe_db_operation, init_trip_db

from education_system.university_system.modules.domain.mobility.services.trip_management.permissions import setup_trip_permissions, setup_report_permissions

from education_system.university_system.modules.domain.mobility.services.trip_management.trips import (
    view_trips_with_calendar,
    create_trip,
    view_trips,
    view_trip_details,
    update_trip,
    delete_trip,
)

from education_system.university_system.modules.domain.mobility.services.trip_management.registrations import (
    register_for_trip,
    view_my_trip_registrations,
    manage_trip_participants,
    update_payment_status,
    update_participant_status,
    remove_participant,
    cancel_trip_registration,
)

from education_system.university_system.modules.domain.mobility.services.trip_management.calendar_integration import (
    create_trip_calendar_event,
    view_trip_events_in_calendar,
)

from education_system.university_system.modules.domain.mobility.services.trip_management.reports import TripReportGenerator, generate_trip_report

from education_system.university_system.modules.domain.mobility.services.trip_management.itinerary import add_trip_itinerary, view_trip_itinerary

from education_system.university_system.modules.domain.mobility.services.trip_management.expenses import (
    manage_trip_expenses,
    add_expense,
    edit_expense,
    delete_expense,
)

from education_system.university_system.modules.domain.mobility.services.trip_management.staff import assign_trip_staff

from education_system.university_system.modules.domain.mobility.services.trip_management.menu import (
    display_trip_management_menu,
    integrate_trip_management_with_main,
    test_report_generation,
    test_trip_management,
)

if __name__ == "__main__":
    test_report_generation()
    # Run tests
    test_trip_management()
