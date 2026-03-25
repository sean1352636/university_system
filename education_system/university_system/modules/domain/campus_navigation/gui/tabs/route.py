"""Route planner tab for Campus Navigation GUI."""

from education_system.university_system.modules.domain.campus_navigation.gui._imports import tk, ttk, messagebox, _t


class RouteTabMixin:
    """Mixin for the route planner tab."""

    def setup_route_tab(self, parent):
        """Set up the route planning tab."""
        # Instructions
        ttk.Label(
            parent,
            text=_t("navigation.route.instructions", default="Plan your route between two locations"),
            font=("Arial", 10, "italic")
        ).pack(pady=10)

        # Start location
        start_frame = ttk.LabelFrame(parent, text=_t("navigation.route.starting_location", default="Starting Location"), padding=10)
        start_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(start_frame, text=_t("navigation.route.building_code_label", default="Building Code:")).grid(row=0, column=0, sticky=tk.W)
        self.start_entry = ttk.Entry(start_frame)
        self.start_entry.grid(row=0, column=1, sticky=tk.EW, padx=5)

        ttk.Button(
            start_frame,
            text=_t("navigation.route.select_from_map", default="Select from Map"),
            command=lambda: self.select_for_route('start')
        ).grid(row=1, column=0, columnspan=2, pady=5)

        start_frame.columnconfigure(1, weight=1)

        # End location
        end_frame = ttk.LabelFrame(parent, text=_t("navigation.route.destination", default="Destination"), padding=10)
        end_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(end_frame, text=_t("navigation.route.building_code_label", default="Building Code:")).grid(row=0, column=0, sticky=tk.W)
        self.end_entry = ttk.Entry(end_frame)
        self.end_entry.grid(row=0, column=1, sticky=tk.EW, padx=5)

        ttk.Button(
            end_frame,
            text=_t("navigation.route.select_from_map", default="Select from Map"),
            command=lambda: self.select_for_route('end')
        ).grid(row=1, column=0, columnspan=2, pady=5)

        end_frame.columnconfigure(1, weight=1)

        # Options
        options_frame = ttk.LabelFrame(parent, text=_t("navigation.route.options", default="Options"), padding=10)
        options_frame.pack(fill=tk.X, padx=5, pady=5)

        self.accessible_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            options_frame,
            text=_t("navigation.route.require_accessible", default="Require accessible route"),
            variable=self.accessible_var
        ).pack(anchor=tk.W)

        # Calculate button
        ttk.Button(
            parent,
            text=_t("navigation.route.calculate_button", default="Calculate Route"),
            command=self.calculate_route,
            style='Accent.TButton'
        ).pack(pady=10)

        # Clear button
        ttk.Button(
            parent,
            text=_t("navigation.route.clear_button", default="Clear Route"),
            command=self.clear_route
        ).pack(pady=5)

    def select_for_route(self, route_point: str):
        """Select a building from the map for route planning."""
        # Store which point we're selecting for
        self.selecting_for = route_point

        # Change cursor to indicate selection mode
        self.map_canvas.config(cursor='crosshair')

        location_name = _t("navigation.messages.starting_location", default="starting location") if route_point == 'start' else _t("navigation.messages.destination", default="destination")
        messagebox.showinfo(
            _t("navigation.messages.select_building", default="Select Building"),
            _t("navigation.messages.click_to_set_location", default="Click on a building on the map to set your {location_name}.").format(location_name=location_name)
        )

    def calculate_route(self):
        """Calculate route between two locations."""
        start_code = self.start_entry.get().strip().upper()
        end_code = self.end_entry.get().strip().upper()

        if not start_code or not end_code:
            messagebox.showerror(_t("navigation.errors.error_title", default="Error"), _t("navigation.errors.enter_both_locations", default="Please enter both start and end locations."))
            return

        start_building = self.service.get_building(building_code=start_code)
        end_building = self.service.get_building(building_code=end_code)

        if not start_building:
            messagebox.showerror(_t("navigation.errors.error_title", default="Error"), _t("navigation.errors.start_building_not_found", default="Starting building '{start_code}' not found.").format(start_code=start_code))
            return

        if not end_building:
            messagebox.showerror(_t("navigation.errors.error_title", default="Error"), _t("navigation.errors.destination_not_found", default="Destination building '{end_code}' not found.").format(end_code=end_code))
            return

        if start_building['building_id'] == end_building['building_id']:
            messagebox.showwarning(_t("navigation.dialogs.warning", default="Warning"), _t("navigation.warnings.same_location", default="Start and destination are the same!"))
            return

        try:
            self.current_route = self.service.calculate_route(
                start_building['building_id'],
                end_building['building_id'],
                self.accessible_var.get()
            )

            # Redraw map with route
            self.draw_campus_map()

            # Show route details
            self.show_route_details()

            # Save to history if logged in
            if self.auth.current_user:
                user = self.auth.get_current_user()
                self.service.save_navigation_history(
                    user_id=user['username'],
                    start_location=start_building['building_name'],
                    end_location=end_building['building_name'],
                    route_taken=f"{start_code} to {end_code}",
                    duration_minutes=self.current_route['estimated_time_minutes'],
                    accessibility_required=self.accessible_var.get()
                )

        except ValueError as e:
            messagebox.showerror(_t("navigation.errors.error_title", default="Error"), str(e))

    def show_route_details(self):
        """Display route details."""
        if not self.current_route:
            return

        route = self.current_route

        details = f"{_t('navigation.route_details.title', default='=== ROUTE INFORMATION ===')}\n\n"
        details += f"{_t('navigation.route_details.from_label', default='From:')} {route['start_building']['building_name']}\n"
        details += f"{_t('navigation.route_details.to_label', default='To:')} {route['end_building']['building_name']}\n\n"
        details += f"{_t('navigation.route_details.distance_label', default='Distance:')} {route['distance_description']}\n"
        details += f"{_t('navigation.route_details.estimated_time_label', default='Estimated Time:')} {route['estimated_time_minutes']} {_t('navigation.route_details.minutes', default='minutes')}\n"

        if route['is_accessible']:
            details += f"\n{_t('navigation.route_details.accessible_route_notice', default='*** ACCESSIBLE ROUTE ***')}\n"

        details += f"\n{_t('navigation.route_details.directions_title', default='--- Directions ---')}\n"
        for direction in route['directions']:
            details += f"{direction}\n"

        if route['accessibility_notes']:
            details += f"\n{_t('navigation.route_details.accessibility_notes_title', default='--- Accessibility Notes ---')}\n"
            for note in route['accessibility_notes']:
                details += f"• {note}\n"

        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(1.0, details)

    def clear_route(self):
        """Clear the current route."""
        self.current_route = None
        self.start_entry.delete(0, tk.END)
        self.end_entry.delete(0, tk.END)
        self.draw_campus_map()
        self.details_text.delete(1.0, tk.END)

    def use_for_route(self, route_point: str):
        """Use the currently selected building for route planning."""
        if not self.selected_building:
            messagebox.showwarning(_t("navigation.dialogs.warning", default="Warning"), _t("navigation.warnings.no_building_selected", default="No building selected."))
            return

        building_code = self.selected_building['building_code']
        building_name = self.selected_building['building_name']

        if route_point == 'start':
            self.start_entry.delete(0, tk.END)
            self.start_entry.insert(0, building_code)
            messagebox.showinfo(
                _t("navigation.messages.start_location_set", default="Start Location Set"),
                _t("navigation.messages.start_set_to", default="Starting location set to: {building_name}").format(building_name=building_name)
            )
        elif route_point == 'end':
            self.end_entry.delete(0, tk.END)
            self.end_entry.insert(0, building_code)
            messagebox.showinfo(
                _t("navigation.messages.destination_set", default="Destination Set"),
                _t("navigation.messages.destination_set_to", default="Destination set to: {building_name}").format(building_name=building_name)
            )
