"""Gradebook in the terminal. The old options 1-5 are kept (record / update an
entry, list entries, pupil / subject summary, cohort assessment summary, delete
an entry); 6-14 are added. Rules live in :mod:`modules.assessment.domain.gradebook`."""

from __future__ import annotations

from education_system.systems.secondary.modules.assessment.domain import gradebook as GB
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

_ERRORS = (GB.ValidationError, GB.PermissionDenied, GB.NotFound)


_problem = prompts.problem


def _pct(v) -> str:
    return "-" if v is None else f"{v:g}%"


def _print_entries(rows: list[GB.Entry]) -> None:
    if not rows:
        print("  (no entries)")
        return
    print(f"  {'ID':<5} {'Date':<10} {'Pupil':<20} {'Subj':<6} {'Term':<7} {'Type':<10} "
          f"{'Assessment':<22} {'Marks':<8} {'%':<5} Grade")
    for e in rows:
        pct = f"{e.mark_pct:.0f}" if e.mark_pct is not None else "-"
        print(f"  {e.mark_id:<5} {e.assessment_date:<10} {e.pupil_name[:20]:<20} "
              f"{e.subject_code[:6]:<6} {e.term:<7} {e.assessment_type[:10]:<10} "
              f"{e.assessment_name[:22]:<22} {e.marks_label[:8]:<8} {pct:<5} {e.grade or '-'}")


def _print_assessments(rows: list[GB.Assessment]) -> None:
    if not rows:
        print("  (no assessments)")
        return
    print(f"  {'ID':<5} {'Date':<10} {'For':<9} {'Subj':<6} {'Assessment':<26} {'Out of':<7} "
          f"{'Marked':<7} Status")
    for a in rows:
        print(f"  {a.assessment_id:<5} {a.assessment_date:<10} {a.for_label[:9]:<9} "
              f"{a.subject_code[:6]:<6} {a.name[:26]:<26} "
              f"{'' if a.max_marks is None else f'{a.max_marks:g}':<7} {a.marked:<7} "
              f"{a.status}")


def _subject() -> S.Subject | None:
    code = _prompt("  Subject code: ").strip().lower()
    if not code:
        return None
    match = next((s for s in S.list_subjects() if s.code.lower() == code), None)
    if match is None:
        print("  No subject with that code.")
    return match


def _pupil() -> P.Pupil | None:
    ref = _prompt("  Pupil (admission no or UPN): ")
    if not ref:
        return None
    p = P.find_by_reference(ref)
    if p is None:
        print("  No pupil with that admission number or UPN.")
    return p


def _assessment() -> GB.Assessment | None:
    raw = _prompt("  Assessment ID: ")
    if not raw.isdigit():
        return None
    try:
        return GB.get(int(raw))
    except GB.NotFound:
        print("  No such assessment.")
        return None


def _group() -> TG.TeachingGroup | None:
    code = _prompt("  Teaching group code: ")
    if not code:
        return None
    g = TG.find(code)
    if g is None:
        print("  No group with that code this year.")
    return g


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("gradebook.view")
        year = TG.current_year()
        missing = sum(n for _a, n in GB.missing_marks(principal))
        print("\n── Gradebook ──")
        print(f"  Assessments this year ({year}): {len(GB.list_assessments(academic_year=year))}"
              + (f"   · {missing} mark(s) for you to enter" if missing else ""))
        print("   1) Record / update entry\n   2) List entries\n   3) Pupil / subject summary"
              "\n   4) Cohort assessment summary\n   5) Delete entry"
              "\n   6) New assessment for a class\n   7) List assessments"
              "\n   8) Enter marks for a class\n   9) Edit / lock / delete an assessment"
              "\n  10) Markbook for a class\n  11) Missing marks\n  12) Pupils of concern"
              "\n  13) Subject grade boundaries\n  14) Export markbook / import marks (CSV)"
              "\n   0) Back")
        choice = _prompt("Select: ")
        if choice in {"0", ""}:
            return
        try:
            {"1": lambda: _record(principal), "2": _list, "3": _pupil_summary, "4": _cohort,
             "5": lambda: _delete_entry(principal), "6": lambda: _new(principal),
             "7": lambda: _list_assessments(principal), "8": lambda: _marks(principal),
             "9": lambda: _manage(principal), "10": _markbook,
             "11": lambda: _missing(principal), "12": _concerns,
             "13": lambda: _boundaries(principal), "14": lambda: _csv(principal),
             }.get(choice, lambda: print("  Invalid selection."))()
        except _ERRORS as e:
            _problem(e)


def _record(principal: Principal) -> None:
    p = _pupil()
    s = p and _subject()
    if not p or not s:
        return
    data = {"pupil": p.admission_no, "subject_id": s.subject_id,
            "assessment_name": _prompt("  Assessment name: "),
            "assessment_type": _prompt(f"  Type ({'/'.join(GB.ASSESSMENT_TYPES)}) "
                                       "[Test]: ") or "Test",
            "term": _prompt(f"  Term ({'/'.join(GB.TERMS)}, blank = from date): ") or None,
            "assessment_date": _prompt("  Date (YYYY-MM-DD, blank = today): ") or None,
            "status": _prompt("  Status (Marked/Absent/Excused) [Marked]: ") or "Marked"}
    if data["status"].lower() == "marked":
        data.update(marks_awarded=_prompt("  Marks awarded (blank ok): "),
                    max_marks=_prompt("  Max marks (blank ok): "),
                    grade=_prompt("  Grade (blank = from boundaries): "))
    data.update(teacher=_prompt("  Teacher (blank ok): ") or None,
                comments=_prompt("  Comments (blank ok): ") or None)
    e = GB.record_entry(data, actor=principal)
    print(f"  ✓ Saved entry #{e.mark_id}: {e.pupil_name} / {e.subject_code} / "
          f"{e.assessment_name} - {e.marks_label} {_pct(e.mark_pct)} {e.grade or ''}")


def _list() -> None:
    yg = _prompt("  Year (7-11, blank): ")
    term = _prompt(f"  Term ({'/'.join(GB.TERMS)}, blank): ").title() or None
    atype = _prompt(f"  Type ({'/'.join(GB.ASSESSMENT_TYPES)}, blank): ").title() or None
    df = _prompt("  From date (blank): ") or None
    dt = _prompt("  To date (blank): ") or None
    rows = GB.list_entries(year_group=int(yg) if yg.isdigit() else None, term=term,
                           assessment_type=atype, date_from=df, date_to=dt)
    print(f"\n  {len(rows)} entr(ies):")
    _print_entries(rows)
    _pause()


def _pupil_summary() -> None:
    p = _pupil()
    s = p and _subject()
    if not p or not s:
        return
    r = GB.pupil_subject_summary(p.pupil_id, s.subject_id)
    print(f"\n  {p.display_name} · {s.code}")
    print(f"  Entries: {r['count']}    Avg %: {_pct(r['avg_pct'])}    Latest grade: "
          f"{r['latest_grade'] or '-'}    Absent: {r['absent']}")
    print("  By term: " + "    ".join(f"{k}: {v}" for k, v in r["by_term"].items()))
    _print_entries(r["entries"])
    _pause()


def _cohort() -> None:
    a = _assessment()
    if not a:
        return
    s = GB.assessment_summary(a.assessment_id)
    print(f"\n  {a.name} · {a.subject_code} {a.for_label} · {a.assessment_date}")
    print(f"  Pupils: {s['count']}    marked {s['marked']} · absent {s['absent']} · "
          f"excused {s['excused']} · still to mark {len(s['missing'])}")
    print(f"  Avg %: {_pct(s['avg_pct'])}    median {_pct(s['median_pct'])}    max "
          f"{_pct(s['max_pct'])}    min {_pct(s['min_pct'])}")
    print("  Grades: " + ("  ".join(f"{g}: {n}" for g, n in s["grades"].items()) or "-"))
    _print_entries(s["entries"])
    if s["missing"]:
        print("  Still to mark: " + ", ".join(p.display_name for p in s["missing"]))
    _pause()


def _delete_entry(principal: Principal) -> None:
    raw = _prompt("  Entry ID: ")
    if not raw.isdigit():
        return
    e = GB.get_entry(int(raw))
    if _yes(f"  Delete {e.pupil_name} — {e.assessment_name}?"):
        GB.delete_entry(e.mark_id, actor=principal)
        print(f"  ✓ Deleted entry #{e.mark_id}.")


def _collect(existing: GB.Assessment | None) -> dict:
    data: dict = {}

    def ask(key: str, label: str, current=None, **kw) -> None:
        v = _ask(label, None if current in (None, "") else (
            f"{current:g}" if isinstance(current, float) else str(current)), **kw)
        if v is not None:
            data[key] = v
    g = (lambda k: getattr(existing, k)) if existing else (lambda _k: None)
    ask("name", "Assessment name", g("name"), required=existing is None)
    ask("assessment_type", "Type", g("assessment_type") or "Test",
        hint="/".join(GB.ASSESSMENT_TYPES))
    ask("assessment_date", "Date", g("assessment_date"), hint="YYYY-MM-DD, blank = today")
    ask("term", "Term", g("term"), hint="blank = from the date")
    ask("max_marks", "Out of (max marks)", g("max_marks"), hint="blank = grades only")
    ask("weight", "Weight", g("weight"), hint="default 1")
    ask("boundaries", "Grade boundaries", g("boundaries"), hint="blank = the subject's")
    ask("notes", "Notes", g("notes"))
    return data


def _new(principal: Principal) -> None:
    g = _group()
    data: dict = {}
    if g:
        data["group_id"] = g.group_id
    else:
        s = _subject()
        y = _prompt("  Year (7-11): ")
        if not s or not y:
            return
        data.update(subject_id=s.subject_id, year_group=y)
    data.update(_collect(None))
    a = GB.create(data, actor=principal)
    print(f"  ✓ Assessment #{a.assessment_id}: {a.name} for {a.for_label}")


def _list_assessments(principal: Principal) -> None:
    mine = _yes("  Only mine?")
    _print_assessments(GB.list_assessments(academic_year=TG.current_year(),
                                           teacher=principal.username if mine else None))
    _pause()


def _marks(principal: Principal) -> None:
    a = _assessment()
    if not a:
        return
    done = {e.pupil_id: e for e in GB.entries(a.assessment_id)}
    pupils = GB.pupils_for(a)
    if not pupils:
        print("  No pupils yet (year-group assessment) - add marks with option 1.")
        return
    print(f"  {a.name} - " + (f"out of {a.max_marks:g}" if a.max_marks else "grades only")
          + ". Type a mark, a grade after a slash (12/6, or /6), A = absent, X = excused, "
            "Enter = keep, '.' = stop.")
    changes = {}
    for p in pupils:
        e = done.get(p.pupil_id)
        cur = e.marks_label + (f" {e.grade}" if e and e.grade else "") if e else ""
        raw = _prompt(f"  {p.display_name[:26]:<26} [{cur}]: ")
        if raw == ".":
            break
        if not raw:
            continue
        if raw.upper() in ("A", "X"):
            changes[p.pupil_id] = {"status": "Absent" if raw.upper() == "A" else "Excused"}
            continue
        mark, _sep, grade = raw.partition("/")
        changes[p.pupil_id] = {"marks_awarded": mark.strip(), "grade": grade.strip(),
                               "comments": e.comments if e else None}
    if changes:
        n = GB.record_marks(a.assessment_id, changes, actor=principal)
        print(f"  ✓ Saved {n} mark(s)")


def _manage(principal: Principal) -> None:
    a = _assessment()
    if not a:
        return
    act = _prompt("  e) Edit  l) Lock / unlock  d) Delete  h) History: ").lower()
    if act == "e":
        a = GB.update(a.assessment_id, _collect(a), actor=principal)
        print(f"  ✓ Saved {a.name}")
    elif act == "l":
        a = GB.set_locked(a.assessment_id, not a.locked, actor=principal)
        print(f"  ✓ {a.name} is now {a.status.lower()}")
    elif act == "d" and _yes(f"  Delete '{a.name}'" + (f" and {a.marked} mark(s)"
                                                       if a.marked else "") + "?"):
        GB.delete(a.assessment_id, actor=principal)
        print("  ✓ Deleted")
    elif act == "h":
        for h in GB.history(a.assessment_id):
            print(f"  {h['at']}  {h['actor']:<14} {h['action']:<10} "
                  + ", ".join(f"{k}: {v}" for k, v in h["detail"].items()))
        _pause()


def _markbook() -> None:
    g = _group()
    if not g:
        return
    mb = GB.markbook(group_id=g.group_id)
    heads = [a.name[:10] for a in mb["assessments"]]
    print(f"\n  {g.code}: " + ", ".join(f"{i + 1}={a.name} ({a.assessment_date})"
                                     for i, a in enumerate(mb["assessments"])))
    print(f"  {'Pupil':<24} " + " ".join(f"{i + 1:<8}" for i in range(len(heads)))
          + " Avg     Latest")
    for r in mb["rows"]:
        p = r["pupil"]
        cells = [r["cells"].get(a.assessment_id) for a in mb["assessments"]]
        print(f"  {p.display_name[:24]:<24} "
              + " ".join(f"{(c.marks_label if c else '·')[:8]:<8}" for c in cells)
              + f" {_pct(r['avg_pct']):<7} {r['latest_grade'] or ''}")
    _pause()


def _missing(principal: Principal) -> None:
    rows = GB.missing_marks(principal, everyone=GB.is_editor(principal) and _yes(
        "  Everyone's?"))
    if not rows:
        print("  Nothing waiting to be marked.")
    for a, n in rows:
        print(f"  #{a.assessment_id:<5} {a.assessment_date} {a.for_label:<9} {a.name[:30]:<30} "
              f"{n} to mark")
    _pause()


def _concerns() -> None:
    raw = _prompt("  Average below % [40]: ")
    drop = _prompt("  Or a drop of [15]: ")
    rows = GB.concerns(below=float(raw) if raw else 40.0, drop=float(drop) if drop else 15.0)
    if not rows:
        print("  No pupils of concern.")
    for c in rows:
        print(f"  {c['pupil_name'][:24]:<24} Y{c['year']} {c['subject_code']:<6} {c['why']}")
    _pause()


def _boundaries(principal: Principal) -> None:
    s = _subject()
    if not s:
        return
    print(f"  Current: {GB.subject_boundaries(s.subject_id) or '(none)'}")
    if not GB.is_editor(principal):
        return
    raw = _prompt(f"  New (e.g. {GB.GCSE_BOUNDARIES}; 'gcse' for that; '-' to remove; "
                  "Enter = keep): ")
    if not raw:
        return
    text = GB.GCSE_BOUNDARIES if raw.lower() == "gcse" else "" if raw == "-" else raw
    print(f"  ✓ {GB.set_subject_boundaries(s.subject_id, text, actor=principal) or 'Removed'}")


def _csv(principal: Principal) -> None:
    act = _prompt("  e) Export a class markbook  i) Import marks for an assessment: ").lower()
    if act == "e":
        g = _group()
        if not g:
            return
        default = f"markbook-{g.code.replace('/', '-')}.csv"
        path = _prompt(f"  Save to [{default}]: ") or default
        try:
            n = GB.export_markbook(path, actor=principal, group_id=g.group_id)
        except OSError as e:
            print(f"  Couldn't save: {e}")
            return
        print(f"  ✓ Saved {n} pupil(s) to {path}")
    elif act == "i":
        a = _assessment()
        path = a and _prompt("  CSV file (Admission no, Mark / Grade, Comments): ")
        if not a or not path:
            return
        try:
            n, notes = GB.import_marks(a.assessment_id, path, actor=principal)
        except (OSError, UnicodeDecodeError) as e:
            print(f"  Couldn't read: {e}")
            return
        print(f"  ✓ Saved {n} mark(s)")
        for x in notes:
            print(f"  ! {x}")
