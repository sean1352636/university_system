"""Building directory tab for Campus Navigation GUI."""

from education_system.systems.university.interfaces.gui.operations.campus.campus_navigation._imports import tk, ttk, Optional, _t


class DirectoryTabMixin:
    """Mixin for the building directory tab."""

    def setup_directory_tab(self, parent):
        """Set up the building directory tab."""
        # Search frame
        search_frame = ttk.LabelFrame(parent, text=_t("navigation.directory.search_buildings", default="Search Buildings"), padding=10)
        search_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(search_frame, text=_t("navigation.directory.search_label", default="Search:")).grid(row=0, column=0, sticky=tk.W, pady=2)
        self.search_entry = ttk.Entry(search_frame)
        self.search_entry.grid(row=0, column=1, sticky=tk.EW, pady=2)
        self.search_entry.bind('<Return>', lambda e: self.search_buildings())

        ttk.Button(search_frame, text=_t("navigation.directory.search_button", default="Search"), command=self.search_buildings).grid(
            row=0, column=2, padx=5, pady=2
        )

        search_frame.columnconfigure(1, weight=1)

        # Filter frame
        filter_frame = ttk.LabelFrame(parent, text=_t("navigation.directory.filter_by_type", default="Filter by Type"), padding=10)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        self.building_type_var = tk.StringVar(value=_t("navigation.building_types.all", default="All"))
        types = [
            _t("navigation.building_types.all", default="All"),
            _t("navigation.building_types.academic", default="Academic"),
            _t("navigation.building_types.housing", default="Housing"),
            _t("navigation.building_types.athletic", default="Athletic"),
            _t("navigation.building_types.administrative", default="Administrative"),
            _t("navigation.building_types.student_services", default="Student Services"),
            _t("navigation.building_types.medical", default="Medical")
        ]

        for i, btype in enumerate(types):
            ttk.Radiobutton(
                filter_frame,
                text=btype,
                variable=self.building_type_var,
                value=btype,
                command=self.filter_buildings
            ).grid(row=i // 2, column=i % 2, sticky=tk.W, pady=2)

        # Buildings list
        list_frame = ttk.LabelFrame(parent, text=_t("navigation.directory.buildings_list", default="Buildings"), padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Scrollable listbox
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.buildings_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        self.buildings_listbox.pack(fill=tk.BOTH, expand=True)
        self.buildings_listbox.bind('<<ListboxSelect>>', self.on_building_select)

        scrollbar.config(command=self.buildings_listbox.yview)

        # Load all buildings initially
        self.load_buildings()

    def load_buildings(self, building_type: Optional[str] = None):
        """Load buildings into the list."""
        self.buildings_listbox.delete(0, tk.END)

        if building_type and building_type != "All":
            buildings = self.service.get_all_buildings(building_type)
        else:
            buildings = self.service.get_all_buildings()

        for building in buildings:
            self.buildings_listbox.insert(
                tk.END,
                f"{building['building_code']} - {building['building_name']}"
            )

    def search_buildings(self):
        """Search for buildings."""
        search_term = self.search_entry.get().strip()
        if not search_term:
            self.load_buildings()
            return

        buildings = self.service.search_buildings(search_term)

        self.buildings_listbox.delete(0, tk.END)
        for building in buildings:
            self.buildings_listbox.insert(
                tk.END,
                f"{building['building_code']} - {building['building_name']}"
            )

    def filter_buildings(self):
        """Filter buildings by type."""
        building_type = self.building_type_var.get()
        all_text = _t("navigation.building_types.all", default="All")
        self.load_buildings(None if building_type == all_text else building_type)

    def on_building_select(self, event):
        """Handle building selection from list."""
        selection = self.buildings_listbox.curselection()
        if selection:
            index = selection[0]
            building_info = self.buildings_listbox.get(index)
            # Extract building code (format: "CODE - Name")
            code = building_info.split('-')[0].strip()

            building = self.service.get_building(building_code=code)
            if building:
                self.show_building_details(building)
