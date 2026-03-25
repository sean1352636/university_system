"""Apprenticeships GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.core.i18n import t
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
        tk.Label(header, text=t("apprenticeships.management"),
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_standards_tab()
        self._build_enrollments_tab()
        self._build_otj_log_tab()
        self._build_reviews_tab()

        toolbar = tk.Frame(self, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=10, pady=(0, 5))
        ttk.Button(toolbar, text="Export CSV", command=self._export_csv).pack(side="left", padx=4)


    def _build_standards_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("apprenticeships.standard"))
        cols = ("id", "standard_name", "level", "sector",)
        self._tree_0 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_0.heading("id", text=t("common.id"))
        self._tree_0.column("id", width=40, anchor="center")
        self._tree_0.heading("standard_name", text=t("apprenticeships.standard"))
        self._tree_0.column("standard_name", width=200, anchor="center")
        self._tree_0.heading("level", text=t("apprenticeships.level"))
        self._tree_0.column("level", width=50, anchor="center")
        self._tree_0.heading("sector", text=t("common.category"))
        self._tree_0.column("sector", width=120, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_0.yview)
        self._tree_0.configure(yscrollcommand=vsb.set)
        self._tree_0.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_enrollments_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("common.enrolled"))
        cols = ("id", "sid", "standard_name", "employer_name", "otj_hours_completed",)
        self._tree_1 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_1.heading("id", text=t("common.id"))
        self._tree_1.column("id", width=40, anchor="center")
        self._tree_1.heading("sid", text=t("apprenticeships.apprentice"))
        self._tree_1.column("sid", width=80, anchor="center")
        self._tree_1.heading("standard_name", text=t("apprenticeships.standard"))
        self._tree_1.column("standard_name", width=150, anchor="center")
        self._tree_1.heading("employer_name", text=t("apprenticeships.employer"))
        self._tree_1.column("employer_name", width=120, anchor="center")
        self._tree_1.heading("otj_hours_completed", text=t("tlevel.placement_hours"))
        self._tree_1.column("otj_hours_completed", width=60, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_1.yview)
        self._tree_1.configure(yscrollcommand=vsb.set)
        self._tree_1.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_otj_log_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("tlevel.industry_placement"))
        cols = ("id", "log_date", "hours", "activity_type", "description",)
        self._tree_2 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_2.heading("id", text=t("common.id"))
        self._tree_2.column("id", width=40, anchor="center")
        self._tree_2.heading("log_date", text=t("common.date"))
        self._tree_2.column("log_date", width=90, anchor="center")
        self._tree_2.heading("hours", text=t("tlevel.placement_hours"))
        self._tree_2.column("hours", width=50, anchor="center")
        self._tree_2.heading("activity_type", text=t("common.type"))
        self._tree_2.column("activity_type", width=100, anchor="center")
        self._tree_2.heading("description", text=t("common.description"))
        self._tree_2.column("description", width=200, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_2.yview)
        self._tree_2.configure(yscrollcommand=vsb.set)
        self._tree_2.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_reviews_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("ilp.review_date"))
        cols = ("id", "review_date", "progress_summary",)
        self._tree_3 = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self._tree_3.heading("id", text=t("common.id"))
        self._tree_3.column("id", width=40, anchor="center")
        self._tree_3.heading("review_date", text=t("common.date"))
        self._tree_3.column("review_date", width=90, anchor="center")
        self._tree_3.heading("progress_summary", text=t("common.summary"))
        self._tree_3.column("progress_summary", width=250, anchor="center")
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self._tree_3.yview)
        self._tree_3.configure(yscrollcommand=vsb.set)
        self._tree_3.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")


    def _load_standards(self):
        self._tree_0.delete(*self._tree_0.get_children())
        try:
            for s in self._svc.list_standards():
                self._tree_0.insert("", "end", values=(
                    s["id"], s.get("standard_name", ""),
                    s.get("level") or "-",
                    s.get("sector") or "-"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_enrollments(self):
        self._tree_1.delete(*self._tree_1.get_children())
        try:
            for e in self._svc.list_enrollments():
                self._tree_1.insert("", "end", values=(
                    e["id"], e.get("sid", ""),
                    e.get("standard_name", ""),
                    e.get("employer_name") or "-",
                    e.get("otj_hours_completed") or 0))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_otj_log(self):
        self._tree_2.delete(*self._tree_2.get_children())
        try:
            for enr in self._svc.list_enrollments():
                for log in self._svc.list_otj_logs(enr["id"]):
                    self._tree_2.insert("", "end", values=(
                        log["id"], log.get("log_date") or "-",
                        log.get("hours") or 0,
                        log.get("activity_type") or "-",
                        log.get("description") or "-"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_reviews(self):
        self._tree_3.delete(*self._tree_3.get_children())
        try:
            conn = self._svc._conn()
            try:
                rows = conn.execute(
                    "SELECT * FROM apprenticeship_reviews ORDER BY review_date DESC"
                ).fetchall()
                for r in rows:
                    r = dict(r)
                    self._tree_3.insert("", "end", values=(
                        r["id"], r.get("review_date") or "-",
                        r.get("progress_summary") or "-"))
            finally:
                conn.close()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        tab_index = self._nb.index(self._nb.select())
        trees = [self._tree_0, self._tree_1, self._tree_2, self._tree_3]
        names = ["apprenticeship_standards.csv", "apprenticeship_enrollments.csv",
                 "apprenticeship_otj_log.csv", "apprenticeship_reviews.csv"]
        export_treeview_to_csv(trees[tab_index], names[tab_index])

    def refresh(self):
        self._load_standards()
        self._load_enrollments()
        self._load_otj_log()
        self._load_reviews()

