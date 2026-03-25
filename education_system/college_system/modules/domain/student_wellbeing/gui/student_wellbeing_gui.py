"""Student Wellbeing GUI module."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.core.i18n import t
from education_system.college_system.modules.domain.student_wellbeing.services.student_wellbeing_service import (
    StudentWellbeingService,
)


class StudentWellbeingFrame(tk.Frame):
    """Student Wellbeing management frame with referrals, logs, sessions, and stats."""

    REFERRAL_TYPES = ("internal", "external", "self")
    CONCERN_CATEGORIES = (
        "", "anxiety", "depression", "family", "bullying", "financial",
        "housing", "substance", "bereavement", "eating_disorder", "self_harm", "other",
    )
    RISK_LEVELS = ("", "low", "medium", "high", "critical")
    REFERRAL_STATUSES = ("", "open", "in_progress", "referred_externally", "resolved", "closed")
    SLEEP_QUALITIES = ("", "poor", "fair", "good", "excellent")
    FOLLOW_UP_OPTIONS = ("", "Yes", "No")
    SESSION_TYPES = ("", "individual", "group", "crisis", "drop_in")
    SESSION_STATUSES = ("", "scheduled", "completed", "cancelled", "no_show")

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = StudentWellbeingService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text=t("student_wellbeing.management"),
            font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white",
        ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_referrals_tab()
        self._build_logs_tab()
        self._build_sessions_tab()
        self._build_stats_tab()

    # ================================================================
    # Tab 1: Referrals
    # ================================================================

    def _build_referrals_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("student_wellbeing.referrals"))

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))

        tk.Label(filt, text=t("common.status") + ":", bg="#ecf0f1").pack(side="left", padx=(0, 3))
        self._ref_status_var = tk.StringVar()
        ttk.Combobox(filt, textvariable=self._ref_status_var,
                      values=self.REFERRAL_STATUSES, width=14, state="readonly"
                      ).pack(side="left", padx=(0, 10))

        tk.Label(filt, text=t("student_wellbeing.risk") + ":", bg="#ecf0f1").pack(side="left", padx=(0, 3))
        self._ref_risk_var = tk.StringVar()
        ttk.Combobox(filt, textvariable=self._ref_risk_var,
                      values=self.RISK_LEVELS, width=10, state="readonly"
                      ).pack(side="left", padx=(0, 10))

        tk.Label(filt, text=t("common.category") + ":", bg="#ecf0f1").pack(side="left", padx=(0, 3))
        self._ref_cat_var = tk.StringVar()
        ttk.Combobox(filt, textvariable=self._ref_cat_var,
                      values=self.CONCERN_CATEGORIES, width=14, state="readonly"
                      ).pack(side="left", padx=(0, 10))

        ttk.Button(filt, text=t("common.filter"), command=self._load_referrals).pack(side="left", padx=3)
        ttk.Button(filt, text=t("common.clear"), command=self._clear_ref_filters).pack(side="left", padx=3)

        # Treeview
        cols = ("id", "student_id", "type", "category", "risk_level", "status", "appointment")
        tree_frame = tk.Frame(tab, bg="#ecf0f1")
        tree_frame.pack(fill="both", expand=True)

        self._ref_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", t("common.id"), 40), ("student_id", t("common.student_id"), 70),
                         ("type", t("common.type"), 80), ("category", t("common.category"), 110),
                         ("risk_level", t("student_wellbeing.risk_level"), 80),
                         ("status", t("common.status"), 100),
                         ("appointment", t("student_wellbeing.appointment"), 100)]:
            self._ref_tree.heading(c, text=h)
            self._ref_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._ref_tree.yview)
        self._ref_tree.configure(yscrollcommand=vsb.set)
        self._ref_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Buttons
        btn = tk.Frame(tab, bg="#ecf0f1")
        btn.pack(fill="x", pady=(5, 0))
        ttk.Button(btn, text=t("common.new"), command=self._new_referral).pack(side="left", padx=3)
        ttk.Button(btn, text=t("common.view"), command=self._view_referral).pack(side="left", padx=3)
        ttk.Button(btn, text=t("common.update"), command=self._update_referral).pack(side="left", padx=3)
        ttk.Button(btn, text=t("student_wellbeing.resolve"), command=self._resolve_referral).pack(side="left", padx=3)
        ttk.Button(btn, text=t("common.delete"), command=self._delete_referral).pack(side="left", padx=3)
        ttk.Button(btn, text="Export CSV", command=self._export_referrals_csv).pack(side="left", padx=3)
        ttk.Button(btn, text=t("student_wellbeing.high_risk"), command=self._show_high_risk).pack(side="right", padx=3)

    def _clear_ref_filters(self):
        self._ref_status_var.set("")
        self._ref_risk_var.set("")
        self._ref_cat_var.set("")
        self._load_referrals()

    def _load_referrals(self):
        self._ref_tree.delete(*self._ref_tree.get_children())
        try:
            status = self._ref_status_var.get() or None
            risk = self._ref_risk_var.get() or None
            cat = self._ref_cat_var.get() or None
            items = self._svc.list_referrals(status=status, risk_level=risk, concern_category=cat)
            for r in items:
                self._ref_tree.insert("", "end", values=(
                    r["id"], r["student_id"], r.get("referral_type", ""),
                    r.get("concern_category", ""), r.get("risk_level", ""),
                    r.get("status", ""), r.get("appointment_date", "") or "",
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _selected_referral_id(self):
        sel = self._ref_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"))
            return None
        return self._ref_tree.item(sel[0], "values")[0]

    def _new_referral(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("student_wellbeing.new_referral"))
        dlg.geometry("450x520")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key, widget_type, opts in [
            (t("common.student_id") + "*:", "student_id", "entry", {}),
            (t("student_wellbeing.referral_type") + ":", "referral_type", "combo", {"values": self.REFERRAL_TYPES}),
            (t("common.category") + ":", "concern_category", "combo", {"values": self.CONCERN_CATEGORIES[1:]}),
            (t("student_wellbeing.risk_level") + ":", "risk_level", "combo", {"values": self.RISK_LEVELS[1:]}),
            (t("student_wellbeing.service_referred_to") + ":", "service_referred_to", "entry", {}),
            (t("student_wellbeing.external_agency") + ":", "external_agency", "entry", {}),
            (t("student_wellbeing.consent_obtained") + ":", "consent_obtained", "check", {}),
            (t("student_wellbeing.appointment_date") + ":", "appointment_date", "entry", {}),
        ]:
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=row, column=0, sticky="w", padx=10, pady=3)
            if widget_type == "entry":
                var = tk.StringVar()
                tk.Entry(dlg, textvariable=var, width=30).grid(row=row, column=1, padx=10, pady=3)
                fields[key] = var
            elif widget_type == "combo":
                var = tk.StringVar()
                ttk.Combobox(dlg, textvariable=var, values=opts["values"],
                              width=27, state="readonly").grid(row=row, column=1, padx=10, pady=3)
                fields[key] = var
            elif widget_type == "check":
                var = tk.IntVar()
                tk.Checkbutton(dlg, variable=var, bg="#ecf0f1").grid(row=row, column=1, sticky="w", padx=10, pady=3)
                fields[key] = var
            row += 1

        tk.Label(dlg, text=t("student_wellbeing.concern_details") + "*:", bg="#ecf0f1").grid(row=row, column=0, sticky="nw", padx=10, pady=3)
        details_text = tk.Text(dlg, width=30, height=5)
        details_text.grid(row=row, column=1, padx=10, pady=3)

        def save():
            sid = fields["student_id"].get().strip()
            details = details_text.get("1.0", "end").strip()
            if not sid or not details:
                messagebox.showwarning(t("common.validation"), t("common.both_required"))
                return
            try:
                kwargs = {}
                for k in ("referral_type", "concern_category", "risk_level",
                          "service_referred_to", "external_agency", "appointment_date"):
                    v = fields[k].get().strip() if hasattr(fields[k], "get") else ""
                    if v:
                        kwargs[k] = v
                consent_val = fields["consent_obtained"].get()
                if consent_val:
                    kwargs["consent_obtained"] = consent_val
                if self._auth and hasattr(self._auth, "current_user"):
                    kwargs["referred_by"] = self._auth.current_user.get("user_id")
                self._svc.create_referral(int(sid), details, **kwargs)
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                dlg.destroy()
                self._load_referrals()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("common.save"), command=save).grid(row=row + 1, column=0, columnspan=2, pady=10)

    def _view_referral(self):
        rid = self._selected_referral_id()
        if not rid:
            return
        try:
            r = self._svc.get_referral(int(rid))
            if not r:
                messagebox.showwarning(t("common.warning"), t("common.no_data"))
                return
            dlg = tk.Toplevel(self)
            dlg.title(f"{t('student_wellbeing.referral')} #{r['id']}")
            dlg.geometry("500x500")
            dlg.configure(bg="#ecf0f1")
            dlg.transient(self)

            text_widget = tk.Text(dlg, wrap="word", bg="white", padx=10, pady=10)
            text_widget.pack(fill="both", expand=True, padx=10, pady=10)

            name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or t("common.not_applicable")
            lines = [
                f"{t('student_wellbeing.referral')} {t('common.id')}: {r['id']}",
                f"{t('tutorial.student')}: {name} ({t('common.id')}: {r['student_id']})",
                f"{t('common.type')}: {r.get('referral_type', '')}",
                f"{t('common.category')}: {r.get('concern_category', '')}",
                f"{t('student_wellbeing.risk_level')}: {r.get('risk_level', '')}",
                f"{t('common.status')}: {r.get('status', '')}",
                f"{t('student_wellbeing.service_referred_to')}: {r.get('service_referred_to', '') or ''}",
                f"{t('student_wellbeing.external_agency')}: {r.get('external_agency', '') or ''}",
                f"{t('student_wellbeing.consent')}: {t('common.yes') if r.get('consent_obtained') else t('common.no')}",
                f"{t('student_wellbeing.appointment')}: {r.get('appointment_date', '') or ''}",
                f"{t('student_wellbeing.outcome')}: {r.get('outcome', '') or ''}",
                f"{t('common.created_at')}: {r.get('created_at', '')}",
                f"{t('common.updated_at')}: {r.get('updated_at', '') or ''}",
                "",
                f"{t('student_wellbeing.concern_details')}:",
                r.get("concern_details", ""),
            ]
            text_widget.insert("1.0", "\n".join(lines))
            text_widget.configure(state="disabled")
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _update_referral(self):
        rid = self._selected_referral_id()
        if not rid:
            return
        try:
            r = self._svc.get_referral(int(rid))
            if not r:
                messagebox.showwarning(t("common.warning"), t("common.no_data"))
                return
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"{t('student_wellbeing.update_referral')} #{rid}")
        dlg.geometry("450x450")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key, widget_type, opts, default in [
            (t("common.type") + ":", "referral_type", "combo", {"values": self.REFERRAL_TYPES}, r.get("referral_type", "")),
            (t("common.category") + ":", "concern_category", "combo", {"values": self.CONCERN_CATEGORIES[1:]}, r.get("concern_category", "")),
            (t("student_wellbeing.risk_level") + ":", "risk_level", "combo", {"values": self.RISK_LEVELS[1:]}, r.get("risk_level", "")),
            (t("common.status") + ":", "status", "combo", {"values": self.REFERRAL_STATUSES[1:]}, r.get("status", "")),
            (t("student_wellbeing.service_referred_to") + ":", "service_referred_to", "entry", {}, r.get("service_referred_to", "") or ""),
            (t("student_wellbeing.external_agency") + ":", "external_agency", "entry", {}, r.get("external_agency", "") or ""),
            (t("student_wellbeing.appointment_date") + ":", "appointment_date", "entry", {}, r.get("appointment_date", "") or ""),
        ]:
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=row, column=0, sticky="w", padx=10, pady=3)
            if widget_type == "entry":
                var = tk.StringVar(value=default)
                tk.Entry(dlg, textvariable=var, width=30).grid(row=row, column=1, padx=10, pady=3)
                fields[key] = var
            elif widget_type == "combo":
                var = tk.StringVar(value=default)
                ttk.Combobox(dlg, textvariable=var, values=opts["values"],
                              width=27, state="readonly").grid(row=row, column=1, padx=10, pady=3)
                fields[key] = var
            row += 1

        tk.Label(dlg, text=t("student_wellbeing.concern_details") + ":", bg="#ecf0f1").grid(row=row, column=0, sticky="nw", padx=10, pady=3)
        details_text = tk.Text(dlg, width=30, height=4)
        details_text.grid(row=row, column=1, padx=10, pady=3)
        details_text.insert("1.0", r.get("concern_details", ""))

        def save():
            try:
                kwargs = {}
                for k in ("referral_type", "concern_category", "risk_level",
                          "status", "service_referred_to", "external_agency",
                          "appointment_date"):
                    v = fields[k].get().strip()
                    if v:
                        kwargs[k] = v
                details = details_text.get("1.0", "end").strip()
                if details:
                    kwargs["concern_details"] = details
                if kwargs:
                    self._svc.update_referral(int(rid), **kwargs)
                    messagebox.showinfo(t("common.success"), t("common.updated_success"))
                    dlg.destroy()
                    self._load_referrals()
                else:
                    messagebox.showwarning(t("common.warning"), t("student_wellbeing.no_changes"))
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("common.save"), command=save).grid(row=row + 1, column=0, columnspan=2, pady=10)

    def _resolve_referral(self):
        rid = self._selected_referral_id()
        if not rid:
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"{t('student_wellbeing.resolve_referral')} #{rid}")
        dlg.geometry("400x200")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text=t("student_wellbeing.outcome") + ":", bg="#ecf0f1").pack(padx=10, pady=(10, 3), anchor="w")
        outcome_text = tk.Text(dlg, width=40, height=4)
        outcome_text.pack(padx=10, pady=3)

        def save():
            outcome = outcome_text.get("1.0", "end").strip()
            if not outcome:
                messagebox.showwarning(t("common.validation"), t("common.field_required"))
                return
            try:
                self._svc.resolve_referral(int(rid), outcome)
                messagebox.showinfo(t("common.success"), t("student_wellbeing.referral_resolved"))
                dlg.destroy()
                self._load_referrals()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("student_wellbeing.resolve"), command=save).pack(pady=10)

    def _delete_referral(self):
        rid = self._selected_referral_id()
        if not rid:
            return
        if not messagebox.askyesno(t("common.confirm"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_referral(int(rid))
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_referrals()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _show_high_risk(self):
        try:
            items = self._svc.get_high_risk_students()
            dlg = tk.Toplevel(self)
            dlg.title(t("student_wellbeing.high_risk_students"))
            dlg.geometry("600x400")
            dlg.configure(bg="#ecf0f1")
            dlg.transient(self)

            cols = ("id", "student", "category", "risk", "status", "created")
            tree = ttk.Treeview(dlg, columns=cols, show="headings", selectmode="browse")
            for c, h, w in [("id", t("common.id"), 40), ("student", t("tutorial.student"), 140),
                             ("category", t("common.category"), 110),
                             ("risk", t("student_wellbeing.risk"), 70),
                             ("status", t("common.status"), 90),
                             ("created", t("common.created_at"), 100)]:
                tree.heading(c, text=h)
                tree.column(c, width=w, anchor="center")
            tree.pack(fill="both", expand=True, padx=10, pady=10)

            for r in items:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
                tree.insert("", "end", values=(
                    r["id"], name or r["student_id"],
                    r.get("concern_category", ""), r.get("risk_level", ""),
                    r.get("status", ""), r.get("created_at", ""),
                ))
            if not items:
                tk.Label(dlg, text=t("student_wellbeing.no_high_risk"), bg="#ecf0f1",
                         font=("Helvetica", 12)).pack(pady=20)
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ================================================================
    # Tab 2: Wellbeing Logs
    # ================================================================

    def _build_logs_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("student_wellbeing.wellbeing_logs"))

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))

        tk.Label(filt, text=t("common.student_id") + ":", bg="#ecf0f1").pack(side="left", padx=(0, 3))
        self._log_student_var = tk.StringVar()
        tk.Entry(filt, textvariable=self._log_student_var, width=8).pack(side="left", padx=(0, 10))

        tk.Label(filt, text=t("student_wellbeing.follow_up") + ":", bg="#ecf0f1").pack(side="left", padx=(0, 3))
        self._log_followup_var = tk.StringVar()
        ttk.Combobox(filt, textvariable=self._log_followup_var,
                      values=self.FOLLOW_UP_OPTIONS, width=8, state="readonly"
                      ).pack(side="left", padx=(0, 10))

        ttk.Button(filt, text=t("common.filter"), command=self._load_logs).pack(side="left", padx=3)
        ttk.Button(filt, text=t("common.clear"), command=self._clear_log_filters).pack(side="left", padx=3)

        # Treeview
        cols = ("id", "student_id", "date", "mood", "anxiety", "sleep", "follow_up")
        tree_frame = tk.Frame(tab, bg="#ecf0f1")
        tree_frame.pack(fill="both", expand=True)

        self._log_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", t("common.id"), 40), ("student_id", t("common.student_id"), 70),
                         ("date", t("common.date"), 90),
                         ("mood", t("student_wellbeing.mood"), 50),
                         ("anxiety", t("student_wellbeing.anxiety"), 60),
                         ("sleep", t("student_wellbeing.sleep"), 70),
                         ("follow_up", t("student_wellbeing.follow_up"), 70)]:
            self._log_tree.heading(c, text=h)
            self._log_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._log_tree.yview)
        self._log_tree.configure(yscrollcommand=vsb.set)
        self._log_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Buttons
        btn = tk.Frame(tab, bg="#ecf0f1")
        btn.pack(fill="x", pady=(5, 0))
        ttk.Button(btn, text=t("common.new"), command=self._new_log).pack(side="left", padx=3)
        ttk.Button(btn, text=t("common.view"), command=self._view_log).pack(side="left", padx=3)
        ttk.Button(btn, text=t("common.update"), command=self._update_log).pack(side="left", padx=3)
        ttk.Button(btn, text=t("common.delete"), command=self._delete_log).pack(side="left", padx=3)
        ttk.Button(btn, text="Export CSV", command=self._export_logs_csv).pack(side="left", padx=3)

    def _clear_log_filters(self):
        self._log_student_var.set("")
        self._log_followup_var.set("")
        self._load_logs()

    def _load_logs(self):
        self._log_tree.delete(*self._log_tree.get_children())
        try:
            sid_str = self._log_student_var.get().strip()
            sid = int(sid_str) if sid_str else None
            fu_str = self._log_followup_var.get()
            fu = None
            if fu_str == "Yes":
                fu = 1
            elif fu_str == "No":
                fu = 0
            items = self._svc.list_logs(student_id=sid, follow_up_needed=fu)
            for log_item in items:
                self._log_tree.insert("", "end", values=(
                    log_item["id"], log_item["student_id"], log_item.get("log_date", ""),
                    log_item.get("mood_rating", "") or "", log_item.get("anxiety_level", "") or "",
                    log_item.get("sleep_quality", "") or "",
                    t("common.yes") if log_item.get("follow_up_needed") else t("common.no"),
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _selected_log_id(self):
        sel = self._log_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"))
            return None
        return self._log_tree.item(sel[0], "values")[0]

    def _new_log(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("student_wellbeing.new_log"))
        dlg.geometry("400x400")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key, widget_type, opts in [
            (t("common.student_id") + "*:", "student_id", "entry", {}),
            (t("student_wellbeing.log_date") + ":", "log_date", "entry", {}),
            (t("student_wellbeing.mood_rating") + ":", "mood_rating", "entry", {}),
            (t("student_wellbeing.anxiety_level") + ":", "anxiety_level", "entry", {}),
            (t("student_wellbeing.sleep_quality") + ":", "sleep_quality", "combo", {"values": self.SLEEP_QUALITIES[1:]}),
            (t("student_wellbeing.follow_up_needed") + ":", "follow_up_needed", "check", {}),
        ]:
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=row, column=0, sticky="w", padx=10, pady=3)
            if widget_type == "entry":
                var = tk.StringVar()
                tk.Entry(dlg, textvariable=var, width=25).grid(row=row, column=1, padx=10, pady=3)
                fields[key] = var
            elif widget_type == "combo":
                var = tk.StringVar()
                ttk.Combobox(dlg, textvariable=var, values=opts["values"],
                              width=22, state="readonly").grid(row=row, column=1, padx=10, pady=3)
                fields[key] = var
            elif widget_type == "check":
                var = tk.IntVar()
                tk.Checkbutton(dlg, variable=var, bg="#ecf0f1").grid(row=row, column=1, sticky="w", padx=10, pady=3)
                fields[key] = var
            row += 1

        tk.Label(dlg, text=t("common.notes") + ":", bg="#ecf0f1").grid(row=row, column=0, sticky="nw", padx=10, pady=3)
        notes_text = tk.Text(dlg, width=25, height=4)
        notes_text.grid(row=row, column=1, padx=10, pady=3)

        def save():
            sid = fields["student_id"].get().strip()
            if not sid:
                messagebox.showwarning(t("common.validation"), t("common.field_required"))
                return
            try:
                kwargs = {}
                log_date = fields["log_date"].get().strip()
                if log_date:
                    kwargs["log_date"] = log_date
                mood = fields["mood_rating"].get().strip()
                if mood:
                    kwargs["mood_rating"] = int(mood)
                anxiety = fields["anxiety_level"].get().strip()
                if anxiety:
                    kwargs["anxiety_level"] = int(anxiety)
                sleep = fields["sleep_quality"].get().strip()
                if sleep:
                    kwargs["sleep_quality"] = sleep
                fu = fields["follow_up_needed"].get()
                kwargs["follow_up_needed"] = fu
                notes = notes_text.get("1.0", "end").strip()
                if notes:
                    kwargs["notes"] = notes
                if self._auth and hasattr(self._auth, "current_user"):
                    kwargs["logged_by"] = self._auth.current_user.get("user_id")
                self._svc.create_log(int(sid), **kwargs)
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                dlg.destroy()
                self._load_logs()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("common.save"), command=save).grid(row=row + 1, column=0, columnspan=2, pady=10)

    def _view_log(self):
        lid = self._selected_log_id()
        if not lid:
            return
        try:
            log_item = self._svc.get_log(int(lid))
            if not log_item:
                messagebox.showwarning(t("common.warning"), t("common.no_data"))
                return
            dlg = tk.Toplevel(self)
            dlg.title(f"{t('student_wellbeing.wellbeing_log')} #{log_item['id']}")
            dlg.geometry("420x380")
            dlg.configure(bg="#ecf0f1")
            dlg.transient(self)

            text_widget = tk.Text(dlg, wrap="word", bg="white", padx=10, pady=10)
            text_widget.pack(fill="both", expand=True, padx=10, pady=10)

            name = f"{log_item.get('first_name', '')} {log_item.get('last_name', '')}".strip() or t("common.not_applicable")
            lines = [
                f"{t('student_wellbeing.log')} {t('common.id')}: {log_item['id']}",
                f"{t('tutorial.student')}: {name} ({t('common.id')}: {log_item['student_id']})",
                f"{t('common.date')}: {log_item.get('log_date', '')}",
                f"{t('student_wellbeing.mood_rating')}: {log_item.get('mood_rating', '') or t('common.not_applicable')}",
                f"{t('student_wellbeing.anxiety_level')}: {log_item.get('anxiety_level', '') or t('common.not_applicable')}",
                f"{t('student_wellbeing.sleep_quality')}: {log_item.get('sleep_quality', '') or t('common.not_applicable')}",
                f"{t('student_wellbeing.follow_up_needed')}: {t('common.yes') if log_item.get('follow_up_needed') else t('common.no')}",
                f"{t('common.created_at')}: {log_item.get('created_at', '')}",
                "",
                f"{t('common.notes')}:",
                log_item.get("notes", "") or "",
            ]
            text_widget.insert("1.0", "\n".join(lines))
            text_widget.configure(state="disabled")
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _update_log(self):
        lid = self._selected_log_id()
        if not lid:
            return
        try:
            log_item = self._svc.get_log(int(lid))
            if not log_item:
                messagebox.showwarning(t("common.warning"), t("common.no_data"))
                return
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"{t('student_wellbeing.update_log')} #{lid}")
        dlg.geometry("400x380")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key, widget_type, opts, default in [
            (t("student_wellbeing.log_date") + ":", "log_date", "entry", {}, log_item.get("log_date", "") or ""),
            (t("student_wellbeing.mood") + " (1-10):", "mood_rating", "entry", {}, str(log_item.get("mood_rating", "") or "")),
            (t("student_wellbeing.anxiety") + " (1-10):", "anxiety_level", "entry", {}, str(log_item.get("anxiety_level", "") or "")),
            (t("student_wellbeing.sleep_quality") + ":", "sleep_quality", "combo", {"values": self.SLEEP_QUALITIES[1:]}, log_item.get("sleep_quality", "") or ""),
            (t("student_wellbeing.follow_up") + ":", "follow_up_needed", "check", {}, log_item.get("follow_up_needed", 0)),
        ]:
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=row, column=0, sticky="w", padx=10, pady=3)
            if widget_type == "entry":
                var = tk.StringVar(value=default)
                tk.Entry(dlg, textvariable=var, width=25).grid(row=row, column=1, padx=10, pady=3)
                fields[key] = var
            elif widget_type == "combo":
                var = tk.StringVar(value=default)
                ttk.Combobox(dlg, textvariable=var, values=opts["values"],
                              width=22, state="readonly").grid(row=row, column=1, padx=10, pady=3)
                fields[key] = var
            elif widget_type == "check":
                var = tk.IntVar(value=default)
                tk.Checkbutton(dlg, variable=var, bg="#ecf0f1").grid(row=row, column=1, sticky="w", padx=10, pady=3)
                fields[key] = var
            row += 1

        tk.Label(dlg, text=t("common.notes") + ":", bg="#ecf0f1").grid(row=row, column=0, sticky="nw", padx=10, pady=3)
        notes_text = tk.Text(dlg, width=25, height=4)
        notes_text.grid(row=row, column=1, padx=10, pady=3)
        notes_text.insert("1.0", log_item.get("notes", "") or "")

        def save():
            try:
                kwargs = {}
                log_date = fields["log_date"].get().strip()
                if log_date:
                    kwargs["log_date"] = log_date
                mood = fields["mood_rating"].get().strip()
                if mood:
                    kwargs["mood_rating"] = int(mood)
                anxiety = fields["anxiety_level"].get().strip()
                if anxiety:
                    kwargs["anxiety_level"] = int(anxiety)
                sleep = fields["sleep_quality"].get().strip()
                if sleep:
                    kwargs["sleep_quality"] = sleep
                kwargs["follow_up_needed"] = fields["follow_up_needed"].get()
                notes = notes_text.get("1.0", "end").strip()
                if notes:
                    kwargs["notes"] = notes
                if kwargs:
                    self._svc.update_log(int(lid), **kwargs)
                    messagebox.showinfo(t("common.success"), t("common.updated_success"))
                    dlg.destroy()
                    self._load_logs()
                else:
                    messagebox.showwarning(t("common.warning"), t("student_wellbeing.no_changes"))
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("common.save"), command=save).grid(row=row + 1, column=0, columnspan=2, pady=10)

    def _delete_log(self):
        lid = self._selected_log_id()
        if not lid:
            return
        if not messagebox.askyesno(t("common.confirm"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_log(int(lid))
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_logs()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ================================================================
    # Tab 3: Counselling Sessions
    # ================================================================

    def _build_sessions_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("student_wellbeing.counselling_sessions"))

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 5))

        tk.Label(filt, text=t("common.status") + ":", bg="#ecf0f1").pack(side="left", padx=(0, 3))
        self._sess_status_var = tk.StringVar()
        ttk.Combobox(filt, textvariable=self._sess_status_var,
                      values=self.SESSION_STATUSES, width=12, state="readonly"
                      ).pack(side="left", padx=(0, 10))

        tk.Label(filt, text=t("common.type") + ":", bg="#ecf0f1").pack(side="left", padx=(0, 3))
        self._sess_type_var = tk.StringVar()
        ttk.Combobox(filt, textvariable=self._sess_type_var,
                      values=self.SESSION_TYPES, width=12, state="readonly"
                      ).pack(side="left", padx=(0, 10))

        ttk.Button(filt, text=t("common.filter"), command=self._load_sessions).pack(side="left", padx=3)
        ttk.Button(filt, text=t("common.clear"), command=self._clear_sess_filters).pack(side="left", padx=3)

        # Treeview
        cols = ("id", "student_id", "counsellor", "date", "session_num", "type", "status")
        tree_frame = tk.Frame(tab, bg="#ecf0f1")
        tree_frame.pack(fill="both", expand=True)

        self._sess_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", t("common.id"), 40), ("student_id", t("common.student_id"), 70),
                         ("counsellor", t("student_wellbeing.counsellor"), 80),
                         ("date", t("common.date"), 90),
                         ("session_num", t("student_wellbeing.session_num"), 65),
                         ("type", t("common.type"), 80),
                         ("status", t("common.status"), 80)]:
            self._sess_tree.heading(c, text=h)
            self._sess_tree.column(c, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._sess_tree.yview)
        self._sess_tree.configure(yscrollcommand=vsb.set)
        self._sess_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Buttons
        btn = tk.Frame(tab, bg="#ecf0f1")
        btn.pack(fill="x", pady=(5, 0))
        ttk.Button(btn, text=t("common.new"), command=self._new_session).pack(side="left", padx=3)
        ttk.Button(btn, text=t("common.view"), command=self._view_session).pack(side="left", padx=3)
        ttk.Button(btn, text=t("common.update"), command=self._update_session).pack(side="left", padx=3)
        ttk.Button(btn, text=t("common.delete"), command=self._delete_session).pack(side="left", padx=3)
        ttk.Button(btn, text="Export CSV", command=self._export_sessions_csv).pack(side="left", padx=3)

    def _clear_sess_filters(self):
        self._sess_status_var.set("")
        self._sess_type_var.set("")
        self._load_sessions()

    def _load_sessions(self):
        self._sess_tree.delete(*self._sess_tree.get_children())
        try:
            status = self._sess_status_var.get() or None
            stype = self._sess_type_var.get() or None
            items = self._svc.list_sessions(status=status, session_type=stype)
            for s in items:
                self._sess_tree.insert("", "end", values=(
                    s["id"], s["student_id"], s.get("counsellor_id", "") or "",
                    s.get("session_date", ""), s.get("session_number", 1),
                    s.get("session_type", ""), s.get("status", ""),
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _selected_session_id(self):
        sel = self._sess_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"))
            return None
        return self._sess_tree.item(sel[0], "values")[0]

    def _new_session(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("student_wellbeing.new_session"))
        dlg.geometry("450x520")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key, widget_type, opts in [
            (t("common.student_id") + "*:", "student_id", "entry", {}),
            (t("student_wellbeing.session_date") + "*:", "session_date", "entry", {}),
            (t("student_wellbeing.counsellor_id") + ":", "counsellor_id", "entry", {}),
            (t("student_wellbeing.session_number") + ":", "session_number", "entry", {}),
            (t("student_wellbeing.session_type") + ":", "session_type", "combo", {"values": self.SESSION_TYPES[1:]}),
            (t("common.status") + ":", "status", "combo", {"values": self.SESSION_STATUSES[1:]}),
            (t("student_wellbeing.next_appointment") + ":", "next_appointment", "entry", {}),
        ]:
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=row, column=0, sticky="w", padx=10, pady=3)
            if widget_type == "entry":
                var = tk.StringVar()
                tk.Entry(dlg, textvariable=var, width=28).grid(row=row, column=1, padx=10, pady=3)
                fields[key] = var
            elif widget_type == "combo":
                var = tk.StringVar()
                ttk.Combobox(dlg, textvariable=var, values=opts["values"],
                              width=25, state="readonly").grid(row=row, column=1, padx=10, pady=3)
                fields[key] = var
            row += 1

        tk.Label(dlg, text=t("student_wellbeing.presenting_issues") + ":", bg="#ecf0f1").grid(row=row, column=0, sticky="nw", padx=10, pady=3)
        issues_text = tk.Text(dlg, width=28, height=3)
        issues_text.grid(row=row, column=1, padx=10, pady=3)
        row += 1

        tk.Label(dlg, text=t("student_wellbeing.session_notes") + ":", bg="#ecf0f1").grid(row=row, column=0, sticky="nw", padx=10, pady=3)
        notes_text = tk.Text(dlg, width=28, height=3)
        notes_text.grid(row=row, column=1, padx=10, pady=3)
        row += 1

        tk.Label(dlg, text=t("student_wellbeing.risk_assessment") + ":", bg="#ecf0f1").grid(row=row, column=0, sticky="nw", padx=10, pady=3)
        risk_text = tk.Text(dlg, width=28, height=2)
        risk_text.grid(row=row, column=1, padx=10, pady=3)

        def save():
            sid = fields["student_id"].get().strip()
            sdate = fields["session_date"].get().strip()
            if not sid or not sdate:
                messagebox.showwarning(t("common.validation"), t("common.both_required"))
                return
            try:
                kwargs = {}
                cid = fields["counsellor_id"].get().strip()
                if cid:
                    kwargs["counsellor_id"] = int(cid)
                snum = fields["session_number"].get().strip()
                if snum:
                    kwargs["session_number"] = int(snum)
                st = fields["session_type"].get().strip()
                if st:
                    kwargs["session_type"] = st
                status = fields["status"].get().strip()
                if status:
                    kwargs["status"] = status
                nxt = fields["next_appointment"].get().strip()
                if nxt:
                    kwargs["next_appointment"] = nxt
                issues = issues_text.get("1.0", "end").strip()
                if issues:
                    kwargs["presenting_issues"] = issues
                notes = notes_text.get("1.0", "end").strip()
                if notes:
                    kwargs["session_notes"] = notes
                risk = risk_text.get("1.0", "end").strip()
                if risk:
                    kwargs["risk_assessment"] = risk
                self._svc.create_session(int(sid), sdate, **kwargs)
                messagebox.showinfo(t("common.success"), t("common.created_success"))
                dlg.destroy()
                self._load_sessions()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("common.save"), command=save).grid(row=row + 1, column=0, columnspan=2, pady=10)

    def _view_session(self):
        sid = self._selected_session_id()
        if not sid:
            return
        try:
            s = self._svc.get_session(int(sid))
            if not s:
                messagebox.showwarning(t("common.warning"), t("common.no_data"))
                return
            dlg = tk.Toplevel(self)
            dlg.title(f"{t('student_wellbeing.session')} #{s['id']}")
            dlg.geometry("480x450")
            dlg.configure(bg="#ecf0f1")
            dlg.transient(self)

            text_widget = tk.Text(dlg, wrap="word", bg="white", padx=10, pady=10)
            text_widget.pack(fill="both", expand=True, padx=10, pady=10)

            name = f"{s.get('first_name', '')} {s.get('last_name', '')}".strip() or t("common.not_applicable")
            lines = [
                f"{t('student_wellbeing.session')} {t('common.id')}: {s['id']}",
                f"{t('tutorial.student')}: {name} ({t('common.id')}: {s['student_id']})",
                f"{t('student_wellbeing.counsellor_id')}: {s.get('counsellor_id', '') or t('common.not_applicable')}",
                f"{t('common.date')}: {s.get('session_date', '')}",
                f"{t('student_wellbeing.session_num')}: {s.get('session_number', 1)}",
                f"{t('common.type')}: {s.get('session_type', '')}",
                f"{t('common.status')}: {s.get('status', '')}",
                f"{t('student_wellbeing.next_appointment')}: {s.get('next_appointment', '') or t('common.not_applicable')}",
                f"{t('common.created_at')}: {s.get('created_at', '')}",
                "",
                f"{t('student_wellbeing.presenting_issues')}:",
                s.get("presenting_issues", "") or "",
                "",
                f"{t('student_wellbeing.session_notes')}:",
                s.get("session_notes", "") or "",
                "",
                f"{t('student_wellbeing.risk_assessment')}:",
                s.get("risk_assessment", "") or "",
            ]
            text_widget.insert("1.0", "\n".join(lines))
            text_widget.configure(state="disabled")
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _update_session(self):
        sid = self._selected_session_id()
        if not sid:
            return
        try:
            s = self._svc.get_session(int(sid))
            if not s:
                messagebox.showwarning(t("common.warning"), t("common.no_data"))
                return
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"{t('student_wellbeing.update_session')} #{sid}")
        dlg.geometry("450x520")
        dlg.configure(bg="#ecf0f1")
        dlg.transient(self)
        dlg.grab_set()

        fields = {}
        row = 0
        for label, key, widget_type, opts, default in [
            (t("student_wellbeing.session_date") + ":", "session_date", "entry", {}, s.get("session_date", "")),
            (t("student_wellbeing.counsellor_id") + ":", "counsellor_id", "entry", {}, str(s.get("counsellor_id", "") or "")),
            (t("student_wellbeing.session_number") + ":", "session_number", "entry", {}, str(s.get("session_number", 1))),
            (t("common.type") + ":", "session_type", "combo", {"values": self.SESSION_TYPES[1:]}, s.get("session_type", "")),
            (t("common.status") + ":", "status", "combo", {"values": self.SESSION_STATUSES[1:]}, s.get("status", "")),
            (t("student_wellbeing.next_appointment") + ":", "next_appointment", "entry", {}, s.get("next_appointment", "") or ""),
        ]:
            tk.Label(dlg, text=label, bg="#ecf0f1").grid(row=row, column=0, sticky="w", padx=10, pady=3)
            if widget_type == "entry":
                var = tk.StringVar(value=default)
                tk.Entry(dlg, textvariable=var, width=28).grid(row=row, column=1, padx=10, pady=3)
                fields[key] = var
            elif widget_type == "combo":
                var = tk.StringVar(value=default)
                ttk.Combobox(dlg, textvariable=var, values=opts["values"],
                              width=25, state="readonly").grid(row=row, column=1, padx=10, pady=3)
                fields[key] = var
            row += 1

        tk.Label(dlg, text=t("student_wellbeing.presenting_issues") + ":", bg="#ecf0f1").grid(row=row, column=0, sticky="nw", padx=10, pady=3)
        issues_text = tk.Text(dlg, width=28, height=3)
        issues_text.grid(row=row, column=1, padx=10, pady=3)
        issues_text.insert("1.0", s.get("presenting_issues", "") or "")
        row += 1

        tk.Label(dlg, text=t("student_wellbeing.session_notes") + ":", bg="#ecf0f1").grid(row=row, column=0, sticky="nw", padx=10, pady=3)
        notes_text = tk.Text(dlg, width=28, height=3)
        notes_text.grid(row=row, column=1, padx=10, pady=3)
        notes_text.insert("1.0", s.get("session_notes", "") or "")
        row += 1

        tk.Label(dlg, text=t("student_wellbeing.risk_assessment") + ":", bg="#ecf0f1").grid(row=row, column=0, sticky="nw", padx=10, pady=3)
        risk_text = tk.Text(dlg, width=28, height=2)
        risk_text.grid(row=row, column=1, padx=10, pady=3)
        risk_text.insert("1.0", s.get("risk_assessment", "") or "")

        def save():
            try:
                kwargs = {}
                sdate = fields["session_date"].get().strip()
                if sdate:
                    kwargs["session_date"] = sdate
                cid = fields["counsellor_id"].get().strip()
                if cid:
                    kwargs["counsellor_id"] = int(cid)
                snum = fields["session_number"].get().strip()
                if snum:
                    kwargs["session_number"] = int(snum)
                st = fields["session_type"].get().strip()
                if st:
                    kwargs["session_type"] = st
                status = fields["status"].get().strip()
                if status:
                    kwargs["status"] = status
                nxt = fields["next_appointment"].get().strip()
                if nxt:
                    kwargs["next_appointment"] = nxt
                issues = issues_text.get("1.0", "end").strip()
                if issues:
                    kwargs["presenting_issues"] = issues
                notes = notes_text.get("1.0", "end").strip()
                if notes:
                    kwargs["session_notes"] = notes
                risk = risk_text.get("1.0", "end").strip()
                if risk:
                    kwargs["risk_assessment"] = risk
                if kwargs:
                    self._svc.update_session(int(sid), **kwargs)
                    messagebox.showinfo(t("common.success"), t("common.updated_success"))
                    dlg.destroy()
                    self._load_sessions()
                else:
                    messagebox.showwarning(t("common.warning"), t("student_wellbeing.no_changes"))
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("common.save"), command=save).grid(row=row + 1, column=0, columnspan=2, pady=10)

    def _delete_session(self):
        sid = self._selected_session_id()
        if not sid:
            return
        if not messagebox.askyesno(t("common.confirm"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_session(int(sid))
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_sessions()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ================================================================
    # Tab 4: Statistics
    # ================================================================

    def _build_stats_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("common.summary"))
        self._stats_tab = tab

        # Will be populated on refresh
        self._stats_frame = tk.Frame(tab, bg="#ecf0f1")
        self._stats_frame.pack(fill="both", expand=True)

    def _load_stats(self):
        for w in self._stats_frame.winfo_children():
            w.destroy()
        try:
            stats = self._svc.get_stats()

            # Referrals section
            ref_lf = tk.LabelFrame(self._stats_frame, text=t("student_wellbeing.referrals"), bg="#ecf0f1",
                                    font=("Helvetica", 11, "bold"), padx=10, pady=5)
            ref_lf.pack(fill="x", pady=(0, 8))

            row_frame = tk.Frame(ref_lf, bg="#ecf0f1")
            row_frame.pack(fill="x")
            tk.Label(row_frame, text=f"{t('common.total')}: {stats['total_referrals']}", bg="#ecf0f1",
                     font=("Helvetica", 10)).pack(side="left", padx=10)
            tk.Label(row_frame, text=f"{t('student_wellbeing.open')}: {stats['open_referrals']}", bg="#ecf0f1",
                     font=("Helvetica", 10)).pack(side="left", padx=10)
            tk.Label(row_frame, text=f"{t('student_wellbeing.high_risk')}: {stats['high_risk_count']}", bg="#ecf0f1",
                     font=("Helvetica", 10), fg="red").pack(side="left", padx=10)

            if stats["by_status"]:
                status_str = ", ".join(f"{k}: {v}" for k, v in stats["by_status"].items())
                tk.Label(ref_lf, text=f"{t('student_wellbeing.by_status')}: {status_str}", bg="#ecf0f1",
                         font=("Helvetica", 9)).pack(anchor="w", padx=10)
            if stats["by_risk_level"]:
                risk_str = ", ".join(f"{k}: {v}" for k, v in stats["by_risk_level"].items())
                tk.Label(ref_lf, text=f"{t('student_wellbeing.by_risk_level')}: {risk_str}", bg="#ecf0f1",
                         font=("Helvetica", 9)).pack(anchor="w", padx=10)
            if stats["by_category"]:
                cat_str = ", ".join(f"{k}: {v}" for k, v in stats["by_category"].items())
                tk.Label(ref_lf, text=f"{t('student_wellbeing.by_category')}: {cat_str}", bg="#ecf0f1",
                         font=("Helvetica", 9), wraplength=500, justify="left").pack(anchor="w", padx=10)

            # Logs section
            log_lf = tk.LabelFrame(self._stats_frame, text=t("student_wellbeing.wellbeing_logs"), bg="#ecf0f1",
                                    font=("Helvetica", 11, "bold"), padx=10, pady=5)
            log_lf.pack(fill="x", pady=(0, 8))

            log_row = tk.Frame(log_lf, bg="#ecf0f1")
            log_row.pack(fill="x")
            tk.Label(log_row, text=f"{t('student_wellbeing.total_logs')}: {stats['total_logs']}", bg="#ecf0f1",
                     font=("Helvetica", 10)).pack(side="left", padx=10)
            tk.Label(log_row, text=f"{t('student_wellbeing.follow_ups_needed')}: {stats['follow_ups_needed']}", bg="#ecf0f1",
                     font=("Helvetica", 10)).pack(side="left", padx=10)
            tk.Label(log_row, text=f"{t('student_wellbeing.avg_mood')}: {stats['avg_mood']}", bg="#ecf0f1",
                     font=("Helvetica", 10)).pack(side="left", padx=10)

            # Sessions section
            sess_lf = tk.LabelFrame(self._stats_frame, text=t("student_wellbeing.counselling_sessions"), bg="#ecf0f1",
                                     font=("Helvetica", 11, "bold"), padx=10, pady=5)
            sess_lf.pack(fill="x", pady=(0, 8))

            sess_row = tk.Frame(sess_lf, bg="#ecf0f1")
            sess_row.pack(fill="x")
            tk.Label(sess_row, text=f"{t('student_wellbeing.total_sessions')}: {stats['total_sessions']}", bg="#ecf0f1",
                     font=("Helvetica", 10)).pack(side="left", padx=10)
            if stats["by_session_type"]:
                type_str = ", ".join(f"{k}: {v}" for k, v in stats["by_session_type"].items())
                tk.Label(sess_lf, text=f"{t('student_wellbeing.by_type')}: {type_str}", bg="#ecf0f1",
                         font=("Helvetica", 9)).pack(anchor="w", padx=10)

            ttk.Button(self._stats_frame, text=t("common.refresh"),
                       command=self._load_stats).pack(pady=10)

        except Exception as e:
            tk.Label(self._stats_frame, text=f"{t('common.error')}: {e}",
                     bg="#ecf0f1", fg="red").pack(pady=20)

    def _export_referrals_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._ref_tree, "student_wellbeing.csv")

    def _export_logs_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._log_tree, "student_wellbeing_logs_export.csv")

    def _export_sessions_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._sess_tree, "student_wellbeing_sessions_export.csv")

    # ================================================================
    # Main refresh
    # ================================================================

    def refresh(self):
        self._load_referrals()
        self._load_logs()
        self._load_sessions()
        self._load_stats()
