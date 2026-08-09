import csv
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime
from typing import List
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.domain.pastoral.health.dentist.services.dentist_core import PatientManager, AppointmentManager, TreatmentManager, PrescriptionManager, TransactionManager, ReportManager, init_dentist_db, TREATMENT_TYPES, DENTIST_STAFF, APPOINTMENT_SLOTS
from education_system.systems.university.interfaces.gui.pastoral.health.health_portal.dentist import EMAIL_AVAILABLE, send_email, render_template, _send_dentist_email

class ReportServiceMixin:
        def generate_admin_report(self):
            """Function 23: Generate admin report."""
            report_type = self.report_type_var.get()
            if report_type == 'daily':
                data = ReportManager.get_daily_report()
                report = f"=== Daily Report ===\nDate: {data.get('date', 'N/A')}\nTotal Appointments: {data.get('total_appointments', 0)}\nCompleted: {data.get('completed_appointments', 0)}\nTreatments: {data.get('treatments_performed', 0)}\nRevenue: GBP {data.get('revenue', 0):.2f}"
            else:
                data = ReportManager.get_monthly_summary()
                report = f"=== Monthly Summary ===\nPeriod: {data.get('month', '')}/{data.get('year', '')}\nTotal Appointments: {data.get('total_appointments', 0)}\nNew Patients: {data.get('new_patients', 0)}\nRevenue: GBP {data.get('total_revenue', 0):.2f}\n\nTreatments by Type:\n"
                for ttype, info in data.get('treatments_by_type', {}).items():
                    report += f"  {ttype}: {info['count']} (GBP {info['revenue']:.2f})\n"
            self.current_report = report
            self.report_text.delete("1.0", tk.END)
            self.report_text.insert("1.0", report)
            messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.report_generated"))

        def _get_admin_emails(self) -> List[str]:
            """Get email addresses of all admin users."""
            try:
                from education_system.systems.university.infrastructure.database.db import get_connection
                with get_connection() as conn:
                    cursor = conn.execute('''
                        SELECT email FROM users
                        WHERE role = 'admin' AND email IS NOT NULL AND email != ''
                    ''')
                    return [row[0] for row in cursor.fetchall()]
            except Exception as e:
                print(f"Error getting admin emails: {e}")
                return []

        def email_admin_report(self):
            """Function 24: Email report to admin automatically."""
            if not self.current_report:
                messagebox.showwarning(_t("dentist.window_title"), _t("dentist.warnings.generate_report_first"))
                return

            if not EMAIL_AVAILABLE:
                messagebox.showwarning(_t("dentist.window_title"), _t("dentist.warnings.email_unavailable"))
                return

            # Auto-detect admin emails
            admin_emails = self._get_admin_emails()

            if not admin_emails:
                # Fallback: prompt for email if no admins found
                admin_email = simpledialog.askstring(
                    _t("dentist.window_title"),
                    "No admin emails found. Enter admin email manually:"
                )
                if admin_email:
                    admin_emails = [admin_email]
                else:
                    return

            # Send report to all admins
            subject = f"Dental Clinic Report - {datetime.now().strftime('%Y-%m-%d')}"
            success_count = 0
            for email in admin_emails:
                if _send_dentist_email(email, subject, self.current_report):
                    success_count += 1

            if success_count > 0:
                messagebox.showinfo(
                    _t("dentist.window_title"),
                    f"Report sent to {success_count} admin(s): {', '.join(admin_emails)}"
                )
                print(f"[Dentist] Admin report sent to {success_count} admin(s)")
            else:
                messagebox.showerror(_t("dentist.window_title"), _t("dentist.errors.email_failed"))
