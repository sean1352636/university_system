"""Settings CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def settings_menu(auth):
    """Settings menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.admin.settings.services.settings_service import SettingsService

    svc = SettingsService(get_db_path())

    while True:
        print_header("Settings")
        print_menu([("1", "List settings"), ("2", "View setting"), ("3", "Update setting"), ("0", "Back")])
        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_settings()
            for item in (items or []):
                print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            key = input("  Key: ").strip()
            print(f"  {key} = {svc.get_setting(key)}")
        elif choice == "3":
            key = input("  Key: ").strip()
            value = input("  Value: ").strip()
            try:
                svc.update_setting(key, value)
                print("\n  Updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
