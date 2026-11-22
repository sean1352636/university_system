
from education_system.systems.university.infrastructure.i18n import get_text as _t
import html
import tkinter as tk
from education_system.systems.university.domains.health.interfaces.gui.health._dialogs import make_toplevel
from tkinter import ttk, scrolledtext
from education_system.systems.university.domains.health.interfaces.gui.health._dialogs import messagebox, filedialog
from datetime import datetime

from education_system.systems.university.domains.health.interfaces.gui.health.health_portal import access_ui


class StudentReportsMixin:
    """Mixin for individual student health report generation, display, and email."""

    def create_generate_health_reports(self):
        """Generate various health reports for the user"""
        content_frame = ttk.Frame(self.content_area)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        title_label = ttk.Label(content_frame, text=_t('gui.pastoral.health.health_portal.reports.student_reports.labels.health_reports_generator', default="Health Reports Generator"),
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 20))

        report_frame = ttk.LabelFrame(content_frame, text=_t('gui.pastoral.health.health_portal.reports.student_reports.labels.select_report_type', default="Select Report Type"), padding=15)
        report_frame.pack(fill=tk.X, pady=(0, 20))

        # Whose report: a student's own (locked); the health team names one.
        subject_row = ttk.Frame(report_frame)
        subject_row.pack(anchor=tk.W, pady=(0, 6))
        ttk.Label(subject_row, text="Student ID:").pack(side=tk.LEFT)
        self.report_student_var = tk.StringVar()
        subject_entry = ttk.Entry(subject_row, textvariable=self.report_student_var, width=20)
        subject_entry.pack(side=tk.LEFT, padx=5)
        access_ui.lock_to_own(self.auth, self.report_student_var, subject_entry)

        self.report_type = tk.StringVar(value=_t('gui.pastoral.health.health_portal.reports.student_reports.values.immunization', default="immunization"))

        ttk.Radiobutton(report_frame, text=_t('gui.pastoral.health.health_portal.reports.student_reports.buttons.immunization_status_report', default="Immunization Status Report"),
                       variable=self.report_type, value="immunization").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(report_frame, text=_t('gui.pastoral.health.health_portal.reports.student_reports.buttons.health_summary_report', default="Health Summary Report"),
                       variable=self.report_type, value="health_summary").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(report_frame, text=_t('gui.pastoral.health.health_portal.reports.student_reports.buttons.appointment_history_report', default="Appointment History Report"),
                       variable=self.report_type, value="appointment_history").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(report_frame, text=_t('gui.pastoral.health.health_portal.reports.student_reports.buttons.medical_history_report', default="Medical History Report"),
                       variable=self.report_type, value="medical_history").pack(anchor=tk.W, pady=2)

        button_frame = ttk.Frame(content_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text=_t('gui.pastoral.health.health_portal.reports.student_reports.buttons.generate_report', default="Generate Report"),
                  command=self.generate_selected_report).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(button_frame, text=_t('gui.pastoral.health.health_portal.reports.student_reports.buttons.send_to_admin', default="Send to Admin"),
                  command=self.send_report_to_admin).pack(side=tk.LEFT, padx=(0, 10))

        report_display_frame = ttk.LabelFrame(content_frame, text=_t('gui.pastoral.health.health_portal.reports.student_reports.labels.generated_report', default="Generated Report"), padding=15)
        report_display_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 0))

        self.report_text = scrolledtext.ScrolledText(report_display_frame, wrap=tk.WORD, height=15)
        self.report_text.pack(fill=tk.BOTH, expand=True)

    def generate_selected_report(self):
        """Generate the selected type of health report"""
        typed = self.report_student_var.get().strip() if hasattr(self, 'report_student_var') else ""
        sid = access_ui.scoped_student(self.root, self.auth, typed,
                                       var=getattr(self, 'report_student_var', None))
        if sid is None:
            return
        if not sid:
            messagebox.showerror(_t('gui.pastoral.health.health_portal.reports.student_reports.dialogs.access_denied', default="Access Denied"), "Enter the student ID the report is for.")
            return
        if not access_ui.record_view(self.root, self.auth, "health_report", student_id=sid):
            return
        # The report subject is a student number (never users.id).
        self._report_sid = sid

        report_type = self.report_type.get()

        try:
            report_content = ""

            if report_type == "immunization":
                report_content = self.get_immunization_report()
            elif report_type == "health_summary":
                report_content = self.get_health_summary_report()
            elif report_type == "appointment_history":
                report_content = self.get_appointment_history_report()
            elif report_type == "medical_history":
                report_content = self.get_medical_history_report()

            self.show_report_window(report_content, report_type)

            self.log_audit_event('generate_report', 'health_report', report_type)

        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.health.health_portal.reports.student_reports.dialogs.error', default="Error"), f"Failed to generate report: {str(e)}")

    def show_report_window(self, report_content, report_type):
        """Show report in a new window with save and email buttons"""
        report_window = make_toplevel(self.root)
        report_window.title(f"Health Report - {report_type.replace('_', ' ').title()}")
        report_window.geometry("800x600")

        main_frame = ttk.Frame(report_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        report_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=('Courier', 10))
        report_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        report_text.insert(1.0, report_content)
        report_text.config(state='disabled')

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        def save_report_as_txt():
            """Save report as text file"""
            try:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                default_filename = f"health_report_{report_type}_{timestamp}.txt"

                filename = filedialog.asksaveasfilename(
                    initialfile=default_filename,
                    defaultextension=".txt",
                    filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                    title=_t('gui.pastoral.health.health_portal.reports.student_reports.dialogs.save_report_as', default="Save Report As")
                )

                if filename:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(report_content)

                    self.log_audit_event('save_report', 'health_report', filename)
                    messagebox.showinfo(_t('gui.pastoral.health.health_portal.reports.student_reports.dialogs.success', default="Success"), f"Report saved to: {filename}")

            except Exception as e:
                messagebox.showerror(_t('gui.pastoral.health.health_portal.reports.student_reports.dialogs.error', default="Error"), f"Failed to save report: {str(e)}")

        def email_report_to_admin():
            """Email report to admin"""
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT email FROM users
                    WHERE role = 'admin' AND email IS NOT NULL
                """)
                admin_emails = [row[0] for row in cursor.fetchall()]
                conn.close()

                if not admin_emails:
                    messagebox.showwarning(_t('gui.pastoral.health.health_portal.reports.student_reports.dialogs.no_admin_emails', default="No Admin Emails"), _t('gui.pastoral.health.health_portal.reports.student_reports.dialogs.no_admin_email_addresses_found_in_the_system', default="No admin email addresses found in the system."))
                    return

                result = messagebox.askyesno(
                    _t('gui.pastoral.health.health_portal.reports.student_reports.dialogs.email_report', default="Email Report"),
                    f"Send this report to {len(admin_emails)} admin(s)?\n\n"
                    f"Recipients: {', '.join(admin_emails[:3])}"
                    f"{'...' if len(admin_emails) > 3 else ''}"
                )

                if result:
                    self.log_audit_event('email_report', 'health_report', f"to_{len(admin_emails)}_admins")
                    messagebox.showinfo(_t('gui.pastoral.health.health_portal.reports.student_reports.dialogs.success', default="Success"), _t('gui.pastoral.health.health_portal.reports.student_reports.dialogs.report_sent_to_administrators', default="Report sent to administrators."))

            except Exception as e:
                messagebox.showerror(_t('gui.pastoral.health.health_portal.reports.student_reports.dialogs.error', default="Error"), f"Failed to email report: {str(e)}")

        ttk.Button(button_frame, text=_t('gui.pastoral.health.health_portal.reports.student_reports.buttons.save_as_txt', default="Save as TXT"), command=save_report_as_txt).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.health.health_portal.reports.student_reports.buttons.email_to_admin', default="Email to Admin"), command=email_report_to_admin).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.health.health_portal.reports.student_reports.buttons.close', default="Close"), command=report_window.destroy).pack(side=tk.RIGHT)

    def generate_immunization_report(self):
        """Generate immunization status report"""
        user_id = self._report_student()

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT vaccine_name, administered_date, expiry_date, administered_by, lot_number
                FROM vaccination_records
                WHERE student_id = ?
                ORDER BY administered_date DESC
                """, [user_id])

                vaccinations = cursor.fetchall()

                report = "IMMUNIZATION STATUS REPORT\n"
                report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                report += f"Patient: {user_id}\n"
                report += "=" * 60 + "\n\n"

                if vaccinations:
                    for vac in vaccinations:
                        report += f"Vaccine: {vac[0]}\n"
                        report += f"Administered Date: {vac[1]}\n"
                        report += f"Expiry Date: {vac[2] or 'N/A'}\n"
                        report += f"Administered By: {vac[3] or 'Not specified'}\n"
                        report += f"Lot Number: {vac[4] or 'N/A'}\n"
                        report += "-" * 40 + "\n"
                else:
                    report += "No vaccination records found.\n"

                self.report_text.insert(tk.END, report)
        except Exception as e:
            self.report_text.insert(tk.END, f"Error generating immunization report: {str(e)}")

    def generate_health_summary_report(self):
        """Generate comprehensive health summary report"""
        user_id = self._report_student()

        report = "HEALTH SUMMARY REPORT\n"
        report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"Patient: {user_id}\n"
        report += "=" * 60 + "\n\n"

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                SELECT record_type, COUNT(*) as count, MAX(created_at) as latest
                FROM health_records
                WHERE student_id = ?
                GROUP BY record_type ORDER BY latest DESC
                """, [user_id])

                records = cursor.fetchall()

                report += "HEALTH RECORDS SUMMARY:\n"
                if records:
                    for record in records:
                        report += f"- {record[0]}: {record[1]} records (Latest: {record[2]})\n"
                else:
                    report += "No health records found.\n"

                cursor.execute("""
                SELECT COUNT(*) as total_vaccines, MAX(administered_date) as latest_vaccine
                FROM vaccination_records WHERE student_id = ?
                """, [user_id])

                vac_summary = cursor.fetchone()
                report += "\nVACCINATION SUMMARY:\n"
                report += f"Total Vaccinations: {vac_summary[0] if vac_summary else 0}\n"
                report += f"Latest Vaccination: {vac_summary[1] if vac_summary and vac_summary[1] else 'None'}\n\n"

                self.report_text.insert(tk.END, report)
        except Exception as e:
            self.report_text.insert(tk.END, f"Error generating health summary: {str(e)}")

    def generate_appointment_history_report(self):
        """Generate appointment history report"""
        user_id = self._report_student()

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT appointment_date, appointment_time, appointment_type, provider, status, notes
                FROM health_appointments
                WHERE student_id = ?
                ORDER BY appointment_date DESC, appointment_time DESC
                """, [user_id])

                appointments = cursor.fetchall()

                report = "APPOINTMENT HISTORY REPORT\n"
                report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                report += f"Patient: {user_id}\n"
                report += "=" * 60 + "\n\n"

                if appointments:
                    for apt in appointments:
                        report += f"Date: {apt[0]} at {apt[1]}\n"
                        report += f"Type: {apt[2]}\n"
                        report += f"Provider: {apt[3] or 'Not specified'}\n"
                        report += f"Status: {apt[4]}\n"
                        if apt[5]:
                            report += f"Notes: {apt[5]}\n"
                        report += "-" * 40 + "\n"
                else:
                    report += "No appointment history found.\n"

                self.report_text.insert(tk.END, report)
        except Exception as e:
            self.report_text.insert(tk.END, f"Error generating appointment history: {str(e)}")

    def generate_medical_history_report(self):
        """Generate medical history report"""
        user_id = self._report_student()

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT condition_name, icd_code, severity, diagnosed_date, status, provider, notes
                FROM medical_conditions
                WHERE student_id = ?
                ORDER BY diagnosed_date DESC
                """, [user_id])

                records = cursor.fetchall()

                report = "MEDICAL HISTORY REPORT\n"
                report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                report += f"Patient: {user_id}\n"
                report += "=" * 60 + "\n\n"

                if records:
                    for record in records:
                        report += f"Condition: {record[0] or 'Not specified'}\n"
                        report += f"ICD Code: {record[1] or 'N/A'}\n"
                        report += f"Severity: {record[2] or 'Not specified'}\n"
                        report += f"Diagnosed Date: {record[3] or 'Not specified'}\n"
                        report += f"Status: {record[4] or 'Active'}\n"
                        report += f"Provider: {record[5] or 'Not specified'}\n"
                        if record[6]:
                            report += f"Notes: {record[6]}\n"
                        report += "-" * 40 + "\n"
                else:
                    report += "No medical history found.\n"

                self.report_text.insert(tk.END, report)
        except Exception as e:
            self.report_text.insert(tk.END, f"Error generating medical history: {str(e)}")

    def get_immunization_report(self):
        """Get immunization status report as string"""
        user_id = self._report_student()

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT vaccine_name, administered_date, expiry_date, administered_by, lot_number
                FROM vaccination_records
                WHERE student_id = ?
                ORDER BY administered_date DESC
                """, [user_id])

                vaccinations = cursor.fetchall()

                report = "IMMUNIZATION STATUS REPORT\n"
                report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                report += f"Patient: {user_id}\n"
                report += "=" * 60 + "\n\n"

                if vaccinations:
                    for vac in vaccinations:
                        report += f"Vaccine: {vac[0]}\n"
                        report += f"Administered Date: {vac[1]}\n"
                        report += f"Expiry Date: {vac[2] or 'N/A'}\n"
                        report += f"Administered By: {vac[3] or 'Not specified'}\n"
                        report += f"Lot Number: {vac[4] or 'N/A'}\n"
                        report += "-" * 40 + "\n"
                else:
                    report += "No vaccination records found.\n"

                return report
        except Exception as e:
            return f"Error generating immunization report: {str(e)}"

    def get_health_summary_report(self):
        """Get comprehensive health summary report as string"""
        user_id = self._report_student()

        report = "HEALTH SUMMARY REPORT\n"
        report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"Patient: {user_id}\n"
        report += "=" * 60 + "\n\n"

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                SELECT record_type, COUNT(*) as count, MAX(created_at) as latest
                FROM health_records
                WHERE student_id = ?
                GROUP BY record_type ORDER BY latest DESC
                """, [user_id])

                health_records = cursor.fetchall()

                if health_records:
                    report += "Health Records Summary:\n"
                    for record in health_records:
                        report += f"  {record[0]}: {record[1]} record(s) (Latest: {record[2] or 'Unknown'})\n"
                    report += "\n"

                cursor.execute("""
                SELECT COUNT(*) FROM vaccination_records WHERE student_id = ?
                """, [user_id])
                vac_count = cursor.fetchone()[0]
                report += f"Total Vaccinations: {vac_count}\n"

                cursor.execute("""
                SELECT COUNT(*) FROM health_appointments WHERE student_id = ?
                """, [user_id])
                apt_count = cursor.fetchone()[0]
                report += f"Total Appointments: {apt_count}\n\n"

                report += "=" * 60 + "\n"
                report += "For detailed information, please generate specific reports.\n"

                return report
        except Exception as e:
            return report + f"\nError generating health summary: {str(e)}"

    def get_appointment_history_report(self):
        """Get appointment history report as string"""
        user_id = self._report_student()

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT appointment_date, appointment_time, provider, department, reason, status, notes
                FROM health_appointments
                WHERE student_id = ?
                ORDER BY appointment_date DESC, appointment_time DESC
                """, [user_id])

                appointments = cursor.fetchall()

                report = "APPOINTMENT HISTORY REPORT\n"
                report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                report += f"Patient: {user_id}\n"
                report += "=" * 60 + "\n\n"

                if appointments:
                    for apt in appointments:
                        report += f"Date: {apt[0]} at {apt[1]}\n"
                        report += f"Provider: {apt[2] or 'Not specified'}\n"
                        report += f"Department: {apt[3] or 'General'}\n"
                        report += f"Reason: {apt[4] or 'Not specified'}\n"
                        report += f"Status: {apt[5] or 'Scheduled'}\n"
                        if apt[6]:
                            report += f"Notes: {apt[6]}\n"
                        report += "-" * 40 + "\n"
                else:
                    report += "No appointment history found.\n"

                return report
        except Exception as e:
            return f"Error generating appointment history: {str(e)}"

    def get_medical_history_report(self):
        """Get medical history report as string"""
        user_id = self._report_student()

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT condition_name, icd_code, severity, diagnosed_date, status, provider, notes
                FROM medical_conditions
                WHERE student_id = ?
                ORDER BY diagnosed_date DESC
                """, [user_id])

                records = cursor.fetchall()

                report = "MEDICAL HISTORY REPORT\n"
                report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                report += f"Patient: {user_id}\n"
                report += "=" * 60 + "\n\n"

                if records:
                    for record in records:
                        report += f"Condition: {record[0] or 'Not specified'}\n"
                        report += f"ICD Code: {record[1] or 'N/A'}\n"
                        report += f"Severity: {record[2] or 'Not specified'}\n"
                        report += f"Diagnosed Date: {record[3] or 'Not specified'}\n"
                        report += f"Status: {record[4] or 'Active'}\n"
                        report += f"Provider: {record[5] or 'Not specified'}\n"
                        if record[6]:
                            report += f"Notes: {record[6]}\n"
                        report += "-" * 40 + "\n"
                else:
                    report += "No medical history found.\n"

                return report
        except Exception as e:
            return f"Error generating medical history: {str(e)}"

    def _report_student(self):
        """The student number the report is for (set by
        :meth:`generate_selected_report`; a student's own otherwise)."""
        sid = getattr(self, '_report_sid', None) or access_ui.own_student_id(self.auth)
        if not sid:
            raise PermissionError("No student selected for the report")
        return sid

    def send_report_to_admin(self):
        """Send the generated health report to admin via email"""
        try:
            report_text = self.report_text.get("1.0", tk.END).strip()

            if not report_text or report_text == "":
                messagebox.showwarning(_t('gui.pastoral.health.health_portal.reports.student_reports.dialogs.no_report', default="No Report"), _t('gui.pastoral.health.health_portal.reports.student_reports.dialogs.please_generate_a_report_first_before_sending_to_admin', default="Please generate a report first before sending to admin."))
                return

            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT email FROM users WHERE role = 'admin' AND email IS NOT NULL AND email != ''")
            admin_emails = [row[0] for row in cursor.fetchall()]
            conn.close()

            if not admin_emails:
                messagebox.showerror(_t('gui.pastoral.health.health_portal.reports.student_reports.dialogs.error', default="Error"), _t('gui.pastoral.health.health_portal.reports.student_reports.dialogs.no_admin_email_addresses_found_in_the_system', default="No admin email addresses found in the system."))
                return

            report_type_map = {
                'immunization': 'Immunization Status',
                'health_summary': 'Health Summary',
                'appointment_history': 'Appointment History',
                'medical_history': 'Medical History'
            }
            report_type_name = report_type_map.get(self.report_type.get(), 'Health Report')

            user_name = f"{self.auth.current_user.get('first_name', '')} {self.auth.current_user.get('last_name', '')}".strip()
            if not user_name:
                user_name = self.auth.current_user.get('username', 'Unknown User')

            try:
                from education_system.systems.university.infrastructure.email.template_utils import render_template
                subject, message = render_template("health_portal_report", {
                    "report_type": report_type_name,
                    "user_name": user_name,
                    "user_id": getattr(self, '_report_sid', None) or 'N/A',
                    "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "report_content": html.escape(report_text)
                })
                if not subject or not message:
                    raise ValueError("template render returned no content")
            except Exception:
                subject = f"Health Portal - {report_type_name} - {user_name}"
                message = f"""Health Portal Report

Report Type: {report_type_name}
Student: {user_name} (ID: {getattr(self, '_report_sid', None) or 'N/A'})
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'=' * 60}

{report_text}

{'=' * 60}

This report was automatically generated and sent from the Health Portal system.
"""

            from education_system.systems.university.infrastructure.email.email_service import send_email

            success_count = 0
            for admin_email in admin_emails:
                try:
                    result = send_email(
                        recipient_email=admin_email,
                        subject=subject,
                        body=message
                    )
                    if result:
                        success_count += 1
                except Exception as e:
                    print(f"Failed to send to {admin_email}: {e}")

            if success_count > 0:
                messagebox.showinfo(_t('gui.pastoral.health.health_portal.reports.student_reports.dialogs.success', default="Success"),
                    f"Report sent successfully to {success_count} admin(s).\n\n"
                    f"Recipients: {', '.join(admin_emails[:3])}"
                    + (f" and {len(admin_emails) - 3} more" if len(admin_emails) > 3 else ""))
                self.log_audit_event('send_report_to_admin', 'health_report', f"{report_type_name} sent to admins")
            else:
                messagebox.showerror(_t('gui.pastoral.health.health_portal.reports.student_reports.dialogs.error', default="Error"), _t('gui.pastoral.health.health_portal.reports.student_reports.dialogs.failed_to_send_report_to_any_admin', default="Failed to send report to any admin."))

        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.health.health_portal.reports.student_reports.dialogs.error', default="Error"), f"Failed to send report to admin: {str(e)}")
            print(f"Error in send_report_to_admin: {e}")
            import traceback
            traceback.print_exc()
