"""Target grades in the terminal. The old options 1-5 are kept (set / update a
target, list targets, view a pupil + subject target, distribution, delete);
6-11 are added. Rules live in :mod:`modules.assessment.domain.target_grades`."""

from __future__ import annotations

from education_system.systems.secondary.modules.assessment.domain import target_grades as TGR
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (TGR.ValidationError, TGR.PermissionDenied, TGR.NotFound)


_problem = prompts.problem


def _print_table(rows: list[TGR.TargetGrade]) -> None:
    """The old table: ID, Pupil, Yr, Name, Subj, Tgt, Min, Asp, Source, Set on."""
    if not rows:
        print("  (no targets)")
        return
    print(f"  {'ID':<5} {'Pupil':<10} {'Yr':<3} {'Name':<22} {'Subj':<6} {'Tgt':<10} "
          f"{'Min':<10} {'Asp':<10} {'Source':<9} {'Set on':<10}")
    for t in rows:
        print(f"  {t.target_id:<5} {t.admission_no:<10} {t.pupil_year:<3} "
              f"{t.pupil_name[:22]:<22} {t.subject_code[:6]:<6} {t.target_grade:<10} "
              f"{(t.minimum_grade or '-'):<10} {(t.aspirational_grade or '-'):<10} "
              f"{t.source[:9]:<9} {t.set_date:<10}")


def _pupil() -> P.Pupil | None:
    ref = _prompt("  Pupil (admission number or UPN): ")
    if not ref:
        return None
    p = P.find_by_reference(ref)
    if p is None:
        print("  No pupil with that admission number.")
    return p


def _subject(required: bool = True) -> S.Subject | None:
    subjects = S.list_subjects()
    print("  Subjects: " + ", ".join(s.code for s in subjects))
    code = _prompt("  Subject code" + ("" if required else " (blank = all)") + ": ")
    if not code:
        return None
    s = S.get_by_code(code)
    if s is None:
        print("  No subject with that code.")
    return s


def _year() -> int | None:
    y = _prompt("  Year (7-11, blank = all): ")
    return int(y) if y.isdigit() else None


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("targets.view")
        print("\n── Target Grades ──")
        print(f"  Total: {len(TGR.list_targets())}")
        print("   1) Set / update target\n   2) List targets"
              "\n   3) View target for pupil + subject\n   4) Distribution (year + subject)"
              "\n   5) Delete target\n   6) Set targets for a class\n   7) Missing targets"
              "\n   8) Progress against target\n   9) A pupil's targets and history"
              "\n  10) Export targets (CSV)\n  11) Import targets (CSV)\n   0) Back")
        choice = _prompt("Select: ")
        if choice in {"0", ""}:
            return
        try:
            {"1": lambda: _upsert(principal), "2": _list, "3": _view, "4": _distribution,
             "5": lambda: _delete(principal), "6": lambda: _class(principal),
             "7": lambda: _missing(principal), "8": _progress, "9": _pupil_targets,
             "10": lambda: _export(principal), "11": lambda: _import(principal),
             }.get(choice, lambda: print("  Invalid selection."))()
        except _ERRORS as e:
            _problem(e)


def _upsert(principal: Principal) -> None:
    p = _pupil()
    s = p and _subject()
    if not p or not s:
        return
    cur = TGR.get_for(p.pupil_id, s.subject_id)
    names = TGR.scales_for(p.year_group, s)
    print(f"  {p.display_name}, Year {p.year_group}: grades "
          + " or ".join(f"{n} ({', '.join(TGR.SCALES[n])})" for n in names))
    if cur:
        print(f"  Existing target: {cur.target_grade} (set {cur.set_date} via {cur.source})")
    data = {"pupil_id": p.pupil_id, "subject_id": s.subject_id}
    for key, label, hint in (("target_grade", "Target grade", ""),
                             ("minimum_grade", "Minimum grade", "blank ok"),
                             ("aspirational_grade", "Aspirational grade", "blank ok"),
                             ("source", "Source", "/".join(TGR.GRADE_SOURCES)),
                             ("set_by", "Set by", ""),
                             ("set_date", "Set date", "YYYY-MM-DD, blank = today"),
                             ("notes", "Notes", "")):
        v = _ask(label, getattr(cur, key) if cur else None,
                 required=key == "target_grade" and cur is None, hint=hint)
        if v is not None:
            data[key] = v
    reason = None
    new = data.get("target_grade")
    if cur and new and TGR.is_editor(principal) and TGR._lowered(cur, str(new).strip()):
        reason = _prompt("  Reason for lowering the target: ")
    rec = TGR.upsert(data, actor=principal, reason=reason)
    print(f"  ✓ Saved target for {rec.pupil_name} / {rec.subject_code} = {rec.target_grade}")


def _list() -> None:
    yg = _year()
    s = _subject(required=False)
    pupil = _prompt("  Pupil (name or admission no, blank): ") or None
    src = _prompt(f"  Source ({'/'.join(TGR.GRADE_SOURCES)}, blank): ") or None
    rows = TGR.list_targets(year_group=yg, subject_id=s.subject_id if s else None,
                            pupil=pupil, source=src)
    print(f"\n  {len(rows)} target(s):")
    _print_table(rows)
    _pause()


def _view() -> None:
    p = _pupil()
    s = p and _subject()
    if not p or not s:
        return
    t = TGR.get_for(p.pupil_id, s.subject_id)
    if t is None:
        print("  No target set for that pupil + subject.")
        return
    print(f"\n  ── Target #{t.target_id} ──")
    print(f"  Pupil:        {t.admission_no}  {p.display_name}")
    print(f"  Subject:      {t.subject_code} - {t.subject_name}")
    print(f"  Target:       {t.target_grade}")
    print(f"  Minimum:      {t.minimum_grade or '-'}")
    print(f"  Aspirational: {t.aspirational_grade or '-'}")
    print(f"  Source:       {t.source}")
    print(f"  Set by:       {t.set_by or '-'}  on {t.set_date}")
    print(f"  Notes:        {t.notes or '-'}")
    now = TGR.progress(subject_id=t.subject_id, pupil_id=t.pupil_id)
    if now:
        r = now[0]
        print(f"  Now:          {r['current'] or '-'}"
              + (f" ({r['from']})" if r["from"] else "") + f" - {r['status']}")
    _pause()


def _distribution() -> None:
    yg = _year()
    s = _subject(required=False)
    dist = TGR.distribution(year_group=yg, subject_id=s.subject_id if s else None)
    print(f"\n  Distribution ({sum(dist.values())} target(s)):")
    top = max(dist.values(), default=0)
    for g, n in dist.items():
        print(f"    {g:<11} {n:<4} {'█' * round(n * 30 / top) if top else ''}")
    _pause()


def _delete(principal: Principal) -> None:
    raw = _prompt("  Target ID: ")
    if not raw.isdigit():
        if raw:
            print("  Target ID must be a number.")
        return
    t = TGR.get(int(raw))
    if not _yes(f"  Delete target #{t.target_id} ({t.admission_no} / {t.subject_code} "
                f"= {t.target_grade})?"):
        print("  Cancelled.")
        return
    reason = _prompt("  Reason (blank ok): ") or None
    TGR.delete(t.target_id, actor=principal, reason=reason)
    print(f"  ✓ Deleted target #{t.target_id}.")


def _class(principal: Principal) -> None:
    mine = TG.list_groups(academic_year=TG.current_year(), teacher=principal.username)
    groups = [g for g in (mine if mine and not (TGR.is_editor(principal) and not _yes(
        "  Only your groups?")) else TG.list_groups(academic_year=TG.current_year()))
        if g.is_active]
    if not groups:
        print("  No teaching groups this year.")
        return
    for i, g in enumerate(groups, 1):
        print(f"  {i:>3}) {g.code:<10} Y{g.year_group} {g.teacher_name or ''}")
    raw = _prompt("  Group number or code: ")
    g = groups[int(raw) - 1] if raw.isdigit() and 1 <= int(raw) <= len(groups) else \
        next((x for x in groups if x.code.lower() == raw.lower()), None)
    if g is None:
        if raw:
            print("  No such group.")
        return
    s = S.get(g.subject_id)
    names = TGR.scales_for(g.year_group, s)
    print(f"\n  {g.code} {s.code} - grades: "
          + " or ".join(", ".join(TGR.SCALES[n]) for n in names)
          + ". Enter keeps a value, '-' clears min/aspirational.")
    source = _prompt(f"  Source for new targets [{TGR.DEFAULT_SOURCE}]: ") or TGR.DEFAULT_SOURCE
    changes = {}
    lowered = False
    for p, t in TGR.class_sheet(g.group_id):
        print(f"\n  {p.display_name} ({p.admission_no})")
        row = {k: (getattr(t, k) if t else None) for k in ("target_grade", "minimum_grade",
                                                            "aspirational_grade")}
        changed = False
        for k, label in (("target_grade", "Target"), ("minimum_grade", "Minimum"),
                         ("aspirational_grade", "Aspirational")):
            v = _ask(f"  {label}", row[k])
            if v is not None:
                row[k] = v or None
                changed = True
        if changed and row["target_grade"]:
            if t is None:
                row["source"] = source
            elif TGR._lowered(t, str(row["target_grade"])):
                lowered = True
            changes[p.pupil_id] = row
    if not changes:
        print("  Nothing changed.")
        return
    reason = _prompt("  Reason for lowering: ") if lowered and TGR.is_editor(principal) \
        else None
    n = TGR.save_class(g.group_id, changes, actor=principal, reason=reason)
    print(f"  ✓ Saved {n} target(s)")


def _missing(principal: Principal) -> None:
    yg = _year()
    rows = TGR.missing(year_group=yg, teacher=principal.username
                       if _yes("  Only your groups?") else None)
    if not rows:
        print("  Every pupil has a target.")
    for g, pupils in rows:
        print(f"  {g.code:<10} Y{g.year_group} {(g.teacher_name or '-')[:18]:<18} "
              f"{len(pupils)}: " + ", ".join(p.display_name for p in pupils))
    _pause()


def _progress() -> None:
    yg = _year()
    s = _subject(required=False)
    status = _prompt(f"  Status ({'/'.join(TGR.STATUSES)}, blank = all): ") or None
    f = {"year_group": yg, "subject_id": s.subject_id if s else None}
    print("\n  " + "  ".join(f"{k}: {v}" for k, v in TGR.progress_summary(**f).items()))
    for r in TGR.progress(**f, status=status):
        t = r["target"]
        print(f"  {t.pupil_name[:22]:<22} Y{t.pupil_year:<2} {t.subject_code[:6]:<6} "
              f"target {t.target_grade:<10} now {r['current'] or '-':<10} {r['status']}")
    _pause()


def _pupil_targets() -> None:
    p = _pupil()
    if not p:
        return
    rows = TGR.for_pupil(p.pupil_id)
    print(f"\n  {p.display_name} ({p.admission_no}) Year {p.year_group}")
    for t in rows:
        print(f"  {t.subject_code:<6} target {t.target_grade:<10} min "
              f"{t.minimum_grade or '-':<10} asp {t.aspirational_grade or '-':<10} "
              f"{t.source} {t.set_date}")
    if not rows:
        print("  No targets.")
    print("\n  History:")
    for h in TGR.history(p.pupil_id):
        print(f"  {h['at']}  {h['actor']:<14} {h['subject_code'] or '':<6} {h['action']:<7} "
              f"{h['old'] or '-'} → {h['new'] or '-'}"
              + (f"  ({h['reason']})" if h["reason"] else ""))
    _pause()


def _export(principal: Principal) -> None:
    yg = _year()
    s = _subject(required=False)
    path = _prompt("  Save to (path.csv): ")
    if path:
        n = TGR.export_csv(path, actor=principal, year_group=yg,
                           subject_id=s.subject_id if s else None)
        print(f"  ✓ Exported {n} target(s)")


def _import(principal: Principal) -> None:
    print("  Columns: Admission no, Subject (code), Target, and optionally Minimum, "
          "Aspirational, Source, Set date, Notes. Nothing is saved unless every row is valid.")
    path = _prompt("  File: ")
    if not path:
        return
    source = _prompt("  Source for rows without one (blank = Teacher): ") or None
    try:
        r = TGR.import_csv(path, actor=principal, source=source)
    except (OSError, UnicodeDecodeError) as e:
        print(f"  Couldn't read the file: {e}")
        return
    print(f"  ✓ New {r['set']} · changed {r['changed']} · unchanged {r['unchanged']}")
