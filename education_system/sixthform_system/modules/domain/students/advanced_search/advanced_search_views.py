"""Tkinter views for Sixth Form Advanced Search.

Single window with three tabs:
* Search          — query bar + scope checkboxes + results treeview
                    grouped by scope.
* Saved Searches  — list / run / new / edit / delete saved queries.
* History         — recent runs with re-run / clear.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.shared import branding
from education_system.sixthform_system.modules.domain.students.advanced_search import (
    advanced_search as data,
)
from education_system.sixthform_system.modules.domain.students.advanced_search.advanced_search import (
    ALL_SCOPES,
    DEFAULT_LIMIT_PER_SCOPE,
    Hit,
    QUERY_SYNTAX_HELP,
    QueryOptions,
    SavedSearch,
    SCOPE_LABELS,
    SearchResults,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_advanced_search_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Advanced Search — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    search_tab = SearchTab(nb)
    SavedTab(nb, search_tab)
    HistoryTab(nb, search_tab)
    ToolsTab(nb)


# ══ Search tab ═════════════════════════════════════════════════════

class SearchTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Search")
        self._scope_vars: dict[str, tk.BooleanVar] = {}
        self._build()

    def _build(self) -> None:
        # Query row
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Query:").pack(side="left")
        self.query_e = ttk.Entry(bar, width=44)
        self.query_e.pack(side="left", padx=(4, 8), fill="x", expand=True)
        self.query_e.bind("<Return>", lambda _e: self.run())
        self.query_e.bind("<KeyRelease>", self._on_query_key)
        ttk.Label(bar, text="Limit/scope:").pack(side="left")
        self.limit_e = ttk.Entry(bar, width=6)
        self.limit_e.insert(0, str(DEFAULT_LIMIT_PER_SCOPE))
        self.limit_e.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Search",
                    command=self.run).pack(side="left")
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left", padx=(4, 0))
        ttk.Button(bar, text="Syntax…",
                    command=self._show_syntax).pack(side="left", padx=(4, 0))

        # Scopes row
        scopes_frame = ttk.LabelFrame(self.frame, text="Scopes",
                                         padding=6)
        scopes_frame.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Button(scopes_frame, text="All",
                    command=self._select_all_scopes).grid(
            row=0, column=0, padx=2)
        ttk.Button(scopes_frame, text="None",
                    command=self._select_no_scopes).grid(
            row=0, column=1, padx=2)
        col = 2
        row = 0
        for key in ALL_SCOPES:
            var = tk.BooleanVar(value=True)
            self._scope_vars[key] = var
            ttk.Checkbutton(scopes_frame, text=SCOPE_LABELS[key],
                              variable=var).grid(row=row, column=col,
                                                  sticky="w", padx=4)
            col += 1
            if col >= 8:
                col = 2
                row += 1

        # Filters row (items 23–30)
        filt = ttk.LabelFrame(self.frame, text="Filters", padding=6)
        filt.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Label(filt, text="Year:").grid(row=0, column=0, sticky="e")
        self.year_e = ttk.Entry(filt, width=6)
        self.year_e.grid(row=0, column=1, padx=(2, 8))
        ttk.Label(filt, text="Tutor group:").grid(row=0, column=2,
                                                    sticky="e")
        self.tg_e = ttk.Entry(filt, width=10)
        self.tg_e.grid(row=0, column=3, padx=(2, 8))
        ttk.Label(filt, text="Role:").grid(row=0, column=4, sticky="e")
        self.role_e = ttk.Entry(filt, width=10)
        self.role_e.grid(row=0, column=5, padx=(2, 8))
        ttk.Label(filt, text="Staff:").grid(row=0, column=6, sticky="e")
        self.owner_e = ttk.Entry(filt, width=10)
        self.owner_e.grid(row=0, column=7, padx=(2, 8))
        ttk.Label(filt, text="Actor:").grid(row=0, column=8, sticky="e")
        self.actor_e = ttk.Entry(filt, width=10)
        self.actor_e.grid(row=0, column=9, padx=(2, 8))
        self.sen_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filt, text="SEN only",
                          variable=self.sen_var).grid(row=0, column=10,
                                                       padx=4)
        self.arch_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filt, text="Inc. archived",
                          variable=self.arch_var).grid(row=0, column=11,
                                                        padx=4)
        self.interleave_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filt, text="Interleave by score",
                          variable=self.interleave_var).grid(
            row=0, column=12, padx=4)
        self.cluster_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filt, text="Cluster by student",
                          variable=self.cluster_var).grid(
            row=0, column=13, padx=4)
        self.fold_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(filt, text="Fold accents",
                          variable=self.fold_var).grid(
            row=0, column=14, padx=4)
        # Security + live-search controls (items 31, 35, 42)
        self.redact_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filt, text="Redact sensitive",
                          variable=self.redact_var).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Label(filt, text="Break-glass reason:").grid(
            row=1, column=2, sticky="e")
        self.bg_e = ttk.Entry(filt, width=22)
        self.bg_e.grid(row=1, column=3, columnspan=3, sticky="w", padx=(2, 8))
        self.live_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(filt, text="Live (search as you type)",
                          variable=self.live_var).grid(
            row=1, column=6, columnspan=3, sticky="w")
        self._live_after = None

        # Controls strip: grouping (21), column chooser (18), stats (22)
        ctrl = ttk.Frame(self.frame)
        ctrl.pack(fill="x", padx=8, pady=(0, 2))
        ttk.Label(ctrl, text="Group by:").pack(side="left")
        self.group_by = tk.StringVar(value="Scope")
        gb = ttk.Combobox(ctrl, textvariable=self.group_by, width=8,
                           state="readonly",
                           values=["Scope", "Year", "Tutor", "Risk"])
        gb.pack(side="left", padx=(2, 8))
        gb.bind("<<ComboboxSelected>>", lambda _e: self._rerender())
        self._col_vars: dict[str, tk.BooleanVar] = {}
        colmb = ttk.Menubutton(ctrl, text="Columns ▾")
        colmenu = tk.Menu(colmb, tearoff=False)
        for key, lbl in (("entity_id", "ID"), ("label", "Label"),
                         ("sublabel", "Details"), ("match", "Match")):
            v = tk.BooleanVar(value=True)
            self._col_vars[key] = v
            colmenu.add_checkbutton(label=lbl, variable=v,
                                     command=self._apply_columns)
        colmb.configure(menu=colmenu)
        colmb.pack(side="left")
        self.stats_var = tk.StringVar(value="")
        ttk.Label(ctrl, textvariable=self.stats_var,
                   anchor="e").pack(side="right")

        # Main split: results (left) + preview/shortlist (right) (19, 23)
        paned = ttk.Panedwindow(self.frame, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=4)
        table_frame = ttk.Frame(paned)
        paned.add(table_frame, weight=3)
        self._cols = ("entity_id", "label", "sublabel", "match")
        self._col_titles = {"entity_id": "ID", "label": "Label",
                            "sublabel": "Details", "match": "Match"}
        self.tree = ttk.Treeview(table_frame, columns=self._cols,
                                    show="tree headings")
        self.tree.heading("#0", text="Group")
        for c in self._cols:
            self.tree.heading(
                c, text=self._col_titles[c],
                command=lambda cc=c: self._sort_by(cc))
        self.tree.column("#0", width=150, anchor="w")
        self.tree.column("entity_id", width=80, anchor="w")
        self.tree.column("label", width=300, anchor="w")
        self.tree.column("sublabel", width=420, anchor="w")
        self.tree.column("match", width=150, anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("scope", background="#eef7ff",
                                  font=("", 10, "bold"))

        right = ttk.Panedwindow(paned, orient="vertical")
        paned.add(right, weight=2)
        # Preview pane (item 19)
        prev_frame = ttk.LabelFrame(right, text="Preview", padding=4)
        right.add(prev_frame, weight=3)
        self.preview = tk.Text(prev_frame, wrap="word", width=38,
                                font=("TkFixedFont", 9), state="disabled")
        self.preview.pack(fill="both", expand=True)
        # Shortlist tray (item 23) — persists across searches this session
        sl_frame = ttk.LabelFrame(right, text="Shortlist", padding=4)
        right.add(sl_frame, weight=2)
        self.shortlist_box = tk.Listbox(sl_frame, height=6)
        self.shortlist_box.pack(side="left", fill="both", expand=True)
        self.shortlist_box.bind("<Double-1>",
                                 lambda _e: self._open_shortlisted())
        slb = ttk.Frame(sl_frame)
        slb.pack(side="right", fill="y")
        ttk.Button(slb, text="Open", width=7,
                    command=self._open_shortlisted).pack(pady=1)
        ttk.Button(slb, text="Remove", width=7,
                    command=self._remove_shortlisted).pack(pady=1)
        ttk.Button(slb, text="→Cohort", width=7,
                    command=self._shortlist_to_cohort).pack(pady=1)
        ttk.Button(slb, text="Clear", width=7,
                    command=self._clear_shortlist).pack(pady=1)
        self._shortlist: list[Hit] = []

        # Bulk-actions toolbar (item 20) + recent breadcrumb (item 25)
        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(2, 4))
        ttk.Button(actions, text="Open",
                    command=self._open_selected).pack(side="left")
        ttk.Button(actions, text="Copy IDs",
                    command=self._copy_ids).pack(side="left", padx=(4, 0))
        ttk.Button(actions, text="Copy emails",
                    command=self._copy_emails).pack(side="left", padx=(4, 0))
        ttk.Button(actions, text="Export…",
                    command=self._export_results_dialog).pack(
            side="left", padx=(4, 0))
        ttk.Button(actions, text="Message…",
                    command=self._mailmerge_dialog).pack(side="left",
                                                          padx=(4, 0))
        ttk.Button(actions, text="Contact sheet",
                    command=self._contact_sheet).pack(side="left", padx=(4, 0))
        ttk.Button(actions, text="Pin",
                    command=self._pin_selected).pack(side="left", padx=(4, 0))
        ttk.Button(actions, text="Shortlist +",
                    command=self._add_to_shortlist).pack(side="left",
                                                          padx=(4, 0))
        ttk.Button(actions, text="Save as cohort…",
                    command=self._save_cohort).pack(side="left", padx=(4, 0))
        self.recent_var = tk.StringVar()
        self.recent_combo = ttk.Combobox(
            actions, textvariable=self.recent_var, width=26,
            state="readonly")
        self.recent_combo.pack(side="right")
        self.recent_combo.bind("<<ComboboxSelected>>", self._reopen_recent)
        ttk.Label(actions, text="Recently opened:").pack(side="right",
                                                          padx=(0, 4))
        self._recent: list[Hit] = []

        # Suggested-filter facet chips (item 47).
        self.facet_frame = ttk.Frame(self.frame)
        self.facet_frame.pack(fill="x", padx=8)

        # Did-you-mean row (item 20 of the previous batch).
        self.sugg_frame = ttk.Frame(self.frame)
        self.sugg_frame.pack(fill="x", padx=8)

        # Status bar
        self.status_var = tk.StringVar(value="Ready.  (/ to focus, "
                                              "Enter to search, "
                                              "double-click to open, "
                                              "type to jump)")
        ttk.Label(self.frame, textvariable=self.status_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

        # Keyboard navigation + type-ahead jump (item 24)
        self.tree.bind("<Double-1>", lambda _e: self._open_selected())
        self.tree.bind("<Return>", lambda _e: self._open_selected())
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Key>", self._type_ahead)
        self.frame.bind_all("<slash>", self._focus_query)
        self.frame.bind_all("<Control-l>", self._focus_query)
        self.frame.bind_all("<Escape>", self._focus_query)
        self.query_e.bind("<Down>",
                           lambda _e: (self.tree.focus_set(),
                                        self._focus_first_hit()))
        self._typeahead_buf = ""
        self._sort_state: tuple[str, bool] | None = None
        self._last_results: SearchResults | None = None
        self._group_index: dict[str, tuple] = {}

    def _selected_scopes(self) -> list[str]:
        return [k for k, v in self._scope_vars.items() if v.get()]

    def _select_all_scopes(self) -> None:
        for v in self._scope_vars.values():
            v.set(True)

    def _select_no_scopes(self) -> None:
        for v in self._scope_vars.values():
            v.set(False)

    def _clear(self) -> None:
        self.query_e.delete(0, "end")
        for i in self.tree.get_children():
            self.tree.delete(i)
        self._show_suggestion("")
        for w in self.facet_frame.winfo_children():
            w.destroy()
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.configure(state="disabled")
        self.stats_var.set("")
        self.status_var.set("Cleared.  (shortlist kept)")

    # Public API for other tabs to load a query into the search bar
    # and run it.
    def load_query(self, query: str, scopes: list[str] | None) -> None:
        self.query_e.delete(0, "end")
        self.query_e.insert(0, query)
        if scopes is not None:
            for k, v in self._scope_vars.items():
                v.set(k in scopes)
        self.run()

    def run(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        q = self.query_e.get().strip()
        scopes = self._selected_scopes()
        if not scopes:
            self.status_var.set("No scopes selected — pick at least one.")
            return
        try:
            limit = int(self.limit_e.get().strip()
                         or str(DEFAULT_LIMIT_PER_SCOPE))
        except ValueError:
            messagebox.showerror("Limit",
                                    "Limit must be a positive integer.")
            return
        filters: dict[str, object] = {}
        if self.year_e.get().strip():
            filters["year_group"] = self.year_e.get().strip()
        if self.tg_e.get().strip():
            filters["tutor_group"] = self.tg_e.get().strip()
        if self.role_e.get().strip():
            filters["role"] = self.role_e.get().strip()
        if self.owner_e.get().strip():
            filters["owned_by_staff"] = self.owner_e.get().strip()
        if self.sen_var.get():
            filters["sen_only"] = True
        if self.arch_var.get():
            filters["include_archived"] = True
        if self.redact_var.get():
            filters["redact"] = True
        if self.bg_e.get().strip():
            filters["break_glass"] = self.bg_e.get().strip()
        actor = self.actor_e.get().strip() or None
        options = QueryOptions(fold_diacritics=self.fold_var.get())
        try:
            results = data.run_search(
                q, scopes=scopes, limit_per_scope=limit,
                filters=filters, actor=actor, options=options,
                interleave=self.interleave_var.get(),
                cluster_by_student=self.cluster_var.get())
        except ValidationError as e:
            messagebox.showerror("Search error", str(e))
            return
        self._render(results)

    def _render(self, results: SearchResults) -> None:
        self._last_results = results
        self._rerender()
        self._render_facets(results)
        self._show_suggestion(
            results.suggestions[0]
            if results.total == 0 and results.suggestions else "")

    # ── Live search (item 42) ─────────────────────────────────────

    def _on_query_key(self, event) -> None:
        if not getattr(self, "live_var", None) or not self.live_var.get():
            return
        if event.keysym in ("Return", "Up", "Down", "Left", "Right",
                            "Tab", "Escape"):
            return
        if self._live_after is not None:
            try:
                self.frame.after_cancel(self._live_after)
            except Exception:
                pass
        self._live_after = self.frame.after(400, self.run)

    # ── Suggested-filter facet chips (item 47) ────────────────────

    def _render_facets(self, results: SearchResults) -> None:
        for w in self.facet_frame.winfo_children():
            w.destroy()
        try:
            fcs = data.facets(results, top=4)
        except Exception:
            fcs = []
        if not fcs:
            return
        ttk.Label(self.facet_frame, text="Narrow:").pack(side="left")
        shown = 0
        for f in fcs:
            for val, cnt in f.values:
                if shown >= 12:
                    return
                ttk.Button(
                    self.facet_frame, text=f"{f.field}:{val} ({cnt})",
                    command=lambda fl=f.field, v=val: self._apply_facet(fl, v)
                ).pack(side="left", padx=2)
                shown += 1

    def _apply_facet(self, field: str, value: str) -> None:
        add = f'{field}:"{value}"' if " " in value else f"{field}:{value}"
        cur = self.query_e.get().strip()
        self.query_e.delete(0, "end")
        self.query_e.insert(0, (cur + " " + add).strip())
        self.run()

    # ── Export / message / contact sheet (items 36, 37, 39) ───────

    def _export_results_dialog(self) -> None:
        if self._last_results is None or self._last_results.total == 0:
            self.status_var.set("Run a search first.")
            return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Excel", "*.xlsx"),
                       ("PDF", "*.pdf"), ("HTML", "*.html"),
                       ("JSON", "*.json"), ("Markdown", "*.md"),
                       ("TSV", "*.tsv")],
            initialfile="advanced_search_results.csv")
        if not path:
            return
        try:
            data.export_results_file(self._last_results, path)
            self.status_var.set(f"Exported to {path}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def _mailmerge_dialog(self) -> None:
        if self._last_results is None:
            self.status_var.set("Run a search first.")
            return
        from tkinter import simpledialog
        subject = simpledialog.askstring("Message students", "Subject:")
        if not subject:
            return
        body = simpledialog.askstring("Message students", "Body:") or ""
        try:
            res = data.mailmerge_results(
                self._last_results, subject=subject, body=body, send=False)
        except Exception as e:
            messagebox.showerror("Message failed", str(e))
            return
        messagebox.showinfo(
            "Message",
            f"Drafted {res['created']} message(s) to "
            f"{res['recipients']} student(s) (thread {res['thread_id']}).")

    def _contact_sheet(self) -> None:
        if self._last_results is None or self._last_results.total == 0:
            self.status_var.set("Run a search first.")
            return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".html", filetypes=[("HTML", "*.html")],
            initialfile="contact_sheet.html")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(data.contact_sheet(self._last_results))
            self.status_var.set(f"Contact sheet → {path}")
        except Exception as e:
            messagebox.showerror("Contact sheet failed", str(e))

    def _rerender(self) -> None:
        """(Re)draw the tree honouring the current Group-by choice (21),
        refresh the quick-stats bar (22) and apply column visibility (18)."""
        for i in self.tree.get_children():
            self.tree.delete(i)
        self._hit_by_item: dict[str, Hit] = {}
        results = self._last_results
        if results is None:
            return
        mode = self.group_by.get()
        if mode in ("Year", "Tutor"):
            try:
                self._group_index = data.student_group_index()
            except Exception:
                self._group_index = {}
        groups: dict[str, list[Hit]] = {}
        order: list[str] = []
        for scope in results.scopes:
            for h in results.hits_by_scope.get(scope, []):
                key = self._group_key(scope, h)
                if key not in groups:
                    groups[key] = []
                    order.append(key)
                groups[key].append(h)
        for key in order:
            hits = groups[key]
            node = self.tree.insert(
                "", "end", text=f"{key}  ({len(hits)})",
                values=("", "", "", ""), open=True, tags=("scope",))
            for h in hits:
                item_id = self.tree.insert(
                    node, "end", text="",
                    values=(h.entity_id, h.label, h.sublabel,
                             h.matched_field))
                self._hit_by_item[item_id] = h
        self._apply_columns()
        per = {s: len(results.hits_by_scope.get(s, [])) for s in results.scopes}
        chips = [f"{SCOPE_LABELS.get(s, s)} {n}" for s, n in per.items() if n]
        self.stats_var.set("   ·   ".join(chips[:8])
                           + (f"      Σ {results.total}" if results.total
                              else ""))
        self.status_var.set(
            f"{results.total} hit(s) for "
            f"{(results.query or '(empty)')!r}  ·  grouped by "
            f"{mode.lower()}")

    def _hit_student_id(self, scope: str, h: Hit) -> str:
        if scope == "students":
            return h.entity_id
        if scope in data._STUDENT_KEYED_SCOPES:
            doc = (h.extra or {}).get("_doc") or {}
            return str(doc.get("name") or "").strip()
        return ""

    def _group_key(self, scope: str, h: Hit) -> str:
        mode = self.group_by.get()
        if mode == "Scope":
            return SCOPE_LABELS.get(scope, scope)
        if mode == "Risk":
            doc = (h.extra or {}).get("_doc") or {}
            return f"Risk: {doc.get('level') or '—'}"
        sid = self._hit_student_id(scope, h)
        if not sid:
            return "(non-student)"
        yr, tg = self._group_index.get(sid, (None, None))
        if mode == "Year":
            return f"Year {yr}" if yr is not None else "Year —"
        return f"Tutor {tg}" if tg else "Tutor —"

    # ── Column chooser + sortable columns (item 18) ───────────────

    def _apply_columns(self) -> None:
        visible = [c for c in self._cols if self._col_vars[c].get()]
        self.tree.configure(displaycolumns=visible or list(self._cols))

    def _sort_by(self, col: str) -> None:
        asc = True
        if self._sort_state and self._sort_state[0] == col:
            asc = not self._sort_state[1]
        self._sort_state = (col, asc)
        for node in self.tree.get_children():
            kids = list(self.tree.get_children(node))
            kids.sort(key=lambda k: (self.tree.set(k, col) or "").lower(),
                      reverse=not asc)
            for pos, k in enumerate(kids):
                self.tree.move(k, node, pos)
        for c in self._cols:
            arrow = (" ▲" if asc else " ▼") if c == col else ""
            self.tree.heading(c, text=self._col_titles[c] + arrow)

    # ── Preview pane (item 19) ────────────────────────────────────

    def _on_select(self, _event=None) -> None:
        hits = self._selected_hits()
        if not hits:
            return
        h = hits[0]
        doc = (h.extra or {}).get("_doc") or {}
        lines = [f"[{h.scope}]  {h.entity_id}", h.label, ""]
        if h.sublabel:
            lines += [h.sublabel, ""]
        for k, v in doc.items():
            if k.startswith("_") or v in (None, ""):
                continue
            lines.append(f"{k:>14}: {v}")
        if h.matched_fields:
            lines += ["", "matched: " + ", ".join(h.matched_fields)]
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", "\n".join(str(x) for x in lines))
        self.preview.configure(state="disabled")

    # ── Keyboard type-ahead jump (item 24) ────────────────────────

    def _type_ahead(self, event) -> None:
        ch = event.char
        if not ch or len(ch) != 1 or not ch.isprintable():
            return
        self._typeahead_buf = (self._typeahead_buf + ch).lower()
        after = getattr(self, "_ta_after", None)
        if after is not None:
            try:
                self.frame.after_cancel(after)
            except Exception:
                pass
        self._ta_after = self.frame.after(800, self._reset_typeahead)
        for node in self.tree.get_children():
            for k in self.tree.get_children(node):
                lbl = (self.tree.set(k, "label") or "").lower()
                if lbl.startswith(self._typeahead_buf):
                    self.tree.see(k)
                    self.tree.selection_set(k)
                    self.tree.focus(k)
                    return

    def _reset_typeahead(self) -> None:
        self._typeahead_buf = ""

    def _show_suggestion(self, suggestion: str) -> None:
        for w in self.sugg_frame.winfo_children():
            w.destroy()
        if not suggestion:
            return
        ttk.Label(self.sugg_frame,
                   text="Did you mean:").pack(side="left")

        def _apply() -> None:
            self.query_e.delete(0, "end")
            self.query_e.insert(0, suggestion)
            self.run()

        ttk.Button(self.sugg_frame, text=suggestion,
                    command=_apply).pack(side="left", padx=(4, 0))

    def _show_syntax(self) -> None:
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title("Advanced Search — query syntax")
        win.geometry("760x520")
        txt = tk.Text(win, wrap="none", font=("TkFixedFont", 10))
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert("1.0", QUERY_SYNTAX_HELP)
        txt.configure(state="disabled")
        ttk.Button(win, text="Close",
                    command=win.destroy).pack(pady=(0, 8))

    # ── Bulk-action handlers (item 45) ────────────────────────────

    def _selected_hits(self) -> list[Hit]:
        return [self._hit_by_item[i]
                for i in self.tree.selection()
                if i in getattr(self, "_hit_by_item", {})]

    def _open_selected(self) -> None:
        hits = self._selected_hits()
        if not hits:
            self.status_var.set("Nothing selected.")
            return
        opened = 0
        for h in hits:
            self._push_recent(h)
            if data.open_hit(h) is not None:
                opened += 1
        self.status_var.set(
            f"Opened {opened}/{len(hits)} — "
            f"{'(no editor registered)' if not opened else ''}")

    # ── Recent-result breadcrumb (item 25) ────────────────────────

    def _push_recent(self, h: Hit) -> None:
        key = (h.scope, h.entity_id)
        self._recent = [x for x in self._recent
                        if (x.scope, x.entity_id) != key]
        self._recent.insert(0, h)
        self._recent = self._recent[:10]
        self.recent_combo.configure(
            values=[f"[{x.scope}] {x.label[:34]}" for x in self._recent])

    def _reopen_recent(self, _event=None) -> None:
        i = self.recent_combo.current()
        if 0 <= i < len(self._recent):
            data.open_hit(self._recent[i])

    # ── Copy emails + shortlist + cohort (items 20, 23) ───────────

    def _copy_emails(self) -> None:
        emails: list[str] = []
        for h in self._selected_hits():
            doc = (h.extra or {}).get("_doc") or {}
            e = str(doc.get("email") or "").strip()
            if e and e not in emails:
                emails.append(e)
        if not emails:
            self.status_var.set("No emails in selection.")
            return
        self.frame.clipboard_clear()
        self.frame.clipboard_append("; ".join(emails))
        self.status_var.set(f"Copied {len(emails)} email(s).")

    def _add_to_shortlist(self) -> None:
        existing = {(h.scope, h.entity_id) for h in self._shortlist}
        added = 0
        for h in self._selected_hits():
            if (h.scope, h.entity_id) not in existing:
                self._shortlist.append(h)
                existing.add((h.scope, h.entity_id))
                added += 1
        self._refresh_shortlist()
        self.status_var.set(
            f"Added {added} to shortlist ({len(self._shortlist)} total).")

    def _refresh_shortlist(self) -> None:
        self.shortlist_box.delete(0, "end")
        for h in self._shortlist:
            self.shortlist_box.insert("end", f"[{h.scope}] {h.label[:40]}")

    def _open_shortlisted(self) -> None:
        sel = self.shortlist_box.curselection()
        targets = ([self._shortlist[i] for i in sel] if sel
                   else list(self._shortlist))
        for h in targets:
            self._push_recent(h)
            data.open_hit(h)

    def _remove_shortlisted(self) -> None:
        for i in sorted(self.shortlist_box.curselection(), reverse=True):
            del self._shortlist[i]
        self._refresh_shortlist()

    def _clear_shortlist(self) -> None:
        self._shortlist = []
        self._refresh_shortlist()

    def _shortlist_to_cohort(self) -> None:
        if not self._shortlist:
            messagebox.showinfo("Cohort", "Shortlist is empty.")
            return
        self._cohort_from_hits(self._shortlist, "shortlist")

    def _save_cohort(self) -> None:
        if self._last_results is None or self._last_results.total == 0:
            messagebox.showinfo("Cohort", "Run a search with results first.")
            return
        from tkinter import simpledialog
        name = simpledialog.askstring("Save cohort", "Cohort name:")
        if not name:
            return
        try:
            c = data.create_cohort_from_results(name.strip(),
                                                 self._last_results)
        except Exception as e:
            messagebox.showerror("Cohort failed", str(e))
            return
        messagebox.showinfo(
            "Cohort",
            f"Cohort '{c.name}' saved with {c.member_count} student(s).")

    def _cohort_from_hits(self, hits: list[Hit], default_name: str) -> None:
        from tkinter import simpledialog
        name = simpledialog.askstring("Save cohort", "Cohort name:",
                                       initialvalue=default_name)
        if not name:
            return
        ids: list[str] = []
        for h in hits:
            sid = self._hit_student_id(h.scope, h)
            if sid and sid not in ids:
                ids.append(sid)
        if not ids:
            messagebox.showinfo("Cohort", "No students in selection.")
            return
        try:
            c = data.create_cohort(name.strip(), ids)
        except Exception as e:
            messagebox.showerror("Cohort failed", str(e))
            return
        messagebox.showinfo(
            "Cohort",
            f"Cohort '{c.name}' saved with {c.member_count} student(s).")

    def _copy_ids(self) -> None:
        hits = self._selected_hits()
        if not hits:
            return
        text = "\n".join(h.entity_id for h in hits)
        self.frame.clipboard_clear()
        self.frame.clipboard_append(text)
        self.status_var.set(f"Copied {len(hits)} id(s).")

    def _export_csv(self) -> None:
        if self._last_results is None:
            self.status_var.set("Run a search first.")
            return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
            initialfile="advanced_search_results.csv")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(data.export_results_csv(self._last_results))
            self.status_var.set(f"Exported to {path}")
        except OSError as e:
            messagebox.showerror("Export failed", str(e))

    def _pin_selected(self) -> None:
        hits = self._selected_hits()
        if not hits:
            return
        actor = "default"   # caller can set window.actor for per-user pins
        n = 0
        for h in hits:
            try:
                data.pin_result(actor, h.scope, h.entity_id,
                                 label=h.label)
                n += 1
            except ValidationError:
                pass
        self.status_var.set(f"Pinned {n} hit(s) for actor={actor!r}")

    # ── Keyboard helpers (item 44) ────────────────────────────────

    def _focus_query(self, _event=None) -> str:
        try:
            self.query_e.focus_set()
            self.query_e.select_range(0, "end")
        except Exception:
            pass
        return "break"

    def _focus_first_hit(self) -> None:
        for parent in self.tree.get_children():
            kids = self.tree.get_children(parent)
            if kids:
                self.tree.selection_set(kids[0])
                self.tree.focus(kids[0])
                return


# ══ Saved searches tab ═════════════════════════════════════════════

class SavedTab:
    def __init__(self, nb: ttk.Notebook, search_tab: SearchTab) -> None:
        self.search_tab = search_tab
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Saved")
        self._build()
        self.refresh()

    def _build(self) -> None:
        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        cols = ("id", "name", "query", "scopes", "notes")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        widths = {"id": 60, "name": 180, "query": 180,
                  "scopes": 320, "notes": 300}
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._run_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="Run",
                    command=self._run_selected).pack(side="left")
        ttk.Button(actions, text="New",
                    command=self._new).pack(side="left", padx=4)
        ttk.Button(actions, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left",
                                                          padx=4)
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = data.list_saved_searches()
        for s in rows:
            scopes = ", ".join(s.scopes) if s.scopes else "(all)"
            self.tree.insert("", "end", iid=str(s.saved_id), values=(
                s.saved_id, s.name, s.query or "(empty)",
                scopes, s.notes or "",
            ))
        self.count_var.set(f"{len(rows)} saved.")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _run_selected(self) -> None:
        sid = self._selected_id()
        if sid is None:
            messagebox.showinfo("Run", "Select a saved search first.")
            return
        s = data.get_saved_search(sid)
        if s is None:
            return
        # Switch to the Search tab and run the saved query.
        nb = self.frame.master
        if isinstance(nb, ttk.Notebook):
            nb.select(0)
        self.search_tab.load_query(s.query, s.scopes or None)

    def _new(self) -> None:
        SavedDialog(self.frame.winfo_toplevel(),
                     existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        sid = self._selected_id()
        if sid is None:
            messagebox.showinfo("Edit", "Select a saved search first.")
            return
        existing = data.get_saved_search(sid)
        if existing is None:
            return
        SavedDialog(self.frame.winfo_toplevel(),
                     existing=existing, on_save=self.refresh)

    def _delete_selected(self) -> None:
        sid = self._selected_id()
        if sid is None:
            messagebox.showinfo("Delete", "Select a saved search first.")
            return
        if not messagebox.askyesno("Delete",
                                     f"Delete saved search #{sid}?"):
            return
        try:
            data.delete_saved_search(sid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ History tab ════════════════════════════════════════════════════

class HistoryTab:
    def __init__(self, nb: ttk.Notebook, search_tab: SearchTab) -> None:
        self.search_tab = search_tab
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="History")
        self._build()
        self.refresh()

    def _build(self) -> None:
        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        cols = ("id", "ts", "hits", "query", "scopes", "actor")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        headings = {"id": "ID", "ts": "When", "hits": "Hits",
                    "query": "Query", "scopes": "Scopes",
                    "actor": "Actor"}
        widths = {"id": 60, "ts": 160, "hits": 60,
                  "query": 220, "scopes": 320, "actor": 120}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c == "hits" else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._rerun_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="Re-run",
                    command=self._rerun_selected).pack(side="left")
        ttk.Button(actions, text="Refresh",
                    command=self.refresh).pack(side="right")
        ttk.Button(actions, text="Clear all",
                    command=self._clear).pack(side="right", padx=4)

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = data.list_history(limit=50)
        for h in rows:
            scopes = ", ".join(h.scopes) if h.scopes else "(all)"
            self.tree.insert("", "end", iid=str(h.history_id), values=(
                h.history_id, h.ts, h.result_count,
                h.query or "(empty)", scopes, h.actor or "—",
            ))
        self.count_var.set(f"{len(rows)} entry/entries.")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _rerun_selected(self) -> None:
        hid = self._selected_id()
        if hid is None:
            messagebox.showinfo("Re-run",
                                  "Select a history entry first.")
            return
        rows = data.list_history(limit=50)
        match = next((h for h in rows if h.history_id == hid), None)
        if match is None:
            return
        nb = self.frame.master
        if isinstance(nb, ttk.Notebook):
            nb.select(0)
        self.search_tab.load_query(match.query, match.scopes or None)

    def _clear(self) -> None:
        if not messagebox.askyesno("Clear",
                                     "Clear all search history?"):
            return
        n = data.clear_history()
        messagebox.showinfo("Clear", f"Cleared {n} entry/entries.")
        self.refresh()


# ══ Dialogs ════════════════════════════════════════════════════════

class SavedDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: SavedSearch | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Saved Search" if existing
                          else "New Saved Search")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._scope_vars: dict[str, tk.BooleanVar] = {}
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win, padding=12)
        form.pack(fill="both", expand=True)

        ttk.Label(form, text="Name:").grid(row=0, column=0,
                                              sticky="e", pady=4)
        self.name_e = ttk.Entry(form, width=40)
        if self.existing:
            self.name_e.insert(0, self.existing.name)
        self.name_e.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Query:").grid(row=1, column=0,
                                               sticky="e", pady=4)
        self.query_e = ttk.Entry(form, width=40)
        if self.existing:
            self.query_e.insert(0, self.existing.query)
        self.query_e.grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(form, text="Scopes:").grid(row=2, column=0,
                                                sticky="ne", pady=4)
        scopes_frame = ttk.Frame(form)
        scopes_frame.grid(row=2, column=1, sticky="w", padx=6)
        current = set(self.existing.scopes) if self.existing else set(ALL_SCOPES)
        col = 0
        row = 0
        for key in ALL_SCOPES:
            var = tk.BooleanVar(value=key in current)
            self._scope_vars[key] = var
            ttk.Checkbutton(scopes_frame, text=SCOPE_LABELS[key],
                              variable=var).grid(row=row, column=col,
                                                  sticky="w", padx=2)
            col += 1
            if col >= 3:
                col = 0
                row += 1

        ttk.Label(form, text="Notes:").grid(row=3, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=40, height=4)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=3, column=1, sticky="w", padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=4, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        scopes = [k for k, v in self._scope_vars.items() if v.get()]
        payload = {
            "name":   self.name_e.get().strip(),
            "query":  self.query_e.get().strip(),
            "scopes": scopes or list(ALL_SCOPES),
            "notes":  self.notes_t.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_saved_search(self.existing.saved_id, payload)
            else:
                data.create_saved_search(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


# ══ Tools tab (telemetry, FTS, pinning, subscriptions, export) ════════

class ToolsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Tools")
        self._build()

    def _build(self) -> None:
        # Section: Index / cache
        sec1 = ttk.LabelFrame(self.frame, text="Index & cache",
                               padding=8)
        sec1.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Button(sec1, text="Rebuild FTS5 index",
                    command=self._rebuild_index).pack(side="left")
        ttk.Button(sec1, text="Clear search cache",
                    command=self._clear_cache).pack(side="left",
                                                     padx=(6, 0))
        self.fts_var = tk.StringVar(value=self._fts_status())
        ttk.Label(sec1, textvariable=self.fts_var).pack(side="left",
                                                          padx=(12, 0))

        # Section: Subscriptions
        sec2 = ttk.LabelFrame(self.frame, text="Subscriptions",
                               padding=8)
        sec2.pack(fill="x", padx=10, pady=4)
        ttk.Button(sec2, text="Poll now",
                    command=self._poll).pack(side="left")
        ttk.Label(sec2, text="  Inbox for actor:").pack(side="left")
        self.inbox_actor = ttk.Entry(sec2, width=14)
        self.inbox_actor.pack(side="left", padx=(2, 4))
        ttk.Button(sec2, text="Show inbox",
                    command=self._show_inbox).pack(side="left")
        ttk.Label(sec2, text="  Snooze id:").pack(side="left")
        self.snooze_id = ttk.Entry(sec2, width=6)
        self.snooze_id.pack(side="left", padx=(2, 4))
        ttk.Button(sec2, text="Snooze 24h",
                    command=self._snooze).pack(side="left")

        # Section: Alerts & dashboards (items 27, 29)
        sec_a = ttk.LabelFrame(self.frame, text="Alerts & dashboards",
                                padding=8)
        sec_a.pack(fill="x", padx=10, pady=4)
        ttk.Label(sec_a, text="Digest actor:").pack(side="left")
        self.digest_actor = ttk.Entry(sec_a, width=12)
        self.digest_actor.pack(side="left", padx=(2, 4))
        ttk.Button(sec_a, text="Build digest",
                    command=self._digest).pack(side="left")
        ttk.Label(sec_a, text="   Dashboard:").pack(side="left")
        self.dash_name = ttk.Entry(sec_a, width=14)
        self.dash_name.pack(side="left", padx=(2, 4))
        ttk.Button(sec_a, text="Run",
                    command=self._run_dashboard).pack(side="left")
        ttk.Button(sec_a, text="List",
                    command=self._list_dashboards).pack(side="left",
                                                        padx=(4, 0))

        # Section: Data quality & admin (items 33, 41, 43, 44, 45, 46)
        sec_b = ttk.LabelFrame(self.frame, text="Data quality & admin",
                                padding=8)
        sec_b.pack(fill="x", padx=10, pady=4)
        ttk.Button(sec_b, text="Index status",
                    command=self._index_status).pack(side="left")
        ttk.Button(sec_b, text="Refresh stale",
                    command=self._refresh_stale).pack(side="left", padx=(4, 0))
        ttk.Button(sec_b, text="Cache stats",
                    command=self._cache_stats).pack(side="left", padx=(4, 0))
        ttk.Button(sec_b, text="Duplicate students",
                    command=self._duplicates).pack(side="left", padx=(4, 0))
        ttk.Button(sec_b, text="Data gaps",
                    command=self._data_gaps).pack(side="left", padx=(4, 0))
        ttk.Button(sec_b, text="Audit log",
                    command=self._audit).pack(side="left", padx=(4, 0))
        ttk.Button(sec_b, text="Search volume",
                    command=self._volume).pack(side="left", padx=(4, 0))

        # Section: Saved searches export/import
        sec3 = ttk.LabelFrame(self.frame, text="Saved searches",
                               padding=8)
        sec3.pack(fill="x", padx=10, pady=4)
        ttk.Button(sec3, text="Export to JSON…",
                    command=self._export).pack(side="left")
        ttk.Button(sec3, text="Import from JSON…",
                    command=self._import).pack(side="left", padx=(6, 0))

        # Section: Telemetry
        sec4 = ttk.LabelFrame(self.frame, text="Telemetry",
                               padding=8)
        sec4.pack(fill="both", expand=True, padx=10, pady=4)
        ttk.Button(sec4, text="Refresh",
                    command=self._refresh_telemetry).pack(side="top",
                                                            anchor="w")
        self.telem_txt = tk.Text(sec4, height=18, wrap="word")
        self.telem_txt.pack(fill="both", expand=True, pady=(6, 0))
        self._refresh_telemetry()

        # Section: Pinned
        sec5 = ttk.LabelFrame(self.frame, text="Pinned results",
                               padding=8)
        sec5.pack(fill="x", padx=10, pady=(4, 10))
        ttk.Label(sec5, text="Actor:").pack(side="left")
        self.pin_actor = ttk.Entry(sec5, width=14)
        self.pin_actor.pack(side="left", padx=(2, 4))
        ttk.Button(sec5, text="List",
                    command=self._list_pins).pack(side="left")

    # ── handlers ──────────────────────────────────────────────────

    def _fts_status(self) -> str:
        return ("FTS5: available"
                if data._fts_available() else "FTS5: NOT available")

    def _rebuild_index(self) -> None:
        if not data._fts_available():
            messagebox.showinfo("FTS5",
                                "SQLite FTS5 is not available.")
            return
        counts = data.refresh_index()
        total = sum(counts.values())
        messagebox.showinfo(
            "Index rebuilt",
            f"Indexed {total} row(s) across {len(counts)} scope(s).")

    def _clear_cache(self) -> None:
        data.clear_cache()
        messagebox.showinfo("Cache", "Search cache cleared.")

    def _poll(self) -> None:
        fired = data.poll_subscriptions()
        messagebox.showinfo(
            "Subscriptions",
            f"{len(fired)} subscription(s) fired.")

    def _show_inbox(self) -> None:
        actor = self.inbox_actor.get().strip()
        if not actor:
            messagebox.showinfo("Inbox", "Enter an actor id first.")
            return
        rows = data.list_subscription_notifications(actor)
        if not rows:
            messagebox.showinfo("Inbox", "(empty)")
            return
        lines = []
        for r in rows[:50]:
            mark = "•" if not r.get("read_at") else " "
            lines.append(
                f"{mark} #{r['notif_id']} +{r['delta']}/{r['total']}  "
                f"{r.get('sample_scope') or ''}: "
                f"{r.get('sample_label') or ''}")
        messagebox.showinfo(f"Inbox for {actor}",
                            "\n".join(lines))

    def _export(self) -> None:
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialfile="saved_searches.json",
            filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(data.export_saved_searches())
            messagebox.showinfo("Export", f"Wrote {path}")
        except OSError as e:
            messagebox.showerror("Export failed", str(e))

    def _import(self) -> None:
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        overwrite = messagebox.askyesno(
            "Import",
            "Overwrite existing saved searches with same name?")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
            counts = data.import_saved_searches(text,
                                                  overwrite=overwrite)
            messagebox.showinfo("Import", str(counts))
        except (OSError, ValidationError) as e:
            messagebox.showerror("Import failed", str(e))

    def _refresh_telemetry(self) -> None:
        ts = data.telemetry_summary()
        lines = [
            f"Total searches: {ts.total_searches}",
            f"Zero-result:    {ts.zero_result}",
            "",
            "Top queries:",
        ]
        for q, n in ts.top_queries:
            lines.append(f"  {n:>3}×  {q!r}")
        lines.append("")
        lines.append("Slowest scopes (avg ms):")
        for s, ms in ts.slowest_scopes_ms.items():
            lines.append(f"  {s:<22} {ms:>8.1f}")
        if ts.zero_result_queries:
            lines.append("")
            lines.append("Recent zero-result queries:")
            for q in ts.zero_result_queries:
                lines.append(f"  • {q!r}")
        self.telem_txt.configure(state="normal")
        self.telem_txt.delete("1.0", "end")
        self.telem_txt.insert("1.0", "\n".join(lines))
        self.telem_txt.configure(state="disabled")

    def _list_pins(self) -> None:
        actor = self.pin_actor.get().strip() or None
        pins = data.list_pinned(actor)
        if not pins:
            messagebox.showinfo("Pinned", "(none)")
            return
        text = "\n".join(
            f"#{p.pin_id}  {p.actor}  {p.scope}/{p.entity_id}  "
            f"{p.label}" for p in pins[:50])
        messagebox.showinfo("Pinned results", text)

    # ── Alerts / dashboards / admin handlers (items 26–50) ────────

    def _show_text(self, title: str, text: str) -> None:
        win = tk.Toplevel(self.frame.winfo_toplevel())
        win.title(title)
        win.geometry("720x460")
        t = tk.Text(win, wrap="none", font=("TkFixedFont", 9))
        t.pack(fill="both", expand=True, padx=8, pady=8)
        t.insert("1.0", text or "(nothing)")
        t.configure(state="disabled")
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 8))

    def _snooze(self) -> None:
        raw = self.snooze_id.get().strip()
        if not raw.isdigit():
            messagebox.showinfo("Snooze", "Enter a notification id.")
            return
        ok = data.snooze_notification(int(raw), hours=24)
        messagebox.showinfo("Snooze",
                            "Snoozed 24h." if ok else "Not found.")

    def _digest(self) -> None:
        dg = data.build_digest(self.digest_actor.get().strip() or None)
        lines = [f"Digest — {dg.total_new} new across "
                 f"{len(dg.lines)} scheduled search(es)", ""]
        for line in dg.lines:
            lines.append(
                f"{line.new_since_last:>4} new · total {line.total:<5} "
                f"{line.saved_name}  (last {line.last_run_at or '—'})")
        self._show_text("Subscription digest", "\n".join(lines))

    def _run_dashboard(self) -> None:
        name = self.dash_name.get().strip()
        if not name:
            messagebox.showinfo("Dashboard", "Enter a dashboard name/id.")
            return
        try:
            panels = data.run_dashboard(name)
        except Exception as e:
            messagebox.showerror("Dashboard", str(e))
            return
        lines = [f"{name}:", ""]
        for p in panels:
            cnt = "err" if p.total < 0 else str(p.total)
            lines.append(f"{cnt:>6}  {p.name}   ({p.query or '(empty)'})")
        self._show_text(f"Dashboard — {name}", "\n".join(lines))

    def _list_dashboards(self) -> None:
        rows = data.list_dashboards()
        lines = [f"#{d.dashboard_id}  {d.name}  "
                 f"({len(d.saved_ids)} panel(s))" for d in rows]
        self._show_text("Dashboards", "\n".join(lines) or "(none)")

    def _index_status(self) -> None:
        rows = data.index_status()
        lines = [f"{s.scope:<22} indexed {s.indexed_rows:>5} / current "
                 f"{s.current_rows:>5}  [{'STALE' if s.stale else 'ok'}]  "
                 f"{s.last_refresh or '—'}" for s in rows]
        self._show_text("FTS index status", "\n".join(lines))

    def _refresh_stale(self) -> None:
        counts = data.refresh_index(only_stale=True)
        messagebox.showinfo(
            "Refresh stale",
            f"Refreshed {sum(counts.values())} row(s) across "
            f"{len(counts)} scope(s).")
        self.fts_var.set(self._fts_status())

    def _cache_stats(self) -> None:
        st = data.cache_stats()
        messagebox.showinfo(
            "Cache stats",
            f"Entries: {st['entries']}/{st['max_entries']}\n"
            f"Hits: {st['hits']}   Misses: {st['misses']}\n"
            f"Hit-rate: {st['hit_rate']:.0%}   TTL: {st['ttl_seconds']}s")

    def _duplicates(self) -> None:
        groups = data.find_duplicate_students()
        lines = [f"[{g.reason}] {g.key}: {', '.join(g.student_ids)}"
                 for g in groups[:80]]
        self._show_text("Possible duplicate students",
                        "\n".join(lines) or "No likely duplicates.")

    def _data_gaps(self) -> None:
        gaps = data.find_data_gaps("students")
        lines = [f"{g.entity_id}  {g.label[:36]:<36}  "
                 f"missing: {', '.join(g.missing)}" for g in gaps[:120]]
        self._show_text("Student data gaps",
                        "\n".join(lines) or "No data gaps.")

    def _audit(self) -> None:
        rows = data.list_search_audit(limit=80)
        lines = []
        for e in rows:
            bg = "  [BREAK-GLASS]" if e.break_glass else ""
            lines.append(f"{e.ts}  {e.actor or '—'}/{e.role or '—'}  "
                         f"{e.query!r}  "
                         f"sens={','.join(e.sensitive_scopes)}{bg}")
            if e.reason:
                lines.append(f"      reason: {e.reason}")
        self._show_text("Sensitive-access audit",
                        "\n".join(lines) or "(no entries)")

    def _volume(self) -> None:
        rows = data.search_volume_by_day()
        lines = [f"{d}  {'#' * min(n, 50)} {n}" for d, n in rows]
        self._show_text("Searches per day",
                        "\n".join(lines) or "(no history)")
