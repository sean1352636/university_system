from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
import json
import hashlib


class StudentExperienceMixin:
    """Mixin providing student experience features: drafts, receipts, progress tracking,
    accessibility settings, and countdown info."""

    def manage_drafts(self):
        """View and manage saved drafts with version history"""
        if not self._check_permission('submit_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            student_id = self.auth.current_user['id']

            cursor.execute('''
            SELECT sd.id, sd.assignment_id, a.title, sd.version, sd.saved_at, sd.content
            FROM submission_drafts sd
            JOIN assignments a ON sd.assignment_id = a.id
            WHERE sd.student_id = ?
            ORDER BY sd.assignment_id, sd.version DESC
            ''', (student_id,))

            drafts = cursor.fetchall()

            if not drafts:
                print("\nNo saved drafts found.")
                conn.close()
                return

            print("\nSaved Drafts")
            print("=" * 60)

            current_assignment = None
            for draft_id, assignment_id, title, version, saved_at, content in drafts:
                if assignment_id != current_assignment:
                    current_assignment = assignment_id
                    print(f"\n  Assignment: {title}")
                    print(f"  {'-' * 50}")

                preview = content[:80] + "..." if content and len(content) > 80 else (content or "")
                print(f"    v{version} | {saved_at} | {preview}")

            print(f"\n{'=' * 60}")
            print("\nOptions:")
            print("1. Restore a draft version")
            print("2. Delete a draft")
            print("3. Return to menu")

            choice = input("\nSelect option: ").strip()

            if choice == '1':
                self.restore_draft()
            elif choice == '2':
                draft_id_input = input("Enter draft ID to delete: ").strip()
                try:
                    draft_id_val = int(draft_id_input)
                    cursor.execute('''
                    DELETE FROM submission_drafts
                    WHERE id = ? AND student_id = ?
                    ''', (draft_id_val, student_id))
                    conn.commit()
                    if cursor.rowcount > 0:
                        print("Draft deleted successfully.")
                    else:
                        print("Draft not found or you don't have permission to delete it.")
                except ValueError:
                    print("Invalid draft ID.")

            conn.close()

        except Exception as e:
            print(f"Error managing drafts: {e}")

    def save_draft(self):
        """Save a draft for an assignment with auto-incrementing version"""
        if not self._check_permission('submit_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            student_id = self.auth.current_user['id']

            cursor.execute('''
            SELECT id, title, module_code, due_date
            FROM assignments
            WHERE is_active = 1
            ORDER BY due_date
            ''')

            assignments = cursor.fetchall()

            if not assignments:
                print("\nNo active assignments found.")
                conn.close()
                return

            print("\nSelect Assignment to Save Draft:")
            print("=" * 50)
            for i, (aid, title, module, due_date) in enumerate(assignments, 1):
                print(f"{i}. {title} ({module}) - Due: {due_date}")

            choice = input("\nSelect assignment number: ").strip()
            try:
                index = int(choice) - 1
                if not (0 <= index < len(assignments)):
                    print("Invalid selection.")
                    conn.close()
                    return
            except ValueError:
                print("Please enter a number.")
                conn.close()
                return

            assignment_id = assignments[index][0]
            assignment_title = assignments[index][1]

            # Get current max version for this student/assignment
            cursor.execute('''
            SELECT COALESCE(MAX(version), 0)
            FROM submission_drafts
            WHERE student_id = ? AND assignment_id = ?
            ''', (student_id, assignment_id))

            current_version = cursor.fetchone()[0]
            new_version = current_version + 1

            print(f"\nSaving draft for: {assignment_title} (version {new_version})")
            print("Enter your draft content (type 'END' on a new line to finish):")

            lines = []
            while True:
                line = input()
                if line.strip() == 'END':
                    break
                lines.append(line)

            content = "\n".join(lines)

            if not content.strip():
                print("Draft content cannot be empty.")
                conn.close()
                return

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT INTO submission_drafts (student_id, assignment_id, version, content, saved_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (student_id, assignment_id, new_version, content, timestamp))

            conn.commit()
            conn.close()

            print(f"\nDraft saved successfully!")
            print(f"  Assignment: {assignment_title}")
            print(f"  Version:    {new_version}")
            print(f"  Saved at:   {timestamp}")

        except Exception as e:
            print(f"Error saving draft: {e}")

    def restore_draft(self):
        """Restore a specific draft version"""
        if not self._check_permission('submit_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            student_id = self.auth.current_user['id']

            cursor.execute('''
            SELECT sd.id, a.title, sd.version, sd.saved_at
            FROM submission_drafts sd
            JOIN assignments a ON sd.assignment_id = a.id
            WHERE sd.student_id = ?
            ORDER BY sd.assignment_id, sd.version DESC
            ''', (student_id,))

            drafts = cursor.fetchall()

            if not drafts:
                print("\nNo drafts available to restore.")
                conn.close()
                return

            print("\nAvailable Drafts:")
            print("=" * 60)
            for i, (draft_id, title, version, saved_at) in enumerate(drafts, 1):
                print(f"{i}. [{title}] v{version} - Saved: {saved_at}")

            choice = input("\nSelect draft to restore: ").strip()
            try:
                index = int(choice) - 1
                if not (0 <= index < len(drafts)):
                    print("Invalid selection.")
                    conn.close()
                    return
            except ValueError:
                print("Please enter a number.")
                conn.close()
                return

            selected_draft_id = drafts[index][0]
            selected_title = drafts[index][1]
            selected_version = drafts[index][2]

            cursor.execute('''
            SELECT content FROM submission_drafts WHERE id = ?
            ''', (selected_draft_id,))

            row = cursor.fetchone()
            if not row:
                print("Draft not found.")
                conn.close()
                return

            content = row[0]

            print(f"\nRestored Draft: {selected_title} (v{selected_version})")
            print("-" * 60)
            print(content)
            print("-" * 60)

            confirm = input("\nUse this draft as your current working copy? (y/n): ").strip().lower()
            if confirm == 'y':
                # Save as the latest version
                cursor.execute('''
                SELECT assignment_id FROM submission_drafts WHERE id = ?
                ''', (selected_draft_id,))
                assignment_id = cursor.fetchone()[0]

                cursor.execute('''
                SELECT COALESCE(MAX(version), 0)
                FROM submission_drafts
                WHERE student_id = ? AND assignment_id = ?
                ''', (student_id, assignment_id))

                new_version = cursor.fetchone()[0] + 1
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO submission_drafts (student_id, assignment_id, version, content, saved_at)
                VALUES (?, ?, ?, ?, ?)
                ''', (student_id, assignment_id, new_version, content, timestamp))

                conn.commit()
                print(f"Draft restored as version {new_version}.")
            else:
                print("Restore cancelled.")

            conn.close()

        except Exception as e:
            print(f"Error restoring draft: {e}")

    def view_submission_receipt(self, submission_id):
        """Display timestamped receipt with confirmation code for a submission"""
        if not self._check_permission('submit_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
            SELECT sr.id, sr.submission_id, sr.receipt_hash, sr.confirmation_code,
                   sr.generated_at, a.title, a.module_code
            FROM submission_receipts sr
            JOIN assignment_submissions asub ON sr.submission_id = asub.id
            JOIN assignments a ON asub.assignment_id = a.id
            WHERE sr.submission_id = ?
            ''', (submission_id,))

            receipt = cursor.fetchone()

            if not receipt:
                print(f"\nNo receipt found for submission #{submission_id}.")
                print("Generating receipt now...")
                self.generate_submission_receipt(submission_id)
                conn.close()
                return

            receipt_id, sub_id, receipt_hash, confirmation_code, generated_at, title, module = receipt

            print("\n" + "=" * 60)
            print("          SUBMISSION RECEIPT")
            print("=" * 60)
            print(f"  Receipt ID:         {receipt_id}")
            print(f"  Submission ID:      {sub_id}")
            print(f"  Assignment:         {title}")
            print(f"  Module:             {module}")
            print(f"  Confirmation Code:  {confirmation_code}")
            print(f"  Receipt Hash:       {receipt_hash}")
            print(f"  Generated At:       {generated_at}")
            print("=" * 60)
            print("  Keep this receipt for your records.")
            print("=" * 60)

            conn.close()

        except Exception as e:
            print(f"Error viewing receipt: {e}")

    def generate_submission_receipt(self, submission_id):
        """Generate SHA-256 receipt hash and confirmation code for a submission"""
        if not self._check_permission('submit_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check if receipt already exists
            cursor.execute('''
            SELECT id FROM submission_receipts WHERE submission_id = ?
            ''', (submission_id,))

            if cursor.fetchone():
                print("Receipt already exists for this submission.")
                self.view_submission_receipt(submission_id)
                conn.close()
                return

            # Get submission details
            cursor.execute('''
            SELECT asub.id, asub.student_id, asub.assignment_id, asub.submitted_at,
                   asub.file_path, a.title
            FROM assignment_submissions asub
            JOIN assignments a ON asub.assignment_id = a.id
            WHERE asub.id = ?
            ''', (submission_id,))

            submission = cursor.fetchone()

            if not submission:
                print(f"Submission #{submission_id} not found.")
                conn.close()
                return

            sub_id, student_id, assignment_id, submitted_at, file_path, title = submission

            # Generate SHA-256 hash from submission data
            hash_input = f"{sub_id}:{student_id}:{assignment_id}:{submitted_at}:{file_path}"
            receipt_hash = hashlib.sha256(hash_input.encode()).hexdigest()

            # Generate confirmation code (first 8 chars uppercase + timestamp suffix)
            timestamp_suffix = datetime.now().strftime('%Y%m%d%H%M%S')
            confirmation_code = f"CONF-{receipt_hash[:8].upper()}-{timestamp_suffix}"

            generated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT INTO submission_receipts (submission_id, receipt_hash, confirmation_code, generated_at)
            VALUES (?, ?, ?, ?)
            ''', (submission_id, receipt_hash, confirmation_code, generated_at))

            conn.commit()

            print("\n" + "=" * 60)
            print("       SUBMISSION RECEIPT GENERATED")
            print("=" * 60)
            print(f"  Assignment:         {title}")
            print(f"  Submission ID:      {sub_id}")
            print(f"  Confirmation Code:  {confirmation_code}")
            print(f"  Receipt Hash:       {receipt_hash}")
            print(f"  Generated At:       {generated_at}")
            print("=" * 60)
            print("  Keep this receipt for your records.")
            print("=" * 60)

            conn.close()

        except Exception as e:
            print(f"Error generating receipt: {e}")

    def view_progress_tracker(self):
        """Show multi-part assignment progress with visual ASCII progress bars"""
        if not self._check_permission('submit_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            student_id = self.auth.current_user['id']

            # Get assignments with their parts/components
            cursor.execute('''
            SELECT a.id, a.title, a.module_code, a.due_date,
                   a.total_parts, a.description
            FROM assignments a
            WHERE a.is_active = 1
            ORDER BY a.due_date
            ''')

            assignments = cursor.fetchall()

            if not assignments:
                print("\nNo active assignments found.")
                conn.close()
                return

            print("\nAssignment Progress Tracker")
            print("=" * 70)

            for aid, title, module, due_date, total_parts, description in assignments:
                total_parts = total_parts or 1

                # Count submitted parts
                cursor.execute('''
                SELECT COUNT(*)
                FROM assignment_submissions
                WHERE assignment_id = ? AND student_id = ? AND status = 'submitted'
                ''', (aid, student_id))

                completed = cursor.fetchone()[0]

                # Check for drafts
                cursor.execute('''
                SELECT COUNT(*)
                FROM submission_drafts
                WHERE assignment_id = ? AND student_id = ?
                ''', (aid, student_id))

                draft_count = cursor.fetchone()[0]

                # Calculate progress
                if total_parts > 0:
                    percentage = min(int((completed / total_parts) * 100), 100)
                else:
                    percentage = 0

                # Build ASCII progress bar (16 chars wide)
                bar_width = 16
                filled = int(bar_width * percentage / 100)
                empty = bar_width - filled
                progress_bar = "\u2588" * filled + "\u2591" * empty

                # Status indicator
                if percentage == 100:
                    status = "COMPLETE"
                elif percentage > 0:
                    status = "IN PROGRESS"
                else:
                    status = "NOT STARTED"

                print(f"\n  {title} ({module})")
                print(f"  Due: {due_date} | Status: {status}")
                print(f"  [{progress_bar}] {percentage}%  ({completed}/{total_parts} parts)")
                if draft_count > 0:
                    print(f"  Drafts saved: {draft_count}")

                # Time remaining
                try:
                    due_dt = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    try:
                        due_dt = datetime.strptime(due_date, '%Y-%m-%d')
                    except ValueError:
                        due_dt = None

                if due_dt:
                    remaining = due_dt - datetime.now()
                    if remaining.total_seconds() > 0:
                        days = remaining.days
                        hours = remaining.seconds // 3600
                        print(f"  Time remaining: {days}d {hours}h")
                    else:
                        print(f"  OVERDUE")

            print(f"\n{'=' * 70}")
            conn.close()

        except Exception as e:
            print(f"Error viewing progress: {e}")

    def manage_accessibility_settings(self):
        """Configure accessibility settings: extended time, high contrast, screen reader, font size"""
        if not self._check_permission('submit_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            student_id = self.auth.current_user['id']

            # Load current settings
            cursor.execute('''
            SELECT extended_time, high_contrast, screen_reader, font_size
            FROM accessibility_settings
            WHERE student_id = ?
            ''', (student_id,))

            row = cursor.fetchone()

            if row:
                extended_time, high_contrast, screen_reader, font_size = row
            else:
                extended_time = 0
                high_contrast = 0
                screen_reader = 0
                font_size = 14

            print("\nAccessibility Settings")
            print("=" * 50)
            print(f"1. Extended Time:   {'Enabled' if extended_time else 'Disabled'}")
            print(f"2. High Contrast:   {'Enabled' if high_contrast else 'Disabled'}")
            print(f"3. Screen Reader:   {'Enabled' if screen_reader else 'Disabled'}")
            print(f"4. Font Size:       {font_size}px")
            print(f"5. Save and return")
            print("=" * 50)

            changed = False

            while True:
                choice = input("\nSelect setting to toggle (or 5 to save): ").strip()

                if choice == '1':
                    extended_time = 0 if extended_time else 1
                    print(f"Extended Time: {'Enabled' if extended_time else 'Disabled'}")
                    changed = True
                elif choice == '2':
                    high_contrast = 0 if high_contrast else 1
                    print(f"High Contrast: {'Enabled' if high_contrast else 'Disabled'}")
                    changed = True
                elif choice == '3':
                    screen_reader = 0 if screen_reader else 1
                    print(f"Screen Reader: {'Enabled' if screen_reader else 'Disabled'}")
                    changed = True
                elif choice == '4':
                    size_input = input("Enter font size (10-32): ").strip()
                    try:
                        new_size = int(size_input)
                        if 10 <= new_size <= 32:
                            font_size = new_size
                            print(f"Font Size: {font_size}px")
                            changed = True
                        else:
                            print("Font size must be between 10 and 32.")
                    except ValueError:
                        print("Please enter a valid number.")
                elif choice == '5':
                    break
                else:
                    print("Invalid option. Please select 1-5.")

            if changed:
                if row:
                    cursor.execute('''
                    UPDATE accessibility_settings
                    SET extended_time = ?, high_contrast = ?, screen_reader = ?, font_size = ?
                    WHERE student_id = ?
                    ''', (extended_time, high_contrast, screen_reader, font_size, student_id))
                else:
                    cursor.execute('''
                    INSERT INTO accessibility_settings
                    (student_id, extended_time, high_contrast, screen_reader, font_size)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (student_id, extended_time, high_contrast, screen_reader, font_size))

                conn.commit()
                print("\nAccessibility settings saved successfully.")
            else:
                print("\nNo changes made.")

            conn.close()

        except Exception as e:
            print(f"Error managing accessibility settings: {e}")

    def view_countdown_info(self, assessment_id):
        """Show time remaining for an assessment, respecting extended time settings"""
        if not self._check_permission('submit_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get assessment details
            cursor.execute('''
            SELECT id, title, module_code, due_date, time_limit
            FROM assignments
            WHERE id = ?
            ''', (assessment_id,))

            assessment = cursor.fetchone()

            if not assessment:
                print(f"\nAssessment #{assessment_id} not found.")
                conn.close()
                return

            aid, title, module, due_date, time_limit = assessment
            time_limit = time_limit or 0

            # Check for extended time accessibility setting
            student_id = self.auth.current_user['id']
            cursor.execute('''
            SELECT extended_time FROM accessibility_settings
            WHERE student_id = ?
            ''', (student_id,))

            acc_row = cursor.fetchone()
            has_extended_time = acc_row[0] if acc_row else 0

            # Apply extended time (25% extra)
            effective_time_limit = time_limit
            if has_extended_time and time_limit > 0:
                effective_time_limit = int(time_limit * 1.25)

            print("\nAssessment Countdown")
            print("=" * 50)
            print(f"  Assessment:   {title}")
            print(f"  Module:       {module}")
            print(f"  Due Date:     {due_date}")

            if effective_time_limit > 0:
                hours = effective_time_limit // 60
                minutes = effective_time_limit % 60
                print(f"  Time Limit:   {hours}h {minutes}m")
                if has_extended_time:
                    orig_hours = time_limit // 60
                    orig_minutes = time_limit % 60
                    print(f"  (Extended from {orig_hours}h {orig_minutes}m - 25% extra time)")

            # Calculate countdown to due date
            try:
                due_dt = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    due_dt = datetime.strptime(due_date, '%Y-%m-%d')
                except ValueError:
                    print("  Unable to parse due date.")
                    conn.close()
                    return

            now = datetime.now()
            remaining = due_dt - now

            print(f"\n  Current Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")

            if remaining.total_seconds() > 0:
                days = remaining.days
                hours_rem = remaining.seconds // 3600
                minutes_rem = (remaining.seconds % 3600) // 60
                seconds_rem = remaining.seconds % 60

                print(f"  Time Remaining: {days}d {hours_rem}h {minutes_rem}m {seconds_rem}s")

                # Visual countdown bar (based on 30-day window)
                total_window = 30 * 24 * 3600  # 30 days in seconds
                elapsed_seconds = total_window - remaining.total_seconds()
                if elapsed_seconds < 0:
                    elapsed_seconds = 0
                elapsed_pct = min(int((elapsed_seconds / total_window) * 100), 100)

                bar_width = 16
                filled = int(bar_width * elapsed_pct / 100)
                empty = bar_width - filled
                countdown_bar = "\u2588" * filled + "\u2591" * empty

                print(f"  [{countdown_bar}] {elapsed_pct}% elapsed")

                # Urgency indicator
                if days == 0 and hours_rem < 6:
                    print("\n  *** URGENT: Less than 6 hours remaining! ***")
                elif days == 0:
                    print("\n  ** WARNING: Due today! **")
                elif days <= 2:
                    print("\n  * Note: Due within 2 days *")
            else:
                print(f"  Status: PAST DUE")
                overdue = now - due_dt
                print(f"  Overdue by: {overdue.days}d {overdue.seconds // 3600}h")

            print("=" * 50)
            conn.close()

        except Exception as e:
            print(f"Error viewing countdown: {e}")
