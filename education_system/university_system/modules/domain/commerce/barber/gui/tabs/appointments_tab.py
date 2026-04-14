"""Barber Shop GUI - Appointments tab creation."""

from education_system.university_system.modules.domain.commerce.barber.gui.common import (
    tk, ttk, datetime, _t,
)


class AppointmentsTabMixin:
    """Mixin that creates the appointments management tab."""

    def create_appointments_tab(self):
        """Create the appointments management tab."""
        appointments_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(appointments_frame, text=_t("barber.tabs.appointments"))

        # Top - Book new appointment
        book_frame = ttk.LabelFrame(appointments_frame, text=_t("barber.labels.book_appointment"), padding="10")
        book_frame.pack(fill=tk.X, pady=(0, 10))

        # Customer details row - Using current logged-in user
        cust_frame = ttk.Frame(book_frame)
        cust_frame.pack(fill=tk.X, pady=5)

        # Get user details from current session
        first_name = self.current_user.get('first_name', '')
        last_name = self.current_user.get('last_name', '')
        if first_name and last_name:
            user_name = f"{first_name} {last_name}"
        else:
            user_name = self.current_user.get('full_name') or self.current_user.get('username', 'Guest')
        user_email = self.current_user.get('email', '')
        user_id = (self.current_user.get('student_id') or
                  self.current_user.get('username') or
                  str(self.current_user.get('id', '')))

        ttk.Label(cust_frame, text="Booking for:", font=('Helvetica', 10, 'bold')).pack(side=tk.LEFT)
        ttk.Label(cust_frame, text=user_name, font=('Helvetica', 10)).pack(side=tk.LEFT, padx=(5, 20))

        ttk.Label(cust_frame, text="Email:").pack(side=tk.LEFT)
        ttk.Label(cust_frame, text=user_email if user_email else "Not set",
                 foreground='gray' if not user_email else 'black').pack(side=tk.LEFT, padx=(5, 20))

        ttk.Label(cust_frame, text="ID:").pack(side=tk.LEFT)
        ttk.Label(cust_frame, text=user_id if user_id else "N/A").pack(side=tk.LEFT, padx=5)

        # Service and scheduling row
        sched_frame = ttk.Frame(book_frame)
        sched_frame.pack(fill=tk.X, pady=5)

        ttk.Label(sched_frame, text=_t("barber.labels.service") + ":").pack(side=tk.LEFT)
        self.appt_service_combo = ttk.Combobox(sched_frame, state="readonly", width=25)
        self.appt_service_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(sched_frame, text=_t("barber.labels.barber") + ":").pack(side=tk.LEFT)
        self.appt_staff_combo = ttk.Combobox(sched_frame, state="readonly", width=20)
        self.appt_staff_combo.pack(side=tk.LEFT, padx=5)

        ttk.Label(sched_frame, text=_t("barber.labels.date") + ":").pack(side=tk.LEFT)
        self.appt_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(sched_frame, textvariable=self.appt_date_var, width=12).pack(side=tk.LEFT, padx=5)

        ttk.Label(sched_frame, text=_t("barber.labels.time") + ":").pack(side=tk.LEFT)
        self.appt_time_combo = ttk.Combobox(sched_frame, state="readonly", width=10)
        self.appt_time_combo['values'] = self._get_time_slots()
        self.appt_time_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(sched_frame, text=_t("barber.btn.book_appointment"),
                  command=self.book_appointment).pack(side=tk.LEFT, padx=20)

        # Today's appointments
        today_frame = ttk.LabelFrame(appointments_frame, text=_t("barber.labels.todays_appointments"), padding="5")
        today_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('number', 'time', 'customer', 'service', 'barber', 'status', 'payment')
        self.appointments_tree = ttk.Treeview(today_frame, columns=columns, show='headings', height=12)

        self.appointments_tree.heading('number', text=_t("barber.labels.appt_number"))
        self.appointments_tree.heading('time', text=_t("barber.labels.time"))
        self.appointments_tree.heading('customer', text=_t("barber.labels.customer"))
        self.appointments_tree.heading('service', text=_t("barber.labels.service"))
        self.appointments_tree.heading('barber', text=_t("barber.labels.barber"))
        self.appointments_tree.heading('status', text=_t("barber.labels.status"))
        self.appointments_tree.heading('payment', text=_t("barber.labels.payment_status"))

        self.appointments_tree.column('number', width=120)
        self.appointments_tree.column('time', width=70)
        self.appointments_tree.column('customer', width=150)
        self.appointments_tree.column('service', width=150)
        self.appointments_tree.column('barber', width=120)
        self.appointments_tree.column('status', width=100)
        self.appointments_tree.column('payment', width=100)

        scrollbar = ttk.Scrollbar(today_frame, orient=tk.VERTICAL, command=self.appointments_tree.yview)
        self.appointments_tree.configure(yscrollcommand=scrollbar.set)

        self.appointments_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons - Row 1
        action_frame = ttk.Frame(appointments_frame)
        action_frame.pack(fill=tk.X, pady=(5, 2))

        ttk.Button(action_frame, text=_t("barber.btn.check_in"),
                  command=self.check_in_customer).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text=_t("barber.btn.start_service"),
                  command=self.start_service).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text=_t("barber.btn.complete_service"),
                  command=self.complete_service).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text=_t("barber.btn.process_payment"),
                  command=self.process_payment).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text=_t("barber.btn.cancel_appointment"),
                  command=self.cancel_appointment).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame, text=_t("barber.btn.reschedule"),
                  command=self.reschedule_appointment).pack(side=tk.LEFT, padx=3)

        # Action buttons - Row 2 (Additional features)
        action_frame2 = ttk.Frame(appointments_frame)
        action_frame2.pack(fill=tk.X, pady=2)

        ttk.Button(action_frame2, text="Mark No-Show",
                  command=self.mark_no_show).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame2, text="Set Reminder",
                  command=self.set_appointment_reminder).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame2, text="View History",
                  command=self.view_appointment_history).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame2, text="Weekly Calendar",
                  command=self.show_weekly_calendar).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame2, text="Bulk Cancel",
                  command=self.bulk_cancel_appointments).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame2, text="View Waitlist",
                  command=self.view_waitlist).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame2, text="Add to Waitlist",
                  command=self.add_to_waitlist).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame2, text="Block Time Slot",
                  command=self.block_time_slot).pack(side=tk.LEFT, padx=3)
        ttk.Button(action_frame2, text="Recurring Appt",
                  command=self.recurring_appointment).pack(side=tk.LEFT, padx=3)
