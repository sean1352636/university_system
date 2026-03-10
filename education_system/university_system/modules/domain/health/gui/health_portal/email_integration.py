import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime

from education_system.university_system.modules.shared.utils.i18n import get_text as _t


class EmailIntegrationMixin:
    """Mixin for all email-related methods."""

    # ==================== INTEGRATION SERVICE INTERFACES ====================

    def create_email_manager(self):
        """Create email manager interface"""
        title = ttk.Label(self.content_frame, text=_t("health_portal.labels.email_manager"),
                         style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)

        launch_frame = ttk.Frame(self.content_frame)
        launch_frame.grid(row=1, column=0, pady=20)

        ttk.Button(launch_frame, text=_t("health_portal.buttons.open_email_manager"),
                  command=self.open_email_manager_gui).pack(pady=10)

        info_text = """The Email Manager allows you to:
\u2022 Send appointment confirmations and cancellations
\u2022 Email health reports to patients
\u2022 Send health record notifications
\u2022 Manage emergency contact communications

Click the button above to open the full Email Manager interface."""

        info_label = ttk.Label(self.content_frame, text=info_text, justify=tk.LEFT)
        info_label.grid(row=2, column=0, pady=10, padx=20)

    def create_send_health_report_email(self):
        """Create interface for sending health report emails"""
        title = ttk.Label(self.content_frame, text=_t("health_portal.labels.send_report_title"),
                         style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)

        form_frame = ttk.LabelFrame(self.content_frame, text=_t("health_portal.labels.email_health_report"), padding="10")
        form_frame.grid(row=1, column=0, pady=10, padx=20, sticky=(tk.W, tk.E))

        ttk.Label(form_frame, text=_t("health_portal.labels.student_id")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.email_student_id = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.email_student_id, width=20).grid(row=0, column=1, pady=5, padx=10)

        ttk.Label(form_frame, text=_t("health_portal.labels.report_title")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.email_report_title = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.email_report_title, width=40).grid(row=1, column=1, pady=5, padx=10)

        ttk.Label(form_frame, text=_t("health_portal.labels.report_type")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.email_report_type = tk.StringVar()
        ttk.Combobox(form_frame, textvariable=self.email_report_type,
                    values=["Blood Test Results", "Physical Exam", "Vaccination Record", "Medical Clearance"]).grid(row=2, column=1, pady=5, padx=10)

        ttk.Label(form_frame, text=_t("health_portal.labels.report_summary")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.email_report_summary = scrolledtext.ScrolledText(form_frame, height=4, width=50)
        self.email_report_summary.grid(row=3, column=1, pady=5, padx=10)

        def send_health_report_email():
            student_id = self.email_student_id.get().strip()
            if not student_id:
                messagebox.showerror("Error", "Please enter a Student ID")
                return

            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT first_name, last_name, email_address FROM students WHERE student_id = ?", (student_id,))
                patient_info = cursor.fetchone()
                conn.close()

                if not patient_info:
                    messagebox.showerror("Error", "Student not found")
                    return

                patient_name = f"{patient_info[0]} {patient_info[1]}"
                patient_email = patient_info[2]

                report_details = {
                    'title': self.email_report_title.get(),
                    'type': self.email_report_type.get(),
                    'summary': self.email_report_summary.get('1.0', tk.END).strip(),
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'practitioner': self.auth.current_user.get('username', 'Health Center Staff')
                }

                self.send_health_report_email(patient_email, patient_name, report_details)
                messagebox.showinfo("Success", f"Health report email sent to {patient_name}")

                self.email_student_id.set("")
                self.email_report_title.set("")
                self.email_report_type.set("")
                self.email_report_summary.delete('1.0', tk.END)

            except Exception as e:
                messagebox.showerror(_t("common.error"), f"{_t('health_portal.messages.email_send_failed')}: {str(e)}")

        ttk.Button(form_frame, text=_t("health_portal.buttons.send_health_report_email"),
                  command=send_health_report_email).grid(row=4, column=0, columnspan=2, pady=20)

    def create_send_health_record_email(self):
        """Create interface for sending health record emails"""
        title = ttk.Label(self.content_frame, text=_t("health_portal.labels.send_record_email_title"),
                         style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)

        form_frame = ttk.LabelFrame(self.content_frame, text=_t("health_portal.labels.email_health_record_form"), padding="10")
        form_frame.grid(row=1, column=0, pady=10, padx=20, sticky=(tk.W, tk.E))

        ttk.Label(form_frame, text=_t("health_portal.labels.student_id")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.record_email_student_id = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.record_email_student_id, width=20).grid(row=0, column=1, pady=5, padx=10)

        ttk.Label(form_frame, text=_t("health_portal.labels.record_type")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.record_email_type = tk.StringVar()
        ttk.Combobox(form_frame, textvariable=self.record_email_type,
                    values=[_t("health_portal.record_types.complete_history"), _t("health_portal.record_types.vaccination"), _t("health_portal.record_types.visit_summary"), _t("health_portal.record_types.emergency_info")]).grid(row=1, column=1, pady=5, padx=10)

        ttk.Label(form_frame, text=_t("health_portal.labels.date_range")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.record_email_date_range = tk.StringVar(value=_t("health_portal.labels.all_dates"))
        ttk.Entry(form_frame, textvariable=self.record_email_date_range, width=30).grid(row=2, column=1, pady=5, padx=10)

        ttk.Label(form_frame, text=_t("health_portal.labels.summary")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.record_email_summary = scrolledtext.ScrolledText(form_frame, height=4, width=50)
        self.record_email_summary.grid(row=3, column=1, pady=5, padx=10)

        def send_health_record_email():
            student_id = self.record_email_student_id.get().strip()
            if not student_id:
                messagebox.showerror(_t("common.error"), _t("health_portal.messages.enter_student_id"))
                return

            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT first_name, last_name, email_address FROM students WHERE student_id = ?", (student_id,))
                patient_info = cursor.fetchone()
                conn.close()

                if not patient_info:
                    messagebox.showerror(_t("common.error"), _t("health_portal.messages.student_not_found"))
                    return

                patient_name = f"{patient_info[0]} {patient_info[1]}"
                patient_email = patient_info[2]

                record_details = {
                    'type': self.record_email_type.get(),
                    'date_range': self.record_email_date_range.get(),
                    'summary': self.record_email_summary.get('1.0', tk.END).strip()
                }

                self.send_health_record_email(patient_email, patient_name, record_details)
                messagebox.showinfo(_t("common.success"), _t("health_portal.messages.record_email_sent").format(name=patient_name))

                self.record_email_student_id.set("")
                self.record_email_type.set("")
                self.record_email_date_range.set(_t("health_portal.labels.all_dates"))
                self.record_email_summary.delete('1.0', tk.END)

            except Exception as e:
                messagebox.showerror(_t("common.error"), f"{_t('health_portal.messages.email_send_failed')}: {str(e)}")

        ttk.Button(form_frame, text=_t("health_portal.buttons.send_health_record_email"),
                  command=send_health_record_email).grid(row=4, column=0, columnspan=2, pady=20)

    # ==================== EMAIL CORE METHODS ====================

    def _send_email_via_gui(self, to_email, subject, message):
        """Send email via email service"""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_email
            result = send_email(
                recipient_email=to_email,
                subject=subject,
                body=message
            )
            return result
        except ImportError:
            return False
        except Exception as e:
            print(f"Error sending email via service: {e}")
            return False

    def _show_email_fallback_dialog(self, to_email, subject, message):
        """Show email dialog as fallback when email system unavailable"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Health Portal Email Notification")
        dialog.geometry("600x500")
        dialog.configure(bg='white')
        dialog.grab_set()

        tk.Label(dialog, text="\U0001f3e5 Health Portal Email Notification", font=('Arial', 14, 'bold'),
                bg='white', fg='#2c3e50').pack(pady=10)

        info_frame = tk.Frame(dialog, bg='white')
        info_frame.pack(fill='x', padx=20, pady=10)

        tk.Label(info_frame, text=f"To: {to_email}", font=('Arial', 11),
                bg='white', fg='#34495e').pack(anchor='w')
        tk.Label(info_frame, text=f"Subject: {subject}", font=('Arial', 11),
                bg='white', fg='#34495e').pack(anchor='w')

        tk.Label(dialog, text="Message:", font=('Arial', 11, 'bold'),
                bg='white', fg='#2c3e50').pack(anchor='w', padx=20, pady=(10, 5))

        message_text = tk.Text(dialog, height=15, wrap='word', font=('Arial', 10))
        message_text.pack(fill='both', expand=True, padx=20, pady=(0, 10))
        message_text.insert('1.0', message)
        message_text.config(state='disabled')

        tk.Button(dialog, text="Close", command=dialog.destroy,
                 bg='#6c757d', fg='white', font=('Arial', 10),
                 padx=20, pady=5, relief='flat').pack(pady=10)

    # ==================== APPOINTMENT EMAIL METHODS ====================

    def send_appointment_confirmation(self, patient_email, patient_name, appointment_details):
        """Send confirmation email for appointment booking"""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_template_email

            template_vars = {
                'patient_name': patient_name,
                'first_name': patient_name.split()[0] if patient_name else 'Patient',
                'last_name': ' '.join(patient_name.split()[1:]) if len(patient_name.split()) > 1 else '',
                'appointment_id': appointment_details.get('id', 'N/A'),
                'date': appointment_details.get('date', 'N/A'),
                'appointment_date': appointment_details.get('date', 'N/A'),
                'time': appointment_details.get('time', 'N/A'),
                'appointment_time': appointment_details.get('time', 'N/A'),
                'practitioner': appointment_details.get('practitioner', 'N/A'),
                'provider': appointment_details.get('practitioner', 'N/A'),
                'department': appointment_details.get('department', 'N/A'),
                'location': appointment_details.get('location', 'University Health Center'),
                'appointment_type': appointment_details.get('type', 'N/A')
            }

            send_template_email('health_appointment_confirmation', patient_email, template_vars)
        except Exception as e:
            print(f"Failed to send appointment confirmation: {e}")

    def send_appointment_cancellation(self, patient_email, patient_name, appointment_details, cancellation_reason):
        """Send confirmation email for appointment cancellation"""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_template_email

            template_vars = {
                'patient_name': patient_name,
                'date': appointment_details.get('date', 'N/A'),
                'time': appointment_details.get('time', 'N/A'),
                'practitioner': appointment_details.get('practitioner', 'N/A'),
                'department': appointment_details.get('department', 'N/A'),
                'cancellation_reason': cancellation_reason,
                'reason': cancellation_reason
            }

            send_template_email('appointment_cancellation', patient_email, template_vars)
        except Exception as e:
            print(f"Failed to send cancellation confirmation: {e}")

    def send_appointment_date_change(self, patient_email, patient_name, old_appointment, new_appointment):
        """Send confirmation email for appointment date/time changes"""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_template_email

            template_vars = {
                'patient_name': patient_name,
                'old_date': old_appointment.get('date', 'N/A'),
                'old_time': old_appointment.get('time', 'N/A'),
                'date': new_appointment.get('date', 'N/A'),
                'new_date': new_appointment.get('date', 'N/A'),
                'time': new_appointment.get('time', 'N/A'),
                'new_time': new_appointment.get('time', 'N/A'),
                'practitioner': new_appointment.get('practitioner', 'N/A'),
                'department': new_appointment.get('department', 'N/A'),
                'location': new_appointment.get('location', 'University Health Center')
            }

            send_template_email('appointment_rescheduled', patient_email, template_vars)
        except Exception as e:
            print(f"Failed to send reschedule confirmation: {e}")

    # ==================== HEALTH REPORT EMAIL METHODS ====================

    def send_health_report_email(self, patient_email, patient_name, report_details):
        """Send health report via email"""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_template_email

            template_vars = {
                "patient_name": patient_name,
                "report_title": report_details.get('title', 'Health Report'),
                "report_type": report_details.get('type', 'N/A'),
                "report_date": report_details.get('date', datetime.now().strftime('%Y-%m-%d')),
                "practitioner": report_details.get('practitioner', 'University Health Center'),
                "report_summary": report_details.get('summary', 'Please see the attached detailed report.'),
                "next_steps": report_details.get('next_steps', 'Please follow up with your healthcare provider if you have any questions about this report.')
            }

            send_template_email('health_report', patient_email, template_vars)
        except Exception as e:
            print(f"Failed to send health report email: {e}")

    def send_health_report_creation_confirmation(self, patient_email, patient_name, report_title):
        """Send confirmation email for health report creation"""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_template_email

            template_vars = {
                'patient_name': patient_name,
                'report_title': report_title
            }

            send_template_email('health_report_created', patient_email, template_vars)
        except Exception as e:
            print(f"Failed to send report creation confirmation: {e}")

    def send_health_report_update_confirmation(self, patient_email, patient_name, report_title, update_details):
        """Send confirmation email for health report updates"""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_template_email

            template_vars = {
                'patient_name': patient_name,
                'report_title': report_title,
                'update_details': update_details
            }

            send_template_email('health_report_updated', patient_email, template_vars)
        except Exception as e:
            print(f"Failed to send report update confirmation: {e}")

    def send_health_report_deletion_confirmation(self, patient_email, patient_name, report_title):
        """Send confirmation email for health report deletion"""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_template_email

            template_vars = {
                'patient_name': patient_name,
                'report_title': report_title
            }

            send_template_email('health_report_deleted', patient_email, template_vars)
        except Exception as e:
            print(f"Failed to send report deletion confirmation: {e}")

    # ==================== HEALTH RECORD EMAIL METHODS ====================

    def send_health_record_email(self, patient_email, patient_name, record_details):
        """Send health record via email"""
        try:
            from education_system.university_system.infrastructure.email.template_utils import render_template
            subject, message = render_template("health_record_email", {
                "patient_name": patient_name,
                "record_type": record_details.get('type', 'Health Record'),
                "date_range": record_details.get('date_range', 'N/A'),
                "generated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "record_summary": record_details.get('summary', 'This record contains your health information as requested.')
            })
        except Exception:
            subject = f"Health Portal - Your Health Record: {record_details.get('type', 'Health Record')}"
            message = f"""Dear {patient_name},

Your requested health record is ready for review.

RECORD DETAILS
=============
Record Type: {record_details.get('type', 'N/A')}
Date Range: {record_details.get('date_range', 'N/A')}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

RECORD CONTENTS
==============
{record_details.get('summary', 'This record contains your health information as requested.')}

IMPORTANT INFORMATION
====================
- This record contains confidential medical information
- Keep this information secure and private
- Share only with authorized healthcare providers
- Contact us if you notice any discrepancies

USING YOUR HEALTH RECORD
=======================
You can use this record to:
- Share with other healthcare providers
- Apply for medical accommodations
- Track your health history
- Support insurance claims

If you have questions about this record or need additional information, please contact us at (555) 123-4567.

Best regards,
University Health Center

PRIVACY NOTICE: This health record is protected under HIPAA regulations."""

        if not self._send_email_via_gui(patient_email, subject, message):
            self._show_email_fallback_dialog(patient_email, subject, message)

    def send_health_record_creation_confirmation(self, patient_email, patient_name, record_type):
        """Send confirmation email for health record creation"""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_template_email

            template_vars = {
                'patient_name': patient_name,
                'record_type': record_type
            }

            send_template_email('health_record_created', patient_email, template_vars)
        except Exception as e:
            print(f"Failed to send record creation confirmation: {e}")

    def send_health_record_update_confirmation(self, patient_email, patient_name, record_type, update_details):
        """Send confirmation email for health record updates"""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_template_email

            template_vars = {
                'patient_name': patient_name,
                'record_type': record_type,
                'update_details': update_details
            }

            send_template_email('health_record_updated', patient_email, template_vars)
        except Exception as e:
            print(f"Failed to send record update confirmation: {e}")

    def send_health_record_deletion_confirmation(self, patient_email, patient_name, record_type):
        """Send confirmation email for health record deletion"""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_template_email

            template_vars = {
                'patient_name': patient_name,
                'record_type': record_type
            }

            send_template_email('health_record_deleted', patient_email, template_vars)
        except Exception as e:
            print(f"Failed to send record deletion confirmation: {e}")

    # ==================== EMERGENCY CONTACT EMAIL METHODS ====================

    def send_emergency_contact_creation_confirmation(self, patient_email, patient_name, contact_name, contact_relationship):
        """Send confirmation email for emergency contact creation"""
        from education_system.university_system.infrastructure.email.template_utils import render_template

        template_vars = {
            'patient_name': patient_name,
            'contact_name': contact_name,
            'contact_relationship': contact_relationship
        }

        subject, message = render_template('emergency_contact_added', template_vars)

        if not subject or not message:
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(patient_email, subject, message):
            self._show_email_fallback_dialog(patient_email, subject, message)

    def send_emergency_contact_update_confirmation(self, patient_email, patient_name, contact_name, update_details):
        """Send confirmation email for emergency contact updates"""
        from education_system.university_system.infrastructure.email.template_utils import render_template

        template_vars = {
            'patient_name': patient_name,
            'contact_name': contact_name,
            'update_details': update_details
        }

        subject, message = render_template('emergency_contact_updated', template_vars)

        if not subject or not message:
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(patient_email, subject, message):
            self._show_email_fallback_dialog(patient_email, subject, message)

    def send_emergency_contact_deletion_confirmation(self, patient_email, patient_name, contact_name):
        """Send confirmation email for emergency contact deletion"""
        from education_system.university_system.infrastructure.email.template_utils import render_template

        template_vars = {
            'patient_name': patient_name,
            'contact_name': contact_name
        }

        subject, message = render_template('emergency_contact_removed', template_vars)

        if not subject or not message:
            print("Failed to load email template.")
            return

        if not self._send_email_via_gui(patient_email, subject, message):
            self._show_email_fallback_dialog(patient_email, subject, message)

    def open_email_manager_gui(self):
        """Open email manager GUI for health portal"""
        try:
            from education_system.university_system.modules.shared.gui.email.email_gui import EmailManagerGUI
            email_window = tk.Toplevel(self.root)
            email_window.title("Health Portal - Email Manager")
            email_window.geometry("800x600")
            email_gui = EmailManagerGUI(email_window, auth=self.auth)
        except ImportError:
            messagebox.showerror("Error", "Email Manager GUI not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error opening Email Manager: {e}")
