"""Prevent Duty GUI frame with referrals, training and statistics tabs."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.core.i18n import t
from education_system.college_system.modules.domain.prevent_duty.services.prevent_duty_service import PreventDutyService


# ── Dialogs ────────────────────────────────────────────────────────


class _ReferralDialog(tk.Toplevel):
    """Modal dialog for creating / editing a referral."""

    def __init__(self, parent, title="Referral", item=None):
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
        pw = parent.winfo_rootx() + parent.winfo_width() // 2
        ph = parent.winfo_rooty() + parent.winfo_height() // 2
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{pw - w // 2}+{ph - h // 2}")

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(self, padx=20, pady=15)
        c.pack(fill="both", expand=True)
        self._vars: dict[str, tk.StringVar] = {}

        fields = [
            ("subject_name", t("common.name")),
            ("subject_type", t("common.type")),
            ("subject_id", t("common.id")),
            ("concern_type", t("common.type")),
            ("risk_level", t("common.priority")),
            ("actions_taken", t("common.actions")),
            ("outcome", t("common.status")),
            ("status", t("common.status")),
        ]
        for row_idx, (key, label) in enumerate(fields):
            tk.Label(c, text=label, anchor="w",
                     font=("Helvetica", 9, "bold")).grid(row=row_idx, column=0, sticky="w", **pad)
            if key == "risk_level":
                var = tk.StringVar(value=self._item.get(key, "low"))
                combo = ttk.Combobox(c, textvariable=var, width=34,
                                     values=["low", "medium", "high", "critical"],
                                     state="readonly")
                combo.grid(row=row_idx, column=1, sticky="ew", **pad)
            elif key == "status":
                var = tk.StringVar(value=self._item.get(key, "open"))
                combo = ttk.Combobox(c, textvariable=var, width=34,
                                     values=["open", "under_review", "escalated", "closed"],
                                     state="readonly")
                combo.grid(row=row_idx, column=1, sticky="ew", **pad)
            elif key == "subject_type":
                var = tk.StringVar(value=self._item.get(key, "student"))
                combo = ttk.Combobox(c, textvariable=var, width=34,
                                     values=["student", "staff", "visitor", "other"],
                                     state="readonly")
                combo.grid(row=row_idx, column=1, sticky="ew", **pad)
            else:
                var = tk.StringVar(value=str(self._item.get(key, "") or ""))
                ttk.Entry(c, textvariable=var, width=36).grid(row=row_idx, column=1, sticky="ew", **pad)
            self._vars[key] = var

        # Concern details as Text widget
        row_idx = len(fields)
        tk.Label(c, text=t("common.details"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=row_idx, column=0, sticky="nw", **pad)
        self._details_text = tk.Text(c, width=36, height=5, wrap="word")
        self._details_text.grid(row=row_idx, column=1, sticky="ew", **pad)
        self._details_text.insert("1.0", str(self._item.get("concern_details", "") or ""))

        btn_frame = tk.Frame(c)
        btn_frame.grid(row=row_idx + 1, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn_frame, text=t("common.save"), command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=t("common.cancel"), command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        self.result["concern_details"] = self._details_text.get("1.0", "end-1c").strip()
        if not self.result.get("subject_name"):
            messagebox.showwarning(t("common.validation"), t("common.field_required"), parent=self)
            return
        if not self.result.get("concern_details"):
            messagebox.showwarning(t("common.validation"), t("common.field_required"), parent=self)
            return
        # Convert subject_id to int or None
        sid = self.result.get("subject_id", "")
        self.result["subject_id"] = int(sid) if sid else None
        self.destroy()


class _TrainingDialog(tk.Toplevel):
    """Modal dialog for creating / editing a training record."""

    def __init__(self, parent, title="Training Record", item=None):
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
        pw = parent.winfo_rootx() + parent.winfo_width() // 2
        ph = parent.winfo_rooty() + parent.winfo_height() // 2
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{pw - w // 2}+{ph - h // 2}")

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(self, padx=20, pady=15)
        c.pack(fill="both", expand=True)
        self._vars: dict[str, tk.StringVar] = {}

        fields = [
            ("staff_id", t("common.id")),
            ("training_type", t("common.type")),
            ("completed_date", t("common.date")),
            ("expiry_date", t("common.end_date")),
            ("certificate_ref", t("common.details")),
            ("status", t("common.status")),
        ]
        for row_idx, (key, label) in enumerate(fields):
            tk.Label(c, text=label, anchor="w",
                     font=("Helvetica", 9, "bold")).grid(row=row_idx, column=0, sticky="w", **pad)
            if key == "training_type":
                var = tk.StringVar(value=self._item.get(key, "basic"))
                combo = ttk.Combobox(c, textvariable=var, width=34,
                                     values=["basic", "advanced", "refresher", "wrap"],
                                     state="readonly")
                combo.grid(row=row_idx, column=1, sticky="ew", **pad)
            elif key == "status":
                var = tk.StringVar(value=self._item.get(key, "completed"))
                combo = ttk.Combobox(c, textvariable=var, width=34,
                                     values=["completed", "pending", "expired"],
                                     state="readonly")
                combo.grid(row=row_idx, column=1, sticky="ew", **pad)
            else:
                var = tk.StringVar(value=str(self._item.get(key, "") or ""))
                ttk.Entry(c, textvariable=var, width=36).grid(row=row_idx, column=1, sticky="ew", **pad)
            self._vars[key] = var

        btn_frame = tk.Frame(c)
        btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn_frame, text=t("common.save"), command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=t("common.cancel"), command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        sid = self.result.get("staff_id", "")
        if not sid:
            messagebox.showwarning(t("common.validation"), t("common.field_required"), parent=self)
            return
        try:
            self.result["staff_id"] = int(sid)
        except ValueError:
            messagebox.showwarning(t("common.validation"), t("common.invalid_input"), parent=self)
            return
        self.destroy()


class _ViewReferralDialog(tk.Toplevel):
    """Read-only dialog to view referral details."""

    def __init__(self, parent, item: dict):
        super().__init__(parent)
        self.title(f"{t('prevent_duty.referral')} #{item.get('id', '')}")
        self.resizable(False, False)
        self.grab_set()
        c = tk.Frame(self, padx=20, pady=15)
        c.pack(fill="both", expand=True)
        for row_idx, (k, v) in enumerate(item.items()):
            tk.Label(c, text=k.replace("_", " ").title(), anchor="w",
                     font=("Helvetica", 9, "bold")).grid(row=row_idx, column=0, sticky="nw", padx=5, pady=2)
            tk.Label(c, text=str(v) if v is not None else "", anchor="w",
                     font=("Helvetica", 9), wraplength=350, justify="left"
                     ).grid(row=row_idx, column=1, sticky="w", padx=5, pady=2)
        ttk.Button(c, text=t("common.close"), command=self.destroy).grid(
            row=row_idx + 1, column=0, columnspan=2, pady=(15, 0))
        self.update_idletasks()
        pw = parent.winfo_rootx() + parent.winfo_width() // 2
        ph = parent.winfo_rooty() + parent.winfo_height() // 2
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{pw - w // 2}+{ph - h // 2}")


# ── Main Frame ─────────────────────────────────────────────────────


class PreventDutyFrame(tk.Frame):
    """Prevent Duty management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = PreventDutyService(db_path)
        self._build_ui()

    # ── UI Construction ────────────────────────────────────────────

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("prevent_duty.management"),
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_referrals_tab()
        self._build_training_tab()
        self._build_stats_tab()

    # ── Referrals Tab ──────────────────────────────────────────────

    def _build_referrals_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("prevent_duty.referral"))

        # Filters bar
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 8))

        tk.Label(filt, text=t("common.search") + ":", bg="#ecf0f1").pack(side="left", padx=(0, 4))
        self._ref_search_var = tk.StringVar()
        ttk.Entry(filt, textvariable=self._ref_search_var, width=18).pack(side="left", padx=2)

        tk.Label(filt, text=t("common.status") + ":", bg="#ecf0f1").pack(side="left", padx=(10, 4))
        self._ref_status_var = tk.StringVar()
        ttk.Combobox(filt, textvariable=self._ref_status_var, width=12,
                      values=["", "open", "under_review", "escalated", "closed"],
                      state="readonly").pack(side="left", padx=2)

        tk.Label(filt, text=t("common.priority") + ":", bg="#ecf0f1").pack(side="left", padx=(10, 4))
        self._ref_risk_var = tk.StringVar()
        ttk.Combobox(filt, textvariable=self._ref_risk_var, width=10,
                      values=["", "low", "medium", "high", "critical"],
                      state="readonly").pack(side="left", padx=2)

        ttk.Button(filt, text=t("common.filter"), command=self._load_referrals).pack(side="left", padx=8)

        # Buttons bar
        btn_bar = tk.Frame(tab, bg="#ecf0f1")
        btn_bar.pack(fill="x", pady=(0, 5))
        ttk.Button(btn_bar, text=t("common.create"), command=self._on_new_referral).pack(side="left", padx=4)
        ttk.Button(btn_bar, text=t("common.view"), command=self._on_view_referral).pack(side="left", padx=4)
        ttk.Button(btn_bar, text=t("common.edit"), command=self._on_edit_referral).pack(side="left", padx=4)
        ttk.Button(btn_bar, text=t("common.submit"), command=self._on_escalate).pack(side="left", padx=4)
        ttk.Button(btn_bar, text=t("common.delete"), command=self._on_delete_referral).pack(side="left", padx=4)
        ttk.Button(btn_bar, text=t("common.refresh"), command=self._load_referrals).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="Export CSV", command=self._export_referrals_csv).pack(side="left", padx=4)

        # Treeview
        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill="both", expand=True)
        cols = ("id", "subject_name", "subject_type", "concern_type",
                "risk_level", "channel_referral", "status", "created_at")
        self._ref_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        headings = {
            "id": (t("common.id"), 40), "subject_name": (t("common.name"), 140),
            "subject_type": (t("common.type"), 70), "concern_type": (t("common.type"), 100),
            "risk_level": (t("common.priority"), 70), "channel_referral": (t("common.status"), 60),
            "status": (t("common.status"), 90), "created_at": (t("common.created_at"), 130),
        }
        for col, (text, width) in headings.items():
            self._ref_tree.heading(col, text=text)
            self._ref_tree.column(col, width=width, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._ref_tree.yview)
        self._ref_tree.configure(yscrollcommand=vsb.set)
        self._ref_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._ref_status = tk.StringVar(value=t("common.ready"))
        tk.Label(tab, textvariable=self._ref_status, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", pady=(4, 0))

    # ── Training Tab ───────────────────────────────────────────────

    def _build_training_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("prevent_duty.training_status"))

        # Filter
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 8))
        tk.Label(filt, text=t("common.status") + ":", bg="#ecf0f1").pack(side="left", padx=(0, 4))
        self._trn_status_var = tk.StringVar()
        ttk.Combobox(filt, textvariable=self._trn_status_var, width=12,
                      values=["", "completed", "pending", "expired"],
                      state="readonly").pack(side="left", padx=2)
        self._trn_expiring_var = tk.BooleanVar()
        ttk.Checkbutton(filt, text=t("common.overdue"), variable=self._trn_expiring_var
                         ).pack(side="left", padx=10)
        ttk.Button(filt, text=t("common.filter"), command=self._load_training).pack(side="left", padx=8)

        # Buttons
        btn_bar = tk.Frame(tab, bg="#ecf0f1")
        btn_bar.pack(fill="x", pady=(0, 5))
        ttk.Button(btn_bar, text=t("common.create"), command=self._on_new_training).pack(side="left", padx=4)
        ttk.Button(btn_bar, text=t("common.edit"), command=self._on_edit_training).pack(side="left", padx=4)
        ttk.Button(btn_bar, text=t("common.delete"), command=self._on_delete_training).pack(side="left", padx=4)
        ttk.Button(btn_bar, text=t("common.refresh"), command=self._load_training).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="Export CSV", command=self._export_training_csv).pack(side="left", padx=4)

        # Treeview
        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill="both", expand=True)
        cols = ("id", "staff_id", "training_type", "completed_date",
                "expiry_date", "certificate_ref", "status")
        self._trn_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        headings = {
            "id": (t("common.id"), 40), "staff_id": (t("common.id"), 70),
            "training_type": (t("common.type"), 90), "completed_date": (t("common.date"), 100),
            "expiry_date": (t("common.end_date"), 100), "certificate_ref": (t("common.details"), 120),
            "status": (t("common.status"), 80),
        }
        for col, (text, width) in headings.items():
            self._trn_tree.heading(col, text=text)
            self._trn_tree.column(col, width=width, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._trn_tree.yview)
        self._trn_tree.configure(yscrollcommand=vsb.set)
        self._trn_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._trn_status = tk.StringVar(value=t("common.ready"))
        tk.Label(tab, textvariable=self._trn_status, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", pady=(4, 0))

    # ── Statistics Tab ─────────────────────────────────────────────

    def _build_stats_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("common.summary"))

        self._stats_text = tk.Text(tab, wrap="word", font=("Courier", 10),
                                    state="disabled", bg="white", height=20)
        self._stats_text.pack(fill="both", expand=True, pady=(0, 8))

        ttk.Button(tab, text=t("common.refresh"), command=self._load_stats).pack(anchor="w")

    # ── Data Loading ───────────────────────────────────────────────

    def _load_referrals(self):
        self._ref_tree.delete(*self._ref_tree.get_children())
        try:
            kwargs: dict = {}
            s = self._ref_status_var.get()
            if s:
                kwargs["status"] = s
            r = self._ref_risk_var.get()
            if r:
                kwargs["risk_level"] = r
            q = self._ref_search_var.get().strip()
            if q:
                kwargs["search"] = q
            items = self._svc.list_referrals(**kwargs)
            for item in items:
                ch = t("common.yes") if item.get("channel_referral") else t("common.no")
                self._ref_tree.insert("", "end", iid=item["id"], values=(
                    item["id"], item.get("subject_name", ""),
                    item.get("subject_type", ""), item.get("concern_type", ""),
                    item.get("risk_level", ""), ch,
                    item.get("status", ""), item.get("created_at", ""),
                ))
            self._ref_status.set(t("prevent_duty.count_loaded", count=len(items)))
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _load_training(self):
        self._trn_tree.delete(*self._trn_tree.get_children())
        try:
            kwargs: dict = {}
            s = self._trn_status_var.get()
            if s:
                kwargs["status"] = s
            if self._trn_expiring_var.get():
                kwargs["expiring"] = True
            items = self._svc.list_training(**kwargs)
            for item in items:
                self._trn_tree.insert("", "end", iid=item["id"], values=(
                    item["id"], item.get("staff_id", ""),
                    item.get("training_type", ""), item.get("completed_date", ""),
                    item.get("expiry_date", ""), item.get("certificate_ref", ""),
                    item.get("status", ""),
                ))
            self._trn_status.set(t("prevent_duty.count_loaded", count=len(items)))
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _load_stats(self):
        try:
            stats = self._svc.get_stats()
            lines = [
                f"=== {t('prevent_duty.management')} {t('common.summary')} ===",
                "",
                t("prevent_duty.referral").upper(),
                f"  {t('common.total')}:             {stats.get('total_referrals', 0)}",
                f"  {t('common.active')}:              {stats.get('open_referrals', 0)}",
                f"  {t('common.completed')}:            {stats.get('closed_referrals', 0)}",
                f"  Channel:           {stats.get('channel_referrals', 0)}",
                "",
                f"  {t('common.priority')}:",
            ]
            for level, count in stats.get("by_risk_level", {}).items():
                lines.append(f"    {level:<12} {count}")
            lines += [
                "",
                t("prevent_duty.training_status").upper(),
                f"  {t('common.total')}:     {stats.get('total_training', 0)}",
                f"  {t('common.completed')}:         {stats.get('completed_training', 0)}",
                f"  {t('common.overdue')}:   {stats.get('expiring_soon', 0)}",
            ]
            self._stats_text.configure(state="normal")
            self._stats_text.delete("1.0", "end")
            self._stats_text.insert("1.0", "\n".join(lines))
            self._stats_text.configure(state="disabled")
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    # ── Referral Actions ───────────────────────────────────────────

    def _selected_ref_id(self) -> int | None:
        sel = self._ref_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"))
            return None
        return int(sel[0])

    def _on_new_referral(self):
        dlg = _ReferralDialog(self, title=t("prevent_duty.log_concern"))
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            reported_by = None
            if self._auth and hasattr(self._auth, "current_user") and self._auth.current_user:
                reported_by = self._auth.current_user.get("user_id")
            self._svc.create_referral(
                subject_name=dlg.result["subject_name"],
                concern_details=dlg.result["concern_details"],
                reported_by=reported_by,
                subject_type=dlg.result.get("subject_type", "student"),
                subject_id=dlg.result.get("subject_id"),
                concern_type=dlg.result.get("concern_type") or None,
                risk_level=dlg.result.get("risk_level", "low"),
                actions_taken=dlg.result.get("actions_taken") or None,
            )
            messagebox.showinfo(t("common.success"), t("common.created_success"))
            self._load_referrals()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _on_view_referral(self):
        rid = self._selected_ref_id()
        if rid is None:
            return
        item = self._svc.get_referral(rid)
        if not item:
            messagebox.showerror(t("common.error"), t("common.no_data"))
            return
        dlg = _ViewReferralDialog(self, item)
        self.wait_window(dlg)

    def _on_edit_referral(self):
        rid = self._selected_ref_id()
        if rid is None:
            return
        item = self._svc.get_referral(rid)
        if not item:
            messagebox.showerror(t("common.error"), t("common.no_data"))
            return
        dlg = _ReferralDialog(self, title=t("common.edit"), item=item)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.update_referral(rid, **dlg.result)
            messagebox.showinfo(t("common.success"), t("common.updated_success"))
            self._load_referrals()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _on_escalate(self):
        rid = self._selected_ref_id()
        if rid is None:
            return
        ref = self._svc.get_referral(rid)
        if not ref:
            messagebox.showerror(t("common.error"), t("common.no_data"))
            return
        if ref.get("channel_referral"):
            messagebox.showinfo(t("common.info"), t("common.completed"))
            return
        if not messagebox.askyesno(t("common.confirm"), t("common.confirm")):
            return
        # Ask for optional reference
        win = tk.Toplevel(self)
        win.title(t("common.details"))
        win.resizable(False, False)
        win.grab_set()
        tk.Label(win, text=t("common.details") + ":", padx=10, pady=5).pack()
        ref_var = tk.StringVar()
        ttk.Entry(win, textvariable=ref_var, width=30).pack(padx=10, pady=5)
        result = {"done": False}

        def _submit():
            result["done"] = True
            win.destroy()

        ttk.Button(win, text=t("common.submit"), command=_submit).pack(pady=10)
        self.wait_window(win)
        if not result["done"]:
            return
        try:
            self._svc.escalate_to_channel(rid, channel_reference=ref_var.get().strip() or None)
            messagebox.showinfo(t("common.success"), t("common.updated_success"))
            self._load_referrals()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _on_delete_referral(self):
        rid = self._selected_ref_id()
        if rid is None:
            return
        if not messagebox.askyesno(t("common.confirm_delete"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_referral(rid)
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_referrals()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    # ── Training Actions ───────────────────────────────────────────

    def _selected_trn_id(self) -> int | None:
        sel = self._trn_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"))
            return None
        return int(sel[0])

    def _on_new_training(self):
        dlg = _TrainingDialog(self, title=t("common.create"))
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.create_training(
                staff_id=dlg.result["staff_id"],
                training_type=dlg.result.get("training_type", "basic"),
                completed_date=dlg.result.get("completed_date") or None,
                expiry_date=dlg.result.get("expiry_date") or None,
                certificate_ref=dlg.result.get("certificate_ref") or None,
                status=dlg.result.get("status", "completed"),
            )
            messagebox.showinfo(t("common.success"), t("common.created_success"))
            self._load_training()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _on_edit_training(self):
        tid = self._selected_trn_id()
        if tid is None:
            return
        item = self._svc.get_training(tid)
        if not item:
            messagebox.showerror(t("common.error"), t("common.no_data"))
            return
        dlg = _TrainingDialog(self, title=t("common.edit"), item=item)
        self.wait_window(dlg)
        if dlg.result is None:
            return
        try:
            self._svc.update_training(tid, **dlg.result)
            messagebox.showinfo(t("common.success"), t("common.updated_success"))
            self._load_training()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _on_delete_training(self):
        tid = self._selected_trn_id()
        if tid is None:
            return
        if not messagebox.askyesno(t("common.confirm_delete"), t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_training(tid)
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
            self._load_training()
        except Exception as exc:
            messagebox.showerror(t("common.error"), str(exc))

    def _export_referrals_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._ref_tree, "prevent_duty_referrals_export.csv")

    def _export_training_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._trn_tree, "prevent_duty_training_export.csv")

    # ── Refresh ────────────────────────────────────────────────────

    def refresh(self):
        """Reload all tabs."""
        self._load_referrals()
        self._load_training()
        self._load_stats()
