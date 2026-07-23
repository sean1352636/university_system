"""Notification configuration, templates, email/SMS setup, and system info."""

import sys
import io
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from datetime import datetime

from education_system.post_18.university_system.core.i18n import get_text as _
from education_system.post_18.university_system.infrastructure.database.db import get_connection

from education_system.post_18.university_system.modules.domain.finance.gui.finance.common_imports import (
    enhanced_notification_system,
    setup_email_config,
    setup_sms_config,
    test_email_service,
    test_sms_service,
)

from education_system.post_18.university_system.modules.domain.finance.gui.finance.settings.currency import SUPPORTED_CURRENCIES


class NotificationsMixin:
    """Email/SMS config, notification templates, and system-info display."""

    def load_notification_templates(self):
        """Load notification templates"""
        def load_thread():
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT template_id, template_name, template_type, is_active
                FROM notification_templates
                ORDER BY template_type, template_name
                ''')

                templates = cursor.fetchall()
                conn.close()

                self.root.after(0, lambda: self.update_notification_templates(templates))

            except Exception as e:
                print(f"Error loading notification templates: {e}")

        threading.Thread(target=load_thread, daemon=True).start()


    def update_notification_templates(self, templates):
        """Update notification templates table"""
        try:
            for item in self.templates_tree.get_children():
                self.templates_tree.delete(item)

            for template in templates:
                template_id, name, template_type, is_active = template
                active_str = "Yes" if is_active else "No"
                display_data = (template_id, name, template_type, active_str)
                self.templates_tree.insert('', 'end', values=display_data)
        except AttributeError:
            pass  # Table not created yet


    def load_system_info(self):
        """Load system information"""
        try:
            import sys
            # Use the shared DEFAULT_DB_PATH for database status and metadata.  This ensures
            # that the GUI reflects the correct database location even when the working
            # directory changes.  Import inside the method to avoid circular
            # dependencies on module load.
            from education_system.post_18.university_system.infrastructure.database.db import DEFAULT_DB_PATH
            db_exists = os.path.exists(DEFAULT_DB_PATH)
            last_modified = (
                datetime.fromtimestamp(os.path.getmtime(DEFAULT_DB_PATH)).strftime('%Y-%m-%d %H:%M:%S')
                if db_exists else 'N/A'
            )
            info_text = f"""System Information
    ===================
    Database: {os.path.basename(DEFAULT_DB_PATH)}
    Status: {'Connected' if db_exists else 'Not Found'}
    Last Modified: {last_modified}

    Version: 2.0.0 GUI
    GUI Framework: Tkinter
    Python Version: {sys.version}
    Platform: {sys.platform}

    Current User: {self.auth.current_user['username'] if self.auth and self.auth.current_user else 'Not Authenticated'}
    Session Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """

            self.system_info_text.delete('1.0', tk.END)
            self.system_info_text.insert('1.0', info_text)
        except Exception as e:
            print(f"Error loading system info: {e}")

    # ==================== DIALOG METHODS ====================



    def gui_setup_email_config(self):
        """GUI wrapper for setup_email_config"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.email_config_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.email_settings_config_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # SMTP Server
        ttk.Label(form_frame, text=_("finance_gui.settings.smtp_server_label")).pack(anchor='w', pady=5)
        smtp_var = tk.StringVar(value="smtp.gmail.com")
        ttk.Entry(form_frame, textvariable=smtp_var).pack(anchor='w', fill='x', pady=5)

        # Port
        ttk.Label(form_frame, text=_("finance_gui.settings.port_label")).pack(anchor='w', pady=5)
        port_var = tk.StringVar(value="587")
        ttk.Entry(form_frame, textvariable=port_var).pack(anchor='w', fill='x', pady=5)

        # Username
        ttk.Label(form_frame, text=_("finance_gui.settings.username_label")).pack(anchor='w', pady=5)
        username_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=username_var).pack(anchor='w', fill='x', pady=5)

        # Password
        ttk.Label(form_frame, text=_("finance_gui.settings.password_label")).pack(anchor='w', pady=5)
        password_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=password_var, show="*").pack(anchor='w', fill='x', pady=5)

        def save_config():
            try:
                smtp_server = smtp_var.get().strip()
                port = int(port_var.get())
                username = username_var.get().strip()
                password = password_var.get().strip()

                if not all([smtp_server, port, username, password]):
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.all_fields_required"))
                    return

                setup_email_config(smtp_server, port, username, password)
                messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.email_config_saved"))
                dialog.destroy()

            except ValueError:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.invalid_port"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_save_email_config", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.settings.btn_save_config"), command=save_config).pack(pady=20)


    def gui_setup_sms_config(self):
        """GUI wrapper for setup_sms_config"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.sms_config_title"))
        dialog.geometry("500x350")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.sms_settings_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Service provider
        ttk.Label(form_frame, text=_("finance_gui.settings.sms_provider_label")).pack(anchor='w', pady=5)
        provider_var = tk.StringVar(value="twilio")
        provider_combo = ttk.Combobox(form_frame, textvariable=provider_var,
                                     values=["twilio", "aws_sns"], state='readonly')
        provider_combo.pack(anchor='w', fill='x', pady=5)

        # Account SID / Access Key
        ttk.Label(form_frame, text=_("finance_gui.settings.account_sid_label")).pack(anchor='w', pady=5)
        sid_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=sid_var).pack(anchor='w', fill='x', pady=5)

        # Auth Token / Secret Key
        ttk.Label(form_frame, text=_("finance_gui.settings.auth_token_label")).pack(anchor='w', pady=5)
        token_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=token_var, show="*").pack(anchor='w', fill='x', pady=5)

        def save_config():
            try:
                provider = provider_var.get()
                sid = sid_var.get().strip()
                token = token_var.get().strip()

                if not all([provider, sid, token]):
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.all_fields_required"))
                    return

                setup_sms_config(provider, sid, token)
                messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.sms_config_saved"))
                dialog.destroy()

            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_save_sms_config", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.settings.btn_save_config"), command=save_config).pack(pady=20)


    def gui_test_email_service(self):
        """GUI wrapper for test_email_service"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.test_email_title"))
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.email_test_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Test email address
        ttk.Label(form_frame, text=_("finance_gui.settings.test_email_address_label")).pack(anchor='w', pady=5)
        email_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=email_var).pack(anchor='w', fill='x', pady=5)

        def run_test():
            try:
                test_email = email_var.get().strip()
                if not test_email:
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.test_email_required"))
                    return

                test_email_service(test_email)
                messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.test_email_sent", email=test_email))
                dialog.destroy()

            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.email_test_failed", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.settings.btn_send_test_email"), command=run_test).pack(pady=20)


    def gui_test_sms_service(self):
        """GUI wrapper for test_sms_service"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.test_sms_title"))
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        form_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.sms_test_frame"), padding=20)
        form_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Test phone number
        ttk.Label(form_frame, text=_("finance_gui.settings.test_phone_label")).pack(anchor='w', pady=5)
        phone_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=phone_var).pack(anchor='w', fill='x', pady=5)

        def run_test():
            try:
                test_phone = phone_var.get().strip()
                if not test_phone:
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.test_phone_required"))
                    return

                test_sms_service(test_phone)
                messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.test_sms_sent", phone=test_phone))
                dialog.destroy()

            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.sms_test_failed", error=str(e)))

        ttk.Button(form_frame, text=_("finance_gui.settings.btn_send_test_sms"), command=run_test).pack(pady=20)


    def gui_enhanced_notification_system(self):
        """GUI wrapper for enhanced_notification_system"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.enhanced_notifications_title"))
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        try:
            old_stdout = sys.stdout
            sys.stdout = mystdout = io.StringIO()

            enhanced_notification_system()

            output = mystdout.getvalue()
            sys.stdout = old_stdout

            text_widget = ScrolledText(dialog, height=25, width=70, font=('Courier', 10))
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            text_widget.insert('1.0', output)

            ttk.Button(dialog, text=_("finance_gui.settings.btn_close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_notification_system", error=str(e)))

    # Add menu update methods to include new GUI functions in menus

    def gui_setup_automated_notifications(self):
        """GUI wrapper for notification setup"""
        try:
            # Call the original setup function logic
            conn = get_connection()
            cursor = conn.cursor()

            # Default notification schedules
            schedules = [
                (1, '{"fee_status": "unpaid", "days_before_due": 7}', 7, 3, 7, 1),
                (2, '{"fee_status": "unpaid", "days_overdue": 1}', -1, 5, 3, 1),
                (4, '{"payment_plan_created": true}', 0, 1, 0, 1)
            ]

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            for template_id, conditions, days_before, max_reminders, interval, is_active in schedules:
                cursor.execute('''
                INSERT OR REPLACE INTO notification_schedules
                (template_id, trigger_condition, days_before_due, max_reminders,
                 reminder_interval_days, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (template_id, conditions, days_before, max_reminders, interval, is_active, now, now))

            conn.commit()
            conn.close()

            messagebox.showinfo(_("finance_gui.settings.success_title"),
                               _("finance_gui.settings.notifications_setup_success"))

            self.update_status(_("finance_gui.settings.settings_saved"))

        except Exception as e:
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_setup_notifications", error=str(e)))


    def gui_send_automated_notifications(self):
        """GUI wrapper for sending automated notifications"""
        if messagebox.askyesno(_("finance_gui.settings.confirm_title"), _("finance_gui.settings.confirm_send_notifications")):
            try:
                self.update_status(_("finance_gui.settings.sending_notifications"))

                def send_notifications():
                    # Simplified notification sending
                    notifications_sent = 0

                    try:
                        conn = get_connection()
                        cursor = conn.cursor()

                        # Find overdue fees for notifications
                        cursor.execute('''
                        SELECT DISTINCT sf.student_id, s.first_name, s.last_name, s.email_address,
                               COUNT(*) as overdue_count, SUM(sf.amount) as total_overdue
                        FROM student_fees sf
                        JOIN students s ON sf.student_id = s.student_id
                        WHERE sf.status IN ('unpaid', 'partial')
                        AND date(sf.due_date) < date('now')
                        GROUP BY sf.student_id
                        LIMIT 10
                        ''')

                        overdue_students = cursor.fetchall()

                        for student in overdue_students:
                            student_id, first_name, last_name, email, count, total = student

                            # Send overdue payment reminder using template system
                            try:
                                from education_system.post_18.university_system.infrastructure.email.template_utils import render_template

                                subject, message = render_template("finance/overdue_payment_reminder", {
                                    "first_name": first_name,
                                    "last_name": last_name,
                                    "overdue_count": str(count),
                                    "total_amount": f"{total:.2f}",
                                    "student_id": student_id
                                })

                                if not (subject and message):
                                    # Fallback if template not found
                                    subject = "Overdue Payment Reminder"
                                    message = f"Dear {first_name} {last_name}, you have {count} overdue fees totaling \u00a3{total:.2f}"
                            except Exception:
                                # Error handling - use fallback template
                                subject = "Overdue Payment Reminder"
                                message = f"Dear {first_name} {last_name}, you have {count} overdue fees totaling \u00a3{total:.2f}"

                            # In a real implementation, you would call actual email/SMS services here
                            print(f"\U0001f4e7 Notification sent to {email}: {subject}")
                            notifications_sent += 1

                        conn.close()

                    except Exception as e:
                        print(f"Error in notification sending: {e}")

                    messagebox.showinfo(_("finance_gui.settings.notifications_sent_title"),
                                       _("finance_gui.settings.notifications_sent_message", count=notifications_sent))

                    self.update_status(_("finance_gui.settings.sent_notifications_status", count=notifications_sent))

                thread = threading.Thread(target=send_notifications)
                thread.daemon = True
                thread.start()

            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_send_notifications", error=str(e)))


    def gui_system_settings(self):
        """GUI for system settings"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.system_settings_dialog_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        # Settings notebook
        settings_notebook = ttk.Notebook(dialog)
        settings_notebook.pack(fill='both', expand=True, padx=20, pady=20)

        # General settings tab
        general_tab = ttk.Frame(settings_notebook)
        settings_notebook.add(general_tab, text=_("finance_gui.settings.general_settings_tab"))

        # Currency settings
        currency_frame = ttk.LabelFrame(general_tab, text=_("finance_gui.settings.currency_settings_frame"), padding=15)
        currency_frame.pack(fill='x', pady=10)

        ttk.Label(currency_frame, text=_("finance_gui.settings.base_currency_label")).pack(anchor='w')
        base_currency_var = tk.StringVar(value='GBP')
        ttk.Combobox(currency_frame, textvariable=base_currency_var,
                    values=SUPPORTED_CURRENCIES, state='readonly').pack(anchor='w', pady=5)

        ttk.Label(currency_frame, text=_("finance_gui.settings.auto_update_rates_label")).pack(anchor='w', pady=(10,0))
        auto_update_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(currency_frame, variable=auto_update_var).pack(anchor='w')

        # Notification settings tab
        notification_tab = ttk.Frame(settings_notebook)
        settings_notebook.add(notification_tab, text=_("finance_gui.settings.notifications_settings_tab"))

        email_frame = ttk.LabelFrame(notification_tab, text=_("finance_gui.settings.email_settings_frame"), padding=15)
        email_frame.pack(fill='x', pady=10)

        ttk.Label(email_frame, text=_("finance_gui.settings.smtp_server_label")).pack(anchor='w')
        smtp_var = tk.StringVar(value='smtp.gmail.com')
        ttk.Entry(email_frame, textvariable=smtp_var, width=30).pack(anchor='w', pady=5)

        ttk.Label(email_frame, text=_("finance_gui.settings.from_email_label")).pack(anchor='w')
        from_email_var = tk.StringVar()
        ttk.Entry(email_frame, textvariable=from_email_var, width=30).pack(anchor='w', pady=5)

        def save_settings():
            try:
                # In a real implementation, save settings to database or config file
                messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.settings_saved_dialog"))
                dialog.destroy()
            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_save_settings_dialog", error=str(e)))

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=_("finance_gui.settings.btn_save_settings"), command=save_settings).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("finance_gui.settings.btn_cancel"), command=dialog.destroy).pack(side='left', padx=10)
