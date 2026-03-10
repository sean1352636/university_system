"""Barber Shop GUI - Services tab creation."""

from education_system.university_system.modules.domain.barber.gui.common import (
    tk, ttk, _t,
)


class ServicesTabMixin:
    """Mixin that creates the services management tab."""

    def create_services_tab(self):
        """Create the services management tab."""
        services_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(services_frame, text=_t("barber.tabs.services"))

        # Left - Services list
        list_frame = ttk.LabelFrame(services_frame, text=_t("barber.labels.service_list"), padding="5")
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        columns = ('id', 'name', 'type', 'duration', 'price')
        self.services_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        self.services_tree.heading('id', text='ID')
        self.services_tree.heading('name', text=_t("barber.labels.service_name"))
        self.services_tree.heading('type', text=_t("barber.labels.type"))
        self.services_tree.heading('duration', text=_t("barber.labels.duration"))
        self.services_tree.heading('price', text=_t("barber.labels.price"))

        self.services_tree.column('id', width=50)
        self.services_tree.column('name', width=150)
        self.services_tree.column('type', width=120)
        self.services_tree.column('duration', width=80)
        self.services_tree.column('price', width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.services_tree.yview)
        self.services_tree.configure(yscrollcommand=scrollbar.set)

        self.services_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Right - Add/Edit service
        edit_frame = ttk.LabelFrame(services_frame, text=_t("barber.labels.add_service"), padding="10")
        edit_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        ttk.Label(edit_frame, text=_t("barber.labels.service_name") + ":").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.service_name_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.service_name_var, width=25).grid(row=0, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("barber.labels.type") + ":").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.service_type_combo = ttk.Combobox(edit_frame, state="readonly", width=22)
        self.service_type_combo['values'] = list(self._get_service_types().values())
        self.service_type_combo.grid(row=1, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("barber.labels.duration") + " (min):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.service_duration_var = tk.StringVar(value="30")
        ttk.Entry(edit_frame, textvariable=self.service_duration_var, width=25).grid(row=2, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("barber.labels.price") + " (£):").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.service_price_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.service_price_var, width=25).grid(row=3, column=1, pady=2)

        ttk.Label(edit_frame, text=_t("barber.labels.description") + ":").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.service_desc_text = tk.Text(edit_frame, width=25, height=3)
        self.service_desc_text.grid(row=4, column=1, pady=2)

        btn_frame = ttk.Frame(edit_frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text=_t("barber.btn.add_service"),
                  command=self.add_service).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t("barber.btn.update_service"),
                  command=self.update_service).pack(side=tk.LEFT, padx=2)
