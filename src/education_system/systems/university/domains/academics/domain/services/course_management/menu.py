from education_system.systems.university.infrastructure.utils.activity_logger import log_menu_navigation
from education_system.systems.university.infrastructure.i18n import get_text
from education_system.systems.university.infrastructure.utils.language_selector import display_language_menu_option
from education_system.systems.university.domains.academics.domain.services.course_management.database import initialize_enhanced_database
from education_system.systems.university.domains.academics.domain.services.course_management.courses import create_enhanced_course, view_all_courses, update_course, delete_course
from education_system.systems.university.domains.academics.domain.services.course_management.prerequisites import add_prerequisite, view_prerequisites, remove_prerequisite
from education_system.systems.university.domains.academics.domain.services.course_management.instructors import create_instructor, view_instructors, assign_instructor_to_course
from education_system.systems.university.domains.academics.domain.services.course_management.scheduling import create_course_schedule, view_course_schedules, update_schedule
from education_system.systems.university.domains.academics.domain.services.course_management.search import search_courses
from education_system.systems.university.domains.academics.domain.services.course_management.import_export import import_courses_from_csv, export_courses_to_csv, bulk_update_courses
from education_system.systems.university.domains.academics.domain.services.course_management.analytics import generate_course_analytics, generate_enrollment_report, department_statistics
from education_system.systems.university.domains.academics.domain.services.course_management.waitlist import add_to_waitlist, view_waitlists, process_waitlist
from education_system.systems.university.domains.academics.domain.services.course_management.recommendations import recommend_courses, find_alternative_courses
from education_system.systems.university.domains.academics.domain.services.course_management.status import manage_course_status
from education_system.systems.university.domains.academics.domain.services.course_management.history import view_course_history
from education_system.systems.university.domains.academics.domain.services.course_management.maintenance import system_maintenance
from education_system.systems.university.domains.academics.domain.services.course_management.curriculum_extensions import display_curriculum_extensions_menu


def _launch_course_planning_cli():
    """Launch the Course Planning Assistant CLI."""
    try:
        from education_system.systems.university.domains.academics.interfaces.gui.course_management_gui.cli.course_planning_cli import display_course_planning_menu
        display_course_planning_menu()
    except ImportError as e:
        print(f"\n❌ Course Planning CLI not available: {e}")
        input("Press Enter to continue...")


def _launch_course_evaluation_cli(auth):
    """Launch the Course Evaluation CLI."""
    try:
        from education_system.systems.university.domains.academics.domain.services.evaluation.course_evaluation_core import display_course_evaluation_menu
        display_course_evaluation_menu(auth)
    except ImportError as e:
        print(f"\n❌ Course Evaluation CLI not available: {e}")
        input("Press Enter to continue...")


def _launch_degree_audit_cli(auth):
    """Launch the Degree Audit CLI."""
    try:
        from education_system.systems.university.domains.academics.interfaces.gui.course_management_gui.cli.degree_audit_cli import launch_degree_audit_cli
        launch_degree_audit_cli(auth)
    except ImportError as e:
        print(f"\n❌ Degree Audit CLI not available: {e}")
        input("Press Enter to continue...")


def _launch_graduation_ceremony_cli(auth):
    """Launch the Graduation Ceremony CLI."""
    try:
        from education_system.systems.university.domains.academics.interfaces.cli.graduation_ceremony_cli import launch_graduation_ceremony_cli
        launch_graduation_ceremony_cli(auth)
    except ImportError as e:
        print(f"\n❌ Graduation Ceremony CLI not available: {e}")
        input("Press Enter to continue...")




@log_menu_navigation(description="Displaying enhanced course management menu")
def display_enhanced_course_menu(auth):
    """Display the enhanced course management menu"""
    if not auth or not auth.current_user:
        print(get_text('course_mgmt.login_required', default='You must be logged in to access course management.'))
        return

    # Initialize enhanced database schema
    initialize_enhanced_database()

    def _module_management():
        from education_system.systems.university.shell.cli.module_operations import display_module_management_menu
        display_module_management_menu()

    # The 37 options used to be printed as one flat list. They are grouped
    # here and shown two levels deep: pick an area, then an action.
    if auth.check_permission('manage_courses'):
        groups = [
            (f"📚 {get_text('course_mgmt.sections.course_management', default='COURSES')}", [
                (get_text('course_mgmt.menu.create_course', default='Create new course'), lambda: create_enhanced_course(auth)),
                (get_text('course_mgmt.menu.view_courses', default='View all courses'), lambda: view_all_courses(auth)),
                (get_text('course_mgmt.menu.update_course', default='Update course'), lambda: update_course(auth)),
                (get_text('course_mgmt.menu.delete_course', default='Delete course'), lambda: delete_course(auth)),
                (get_text('course_mgmt.menu.manage_status', default='Manage course status'), lambda: manage_course_status(auth)),
                (get_text('course_mgmt.menu.search_courses', default='Search courses'), lambda: search_courses(auth)),
                (get_text('course_mgmt.menu.course_history', default='Course history'), lambda: view_course_history(auth)),
            ]),
            (f"🔗 {get_text('course_mgmt.sections.prerequisites', default='CURRICULUM & STRUCTURE')}", [
                (get_text('course_mgmt.menu.add_prerequisite', default='Add prerequisite'), lambda: add_prerequisite(auth)),
                (get_text('course_mgmt.menu.view_prerequisites', default='View prerequisites'), lambda: view_prerequisites(auth)),
                (get_text('course_mgmt.menu.remove_prerequisite', default='Remove prerequisite'), lambda: remove_prerequisite(auth)),
                (get_text('course_mgmt.menu.curriculum_extensions', default='Curriculum extensions'), lambda: display_curriculum_extensions_menu(auth)),
                (get_text('course_mgmt.menu.module_management', default='Module Management'), _module_management),
            ]),
            (f"👨‍🏫 {get_text('course_mgmt.sections.instructor_management', default='INSTRUCTORS & SCHEDULING')}", [
                (get_text('course_mgmt.menu.create_instructor', default='Create instructor'), lambda: create_instructor(auth)),
                (get_text('course_mgmt.menu.view_instructors', default='View instructors'), lambda: view_instructors(auth)),
                (get_text('course_mgmt.menu.assign_to_course', default='Assign to course'), lambda: assign_instructor_to_course(auth)),
                (get_text('course_mgmt.menu.create_schedule', default='Create schedule'), lambda: create_course_schedule(auth)),
                (get_text('course_mgmt.menu.view_schedules', default='View schedules'), lambda: view_course_schedules(auth)),
                (get_text('course_mgmt.menu.update_schedule', default='Update schedule'), lambda: update_schedule(auth)),
            ]),
            (f"📊 {get_text('course_mgmt.sections.enrollment_waitlists', default='ENROLMENT & ANALYTICS')}", [
                (get_text('course_mgmt.menu.add_to_waitlist', default='Add to waitlist'), lambda: add_to_waitlist(auth)),
                (get_text('course_mgmt.menu.view_waitlists', default='View waitlists'), lambda: view_waitlists(auth)),
                (get_text('course_mgmt.menu.process_waitlist', default='Process waitlist'), lambda: process_waitlist(auth)),
                (get_text('course_mgmt.menu.analytics_dashboard', default='Analytics dashboard'), lambda: generate_course_analytics(auth)),
                (get_text('course_mgmt.menu.enrollment_report', default='Enrollment report'), lambda: generate_enrollment_report(auth)),
                (get_text('course_mgmt.menu.dept_statistics', default='Dept statistics'), lambda: department_statistics(auth)),
                (get_text('course_mgmt.menu.recommendations', default='Recommendations'), lambda: recommend_courses(auth)),
                (get_text('course_mgmt.menu.alternative_courses', default='Alternative courses'), lambda: find_alternative_courses(auth)),
            ]),
            (f"🧰 {get_text('course_mgmt.sections.utilities', default='TOOLS, DATA & SETTINGS')}", [
                (get_text('course_mgmt.menu.import_csv', default='Import from CSV'), lambda: import_courses_from_csv(auth)),
                (get_text('course_mgmt.menu.export_csv', default='Export to CSV'), lambda: export_courses_to_csv(auth)),
                (get_text('course_mgmt.menu.bulk_update', default='Bulk update'), lambda: bulk_update_courses(auth)),
                ('Course Planning Assistant', _launch_course_planning_cli),
                ('Course Evaluation', lambda: _launch_course_evaluation_cli(auth)),
                ('Degree Audit', lambda: _launch_degree_audit_cli(auth)),
                ('Graduation Ceremony', lambda: _launch_graduation_ceremony_cli(auth)),
                (get_text('course_mgmt.menu.system_maintenance', default='System maintenance'), lambda: system_maintenance(auth)),
                (get_text('course_mgmt.menu.language', default='Change Language'), display_language_menu_option),
            ]),
        ]
    elif auth.check_permission('view_courses'):
        groups = [
            (f"📚 {get_text('course_mgmt.sections.course_viewing', default='BROWSE COURSES')}", [
                (get_text('course_mgmt.menu.view_courses', default='View all courses'), lambda: view_all_courses(auth)),
                (get_text('course_mgmt.menu.search_courses', default='Search courses'), lambda: search_courses(auth)),
                (get_text('course_mgmt.menu.view_prerequisites', default='View prerequisites'), lambda: view_prerequisites(auth)),
                (get_text('course_mgmt.menu.recommendations', default='Course recommendations'), lambda: recommend_courses(auth)),
                (get_text('course_mgmt.menu.course_analytics', default='Course analytics'), lambda: generate_course_analytics(auth)),
            ]),
            ("📋 INTEGRATED TOOLS", [
                ('Course Planning Assistant', _launch_course_planning_cli),
                ('Course Evaluation', lambda: _launch_course_evaluation_cli(auth)),
                ('Degree Audit', lambda: _launch_degree_audit_cli(auth)),
                (get_text('course_mgmt.menu.curriculum_extensions', default='Curriculum extensions'), lambda: display_curriculum_extensions_menu(auth)),
            ]),
            (f"⚙️  {get_text('course_mgmt.sections.settings', default='SETTINGS')}", [
                (get_text('course_mgmt.menu.language', default='Change Language'), display_language_menu_option),
            ]),
        ]
    else:
        print(get_text('course_mgmt.no_permission', default="You don't have permission to manage courses."))
        return

    while True:
        print("\n" + "="*100)
        print(get_text('course_mgmt.title', default='ENHANCED COURSE MANAGEMENT SYSTEM').center(100))
        print("="*100)

        for number, (title, actions) in enumerate(groups, 1):
            print(f"  {number}. {title}  ({len(actions)})")
        print(f"\n  0. {get_text('course_mgmt.menu.return_main', default='Return to Main Menu')}")

        choice = input(f"\n{get_text('course_mgmt.enter_choice', default='Enter your choice')} (0-{len(groups)}): ").strip()

        if choice == '0':
            return
        if not (choice.isdigit() and 1 <= int(choice) <= len(groups)):
            print(get_text('course_mgmt.invalid_choice',
                           default='Invalid choice. Please enter a number between 0 and {max_option}.'
                           ).format(max_option=len(groups)))
            continue

        title, actions = groups[int(choice) - 1]

        while True:
            print("\n" + "="*100)
            print(title.center(100))
            print("="*100)
            for number, (label, _handler) in enumerate(actions, 1):
                print(f"  {number:>2}. {label}")
            print(f"\n   0. {get_text('course_mgmt.menu.return_main', default='Back')}")

            picked = input(f"\n{get_text('course_mgmt.enter_choice', default='Enter your choice')} (0-{len(actions)}): ").strip()

            if picked == '0' or picked == '':
                break
            if not (picked.isdigit() and 1 <= int(picked) <= len(actions)):
                print(get_text('course_mgmt.invalid_choice',
                               default='Invalid choice. Please enter a number between 0 and {max_option}.'
                               ).format(max_option=len(actions)))
                continue

            handler = actions[int(picked) - 1][1]
            handler()

            input(f"\n{get_text('course_mgmt.press_enter', default='Press Enter to continue...')}")


@log_menu_navigation(description="Displaying course management menu")
def display_course_management_menu(auth):
    """Legacy function - redirects to enhanced menu"""
    return display_enhanced_course_menu(auth)
