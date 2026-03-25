"""Risk Management GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.core.i18n import t
from education_system.college_system.modules.domain.risk_management.services.risk_management_service import (
    RiskManagementService, RISK_CATEGORIES, RISK_STATUSES,
)


class RiskManagementFrame(tk.Frame):
    """Risk Management frame with Risk Register, Reviews, and Statistics tabs."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = RiskManagementService(db_path)
        self._build_ui()

    # ── UI Construction ──────────────────────────────────────────────────

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("risk_management.management"),
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_register_tab()
        self._build_reviews_tab()
        self._build_stats_tab()

    # ── Tab 1: Risk Register ─────────────────────────────────────────────

    def _build_register_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("risk_management.risk_title"))

        # Filters
        filt = tk.Frame(tab, bg="#ecf0f1")
        filt.pack(fill="x", pady=(0, 8))

        tk.Label(filt, text=t("common.status") + ":", bg="#ecf0f1").pack(side="left")
        self._reg_status_var = tk.StringVar(value=t("common.all"))
        ttk.Combobox(filt, textvariable=self._reg_status_var,
                     values=[t("common.all")] + RISK_STATUSES,
                     width=12, state="readonly").pack(side="left", padx=5)

        tk.Label(filt, text=t("common.category") + ":", bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._reg_cat_var = tk.StringVar(value=t("common.all"))
        ttk.Combobox(filt, textvariable=self._reg_cat_var,
                     values=[t("common.all")] + RISK_CATEGORIES,
                     width=16, state="readonly").pack(side="left", padx=5)

        tk.Label(filt, text=t("common.search") + ":", bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._reg_search_var = tk.StringVar()
        ttk.Entry(filt, textvariable=self._reg_search_var, width=18).pack(side="left", padx=5)

        ttk.Button(filt, text=t("common.filter"), command=self._load_risks).pack(side="left", padx=5)

        # Buttons
        btn_bar = tk.Frame(tab, bg="#ecf0f1")
        btn_bar.pack(fill="x", pady=(0, 8))
        ttk.Button(btn_bar, text=t("risk_management.add_risk"), command=self._new_risk_dialog).pack(side="left", padx=2)
        ttk.Button(btn_bar, text=t("common.view"), command=self._view_risk).pack(side="left", padx=2)
        ttk.Button(btn_bar, text=t("common.edit"), command=self._edit_risk_dialog).pack(side="left", padx=2)
        ttk.Button(btn_bar, text=t("common.delete"), command=self._delete_risk).pack(side="left", padx=2)
        ttk.Button(btn_bar, text="Export CSV", command=self._export_risks_csv).pack(side="left", padx=2)

        # Treeview
        cols = ("id", "risk_title", "category", "likelihood", "impact",
                "risk_score", "status", "risk_owner", "review_date")
        self._risk_tree = ttk.Treeview(tab, columns=cols, show="headings",
                                       selectmode="browse")
        for c, h, w in [
            ("id", t("common.id"), 40), ("risk_title", t("risk_management.risk_title"), 200),
            ("category", t("common.category"), 110), ("likelihood", t("risk_management.likelihood"), 35),
            ("impact", t("risk_management.impact"), 35), ("risk_score", t("common.score"), 50),
            ("status", t("common.status"), 80), ("risk_owner", t("risk_management.owner"), 100),
            ("review_date", t("common.date"), 90),
        ]:
            self._risk_tree.heading(c, text=h)
            self._risk_tree.column(c, width=w, anchor="center")
        self._risk_tree.column("risk_title", anchor="w")

        self._risk_tree.tag_configure("high", foreground="#c0392b")
        self._risk_tree.tag_configure("medium", foreground="#e67e22")
        self._risk_tree.tag_configure("low", foreground="#27ae60")

        sb = ttk.Scrollbar(tab, orient="vertical", command=self._risk_tree.yview)
        self._risk_tree.configure(yscrollcommand=sb.set)
        self._risk_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    # ── Tab 2: Reviews ───────────────────────────────────────────────────

    def _build_reviews_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("common.history"))

        top = tk.Frame(tab, bg="#ecf0f1")
        top.pack(fill="x", pady=(0, 8))
        tk.Label(top, text=t("common.id") + ":", bg="#ecf0f1").pack(side="left")
        self._rev_risk_id_var = tk.StringVar()
        ttk.Entry(top, textvariable=self._rev_risk_id_var, width=8).pack(side="left", padx=5)
        ttk.Button(top, text=t("common.refresh"), command=self._load_reviews).pack(side="left", padx=5)
        ttk.Button(top, text=t("common.create"), command=self._new_review_dialog).pack(side="left", padx=5)
        ttk.Button(top, text=t("common.delete"), command=self._delete_review).pack(side="left", padx=5)
        ttk.Button(top, text="Export CSV", command=self._export_reviews_csv).pack(side="left", padx=5)

        cols = ("id", "risk_id", "review_date", "reviewer", "previous_score",
                "new_score", "commentary", "actions_taken")
        self._rev_tree = ttk.Treeview(tab, columns=cols, show="headings",
                                      selectmode="browse")
        for c, h, w in [
            ("id", t("common.id"), 40), ("risk_id", t("risk_management.risk_title"), 50),
            ("review_date", t("common.date"), 90), ("reviewer", t("common.name"), 100),
            ("previous_score", t("common.score"), 45), ("new_score", t("common.score"), 45),
            ("commentary", t("common.comments"), 200), ("actions_taken", t("common.actions"), 200),
        ]:
            self._rev_tree.heading(c, text=h)
            self._rev_tree.column(c, width=w, anchor="center")
        self._rev_tree.column("commentary", anchor="w")
        self._rev_tree.column("actions_taken", anchor="w")

        sb = ttk.Scrollbar(tab, orient="vertical", command=self._rev_tree.yview)
        self._rev_tree.configure(yscrollcommand=sb.set)
        self._rev_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    # ── Tab 3: Statistics ────────────────────────────────────────────────

    def _build_stats_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("common.summary"))

        self._stats_text = tk.Text(tab, wrap="word", font=("Courier", 11),
                                   bg="white", state="disabled", height=20)
        self._stats_text.pack(fill="both", expand=True)

        ttk.Button(tab, text=t("common.refresh"),
                   command=self._load_stats).pack(pady=8)

    def _export_risks_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._risk_tree, "risk_register_export.csv")

    def _export_reviews_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._rev_tree, "risk_reviews_export.csv")

    # ── Data Loading ─────────────────────────────────────────────────────

    def refresh(self):
        """Reload all tabs."""
        self._load_risks()
        self._load_stats()

    def _load_risks(self):
        self._risk_tree.delete(*self._risk_tree.get_children())
        try:
            status = self._reg_status_var.get()
            cat = self._reg_cat_var.get()
            search = self._reg_search_var.get().strip() or None
            risks = self._svc.list_risks(
                status=status if status != t("common.all") else None,
                category=cat if cat != t("common.all") else None,
                search=search,
            )
            for r in risks:
                score = r.get("risk_score") or 0
                tag = "high" if score >= 15 else ("medium" if score >= 8 else "low")
                self._risk_tree.insert("", "end", values=(
                    r["id"], r["risk_title"], r["category"],
                    r["likelihood"], r["impact"], score,
                    r["status"], r.get("risk_owner", ""),
                    r.get("review_date", ""),
                ), tags=(tag,))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e), parent=self)

    def _load_reviews(self):
        self._rev_tree.delete(*self._rev_tree.get_children())
        rid = self._rev_risk_id_var.get().strip()
        if not rid or not rid.isdigit():
            messagebox.showwarning(t("common.input"), t("common.field_required"), parent=self)
            return
        try:
            reviews = self._svc.list_reviews(int(rid))
            if not reviews:
                messagebox.showinfo(t("common.info"), t("common.no_data"), parent=self)
                return
            for rv in reviews:
                self._rev_tree.insert("", "end", values=(
                    rv["id"], rv["risk_id"], rv["review_date"],
                    rv.get("reviewer", ""), rv.get("previous_score", ""),
                    rv.get("new_score", ""), rv.get("commentary", ""),
                    rv.get("actions_taken", ""),
                ))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e), parent=self)

    def _load_stats(self):
        try:
            stats = self._svc.get_stats()
            lines = [
                f"=== {t('risk_management.management')} {t('common.summary')} ===",
                "",
                f"  {t('common.total')}:        {stats['total_risks']}",
                f"  {t('common.high')} (>=15):  {stats['high_risks']}",
                f"  {t('common.average')}:      {stats['avg_risk_score']}",
                f"  {t('common.total')} {t('common.history')}:      {stats['reviews_count']}",
                "",
                f"  {t('common.status')}:",
            ]
            for s, c in stats["by_status"].items():
                lines.append(f"    {s:<14} {c}")
            lines.append("")
            lines.append(f"  {t('common.category')}:")
            for cat, c in stats["by_category"].items():
                lines.append(f"    {cat:<18} {c}")

            self._stats_text.configure(state="normal")
            self._stats_text.delete("1.0", "end")
            self._stats_text.insert("1.0", "\n".join(lines))
            self._stats_text.configure(state="disabled")
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e), parent=self)

    # ── Risk Dialogs ─────────────────────────────────────────────────────

    def _new_risk_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("risk_management.add_risk"))
        dlg.geometry("500x520")
        dlg.transient(self)
        dlg.grab_set()

        fields = self._build_risk_form(dlg)

        def _save():
            title = fields["risk_title"].get().strip()
            if not title:
                messagebox.showwarning(t("common.input"), t("common.field_required"), parent=dlg)
                return
            try:
                lk = int(fields["likelihood"].get())
                imp = int(fields["impact"].get())
            except ValueError:
                messagebox.showwarning(t("common.input"), t("common.invalid_input"),
                                       parent=dlg)
                return
            try:
                self._svc.create_risk(
                    risk_title=title,
                    category=fields["category"].get(),
                    description=fields["description"].get("1.0", "end").strip() or None,
                    likelihood=lk,
                    impact=imp,
                    current_controls=fields["current_controls"].get().strip() or None,
                    mitigation_strategy=fields["mitigation_strategy"].get().strip() or None,
                    risk_owner=fields["risk_owner"].get().strip() or None,
                    review_date=fields["review_date"].get().strip() or None,
                    status=fields["status"].get(),
                    notes=fields["notes"].get().strip() or None,
                )
                messagebox.showinfo(t("common.success"), t("common.created_success"), parent=dlg)
                dlg.destroy()
                self._load_risks()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e), parent=dlg)

        ttk.Button(dlg, text=t("common.save"), command=_save).pack(pady=10)

    def _view_risk(self):
        sel = self._risk_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"), parent=self)
            return
        rid = self._risk_tree.item(sel[0])["values"][0]
        try:
            r = self._svc.get_risk(int(rid))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e), parent=self)
            return
        if not r:
            messagebox.showinfo(t("common.info"), t("common.no_data"), parent=self)
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"{t('risk_management.risk_title')} #{r['id']}")
        dlg.geometry("480x480")
        dlg.transient(self)

        txt = tk.Text(dlg, wrap="word", font=("Courier", 10), bg="white",
                      state="disabled")
        txt.pack(fill="both", expand=True, padx=10, pady=10)

        score = r.get("risk_score") or 0
        residual = ""
        if r.get("residual_likelihood") and r.get("residual_impact"):
            residual = f"\n  Residual L x I:    {r['residual_likelihood']} x {r['residual_impact']} = {r['residual_likelihood'] * r['residual_impact']}"

        info = (
            f"  {t('common.id')}:                {r['id']}\n"
            f"  {t('common.title')}:             {r['risk_title']}\n"
            f"  {t('common.category')}:          {r['category']}\n"
            f"  {t('common.status')}:            {r['status']}\n"
            f"  {t('risk_management.likelihood')}:        {r['likelihood']}\n"
            f"  {t('risk_management.impact')}:            {r['impact']}\n"
            f"  {t('common.score')}:        {score}\n"
            f"{residual}\n"
            f"  {t('risk_management.owner')}:             {r.get('risk_owner', '')}\n"
            f"  {t('common.date')}:       {r.get('review_date', '')}\n"
            f"  {t('common.details')}:          {r.get('current_controls', '')}\n"
            f"  {t('risk_management.mitigation')}:        {r.get('mitigation_strategy', '')}\n"
            f"  {t('common.notes')}:             {r.get('notes', '')}\n"
            f"  {t('common.description')}:\n    {r.get('description', '')}\n"
            f"\n  {t('common.created_at')}:  {r.get('created_at', '')}"
            f"\n  {t('common.updated_at')}:  {r.get('updated_at', '')}"
        )
        txt.configure(state="normal")
        txt.insert("1.0", info)
        txt.configure(state="disabled")

    def _edit_risk_dialog(self):
        sel = self._risk_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"), parent=self)
            return
        rid = self._risk_tree.item(sel[0])["values"][0]
        try:
            r = self._svc.get_risk(int(rid))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e), parent=self)
            return
        if not r:
            messagebox.showinfo(t("common.info"), t("common.no_data"), parent=self)
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"{t('common.edit')} #{r['id']}")
        dlg.geometry("500x560")
        dlg.transient(self)
        dlg.grab_set()

        fields = self._build_risk_form(dlg, r)

        def _save():
            title = fields["risk_title"].get().strip()
            if not title:
                messagebox.showwarning(t("common.input"), t("common.field_required"), parent=dlg)
                return
            try:
                lk = int(fields["likelihood"].get())
                imp = int(fields["impact"].get())
            except ValueError:
                messagebox.showwarning(t("common.input"), t("common.invalid_input"),
                                       parent=dlg)
                return
            try:
                self._svc.update_risk(
                    int(rid),
                    risk_title=title,
                    category=fields["category"].get(),
                    description=fields["description"].get("1.0", "end").strip() or None,
                    likelihood=lk,
                    impact=imp,
                    current_controls=fields["current_controls"].get().strip() or None,
                    mitigation_strategy=fields["mitigation_strategy"].get().strip() or None,
                    risk_owner=fields["risk_owner"].get().strip() or None,
                    review_date=fields["review_date"].get().strip() or None,
                    status=fields["status"].get(),
                    notes=fields["notes"].get().strip() or None,
                )
                messagebox.showinfo(t("common.success"), t("common.updated_success"), parent=dlg)
                dlg.destroy()
                self._load_risks()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e), parent=dlg)

        ttk.Button(dlg, text=t("common.save"), command=_save).pack(pady=10)

    def _delete_risk(self):
        sel = self._risk_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"), parent=self)
            return
        rid = self._risk_tree.item(sel[0])["values"][0]
        if not messagebox.askyesno(t("common.confirm_delete"),
                                   t("common.delete_confirm_msg"),
                                   parent=self):
            return
        try:
            self._svc.delete_risk(int(rid))
            messagebox.showinfo(t("common.success"), t("common.deleted_success"), parent=self)
            self._load_risks()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e), parent=self)

    # ── Review Dialogs ───────────────────────────────────────────────────

    def _new_review_dialog(self):
        rid = self._rev_risk_id_var.get().strip()
        if not rid or not rid.isdigit():
            messagebox.showwarning(t("common.input"), t("common.field_required"), parent=self)
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"{t('common.create')} #{rid}")
        dlg.geometry("420x350")
        dlg.transient(self)
        dlg.grab_set()

        frame = tk.Frame(dlg, padx=15, pady=10)
        frame.pack(fill="both", expand=True)

        vars_ = {}

        for label, key, width in [
            (t("common.date") + " (YYYY-MM-DD):", "review_date", 14),
            (t("common.name") + ":", "reviewer", 20),
            (t("common.score") + ":", "previous_score", 6),
            (t("common.score") + ":", "new_score", 6),
            (t("common.comments") + ":", "commentary", 30),
            (t("common.actions") + ":", "actions_taken", 30),
        ]:
            row = tk.Frame(frame)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label, width=22, anchor="w").pack(side="left")
            v = tk.StringVar()
            ttk.Entry(row, textvariable=v, width=width).pack(side="left", padx=5)
            vars_[key] = v

        def _save():
            rd = vars_["review_date"].get().strip()
            if not rd:
                messagebox.showwarning(t("common.input"), t("common.field_required"), parent=dlg)
                return
            prev = vars_["previous_score"].get().strip()
            new = vars_["new_score"].get().strip()
            try:
                self._svc.create_review(
                    risk_id=int(rid),
                    review_date=rd,
                    reviewer=vars_["reviewer"].get().strip() or None,
                    previous_score=int(prev) if prev else None,
                    new_score=int(new) if new else None,
                    commentary=vars_["commentary"].get().strip() or None,
                    actions_taken=vars_["actions_taken"].get().strip() or None,
                )
                messagebox.showinfo(t("common.success"), t("common.created_success"), parent=dlg)
                dlg.destroy()
                self._load_reviews()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e), parent=dlg)

        ttk.Button(frame, text=t("common.save"), command=_save).pack(pady=10)

    def _delete_review(self):
        sel = self._rev_tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("common.select_first"), parent=self)
            return
        rev_id = self._rev_tree.item(sel[0])["values"][0]
        if not messagebox.askyesno(t("common.confirm_delete"), t("common.delete_confirm_msg"), parent=self):
            return
        try:
            self._svc.delete_review(int(rev_id))
            messagebox.showinfo(t("common.success"), t("common.deleted_success"), parent=self)
            self._load_reviews()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e), parent=self)

    # ── Helpers ──────────────────────────────────────────────────────────

    def _build_risk_form(self, parent, existing=None):
        """Build a risk form inside *parent*. Returns dict of field widgets."""
        frame = tk.Frame(parent, padx=15, pady=10)
        frame.pack(fill="both", expand=True)

        fields = {}

        # Title
        row = tk.Frame(frame); row.pack(fill="x", pady=3)
        tk.Label(row, text=t("risk_management.risk_title") + ":", width=16, anchor="w").pack(side="left")
        v = tk.StringVar(value=existing["risk_title"] if existing else "")
        ttk.Entry(row, textvariable=v, width=30).pack(side="left", padx=5)
        fields["risk_title"] = v

        # Category
        row = tk.Frame(frame); row.pack(fill="x", pady=3)
        tk.Label(row, text=t("common.category") + ":", width=16, anchor="w").pack(side="left")
        v = tk.StringVar(value=existing["category"] if existing else "operational")
        ttk.Combobox(row, textvariable=v, values=RISK_CATEGORIES,
                     width=18, state="readonly").pack(side="left", padx=5)
        fields["category"] = v

        # Likelihood & Impact
        row = tk.Frame(frame); row.pack(fill="x", pady=3)
        tk.Label(row, text=t("risk_management.likelihood") + " (1-5):", width=16, anchor="w").pack(side="left")
        v = tk.StringVar(value=str(existing["likelihood"]) if existing else "3")
        ttk.Spinbox(row, textvariable=v, from_=1, to=5, width=4).pack(side="left", padx=5)
        fields["likelihood"] = v
        tk.Label(row, text=t("risk_management.impact") + " (1-5):").pack(side="left", padx=(15, 0))
        v2 = tk.StringVar(value=str(existing["impact"]) if existing else "3")
        ttk.Spinbox(row, textvariable=v2, from_=1, to=5, width=4).pack(side="left", padx=5)
        fields["impact"] = v2

        # Score preview
        score_lbl = tk.Label(frame, text="", font=("Helvetica", 11, "bold"),
                             fg="#c0392b")
        score_lbl.pack(anchor="w", pady=2)

        def _update_score(*_args):
            try:
                s = int(fields["likelihood"].get()) * int(fields["impact"].get())
                color = "#c0392b" if s >= 15 else ("#e67e22" if s >= 8 else "#27ae60")
                score_lbl.configure(text=f"  {t('common.score')}: {s}", fg=color)
            except ValueError:
                score_lbl.configure(text="")

        fields["likelihood"].trace_add("write", _update_score)
        fields["impact"].trace_add("write", _update_score)
        _update_score()

        # Status
        row = tk.Frame(frame); row.pack(fill="x", pady=3)
        tk.Label(row, text=t("common.status") + ":", width=16, anchor="w").pack(side="left")
        v = tk.StringVar(value=existing["status"] if existing else "open")
        ttk.Combobox(row, textvariable=v, values=RISK_STATUSES,
                     width=14, state="readonly").pack(side="left", padx=5)
        fields["status"] = v

        # Owner
        row = tk.Frame(frame); row.pack(fill="x", pady=3)
        tk.Label(row, text=t("risk_management.owner") + ":", width=16, anchor="w").pack(side="left")
        v = tk.StringVar(value=existing.get("risk_owner", "") if existing else "")
        ttk.Entry(row, textvariable=v, width=20).pack(side="left", padx=5)
        fields["risk_owner"] = v

        # Review Date
        row = tk.Frame(frame); row.pack(fill="x", pady=3)
        tk.Label(row, text=t("common.date") + ":", width=16, anchor="w").pack(side="left")
        v = tk.StringVar(value=existing.get("review_date", "") if existing else "")
        ttk.Entry(row, textvariable=v, width=14).pack(side="left", padx=5)
        fields["review_date"] = v

        # Controls
        row = tk.Frame(frame); row.pack(fill="x", pady=3)
        tk.Label(row, text=t("common.details") + ":", width=16, anchor="w").pack(side="left")
        v = tk.StringVar(value=existing.get("current_controls", "") if existing else "")
        ttk.Entry(row, textvariable=v, width=30).pack(side="left", padx=5)
        fields["current_controls"] = v

        # Mitigation
        row = tk.Frame(frame); row.pack(fill="x", pady=3)
        tk.Label(row, text=t("risk_management.mitigation") + ":", width=16, anchor="w").pack(side="left")
        v = tk.StringVar(value=existing.get("mitigation_strategy", "") if existing else "")
        ttk.Entry(row, textvariable=v, width=30).pack(side="left", padx=5)
        fields["mitigation_strategy"] = v

        # Notes
        row = tk.Frame(frame); row.pack(fill="x", pady=3)
        tk.Label(row, text=t("common.notes") + ":", width=16, anchor="w").pack(side="left")
        v = tk.StringVar(value=existing.get("notes", "") if existing else "")
        ttk.Entry(row, textvariable=v, width=30).pack(side="left", padx=5)
        fields["notes"] = v

        # Description
        tk.Label(frame, text=t("common.description") + ":", anchor="w").pack(fill="x", pady=(5, 0))
        desc = tk.Text(frame, height=4, wrap="word")
        desc.pack(fill="x", pady=3)
        if existing and existing.get("description"):
            desc.insert("1.0", existing["description"])
        fields["description"] = desc

        return fields
