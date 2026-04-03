"""Value-Added Analysis GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.core.i18n import t
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
        tk.Label(header, text=t("value_added.management"),
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_baselines_tab()
        self._build_predictions_tab()
        self._build_analysis_tab()


    def _build_baselines_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("value_added.baseline"))

        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", pady=(0, 5))
        ttk.Button(toolbar, text="Export CSV", command=self._export_baselines_csv).pack(side="left", padx=4)

        cols = ("id", "student_id", "gcse_average", "baseline_score",)
        self._tree_0 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_0.heading("id", text=t("common.id"))
        self._tree_0.column("id", width=40, anchor="center")
        self._tree_0.heading("student_id", text=t("common.student_name"))
        self._tree_0.column("student_id", width=60, anchor="center")
        self._tree_0.heading("gcse_average", text=t("common.average"))
        self._tree_0.column("gcse_average", width=70, anchor="center")
        self._tree_0.heading("baseline_score", text=t("value_added.baseline"))
        self._tree_0.column("baseline_score", width=70, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_0.yview)
        self._tree_0.configure(yscrollcommand=vsb.set)
        self._tree_0.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_predictions_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("value_added.target"))
        cols = ("id", "sid", "course_title", "predicted_grade", "actual_grade", "value_added_score",)
        self._tree_1 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_1.heading("id", text=t("common.id"))
        self._tree_1.column("id", width=40, anchor="center")
        self._tree_1.heading("sid", text=t("common.student_name"))
        self._tree_1.column("sid", width=80, anchor="center")
        self._tree_1.heading("course_title", text=t("common.course_title"))
        self._tree_1.column("course_title", width=150, anchor="center")
        self._tree_1.heading("predicted_grade", text=t("value_added.target"))
        self._tree_1.column("predicted_grade", width=70, anchor="center")
        self._tree_1.heading("actual_grade", text=t("value_added.actual"))
        self._tree_1.column("actual_grade", width=60, anchor="center")
        self._tree_1.heading("value_added_score", text=t("value_added.residual"))
        self._tree_1.column("value_added_score", width=50, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_1.yview)
        self._tree_1.configure(yscrollcommand=vsb.set)
        self._tree_1.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        btn = tk.Frame(tab, bg="#ecf0f1")
        btn.pack(fill="x", pady=(5, 0))
        ttk.Button(btn, text="Export CSV", command=self._export_predictions_csv).pack(side="left", padx=4)

    def _build_analysis_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("value_added.management"))
        self._analysis_frame = tk.Frame(tab, bg="#ecf0f1")
        self._analysis_frame.pack(fill="both", expand=True)
        tk.Label(self._analysis_frame, text=t("value_added.management"),
                 font=("Helvetica", 12), bg="#ecf0f1").pack(pady=20)


    def _export_baselines_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._tree_0, "value_added_baselines_export.csv")

    def _export_predictions_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._tree_1, "value_added_predictions_export.csv")

    def _load_baselines(self):
        self._tree_0.delete(*self._tree_0.get_children())
        try:
            conn = self._svc._conn()
            try:
                rows = conn.execute(
                    "SELECT * FROM value_added_baselines ORDER BY id DESC"
                ).fetchall()
                for b in rows:
                    b = dict(b)
                    self._tree_0.insert("", "end", values=(
                        b["id"], b["student_id"],
                        b.get("gcse_average") or "-",
                        b.get("baseline_score") or "-"))
            finally:
                conn.close()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_predictions(self):
        self._tree_1.delete(*self._tree_1.get_children())
        try:
            for p in self._svc.list_predictions():
                self._tree_1.insert("", "end", values=(
                    p["id"], p.get("sid", ""),
                    p.get("course_title", ""),
                    p.get("predicted_grade") or "-",
                    p.get("actual_grade") or "-",
                    p.get("value_added_score") if p.get("value_added_score") is not None else "-"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def refresh(self):
        self._load_baselines()
        self._load_predictions()

