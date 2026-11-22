"""Enrolment checks: the warnings shown after an enrolment is saved or
opened (they never block a save), class sizes, tutor group sizes, a
learner's timetable, and the data check (``reconcile``) with fixes."""

from __future__ import annotations

import logging
from tkinter import ttk

from education_system.platform.delivery.gui.parented_dialogs import messagebox
from education_system.systems.sixth_form.domain.admissions.enrolments import (
    enrolment_checks as checks,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import reconcile

from . import enrolment_page_kit as kit
from .enrolment_common import _default_academic_year, _student_name_map, describe_error, show_error

logger = logging.getLogger(__name__)


def warnings_for(student_id: str, academic_year: str | None = None) -> list[str]:
    """``check_enrolment`` messages; a failed check is one line, never
    an exception (the save it follows has already happened)."""
    try:
        return [w.message for w in checks.check_enrolment(student_id, academic_year)]
    except Exception as exc:  # noqa: BLE001 — reported as a line
        logger.exception("check_enrolment(%s) failed", student_id)
        return [f"The checks could not run: {describe_error(exc)}"]


def warnings_section(parent, student_id: str, academic_year: str | None) -> list[str]:
    lines = warnings_for(student_id, academic_year)
    if lines:
        kit.section(parent, "Checks")
        for line in lines:
            kit.note(parent, f"⚠ {line}", colour="#a06000")
    return lines


# ── Class and tutor group sizes ─────────────────────────────────────

CLASS_COLS = [("code", "Course", 100), ("subject", "Subject", 180), ("yg", "YG", 40),
              ("group", "Group", 160), ("n", "Members", 70), ("cap", "Cap", 60),
              ("left", "Places left", 80), ("state", "State", 80)]
TUTOR_COLS = [("name", "Tutor group", 120), ("yg", "YG", 40), ("tutor", "Tutor", 180),
              ("n", "Members", 70), ("limit", "Limit", 60), ("state", "State", 80)]
TT_COLS = [("day", "Day", 90), ("period", "Period", 60), ("start", "Start", 60),
           ("end", "End", 60), ("group", "Group", 180), ("code", "Course", 100),
           ("room", "Room", 80), ("teacher", "Teacher", 160)]


def open_class_sizes(gui, academic_year: str | None = None) -> None:
    year = academic_year or _default_academic_year()
    frame, bar = kit.page(gui, "Class Sizes")
    top = ttk.Frame(frame)
    top.pack(anchor="w", fill="x")
    kit.year_picker(top, year, on_change=lambda y: open_class_sizes(gui, y))
    try:
        rows = checks.class_size_report(year)
    except Exception as exc:  # noqa: BLE001
        show_error(gui.root, "Class sizes", exc)
        rows = []
    kit.table(frame, CLASS_COLS, [
        (r.course_code, r.subject, r.year_group, r.group_name, r.members,
         "—" if r.cap is None else r.cap, "—" if r.remaining is None else r.remaining,
         "Over" if r.over else ("Full" if r.full else "")) for r in rows])
    kit.note(frame, f"{len(rows)} class group(s); {sum(r.over for r in rows)} over capacity, "
             f"{sum(r.full and not r.over for r in rows)} full.")
    kit.csv_button(bar, gui, lambda: rows, f"class_sizes_{year.replace('/', '-')}.csv")
    gui.status_var.set(f"Class sizes {year}")


def open_tutor_group_sizes(gui) -> None:
    frame, bar = kit.page(gui, "Tutor Group Sizes")
    try:
        rows = checks.tutor_group_sizes()
    except Exception as exc:  # noqa: BLE001
        show_error(gui.root, "Tutor group sizes", exc)
        rows = []
    kit.table(frame, TUTOR_COLS, [(r.name, r.year_group, r.tutor, r.members, r.limit,
                                   "Over" if r.over else "") for r in rows])
    kit.note(frame, "The limit is the Tutor group size limit in Enrolment Settings.")
    kit.csv_button(bar, gui, lambda: rows, "tutor_group_sizes.csv")
    gui.status_var.set(f"{len(rows)} tutor group(s)")


def open_learner_timetable(gui, student_id: str | None = None) -> None:
    from .enrolment_pickers import choose_student
    if not student_id:
        student_id = choose_student(gui.root, "Learner timetable", "Learner:")
        if not student_id:
            return
    name = _student_name_map().get(student_id, "")
    frame, bar = kit.page(gui, f"Timetable — {student_id} {name}")
    try:
        rows = checks.learner_timetable(student_id)
    except Exception as exc:  # noqa: BLE001
        show_error(gui.root, "Timetable", exc)
        rows = []
    kit.table(frame, TT_COLS, [(r.day, r.period, r.start, r.end, r.group_name,
                                r.course_code, r.room, r.teacher) for r in rows])
    if not rows:
        kit.note(frame, "No timetabled sessions — the learner may not be in any "
                 "class group yet.", colour="#777")
    kit.button(bar, "Another Learner…", lambda: open_learner_timetable(gui))
    kit.csv_button(bar, gui, lambda: rows, f"timetable_{student_id}.csv")
    gui.status_var.set(f"Timetable for {student_id}")


# ── Data check (reconcile) ──────────────────────────────────────────

ISSUE_COLS = [("sid", "Student / check", 300), ("eid", "Enrolment", 70),
              ("detail", "Detail", 430), ("hint", "Fix", 380), ("fix", "Fixable", 60)]


def selection_ids(tree, fixable_kinds: set[str], fixable_ids: set[str]) -> list[str]:
    """What to pass to ``reconcile.fix``: whole kinds selected, plus
    single issues not already covered by their kind."""
    sel = list(tree.selection())
    kinds = [s for s in sel if s in fixable_kinds]
    ids = [s for s in sel if s in fixable_ids and s.split(":", 1)[0] not in kinds]
    return kinds + ids


def open_data_check(gui, student_id: str | None = None) -> None:
    frame, bar = kit.page(gui, "Enrolment Data Check")
    try:
        issues = reconcile.check(student_id=student_id)
    except Exception as exc:  # noqa: BLE001
        kit.note(frame, f"The check could not run: {describe_error(exc)}", colour="#a33")
        return
    counts = reconcile.summary(issues)
    kit.note(frame, "  ·  ".join(f"{reconcile.KIND_LABELS.get(k, k)}: {n}"
                                 for k, n in counts.items()),
             colour="#a33" if issues else "#2e7d32")
    kit.note(frame, "Select issues, or a whole check, then Fix Selected. Greyed issues "
             "are report-only and must be put right by hand.")
    names = _student_name_map()
    holder = ttk.Frame(frame)
    holder.pack(fill="both", expand=True)
    from education_system.systems.sixth_form.interfaces.gui.admissions import (
        _admissions_ui as ui,
    )
    tree = ui.make_tree(holder, ISSUE_COLS, height=18, selectmode="extended")
    tree.configure(show="tree headings")
    tree.column("#0", width=24, stretch=False)
    tree.tag_configure("report", foreground="#999")
    tree.tag_configure("kind", font=("", 10, "bold"))
    fixable_kinds: set[str] = set()
    fixable_ids: set[str] = set()
    for kind in reconcile.KINDS:
        mine = [i for i in issues if i.kind == kind]
        if not mine:
            continue
        any_fix = any(i.fixable for i in mine)
        if any_fix:
            fixable_kinds.add(kind)
        tree.insert("", "end", iid=kind, open=True, tags=("kind",) if any_fix
                    else ("kind", "report"),
                    values=(f"{reconcile.KIND_LABELS.get(kind, kind)} ({len(mine)})",
                            "", "", "", "Yes" if any_fix else "No"))
        for i in mine:
            if i.fixable:
                fixable_ids.add(i.issue_id)
            tree.insert(kind, "end", iid=i.issue_id, tags=() if i.fixable else ("report",),
                        values=(f"{i.student_id} {names.get(i.student_id, '')}",
                                i.enrolment_id or "", i.detail, i.fix_hint,
                                "Yes" if i.fixable else "No"))
    if not issues:
        kit.note(frame, "No problems found.", colour="#2e7d32")

    def drop_report_only(_e=None) -> None:
        keep = [s for s in tree.selection() if s in fixable_kinds or s in fixable_ids]
        if len(keep) != len(tree.selection()):
            tree.selection_set(keep)

    tree.bind("<<TreeviewSelect>>", drop_report_only)

    def fix_selected() -> None:
        chosen = selection_ids(tree, fixable_kinds, fixable_ids)
        if not chosen:
            messagebox.showinfo("Data check", "Select fixable issues (or a whole "
                                "check) first.", parent=gui.root)
            return
        n = sum(1 for i in issues if i.fixable and (i.kind in chosen or i.issue_id in chosen))
        if not messagebox.askyesno(
                "Fix data", f"Fix {n} issue(s)? Each fix goes through the normal "
                "enrolment rules and is recorded in the history.", parent=gui.root):
            return
        run_fix(gui, chosen, student_id)

    kit.button(bar, "Fix Selected…", fix_selected, enabled=kit.can_write() and bool(fixable_ids))
    kit.button(bar, "Re-run Check", lambda: open_data_check(gui, student_id))
    kit.csv_button(bar, gui, lambda: [{"check": i.label, "student_id": i.student_id,
                                       "enrolment_id": i.enrolment_id, "aim_id": i.aim_id,
                                       "detail": i.detail, "fix": i.fix_hint,
                                       "fixable": i.fixable} for i in issues],
                   "enrolment_data_check.csv")
    gui.status_var.set(f"Data check: {len(issues)} issue(s)")
    frame.tree = tree  # type: ignore[attr-defined]  # for scripted checks


def run_fix(gui, chosen: list[str], student_id: str | None = None) -> list[str] | None:
    lines = kit.attempt(gui, "Fix data", lambda: reconcile.fix(selection=chosen))
    if lines is not None:
        kit.show_lines(gui, "Fix data", lines or ["Nothing was changed."])
        open_data_check(gui, student_id)
    return lines
