from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
import datetime


class AcademicsMixin:
    def view_child_grades(self):
        """View grades for a child of the logged-in parent"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view your child's grades.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        if not self.auth.check_permission('view_child_grades'):
            print("You don't have permission to view grades.")
            return

        children = self.view_children()

        if not children:
            print("You have no children registered in the system.")
            return

        print("\nYour children:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]}, Course: {child[4]})")

        choice = input("Enter the number of the child whose grades you want to view: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError

            selected_child = children[index]

            if selected_child[6] == 'minimal':
                print("You have minimal access to this child's records and cannot view grades.")
                return

            student_id = selected_child[0]

            print(f"\nViewing grades for {selected_child[1]} {selected_child[3]}")

            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()

                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student_grades'")

                if not cursor.fetchone():
                    print("Grade tracking is not yet set up in the system.")
                    return

                cursor.execute('''
                SELECT m.module_code, m.module_name, g.assessment_name, g.grade, g.grade_date
                FROM student_modules sm
                JOIN modules m ON sm.module_code = m.module_code
                LEFT JOIN student_grades g ON sm.student_id = g.student_id AND sm.module_code = g.module_code
                WHERE sm.student_id = ?
                ORDER BY m.module_code, g.assessment_name
                ''', (student_id,))

                grades = cursor.fetchall()

                if not grades:
                    print("No grades recorded for this student.")
                    return

                current_module = None
                for grade in grades:
                    module_code, module_name, assessment_name, grade_value, grade_date = grade

                    if module_code != current_module:
                        print(f"\n{module_code}: {module_name}")
                        current_module = module_code

                    if assessment_name:
                        print(f"  - {assessment_name}: {grade_value} (Recorded: {grade_date})")
                    else:
                        print("  - No assessments recorded yet")

            except sqlite3.Error as e:
                print(f"Database error viewing grades: {e}")
            finally:
                if conn:
                    conn.close()

        except (ValueError, IndexError):
            print("Invalid choice.")

    def view_child_attendance(self):
        """View attendance records for a child of the logged-in parent"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view your child's attendance.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        if not self.auth.check_permission('view_child_attendance'):
            print("You don't have permission to view attendance records.")
            return

        children = self.view_children()

        if not children:
            print("You have no children registered in the system.")
            return

        print("\nYour children:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]}, Course: {child[4]})")

        choice = input("Enter the number of the child whose attendance you want to view: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError

            selected_child = children[index]
            student_id = selected_child[0]

            print(f"\nViewing attendance for {selected_child[1]} {selected_child[3]}")

            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()

                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='attendance'")

                if not cursor.fetchone():
                    print("Attendance tracking is not yet set up in the system.")
                    return

                cursor.execute('''
                SELECT m.module_code, m.module_name,
                       COUNT(a.id) as total_sessions,
                       SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) as attended_sessions
                FROM student_modules sm
                JOIN modules m ON sm.module_code = m.module_code
                LEFT JOIN attendance a ON sm.student_id = a.student_id AND sm.module_code = a.module_code
                WHERE sm.student_id = ?
                GROUP BY m.module_code, m.module_name
                ORDER BY m.module_code
                ''', (student_id,))

                module_attendance = cursor.fetchall()

                if not module_attendance or all(row[2] == 0 for row in module_attendance):
                    print("No attendance records found for this student.")
                else:
                    total_sessions = sum(row[2] for row in module_attendance)
                    total_attended = sum(row[3] for row in module_attendance)

                    if total_sessions > 0:
                        overall_percentage = (total_attended / total_sessions) * 100
                        print(f"\nOverall Attendance: {overall_percentage:.1f}% ({total_attended}/{total_sessions} sessions)")

                    print("\nAttendance by Module:")
                    for module in module_attendance:
                        module_code, module_name, total_sessions, attended_sessions = module

                        if total_sessions > 0:
                            percentage = (attended_sessions / total_sessions) * 100
                            print(f"{module_code}: {module_name}")
                            print(f"  {percentage:.1f}% ({attended_sessions}/{total_sessions} sessions)")

                cursor.execute('''
                SELECT a.date, m.module_code, m.module_name, a.status, a.reason
                FROM attendance a
                JOIN modules m ON a.module_code = m.module_code
                WHERE a.student_id = ? AND a.status != 'present'
                ORDER BY a.date DESC
                LIMIT 10
                ''', (student_id,))

                recent_absences = cursor.fetchall()

                if recent_absences:
                    print("\nRecent Absences:")
                    for absence in recent_absences:
                        date, module_code, module_name, status, reason = absence
                        print(f"{date} - {module_code}: {module_name} - {status.upper()}")
                        if reason:
                            print(f"  Reason: {reason}")

            except sqlite3.Error as e:
                print(f"Database error viewing attendance: {e}")
            finally:
                if conn:
                    conn.close()

        except (ValueError, IndexError):
            print("Invalid choice.")

    def view_teacher_reports(self):
        """View teacher reports for a child of the logged-in parent"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view teacher reports.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        if not self.auth.check_permission('view_teacher_reports'):
            print("You don't have permission to view teacher reports.")
            return

        children = self.view_children()

        if not children:
            print("You have no children registered in the system.")
            return

        print("\nYour children:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]}, Course: {child[4]})")

        choice = input("Enter the number of the child whose reports you want to view: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError

            selected_child = children[index]

            if selected_child[6] == 'minimal' or selected_child[6] == 'limited':
                print("You don't have sufficient access to view teacher reports for this child.")
                return

            student_id = selected_child[0]

            print(f"\nViewing teacher reports for {selected_child[1]} {selected_child[3]}")

            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()

                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='teacher_reports'")

                if not cursor.fetchone():
                    print("Teacher reporting is not yet set up in the system.")
                    return

                cursor.execute('''
                SELECT r.id, r.module_code, m.module_name, r.report_type, r.created_date, u.username as teacher_name
                FROM teacher_reports r
                JOIN modules m ON r.module_code = m.module_code
                LEFT JOIN users u ON r.teacher_id = u.id
                WHERE r.student_id = ?
                ORDER BY r.created_date DESC
                ''', (student_id,))

                reports = cursor.fetchall()

                if not reports:
                    print("No teacher reports found for this student.")
                    return

                print("\nAvailable Reports:")
                for i, report in enumerate(reports):
                    report_id, module_code, module_name, report_type, date, teacher = report
                    print(f"{i+1}. {date} - {module_code}: {report_type} by {teacher or 'Unknown Teacher'}")

                report_choice = input("\nEnter the number of the report you want to view (or 0 to go back): ")

                if report_choice == '0':
                    return

                try:
                    report_index = int(report_choice) - 1
                    if report_index < 0 or report_index >= len(reports):
                        raise ValueError

                    selected_report = reports[report_index]
                    report_id = selected_report[0]

                    cursor.execute('SELECT report_content FROM teacher_reports WHERE id = ?', (report_id,))
                    report_content = cursor.fetchone()[0]

                    print("\n" + "=" * 50)
                    print(f"REPORT: {selected_report[3]}")
                    print(f"Module: {selected_report[1]} - {selected_report[2]}")
                    print(f"Date: {selected_report[4]}")
                    print(f"Teacher: {selected_report[5] or 'Unknown'}")
                    print("=" * 50)
                    print(report_content)
                    print("=" * 50)

                except (ValueError, IndexError):
                    print("Invalid report choice.")

            except sqlite3.Error as e:
                print(f"Database error viewing teacher reports: {e}")
            finally:
                if conn:
                    conn.close()

        except (ValueError, IndexError):
            print("Invalid choice.")

    def view_child_timetable(self):
        """View a child's weekly timetable"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view your child's timetable.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        if not self.auth.check_permission('view_child_timetable'):
            print("You don't have permission to view timetables.")
            return

        children = self.view_children()

        if not children:
            print("You have no children registered in the system.")
            return

        print("\nSelect the child whose timetable you want to view:")
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

                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='class_schedule'")

                if not cursor.fetchone():
                    print("Timetable functionality is not yet set up in the system.")
                    return

                cursor.execute('''
                SELECT cs.day_of_week, cs.start_time, cs.end_time, cs.room_number, m.module_code, m.module_name
                FROM class_schedule cs
                JOIN student_modules sm ON cs.module_code = sm.module_code
                JOIN modules m ON sm.module_code = m.module_code
                WHERE sm.student_id = ?
                ORDER BY
                    CASE cs.day_of_week
                        WHEN 'Monday' THEN 1
                        WHEN 'Tuesday' THEN 2
                        WHEN 'Wednesday' THEN 3
                        WHEN 'Thursday' THEN 4
                        WHEN 'Friday' THEN 5
                        WHEN 'Saturday' THEN 6
                        WHEN 'Sunday' THEN 7
                    END,
                    cs.start_time
                ''', (student_id,))

                timetable = cursor.fetchall()

                if not timetable:
                    print("No timetable information found for this student.")
                    return

                print(f"\nTimetable for {selected_child[1]} {selected_child[3]}:")

                current_day = None
                for entry in timetable:
                    day, start_time, end_time, room, module_code, module_name = entry

                    if day != current_day:
                        print(f"\n{day}:")
                        current_day = day

                    print(f"  {start_time} - {end_time}: {module_code} ({module_name}) in Room {room}")

            except sqlite3.Error as e:
                print(f"Database error viewing timetable: {e}")
            finally:
                if conn:
                    conn.close()

        except (ValueError, IndexError):
            print("Invalid choice.")

    def view_child_assignments(self):
        """View a child's upcoming and overdue assignments"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view your child's assignments.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        if not self.auth.check_permission('view_child_assignments'):
            print("You don't have permission to view assignments.")
            return

        children = self.view_children()

        if not children:
            print("You have no children registered in the system.")
            return

        print("\nSelect the child whose assignments you want to view:")
        for i, child in enumerate(children):
            print(f"{i+1}. {child[1]} {child[3]} (ID: {child[0]}, Course: {child[4]})")

        choice = input("Enter the number of the child: ")
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(children):
                raise ValueError

            selected_child = children[index]

            if selected_child[6] == 'minimal':
                print("You have minimal access and cannot view assignments for this child.")
                return

            student_id = selected_child[0]

            conn = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                conn.execute("PRAGMA busy_timeout = 30000")
                cursor = conn.cursor()

                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student_assignments'")

                if not cursor.fetchone():
                    print("Assignment tracking is not yet set up in the system.")
                    return

                today = datetime.datetime.now().strftime('%Y-%m-%d')

                cursor.execute('''
                SELECT sa.id, sa.title, sa.description, sa.due_date, m.module_code, m.module_name, sa.status
                FROM student_assignments sa
                JOIN modules m ON sa.module_code = m.module_code
                WHERE sa.student_id = ? AND sa.due_date >= ? AND sa.status != 'completed'
                ORDER BY sa.due_date
                ''', (student_id, today))

                upcoming = cursor.fetchall()

                cursor.execute('''
                SELECT sa.id, sa.title, sa.description, sa.due_date, m.module_code, m.module_name, sa.status
                FROM student_assignments sa
                JOIN modules m ON sa.module_code = m.module_code
                WHERE sa.student_id = ? AND sa.due_date < ? AND sa.status != 'completed'
                ORDER BY sa.due_date
                ''', (student_id, today))

                overdue = cursor.fetchall()

                cursor.execute('''
                SELECT sa.id, sa.title, sa.description, sa.due_date, m.module_code, m.module_name, sa.status
                FROM student_assignments sa
                JOIN modules m ON sa.module_code = m.module_code
                WHERE sa.student_id = ? AND sa.status = 'completed'
                ORDER BY sa.due_date DESC
                LIMIT 5
                ''', (student_id,))

                completed = cursor.fetchall()

                print(f"\nAssignments for {selected_child[1]} {selected_child[3]}:")

                if not upcoming and not overdue and not completed:
                    print("No assignments found for this student.")
                else:
                    if upcoming:
                        print("\nUpcoming Assignments:")
                        for assignment in upcoming:
                            id, title, description, due_date, module_code, module_name, status = assignment
                            print(f"- {title} ({module_code})")
                            print(f"  Due: {due_date}")
                            print(f"  Status: {status}")
                            if description:
                                print(f"  Description: {description}")
                            print()

                    if overdue:
                        print("\nOverdue Assignments:")
                        for assignment in overdue:
                            id, title, description, due_date, module_code, module_name, status = assignment
                            print(f"- {title} ({module_code})")
                            print(f"  Due: {due_date} (OVERDUE)")
                            print(f"  Status: {status}")
                            if description:
                                print(f"  Description: {description}")
                            print()

                    if completed:
                        print("\nRecently Completed Assignments:")
                        for assignment in completed:
                            id, title, description, due_date, module_code, module_name, status = assignment
                            print(f"- {title} ({module_code})")
                            print(f"  Due: {due_date}")
                            print(f"  Status: {status}")
                            print()

            except sqlite3.Error as e:
                print(f"Database error viewing assignments: {e}")
            finally:
                if conn:
                    conn.close()

        except (ValueError, IndexError):
            print("Invalid choice.")

    def view_school_calendar(self):
        """View school calendar events"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view the school calendar.")
            return

        if not self.auth.check_permission('view_school_calendar'):
            print("You don't have permission to view the school calendar.")
            return

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='school_calendar'")

            if not cursor.fetchone():
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS school_calendar (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_name TEXT,
                    event_description TEXT,
                    event_date TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    location TEXT,
                    event_type TEXT,
                    audience TEXT
                )
                ''')

                sample_events = [
                    ('Start of Fall Semester', 'First day of classes for the fall semester', '2023-09-04', '08:00', '17:00', 'All Campuses', 'academic', 'all'),
                    ('Parents Evening', 'Meet with teachers to discuss student progress', '2023-09-20', '17:00', '20:00', 'Main Hall', 'parent', 'parents'),
                    ('Midterm Exams Begin', 'First day of midterm examinations', '2023-10-16', '09:00', '17:00', 'Examination Halls', 'academic', 'all'),
                    ('Fall Break', 'No classes during fall break', '2023-11-23', '00:00', '23:59', 'All Campuses', 'holiday', 'all'),
                    ('End of Fall Semester', 'Last day of classes for the fall semester', '2023-12-15', '08:00', '17:00', 'All Campuses', 'academic', 'all')
                ]

                cursor.executemany(
                    'INSERT INTO school_calendar (event_name, event_description, event_date, start_time, end_time, location, event_type, audience) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    sample_events
                )

                conn.commit()

            today = datetime.datetime.now().strftime('%Y-%m-%d')

            print("\nCalendar View Options:")
            print("1. Upcoming Events")
            print("2. This Month's Events")
            print("3. All Events")
            print("4. Parent-Specific Events")

            view_choice = input("Select view option (1-4): ")

            if view_choice == '1':
                cursor.execute('''
                SELECT event_name, event_description, event_date, start_time, end_time, location, event_type
                FROM school_calendar
                WHERE event_date >= ?
                ORDER BY event_date, start_time
                LIMIT 10
                ''', (today,))
                print("\nUpcoming Events:")
            elif view_choice == '2':
                current_month = datetime.datetime.now().strftime('%Y-%m')
                cursor.execute('''
                SELECT event_name, event_description, event_date, start_time, end_time, location, event_type
                FROM school_calendar
                WHERE event_date LIKE ?
                ORDER BY event_date, start_time
                ''', (f"{current_month}%",))
                print(f"\nEvents for {datetime.datetime.now().strftime('%B %Y')}:")
            elif view_choice == '3':
                cursor.execute('''
                SELECT event_name, event_description, event_date, start_time, end_time, location, event_type
                FROM school_calendar
                ORDER BY event_date, start_time
                ''')
                print("\nAll Events:")
            elif view_choice == '4':
                cursor.execute('''
                SELECT event_name, event_description, event_date, start_time, end_time, location, event_type
                FROM school_calendar
                WHERE audience IN ('all', 'parents')
                ORDER BY event_date, start_time
                ''')
                print("\nParent-Related Events:")
            else:
                print("Invalid choice. Showing upcoming events.")
                cursor.execute('''
                SELECT event_name, event_description, event_date, start_time, end_time, location, event_type
                FROM school_calendar
                WHERE event_date >= ?
                ORDER BY event_date, start_time
                LIMIT 10
                ''', (today,))
                print("\nUpcoming Events:")

            events = cursor.fetchall()

            if not events:
                print("No events found for the selected view.")
            else:
                current_date = None

                for event in events:
                    name, description, date, start, end, location, type = event

                    if date != current_date:
                        day_name = datetime.datetime.strptime(date, '%Y-%m-%d').strftime('%A')
                        print(f"\n{date} ({day_name}):")
                        current_date = date

                    print(f"  {start} - {end}: {name}")
                    print(f"  Location: {location}")
                    print(f"  Type: {type}")
                    if description:
                        print(f"  Description: {description}")
                    print()

        except sqlite3.Error as e:
            print(f"Database error viewing calendar: {e}")
        finally:
            if conn:
                conn.close()

    def view_school_announcements(self):
        """View school announcements"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view announcements.")
            return

        if not self.auth.check_permission('view_announcements'):
            print("You don't have permission to view announcements.")
            return

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            today = datetime.datetime.now().strftime('%Y-%m-%d')

            # Get unread announcements
            cursor.execute('''
            SELECT sa.id, sa.title, sa.content, sa.priority, sa.category, sa.created_date, sa.requires_acknowledgment
            FROM school_announcements sa
            WHERE sa.audience IN ('all', 'parents')
            AND (sa.expiry_date IS NULL OR sa.expiry_date >= ?)
            AND sa.id NOT IN (
                SELECT announcement_id FROM announcement_reads
                WHERE parent_id = ?
            )
            ORDER BY sa.priority DESC, sa.created_date DESC
            ''', (today, parent_id))

            unread_announcements = cursor.fetchall()

            # Get recent read announcements
            cursor.execute('''
            SELECT sa.id, sa.title, sa.content, sa.priority, sa.category, sa.created_date, ar.read_date
            FROM school_announcements sa
            JOIN announcement_reads ar ON sa.id = ar.announcement_id
            WHERE ar.parent_id = ?
            ORDER BY ar.read_date DESC
            LIMIT 5
            ''', (parent_id,))

            read_announcements = cursor.fetchall()

            print("\nSchool Announcements:")

            if unread_announcements:
                print("\nNew Announcements:")
                for announcement in unread_announcements:
                    id, title, content, priority, category, created_date, requires_ack = announcement
                    priority_text = f" ({priority.upper()})" if priority != 'normal' else ""
                    ack_text = " [REQUIRES ACKNOWLEDGMENT]" if requires_ack else ""

                    print(f"- {title}{priority_text}{ack_text}")
                    print(f"  Category: {category}")
                    print(f"  Date: {created_date}")
                    print(f"  {content}")
                    print()

                # Mark announcements as read
                if input("Mark all announcements as read? (y/n): ").lower() == 'y':
                    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    for announcement in unread_announcements:
                        announcement_id = announcement[0]
                        requires_ack = announcement[6]

                        cursor.execute('''
                        INSERT INTO announcement_reads (announcement_id, parent_id, read_date, acknowledged)
                        VALUES (?, ?, ?, ?)
                        ''', (announcement_id, parent_id, current_time, 1 if requires_ack else 0))

                    conn.commit()
                    print("All announcements marked as read.")

            if read_announcements:
                print("\nRecently Read Announcements:")
                for announcement in read_announcements:
                    id, title, content, priority, category, created_date, read_date = announcement
                    print(f"- {title} (read on {read_date})")
                    print(f"  {content[:100]}...")
                    print()

            if not unread_announcements and not read_announcements:
                print("No announcements available.")

        except sqlite3.Error as e:
            print(f"Database error viewing announcements: {e}")
        finally:
            if conn:
                conn.close()

    def view_parent_dashboard(self):
        """Display a dashboard summary for the parent"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view the dashboard.")
            return

        if self.auth.current_user.get('role', '') != 'parent' and self.auth.current_user.get('role', '') != 'admin':
            print("This function is only available for parent accounts and administrators.")
            return

        if self.auth.current_user.get('role', '') == 'parent' and not self.auth.check_permission('access_parent_dashboard'):
            print("You don't have permission to access the dashboard.")
            return

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            if self.auth.current_user.get('role', '') == 'parent':
                parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
                if not parent_id:
                    print("Error retrieving parent ID.")
                    return
            else:
                print("\nView Dashboard for Parent:")
                cursor.execute('SELECT parent_id, first_name, last_name FROM parent_accounts')
                parents = cursor.fetchall()

                if not parents:
                    print("No parent accounts found in the system.")
                    return

                for i, parent in enumerate(parents):
                    print(f"{i+1}. {parent[1]} {parent[2]} (ID: {parent[0]})")

                choice = input("Select parent (or 0 to cancel): ")
                if choice == '0':
                    return

                try:
                    index = int(choice) - 1
                    if index < 0 or index >= len(parents):
                        raise ValueError
                    parent_id = parents[index][0]
                except (ValueError, IndexError):
                    print("Invalid choice.")
                    return

            cursor.execute('SELECT first_name, last_name FROM parent_accounts WHERE parent_id = ?', (parent_id,))
            parent_info = cursor.fetchone()

            if not parent_info:
                print("Error: Parent account not found.")
                return

            cursor.execute('''
            SELECT s.student_id, s.first_name, s.last_name, s.course
            FROM students s
            JOIN parent_student_relationships psr ON s.student_id = psr.student_id
            WHERE psr.parent_id = ?
            ORDER BY s.last_name, s.first_name
            ''', (parent_id,))

            children = cursor.fetchall()

            if not children:
                print("No children registered for this parent.")
                return

            print("\n" + "=" * 60)
            print(f"PARENT DASHBOARD: {parent_info[0]} {parent_info[1]}")
            print("=" * 60)

            print(f"\nYou have {len(children)} student(s) registered:")
            for child in children:
                student_id, first_name, last_name, course = child
                print(f"- {first_name} {last_name} (ID: {student_id}, Course: {course})")

            try:
                cursor.execute('''
                SELECT COUNT(*) FROM parent_messages
                WHERE parent_id = ? AND is_read = 0 AND is_from_parent = 0
                ''', (parent_id,))

                unread_count = cursor.fetchone()[0]
                print(f"\nUnread Messages: {unread_count}")
            except sqlite3.Error:
                print("\nUnread Messages: Unable to retrieve")

            print("\nStudent Alerts:")

            today = datetime.datetime.now().strftime('%Y-%m-%d')

            for child in children:
                student_id, first_name, last_name, course = child

                print(f"\n{first_name} {last_name}:")

                try:
                    cursor.execute('''
                    SELECT COUNT(*)
                    FROM attendance
                    WHERE student_id = ? AND status != 'present' AND date >= date('now', '-14 days')
                    ''', (student_id,))

                    absence_count = cursor.fetchone()

                    if absence_count and absence_count[0] > 0:
                        print(f"- Attendance: {absence_count[0]} absence(s) in the last 14 days")
                except sqlite3.Error:
                    pass

                try:
                    cursor.execute('''
                    SELECT COUNT(*)
                    FROM student_assignments
                    WHERE student_id = ? AND due_date < ? AND status != 'completed'
                    ''', (student_id, today))

                    overdue_count = cursor.fetchone()

                    if overdue_count and overdue_count[0] > 0:
                        print(f"- Assignments: {overdue_count[0]} overdue assignment(s)")
                except sqlite3.Error:
                    pass

                try:
                    cursor.execute('''
                    SELECT COUNT(*)
                    FROM student_assignments
                    WHERE student_id = ? AND due_date >= ? AND due_date <= date(?, '+7 days')
                    AND (title LIKE '%test%' OR title LIKE '%exam%' OR title LIKE '%quiz%')
                    ''', (student_id, today, today))

                    test_count = cursor.fetchone()

                    if test_count and test_count[0] > 0:
                        print(f"- Upcoming: {test_count[0]} test(s) in the next 7 days")
                except sqlite3.Error:
                    pass

                try:
                    cursor.execute('''
                    SELECT COUNT(*)
                    FROM student_grades
                    WHERE student_id = ? AND grade_date >= date('now', '-7 days')
                    ''', (student_id, ))

                    grade_count = cursor.fetchone()

                    if grade_count and grade_count[0] > 0:
                        print(f"- Grades: {grade_count[0]} new grade(s) in the last 7 days")
                except sqlite3.Error:
                    pass

                try:
                    cursor.execute('''
                    SELECT COUNT(*)
                    FROM teacher_reports
                    WHERE student_id = ? AND created_date >= date('now', '-7 days')
                    ''', (student_id, ))

                    report_count = cursor.fetchone()

                    if report_count and report_count[0] > 0:
                        print(f"- Reports: {report_count[0]} new teacher report(s) in the last 7 days")
                except sqlite3.Error:
                    pass

            try:
                print("\nUpcoming School Events:")

                cursor.execute('''
                SELECT event_name, event_date, event_type
                FROM school_calendar
                WHERE event_date >= ? AND event_date <= date(?, '+14 days') AND audience IN ('all', 'parents')
                ORDER BY event_date
                LIMIT 3
                ''', (today, today))

                events = cursor.fetchall()

                if not events:
                    print("No upcoming events in the next 14 days.")
                else:
                    for event in events:
                        name, date, type = event
                        print(f"- {date}: {name} ({type})")
            except sqlite3.Error:
                print("Unable to retrieve upcoming events.")

            print("\n" + "=" * 60)

        except sqlite3.Error as e:
            print(f"Database error accessing dashboard: {e}")
        finally:
            if conn:
                conn.close()
