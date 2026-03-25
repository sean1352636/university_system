"""IQR Manager GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.college_system.modules.domain.iqr_manager.services.iqr_manager_service import (
    IQRManagerService,
)
from education_system.college_system.core.i18n import t


class IQRManagerFrame(tk.Frame):
    """GUI for Internal Quality Review management."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = IQRManagerService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text=t("iqr_manager.title", "Internal Quality Review Manager"),
            font=("Helvetica", 15, "bold"),
            bg="#2c3e50",
            fg="white",
        ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_cycles_tab()
        self._build_visits_tab()
        self._build_actions_tab()
        self._build_reports_tab()

    # ── Review Cycles Tab ──

    def _build_cycles_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("iqr_manager.cycles", "Review Cycles"))

        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text=t("iqr_manager.year", "Year:"), bg="#ecf0f1").pack(side="left", padx=2)
        self._cycle_year = ttk.Entry(toolbar, width=12)
        self._cycle_year.pack(side="left", padx=2)

        ttk.Button(toolbar, text=t("iqr_manager.search", "Search"), command=self._load_cycles).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("iqr_manager.new_cycle", "New Cycle"), command=self._new_cycle_dialog).pack(side="left", padx=5)

        cols = ("id", "academic_year", "cycle_name", "start_date", "end_date", "status", "focus_areas")
        self._cycles_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c in cols:
            self._cycles_tree.heading(c, text=c.replace("_", " ").title())
            self._cycles_tree.column(c, width=120)
        self._cycles_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _load_cycles(self):
        for row in self._cycles_tree.get_children():
            self._cycles_tree.delete(row)
        try:
            yr = self._cycle_year.get().strip() or None
            cycles = self._svc.list_cycles(academic_year=yr)
            for c in cycles:
                self._cycles_tree.insert("", "end", values=(
                    c["id"], c.get("academic_year", ""), c["cycle_name"],
                    c.get("start_date", ""), c.get("end_date", ""),
                    c["status"], c.get("focus_areas", ""),
                ))
        except Exception as exc:
            messagebox.showerror(t("iqr_manager.error", "Error"), str(exc))

    def _new_cycle_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("iqr_manager.new_cycle", "New Review Cycle"))
        dlg.geometry("400x300")
        dlg.transient(self)

        fields = {}
        for i, (label, key) in enumerate([
            ("Academic Year:", "academic_year"),
            ("Cycle Name:", "cycle_name"),
            ("Start Date:", "start_date"),
            ("End Date:", "end_date"),
            ("Focus Areas:", "focus_areas"),
        ]):
            tk.Label(dlg, text=label).grid(row=i, column=0, padx=10, pady=5, sticky="e")
            w = ttk.Entry(dlg, width=25)
            w.grid(row=i, column=1, padx=10, pady=5)
            fields[key] = w

        def _save():
            try:
                user_id = self._auth.get("user_id", 0) if self._auth else 0
                self._svc.create_cycle(
                    fields["academic_year"].get().strip(),
                    fields["cycle_name"].get().strip(),
                    fields["start_date"].get().strip(),
                    fields["end_date"].get().strip(),
                    fields["focus_areas"].get().strip(),
                    user_id,
                )
                dlg.destroy()
                self._load_cycles()
                messagebox.showinfo(t("iqr_manager.success", "Success"), t("iqr_manager.cycle_created", "Cycle created."))
            except Exception as exc:
                messagebox.showerror(t("iqr_manager.error", "Error"), str(exc))

        ttk.Button(dlg, text=t("iqr_manager.save", "Save"), command=_save).grid(row=5, column=0, columnspan=2, pady=15)

    # ── Visit Schedule Tab ──

    def _build_visits_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("iqr_manager.visits", "Visit Schedule"))

        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text=t("iqr_manager.cycle_id", "Cycle ID:"), bg="#ecf0f1").pack(side="left", padx=2)
        self._visit_cycle_id = ttk.Entry(toolbar, width=8)
        self._visit_cycle_id.pack(side="left", padx=2)

        tk.Label(toolbar, text=t("iqr_manager.dept", "Dept:"), bg="#ecf0f1").pack(side="left", padx=2)
        self._visit_dept = ttk.Entry(toolbar, width=12)
        self._visit_dept.pack(side="left", padx=2)

        tk.Label(toolbar, text=t("iqr_manager.status", "Status:"), bg="#ecf0f1").pack(side="left", padx=2)
        self._visit_status = ttk.Combobox(toolbar, values=["", "scheduled", "completed", "cancelled"], width=12, state="readonly")
        self._visit_status.set("")
        self._visit_status.pack(side="left", padx=2)

        ttk.Button(toolbar, text=t("iqr_manager.search", "Search"), command=self._load_visits).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("iqr_manager.schedule", "Schedule Visit"), command=self._schedule_visit_dialog).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("iqr_manager.complete", "Complete Visit"), command=self._complete_visit_dialog).pack(side="left", padx=5)

        cols = ("id", "cycle_id", "department", "visit_date", "reviewer_id", "visit_type", "overall_judgement", "status")
        self._visits_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c in cols:
            self._visits_tree.heading(c, text=c.replace("_", " ").title())
            self._visits_tree.column(c, width=110)
        self._visits_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _load_visits(self):
        for row in self._visits_tree.get_children():
            self._visits_tree.delete(row)
        try:
            cid = self._visit_cycle_id.get().strip()
            cid = int(cid) if cid and cid.isdigit() else None
            dept = self._visit_dept.get().strip() or None
            status = self._visit_status.get() or None
            visits = self._svc.list_visits(cycle_id=cid, department=dept, status=status)
            for v in visits:
                self._visits_tree.insert("", "end", values=(
                    v["id"], v.get("cycle_id", ""), v.get("department", ""),
                    v.get("visit_date", ""), v.get("reviewer_id", ""),
                    v.get("visit_type", ""), v.get("overall_judgement", ""),
                    v["status"],
                ))
        except Exception as exc:
            messagebox.showerror(t("iqr_manager.error", "Error"), str(exc))

    def _schedule_visit_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("iqr_manager.schedule_visit", "Schedule Visit"))
        dlg.geometry("400x320")
        dlg.transient(self)

        fields = {}
        labels = [
            ("Cycle ID:", "cycle_id"), ("Department:", "department"),
            ("Visit Date:", "visit_date"), ("Reviewer ID:", "reviewer_id"),
            ("Visit Type:", "visit_type"), ("Course ID (opt):", "course_id"),
        ]
        for i, (label, key) in enumerate(labels):
            tk.Label(dlg, text=label).grid(row=i, column=0, padx=10, pady=5, sticky="e")
            if key == "visit_type":
                w = ttk.Combobox(dlg, values=[
                    "learning_walk", "deep_dive", "work_scrutiny", "student_voice", "staff_interview",
                ], state="readonly", width=20)
                w.set("learning_walk")
            else:
                w = ttk.Entry(dlg, width=22)
            w.grid(row=i, column=1, padx=10, pady=5)
            fields[key] = w

        def _save():
            try:
                cid = int(fields["course_id"].get().strip()) if fields["course_id"].get().strip() else None
                self._svc.schedule_visit(
                    cycle_id=int(fields["cycle_id"].get().strip()),
                    department=fields["department"].get().strip(),
                    visit_date=fields["visit_date"].get().strip(),
                    reviewer_id=int(fields["reviewer_id"].get().strip()),
                    visit_type=fields["visit_type"].get(),
                    course_id=cid,
                )
                dlg.destroy()
                self._load_visits()
                messagebox.showinfo(t("iqr_manager.success", "Success"), t("iqr_manager.visit_scheduled", "Visit scheduled."))
            except Exception as exc:
                messagebox.showerror(t("iqr_manager.error", "Error"), str(exc))

        ttk.Button(dlg, text=t("iqr_manager.save", "Save"), command=_save).grid(row=len(labels), column=0, columnspan=2, pady=15)

    def _complete_visit_dialog(self):
        sel = self._visits_tree.selection()
        if not sel:
            messagebox.showwarning(t("iqr_manager.warning", "Warning"), t("iqr_manager.select_visit", "Select a visit."))
            return
        visit_id = self._visits_tree.item(sel[0], "values")[0]

        dlg = tk.Toplevel(self)
        dlg.title(t("iqr_manager.complete_visit", "Complete Visit"))
        dlg.geometry("500x400")
        dlg.transient(self)

        tk.Label(dlg, text="Findings:").grid(row=0, column=0, padx=10, pady=5, sticky="ne")
        findings = tk.Text(dlg, height=3, width=40)
        findings.grid(row=0, column=1, padx=10, pady=5)

        tk.Label(dlg, text="Strengths:").grid(row=1, column=0, padx=10, pady=5, sticky="ne")
        strengths = tk.Text(dlg, height=3, width=40)
        strengths.grid(row=1, column=1, padx=10, pady=5)

        tk.Label(dlg, text="Areas for Improvement:").grid(row=2, column=0, padx=10, pady=5, sticky="ne")
        afi = tk.Text(dlg, height=3, width=40)
        afi.grid(row=2, column=1, padx=10, pady=5)

        tk.Label(dlg, text="Overall Judgement:").grid(row=3, column=0, padx=10, pady=5, sticky="e")
        judgement = ttk.Combobox(dlg, values=["outstanding", "good", "requires_improvement", "inadequate"], state="readonly", width=22)
        judgement.set("good")
        judgement.grid(row=3, column=1, padx=10, pady=5)

        def _save():
            try:
                self._svc.complete_visit(
                    int(visit_id),
                    findings.get("1.0", "end").strip(),
                    strengths.get("1.0", "end").strip(),
                    afi.get("1.0", "end").strip(),
                    judgement.get(),
                )
                dlg.destroy()
                self._load_visits()
                messagebox.showinfo(t("iqr_manager.success", "Success"), t("iqr_manager.visit_completed", "Visit completed."))
            except Exception as exc:
                messagebox.showerror(t("iqr_manager.error", "Error"), str(exc))

        ttk.Button(dlg, text=t("iqr_manager.save", "Save"), command=_save).grid(row=4, column=0, columnspan=2, pady=15)

    # ── Action Plans Tab ──

    def _build_actions_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("iqr_manager.actions", "Action Plans"))

        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        tk.Label(toolbar, text=t("iqr_manager.visit_id", "Visit ID:"), bg="#ecf0f1").pack(side="left", padx=2)
        self._action_visit_id = ttk.Entry(toolbar, width=8)
        self._action_visit_id.pack(side="left", padx=2)

        tk.Label(toolbar, text=t("iqr_manager.status", "Status:"), bg="#ecf0f1").pack(side="left", padx=2)
        self._action_status = ttk.Combobox(toolbar, values=["", "not_started", "in_progress", "completed", "overdue"], width=14, state="readonly")
        self._action_status.set("")
        self._action_status.pack(side="left", padx=2)

        ttk.Button(toolbar, text=t("iqr_manager.search", "Search"), command=self._load_actions).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("iqr_manager.new_action", "New Action"), command=self._new_action_dialog).pack(side="left", padx=5)
        ttk.Button(toolbar, text=t("iqr_manager.update_progress", "Update Progress"), command=self._update_progress_dialog).pack(side="left", padx=5)

        cols = ("id", "visit_id", "action_description", "responsible_person", "target_date", "status", "progress")
        self._actions_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        for c in cols:
            self._actions_tree.heading(c, text=c.replace("_", " ").title())
            self._actions_tree.column(c, width=120)
        self._actions_tree.pack(fill="both", expand=True, padx=5, pady=5)

    def _load_actions(self):
        for row in self._actions_tree.get_children():
            self._actions_tree.delete(row)
        try:
            vid = self._action_visit_id.get().strip()
            vid = int(vid) if vid and vid.isdigit() else None
            status = self._action_status.get() or None
            actions = self._svc.list_action_plans(visit_id=vid, status=status)
            for a in actions:
                desc = (a.get("action_description") or "")[:50]
                self._actions_tree.insert("", "end", values=(
                    a["id"], a.get("visit_id", ""), desc,
                    a.get("responsible_person", ""), a.get("target_date", ""),
                    a["status"], (a.get("progress") or "")[:30],
                ))
        except Exception as exc:
            messagebox.showerror(t("iqr_manager.error", "Error"), str(exc))

    def _new_action_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("iqr_manager.new_action", "New Action Plan"))
        dlg.geometry("450x320")
        dlg.transient(self)

        fields = {}
        for i, (label, key) in enumerate([
            ("Visit ID:", "visit_id"),
            ("Responsible Person:", "responsible_person"),
            ("Target Date:", "target_date"),
            ("Success Criteria:", "success_criteria"),
        ]):
            tk.Label(dlg, text=label).grid(row=i, column=0, padx=10, pady=5, sticky="e")
            w = ttk.Entry(dlg, width=25)
            w.grid(row=i, column=1, padx=10, pady=5)
            fields[key] = w

        tk.Label(dlg, text="Action Description:").grid(row=4, column=0, padx=10, pady=5, sticky="ne")
        desc_text = tk.Text(dlg, height=4, width=30)
        desc_text.grid(row=4, column=1, padx=10, pady=5)

        def _save():
            try:
                self._svc.create_action_plan(
                    int(fields["visit_id"].get().strip()),
                    desc_text.get("1.0", "end").strip(),
                    fields["responsible_person"].get().strip(),
                    fields["target_date"].get().strip(),
                    fields["success_criteria"].get().strip(),
                )
                dlg.destroy()
                self._load_actions()
                messagebox.showinfo(t("iqr_manager.success", "Success"), t("iqr_manager.action_created", "Action plan created."))
            except Exception as exc:
                messagebox.showerror(t("iqr_manager.error", "Error"), str(exc))

        ttk.Button(dlg, text=t("iqr_manager.save", "Save"), command=_save).grid(row=5, column=0, columnspan=2, pady=15)

    def _update_progress_dialog(self):
        sel = self._actions_tree.selection()
        if not sel:
            messagebox.showwarning(t("iqr_manager.warning", "Warning"), t("iqr_manager.select_action", "Select an action plan."))
            return
        action_id = self._actions_tree.item(sel[0], "values")[0]

        dlg = tk.Toplevel(self)
        dlg.title(t("iqr_manager.update_progress", "Update Progress"))
        dlg.geometry("400x280")
        dlg.transient(self)

        tk.Label(dlg, text="Progress:").grid(row=0, column=0, padx=10, pady=5, sticky="ne")
        progress_text = tk.Text(dlg, height=4, width=30)
        progress_text.grid(row=0, column=1, padx=10, pady=5)

        tk.Label(dlg, text="Evidence:").grid(row=1, column=0, padx=10, pady=5, sticky="ne")
        evidence_text = tk.Text(dlg, height=3, width=30)
        evidence_text.grid(row=1, column=1, padx=10, pady=5)

        tk.Label(dlg, text="Status:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        status_combo = ttk.Combobox(dlg, values=["not_started", "in_progress", "completed", "overdue"], state="readonly", width=18)
        status_combo.set("in_progress")
        status_combo.grid(row=2, column=1, padx=10, pady=5)

        def _save():
            try:
                self._svc.update_action_progress(
                    int(action_id),
                    progress_text.get("1.0", "end").strip(),
                    evidence=evidence_text.get("1.0", "end").strip() or None,
                    status=status_combo.get(),
                )
                dlg.destroy()
                self._load_actions()
            except Exception as exc:
                messagebox.showerror(t("iqr_manager.error", "Error"), str(exc))

        ttk.Button(dlg, text=t("iqr_manager.save", "Save"), command=_save).grid(row=3, column=0, columnspan=2, pady=15)

    # ── Reports Tab ──

    def _build_reports_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text=t("iqr_manager.reports", "Reports"))

        frame = tk.Frame(tab, bg="#ecf0f1")
        frame.pack(padx=20, pady=20, fill="x")

        tk.Label(frame, text=t("iqr_manager.cycle_id", "Cycle ID:"), bg="#ecf0f1").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self._report_cycle_id = ttk.Entry(frame, width=10)
        self._report_cycle_id.grid(row=0, column=1, padx=5, pady=5)

        ttk.Button(frame, text=t("iqr_manager.generate_report", "Generate Report"), command=self._generate_report).grid(row=0, column=2, padx=5, pady=5)

        self._report_output = tk.Text(tab, height=20, wrap="word")
        self._report_output.pack(fill="both", expand=True, padx=20, pady=10)

    def _generate_report(self):
        val = self._report_cycle_id.get().strip()
        if not val or not val.isdigit():
            messagebox.showwarning(t("iqr_manager.warning", "Warning"), t("iqr_manager.enter_cycle_id", "Enter a valid Cycle ID."))
            return
        try:
            stats = self._svc.get_cycle_stats(int(val))
            self._report_output.delete("1.0", "end")
            self._report_output.insert("end", f"IQR Cycle Report - Cycle {val}\n{'='*50}\n\n")
            self._report_output.insert("end", f"Total Visits: {stats['total_visits']}\n")
            self._report_output.insert("end", "Visit Status:\n")
            for s, c in stats.get("visit_status", {}).items():
                self._report_output.insert("end", f"  {s}: {c}\n")
            self._report_output.insert("end", "\nJudgement Distribution:\n")
            for j, c in stats.get("judgement_distribution", {}).items():
                self._report_output.insert("end", f"  {j}: {c}\n")
            self._report_output.insert("end", f"\nTotal Actions: {stats['total_actions']}\n")
            self._report_output.insert("end", "Action Status:\n")
            for s, c in stats.get("action_status", {}).items():
                self._report_output.insert("end", f"  {s}: {c}\n")
        except Exception as exc:
            messagebox.showerror(t("iqr_manager.error", "Error"), str(exc))

    def refresh(self):
        """Reload data in all tabs."""
        self._load_cycles()
        self._load_visits()
        self._load_actions()
