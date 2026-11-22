"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


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
