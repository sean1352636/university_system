"""Form Tutors in the terminal.

The old menu keeps its options in place: Assignments 1 New, 2 List, 3 View
+ meetings, 4 Edit, 5 End, 6 Delete; Meetings 7 Log, 8 List (filters),
9 Edit, 10 Delete; Reports 11 Cohort summary. New: 12 My form, 13
Follow-ups, 14 Mark follow-up done, 15 Coverage, 16 Take tutors from form
groups, 17 Carry forward to next year, 18 Export CSV. Rules live in
:mod:`modules.curriculum.domain.form_tutors`.
"""

from __future__ import annotations

from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
from education_system.systems.secondary.modules.curriculum.domain import form_tutors as FT
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (FT.ValidationError, FT.PermissionDenied, FT.NotFound)


_problem = prompts.problem
_int = prompts.ask_int
_pick = prompts.pick


def _table(rows: list[FT.TutorAssignment]) -> None:
    if not rows:
        print("  (no assignments)")
        return
    print(f"  {'ID':<5} {'Acad yr':<8} {'Yr':<3} {'Form':<7} {'Tutor':<24} {'Role':<9} "
          f"{'Status':<12} {'Start':<11} End")
    for a in rows:
        print(f"  {a.assignment_id:<5} {a.academic_year:<8} {a.year_group:<3} "
              f"{a.form_group:<7} {a.tutor_name[:24]:<24} {a.role:<9} {a.status:<12} "
              f"{a.start_date:<11} {a.end_date or ''}")


def _meetings_table(rows: list[FT.TutorMeeting]) -> None:
    if not rows:
        print("  (no meetings)")
        return
    for m in rows:
        print(f"  {m.meeting_id:<5} {m.meeting_date:<11} {m.form_group or '':<6} "
              f"{m.meeting_type:<15} {(m.agenda or '')[:40]:<40} "
              + ((m.follow_up_actions or "")[:30] + (" ✓" if m.follow_up_done_at else "")
                 if m.follow_up_actions else ""))


def _get() -> FT.TutorAssignment | None:
    aid = _int("  Assignment ID: ")
    if aid is None:
        print("  Enter the assignment's ID number.")
        return None
    try:
        return FT.get_assignment(aid)
    except FT.NotFound:
        print("  No assignment with that ID.")
        return None


def _form_id(current: FT.TutorAssignment | None = None) -> int | None:
    forms = FG.list_forms()
    for f in forms:
        print(f"    {f.form_id:<4} {f.label:<18} tutor: {f.tutor_name or '-'}")
    v = _prompt("  Form ID" + (f" [{current.form_id}]" if current else "") + ": ")
    if not v:
        return current.form_id if current else None
    return int(v) if v.isdigit() else None


def _details(a: FT.TutorAssignment | None) -> dict:
    data: dict = {}
    if a:
        print("  Press Enter to keep existing value ('-' clears).")
    fid = _form_id(a)
    if fid is not None:
        data["form_id"] = fid
    g = (lambda k: getattr(a, k) if a else None)

    def ask(key, label, default=None):
        cur = g(key) or default
        v = _prompt(f"  {label}" + (f" [{cur}]" if cur else "") + ": ")
        if v:
            data[key] = "" if v == "-" else v
        elif a is None and default:
            data[key] = default
    ask("academic_year", "Academic year", FT.current_year())
    names = FT.staff_names()
    if names:
        print("  Staff: " + "; ".join(names[:20]) + (" …" if len(names) > 20 else ""))
    v = _prompt("  Tutor (username or name)" + (f" [{a.tutor_name}]" if a else "") + ": ")
    if v:
        data["tutor"] = v
    data["role"] = _pick("Role", FT.ROLES, g("role") or FT.DEFAULT_ROLE)
    ask("contact_email", "Email (blank = their login's)")
    ask("start_date", "Start date (YYYY-MM-DD)")
    ask("end_date", "End date")
    data["status"] = _pick("Status", FT.ASSIGNMENT_STATUSES,
                           g("status") or FT.DEFAULT_ASSIGNMENT_STATUS)
    ask("notes", "Notes")
    return data


# ── Assignments (old 1-6) ────────────────────────────────────────────

def _new(principal: Principal) -> None:
    print("\n  ── New Tutor Assignment ──")
    a = FT.create_assignment(_details(None), actor=principal)
    print(f"\n  Created #{a.assignment_id}: {a.tutor_name} ({a.role}) for {a.form_label}.")


def _list(_p: Principal) -> None:
    y = _prompt("  Year (7-11, blank = all): ")
    ay = _prompt(f"  Academic year [{FT.current_year()}, '-' = all]: ")
    st = _prompt("  Status (blank = all): ").capitalize()
    _table(FT.list_assignments(year_group=int(y) if y.isdigit() else None,
                               academic_year=None if ay == "-" else ay or FT.current_year(),
                               status=st or None))


def _view(principal: Principal) -> None:
    a = _get()
    if a is None:
        return
    s = FT.assignment_summary(a.assignment_id, actor=principal)
    print(f"\n  #{a.assignment_id}  {a.tutor_name} - {a.role}, {a.form_label}, "
          f"{a.academic_year}")
    print(f"  {a.status}, {a.start_date} → {a.end_date or 'now'}"
          + (f" · {a.contact_email}" if a.contact_email else ""))
    if a.notes:
        print(f"  Notes: {a.notes}")
    print(f"  {s['meeting_count']} meeting(s), {s['open_follow_ups']} open follow-up(s)")
    if s["by_type"]:
        print("  By type: " + ", ".join(f"{k} {v}" for k, v in sorted(s["by_type"].items())))
    _meetings_table(s["meetings"])


def _edit(principal: Principal) -> None:
    a = _get()
    if a:
        FT.update_assignment(a.assignment_id, _details(a), actor=principal)
        print("\n  Saved.")


def _end(principal: Principal) -> None:
    a = _get()
    if a and _yes(f"  End {a.tutor_name}'s assignment for {a.form_label}?"):
        d = _prompt("  End date (blank = today): ")
        FT.end_assignment(a.assignment_id, d or None, actor=principal)
        print("  Ended.")
    elif a:
        print("  Cancelled.")


def _delete(principal: Principal) -> None:
    a = _get()
    if a is None:
        return
    n = FT.meeting_count(a.assignment_id)
    if _yes(f"  Delete #{a.assignment_id}" + (f" and its {n} meeting(s)?" if n else "?")):
        FT.delete_assignment(a.assignment_id, actor=principal)
        print("  Deleted.")
    else:
        print("  Cancelled.")


# ── Meetings (old 7-10) ──────────────────────────────────────────────

def _meeting_data(m: FT.TutorMeeting | None, a: FT.TutorAssignment) -> dict:
    data: dict = {}
    g = (lambda k: getattr(m, k) if m else None)
    v = _prompt("  Date (YYYY-MM-DD, blank = " + (m.meeting_date if m else "today") + "): ")
    if v:
        data["meeting_date"] = v
    data["meeting_type"] = _pick("Type", FT.MEETING_TYPES,
                                 g("meeting_type") or FT.DEFAULT_MEETING_TYPE)
    refs = _prompt("  About pupils (admission numbers in the form, blank = "
                   + ("keep" if m else "none") + "): ")
    if refs:
        data["pupils"] = refs.replace(",", " ").split()
    for key, label in (("pupils_present", "Pupils present"), ("agenda", "Agenda"),
                       ("decisions", "Decisions"), ("follow_up_actions", "Follow-up actions"),
                       ("follow_up_due", "Follow-up due (YYYY-MM-DD)"), ("notes", "Notes")):
        cur = g(key)
        v = _prompt(f"  {label}" + (f" [{cur[:30]}]" if cur else "") + ": ")
        if v:
            data[key] = "" if v == "-" else v
    return data


def _log(principal: Principal) -> None:
    a = _get()
    if a:
        m = FT.add_meeting(a.assignment_id, _meeting_data(None, a), actor=principal)
        print(f"\n  Logged meeting #{m.meeting_id}.")


def _list_meetings(principal: Principal) -> None:
    aid = _int("  Assignment ID (blank = all I can see): ")
    t = _prompt("  Type (blank = all): ")
    _meetings_table(FT.list_meetings(actor=principal, assignment_id=aid,
                                     meeting_type=t or None,
                                     date_from=_prompt("  From (YYYY-MM-DD): ") or None,
                                     date_to=_prompt("  To (YYYY-MM-DD): ") or None))


def _meeting() -> FT.TutorMeeting | None:
    mid = _int("  Meeting ID: ")
    try:
        return FT.get_meeting(mid) if mid is not None else None
    except FT.NotFound:
        print("  No meeting with that ID.")
        return None


def _edit_meeting(principal: Principal) -> None:
    m = _meeting()
    if m:
        FT.update_meeting(m.meeting_id, _meeting_data(m, FT.get_assignment(m.assignment_id)),
                          actor=principal)
        print("\n  Saved.")


def _delete_meeting(principal: Principal) -> None:
    m = _meeting()
    if m and _yes(f"  Delete meeting #{m.meeting_id}?"):
        FT.delete_meeting(m.meeting_id, actor=principal)
        print("  Deleted.")
    elif m:
        print("  Cancelled.")


# ── Reports (old 11) ─────────────────────────────────────────────────

def _cohort(_p: Principal) -> None:
    ay = _prompt(f"  Academic year [{FT.current_year()}, '-' = all]: ")
    s = FT.cohort_summary(academic_year=None if ay == "-" else ay or FT.current_year())
    print(f"\n  {s['total']} assignment(s), {s['tutors']} tutor(s), {s['forms']} form(s)")
    print("  By status: " + ", ".join(f"{k} {v}" for k, v in sorted(s["by_status"].items())))
    print("  By role:   " + ", ".join(f"{k} {v}" for k, v in sorted(s["by_role"].items())))
    print("  By year:")
    for k, v in sorted(s["by_year"].items()):
        print(f"    Year {k}: {v}")


# ── New ──────────────────────────────────────────────────────────────

def _my_form(principal: Principal) -> None:
    forms = FT.my_forms(principal)
    if not forms:
        print("  You aren't the tutor of a form this year.")
        return
    for i, f in enumerate(forms, 1):
        print(f"    {i}) {f.label}")
    v = _prompt("  Form [1]: ") or "1"
    if not v.isdigit() or not 1 <= int(v) <= len(forms):
        return
    ov = FT.form_overview(forms[int(v) - 1].form_id, actor=principal)
    print(f"\n  {ov['form'].label} - " + (", ".join(f"{a.role} {a.tutor_name}"
                                                  for a in ov["tutors"]) or "no tutor"))
    print(f"  {'Pupil':<32} {'Att %':>6} {'Absence':<10} {'Late':>4} {'Int':>3} "
          f"{'Last 1-to-1':<11} E-mail")
    for r in ov["pupils"]:
        p = r["pupil"]
        print(f"  {(p.admission_no + ' ' + p.display_name)[:32]:<32} "
              f"{'-' if r['attendance_pct'] is None else r['attendance_pct']:>6} "
              f"{r['band']:<10} {r['late']:>4} {r['interventions'] or '':>3} "
              f"{r['last_contact'] or 'never':<11} {'yes' if r['email_contact'] else 'none'}")
    print(f"\n  {len(ov['no_contact_this_term'])} pupil(s) not seen 1-to-1 this term.")


def _follow_ups(principal: Principal) -> None:
    rows = FT.follow_ups(actor=principal)
    if not rows:
        print("  No open follow-ups.")
    for m in rows:
        print(f"  {m.meeting_id:<5} {'OVERDUE ' if FT.overdue(m) else ''}"
              f"due {m.follow_up_due or '-':<11} {m.form_group:<6} "
              f"{(m.follow_up_actions or '')[:60]}")


def _done(principal: Principal) -> None:
    m = _meeting()
    if m:
        FT.complete_follow_up(m.meeting_id, actor=principal, undo=bool(m.follow_up_done_at))
        print("  Reopened." if m.follow_up_done_at else "  Marked done.")


def _coverage(_p: Principal) -> None:
    cv = FT.coverage()
    print(f"\n  {cv['academic_year']}")
    for f in cv["no_tutor"]:
        print(f"  No active tutor: {f.label}")
    for name, forms in cv["several_forms"].items():
        print(f"  {name} tutors {', '.join(forms)}")
    for a in cv["archived_forms"]:
        print(f"  {a.form_label} is archived but {a.tutor_name} is still active")
    for x in FT.mismatches():
        print(f"  {x['form'].label} {x['role']}: form says {x['on_form'] or '-'}, "
              f"assignment says {x['assigned'] or '-'}")
    if not (cv["no_tutor"] or cv["several_forms"] or cv["archived_forms"]):
        print("  Every form has a tutor.")


def _import(principal: Principal) -> None:
    r = FT.import_from_forms(actor=principal)
    print(f"  Created {r['created']} assignment(s) from the form groups"
          + (f"; {r['skipped']} skipped." if r["skipped"] else "."))


def _carry(principal: Principal) -> None:
    frm = _prompt(f"  From academic year [{FT.current_year()}]: ") or FT.current_year()
    if not _yes(f"  Copy {frm}'s active assignments to {FT.next_year(frm)} and end the old "
                "ones?"):
        return
    r = FT.carry_forward(actor=principal, from_year=frm)
    print(f"  Copied {r['copied']} to {r['to_year']}.")
    for s in r["skipped"]:
        print(f"   skipped {s}")


def _export(principal: Principal) -> None:
    path = _prompt("  Save to (path, .csv): ")
    if not path:
        return
    try:
        print(f"  Exported {FT.export_csv(path, actor=principal)} assignment(s).")
    except OSError as e:
        print(f"  Couldn't write the file: {e.strerror or e}")


_OPTIONS = {"1": _new, "2": _list, "3": _view, "4": _edit, "5": _end, "6": _delete,
            "7": _log, "8": _list_meetings, "9": _edit_meeting, "10": _delete_meeting,
            "11": _cohort, "12": _my_form, "13": _follow_ups, "14": _done, "15": _coverage,
            "16": _import, "17": _carry, "18": _export}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("form_tutors.view")
        print("\n  ── Form Tutors ──")
        print("  Assignments")
        print("    1) New assignment\n    2) List assignments\n    3) View assignment + "
              "meetings\n    4) Edit assignment\n    5) End assignment\n    6) Delete "
              "assignment")
        print("  Meetings")
        print("    7) Log meeting\n    8) List meetings (filters)\n    9) Edit meeting"
              "\n   10) Delete meeting")
        print("  Reports")
        print("   11) Cohort summary")
        print("  My form & more")
        print("   12) My form\n   13) Follow-ups\n   14) Mark follow-up done / reopen"
              "\n   15) Coverage\n   16) Take tutors from form groups"
              "\n   17) Carry forward to next year\n   18) Export CSV")
        print("    0) Back")
        choice = _prompt("Select: ")
        if choice in ("0", ""):
            return
        fn = _OPTIONS.get(choice)
        if fn is None:
            print("  Invalid selection.")
            continue
        try:
            fn(principal)
        except _ERRORS as e:
            _problem(e)
        _pause()
