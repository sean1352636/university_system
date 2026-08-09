"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


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
