# Auto-generated module (split from student_crud_gui.py)
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import logging
import random
import secrets
import json
import csv
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from education_system.post_18.university_system.modules.shared.gui.main._tk_callback_filter import install_clean_close as _install_clean_close

from education_system.post_18.university_system.core.i18n import get_text as _t
from education_system.post_18.university_system.infrastructure.database.db import get_db_connection, get_connection, transaction
from education_system.post_18.university_system.core.sql_safety import (
    validate_table_name,
    validate_column_name,
    SQLIdentifierError,
)

logger = logging.getLogger("education_system.post_18.university_system.modules.shared.gui.main.students.student_crud_gui")

try:
    from education_system.post_18.university_system.core.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False

class _DOBPicker(ttk.Frame):
    """Year / Month / Day spinbox trio for date of birth.

    Replaces the old plain Entry that expected YYYY-MM-DD and failed
    with a post-submit "Date format must be YYYY-MM-DD" error
    whenever the user typed anything else. Days range is clamped to
    the selected month's length so 31 Feb is unreachable.

    Public API mirrors the bits the rest of the form actually used:
      * ``get()`` -> YYYY-MM-DD string (or "" if any field is blank)
      * ``set(value)`` -> accepts "" or YYYY-MM-DD
      * ``delete(0, 'end')`` -> clear helper used by the Clear-form
        callback that iterates all fields.
    """

    _MONTHS = (
        (1, "Jan"), (2, "Feb"), (3, "Mar"), (4, "Apr"),
        (5, "May"), (6, "Jun"), (7, "Jul"), (8, "Aug"),
        (9, "Sep"), (10, "Oct"), (11, "Nov"), (12, "Dec"),
    )

    def __init__(self, parent, *, default_year_offset: int = 19,
                  on_change=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._on_change = on_change
        this_year = datetime.now().year
        # Sensible UCAS-ish defaults: a typical undergrad applicant is
        # ~19; nothing older than 1944 is plausible for this form.
        default_year = this_year - default_year_offset

        self._year_var = tk.IntVar(value=default_year)
        self._month_var = tk.StringVar(value=self._MONTHS[0][1])
        self._day_var = tk.IntVar(value=1)

        self._year = tk.Spinbox(
            self, from_=1944, to=this_year, width=6,
            textvariable=self._year_var,
            command=self._notify_change,
        )
        self._year.pack(side=tk.LEFT, padx=(0, 4))

        self._month = ttk.Combobox(
            self, values=[m[1] for m in self._MONTHS],
            state="readonly", width=5,
            textvariable=self._month_var,
        )
        self._month.bind("<<ComboboxSelected>>",
                          lambda _e: (self._clamp_day(),
                                       self._notify_change()))
        self._month.pack(side=tk.LEFT, padx=(0, 4))

        self._day = tk.Spinbox(
            self, from_=1, to=31, width=4,
            textvariable=self._day_var,
            command=self._notify_change,
        )
        self._day.pack(side=tk.LEFT)

        # Notify on direct typing too, not just spinner clicks.
        for w in (self._year, self._day):
            w.bind("<KeyRelease>",
                    lambda _e: (self._clamp_day(),
                                 self._notify_change()))

    # ── public ───────────────────────────────────────────────────
    def get(self) -> str:
        y = self._safe_int(self._year_var)
        d = self._safe_int(self._day_var)
        m = next((n for n, abbr in self._MONTHS
                   if abbr == self._month_var.get()), None)
        if y is None or m is None or d is None:
            return ""
        try:
            return datetime(y, m, d).strftime("%Y-%m-%d")
        except ValueError:
            return ""  # e.g. 31 Feb after a bad direct edit

    def set(self, value: str) -> None:
        if not value:
            return
        try:
            dt = datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return
        self._year_var.set(dt.year)
        self._month_var.set(self._MONTHS[dt.month - 1][1])
        self._day_var.set(dt.day)

    def delete(self, _first, _last=None) -> None:
        """Clear-form helper. Resets to defaults rather than literally
        blank, since a blank spinbox is awkward to reach via UI."""
        this_year = datetime.now().year
        self._year_var.set(this_year - 19)
        self._month_var.set(self._MONTHS[0][1])
        self._day_var.set(1)

    # ── internal ─────────────────────────────────────────────────
    @staticmethod
    def _safe_int(var) -> int | None:
        try:
            return int(var.get())
        except (tk.TclError, ValueError, TypeError):
            return None

    def _clamp_day(self) -> None:
        """Cap the day spinner so users can't pick 31 Feb."""
        import calendar as _cal
        y = self._safe_int(self._year_var) or datetime.now().year
        m = next((n for n, abbr in self._MONTHS
                   if abbr == self._month_var.get()), 1)
        max_day = _cal.monthrange(y, m)[1]
        try:
            self._day.configure(to=max_day)
        except tk.TclError:
            pass
        d = self._safe_int(self._day_var)
        if d is not None and d > max_day:
            self._day_var.set(max_day)

    def _notify_change(self) -> None:
        if self._on_change is not None:
            try:
                self._on_change()
            except Exception:
                logger.exception("DOB on_change callback failed")


# Helper functions for safely setting widget values
def _safe_set_combobox(combobox, value):
    """Safely set combobox value"""
    try:
        if value and value in combobox['values']:
            combobox.set(value)
        else:
            combobox.set('')
    except Exception:
        combobox.set('')

def _safe_entry_insert(entry, value):
    """Safely insert value into entry widget"""
    try:
        entry.delete(0, tk.END)
        if value:
            entry.insert(0, str(value))
    except Exception:
        pass

