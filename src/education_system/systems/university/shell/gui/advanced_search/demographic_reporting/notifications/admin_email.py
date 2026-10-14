"""Extracted demographic-reporting behaviour."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
from .. import *

class AdvancedNotificationsAdminEmailMixin:
    def _email_to_admin(self):
        """Email report to admin"""
        if not self.report_data or self.report_data.get('total', 0) == 0:
            messagebox.showwarning(_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.dialogs.no_data', default="No Data"), _t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.dialogs.please_generate_report_first', default="Please generate report first."))
            return

        # Email dialog
        email_dialog = tk.Toplevel(self.window)
        email_dialog.title(_t('advanced_search.email_demographic_report_title', default="===== EMAIL DEMOGRAPHIC REPORT ====="))
        email_dialog.geometry("700x550")
        email_dialog.transient(self.window)
        email_dialog.grab_set()

        # Center
        email_dialog.update_idletasks()
        x = (email_dialog.winfo_screenwidth() - 700) // 2
        y = (email_dialog.winfo_screenheight() - 550) // 2
        email_dialog.geometry(f"+{x}+{y}")

        frame = ttk.Frame(email_dialog, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        # Recipient
        ttk.Label(frame, text=_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.labels.recipient_email', default="Recipient Email:")).pack(anchor='w')
        recipient_var = tk.StringVar(value=_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.values.admin_university_edu', default="admin@university.edu"))
        ttk.Entry(frame, textvariable=recipient_var, width=60).pack(fill=tk.X, pady=(0, 10))

        # Subject
        ttk.Label(frame, text=_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.labels.subject', default="Subject:")).pack(anchor='w')
        subject_var = tk.StringVar(value=f"Advanced Demographic Report - {datetime.now().strftime('%Y-%m-%d')}")
        ttk.Entry(frame, textvariable=subject_var, width=60).pack(fill=tk.X, pady=(0, 10))

        # Message
        ttk.Label(frame, text=_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.labels.additional_message', default="Additional Message:")).pack(anchor='w')
        message_text = tk.Text(frame, height=8, wrap=tk.WORD)
        message_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        total = self.report_data.get('total', 0)
        message_text.insert(tk.END, f"Please find the Advanced Demographic Report for {total:,} students.\n\n")
        message_text.insert(tk.END, "Key Statistics:\n")

        # Add summary stats
        for gender, count in sorted(self.report_data['gender'].items(), key=lambda x: -x[1])[:3]:
            pct = (count / total * 100) if total > 0 else 0
            message_text.insert(tk.END, f"- {gender}: {count:,} ({pct:.1f}%)\n")

        # Info label
        ttk.Label(
            frame,
            text=f"Report contains analysis of {total:,} student records"
        ).pack(anchor='w', pady=(0, 10))

        def send_action():
            recipient = recipient_var.get().strip()
            subject = subject_var.get().strip()
            additional = message_text.get(1.0, tk.END).strip()

            if not recipient:
                messagebox.showwarning(_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.dialogs.missing', default="Missing"), _t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.dialogs.please_enter_recipient_email', default="Please enter recipient email."))
                return

            if not subject:
                messagebox.showwarning(_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.dialogs.missing', default="Missing"), _t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.dialogs.please_enter_subject', default="Please enter subject."))
                return

            body = additional + "\n\n" + "=" * 60 + "\n"
            body += self._generate_report_text()

            try:
                from education_system.systems.university.infrastructure.email.email_service import send_email

                success = send_email(
                    recipient_email=recipient,
                    subject=subject,
                    body=body
                )

                if success:
                    messagebox.showinfo(_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.dialogs.success', default="Success"), f"Report sent to {recipient}")
                    email_dialog.destroy()

                    try:
                        from education_system.systems.university.infrastructure.activity_logger import log_activity
                        log_activity('email', 'advanced_demographic_report', details={
                            'recipient': recipient,
                            'total_students': total
                        })
                    except ImportError:
                        pass
                else:
                    messagebox.showwarning(_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.dialogs.queued', default="Queued"), f"Email queued for delivery to {recipient}")
                    email_dialog.destroy()

            except ImportError:
                messagebox.showerror(_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.dialogs.error', default="Error"), _t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.dialogs.email_service_not_available', default="Email service not available."))
            except Exception as e:
                messagebox.showerror(_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.dialogs.error', default="Error"), f"Failed to send: {str(e)}")

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text=_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.buttons.send_email', default="Send Email"), command=send_action).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text=_t('advanced_search.cancel_button'), command=email_dialog.destroy).pack(side=tk.RIGHT)

class StudentNotificationsAdminEmailMixin:
    def _email_to_admin(self):
        """Email report to admin - opens dialog to compose email"""
        if not self.report_data:
            messagebox.showwarning(_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.dialogs.no_data', default="No Data"), _t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.dialogs.please_perform_a_search_first_to_generate_data', default="Please perform a search first to generate data."))
            return

        # Create email composition dialog
        email_dialog = tk.Toplevel(self.window)
        email_dialog.title(_t('advanced_search.email_report_admin_title', default="===== EMAIL REPORT ADMIN ====="))
        email_dialog.geometry("650x500")
        email_dialog.transient(self.window)
        email_dialog.grab_set()

        # Center dialog
        email_dialog.update_idletasks()
        x = (email_dialog.winfo_screenwidth() - 650) // 2
        y = (email_dialog.winfo_screenheight() - 500) // 2
        email_dialog.geometry(f"+{x}+{y}")

        frame = ttk.Frame(email_dialog, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        # Recipient
        ttk.Label(frame, text=_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.labels.recipient_email', default="Recipient Email:")).pack(anchor='w')
        recipient_var = tk.StringVar(value=_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.values.admin_university_edu', default="admin@university.edu"))
        recipient_entry = ttk.Entry(frame, textvariable=recipient_var, width=50)
        recipient_entry.pack(fill=tk.X, pady=(0, 10))

        # Subject
        ttk.Label(frame, text=_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.labels.subject', default="Subject:")).pack(anchor='w')
        subject_var = tk.StringVar(value=f"Student Demographic Report - {datetime.now().strftime('%Y-%m-%d')}")
        subject_entry = ttk.Entry(frame, textvariable=subject_var, width=50)
        subject_entry.pack(fill=tk.X, pady=(0, 10))

        # Additional message
        ttk.Label(frame, text=_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.labels.additional_message_optional', default="Additional Message (optional):")).pack(anchor='w')
        message_text = tk.Text(frame, height=6, wrap=tk.WORD)
        message_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        message_text.insert(tk.END, f"Please find attached the demographic report for {len(self.report_data)} students.\n\nFilters applied:\n")
        for name, var in self.filter_vars.items():
            if var.get() != 'All':
                message_text.insert(tk.END, f"- {name.replace('_', ' ').title()}: {var.get()}\n")

        # Preview label
        ttk.Label(frame, text=f"Report contains data for {len(self.report_data)} student(s)").pack(anchor='w', pady=(0, 10))

        def send_email_action():
            recipient = recipient_var.get().strip()
            subject = subject_var.get().strip()
            additional_msg = message_text.get(1.0, tk.END).strip()

            if not recipient:
                messagebox.showwarning(_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.dialogs.missing_information', default="Missing Information"), _t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.dialogs.please_enter_a_recipient_email_address', default="Please enter a recipient email address."))
                return

            if not subject:
                messagebox.showwarning(_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.dialogs.missing_information', default="Missing Information"), _t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.dialogs.please_enter_a_subject', default="Please enter a subject."))
                return

            # Build email body
            body = additional_msg + "\n\n"
            body += "=" * 60 + "\n"
            body += self._generate_report_text()

            try:
                # Import and use email service
                from education_system.systems.university.infrastructure.email.email_service import send_email

                success = send_email(
                    recipient_email=recipient,
                    subject=subject,
                    body=body
                )

                if success:
                    messagebox.showinfo(_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.dialogs.success', default="Success"), f"Report sent successfully to {recipient}")
                    email_dialog.destroy()

                    # Log activity
                    try:
                        from education_system.systems.university.infrastructure.activity_logger import log_activity
                        log_activity('email', 'demographic_report', details={
                            'recipient': recipient,
                            'student_count': len(self.report_data)
                        })
                    except ImportError:
                        pass
                else:
                    messagebox.showwarning(_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.dialogs.email_queued', default="Email Queued"),
                        f"Email has been queued for delivery to {recipient}.\n"
                        "Check email logs for delivery status.")
                    email_dialog.destroy()

            except ImportError:
                messagebox.showerror(_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.dialogs.error', default="Error"), _t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.dialogs.email_service_is_not_available_please_check_your_configuration', default="Email service is not available. Please check your configuration."))
            except Exception as e:
                messagebox.showerror(_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.dialogs.error', default="Error"), f"Failed to send email: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text=_t('gui.shell.advanced_search.demographic_reporting.notifications.admin_email.buttons.send_email', default="Send Email"), command=send_email_action).pack(side=tk.LEFT)
        ttk.Button(button_frame, text=_t('advanced_search.cancel_button'), command=email_dialog.destroy).pack(side=tk.RIGHT)
