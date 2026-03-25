from education_system.university_system.modules.domain.housing.services.housing_accommodation import common as _common
from education_system.university_system.modules.domain.housing.services.housing_accommodation.common import (
    get_text, display_language_menu_option, log_menu_navigation,
)
from education_system.university_system.modules.domain.housing.services.housing_accommodation.database import init_housing_db
from education_system.university_system.modules.domain.housing.services.housing_accommodation.buildings import create_building, create_rooms_for_building, view_building, update_building, delete_building
from education_system.university_system.modules.domain.housing.services.housing_accommodation.applications import create_application, view_application, process_application
from education_system.university_system.modules.domain.housing.services.housing_accommodation.assignments import view_assignment, update_assignment_status
from education_system.university_system.modules.domain.housing.services.housing_accommodation.maintenance import create_maintenance_request, view_maintenance_requests, update_maintenance_request
from education_system.university_system.modules.domain.housing.services.housing_accommodation.payments import record_payment, view_payment_history
from education_system.university_system.modules.domain.housing.services.housing_accommodation.inventory import manage_inventory
from education_system.university_system.modules.domain.housing.services.housing_accommodation.inspections import create_inspection, view_inspections
from education_system.university_system.modules.domain.housing.services.housing_accommodation.reports import display_reports_menu


# Main Menu Function
@log_menu_navigation(description="Displaying housing accommodation menu")
def display_housing_accommodation_menu(auth_instance=None):
    """Display the housing accommodation management menu"""
    if auth_instance:
        _common.set_auth(auth_instance)
    auth = _common.auth

    # First, initialize the housing database if not already done
    init_housing_db()

    while True:
        print(f"\n{get_text('housing.title', default='Housing Accommodation Management')}")
        print("===============================")

        # Different menu options based on permissions
        if auth.check_permission('manage_accommodations'):
            # Administrator / Housing Staff Menu
            print(f"1. {get_text('housing.menu.building', default='Building Management')}")
            print(f"   - {get_text('housing.menu.building_desc', default='View/Add/Edit/Delete Buildings')}")
            print(f"   - {get_text('housing.menu.rooms_desc', default='Manage Rooms and Room Types')}")
            print(f"2. {get_text('housing.menu.applications', default='Housing Applications')}")
            print(f"   - {get_text('housing.menu.applications_desc', default='View/Process Applications')}")
            print(f"3. {get_text('housing.menu.assignments', default='Housing Assignments')}")
            print(f"   - {get_text('housing.menu.assignments_desc', default='View/Create/Update Assignments')}")
            print(f"4. {get_text('housing.menu.maintenance', default='Maintenance Requests')}")
            print(f"   - {get_text('housing.menu.maintenance_desc', default='View/Create/Update Maintenance Requests')}")
            print(f"5. {get_text('housing.menu.payments', default='Payment Management')}")
            print(f"   - {get_text('housing.menu.record_payments', default='Record Payments')}")
            print(f"   - {get_text('housing.menu.view_history', default='View Payment History')}")
            print(f"6. {get_text('housing.menu.inventory', default='Room Inventory')}")
            print(f"   - {get_text('housing.menu.inventory_desc', default='Manage Room Inventory Items')}")
            print(f"7. {get_text('housing.menu.inspections', default='Room Inspections')}")
            print(f"   - {get_text('housing.menu.inspections_desc', default='Create/View Room Inspections')}")
            print(f"8. {get_text('housing.menu.reports', default='Reports & Analytics')}")
            print(f"   - {get_text('housing.menu.reports_desc', default='Generate Reports and Search Records')}")
            print(f"9. {get_text('housing.menu.language', default='Language')}")
            print(f"10. {get_text('housing.menu.return_main', default='Return to Main Menu')}")

            choice = input(f"\n{get_text('housing.prompt.choice', default='Enter your choice (1-10)')}: ")

            if choice == '1':
                display_building_menu()
            elif choice == '2':
                display_application_menu()
            elif choice == '3':
                display_assignment_menu()
            elif choice == '4':
                display_maintenance_menu()
            elif choice == '5':
                display_payment_menu()
            elif choice == '6':
                manage_inventory()
            elif choice == '7':
                display_inspection_menu()
            elif choice == '8':
                display_reports_menu()
            elif choice == '9':
                display_language_menu_option()
            elif choice == '10':
                return
            else:
                print("Invalid choice. Please try again.")

        elif auth.check_permission('view_accommodations'):
            # View-only Staff Menu
            print(f"1. {get_text('housing.menu.view_buildings', default='View Buildings and Rooms')}")
            print(f"2. {get_text('housing.menu.view_applications', default='View Housing Applications')}")
            print(f"3. {get_text('housing.menu.view_assignments', default='View Housing Assignments')}")
            print(f"4. {get_text('housing.menu.view_maintenance', default='View Maintenance Requests')}")
            print(f"5. {get_text('housing.menu.view_payments', default='View Payment History')}")
            print(f"6. {get_text('housing.menu.view_inspections', default='View Room Inspections')}")
            print(f"7. {get_text('housing.menu.language', default='Language')}")
            print(f"8. {get_text('housing.menu.return_main', default='Return to Main Menu')}")

            choice = input(f"\n{get_text('housing.prompt.choice_8', default='Enter your choice (1-8)')}: ")

            if choice == '1':
                view_building()
            elif choice == '2':
                view_application()
            elif choice == '3':
                view_assignment()
            elif choice == '4':
                view_maintenance_requests()
            elif choice == '5':
                view_payment_history()
            elif choice == '6':
                view_inspections()
            elif choice == '7':
                display_language_menu_option()
            elif choice == '8':
                return
            else:
                print(get_text('housing.invalid_choice', default='Invalid choice. Please try again.'))

        elif auth.check_permission('view_own_record'):
            # Student Menu
            print(f"1. {get_text('housing.student.my_application', default='My Housing Application')}")
            print(f"   - {get_text('housing.student.apply', default='Apply for Housing')}")
            print(f"   - {get_text('housing.student.view_status', default='View My Application Status')}")
            print(f"2. {get_text('housing.student.my_assignment', default='My Housing Assignment')}")
            print(f"   - {get_text('housing.student.view_room', default='View My Room Assignment')}")
            print(f"3. {get_text('housing.menu.maintenance', default='Maintenance Requests')}")
            print(f"   - {get_text('housing.student.report_issue', default='Report Maintenance Issues')}")
            print(f"   - {get_text('housing.student.view_requests', default='View My Maintenance Requests')}")
            print(f"4. {get_text('housing.menu.language', default='Language')}")
            print(f"5. {get_text('housing.menu.return_main', default='Return to Main Menu')}")

            choice = input(f"\n{get_text('housing.prompt.choice_5', default='Enter your choice (1-5)')}: ")

            if choice == '1':
                # Display student application menu
                subChoiceValid = False
                while not subChoiceValid:
                    print(f"\n{get_text('housing.student.app_options', default='Housing Application Options:')}")
                    print(f"1. {get_text('housing.student.apply', default='Apply for Housing')}")
                    print(f"2. {get_text('housing.student.view_status', default='View My Application Status')}")
                    print(f"3. {get_text('housing.back', default='Back')}")

                    sub_choice = input(f"\n{get_text('housing.prompt.choice_3', default='Enter your choice (1-3)')}: ")

                    if sub_choice == '1':
                        create_application()
                        subChoiceValid = True
                    elif sub_choice == '2':
                        view_application()
                        subChoiceValid = True
                    elif sub_choice == '3':
                        subChoiceValid = True
                    else:
                        print(get_text('housing.invalid_choice', default='Invalid choice. Please try again.'))

            elif choice == '2':
                view_assignment()
            elif choice == '3':
                # Display student maintenance menu
                subChoiceValid = False
                while not subChoiceValid:
                    print(f"\n{get_text('housing.student.maint_options', default='Maintenance Request Options:')}")
                    print(f"1. {get_text('housing.student.report_issue', default='Report a Maintenance Issue')}")
                    print(f"2. {get_text('housing.student.view_requests', default='View My Maintenance Requests')}")
                    print(f"3. {get_text('housing.back', default='Back')}")

                    sub_choice = input(f"\n{get_text('housing.prompt.choice_3', default='Enter your choice (1-3)')}: ")

                    if sub_choice == '1':
                        create_maintenance_request()
                        subChoiceValid = True
                    elif sub_choice == '2':
                        view_maintenance_requests()
                        subChoiceValid = True
                    elif sub_choice == '3':
                        subChoiceValid = True
                    else:
                        print(get_text('housing.invalid_choice', default='Invalid choice. Please try again.'))

            elif choice == '4':
                display_language_menu_option()
            elif choice == '5':
                return
            else:
                print(get_text('housing.invalid_choice', default='Invalid choice. Please try again.'))
        else:
            print(get_text('housing.no_permission', default="You don't have permission to access housing accommodation management."))
            return

# Sub-menu Functions
@log_menu_navigation(description="Displaying building management menu")
def display_building_menu():
    """Display the building management menu"""
    while True:
        print("\nBuilding Management")
        print("==================")
        print("1. View Buildings")
        print("2. Add New Building")
        print("3. Update Building")
        print("4. Delete Building")
        print("5. Back to Housing Menu")

        choice = input("\nEnter your choice (1-5): ")

        if choice == '1':
            view_building()
        elif choice == '2':
            create_building()
        elif choice == '3':
            update_building()
        elif choice == '4':
            delete_building()
        elif choice == '5':
            return
        else:
            print("Invalid choice. Please try again.")

@log_menu_navigation(description="Displaying application management menu")
def display_application_menu():
    """Display the application management menu"""
    while True:
        print("\nHousing Application Management")
        print("=============================")
        print("1. View Applications")
        print("2. Create New Application")
        print("3. Process Application")
        print("4. Back to Housing Menu")

        choice = input("\nEnter your choice (1-4): ")

        if choice == '1':
            view_application()
        elif choice == '2':
            create_application()
        elif choice == '3':
            process_application()
        elif choice == '4':
            return
        else:
            print("Invalid choice. Please try again.")

@log_menu_navigation(description="Displaying assignment management menu")
def display_assignment_menu():
    """Display the assignment management menu"""
    while True:
        print("\nHousing Assignment Management")
        print("============================")
        print("1. View Assignments")
        print("2. Update Assignment Status")
        print("3. Back to Housing Menu")

        choice = input("\nEnter your choice (1-3): ")

        if choice == '1':
            view_assignment()
        elif choice == '2':
            update_assignment_status()
        elif choice == '3':
            return
        else:
            print("Invalid choice. Please try again.")

@log_menu_navigation(description="Displaying maintenance management menu")
def display_maintenance_menu():
    """Display the maintenance management menu"""
    while True:
        print("\nMaintenance Request Management")
        print("=============================")
        print("1. View Maintenance Requests")
        print("2. Create New Maintenance Request")
        print("3. Update Maintenance Request")
        print("4. Back to Housing Menu")

        choice = input("\nEnter your choice (1-4): ")

        if choice == '1':
            view_maintenance_requests()
        elif choice == '2':
            create_maintenance_request()
        elif choice == '3':
            update_maintenance_request()
        elif choice == '4':
            return
        else:
            print("Invalid choice. Please try again.")

@log_menu_navigation(description="Displaying payment management menu")
def display_payment_menu():
    """Display the payment management menu"""
    while True:
        print("\nPayment Management")
        print("=================")
        print("1. Record New Payment")
        print("2. View Payment History")
        print("3. Back to Housing Menu")

        choice = input("\nEnter your choice (1-3): ")

        if choice == '1':
            record_payment()
        elif choice == '2':
            view_payment_history()
        elif choice == '3':
            return
        else:
            print("Invalid choice. Please try again.")

@log_menu_navigation(description="Displaying inspection management menu")
def display_inspection_menu():
    """Display the inspection management menu"""
    while True:
        print("\nRoom Inspection Management")
        print("=========================")
        print("1. Create New Inspection")
        print("2. View Inspections")
        print("3. Back to Housing Menu")

        choice = input("\nEnter your choice (1-3): ")

        if choice == '1':
            create_inspection()
        elif choice == '2':
            view_inspections()
        elif choice == '3':
            return
        else:
            print("Invalid choice. Please try again.")
