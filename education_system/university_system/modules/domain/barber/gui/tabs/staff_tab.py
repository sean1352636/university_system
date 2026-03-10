"""Barber Shop GUI - Staff tab creation."""

from education_system.university_system.modules.domain.barber.gui.common import (
    tk, ttk, _t,
)


class StaffTabMixin:
    """Mixin that creates the staff management tab."""

    def create_staff_tab(self):
        """Create the staff management tab."""
        staff_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(staff_frame, text=_t("barber.tabs.staff"))

        # Left - Staff list
        list_frame = ttk.LabelFrame(staff_frame, text=_t("barber.labels.staff_list"), padding="5")
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        columns = ('id', 'name', 'employee_id', 'specialties', 'status')
        self.staff_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        self.staff_tree.heading('id', text='ID')
        self.staff_tree.heading('name', text=_t("barber.labels.name"))
        self.staff_tree.heading('employee_id', text=_t("barber.labels.employee_id"))
        self.staff_tree.heading('specialties', text=_t("barber.labels.specialties"))
        self.staff_tree.heading('status', text=_t("barber.labels.status"))

        self.staff_tree.column('id', width=50)
        self.staff_tree.column('name', width=150)
        self.staff_tree.column('employee_id', width=100)
        self.staff_tree.column('specialties', width=200)
        self.staff_tree.column('status', width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.staff_tree.yview)
        self.staff_tree.configure(yscrollcommand=scrollbar.set)

        self.staff_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Right - Add staff
        edit_frame = ttk.LabelFrame(staff_frame, text=_t("barber.labels.add_staff"), padding="10")
        edit_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        ttk.Label(edit_frame, text=_t("barber.labels.name") + ":").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.staff_name_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.staff_name_var, width=25).grid(row=0, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("barber.labels.employee_id") + ":").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.staff_emp_id_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.staff_emp_id_var, width=25).grid(row=1, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("barber.labels.specialties") + ":").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.staff_specialties_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.staff_specialties_var, width=25).grid(row=2, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("barber.labels.phone") + ":").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.staff_phone_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.staff_phone_var, width=25).grid(row=3, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("barber.labels.email") + ":").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.staff_email_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.staff_email_var, width=25).grid(row=4, column=1, pady=2)

        ttk.Button(edit_frame, text=_t("barber.btn.add_staff"),
                  command=self.add_staff).grid(row=5, column=0, columnspan=2, pady=10)
