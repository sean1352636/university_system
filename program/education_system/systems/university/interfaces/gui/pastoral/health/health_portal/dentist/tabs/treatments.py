
from education_system.systems.university.infrastructure.i18n import get_text as _t
from .. import *  # shared compatibility dependencies

class TreatmentsTabMixin:
        def create_treatments_tab(self):
            """Function 11: Create treatments tab."""
            tab = ttk.Frame(self.notebook, padding="10")
            self.notebook.add(tab, text=_t("dentist.tabs.treatments"))

            # Filter frame
            filter_frame = ttk.LabelFrame(tab, text=_t("dentist.btn.filter_treatments"), padding="5")
            filter_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(filter_frame, text=_t("dentist.labels.treatment_type_colon")).grid(row=0, column=0, sticky=tk.W, padx=5)
            self.treatment_filter_var = tk.StringVar(value=_t('gui.pastoral.health.health_portal.dentist.tabs.treatments.values.all', default="All"))
            treatment_types = ["All"] + [t['name'] for t in TREATMENT_TYPES.values()]
            ttk.Combobox(filter_frame, textvariable=self.treatment_filter_var, values=treatment_types, width=25).grid(row=0, column=1, padx=5)

            ttk.Label(filter_frame, text=_t("dentist.labels.payment_status")).grid(row=0, column=2, sticky=tk.W, padx=5)
            self.payment_filter_var = tk.StringVar(value=_t('gui.pastoral.health.health_portal.dentist.tabs.treatments.values.all', default="All"))
            ttk.Combobox(filter_frame, textvariable=self.payment_filter_var, values=["All", "paid", "pending"], width=15).grid(row=0, column=3, padx=5)

            ttk.Button(filter_frame, text=_t("dentist.btn.apply_filter"), command=self._refresh_treatments_list).grid(row=0, column=4, padx=5)
            ttk.Button(filter_frame, text=_t("dentist.btn.clear"), command=self._clear_treatment_filters).grid(row=0, column=5, padx=5)

            # Treatment history
            history_frame = ttk.LabelFrame(tab, text=_t("dentist.treatment_history"), padding="5")
            history_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            columns = ('id', 'date', 'treatment', 'dentist', 'fee', 'status', 'follow_up')
            self.treatments_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=10)
            self.treatments_tree.heading('id', text=_t('dentist.columns.id'))
            self.treatments_tree.heading('date', text=_t('dentist.columns.date'))
            self.treatments_tree.heading('treatment', text=_t('dentist.columns.treatment'))
            self.treatments_tree.heading('dentist', text=_t('dentist.columns.dentist'))
            self.treatments_tree.heading('fee', text=_t('dentist.columns.fee_gbp'))
            self.treatments_tree.heading('status', text=_t('dentist.columns.payment_status'))
            self.treatments_tree.heading('follow_up', text=_t('dentist.columns.follow_up'))

            self.treatments_tree.column('id', width=50)
            self.treatments_tree.column('date', width=100)
            self.treatments_tree.column('treatment', width=150)
            self.treatments_tree.column('dentist', width=120)
            self.treatments_tree.column('fee', width=80)
            self.treatments_tree.column('status', width=100)
            self.treatments_tree.column('follow_up', width=120)

            scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.treatments_tree.yview)
            self.treatments_tree.configure(yscrollcommand=scrollbar.set)
            self.treatments_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Double-click to view details
            self.treatments_tree.bind('<Double-1>', lambda e: self.view_treatment_details_advanced())

            # Actions
            action_frame = ttk.Frame(tab)
            action_frame.pack(fill=tk.X)
            ttk.Button(action_frame, text=_t("dentist.btn.view_full_details"), command=self.view_treatment_details_advanced).pack(side=tk.LEFT, padx=5)
            ttk.Button(action_frame, text=_t("dentist.btn.pay"), command=self.process_treatment_payment).pack(side=tk.LEFT, padx=5)
            ttk.Button(action_frame, text=_t("dentist.btn.request_treatment"), command=self.request_treatment_dialog).pack(side=tk.LEFT, padx=5)
            ttk.Button(action_frame, text=_t("dentist.btn.schedule_follow_up"), command=self.schedule_followup_from_treatment).pack(side=tk.LEFT, padx=5)
            ttk.Button(action_frame, text=_t("dentist.btn.export_csv"), command=self.export_treatments_csv).pack(side=tk.LEFT, padx=5)
            ttk.Button(action_frame, text=_t("dentist.btn.view_prescriptions"), command=self.view_prescriptions).pack(side=tk.LEFT, padx=5)
            self._refresh_treatments_list()

        def _refresh_treatments_list(self):
            """Refresh treatments list with filtering."""
            for item in self.treatments_tree.get_children():
                self.treatments_tree.delete(item)
            if not self.patient:
                return

            treatments = TreatmentManager.get_patient_treatments(self.patient['patient_id'])

            if not treatments:
                # Show helpful message when no treatments
                self.treatments_tree.insert('', tk.END, values=(
                    'N/A',
                    '',
                    'No treatment history yet',
                    'Treatments are recorded after appointments are completed',
                    '',
                    '',
                    'Check Appointments tab'
                ))
                return

            # Apply filters
            treatment_filter = self.treatment_filter_var.get()
            payment_filter = self.payment_filter_var.get()

            filtered_count = 0
            for t in treatments:
                # Get display name for treatment type
                treatment_key = t['treatment_type']
                treatment_display = TREATMENT_TYPES.get(treatment_key, {}).get('name', treatment_key)

                # Filter by treatment type (compare display names)
                if treatment_filter != "All" and treatment_display != treatment_filter:
                    continue

                # Filter by payment status
                if payment_filter != "All" and t['payment_status'] != payment_filter:
                    continue

                filtered_count += 1

                # Determine follow-up status
                follow_up = "Required" if t.get('follow_up_required') else "None"
                if t.get('follow_up_date'):
                    follow_up = f"Due: {t['follow_up_date']}"

                self.treatments_tree.insert('', tk.END, values=(
                    t.get('treatment_id', 'N/A'),
                    t['treatment_date'],
                    treatment_display,  # Show display name instead of key
                    t['dentist_name'],
                    f"{t['fee']:.2f}",
                    t['payment_status'],
                    follow_up
                ))

            # Show message if filters resulted in no results
            if filtered_count == 0 and (treatment_filter != "All" or payment_filter != "All"):
                self.treatments_tree.insert('', tk.END, values=(
                    'N/A',
                    '',
                    'No treatments match current filters',
                    'Try clearing filters or selecting different options',
                    '',
                    '',
                    ''
                ))
