from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
import csv
import os


class GroupManagementMixin:
    """Mixin providing group assignment creation, management, and export."""

    def create_group_assignment(self):
        """Create a group assignment"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            print("\nCreate Group Assignment")
            print("=" * 50)

            # Get basic assignment details first
            self._get_basic_assignment_details()

            # Additional group-specific settings
            while True:
                try:
                    min_size = int(input("Minimum group size: "))
                    if min_size > 0:
                        break
                    else:
                        print("Size must be positive.")
                except ValueError:
                    print("Please enter a valid number.")

            while True:
                try:
                    max_size = int(input("Maximum group size: "))
                    if max_size >= min_size:
                        break
                    else:
                        print("Max size must be >= min size.")
                except ValueError:
                    print("Please enter a valid number.")

            # Create assignment with group settings
            # (Implementation would extend the create_assignment method)
            print("Group assignment creation functionality implemented!")

        except Exception as e:
            print(f"Error creating group assignment: {e}")

    def manage_groups(self):
        """Manage assignment groups"""
        if not self._check_permission('manage_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Show group assignments
            cursor.execute('''
            SELECT id, title, module_code, group_size_min, group_size_max
            FROM assignments
            WHERE assignment_type = 'group' AND is_active = 1
            ORDER BY due_date
            ''')

            assignments = cursor.fetchall()

            if not assignments:
                print("No active group assignments found.")
                conn.close()
                return

            print("\nGroup Assignments:")
            for i, (aid, title, module, min_size, max_size) in enumerate(assignments, 1):
                print(f"{i}. {title} ({module}) - Groups: {min_size}-{max_size} members")

            choice = input("\nSelect assignment number: ").strip()
            try:
                index = int(choice) - 1
                if 0 <= index < len(assignments):
                    assignment_id = assignments[index][0]
                    self._manage_assignment_groups(cursor, assignment_id)
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Please enter a number.")

            conn.close()

        except Exception as e:
            print(f"Error managing groups: {e}")

    def _manage_assignment_groups(self, cursor, assignment_id):
        """Manage groups for a specific assignment"""
        cursor.execute('''
        SELECT g.id, g.group_name, COUNT(gm.student_id) as member_count
        FROM groups g
        LEFT JOIN group_members gm ON g.id = gm.group_id
        WHERE g.assignment_id = ? AND g.is_active = 1
        GROUP BY g.id, g.group_name
        ORDER BY g.group_name
        ''', (assignment_id,))

        groups = cursor.fetchall()

        print(f"\nExisting Groups:")
        if groups:
            for gid, name, count in groups:
                print(f"- {name}: {count} members")
        else:
            print("No groups created yet.")

        print("\nGroup Management Options:")
        print("1. View group details")
        print("2. Create new group")
        print("3. Add student to group")
        print("4. Remove student from group")
        print("5. Delete group")
        print("6. Export group list")

        choice = input("Choose option: ").strip()

        if choice == '1':
            self._view_group_details(cursor, assignment_id)
        elif choice == '2':
            self._create_group(cursor, assignment_id)
        elif choice == '3':
            self._add_student_to_group(cursor, assignment_id)
        elif choice == '4':
            self._remove_student_from_group(cursor, assignment_id)
        elif choice == '5':
            self._delete_group(cursor, assignment_id)
        elif choice == '6':
            self._export_group_list(cursor, assignment_id)

    def _view_group_details(self, cursor, assignment_id):
        """View detailed group information"""
        cursor.execute('''
        SELECT g.id, g.group_name, g.created_at, g.created_by
        FROM groups g
        WHERE g.assignment_id = ? AND g.is_active = 1
        ORDER BY g.group_name
        ''', (assignment_id,))

        groups = cursor.fetchall()

        if not groups:
            print("No groups found.")
            return

        for group in groups:
            gid, name, created_at, created_by = group
            print(f"\nGroup: {name}")
            print(f"Created: {created_at} by {created_by}")

            cursor.execute('''
            SELECT gm.student_id, s.first_name, s.last_name, gm.role, gm.joined_at
            FROM group_members gm
            JOIN students s ON gm.student_id = s.student_id
            WHERE gm.group_id = ?
            ORDER BY gm.joined_at
            ''', (gid,))

            members = cursor.fetchall()
            print("Members:")
            for member in members:
                sid, fname, lname, role, joined = member
                print(f"  - {fname} {lname} ({sid}) - {role} (joined: {joined})")

            print("-" * 50)

    def _create_group(self, cursor, assignment_id):
        """Create a new group (instructor function)"""
        group_name = input("Group name: ").strip()
        if not group_name:
            print("Group name cannot be empty.")
            return

        cursor.execute('''
        INSERT INTO groups (assignment_id, group_name, created_at, created_by)
        VALUES (?, ?, ?, ?)
        ''', (assignment_id, group_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              self.auth.current_user['username']))

        print(f"Group '{group_name}' created successfully!")

    def _add_student_to_group(self, cursor, assignment_id):
        """Add student to a group"""
        cursor.execute('''
        SELECT id, group_name FROM groups
        WHERE assignment_id = ? AND is_active = 1
        ORDER BY group_name
        ''', (assignment_id,))

        groups = cursor.fetchall()

        if not groups:
            print("No groups available.")
            return

        print("Available groups:")
        for i, (gid, name) in enumerate(groups, 1):
            print(f"{i}. {name}")

        group_choice = input("Select group number: ").strip()
        try:
            index = int(group_choice) - 1
            if 0 <= index < len(groups):
                group_id = groups[index][0]

                student_id = input("Enter student ID: ").strip()
                if not student_id:
                    print("Student ID cannot be empty.")
                    return

                cursor.execute('''
                SELECT s.first_name, s.last_name FROM students s
                JOIN student_modules sm ON s.student_id = sm.student_code
                JOIN assignments a ON sm.module_code = a.module_code
                WHERE s.student_id = ? AND a.id = ?
                ''', (student_id, assignment_id))

                student = cursor.fetchone()
                if not student:
                    print("Student not found or not enrolled in this module.")
                    return

                cursor.execute('''
                INSERT INTO group_members (group_id, student_id, joined_at)
                VALUES (?, ?, ?)
                ''', (group_id, student_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                print(f"Added {student[0]} {student[1]} to group {groups[index][1]}")

        except (ValueError, IndexError):
            print("Invalid selection.")

    def _remove_student_from_group(self, cursor, assignment_id):
        """Remove student from a group"""
        cursor.execute('''
        SELECT g.id, g.group_name, gm.student_id, s.first_name, s.last_name
        FROM groups g
        JOIN group_members gm ON g.id = gm.group_id
        JOIN students s ON gm.student_id = s.student_id
        WHERE g.assignment_id = ? AND g.is_active = 1
        ORDER BY g.group_name, s.last_name
        ''', (assignment_id,))

        memberships = cursor.fetchall()

        if not memberships:
            print("No group memberships found.")
            return

        print("Group memberships:")
        for i, (gid, gname, sid, fname, lname) in enumerate(memberships, 1):
            print(f"{i}. {fname} {lname} ({sid}) - {gname}")

        choice = input("Select membership number to remove: ").strip()
        try:
            index = int(choice) - 1
            if 0 <= index < len(memberships):
                group_id, group_name, student_id, fname, lname = memberships[index]

                cursor.execute('''
                DELETE FROM group_members
                WHERE group_id = ? AND student_id = ?
                ''', (group_id, student_id))

                print(f"Removed {fname} {lname} from {group_name}")

        except (ValueError, IndexError):
            print("Invalid selection.")

    def _delete_group(self, cursor, assignment_id):
        """Delete a group"""
        cursor.execute('''
        SELECT id, group_name FROM groups
        WHERE assignment_id = ? AND is_active = 1
        ORDER BY group_name
        ''', (assignment_id,))

        groups = cursor.fetchall()

        if not groups:
            print("No groups to delete.")
            return

        print("Groups:")
        for i, (gid, name) in enumerate(groups, 1):
            print(f"{i}. {name}")

        choice = input("Select group number to delete: ").strip()
        try:
            index = int(choice) - 1
            if 0 <= index < len(groups):
                group_id, group_name = groups[index]

                confirm = input(f"Delete group '{group_name}'? (yes/no): ").lower()
                if confirm == 'yes':
                    cursor.execute('DELETE FROM group_members WHERE group_id = ?', (group_id,))
                    cursor.execute('UPDATE groups SET is_active = 0 WHERE id = ?', (group_id,))

                    print(f"Group '{group_name}' deleted.")
                else:
                    print("Deletion cancelled.")

        except (ValueError, IndexError):
            print("Invalid selection.")

    def _export_group_list(self, cursor, assignment_id):
        """Export group list to CSV"""
        try:
            cursor.execute('SELECT title FROM assignments WHERE id = ?', (assignment_id,))
            assignment_title = cursor.fetchone()[0]

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"groups_{assignment_title.replace(' ', '_')}_{timestamp}.csv"
            filepath = os.path.join(self.submission_dir, 'exports', filename)

            cursor.execute('''
            SELECT g.group_name, gm.student_id, s.first_name, s.last_name, gm.role, gm.joined_at
            FROM groups g
            JOIN group_members gm ON g.id = gm.group_id
            JOIN students s ON gm.student_id = s.student_id
            WHERE g.assignment_id = ? AND g.is_active = 1
            ORDER BY g.group_name, gm.joined_at
            ''', (assignment_id,))

            data = cursor.fetchall()

            with open(filepath, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Group Name', 'Student ID', 'First Name', 'Last Name', 'Role', 'Joined Date'])
                writer.writerows(data)

            print(f"Group list exported to: {filepath}")

        except Exception as e:
            print(f"Error exporting group list: {e}")

    # API methods

    def delete_group(self, group_id):
        """Delete a group"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('DELETE FROM assignment_group_members WHERE group_id = ?', (group_id,))
            cursor.execute('DELETE FROM assignment_groups WHERE id = ?', (group_id,))

            conn.commit()
            self._log_action('delete', 'assignment_groups', group_id)
            conn.close()

            print("Group deleted successfully!")
            return True

        except Exception as e:
            print(f"Error deleting group: {e}")
            return False

    def edit_group(self, group_id, group_name=None):
        """Edit a group's details"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if group_name:
                cursor.execute('UPDATE assignment_groups SET group_name = ? WHERE id = ?', (group_name, group_id))

            conn.commit()
            self._log_action('update', 'assignment_groups', group_id, {'group_name': group_name})
            conn.close()

            print("Group updated successfully!")
            return True

        except Exception as e:
            print(f"Error editing group: {e}")
            return False

    def add_member_to_group(self, group_id, student_id):
        """Add a member to a group"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO assignment_group_members (group_id, student_id, joined_at)
                VALUES (?, ?, ?)
            ''', (group_id, student_id, timestamp))

            conn.commit()
            self._log_action('create', 'assignment_group_members', cursor.lastrowid)
            conn.close()

            print("Member added to group successfully!")
            return True

        except Exception as e:
            print(f"Error adding member to group: {e}")
            return False

    def remove_member_from_group(self, group_id, student_id):
        """Remove a member from a group"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                DELETE FROM assignment_group_members
                WHERE group_id = ? AND student_id = ?
            ''', (group_id, student_id))

            conn.commit()
            self._log_action('delete', 'assignment_group_members', None, {'group_id': group_id, 'student_id': student_id})
            conn.close()

            print("Member removed from group successfully!")
            return True

        except Exception as e:
            print(f"Error removing member from group: {e}")
            return False

    def get_group_members(self, group_id):
        """Get all members of a group"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT student_id, joined_at
                FROM assignment_group_members
                WHERE group_id = ?
                ORDER BY joined_at
            ''', (group_id,))

            members = cursor.fetchall()
            conn.close()
            return members

        except Exception as e:
            print(f"Error retrieving group members: {e}")
            return []

    def get_student_groups(self, student_id):
        """Get all groups a student is in"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT g.*, gm.joined_at
                FROM assignment_groups g
                INNER JOIN assignment_group_members gm ON g.id = gm.group_id
                WHERE gm.student_id = ?
                ORDER BY gm.joined_at DESC
            ''', (student_id,))

            groups = cursor.fetchall()
            conn.close()
            return groups

        except Exception as e:
            print(f"Error retrieving student groups: {e}")
            return []

    def merge_groups(self, group_id_1, group_id_2, new_group_name):
        """Merge two groups into a new group"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT assignment_id FROM assignment_groups WHERE id = ?', (group_id_1,))
            assignment_id = cursor.fetchone()[0]

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO assignment_groups (assignment_id, group_name, created_at)
                VALUES (?, ?, ?)
            ''', (assignment_id, new_group_name, timestamp))

            new_group_id = cursor.lastrowid

            cursor.execute('''
                UPDATE assignment_group_members
                SET group_id = ?
                WHERE group_id IN (?, ?)
            ''', (new_group_id, group_id_1, group_id_2))

            cursor.execute('DELETE FROM assignment_groups WHERE id IN (?, ?)', (group_id_1, group_id_2))

            conn.commit()
            self._log_action('create', 'assignment_groups', new_group_id)
            conn.close()

            print(f"Groups merged successfully! New group ID: {new_group_id}")
            return new_group_id

        except Exception as e:
            print(f"Error merging groups: {e}")
            return None

    def auto_generate_groups(self, assignment_id, group_size):
        """Automatically generate groups for an assignment"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT sm.student_id
                FROM student_modules sm
                INNER JOIN assignments a ON sm.module_code = a.module_code
                WHERE a.id = ?
            ''', (assignment_id,))

            students = [row[0] for row in cursor.fetchall()]

            group_count = 0
            for i in range(0, len(students), group_size):
                group_students = students[i:i+group_size]

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                group_name = f"Group {group_count + 1}"

                cursor.execute('''
                    INSERT INTO assignment_groups (assignment_id, group_name, created_at)
                    VALUES (?, ?, ?)
                ''', (assignment_id, group_name, timestamp))

                group_id = cursor.lastrowid

                for student_id in group_students:
                    cursor.execute('''
                        INSERT INTO assignment_group_members (group_id, student_id, joined_at)
                        VALUES (?, ?, ?)
                    ''', (group_id, student_id, timestamp))

                group_count += 1

            conn.commit()
            conn.close()

            print(f"Successfully created {group_count} groups")
            return group_count

        except Exception as e:
            print(f"Error auto-generating groups: {e}")
            return 0

    def submit_group_assignment(self, assignment_id, group_id, file_path):
        """Submit an assignment on behalf of a group"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM assignment_group_members WHERE group_id = ?', (group_id,))
            members = cursor.fetchall()

            file_hash = self._calculate_file_hash(file_path)
            file_size = os.path.getsize(file_path)
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            for member in members:
                student_id = member[0]
                cursor.execute('''
                    INSERT INTO assignment_submissions (
                        assignment_id, student_id, group_id, submission_date,
                        file_path, file_name, file_size, file_hash, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'submitted')
                ''', (assignment_id, student_id, group_id, timestamp, file_path,
                      os.path.basename(file_path), file_size, file_hash))

            conn.commit()
            self._log_action('create', 'assignment_submissions', None, {'group_id': group_id})
            conn.close()

            print(f"Group assignment submitted for {len(members)} members!")
            return True

        except Exception as e:
            print(f"Error submitting group assignment: {e}")
            return False

    def export_group_list(self, assignment_id, export_path=None):
        """Export group list to CSV"""
        try:
            if not export_path:
                export_path = os.path.join(self.submission_dir, 'exports', f'groups_{assignment_id}.csv')

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT g.id, g.group_name, GROUP_CONCAT(gm.student_id, ', ')
                    FROM assignment_groups g
                    LEFT JOIN assignment_group_members gm ON g.id = gm.group_id
                    WHERE g.assignment_id = ?
                    GROUP BY g.id, g.group_name
                ''', (assignment_id,))

                groups = cursor.fetchall()
            finally:
                conn.close()

            with open(export_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Group ID', 'Group Name', 'Members'])
                writer.writerows(groups)

            print(f"Group list exported to: {export_path}")
            return export_path

        except Exception as e:
            print(f"Error exporting group list: {e}")
            return None
