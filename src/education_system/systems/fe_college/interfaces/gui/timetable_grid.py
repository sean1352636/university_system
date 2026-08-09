"""The weekly timetable grid, drawn once and reused by three windows.

Admin, staff and learner all show the same grid; only what fills it and
whether the cells are clickable differ. Keeping one renderer means a change to
the layout (a new period, a Saturday column) lands everywhere at once.

The plain-text equivalent lives in ``timetable_service.as_text`` rather than
here, so the CLI can print a timetable without importing tkinter.
"""

from __future__ import annotations

from collections.abc import Callable
from tkinter import ttk

from education_system.systems.fe_college.interfaces.gui import widgets as w


def render(parent, timetable, ctl, *,
           on_click: Callable | None = None,
           days: int = 6,
           highlight_day: str | None = None) -> ttk.Frame:
    """Draw ``timetable`` as a day × period grid inside ``parent``.

    ``on_click`` receives the :class:`Session` behind a cell when one is
    clicked; without it the cells render as static labels. Two entries in one
    slot are a clash and are flagged as such — a personal timetable should
    never have one, and a college-wide view often does.
    """
    inner, _canvas = w.scrollable(parent)
    grid = ttk.Frame(inner, padding=4)
    grid.pack(fill="both", expand=True)

    weekdays = list(ctl.timetable.days()[:days])
    periods = ctl.timetable.periods()

    for col in range(len(weekdays) + 1):
        grid.columnconfigure(col, weight=0 if col == 0 else 1,
                             uniform="day" if col else "")

    ttk.Label(grid, text="", width=13).grid(row=0, column=0)
    for c, day in enumerate(weekdays, start=1):
        ttk.Label(
            grid, text=day, anchor="center",
            font=("", 10, "bold" if day != highlight_day else "bold"),
            foreground=w.TONE["info"] if day == highlight_day else "",
        ).grid(row=0, column=c, sticky="ew", padx=1, pady=(0, 4))

    for r, (code, start, end) in enumerate(periods, start=1):
        ttk.Label(grid, text=f"{code}\n{start}-{end}", font=("", 9),
                  foreground=w.TONE["muted"]).grid(
            row=r, column=0, sticky="nw", padx=(0, 6), pady=1)
        for c, day in enumerate(weekdays, start=1):
            cell = ttk.Frame(grid, relief="solid", borderwidth=1, padding=3)
            cell.grid(row=r, column=c, sticky="nsew", padx=1, pady=1)
            entries = timetable.at(day, code)
            if not entries:
                # An empty frame collapses to nothing, which breaks the grid's
                # alignment — a blank label holds the row height open.
                ttk.Label(cell, text=" ", font=("", 8)).pack(anchor="w")
                continue
            clash = len(entries) > 1
            for entry in entries:
                if on_click is not None:
                    ttk.Button(
                        cell, text=entry.summary,
                        command=lambda e=entry: on_click(e.session),
                    ).pack(fill="x", pady=1)
                else:
                    ttk.Label(
                        cell, text=entry.summary, wraplength=150,
                        justify="left", font=("", 9),
                    ).pack(anchor="w")
            if clash:
                ttk.Label(cell, text=f"⚠ {len(entries)} clash",
                          foreground=w.TONE["bad"], font=("", 8)).pack(anchor="w")
    return grid


__all__ = ["render"]
