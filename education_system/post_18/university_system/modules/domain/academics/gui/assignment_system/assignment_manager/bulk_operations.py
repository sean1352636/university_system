"""Bulk operations on assignments - archive, delete, date changes, export, reminders"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import csv
from datetime import datetime
from education_system.post_18.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH


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
            try:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT s.id, st.student_id, st.first_name, st.last_name, s.file_path
                FROM assignment_submissions s
                JOIN students st ON s.student_id = st.student_id
                WHERE s.assignment_id = ? AND s.file_path IS NOT NULL
                ''', (assignment_id,))

                submissions = cursor.fetchall()
            finally:
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
            try:
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
            finally:
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
            try:
                cursor = conn.cursor()
                cursor.execute("PRAGMA foreign_keys = OFF")

                for selection in selections:
                    item = self.manage_assignments_tree.item(selection)
                    assignment_id = item['values'][0]

                    # Delete all related records
                    cursor.execute("DELETE FROM assignment_submissions WHERE assignment_id = ?", (assignment_id,))
                    # Delete group members for groups belonging to this assignment
                    cursor.execute("""
                        DELETE FROM group_members WHERE group_id IN (
                            SELECT id FROM groups WHERE assignment_id = ?
                        )
                    """, (assignment_id,))
                    cursor.execute("DELETE FROM groups WHERE assignment_id = ?", (assignment_id,))
                    # Delete the assignment
                    cursor.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))

                cursor.execute("PRAGMA foreign_keys = ON")
                conn.commit()
            finally:
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

        # Option to email students
        notify_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(dialog, text="Email students about due date change",
                       variable=notify_var).pack(anchor='w', padx=10, pady=(5, 0))

        def apply_changes():
            try:
                method = method_var.get()
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                updated_assignments = []

                for selection in selections:
                    item = self.manage_assignments_tree.item(selection)
                    assignment_id = item['values'][0]
                    assignment_title = item['values'][1]
                    module_code = item['values'][2]

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

                    # Fetch the new due date
                    cursor.execute("SELECT due_date FROM assignments WHERE id = ?", (assignment_id,))
                    row = cursor.fetchone()
                    new_due = row[0] if row else "Unknown"
                    updated_assignments.append({
                        'id': assignment_id, 'title': assignment_title,
                        'module': module_code, 'new_due': new_due
                    })

                conn.commit()
                conn.close()

                dialog.destroy()
                messagebox.showinfo("Success", "Due dates updated successfully")
                self.load_managed_assignments()

                # Email students about the change
                if notify_var.get() and updated_assignments:
                    self._email_due_date_change(updated_assignments)

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
            try:
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

            finally:
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

        # Gather assignment info
        assignments_info = []
        for selection in selections:
            item = self.manage_assignments_tree.item(selection)
            vals = item['values']
            assignments_info.append({
                'id': vals[0], 'title': vals[1], 'module': vals[2],
                'due_date': vals[4] if len(vals) > 4 else ''
            })

        # Create reminder dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Send Assignment Reminders")
        dialog.geometry("600x550")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=f"Send Reminders for {len(assignments_info)} Assignment(s)",
                 font=('TkDefaultFont', 12, 'bold')).pack(anchor='w', padx=10, pady=(10, 5))

        # Assignment list
        list_frame = ttk.LabelFrame(dialog, text="Selected Assignments", padding=5)
        list_frame.pack(fill='x', padx=10, pady=(0, 10))
        for a in assignments_info:
            ttk.Label(list_frame,
                     text=f"  {a['title']} ({a['module']}) - Due: {a['due_date']}").pack(anchor='w')

        # Recipient type
        recipient_frame = ttk.LabelFrame(dialog, text="Recipients", padding=10)
        recipient_frame.pack(fill='x', padx=10, pady=(0, 10))

        recipient_var = tk.StringVar(value="not_submitted")
        ttk.Radiobutton(recipient_frame, text="Students who haven't submitted",
                       variable=recipient_var, value="not_submitted").pack(anchor='w')
        ttk.Radiobutton(recipient_frame, text="All enrolled students",
                       variable=recipient_var, value="enrolled").pack(anchor='w')

        # Message
        message_frame = ttk.LabelFrame(dialog, text="Email Message", padding=10)
        message_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        ttk.Label(message_frame, text="Subject:").pack(anchor='w')
        subject_var = tk.StringVar(value="Assignment Reminder")
        ttk.Entry(message_frame, textvariable=subject_var).pack(fill='x', pady=(0, 5))

        ttk.Label(message_frame, text="Message body ({assignment_title} and {due_date} will be replaced):").pack(anchor='w')
        from tkinter import scrolledtext as st
        body_text = st.ScrolledText(message_frame, height=8, wrap=tk.WORD)
        body_text.pack(fill='both', expand=True)
        body_text.insert('1.0',
            "Dear Student,\n\n"
            "This is a reminder about your assignment:\n\n"
            "Assignment: {assignment_title}\n"
            "Due Date: {due_date}\n\n"
            "Please ensure your work is submitted before the deadline.\n\n"
            "Best regards,\nAcademic Administration"
        )

        # Status
        status_var = tk.StringVar(value="")
        ttk.Label(dialog, textvariable=status_var, style='Info.TLabel').pack(anchor='w', padx=10)

        def send_reminders():
            try:
                from education_system.post_18.university_system.infrastructure.email.email_service import send_email

                subject = subject_var.get().strip()
                template = body_text.get('1.0', tk.END).strip()
                rtype = recipient_var.get()

                if not subject or not template:
                    status_var.set("Subject and message are required.")
                    return

                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                total_sent = 0

                for a in assignments_info:
                    if rtype == "not_submitted":
                        cursor.execute('''
                            SELECT DISTINCT s.first_name, s.last_name, s.email_address
                            FROM students s
                            JOIN student_modules sm ON s.student_id = sm.student_id
                            WHERE sm.module_code = ?
                            AND s.email_address IS NOT NULL AND s.email_address != ''
                            AND s.student_id NOT IN (
                                SELECT student_id FROM assignment_submissions WHERE assignment_id = ?
                            )
                        ''', (a['module'], a['id']))
                    else:
                        cursor.execute('''
                            SELECT DISTINCT s.first_name, s.last_name, s.email_address
                            FROM students s
                            JOIN student_modules sm ON s.student_id = sm.student_id
                            WHERE sm.module_code = ?
                            AND s.email_address IS NOT NULL AND s.email_address != ''
                        ''', (a['module'],))

                    students = cursor.fetchall()
                    msg = template.replace("{assignment_title}", str(a['title']))
                    msg = msg.replace("{due_date}", str(a['due_date']))
                    subj = subject.replace("{assignment_title}", str(a['title']))

                    for fname, lname, email in students:
                        try:
                            send_email(recipient_email=email, subject=subj, body=msg)
                            total_sent += 1
                        except Exception:
                            pass

                conn.close()
                dialog.destroy()
                messagebox.showinfo("Reminders Sent",
                                   f"Sent {total_sent} reminder emails across {len(assignments_info)} assignment(s).")

            except ImportError:
                status_var.set("Email service not available.")
            except Exception as e:
                status_var.set(f"Error: {e}")

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill='x', padx=10, pady=10)
        ttk.Button(btn_frame, text="Send Reminders", command=send_reminders,
                  style='Accent.TButton').pack(side='left', padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='right')


    def _email_due_date_change(self, updated_assignments):
        """Email students about changed due dates for assignments."""
        try:
            from education_system.post_18.university_system.infrastructure.email.email_service import send_email

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            total_sent = 0

            for a in updated_assignments:
                cursor.execute('''
                    SELECT DISTINCT s.first_name, s.last_name, s.email_address
                    FROM students s
                    JOIN student_modules sm ON s.student_id = sm.student_id
                    WHERE sm.module_code = ?
                    AND s.email_address IS NOT NULL AND s.email_address != ''
                ''', (a['module'],))

                students = cursor.fetchall()

                for fname, lname, email in students:
                    name = f"{fname or ''} {lname or ''}".strip()
                    body = (
                        f"Dear {name},\n\n"
                        f"The due date for the following assignment has been changed:\n\n"
                        f"Assignment: {a['title']}\n"
                        f"Module: {a['module']}\n"
                        f"New Due Date: {a['new_due']}\n\n"
                        f"Please take note of the updated deadline.\n\n"
                        f"Best regards,\nAcademic Administration"
                    )
                    try:
                        send_email(
                            recipient_email=email,
                            subject=f"Due Date Changed: {a['title']}",
                            body=body
                        )
                        total_sent += 1
                    except Exception:
                        pass

            conn.close()

            if total_sent > 0:
                messagebox.showinfo("Emails Sent",
                                   f"Notified {total_sent} students about due date changes.")

        except ImportError:
            print("Email service not available for due date notifications")
        except Exception as e:
            print(f"Due date change email failed: {e}")
