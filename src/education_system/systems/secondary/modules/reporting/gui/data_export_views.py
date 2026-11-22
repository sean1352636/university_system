"""Data Export screen.

Kept from the old Custom Export window (first tab, "Custom Export"): the
dataset list (Key, Label), the Columns checklist with Select all / Clear,
the Filters, Format, "Row limit (blank=all)", Preview, Render (the whole
export as text in the output pane) and Export to file. Kept from the old
Data Export window: Run Export (a pack of datasets, Format, "Zip when done",
Output folder with Browse…, Run export, output pane), Presets (now "Saved
exports", each person's own: Run…, Load, Delete, Refresh), Past Jobs (now
"Past exports": View, Delete, Refresh) and Overview.

New: per-person saved exports from the current choices (Save as…), the
data manager's view of everyone's exports, and the rules on sensitive
datasets and columns (other staff see only what they may export). The
rules are in :mod:`modules.reporting.domain.data_export`.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.reporting.domain import data_export as DX
from education_system.systems.secondary.modules.reporting.gui import report_widgets as RW
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W


class DataExportPage:
    TABS = ("Custom Export", "Saved exports", "Run Export", "Past exports", "Overview")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.manager = DX.can_export_all(principal)
        activity_log.record("data_export.view")
        ttk.Label(parent, text="Data Export", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(parent, foreground="#666", text=(
            "You can export every dataset." if self.manager else
            "You can export non-sensitive data for the groups you teach and the forms you "
            "tutor.")).pack(anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n in self.TABS:
            self.book.add(self.tabs[n], text=n)
        self._built: set[str] = set()
        start = state.get("tab") if state.get("tab") in self.TABS else self.TABS[0]
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, W.problems(e), parent=self._top())

    def _on_tab(self, _e=None) -> None:
        name = self.TABS[self.book.index(self.book.select())]
        self.state["tab"] = name
        build, refresh = {"Custom Export": (self._build_custom, lambda: None),
                          "Saved exports": (self._build_saved, self.refresh_saved),
                          "Run Export": (self._build_pack, lambda: None),
                          "Past exports": (self._build_log, self.refresh_log),
                          "Overview": (self._build_overview, self.refresh_overview)}[name]
        if name not in self._built:
            self._built.add(name)
            build(self.tabs[name])
        refresh()

    # ── Custom Export ────────────────────────────────────────────────

    def _build_custom(self, tab) -> None:
        body = ttk.Frame(tab)
        body.pack(fill="both", expand=True)
        left = ttk.LabelFrame(body, text="Datasets", padding=4)
        left.pack(side="left", fill="y")
        self.ds_tree = W.tree(left, [("key", "Key", 90), ("label", "Label", 190)], height=14)
        self.datasets = DX.datasets_for(self.principal)
        for d in self.datasets:
            self.ds_tree.insert("", "end", iid=d.key, values=(d.key, d.label))
        self.ds_tree.bind("<<TreeviewSelect>>", lambda _e: self._pick_dataset())
        mid = ttk.LabelFrame(body, text="Columns", padding=4)
        mid.pack(side="left", fill="y", padx=6)
        cbar = ttk.Frame(mid)
        cbar.pack(fill="x")
        ttk.Button(cbar, text="Select all", command=lambda: self._all(True)).pack(side="left")
        ttk.Button(cbar, text="Clear", command=lambda: self._all(False)).pack(side="left",
                                                                            padx=4)
        self.col_list = tk.Listbox(mid, selectmode="multiple", height=16, width=26,
                                   exportselection=False)
        self.col_list.pack(fill="y", expand=True, pady=(4, 0))
        self.col_keys: list[str] = []
        right = ttk.LabelFrame(body, text="Filters", padding=6)
        right.pack(side="left", fill="both", expand=True)
        self.fvars: dict[str, tk.StringVar] = {}
        saved = self.state.get("filters", {})
        for i, (k, label) in enumerate(DX.FILTERS.items()):
            ttk.Label(right, text=label + ":").grid(row=i, column=0, sticky="w", pady=2)
            v = tk.StringVar(value=saved.get(k, ""))
            if k == "year_group":
                ttk.Combobox(right, textvariable=v, values=RW.YEARS, state="readonly",
                             width=6).grid(row=i, column=1, sticky="w")
            else:
                ttk.Entry(right, textvariable=v, width=14).grid(row=i, column=1, sticky="w")
            self.fvars[k] = v
        ttk.Label(right, text="Blank means no filter. Dates: YYYY-MM-DD.",
                  foreground="#777").grid(row=9, column=0, columnspan=2, sticky="w",
                                          pady=(4, 8))
        ttk.Label(right, text="Format:").grid(row=10, column=0, sticky="w")
        self.fmt = tk.StringVar(value=self.state.get("fmt", DX.DEFAULT_FORMAT))
        ttk.Combobox(right, textvariable=self.fmt, values=list(DX.FORMATS), state="readonly",
                     width=10).grid(row=10, column=1, sticky="w")
        ttk.Label(right, text="Row limit (blank=all):").grid(row=11, column=0, sticky="w")
        self.limit = tk.StringVar(value=self.state.get("limit", ""))
        ttk.Entry(right, textvariable=self.limit, width=8).grid(row=11, column=1, sticky="w")
        btns = ttk.Frame(tab)
        btns.pack(fill="x", pady=6)
        for text, cmd in (("Preview", self.preview), ("Render", self.render),
                          ("Export to file…", self.export), ("Save as…", self.save_as)):
            ttk.Button(btns, text=text, command=cmd).pack(side="left", padx=2)
        self.out_var = tk.StringVar()
        ttk.Label(btns, textvariable=self.out_var, foreground="#555").pack(side="left", padx=8)
        out = ttk.LabelFrame(tab, text="Preview / output", padding=4)
        out.pack(fill="both", expand=True)
        self.preview_box = RW.TableBox(out, height=10)
        key = self.state.get("dataset")
        if key and self.ds_tree.exists(key):
            self.ds_tree.selection_set(key)
            self.ds_tree.see(key)

    def _pick_dataset(self, chosen: list[str] | None = None) -> None:
        sel = self.ds_tree.selection()
        if not sel:
            return
        self.state["dataset"] = sel[0]
        cols = DX.columns_for(self.principal, sel[0])
        self.col_keys = [c.key for c in cols]
        self.col_list.delete(0, "end")
        want = chosen if chosen is not None else self.state.get("columns", {}).get(sel[0])
        for i, c in enumerate(cols):
            self.col_list.insert("end", c.heading + ("  (sensitive)" if c.sensitive else ""))
            if want is None or c.key in want:
                self.col_list.selection_set(i)

    def _all(self, on: bool) -> None:
        if on:
            self.col_list.selection_set(0, "end")
        else:
            self.col_list.selection_clear(0, "end")

    def _choices(self) -> tuple[str, list[str], dict[str, str], int | None] | None:
        sel = self.ds_tree.selection()
        if not sel:
            messagebox.showinfo("Data Export", "Choose a dataset first.", parent=self._top())
            return None
        cols = [self.col_keys[i] for i in self.col_list.curselection()]
        self.state.setdefault("columns", {})[sel[0]] = cols
        filters = {k: v.get().strip() for k, v in self.fvars.items()}
        self.state["filters"] = filters
        self.state["fmt"], self.state["limit"] = self.fmt.get(), self.limit.get().strip()
        limit = self.limit.get().strip()
        if limit and not limit.isdigit():
            messagebox.showerror("Data Export", "Row limit must be a whole number.",
                                 parent=self._top())
            return None
        return sel[0], cols, filters, int(limit) if limit else None

    def preview(self) -> None:
        ch = self._choices()
        if ch is None:
            return
        key, cols, filters, _limit = ch

        def done(pv: dict[str, Any]) -> None:
            self.preview_box.show([c.heading for c in pv["columns"]], pv["rows"])
            self.out_var.set(f"{pv['total']} row(s) ({pv['scope']}); showing the first "
                             f"{len(pv['rows'])}.")

        RW.run_in_background(self.parent, lambda: DX.preview(self.principal, key, cols,
                                                             filters),
                             done, lambda e: self._err("Preview", e))

    def render(self) -> None:
        ch = self._choices()
        if ch is None:
            return
        key, cols, filters, limit = ch
        try:
            c, rows, _scope = DX.rows(self.principal, key, cols, filters, limit)
            text = DX.render(c, rows, self.fmt.get())
        except W.ERRORS as e:
            self._err("Render", e)
            return
        W.text_window(self.parent, f"{key} ({self.fmt.get()})", text, size="900x520")

    def export(self) -> None:
        ch = self._choices()
        if ch is None:
            return
        key, cols, filters, limit = ch
        fmt = self.fmt.get()
        path = filedialog.asksaveasfilename(parent=self._top(),
                                            defaultextension=DX.FORMATS[fmt],
                                            initialfile=f"{key}{DX.FORMATS[fmt]}")
        if not path:
            return
        try:
            n = DX.export(self.principal, key, path, columns=cols, filters=filters, fmt=fmt,
                          limit=limit)
        except (*W.ERRORS, OSError) as e:
            self._err("Export", e)
            return
        self.out_var.set(f"Exported {n} row(s).")
        messagebox.showinfo("Export", f"Exported {n} row(s).", parent=self._top())

    def save_as(self) -> None:
        ch = self._choices()
        if ch is None:
            return
        key, cols, filters, limit = ch
        W.form_dialog(self.parent, "Save export",
                      [("name", "Name", "", None), ("description", "Description", "", None)],
                      lambda d: (DX.save_definition(self.principal, {
                          **d, "dataset": key, "columns": cols, "filters": filters,
                          "fmt": self.fmt.get(), "row_limit": limit}),
                          self.refresh_saved()))

    # ── Saved exports ────────────────────────────────────────────────

    def _build_saved(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        for text, cmd in (("Run…", self.run_saved), ("Load", self.load_saved),
                          ("Delete", self.delete_saved), ("Refresh", self.refresh_saved)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        self.saved_tree = W.tree(tab, [("id", "#", 40), ("name", "Name", 180),
                                       ("ds", "Dataset", 140), ("cols", "Columns", 70),
                                       ("filters", "Filters", 200), ("fmt", "Format", 70),
                                       ("limit", "Limit", 50), ("desc", "Description", 220),
                                       ("upd", "Updated", 130)], stretch={"desc"})
        self.saved_tree.bind("<Double-1>", lambda _e: self.run_saved())

    def refresh_saved(self) -> None:
        if "Saved exports" not in self._built:
            return
        t = self.saved_tree
        t.delete(*t.get_children())
        for d in DX.list_definitions(self.principal):
            t.insert("", "end", iid=str(d.definition_id), values=(
                d.definition_id, d.name, DX.DATASETS[d.dataset].label if d.dataset in
                DX.DATASETS else d.dataset, len(d.columns),
                ", ".join(f"{k}={v}" for k, v in d.filters.items()), d.fmt,
                d.row_limit if d.row_limit is not None else "", d.description or "",
                d.updated_at))

    def _saved(self) -> DX.Definition | None:
        sel = self.saved_tree.selection()
        if not sel:
            messagebox.showinfo("Saved exports", "Select a saved export.", parent=self._top())
            return None
        try:
            return DX.get_definition(self.principal, int(sel[0]))
        except W.ERRORS as e:
            self._err("Saved exports", e)
            return None

    def run_saved(self) -> None:
        d = self._saved()
        if d is None:
            return
        path = filedialog.asksaveasfilename(parent=self._top(),
                                            defaultextension=DX.FORMATS[d.fmt],
                                            initialfile=DX.safe_file_name(d.name)
                                            + DX.FORMATS[d.fmt])
        if not path:
            return
        try:
            n = DX.run_definition(self.principal, d.definition_id, path)
        except (*W.ERRORS, OSError) as e:
            self._err("Run export", e)
            return
        messagebox.showinfo("Run export", f"Exported {n} row(s).", parent=self._top())

    def load_saved(self) -> None:
        d = self._saved()
        if d is None:
            return
        self.book.select(self.TABS.index("Custom Export"))
        if not self.ds_tree.exists(d.dataset):
            return
        for k, v in self.fvars.items():
            v.set(str(d.filters.get(k, "")))
        self.fmt.set(d.fmt)
        self.limit.set("" if d.row_limit is None else str(d.row_limit))
        self.ds_tree.selection_set(d.dataset)
        self.ds_tree.update_idletasks()
        self._pick_dataset(d.columns)

    def delete_saved(self) -> None:
        d = self._saved()
        if d is None or not messagebox.askyesno("Delete", f"Delete saved export '{d.name}'?",
                                                parent=self._top()):
            return
        DX.delete_definition(self.principal, d.definition_id)
        self.refresh_saved()

    # ── Run Export (packs) ───────────────────────────────────────────

    def _build_pack(self, tab) -> None:
        row = ttk.Frame(tab)
        row.pack(fill="x")
        ttk.Label(row, text="Pack:").pack(side="left")
        names = {f"{label} ({key})": key for key, (label, _ds) in DX.PACKS.items()}
        self.pack_names = names
        self.pack = tk.StringVar(value=next(iter(names)))
        cb = ttk.Combobox(row, textvariable=self.pack, values=list(names), state="readonly",
                          width=30)
        cb.pack(side="left", padx=(2, 8))
        cb.bind("<<ComboboxSelected>>", lambda _e: self._pack_detail())
        ttk.Label(row, text="Format:").pack(side="left")
        self.pack_fmt = tk.StringVar(value=DX.DEFAULT_FORMAT)
        ttk.Combobox(row, textvariable=self.pack_fmt, values=list(DX.FORMATS),
                     state="readonly", width=9).pack(side="left", padx=(2, 8))
        self.zip = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, text="Zip when done", variable=self.zip).pack(side="left")
        row2 = ttk.Frame(tab)
        row2.pack(fill="x", pady=6)
        ttk.Label(row2, text="Output folder:").pack(side="left")
        self.folder = tk.StringVar(value=self.state.get("folder", ""))
        ttk.Entry(row2, textvariable=self.folder, width=50).pack(side="left", padx=4)
        ttk.Button(row2, text="Browse…", command=self._browse).pack(side="left", padx=2)
        ttk.Button(row2, text="Run export", command=self.run_pack).pack(side="left", padx=6)
        ttk.Label(tab, text="Uses the filters on the Custom Export tab (if any).",
                  foreground="#777").pack(anchor="w")
        self.pack_text = tk.Text(tab, height=16, wrap="word", font=("TkFixedFont", 10))
        self.pack_text.pack(fill="both", expand=True, pady=(6, 0))
        self.pack_status = tk.StringVar(value="Ready.")
        ttk.Label(tab, textvariable=self.pack_status, foreground="#555").pack(anchor="w")
        self._pack_detail()

    def _set_pack_text(self, text: str) -> None:
        self.pack_text.configure(state="normal")
        self.pack_text.delete("1.0", "end")
        self.pack_text.insert("1.0", text)
        self.pack_text.configure(state="disabled")

    def _pack_detail(self) -> None:
        key = self.pack_names[self.pack.get()]
        label, ds = DX.PACKS[key]
        allowed = {d.key for d in DX.datasets_for(self.principal)}
        self._set_pack_text(f"Preset detail - {label}\n\n" + "\n".join(
            f"  {DX.DATASETS[k].label}" + ("" if k in allowed else "  (not for your account)")
            for k in ds))

    def _browse(self) -> None:
        d = filedialog.askdirectory(parent=self._top(), title="Output folder")
        if d:
            self.folder.set(d)

    def run_pack(self) -> None:
        folder = self.folder.get().strip()
        if not folder:
            messagebox.showinfo("Run export", "Choose an output folder.", parent=self._top())
            return
        self.state["folder"] = folder
        key = self.pack_names[self.pack.get()]
        fmt, zip_ = self.pack_fmt.get(), self.zip.get()
        filters = ({k: v.get().strip() for k, v in self.fvars.items()}
                   if hasattr(self, "fvars") else {})
        self.pack_status.set("Running…")

        def done(out: dict[str, Any]) -> None:
            self.pack_status.set(f"Done: {len(out['files'])} file(s), {out['rows_total']} "
                                 "row(s).")
            lines = [f"Output: {out['folder']}"] + \
                [f"  {f['file']:<24} {f['rows']:>6} rows  {f['bytes']:>8} bytes"
                 for f in out["files"]]
            lines += [f"  refused: {r['dataset']} - {r['why']}" for r in out["refused"]]
            if out["archive"]:
                lines.append(f"Zipped to {out['archive']}")
            self._set_pack_text("\n".join(lines))

        def failed(e: Exception) -> None:
            self.pack_status.set("Failed.")
            self._err("Run export", e)

        RW.run_in_background(self.parent, lambda: DX.run_pack(
            self.principal, key, folder, fmt=fmt, filters=filters, zip_output=zip_),
            done, failed, name="secondary-data-export")

    # ── Past exports ─────────────────────────────────────────────────

    def _build_log(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.everyone = tk.BooleanVar(value=self.manager)
        cb = ttk.Checkbutton(bar, text="Everyone's", variable=self.everyone,
                             command=self.refresh_log)
        if not self.manager:
            cb.state(["disabled"])
        cb.pack(side="left")
        for text, cmd, lead in (("View", self.view_log, False), ("Delete", self.delete_log, True),
                                ("Refresh", self.refresh_log, False)):
            b = ttk.Button(bar, text=text, command=cmd)
            if lead and not self.manager:
                b.state(["disabled"])
            b.pack(side="left", padx=2)
        self.log_tree = W.tree(tab, [("id", "#", 40), ("at", "When", 130), ("who", "Who", 90),
                                     ("ds", "Dataset", 110), ("cols", "Columns", 60),
                                     ("filters", "Filters", 150), ("fmt", "Format", 60),
                                     ("rows", "Rows", 60), ("scope", "Scope", 90),
                                     ("pack", "Pack", 90), ("file", "File", 140),
                                     ("status", "Status", 60)], stretch={"file"},
                               tags=W.STANDARD_TAGS)
        self.log_rows: dict[str, dict[str, Any]] = {}

    def refresh_log(self) -> None:
        if "Past exports" not in self._built:
            return
        self.log_tree.delete(*self.log_tree.get_children())
        self.log_rows = {}
        for r in DX.history(self.principal, everyone=self.everyone.get()):
            self.log_rows[str(r["log_id"])] = r
            self.log_tree.insert("", "end", iid=str(r["log_id"]),
                                 tags=("bad",) if r["status"] != "ok" else (),
                                 values=(r["log_id"], r["at"], r["actor"], r["dataset"],
                                         r["columns"], r["filters"], r["fmt"] or "",
                                         r["row_count"], r["scope"] or "", r["pack"] or "",
                                         r["file_name"] or "", r["status"]))

    def view_log(self) -> None:
        sel = self.log_tree.selection()
        if not sel:
            return
        r = self.log_rows[sel[0]]
        W.text_window(self.parent, f"Export #{r['log_id']}",
                      "\n".join(f"{k:<10} {v}" for k, v in r.items()), size="520x360")

    def delete_log(self) -> None:
        sel = self.log_tree.selection()
        if not sel or not messagebox.askyesno("Delete", "Delete this export record?",
                                              parent=self._top()):
            return
        try:
            DX.delete_log_entry(self.principal, int(sel[0]))
        except W.ERRORS as e:
            self._err("Delete", e)
            return
        self.refresh_log()

    # ── Overview ─────────────────────────────────────────────────────

    def _build_overview(self, tab) -> None:
        ttk.Button(tab, text="Refresh", command=self.refresh_overview).pack(anchor="w")
        self.ov_text = tk.Text(tab, height=14, wrap="word", font=("TkFixedFont", 10))
        self.ov_text.pack(fill="both", expand=True, pady=(6, 0))

    def refresh_overview(self) -> None:
        if "Overview" not in self._built:
            return
        o = DX.overview(self.principal)
        text = "\n".join([
            "Everyone's exports" if self.manager else "Your exports", "",
            f"Total exports:      {o['exports']}", f"Succeeded:          {o['succeeded']}",
            f"Failed:             {o['failed']}", f"Rows written:       {o['rows']}",
            f"Datasets exported:  {o['datasets']}", f"Built-in packs:     {o['packs']}",
            f"Your saved exports: {o['saved']}", f"Last export:        {o['last'] or '-'}"])
        self.ov_text.configure(state="normal")
        self.ov_text.delete("1.0", "end")
        self.ov_text.insert("1.0", text)
        self.ov_text.configure(state="disabled")


def draw_data_export(parent: ttk.Frame, *, principal: Principal, state: dict
                     ) -> DataExportPage:
    return DataExportPage(parent, principal=principal, state=state)
