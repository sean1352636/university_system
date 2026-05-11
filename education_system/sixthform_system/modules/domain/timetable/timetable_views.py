"""GUI panels for Sixth Form Timetable.

Two top-level panels share the same `open_directory` entry point with
a tabbed Notebook:

  * Slots tab — flat directory of every slot with the usual filter /
    Treeview / action-button layout. Add / Edit / Delete here.
  * Weekly grid tab — 5×6 grid filtered by group / student / teacher /
    room, with click-through to the slot details.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.class_groups import class_groups
from education_system.sixthform_system.modules.domain.courses import courses
from education_system.sixthform_system.modules.domain.students import students
from education_system.sixthform_system.modules.domain.timetable import timetable as cg_data
from education_system.sixthform_system.modules.domain.courses import courses as course_data
from education_system.sixthform_system.modules.domain.students import students as student_data
from education_system.sixthform_system.modules.domain.timetable import timetable as data
from education_system.sixthform_system.modules.domain.timetable.timetable import (
    DAYS,
    DAY_NUMBERS,
    DEFAULT_PERIOD_TIMES,
    PERIODS,
    SaveResult,
    TimetableSlot,
    ValidationError,
    day_name,
    day_number,
)

logger = logging.getLogger(__name__)


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _group_label(group, course=None) -> str:
    if course is None:
        course = course_data.get_course(group.course_id)
    code = course.course_code if course else f"#{group.course_id}"
    return f"#{group.group_id} {group.group_name} ({code})"


def _load_groups() -> list:
    try:
        return cg_data.list_groups()
    except Exception:
        logger.exception("Could not load class groups")
        return []


def _load_students() -> list:
    try:
        return student_data.list_students()
    except Exception:
        logger.exception("Could not load students")
        return []


def _surface_clashes(save: SaveResult, parent) -> None:
    if not save.student_clashes and not save.teacher_clashes:
        return
    parts: list[str] = []
    if save.student_clashes:
        parts.append(
            "Student clashes (in another class at the same time):\n"
            "  · " + "\n  · ".join(sorted(save.student_clashes))
        )
    if save.teacher_clashes:
        parts.append(
            "Teacher clashes:\n"
            "  · " + "\n  · ".join(sorted(set(save.teacher_clashes)))
        )
    messagebox.showwarning(
        "Saved with clash warnings",
        "Slot saved, but the timetable has clashes:\n\n" + "\n\n".join(parts),
        parent=parent,
    )


# ── Add / Edit form ─────────────────────────────────────────────────

def _slot_form(
    gui,
    *,
    title: str,
    existing: TimetableSlot | None,
    preselect_group_id: int | None,
    on_save: Callable[[dict[str, Any]], SaveResult],
) -> None:
    frame = _clear(gui)
    _heading(frame, title)

    is_edit = existing is not None
    groups = _load_groups()
    if not groups and not is_edit:
        ttk.Label(
            frame,
            text="No class groups yet — create a class group before timetabling.",
            foreground="#a33",
        ).pack(anchor="w")
        ttk.Button(frame, text="Back to Timetable",
                   command=lambda: open_directory(gui)
                   ).pack(anchor="w", pady=(8, 0))
        return

    courses_by_id = {c.course_id: c for c in course_data.list_courses()}
    group_labels = [_group_label(g, courses_by_id.get(g.course_id))
                    for g in groups]
    group_by_label = {lbl: g.group_id for lbl, g in zip(group_labels, groups)}

    if is_edit:
        g = cg_data.get_group(existing.group_id)
        disp = _group_label(g, courses_by_id.get(g.course_id)) if g else \
               f"#{existing.group_id} (deleted)"
    elif preselect_group_id is not None:
        g = cg_data.get_group(preselect_group_id)
        disp = (_group_label(g, courses_by_id.get(g.course_id))
                if g else (group_labels[0] if group_labels else ""))
    else:
        disp = group_labels[0] if group_labels else ""

    group_var = tk.StringVar(value=disp)
    day_var = tk.StringVar(
        value=DAYS[existing.day - 1] if is_edit else DAYS[0])
    period_var = tk.StringVar(
        value=str(existing.period) if is_edit else str(PERIODS[0]))
    start_var = tk.StringVar(
        value=(existing.start_time or "") if is_edit
              else DEFAULT_PERIOD_TIMES[PERIODS[0]][0])
    end_var = tk.StringVar(
        value=(existing.end_time or "") if is_edit
              else DEFAULT_PERIOD_TIMES[PERIODS[0]][1])
    room_var = tk.StringVar(value=(existing.room or "") if is_edit else "")

    form = ttk.Frame(frame, padding=(0, 4))
    form.pack(anchor="w", fill="x")
    form.columnconfigure(1, weight=1, minsize=320)

    notes_text = tk.Text(form, height=4, width=60)

    def row(idx: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(form, text=label).grid(
            row=idx, column=0, sticky="e", padx=(0, 8), pady=4)
        widget.grid(row=idx, column=1, sticky="ew", pady=4)

    row(0, "Class group *", ttk.Combobox(
        form, textvariable=group_var, values=group_labels,
        state=("readonly" if not is_edit else "disabled"), width=46))
    row(1, "Day *", ttk.Combobox(
        form, textvariable=day_var, values=list(DAYS),
        state="readonly", width=8))

    def _period_picked(*_a) -> None:
        # Pre-fill times whenever the user changes the period, but
        # respect manual overrides — only auto-fill when blank.
        try:
            p = int(period_var.get())
            st, et = DEFAULT_PERIOD_TIMES.get(p, ("", ""))
            if not start_var.get():
                start_var.set(st)
            if not end_var.get():
                end_var.set(et)
        except ValueError:
            pass

    row(2, "Period *", ttk.Combobox(
        form, textvariable=period_var, values=[str(p) for p in PERIODS],
        state="readonly", width=8))
    period_var.trace_add("write", _period_picked)

    row(3, "Start time (HH:MM)", ttk.Entry(form, textvariable=start_var, width=10))
    row(4, "End time (HH:MM)",   ttk.Entry(form, textvariable=end_var, width=10))
    row(5, "Room (override)",     ttk.Entry(form, textvariable=room_var))
    ttk.Label(form, text="Notes").grid(
        row=6, column=0, sticky="ne", padx=(0, 8), pady=4)
    notes_text.grid(row=6, column=1, sticky="ew", pady=4)
    if is_edit and existing.notes:
        notes_text.insert("1.0", existing.notes)

    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(12, 0))

    def submit() -> None:
        if is_edit:
            gid = existing.group_id
        else:
            gid = group_by_label.get(group_var.get().strip())
            if gid is None:
                messagebox.showerror("Cannot save",
                                     "Pick a class group.", parent=gui.root)
                return
        payload = {
            "group_id":   gid,
            "day":        day_number(day_var.get()) or 0,
            "period":     period_var.get(),
            "start_time": start_var.get(),
            "end_time":   end_var.get(),
            "room":       room_var.get(),
            "notes":      notes_text.get("1.0", "end").strip(),
        }
        try:
            save = on_save(payload)
        except ValidationError as e:
            logger.warning("Timetable form rejected: %s", e)
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("Unexpected error saving slot")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=gui.root)
            return
        _surface_clashes(save, gui.root)
        gui.status_var.set(f"Saved slot #{save.slot.slot_id}")
        open_directory(gui)

    ttk.Button(bar, text="Save", command=submit).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Cancel",
               command=lambda: open_directory(gui)).pack(side="left")


def open_add_slot(gui, preselect_group_id: int | None = None) -> None:
    def on_save(payload: dict[str, Any]) -> SaveResult:
        return data.create_slot(payload)
    _slot_form(gui, title="New Timetable Slot", existing=None,
               preselect_group_id=preselect_group_id, on_save=on_save)
    gui.status_var.set("New timetable slot")


def open_edit_slot(gui, slot_id: int) -> None:
    try:
        existing = data.get_slot(slot_id)
    except Exception as e:
        logger.exception("Failed to load slot %d", slot_id)
        messagebox.showerror("Error", f"Could not load slot: {e}",
                             parent=gui.root)
        return
    if existing is None:
        messagebox.showerror("Not found", f"No slot #{slot_id}",
                             parent=gui.root)
        return

    def on_save(payload: dict[str, Any]) -> SaveResult:
        return data.update_slot(slot_id, payload)
    _slot_form(gui, title=f"Edit Slot #{slot_id}",
               existing=existing, preselect_group_id=existing.group_id,
               on_save=on_save)
    gui.status_var.set(f"Editing slot #{slot_id}")


# ── Directory (tabbed) ─────────────────────────────────────────────

def open_directory(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Timetable")

    notebook = ttk.Notebook(frame)
    notebook.pack(fill="both", expand=True)

    slots_tab = ttk.Frame(notebook, padding=8)
    grid_tab  = ttk.Frame(notebook, padding=8)
    notebook.add(slots_tab, text="Slots")
    notebook.add(grid_tab,  text="Weekly grid")

    _build_slots_tab(gui, slots_tab)
    _build_grid_tab(gui, grid_tab)


# ─── Slots tab ──────────────────────────────────────────────────────

def _build_slots_tab(gui, parent: ttk.Frame) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    group_filter_var = tk.StringVar()
    day_var = tk.StringVar()
    period_var = tk.StringVar()
    room_var = tk.StringVar()

    groups = _load_groups()
    courses_by_id = {c.course_id: c for c in course_data.list_courses()}
    group_filter_choices = [""] + [
        _group_label(g, courses_by_id.get(g.course_id)) for g in groups]
    group_filter_by_label = {
        _group_label(g, courses_by_id.get(g.course_id)): g.group_id
        for g in groups
    }

    ttk.Label(filt, text="Group:").pack(side="left")
    ttk.Combobox(filt, textvariable=group_filter_var,
                 values=group_filter_choices, state="readonly", width=42
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Day:").pack(side="left")
    ttk.Combobox(filt, textvariable=day_var,
                 values=["", *DAYS], state="readonly", width=6
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Period:").pack(side="left")
    ttk.Combobox(filt, textvariable=period_var,
                 values=["", *[str(p) for p in PERIODS]],
                 state="readonly", width=4
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Room:").pack(side="left")
    ttk.Entry(filt, textvariable=room_var, width=10
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
            gid = group_filter_by_label.get(group_filter_var.get())
            day = day_number(day_var.get()) if day_var.get() else None
            per = int(period_var.get()) if period_var.get() else None
            rows = data.list_slots(
                group_id=gid, day=day, period=per,
                room=room_var.get().strip() or None,
            )
        except Exception as e:
            logger.exception("Failed to load slots")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("slot_id", "day", "period", "group",
                "room", "start", "end")
        headings = {
            "slot_id": ("#",      50),
            "day":     ("Day",    60),
            "period":  ("P",      35),
            "group":   ("Group", 280),
            "room":    ("Room",   70),
            "start":   ("Start",  70),
            "end":     ("End",    70),
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

        group_index = {g.group_id: g for g in groups}
        for s in rows:
            g = group_index.get(s.group_id)
            label = (_group_label(g, courses_by_id.get(g.course_id))
                     if g else f"#{s.group_id}")
            tree.insert("", "end", iid=str(s.slot_id), values=(
                s.slot_id, day_name(s.day), s.period, label,
                s.room or "—", s.start_time or "—", s.end_time or "—",
            ))

        summary.configure(text=f"{len(rows)} slot(s).")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _require() -> int | None:
            sid = _selected()
            if sid is None:
                messagebox.showinfo("No selection",
                                    "Pick a slot first.", parent=gui.root)
            return sid

        ttk.Button(actions_holder, text="Edit",
                   command=lambda: (_require() and open_edit_slot(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Delete",
                   command=lambda: (_require() and _delete_with_confirm(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="New Slot",
                   command=lambda: open_add_slot(gui)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions_holder, text="Refresh", command=refresh
                   ).pack(side="left")

        tree.bind("<Double-1>",
                  lambda _e: (_selected() and open_edit_slot(gui, _selected())))
        gui.status_var.set(f"Timetable slots: {len(rows)} match(es)")

    ttk.Button(filt, text="Apply", command=refresh).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
               command=lambda: (group_filter_var.set(""), day_var.set(""),
                                period_var.set(""), room_var.set(""), refresh())
               ).pack(side="left", padx=(4, 0))
    refresh()


# ─── Weekly grid tab ────────────────────────────────────────────────

def _build_grid_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))

    view_var = tk.StringVar(value="All")
    target_var = tk.StringVar()

    groups = _load_groups()
    courses_by_id = {c.course_id: c for c in course_data.list_courses()}
    group_labels = [_group_label(g, courses_by_id.get(g.course_id))
                    for g in groups]
    group_by_label = {lbl: g.group_id for lbl, g in zip(group_labels, groups)}

    students = _load_students()
    student_labels = [f"{s.student_id} — {s.full_name}" for s in students]
    student_by_label = {f"{s.student_id} — {s.full_name}": s.student_id
                        for s in students}

    teachers = sorted({
        (g.teacher or
         (courses_by_id.get(g.course_id).teacher
          if courses_by_id.get(g.course_id) else None) or "").strip()
        for g in groups
    } - {""})
    rooms = sorted({
        (g.room or
         (courses_by_id.get(g.course_id).room
          if courses_by_id.get(g.course_id) else None) or "").strip()
        for g in groups
    } - {""})

    target_combo_values: list[str] = []

    target_combo = ttk.Combobox(
        bar, textvariable=target_var, state="readonly", width=46)

    def _set_target_values(*_a) -> None:
        nonlocal target_combo_values
        v = view_var.get()
        if v == "Group":
            target_combo_values = group_labels
        elif v == "Student":
            target_combo_values = student_labels
        elif v == "Teacher":
            target_combo_values = teachers
        elif v == "Room":
            target_combo_values = rooms
        else:
            target_combo_values = []
        target_combo.configure(values=target_combo_values)
        target_var.set("")

    ttk.Label(bar, text="View by:").pack(side="left")
    view_combo = ttk.Combobox(
        bar, textvariable=view_var,
        values=["All", "Group", "Student", "Teacher", "Room"],
        state="readonly", width=10,
    )
    view_combo.pack(side="left", padx=(4, 12))
    view_var.trace_add("write", _set_target_values)

    ttk.Label(bar, text="Target:").pack(side="left")
    target_combo.pack(side="left", padx=(4, 12))

    grid_holder = ttk.Frame(parent)
    grid_holder.pack(fill="both", expand=True)

    def render() -> None:
        for w in grid_holder.winfo_children():
            w.destroy()

        kwargs: dict[str, Any] = {}
        v = view_var.get()
        t = target_var.get().strip()
        if v == "Group":
            kwargs["group_id"] = group_by_label.get(t)
            if kwargs["group_id"] is None and t:
                ttk.Label(grid_holder,
                          text="Pick a group from the dropdown.",
                          foreground="#a33").pack(anchor="w")
                return
        elif v == "Student":
            kwargs["student_id"] = student_by_label.get(t)
            if kwargs["student_id"] is None and t:
                ttk.Label(grid_holder, text="Pick a student.",
                          foreground="#a33").pack(anchor="w")
                return
        elif v == "Teacher":
            kwargs["teacher"] = t or None
        elif v == "Room":
            kwargs["room"] = t or None

        try:
            grid = data.weekly_grid(**kwargs)
        except Exception as e:
            logger.exception("weekly_grid failed")
            ttk.Label(grid_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        # Render the 5×6 table.
        table = ttk.Frame(grid_holder)
        table.pack(fill="both", expand=True)
        # Header row
        ttk.Label(table, text="", width=10).grid(row=0, column=0, sticky="nsew",
                                                  padx=1, pady=1)
        for col_idx, d in enumerate(DAY_NUMBERS, start=1):
            cell = ttk.Label(table, text=day_name(d), anchor="center",
                             font=("", 10, "bold"), background="#dde",
                             padding=4)
            cell.grid(row=0, column=col_idx, sticky="nsew", padx=1, pady=1)
            table.columnconfigure(col_idx, weight=1, minsize=160)

        group_index = {g.group_id: g for g in groups}
        for r_idx, p in enumerate(PERIODS, start=1):
            ttk.Label(
                table, text=f"P{p}\n{DEFAULT_PERIOD_TIMES[p][0]}",
                anchor="center", font=("", 9, "bold"),
                background="#eef", padding=4, width=10,
            ).grid(row=r_idx, column=0, sticky="nsew", padx=1, pady=1)
            table.rowconfigure(r_idx, weight=1, minsize=60)
            for c_idx, d in enumerate(DAY_NUMBERS, start=1):
                cell_slots = grid.get((d, p), [])
                bg = "#ffffff"
                if len(cell_slots) > 1:
                    bg = "#f6cccc"  # clash highlight
                elif len(cell_slots) == 1:
                    bg = "#eaf4ea"
                container = tk.Frame(table, background=bg, padx=4, pady=4,
                                     borderwidth=1, relief="solid",
                                     highlightthickness=0)
                container.grid(row=r_idx, column=c_idx, sticky="nsew",
                               padx=1, pady=1)
                if not cell_slots:
                    tk.Label(container, text="", background=bg).pack()
                else:
                    for s in cell_slots:
                        g = group_index.get(s.group_id)
                        course = courses_by_id.get(g.course_id) if g else None
                        title = (f"{course.course_code} — {g.group_name}"
                                 if g and course else
                                 (g.group_name if g else f"#{s.group_id}"))
                        sub = s.room or (course.room if course else None) or "—"
                        time_str = (f"{s.start_time}–{s.end_time}"
                                    if s.start_time and s.end_time else "")
                        tk.Label(container, text=title, background=bg,
                                 font=("", 9, "bold"), justify="left",
                                 anchor="w").pack(fill="x")
                        tk.Label(container, text=sub, background=bg,
                                 font=("", 8), foreground="#555",
                                 anchor="w").pack(fill="x")
                        if time_str:
                            tk.Label(container, text=time_str, background=bg,
                                     font=("", 8), foreground="#555",
                                     anchor="w").pack(fill="x")
                        # Clicking opens the slot editor
                        sid = s.slot_id
                        for child in container.winfo_children():
                            child.bind("<Button-1>",
                                       lambda _e, _s=sid: open_edit_slot(gui, _s))
                        container.bind("<Button-1>",
                                       lambda _e, _s=sid: open_edit_slot(gui, _s))

        gui.status_var.set(f"Timetable grid ({v}: {t or '—'})")

    ttk.Button(bar, text="Show", command=render).pack(side="left", padx=(8, 0))
    render()


# ── Delete confirm ─────────────────────────────────────────────────

def _delete_with_confirm(gui, slot_id: int) -> None:
    s = data.get_slot(slot_id)
    if s is None:
        messagebox.showerror("Not found", f"No slot #{slot_id}", parent=gui.root)
        return
    if not messagebox.askyesno(
        "Delete slot",
        f"Delete slot #{s.slot_id} ({day_name(s.day)} P{s.period}, "
        f"group #{s.group_id})?",
        parent=gui.root,
    ):
        return
    try:
        data.delete_slot(slot_id)
    except Exception as e:
        logger.exception("delete_slot crashed")
        messagebox.showerror("Error", f"Could not delete: {e}", parent=gui.root)
        return
    gui.status_var.set(f"Deleted slot #{slot_id}")
    open_directory(gui)
