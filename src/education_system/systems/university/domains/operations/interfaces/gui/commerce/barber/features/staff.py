"""Barber Shop GUI - Staff management feature methods."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from education_system.systems.university.domains.operations.interfaces.gui.commerce.barber.common import (
    tk, ttk, messagebox, filedialog, logging,
    datetime, timedelta,
    _t, get_db_connection, log_activity,
    EMAIL_AVAILABLE,
)

logger = logging.getLogger(__name__)


class StaffMixin:
    """Mixin providing staff management methods for BarberGUI."""

    def add_staff(self):
        """Add a new staff member."""
        name = self.staff_name_var.get().strip()
        emp_id = self.staff_emp_id_var.get().strip()
        specialties = self.staff_specialties_var.get().strip()
        phone = self.staff_phone_var.get().strip()
        email = self.staff_email_var.get().strip()

        if not name:
            messagebox.showerror(_t("common.error"), _t("barber.errors.fill_required"))
            return

        try:
            from education_system.systems.university.domains.operations.domain.commerce.barber.services.barber_core import StaffManager
            staff_id = StaffManager.add_staff(
                name=name, employee_id=emp_id, specialties=specialties,
                phone=phone, email=email
            )

            log_activity('create', 'barber_staff',
                        user_id=self.current_user.get('user_id'),
                        details={'staff_id': staff_id})

            messagebox.showinfo(_t("common.success"), _t("barber.messages.staff_added"))
            self._clear_staff_form()
            self._load_staff()

        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    # ==================== ADVANCED STAFF FEATURES ====================

    def set_staff_schedule(self):
        """Set staff schedule."""
        selected = self.staff_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.operations.commerce.barber.features.staff.dialogs.warning', default="Warning"), _t('gui.operations.commerce.barber.features.staff.dialogs.please_select_a_staff_member', default="Please select a staff member."))
            return

        item = self.staff_tree.item(selected[0])
        staff_id = item['values'][0]
        staff_name = item['values'][1]

        sched_window = tk.Toplevel(self.parent)
        sched_window.title(f"Schedule - {staff_name}")
        sched_window.geometry("500x450")
        sched_window.transient(self.parent)
        sched_window.grab_set()

        ttk.Label(sched_window, text=f"Set Schedule for {staff_name}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(sched_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        schedule_entries = {}

        for i, day in enumerate(days):
            ttk.Label(frame, text=day).grid(row=i, column=0, sticky=tk.W, pady=2)

            working_var = tk.BooleanVar(value=True if i < 5 else False)
            ttk.Checkbutton(frame, text=_t('gui.operations.commerce.barber.features.staff.buttons.working', default="Working"), variable=working_var).grid(row=i, column=1, padx=5)

            start_combo = ttk.Combobox(frame, values=self._get_time_slots(), width=8)
            start_combo.set('09:00')
            start_combo.grid(row=i, column=2, padx=2)

            end_combo = ttk.Combobox(frame, values=self._get_time_slots(), width=8)
            end_combo.set('17:00')
            end_combo.grid(row=i, column=3, padx=2)

            schedule_entries[day] = {'working': working_var, 'start': start_combo, 'end': end_combo}

        def save_schedule():
            try:
                schedule = []
                for day, entries in schedule_entries.items():
                    if entries['working'].get():
                        schedule.append({
                            'day': day,
                            'start_time': entries['start'].get(),
                            'end_time': entries['end'].get()
                        })

                from education_system.systems.university.domains.operations.domain.commerce.barber.services.barber_core import StaffScheduleManager
                StaffScheduleManager.set_schedule(staff_id, schedule)
                messagebox.showinfo(_t('gui.operations.commerce.barber.features.staff.dialogs.success', default="Success"), _t('gui.operations.commerce.barber.features.staff.dialogs.schedule_saved', default="Schedule saved!"))
                sched_window.destroy()
            except Exception as e:
                messagebox.showerror(_t('gui.operations.commerce.barber.features.staff.dialogs.error', default="Error"), str(e))

        ttk.Button(sched_window, text=_t('gui.operations.commerce.barber.features.staff.buttons.save_schedule', default="Save Schedule"), command=save_schedule).pack(pady=10)

    def view_staff_performance(self):
        """View staff performance."""
        perf_window = tk.Toplevel(self.parent)
        perf_window.title(_t('gui.operations.commerce.barber.features.staff.windows.staff_performance', default="Staff Performance"))
        perf_window.geometry("700x450")
        perf_window.transient(self.parent)

        columns = ('name', 'appointments', 'revenue', 'avg_rating', 'no_shows', 'retention')
        tree = ttk.Treeview(perf_window, columns=columns, show='headings', height=15)

        tree.heading('name', text=_t('gui.operations.commerce.barber.features.staff.headings.staff', default='Staff'))
        tree.heading('appointments', text=_t('gui.operations.commerce.barber.features.staff.headings.appointments', default='Appointments'))
        tree.heading('revenue', text=_t('gui.operations.commerce.barber.features.staff.headings.revenue', default='Revenue'))
        tree.heading('avg_rating', text=_t('gui.operations.commerce.barber.features.staff.headings.avg_rating', default='Avg Rating'))
        tree.heading('no_shows', text=_t('gui.operations.commerce.barber.features.staff.headings.no_shows', default='No-Shows'))
        tree.heading('retention', text=_t('gui.operations.commerce.barber.features.staff.headings.retention', default='Retention %'))

        for col in columns:
            tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(perf_window, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        try:
            from education_system.systems.university.domains.operations.domain.commerce.barber.services.barber_core import AnalyticsManager
            performance = AnalyticsManager.get_staff_performance()
            for staff in performance:
                tree.insert('', tk.END, values=(
                    staff['name'], staff['appointment_count'],
                    f"£{staff['total_revenue']:.2f}", f"{staff['avg_rating']:.1f}/5",
                    staff['no_show_count'], f"{staff['retention_rate']:.0f}%"
                ))
        except Exception as e:
            logger.error(f"Error loading performance: {e}")

    def assign_staff_to_appointment(self):
        """Assign staff to appointment."""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.operations.commerce.barber.features.staff.dialogs.warning', default="Warning"), _t('gui.operations.commerce.barber.features.staff.dialogs.please_select_an_appointment', default="Please select an appointment."))
            return

        item = self.appointments_tree.item(selected[0])
        appt_number = item['values'][0]

        assign_window = tk.Toplevel(self.parent)
        assign_window.title(_t('gui.operations.commerce.barber.features.staff.windows.assign_staff', default="Assign Staff"))
        assign_window.geometry("350x200")
        assign_window.transient(self.parent)
        assign_window.grab_set()

        ttk.Label(assign_window, text=f"Assign Staff to {appt_number}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(assign_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_t('gui.operations.commerce.barber.features.staff.labels.select_staff', default="Select Staff:")).pack(anchor=tk.W)
        staff_combo = ttk.Combobox(frame, values=self.appt_staff_combo['values'], width=25)
        staff_combo.pack(fill=tk.X, pady=10)

        def assign():
            if not staff_combo.get() or staff_combo.get() == 'Any':
                messagebox.showerror(_t('gui.operations.commerce.barber.features.staff.dialogs.error', default="Error"), _t('gui.operations.commerce.barber.features.staff.dialogs.please_select_a_staff_member', default="Please select a staff member."))
                return
            try:
                staff_id = int(staff_combo.get().split(':')[0])
                from education_system.systems.university.domains.operations.domain.commerce.barber.services.barber_core import AppointmentManager
                appt = AppointmentManager.get_appointment_by_number(appt_number)
                if appt:
                    AppointmentManager.assign_staff(appt['appointment_id'], staff_id)
                    messagebox.showinfo(_t('gui.operations.commerce.barber.features.staff.dialogs.success', default="Success"), _t('gui.operations.commerce.barber.features.staff.dialogs.staff_assigned', default="Staff assigned!"))
                    assign_window.destroy()
                    self._load_appointments()
            except Exception as e:
                messagebox.showerror(_t('gui.operations.commerce.barber.features.staff.dialogs.error', default="Error"), str(e))

        ttk.Button(assign_window, text=_t('gui.operations.commerce.barber.features.staff.buttons.assign', default="Assign"), command=assign).pack(pady=10)

    def set_staff_commission(self):
        """Set staff commission."""
        selected = self.staff_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.operations.commerce.barber.features.staff.dialogs.warning', default="Warning"), _t('gui.operations.commerce.barber.features.staff.dialogs.please_select_a_staff_member', default="Please select a staff member."))
            return

        item = self.staff_tree.item(selected[0])
        staff_id = item['values'][0]
        staff_name = item['values'][1]

        comm_window = tk.Toplevel(self.parent)
        comm_window.title(f"Commission - {staff_name}")
        comm_window.geometry("400x300")
        comm_window.transient(self.parent)
        comm_window.grab_set()

        ttk.Label(comm_window, text=f"Set Commission for {staff_name}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(comm_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_t('gui.operations.commerce.barber.features.staff.labels.commission_type', default="Commission Type:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        type_combo = ttk.Combobox(frame, values=['percentage', 'flat_rate'], width=15)
        type_combo.set('percentage')
        type_combo.grid(row=0, column=1, pady=5)

        ttk.Label(frame, text=_t('gui.operations.commerce.barber.features.staff.labels.rate_or', default="Rate (% or £):")).grid(row=1, column=0, sticky=tk.W, pady=5)
        rate_var = tk.StringVar(value="20")
        ttk.Entry(frame, textvariable=rate_var, width=10).grid(row=1, column=1, pady=5)

        ttk.Label(frame, text=_t('gui.operations.commerce.barber.features.staff.labels.for_service_optional', default="For Service (optional):")).grid(row=2, column=0, sticky=tk.W, pady=5)
        service_combo = ttk.Combobox(frame, values=['All Services'] + list(self.appt_service_combo['values']), width=25)
        service_combo.set('All Services')
        service_combo.grid(row=2, column=1, pady=5)

        def save_commission():
            try:
                service_id = None
                if service_combo.get() != 'All Services':
                    service_id = int(service_combo.get().split(':')[0])

                from education_system.systems.university.domains.operations.domain.commerce.barber.services.barber_core import CommissionManager
                CommissionManager.set_commission(
                    staff_id=staff_id,
                    commission_type=type_combo.get(),
                    rate=float(rate_var.get()),
                    service_id=service_id
                )
                messagebox.showinfo(_t('gui.operations.commerce.barber.features.staff.dialogs.success', default="Success"), _t('gui.operations.commerce.barber.features.staff.dialogs.commission_saved', default="Commission saved!"))
                comm_window.destroy()
            except Exception as e:
                messagebox.showerror(_t('gui.operations.commerce.barber.features.staff.dialogs.error', default="Error"), str(e))

        ttk.Button(comm_window, text=_t('gui.operations.commerce.barber.features.staff.buttons.save', default="Save"), command=save_commission).pack(pady=10)

    def view_staff_calendar(self):
        """View staff calendar."""
        selected = self.staff_tree.selection()
        staff_id = None
        staff_name = "All Staff"
        if selected:
            item = self.staff_tree.item(selected[0])
            staff_id = item['values'][0]
            staff_name = item['values'][1]

        cal_window = tk.Toplevel(self.parent)
        cal_window.title(f"Calendar - {staff_name}")
        cal_window.geometry("800x500")
        cal_window.transient(self.parent)

        # Week navigation
        nav_frame = ttk.Frame(cal_window, padding="10")
        nav_frame.pack(fill=tk.X)

        current_week_start = datetime.now() - timedelta(days=datetime.now().weekday())
        week_var = tk.StringVar(value=current_week_start.strftime('%Y-%m-%d'))

        def prev_week():
            date = datetime.strptime(week_var.get(), '%Y-%m-%d') - timedelta(days=7)
            week_var.set(date.strftime('%Y-%m-%d'))
            load_calendar()

        def next_week():
            date = datetime.strptime(week_var.get(), '%Y-%m-%d') + timedelta(days=7)
            week_var.set(date.strftime('%Y-%m-%d'))
            load_calendar()

        ttk.Button(nav_frame, text=_t('gui.operations.commerce.barber.features.staff.buttons.prev', default="< Prev"), command=prev_week).pack(side=tk.LEFT)
        ttk.Label(nav_frame, textvariable=week_var, font=('Helvetica', 12, 'bold')).pack(side=tk.LEFT, padx=20)
        ttk.Button(nav_frame, text=_t('gui.operations.commerce.barber.features.staff.buttons.next', default="Next >"), command=next_week).pack(side=tk.LEFT)

        # Calendar display
        columns = ('time', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')
        tree = ttk.Treeview(cal_window, columns=columns, show='headings', height=18)

        tree.heading('time', text=_t('gui.operations.commerce.barber.features.staff.headings.time', default='Time'))
        for i, day in enumerate(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']):
            tree.heading(columns[i + 1], text=day)
            tree.column(columns[i + 1], width=90)
        tree.column('time', width=60)

        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        def load_calendar():
            for item in tree.get_children():
                tree.delete(item)

            start = datetime.strptime(week_var.get(), '%Y-%m-%d')
            time_slots = self._get_time_slots()

            try:
                with get_db_connection() as conn:
                    for time_slot in time_slots:
                        row = [time_slot]
                        for i in range(7):
                            day_date = (start + timedelta(days=i)).strftime('%Y-%m-%d')
                            query = """
                                SELECT customer_name FROM barber_appointments
                                WHERE appointment_date = ? AND appointment_time = ?
                            """
                            params = [day_date, time_slot]
                            if staff_id:
                                query += " AND staff_id = ?"
                                params.append(staff_id)

                            appt = conn.execute(query, params).fetchone()
                            row.append(appt['customer_name'][:12] if appt else '')

                        tree.insert('', tk.END, values=row)
            except Exception as e:
                logger.error(f"Error loading calendar: {e}")

        load_calendar()

    def toggle_staff_availability(self):
        """Toggle staff availability."""
        selected = self.staff_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.operations.commerce.barber.features.staff.dialogs.warning', default="Warning"), _t('gui.operations.commerce.barber.features.staff.dialogs.please_select_a_staff_member', default="Please select a staff member."))
            return

        item = self.staff_tree.item(selected[0])
        staff_id = item['values'][0]
        staff_name = item['values'][1]
        current_status = item['values'][4]

        new_status = 'Inactive' if current_status == 'Active' else 'Active'
        if not messagebox.askyesno(_t('gui.operations.commerce.barber.features.staff.dialogs.confirm', default="Confirm"), f"Set {staff_name} to {new_status}?"):
            return

        try:
            from education_system.systems.university.domains.operations.domain.commerce.barber.services.barber_core import StaffManager
            StaffManager.set_availability(staff_id, new_status == 'Active')
            messagebox.showinfo(_t('gui.operations.commerce.barber.features.staff.dialogs.success', default="Success"), f"{staff_name} is now {new_status}.")
            self._load_staff()
        except Exception as e:
            messagebox.showerror(_t('gui.operations.commerce.barber.features.staff.dialogs.error', default="Error"), str(e))

    def add_staff_photo(self):
        """Add staff photo."""
        selected = self.staff_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.operations.commerce.barber.features.staff.dialogs.warning', default="Warning"), _t('gui.operations.commerce.barber.features.staff.dialogs.please_select_a_staff_member', default="Please select a staff member."))
            return

        item = self.staff_tree.item(selected[0])
        staff_id = item['values'][0]

        file_path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif")],
            title=_t('gui.operations.commerce.barber.features.staff.dialogs.select_staff_photo', default="Select Staff Photo")
        )
        if not file_path:
            return

        try:
            from education_system.systems.university.domains.operations.domain.commerce.barber.services.barber_core import StaffManager
            StaffManager.add_photo(staff_id, file_path)
            messagebox.showinfo(_t('gui.operations.commerce.barber.features.staff.dialogs.success', default="Success"), _t('gui.operations.commerce.barber.features.staff.dialogs.photo_added', default="Photo added!"))
        except Exception as e:
            messagebox.showerror(_t('gui.operations.commerce.barber.features.staff.dialogs.error', default="Error"), str(e))

    def send_staff_notification(self):
        """Send staff notification."""
        selected = self.staff_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.operations.commerce.barber.features.staff.dialogs.warning', default="Warning"), _t('gui.operations.commerce.barber.features.staff.dialogs.please_select_a_staff_member', default="Please select a staff member."))
            return

        item = self.staff_tree.item(selected[0])
        staff_id = item['values'][0]
        staff_name = item['values'][1]

        notif_window = tk.Toplevel(self.parent)
        notif_window.title(f"Notify {staff_name}")
        notif_window.geometry("400x300")
        notif_window.transient(self.parent)
        notif_window.grab_set()

        ttk.Label(notif_window, text=f"Send Notification to {staff_name}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(notif_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=_t('gui.operations.commerce.barber.features.staff.labels.subject', default="Subject:")).pack(anchor=tk.W)
        subject_var = tk.StringVar(value=_t('gui.operations.commerce.barber.features.staff.values.schedule_update', default="Schedule Update"))
        ttk.Entry(frame, textvariable=subject_var, width=40).pack(fill=tk.X, pady=5)

        ttk.Label(frame, text=_t('gui.operations.commerce.barber.features.staff.labels.message', default="Message:")).pack(anchor=tk.W)
        msg_text = tk.Text(frame, height=6, width=40)
        msg_text.pack(fill=tk.BOTH, expand=True, pady=5)

        def send():
            try:
                from education_system.systems.university.domains.operations.domain.commerce.barber.services.barber_core import StaffManager
                staff = StaffManager.get_staff(staff_id)
                if staff and staff.get('email') and EMAIL_AVAILABLE:
                    from education_system.systems.university.infrastructure.email.email_service import send_email
                    send_email(
                        staff['email'],
                        subject_var.get(),
                        msg_text.get('1.0', tk.END).strip()
                    )
                    messagebox.showinfo(_t('gui.operations.commerce.barber.features.staff.dialogs.success', default="Success"), _t('gui.operations.commerce.barber.features.staff.dialogs.notification_sent', default="Notification sent!"))
                    notif_window.destroy()
                else:
                    messagebox.showerror(_t('gui.operations.commerce.barber.features.staff.dialogs.error', default="Error"), _t('gui.operations.commerce.barber.features.staff.dialogs.staff_has_no_email_or_email_service_unavailable', default="Staff has no email or email service unavailable."))
            except Exception as e:
                messagebox.showerror(_t('gui.operations.commerce.barber.features.staff.dialogs.error', default="Error"), str(e))

        ttk.Button(notif_window, text=_t('gui.operations.commerce.barber.features.staff.buttons.send', default="Send"), command=send).pack(pady=10)
