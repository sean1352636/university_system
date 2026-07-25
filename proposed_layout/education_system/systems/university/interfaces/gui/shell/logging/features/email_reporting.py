import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime

from education_system.systems.university.interfaces.gui.shell.logging.helpers import _t


class EmailReportingMixin:
    """Mixin providing email reporting functionality."""

    def scheduled_reports_menu_gui(self):
        """GUI version of scheduled reports menu"""
        reports_window = tk.Toplevel(self.root)
        reports_window.title(_t("log_management.scheduled_reports.title"))
        reports_window.geometry("600x500")

        ttk.Label(reports_window, text=_t("log_management.scheduled_reports.config_title"),
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Daily Email Reports
        daily_frame = ttk.LabelFrame(reports_window, text=_t("log_management.scheduled_reports.daily_reports"))
        daily_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(daily_frame, text=_t("log_management.scheduled_reports.email_address")).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        daily_email_var = tk.StringVar(value=self.log_manager.config.get('alert_email', ''))
        ttk.Entry(daily_frame, textvariable=daily_email_var, width=30).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(daily_frame, text=_t("log_management.scheduled_reports.send_time")).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        time_var = tk.StringVar(value="08:00")
        ttk.Entry(daily_frame, textvariable=time_var, width=10).grid(row=1, column=1, sticky="w", padx=5, pady=2)

        def save_daily_reports():
            self.log_manager.config.set('alert_email', daily_email_var.get())
            self.log_manager.config.set('daily_report_time', time_var.get())
            messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.scheduled_reports.saved"))

        ttk.Button(daily_frame, text=_t("log_management.scheduled_reports.save_daily"), command=save_daily_reports).grid(row=2, column=0, columnspan=2, pady=10)

        # Weekly Reports
        weekly_frame = ttk.LabelFrame(reports_window, text=_t("log_management.scheduled_reports.weekly_reports"))
        weekly_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(weekly_frame, text=_t("log_management.scheduled_reports.email_address")).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        weekly_email_var = tk.StringVar(value=self.log_manager.config.get('weekly_report_email', ''))
        ttk.Entry(weekly_frame, textvariable=weekly_email_var, width=30).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(weekly_frame, text=_t("log_management.scheduled_reports.day_of_week")).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        day_var = tk.StringVar(value="Monday")
        day_combo = ttk.Combobox(weekly_frame, textvariable=day_var,
                                values=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
        day_combo.grid(row=1, column=1, sticky="w", padx=5, pady=2)

        def save_weekly_reports():
            day_map = {"Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4,
                      "Friday": 5, "Saturday": 6, "Sunday": 7}
            self.log_manager.config.set('weekly_report_email', weekly_email_var.get())
            self.log_manager.config.set('weekly_report_day', day_map[day_var.get()])
            messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.reports.weekly_saved"))

        ttk.Button(weekly_frame, text=_t("log_management.scheduled_reports.save_weekly"), command=save_weekly_reports).grid(row=2, column=0, columnspan=2, pady=10)

    def setup_weekly_report_gui(self):
        """GUI version of weekly report setup"""
        weekly_window = tk.Toplevel(self.root)
        weekly_window.title(_t("log_management.dialogs.weekly_report_setup"))
        weekly_window.geometry("400x300")

        ttk.Label(weekly_window, text=_t("log_management.weekly_report.title"),
                 font=("Arial", 12, "bold")).pack(pady=10)

        # Email settings
        email_frame = ttk.LabelFrame(weekly_window, text="Email Configuration")
        email_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(email_frame, text=_t("log_management.security_alerts_config.email_address")).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        email_var = tk.StringVar(value=self.log_manager.config.get('weekly_report_email', ''))
        ttk.Entry(email_frame, textvariable=email_var, width=30).grid(row=0, column=1, padx=5, pady=5)

        # Schedule settings
        schedule_frame = ttk.LabelFrame(weekly_window, text="Schedule Configuration")
        schedule_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(schedule_frame, text=_t("log_management.weekly_report.day_of_week")).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        day_var = tk.StringVar(value="Monday")
        day_combo = ttk.Combobox(schedule_frame, textvariable=day_var,
                                values=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
        day_combo.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(schedule_frame, text=_t("log_management.weekly_report.time")).grid(row=1, column=0, sticky="w", padx=5, pady=5)
        time_var = tk.StringVar(value="09:00")
        ttk.Entry(schedule_frame, textvariable=time_var, width=10).grid(row=1, column=1, sticky="w", padx=5, pady=5)

        # Report content
        content_frame = ttk.LabelFrame(weekly_window, text="Report Content")
        content_frame.pack(fill=tk.X, padx=10, pady=5)

        include_summary_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(content_frame, text="Activity Summary", variable=include_summary_var).pack(anchor="w", padx=10, pady=2)

        include_charts_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(content_frame, text="Activity Charts", variable=include_charts_var).pack(anchor="w", padx=10, pady=2)

        include_alerts_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(content_frame, text="Security Alerts", variable=include_alerts_var).pack(anchor="w", padx=10, pady=2)

        def save_weekly_settings():
            try:
                day_map = {"Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4,
                          "Friday": 5, "Saturday": 6, "Sunday": 7}

                self.log_manager.config.set('weekly_report_email', email_var.get())
                self.log_manager.config.set('weekly_report_day', day_map[day_var.get()])
                self.log_manager.config.set('weekly_report_time', time_var.get())
                self.log_manager.config.set('weekly_include_summary', include_summary_var.get())
                self.log_manager.config.set('weekly_include_charts', include_charts_var.get())
                self.log_manager.config.set('weekly_include_alerts', include_alerts_var.get())

                messagebox.showinfo("Success", f"Weekly reports configured!\nReports will be sent every {day_var.get()} at {time_var.get()}")
                weekly_window.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Error saving settings: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(weekly_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Save Settings", command=save_weekly_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=weekly_window.destroy).pack(side=tk.RIGHT, padx=5)

    def setup_daily_email_report_gui(self):
        """GUI version of daily email report setup"""
        daily_window = tk.Toplevel(self.root)
        daily_window.title(_t("log_management.dialogs.daily_report_setup"))
        daily_window.geometry("400x250")

        ttk.Label(daily_window, text=_t("log_management.daily_report.title"),
                 font=("Arial", 12, "bold")).pack(pady=10)

        # Email settings
        email_frame = ttk.LabelFrame(daily_window, text="Email Configuration")
        email_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(email_frame, text=_t("log_management.security_alerts_config.email_address")).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        email_var = tk.StringVar(value=self.log_manager.config.get('alert_email', ''))
        ttk.Entry(email_frame, textvariable=email_var, width=30).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(email_frame, text=_t("log_management.daily_report.send_time")).grid(row=1, column=0, sticky="w", padx=5, pady=5)
        time_var = tk.StringVar(value="08:00")
        ttk.Entry(email_frame, textvariable=time_var, width=10).grid(row=1, column=1, sticky="w", padx=5, pady=5)

        # SMTP settings
        smtp_frame = ttk.LabelFrame(daily_window, text="SMTP Configuration")
        smtp_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(smtp_frame, text=_t("log_management.daily_report.smtp_server")).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        smtp_server_var = tk.StringVar(value=self.log_manager.config.get('smtp_server', ''))
        ttk.Entry(smtp_frame, textvariable=smtp_server_var, width=25).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(smtp_frame, text=_t("log_management.daily_report.smtp_port")).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        smtp_port_var = tk.StringVar(value=str(self.log_manager.config.get('smtp_port', 587)))
        ttk.Entry(smtp_frame, textvariable=smtp_port_var, width=10).grid(row=1, column=1, sticky="w", padx=5, pady=2)

        def save_daily_settings():
            try:
                self.log_manager.config.set('alert_email', email_var.get())
                self.log_manager.config.set('daily_report_time', time_var.get())
                self.log_manager.config.set('smtp_server', smtp_server_var.get())
                self.log_manager.config.set('smtp_port', int(smtp_port_var.get()))

                messagebox.showinfo("Success", f"Daily email reports configured!\nReports will be sent at {time_var.get()} daily")
                daily_window.destroy()

            except ValueError:
                messagebox.showerror("Error", "Please enter a valid port number")
            except Exception as e:
                messagebox.showerror("Error", f"Error saving settings: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(daily_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Save Settings", command=save_daily_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=daily_window.destroy).pack(side=tk.RIGHT, padx=5)

    def setup_security_alerts_gui(self):
        """GUI version of security alerts setup"""
        alerts_window = tk.Toplevel(self.root)
        alerts_window.title(_t("log_management.dialogs.security_alerts_config"))
        alerts_window.geometry("500x400")

        ttk.Label(alerts_window, text=_t("log_management.security_alerts_config.title"),
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Email configuration
        email_frame = ttk.LabelFrame(alerts_window, text="Alert Email Settings")
        email_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(email_frame, text=_t("log_management.security_alerts_config.email_address")).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        email_var = tk.StringVar(value=self.log_manager.config.get('security_alert_email', ''))
        ttk.Entry(email_frame, textvariable=email_var, width=30).grid(row=0, column=1, padx=5, pady=5)

        # Threshold settings
        threshold_frame = ttk.LabelFrame(alerts_window, text="Alert Thresholds")
        threshold_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(threshold_frame, text=_t("log_management.security_alerts_config.failed_login_threshold")).grid(row=0, column=0, sticky="w", padx=5, pady=5)
        login_threshold_var = tk.StringVar(value=str(self.log_manager.config.get('failed_login_threshold', 5)))
        ttk.Spinbox(threshold_frame, from_=1, to=50, textvariable=login_threshold_var, width=10).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(threshold_frame, text=_t("log_management.security_alerts_config.rapid_actions_threshold")).grid(row=1, column=0, sticky="w", padx=5, pady=5)
        rapid_threshold_var = tk.StringVar(value=str(self.log_manager.config.get('rapid_actions_threshold', 20)))
        ttk.Spinbox(threshold_frame, from_=5, to=100, textvariable=rapid_threshold_var, width=10).grid(row=1, column=1, padx=5, pady=5)

        # Alert types
        types_frame = ttk.LabelFrame(alerts_window, text="Alert Types")
        types_frame.pack(fill=tk.X, padx=10, pady=5)

        failed_logins_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(types_frame, text="Failed Login Attempts", variable=failed_logins_var).pack(anchor="w", padx=10, pady=2)

        unusual_hours_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(types_frame, text="Unusual Activity Hours", variable=unusual_hours_var).pack(anchor="w", padx=10, pady=2)

        rapid_actions_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(types_frame, text="Rapid Fire Actions", variable=rapid_actions_var).pack(anchor="w", padx=10, pady=2)

        admin_actions_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(types_frame, text="Admin Actions", variable=admin_actions_var).pack(anchor="w", padx=10, pady=2)

        def save_security_settings():
            try:
                self.log_manager.config.set('security_alert_email', email_var.get())
                self.log_manager.config.set('failed_login_threshold', int(login_threshold_var.get()))
                self.log_manager.config.set('rapid_actions_threshold', int(rapid_threshold_var.get()))
                self.log_manager.config.set('alert_failed_logins', failed_logins_var.get())
                self.log_manager.config.set('alert_unusual_hours', unusual_hours_var.get())
                self.log_manager.config.set('alert_rapid_actions', rapid_actions_var.get())
                self.log_manager.config.set('alert_admin_actions', admin_actions_var.get())

                messagebox.showinfo("Success", "Security alert settings saved successfully!")

            except ValueError:
                messagebox.showerror("Error", "Please enter valid threshold values")
            except Exception as e:
                messagebox.showerror("Error", f"Error saving settings: {str(e)}")

        def test_security_alerts():
            try:
                alerts = self.log_manager.alerts.run_alert_checks()
                if alerts:
                    messagebox.showinfo("Test Results", f"Found {len(alerts)} alerts")
                else:
                    messagebox.showinfo("Test Results", "No alerts found")
            except Exception as e:
                messagebox.showerror("Error", f"Error testing alerts: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(alerts_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Save Settings", command=save_security_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Test Alerts", command=test_security_alerts).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("log_management.buttons.close"), command=alerts_window.destroy).pack(side=tk.RIGHT, padx=5)

    def send_test_email(self):
        """Send test email to verify SMTP configuration"""
        try:
            from education_system.systems.university.infrastructure.email.smtp import send_email_via_smtp

            alert_email = self.log_manager.config.get('alert_email')

            if not alert_email:
                messagebox.showerror("Configuration Error", "Alert email not configured")
                return

            body = "This is a test email from Log Management System"
            subject = "Log Management System - Test Email"

            current_time = datetime.now().isoformat()
            success = send_email_via_smtp(
                recipient_email=alert_email,
                subject=subject,
                body=body,
                cc=None,
                bcc=None,
                attachments=None,
                current_time=current_time
            )

            if success:
                messagebox.showinfo("Success", f"Test email sent to {alert_email}")
            else:
                messagebox.showerror("Email Error", "Failed to send test email")

        except Exception as e:
            messagebox.showerror("Email Error", f"Failed to send test email: {str(e)}")

    def email_report_dialog(self):
        """Dialog for sending email reports"""
        email_window = tk.Toplevel(self.root)
        email_window.title(_t("log_management.dialogs.email_report"))
        email_window.geometry("400x300")

        ttk.Label(email_window, text=_t("log_management.email_report.title"),
                 font=("Arial", 12, "bold")).pack(pady=10)

        # Report type selection
        type_frame = ttk.Frame(email_window)
        type_frame.pack(pady=10)

        ttk.Label(type_frame, text=_t("log_management.email_report.report_type")).pack(anchor="w")
        report_type = tk.StringVar(value="daily")
        ttk.Radiobutton(type_frame, text="Daily Summary",
                       variable=report_type, value="daily").pack(anchor="w")
        ttk.Radiobutton(type_frame, text="Weekly Analytics",
                       variable=report_type, value="weekly").pack(anchor="w")
        ttk.Radiobutton(type_frame, text="Security Alert",
                       variable=report_type, value="security").pack(anchor="w")

        # Email address - get admin email from database
        email_frame = ttk.Frame(email_window)
        email_frame.pack(pady=10, fill=tk.X, padx=20)

        ttk.Label(email_frame, text=_t("log_management.security_alerts_config.email_address")).pack(anchor="w")

        # Get admin email from database
        admin_email = self.log_manager.config.get('alert_email', '')
        try:
            from education_system.systems.university.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("""
                    SELECT email FROM users
                    WHERE role = 'admin' AND email IS NOT NULL AND email != ''
                    LIMIT 1
                """)
                admin_row = cursor.fetchone()
                if admin_row and admin_row[0]:
                    admin_email = admin_row[0]
        except Exception:
            pass

        email_var = tk.StringVar(value=admin_email)
        ttk.Entry(email_frame, textvariable=email_var).pack(fill=tk.X)

        def send_report():
            try:
                from education_system.systems.university.infrastructure.email.email_service import send_email

                email_addr = email_var.get().strip()
                if not email_addr:
                    messagebox.showerror("Error", "Email address required")
                    return

                # Generate report based on type
                report_content = self.generate_email_report_content(report_type.get())

                # Build email subject and body
                report_type_name = report_type.get().replace('_', ' ').title()
                subject = f"Log Management {report_type_name} Report - {datetime.now().strftime('%Y-%m-%d')}"

                body = f"""Log Management Report

Report Type: {report_type_name}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'=' * 60}

{report_content}

{'=' * 60}

This report was automatically generated by the Log Management System.
"""

                # Send the email
                result = send_email(
                    recipient_email=email_addr,
                    subject=subject,
                    body=body
                )

                if result:
                    messagebox.showinfo("Success", f"Report sent successfully to {email_addr}")
                else:
                    messagebox.showinfo("Queued", f"Report queued for delivery to {email_addr}")
                email_window.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to send report: {str(e)}")

        button_frame = ttk.Frame(email_window)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Send Report", command=send_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Test Email", command=self.send_test_email).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=email_window.destroy).pack(side=tk.LEFT, padx=5)

    def generate_email_report_content(self, report_type):
        """Generate content for email reports"""
        if report_type == "daily":
            summary = self.log_manager.analytics.generate_activity_summary(1)
            return f"Daily Summary: {summary.get('total_activities', 0)} activities today"
        elif report_type == "weekly":
            summary = self.log_manager.analytics.generate_activity_summary(7)
            return f"Weekly Summary: {summary.get('total_activities', 0)} activities this week"
        else:
            return "Security Alert: No recent alerts found"
