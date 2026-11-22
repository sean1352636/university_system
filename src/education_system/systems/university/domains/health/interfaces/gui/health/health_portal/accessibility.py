import tkinter as tk
from tkinter import ttk
from education_system.systems.university.domains.health.interfaces.gui.health._dialogs import (
    make_toplevel, messagebox,
)


class AccessibilityMixin:
    """Mixin for accessibility tools and medical accommodations."""

    def create_open_accessibility_tools(self):
        """Embed the Accessibility Tools GUI directly in the content frame."""
        try:
            from education_system.systems.university.domains.student_support.interfaces.gui.accessibility_tools_gui import (
                AccessibilityToolsGUI,
            )
            host = ttk.Frame(self.content_frame)
            host.grid(row=0, column=0, sticky="nsew")
            self.content_frame.grid_rowconfigure(0, weight=1)
            self.content_frame.grid_columnconfigure(0, weight=1)
            AccessibilityToolsGUI(self.root, self.auth, parent_container=host)
        except Exception as e:
            ttk.Label(self.content_frame,
                      text=f"Accessibility Tools could not be loaded: {e}",
                      font=("Arial", 12)).grid(row=0, column=0, padx=20, pady=20)

    def create_medical_accommodations(self):
        """The Disability & Accessibility portal, in the content frame.

        Medical Accommodations was merged into it on 2026-10-19: staff land
        on its Accommodations tab (the full tool, every menu), next to the
        students' requests and renewals; a student gets My Support. Access
        follows domain/disability/access, as before."""
        try:
            from education_system.systems.university.domains.student_support.interfaces.gui.disability.portal import (
                DisabilityPortal,
            )
            host = ttk.Frame(self.content_frame)
            host.grid(row=0, column=0, sticky="nsew")
            self.content_frame.grid_rowconfigure(0, weight=1)
            self.content_frame.grid_columnconfigure(0, weight=1)
            DisabilityPortal(host, self.auth, section="accommodations")
        except Exception as e:
            ttk.Label(self.content_frame, text=f"Medical Accommodations could not be loaded: {e}",
                      font=("Arial", 12)).grid(row=0, column=0, padx=20, pady=20)
