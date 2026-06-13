"""GUI panels for Sixth Form Class Groups.

A class group is a teaching set within a course. Beyond plain CRUD,
the profile view manages the group's membership (add/remove students)
with capacity enforcement.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.academics.class_groups import class_groups
from education_system.sixthform_system.modules.domain.academics.courses import courses
from education_system.sixthform_system.modules.domain.academics.class_groups import class_groups as data
from education_system.sixthform_system.modules.domain.academics.courses import courses as course_data
from education_system.sixthform_system.modules.domain.students.students import students as student_data
from education_system.sixthform_system.modules.domain.academics.class_groups.class_groups import (
    ClassGroup,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _course_label(course) -> str:
    return f"{course.course_id} — {course.course_code} ({course.subject}, Y{course.year_group})"


def _load_courses() -> list:
    try:
        return course_data.list_courses()
    except Exception:
        logger.exception("Could not load courses for class-group form")
        return []


def _load_students() -> list:
    try:
        return student_data.list_students()
    except Exception:
        logger.exception("Could not load students")
        return []


# ── Add / Edit form ─────────────────────────────────────────────────

def _group_form(
    gui,
    *,
    title: str,
    existing: ClassGroup | None,
    preselect_course_id: int | None,
    on_save: Callable[[dict[str, Any]], ClassGroup],
) -> None:
    frame = _clear(gui)
    _heading(frame, title)

    is_edit = existing is not None

    courses = _load_courses()
    if not courses and not is_edit:
        ttk.Label(
            frame,
            text="No courses yet — create a course before adding a class group.",
            foreground="#a33",
        ).pack(anchor="w")
        ttk.Button(frame, text="Back to Class Groups",
                   command=lambda: open_directory(gui)).pack(anchor="w", pady=(8, 0))
        return

    course_choices = [_course_label(c) for c in courses]
    course_by_label = {_course_label(c): c.course_id for c in courses}

    if is_edit:
        c = course_data.get_course(existing.course_id)
        disp = _course_label(c) if c else f"{existing.course_id} — (course missing)"
    elif preselect_course_id is not None:
        c = course_data.get_course(preselect_course_id)
        disp = _course_label(c) if c else ""
    else:
        disp = course_choices[0] if course_choices else ""

    course_var = tk.StringVar(value=disp)
    name_var = tk.StringVar(value=existing.group_name if is_edit else "")
    teacher_var = tk.StringVar(value=(existing.teacher or "") if is_edit else "")
    room_var = tk.StringVar(value=(existing.room or "") if is_edit else "")
    schedule_var = tk.StringVar(value=(existing.schedule or "") if is_edit else "")
    max_var = tk.StringVar(value=(
        str(existing.max_students) if (is_edit and existing.max_students is not None)
        else ""))

    form = ttk.Frame(frame, padding=(0, 4))
    form.pack(anchor="w", fill="x")
    form.columnconfigure(1, weight=1, minsize=320)

    # Parented on form so we can grid alongside the other fields.
    notes_text = tk.Text(form, height=4, width=60)

    def row(idx: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(form, text=label).grid(
            row=idx, column=0, sticky="e", padx=(0, 8), pady=4)
        widget.grid(row=idx, column=1, sticky="ew", pady=4)

    row(0, "Course *", ttk.Combobox(
        form, textvariable=course_var, values=course_choices,
        state=("readonly" if not is_edit else "disabled"), width=46))
    row(1, "Group name *", ttk.Entry(form, textvariable=name_var))
    row(2, "Teacher (override course)", ttk.Entry(form, textvariable=teacher_var))
    row(3, "Room (override course)", ttk.Entry(form, textvariable=room_var))
    row(4, "Schedule", ttk.Entry(form, textvariable=schedule_var))
    row(5, "Max students (override course)",
        ttk.Entry(form, textvariable=max_var, width=10))
    ttk.Label(form, text="Notes").grid(
        row=6, column=0, sticky="ne", padx=(0, 8), pady=4)
    notes_text.grid(row=6, column=1, sticky="ew", pady=4)
    if is_edit and existing.notes:
        notes_text.insert("1.0", existing.notes)

    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(12, 0))

    def submit() -> None:
        if is_edit:
            cid = existing.course_id
        else:
            cid = course_by_label.get(course_var.get().strip())
            if cid is None:
                messagebox.showerror(
                    "Cannot save", "Please pick a course.", parent=gui.root)
                return
        payload = {
            "course_id":    cid,
            "group_name":   name_var.get(),
            "teacher":      teacher_var.get(),
            "room":         room_var.get(),
            "schedule":     schedule_var.get(),
            "max_students": max_var.get(),
            "notes":        notes_text.get("1.0", "end").strip(),
        }
        try:
            saved = on_save(payload)
        except ValidationError as e:
            logger.warning("Class-group form rejected: %s", e)
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("Unexpected error saving class-group form")
            messagebox.showerror("Error", f"Unexpected error: {e}",
                                 parent=gui.root)
            return
        logger.info("GUI saved class group #%d via %s", saved.group_id, title)
        messagebox.showinfo(
            "Saved",
            f"Class group #{saved.group_id} saved\n"
            f"  Course : #{saved.course_id}\n"
            f"  Name   : {saved.group_name}\n"
            f"  Cap    : {data.effective_cap(saved) or '—'}",
            parent=gui.root,
        )
        gui.status_var.set(f"Saved class group {saved.group_name}")
        open_profile(gui, saved.group_id)

    ttk.Button(bar, text="Save", command=submit).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Cancel",
               command=lambda: open_directory(gui)).pack(side="left")


def open_add_group(gui, preselect_course_id: int | None = None) -> None:
    def on_save(payload: dict[str, Any]) -> ClassGroup:
        return data.create_group(payload)
    _group_form(
        gui, title="New Class Group", existing=None,
        preselect_course_id=preselect_course_id, on_save=on_save,
    )
    gui.status_var.set("New class group")


def open_edit_group(gui, group_id: int) -> None:
    try:
        existing = data.get_group(group_id)
    except Exception as e:
        logger.exception("Failed to load class group %d", group_id)
        messagebox.showerror("Error", f"Could not load group: {e}",
                             parent=gui.root)
        return
    if existing is None:
        messagebox.showerror("Not found", f"No class group #{group_id}",
                             parent=gui.root)
        return

    def on_save(payload: dict[str, Any]) -> ClassGroup:
        return data.update_group(group_id, payload)
    _group_form(
        gui, title=f"Edit Class Group — {existing.group_name}",
        existing=existing, preselect_course_id=existing.course_id,
        on_save=on_save,
    )
    gui.status_var.set(f"Editing class group #{group_id}")


# ── Directory ───────────────────────────────────────────────────────

def open_directory(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Class Groups")

    filt = ttk.Frame(frame)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    course_filter_var = tk.StringVar()
    teacher_var = tk.StringVar()
    search_var = tk.StringVar()

    courses = _load_courses()
    course_filter_choices = [""] + [_course_label(c) for c in courses]
    course_filter_by_label = {_course_label(c): c.course_id for c in courses}

    ttk.Label(filt, text="Course:").pack(side="left")
    ttk.Combobox(
        filt, textvariable=course_filter_var, values=course_filter_choices,
        state="readonly", width=46,
    ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Teacher:").pack(side="left")
    ttk.Entry(filt, textvariable=teacher_var, width=14).pack(
        side="left", padx=(4, 12))
    ttk.Label(filt, text="Search:").pack(side="left")
    ttk.Entry(filt, textvariable=search_var, width=14).pack(
        side="left", padx=(4, 4))

    table_holder = ttk.Frame(frame)
    table_holder.pack(fill="both", expand=True)
    summary = ttk.Label(frame, text="", foreground="#555")
    summary.pack(anchor="w", pady=(4, 8))
    actions_holder = ttk.Frame(frame)
    actions_holder.pack(anchor="w", pady=(0, 4))

    def refresh() -> None:
        for w in table_holder.winfo_children():
            w.destroy()
        for w in actions_holder.winfo_children():
            w.destroy()
        try:
            cid_filter = course_filter_by_label.get(course_filter_var.get())
            rows = data.list_groups(
                course_id=cid_filter,
                teacher=teacher_var.get().strip() or None,
                search=search_var.get().strip() or None,
            )
        except Exception as e:
            logger.exception("Failed to load class groups")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        course_codes = {c.course_id: c.course_code for c in courses}

        cols = ("group_id", "course", "group_name",
                "teacher", "room", "members", "cap")
        headings = {
            "group_id":   ("#",         50),
            "course":     ("Course",   130),
            "group_name": ("Group",    140),
            "teacher":    ("Teacher",  150),
            "room":       ("Room",      80),
            "members":    ("Members",   70),
            "cap":        ("Cap",       60),
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

        for g in rows:
            cap = data.effective_cap(g)
            tree.insert("", "end", iid=str(g.group_id), values=(
                g.group_id,
                course_codes.get(g.course_id, f"#{g.course_id}"),
                g.group_name,
                g.teacher or "—",
                g.room or "—",
                data.count_members(g.group_id),
                cap if cap is not None else "—",
            ))

        summary.configure(text=f"{len(rows)} class group(s).")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _require() -> int | None:
            gid = _selected()
            if gid is None:
                messagebox.showinfo("No selection",
                                    "Pick a class group first.", parent=gui.root)
            return gid

        ttk.Button(actions_holder, text="View / Members",
                   command=lambda: (_require() and open_profile(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Edit",
                   command=lambda: (_require() and open_edit_group(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Delete",
                   command=lambda: (_require() and _delete_with_confirm(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="New Class Group",
                   command=lambda: open_add_group(gui)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions_holder, text="Refresh", command=refresh
                   ).pack(side="left")

        tree.bind("<Double-1>",
                  lambda _e: (_selected() and open_profile(gui, _selected())))
        gui.status_var.set(f"Class groups: {len(rows)} match(es)")

    ttk.Button(filt, text="Apply", command=refresh).pack(side="left", padx=(8, 0))
    ttk.Button(
        filt, text="Clear",
        command=lambda: (course_filter_var.set(""), teacher_var.set(""),
                         search_var.set(""), refresh()),
    ).pack(side="left", padx=(4, 0))
    refresh()


# ── Profile + member management ─────────────────────────────────────

def open_profile(gui, group_id: int) -> None:
    frame = _clear(gui)
    _heading(frame, f"Class Group #{group_id}")

    try:
        g = data.get_group(group_id)
    except Exception as exc:
        logger.exception("Failed to load class group %d", group_id)
        ttk.Label(frame, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
        return
    if g is None:
        ttk.Label(frame, text="No such class group.",
                  foreground="#a33").pack(anchor="w")
        return

    course = course_data.get_course(g.course_id)
    cap = data.effective_cap(g)

    # ── Header (group details) ──
    grid = ttk.Frame(frame)
    grid.pack(anchor="w", pady=(8, 0))

    def field(row: int, label: str, value: str) -> None:
        ttk.Label(grid, text=label + ":", foreground="#555",
                  width=20, anchor="e").grid(row=row, column=0, sticky="e",
                                              pady=2, padx=(0, 8))
        ttk.Label(grid, text=value or "—").grid(
            row=row, column=1, sticky="w", pady=2)

    field(0, "Course",
          _course_label(course) if course else f"#{g.course_id} (deleted)")
    field(1, "Group name",   g.group_name)
    field(2, "Teacher",      g.teacher or (course.teacher if course else None) or "—")
    field(3, "Room",         g.room    or (course.room    if course else None) or "—")
    field(4, "Schedule",     g.schedule or "—")
    field(5, "Capacity",     f"{data.count_members(group_id)} / {cap if cap is not None else '—'}")
    field(6, "Created",      g.created_at)
    if g.notes:
        ttk.Separator(grid, orient="horizontal").grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=(10, 6))
        ttk.Label(grid, text="Notes:", foreground="#555",
                  width=20, anchor="e").grid(row=8, column=0, sticky="ne",
                                              padx=(0, 8))
        ttk.Label(grid, text=g.notes,
                  wraplength=520, justify="left").grid(
            row=8, column=1, sticky="w")

    # ── Members ──
    members_section = ttk.LabelFrame(frame, text="Members", padding=8)
    members_section.pack(fill="both", expand=True, pady=(16, 0))

    table_holder = ttk.Frame(members_section)
    table_holder.pack(fill="both", expand=True)

    add_bar = ttk.Frame(members_section)
    add_bar.pack(anchor="w", fill="x", pady=(8, 0))

    def refresh_members() -> None:
        for w in table_holder.winfo_children():
            w.destroy()
        for w in add_bar.winfo_children():
            w.destroy()

        member_ids = data.list_members(group_id)
        # Pre-load student details for the table and the "add" dropdown.
        all_students = _load_students()
        student_index = {s.student_id: s for s in all_students}
        non_members = [s for s in all_students if s.student_id not in member_ids]

        cols = ("student_id", "name", "joined")
        headings = {
            "student_id": ("Student ID", 110),
            "name":       ("Name",       260),
            "joined":     ("Joined",     160),
        }
        tree = ttk.Treeview(table_holder, columns=cols, show="headings", height=10)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        # Fetch joined_at via direct query (kept simple — one round-trip).
        import sqlite3 as _sqlite3
        joined_lookup: dict[str, str] = {}
        try:
            with _sqlite3.connect(str(data.DB_PATH)) as conn:
                conn.row_factory = _sqlite3.Row
                for r in conn.execute(
                    "SELECT student_id, joined_at FROM class_group_students "
                    "WHERE group_id = ?", (group_id,),
                ):
                    joined_lookup[r["student_id"]] = r["joined_at"]
        except Exception:
            logger.exception("Could not fetch joined_at timestamps")

        for sid in member_ids:
            s = student_index.get(sid)
            tree.insert("", "end", iid=sid, values=(
                sid,
                s.full_name if s else "(unknown)",
                joined_lookup.get(sid, "—"),
            ))

        # Re-render the add bar with the current non-members list.
        ttk.Label(add_bar, text="Add student:").pack(side="left")
        add_var = tk.StringVar()
        add_choices = [f"{s.student_id} — {s.full_name}" for s in non_members]
        add_lookup = {f"{s.student_id} — {s.full_name}": s.student_id
                      for s in non_members}
        combo = ttk.Combobox(
            add_bar, textvariable=add_var, values=add_choices,
            state="readonly", width=42,
        )
        combo.pack(side="left", padx=(6, 6))

        def do_add() -> None:
            sid = add_lookup.get(add_var.get())
            if not sid:
                messagebox.showinfo("No selection",
                                    "Pick a student to add.", parent=gui.root)
                return
            try:
                data.add_member(group_id, sid)
            except ValidationError as e:
                messagebox.showerror("Cannot add", str(e), parent=gui.root)
                return
            except Exception as e:
                logger.exception("add_member crash")
                messagebox.showerror("Error", f"Unexpected: {e}", parent=gui.root)
                return
            gui.status_var.set(f"Added {sid} to group #{group_id}")
            refresh_members()

        def do_remove() -> None:
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("No selection",
                                    "Pick a member to remove.", parent=gui.root)
                return
            sid = sel[0]
            if not messagebox.askyesno(
                "Remove member",
                f"Remove {sid} from this group?", parent=gui.root,
            ):
                return
            try:
                data.remove_member(group_id, sid)
            except Exception as e:
                logger.exception("remove_member crash")
                messagebox.showerror("Error", f"Unexpected: {e}", parent=gui.root)
                return
            gui.status_var.set(f"Removed {sid} from group #{group_id}")
            refresh_members()

        ttk.Button(add_bar, text="Add", command=do_add).pack(side="left")
        ttk.Button(add_bar, text="Remove selected",
                   command=do_remove).pack(side="left", padx=(12, 0))
        ttk.Button(add_bar, text="Refresh members",
                   command=refresh_members).pack(side="left", padx=(6, 0))

    refresh_members()

    # ── Footer (group actions) ──
    actions = ttk.Frame(frame)
    actions.pack(anchor="w", pady=(12, 0))
    ttk.Button(actions, text="Edit group",
               command=lambda: open_edit_group(gui, g.group_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Delete group",
               command=lambda: _delete_with_confirm(gui, g.group_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Back to Class Groups",
               command=lambda: open_directory(gui)).pack(side="left")
    gui.status_var.set(f"Viewing class group #{group_id}")


def _delete_with_confirm(gui, group_id: int) -> None:
    try:
        g = data.get_group(group_id)
    except Exception as exc:
        logger.exception("Failed to load class group %d", group_id)
        messagebox.showerror("Error", f"Could not load group: {exc}",
                             parent=gui.root)
        return
    if g is None:
        messagebox.showerror("Not found", f"No class group #{group_id}",
                             parent=gui.root)
        return

    n = data.count_members(group_id)
    msg = f"Delete class group '{g.group_name}'?"
    if n:
        msg += f"\n\n{n} student(s) will be removed from this group."
    if not messagebox.askyesno("Delete class group", msg, parent=gui.root):
        return
    try:
        deleted = data.delete_group(group_id)
    except Exception as exc:
        logger.exception("Delete failed for class group %d", group_id)
        messagebox.showerror("Error", f"Could not delete: {exc}",
                             parent=gui.root)
        return
    if deleted:
        gui.status_var.set(f"Deleted class group #{group_id}")
        open_directory(gui)
    else:
        messagebox.showerror("Error", "Could not delete class group.",
                             parent=gui.root)
