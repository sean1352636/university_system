"""CLI interface for settings management."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.modules.domain.settings.services.settings_service import SettingsService
from education_system.college_system.infrastructure.auth.core import UserAuth


def settings_menu(auth: UserAuth):
    """Settings management menu."""
    svc = SettingsService(auth._db_path)
    user_id = auth.current_user["user_id"]
    role = auth.current_user.get("role", "student")
    is_admin = role == "admin"

    while True:
        print_header("Settings")
        options = [
            ("1", "View My Settings"),
            ("2", "Change Theme"),
            ("3", "Toggle Notifications"),
        ]
        if is_admin:
            options.append(("4", "System Settings"))
        options.append(("0", "Back"))
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _view_settings(svc, user_id)
        elif choice == "2":
            _change_theme(svc, user_id)
        elif choice == "3":
            _toggle_notifications(svc, user_id)
        elif choice == "4" and is_admin:
            _system_settings(svc, user_id)
        elif choice == "0":
            break


def _view_settings(svc, user_id):
    settings = svc.get_all_user_settings(user_id)
    if not settings:
        print("\n  No settings configured yet (using defaults).")
        print("  Theme: light | Notifications: enabled | Language: en | Items/page: 25")
        return

    print("\n  Your Settings:")
    for key, value in sorted(settings.items()):
        print(f"  {key}: {value}")


def _change_theme(svc, user_id):
    current = svc.get_user_setting(user_id, "theme", "light")
    print(f"\n  Current theme: {current}")
    new_theme = input("  New theme (light/dark): ").strip().lower()
    if new_theme not in ("light", "dark"):
        print("\n  Invalid theme.")
        return
    try:
        svc.set_user_setting(user_id, "theme", new_theme)
        print(f"\n  Theme changed to {new_theme}.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _toggle_notifications(svc, user_id):
    current = svc.get_user_setting(user_id, "notifications_enabled", "true")
    enabled = current == "true"
    new_value = "false" if enabled else "true"
    try:
        svc.set_user_setting(user_id, "notifications_enabled", new_value)
        state = "enabled" if new_value == "true" else "disabled"
        print(f"\n  Notifications {state}.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _system_settings(svc, user_id):
    while True:
        print_header("System Settings")
        settings = svc.get_all_system_settings()
        if settings:
            for key, value in sorted(settings.items()):
                print(f"  {key}: {value}")
        else:
            print("  No system settings configured.")

        options = [
            ("1", "Set College Name"),
            ("2", "Set Academic Year"),
            ("3", "Set Default Capacity"),
            ("0", "Back"),
        ]
        print()
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            value = input("  College name: ").strip()
            if value:
                svc.set_system_setting("college_name", value, user_id)
                print("\n  Saved.")
        elif choice == "2":
            value = input("  Academic year (e.g. 2025-2026): ").strip()
            if value:
                svc.set_system_setting("academic_year", value, user_id)
                print("\n  Saved.")
        elif choice == "3":
            value = input("  Default capacity: ").strip()
            if value:
                svc.set_system_setting("default_capacity", value, user_id)
                print("\n  Saved.")
        elif choice == "0":
            break
