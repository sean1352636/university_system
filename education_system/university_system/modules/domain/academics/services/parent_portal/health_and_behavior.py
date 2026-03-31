from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from education_system.university_system.infrastructure.email import send_email
import datetime


class HealthAndBehaviorMixin:
    def report_absence(self):
        """Report a student absence"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to report an absence.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        if not self.auth.check_permission('report_absence'):
            print("You don't have permission to report absences.")
            return

        children = self.view_children()

        if not children:
            print("You have no children registered in the system.")
            return

        print("\nSelect the child to report absent:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]}, Course: {child[4]})")

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

                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student_absences'")
                if not cursor.fetchone():
                    cursor.execute('''
                    CREATE TABLE IF NOT EXISTS student_absences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT,
                        absence_date TEXT,
                        return_date TEXT,
                        reason TEXT,
                        reported_by TEXT,
                        reported_date TEXT,
                        notes TEXT,
                        FOREIGN KEY (student_id) REFERENCES students (student_id)
                    )
                    ''')

                print("\nReport Absence:")

                while True:
                    absence_date_str = input("Absence date (YYYY-MM-DD) or 'today': ")
                    if absence_date_str.lower() == 'today':
                        absence_date = datetime.datetime.now().strftime('%Y-%m-%d')
                        break
                    try:
                        absence_date = datetime.datetime.strptime(absence_date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
                        break
                    except ValueError:
                        print("Invalid date format. Please use YYYY-MM-DD.")

                while True:
                    return_date_str = input("Expected return date (YYYY-MM-DD) or press Enter if unknown: ")
                    if not return_date_str:
                        return_date = None
                        break
                    try:
                        return_date = datetime.datetime.strptime(return_date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
                        break
                    except ValueError:
                        print("Invalid date format. Please use YYYY-MM-DD.")

                reason = input("Reason for absence: ")
                if not reason:
                    print("A reason must be provided.")
                    return

                notes = input("Additional notes (optional): ")

                parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
                if not parent_id:
                    print("Error retrieving parent ID.")
                    return

                reported_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute(
                    'INSERT INTO student_absences (student_id, absence_date, return_date, reason, reported_by, reported_date, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (student_id, absence_date, return_date, reason, f"parent:{parent_id}", reported_date, notes)
                )

                conn.commit()
                print("Absence reported successfully.")

                notify = input("Would you like to notify the student's teachers? (y/n): ")
                if notify.lower() == 'y':
                    try:
                        cursor.execute('''
                        CREATE TABLE IF NOT EXISTS parent_messages (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            parent_id TEXT,
                            teacher_id INTEGER,
                            student_id TEXT,
                            message_content TEXT,
                            created_date TEXT,
                            is_read BOOLEAN DEFAULT 0,
                            is_from_parent BOOLEAN DEFAULT 1,
                            message_type TEXT DEFAULT 'individual',
                            group_id TEXT,
                            FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id),
                            FOREIGN KEY (teacher_id) REFERENCES users (id),
                            FOREIGN KEY (student_id) REFERENCES students (student_id)
                        )
                        ''')

                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='module_teachers'")
                        if not cursor.fetchone():
                            print("Module-teacher assignments not yet set up. Cannot notify teachers.")
                            return

                        cursor.execute('''
                        SELECT DISTINCT t.id, t.username, t.email
                        FROM student_modules sm
                        JOIN module_teachers mt ON sm.module_code = mt.module_code
                        JOIN users t ON mt.teacher_id = t.id
                        WHERE sm.student_id = ? AND t.role = 'teacher'
                        ''', (student_id,))

                        teachers = cursor.fetchall()

                        if teachers:
                            message = f"Student {selected_child[1]} {selected_child[3]} (ID: {student_id}) will be absent on {absence_date} due to {reason}."
                            if return_date:
                                message += f" Expected return date: {return_date}."
                            if notes:
                                message += f" Additional notes: {notes}"

                            for teacher in teachers:
                                try:
                                    cursor.execute(
                                        'INSERT INTO parent_messages (parent_id, teacher_id, student_id, message_content, created_date, is_read, is_from_parent) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                        (parent_id, teacher[0], student_id, message, reported_date, 0, 1)
                                    )

                                    if teacher[2]:
                                        try:
                                            send_email(
                                                teacher[2],
                                                f"Absence Notification: {selected_child[1]} {selected_child[3]}",
                                                message
                                            )
                                        except Exception as e:
                                            print(f"Could not send email to {teacher[1]}: {e}")
                                except Exception as e:
                                    print(f"Error notifying teacher {teacher[1]}: {e}")

                            conn.commit()
                            print("Teachers have been notified.")
                        else:
                            print("No teachers found to notify.")
                    except sqlite3.Error as e:
                        print(f"Error notifying teachers: {e}")
                        conn.rollback()

            except sqlite3.Error as e:
                print(f"Database error reporting absence: {e}")
                if conn:
                    conn.rollback()
            finally:
                if conn:
                    conn.close()

        except (ValueError, IndexError):
            print("Invalid choice.")

    def view_behavior_reports(self):
        """View behavior incidents and positive reports"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view behavior reports.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        if not self.auth.check_permission('view_behavior_reports'):
            print("You don't have permission to view behavior reports.")
            return

        children = self.view_children()

        if not children:
            print("You have no children registered in the system.")
            return

        print("\nSelect child to view behavior reports:")
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

                # Get behavior reports
                cursor.execute('''
                SELECT incident_date, behavior_type, severity, description, action_taken, reported_by, resolved
                FROM student_behavior
                WHERE student_id = ?
                ORDER BY incident_date DESC
                ''', (student_id,))

                reports = cursor.fetchall()

                if not reports:
                    print(f"No behavior reports found for {selected_child[1]} {selected_child[3]}.")
                    return

                print(f"\nBehavior Reports for {selected_child[1]} {selected_child[3]}:")

                positive_reports = [r for r in reports if r[2] == 'positive']
                negative_reports = [r for r in reports if r[2] in ['minor', 'major', 'severe']]

                if positive_reports:
                    print("\nPositive Behavior Reports:")
                    for report in positive_reports:
                        date, behavior_type, severity, description, action, reporter, resolved = report
                        print(f"- {date}: {behavior_type}")
                        print(f"  {description}")
                        if action:
                            print(f"  Recognition: {action}")
                        print(f"  Reported by: {reporter}")
                        print()

                if negative_reports:
                    print("\nIncident Reports:")
                    for report in negative_reports:
                        date, behavior_type, severity, description, action, reporter, resolved = report
                        status = "Resolved" if resolved else "Open"
                        print(f"- {date}: {behavior_type} ({severity.upper()}) - {status}")
                        print(f"  {description}")
                        if action:
                            print(f"  Action taken: {action}")
                        print(f"  Reported by: {reporter}")
                        print()

                # Summary statistics
                total_positive = len(positive_reports)
                total_incidents = len(negative_reports)

                print(f"Summary: {total_positive} positive reports, {total_incidents} incidents")

            except sqlite3.Error as e:
                print(f"Database error viewing behavior reports: {e}")
            finally:
                if conn:
                    conn.close()

        except (ValueError, IndexError):
            print("Invalid choice.")

    def view_medical_information(self):
        """View and update medical information for children"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view medical information.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        if not self.auth.check_permission('manage_medical_info'):
            print("You don't have permission to view medical information.")
            return

        children = self.view_children()

        if not children:
            print("You have no children registered in the system.")
            return

        print("\nSelect child to view medical information:")
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

                # Get medical information
                cursor.execute('''
                SELECT condition_type, description, medication_name, dosage, administration_time,
                       emergency_contact, doctor_contact, expiry_date, notes
                FROM student_medical_info
                WHERE student_id = ?
                ORDER BY condition_type
                ''', (student_id,))

                medical_info = cursor.fetchall()

                print(f"\nMedical Information for {selected_child[1]} {selected_child[3]}:")

                if not medical_info:
                    print("No medical information on file.")
                else:
                    for info in medical_info:
                        condition, description, medication, dosage, admin_time, emergency, doctor, expiry, notes = info
                        print(f"\nCondition: {condition}")
                        print(f"Description: {description}")
                        if medication:
                            print(f"Medication: {medication}")
                            print(f"Dosage: {dosage}")
                            print(f"Administration time: {admin_time}")
                            if expiry:
                                print(f"Expires: {expiry}")
                        if emergency:
                            print(f"Emergency contact: {emergency}")
                        if doctor:
                            print(f"Doctor contact: {doctor}")
                        if notes:
                            print(f"Notes: {notes}")
                        print("-" * 40)

                print("\nOptions:")
                print("1. Add medical condition/medication")
                print("2. Update existing information")
                print("3. Back to menu")

                option = input("Select option: ")

                if option == '1':
                    print("\nAdd Medical Information:")
                    condition_type = input("Condition type (allergy/medication/condition): ")
                    description = input("Description: ")
                    medication = input("Medication name (if applicable): ")
                    dosage = input("Dosage (if applicable): ")
                    admin_time = input("Administration time (if applicable): ")
                    emergency = input("Emergency contact: ")
                    doctor = input("Doctor contact: ")
                    expiry = input("Expiry date (YYYY-MM-DD, if applicable): ")
                    notes = input("Additional notes: ")

                    cursor.execute('''
                    INSERT INTO student_medical_info
                    (student_id, condition_type, description, medication_name, dosage,
                     administration_time, emergency_contact, doctor_contact, expiry_date, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (student_id, condition_type, description, medication, dosage,
                          admin_time, emergency, doctor, expiry, notes))

                    conn.commit()
                    print("Medical information added successfully.")

            except sqlite3.Error as e:
                print(f"Database error viewing medical information: {e}")
            finally:
                if conn:
                    conn.close()

        except (ValueError, IndexError):
            print("Invalid choice.")
