from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.modules.shared.utils.i18n import get_text, get_current_language
from education_system.university_system.modules.shared.utils.language_selector import display_language_menu_option
from education_system.university_system.modules.domain.mobility.services.trip_management import (
    display_trip_management_menu,
    view_trips,
    create_trip,
    register_for_trip,
    view_my_trip_registrations,
    manage_trip_participants
)
from education_system.university_system.modules.domain.mobility.services.parking_management.permits import create_parking_permit, view_parking_permit, update_parking_permit, delete_parking_permit
from education_system.university_system.modules.domain.mobility.services.parking_management.vehicles import register_vehicle, view_vehicle, update_vehicle, delete_vehicle
from education_system.university_system.modules.domain.mobility.services.parking_management.violations import record_violation, view_violations, update_violation, delete_violation
from education_system.university_system.modules.domain.mobility.services.parking_management.lots import view_parking_lots, add_parking_lot, update_parking_lot, delete_parking_lot, update_available_spaces
from education_system.university_system.modules.domain.mobility.services.parking_management.reports import (generate_permit_report, generate_violation_report, generate_compliance_report,
                      generate_analytics_dashboard, generate_revenue_report, generate_user_activity_report)
from education_system.university_system.modules.domain.mobility.services.parking_management.exports import export_data
from education_system.university_system.modules.domain.mobility.services.parking_management.core import init_db
from education_system.university_system.modules.domain.mobility.services.parking_management import core

_t = get_text


def pay_violation_fine():
    print("Feature not yet implemented.")

def check_lot_availability():
    print("Feature not yet implemented.")

def generate_occupancy_report():
    print("Feature not yet implemented.")


def display_permit_menu():
    auth = core.auth

    while True:
        print("\n" + _t("parking.section.permit_menu") + ":")
        print("1. " + _t("parking.menu.create_permit"))
        print("2. " + _t("parking.menu.view_permits"))
        print("3. " + _t("parking.menu.update_permit"))
        print("4. " + _t("parking.menu.delete_permit"))
        print("5. " + _t("parking.menu.return_to_main"))

        choice = input("Enter your choice (1-5): ")

        if choice == '1' and auth.check_permission('create_permit'):
            create_parking_permit()
        elif choice == '2' and (auth.check_permission('view_any_permit') or auth.check_permission('view_own_permit')):
            view_parking_permit()
        elif choice == '3' and (auth.check_permission('update_any_permit') or auth.check_permission('update_own_permit')):
            update_parking_permit()
        elif choice == '4' and auth.check_permission('delete_any_permit'):
            delete_parking_permit()
        elif choice == '5':
            return
        else:
            print(_t("parking.error.invalid_choice_or_no_permission"))


def display_vehicle_menu():
    auth = core.auth

    while True:
        print("\n" + _t("parking.section.vehicle_menu") + ":")
        print("1. " + _t("parking.menu.register_vehicle"))
        print("2. " + _t("parking.menu.view_vehicles"))
        print("3. " + _t("parking.menu.update_vehicle"))
        print("4. " + _t("parking.menu.delete_vehicle"))
        print("5. " + _t("parking.menu.return_to_main"))

        choice = input("Enter your choice (1-5): ")

        if choice == '1' and (auth.check_permission('register_vehicle') or auth.check_permission('register_own_vehicle')):
            register_vehicle()
        elif choice == '2' and (auth.check_permission('view_any_vehicle') or auth.check_permission('view_own_vehicle')):
            view_vehicle()
        elif choice == '3' and (auth.check_permission('update_any_vehicle') or auth.check_permission('update_own_vehicle')):
            update_vehicle()
        elif choice == '4' and (auth.check_permission('delete_any_vehicle') or auth.check_permission('delete_own_vehicle')):
            delete_vehicle()
        elif choice == '5':
            return
        else:
            print(_t("parking.error.invalid_choice_or_no_permission"))


def display_violation_menu():
    auth = core.auth

    while True:
        print("\n" + _t("parking.section.violation_menu") + ":")
        print("1. " + _t("parking.menu.record_violation"))
        print("2. " + _t("parking.menu.view_violations"))
        print("3. " + _t("parking.menu.update_violation"))
        print("4. " + _t("parking.menu.delete_violation"))
        print("5. " + _t("parking.menu.return_to_main"))

        choice = input("Enter your choice (1-5): ")

        if choice == '1' and auth.check_permission('record_violation'):
            record_violation()
        elif choice == '2' and (auth.check_permission('view_any_violation') or auth.check_permission('view_own_violation')):
            view_violations()
        elif choice == '3' and auth.check_permission('update_violation'):
            update_violation()
        elif choice == '4' and auth.check_permission('delete_violation'):
            delete_violation()
        elif choice == '5':
            return
        else:
            print(_t("parking.error.invalid_choice_or_no_permission"))


def display_lot_menu():
    auth = core.auth

    while True:
        print("\n" + _t("parking.section.lot_menu") + ":")
        print("1. " + _t("parking.menu.view_parking_lots"))
        print("2. " + _t("parking.menu.add_parking_lot"))
        print("3. " + _t("parking.menu.update_parking_lot"))
        print("4. " + _t("parking.menu.delete_parking_lot"))
        print("5. " + _t("parking.menu.update_available_spaces"))
        print("6. " + _t("parking.menu.return_to_main"))

        choice = input("Enter your choice (1-6): ")

        if choice == '1':
            view_parking_lots()
        elif choice == '2' and auth.check_permission('manage_parking_lots'):
            add_parking_lot()
        elif choice == '3' and auth.check_permission('manage_parking_lots'):
            update_parking_lot()
        elif choice == '4' and auth.check_permission('manage_parking_lots'):
            delete_parking_lot()
        elif choice == '5' and auth.check_permission('manage_parking_lots'):
            update_available_spaces()
        elif choice == '6':
            return
        else:
            print(_t("parking.error.invalid_choice_or_no_permission"))


def display_export_menu():
    """Display the export menu for parking data"""
    auth = core.auth

    while True:
        print("\n" + _t("parking.section.export_menu") + ":")
        print("1. " + _t("parking.menu.export_to_csv"))
        print("2. " + _t("parking.menu.export_to_excel"))
        print("3. " + _t("parking.menu.export_to_pdf"))
        print("4. " + _t("parking.menu.export_to_txt"))
        print("5. " + _t("parking.menu.return_to_main"))

        choice = input("Enter your choice (1-5): ")

        if choice == '1':
            export_data('csv')
        elif choice == '2':
            export_data('excel')
        elif choice == '3':
            export_data('pdf')
        elif choice == '4':
            export_data('txt')
        elif choice == '5':
            return
        else:
            print(_t("common.invalid_choice"))


def display_reports_menu():
    """Display the reports menu for parking data"""
    auth = core.auth

    while True:
        print("\n" + _t("parking.section.reports_menu") + ":")
        print("1. " + _t("parking.menu.permit_status_report"))
        print("2. " + _t("parking.menu.violation_summary_report"))
        print("3. " + _t("parking.menu.parking_lot_occupancy_report"))
        print("4. " + _t("parking.menu.revenue_report"))
        print("5. " + _t("parking.menu.user_activity_report"))
        print("6. " + _t("parking.menu.return_to_main"))

        choice = input("Enter your choice (1-6): ")

        if choice == '1' and auth.check_permission('generate_reports'):
            generate_permit_report()
        elif choice == '2' and auth.check_permission('generate_reports'):
            generate_violation_report()
        elif choice == '3' and auth.check_permission('generate_reports'):
            generate_occupancy_report()
        elif choice == '4' and auth.check_permission('generate_reports'):
            generate_revenue_report()
        elif choice == '5' and auth.check_permission('generate_reports'):
            generate_user_activity_report()
        elif choice == '6':
            return
        else:
            print(_t("parking.error.invalid_choice_or_no_permission"))


def display_parking_menu():
    auth = core.auth

    # Initialize the database
    init_db()

    # Initialize authentication system if not already done
    if auth is None:
        auth = get_auth()
        if auth is None:
            auth = UserAuth()
        core.auth = auth

    while True:
        print("\n" + "="*100)
        print(f"  {get_text('parking.title', default='PARKING & TRANSPORTATION MANAGEMENT SYSTEM')}")
        print("="*100)
        logged_in_msg = get_text('parking.logged_in', default='Logged in as: {user} ({role})').format(user=auth.current_user['username'], role=auth.current_user['role']) if auth.current_user else get_text('parking.not_logged_in', default='Not logged in')
        print(logged_in_msg)

        print(f"\n🅿️ {get_text('parking.section.permits', default='Parking Permits')}:")
        print(f"{'1.  ' + get_text('parking.menu.create_permit', default='Create Permit'):<25} {'2.  ' + get_text('parking.menu.view_permits', default='View Permits'):<25} {'3.  ' + get_text('parking.menu.update_permit', default='Update Permit'):<25} {'4.  ' + get_text('parking.menu.delete_permit', default='Delete Permit'):<25}")

        print(f"\n🚗 {get_text('parking.section.vehicles', default='Vehicle Management')}:")
        print(f"{'5.  ' + get_text('parking.menu.register_vehicle', default='Register Vehicle'):<25} {'6.  ' + get_text('parking.menu.view_vehicles', default='View Vehicles'):<25} {'7.  ' + get_text('parking.menu.update_vehicle', default='Update Vehicle'):<25} {'8.  ' + get_text('parking.menu.delete_vehicle', default='Delete Vehicle'):<25}")

        print(f"\n⚠️ {get_text('parking.section.violations', default='Parking Violations')}:")
        print(f"{'9.  ' + get_text('parking.menu.record_violation', default='Record Violation'):<25} {'10. ' + get_text('parking.menu.view_violations', default='View Violations'):<25} {'11. ' + get_text('parking.menu.update_status', default='Update Status'):<25} {'12. ' + get_text('parking.menu.pay_fine', default='Pay Fine'):<25}")

        print(f"\n🏢 {get_text('parking.section.lots', default='Parking Lots')}:")
        print(f"{'13. ' + get_text('parking.menu.create_lot', default='Create Lot'):<25} {'14. ' + get_text('parking.menu.view_lots', default='View Lots'):<25} {'15. ' + get_text('parking.menu.update_lot', default='Update Lot'):<25} {'16. ' + get_text('parking.menu.check_availability', default='Check Availability'):<25}")

        print(f"\n🚍 {get_text('parking.section.transport', default='Transportation & Trips')}:")
        print(f"{'17. ' + get_text('parking.menu.view_trips', default='View All Trips'):<25} {'18. ' + get_text('parking.menu.create_trip', default='Create Trip'):<25} {'19. ' + get_text('parking.menu.register_trip', default='Register for Trip'):<25} {'20. ' + get_text('parking.menu.my_registrations', default='My Registrations'):<25}")
        print(f"{'21. ' + get_text('parking.menu.manage_participants', default='Manage Participants'):<25}")

        print(f"\n📊 {get_text('parking.section.reports', default='Reports & Data')}:")
        print(f"{'22. ' + get_text('parking.menu.parking_reports', default='Parking Reports'):<25} {'23. ' + get_text('parking.menu.trip_reports', default='Trip Reports'):<25} {'24. ' + get_text('parking.menu.export_parking', default='Export Parking'):<25} {'25. ' + get_text('parking.menu.export_trip', default='Export Trip Data'):<25}")

        print(f"\n↩️ {get_text('parking.section.navigation', default='Navigation')}:")
        print(f"26. {get_text('parking.menu.language', default='Language')}")
        print(f"27. {get_text('parking.menu.return_main', default='Return to Main Menu')}")
        print("="*100)

        choice = input(f"\n{get_text('parking.prompt.choice', default='Enter your choice (1-27)')}: ")

        # Parking Permits (1-4)
        if choice == '1' and auth.check_permission('create_permit'):
            create_parking_permit()
        elif choice == '2' and (auth.check_permission('view_any_permit') or auth.check_permission('view_own_permit')):
            view_parking_permit()
        elif choice == '3' and (auth.check_permission('update_any_permit') or auth.check_permission('update_own_permit')):
            update_parking_permit()
        elif choice == '4' and auth.check_permission('delete_any_permit'):
            delete_parking_permit()

        # Vehicles (5-8)
        elif choice == '5' and auth.check_permission('register_vehicle'):
            register_vehicle()
        elif choice == '6' and (auth.check_permission('view_any_vehicle') or auth.check_permission('view_own_vehicle')):
            view_vehicle()
        elif choice == '7' and (auth.check_permission('update_any_vehicle') or auth.check_permission('update_own_vehicle')):
            update_vehicle()
        elif choice == '8' and auth.check_permission('delete_any_vehicle'):
            delete_vehicle()

        # Violations (9-12)
        elif choice == '9' and auth.check_permission('record_violation'):
            record_violation()
        elif choice == '10' and (auth.check_permission('view_any_violation') or auth.check_permission('view_own_violation')):
            view_violations()
        elif choice == '11' and auth.check_permission('update_violation'):
            update_violation()
        elif choice == '12' and auth.check_permission('view_own_violation'):
            pay_violation_fine()

        # Parking Lots (13-16)
        elif choice == '13' and auth.check_permission('manage_parking_lots'):
            add_parking_lot()
        elif choice == '14':
            view_parking_lots()
        elif choice == '15' and auth.check_permission('manage_parking_lots'):
            update_parking_lot()
        elif choice == '16':
            check_lot_availability()

        # Transportation & Trips (17-21)
        elif choice == '17' and auth.check_permission('view_trips'):
            view_trips()
        elif choice == '18' and auth.check_permission('create_trips'):
            create_trip()
        elif choice == '19' and auth.check_permission('register_for_trips'):
            register_for_trip()
        elif choice == '20' and auth.check_permission('view_own_trip_registrations'):
            view_my_trip_registrations()
        elif choice == '21' and auth.check_permission('manage_trip_participants'):
            manage_trip_participants()

        # Reports & Data (22-25)
        elif choice == '22':
            display_reports_menu()
        elif choice == '23' and auth.check_permission('generate_trip_reports'):
            # Trip report generation
            print("\n📊 Trip Report Generation")
            print("="*50)
            print(_t("parking.trip.generator_info"))
            print("  • Trip Summary Reports")
            print("  • Participant List Reports")
            print("  • Financial Reports")
            print("\n" + _t("parking.msg.access_via_trip_menu"))
            print(_t("parking.trip.import_hint"))
            input("\nPress Enter to continue...")
        elif choice == '24':
            display_export_menu()
        elif choice == '25' and auth.check_permission('generate_trip_reports'):
            print("\n📊 Trip data export functionality available via Reports menu")
            input("\nPress Enter to continue...")

        # Navigation (26-27)
        elif choice == '26':
            display_language_menu_option()
        elif choice == '27':
            print(get_text('parking.returning', default='Returning to main menu...'))
            return
        else:
            print(get_text('parking.invalid_choice', default='Invalid choice or insufficient permissions. Please try again.'))
