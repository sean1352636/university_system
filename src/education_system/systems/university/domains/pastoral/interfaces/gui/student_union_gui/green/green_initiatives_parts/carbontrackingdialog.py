"""Extracted class implementation."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import green_initiatives_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class CarbonTrackingDialog:
    """Dialog for tracking carbon footprint"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        _ensure_green_tables()

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.windows.carbon_footprint_tracking', default="Carbon Footprint Tracking"))
        self.dialog.geometry("950x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_history()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.labels.carbon_footprint_calculator', default="Carbon Footprint Calculator"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Event name
        name_frame = ttk.Frame(main_frame)
        name_frame.pack(fill='x', pady=(0, 10))
        ttk.Label(name_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.labels.event_activity_name', default="Event / Activity Name:")).pack(side='left')
        self.event_name_var = tk.StringVar()
        ttk.Entry(name_frame, textvariable=self.event_name_var, width=50).pack(side='left', padx=5)

        # Calculator notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='x', pady=(0, 10))

        # Transportation tab
        transport_frame = ttk.Frame(notebook)
        notebook.add(transport_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.tabs.transportation', default="Transportation"))
        self.create_transport_tab(transport_frame)

        # Energy tab
        energy_frame = ttk.Frame(notebook)
        notebook.add(energy_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.tabs.energy', default="Energy"))
        self.create_energy_tab(energy_frame)

        # Catering tab
        catering_frame = ttk.Frame(notebook)
        notebook.add(catering_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.tabs.catering', default="Catering"))
        self.create_catering_tab(catering_frame)

        # Results display
        results_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.labels.carbon_footprint_results', default="Carbon Footprint Results"))
        results_frame.pack(fill='x', pady=(0, 10))

        self.results_label = ttk.Label(results_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.labels.total_carbon_footprint_0_00_kg_co2', default="Total Carbon Footprint: 0.00 kg CO2"),
                                      font=('Arial', 12, 'bold'))
        self.results_label.pack(padx=10, pady=5)

        self.detail_label = ttk.Label(results_frame,
                                       text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.labels.transport_0_00_energy_0_00_catering_0_00', default="Transport: 0.00 | Energy: 0.00 | Catering: 0.00"))
        self.detail_label.pack(padx=10, pady=(0, 5))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(0, 10))

        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.buttons.calculate', default="Calculate"), command=self.calculate_footprint).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.buttons.save_to_database', default="Save to Database"), command=self.save_report).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.buttons.close', default="Close"), command=self.dialog.destroy).pack(side='right')

        # History
        hist_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.labels.saved_carbon_records', default="Saved Carbon Records"))
        hist_frame.pack(fill='both', expand=True)

        columns = ('ID', 'Event', 'Transport', 'Energy', 'Catering', 'Total', 'Per Person', 'Score', 'Date')
        self.history_tree = ttk.Treeview(hist_frame, columns=columns, show='headings', height=6)
        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=90)
        self.history_tree.column('Event', width=150)
        self.history_tree.pack(fill='both', expand=True, padx=5, pady=5)

    def create_transport_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.labels.attendee_transportation', default="Attendee Transportation")).pack(anchor='w', pady=(0, 10))

        self.transport_vars = {}
        methods = [("Walking/Cycling", 0), ("Public Transport", 0.05), ("Car", 0.21), ("Taxi/Uber", 0.25)]

        for method, rate in methods:
            row = ttk.Frame(frame)
            row.pack(fill='x', pady=5)

            ttk.Label(row, text=f"{method}:", width=20).pack(side='left')

            count_var = tk.StringVar(value="0")
            ttk.Entry(row, textvariable=count_var, width=10).pack(side='left', padx=5)
            ttk.Label(row, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.labels.attendees', default="attendees")).pack(side='left')

            self.transport_vars[method] = (count_var, rate)

    def create_energy_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.labels.energy_consumption', default="Energy Consumption")).pack(anchor='w', pady=(0, 10))

        ttk.Label(frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.labels.event_duration_hours', default="Event Duration (hours):")).pack(anchor='w')
        self.duration_var = tk.StringVar(value="2")
        ttk.Entry(frame, textvariable=self.duration_var, width=10).pack(anchor='w', pady=(0, 10))

        ttk.Label(frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.labels.number_of_attendees', default="Number of Attendees:")).pack(anchor='w')
        self.attendees_var = tk.StringVar(value="50")
        ttk.Entry(frame, textvariable=self.attendees_var, width=10).pack(anchor='w', pady=(0, 10))

        ttk.Label(frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.labels.estimated_0_5_kwh_per_person_per_hour_carbon_0_233_kg_co2_per_kw', default="Estimated: 0.5 kWh per person per hour\nCarbon: 0.233 kg CO2 per kWh (UK average)"),
                 foreground='gray').pack(anchor='w')

    def create_catering_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill='both', expand=True, padx=10, pady=10)

        ttk.Label(frame, text=_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.labels.catering_impact', default="Catering Impact")).pack(anchor='w', pady=(0, 10))

        self.catering_vars = {}
        options = [("Vegan", 1.5), ("Vegetarian", 2.5), ("Meat-based", 5.0)]

        for option, rate in options:
            row = ttk.Frame(frame)
            row.pack(fill='x', pady=5)

            ttk.Label(row, text=f"{option} meals:", width=20).pack(side='left')

            count_var = tk.StringVar(value="0")
            ttk.Entry(row, textvariable=count_var, width=10).pack(side='left', padx=5)
            ttk.Label(row, text=f"({rate} kg CO2 each)").pack(side='left')

            self.catering_vars[option] = (count_var, rate)

    def calculate_footprint(self):
        """Calculate and display the carbon footprint breakdown."""
        self._transport_total = 0.0
        self._energy_total = 0.0
        self._catering_total = 0.0

        try:
            for method, (count_var, rate) in self.transport_vars.items():
                count = float(count_var.get() or 0)
                self._transport_total += count * rate * 10  # 10 km average

            duration = float(self.duration_var.get() or 0)
            attendees = float(self.attendees_var.get() or 0)
            self._energy_total = duration * attendees * 0.5 * 0.233

            for option, (count_var, rate) in self.catering_vars.items():
                count = float(count_var.get() or 0)
                self._catering_total += count * rate

            total = self._transport_total + self._energy_total + self._catering_total
            self._last_total = total
            self._last_attendees = int(attendees) if attendees else 0

            self.results_label.config(text=f"Total Carbon Footprint: {total:.2f} kg CO2")
            self.detail_label.config(
                text=f"Transport: {self._transport_total:.2f} | "
                     f"Energy: {self._energy_total:.2f} | "
                     f"Catering: {self._catering_total:.2f}")

            if total > 100:
                messagebox.showinfo(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.dialogs.recommendations', default="Recommendations"),
                                   _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.dialogs.high_carbon_footprint_consider_encourage_public_transport_serve', default="High carbon footprint! Consider:\n\n"
                                   "- Encourage public transport\n"
                                   "- Serve more plant-based food\n"
                                   "- Use renewable energy\n"
                                   "- Reduce event duration"))
        except ValueError:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.dialogs.error', default="Error"), _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.dialogs.please_enter_valid_numbers', default="Please enter valid numbers."))

    def save_report(self):
        """Save the carbon tracking record to the database."""
        event_name = self.event_name_var.get().strip()
        if not event_name:
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.dialogs.validation', default="Validation"), _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.dialogs.please_enter_an_event_name', default="Please enter an event name."))
            return

        if not hasattr(self, '_last_total'):
            messagebox.showwarning(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.dialogs.calculate_first', default="Calculate First"), _t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.dialogs.please_click_calculate_before_saving', default="Please click Calculate before saving."))
            return

        total = self._last_total
        attendees = self._last_attendees
        per_person = total / attendees if attendees > 0 else 0
        score = max(0, 100 - (per_person * 10))

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO carbon_tracking
                    (event_name, transport_carbon, energy_carbon, catering_carbon,
                     total_carbon, attendees, carbon_per_person, sustainability_score,
                     recorded_by, recorded_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event_name,
                self._transport_total,
                self._energy_total,
                self._catering_total,
                total,
                attendees,
                per_person,
                score,
                _get_current_user_id(self.auth),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            ))
            conn.commit()
            conn.close()
            messagebox.showinfo(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.dialogs.success', default="Success"), f"Carbon record saved for '{event_name}'.\n"
                                f"Sustainability score: {score:.1f}/100")
            self.load_history()
        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.student_union_gui.green.green_initiatives_parts.carbontrackingdialog.dialogs.error', default="Error"), f"Failed to save: {e}")

    def load_history(self):
        for row in self.history_tree.get_children():
            self.history_tree.delete(row)
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT record_id, event_name, transport_carbon, energy_carbon,
                       catering_carbon, total_carbon, carbon_per_person,
                       sustainability_score, recorded_date
                FROM carbon_tracking ORDER BY recorded_date DESC LIMIT 50
            ''')
            for r in cursor.fetchall():
                self.history_tree.insert('', 'end', values=(
                    r['record_id'], r['event_name'],
                    f"{r['transport_carbon']:.1f}", f"{r['energy_carbon']:.1f}",
                    f"{r['catering_carbon']:.1f}", f"{r['total_carbon']:.1f}",
                    f"{r['carbon_per_person']:.2f}", f"{r['sustainability_score']:.0f}",
                    r['recorded_date'] or ''
                ))
            conn.close()
        except Exception as e:
            logger.error(f"Error loading carbon history: {e}")
