"""Notification functionality for the Academic Misconduct Panel."""

from education_system.shared.academic_misconduct._imports import (
    tk, messagebox, scrolledtext, _t,
    EMAIL_AVAILABLE, queue_email,
)


class MisconductNotificationsMixin:
    """Mixin providing notification and return-to-home functionality."""

    def return_to_home(self):
        """Close this window and return to the main GUI."""
        if messagebox.askyesno(_t("misconduct.msg_titles.confirm"), "Are you sure you want to close the Academic Misconduct Panel?"):
            self.root.destroy()

    def notify_student(self):
        """Send notification to student via email."""
        if not self.selected_case:
            messagebox.showwarning(_t("misconduct.msg_titles.no_selection"), "Please select a case first.")
            return

        # Create notification dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Notify Student")
        dialog.geometry("600x500")
        dialog.configure(bg=self.colors['light'])
        dialog.transient(self.root)
        dialog.grab_set()

        content = tk.Frame(dialog, bg=self.colors['light'])
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        tk.Label(
            content,
            text=_t("misconduct.labels.send_notification"),
            font=('Segoe UI', 16, 'bold'),
            fg=self.colors['text_dark'],
            bg=self.colors['light']
        ).pack(anchor='w', pady=(0, 20))

        # Student info
        info_frame = tk.Frame(content, bg=self.colors['light'])
        info_frame.pack(fill=tk.X, pady=(0, 15))

        tk.Label(info_frame, text=f"To: {self.selected_case['student']} ({self.selected_case['student_id']})",
                 font=('Segoe UI', 10), fg=self.colors['text_dark'], bg=self.colors['light']).pack(anchor='w', padx=15, pady=10)

        # Email field
        tk.Label(content, text=_t("misconduct.labels.student_email"), font=('Segoe UI', 10),
                 fg=self.colors['text_muted'], bg=self.colors['light']).pack(anchor='w', pady=(0, 5))

        email_entry = tk.Entry(content, font=('Segoe UI', 11), bg=self.colors['light'],
                               fg=self.colors['text_dark'], insertbackground=self.colors['text_dark'], relief='flat')
        email_entry.pack(fill=tk.X, ipady=8)
        email_entry.insert(0, self.selected_case.get('student_email', ''))

        # Subject
        tk.Label(content, text=_t("misconduct.labels.subject"), font=('Segoe UI', 10),
                 fg=self.colors['text_muted'], bg=self.colors['light']).pack(anchor='w', pady=(15, 5))

        subject_entry = tk.Entry(content, font=('Segoe UI', 11), bg=self.colors['light'],
                                 fg=self.colors['text_dark'], insertbackground=self.colors['text_dark'], relief='flat')
        subject_entry.pack(fill=tk.X, ipady=8)
        subject_entry.insert(0, f"Academic Integrity Case {self.selected_case['id']} - Notification")

        # Message body
        tk.Label(content, text=_t("misconduct.labels.message"), font=('Segoe UI', 10),
                 fg=self.colors['text_muted'], bg=self.colors['light']).pack(anchor='w', pady=(15, 5))

        message_text = scrolledtext.ScrolledText(content, font=('Segoe UI', 10), bg=self.colors['light'],
                                                  fg=self.colors['text_dark'], relief='flat', height=8,
                                                  insertbackground=self.colors['text_dark'])
        message_text.pack(fill=tk.BOTH, expand=True)

        # Default message
        default_msg = f"""Dear {self.selected_case['student']},

This is to inform you that an academic integrity case ({self.selected_case['id']}) has been filed regarding your coursework in {self.selected_case['course']}.

Violation Type: {self.selected_case['type']}
Current Status: {self.selected_case['status']}
Date Filed: {self.selected_case['date_filed']}

Please contact the Office of Academic Integrity to discuss this matter.

Sincerely,
Office of Academic Integrity"""
        message_text.insert(tk.END, default_msg)

        def send_notification():
            email = email_entry.get().strip()
            subject = subject_entry.get().strip()
            message = message_text.get('1.0', tk.END).strip()

            if not email:
                messagebox.showwarning(_t("misconduct.msg_titles.missing_email"), "Please enter the student's email address.")
                return

            if not EMAIL_AVAILABLE or queue_email is None:
                messagebox.showerror(_t("misconduct.msg_titles.email_unavailable"), "Email system is not available.")
                return

            try:
                success = queue_email(email, subject, message)
                if success:
                    # Update case with email and add to history
                    self.selected_case['student_email'] = email
                    self.update_case_in_db(self.selected_case)
                    self.add_case_history(self.selected_case['id'], f"Student notified via email to {email}", 'warning')
                    messagebox.showinfo(_t("misconduct.msg_titles.success"), f"Notification sent to {email}")
                    dialog.destroy()
                else:
                    messagebox.showerror(_t("misconduct.msg_titles.error"), "Failed to send email. Please try again.")
            except Exception as e:
                messagebox.showerror(_t("misconduct.msg_titles.error"), f"Failed to send notification: {str(e)}")

        # Buttons
        btn_frame = tk.Frame(content, bg=self.colors['light'])
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        self.create_button(btn_frame, "Cancel", dialog.destroy, 'secondary').pack(side=tk.RIGHT, padx=(10, 0))
        self.create_button(btn_frame, "📧 Send Email", send_notification, 'primary').pack(side=tk.RIGHT)


def notify_appeal_status(case: dict, appeal_status: str,
                         appeal_notes: str = "",
                         appeal_reviewer: str = "Academic Appeals Committee",
                         appeal_submitted_on: str = "",
                         appeal_updated_on: str = "") -> bool:
    """Email the student in *case* with an appeal-status update.

    *appeal_status* should be one of: received, under_review, upheld, denied,
    withdrawn. Anything else is sent through as-is in the subject. Returns
    True on send, False otherwise. Best-effort — never raises."""
    from datetime import datetime as _dt

    if not EMAIL_AVAILABLE or queue_email is None:
        return False
    recipient = (case.get('student_email') or '').strip()
    if not recipient:
        return False

    norm = (appeal_status or '').strip().lower().replace(' ', '_')
    display_map = {
        'received':     'Received — Logged',
        'under_review': 'Under Review',
        'upheld':       'Upheld — Original Ruling Overturned',
        'denied':       'Denied — Original Ruling Stands',
        'withdrawn':    'Withdrawn by Appellant',
    }
    message_map = {
        'received':     "We confirm receipt of your appeal. It has been logged and will be allocated to the Academic Appeals Committee for review.",
        'under_review': "Your appeal is now under active review. We aim to reach a decision within 15 working days of this notice; we will write to you again as soon as the outcome is finalised.",
        'upheld':       "Your appeal has been UPHELD. The original ruling has been set aside; the case will be returned for re-determination or closed as directed by the committee. Any related sanctions are paused pending that step.",
        'denied':       "Your appeal has been DENIED. The original ruling and any sanctions remain in force. This decision is final under University policy.",
        'withdrawn':    "We have recorded the withdrawal of your appeal at your request. The original ruling remains in force.",
    }
    next_map = {
        'received':     "No action is required from you at this stage. Watch your university inbox for the next update.",
        'under_review': "No action is required from you at this stage. The committee will contact you if further information is needed.",
        'upheld':       "Please contact the Office of Academic Integrity to discuss the next steps within 10 working days.",
        'denied':       "Comply with the original sanctions on the timetable previously communicated. Support is available via Student Services if you need it.",
        'withdrawn':    "No further action — please retain this email as confirmation that the appeal was withdrawn.",
    }

    try:
        from education_system.post_18.university_system.infrastructure.email.template_utils import render_template
        subject, body = render_template('academics/misconduct_appeal_status', {
            'student_name':           case.get('student', 'Student'),
            'case_id':                case.get('id', '(unknown)'),
            'ruling':                 case.get('ruling') or '(no ruling on file)',
            'appeal_submitted_on':    appeal_submitted_on or case.get('appeal_submitted_on') or '(not recorded)',
            'appeal_status_display':  display_map.get(norm, appeal_status or 'Updated'),
            'appeal_updated_on':      appeal_updated_on or _dt.now().date().isoformat(),
            'appeal_reviewer':        appeal_reviewer,
            'appeal_status_message':  message_map.get(norm, f"Your appeal status is now: {appeal_status}."),
            'appeal_notes':           appeal_notes or '(no additional notes provided)',
            'appeal_next_steps':      next_map.get(norm, "Please contact the Office of Academic Integrity if you have questions."),
        })
    except Exception:
        subject, body = None, None
    if not subject or not body:
        subject = f"Academic Misconduct Appeal Update - Case {case.get('id')}"
        body = (f"Dear {case.get('student', 'Student')},\n\n"
                f"Your appeal for case {case.get('id')} is now: {appeal_status}.\n\n"
                f"Notes: {appeal_notes or '(none)'}\n\n"
                "Regards,\nAcademic Appeals Committee")
    try:
        return bool(queue_email(recipient, subject, body))
    except Exception:
        return False
