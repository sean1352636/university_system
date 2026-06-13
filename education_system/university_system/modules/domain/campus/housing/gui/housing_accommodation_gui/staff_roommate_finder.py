"""Staff-side roommate finder.

The existing ``roommate_finder.RoommateFinderGUI`` is wired only into
the student menu. This thin wrapper opens the same widget from the
admin sidebar so staff can run match suggestions when placing
applicants (e.g. to fill the last spot in a 4-person flat).
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.modules.domain.campus.housing.gui.housing_accommodation_gui import (
    roommate_finder,
)

logger = logging.getLogger(__name__)


def show_staff_roommate_finder(gui_instance) -> None:
    gui_instance.clear_content()
    parent = gui_instance.content_frame

    ttk.Label(parent, text="Roommate Finder (staff view)",
              font=("Arial", 14, "bold")).pack(anchor="w", padx=8,
                                                pady=(8, 4))
    ttk.Label(parent,
              text=("Run match suggestions for any applicant or current "
                    "resident. The widget is the same one residents use "
                    "from their portal."),
              wraplength=820, foreground="#555").pack(anchor="w", padx=8,
                                                        pady=(0, 8))

    container = ttk.Frame(parent)
    container.pack(fill="both", expand=True, padx=8, pady=4)

    try:
        roommate_finder.RoommateFinderGUI(
            parent=gui_instance.root,
            auth=gui_instance.auth,
            container=container)
    except Exception as e:
        logger.exception("Could not start roommate finder for staff")
        messagebox.showerror("Roommate finder",
                              f"Could not open:\n\n{e}",
                              parent=gui_instance.root)
