"""
Campus Navigation GUI Interface

Provides graphical interface for campus navigation with interactive map.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from typing import Optional, Dict, List
import math

from university_system.modules.domain.campus_navigation.services.navigation_service import (
    NavigationService
)
from university_system.infrastructure.shared_context import get_auth
from university_system.infrastructure.localization import get_translation

_t = get_translation


class NavigationGUI:
    """GUI interface for Campus Navigation."""

    def __init__(self, parent=None):
        """Initialize the Campus Navigation GUI."""
        self.service = NavigationService()
        self.auth = get_auth()

        # Create main window or frame
        if parent is None:
            self.root = tk.Tk()
            self.root.title(_t("navigation.title", default="Campus Navigation System"))
            self.root.geometry("1200x800")
            self.is_standalone = True
            self.window = self.root
        else:
            # Parent is a Toplevel window
            self.window = parent
            self.root = tk.Frame(parent)
            self.root.pack(fill=tk.BOTH, expand=True)
            self.is_standalone = False

        # State variables
        self.selected_building = None
        self.route_start = None
        self.route_end = None
        self.current_route = None
        self.selecting_for = None  # Track if we're selecting from map

        self.setup_ui()

    def setup_ui(self):
        """Set up the GUI components."""
        # Main container with paned window
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel - Controls
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)

        # Right panel - Map and details
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=3)

        self.setup_left_panel(left_frame)
        self.setup_right_panel(right_frame)

    def setup_left_panel(self, parent):
        """Set up the left control panel."""
        # Title
        title = ttk.Label(parent, text=_t("navigation.main_title", default="Campus Navigation"), font=("Arial", 16, "bold"))
        title.pack(pady=10)

        # Notebook for different features
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tab 1: Building Directory
        directory_tab = ttk.Frame(notebook)
        notebook.add(directory_tab, text=_t("navigation.tabs.directory", default="Directory"))
        self.setup_directory_tab(directory_tab)

        # Tab 2: Route Planner
        route_tab = ttk.Frame(notebook)
        notebook.add(route_tab, text=_t("navigation.tabs.directions", default="Get Directions"))
        self.setup_route_tab(route_tab)

        # Tab 3: Find Nearest
        nearest_tab = ttk.Frame(notebook)
        notebook.add(nearest_tab, text=_t("navigation.tabs.find_nearest", default="Find Nearest"))
        self.setup_nearest_tab(nearest_tab)

        # Tab 4: Favorites
        favorites_tab = ttk.Frame(notebook)
        notebook.add(favorites_tab, text=_t("navigation.tabs.favorites", default="Favorites"))
        self.setup_favorites_tab(favorites_tab)

        # Return to Main Menu button
        ttk.Button(
            parent,
            text=_t("navigation.return_to_main", default="Return to Main Menu"),
            command=self.close_window,
            style='Accent.TButton'
        ).pack(side=tk.BOTTOM, pady=10, padx=5, fill=tk.X)

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

    def setup_favorites_tab(self, parent):
        """Set up the favorites tab."""
        if not self.auth.current_user:
            ttk.Label(
                parent,
                text=_t("navigation.favorites.login_required", default="Please log in to use favorites"),
                font=("Arial", 12)
            ).pack(pady=50)
            return

        # Favorites list
        list_frame = ttk.LabelFrame(parent, text=_t("navigation.favorites.my_favorites", default="My Favorites"), padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Treeview for favorites
        columns = ("nickname", "location", "type")
        self.favorites_tree = ttk.Treeview(list_frame, columns=columns, show='headings')

        self.favorites_tree.heading("nickname", text=_t("navigation.favorites.nickname_header", default="Nickname"))
        self.favorites_tree.heading("location", text=_t("navigation.favorites.location_header", default="Location"))
        self.favorites_tree.heading("type", text=_t("navigation.favorites.type_header", default="Type"))

        self.favorites_tree.column("nickname", width=100)
        self.favorites_tree.column("location", width=150)
        self.favorites_tree.column("type", width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                  command=self.favorites_tree.yview)
        self.favorites_tree.configure(yscrollcommand=scrollbar.set)

        self.favorites_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(
            button_frame,
            text=_t("navigation.favorites.refresh_button", default="Refresh"),
            command=self.load_favorites
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text=_t("navigation.favorites.remove_button", default="Remove Selected"),
            command=self.remove_favorite
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text=_t("navigation.favorites.navigate_button", default="Navigate To"),
            command=self.navigate_to_favorite
        ).pack(side=tk.LEFT, padx=5)

        # Load favorites
        self.load_favorites()

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

    def load_favorites(self):
        """Load user's favorite locations."""
        if not self.auth.current_user:
            return

        user = self.auth.get_current_user()
        favorites = self.service.get_favorites(user['username'])

        # Clear existing items
        for item in self.favorites_tree.get_children():
            self.favorites_tree.delete(item)

        # Add favorites
        for fav in favorites:
            nickname = fav.get('nickname', 'N/A')
            location = fav.get('location_name', 'N/A')
            loc_type = fav['location_type']

            self.favorites_tree.insert(
                '',
                tk.END,
                values=(nickname, location, loc_type),
                tags=(fav['favorite_id'],)
            )

    def remove_favorite(self):
        """Remove selected favorite."""
        selection = self.favorites_tree.selection()
        if not selection:
            messagebox.showwarning(_t("navigation.dialogs.warning", default="Warning"), _t("navigation.warnings.select_favorite", default="Please select a favorite to remove."))
            return

        item = selection[0]
        tags = self.favorites_tree.item(item, 'tags')
        if tags:
            favorite_id = int(tags[0])

            if messagebox.askyesno(_t("navigation.dialogs.confirm", default="Confirm"), _t("navigation.dialogs.remove_favorite_confirm", default="Remove this favorite?")):
                self.service.remove_favorite(favorite_id)
                self.load_favorites()
                messagebox.showinfo(_t("navigation.dialogs.success", default="Success"), _t("navigation.messages.favorite_removed", default="Favorite removed!"))

    def navigate_to_favorite(self):
        """Navigate to selected favorite location."""
        selection = self.favorites_tree.selection()
        if not selection:
            messagebox.showwarning(_t("navigation.dialogs.warning", default="Warning"), _t("navigation.warnings.select_favorite_location", default="Please select a favorite location."))
            return

        item = selection[0]
        values = self.favorites_tree.item(item, 'values')
        location_name = values[1]

        # Search for the location
        buildings = self.service.search_buildings(location_name)
        if buildings:
            self.show_building_details(buildings[0])
            messagebox.showinfo(_t("navigation.dialogs.info", default="Info"), _t("navigation.messages.showing_details", default="Showing details for {location_name}").format(location_name=location_name))
        else:
            messagebox.showinfo(_t("navigation.dialogs.info", default="Info"), _t("navigation.messages.location_found_no_details", default="Location found but details not available."))

    def add_to_favorites(self):
        """Add the currently selected building to favorites."""
        if not self.auth.current_user:
            messagebox.showerror(_t("navigation.errors.error_title", default="Error"), _t("navigation.errors.login_required", default="Please log in to add favorites."))
            return

        if not self.selected_building:
            messagebox.showwarning(_t("navigation.dialogs.warning", default="Warning"), _t("navigation.warnings.no_building_selected", default="No building selected."))
            return

        # Create dialog for nickname
        dialog = tk.Toplevel(self.window)
        dialog.title(_t("navigation.messages.add_to_favorites_title", default="Add to Favorites"))
        dialog.geometry("400x150")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(
            dialog,
            text=_t("navigation.messages.add_to_favorites_text", default="Add '{building_name}' to favorites").format(building_name=self.selected_building['building_name']),
            font=("Arial", 10, "bold")
        ).pack(pady=10)

        ttk.Label(dialog, text=_t("navigation.messages.nickname_optional", default="Nickname (optional):")).pack(pady=5)
        nickname_entry = ttk.Entry(dialog, width=40)
        nickname_entry.pack(pady=5)
        nickname_entry.insert(0, self.selected_building['building_name'])

        def save_favorite():
            nickname = nickname_entry.get().strip()
            if not nickname:
                nickname = self.selected_building['building_name']

            try:
                user = self.auth.get_current_user()
                self.service.add_favorite(
                    user_id=user['username'],
                    location_type='building',
                    location_id=self.selected_building['building_id'],
                    nickname=nickname
                )
                messagebox.showinfo(_t("navigation.dialogs.success", default="Success"), _t("navigation.messages.building_added_to_favorites", default="Building added to favorites!"))
                dialog.destroy()
                # Refresh favorites if tab is visible
                self.load_favorites()
            except Exception as e:
                messagebox.showerror(_t("navigation.errors.error_title", default="Error"), _t("navigation.errors.failed_to_add_favorite", default="Failed to add favorite: {error}").format(error=str(e)))

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=_t("navigation.messages.add_button", default="Add"), command=save_favorite).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("navigation.messages.cancel_button", default="Cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

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

    def close_window(self):
        """Close the Campus Navigation GUI and return to main menu"""
        # Close the Toplevel window
        self.window.destroy()

    def run(self):
        """Run the GUI application."""
        if self.is_standalone:
            self.root.mainloop()


def main():
    """Main entry point for GUI."""
    app = NavigationGUI()
    app.run()


if __name__ == '__main__':
    main()
