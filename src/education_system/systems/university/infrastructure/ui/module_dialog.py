"""The one add/edit-module form, shared by every GUI that offers it.

Module Scheduling and Grade Tracking each grew their own dialog over the
same ``modules`` table, and they had drifted apart: Grade Tracking asked
for a description, an academic year and checked for a duplicate code;
Module Scheduling offered a course dropdown but its edit form wrote only
code, name and type — silently leaving credits, semester and everything
else untouched. Which fields a module actually kept depended on which
screen you happened to edit it from.

This is the union of the two, so nothing either screen could do is lost:
the richer field set and validation from Grade Tracking, the course
dropdown from Module Scheduling.

``course`` and ``department`` are both written from the same picked
course unless a department is entered: the two dialogs each populated one
and ignored the other, so a module was filed under a course in one screen
and a department in the other; keeping them in step by default is what
makes the two views agree.

Every save goes through ``application/modules/specification``, so each
changed field lands in the module's change history. ``mode="propose"``
(a module leader without catalogue rights) records a change request for a
catalogue manager to approve instead of writing.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

logger = logging.getLogger(__name__)

__all__ = ["open_module_dialog", "load_module", "course_options"]

MODULE_TYPES = ["Core", "Elective", "Optional", "Lab", "Project", "Seminar"]
SEMESTERS = ["Fall", "Spring", "Summer", "Winter", "Year-long"]
#: FHEQ levels, shown with what they mean.
LEVELS = ["", "3 - Foundation", "4 - Certificate (year 1)", "5 - Intermediate (year 2)",
          "6 - Honours (year 3)", "7 - Masters", "8 - Doctoral"]


def _connect():
    from education_system.systems.university.infrastructure.database.db import (
        get_connection,
    )
    return get_connection()


def course_options():
    """``["CS - Computer Science", ...]`` for the course dropdown."""
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT COALESCE(NULLIF(course_code,''), code) AS c, "
                "       COALESCE(NULLIF(course_name,''), name) AS n "
                "FROM courses "
                "WHERE COALESCE(NULLIF(course_code,''), code) IS NOT NULL "
                "  AND TRIM(COALESCE(NULLIF(course_code,''), code)) != '' "
                "ORDER BY 1").fetchall()
        return [f"{r['c']} - {r['n']}" if r["n"] else str(r["c"]) for r in rows]
    except Exception:
        logger.debug("Could not load courses for module dialog", exc_info=True)
        return []


def _distinct(column, defaults):
    """*defaults* plus whatever values the table already uses.

    Real data does not match a hand-written list — module_type holds
    'compulsory', which is in neither dialog's options. A readonly
    dropdown that omits the stored value silently discards it on the
    next save, so existing values are always offered.
    """
    values = list(defaults)
    try:
        with _connect() as conn:
            rows = conn.execute(
                f"SELECT DISTINCT {column} FROM modules "
                f"WHERE {column} IS NOT NULL AND TRIM({column}) != '' "
                f"ORDER BY {column}").fetchall()
        for row in rows:
            existing = str(row[0]).strip()
            if existing and existing.lower() not in {v.lower() for v in values}:
                values.append(existing)
    except Exception:
        logger.debug("Could not read existing %s values", column, exc_info=True)
    return values


def _course_code(value: str) -> str:
    """'CS - Computer Science' -> 'CS'."""
    return value.split(" - ")[0].strip() if " - " in value else value.strip()


def _level_choice(level):
    return next((choice for choice in LEVELS if choice.split(" ")[0] == str(level)), "")


def load_module(module_code):
    """Every field the dialog edits, or None when the module is gone."""
    try:
        with _connect() as conn:
            from education_system.systems.university.infrastructure.database.schemas import (
                module_catalogue_schema,
            )
            module_catalogue_schema.apply_to_connection(conn)
            row = conn.execute(
                "SELECT module_code, module_name, module_type, credits, "
                "       description, COALESCE(course, department) AS course, "
                "       semester, year, level, capacity, "
                "       NULLIF(department, COALESCE(course, '')) AS department "
                "FROM modules WHERE module_code = ?", (module_code,)).fetchone()
        return dict(row) if row is not None else None
    except Exception:
        logger.exception("Failed to load module %s", module_code)
        return None


def open_module_dialog(parent, *, mode="add", module_code=None, on_saved=None,
                       toplevel_factory=None, actor=None):
    """Open the add/edit module form.

    *mode* is ``"add"``, ``"edit"`` or ``"propose"``; the last two need
    *module_code*. *actor* is the username recorded in the change history.
    *on_saved* is called with the module code once the write succeeds, so
    each caller refreshes its own view. *toplevel_factory* lets a GUI
    supply its own parented-Toplevel helper.
    """
    existing = None
    if mode in ("edit", "propose"):
        if not module_code:
            messagebox.showwarning("No Selection",
                                   "Please select a module to edit.", parent=parent)
            return None
        existing = load_module(module_code)
        if existing is None:
            messagebox.showerror("Error", "Module not found in database",
                                 parent=parent)
            return None

    make_top = toplevel_factory or (lambda p: tk.Toplevel(p))
    dialog = make_top(parent)
    dialog.title({"edit": f"Edit Module: {module_code}",
                  "propose": f"Propose a change to {module_code}"}.get(mode, "Add New Module"))
    dialog.geometry("620x660")
    dialog.transient(parent)

    form = ttk.Frame(dialog, padding=20)
    form.pack(fill="both", expand=True)
    form.columnconfigure(1, weight=1)

    def label(text, row, sticky="w"):
        ttk.Label(form, text=text).grid(row=row, column=0, sticky=sticky, pady=5)

    # Module code is the key the row is found by, so it is fixed once set.
    label("Module Code*:", 0)
    code_entry = ttk.Entry(form, width=40)
    code_entry.grid(row=0, column=1, sticky="ew", pady=5)
    if existing:
        code_entry.insert(0, existing["module_code"] or "")
        code_entry.configure(state="readonly")

    label("Module Name*:", 1)
    name_entry = ttk.Entry(form, width=40)
    name_entry.grid(row=1, column=1, sticky="ew", pady=5)

    label("Module Type:", 2)
    type_combo = ttk.Combobox(form, width=38,
                              values=_distinct("module_type", MODULE_TYPES),
                              state="readonly")
    type_combo.grid(row=2, column=1, sticky="ew", pady=5)
    type_combo.set(MODULE_TYPES[0])

    label("Credits:", 3)
    # UK modules are 10-60 credits (a dissertation can be more); the old
    # 1-20 range could not even hold a 30-credit module.
    credits_spin = ttk.Spinbox(form, from_=0, to=180, increment=5, width=38)
    credits_spin.grid(row=3, column=1, sticky="ew", pady=5)
    credits_spin.set(20)

    label("Course/Programme:", 4)
    courses = course_options()
    course_combo = ttk.Combobox(form, width=38, values=courses)
    course_combo.grid(row=4, column=1, sticky="ew", pady=5)

    label("Semester:", 5)
    # "" first: a module with no semester recorded must be able to keep
    # it that way. Defaulting the box to Fall meant merely opening the
    # edit dialog and saving stamped a semester onto every such module.
    semester_combo = ttk.Combobox(form, width=38,
                                  values=[""] + _distinct("semester", SEMESTERS),
                                  state="readonly")
    semester_combo.grid(row=5, column=1, sticky="ew", pady=5)
    semester_combo.set(SEMESTERS[0] if mode == "add" else "")

    label("Academic Year:", 6)
    year_spin = ttk.Spinbox(form, from_=2020, to=2035, width=38)
    year_spin.grid(row=6, column=1, sticky="ew", pady=5)
    year_spin.set(datetime.now().year if mode == "add" else "")

    label("FHEQ Level:", 7)
    level_combo = ttk.Combobox(form, width=38, values=LEVELS, state="readonly")
    level_combo.grid(row=7, column=1, sticky="ew", pady=5)

    label("Department:", 8)
    dept_entry = ttk.Entry(form, width=40)
    dept_entry.grid(row=8, column=1, sticky="ew", pady=5)
    ttk.Label(form, text="Blank = same as the course", foreground="#666").grid(
        row=9, column=1, sticky="w")

    label("Capacity:", 10)
    capacity_spin = ttk.Spinbox(form, from_=0, to=2000, width=38)
    capacity_spin.grid(row=10, column=1, sticky="ew", pady=5)
    capacity_spin.set(0)
    ttk.Label(form, text="0 = no limit", foreground="#666").grid(row=11, column=1, sticky="w")

    label("Description:", 12, "nw")
    desc_text = tk.Text(form, width=40, height=5)
    desc_text.grid(row=12, column=1, sticky="ew", pady=5)

    if existing:
        name_entry.insert(0, existing["module_name"] or "")
        if existing["module_type"]:
            type_combo.set(existing["module_type"])
        if existing["credits"]:
            credits_spin.set(existing["credits"])
        if existing["course"]:
            # Show the full "CODE - Name" entry when we have one.
            match = next((c for c in courses
                          if _course_code(c) == str(existing["course"])), None)
            course_combo.set(match or existing["course"])
        if existing["semester"]:
            semester_combo.set(existing["semester"])
        if existing["year"]:
            year_spin.set(existing["year"])
        if existing["description"]:
            desc_text.insert("1.0", existing["description"])
        level_combo.set(_level_choice(existing["level"]))
        if existing["department"]:
            dept_entry.insert(0, existing["department"])
        capacity_spin.set(existing["capacity"] or 0)

    buttons = ttk.Frame(dialog, padding=10)
    buttons.pack(fill="x", side="bottom")

    def save():
        code = code_entry.get().strip()
        name = name_entry.get().strip()
        if not code:
            messagebox.showerror("Validation Error", "Module Code is required",
                                 parent=dialog)
            code_entry.focus()
            return
        if not name:
            messagebox.showerror("Validation Error", "Module Name is required",
                                 parent=dialog)
            name_entry.focus()
            return
        try:
            credits = int(credits_spin.get())
        except ValueError:
            messagebox.showerror("Validation Error", "Credits must be a number",
                                 parent=dialog)
            return

        try:
            capacity = int(capacity_spin.get() or 0)
        except ValueError:
            messagebox.showerror("Validation Error", "Capacity must be a number",
                                 parent=dialog)
            return
        course = _course_code(course_combo.get()) or None
        level = level_combo.get().split(" ")[0] if level_combo.get() else None
        values = {
            "module_name": name,
            "module_type": type_combo.get().strip() or None,
            "credits": credits,
            "description": desc_text.get("1.0", "end-1c").strip() or None,
            "course": course,
            "department": dept_entry.get().strip() or course,
            "semester": semester_combo.get().strip() or None,
            "year": year_spin.get().strip() or None,
            "level": int(level) if level else None,
            "capacity": capacity or None,
        }
        who = actor or _current_username()

        if mode == "propose":
            from tkinter import simpledialog
            summary = simpledialog.askstring(
                "Propose a change", "What is the change, and why?", parent=dialog)
            if not summary:
                return

        from education_system.systems.university.application.modules import (
            specification as module_specification,
        )

        try:
            with _connect() as conn:
                if mode == "propose":
                    request_id = module_specification.propose_change(
                        conn, code, values, who, summary)
                    conn.commit()
                    messagebox.showinfo(
                        "Change proposed",
                        f"Change request #{request_id} is waiting for a catalogue "
                        "manager to approve it.", parent=dialog)
                    dialog.destroy()
                    return
                if mode == "add":
                    # Module code is the natural key everything else joins
                    # on, so a duplicate has to be refused rather than
                    # quietly creating a second row with the same code.
                    if conn.execute("SELECT 1 FROM modules WHERE module_code = ?",
                                    (code,)).fetchone():
                        messagebox.showerror(
                            "Duplicate Error",
                            f"Module code {code} already exists", parent=dialog)
                        return
                    values = module_specification.clean_changes(values)
                    module_specification.ensure(conn)
                    cols = ["module_code"] + list(values)
                    conn.execute(
                        f"INSERT INTO modules ({', '.join(cols)}) "
                        f"VALUES ({', '.join('?' * len(cols))})",
                        (code, *values.values()))
                    module_specification.record_created(conn, code, values, who)
                else:
                    if not module_specification.apply_changes(conn, code, values, who):
                        messagebox.showinfo("No changes", "Nothing was changed.",
                                            parent=dialog)
                        return
                conn.commit()
        except ValueError as exc:
            messagebox.showerror("Validation Error", str(exc), parent=dialog)
            return
        except Exception as exc:
            messagebox.showerror("Database Error",
                                 f"Failed to save module: {exc}", parent=dialog)
            return

        _audit(code, mode, values)
        messagebox.showinfo(
            "Success",
            f"Module {code} {'updated' if mode == 'edit' else 'added'}.",
            parent=dialog)
        dialog.destroy()
        if callable(on_saved):
            try:
                on_saved(code)
            except Exception:
                logger.exception("on_saved callback failed for module %s", code)

    ttk.Button(buttons, text="Save", command=save).pack(side="left", padx=5)
    ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left", padx=5)
    return dialog


def _current_username():
    try:
        from education_system.systems.university.infrastructure.security.audit_helpers import (
            get_gui_context,
        )
        user_id = get_gui_context()[0]
        return str(user_id) if user_id is not None else None
    except Exception:
        return None


def _audit(module_code, mode, values):
    """Record the change; never blocks the save."""
    try:
        from education_system.systems.university.infrastructure.security.audit_helpers import (
            safe_log_security_event, get_gui_context,
        )
        from education_system.systems.university.infrastructure.security.immutable_audit_log import (
            AuditAction,
        )
        user_id, session_id = get_gui_context()
        safe_log_security_event(
            action=AuditAction.RECORD_CREATE if mode == "add" else AuditAction.RECORD_UPDATE,
            user_id=user_id, resource_type="module", resource_id=module_code,
            session_id=session_id, details=dict(values, module_code=module_code))
    except Exception:
        logger.debug("module audit unavailable", exc_info=True)
