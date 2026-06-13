"""
Campus Navigation GUI Interface

Provides graphical interface for campus navigation with interactive map.
"""

from education_system.university_system.modules.domain.campus.campus_navigation.gui._imports import tk, ttk, NavigationService, get_auth, _t
from education_system.university_system.modules.domain.campus.campus_navigation.gui.map_canvas import MapCanvasMixin
from education_system.university_system.modules.domain.campus.campus_navigation.gui.tabs.directory import DirectoryTabMixin
from education_system.university_system.modules.domain.campus.campus_navigation.gui.tabs.route import RouteTabMixin
from education_system.university_system.modules.domain.campus.campus_navigation.gui.tabs.nearest import NearestTabMixin
from education_system.university_system.modules.domain.campus.campus_navigation.gui.tabs.favorites import FavoritesTabMixin


class NavigationGUI(
    MapCanvasMixin,
    DirectoryTabMixin,
    RouteTabMixin,
    NearestTabMixin,
    FavoritesTabMixin,
):
    """GUI interface for Campus Navigation."""

    def __init__(self, parent=None):
        """Initialize the Campus Navigation GUI."""
        self.service = NavigationService()
        self.auth = get_auth()
        if not self.auth or not getattr(self.auth, "current_user", None):
            try:
                from tkinter import messagebox
                messagebox.showerror(
                    "Login required",
                    "You must be logged in via the main GUI to use "
                    "Campus Navigation.",
                )
            except Exception:
                pass
            raise PermissionError(
                "Campus Navigation GUI requires an authenticated user")

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
    from education_system.university_system.modules.shared.gui.auth.launch_guard import (
        require_launcher_auth,
    )
    if require_launcher_auth("Campus Navigation GUI") is None:
        return
    app = NavigationGUI()
    app.run()


if __name__ == '__main__':
    main()
