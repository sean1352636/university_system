"""Lesson Plans in the terminal. The old options 1-6 are kept (new, list, view,
edit, set status, delete); 7-11 are added. Rules live in
:mod:`modules.curriculum.domain.lesson_plans`. When editing, Enter keeps a value and ``-`` clears it."""

from __future__ import annotations

import datetime as _dt

from education_system.systems.secondary.modules.curriculum.domain import lesson_plans as LP
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import LESSON_PLAN_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_problem = prompts.problem


def _warn(warnings: list[str]) -> None:
    for w in warnings:
        print(f"  ⚠ {w}")


def _print_list(plans: list[LP.Plan]) -> None:
    if not plans:
        print("  (no plans)")
        return
    print(f"  {'ID':<5} {'Date':<11} {'P':<2} {'Yr':<3} {'Group':<9} {'Subj':<6} "
          f"{'Title':<34} {'Teacher':<16} Status")
    for p in plans:
        print(f"  {p.plan_id:<5} {p.planned_date or 'shared':<11} {p.period or '':<2} "
              f"{p.year_group:<3} {(p.group_code or '-')[:9]:<9} {p.subject_code[:6]:<6} "
              f"{p.title[:34]:<34} {(p.teacher_name or '')[:16]:<16} {p.status}")


def _choose() -> LP.Plan | None:
    raw = _prompt("  Plan ID: ")
    if not raw.isdigit():
        return None
    try:
        return LP.get(int(raw))
    except LP.NotFound:
        print("  No such plan.")
        return None


def _pick_subject() -> S.Subject | None:
    code = _prompt("  Subject code: ")
    s = S.get_by_code(code) if code else None
    if s is None and code:
        print("  No such subject.")
    return s


def menu(principal: Principal) -> None:
    editor = principal.role in LESSON_PLAN_EDITORS
    while True:
        activity_log.record("lesson_plans.view")
        counts = LP.status_counts()
        print("\n── Lesson Plans ──")
        print("  " + " · ".join(f"{k} {v}" for k, v in counts.items()))
        print("   1) New plan\n   2) List plans\n   3) View plan\n   4) Edit plan"
              "\n   5) Set status\n   6) Delete plan\n   7) My lessons this week"
              "\n   8) Copy a plan\n   9) Plan from timetable\n  10) Schemes of work"
              "\n  11) Export a plan to a text file\n   0) Back")
        c = _prompt("Select: ")
        if c in {"0", ""}:
            return
        try:
            {"1": lambda: _new(principal), "2": _list, "3": _view,
             "4": lambda: _edit(principal), "5": lambda: _status(principal),
             "6": lambda: _delete(principal), "7": lambda: _week(principal),
             "8": lambda: _copy(principal), "9": lambda: _from_timetable(principal),
             "10": lambda: _units(principal, editor), "11": lambda: _export(principal),
             }.get(c, lambda: print("  Invalid selection."))()
        except (LP.ValidationError, LP.PermissionDenied, LP.NotFound) as e:
            _problem(e)


def _list() -> None:
    print("  Filter (Enter to skip each):")
    y = _prompt("   Year (7-11): ")
    st = _prompt(f"   Status ({'/'.join(LP.STATUSES)}): ").title()
    teacher = _prompt("   Teacher (name or login): ")
    group = _prompt("   Teaching group code: ")
    g = TG.find(group) if group else None
    if group and g is None:
        print("  No such group this year.")
        return
    search = _prompt("   Search titles/objectives: ")
    _print_list(LP.list_plans(year_group=int(y) if y.isdigit() else None,
                              status=st or None, teacher=teacher or None,
                              group_id=g.group_id if g else None, search=search or None))
    _pause()


def _view() -> None:
    p = _choose()
    if p:
        print()
        print("  " + LP.as_text(p.plan_id).replace("\n", "\n  "))
        print(f"  Written by {p.created_by or '-'}; last changed {p.updated_at} by "
              f"{p.updated_by or '-'}")
        _pause()


def _collect(p: LP.Plan | None) -> dict:
    data: dict = {}
    v = _ask("Title", p.title if p else None, required=p is None)
    if v is not None:
        data["title"] = v
    if p is None:
        code = _prompt("  Teaching group code (Enter = shared plan for a subject and year): ")
        if code:
            g = TG.find(code)
            if g is None:
                raise LP.ValidationError([f"No group {code} this year"])
            data["group_id"] = g.group_id
        else:
            s = _pick_subject()
            data.update(group_id=None, subject_id=s.subject_id if s else None,
                        year_group=_prompt("  Year (7-11): ") or None)
    shared = p.is_shared if p else data.get("group_id") is None
    v = _ask("Date", p.planned_date if p else None, required=not shared, hint="YYYY-MM-DD")
    if v is not None:
        data["planned_date"] = v
    v = _ask("Period", str(p.period) if p and p.period else None, hint="number, optional")
    if v is not None:
        data["period"] = v
    sid = p.subject_id if p else data.get("subject_id")
    if sid is None and data.get("group_id"):
        sid = TG.get(data["group_id"]).subject_id
    yr = p.year_group if p else (TG.get(data["group_id"]).year_group if data.get("group_id")
                                 else data.get("year_group"))
    units = LP.list_units(subject_id=sid, year_group=int(yr)) if sid and str(yr).isdigit() \
        else []
    if units:
        for i, u in enumerate(units, 1):
            print(f"   {i}) {u.term} {u.label}")
        raw = _prompt("  Unit number (Enter = " + ("keep" if p else "none") + ", '-' = none): ")
        if raw == "-":
            data["unit_id"] = None
        elif raw.isdigit() and 1 <= int(raw) <= len(units):
            data["unit_id"] = units[int(raw) - 1].unit_id
    for key, label in LP.TEXT_FIELDS:
        if key == "evaluation" and p is None:
            continue
        v = _ask(label, getattr(p, key) if p else None)
        if v is not None:
            data[key] = v
    return data


def _new(principal: Principal) -> None:
    print("\n  ── New lesson plan ──")
    p, warnings = LP.create(_collect(None), actor=principal)
    _warn(warnings)
    print(f"  ✓ Plan #{p.plan_id} saved as Draft.")


def _edit(principal: Principal) -> None:
    p = _choose()
    if not p:
        return
    if not LP.can_change(principal, p):
        print("  Only the plan's teacher (or whoever wrote it) can change it.")
        return
    print("  Enter keeps a value, '-' clears it.")
    q, warnings = LP.update(p.plan_id, _collect(p), actor=principal)
    _warn(warnings)
    print(f"  ✓ Saved #{q.plan_id}.")


def _status(principal: Principal) -> None:
    p = _choose()
    if not p:
        return
    print(f"  Current status: {p.status}")
    for i, s in enumerate(LP.STATUSES, 1):
        why = LP.status_problems(p, s, evaluation="x" if s == "Reviewed" else None)
        print(f"   {i}) {s}" + (f"  - {why[0]}" if why and s != p.status else ""))
    raw = _prompt("  New status: ")
    if not raw.isdigit() or not 1 <= int(raw) <= len(LP.STATUSES):
        return
    status = LP.STATUSES[int(raw) - 1]
    ev = _prompt("  Evaluation (what went well, next steps): ") if status == "Reviewed" \
        else None
    q = LP.set_status(p.plan_id, status, actor=principal, evaluation=ev)
    print(f"  ✓ {q.title}: {q.status}")


def _delete(principal: Principal) -> None:
    p = _choose()
    if p and _yes(f"  Delete '{p.title}' ({p.when})?"):
        LP.delete(p.plan_id, actor=principal)
        print("  ✓ Deleted.")


def _week(principal: Principal) -> None:
    today = _dt.date.today()
    monday = today - _dt.timedelta(days=today.weekday())
    raw = _prompt(f"  Week starting [{monday.isoformat()}]: ")
    try:
        start = _dt.date.fromisoformat(raw) if raw else monday
    except ValueError:
        print("  Not a date.")
        return
    mine = _yes("  Only my lessons?")
    rows = LP.coverage(start, start + _dt.timedelta(days=4),
                       teacher=principal.username if mine else None)
    if not rows:
        print("  No timetabled lessons.")
    for d, x, p in rows:
        print(f"  {d:%a %d %b} P{x.period:<2} {x.subject_code:<6} {x.group_code:<10} "
              + (f"#{p.plan_id} {p.title[:34]} [{p.status}]" if p else "- no plan -"))
    print(f"\n  {sum(1 for *_r, p in rows if p is None)} lesson(s) without a plan.")
    _pause()


def _copy(principal: Principal) -> None:
    p = _choose()
    if not p:
        return
    code = _prompt("  Copy to group code (Enter = as a shared plan): ")
    if code:
        g = TG.find(code)
        if g is None:
            print("  No such group this year.")
            return
        new, warnings = LP.copy(p.plan_id, actor=principal, group_id=g.group_id,
                                planned_date=_prompt("  Date (YYYY-MM-DD): ") or None,
                                period=_prompt("  Period: ") or None)
    else:
        new, warnings = LP.copy(p.plan_id, actor=principal, shared=True)
    _warn(warnings)
    print(f"  ✓ Copied as #{new.plan_id} (Draft).")


def _from_timetable(principal: Principal) -> None:
    g = TG.find(_prompt("  Teaching group code: "))
    if g is None:
        print("  No such group this year.")
        return
    today = _dt.date.today()
    start = _prompt(f"  From [{today.isoformat()}]: ") or today.isoformat()
    end = _prompt(f"  To [{(today + _dt.timedelta(days=13)).isoformat()}]: ") or (
        today + _dt.timedelta(days=13)).isoformat()
    units = LP.list_units(subject_id=g.subject_id, year_group=g.year_group)
    unit = None
    for i, u in enumerate(units, 1):
        print(f"   {i}) {u.term} {u.label}")
    if units:
        raw = _prompt("  Unit number (Enter = none): ")
        unit = units[int(raw) - 1] if raw.isdigit() and 1 <= int(raw) <= len(units) else None
    created, skipped = LP.plan_from_timetable(g.group_id, start, end, actor=principal,
                                              unit_id=unit.unit_id if unit else None)
    print(f"  ✓ Created {len(created)} draft plan(s); {skipped} lesson(s) already had one.")


def _units(principal: Principal, editor: bool) -> None:
    s = _pick_subject()
    y = _prompt("  Year (7-11, Enter = all): ")
    units = LP.list_units(subject_id=s.subject_id if s else None,
                          year_group=int(y) if y.isdigit() else None, include_archived=True)
    if not units:
        print("  No units.")
    for u in units:
        prog = "; ".join(f"{g.group_code or 'shared'} {g.planned}/{g.delivered}"
                         for g in LP.unit_progress(u.unit_id)) or "no plans yet"
        print(f"  #{u.unit_id:<4} Y{u.year_group} {u.term:<7} {u.label[:36]:<36} "
              f"lessons {u.lessons or '-':<4} {prog}" + ("" if u.is_active else " (archived)"))
    if not editor:
        _pause()
        return
    c = _prompt("  N) New unit   E) Edit   A) Archive/restore   D) Delete   Enter) Back: "
                ).lower()
    if c == "n":
        subj = s or _pick_subject()
        if subj is None:
            return
        u = LP.create_unit({"subject_id": subj.subject_id,
                            "year_group": y or _prompt("  Year (7-11): "),
                            "title": _prompt("  Title: "),
                            "term": _prompt("  Term (Autumn/Spring/Summer/Any) [Any]: ") or "Any",
                            "sequence": _prompt("  Order [1]: ") or None,
                            "lessons": _prompt("  Number of lessons: ") or None,
                            "overview": _prompt("  Overview: ")}, actor=principal)
        print(f"  ✓ Unit #{u.unit_id} created.")
        return
    raw = _prompt("  Unit #: ") if c in {"e", "a", "d"} else ""
    if not raw.isdigit():
        return
    u = LP.get_unit(int(raw))
    if c == "e":
        changes = {}
        for key, label in (("title", "Title"), ("term", "Term"), ("sequence", "Order"),
                           ("lessons", "Number of lessons"), ("overview", "Overview")):
            v = _ask(label, None if getattr(u, key) is None else str(getattr(u, key)))
            if v is not None:
                changes[key] = v or None
        LP.update_unit(u.unit_id, changes, actor=principal)
        print("  ✓ Saved.")
    elif c == "a":
        (LP.archive_unit if u.is_active else LP.restore_unit)(u.unit_id, actor=principal)
        print("  ✓ Done.")
    elif c == "d" and _yes(f"  Delete '{u.title}'?"):
        LP.delete_unit(u.unit_id, actor=principal)
        print("  ✓ Deleted.")


def _export(principal: Principal) -> None:
    p = _choose()
    if not p:
        return
    path = _prompt(f"  Save to [lesson-plan-{p.plan_id}.txt]: ") or f"lesson-plan-{p.plan_id}.txt"
    LP.export_text(p.plan_id, path, actor=principal)
    print(f"  ✓ Saved to {path}")
