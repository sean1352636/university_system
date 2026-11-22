"""What "Open" does for each kind of Advanced Search result.

A record that has its own screen in the main window opens there (the
student profile, a course, a class group, a UCAS application…); a record
about one student with no screen of its own opens that student's profile,
which lists their records by area. Anything else opens a read-only detail
window showing every field the search holds for it.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import make_toplevel
from education_system.systems.sixth_form.domain.learners.advanced_search import (
    exports as search_exports,
    matching as search_matching,
    query as search_query,
)
from education_system.systems.sixth_form.domain.learners.advanced_search.models import (
    ALL_SCOPES,
    Hit,
    SCOPE_LABELS,
)

logger = logging.getLogger(__name__)


def _int_id(h: Hit) -> int:
    return int(str(h.entity_id).split(":")[-1])


def _record_openers() -> dict[str, Callable[[Any, Hit], None]]:
    """Scope → ``fn(gui, hit)`` for records with their own screen."""
    def courses(gui, h):
        from education_system.systems.sixth_form.interfaces.gui.academics.courses import course_views
        course_views.open_profile(gui, _int_id(h))

    def subjects(gui, h):
        from education_system.systems.sixth_form.interfaces.gui.academics.subjects import subject_views
        subject_views.open_profile(gui, _int_id(h))

    def class_groups(gui, h):
        from education_system.systems.sixth_form.interfaces.gui.academics.class_groups import class_group_views
        class_group_views.open_profile(gui, _int_id(h))

    def homework(gui, h):
        from education_system.systems.sixth_form.interfaces.gui.academics.homework import homework_views
        homework_views.open_profile(gui, _int_id(h))

    def timetable(gui, h):
        from education_system.systems.sixth_form.interfaces.gui.academics.timetable import timetable_views
        timetable_views.open_edit_slot(gui, _int_id(h))

    def ucas(gui, h):
        if not str(h.entity_id).startswith("app:"):
            raise LookupError("references open from the student")
        from education_system.systems.sixth_form.interfaces.gui.progression.university import ucas as ucas_views
        ucas_views.open_application(gui, _int_id(h))

    return {"courses": courses, "subjects": subjects,
            "class_groups": class_groups, "homework": homework,
            "timetable": timetable, "ucas": ucas}


def _open_student(gui, student_id: str) -> None:
    from education_system.systems.sixth_form.interfaces.gui.learners.students import student_views
    student_views.open_profile(gui, student_id)


def _raise_main(gui) -> None:
    root = getattr(gui, "root", None)
    if root is not None:
        try:
            root.deiconify()
            root.lift()
            root.focus_force()
        except tk.TclError:
            pass


def register(gui: Any, window: tk.Misc) -> None:
    """Install an open handler for every scope. *gui* is the main window
    (None when Advanced Search runs on its own); *window* parents the
    detail view."""
    openers = _record_openers()
    in_main = gui is not None and hasattr(gui, "content_frame")

    def handler(hit: Hit) -> bool:
        if in_main:
            try:
                if hit.scope in openers:
                    openers[hit.scope](gui, hit)
                    _raise_main(gui)
                    return True
            except Exception:  # noqa: BLE001 — fall through to the student
                logger.debug("No record screen for %s %s", hit.scope,
                             hit.entity_id, exc_info=True)
            if hit.scope in search_matching._STUDENT_KEYED_SCOPES:
                doc = (hit.extra or {}).get("_doc") or {}
                sid = search_query._doc_student_id(hit.scope, doc)
                if sid:
                    _open_student(gui, sid)
                    _raise_main(gui)
                    return True
        show_detail(window, hit)
        return True

    for scope in ALL_SCOPES:
        search_exports.register_open_handler(scope, handler)


def show_detail(parent: tk.Misc, hit: Hit) -> None:
    """Read-only window with every field the search holds for *hit*."""
    win = make_toplevel(parent)
    win.title(f"{SCOPE_LABELS.get(hit.scope, hit.scope)} — {hit.entity_id}")
    win.geometry("640x460")
    bar = ttk.Frame(win)
    bar.pack(side="bottom", fill="x", padx=8, pady=8)
    ttk.Button(bar, text="Close", command=win.destroy).pack(side="right")
    ttk.Label(win, text=hit.label, font=("", 12, "bold"),
              wraplength=600).pack(anchor="w", padx=10, pady=(10, 2))
    if hit.sublabel:
        ttk.Label(win, text=hit.sublabel, foreground="#555",
                  wraplength=600).pack(anchor="w", padx=10)
    body = ttk.Frame(win)
    body.pack(fill="both", expand=True, padx=8, pady=8)
    tree = ttk.Treeview(body, columns=("field", "value"), show="headings")
    tree.heading("field", text="Field")
    tree.heading("value", text="Value")
    tree.column("field", width=150, anchor="w")
    tree.column("value", width=440, anchor="w")
    vs = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vs.set)
    vs.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    doc = (hit.extra or {}).get("_doc") or {}
    for k, v in doc.items():
        if k.startswith("_") and k not in ("_date", "_grade"):
            continue
        if v in (None, ""):
            continue
        tree.insert("", "end", values=(k.lstrip("_"), str(v)))
