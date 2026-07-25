"""Reusable Tk dialogs and entity pickers for admin features."""
from __future__ import annotations

import calendar as _cal
import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, simpledialog, ttk
from typing import Optional

from .context import AdminContext, logger


def _combo_dialog(parent, title, label, values) -> Optional[str]:
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.transient(parent)
    dlg.grab_set()
    dlg.geometry("520x140")
    tk.Label(dlg, text=label).pack(pady=8)
    var = tk.StringVar()
    cb = ttk.Combobox(dlg, textvariable=var, values=values,
                      state="readonly", width=60)
    cb.pack(padx=10)
    result = {"v": None}

    def ok():
        result["v"] = var.get()
        dlg.destroy()

    tk.Button(dlg, text="OK", command=ok, bg="#2563eb", fg="white",
              relief="flat", padx=16, pady=4).pack(pady=12)
    dlg.wait_window()
    return result["v"] or None


def _show_table(parent, title, columns, rows, widths=None, extra_button=None):
    """Pop up a modal window showing `rows` in a Treeview."""
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("1000x600")
    frame = ttk.Frame(win)
    frame.pack(fill="both", expand=True, padx=10, pady=10)
    tree = ttk.Treeview(frame, columns=columns, show="headings")
    widths = widths or [max(80, int(900 / max(1, len(columns))))] * len(columns)
    for c, w in zip(columns, widths):
        tree.heading(c, text=c)
        tree.column(c, width=w, anchor="w")
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")
    for row in rows:
        tree.insert("", "end", values=row)
    btns = tk.Frame(win)
    btns.pack(fill="x", pady=6)
    if extra_button:
        label, cmd = extra_button
        tk.Button(btns, text=label, command=cmd, bg="#2563eb", fg="white",
                  relief="flat", padx=10, pady=4).pack(side="left", padx=10)
    tk.Button(btns, text="Close", command=win.destroy, bg="#6b7280",
              fg="white", relief="flat", padx=10, pady=4
              ).pack(side="right", padx=10)
    return win, tree


def pick_date(parent, title="Pick a date",
              initial: Optional[date] = None) -> Optional[str]:
    """Modal year/month/day combobox dialog. Returns 'YYYY-MM-DD' or None."""
    today = initial or date.today()
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.transient(parent)
    dlg.grab_set()
    dlg.geometry("360x180")
    tk.Label(dlg, text=title, font=("Arial", 11, "bold")).pack(pady=10)

    row = tk.Frame(dlg); row.pack(pady=6)
    years = [str(y) for y in range(today.year - 2, today.year + 4)]
    months = [f"{m:02d}" for m in range(1, 13)]
    y_var = tk.StringVar(value=str(today.year))
    m_var = tk.StringVar(value=f"{today.month:02d}")
    d_var = tk.StringVar(value=f"{today.day:02d}")

    def days_for(y: str, m: str) -> list[str]:
        try:
            n = _cal.monthrange(int(y), int(m))[1]
        except (ValueError, _cal.IllegalMonthError):
            n = 31
        return [f"{d:02d}" for d in range(1, n + 1)]

    tk.Label(row, text="Year").grid(row=0, column=0, padx=4)
    tk.Label(row, text="Month").grid(row=0, column=1, padx=4)
    tk.Label(row, text="Day").grid(row=0, column=2, padx=4)
    y_cb = ttk.Combobox(row, textvariable=y_var, values=years,
                        width=6, state="readonly")
    m_cb = ttk.Combobox(row, textvariable=m_var, values=months,
                        width=5, state="readonly")
    d_cb = ttk.Combobox(row, textvariable=d_var,
                        values=days_for(y_var.get(), m_var.get()),
                        width=5, state="readonly")
    y_cb.grid(row=1, column=0, padx=4)
    m_cb.grid(row=1, column=1, padx=4)
    d_cb.grid(row=1, column=2, padx=4)

    def refresh_days(*_):
        days = days_for(y_var.get(), m_var.get())
        d_cb.configure(values=days)
        if d_var.get() not in days:
            d_var.set(days[-1])

    y_var.trace_add("write", refresh_days)
    m_var.trace_add("write", refresh_days)

    result = {"v": None}

    def ok():
        result["v"] = f"{y_var.get()}-{m_var.get()}-{d_var.get()}"
        dlg.destroy()

    btns = tk.Frame(dlg); btns.pack(pady=12)
    tk.Button(btns, text="OK", command=ok, bg="#2563eb", fg="white",
              relief="flat", padx=18, pady=4).pack(side="left", padx=6)
    tk.Button(btns, text="Cancel", command=dlg.destroy, bg="#6b7280",
              fg="white", relief="flat", padx=18, pady=4
              ).pack(side="left", padx=6)
    dlg.wait_window()
    return result["v"]


def pick_date_range(parent,
                    title="Pick a date range") -> Optional[tuple[str, str]]:
    """Two sequential date pickers. Returns (start, end) or None."""
    start = pick_date(parent, f"{title} — start date")
    if not start:
        return None
    try:
        init = datetime.strptime(start, "%Y-%m-%d").date()
    except ValueError:
        init = None
    end = pick_date(parent, f"{title} — end date", initial=init)
    if not end:
        return None
    if end < start:
        start, end = end, start
    return start, end




class Prompt:
    """Reusable Tk dialogs with validation."""

    @staticmethod
    def iso_date(parent, title: str = "Date",
                 prompt: str = "Date (YYYY-MM-DD):",
                 initial: Optional[str] = None) -> Optional[str]:
        initial = initial or date.today().isoformat()
        while True:
            s = simpledialog.askstring(title, prompt, parent=parent,
                                       initialvalue=initial)
            if s is None:
                return None
            s = s.strip()
            try:
                datetime.strptime(s, "%Y-%m-%d")
                return s
            except ValueError:
                messagebox.showerror("Bad date",
                                     f"'{s}' is not YYYY-MM-DD.",
                                     parent=parent)
                initial = s

    @staticmethod
    def non_empty(parent, title: str, prompt: str,
                  min_len: int = 1) -> Optional[str]:
        while True:
            s = simpledialog.askstring(title, prompt, parent=parent)
            if s is None:
                return None
            s = s.strip()
            if len(s) >= min_len:
                return s
            messagebox.showerror("Too short",
                                 f"Please give at least {min_len} character(s).",
                                 parent=parent)

    @staticmethod
    def confirm(parent, title: str, msg: str) -> bool:
        return bool(messagebox.askyesno(title, msg, parent=parent))


class StudentPicker:
    """Pick a student id from the users table."""

    def __init__(self, ctx: AdminContext) -> None:
        self.ctx = ctx

    def pick(self, prompt: str = "Pick a student") -> Optional[str]:
        try:
            rows = self.ctx.db.get_users("student")
        except Exception:
            logger.exception("get_users('student') failed")
            messagebox.showerror("Error", "Could not load students.",
                                 parent=self.ctx.parent)
            return None
        if not rows:
            messagebox.showinfo("No students",
                                "No students in the database.",
                                parent=self.ctx.parent)
            return None
        options = {f"{r[3] or r[1]} ({r[1]})": r[0] for r in rows}
        pick = _combo_dialog(self.ctx.parent, prompt,
                             "Student:", list(options.keys()))
        return options.get(pick) if pick else None


class ModulePicker:
    """Pick a module code from the modules table."""

    def __init__(self, ctx: AdminContext) -> None:
        self.ctx = ctx

    def pick(self, prompt: str = "Pick a module") -> Optional[str]:
        try:
            rows = self.ctx.db.get_courses()
        except Exception:
            logger.exception("get_courses failed")
            messagebox.showerror("Error", "Could not load modules.",
                                 parent=self.ctx.parent)
            return None
        if not rows:
            messagebox.showinfo("No modules",
                                "No modules in the database.",
                                parent=self.ctx.parent)
            return None
        options = {f"{r[1]} - {r[2]}": r[0] for r in rows}
        pick = _combo_dialog(self.ctx.parent, prompt,
                             "Module:", list(options.keys()))
        return options.get(pick) if pick else None


# Legacy single-call wrappers retained so old code paths still work.
def _pick_student(ctx: AdminContext,
                  prompt: str = "Pick a student") -> Optional[str]:
    return StudentPicker(ctx).pick(prompt)


def _pick_module(ctx: AdminContext,
                 prompt: str = "Pick a module") -> Optional[str]:
    return ModulePicker(ctx).pick(prompt)
