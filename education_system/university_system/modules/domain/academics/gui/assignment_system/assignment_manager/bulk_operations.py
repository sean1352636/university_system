"""Bulk operations on assignments - archive, delete, date changes, export, reminders"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import csv
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH


class BulkOperationsMixin:
    """Bulk assignment operations"""

    def download_all_submissions(self):
        """Download all submissions for selected assignment as ZIP"""
        selection = self.manage_assignments_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an assignment")
            return

        item = self.manage_assignments_tree.item(selection[0])
        assignment_id = item['values'][0]
        assignment_title = item['values'][1]

        try:
            # Ask for save location
            save_path = filedialog.asksaveasfilename(
                defaultextension=".zip",
                initialfile=f"{assignment_title.replace(' ', '_')}_submissions.zip",
                filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")]
            )

            if not save_path:
                return

            import zipfile
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT s.id, st.student_id, st.first_name, st.last_name, s.file_path
            FROM assignment_submissions s
            JOIN students st ON s.student_id = st.student_id
            WHERE s.assignment_id = ? AND s.file_path IS NOT NULL
            ''', (assignment_id,))

            submissions = cursor.fetchall()
            conn.close()

            if not submissions:
                messagebox.showinfo("No Submissions", "No submissions with files found for this assignment")
                return

            # Create ZIP file
            with zipfile.ZipFile(save_path, 'w') as zipf:
                for submission in submissions:
                    sub_id, student_id, fname, lname, file_path = submission
                    if file_path and os.path.exists(file_path):
                        # Create friendly filename
                        filename = f"{lname}_{fname}_{student_id}_{os.path.basename(file_path)}"
                        zipf.write(file_path, filename)

            messagebox.showinfo("Success", f"Downloaded {len(submissions)} submissions to:\n{save_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to download submissions: {e}")


    def bulk_archive_assignments(self):
        """Archive multiple selected assignments"""
        selections = self.manage_assignments_tree.selection()
        if not selections:
            messagebox.showwarning("Warning", "Please select assignments to archive")
            return

        if not messagebox.askyesno("Confirm", f"Archive {len(selections)} assignment(s)?"):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Ensure archived column exists
            cursor.execute("PRAGMA table_info(assignments)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'archived' not in columns:
                cursor.execute("ALTER TABLE assignments ADD COLUMN archived INTEGER DEFAULT 0")

            for selection in selections:
                item = self.manage_assignments_tree.item(selection)
                assignment_id = item['values'][0]
                cursor.execute("UPDATE assignments SET archived = 1, is_active = 0 WHERE id = ?",
                             (assignment_id,))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Archived {len(selections)} assignment(s)")
            self.load_managed_assignments()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to archive assignments: {e}")


    def bulk_delete_assignments(self):
        """Delete multiple selected assignments"""
        selections = self.manage_assignments_tree.selection()
        if not selections:
            messagebox.showwarning("Warning", "Please select assignments to delete")
            return

        if not messagebox.askyesno("Confirm Delete",
                                   f"Permanently delete {len(selections)} assignment(s)?\n\nThis will also delete all submissions!"):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            for selection in selections:
                item = self.manage_assignments_tree.item(selection)
                assignment_id = item['values'][0]

                # Delete submissions first
                cursor.execute("DELETE FROM assignment_submissions WHERE assignment_id = ?", (assignment_id,))
                # Delete assignment
                cursor.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Deleted {len(selections)} assignment(s)")
            self.load_managed_assignments()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete assignments: {e}")


    def bulk_change_due_dates(self):
        """Change due dates for multiple selected assignments"""
        selections = self.manage_assignments_tree.selection()
        if not selections:
            messagebox.showwarning("Warning", "Please select assignments to change due dates")
            return

        # Create dialog for date change
        dialog = tk.Toplevel(self.root)
        dialog.title("Change Due Dates")
        dialog.geometry("400x300")
        dialog.transient(self.root)

        ttk.Label(dialog, text=f"Change due dates for {len(selections)} assignment(s)",
                 font=('TkDefaultFont', 11, 'bold')).pack(pady=10)

        # Method selection
        method_frame = ttk.LabelFrame(dialog, text="Change Method", padding=10)
        method_frame.pack(fill='x', padx=10, pady=10)

        method_var = tk.StringVar(value="extend")
        ttk.Radiobutton(method_frame, text="Extend by days", variable=method_var,
                       value="extend").pack(anchor='w')
        ttk.Radiobutton(method_frame, text="Set specific date", variable=method_var,
                       value="specific").pack(anchor='w')

        # Days to extend
        extend_frame = ttk.Frame(method_frame)
        extend_frame.pack(fill='x', pady=5)
        ttk.Label(extend_frame, text="Days to extend:").pack(side='left')
        days_var = tk.StringVar(value="7")
        ttk.Entry(extend_frame, textvariable=days_var, width=10).pack(side='left', padx=(10, 0))

        # Specific date
        specific_frame = ttk.Frame(method_frame)
        specific_frame.pack(fill='x', pady=5)
        ttk.Label(specific_frame, text="New date (YYYY-MM-DD):").pack(side='left')
        date_var = tk.StringVar()
        ttk.Entry(specific_frame, textvariable=date_var, width=15).pack(side='left', padx=(10, 0))

        def apply_changes():
            try:
                method = method_var.get()
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                for selection in selections:
                    item = self.manage_assignments_tree.item(selection)
                    assignment_id = item['values'][0]

                    if method == "extend":
                        days = int(days_var.get())
                        cursor.execute('''
                        UPDATE assignments
                        SET due_date = datetime(due_date, '+' || ? || ' days')
                        WHERE id = ?
                        ''', (days, assignment_id))
                    else:
                        new_date = date_var.get()
                        # Validate date format
                        datetime.strptime(new_date, "%Y-%m-%d")
                        cursor.execute("UPDATE assignments SET due_date = ? WHERE id = ?",
                                     (new_date, assignment_id))

                conn.commit()
                conn.close()

                dialog.destroy()
                messagebox.showinfo("Success", "Due dates updated successfully")
                self.load_managed_assignments()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to change due dates: {e}")

        ttk.Button(dialog, text="Apply Changes", command=apply_changes).pack(pady=10)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack()


    def bulk_export_assignments(self):
        """Export data for multiple selected assignments"""
        selections = self.manage_assignments_tree.selection()
        if not selections:
            messagebox.showwarning("Warning", "Please select assignments to export")
            return

        try:
            save_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                initialfile="bulk_assignments_export.csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )

            if not save_path:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            all_data = []
            for selection in selections:
                item = self.manage_assignments_tree.item(selection)
                assignment_id = item['values'][0]

                cursor.execute('''
                SELECT a.title, a.module_code, st.student_id, st.first_name, st.last_name,
                       s.submission_date, s.status, s.grade, s.late_submission
                FROM assignments a
                LEFT JOIN assignment_submissions s ON a.id = s.assignment_id
                LEFT JOIN students st ON s.student_id = st.student_id
                WHERE a.id = ?
                ORDER BY a.title, st.last_name, st.first_name
                ''', (assignment_id,))

                all_data.extend(cursor.fetchall())

            conn.close()

            # Write to CSV
            with open(save_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Assignment', 'Module', 'Student ID', 'First Name', 'Last Name',
                               'Submission Date', 'Status', 'Grade', 'Late'])
                writer.writerows(all_data)

            messagebox.showinfo("Success", f"Exported {len(all_data)} records to:\n{save_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export assignments: {e}")


    def bulk_send_reminders(self):
        """Send reminders for multiple selected assignments"""
        selections = self.manage_assignments_tree.selection()
        if not selections:
            messagebox.showwarning("Warning", "Please select assignments to send reminders")
            return

        messagebox.showinfo("Bulk Reminders",
                           f"Sending reminders for {len(selections)} assignment(s)...\n\n"
                           "This feature would integrate with email system to send batch reminders.")
