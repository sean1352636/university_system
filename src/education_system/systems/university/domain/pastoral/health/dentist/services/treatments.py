import csv
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.domain.pastoral.health.dentist.services.dentist_core import PatientManager, AppointmentManager, TreatmentManager, PrescriptionManager, TransactionManager, ReportManager, init_dentist_db, TREATMENT_TYPES, DENTIST_STAFF, APPOINTMENT_SLOTS
from education_system.systems.university.interfaces.gui.pastoral.health.health_portal.dentist import EMAIL_AVAILABLE, send_email, render_template, _send_dentist_email

class TreatmentServiceMixin:
        def view_treatment_details(self):
            """Function 12: View treatment details (simple)."""
            selected = self.treatments_tree.selection()
            if not selected:
                messagebox.showwarning(_t("dentist.window_title"), _t("dentist.errors.select_treatment"))
                return
            values = self.treatments_tree.item(selected[0])['values']
            details = f"Treatment ID: {values[0]}\nDate: {values[1]}\nTreatment: {values[2]}\nDentist: {values[3]}\nFee: GBP {values[4]}\nPayment Status: {values[5]}\nFollow-up: {values[6]}"
            messagebox.showinfo(_t("dentist.treatment_details"), details)

        def view_treatment_details_advanced(self):
            """View detailed treatment information with notes and prescriptions."""
            selected = self.treatments_tree.selection()
            if not selected:
                messagebox.showwarning(_t("dentist.window_title"), _t("dentist.errors.select_treatment"))
                return

            try:
                values = self.treatments_tree.item(selected[0])['values']
                treatment_id = values[0]

                # Fetch full treatment details from database
                from education_system.systems.university.infrastructure.database.db import get_connection
                with get_connection() as conn:
                    cursor = conn.execute('''
                        SELECT * FROM dentist_treatments WHERE treatment_id = ?
                    ''', (treatment_id,))
                    treatment = cursor.fetchone()

                    if not treatment:
                        messagebox.showerror(_t("dentist.msg_titles.error"), "Treatment details not found")
                        return

                # Create details dialog
                dialog = tk.Toplevel(self.root)
                dialog.title(_t("dentist.labels.treatment_details"))
                dialog.geometry("600x500")
                dialog.transient(self.root)

                main_frame = ttk.Frame(dialog, padding="20")
                main_frame.pack(fill=tk.BOTH, expand=True)

                ttk.Label(main_frame, text=_t("dentist.labels.treatment_details"), font=('Arial', 14, 'bold')).pack(pady=(0, 15))

                # Details frame
                details_frame = ttk.LabelFrame(main_frame, text=_t("dentist.labels.treatment_information"), padding="10")
                details_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

                details_text = tk.Text(details_frame, height=20, wrap=tk.WORD, font=('Arial', 10))
                details_text.pack(fill=tk.BOTH, expand=True)

                # Format treatment details
                info = f"""Treatment ID: {treatment['treatment_id']}
    Date: {treatment['treatment_date']}
    Treatment Type: {treatment['treatment_type']}
    Dentist: {treatment['dentist_name']}
    Fee: GBP {treatment['fee']:.2f}
    Payment Status: {treatment['payment_status']}

    {'='*50}
    TREATMENT DETAILS
    {'='*50}
    Tooth Number: {treatment['tooth_number'] if treatment['tooth_number'] else 'N/A'}
    Description: {treatment['description'] if treatment['description'] else 'No description provided'}

    Notes: {treatment['notes'] if treatment['notes'] else 'No notes recorded'}

    {'='*50}
    FOLLOW-UP INFORMATION
    {'='*50}
    Follow-up Required: {'Yes' if treatment['follow_up_required'] else 'No'}
    Follow-up Date: {treatment['follow_up_date'] if treatment['follow_up_date'] else 'Not scheduled'}
    """
                details_text.insert('1.0', info)
                details_text.config(state='disabled')

                # Buttons frame
                btn_frame = ttk.Frame(main_frame)
                btn_frame.pack(fill=tk.X, pady=(10, 0))

                ttk.Button(btn_frame, text=_t("dentist.btn.close"), command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

                if treatment['follow_up_required'] and not treatment['follow_up_date']:
                    ttk.Button(btn_frame, text=_t("dentist.btn.schedule_follow_up"),
                              command=lambda: [dialog.destroy(), self.schedule_followup_from_treatment()]).pack(side=tk.LEFT, padx=5)

            except Exception as e:
                messagebox.showerror(_t("dentist.msg_titles.error"), f"Failed to load treatment details: {e}")

        def request_treatment_dialog(self):
            """Request a new treatment/appointment."""
            if not self.patient:
                messagebox.showwarning(_t("dentist.window_title"), _t("dentist.errors.not_registered"))
                return

            dialog = tk.Toplevel(self.root)
            dialog.title(_t("dentist.msg_titles.treatment_request"))
            dialog.geometry("450x400")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text=_t("dentist.btn.request_treatment_appt"), font=('Arial', 12, 'bold')).pack(pady=(0, 15))

            # Treatment type
            ttk.Label(main_frame, text=_t("dentist.labels.treatment_type_colon")).pack(anchor=tk.W, pady=(5, 0))
            treatment_var = tk.StringVar()
            treatment_names = [t['name'] for t in TREATMENT_TYPES.values()]
            treatment_combo = ttk.Combobox(main_frame, textvariable=treatment_var, values=treatment_names, width=40)
            treatment_combo.pack(fill=tk.X, pady=(0, 10))

            # Preferred date
            ttk.Label(main_frame, text=_t("dentist.labels.preferred_date")).pack(anchor=tk.W, pady=(5, 0))
            date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
            ttk.Entry(main_frame, textvariable=date_var, width=43).pack(fill=tk.X, pady=(0, 10))

            # Dentist preference
            ttk.Label(main_frame, text=_t("dentist.labels.preferred_dentist")).pack(anchor=tk.W, pady=(5, 0))
            dentist_var = tk.StringVar()
            dentist_names = ["Any"] + [d['name'] for d in DENTIST_STAFF]
            ttk.Combobox(main_frame, textvariable=dentist_var, values=dentist_names, width=40).pack(fill=tk.X, pady=(0, 10))

            # Notes
            ttk.Label(main_frame, text=_t("dentist.labels.additional_notes")).pack(anchor=tk.W, pady=(5, 0))
            notes_text = tk.Text(main_frame, height=5, wrap=tk.WORD)
            notes_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

            def submit_request():
                if not treatment_var.get():
                    messagebox.showerror(_t("dentist.msg_titles.error"), "Please select a treatment type")
                    return

                # For now, redirect to appointment booking
                messagebox.showinfo(_t("dentist.msg_titles.treatment_request"),
                                  f"Treatment request noted:\n\n"
                                  f"Type: {treatment_var.get()}\n"
                                  f"Preferred Date: {date_var.get()}\n"
                                  f"Preferred Dentist: {dentist_var.get() or 'Any'}\n\n"
                                  f"Please proceed to the Appointments tab to book your appointment.")
                dialog.destroy()

                # Switch to appointments tab
                self.notebook.select(0)  # Assuming appointments is first tab

            btn_frame = ttk.Frame(main_frame)
            btn_frame.pack(fill=tk.X)

            ttk.Button(btn_frame, text=_t("dentist.btn.submit_request"), command=submit_request).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text=_t("dentist.btn.cancel"), command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        def schedule_followup_from_treatment(self):
            """Schedule a follow-up appointment from a treatment."""
            selected = self.treatments_tree.selection()
            if not selected:
                messagebox.showwarning(_t("dentist.window_title"), "Please select a treatment that requires follow-up")
                return

            try:
                values = self.treatments_tree.item(selected[0])['values']
                treatment_id = values[0]
                treatment_type = values[2]

                # Check if follow-up is required
                from education_system.systems.university.infrastructure.database.db import get_connection
                with get_connection() as conn:
                    cursor = conn.execute('''
                        SELECT follow_up_required, follow_up_date FROM dentist_treatments
                        WHERE treatment_id = ?
                    ''', (treatment_id,))
                    result = cursor.fetchone()

                    if not result or not result['follow_up_required']:
                        messagebox.showinfo(_t("dentist.msg_titles.follow_up"), "This treatment does not require a follow-up appointment")
                        return

                    if result['follow_up_date']:
                        messagebox.showinfo(_t("dentist.msg_titles.follow_up"), f"Follow-up already scheduled for: {result['follow_up_date']}")
                        return

                # Show scheduling dialog
                messagebox.showinfo(_t("dentist.msg_titles.schedule_follow_up"),
                                  f"Follow-up required for: {treatment_type}\n\n"
                                  f"Please use the Appointments tab to schedule your follow-up appointment.")

                # Switch to appointments tab
                self.notebook.select(0)

            except Exception as e:
                messagebox.showerror(_t("dentist.msg_titles.error"), f"Failed to check follow-up status: {e}")

        def record_treatment(self):
            """Function 21: Record a treatment (staff)."""
            if self.user_role not in ('admin', 'staff'):
                messagebox.showerror(_t("dentist.window_title"), _t("dentist.errors.permission_denied"))
                return
            patient_number = simpledialog.askstring(_t("dentist.window_title"), _t("dentist.prompts.patient_number"))
            if not patient_number:
                return
            patient = PatientManager.get_patient(patient_number=patient_number)
            if not patient:
                messagebox.showerror(_t("dentist.window_title"), _t("dentist.errors.patient_not_found"))
                return
            treatment_type = simpledialog.askstring(_t("dentist.window_title"), _t("dentist.prompts.treatment_type"))
            if not treatment_type or treatment_type not in TREATMENT_TYPES:
                messagebox.showerror(_t("dentist.window_title"), _t("dentist.errors.invalid_treatment"))
                return
            result = TreatmentManager.record_treatment(patient_id=patient['patient_id'], dentist_id='STAFF', dentist_name=self.user_id, treatment_type=treatment_type, treatment_date=datetime.now().strftime('%Y-%m-%d'))
            if result:
                messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.treatment_recorded"))

        def process_treatment_payment(self):
            """Function 13: Process payment for a treatment."""
            selected = self.treatments_tree.selection()
            if not selected:
                messagebox.showwarning(_t("dentist.window_title"), _t("dentist.errors.select_treatment"))
                return
            values = self.treatments_tree.item(selected[0])['values']
            # Updated: values are now (id, date, treatment_display_name, dentist, fee, status, follow_up)
            if values[5] == 'paid':
                messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.already_paid"))
                return
            try:
                amount = float(values[4])
            except (ValueError, TypeError):
                amount = 0
            treatment_id = values[0]

            if messagebox.askyesno(_t("dentist.window_title"), f"Process payment of GBP {amount:.2f}?"):
                # Process the payment
                result = self.process_payment('treatment', amount, f"Dental treatment - {values[2]}")

                if result:
                    # Update treatment payment status in database
                    try:
                        from education_system.systems.university.infrastructure.database.db import transaction as db_transaction
                        with db_transaction() as conn:
                            conn.execute('''
                                UPDATE dentist_treatments
                                SET payment_status = 'paid'
                                WHERE treatment_id = ?
                            ''', (treatment_id,))
                    except Exception as e:
                        print(f"Error updating treatment payment status: {e}")

                    messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.payment_processed"))
                    self._refresh_treatments_list()

