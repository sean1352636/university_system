"""GUI panels for Sixth Form Tutor Groups.

Four tabs:

* Directory   — filterable list of tutor groups with member counts.
* Group       — open one group → details, member roster, add/remove.
* Per-student — pick a student → see their tutor group + reassign.
* Summary     — totals and an "unassigned" alert.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.students.students import students
from education_system.sixthform_system.modules.domain.students.students import students as student_data
from education_system.sixthform_system.modules.domain.pastoral.tutor_groups import tutor_groups as data
from education_system.sixthform_system.modules.domain.pastoral.tutor_groups.tutor_groups import (
    TutorGroup,
    ValidationError,
    YEAR_GROUPS,
)

logger = logging.getLogger(__name__)


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _group_label(g: TutorGroup) -> str:
    return f"#{g.tutor_group_id} {g.name} (Year {g.year_group})"


# ── Top-level tabbed view ───────────────────────────────────────────

def open_directory(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Tutor Groups")

    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True)

    dir_tab = ttk.Frame(nb, padding=8)
    group_tab = ttk.Frame(nb, padding=8)
    student_tab = ttk.Frame(nb, padding=8)
    summary_tab = ttk.Frame(nb, padding=8)
    nb.add(dir_tab,     text="Directory")
    nb.add(group_tab,   text="Group")
    nb.add(student_tab, text="Per-student")
    nb.add(summary_tab, text="Summary")

    _build_directory_tab(gui, dir_tab)
    _build_group_tab(gui, group_tab)
    _build_student_tab(gui, student_tab)
    _build_summary_tab(gui, summary_tab)


# ─── Directory tab ──────────────────────────────────────────────────

def _build_directory_tab(gui, parent: ttk.Frame) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    year_var = tk.StringVar()
    tutor_var = tk.StringVar()

    ttk.Label(filt, text="Year:").pack(side="left")
    ttk.Combobox(filt, textvariable=year_var,
                 values=["", *[str(y) for y in YEAR_GROUPS]],
                 state="readonly", width=6
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Tutor:").pack(side="left")
    ttk.Entry(filt, textvariable=tutor_var, width=20
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
            year = int(year_var.get()) if year_var.get().strip() else None
        except ValueError:
            messagebox.showerror("Bad filter",
                                 "Year must be a number.", parent=gui.root)
            return
        try:
            rows = data.list_groups_with_counts(
                year_group=year,
                tutor_like=tutor_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("list_groups_with_counts failed")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("group_id", "name", "year", "tutor", "co_tutor",
                "room", "members")
        headings = {
            "group_id": ("#",         50),
            "name":     ("Group",     90),
            "year":     ("Year",      60),
            "tutor":    ("Tutor",    140),
            "co_tutor": ("Co-tutor", 140),
            "room":     ("Room",      80),
            "members":  ("Members",   70),
        }
        tree = ttk.Treeview(table_holder, columns=cols,
                            show="headings", height=14)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical",
                            command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        for r in rows:
            g = r.group
            tree.insert("", "end", iid=str(g.tutor_group_id), values=(
                g.tutor_group_id, g.name, g.year_group,
                g.tutor or "—", g.co_tutor or "—",
                g.room or "—", r.member_count,
            ))
        summary.configure(text=f"{len(rows)} tutor group(s).")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _require() -> int | None:
            gid = _selected()
            if gid is None:
                messagebox.showinfo("No selection",
                                    "Pick a group first.",
                                    parent=gui.root)
            return gid

        def _open() -> None:
            gid = _require()
            if gid is None:
                return
            open_group(gui, gid)

        def _edit() -> None:
            gid = _require()
            if gid is None:
                return
            _edit_group_dialog(gui, gid, on_saved=refresh)

        def _delete() -> None:
            gid = _require()
            if gid is None:
                return
            g = data.get_group(gid)
            if g is None:
                return
            n = data.count_members(gid)
            msg = f"Delete tutor group {g.name}?"
            if n:
                msg += (f"\n\n{n} student(s) will be unassigned.")
            if not messagebox.askyesno(
                "Delete tutor group", msg, parent=gui.root,
            ):
                return
            try:
                data.delete_group(gid)
            except Exception as e:
                logger.exception("delete_group crashed")
                messagebox.showerror("Error", f"Could not delete: {e}",
                                     parent=gui.root)
                return
            refresh()

        ttk.Button(actions_holder, text="Open",
                   command=_open).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Edit details",
                   command=_edit).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Delete",
                   command=_delete).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="New",
                   command=lambda: _new_group_dialog(gui, on_saved=refresh)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions_holder, text="Refresh",
                   command=refresh).pack(side="left")
        tree.bind("<Double-1>", lambda _e: _open())
        gui.status_var.set(f"Tutor groups: {len(rows)} match(es)")

    ttk.Button(filt, text="Apply", command=refresh
               ).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
               command=lambda: (year_var.set(""), tutor_var.set(""),
                                refresh())
               ).pack(side="left", padx=(4, 0))
    refresh()


def _new_group_dialog(gui, on_saved: Callable[[], None]) -> None:
    _group_dialog(gui, existing=None, on_saved=on_saved)


def _edit_group_dialog(gui, tutor_group_id: int,
                        on_saved: Callable[[], None]) -> None:
    existing = data.get_group(tutor_group_id)
    if existing is None:
        messagebox.showerror("Not found",
                             f"No tutor group #{tutor_group_id}",
                             parent=gui.root)
        return
    _group_dialog(gui, existing=existing, on_saved=on_saved)


def _group_dialog(gui, *, existing: TutorGroup | None,
                   on_saved: Callable[[], None]) -> None:
    win = tk.Toplevel(gui.root)
    win.title(f"Edit tutor group #{existing.tutor_group_id}"
              if existing else "New tutor group")
    win.transient(gui.root)
    win.after_idle(win.grab_set)
    frm = ttk.Frame(win, padding=12)
    frm.grid()

    name_var = tk.StringVar(value=existing.name if existing else "")
    year_var = tk.StringVar(
        value=str(existing.year_group) if existing
              else str(YEAR_GROUPS[0]))
    tutor_var = tk.StringVar(
        value=(existing.tutor or "") if existing else "")
    co_var = tk.StringVar(
        value=(existing.co_tutor or "") if existing else "")
    room_var = tk.StringVar(
        value=(existing.room or "") if existing else "")
    notes_var = tk.StringVar(
        value=(existing.notes or "") if existing else "")

    def row(idx, label, w):
        ttk.Label(frm, text=label).grid(row=idx, column=0, sticky="e",
                                         padx=(0, 6), pady=2)
        w.grid(row=idx, column=1, sticky="w", pady=2)

    row(0, "Group name *:",
        ttk.Entry(frm, textvariable=name_var, width=20))
    row(1, "Year group *:",
        ttk.Combobox(frm, textvariable=year_var,
                     values=[str(y) for y in YEAR_GROUPS],
                     state="readonly", width=6))
    row(2, "Tutor:",
        ttk.Entry(frm, textvariable=tutor_var, width=28))
    row(3, "Co-tutor:",
        ttk.Entry(frm, textvariable=co_var, width=28))
    row(4, "Room:",
        ttk.Entry(frm, textvariable=room_var, width=14))
    row(5, "Notes:",
        ttk.Entry(frm, textvariable=notes_var, width=42))

    def save() -> None:
        payload = {
            "name":       name_var.get(),
            "year_group": year_var.get(),
            "tutor":      tutor_var.get(),
            "co_tutor":   co_var.get(),
            "room":       room_var.get(),
            "notes":      notes_var.get(),
        }
        try:
            if existing:
                data.update_group(existing.tutor_group_id, payload)
            else:
                data.create_group(payload)
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("save group crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()
        on_saved()

    bar = ttk.Frame(frm)
    bar.grid(row=6, column=0, columnspan=2, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


# ─── Group tab + standalone group view ──────────────────────────────

def _build_group_tab(gui, parent: ttk.Frame) -> None:
    rows = data.list_groups()
    if rows:
        _render_group(gui, parent, rows[0].tutor_group_id)
    else:
        ttk.Label(
            parent,
            text="No tutor groups yet. Use Directory → New to create one.",
            foreground="#555",
        ).pack(anchor="w", pady=8)


def open_group(gui, tutor_group_id: int) -> None:
    """Standalone full-page group view."""
    frame = _clear(gui)
    _heading(frame, f"Tutor Group #{tutor_group_id}")
    _render_group(gui, frame, tutor_group_id)
    ttk.Button(frame, text="Back to Tutor Groups",
               command=lambda: open_directory(gui)
               ).pack(anchor="w", pady=(12, 0))


def _render_group(gui, parent: ttk.Frame, tutor_group_id: int) -> None:
    g = data.get_group(tutor_group_id)
    if g is None:
        ttk.Label(parent, text="No such tutor group.",
                  foreground="#a33").pack(anchor="w")
        return

    # Header
    head = ttk.Frame(parent)
    head.pack(anchor="w", fill="x", pady=(0, 8))

    def field(idx: int, label: str, value: str) -> None:
        ttk.Label(head, text=label + ":", foreground="#555",
                  width=12, anchor="e").grid(row=idx, column=0,
                                              sticky="e", pady=2, padx=(0, 8))
        ttk.Label(head, text=value or "—").grid(
            row=idx, column=1, sticky="w", pady=2)

    field(0, "Group", g.name)
    field(1, "Year", f"Year {g.year_group}")
    field(2, "Tutor", g.tutor or "—")
    field(3, "Co-tutor", g.co_tutor or "—")
    field(4, "Room", g.room or "—")
    field(5, "Members", str(data.count_members(tutor_group_id)))
    if g.notes:
        ttk.Label(head, text="Notes:", foreground="#555",
                  width=12, anchor="ne").grid(row=6, column=0, sticky="ne",
                                               padx=(0, 8), pady=(6, 0))
        ttk.Label(head, text=g.notes,
                  wraplength=620, justify="left").grid(
            row=6, column=1, sticky="w", pady=(6, 0))

    actions = ttk.Frame(parent)
    actions.pack(anchor="w", pady=(8, 12))
    ttk.Button(actions, text="Edit details",
               command=lambda: _edit_group_dialog(
                   gui, tutor_group_id,
                   on_saved=lambda: open_group(gui, tutor_group_id))
               ).pack(side="left", padx=(0, 6))

    # Members section
    members = data.list_members(tutor_group_id)
    members_frame = ttk.LabelFrame(parent,
                                    text=f"Members ({len(members)})",
                                    padding=8)
    members_frame.pack(fill="both", expand=True)

    table_holder = ttk.Frame(members_frame)
    table_holder.pack(fill="both", expand=True)

    cols = ("student_id", "name", "subjects")
    headings = {
        "student_id": ("Student ID", 110),
        "name":       ("Name",       240),
        "subjects":   ("A-Levels",   420),
    }
    tree = ttk.Treeview(table_holder, columns=cols, show="headings",
                        height=10)
    for col in cols:
        text, width = headings[col]
        tree.heading(col, text=text)
        tree.column(col, width=width, anchor="w")
    vs = ttk.Scrollbar(table_holder, orient="vertical",
                        command=tree.yview)
    tree.configure(yscrollcommand=vs.set)
    tree.pack(side="left", fill="both", expand=True)
    vs.pack(side="right", fill="y")

    student_index = {s.student_id: s for s in student_data.list_students()}
    for sid in members:
        s = student_index.get(sid)
        tree.insert("", "end", iid=sid, values=(
            sid,
            s.full_name if s else "(deleted)",
            ", ".join(s.subjects) if s else "—",
        ))

    # Add bar
    add_bar = ttk.Frame(members_frame)
    add_bar.pack(anchor="w", fill="x", pady=(8, 0))
    all_students = student_data.list_students()
    non_members = [s for s in all_students if s.student_id not in members]
    add_labels = [f"{s.student_id} — {s.full_name}" for s in non_members]
    add_lookup = {f"{s.student_id} — {s.full_name}": s.student_id
                  for s in non_members}
    add_var = tk.StringVar(value=add_labels[0] if add_labels else "")
    ttk.Label(add_bar, text="Add student:").pack(side="left")
    add_combo = ttk.Combobox(add_bar, textvariable=add_var,
                              values=add_labels,
                              state="readonly", width=42)
    add_combo.pack(side="left", padx=(6, 6))

    def do_add() -> None:
        sid = add_lookup.get(add_var.get())
        if not sid:
            messagebox.showinfo("No selection",
                                "Pick a student to add.", parent=gui.root)
            return
        # Warn if they're already in another group
        prev = data.group_for_student(sid)
        if prev is not None:
            if not messagebox.askyesno(
                "Move student?",
                f"{sid} is currently in {prev.name}. "
                f"Move them to {g.name}?",
                parent=gui.root,
            ):
                return
        try:
            data.assign_student(sid, tutor_group_id)
        except ValidationError as e:
            messagebox.showerror("Cannot add", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("assign_student crashed")
            messagebox.showerror("Error", f"Unexpected: {e}",
                                 parent=gui.root)
            return
        open_group(gui, tutor_group_id)

    def do_remove() -> None:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("No selection",
                                "Pick a member to remove.",
                                parent=gui.root)
            return
        sid = sel[0]
        if not messagebox.askyesno(
            "Remove member",
            f"Remove {sid} from {g.name}?",
            parent=gui.root,
        ):
            return
        try:
            data.unassign_student(sid)
        except Exception as e:
            logger.exception("unassign_student crashed")
            messagebox.showerror("Error", f"Unexpected: {e}",
                                 parent=gui.root)
            return
        open_group(gui, tutor_group_id)

    ttk.Button(add_bar, text="Add",
               command=do_add).pack(side="left")
    ttk.Button(add_bar, text="Remove selected",
               command=do_remove).pack(side="left", padx=(12, 0))

    gui.status_var.set(f"Tutor group {g.name} loaded "
                        f"({len(members)} member(s))")


# ─── Per-student tab ────────────────────────────────────────────────

def _build_student_tab(gui, parent: ttk.Frame) -> None:
    students = student_data.list_students()
    labels = [f"{s.student_id} — {s.full_name}" for s in students]
    by_label = {lbl: s.student_id for lbl, s in zip(labels, students)}

    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))
    student_var = tk.StringVar(value=labels[0] if labels else "")
    ttk.Label(bar, text="Student:").pack(side="left")
    ttk.Combobox(bar, textvariable=student_var, values=labels,
                 state="readonly", width=42
                 ).pack(side="left", padx=(4, 4))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        sid = by_label.get(student_var.get())
        if not sid:
            ttk.Label(holder, text="Pick a student.",
                      foreground="#a33").pack(anchor="w")
            return
        student = student_data.get_student(sid)
        ttk.Label(holder,
                  text=f"{student.student_id}  {student.full_name}"
                       if student else f"{sid} (deleted)",
                  font=("", 12, "bold")).pack(anchor="w", pady=(0, 6))

        cur_group = data.group_for_student(sid)
        info = ttk.Frame(holder)
        info.pack(anchor="w", pady=(0, 8))
        ttk.Label(info, text="Current tutor group:",
                  foreground="#555").pack(side="left", padx=(0, 6))
        ttk.Label(info,
                  text=_group_label(cur_group) if cur_group
                       else "(none assigned)",
                  font=("", 11, "bold")
                  ).pack(side="left")

        groups = data.list_groups()
        group_labels = ["(none)"] + [_group_label(g) for g in groups]
        group_by_label = {_group_label(g): g.tutor_group_id for g in groups}
        change_var = tk.StringVar(
            value=_group_label(cur_group) if cur_group else "(none)")

        change_bar = ttk.Frame(holder)
        change_bar.pack(anchor="w", pady=(0, 8))
        ttk.Label(change_bar, text="Assign to:").pack(side="left")
        ttk.Combobox(change_bar, textvariable=change_var,
                     values=group_labels, state="readonly", width=40
                     ).pack(side="left", padx=(6, 6))

        def do_save() -> None:
            target = change_var.get()
            if target == "(none)":
                try:
                    data.unassign_student(sid)
                except Exception as e:
                    logger.exception("unassign_student crashed")
                    messagebox.showerror("Error", f"Unexpected: {e}",
                                         parent=gui.root)
                    return
            else:
                gid = group_by_label.get(target)
                if gid is None:
                    messagebox.showerror("Cannot save",
                                         "Pick a group.", parent=gui.root)
                    return
                try:
                    data.assign_student(sid, gid)
                except ValidationError as e:
                    messagebox.showerror("Cannot save", str(e),
                                         parent=gui.root)
                    return
                except Exception as e:
                    logger.exception("assign_student crashed")
                    messagebox.showerror("Error", f"Unexpected: {e}",
                                         parent=gui.root)
                    return
            gui.status_var.set(f"Updated tutor group for {sid}")
            render()

        ttk.Button(change_bar, text="Save",
                   command=do_save).pack(side="left")

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))
    if labels:
        render()
    else:
        ttk.Label(holder, text="No students yet.",
                  foreground="#a33").pack(anchor="w")


# ─── Summary tab ────────────────────────────────────────────────────

def _build_summary_tab(gui, parent: ttk.Frame) -> None:
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        try:
            summ = data.summary()
        except Exception as e:
            logger.exception("summary failed")
            ttk.Label(holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        ttk.Label(
            holder,
            text=f"Tutor groups: {summ.total_groups}  ·  "
                 f"Students assigned: {summ.assigned_students}"
                 f"/{summ.total_students}",
            font=("", 12, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        ttk.Label(holder, text="By year:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        for y in YEAR_GROUPS:
            ttk.Label(holder,
                      text=f"   Year {y}  : {summ.by_year.get(y, 0)} group(s)",
                      foreground="#444").pack(anchor="w")

        ttk.Label(
            holder,
            text=f"Unassigned students: {summ.unassigned_students}",
            foreground=("#a33" if summ.unassigned_students else "#444"),
            font=("", 10, "bold"),
        ).pack(anchor="w", pady=(8, 2))

        if summ.unassigned_students:
            unassigned = data.unassigned_students()
            names = {s.student_id: s.full_name
                     for s in student_data.list_students()}
            for sid in unassigned[:30]:
                ttk.Label(holder,
                          text=f"   {sid:<10}  {names.get(sid, '—')}",
                          foreground="#555").pack(anchor="w")
            if len(unassigned) > 30:
                ttk.Label(holder,
                          text=f"   … and {len(unassigned) - 30} more",
                          foreground="#777").pack(anchor="w")
        gui.status_var.set("Tutor-group summary loaded")

    bar = ttk.Frame(parent)
    bar.pack(anchor="w", pady=(0, 8))
    ttk.Button(bar, text="Refresh", command=render
               ).pack(side="left")
    render()
