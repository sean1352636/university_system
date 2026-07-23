from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
import json


class ExamIntegrityMixin:
    """Mixin providing exam integrity monitoring, proctoring settings, and flag management."""

    def manage_exam_integrity(self):
        """Main menu for exam integrity settings"""
        while True:
            print("\nExam Integrity Management")
            print("=" * 40)
            print("1. Configure Exam Settings")
            print("2. Configure IP Restrictions")
            print("3. View Integrity Logs")
            print("4. View Flagged Students")
            print("5. View Proctoring Status")
            print("6. Clear Integrity Flags")
            print("7. Back")

            choice = input("\nSelect option: ").strip()

            if choice == '1':
                self.configure_exam_settings()
            elif choice == '2':
                self.configure_ip_restrictions()
            elif choice == '3':
                self.view_integrity_logs()
            elif choice == '4':
                self.view_flagged_students()
            elif choice == '5':
                self.view_proctoring_status()
            elif choice == '6':
                self.clear_integrity_flags()
            elif choice == '7':
                break
            else:
                print("Invalid option. Please try again.")

    def configure_exam_settings(self):
        """Configure integrity settings for an assessment"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT id, title, module_code FROM assignments
            WHERE is_active = 1
            ORDER BY due_date DESC
            ''')

            assignments = cursor.fetchall()

            if not assignments:
                print("No active assignments found.")
                conn.close()
                return

            print("\nActive Assignments:")
            for i, (aid, title, module) in enumerate(assignments, 1):
                print(f"{i}. {title} ({module})")

            choice = input("\nSelect assignment number: ").strip()
            try:
                index = int(choice) - 1
                if index < 0 or index >= len(assignments):
                    print("Invalid selection.")
                    conn.close()
                    return
            except ValueError:
                print("Please enter a number.")
                conn.close()
                return

            assessment_id = assignments[index][0]

            # Check for existing settings
            cursor.execute('''
            SELECT * FROM exam_integrity_settings WHERE assessment_id = ?
            ''', (assessment_id,))
            existing = cursor.fetchone()

            print("\nConfigure Exam Integrity Settings:")
            print("-" * 40)

            randomize_questions = input("Randomize questions? (y/n): ").strip().lower()
            if randomize_questions not in ('y', 'n'):
                print("Invalid input. Defaulting to 'n'.")
                randomize_questions = 'n'
            randomize_questions = 1 if randomize_questions == 'y' else 0

            randomize_answers = input("Randomize answer options? (y/n): ").strip().lower()
            if randomize_answers not in ('y', 'n'):
                print("Invalid input. Defaulting to 'n'.")
                randomize_answers = 'n'
            randomize_answers = 1 if randomize_answers == 'y' else 0

            question_count_str = input("Number of questions to display (0 for all): ").strip()
            try:
                question_count = int(question_count_str)
                if question_count < 0:
                    print("Invalid number. Defaulting to 0 (all).")
                    question_count = 0
            except ValueError:
                print("Invalid input. Defaulting to 0 (all).")
                question_count = 0

            time_limit_str = input("Time limit in minutes (0 for no limit): ").strip()
            try:
                time_limit = int(time_limit_str)
                if time_limit < 0:
                    print("Invalid number. Defaulting to 0 (no limit).")
                    time_limit = 0
            except ValueError:
                print("Invalid input. Defaulting to 0 (no limit).")
                time_limit = 0

            auto_submit = input("Auto-submit when time expires? (y/n): ").strip().lower()
            if auto_submit not in ('y', 'n'):
                print("Invalid input. Defaulting to 'n'.")
                auto_submit = 'n'
            auto_submit = 1 if auto_submit == 'y' else 0

            browser_lockdown = input("Enable browser lockdown? (y/n): ").strip().lower()
            if browser_lockdown not in ('y', 'n'):
                print("Invalid input. Defaulting to 'n'.")
                browser_lockdown = 'n'
            browser_lockdown = 1 if browser_lockdown == 'y' else 0

            proctoring_provider = input("Proctoring provider (none/internal/proctorio/examity): ").strip().lower()
            if proctoring_provider not in ('none', 'internal', 'proctorio', 'examity'):
                print("Invalid provider. Defaulting to 'none'.")
                proctoring_provider = 'none'

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            if existing:
                cursor.execute('''
                UPDATE exam_integrity_settings
                SET randomize_questions = ?, randomize_answers = ?, question_count = ?,
                    time_limit_minutes = ?, auto_submit = ?, browser_lockdown = ?,
                    proctoring_provider = ?, updated_at = ?
                WHERE assessment_id = ?
                ''', (randomize_questions, randomize_answers, question_count,
                      time_limit, auto_submit, browser_lockdown,
                      proctoring_provider, timestamp, assessment_id))
                print("\nExam integrity settings updated successfully!")
            else:
                cursor.execute('''
                INSERT INTO exam_integrity_settings
                (assessment_id, randomize_questions, randomize_answers, question_count,
                 time_limit_minutes, auto_submit, browser_lockdown,
                 proctoring_provider, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (assessment_id, randomize_questions, randomize_answers, question_count,
                      time_limit, auto_submit, browser_lockdown,
                      proctoring_provider, timestamp, timestamp))
                print("\nExam integrity settings configured successfully!")

            conn.commit()
            conn.close()

        except Exception as e:
            print(f"Error configuring exam settings: {e}")

    def configure_ip_restrictions(self):
        """Set allowed IP ranges for an assessment"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT eis.assessment_id, a.title, a.module_code, eis.allowed_ip_ranges
            FROM exam_integrity_settings eis
            JOIN assignments a ON eis.assessment_id = a.id
            WHERE a.is_active = 1
            ORDER BY a.due_date DESC
            ''')

            settings = cursor.fetchall()

            if not settings:
                print("No assessments with integrity settings found.")
                print("Please configure exam settings first.")
                conn.close()
                return

            print("\nAssessments with Integrity Settings:")
            for i, (aid, title, module, ip_ranges) in enumerate(settings, 1):
                current_ips = ip_ranges if ip_ranges else "None"
                print(f"{i}. {title} ({module}) - Current IPs: {current_ips}")

            choice = input("\nSelect assessment number: ").strip()
            try:
                index = int(choice) - 1
                if index < 0 or index >= len(settings):
                    print("Invalid selection.")
                    conn.close()
                    return
            except ValueError:
                print("Please enter a number.")
                conn.close()
                return

            assessment_id = settings[index][0]
            current_ranges = settings[index][3]

            if current_ranges:
                print(f"\nCurrent allowed IP ranges: {current_ranges}")

            print("\nEnter allowed IP ranges (comma-separated, e.g., 192.168.1.0/24,10.0.0.0/8)")
            print("Enter 'clear' to remove restrictions, or 'cancel' to abort.")
            ip_input = input("IP ranges: ").strip()

            if ip_input.lower() == 'cancel':
                print("Operation cancelled.")
                conn.close()
                return

            if ip_input.lower() == 'clear':
                ip_ranges = None
            else:
                # Validate IP range format
                ranges = [r.strip() for r in ip_input.split(',') if r.strip()]
                if not ranges:
                    print("No valid IP ranges provided.")
                    conn.close()
                    return

                valid_ranges = []
                for ip_range in ranges:
                    parts = ip_range.split('/')
                    if len(parts) > 2:
                        print(f"Invalid IP range format: {ip_range}")
                        conn.close()
                        return
                    ip_parts = parts[0].split('.')
                    if len(ip_parts) != 4:
                        print(f"Invalid IP address: {parts[0]}")
                        conn.close()
                        return
                    try:
                        for part in ip_parts:
                            val = int(part)
                            if val < 0 or val > 255:
                                print(f"Invalid IP octet value: {part} in {ip_range}")
                                conn.close()
                                return
                        if len(parts) == 2:
                            prefix = int(parts[1])
                            if prefix < 0 or prefix > 32:
                                print(f"Invalid CIDR prefix: {parts[1]} in {ip_range}")
                                conn.close()
                                return
                    except ValueError:
                        print(f"Invalid IP range: {ip_range}")
                        conn.close()
                        return
                    valid_ranges.append(ip_range)

                ip_ranges = ','.join(valid_ranges)

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
            UPDATE exam_integrity_settings
            SET allowed_ip_ranges = ?, updated_at = ?
            WHERE assessment_id = ?
            ''', (ip_ranges, timestamp, assessment_id))

            conn.commit()
            conn.close()

            if ip_ranges:
                print(f"\nIP restrictions set: {ip_ranges}")
            else:
                print("\nIP restrictions cleared.")

        except Exception as e:
            print(f"Error configuring IP restrictions: {e}")

    def view_integrity_logs(self):
        """View integrity event logs with filters"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            print("\nIntegrity Log Filters:")
            print("1. All events")
            print("2. Filter by assessment")
            print("3. Filter by student")
            print("4. Filter by event type")

            filter_choice = input("\nSelect filter: ").strip()

            query = '''
            SELECT eil.id, eil.assessment_id, a.title, eil.student_id,
                   eil.event_type, eil.event_data, eil.created_at
            FROM exam_integrity_logs eil
            JOIN assignments a ON eil.assessment_id = a.id
            '''
            params = []

            if filter_choice == '2':
                assessment_id = input("Enter assessment ID: ").strip()
                if not assessment_id.isdigit():
                    print("Invalid assessment ID.")
                    conn.close()
                    return
                query += ' WHERE eil.assessment_id = ?'
                params.append(int(assessment_id))
            elif filter_choice == '3':
                student_id = input("Enter student ID: ").strip()
                if not student_id:
                    print("Student ID cannot be empty.")
                    conn.close()
                    return
                query += ' WHERE eil.student_id = ?'
                params.append(student_id)
            elif filter_choice == '4':
                print("Event types: tab_switch, copy_paste, focus_lost, right_click, screenshot_attempt")
                event_type = input("Enter event type: ").strip().lower()
                valid_types = ('tab_switch', 'copy_paste', 'focus_lost', 'right_click', 'screenshot_attempt')
                if event_type not in valid_types:
                    print("Invalid event type.")
                    conn.close()
                    return
                query += ' WHERE eil.event_type = ?'
                params.append(event_type)

            query += ' ORDER BY eil.created_at DESC LIMIT 100'

            cursor.execute(query, params)
            logs = cursor.fetchall()

            if not logs:
                print("\nNo integrity events found.")
                conn.close()
                return

            print(f"\nIntegrity Events ({len(logs)} records):")
            print("=" * 100)
            print(f"{'ID':<6} {'Assessment':<30} {'Student':<15} {'Event Type':<20} {'Timestamp':<20}")
            print("-" * 100)

            for log_id, aid, title, sid, event_type, event_data, created_at in logs:
                title_display = title[:27] + '...' if len(title) > 30 else title
                print(f"{log_id:<6} {title_display:<30} {sid:<15} {event_type:<20} {created_at:<20}")

            # Option to view details
            detail_id = input("\nEnter event ID for details (or press Enter to skip): ").strip()
            if detail_id.isdigit():
                for log_id, aid, title, sid, event_type, event_data, created_at in logs:
                    if log_id == int(detail_id):
                        print("\nEvent Details:")
                        print(f"  ID: {log_id}")
                        print(f"  Assessment: {title} (ID: {aid})")
                        print(f"  Student: {sid}")
                        print(f"  Event Type: {event_type}")
                        print(f"  Timestamp: {created_at}")
                        if event_data:
                            try:
                                data = json.loads(event_data)
                                print("  Event Data:")
                                for key, value in data.items():
                                    print(f"    {key}: {value}")
                            except (json.JSONDecodeError, TypeError):
                                print(f"  Event Data: {event_data}")
                        break
                else:
                    print("Event not found in current results.")

            conn.close()

        except Exception as e:
            print(f"Error viewing integrity logs: {e}")

    def view_flagged_students(self):
        """Show students with suspicious activity (3+ events)"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT eil.assessment_id, a.title, eil.student_id,
                   COUNT(*) as event_count,
                   GROUP_CONCAT(DISTINCT eil.event_type) as event_types,
                   MIN(eil.created_at) as first_event,
                   MAX(eil.created_at) as last_event
            FROM exam_integrity_logs eil
            JOIN assignments a ON eil.assessment_id = a.id
            WHERE eil.dismissed = 0
            GROUP BY eil.assessment_id, eil.student_id
            HAVING COUNT(*) >= 3
            ORDER BY event_count DESC
            ''')

            flagged = cursor.fetchall()

            if not flagged:
                print("\nNo flagged students found.")
                conn.close()
                return

            print(f"\nFlagged Students ({len(flagged)} records):")
            print("=" * 110)
            print(f"{'Assessment':<30} {'Student':<15} {'Events':<8} {'Types':<30} {'First':<20} {'Last':<20}")
            print("-" * 110)

            for aid, title, sid, count, types, first_event, last_event in flagged:
                title_display = title[:27] + '...' if len(title) > 30 else title
                types_display = types[:27] + '...' if len(types) > 30 else types
                print(f"{title_display:<30} {sid:<15} {count:<8} {types_display:<30} {first_event:<20} {last_event:<20}")

            conn.close()

        except Exception as e:
            print(f"Error viewing flagged students: {e}")

    def log_integrity_event(self, assessment_id, student_id, event_type, event_data):
        """Record an integrity event"""
        try:
            valid_types = ('tab_switch', 'copy_paste', 'focus_lost', 'right_click', 'screenshot_attempt')
            if event_type not in valid_types:
                print(f"Invalid event type: {event_type}")
                return False

            if not assessment_id or not student_id:
                print("Assessment ID and student ID are required.")
                return False

            if isinstance(event_data, dict):
                event_data_str = json.dumps(event_data)
            else:
                event_data_str = str(event_data) if event_data else '{}'

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('''
                INSERT INTO exam_integrity_logs
                (assessment_id, student_id, event_type, event_data, dismissed, created_at)
                VALUES (?, ?, ?, ?, 0, ?)
                ''', (assessment_id, student_id, event_type, event_data_str, timestamp))

                # Pull a richer student/assessment record for the legal case
                row = cursor.execute(
                    """
                    SELECT s.first_name, s.last_name, s.email_address,
                           a.assessment_name
                    FROM students s
                    LEFT JOIN assessments a ON a.id = ?
                    WHERE s.student_id = ?
                    """,
                    (assessment_id, student_id),
                ).fetchone()

                conn.commit()
            finally:
                conn.close()

            # Mirror serious integrity events as a legal case so the
            # academic-misconduct trail lives alongside the per-event log.
            try:
                from education_system.post_18.university_system.modules.domain.academics.gui.assignment_system.integrations import (
                    open_integrity_case,
                )
                if row:
                    first, last, email, assessment_title = row
                else:
                    first, last, email, assessment_title = ("", "", "", str(assessment_id))
                open_integrity_case(
                    student_id=str(student_id),
                    student_name=f"{first or ''} {last or ''}".strip()
                        or str(student_id),
                    student_email=email or "",
                    assessment_title=assessment_title or str(assessment_id),
                    event_type=event_type,
                    details=event_data_str,
                )
            except Exception as legal_err:
                print(f"Warning: failed to mirror integrity event to legal: {legal_err}")

            print(f"Integrity event logged: {event_type} for student {student_id}")
            return True

        except Exception as e:
            print(f"Error logging integrity event: {e}")
            return False

    def view_proctoring_status(self):
        """Show active exams and their integrity settings"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT a.id, a.title, a.module_code, a.due_date,
                   eis.randomize_questions, eis.randomize_answers,
                   eis.question_count, eis.time_limit_minutes,
                   eis.auto_submit, eis.browser_lockdown,
                   eis.proctoring_provider, eis.allowed_ip_ranges
            FROM assignments a
            JOIN exam_integrity_settings eis ON a.id = eis.assessment_id
            WHERE a.is_active = 1
            ORDER BY a.due_date
            ''')

            exams = cursor.fetchall()

            if not exams:
                print("\nNo active exams with integrity settings found.")
                conn.close()
                return

            print(f"\nActive Exams with Integrity Settings ({len(exams)}):")
            print("=" * 80)

            for (aid, title, module, due_date, rand_q, rand_a, q_count,
                 time_limit, auto_sub, lockdown, proctor, ip_ranges) in exams:
                print(f"\n  Assessment: {title} ({module})")
                print(f"  ID: {aid} | Due: {due_date}")
                print(f"  Randomize Questions: {'Yes' if rand_q else 'No'}")
                print(f"  Randomize Answers: {'Yes' if rand_a else 'No'}")
                print(f"  Question Count: {'All' if q_count == 0 else q_count}")
                print(f"  Time Limit: {'No limit' if time_limit == 0 else f'{time_limit} minutes'}")
                print(f"  Auto-Submit: {'Yes' if auto_sub else 'No'}")
                print(f"  Browser Lockdown: {'Yes' if lockdown else 'No'}")
                print(f"  Proctoring: {proctor}")
                print(f"  IP Restrictions: {ip_ranges if ip_ranges else 'None'}")

                # Show event counts for this assessment
                cursor.execute('''
                SELECT COUNT(*) FROM exam_integrity_logs
                WHERE assessment_id = ?
                ''', (aid,))
                event_count = cursor.fetchone()[0]

                cursor.execute('''
                SELECT COUNT(DISTINCT student_id) FROM exam_integrity_logs
                WHERE assessment_id = ? AND dismissed = 0
                GROUP BY assessment_id
                HAVING COUNT(*) >= 3
                ''')
                flagged_row = cursor.fetchone()
                flagged_count = flagged_row[0] if flagged_row else 0

                print(f"  Integrity Events: {event_count} | Flagged Students: {flagged_count}")
                print("-" * 80)

            conn.close()

        except Exception as e:
            print(f"Error viewing proctoring status: {e}")

    def clear_integrity_flags(self, assessment_id=None, student_id=None):
        """Dismiss flags for a student after review"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if not assessment_id:
                assessment_id_str = input("Enter assessment ID: ").strip()
                if not assessment_id_str.isdigit():
                    print("Invalid assessment ID.")
                    conn.close()
                    return
                assessment_id = int(assessment_id_str)

            if not student_id:
                student_id = input("Enter student ID: ").strip()
                if not student_id:
                    print("Student ID cannot be empty.")
                    conn.close()
                    return

            # Verify events exist
            cursor.execute('''
            SELECT COUNT(*) FROM exam_integrity_logs
            WHERE assessment_id = ? AND student_id = ? AND dismissed = 0
            ''', (assessment_id, student_id))

            event_count = cursor.fetchone()[0]

            if event_count == 0:
                print(f"No active flags found for student {student_id} on assessment {assessment_id}.")
                conn.close()
                return

            # Show events before clearing
            cursor.execute('''
            SELECT event_type, COUNT(*) as count
            FROM exam_integrity_logs
            WHERE assessment_id = ? AND student_id = ? AND dismissed = 0
            GROUP BY event_type
            ''', (assessment_id, student_id))

            events = cursor.fetchall()
            print(f"\nFlags for student {student_id} on assessment {assessment_id}:")
            for event_type, count in events:
                print(f"  {event_type}: {count} events")
            print(f"  Total: {event_count} events")

            confirm = input("\nDismiss all flags for this student? (y/n): ").strip().lower()
            if confirm != 'y':
                print("Operation cancelled.")
                conn.close()
                return

            reason = input("Reason for dismissal: ").strip()
            if not reason:
                print("Dismissal reason is required.")
                conn.close()
                return

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            UPDATE exam_integrity_logs
            SET dismissed = 1, dismissed_by = ?, dismissed_reason = ?, dismissed_at = ?
            WHERE assessment_id = ? AND student_id = ? AND dismissed = 0
            ''', (self.auth.current_user['id'], reason, timestamp,
                  assessment_id, student_id))

            conn.commit()
            conn.close()

            print(f"\n{event_count} integrity flags dismissed for student {student_id}.")

        except Exception as e:
            print(f"Error clearing integrity flags: {e}")
