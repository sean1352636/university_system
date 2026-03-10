"""Value-Added Analysis GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.value_added.services.value_added_service import ValueAddedService


class ValueAddedFrame(tk.Frame):
    """Value-Added Analysis management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = ValueAddedService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Value-Added Analysis",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_baselines_tab()
        self._build_predictions_tab()
        self._build_analysis_tab()
        

    def _build_baselines_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Baselines")
        cols = ("id", "student_id", "gcse_average", "baseline_score",)
        self._tree_0 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_0.heading("id", text="ID")
        self._tree_0.column("id", width=40, anchor="center")
        self._tree_0.heading("student_id", text="Student")
        self._tree_0.column("student_id", width=60, anchor="center")
        self._tree_0.heading("gcse_average", text="GCSE Avg")
        self._tree_0.column("gcse_average", width=70, anchor="center")
        self._tree_0.heading("baseline_score", text="Baseline")
        self._tree_0.column("baseline_score", width=70, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_0.yview)
        self._tree_0.configure(yscrollcommand=vsb.set)
        self._tree_0.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_predictions_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Predictions")
        cols = ("id", "sid", "course_title", "predicted_grade", "actual_grade", "value_added_score",)
        self._tree_1 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_1.heading("id", text="ID")
        self._tree_1.column("id", width=40, anchor="center")
        self._tree_1.heading("sid", text="Student")
        self._tree_1.column("sid", width=80, anchor="center")
        self._tree_1.heading("course_title", text="Course")
        self._tree_1.column("course_title", width=150, anchor="center")
        self._tree_1.heading("predicted_grade", text="Predicted")
        self._tree_1.column("predicted_grade", width=70, anchor="center")
        self._tree_1.heading("actual_grade", text="Actual")
        self._tree_1.column("actual_grade", width=60, anchor="center")
        self._tree_1.heading("value_added_score", text="VA")
        self._tree_1.column("value_added_score", width=50, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_1.yview)
        self._tree_1.configure(yscrollcommand=vsb.set)
        self._tree_1.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_analysis_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Analysis")
        self._analysis_frame = tk.Frame(tab, bg="#ecf0f1")
        self._analysis_frame.pack(fill="both", expand=True)
        tk.Label(self._analysis_frame, text="Analysis view",
                 font=("Helvetica", 12), bg="#ecf0f1").pack(pady=20)


    def _load_baselines(self):
        self._tree_0.delete(*self._tree_0.get_children())

    def _load_predictions(self):
        self._tree_1.delete(*self._tree_1.get_children())

    def refresh(self):
        self._load_baselines()
        self._load_predictions()

