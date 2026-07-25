from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime
import os
import shutil
import zipfile

from education_system.systems.university.infrastructure import paths
from education_system.systems.university.domain.academics.services.assignments.core.constants import SUBDIR_EXPORTS


class SubmissionsMixin:
    """Mixin providing submission, resubmission, file preview, and download."""

    def submit_assignment(self):
        """Submit an assignment with enhanced features"""
        if not self._check_permission('submit_assignment'):
            return

        try:
            student_id = self._get_student_id()
            if not student_id:
                print("No student ID associated with your account.")
                return

            # Show available assignments
            self.view_assignments()

            assignment_id = input("\nEnter assignment ID to submit: ").strip()
            if not assignment_id.isdigit():
                print("Invalid assignment ID.")
                return

            assignment_id = int(assignment_id)

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                # Get assignment details
                cursor.execute('''
                SELECT a.*, m.module_name
                FROM assignments a
                JOIN modules m ON a.module_code = m.module_code
                WHERE a.id = ? AND a.is_active = 1
                ''', (assignment_id,))

                assignment = cursor.fetchone()

                if not assignment:
                    print("Assignment not found.")
            finally:
                conn.close()
                return

            # Check if student is enrolled
            cursor.execute('''
            SELECT 1 FROM student_modules
            WHERE student_id = ? AND module_code = ?
            ''', (student_id, assignment[1]))

            if not cursor.fetchone():
                print("You are not enrolled in this module.")
                conn.close()
                return

            # Check for existing submissions
            cursor.execute('''
            SELECT id, status, submission_date, version_number
            FROM assignment_submissions
            WHERE assignment_id = ? AND student_id = ?
            ORDER BY submission_date DESC
            LIMIT 1
            ''', (assignment_id, student_id))

            existing = cursor.fetchone()

            if existing and existing[1] == 'submitted':
                print(f"\nYou have already submitted this assignment (Version {existing[3]})")
                print(f"Previous submission: {existing[2]}")
                replace = input("Submit a new version? (y/n): ").lower()
                if replace != 'y':
                    conn.close()
                    return
                version_number = existing[3] + 1
            else:
                version_number = 1

            # Handle group assignments
            if assignment[15] == 'group':  # assignment_type
                group_id = self._handle_group_submission(cursor, assignment_id, student_id)
                if not group_id:
                    conn.close()
                    return
            else:
                group_id = None

            # Get file path
            file_path = input("Enter the full path to your file: ").strip()
            file_path = file_path.strip('"').strip("'")

            # Validate file
            valid, message = self._validate_file(
                file_path,
                assignment[6],  # file_types_allowed
                assignment[7]   # max_file_size_mb
            )

            if not valid:
                print(f"File validation failed: {message}")
                conn.close()
                return

            # Check due date and late submissions
            due_date = datetime.strptime(assignment[4], '%Y-%m-%d %H:%M:%S')
            submission_time = datetime.now()
            late_submission = submission_time > due_date
            late_days = (submission_time - due_date).days if late_submission else 0

            if late_submission:
                if not assignment[16]:  # allow_late_submission
                    print("Late submissions are not allowed for this assignment.")
                    conn.close()
                    return

                print(f"\nWARNING: This is a late submission ({late_days} days late)!")
                if assignment[17] > 0:  # late_penalty_per_day
                    penalty = assignment[17] * late_days
                    print(f"Late penalty: {penalty}% per day ({penalty * late_days}% total)")

                proceed = input("Do you want to proceed? (y/n): ").lower()
                if proceed != 'y':
                    conn.close()
                    return

            # Create submission directory
            submission_dir = os.path.join(
                self.submission_dir,
                'submitted',
                student_id,
                f"assignment_{assignment_id}"
            )
            os.makedirs(submission_dir, exist_ok=True)

            # Copy file
            file_name = os.path.basename(file_path)
            timestamp = submission_time.strftime('%Y%m%d_%H%M%S')
            new_file_name = f"v{version_number}_{timestamp}_{file_name}"
            new_file_path = os.path.join(submission_dir, new_file_name)

            try:
                shutil.copy2(file_path, new_file_path)
            except Exception as e:
                print(f"Error copying file: {e}")
                conn.close()
                return

            # Calculate file hash and size
            file_hash = self._calculate_file_hash(new_file_path)
            file_size = os.path.getsize(new_file_path)

            # Save submission
            submission_date = submission_time.strftime('%Y-%m-%d %H:%M:%S')

            # Mark previous submissions as not final
            if existing:
                cursor.execute('''
                UPDATE assignment_submissions
                SET is_final_submission = 0
                WHERE assignment_id = ? AND student_id = ?
                ''', (assignment_id, student_id))

            cursor.execute('''
            INSERT INTO assignment_submissions
            (assignment_id, student_id, group_id, submission_date, file_path,
             file_name, file_size, file_hash, status, late_submission, late_days,
             version_number, is_final_submission, ip_address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (assignment_id, student_id, group_id, submission_date, new_file_path,
                  file_name, file_size, file_hash, 'submitted', late_submission, late_days,
                  version_number, 1, 'localhost'))  # Replace with actual IP if available

            submission_id = cursor.lastrowid

            # Create file version record
            cursor.execute('''
            INSERT INTO file_versions (submission_id, version_number, file_path, file_hash, created_at, is_current)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (submission_id, version_number, new_file_path, file_hash, submission_date, 1))

            # Log submission history
            cursor.execute('''
            INSERT INTO submission_history
            (submission_id, student_id, action, action_date, details)
            VALUES (?, ?, ?, ?, ?)
            ''', (submission_id, student_id, 'submitted', submission_date,
                  f"Version {version_number}: {file_name}, Size: {file_size} bytes"))

            conn.commit()
            conn.close()

            print("\nAssignment submitted successfully!")
            print(f"Submission ID: {submission_id}")
            print(f"Version: {version_number}")
            print(f"File: {file_name}")
            print(f"Submitted at: {submission_date}")
            if late_submission:
                print(f"Status: LATE SUBMISSION ({late_days} days)")

            # Log the action
            self._log_action('submit_assignment', 'assignment_submissions', submission_id,
                           None, {'assignment_id': assignment_id, 'file': file_name})

        except Exception as e:
            print(f"Error submitting assignment: {e}")

    def _handle_group_submission(self, cursor, assignment_id, student_id):
        """Handle group assignment submission logic"""
        # Check if student is already in a group for this assignment
        cursor.execute('''
        SELECT g.id, g.group_name FROM groups g
        JOIN group_members gm ON g.id = gm.group_id
        WHERE g.assignment_id = ? AND gm.student_id = ? AND g.is_active = 1
        ''', (assignment_id, student_id))

        existing_group = cursor.fetchone()

        if existing_group:
            print(f"You are in group: {existing_group[1]}")
            return existing_group[0]

        print("\nYou are not in a group for this assignment.")
        print("1. Join existing group")
        print("2. Create new group")

        choice = input("Choose option: ").strip()

        if choice == '1':
            return self._join_existing_group(cursor, assignment_id, student_id)
        elif choice == '2':
            return self._create_new_group(cursor, assignment_id, student_id)
        else:
            print("Invalid choice.")
            return None

    def _join_existing_group(self, cursor, assignment_id, student_id):
        """Join an existing group"""
        # Show available groups
        cursor.execute('''
        SELECT g.id, g.group_name, COUNT(gm.student_id) as current_size, a.group_size_max
        FROM groups g
        LEFT JOIN group_members gm ON g.id = gm.group_id
        JOIN assignments a ON g.assignment_id = a.id
        WHERE g.assignment_id = ? AND g.is_active = 1
        GROUP BY g.id
        HAVING current_size < a.group_size_max
        ORDER BY g.group_name
        ''', (assignment_id,))

        available_groups = cursor.fetchall()

        if not available_groups:
            print("No groups available to join. You'll need to create a new group.")
            return self._create_new_group(cursor, assignment_id, student_id)

        print("\nAvailable groups:")
        for i, (gid, name, size, max_size) in enumerate(available_groups, 1):
            print(f"{i}. {name} ({size}/{max_size} members)")

        choice = input("Select group number: ").strip()
        try:
            index = int(choice) - 1
            if 0 <= index < len(available_groups):
                group_id = available_groups[index][0]

                # Add student to group
                cursor.execute('''
                INSERT INTO group_members (group_id, student_id, joined_at)
                VALUES (?, ?, ?)
                ''', (group_id, student_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                print(f"Joined group: {available_groups[index][1]}")
                return group_id
            else:
                print("Invalid selection.")
                return None
        except ValueError:
            print("Please enter a valid number.")
            return None

    def _create_new_group(self, cursor, assignment_id, student_id):
        """Create a new group"""
        group_name = input("Enter group name: ").strip()
        if not group_name:
            print("Group name cannot be empty.")
            return None

        # Create group
        cursor.execute('''
        INSERT INTO groups (assignment_id, group_name, created_at, created_by)
        VALUES (?, ?, ?, ?)
        ''', (assignment_id, group_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), student_id))

        group_id = cursor.lastrowid

        # Add creator as member
        cursor.execute('''
        INSERT INTO group_members (group_id, student_id, role, joined_at)
        VALUES (?, ?, ?, ?)
        ''', (group_id, student_id, 'leader', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        print(f"Created group: {group_name}")
        return group_id

    def resubmit_assignment(self, submission_id, new_file_path):
        """Resubmit an assignment"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get original submission
            cursor.execute('SELECT assignment_id, student_id FROM assignment_submissions WHERE id = ?', (submission_id,))
            submission = cursor.fetchone()

            if not submission:
                print("Original submission not found")
                return False

            assignment_id, student_id = submission

            # Validate file
            file_hash = self._calculate_file_hash(new_file_path)
            file_size = os.path.getsize(new_file_path)
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Update submission
            cursor.execute('''
                UPDATE assignment_submissions
                SET file_path = ?, file_name = ?, file_size = ?, file_hash = ?,
                    submission_date = ?, status = 'resubmitted', version = version + 1
                WHERE id = ?
            ''', (new_file_path, os.path.basename(new_file_path), file_size, file_hash, timestamp, submission_id))

            conn.commit()
            self._log_action('update', 'assignment_submissions', submission_id)
            conn.close()

            print("Assignment resubmitted successfully!")
            return True

        except Exception as e:
            print(f"Error resubmitting assignment: {e}")
            return False

    def get_student_submissions(self, student_id=None):
        """Get all submissions for a student"""
        try:
            if not student_id:
                student_id = self._get_student_id()

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT s.*, a.title, a.module_code, a.due_date
                    FROM assignment_submissions s
                    INNER JOIN assignments a ON s.assignment_id = a.id
                    WHERE s.student_id = ?
                    ORDER BY s.submission_date DESC
                ''', (student_id,))

                submissions = cursor.fetchall()
            finally:
                conn.close()

            return submissions

        except Exception as e:
            print(f"Error retrieving submissions: {e}")
            return []

    def get_all_submissions(self, assignment_id=None):
        """Get all submissions for an assignment or all assignments"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if assignment_id:
                cursor.execute('''
                    SELECT * FROM assignment_submissions
                    WHERE assignment_id = ?
                    ORDER BY submission_date DESC
                ''', (assignment_id,))
            else:
                cursor.execute('''
                    SELECT * FROM assignment_submissions
                    ORDER BY submission_date DESC
                ''')

            submissions = cursor.fetchall()
            conn.close()

            return submissions

        except Exception as e:
            print(f"Error retrieving all submissions: {e}")
            return []

    def get_submission_details(self, submission_id):
        """Get detailed information about a submission"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT s.*, a.title, a.max_marks
                FROM assignment_submissions s
                INNER JOIN assignments a ON s.assignment_id = a.id
                WHERE s.id = ?
            ''', (submission_id,))

            submission = cursor.fetchone()
            conn.close()

            return submission

        except Exception as e:
            print(f"Error retrieving submission details: {e}")
            return None

    def validate_file_submission(self, file_path, allowed_types, max_size_mb):
        """Validate a file for submission"""
        return self._validate_file(file_path, allowed_types, max_size_mb)

    def check_late_submission(self, assignment_id, submission_date=None):
        """Check if a submission is late"""
        try:
            if not submission_date:
                submission_date = datetime.now()
            elif isinstance(submission_date, str):
                submission_date = datetime.strptime(submission_date, '%Y-%m-%d %H:%M:%S')

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('SELECT due_date FROM assignments WHERE id = ?', (assignment_id,))
                result = cursor.fetchone()
            finally:
                conn.close()

            if result:
                due_date = datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
                return submission_date > due_date

            return False

        except Exception as e:
            print(f"Error checking late submission: {e}")
            return False

    def download_submission(self, submission_id, download_path=None):
        """Download a submission file"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT file_path, file_name FROM assignment_submissions WHERE id = ?', (submission_id,))
            result = cursor.fetchone()
            conn.close()

            if not result:
                print("Submission not found")
                return None

            source_path, file_name = result

            if not download_path:
                downloads_dir = paths.EXPORTS_SUBMISSIONS_DIR
                downloads_dir.mkdir(parents=True, exist_ok=True)
                download_path = str(downloads_dir / file_name)

            shutil.copy2(source_path, download_path)
            print(f"File downloaded to: {download_path}")
            return download_path

        except Exception as e:
            print(f"Error downloading submission: {e}")
            return None

    def export_submissions(self, assignment_id, export_path=None):
        """Export all submissions for an assignment as ZIP"""
        try:
            if not export_path:
                export_path = os.path.join(self.submission_dir, SUBDIR_EXPORTS, f'submissions_{assignment_id}.zip')

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT student_id, file_path, file_name
                    FROM assignment_submissions
                    WHERE assignment_id = ?
                ''', (assignment_id,))

                submissions = cursor.fetchall()
            finally:
                conn.close()

            with zipfile.ZipFile(export_path, 'w') as zipf:
                for student_id, file_path, file_name in submissions:
                    if os.path.exists(file_path):
                        arcname = f"{student_id}_{file_name}"
                        zipf.write(file_path, arcname)

            print(f"Submissions exported to: {export_path}")
            return export_path

        except Exception as e:
            print(f"Error exporting submissions: {e}")
            return None

    def view_submission_feedback(self, submission_id):
        """View feedback for a submission"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT grade, feedback, graded_by, graded_at
                FROM assignment_submissions
                WHERE id = ?
            ''', (submission_id,))

            result = cursor.fetchone()
            conn.close()

            return result

        except Exception as e:
            print(f"Error retrieving feedback: {e}")
            return None

    def preview_submission_file(self):
        """Preview submission files"""
        if not self._check_permission('view_all_submissions'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Show recent submissions
            cursor.execute('''
            SELECT s.id, s.file_name, s.file_path, st.first_name, st.last_name, a.title
            FROM assignment_submissions s
            JOIN students st ON s.student_id = st.student_id
            JOIN assignments a ON s.assignment_id = a.id
            ORDER BY s.submission_date DESC
            LIMIT 20
            ''')

            submissions = cursor.fetchall()

            if not submissions:
                print("No submissions found.")
                conn.close()
                return

            print("\nRecent Submissions:")
            for i, (sid, fname, fpath, first, last, title) in enumerate(submissions, 1):
                print(f"{i}. {fname} - {first} {last} ({title})")

            choice = input("\nSelect submission number to preview: ").strip()
            try:
                index = int(choice) - 1
                if 0 <= index < len(submissions):
                    file_path = submissions[index][2]
                    self._show_file_preview(file_path)
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a number.")

            conn.close()

        except Exception as e:
            print(f"Error previewing file: {e}")

    def _show_file_preview(self, file_path):
        """Show file preview based on file type"""
        if not os.path.exists(file_path):
            print("File not found.")
            return

        file_ext = os.path.splitext(file_path)[1].lower()

        try:
            if file_ext in ['.txt', '.py', '.java', '.cpp', '.c', '.js', '.html', '.css']:
                # Text files - show first 50 lines
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()[:50]
                    print("\n" + "="*60)
                    print(f"FILE PREVIEW: {os.path.basename(file_path)}")
                    print("="*60)
                    for i, line in enumerate(lines, 1):
                        print(f"{i:3d}: {line.rstrip()}")
                    if len(lines) == 50:
                        print("... (truncated)")
                    print("="*60)

            elif file_ext == '.pdf':
                print(f"PDF file: {os.path.basename(file_path)}")
                print(f"Size: {os.path.getsize(file_path)} bytes")
                print("PDF preview requires external viewer.")

            else:
                print(f"File: {os.path.basename(file_path)}")
                print(f"Type: {file_ext}")
                print(f"Size: {os.path.getsize(file_path)} bytes")
                print("Preview not available for this file type.")

        except Exception as e:
            print(f"Error previewing file: {e}")
