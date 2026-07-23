import tkinter as tk
from tkinter import ttk, messagebox


class AccessibilityMixin:
    """Mixin for accessibility tools and medical accommodations."""

    def create_open_accessibility_tools(self):
        """Embed the Accessibility Tools GUI directly in the content frame."""
        try:
            from education_system.post_18.university_system.modules.domain.student_affairs.gui.accessibility_tools_gui import (
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
        """Embed the Medical Accommodation GUI directly in the content frame."""
        try:
            from education_system.post_18.university_system.modules.domain.health.gui.medical_accommodation import AccommodationGUI
            AccommodationGUI(self.content_frame, self.auth)
        except Exception as e:
            ttk.Label(self.content_frame, text=f"Medical Accommodations could not be loaded: {e}",
                      font=("Arial", 12)).grid(row=0, column=0, padx=20, pady=20)
