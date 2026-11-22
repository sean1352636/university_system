"""Exam results in the terminal. The old Results Day options 1-7 are kept
(record / update, list, view, pupil sheet, cohort summary, pending entries,
delete); 8-24 are added (results file import, grade sheet, release and
embargo, reviews of marking, analysis, export, results slips, history) and S
chooses the exam series. Rules live in :mod:`modules.examinations.domain.exam_results`."""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.examinations.domain import exam_entries as EE
from education_system.systems.secondary.modules.examinations.domain import exam_results as ER
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (ER.ValidationError, ER.PermissionDenied, ER.NotFound)
_state: dict[str, Any] = {"series_id": None}


_problem = prompts.problem
_int = prompts.to_int


def _num(v: float | None) -> str:
    return f"{v:g}" if v is not None else "-"


def _pct(v: float | None) -> str:
    return f"{v:g}%" if v is not None else "-"


def _series(required: bool = True) -> EE.ExamSeries | None:
    sid = _state.get("series_id")
    if sid is None:
        cur = EE.current_series()
        sid = cur.series_id if cur else None
    try:
        s = EE.get_series(sid) if sid else None
    except EE.NotFound:
        s = None
    if s is None and required:
        print("  No exam series yet - add one in Exam Entries.")
    return s


def _choose_series() -> None:
    rows = EE.list_series()
    if not rows:
        print("  No exam series yet - add one in Exam Entries.")
        return
    print(f"\n  {'ID':<4} {'Name':<18} {'Status':<9} Results")
    for s in rows:
        rel = ER.released(s.series_id)
        print(f"  {s.series_id:<4} {s.name[:18]:<18} {s.status:<9} "
              + (f"released {rel['at'][:10]}" if rel else "embargoed"))
    sid = _int(_prompt("  Series ID: "))
    if sid is not None:
        _state["series_id"] = EE.get_series(sid).series_id


def _pupil(prompt: str = "  Pupil (admission number or UPN): ") -> P.Pupil | None:
    ref = _prompt(prompt)
    if not ref:
        return None
    p = P.find_by_reference(ref) or (P.get_pupil(int(ref)) if ref.isdigit() else None)
    if p is None:
        print("  No pupil with that reference.")
    return p


def _result() -> ER.ExamResult | None:
    rid = _int(_prompt("  Result ID: "))
    if rid is None:
        return None
    r = ER.get(rid)
    if r is None:
        print("  No result with that ID.")
    return r


def _print_table(rows: list[ER.ExamResult]) -> None:
    if not rows:
        print("  (no results)")
        return
    print(f"  {'ID':<5} {'Entry':<6} {'Pupil':<10} {'Name':<20} {'Yr':<3} {'Subj':<6} "
          f"{'Board':<8} {'Tier':<10} {'Grade':<5} {'Marks':<6} {'UMS':<5} {'Status':<10}")
    print(f"  {'-'*5} {'-'*6} {'-'*10} {'-'*20} {'-'*3} {'-'*6} {'-'*8} {'-'*10} "
          f"{'-'*5} {'-'*6} {'-'*5} {'-'*10}")
    for r in rows:
        print(f"  {r.result_id:<5} {r.entry_id:<6} {r.admission_no[:10]:<10} "
              f"{(r.pupil_name or '')[:20]:<20} {r.pupil_year or '-'!s:<3} "
              f"{(r.subject_code or '?')[:6]:<6} {(r.exam_board or '-')[:8]:<8} "
              f"{(r.tier or '-')[:10]:<10} {(r.final_grade or '-'):<5} "
              f"{_num(r.marks_awarded):<6} {_num(r.ums):<5} {r.status:<10}")


def _embargo_note(principal: Principal, s: EE.ExamSeries | None) -> None:
    if s and ER.released(s.series_id) is None:
        print("  (Embargoed: only the exams officer sees these until they are released.)"
              if ER.is_editor(principal) else
              "  These results are under embargo until they are released.")


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("exam.results.view")
        s = _series(required=False)
        rel = ER.released(s.series_id) if s else None
        print("\n── Results Day ──")
        print(f"  Series: {s.name} · " + (f"released {rel['at'][:16]}" if rel
                                          else "under embargo") if s else "  Series: none yet")
        print("   1) Record / update result for entry\n   2) List results\n   3) View result"
              "\n   4) Pupil results sheet\n   5) Cohort summary"
              "\n   6) Pending entries (no result yet)\n   7) Delete result"
              "\n   8) Import the board's results file (CSV)\n   9) Grade sheet for a subject"
              "\n  10) Release results / put back under embargo"
              "\n  11) Request a review of marking\n  12) Mark a review sent to the board"
              "\n  13) Record a review outcome\n  14) Cancel a review\n  15) List reviews"
              "\n  16) Headlines\n  17) Subject analysis\n  18) Pupils against target"
              "\n  19) Export results (CSV)\n  20) Preview a results slip"
              "\n  21) E-mail results slips\n  22) Series history\n  23) Result history"
              "\n   S) Choose the exam series\n   0) Back")
        choice = _prompt("Select: ").lower()
        if choice in {"0", ""}:
            return
        try:
            {"1": lambda: _upsert(principal), "2": lambda: _list(principal),
             "3": lambda: _view(principal), "4": lambda: _pupil_sheet(principal),
             "5": lambda: _summary(principal), "6": _pending,
             "7": lambda: _delete(principal), "8": lambda: _import(principal),
             "9": lambda: _sheet(principal), "10": lambda: _release(principal),
             "11": lambda: _request_review(principal),
             "12": lambda: _submitted(principal), "13": lambda: _outcome(principal),
             "14": lambda: _cancel(principal), "15": lambda: _reviews(principal),
             "16": lambda: _headlines(principal), "17": lambda: _analysis(principal),
             "18": lambda: _vs_target(principal), "19": lambda: _export(principal),
             "20": lambda: _preview(principal), "21": lambda: _slips(principal),
             "22": lambda: _series_history(principal),
             "23": lambda: _result_history(principal), "s": _choose_series,
             }.get(choice, lambda: print("  Invalid selection."))()
        except _ERRORS as e:
            _problem(e)


def _need_editor(principal: Principal) -> None:
    if not ER.is_editor(principal):
        raise ER.PermissionDenied("Only the exams officer can do that.")


def _visible(principal: Principal, r: ER.ExamResult) -> bool:
    if ER.can_see(principal, r.series_id):
        return True
    print("  That result is under embargo until it is released.")
    return False


# ── The old options ──────────────────────────────────────────────────

def _upsert(principal: Principal) -> None:
    _need_editor(principal)
    print("\n  ── Record / Update Result ──")
    eid = _int(_prompt("  Entry ID: "))
    if eid is None:
        return
    entry = EE.get(eid)
    if entry is None:
        print("  No exam entry with that ID.")
        return
    cur = ER.get_for_entry(eid)
    print(f"  Entry: {entry.admission_no} {entry.pupil_name} / {entry.subject_code} "
          f"({entry.exam_board} {entry.tier}) - {entry.entry_status}")
    if cur and cur.status == "Remarked" and ER.open_review(cur.result_id):
        print("  A review is open - record its outcome with option 13.")
        return
    grades = "/".join(ER.GCSE_GRADES) if entry.qualification in ER.GCSE_QUALS else "board grade"
    data: dict[str, Any] = {"entry_id": eid}
    data["final_grade"] = _ask("Final grade", cur.final_grade if cur else None, hint=grades)
    data["marks_awarded"] = _ask("Marks awarded", _num(cur.marks_awarded) if cur and
                                 cur.marks_awarded is not None else None, hint="blank ok")
    data["max_marks"] = _ask("Out of", _num(cur.max_marks) if cur and
                             cur.max_marks is not None else None, hint="blank ok")
    data["ums"] = _ask("UMS", _num(cur.ums) if cur and cur.ums is not None else None,
                       hint="blank ok")
    data["result_date"] = _ask("Result date", cur.result_date if cur else None,
                               hint="YYYY-MM-DD, blank = today")
    data["status"] = _ask("Status", cur.status if cur else None,
                          hint="/".join(ER.RESULT_STATUSES) + ", blank = follow the grade")
    data["remark_outcome"] = _ask("Remark outcome", cur.remark_outcome if cur else None,
                                  hint="blank ok")
    data["notes"] = _ask("Notes", cur.notes if cur else None)
    r = ER.upsert(data, actor=principal)
    print(f"  ✓ Saved result #{r.result_id}: grade={r.final_grade or '-'} status={r.status}")


def _list(principal: Principal) -> None:
    s = _series(required=False)
    yg = _prompt(f"  Year ({'/'.join(map(str, P.YEAR_GROUPS))}, blank = all): ") or None
    st = _prompt(f"  Status ({'/'.join(ER.RESULT_STATUSES)}, blank = all): ") or None
    status = next((x for x in ER.RESULT_STATUSES if st and x.lower() == st.lower()), st)
    rows = ER.list_results(series_id=s.series_id if s else None, year_group=yg,
                           status=status, actor=principal)
    _print_table(rows)
    _embargo_note(principal, s)
    _pause()


def _view(principal: Principal) -> None:
    r = _result()
    if r is None or not _visible(principal, r):
        return
    print(f"\n  Result #{r.result_id} - {r.pupil_name} ({r.admission_no}), Year "
          f"{r.pupil_year or '-'}")
    for label, value in (
            ("Series", r.series_name), ("Entry", f"#{r.entry_id} {r.entry_code or ''}"),
            ("Subject", f"{r.subject_name} ({r.qualification}, {r.exam_board} "
                        f"{r.spec_code})"), ("Tier", r.tier),
            ("Candidate number", r.candidate_number), ("Final grade", r.final_grade),
            ("Original grade", r.original_grade),
            ("Marks", f"{_num(r.marks_awarded)} / {_num(r.max_marks)}"), ("UMS", _num(r.ums)),
            ("Result date", r.result_date), ("Status", r.status),
            ("Remark outcome", r.remark_outcome), ("Notes", r.notes),
            ("Entered by", r.entered_by), ("Updated", r.updated_at)):
        print(f"  {label + ':':<18} {value if value not in (None, '') else '-'}")
    for v in ER.reviews(r.result_id):
        print(f"  Review #{v.review_id}: {v.service} - {v.status}"
              + (f", {v.outcome} ({v.grade_before} -> {v.grade_after})" if v.outcome else ""))
    _pause()


def _pupil_sheet(principal: Principal) -> None:
    p = _pupil()
    if p is None:
        return
    s = _series(required=False)
    d = ER.pupil_results(p.pupil_id, actor=principal)
    print(f"\n  ── Results for {p.display_name} ({p.admission_no}) ──")
    _print_table(d["results"])
    print(f"\n  Graded: {d['graded']}   Grade 4+: {d['passes']}   "
          f"Grade 5+: {d['strong_passes']}")
    if s and s.series_id not in {r.series_id for r in d["results"]}:
        _embargo_note(principal, s)
    _pause()


def _summary(principal: Principal) -> None:
    s = _series(required=False)
    yg = _prompt(f"  Year ({'/'.join(map(str, P.YEAR_GROUPS))}, blank = all): ") or None
    sid = s.series_id if s else None
    if sid is not None and not ER.can_see(principal, sid):
        print("  These results are under embargo until they are released.")
        return
    d = ER.cohort_summary(year_group=yg, series_id=sid, actor=principal)
    print(f"\n  ── Cohort Summary{' - ' + s.name if s else ''} ──")
    print(f"  Results: {d['total']}   Graded: {d['graded']}   Pending entries: "
          f"{d['pending']}   Open reviews: {d['reviews_open']}")
    print(f"  Grade 4+: {_pct(d['pass_rate_pct'])}   Grade 5+: {_pct(d['strong_pass_pct'])}")
    print("  By status: " + (", ".join(f"{k} {v}" for k, v in d["by_status"].items()) or "-"))
    print("  By grade:  " + (", ".join(f"{k}: {v}" for k, v in sorted(
        d["by_grade"].items(), key=lambda kv: -(ER.grade_value(kv[0]) or -1))) or "-"))
    _pause()


def _pending() -> None:
    s = _series(required=False)
    yg = _prompt(f"  Year ({'/'.join(map(str, P.YEAR_GROUPS))}, blank = all): ") or None
    rows = ER.list_pending_for_entries(yg, series_id=s.series_id if s else None)
    if not rows:
        print("  Every Final entry has a result.")
    else:
        print(f"\n  {'Entry':<6} {'Pupil':<10} {'Name':<22} {'Yr':<3} {'Subj':<6} "
              f"{'Board':<10} {'Tier':<10} Cand#")
        for e in rows:
            print(f"  {e.entry_id:<6} {e.admission_no[:10]:<10} {(e.pupil_name or '')[:22]:<22} "
                  f"{e.pupil_year or '-'!s:<3} {(e.subject_code or '?')[:6]:<6} "
                  f"{e.exam_board[:10]:<10} {e.tier[:10]:<10} {e.candidate_number or '-'}")
        print(f"\n  {len(rows)} entr{'y' if len(rows) == 1 else 'ies'} awaiting a result.")
    _pause()


def _delete(principal: Principal) -> None:
    _need_editor(principal)
    r = _result()
    if r is None:
        return
    if _yes(f"  Delete result #{r.result_id} ({r.pupil_name} {r.subject_code} "
            f"{r.final_grade or r.status})?"):
        print("  ✓ Deleted." if ER.delete(r.result_id, actor=principal) else "  Not found.")


# ── Results file, grade sheet, release ───────────────────────────────

def _import(principal: Principal) -> None:
    _need_editor(principal)
    s = _series()
    if s is None:
        return
    print("  Columns: Candidate number (or Admission no), Entry code (or Spec code), Grade;"
          "\n  optional Marks, Max marks, UMS, Status (e.g. Withheld). All rows or none.")
    path = _prompt("  CSV file: ")
    if not path:
        return
    try:
        c = ER.import_results(s.series_id, path, actor=principal)
    except OSError as e:
        print(f"  Couldn't read the file: {e}")
        return
    print(f"  ✓ {c.get('record', 0)} new, {c.get('change', 0)} changed, "
          f"{c.get('unchanged', 0)} unchanged")


def _sheet(principal: Principal) -> None:
    _need_editor(principal)
    s = _series()
    if s is None:
        return
    specs = sorted({(e.spec_id, e.subject_name, e.exam_board, e.spec_code)
                    for e in EE.list_entries(series_id=s.series_id, entry_status="Final")},
                   key=lambda t: (t[1] or "").lower())
    if not specs:
        print("  No Final entries in this series.")
        return
    for spec_id, name, board, code in specs:
        print(f"  {spec_id:<4} {(name or '')[:24]:<24} {board[:12]:<12} {code}")
    spec_id = _int(_prompt("  Specification ID: "))
    if spec_id is None:
        return
    entries = EE.list_entries(series_id=s.series_id, spec_id=spec_id, entry_status="Final")
    print("  Type each grade (blank = leave as it is, - = no grade yet).")
    rows: dict[int, dict[str, Any]] = {}
    for e in entries:
        cur = ER.get_for_entry(e.entry_id)
        if cur and cur.status == "Remarked" and ER.open_review(cur.result_id):
            print(f"  {e.pupil_name}: under review ({cur.final_grade}) - skipped")
            continue
        shown = f" [{cur.final_grade or cur.status}]" if cur else ""
        g = _prompt(f"  {e.candidate_number or '-':<6} {(e.pupil_name or '')[:24]:<24} "
                    f"{e.tier[:10]:<10}{shown}: ")
        if g == "-":
            rows[e.entry_id] = {"final_grade": "", "status": "Pending"}
        elif g:
            rows[e.entry_id] = {"final_grade": g}
    if rows:
        print(f"  ✓ {ER.save_sheet(s.series_id, rows, actor=principal)} result(s) saved")


def _release(principal: Principal) -> None:
    _need_editor(principal)
    s = _series()
    if s is None:
        return
    rel = ER.released(s.series_id)
    if rel:
        print(f"  Released {rel['at']} by {rel['by']}.")
        if _yes("  Put the results back under embargo?"):
            ER.release(s.series_id, actor=principal, on=False)
            print("  ✓ Under embargo again.")
    elif _yes(f"  Release the {s.name} results to staff and the portal?"):
        out = ER.release(s.series_id, actor=principal) or {}
        print("  ✓ Released.")
        sf = out.get("sixth_form")
        if sf and sf.get("failed"):
            print("  Couldn't pass them on to the sixth form just now - use Move to Sixth Form,"
                  " option 13.")
        elif sf and (sf["sent"] or sf["skipped"]):
            print(f"  Passed on to {len(sf['sent'])} sixth form application(s).")
            for k, v in sf["skipped"].items():
                print(f"    {k}: not passed on ({v})")


# ── Reviews of marking ───────────────────────────────────────────────

def _pick(options: tuple[str, ...], label: str) -> str | None:
    for i, o in enumerate(options, 1):
        print(f"   {i}) {o}")
    n = _int(_prompt(f"  {label}: "))
    return options[n - 1] if n and 1 <= n <= len(options) else None


def _review_id() -> ER.Review | None:
    vid = _int(_prompt("  Review ID: "))
    return ER.get_review(vid) if vid is not None else None


def _request_review(principal: Principal) -> None:
    _need_editor(principal)
    r = _result()
    if r is None:
        return
    print(f"  {r.pupil_name} {r.subject_code}: {r.final_grade} ({r.status})")
    service = _pick(ER.REVIEW_SERVICES, "Service")
    if service is None:
        return
    print("  The candidate must consent in writing: the grade can go down as well as up.")
    data = {"service": service,
            "consent_by": _ask("Consent given by", required=True),
            "consent_on": _ask("Consent date", hint="YYYY-MM-DD, blank = today"),
            "deadline": _ask("Board deadline", hint="YYYY-MM-DD, blank ok"),
            "fee": _ask("Fee", hint="blank ok"),
            "fee_payer": _ask("Fee payer", hint="/".join(EE.FEE_PAYERS) + ", blank = School"),
            "notes": _ask("Notes")}
    v = ER.request_review(r.result_id, data, actor=principal)
    print(f"  ✓ Review #{v.review_id} requested ({v.service})")


def _submitted(principal: Principal) -> None:
    _need_editor(principal)
    v = _review_id()
    if v:
        ER.mark_submitted(v.review_id, actor=principal)
        print("  ✓ Marked as sent to the board.")


def _outcome(principal: Principal) -> None:
    _need_editor(principal)
    v = _review_id()
    if v is None:
        return
    r = ER.get_result(v.result_id)
    print(f"  {r.pupil_name} {r.subject_code}: {v.service}, grade before {v.grade_before}")
    out = _pick(ER.REVIEW_OUTCOMES, "Outcome")
    if out is None:
        return
    grade = _ask("New grade") if out in ("Grade raised", "Grade lowered") else None
    marks = _ask("New marks", hint="blank ok")
    notes = _ask("Notes")
    v = ER.record_outcome(v.review_id, out, actor=principal, new_grade=grade, new_marks=marks,
                          notes=notes)
    print(f"  ✓ {v.outcome}: {v.grade_before} -> {v.grade_after}"
          + (" (fee refunded)" if v.refunded else ""))


def _cancel(principal: Principal) -> None:
    _need_editor(principal)
    v = _review_id()
    if v and _yes(f"  Cancel review #{v.review_id}?"):
        ER.cancel_review(v.review_id, actor=principal, reason=_ask("Reason"))
        print("  ✓ Cancelled.")


def _reviews(principal: Principal) -> None:
    s = _series()
    if s is None:
        return
    if not ER.can_see(principal, s.series_id):
        print("  These results are under embargo until they are released.")
        return
    rows = ER.reviews(series_id=s.series_id)
    if not rows:
        print("  No reviews of marking for this series.")
    else:
        print(f"\n  {'ID':<4} {'Res':<5} {'Pupil':<20} {'Subj':<6} {'Service':<26} "
              f"{'Status':<10} {'Deadline':<11} {'Before':<6} {'After':<6} Outcome")
        for v in rows:
            r = ER.get(v.result_id)
            print(f"  {v.review_id:<4} {v.result_id:<5} {(r.pupil_name if r else '')[:20]:<20} "
                  f"{((r.subject_code if r else '') or '')[:6]:<6} {v.service[:26]:<26} "
                  f"{v.status:<10} {v.deadline or '-':<11} {v.grade_before or '-':<6} "
                  f"{v.grade_after or '-':<6} {v.outcome or ''}")
    _pause()


# ── Analysis ─────────────────────────────────────────────────────────

def _headlines(principal: Principal) -> None:
    s = _series()
    if s is None:
        return
    h = ER.headlines(s.series_id, actor=principal)
    print(f"\n  ── Headlines - {s.name} ──")
    print(f"  Candidates: {h['candidates']}   Results: {h['results']}   Average grade: "
          f"{_num(h['average'])}   Grades 7+: {_pct(h['pct_7'])}")
    print(f"  English and maths 4+: {h['english_maths_4']} ({_pct(h['english_maths_4_pct'])})"
          f"   5+: {h['english_maths_5']} ({_pct(h['english_maths_5_pct'])})")
    t = h["vs_target"]
    print(f"  Against target: {t.get('above', 0)} above, {t.get('met', 0)} met, "
          f"{t.get('below', 0)} below")
    _pause()


def _signed(v: float | None) -> str:
    return f"{v:+g}" if v is not None else "-"


def _analysis(principal: Principal) -> None:
    s = _series()
    if s is None:
        return
    rows = ER.subject_analysis(s.series_id, actor=principal)
    if not rows:
        print("  No graded results yet.")
    else:
        print(f"\n  {'Subject':<22} {'N':>4} {'Avg':>5} {'7+':>7} {'5+':>7} {'4+':>7} "
              f"{'vs mock':>8} {'vs tgt':>7}")
        for d in rows:
            print(f"  {(d['subject'] or '')[:22]:<22} {d['graded']:>4} {_num(d['average']):>5} "
                  f"{_pct(d['pct_7']):>7} {_pct(d['pct_5']):>7} {_pct(d['pct_4']):>7} "
                  f"{_signed(d['vs_mock']):>8} {_signed(d['vs_target']):>7}")
    _pause()


def _vs_target(principal: Principal) -> None:
    s = _series()
    if s is None:
        return
    rows = ER.pupils_vs_target(s.series_id, actor=principal)
    if not rows:
        print("  No graded results yet.")
    for d in rows:
        print(f"  {d['admission_no'][:10]:<10} {(d['name'] or '')[:22]:<22} "
              f"{_signed(d['average_gap']):>6}  {', '.join(d['grades'])}")
    _pause()


# ── Export, slips, history ───────────────────────────────────────────

def _export(principal: Principal) -> None:
    s = _series()
    path = _prompt("  Save as (path to a .csv file): ") if s else ""
    if s and path:
        try:
            print(f"  ✓ Saved {ER.export_results(s.series_id, path, actor=principal)} row(s)")
        except OSError as e:
            print(f"  Couldn't write the file: {e}")


def _preview(principal: Principal) -> None:
    s = _series()
    if s is None:
        return
    if not ER.can_see(principal, s.series_id):
        print("  These results are under embargo until they are released.")
        return
    p = _pupil()
    if p:
        print("\n" + ER.slip_text(ER.slip(p.pupil_id, s.series_id)))
        _pause()


def _slips(principal: Principal) -> None:
    _need_editor(principal)
    s = _series()
    if s is None or not _yes(f"  E-mail every candidate's results slip for {s.name}?"):
        return
    r = ER.send_slips(s.series_id, actor=principal)
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    try:
        report = E.deliver(r["message_id"], principal=principal)
        print(f"  ✓ {r['emails']} e-mail(s): " + ", ".join(
            f"{n} {E.STATUS_LABELS[k].lower()}" for k, n in report.counts.items()))
    except Exception as e:  # noqa: BLE001 - stays queued in the outbox
        print(f"  Saved {r['emails']} e-mail(s) but delivery failed: {e}")
    if r["nobody"]:
        print("  No e-mail address for: " + ", ".join(p.display_name for p in r["nobody"]))


def _print_history(rows: list[dict[str, Any]]) -> None:
    for h in rows:
        print(f"  {h['at']}  {h['actor']:<12} {h['action']:<15} "
              + (f"result {h['result_id']} " if h["result_id"] else "") + str(h["detail"]))
    if not rows:
        print("  No history yet.")
    _pause()


def _series_history(principal: Principal) -> None:
    s = _series()
    if s and not ER.can_see(principal, s.series_id):
        print("  These results are under embargo until they are released.")
    elif s:
        _print_history(ER.history(series_id=s.series_id, limit=60))


def _result_history(principal: Principal) -> None:
    r = _result()
    if r and _visible(principal, r):
        _print_history(ER.history(result_id=r.result_id, limit=60))
