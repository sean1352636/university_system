import tkinter as tk
from tkinter import ttk, messagebox


class AccessibilityMixin:
    """Mixin for accessibility tools and medical accommodations."""

    def create_open_accessibility_tools(self):
        """Create interface for opening Accessibility Tools GUI"""
        title = ttk.Label(self.content_frame, text="Accessibility & Accommodation Tools",
                         style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)

        launch_frame = ttk.Frame(self.content_frame)
        launch_frame.grid(row=1, column=0, pady=20)

        ttk.Button(launch_frame, text="Open Accessibility Tools",
                  command=self.open_accessibility_tools_gui, style='Accent.TButton').pack(pady=10)

        info_text = """The Accessibility & Accommodation Tools system allows you to:

\u2022 Manage accessibility profiles for students
\u2022 Submit and review accommodation requests
\u2022 Configure exam accommodations (extended time, separate room, etc.)
\u2022 Request assistive technology
\u2022 Track alternative material formats
\u2022 Configure personal accessibility settings

This comprehensive system ensures that all students have equal access
to educational opportunities and resources.

Click the button above to open the Accessibility Tools interface."""

        info_label = ttk.Label(self.content_frame, text=info_text, justify=tk.LEFT, wraplength=800)
        info_label.grid(row=2, column=0, pady=10, padx=20)

    def open_accessibility_tools_gui(self):
        """Open Accessibility Tools GUI"""
        try:
            from education_system.university_system.modules.domain.student_affairs.gui.accessibility_tools_gui import (
                launch_accessibility_tools_gui
            )
            launch_accessibility_tools_gui(self.root, self.auth)
        except ImportError as e:
            messagebox.showerror("Error", f"Accessibility Tools GUI not available: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Error opening Accessibility Tools: {e}")

    def create_medical_accommodations(self):
        """Embed the Medical Accommodation GUI directly in the content frame."""
        try:
            from education_system.university_system.modules.domain.health.gui.health_portal.medical_accommodation import AccommodationGUI
            AccommodationGUI(self.content_frame, self.auth)
        except Exception as e:
            ttk.Label(self.content_frame, text=f"Medical Accommodations could not be loaded: {e}",
                      font=("Arial", 12)).grid(row=0, column=0, padx=20, pady=20)
