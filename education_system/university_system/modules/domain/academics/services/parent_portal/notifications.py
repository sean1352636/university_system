from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager
from education_system.university_system.core.paths import DEFAULT_DB_PATH
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608
import datetime


class NotificationsMixin:
    def update_notification_preferences(self):
        """Update parent notification preferences"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to update notification preferences.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        if not self.auth.check_permission('set_notification_preferences'):
            print("You don't have permission to set notification preferences.")
            return

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            if not parent_id:
                print("Error retrieving parent ID.")
                return

            cursor.execute('''
            SELECT email_notifications, sms_notifications, grade_alerts, attendance_alerts,
                   behavior_alerts, assignment_alerts, weekly_summary
            FROM parent_preferences
            WHERE parent_id = ?
            ''', (parent_id,))

            prefs = cursor.fetchone()

            if not prefs:
                cursor.execute(
                    'INSERT INTO parent_preferences (parent_id) VALUES (?)',
                    (parent_id,)
                )
                conn.commit()

                cursor.execute('''
                SELECT email_notifications, sms_notifications, grade_alerts, attendance_alerts,
                       behavior_alerts, assignment_alerts, weekly_summary
                FROM parent_preferences
                WHERE parent_id = ?
                ''', (parent_id,))

                prefs = cursor.fetchone()

            print("\nCurrent Notification Preferences:")
            print(f"1. Email Notifications: {'Enabled' if prefs[0] else 'Disabled'}")
            print(f"2. SMS Notifications: {'Enabled' if prefs[1] else 'Disabled'}")
            print(f"3. Grade Alerts: {'Enabled' if prefs[2] else 'Disabled'}")
            print(f"4. Attendance Alerts: {'Enabled' if prefs[3] else 'Disabled'}")
            print(f"5. Behavior Alerts: {'Enabled' if prefs[4] else 'Disabled'}")
            print(f"6. Assignment Alerts: {'Enabled' if prefs[5] else 'Disabled'}")
            print(f"7. Weekly Summary: {'Enabled' if prefs[6] else 'Disabled'}")
            print("8. Save and Return")

            while True:
                choice = input("\nSelect preference to toggle (1-7) or 8 to save: ")

                if choice == '8':
                    break

                if choice in ['1', '2', '3', '4', '5', '6', '7']:
                    columns = [
                        'email_notifications', 'sms_notifications', 'grade_alerts',
                        'attendance_alerts', 'behavior_alerts', 'assignment_alerts', 'weekly_summary'
                    ]
                    column = columns[int(choice) - 1]
                    safe_column = validate_identifier(column, "column")

                    cursor.execute('''
                    UPDATE parent_preferences
                    SET [''' + safe_column + '''] = NOT [''' + safe_column + ''']
                    WHERE parent_id = ?
                    ''', (parent_id,))

                    conn.commit()

                    cursor.execute('''
                    SELECT email_notifications, sms_notifications, grade_alerts, attendance_alerts,
                           behavior_alerts, assignment_alerts, weekly_summary
                    FROM parent_preferences
                    WHERE parent_id = ?
                    ''', (parent_id,))

                    prefs = cursor.fetchone()

                    print("\nUpdated Notification Preferences:")
                    print(f"1. Email Notifications: {'Enabled' if prefs[0] else 'Disabled'}")
                    print(f"2. SMS Notifications: {'Enabled' if prefs[1] else 'Disabled'}")
                    print(f"3. Grade Alerts: {'Enabled' if prefs[2] else 'Disabled'}")
                    print(f"4. Attendance Alerts: {'Enabled' if prefs[3] else 'Disabled'}")
                    print(f"5. Behavior Alerts: {'Enabled' if prefs[4] else 'Disabled'}")
                    print(f"6. Assignment Alerts: {'Enabled' if prefs[5] else 'Disabled'}")
                    print(f"7. Weekly Summary: {'Enabled' if prefs[6] else 'Disabled'}")
                    print("8. Save and Return")
                else:
                    print("Invalid choice.")

            print("Preferences saved successfully.")

        except sqlite3.Error as e:
            print(f"Database error updating preferences: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    def advanced_notification_preferences(self):
        """Advanced notification settings"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to manage advanced preferences.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            if not parent_id:
                print("Error retrieving parent ID.")
                return

            # Get current advanced preferences
            cursor.execute('''
            SELECT notification_timing, quiet_hours_start, quiet_hours_end
            FROM parent_preferences
            WHERE parent_id = ?
            ''', (parent_id,))

            prefs = cursor.fetchone()

            if not prefs:
                # Create default preferences
                cursor.execute('''
                INSERT INTO parent_preferences (parent_id, notification_timing, quiet_hours_start, quiet_hours_end)
                VALUES (?, '08:00', '20:00', '07:00')
                ''', (parent_id,))
                conn.commit()
                prefs = ('08:00', '20:00', '07:00')

            timing, quiet_start, quiet_end = prefs

            print("\nAdvanced Notification Preferences:")
            print(f"Current preferred notification time: {timing}")
            print(f"Quiet hours: {quiet_start} - {quiet_end}")

            print("\nOptions:")
            print("1. Change preferred notification time")
            print("2. Update quiet hours")
            print("3. Set subject-specific preferences")
            print("4. Back to menu")

            choice = input("Select option: ")

            if choice == '1':
                new_timing = input("Preferred notification time (HH:MM): ")
                try:
                    datetime.datetime.strptime(new_timing, '%H:%M')
                    cursor.execute('UPDATE parent_preferences SET notification_timing = ? WHERE parent_id = ?',
                                 (new_timing, parent_id))
                    conn.commit()
                    print("Notification timing updated.")
                except ValueError:
                    print("Invalid time format.")

            elif choice == '2':
                new_quiet_start = input(f"Quiet hours start (current: {quiet_start}): ")
                new_quiet_end = input(f"Quiet hours end (current: {quiet_end}): ")

                try:
                    datetime.datetime.strptime(new_quiet_start, '%H:%M')
                    datetime.datetime.strptime(new_quiet_end, '%H:%M')

                    cursor.execute('''UPDATE parent_preferences
                                   SET quiet_hours_start = ?, quiet_hours_end = ?
                                   WHERE parent_id = ?''',
                                 (new_quiet_start, new_quiet_end, parent_id))
                    conn.commit()
                    print("Quiet hours updated.")
                except ValueError:
                    print("Invalid time format.")

            elif choice == '3':
                # Subject-specific preferences
                print("\n=== Subject-Specific Preferences ===")
                subjects = input("Enter subjects to get notifications for (comma-separated): ").split(',')
                subjects = [s.strip() for s in subjects if s.strip()]

                if subjects:
                    # Store preferences as JSON
                    import json
                    prefs_json = json.dumps({'subjects': subjects})
                    cursor.execute('''UPDATE parent_preferences
                                   SET subject_preferences = ?
                                   WHERE parent_id = ?''',
                                 (prefs_json, parent_id))
                    conn.commit()
                    print(f"Subject preferences updated: {', '.join(subjects)}")
                else:
                    print("No subjects entered.")

        except sqlite3.Error as e:
            print(f"Database error managing preferences: {e}")
        finally:
            if conn:
                conn.close()

    def get_notification_count(self):
        """Get count of unread notifications for dashboard"""
        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            if not parent_id:
                return 0

            cursor.execute('''
            SELECT COUNT(*) FROM parent_notifications
            WHERE parent_id = ? AND read_status = 0
            ''', (parent_id,))

            count = cursor.fetchone()[0]
            return count

        except sqlite3.Error:
            return 0
        finally:
            if conn:
                conn.close()

    def mark_notifications_read(self):
        """Mark all notifications as read"""
        if not self.auth or not self.auth.current_user:
            print("You must be logged in to mark notifications as read.")
            return

        if self.auth.current_user.get('role', '') != 'parent':
            print("This function is only available for parent accounts.")
            return

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            conn.execute("PRAGMA busy_timeout = 30000")
            cursor = conn.cursor()

            parent_id = self.get_parent_id_from_user(self.auth.current_user['id'])
            if not parent_id:
                print("Error retrieving parent ID.")
                return

            cursor.execute('''
            UPDATE parent_notifications
            SET read_status = 1
            WHERE parent_id = ? AND read_status = 0
            ''', (parent_id,))

            updated_count = cursor.rowcount
            conn.commit()

            print(f"Marked {updated_count} notifications as read.")

        except sqlite3.Error as e:
            print(f"Database error marking notifications as read: {e}")
        finally:
            if conn:
                conn.close()
