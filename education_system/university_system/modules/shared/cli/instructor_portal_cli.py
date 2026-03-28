"""
Instructor Portal CLI — the CLI equivalent of an Instructor Portal GUI.

When an instructor logs in via CLI, they see this focused menu instead of the
full display_menu(). The menu is organised by category, mirroring a teaching-
oriented sidebar layout.
"""

import logging

from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


class InstructorPortalCLI:
    """Instructor-facing CLI portal with category-organised menu."""

    def __init__(self):
        self.auth = get_auth()
        self.instructor_id = None
        if self.auth and self.auth.current_user:
            self.instructor_id = (
                self.auth.current_user.get('username')
                or self.auth.current_user.get('id')
                or self.auth.current_user.get('user_id')
            )

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def view_dashboard(self):
        """Show modules taught, upcoming assignments, grade stats, and office hours."""
        username = ''
        if self.auth and self.auth.current_user:
            username = (
                self.auth.current_user.get('display_name')
                or self.auth.current_user.get('username', '')
            )

        print("\n" + "=" * 60)
        print(f"  INSTRUCTOR DASHBOARD — {username}")
        print("=" * 60)

        conn = None
        try:
            conn = get_connection()

            # --- Modules Taught ---
            print("\n--- Modules Taught ---")
            try:
                modules = conn.execute(
                    "SELECT module_code, module_name FROM modules "
                    "WHERE instructor_id = ? OR taught_by = ?",
                    (self.instructor_id, self.instructor_id),
                ).fetchall()
                if modules:
                    for i, mod in enumerate(modules, 1):
                        print(f"  {i}. {mod['module_code']} — {mod['module_name']}")
                else:
                    print("  No modules assigned.")
            except Exception as e:
                logger.debug(f"Could not fetch modules: {e}")
                print("  Module data not available.")

            # --- Upcoming Assignments ---
            print("\n--- Upcoming Assignments (created by you) ---")
            try:
                assignments = conn.execute(
                    "SELECT title, module_code, due_date FROM assignments "
                    "WHERE created_by = ? AND due_date > date('now') "
                    "ORDER BY due_date ASC LIMIT 10",
                    (self.instructor_id,),
                ).fetchall()
                if assignments:
                    for a in assignments:
                        print(f"  - {a['title']}  [{a['module_code']}]  (due: {a['due_date']})")
                else:
                    print("  No upcoming assignments.")
            except Exception as e:
                logger.debug(f"Could not fetch assignments: {e}")
                print("  Assignment data not available.")

            # --- Recent Grade Submissions ---
            print("\n--- Recent Grade Submissions ---")
            try:
                row = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM module_grades "
                    "WHERE graded_by = ?",
                    (self.instructor_id,),
                ).fetchone()
                count = row['cnt'] if row else 0
                print(f"  Total grades submitted: {count}")
            except Exception as e:
                logger.debug(f"Could not fetch grade count: {e}")
                print("  Grade submission data not available.")

            # --- Office Hours ---
            print("\n--- Office Hours ---")
            try:
                hours = conn.execute(
                    "SELECT day_of_week, start_time, end_time, location "
                    "FROM office_hours WHERE instructor_id = ?",
                    (self.instructor_id,),
                ).fetchall()
                if hours:
                    for h in hours:
                        print(
                            f"  {h['day_of_week']}: {h['start_time']} – "
                            f"{h['end_time']}  ({h['location']})"
                        )
                else:
                    print("  No office hours scheduled.")
            except Exception as e:
                logger.debug(f"Could not fetch office hours: {e}")
                print("  Office hours data not available.")

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

    def _handle_course_management(self):
        try:
            from education_system.university_system.modules.domain.course_planning.cli.course_planning_cli import display_course_planning_menu
            display_course_planning_menu()
        except ImportError as e:
            print(f"\n  Course Management module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_module_management(self):
        try:
            from education_system.university_system.modules.shared.cli.menu_router import display_module_management_menu
            display_module_management_menu(self.auth)
        except ImportError as e:
            print(f"\n  Module Management module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_assignments(self):
        try:
            from education_system.university_system.modules.shared.cli.menu_router import display_assignments_menu
            display_assignments_menu(self.auth)
        except ImportError as e:
            print(f"\n  Assignments module is not available: {e}")
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

    def _handle_virtual_classroom(self):
        try:
            from education_system.university_system.modules.shared.cli.menu_router import display_virtual_classroom_menu
            display_virtual_classroom_menu(self.auth)
        except ImportError as e:
            print(f"\n  Virtual Classroom module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_office_hours(self):
        try:
            from education_system.university_system.modules.domain.academics.cli.office_hours_cli import display_office_hours_menu
            display_office_hours_menu(self.auth)
        except ImportError as e:
            print(f"\n  Office Hours module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_ta_management(self):
        try:
            from education_system.university_system.modules.shared.cli.menu_router import display_ta_management_menu
            display_ta_management_menu(self.auth)
        except ImportError as e:
            print(f"\n  TA Management module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_student_records(self):
        try:
            from education_system.university_system.modules.shared.cli.student_operations import display_student_records_menu
            display_student_records_menu()
        except ImportError as e:
            print(f"\n  Student Records module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_student_analytics(self):
        try:
            from education_system.university_system.modules.shared.cli.menu_router import display_student_analytics_menu
            display_student_analytics_menu(self.auth)
        except ImportError as e:
            print(f"\n  Student Analytics module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_learning_outcomes(self):
        try:
            from education_system.university_system.modules.shared.cli.menu_router import display_learning_outcomes_menu
            display_learning_outcomes_menu(self.auth)
        except ImportError as e:
            print(f"\n  Learning Outcomes module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_early_warning(self):
        try:
            from education_system.university_system.modules.shared.cli.menu_router import display_early_warning_menu
            display_early_warning_menu(self.auth)
        except ImportError as e:
            print(f"\n  Early Warning System module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_academic_progress(self):
        try:
            from education_system.university_system.modules.domain.academic_progress.cli.progress_cli import AcademicProgressCLI
            cli = AcademicProgressCLI()
            cli.run()
        except ImportError as e:
            print(f"\n  Academic Progress module is not available: {e}")
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

    def _handle_attendance(self):
        try:
            from education_system.university_system.modules.shared.cli.menu_router import display_attendance_menu
            display_attendance_menu(self.auth)
        except ImportError as e:
            print(f"\n  Attendance module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_exam_scheduler(self):
        try:
            from education_system.university_system.modules.shared.cli.menu_router import display_exam_scheduler_menu
            display_exam_scheduler_menu(self.auth)
        except ImportError as e:
            print(f"\n  Exam Scheduler module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_analytics_reports(self):
        try:
            from education_system.university_system.modules.shared.cli.menu_router import display_analytics_reports_menu
            display_analytics_reports_menu(self.auth)
        except ImportError as e:
            print(f"\n  Analytics & Reports module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_export_data(self):
        try:
            from education_system.university_system.modules.shared.cli.menu_router import display_export_data_menu
            display_export_data_menu(self.auth)
        except ImportError as e:
            print(f"\n  Export Data module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_communication_hub(self):
        try:
            from education_system.university_system.modules.shared.cli.menu_router import display_communication_hub_menu
            display_communication_hub_menu(self.auth)
        except ImportError as e:
            print(f"\n  Communication Hub module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_library(self):
        try:
            from education_system.university_system.modules.domain.academics.services.library.menu import display_library_menu
            display_library_menu()
        except ImportError as e:
            print(f"\n  Library module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_university_shop(self):
        try:
            from education_system.university_system.modules.domain.commerce.services.shop_management.menus import display_shop_menu
            display_shop_menu()
        except ImportError as e:
            print(f"\n  University Shop module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_change_password(self):
        """Prompt the instructor to change their password."""
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

    # ------------------------------------------------------------------
    # Main menu loop
    # ------------------------------------------------------------------

    def main_menu(self):
        """Display the instructor portal menu and handle choices."""
        username = ''
        if self.auth and self.auth.current_user:
            username = (
                self.auth.current_user.get('display_name')
                or self.auth.current_user.get('username', '')
            )

        while True:
            print("\n" + "=" * 50)
            print("  INSTRUCTOR PORTAL")
            print("=" * 50)
            print(f"  Welcome, {username}!")

            print("\n  DASHBOARD:")
            print("    1.  View Dashboard")

            print("\n  TEACHING:")
            print("    2.  Course Management")
            print("    3.  Module Management")
            print("    4.  Assignments")
            print("    5.  Grade Tracking")
            print("    6.  Virtual Classroom")
            print("    7.  Office Hours")
            print("    8.  TA Management")

            print("\n  STUDENTS:")
            print("    9.  Student Records")
            print("    10. Student Analytics")
            print("    11. Learning Outcomes")
            print("    12. Early Warning System")
            print("    13. Academic Progress")

            print("\n  SCHEDULE:")
            print("    14. Academic Calendar")
            print("    15. Timetable")
            print("    16. Attendance")
            print("    17. Exam Scheduler")

            print("\n  ANALYTICS:")
            print("    18. Analytics & Reports")
            print("    19. Export Data")

            print("\n  COMMUNICATION:")
            print("    20. Communication Hub")

            print("\n  RESOURCES:")
            print("    21. Library")
            print("    22. University Shop")

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
                self._handle_course_management()
            elif choice == '3':
                self._handle_module_management()
            elif choice == '4':
                self._handle_assignments()
            elif choice == '5':
                self._handle_grade_tracking()
            elif choice == '6':
                self._handle_virtual_classroom()
            elif choice == '7':
                self._handle_office_hours()
            elif choice == '8':
                self._handle_ta_management()
            elif choice == '9':
                self._handle_student_records()
            elif choice == '10':
                self._handle_student_analytics()
            elif choice == '11':
                self._handle_learning_outcomes()
            elif choice == '12':
                self._handle_early_warning()
            elif choice == '13':
                self._handle_academic_progress()
            elif choice == '14':
                self._handle_academic_calendar()
            elif choice == '15':
                self._handle_timetable()
            elif choice == '16':
                self._handle_attendance()
            elif choice == '17':
                self._handle_exam_scheduler()
            elif choice == '18':
                self._handle_analytics_reports()
            elif choice == '19':
                self._handle_export_data()
            elif choice == '20':
                self._handle_communication_hub()
            elif choice == '21':
                self._handle_library()
            elif choice == '22':
                self._handle_university_shop()
            elif choice == '23':
                self._handle_change_password()
            else:
                print("\n  Invalid choice. Please try again.")
                input("Press Enter to continue...")


def run_instructor_portal():
    """Create an InstructorPortalCLI instance and run the main menu."""
    portal = InstructorPortalCLI()
    portal._return_to_login = False
    portal.main_menu()
    if getattr(portal, '_return_to_login', False):
        try:
            from education_system.shared.cli.login_cli import universal_cli_login
            result = universal_cli_login()
            if result:
                user_info, sys_key, role, shared_auth = result
                if sys_key == 'university':
                    from run import run_university_cli
                    run_university_cli(user_info=user_info, role=role, shared_auth=shared_auth)
        except Exception as e:
            print(f"Error returning to login: {e}")
