"""Internal Verification GUI module."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.internal_verification.services.internal_verification_service import InternalVerificationService
from education_system.college_system.core.i18n import t


# -- Dialogs ------------------------------------------------------------------


class _PlanDialog(tk.Toplevel):
    """Dialog for creating / editing an IV plan."""

    def __init__(self, parent, title="IV Plan", item=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.result: dict | None = None
        self._item = item or {}
        self._build_ui()
        self._center(parent)

    def _center(self, parent):
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px - w // 2}+{py - h // 2}")

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(self, padx=20, pady=15)
        c.pack(fill="both", expand=True)
        self._vars: dict[str, tk.StringVar] = {}

        fields = [
            ("course_id", t("internal_verification.course") + " ID"),
            ("academic_year", t("internal_verification.academic_year")),
            ("lead_iv_id", t("internal_verification.lead_iv")),
            ("sampling_strategy", t("internal_verification.sampling_strategy")),
            ("sample_size_pct", t("internal_verification.sample_size") + " %"),
            ("status", t("common.status")),
        ]
        for row, (key, label) in enumerate(fields):
            tk.Label(c, text=label, anchor="w",
                     font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            var = tk.StringVar(value=str(self._item.get(key, "")))
            ttk.Entry(c, textvariable=var, width=36).grid(row=row, column=1, sticky="ew", **pad)
            self._vars[key] = var

        btn = tk.Frame(c)
        btn.grid(row=len(fields), column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn, text=t("common.save"), command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn, text=t("common.cancel"), command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        self.destroy()


class _SampleDialog(tk.Toplevel):
    """Dialog for creating / editing an IV sample."""

    def __init__(self, parent, title="IV Sample", item=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.result: dict | None = None
        self._item = item or {}
        self._build_ui()
        self._center(parent)

    def _center(self, parent):
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px - w // 2}+{py - h // 2}")

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(self, padx=20, pady=15)
        c.pack(fill="both", expand=True)
        self._vars: dict[str, tk.StringVar] = {}

        fields = [
            ("plan_id", t("internal_verification.plan_id")),
            ("assignment_title", t("internal_verification.assignment_title")),
            ("assessor_id", t("internal_verification.assessor_id")),
            ("verifier_id", t("internal_verification.verifier") + " ID"),
            ("sample_date", t("internal_verification.sample_date")),
            ("student_ids", t("internal_verification.student_ids")),
            ("status", t("common.status")),
        ]
        for row, (key, label) in enumerate(fields):
            tk.Label(c, text=label, anchor="w",
                     font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            var = tk.StringVar(value=str(self._item.get(key, "")))
            ttk.Entry(c, textvariable=var, width=36).grid(row=row, column=1, sticky="ew", **pad)
            self._vars[key] = var

        btn = tk.Frame(c)
        btn.grid(row=len(fields), column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn, text=t("common.save"), command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn, text=t("common.cancel"), command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        self.destroy()


class _CompleteSampleDialog(tk.Toplevel):
    """Dialog for completing a sample verification."""

    def __init__(self, parent, title=None):
        super().__init__(parent)
        self.title(title or t("internal_verification.complete_sample"))
        self.resizable(False, False)
        self.grab_set()
        self.result: dict | None = None
        self._build_ui()
        self._center(parent)

    def _center(self, parent):
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px - w // 2}+{py - h // 2}")

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(self, padx=20, pady=15)
        c.pack(fill="both", expand=True)

        self._decisions_var = tk.IntVar(value=1)
        self._grading_var = tk.IntVar(value=1)
        self._quality_var = tk.StringVar()
        self._action_var = tk.StringVar()

        tk.Label(c, text=t("internal_verification.decisions_agreed"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        ttk.Checkbutton(c, variable=self._decisions_var).grid(row=0, column=1, sticky="w", **pad)

        tk.Label(c, text=t("internal_verification.grading_accurate"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        ttk.Checkbutton(c, variable=self._grading_var).grid(row=1, column=1, sticky="w", **pad)

        tk.Label(c, text=t("internal_verification.feedback_quality"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=2, column=0, sticky="w", **pad)
        ttk.Combobox(c, textvariable=self._quality_var, width=33,
                     values=["excellent", "good", "adequate", "inadequate"],
                     state="readonly").grid(row=2, column=1, sticky="ew", **pad)
        self._quality_var.set("good")

        tk.Label(c, text=t("internal_verification.action_required"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(c, textvariable=self._action_var, width=36).grid(row=3, column=1, sticky="ew", **pad)

        btn = tk.Frame(c)
        btn.grid(row=4, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn, text=t("common.completed"), command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn, text=t("common.cancel"), command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        self.result = {
            "decisions_agreed": self._decisions_var.get(),
            "grading_accurate": self._grading_var.get(),
            "feedback_quality": self._quality_var.get(),
            "action_required": self._action_var.get().strip() or None,
        }
        self.destroy()


class _ObservationDialog(tk.Toplevel):
    """Dialog for creating / editing an observation."""

    def __init__(self, parent, title="Observation", item=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.result: dict | None = None
        self._item = item or {}
        self._build_ui()
        self._center(parent)

    def _center(self, parent):
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px - w // 2}+{py - h // 2}")

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(self, padx=20, pady=15)
        c.pack(fill="both", expand=True)
        self._vars: dict[str, tk.StringVar] = {}

        fields = [
            ("plan_id", t("internal_verification.plan_id")),
            ("assessor_id", t("internal_verification.assessor_id")),
            ("observer_id", t("internal_verification.observer_id")),
            ("observation_date", t("common.date") + " (YYYY-MM-DD)"),
            ("assessment_type", t("internal_verification.assessment_type")),
            ("grade", t("common.grade")),
            ("status", t("common.status")),
        ]
        for row, (key, label) in enumerate(fields):
            tk.Label(c, text=label, anchor="w",
                     font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            var = tk.StringVar(value=str(self._item.get(key, "")))
            ttk.Entry(c, textvariable=var, width=36).grid(row=row, column=1, sticky="ew", **pad)
            self._vars[key] = var

        btn = tk.Frame(c)
        btn.grid(row=len(fields), column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn, text=t("common.save"), command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn, text=t("common.cancel"), command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        self.destroy()


class _CompleteObservationDialog(tk.Toplevel):
    """Dialog for completing an observation."""

    def __init__(self, parent, title=None):
        super().__init__(parent)
        self.title(title or t("internal_verification.complete_observation"))
        self.resizable(False, False)
        self.grab_set()
        self.result: dict | None = None
        self._build_ui()
        self._center(parent)

    def _center(self, parent):
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px - w // 2}+{py - h // 2}")

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(self, padx=20, pady=15)
        c.pack(fill="both", expand=True)

        self._feedback_var = tk.StringVar()
        self._grade_var = tk.StringVar()
        self._actions_var = tk.StringVar()

        tk.Label(c, text=t("internal_verification.feedback"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(c, textvariable=self._feedback_var, width=36).grid(row=0, column=1, sticky="ew", **pad)

        tk.Label(c, text=t("common.grade"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(c, textvariable=self._grade_var, width=36).grid(row=1, column=1, sticky="ew", **pad)

        tk.Label(c, text=t("internal_verification.actions_optional"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(c, textvariable=self._actions_var, width=36).grid(row=2, column=1, sticky="ew", **pad)

        btn = tk.Frame(c)
        btn.grid(row=3, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn, text=t("common.completed"), command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn, text=t("common.cancel"), command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        fb = self._feedback_var.get().strip()
        gr = self._grade_var.get().strip()
        if not fb or not gr:
            messagebox.showwarning(t("common.validation"), t("common.field_required"))
            return
        self.result = {
            "feedback": fb,
            "grade": gr,
            "actions": self._actions_var.get().strip() or None,
        }
        self.destroy()


# -- Main Frame ----------------------------------------------------------------


class InternalVerificationFrame(tk.Frame):
    """Internal Verification management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = InternalVerificationService(db_path)
        self._build_ui()

    # -- UI construction -------------------------------------------------------

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("internal_verification.management"),
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_plans_tab()
        self._build_samples_tab()
        self._build_observations_tab()
        self._build_stats_tab()

    # -- Plans tab -------------------------------------------------------------

    def _build_plans_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("internal_verification.iv_plans"))

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 8))
        tk.Label(filt, text=t("common.status") + ":", bg="#ecf0f1").pack(side="left", padx=(0, 4))
        self._plan_status_var = tk.StringVar(value="")
        ttk.Combobox(filt, textvariable=self._plan_status_var, width=12,
                     values=["", "active", "completed", "archived"],
                     state="readonly").pack(side="left", padx=4)
        tk.Label(filt, text=t("internal_verification.course") + " ID:", bg="#ecf0f1").pack(side="left", padx=(12, 4))
        self._plan_course_var = tk.StringVar()
        ttk.Entry(filt, textvariable=self._plan_course_var, width=8).pack(side="left", padx=4)
        ttk.Button(filt, text=t("common.filter"), command=self._load_plans).pack(side="left", padx=8)

        # Buttons
        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text=t("common.create"), command=self._on_plan_new).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.view"), command=self._on_plan_view).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.update"), command=self._on_plan_update).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.delete"), command=self._on_plan_delete).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_plans).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.export_csv", default="Export CSV"), command=self._export_plans_csv).pack(side="right", padx=4)

        # Treeview
        cols = ("id", "course_id", "academic_year", "lead_iv_id",
                "sampling_strategy", "sample_size_pct", "status")
        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill="both", expand=True)
        self._plan_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", t("common.id"), 40), ("course_id", t("internal_verification.course") + " ID", 70),
                         ("academic_year", t("internal_verification.academic_year"), 100),
                         ("lead_iv_id", t("internal_verification.lead_iv"), 70),
                         ("sampling_strategy", t("internal_verification.sampling_strategy"), 140),
                         ("sample_size_pct", t("internal_verification.sample_size") + " %", 70),
                         ("status", t("common.status"), 90)]:
            self._plan_tree.heading(c, text=h)
            self._plan_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._plan_tree.yview)
        self._plan_tree.configure(yscrollcommand=vsb.set)
        self._plan_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    # -- Samples tab -----------------------------------------------------------

    def _build_samples_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("internal_verification.samples"))

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 8))
        tk.Label(filt, text=t("internal_verification.plan_id") + ":", bg="#ecf0f1").pack(side="left", padx=(0, 4))
        self._sample_plan_var = tk.StringVar()
        ttk.Entry(filt, textvariable=self._sample_plan_var, width=8).pack(side="left", padx=4)
        tk.Label(filt, text=t("common.status") + ":", bg="#ecf0f1").pack(side="left", padx=(12, 4))
        self._sample_status_var = tk.StringVar(value="")
        ttk.Combobox(filt, textvariable=self._sample_status_var, width=14,
                     values=["", "pending", "in_progress", "completed", "action_required"],
                     state="readonly").pack(side="left", padx=4)
        ttk.Button(filt, text=t("common.filter"), command=self._load_samples).pack(side="left", padx=8)

        # Buttons
        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text=t("common.create"), command=self._on_sample_new).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.completed"), command=self._on_sample_complete).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.update"), command=self._on_sample_update).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.delete"), command=self._on_sample_delete).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_samples).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.export_csv", default="Export CSV"), command=self._export_samples_csv).pack(side="right", padx=4)

        # Treeview
        cols = ("id", "plan_id", "assignment_title", "assessor_id", "verifier_id",
                "sample_date", "assessment_decisions_agreed", "grading_accurate", "status")
        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill="both", expand=True)
        self._sample_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", t("common.id"), 40), ("plan_id", t("internal_verification.plan_id"), 60),
                         ("assignment_title", t("internal_verification.assignment_title"), 160),
                         ("assessor_id", t("internal_verification.assessor"), 70),
                         ("verifier_id", t("internal_verification.verifier"), 70),
                         ("sample_date", t("common.date"), 90),
                         ("assessment_decisions_agreed", t("internal_verification.decisions_agreed"), 110),
                         ("grading_accurate", t("internal_verification.grading_ok"), 80),
                         ("status", t("common.status"), 100)]:
            self._sample_tree.heading(c, text=h)
            self._sample_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._sample_tree.yview)
        self._sample_tree.configure(yscrollcommand=vsb.set)
        self._sample_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    # -- Observations tab ------------------------------------------------------

    def _build_observations_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("internal_verification.observations"))

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 8))
        tk.Label(filt, text=t("internal_verification.plan_id") + ":", bg="#ecf0f1").pack(side="left", padx=(0, 4))
        self._obs_plan_var = tk.StringVar()
        ttk.Entry(filt, textvariable=self._obs_plan_var, width=8).pack(side="left", padx=4)
        tk.Label(filt, text=t("common.status") + ":", bg="#ecf0f1").pack(side="left", padx=(12, 4))
        self._obs_status_var = tk.StringVar(value="")
        ttk.Combobox(filt, textvariable=self._obs_status_var, width=12,
                     values=["", "scheduled", "completed", "cancelled"],
                     state="readonly").pack(side="left", padx=4)
        ttk.Button(filt, text=t("common.filter"), command=self._load_observations).pack(side="left", padx=8)

        # Buttons
        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text=t("common.create"), command=self._on_obs_new).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.completed"), command=self._on_obs_complete).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.update"), command=self._on_obs_update).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.delete"), command=self._on_obs_delete).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.refresh"), command=self._load_observations).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.export_csv", default="Export CSV"), command=self._export_observations_csv).pack(side="right", padx=4)

        # Treeview
        cols = ("id", "plan_id", "assessor_id", "observer_id",
                "observation_date", "grade", "status")
        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill="both", expand=True)
        self._obs_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", t("common.id"), 40), ("plan_id", t("internal_verification.plan_id"), 60),
                         ("assessor_id", t("internal_verification.assessor"), 70),
                         ("observer_id", t("internal_verification.observer"), 70),
                         ("observation_date", t("common.date"), 100),
                         ("grade", t("common.grade"), 60),
                         ("status", t("common.status"), 90)]:
            self._obs_tree.heading(c, text=h)
            self._obs_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._obs_tree.yview)
        self._obs_tree.configure(yscrollcommand=vsb.set)
        self._obs_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    # -- Statistics tab --------------------------------------------------------

    def _build_stats_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=20, pady=20)
        self._nb.add(tab, text=t("common.summary"))

        self._stats_labels: dict[str, tk.StringVar] = {}
        items = [
            ("total_plans", t("internal_verification.total_plans")),
            ("active_plans", t("internal_verification.active_plans")),
            ("total_samples", t("internal_verification.total_samples")),
            ("samples_completed", t("internal_verification.samples_completed")),
            ("samples_with_actions", t("internal_verification.samples_with_actions")),
            ("action_completion_rate", t("internal_verification.action_completion_rate")),
            ("total_observations", t("internal_verification.total_observations")),
            ("observations_completed", t("internal_verification.observations_completed")),
            ("grading_accuracy_rate", t("internal_verification.grading_accuracy_rate")),
        ]
        for row, (key, label) in enumerate(items):
            tk.Label(tab, text=label + ":", bg="#ecf0f1", anchor="w",
                     font=("Helvetica", 10, "bold")).grid(
                row=row, column=0, sticky="w", padx=10, pady=6)
            var = tk.StringVar(value="-")
            tk.Label(tab, textvariable=var, bg="#ecf0f1", anchor="w",
                     font=("Helvetica", 10)).grid(
                row=row, column=1, sticky="w", padx=10, pady=6)
            self._stats_labels[key] = var

        ttk.Button(tab, text=t("internal_verification.refresh_statistics"),
                   command=self._load_stats).grid(
            row=len(items), column=0, columnspan=2, pady=(20, 0))

    # -- Data loading ----------------------------------------------------------

    def refresh(self):
        self._load_plans()
        self._load_samples()
        self._load_observations()
        self._load_stats()

    def _load_plans(self):
        self._plan_tree.delete(*self._plan_tree.get_children())
        try:
            status = self._plan_status_var.get() or None
            cid_str = self._plan_course_var.get().strip()
            course_id = int(cid_str) if cid_str else None
            for r in self._svc.list_plans(status=status, course_id=course_id):
                self._plan_tree.insert("", "end", iid=r["id"], values=(
                    r["id"], r["course_id"], r.get("academic_year") or "-",
                    r.get("lead_iv_id") or "-",
                    r.get("sampling_strategy") or "-",
                    r.get("sample_size_pct", 25), r["status"]))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_samples(self):
        self._sample_tree.delete(*self._sample_tree.get_children())
        try:
            pid_str = self._sample_plan_var.get().strip()
            plan_id = int(pid_str) if pid_str else None
            status = self._sample_status_var.get() or None
            for r in self._svc.list_samples(plan_id=plan_id, status=status):
                agreed = t("common.yes") if r.get("assessment_decisions_agreed") else t("common.no")
                grading = t("common.yes") if r.get("grading_accurate") else t("common.no")
                self._sample_tree.insert("", "end", iid=r["id"], values=(
                    r["id"], r["plan_id"], r.get("assignment_title") or "-",
                    r.get("assessor_id") or "-", r.get("verifier_id") or "-",
                    r.get("sample_date") or "-", agreed, grading, r["status"]))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_observations(self):
        self._obs_tree.delete(*self._obs_tree.get_children())
        try:
            pid_str = self._obs_plan_var.get().strip()
            plan_id = int(pid_str) if pid_str else None
            status = self._obs_status_var.get() or None
            for r in self._svc.list_observations(plan_id=plan_id, status=status):
                self._obs_tree.insert("", "end", iid=r["id"], values=(
                    r["id"], r["plan_id"],
                    r.get("assessor_id") or "-", r.get("observer_id") or "-",
                    r.get("observation_date") or "-",
                    r.get("grade") or "-", r["status"]))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _load_stats(self):
        try:
            stats = self._svc.get_stats()
            for key, var in self._stats_labels.items():
                var.set(str(stats.get(key, "-")))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # -- CSV export ------------------------------------------------------------

    def _export_plans_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._plan_tree, "iv_plans.csv")

    def _export_samples_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._sample_tree, "iv_samples.csv")

    def _export_observations_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._obs_tree, "iv_observations.csv")

    # -- Selection helpers -----------------------------------------------------

    def _selected_plan_id(self) -> int | None:
        sel = self._plan_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"))
            return None
        return int(sel[0])

    def _selected_sample_id(self) -> int | None:
        sel = self._sample_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"))
            return None
        return int(sel[0])

    def _selected_obs_id(self) -> int | None:
        sel = self._obs_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"))
            return None
        return int(sel[0])

    # -- Plan actions ----------------------------------------------------------

    def _on_plan_new(self):
        dlg = _PlanDialog(self, title=t("internal_verification.new_plan"))
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            data = dlg.result
            course_id = int(data.pop("course_id"))
            # Convert numeric strings
            if data.get("lead_iv_id"):
                data["lead_iv_id"] = int(data["lead_iv_id"])
            else:
                data.pop("lead_iv_id", None)
            if data.get("sample_size_pct"):
                data["sample_size_pct"] = int(data["sample_size_pct"])
            else:
                data.pop("sample_size_pct", None)
            # Remove empty strings
            data = {k: v for k, v in data.items() if v}
            self._svc.create_plan(course_id, **data)
            messagebox.showinfo(t("common.success"), t("common.created_success"))
            self._load_plans()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _on_plan_view(self):
        pk = self._selected_plan_id()
        if pk is None:
            return
        plan = self._svc.get_plan(pk)
        if not plan:
            messagebox.showerror(t("common.error"), t("common.no_data"))
            return
        info = "\n".join(f"{k}: {v}" for k, v in plan.items())
        messagebox.showinfo(f"Plan {pk}", info)

    def _on_plan_update(self):
        pk = self._selected_plan_id()
        if pk is None:
            return
        item = self._svc.get_plan(pk)
        if not item:
            messagebox.showerror(t("common.error"), t("common.no_data"))
            return
        dlg = _PlanDialog(self, title=t("internal_verification.update_plan"), item=item)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            data = dlg.result
            if data.get("course_id"):
                data["course_id"] = int(data["course_id"])
            if data.get("lead_iv_id"):
                data["lead_iv_id"] = int(data["lead_iv_id"])
            if data.get("sample_size_pct"):
                data["sample_size_pct"] = int(data["sample_size_pct"])
            data = {k: v for k, v in data.items() if v}
            self._svc.update_plan(pk, **data)
            messagebox.showinfo(t("common.success"), t("common.updated_success"))
            self._load_plans()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _on_plan_delete(self):
        pk = self._selected_plan_id()
        if pk is None:
            return
        if not messagebox.askyesno(t("common.confirm"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_plan(pk)
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_plans()
            self._load_samples()
            self._load_observations()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # -- Sample actions --------------------------------------------------------

    def _on_sample_new(self):
        dlg = _SampleDialog(self, title=t("internal_verification.new_sample"))
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            data = dlg.result
            plan_id = int(data.pop("plan_id"))
            assignment_title = data.pop("assignment_title")
            if not assignment_title:
                messagebox.showwarning(t("common.validation"), t("common.field_required"))
                return
            if data.get("assessor_id"):
                data["assessor_id"] = int(data["assessor_id"])
            else:
                data.pop("assessor_id", None)
            if data.get("verifier_id"):
                data["verifier_id"] = int(data["verifier_id"])
            else:
                data.pop("verifier_id", None)
            data = {k: v for k, v in data.items() if v}
            self._svc.create_sample(plan_id, assignment_title, **data)
            messagebox.showinfo(t("common.success"), t("common.created_success"))
            self._load_samples()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _on_sample_complete(self):
        pk = self._selected_sample_id()
        if pk is None:
            return
        dlg = _CompleteSampleDialog(self, title=t("internal_verification.complete_sample"))
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.complete_sample(pk, **dlg.result)
            messagebox.showinfo(t("common.success"), t("internal_verification.sample_completed"))
            self._load_samples()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _on_sample_update(self):
        pk = self._selected_sample_id()
        if pk is None:
            return
        item = self._svc.get_sample(pk)
        if not item:
            messagebox.showerror(t("common.error"), t("common.no_data"))
            return
        dlg = _SampleDialog(self, title=t("internal_verification.update_sample"), item=item)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            data = dlg.result
            if data.get("plan_id"):
                data["plan_id"] = int(data["plan_id"])
            if data.get("assessor_id"):
                data["assessor_id"] = int(data["assessor_id"])
            if data.get("verifier_id"):
                data["verifier_id"] = int(data["verifier_id"])
            data = {k: v for k, v in data.items() if v}
            self._svc.update_sample(pk, **data)
            messagebox.showinfo(t("common.success"), t("common.updated_success"))
            self._load_samples()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _on_sample_delete(self):
        pk = self._selected_sample_id()
        if pk is None:
            return
        if not messagebox.askyesno(t("common.confirm"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_sample(pk)
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_samples()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # -- Observation actions ---------------------------------------------------

    def _on_obs_new(self):
        dlg = _ObservationDialog(self, title=t("internal_verification.new_observation"))
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            data = dlg.result
            plan_id = int(data.pop("plan_id"))
            if data.get("assessor_id"):
                data["assessor_id"] = int(data["assessor_id"])
            else:
                data.pop("assessor_id", None)
            if data.get("observer_id"):
                data["observer_id"] = int(data["observer_id"])
            else:
                data.pop("observer_id", None)
            data = {k: v for k, v in data.items() if v}
            self._svc.create_observation(plan_id, **data)
            messagebox.showinfo(t("common.success"), t("common.created_success"))
            self._load_observations()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _on_obs_complete(self):
        pk = self._selected_obs_id()
        if pk is None:
            return
        dlg = _CompleteObservationDialog(self, title=t("internal_verification.complete_observation"))
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.complete_observation(pk, **dlg.result)
            messagebox.showinfo(t("common.success"), t("internal_verification.observation_completed"))
            self._load_observations()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _on_obs_update(self):
        pk = self._selected_obs_id()
        if pk is None:
            return
        item = self._svc.get_observation(pk)
        if not item:
            messagebox.showerror(t("common.error"), t("common.no_data"))
            return
        dlg = _ObservationDialog(self, title=t("internal_verification.update_observation"), item=item)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            data = dlg.result
            if data.get("plan_id"):
                data["plan_id"] = int(data["plan_id"])
            if data.get("assessor_id"):
                data["assessor_id"] = int(data["assessor_id"])
            if data.get("observer_id"):
                data["observer_id"] = int(data["observer_id"])
            data = {k: v for k, v in data.items() if v}
            self._svc.update_observation(pk, **data)
            messagebox.showinfo(t("common.success"), t("common.updated_success"))
            self._load_observations()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _on_obs_delete(self):
        pk = self._selected_obs_id()
        if pk is None:
            return
        if not messagebox.askyesno(t("common.confirm"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_observation(pk)
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_observations()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
