from education_system.systems.university.infrastructure.database.db import sqlite3, DatabaseManager
from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH
import datetime


class QuickActionsMixin:
    def quick_actions_menu(self):
        """Quick actions for busy parents"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to use quick actions.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        print("\nQuick Actions Menu:")
        print("==================")
        print("1. Quick absence report")
        print("2. Emergency contact update")
        print("3. View today's alerts")
        print("4. Check meal account balance")
        print("5. View urgent messages")
        print("6. Back to main menu")

        choice = input("Enter your choice (1-6): ")

        if choice == '1':
            # Quick absence report
            children = self.view_children()
            if children and len(children) == 1:
                # If only one child, skip selection
                self._quick_absence_report(children[0])
            else:
                self.report_absence()

        elif choice == '2':
            self.emergency_contact_update()

        elif choice == '3':
            self._view_todays_alerts()

        elif choice == '4':
            self._quick_meal_balance_check()

        elif choice == '5':
            self._view_urgent_messages()

        elif choice == '6':
            return

        else:
            print("Invalid choice.")

    def _quick_absence_report(self, child):
        """Quick absence report for single child"""
        student_id = child[0]
        reason = input(f"Reason for {child[1]} {child[3]}'s absence today: ")

        if not reason:
            print("Absence report cancelled.")
            return

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            today = datetime.datetime.now().strftime('%Y-%m-%d')
            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            reported_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute(
                'INSERT INTO student_absences (student_id, absence_date, reason, reported_by, reported_date) VALUES (?, ?, ?, ?, ?)',
                (student_id, today, reason, f"parent:{parent_id}", reported_date)
            )

            conn.commit()
            print("Quick absence report submitted successfully.")

        except sqlite3.Error as e:
            print(f"Error submitting absence report: {e}")
        finally:
            if conn:
                conn.close()

    def _view_todays_alerts(self):
        """View today's alerts and important notices"""
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            today = datetime.datetime.now().strftime('%Y-%m-%d')

            print(f"\nToday's Alerts ({today}):")

            # Unread messages
            cursor.execute('''
            SELECT COUNT(*) FROM parent_messages
            WHERE parent_id = ? AND is_read = 0 AND is_from_parent = 0
            ''', (parent_id,))

            unread_count = cursor.fetchone()[0]
            if unread_count > 0:
                print(f"📧 {unread_count} unread message(s)")

            # Emergency alerts
            cursor.execute('''
            SELECT alert_title, alert_message FROM emergency_alerts
            WHERE active = 1 AND date(created_date) = ?
            ''', (today,))

            emergency_alerts = cursor.fetchall()
            for alert in emergency_alerts:
                print(f"🚨 EMERGENCY: {alert[0]}")
                print(f"   {alert[1]}")

            # Today's events
            cursor.execute('''
            SELECT name AS event_name, start_time, location FROM academic_calendar_events
            WHERE COALESCE(date, substr(date_start, 1, 10)) = ?
              AND (audience IS NULL OR audience IN ('all', 'parents'))
            ''', (today,))

            events = cursor.fetchall()
            for event in events:
                print(f"📅 {event[1]}: {event[0]} at {event[2]}")

            if unread_count == 0 and not emergency_alerts and not events:
                print("No alerts for today.")

        except sqlite3.Error as e:
            print(f"Error viewing alerts: {e}")
        finally:
            if conn:
                conn.close()

    def _quick_meal_balance_check(self):
        """Quick check of all children's meal balances"""
        children = self.view_children()

        if not children:
            print("No children registered.")
            return

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            print("\nMeal Account Balances:")

            for child in children:
                student_id = child[0]

                cursor.execute('SELECT balance, low_balance_threshold FROM meal_accounts WHERE student_id = ?', (student_id,))
                account = cursor.fetchone()

                if account:
                    balance, threshold = account
                    status = "⚠️ LOW" if float(balance) <= float(threshold) else "✅ OK"
                    print(f"  {child[1]} {child[3]}: £{balance:.2f} {status}")
                else:
                    print(f"  {child[1]} {child[3]}: No meal account")

        except sqlite3.Error as e:
            print(f"Error checking meal balances: {e}")
        finally:
            if conn:
                conn.close()

    def _view_urgent_messages(self):
        """View urgent/priority messages"""
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])

            # Get urgent messages (last 24 hours, unread)
            cursor.execute('''
            SELECT pm.message_content, pm.created_date, u.username as teacher_name, s.first_name, s.last_name
            FROM parent_messages pm
            JOIN users u ON pm.teacher_id = u.id
            JOIN students s ON pm.student_id = s.student_id
            WHERE pm.parent_id = ? AND pm.is_read = 0 AND pm.is_from_parent = 0
            AND datetime(pm.created_date) >= datetime('now', '-1 day')
            ORDER BY pm.created_date DESC
            LIMIT 5
            ''', (parent_id,))

            urgent_messages = cursor.fetchall()

            print("\nUrgent Messages (Last 24 hours):")

            if urgent_messages:
                for msg in urgent_messages:
                    content, date, teacher, student_first, student_last = msg
                    print(f"📨 From {teacher} re: {student_first} {student_last}")
                    print(f"   {date}: {content}")
                    print()
            else:
                print("No urgent messages.")

        except sqlite3.Error as e:
            print(f"Error viewing urgent messages: {e}")
        finally:
            if conn:
                conn.close()

    def report_issue(self):
        """Report an issue or concern to school administration"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to report an issue.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("Only parents can report issues.")
            return

        parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])

        print("\n=== Report an Issue ===")
        print("1. Academic concern")
        print("2. Behavioral concern")
        print("3. Facility issue")
        print("4. Safety concern")
        print("5. Billing/Administrative")
        print("6. Other")

        category = input("Select issue category: ")
        category_map = {
            '1': 'Academic', '2': 'Behavioral', '3': 'Facility',
            '4': 'Safety', '5': 'Administrative', '6': 'Other'
        }

        category_name = category_map.get(category, 'Other')
        subject = input("Issue subject: ")
        description = input("Detailed description: ")
        priority = input("Priority (low/medium/high): ").lower()

        if priority not in ['low', 'medium', 'high']:
            priority = 'medium'

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS parent_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT,
                category TEXT,
                subject TEXT,
                description TEXT,
                priority TEXT,
                status TEXT DEFAULT 'open',
                created_date TEXT,
                resolved_date TEXT,
                response TEXT,
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
            )
            ''')

            cursor.execute('''
            INSERT INTO parent_issues (parent_id, category, subject, description, priority, created_date)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (parent_id, category_name, subject, description, priority, datetime.datetime.now().isoformat()))

            conn.commit()
            issue_id = cursor.lastrowid
            print(f"\nIssue reported successfully! Tracking ID: #{issue_id}")
            print("School administration will respond within 24-48 hours.")

        except sqlite3.Error as e:
            print(f"Database error reporting issue: {e}")
        finally:
            if conn:
                conn.close()

    def view_activity_log(self):
        """View parent account activity log"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to view activity log.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("Only parents can view activity logs.")
            return

        parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Create activity log table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS parent_activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id TEXT,
                activity_type TEXT,
                activity_description TEXT,
                ip_address TEXT,
                timestamp TEXT,
                FOREIGN KEY (parent_id) REFERENCES parent_accounts (parent_id)
            )
            ''')

            # Fetch recent activities
            cursor.execute('''
            SELECT activity_type, activity_description, timestamp
            FROM parent_activity_log
            WHERE parent_id = ?
            ORDER BY timestamp DESC
            LIMIT 50
            ''', (parent_id,))

            activities = cursor.fetchall()

            print("\n=== Activity Log (Last 50 entries) ===")
            if activities:
                for act in activities:
                    print(f"[{act[2]}] {act[0]}: {act[1]}")
            else:
                print("No activity recorded yet.")

        except sqlite3.Error as e:
            print(f"Database error viewing activity log: {e}")
        finally:
            if conn:
                conn.close()

    def family_calendar_integration(self):
        """Export school events to family calendar"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to access calendar integration.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            # Get upcoming school events
            today = datetime.datetime.now().strftime('%Y-%m-%d')

            cursor.execute('''
            SELECT name AS event_name, description AS event_description,
                   COALESCE(date, substr(date_start, 1, 10)) AS event_date,
                   start_time, end_time, location, event_type
            FROM academic_calendar_events
            WHERE COALESCE(date, substr(date_start, 1, 10)) >= ?
              AND (audience IS NULL OR audience IN ('all', 'parents'))
            ORDER BY event_date
            LIMIT 20
            ''', (today,))

            events = cursor.fetchall()

            if not events:
                print("No upcoming events to export.")
                return

            print("\nCalendar Integration:")
            print("=====================")
            print(f"Found {len(events)} upcoming events")

            print("\nExport Options:")
            print("1. Generate iCal file (.ics)")
            print("2. Generate Google Calendar CSV")
            print("3. Display calendar URLs")
            print("4. Back to menu")

            choice = input("Select export option: ")

            if choice == '1':
                # Generate iCal content
                ical_content = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//School//Parent Portal//EN\n"

                for event in events:
                    name, description, date, start_time, end_time, location, event_type = event

                    # Convert to iCal format
                    event_start = f"{date.replace('-', '')}T{start_time.replace(':', '')}00"
                    event_end = f"{date.replace('-', '')}T{end_time.replace(':', '')}00"

                    ical_content += "BEGIN:VEVENT\n"
                    ical_content += f"DTSTART:{event_start}\n"
                    ical_content += f"DTEND:{event_end}\n"
                    ical_content += f"SUMMARY:{name}\n"
                    ical_content += f"DESCRIPTION:{description or ''}\n"
                    ical_content += f"LOCATION:{location}\n"
                    ical_content += "END:VEVENT\n"

                ical_content += "END:VCALENDAR\n"

                # In a real implementation, you would save this to a file
                print("\niCal file content generated:")
                print("Save the following content as 'school_events.ics':")
                print("-" * 50)
                print(ical_content)
                print("-" * 50)

            elif choice == '2':
                print("\nGoogle Calendar CSV format:")
                print("Subject,Start Date,Start Time,End Date,End Time,Description,Location")

                for event in events:
                    name, description, date, start_time, end_time, location, event_type = event
                    print(f'"{name}",{date},{start_time},{date},{end_time},"{description or ""}","{location}"')

            elif choice == '3':
                print("\nCalendar Subscription URLs:")
                print("(In a real implementation, these would be actual URLs)")
                print(f"School Events: https://school.example.com/calendar/parent/{self.get_parent_id_from_user(self.auth.current_user['id'])}")
                print("Add this URL to your calendar app to automatically sync school events.")

        except sqlite3.Error as e:
            print(f"Database error accessing calendar: {e}")
        finally:
            if conn:
                conn.close()

    def log_activity(self, action, details=""):
        """Log parent activity for security purposes"""
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            if parent_id:
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO parent_activity_log
                (parent_id, action, details, timestamp)
                VALUES (?, ?, ?, ?)
                ''', (parent_id, action, details, timestamp))

                conn.commit()
        except sqlite3.Error:
            pass  # Don't fail the main operation if logging fails
        finally:
            if conn:
                conn.close()
