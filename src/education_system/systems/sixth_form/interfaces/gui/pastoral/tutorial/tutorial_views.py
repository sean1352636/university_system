"""Tkinter window: Tutorial & PSHE Programme and personal-tutor 1:1s.

Tabs: Programme (topics), Sessions (per tutor group, with the register),
Coverage, Overdue Sessions, Catch-up, 1:1 Meetings, Agreed Actions and
Not Seen. Data calls go through ``tutorial``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox
from typing import Any

from education_system.platform.delivery.gui import window_sizing
from education_system.systems.sixth_form.domain.pastoral._records import Col, today
from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
    tutor_groups as _tg,
)
from education_system.systems.sixth_form.domain.pastoral.tutorial import (
    tutorial as data,
)
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable
from education_system.systems.sixth_form.interfaces.gui.pastoral._pastoral_ui import (
    ReportTab, make_window, staff_col, swap_cols, user_error,
)
from education_system.systems.sixth_form.interfaces.gui.pastoral._records_ui import (
    RecordTab, ask_form, open_records_window,
)

logger = logging.getLogger(__name__)

_TAGS = {"overdue": ("#ffd1d1", "#8c0d0d"), "done": ("#e6f7e6", "#0d6b2a"),
         "muted": ("#eeeeee", "#555555")}


def _group_labels() -> tuple[str, ...]:
    return tuple(f"{g.tutor_group_id} — {g.name}" for g in _tg.list_groups())


def _group_id(label: str | None) -> int | None:
    s = (label or "").split(" — ", 1)[0].strip()
    return int(s) if s.isdigit() else None


# ── Register dialog ─────────────────────────────────────────────────

def open_register(parent: tk.Misc, delivery_id: int,
                  on_saved: Any = None) -> None:
    d = data.get_delivery(delivery_id)
    if d is None:
        raise ValueError(f"No session #{delivery_id}")
    lines = data.register_for(delivery_id)
    if not lines:
        raise ValueError("Nobody is in this tutor group to register")
    top = tk.Toplevel(parent)
    top.title(f"Register — {d.group_name}: {d.topic_title}")
    window_sizing.fit(top, "760x640", (520, 400))
    top.transient(parent)

    bar = ttk.Frame(top, padding=(10, 8))
    bar.pack(side="bottom", fill="x")
    head = ttk.Frame(top, padding=(10, 8))
    head.pack(side="top", fill="x")
    ttk.Label(head, text="Delivered on:").pack(side="left")
    on_var = tk.StringVar(value=d.delivered_on or today())
    ttk.Entry(head, textvariable=on_var, width=12).pack(side="left",
                                                        padx=(2, 12))
    ttk.Label(head, text="Delivered by:").pack(side="left")
    by_var = tk.StringVar(value=d.delivered_by or "")
    ttk.Entry(head, textvariable=by_var, width=26).pack(side="left", padx=2)

    body = ttk.Frame(top, padding=(10, 0))
    body.pack(fill="both", expand=True)
    canvas = tk.Canvas(body, highlightthickness=0)
    sb = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
    grid = ttk.Frame(canvas)
    grid.bind("<Configure>", lambda _e: canvas.configure(
        scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=grid, anchor="nw")
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    marks: dict[str, tk.StringVar] = {}
    notes: dict[str, tk.StringVar] = {}
    for i, ln in enumerate(lines):
        ttk.Label(grid, text=f"{ln.student_id}  {ln.student_name}").grid(
            row=i, column=0, sticky="w", padx=4, pady=2)
        mv = tk.StringVar(value=ln.mark or "Present")
        ttk.Combobox(grid, textvariable=mv, values=data.MARKS,
                     state="readonly", width=10).grid(row=i, column=1,
                                                      padx=4)
        nv = tk.StringVar(value=ln.note or "")
        ttk.Entry(grid, textvariable=nv, width=30).grid(row=i, column=2,
                                                        padx=4)
        marks[ln.student_id] = mv
        notes[ln.student_id] = nv

    def save() -> None:
        try:
            data.save_register(
                delivery_id, {k: v.get() for k, v in marks.items()},
                notes={k: v.get() for k, v in notes.items()},
                delivered_on=on_var.get().strip() or None,
                delivered_by=by_var.get().strip() or None)
        except Exception as exc:
            user_error(top, "Register", exc)
            return
        top.destroy()
        if on_saved:
            on_saved()

    def all_present() -> None:
        for v in marks.values():
            v.set("Present")

    ttk.Button(bar, text="Save register", command=save).pack(side="right")
    ttk.Button(bar, text="Cancel", command=top.destroy).pack(
        side="right", padx=6)
    ttk.Button(bar, text="All present", command=all_present).pack(
        side="left")
    grab_when_viewable(top)


# ── Actions ─────────────────────────────────────────────────────────

def _plan(tab: RecordTab, topic: Any) -> None:
    def save(v: dict[str, Any]) -> Any:
        ids = None
        if v.get("group"):
            ids = [_group_id(v["group"])]
        made = data.plan_for_groups(topic.topic_id, group_ids=ids,
                                    planned_date=v["date"] or None)
        messagebox.showinfo("Tutorial", f"Planned for {len(made)} group(s) "
                            "(groups that already have it were skipped).",
                            parent=tab.frame)
        return made
    ask_form(tab.frame, f"Plan sessions — {topic.title}",
             (Col("date", "Planned for (blank = week commencing)", "date"),
              Col("group", "Only this group (blank = all in year)",
                  "choice", choices=_group_labels())),
             on_save=save)


def _copy(tab: RecordTab, _row: Any) -> None:
    year = data.current_academic_year()
    start = int(year[:4])
    nxt = f"{start + 1}/{(start + 2) % 100:02d}"

    def save(v: dict[str, Any]) -> Any:
        n = data.copy_programme(v["from_year"], v["to_year"])
        messagebox.showinfo("Tutorial", f"Copied {n} topic(s).",
                            parent=tab.frame)
        return n
    ask_form(tab.frame, "Copy programme to another year",
             (Col("from_year", "From year", required=True, default=year),
              Col("to_year", "To year", required=True, default=nxt)),
             on_save=save)


def _register(tab: RecordTab, d: Any) -> None:
    open_register(tab.frame, d.delivery_id, on_saved=tab.refresh)


def _delivery_tag(d: Any) -> str | None:
    if d.status == data.DELIVERY_DONE:
        return "done"
    if d.status == "Cancelled":
        return "muted"
    if d.planned_date and d.planned_date < today():
        return "overdue"
    return None


def _meeting_actions(tab: RecordTab, m: Any) -> None:
    open_records_window(
        tab.frame, f"Agreed actions — 1:1 #{m.meeting_id} ({m.student_id})",
        data.ACTION_SPEC, tab_title="Agreed Actions",
        load=lambda _f: data.list_actions(meeting_id=m.meeting_id),
        create=data.add_action, update=data.update_action,
        delete=data.delete_action,
        new_defaults=lambda _t: {"meeting_id": m.meeting_id},
        row_tag=lambda a: "overdue" if a.overdue else None,
        tag_colours=_TAGS)


def _add_action(tab: RecordTab, m: Any) -> None:
    ask_form(tab.frame, f"Agreed action — 1:1 #{m.meeting_id}",
             data.ACTION_SPEC.cols, initial={"meeting_id": m.meeting_id},
             on_save=data.add_action)


def _follow_up(tab: RecordTab, m: Any) -> None:
    ask_form(tab.frame, f"Follow-up done — 1:1 #{m.meeting_id}",
             (Col("on", "Followed up on", "date", default=today),
              Col("notes", "Notes", "multiline")),
             on_save=lambda v: data.complete_follow_up(
                 m.meeting_id, on=v["on"] or None, notes=v["notes"]))


def _action_done(tab: RecordTab, a: Any) -> None:
    ask_form(tab.frame, f"Close action #{a.action_id}",
             (Col("status", "Outcome", "choice", required=True,
                  choices=tuple(s for s in data.ACTION_STATUSES
                                if s != data.ACTION_OPEN), default="Done"),
              Col("notes", "Notes", "multiline")),
             on_save=lambda v: data.complete_action(
                 a.action_id, status=v["status"], notes=v["notes"]))


# ── Window ──────────────────────────────────────────────────────────

def open_tutorial_window(parent=None) -> None:
    data.init_db()
    win, nb = make_window(parent, "Tutorial & PSHE Programme")
    year = data.current_academic_year()

    RecordTab(
        nb, "Programme", data.TOPIC_SPEC,
        load=lambda f: data.list_topics(
            academic_year=f.get("year") or None,
            year_group=f.get("year_group") or None,
            term=f.get("term") or None, strand=f.get("strand") or None,
            required_only=bool(f.get("required"))),
        create=data.create_topic, update=data.update_topic,
        delete=data.delete_topic,
        new_defaults=lambda _t: {"academic_year": year},
        filters=(Col("year", "Year (2026/27)"),
                 Col("year_group", "Year group", "choice",
                     choices=data.YEAR_GROUP_CHOICES),
                 Col("term", "Term", "choice", choices=data.TERMS),
                 Col("strand", "Strand", "choice", choices=data.STRANDS),
                 Col("required", "Required only", "bool")),
        actions=(("Plan for Groups…", _plan, True),
                 ("Copy Programme…", _copy, False)),
        intro=("The planned tutorial / PSHE curriculum by term and week. "
               "'Plan for Groups' creates a session for every tutor group "
               "in the topic's year group."))

    RecordTab(
        nb, "Sessions", data.DELIVERY_SPEC,
        load=lambda f: data.list_deliveries(
            academic_year=f.get("year") or None,
            tutor_group_id=_group_id(f.get("group")),
            status=f.get("status") or None),
        update=data.update_delivery, delete=data.delete_delivery,
        columns=(("#", lambda d: d.delivery_id, 50),
                 ("Group", lambda d: d.group_name, 90),
                 ("Topic", lambda d: d.topic_title, 280),
                 ("Status", lambda d: d.status, 90),
                 ("Planned", lambda d: d.planned_date, 95),
                 ("Delivered", lambda d: d.delivered_on, 95),
                 ("By", lambda d: d.delivered_by, 150),
                 ("Present", lambda d: f"{d.present}/{d.marked}"
                  if d.marked else "", 70)),
        filters=(Col("year", "Year (2026/27)"),
                 Col("group", "Tutor group", "choice",
                     choices=_group_labels()),
                 Col("status", "Status", "choice",
                     choices=data.DELIVERY_STATUSES)),
        actions=(("Take Register…", _register, True),),
        row_tag=_delivery_tag, tag_colours=_TAGS,
        intro=("Each topic per tutor group. Take the register to mark it "
               "delivered. Red = planned date passed."))

    def coverage(f: dict[str, str]) -> list[str]:
        yr = f.get("year") or year
        groups, rows = data.coverage(yr, year_group=f.get("yg") or None)
        if not rows:
            return [f"No topics planned for {yr}."]
        w = max(8, *(len(g) for g in groups)) if groups else 8
        head = f"{'Term/wk':<10}{'Topic':<40}" + "".join(
            f"{g[:w]:<{w + 2}}" for g in groups) + "Done"
        out = [f"Coverage {yr}  (D = delivered, P = planned, C = cancelled,"
               " - = not planned, blank = other year)", "", head,
               "-" * len(head)]
        abbr = {"Delivered": "D", "Planned": "P", "Cancelled": "C",
                "—": "-", "n/a": ""}
        for r in rows:
            t = r.topic
            mark = "*" if t.required else " "
            out.append(f"{t.term[:2]} {t.week:<6}{mark}{t.title[:38]:<39}"
                       + "".join(f"{abbr.get(r.by_group[g], '?'):<{w + 2}}"
                                 for g in groups) + str(r.delivered))
        out += ["", "* = required content"]
        return out

    ReportTab(nb, "Coverage", coverage,
              filters=(("year", "Year", year), ("yg", "Year group", "")))

    RecordTab(
        nb, "Overdue Sessions", None,
        load=lambda f: data.overdue_sessions(f.get("year") or None),
        columns=(("Group", lambda r: r.group_name, 90),
                 ("Week commencing", lambda r: r.topic.week_commencing, 110),
                 ("Topic", lambda r: r.topic.title, 300),
                 ("Strand", lambda r: r.topic.strand, 200),
                 ("Required", lambda r: r.topic.required, 70),
                 ("State", lambda r: r.status, 100)),
        filters=(Col("year", "Year (2026/27)"),),
        row_id=lambda r: f"{r.topic.topic_id}:{r.group_name}",
        intro="Topics whose week has passed that a group has not had.")

    RecordTab(
        nb, "Catch-up", None,
        load=lambda f: data.catch_up_list(f.get("year") or None),
        columns=(("Student", lambda r: r.student_id, 90),
                 ("Name", lambda r: r.student_name, 170),
                 ("Topic", lambda r: r.topic_title, 280),
                 ("Strand", lambda r: r.strand, 200),
                 ("Group", lambda r: r.group_name, 90),
                 ("Session", lambda r: r.session_date, 95),
                 ("Mark", lambda r: r.mark, 70)),
        filters=(Col("year", "Year (2026/27)"),),
        row_id=lambda r: f"{r.student_id}:{r.topic_id}",
        intro=("Learners who missed required content and have not been "
               "present at another session of it."))

    RecordTab(
        nb, "1:1 Meetings", data.MEETING_SPEC,
        load=lambda f: data.list_meetings(
            student_id=f.get("student_id") or None,
            follow_up_due_only=bool(f.get("due"))),
        create=data.create_meeting, update=data.update_meeting,
        delete=data.delete_meeting,
        form_cols=swap_cols(data.MEETING_SPEC.cols, {
            "tutor_staff_id": staff_col("tutor_staff_id",
                                        "Tutor (blank = me)")}),
        filters=(Col("student_id", "Student", "student"),
                 Col("due", "Follow-up due", "bool")),
        actions=(("Agreed Actions…", _meeting_actions, True),
                 ("Add Action", _add_action, True),
                 ("Follow-up Done", _follow_up, True)),
        row_tag=lambda m: "overdue" if m.follow_up_due else None,
        tag_colours=_TAGS,
        intro=("Personal tutor 1:1 records. Red = follow-up date reached "
               "and not done."))

    RecordTab(
        nb, "Agreed Actions", data.ACTION_SPEC,
        load=lambda f: data.list_actions(
            student_id=f.get("student_id") or None,
            open_only=bool(f.get("open")),
            overdue_only=bool(f.get("overdue"))),
        update=data.update_action, delete=data.delete_action,
        filters=(Col("student_id", "Student", "student"),
                 Col("open", "Open only", "bool", default=True),
                 Col("overdue", "Overdue only", "bool")),
        actions=(("Close Action", _action_done, True),),
        row_tag=lambda a: "overdue" if a.overdue else None,
        tag_colours=_TAGS)

    term_start = (_dt.date.today() - _dt.timedelta(days=42)).isoformat()
    RecordTab(
        nb, "Not Seen", None,
        load=lambda f: data.students_not_seen(
            since=f.get("since") or term_start,
            tutor_group_id=_group_id(f.get("group"))),
        columns=(("Student", lambda r: r.student_id, 90),
                 ("Name", lambda r: r.student_name, 180),
                 ("Group", lambda r: r.group_name, 90),
                 ("Tutor", lambda r: r.tutor, 160),
                 ("Last 1:1", lambda r: r.last_meeting or "never", 100)),
        filters=(Col("since", "Since (blank = 6 weeks)", "date"),
                 Col("group", "Tutor group", "choice",
                     choices=_group_labels())),
        row_id=lambda r: r.student_id,
        intro="Current tutor-group members with no 1:1 since the date.")
