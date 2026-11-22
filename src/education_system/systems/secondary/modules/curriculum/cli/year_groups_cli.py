"""Year Groups in the terminal. Rules live in :mod:`modules.curriculum.domain.year_groups`.
When editing, Enter keeps a value and ``-`` clears it."""

from __future__ import annotations

from education_system.systems.secondary.modules.curriculum.domain import year_groups as YG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import YEAR_GROUP_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes


def _problem(e: Exception) -> None:
    prompts.problem(e, "Please fix:")


def _describe(h: dict) -> str:
    d = h["detail"]
    if h["action"] == "update":
        return "changed " + ", ".join(YG.FIELD_LABELS.get(k, k).lower() for k in d)
    if h["action"] == "clear":
        return "cleared settings"
    return f"moved in {d.get('moved_in', 0)} pupil(s)"


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("year_group.list")
        rows = YG.overview()
        print("\n── Year Groups ──")
        print(f"  {'Year':<8} {'KS':<4} {'Head of year':<24} {'Roll':>5} {'Capacity':<16} "
              f"{'Forms':>5} {'Out of yr':>9}")
        for g, pr in rows:
            cap = "—" if pr.capacity is None else (
                f"{pr.capacity} ({-pr.spaces} over)" if pr.over_capacity  # type: ignore[operator]
                else f"{pr.capacity} ({pr.spaces} free)")
            print(f"  {g.label:<8} {g.key_stage:<4} {(g.head_of_year or '—')[:24]:<24} "
                  f"{pr.on_roll:>5} {cap:<16} {len(pr.forms):>5} {len(pr.out_of_year):>9}")
        raw = _prompt("\n  Year to open (7-11, Enter to go back): ")
        if not raw:
            return
        if raw.isdigit() and int(raw) in P.YEAR_GROUPS:
            show(principal, int(raw))


def show(principal: Principal, year: int) -> None:
    editor = principal.role in YEAR_GROUP_EDITORS
    while True:
        g, pr = YG.get(year), YG.profile(year)
        activity_log.record("year_group.view", target=f"Y{year}")
        print(f"\n── {g.label} ({g.key_stage}) ──")
        for k in YG.EDITABLE_FIELDS:
            v = getattr(g, k)
            print(f"  {YG.FIELD_LABELS[k]}: {'—' if v in (None, '') else v}")
        other = pr.on_roll - pr.by_gender.get('Female', 0) - pr.by_gender.get('Male', 0)
        print(f"  On roll: {pr.on_roll} ({pr.by_gender.get('Female', 0)} F, "
              f"{pr.by_gender.get('Male', 0)} M" + (f", {other} other" if other else "") + ")" + (f" - {-pr.spaces} over capacity"
                                                     if pr.over_capacity else ""))
        print(f"  This year: {pr.joined_this_year} joined, {pr.left_this_year} left")
        print("  Forms: " + (", ".join(f"{f} ({n})" for f, n in pr.forms.items()) or "none")
              + (f"; no form: {pr.no_form}" if pr.no_form else ""))
        print(f"  SEN support {pr.sen_support} · EHC plan {pr.ehcp} · FSM {pr.fsm} · "
              f"EAL {pr.eal}")
        for p, exp in pr.out_of_year:
            print(f"  ! {p.display_name} ({p.admission_no}) - age fits Year {exp}")
        opts = "  P) Pupils"
        if editor:
            opts += "   E) Edit   C) Clear   M) Move pupils to another year"
        print("\n" + opts + "   H) History   0) Back")
        choice = _prompt("Select: ").lower()
        if choice in {"0", "", "q"}:
            return
        try:
            if choice == "p":
                for p in P.list_pupils(year_group=year):
                    print(f"  {p.admission_no:<10} {p.display_name[:26]:<26} "
                          f"{p.form_group or '':<6} {p.gender}")
                _pause()
            elif choice == "h":
                for h in YG.history(year)[:30]:
                    print(f"  {h['at']}  {h['actor']}  {_describe(h)}")
                _pause()
            elif choice == "e" and editor:
                changes = {}
                for k in YG.EDITABLE_FIELDS:
                    v = _ask(YG.FIELD_LABELS[k], None if getattr(g, k) is None
                             else str(getattr(g, k)))
                    if v is not None:
                        changes[k] = v
                _g, changed = YG.update(year, changes, actor=principal)
                print("  ✓ Saved." if changed else "  Nothing changed.")
            elif choice == "c" and editor:
                if _yes(f"  Clear {g.label}'s settings? (pupils aren't affected)"):
                    YG.clear(year, actor=principal)
                    print("  ✓ Cleared.")
            elif choice == "m" and editor:
                move(principal, year)
        except (YG.ValidationError, YG.PermissionDenied) as e:
            _problem(e)


def move(principal: Principal, year: int) -> None:
    refs = _prompt("  Admission numbers to move (comma or space separated): ")
    from education_system.systems.secondary.modules.pupils.domain import bulk_import as B
    pupils, missing = B.resolve_refs(refs)
    for ref in missing:
        print(f"  Not found: {ref}")
    pupils = [p for p in pupils if p.year_group == year]
    if not pupils:
        print(f"  None of those are in Year {year}.")
        return
    to = _prompt("  Move to year group: ")
    if not (to.isdigit() and int(to) in P.YEAR_GROUPS):
        return
    new = int(to)
    for p in pupils:
        notes = []
        if YG.form_after_move(p.form_group, year, new) is None and p.form_group:
            notes.append(f"form {p.form_group} cleared")
        if P.expected_year_group(p.date_of_birth) != new:
            notes.append("outside age-expected year")
        print(f"  {p.admission_no:<10} {p.display_name[:26]:<26} " + "; ".join(notes))
    if not _yes(f"  Move {len(pupils)} to Year {new}?"):
        return
    moved, refused = YG.move_pupils([p.pupil_id for p in pupils], new, actor=principal)
    print(f"  ✓ {len(moved)} moved.")
    for adm, why in refused:
        print(f"  ✗ {adm}: {why}")
    _pause()
