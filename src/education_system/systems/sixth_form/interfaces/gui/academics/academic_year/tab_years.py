"""Years tab of the Sixth Form Academic Year window.

Split out of ``academic_year_views`` (2026-10-22); that module
re-exports every name defined here.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Callable
from education_system.systems.sixth_form.domain.academics.academic_year import (
    academic_year as data,
)
from education_system.systems.sixth_form.domain.academics.academic_year.academic_year import (
    AcademicYear,
    ValidationError,
    YEAR_STATUSES,
)
from ._common import logger


# ══ Years tab ═════════════════════════════════════════════════════

_SORT_KEYS: dict[str, Callable[[AcademicYear], object]] = {
    "id":      lambda y: y.year_id,
    "name":    lambda y: y.name.lower(),
    "start":   lambda y: y.start_date,
    "end":     lambda y: y.end_date,
    "days":    lambda y: y.day_count,
    "status":  lambda y: y.status,
    "current": lambda y: (0 if y.is_current else 1),
}


class YearsTab:
    def __init__(self, nb: ttk.Notebook, state: dict,
                  *, goto_tab: Callable[[int], None] | None = None) -> None:
        self.state = state
        self.goto_tab = goto_tab
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Years")
        self._sort_col: str = "start"
        self._sort_reverse: bool = True
        self._build()
        self.refresh()

    def _build(self) -> None:
        # Yellow banner — shown only when there's no current year.
        self.banner = tk.Label(
            self.frame, text="", bg="#fff3b0", fg="#5a4a00",
            anchor="w", padx=10, pady=4)
        # packed/unpacked dynamically in refresh()

        # Filter bar — search + status filter.
        filt = ttk.Frame(self.frame)
        filt.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(filt, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write",
                                    lambda *_: self._render_rows())
        ttk.Entry(filt, textvariable=self.search_var,
                   width=24).pack(side="left", padx=(2, 12))
        ttk.Label(filt, text="Status:").pack(side="left")
        self.status_cb = ttk.Combobox(
            filt, values=("All",) + YEAR_STATUSES,
            state="readonly", width=12)
        self.status_cb.current(0)
        self.status_cb.bind("<<ComboboxSelected>>",
                              lambda _e: self._render_rows())
        self.status_cb.pack(side="left", padx=(2, 12))
        ttk.Label(filt, text="Year range:").pack(side="left")
        self.from_e = ttk.Entry(filt, width=12)
        self.from_e.pack(side="left", padx=(2, 4))
        ttk.Label(filt, text="to").pack(side="left")
        self.to_e = ttk.Entry(filt, width=12)
        self.to_e.pack(side="left", padx=(2, 4))
        ttk.Button(filt, text="Apply",
                    command=self._render_rows).pack(side="left", padx=4)
        ttk.Button(filt, text="Clear",
                    command=self._clear_filters).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=(4, 4))
        cols = ("id", "name", "start", "end", "days",
                "status", "current")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        self._headings = {"id": "ID", "name": "Name",
                           "start": "Start", "end": "End",
                           "days": "Days", "status": "Status",
                           "current": "Current"}
        widths = {"id": 60, "name": 120, "start": 110, "end": 110,
                  "days": 70, "status": 110, "current": 80}
        for c in cols:
            self.tree.heading(
                c, text=self._headings[c],
                command=lambda _c=c: self._sort_by(_c))
            anchor = "center" if c in ("days", "current") else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("current", background="#d8f4d8")
        self.tree.tag_configure("Active", background="#eef7ff")
        self.tree.tag_configure("Archived", background="#eeeeee")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())
        # Right-click context menu (Button-3 on X11, Button-2 on macOS).
        self.tree.bind("<Button-3>", self._on_right_click)
        self.tree.bind("<Button-2>", self._on_right_click)

        self.menu = tk.Menu(self.frame, tearoff=False)
        self.menu.add_command(label="Edit",
                                 command=self._edit_selected)
        self.menu.add_command(label="Set current",
                                 command=self._set_current)
        self.menu.add_command(label="Duplicate (+1 year)",
                                 command=self._duplicate_selected)
        self.menu.add_separator()
        self.menu.add_command(label="Archive",
                                 command=lambda: self._set_status("Archived"))
        self.menu.add_command(label="Unarchive (→ Active)",
                                 command=lambda: self._set_status("Active"))
        self.menu.add_separator()
        self.menu.add_command(label="Open Terms",
                                 command=lambda: self._open_tab(1))
        self.menu.add_command(label="Open Breaks",
                                 command=lambda: self._open_tab(2))
        self.menu.add_separator()
        self.menu.add_command(label="Delete",
                                 command=self._delete_selected)

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(bar, text="New",
                    command=self._new).pack(side="left")
        ttk.Button(bar, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Set current",
                    command=self._set_current).pack(side="left", padx=4)
        ttk.Button(bar, text="Duplicate",
                    command=self._duplicate_selected).pack(side="left",
                                                              padx=4)
        ttk.Button(bar, text="Archive",
                    command=lambda: self._set_status("Archived")).pack(
            side="left", padx=4)
        ttk.Button(bar, text="Unarchive",
                    command=lambda: self._set_status("Active")).pack(
            side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Separator(bar, orient="vertical").pack(side="left",
                                                       fill="y", padx=8)
        ttk.Button(bar, text="Open Terms »",
                    command=lambda: self._open_tab(1)).pack(side="left",
                                                              padx=2)
        ttk.Button(bar, text="Open Breaks »",
                    command=lambda: self._open_tab(2)).pack(side="left",
                                                              padx=2)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    # ── Banner / data load ──────────────────────────────────────

    def _show_banner(self, text: str) -> None:
        self.banner.configure(text=text)
        if not self.banner.winfo_ismapped():
            self.banner.pack(fill="x", before=self.frame.winfo_children()[0]
                              if self.frame.winfo_children() else None)

    def _hide_banner(self) -> None:
        if self.banner.winfo_ismapped():
            self.banner.pack_forget()

    def refresh(self) -> None:
        self._all_rows: list[AcademicYear] = data.list_years()
        self._render_rows()
        # Auto-select the current year if nothing selected.
        if self.state.get("selected_year_id") is None:
            cur = data.current_year()
            if cur is not None:
                self.state["selected_year_id"] = cur.year_id
                try:
                    self.tree.selection_set(str(cur.year_id))
                except tk.TclError:
                    pass

    # ── Filtering / sorting / rendering ─────────────────────────

    def _clear_filters(self) -> None:
        self.search_var.set("")
        self.status_cb.current(0)
        self.from_e.delete(0, "end")
        self.to_e.delete(0, "end")
        self._render_rows()

    def _sort_by(self, col: str) -> None:
        if col not in _SORT_KEYS:
            return
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False
        for c, label in self._headings.items():
            arrow = ""
            if c == self._sort_col:
                arrow = "  ▼" if self._sort_reverse else "  ▲"
            self.tree.heading(c, text=label + arrow)
        self._render_rows()

    def _filter_rows(self) -> list[AcademicYear]:
        rows = list(self._all_rows)
        q = self.search_var.get().strip().lower()
        if q:
            rows = [r for r in rows
                     if q in r.name.lower()
                     or q in r.status.lower()
                     or q in r.start_date
                     or q in r.end_date]
        st = self.status_cb.get()
        if st and st != "All":
            rows = [r for r in rows if r.status == st]
        frm = self.from_e.get().strip()
        to = self.to_e.get().strip()
        if frm:
            rows = [r for r in rows if r.end_date >= frm]
        if to:
            rows = [r for r in rows if r.start_date <= to]
        key = _SORT_KEYS.get(self._sort_col, _SORT_KEYS["start"])
        rows.sort(key=key, reverse=self._sort_reverse)
        return rows

    def _render_rows(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = self._filter_rows()
        for y in rows:
            tags = []
            if y.is_current:
                tags.append("current")
            if y.status in ("Active", "Archived"):
                tags.append(y.status)
            self.tree.insert("", "end", iid=str(y.year_id), values=(
                y.year_id, y.name, y.start_date, y.end_date,
                y.day_count, y.status, "✓" if y.is_current else "",
            ), tags=tuple(tags))

        total = len(self._all_rows)
        shown = len(rows)
        cur = sum(1 for r in self._all_rows if r.is_current)
        act = sum(1 for r in self._all_rows if r.status == "Active")
        arch = sum(1 for r in self._all_rows if r.status == "Archived")
        plan = sum(1 for r in self._all_rows if r.status == "Planning")
        suffix = "" if shown == total else f"  (showing {shown})"
        self.count_var.set(
            f"{total} year(s) — {cur} current, {act} active, "
            f"{plan} planning, {arch} archived.{suffix}")

        if cur == 0 and total > 0:
            self._show_banner(
                "⚠  No academic year is flagged as current — "
                "select a row and click ‘Set current’.")
        else:
            self._hide_banner()

    # ── Selection / context menu ────────────────────────────────

    def _on_select(self, _evt=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        try:
            self.state["selected_year_id"] = int(sel[0])
        except ValueError:
            pass

    def _on_right_click(self, event: tk.Event) -> None:
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self._on_select()
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    # ── Actions ─────────────────────────────────────────────────

    def _new(self) -> None:
        YearDialog(self.frame.winfo_toplevel(),
                    existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        yid = self._selected_id()
        if yid is None:
            messagebox.showinfo("Edit", "Select a year first.")
            return
        existing = data.get_year(yid)
        if existing is None:
            return
        YearDialog(self.frame.winfo_toplevel(),
                    existing=existing, on_save=self.refresh)

    def _set_current(self) -> None:
        yid = self._selected_id()
        if yid is None:
            messagebox.showinfo("Current", "Select a year first.")
            return
        try:
            data.set_current(yid)
        except ValidationError as e:
            messagebox.showerror("Current", str(e))
            return
        self.refresh()

    def _set_status(self, new_status: str) -> None:
        yid = self._selected_id()
        if yid is None:
            messagebox.showinfo("Status", "Select a year first.")
            return
        existing = data.get_year(yid)
        if existing is None:
            return
        if existing.status == new_status:
            return
        try:
            data.update_year(yid, {"status": new_status})
        except (ValidationError, Exception) as e:
            messagebox.showerror("Status change failed", str(e))
            return
        self.refresh()

    def _duplicate_selected(self) -> None:
        yid = self._selected_id()
        if yid is None:
            messagebox.showinfo("Duplicate", "Select a year first.")
            return
        src = data.get_year(yid)
        if src is None:
            return
        try:
            new_name = _bump_year_name(src.name)
            new_start = _shift_iso(src.start_date, 365)
            new_end = _shift_iso(src.end_date, 365)
        except Exception as e:
            messagebox.showerror("Duplicate failed", str(e))
            return
        if not messagebox.askyesno(
                "Duplicate",
                f"Create new year {new_name!r}\n"
                f"({new_start} → {new_end})\n"
                f"with all terms and breaks shifted by +365 days?"):
            return
        try:
            new_year = data.create_year({
                "name": new_name,
                "start_date": new_start,
                "end_date": new_end,
                "status": "Planning",
                "is_current": False,
                "notes": src.notes,
            })
            for t in data.list_terms(year_id=src.year_id):
                try:
                    data.create_term({
                        "year_id": new_year.year_id,
                        "name": t.name,
                        "start_date": _shift_iso(t.start_date, 365),
                        "end_date": _shift_iso(t.end_date, 365),
                        "notes": t.notes,
                    })
                except ValidationError as e:
                    logger.warning("Skipped duplicating term %r: %s",
                                    t.name, e)
            for b in data.list_breaks(year_id=src.year_id):
                try:
                    data.create_break({
                        "year_id": new_year.year_id,
                        "name": b.name,
                        "type": b.type,
                        "start_date": _shift_iso(b.start_date, 365),
                        "end_date": _shift_iso(b.end_date, 365),
                        "notes": b.notes,
                    })
                except ValidationError as e:
                    logger.warning("Skipped duplicating break %r: %s",
                                    b.name, e)
            self.state["selected_year_id"] = new_year.year_id
        except (ValidationError, Exception) as e:
            messagebox.showerror("Duplicate failed", str(e))
            return
        self.refresh()

    def _open_tab(self, idx: int) -> None:
        yid = self._selected_id()
        if yid is not None:
            self.state["selected_year_id"] = yid
        if self.goto_tab is not None:
            self.goto_tab(idx)

    def _delete_selected(self) -> None:
        yid = self._selected_id()
        if yid is None:
            messagebox.showinfo("Delete", "Select a year first.")
            return
        y = data.get_year(yid)
        if y is None:
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete year #{yid} {y.name!r}?\n"
                "Soft-delete — Ctrl-Z to undo."):
            return
        try:
            data.delete_year(yid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        undo = self.state.get("_undo")
        if undo is not None:
            undo.push(f"delete year #{yid}",
                       lambda i=yid: data.restore_year(i))
        toaster = self.state.get("_toast")
        if toaster:
            toaster(f"Deleted year #{yid} — Ctrl-Z to undo",
                      kind="warn")
        if self.state.get("selected_year_id") == yid:
            self.state["selected_year_id"] = None
        self.refresh()


# Sibling names used only at call time; imported last so any import order works.
from .dialogs import YearDialog  # noqa: E402
from education_system.systems.sixth_form.domain.academics.academic_year.planning import (  # noqa: E402
    _bump_year_name,
    _shift_iso,
)
