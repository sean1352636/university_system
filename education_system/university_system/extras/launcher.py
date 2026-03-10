#!/usr/bin/env python3
"""
Extras & Tools Launcher GUI
A comprehensive launcher for games, utilities, and mini-projects in the extras module.

Part of the University Management System.
Location: university_system/extras/
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import subprocess
import sys
from pathlib import Path


class ProgramLauncher:
    def __init__(self, root, standalone=True):
        """
        Initialize the Program Launcher.

        Args:
            root: Tk root or Toplevel window
            standalone: If True, this is the main window. If False, it's a child window.
        """
        self.root = root
        self.standalone = standalone
        self.root.title("Extras & Tools Launcher")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)

        # Base directory
        self.base_dir = Path(__file__).parent

        # Store running processes
        self.running_processes = []

        # Configure style
        self.setup_style()

        # Create main layout
        self.setup_gui()

        # Load programs
        self.load_programs()

    def setup_style(self):
        """Configure ttk styles to match university system"""
        self.style = ttk.Style()
        self.style.theme_use('clam')

    def setup_gui(self):
        """Setup the GUI interface matching university system layout"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Header
        self.create_header(main_frame)

        # Left panel - Navigation/Categories
        self.create_navigation_panel(main_frame)

        # Right panel - Content area
        self.create_content_area(main_frame)

        # Show welcome message
        self.show_welcome()

    def create_header(self, parent):
        """Create header with title and controls"""
        header_frame = ttk.LabelFrame(parent, text="Extras & Tools Launcher", padding="10")
        header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        # Title and description
        ttk.Label(header_frame, text="Launch games, utilities, and mini-projects",
                  font=('Arial', 11)).grid(row=0, column=0, sticky=tk.W)

        # Status label
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(header_frame, text="Status:").grid(row=0, column=1, sticky=tk.E, padx=(20, 5))
        ttk.Label(header_frame, textvariable=self.status_var).grid(row=0, column=2, sticky=tk.W)

        # Close button
        ttk.Button(header_frame, text="Close", command=self.close_launcher).grid(row=0, column=3, padx=(20, 0))

        header_frame.columnconfigure(0, weight=1)

    def create_navigation_panel(self, parent):
        """Create navigation panel with category list"""
        nav_frame = ttk.LabelFrame(parent, text="Categories", padding="5")
        nav_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))

        # Simple frame for buttons (no canvas needed for small number of categories)
        self.nav_buttons_frame = ttk.Frame(nav_frame)
        self.nav_buttons_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def create_content_area(self, parent):
        """Create the main content area for displaying programs"""
        self.content_frame = ttk.LabelFrame(parent, text="Programs", padding="10")
        self.content_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(0, weight=1)

        # Canvas + scrollbar for programs
        self.content_canvas = tk.Canvas(self.content_frame, highlightthickness=0, bg='#f0f0f0')
        scrollbar_y = ttk.Scrollbar(self.content_frame, orient="vertical", command=self.content_canvas.yview)
        scrollbar_x = ttk.Scrollbar(self.content_frame, orient="horizontal", command=self.content_canvas.xview)

        self.programs_frame = ttk.Frame(self.content_canvas)

        # Create window in canvas
        self.canvas_window = self.content_canvas.create_window((0, 0), window=self.programs_frame, anchor="nw")

        self.content_canvas.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        # Grid layout
        self.content_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar_y.grid(row=0, column=1, sticky=(tk.N, tk.S))
        scrollbar_x.grid(row=1, column=0, sticky=(tk.W, tk.E))

        # Bind events for scroll region and canvas width
        self.programs_frame.bind("<Configure>", self._on_frame_configure)
        self.content_canvas.bind("<Configure>", self._on_canvas_configure)

        # Mousewheel scrolling (cross-platform)
        self.content_canvas.bind('<Enter>', self._bind_mousewheel)
        self.content_canvas.bind('<Leave>', self._unbind_mousewheel)

    def _on_frame_configure(self, event):
        """Update scroll region when frame size changes"""
        self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        """Update inner frame width to match canvas"""
        # Make the inner frame at least as wide as the canvas
        canvas_width = event.width
        self.content_canvas.itemconfig(self.canvas_window, width=canvas_width)

    def _bind_mousewheel(self, event):
        """Bind mousewheel events"""
        # Windows and MacOS
        self.content_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        # Linux
        self.content_canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.content_canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

    def _unbind_mousewheel(self, event):
        """Unbind mousewheel events"""
        self.content_canvas.unbind_all("<MouseWheel>")
        self.content_canvas.unbind_all("<Button-4>")
        self.content_canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        """Handle mousewheel on Windows/MacOS"""
        self.content_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_linux(self, event):
        """Handle mousewheel on Linux"""
        if event.num == 4:
            self.content_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.content_canvas.yview_scroll(1, "units")

    def show_welcome(self):
        """Show welcome message in content area"""
        self.clear_content()
        self.content_frame.configure(text="Programs")

        welcome_frame = ttk.Frame(self.programs_frame)
        welcome_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ttk.Label(welcome_frame, text="Welcome to Extras & Tools!",
                  font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        welcome_text = """Select a category from the left panel to browse available programs.

Available categories:
• Standalone Games - Quick Python games
• Game Projects - Larger game projects with assets
• Standalone Utilities - Calculator, countdown, network tools
• Python Utility Projects - Various utility applications
• 91 Mini Projects - Collection of Python mini-projects

Click on any program button to launch it in a new window."""

        ttk.Label(welcome_frame, text=welcome_text, justify=tk.LEFT,
                  wraplength=500).pack(pady=10)

        # Update the canvas
        self._update_canvas()

    def clear_content(self):
        """Clear the content area"""
        for widget in self.programs_frame.winfo_children():
            widget.destroy()

    def _update_canvas(self):
        """Force canvas to update its scroll region"""
        self.programs_frame.update_idletasks()
        self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))
        self.content_canvas.yview_moveto(0)  # Scroll to top

    def load_programs(self):
        """Load all program categories"""
        # Define categories and their sources
        self.categories = {
            "Standalone Games": {
                "path": self.base_dir / "games" / "standalone-games",
                "type": "files",
                "pattern": "*.py"
            },
            "Game Projects": {
                "path": self.base_dir / "games",
                "type": "folders",
                "exclude": ["standalone-games"]
            },
            "Standalone Utilities": {
                "path": self.base_dir / "standalone-utilities",
                "type": "files",
                "pattern": "*.py"
            },
            "Python Utility Projects": {
                "path": self.base_dir / "python-utilities",
                "type": "folders"
            },
            "91 Mini Projects": {
                "path": self.base_dir / "91_Python_Mini_Projects-main",
                "type": "folders"
            }
        }

        # Create category buttons in navigation panel
        for category_name, config in self.categories.items():
            if config["path"].exists():
                self.create_category_button(category_name, config)

    def create_category_button(self, category_name, config):
        """Create a button for a category in the navigation panel"""
        btn = ttk.Button(
            self.nav_buttons_frame,
            text=category_name,
            command=lambda cn=category_name, cfg=config: self.show_category(cn, cfg)
        )
        btn.pack(fill=tk.X, pady=3, padx=2)

    def show_category(self, category_name, config):
        """Show programs from a specific category in the content area"""
        self.clear_content()
        self.content_frame.configure(text=f"Programs - {category_name}")
        self.status_var.set(f"Loading {category_name}...")
        self.root.update()

        path = config["path"]

        if config["type"] == "files":
            self.load_file_items(path, config.get("pattern", "*.py"))
        elif config["type"] == "folders":
            self.load_folder_items(path, config.get("exclude", []))

        # Update canvas after loading content
        self._update_canvas()
        self.status_var.set(f"Showing {category_name}")

    def load_file_items(self, path, pattern):
        """Load individual Python files as program buttons"""
        files = sorted(path.glob(pattern))

        if not files:
            ttk.Label(self.programs_frame, text="No programs found in this category.",
                      font=('Arial', 10, 'italic')).pack(pady=20)
            return

        # Create a container frame for the grid
        grid_frame = ttk.Frame(self.programs_frame)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create grid of buttons
        row = 0
        col = 0
        max_cols = 3

        for file_path in files:
            program_name = file_path.stem.replace('_', ' ').title()

            btn = ttk.Button(
                grid_frame,
                text=program_name,
                command=lambda p=file_path: self.run_program(p)
            )
            btn.grid(row=row, column=col, padx=5, pady=5, sticky='ew')

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        # Configure column weights
        for i in range(max_cols):
            grid_frame.columnconfigure(i, weight=1)

    def load_folder_items(self, path, exclude=None):
        """Load folder-based projects as program buttons"""
        if exclude is None:
            exclude = []

        folders = [f for f in sorted(path.iterdir())
                   if f.is_dir() and f.name not in exclude and not f.name.startswith('.')]

        if not folders:
            ttk.Label(self.programs_frame, text="No projects found in this category.",
                      font=('Arial', 10, 'italic')).pack(pady=20)
            return

        # Create a container frame for the grid
        grid_frame = ttk.Frame(self.programs_frame)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create grid of buttons
        row = 0
        col = 0
        max_cols = 3
        items_added = 0

        for folder in folders:
            entry_point = self.find_entry_point(folder)

            if not entry_point:
                continue

            program_name = folder.name.replace('_', ' ').replace('-', ' ').title()

            btn = ttk.Button(
                grid_frame,
                text=program_name,
                command=lambda p=entry_point: self.run_program(p)
            )
            btn.grid(row=row, column=col, padx=5, pady=5, sticky='ew')
            items_added += 1

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        # Configure column weights
        for i in range(max_cols):
            grid_frame.columnconfigure(i, weight=1)

        if items_added == 0:
            grid_frame.destroy()
            ttk.Label(self.programs_frame, text="No launchable projects found in this category.",
                      font=('Arial', 10, 'italic')).pack(pady=20)

    def find_entry_point(self, folder):
        """Find the main entry point for a project"""
        entry_names = ['main.py', 'app.py', 'run.py', '__main__.py', 'game.py', 'start.py']

        for name in entry_names:
            entry = folder / name
            if entry.exists():
                return entry

        # If no standard entry point, find first .py file
        py_files = list(folder.glob('*.py'))
        if py_files:
            # Sort to get consistent results
            py_files.sort()
            return py_files[0]

        return None

    def run_program(self, program_path):
        """Run a program in a new process"""
        try:
            program_path = Path(program_path)

            # Update status
            self.status_var.set(f"Launching {program_path.name}...")
            self.root.update()

            # Change to program directory
            cwd = program_path.parent

            # Launch program
            if sys.platform == "win32":
                process = subprocess.Popen(
                    [sys.executable, str(program_path)],
                    cwd=str(cwd),
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                env = os.environ.copy()
                env['DISPLAY'] = os.environ.get('DISPLAY', ':0')
                process = subprocess.Popen(
                    [sys.executable, str(program_path)],
                    cwd=str(cwd),
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )

            self.running_processes.append(process)
            self.status_var.set(f"Launched {program_path.stem}")

        except Exception as e:
            messagebox.showerror("Launch Error",
                                 f"Failed to launch {program_path.name}:\n{str(e)}")
            self.status_var.set(f"Failed to launch {program_path.name}")

    def close_launcher(self):
        """Close the launcher window"""
        if self.standalone:
            if messagebox.askokcancel("Quit", "Do you want to close the launcher?"):
                self.cleanup()
                self.root.destroy()
        else:
            self.cleanup()
            self.root.destroy()

    def cleanup(self):
        """Cleanup running processes"""
        for process in self.running_processes:
            if process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    pass


def main():
    """Launch the Program Launcher as a standalone application."""
    root = tk.Tk()
    app = ProgramLauncher(root, standalone=True)
    root.protocol("WM_DELETE_WINDOW", app.close_launcher)
    root.mainloop()


def launch_as_toplevel(parent_window):
    """
    Launch the Program Launcher as a child window (Toplevel) of another Tk window.

    Args:
        parent_window: The parent Tk window

    Returns:
        ProgramLauncher: The launcher instance
    """
    toplevel = tk.Toplevel(parent_window)
    app = ProgramLauncher(toplevel, standalone=False)
    toplevel.protocol("WM_DELETE_WINDOW", app.close_launcher)
    return app


if __name__ == "__main__":
    main()
