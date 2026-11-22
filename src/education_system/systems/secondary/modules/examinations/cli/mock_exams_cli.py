"""Mock exams in the terminal. The old options 1-14 are kept (series, papers,
results, summary, pupil history); 15-28 are added (whole-paper mark entry,
tiers, subject grades against target, analysis, timetable and clashes,
release, CSV). Rules live in :mod:`modules.examinations.domain.mock_exams`."""

from __future__ import annotations

from education_system.systems.secondary.modules.examinations.domain import mock_exams as MX
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (MX.ValidationError, MX.PermissionDenied, MX.NotFound)


_problem = prompts.problem
_int = prompts.to_int


def _series() -> MX.MockSeries | None:
    rows = MX.list_series()
    if not rows:
        print("  No mock series yet.")
        return None
    _print_series(rows)
    sid = _int(_prompt("  Series ID: "))
    if sid is None:
        return None
    try:
        return MX.get_series(sid)
    except MX.NotFound:
        print("  No series with that ID.")
        return None


def _paper(series: MX.MockSeries | None = None) -> MX.MockPaper | None:
    s = series or _series()
    if s is None:
        return None
    rows = MX.papers(s.series_id)
    if not rows:
        print("  No papers in this series.")
        return None
    _print_papers(rows)
    pid = _int(_prompt("  Paper ID: "))
    if pid is None:
        return None
    p = next((x for x in rows if x.paper_id == pid), None)
    if p is None:
        print("  No paper with that ID in this series.")
    return p


def _pupil() -> P.Pupil | None:
    ref = _prompt("  Pupil (admission number or UPN): ")
    if not ref:
        return None
    p = P.find_by_reference(ref)
    if p is None:
        print("  No pupil with that admission number.")
    return p


def _subject_in(s: MX.MockSeries) -> S.Subject | None:
    subs = {p.subject_code.upper(): p.subject_id for p in MX.papers(s.series_id)}
    if not subs:
        print("  No papers in this series.")
        return None
    code = _prompt(f"  Subject ({', '.join(subs)}): ").upper()
    if code not in subs:
        print("  That subject has no papers in this series.")
        return None
    return S.get(subs[code])


def _print_series(rows: list[MX.MockSeries]) -> None:
    """The old table: ID, Yr, Start, End, Status, Name."""
    print(f"  {'ID':<5} {'Yr':<3} {'Start':<11} {'End':<11} {'Status':<11} {'Name':<34} "
          f"{'Released':<10}")
    for s in rows:
        print(f"  {s.series_id:<5} {s.year_group:<3} {s.start_date:<11} {s.end_date:<11} "
              f"{s.status:<11} {s.name[:34]:<34} {s.released_on or '':<10}")


def _print_papers(rows: list[MX.MockPaper]) -> None:
    """The old table: ID, Date, Subj, Paper, Tier, Max."""
    print(f"  {'ID':<5} {'Date':<11} {'Time':<6} {'Subj':<6} {'Paper':<24} {'Tier':<11} "
          f"{'Max':<5} Boundaries")
    for p in rows:
        print(f"  {p.paper_id:<5} {p.paper_date:<11} {(p.start_time or ''):<6} "
              f"{p.subject_code[:6]:<6} {p.paper_name[:24]:<24} {p.tier:<11} "
              f"{MX._num(p.max_marks):<5} {p.boundaries_text or 'none'}")


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("mock.view")
        print("\n── Mock Exams ──")
        print(f"  Series: {len(MX.list_series())}")
        print("   1) New series\n   2) List series\n   3) Edit series\n   4) Set series status"
              "\n   5) Delete series\n   6) Add paper\n   7) List papers in series"
              "\n   8) Edit paper\n   9) Delete paper\n  10) Paper summary stats"
              "\n  11) Record / update result\n  12) List results for paper"
              "\n  13) Pupil mock history\n  14) Delete result"
              "\n  15) Enter marks for a whole paper\n  16) Set Foundation / Higher tiers"
              "\n  17) Subject grades against target\n  18) Subject summary"
              "\n  19) Below target\n  20) Compare with an earlier series"
              "\n  21) Missing marks\n  22) Timetable and clashes"
              "\n  23) Release / withdraw results\n  24) Pupil report for a series"
              "\n  25) Import marks (CSV)\n  26) Export results (CSV)"
              "\n  27) Blank mark sheet (CSV)\n  28) Series history\n   0) Back")
        choice = _prompt("Select: ")
        if choice in {"0", ""}:
            return
        try:
            {"1": lambda: _series_form(principal, None), "2": _list_series,
             "3": lambda: _series_form(principal, _series()),
             "4": lambda: _set_status(principal), "5": lambda: _delete_series(principal),
             "6": lambda: _paper_form(principal, None), "7": _list_papers,
             "8": lambda: _paper_form(principal, _paper()),
             "9": lambda: _delete_paper(principal), "10": _summary,
             "11": lambda: _record(principal), "12": _list_results, "13": _pupil_history,
             "14": lambda: _delete_result(principal), "15": lambda: _sheet(principal),
             "16": lambda: _tiers(principal), "17": _grades, "18": _subject_summary,
             "19": _below, "20": _compare, "21": _missing, "22": _timetable,
             "23": lambda: _release(principal), "24": _report,
             "25": lambda: _import(principal), "26": lambda: _export(principal),
             "27": lambda: _template(principal), "28": _history,
             }.get(choice, lambda: print("  Invalid selection."))()
        except _ERRORS as e:
            _problem(e)


# ── Series ──────────────────────────────────────────────────────────

def _series_form(principal: Principal, s: MX.MockSeries | None) -> None:
    if s is None and not MX.is_editor(principal):
        raise MX.PermissionDenied("Only the exams officer can do that.")
    data: dict = {}
    for key, label, hint in (("name", "Name", ""),
                             ("year_group", "Year", "7-11"),
                             ("start_date", "Start date", "YYYY-MM-DD"),
                             ("end_date", "End date", "YYYY-MM-DD"),
                             ("notes", "Notes", "")):
        cur = str(getattr(s, key)) if s and getattr(s, key) is not None else None
        v = _ask(label, cur, required=s is None and key != "notes", hint=hint)
        if v is not None:
            data[key] = v
    if s:
        rec = MX.update_series(s.series_id, data, actor=principal)
        print(f"  ✓ Updated {rec.name}")
    else:
        rec = MX.create_series(data, actor=principal)
        print(f"  ✓ Created series {rec.series_id}: {rec.name} ({rec.status})")


def _list_series() -> None:
    y = _int(_prompt("  Year (7-11, blank = all): "))
    st = _prompt(f"  Status ({'/'.join(MX.SERIES_STATUSES)}, blank = all): ") or None
    rows = MX.list_series(year_group=y, status=st)
    print(f"\n  {len(rows)} series:")
    if rows:
        _print_series(rows)
    _pause()


def _set_status(principal: Principal) -> None:
    s = _series()
    if s is None:
        return
    print(f"  Current: {s.status}")
    st = _prompt(f"  New status ({'/'.join(MX.SERIES_STATUSES)}): ")
    if st:
        rec = MX.set_series_status(s.series_id, st, actor=principal)
        print(f"  ✓ {rec.name} is now {rec.status_label}")


def _delete_series(principal: Principal) -> None:
    s = _series()
    if s is None:
        return
    if _yes(f"  Delete {s.name}, {len(MX.papers(s.series_id))} paper(s) and "
            f"{MX.results_count(s.series_id)} result(s)?"):
        MX.delete_series(s.series_id, actor=principal)
        print("  ✓ Deleted")


# ── Papers ──────────────────────────────────────────────────────────

def _paper_form(principal: Principal, p: MX.MockPaper | None) -> None:
    if p is None:
        s = _series()
        if s is None:
            return
        print("  Subjects: " + ", ".join(x.code for x in S.list_subjects()))
    else:
        s = MX.get_series(p.series_id)
    print(f"  Series dates {s.start_date} to {s.end_date}. Tiers: {', '.join(MX.PAPER_TIERS)}")
    print("  Grade boundaries: lowest mark per grade, e.g. 9=72, 8=64, 7=56 (higher-tier "
          "combined science 9-9=..., foundation 5=...).")
    data: dict = {}
    for key, label, hint in (("subject", "Subject code", ""),
                             ("paper_name", "Paper name", "e.g. Paper 1"),
                             ("paper_date", "Paper date", "YYYY-MM-DD"),
                             ("start_time", "Start time", "HH:MM"),
                             ("duration_mins", "Length (mins)", ""),
                             ("room", "Room", ""),
                             ("max_marks", "Max marks", ""),
                             ("tier", "Tier", "/".join(MX.PAPER_TIERS)),
                             ("grade_boundaries", "Grade boundaries", ""),
                             ("notes", "Notes", "")):
        if p is None:
            cur = None
        elif key == "subject":
            cur = p.subject_code
        elif key == "grade_boundaries":
            cur = p.boundaries_text or None
        else:
            v = getattr(p, key)
            cur = MX._num(v) if isinstance(v, float) else (None if v is None else str(v))
        v = _ask(label, cur, required=p is None and key in ("subject", "paper_name",
                                                            "paper_date", "max_marks"),
                 hint=hint)
        if v is not None:
            data[key] = v
    if "subject" in data:
        data["subject_id"] = data.pop("subject")
    if p:
        rec = MX.update_paper(p.paper_id, data, actor=principal)
        print(f"  ✓ Updated {rec.label}")
    else:
        rec = MX.create_paper({**data, "series_id": s.series_id}, actor=principal)
        print(f"  ✓ Added paper {rec.paper_id}: {rec.label}")


def _list_papers() -> None:
    s = _series()
    if s is None:
        return
    rows = MX.papers(s.series_id)
    print(f"\n  {len(rows)} paper(s) in {s.name}:")
    if rows:
        _print_papers(rows)
    _pause()


def _delete_paper(principal: Principal) -> None:
    p = _paper()
    if p and _yes(f"  Delete {p.label} and its {len(MX.list_results(p.paper_id))} "
                  "result(s)?"):
        MX.delete_paper(p.paper_id, actor=principal)
        print("  ✓ Deleted")


def _summary() -> None:
    p = _paper()
    if p is None:
        return
    from education_system.systems.secondary.modules.examinations.gui.mock_exams_views import (
        summary_text,
    )
    print("\n  " + summary_text(p.paper_id).replace("\n", "\n  "))
    _pause()


# ── Results ─────────────────────────────────────────────────────────

def _record(principal: Principal) -> None:
    p = _paper()
    pupil = p and _pupil()
    if not p or not pupil:
        return
    cur = next((r for r in MX.list_results(p.paper_id) if r.pupil_id == pupil.pupil_id), None)
    print(f"  {p.label}: out of {MX._num(p.max_marks)}; grades "
          f"{', '.join(MX.grades_for(p.tier))}; blank grade = from the boundaries")
    if cur:
        print(f"  Existing: {'absent' if cur.absent else MX._num(cur.marks_awarded)} "
              f"{cur.grade or ''}")
    absent = _yes("  Absent?")
    data: dict = {"pupil_id": pupil.pupil_id, "absent": absent}
    if absent:
        data["absence_reason"] = _prompt(f"  Reason ({'/'.join(MX.ABSENCE_REASONS)}): ")
    else:
        data["marks_awarded"] = _prompt("  Marks: ")
        data["grade"] = _prompt("  Grade (blank = from boundaries): ")
    data["notes"] = _prompt("  Notes: ") or (cur.notes if cur else "")
    r = MX.upsert_result(p.paper_id, data, actor=principal)
    print(f"  ✓ {r.pupil_name}: " + ("absent" if r.absent else
                                     f"{MX._num(r.marks_awarded)} ({r.mark_pct}%) "
                                     f"grade {r.grade or '-'}"))


def _print_results(p: MX.MockPaper) -> list[MX.MockResult]:
    """The old table: ID, Pupil, Marks, %, Grade, Abs."""
    rows = MX.list_results(p.paper_id)
    print(f"  {'ID':<5} {'Pupil':<10} {'Name':<24} {'Marks':<8} {'%':<6} {'Grade':<6} Abs")
    for r in rows:
        print(f"  {r.result_id:<5} {r.admission_no:<10} {r.pupil_name[:24]:<24} "
              f"{MX._num(r.marks_awarded):<8} "
              f"{'' if r.mark_pct is None else r.mark_pct:<6} "
              f"{(r.grade or '') + ('*' if r.grade_source == 'manual' else ''):<6} "
              f"{'Y' if r.absent else ''}")
    return rows


def _list_results() -> None:
    p = _paper()
    if p is None:
        return
    print(f"\n  {p.label}:")
    rows = _print_results(p)
    print(f"  {len(rows)} result(s); * = grade typed in")
    _pause()


def _pupil_history() -> None:
    pupil = _pupil()
    if pupil is None:
        return
    rows = MX.results_for_pupil(pupil.pupil_id)
    print(f"\n  {pupil.display_name}: {len(rows)} mock result(s)")
    for s, p, r in rows:
        print(f"  {p.paper_date} {s.name[:22]:<22} {p.label[:30]:<30} " + (
            "absent" if r.absent else f"{MX._num(r.marks_awarded)}/{MX._num(p.max_marks)} "
            f"{r.grade or ''}") + ("" if s.released else "  (not released)"))
    _pause()


def _delete_result(principal: Principal) -> None:
    p = _paper()
    if p is None:
        return
    rows = _print_results(p)
    rid = _int(_prompt("  Result ID: "))
    r = next((x for x in rows if x.result_id == rid), None)
    if r and _yes(f"  Delete {r.pupil_name}'s result?"):
        MX.delete_result(r.result_id, actor=principal)
        print("  ✓ Deleted")


def _sheet(principal: Principal) -> None:
    p = _paper()
    if p is None:
        return
    s = MX.get_series(p.series_id)
    print(f"  {p.label}: out of {MX._num(p.max_marks)}. Type marks, a grade (e.g. g6), "
          "'a' for absent, '-' to clear, blank to keep.")
    rows: dict[int, dict] = {}
    for pupil, r, access in MX.mark_sheet(p.paper_id):
        if not MX.can_mark(principal, p, s, pupil.pupil_id):
            continue
        cur = "absent" if r and r.absent else (MX._num(r.marks_awarded) or r.grade or "") \
            if r else ""
        extra = f"  [{access}]" if access else ""
        raw = _prompt(f"  {pupil.admission_no} {pupil.display_name[:24]:<24}"
                      f"{f' [{cur}]' if cur else ''}{extra}: ").strip()
        if not raw:
            continue
        if raw == "-":
            rows[pupil.pupil_id] = {}
        elif raw.lower() == "a":
            rows[pupil.pupil_id] = {"absent": "Y"}
        elif raw.lower().startswith("g"):
            rows[pupil.pupil_id] = {"grade": raw[1:]}
        else:
            rows[pupil.pupil_id] = {"marks_awarded": raw}
    if not rows:
        print("  Nothing changed.")
        return
    n = MX.save_sheet(p.paper_id, rows, actor=principal)
    print(f"  ✓ {n} result(s) saved")


def _tiers(principal: Principal) -> None:
    s = _series()
    sub = s and _subject_in(s)
    if not s or not sub:
        return
    cur = MX.entries(s.series_id, sub.subject_id)
    print("  F = Foundation, H = Higher, '-' = no tier, blank = keep.")
    changes: dict[int, str | None] = {}
    for pupil in MX.subject_pupils(s, sub.subject_id):
        raw = _prompt(f"  {pupil.admission_no} {pupil.display_name[:24]:<24} "
                      f"[{cur.get(pupil.pupil_id, '-')}]: ").strip().upper()
        if raw in ("F", "H"):
            changes[pupil.pupil_id] = "Foundation" if raw == "F" else "Higher"
        elif raw == "-":
            changes[pupil.pupil_id] = None
    if changes:
        n = MX.set_tiers(s.series_id, sub.subject_id, changes, actor=principal)
        print(f"  ✓ {n} entr(y/ies) changed")


# ── Analysis ────────────────────────────────────────────────────────

def _print_grades(rows: list[dict]) -> None:
    print(f"  {'Pupil':<10} {'Name':<22} {'Subj':<6} {'Tier':<11} {'Marks':<10} {'%':<6} "
          f"{'Grade':<6} {'Tgt':<5} {'Against':<11} Note")
    for r in rows:
        marks = f"{MX._num(r['marks'])}/{MX._num(r['max'])}" if r["marks"] is not None else ""
        print(f"  {r['pupil'].admission_no:<10} {r['pupil'].display_name[:22]:<22} "
              f"{r['subject_code'][:6]:<6} {r['tier']:<11} {marks:<10} "
              f"{'' if r['pct'] is None else r['pct']:<6} {(r['grade'] or '-'):<6} "
              f"{(r['target'] or '-'):<5} {r['vs_target']:<11} {r['note']}")


def _grades() -> None:
    s = _series()
    if s is None:
        return
    code = _prompt("  Subject code (blank = all): ").upper()
    sid = next((p.subject_id for p in MX.papers(s.series_id)
                if p.subject_code.upper() == code), None) if code else None
    rows = MX.subject_results(s.series_id, subject_id=sid)
    print(f"\n  {len(rows)} pupil-subject result(s):")
    _print_grades(rows)
    _pause()


def _subject_summary() -> None:
    s = _series()
    if s is None:
        return
    print(f"\n  {'Subject':<24} {'Pupils':<7} {'Graded':<7} {'Avg%':<6} {'4+%':<6} {'5+%':<6} "
          f"{'7+%':<6} Below target")
    for r in MX.subject_summary(s.series_id):
        def pc(v):
            return "-" if v is None else v
        print(f"  {r['subject_name'][:24]:<24} {r['pupils']:<7} {r['graded']:<7} "
              f"{pc(r['avg_pct']):<6} {pc(r['pct4']):<6} {pc(r['pct5']):<6} "
              f"{pc(r['pct7']):<6} {r['below_target']}")
    _pause()


def _below() -> None:
    s = _series()
    if s is None:
        return
    rows = MX.below_target(s.series_id, well_below_only=_yes("  Well below only?"))
    print(f"\n  {len(rows)} below target:")
    _print_grades(rows)
    _pause()


def _compare() -> None:
    print("  This series:")
    s = _series()
    if s is None:
        return
    print("  Compare with:")
    e = _series()
    if e is None:
        return
    rows = MX.compare_series(s.series_id, e.series_id)
    print(f"\n  {len(rows)} pupil-subject(s): {sum(r['change'] > 0 for r in rows)} up, "
          f"{sum(r['change'] < 0 for r in rows)} down")
    for r in sorted(rows, key=lambda x: x["change"]):
        print(f"  {r['pupil'].display_name[:24]:<24} {r['subject_code']:<6} "
              f"{r['earlier']:>4} → {r['grade']:<4} ({r['change']:+g})")
    _pause()


def _missing() -> None:
    s = _series()
    if s is None:
        return
    rows = MX.missing_marks(s.series_id)
    if not rows:
        print("  Every candidate has a result.")
    for p, ms in rows:
        print(f"  {p.paper_date} {p.label}: " + ", ".join(x.display_name for x in ms))
    _pause()


def _timetable() -> None:
    s = _series()
    if s is None:
        return
    print(f"\n  {'Date':<11} {'Time':<12} {'Paper':<34} {'Room':<8} {'Cands':<6} Access")
    for row in MX.timetable(s.series_id):
        p = row["paper"]
        w = p.window()
        print(f"  {p.paper_date:<11} "
              f"{(f'{w[0]:%H:%M}-{w[1]:%H:%M}' if w else 'not set'):<12} {p.label[:34]:<34} "
              f"{(p.room or ''):<8} {row['candidates']:<6} {row['access']}")
    cl = MX.clashes(s.series_id)
    print(f"\n  {len(cl)} clash(es)")
    for p, q, ps in cl:
        print(f"  {p.paper_date}: {p.label} and {q.label} - "
              + ", ".join(x.display_name for x in ps))
    _pause()


def _release(principal: Principal) -> None:
    s = _series()
    if s is None:
        return
    if s.released:
        if _yes(f"  {s.name} was released on {s.released_on}. Withdraw it?"):
            MX.release_results(s.series_id, actor=principal, release=False)
            print("  ✓ Release withdrawn")
    elif _yes(f"  Release {s.name} results to pupils and parents?"):
        MX.release_results(s.series_id, actor=principal)
        print("  ✓ Released")


def _report() -> None:
    s = _series()
    pupil = s and _pupil()
    if not s or not pupil:
        return
    rep = MX.pupil_report(s.series_id, pupil.pupil_id)
    print(f"\n  {pupil.display_name} - {s.name}")
    _print_grades(rep["subjects"])
    for p, r in rep["papers"]:
        print(f"    {p.paper_date} {p.label[:30]:<30} " + (
            "absent" if r.absent else f"{MX._num(r.marks_awarded)}/{MX._num(p.max_marks)} "
            f"{r.grade or ''}"))
    _pause()


def _import(principal: Principal) -> None:
    p = _paper()
    if p is None:
        return
    print("  Columns: Admission no, Marks, Grade, Absent, Absence reason, Notes")
    path = _prompt("  CSV file: ")
    if path:
        try:
            n = MX.import_marks(p.paper_id, path, actor=principal)
        except (OSError, UnicodeDecodeError) as e:
            print(f"  Can't read that file: {e}")
            return
        print(f"  ✓ {n} result(s) changed")


def _export(principal: Principal) -> None:
    s = _series()
    path = s and _prompt("  Save to (CSV path): ")
    if s and path:
        try:
            n = MX.export_results(s.series_id, path, actor=principal)
        except OSError as e:
            print(f"  Can't write that file: {e}")
            return
        print(f"  ✓ {n} row(s) written to {path}")


def _template(principal: Principal) -> None:
    p = _paper()
    path = p and _prompt("  Save to (CSV path): ")
    if p and path:
        try:
            n = MX.export_sheet_template(p.paper_id, path, actor=principal)
        except OSError as e:
            print(f"  Can't write that file: {e}")
            return
        print(f"  ✓ {n} candidate(s) written to {path}")


def _history() -> None:
    s = _series()
    if s is None:
        return
    for h in MX.history(s.series_id):
        print(f"  {h['at']}  {h['actor']:<14} {h['action']:<15} "
              + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))
    _pause()
