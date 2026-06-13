import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import csv
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

try:
    from education_system.university_system.infrastructure.database.db import get_connection
except ImportError:
    from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

try:
    from education_system.university_system.core.i18n import get_text as _t
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")


class StudentsManager:
    """Manages student-related views, reports, and operations in the Document Manager GUI."""

    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def view_student_profile(self):
        """View selected student's profile"""
        selection = self.gui.students_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a student to view profile.")
            return

        item = self.gui.students_tree.item(selection[0])
        student_id = item['values'][0]

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
            student_data = cursor.fetchone()

            # Get document count
            cursor.execute('SELECT COUNT(*) FROM documents WHERE owner_id = ? AND source_type = \'student\' AND is_current_version = 1', (student_id,))
            doc_count = cursor.fetchone()[0]

            conn.close()

            if student_data:
                self.show_student_profile_window(student_data, doc_count)
            else:
                messagebox.showerror("Error", "Student not found.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load student profile: {str(e)}")

    def show_student_profile_window(self, student_data, doc_count):
        """Show student profile in new window"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Student Profile")
        dialog.geometry("700x550")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Student Profile", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        profile_text = f"""Student Information
==================

Student ID: {student_data[0]}
Name: {student_data[1]} {student_data[2]}
Email: {student_data[3]}
Course: {student_data[4]}
Year: {student_data[5]}
Enrollment Date: {student_data[6]}
Status: {student_data[7]}

Document Statistics:
Total Documents: {doc_count}
"""

        text_widget = tk.Text(main_frame, wrap='word', height=15, width=50)
        text_widget.insert('1.0', profile_text)
        text_widget.config(state='disabled')
        text_widget.pack(fill='both', expand=True)

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

    def view_student_documents(self):
        """View documents for selected student"""
        selection = self.gui.students_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a student to view documents.")
            return

        item = self.gui.students_tree.item(selection[0])
        student_id = item['values'][0]
        student_name = item['values'][1]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Documents for {student_name}")
        dialog.geometry("800x600")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"Documents for {student_name} (ID: {student_id})",
                  font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Create treeview for student documents
        columns = ('Document Type', 'Status', 'Upload Date', 'Expiry', 'Version')
        docs_tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)

        for col in columns:
            docs_tree.heading(col, text=col)
            docs_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=docs_tree.yview)
        docs_tree.configure(yscrollcommand=scrollbar.set)

        docs_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Load student documents
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT dt.type_name, sd.verification_status, DATE(sd.upload_date),
                   sd.expiry_date, sd.version_number
            FROM documents sd
            JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            WHERE sd.owner_id = ? AND sd.source_type = 'student' AND sd.is_current_version = 1
            ORDER BY sd.upload_date DESC
            ''', (student_id,))

            documents = cursor.fetchall()
            conn.close()

            for doc in documents:
                docs_tree.insert('', 'end', values=tuple(doc))

        except Exception as e:
            ttk.Label(main_frame, text=f"Error loading documents: {e}").pack()

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

    def upload_for_student(self):
        """Upload document for selected student"""
        selection = self.gui.students_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a student first.")
            return

        item = self.gui.students_tree.item(selection[0])
        student_id = item['values'][0]
        student_name = item['values'][1]

        # Open upload dialog with pre-selected student
        self.gui.upload_document_dialog()
        # Set the student in the upload dialog if possible
        if hasattr(self.gui, 'upload_student_id'):
            self.gui.upload_student_id.set(f"{student_id} - {student_name}")

    def send_student_notification(self):
        """Send notification to selected student"""
        selection = self.gui.students_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a student to send notification to.")
            return

        item = self.gui.students_tree.item(selection[0])
        student_id = item['values'][0]
        student_name = item['values'][1]

        dialog = tk.Toplevel(self.root)
        dialog.title("Send Student Notification")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"Send notification to:", font=('Arial', 12, 'bold')).pack(pady=(0, 10))
        ttk.Label(main_frame, text=f"Student: {student_name} (ID: {student_id})").pack(anchor='w')

        ttk.Label(main_frame, text="Subject:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(15, 5))
        subject_entry = tk.Entry(main_frame, width=40)
        subject_entry.pack(fill='x', pady=5)

        ttk.Label(main_frame, text="Message:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 5))
        message_text = tk.Text(main_frame, height=8, width=40)
        message_text.pack(fill='x', pady=5)

        def send_notification():
            subject = subject_entry.get()
            message = message_text.get('1.0', 'end-1c')

            if not subject or not message:
                messagebox.showerror("Error", "Please enter both subject and message")
                return

            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                INSERT INTO notifications (user_id, channel, priority, title, message, source_system)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (student_id, 'general', 'normal', subject, message, 'document_manager'))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Notification sent successfully!")
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to send notification: {str(e)}")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))

        ttk.Button(button_frame, text="Send", command=send_notification).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

    def generate_student_report(self):
        """Generate report for selected student"""
        selection = self.gui.students_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a student to generate report for.")
            return

        item = self.gui.students_tree.item(selection[0])
        student_id = item['values'][0]
        student_name = item['values'][1]

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get student details and documents
            cursor.execute('''
            SELECT s.*, COUNT(sd.document_id) as doc_count,
                   COUNT(CASE WHEN sd.verification_status = 'Verified' THEN 1 END) as verified_count,
                   COUNT(CASE WHEN sd.verification_status = 'Pending' THEN 1 END) as pending_count
            FROM students s
            LEFT JOIN documents sd ON s.student_id = sd.owner_id AND sd.source_type = 'student' AND sd.is_current_version = 1
            WHERE s.student_id = ?
            GROUP BY s.student_id
            ''', (student_id,))

            student_data = cursor.fetchone()
            conn.close()

            if not student_data:
                messagebox.showerror("Error", "Student not found")
                return

            # Create report window
            report_window = tk.Toplevel(self.root)
            report_window.title(f"Student Report - {student_name}")
            report_window.geometry("850x700")

            report_frame = ttk.Frame(report_window, padding=20)
            report_frame.pack(fill='both', expand=True)

            report_content = f"""STUDENT REPORT
    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    =====================================

    STUDENT INFORMATION:
    Name: {student_data[1]} {student_data[2]}
    Student ID: {student_data[0]}
    Email: {student_data[3]}
    Course: {student_data[4]}
    Year: {student_data[5]}
    Enrollment Date: {student_data[6]}
    Status: {student_data[7]}

    DOCUMENT SUMMARY:
    Total Documents: {student_data[8]}
    Verified Documents: {student_data[9]}
    Pending Documents: {student_data[10]}
    Completion Rate: {(student_data[9] / student_data[8] * 100) if student_data[8] > 0 else 0:.1f}%

    COMPLIANCE STATUS:
    Overall Status: {'Compliant' if student_data[10] == 0 else 'Non-Compliant'}
    """

            text_widget = tk.Text(report_frame, wrap='word', height=20, width=70)
            text_widget.insert('1.0', report_content)
            text_widget.config(state='disabled')
            text_widget.pack(fill='both', expand=True)

            ttk.Button(report_frame, text="Close", command=report_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {str(e)}")

    def edit_student(self):
        """Redirect to centralized student management"""
        self.show_student_management_redirect()

    def deactivate_student(self):
        """Redirect to centralized student management"""
        self.show_student_management_redirect()

    def add_student_dialog(self):
        """Redirect to centralized student management"""
        self.show_student_management_redirect()

    def show_student_management_redirect(self):
        """Redirect to centralized student management"""
        messagebox.showinfo(
            "Student Management",
            "Student creation, editing, and deletion have been centralized.\n\n"
            "Please use the main GUI (Student Management menu) or CLI to:\n"
            "• Create new students\n"
            "• Edit student information\n"
            "• Delete student records\n\n"
            "This ensures consistent student data across all modules."
        )

    def student_report_dialog(self):
        """Student report generation dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Generate Student Report")
        dialog.geometry("600x450")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Student Report Options", font=('Arial', 12, 'bold')).pack(pady=(0, 15))

        report_type = tk.StringVar(value="all_students")

        ttk.Radiobutton(main_frame, text="All Students Summary", variable=report_type, value="all_students").pack(anchor='w', pady=5)
        ttk.Radiobutton(main_frame, text="Students by Course", variable=report_type, value="by_course").pack(anchor='w', pady=5)
        ttk.Radiobutton(main_frame, text="Non-Compliant Students", variable=report_type, value="non_compliant").pack(anchor='w', pady=5)
        ttk.Radiobutton(main_frame, text="Students by Year", variable=report_type, value="by_year").pack(anchor='w', pady=5)

        def generate_report():
            report_option = report_type.get()
            dialog.destroy()

            if report_option == "all_students":
                self.generate_all_students_report()
            elif report_option == "by_course":
                self.gui.generate_students_by_course_report()
            elif report_option == "non_compliant":
                self.gui.generate_non_compliant_students_report()
            elif report_option == "by_year":
                self.gui.generate_students_by_year_report()

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))

        ttk.Button(button_frame, text="Generate", command=generate_report).pack(side='right', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

    def generate_all_students_report(self):
        """Generate report for all students"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT s.student_id, s.first_name, s.last_name, s.course,
                   'N/A' as year,
                   COUNT(sd.document_id) as doc_count,
                   COUNT(CASE WHEN sd.verification_status = 'Verified' THEN 1 END) as verified_count
            FROM students s
            LEFT JOIN documents sd ON s.student_id = sd.owner_id AND sd.source_type = 'student' AND sd.is_current_version = 1
            GROUP BY s.student_id
            ORDER BY s.last_name, s.first_name
            ''')

            students = cursor.fetchall()
            conn.close()

            # Show report in new window
            self.show_students_report(students, "All Students Report")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate report: {str(e)}")

    def show_students_report(self, data, title):
        """Show students report in new window"""
        report_window = tk.Toplevel(self.root)
        report_window.title(title)
        report_window.geometry("900x650")

        report_frame = ttk.Frame(report_window, padding=20)
        report_frame.pack(fill='both', expand=True)

        ttk.Label(report_frame, text=title, font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Create treeview for report data
        columns = ('Student ID', 'Name', 'Course', 'Year', 'Documents', 'Verified')
        report_tree = ttk.Treeview(report_frame, columns=columns, show='headings', height=15)

        for col in columns:
            report_tree.heading(col, text=col)
            report_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(report_frame, orient='vertical', command=report_tree.yview)
        report_tree.configure(yscrollcommand=scrollbar.set)

        report_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Insert data
        for row in data:
            student_id, first_name, last_name, course, year, doc_count, verified_count = row
            full_name = f"{first_name} {last_name}"
            report_tree.insert('', 'end', values=(student_id, full_name, course, year, doc_count, verified_count))

        # Button frame
        button_frame = ttk.Frame(report_frame)
        button_frame.pack(fill='x', pady=10)

        ttk.Button(button_frame, text="\U0001f4e7 Send to Admin",
                  command=lambda: self.send_report_to_admin(title, columns, data)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="\U0001f4c4 Export CSV",
                  command=lambda: self.export_report_to_csv(title, columns, data)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Close", command=report_window.destroy).pack(side='right', padx=5)

    def send_report_to_admin(self, title, columns, data):
        """Send a report to admin via email"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Send Report to Admin")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Send Report to Admin", font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Get admin email from database
        admin_email = "admin@school.edu"
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE role = 'admin' AND email IS NOT NULL LIMIT 1")
            result = cursor.fetchone()
            if result and result[0]:
                admin_email = result[0]
            conn.close()
        except Exception:
            pass

        # Email fields
        fields_frame = ttk.Frame(main_frame)
        fields_frame.pack(fill='x', pady=10)

        ttk.Label(fields_frame, text="To (Admin Email):").grid(row=0, column=0, sticky='w', pady=5)
        to_entry = ttk.Entry(fields_frame, width=40)
        to_entry.insert(0, admin_email)
        to_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(fields_frame, text="Subject:").grid(row=1, column=0, sticky='w', pady=5)
        subject_entry = ttk.Entry(fields_frame, width=40)
        subject_entry.insert(0, f"Document Manager Report: {title}")
        subject_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(fields_frame, text="Additional Notes:").grid(row=2, column=0, sticky='nw', pady=5)
        notes_text = tk.Text(fields_frame, height=5, width=40)
        notes_text.grid(row=2, column=1, padx=5, pady=5)

        # Options
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding=10)
        options_frame.pack(fill='x', pady=10)

        attach_csv = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Attach report as CSV file", variable=attach_csv).pack(anchor='w')

        include_summary = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Include summary in email body", variable=include_summary).pack(anchor='w')

        def send_email():
            recipient = to_entry.get().strip()
            subject = subject_entry.get().strip()
            notes = notes_text.get('1.0', 'end').strip()

            if not recipient:
                messagebox.showwarning("Warning", "Please enter admin email address")
                return

            try:
                # Build email body
                body_parts = [f"Report: {title}", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"]

                if notes:
                    body_parts.append(f"\nNotes: {notes}")

                if include_summary.get():
                    body_parts.append(f"\nTotal Records: {len(data)}")
                    body_parts.append("\n--- Report Data ---\n")
                    body_parts.append(" | ".join(str(c) for c in columns))
                    body_parts.append("-" * 80)
                    for row in data[:50]:  # Limit to first 50 rows in body
                        if isinstance(row, (list, tuple)) and len(row) == 7:
                            # Student report format (raw data with separate first/last name)
                            student_id, first_name, last_name, course, year, doc_count, verified_count = row
                            body_parts.append(f"{student_id} | {first_name} {last_name} | {course} | {year} | {doc_count} | {verified_count}")
                        else:
                            body_parts.append(" | ".join(str(v) for v in row))
                    if len(data) > 50:
                        body_parts.append(f"\n... and {len(data) - 50} more records (see attached CSV)")

                body = "\n".join(body_parts)

                # Try to send via email service
                try:
                    from education_system.university_system.infrastructure.email.email_service import send_email as _send_email

                    # Create CSV attachment if requested
                    attachments = None
                    attachment_path = None
                    if attach_csv.get():
                        import tempfile
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
                            writer = csv.writer(f)
                            writer.writerow(columns)
                            for row in data:
                                if isinstance(row, (list, tuple)) and len(row) == 7:
                                    student_id, first_name, last_name, course, year, doc_count, verified_count = row
                                    writer.writerow([student_id, f"{first_name} {last_name}", course, year, doc_count, verified_count])
                                else:
                                    writer.writerow(row)
                            attachment_path = f.name
                            attachments = [attachment_path]

                    # Send the email
                    result = _send_email(
                        recipient_email=recipient,
                        subject=subject,
                        body=body,
                        attachments=attachments
                    )

                    # Clean up temp file
                    if attachment_path and os.path.exists(attachment_path):
                        os.remove(attachment_path)

                    if result:
                        messagebox.showinfo("Success", f"Report sent successfully to {recipient}")
                        self.gui.log_event('send', 'email_report', details=f'Sent {title} to {recipient}')
                        dialog.destroy()
                    else:
                        raise Exception("Email sending returned False")

                except ImportError:
                    # Fallback: Log to database for later sending
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO notifications (user_id, channel, priority, title, message, source_system)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (recipient, 'email', 'normal', subject, body, 'document_manager'))
                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Queued",
                                      f"Report queued for sending to {recipient}.\n"
                                      "Email will be sent when the email scheduler runs.")
                    self.gui.log_event('queue', 'email_report', details=f'Queued {title} for {recipient}')
                    dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to send report: {e}")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=15)

        ttk.Button(button_frame, text="\U0001f4e7 Send Email", command=send_email).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

    def export_report_to_csv(self, title, columns, data):
        """Export report data to CSV file"""
        try:
            # Generate safe filename
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
            default_filename = f"{safe_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
                initialfile=default_filename
            )

            if not file_path:
                return

            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                for row in data:
                    if isinstance(columns, tuple) and len(columns) == 6:
                        student_id, first_name, last_name, course, year, doc_count, verified_count = row
                        writer.writerow([student_id, f"{first_name} {last_name}", course, year, doc_count, verified_count])
                    else:
                        writer.writerow(row)

            messagebox.showinfo("Success", f"Report exported to:\n{file_path}")
            self.gui.log_event('export', 'report_csv', details=f'Exported {title}')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export report: {e}")

    def show_students(self):
        """Show students management interface"""
        self.gui.clear_content_area()

        # Create students frame
        students_frame = ttk.Frame(self.gui.content_area)
        students_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title and controls
        title_frame = ttk.Frame(students_frame)
        title_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(title_frame, text="Student Management", font=('Arial', 18, 'bold')).pack(side='left')

        # Control buttons
        controls_frame = ttk.Frame(title_frame)
        controls_frame.pack(side='right')

        ttk.Button(controls_frame, text="\u2795 Add Student", command=self.add_student_dialog).pack(side='left', padx=2)
        ttk.Button(controls_frame, text="\U0001f4ca Student Report", command=self.student_report_dialog).pack(side='left', padx=2)
        ttk.Button(controls_frame, text="\U0001f504 Refresh", command=self.refresh_students).pack(side='left', padx=2)

        # Search frame
        search_frame = ttk.Frame(students_frame)
        search_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(search_frame, text="Search:").pack(side='left', padx=5)
        self.gui.student_search_var = tk.StringVar()
        self.gui.student_search_entry = tk.Entry(search_frame, textvariable=self.gui.student_search_var, width=30)
        self.gui.student_search_entry.pack(side='left', padx=5)
        self.gui.student_search_entry.bind('<KeyRelease>', self.search_students)

        # Students table
        self.create_students_table(students_frame)

        # Load initial data
        self.refresh_students()

    def create_students_table(self, parent):
        """Create the students table"""
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill='both', expand=True)

        # Define columns
        columns = ('ID', 'Name', 'Email', 'Course', 'Status', 'Documents', 'Compliance')
        self.gui.students_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        # Define headings and column widths
        column_widths = {'ID': 100, 'Name': 200, 'Email': 200, 'Course': 150,
                        'Status': 100, 'Documents': 100, 'Compliance': 100}

        for col in columns:
            self.gui.students_tree.heading(col, text=col, command=lambda c=col: self.sort_students_column(c))
            self.gui.students_tree.column(col, width=column_widths.get(col, 100))

        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=self.gui.students_tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient='horizontal', command=self.gui.students_tree.xview)
        self.gui.students_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Pack widgets
        self.gui.students_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Context menu for students
        self.create_students_context_menu()

        # Double-click binding
        self.gui.students_tree.bind('<Double-1>', self.on_student_double_click)

    def create_students_context_menu(self):
        """Create context menu for students table"""
        self.gui.students_context_menu = tk.Menu(self.root, tearoff=0)
        self.gui.students_context_menu.add_command(label="View Profile", command=self.view_student_profile)
        self.gui.students_context_menu.add_command(label="View Documents", command=self.view_student_documents)
        self.gui.students_context_menu.add_command(label="Upload Document", command=self.upload_for_student)
        self.gui.students_context_menu.add_separator()
        self.gui.students_context_menu.add_command(label="Send Notification", command=self.send_student_notification)
        self.gui.students_context_menu.add_command(label="Generate Report", command=self.generate_student_report)
        self.gui.students_context_menu.add_separator()
        self.gui.students_context_menu.add_command(label="Edit Student", command=self.edit_student)
        self.gui.students_context_menu.add_command(label="Deactivate", command=self.deactivate_student)

        # Bind right-click
        self.gui.students_tree.bind('<Button-3>', self.show_students_context_menu)

    def show_students_context_menu(self, event):
        """Show context menu for students"""
        item = self.gui.students_tree.identify_row(event.y)
        if item:
            self.gui.students_tree.selection_set(item)
            self.gui.students_context_menu.post(event.x_root, event.y_root)

    def search_student_for_upload(self):
        """Search for student in upload dialog"""
        if hasattr(self.gui, 'upload_student_id'):
            search_term = simpledialog.askstring("Search Student", "Enter student ID or name:")
            if search_term:
                # Here you would implement actual search logic
                messagebox.showinfo("Search", f"Searching for: {search_term}")

    def get_students_list(self):
        """Get list of students"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id, first_name, last_name FROM students ORDER BY last_name, first_name')
            students = cursor.fetchall()
            conn.close()
            return students
        except Exception:
            return []

    def load_students_data(self):
        """Load students data into table"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get students with document counts and compliance status
            query = '''
            SELECT s.student_id, s.first_name || ' ' || s.last_name as name,
                   s.email_address, s.course, s.status,
                   COUNT(DISTINCT sd.document_id) as doc_count,
                   CASE
                       WHEN COUNT(DISTINCT CASE WHEN dt.is_required = 1 THEN dt.type_id END) =
                            COUNT(DISTINCT CASE WHEN dt.is_required = 1 AND sd.document_id IS NOT NULL THEN dt.type_id END)
                       THEN 'Compliant'
                       ELSE 'Non-Compliant'
                   END as compliance
            FROM students s
            LEFT JOIN documents sd ON s.student_id = sd.owner_id AND sd.source_type = 'student' AND sd.is_current_version = 1
            LEFT JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            GROUP BY s.student_id
            ORDER BY s.last_name, s.first_name
            '''

            cursor.execute(query)
            students = cursor.fetchall()
            conn.close()

            # Clear existing items
            for item in self.gui.students_tree.get_children():
                self.gui.students_tree.delete(item)

            # Insert new items
            for student in students:
                self.gui.students_tree.insert('', 'end', values=tuple(student))

        except Exception as e:
            messagebox.showerror("Data Error", f"Failed to load students: {str(e)}")

    def on_student_double_click(self, event):
        """Handle double-click on student"""
        selection = self.gui.students_tree.selection()
        if selection:
            self.view_student_profile()

    def search_students(self, event=None):
        """Search students as user types"""
        search_term = self.gui.student_search_var.get().lower()

        # Hide all items first
        for item in self.gui.students_tree.get_children():
            self.gui.students_tree.detach(item)

        # Show matching items
        for item in self.gui.students_tree.get_children():
            values = self.gui.students_tree.item(item)['values']
            if search_term in str(values).lower():
                self.gui.students_tree.reattach(item, '', 'end')

    def sort_students_column(self, col):
        """
        Sort students table by column

        Sorts the students tree view by the specified column.
        Toggles between ascending and descending order on repeated clicks.
        """
        # Get all items
        items = [(self.gui.students_tree.set(item, col), item) for item in self.gui.students_tree.get_children('')]

        # Determine sort order (toggle if clicking same column)
        if hasattr(self, '_sort_students_col') and self._sort_students_col == col:
            self._sort_students_reverse = not getattr(self, '_sort_students_reverse', False)
        else:
            self._sort_students_reverse = False

        self._sort_students_col = col

        # Sort items
        try:
            # Try numeric sort first
            items.sort(key=lambda x: float(x[0]) if x[0] else 0, reverse=self._sort_students_reverse)
        except (ValueError, TypeError):
            # Fall back to string sort
            items.sort(key=lambda x: str(x[0]).lower(), reverse=self._sort_students_reverse)

        # Rearrange items in tree
        for index, (val, item) in enumerate(items):
            self.gui.students_tree.move(item, '', index)

        # Update column heading to show sort direction
        for c in self.gui.students_tree['columns']:
            heading = self.gui.students_tree.heading(c)['text']
            # Remove existing sort indicators
            if heading.endswith(' \u2191') or heading.endswith(' \u2193'):
                heading = heading[:-2]
            self.gui.students_tree.heading(c, text=heading)

        # Add sort indicator to current column
        heading = self.gui.students_tree.heading(col)['text']
        indicator = ' \u2193' if self._sort_students_reverse else ' \u2191'
        self.gui.students_tree.heading(col, text=heading + indicator)

    def refresh_students(self):
        """Refresh students table"""
        if hasattr(self.gui, 'students_tree') and self.gui.students_tree is not None:
            self.load_students_data()
