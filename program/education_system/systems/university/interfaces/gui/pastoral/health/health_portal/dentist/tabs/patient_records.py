from .. import *  # shared compatibility dependencies

class PatientRecordsTabMixin:
        def create_records_tab(self):
            """Function 15: Create records tab."""
            tab = ttk.Frame(self.notebook, padding="10")
            self.notebook.add(tab, text=_t("dentist.tabs.records"))
            # Patient profile
            profile_frame = ttk.LabelFrame(tab, text=_t("dentist.my_profile"), padding="10")
            profile_frame.pack(fill=tk.X, pady=(0, 10))
            self.profile_text = tk.Text(profile_frame, height=8, wrap=tk.WORD)
            self.profile_text.pack(fill=tk.X)
            # Actions
            action_frame = ttk.Frame(tab)
            action_frame.pack(fill=tk.X, pady=(0, 10))
            ttk.Button(action_frame, text=_t("dentist.btn.update_profile"), command=self.update_patient_profile).pack(side=tk.LEFT, padx=5)
            ttk.Button(action_frame, text=_t("dentist.btn.view_history"), command=self.view_dental_history).pack(side=tk.LEFT, padx=5)
            # Available treatments
            treatments_frame = ttk.LabelFrame(tab, text=_t("dentist.available_treatments"), padding="5")
            treatments_frame.pack(fill=tk.BOTH, expand=True)
            columns = ('treatment', 'duration', 'fee')
            tree = ttk.Treeview(treatments_frame, columns=columns, show='headings', height=8)
            for col in columns:
                tree.heading(col, text=col.title())
            for key, t in TREATMENT_TYPES.items():
                tree.insert('', tk.END, values=(t['name'], f"{t['duration']} min", f"GBP {t['fee']:.2f}"))
            tree.pack(fill=tk.BOTH, expand=True)
            self._refresh_profile()

        def view_dental_history(self):
            """Function 17: View complete dental history."""
            if not self.patient:
                messagebox.showwarning(_t("dentist.window_title"), _t("dentist.errors.not_registered"))
                return
            treatments = TreatmentManager.get_patient_treatments(self.patient['patient_id'])
            dialog = tk.Toplevel(self.root)
            dialog.title(_t("dentist.dental_history"))
            dialog.geometry("700x500")
            columns = ('date', 'treatment', 'dentist', 'notes')
            tree = ttk.Treeview(dialog, columns=columns, show='headings')
            for col in columns:
                tree.heading(col, text=col.title())
            for t in treatments:
                tree.insert('', tk.END, values=(t['treatment_date'], t['treatment_type'], t['dentist_name'], t.get('notes', '')))
            tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
