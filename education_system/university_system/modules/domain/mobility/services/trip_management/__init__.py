# trip_management package - split from trip_management.py
# All public names are re-exported here for backwards compatibility.

from ._common import set_auth, PDF_AVAILABLE, CALENDAR_AVAILABLE, HAS_AUTH

from .database import get_db_connection, safe_db_operation, init_trip_db

from .permissions import setup_trip_permissions, setup_report_permissions

from .trips import (
    view_trips_with_calendar,
    create_trip,
    view_trips,
    view_trip_details,
    update_trip,
    delete_trip,
)

from .registrations import (
    register_for_trip,
    view_my_trip_registrations,
    manage_trip_participants,
    update_payment_status,
    update_participant_status,
    remove_participant,
    cancel_trip_registration,
)

from .calendar_integration import (
    create_trip_calendar_event,
    view_trip_events_in_calendar,
)

from .reports import TripReportGenerator, generate_trip_report

from .itinerary import add_trip_itinerary, view_trip_itinerary

from .expenses import (
    manage_trip_expenses,
    add_expense,
    edit_expense,
    delete_expense,
)

from .staff import assign_trip_staff

from .menu import (
    display_trip_management_menu,
    integrate_trip_management_with_main,
    test_report_generation,
    test_trip_management,
)

if __name__ == "__main__":
    test_report_generation()
    # Run tests
    test_trip_management()
