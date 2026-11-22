"""Year/term/break dialogs and date-picker helpers for the Sixth Form Academic Year window.

Split out of ``academic_year_views`` (2026-10-22); that module
re-exports every name defined here.
"""
from __future__ import annotations

from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable
import datetime as _dt
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Callable
from education_system.systems.sixth_form.domain.academics.academic_year import (
    academic_year as data,
)
from education_system.systems.sixth_form.domain.academics.academic_year.academic_year import (
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
from ._widgets import _today


# ══ Dialog helpers (date picker, validation) ══════════════════════

def _open_date_picker(parent: tk.Misc, entry: ttk.Entry,
                       *, year_hint: AcademicYear | None = None,
                       on_pick: Callable[[], None] | None = None
                       ) -> None:
    """Pop up a small year/month grid picker and write the chosen ISO
    date back into ``entry`` (replacing whatever is there)."""
    top = tk.Toplevel(parent)
    top.title("Pick a date")
    top.transient(parent)
    grab_when_viewable(top)
    top.resizable(False, False)

    # Seed state from the entry's current value, else today, else year.
    seed: _dt.date
    cur = entry.get().strip()
    try:
        seed = _dt.date.fromisoformat(cur)
    except ValueError:
        if year_hint is not None:
            try:
                seed = _dt.date.fromisoformat(year_hint.start_date)
            except ValueError:
                seed = _dt.date.today()
        else:
            seed = _dt.date.today()

    state = {"year": seed.year, "month": seed.month}

    bar = ttk.Frame(top)
    bar.pack(fill="x", padx=8, pady=6)
    ttk.Button(bar, text="◀", width=2,
                command=lambda: _shift_month(-1)).pack(side="left")
    title_var = tk.StringVar()
    ttk.Label(bar, textvariable=title_var, width=18,
               anchor="center", font=("TkDefaultFont", 10, "bold")
               ).pack(side="left", padx=4)
    ttk.Button(bar, text="▶", width=2,
                command=lambda: _shift_month(1)).pack(side="left")
    ttk.Button(bar, text="Today",
                command=lambda: _jump_today()).pack(side="right")

    grid = ttk.Frame(top)
    grid.pack(padx=8, pady=(0, 8))
    cells: list[tk.Label] = []
    for i, lbl in enumerate(("M", "T", "W", "T", "F", "S", "S")):
        tk.Label(grid, text=lbl, width=3, fg="#888",
                  font=("TkDefaultFont", 8, "bold")
                  ).grid(row=0, column=i, padx=1, pady=1)

    def _shift_month(delta: int) -> None:
        m = state["month"] + delta
        y = state["year"]
        while m < 1:
            m += 12
            y -= 1
        while m > 12:
            m -= 12
            y += 1
        state["year"] = y
        state["month"] = m
        _redraw()

    def _jump_today() -> None:
        t = _dt.date.today()
        state["year"] = t.year
        state["month"] = t.month
        _redraw()

    def _pick(d: _dt.date) -> None:
        entry.delete(0, "end")
        entry.insert(0, d.isoformat())
        top.destroy()
        if on_pick:
            on_pick()

    def _redraw() -> None:
        for c in cells:
            c.destroy()
        cells.clear()
        y, m = state["year"], state["month"]
        title_var.set(_dt.date(y, m, 1).strftime("%B %Y"))
        first = _dt.date(y, m, 1)
        start = first - _dt.timedelta(days=first.weekday())
        today = _dt.date.today()
        for week in range(6):
            for i in range(7):
                d = start + _dt.timedelta(days=7 * week + i)
                bg = "#fafafa" if d.month != m else "white"
                fg = "#bbb" if d.month != m else "#222"
                bold = ("TkDefaultFont", 9, "bold") \
                          if d == today else ("TkDefaultFont", 9)
                lbl = tk.Label(grid, text=str(d.day), width=3,
                                relief="solid", borderwidth=1,
                                bg=bg, fg=fg, font=bold)
                lbl.grid(row=1 + week, column=i, padx=1, pady=1)
                lbl.bind("<Button-1>",
                           lambda _e, dd=d: _pick(dd))
                lbl.bind("<Enter>",
                           lambda _e, w=lbl: w.configure(bg="#dde9f4"))
                lbl.bind("<Leave>",
                           lambda _e, w=lbl, b=bg:
                               w.configure(bg=b))
                cells.append(lbl)

    btn_bar = ttk.Frame(top)
    btn_bar.pack(fill="x", padx=8, pady=(0, 8))
    ttk.Button(btn_bar, text="Cancel",
                command=top.destroy).pack(side="right")

    _redraw()
    top.bind("<Escape>", lambda _e: top.destroy())


def _attach_picker(parent: tk.Misc, entry: ttk.Entry,
                    *, year_hint: AcademicYear | None = None,
                    on_pick: Callable[[], None] | None = None
                    ) -> ttk.Button:
    """Drop a 📅 button next to ``entry`` that opens a picker."""
    btn = ttk.Button(
        parent, text="📅", width=3,
        command=lambda: _open_date_picker(
            parent.winfo_toplevel(), entry,
            year_hint=year_hint, on_pick=on_pick))
    return btn


def _is_valid_iso(s: str) -> bool:
    s = s.strip()
    if not s:
        return False
    try:
        _dt.date.fromisoformat(s)
        return True
    except ValueError:
        return False


def _wire_validation(entry: ttk.Entry, *,
                      on_change: Callable[[], None] | None = None
                      ) -> None:
    """Turn the entry red on blur if its value isn't an ISO date.
    Also fires ``on_change`` on each keystroke (for live day-count)."""
    def _check(_e=None) -> None:
        s = entry.get().strip()
        if not s or _is_valid_iso(s):
            try:
                entry.configure(foreground="black")
            except tk.TclError:
                pass
            entry.configure(background="white")
        else:
            entry.configure(background="#ffe0e0")
    entry.bind("<FocusOut>", _check)
    entry.bind("<KeyRelease>",
                 lambda _e: (_check(),
                              on_change() if on_change else None))


def _days_between(s: str, e: str) -> int | None:
    if not (_is_valid_iso(s) and _is_valid_iso(e)):
        return None
    try:
        return ((_dt.date.fromisoformat(e)
                  - _dt.date.fromisoformat(s)).days + 1)
    except ValueError:
        return None


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
        grab_when_viewable(self.win)
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
        self.name_e.grid(row=r, column=1, sticky="w", padx=6,
                           columnspan=2)

        # Defaults for a brand-new year: continue from the most recent
        # existing year's end.
        default_start = ""
        default_end = ""
        if not self.existing:
            years = data.list_years()
            if years:
                latest = max(years, key=lambda y: y.end_date)
                try:
                    ds = (_dt.date.fromisoformat(latest.end_date)
                           + _dt.timedelta(days=1))
                    default_start = ds.isoformat()
                    default_end = (ds + _dt.timedelta(days=364)
                                       ).isoformat()
                except ValueError:
                    pass

        r += 1
        ttk.Label(form, text="Start date:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.start_e = ttk.Entry(form, width=14)
        if self.existing:
            self.start_e.insert(0, self.existing.start_date)
        elif default_start:
            self.start_e.insert(0, default_start)
        self.start_e.grid(row=r, column=1, sticky="w", padx=6)
        _attach_picker(form, self.start_e,
                         on_pick=lambda: self._update_days()
                         ).grid(row=r, column=2, sticky="w")

        r += 1
        ttk.Label(form, text="End date:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.end_e = ttk.Entry(form, width=14)
        if self.existing:
            self.end_e.insert(0, self.existing.end_date)
        elif default_end:
            self.end_e.insert(0, default_end)
        self.end_e.grid(row=r, column=1, sticky="w", padx=6)
        _attach_picker(form, self.end_e,
                         on_pick=lambda: self._update_days()
                         ).grid(row=r, column=2, sticky="w")

        r += 1
        self.days_var = tk.StringVar(value="")
        ttk.Label(form, textvariable=self.days_var,
                   foreground="#666").grid(
            row=r, column=1, sticky="w", padx=6, columnspan=2)

        r += 1
        ttk.Label(form, text="Status:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.status_cb = ttk.Combobox(form, values=YEAR_STATUSES,
                                         state="readonly", width=14)
        self.status_cb.set(self.existing.status if self.existing
                              else DEFAULT_YEAR_STATUS)
        self.status_cb.grid(row=r, column=1, sticky="w", padx=6,
                              columnspan=2)

        r += 1
        self.current_var = tk.BooleanVar(
            value=(self.existing.is_current if self.existing else False))
        ttk.Checkbutton(form, text="Flag as current year",
                          variable=self.current_var).grid(
            row=r, column=1, sticky="w", padx=6, pady=2, columnspan=2)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=44, height=4)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6,
                            columnspan=2)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=3, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

        _wire_validation(self.start_e, on_change=self._update_days)
        _wire_validation(self.end_e, on_change=self._update_days)
        self._update_days()
        self.name_e.focus_set()
        self.win.bind("<Return>", lambda _e: self._save())
        self.win.bind("<Escape>", lambda _e: self.win.destroy())

    def _update_days(self) -> None:
        n = _days_between(self.start_e.get(), self.end_e.get())
        if n is None:
            self.days_var.set("")
        elif n <= 0:
            self.days_var.set("⚠ end date is before start date")
        else:
            self.days_var.set(f"{n} day(s)")

    def _save(self) -> None:
        payload = {
            "name":       self.name_e.get().strip(),
            "start_date": self.start_e.get().strip(),
            "end_date":   self.end_e.get().strip(),
            "status":     self.status_cb.get().strip(),
            "is_current": self.current_var.get(),
            "notes":      self.notes_t.get("1.0", "end").strip(),
        }
        if payload["status"] == "Archived" and payload["is_current"]:
            messagebox.showerror(
                "Save failed",
                "A year cannot be both Archived and the current year. "
                "Set status to Active or Planning first.")
            return
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
        grab_when_viewable(self.win)
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
        self.name_cb.grid(row=r, column=1, sticky="w", padx=6,
                            columnspan=2)

        r += 1
        ttk.Label(form, text="Start date:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.start_e = ttk.Entry(form, width=14)
        self.start_e.insert(0, (self.existing.start_date
                                  if self.existing
                                  else self.year.start_date))
        self.start_e.grid(row=r, column=1, sticky="w", padx=6)
        _attach_picker(form, self.start_e, year_hint=self.year,
                         on_pick=lambda: self._update_days()
                         ).grid(row=r, column=2, sticky="w")

        r += 1
        ttk.Label(form, text="End date:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.end_e = ttk.Entry(form, width=14)
        self.end_e.insert(0, (self.existing.end_date
                                if self.existing
                                else self.year.end_date))
        self.end_e.grid(row=r, column=1, sticky="w", padx=6)
        _attach_picker(form, self.end_e, year_hint=self.year,
                         on_pick=lambda: self._update_days()
                         ).grid(row=r, column=2, sticky="w")

        # "+N weeks" helper bar
        r += 1
        weeks_bar = ttk.Frame(form)
        weeks_bar.grid(row=r, column=1, columnspan=2,
                          sticky="w", padx=6, pady=(2, 0))
        ttk.Label(weeks_bar, text="End = Start +").pack(side="left")
        self.weeks_sp = tk.Spinbox(weeks_bar, from_=1, to=52, width=4)
        self.weeks_sp.delete(0, "end")
        self.weeks_sp.insert(0, "12")
        self.weeks_sp.pack(side="left", padx=2)
        ttk.Label(weeks_bar, text="weeks").pack(side="left")
        ttk.Button(weeks_bar, text="Apply", width=6,
                    command=self._apply_weeks).pack(side="left", padx=4)

        r += 1
        self.days_var = tk.StringVar(value="")
        ttk.Label(form, textvariable=self.days_var,
                   foreground="#666").grid(
            row=r, column=1, sticky="w", padx=6, columnspan=2)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=44, height=4)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6,
                            columnspan=2)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=3, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

        _wire_validation(self.start_e, on_change=self._update_days)
        _wire_validation(self.end_e, on_change=self._update_days)
        self._update_days()
        self.name_cb.focus_set()
        self.win.bind("<Return>", lambda _e: self._save())
        self.win.bind("<Escape>", lambda _e: self.win.destroy())

    def _apply_weeks(self) -> None:
        try:
            s = _dt.date.fromisoformat(self.start_e.get().strip())
            n = max(1, int(self.weeks_sp.get()))
        except (ValueError, TypeError):
            messagebox.showerror(
                "Weeks helper",
                "Enter a valid start date first.")
            return
        end = s + _dt.timedelta(days=n * 7 - 1)
        self.end_e.delete(0, "end")
        self.end_e.insert(0, end.isoformat())
        self._update_days()

    def _update_days(self) -> None:
        n = _days_between(self.start_e.get(), self.end_e.get())
        if n is None:
            self.days_var.set("")
        elif n <= 0:
            self.days_var.set("⚠ end date is before start date")
        else:
            self.days_var.set(f"{n} day(s)")

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
                 on_save: Callable[..., None],
                 default_type: str | None = None) -> None:
        self.year = year
        self.existing = existing
        self.on_save = on_save
        self.default_type = default_type or DEFAULT_BREAK_TYPE
        self.win = tk.Toplevel(parent)
        self.win.title("Edit Break" if existing else "New Break")
        self.win.transient(parent)
        grab_when_viewable(self.win)
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
        self.name_e.grid(row=r, column=1, sticky="w", padx=6,
                           columnspan=2)

        r += 1
        ttk.Label(form, text="Type:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.type_cb = ttk.Combobox(form, values=BREAK_TYPES,
                                       state="readonly", width=14)
        self.type_cb.set(self.existing.type if self.existing
                            else self.default_type)
        self.type_cb.grid(row=r, column=1, sticky="w", padx=6,
                            columnspan=2)

        r += 1
        ttk.Label(form, text="Start date:").grid(row=r, column=0,
                                                    sticky="e", pady=4)
        self.start_e = ttk.Entry(form, width=14)
        self.start_e.insert(0, (self.existing.start_date
                                  if self.existing
                                  else self.year.start_date))
        self.start_e.grid(row=r, column=1, sticky="w", padx=6)
        _attach_picker(form, self.start_e, year_hint=self.year,
                         on_pick=lambda: self._update_days()
                         ).grid(row=r, column=2, sticky="w")

        r += 1
        ttk.Label(form, text="End date:").grid(row=r, column=0,
                                                  sticky="e", pady=4)
        self.end_e = ttk.Entry(form, width=14)
        self.end_e.insert(0, (self.existing.end_date
                                if self.existing
                                else self.year.start_date))
        self.end_e.grid(row=r, column=1, sticky="w", padx=6)
        _attach_picker(form, self.end_e, year_hint=self.year,
                         on_pick=lambda: self._update_days()
                         ).grid(row=r, column=2, sticky="w")

        r += 1
        self.days_var = tk.StringVar(value="")
        ttk.Label(form, textvariable=self.days_var,
                   foreground="#666").grid(
            row=r, column=1, sticky="w", padx=6, columnspan=2)

        r += 1
        ttk.Label(form, text="Notes:").grid(row=r, column=0,
                                               sticky="ne", pady=4)
        self.notes_t = tk.Text(form, width=44, height=4)
        if self.existing and self.existing.notes:
            self.notes_t.insert("1.0", self.existing.notes)
        self.notes_t.grid(row=r, column=1, sticky="w", padx=6,
                            columnspan=2)

        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=3, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)

        _wire_validation(self.start_e, on_change=self._update_days)
        _wire_validation(self.end_e, on_change=self._update_days)
        self._update_days()
        self.name_e.focus_set()
        self.win.bind("<Return>", lambda _e: self._save())
        self.win.bind("<Escape>", lambda _e: self.win.destroy())

    def _update_days(self) -> None:
        n = _days_between(self.start_e.get(), self.end_e.get())
        if n is None:
            self.days_var.set("")
        elif n <= 0:
            self.days_var.set("⚠ end date is before start date")
        else:
            self.days_var.set(f"{n} day(s)")

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
        BreaksTab.LAST_TYPE = payload["type"] or BreaksTab.LAST_TYPE
        self.win.destroy()
        try:
            self.on_save(payload["type"])
        except TypeError:
            self.on_save()


class QuickInsetDialog:
    """One-day INSET creator — name + date."""

    def __init__(self, parent: tk.Misc, *,
                 year: AcademicYear,
                 on_save: Callable[[], None]) -> None:
        self.year = year
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Add INSET day")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        ttk.Label(form,
                   text=f"Year: {year.name}  "
                         f"({year.start_date} → {year.end_date})"
                   ).grid(row=0, column=0, columnspan=2,
                           sticky="w", pady=(0, 8))
        ttk.Label(form, text="Name:").grid(row=1, column=0,
                                              sticky="e", pady=4)
        self.name_e = ttk.Entry(form, width=30)
        self.name_e.insert(0, "INSET Day")
        self.name_e.grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Date:").grid(row=2, column=0,
                                              sticky="e", pady=4)
        self.date_e = ttk.Entry(form, width=14)
        today = _today()
        default_date = (today if year.start_date <= today <= year.end_date
                          else year.start_date)
        self.date_e.insert(0, default_date)
        self.date_e.grid(row=2, column=1, sticky="w", padx=6)
        _attach_picker(form, self.date_e, year_hint=year
                         ).grid(row=2, column=2, sticky="w")
        _wire_validation(self.date_e)
        bar = ttk.Frame(form)
        bar.grid(row=3, column=0, columnspan=3, pady=(12, 0))
        ttk.Button(bar, text="Save", command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)
        self.name_e.focus_set()
        self.win.bind("<Return>", lambda _e: self._save())
        self.win.bind("<Escape>", lambda _e: self.win.destroy())

    def _save(self) -> None:
        d = self.date_e.get().strip()
        try:
            data.create_break({
                "year_id": self.year.year_id,
                "name": self.name_e.get().strip() or "INSET Day",
                "type": "INSET",
                "start_date": d, "end_date": d, "notes": None,
            })
        except (ValidationError, Exception) as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.win.destroy()
        self.on_save()


class RecurringBreakDialog:
    """Generate a series of breaks (e.g. weekly PD afternoons) between
    two dates."""

    WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

    def __init__(self, parent: tk.Misc, *,
                 year: AcademicYear,
                 on_save: Callable[[], None]) -> None:
        self.year = year
        self.on_save = on_save
        self.win = tk.Toplevel(parent)
        self.win.title("Recurring break template")
        self.win.transient(parent)
        grab_when_viewable(self.win)
        form = ttk.Frame(self.win)
        form.pack(fill="both", expand=True, padx=12, pady=12)
        r = 0
        ttk.Label(form,
                   text=f"Year: {year.name}  "
                         f"({year.start_date} → {year.end_date})"
                   ).grid(row=r, column=0, columnspan=3,
                           sticky="w", pady=(0, 8))
        r += 1
        ttk.Label(form, text="Name prefix:").grid(
            row=r, column=0, sticky="e", pady=4)
        self.name_e = ttk.Entry(form, width=24)
        self.name_e.insert(0, "PD Afternoon")
        self.name_e.grid(row=r, column=1, sticky="w", padx=6)
        r += 1
        ttk.Label(form, text="Type:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.type_cb = ttk.Combobox(form, values=BREAK_TYPES,
                                       state="readonly", width=14)
        self.type_cb.set("INSET")
        self.type_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1
        ttk.Label(form, text="Every:").grid(row=r, column=0,
                                                sticky="e", pady=4)
        self.every_sp = tk.Spinbox(form, from_=1, to=12, width=4)
        self.every_sp.delete(0, "end")
        self.every_sp.insert(0, "1")
        self.every_sp.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(form, text="weeks").grid(row=r, column=2,
                                              sticky="w")
        r += 1
        ttk.Label(form, text="On:").grid(row=r, column=0,
                                            sticky="e", pady=4)
        self.dow_cb = ttk.Combobox(form, values=self.WEEKDAYS,
                                      state="readonly", width=6)
        self.dow_cb.current(4)  # Fri
        self.dow_cb.grid(row=r, column=1, sticky="w", padx=6)
        r += 1
        ttk.Label(form, text="From:").grid(row=r, column=0,
                                              sticky="e", pady=4)
        self.from_e = ttk.Entry(form, width=14)
        self.from_e.insert(0, year.start_date)
        self.from_e.grid(row=r, column=1, sticky="w", padx=6)
        _attach_picker(form, self.from_e, year_hint=year
                         ).grid(row=r, column=2, sticky="w")
        _wire_validation(self.from_e)
        r += 1
        ttk.Label(form, text="To:").grid(row=r, column=0,
                                            sticky="e", pady=4)
        self.to_e = ttk.Entry(form, width=14)
        self.to_e.insert(0, year.end_date)
        self.to_e.grid(row=r, column=1, sticky="w", padx=6)
        _attach_picker(form, self.to_e, year_hint=year
                         ).grid(row=r, column=2, sticky="w")
        _wire_validation(self.to_e)
        r += 1
        bar = ttk.Frame(form)
        bar.grid(row=r, column=0, columnspan=3, pady=(12, 0))
        ttk.Button(bar, text="Generate",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.win.destroy).pack(side="left", padx=8)
        self.win.bind("<Escape>", lambda _e: self.win.destroy())

    def _save(self) -> None:
        try:
            frm = _dt.date.fromisoformat(self.from_e.get().strip())
            to = _dt.date.fromisoformat(self.to_e.get().strip())
            every = max(1, int(self.every_sp.get()))
        except (ValueError, TypeError) as e:
            messagebox.showerror("Recurring", f"Bad input: {e}")
            return
        dow = self.dow_cb.current()
        if dow < 0:
            messagebox.showerror("Recurring", "Pick a day of week.")
            return
        # Snap from-date forward to the chosen weekday
        shift = (dow - frm.weekday()) % 7
        cur = frm + _dt.timedelta(days=shift)
        step = _dt.timedelta(days=7 * every)
        dates: list[_dt.date] = []
        while cur <= to:
            dates.append(cur)
            cur += step
        if not dates:
            messagebox.showinfo("Recurring",
                                   "No dates produced. Check inputs.")
            return
        name = self.name_e.get().strip() or "Recurring"
        typ = self.type_cb.get().strip() or "INSET"
        preview = "\n".join(f"  • {name} — {d.isoformat()} "
                              f"({d.strftime('%a')})"
                              for d in dates[:10])
        more = ("" if len(dates) <= 10
                 else f"\n  …and {len(dates) - 10} more")
        if not messagebox.askyesno(
                "Recurring",
                f"Create {len(dates)} {typ} break(s)?\n\n"
                f"{preview}{more}"):
            return
        errs: list[str] = []
        for d in dates:
            iso = d.isoformat()
            try:
                data.create_break({
                    "year_id": self.year.year_id,
                    "name": name, "type": typ,
                    "start_date": iso, "end_date": iso, "notes": None,
                })
            except (ValidationError, Exception) as ex:
                errs.append(f"{iso}: {ex}")
        if errs:
            messagebox.showerror("Some inserts failed",
                                    "\n".join(errs))
        self.win.destroy()
        self.on_save()


# Sibling names used only at call time; imported last so any import order works.
from .tab_breaks import BreaksTab  # noqa: E402
