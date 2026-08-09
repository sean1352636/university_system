"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


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
