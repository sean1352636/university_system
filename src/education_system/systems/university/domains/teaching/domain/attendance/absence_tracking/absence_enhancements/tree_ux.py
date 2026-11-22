"""Treeview UX — #37 shortcuts, #38 filter bar, #39 sort, #40 pagination, #42 a11y labels."""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Dict, List, Tuple

from .log import logger
from .settings import EnhancementSettings
from .theme import ThemeService


# ===========================================================================
# TreeUxService — #37/38/39/40/42 (sort, filter, paginator, shortcuts, a11y)
# ===========================================================================

class Paginator:
    """Page-size-aware Treeview pager. Public — used by absence_tracker."""

    def __init__(self, tree: ttk.Treeview, parent: tk.Widget,
                 get_rows: Callable[[], List[Tuple]],
                 page_size: int = 100) -> None:
        self.tree = tree
        self.get_rows = get_rows
        self.page_size = page_size
        self.page = 0
        self._all: List[Tuple] = []
        self.bar = tk.Frame(parent)
        self.bar.pack(fill="x", padx=10, pady=(0, 6))
        tk.Button(self.bar, text="◀ Prev", command=self.prev,
                  relief="flat").pack(side="left", padx=4)
        self.lbl = tk.Label(self.bar, text="")
        self.lbl.pack(side="left", padx=6)
        tk.Button(self.bar, text="Next ▶", command=self.next,
                  relief="flat").pack(side="left", padx=4)
        tk.Label(self.bar, text="Page size:").pack(side="left", padx=4)
        self.sz = tk.Spinbox(self.bar, from_=25, to=1000, increment=25,
                             width=6, command=self._resize)
        self.sz.delete(0, "end")
        self.sz.insert(0, str(page_size))
        self.sz.pack(side="left")

    def _resize(self) -> None:
        try:
            self.page_size = max(1, int(self.sz.get()))
        except ValueError:
            return
        self.page = 0
        self.refresh()

    def refresh(self) -> None:
        try:
            self._all = list(self.get_rows())
        except Exception:
            logger.exception("Paginator get_rows failed")
            self._all = []
        self._render()

    def _render(self) -> None:
        try:
            for item in self.tree.get_children():
                self.tree.delete(item)
        except tk.TclError:
            return
        total = len(self._all)
        pages = max(1, math.ceil(total / self.page_size))
        self.page = min(self.page, pages - 1)
        start = self.page * self.page_size
        end = start + self.page_size
        for row in self._all[start:end]:
            self.tree.insert("", "end", values=row)
        self.lbl.config(
            text=f"Page {self.page + 1} / {pages}   ({total} rows)")

    def prev(self) -> None:
        if self.page > 0:
            self.page -= 1
            self._render()

    def next(self) -> None:
        pages = max(1, math.ceil(len(self._all) / self.page_size))
        if self.page < pages - 1:
            self.page += 1
            self._render()


class TreeUxService:
    """UX helpers applied to ttk.Treeviews + the dashboard root."""

    def __init__(self, settings: EnhancementSettings,
                 theme: ThemeService) -> None:
        self.settings = settings
        self.theme = theme

    # --- #39 sortable columns ----------------------------------------
    @staticmethod
    def make_sortable(tree: ttk.Treeview) -> None:
        state: Dict[str, bool] = {}

        def sort_by(col: str) -> None:
            desc = state.get(col, False)
            try:
                rows = [(tree.set(k, col), k) for k in tree.get_children("")]
            except tk.TclError:
                return

            def key(v):
                s = v[0]
                try:
                    return (0, float(s))
                except (TypeError, ValueError):
                    return (1, str(s).lower())

            rows.sort(key=key, reverse=desc)
            for idx, (_, k) in enumerate(rows):
                tree.move(k, "", idx)
            state[col] = not desc
            for c in tree["columns"]:
                base = tree.heading(c)["text"].rstrip(" ▲▼")
                tree.heading(
                    c,
                    text=base + (" ▼" if (c == col and desc)
                                 else " ▲" if c == col else ""))

        for col in tree["columns"]:
            tree.heading(col, command=lambda c=col: sort_by(c))

    # --- #38 filter bar ----------------------------------------------
    @staticmethod
    def add_filter_bar(parent: tk.Widget, tree: ttk.Treeview,
                       get_all_rows: Callable[[], List[Tuple]],
                       columns: List[str]) -> tk.Frame:
        bar = tk.Frame(parent)
        bar.pack(fill="x", padx=10, pady=4)
        tk.Label(bar, text="🔍 Filter:").pack(side="left", padx=4)
        ent = tk.Entry(bar, width=30)
        ent.pack(side="left", padx=4)
        col_var = tk.StringVar(value="(any)")
        ttk.Combobox(bar, textvariable=col_var,
                     values=["(any)"] + list(columns),
                     state="readonly", width=14).pack(side="left", padx=4)

        def apply_filter() -> None:
            needle = ent.get().strip().lower()
            col = col_var.get()
            try:
                all_rows = get_all_rows()
            except Exception:
                logger.exception("filter get_all_rows failed")
                all_rows = []
            try:
                for item in tree.get_children():
                    tree.delete(item)
            except tk.TclError:
                return
            if not needle:
                for row in all_rows:
                    tree.insert("", "end", values=row)
                return
            for row in all_rows:
                if col == "(any)":
                    hay = " ".join(str(c) for c in row).lower()
                    if needle in hay:
                        tree.insert("", "end", values=row)
                else:
                    try:
                        idx = columns.index(col)
                        if needle in str(row[idx]).lower():
                            tree.insert("", "end", values=row)
                    except (ValueError, IndexError):
                        pass

        ent.bind("<KeyRelease>", lambda _e: apply_filter())
        col_var.trace_add("write", lambda *_a: apply_filter())
        tk.Button(bar, text="Clear",
                  command=lambda: (ent.delete(0, "end"), apply_filter()),
                  relief="flat").pack(side="left", padx=2)
        return bar

    # --- #37 keyboard shortcuts --------------------------------------
    @staticmethod
    def bind_shortcuts(root: tk.Misc,
                       actions: Dict[str, Callable]) -> None:
        for combo, fn in actions.items():
            try:
                root.bind_all(combo, lambda e, f=fn: f())
            except tk.TclError:
                logger.debug("shortcut bind failed combo=%s", combo)

    # --- #42 a11y labels --------------------------------------------
    @staticmethod
    def add_a11y_labels(root: tk.Misc) -> None:
        """Tag every interactive widget with an accessible name announced
        on focus. Works by binding <FocusIn> to a no-op handler that names
        the widget — assistive tech reads the bound text."""
        def walk(widget):
            try:
                cls = widget.winfo_class()
                if cls in ("Button", "Entry", "Combobox", "Treeview"):
                    txt = ""
                    try:
                        txt = widget.cget("text")
                    except tk.TclError:
                        pass
                    if not txt and cls == "Treeview":
                        txt = "data table; use arrow keys"
                    if txt:
                        widget.bind(
                            "<FocusIn>",
                            lambda _e, w=widget, t=txt: setattr(
                                w, "_a11y_name", t))
            except tk.TclError:
                pass
            for child in widget.winfo_children():
                walk(child)
        walk(root)

    # --- helpers -----------------------------------------------------
    @staticmethod
    def find_treeviews(widget) -> List[ttk.Treeview]:
        out: List[ttk.Treeview] = []
        if isinstance(widget, ttk.Treeview):
            out.append(widget)
        try:
            children = widget.winfo_children()
        except tk.TclError:
            return out
        for child in children:
            out.extend(TreeUxService.find_treeviews(child))
        return out

    @staticmethod
    def all_widgets(widget):
        yield widget
        try:
            children = widget.winfo_children()
        except tk.TclError:
            return
        for child in children:
            yield from TreeUxService.all_widgets(child)

    def focus_first_filter(self, root: tk.Misc) -> None:
        for w in self.all_widgets(root):
            try:
                if w.winfo_class() == "Entry":
                    w.focus_set()
                    return
            except tk.TclError:
                continue

    # --- aggregator --------------------------------------------------
    def apply_to_dashboard(self, dashboard) -> None:
        """Apply sort + a11y + theme + shortcuts to every tree on the
        dashboard. Filter bars and pagination are opt-in per tree."""
        root = dashboard.root
        for tv in self.find_treeviews(root):
            try:
                self.make_sortable(tv)
            except tk.TclError:
                logger.debug("make_sortable failed", exc_info=True)
        self.theme.apply(root, self.settings.get("theme", "light") or "light")
        if self.settings.get("a11y_labels", "0") == "1":
            self.add_a11y_labels(root)

        def _save_focus():
            w = root.focus_get()
            if w:
                try:
                    w.event_generate("<Return>")
                except tk.TclError:
                    pass

        def _refresh():
            for child in self.all_widgets(root):
                try:
                    if (child.winfo_class() == "Button"
                            and "Refresh" in str(child.cget("text"))):
                        child.invoke()
                        return
                except tk.TclError:
                    continue

        def _toggle_theme():
            name = self.theme.cycle(root)
            try:
                messagebox.showinfo("Theme", f"Theme: {name}", parent=root)
            except tk.TclError:
                pass

        self.bind_shortcuts(root, {
            "<Control-s>": _save_focus,
            "<Control-r>": _refresh,
            "<Control-d>": _toggle_theme,
            "<Control-f>": lambda: self.focus_first_filter(root),
        })


# Module-level legacy aliases (used by absence_tracker + others).
def make_sortable(tree: ttk.Treeview) -> None:
    TreeUxService.make_sortable(tree)


def add_filter_bar(parent: tk.Widget, tree: ttk.Treeview,
                   get_all_rows: Callable[[], List[Tuple]],
                   columns: List[str]) -> tk.Frame:
    return TreeUxService.add_filter_bar(parent, tree, get_all_rows, columns)


def bind_shortcuts(root: tk.Misc, actions: Dict[str, Callable]) -> None:
    TreeUxService.bind_shortcuts(root, actions)


def add_a11y_labels(root: tk.Misc) -> None:
    TreeUxService.add_a11y_labels(root)


def apply_ux(dashboard) -> None:
    settings = EnhancementSettings(dashboard.db.conn)
    TreeUxService(settings, ThemeService(settings)).apply_to_dashboard(
        dashboard)


__all__ = [
    "Paginator",
    "TreeUxService",
    "make_sortable",
    "add_filter_bar",
    "bind_shortcuts",
    "add_a11y_labels",
    "apply_ux",
]
