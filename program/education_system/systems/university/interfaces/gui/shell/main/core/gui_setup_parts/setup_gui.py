"""Extracted function implementation."""

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def setup_gui(self):
    """Setup the unified GUI interface.

    Three-row layout:
      row 0 — header (control buttons, no LabelFrame wrapper)
      row 1 — navigation panel + content area (expanding)
      row 2 — status bar (fixed thin)

    Pre-8.117.20 the status + current-user labels lived inside the
    header LabelFrame at the top. Status-at-the-top breaks every
    desktop convention; moved to a thin row at the bottom in this
    version. See the 8.117.16 layout review for the rationale."""
    # Main frame
    main_frame = ttk.Frame(self.root, padding="10")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    # Configure grid weights
    self.root.columnconfigure(0, weight=1)
    self.root.rowconfigure(0, weight=1)
    main_frame.columnconfigure(0, weight=0)  # Navigation column - fixed width
    main_frame.columnconfigure(1, weight=1)  # Content column - expands
    main_frame.rowconfigure(1, weight=1)     # Row 1 (nav + content) - expands vertically

    # Header with control buttons
    self.create_header(main_frame)

    # Left panel - Navigation buttons (like AuthenticationGUI)
    self.create_navigation_panel(main_frame)

    # Right panel - Content area
    self.create_content_area(main_frame)

    # Status bar at the bottom (status / user / system / version)
    self.create_status_bar(main_frame)

    # Show welcome message initially
    self.show_welcome()
