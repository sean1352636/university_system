"""Subjects in the terminal (old New / List / View / Edit / Toggle active /
Delete kept). Rules live in :mod:`modules.curriculum.domain.subjects`. When editing, Enter keeps
a value and ``-`` clears it."""

from __future__ import annotations

from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import SUBJECT_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_HINTS = {
    "code": "2-8 capitals or digits", "key_stage": "/".join(S.KEY_STAGES),
    "qualification": "/".join(S.QUALIFICATIONS), "exam_board": ", ".join(S.EXAM_BOARDS),
    "ebacc_category": ", ".join(S.EBACC_CATEGORIES), "is_core": "y/n",
}


def _problem(e: Exception) -> None:
    prompts.problem(e, "Please fix:")


def _lessons_text(s: S.Subject, by_year: dict[int, int]) -> str:
    return " ".join(str(by_year.get(y, 0)) if y in s.years else "-" for y in P.YEAR_GROUPS)


def _table(rows: list[S.Subject]) -> None:
    if not rows:
        print("  (no subjects)")
        return
    plan = S.plan(active_only=False)
    print(f"  {'Code':<8} {'Name':<28} {'KS':<5} {'Qual':<6} {'Department':<16} {'Core':<5} "
          f"{'Active':<7} Lessons Y7-11")
    for s in rows:
        print(f"  {s.code:<8} {s.name[:28]:<28} {s.key_stage:<5} {s.qualification:<6} "
              f"{(s.department or '')[:16]:<16} {'yes' if s.is_core else '':<5} "
              f"{'yes' if s.is_active else 'no':<7} {_lessons_text(s, plan.get(s.subject_id, {}))}")


def _choose() -> S.Subject | None:
    raw = _prompt("  Subject code: ")
    if not raw:
        return None
    s = S.get_by_code(raw)
    if s is None:
        print("  No subject with that code.")
    return s


def menu(principal: Principal) -> None:
    editor = principal.role in SUBJECT_EDITORS
    while True:
        activity_log.record("subject.list")
        c = S.counts()
        print("\n── Subjects (KS3 / GCSE) ──")
        print(f"  Total: {c['total']}   Active: {c['active']}   Inactive: {c['inactive']}   "
              f"Core: {c['core']}")
        print("\n   1) New subject\n   2) List subjects\n   3) View subject\n   4) Edit subject"
              "\n   5) Toggle active\n   6) Delete subject\n   7) Curriculum plan"
              "\n   8) Add standard subjects\n   0) Back")
        choice = _prompt("Select: ")
        if choice in {"0", ""}:
            return
        if choice in {"1", "4", "5", "6", "8"} and not editor:
            print("  Your account can view subjects but not change them.")
            continue
        try:
            {"1": lambda: _new(principal), "2": _list, "3": _view,
             "4": lambda: _edit(principal), "5": lambda: _toggle(principal),
             "6": lambda: _delete(principal), "7": lambda: _plan(principal, editor),
             "8": lambda: _standard(principal),
             }.get(choice, lambda: print("  Invalid selection."))()
        except (S.ValidationError, S.PermissionDenied) as e:
            _problem(e)


def _collect(s: S.Subject | None) -> dict:
    out = {}
    for k in S.EDITABLE_FIELDS:
        v = getattr(s, k) if s else None
        cur = ("y" if v else "n") if k == "is_core" and s else (None if v is None else str(v))
        ans = _ask(S.FIELD_LABELS[k], cur, required=k in {"code", "name"} and s is None,
                   hint=_HINTS.get(k, ""))
        if ans is not None:
            out[k] = ans
    return out


def _ask_lessons(principal: Principal, s: S.Subject) -> None:
    now = S.lessons(s.subject_id)
    plan = {}
    for y in s.years:
        ans = _ask(f"Lessons per week, Year {y}", str(now[y]) if y in now else None,
                   hint=f"0-{S.MAX_LESSONS}")
        if ans is not None:
            plan[y] = ans
    if plan:
        _now, warnings = S.set_lessons(s.subject_id, plan, actor=principal)
        for w in warnings:
            print(f"  ⚠ {w}")


def _new(principal: Principal) -> None:
    print("\n  ── New subject ──")
    s = S.create(_collect(None), actor=principal)
    print(f"  ✓ Added {s.label}")
    _ask_lessons(principal, s)


def _list() -> None:
    ks = _prompt(f"  Key stage ({'/'.join(S.KEY_STAGES)}, Enter for all): ").strip()
    inactive = _yes("  Include inactive?")
    rows = S.list_subjects(key_stage=next((k for k in S.KEY_STAGES if k.lower() == ks.lower()),
                                          None), active_only=not inactive)
    _table(rows)
    _pause()


def _view() -> None:
    s = _choose()
    if not s:
        return
    activity_log.record("subject.view", target=s.code)
    print(f"\n── {s.label} ──")
    for k in S.EDITABLE_FIELDS:
        v = getattr(s, k)
        print(f"  {S.FIELD_LABELS[k]}: {('yes' if v else 'no') if k == 'is_core' else v or '—'}")
    print(f"  Active: {'yes' if s.is_active else 'no'}")
    print("  Lessons per week: " + (", ".join(
        f"Y{y} {n}" for y, n in sorted(S.lessons(s.subject_id).items())) or "none planned"))
    for what, n in S.usage(s.subject_id):
        print(f"  Used by {n} {what}")
    for h in S.history(s.subject_id)[:10]:
        print(f"  {h['at']}  {h['actor']}  {h['action']}")
    _pause()


def _edit(principal: Principal) -> None:
    s = _choose()
    if not s:
        return
    print("  Enter keeps a value, '-' clears it.")
    s2, changed = S.update(s.subject_id, _collect(s), actor=principal)
    print(f"  ✓ Saved ({', '.join(changed)})." if changed else "  Nothing changed.")
    _ask_lessons(principal, s2)


def _toggle(principal: Principal) -> None:
    s = _choose()
    if s and _yes(f"  Make {s.label} {'inactive' if s.is_active else 'active'}?"):
        s = S.toggle_active(s.subject_id, actor=principal)
        print(f"  ✓ {s.code} is now {'active' if s.is_active else 'inactive'}.")


def _delete(principal: Principal) -> None:
    s = _choose()
    if s and _yes(f"  Delete {s.label}? (for a subject added by mistake)"):
        S.delete(s.subject_id, actor=principal)
        print("  ✓ Deleted.")


def _plan(principal: Principal, editor: bool) -> None:
    while True:
        subjects, plan, totals = S.list_subjects(), S.plan(), S.year_totals()
        week = S.periods_per_week()
        print(f"\n── Curriculum plan (lessons per week; timetable week {week}) ──")
        print(f"  {'Subject':<36}" + "".join(f"{'Y' + str(y):>5}" for y in P.YEAR_GROUPS))
        for s in subjects:
            row = plan.get(s.subject_id, {})
            print(f"  {(s.label + (' *' if s.is_core else ''))[:36]:<36}" + "".join(
                f"{(row.get(y, 0) if y in s.years else '-'):>5}" for y in P.YEAR_GROUPS))
        print(f"  {'Total':<36}" + "".join(f"{totals[y]:>5}" for y in P.YEAR_GROUPS))
        for w in S.plan_warnings():
            print(f"  ⚠ {w}")
        if not editor:
            _pause()
            return
        c = _prompt("\n  L) Set a subject's lessons   W) Timetable week   0) Back: ").lower()
        if c in {"0", ""}:
            return
        try:
            if c == "l":
                s = _choose()
                if s:
                    _ask_lessons(principal, s)
            elif c == "w":
                raw = _prompt(f"  Lessons in the timetable week [{week}]: ")
                if raw:
                    S.set_periods_per_week(raw, actor=principal)
        except (S.ValidationError, S.PermissionDenied) as e:
            _problem(e)


def _standard(principal: Principal) -> None:
    missing = S.missing_standard()
    if not missing:
        print("  Every standard subject is already in the list.")
        return
    for d in missing:
        print(f"  {d['code']:<8} {d['name']}")
    raw = _prompt("  Codes to add (space separated), 'all', or Enter to cancel: ").upper()
    if not raw:
        return
    codes = None if raw == "ALL" else raw.replace(",", " ").split()
    made = S.add_standard(codes, actor=principal)
    print(f"  ✓ {len(made)} added. Set their lessons with Curriculum plan.")
