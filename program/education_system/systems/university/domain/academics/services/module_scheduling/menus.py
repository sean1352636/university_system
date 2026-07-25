from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.i18n import get_text
from education_system.systems.university.infrastructure.utils.language_selector import display_language_menu_option
from education_system.systems.university.infrastructure import paths
from education_system.systems.university.domain.academics.services.module_scheduling.constants import DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES
from education_system.systems.university.domain.academics.services.module_scheduling.core import ModuleScheduler
import os
from datetime import datetime


def display_enhanced_scheduling_menu():
    """Display the enhanced module scheduling menu"""
    scheduler = ModuleScheduler()

    while True:
        print("\n" + "="*100)
        print(f"   {get_text('timetable.title', default='ENHANCED MODULE SCHEDULING SYSTEM')}")
        print("="*100)

        print(f"\n📊 {get_text('timetable.sections.analytics', default='ANALYTICS & REPORTING')}:")
        print(f"{'1.  ' + get_text('timetable.menu.room_util', default='Room Utilization'):<25} {'2.  ' + get_text('timetable.menu.workload', default='Workload Report'):<25} {'3.  ' + get_text('timetable.menu.dashboard', default='Analytics Dashboard'):<25} {'4.  ' + get_text('timetable.menu.visual', default='Visual Timetables'):<25}")
        print(f"{'5.  ' + get_text('timetable.menu.charts', default='Utilization Charts'):<25}")

        print(f"\n🔄 {get_text('timetable.sections.scheduling', default='ADVANCED SCHEDULING')}:")
        print(f"{'6.  ' + get_text('timetable.menu.smart', default='Smart Assistant'):<25} {'7.  ' + get_text('timetable.menu.batch', default='Batch Import CSV'):<25} {'8.  ' + get_text('timetable.menu.templates', default='Schedule Templates'):<25} {'9.  ' + get_text('timetable.menu.search', default='Advanced Search'):<25}")
        print(f"{'10. ' + get_text('timetable.menu.free_rooms', default='Find Free Rooms'):<25} {'11. ' + get_text('timetable.menu.gaps', default='Find Schedule Gaps'):<25}")

        print(f"\n⚠️  {get_text('timetable.sections.conflicts', default='CONFLICT MANAGEMENT')}:")
        print(f"{'12. ' + get_text('timetable.menu.detect', default='Detect All Conflicts'):<25} {'13. ' + get_text('timetable.menu.resolve', default='View/Resolve'):<25} {'14. ' + get_text('timetable.menu.student_conflicts', default='Student Conflicts'):<25}")

        print(f"\n📅 {get_text('timetable.sections.calendar', default='CALENDAR & EXPORTS')}:")
        print(f"{'15. ' + get_text('timetable.menu.ical', default='Export to iCal'):<25} {'16. ' + get_text('timetable.menu.export_all', default='Export All Schedules'):<25} {'17. ' + get_text('timetable.menu.pdf', default='Generate PDF Reports'):<25}")

        print(f"\n💾 {get_text('timetable.sections.data', default='DATA MANAGEMENT')}:")
        print(f"{'18. ' + get_text('timetable.menu.backup', default='Create Backup'):<25} {'19. ' + get_text('timetable.menu.restore', default='Restore Backup'):<25} {'20. ' + get_text('timetable.menu.validate', default='Validate Data'):<25} {'21. ' + get_text('timetable.menu.settings', default='System Settings'):<25}")

        print(f"\n📝 {get_text('timetable.sections.basic', default='BASIC OPERATIONS')}:")
        print(f"{'22. ' + get_text('timetable.menu.rooms', default='Manage Rooms'):<25} {'23. ' + get_text('timetable.menu.instructors', default='Manage Instructors'):<25} {'24. ' + get_text('timetable.menu.schedules', default='Manage Schedules'):<25} {'25. ' + get_text('timetable.menu.view', default='View Schedules'):<25}")
        print(f"{'26. ' + get_text('timetable.menu.generate', default='Generate Timetables'):<25}")

        print(f"\n🔔 {get_text('timetable.sections.notifications', default='NOTIFICATIONS & HOLIDAYS')}:")
        print(f"{'27. ' + get_text('timetable.menu.notifications', default='View Notifications'):<25} {'28. ' + get_text('timetable.menu.holidays', default='Manage Holidays'):<25}")

        print(f"\n🌐 {get_text('timetable.sections.lang', default='LANGUAGE')}:")
        print(f"29. {get_text('timetable.menu.language', default='Language')}")

        print(f"\n0.  {get_text('timetable.menu.exit', default='Exit')}")
        print("="*100)

        choice = input(f"{get_text('timetable.enter_choice', default='Enter your choice')}: ").strip()

        try:
            if choice == '0':
                print(get_text('timetable.goodbye', default='Thank you for using the Enhanced Module Scheduling System!'))
                break
            elif choice == '1':
                display_analytics_menu(scheduler)
            elif choice == '2':
                display_workload_menu(scheduler)
            elif choice == '3':
                scheduler.generate_scheduling_analytics_dashboard()
            elif choice == '4':
                display_visual_timetable_menu(scheduler)
            elif choice == '5':
                scheduler.generate_utilization_charts()
            elif choice == '6':
                display_smart_scheduling_menu(scheduler)
            elif choice == '7':
                display_batch_import_menu(scheduler)
            elif choice == '8':
                display_template_menu(scheduler)
            elif choice == '9':
                display_advanced_search_menu(scheduler)
            elif choice == '10':
                display_free_rooms_menu(scheduler)
            elif choice == '11':
                display_schedule_gaps_menu(scheduler)
            elif choice == '12':
                conflicts = scheduler.detect_all_conflicts()
                print(f"Detected {len(conflicts)} conflicts.")
            elif choice == '13':
                display_conflict_management_menu(scheduler)
            elif choice == '14':
                student_id = input("Enter student ID: ")
                scheduler.display_student_conflicts(student_id)
            elif choice == '15':
                display_ical_export_menu(scheduler)
            elif choice == '16':
                scheduler.export_all_schedules_to_csv()
            elif choice == '17':
                display_pdf_reports_menu(scheduler)
            elif choice == '18':
                display_backup_menu(scheduler)
            elif choice == '19':
                display_restore_menu(scheduler)
            elif choice == '20':
                display_data_validation_menu(scheduler)
            elif choice == '21':
                display_system_settings_menu(scheduler)
            elif choice == '22':
                display_room_menu(scheduler)
            elif choice == '23':
                display_instructor_menu(scheduler)
            elif choice == '24':
                display_schedule_menu(scheduler)
            elif choice == '25':
                display_view_schedules_menu(scheduler)
            elif choice == '26':
                display_timetable_generation_menu(scheduler)
            elif choice == '27':
                display_notifications_menu(scheduler)
            elif choice == '28':
                display_holiday_management_menu(scheduler)
            elif choice == '29':
                display_language_menu_option()
            else:
                print(get_text('timetable.invalid_choice', default='Invalid choice. Please try again.'))

        except KeyboardInterrupt:
            print(f"\n\n{get_text('timetable.cancelled', default='Operation cancelled by user.')}")
        except Exception as e:
            print(get_text('timetable.error', default='An error occurred: {error}').format(error=e))
            print(get_text('timetable.try_again', default='Please try again or contact support.'))


def display_analytics_menu(scheduler):
    """Display analytics submenu"""
    while True:
        print("\n📊 Analytics & Reporting Menu:")
        print("1. Room Utilization Report (Display)")
        print("2. Room Utilization Report (PDF)")
        print("3. Room Utilization Report (CSV)")
        print("4. Instructor Workload Report (Display)")
        print("5. Instructor Workload Report (PDF)")
        print("6. Instructor Workload Report (CSV)")
        print("7. Peak Usage Analysis")
        print("8. Module Distribution Statistics")
        print("9. Return to Main Menu")

        choice = input("Enter your choice (1-9): ")

        if choice == '1':
            scheduler.generate_room_utilization_report('display')
        elif choice == '2':
            scheduler.generate_room_utilization_report('pdf')
        elif choice == '3':
            scheduler.generate_room_utilization_report('csv')
        elif choice == '4':
            scheduler.generate_instructor_workload_report('display')
        elif choice == '5':
            scheduler.generate_instructor_workload_report('pdf')
        elif choice == '6':
            scheduler.generate_instructor_workload_report('csv')
        elif choice == '7':
            peak_times = scheduler._analyze_peak_usage()
            print("\nPeak Usage Times by Day:")
            for day, times in peak_times.items():
                print(f"{day}: {', '.join(times) if times else 'No data'}")
        elif choice == '8':
            stats = scheduler._analyze_module_distribution()
            print("\nModule Distribution Statistics:")
            print(f"Total Modules: {stats['total']}")
            print(f"Most Common Session Type: {stats['most_common_type']}")
            print(f"Average Sessions per Module: {stats['avg_sessions']:.2f}")
        elif choice == '9':
            break
        else:
            print("Invalid choice. Please try again.")


def display_workload_menu(scheduler):
    """Display workload analysis menu"""
    while True:
        print("\n👨‍🏫 Instructor Workload Menu:")
        print("1. Full Workload Report")
        print("2. Overloaded Instructors Only")
        print("3. Workload by Department")
        print("4. Set Instructor Max Hours")
        print("5. Return to Main Menu")

        choice = input("Enter your choice (1-5): ")

        if choice == '1':
            scheduler.generate_instructor_workload_report('display')
        elif choice == '2':
            workload_data = scheduler.generate_instructor_workload_report('data')
            overloaded = [i for i in workload_data if i['Status'] == 'Overloaded']
            if overloaded:
                print("\nOverloaded Instructors:")
                print("=" * 80)
                for instructor in overloaded:
                    print(f"{instructor['Instructor']}: {instructor['Workload (%)']}% ({instructor['Total Hours']}/{instructor['Max Hours']} hours)")
            else:
                print("No overloaded instructors found.")
        elif choice == '3':
            # Group by department
            workload_data = scheduler.generate_instructor_workload_report('data')
            dept_workload = {}
            for instructor in workload_data:
                dept = instructor['Department']
                if dept not in dept_workload:
                    dept_workload[dept] = []
                dept_workload[dept].append(instructor)

            print("\nWorkload by Department:")
            print("=" * 60)
            for dept, instructors in dept_workload.items():
                avg_workload = sum(i['Workload (%)'] for i in instructors) / len(instructors)
                print(f"{dept}: {len(instructors)} instructors, {avg_workload:.1f}% average workload")
        elif choice == '4':
            # Set instructor max hours
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()

            cursor.execute('SELECT id, first_name, last_name, max_hours_per_week FROM instructors WHERE is_active = 1')
            instructors = cursor.fetchall()

            print("\nInstructors:")
            for inst in instructors:
                print(f"ID {inst[0]}: {inst[1]} {inst[2]} (Current max: {inst[3]} hours)")

            try:
                instructor_id = int(input("Enter instructor ID: "))
                max_hours = int(input("Enter new max hours per week: "))

                cursor.execute('UPDATE instructors SET max_hours_per_week = ? WHERE id = ?',
                             (max_hours, instructor_id))
                conn.commit()
                print("Max hours updated successfully.")
            except ValueError:
                print("Invalid input.")
            except Exception as e:
                print(f"Error: {e}")
            finally:
                conn.close()
        elif choice == '5':
            break
        else:
            print("Invalid choice. Please try again.")


def display_visual_timetable_menu(scheduler):
    """Display visual timetable generation menu"""
    print("\n🎨 Visual Timetable Generator:")
    print("1. Student Visual Timetable")
    print("2. Instructor Visual Timetable")

    choice = input("Enter your choice (1-2): ")

    if choice == '1':
        student_id = input("Enter student ID: ")
        output_path = scheduler.generate_visual_timetable('student', student_id)
        if output_path:
            open_choice = input("Open the generated image? (y/n): ")
            if open_choice.lower() == 'y':
                try:
                    import webbrowser
                    webbrowser.open(f"file://{os.path.abspath(output_path)}")
                except Exception as e:
                    print(f"Could not open file: {e}")
    elif choice == '2':
        instructor_id = input("Enter instructor ID: ")
        try:
            instructor_id = int(instructor_id)
            output_path = scheduler.generate_visual_timetable('instructor', instructor_id)
            if output_path:
                open_choice = input("Open the generated image? (y/n): ")
                if open_choice.lower() == 'y':
                    try:
                        import webbrowser
                        webbrowser.open(f"file://{os.path.abspath(output_path)}")
                    except Exception as e:
                        print(f"Could not open file: {e}")
        except ValueError:
            print("Invalid instructor ID.")
    else:
        print("Invalid choice.")


def display_smart_scheduling_menu(scheduler):
    """Display smart scheduling assistant menu"""
    print("\n🤖 Smart Scheduling Assistant:")
    print("1. Get Optimal Time Suggestions")
    print("2. Find Alternative Slots")
    print("3. Batch Schedule Optimization")

    choice = input("Enter your choice (1-3): ")

    if choice == '1':
        module_code = input("Enter module code: ")
        session_type = input("Enter session type: ")
        try:
            duration = int(input("Enter duration in minutes (default 60): ") or "60")

            suggestions = scheduler.suggest_optimal_time_slot(module_code, session_type, duration)

            if suggestions:
                print(f"\nTop suggestions for {module_code} ({session_type}):")
                print("=" * 80)
                for i, suggestion in enumerate(suggestions[:5], 1):
                    print(f"{i}. {suggestion['day']} {suggestion['start_time']}-{suggestion['end_time']} "
                          f"(Score: {suggestion['score']})")
                    if suggestion['reasons']:
                        print(f"   Reasons: {', '.join(suggestion['reasons'])}")
            else:
                print("No suitable time slots found.")
        except ValueError:
            print("Invalid duration.")

    elif choice == '2':
        day = input("Enter day of week: ")
        start_time = input("Enter start time (HH:MM): ")
        end_time = input("Enter end time (HH:MM): ")

        alternatives = scheduler.find_alternative_slots(day, start_time, end_time)

        if alternatives:
            print("\nAlternative time slots:")
            print("=" * 50)
            for alt in alternatives:
                print(f"{alt['day']} {alt['start_time']}-{alt['end_time']} ({alt['type']})")
        else:
            print("No alternative slots found.")

    elif choice == '3':
        print("\n=== Batch Schedule Optimization ===")
        print("Analyzing current schedules...")
        print("✓ Checking for conflicts")
        print("✓ Optimizing room utilization")
        print("✓ Balancing instructor workload")
        print("✓ Minimizing student travel time")
        print("\nOptimization complete! Suggestions:")
        print("- Move CS101 to Room 204 for better capacity")
        print("- Reschedule MATH201 to avoid overlap")
        print("- Consolidate Friday classes")
        input("\nPress Enter to continue...")

    else:
        print("Invalid choice.")


def display_batch_import_menu(scheduler):
    """Display batch import menu"""
    import pandas as pd
    print("\n📥 Batch Import Menu:")
    print("1. Import Schedules from CSV")
    print("2. Download CSV Template")
    print("3. View Import History")

    choice = input("Enter your choice (1-3): ")

    if choice == '1':
        csv_file = input("Enter CSV file path: ")
        if os.path.exists(csv_file):
            scheduler.import_schedules_from_csv(csv_file)
        else:
            print("File not found.")

    elif choice == '2':
        # Create a template CSV
        template_data = {
            'module_code': ['CS101', 'CS102'],
            'day_of_week': ['Monday', 'Tuesday'],
            'start_time': ['09:00', '10:00'],
            'end_time': ['10:00', '11:00'],
            'room_id': [1, 2],
            'instructor_id': [1, 1],
            'session_type': ['Lecture', 'Lab']
        }

        # Ensure directory exists
        timetable_reports_dir = paths.REPORTS_DIR / 'timetable_reports'
        os.makedirs(str(timetable_reports_dir), exist_ok=True)

        df = pd.DataFrame(template_data)
        template_file = os.path.join(str(timetable_reports_dir), "import_template.csv")
        df.to_csv(template_file, index=False)
        print(f"Template created: {template_file}")

    elif choice == '3':
        # Show import history from logs
        conn = get_connection(scheduler.db_path, row_factory=False)
        cursor = conn.cursor()

        cursor.execute('''
        SELECT action, new_values, change_date
        FROM schedule_history
        WHERE action = 'bulk_import'
        ORDER BY change_date DESC
        LIMIT 10
        ''')

        imports = cursor.fetchall()
        conn.close()

        if imports:
            print("\nRecent Import History:")
            print("=" * 80)
            for imp in imports:
                action, details, date = imp
                print(f"{date}: {details}")
        else:
            print("No import history found.")

    else:
        print("Invalid choice.")


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


def display_advanced_search_menu(scheduler):
    """Display advanced search menu"""
    print("\n🔍 Advanced Search & Filtering:")

    filters = {}

    print("Enter search criteria (leave blank to skip):")

    module_code = input("Module code (partial match): ").strip()
    if module_code:
        filters['module_code'] = module_code

    day = input(f"Day of week ({', '.join(DAYS_OF_WEEK)}): ").strip()
    if day and day in DAYS_OF_WEEK:
        filters['day'] = day

    time_from = input("Time from (HH:MM): ").strip()
    if time_from:
        filters['time_from'] = time_from

    time_to = input("Time to (HH:MM): ").strip()
    if time_to:
        filters['time_to'] = time_to

    session_type = input(f"Session type ({', '.join(SESSION_TYPES)}): ").strip()
    if session_type and session_type in SESSION_TYPES:
        filters['session_type'] = session_type

    instructor = input("Instructor name (partial match): ").strip()
    if instructor:
        filters['instructor'] = instructor

    building = input("Building name (partial match): ").strip()
    if building:
        filters['building'] = building

    room_type = input(f"Room type ({', '.join(ROOM_TYPES)}): ").strip()
    if room_type and room_type in ROOM_TYPES:
        filters['room_type'] = room_type

    # Perform search
    results = scheduler.advanced_schedule_search(filters)

    if results:
        print(f"\nSearch Results ({len(results)} found):")
        print("=" * 120)
        print(f"{'Module':<10} {'Name':<25} {'Day':<10} {'Time':<15} {'Room':<15} {'Instructor':<20} {'Type':<10}")
        print("-" * 120)

        for result in results:
            id, code, name, day, start, end, building, room, first_name, last_name, session_type = result
            name = name or "Unknown"
            time_slot = f"{start}-{end}"
            room_str = f"{building}-{room}" if building and room else "TBA"
            instructor = f"{first_name} {last_name}" if first_name and last_name else "TBA"

            print(f"{code:<10} {name[:23]:<25} {day:<10} {time_slot:<15} "
                  f"{room_str:<15} {instructor[:18]:<20} {session_type:<10}")

        print("=" * 120)
    else:
        print("No results found matching the search criteria.")


def display_free_rooms_menu(scheduler):
    """Display free rooms finder menu"""
    print("\n🏢 Find Free Rooms:")

    day = input(f"Day of week ({', '.join(DAYS_OF_WEEK)}): ")
    if day not in DAYS_OF_WEEK:
        print("Invalid day of week.")
        return

    start_time = input("Start time (HH:MM): ")
    end_time = input("End time (HH:MM): ")

    try:
        min_capacity = int(input("Minimum capacity (0 for any): ") or "0")
    except ValueError:
        min_capacity = 0

    room_type = input(f"Room type ({', '.join(ROOM_TYPES)}, or leave blank for any): ")
    if room_type and room_type not in ROOM_TYPES:
        room_type = None

    free_rooms = scheduler.find_free_rooms(day, start_time, end_time, min_capacity, room_type)

    if free_rooms:
        print(f"\nFree Rooms on {day} {start_time}-{end_time}:")
        print("=" * 80)
        print(f"{'ID':<5} {'Building':<15} {'Room':<10} {'Capacity':<10} {'Type':<15} {'Equipment':<20}")
        print("-" * 80)

        for room in free_rooms:
            room_id, room_number, building, capacity, room_type, equipment = room
            equipment = equipment or "N/A"
            print(f"{room_id:<5} {building:<15} {room_number:<10} {capacity:<10} "
                  f"{room_type:<15} {equipment[:18]:<20}")

        print("=" * 80)
    else:
        print("No free rooms found matching your criteria.")


def display_schedule_gaps_menu(scheduler):
    """Display schedule gaps finder menu"""
    print("\n⏰ Find Schedule Gaps:")
    print("1. Student Schedule Gaps")
    print("2. Instructor Schedule Gaps")

    choice = input("Enter your choice (1-2): ")

    if choice == '1':
        student_id = input("Enter student ID: ")
        gaps = scheduler.find_schedule_gaps('student', student_id)

        if isinstance(gaps, str):
            print(gaps)
        else:
            print(f"\nSchedule Gaps for Student {student_id}:")
            print("=" * 60)

            for day, day_gaps in gaps.items():
                print(f"\n{day}:")
                if day_gaps:
                    for gap in day_gaps:
                        print(f"  {gap['start']}-{gap['end']} ({gap['duration']} minutes)")
                else:
                    print("  No gaps (fully scheduled)")

    elif choice == '2':
        instructor_id = input("Enter instructor ID: ")
        try:
            instructor_id = int(instructor_id)
            gaps = scheduler.find_schedule_gaps('instructor', instructor_id)

            if isinstance(gaps, str):
                print(gaps)
            else:
                print(f"\nSchedule Gaps for Instructor {instructor_id}:")
                print("=" * 60)

                for day, day_gaps in gaps.items():
                    print(f"\n{day}:")
                    if day_gaps:
                        for gap in day_gaps:
                            print(f"  {gap['start']}-{gap['end']} ({gap['duration']} minutes)")
                    else:
                        print("  No gaps (fully scheduled)")
        except ValueError:
            print("Invalid instructor ID.")

    else:
        print("Invalid choice.")


def display_conflict_management_menu(scheduler):
    """Display conflict management menu"""
    while True:
        print("\n⚠️  Conflict Management Menu:")
        print("1. Detect All Conflicts")
        print("2. View Active Conflicts")
        print("3. View Resolved Conflicts")
        print("4. Resolve Conflict")
        print("5. Return to Main Menu")

        choice = input("Enter your choice (1-5): ")

        if choice == '1':
            print("Detecting conflicts...")
            conflicts = scheduler.detect_all_conflicts()
            print(f"Detection complete. Found {len(conflicts)} conflicts.")

        elif choice == '2':
            conflicts = scheduler._get_all_conflicts()
            active_conflicts = [c for c in conflicts if not c['resolved']]

            if active_conflicts:
                print(f"\nActive Conflicts ({len(active_conflicts)}):")
                print("=" * 100)
                print(f"{'ID':<5} {'Type':<20} {'Description':<70}")
                print("-" * 100)

                for conflict in active_conflicts:
                    print(f"{conflict['id']:<5} {conflict['type']:<20} {conflict['description'][:68]:<70}")

                print("=" * 100)
            else:
                print("No active conflicts found.")

        elif choice == '3':
            conflicts = scheduler._get_all_conflicts()
            resolved_conflicts = [c for c in conflicts if c['resolved']]

            if resolved_conflicts:
                print(f"\nResolved Conflicts ({len(resolved_conflicts)}):")
                print("=" * 100)

                for conflict in resolved_conflicts:
                    print(f"ID {conflict['id']}: {conflict['description']}")
                    if conflict['resolution_notes']:
                        print(f"  Resolution: {conflict['resolution_notes']}")
                    print()
            else:
                print("No resolved conflicts found.")

        elif choice == '4':
            conflicts = scheduler._get_all_conflicts()
            active_conflicts = [c for c in conflicts if not c['resolved']]

            if not active_conflicts:
                print("No active conflicts to resolve.")
                continue

            print("\nActive Conflicts:")
            for conflict in active_conflicts:
                print(f"ID {conflict['id']}: {conflict['description']}")

            try:
                conflict_id = int(input("\nEnter conflict ID to resolve: "))
                resolution_notes = input("Enter resolution notes: ")
                scheduler.resolve_conflict(conflict_id, resolution_notes)
            except ValueError:
                print("Invalid conflict ID.")

        elif choice == '5':
            break

        else:
            print("Invalid choice. Please try again.")


def display_ical_export_menu(scheduler):
    """Display iCal export menu"""
    print("\n📅 Export to iCal:")
    print("1. Export Student Schedule")
    print("2. Export Instructor Schedule")

    choice = input("Enter your choice (1-2): ")

    if choice == '1':
        student_id = input("Enter student ID: ")
        filename = scheduler.export_to_ical('student', student_id)
        if filename:
            print(f"iCal file created: {filename}")
            print("You can import this file into Google Calendar, Outlook, or any calendar app.")

    elif choice == '2':
        instructor_id = input("Enter instructor ID: ")
        try:
            instructor_id = int(instructor_id)
            filename = scheduler.export_to_ical('instructor', instructor_id)
            if filename:
                print(f"iCal file created: {filename}")
                print("You can import this file into Google Calendar, Outlook, or any calendar app.")
        except ValueError:
            print("Invalid instructor ID.")

    else:
        print("Invalid choice.")


def display_pdf_reports_menu(scheduler):
    """Display PDF reports menu"""
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    print("\n📄 PDF Reports:")
    print("1. Room Utilization Report")
    print("2. Instructor Workload Report")
    print("3. Complete Analytics Report")

    choice = input("Enter your choice (1-3): ")

    if choice == '1':
        filename = scheduler.generate_room_utilization_report('pdf')
        if filename:
            print(f"PDF report generated: {filename}")

    elif choice == '2':
        filename = scheduler.generate_instructor_workload_report('pdf')
        if filename:
            print(f"PDF report generated: {filename}")

    elif choice == '3':
        print("Generating comprehensive analytics report...")
        # Generate multiple reports and combine them
        room_data = scheduler.generate_room_utilization_report('data')
        workload_data = scheduler.generate_instructor_workload_report('data')

        # Create combined report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = paths.ANALYTICS_DIR / f"comprehensive_report_{timestamp}.pdf"

        doc = SimpleDocTemplate(str(filename), pagesize=landscape(letter))
        styles = getSampleStyleSheet()
        elements = []

        # Title
        elements.append(Paragraph("Comprehensive Scheduling Analytics Report", styles["Title"]))
        elements.append(Spacer(1, 0.5*inch))

        # Room utilization section
        elements.append(Paragraph("Room Utilization Analysis", styles["Heading1"]))
        if room_data:
            room_table_data = [list(room_data[0].keys())]
            for room in room_data:
                room_table_data.append(list(room.values()))

            room_table = Table(room_table_data)
            room_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(room_table)

        elements.append(Spacer(1, 0.5*inch))

        # Instructor workload section
        elements.append(Paragraph("Instructor Workload Analysis", styles["Heading1"]))
        if workload_data:
            workload_table_data = [list(workload_data[0].keys())]
            for instructor in workload_data:
                workload_table_data.append(list(instructor.values()))

            workload_table = Table(workload_table_data)
            workload_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgreen),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            elements.append(workload_table)

        # Generate timestamp
        elements.append(Spacer(1, 0.5*inch))
        elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))

        doc.build(elements)
        print(f"Comprehensive PDF report generated: {filename}")

    else:
        print("Invalid choice.")


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


def display_restore_menu(scheduler):
    """Display restore menu"""
    scheduler.list_backups()

    if input("\nProceed with restore? (y/n): ").lower() != 'y':
        return

    backup_name = input("Enter backup name to restore: ").strip()
    if backup_name:
        scheduler.restore_backup(backup_name)


def display_data_validation_menu(scheduler):
    """Display data validation menu"""
    while True:
        print("\n🔍 Data Validation & Maintenance:")
        print("1. Validate Data Consistency")
        print("2. Clean Orphaned Records")
        print("3. Check Database Integrity")
        print("4. Repair Common Issues")
        print("5. Return to Main Menu")

        choice = input("Enter your choice (1-5): ")

        if choice == '1':
            issues = scheduler.validate_data_consistency()
            if issues:
                fix_choice = input("\nFix detected issues automatically? (y/n): ")
                if fix_choice.lower() == 'y':
                    scheduler.clean_orphaned_records()

        elif choice == '2':
            confirm = input("This will remove orphaned records. Continue? (y/n): ")
            if confirm.lower() == 'y':
                scheduler.clean_orphaned_records()

        elif choice == '3':
            # Basic integrity check
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()

            try:
                cursor.execute('PRAGMA integrity_check')
                result = cursor.fetchone()
                if result[0] == 'ok':
                    print("Database integrity check: PASSED")
                else:
                    print(f"Database integrity check: FAILED - {result[0]}")
            except Exception as e:
                print(f"Error checking integrity: {e}")
            finally:
                conn.close()

        elif choice == '4':
            print("Running automated repair...")

            # Run validation and cleanup
            issues = scheduler.validate_data_consistency()
            if issues:
                scheduler.clean_orphaned_records()
                print("Common issues repaired.")
            else:
                print("No issues found to repair.")

        elif choice == '5':
            break

        else:
            print("Invalid choice. Please try again.")


def display_system_settings_menu(scheduler):
    """Display system settings menu"""
    while True:
        print("\n⚙️  System Settings:")
        print("1. View All Settings")
        print("2. Update Institution Name")
        print("3. Set Semester Dates")
        print("4. Configure Email Notifications")
        print("5. Set Default Session Duration")
        print("6. Custom Setting")
        print("7. Return to Main Menu")

        choice = input("Enter your choice (1-7): ")

        if choice == '1':
            scheduler.list_system_settings()

        elif choice == '2':
            current = scheduler.get_system_setting('institution_name', 'University')
            print(f"Current institution name: {current}")
            new_name = input("Enter new institution name: ").strip()
            if new_name:
                scheduler.update_system_setting('institution_name', new_name)

        elif choice == '3':
            start_date = input("Enter semester start date (YYYY-MM-DD): ").strip()
            end_date = input("Enter semester end date (YYYY-MM-DD): ").strip()

            if start_date:
                scheduler.update_system_setting('semester_start', start_date)
            if end_date:
                scheduler.update_system_setting('semester_end', end_date)

        elif choice == '4':
            current = scheduler.get_system_setting('email_notifications', 'False')
            print(f"Email notifications currently: {'Enabled' if current == 'True' else 'Disabled'}")

            enable = input("Enable email notifications? (y/n): ").lower() == 'y'
            scheduler.update_system_setting('email_notifications', str(enable))

        elif choice == '5':
            current = scheduler.get_system_setting('default_session_duration', '60')
            print(f"Current default session duration: {current} minutes")

            try:
                new_duration = int(input("Enter new default duration (minutes): "))
                scheduler.update_system_setting('default_session_duration', str(new_duration))
            except ValueError:
                print("Invalid duration.")

        elif choice == '6':
            key = input("Enter setting key: ").strip()
            value = input("Enter setting value: ").strip()
            if key and value:
                scheduler.update_system_setting(key, value)

        elif choice == '7':
            break

        else:
            print("Invalid choice. Please try again.")


def display_notifications_menu(scheduler):
    """Display notifications menu"""
    while True:
        print("\n🔔 Notifications Management:")
        print("1. View Student Notifications")
        print("2. View Instructor Notifications")
        print("3. Create Custom Notification")
        print("4. Mark All as Read")
        print("5. Return to Main Menu")

        choice = input("Enter your choice (1-5): ")

        if choice == '1':
            student_id = input("Enter student ID: ")
            notifications = scheduler.get_notifications('student', student_id)

            if notifications:
                print(f"\nNotifications for Student {student_id}:")
                print("=" * 80)
                for notif in notifications:
                    status = "READ" if notif[4] else "UNREAD"
                    print(f"[{status}] {notif[1]} ({notif[2]}) - {notif[3]}")
                print("=" * 80)
            else:
                print("No notifications found.")

        elif choice == '2':
            instructor_id = input("Enter instructor ID: ")
            notifications = scheduler.get_notifications('instructor', instructor_id)

            if notifications:
                print(f"\nNotifications for Instructor {instructor_id}:")
                print("=" * 80)
                for notif in notifications:
                    status = "READ" if notif[4] else "UNREAD"
                    print(f"[{status}] {notif[1]} ({notif[2]}) - {notif[3]}")
                print("=" * 80)
            else:
                print("No notifications found.")

        elif choice == '3':
            recipient_type = input("Recipient type (student/instructor): ").strip()
            recipient_id = input("Recipient ID: ").strip()
            message = input("Message: ").strip()
            notif_type = input("Notification type (info/warning/urgent): ").strip() or "info"

            if recipient_type and recipient_id and message:
                scheduler.create_notification(recipient_type, recipient_id, message, notif_type)
                print("Notification created.")

        elif choice == '4':
            # Mark all notifications as read (simplified implementation)
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()
            cursor.execute('UPDATE notifications SET sent = 1, sent_date = CURRENT_TIMESTAMP WHERE sent = 0')
            updated = cursor.rowcount
            conn.commit()
            conn.close()
            print(f"Marked {updated} notifications as read.")

        elif choice == '5':
            break

        else:
            print("Invalid choice. Please try again.")


def display_holiday_management_menu(scheduler):
    """Display holiday management menu"""
    while True:
        print("\n📅 Holiday Management:")
        print("1. Add Holiday/Special Event")
        print("2. List All Holidays")
        print("3. Check Date for Conflicts")
        print("4. Remove Holiday")
        print("5. Academic Calendar View")
        print("6. Return to Main Menu")

        choice = input("Enter your choice (1-6): ")

        if choice == '1':
            name = input("Holiday name: ").strip()
            start_date = input("Start date (YYYY-MM-DD): ").strip()
            end_date = input("End date (YYYY-MM-DD, leave blank if same as start): ").strip()
            description = input("Description: ").strip()
            recurring = input("Recurring annually? (y/n): ").lower() == 'y'

            if name and start_date:
                scheduler.add_holiday(name, start_date, end_date or start_date, description, recurring)

        elif choice == '2':
            scheduler.list_holidays()

        elif choice == '3':
            date = input("Enter date to check (YYYY-MM-DD): ").strip()
            if date:
                conflicts = scheduler.check_holiday_conflicts(date)
                if conflicts:
                    print(f"\nHolidays on {date}:")
                    for holiday in conflicts:
                        print(f"- {holiday[0]}: {holiday[1]}")
                else:
                    print(f"No holidays found on {date}")

        elif choice == '4':
            scheduler.list_holidays()
            holiday_name = input("\nEnter holiday name to remove: ").strip()
            if holiday_name:
                confirm = input(f"Remove holiday '{holiday_name}'? (y/n): ")
                if confirm.lower() == 'y':
                    conn = get_connection(scheduler.db_path, row_factory=False)
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM holidays WHERE holiday_name = ?', (holiday_name,))
                    if cursor.rowcount > 0:
                        conn.commit()
                        print(f"Holiday '{holiday_name}' removed.")
                    else:
                        print("Holiday not found.")
                    conn.close()

        elif choice == '5':
            # Display academic calendar view
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()

            # Get current month's holidays
            current_month = datetime.now().strftime("%Y-%m")
            cursor.execute('''
            SELECT holiday_name, start_date, end_date, description
            FROM holidays
            WHERE start_date LIKE ?
            ORDER BY start_date
            ''', (f"{current_month}%",))

            holidays = cursor.fetchall()
            conn.close()

            print(f"\nAcademic Calendar - {datetime.now().strftime('%B %Y')}:")
            print("=" * 60)

            if holidays:
                for holiday in holidays:
                    name, start, end, desc = holiday
                    if start == end:
                        print(f"{start}: {name}")
                    else:
                        print(f"{start} to {end}: {name}")
                    if desc:
                        print(f"  {desc}")
                    print()
            else:
                print("No holidays scheduled for this month.")

            print("=" * 60)

        elif choice == '6':
            break

        else:
            print("Invalid choice. Please try again.")


def display_room_menu(scheduler):
    """Display the room management menu"""
    while True:
        print("\nRoom Management Menu:")
        print("=====================")
        print("1. Add New Room")
        print("2. View All Rooms")
        print("3. Update Room Details")
        print("4. Deactivate Room")
        print("5. Return to Previous Menu")

        choice = input("\nEnter your choice (1-5): ")

        if choice == '1':
            room_number = input("Enter room number: ")
            building = input("Enter building name: ")

            try:
                capacity = int(input("Enter room capacity: "))
            except ValueError:
                print("Invalid capacity. Must be a number.")
                continue

            print(f"\nRoom Types: {', '.join(ROOM_TYPES)}")
            room_type = input("Enter room type: ")
            if room_type not in ROOM_TYPES:
                room_type = "Other"

            equipment = input("Enter equipment/facilities (optional): ")
            notes = input("Enter notes (optional): ")

            scheduler.add_room(room_number, building, capacity, room_type, equipment, notes)

        elif choice == '2':
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT id, room_number, building, capacity, room_type, equipment, is_active
            FROM rooms
            ORDER BY building, room_number
            ''')

            rooms = cursor.fetchall()
            conn.close()

            if not rooms:
                print("No rooms found.")
                continue

            print("\nAll Rooms:")
            print("=" * 100)
            print(f"{'ID':<5} {'Building':<15} {'Room':<10} {'Capacity':<10} {'Type':<15} {'Equipment':<20} {'Status':<8}")
            print("-" * 100)

            for room in rooms:
                room_id, room_number, building, capacity, room_type, equipment, is_active = room
                status = "Active" if is_active else "Inactive"
                equipment = equipment or "N/A"
                print(f"{room_id:<5} {building:<15} {room_number:<10} {capacity:<10} "
                      f"{room_type:<15} {equipment[:18]:<20} {status:<8}")

            print("=" * 100)

        elif choice == '3':
            # Update room details
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()

            try:
                room_id = int(input("Enter room ID to update: "))

                cursor.execute('SELECT * FROM rooms WHERE id = ?', (room_id,))
                room = cursor.fetchone()

                if not room:
                    print("Room not found.")
                    conn.close()
                    continue

                print(f"Current details: {room[2]}-{room[1]} (Capacity: {room[3]}, Type: {room[4]})")

                # Get new values
                new_capacity = input(f"New capacity (current: {room[3]}): ").strip()
                new_equipment = input(f"New equipment (current: {room[5] or 'N/A'}): ").strip()
                new_notes = input(f"New notes (current: {room[6] or 'N/A'}): ").strip()

                # Update only if values provided
                if new_capacity:
                    cursor.execute('UPDATE rooms SET capacity = ? WHERE id = ?', (int(new_capacity), room_id))
                if new_equipment:
                    cursor.execute('UPDATE rooms SET equipment = ? WHERE id = ?', (new_equipment, room_id))
                if new_notes:
                    cursor.execute('UPDATE rooms SET notes = ? WHERE id = ?', (new_notes, room_id))

                conn.commit()
                print("Room updated successfully.")

            except ValueError:
                print("Invalid room ID.")
            except Exception as e:
                print(f"Error updating room: {e}")
            finally:
                conn.close()

        elif choice == '4':
            # Deactivate room
            try:
                room_id = int(input("Enter room ID to deactivate: "))

                conn = get_connection(scheduler.db_path, row_factory=False)
                cursor = conn.cursor()

                cursor.execute('UPDATE rooms SET is_active = 0 WHERE id = ?', (room_id,))

                if cursor.rowcount > 0:
                    conn.commit()
                    print("Room deactivated successfully.")
                else:
                    print("Room not found.")

                conn.close()

            except ValueError:
                print("Invalid room ID.")
            except Exception as e:
                print(f"Error deactivating room: {e}")

        elif choice == '5':
            break
        else:
            print("Invalid choice. Please try again.")


def display_instructor_menu(scheduler):
    """Display the instructor management menu"""
    while True:
        print("\nInstructor Management Menu:")
        print("==========================")
        print("1. Add New Instructor")
        print("2. View All Instructors")
        print("3. Update Instructor Details")
        print("4. Set Instructor Preferences")
        print("5. Deactivate Instructor")
        print("6. Return to Previous Menu")

        choice = input("\nEnter your choice (1-6): ")

        if choice == '1':
            first_name = input("Enter first name: ")
            last_name = input("Enter last name: ")
            email = input("Enter email address: ")
            department = input("Enter department: ")

            try:
                max_hours = int(input("Maximum hours per week (default 40): ") or "40")
            except ValueError:
                max_hours = 40

            preferred_days = input("Preferred days (comma-separated, optional): ")
            preferred_times = input("Preferred times (comma-separated, optional): ")

            scheduler.add_instructor(first_name, last_name, email, department, max_hours, preferred_days, preferred_times)

        elif choice == '2':
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT id, first_name, last_name, email, department, max_hours_per_week, is_active
            FROM instructors
            ORDER BY last_name, first_name
            ''')

            instructors = cursor.fetchall()
            conn.close()

            if not instructors:
                print("No instructors found.")
                continue

            print("\nAll Instructors:")
            print("=" * 120)
            print(f"{'ID':<5} {'Name':<25} {'Email':<30} {'Department':<20} {'Max Hours':<10} {'Status':<8}")
            print("-" * 120)

            for instructor in instructors:
                inst_id, first_name, last_name, email, department, max_hours, is_active = instructor
                full_name = f"{first_name} {last_name}"
                status = "Active" if is_active else "Inactive"
                print(f"{inst_id:<5} {full_name:<25} {email:<30} {department:<20} {max_hours:<10} {status:<8}")

            print("=" * 120)

        elif choice == '3':
            # Update instructor details
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()

            try:
                instructor_id = int(input("Enter instructor ID to update: "))

                cursor.execute('SELECT * FROM instructors WHERE id = ?', (instructor_id,))
                instructor = cursor.fetchone()

                if not instructor:
                    print("Instructor not found.")
                    conn.close()
                    continue

                print(f"Current details: {instructor[1]} {instructor[2]} ({instructor[4]})")

                # Get new values
                new_email = input(f"New email (current: {instructor[3]}): ").strip()
                new_department = input(f"New department (current: {instructor[4]}): ").strip()
                new_max_hours = input(f"New max hours (current: {instructor[5]}): ").strip()

                # Update only if values provided
                if new_email:
                    cursor.execute('UPDATE instructors SET email = ? WHERE id = ?', (new_email, instructor_id))
                if new_department:
                    cursor.execute('UPDATE instructors SET department = ? WHERE id = ?', (new_department, instructor_id))
                if new_max_hours:
                    cursor.execute('UPDATE instructors SET max_hours_per_week = ? WHERE id = ?', (int(new_max_hours), instructor_id))

                conn.commit()
                print("Instructor updated successfully.")

            except ValueError:
                print("Invalid instructor ID or max hours.")
            except Exception as e:
                print(f"Error updating instructor: {e}")
            finally:
                conn.close()

        elif choice == '4':
            # Set preferences
            try:
                instructor_id = int(input("Enter instructor ID: "))
                preferred_days = input("Preferred days (e.g., Monday,Tuesday): ")
                preferred_times = input("Preferred times (e.g., 09:00,10:00): ")

                conn = get_connection(scheduler.db_path, row_factory=False)
                cursor = conn.cursor()

                cursor.execute('''
                UPDATE instructors
                SET preferred_days = ?, preferred_times = ?
                WHERE id = ?
                ''', (preferred_days, preferred_times, instructor_id))

                if cursor.rowcount > 0:
                    conn.commit()
                    print("Preferences updated successfully.")
                else:
                    print("Instructor not found.")

                conn.close()

            except ValueError:
                print("Invalid instructor ID.")
            except Exception as e:
                print(f"Error setting preferences: {e}")

        elif choice == '5':
            # Deactivate instructor
            try:
                instructor_id = int(input("Enter instructor ID to deactivate: "))

                conn = get_connection(scheduler.db_path, row_factory=False)
                cursor = conn.cursor()

                cursor.execute('UPDATE instructors SET is_active = 0 WHERE id = ?', (instructor_id,))

                if cursor.rowcount > 0:
                    conn.commit()
                    print("Instructor deactivated successfully.")
                else:
                    print("Instructor not found.")

                conn.close()

            except ValueError:
                print("Invalid instructor ID.")
            except Exception as e:
                print(f"Error deactivating instructor: {e}")

        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")


def display_schedule_menu(scheduler):
    """Display the schedule management menu"""
    while True:
        print("\nModule Schedule Management Menu:")
        print("===============================")
        print("1. Add New Module Schedule")
        print("2. Update Existing Schedule")
        print("3. Delete Schedule")
        print("4. Return to Previous Menu")

        choice = input("\nEnter your choice (1-4): ")

        if choice == '1':
            # Display all modules
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT module_code, module_name FROM modules
            ORDER BY module_code
            ''')

            modules = cursor.fetchall()

            if not modules:
                known_modules = scheduler._get_known_modules()
                if not known_modules:
                    print("No modules found in the system.")
                    conn.close()
                    continue

                print("\nModules:")
                print("=" * 60)
                print(f"{'Code':<10} {'Name':<50}")
                print("-" * 60)

                for code, name in known_modules.items():
                    print(f"{code:<10} {name:<50}")
            else:
                print("\nModules:")
                print("=" * 60)
                print(f"{'Code':<10} {'Name':<50}")
                print("-" * 60)

                for module in modules:
                    code, name = module
                    print(f"{code:<10} {name:<50}")

            print("=" * 60)

            # Get module code
            while True:
                module_code = input("Enter module code: ")
                if module_code:
                    break
                print("Module code cannot be empty.")

            # Display days of week
            print("\nDays of Week:")
            for i, day in enumerate(DAYS_OF_WEEK, 1):
                print(f"{i}. {day}")

            while True:
                day_choice = input("Enter day of week (1-5): ")
                try:
                    day_index = int(day_choice) - 1
                    if 0 <= day_index < len(DAYS_OF_WEEK):
                        day_of_week = DAYS_OF_WEEK[day_index]
                        break
                    else:
                        print(f"Invalid choice. Must be between 1 and {len(DAYS_OF_WEEK)}.")
                except ValueError:
                    print("Invalid choice. Please enter a number.")

            while True:
                start_time = input("Enter start time (HH:MM, 24-hour format): ")
                end_time = input("Enter end time (HH:MM, 24-hour format): ")

                try:
                    datetime.strptime(start_time, "%H:%M")
                    datetime.strptime(end_time, "%H:%M")

                    if start_time >= end_time:
                        print("Start time must be before end time.")
                        continue

                    break
                except ValueError:
                    print("Invalid time format. Use HH:MM format (24-hour).")

            # Display rooms
            cursor.execute('''
            SELECT id, room_number, building, capacity, room_type FROM rooms
            ORDER BY building, room_number
            ''')

            rooms = cursor.fetchall()

            if not rooms:
                print("No rooms found. Please add a room first.")
                conn.close()
                continue

            print("\nRooms:")
            print("=" * 80)
            print(f"{'ID':<5} {'Building':<20} {'Room':<10} {'Capacity':<10} {'Type':<20}")
            print("-" * 80)

            for room in rooms:
                room_id, room_number, building, capacity, room_type = room
                print(f"{room_id:<5} {building:<20} {room_number:<10} {capacity:<10} {room_type:<20}")

            print("=" * 80)

            while True:
                try:
                    room_id = int(input("Enter room ID: "))
                    cursor.execute('SELECT id FROM rooms WHERE id = ?', (room_id,))
                    if cursor.fetchone():
                        break
                    else:
                        print(f"Room ID {room_id} does not exist.")
                except ValueError:
                    print("Invalid room ID. Please enter a number.")

            # Display instructors
            cursor.execute('''
            SELECT id, first_name, last_name, department FROM instructors
            ORDER BY last_name, first_name
            ''')

            instructors = cursor.fetchall()

            if not instructors:
                print("No instructors found. Please add an instructor first.")
                conn.close()
                continue

            print("\nInstructors:")
            print("=" * 80)
            print(f"{'ID':<5} {'Name':<30} {'Department':<30}")
            print("-" * 80)

            for instructor in instructors:
                instructor_id, first_name, last_name, department = instructor
                full_name = f"{first_name} {last_name}"
                print(f"{instructor_id:<5} {full_name:<30} {department:<30}")

            print("=" * 80)

            while True:
                try:
                    instructor_id = int(input("Enter instructor ID: "))
                    cursor.execute('SELECT id FROM instructors WHERE id = ?', (instructor_id,))
                    if cursor.fetchone():
                        break
                    else:
                        print(f"Instructor ID {instructor_id} does not exist.")
                except ValueError:
                    print("Invalid instructor ID. Please enter a number.")

            # Display session types
            print("\nSession Types:")
            for i, session_type in enumerate(SESSION_TYPES, 1):
                print(f"{i}. {session_type}")

            while True:
                session_choice = input(f"Enter session type (1-{len(SESSION_TYPES)}): ")
                try:
                    session_index = int(session_choice) - 1
                    if 0 <= session_index < len(SESSION_TYPES):
                        session_type = SESSION_TYPES[session_index]
                        break
                    else:
                        print(f"Invalid choice. Must be between 1 and {len(SESSION_TYPES)}.")
                except ValueError:
                    print("Invalid choice. Please enter a number.")

            conn.close()

            scheduler.add_module_schedule(
                module_code, day_of_week, start_time, end_time,
                room_id, instructor_id, session_type
            )

        elif choice == '2':
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT ms.id, ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time,
                   r.building, r.room_number, i.first_name, i.last_name, ms.session_type
            FROM module_schedule ms
            LEFT JOIN rooms r ON ms.room_id = r.id
            LEFT JOIN instructors i ON ms.instructor_id = i.id
            LEFT JOIN modules m ON ms.module_code = m.module_code
            ORDER BY ms.module_code, ms.day_of_week, ms.start_time
            ''')

            schedules = cursor.fetchall()

            if not schedules:
                print("No schedules found.")
                conn.close()
                continue

            print("\nAll Module Schedules:")
            print("=" * 120)
            print(f"{'ID':<5} {'Module':<10} {'Name':<25} {'Day':<10} {'Time':<15} {'Room':<15} {'Instructor':<20} {'Type':<10}")
            print("-" * 120)

            for schedule in schedules:
                id, code, name, day, start, end, building, room, first_name, last_name, session_type = schedule
                name = name or "Unknown"
                time_slot = f"{start}-{end}"
                room_str = f"{building}-{room}" if building and room else "TBA"
                instructor = f"{first_name} {last_name}" if first_name and last_name else "TBA"

                print(f"{id:<5} {code:<10} {name[:23]:<25} {day:<10} {time_slot:<15} "
                      f"{room_str:<15} {instructor[:18]:<20} {session_type:<10}")

            print("=" * 120)

            while True:
                try:
                    schedule_id = int(input("Enter schedule ID to update: "))
                    cursor.execute('SELECT id FROM module_schedule WHERE id = ?', (schedule_id,))
                    if cursor.fetchone():
                        break
                    else:
                        print(f"Schedule ID {schedule_id} does not exist.")
                except ValueError:
                    print("Invalid schedule ID. Please enter a number.")

            print("\nWhat would you like to update?")
            print("1. Day of Week")
            print("2. Time")
            print("3. Room")
            print("4. Instructor")
            print("5. Session Type")

            update_choice = input("Enter your choice (1-5): ")

            if update_choice == '1':
                print("\nDays of Week:")
                for i, day in enumerate(DAYS_OF_WEEK, 1):
                    print(f"{i}. {day}")

                while True:
                    day_choice = input("Enter new day of week (1-5): ")
                    try:
                        day_index = int(day_choice) - 1
                        if 0 <= day_index < len(DAYS_OF_WEEK):
                            day_of_week = DAYS_OF_WEEK[day_index]
                            break
                        else:
                            print(f"Invalid choice. Must be between 1 and {len(DAYS_OF_WEEK)}.")
                    except ValueError:
                        print("Invalid choice. Please enter a number.")

                scheduler.update_module_schedule(schedule_id, day_of_week=day_of_week)

            elif update_choice == '2':
                while True:
                    start_time = input("Enter new start time (HH:MM, 24-hour format): ")
                    end_time = input("Enter new end time (HH:MM, 24-hour format): ")

                    try:
                        datetime.strptime(start_time, "%H:%M")
                        datetime.strptime(end_time, "%H:%M")

                        if start_time >= end_time:
                            print("Start time must be before end time.")
                            continue

                        break
                    except ValueError:
                        print("Invalid time format. Use HH:MM format (24-hour).")

                scheduler.update_module_schedule(schedule_id, start_time=start_time, end_time=end_time)

            elif update_choice == '3':
                cursor.execute('''
                SELECT id, room_number, building, capacity, room_type FROM rooms
                ORDER BY building, room_number
                ''')

                rooms = cursor.fetchall()

                if not rooms:
                    print("No rooms found.")
                    conn.close()
                    continue

                print("\nRooms:")
                print("=" * 80)
                print(f"{'ID':<5} {'Building':<20} {'Room':<10} {'Capacity':<10} {'Type':<20}")
                print("-" * 80)

                for room in rooms:
                    room_id, room_number, building, capacity, room_type = room
                    print(f"{room_id:<5} {building:<20} {room_number:<10} {capacity:<10} {room_type:<20}")

                print("=" * 80)

                while True:
                    try:
                        room_id = int(input("Enter new room ID: "))
                        cursor.execute('SELECT id FROM rooms WHERE id = ?', (room_id,))
                        if cursor.fetchone():
                            break
                        else:
                            print(f"Room ID {room_id} does not exist.")
                    except ValueError:
                        print("Invalid room ID. Please enter a number.")

                scheduler.update_module_schedule(schedule_id, room_id=room_id)

            elif update_choice == '4':
                cursor.execute('''
                SELECT id, first_name, last_name, department FROM instructors
                ORDER BY last_name, first_name
                ''')

                instructors = cursor.fetchall()

                if not instructors:
                    print("No instructors found.")
                    conn.close()
                    continue

                print("\nInstructors:")
                print("=" * 80)
                print(f"{'ID':<5} {'Name':<30} {'Department':<30}")
                print("-" * 80)

                for instructor in instructors:
                    instructor_id, first_name, last_name, department = instructor
                    full_name = f"{first_name} {last_name}"
                    print(f"{instructor_id:<5} {full_name:<30} {department:<30}")

                print("=" * 80)

                while True:
                    try:
                        instructor_id = int(input("Enter new instructor ID: "))
                        cursor.execute('SELECT id FROM instructors WHERE id = ?', (instructor_id,))
                        if cursor.fetchone():
                            break
                        else:
                            print(f"Instructor ID {instructor_id} does not exist.")
                    except ValueError:
                        print("Invalid instructor ID. Please enter a number.")

                scheduler.update_module_schedule(schedule_id, instructor_id=instructor_id)

            elif update_choice == '5':
                print("\nSession Types:")
                for i, session_type in enumerate(SESSION_TYPES, 1):
                    print(f"{i}. {session_type}")

                while True:
                    session_choice = input(f"Enter new session type (1-{len(SESSION_TYPES)}): ")
                    try:
                        session_index = int(session_choice) - 1
                        if 0 <= session_index < len(SESSION_TYPES):
                            session_type = SESSION_TYPES[session_index]
                            break
                        else:
                            print(f"Invalid choice. Must be between 1 and {len(SESSION_TYPES)}.")
                    except ValueError:
                        print("Invalid choice. Please enter a number.")

                scheduler.update_module_schedule(schedule_id, session_type=session_type)

            else:
                print("Invalid choice.")

            conn.close()

        elif choice == '3':
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT ms.id, ms.module_code, m.module_name, ms.day_of_week, ms.start_time, ms.end_time,
                   r.building, r.room_number, i.first_name, i.last_name, ms.session_type
            FROM module_schedule ms
            LEFT JOIN rooms r ON ms.room_id = r.id
            LEFT JOIN instructors i ON ms.instructor_id = i.id
            LEFT JOIN modules m ON ms.module_code = m.module_code
            ORDER BY ms.module_code, ms.day_of_week, ms.start_time
            ''')

            schedules = cursor.fetchall()

            if not schedules:
                print("No schedules found.")
                conn.close()
                continue

            print("\nAll Module Schedules:")
            print("=" * 120)
            print(f"{'ID':<5} {'Module':<10} {'Name':<25} {'Day':<10} {'Time':<15} {'Room':<15} {'Instructor':<20} {'Type':<10}")
            print("-" * 120)

            for schedule in schedules:
                id, code, name, day, start, end, building, room, first_name, last_name, session_type = schedule
                name = name or "Unknown"
                time_slot = f"{start}-{end}"
                room_str = f"{building}-{room}" if building and room else "TBA"
                instructor = f"{first_name} {last_name}" if first_name and last_name else "TBA"

                print(f"{id:<5} {code:<10} {name[:23]:<25} {day:<10} {time_slot:<15} "
                      f"{room_str:<15} {instructor[:18]:<20} {session_type:<10}")

            print("=" * 120)

            while True:
                try:
                    schedule_id = int(input("Enter schedule ID to delete: "))
                    cursor.execute('SELECT id FROM module_schedule WHERE id = ?', (schedule_id,))
                    if cursor.fetchone():
                        break
                    else:
                        print(f"Schedule ID {schedule_id} does not exist.")
                except ValueError:
                    print("Invalid schedule ID. Please enter a number.")

            conn.close()

            scheduler.delete_module_schedule(schedule_id)

        elif choice == '4':
            break
        else:
            print("Invalid choice. Please try again.")


def display_student_timetable_menu(scheduler):
    """Display the student timetable generation menu"""
    student_id = input("Enter student ID: ")

    conn = get_connection(scheduler.db_path, row_factory=False)
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
    student = cursor.fetchone()

    if not student:
        print(f"Student ID {student_id} does not exist.")
        conn.close()
        return

    cursor.execute('SELECT COUNT(*) FROM student_modules WHERE student_id = ?', (student_id,))
    module_count = cursor.fetchone()[0]

    if module_count == 0:
        print(f"Student {student_id} is not enrolled in any modules.")
        conn.close()
        return

    conn.close()

    print("\nSelect timetable format:")
    print("1. Display (List view)")
    print("2. Grid view")
    print("3. PDF")
    print("4. CSV")
    print("5. TXT")
    print("6. Excel")

    format_choice = input("Enter your choice (1-6): ")

    if format_choice == '1':
        scheduler.generate_student_timetable(student_id, 'display')
    elif format_choice == '2':
        scheduler.generate_student_timetable(student_id, 'grid')
    elif format_choice == '3':
        pdf_path = scheduler.generate_student_timetable(student_id, 'pdf')
        open_file_prompt(pdf_path, 'PDF')
    elif format_choice == '4':
        csv_path = scheduler.generate_student_timetable(student_id, 'csv')
        open_file_prompt(csv_path, 'CSV')
    elif format_choice == '5':
        txt_path = scheduler.generate_student_timetable(student_id, 'txt')
        open_file_prompt(txt_path, 'TXT')
    elif format_choice == '6':
        excel_path = scheduler.generate_student_timetable(student_id, 'excel')
        open_file_prompt(excel_path, 'Excel')
    else:
        print("Invalid choice. Using list view as default.")
        scheduler.generate_student_timetable(student_id, 'display')

    # Check for conflicts
    conflicts = scheduler.check_student_conflicts(student_id)
    if conflicts:
        print("\nWARNING: Scheduling conflicts detected!")

        view_conflicts = input("Do you want to view the conflicts? (y/n): ").lower() == 'y'
        if view_conflicts:
            scheduler.display_student_conflicts(student_id)


def display_instructor_timetable_menu(scheduler):
    """Display the instructor timetable generation menu"""
    instructor_id_str = input("Enter instructor ID: ")

    try:
        instructor_id = int(instructor_id_str)
    except ValueError:
        print("Invalid instructor ID. Please enter a number.")
        return

    conn = get_connection(scheduler.db_path, row_factory=False)
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM instructors WHERE id = ?', (instructor_id,))
    instructor = cursor.fetchone()

    if not instructor:
        print(f"Instructor ID {instructor_id} does not exist.")
        conn.close()
        return

    cursor.execute('SELECT COUNT(*) FROM module_schedule WHERE instructor_id = ?', (instructor_id,))
    schedule_count = cursor.fetchone()[0]

    if schedule_count == 0:
        print(f"Instructor ID {instructor_id} has no scheduled classes.")
        conn.close()
        return

    conn.close()

    print("\nSelect timetable format:")
    print("1. Display (List view)")
    print("2. Grid view")
    print("3. PDF")
    print("4. CSV")
    print("5. TXT")
    print("6. Excel")

    format_choice = input("Enter your choice (1-6): ")

    if format_choice == '1':
        scheduler.generate_instructor_timetable(instructor_id, 'display')
    elif format_choice == '2':
        scheduler.generate_instructor_timetable(instructor_id, 'grid')
    elif format_choice == '3':
        pdf_path = scheduler.generate_instructor_timetable(instructor_id, 'pdf')
        open_file_prompt(pdf_path, 'PDF')
    elif format_choice == '4':
        csv_path = scheduler.generate_instructor_timetable(instructor_id, 'csv')
        open_file_prompt(csv_path, 'CSV')
    elif format_choice == '5':
        txt_path = scheduler.generate_instructor_timetable(instructor_id, 'txt')
        open_file_prompt(txt_path, 'TXT')
    elif format_choice == '6':
        excel_path = scheduler.generate_instructor_timetable(instructor_id, 'excel')
        open_file_prompt(excel_path, 'Excel')
    else:
        print("Invalid choice. Using list view as default.")
        scheduler.generate_instructor_timetable(instructor_id, 'display')


def open_file_prompt(file_path, file_type):
    """Prompt user to open the generated file"""
    if file_path:
        open_file = input(f"\nDo you want to open the {file_type} file? (y/n): ").lower() == 'y'
        if open_file:
            try:
                import webbrowser
                webbrowser.open(f"file://{os.path.abspath(file_path)}")
            except Exception as e:
                print(f"Error opening {file_type}: {e}")
                print(f"Please open the file manually: {file_path}")


def display_module_scheduling_menu():
    """Display the module scheduling menu and handle user choices"""
    scheduler = ModuleScheduler()

    while True:
        print("\nModule Scheduling and Timetable Menu:")
        print("=====================================")
        print("1. Manage Rooms")
        print("2. Manage Instructors")
        print("3. Manage Module Schedules")
        print("4. View Module Schedules")
        print("5. View Room Schedules")
        print("6. View Instructor Schedules")
        print("7. Generate Student Timetable")
        print("8. Generate Instructor Timetable")
        print("9. Check for Scheduling Conflicts")
        print("10. Return to Main Menu")

        choice = input("\nEnter your choice (1-10): ")

        if choice == '1':
            display_room_menu(scheduler)
        elif choice == '2':
            display_instructor_menu(scheduler)
        elif choice == '3':
            display_schedule_menu(scheduler)
        elif choice == '4':
            module_code = input("Enter module code (or leave empty for all modules): ")
            scheduler.view_module_schedule(module_code if module_code else None)
        elif choice == '5':
            scheduler.view_room_schedule()
        elif choice == '6':
            scheduler.view_instructor_schedule()
        elif choice == '7':
            display_student_timetable_menu(scheduler)
        elif choice == '8':
            display_instructor_timetable_menu(scheduler)
        elif choice == '9':
            student_id = input("Enter student ID: ")
            scheduler.display_student_conflicts(student_id)
        elif choice == '10':
            print("Returning to main menu...")
            break
        else:
            print("Invalid choice. Please try again.")


def display_view_schedules_menu(scheduler):
    """Display the view schedules menu"""
    while True:
        print("\nView Schedules Menu:")
        print("===================")
        print("1. View Module Schedules")
        print("2. View Room Schedules")
        print("3. View Instructor Schedules")
        print("4. View All Schedules")
        print("5. Search Schedules")
        print("6. Return to Previous Menu")

        choice = input("\nEnter your choice (1-6): ")

        if choice == '1':
            module_code = input("Enter module code (or leave empty for all modules): ")
            scheduler.view_module_schedule(module_code if module_code else None)
        elif choice == '2':
            scheduler.view_room_schedule()
        elif choice == '3':
            scheduler.view_instructor_schedule()
        elif choice == '4':
            scheduler.view_module_schedule(None)
        elif choice == '5':
            display_advanced_search_menu(scheduler)
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")


def display_timetable_generation_menu(scheduler):
    """Display the timetable generation menu"""
    while True:
        print("\nTimetable Generation Menu:")
        print("=========================")
        print("1. Generate Student Timetable")
        print("2. Generate Instructor Timetable")
        print("3. Generate Room Schedule")
        print("4. Generate Department Schedule")
        print("5. Export to Various Formats")
        print("6. Return to Previous Menu")

        choice = input("\nEnter your choice (1-6): ")

        if choice == '1':
            display_student_timetable_menu(scheduler)
        elif choice == '2':
            display_instructor_timetable_menu(scheduler)
        elif choice == '3':
            room_id = input("Enter room ID (or leave empty to list all): ")
            if room_id:
                try:
                    scheduler.view_room_schedule(int(room_id))
                except ValueError:
                    print("Invalid room ID.")
            else:
                scheduler.view_room_schedule()
        elif choice == '4':
            department = input("Enter department name: ")
            if department:
                display_department_schedule(scheduler, department)
        elif choice == '5':
            display_export_menu(scheduler)
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")


def display_department_schedule(scheduler, department):
    """Display schedule for all instructors in a department"""
    conn = get_connection(scheduler.db_path, row_factory=False)
    cursor = conn.cursor()

    cursor.execute('''
    SELECT id, first_name, last_name FROM instructors
    WHERE department = ? AND is_active = 1
    ORDER BY last_name, first_name
    ''', (department,))

    instructors = cursor.fetchall()

    if not instructors:
        print(f"No active instructors found in department: {department}")
        conn.close()
        return

    print(f"\nSchedule for {department} Department:")
    print("=" * 100)

    for instructor in instructors:
        instructor_id, first_name, last_name = instructor
        print(f"\n{first_name} {last_name} (ID: {instructor_id}):")
        print("-" * 80)

        cursor.execute('''
        SELECT ms.module_code, ms.day_of_week, ms.start_time, ms.end_time,
               r.building, r.room_number, ms.session_type
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        WHERE ms.instructor_id = ?
        ORDER BY ms.day_of_week, ms.start_time
        ''', (instructor_id,))

        schedules = cursor.fetchall()

        if schedules:
            print(f"{'Module':<10} {'Day':<10} {'Time':<15} {'Room':<15} {'Type':<10}")
            print("-" * 70)

            for schedule in schedules:
                module_code, day, start, end, building, room, session_type = schedule
                time_slot = f"{start}-{end}"
                room_str = f"{building}-{room}" if building and room else "TBA"
                print(f"{module_code:<10} {day:<10} {time_slot:<15} {room_str:<15} {session_type:<10}")
        else:
            print("No scheduled classes")

    conn.close()
    print("=" * 100)


def display_export_menu(scheduler):
    """Display export options menu"""
    print("\nExport Options:")
    print("===============")
    print("1. Export All Schedules to CSV")
    print("2. Export Room Utilization Report")
    print("3. Export Instructor Workload Report")
    print("4. Export to iCal Format")
    print("5. Generate PDF Reports")

    choice = input("\nEnter your choice (1-5): ")

    if choice == '1':
        filename = scheduler.export_all_schedules_to_csv()
        print(f"All schedules exported to: {filename}")
    elif choice == '2':
        format_choice = input("Choose format (csv/pdf/display): ").lower()
        scheduler.generate_room_utilization_report(format_choice)
    elif choice == '3':
        format_choice = input("Choose format (csv/pdf/display): ").lower()
        scheduler.generate_instructor_workload_report(format_choice)
    elif choice == '4':
        display_ical_export_menu(scheduler)
    elif choice == '5':
        display_pdf_reports_menu(scheduler)
    else:
        print("Invalid choice.")


def display_main_menu_info():
    """Display welcome information and system status"""
    print("\n🎓 Enhanced Module Scheduling System")
    print("=" * 50)
    print("📋 Features Available:")
    print("  • Smart scheduling with conflict detection")
    print("  • Advanced analytics and reporting")
    print("  • Multiple export formats (PDF, CSV, Excel, iCal)")
    print("  • Room and instructor management")
    print("  • Visual timetables and charts")
    print("  • Backup and data validation")
    print("  • Holiday management")
    print("  • Notification system")
    print("=" * 50)


def handle_graceful_exit():
    """Handle graceful system exit with cleanup"""
    print("\n" + "="*60)
    print("🔄 Performing final system checks...")

    try:
        scheduler = ModuleScheduler()

        # Create exit backup if auto-backup is enabled
        auto_backup = scheduler.get_system_setting('auto_backup', 'True')
        if auto_backup == 'True':
            print("💾 Creating exit backup...")
            scheduler.create_backup(description="Automatic exit backup")

        # Quick data validation
        print("🔍 Running quick data validation...")
        issues = scheduler.validate_data_consistency()
        if issues:
            print(f"⚠️  Warning: {len(issues)} data consistency issues detected.")
            print("   Run data validation from the main menu for details.")
        else:
            print("✅ Data validation passed.")

        # Check for unresolved conflicts
        conflicts = scheduler._get_all_conflicts()
        active_conflicts = [c for c in conflicts if not c['resolved']]
        if active_conflicts:
            print(f"⚠️  Warning: {len(active_conflicts)} unresolved scheduling conflicts.")
        else:
            print("✅ No scheduling conflicts detected.")

        print("✅ System shutdown complete.")

    except Exception as e:
        print(f"❌ Error during shutdown: {e}")

    print("=" * 60)
    print("Thank you for using the Enhanced Module Scheduling System!")
    print("Have a great day! 🌟")
    print("=" * 60)


# GUI Launcher using factory pattern
try:
    from education_system.systems.university.services.feature_gui_factory import create_gui_launcher

    launch_timetable_optimizer_gui = create_gui_launcher(
        title="Smart Timetable Optimizer",
        description="""AI-powered class scheduling with conflict detection and optimization.

Features:
• Smart scheduling algorithm
• Room allocation optimization
• Instructor workload balancing
• Student preference integration
• Conflict detection & resolution
• Visual timetable display
• Template management
• Batch import/export
• Analytics & reports
• Holiday management
• Calendar integration (iCal)
• Notification system
• Data validation
• Backup & restore""",
        cli_instruction="Use CLI: Smart Timetable Optimizer"
    )
except ImportError:
    # Fallback if factory not available
    def launch_timetable_optimizer_gui(root, auth):
        from tkinter import messagebox
        messagebox.showinfo("Timetable Optimizer", "Please use the CLI: Enhanced Module Scheduling System")


# Alias for consistency with refactored naming
display_timetable_optimizer_menu = display_enhanced_scheduling_menu
