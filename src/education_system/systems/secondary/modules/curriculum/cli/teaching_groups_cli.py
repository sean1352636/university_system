"""Teaching Groups in the terminal. Rules live in :mod:`modules.curriculum.domain.teaching_groups`.
When editing, Enter keeps a value and ``-`` clears it."""

from __future__ import annotations

from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import TEACHING_GROUP_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes


def _problem(e: Exception) -> None:
    prompts.problem(e, "Please fix:")


def _table(rows: list[TG.GroupInfo]) -> None:
    if not rows:
        print("  (no teaching groups)")
        return
    print(f"  {'Group':<14} {'Subject':<8} {'Yr':<3} {'Kind':<8} {'Teacher':<22} {'Room':<7} "
          f"{'Pupils':<8} Lessons")
    for i in rows:
        g = i.group
        size = f"{i.pupils}" + (f"/{g.capacity}" if g.capacity else "")
        print(f"  {g.code[:14]:<14} {i.subject.code:<8} {g.year_group:<3} {g.kind_label:<8} "
              f"{(g.teacher_name or '—')[:22]:<22} {(g.room or '')[:7]:<7} "
              f"{size if g.is_active else 'archived':<8} {i.lessons or ''}")


def _choose(year: str | None = None) -> TG.TeachingGroup | None:
    code = _prompt("  Group code: ")
    if not code:
        return None
    g = TG.find(code, year)
    if g is None:
        print("  No group with that code" + (f" in {year}." if year else " this year."))
    return g


def _subject() -> S.Subject | None:
    code = _prompt("  Subject code: ")
    s = S.get_by_code(code) if code else None
    if code and s is None:
        print("  No subject with that code.")
    return s


def menu(principal: Principal) -> None:
    editor = principal.role in TEACHING_GROUP_EDITORS
    while True:
        activity_log.record("teaching_group.list")
        groups = TG.list_groups()
        print(f"\n── Teaching Groups ({TG.current_year()}) ──")
        print(f"  {len(groups)} group(s) this year.")
        gaps = TG.coverage()
        if gaps:
            print("  ! No group yet (core): " + "; ".join(
                f"{s.code} Y{y} ({len(ps)})" for s, y, ps in gaps[:8]))
        print("\n   1) List groups\n   2) My groups\n   3) Open a group\n   4) New group"
              "\n   5) Edit group\n   6) Delete group\n   7) Archive / restore"
              "\n   8) Create groups from forms\n   9) Past years\n   0) Back")
        c = _prompt("Select: ")
        if c in {"0", ""}:
            return
        if c in {"4", "5", "6", "7", "8"} and not editor:
            print("  Your account can view teaching groups but not change them.")
            continue
        try:
            {"1": _list, "2": lambda: _mine(principal), "3": lambda: _open(principal),
             "4": lambda: _new(principal), "5": lambda: _edit(principal),
             "6": lambda: _delete(principal), "7": lambda: _archive(principal),
             "8": lambda: _from_forms(principal), "9": lambda: _past(principal),
             }.get(c, lambda: print("  Invalid selection."))()
        except (TG.ValidationError, TG.PermissionDenied) as e:
            _problem(e)


def _list() -> None:
    raw = _prompt("  Year (7-11) and/or subject code, e.g. '8 MATH' (Enter for all): ").split()
    year = next((int(x) for x in raw if x.isdigit() and int(x) in P.YEAR_GROUPS), None)
    code = next((x for x in raw if not x.isdigit()), None)
    subj = S.get_by_code(code) if code else None
    _table(TG.info(TG.list_groups(year_group=year,
                                  subject_id=subj.subject_id if subj else None)))
    _pause()


def _mine(principal: Principal) -> None:
    _table(TG.info(TG.list_groups(teacher=principal.username)))
    _pause()


def _past(principal: Principal) -> None:
    years = [y for y in TG.academic_years() if y != TG.current_year()]
    if not years:
        print("  No groups from past years.")
        return
    y = _prompt(f"  Academic year ({', '.join(years)}): ")
    if y in years:
        _table(TG.info(TG.list_groups(academic_year=y, include_archived=True)))
        g = _choose(y) if _yes("  Open one?") else None
        if g:
            _show(principal, g.group_id)


def _collect(g: TG.TeachingGroup | None) -> dict:
    out: dict = {}
    has_pupils = bool(g and TG.members(g.group_id, include_left=True))
    v = _ask("Group code", g.code if g else None, required=g is None, hint="e.g. 8x/Ma1")
    if v is not None:
        out["code"] = v
    if not has_pupils:
        s = None
        while s is None:
            cur = S.get(g.subject_id).code if g else None
            code = _ask("Subject code", cur, required=g is None)
            if code is None and g:
                break
            s = S.get_by_code(code or "")
            if s is None:
                print("  No subject with that code.")
        if s:
            out["subject_id"] = s.subject_id
        v = _ask("Year group", str(g.year_group) if g else None, required=g is None,
                 hint="7-11")
        if v is not None:
            out["year_group"] = v
    for k, hint in (("kind", "/".join(TG.KINDS)), ("set_number", "for a set")):
        v = _ask(TG.FIELD_LABELS[k], None if g is None or getattr(g, k) is None
                 else str(getattr(g, k)), hint=hint)
        if v is not None:
            out[k] = v
    teachers = TG.teacher_choices()
    if teachers:
        print("  Staff logins: " + ", ".join(f"{t['username']} ({t['display_name']})"
                                             for t in teachers[:15]))
    for k in ("teacher_username", "teacher_name", "teacher_email", "second_teacher", "room",
              "capacity", "lessons_per_week", "notes"):
        cur = getattr(g, k) if g else None
        v = _ask(TG.FIELD_LABELS[k], None if cur is None else str(cur),
                 hint="fills name and e-mail" if k == "teacher_username" else "")
        if v is not None:
            out[k] = v
    return out


def _new(principal: Principal) -> None:
    print(f"\n  ── New teaching group ({TG.current_year()}) ──")
    g = TG.create(_collect(None), actor=principal)
    print(f"  ✓ Added {g.code}")


def _edit(principal: Principal) -> None:
    g = _choose()
    if g:
        print("  Enter keeps a value, '-' clears it.")
        g2, changed = TG.update(g.group_id, _collect(g), actor=principal)
        print(f"  ✓ Saved ({', '.join(changed)})." if changed else "  Nothing changed.")


def _delete(principal: Principal) -> None:
    g = _choose()
    if g and _yes(f"  Delete {g.code}? (for a group set up by mistake)"):
        TG.delete(g.group_id, actor=principal)
        print("  ✓ Deleted.")


def _archive(principal: Principal) -> None:
    g = _choose()
    if not g:
        return
    if g.is_active:
        n = len(TG.members(g.group_id))
        if _yes(f"  Archive {g.code}?" + (f" Its {n} pupil(s) come out of it." if n else "")):
            TG.archive(g.group_id, actor=principal)
            print("  ✓ Archived.")
    elif _yes(f"  Restore {g.code}?"):
        TG.restore(g.group_id, actor=principal)
        print("  ✓ Restored.")


def _from_forms(principal: Principal) -> None:
    s = _subject()
    if not s:
        return
    y = _prompt(f"  Year group ({', '.join(map(str, s.years))}): ")
    if not (y.isdigit() and int(y) in s.years):
        return
    forms = FG.names_for_year(int(y))
    if not forms:
        print(f"  Year {y} has no forms set up.")
        return
    print("  Will make: " + ", ".join(f"{f}/{s.code}" for f in forms))
    if _yes("  Go ahead?"):
        made, notes = TG.create_from_forms(s.subject_id, int(y), actor=principal)
        print(f"  ✓ {len(made)} group(s) made.")
        for n in notes:
            print(f"  · {n}")


def _open(principal: Principal) -> None:
    g = _choose()
    if g:
        _show(principal, g.group_id)


def _add(principal: Principal, g: TG.TeachingGroup, ids: list[int], move: bool) -> None:
    try:
        done, refused = TG.add_pupils(ids, g.group_id, actor=principal, move=move)
    except TG.ValidationError as e:
        _problem(e)
        if not (g.capacity and _yes("  Go over capacity?")):
            return
        done, refused = TG.add_pupils(ids, g.group_id, actor=principal, move=move,
                                      allow_over_capacity=True)
    print(f"  ✓ {len(done)} added to {g.code}.")
    for adm, why in refused:
        print(f"  ✗ {adm}: {why}")


def _show(principal: Principal, group_id: int) -> None:
    while True:
        g = TG.get(group_id)
        editor = principal.role in TEACHING_GROUP_EDITORS and g.is_active and g.is_current
        i = TG.info([g])[0]
        activity_log.record("teaching_group.view", target=f"TG{group_id}")
        print(f"\n── {g.code} · {i.subject.name} · Year {g.year_group} · {g.kind_label} · "
              f"{g.academic_year}{'' if g.is_active else ' · archived'} ──")
        print(f"  Teacher: {g.teacher_name or '—'}" + (f" ({g.teacher_email})"
                                                       if g.teacher_email else "")
              + (f" · second teacher {g.second_teacher}" if g.second_teacher else ""))
        print(f"  Room: {g.room or '—'} · Pupils: {i.pupils}"
              + (f"/{g.capacity}" if g.capacity else "") + f" · Lessons/week: {i.lessons or '—'}")
        for p in TG.members(group_id):
            flag = f"  (now Year {p.year_group})" if p.year_group != g.year_group else ""
            print(f"    {p.admission_no:<10} {p.display_name[:26]:<26} {p.form_group or '':<6}"
                  f"{flag}")
        print("\n  " + ("A) Add pupils   F) Add a form   M) Move pupils to another group   "
                        "R) Remove pupils   " if editor else "") + "H) History   0) Back")
        c = _prompt("Select: ").lower()
        if c in {"0", ""}:
            return
        try:
            if c == "h":
                for h in TG.history(group_id)[:30]:
                    print(f"  {h['at']}  {h['actor']}  {h['action']}")
                _pause()
            elif c == "f" and editor:
                forms = {f.name: f for f in FG.list_forms(g.year_group)}
                name = _prompt(f"  Form ({', '.join(forms) or 'none set up'}): ").upper()
                if name in forms:
                    _add(principal, g, [p.pupil_id for p in FG.members(forms[name])],
                         _yes("  Move pupils already in another group for this subject?"))
            elif c in {"a", "m", "r"} and editor:
                from education_system.systems.secondary.modules.pupils.domain import (
                    bulk_import as B,
                )
                found, missing = B.resolve_refs(_prompt("  Admission numbers: "))
                for ref in missing:
                    print(f"  Not found: {ref}")
                ids = [p.pupil_id for p in found]
                if not ids:
                    continue
                if c == "r":
                    print(f"  ✓ {TG.remove_pupils(ids, group_id, actor=principal)} removed.")
                elif c == "a":
                    _add(principal, g, ids, _yes("  Move any already in another group for "
                                                 "this subject?"))
                else:
                    target = _choose()
                    if target:
                        _add(principal, target, ids, True)
        except (TG.ValidationError, TG.PermissionDenied) as e:
            _problem(e)
