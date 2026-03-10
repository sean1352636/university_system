"""Apprenticeships GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.apprenticeships.services.apprenticeships_service import ApprenticeshipService


class ApprenticeshipFrame(tk.Frame):
    """Apprenticeships management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = ApprenticeshipService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Apprenticeships",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_standards_tab()
        self._build_enrollments_tab()
        self._build_otj_log_tab()
        self._build_reviews_tab()
        

    def _build_standards_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Standards")
        cols = ("id", "standard_name", "level", "sector",)
        self._tree_0 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_0.heading("id", text="ID")
        self._tree_0.column("id", width=40, anchor="center")
        self._tree_0.heading("standard_name", text="Standard")
        self._tree_0.column("standard_name", width=200, anchor="center")
        self._tree_0.heading("level", text="Level")
        self._tree_0.column("level", width=50, anchor="center")
        self._tree_0.heading("sector", text="Sector")
        self._tree_0.column("sector", width=120, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_0.yview)
        self._tree_0.configure(yscrollcommand=vsb.set)
        self._tree_0.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_enrollments_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Enrollments")
        cols = ("id", "sid", "standard_name", "employer_name", "otj_hours_completed",)
        self._tree_1 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_1.heading("id", text="ID")
        self._tree_1.column("id", width=40, anchor="center")
        self._tree_1.heading("sid", text="Student")
        self._tree_1.column("sid", width=80, anchor="center")
        self._tree_1.heading("standard_name", text="Standard")
        self._tree_1.column("standard_name", width=150, anchor="center")
        self._tree_1.heading("employer_name", text="Employer")
        self._tree_1.column("employer_name", width=120, anchor="center")
        self._tree_1.heading("otj_hours_completed", text="OTJ Hrs")
        self._tree_1.column("otj_hours_completed", width=60, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_1.yview)
        self._tree_1.configure(yscrollcommand=vsb.set)
        self._tree_1.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_otj_log_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="OTJ Log")
        cols = ("id", "log_date", "hours", "activity_type", "description",)
        self._tree_2 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_2.heading("id", text="ID")
        self._tree_2.column("id", width=40, anchor="center")
        self._tree_2.heading("log_date", text="Date")
        self._tree_2.column("log_date", width=90, anchor="center")
        self._tree_2.heading("hours", text="Hours")
        self._tree_2.column("hours", width=50, anchor="center")
        self._tree_2.heading("activity_type", text="Type")
        self._tree_2.column("activity_type", width=100, anchor="center")
        self._tree_2.heading("description", text="Description")
        self._tree_2.column("description", width=200, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_2.yview)
        self._tree_2.configure(yscrollcommand=vsb.set)
        self._tree_2.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_reviews_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Reviews")
        cols = ("id", "review_date", "progress_summary",)
        self._tree_3 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_3.heading("id", text="ID")
        self._tree_3.column("id", width=40, anchor="center")
        self._tree_3.heading("review_date", text="Date")
        self._tree_3.column("review_date", width=90, anchor="center")
        self._tree_3.heading("progress_summary", text="Summary")
        self._tree_3.column("progress_summary", width=250, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_3.yview)
        self._tree_3.configure(yscrollcommand=vsb.set)
        self._tree_3.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")


    def _load_standards(self):
        self._tree_0.delete(*self._tree_0.get_children())

    def _load_enrollments(self):
        self._tree_1.delete(*self._tree_1.get_children())

    def _load_otj_log(self):
        self._tree_2.delete(*self._tree_2.get_children())

    def _load_reviews(self):
        self._tree_3.delete(*self._tree_3.get_children())

    def refresh(self):
        self._load_standards()
        self._load_enrollments()
        self._load_otj_log()
        self._load_reviews()

