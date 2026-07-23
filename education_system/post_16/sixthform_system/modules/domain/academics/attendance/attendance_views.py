"""GUI panels for Sixth Form Attendance.

Tabbed entry point with three tabs:

  * Take register — pick slot + date, fill in the roster, save once.
  * Records — flat directory with filters and per-record edit/delete.
  * Summary — per-student attendance % for a chosen group/date range.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Any
from education_system.post_16.sixthform_system.modules.domain.academics.attendance import attendance
from education_system.post_16.sixthform_system.modules.domain.academics.class_groups import class_groups
from education_system.post_16.sixthform_system.modules.domain.students.students import students
from education_system.post_16.sixthform_system.modules.domain.academics.attendance import attendance as data
from education_system.post_16.sixthform_system.modules.domain.academics.class_groups import class_groups as cg_data
from education_system.post_16.sixthform_system.modules.domain.academics.courses import courses as course_data
from education_system.post_16.sixthform_system.modules.domain.students.students import students as student_data
from education_system.post_16.sixthform_system.modules.domain.academics.timetable import timetable as tt_data
from education_system.post_16.sixthform_system.modules.domain.academics.attendance.attendance import (
    DEFAULT_STATUS,
    STATUSES,
    AttendanceRecord,
    AttendanceSummary,
    ValidationError,
)
from education_system.post_16.sixthform_system.modules.domain.academics.timetable.timetable import day_name

logger = logging.getLogger(__name__)


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _slot_label(slot, group=None, course=None) -> str:
    if group is None:
        group = cg_data.get_group(slot.group_id)
    if course is None and group is not None:
        course = course_data.get_course(group.course_id)
    code = course.course_code if course else f"#{slot.group_id}"
    gname = group.group_name if group else "?"
    return (f"#{slot.slot_id} {day_name(slot.day)} P{slot.period} "
            f"· {code} {gname}")


def _today() -> str:
    return _date.today().isoformat()


# ── Top-level tabbed view ───────────────────────────────────────────

def open_directory(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Attendance")

    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True)

    take_tab = ttk.Frame(nb, padding=8)
    records_tab = ttk.Frame(nb, padding=8)
    summary_tab = ttk.Frame(nb, padding=8)
    nb.add(take_tab,    text="Take register")
    nb.add(records_tab, text="Records")
    nb.add(summary_tab, text="Summary")

    _build_take_tab(gui, take_tab)
    _build_records_tab(gui, records_tab)
    _build_summary_tab(gui, summary_tab)


# ─── Take register tab ──────────────────────────────────────────────

def _build_take_tab(gui, parent: ttk.Frame) -> None:
    slots = tt_data.list_slots()
    groups = {g.group_id: g for g in cg_data.list_groups()}
    courses = {c.course_id: c for c in course_data.list_courses()}
    slot_labels = [
        _slot_label(s, groups.get(s.group_id), courses.get(
            groups[s.group_id].course_id if s.group_id in groups else 0))
        for s in slots
    ]
    slot_by_label = {lbl: s.slot_id for lbl, s in zip(slot_labels, slots)}

    if not slots:
        ttk.Label(
            parent,
            text="No timetable slots yet — create a slot before taking registers.",
            foreground="#a33",
        ).pack(anchor="w")
        return

    # ── Selector bar ──
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))

    slot_var = tk.StringVar(value=slot_labels[0])
    date_var = tk.StringVar(value=_today())

    ttk.Label(bar, text="Slot:").pack(side="left")
    ttk.Combobox(bar, textvariable=slot_var, values=slot_labels,
                 state="readonly", width=58).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Date (YYYY-MM-DD):").pack(side="left")
    ttk.Entry(bar, textvariable=date_var, width=14).pack(
        side="left", padx=(4, 12))

    register_holder = ttk.Frame(parent)
    register_holder.pack(fill="both", expand=True, pady=(0, 8))

    # Row widgets keyed by student_id, kept in scope so submit() can read them.
    row_state: dict[str, dict[str, Any]] = {}

    def load() -> None:
        nonlocal row_state
        for w in register_holder.winfo_children():
            w.destroy()
        row_state = {}

        sid = slot_by_label.get(slot_var.get())
        if sid is None:
            ttk.Label(register_holder, text="Pick a slot.",
                      foreground="#a33").pack(anchor="w")
            return
        try:
            entries = data.register_view(sid, date_var.get())
        except ValidationError as e:
            ttk.Label(register_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("register_view failed")
            ttk.Label(register_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        if not entries:
            ttk.Label(
                register_holder,
                text="This slot's class group has no members yet.",
                foreground="#a33",
            ).pack(anchor="w")
            return

        # Header row
        header = ttk.Frame(register_holder)
        header.pack(fill="x")
        for col, text, width in [
            ("id",      "Student ID",   12),
            ("name",    "Name",         30),
            ("status",  "Status",       18),
            ("late",    "Mins late",     8),
            ("notes",   "Notes",        30),
        ]:
            ttk.Label(header, text=text, font=("", 10, "bold"),
                      width=width, anchor="w").pack(side="left", padx=2)

        for e in entries:
            row = ttk.Frame(register_holder)
            row.pack(fill="x", pady=1)

            ttk.Label(row, text=e.student_id, width=12, anchor="w"
                      ).pack(side="left", padx=2)
            ttk.Label(row, text=e.full_name, width=30, anchor="w"
                      ).pack(side="left", padx=2)

            status_var = tk.StringVar(
                value=e.record.status if e.record else DEFAULT_STATUS)
            late_var = tk.StringVar(
                value=str(e.record.minutes_late)
                if (e.record and e.record.minutes_late is not None) else "")
            notes_var = tk.StringVar(
                value=(e.record.notes or "") if e.record else "")

            ttk.Combobox(row, textvariable=status_var, values=list(STATUSES),
                         state="readonly", width=16
                         ).pack(side="left", padx=2)
            ttk.Entry(row, textvariable=late_var, width=8
                      ).pack(side="left", padx=2)
            ttk.Entry(row, textvariable=notes_var, width=30
                      ).pack(side="left", padx=2)

            row_state[e.student_id] = {
                "status": status_var,
                "minutes_late": late_var,
                "notes": notes_var,
            }

        # Initial-mark helpers
        helpers = ttk.Frame(register_holder)
        helpers.pack(anchor="w", pady=(8, 0))
        for label, status in (("Mark all Present", "Present"),
                              ("Mark all Absent",  "Absent")):
            def make_cmd(s=status) -> None:
                for rs in row_state.values():
                    rs["status"].set(s)
            ttk.Button(helpers, text=label, command=make_cmd
                       ).pack(side="left", padx=(0, 6))

        gui.status_var.set(f"Loaded register: slot #{sid}, {date_var.get()} "
                           f"({len(entries)} student(s))")

    def submit() -> None:
        sid = slot_by_label.get(slot_var.get())
        if sid is None:
            messagebox.showerror("Cannot save",
                                 "Pick a slot.", parent=gui.root)
            return
        if not row_state:
            messagebox.showinfo("Nothing to save",
                                "Load the register first.", parent=gui.root)
            return
        payload: dict[str, dict[str, Any]] = {}
        for sid_s, vs in row_state.items():
            payload[sid_s] = {
                "status":       vs["status"].get(),
                "minutes_late": vs["minutes_late"].get(),
                "notes":        vs["notes"].get(),
            }
        try:
            n = data.save_register(sid, date_var.get(), payload)
        except ValidationError as e:
            logger.warning("save_register rejected: %s", e)
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("save_register crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=gui.root)
            return
        gui.status_var.set(f"Saved register: slot #{sid}, {date_var.get()}")
        messagebox.showinfo(
            "Register saved",
            f"Saved {n} row(s) for slot #{sid} on {date_var.get()}.",
            parent=gui.root,
        )

    actions = ttk.Frame(parent)
    actions.pack(anchor="w", pady=(0, 4))
    ttk.Button(actions, text="Load", command=load
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Save register", command=submit
               ).pack(side="left", padx=(0, 6))

    load()


# ─── Records tab ────────────────────────────────────────────────────

def _build_records_tab(gui, parent: ttk.Frame) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    sid_var = tk.StringVar()
    slot_var = tk.StringVar()
    from_var = tk.StringVar()
    to_var = tk.StringVar()
    status_var = tk.StringVar()

    ttk.Label(filt, text="Student ID:").pack(side="left")
    ttk.Entry(filt, textvariable=sid_var, width=12).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Slot ID:").pack(side="left")
    ttk.Entry(filt, textvariable=slot_var, width=6).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="From:").pack(side="left")
    ttk.Entry(filt, textvariable=from_var, width=12).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="To:").pack(side="left")
    ttk.Entry(filt, textvariable=to_var, width=12).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Status:").pack(side="left")
    ttk.Combobox(filt, textvariable=status_var,
                 values=["", *STATUSES], state="readonly", width=12
                 ).pack(side="left", padx=(4, 4))

    table_holder = ttk.Frame(parent)
    table_holder.pack(fill="both", expand=True)
    summary = ttk.Label(parent, text="", foreground="#555")
    summary.pack(anchor="w", pady=(4, 8))
    actions_holder = ttk.Frame(parent)
    actions_holder.pack(anchor="w", pady=(0, 4))

    def refresh() -> None:
        for w in table_holder.winfo_children():
            w.destroy()
        for w in actions_holder.winfo_children():
            w.destroy()
        try:
            kwargs: dict[str, Any] = {
                "student_id": sid_var.get().strip() or None,
                "status": status_var.get().strip() or None,
                "date_from": from_var.get().strip() or None,
                "date_to": to_var.get().strip() or None,
            }
            if slot_var.get().strip():
                try:
                    kwargs["slot_id"] = int(slot_var.get())
                except ValueError:
                    messagebox.showerror("Bad filter",
                                         "Slot ID must be a number.",
                                         parent=gui.root)
                    return
            rows = data.list_records(**kwargs)
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("list_records failed")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("record_id", "date", "slot", "student", "status",
                "minutes_late", "notes")
        headings = {
            "record_id":    ("#",      50),
            "date":         ("Date",   100),
            "slot":         ("Slot",    60),
            "student":      ("Student", 110),
            "status":       ("Status", 110),
            "minutes_late": ("Mins",    50),
            "notes":        ("Notes",  240),
        }
        tree = ttk.Treeview(table_holder, columns=cols, show="headings", height=14)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        for r in rows:
            tree.insert("", "end", iid=str(r.record_id), values=(
                r.record_id, r.date, r.slot_id, r.student_id,
                r.status,
                r.minutes_late if r.minutes_late is not None else "—",
                r.notes or "",
            ))
        summary.configure(text=f"{len(rows)} record(s).")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _edit_status() -> None:
            rid = _selected()
            if rid is None:
                messagebox.showinfo("No selection",
                                    "Pick a record first.", parent=gui.root)
                return
            _quick_edit_dialog(gui, rid, on_saved=refresh)

        def _delete() -> None:
            rid = _selected()
            if rid is None:
                messagebox.showinfo("No selection",
                                    "Pick a record first.", parent=gui.root)
                return
            if not messagebox.askyesno(
                    "Delete record",
                    f"Delete attendance record #{rid}?",
                    parent=gui.root):
                return
            try:
                data.delete_record(rid)
            except Exception as e:
                logger.exception("delete_record failed")
                messagebox.showerror("Error", f"Could not delete: {e}",
                                     parent=gui.root)
                return
            refresh()

        ttk.Button(actions_holder, text="Edit",
                   command=_edit_status).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Delete",
                   command=_delete).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Refresh",
                   command=refresh).pack(side="left", padx=(12, 0))
        gui.status_var.set(f"Attendance records: {len(rows)} match(es)")

    ttk.Button(filt, text="Apply", command=refresh
               ).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
               command=lambda: (sid_var.set(""), slot_var.set(""),
                                from_var.set(""), to_var.set(""),
                                status_var.set(""), refresh())
               ).pack(side="left", padx=(4, 0))
    refresh()


def _quick_edit_dialog(gui, record_id: int, on_saved) -> None:
    rec = data.get_record(record_id)
    if rec is None:
        messagebox.showerror("Not found", f"No record #{record_id}",
                             parent=gui.root)
        return

    win = tk.Toplevel(gui.root)
    win.title(f"Edit attendance #{record_id}")
    win.transient(gui.root)
    win.after_idle(win.grab_set)

    frm = ttk.Frame(win, padding=12)
    frm.grid()

    status_var = tk.StringVar(value=rec.status)
    late_var = tk.StringVar(value=str(rec.minutes_late) if rec.minutes_late is not None else "")
    notes_var = tk.StringVar(value=rec.notes or "")

    ttk.Label(frm, text=f"{rec.student_id}  ·  slot #{rec.slot_id}  ·  {rec.date}",
              foreground="#555").grid(row=0, column=0, columnspan=2,
                                       sticky="w", pady=(0, 8))
    ttk.Label(frm, text="Status:").grid(row=1, column=0, sticky="e", padx=(0, 6), pady=2)
    ttk.Combobox(frm, textvariable=status_var, values=list(STATUSES),
                 state="readonly", width=18
                 ).grid(row=1, column=1, sticky="w", pady=2)
    ttk.Label(frm, text="Minutes late:").grid(row=2, column=0, sticky="e", padx=(0, 6), pady=2)
    ttk.Entry(frm, textvariable=late_var, width=10
              ).grid(row=2, column=1, sticky="w", pady=2)
    ttk.Label(frm, text="Notes:").grid(row=3, column=0, sticky="e", padx=(0, 6), pady=2)
    ttk.Entry(frm, textvariable=notes_var, width=42
              ).grid(row=3, column=1, sticky="w", pady=2)

    def save() -> None:
        try:
            data.update_record(record_id, {
                "status": status_var.get(),
                "minutes_late": late_var.get(),
                "notes": notes_var.get(),
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("update_record crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()
        on_saved()

    bar = ttk.Frame(frm)
    bar.grid(row=4, column=0, columnspan=2, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


# ─── Summary tab ────────────────────────────────────────────────────

def _build_summary_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))

    groups = cg_data.list_groups()
    courses_by_id = {c.course_id: c for c in course_data.list_courses()}
    group_labels = [
        f"#{g.group_id} {g.group_name} "
        f"({courses_by_id.get(g.course_id).course_code if g.course_id in courses_by_id else '?'})"
        for g in groups
    ]
    group_by_label = {lbl: g.group_id for lbl, g in zip(group_labels, groups)}

    group_var = tk.StringVar(value=group_labels[0] if group_labels else "")
    from_var = tk.StringVar()
    to_var = tk.StringVar()

    ttk.Label(bar, text="Group:").pack(side="left")
    ttk.Combobox(bar, textvariable=group_var, values=group_labels,
                 state="readonly", width=40).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="From:").pack(side="left")
    ttk.Entry(bar, textvariable=from_var, width=12).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="To:").pack(side="left")
    ttk.Entry(bar, textvariable=to_var, width=12).pack(side="left", padx=(4, 12))

    table_holder = ttk.Frame(parent)
    table_holder.pack(fill="both", expand=True)
    grp_label = ttk.Label(parent, text="", foreground="#333")
    grp_label.pack(anchor="w", pady=(8, 0))

    def render() -> None:
        for w in table_holder.winfo_children():
            w.destroy()
        gid = group_by_label.get(group_var.get())
        if gid is None:
            ttk.Label(table_holder, text="Pick a group.",
                      foreground="#a33").pack(anchor="w")
            return
        try:
            per_student = data.per_student_summary_for_group(
                gid,
                date_from=from_var.get().strip() or None,
                date_to=to_var.get().strip() or None,
            )
            group_summary = data.summary_for_group(
                gid,
                date_from=from_var.get().strip() or None,
                date_to=to_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("summary failed")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        students_index = {s.student_id: s for s in student_data.list_students()}

        cols = ("student_id", "name", "total", "present", "late",
                "absent", "authorised", "pct")
        headings = {
            "student_id": ("Student ID", 110),
            "name":       ("Name",       220),
            "total":      ("Sessions",    70),
            "present":    ("Present",     70),
            "late":       ("Late",        50),
            "absent":     ("Absent",      70),
            "authorised": ("Auth.",       60),
            "pct":        ("%",           60),
        }
        tree = ttk.Treeview(table_holder, columns=cols, show="headings", height=12)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        for sid, s in sorted(per_student.items()):
            student = students_index.get(sid)
            name = student.full_name if student else "(deleted)"
            tree.insert("", "end", iid=sid, values=(
                sid, name, s.total, s.present, s.late, s.absent,
                s.authorised, f"{s.percentage}%" if s.percentage is not None else "—",
            ))

        pct = (f"{group_summary.percentage}%"
               if group_summary.percentage is not None else "—")
        grp_label.configure(
            text=(f"Group: total sessions={group_summary.total}, "
                  f"present={group_summary.present}, late={group_summary.late}, "
                  f"absent={group_summary.absent}, "
                  f"authorised={group_summary.authorised}, attending={pct}")
        )
        gui.status_var.set("Attendance summary loaded")

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))
    if group_labels:
        render()
    else:
        ttk.Label(table_holder, text="No class groups yet.",
                  foreground="#a33").pack(anchor="w")
