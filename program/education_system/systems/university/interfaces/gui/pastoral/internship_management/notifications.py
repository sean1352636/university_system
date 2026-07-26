from education_system.systems.university.interfaces.gui.pastoral.internship_management._imports import datetime, messagebox, get_connection, tk, scrolledtext


def send_internship_notification(*args, **kwargs):
    """
    Send internship notification - Sends email notifications to students about internship opportunities
    """
    try:
        # Extract arguments if provided positionally or as keywords
        student_id = args[0] if len(args) > 0 else kwargs.get('student_id')
        internship_title = args[1] if len(args) > 1 else kwargs.get('internship_title', 'Internship')
        message = args[2] if len(args) > 2 else kwargs.get('message', 'New internship notification')

        from education_system.systems.university.infrastructure.email.email_service import EmailService
        from education_system.systems.university.infrastructure.database.db import get_connection

        email_service = EmailService()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT email_address, first_name FROM students WHERE student_id = ?", (student_id,))
        result = cursor.fetchone()
        conn.close()

        if result:
            email, first_name = result
            from education_system.systems.university.infrastructure.email.template_utils import render_template
            subject, body = render_template('internships/internship_update_notification', {
                'internship_title': internship_title,
                'first_name': first_name,
                'message': message
            })
            email_service.send_email(to_address=email, subject=subject, body=body)
            print(f"Notification sent to {email}")
    except Exception as e:
        print(f"Failed to send notification: {e}")

def send_application_confirmation(*args, **kwargs):
    """
    Send application confirmation - Acknowledges receipt of student internship application
    """
    try:
        student_id = args[0] if len(args) > 0 else kwargs.get('student_id')
        internship_id = args[1] if len(args) > 1 else kwargs.get('internship_id')

        from education_system.systems.university.infrastructure.email.email_service import EmailService
        from education_system.systems.university.infrastructure.database.db import get_connection

        email_service = EmailService()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.email_address, s.first_name, i.title, i.company
            FROM students s, internships i
            WHERE s.student_id = ? AND i.internship_id = ?
        """, (student_id, internship_id))
        result = cursor.fetchone()
        conn.close()

        if result:
            email, first_name, title, company = result
            from education_system.systems.university.infrastructure.email.template_utils import render_template
            subject, body = render_template('internships/application_confirmation', {
                'first_name': first_name,
                'title': title,
                'company': company
            })
            email_service.send_email(to_address=email, subject=subject, body=body)
            print(f"Confirmation sent to {email}")
    except Exception as e:
        print(f"Failed to send confirmation: {e}")


class NotificationsMixin:
    def send_new_internship_announcement(self, internship_id, internship_title, company_name, description, requirements):
        """Send email to all students about new internship"""
        try:
            from education_system.systems.university.infrastructure.email.email_service import send_template_email

            # Get all student emails
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT email, first_name, last_name
                FROM students
                WHERE email IS NOT NULL AND email != ""
            ''')
            students = cursor.fetchall()
            conn.close()

            for email, first_name, last_name in students:
                try:
                    template_vars = {
                        "first_name": first_name,
                        "last_name": last_name,
                        "internship_title": internship_title,
                        "company_name": company_name,
                        "internship_id": internship_id,
                        "description": description,
                        "requirements": requirements
                    }
                    send_template_email('internships/internship_opportunity', email, template_vars)
                except Exception as e:
                    print(f"Failed to send announcement to {email}: {e}")

            print(f"New internship announcement sent to {len(students)} students")

        except Exception as e:
            print(f"Failed to send new internship announcements: {e}")

    def send_application_confirmation(self, student_email, student_name, internship_title, company_name, action_type="applied"):
        """Send confirmation email when student applies for or deletes internship application"""
        try:
            from education_system.systems.university.infrastructure.email.email_service import send_template_email

            if action_type == "applied":
                template_name="internships/internship_application_confirmation"
                action_text = "submitted"
                status_text = "Your application has been successfully submitted and is now under review."
                next_steps = """What happens next:
\u2022 Your application will be reviewed by our career services team
\u2022 We'll check your academic eligibility
\u2022 If eligible, your application will be forwarded to the company
\u2022 You'll receive updates via email on your application status"""
            else:  # deleted/withdrawn
                template_name="internships/internship_application_withdrawn"
                action_text = "withdrawn"
                status_text = "Your application has been successfully withdrawn."
                next_steps = """You can still:
\u2022 Apply for other available internships
\u2022 Reapply for this position if it's still open
\u2022 Contact career services if you need assistance"""

            template_vars = {
                "student_name": student_name,
                "internship_title": internship_title,
                "company_name": company_name,
                "action_text": action_text,
                "status_text": status_text,
                "next_steps": next_steps,
                "action_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            send_template_email(template_name, student_email, template_vars)
            messagebox.showinfo("Email Sent", f"Confirmation email sent to {student_name}")

        except Exception as e:
            print(f"Failed to send application confirmation: {e}")

    def send_application_decision(self, student_email, student_name, internship_title, company_name, decision, reason=""):
        """Send email notification for application acceptance or rejection"""
        try:
            from education_system.systems.university.infrastructure.email.email_service import send_template_email

            if decision.lower() == "accepted":
                template_name="internships/internship_application_accepted"
            else:  # rejected or update
                template_name="internships/internship_application_update"

            template_vars = {
                "student_name": student_name,
                "internship_title": internship_title,
                "company_name": company_name,
                "decision": decision,
                "reason": reason if reason else "",
                "decision_date": datetime.now().strftime('%Y-%m-%d')
            }

            send_template_email(template_name, student_email, template_vars)
            messagebox.showinfo("Decision Email Sent", f"Application decision sent to {student_name}")

        except Exception as e:
            print(f"Failed to send application decision: {e}")

    def _send_email_via_gui(self, to_email, subject, message):
        """Send email via email manager GUI"""
        try:
            from education_system.systems.university.interfaces.gui.shell.email.email_gui import EmailManagerGUI
            email_gui = EmailManagerGUI(self.root, auth=self.auth)

            if hasattr(email_gui, 'send_email'):
                email_gui.send_email(to_email=to_email, subject=subject, message=message)
                return True
            return False
        except ImportError:
            return False
        except Exception as e:
            print(f"Error sending email via GUI: {e}")
            return False

    def _show_email_fallback(self, email, subject, message, email_type):
        """Show fallback dialog for email"""
        try:
            fallback_window = tk.Toplevel(self.root)
            fallback_window.title(f"{email_type} Email - Manual Send")
            fallback_window.geometry("700x500")
            fallback_window.transient(self.root)

            tk.Label(fallback_window,
                    text=f"Email system unavailable. Please manually send this {email_type.lower()}:",
                    font=('Arial', 10, 'bold')).pack(pady=10)

            details_frame = tk.Frame(fallback_window)
            details_frame.pack(fill='both', expand=True, padx=10, pady=10)

            details_text = scrolledtext.ScrolledText(details_frame, height=20, width=80)
            details_text.pack(fill='both', expand=True)

            email_details = f"To: {email}\nSubject: {subject}\n\nMessage:\n{message}"
            details_text.insert('1.0', email_details)
            details_text.config(state='disabled')

            tk.Button(fallback_window, text="Close", command=fallback_window.destroy).pack(pady=10)
        except Exception as e:
            print(f"Failed to show email fallback: {e}")
