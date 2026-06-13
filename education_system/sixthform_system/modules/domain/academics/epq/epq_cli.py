"""CLI flows for Extended Project Qualification (EPQ).

Top-level menu:
    1) List projects (all / by stage / by artefact)
    2) View project (full detail + production log + milestones)
    3) Add project
    4) Edit project
    5) Delete project
    6) Add production-log entry
    7) Save / update milestone
    8) Summary report
    0) Back
"""

from __future__ import annotations

import logging
from typing import Callable

from education_system.sixthform_system.modules.domain.academics.epq import (
    epq as data,
)
from education_system.sixthform_system.modules.domain.academics.epq.epq import (
    ARTEFACT_TYPES,
    DEFAULT_ARTEFACT_TYPE,
    DEFAULT_MILESTONE_STATUS,
    DEFAULT_STAGE,
    EPQLogEntry,
    EPQMilestone,
    EPQProject,
    GRADES,
    MILESTONE_LABELS,
    MILESTONE_STATUSES,
    MILESTONE_TYPES,
    STAGES,
    ValidationError,
)
from education_system.sixthform_system.modules.domain.students.students import (
    students as _students,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Input helpers ────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "",
            allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _yes_no(prompt: str, *, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)",
                  default="y" if default else "n").strip().lower()
    return raw in ("y", "yes")


def _multiline(prompt: str, *, default: str = "") -> str:
    print(f"\n  {prompt} (end with '.'; ENTER for default)")
    if default:
        for line in default.splitlines():
            print(f"    | {line}")
    lines: list[str] = []
    try:
        while True:
            ln = input("  > ")
            if ln.strip() == ".":
                break
            if not lines and not ln:
                return default
            lines.append(ln)
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    return "\n".join(lines)


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt or '(none)'}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number.")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_student() -> str:
    rows = _students.list_students()
    if not rows:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(rows, 1):
        full = f"{getattr(s, 'first_name', '')} " \
               f"{getattr(s, 'last_name', '')}".strip()
        print(f"    {i:>3}) {s.student_id:<12}  {full}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].student_id
        match = next((s for s in rows if s.student_id == raw), None)
        if match:
            return match.student_id
        print("    No matching student.")


def _pick_project() -> EPQProject:
    rows = data.list_projects()
    if not rows:
        print("    No EPQ projects yet.")
        raise _UserAbort
    names = {s.student_id: s.full_name for s in _students.list_students()}
    print("\n  EPQ projects:")
    for i, p in enumerate(rows, 1):
        student = names.get(p.student_id, "(unknown)")
        print(f"    {i:>3}) #{p.project_id}  {p.student_id:<12}  "
              f"{student[:22]:<22}  {p.working_title[:30]:<30}  "
              f"[{p.stage}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or project id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows if r.project_id == n), None)
            if match:
                return match
        print("    No matching project.")


# ── Rendering ────────────────────────────────────────────────────

def _print_table(rows: list[data.ProjectRow]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<12}  {'Name':<22}  "
          f"{'Title':<30}  {'Type':<13}  {'Stage':<12}  "
          f"{'Hrs':>5}  {'Mile':>6}  Grade")
    print("  " + "-" * 130)
    for r in rows:
        p = r.project
        ms = f"{r.milestones_completed}/{r.milestones_total}"
        print(f"  {p.project_id:>4}  {p.student_id:<12}  "
              f"{r.student_name[:22]:<22}  "
              f"{p.working_title[:30]:<30}  "
              f"{p.artefact_type:<13}  {p.stage:<12}  "
              f"{r.total_hours:>5.1f}  {ms:>6}  "
              f"{p.final_grade or '—'}")
    print(f"\n  {len(rows)} project(s).")


def _print_full(p: EPQProject) -> None:
    name = "(unknown)"
    s = _students.get_student(p.student_id)
    if s is not None:
        name = getattr(s, "full_name", "") or p.student_id
    print()
    print(f"    #{p.project_id}  Student {p.student_id}  ({name})")
    print(f"    Working title    : {p.working_title}")
    print(f"    Research question: {p.research_question or '—'}")
    print(f"    Artefact type    : {p.artefact_type}")
    print(f"    Supervisor       : {p.supervisor or '—'}")
    print(f"    Stage            : {p.stage}")
    print(f"    Final mark/grade : "
          f"{p.final_mark if p.final_mark is not None else '—'}"
          f"  /  {p.final_grade or '—'}")
    if p.notes:
        print("\n    Notes:")
        for line in p.notes.splitlines():
            print(f"      {line}")

    log = data.list_log_entries(p.project_id)
    total = data.total_hours_for_project(p.project_id)
    print(f"\n    Production log ({len(log)} entries, {total:.1f} hrs):")
    if not log:
        print("      (no entries)")
    else:
        for e in log[:10]:
            print(f"      {e.entry_date}  {e.hours:>4.1f}h  "
                  f"{e.activity[:60]}")
        if len(log) > 10:
            print(f"      … plus {len(log) - 10} older entries")

    ms = data.list_milestones(p.project_id)
    print(f"\n    Milestones ({len(ms)}):")
    if not ms:
        print("      (none yet)")
    else:
        for m in ms:
            due = m.due_date or "—"
            done = m.completed_date or "—"
            label = MILESTONE_LABELS.get(m.milestone_type,
                                          m.milestone_type)
            print(f"      {m.milestone_type:<13} {label[:30]:<30}  "
                  f"due {due:<10}  done {done:<10}  [{m.status}]")


# ── Flows ────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All EPQ Projects ═══")
    _print_table(data.list_projects_with_detail())
    _pause()


def list_by_stage() -> None:
    try:
        stage = _pick_from("Filter by stage", list(STAGES))
        print(f"\n═══ Projects in stage: {stage} ═══")
        _print_table(data.list_projects_with_detail(stage=stage))
        _pause()
    except _UserAbort:
        return


def list_by_artefact() -> None:
    try:
        artefact = _pick_from("Filter by artefact type",
                                list(ARTEFACT_TYPES))
        print(f"\n═══ Projects of type: {artefact} ═══")
        _print_table(data.list_projects_with_detail(
            artefact_type=artefact))
        _pause()
    except _UserAbort:
        return


def view_project() -> None:
    try:
        p = _pick_project()
        _print_full(p)
        _pause()
    except _UserAbort:
        return


def add_project() -> None:
    print("\n═══ Add EPQ Project ═══")
    try:
        sid = _pick_student()
        if data.get_project_for_student(sid) is not None:
            print(f"\n  ✗ {sid} already has an EPQ project. Use Edit instead.")
            _pause()
            return
        title = _input("Working title", allow_empty=False)
        question = _input("Research question")
        artefact = _pick_from("Artefact type",
                                list(ARTEFACT_TYPES),
                                default=DEFAULT_ARTEFACT_TYPE)
        supervisor = _input("Supervisor")
        stage = _pick_from("Stage", list(STAGES),
                            default=DEFAULT_STAGE)
        notes = _multiline("Notes (optional)")
        payload = {
            "student_id":        sid,
            "working_title":     title,
            "research_question": question,
            "artefact_type":     artefact,
            "supervisor":        supervisor,
            "stage":             stage,
            "notes":             notes,
        }
        p = data.create_project(payload)
        print(f"\n  ✓ Created EPQ project #{p.project_id}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("add_project failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def edit_project() -> None:
    print("\n═══ Edit EPQ Project ═══")
    try:
        p = _pick_project()
        title = _input("Working title", default=p.working_title,
                        allow_empty=False)
        question = _input("Research question",
                            default=p.research_question or "")
        artefact = _pick_from("Artefact type",
                                list(ARTEFACT_TYPES),
                                default=p.artefact_type)
        supervisor = _input("Supervisor",
                            default=p.supervisor or "")
        stage = _pick_from("Stage", list(STAGES),
                            default=p.stage)
        mark = _input("Final mark (0-50, blank for none)",
                        default=str(p.final_mark)
                            if p.final_mark is not None else "")
        grade_opts = ["(none)"] + list(GRADES)
        cur_grade = p.final_grade or "(none)"
        grade_pick = _pick_from("Final grade", grade_opts,
                                  default=cur_grade)
        grade = "" if grade_pick == "(none)" else grade_pick
        notes = _multiline("Notes", default=p.notes or "")
        out = data.update_project(p.project_id, {
            "working_title":     title,
            "research_question": question,
            "artefact_type":     artefact,
            "supervisor":        supervisor,
            "stage":             stage,
            "final_mark":        mark,
            "final_grade":       grade,
            "notes":             notes,
        })
        print(f"\n  ✓ Updated EPQ project #{out.project_id}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("edit_project failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def delete_project_flow() -> None:
    print("\n═══ Delete EPQ Project ═══")
    try:
        p = _pick_project()
        _print_full(p)
        if not _yes_no("\n  Delete this project (and its log & milestones)?"):
            print("  (cancelled)")
            return
        if data.delete_project(p.project_id):
            print(f"\n  ✓ Deleted EPQ project #{p.project_id}.")
        else:
            print("\n  ✗ Delete failed.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except Exception as e:
        logger.exception("delete_project_flow failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def add_log_entry() -> None:
    print("\n═══ Add Production-Log Entry ═══")
    try:
        p = _pick_project()
        date_s = _input("Entry date (YYYY-MM-DD)", allow_empty=False)
        hours = _input("Hours spent (e.g. 1.5)", allow_empty=False)
        activity = _input("Activity (one-line summary)", allow_empty=False)
        reflection = _multiline("Reflection (optional)")
        entry = data.create_log_entry({
            "project_id": p.project_id,
            "entry_date": date_s,
            "hours":      hours,
            "activity":   activity,
            "reflection": reflection,
        })
        total = data.total_hours_for_project(p.project_id)
        print(f"\n  ✓ Added log entry #{entry.log_id} "
              f"({entry.hours}h). Project total: {total:.1f}h.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("add_log_entry failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def save_milestone_flow() -> None:
    print("\n═══ Save / Update Milestone ═══")
    try:
        p = _pick_project()
        mtype = _pick_from("Milestone type", list(MILESTONE_TYPES))
        existing = next((m for m in data.list_milestones(p.project_id)
                          if m.milestone_type == mtype), None)
        due = _input("Due date (YYYY-MM-DD, optional)",
                      default=(existing.due_date if existing else ""))
        status = _pick_from("Status", list(MILESTONE_STATUSES),
                              default=(existing.status if existing
                                       else DEFAULT_MILESTONE_STATUS))
        completed = ""
        if status == "Completed":
            completed = _input(
                "Completed date (YYYY-MM-DD, ENTER for today)",
                default=(existing.completed_date if existing
                          and existing.completed_date else ""))
        notes = _multiline("Notes (optional)",
                            default=(existing.notes if existing else "") or "")
        out = data.save_milestone({
            "project_id":     p.project_id,
            "milestone_type": mtype,
            "due_date":       due,
            "completed_date": completed,
            "status":         status,
            "notes":          notes,
        })
        print(f"\n  ✓ Saved milestone {out.milestone_type} "
              f"(status={out.status}).")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("save_milestone_flow failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def show_summary() -> None:
    print("\n═══ EPQ Summary ═══")
    try:
        s = data.summary()
        print(f"\n  Total projects        : {s.total_projects}")
        print(f"  Total production-log  : {s.total_log_hours:.1f} hrs")
        print(f"  Overdue milestones    : {s.overdue_milestones}")
        print(f"  Upcoming milestones   : {s.upcoming_milestones}"
              "  (next 21 days)")
        print("\n  By stage:")
        for stage, n in s.by_stage.items():
            if n:
                print(f"    {stage:<14} {n:>3}")
        print("\n  By artefact type:")
        for art, n in s.by_artefact.items():
            if n:
                print(f"    {art:<14} {n:>3}")
        any_grades = any(n for n in s.by_grade.values())
        if any_grades:
            print("\n  By final grade:")
            for g, n in s.by_grade.items():
                if n:
                    print(f"    {g:<14} {n:>3}")
        _pause()
    except Exception as e:
        logger.exception("show_summary failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


# ── Menu ─────────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all projects",            list_all),
    ("List projects by stage",       list_by_stage),
    ("List projects by artefact",    list_by_artefact),
    ("View project (detail)",        view_project),
    ("Add project",                  add_project),
    ("Edit project",                 edit_project),
    ("Delete project",               delete_project_flow),
    ("Add production-log entry",     add_log_entry),
    ("Save / update milestone",      save_milestone_flow),
    ("Summary report",               show_summary),
]


def run() -> None:
    while True:
        print("\n══════ Extended Project Qualification ══════")
        for i, (label, _fn) in enumerate(_MENU, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        _label, fn = _MENU[int(choice) - 1]
        try:
            fn()
        except _UserAbort:
            print("\n  (cancelled)")
        except Exception as e:
            logger.exception("EPQ CLI flow crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "EPQ":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("EPQ CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
