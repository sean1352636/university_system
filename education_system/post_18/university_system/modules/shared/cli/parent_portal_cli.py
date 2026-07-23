"""Parent Portal CLI wrapper — routes parent users to the existing parent portal menu.

Adds Return to Login (R) and Shutdown (Q) options around the existing
display_parent_portal_menu().
"""

import logging

from education_system.post_18.university_system.infrastructure.shared_context import get_auth

logger = logging.getLogger(__name__)


class ParentPortalCLI:
    """CLI wrapper for the parent portal with login/shutdown controls."""

    def __init__(self):
        self.auth = get_auth()
        self._return_to_login = False

    def main_menu(self):
        while True:
            print("\n" + "=" * 50)
            print("  PARENT PORTAL")
            print("=" * 50)

            username = ''
            if self.auth and self.auth.current_user:
                username = self.auth.current_user.get('display_name') or self.auth.current_user.get('username', '')
            print(f"  Welcome, {username}!")

            print("\n  1.  Open Parent Portal")
            print("\n  R.  Return to Login")
            print("  Q.  Shutdown")
            print("=" * 50)

            choice = input("\n  Enter your choice: ").strip()

            if choice.lower() == 'q':
                print("\n  Shutting down...")
                try:
                    self.auth.logout()
                except Exception:
                    pass
                raise SystemExit(0)
            elif choice.lower() == 'r' or choice == '0':
                print("\n  Returning to login...")
                try:
                    self.auth.logout()
                except Exception:
                    pass
                self._return_to_login = True
                break
            elif choice == '1':
                self._open_portal()
            else:
                print("\n  Invalid choice. Please try again.")
                input("Press Enter to continue...")

    def _open_portal(self):
        try:
            from education_system.post_18.university_system.modules.domain.academics.services.parent_portal.menu import display_parent_portal_menu
            display_parent_portal_menu(self.auth)
        except ImportError as e:
            print(f"\n  Parent Portal module is not available: {e}")
            input("Press Enter to continue...")


def run_parent_portal():
    """Create a ParentPortalCLI instance and run the main menu."""
    portal = ParentPortalCLI()
    portal.main_menu()
    if portal._return_to_login:
        try:
            from education_system.shared.cli.login_cli import universal_cli_login
            result = universal_cli_login()
            if result:
                user_info, sys_key, role, shared_auth = result
                if sys_key == 'university':
                    from education_system.launcher.systems import run_university_cli
                    run_university_cli(user_info=user_info, role=role, shared_auth=shared_auth)
        except Exception as e:
            print(f"Error returning to login: {e}")
