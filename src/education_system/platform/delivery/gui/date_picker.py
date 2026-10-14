"""A date picked from dropdowns, not typed.

Every date this platform stores is ``YYYY-MM-DD`` and every validator
rejects anything else, so a free-text box is a format error waiting to
happen — and a slower way to enter a date besides. Three dropdowns
cannot produce an invalid string.

Used for destination start/confirmation dates and for a learner's date
of birth, which is why the year range is a parameter: a date of birth is
sixteen-odd years in the past, a start date is next term.
"""

from __future__ import annotations

import datetime as _dt
import tkinter as tk
from tkinter import ttk

__all__ = ["DatePicker", "birth_years", "recent_years"]


def recent_years(*, ahead: int = 2, back: int = 8) -> list[str]:
    """Years around now — for dates a record is about to acquire."""
    this_year = _dt.date.today().year
    return [str(y) for y in range(this_year + ahead, this_year - back, -1)]


def birth_years(*, youngest: int = 14, oldest: int = 80) -> list[str]:
    """Plausible birth years, newest first."""
    this_year = _dt.date.today().year
    return [str(y) for y in range(this_year - youngest, this_year - oldest, -1)]


class DatePicker(ttk.Frame):
    """Day / month / year dropdowns yielding ``YYYY-MM-DD`` or ``""``.

    The stored format is exact and the validator rejects anything else,
    so picking the parts is both quicker than typing and impossible to
    get syntactically wrong. Blank in any box means "not set".
    """

    _MONTHS = (
        ("01", "Jan"), ("02", "Feb"), ("03", "Mar"), ("04", "Apr"),
        ("05", "May"), ("06", "Jun"), ("07", "Jul"), ("08", "Aug"),
        ("09", "Sep"), ("10", "Oct"), ("11", "Nov"), ("12", "Dec"),
    )

    def __init__(self, master: tk.Misc, *, value: str | None = None,
                 years: list[str] | None = None) -> None:
        """*years* defaults to a window around now — pass
        :func:`birth_years` for a date of birth, where offering next year
        is nonsense and 2009 is the answer."""
        super().__init__(master)
        years = [""] + list(years if years is not None else recent_years())

        self._month_labels = {lbl: num for num, lbl in self._MONTHS}
        self.cb_day = ttk.Combobox(self, values=[""] + [f"{d:02d}" for d in range(1, 32)],
                                   state="readonly", width=4)
        self.cb_month = ttk.Combobox(self, values=[""] + [lbl for _n, lbl in self._MONTHS],
                                     state="readonly", width=6)
        self.cb_year = ttk.Combobox(self, values=years, state="readonly", width=6)
        for w in (self.cb_day, self.cb_month, self.cb_year):
            w.set("")
            w.pack(side="left", padx=(0, 4))
        ttk.Button(self, text="Today", width=6,
                   command=self._today).pack(side="left", padx=(4, 0))
        ttk.Button(self, text="Clear", width=6,
                   command=self.clear).pack(side="left", padx=(4, 0))
        if value:
            self.set(value)

    def _today(self) -> None:
        self.set(_dt.date.today().isoformat())

    def clear(self) -> None:
        for w in (self.cb_day, self.cb_month, self.cb_year):
            w.set("")

    def set(self, value: str) -> None:
        try:
            y, m, d = value.split("-")
            self.cb_year.set(y)
            self.cb_month.set(dict(self._MONTHS)[m])
            self.cb_day.set(d)
        except (ValueError, KeyError):
            self.clear()

    def get(self) -> str:
        day, month, year = self.cb_day.get(), self.cb_month.get(), self.cb_year.get()
        if not (day and month and year):
            return ""
        return f"{year}-{self._month_labels[month]}-{day}"
