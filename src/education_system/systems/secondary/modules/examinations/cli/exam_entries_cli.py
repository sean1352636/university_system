"""Exam entries in the terminal. The old options 1-6 are kept (new / update,
list, view, set status, cohort summary, delete); 7-30 are added (series,
specifications, candidate numbers, generating and finalising entries,
checks, fees, board files, statements of entry, CSV, the exam centre) and S
chooses the exam series. Rules live in :mod:`modules.examinations.domain.exam_entries`."""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.modules.examinations.domain import exam_entries as EE
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (EE.ValidationError, EE.PermissionDenied, EE.NotFound)
_state: dict[str, Any] = {"series_id": None}


_problem = prompts.problem
_int = prompts.to_int


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
        print("  No exam series yet - add one with option 7.")
    return s


def _choose_series() -> None:
    rows = EE.list_series()
    _print_series(rows)
    sid = _int(_prompt("  Series ID: "))
    if sid is not None:
        _state["series_id"] = EE.get_series(sid).series_id


def _print_series(rows: list[EE.ExamSeries]) -> None:
    if not rows:
        print("  No exam series yet.")
        return
    print(f"\n  {'ID':<4} {'Name':<16} {'Status':<9} {'Entry by':<11} {'Late by':<11} Deadline")
    for s in rows:
        print(f"  {s.series_id:<4} {s.name[:16]:<16} {s.status:<9} {s.entry_deadline or '-':<11} "
              f"{s.late_deadline or '-':<11} {EE.deadline_text(s)}")


def _pupil(prompt: str = "  Pupil (admission number or UPN): ") -> P.Pupil | None:
    ref = _prompt(prompt)
    if not ref:
        return None
    p = P.find_by_reference(ref) or (P.get_pupil(int(ref)) if ref.isdigit() else None)
    if p is None:
        print("  No pupil with that reference.")
    return p


def _spec() -> EE.Spec | None:
    rows = EE.list_specs(active_only=True)
    if not rows:
        print("  No specifications - set them up with option 12 or 14.")
        return None
    _print_specs(rows)
    sid = _int(_prompt("  Specification ID: "))
    return EE.get_spec(sid) if sid is not None else None


def _print_specs(rows: list[EE.Spec]) -> None:
    print(f"\n  {'ID':<4} {'Subject':<20} {'Board':<14} {'Spec':<7} {'Codes':<18} "
          f"{'Fee':>8} {'Late':>8} Active")
    for x in rows:
        codes = f"{x.foundation_code}/{x.higher_code}" if x.tiered else (x.entry_code or
                                                                        x.spec_code)
        print(f"  {x.spec_id:<4} {x.subject_name[:20]:<20} {x.exam_board[:14]:<14} "
              f"{x.spec_code[:7]:<7} {codes[:18]:<18} {EE.money(x.fee):>8} "
              f"{EE.money(x.late_fee):>8} {'yes' if x.is_active else 'no'}")


def _print_table(rows: list[EE.ExamEntry]) -> None:
    print(f"  {'ID':<5} {'Pupil':<10} {'Name':<20} {'Yr':<3} {'Subj':<6} {'Board':<10} "
          f"{'Spec':<7} {'Tier':<10} {'Cand#':<6} {'Status':<12} {'Fee':>8} Sent")
    for e in rows:
        print(f"  {e.entry_id:<5} {e.admission_no:<10} {(e.pupil_name or '')[:20]:<20} "
              f"{e.pupil_year or '-'!s:<3} {(e.subject_code or '?')[:6]:<6} "
              f"{e.exam_board[:10]:<10} {(e.spec_code or '-')[:7]:<7} {e.tier:<10} "
              f"{(e.candidate_number or '-'):<6} "
              f"{(e.entry_status + ('*' if e.late else '')):<12} "
              f"{(EE.money(e.fee) if e.fee is not None else '-'):>8} "
              + ("to send" if e.unsent else (e.submitted_on or "")))


def _entry() -> EE.ExamEntry | None:
    eid = _int(_prompt("  Entry ID: "))
    if eid is None:
        return None
    e = EE.get(eid)
    if e is None:
        print("  No entry with that ID.")
    return e


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("exam.entries.view")
        s = _series(required=False)
        print("\n── GCSE Exam Entries ──")
        print(f"  Series: {s.name} ({s.status}) · {EE.deadline_text(s)}" if s
              else "  Series: none yet")
        print("   1) New / update entry\n   2) List entries\n   3) View entry"
              "\n   4) Set entry status\n   5) Cohort summary\n   6) Delete entry"
              "\n   7) New exam series\n   8) List exam series\n   9) Edit exam series"
              "\n  10) Set series status\n  11) List specifications\n  12) New specification"
              "\n  13) Edit specification\n  14) Set up specifications from subjects"
              "\n  15) Candidate numbers for a year group\n  16) Set a candidate number / UCI"
              "\n  17) Number everyone entered in the series"
              "\n  18) Generate provisional entries from teaching groups"
              "\n  19) Make provisional entries Final\n  20) Checks\n  21) Fees"
              "\n  22) Board files\n  23) Preview a statement of entry"
              "\n  24) E-mail statements of entry\n  25) Import entries (CSV)"
              "\n  26) Export entries (CSV)\n  27) Exam centre\n  28) Series history"
              "\n  29) Access arrangements\n  30) Set the tier of an entry"
              "\n   S) Choose the exam series\n   0) Back")
        choice = _prompt("Select: ").lower()
        if choice in {"0", ""}:
            return
        try:
            {"1": lambda: _upsert(principal), "2": _list, "3": _view,
             "4": lambda: _set_status(principal), "5": _summary,
             "6": lambda: _delete(principal), "7": lambda: _series_form(principal, None),
             "8": lambda: _print_series(EE.list_series()),
             "9": lambda: _series_form(principal, _series()),
             "10": lambda: _series_status(principal), "11": lambda: _print_specs(
                 EE.list_specs()), "12": lambda: _spec_form(principal, None),
             "13": lambda: _spec_form(principal, _spec_any()),
             "14": lambda: _specs_from_subjects(principal), "15": _candidates,
             "16": lambda: _set_candidate(principal), "17": lambda: _number_series(principal),
             "18": lambda: _generate(principal), "19": lambda: _finalise(principal),
             "20": _checks, "21": _fees, "22": lambda: _board_files(principal),
             "23": _preview, "24": lambda: _statements(principal),
             "25": lambda: _import(principal), "26": lambda: _export(principal),
             "27": lambda: _centre(principal), "28": _history, "29": _access,
             "30": lambda: _tier(principal), "s": _choose_series,
             }.get(choice, lambda: print("  Invalid selection."))()
        except _ERRORS as e:
            _problem(e)


# ── The old options ──────────────────────────────────────────────────

def _upsert(principal: Principal) -> None:
    if not EE.is_editor(principal):
        raise EE.PermissionDenied("Only the exams officer can do that.")
    s = _series()
    if s is None:
        return
    print(f"\n  ── New / Update Entry ({s.name}) ──")
    p = _pupil("  Pupil ID (admission number): ")
    if p is None:
        return
    x = _spec()
    if x is None:
        return
    existing = next((e for e in EE.list_entries(series_id=s.series_id, pupil_id=p.pupil_id,
                                                spec_id=x.spec_id)), None)
    if existing:
        print(f"  Existing entry on {existing.exam_board}, {existing.entry_status}.")
    cand = EE.candidate(p.pupil_id)
    data: dict[str, Any] = {"series_id": s.series_id, "pupil_id": p.pupil_id,
                            "spec_id": x.spec_id}
    if x.tiered:
        t = _ask("Tier (Foundation/Higher/N/A)", existing.tier if existing else "N/A")
        if t is not None:
            data["tier"] = t
    if EE.is_editor(principal):
        c = _ask("Candidate number (blank = keep / next free)",
                 cand.candidate_number if cand else None)
        if c:
            EE.set_candidate(p.pupil_id, candidate_number=c, actor=principal)
    if not existing:
        st = _ask("Status (Provisional/Final)", "Provisional")
        if st is not None:
            data["entry_status"] = st
    fee = _ask(f"Fee (£, blank = automatic {EE.money(x.fee)})",
               EE._num(existing.fee) if existing and existing.fee_manual else None)
    if fee is not None:
        data["fee"] = fee
    for key, label, cur in (("fee_payer", "Fee payer (School/Parent)",
                             existing.fee_payer if existing else "School"),
                            ("resit", "Resit (y/n)", ("y" if existing and existing.resit
                                                      else "n")),
                            ("notes", "Notes", existing.notes if existing else None)):
        v = _ask(label, cur)
        if v is not None:
            data[key] = v
    e = EE.upsert(data, actor=principal)
    print(f"  Saved entry #{e.entry_id}: {e.admission_no} / {e.subject_code} "
          f"({e.exam_board} {e.tier}, {e.entry_status}, {EE.money(e.fee)})")


def _list() -> None:
    s = _series()
    if s is None:
        return
    yg = _int(_prompt(f"  Year ({'/'.join(map(str, P.YEAR_GROUPS))}, blank): "))
    sub = _prompt("  Subject code (blank): ").upper()
    subj = S.get_by_code(sub) if sub else None
    board = _prompt(f"  Board ({'/'.join(EE.EXAM_BOARDS)}, blank): ") or None
    status = _prompt(f"  Status ({'/'.join(EE.ENTRY_STATUSES)}, blank): ") or None
    tier = _prompt(f"  Tier ({'/'.join(EE.TIERS)}, blank): ") or None
    pid = _prompt("  Pupil (admission number, blank): ") or None
    rows = EE.list_entries(series_id=s.series_id, year_group=yg,
                           subject_id=subj.subject_id if subj else None, exam_board=board,
                           entry_status=status.title() if status else None,
                           tier=tier, pupil_id=pid)
    print(f"\n  {len(rows)} entry(ies) in {s.name}:  (* = late fee)")
    _print_table(rows)
    _pause()


def _view() -> None:
    e = _entry()
    if e is None:
        return
    print(f"\n  ── Entry #{e.entry_id} ({e.series_name}) ──")
    print(f"  Pupil:        {e.admission_no} ({e.pupil_name}, Year {e.pupil_year})"
          + ("" if e.on_roll else " - no longer on roll"))
    print(f"  Candidate #:  {e.candidate_number or '-'}   UCI: {e.uci or '-'}")
    print(f"  Subject:      {e.subject_name} ({e.subject_code})")
    print(f"  Board / spec: {e.exam_board} {e.spec_code} - {e.spec_title} ({e.qualification})")
    print(f"  Entry code:   {e.entry_code}   Tier: {e.tier}")
    print(f"  Status:       {e.entry_status}{' (late)' if e.late else ''} since {e.entry_date}")
    print(f"  Fee:          {EE.money(e.fee)}{' (typed in)' if e.fee_manual else ''}, paid by "
          f"{e.fee_payer}{', resit' if e.resit else ''}")
    print("  Board:        " + ("change not sent yet" if e.unsent else
                                (f"sent {e.submitted_on}" if e.submitted_on else "not sent")))
    print(f"  Notes:        {e.notes or '-'}")
    _pause()


def _set_status(principal: Principal) -> None:
    e = _entry()
    if e is None:
        return
    print(f"  {e.pupil_name} / {e.subject_code}: currently {e.entry_status}")
    st = _prompt(f"  New status ({'/'.join(EE.ENTRY_STATUSES)}): ").title()
    if not st:
        return
    reason = _prompt("  Reason (optional): ")
    e = EE.set_status(e.entry_id, st, actor=principal, reason=reason or None)
    print(f"  ✓ {e.entry_status}" + (f" - fee {EE.money(e.fee)}" if e.fee is not None else ""))


def _summary() -> None:
    s = _series()
    if s is None:
        return
    yg = _int(_prompt("  Year (blank = all): "))
    d = EE.cohort_summary(series_id=s.series_id, year_group=yg)
    print(f"\n  {s.name}: {d['total']} entries for {d['candidates']} candidate(s)")
    for k in ("by_status", "by_board", "by_tier", "by_subject"):
        print(f"  {k[3:].title():<9} " + ", ".join(f"{a}: {b}" for a, b in d[k].items()))
    print(f"  Fees      billed {EE.money(d['total_fees'])} (late {EE.money(d['late_fees'])}, "
          f"parents {EE.money(d['by_payer']['Parent'])}); provisional estimate "
          f"{EE.money(d['estimated'])}")
    if d["unsent"]:
        print(f"  {d['unsent']} change(s) not sent to the board yet")
    _pause()


def _delete(principal: Principal) -> None:
    e = _entry()
    if e and _yes(f"  Delete entry for {e.admission_no} / {e.subject_code}?"):
        EE.delete(e.entry_id, actor=principal)
        print("  ✓ Deleted")


# ── Series and specifications ────────────────────────────────────────

def _series_form(principal: Principal, s: EE.ExamSeries | None) -> None:
    if not EE.is_editor(principal):
        raise EE.PermissionDenied("Only the exams officer can do that.")
    if s is None and _state.get("series_id") is not None and not _yes(
            "  Make a new series?"):
        return
    data: dict = {}
    for key, label, hint in (("season", "Season", "June/November"),
                             ("exam_year", "Exam year", "e.g. 2027"),
                             ("name", "Name", "blank = season + year"),
                             ("entry_deadline", "Entry deadline", "YYYY-MM-DD"),
                             ("late_deadline", "Late deadline", "YYYY-MM-DD"),
                             ("results_day", "Results day", "YYYY-MM-DD"),
                             ("notes", "Notes", "")):
        cur = str(getattr(s, key)) if s and getattr(s, key) is not None else None
        v = _ask(label, cur, required=s is None and key == "exam_year", hint=hint)
        if v is not None:
            data[key] = v
    if s:
        rec = EE.update_series(s.series_id, data, actor=principal)
        print(f"  ✓ Updated {rec.name}")
    else:
        rec = EE.create_series(data, actor=principal)
        _state["series_id"] = rec.series_id
        print(f"  ✓ Created {rec.name} - it is now the chosen series")


def _series_status(principal: Principal) -> None:
    s = _series()
    if s is None:
        return
    st = _prompt(f"  {s.name} is {s.status}. New status ({'/'.join(EE.SERIES_STATUSES)}): ")
    if st:
        print(f"  ✓ {EE.set_series_status(s.series_id, st.title(), actor=principal).status}")


def _spec_any() -> EE.Spec | None:
    _print_specs(EE.list_specs())
    sid = _int(_prompt("  Specification ID: "))
    return EE.get_spec(sid) if sid is not None else None


def _spec_form(principal: Principal, x: EE.Spec | None) -> None:
    if not EE.is_editor(principal):
        raise EE.PermissionDenied("Only the exams officer can do that.")
    data: dict = {}
    if x is None:
        code = _prompt("  Subject code: ").upper()
        subj = S.get_by_code(code)
        if subj is None:
            print("  No subject with that code.")
            return
        data["subject_id"] = subj.subject_id
    for key, label, hint in (("exam_board", "Exam board", "/".join(EE.EXAM_BOARDS)),
                             ("spec_code", "Spec code", "e.g. 8300"),
                             ("title", "Title", ""),
                             ("qualification", "Qualification", "/".join(EE.QUALIFICATIONS)),
                             ("tiered", "Tiered", "y/n"),
                             ("entry_code", "Entry code", ""),
                             ("foundation_code", "Foundation code", "tiered only"),
                             ("higher_code", "Higher code", "tiered only"),
                             ("fee", "Fee £", ""), ("late_fee", "Late fee £", "")):
        cur = getattr(x, key) if x else None
        if key == "tiered" and x:
            cur = "y" if x.tiered else "n"
        elif key in ("fee", "late_fee"):
            cur = EE._num(cur)
        v = _ask(label, None if cur in (None, "") else str(cur),
                 required=x is None and key in ("exam_board", "spec_code"), hint=hint)
        if v is not None:
            data[key] = v
    rec = (EE.update_spec(x.spec_id, data, actor=principal) if x
           else EE.create_spec(data, actor=principal))
    print(f"  ✓ {rec.label}")


def _specs_from_subjects(principal: Principal) -> None:
    made = EE.specs_from_subjects(actor=principal)
    print(f"  ✓ Set up {len(made)} specification(s)" + "".join(f"\n    {x.label}" for x in made))
    missing = EE.subjects_without_spec()
    if missing:
        print("  KS4 subjects still without one: " + ", ".join(s.name for s in missing))
    print("  Check the entry codes, tiers and fees (option 13).")


# ── Candidates ───────────────────────────────────────────────────────

def _candidates() -> None:
    yg = _int(_prompt("  Year group [11]: ")) or 11
    pupils = P.list_pupils(year_group=yg)
    cands = EE.candidates([p.pupil_id for p in pupils])
    print(f"\n  {'Adm no':<10} {'Pupil':<24} {'Cand#':<6} UCI")
    for p in pupils:
        c = cands.get(p.pupil_id)
        print(f"  {p.admission_no:<10} {p.display_name[:24]:<24} "
              f"{(c.candidate_number if c else '-'):<6} {(c.uci or '') if c else ''}")
    missing = [p for p in pupils if p.pupil_id not in cands]
    print(f"\n  {len(missing)} pupil(s) without a candidate number")
    _pause()


def _set_candidate(principal: Principal) -> None:
    p = _pupil()
    if p is None:
        return
    c = EE.candidate(p.pupil_id)
    num = _ask("Candidate number (blank = keep / next free)", c.candidate_number if c else None)
    uci = _ask("UCI (13 characters)", c.uci if c else None)
    rec = EE.set_candidate(p.pupil_id, candidate_number=num, uci=uci, actor=principal)
    print(f"  ✓ {p.display_name}: candidate {rec.candidate_number}"
          + (f", UCI {rec.uci}" if rec.uci else ""))


def _number_series(principal: Principal) -> None:
    s = _series()
    if s:
        print(f"  ✓ {EE.assign_series_numbers(s.series_id, actor=principal)} candidate "
              "number(s) given")


# ── Entries in bulk ──────────────────────────────────────────────────

def _generate(principal: Principal) -> None:
    s = _series()
    if s is None:
        return
    yg = _int(_prompt("  Year group [11]: ")) or 11
    r = EE.generate(s.series_id, yg, actor=principal)
    print(f"  ✓ {r['created']} provisional entr{'y' if r['created'] == 1 else 'ies'} made "
          f"({r['tiers']} with a tier from the mocks); {r['already']} already entered")
    if r["several_specs"]:
        print("  More than one specification - enter by hand: " + ", ".join(r["several_specs"]))
    if r["no_pupils"]:
        print("  Nobody in a teaching group for: " + ", ".join(r["no_pupils"]))


def _finalise(principal: Principal) -> None:
    s = _series()
    if s is None:
        return
    print(f"  {EE.deadline_text(s)}")
    ids_text = _prompt("  Entry IDs, comma separated (blank = every provisional entry): ")
    ids = [int(x) for x in ids_text.replace(" ", "").split(",") if x.isdigit()] or None
    if ids is None and not _yes("  Make every provisional entry Final?"):
        return
    r = EE.finalise(s.series_id, entry_ids=ids, actor=principal)
    print(f"  ✓ {r['made']} made Final")
    for e, why in r["skipped"]:
        print(f"    not ready: {e.pupil_name} {e.subject_code} - {why}")


def _checks() -> None:
    s = _series()
    if s is None:
        return
    yg = _prompt("  Check who's taught but not entered in Year [11, '-' = skip]: ")
    rows = EE.checks(s.series_id, year_group=None if yg == "-" else (_int(yg) or 11))
    for c in rows:
        print(f"  {c['level'].upper():<8} {c['text']}")
    if not rows:
        print("  Nothing to sort out. ✓")
    _pause()


def _fees() -> None:
    s = _series()
    if s is None:
        return
    by = _prompt("  Group by (subject/board/payer) [subject]: ").lower() or "subject"
    if by not in ("subject", "board", "payer"):
        print("  Choose subject, board or payer.")
        return
    print(f"\n  {by.title():<26} {'Entries':>7} {'Late':>5} {'Fees':>10}")
    for d in EE.fees_by(s.series_id, by):
        print(f"  {str(d['name'])[:26]:<26} {d['entries']:>7} {d['late']:>5} "
              f"{EE.money(d['fees']):>10}")
    t = EE.cohort_summary(series_id=s.series_id)
    print(f"\n  Billed {EE.money(t['billed'])}; provisional estimate {EE.money(t['estimated'])}")
    _pause()


# ── Board files and statements ───────────────────────────────────────

def _board_files(principal: Principal) -> None:
    s = _series()
    if s is None:
        return
    unsent = EE.unsent_by_board(s.series_id)
    boards = sorted({e.exam_board for e in EE.list_entries(series_id=s.series_id)})
    for b in boards:
        print(f"  {b:<16} {unsent.get(b, 0)} change(s) to send")
    if not boards:
        print("  No entries yet.")
        return
    board = _prompt("  Board to save a file for (blank = none): ")
    if not board:
        return
    match = next((b for b in boards if b.lower() == board.lower()), None)
    if match is None:
        print("  No entries for that board.")
        return
    full = _yes("  Full file (every entry) instead of just the changes?")
    path = _prompt("  Save as (path to a .csv file): ")
    if not path:
        return
    n = EE.export_board_file(s.series_id, match, path, actor=principal, changes_only=not full)
    print(f"  ✓ Saved {n} row(s); they are now recorded as sent to {match}")


def _preview() -> None:
    s = _series()
    p = _pupil() if s else None
    if s and p:
        print("\n" + EE.statement_text(EE.statement(p.pupil_id, s.series_id)))
        _pause()


def _statements(principal: Principal) -> None:
    s = _series()
    if s is None or not _yes(f"  E-mail every candidate's statement of entry for {s.name}?"):
        return
    r = EE.send_statements(s.series_id, actor=principal)
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    try:
        report = E.deliver(r["message_id"], principal=principal)
        print(f"  ✓ {r['emails']} e-mail(s): " + ", ".join(
            f"{n} {E.STATUS_LABELS[k].lower()}" for k, n in report.counts.items()))
    except Exception as e:  # noqa: BLE001 - stays queued in the outbox
        print(f"  Saved {r['emails']} e-mail(s) but delivery failed: {e}")
    if r["nobody"]:
        print("  No e-mail address for: " + ", ".join(p.display_name for p in r["nobody"]))


def _import(principal: Principal) -> None:
    s = _series()
    if s is None:
        return
    print("  Columns: Admission no, Spec code (or an entry code); optional Board, Tier, "
          "Fee payer, Resit, Notes")
    path = _prompt("  CSV file: ")
    if path:
        try:
            print(f"  ✓ Imported {EE.import_entries(s.series_id, path, actor=principal)} row(s)")
        except OSError as e:
            print(f"  Couldn't read the file: {e}")


def _export(principal: Principal) -> None:
    s = _series()
    path = _prompt("  Save as (path to a .csv file): ") if s else ""
    if s and path:
        try:
            print(f"  ✓ Saved {EE.export_entries(s.series_id, path, actor=principal)} row(s)")
        except OSError as e:
            print(f"  Couldn't write the file: {e}")


def _centre(principal: Principal) -> None:
    c = EE.get_centre()
    print(f"  Centre {c.centre_number or '-'} · {c.centre_name or '-'} · exams officer "
          f"{c.officer_name or '-'} {c.officer_email or ''}")
    if not EE.is_editor(principal) or not _yes("  Change it?"):
        return
    data = {}
    for key, label in (("centre_number", "Centre number (5 digits)"),
                       ("centre_name", "Centre name"), ("officer_name", "Exams officer"),
                       ("officer_email", "Officer e-mail")):
        v = _ask(label, getattr(c, key))
        if v is not None:
            data[key] = v
    EE.update_centre(data, actor=principal)
    print("  ✓ Saved")


def _history() -> None:
    s = _series()
    if s is None:
        return
    for h in EE.history(series_id=s.series_id, limit=60):
        print(f"  {h['at']}  {h['actor']:<12} {h['action']:<14} "
              + (f"entry {h['entry_id']} " if h["entry_id"] else "") + str(h["detail"]))
    _pause()


def _access() -> None:
    s = _series()
    if s is None:
        return
    rows = EE.access_arrangements(s.series_id)
    for p, a in rows:
        print(f"  {p.admission_no:<10} {p.display_name[:24]:<24} {a}")
    if not rows:
        print("  No candidates with Final entries have access arrangements.")
    _pause()


def _tier(principal: Principal) -> None:
    e = _entry()
    if e is None:
        return
    t = _prompt(f"  {e.pupil_name} {e.subject_code} is {e.tier}. New tier "
                f"({'/'.join(EE.TIERS)}): ")
    if t:
        tier = "N/A" if t.upper() == "N/A" else t.title()
        print(f"  ✓ {EE.set_tier(e.entry_id, tier, actor=principal).tier}")
