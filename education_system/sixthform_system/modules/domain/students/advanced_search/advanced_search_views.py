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
        ttk.Label(bar, text="Limit/scope:").pack(side="left")
        self.limit_e = ttk.Entry(bar, width=6)
        self.limit_e.insert(0, str(DEFAULT_LIMIT_PER_SCOPE))
        self.limit_e.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Search",
                    command=self.run).pack(side="left")
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left", padx=(4, 0))

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

        # Results treeview (hierarchical: scope → hits)
        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("entity_id", "label", "sublabel", "match")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="tree headings")
        self.tree.heading("#0", text="Scope")
        self.tree.heading("entity_id", text="ID")
        self.tree.heading("label", text="Label")
        self.tree.heading("sublabel", text="Details")
        self.tree.heading("match", text="Match")
        self.tree.column("#0", width=160, anchor="w")
        self.tree.column("entity_id", width=80, anchor="w")
        self.tree.column("label", width=320, anchor="w")
        self.tree.column("sublabel", width=480, anchor="w")
        self.tree.column("match", width=160, anchor="w")
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("scope", background="#eef7ff",
                                  font=("", 10, "bold"))

        # Status bar
        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(self.frame, textvariable=self.status_var,
                   anchor="w").pack(fill="x", padx=8, pady=(0, 8))

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
        self.status_var.set("Cleared.")

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
        try:
            results = data.run_search(q, scopes=scopes,
                                        limit_per_scope=limit)
        except ValidationError as e:
            messagebox.showerror("Search error", str(e))
            return
        self._render(results)

    def _render(self, results: SearchResults) -> None:
        for scope in results.scopes:
            hits = results.hits_by_scope.get(scope, [])
            label = (f"{SCOPE_LABELS.get(scope, scope)}  "
                     f"({len(hits)})")
            node = self.tree.insert(
                "", "end", text=label,
                values=("", "", "", ""), open=bool(hits),
                tags=("scope",))
            for h in hits:
                self.tree.insert(
                    node, "end", text="",
                    values=(h.entity_id, h.label,
                             h.sublabel, h.matched_field))
        self.status_var.set(
            f"{results.total} hit(s) for "
            f"{(results.query or '(empty)')!r}  ·  "
            f"{len(results.scopes)} scope(s)")


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
