import csv
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.domains.pastoral.domain.health.dentist.services.dentist_core import PatientManager, AppointmentManager, TreatmentManager, PrescriptionManager, TransactionManager, ReportManager, init_dentist_db, TREATMENT_TYPES, DENTIST_STAFF, APPOINTMENT_SLOTS
from education_system.systems.university.domains.pastoral.interfaces.gui.health.health_portal.dentist import EMAIL_AVAILABLE, send_email, render_template, _send_dentist_email

class PatientServiceMixin:
        def _init_database(self):
            """Function 3: Initialize database tables."""
            try:
                if not init_dentist_db():
                    messagebox.showwarning(_t("dentist.window_title"), _t("dentist.warnings.db_init"))
            except Exception as e:
                messagebox.showwarning(_t("dentist.window_title"), f"DB init error: {e}")

        def _load_patient(self):
            self.patient = PatientManager.get_patient(user_id=self.user_id)

        def register_patient(self):
            """Function 7: Register as a patient."""
            if self.patient:
                messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.already_registered"))
                return
            dialog = tk.Toplevel(self.root)
            dialog.title(_t("dentist.btn.register"))
            dialog.geometry("400x350")
            dialog.transient(self.root)
            dialog.grab_set()
            frame = ttk.Frame(dialog, padding="20")
            frame.pack(fill=tk.BOTH, expand=True)
            ttk.Label(frame, text=_t("dentist.labels.phone") + ":").grid(row=0, column=0, sticky=tk.W, pady=2)
            phone_var = tk.StringVar()
            ttk.Entry(frame, textvariable=phone_var, width=30).grid(row=0, column=1, pady=2)
            ttk.Label(frame, text=_t("dentist.labels.dob") + " (YYYY-MM-DD):").grid(row=1, column=0, sticky=tk.W, pady=2)
            dob_var = tk.StringVar()
            ttk.Entry(frame, textvariable=dob_var, width=30).grid(row=1, column=1, pady=2)
            ttk.Label(frame, text=_t("dentist.labels.emergency_contact") + ":").grid(row=2, column=0, sticky=tk.W, pady=2)
            emergency_var = tk.StringVar()
            ttk.Entry(frame, textvariable=emergency_var, width=30).grid(row=2, column=1, pady=2)
            ttk.Label(frame, text=_t("dentist.labels.allergies") + ":").grid(row=3, column=0, sticky=tk.W, pady=2)
            allergies_var = tk.StringVar()
            ttk.Entry(frame, textvariable=allergies_var, width=30).grid(row=3, column=1, pady=2)
            def save():
                result = PatientManager.register_patient(user_id=self.user_id, user_name=self.user_id, user_email=self.user_email, user_phone=phone_var.get(), date_of_birth=dob_var.get(), emergency_contact=emergency_var.get(), allergies=allergies_var.get())
                if result:
                    messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.registered").format(patient_number=result['patient_number']))
                    self._load_patient()
                    self._refresh_patient_info()
                    dialog.destroy()
                else:
                    messagebox.showerror(_t("dentist.window_title"), _t("dentist.errors.registration_failed"))
            ttk.Button(frame, text=_t("common.save"), command=save).grid(row=4, column=1, pady=20)

        def update_patient_profile(self):
            """Function 16: Update patient profile."""
            if not self.patient:
                messagebox.showwarning(_t("dentist.window_title"), _t("dentist.errors.not_registered"))
                return
            phone = simpledialog.askstring(_t("dentist.window_title"), _t("dentist.prompts.new_phone"), initialvalue=self.patient.get('user_phone', ''))
            if phone:
                PatientManager.update_patient(self.patient['patient_id'], user_phone=phone)
                self._load_patient()
                self._refresh_profile()
                messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.profile_updated"))

        def search_patients(self):
            """Function 19: Search patients."""
            search_term = simpledialog.askstring(_t("dentist.window_title"), _t("dentist.prompts.search_patient"))
            if not search_term:
                return
            patients = PatientManager.search_patients(search_term)
            if not patients:
                messagebox.showinfo(_t("dentist.window_title"), _t("dentist.messages.no_patients_found"))
                return
            dialog = tk.Toplevel(self.root)
            dialog.title(_t("dentist.search_results"))
            dialog.geometry("600x400")
            columns = ('number', 'name', 'email', 'last_visit')
            tree = ttk.Treeview(dialog, columns=columns, show='headings')
            for col in columns:
                tree.heading(col, text=col.replace('_', ' ').title())
            for p in patients:
                tree.insert('', tk.END, values=(p['patient_number'], p['user_name'], p.get('user_email', ''), p.get('last_visit', 'Never')))
            tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

