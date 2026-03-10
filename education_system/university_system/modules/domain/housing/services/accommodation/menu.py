import logging

from education_system.university_system.modules.domain.housing.services.accommodation._common import (
    get_auth, get_text,
)
from education_system.university_system.modules.domain.housing.services.accommodation.db import (
    init_accommodation_db, migrate_audit_log_schema, fix_accommodation_db_schema,
    verify_database_schema,
)
from education_system.university_system.modules.domain.housing.services.accommodation.crud import (
    add_accommodation, view_accommodations, update_accommodation,
    remove_accommodation, view_students_by_accommodation,
)
from education_system.university_system.modules.domain.housing.services.accommodation.templates import (
    save_template, apply_template,
)
from education_system.university_system.modules.domain.housing.services.accommodation.approval import approve_accommodation
from education_system.university_system.modules.domain.housing.services.accommodation.notifications import check_expiry_notifications
from education_system.university_system.modules.domain.housing.services.accommodation.import_export import (
    bulk_import_from_csv, import_from_json, export_accommodations,
)
from education_system.university_system.modules.domain.housing.services.accommodation.dashboard import (
    show_dashboard_metrics, generate_statistics_report,
)


def display_accommodation_menu():
    """Interactive menu for accommodation management including advanced features."""
    auth = get_auth()

    init_accommodation_db()

    # Define menu options with permission requirements
    options = {
        '1': ('Register Student Accommodation', add_accommodation, ['manage_accommodations']),
        '2': ('Bulk Import from CSV', bulk_import_from_csv, ['manage_accommodations', 'batch_operations']),
        '3': ('Import from JSON', import_from_json, ['manage_accommodations', 'batch_operations']),
        '4': ('Save Template', save_template, ['manage_accommodations']),
        '5': ('Apply Template', apply_template, ['manage_accommodations']),
        '6': ('Search/Filter Accommodations', view_accommodations, ['view_accommodations']),
        '7': ('Update Accommodation', update_accommodation, ['manage_accommodations']),
        '8': ('Remove Accommodation', remove_accommodation, ['manage_accommodations']),
        '9': ('View by Accommodation Type', view_students_by_accommodation, ['view_accommodations']),
        '10': ('Approve/Reject Accommodations', approve_accommodation, ['approve_accommodations']),
        '11': ('Export Data', export_accommodations, ['export_data']),
        '12': ('Check Expiry Notifications', check_expiry_notifications, ['manage_accommodations']),
        '13': ('Dashboard Metrics', show_dashboard_metrics, ['view_accommodations']),
        '14': ('Generate Statistics Report', generate_statistics_report, ['view_accommodations']),
        '15': ('Return to Main Menu', None, [])
    }

    while True:
        print("\n" + get_text("housing.accommodation.menu.title", "Accommodation Management:"))
        print("=" * 40)

        # Display only options the user has permission for
        available_options = []

        for key, (desc, _, required_perms) in options.items():
            # If no auth or no permissions required, show the option
            if not auth or not required_perms or not auth.current_user:
                print(f"{key}. {desc}")
                available_options.append(key)
            # Otherwise, check permissions
            elif auth and auth.current_user:
                if all(auth.check_permission(perm) for perm in required_perms):
                    print(f"{key}. {desc}")
                    available_options.append(key)

        choice = input("\n" + get_text("housing.accommodation.input.enter_your_choice", "Enter your choice: ")).strip()

        if choice not in options:
            print(get_text("housing.accommodation.error.invalid_choice", "Invalid choice. Please try again."))
            continue

        if choice not in available_options:
            print(get_text("housing.accommodation.error.no_permission_option", "You don't have permission to access that option."))
            continue

        desc, func, _ = options[choice]
        if func:
            try:
                # If function requires a filepath parameter
                if func == bulk_import_from_csv:
                    filepath = input(get_text("housing.accommodation.input.csv_file_path", "CSV file path: ")).strip()
                    func(filepath)
                else:
                    func()
            except Exception as e:
                logging.error(f"Menu action error ({desc}): {e}")
                print(get_text("housing.accommodation.error.during_action", "An error occurred during {action}: {error}").format(action=desc, error=e))
                print(get_text("housing.accommodation.error.try_again_or_contact", "Please try again or contact technical support."))
        else:
            # Return to main menu
            break


if __name__ == "__main__":
    print(get_text("housing.accommodation.main.starting_migration", "Starting database schema migration..."))
    print("=" * 50)

    # Step 1: Migrate audit_log table
    print("\n" + get_text("housing.accommodation.main.step1", "Step 1: Migrating audit_log table..."))
    if migrate_audit_log_schema():
        print(get_text("housing.accommodation.main.audit_log_success", "audit_log migration successful"))
    else:
        print(get_text("housing.accommodation.main.audit_log_failed", "audit_log migration failed"))

    # Step 2: Fix accommodation database schema
    print("\n" + get_text("housing.accommodation.main.step2", "Step 2: Fixing accommodation database schema..."))
    if fix_accommodation_db_schema():
        print(get_text("housing.accommodation.main.schema_fix_success", "Accommodation schema fix successful"))
    else:
        print(get_text("housing.accommodation.main.schema_fix_failed", "Accommodation schema fix failed"))

    # Step 3: Verify final schema
    print("\n" + get_text("housing.accommodation.main.step3", "Step 3: Verifying database schema..."))
    verify_database_schema()

    print("\n" + "=" * 50)
    print(get_text("housing.accommodation.main.migration_completed", "Migration completed!"))

    display_accommodation_menu()
