"""Interventions in the terminal.

The old Intervention Tracking menu keeps its options in place:
Interventions 1 New, 2 List, 3 View + reviews, 4 Edit, 5 Set status (with
outcome), 6 Delete; Reviews 7 Add review, 8 Delete review; Reports 9 Cohort
summary. New: 10 Register session, 11 Group register, 12 Delete session,
13 Group intervention, 14 Refresh grade, 15 Who needs one?, 16 Due for
review, 17 Impact, 18 Export CSV, 19 History. Rules live in
:mod:`modules.assessment.domain.interventions`.
"""

from __future__ import annotations

from education_system.systems.secondary.modules.assessment.domain import interventions as IV
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (IV.ValidationError, IV.PermissionDenied, IV.NotFound)


_problem = prompts.problem
_int = prompts.ask_int
_pick = prompts.pick


def _get() -> IV.Intervention | None:
    iid = _int("  Intervention ID: ")
    if iid is None:
        print("  Enter the intervention's ID number.")
        return None
    try:
        return IV.get(iid)
    except IV.NotFound as e:
        print(f"  {e}")
        return None


def _table(rows: list[IV.Intervention]) -> None:
    if not rows:
        print("  (no interventions)")
        return
    print(f"  {'ID':<5} {'Pupil':<10} {'Name':<20} {'Yr':<3} {'Subj':<6} {'Type':<16} "
          f"{'Start':<11} {'Led by':<16} {'Freq':<12} {'Status':<10} Outcome")
    for r in rows:
        print(f"  {r.intervention_id:<5} {r.admission_no:<10} {r.pupil_name[:20]:<20} "
              f"{r.pupil_year:<3} {(r.subject_code or '-'):<6} {r.intervention_type:<16} "
              f"{r.start_date:<11} {(r.led_by or '-')[:16]:<16} {r.frequency:<12} "
              f"{r.status:<10} {r.outcome or ''}")


def _details(existing: IV.Intervention | None) -> dict:
    """Prompt for the fields; blank keeps the current value (or the default)."""
    g = (lambda k: getattr(existing, k) if existing else None)

    def ask(key: str, label: str) -> None:
        cur = g(key)
        v = _prompt(f"  {label}" + (f" [{cur}]" if cur else "") + ": ")
        if v:
            data[key] = "" if v == "-" else v

    data: dict = {}
    if existing:
        print("  (Enter keeps the current value, '-' clears it.)")
    cur = existing.subject_code if existing else None
    v = _prompt("  Subject code" + (f" [{cur}]" if cur else " (blank = none)") + ": ")
    if v:
        data["subject"] = "" if v == "-" else v
    t = _pick("Type", IV.INTERVENTION_TYPES, g("intervention_type") or IV.DEFAULT_TYPE)
    data["intervention_type"] = t
    for key, label in (("programme", "Programme / group"), ("reason", "Reason"),
                       ("start_date", "Start date (YYYY-MM-DD, blank = today)"
                        if not existing else "Start date"),
                       ("end_date", "End date"), ("led_by", "Led by (username or name)"),
                       ("location", "Location")):
        ask(key, label)
    data["frequency"] = _pick("Frequency", IV.FREQUENCIES,
                              g("frequency") or IV.DEFAULT_FREQUENCY)
    if not existing:
        data["status"] = _pick("Status", ("Planned", "Active"), "Planned")
    print("  (Leave grades blank to fill them from the target and newest grade.)")
    for key, label in (("baseline_grade", "Baseline grade"), ("target_grade", "Target grade"),
                       ("current_grade", "Current grade"), ("goal", "Goal"),
                       ("notes", "Notes")):
        ask(key, label)
    if existing and "subject" in data and data["subject"] == "":
        data["subject_id"] = None
    return data


# ── Interventions (old 1-6) ──────────────────────────────────────────

def _new(principal: Principal) -> None:
    ref = _prompt("  Pupil (admission number or UPN): ")
    if not ref:
        return
    data = _details(None)
    iv = IV.create({**data, "pupil": ref}, actor=principal)
    print(f"\n  Started intervention #{iv.intervention_id} for {iv.pupil_name}"
          + (f" (baseline {iv.baseline_grade}, target {iv.target_grade})"
             if iv.baseline_grade or iv.target_grade else "") + ".")


def _list(principal: Principal) -> None:
    y = _prompt("  Year (7-11, blank = all): ")
    st = _prompt("  Status (blank = all): ")
    ty = _prompt("  Type (blank = all): ")
    mine = _yes("  Only the ones I lead?")
    _table(IV.list_interventions(year_group=int(y) if y.isdigit() else None,
                                 status=st.capitalize() or None,
                                 intervention_type=ty or None,
                                 lead=principal.username if mine else None))


def _view(_principal: Principal) -> None:
    iv = _get()
    if iv is None:
        return
    s = IV.intervention_summary(iv.intervention_id)
    print(f"\n  #{iv.intervention_id}  {iv.admission_no} {iv.pupil_name} (Y{iv.pupil_year})")
    print(f"  {iv.intervention_type}" + (f" in {iv.subject_name}" if iv.subject_name else "")
          + (f" · {iv.programme}" if iv.programme else ""))
    print(f"  Status {iv.status}" + (f" · outcome {iv.outcome}" if iv.outcome else ""))
    print(f"  {iv.start_date} → {iv.end_date or 'ongoing'} · {iv.frequency} · led by "
          f"{iv.led_by or '-'}" + (f" · {iv.location}" if iv.location else ""))
    if iv.reason:
        print(f"  Reason: {iv.reason}")
    if iv.goal:
        print(f"  Goal: {iv.goal}")
    if iv.subject_id:
        ch = s["grade_change"]
        print(f"  Grades: baseline {iv.baseline_grade or '-'}, current "
              f"{iv.current_grade or '-'}, target {iv.target_grade or '-'}"
              + (f" (change {ch:+g})" if ch is not None else ""))
    a = s["sessions"]
    print(f"  Sessions: {a['ran']} run, {a['Present']} present, {a['Late']} late, "
          f"{a['Absent']} absent" + (f" - {a['pct']}%" if a["pct"] is not None else ""))
    print(f"  Reviews: {s['review_count']} ({s['on_track']} on track, {s['off_track']} off)"
          + (f", average attendance {s['avg_attendance']}%"
             if s["avg_attendance"] is not None else ""))
    for rv in s["reviews"]:
        print(f"   [{rv.review_id}] {rv.review_date} {rv.reviewer or '-'} "
              f"att {'-' if rv.attendance_pct is None else f'{rv.attendance_pct:g}%'} "
              f"{'on track' if rv.on_track else 'OFF TRACK'}"
              + (f" - {rv.progress_notes}" if rv.progress_notes else "")
              + (f" → {rv.next_action}" if rv.next_action else ""))
    if iv.notes:
        print(f"  Notes: {iv.notes}")


def _edit(principal: Principal) -> None:
    iv = _get()
    if iv is None:
        return
    data = _details(iv)
    if iv.status in IV.CLOSED_STATUSES:
        o = _pick("Outcome", IV.OUTCOMES, iv.outcome)
        data["outcome"] = o
    IV.update(iv.intervention_id, data, actor=principal)
    print("\n  Saved.")


def _status(principal: Principal) -> None:
    iv = _get()
    if iv is None:
        return
    moves = tuple(sorted(IV.MOVES[iv.status], key=IV.INTERVENTION_STATUSES.index))
    print(f"  Currently {iv.status}.")
    st = _pick("New status", moves)
    if not st:
        return
    out = None
    if st in IV.CLOSED_STATUSES:
        out = _pick("Outcome (required)", IV.OUTCOMES)
    note = _prompt("  Note (optional): ")
    new = IV.set_status(iv.intervention_id, st, actor=principal, outcome=out,
                        notes=note or None)
    print(f"\n  Now {new.status}" + (f" ({new.outcome})" if new.outcome else "")
          + (f", current grade {new.current_grade}" if new.current_grade else "") + ".")


def _delete(principal: Principal) -> None:
    iv = _get()
    if iv is None:
        return
    if _yes(f"  Delete #{iv.intervention_id} for {iv.pupil_name} with its reviews and "
            f"sessions?"):
        IV.delete(iv.intervention_id, actor=principal,
                  reason=_prompt("  Reason (optional): ") or None)
        print("  Deleted.")


# ── Reviews (old 7-8) ────────────────────────────────────────────────

def _add_review(principal: Principal) -> None:
    iv = _get()
    if iv is None:
        return
    data = {"review_date": _prompt("  Review date (blank = today): "),
            "reviewer": _prompt(f"  Reviewer [{principal.username}]: "),
            "attendance_pct": _prompt("  Attendance % (blank = from sessions): "),
            "on_track": _yes("  On track?"),
            "progress_notes": _prompt("  Progress notes: "),
            "next_action": _prompt("  Next action: ")}
    rv = IV.add_review(iv.intervention_id, data, actor=principal)
    print(f"\n  Review {rv.review_id} added"
          + (f" (attendance {rv.attendance_pct:g}%)" if rv.attendance_pct is not None else "")
          + ".")


def _delete_review(principal: Principal) -> None:
    rid = _int("  Review ID: ")
    if rid is None:
        print("  Enter the review's ID number.")
        return
    if _yes("  Delete that review?"):
        IV.delete_review(rid, actor=principal)
        print("  Deleted.")


# ── Reports (old 9) ──────────────────────────────────────────────────

def _cohort(_principal: Principal) -> None:
    y = _prompt("  Year (7-11, blank = all): ")
    s = IV.cohort_summary(year_group=int(y) if y.isdigit() else None)
    print(f"\n  {s['total']} intervention(s), {s['open']} open, {s['pupils']} pupil(s)")
    for title, key in (("By status", "by_status"), ("By type", "by_type"),
                       ("By outcome", "by_outcome")):
        print(f"  {title}:")
        for k, v in sorted(s[key].items()):
            print(f"    {k:<18} {v}")
        if not s[key]:
            print("    -")


# ── New ──────────────────────────────────────────────────────────────

def _session(principal: Principal) -> None:
    iv = _get()
    if iv is None:
        return
    for s in IV.sessions(iv.intervention_id)[:10]:
        print(f"   [{s.session_id}] {s.session_date} {s.attendance}"
              + (f" - {s.notes}" if s.notes else ""))
    data = {"session_date": _prompt("  Date (blank = today): "),
            "attendance": _pick("Attendance", IV.ATTENDANCE, "Present"),
            "notes": _prompt("  Notes: ")}
    IV.record_session(iv.intervention_id, data, actor=principal)
    a = IV.session_attendance(iv.intervention_id)
    print(f"\n  Registered. {a['ran']} session(s) run"
          + (f", {a['pct']}% attendance" if a["pct"] is not None else "") + ".")


def _group_register(principal: Principal) -> None:
    progs = IV.programmes()
    if not progs:
        print("  No intervention has a programme / group name yet.")
        return
    prog = _pick("Group", tuple(progs))
    if prog not in progs:
        print("  Not a group.")
        return
    day = _prompt("  Date (blank = today): ") or IV._today().isoformat()
    marks = {}
    for iv in IV.list_interventions(programme=prog, status="Active"):
        v = _prompt(f"  {iv.admission_no} {iv.pupil_name[:24]:<24} P/L/A/C/skip [P]: ").upper()
        marks[iv.intervention_id] = {"": "Present", "P": "Present", "L": "Late",
                                     "A": "Absent", "C": "Cancelled"}.get(v, "")
    if not marks:
        print("  No active interventions in that group.")
        return
    n = IV.register_programme(prog, day, marks, actor=principal)
    print(f"\n  Registered {n} pupil(s).")


def _delete_session(principal: Principal) -> None:
    sid = _int("  Session ID: ")
    if sid is not None and _yes("  Delete that session?"):
        IV.delete_session(sid, actor=principal)
        print("  Deleted.")


def _group(principal: Principal) -> None:
    refs = _prompt("  Pupils (admission numbers, separated by spaces or commas): ")
    ids, missing = [], []
    for ref in refs.replace(",", " ").split():
        p = P.find_by_reference(ref)
        (ids.append(p.pupil_id) if p else missing.append(ref))
    if missing:
        print("  Not found: " + ", ".join(missing))
        return
    if not ids:
        return
    res = IV.create_many(ids, _details(None), actor=principal)
    print(f"\n  Started {len(res['created'])} intervention(s).")
    for k, why in res["skipped"].items():
        print(f"   skipped {k}: {why}")


def _refresh_grade(principal: Principal) -> None:
    iv = _get()
    if iv is None:
        return
    new = IV.refresh_grade(iv.intervention_id, actor=principal)
    print(f"\n  Current grade {new.current_grade}"
          + (f" (target {new.target_grade})" if new.target_grade else "") + ".")


def _suggest(_principal: Principal) -> None:
    y = _prompt("  Year (7-11, blank = all): ")
    rows = IV.suggestions(year_group=int(y) if y.isdigit() else None)
    if not rows:
        print("  No suggestions - nobody flagged who isn't already in an intervention.")
        return
    for s in rows:
        p = s["pupil"]
        print(f"  {'!' if s['severity'] > 1 else ' '} {p.admission_no:<10} "
              f"{p.display_name[:22]:<22} Y{p.year_group:<3} {s['type']:<11} {s['reason']}")


def _due(principal: Principal) -> None:
    d = _int("  No review for how many days? [28]: ") or 28
    rows = IV.due_for_review(days=d, lead=principal.username
                             if _yes("  Only the ones I lead?") else None)
    if not rows:
        print("  None due.")
    for r in rows:
        iv = r["intervention"]
        print(f"  {iv.intervention_id:<5} {iv.admission_no:<10} {iv.pupil_name[:20]:<20} "
              f"{iv.intervention_type:<16} last review {r['last_review'] or 'never'}")


def _impact(_principal: Principal) -> None:
    by = _pick("Group by", ("type", "subject", "programme"), "type")
    if by not in ("type", "subject", "programme"):
        by = "type"
    rows = IV.impact(by=by)
    if not rows:
        print("  (no interventions)")
        return
    print(f"  {'Group':<22} {'Count':>5} {'Open':>5} {'Done':>5} {'Succ':>5} {'Succ%':>6} "
          f"{'Grade chg':>10} {'Att%':>6}")
    for r in rows:
        chg = "-" if r["avg_grade_change"] is None else format(r["avg_grade_change"], "+g")
        print(f"  {r['group'][:22]:<22} {r['count']:>5} {r['open']:>5} {r['complete']:>5} "
              f"{r['successful']:>5} {'-' if r['success_pct'] is None else r['success_pct']:>6}"
              f" {chg:>10}"
              f" {'-' if r['attendance_pct'] is None else r['attendance_pct']:>6}")


def _export(principal: Principal) -> None:
    path = _prompt("  Save to (path, .csv): ")
    if not path:
        return
    try:
        n = IV.export_csv(path, actor=principal)
    except OSError as e:
        print(f"  Couldn't write the file: {e.strerror or e}")
        return
    print(f"  Exported {n} intervention(s).")


def _history(_principal: Principal) -> None:
    iv = _get()
    if iv is None:
        return
    for h in IV.history(iv.intervention_id):
        print(f"  {h['at']}  {h['actor']:<14} {h['action']:<14} "
              + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))


_OPTIONS = {"1": _new, "2": _list, "3": _view, "4": _edit, "5": _status, "6": _delete,
            "7": _add_review, "8": _delete_review, "9": _cohort, "10": _session,
            "11": _group_register, "12": _delete_session, "13": _group,
            "14": _refresh_grade, "15": _suggest, "16": _due, "17": _impact,
            "18": _export, "19": _history}


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("interventions.view")
        print("\n── Intervention Tracking ──")
        print("  Interventions\n   1) New\n   2) List\n   3) View + reviews\n   4) Edit"
              "\n   5) Set status (with outcome)\n   6) Delete")
        print("  Reviews\n   7) Add review\n   8) Delete review")
        print("  Reports\n   9) Cohort summary")
        print("  Sessions & groups\n  10) Register session\n  11) Group register"
              "\n  12) Delete session\n  13) Group intervention\n  14) Refresh grade")
        print("  More\n  15) Who needs one?\n  16) Due for review\n  17) Impact"
              "\n  18) Export CSV\n  19) History\n   0) Back")
        choice = _prompt("Select: ")
        if choice in ("0", ""):
            return
        fn = _OPTIONS.get(choice)
        if fn is None:
            continue
        try:
            fn(principal)
        except _ERRORS as e:
            _problem(e)
        _pause()
