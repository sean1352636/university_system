from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager
from education_system.university_system.core.paths import DEFAULT_DB_PATH
import datetime


class ServicesMixin:
    def view_transportation_info(self):
        """View transportation information and routes"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view transportation information.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        if not self.auth.check_permission('view_transportation'):
            print("You don't have permission to view transportation information.")
            return

        children = self.view_children()

        if not children:
            print("You have no children registered in the system.")
            return

        print("\nSelect child to view transportation information:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")

        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError

            selected_child = children[index]
            student_id = selected_child[0]

            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()

                # Get transportation information
                cursor.execute('''
                SELECT route_name, bus_number, pickup_time, dropoff_time, pickup_location,
                       dropoff_location, driver_name, driver_phone, active
                FROM transportation
                WHERE student_id = ? AND active = 1
                ''', (student_id,))

                transport_info = cursor.fetchall()

                print(f"\nTransportation Information for {selected_child[1]} {selected_child[3]}:")

                if not transport_info:
                    print("No transportation arrangements on file.")
                else:
                    for info in transport_info:
                        route, bus_num, pickup_time, dropoff_time, pickup_loc, dropoff_loc, driver, driver_phone, active = info
                        print(f"\nRoute: {route}")
                        print(f"Bus Number: {bus_num}")
                        print(f"Pickup Time: {pickup_time}")
                        print(f"Pickup Location: {pickup_loc}")
                        print(f"Dropoff Time: {dropoff_time}")
                        print(f"Dropoff Location: {dropoff_loc}")
                        print(f"Driver: {driver}")
                        if driver_phone:
                            print(f"Driver Phone: {driver_phone}")

            except sqlite3.Error as e:
                print(f"Database error viewing transportation information: {e}")
            finally:
                if conn:
                    conn.close()

        except (ValueError, IndexError):
            print("Invalid choice.")

    def view_library_account(self):
        """View library account and borrowed books"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view library information.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        if not self.auth.check_permission('view_library_account'):
            print("You don't have permission to view library accounts.")
            return

        children = self.view_children()

        if not children:
            print("You have no children registered in the system.")
            return

        print("\nSelect child to view library account:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")

        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError

            selected_child = children[index]
            student_id = selected_child[0]

            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()

                # Get currently borrowed books
                cursor.execute('''
                SELECT book_title, author, checkout_date, due_date, fine_amount, status
                FROM library_accounts
                WHERE student_id = ? AND status = 'checked_out'
                ORDER BY due_date
                ''', (student_id,))

                current_books = cursor.fetchall()

                # Get recently returned books
                cursor.execute('''
                SELECT book_title, author, checkout_date, return_date, fine_amount
                FROM library_accounts
                WHERE student_id = ? AND status = 'returned'
                ORDER BY return_date DESC
                LIMIT 5
                ''', (student_id,))

                returned_books = cursor.fetchall()

                # Calculate total fines
                cursor.execute('''
                SELECT SUM(fine_amount)
                FROM library_accounts
                WHERE student_id = ? AND fine_amount > 0
                ''', (student_id,))

                total_fines = cursor.fetchone()[0] or 0

                print(f"\nLibrary Account for {selected_child[1]} {selected_child[3]}:")

                if current_books:
                    print("\nCurrently Borrowed Books:")
                    for book in current_books:
                        title, author, checkout_date, due_date, fine, status = book
                        print(f"- {title} by {author}")
                        print(f"  Checked out: {checkout_date}")
                        print(f"  Due: {due_date}")
                        if fine > 0:
                            print(f"  Fine: £{fine:.2f}")

                        # Check if overdue
                        today = datetime.datetime.now().strftime('%Y-%m-%d')
                        if due_date < today:
                            print("  STATUS: OVERDUE")
                        print()
                else:
                    print("\nNo books currently borrowed.")

                if total_fines > 0:
                    print(f"\nTotal Outstanding Fines: £{total_fines:.2f}")

                if returned_books:
                    print("\nRecently Returned Books:")
                    for book in returned_books:
                        title, author, checkout_date, return_date, fine = book
                        print(f"- {title} by {author}")
                        print(f"  Returned: {return_date}")
                        if fine > 0:
                            print(f"  Fine paid: £{fine:.2f}")
                        print()

            except sqlite3.Error as e:
                print(f"Database error viewing library account: {e}")
            finally:
                if conn:
                    conn.close()

        except (ValueError, IndexError):
            print("Invalid choice.")

    def view_extracurricular_activities(self):
        """View and manage extracurricular activities"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view extracurricular activities.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        if not self.auth.check_permission('view_extracurricular'):
            print("You don't have permission to view extracurricular activities.")
            return

        children = self.view_children()

        if not children:
            print("You have no children registered in the system.")
            return

        print("\nSelect child to view activities:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]})")

        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError

            selected_child = children[index]
            student_id = selected_child[0]

            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()

                # Get enrolled activities
                cursor.execute('''
                SELECT ea.activity_name, ea.description, ea.supervisor, ea.meeting_schedule,
                       ea.location, ea.fee, sa.enrollment_date, sa.status
                FROM student_activities sa
                JOIN extracurricular_activities ea ON sa.activity_id = ea.id
                WHERE sa.student_id = ? AND sa.status = 'active'
                ORDER BY ea.activity_name
                ''', (student_id,))

                enrolled_activities = cursor.fetchall()

                # Get available activities
                cursor.execute('''
                SELECT ea.id, ea.activity_name, ea.description, ea.supervisor, ea.meeting_schedule,
                       ea.location, ea.fee, ea.max_participants
                FROM extracurricular_activities ea
                WHERE ea.status = 'active'
                AND ea.id NOT IN (
                    SELECT activity_id FROM student_activities
                    WHERE student_id = ? AND status = 'active'
                )
                ORDER BY ea.activity_name
                ''', (student_id,))

                available_activities = cursor.fetchall()

                print(f"\nExtracurricular Activities for {selected_child[1]} {selected_child[3]}:")

                if enrolled_activities:
                    print("\nEnrolled Activities:")
                    for activity in enrolled_activities:
                        name, description, supervisor, schedule, location, fee, enrollment_date, status = activity
                        print(f"- {name}")
                        print(f"  Description: {description}")
                        print(f"  Supervisor: {supervisor}")
                        print(f"  Schedule: {schedule}")
                        print(f"  Location: {location}")
                        if fee > 0:
                            print(f"  Fee: £{fee:.2f}")
                        print(f"  Enrolled: {enrollment_date}")
                        print()
                else:
                    print("\nNot enrolled in any activities.")

                if available_activities:
                    print("\nAvailable Activities:")
                    for activity in available_activities:
                        id, name, description, supervisor, schedule, location, fee, max_participants = activity
                        print(f"- {name}")
                        print(f"  Description: {description}")
                        print(f"  Supervisor: {supervisor}")
                        print(f"  Schedule: {schedule}")
                        print(f"  Location: {location}")
                        if fee > 0:
                            print(f"  Fee: £{fee:.2f}")
                        print()

            except sqlite3.Error as e:
                print(f"Database error viewing activities: {e}")
            finally:
                if conn:
                    conn.close()

        except (ValueError, IndexError):
            print("Invalid choice.")
