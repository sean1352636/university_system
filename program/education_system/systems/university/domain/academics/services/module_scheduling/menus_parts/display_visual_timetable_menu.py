"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


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
