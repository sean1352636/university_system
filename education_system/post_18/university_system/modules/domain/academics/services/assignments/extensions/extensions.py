from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime


class ExtensionsMixin:
    """Mixin providing extension request submission, review, and management."""

    def request_extension(self):
        """Request an extension for an assignment"""
        if not self._check_permission('submit_assignment'):
            return

        try:
            student_id = self._get_student_id()
            if not student_id:
                print("No student ID associated with your account.")
                return

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT a.id, a.title, a.due_date, a.module_code
                FROM assignments a
                JOIN student_modules sm ON a.module_code = sm.module_code
                WHERE sm.student_id = ? AND a.is_active = 1
                AND a.due_date > datetime('now')
                ORDER BY a.due_date
                ''', (student_id,))

                assignments = cursor.fetchall()

                if not assignments:
                    print("No upcoming assignments found.")
            finally:
                conn.close()
                return

            print("\nUpcoming Assignments:")
            for i, (aid, title, due_date, module) in enumerate(assignments, 1):
                print(f"{i}. {title} ({module}) - Due: {due_date}")

            choice = input("\nSelect assignment number: ").strip()
            try:
                index = int(choice) - 1
                if 0 <= index < len(assignments):
                    assignment_id = assignments[index][0]
                    self._submit_extension_request(cursor, assignment_id, student_id)
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a number.")

            conn.commit()
            conn.close()

        except Exception as e:
            print(f"Error requesting extension: {e}")

    def _submit_extension_request(self, cursor, assignment_id, student_id):
        """Submit an extension request"""
        print("\nExtension Request Form:")

        cursor.execute('''
        SELECT status FROM extension_requests
        WHERE assignment_id = ? AND student_id = ?
        ORDER BY requested_date DESC LIMIT 1
        ''', (assignment_id, student_id))

        existing = cursor.fetchone()
        if existing and existing[0] == 'pending':
            print("You already have a pending extension request for this assignment.")
            return

        while True:
            new_due_str = input("Requested new due date (YYYY-MM-DD HH:MM): ")
            try:
                new_due_date = datetime.strptime(new_due_str, "%Y-%m-%d %H:%M")
                if new_due_date <= datetime.now():
                    print("New due date must be in the future.")
                    continue
                break
            except ValueError:
                print("Invalid date format. Use YYYY-MM-DD HH:MM")

        reason = input("Reason for extension request: ").strip()
        if not reason:
            print("Reason cannot be empty.")
            return

        supporting_docs = input("Supporting documents (file paths, comma-separated, optional): ").strip()

        cursor.execute('''
        INSERT INTO extension_requests
        (assignment_id, student_id, requested_date, new_due_date, reason, supporting_documents)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (assignment_id, student_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              new_due_date.strftime('%Y-%m-%d %H:%M:%S'), reason, supporting_docs))

        print("Extension request submitted successfully!")
        print("You will be notified when it's reviewed.")

    def review_extension_requests(self):
        """Review extension requests (instructor/admin only)"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT er.id, er.assignment_id, er.student_id, st.first_name, st.last_name,
                   a.title, er.requested_date, er.new_due_date, er.reason
            FROM extension_requests er
            JOIN assignments a ON er.assignment_id = a.id
            JOIN students st ON er.student_id = st.student_id
            WHERE er.status = 'pending'
            ORDER BY er.requested_date
            ''')

            requests = cursor.fetchall()

            if not requests:
                print("No pending extension requests.")
                conn.close()
                return

            print("\nPending Extension Requests:")
            print("=" * 100)
            for req in requests:
                req_id, aid, sid, fname, lname, title, req_date, new_due, reason = req
                print(f"\nRequest ID: {req_id}")
                print(f"Student: {fname} {lname} ({sid})")
                print(f"Assignment: {title}")
                print(f"Requested: {req_date}")
                print(f"New due date: {new_due}")
                print(f"Reason: {reason}")
                print("-" * 100)

            req_id = input("\nEnter request ID to review: ").strip()
            if req_id.isdigit():
                self._process_extension_request(cursor, int(req_id))

            conn.commit()
            conn.close()

        except Exception as e:
            print(f"Error reviewing extension requests: {e}")

    def _process_extension_request(self, cursor, request_id):
        """Process a specific extension request"""
        cursor.execute('''
        SELECT er.*, st.first_name, st.last_name, a.title, a.due_date
        FROM extension_requests er
        JOIN students st ON er.student_id = st.student_id
        JOIN assignments a ON er.assignment_id = a.id
        WHERE er.id = ?
        ''', (request_id,))

        request = cursor.fetchone()
        if not request:
            print("Request not found.")
            return

        print(f"\nReviewing request from {request[11]} {request[12]}")
        print(f"Assignment: {request[13]}")
        print(f"Original due: {request[14]}")
        print(f"Requested due: {request[4]}")
        print(f"Reason: {request[5]}")

        decision = input("\nApprove request? (y/n): ").lower()
        comments = input("Reviewer comments: ").strip()

        if decision == 'y':
            original_due = datetime.strptime(request[14], '%Y-%m-%d %H:%M:%S')
            new_due = datetime.strptime(request[4], '%Y-%m-%d %H:%M:%S')
            extension_days = (new_due - original_due).days

            cursor.execute('''
            UPDATE extension_requests
            SET status = 'approved', reviewed_by = ?, reviewed_date = ?,
                reviewer_comments = ?, approved_extension_days = ?
            WHERE id = ?
            ''', (self.auth.current_user['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  comments, extension_days, request_id))

            print(f"Extension approved for {extension_days} days!")

        else:
            cursor.execute('''
            UPDATE extension_requests
            SET status = 'denied', reviewed_by = ?, reviewed_date = ?, reviewer_comments = ?
            WHERE id = ?
            ''', (self.auth.current_user['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  comments, request_id))

            print("Extension request denied.")

    def approve_extension(self, request_id):
        """Approve an extension request"""
        try:
            if not self._check_permission('manage_extensions'):
                print("Permission denied")
                return False

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                reviewer_id = self._get_student_id()

                cursor.execute('SELECT assignment_id, student_id, new_due_date FROM extension_requests WHERE id = ?', (request_id,))
                result = cursor.fetchone()

                if not result:
                    print("Extension request not found")
                    return False

                assignment_id, student_id, new_due_date = result

                cursor.execute('''
                    UPDATE extension_requests
                    SET status = 'approved', reviewed_by = ?, reviewed_at = ?
                    WHERE id = ?
                ''', (reviewer_id, timestamp, request_id))

                self._send_notification(student_id, "Extension Approved",
                                      f"Your extension request has been approved until {new_due_date}",
                                      "extension_approved", assignment_id)

                conn.commit()
                self._log_action('update', 'extension_requests', request_id, {'status': 'approved'})
            finally:
                conn.close()

            print("Extension approved successfully!")
            return True

        except Exception as e:
            print(f"Error approving extension: {e}")
            return False

    def reject_extension(self, request_id, reason=''):
        """Reject an extension request"""
        try:
            if not self._check_permission('manage_extensions'):
                print("Permission denied")
                return False

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                reviewer_id = self._get_student_id()

                cursor.execute('SELECT assignment_id, student_id FROM extension_requests WHERE id = ?', (request_id,))
                result = cursor.fetchone()

                if not result:
                    print("Extension request not found")
                    return False

                assignment_id, student_id = result

                cursor.execute('''
                    UPDATE extension_requests
                    SET status = 'rejected', reviewed_by = ?, reviewed_at = ?, reviewer_notes = ?
                    WHERE id = ?
                ''', (reviewer_id, timestamp, reason, request_id))

                self._send_notification(student_id, "Extension Rejected",
                                      f"Your extension request has been rejected. {reason}",
                                      "extension_rejected", assignment_id)

                conn.commit()
                self._log_action('update', 'extension_requests', request_id, {'status': 'rejected'})
            finally:
                conn.close()

            print("Extension rejected successfully!")
            return True

        except Exception as e:
            print(f"Error rejecting extension: {e}")
            return False

    def get_extension_requests(self, status=None):
        """Get all extension requests, optionally filtered by status"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if status:
                cursor.execute('''
                    SELECT * FROM extension_requests
                    WHERE status = ?
                    ORDER BY requested_at DESC
                ''', (status,))
            else:
                cursor.execute('''
                    SELECT * FROM extension_requests
                    ORDER BY requested_at DESC
                ''')

            requests = cursor.fetchall()
            conn.close()
            return requests

        except Exception as e:
            print(f"Error retrieving extension requests: {e}")
            return []

    def get_student_extensions(self, student_id=None):
        """Get all extension requests for a specific student"""
        try:
            if not student_id:
                student_id = self._get_student_id()

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT * FROM extension_requests
                    WHERE student_id = ?
                    ORDER BY requested_at DESC
                ''', (student_id,))

                requests = cursor.fetchall()
            finally:
                conn.close()
            return requests

        except Exception as e:
            print(f"Error retrieving student extensions: {e}")
            return []
