"""Homework in the terminal. The old options 1-12 are kept (new, list, view,
edit, set status, seed, record a submission, list submissions, pupil history,
summary, delete a submission, delete); 13-20 are added. Rules live in
:mod:`modules.curriculum.domain.homework`."""

from __future__ import annotations

import datetime as _dt

from education_system.systems.secondary.modules.curriculum.domain import homework as HW
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import HOMEWORK_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (HW.ValidationError, HW.PermissionDenied, HW.NotFound)


_problem = prompts.problem


def _warn(warnings: list[str]) -> None:
    for w in warnings:
        print(f"  ! {w}")


def _print(rows: list[HW.Task]) -> None:
    if not rows:
        print("  (no homework)")
        return
    print(f"  {'ID':<5} {'Due':<10} {'Yr':<3} {'For':<9} {'Subj':<6} {'Title':<30} "
          f"{'Set by':<14} {'Pts':<4} Status")
    for t in rows:
        flag = " OVERDUE" if t.overdue else ""
        print(f"  {t.task_id:<5} {t.due_date:<10} {t.year_group:<3} {t.for_label[:9]:<9} "
              f"{t.subject_code[:6]:<6} {t.title[:30]:<30} {(t.set_by_name or '')[:14]:<14} "
              f"{str(t.points or ''):<4} {t.status}{flag}")


def _print_work(rows: list[HW.Work]) -> None:
    if not rows:
        print("  (no pupils on the list - set the homework or seed it)")
        return
    print(f"  {'Pupil':<24} {'Adm no':<10} {'Handed in':<10} {'Status':<9} {'Mark':<12} "
          "Feedback")
    for w in rows:
        print(f"  {w.pupil_name[:24]:<24} {w.admission_no:<10} {(w.handed_in or ''):<10} "
              f"{w.status:<9} {w.mark_label[:12]:<12} "
              f"{(w.feedback or w.excuse_reason or '')[:40]}")


def _choose() -> HW.Task | None:
    raw = _prompt("  Homework ID: ")
    if not raw.isdigit():
        return None
    try:
        return HW.get(int(raw))
    except HW.NotFound:
        print("  No such homework.")
        return None


def _choose_pupil(task: HW.Task) -> P.Pupil | None:
    pupils = HW.pupils_for(task)
    ref = _prompt("  Pupil (admission no, or part of the name): ").lower()
    if not ref:
        return None
    hits = [p for p in pupils if ref == p.admission_no.lower() or ref in p.full_name.lower()
            or ref in p.display_name.lower()]
    if not hits:
        print(f"  Nobody like that in {task.for_label}.")
        return None
    if len(hits) > 1:
        for i, p in enumerate(hits[:20], 1):
            print(f"   {i}) {p.display_name} ({p.admission_no})")
        n = _prompt("  Which? ")
        return hits[int(n) - 1] if n.isdigit() and 0 < int(n) <= len(hits[:20]) else None
    return hits[0]


def menu(principal: Principal) -> None:
    editor = principal.role in HOMEWORK_EDITORS
    while True:
        activity_log.record("homework.view")
        c = HW.status_counts()
        marking = sum(n for _t, n in HW.to_mark(principal))
        print("\n── Homework ──")
        print(f"  Homework: {sum(c.values())}   Draft {c['Draft']} · Set {c['Set']} · "
              f"Closed {c['Closed']}" + (f"   · {marking} piece(s) for you to mark"
                                         if marking else ""))
        print("   1) New homework\n   2) List homework\n   3) View homework"
              "\n   4) Edit homework\n   5) Set homework status"
              "\n   6) Seed submissions (add the class)\n   7) Record / update a submission"
              "\n   8) List submissions for a homework\n   9) Pupil homework history"
              "\n  10) Submission summary\n  11) Delete a submission\n  12) Delete homework"
              "\n  13) My homework / to mark\n  14) Tick off several pupils"
              "\n  15) Missing homework report\n  16) Homework due this week"
              "\n  17) Copy homework to another group\n  18) E-mail parents about missing "
              "homework\n  19) Export marks (CSV)\n  20) Daily homework limit\n   0) Back")
        choice = _prompt("Select: ")
        if choice in {"0", ""}:
            return
        try:
            {"1": lambda: _new(principal), "2": _list, "3": _view,
             "4": lambda: _edit(principal), "5": lambda: _status(principal),
             "6": lambda: _seed(principal), "7": lambda: _record(principal),
             "8": _list_work, "9": _pupil_history, "10": _summary,
             "11": lambda: _delete_work(principal), "12": lambda: _delete(principal),
             "13": lambda: _mine(principal), "14": lambda: _tick(principal),
             "15": _missing, "16": _week, "17": lambda: _copy(principal),
             "18": lambda: _email(principal), "19": lambda: _export(principal),
             "20": lambda: _limit(principal, editor),
             }.get(choice, lambda: print("  Invalid selection."))()
        except _ERRORS as e:
            _problem(e)


def _collect(existing: HW.Task | None) -> dict:
    data: dict = {}

    def ask(key: str, label: str, current=None, **kw) -> None:
        v = _ask(label, None if current is None else str(current), **kw)
        if v is not None:
            data[key] = v
    ask("title", "Title", existing.title if existing else None, required=existing is None)
    if existing is None or existing.status == "Draft":
        code = _prompt("  Teaching group code (Enter = a whole year instead)"
                       + (f" [{existing.group_code}]" if existing and existing.group_code
                          else "") + ": ")
        if code:
            g = TG.find(code)
            if g is None:
                raise HW.ValidationError([f"No group {code} this year"])
            data["group_id"] = g.group_id
        elif existing is None or existing.group_id is None:
            subjects = S.list_subjects()
            for s in subjects:
                print(f"    {s.code:<8} {s.name}")
            sc = _prompt("  Subject code"
                         + (f" [{existing.subject_code}]" if existing else "") + ": ")
            hit = next((s for s in subjects if s.code.lower() == sc.lower()), None)
            if sc and hit is None:
                raise HW.ValidationError([f"No subject {sc}"])
            if hit:
                data["subject_id"] = hit.subject_id
            data["group_id"] = None
            ask("year_group", "Year group", existing.year_group if existing else None,
                hint="7-11")
            ask("form_group", "Form (optional)", existing.form_group if existing else None)
    ask("set_date", "Set date", existing.set_date if existing else _dt.date.today(),
        hint="YYYY-MM-DD")
    ask("due_date", "Due date", existing.due_date if existing else None, hint="YYYY-MM-DD",
        required=existing is None)
    ask("points", "Points (marked out of)", existing.points if existing else None)
    ask("est_minutes", "Expected time (minutes)", existing.est_minutes if existing else None)
    ask("instructions", "Instructions", existing.instructions if existing else None)
    ask("resources", "Resources / links", existing.resources if existing else None)
    ask("notes", "Notes", existing.notes if existing else None)
    return data


def _new(principal: Principal) -> None:
    print("\n  ── New homework ── (- clears a field)")
    data = _collect(None)
    if _yes("  Set it now (adds the class)?"):
        data["status"] = "Set"
    t, warnings = HW.create(data, actor=principal)
    print(f"  ✓ Homework #{t.task_id} '{t.title}' for {t.for_label}, due {t.due_date} "
          f"({t.status})")
    _warn(warnings)


def _list() -> None:
    year = _prompt("  Year (7-11, Enter = all): ")
    st = _prompt(f"  Status ({'/'.join(HW.STATUSES)}, Enter = all): ").title()
    teacher = _prompt("  Set by / teacher (Enter = all): ")
    rows = HW.list_tasks(year_group=int(year) if year.isdigit() else None,
                         status=st or None, teacher=teacher or None)
    print(f"\n  {len(rows)} homework(s):")
    _print(rows)
    _pause()


def _view() -> None:
    t = _choose()
    if t:
        print()
        print("  " + HW.as_text(t.task_id).replace("\n", "\n  "))
        s = HW.summary(t.task_id)
        if s["total"]:
            print(f"  {s['total']} pupils · handed in {s['handed_in']} · to mark "
                  f"{s['to_mark']} · missing {s['by_status']['Missing']}")
        _pause()


def _edit(principal: Principal) -> None:
    t = _choose()
    if not t:
        return
    print("  Press Enter to keep a value, - to clear it.")
    t, warnings = HW.update(t.task_id, _collect(t), actor=principal)
    print(f"  ✓ Updated #{t.task_id}")
    _warn(warnings)


def _status(principal: Principal) -> None:
    t = _choose()
    if not t:
        return
    print(f"  Now: {t.status}.  Draft = not set · Set = adds the class · Closed = Pending "
          "become Missing")
    new = _prompt(f"  New status ({'/'.join(HW.STATUSES)}): ")
    if new:
        t, warnings = HW.set_status(t.task_id, new, actor=principal)
        print(f"  ✓ #{t.task_id} is {t.status}")
        _warn(warnings)


def _seed(principal: Principal) -> None:
    t = _choose()
    if t:
        print(f"  ✓ Added {HW.seed(t.task_id, actor=principal)} pupil(s)")


def _record(principal: Principal) -> None:
    t = _choose()
    if not t:
        return
    p = _choose_pupil(t)
    if not p:
        return
    w = HW.get_work(t.task_id, p.pupil_id)
    if w:
        print(f"  Now: {w.status} · handed in {w.handed_in or '-'} · {w.mark_label or 'no mark'}")
    status = _prompt(f"  Status ({'/'.join(HW.WORK_STATUSES)})"
                     + (f" [{w.status}]" if w else "") + ": ").title()
    data: dict = {}
    if status:
        data["status"] = status
    final = status or (w.status if w else "Pending")
    if final in HW.HANDED_IN:
        for key, label in (("handed_in", "Handed in (YYYY-MM-DD, Enter = today/keep)"),
                           ("mark", f"Mark (out of {t.points})" if t.points else "Mark (%)"),
                           ("grade", "Grade")):
            v = _ask(label)
            if v is not None:
                data[key] = v
    if final == "Excused":
        data["excuse_reason"] = _prompt("  Why are they excused? ")
    v = _ask("Feedback", w.feedback if w else None)
    if v is not None:
        data["feedback"] = v
    w = HW.record(t.task_id, p.pupil_id, data, actor=principal)
    print(f"  ✓ {p.display_name}: {w.status}" + (f" · {w.mark_label}" if w.mark_label else ""))


def _list_work() -> None:
    t = _choose()
    if t:
        print(f"\n  {t.title} - {t.for_label}, due {t.due_date}")
        _print_work(HW.list_work(t.task_id))
        _pause()


def _pupil_history() -> None:
    ref = _prompt("  Pupil admission no or UPN: ")
    p = P.find_by_reference(ref) if ref else None
    if p is None:
        print("  No such pupil.")
        return
    s = HW.pupil_summary(p.pupil_id)
    print(f"\n  {p.display_name} - this year: {s.set} due, {s.handed_in} handed in "
          f"({s.late} late), {s.missing} missing"
          + (f", average {s.average_pct}%" if s.average_pct is not None else ""))
    rows = HW.for_pupil(p.pupil_id)
    if not rows:
        print("  (no homework)")
    for w in rows:
        print(f"  {w.due_date:<10} {w.subject_code:<6} {w.title[:30]:<30} {w.status:<9} "
              f"{w.mark_label}")
    _pause()


def _summary() -> None:
    t = _choose()
    if not t:
        return
    s = HW.summary(t.task_id)
    print(f"\n  {t.title} ({t.for_label}, due {t.due_date}) - {s['total']} pupils")
    for k, v in s["by_status"].items():
        print(f"    {k:<10} {v}")
    print(f"  Handed in {s['handed_in']} (late {s['late']}) · completion "
          f"{s['completion_pct'] if s['completion_pct'] is not None else '-'}% · "
          f"average mark {s['average_pct'] if s['average_pct'] is not None else '-'}%")
    _pause()


def _delete_work(principal: Principal) -> None:
    t = _choose()
    if not t:
        return
    p = _choose_pupil(t)
    if p and _yes(f"  Remove {p.display_name} from this homework's list?"):
        HW.delete_work(t.task_id, p.pupil_id, actor=principal)
        print("  ✓ Removed")


def _delete(principal: Principal) -> None:
    t = _choose()
    if t and _yes(f"  Delete '{t.title}' for {t.for_label} and every pupil's record of it?"):
        HW.delete(t.task_id, actor=principal)
        print("  ✓ Deleted")


def _mine(principal: Principal) -> None:
    print("\n  Homework you set or teach:")
    _print([t for t in HW.my_homework(principal) if t.status != "Closed"])
    marking = HW.to_mark(principal)
    print("\n  Waiting to be marked:")
    if not marking:
        print("  (nothing)")
    for t, n in marking:
        print(f"  #{t.task_id:<5} {t.due_date}  {t.for_label:<9} {t.title[:34]:<34} {n} to mark")
    _pause()


def _tick(principal: Principal) -> None:
    t = _choose()
    if not t:
        return
    rows = HW.list_work(t.task_id)
    for i, w in enumerate(rows, 1):
        print(f"   {i:>2}) {w.pupil_name:<26} {w.status}")
    picks = _prompt("  Numbers (e.g. 1 3 5-9): ")
    chosen: list[int] = []
    for part in picks.replace(",", " ").split():
        lo, _, hi = part.partition("-")
        if lo.isdigit() and (not hi or hi.isdigit()):
            chosen += [rows[i - 1].pupil_id for i in range(int(lo), int(hi or lo) + 1)
                       if 0 < i <= len(rows)]
    if not chosen:
        return
    status = _prompt("  Status for them (Submitted/Missing/Pending/Excused): ").title()
    reason = _prompt("  Why are they excused? ") if status == "Excused" else None
    n, problems = HW.record_many(t.task_id, chosen, status, actor=principal,
                                 excuse_reason=reason)
    print(f"  ✓ {n} updated")
    for p in problems:
        print(f"   • {p}")


def _missing() -> None:
    start = _prompt("  From (YYYY-MM-DD, Enter = start of the year): ")
    end = _prompt("  To (Enter = today): ")
    year = _prompt("  Year (Enter = all): ")
    rows = HW.missing_report(start=start or None, end=end or None,
                             year_group=int(year) if year.isdigit() else None)
    if not rows:
        print("  Nobody has missing or late homework.")
    for r in rows:
        print(f"  {r['name'][:24]:<24} {r['admission_no']:<10} {(r['form_group'] or ''):<5} "
              f"missing {r['missing']:<3} late {r['late']:<3} "
              f"{'; '.join(r['titles'])[:60]}")
    _pause()


def _week() -> None:
    today = _dt.date.today()
    monday = today - _dt.timedelta(days=today.weekday())
    year = _prompt("  Year (Enter = all): ")
    cal = HW.due_calendar(monday, monday + _dt.timedelta(days=6),
                          year_group=int(year) if year.isdigit() else None)
    if not cal:
        print("  No homework due this week.")
    for day, tasks in cal.items():
        print(f"\n  {_dt.date.fromisoformat(day):%A %d %b} - {len(tasks)} due")
        for t in tasks:
            print(f"    Y{t.year_group:<3} {t.for_label:<9} {t.subject_code:<6} {t.title[:40]}"
                  + (f" ({t.est_minutes} min)" if t.est_minutes else ""))
    _pause()


def _copy(principal: Principal) -> None:
    t = _choose()
    if not t:
        return
    code = _prompt(f"  To group code (Enter = {t.for_label}): ")
    g = TG.find(code) if code else None
    if code and g is None:
        print("  No such group this year.")
        return
    new, warnings = HW.copy(t.task_id, actor=principal, group_id=g.group_id if g else None,
                            set_date=_prompt("  Set date (Enter = today): ") or None,
                            due_date=_prompt("  Due date (YYYY-MM-DD): "))
    print(f"  ✓ Copied as #{new.task_id} for {new.for_label} (Draft)")
    _warn(warnings)


def _email(principal: Principal) -> None:
    t = _choose()
    if not t:
        return
    missing = [w for w in HW.list_work(t.task_id) if w.status == "Missing"]
    if not missing:
        print("  Nobody's homework is marked Missing.")
        return
    print(f"  {len(missing)} missing: " + ", ".join(w.pupil_name for w in missing))
    print("\n  " + HW.email_body(t).replace("\n", "\n  "))
    if not _yes("\n  Send this to their parents/carers?"):
        return
    result = HW.notify_parents(t.task_id, actor=principal)
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    report = E.deliver(result.message_id, principal=principal)
    print(f"  ✓ E-mail to {result.recipients} contact(s) ({report.mode}): "
          + ", ".join(f"{k} {v}" for k, v in report.counts.items() if v))
    if result.pupils_without_email:
        print("  No e-mail address for: "
              + ", ".join(p.display_name for p in result.pupils_without_email))


def _export(principal: Principal) -> None:
    t = _choose()
    if not t:
        return
    path = _prompt(f"  Save to [homework-{t.task_id}-marks.csv]: ") or \
        f"homework-{t.task_id}-marks.csv"
    try:
        n = HW.export_marks(t.task_id, path, actor=principal)
    except OSError as e:
        print(f"  Couldn't save: {e}")
        return
    print(f"  ✓ Saved {n} pupil(s) to {path}")


def _limit(principal: Principal, editor: bool) -> None:
    print(f"  Daily homework limit: {HW.daily_limit()} piece(s) due per pupil per day")
    if editor and _yes("  Change it?"):
        print(f"  ✓ Now {HW.set_daily_limit(_prompt('  New limit: '), actor=principal)}.")
