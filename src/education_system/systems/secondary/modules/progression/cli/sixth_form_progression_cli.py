"""Move to Sixth Form in the terminal: send Year 11 pupils as sixth form
applicants (the old prompts: Subject 1-3, Destination, Notes, consent),
plus GCSE results and SEN details. Rules live in
:mod:`modules.progression.domain.sixth_form_progression`, :mod:`modules.examinations.domain.gcse_results` and
:mod:`modules.pupils.domain.sen_details`."""

from __future__ import annotations

from education_system.systems.secondary.modules.examinations.domain import gcse_results as G
from education_system.systems.secondary.modules.progression.domain import (
    sixth_form_progression as SFP,
)
from education_system.systems.secondary.modules.pupils.domain import sen_details as SEN
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (P.ValidationError, P.PermissionDenied, P.NotFound)


_problem = prompts.problem


def _pupil() -> P.Pupil | None:
    ref = _prompt("  Pupil (admission number or UPN): ")
    if not ref:
        return None
    p = P.find_by_reference(ref)
    if p is None:
        print("  No pupil with that admission number.")
    return p


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("progression.view")
        print("\n── Move to Sixth Form ──")
        print("   1) Year 11 list\n   2) Move a pupil to the sixth form"
              "\n   3) Send several pupils (no subjects, no SEN)\n   4) Applications sent"
              "\n   5) Withdraw an application\n   6) A pupil's GCSE results"
              "\n   7) Record a GCSE result\n   8) Delete a GCSE result"
              "\n   9) Import results-day CSV\n  10) Export GCSE results (CSV)"
              "\n  11) SEN register\n  12) Edit a pupil's SEN details"
              "\n  13) Send exam results to the sixth form\n  14) A-level choices"
              "\n  15) Choose / change a pupil's A-levels"
              "\n  16) A pupil's courses and entry requirements\n   0) Back")
        choice = _prompt("Select: ")
        if choice in {"0", ""}:
            return
        try:
            {"1": _cohort, "2": lambda: _send(principal), "3": lambda: _send_many(principal),
             "4": _sent, "5": lambda: _withdraw(principal), "6": _results,
             "7": lambda: _record(principal), "8": lambda: _delete(principal),
             "9": lambda: _import(principal), "10": lambda: _export(principal),
             "11": _sen_register, "12": lambda: _sen_edit(principal),
             "13": lambda: _send_results(principal), "14": _choices,
             "15": lambda: _choose(principal), "16": _courses,
             }.get(choice, lambda: print("  Invalid selection."))()
        except _ERRORS as e:
            _problem(e)


def _cohort() -> None:
    rows = SFP.cohort()
    if not rows:
        print("  No Year 11 pupils on roll.")
        return
    print(f"  {'Adm no':<10} {'Pupil':<26} {'Form':<6} {'GCSEs':<6} {'SEN':<22} "
          f"{'Sixth form':<24} Exam results")
    for c in rows:
        p = c.pupil
        sen = "-" if p.sen_status == "N" else (p.sen_label + ("" if c.sen_recorded else " *"))
        print(f"  {p.admission_no:<10} {p.display_name[:26]:<26} {(p.form_group or ''):<6} "
              f"{c.gcse_count or '-':<6} {sen[:22]:<22} {c.stage[:24]:<24} "
              f"{c.exam_results or '-'}")
    print("  * SEN details not recorded")
    _pause()


def _send(principal: Principal) -> None:
    p = _pupil()
    if p is None:
        return
    print(f"\n  Move {p.full_name} ({p.admission_no}) into the sixth form system?")
    if p.year_group != P.YEAR_GROUPS[-1]:
        print(f"  Current secondary year group is {p.year_group}.")
    print("  GCSE results: " + (G.summary_line(p.pupil_id) or "none recorded"))
    offered = SFP.offered_subjects()
    if offered:
        print("  Sixth form subjects: " + ", ".join(offered))
    subjects = [_prompt(f"  Subject {i} (blank = none): ") for i in (1, 2, 3)]
    destination = _prompt(f"  Destination [{SFP.DESTINATION_LABEL}]: ")
    notes = _prompt("  Notes: ")
    consent, ref = False, ""
    if SEN.handover_block(p):
        print("  SEN: " + SEN.summary_line(p))
        consent = _yes("  Consent recorded to share support, access and reference detail?")
        if consent:
            ref = _prompt("  Consent reference: ")
    pv = SFP.preview(p.pupil_id, actor=principal, consent_sen=consent, consent_reference=ref,
                     subjects=subjects, notes=notes)
    print("  Will send: " + ", ".join(pv.included))
    if pv.withheld_no_consent:
        print("  Held back (no consent): " + ", ".join(pv.withheld_no_consent))
    if not _yes("  Send now?"):
        return
    try:
        app = SFP.send(p.pupil_id, actor=principal, consent_sen=consent,
                       consent_reference=ref, subjects=subjects, notes=notes,
                       destination_label=destination)
    except _ERRORS:
        raise
    except Exception as e:  # noqa: BLE001 - the platform / sixth form failed
        print(f"\n  The sixth form could not take the application: {e}")
        return
    print(f"\n  {p.display_name} sent to the sixth form as an applicant ({app['stage']}).")


def _send_many(principal: Principal) -> None:
    refs = _prompt("  Admission numbers (comma-separated, blank = every Year 11 not yet "
                   "sent): ")
    if refs:
        ps = [P.find_by_reference(r.strip()) for r in refs.split(",") if r.strip()]
        missing = [r for r, p in zip(refs.split(","), ps) if p is None]
        if missing:
            print("  Not found: " + ", ".join(m.strip() for m in missing))
        ids = [p.pupil_id for p in ps if p]
    else:
        ids = [c.pupil.pupil_id for c in SFP.cohort() if c.can_send]
    if not ids:
        print("  Nobody to send.")
        return
    if not _yes(f"  Send {len(ids)} pupil(s)? SEN details are held back"):
        return
    out = SFP.send_many(ids, actor=principal)
    print(f"\n  Sent: {len(out['sent'])}")
    for k, v in out["failed"].items():
        print(f"   • {k}: {v}")


def _sent() -> None:
    rows = SFP.sent()
    if not rows:
        print("  No sixth form applications yet.")
        return
    print(f"  {'Adm no':<10} {'Pupil':<24} {'Stage':<26} {'Subjects':<28} Sent")
    for p, a in rows:
        print(f"  {(p.admission_no if p else a['pupil_id']):<10} "
              f"{(p.display_name if p else '')[:24]:<24} {a['stage']:<26} "
              f"{(a.get('programme_label') or '')[:28]:<28} {(a.get('created_at') or '')[:10]}")
    _pause()


def _withdraw(principal: Principal) -> None:
    p = _pupil()
    if p is None:
        return
    reason = _prompt("  Reason: ")
    if _yes(f"  Withdraw {p.display_name}'s sixth form application?"):
        SFP.withdraw(p.pupil_id, actor=principal, reason=reason)
        print("  Withdrawn.")


def _results() -> None:
    p = _pupil()
    if p is None:
        return
    rows = G.for_pupil(p.pupil_id)
    if not rows:
        print("  No GCSE results recorded.")
        return
    print(f"  {'ID':<5} {'Subject':<26} {'Qualification':<18} {'Grade':<6} {'Board':<16} Year")
    for r in rows:
        print(f"  {r.result_id:<5} {r.subject_name[:26]:<26} {r.qualification:<18} "
              f"{r.grade:<6} {(r.exam_board or '-'):<16} {r.exam_year} {r.series}")
    s = G.summary(p.pupil_id)
    print(f"  {s['passes']} at 4+, {s['strong']} at 5+; English {s['english'] or '-'}, "
          f"Maths {s['maths'] or '-'}")
    for h in G.history(p.pupil_id)[:10]:
        d = h["detail"]
        print(f"   {h['at']}  {h['actor']:<12} {h['action']:<7} {d.get('from') or '-'} → "
              f"{d.get('to') or '-'}")
    _pause()


def _record(principal: Principal) -> None:
    p = _pupil()
    if p is None:
        return
    print("  Grades: " + ", ".join(G.GRADES) + "; boards: " + ", ".join(G.BOARDS))
    data = {
        "subject": _prompt("  Subject (code or name): "),
        "grade": _prompt("  Grade: "),
        "qualification": _prompt(f"  Qualification ({'/'.join(G.QUALIFICATIONS)}, "
                                 "blank = GCSE): "),
        "exam_board": _prompt("  Board (blank = the subject's board): "),
        "exam_year": _prompt(f"  Exam year (blank = {G._today().year}): "),
        "series": _prompt("  Series (June/November, blank = June): "),
    }
    r = G.record(p.pupil_id, data, actor=principal)
    print(f"  Saved: {r.subject_code} {r.grade} ({r.qualification}, {r.exam_year}).")


def _delete(principal: Principal) -> None:
    rid = _prompt("  Result ID (see option 6): ")
    if not rid.isdigit():
        return
    r = G.get(int(rid))
    if _yes(f"  Delete {r.pupil_name}'s {r.subject_name} ({r.grade})?"):
        G.delete(r.result_id, actor=principal)
        print("  Deleted.")


def _import(principal: Principal) -> None:
    print("  Columns: Admission no, Subject, Grade (+ optional Qualification, Board, "
          "Exam year, Series). All rows or none.")
    path = _prompt("  CSV file: ")
    if not path:
        return
    try:
        n = G.import_csv(path, actor=principal)
    except (OSError, UnicodeDecodeError) as e:
        print(f"  Could not read the file: {e}")
        return
    print(f"  New: {n['record']} · changed: {n['change']} · unchanged: {n['unchanged']}")


def _export(principal: Principal) -> None:
    path = _prompt("  Save as (e.g. gcse_results.csv): ")
    if not path:
        return
    y = _prompt("  Year (7-11, blank = all): ")
    try:
        n = G.export_csv(path, actor=principal, year_group=int(y) if y.isdigit() else None)
    except OSError as e:
        print(f"  Could not write the file: {e}")
        return
    print(f"  {n} result(s) written to {path}.")


def _sen_register() -> None:
    y = _prompt("  Year (7-11, blank = all): ")
    rows = SEN.register(year_group=int(y) if y.isdigit() else None)
    if not rows:
        print("  No pupils with SEN support or an EHC plan.")
        return
    for p, d in rows:
        print(f"  {p.admission_no:<10} {p.display_name[:26]:<26} Y{p.year_group:<3} "
              + SEN.summary_line(p))
    _pause()


def _sen_edit(principal: Principal) -> None:
    p = _pupil()
    if p is None:
        return
    if not SEN.is_editor(principal):
        print("  Only the SENCO can change SEN details.")
        return
    cur = SEN.get(p.pupil_id)
    print(f"  SEN status: {p.sen_label}. Need codes: " + ", ".join(SEN.NEEDS))
    data: dict = {}
    fields = [("primary_need", "Primary need (code)"), ("secondary_need", "Secondary need"),
              ("provision", "Provision"), ("strategies", "Strategies"),
              ("exam_access", "Exam access arrangements"), ("notes", "SENCO notes")]
    if p.sen_status == "E":
        fields[2:2] = [("ehcp_reference", "EHC plan reference"),
                       ("ehcp_issued_on", "EHC plan issued (YYYY-MM-DD)")]
    for key, label in fields:
        v = _ask(label, getattr(cur, key) if cur else None,
                 hint="- clears" if cur else "")
        if v is not None:
            data[key] = v
    SEN.save(p.pupil_id, data, actor=principal)
    print("  Saved: " + SEN.summary_line(P.get_pupil(p.pupil_id)))  # type: ignore[arg-type]


def _send_results(principal: Principal) -> None:
    print("  Sends each open sixth form application the pupil's current GCSE results and")
    print("  entries (grades still under embargo stay back). This also happens by itself")
    print("  when the exams officer releases results.")
    ref = _prompt("  One pupil (admission number), or blank for everyone: ")
    ids = None
    if ref:
        p = P.find_by_reference(ref)
        if p is None:
            print("  No pupil with that reference.")
            return
        ids = [p.pupil_id]
    elif not _yes("  Send for every open application?"):
        return
    out = SFP.send_results(ids, actor=principal)
    print(f"  ✓ Sent for {len(out['sent'])} pupil(s)")
    for k, v in out["skipped"].items():
        print(f"    {k}: not sent ({v})")


# ── A-level choices ──────────────────────────────────────────────────

def _choices() -> None:
    from education_system.systems.secondary.modules.progression.domain import (
        sixth_form_choices as SC,
    )
    show = _prompt("  Show (all / not chosen / needs new choices) [all]: ").lower() or "all"
    if show not in ("all", "not chosen", "needs new choices"):
        print("  Show all, not chosen or needs new choices.")
        return
    rows = SC.cohort(show=show)
    print(f"\n  {'Adm no':<10} {'Pupil':<22} {'A-levels':<52} {'Results':<18} Can choose from")
    for st in rows:
        p = st["pupil"]
        print(f"  {p.admission_no:<10} {p.display_name[:22]:<22} "
              f"{', '.join(st['choices'])[:52] or '-':<52} {st['summary'][:18]:<18} "
              + (", ".join(st["can_choose_from"]) if st["all_met"] is False else ""))
    if not rows:
        print("  Nobody to show.")
    _pause()


def _courses() -> None:
    from education_system.systems.secondary.modules.progression.domain import (
        sixth_form_choices as SC,
    )
    p = _pupil()
    if p is None:
        return
    st = SC.status(p.pupil_id)
    print(f"\n  {p.display_name}: {SC.summary(st)}")
    if st["options"] is None:
        print("  The sixth form's course list isn't available.")
    for o in st["options"] or []:
        mark = "*" if o["course"] in st["choices"] else " "
        out = "awaited" if not st["results_known"] and o["requirements"] else o["outcome"]
        block = "/".join(o.get("blocks") or [])
        block = f"  [block {block}{', full' if o.get('full') else ''}]" if block else ""
        print(f"  {mark} {o['course']:<24} {out:<10} "
              + ("; ".join(o["requirements"]) or "no entry requirements") + block)
        for x in o["checks"]:
            if st["results_known"] and x["outcome"] != "Met":
                print(f"        {x['requirement']}: {x['detail']}")
    print("  * = chosen")
    _print_blocks(SC, st)
    _pause()


def _print_blocks(SC, st: dict) -> None:
    """The sixth form's option blocks, if it has set them up."""
    lines = SC.block_lines(st.get("blocks"))
    if not lines:
        return
    print(f"  Option blocks ({st['blocks']['academic_year']}) - one course from each block, "
          "full courses can't be chosen:")
    for b in lines:
        print(f"    {b}")
    for c in st["blocks"].get("clashes") or []:
        print(f"  ✗ {c}")


def _choose(principal: Principal) -> None:
    from education_system.systems.secondary.modules.progression.domain import (
        sixth_form_choices as SC,
    )
    p = _pupil()
    if p is None:
        return
    st = SC.status(p.pupil_id)
    if st["options"] is None:
        print("  The sixth form's course list isn't available just now.")
        return
    mine = {c.lower() for c in st["choices"]}
    names = [o["course"] for o in st["options"]
             if (not st["results_known"] or o["outcome"] in SC.STAFF_OK)
             and (not o.get("full") or o["course"].lower() in mine)]
    print("  Now: " + (", ".join(st["choices"]) or "none chosen"))
    _print_blocks(SC, st)
    for i, n in enumerate(names, 1):
        print(f"   {i:2d}) {n}")
    raw = _prompt("  Three numbers, comma separated: ")
    nums = [int(n) for n in raw.replace(" ", "").split(",") if n.isdigit()]
    if len(nums) != 3 or not all(1 <= n <= len(names) for n in nums):
        print("  Give three numbers from the list.")
        return
    out = SC.save(p.pupil_id, [names[n - 1] for n in nums], actor=principal)
    print(f"  ✓ Saved: {', '.join(out['choices'])} (sixth form: {out['sixth_form']})")
