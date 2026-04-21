"""
Student Portal CLI — the CLI equivalent of the Student Portal GUI.

When a student logs in via CLI, they see this focused menu instead of the
full display_menu(). The menu is organised by category, mirroring the GUI
sidebar in student_portal.py.
"""

import logging

from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


class StudentPortalCLI:
    """Student-facing CLI portal with category-organised menu."""

    def __init__(self):
        self.auth = get_auth()
        self.student_id = None
        if self.auth and self.auth.current_user:
            self.student_id = (
                self.auth.current_user.get('student_id')
                or self.auth.current_user.get('id')
                or self.auth.current_user.get('user_id')
            )

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def view_dashboard(self):
        """Show current GPA, enrolled modules, and upcoming assignments."""
        username = ''
        if self.auth and self.auth.current_user:
            username = (
                self.auth.current_user.get('display_name')
                or self.auth.current_user.get('username', '')
            )

        print("\n" + "=" * 60)
        print(f"  STUDENT DASHBOARD — {username}")
        print("=" * 60)

        conn = None
        try:
            conn = get_connection()

            # --- GPA & Credits ---
            print("\n--- GPA & Credits ---")
            try:
                row = conn.execute(
                    "SELECT AVG(grade_point) AS gpa, SUM(credits) AS total_credits "
                    "FROM module_grades WHERE student_id = ?",
                    (self.student_id,),
                ).fetchone()
                if row and row['gpa'] is not None:
                    print(f"  Current GPA:    {row['gpa']:.2f}")
                    print(f"  Total Credits:  {row['total_credits'] or 0}")
                else:
                    print("  No grade data available yet.")
            except Exception as e:
                logger.debug(f"Could not fetch GPA: {e}")
                print("  GPA data not available.")

            # --- Enrolled Modules ---
            print("\n--- Enrolled Modules ---")
            try:
                modules = conn.execute(
                    "SELECT module_name FROM student_modules WHERE student_id = ?",
                    (self.student_id,),
                ).fetchall()
                if modules:
                    for i, mod in enumerate(modules, 1):
                        print(f"  {i}. {mod['module_name']}")
                else:
                    print("  No modules enrolled.")
            except Exception as e:
                logger.debug(f"Could not fetch modules: {e}")
                print("  Module data not available.")

            # --- Upcoming Assignments ---
            print("\n--- Upcoming Assignments ---")
            try:
                assignments = conn.execute(
                    "SELECT title, due_date FROM assignments "
                    "WHERE student_id = ? AND due_date > date('now') "
                    "ORDER BY due_date ASC LIMIT 10",
                    (self.student_id,),
                ).fetchall()
                if assignments:
                    for a in assignments:
                        print(f"  - {a['title']}  (due: {a['due_date']})")
                else:
                    print("  No upcoming assignments.")
            except Exception as e:
                logger.debug(f"Could not fetch assignments: {e}")
                print("  Assignment data not available.")

        except Exception as e:
            logger.error(f"Dashboard error: {e}")
            print(f"\n  Error loading dashboard: {e}")
        finally:
            if conn:
                conn.close()

        input("\nPress Enter to continue...")

    # ------------------------------------------------------------------
    # Menu handlers — each lazily imports the required module
    # ------------------------------------------------------------------

    def _handle_academic_progress(self):
        try:
            from education_system.university_system.modules.domain.academics.academic_progress.cli.progress_cli import AcademicProgressCLI
            cli = AcademicProgressCLI()
            cli.run()
        except ImportError as e:
            print(f"\n  Academic Progress module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_grade_tracking(self):
        try:
            from education_system.university_system.modules.domain.academics.gui.grade_tracking_management_gui import display_enhanced_grade_menu
            if display_enhanced_grade_menu:
                display_enhanced_grade_menu()
            else:
                print("\n  Grade Tracking is not available.")
                input("Press Enter to continue...")
        except ImportError:
            print("\n  Grade Tracking module is not available.")
            input("Press Enter to continue...")

    def _handle_course_planning(self):
        try:
            from education_system.university_system.modules.domain.academics.gui.course_management_gui.cli.course_planning_cli import display_course_planning_menu
            display_course_planning_menu()
        except ImportError as e:
            print(f"\n  Course Planning module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_library(self):
        try:
            from education_system.university_system.modules.domain.academics.services.library.menu import display_library_menu
            display_library_menu()
        except ImportError as e:
            print(f"\n  Library module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_office_hours(self):
        try:
            from education_system.university_system.modules.domain.academics.cli.office_hours_cli import display_office_hours_menu
            display_office_hours_menu(self.auth)
        except ImportError as e:
            print(f"\n  Office Hours module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_student_registration(self):
        try:
            from education_system.university_system.modules.shared.cli.student_operations import display_student_records_menu
            display_student_records_menu()
        except ImportError as e:
            print(f"\n  Student Registration module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_academic_calendar(self):
        try:
            from education_system.university_system.modules.domain.academics.services.academic_calendar.cli import display_academic_calendar_menu
            display_academic_calendar_menu()
        except ImportError as e:
            print(f"\n  Academic Calendar module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_timetable(self):
        try:
            from education_system.university_system.modules.domain.academics.services.timetable import display_timetable_optimizer_menu
            display_timetable_optimizer_menu()
        except ImportError as e:
            print(f"\n  Timetable module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_financial_aid(self):
        try:
            from education_system.university_system.modules.shared.cli.menu_router import display_financial_aid_menu
            display_financial_aid_menu(self.auth)
        except ImportError as e:
            print(f"\n  Financial Aid module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_health_portal(self):
        try:
            from education_system.university_system.modules.domain.health.services.health_portal import display_health_portal_menu
            display_health_portal_menu(self.auth)
        except ImportError as e:
            print(f"\n  Health Portal module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_student_union(self):
        try:
            from education_system.university_system.modules.domain.student_affairs.gui.student_union_management_gui import display_student_union_menu
            if display_student_union_menu:
                try:
                    from education_system.university_system.modules.domain.student_affairs.student_union import set_auth as _su_set_auth
                    _su_set_auth(self.auth)
                except ImportError:
                    pass
                display_student_union_menu()
            else:
                print("\n  Student Union menu is not available.")
                input("Press Enter to continue...")
        except ImportError:
            print("\n  Student Union module is not available.")
            input("Press Enter to continue...")

    def _handle_campus_events(self):
        try:
            from education_system.university_system.modules.domain.campus.services.campus_events_core import display_campus_events_menu
            display_campus_events_menu(self.auth)
        except ImportError as e:
            print(f"\n  Campus Events module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_career_services(self):
        try:
            from education_system.university_system.modules.domain.career.services.career_services_core import display_career_services_menu
            display_career_services_menu(self.auth)
        except ImportError as e:
            print(f"\n  Career Services module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_university_shop(self):
        try:
            from education_system.university_system.modules.domain.commerce.services.shop_management.menus import display_shop_menu
            display_shop_menu()
        except ImportError as e:
            print(f"\n  University Shop module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_cafe_system(self):
        try:
            from education_system.university_system.modules.services.cli.cafe_system_cli import display_cafe_menu
            display_cafe_menu()
        except ImportError as e:
            print(f"\n  Cafe System module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_takeaway(self):
        try:
            from education_system.university_system.modules.domain.commerce.services.takeaway import display_takeaway_menu
            display_takeaway_menu()
        except ImportError as e:
            print(f"\n  Takeaway module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_grocery_shop(self):
        try:
            from education_system.university_system.modules.domain.commerce.services.grocery import display_grocery_menu
            display_grocery_menu()
        except ImportError as e:
            print(f"\n  Grocery Shop module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_helpdesk(self):
        try:
            from education_system.university_system.modules.domain.student_affairs.services.helpdesk import display_helpdesk_menu
            display_helpdesk_menu(self.auth)
        except ImportError as e:
            print(f"\n  Helpdesk module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_internship_portal(self):
        try:
            from education_system.university_system.modules.domain.student_affairs.services.internship_management import display_internship_menu
            display_internship_menu()
        except ImportError as e:
            print(f"\n  Internship Portal module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_communication_hub(self):
        try:
            from education_system.university_system.modules.shared.cli.menu_router import display_communication_hub_menu
            display_communication_hub_menu(self.auth)
        except ImportError as e:
            print(f"\n  Communication Hub module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_todo(self):
        try:
            from education_system.university_system.modules.shared.cli.imports import TODO_AVAILABLE, todo_menu
            if TODO_AVAILABLE and todo_menu:
                todo_menu()
            else:
                print("\n  To-Do List is not available.")
                input("Press Enter to continue...")
        except ImportError:
            print("\n  To-Do List module is not available.")
            input("Press Enter to continue...")

    def _handle_change_password(self):
        """Prompt the student to change their password."""
        print("\n" + "=" * 50)
        print("  CHANGE PASSWORD")
        print("=" * 50)
        try:
            username = self.auth.current_user.get('username', '')
            current_password = input("Enter current password: ").strip()
            new_password = input("Enter new password (min 8 chars, mix of letters & numbers): ").strip()
            confirm_password = input("Confirm new password: ").strip()

            if new_password != confirm_password:
                print("\n  Passwords do not match.")
                input("Press Enter to continue...")
                return

            if self.auth.change_password(username, current_password, new_password):
                print("\n  Password changed successfully!")
            else:
                print("\n  Failed to change password. Please check your current password.")
        except Exception as e:
            print(f"\n  Error changing password: {e}")
        input("Press Enter to continue...")

    def _handle_course_catalog(self):
        try:
            from education_system.university_system.modules.domain.academics.cli.course_catalog_cli import display_course_catalog_menu
            display_course_catalog_menu(self.auth)
        except ImportError as e:
            print(f"\n  Course Catalog module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_transfer_credits(self):
        try:
            from education_system.university_system.modules.domain.academics.cli.transfer_credits_cli import display_transfer_credits_menu
            display_transfer_credits_menu(self.auth)
        except ImportError as e:
            print(f"\n  Transfer Credits module is not available: {e}")
            input("Press Enter to continue...")

    # ------------------------------------------------------------------
    # Main menu loop
    # ------------------------------------------------------------------

    def main_menu(self):
        """Display the student portal menu and handle choices."""
        username = ''
        if self.auth and self.auth.current_user:
            username = (
                self.auth.current_user.get('display_name')
                or self.auth.current_user.get('username', '')
            )

        while True:
            print("\n" + "=" * 50)
            print("  STUDENT PORTAL")
            print("=" * 50)
            print(f"  Welcome, {username}!")

            print("\n  DASHBOARD:")
            print("    1.  View Dashboard (GPA, modules, assignments)")

            print("\n  ACADEMIC:")
            print("    2.  Academic Progress")
            print("    3.  Grade Tracking")
            print("    4.  Course Planning")
            print("    5.  Library")
            print("    6.  Office Hours")
            print("    7.  Student Registration")

            print("\n  SCHEDULE:")
            print("    8.  Academic Calendar")
            print("    9.  My Timetable")

            print("\n  FINANCE:")
            print("    10. Financial Aid")

            print("\n  HEALTH & WELLNESS:")
            print("    11. Health Portal")

            print("\n  STUDENT LIFE:")
            print("    12. Student Union")
            print("    13. Campus Events")
            print("    14. Career Services")

            print("\n  SERVICES:")
            print("    15. University Shop")
            print("    16. Cafe System")
            print("    17. Takeaway")
            print("    18. Grocery Shop")

            print("\n  SUPPORT:")
            print("    19. Helpdesk")
            print("    20. Internship Portal")

            print("\n  COMMUNICATION:")
            print("    21. Communication Hub")
            print("    22. To-Do List")

            print("\n  ACADEMIC:")
            print("    24. Course Catalog")
            print("    25. Transfer Credits")

            print("\n  ACCOUNT:")
            print("    23. Change Password")

            print("\n    R.  Return to Login")
            print("    Q.  Shutdown")
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
                self.view_dashboard()
            elif choice == '2':
                self._handle_academic_progress()
            elif choice == '3':
                self._handle_grade_tracking()
            elif choice == '4':
                self._handle_course_planning()
            elif choice == '5':
                self._handle_library()
            elif choice == '6':
                self._handle_office_hours()
            elif choice == '7':
                self._handle_student_registration()
            elif choice == '8':
                self._handle_academic_calendar()
            elif choice == '9':
                self._handle_timetable()
            elif choice == '10':
                self._handle_financial_aid()
            elif choice == '11':
                self._handle_health_portal()
            elif choice == '12':
                self._handle_student_union()
            elif choice == '13':
                self._handle_campus_events()
            elif choice == '14':
                self._handle_career_services()
            elif choice == '15':
                self._handle_university_shop()
            elif choice == '16':
                self._handle_cafe_system()
            elif choice == '17':
                self._handle_takeaway()
            elif choice == '18':
                self._handle_grocery_shop()
            elif choice == '19':
                self._handle_helpdesk()
            elif choice == '20':
                self._handle_internship_portal()
            elif choice == '21':
                self._handle_communication_hub()
            elif choice == '22':
                self._handle_todo()
            elif choice == '23':
                self._handle_change_password()
            elif choice == '24':
                self._handle_course_catalog()
            elif choice == '25':
                self._handle_transfer_credits()
            else:
                print("\n  Invalid choice. Please try again.")
                input("Press Enter to continue...")


def run_student_portal():
    """Create a StudentPortalCLI instance and run the main menu."""
    portal = StudentPortalCLI()
    portal._return_to_login = False
    portal.main_menu()
    if getattr(portal, '_return_to_login', False):
        # Re-run the universal CLI login and relaunch
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
