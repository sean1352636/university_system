"""
Staff Portal CLI — the CLI equivalent of the Staff Portal GUI.

When a staff member logs in via CLI, they see this focused menu instead of the
full display_menu(). The menu is organised by category, mirroring staff-facing
functionality across the university system.
"""

import logging

from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


class StaffPortalCLI:
    """Staff-facing CLI portal with category-organised menu."""

    def __init__(self):
        self.auth = get_auth()

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def view_dashboard(self):
        """Show summary stats: students, staff, modules, recent registrations."""
        username = ''
        if self.auth and self.auth.current_user:
            username = (
                self.auth.current_user.get('display_name')
                or self.auth.current_user.get('username', '')
            )

        print("\n" + "=" * 60)
        print(f"  STAFF DASHBOARD — {username}")
        print("=" * 60)

        conn = None
        try:
            conn = get_connection()

            # --- Summary Counts ---
            print("\n--- Summary ---")

            # Total students
            try:
                row = conn.execute(
                    "SELECT COUNT(*) AS total FROM students"
                ).fetchone()
                total_students = row['total'] if row else 0
                print(f"  Total Students:  {total_students}")
            except Exception as e:
                logger.debug(f"Could not fetch student count: {e}")
                print("  Total Students:  N/A")

            # Total staff
            try:
                row = conn.execute(
                    "SELECT COUNT(*) AS total FROM staff"
                ).fetchone()
                total_staff = row['total'] if row else 0
                print(f"  Total Staff:     {total_staff}")
            except Exception:
                try:
                    row = conn.execute(
                        "SELECT COUNT(*) AS total FROM staff_profiles"
                    ).fetchone()
                    total_staff = row['total'] if row else 0
                    print(f"  Total Staff:     {total_staff}")
                except Exception as e:
                    logger.debug(f"Could not fetch staff count: {e}")
                    print("  Total Staff:     N/A")

            # Total modules
            try:
                row = conn.execute(
                    "SELECT COUNT(*) AS total FROM modules"
                ).fetchone()
                total_modules = row['total'] if row else 0
                print(f"  Total Modules:   {total_modules}")
            except Exception as e:
                logger.debug(f"Could not fetch module count: {e}")
                print("  Total Modules:   N/A")

            # --- Recent Registrations ---
            print("\n--- Recent Registrations ---")
            try:
                rows = conn.execute(
                    "SELECT student_id, first_name, last_name, registration_date "
                    "FROM students ORDER BY registration_date DESC LIMIT 5"
                ).fetchall()
                if rows:
                    for r in rows:
                        print(
                            f"  {r['student_id']}  {r['first_name']} {r['last_name']}"
                            f"  (registered: {r['registration_date']})"
                        )
                else:
                    print("  No recent registrations.")
            except Exception as e:
                logger.debug(f"Could not fetch recent registrations: {e}")
                print("  Registration data not available.")

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

    # --- Student Management ---

    def _handle_student_records(self):
        try:
            from education_system.university_system.modules.shared.cli.student_operations import display_student_records_menu
            display_student_records_menu()
        except ImportError as e:
            print(f"\n  Student Records module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_create_student(self):
        try:
            from education_system.university_system.modules.shared.cli.student_operations import create_student_record
            create_student_record()
        except ImportError as e:
            print(f"\n  Create Student module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_search_students(self):
        try:
            from education_system.university_system.modules.shared.cli.student_search import search_student_by_first_name
            search_student_by_first_name()
        except ImportError as e:
            print(f"\n  Student Search module is not available: {e}")
            input("Press Enter to continue...")

    # --- Academic ---

    def _handle_course_management(self):
        try:
            from education_system.university_system.modules.domain.academics.services.course_management.menu import display_course_management_menu
            display_course_management_menu(self.auth)
        except ImportError as e:
            print(f"\n  Course Management module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_module_management(self):
        try:
            from education_system.university_system.modules.shared.cli.module_operations import display_module_management_menu
            display_module_management_menu()
        except ImportError as e:
            print(f"\n  Module Management module is not available: {e}")
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

    def _handle_attendance(self):
        try:
            from education_system.university_system.modules.domain.academics.services.attendance import display_advanced_attendance_menu
            display_advanced_attendance_menu()
        except ImportError as e:
            print(f"\n  Attendance module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_academic_progress(self):
        try:
            from education_system.university_system.modules.domain.academic_progress.cli.progress_cli import AcademicProgressCLI
            cli = AcademicProgressCLI()
            cli.run()
        except ImportError as e:
            print(f"\n  Academic Progress module is not available: {e}")
            input("Press Enter to continue...")

    # --- Schedule ---

    def _handle_academic_calendar(self):
        try:
            from education_system.university_system.modules.domain.academics.services.academic_calendar.cli import display_academic_calendar_menu
            display_academic_calendar_menu()
        except ImportError as e:
            print(f"\n  Academic Calendar module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_scheduling(self):
        try:
            from education_system.university_system.modules.domain.academics.services.module_scheduling.menus import display_module_scheduling_menu
            display_module_scheduling_menu()
        except ImportError as e:
            print(f"\n  Scheduling module is not available: {e}")
            input("Press Enter to continue...")

    # --- HR & Staff ---

    def _handle_staff_hr(self):
        try:
            from education_system.university_system.modules.shared.cli.imports import STAFF_HR_CLI_AVAILABLE, display_staff_hr_menu
            if STAFF_HR_CLI_AVAILABLE and display_staff_hr_menu:
                display_staff_hr_menu()
            else:
                print("\n  Staff HR module is not available.")
                input("Press Enter to continue...")
        except ImportError as e:
            print(f"\n  Staff HR module is not available: {e}")
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
            from education_system.university_system.modules.domain.academics.cli.ta_management_cli import display_ta_management_menu
            display_ta_management_menu(self.auth)
        except ImportError as e:
            print(f"\n  TA Management module is not available: {e}")
            input("Press Enter to continue...")

    # --- Finance ---

    def _handle_finance_management(self):
        try:
            from education_system.university_system.modules.domain.finance.gui.finance_reporting.misc import display_finance_menu
            display_finance_menu(self.auth)
        except ImportError as e:
            print(f"\n  Finance Management module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_financial_aid(self):
        try:
            from education_system.university_system.modules.shared.cli.menu_router import display_financial_aid_menu
            display_financial_aid_menu(self.auth)
        except ImportError as e:
            print(f"\n  Financial Aid module is not available: {e}")
            input("Press Enter to continue...")

    # --- Communication ---

    def _handle_communication_hub(self):
        try:
            from education_system.university_system.modules.shared.cli.menu_router import display_communication_hub_menu
            display_communication_hub_menu(self.auth)
        except ImportError as e:
            print(f"\n  Communication Hub module is not available: {e}")
            input("Press Enter to continue...")

    # --- Analytics ---

    def _handle_analytics(self):
        try:
            from education_system.university_system.modules.shared.cli.admin_tools import display_analytics_menu
            display_analytics_menu()
        except ImportError as e:
            print(f"\n  Analytics module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_early_warning(self):
        try:
            from education_system.university_system.modules.domain.student_affairs.services.early_warning.early_warning_core import display_early_warning_menu
            display_early_warning_menu(self.auth)
        except ImportError as e:
            print(f"\n  Early Warning System module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_export_data(self):
        try:
            from education_system.university_system.modules.shared.cli.export_manager import display_export_menu
            display_export_menu()
        except ImportError as e:
            print(f"\n  Export Data module is not available: {e}")
            input("Press Enter to continue...")

    # --- Services ---

    def _handle_university_shop(self):
        try:
            from education_system.university_system.modules.domain.commerce.services.shop_management.menus import display_shop_menu
            display_shop_menu()
        except ImportError as e:
            print(f"\n  University Shop module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_library(self):
        try:
            from education_system.university_system.modules.domain.academics.services.library.menu import display_library_menu
            display_library_menu()
        except ImportError as e:
            print(f"\n  Library module is not available: {e}")
            input("Press Enter to continue...")

    # --- Institutional ---

    def _handle_admissions_crm(self):
        try:
            from education_system.university_system.modules.domain.admissions.services.admissions_crm_core import display_admissions_crm_menu
            display_admissions_crm_menu(self.auth)
        except ImportError as e:
            print(f"\n  Admissions CRM module is not available: {e}")
            input("Press Enter to continue...")

    def _handle_alumni_management(self):
        try:
            from education_system.university_system.modules.domain.student_affairs.services.alumni_management import display_alumni_menu
            display_alumni_menu()
        except ImportError as e:
            print(f"\n  Alumni Management module is not available: {e}")
            input("Press Enter to continue...")

    # ------------------------------------------------------------------
    # Main menu loop
    # ------------------------------------------------------------------

    def main_menu(self):
        """Display the staff portal menu and handle choices."""
        username = ''
        if self.auth and self.auth.current_user:
            username = (
                self.auth.current_user.get('display_name')
                or self.auth.current_user.get('username', '')
            )

        while True:
            print("\n" + "=" * 50)
            print("  STAFF PORTAL")
            print("=" * 50)
            print(f"  Welcome, {username}!")

            print("\n  DASHBOARD:")
            print("    1.  View Dashboard")

            print("\n  STUDENT MANAGEMENT:")
            print("    2.  Student Records Menu")
            print("    3.  Create Student")
            print("    4.  Search Students")

            print("\n  ACADEMIC:")
            print("    5.  Course Management")
            print("    6.  Module Management")
            print("    7.  Grade Tracking")
            print("    8.  Attendance")
            print("    9.  Academic Progress")

            print("\n  SCHEDULE:")
            print("    10. Academic Calendar")
            print("    11. Scheduling")

            print("\n  HR & STAFF:")
            print("    12. Staff HR")
            print("    13. Office Hours")
            print("    14. TA Management")

            print("\n  FINANCE:")
            print("    15. Finance Management")
            print("    16. Financial Aid")

            print("\n  COMMUNICATION:")
            print("    17. Communication Hub")

            print("\n  ANALYTICS:")
            print("    18. Analytics & Reports")
            print("    19. Early Warning System")
            print("    20. Export Data")

            print("\n  SERVICES:")
            print("    21. University Shop")
            print("    22. Library")

            print("\n  INSTITUTIONAL:")
            print("    23. Admissions CRM")
            print("    24. Alumni Management")

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
                self._handle_student_records()
            elif choice == '3':
                self._handle_create_student()
            elif choice == '4':
                self._handle_search_students()
            elif choice == '5':
                self._handle_course_management()
            elif choice == '6':
                self._handle_module_management()
            elif choice == '7':
                self._handle_grade_tracking()
            elif choice == '8':
                self._handle_attendance()
            elif choice == '9':
                self._handle_academic_progress()
            elif choice == '10':
                self._handle_academic_calendar()
            elif choice == '11':
                self._handle_scheduling()
            elif choice == '12':
                self._handle_staff_hr()
            elif choice == '13':
                self._handle_office_hours()
            elif choice == '14':
                self._handle_ta_management()
            elif choice == '15':
                self._handle_finance_management()
            elif choice == '16':
                self._handle_financial_aid()
            elif choice == '17':
                self._handle_communication_hub()
            elif choice == '18':
                self._handle_analytics()
            elif choice == '19':
                self._handle_early_warning()
            elif choice == '20':
                self._handle_export_data()
            elif choice == '21':
                self._handle_university_shop()
            elif choice == '22':
                self._handle_library()
            elif choice == '23':
                self._handle_admissions_crm()
            elif choice == '24':
                self._handle_alumni_management()
            else:
                print("\n  Invalid choice. Please try again.")
                input("Press Enter to continue...")


def run_staff_portal():
    """Create a StaffPortalCLI instance and run the main menu."""
    portal = StaffPortalCLI()
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
