"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_data_validation_menu(scheduler):
    """Display data validation menu"""
    while True:
        print("\n🔍 Data Validation & Maintenance:")
        print("1. Validate Data Consistency")
        print("2. Clean Orphaned Records")
        print("3. Check Database Integrity")
        print("4. Repair Common Issues")
        print("5. Return to Main Menu")

        choice = input("Enter your choice (1-5): ")

        if choice == '1':
            issues = scheduler.validate_data_consistency()
            if issues:
                fix_choice = input("\nFix detected issues automatically? (y/n): ")
                if fix_choice.lower() == 'y':
                    scheduler.clean_orphaned_records()

        elif choice == '2':
            confirm = input("This will remove orphaned records. Continue? (y/n): ")
            if confirm.lower() == 'y':
                scheduler.clean_orphaned_records()

        elif choice == '3':
            # Basic integrity check
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()

            try:
                cursor.execute('PRAGMA integrity_check')
                result = cursor.fetchone()
                if result[0] == 'ok':
                    print("Database integrity check: PASSED")
                else:
                    print(f"Database integrity check: FAILED - {result[0]}")
            except Exception as e:
                print(f"Error checking integrity: {e}")
            finally:
                conn.close()

        elif choice == '4':
            print("Running automated repair...")

            # Run validation and cleanup
            issues = scheduler.validate_data_consistency()
            if issues:
                scheduler.clean_orphaned_records()
                print("Common issues repaired.")
            else:
                print("No issues found to repair.")

        elif choice == '5':
            break

        else:
            print("Invalid choice. Please try again.")
