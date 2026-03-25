"""Differentiated target setting GUI frame."""
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.target_setting.services.target_setting_service import (
    TargetSettingService,
)
from education_system.college_system.core.i18n import t


class TargetSettingFrame(tk.Frame):
    """GUI for differentiated target setting engine."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = TargetSettingService(db_path)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text=t("target_setting.title", "Target Setting Engine"),
            font=("Helvetica", 15, "bold"),
            bg="#2c3e50",
            fg="white",
        ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_prior_tab()
        self._build_targets_tab()
        self._build_va_tab()
        self._build_alps_tab()
        self._build_benchmarks_tab()

    # -- Prior Attainment Tab --

    def _build_prior_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("target_setting.prior_tab", "Prior Attainment"))

        form = tk.LabelFrame(tab, text=t("target_setting.import_prior", "Import Prior Attainment"), bg="#ecf0f1")
        form.pack(fill="x", padx=10, pady=5)

        labels = ["Student ID", "Qual Type", "Subject", "Grade", "Points", "Academic Year"]
        self._prior_vars = {}
        for i, lbl in enumerate(labels):
            tk.Label(form, text=lbl + ":", bg="#ecf0f1").grid(row=i // 3, column=(i % 3) * 2, padx=5, pady=2, sticky="e")
            var = tk.StringVar()
            tk.Entry(form, textvariable=var, width=18).grid(row=i // 3, column=(i % 3) * 2 + 1, padx=5, pady=2)
            self._prior_vars[lbl] = var

        btn_frame = tk.Frame(form, bg="#ecf0f1")
        btn_frame.grid(row=3, column=0, columnspan=6, pady=5)
        tk.Button(btn_frame, text=t("common.add", "Add"), command=self._add_prior).pack(side="left", padx=5)
        tk.Button(btn_frame, text=t("common.load", "Load"), command=self._load_prior).pack(side="left", padx=5)

        cols = ("id", "student_id", "qualification_type", "subject", "grade", "points", "academic_year")
        self._prior_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c in cols:
            self._prior_tree.heading(c, text=c.replace("_", " ").title())
            self._prior_tree.column(c, width=110)
        self._prior_tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _add_prior(self):
        try:
            v = self._prior_vars
            self._svc.import_prior_attainment(
                student_id=int(v["Student ID"].get()),
                qualification_type=v["Qual Type"].get(),
                subject=v["Subject"].get(),
                grade=v["Grade"].get(),
                points=float(v["Points"].get()),
                academic_year=v["Academic Year"].get(),
            )
            messagebox.showinfo(t("common.success", "Success"), t("target_setting.prior_added", "Prior attainment added."))
            self._load_prior()
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _load_prior(self):
        for row in self._prior_tree.get_children():
            self._prior_tree.delete(row)
        try:
            sid = self._prior_vars["Student ID"].get()
            if not sid:
                return
            for r in self._svc.get_student_prior_attainment(int(sid)):
                self._prior_tree.insert("", "end", values=(
                    r["id"], r["student_id"], r["qualification_type"],
                    r["subject"], r["grade"], r["points"], r.get("academic_year", ""),
                ))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    # -- Target Generation Tab --

    def _build_targets_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("target_setting.targets_tab", "Target Generation"))

        form = tk.LabelFrame(tab, text=t("target_setting.generate", "Generate Targets"), bg="#ecf0f1")
        form.pack(fill="x", padx=10, pady=5)

        labels = ["Student ID", "Course ID", "Academic Year", "Method"]
        self._gen_vars = {}
        for i, lbl in enumerate(labels):
            tk.Label(form, text=lbl + ":", bg="#ecf0f1").grid(row=0, column=i * 2, padx=5, pady=5, sticky="e")
            var = tk.StringVar()
            if lbl == "Method":
                var.set("alps")
            tk.Entry(form, textvariable=var, width=15).grid(row=0, column=i * 2 + 1, padx=5, pady=5)
            self._gen_vars[lbl] = var

        btn_frame = tk.Frame(form, bg="#ecf0f1")
        btn_frame.grid(row=1, column=0, columnspan=8, pady=5)
        tk.Button(btn_frame, text=t("target_setting.generate_single", "Generate"), command=self._generate_single).pack(side="left", padx=5)
        tk.Button(btn_frame, text=t("target_setting.generate_bulk", "Bulk Generate (Course)"), command=self._generate_bulk).pack(side="left", padx=5)
        tk.Button(btn_frame, text=t("common.refresh", "Refresh"), command=self._load_targets).pack(side="left", padx=5)

        cols = ("id", "student_id", "course_id", "prior_average_points", "meg_grade",
                "target_grade", "aspirational_grade", "current_grade", "value_added", "setting_method")
        self._targets_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c in cols:
            self._targets_tree.heading(c, text=c.replace("_", " ").title())
            self._targets_tree.column(c, width=100)
        self._targets_tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _generate_single(self):
        try:
            v = self._gen_vars
            self._svc.generate_targets(
                student_id=int(v["Student ID"].get()),
                course_id=int(v["Course ID"].get()),
                academic_year=v["Academic Year"].get(),
                method=v["Method"].get(),
            )
            messagebox.showinfo(t("common.success", "Success"), t("target_setting.target_generated", "Target generated."))
            self._load_targets()
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _generate_bulk(self):
        try:
            v = self._gen_vars
            count = self._svc.bulk_generate_targets(
                course_id=int(v["Course ID"].get()),
                academic_year=v["Academic Year"].get(),
                method=v["Method"].get(),
            )
            messagebox.showinfo(t("common.success", "Success"), f"{count} targets generated.")
            self._load_targets()
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _load_targets(self):
        for row in self._targets_tree.get_children():
            self._targets_tree.delete(row)
        try:
            v = self._gen_vars
            sid = v["Student ID"].get()
            cid = v["Course ID"].get()
            ay = v["Academic Year"].get()
            for r in self._svc.get_targets(
                student_id=int(sid) if sid else None,
                course_id=int(cid) if cid else None,
                academic_year=ay or None,
            ):
                self._targets_tree.insert("", "end", values=(
                    r["id"], r["student_id"], r["course_id"],
                    r.get("prior_average_points", ""), r.get("meg_grade", ""),
                    r.get("target_grade", ""), r.get("aspirational_grade", ""),
                    r.get("current_grade", ""), r.get("value_added", ""),
                    r.get("setting_method", ""),
                ))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    # -- Value Added Tab --

    def _build_va_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("target_setting.va_tab", "Value Added"))

        ctrl = tk.Frame(tab, bg="#ecf0f1")
        ctrl.pack(fill="x", padx=10, pady=5)

        tk.Label(ctrl, text="Course ID:", bg="#ecf0f1").pack(side="left", padx=5)
        self._va_course_var = tk.StringVar()
        tk.Entry(ctrl, textvariable=self._va_course_var, width=10).pack(side="left", padx=5)
        tk.Label(ctrl, text="Academic Year:", bg="#ecf0f1").pack(side="left", padx=5)
        self._va_year_var = tk.StringVar()
        tk.Entry(ctrl, textvariable=self._va_year_var, width=12).pack(side="left", padx=5)
        tk.Button(ctrl, text=t("target_setting.load_va", "Load VA"), command=self._load_va).pack(side="left", padx=5)

        cols = ("student_id", "meg_grade", "target_grade", "current_grade", "value_added")
        self._va_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        for c in cols:
            self._va_tree.heading(c, text=c.replace("_", " ").title())
            self._va_tree.column(c, width=130)
        self._va_tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _load_va(self):
        for row in self._va_tree.get_children():
            self._va_tree.delete(row)
        try:
            cid = int(self._va_course_var.get())
            ay = self._va_year_var.get()
            for r in self._svc.get_course_value_added(cid, ay):
                self._va_tree.insert("", "end", values=(
                    r["student_id"], r.get("meg_grade", ""),
                    r.get("target_grade", ""), r.get("current_grade", ""),
                    r.get("value_added", ""),
                ))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    # -- ALPS Dashboard Tab --

    def _build_alps_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("target_setting.alps_tab", "ALPS Dashboard"))

        ctrl = tk.Frame(tab, bg="#ecf0f1")
        ctrl.pack(fill="x", padx=10, pady=5)

        tk.Label(ctrl, text="Academic Year:", bg="#ecf0f1").pack(side="left", padx=5)
        self._alps_year_var = tk.StringVar()
        tk.Entry(ctrl, textvariable=self._alps_year_var, width=12).pack(side="left", padx=5)
        tk.Button(ctrl, text=t("target_setting.load_alps", "Load Summary"), command=self._load_alps).pack(side="left", padx=5)

        self._alps_info = tk.Text(tab, height=15, width=60, state="disabled")
        self._alps_info.pack(fill="both", expand=True, padx=10, pady=10)

    def _load_alps(self):
        try:
            ay = self._alps_year_var.get()
            summary = self._svc.get_alps_summary(ay)
            self._alps_info.config(state="normal")
            self._alps_info.delete("1.0", "end")
            self._alps_info.insert("end", f"ALPS Summary for {ay}\n")
            self._alps_info.insert("end", "=" * 40 + "\n\n")
            for key, val in summary.items():
                label = key.replace("_", " ").title()
                self._alps_info.insert("end", f"{label}: {val}\n")
            self._alps_info.config(state="disabled")
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    # -- Benchmarks Tab --

    def _build_benchmarks_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("target_setting.benchmarks_tab", "Benchmarks"))

        form = tk.LabelFrame(tab, text=t("target_setting.add_benchmark", "Add Benchmark"), bg="#ecf0f1")
        form.pack(fill="x", padx=10, pady=5)

        labels = ["Qual Type", "Points Min", "Points Max", "Subject Group",
                  "MEG Grade", "Target Grade", "Aspirational", "Academic Year"]
        self._bench_vars = {}
        for i, lbl in enumerate(labels):
            tk.Label(form, text=lbl + ":", bg="#ecf0f1").grid(row=i // 4, column=(i % 4) * 2, padx=5, pady=2, sticky="e")
            var = tk.StringVar()
            tk.Entry(form, textvariable=var, width=14).grid(row=i // 4, column=(i % 4) * 2 + 1, padx=5, pady=2)
            self._bench_vars[lbl] = var

        btn_frame = tk.Frame(form, bg="#ecf0f1")
        btn_frame.grid(row=3, column=0, columnspan=8, pady=5)
        tk.Button(btn_frame, text=t("common.add", "Add"), command=self._add_benchmark).pack(side="left", padx=5)
        tk.Button(btn_frame, text=t("common.refresh", "Refresh"), command=self._load_benchmarks).pack(side="left", padx=5)

        cols = ("id", "qualification_type", "prior_points_min", "prior_points_max",
                "subject_group", "meg_grade", "target_grade", "aspirational_grade", "academic_year")
        self._bench_tree = ttk.Treeview(tab, columns=cols, show="headings", height=10)
        for c in cols:
            self._bench_tree.heading(c, text=c.replace("_", " ").title())
            self._bench_tree.column(c, width=100)
        self._bench_tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _add_benchmark(self):
        try:
            v = self._bench_vars
            self._svc.set_benchmark(
                qualification_type=v["Qual Type"].get(),
                prior_points_min=float(v["Points Min"].get()),
                prior_points_max=float(v["Points Max"].get()),
                subject_group=v["Subject Group"].get(),
                meg_grade=v["MEG Grade"].get(),
                target_grade=v["Target Grade"].get(),
                aspirational_grade=v["Aspirational"].get(),
                academic_year=v["Academic Year"].get(),
            )
            messagebox.showinfo(t("common.success", "Success"), t("target_setting.benchmark_added", "Benchmark added."))
            self._load_benchmarks()
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def _load_benchmarks(self):
        for row in self._bench_tree.get_children():
            self._bench_tree.delete(row)
        try:
            v = self._bench_vars
            for r in self._svc.list_benchmarks(
                qualification_type=v["Qual Type"].get() or None,
                academic_year=v["Academic Year"].get() or None,
            ):
                self._bench_tree.insert("", "end", values=(
                    r["id"], r["qualification_type"], r["prior_points_min"],
                    r["prior_points_max"], r.get("subject_group", ""),
                    r["meg_grade"], r["target_grade"], r["aspirational_grade"],
                    r.get("academic_year", ""),
                ))
        except Exception as exc:
            messagebox.showerror(t("common.error", "Error"), str(exc))

    def refresh(self):
        """Refresh all data."""
        pass
