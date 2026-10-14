"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


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
        timetable_reports_dir = paths.UNIVERSITY_REPORTS_DIR / 'timetable_reports'
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
