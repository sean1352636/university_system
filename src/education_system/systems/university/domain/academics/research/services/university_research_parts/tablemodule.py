"""Extracted class implementation."""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class TableModule(ModuleTab):
    """
    Reusable module with:
      * title + New/Edit/Delete/Refresh buttons
      * search box
      * treeview listing
      * detail pane showing the selected record
    Subclasses define columns, query, field specs, and detail rendering.
    """

    title = ""
    subtitle = ""
    table_name = ""
    pk = "id"

    def _build(self):
        wrapper = ttk.Frame(self, style="TFrame")
        wrapper.pack(fill="both", expand=True, padx=24, pady=20)

        # Title row
        top = ttk.Frame(wrapper, style="TFrame")
        top.pack(fill="x")
        ttk.Label(top, text=self.title, font=("Segoe UI", 18, "bold"),
                  foreground=PALETTE["header"]).pack(anchor="w")
        ttk.Label(top, text=self.subtitle,
                  foreground=PALETTE["muted"]).pack(anchor="w")

        # Actions
        actions = ttk.Frame(wrapper, style="TFrame")
        actions.pack(fill="x", pady=(14, 8))

        ttk.Button(actions, text="+ New", style="Accent.TButton",
                   command=self.on_new).pack(side="left")
        ttk.Button(actions, text="Edit", command=self.on_edit).pack(side="left",
                                                                    padx=6)
        ttk.Button(actions, text="Delete", command=self.on_delete).pack(
            side="left")
        ttk.Button(actions, text="Refresh", command=self.refresh).pack(
            side="left", padx=6)

        ttk.Label(actions, text="Search:",
                  foreground=PALETTE["muted"]).pack(side="left", padx=(20, 6))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh())
        ttk.Entry(actions, textvariable=self.search_var, width=30).pack(
            side="left")

        # Split area: table | detail
        split = ttk.Frame(wrapper, style="TFrame")
        split.pack(fill="both", expand=True)
        split.columnconfigure(0, weight=3)
        split.columnconfigure(1, weight=2)
        split.rowconfigure(0, weight=1)

        # Table area
        table_frame = ttk.Frame(split, style="Panel.TFrame")
        table_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        cols, heads, widths = self.get_columns()
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings",
                                 selectmode="browse")
        for c, h, w in zip(cols, heads, widths):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True, padx=1, pady=1)

        sb = ttk.Scrollbar(table_frame, orient="vertical",
                           command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.config(yscrollcommand=sb.set)

        self.tree.bind("<<TreeviewSelect>>", lambda e: self.on_select())
        self.tree.bind("<Double-1>", lambda e: self.on_edit())

        self.tree.tag_configure("alt", background="#fafbfd")

        # Detail panel
        detail_frame = ttk.Frame(split, style="Panel.TFrame")
        detail_frame.grid(row=0, column=1, sticky="nsew")
        detail_inner = ttk.Frame(detail_frame, style="Panel.TFrame")
        detail_inner.pack(fill="both", expand=True, padx=18, pady=16)
        ttk.Label(detail_inner, text="Details",
                  style="SectionTitle.TLabel").pack(anchor="w")
        ttk.Separator(detail_inner).pack(fill="x", pady=(6, 10))

        self.detail_text = tk.Text(detail_inner, height=20, wrap="word",
                                   font=("Segoe UI", 10),
                                   relief="flat", bg=PALETTE["panel"],
                                   fg=PALETTE["text"])
        self.detail_text.pack(fill="both", expand=True)
        self.detail_text.configure(state="disabled")
        self.detail_text.tag_configure("label",
                                       font=("Segoe UI", 10, "bold"),
                                       foreground=PALETTE["header"])
        self.detail_text.tag_configure("value", foreground=PALETTE["text"])
        self.detail_text.tag_configure("muted", foreground=PALETTE["muted"])
        self.detail_text.tag_configure("section",
                                       font=("Segoe UI", 11, "bold"),
                                       foreground=PALETTE["header"])

    # ---- methods subclasses override ---------------------------------------
    def get_columns(self):
        raise NotImplementedError

    def fetch_rows(self, search):
        raise NotImplementedError

    def row_to_tree_values(self, row):
        raise NotImplementedError

    def get_field_specs(self, record=None):
        raise NotImplementedError

    def build_record_from_row(self, row):
        return dict(row)

    def render_detail(self, row):
        raise NotImplementedError

    def insert_sql(self, data):
        raise NotImplementedError

    def update_sql(self, data, pk):
        raise NotImplementedError

    # ---- common behaviour --------------------------------------------------
    def refresh(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        rows = self.fetch_rows(self.search_var.get())
        for i, r in enumerate(rows):
            tag = ("alt",) if i % 2 else ()
            self.tree.insert("", "end", iid=str(r[self.pk]),
                             values=self.row_to_tree_values(r), tags=tag)
        self._clear_detail()

    def _clear_detail(self):
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0",
                                "Select a row to view full details.",
                                ("muted",))
        self.detail_text.configure(state="disabled")

    def on_select(self):
        sel = self.tree.selection()
        if not sel:
            return
        pk_val = int(sel[0])
        row = self.db.query(
            f"SELECT * FROM {self.table_name} WHERE {self.pk}=?",
            (pk_val,))
        if not row:
            return
        row = self.build_record_from_row(row[0])
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.render_detail(row)
        self.detail_text.configure(state="disabled")

    def _write_detail(self, pairs):
        for label, value, *rest in pairs:
            tag = rest[0] if rest else "value"
            self.detail_text.insert("end", f"{label}\n", ("label",))
            self.detail_text.insert("end", f"{value or '—'}\n\n", (tag,))

    def on_new(self):
        fields = self.get_field_specs()
        dlg = RecordDialog(self.app.root, f"New — {self.title}", fields)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self.insert_sql(dlg.result)
                self.refresh()
                self.app.dashboard.refresh()
            except Exception as e:
                messagebox.showerror("Save failed", str(e), parent=self)

    def on_edit(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No selection",
                                "Select a record to edit.", parent=self)
            return
        pk_val = int(sel[0])
        row = self.db.query(
            f"SELECT * FROM {self.table_name} WHERE {self.pk}=?",
            (pk_val,))
        if not row:
            return
        record = self.build_record_from_row(row[0])
        fields = self.get_field_specs(record)
        dlg = RecordDialog(self.app.root, f"Edit — {self.title}",
                           fields, record=record)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self.update_sql(dlg.result, pk_val)
                self.refresh()
                self.tree.selection_set(str(pk_val))
                self.app.dashboard.refresh()
            except Exception as e:
                messagebox.showerror("Save failed", str(e), parent=self)

    def on_delete(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No selection",
                                "Select a record to delete.", parent=self)
            return
        pk_val = int(sel[0])
        if not messagebox.askyesno("Confirm delete",
                                   "Delete the selected record? This cannot be undone.",
                                   parent=self):
            return
        self.db.execute(
            f"DELETE FROM {self.table_name} WHERE {self.pk}=?", (pk_val,))
        self.refresh()
        self.app.dashboard.refresh()
