"""Letter Templates GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

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
        tk.Label(header, text="Letter Templates",
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
        self._nb.add(tab, text="Templates")

        # Filter bar
        fbar = tk.Frame(tab, bg="#ecf0f1")
        fbar.pack(fill="x", pady=(0, 5))

        tk.Label(fbar, text="Category:", bg="#ecf0f1").pack(side="left")
        self._tmpl_cat_var = tk.StringVar(value="All")
        cat_cb = ttk.Combobox(fbar, textvariable=self._tmpl_cat_var,
                              values=["All", "general", "admissions",
                                      "finance", "academic", "pastoral",
                                      "disciplinary", "hr", "other"],
                              state="readonly", width=14)
        cat_cb.pack(side="left", padx=(4, 10))
        cat_cb.bind("<<ComboboxSelected>>",
                     lambda _: self._refresh_templates())

        tk.Label(fbar, text="Search:", bg="#ecf0f1").pack(side="left")
        self._tmpl_search_var = tk.StringVar()
        se = tk.Entry(fbar, textvariable=self._tmpl_search_var, width=20)
        se.pack(side="left", padx=4)
        se.bind("<Return>", lambda _: self._refresh_templates())
        ttk.Button(fbar, text="Go",
                   command=self._refresh_templates).pack(side="left")

        # Toolbar
        tb = tk.Frame(tab, bg="#ecf0f1")
        tb.pack(fill="x", pady=(0, 5))
        for txt, cmd in [("New", self._new_template),
                         ("View", self._view_template),
                         ("Edit", self._edit_template),
                         ("Toggle Active", self._toggle_template),
                         ("Delete", self._delete_template)]:
            ttk.Button(tb, text=txt, command=cmd).pack(side="left", padx=2)

        # Treeview
        cols = ("id", "name", "category", "subject", "active", "merge_fields")
        self._tree_tmpl = ttk.Treeview(tab, columns=cols, show="headings",
                                       selectmode="browse")
        for cid, label, w in [("id", "ID", 40),
                              ("name", "Name", 200),
                              ("category", "Category", 100),
                              ("subject", "Subject", 180),
                              ("active", "Active", 60),
                              ("merge_fields", "Merge Fields", 180)]:
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
        self._nb.add(tab, text="Generated Letters")

        # Filter bar
        fbar = tk.Frame(tab, bg="#ecf0f1")
        fbar.pack(fill="x", pady=(0, 5))

        tk.Label(fbar, text="Template:", bg="#ecf0f1").pack(side="left")
        self._let_tmpl_var = tk.StringVar(value="All")
        self._let_tmpl_cb = ttk.Combobox(fbar,
                                         textvariable=self._let_tmpl_var,
                                         state="readonly", width=20)
        self._let_tmpl_cb.pack(side="left", padx=(4, 10))
        self._let_tmpl_cb.bind("<<ComboboxSelected>>",
                               lambda _: self._refresh_letters())

        tk.Label(fbar, text="Status:", bg="#ecf0f1").pack(side="left")
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
        for txt, cmd in [("New", self._new_letter),
                         ("View", self._view_letter),
                         ("Mark Sent", self._mark_sent),
                         ("Delete", self._delete_letter)]:
            ttk.Button(tb, text=txt, command=cmd).pack(side="left", padx=2)

        # Treeview
        cols = ("id", "template", "recipient", "subject", "via", "status",
                "sent_at")
        self._tree_let = ttk.Treeview(tab, columns=cols, show="headings",
                                      selectmode="browse")
        for cid, label, w in [("id", "ID", 40),
                              ("template", "Template", 150),
                              ("recipient", "Recipient", 150),
                              ("subject", "Subject", 160),
                              ("via", "Via", 60),
                              ("status", "Status", 70),
                              ("sent_at", "Sent At", 140)]:
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
        self._nb.add(tab, text="Statistics")
        self._stats_text = tk.Text(tab, wrap="word", font=("Courier", 11),
                                   state="disabled", bg="white")
        self._stats_text.pack(fill="both", expand=True)
        ttk.Button(tab, text="Refresh Stats",
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
            messagebox.showerror("Error", str(e))
            return
        for t in templates:
            self._tree_tmpl.insert("", "end", values=(
                t["id"],
                t.get("template_name", ""),
                t.get("category", ""),
                t.get("subject_line", ""),
                "Yes" if t.get("is_active") else "No",
                t.get("merge_fields", ""),
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
            messagebox.showerror("Error", str(e))
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
            messagebox.showerror("Error", str(e))
            return
        self._stats_text.configure(state="normal")
        self._stats_text.delete("1.0", "end")
        lines = [
            "=== Letter Templates Statistics ===\n",
            f"Total Templates:    {stats['total_templates']}",
            f"  Active:           {stats['active_templates']}",
            f"  Inactive:         {stats['inactive_templates']}",
            "",
            f"Total Letters:      {stats['total_letters']}",
            "",
            "Letters by Status:",
        ]
        for s, c in stats.get("by_status", {}).items():
            lines.append(f"  {s:<16} {c}")
        lines.append("")
        lines.append("Templates by Category:")
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
        vals = ["All"] + [f"{t['id']} {t['template_name']}"
                          for t in templates]
        self._let_tmpl_cb["values"] = vals

    # ── Template helpers ──────────────────────────────────────────────

    def _selected_template_id(self):
        sel = self._tree_tmpl.selection()
        if not sel:
            messagebox.showwarning("Selection",
                                   "Please select a template first.")
            return None
        return self._tree_tmpl.item(sel[0])["values"][0]

    def _selected_letter_id(self):
        sel = self._tree_let.selection()
        if not sel:
            messagebox.showwarning("Selection",
                                   "Please select a letter first.")
            return None
        return self._tree_let.item(sel[0])["values"][0]

    # ── Template CRUD dialogs ─────────────────────────────────────────

    def _new_template(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Template")
        dlg.geometry("520x480")
        dlg.grab_set()

        fields = {}
        for label, key, widget_type in [
            ("Name*:", "template_name", "entry"),
            ("Category:", "category", "combo"),
            ("Subject Line:", "subject_line", "entry"),
            ("Merge Fields:", "merge_fields", "entry"),
            ("Body*:", "body_template", "text"),
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
                messagebox.showinfo("Success", "Template created.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(dlg, text="Save", command=_save).pack(pady=10)

    def _view_template(self):
        tid = self._selected_template_id()
        if tid is None:
            return
        tmpl = self._svc.get_template(tid)
        if not tmpl:
            messagebox.showerror("Error", "Template not found.")
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Template #{tmpl['id']}")
        dlg.geometry("520x450")
        dlg.grab_set()

        info = (
            f"Name:         {tmpl.get('template_name', '')}\n"
            f"Category:     {tmpl.get('category', '')}\n"
            f"Subject:      {tmpl.get('subject_line', '')}\n"
            f"Active:       {'Yes' if tmpl.get('is_active') else 'No'}\n"
            f"Merge Fields: {tmpl.get('merge_fields', '')}\n"
            f"Created:      {tmpl.get('created_at', '')}\n"
            f"Updated:      {tmpl.get('updated_at', '')}\n"
        )
        tk.Label(dlg, text=info, justify="left",
                 font=("Courier", 10)).pack(padx=10, pady=10, anchor="w")

        tk.Label(dlg, text="Body:").pack(anchor="w", padx=10)
        txt = tk.Text(dlg, wrap="word", height=12, state="normal")
        txt.pack(padx=10, fill="both", expand=True)
        txt.insert("1.0", tmpl.get("body_template", ""))
        txt.configure(state="disabled")
        ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=8)

    def _edit_template(self):
        tid = self._selected_template_id()
        if tid is None:
            return
        tmpl = self._svc.get_template(tid)
        if not tmpl:
            messagebox.showerror("Error", "Template not found.")
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Edit Template #{tmpl['id']}")
        dlg.geometry("520x480")
        dlg.grab_set()

        fields = {}
        for label, key, default, widget_type in [
            ("Name:", "template_name", tmpl.get("template_name", ""), "entry"),
            ("Category:", "category", tmpl.get("category", "general"),
             "combo"),
            ("Subject Line:", "subject_line",
             tmpl.get("subject_line", ""), "entry"),
            ("Merge Fields:", "merge_fields",
             tmpl.get("merge_fields", ""), "entry"),
            ("Body:", "body_template",
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
                messagebox.showinfo("Success", "Template updated.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(dlg, text="Save", command=_save).pack(pady=10)

    def _toggle_template(self):
        tid = self._selected_template_id()
        if tid is None:
            return
        try:
            self._svc.toggle_active(tid)
            self._refresh_templates()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _delete_template(self):
        tid = self._selected_template_id()
        if tid is None:
            return
        if not messagebox.askyesno(
                "Confirm",
                "Delete this template and all its generated letters?"):
            return
        try:
            self._svc.delete_template(tid)
            self.refresh()
            messagebox.showinfo("Deleted", "Template deleted.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ── Letter CRUD dialogs ───────────────────────────────────────────

    def _new_letter(self):
        dlg = tk.Toplevel(self)
        dlg.title("Generate Letter")
        dlg.geometry("520x500")
        dlg.grab_set()

        try:
            templates = self._svc.list_templates(active=1)
        except Exception:
            templates = []
        tmpl_map = {f"{t['id']} {t['template_name']}": t for t in templates}

        fields = {}

        tk.Label(dlg, text="Template*:").pack(anchor="w", padx=10,
                                              pady=(8, 0))
        tmpl_var = tk.StringVar()
        tmpl_cb = ttk.Combobox(dlg, textvariable=tmpl_var,
                               values=list(tmpl_map.keys()),
                               state="readonly", width=40)
        tmpl_cb.pack(padx=10, anchor="w")
        fields["template"] = tmpl_var

        tk.Label(dlg, text="Recipient Name*:").pack(anchor="w", padx=10,
                                                    pady=(6, 0))
        rn_var = tk.StringVar()
        tk.Entry(dlg, textvariable=rn_var, width=40).pack(padx=10,
                                                           anchor="w")
        fields["recipient_name"] = rn_var

        tk.Label(dlg, text="Recipient Type:").pack(anchor="w", padx=10,
                                                   pady=(6, 0))
        rt_var = tk.StringVar(value="student")
        ttk.Combobox(dlg, textvariable=rt_var, state="readonly",
                     values=["student", "parent", "staff", "external"],
                     width=14).pack(padx=10, anchor="w")
        fields["recipient_type"] = rt_var

        tk.Label(dlg, text="Subject:").pack(anchor="w", padx=10, pady=(6, 0))
        subj_var = tk.StringVar()
        tk.Entry(dlg, textvariable=subj_var, width=40).pack(padx=10,
                                                             anchor="w")
        fields["subject"] = subj_var

        tk.Label(dlg, text="Sent Via:").pack(anchor="w", padx=10,
                                             pady=(6, 0))
        via_var = tk.StringVar(value="email")
        ttk.Combobox(dlg, textvariable=via_var, state="readonly",
                     values=["email", "post", "hand"],
                     width=10).pack(padx=10, anchor="w")
        fields["sent_via"] = via_var

        tk.Label(dlg, text="Body*:").pack(anchor="w", padx=10, pady=(6, 0))
        body_txt = tk.Text(dlg, width=55, height=8, wrap="word")
        body_txt.pack(padx=10, fill="both", expand=True)
        fields["body"] = body_txt

        def _on_template_select(_event=None):
            key = tmpl_var.get()
            tmpl = tmpl_map.get(key)
            if tmpl:
                subj_var.set(tmpl.get("subject_line", ""))
                body_txt.delete("1.0", "end")
                body_txt.insert("1.0", tmpl.get("body_template", ""))

        tmpl_cb.bind("<<ComboboxSelected>>", _on_template_select)

        def _save():
            key = tmpl_var.get()
            tmpl = tmpl_map.get(key)
            if not tmpl:
                messagebox.showwarning("Warning", "Select a template.")
                return
            try:
                body = body_txt.get("1.0", "end").strip()
                self._svc.generate_letter(
                    template_id=tmpl["id"],
                    recipient_name=rn_var.get(),
                    body=body,
                    recipient_type=rt_var.get(),
                    subject=subj_var.get(),
                    sent_via=via_var.get(),
                )
                dlg.destroy()
                self.refresh()
                messagebox.showinfo("Success", "Letter generated.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(dlg, text="Generate", command=_save).pack(pady=10)

    def _view_letter(self):
        lid = self._selected_letter_id()
        if lid is None:
            return
        letter = self._svc.get_letter(lid)
        if not letter:
            messagebox.showerror("Error", "Letter not found.")
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Letter #{letter['id']}")
        dlg.geometry("520x450")
        dlg.grab_set()

        info = (
            f"Template:     {letter.get('template_name', '')}\n"
            f"Recipient:    {letter.get('recipient_name', '')}\n"
            f"Type:         {letter.get('recipient_type', '')}\n"
            f"Subject:      {letter.get('subject', '')}\n"
            f"Sent Via:     {letter.get('sent_via', '')}\n"
            f"Status:       {letter.get('status', '')}\n"
            f"Sent At:      {letter.get('sent_at', 'N/A')}\n"
            f"Created:      {letter.get('created_at', '')}\n"
        )
        tk.Label(dlg, text=info, justify="left",
                 font=("Courier", 10)).pack(padx=10, pady=10, anchor="w")

        tk.Label(dlg, text="Body:").pack(anchor="w", padx=10)
        txt = tk.Text(dlg, wrap="word", height=10, state="normal")
        txt.pack(padx=10, fill="both", expand=True)
        txt.insert("1.0", letter.get("body", ""))
        txt.configure(state="disabled")
        ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=8)

    def _mark_sent(self):
        lid = self._selected_letter_id()
        if lid is None:
            return
        try:
            self._svc.mark_sent(lid)
            self._refresh_letters()
            messagebox.showinfo("Success", "Letter marked as sent.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _delete_letter(self):
        lid = self._selected_letter_id()
        if lid is None:
            return
        if not messagebox.askyesno("Confirm",
                                   "Delete this generated letter?"):
            return
        try:
            self._svc.delete_letter(lid)
            self._refresh_letters()
            messagebox.showinfo("Deleted", "Letter deleted.")
        except Exception as e:
            messagebox.showerror("Error", str(e))
