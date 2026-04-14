"""Find nearest tab for Campus Navigation GUI."""

from education_system.university_system.modules.domain.campus.campus_navigation.gui._imports import tk, ttk, messagebox, scrolledtext, _t


class NearestTabMixin:
    """Mixin for the find nearest tab."""

    def setup_nearest_tab(self, parent):
        """Set up the find nearest tab."""
        # Instructions
        ttk.Label(
            parent,
            text=_t("navigation.nearest.instructions", default="Find nearest amenities"),
            font=("Arial", 10, "italic")
        ).pack(pady=10)

        # Current location
        location_frame = ttk.LabelFrame(parent, text=_t("navigation.nearest.your_location", default="Your Location"), padding=10)
        location_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(location_frame, text=_t("navigation.route.building_code_label", default="Building Code:")).grid(row=0, column=0, sticky=tk.W)
        self.current_location_entry = ttk.Entry(location_frame)
        self.current_location_entry.grid(row=0, column=1, sticky=tk.EW, padx=5)
        self.current_location_entry.insert(0, "LIB")

        location_frame.columnconfigure(1, weight=1)

        # Quick search buttons
        quick_frame = ttk.LabelFrame(parent, text=_t("navigation.nearest.quick_search", default="Quick Search"), padding=10)
        quick_frame.pack(fill=tk.X, padx=5, pady=5)

        quick_searches = [
            (_t("navigation.quick_searches.restroom", default="Restroom"), "Restroom"),
            (_t("navigation.quick_searches.study_space", default="Study Space"), "Study"),
            (_t("navigation.quick_searches.coffee_food", default="Coffee/Food"), "Food"),
            (_t("navigation.quick_searches.computer_lab", default="Computer Lab"), "Computer"),
            (_t("navigation.quick_searches.medical", default="Medical"), "Medical"),
            (_t("navigation.quick_searches.atm", default="ATM"), "ATM")
        ]

        for i, (label, search_term) in enumerate(quick_searches):
            ttk.Button(
                quick_frame,
                text=label,
                command=lambda t=search_term: self.find_nearest(t)
            ).grid(row=i // 2, column=i % 2, padx=5, pady=5, sticky=tk.EW)

        quick_frame.columnconfigure(0, weight=1)
        quick_frame.columnconfigure(1, weight=1)

        # Custom search
        custom_frame = ttk.LabelFrame(parent, text=_t("navigation.nearest.custom_search", default="Custom Search"), padding=10)
        custom_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(custom_frame, text=_t("navigation.nearest.search_for_label", default="Search for:")).pack(anchor=tk.W)
        self.custom_search_entry = ttk.Entry(custom_frame)
        self.custom_search_entry.pack(fill=tk.X, pady=5)

        ttk.Button(
            custom_frame,
            text=_t("navigation.nearest.search_button", default="Search"),
            command=lambda: self.find_nearest(self.custom_search_entry.get())
        ).pack()

        # Results
        results_frame = ttk.LabelFrame(parent, text=_t("navigation.nearest.results", default="Results"), padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.nearest_results_text = scrolledtext.ScrolledText(
            results_frame,
            height=10,
            wrap=tk.WORD
        )
        self.nearest_results_text.pack(fill=tk.BOTH, expand=True)

    def find_nearest(self, location_type: str):
        """Find nearest locations of a specific type."""
        if not location_type.strip():
            return

        current_code = self.current_location_entry.get().strip().upper()
        if not current_code:
            current_code = "LIB"

        current_building = self.service.get_building(building_code=current_code)
        if not current_building:
            messagebox.showerror(_t("navigation.errors.error_title", default="Error"), _t("navigation.errors.building_not_found", default="Building '{building_code}' not found.").format(building_code=current_code))
            return

        results = self.service.find_nearest(
            location_type,
            current_building['latitude'],
            current_building['longitude'],
            limit=5
        )

        # Display results
        self.nearest_results_text.delete(1.0, tk.END)

        if not results:
            self.nearest_results_text.insert(
                1.0,
                _t("navigation.nearest_results.no_results", default="No {location_type} found nearby.").format(location_type=location_type)
            )
            return

        output = f"{_t('navigation.nearest_results.title_prefix', default='=== Nearest')} {location_type} ({len(results)} {_t('navigation.nearest_results.title_suffix', default='results')}) ===\n\n"

        for i, result in enumerate(results, 1):
            if result.get('result_type') == 'building':
                output += f"{i}. {result['building_name']} ({result['building_code']})\n"
            else:
                output += f"{i}. {result['poi_name']}\n"
                if result.get('building_name'):
                    output += f"   {_t('navigation.nearest_results.location_label', default='Location:')} {result['building_name']}\n"
                if result.get('room_number'):
                    output += f"   {_t('navigation.nearest_results.room_label', default='Room:')} {result['room_number']}\n"

            output += f"   {_t('navigation.nearest_results.distance_label', default='Distance:')} {result['distance_description']}\n"

            if result.get('operating_hours'):
                output += f"   {_t('navigation.nearest_results.hours_label', default='Hours:')} {result['operating_hours']}\n"
            output += "\n"

        self.nearest_results_text.insert(1.0, output)
