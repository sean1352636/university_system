"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


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
