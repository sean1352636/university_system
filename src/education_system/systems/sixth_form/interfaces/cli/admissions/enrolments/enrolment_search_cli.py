"""Enrolment CLI: search, filter, sort, saved presets and record checks."""

from __future__ import annotations

from typing import Callable
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as data
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.admissions.enrolments.enrolments import (
    Enrolment,
    STATUSES,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.enrolments._common import (
    _PRESETS_PATH,
    _UserAbort,
    _colour,
    _default_academic_year,
    _input,
    _load_presets,
    _pause,
    _pick_from,
    _pick_student,
    _print_leaver_effects,
    _print_table,
    _print_table_paged,
    _row_action_loop,
    _save_json,
    _status_counts,
    _student_names,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.enrolments.enrolment_workflows_cli import (
    enrol_from_student_profile,
)



# ════════════════════════════════════════════════════════════════════
# Search / filter / sort (features 9, 10, 11, 12, 14, 15)
# ════════════════════════════════════════════════════════════════════

def _apply_filter_dict(preset: dict[str, str]) -> list[Enrolment]:
    """Run a saved-preset filter dict (same keys as the GUI directory)."""
    rows = data.list_enrolments(
        academic_year=(preset.get("academic_year") or "").strip() or None,
        year_group=int(preset["year_group"]) if preset.get("year_group") else None,
        status=(preset.get("status") or "").strip() or None,
    )
    names = _student_names()
    tg = (preset.get("tutor_group") or "").strip().lower()
    if tg:
        rows = [r for r in rows if tg in (r.tutor_group or "").lower()]
    q = (preset.get("search") or "").strip().lower()
    if q:
        rows = [r for r in rows if q in r.student_id.lower()
                or q in names.get(r.student_id, "").lower()]
    sf = (preset.get("start_from") or "").strip()
    if sf:
        rows = [r for r in rows if (r.start_date or "") >= sf]
    st = (preset.get("start_to") or "").strip()
    if st:
        rows = [r for r in rows if r.start_date and r.start_date <= st]
    return rows


def search_enrolments() -> None:
    """Feature #9 — free-text search by student ID or name."""
    print("\n═══ Search Enrolments ═══")
    try:
        q = _input("Search (student ID or name)", allow_empty=False).lower()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    names = _student_names()
    rows = [r for r in data.list_enrolments()
            if q in r.student_id.lower() or q in names.get(r.student_id, "").lower()]
    _print_table_paged(rows)
    _row_action_loop(rows)


def filter_by_tutor_group() -> None:
    """Feature #10 — filter enrolments by tutor group (substring match)."""
    print("\n═══ Filter by Tutor Group ═══")
    try:
        tg = _input("Tutor group contains", allow_empty=False).lower()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = [r for r in data.list_enrolments() if tg in (r.tutor_group or "").lower()]
    _print_table_paged(rows)
    _row_action_loop(rows)


def filter_by_date_range() -> None:
    """Feature #11 — filter by a start-date window (inclusive)."""
    print("\n═══ Filter by Start-Date Range ═══")
    try:
        sf = _input("Start on/after (YYYY-MM-DD, blank = any)")
        st = _input("Start on/before (YYYY-MM-DD, blank = any)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_enrolments()
    if sf:
        rows = [r for r in rows if (r.start_date or "") >= sf]
    if st:
        rows = [r for r in rows if r.start_date and r.start_date <= st]
    _print_table_paged(rows)
    _row_action_loop(rows)


def quick_filter_current_year() -> None:
    """Feature #15 — list enrolments for the current academic year."""
    year = _default_academic_year()
    print(f"\n═══ Current Year Enrolments ({year}) ═══")
    rows = data.list_enrolments(academic_year=year)
    _print_table_paged(rows)
    _row_action_loop(rows)


def sort_enrolments() -> None:
    """Feature #12 — list all enrolments sorted by a chosen column."""
    print("\n═══ Sort Enrolments ═══")
    keys = {
        "Enrolment #": lambda e: e.enrolment_id,
        "Student ID": lambda e: e.student_id,
        "Academic year": lambda e: e.academic_year,
        "Year group": lambda e: e.year_group,
        "Tutor group": lambda e: (e.tutor_group or ""),
        "Start date": lambda e: (e.start_date or ""),
        "Status": lambda e: e.status,
    }
    try:
        col = _pick_from("Sort by", list(keys))
        direction = _pick_from("Direction", ["Ascending", "Descending"],
                               default="Ascending")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = sorted(data.list_enrolments(), key=keys[col],
                  reverse=(direction == "Descending"))
    _print_table_paged(rows)
    _row_action_loop(rows)


def saved_filter_manager() -> None:
    """Feature #14 — apply / create / delete named filter presets (shared with
    the GUI via the same JSON file)."""
    while True:
        presets = _load_presets()
        print("\n═══ Saved Filter Presets ═══")
        names = sorted(presets)
        for i, name in enumerate(names, 1):
            print(f"  {i}) {name}   {presets[name]}")
        if not names:
            print("  (no presets yet)")
        print("\n  A) Apply   N) New   D) Delete   (Enter to go back)")
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice == "a" and names:
            try:
                name = _pick_from("Apply which preset", names)
            except _UserAbort:
                continue
            rows = _apply_filter_dict(presets[name])
            _print_table_paged(rows)
            _row_action_loop(rows)
        elif choice == "n":
            try:
                name = _input("Preset name", allow_empty=False)
                preset = {
                    "academic_year": _input("Academic year (blank=any)"),
                    "year_group": _input("Year group (blank=any)"),
                    "status": _input("Status (blank=any)"),
                    "tutor_group": _input("Tutor contains (blank=any)"),
                    "search": _input("Search text (blank=any)"),
                    "start_from": _input("Start from (blank=any)"),
                    "start_to": _input("Start to (blank=any)"),
                }
            except _UserAbort:
                continue
            presets[name] = preset
            _save_json(_PRESETS_PATH, presets)
            print(f"  ✓ Saved preset '{name}'")
        elif choice == "d" and names:
            try:
                name = _pick_from("Delete which preset", names)
            except _UserAbort:
                continue
            presets.pop(name, None)
            _save_json(_PRESETS_PATH, presets)
            print(f"  ✓ Deleted preset '{name}'")


# ════════════════════════════════════════════════════════════════════
# Discovery / integrity / student views (features 16, 17, 18, 19, 20,
# 46, 47, 49)
# ════════════════════════════════════════════════════════════════════

def status_badges() -> None:
    """Feature #16 — counts per status across all enrolments."""
    print("\n═══ Status Summary ═══")
    rows = data.list_enrolments()
    counts = _status_counts(rows)
    print(f"\n  Total: {len(rows)}")
    for s in STATUSES:
        print(f"    {_colour(s, s):<20} {counts.get(s, 0)}")
    _pause()


def student_enrolment_history(student_id: str | None = None) -> None:
    """Feature #17 — every enrolment for one student, newest first."""
    print("\n═══ Student Enrolment History ═══")
    try:
        sid = student_id or _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = student_data.get_student(sid)
    print(f"\n  {sid} — {student.full_name if student else '(unknown)'}")
    print(f"  Current: {show_current_year_group(sid, _return=True)}")
    rows = data.list_for_student(sid)
    _print_table(rows)
    for e in rows:
        if e.status == "Withdrawn":
            print(f"    #{e.enrolment_id} withdrawn {e.withdrawal_date or '?'} — "
                  f"{e.withdrawal_reason_label or 'no reason'}")
    try:
        trail = data.enrolment_history(student_id=sid, limit=10)
    except Exception as exc:  # noqa: BLE001 — shown
        print(f"  ✗ Change history not read: {exc}")
        trail = []
    print()
    _print_leaver_effects(sid, indent="  ")
    if trail:
        print("\n  Latest changes (full list: Enrolment Change History):")
        for h in trail:
            print(f"    {(h.get('changed_at') or '')[:16]}  #{h['enrolment_id']:<5} "
                  f"{h['action']:<16} {h.get('changed_by') or '—':<10} "
                  f"{h.get('detail') or ''}")
    _pause()


def show_current_year_group(student_id: str | None = None, *, _return: bool = False):
    """Feature #47 — surface the student's current year-group label."""
    if student_id is None:
        print("\n═══ Current Year Group ═══")
        try:
            student_id = _pick_student()
        except _UserAbort:
            print("\n  Cancelled.")
            return None
    label = data.current_year_group_label(student_id) or "Not currently enrolled"
    if _return:
        return label
    print(f"\n  {student_id}: {label}")
    _pause()
    return label


def sync_status_to_student_record(student_id: str | None = None) -> str | None:
    """Feature #49 — reconcile the student's displayed year group with their
    live enrolment. The enrolment is the source of truth (year group is never
    stored on the student row), so this is a non-destructive read."""
    if student_id is None:
        print("\n═══ Reconcile Year Group ═══")
        try:
            student_id = _pick_student()
        except _UserAbort:
            print("\n  Cancelled.")
            return None
    label = data.current_year_group_label(student_id)
    print(f"\n  Authoritative year group for {student_id}: "
          f"{label or 'none (not enrolled)'}")
    print("  (Year group lives only on the enrolment, so nothing can drift.)")
    _pause()
    return label


def students_without_enrolment() -> None:
    """Feature #18 — students on the roll with no enrolment record."""
    print("\n═══ Students Without an Enrolment ═══")
    try:
        include_leavers = _input("Include learners who have left? (y/n)",
                                 default="n").lower().startswith("y")
        year = _default_academic_year()
        scope = _pick_from("No enrolment", [
            f"this year ({year}) — no live enrolment",
            "ever — no enrolment record at all"], default=None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    this_year = scope.startswith("this year")
    try:
        students = [s for s in student_data.list_students()
                    if include_leavers or s.on_roll]
        if this_year:
            enrolled = {e.student_id for e in data.list_enrolments(academic_year=year)
                        if e.is_live}
        else:
            enrolled = {e.student_id for e in data.list_enrolments()}
    except Exception as exc:
        print(f"  ✗ {exc}")
        _pause()
        return
    missing = [s for s in students if s.student_id not in enrolled]
    what = f"no live enrolment in {year}" if this_year else "no enrolment"
    print(f"\n  {len(missing)} student(s) "
          f"{'(including leavers) ' if include_leavers else 'on roll '}have {what}:\n")
    for s in missing:
        print(f"    {s.student_id:<10}  {s.full_name}"
              + ("  (left)" if not s.on_roll else ""))
    if missing and _input("\n  Enrol one now? Type 'yes' to confirm",
                          default="no").lower() == "yes":
        enrol_from_student_profile()
    else:
        _pause()


def duplicate_conflicts() -> None:
    """Feature #19 — learners with two or more LIVE (Enrolled / Pending)
    enrolments in different academic years: an old year never closed by
    withdrawal, completion or rollover. (One enrolment per learner per
    year is enforced by the database, so that cannot clash.)"""
    print("\n═══ Duplicate Enrolment Conflicts ═══")
    live: dict[str, list[Enrolment]] = {}
    for e in data.list_enrolments():
        if e.is_live:
            live.setdefault(e.student_id, []).append(e)
    clashes = {sid: rows for sid, rows in live.items()
               if len({r.academic_year for r in rows}) > 1}
    if not clashes:
        print("\n  ✓ No conflicts — no learner has live enrolments in two years.")
    else:
        names = _student_names()
        print(f"\n  ✗ {len(clashes)} learner(s) have live enrolments in more "
              "than one year:")
        for sid, rows in sorted(clashes.items()):
            print(f"\n    {sid}  {names.get(sid, '—')}")
            for r in sorted(rows, key=lambda r: r.academic_year):
                print(f"      #{r.enrolment_id:<5} {r.academic_year} Year "
                      f"{r.year_group} [{r.status}]")
        print("\n  Close the older year: Withdraw it (ILR reason), or Bulk "
              "Status Change → Completed.")
        rows = [r for rs in clashes.values() for r in rs]
        _row_action_loop(rows)
        return
    _pause()


def advanced_query() -> None:
    """Feature #20 — combine several conditions with AND / OR."""
    print("\n═══ Advanced Query ═══")
    try:
        mode = _pick_from("Match", ["AND", "OR"], default="AND")
        year = _input("Academic year = (blank to skip)")
        yg = _input("Year group = (blank to skip)")
        status = _input("Status = (blank to skip)")
        tutor = _input("Tutor contains (blank to skip)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    conds: list[Callable[[Enrolment], bool]] = []
    if year:
        conds.append(lambda e, v=year: e.academic_year == v)
    if yg:
        try:
            conds.append(lambda e, v=int(yg): e.year_group == v)
        except ValueError:
            print("  ✗ Year group must be a number.")
            _pause()
            return
    if status:
        conds.append(lambda e, v=status: e.status == v)
    if tutor:
        conds.append(lambda e, v=tutor.lower(): v in (e.tutor_group or "").lower())
    rows = data.list_enrolments()
    if conds:
        combine = all if mode == "AND" else any
        rows = [e for e in rows if combine(c(e) for c in conds)]
    _print_table_paged(rows)
    _row_action_loop(rows)
