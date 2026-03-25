"""Data loading helpers for combo boxes and filters"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH


class DataLoadersMixin:
    """Data loading operations for filters and combo boxes"""

    def load_modules_for_filter(self, combo):
        """Load modules for filtering"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT module_code, module_name FROM modules ORDER BY module_code')
            modules = cursor.fetchall()

            module_list = ["All Modules"] + [f"{code} - {name}" for code, name in modules]
            combo['values'] = module_list
            combo.set("All Modules")

            conn.close()

        except Exception as e:
            print(f"Error loading modules: {e}")

    def load_assignments_for_group_filter(self, combo):
        """Load assignments that have groups"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT DISTINCT a.id, a.title
            FROM assignments a
            WHERE a.assignment_type = 'group'
            ORDER BY a.title
            ''')

            assignments = cursor.fetchall()
            conn.close()

            combo_values = ["All Assignments"] + [f"{aid} - {title}" for aid, title in assignments]
            combo['values'] = combo_values
            if combo_values:
                combo.current(0)

        except Exception as e:
            print(f"Error loading assignments: {e}")


    def load_assignments_for_message(self, combo):
        """Load assignments for message reference"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT id, title, module_code FROM assignments WHERE is_active = 1 ORDER BY due_date DESC')
            assignments = cursor.fetchall()

            assignment_list = ["None"] + [f"{title} ({module})" for aid, title, module in assignments]
            combo['values'] = assignment_list
            combo.set("None")

            # Create mapping for assignment IDs
            self.message_assignment_map = {"None": None}
            for aid, title, module in assignments:
                self.message_assignment_map[f"{title} ({module})"] = aid

            conn.close()

        except Exception as e:
            print(f"Error loading assignments: {e}")


    def load_my_assignments_filter(self, combo):
        """Load assignments for submission filter"""
        try:
            student_id = self.assignment_system._get_student_id()
            if not student_id:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT DISTINCT a.id, a.title, a.module_code
                FROM assignments a
                JOIN student_modules sm ON a.module_code = sm.module_code
                WHERE sm.student_id = ?
                ORDER BY a.due_date DESC
                ''', (student_id,))

                assignments = cursor.fetchall()

                assignment_list = ["All Assignments"] + [f"{title} ({module})" for aid, title, module in assignments]
                combo['values'] = assignment_list
                combo.set("All Assignments")

                # Create mapping
                self.submission_assignment_map = {"All Assignments": None}
                for aid, title, module in assignments:
                    self.submission_assignment_map[f"{title} ({module})"] = aid

            finally:
                conn.close()

        except Exception as e:
            print(f"Error loading assignments: {e}")


    def load_extension_assignments(self, combo):
        """Load assignments available for extension request"""
        try:
            student_id = self._get_student_id_safe()
            # Show all assignments if no student ID (for admin/instructor)

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                if student_id:
                    cursor.execute('''
                    SELECT a.id, a.title, a.module_code, a.due_date
                    FROM assignments a
                    JOIN student_modules sm ON a.module_code = sm.module_code
                    WHERE sm.student_id = ? AND a.is_active = 1
                    AND a.due_date > datetime('now', '-7 days')
                    ORDER BY a.due_date
                    ''', (student_id,))
                else:
                    # Show all active assignments if no student ID
                    cursor.execute('''
                    SELECT a.id, a.title, a.module_code, a.due_date
                    FROM assignments a
                    WHERE a.is_active = 1
                    AND a.due_date > datetime('now', '-7 days')
                    ORDER BY a.due_date
                    ''')

                assignments = cursor.fetchall()

                assignment_list = []
                self.ext_assignment_map = {}

                for aid, title, module, due_date in assignments:
                    display_text = f"{title} ({module}) - Due: {due_date}"
                    assignment_list.append(display_text)
                    self.ext_assignment_map[display_text] = aid

                combo['values'] = assignment_list
            finally:
                conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load assignments: {e}")


    def _load_assignments_for_compose(self, assignment_combo):
        """Load assignments for message compose"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, title, module_code
                FROM assignments
                WHERE is_active = 1
                ORDER BY due_date DESC
                LIMIT 50
            ''')

            assignments = cursor.fetchall()
            conn.close()

            values = ["(No Assignment)"] + [f"{a[0]}: {a[1]} ({a[2]})" for a in assignments]
            assignment_combo['values'] = values
            assignment_combo.current(0)

        except Exception as e:
            print(f"Error loading assignments: {e}")

    def export_assignment_data(self):
        """Export assignment data"""
        selection = self.manage_assignments_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an assignment to export")
            return

        item = self.manage_assignments_tree.item(selection[0])
        assignment_id = item['values'][0]
        assignment_title = item['values'][1]

        try:
            save_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                initialfile=f"{assignment_title.replace(' ', '_')}_data.csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )

            if not save_path:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT st.student_id, st.first_name, st.last_name, s.submission_date,
                       s.status, s.grade, s.late_submission, s.late_days, s.feedback
                FROM assignment_submissions s
                JOIN students st ON s.student_id = st.student_id
                WHERE s.assignment_id = ?
                ORDER BY st.last_name, st.first_name
                ''', (assignment_id,))

                data = cursor.fetchall()

                import csv
                with open(save_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Student ID', 'First Name', 'Last Name', 'Submission Date',
                                   'Status', 'Grade', 'Late Submission', 'Late Days', 'Feedback'])
                    writer.writerows(data)

            finally:
                conn.close()
            messagebox.showinfo("Success", f"Assignment data exported to: {save_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export data: {e}")
