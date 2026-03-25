"""Letter Templates GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.core.i18n import t
from education_system.college_system.modules.domain.letter_templates.services.letter_templates_service import LetterTemplateService


class LetterTemplateFrame(tk.Frame):
    """Letter Templates management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = LetterTemplateService(db_path)
        self._build_ui()
        self.refresh()

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("letter_templates.management"),
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_templates_tab()
        self._build_letters_tab()
        self._build_stats_tab()

    # ── Tab 1: Templates ──────────────────────────────────────────────

    def _build_templates_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("letter_templates.templates"))

        # Filter bar
        fbar = tk.Frame(tab, bg="#ecf0f1")
        fbar.pack(fill="x", pady=(0, 5))

        tk.Label(fbar, text=t("common.category") + ":", bg="#ecf0f1").pack(side="left")
        self._tmpl_cat_var = tk.StringVar(value="All")
        cat_cb = ttk.Combobox(fbar, textvariable=self._tmpl_cat_var,
                              values=["All", "general", "admissions",
                                      "finance", "academic", "pastoral",
                                      "disciplinary", "hr", "other"],
                              state="readonly", width=14)
        cat_cb.pack(side="left", padx=(4, 10))
        cat_cb.bind("<<ComboboxSelected>>",
                     lambda _: self._refresh_templates())

        tk.Label(fbar, text=t("common.search") + ":", bg="#ecf0f1").pack(side="left")
        self._tmpl_search_var = tk.StringVar()
        se = tk.Entry(fbar, textvariable=self._tmpl_search_var, width=20)
        se.pack(side="left", padx=4)
        se.bind("<Return>", lambda _: self._refresh_templates())
        ttk.Button(fbar, text=t("common.search"),
                   command=self._refresh_templates).pack(side="left")

        # Toolbar
        tb = tk.Frame(tab, bg="#ecf0f1")
        tb.pack(fill="x", pady=(0, 5))
        for txt, cmd in [(t("common.create"), self._new_template),
                         (t("common.view"), self._view_template),
                         (t("common.edit"), self._edit_template),
                         (t("letter_templates.toggle_active"), self._toggle_template),
                         (t("common.delete"), self._delete_template)]:
            ttk.Button(tb, text=txt, command=cmd).pack(side="left", padx=2)
        ttk.Button(tb, text=t("common.export_csv", default="Export CSV"), command=self._export_templates_csv).pack(side="right", padx=2)

        # Treeview
        cols = ("id", "name", "category", "subject", "active", "merge_fields")
        self._tree_tmpl = ttk.Treeview(tab, columns=cols, show="headings",
                                       selectmode="browse")
        for cid, label, w in [("id", t("common.id"), 40),
                              ("name", t("letter_templates.template_name"), 200),
                              ("category", t("common.category"), 100),
                              ("subject", t("letter_templates.subject"), 180),
                              ("active", t("letter_templates.active"), 60),
                              ("merge_fields", t("letter_templates.merge_fields"), 180)]:
            self._tree_tmpl.heading(cid, text=label)
            self._tree_tmpl.column(cid, width=w,
                                   anchor="center" if cid in ("id", "active")
                                   else "w")
        vsb = ttk.Scrollbar(tab, orient="vertical",
                            command=self._tree_tmpl.yview)
        self._tree_tmpl.configure(yscrollcommand=vsb.set)
        self._tree_tmpl.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    # ── Tab 2: Generated Letters ──────────────────────────────────────

    def _build_letters_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("letter_templates.generated_letters"))

        # Filter bar
        fbar = tk.Frame(tab, bg="#ecf0f1")
        fbar.pack(fill="x", pady=(0, 5))

        tk.Label(fbar, text=t("letter_templates.template") + ":", bg="#ecf0f1").pack(side="left")
        self._let_tmpl_var = tk.StringVar(value="All")
        self._let_tmpl_cb = ttk.Combobox(fbar,
                                         textvariable=self._let_tmpl_var,
                                         state="readonly", width=20)
        self._let_tmpl_cb.pack(side="left", padx=(4, 10))
        self._let_tmpl_cb.bind("<<ComboboxSelected>>",
                               lambda _: self._refresh_letters())

        tk.Label(fbar, text=t("common.status") + ":", bg="#ecf0f1").pack(side="left")
        self._let_status_var = tk.StringVar(value="All")
        st_cb = ttk.Combobox(fbar, textvariable=self._let_status_var,
                             values=["All", "draft", "sent", "archived"],
                             state="readonly", width=10)
        st_cb.pack(side="left", padx=4)
        st_cb.bind("<<ComboboxSelected>>",
                    lambda _: self._refresh_letters())

        # Toolbar
        tb = tk.Frame(tab, bg="#ecf0f1")
        tb.pack(fill="x", pady=(0, 5))
        for txt, cmd in [(t("common.create"), self._new_letter),
                         (t("common.view"), self._view_letter),
                         (t("letter_templates.mark_sent"), self._mark_sent),
                         (t("common.delete"), self._delete_letter)]:
            ttk.Button(tb, text=txt, command=cmd).pack(side="left", padx=2)
        ttk.Button(tb, text=t("common.export_csv", default="Export CSV"), command=self._export_letters_csv).pack(side="right", padx=2)

        # Treeview
        cols = ("id", "template", "recipient", "subject", "via", "status",
                "sent_at")
        self._tree_let = ttk.Treeview(tab, columns=cols, show="headings",
                                      selectmode="browse")
        for cid, label, w in [("id", t("common.id"), 40),
                              ("template", t("letter_templates.template"), 150),
                              ("recipient", t("letter_templates.recipient"), 150),
                              ("subject", t("letter_templates.subject"), 160),
                              ("via", t("letter_templates.sent_via"), 60),
                              ("status", t("common.status"), 70),
                              ("sent_at", t("letter_templates.sent_at"), 140)]:
            self._tree_let.heading(cid, text=label)
            self._tree_let.column(cid, width=w,
                                  anchor="center" if cid in ("id", "via",
                                                              "status")
                                  else "w")
        vsb = ttk.Scrollbar(tab, orient="vertical",
                            command=self._tree_let.yview)
        self._tree_let.configure(yscrollcommand=vsb.set)
        self._tree_let.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    # ── Tab 3: Statistics ─────────────────────────────────────────────

    def _build_stats_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text=t("common.summary"))
        self._stats_text = tk.Text(tab, wrap="word", font=("Courier", 11),
                                   state="disabled", bg="white")
        self._stats_text.pack(fill="both", expand=True)
        ttk.Button(tab, text=t("common.refresh"),
                   command=self._refresh_stats).pack(pady=5)

    # ── Refresh methods ───────────────────────────────────────────────

    def refresh(self):
        self._refresh_templates()
        self._refresh_letters()
        self._refresh_stats()
        self._refresh_template_filter_cb()

    def _refresh_templates(self):
        for row in self._tree_tmpl.get_children():
            self._tree_tmpl.delete(row)
        cat = self._tmpl_cat_var.get()
        cat = None if cat == "All" else cat
        search = self._tmpl_search_var.get().strip() or None
        try:
            templates = self._svc.list_templates(category=cat, search=search)
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
            return
        for tmpl in templates:
            self._tree_tmpl.insert("", "end", values=(
                tmpl["id"],
                tmpl.get("template_name", ""),
                tmpl.get("category", ""),
                tmpl.get("subject_line", ""),
                t("common.yes") if tmpl.get("is_active") else t("common.no"),
                tmpl.get("merge_fields", ""),
            ))

    def _refresh_letters(self):
        for row in self._tree_let.get_children():
            self._tree_let.delete(row)
        tmpl = self._let_tmpl_var.get()
        status = self._let_status_var.get()
        tmpl_id = None
        if tmpl != "All":
            try:
                tmpl_id = int(tmpl.split(" ")[0])
            except (ValueError, IndexError):
                tmpl_id = None
        status = None if status == "All" else status
        try:
            letters = self._svc.list_letters(template_id=tmpl_id,
                                             status=status)
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
            return
        for lt in letters:
            self._tree_let.insert("", "end", values=(
                lt["id"],
                lt.get("template_name", ""),
                lt.get("recipient_name", ""),
                lt.get("subject", ""),
                lt.get("sent_via", ""),
                lt.get("status", ""),
                lt.get("sent_at", ""),
            ))

    def _refresh_stats(self):
        try:
            stats = self._svc.get_stats()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
            return
        self._stats_text.configure(state="normal")
        self._stats_text.delete("1.0", "end")
        lines = [
            f"=== {t('letter_templates.management')} - {t('common.summary')} ===\n",
            f"{t('letter_templates.total_templates')}:    {stats['total_templates']}",
            f"  {t('letter_templates.active')}:           {stats['active_templates']}",
            f"  {t('letter_templates.inactive')}:         {stats['inactive_templates']}",
            "",
            f"{t('letter_templates.total_letters')}:      {stats['total_letters']}",
            "",
            t("letter_templates.letters_by_status") + ":",
        ]
        for s, c in stats.get("by_status", {}).items():
            lines.append(f"  {s:<16} {c}")
        lines.append("")
        lines.append(t("letter_templates.templates_by_category") + ":")
        for cat, c in stats.get("by_category", {}).items():
            lines.append(f"  {cat:<16} {c}")
        self._stats_text.insert("1.0", "\n".join(lines))
        self._stats_text.configure(state="disabled")

    def _refresh_template_filter_cb(self):
        """Populate the template filter combobox on the letters tab."""
        try:
            templates = self._svc.list_templates()
        except Exception:
            templates = []
        vals = ["All"] + [f"{tmpl['id']} {tmpl['template_name']}"
                          for tmpl in templates]
        self._let_tmpl_cb["values"] = vals

    # ── CSV export ────────────────────────────────────────────────

    def _export_templates_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._tree_tmpl, "letter_templates.csv")

    def _export_letters_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._tree_let, "generated_letters.csv")

    # ── Template helpers ──────────────────────────────────────────────

    def _selected_template_id(self):
        sel = self._tree_tmpl.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"),
                                   t("common.select_first"))
            return None
        return self._tree_tmpl.item(sel[0])["values"][0]

    def _selected_letter_id(self):
        sel = self._tree_let.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"),
                                   t("common.select_first"))
            return None
        return self._tree_let.item(sel[0])["values"][0]

    # ── Template CRUD dialogs ─────────────────────────────────────────

    def _new_template(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("letter_templates.new_template"))
        dlg.geometry("520x480")
        dlg.grab_set()

        fields = {}
        for label, key, widget_type in [
            (t("letter_templates.template_name") + "*:", "template_name", "entry"),
            (t("common.category") + ":", "category", "combo"),
            (t("letter_templates.subject") + ":", "subject_line", "entry"),
            (t("letter_templates.merge_fields") + ":", "merge_fields", "entry"),
            (t("letter_templates.body") + "*:", "body_template", "text"),
        ]:
            tk.Label(dlg, text=label).pack(anchor="w", padx=10, pady=(6, 0))
            if widget_type == "entry":
                var = tk.StringVar()
                tk.Entry(dlg, textvariable=var, width=55).pack(
                    padx=10, fill="x")
                fields[key] = var
            elif widget_type == "combo":
                var = tk.StringVar(value="general")
                ttk.Combobox(dlg, textvariable=var, state="readonly",
                             values=["general", "admissions", "finance",
                                     "academic", "pastoral", "disciplinary",
                                     "hr", "other"],
                             width=20).pack(padx=10, anchor="w")
                fields[key] = var
            elif widget_type == "text":
                txt = tk.Text(dlg, width=55, height=10, wrap="word")
                txt.pack(padx=10, fill="both", expand=True)
                fields[key] = txt

        def _save():
            try:
                body = fields["body_template"].get("1.0", "end").strip()
                self._svc.create_template(
                    template_name=fields["template_name"].get(),
                    body_template=body,
                    category=fields["category"].get(),
                    subject_line=fields["subject_line"].get(),
                    merge_fields=fields["merge_fields"].get(),
                )
                dlg.destroy()
                self.refresh()
                messagebox.showinfo(t("common.success"), t("common.created_success"))
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("common.save"), command=_save).pack(pady=10)

    def _view_template(self):
        tid = self._selected_template_id()
        if tid is None:
            return
        tmpl = self._svc.get_template(tid)
        if not tmpl:
            messagebox.showerror(t("common.error"), t("common.not_found"))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"{t('letter_templates.template')} #{tmpl['id']}")
        dlg.geometry("520x450")
        dlg.grab_set()

        info = (
            f"{t('letter_templates.template_name')}:  {tmpl.get('template_name', '')}\n"
            f"{t('common.category')}:     {tmpl.get('category', '')}\n"
            f"{t('letter_templates.subject')}:      {tmpl.get('subject_line', '')}\n"
            f"{t('letter_templates.active')}:       {t('common.yes') if tmpl.get('is_active') else t('common.no')}\n"
            f"{t('letter_templates.merge_fields')}: {tmpl.get('merge_fields', '')}\n"
            f"{t('common.created')}:      {tmpl.get('created_at', '')}\n"
            f"{t('common.updated')}:      {tmpl.get('updated_at', '')}\n"
        )
        tk.Label(dlg, text=info, justify="left",
                 font=("Courier", 10)).pack(padx=10, pady=10, anchor="w")

        tk.Label(dlg, text=t("letter_templates.body") + ":").pack(anchor="w", padx=10)
        txt = tk.Text(dlg, wrap="word", height=12, state="normal")
        txt.pack(padx=10, fill="both", expand=True)
        txt.insert("1.0", tmpl.get("body_template", ""))
        txt.configure(state="disabled")
        ttk.Button(dlg, text=t("common.close"), command=dlg.destroy).pack(pady=8)

    def _edit_template(self):
        tid = self._selected_template_id()
        if tid is None:
            return
        tmpl = self._svc.get_template(tid)
        if not tmpl:
            messagebox.showerror(t("common.error"), t("common.not_found"))
            return

        dlg = tk.Toplevel(self)
        dlg.title(t("common.edit") + f" {t('letter_templates.template')} #{tmpl['id']}")
        dlg.geometry("520x480")
        dlg.grab_set()

        fields = {}
        for label, key, default, widget_type in [
            (t("letter_templates.template_name") + ":", "template_name",
             tmpl.get("template_name", ""), "entry"),
            (t("common.category") + ":", "category",
             tmpl.get("category", "general"), "combo"),
            (t("letter_templates.subject") + ":", "subject_line",
             tmpl.get("subject_line", ""), "entry"),
            (t("letter_templates.merge_fields") + ":", "merge_fields",
             tmpl.get("merge_fields", ""), "entry"),
            (t("letter_templates.body") + ":", "body_template",
             tmpl.get("body_template", ""), "text"),
        ]:
            tk.Label(dlg, text=label).pack(anchor="w", padx=10, pady=(6, 0))
            if widget_type == "entry":
                var = tk.StringVar(value=default)
                tk.Entry(dlg, textvariable=var, width=55).pack(
                    padx=10, fill="x")
                fields[key] = var
            elif widget_type == "combo":
                var = tk.StringVar(value=default)
                ttk.Combobox(dlg, textvariable=var, state="readonly",
                             values=["general", "admissions", "finance",
                                     "academic", "pastoral", "disciplinary",
                                     "hr", "other"],
                             width=20).pack(padx=10, anchor="w")
                fields[key] = var
            elif widget_type == "text":
                txt = tk.Text(dlg, width=55, height=10, wrap="word")
                txt.pack(padx=10, fill="both", expand=True)
                txt.insert("1.0", default)
                fields[key] = txt

        def _save():
            try:
                body = fields["body_template"].get("1.0", "end").strip()
                self._svc.update_template(
                    tid,
                    template_name=fields["template_name"].get(),
                    body_template=body,
                    category=fields["category"].get(),
                    subject_line=fields["subject_line"].get(),
                    merge_fields=fields["merge_fields"].get(),
                )
                dlg.destroy()
                self.refresh()
                messagebox.showinfo(t("common.success"), t("common.updated_success"))
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("common.save"), command=_save).pack(pady=10)

    def _toggle_template(self):
        tid = self._selected_template_id()
        if tid is None:
            return
        try:
            self._svc.toggle_active(tid)
            self._refresh_templates()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _delete_template(self):
        tid = self._selected_template_id()
        if tid is None:
            return
        if not messagebox.askyesno(
                t("common.confirm_delete"),
                t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_template(tid)
            self.refresh()
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ── Letter CRUD dialogs ───────────────────────────────────────────

    def _new_letter(self):
        dlg = tk.Toplevel(self)
        dlg.title(t("letter_templates.generate_letter"))
        dlg.geometry("520x500")
        dlg.grab_set()

        try:
            templates = self._svc.list_templates(active=1)
        except Exception:
            templates = []
        tmpl_map = {f"{tmpl['id']} {tmpl['template_name']}": tmpl for tmpl in templates}

        fields = {}

        tk.Label(dlg, text=t("letter_templates.template") + "*:").pack(anchor="w", padx=10,
                                              pady=(8, 0))
        tmpl_var = tk.StringVar()
        tmpl_cb = ttk.Combobox(dlg, textvariable=tmpl_var,
                               values=list(tmpl_map.keys()),
                               state="readonly", width=40)
        tmpl_cb.pack(padx=10, anchor="w")
        fields["template"] = tmpl_var

        tk.Label(dlg, text=t("letter_templates.recipient") + "*:").pack(anchor="w", padx=10,
                                                    pady=(6, 0))
        rn_var = tk.StringVar()
        tk.Entry(dlg, textvariable=rn_var, width=40).pack(padx=10,
                                                           anchor="w")
        fields["recipient_name"] = rn_var

        tk.Label(dlg, text=t("letter_templates.recipient_type") + ":").pack(anchor="w", padx=10,
                                                   pady=(6, 0))
        rt_var = tk.StringVar(value="student")
        ttk.Combobox(dlg, textvariable=rt_var, state="readonly",
                     values=["student", "parent", "staff", "external"],
                     width=14).pack(padx=10, anchor="w")
        fields["recipient_type"] = rt_var

        tk.Label(dlg, text=t("letter_templates.subject") + ":").pack(anchor="w", padx=10, pady=(6, 0))
        subj_var = tk.StringVar()
        tk.Entry(dlg, textvariable=subj_var, width=40).pack(padx=10,
                                                             anchor="w")
        fields["subject"] = subj_var

        tk.Label(dlg, text=t("letter_templates.sent_via") + ":").pack(anchor="w", padx=10,
                                             pady=(6, 0))
        via_var = tk.StringVar(value="email")
        ttk.Combobox(dlg, textvariable=via_var, state="readonly",
                     values=["email", "post", "hand"],
                     width=10).pack(padx=10, anchor="w")
        fields["sent_via"] = via_var

        tk.Label(dlg, text=t("letter_templates.body") + "*:").pack(anchor="w", padx=10, pady=(6, 0))
        body_txt = tk.Text(dlg, width=55, height=8, wrap="word")
        body_txt.pack(padx=10, fill="both", expand=True)
        fields["body"] = body_txt

        def _on_template_select(_event=None):
            key = tmpl_var.get()
            selected_tmpl = tmpl_map.get(key)
            if selected_tmpl:
                subj_var.set(selected_tmpl.get("subject_line", ""))
                body_txt.delete("1.0", "end")
                body_txt.insert("1.0", selected_tmpl.get("body_template", ""))

        tmpl_cb.bind("<<ComboboxSelected>>", _on_template_select)

        def _save():
            key = tmpl_var.get()
            selected_tmpl = tmpl_map.get(key)
            if not selected_tmpl:
                messagebox.showwarning(t("common.warning"), t("common.select_first"))
                return
            try:
                body = body_txt.get("1.0", "end").strip()
                self._svc.generate_letter(
                    template_id=selected_tmpl["id"],
                    recipient_name=rn_var.get(),
                    body=body,
                    recipient_type=rt_var.get(),
                    subject=subj_var.get(),
                    sent_via=via_var.get(),
                )
                dlg.destroy()
                self.refresh()
                messagebox.showinfo(t("common.success"), t("common.created_success"))
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))

        ttk.Button(dlg, text=t("letter_templates.generate"), command=_save).pack(pady=10)

    def _view_letter(self):
        lid = self._selected_letter_id()
        if lid is None:
            return
        letter = self._svc.get_letter(lid)
        if not letter:
            messagebox.showerror(t("common.error"), t("common.not_found"))
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"{t('letter_templates.letter')} #{letter['id']}")
        dlg.geometry("520x450")
        dlg.grab_set()

        info = (
            f"{t('letter_templates.template')}:     {letter.get('template_name', '')}\n"
            f"{t('letter_templates.recipient')}:    {letter.get('recipient_name', '')}\n"
            f"{t('letter_templates.recipient_type')}:         {letter.get('recipient_type', '')}\n"
            f"{t('letter_templates.subject')}:      {letter.get('subject', '')}\n"
            f"{t('letter_templates.sent_via')}:     {letter.get('sent_via', '')}\n"
            f"{t('common.status')}:       {letter.get('status', '')}\n"
            f"{t('letter_templates.sent_at')}:      {letter.get('sent_at', 'N/A')}\n"
            f"{t('common.created')}:      {letter.get('created_at', '')}\n"
        )
        tk.Label(dlg, text=info, justify="left",
                 font=("Courier", 10)).pack(padx=10, pady=10, anchor="w")

        tk.Label(dlg, text=t("letter_templates.body") + ":").pack(anchor="w", padx=10)
        txt = tk.Text(dlg, wrap="word", height=10, state="normal")
        txt.pack(padx=10, fill="both", expand=True)
        txt.insert("1.0", letter.get("body", ""))
        txt.configure(state="disabled")
        ttk.Button(dlg, text=t("common.close"), command=dlg.destroy).pack(pady=8)

    def _mark_sent(self):
        lid = self._selected_letter_id()
        if lid is None:
            return
        try:
            self._svc.mark_sent(lid)
            self._refresh_letters()
            messagebox.showinfo(t("common.success"), t("letter_templates.letter_sent"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _delete_letter(self):
        lid = self._selected_letter_id()
        if lid is None:
            return
        if not messagebox.askyesno(t("common.confirm_delete"),
                                   t("common.delete_confirm_msg")):
            return
        try:
            self._svc.delete_letter(lid)
            self._refresh_letters()
            messagebox.showinfo(t("common.success"), t("common.deleted_success"))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
