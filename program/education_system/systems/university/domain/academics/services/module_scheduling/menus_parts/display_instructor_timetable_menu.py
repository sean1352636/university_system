"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


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
