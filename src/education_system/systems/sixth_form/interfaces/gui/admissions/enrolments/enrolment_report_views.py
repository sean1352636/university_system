"""Enrolment reports and analytics (dashboard, cohort, retention, tutor
roster, withdrawals, year-on-year)."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any

from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as data
from education_system.systems.sixth_form.domain.admissions.enrolments.enrolments import (
    Enrolment,
    STATUSES,
)

from education_system.platform.delivery.gui.parented_dialogs import messagebox

from .enrolment_common import (
    _choose_from,
    _clear,
    _default_academic_year,
    _heading,
    _next_academic_year,
    _render_status_bar_chart,
    _status_counts,
    _STATUS_COLOURS,
    _student_name_map,
    _year_choices,
    back_to_directory,
)

logger = logging.getLogger(__name__)


def open_enrolment_dashboard(gui) -> None:
    """Feature #21 — summary cards plus a status bar chart."""
    frame = _clear(gui)
    _heading(frame, "Enrolment Dashboard")
    try:
        rows = data.list_enrolments()
    except Exception as exc:
        ttk.Label(frame, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
        return

    counts = _status_counts(rows)
    by_year: dict[str, int] = {}
    by_yg: dict[int, int] = {}
    for e in rows:
        by_year[e.academic_year] = by_year.get(e.academic_year, 0) + 1
        by_yg[e.year_group] = by_yg.get(e.year_group, 0) + 1

    cards = ttk.Frame(frame)
    cards.pack(anchor="w", pady=(4, 10))

    def card(parent, title: str, value: str, colour: str) -> None:
        box = tk.Frame(parent, bg=colour, padx=14, pady=10)
        box.pack(side="left", padx=(0, 10))
        tk.Label(box, text=value, fg="white", bg=colour,
                 font=("", 18, "bold")).pack()
        tk.Label(box, text=title, fg="white", bg=colour).pack()

    card(cards, "Total", str(len(rows)), "#34495e")
    card(cards, "Enrolled", str(counts.get("Enrolled", 0)), _STATUS_COLOURS["Enrolled"])
    card(cards, "Pending", str(counts.get("Pending", 0)), _STATUS_COLOURS["Pending"])
    card(cards, "Withdrawn", str(counts.get("Withdrawn", 0)), _STATUS_COLOURS["Withdrawn"])
    card(cards, "Completed", str(counts.get("Completed", 0)), _STATUS_COLOURS["Completed"])

    ttk.Label(frame, text="By status", font=("", 11, "bold")).pack(anchor="w")
    chart = ttk.Frame(frame)
    chart.pack(anchor="w", pady=(2, 8))
    _render_status_bar_chart(chart, counts)  # feature #25

    breakdown = "  ·  ".join(f"Year {yg}: {n}" for yg, n in sorted(by_yg.items()))
    ttk.Label(frame, text=f"By year group — {breakdown or '—'}").pack(anchor="w")
    years = "  ·  ".join(f"{y}: {n}" for y, n in sorted(by_year.items(), reverse=True))
    ttk.Label(frame, text=f"By academic year — {years or '—'}").pack(anchor="w", pady=(2, 0))

    ttk.Button(frame, text="Back to Directory",
               command=lambda: back_to_directory(gui)).pack(anchor="w", pady=(12, 0))
    gui.status_var.set("Enrolment dashboard")


def open_cohort_report(gui, academic_year: str | None = None) -> None:
    """Feature #22 — headcount breakdown for a single academic year."""
    frame = _clear(gui)
    year = academic_year or _default_academic_year()
    _heading(frame, f"Cohort Report — {year}")
    try:
        rows = data.list_enrolments(academic_year=year)
    except Exception as exc:
        ttk.Label(frame, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
        return
    counts = _status_counts(rows)
    by_yg: dict[int, dict[str, int]] = {}
    for e in rows:
        by_yg.setdefault(e.year_group, {s: 0 for s in STATUSES})[e.status] += 1

    ttk.Label(frame, text=f"{len(rows)} enrolment(s) in {year}.",
              foreground="#555").pack(anchor="w", pady=(0, 6))
    tree = ttk.Treeview(frame, columns=("yg", *STATUSES, "total"),
                        show="headings", height=6)
    tree.heading("yg", text="Year group")
    tree.column("yg", width=90)
    for s in STATUSES:
        tree.heading(s, text=s)
        tree.column(s, width=90, anchor="center")
    tree.heading("total", text="Total")
    tree.column("total", width=70, anchor="center")
    tree.pack(anchor="w", fill="x")
    for yg in sorted(by_yg):
        c = by_yg[yg]
        tree.insert("", "end", values=(
            f"Year {yg}", *[c.get(s, 0) for s in STATUSES], sum(c.values())))
    tree.insert("", "end", values=(
        "All", *[counts.get(s, 0) for s in STATUSES], len(rows)))

    ttk.Button(frame, text="Back to Directory",
               command=lambda: back_to_directory(gui)).pack(anchor="w", pady=(12, 0))
    gui.status_var.set(f"Cohort report {year}")


def open_retention_report(gui) -> None:
    """Feature #23 — Year 12 → 13 progression / dropout rate per academic year."""
    frame = _clear(gui)
    _heading(frame, "Retention (Year 12 → 13)")
    try:
        rows = data.list_enrolments()
    except Exception as exc:
        ttk.Label(frame, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
        return

    # Map each student's set of (year, year_group).
    by_student: dict[str, set[tuple[str, int]]] = {}
    y12_years: set[str] = set()
    for e in rows:
        by_student.setdefault(e.student_id, set()).add((e.academic_year, e.year_group))
        if e.year_group == 12:
            y12_years.add(e.academic_year)

    tree = ttk.Treeview(frame, columns=("year", "y12", "progressed", "rate"),
                        show="headings", height=8)
    for col, (text, w) in {
        "year": ("Y12 cohort year", 130), "y12": ("Y12 count", 90),
        "progressed": ("Progressed to Y13", 140), "rate": ("Rate", 80),
    }.items():
        tree.heading(col, text=text)
        tree.column(col, width=w, anchor="center")
    tree.pack(anchor="w", fill="x", pady=(6, 0))

    for y12_year in sorted(y12_years, reverse=True):
        next_year = _next_academic_year(y12_year)
        cohort = [sid for sid, pairs in by_student.items()
                  if (y12_year, 12) in pairs]
        progressed = [sid for sid in cohort
                      if (next_year, 13) in by_student.get(sid, set())]
        rate = (100 * len(progressed) / len(cohort)) if cohort else 0
        tree.insert("", "end", values=(
            y12_year, len(cohort), len(progressed), f"{rate:.0f}%"))

    ttk.Button(frame, text="Back to Directory",
               command=lambda: back_to_directory(gui)).pack(anchor="w", pady=(12, 0))
    gui.status_var.set("Retention report")


def _export_tutor_group_pdf(gui, tutor_group: str) -> None:
    from .enrolment_io_views import export_tutor_group_pdf
    export_tutor_group_pdf(gui, tutor_group)


def open_tutor_group_roster(gui, tutor_group: str,
                            academic_year: str | None = None) -> None:
    """Feature #24 — class list for one tutor group (printable via PDF),
    optionally for one academic year."""
    frame = _clear(gui)
    _heading(frame, f"Tutor Group Roster — {tutor_group}"
             + (f" ({academic_year})" if academic_year else ""))
    names = _student_name_map()
    try:
        rows = [e for e in data.list_enrolments(academic_year=academic_year)
                if (e.tutor_group or "").lower() == tutor_group.lower()]
    except Exception as exc:  # noqa: BLE001 — shown
        ttk.Label(frame, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
        rows = []
    live = sum(1 for e in rows if e.is_live)
    ttk.Label(frame, text=f"{len(rows)} enrolment(s) in {tutor_group}, {live} live.",
              foreground="#555").pack(anchor="w", pady=(0, 6))
    bar = ttk.Frame(frame)
    bar.pack(side="bottom", anchor="w", pady=(12, 0))
    tree = ttk.Treeview(frame, columns=("sid", "name", "year", "yg", "status"),
                        show="headings", height=12)
    for col, (text, w) in {
        "sid": ("Student ID", 110), "name": ("Name", 220),
        "year": ("Year", 90), "yg": ("YG", 50), "status": ("Status", 100),
    }.items():
        tree.heading(col, text=text)
        tree.column(col, width=w)
    tree.pack(anchor="w", fill="both", expand=True)
    for e in sorted(rows, key=lambda r: names.get(r.student_id, "")):
        tree.insert("", "end", values=(
            e.student_id, names.get(e.student_id, "—"), e.academic_year,
            e.year_group, e.status))

    ttk.Button(bar, text="Export PDF",
               command=lambda: _export_tutor_group_pdf(gui, tutor_group)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Other Group…",
               command=lambda: open_tutor_group_roster_picker(gui, academic_year)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Back to Directory",
               command=lambda: back_to_directory(gui)).pack(side="left")
    gui.status_var.set(f"Roster {tutor_group}")


def roster_group_names(academic_year: str | None = None) -> list[str]:
    """Tutor groups to offer: the real ones set up in Tutor Groups, plus
    any name used on an enrolment of the year."""
    names: set[str] = set()
    try:
        from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
            tutor_groups,
        )
        names |= {g.name for g in tutor_groups.list_groups()}
    except Exception:  # noqa: BLE001 — enrolment names still offered
        logger.exception("Tutor groups not read")
    names |= {e.tutor_group for e in data.list_enrolments(academic_year=academic_year)
              if e.tutor_group}
    return sorted(names)


def open_tutor_group_roster_picker(gui, academic_year: str | None = None) -> None:
    """Pick a tutor group (and year), then show its roster."""
    try:
        groups = roster_group_names(academic_year)
    except Exception as exc:  # noqa: BLE001
        messagebox.showerror("Tutor Group Roster", str(exc), parent=gui.root)
        return
    if not groups:
        messagebox.showinfo("Tutor Group Roster", "No tutor groups are set up "
                            "and no enrolment names one"
                            + (f" in {academic_year}" if academic_year else "") + ".",
                            parent=gui.root)
        return
    picked = _choose_from(gui, "Tutor Group Roster", "Tutor group:", groups, groups[0])
    if picked:
        from education_system.systems.sixth_form.interfaces.gui import popout
        popout.show_page(
            gui, f"Tutor Group Roster — {picked}",
            lambda g: open_tutor_group_roster(g, picked, academic_year))


def open_withdrawal_analysis(gui) -> None:
    """Feature #26 — all withdrawn enrolments with their captured reasons."""
    frame = _clear(gui)
    _heading(frame, "Withdrawal Analysis")
    names = _student_name_map()
    try:
        rows = data.list_enrolments(status="Withdrawn")
    except Exception as exc:
        ttk.Label(frame, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
        return
    ttk.Label(frame, text=f"{len(rows)} withdrawn enrolment(s).",
              foreground="#555").pack(anchor="w", pady=(0, 6))
    tree = ttk.Treeview(frame, columns=("sid", "name", "year", "date", "reason",
                                        "detail"),
                        show="headings", height=12)
    for col, (text, w) in {
        "sid": ("Student", 90), "name": ("Name", 160), "year": ("Year", 80),
        "date": ("Last day", 95), "reason": ("ILR reason", 300),
        "detail": ("Detail / notes", 320),
    }.items():
        tree.heading(col, text=text)
        tree.column(col, width=w)
    tree.pack(anchor="w", fill="x")
    by_reason: dict[str, int] = {}
    for e in rows:
        label = e.withdrawal_reason_label or "Not recorded"
        by_reason[label] = by_reason.get(label, 0) + 1
        detail = (e.withdrawal_detail or e.notes or "").replace("\n", " ⏎ ")
        tree.insert("", "end", values=(
            e.student_id, names.get(e.student_id, "—"), e.academic_year,
            e.withdrawal_date or "—", label, detail or "—"))
    if by_reason:
        ttk.Label(frame, text="By reason — " + "  ·  ".join(
            f"{k}: {v}" for k, v in sorted(by_reason.items(), key=lambda kv: -kv[1])),
            wraplength=1100, justify="left").pack(anchor="w", pady=(6, 0))

    ttk.Button(frame, text="Back to Directory",
               command=lambda: back_to_directory(gui)).pack(anchor="w", pady=(12, 0))
    gui.status_var.set(f"{len(rows)} withdrawal(s)")


def open_year_on_year_comparison(gui) -> None:
    """Feature #27 — headcounts side by side across academic years."""
    frame = _clear(gui)
    _heading(frame, "Year-on-Year Comparison")
    try:
        rows = data.list_enrolments()
    except Exception as exc:
        ttk.Label(frame, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
        return
    per_year: dict[str, dict[str, int]] = {}
    for e in rows:
        bucket = per_year.setdefault(e.academic_year, {s: 0 for s in STATUSES})
        bucket[e.status] += 1

    tree = ttk.Treeview(frame, columns=("year", *STATUSES, "total"),
                        show="headings", height=12)
    tree.heading("year", text="Academic year")
    tree.column("year", width=120)
    for s in STATUSES:
        tree.heading(s, text=s)
        tree.column(s, width=90, anchor="center")
    tree.heading("total", text="Total")
    tree.column("total", width=70, anchor="center")
    tree.pack(anchor="w", fill="x", pady=(6, 0))
    for year in sorted(per_year, reverse=True):
        c = per_year[year]
        tree.insert("", "end", values=(
            year, *[c.get(s, 0) for s in STATUSES], sum(c.values())))

    ttk.Button(frame, text="Back to Directory",
               command=lambda: back_to_directory(gui)).pack(anchor="w", pady=(12, 0))
    gui.status_var.set("Year-on-year comparison")


def _compute_capacity_utilisation(rows: list[Enrolment], capacity: int) -> dict[str, Any]:
    """Feature #28 — active headcount vs a configured cohort capacity."""
    active = sum(1 for e in rows if e.status in ("Enrolled", "Pending"))
    pct = (100 * active / capacity) if capacity else 0.0
    return {
        "active": active,
        "capacity": capacity,
        "free": max(0, capacity - active),
        "utilisation_pct": round(pct, 1),
        "over_capacity": active > capacity,
    }


def open_capacity_utilisation(gui, academic_year: str | None = None,
                              capacity: int | None = None) -> None:
    """Feature #28 — live headcount (Enrolled + Pending) against a cohort
    capacity, for one academic year (or all), per year group too."""
    frame = _clear(gui)
    _heading(frame, "Capacity Utilisation")
    year_var = tk.StringVar(value=academic_year if academic_year is not None
                            else _default_academic_year())
    cap_var = tk.StringVar(value=str(capacity) if capacity else "")
    top = ttk.Frame(frame)
    top.pack(anchor="w", pady=(0, 8))
    ttk.Label(top, text="Academic year:").pack(side="left")
    ttk.Combobox(top, textvariable=year_var, values=["", *_year_choices()],
                 state="readonly", width=10).pack(side="left", padx=(4, 12))
    ttk.Label(top, text="Cohort capacity:").pack(side="left")
    ttk.Spinbox(top, textvariable=cap_var, from_=0, to=10000, width=8).pack(
        side="left", padx=(4, 12))
    out = ttk.Frame(frame)

    def show() -> None:
        for w in out.winfo_children():
            w.destroy()
        try:
            cap = int(cap_var.get().strip())
            if cap < 0:
                raise ValueError
        except ValueError:
            ttk.Label(out, text="Capacity must be a whole number.",
                      foreground="#a33").pack(anchor="w")
            return
        try:
            rows = data.list_enrolments(academic_year=year_var.get().strip() or None)
        except Exception as exc:  # noqa: BLE001 — shown
            ttk.Label(out, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
            return
        stats = _compute_capacity_utilisation(rows, cap)
        for label, value in (("Active (Enrolled + Pending)", stats["active"]),
                             ("Capacity", stats["capacity"]),
                             ("Free places", stats["free"]),
                             ("Utilisation", f"{stats['utilisation_pct']}%")):
            ttk.Label(out, text=f"{label}: {value}").pack(anchor="w")
        if stats["over_capacity"]:
            ttk.Label(out, text="Over capacity!", foreground="#a33",
                      font=("", 10, "bold")).pack(anchor="w", pady=(4, 0))
        by_yg: dict[int, int] = {}
        for e in rows:
            if e.status in data.LIVE_STATUSES:
                by_yg[e.year_group] = by_yg.get(e.year_group, 0) + 1
        ttk.Label(out, text="Active by year group — " + ("  ·  ".join(
            f"Year {yg}: {n}" for yg, n in sorted(by_yg.items())) or "—")).pack(
            anchor="w", pady=(6, 0))
        gui.status_var.set(f"Capacity: {stats['active']} of {cap} "
                           f"({stats['utilisation_pct']}%)")

    ttk.Button(top, text="Show", command=show).pack(side="left")
    out.pack(anchor="w", fill="x")
    ttk.Button(frame, text="Back to Directory",
               command=lambda: back_to_directory(gui)).pack(anchor="w", pady=(12, 0))
    if cap_var.get():
        show()
