import tkinter as tk
from tkinter import ttk
from tkinter.simpledialog import Dialog


class AboutDialog(Dialog):
    def __init__(self, parent):
        super().__init__(parent, "About Trip Management System")

    def body(self, master):
        """Create the dialog body"""
        # Logo/Icon placeholder
        ttk.Label(master, text="\U0001f392", font=('Arial', 48)).pack(pady=10)

        # Title
        ttk.Label(master, text="Trip Management System",
                 font=('Arial', 16, 'bold')).pack(pady=5)

        # Version info
        ttk.Label(master, text="Version 2.0 - GUI Edition").pack(pady=2)

        # Description
        description = """
A comprehensive system for managing educational trips and excursions.

Features:
\u2022 Trip creation and management
\u2022 Student registration and tracking
\u2022 Staff assignment and coordination
\u2022 Expense tracking and reporting
\u2022 Calendar integration
\u2022 Comprehensive reporting system

Built with backwards compatibility to the original command-line system.
        """

        ttk.Label(master, text=description, justify=tk.LEFT).pack(pady=20, padx=20)

        # Copyright
        ttk.Label(master, text="\u00a9 2024 Educational Trip Management System",
                 font=('Arial', 8)).pack(pady=5)

        return None

    def buttonbox(self):
        """Create button box"""
        box = ttk.Frame(self)
        ttk.Button(box, text="Close", command=self.ok).pack()
        box.pack(pady=10)
