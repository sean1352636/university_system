"""Timetable in the terminal (old New / List / Weekly grid / View / Edit / Delete
kept, plus Today, Clashes, Lessons needed and Settings). Rules live in
:mod:`modules.curriculum.domain.timetable`. When editing, Enter keeps a value and ``-`` clears it."""

from __future__ import annotations

import datetime as _dt

from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.curriculum.domain import timetable as TT
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import TIMETABLE_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_problem = prompts.problem


def _filters() -> dict | None:
    print("  Filter (Enter to skip each): ")
    f: dict = {}
    y = _prompt("   Year (7-11): ")
    if y.isdigit() and int(y) in P.YEAR_GROUPS:
        f["year_group"] = int(y)
    form = _prompt("   Form: ")
    if form:
        f["form"] = form
    t = _prompt("   Teacher (name or login): ")
    if t:
        f["teacher"] = t
    room = _prompt("   Room: ")
    if room:
        f["room"] = room
    ref = _prompt("   Pupil admission no. / UPN: ")
    if ref:
        p = P.find_by_reference(ref)
        if p is None:
            print("  No such pupil.")
            return None
        f["pupil_id"] = p.pupil_id
    return f


def _print_list(lessons: list[TT.Lesson]) -> None:
    if not lessons:
        print("  (no lessons)")
        return
    print(f"  {'ID':<5} {'When':<22} {'Subject':<8} {'Group':<12} {'Yr':<3} {'Teacher':<20} Room")
    for x in lessons:
        print(f"  {x.lesson_id:<5} {x.slot_label[:22]:<22} {x.subject_code:<8} "
              f"{x.group_code[:12]:<12} {x.year_group:<3} {(x.teacher or '—')[:20]:<20} "
              f"{x.room or ''}")


def _print_grid(lessons: list[TT.Lesson], week: int) -> None:
    cells = TT.grid([x for x in lessons if x.week == week])
    width = 22
    if TT.cycle_weeks() == 2:
        print(f"\n  {TT.WEEK_LABELS[week]}")
    print("  " + " " * 7 + "".join(f"{d:<{width}}" for d in TT.DAYS))
    for p in TT.periods():
        here = [cells.get((week, d, p.period), []) for d in range(1, 6)]
        lines = max(1, *(len(h) for h in here))
        for i in range(min(lines, 3)):
            label = p.label if i == 0 else ""
            row = "".join(f"{(h[i].subject_code + ' ' + h[i].group_code)[:width - 1] if i < len(h) else ('–' if i == 0 else ''):<{width}}"
                          for h in here)
            print(f"  {label:<7}{row}")
        if lines > 3:
            print(f"  {'':<7}(+ more)")


def _choose_lesson() -> TT.Lesson | None:
    raw = _prompt("  Lesson ID: ")
    if not raw.isdigit():
        return None
    try:
        return TT.get(int(raw))
    except TT.NotFound:
        print("  No such lesson.")
        return None


def menu(principal: Principal) -> None:
    editor = principal.role in TIMETABLE_EDITORS
    while True:
        activity_log.record("timetable.view")
        n = len(TT.list_lessons())
        clash = len(TT.clashes())
        print(f"\n── Timetable ({TG.current_year()}) ──")
        print(f"  {n} lesson(s) · {TT.cycle_weeks()}-week cycle · {len(TT.periods())} periods"
              + (f" · ! {clash} clash(es)" if clash else ""))
        print("\n   1) New lesson\n   2) List lessons\n   3) Weekly grid (filtered)"
              "\n   4) View lesson\n   5) Edit lesson\n   6) Delete lesson\n   7) Today"
              "\n   8) Clashes\n   9) Lessons needed\n  10) Periods & week cycle\n   0) Back")
        c = _prompt("Select: ")
        if c in {"0", ""}:
            return
        if c in {"1", "5", "6"} and not editor:
            print("  Your account can view the timetable but not change it.")
            continue
        try:
            {"1": lambda: _new(principal), "2": _list, "3": _grid, "4": _view,
             "5": lambda: _edit(principal), "6": lambda: _delete(principal),
             "7": lambda: _today(principal), "8": _clashes, "9": _needed,
             "10": lambda: _settings(principal, editor),
             }.get(c, lambda: print("  Invalid selection."))()
        except (TT.ValidationError, TT.PermissionDenied) as e:
            _problem(e)


def _list() -> None:
    f = _filters()
    if f is not None:
        _print_list(TT.list_lessons(**f))
        _pause()


def _grid() -> None:
    f = _filters()
    if f is None:
        return
    lessons = TT.list_lessons(**f)
    for w in range(1, TT.cycle_weeks() + 1):
        _print_grid(lessons, w)
    _pause()


def _view() -> None:
    x = _choose_lesson()
    if x:
        print(f"\n  {x.slot_label}: {x.subject_name} · {x.group_code} (Year {x.year_group})")
        print(f"  Teacher: {x.teacher or '—'}" + (" (this lesson only)"
                                                  if x.teacher_name_override else ""))
        print(f"  Room: {x.room or '—'}" + (" (this lesson only)" if x.room_override else ""))
        if x.notes:
            print(f"  Notes: {x.notes}")
        _pause()


def _collect(x: TT.Lesson | None) -> dict:
    data: dict = {}
    code = _ask("Teaching group code", x.group_code if x else None, required=x is None)
    if code is not None:
        g = TG.find(code)
        if g is None:
            raise TT.ValidationError([f"No group {code} this year"])
        data["group_id"] = g.group_id
    if TT.cycle_weeks() == 2:
        v = _ask("Week", ("A" if x.week == 1 else "B") if x else None, hint="A/B")
        if v is not None:
            data["week"] = v
    v = _ask("Day", TT.DAYS[x.day - 1] if x else None, required=x is None, hint="Mon-Fri")
    if v is not None:
        data["day"] = v
    plist = TT.periods()
    v = _ask("Period", str(x.period) if x else None, required=x is None,
             hint=", ".join(f"{p.period}={p.label} {p.start_time}" for p in plist))
    if v is not None:
        data["period"] = v
    for key, label, cur in (("room", "Room (blank = group's)", x.room_override if x else None),
                            ("teacher_name", "Teacher (blank = group's)",
                             x.teacher_name_override if x else None),
                            ("notes", "Notes", x.notes if x else None)):
        v = _ask(label, cur)
        if v is not None:
            data[key] = v
    return data


def _save(principal: Principal, data: dict, x: TT.Lesson | None) -> None:
    found = TT.check(data, x.lesson_id if x else None)
    allow = False
    if found:
        for f in found:
            print(f"  ⚠ {f}")
        if any(f.endswith("already has a lesson then") for f in found) or not _yes(
                "  Book it anyway?"):
            return
        allow = True
    if x is None:
        y = TT.add_lesson(data, actor=principal, allow_clash=allow)
    else:
        y = TT.update_lesson(x.lesson_id, data, actor=principal, allow_clash=allow)
    print(f"  ✓ {y.slot_label}: {y.subject_code} {y.group_code}")


def _new(principal: Principal) -> None:
    print("\n  ── New lesson ──")
    _save(principal, _collect(None), None)


def _edit(principal: Principal) -> None:
    x = _choose_lesson()
    if x:
        print("  Enter keeps a value, '-' clears it.")
        _save(principal, _collect(x), x)


def _delete(principal: Principal) -> None:
    x = _choose_lesson()
    if x and _yes(f"  Delete {x.slot_label} {x.group_code}?"):
        TT.delete_lesson(x.lesson_id, actor=principal)
        print("  ✓ Deleted.")


def _today(principal: Principal) -> None:
    raw = _prompt("  Date (YYYY-MM-DD, Enter = today): ")
    try:
        day = _dt.date.fromisoformat(raw) if raw else _dt.date.today()
    except ValueError:
        print("  Not a date.")
        return
    mine = _yes("  Only my lessons?")
    lessons, what = TT.lessons_on(day, **({"teacher": principal.username} if mine else {}))
    print(f"\n  {day:%A %d %B %Y} - {what}")
    times = {p.period: p for p in TT.periods()}
    for x in lessons:
        p = times.get(x.period)
        print(f"  {p.label if p else x.period:<5} {p.times if p else '':<12} {x.subject_code:<8} "
              f"{x.group_code:<12} {(x.teacher or '')[:20]:<20} {x.room or ''}")
    if not lessons:
        print("  No lessons.")
    _pause()


def _clashes() -> None:
    found = TT.clashes()
    if not found:
        print("  No clashes.")
    for a, b, why in found:
        print(f"  {a.slot_label}: {a.group_code} / {b.group_code} - {'; '.join(why)}")
    _pause()


def _needed() -> None:
    per = "fortnight" if TT.cycle_weeks() == 2 else "week"
    print(f"  Lessons per {per}: needed / timetabled")
    for r in TT.requirements():
        if r.status != "ok":
            g = r.info.group
            print(f"  {g.code:<12} {r.info.subject.code:<8} Y{g.year_group}  "
                  f"{r.needed if r.needed is not None else '—':>3} / {r.scheduled:<3} {r.status}")
    if all(r.status == "ok" for r in TT.requirements()):
        print("  Every group has the lessons it needs.")
    _pause()


def _settings(principal: Principal, editor: bool) -> None:
    for p in TT.periods():
        print(f"  {p.period}) {p.label:<6} {p.times}")
    print(f"  Cycle: {TT.cycle_weeks()} week(s); Week A restarts each {TT.cycle_restart()}")
    if not editor:
        _pause()
        return
    c = _prompt("  P) Set periods   C) Set cycle   W) Copy Week A to B   Enter) Back: ").lower()
    if c == "p":
        rows = []
        print("  Enter each period as 'label start end' (e.g. P1 08:50 09:50); blank line ends.")
        while True:
            line = _prompt(f"   Period {len(rows) + 1}: ").split()
            if not line:
                break
            if len(line) != 3:
                print("   Three parts please: label start end")
                continue
            rows.append({"label": line[0], "start_time": line[1], "end_time": line[2]})
        if rows:
            TT.set_periods(rows, actor=principal)
            print("  ✓ Saved.")
    elif c == "c":
        w = _prompt("  Weeks in the cycle (1 or 2): ")
        r = "term" if _yes("  Restart Week A each term? (No = each year)") else "year"
        TT.set_cycle(w, r, actor=principal)
        print("  ✓ Saved.")
    elif c == "w":
        n, notes = TT.copy_week(actor=principal)
        print(f"  ✓ {n} copied.")
        for note in notes[:15]:
            print(f"  · skipped {note}")
