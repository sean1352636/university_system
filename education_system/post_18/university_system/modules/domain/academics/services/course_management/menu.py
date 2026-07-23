from education_system.post_18.university_system.modules.shared.utils.simple_activity_logger import log_menu_navigation
from education_system.post_18.university_system.core.i18n import get_text
from education_system.post_18.university_system.modules.shared.utils.language_selector import display_language_menu_option
from education_system.post_18.university_system.modules.domain.academics.services.course_management.database import initialize_enhanced_database
from education_system.post_18.university_system.modules.domain.academics.services.course_management.courses import create_enhanced_course, view_all_courses, update_course, delete_course
from education_system.post_18.university_system.modules.domain.academics.services.course_management.prerequisites import add_prerequisite, view_prerequisites, remove_prerequisite
from education_system.post_18.university_system.modules.domain.academics.services.course_management.instructors import create_instructor, view_instructors, assign_instructor_to_course
from education_system.post_18.university_system.modules.domain.academics.services.course_management.scheduling import create_course_schedule, view_course_schedules, update_schedule
from education_system.post_18.university_system.modules.domain.academics.services.course_management.search import search_courses
from education_system.post_18.university_system.modules.domain.academics.services.course_management.import_export import import_courses_from_csv, export_courses_to_csv, bulk_update_courses
from education_system.post_18.university_system.modules.domain.academics.services.course_management.analytics import generate_course_analytics, generate_enrollment_report, department_statistics
from education_system.post_18.university_system.modules.domain.academics.services.course_management.waitlist import add_to_waitlist, view_waitlists, process_waitlist
from education_system.post_18.university_system.modules.domain.academics.services.course_management.recommendations import recommend_courses, find_alternative_courses
from education_system.post_18.university_system.modules.domain.academics.services.course_management.status import manage_course_status
from education_system.post_18.university_system.modules.domain.academics.services.course_management.history import view_course_history
from education_system.post_18.university_system.modules.domain.academics.services.course_management.maintenance import system_maintenance
from education_system.post_18.university_system.modules.domain.academics.services.course_management.curriculum_extensions import display_curriculum_extensions_menu


def _launch_course_planning_cli():
    """Launch the Course Planning Assistant CLI."""
    try:
        from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.cli.course_planning_cli import display_course_planning_menu
        display_course_planning_menu()
    except ImportError as e:
        print(f"\n❌ Course Planning CLI not available: {e}")
        input("Press Enter to continue...")


def _launch_lms_cli(auth):
    """Launch the LMS CLI."""
    try:
        from education_system.post_18.university_system.modules.domain.academics.services.lms.lms_core import display_lms_menu
        display_lms_menu(auth)
    except ImportError as e:
        print(f"\n❌ LMS CLI not available: {e}")
        input("Press Enter to continue...")


def _launch_course_evaluation_cli(auth):
    """Launch the Course Evaluation CLI."""
    try:
        from education_system.post_18.university_system.modules.domain.academics.services.evaluation.course_evaluation_core import display_course_evaluation_menu
        display_course_evaluation_menu(auth)
    except ImportError as e:
        print(f"\n❌ Course Evaluation CLI not available: {e}")
        input("Press Enter to continue...")


def _launch_degree_audit_cli(auth):
    """Launch the Degree Audit CLI."""
    try:
        from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.cli.degree_audit_cli import launch_degree_audit_cli
        launch_degree_audit_cli(auth)
    except ImportError as e:
        print(f"\n❌ Degree Audit CLI not available: {e}")
        input("Press Enter to continue...")


def _launch_graduation_ceremony_cli(auth):
    """Launch the Graduation Ceremony CLI."""
    try:
        from education_system.post_18.university_system.modules.domain.academics.cli.graduation_ceremony_cli import launch_graduation_ceremony_cli
        launch_graduation_ceremony_cli(auth)
    except ImportError as e:
        print(f"\n❌ Graduation Ceremony CLI not available: {e}")
        input("Press Enter to continue...")


def _switch_to_gui(auth):
    """Switch from CLI to Course Management GUI."""
    try:
        import tkinter as tk
        from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui import CourseManagementGUI
        print("\nLaunching Course Management GUI...")
        root = tk.Tk()
        root.title("Course Management System")
        root.geometry("1200x800")
        app = CourseManagementGUI(root, auth_system=auth)
        root.mainloop()
    except ImportError as e:
        print(f"\nCourse Management GUI not available: {e}")
        input("Press Enter to continue...")
    except Exception as e:
        print(f"\nError launching GUI: {e}")
        input("Press Enter to continue...")


@log_menu_navigation(description="Displaying enhanced course management menu")
def display_enhanced_course_menu(auth):
    """Display the enhanced course management menu"""
    if not auth or not auth.current_user:
        print(get_text('course_mgmt.login_required', default='You must be logged in to access course management.'))
        return

    # Initialize enhanced database schema
    initialize_enhanced_database()

    while True:
        print("\n" + "="*100)
        print(get_text('course_mgmt.title', default='ENHANCED COURSE MANAGEMENT SYSTEM').center(100))
        print("="*100)

        if auth.check_permission('manage_courses'):
            print(f"\n📚 {get_text('course_mgmt.sections.course_management', default='COURSE MANAGEMENT')}:")
            print(f"{'1.  ' + get_text('course_mgmt.menu.create_course', default='Create new course'):<25} {'2.  ' + get_text('course_mgmt.menu.view_courses', default='View all courses'):<25} {'3.  ' + get_text('course_mgmt.menu.update_course', default='Update course'):<25} {'4.  ' + get_text('course_mgmt.menu.delete_course', default='Delete course'):<25}")
            print(f"{'5.  ' + get_text('course_mgmt.menu.manage_status', default='Manage course status'):<25} {'6.  ' + get_text('course_mgmt.menu.search_courses', default='Search courses'):<25}")

            print(f"\n🔗 {get_text('course_mgmt.sections.prerequisites', default='PREREQUISITES & RELATIONSHIPS')}:")
            print(f"{'7.  ' + get_text('course_mgmt.menu.add_prerequisite', default='Add prerequisite'):<25} {'8.  ' + get_text('course_mgmt.menu.view_prerequisites', default='View prerequisites'):<25} {'9.  ' + get_text('course_mgmt.menu.remove_prerequisite', default='Remove prerequisite'):<25}")

            print(f"\n👨‍🏫 {get_text('course_mgmt.sections.instructor_management', default='INSTRUCTOR MANAGEMENT')}:")
            print(f"{'10. ' + get_text('course_mgmt.menu.create_instructor', default='Create instructor'):<25} {'11. ' + get_text('course_mgmt.menu.view_instructors', default='View instructors'):<25} {'12. ' + get_text('course_mgmt.menu.assign_to_course', default='Assign to course'):<25}")

            print(f"\n📅 {get_text('course_mgmt.sections.scheduling', default='SCHEDULING')}:")
            print(f"{'13. ' + get_text('course_mgmt.menu.create_schedule', default='Create schedule'):<25} {'14. ' + get_text('course_mgmt.menu.view_schedules', default='View schedules'):<25} {'15. ' + get_text('course_mgmt.menu.update_schedule', default='Update schedule'):<25}")

            print(f"\n📊 {get_text('course_mgmt.sections.enrollment_waitlists', default='ENROLLMENT & WAITLISTS')}:")
            print(f"{'16. ' + get_text('course_mgmt.menu.add_to_waitlist', default='Add to waitlist'):<25} {'17. ' + get_text('course_mgmt.menu.view_waitlists', default='View waitlists'):<25} {'18. ' + get_text('course_mgmt.menu.process_waitlist', default='Process waitlist'):<25}")

            print(f"\n📈 {get_text('course_mgmt.sections.analytics_reporting', default='ANALYTICS & REPORTING')}:")
            print(f"{'19. ' + get_text('course_mgmt.menu.analytics_dashboard', default='Analytics dashboard'):<25} {'20. ' + get_text('course_mgmt.menu.enrollment_report', default='Enrollment report'):<25} {'21. ' + get_text('course_mgmt.menu.dept_statistics', default='Dept statistics'):<25}")

            print(f"\n💾 {get_text('course_mgmt.sections.bulk_operations', default='BULK OPERATIONS')}:")
            print(f"{'22. ' + get_text('course_mgmt.menu.import_csv', default='Import from CSV'):<25} {'23. ' + get_text('course_mgmt.menu.export_csv', default='Export to CSV'):<25} {'24. ' + get_text('course_mgmt.menu.bulk_update', default='Bulk update'):<25}")

            print(f"\n🎯 {get_text('course_mgmt.sections.recommendations', default='RECOMMENDATIONS')}:")
            print(f"{'25. ' + get_text('course_mgmt.menu.recommendations', default='Recommendations'):<25} {'26. ' + get_text('course_mgmt.menu.alternative_courses', default='Alternative courses'):<25}")

            print(f"\n🔧 {get_text('course_mgmt.sections.utilities', default='UTILITIES')}:")
            print(f"{'27. ' + get_text('course_mgmt.menu.course_history', default='Course history'):<25} {'28. ' + get_text('course_mgmt.menu.system_maintenance', default='System maintenance'):<25} {'29. ' + get_text('course_mgmt.menu.module_management', default='Module Management'):<25}")

            print("\n📋 INTEGRATED TOOLS:")
            print(f"{'30. Course Planning Assistant':<25} {'31. Learning Management (LMS)':<30} {'32. Course Evaluation':<25} {'33. Degree Audit':<25}")
            print(f"{'37. Graduation Ceremony':<25}")

            print(f"\n🧩 {get_text('course_mgmt.sections.curriculum_extensions', default='CURRICULUM EXTENSIONS')}:")
            print(f"{'36. ' + get_text('course_mgmt.menu.curriculum_extensions', default='Curriculum extensions (terms, sections, outcomes, …)'):<25}")

            print(f"\n⚙️  {get_text('course_mgmt.sections.settings', default='SETTINGS')}:")
            print(f"{'34. ' + get_text('course_mgmt.menu.language', default='Change Language'):<25} {'35. Switch to GUI':<25}")

            print(f"\n0.  {get_text('course_mgmt.menu.return_main', default='Return to Main Menu')}")

            max_option = 37

        elif auth.check_permission('view_courses'):
            print(f"\n📚 {get_text('course_mgmt.sections.course_viewing', default='COURSE VIEWING')}:")
            print(f"1. {get_text('course_mgmt.menu.view_courses', default='View all courses')}")
            print(f"2. {get_text('course_mgmt.menu.search_courses', default='Search courses')}")
            print(f"3. {get_text('course_mgmt.menu.view_prerequisites', default='View prerequisites')}")
            print(f"4. {get_text('course_mgmt.menu.recommendations', default='Course recommendations')}")
            print(f"5. {get_text('course_mgmt.menu.course_analytics', default='Course analytics')}")
            print("6. Course Planning Assistant")
            print("7. Learning Management (LMS)")
            print("8. Course Evaluation")
            print("9. Degree Audit")
            print(f"10. {get_text('course_mgmt.menu.language', default='Change Language')}")
            print("11. Switch to GUI")
            print(f"12. {get_text('course_mgmt.menu.curriculum_extensions', default='Curriculum extensions')}")
            print(f"0. {get_text('course_mgmt.menu.return_main', default='Return to Main Menu')}")

            max_option = 12
        else:
            print(get_text('course_mgmt.no_permission', default="You don't have permission to manage courses."))
            return

        choice = input(f"\n{get_text('course_mgmt.enter_choice', default='Enter your choice')} (0-{max_option}): ").strip()

        if choice == '0':
            return

        # Handle menu choices
        if auth.check_permission('manage_courses'):
            if choice == '1':
                create_enhanced_course(auth)
            elif choice == '2':
                view_all_courses(auth)
            elif choice == '3':
                update_course(auth)
            elif choice == '4':
                delete_course(auth)
            elif choice == '5':
                manage_course_status(auth)
            elif choice == '6':
                search_courses(auth)
            elif choice == '7':
                add_prerequisite(auth)
            elif choice == '8':
                view_prerequisites(auth)
            elif choice == '9':
                remove_prerequisite(auth)
            elif choice == '10':
                create_instructor(auth)
            elif choice == '11':
                view_instructors(auth)
            elif choice == '12':
                assign_instructor_to_course(auth)
            elif choice == '13':
                create_course_schedule(auth)
            elif choice == '14':
                view_course_schedules(auth)
            elif choice == '15':
                update_schedule(auth)
            elif choice == '16':
                add_to_waitlist(auth)
            elif choice == '17':
                view_waitlists(auth)
            elif choice == '18':
                process_waitlist(auth)
            elif choice == '19':
                generate_course_analytics(auth)
            elif choice == '20':
                generate_enrollment_report(auth)
            elif choice == '21':
                department_statistics(auth)
            elif choice == '22':
                import_courses_from_csv(auth)
            elif choice == '23':
                export_courses_to_csv(auth)
            elif choice == '24':
                bulk_update_courses(auth)
            elif choice == '25':
                recommend_courses(auth)
            elif choice == '26':
                find_alternative_courses(auth)
            elif choice == '27':
                view_course_history(auth)
            elif choice == '28':
                system_maintenance(auth)
            elif choice == '29':
                # Import module management menu
                from education_system.post_18.university_system.modules.shared.cli.module_operations import display_module_management_menu
                display_module_management_menu()
            elif choice == '30':
                _launch_course_planning_cli()
            elif choice == '31':
                _launch_lms_cli(auth)
            elif choice == '32':
                _launch_course_evaluation_cli(auth)
            elif choice == '33':
                _launch_degree_audit_cli(auth)
            elif choice == '34':
                display_language_menu_option()
            elif choice == '35':
                _switch_to_gui(auth)
                return  # Exit CLI menu after launching GUI
            elif choice == '36':
                display_curriculum_extensions_menu(auth)
            elif choice == '37':
                _launch_graduation_ceremony_cli(auth)
            else:
                print(get_text('course_mgmt.invalid_choice', default='Invalid choice. Please enter a number between 0 and {max_option}.').format(max_option=max_option))

        else:  # View-only permissions
            if choice == '1':
                view_all_courses(auth)
            elif choice == '2':
                search_courses(auth)
            elif choice == '3':
                view_prerequisites(auth)
            elif choice == '4':
                recommend_courses(auth)
            elif choice == '5':
                generate_course_analytics(auth)
            elif choice == '6':
                _launch_course_planning_cli()
            elif choice == '7':
                _launch_lms_cli(auth)
            elif choice == '8':
                _launch_course_evaluation_cli(auth)
            elif choice == '9':
                _launch_degree_audit_cli(auth)
            elif choice == '10':
                display_language_menu_option()
            elif choice == '11':
                _switch_to_gui(auth)
                return  # Exit CLI menu after launching GUI
            elif choice == '12':
                display_curriculum_extensions_menu(auth)
            else:
                print(get_text('course_mgmt.invalid_choice', default='Invalid choice. Please enter a number between 0 and {max_option}.').format(max_option=max_option))

        # Pause before showing menu again
        input(f"\n{get_text('course_mgmt.press_enter', default='Press Enter to continue...')}")


@log_menu_navigation(description="Displaying course management menu")
def display_course_management_menu(auth):
    """Legacy function - redirects to enhanced menu"""
    return display_enhanced_course_menu(auth)
