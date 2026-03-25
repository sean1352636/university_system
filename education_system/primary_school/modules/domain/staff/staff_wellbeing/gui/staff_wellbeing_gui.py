"""StaffWellbeingFrame GUI for the Primary School."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.staff.staff_wellbeing.services.staff_wellbeing_service import StaffWellbeingService


class StaffWellbeingFrame(tk.Frame):
    """GUI for managing staff wellbeing."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = StaffWellbeingService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Staff Wellbeing",
                 fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Tabs
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=5, pady=5)

        self._surveys_tab = tk.Frame(self._notebook)
        self._notebook.add(self._surveys_tab, text="Surveys")
        self._support_requests_tab = tk.Frame(self._notebook)
        self._notebook.add(self._support_requests_tab, text="Support Requests")
        self._dashboard_tab = tk.Frame(self._notebook)
        self._notebook.add(self._dashboard_tab, text="Dashboard")

        self._build_list_tab()

    def _build_list_tab(self):
        """Build the main list tab with treeview."""
        tab = self._notebook.tabs()[0]
        frame = self._notebook.nametowidget(tab)

        toolbar = tk.Frame(frame, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")
        tk.Button(toolbar, text="Refresh", command=self.refresh).pack(side="left", padx=3)

        self._tree = ttk.Treeview(frame, show="headings", selectmode="browse")
        self._tree.pack(fill="both", expand=True, padx=5, pady=5)

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(frame, textvariable=self._status_var, anchor="w",
                 bg="#ecf0f1", padx=10).pack(fill="x", side="bottom")

    def refresh(self):
        """Reload data."""
        try:
            records = self._service.list_all()
            self._status_var.set(f"{len(records)} record(s) loaded")
        except Exception as e:
            messagebox.showerror("Error", str(e))
