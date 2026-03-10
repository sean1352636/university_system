"""T-Level Pathways GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.tlevel.services.tlevel_service import TLevelService


class TLevelFrame(tk.Frame):
    """T-Level Pathways management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = TLevelService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="T-Level Pathways",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_routes_tab()
        self._build_enrollments_tab()
        self._build_placement_logs_tab()
        

    def _build_routes_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Routes")
        cols = ("id", "route_name", "pathway", "glh_total",)
        self._tree_0 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_0.heading("id", text="ID")
        self._tree_0.column("id", width=40, anchor="center")
        self._tree_0.heading("route_name", text="Route")
        self._tree_0.column("route_name", width=180, anchor="center")
        self._tree_0.heading("pathway", text="Pathway")
        self._tree_0.column("pathway", width=120, anchor="center")
        self._tree_0.heading("glh_total", text="GLH")
        self._tree_0.column("glh_total", width=60, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_0.yview)
        self._tree_0.configure(yscrollcommand=vsb.set)
        self._tree_0.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_enrollments_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Enrollments")
        cols = ("id", "sid", "route_name", "placement_hours_completed", "status",)
        self._tree_1 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_1.heading("id", text="ID")
        self._tree_1.column("id", width=40, anchor="center")
        self._tree_1.heading("sid", text="Student")
        self._tree_1.column("sid", width=80, anchor="center")
        self._tree_1.heading("route_name", text="Route")
        self._tree_1.column("route_name", width=150, anchor="center")
        self._tree_1.heading("placement_hours_completed", text="Placement Hrs")
        self._tree_1.column("placement_hours_completed", width=80, anchor="center")
        self._tree_1.heading("status", text="Status")
        self._tree_1.column("status", width=80, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_1.yview)
        self._tree_1.configure(yscrollcommand=vsb.set)
        self._tree_1.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_placement_logs_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Placement Logs")
        cols = ("id", "enrollment_id", "log_date", "hours", "activity",)
        self._tree_2 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_2.heading("id", text="ID")
        self._tree_2.column("id", width=40, anchor="center")
        self._tree_2.heading("enrollment_id", text="Enroll")
        self._tree_2.column("enrollment_id", width=50, anchor="center")
        self._tree_2.heading("log_date", text="Date")
        self._tree_2.column("log_date", width=90, anchor="center")
        self._tree_2.heading("hours", text="Hours")
        self._tree_2.column("hours", width=50, anchor="center")
        self._tree_2.heading("activity", text="Activity")
        self._tree_2.column("activity", width=200, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_2.yview)
        self._tree_2.configure(yscrollcommand=vsb.set)
        self._tree_2.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")


    def _load_routes(self):
        self._tree_0.delete(*self._tree_0.get_children())

    def _load_enrollments(self):
        self._tree_1.delete(*self._tree_1.get_children())

    def _load_placement_logs(self):
        self._tree_2.delete(*self._tree_2.get_children())

    def refresh(self):
        self._load_routes()
        self._load_enrollments()
        self._load_placement_logs()

