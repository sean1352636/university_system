"""Split from student_features.py — see package __init__.py for public API."""
from __future__ import annotations

import calendar
import csv
import functools
import json
import logging
import sqlite3
import tkinter as tk
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable, Iterable, Optional

from education_system.systems.university.domain.academics.services.attendance.absence_tracking.admin_features import (
    safe, audit, _combo_dialog, _show_table, _export_rows_to_csv,
    _get_setting, _set_setting, ensure_support_tables,
    pick_date, pick_date_range,
)

try:
    from education_system.systems.university.infrastructure.logging.log_config import configure_logging
    logger = configure_logging(name="absence_tracker.student")
except Exception:
    logger = logging.getLogger("absence_tracker.student")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)

from ..context import StudentContext


_STATUS_COLOURS = {
    "present": "#86efac",
    "absent":  "#fca5a5",
    "late":    "#fcd34d",
    "excused": "#bfdbfe",
}
_IN_MONTH_BG = "#f3f4f6"
_OFF_MONTH_BG = "#e5e7eb"
_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


class _CalendarWindow:
    """Toplevel month-calendar view with prev/next navigation."""

    def __init__(self, ctx: StudentContext, sid: str):
        self.ctx = ctx
        self.sid = sid
        today = date.today()
        self.year = today.year
        self.month = today.month
        self._cal = calendar.Calendar(firstweekday=0)

    def show(self) -> None:
        self.win = tk.Toplevel(self.ctx.parent)
        self.win.title("My attendance")
        self.win.geometry("620x460")
        self.win.transient(self.ctx.parent)

        self._build_header()
        self._build_legend()
        self._grid = tk.Frame(self.win)
        self._grid.pack(padx=10, pady=10)
        self._render_grid()

        self.win.bind("<Left>",  lambda _e: self._shift(-1))
        self.win.bind("<Right>", lambda _e: self._shift(+1))
        self.win.bind("<Home>",  lambda _e: self._goto_today())

    def current_month_str(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    def _build_header(self) -> None:
        bar = tk.Frame(self.win)
        bar.pack(fill="x", padx=10, pady=(10, 0))
        tk.Button(bar, text="◀", width=3,
                  command=lambda: self._shift(-1)).pack(side="left")
        self._title_var = tk.StringVar(value=self._title_text())
        tk.Label(bar, textvariable=self._title_var,
                 font=("Arial", 14, "bold")).pack(side="left", expand=True)
        tk.Button(bar, text="▶", width=3,
                  command=lambda: self._shift(+1)).pack(side="right")
        tk.Button(bar, text="Today",
                  command=self._goto_today).pack(side="right", padx=6)

    def _build_legend(self) -> None:
        legend = tk.Frame(self.win)
        legend.pack(fill="x", padx=10, pady=4)
        for status, colour in _STATUS_COLOURS.items():
            chip = tk.Frame(legend, bg=colour, width=14, height=14,
                            relief="solid", borderwidth=1)
            chip.pack(side="left", padx=(8, 4))
            chip.pack_propagate(False)
            tk.Label(legend, text=status.capitalize(),
                     font=("Arial", 9)).pack(side="left")

    def _title_text(self) -> str:
        return f"{calendar.month_name[self.month]} {self.year}"

    def _fetch_month(self) -> dict[str, str]:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT date, status FROM attendance
                   WHERE student_id = ?
                     AND strftime('%Y-%m', date) = ?""",
                (self.sid, self.current_month_str()),
            ).fetchall()
            return dict(rows)
        except sqlite3.Error:
            logger.exception("calendar fetch failed")
            return {}

    def _render_grid(self) -> None:
        for child in self._grid.winfo_children():
            child.destroy()
        for c, wd in enumerate(_WEEKDAYS):
            tk.Label(self._grid, text=wd, width=8,
                     font=("Arial", 10, "bold")).grid(row=0, column=c)

        by_day = self._fetch_month()
        today_iso = date.today().isoformat()

        for r, week in enumerate(self._cal.monthdatescalendar(
                self.year, self.month), start=1):
            for c, d in enumerate(week):
                in_month = d.month == self.month
                status = by_day.get(d.isoformat(), "") if in_month else ""
                bg = _STATUS_COLOURS.get(
                    status, _IN_MONTH_BG if in_month else _OFF_MONTH_BG)
                fg = "#111827" if in_month else "#9ca3af"
                borderwidth = 2 if d.isoformat() == today_iso else 1
                tk.Label(self._grid,
                         text=f"{d.day}\n{status}",
                         width=8, height=3,
                         bg=bg, fg=fg,
                         relief="solid", borderwidth=borderwidth,
                         font=("Arial", 9)
                         ).grid(row=r, column=c, padx=1, pady=1)

    def _shift(self, delta: int) -> None:
        m = self.month + delta
        y = self.year
        while m < 1:
            m += 12; y -= 1
        while m > 12:
            m -= 12; y += 1
        self.year, self.month = y, m
        self._title_var.set(self._title_text())
        self._render_grid()

    def _goto_today(self) -> None:
        today = date.today()
        self.year, self.month = today.year, today.month
        self._title_var.set(self._title_text())
        self._render_grid()
