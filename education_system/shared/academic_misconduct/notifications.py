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
