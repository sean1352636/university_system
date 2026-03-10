"""Individual Learning Plans GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.ilp.services.ilp_service import ILPService


class ILPFrame(tk.Frame):
    """Individual Learning Plans management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = ILPService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Individual Learning Plans",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_plans_tab()
        self._build_targets_tab()
        self._build_reviews_tab()
        

    def _build_plans_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Plans")
        cols = ("id", "student_id", "plan_type", "status", "review_frequency",)
        self._tree_0 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_0.heading("id", text="ID")
        self._tree_0.column("id", width=40, anchor="center")
        self._tree_0.heading("student_id", text="Student")
        self._tree_0.column("student_id", width=60, anchor="center")
        self._tree_0.heading("plan_type", text="Type")
        self._tree_0.column("plan_type", width=80, anchor="center")
        self._tree_0.heading("status", text="Status")
        self._tree_0.column("status", width=80, anchor="center")
        self._tree_0.heading("review_frequency", text="Review Freq")
        self._tree_0.column("review_frequency", width=100, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_0.yview)
        self._tree_0.configure(yscrollcommand=vsb.set)
        self._tree_0.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_targets_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Targets")
        cols = ("id", "plan_id", "subject_area", "target_description", "status",)
        self._tree_1 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_1.heading("id", text="ID")
        self._tree_1.column("id", width=40, anchor="center")
        self._tree_1.heading("plan_id", text="Plan")
        self._tree_1.column("plan_id", width=50, anchor="center")
        self._tree_1.heading("subject_area", text="Subject")
        self._tree_1.column("subject_area", width=100, anchor="center")
        self._tree_1.heading("target_description", text="Target")
        self._tree_1.column("target_description", width=200, anchor="center")
        self._tree_1.heading("status", text="Status")
        self._tree_1.column("status", width=80, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_1.yview)
        self._tree_1.configure(yscrollcommand=vsb.set)
        self._tree_1.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_reviews_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Reviews")
        cols = ("id", "plan_id", "review_date", "summary",)
        self._tree_2 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_2.heading("id", text="ID")
        self._tree_2.column("id", width=40, anchor="center")
        self._tree_2.heading("plan_id", text="Plan")
        self._tree_2.column("plan_id", width=50, anchor="center")
        self._tree_2.heading("review_date", text="Date")
        self._tree_2.column("review_date", width=90, anchor="center")
        self._tree_2.heading("summary", text="Summary")
        self._tree_2.column("summary", width=250, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_2.yview)
        self._tree_2.configure(yscrollcommand=vsb.set)
        self._tree_2.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")


    def _load_plans(self):
        self._tree_0.delete(*self._tree_0.get_children())

    def _load_targets(self):
        self._tree_1.delete(*self._tree_1.get_children())

    def _load_reviews(self):
        self._tree_2.delete(*self._tree_2.get_children())

    def refresh(self):
        self._load_plans()
        self._load_targets()
        self._load_reviews()

