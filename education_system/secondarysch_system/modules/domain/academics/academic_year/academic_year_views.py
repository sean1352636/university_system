"""Tkinter views for Sixth Form Academic Year.

Notebook with 4 tabs:
* Years     — table of academic years, set-current, CRUD.
* Terms     — terms for the selected year.
* Breaks    — holidays / INSET / etc. for the selected year.
* Calendar  — date lookup + year summary.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from education_system.shared import branding
from education_system.secondarysch_system.modules.domain.academics.academic_year import (
    academic_year as data,
)
from education_system.secondarysch_system.modules.domain.academics.academic_year.academic_year import (
    AcademicYear,
    Break,
    BREAK_TYPES,
    DEFAULT_BREAK_TYPE,
    DEFAULT_TERM_NAME,
    DEFAULT_YEAR_STATUS,
    Term,
    TERM_NAMES,
    ValidationError,
    YEAR_STATUSES,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)


def open_academic_year_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Academic Year — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    state: dict = {"selected_year_id": None}

    years_tab = YearsTab(nb, state)
    terms_tab = TermsTab(nb, state)
    breaks_tab = BreaksTab(nb, state)
    calendar_tab = CalendarTab(nb, state)

    def _on_change(_evt=None) -> None:
        # When a child tab is activated, refresh against the latest
        # selected_year_id (set by the Years tab when the user
        # clicks a row).
        idx = nb.index("current")
        if idx == 1:
            terms_tab.refresh()
        elif idx == 2:
            breaks_tab.refresh()
        elif idx == 3:
            calendar_tab.refresh()

    nb.bind("<<NotebookTabChanged>>", _on_change)


def _today() -> str:
    return _dt.date.today().isoformat()


# ══ Years tab ═════════════════════════════════════════════════════

class YearsTab:
    def __init__(self, nb: ttk.Notebook, state: dict) -> None:
        self.state = state
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Years")
        self._build()
        self.refresh()

    def _build(self) -> None:
        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        cols = ("id", "name", "start", "end", "days",
                "status", "current")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        headings = {"id": "ID", "name": "Name",
                    "start": "Start", "end": "End",
                    "days": "Days", "status": "Status",
                    "current": "Current"}
        widths = {"id": 60, "name": 120, "start": 110, "end": 110,
                  "days": 70, "status": 110, "current": 80}
        for c in cols:
            self.tree.heading(c, text=headings[c])
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
        ttk.Button(bar, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = data.list_years()
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
        self.count_var.set(f"{len(rows)} year(s).")
        # Auto-select the current year if nothing selected.
        if self.state.get("selected_year_id") is None:
            cur = data.current_year()
            if cur is not None:
                self.state["selected_year_id"] = cur.year_id
                try:
                    self.tree.selection_set(str(cur.year_id))
                except tk.TclError:
                    pass

    def _on_select(self, _evt=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        try:
            self.state["selected_year_id"] = int(sel[0])
        except ValueError:
            pass

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

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
                "Also wipes its terms and breaks."):
            return
        try:
            data.delete_year(yid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        if self.state.get("selected_year_id") == yid:
            self.state["selected_year_id"] = None
        self.refresh()


# ══ Terms tab ═════════════════════════════════════════════════════

class TermsTab:
    def __init__(self, nb: ttk.Notebook, state: dict) -> None:
        self.state = state
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Terms")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Year:").pack(side="left")
        self.year_cb = ttk.Combobox(bar, state="readonly", width=40)
        self.year_cb.pack(side="left", padx=(2, 10))
        self.year_cb.bind("<<ComboboxSelected>>",
                           lambda _e: self._on_year_change())
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "name", "start", "end", "days")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        headings = {"id": "ID", "name": "Name", "start": "Start",
                    "end": "End", "days": "Days"}
        widths = {"id": 60, "name": 180, "start": 130, "end": 130,
                  "days": 80}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c == "days" else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="New",
                    command=self._new).pack(side="left")
        ttk.Button(actions, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)

    def _year_options(self) -> list[tuple[int, str]]:
        years = data.list_years()
        return [(y.year_id, f"#{y.year_id} {y.name}"
                            f"{' *' if y.is_current else ''}")
                for y in years]

    def _on_year_change(self) -> None:
        idx = self.year_cb.current()
        if idx < 0:
            return
        self.state["selected_year_id"] = self._year_ids[idx]
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        opts = self._year_options()
        self._year_ids = [yid for yid, _ in opts]
        labels = [lbl for _, lbl in opts]
        self.year_cb["values"] = labels

        if not opts:
            self.count_var.set("No academic years configured.")
            return

        target = self.state.get("selected_year_id") or self._year_ids[0]
        try:
            idx = self._year_ids.index(target)
        except ValueError:
            idx = 0
            target = self._year_ids[0]
        self.year_cb.current(idx)
        self.state["selected_year_id"] = target

        rows = data.list_terms(year_id=target)
        for t in rows:
            self.tree.insert("", "end", iid=str(t.term_id), values=(
                t.term_id, t.name, t.start_date, t.end_date,
                t.day_count,
            ))
        self.count_var.set(f"{len(rows)} term(s).")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _current_year(self) -> AcademicYear | None:
        yid = self.state.get("selected_year_id")
        if yid is None:
            return None
        return data.get_year(yid)

    def _new(self) -> None:
        year = self._current_year()
        if year is None:
            messagebox.showinfo("New", "Pick a year first.")
            return
        TermDialog(self.frame.winfo_toplevel(), year=year,
                    existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        tid = self._selected_id()
        if tid is None:
            messagebox.showinfo("Edit", "Select a term first.")
            return
        existing = data.get_term(tid)
        if existing is None:
            return
        year = data.get_year(existing.year_id)
        if year is None:
            return
        TermDialog(self.frame.winfo_toplevel(), year=year,
                    existing=existing, on_save=self.refresh)

    def _delete_selected(self) -> None:
        tid = self._selected_id()
        if tid is None:
            messagebox.showinfo("Delete", "Select a term first.")
            return
        if not messagebox.askyesno("Delete", f"Delete term #{tid}?"):
            return
        try:
            data.delete_term(tid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ Breaks tab ═════════════════════════════════════════════════════

class BreaksTab:
    def __init__(self, nb: ttk.Notebook, state: dict) -> None:
        self.state = state
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Breaks")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Year:").pack(side="left")
        self.year_cb = ttk.Combobox(bar, state="readonly", width=40)
        self.year_cb.pack(side="left", padx=(2, 10))
        self.year_cb.bind("<<ComboboxSelected>>",
                           lambda _e: self._on_year_change())
        ttk.Label(bar, text="Type:").pack(side="left")
        self.type_cb = ttk.Combobox(bar, values=("",) + BREAK_TYPES,
                                       state="readonly", width=14)
        self.type_cb.current(0)
        self.type_cb.bind("<<ComboboxSelected>>",
                            lambda _e: self.refresh())
        self.type_cb.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "name", "type", "start", "end", "days")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        headings = {"id": "ID", "name": "Name", "type": "Type",
                    "start": "Start", "end": "End", "days": "Days"}
        widths = {"id": 60, "name": 220, "type": 110, "start": 110,
                  "end": 110, "days": 70}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c == "days" else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("INSET", background="#fff7d0")
        self.tree.tag_configure("Holiday", background="#eef7ff")
        self.tree.tag_configure("Half-Term", background="#eef7ff")
        self.tree.tag_configure("Bank Holiday", background="#ffe6d0")
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(actions, text="New",
                    command=self._new).pack(side="left")
        ttk.Button(actions, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)

    def _year_options(self) -> list[tuple[int, str]]:
        years = data.list_years()
        return [(y.year_id, f"#{y.year_id} {y.name}"
                            f"{' *' if y.is_current else ''}")
                for y in years]

    def _on_year_change(self) -> None:
        idx = self.year_cb.current()
        if idx < 0:
            return
        self.state["selected_year_id"] = self._year_ids[idx]
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        opts = self._year_options()
        self._year_ids = [yid for yid, _ in opts]
        labels = [lbl for _, lbl in opts]
        self.year_cb["values"] = labels

        if not opts:
            self.count_var.set("No academic years configured.")
            return

        target = self.state.get("selected_year_id") or self._year_ids[0]
        try:
            idx = self._year_ids.index(target)
        except ValueError:
            idx = 0
            target = self._year_ids[0]
        self.year_cb.current(idx)
        self.state["selected_year_id"] = target

        btype = self.type_cb.get() or None
        try:
            rows = data.list_breaks(year_id=target, type=btype)
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return
        for b in rows:
            tags = (b.type,) if b.type in (
                "INSET", "Holiday", "Half-Term", "Bank Holiday") else ()
            self.tree.insert("", "end", iid=str(b.break_id), values=(
                b.break_id, b.name, b.type, b.start_date, b.end_date,
                b.day_count,
            ), tags=tags)
        self.count_var.set(f"{len(rows)} break(s).")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _current_year(self) -> AcademicYear | None:
        yid = self.state.get("selected_year_id")
        if yid is None:
            return None
        return data.get_year(yid)

    def _new(self) -> None:
        year = self._current_year()
        if year is None:
            messagebox.showinfo("New", "Pick a year first.")
            return
        BreakDialog(self.frame.winfo_toplevel(), year=year,
                     existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        bid = self._selected_id()
        if bid is None:
            messagebox.showinfo("Edit", "Select a break first.")
            return
        existing = data.get_break(bid)
        if existing is None:
            return
        year = data.get_year(existing.year_id)
        if year is None:
            return
        BreakDialog(self.frame.winfo_toplevel(), year=year,
                     existing=existing, on_save=self.refresh)

    def _delete_selected(self) -> None:
        bid = self._selected_id()
        if bid is None:
            messagebox.showinfo("Delete", "Select a break first.")
            return
        if not messagebox.askyesno("Delete", f"Delete break #{bid}?"):
            return
        try:
            data.delete_break(bid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        self.refresh()


# ══ Calendar tab ═════════════════════════════════════════════════

class CalendarTab:
    """Date-lookup + year summary. Pick a year, pick a date, see what
    it is (term/break/weekend), and read totals."""

    def __init__(self, nb: ttk.Notebook, state: dict) -> None:
        self.state = state
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Calendar")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Year:").pack(side="left")
        self.year_cb = ttk.Combobox(bar, state="readonly", width=40)
        self.year_cb.pack(side="left", padx=(2, 10))
        self.year_cb.bind("<<ComboboxSelected>>",
                           lambda _e: self._on_year_change())
        ttk.Label(bar, text="Date:").pack(side="left")
        self.date_e = ttk.Entry(bar, width=14)
        self.date_e.insert(0, _today())
        self.date_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Look up",
                    command=self._lookup).pack(side="left")

        self.text = tk.Text(self.frame, wrap="none", height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.configure(state="disabled")

    def _year_options(self) -> list[tuple[int, str]]:
        years = data.list_years()
        return [(y.year_id, f"#{y.year_id} {y.name}"
                            f"{' *' if y.is_current else ''}")
                for y in years]

    def _on_year_change(self) -> None:
        idx = self.year_cb.current()
        if idx < 0:
            return
        self.state["selected_year_id"] = self._year_ids[idx]
        self._render_summary()

    def refresh(self) -> None:
        opts = self._year_options()
        self._year_ids = [yid for yid, _ in opts]
        labels = [lbl for _, lbl in opts]
        self.year_cb["values"] = labels
        if not opts:
            self._write("No academic years configured.")
            return
        target = self.state.get("selected_year_id") or self._year_ids[0]
        try:
            idx = self._year_ids.index(target)
        except ValueError:
            idx = 0
            target = self._year_ids[0]
        self.year_cb.current(idx)
        self.state["selected_year_id"] = target
        self._render_summary()

    def _lookup(self) -> None:
        yid = self.state.get("selected_year_id")
        if yid is None:
            messagebox.showinfo("Lookup", "Pick a year first.")
            return
        s = self.date_e.get().strip()
        try:
            term = data.find_term_on(yid, s)
            brk = data.is_break(yid, s)
            d = _dt.date.fromisoformat(s)
        except (ValidationError, ValueError) as e:
            messagebox.showerror("Lookup", str(e))
            return
        lines: list[str] = []
        lines.append(f"Date    : {s} ({d.strftime('%A')})")
        lines.append(f"Term    : "
                     f"{term.name if term else '— (outside any term)'}")
        if brk:
            lines.append(f"Break   : {brk.name} ({brk.type})")
        elif d.weekday() >= 5:
            lines.append("Status  : Weekend (non-teaching)")
        else:
            lines.append("Status  : Teaching day")
        lines.append("")
        lines.append("─" * 50)
        self._render_summary(prepend="\n".join(lines))

    def _render_summary(self, *, prepend: str = "") -> None:
        yid = self.state.get("selected_year_id")
        if yid is None:
            self._write(prepend or "No year selected.")
            return
        try:
            summ = data.year_summary(yid)
        except ValidationError as e:
            self._write(str(e))
            return
        y = summ.year
        lines: list[str] = []
        if prepend:
            lines.append(prepend)
            lines.append("")
        lines.append(f"#{y.year_id}  {y.name}  "
                     f"({y.start_date} → {y.end_date})")
        lines.append(f"Status            : {y.status}"
                     f"{'  (current)' if y.is_current else ''}")
        lines.append(f"Total days        : {y.day_count}")
        lines.append(f"Teaching days     : {summ.teaching_days}")
        lines.append(f"Non-teaching days : {summ.non_teaching_days}")
        lines.append(f"Weekend days      : {summ.weekend_days}")
        lines.append("")
        lines.append(f"Terms ({len(summ.terms)}):")
        for t in summ.terms:
            lines.append(f"  #{t.term_id:>3}  {t.name:<14}  "
                         f"{t.start_date} → {t.end_date}  "
                         f"({t.day_count} days)")
        lines.append("")
        lines.append(f"Breaks ({len(summ.breaks)}):")
        for b in summ.breaks:
            lines.append(f"  #{b.break_id:>3}  {b.name:<22}  "
                         f"{b.start_date} → {b.end_date}  "
                         f"({b.day_count} days, {b.type})")
        self._write("\n".join(lines))

    def _write(self, text: str) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.configure(state="disabled")


# ══ Dialogs ═══════════════════════════════════════════════════════

class YearDialog:
    def __init__(self, parent: tk.Misc, *,
                 existing: AcademicYear | None,
                 on_save: Callable[[], None]) -> None:
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Year" if existing else "New Year")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0

        ttk.Label(form, text="Name:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.name_e = ttk.Entry(form, width=22)
        if self.existing:
            self.name_e.insert(0, self.existing.name)
        self.name_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Start date:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.start_e = ttk.Entry(form, width=14)
        if self.existing:
            self.start_e.insert(0, self.existing.start_date)
        self.start_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="End date:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.end_e = ttk.Entry(form, width=14)
        if self.existing:
            self.end_e.insert(0, self.existing.end_date)
        self.end_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.status_cb = ttk.Combobox(form, values=YEAR_STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_YEAR_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        self.current_var = tk.BooleanVar(
            value=(self.existing.is_current if self.existing else False))
        ttk.Checkbutton(form, text="Flag as current year",
                          variable=self.current_var).grid(
            row=r, column=1, sticky="w", padx=6, pady=2)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=44, height=4)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        payload = {
            "name":       self.name_e.get().strip(),
            "start_date": self.start_e.get().strip(),
            "end_date":   self.end_e.get().strip(),
            "status":     self.status_cb.get().strip(),
            "is_current": self.current_var.get(),
            "notes":      self.notes_t.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_year(self.existing.year_id, payload)
            else:
                data.create_year(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class TermDialog:
    def __init__(self, parent: tk.Misc, *,
                 year: AcademicYear,
                 existing: Term | None,
                 on_save: Callable[[], None]) -> None:
        self.year = year
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Term" if existing else "New Term")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0

        ttk.Label(form,
                   text=f"Year: #{self.year.year_id} {self.year.name}  "
                         f"({self.year.start_date} → {self.year.end_date})"
                   ).grid(row=r, column=0, columnspan=2,
                           sticky="w", pady=(0, 8))

        r += 1
        ttk.Label(form, text="Name:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.name_cb = ttk.Combobox(form, values=TERM_NAMES, width=20)
        self.name_cb.set(self.existing.name if self.existing
                            else DEFAULT_TERM_NAME)
        self.name_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Start date:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.start_e = ttk.Entry(form, width=14)
        self.start_e.insert(0, (self.existing.start_date
                                  if self.existing
                                  else self.year.start_date))
        self.start_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="End date:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.end_e = ttk.Entry(form, width=14)
        self.end_e.insert(0, (self.existing.end_date
                                if self.existing
                                else self.year.end_date))
        self.end_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=44, height=4)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        payload = {
            "year_id":    self.year.year_id,
            "name":       self.name_cb.get().strip(),
            "start_date": self.start_e.get().strip(),
            "end_date":   self.end_e.get().strip(),
            "notes":      self.notes_t.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_term(self.existing.term_id, payload)
            else:
                data.create_term(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class BreakDialog:
    def __init__(self, parent: tk.Misc, *,
                 year: AcademicYear,
                 existing: Break | None,
                 on_save: Callable[[], None]) -> None:
        self.year = year
        self.existing = existing
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Break" if existing else "New Break")
        self.win.transient(parent)
        self.win.after_idle(self.win.grab_set)
        self._build()

    def _build(self) -> None:
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0

        ttk.Label(form,
                   text=f"Year: #{self.year.year_id} {self.year.name}  "
                         f"({self.year.start_date} → {self.year.end_date})"
                   ).grid(row=r, column=0, columnspan=2,
                           sticky="w", pady=(0, 8))

        r += 1
        ttk.Label(form, text="Name:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.name_e = ttk.Entry(form, width=30)
        if self.existing:
            self.name_e.insert(0, self.existing.name)
        self.name_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Type:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.type_cb = ttk.Combobox(form, values=BREAK_TYPES,
                                       state="readonly", width=14)
        self.type_cb.set(self.existing.type if self.existing
                            else DEFAULT_BREAK_TYPE)
        self.type_cb.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Start date:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.start_e = ttk.Entry(form, width=14)
        self.start_e.insert(0, (self.existing.start_date
                                  if self.existing
                                  else self.year.start_date))
        self.start_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="End date:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.end_e = ttk.Entry(form, width=14)
        self.end_e.insert(0, (self.existing.end_date
                                if self.existing
                                else self.year.start_date))
        self.end_e.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=44, height=4)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

    def _save(self) -> None:
        payload = {
            "year_id":    self.year.year_id,
            "name":       self.name_e.get().strip(),
            "type":       self.type_cb.get().strip(),
            "start_date": self.start_e.get().strip(),
            "end_date":   self.end_e.get().strip(),
            "notes":      self.notes_t.get("1.0", "end").strip(),
        }
        try:
            if self.existing:
                data.update_break(self.existing.break_id, payload)
            else:
                data.create_break(payload)
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()
