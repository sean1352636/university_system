"""Form Groups in the terminal (old New / List by year / Edit / Delete kept).
Rules live in :mod:`modules.curriculum.domain.form_groups`. When editing, Enter keeps a value
and ``-`` clears it."""

from __future__ import annotations

from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import FORM_GROUP_EDITORS, Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes


def _problem(e: Exception) -> None:
    prompts.problem(e, "Please fix:")


def _cap(s: FG.FormStats) -> str:
    if s.capacity is None:
        return "—"
    return (f"{s.capacity} ({-s.spaces} over)" if s.over_capacity  # type: ignore[operator]
            else f"{s.capacity} ({s.spaces} free)")


def _table(forms: list[FG.FormGroup]) -> None:
    if not forms:
        print("  (no form groups)")
        return
    st = FG.stats()
    print(f"  {'ID':<5} {'Year':<5} {'Form':<10} {'Tutor':<22} {'Room':<8} {'Pupils':>6} "
          f"{'Capacity':<14} Status")
    for f in forms:
        s = st.get(f.form_id, FG.FormStats(capacity=f.capacity))
        print(f"  {f.form_id:<5} {f.year_group:<5} {f.name:<10} {(f.tutor_name or '—')[:22]:<22} "
              f"{(f.room or '')[:8]:<8} {s.on_roll if f.is_active else '':>6} "
              f"{_cap(s) if f.is_active else '':<14} {'Open' if f.is_active else 'Archived'}")


def _choose(include_archived: bool = False) -> FG.FormGroup | None:
    raw = _prompt("  Form ID (or year and name, e.g. 7 7K): ")
    if not raw:
        return None
    parts = raw.split(maxsplit=1)
    try:
        if len(parts) == 2 and parts[0].isdigit():
            f = FG.find(int(parts[0]), parts[1])
        else:
            f = FG.get(int(raw))
    except (ValueError, FG.NotFound):
        f = None
    if f is None or (not include_archived and not f.is_active):
        print("  No such form.")
        return None
    return f


def menu(principal: Principal) -> None:
    editor = principal.role in FORM_GROUP_EDITORS
    while True:
        activity_log.record("form_group.list")
        forms = FG.list_forms()
        print("\n── Form Groups ──")
        print(f"  {len(forms)} open form group(s).")
        missing, loose = FG.not_set_up(), len(FG.without_form())
        if missing:
            print("  ! Not set up: " + ", ".join(f"{n} (Y{y})" for y, n, _c in missing[:10]))
        if loose:
            print(f"  ! {loose} pupil(s) on roll have no form")
        print("\n   1) New form group\n   2) List by year\n   3) Edit form group"
              "\n   4) Delete form group\n   5) Open a form (pupils)\n   6) Archive / restore"
              "\n   7) Set up forms named on pupil records\n   8) Place pupils with no form"
              "\n   0) Back")
        choice = _prompt("Select: ")
        if choice in {"0", ""}:
            return
        if choice in {"1", "3", "4", "6", "7", "8"} and not editor:
            print("  Your account can view form groups but not change them.")
            continue
        try:
            {"1": lambda: _new(principal), "2": _list_by_year,
             "3": lambda: _edit(principal), "4": lambda: _delete(principal),
             "5": lambda: _open(principal), "6": lambda: _archive(principal),
             "7": lambda: _set_up(principal), "8": lambda: _place(principal),
             }.get(choice, lambda: print("  Invalid selection."))()
        except (FG.ValidationError, FG.PermissionDenied) as e:
            _problem(e)


def _collect(f: FG.FormGroup | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for k in FG.EDITABLE_FIELDS:
        if k == "year_group" and f is not None and FG.members(f):
            continue  # can't change year while pupils are in it
        cur = None if f is None or getattr(f, k) is None else str(getattr(f, k))
        v = _ask(FG.FIELD_LABELS[k], cur, required=k in {"name", "year_group"} and f is None)
        if v is not None:
            out[k] = v
    return out


def _new(principal: Principal) -> None:
    print("\n  ── New Form Group ──")
    f = FG.create(_collect(None), actor=principal)
    print(f"  ✓ Created form #{f.form_id} {f.label}")


def _list_by_year() -> None:
    raw = _prompt("  Year (7-11, Enter for all; add 'a' for archived, e.g. '8a'): ").lower()
    arch = raw.endswith("a")
    raw = raw.rstrip("a").strip()
    year = int(raw) if raw.isdigit() and int(raw) in P.YEAR_GROUPS else None
    _table(FG.list_forms(year, include_archived=arch))
    _pause()


def _edit(principal: Principal) -> None:
    f = _choose()
    if not f:
        return
    print("  Enter keeps a value, '-' clears it.")
    g, changed, renamed = FG.update(f.form_id, _collect(f), actor=principal)
    print(f"  ✓ Updated {g.label}" if changed else "  Nothing changed.")
    if renamed:
        print(f"  Renamed on {renamed} pupil record(s).")


def _delete(principal: Principal) -> None:
    f = _choose(include_archived=True)
    if f and _yes(f"  Delete {f.label}? (for a form set up by mistake - archive a used one)"):
        FG.delete(f.form_id, actor=principal)
        print("  ✓ Deleted.")


def _archive(principal: Principal) -> None:
    f = _choose(include_archived=True)
    if not f:
        return
    if f.is_active:
        if _yes(f"  Archive {f.label}?"):
            FG.archive(f.form_id, actor=principal)
            print("  ✓ Archived.")
    elif _yes(f"  Restore {f.label}?"):
        FG.restore(f.form_id, actor=principal)
        print("  ✓ Restored.")


def _set_up(principal: Principal) -> None:
    missing = FG.not_set_up()
    if not missing:
        print("  Every form on pupil records is set up.")
        return
    for y, n, c in missing:
        print(f"  Year {y} {n}: {c} pupil(s)")
    if _yes(f"  Set up these {len(missing)} form(s)?"):
        made = FG.set_up_missing(actor=principal)
        print(f"  ✓ {len(made)} set up. Add their tutors with Edit.")


def _place(principal: Principal) -> None:
    raw = _prompt("  Year (7-11): ")
    if not (raw.isdigit() and int(raw) in P.YEAR_GROUPS):
        return
    plan, unplaced = FG.plan_distribution(int(raw))
    if not plan and not unplaced:
        print(f"  Every Year {raw} pupil has a form.")
        return
    for p, f in plan:
        print(f"  {p.admission_no:<10} {p.display_name[:26]:<26} {p.gender:<8} → {f.name}")
    for p in unplaced:
        print(f"  {p.admission_no:<10} {p.display_name[:26]:<26} {p.gender:<8} → no room")
    if plan and _yes(f"  Place {len(plan)} pupil(s) as shown?"):
        done, refused = FG.apply_distribution(plan, actor=principal)
        print(f"  ✓ {done} placed.")
        for adm, why in refused:
            print(f"  ✗ {adm}: {why}")
    _pause()


def _open(principal: Principal) -> None:
    f = _choose(include_archived=True)
    if not f:
        return
    editor = principal.role in FORM_GROUP_EDITORS and f.is_active
    while True:
        f = FG.get(f.form_id)
        activity_log.record("form_group.view", target=f"FG{f.form_id}")
        pupils = FG.members(f) if f.is_active else []
        s = FG.stats(f.year_group).get(f.form_id, FG.FormStats(capacity=f.capacity))
        print(f"\n── Form {f.label}{'' if f.is_active else ' - archived'} ──")
        for k in ("tutor_name", "tutor_email", "co_tutor_name", "room", "notes"):
            print(f"  {FG.FIELD_LABELS[k]}: {getattr(f, k) or '—'}")
        print(f"  Pupils: {s.on_roll} ({s.female} F, {s.male} M) · capacity {_cap(s)} · "
              f"SEN {s.sen} · FSM {s.fsm} · EAL {s.eal}")
        for p in pupils:
            print(f"    {p.admission_no:<10} {p.display_name[:26]:<26} {p.gender}")
        print("\n  " + ("A) Add pupils   M) Move pupils to another form   R) Remove pupils   "
                        if editor else "") + "H) History   0) Back")
        c = _prompt("Select: ").lower()
        if c in {"0", ""}:
            return
        try:
            if c == "h":
                for h in FG.history(f.form_id)[:30]:
                    print(f"  {h['at']}  {h['actor']}  {h['action']}")
                _pause()
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
                    print(f"  ✓ {FG.remove(ids, f.form_id, actor=principal)} removed.")
                    continue
                target = f if c == "a" else _choose()
                if not target:
                    continue
                try:
                    done, refused = FG.assign(ids, target.form_id, actor=principal)
                except FG.ValidationError as e:
                    _problem(e)
                    if not (target.capacity is not None and _yes("  Go over capacity?")):
                        continue
                    done, refused = FG.assign(ids, target.form_id, actor=principal,
                                              allow_over_capacity=True)
                print(f"  ✓ {len(done)} put in {target.name}.")
                for adm, why in refused:
                    print(f"  ✗ {adm}: {why}")
        except (FG.ValidationError, FG.PermissionDenied) as e:
            _problem(e)
