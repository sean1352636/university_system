"""Methods create_reports_tab through complete_treatment."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import nailbar_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class NailBarGUI:
    def create_reports_tab(self):
        """Create the reports tab - Function 9"""
        reports_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(reports_frame, text=_t("nailbar.tabs.reports"))

        # Report options
        options_frame = ttk.LabelFrame(reports_frame, text=_t("nailbar.labels.report_options"), padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(options_frame, text=_t("nailbar.labels.date_from") + ":").pack(side=tk.LEFT)
        self.report_from_var = tk.StringVar(value=(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
        ttk.Entry(options_frame, textvariable=self.report_from_var, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Label(options_frame, text=_t("nailbar.labels.date_to") + ":").pack(side=tk.LEFT)
        self.report_to_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(options_frame, textvariable=self.report_to_var, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Button(options_frame, text=_t("nailbar.btn.generate_report"),
                  command=self.generate_admin_report).pack(side=tk.LEFT, padx=20)
        ttk.Button(options_frame, text=_t("nailbar.btn.email_report"),
                  command=self.email_admin_report).pack(side=tk.LEFT, padx=5)

        # Lookups row - daily revenue, appointments by date, customer appointments
        lookup_frame = ttk.LabelFrame(reports_frame, text=_t("nailbar.labels.lookups"), padding="10")
        lookup_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(lookup_frame, text=_t("nailbar.labels.date") + ":").pack(side=tk.LEFT)
        self.lookup_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(lookup_frame, textvariable=self.lookup_date_var, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Label(lookup_frame, text=_t("nailbar.labels.customer_id") + ":").pack(side=tk.LEFT)
        self.lookup_customer_var = tk.StringVar()
        ttk.Entry(lookup_frame, textvariable=self.lookup_customer_var, width=15).pack(side=tk.LEFT, padx=5)

        ttk.Button(lookup_frame, text=_t("nailbar.btn.daily_revenue"),
                  command=self.show_daily_revenue).pack(side=tk.LEFT, padx=5)
        ttk.Button(lookup_frame, text=_t("nailbar.btn.appointments_by_date"),
                  command=self.show_appointments_by_date).pack(side=tk.LEFT, padx=5)
        ttk.Button(lookup_frame, text=_t("nailbar.btn.customer_appointments"),
                  command=self.show_customer_appointments).pack(side=tk.LEFT, padx=5)

        # Report display
        report_display = ttk.LabelFrame(reports_frame, text=_t("nailbar.labels.report_output"), padding="5")
        report_display.pack(fill=tk.BOTH, expand=True)

        self.report_text = tk.Text(report_display, wrap=tk.WORD, height=25)
        scrollbar = ttk.Scrollbar(report_display, orient=tk.VERTICAL, command=self.report_text.yview)
        self.report_text.configure(yscrollcommand=scrollbar.set)

        self.report_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _render_appointment_list(self, header: str, appointments: list):
        """Render a list of appointment dicts into the report text area."""
        self.report_text.delete("1.0", tk.END)
        lines = [header, "=" * len(header), ""]
        if not appointments:
            lines.append("No appointments found.")
        else:
            lines.append(f"{'ID':<5} {'Reference':<22} {'Customer':<18} "
                         f"{'Date':<12} {'Time':<6} {'Status':<12} {'Total':<8}")
            lines.append("-" * 85)
            for a in appointments:
                lines.append(
                    f"{a['appointment_id']:<5} {a.get('booking_reference', ''):<22} "
                    f"{a.get('customer_name', ''):<18} {a.get('appointment_date', ''):<12} "
                    f"{a.get('appointment_time', ''):<6} {a.get('status', ''):<12} "
                    f"£{(a.get('total_amount') or 0):.2f}"
                )
        self.report_text.insert("1.0", "\n".join(lines))

    def show_daily_revenue(self):
        """Display revenue summary for the selected date."""
        date = self.lookup_date_var.get().strip() or None
        try:
            from education_system.systems.university.plugins.campus_commerce.domain.nailbar.services.nailbar_core import TransactionManager
            revenue = TransactionManager.get_daily_revenue(date)
            self.report_text.delete("1.0", tk.END)
            report = (
                f"Revenue for {revenue['date']}\n"
                f"{'=' * 30}\n\n"
                f"Transactions:    {revenue['transaction_count']}\n"
                f"Service Revenue: £{revenue['service_revenue']:.2f}\n"
                f"Tips:            £{revenue['tips']:.2f}\n"
                f"Total Revenue:   £{revenue['total_revenue']:.2f}"
            )
            self.report_text.insert("1.0", report)
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def show_appointments_by_date(self):
        """Display all appointments for the selected date."""
        date = self.lookup_date_var.get().strip()
        if not date:
            messagebox.showwarning(_t("common.warning"), _t('gui.operations.commerce.nailbar.nailbar_gui_parts.nailbargui_create_reports_tab.dialogs.please_enter_a_date_yyyy_mm_dd', default="Please enter a date (YYYY-MM-DD)."))
            return
        try:
            from education_system.systems.university.plugins.campus_commerce.domain.nailbar.services.nailbar_core import AppointmentManager
            appointments = AppointmentManager.get_appointments_by_date(date)
            self._render_appointment_list(f"Appointments for {date}", appointments)
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def show_customer_appointments(self):
        """Display all appointments for the entered customer ID."""
        customer_id = self.lookup_customer_var.get().strip()
        if not customer_id:
            messagebox.showwarning(_t("common.warning"), _t('gui.operations.commerce.nailbar.nailbar_gui_parts.nailbargui_create_reports_tab.dialogs.please_enter_a_customer_id', default="Please enter a customer ID."))
            return
        try:
            from education_system.systems.university.plugins.campus_commerce.domain.nailbar.services.nailbar_core import AppointmentManager
            appointments = AppointmentManager.get_customer_appointments(customer_id)
            self._render_appointment_list(f"Appointments for customer '{customer_id}'", appointments)
        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def _get_time_slots(self) -> list:
        """Get available time slots - Function 10"""
        from education_system.systems.university.plugins.campus_commerce.domain.nailbar.services.nailbar_core import TIME_SLOTS
        return TIME_SLOTS

    def _get_categories(self) -> dict:
        """Get treatment categories - Function 11"""
        from education_system.systems.university.plugins.campus_commerce.domain.nailbar.services.nailbar_core import TREATMENT_CATEGORIES
        return TREATMENT_CATEGORIES

    def _load_appointments(self):
        """Load appointments into the treeview - Function 12"""
        for item in self.appointments_tree.get_children():
            self.appointments_tree.delete(item)

        try:
            from education_system.systems.university.plugins.campus_commerce.domain.nailbar.services.nailbar_core import AppointmentManager
            appointments = AppointmentManager.get_todays_appointments()

            for appt in appointments:
                # Get treatments for this appointment
                full_appt = AppointmentManager.get_appointment(appt['appointment_id'])
                treatments = ', '.join(t['treatment_name'] for t in full_appt.get('treatments', []))

                self.appointments_tree.insert('', tk.END, values=(
                    appt['booking_reference'],
                    appt['appointment_time'],
                    appt['customer_name'],
                    treatments[:40] + '...' if len(treatments) > 40 else treatments,
                    appt.get('technician_name', 'Any'),
                    appt['status'],
                    appt['payment_status']
                ))
        except Exception as e:
            logger.error(f"Error loading appointments: {e}")

    def _load_treatments(self):
        """Load treatments into the treeview - Function 13"""
        for item in self.treatments_tree.get_children():
            self.treatments_tree.delete(item)

        try:
            from education_system.systems.university.plugins.campus_commerce.domain.nailbar.services.nailbar_core import TreatmentManager

            category_filter = self.treatment_filter.get()
            category = None
            if category_filter != 'All':
                categories = self._get_categories()
                category = next((k for k, v in categories.items() if v == category_filter), None)

            treatments = TreatmentManager.get_all_treatments(category=category)

            treatment_list = []
            categories_dict = self._get_categories()
            for t in treatments:
                cat_name = categories_dict.get(t['category'], t['category'])
                self.treatments_tree.insert('', tk.END, values=(
                    t['treatment_id'],
                    t['name'],
                    cat_name,
                    f"{t['duration_minutes']} min",
                    f"£{t['price']:.2f}"
                ))
                treatment_list.append(f"{t['treatment_id']}: {t['name']} (£{t['price']:.2f})")

            self.appt_treatment_combo['values'] = treatment_list

        except Exception as e:
            logger.error(f"Error loading treatments: {e}")

    def _load_technicians(self):
        """Load technicians into the treeview - Function 14"""
        for item in self.technicians_tree.get_children():
            self.technicians_tree.delete(item)

        try:
            from education_system.systems.university.plugins.campus_commerce.domain.nailbar.services.nailbar_core import TechnicianManager
            technicians = TechnicianManager.get_all_technicians()

            tech_list = ['Any']
            for t in technicians:
                status = 'Active' if t.get('is_active', 1) else 'Inactive'
                self.technicians_tree.insert('', tk.END, values=(
                    t['technician_id'],
                    t['name'],
                    t.get('employee_id', ''),
                    t.get('specialties', ''),
                    t.get('certification', ''),
                    status
                ))
                tech_list.append(f"{t['technician_id']}: {t['name']}")

            self.appt_tech_combo['values'] = tech_list
            self.appt_tech_combo.set('Any')

        except Exception as e:
            logger.error(f"Error loading technicians: {e}")

    def add_treatment_to_booking(self):
        """Add treatment to current booking - Function 15"""
        treatment_str = self.appt_treatment_combo.get()
        if not treatment_str:
            messagebox.showwarning(_t("common.warning"), _t("nailbar.errors.select_treatment"))
            return

        try:
            treatment_id = int(treatment_str.split(':')[0])

            with get_db_connection() as conn:
                treatment = conn.execute(
                    'SELECT * FROM nailbar_treatments WHERE treatment_id = ?',
                    (treatment_id,)
                ).fetchone()

                if treatment:
                    self.selected_treatments.append({
                        'treatment_id': treatment_id,
                        'name': treatment['name'],
                        'duration': treatment['duration_minutes'],
                        'price': treatment['price']
                    })

                    self.selected_treatments_tree.insert('', tk.END, values=(
                        treatment['name'],
                        f"{treatment['duration_minutes']} min",
                        f"£{treatment['price']:.2f}"
                    ))

                    self._update_booking_total()

        except (ValueError, IndexError):
            messagebox.showerror(_t("common.error"), _t("nailbar.errors.invalid_selection"))

    def remove_treatment_from_booking(self):
        """Remove treatment from current booking - Function 16"""
        selected = self.selected_treatments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("nailbar.errors.select_treatment_to_remove"))
            return

        index = self.selected_treatments_tree.index(selected[0])
        self.selected_treatments.pop(index)
        self.selected_treatments_tree.delete(selected[0])
        self._update_booking_total()

    def _update_booking_total(self):
        """Update booking total display - Function 17"""
        total = sum(t['price'] for t in self.selected_treatments)
        self.booking_total_var.set(f"£{total:.2f}")

    def clear_booking(self):
        """Clear current booking - Function 18"""
        self.selected_treatments = []
        for item in self.selected_treatments_tree.get_children():
            self.selected_treatments_tree.delete(item)
        self._update_booking_total()

    def book_appointment(self):
        """Book a new appointment - Function 19"""
        if not self.selected_treatments:
            messagebox.showwarning(_t("common.warning"), _t("nailbar.errors.no_treatments"))
            return

        # Use current user details
        first_name = self.current_user.get('first_name', '')
        last_name = self.current_user.get('last_name', '')
        if first_name and last_name:
            customer_name = f"{first_name} {last_name}"
        else:
            customer_name = self.current_user.get('full_name') or self.current_user.get('username', 'Guest')

        customer_email = self.current_user.get('email', '')
        customer_phone = self.current_user.get('phone', '')
        customer_id = (self.current_user.get('student_id') or
                      self.current_user.get('username') or
                      str(self.current_user.get('id', 'guest')))

        tech_str = self.appt_tech_combo.get()
        appt_date = self.appt_date_var.get().strip()
        appt_time = self.appt_time_combo.get()

        if not appt_date or not appt_time:
            messagebox.showerror(_t("common.error"), _t('gui.operations.commerce.nailbar.nailbar_gui_parts.nailbargui_create_reports_tab.dialogs.please_select_a_date_and_time', default="Please select a date and time."))
            return

        try:
            technician_id = None
            if tech_str != 'Any':
                technician_id = int(tech_str.split(':')[0])

            treatment_ids = [t['treatment_id'] for t in self.selected_treatments]

            from education_system.systems.university.plugins.campus_commerce.domain.nailbar.services.nailbar_core import AppointmentManager

            appt_id, booking_ref = AppointmentManager.create_appointment(
                customer_id=customer_id,
                customer_name=customer_name,
                appointment_date=appt_date,
                appointment_time=appt_time,
                treatment_ids=treatment_ids,
                technician_id=technician_id,
                customer_email=customer_email,
                customer_phone=customer_phone
            )

            log_activity('create', 'nailbar_appointment',
                        details={'appointment_id': appt_id})

            messagebox.showinfo(_t("common.success"),
                              _t("nailbar.messages.appointment_booked").format(booking_reference=booking_ref))

            self.clear_booking()
            self._load_appointments()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("nailbar.errors.booking_failed").format(error=str(e)))

    def check_in_customer(self):
        """Check in customer - Function 20"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("nailbar.errors.select_appointment"))
            return

        item = self.appointments_tree.item(selected[0])
        booking_ref = item['values'][0]

        try:
            from education_system.systems.university.plugins.campus_commerce.domain.nailbar.services.nailbar_core import AppointmentManager
            appt = AppointmentManager.get_appointment_by_reference(booking_ref)

            if appt:
                AppointmentManager.update_status(appt['appointment_id'], 'checked_in',
                                                self.current_user.get('user_id'))
                messagebox.showinfo(_t("common.success"), _t("nailbar.messages.checked_in"))
                self._load_appointments()

        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def start_treatment(self):
        """Mark treatment as started - Function 21"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("nailbar.errors.select_appointment"))
            return

        item = self.appointments_tree.item(selected[0])
        booking_ref = item['values'][0]

        try:
            from education_system.systems.university.plugins.campus_commerce.domain.nailbar.services.nailbar_core import AppointmentManager
            appt = AppointmentManager.get_appointment_by_reference(booking_ref)

            if appt:
                AppointmentManager.update_status(appt['appointment_id'], 'in_progress',
                                                self.current_user.get('user_id'))
                messagebox.showinfo(_t("common.success"), _t("nailbar.messages.treatment_started"))
                self._load_appointments()

        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def complete_treatment(self):
        """Mark treatment as completed - Function 22"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("nailbar.errors.select_appointment"))
            return

        item = self.appointments_tree.item(selected[0])
        booking_ref = item['values'][0]

        try:
            from education_system.systems.university.plugins.campus_commerce.domain.nailbar.services.nailbar_core import AppointmentManager
            appt = AppointmentManager.get_appointment_by_reference(booking_ref)

            if appt:
                AppointmentManager.update_status(appt['appointment_id'], 'completed',
                                                self.current_user.get('user_id'))
                messagebox.showinfo(_t("common.success"), _t("nailbar.messages.treatment_completed"))
                self._load_appointments()

        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))
