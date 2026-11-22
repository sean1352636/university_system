from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608
from education_system.systems.university.domains.assessment.domain.assignments.core.constants import SUBDIR_EXPORTS
from datetime import datetime
import csv
import json
import os


class AssignmentCrudMixin:
    """Mixin providing assignment CRUD, bulk operations, drafts, and export."""

    def create_assignment(self):
        """Create a new assignment with enhanced features"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            print("\nCreate New Assignment")
            print("=" * 50)

            # Get available modules
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('SELECT module_code, module_name FROM modules ORDER BY module_code')
                modules = cursor.fetchall()

                if not modules:
                    print("No modules found in the system.")
                    return

                print("\nAvailable Modules:")
                for i, (code, name) in enumerate(modules, 1):
                    print(f"{i}. {code} - {name}")

                # Select module
                while True:
                    choice = input("\nSelect module number: ")
                    try:
                        index = int(choice) - 1
                        if 0 <= index < len(modules):
                            module_code = modules[index][0]
                            break
                        else:
                            print("Invalid selection.")
                    except ValueError:
                        print("Please enter a number.")

                # Basic assignment details
                title = input("Assignment title: ").strip()
                if not title:
                    print("Title cannot be empty.")
                    return

                description = input("Assignment description: ").strip()
                instructions = input("Detailed instructions: ").strip()

                # Assignment type
                print("\nAssignment Type:")
                print("1. Individual")
                print("2. Group")

                type_choice = input("Select type (1 or 2): ").strip()
                assignment_type = 'group' if type_choice == '2' else 'individual'

                group_min = group_max = 1
                if assignment_type == 'group':
                    while True:
                        try:
                            group_min = int(input("Minimum group size: "))
                            if group_min > 0:
                                break
                            else:
                                print("Size must be positive.")
                        except ValueError:
                            print("Please enter a valid number.")

                    while True:
                        try:
                            group_max = int(input("Maximum group size: "))
                            if group_max >= group_min:
                                break
                            else:
                                print("Max size must be >= min size.")
                        except ValueError:
                            print("Please enter a valid number.")

                # Due date
                while True:
                    due_date_str = input("Due date (YYYY-MM-DD HH:MM): ")
                    try:
                        due_date = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M")
                        if due_date <= datetime.now():
                            print("Due date must be in the future.")
                            continue
                        break
                    except ValueError:
                        print("Invalid date format. Use YYYY-MM-DD HH:MM")

                # Grading settings
                while True:
                    max_marks_str = input("Maximum marks (default 100): ").strip()
                    if not max_marks_str:
                        max_marks = 100
                        break
                    try:
                        max_marks = int(max_marks_str)
                        if max_marks <= 0:
                            print("Marks must be positive.")
                            continue
                        break
                    except ValueError:
                        print("Please enter a valid number.")

                # File settings
                print("\nAllowed file types (comma-separated, e.g., .pdf,.docx,.txt)")
                print("Leave blank to allow all types")
                file_types = input("Allowed types: ").strip()

                while True:
                    max_size_str = input("Maximum file size in MB (default 10): ").strip()
                    if not max_size_str:
                        max_size = 10
                        break
                    try:
                        max_size = int(max_size_str)
                        if max_size <= 0:
                            print("Size must be positive.")
                            continue
                        break
                    except ValueError:
                        print("Please enter a valid number.")

                # Late submission settings
                allow_late = input("Allow late submissions? (y/n): ").lower() == 'y'
                late_penalty = 0
                if allow_late:
                    penalty_str = input("Late penalty per day (percentage, default 0): ").strip()
                    if penalty_str:
                        try:
                            late_penalty = float(penalty_str)
                        except ValueError:
                            late_penalty = 0

                # Additional features
                auto_release = input("Auto-release grades when graded? (y/n): ").lower() == 'y'
                peer_review = input("Enable peer review? (y/n): ").lower() == 'y'

                # Warn when the cohort would have several summative deadlines in one week
                try:
                    from education_system.systems.university.domains.assessment.domain.assignments.assessment_qa import (
                        AssessmentQAService,
                    )
                    clashes = AssessmentQAService(self.db_path).deadline_clashes(
                        module_code, due_date.strftime('%Y-%m-%d %H:%M:%S'))
                except Exception:
                    clashes = []
                if clashes:
                    worst = max(len(c["deadlines"]) + 1 for c in clashes)
                    print(f"\nDeadline clash: {len(clashes)} student(s) would have up to {worst} "
                          "summative deadlines within a week of this one.")
                    if input("Create the assignment anyway? (y/n): ").strip().lower() != 'y':
                        print("Assignment not created.")
                        return

                # Save assignment
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO assignments
                (module_code, title, description, instructions, due_date, max_marks,
                 file_types_allowed, max_file_size_mb, assignment_type, group_size_min, group_size_max,
                 allow_late_submission, late_penalty_per_day, auto_release_grades, peer_review_enabled,
                 created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (module_code, title, description, instructions, due_date.strftime('%Y-%m-%d %H:%M:%S'),
                      max_marks, file_types, max_size, assignment_type, group_min, group_max,
                      allow_late, late_penalty, auto_release, peer_review,
                      self.auth.current_user['id'], timestamp, timestamp))

                assignment_id = cursor.lastrowid

                conn.commit()
            finally:
                conn.close()

            print(f"\nAssignment '{title}' created successfully!")
            print(f"Assignment ID: {assignment_id}")
            print(f"Type: {assignment_type}")
            print(f"Due date: {due_date.strftime('%Y-%m-%d %H:%M')}")

            # Log the action
            self._log_action('create_assignment', 'assignments', assignment_id,
                           None, {'title': title, 'module': module_code})

            # Send notifications to students
            self._notify_new_assignment(assignment_id, module_code)

        except Exception as e:
            print(f"Error creating assignment: {e}")

    def _get_basic_assignment_details(self):
        """Prompt for the details every assignment needs.

        Returns a dict (module_code, title, description, instructions,
        due_date, max_marks, file_types_allowed, max_file_size_mb) or None if
        the user gave up or there are no modules.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            modules = conn.execute(
                "SELECT module_code, module_name FROM modules "
                "WHERE module_code IS NOT NULL AND TRIM(module_code) <> '' "
                "ORDER BY module_code").fetchall()
        finally:
            conn.close()
        if not modules:
            print("No modules found in the system.")
            return None

        code = input("Module code (or '?' to list modules): ").strip()
        if code == '?':
            for mcode, name in modules:
                print(f"  {mcode} - {name}")
            code = input("Module code: ").strip()
        known = {m[0].lower(): m[0] for m in modules}
        if code.lower() not in known:
            print(f"Unknown module code '{code}'.")
            return None

        title = input("Assignment title: ").strip()
        if not title:
            print("Title cannot be empty.")
            return None
        description = input("Assignment description: ").strip()
        instructions = input("Detailed instructions: ").strip()

        for _ in range(3):
            due_str = input("Due date (YYYY-MM-DD HH:MM): ").strip()
            try:
                due = datetime.strptime(due_str, "%Y-%m-%d %H:%M")
            except ValueError:
                print("Invalid date format. Use YYYY-MM-DD HH:MM")
                continue
            if due <= datetime.now():
                print("Due date must be in the future.")
                continue
            break
        else:
            return None

        marks_str = input("Maximum marks (default 100): ").strip()
        try:
            max_marks = int(marks_str) if marks_str else 100
        except ValueError:
            max_marks = 0
        if max_marks <= 0:
            print("Maximum marks must be a positive whole number.")
            return None

        file_types = input("Allowed file types, comma-separated (blank = any): ").strip()
        size_str = input("Maximum file size in MB (default 10): ").strip()
        try:
            max_size = int(size_str) if size_str else 10
        except ValueError:
            max_size = 10

        return {
            'module_code': known[code.lower()],
            'title': title,
            'description': description,
            'instructions': instructions,
            'due_date': due.strftime('%Y-%m-%d %H:%M:%S'),
            'max_marks': max_marks,
            'file_types_allowed': file_types,
            'max_file_size_mb': max(1, max_size),
        }

    def manage_assignments(self):
        """List assignments and edit, reschedule, duplicate, archive or delete one."""
        if not self._check_permission('manage_assignments'):
            return
        while True:
            module = input("\nFilter by module code (Enter for all, 'q' to go back): ").strip()
            if module.lower() == 'q':
                return
            show_archived = input("Include archived assignments? (y/n): ").strip().lower() == 'y'
            where, params = [], []
            if module:
                where.append("a.module_code = ?")
                params.append(module)
            if not show_archived:
                where.append("COALESCE(a.is_active, 1) = 1")
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    "SELECT a.id, a.module_code, a.title, a.due_date, a.max_marks, "
                    "       COALESCE(a.is_active, 1) AS active, a.assignment_type, "
                    "       (SELECT COUNT(*) FROM assignment_submissions s WHERE s.assignment_id = a.id "
                    "          AND COALESCE(s.is_final_submission, 1) = 1) AS submissions, "
                    "       (SELECT COUNT(*) FROM assignment_submissions s WHERE s.assignment_id = a.id "
                    "          AND COALESCE(s.is_final_submission, 1) = 1 AND s.grade IS NOT NULL) AS marked "
                    "FROM assignments a "
                    + ("WHERE " + " AND ".join(where) + " " if where else "")
                    + "ORDER BY a.due_date DESC", params).fetchall()  # nosec B608 - fixed clauses
            finally:
                conn.close()
            if not rows:
                print("No assignments match.")
                continue

            print(f"\n{'ID':<5} {'Module':<11} {'Title':<34} {'Due':<17} {'Type':<11} {'Marked':>9}")
            print("-" * 92)
            for r in rows:
                title = (r['title'] or '') + ('' if r['active'] else ' (archived)')
                print(f"{r['id']:<5} {str(r['module_code'])[:10]:<11} {title[:33]:<34} "
                      f"{str(r['due_date'] or '')[:16]:<17} {str(r['assignment_type'] or '')[:10]:<11} "
                      f"{r['marked']}/{r['submissions']:<5}")

            choice = input("\nAssignment ID to manage (Enter to change filter): ").strip()
            if not choice.isdigit() or int(choice) not in {r['id'] for r in rows}:
                continue
            self._manage_one_assignment(int(choice))

    def _manage_one_assignment(self, assignment_id):
        details = self._assignment_row(assignment_id)
        if details is None:
            print("Assignment not found.")
            return
        print(f"\n#{assignment_id} {details['title']} ({details['module_code']})")
        print(f"  Due: {details['due_date']}   Max marks: {details['max_marks']}   "
              f"Type: {details['assignment_type']}   Active: {'yes' if details['is_active'] else 'no'}")
        if details['description']:
            print(f"  Description: {details['description']}")
        print("\n1. Edit details  2. Change due date  3. Duplicate  4. Archive  "
              "5. Restore from archive  6. Export submissions (CSV)  7. Delete  0. Back")
        action = input("Choice: ").strip()

        if action == '1':
            fields = {}
            for key, label in (('title', 'Title'), ('description', 'Description'),
                               ('instructions', 'Instructions'), ('max_marks', 'Maximum marks'),
                               ('file_types_allowed', 'Allowed file types'),
                               ('late_penalty_per_day', 'Late penalty % per day')):
                value = input(f"{label} [{details[key] if details[key] is not None else ''}]: ").strip()
                if value:
                    fields[key] = value
            if 'max_marks' in fields:
                try:
                    fields['max_marks'] = int(fields['max_marks'])
                except ValueError:
                    print("Maximum marks must be a whole number; left unchanged.")
                    del fields['max_marks']
            if 'late_penalty_per_day' in fields:
                try:
                    fields['late_penalty_per_day'] = float(fields['late_penalty_per_day'])
                except ValueError:
                    print("Late penalty must be a number; left unchanged.")
                    del fields['late_penalty_per_day']
            if fields:
                self.edit_assignment(assignment_id, **fields)
            else:
                print("Nothing changed.")
        elif action == '2':
            new_due = input("New due date (YYYY-MM-DD HH:MM): ").strip()
            try:
                parsed = datetime.strptime(new_due, "%Y-%m-%d %H:%M")
            except ValueError:
                print("Invalid date format.")
                return
            try:
                from education_system.systems.university.domains.assessment.domain.assignments.assessment_qa import (
                    AssessmentQAService,
                )
                clashes = AssessmentQAService(self.db_path).deadline_clashes(
                    details['module_code'], parsed.strftime('%Y-%m-%d %H:%M:%S'), assignment_id)
            except Exception:
                clashes = []
            if clashes and input(f"{len(clashes)} student(s) would have a deadline clash. Continue? (y/n): "
                                 ).strip().lower() != 'y':
                return
            self.edit_assignment(assignment_id, due_date=parsed.strftime('%Y-%m-%d %H:%M:%S'))
        elif action == '3':
            new_id = self.duplicate_assignment(assignment_id)
            if new_id:
                print("The copy is inactive: change its due date, then restore it (option 5).")
        elif action == '4':
            self.archive_assignment(assignment_id)
        elif action == '5':
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("UPDATE assignments SET is_active = 1, updated_at = ? WHERE id = ?",
                             (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), assignment_id))
                conn.commit()
            finally:
                conn.close()
            self._log_action('update', 'assignments', assignment_id, None, {'is_active': 1})
            print("Assignment restored.")
        elif action == '6':
            self.export_assignment_data(assignment_id)
        elif action == '7':
            if details['submissions']:
                print(f"This assignment has {details['submissions']} submission(s); "
                      "deleting removes them permanently. Archive it instead unless you are sure.")
            if input(f"Type the assignment ID ({assignment_id}) to confirm deletion: ").strip() == str(assignment_id):
                self.delete_assignment(assignment_id)
            else:
                print("Not deleted.")

    def _assignment_row(self, assignment_id):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT a.*, COALESCE(a.is_active, 1) AS is_active, "
                "       (SELECT COUNT(*) FROM assignment_submissions s "
                "         WHERE s.assignment_id = a.id) AS submissions "
                "FROM assignments a WHERE a.id = ?", (assignment_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def _notify_new_assignment(self, assignment_id, module_code):
        """Send notifications about new assignment"""
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                # Get assignment details
                cursor.execute('SELECT title, due_date FROM assignments WHERE id = ?', (assignment_id,))
                title, due_date = cursor.fetchone()

                # Get students in the module
                cursor.execute('''
                SELECT u.id FROM users u
                JOIN students s ON u.student_id = s.student_id
                JOIN student_modules sm ON s.student_id = sm.student_id
                WHERE sm.module_code = ?
                ''', (module_code,))

                student_users = cursor.fetchall()

                # Send notifications
                for (user_id,) in student_users:
                    self._send_notification(
                        user_id,
                        "New Assignment Posted",
                        f"New assignment '{title}' has been posted for {module_code}. Due: {due_date}",
                        "new_assignment",
                        assignment_id
                    )
            finally:
                conn.close()

            print(f"Notifications sent to {len(student_users)} students.")

        except Exception as e:
            print(f"Error sending notifications: {e}")

    def edit_assignment(self, assignment_id, **kwargs):
        """Edit an existing assignment"""
        try:
            if not self._check_permission('manage_assignments'):
                print("Permission denied")
                return False

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                # Build UPDATE query dynamically
                update_fields = []
                values = []
                for key, value in kwargs.items():
                    if key in ['title', 'description', 'due_date', 'max_marks', 'instructions',
                              'file_types_allowed', 'max_file_size_mb', 'allow_late_submission',
                              'late_penalty_per_day', 'assignment_type']:
                        update_fields.append(f"{validate_identifier(key, 'column')} = ?")
                        values.append(value)

                if not update_fields:
                    print("No valid fields to update")
                    return False

                # Add updated_at timestamp
                update_fields.append("updated_at = ?")
                values.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                values.append(assignment_id)

                query = f"UPDATE assignments SET {', '.join(update_fields)} WHERE id = ?"
                cursor.execute(query, values)

                conn.commit()
                self._log_action('update', 'assignments', assignment_id, kwargs)
            finally:
                conn.close()

            print("Assignment updated successfully!")
            return True

        except Exception as e:
            print(f"Error updating assignment: {e}")
            return False

    def delete_assignment(self, assignment_id):
        """Delete an assignment and its related data"""
        try:
            if not self._check_permission('delete_assignments'):
                print("Permission denied")
                return False

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                # Delete related data
                cursor.execute('DELETE FROM assignment_submissions WHERE assignment_id = ?', (assignment_id,))
                cursor.execute('DELETE FROM group_members WHERE group_id IN (SELECT id FROM groups '
                               'WHERE assignment_id = ?)', (assignment_id,))
                cursor.execute('DELETE FROM groups WHERE assignment_id = ?', (assignment_id,))
                cursor.execute('DELETE FROM peer_review_assignments WHERE assignment_id = ?', (assignment_id,))
                cursor.execute('DELETE FROM extension_requests WHERE assignment_id = ?', (assignment_id,))
                cursor.execute('DELETE FROM assignments WHERE id = ?', (assignment_id,))

                conn.commit()
                self._log_action('delete', 'assignments', assignment_id)
            finally:
                conn.close()

            print("Assignment deleted successfully!")
            return True

        except Exception as e:
            print(f"Error deleting assignment: {e}")
            return False

    def duplicate_assignment(self, assignment_id):
        """Duplicate an existing assignment"""
        try:
            if not self._check_permission('manage_assignments'):
                print("Permission denied")
                return None

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                # Read by column name: the established table's column order
                # differs from the bootstrap definition, so positions drifted.
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM assignments WHERE id = ?', (assignment_id,))
                assignment = cursor.fetchone()

                if not assignment:
                    print("Assignment not found")
                    return None

                # Copied inactive, so it can be re-dated before students see it.
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                copy = {key: assignment[key] for key in (
                    'module_code', 'description', 'due_date', 'max_marks', 'file_types_allowed',
                    'max_file_size_mb', 'assignment_type', 'allow_late_submission',
                    'late_penalty_per_day', 'instructions', 'rubric_id', 'group_size_min',
                    'group_size_max', 'auto_release_grades', 'peer_review_enabled',
                    'assessment_kind', 'module_weight_pct', 'anonymous_marking', 'word_limit',
                    'word_limit_tolerance_pct', 'word_limit_penalty_pct', 'moderation_required',
                    'moderation_sample_pct') if key in assignment.keys()}
                copy.update({
                    'title': f"{assignment['title']} (Copy)",
                    # created_by references users.id — the staff member's user id,
                    # not a student number.
                    'created_by': self.auth.current_user.get('id') or assignment['created_by'],
                    'created_at': timestamp, 'updated_at': timestamp, 'is_active': 0,
                })
                columns = ", ".join(f'"{k}"' for k in copy)
                marks = ", ".join("?" for _ in copy)
                cursor.execute(f"INSERT INTO assignments ({columns}) VALUES ({marks})",  # nosec B608 - fixed keys
                               tuple(copy.values()))

                new_id = cursor.lastrowid
                conn.commit()
                self._log_action('create', 'assignments', new_id)
            finally:
                conn.close()

            print(f"Assignment duplicated successfully! New ID: {new_id}")
            return new_id

        except Exception as e:
            print(f"Error duplicating assignment: {e}")
            return None

    def archive_assignment(self, assignment_id):
        """Archive an assignment"""
        try:
            if not self._check_permission('manage_assignments'):
                print("Permission denied")
                return False

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('UPDATE assignments SET is_active = 0 WHERE id = ?', (assignment_id,))

                conn.commit()
                self._log_action('update', 'assignments', assignment_id, {'is_active': 0})
            finally:
                conn.close()

            print("Assignment archived successfully!")
            return True

        except Exception as e:
            print(f"Error archiving assignment: {e}")
            return False

    def get_assignments_for_module(self, module_code, active_only=True):
        """Get all assignments for a specific module"""
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                if active_only:
                    cursor.execute('''
                        SELECT * FROM assignments
                        WHERE module_code = ? AND is_active = 1
                        ORDER BY due_date
                    ''', (module_code,))
                else:
                    cursor.execute('''
                        SELECT * FROM assignments
                        WHERE module_code = ?
                        ORDER BY due_date
                    ''', (module_code,))

                assignments = cursor.fetchall()
                return assignments
            finally:
                conn.close()

        except Exception as e:
            print(f"Error retrieving assignments: {e}")
            return []

    def get_assignments_for_student(self, student_id=None):
        """Get all assignments for a student's enrolled modules"""
        try:
            if not student_id:
                student_id = self._get_student_id()

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT a.* FROM assignments a
                    INNER JOIN student_modules sm ON a.module_code = sm.module_code
                    WHERE sm.student_id = ? AND a.is_active = 1
                    ORDER BY a.due_date
                ''', (student_id,))

                assignments = cursor.fetchall()
                return assignments
            finally:
                conn.close()

        except Exception as e:
            print(f"Error retrieving student assignments: {e}")
            return []

    def get_assignment_details(self, assignment_id):
        """Get detailed information about an assignment"""
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('SELECT * FROM assignments WHERE id = ?', (assignment_id,))
                assignment = cursor.fetchone()
                return assignment
            finally:
                conn.close()

        except Exception as e:
            print(f"Error retrieving assignment details: {e}")
            return None

    def save_assignment_draft(self, draft_data):
        """Save an assignment draft"""
        try:
            user_id = self._get_student_id()
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                # Create draft table if not exists
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS assignment_drafts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        draft_name TEXT,
                        draft_data TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                ''')
                # Migrate legacy tables created before draft_name existed.
                columns = {row[1] for row in cursor.execute('PRAGMA table_info(assignment_drafts)')}
                if 'draft_name' not in columns:
                    cursor.execute('ALTER TABLE assignment_drafts ADD COLUMN draft_name TEXT')

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                draft_json = json.dumps(draft_data)

                cursor.execute('''
                    INSERT INTO assignment_drafts (user_id, draft_data, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, draft_json, timestamp, timestamp))

                draft_id = cursor.lastrowid
                conn.commit()
            finally:
                conn.close()

            print(f"Draft saved successfully! ID: {draft_id}")
            return draft_id

        except Exception as e:
            print(f"Error saving draft: {e}")
            return None

    def load_assignment_draft(self, draft_id):
        """Load an assignment draft"""
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('SELECT draft_data FROM assignment_drafts WHERE id = ?', (draft_id,))
                result = cursor.fetchone()
            finally:
                conn.close()

            if result:
                return json.loads(result[0])
            return None

        except Exception as e:
            print(f"Error loading draft: {e}")
            return None

    def bulk_archive_assignments(self, assignment_ids):
        """Archive multiple assignments"""
        try:
            if not self._check_permission('manage_assignments'):
                print("Permission denied")
                return False

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                placeholders = ','.join('?' * len(assignment_ids))
                cursor.execute('UPDATE assignments SET is_active = 0 WHERE id IN (' + placeholders + ')', assignment_ids)

                conn.commit()
            finally:
                conn.close()

            print(f"Successfully archived {len(assignment_ids)} assignments")
            return True

        except Exception as e:
            print(f"Error bulk archiving: {e}")
            return False

    def bulk_delete_assignments(self, assignment_ids):
        """Delete multiple assignments"""
        try:
            if not self._check_permission('delete_assignments'):
                print("Permission denied")
                return False

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                placeholders = ','.join('?' * len(assignment_ids))

                # Delete related data
                cursor.execute('DELETE FROM assignment_submissions WHERE assignment_id IN (' + placeholders + ')', assignment_ids)
                cursor.execute('DELETE FROM group_members WHERE group_id IN (SELECT id FROM groups '
                               'WHERE assignment_id IN (' + placeholders + '))', assignment_ids)
                cursor.execute('DELETE FROM groups WHERE assignment_id IN (' + placeholders + ')', assignment_ids)
                cursor.execute('DELETE FROM peer_review_assignments WHERE assignment_id IN (' + placeholders + ')', assignment_ids)
                cursor.execute('DELETE FROM extension_requests WHERE assignment_id IN (' + placeholders + ')', assignment_ids)
                cursor.execute('DELETE FROM assignments WHERE id IN (' + placeholders + ')', assignment_ids)

                conn.commit()
            finally:
                conn.close()

            print(f"Successfully deleted {len(assignment_ids)} assignments")
            return True

        except Exception as e:
            print(f"Error bulk deleting: {e}")
            return False

    def bulk_change_due_dates(self, assignment_ids, new_due_date):
        """Change due dates for multiple assignments"""
        try:
            if not self._check_permission('manage_assignments'):
                print("Permission denied")
                return False

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                placeholders = ','.join('?' * len(assignment_ids))
                cursor.execute('UPDATE assignments SET due_date = ? WHERE id IN (' + placeholders + ')', [new_due_date] + assignment_ids)

                conn.commit()
            finally:
                conn.close()

            print(f"Successfully updated due dates for {len(assignment_ids)} assignments")
            return True

        except Exception as e:
            print(f"Error bulk updating due dates: {e}")
            return False

    def export_assignment_data(self, assignment_id, export_path=None):
        """Export assignment data to CSV"""
        try:
            if not export_path:
                export_path = os.path.join(self.submission_dir, SUBDIR_EXPORTS, f'assignment_{assignment_id}.csv')

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT
                        s.student_id,
                        s.submission_date,
                        s.status,
                        s.grade,
                        s.feedback,
                        s.late_submission
                    FROM assignment_submissions s
                    WHERE s.assignment_id = ?
                    ORDER BY s.submission_date
                ''', (assignment_id,))

                submissions = cursor.fetchall()
            finally:
                conn.close()

            with open(export_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Student ID', 'Submission Date', 'Status', 'Grade', 'Feedback', 'Late'])
                writer.writerows(submissions)

            print(f"Data exported to: {export_path}")
            return export_path

        except Exception as e:
            print(f"Error exporting data: {e}")
            return None

    def send_assignment_notifications(self, assignment_id, notification_type='assignment_created'):
        """Send notifications about an assignment to all enrolled students"""
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                # Get assignment details
                cursor.execute('SELECT module_code, title FROM assignments WHERE id = ?', (assignment_id,))
                assignment = cursor.fetchone()

                if not assignment:
                    print("Assignment not found")
                    return False

                module_code, title = assignment

                # Get all enrolled students
                cursor.execute('SELECT student_id FROM student_modules WHERE module_code = ?', (module_code,))
                students = cursor.fetchall()

                # Send notification to each student
                for student in students:
                    student_id = student[0]
                    message = f"New assignment posted: {title}"
                    self._send_notification(student_id, title, message, notification_type, assignment_id)
            finally:
                conn.close()

            print(f"Notifications sent to {len(students)} students")
            return True

        except Exception as e:
            print(f"Error sending notifications: {e}")
            return False

    def check_overdue_assignments(self):
        """Check for overdue assignments and send reminders"""
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    SELECT id, module_code, title FROM assignments
                    WHERE due_date < ? AND is_active = 1
                ''', (current_time,))

                overdue_assignments = cursor.fetchall()
            finally:
                conn.close()

            print(f"Found {len(overdue_assignments)} overdue assignments")
            return overdue_assignments

        except Exception as e:
            print(f"Error checking overdue assignments: {e}")
            return []
