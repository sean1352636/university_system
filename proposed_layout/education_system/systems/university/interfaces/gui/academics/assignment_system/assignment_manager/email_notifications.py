"""Email reminder and notification operations for assignments"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from education_system.systems.university.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH


class EmailNotificationsMixin:
    """Email notification operations"""

    def send_assignment_email_reminders(self):
        """Send email reminders for assignment"""
        selection = self.manage_assignments_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an assignment to send reminders for")
            return

        item = self.manage_assignments_tree.item(selection[0])
        assignment_id = item['values'][0]
        assignment_title = item['values'][1]
        assignment_due_date = item['values'][3]

        # Create email reminder dialog
        email_window = tk.Toplevel(self.root)
        email_window.title(f"Email Reminders - {assignment_title}")
        email_window.geometry("600x500")
        email_window.transient(self.root)
        email_window.grab_set()

        # Email options frame
        options_frame = ttk.LabelFrame(email_window, text="Email Options", padding=10)
        options_frame.pack(fill='x', padx=10, pady=10)

        # Email type selection
        email_type_var = tk.StringVar(value="upcoming")
        ttk.Label(options_frame, text="Email Type:").grid(row=0, column=0, sticky='w', padx=(0, 10))

        email_types = [
            ("upcoming", "Upcoming Assignment Reminder"),
            ("overdue", "Overdue Assignment Notice"),
            ("new", "New Assignment Notification"),
            ("custom", "Custom Message")
        ]

        for i, (value, text) in enumerate(email_types):
            ttk.Radiobutton(options_frame, text=text, variable=email_type_var,
                           value=value).grid(row=i+1, column=0, sticky='w', padx=(20, 0))

        # Recipient selection
        recipient_frame = ttk.LabelFrame(email_window, text="Recipients", padding=10)
        recipient_frame.pack(fill='x', padx=10, pady=10)

        recipient_var = tk.StringVar(value="enrolled")
        recipient_options = [
            ("enrolled", "All Enrolled Students"),
            ("not_submitted", "Students Who Haven't Submitted"),
            ("late_submissions", "Students with Late Submissions"),
            ("custom", "Custom Recipients")
        ]

        for i, (value, text) in enumerate(recipient_options):
            ttk.Radiobutton(recipient_frame, text=text, variable=recipient_var,
                           value=value).grid(row=i, column=0, sticky='w')

        # Message frame
        message_frame = ttk.LabelFrame(email_window, text="Message", padding=10)
        message_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Subject line
        ttk.Label(message_frame, text="Subject:").pack(anchor='w')
        subject_var = tk.StringVar(value=f"Reminder: {assignment_title}")
        subject_entry = ttk.Entry(message_frame, textvariable=subject_var, width=70)
        subject_entry.pack(fill='x', pady=(0, 10))

        # Message body
        ttk.Label(message_frame, text="Message:").pack(anchor='w')
        message_text = scrolledtext.ScrolledText(message_frame, height=10, width=70)
        message_text.pack(fill='both', expand=True)

        # Default message based on type
        def update_default_message(*args):
            email_type = email_type_var.get()
            template_map = {
                "upcoming": "assignment_reminder_upcoming",
                "overdue": "assignment_reminder_overdue",
                "new": "assignment_new"
            }

            if email_type in template_map:
                try:
                    from education_system.systems.university.infrastructure.email.template_utils import render_template
                    _, default_message = render_template(template_map[email_type], {
                        "assignment_title": assignment_title,
                        "assignment_due_date": assignment_due_date
                    })
                except (ImportError, KeyError, Exception):
                    default_message = ""
            else:
                default_message = f"Dear Student,\n\nRegarding assignment: {assignment_title}\nDue Date: {assignment_due_date}\n\n[Enter your custom message here]\n\nBest regards,\nAcademic Team"

            message_text.delete('1.0', tk.END)
            message_text.insert('1.0', default_message)

        email_type_var.trace('w', update_default_message)
        update_default_message()  # Set initial message

        # Buttons frame
        buttons_frame = ttk.Frame(email_window)
        buttons_frame.pack(fill='x', padx=10, pady=10)

        def send_emails():
            """Send the email reminders"""
            try:
                email_type = email_type_var.get()
                recipient_type = recipient_var.get()
                subject = subject_var.get().strip()
                message = message_text.get('1.0', tk.END).strip()

                if not subject or not message:
                    messagebox.showwarning("Warning", "Please enter both subject and message")
                    return

                # Get recipient list based on selection
                recipients = self._get_assignment_email_recipients(assignment_id, recipient_type)

                if not recipients:
                    messagebox.showinfo("Info", "No recipients found for the selected criteria")
                    return

                # Try to open email GUI if available
                success = self._send_assignment_emails_via_gui(recipients, subject, message, assignment_title)

                if success:
                    email_window.destroy()
                    messagebox.showinfo("Success", f"Email reminders sent to {len(recipients)} recipients")
                else:
                    # Fallback: show email details for manual sending
                    self._show_email_fallback_dialog(recipients, subject, message)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to send emails: {e}")

        def preview_recipients():
            """Preview the list of recipients"""
            try:
                recipient_type = recipient_var.get()
                recipients = self._get_assignment_email_recipients(assignment_id, recipient_type)

                preview_window = tk.Toplevel(email_window)
                preview_window.title("Email Recipients Preview")
                preview_window.geometry("500x400")
                preview_window.transient(email_window)

                ttk.Label(preview_window, text=f"Recipients ({len(recipients)}):").pack(anchor='w', padx=10, pady=10)

                recipients_list = tk.Listbox(preview_window, height=20)
                recipients_list.pack(fill='both', expand=True, padx=10, pady=(0, 10))

                for recipient in recipients:
                    recipients_list.insert(tk.END, f"{recipient['name']} ({recipient['email']})")

                ttk.Button(preview_window, text="Close",
                          command=preview_window.destroy).pack(pady=10)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to preview recipients: {e}")

        ttk.Button(buttons_frame, text="Preview Recipients",
                  command=preview_recipients).pack(side='left', padx=(0, 10))
        ttk.Button(buttons_frame, text="Send Emails",
                  command=send_emails).pack(side='left', padx=(0, 10))
        ttk.Button(buttons_frame, text="Cancel",
                  command=email_window.destroy).pack(side='right')


    def _get_assignment_email_recipients(self, assignment_id, recipient_type):
        """Get email recipients based on criteria"""
        recipients = []
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            if recipient_type == "enrolled":
                # All students enrolled in the module
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email
                FROM students s
                JOIN student_enrollments se ON s.student_id = se.student_id
                JOIN assignments a ON se.module_code = a.module_code
                WHERE a.id = ? AND s.email IS NOT NULL AND s.email != ''
                ''', (assignment_id,))

            elif recipient_type == "not_submitted":
                # Students who haven't submitted
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email
                FROM students s
                JOIN student_enrollments se ON s.student_id = se.student_id
                JOIN assignments a ON se.module_code = a.module_code
                LEFT JOIN assignment_submissions sub ON s.student_id = sub.student_id AND a.id = sub.assignment_id
                WHERE a.id = ? AND sub.id IS NULL AND s.email IS NOT NULL AND s.email != ''
                ''', (assignment_id,))

            elif recipient_type == "late_submissions":
                # Students with late submissions
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email
                FROM students s
                JOIN assignment_submissions sub ON s.student_id = sub.student_id
                WHERE sub.assignment_id = ? AND sub.late_submission = 1 AND s.email IS NOT NULL AND s.email != ''
                ''', (assignment_id,))

            for row in cursor.fetchall():
                recipients.append({
                    'student_id': row[0],
                    'name': f"{row[1]} {row[2]}",
                    'email': row[3]
                })

            conn.close()

        except Exception as e:
            print(f"Error getting recipients: {e}")

        return recipients


    def _send_assignment_emails_via_gui(self, recipients, subject, message, assignment_title):
        """Try to send emails via email GUI"""
        try:
            # Try to import and use email GUI
            from education_system.systems.university.interfaces.gui.shell.email.email_gui import EmailManagerGUI as EmailGUI

            # Create email GUI instance
            email_gui = EmailGUI(self.root, self.auth)

            # Prepare recipient list
            recipient_emails = [r['email'] for r in recipients]

            # Send emails through email GUI
            for recipient in recipients:
                personalized_message = message.replace("[Student Name]", recipient['name'])
                email_gui.send_email(
                    to_email=recipient['email'],
                    subject=subject,
                    message=personalized_message
                )

            return True

        except ImportError:
            return False
        except Exception as e:
            print(f"Error sending emails via GUI: {e}")
            return False


    def _show_email_fallback_dialog(self, recipients, subject, message):
        """Show fallback dialog with email details for manual sending"""
        fallback_window = tk.Toplevel(self.root)
        fallback_window.title("Email Details - Manual Send")
        fallback_window.geometry("700x500")
        fallback_window.transient(self.root)

        ttk.Label(fallback_window, text="Email GUI not available. Please send manually:",
                 font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10, pady=10)

        # Email details
        details_frame = ttk.LabelFrame(fallback_window, text="Email Details", padding=10)
        details_frame.pack(fill='both', expand=True, padx=10, pady=10)

        details_text = scrolledtext.ScrolledText(details_frame, height=20, width=80)
        details_text.pack(fill='both', expand=True)

        email_details = f"Subject: {subject}\n\n"
        email_details += f"Recipients ({len(recipients)}):\n"
        for recipient in recipients:
            email_details += f"  - {recipient['name']} ({recipient['email']})\n"
        email_details += f"\nMessage:\n{message}"

        details_text.insert('1.0', email_details)
        details_text.config(state='disabled')

        ttk.Button(fallback_window, text="Close",
                  command=fallback_window.destroy).pack(pady=10)


    def check_and_send_overdue_emails(self):
        """Check for overdue assignments and send reminder emails to students"""
        try:
            from education_system.systems.university.infrastructure.email.email_service import send_email

            from datetime import datetime

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                # Get assignments that are overdue
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    SELECT a.id, a.title, a.module_code, m.module_name, a.due_date
                    FROM assignments a
                    JOIN modules m ON a.module_code = m.module_code
                    WHERE a.due_date < ? AND a.is_active = 1
                ''', (current_time,))

                overdue_assignments = cursor.fetchall()

                if not overdue_assignments:
                    print("No overdue assignments found")
            finally:
                conn.close()
                return 0

            total_emails_sent = 0

            for assignment_id, title, module_code, module_name, due_date in overdue_assignments:
                # Find students who haven't submitted
                cursor.execute('''
                    SELECT s.student_id, s.first_name, s.last_name, s.email_address
                    FROM students s
                    JOIN student_modules sm ON s.student_id = sm.student_id
                    WHERE sm.module_code = ?
                    AND s.email_address IS NOT NULL
                    AND s.email_address != ''
                    AND s.student_id NOT IN (
                        SELECT student_id
                        FROM assignment_submissions
                        WHERE assignment_id = ?
                    )
                ''', (module_code, assignment_id))

                students_without_submission = cursor.fetchall()

                # Send emails to students who haven't submitted
                for student_id, first_name, last_name, email in students_without_submission:
                    try:
                        # Calculate days overdue
                        due_date_obj = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
                        days_overdue = (datetime.now() - due_date_obj).days

                        # Use email template
                        try:
                            from education_system.systems.university.infrastructure.email.template_utils import render_template
                            subject, body = render_template("assignment_overdue_reminder", {
                                "first_name": first_name,
                                "module_code": module_code,
                                "module_name": module_name,
                                "assignment_title": title,
                                "due_date": due_date,
                                "days_overdue": days_overdue
                            })
                        except Exception:
                            # Fallback to hardcoded email
                            subject = f"OVERDUE: Assignment Not Submitted - {title}"
                            body = f"""Dear {first_name},

This is a reminder that the following assignment is now OVERDUE and you have not yet submitted it.

Module: {module_code} - {module_name}
Assignment: {title}
Due Date: {due_date}
Days Overdue: {days_overdue}

Please submit your assignment as soon as possible through the Assignment System.

If you have already submitted this assignment, please disregard this message.
If you are experiencing technical difficulties, please contact your instructor immediately.

Best regards,
Academic Administration Team
"""

                        send_email(email, subject, body)
                        total_emails_sent += 1
                        print(f"Overdue reminder sent to {student_id} ({email}) for assignment '{title}'")

                    except Exception as e:
                        print(f"Failed to send overdue email to {student_id}: {e}")

            conn.close()

            print(f"Total overdue reminder emails sent: {total_emails_sent}")
            return total_emails_sent

        except Exception as e:
            print(f"Error in check_and_send_overdue_emails: {e}")
            import traceback
            traceback.print_exc()
            return 0
