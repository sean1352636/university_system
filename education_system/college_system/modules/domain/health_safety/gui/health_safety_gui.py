"""Health & Safety GUI module."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.health_safety.services.health_safety_service import (
    HealthSafetyService,
)
from education_system.college_system.core.exceptions import HealthSafetyError


# ── Dialogs ───────────────────────────────────────────────────────────────────


class _BaseDialog(tk.Toplevel):
    """Base modal dialog with centering and save/cancel buttons."""

    def __init__(self, parent, title="Dialog", fields=None, item=None, combos=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.result: dict | None = None
        self._item = item or {}
        self._field_defs = fields or []
        self._combos = combos or {}
        self._vars: dict[str, tk.StringVar] = {}
        self._build_ui()
        self._center(parent)

    def _center(self, parent):
        self.update_idletasks()
        pw = parent.winfo_rootx() + parent.winfo_width() // 2
        ph = parent.winfo_rooty() + parent.winfo_height() // 2
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{pw - w // 2}+{ph - h // 2}")

    def _build_ui(self):
        pad = {"padx": 10, "pady": 4}
        container = tk.Frame(self, padx=20, pady=15)
        container.pack(fill="both", expand=True)

        for row_idx, (key, label) in enumerate(self._field_defs):
            tk.Label(container, text=label, anchor="w",
                     font=("Helvetica", 9, "bold")).grid(row=row_idx, column=0, sticky="w", **pad)
            var = tk.StringVar(value=str(self._item.get(key, "") or ""))
            self._vars[key] = var
            if key in self._combos:
                cb = ttk.Combobox(container, textvariable=var, values=self._combos[key],
                                  width=34, state="readonly")
                cb.grid(row=row_idx, column=1, sticky="ew", **pad)
            else:
                ttk.Entry(container, textvariable=var, width=36).grid(
                    row=row_idx, column=1, sticky="ew", **pad)

        btn_frame = tk.Frame(container)
        btn_frame.grid(row=len(self._field_defs), column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        self.destroy()


class _IncidentDialog(_BaseDialog):
    FIELDS = [
        ("incident_date", "Date (YYYY-MM-DD)"),
        ("incident_type", "Type"),
        ("location", "Location"),
        ("reported_by", "Reported By"),
        ("description", "Description"),
        ("persons_involved", "Persons Involved"),
        ("injury_details", "Injury Details"),
        ("first_aid_given", "First Aid Given (0/1)"),
        ("riddor_reportable", "RIDDOR Reportable (0/1)"),
        ("riddor_reference", "RIDDOR Reference"),
        ("status", "Status"),
    ]
    COMBOS = {
        "incident_type": ["accident", "near_miss", "dangerous_occurrence", "violence", "illness", "fire", "environmental"],
        "status": ["open", "investigating", "action_required", "closed"],
    }

    def __init__(self, parent, title="Incident", item=None):
        super().__init__(parent, title=title, fields=self.FIELDS, item=item, combos=self.COMBOS)


class _CloseIncidentDialog(tk.Toplevel):
    """Dialog for closing an incident with root cause and corrective actions."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Close Incident")
        self.resizable(False, False)
        self.grab_set()
        self.result: dict | None = None
        self._build_ui()
        self.update_idletasks()
        pw = parent.winfo_rootx() + parent.winfo_width() // 2
        ph = parent.winfo_rooty() + parent.winfo_height() // 2
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{pw - w // 2}+{ph - h // 2}")

    def _build_ui(self):
        container = tk.Frame(self, padx=20, pady=15)
        container.pack(fill="both", expand=True)
        tk.Label(container, text="Root Cause", font=("Helvetica", 9, "bold")).pack(anchor="w", pady=(0, 2))
        self._root_cause = tk.Text(container, width=40, height=4)
        self._root_cause.pack(fill="x", pady=(0, 8))
        tk.Label(container, text="Corrective Actions", font=("Helvetica", 9, "bold")).pack(anchor="w", pady=(0, 2))
        self._actions = tk.Text(container, width=40, height=4)
        self._actions.pack(fill="x", pady=(0, 8))
        btn_frame = tk.Frame(container)
        btn_frame.pack()
        ttk.Button(btn_frame, text="Close Incident", command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        rc = self._root_cause.get("1.0", "end").strip()
        ca = self._actions.get("1.0", "end").strip()
        if not rc or not ca:
            messagebox.showwarning("Validation", "Both root cause and corrective actions are required.")
            return
        self.result = {"root_cause": rc, "corrective_actions": ca}
        self.destroy()


class _InspectionDialog(_BaseDialog):
    FIELDS = [
        ("inspection_type", "Inspection Type"),
        ("area", "Area"),
        ("inspector", "Inspector"),
        ("inspection_date", "Date (YYYY-MM-DD)"),
        ("next_due_date", "Next Due Date"),
        ("findings", "Findings"),
        ("actions_required", "Actions Required"),
        ("certificate_ref", "Certificate Ref"),
        ("status", "Status"),
    ]
    COMBOS = {
        "status": ["passed", "failed", "conditional", "pending"],
    }

    def __init__(self, parent, title="Inspection", item=None):
        super().__init__(parent, title=title, fields=self.FIELDS, item=item, combos=self.COMBOS)


class _RiskAssessmentDialog(_BaseDialog):
    FIELDS = [
        ("activity", "Activity"),
        ("location", "Location"),
        ("assessor", "Assessor"),
        ("assessment_date", "Date (YYYY-MM-DD)"),
        ("hazards", "Hazards"),
        ("persons_at_risk", "Persons at Risk"),
        ("existing_controls", "Existing Controls"),
        ("risk_rating", "Risk Rating"),
        ("additional_controls", "Additional Controls"),
        ("review_date", "Review Date"),
        ("status", "Status"),
    ]
    COMBOS = {
        "risk_rating": ["low", "medium", "high", "very_high"],
        "status": ["active", "review_due", "archived"],
    }

    def __init__(self, parent, title="Risk Assessment", item=None):
        super().__init__(parent, title=title, fields=self.FIELDS, item=item, combos=self.COMBOS)


class _ComplianceCheckDialog(_BaseDialog):
    FIELDS = [
        ("check_type", "Check Type"),
        ("description", "Description"),
        ("responsible_person", "Responsible Person"),
        ("frequency", "Frequency"),
        ("last_completed", "Last Completed"),
        ("next_due", "Next Due"),
        ("certificate_ref", "Certificate Ref"),
        ("provider", "Provider"),
        ("status", "Status"),
        ("notes", "Notes"),
    ]
    COMBOS = {
        "frequency": ["daily", "weekly", "monthly", "quarterly", "annual", "biennial"],
        "status": ["current", "due", "overdue", "expired"],
    }

    def __init__(self, parent, title="Compliance Check", item=None):
        super().__init__(parent, title=title, fields=self.FIELDS, item=item, combos=self.COMBOS)


class _DetailDialog(tk.Toplevel):
    """Read-only detail view for a record."""

    def __init__(self, parent, title, data: dict):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        container = tk.Frame(self, padx=20, pady=15)
        container.pack(fill="both", expand=True)
        for idx, (k, v) in enumerate(data.items()):
            tk.Label(container, text=f"{k}:", font=("Helvetica", 9, "bold"),
                     anchor="w").grid(row=idx, column=0, sticky="w", padx=5, pady=2)
            tk.Label(container, text=str(v or ""), anchor="w", wraplength=350).grid(
                row=idx, column=1, sticky="w", padx=5, pady=2)
        ttk.Button(container, text="Close", command=self.destroy).grid(
            row=len(data), column=0, columnspan=2, pady=(12, 0))
        self.update_idletasks()
        pw = parent.winfo_rootx() + parent.winfo_width() // 2
        ph = parent.winfo_rooty() + parent.winfo_height() // 2
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{pw - w // 2}+{ph - h // 2}")


# ── Main Frame ────────────────────────────────────────────────────────────────


class HealthSafetyFrame(tk.Frame):
    """Health & Safety management frame with tabbed interface."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = HealthSafetyService(db_path)
        self._build_ui()

    # ── UI Construction ───────────────────────────────────────────────────

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Health & Safety",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_incidents_tab()
        self._build_inspections_tab()
        self._build_risk_assessments_tab()
        self._build_compliance_tab()
        self._build_stats_tab()

    # -- Incidents tab --

    def _build_incidents_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Incidents")

        # Filters
        filt_frame = tk.Frame(tab, bg="#ecf0f1")
        filt_frame.pack(fill="x", pady=(0, 8))

        tk.Label(filt_frame, text="Status:", bg="#ecf0f1").pack(side="left", padx=(0, 4))
        self._inc_status_var = tk.StringVar(value="")
        cb = ttk.Combobox(filt_frame, textvariable=self._inc_status_var, width=14, state="readonly",
                          values=["", "open", "investigating", "action_required", "closed"])
        cb.pack(side="left", padx=(0, 10))

        tk.Label(filt_frame, text="Type:", bg="#ecf0f1").pack(side="left", padx=(0, 4))
        self._inc_type_var = tk.StringVar(value="")
        cb2 = ttk.Combobox(filt_frame, textvariable=self._inc_type_var, width=16, state="readonly",
                           values=["", "accident", "near_miss", "dangerous_occurrence", "violence", "illness", "fire", "environmental"])
        cb2.pack(side="left", padx=(0, 10))

        ttk.Button(filt_frame, text="Filter", command=self._load_incidents).pack(side="left", padx=4)

        # Buttons
        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(0, 6))
        ttk.Button(btn_frame, text="New", command=self._on_add_incident).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="View", command=self._on_view_incident).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Update", command=self._on_edit_incident).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Close", command=self._on_close_incident).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Delete", command=self._on_delete_incident).pack(side="left", padx=4)

        # Treeview
        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill="both", expand=True)
        cols = ("id", "date", "type", "location", "description", "riddor", "status")
        self._inc_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, heading, width in [
            ("id", "ID", 40), ("date", "Date", 90), ("type", "Type", 100),
            ("location", "Location", 110), ("description", "Description", 220),
            ("riddor", "RIDDOR", 55), ("status", "Status", 100),
        ]:
            self._inc_tree.heading(col, text=heading)
            self._inc_tree.column(col, width=width, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._inc_tree.yview)
        self._inc_tree.configure(yscrollcommand=vsb.set)
        self._inc_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    # -- Inspections tab --

    def _build_inspections_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Inspections")

        filt_frame = tk.Frame(tab, bg="#ecf0f1")
        filt_frame.pack(fill="x", pady=(0, 8))
        tk.Label(filt_frame, text="Status:", bg="#ecf0f1").pack(side="left", padx=(0, 4))
        self._insp_status_var = tk.StringVar(value="")
        ttk.Combobox(filt_frame, textvariable=self._insp_status_var, width=14, state="readonly",
                     values=["", "passed", "failed", "conditional", "pending"]).pack(side="left", padx=(0, 10))
        ttk.Button(filt_frame, text="Filter", command=self._load_inspections).pack(side="left", padx=4)

        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(0, 6))
        ttk.Button(btn_frame, text="New", command=self._on_add_inspection).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="View", command=self._on_view_inspection).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Update", command=self._on_edit_inspection).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Delete", command=self._on_delete_inspection).pack(side="left", padx=4)

        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill="both", expand=True)
        cols = ("id", "type", "area", "inspector", "date", "next_due", "status")
        self._insp_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, heading, width in [
            ("id", "ID", 40), ("type", "Type", 120), ("area", "Area", 100),
            ("inspector", "Inspector", 100), ("date", "Date", 90),
            ("next_due", "Next Due", 90), ("status", "Status", 80),
        ]:
            self._insp_tree.heading(col, text=heading)
            self._insp_tree.column(col, width=width, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._insp_tree.yview)
        self._insp_tree.configure(yscrollcommand=vsb.set)
        self._insp_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    # -- Risk Assessments tab --

    def _build_risk_assessments_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Risk Assessments")

        filt_frame = tk.Frame(tab, bg="#ecf0f1")
        filt_frame.pack(fill="x", pady=(0, 8))
        tk.Label(filt_frame, text="Rating:", bg="#ecf0f1").pack(side="left", padx=(0, 4))
        self._ra_rating_var = tk.StringVar(value="")
        ttk.Combobox(filt_frame, textvariable=self._ra_rating_var, width=10, state="readonly",
                     values=["", "low", "medium", "high", "very_high"]).pack(side="left", padx=(0, 10))
        tk.Label(filt_frame, text="Status:", bg="#ecf0f1").pack(side="left", padx=(0, 4))
        self._ra_status_var = tk.StringVar(value="")
        ttk.Combobox(filt_frame, textvariable=self._ra_status_var, width=12, state="readonly",
                     values=["", "active", "review_due", "archived"]).pack(side="left", padx=(0, 10))
        ttk.Button(filt_frame, text="Filter", command=self._load_risk_assessments).pack(side="left", padx=4)

        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(0, 6))
        ttk.Button(btn_frame, text="New", command=self._on_add_risk_assessment).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="View", command=self._on_view_risk_assessment).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Update", command=self._on_edit_risk_assessment).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Delete", command=self._on_delete_risk_assessment).pack(side="left", padx=4)

        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill="both", expand=True)
        cols = ("id", "activity", "location", "assessor", "date", "rating", "review", "status")
        self._ra_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, heading, width in [
            ("id", "ID", 40), ("activity", "Activity", 140), ("location", "Location", 100),
            ("assessor", "Assessor", 100), ("date", "Date", 90),
            ("rating", "Rating", 75), ("review", "Review Date", 90), ("status", "Status", 80),
        ]:
            self._ra_tree.heading(col, text=heading)
            self._ra_tree.column(col, width=width, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._ra_tree.yview)
        self._ra_tree.configure(yscrollcommand=vsb.set)
        self._ra_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    # -- Compliance Checks tab --

    def _build_compliance_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Compliance Checks")

        filt_frame = tk.Frame(tab, bg="#ecf0f1")
        filt_frame.pack(fill="x", pady=(0, 8))
        tk.Label(filt_frame, text="Status:", bg="#ecf0f1").pack(side="left", padx=(0, 4))
        self._cc_status_var = tk.StringVar(value="")
        ttk.Combobox(filt_frame, textvariable=self._cc_status_var, width=12, state="readonly",
                     values=["", "current", "due", "overdue", "expired"]).pack(side="left", padx=(0, 10))
        ttk.Button(filt_frame, text="Filter", command=self._load_compliance_checks).pack(side="left", padx=4)
        ttk.Button(filt_frame, text="Show Overdue", command=self._on_show_overdue).pack(side="left", padx=4)

        btn_frame = tk.Frame(tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", pady=(0, 6))
        ttk.Button(btn_frame, text="New", command=self._on_add_compliance).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Update", command=self._on_edit_compliance).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Delete", command=self._on_delete_compliance).pack(side="left", padx=4)

        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill="both", expand=True)
        cols = ("id", "type", "responsible", "frequency", "last_done", "next_due", "status")
        self._cc_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, heading, width in [
            ("id", "ID", 40), ("type", "Type", 140), ("responsible", "Responsible", 110),
            ("frequency", "Frequency", 80), ("last_done", "Last Done", 90),
            ("next_due", "Next Due", 90), ("status", "Status", 75),
        ]:
            self._cc_tree.heading(col, text=heading)
            self._cc_tree.column(col, width=width, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._cc_tree.yview)
        self._cc_tree.configure(yscrollcommand=vsb.set)
        self._cc_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    # -- Statistics tab --

    def _build_stats_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=20, pady=20)
        self._nb.add(tab, text="Statistics")
        self._stats_frame = tab

    # ── Data Loading ──────────────────────────────────────────────────────

    def refresh(self):
        """Reload all tabs."""
        self._load_incidents()
        self._load_inspections()
        self._load_risk_assessments()
        self._load_compliance_checks()
        self._load_stats()

    def _load_incidents(self):
        self._inc_tree.delete(*self._inc_tree.get_children())
        try:
            status = self._inc_status_var.get() or None
            inc_type = self._inc_type_var.get() or None
            items = self._svc.list_incidents(status=status, incident_type=inc_type)
            for item in items:
                riddor = "Yes" if item.get("riddor_reportable") else "No"
                self._inc_tree.insert("", "end", iid=item["id"], values=(
                    item["id"],
                    item.get("incident_date", ""),
                    item.get("incident_type", ""),
                    item.get("location", ""),
                    str(item.get("description", ""))[:60],
                    riddor,
                    item.get("status", ""),
                ))
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load incidents:\n{exc}")

    def _load_inspections(self):
        self._insp_tree.delete(*self._insp_tree.get_children())
        try:
            status = self._insp_status_var.get() or None
            items = self._svc.list_inspections(status=status)
            for item in items:
                self._insp_tree.insert("", "end", iid=item["id"], values=(
                    item["id"],
                    item.get("inspection_type", ""),
                    item.get("area", ""),
                    item.get("inspector", ""),
                    item.get("inspection_date", ""),
                    item.get("next_due_date", ""),
                    item.get("status", ""),
                ))
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load inspections:\n{exc}")

    def _load_risk_assessments(self):
        self._ra_tree.delete(*self._ra_tree.get_children())
        try:
            status = self._ra_status_var.get() or None
            rating = self._ra_rating_var.get() or None
            items = self._svc.list_risk_assessments(status=status, risk_rating=rating)
            for item in items:
                self._ra_tree.insert("", "end", iid=item["id"], values=(
                    item["id"],
                    item.get("activity", ""),
                    item.get("location", ""),
                    item.get("assessor", ""),
                    item.get("assessment_date", ""),
                    item.get("risk_rating", ""),
                    item.get("review_date", ""),
                    item.get("status", ""),
                ))
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load risk assessments:\n{exc}")

    def _load_compliance_checks(self):
        self._cc_tree.delete(*self._cc_tree.get_children())
        try:
            status = self._cc_status_var.get() or None
            items = self._svc.list_compliance_checks(status=status)
            for item in items:
                self._cc_tree.insert("", "end", iid=item["id"], values=(
                    item["id"],
                    item.get("check_type", ""),
                    item.get("responsible_person", ""),
                    item.get("frequency", ""),
                    item.get("last_completed", ""),
                    item.get("next_due", ""),
                    item.get("status", ""),
                ))
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load compliance checks:\n{exc}")

    def _load_stats(self):
        for widget in self._stats_frame.winfo_children():
            widget.destroy()
        try:
            stats = self._svc.get_stats()
            sections = [
                ("Incidents", [
                    f"Total Incidents: {stats.get('total_incidents', 0)}",
                    f"Open Incidents: {stats.get('open_incidents', 0)}",
                    f"RIDDOR Reportable: {stats.get('riddor_count', 0)}",
                ]),
                ("By Incident Type", [
                    f"  {k}: {v}" for k, v in stats.get("by_type", {}).items()
                ]),
                ("Inspections", [
                    f"Total Inspections: {stats.get('total_inspections', 0)}",
                    f"Failed Inspections: {stats.get('failed_inspections', 0)}",
                ]),
                ("Risk Assessments", [
                    f"Total Risk Assessments: {stats.get('total_risk_assessments', 0)}",
                    f"High/Very High Risk: {stats.get('high_risk_count', 0)}",
                ]),
                ("Compliance", [
                    f"Total Compliance Checks: {stats.get('total_compliance', 0)}",
                    f"Overdue Checks: {stats.get('overdue_compliance', 0)}",
                ]),
            ]
            row = 0
            for title, lines in sections:
                tk.Label(self._stats_frame, text=title, font=("Helvetica", 11, "bold"),
                         bg="#ecf0f1", anchor="w").grid(row=row, column=0, sticky="w", pady=(8, 2))
                row += 1
                for line in lines:
                    tk.Label(self._stats_frame, text=line, font=("Helvetica", 10),
                             bg="#ecf0f1", anchor="w").grid(row=row, column=0, sticky="w", padx=10)
                    row += 1
        except Exception as exc:
            tk.Label(self._stats_frame, text=f"Error loading stats: {exc}",
                     bg="#ecf0f1", fg="red").grid(row=0, column=0)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _selected_pk(self, tree) -> int | None:
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select an item first.")
            return None
        return int(sel[0])

    # ── Incident Actions ──────────────────────────────────────────────────

    def _on_add_incident(self):
        dlg = _IncidentDialog(self, title="New Incident")
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            data = dlg.result
            date = data.pop("incident_date", "")
            desc = data.pop("description", "")
            if not date or not desc:
                messagebox.showwarning("Validation", "Date and description are required.")
                return
            self._svc.create_incident(date, desc, **data)
            messagebox.showinfo("Success", "Incident created.")
            self._load_incidents()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_view_incident(self):
        pk = self._selected_pk(self._inc_tree)
        if pk is None:
            return
        item = self._svc.get_incident(pk)
        if not item:
            messagebox.showerror("Error", "Incident not found.")
            return
        _DetailDialog(self, "Incident Details", item)
        self.wait_window()

    def _on_edit_incident(self):
        pk = self._selected_pk(self._inc_tree)
        if pk is None:
            return
        item = self._svc.get_incident(pk)
        if not item:
            messagebox.showerror("Error", "Incident not found.")
            return
        dlg = _IncidentDialog(self, title="Update Incident", item=item)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.update_incident(pk, **dlg.result)
            messagebox.showinfo("Success", "Incident updated.")
            self._load_incidents()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_close_incident(self):
        pk = self._selected_pk(self._inc_tree)
        if pk is None:
            return
        dlg = _CloseIncidentDialog(self)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.close_incident(pk, dlg.result["root_cause"], dlg.result["corrective_actions"])
            messagebox.showinfo("Success", "Incident closed.")
            self._load_incidents()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_delete_incident(self):
        pk = self._selected_pk(self._inc_tree)
        if pk is None:
            return
        if not messagebox.askyesno("Confirm", "Delete this incident?"):
            return
        try:
            self._svc.delete_incident(pk)
            messagebox.showinfo("Success", "Incident deleted.")
            self._load_incidents()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    # ── Inspection Actions ────────────────────────────────────────────────

    def _on_add_inspection(self):
        dlg = _InspectionDialog(self, title="New Inspection")
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            data = dlg.result
            itype = data.pop("inspection_type", "")
            idate = data.pop("inspection_date", "")
            if not itype or not idate:
                messagebox.showwarning("Validation", "Type and date are required.")
                return
            self._svc.create_inspection(itype, idate, **data)
            messagebox.showinfo("Success", "Inspection created.")
            self._load_inspections()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_view_inspection(self):
        pk = self._selected_pk(self._insp_tree)
        if pk is None:
            return
        item = self._svc.get_inspection(pk)
        if not item:
            messagebox.showerror("Error", "Inspection not found.")
            return
        _DetailDialog(self, "Inspection Details", item)
        self.wait_window()

    def _on_edit_inspection(self):
        pk = self._selected_pk(self._insp_tree)
        if pk is None:
            return
        item = self._svc.get_inspection(pk)
        if not item:
            messagebox.showerror("Error", "Inspection not found.")
            return
        dlg = _InspectionDialog(self, title="Update Inspection", item=item)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.update_inspection(pk, **dlg.result)
            messagebox.showinfo("Success", "Inspection updated.")
            self._load_inspections()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_delete_inspection(self):
        pk = self._selected_pk(self._insp_tree)
        if pk is None:
            return
        if not messagebox.askyesno("Confirm", "Delete this inspection?"):
            return
        try:
            self._svc.delete_inspection(pk)
            messagebox.showinfo("Success", "Inspection deleted.")
            self._load_inspections()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    # ── Risk Assessment Actions ───────────────────────────────────────────

    def _on_add_risk_assessment(self):
        dlg = _RiskAssessmentDialog(self, title="New Risk Assessment")
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            data = dlg.result
            activity = data.pop("activity", "")
            adate = data.pop("assessment_date", "")
            if not activity or not adate:
                messagebox.showwarning("Validation", "Activity and date are required.")
                return
            self._svc.create_risk_assessment(activity, adate, **data)
            messagebox.showinfo("Success", "Risk assessment created.")
            self._load_risk_assessments()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_view_risk_assessment(self):
        pk = self._selected_pk(self._ra_tree)
        if pk is None:
            return
        item = self._svc.get_risk_assessment(pk)
        if not item:
            messagebox.showerror("Error", "Risk assessment not found.")
            return
        _DetailDialog(self, "Risk Assessment Details", item)
        self.wait_window()

    def _on_edit_risk_assessment(self):
        pk = self._selected_pk(self._ra_tree)
        if pk is None:
            return
        item = self._svc.get_risk_assessment(pk)
        if not item:
            messagebox.showerror("Error", "Risk assessment not found.")
            return
        dlg = _RiskAssessmentDialog(self, title="Update Risk Assessment", item=item)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.update_risk_assessment(pk, **dlg.result)
            messagebox.showinfo("Success", "Risk assessment updated.")
            self._load_risk_assessments()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_delete_risk_assessment(self):
        pk = self._selected_pk(self._ra_tree)
        if pk is None:
            return
        if not messagebox.askyesno("Confirm", "Delete this risk assessment?"):
            return
        try:
            self._svc.delete_risk_assessment(pk)
            messagebox.showinfo("Success", "Risk assessment deleted.")
            self._load_risk_assessments()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    # ── Compliance Check Actions ──────────────────────────────────────────

    def _on_add_compliance(self):
        dlg = _ComplianceCheckDialog(self, title="New Compliance Check")
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            data = dlg.result
            ctype = data.pop("check_type", "")
            if not ctype:
                messagebox.showwarning("Validation", "Check type is required.")
                return
            self._svc.create_compliance_check(ctype, **data)
            messagebox.showinfo("Success", "Compliance check created.")
            self._load_compliance_checks()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_edit_compliance(self):
        pk = self._selected_pk(self._cc_tree)
        if pk is None:
            return
        item = self._svc.get_compliance_check(pk)
        if not item:
            messagebox.showerror("Error", "Compliance check not found.")
            return
        dlg = _ComplianceCheckDialog(self, title="Update Compliance Check", item=item)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.update_compliance_check(pk, **dlg.result)
            messagebox.showinfo("Success", "Compliance check updated.")
            self._load_compliance_checks()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_delete_compliance(self):
        pk = self._selected_pk(self._cc_tree)
        if pk is None:
            return
        if not messagebox.askyesno("Confirm", "Delete this compliance check?"):
            return
        try:
            self._svc.delete_compliance_check(pk)
            messagebox.showinfo("Success", "Compliance check deleted.")
            self._load_compliance_checks()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_show_overdue(self):
        """Show only overdue compliance checks in the treeview."""
        self._cc_tree.delete(*self._cc_tree.get_children())
        try:
            items = self._svc.get_overdue_checks()
            for item in items:
                self._cc_tree.insert("", "end", iid=item["id"], values=(
                    item["id"],
                    item.get("check_type", ""),
                    item.get("responsible_person", ""),
                    item.get("frequency", ""),
                    item.get("last_completed", ""),
                    item.get("next_due", ""),
                    item.get("status", ""),
                ))
            if not items:
                messagebox.showinfo("Overdue Checks", "No overdue compliance checks found.")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load overdue checks:\n{exc}")
