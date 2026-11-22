"""Saved searches tab, History tab and the saved-search editor dialog.

Moved verbatim from ``advanced_search_views``.
"""

from __future__ import annotations

from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Callable
from education_system.systems.sixth_form.domain.learners.advanced_search import (
    history as search_history,
)
from education_system.systems.sixth_form.domain.learners.advanced_search.models import (
    ALL_SCOPES,
    SavedSearch,
    SCOPE_LABELS,
    ValidationError,
)
from ._widgets import _add_page
from .search_tab import SearchTab


# ══ Saved searches tab ═════════════════════════════════════════════

class SavedTab:
    def __init__(self, nb: ttk.Notebook, search_tab: SearchTab) -> None:
        self.search_tab = search_tab
        self.frame = ttk.Frame(nb)
        _add_page(nb, self.frame, "Saved Searches", "Library")
        self._build()
        self.refresh()

    def _build(self) -> None:
        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        cols = ("id", "name", "query", "scopes", "owner", "shared",
                "folder", "notes")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings")
        widths = {"id": 50, "name": 170, "query": 170, "scopes": 220,
                  "owner": 100, "shared": 90, "folder": 100, "notes": 200}
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
        rows = search_history.list_saved_searches()
        for s in rows:
            scopes = ", ".join(s.scopes) if s.scopes else "(all)"
            shared = s.visibility
            if s.visibility == "role" and s.role_acl:
                shared = "roles: " + ", ".join(s.role_acl)
            self.tree.insert("", "end", iid=str(s.saved_id), values=(
                s.saved_id, s.name, s.query or "(empty)",
                scopes, s.owner_actor or "—", shared, s.folder or "",
                s.notes or "",
            ))
        self.count_var.set(f"{len(rows)} saved search(es) you can use.")

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
        s = search_history.get_saved_search(sid)
        if s is None:
            return
        # Switch to the Search tab and run the saved query with the
        # filters it was saved with.
        nb = self.frame.master
        if hasattr(nb, "select"):
            nb.select(0)
        self.search_tab.load_query(s.query, s.scopes or None,
                                   filters=s.filters or {})

    def _new(self) -> None:
        SavedDialog(self.frame.winfo_toplevel(),
                     existing=None, on_save=self.refresh,
                     current_filters=self.search_tab.current_filters(),
                     current_query=self.search_tab.query_e.get().strip())

    def _edit_selected(self) -> None:
        sid = self._selected_id()
        if sid is None:
            messagebox.showinfo("Edit", "Select a saved search first.")
            return
        existing = search_history.get_saved_search(sid)
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
            search_history.delete_saved_search(sid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ History tab ════════════════════════════════════════════════════

class HistoryTab:
    def __init__(self, nb: ttk.Notebook, search_tab: SearchTab) -> None:
        self.search_tab = search_tab
        self.frame = ttk.Frame(nb)
        _add_page(nb, self.frame, "History", "Library")
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
        rows = search_history.list_history(limit=50)    # your own searches
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
        rows = search_history.list_history(limit=50)
        match = next((h for h in rows if h.history_id == hid), None)
        if match is None:
            return
        nb = self.frame.master
        if hasattr(nb, "select"):
            nb.select(0)
        self.search_tab.load_query(match.query, match.scopes or None)

    def _clear(self) -> None:
        if not messagebox.askyesno("Clear",
                                     "Clear your search history?"):
            return
        n = search_history.clear_history()
        messagebox.showinfo("Clear", f"Cleared {n} entry/entries.")
        self.refresh()


# ══ Dialogs ════════════════════════════════════════════════════════

class SavedDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: SavedSearch | None,
                 on_save: Callable[[], None],
                 current_filters: dict | None = None,
                 current_query: str = "") -> None:
        self.existing = existing
        self.on_save = on_save
        self._current_filters = current_filters or {}
        self._current_query = current_query
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Saved Search" if existing
                          else "New Saved Search")
        self.win.transient(parent)
        grab_when_viewable(self.win)
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
        elif self._current_query:
            self.query_e.insert(0, self._current_query)
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
        self.notes_t = tk.Text(form, width=40, height=3)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=3, column=1, sticky="w", padx=6)

        ex = self.existing
        ttk.Label(form, text="Shared with:").grid(row=4, column=0,
                                                  sticky="e", pady=4)
        share = ttk.Frame(form)
        share.grid(row=4, column=1, sticky="w", padx=6)
        self.vis_var = tk.StringVar(value=(ex.visibility if ex else "private"))
        for value, text in (("private", "Only me"), ("role", "These roles"),
                            ("public", "All staff")):
            ttk.Radiobutton(share, text=text, value=value,
                            variable=self.vis_var).pack(side="left",
                                                        padx=(0, 8))
        ttk.Label(form, text="Roles:").grid(row=5, column=0, sticky="e",
                                            pady=4)
        self.roles_e = ttk.Entry(form, width=40)
        if ex and ex.role_acl:
            self.roles_e.insert(0, ", ".join(ex.role_acl))
        self.roles_e.grid(row=5, column=1, sticky="w", padx=6)
        ttk.Label(form, text="e.g. Tutor, Head of Year, SENCO (comma-separated)",
                  foreground="#666").grid(row=6, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Folder:").grid(row=7, column=0, sticky="e",
                                             pady=4)
        self.folder_e = ttk.Combobox(
            form, width=38, values=search_history.list_saved_folders())
        if ex and ex.folder:
            self.folder_e.set(ex.folder)
        self.folder_e.grid(row=7, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Tags:").grid(row=8, column=0, sticky="e",
                                           pady=4)
        self.tags_e = ttk.Entry(form, width=40)
        if ex and ex.tags:
            self.tags_e.insert(0, ", ".join(ex.tags))
        self.tags_e.grid(row=8, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Filters:").grid(row=9, column=0, sticky="ne",
                                              pady=4)
        self._filters = dict(ex.filters) if ex else dict(self._current_filters)
        filt_row = ttk.Frame(form)
        filt_row.grid(row=9, column=1, sticky="w", padx=6)
        self.filters_var = tk.StringVar(value=self._filters_text())
        ttk.Label(filt_row, textvariable=self.filters_var, wraplength=300,
                  justify="left").pack(side="left")
        ttk.Button(filt_row, text="Clear",
                   command=self._clear_filters).pack(side="left", padx=6)
        if ex and ex.owner_actor:
            ttk.Label(form, text=f"Owner: {ex.owner_actor}",
                      foreground="#666").grid(row=10, column=1, sticky="w",
                                              padx=6)

        bar = ttk.Frame(form)
        bar.grid(row=11, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _filters_text(self) -> str:
        if not self._filters:
            return "(none)"
        return ", ".join(f"{k}={v}" for k, v in sorted(self._filters.items()))

    def _clear_filters(self) -> None:
        self._filters = {}
        self.filters_var.set(self._filters_text())

    def _save(self) -> None:
        scopes = [k for k, v in self._scope_vars.items() if v.get()]
        payload = {
            "name":   self.name_e.get().strip(),
            "query":  self.query_e.get().strip(),
            "scopes": scopes or list(ALL_SCOPES),
            "notes":  self.notes_t.get("1.0", "end").strip(),
            "filters": self._filters,
            "visibility": self.vis_var.get(),
            "role_acl": self.roles_e.get().strip(),
            "folder": self.folder_e.get().strip(),
            "tags": self.tags_e.get().strip(),
        }
        if payload["visibility"] == "role" and not payload["role_acl"]:
            messagebox.showerror("Save failed",
                                 "List the roles to share it with.")
            return
        try:
            if self.existing:
                search_history.update_saved_search(self.existing.saved_id, payload)
            else:
                search_history.create_saved_search(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
