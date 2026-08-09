import csv
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.domains.pastoral.domain.health.dentist.services.dentist_core import PatientManager, AppointmentManager, TreatmentManager, PrescriptionManager, TransactionManager, ReportManager, init_dentist_db, TREATMENT_TYPES, DENTIST_STAFF, APPOINTMENT_SLOTS
from education_system.systems.university.domains.pastoral.interfaces.gui.health.health_portal.dentist import EMAIL_AVAILABLE, send_email, render_template, _send_dentist_email

class PrescriptionServiceMixin:
        def view_prescriptions(self):
            """Function 14: View prescriptions."""
            if not self.patient:
                messagebox.showwarning(_t("dentist.window_title"), _t("dentist.errors.not_registered"))
                return
            prescriptions = PrescriptionManager.get_patient_prescriptions(self.patient['patient_id'])
            if not prescriptions:
                messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.no_prescriptions"))
                return
            dialog = tk.Toplevel(self.root)
            dialog.title(_t("dentist.prescriptions"))
            dialog.geometry("600x400")
            text = tk.Text(dialog, wrap=tk.WORD)
            text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            for p in prescriptions:
                text.insert(tk.END, f"\n=== {p['prescribed_date']} ===\n")
                text.insert(tk.END, f"Medication: {p['medication']}\nDosage: {p['dosage']}\nFrequency: {p['frequency']}\nDuration: {p['duration']}\nInstructions: {p.get('instructions', 'N/A')}\n")

        def create_prescription(self):
            """Function 22: Create a prescription (staff)."""
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
            medication = simpledialog.askstring(_t("dentist.window_title"), _t("dentist.prompts.medication"))
            dosage = simpledialog.askstring(_t("dentist.window_title"), _t("dentist.prompts.dosage"))
            frequency = simpledialog.askstring(_t("dentist.window_title"), _t("dentist.prompts.frequency"))
            duration = simpledialog.askstring(_t("dentist.window_title"), _t("dentist.prompts.duration"))
            if all([medication, dosage, frequency, duration]):
                result = PrescriptionManager.create_prescription(patient_id=patient['patient_id'], dentist_id='STAFF', dentist_name=self.user_id, medication=medication, dosage=dosage, frequency=frequency, duration=duration)
                if result:
                    messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.prescription_created"))

