"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_template_menu(scheduler):
    """Display template management menu"""
    while True:
        print("\n📋 Schedule Template Menu:")
        print("1. Save Current Schedule as Template")
        print("2. Load Template")
        print("3. List All Templates")
        print("4. Delete Template")
        print("5. Return to Main Menu")

        choice = input("Enter your choice (1-5): ")

        if choice == '1':
            name = input("Enter template name: ")
            description = input("Enter description (optional): ")
            scheduler.save_schedule_template(name, description)

        elif choice == '2':
            scheduler.list_schedule_templates()
            template_name = input("\nEnter template name to load: ")
            clear_existing = input("Clear existing schedules first? (y/n): ").lower() == 'y'
            scheduler.load_schedule_template(template_name, clear_existing)

        elif choice == '3':
            scheduler.list_schedule_templates()

        elif choice == '4':
            scheduler.list_schedule_templates()
            template_name = input("\nEnter template name to delete: ")
            confirm = input(f"Delete template '{template_name}'? (y/n): ")
            if confirm.lower() == 'y':
                conn = get_connection(scheduler.db_path, row_factory=False)
                cursor = conn.cursor()
                cursor.execute('DELETE FROM schedule_templates WHERE template_name = ?', (template_name,))
                conn.commit()
                conn.close()
                print(f"Template '{template_name}' deleted.")

        elif choice == '5':
            break

        else:
            print("Invalid choice. Please try again.")
