"""Extracted function implementation."""

from .. import gui_setup_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def create_content_area(self, parent):
    """Create the main content area.

    Pre-8.117.20 wrapped in a ``LabelFrame "Content"`` with both
    horizontal and vertical scrollbars. The H scrollbar was a
    defensive layout choice that never paid off — the dashboard and
    workspace tabs always fit within the canvas width, so the bar
    consumed ~10px of vertical space + visual chrome for nothing.
    Reshaped to:

    - Plain Frame, no LabelFrame label.
    - Vertical scrollbar only. ``content_canvas.bbox`` width is
      ignored when configuring the scroll region so excess width
      can't accidentally turn it back on.
    """
    outer_frame = ttk.Frame(parent, padding=0)
    outer_frame.grid(row=1, column=1, sticky="nsew")
    outer_frame.columnconfigure(0, weight=1)
    outer_frame.rowconfigure(0, weight=1)

    self.content_canvas = tk.Canvas(outer_frame, highlightthickness=0)
    self.content_canvas.grid(row=0, column=0, sticky="nsew")

    v_scrollbar = ttk.Scrollbar(outer_frame, orient="vertical",
                                command=self.content_canvas.yview)
    v_scrollbar.grid(row=0, column=1, sticky="ns")
    self.content_canvas.configure(yscrollcommand=v_scrollbar.set)

    # Inner frame for actual content
    self.content_frame = ttk.Frame(self.content_canvas, padding="10")
    self.content_window = self.content_canvas.create_window((0, 0), window=self.content_frame, anchor="nw")

    # Configure scroll region when content changes
    def configure_scroll_region(event):
        self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))

    self.content_frame.bind("<Configure>", configure_scroll_region)

    # Make canvas resize with window
    def configure_canvas_width(event):
        self.content_canvas.itemconfig(self.content_window, width=event.width)

    self.content_canvas.bind("<Configure>", configure_canvas_width)

    # Enable mousewheel scrolling
    def on_mousewheel(event):
        self.content_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    self.content_canvas.bind("<Enter>", lambda e: self.content_canvas.bind_all("<MouseWheel>", on_mousewheel))
    self.content_canvas.bind("<Leave>", lambda e: self.content_canvas.unbind_all("<MouseWheel>"))

    self.content_frame.columnconfigure(0, weight=1)
    self.content_frame.rowconfigure(0, weight=1)

    # Ensure parent properly configures this cell
    parent.rowconfigure(1, weight=1)
    parent.columnconfigure(1, weight=1)
