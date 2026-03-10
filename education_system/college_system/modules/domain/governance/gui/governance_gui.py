"""Governance & Board GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.governance.services.governance_service import GovernanceService


class GovernanceFrame(tk.Frame):
    """Governance & Board management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = GovernanceService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Governance & Board",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_governors_tab()
        self._build_meetings_tab()
        self._build_actions_tab()
        self._build_strategic_plan_tab()
        

    def _build_governors_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Governors")
        cols = ("id", "first_name", "last_name", "governor_type", "role_on_board", "status",)
        self._tree_0 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_0.heading("id", text="ID")
        self._tree_0.column("id", width=40, anchor="center")
        self._tree_0.heading("first_name", text="First Name")
        self._tree_0.column("first_name", width=100, anchor="center")
        self._tree_0.heading("last_name", text="Last Name")
        self._tree_0.column("last_name", width=100, anchor="center")
        self._tree_0.heading("governor_type", text="Type")
        self._tree_0.column("governor_type", width=100, anchor="center")
        self._tree_0.heading("role_on_board", text="Role")
        self._tree_0.column("role_on_board", width=120, anchor="center")
        self._tree_0.heading("status", text="Status")
        self._tree_0.column("status", width=70, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_0.yview)
        self._tree_0.configure(yscrollcommand=vsb.set)
        self._tree_0.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_meetings_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Meetings")
        cols = ("id", "meeting_date", "meeting_type", "status",)
        self._tree_1 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_1.heading("id", text="ID")
        self._tree_1.column("id", width=40, anchor="center")
        self._tree_1.heading("meeting_date", text="Date")
        self._tree_1.column("meeting_date", width=90, anchor="center")
        self._tree_1.heading("meeting_type", text="Type")
        self._tree_1.column("meeting_type", width=100, anchor="center")
        self._tree_1.heading("status", text="Status")
        self._tree_1.column("status", width=80, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_1.yview)
        self._tree_1.configure(yscrollcommand=vsb.set)
        self._tree_1.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_actions_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Actions")
        cols = ("id", "action_description", "due_date", "status",)
        self._tree_2 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_2.heading("id", text="ID")
        self._tree_2.column("id", width=40, anchor="center")
        self._tree_2.heading("action_description", text="Action")
        self._tree_2.column("action_description", width=250, anchor="center")
        self._tree_2.heading("due_date", text="Due")
        self._tree_2.column("due_date", width=90, anchor="center")
        self._tree_2.heading("status", text="Status")
        self._tree_2.column("status", width=80, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_2.yview)
        self._tree_2.configure(yscrollcommand=vsb.set)
        self._tree_2.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_strategic_plan_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Strategic Plan")
        cols = ("id", "title", "priority_area", "status",)
        self._tree_3 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_3.heading("id", text="ID")
        self._tree_3.column("id", width=40, anchor="center")
        self._tree_3.heading("title", text="Title")
        self._tree_3.column("title", width=200, anchor="center")
        self._tree_3.heading("priority_area", text="Priority")
        self._tree_3.column("priority_area", width=120, anchor="center")
        self._tree_3.heading("status", text="Status")
        self._tree_3.column("status", width=80, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_3.yview)
        self._tree_3.configure(yscrollcommand=vsb.set)
        self._tree_3.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")


    def _load_governors(self):
        self._tree_0.delete(*self._tree_0.get_children())

    def _load_meetings(self):
        self._tree_1.delete(*self._tree_1.get_children())

    def _load_actions(self):
        self._tree_2.delete(*self._tree_2.get_children())

    def _load_strategic_plan(self):
        self._tree_3.delete(*self._tree_3.get_children())

    def refresh(self):
        self._load_governors()
        self._load_meetings()
        self._load_actions()
        self._load_strategic_plan()

