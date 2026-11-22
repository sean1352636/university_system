from .. import *  # shared compatibility dependencies

class AppointmentsTabMixin:
        def create_appointments_tab(self):
            """Function 6: Create appointments tab."""
            tab = ttk.Frame(self.notebook, padding="10")
            self.notebook.add(tab, text=_t("dentist.tabs.appointments"))
            # Patient info
            patient_frame = ttk.LabelFrame(tab, text=_t("dentist.patient_info"), padding="10")
            patient_frame.pack(fill=tk.X, pady=(0, 10))
            self.patient_info_label = ttk.Label(patient_frame, text="")
            self.patient_info_label.pack(side=tk.LEFT)
            ttk.Button(patient_frame, text=_t("dentist.btn.register"), command=self.register_patient).pack(side=tk.RIGHT)
            # Booking frame
            booking_frame = ttk.LabelFrame(tab, text=_t("dentist.book_appointment"), padding="10")
            booking_frame.pack(fill=tk.X, pady=(0, 10))
            ttk.Label(booking_frame, text=_t("dentist.labels.dentist") + ":").grid(row=0, column=0, sticky=tk.W, pady=2)
            self.dentist_var = tk.StringVar()
            dentist_names = [d['name'] for d in DENTIST_STAFF]
            ttk.Combobox(booking_frame, textvariable=self.dentist_var, values=dentist_names, width=30).grid(row=0, column=1, pady=2)
            if not dentist_names:
                ttk.Label(booking_frame, text="No dentists are set up yet: a dentist is a staff account with the 'dentist' role. Ask an administrator to add one.", foreground="#a33", wraplength=380).grid(
                    row=0, column=2, sticky=tk.W, padx=(8, 0))
            ttk.Label(booking_frame, text=_t("dentist.labels.date") + ":").grid(row=1, column=0, sticky=tk.W, pady=2)
            self.appt_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
            ttk.Entry(booking_frame, textvariable=self.appt_date_var, width=33).grid(row=1, column=1, pady=2)
            ttk.Label(booking_frame, text=_t("dentist.labels.time") + ":").grid(row=2, column=0, sticky=tk.W, pady=2)
            self.appt_time_var = tk.StringVar()
            ttk.Combobox(booking_frame, textvariable=self.appt_time_var, values=APPOINTMENT_SLOTS, width=30).grid(row=2, column=1, pady=2)
            ttk.Label(booking_frame, text=_t("dentist.labels.treatment_type") + ":").grid(row=3, column=0, sticky=tk.W, pady=2)
            self.treatment_type_var = tk.StringVar()
            treatment_names = [t['name'] for t in TREATMENT_TYPES.values()]
            ttk.Combobox(booking_frame, textvariable=self.treatment_type_var, values=treatment_names, width=30).grid(row=3, column=1, pady=2)
            ttk.Button(booking_frame, text=_t("dentist.btn.book"), command=self.book_appointment).grid(row=4, column=1, pady=10)
            # Appointments list
            list_frame = ttk.LabelFrame(tab, text=_t("dentist.my_appointments"), padding="5")
            list_frame.pack(fill=tk.BOTH, expand=True)
            columns = ('ref', 'date', 'time', 'dentist', 'treatment', 'status')
            self.appointments_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=8)
            for col in columns:
                self.appointments_tree.heading(col, text=col.title())
                self.appointments_tree.column(col, width=90)
            self.appointments_tree.pack(fill=tk.BOTH, expand=True)
            action_frame = ttk.Frame(list_frame)
            action_frame.pack(fill=tk.X, pady=(5, 0))
            ttk.Button(action_frame, text=_t("dentist.btn.cancel"), command=self.cancel_appointment).pack(side=tk.LEFT, padx=2)
            ttk.Button(action_frame, text=_t("dentist.btn.reschedule"), command=self.reschedule_appointment).pack(side=tk.LEFT, padx=2)
            self._refresh_patient_info()
            self._refresh_appointments_list()

        def _refresh_appointments_list(self):
            for item in self.appointments_tree.get_children():
                self.appointments_tree.delete(item)
            if self.patient:
                for a in AppointmentManager.get_patient_appointments(self.patient['patient_id']):
                    self.appointments_tree.insert('', tk.END, values=(a['appointment_ref'], a['appointment_date'], a['appointment_time'], a['dentist_name'], a['treatment_type'], a['status']))

        def _refresh_today(self):
            for item in self.today_tree.get_children():
                self.today_tree.delete(item)
            for a in AppointmentManager.get_todays_appointments():
                self.today_tree.insert('', tk.END, values=(a['appointment_time'], a.get('patient_name', 'N/A'), a['dentist_name'], a['treatment_type'], a['status']))
