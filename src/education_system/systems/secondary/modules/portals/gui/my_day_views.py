"""The staff portal page ("My Day") - the first page staff see after sign-in.

Read from :mod:`modules.portals.domain.my_day`. Each box has a button that opens the screen
where the work is done, through the main window's normal menu handler (so
the same access rules apply as clicking it in the sidebar).
"""

from __future__ import annotations

import logging
from datetime import datetime
from tkinter import ttk
from typing import Any

from education_system.systems.secondary.modules.portals.domain import my_day as MD
from education_system.systems.secondary.core.permissions.access import Principal

logger = logging.getLogger(__name__)


def _date(iso: str | None) -> str:
    try:
        return datetime.fromisoformat(str(iso)[:10]).strftime("%a %d %b") if iso else ""
    except ValueError:
        return str(iso)


def _box(parent, title: str, count: int | None = None) -> ttk.LabelFrame:
    box = ttk.LabelFrame(parent, text=title + (f" ({count})" if count else ""), padding=8)
    return box


def _line(parent, text: str, colour: str = "") -> None:
    ttk.Label(parent, text=text, foreground=colour, wraplength=520, justify="left").pack(
        anchor="w")


def _open(parent, app, key: str, label: str, text: str | None = None) -> None:
    ttk.Button(parent, text=text or f"Open {label}",
               command=app._handler(key, label)).pack(anchor="w", pady=(6, 0))


def draw_my_day(parent: ttk.Frame, *, principal: Principal, app: Any) -> None:
    from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
    d = MD.day(principal)
    now = datetime.now()
    greet = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 18 \
        else "Good evening"
    head = ttk.Frame(parent)
    head.pack(fill="x", pady=(0, 10))
    ttk.Label(head, text=f"{greet}, {principal.username}", font=("", 18, "bold")).pack(
        side="left")
    ttk.Button(head, text="↻ Refresh", command=lambda: app.open_staff_portal()).pack(
        side="right")
    ttk.Button(head, text="🏠 School dashboard", command=app._show_welcome).pack(
        side="right", padx=6)
    ttk.Label(parent, text="My Day · " + d["day"].strftime("%A %d %B %Y")
              + (f" · {d['label']}" if d["label"] else ""), foreground="#666").pack(
        anchor="w", pady=(0, 8))

    grid = ttk.Frame(parent)
    grid.pack(fill="both", expand=True)
    for c in range(2):
        grid.columnconfigure(c, weight=1, uniform="md")
    cells: list[ttk.LabelFrame] = []

    def place(box: ttk.LabelFrame) -> None:
        i = len(cells)
        box.grid(row=i // 2, column=i % 2, sticky="nsew", padx=4, pady=4)
        cells.append(box)

    # Lessons
    periods = {p.period: p for p in _safe_periods(TT)}
    box = _box(grid, "My lessons today", len(d["lessons"]))
    if not d["lessons"]:
        _line(box, "No lessons on your timetable today.", "#777")
    for lesson, taken in d["lessons"]:
        p = periods.get(lesson.period)
        _line(box, f"{(p.label if p else 'P' + str(lesson.period)):<6} "
                   f"{(p.times if p else ''):<12} {lesson.group_code} {lesson.subject_name}"
                   + (f" · {lesson.room}" if lesson.room else "")
                   + ("   ✓ register" if taken else "   register not taken"),
              "" if taken else "#a60")
    _open(box, app, "attendance", "Registers & Attendance", "Take registers")
    place(box)

    # Form
    box = _box(grid, "My form")
    if not d["forms"]:
        _line(box, "You aren't down as a form tutor.", "#777")
    for r in d["registers"]:
        f = r["form"]
        _line(box, f"{f.year_group}{f.name} {r['session']} register: "
                   + ("complete" if r["complete"] else f"{r['marked']}/{r['on_roll']} marked"),
              "" if r["complete"] else "#a60")
    for c in d.get("suspended") or []:
        _line(box, f"Out today: {c.pupil_name} - {c.case_type.lower()} ({c.period})", "#a60")
    for b in d.get("trips") or []:
        _line(box, f"Away on a trip: {b.pupil_name} - {b.trip_title}", "#06a")
    for f in d["forms"]:
        ttk.Button(box, text=f"Open form {f.year_group}{f.name}",
                   command=lambda f=f: app.show_form_group(f.form_id)).pack(anchor="w",
                                                                            pady=(4, 0))
    place(box)

    # Cover
    cv = d["cover"]
    box = _box(grid, "Cover (next 7 days)", len(cv["doing"]) + len(cv["mine"]))
    if not cv["doing"] and not cv["mine"]:
        _line(box, "No cover for you or your lessons.", "#777")
    for c in cv["doing"]:
        _line(box, f"Covering: {_date(c.date)} P{c.period} {c.group_code} "
                   f"{c.subject_code or ''} for {c.absent_name}"
                   + (f" · room {c.room}" if c.room else "")
                   + ("" if c.work_set else " · no work set yet"))
    for c in cv["mine"]:
        _line(box, f"Your lesson {_date(c.date)} P{c.period} {c.group_code}: "
                   f"{c.cover_name or 'cover not arranged yet'}"
                   + ("" if c.work_set else " · set the work"),
              "" if c.cover_name and c.work_set else "#a60")
    _open(box, app, "cover", "Cover")
    place(box)

    # Marking
    m = d["marking"]
    total = len(m["homework"]) + len(m["gradebook"]) + len(m["points"]) + len(m["mocks"])
    box = _box(grid, "Marking and data to enter", total)
    if not total:
        _line(box, "Nothing waiting. 🎉", "#060")
    for t, n in m["homework"]:
        _line(box, f"Homework: {t.title} ({t.for_label}) - {n} handed in to mark")
    for a, n in m["gradebook"]:
        _line(box, f"Gradebook: {a.name} ({a.for_label}, {_date(a.assessment_date)}) - "
                   f"{n} to mark")
    for pt, row in m["points"]:
        _line(box, f"{pt.name}: {row['group'].code} {row['done']}/{row['pupils']} grades "
                   + (f"(deadline {_date(pt.deadline)})" if pt.deadline else ""), "#a60")
    for s, p, n in m["mocks"]:
        _line(box, f"Mock {s.name}: {p.label} - {n} of your pupils to mark")
    bar = ttk.Frame(box)
    bar.pack(anchor="w")
    for key, label in (("homework", "Homework"), ("gradebook", "Gradebook"),
                       ("assessment_points", "Assessment Points"), ("mock_exams", "Mock Exams")):
        ttk.Button(bar, text=label, command=app._handler(key, label)).pack(
            side="left", padx=(0, 4), pady=(6, 0))
    place(box)

    # Homework set
    box = _box(grid, "Homework I've set - due soon", len(d["homework_set"]))
    if not d["homework_set"]:
        _line(box, "Nothing due in the next week.", "#777")
    for t in d["homework_set"]:
        _line(box, f"{_date(t.due_date)}  {t.for_label} {t.subject_code}: {t.title}",
              "#a00" if t.overdue else "")
    _open(box, app, "homework", "Homework")
    place(box)

    # Clubs + events
    box = _box(grid, "Clubs today and coming up")
    dts = d.get("detentions") or []
    if dts:
        _line(box, f"Detention to supervise: {len(dts)} pupil(s) "
                   + ", ".join(sorted({x.start_time or "" for x in dts} - {""}))
                   + (f" · {dts[0].location}" if dts[0].location else ""), "#a60")
        ttk.Button(box, text="Detentions", command=app._handler("detentions", "Detentions")
                   ).pack(anchor="w", pady=(2, 4))
    for c in d["clubs"]:
        _line(box, f"Your club: {c.name} {c.time_label}" + (f" · {c.room}" if c.room else ""))
    if not d["events"] and not d["clubs"]:
        _line(box, "No clubs or staff events this week.", "#777")
    for e in d["events"]:
        _line(box, f"{_date(e.start_date)}  {e.title}"
              + (f" · {e.location}" if e.location else "")
              + (" (cancelled)" if e.status == "Cancelled" else ""))
    _open(box, app, "academic_year", "Academic Year & Calendar", "Open calendar")
    place(box)

    from education_system.systems.secondary.modules.portals.gui.my_day_linked import draw_linked
    draw_linked(grid, place, d, principal=principal, app=app,
                refresh=lambda: app.open_staff_portal())

    if d["children"]:
        box = _box(grid, "My children at this school")
        for p in d["children"]:
            _line(box, f"{p.display_name} - Year {p.year_group}"
                  + (f" {p.form_group}" if p.form_group else ""))

        def open_parent() -> None:
            from education_system.systems.secondary.modules.portals.gui import portal_views
            portal_views.open_portal_window(parent, principal=principal)
        ttk.Button(box, text="Open parent portal", command=open_parent).pack(anchor="w",
                                                                           pady=(6, 0))
        place(box)


def _safe_periods(TT) -> list:
    try:
        return TT.periods()
    except Exception:  # noqa: BLE001
        logger.exception("Periods failed")
        return []


__all__ = ["draw_my_day"]
