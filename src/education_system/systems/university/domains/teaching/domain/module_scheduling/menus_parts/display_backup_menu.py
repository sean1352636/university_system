"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_backup_menu(scheduler):
    """Display backup menu"""
    while True:
        print("\n💾 Backup Management:")
        print("1. Create New Backup")
        print("2. List All Backups")
        print("3. Create Automatic Backup")
        print("4. Return to Main Menu")

        choice = input("Enter your choice (1-4): ")

        if choice == '1':
            backup_name = input("Enter backup name (leave blank for auto-generated): ").strip()
            description = input("Enter description: ").strip()

            if backup_name:
                scheduler.create_backup(backup_name, description)
            else:
                scheduler.create_backup(description=description)

        elif choice == '2':
            scheduler.list_backups()

        elif choice == '3':
            # Set up automatic backup
            auto_backup = scheduler.get_system_setting('auto_backup', 'True')
            print(f"Automatic backup is currently: {'Enabled' if auto_backup == 'True' else 'Disabled'}")

            new_setting = input("Enable automatic backup? (y/n): ")
            if new_setting.lower() == 'y':
                scheduler.update_system_setting('auto_backup', 'True')
                # Create a backup now
                scheduler.create_backup(description="Automatic backup")
            else:
                scheduler.update_system_setting('auto_backup', 'False')

        elif choice == '4':
            break

        else:
            print("Invalid choice. Please try again.")
