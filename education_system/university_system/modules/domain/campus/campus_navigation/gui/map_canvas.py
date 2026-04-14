"""Campus map canvas drawing and interaction."""

from education_system.university_system.modules.domain.campus.campus_navigation.gui._imports import tk, ttk, messagebox, scrolledtext, Dict, _t


class MapCanvasMixin:
    """Mixin for campus map canvas drawing and interaction."""

    def setup_right_panel(self, parent):
        """Set up the right panel with map and details."""
        # Top section - Campus Map
        map_frame = ttk.LabelFrame(parent, text=_t("navigation.map.campus_map", default="Campus Map"), padding=10)
        map_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Canvas for map
        self.map_canvas = tk.Canvas(map_frame, bg='white', width=700, height=500)
        self.map_canvas.pack(fill=tk.BOTH, expand=True)

        # Bind click events
        self.map_canvas.bind('<Button-1>', self.on_map_click)

        # Draw initial map
        self.draw_campus_map()

        # Bottom section - Details
        details_frame = ttk.LabelFrame(parent, text=_t("navigation.map.location_details", default="Location Details"), padding=10)
        details_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.details_text = scrolledtext.ScrolledText(
            details_frame,
            height=15,
            wrap=tk.WORD
        )
        self.details_text.pack(fill=tk.BOTH, expand=True)

        # Action buttons for selected building
        action_frame = ttk.Frame(details_frame)
        action_frame.pack(fill=tk.X, pady=(5, 0))

        self.add_favorite_btn = ttk.Button(
            action_frame,
            text=_t("navigation.favorites.add_button", default="★ Add to Favorites"),
            command=self.add_to_favorites,
            state=tk.DISABLED
        )
        self.add_favorite_btn.pack(side=tk.LEFT, padx=5)

        self.use_as_start_btn = ttk.Button(
            action_frame,
            text=_t("navigation.route.use_as_start", default="Use as Start"),
            command=lambda: self.use_for_route('start'),
            state=tk.DISABLED
        )
        self.use_as_start_btn.pack(side=tk.LEFT, padx=5)

        self.use_as_end_btn = ttk.Button(
            action_frame,
            text=_t("navigation.route.use_as_destination", default="Use as Destination"),
            command=lambda: self.use_for_route('end'),
            state=tk.DISABLED
        )
        self.use_as_end_btn.pack(side=tk.LEFT, padx=5)

    def draw_campus_map(self):
        """Draw the campus map on canvas."""
        self.map_canvas.delete('all')

        # Get all buildings
        buildings = self.service.get_all_buildings()

        # Calculate scale factors
        if not buildings:
            return

        # Find min/max coordinates
        min_lat = min(b['latitude'] for b in buildings)
        max_lat = max(b['latitude'] for b in buildings)
        min_lon = min(b['longitude'] for b in buildings)
        max_lon = max(b['longitude'] for b in buildings)

        # Canvas dimensions
        canvas_width = self.map_canvas.winfo_width()
        canvas_height = self.map_canvas.winfo_height()

        if canvas_width <= 1:  # Not rendered yet
            canvas_width = 700
            canvas_height = 500

        # Add padding
        padding = 50

        # Store buildings with canvas coordinates
        self.building_markers = {}

        for building in buildings:
            # Convert lat/lon to canvas coordinates
            x = padding + (building['longitude'] - min_lon) / (max_lon - min_lon) * \
                (canvas_width - 2 * padding)
            y = canvas_height - padding - (building['latitude'] - min_lat) / \
                (max_lat - min_lat) * (canvas_height - 2 * padding)

            # Determine color based on type
            color = self.get_building_color(building['building_type'])

            # Draw building as rectangle
            size = 20
            rect_id = self.map_canvas.create_rectangle(
                x - size / 2, y - size / 2,
                x + size / 2, y + size / 2,
                fill=color,
                outline='black',
                width=2,
                tags=('building', f"building_{building['building_id']}")
            )

            # Draw building code
            text_id = self.map_canvas.create_text(
                x, y,
                text=building['building_code'],
                font=("Arial", 8, "bold"),
                tags=('building', f"building_{building['building_id']}")
            )

            # Store reference
            self.building_markers[building['building_id']] = {
                'building': building,
                'x': x,
                'y': y,
                'rect_id': rect_id,
                'text_id': text_id
            }

            # Bind hover events
            self.map_canvas.tag_bind(
                f"building_{building['building_id']}",
                '<Enter>',
                lambda e, b=building: self.on_building_hover(b)
            )

        # Draw route if exists
        if self.current_route:
            self.draw_route_on_map()

        # Draw legend
        self.draw_legend()

    def get_building_color(self, building_type: str) -> str:
        """Get color for building type."""
        colors = {
            'Academic': '#4A90E2',
            'Housing': '#7ED321',
            'Athletic': '#F5A623',
            'Administrative': '#BD10E0',
            'Student Services': '#50E3C2',
            'Medical': '#E74C3C'
        }
        return colors.get(building_type, '#95A5A6')

    def draw_legend(self):
        """Draw color legend on map."""
        types = [
            ('Academic', '#4A90E2'),
            ('Housing', '#7ED321'),
            ('Athletic', '#F5A623'),
            ('Administrative', '#BD10E0'),
            ('Student Services', '#50E3C2'),
            ('Medical', '#E74C3C')
        ]

        x_start = 10
        y_start = 10

        for i, (btype, color) in enumerate(types):
            y = y_start + i * 25

            self.map_canvas.create_rectangle(
                x_start, y,
                x_start + 15, y + 15,
                fill=color,
                outline='black'
            )

            self.map_canvas.create_text(
                x_start + 20, y + 7,
                text=btype,
                anchor=tk.W,
                font=("Arial", 9)
            )

    def draw_route_on_map(self):
        """Draw the current route on the map."""
        if not self.current_route:
            return

        start_id = self.current_route['start_building']['building_id']
        end_id = self.current_route['end_building']['building_id']

        if start_id in self.building_markers and end_id in self.building_markers:
            start_marker = self.building_markers[start_id]
            end_marker = self.building_markers[end_id]

            # Draw route line
            self.map_canvas.create_line(
                start_marker['x'], start_marker['y'],
                end_marker['x'], end_marker['y'],
                fill='red',
                width=3,
                arrow=tk.LAST,
                tags='route'
            )

            # Highlight buildings
            self.map_canvas.itemconfig(start_marker['rect_id'], outline='green', width=4)
            self.map_canvas.itemconfig(end_marker['rect_id'], outline='red', width=4)

    def on_map_click(self, event):
        """Handle map click events."""
        # Find clicked building
        items = self.map_canvas.find_overlapping(event.x, event.y, event.x, event.y)

        for item in items:
            tags = self.map_canvas.gettags(item)
            for tag in tags:
                if tag.startswith('building_'):
                    building_id = int(tag.split('_')[1])
                    if building_id in self.building_markers:
                        building = self.building_markers[building_id]['building']

                        # Check if we're in route selection mode
                        if self.selecting_for:
                            if self.selecting_for == 'start':
                                self.start_entry.delete(0, tk.END)
                                self.start_entry.insert(0, building['building_code'])
                                messagebox.showinfo(
                                    _t("navigation.messages.start_location_set", default="Start Location Set"),
                                    _t("navigation.messages.start_set_to", default="Starting location set to: {building_name}").format(building_name=building['building_name'])
                                )
                            elif self.selecting_for == 'end':
                                self.end_entry.delete(0, tk.END)
                                self.end_entry.insert(0, building['building_code'])
                                messagebox.showinfo(
                                    _t("navigation.messages.destination_set", default="Destination Set"),
                                    _t("navigation.messages.destination_set_to", default="Destination set to: {building_name}").format(building_name=building['building_name'])
                                )

                            # Reset selection mode
                            self.selecting_for = None
                            self.map_canvas.config(cursor='')
                        else:
                            # Normal mode - show details
                            self.show_building_details(building)
                        return

    def on_building_hover(self, building: Dict):
        """Handle building hover events."""
        # Could show tooltip here
        pass

    def show_building_details(self, building: Dict):
        """Display building details in the details panel."""
        self.selected_building = building

        yes_no = lambda val: _t("navigation.building_details.yes", default="Yes") if val else _t("navigation.building_details.no", default="No")
        na_text = _t("navigation.building_details.na", default="N/A")

        details = f"{_t('navigation.building_details.building_label', default='Building:')} {building['building_name']} ({building['building_code']})\n"
        details += f"{_t('navigation.building_details.type_label', default='Type:')} {building['building_type']}\n"
        details += f"{_t('navigation.building_details.address_label', default='Address:')} {building.get('address', na_text)}\n"
        details += f"{_t('navigation.building_details.floors_label', default='Floors:')} {building['floors']}\n\n"

        details += f"{_t('navigation.building_details.accessibility_title', default='Accessibility Features:')}\n"
        details += f"  • {_t('navigation.building_details.accessible_label', default='Accessible:')} {yes_no(building['is_accessible'])}\n"
        details += f"  • {_t('navigation.building_details.elevator_label', default='Elevator:')} {yes_no(building['has_elevator'])}\n"
        details += f"  • {_t('navigation.building_details.ramp_label', default='Ramp:')} {yes_no(building['has_ramp'])}\n"
        details += f"  • {_t('navigation.building_details.automatic_doors_label', default='Automatic Doors:')} {yes_no(building['has_automatic_doors'])}\n\n"

        if building.get('operating_hours'):
            details += f"{_t('navigation.building_details.hours_label', default='Hours:')} {building['operating_hours']}\n\n"

        if building.get('amenities'):
            details += f"{_t('navigation.building_details.amenities_label', default='Amenities:')} {building['amenities']}\n\n"

        # Get POIs
        pois = self.service.get_points_of_interest(building_id=building['building_id'])
        if pois:
            details += f"{_t('navigation.building_details.pois_title', default='Points of Interest')} ({len(pois)}):\n"
            for poi in pois[:5]:
                details += f"  • {poi['poi_name']} ({poi['poi_type']})\n"
                if poi.get('room_number'):
                    details += f"    {_t('navigation.building_details.room_label', default='Room:')} {poi['room_number']}\n"

        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(1.0, details)

        # Enable action buttons
        if self.auth.current_user:
            self.add_favorite_btn.config(state=tk.NORMAL)
        self.use_as_start_btn.config(state=tk.NORMAL)
        self.use_as_end_btn.config(state=tk.NORMAL)
