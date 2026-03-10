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

    def open_medical_accommodation_gui(self):
        """Open Medical Accommodation GUI"""
        try:
            from education_system.university_system.modules.domain.health.gui.medical_accommodation_gui import AccommodationGUI

            accommodation_window = tk.Toplevel(self.root)
            accommodation_window.title("Medical Accommodation Management System")
            accommodation_window.geometry("1200x800")
            accommodation_window.minsize(1000, 700)

            app = AccommodationGUI(accommodation_window, self.auth)
        except ImportError as e:
            messagebox.showerror("Error", f"Medical Accommodation GUI not available: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Error opening Medical Accommodations: {e}")

    def create_medical_accommodations(self):
        """Create interface for medical accommodations information"""
        title = ttk.Label(self.content_frame, text="Medical Accommodations",
                         style='Title.TLabel')
        title.grid(row=0, column=0, pady=10)

        info_frame = ttk.Frame(self.content_frame)
        info_frame.grid(row=1, column=0, pady=20, padx=20, sticky=(tk.W, tk.E))

        info_text = """Medical Accommodations Information:

Medical accommodations are integrated with the Accessibility Tools system.
You can access all accommodation features through the Accessibility Tools
interface, which includes:

\u2022 Medical accommodation requests
\u2022 Disability documentation management
\u2022 Exam accommodations
\u2022 Assistive technology requests
\u2022 Alternative materials
\u2022 Accessibility profiles

For health-specific accommodations, the Health Portal works in conjunction
with the Accessibility Tools system to ensure proper coordination of care
and support services.

To manage medical accommodations, please use the "Open Accessibility Tools"
button in this section."""

        info_label = ttk.Label(info_frame, text=info_text, justify=tk.LEFT, wraplength=800)
        info_label.pack(pady=10)

        ttk.Button(info_frame, text="Open Medical Accommodation System",
                  command=self.open_medical_accommodation_gui,
                  style='Accent.TButton').pack(pady=20)
