"""Early Warning System GUI frame for managing student alerts and rules."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.early_warning.services.early_warning_service import EarlyWarningService

ALERT_TYPES = ["attendance", "grades", "behaviour", "engagement",
               "welfare", "safeguarding", "combined"]
SEVERITIES = ["low", "medium", "high", "critical"]
COMPARISONS = ["less_than", "greater_than", "equals"]
RULE_TYPES = ["attendance_pct", "grade_avg", "behaviour_incidents",
              "absent_sessions", "late_count"]


class EarlyWarningFrame(tk.Frame):
    """Early Warning System management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = EarlyWarningService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Early Warning System",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._alerts_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._alerts_tab, text="Alerts")
        self._build_alerts_tab()

        self._rules_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._rules_tab, text="Rules")
        self._build_rules_tab()

        self._stats_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._stats_tab, text="Statistics")
        self._build_stats_tab()

    # ---- Alerts Tab ----

    def _build_alerts_tab(self):
        toolbar = tk.Frame(self._alerts_tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text="Search:", bg="#ecf0f1").pack(side="left", padx=(5, 2))
        self._alert_search = tk.Entry(toolbar, width=14)
        self._alert_search.pack(side="left", padx=2)
        self._alert_search.bind("<Return>", lambda e: self._load_alerts())

        tk.Label(toolbar, text="Severity:", bg="#ecf0f1").pack(side="left", padx=(8, 2))
        self._alert_severity = ttk.Combobox(toolbar, width=8, state="readonly",
                                             values=[""] + SEVERITIES)
        self._alert_severity.set("")
        self._alert_severity.pack(side="left", padx=2)

        tk.Label(toolbar, text="Type:", bg="#ecf0f1").pack(side="left", padx=(8, 2))
        self._alert_type = ttk.Combobox(toolbar, width=10, state="readonly",
                                         values=[""] + ALERT_TYPES)
        self._alert_type.set("")
        self._alert_type.pack(side="left", padx=2)

        self._alert_resolved_var = tk.BooleanVar()
        ttk.Checkbutton(toolbar, text="Show Resolved",
                         variable=self._alert_resolved_var).pack(side="left", padx=8)

        ttk.Button(toolbar, text="Search", command=self._load_alerts).pack(side="left", padx=5)

        btn_frame = tk.Frame(self._alerts_tab, bg="#ecf0f1")
        btn_frame.pack(fill="x", padx=5, pady=(0, 5))
        ttk.Button(btn_frame, text="Refresh", command=self._load_alerts).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="New Alert", command=self._new_alert).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="View", command=self._view_alert).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Edit", command=self._edit_alert).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Resolve", command=self._resolve_alert).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Delete", command=self._delete_alert).pack(side="right", padx=2)

        cols = ("id", "student", "type", "severity", "trigger",
                "attendance", "resolved", "created")
        self._alert_tree = ttk.Treeview(self._alerts_tab, columns=cols,
                                         show="headings", height=15)
        for c, w, label in [
            ("id", 40, "ID"), ("student", 140, "Student"),
            ("type", 90, "Type"), ("severity", 70, "Severity"),
            ("trigger", 150, "Trigger"), ("attendance", 65, "Att %"),
            ("resolved", 65, "Resolved"), ("created", 130, "Created"),
        ]:
            self._alert_tree.heading(c, text=label)
            self._alert_tree.column(c, width=w,
                                     anchor="center" if w < 80 else "w")
        self._alert_tree.bind("<Double-1>", lambda e: self._view_alert())

        vsb = ttk.Scrollbar(self._alerts_tab, orient="vertical",
                             command=self._alert_tree.yview)
        self._alert_tree.configure(yscrollcommand=vsb.set)
        self._alert_tree.pack(side="left", fill="both", expand=True,
                               padx=(5, 0), pady=5)
        vsb.pack(side="right", fill="y", padx=(0, 5), pady=5)

    def _load_alerts(self):
        for item in self._alert_tree.get_children():
            self._alert_tree.delete(item)
        try:
            search = self._alert_search.get().strip() or None
            severity = self._alert_severity.get().strip() or None
            atype = self._alert_type.get().strip() or None
            resolved = None if self._alert_resolved_var.get() else 0
            alerts = self._svc.list_alerts(
                search=search, severity=severity, alert_type=atype,
                resolved=resolved)
            for a in alerts:
                name = f"{a.get('first_name', '')} {a.get('last_name', '')}".strip() or f"#{a.get('student_id', '')}"
                att = f"{a['attendance_pct']:.0f}%" if a.get("attendance_pct") is not None else ""
                self._alert_tree.insert("", "end", iid=a["id"], values=(
                    a["id"], name, a.get("alert_type", ""),
                    a.get("severity", ""), a.get("trigger_source", ""),
                    att, "Yes" if a.get("resolved") else "No",
                    a.get("created_at", "")))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _selected_alert_id(self):
        sel = self._alert_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select an alert first.")
            return None
        return int(sel[0])

    def _new_alert(self):
        win = tk.Toplevel(self)
        win.title("New Early Warning Alert")
        win.geometry("460x440")
        win.resizable(False, False)

        fields = {}
        row = 0
        for label, key in [
            ("Student ID*:", "student_id"),
            ("Trigger Source:", "trigger_source"),
            ("Trigger Detail:", "trigger_detail"),
            ("Attendance %:", "attendance_pct"),
            ("Behaviour Count:", "behaviour_count"),
            ("Recommended Action:", "recommended_action"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10,
                                            pady=4, sticky="e")
            e = tk.Entry(win, width=28)
            e.grid(row=row, column=1, padx=10, pady=4)
            fields[key] = e
            row += 1

        tk.Label(win, text="Alert Type*:").grid(row=row, column=0, padx=10,
                                                 pady=4, sticky="e")
        type_cb = ttk.Combobox(win, width=25, state="readonly",
                                values=ALERT_TYPES)
        type_cb.set("attendance")
        type_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text="Severity:").grid(row=row, column=0, padx=10,
                                              pady=4, sticky="e")
        sev_cb = ttk.Combobox(win, width=25, state="readonly",
                               values=SEVERITIES)
        sev_cb.set("medium")
        sev_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text="Grade Trend:").grid(row=row, column=0, padx=10,
                                                 pady=4, sticky="e")
        trend_cb = ttk.Combobox(win, width=25, state="readonly",
                                 values=["", "improving", "stable", "declining"])
        trend_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        def save():
            sid = fields["student_id"].get().strip()
            if not sid:
                messagebox.showwarning("Validation", "Student ID is required.")
                return
            try:
                att = fields["attendance_pct"].get().strip()
                bc = fields["behaviour_count"].get().strip()
                self._svc.create_alert(
                    int(sid), type_cb.get(),
                    severity=sev_cb.get(),
                    trigger_source=fields["trigger_source"].get().strip() or None,
                    trigger_detail=fields["trigger_detail"].get().strip() or None,
                    attendance_pct=float(att) if att else None,
                    grade_trend=trend_cb.get() or None,
                    behaviour_count=int(bc) if bc else None,
                    recommended_action=fields["recommended_action"].get().strip() or None)
                messagebox.showinfo("Success", "Alert created.")
                win.destroy()
                self._load_alerts()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _view_alert(self):
        aid = self._selected_alert_id()
        if not aid:
            return
        rec = self._svc.get_alert(aid)
        if not rec:
            messagebox.showwarning("Not Found", "Alert not found.")
            return

        win = tk.Toplevel(self)
        name = f"{rec.get('first_name', '')} {rec.get('last_name', '')}".strip()
        win.title(f"Alert #{aid}: {name}")
        win.geometry("460x480")
        win.resizable(False, False)

        att = f"{rec['attendance_pct']:.1f}%" if rec.get("attendance_pct") is not None else ""
        display = [
            ("ID", rec.get("id")),
            ("Student", name or f"#{rec.get('student_id')}"),
            ("Alert Type", rec.get("alert_type")),
            ("Severity", rec.get("severity")),
            ("Trigger Source", rec.get("trigger_source")),
            ("Trigger Detail", rec.get("trigger_detail")),
            ("Attendance %", att),
            ("Grade Trend", rec.get("grade_trend")),
            ("Behaviour Count", rec.get("behaviour_count")),
            ("Recommended Action", rec.get("recommended_action")),
            ("Action Taken", rec.get("action_taken")),
            ("Resolved", "Yes" if rec.get("resolved") else "No"),
            ("Resolved At", rec.get("resolved_at")),
            ("Created", rec.get("created_at")),
        ]

        frame = tk.Frame(win, padx=15, pady=10)
        frame.pack(fill="both", expand=True)
        for i, (lbl, val) in enumerate(display):
            tk.Label(frame, text=f"{lbl}:", font=("Helvetica", 10, "bold"),
                     anchor="e").grid(row=i, column=0, sticky="ne",
                                       padx=(0, 8), pady=2)
            tk.Label(frame, text=str(val or ""), anchor="w",
                     wraplength=300).grid(row=i, column=1, sticky="w", pady=2)

    def _edit_alert(self):
        aid = self._selected_alert_id()
        if not aid:
            return
        rec = self._svc.get_alert(aid)
        if not rec:
            messagebox.showwarning("Not Found", "Alert not found.")
            return

        win = tk.Toplevel(self)
        win.title(f"Edit Alert #{aid}")
        win.geometry("460x480")
        win.resizable(False, False)

        fields = {}
        row = 0
        for label, key in [
            ("Trigger Source:", "trigger_source"),
            ("Trigger Detail:", "trigger_detail"),
            ("Attendance %:", "attendance_pct"),
            ("Behaviour Count:", "behaviour_count"),
            ("Recommended Action:", "recommended_action"),
            ("Action Taken:", "action_taken"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10,
                                            pady=4, sticky="e")
            e = tk.Entry(win, width=28)
            val = rec.get(key, "")
            if val is not None:
                e.insert(0, str(val))
            e.grid(row=row, column=1, padx=10, pady=4)
            fields[key] = e
            row += 1

        tk.Label(win, text="Alert Type:").grid(row=row, column=0, padx=10,
                                                pady=4, sticky="e")
        type_cb = ttk.Combobox(win, width=25, state="readonly",
                                values=ALERT_TYPES)
        type_cb.set(rec.get("alert_type", "attendance"))
        type_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text="Severity:").grid(row=row, column=0, padx=10,
                                              pady=4, sticky="e")
        sev_cb = ttk.Combobox(win, width=25, state="readonly",
                               values=SEVERITIES)
        sev_cb.set(rec.get("severity", "medium"))
        sev_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text="Grade Trend:").grid(row=row, column=0, padx=10,
                                                 pady=4, sticky="e")
        trend_cb = ttk.Combobox(win, width=25, state="readonly",
                                 values=["", "improving", "stable", "declining"])
        trend_cb.set(rec.get("grade_trend", "") or "")
        trend_cb.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        def save():
            try:
                att = fields["attendance_pct"].get().strip()
                bc = fields["behaviour_count"].get().strip()
                self._svc.update_alert(
                    aid,
                    alert_type=type_cb.get(),
                    severity=sev_cb.get(),
                    trigger_source=fields["trigger_source"].get().strip() or None,
                    trigger_detail=fields["trigger_detail"].get().strip() or None,
                    attendance_pct=float(att) if att else None,
                    grade_trend=trend_cb.get() or None,
                    behaviour_count=int(bc) if bc else None,
                    recommended_action=fields["recommended_action"].get().strip() or None,
                    action_taken=fields["action_taken"].get().strip() or None)
                messagebox.showinfo("Success", "Alert updated.")
                win.destroy()
                self._load_alerts()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _resolve_alert(self):
        aid = self._selected_alert_id()
        if not aid:
            return

        win = tk.Toplevel(self)
        win.title(f"Resolve Alert #{aid}")
        win.geometry("400x180")
        win.resizable(False, False)

        tk.Label(win, text="Action Taken*:").grid(row=0, column=0, padx=10,
                                                   pady=10, sticky="ne")
        action_txt = tk.Text(win, width=28, height=4)
        action_txt.grid(row=0, column=1, padx=10, pady=10)

        def save():
            action = action_txt.get("1.0", "end-1c").strip()
            if not action:
                messagebox.showwarning("Validation", "Action taken is required.")
                return
            try:
                self._svc.resolve_alert(aid, action)
                messagebox.showinfo("Success", "Alert resolved.")
                win.destroy()
                self._load_alerts()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Resolve", command=save).grid(
            row=1, column=0, columnspan=2, pady=8)

    def _delete_alert(self):
        aid = self._selected_alert_id()
        if not aid:
            return
        if not messagebox.askyesno("Confirm", f"Delete alert #{aid}?"):
            return
        try:
            self._svc.delete_alert(aid)
            messagebox.showinfo("Deleted", "Alert deleted.")
            self._load_alerts()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---- Rules Tab ----

    def _build_rules_tab(self):
        toolbar = tk.Frame(self._rules_tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text="Refresh", command=self._load_rules).pack(side="left", padx=5)
        ttk.Button(toolbar, text="New Rule", command=self._new_rule).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Edit", command=self._edit_rule).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Delete", command=self._delete_rule).pack(side="right", padx=5)

        cols = ("id", "name", "type", "comparison", "threshold",
                "severity", "auto_assign", "active")
        self._rule_tree = ttk.Treeview(self._rules_tab, columns=cols,
                                        show="headings", height=16)
        for c, w, label in [
            ("id", 40, "ID"), ("name", 180, "Rule Name"),
            ("type", 110, "Type"), ("comparison", 90, "Comparison"),
            ("threshold", 70, "Threshold"), ("severity", 70, "Severity"),
            ("auto_assign", 100, "Auto-Assign"), ("active", 55, "Active"),
        ]:
            self._rule_tree.heading(c, text=label)
            self._rule_tree.column(c, width=w,
                                    anchor="center" if w < 100 else "w")

        vsb = ttk.Scrollbar(self._rules_tab, orient="vertical",
                             command=self._rule_tree.yview)
        self._rule_tree.configure(yscrollcommand=vsb.set)
        self._rule_tree.pack(side="left", fill="both", expand=True,
                              padx=(5, 0), pady=5)
        vsb.pack(side="right", fill="y", padx=(0, 5), pady=5)

    def _load_rules(self):
        for item in self._rule_tree.get_children():
            self._rule_tree.delete(item)
        try:
            rules = self._svc.list_rules()
            for r in rules:
                self._rule_tree.insert("", "end", iid=r["id"], values=(
                    r["id"], r.get("rule_name", ""), r.get("rule_type", ""),
                    r.get("comparison", ""), r.get("threshold", ""),
                    r.get("severity", ""), r.get("auto_assign_role", ""),
                    "Yes" if r.get("is_active") else "No"))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _new_rule(self):
        win = tk.Toplevel(self)
        win.title("New Early Warning Rule")
        win.geometry("420x340")
        win.resizable(False, False)

        row = 0
        tk.Label(win, text="Rule Name*:").grid(row=row, column=0, padx=10,
                                                pady=5, sticky="e")
        name_e = tk.Entry(win, width=26)
        name_e.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text="Rule Type*:").grid(row=row, column=0, padx=10,
                                                pady=5, sticky="e")
        type_cb = ttk.Combobox(win, width=23, state="readonly",
                                values=RULE_TYPES)
        type_cb.set("attendance_pct")
        type_cb.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text="Threshold*:").grid(row=row, column=0, padx=10,
                                                pady=5, sticky="e")
        thresh_e = tk.Entry(win, width=10)
        thresh_e.grid(row=row, column=1, padx=10, pady=5, sticky="w")
        row += 1

        tk.Label(win, text="Comparison:").grid(row=row, column=0, padx=10,
                                                pady=5, sticky="e")
        comp_cb = ttk.Combobox(win, width=23, state="readonly",
                                values=COMPARISONS)
        comp_cb.set("less_than")
        comp_cb.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text="Severity:").grid(row=row, column=0, padx=10,
                                              pady=5, sticky="e")
        sev_cb = ttk.Combobox(win, width=23, state="readonly",
                               values=SEVERITIES)
        sev_cb.set("medium")
        sev_cb.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text="Auto-Assign Role:").grid(row=row, column=0,
                                                      padx=10, pady=5, sticky="e")
        role_e = tk.Entry(win, width=26)
        role_e.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        active_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(win, text="Active", variable=active_var).grid(
            row=row, column=1, sticky="w", padx=10, pady=2)
        row += 1

        def save():
            name = name_e.get().strip()
            thresh = thresh_e.get().strip()
            if not name or not thresh:
                messagebox.showwarning("Validation",
                                        "Rule name and threshold are required.")
                return
            try:
                self._svc.create_rule(
                    name, type_cb.get(), float(thresh),
                    comparison=comp_cb.get(), severity=sev_cb.get(),
                    auto_assign_role=role_e.get().strip() or None,
                    is_active=1 if active_var.get() else 0)
                messagebox.showinfo("Success", "Rule created.")
                win.destroy()
                self._load_rules()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _edit_rule(self):
        sel = self._rule_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a rule first.")
            return
        rid = int(sel[0])
        rec = self._svc.get_rule(rid)
        if not rec:
            return

        win = tk.Toplevel(self)
        win.title(f"Edit Rule #{rid}")
        win.geometry("420x340")
        win.resizable(False, False)

        row = 0
        tk.Label(win, text="Rule Name*:").grid(row=row, column=0, padx=10,
                                                pady=5, sticky="e")
        name_e = tk.Entry(win, width=26)
        name_e.insert(0, rec.get("rule_name", ""))
        name_e.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text="Rule Type:").grid(row=row, column=0, padx=10,
                                               pady=5, sticky="e")
        type_cb = ttk.Combobox(win, width=23, state="readonly",
                                values=RULE_TYPES)
        type_cb.set(rec.get("rule_type", "attendance_pct"))
        type_cb.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text="Threshold:").grid(row=row, column=0, padx=10,
                                               pady=5, sticky="e")
        thresh_e = tk.Entry(win, width=10)
        thresh_e.insert(0, str(rec.get("threshold", "")))
        thresh_e.grid(row=row, column=1, padx=10, pady=5, sticky="w")
        row += 1

        tk.Label(win, text="Comparison:").grid(row=row, column=0, padx=10,
                                                pady=5, sticky="e")
        comp_cb = ttk.Combobox(win, width=23, state="readonly",
                                values=COMPARISONS)
        comp_cb.set(rec.get("comparison", "less_than"))
        comp_cb.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text="Severity:").grid(row=row, column=0, padx=10,
                                              pady=5, sticky="e")
        sev_cb = ttk.Combobox(win, width=23, state="readonly",
                               values=SEVERITIES)
        sev_cb.set(rec.get("severity", "medium"))
        sev_cb.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        tk.Label(win, text="Auto-Assign Role:").grid(row=row, column=0,
                                                      padx=10, pady=5, sticky="e")
        role_e = tk.Entry(win, width=26)
        role_e.insert(0, rec.get("auto_assign_role", "") or "")
        role_e.grid(row=row, column=1, padx=10, pady=5)
        row += 1

        active_var = tk.BooleanVar(value=bool(rec.get("is_active")))
        ttk.Checkbutton(win, text="Active", variable=active_var).grid(
            row=row, column=1, sticky="w", padx=10, pady=2)
        row += 1

        def save():
            try:
                self._svc.update_rule(
                    rid,
                    rule_name=name_e.get().strip(),
                    rule_type=type_cb.get(),
                    threshold=float(thresh_e.get().strip()),
                    comparison=comp_cb.get(),
                    severity=sev_cb.get(),
                    auto_assign_role=role_e.get().strip() or None,
                    is_active=1 if active_var.get() else 0)
                messagebox.showinfo("Success", "Rule updated.")
                win.destroy()
                self._load_rules()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=12)

    def _delete_rule(self):
        sel = self._rule_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a rule first.")
            return
        rid = int(sel[0])
        if not messagebox.askyesno("Confirm", f"Delete rule #{rid}?"):
            return
        try:
            self._svc.delete_rule(rid)
            messagebox.showinfo("Deleted", "Rule deleted.")
            self._load_rules()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---- Statistics Tab ----

    def _build_stats_tab(self):
        self._stats_frame = tk.Frame(self._stats_tab, bg="#ecf0f1",
                                      padx=20, pady=20)
        self._stats_frame.pack(fill="both", expand=True)

        ttk.Button(self._stats_frame, text="Refresh Statistics",
                   command=self._load_stats).pack(anchor="w", pady=(0, 15))

        self._stats_labels = {}
        for key, label in [
            ("total_alerts", "Total Alerts"),
            ("active_alerts", "Active (Unresolved)"),
            ("resolved_alerts", "Resolved"),
            ("active_rules", "Active Rules"),
        ]:
            row_frame = tk.Frame(self._stats_frame, bg="#ecf0f1")
            row_frame.pack(fill="x", pady=3)
            tk.Label(row_frame, text=f"{label}:",
                     font=("Helvetica", 11, "bold"), bg="#ecf0f1",
                     width=22, anchor="e").pack(side="left")
            lbl = tk.Label(row_frame, text="—", font=("Helvetica", 11),
                           bg="#ecf0f1", anchor="w")
            lbl.pack(side="left", padx=(10, 0))
            self._stats_labels[key] = lbl

        tk.Label(self._stats_frame, text="Active by Severity:",
                 font=("Helvetica", 11, "bold"), bg="#ecf0f1"
                 ).pack(anchor="w", pady=(15, 5))
        self._sev_lbl = tk.Label(self._stats_frame, text="—",
                                  font=("Helvetica", 10), bg="#ecf0f1",
                                  justify="left", anchor="w")
        self._sev_lbl.pack(anchor="w", padx=(20, 0))

        tk.Label(self._stats_frame, text="Active by Type:",
                 font=("Helvetica", 11, "bold"), bg="#ecf0f1"
                 ).pack(anchor="w", pady=(10, 5))
        self._type_lbl = tk.Label(self._stats_frame, text="—",
                                   font=("Helvetica", 10), bg="#ecf0f1",
                                   justify="left", anchor="w")
        self._type_lbl.pack(anchor="w", padx=(20, 0))

    def _load_stats(self):
        try:
            stats = self._svc.get_stats()
            for key, lbl in self._stats_labels.items():
                lbl.config(text=str(stats.get(key, 0)))
            by_sev = stats.get("active_by_severity", {})
            self._sev_lbl.config(
                text="\n".join(f"{k}: {v}" for k, v in by_sev.items()) or "No data")
            by_type = stats.get("active_by_type", {})
            self._type_lbl.config(
                text="\n".join(f"{k}: {v}" for k, v in by_type.items()) or "No data")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refresh(self):
        self._load_alerts()
        self._load_rules()
        self._load_stats()
