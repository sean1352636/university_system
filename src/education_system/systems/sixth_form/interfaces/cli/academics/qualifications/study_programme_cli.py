"""CLI flows for study programmes (mirrors ``study_programme_views``).

* :func:`run_for_student` — one learner: learning aims (add / edit /
  course change / withdraw / complete / qualifying check / history),
  prior GCSEs, condition of funding, planned hours, option choices and
  identifiers. Reached from Student Profile ("P") and the directory
  row actions.
* :func:`run_option_blocks` — define option blocks (Subjects submenu).
* :func:`run_reports` — college-wide reports (Subjects / Courses submenus).

Every prompt accepts ``cancel`` (or Ctrl-C) to back out.
"""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Any, Callable

from education_system.systems.sixth_form.domain.academics.qualifications import (
    grade_scales,
    identifiers,
    learning_aims,
    option_blocks,
    prior_attainment,
    study_programme,
)
from education_system.systems.sixth_form.domain.learners.students import students

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    """Ctrl-C / ``cancel`` at a prompt."""


def _input(prompt: str, *, default: str = "", allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        try:
            raw = input(f"  {prompt}{suffix}: ")
        except (EOFError, KeyboardInterrupt):
            print()
            raise _UserAbort
        s = raw.strip()
        if s.lower() == "cancel":
            raise _UserAbort
        if s:
            return s
        if default:
            return default
        if allow_empty:
            return ""
        print("    Value is required.")


def _pick(label: str, options: list[str], default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, o in enumerate(options, 1):
        print(f"    {i:>2}) {o}{'  *' if o == default else ''}")
    while True:
        raw = _input("Choose number", default=str(options.index(default) + 1)
                     if default in options else "")
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        if raw in options:
            return raw
        print("    Pick a number from the list.")


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _me() -> str:
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        return access.current().username or ""
    except Exception:
        return ""


def _today() -> str:
    return _dt.date.today().isoformat()


def _current_year() -> str:
    return learning_aims.academic_year_for(_today()) or ""


def _menu(title: str, items: list[tuple[str, Callable[[], None]]]) -> None:
    while True:
        print(f"\n── {title} ──")
        for i, (label, _) in enumerate(items, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not 1 <= int(choice) <= len(items):
            print("  Invalid selection.")
            continue
        try:
            items[int(choice) - 1][1]()
        except _UserAbort:
            print("\n  Cancelled.")
        except ValueError as e:          # every ValidationError is a ValueError
            print(f"\n  ✗ {e}")
            _pause()
        except Exception as e:
            logger.exception("Study programme CLI action failed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


# ── One learner ─────────────────────────────────────────────────────

def _print_aims(sid: str) -> list[learning_aims.LearningAim]:
    aims = learning_aims.list_aims(sid)
    print(f"\n  {'#':>4}  {'Qualification':<26} {'Subject':<24} {'Status':<11} "
          f"{'Start':<10} {'End':<10} {'Hours':>6}  Qualifying period")
    for a in aims:
        c = learning_aims.qualifying_check_for(a)
        qp = ("NOT met" if c.withdrawn_before_qualifying else
              "met" if c.met else f"due {c.qualifying_date}")
        print(f"  {a.aim_id:>4}  {a.qualification_type:<26} {a.subject[:24]:<24} "
              f"{a.status:<11} {a.start_date:<10} "
              f"{(a.withdrawal_date or a.planned_end_date or '—'):<10} "
              f"{(a.planned_hours if a.planned_hours is not None else '—'):>6}  {qp}"
              f"{'  [core]' if a.is_core_aim else ''}")
    if not aims:
        print("  (no learning aims)")
    return aims


def _pick_aim(sid: str, *, active_only: bool = True) -> learning_aims.LearningAim:
    aims = [a for a in learning_aims.list_aims(sid) if a.is_active or not active_only]
    if not aims:
        raise learning_aims.ValidationError("No matching aims")
    choice = _pick("Aim", [f"#{a.aim_id} {a.label} ({a.status})" for a in aims])
    return learning_aims.get_aim(int(choice.split()[0][1:]))


def run_for_student(student_id: str | None = None) -> None:
    sid = student_id or _input("Student ID", allow_empty=False)
    student = students.get_student(sid)
    if student is None:
        print(f"\n  ✗ No student with id {sid}")
        _pause()
        return

    def list_aims() -> None:
        _print_aims(sid)
        print(f"\n  Mirrored A-level slots: "
              f"{', '.join(students.get_student(sid).subjects) or '—'}")
        _pause()

    def add() -> None:
        qtype = _pick("Qualification type", list(grade_scales.QUALIFICATION_TYPES),
                      grade_scales.DEFAULT_QUALIFICATION_TYPE)
        data = {
            "qualification_type": qtype,
            "subject": _input("Subject", allow_empty=False),
            "awarding_body": _input("Awarding body"),
            "aim_code": _input("Aim / QAN code"),
            "start_date": _input("Start date (YYYY-MM-DD)", default=_today()),
            "planned_end_date": _input("Planned end date (YYYY-MM-DD)"),
            "planned_hours": _input("Planned hours this year"),
            "is_core_aim": _input("Core aim? (y/n)", default="n").lower().startswith("y"),
        }
        a = learning_aims.add_aim(sid, data, recorded_by=_me())
        print(f"\n  ✓ Added aim #{a.aim_id} {a.label}")
        _pause()

    def edit() -> None:
        a = _pick_aim(sid, active_only=False)
        data = {
            "awarding_body": _input("Awarding body", default=a.awarding_body or ""),
            "aim_code": _input("Aim / QAN code", default=a.aim_code or ""),
            "start_date": _input("Start date", default=a.start_date),
            "planned_end_date": _input("Planned end date", default=a.planned_end_date or ""),
            "planned_hours": _input("Planned hours", default=str(a.planned_hours or "")),
            "is_core_aim": _input("Core aim? (y/n)", default="y" if a.is_core_aim else "n"
                                  ).lower().startswith("y"),
        }
        learning_aims.update_aim(a.aim_id, data, recorded_by=_me())
        print("\n  ✓ Updated.")
        _pause()

    def change() -> None:
        a = _pick_aim(sid)
        qtype = _pick("New qualification type", list(grade_scales.QUALIFICATION_TYPES),
                      a.qualification_type)
        new, chk = learning_aims.change_aim(
            a.aim_id, new_qualification_type=qtype,
            new_subject=_input("New subject", allow_empty=False),
            effective_date=_input("New aim starts on", default=_today()),
            reason=_input("Reason", allow_empty=False),
            approved_by=_input("Approved by", default=_me(), allow_empty=False),
            new_awarding_body=_input("New awarding body", default=a.awarding_body or ""),
            recorded_by=_me())
        print(f"\n  ✓ {a.label} → {new.label} from {new.start_date}. Old aim "
              f"qualifying period {'met' if chk.met else 'NOT met'} "
              f"({chk.days_in_learning}/{chk.qualifying_days} days).")
        _pause()

    def withdraw() -> None:
        a = _pick_aim(sid)
        chk = learning_aims.withdraw_aim(
            a.aim_id,
            effective_date=_input("Last day in learning", default=_today()),
            reason=_input("Reason", allow_empty=False),
            approved_by=_input("Approved by", default=_me(), allow_empty=False),
            status=_pick("Record as", ["Withdrawn", "Transferred"], "Withdrawn"),
            recorded_by=_me())
        print(f"\n  ✓ Withdrawn after {chk.days_in_learning} day(s). Qualifying "
              f"period ({chk.qualifying_days} days): "
              f"{'met' if chk.met else 'NOT met — withdrawn before qualifying period'}")
        _pause()

    def complete() -> None:
        a = _pick_aim(sid)
        learning_aims.complete_aim(
            a.aim_id, end_date=_input("Actual end date",
                                      default=a.planned_end_date or _today()),
            recorded_by=_me())
        print("\n  ✓ Completed.")
        _pause()

    def check() -> None:
        a = _pick_aim(sid, active_only=False)
        c = learning_aims.qualifying_check_for(a)
        print(f"\n  {a.label}: start {c.start_date}, planned end "
              f"{c.planned_end_date or '—'}; qualifying period {c.qualifying_days} "
              f"days (from {c.qualifying_date}); in learning {c.days_in_learning} "
              f"days to {c.end_date_used} → {'MET' if c.met else 'not met'}"
              + (" — withdrawn before qualifying period" if c.withdrawn_before_qualifying else ""))
        _pause()

    def history() -> None:
        for h in learning_aims.aim_history(student_id=sid):
            qp = "" if h.qualifying_met is None else (" QP met" if h.qualifying_met else " QP NOT met")
            print(f"  {h.recorded_at}  #{h.aim_id:<4} {h.action:<11} eff {h.effective_date or '—'}"
                  f"  {h.from_detail or ''} → {h.to_detail or ''}  "
                  f"{h.reason or ''} (approved: {h.approved_by or '—'}){qp}")
        _pause()

    def prior() -> None:
        pa = prior_attainment.prior_attainment(sid)
        print(f"\n  Average GCSE point score: {pa.average_point_score or '—'} "
              f"({pa.gcse_count:g} GCSEs). Best English {pa.best_english_grade or '—'}, "
              f"best maths {pa.best_maths_grade or '—'}")
        for r in pa.results:
            print(f"    #{r.result_id:<4} {r.subject:<26} {r.grade:<3} ({r.grade_system}) "
                  f"{r.kind:<18} {r.year or ''} {r.exam_board or ''}")
        act = _input("A) Add  D) Delete  (Enter = back)").lower()
        if act == "a":
            prior_attainment.add_result(sid, {
                "subject": _input("Subject", allow_empty=False),
                "grade": _input("Grade (9-1 or A*-G)", allow_empty=False),
                "kind": _pick("Kind", list(prior_attainment.QUALIFICATION_KINDS), "GCSE"),
                "year": _input("Year", default=str(_dt.date.today().year)),
                "exam_board": _input("Board"),
            })
            print("  ✓ Saved.")
        elif act == "d":
            rid = _input("Result #", allow_empty=False)
            print("  ✓ Deleted." if prior_attainment.delete_result(int(rid))
                  else "  ✗ Not found.")
        _pause()

    def cof() -> None:
        fc = prior_attainment.funding_condition(sid)
        for a in fc.areas:
            print(f"\n  {a.area}: {a.status}")
            if a.aim_label:
                att = (f"{a.resit_attendance_pct}% of {a.resit_sessions}"
                       if a.resit_attendance_pct is not None else "no marks yet")
                print(f"    Aim {a.aim_label}; attendance {att}")
        act = _input("E) Record exemption  C) Clear exemption  (Enter = back)").lower()
        if act in ("e", "c"):
            area = _pick("Area", list(prior_attainment.AREAS))
            if act == "e":
                prior_attainment.set_exemption(
                    sid, area, reason=_input("Reason", allow_empty=False),
                    agreed_by=_input("Agreed by", default=_me(), allow_empty=False))
            else:
                prior_attainment.clear_exemption(sid, area)
            print("  ✓ Saved.")
        _pause()

    def hours() -> None:
        year = _input("Funding year", default=_current_year())
        ph = study_programme.planned_hours(sid, year)
        for a in ph.aims:
            print(f"    {a.aim.label:<40} {a.planned_hours:>7g} h ({a.source})"
                  f"{'' if a.counted else '  [not counted: withdrawn before QP]'}")
        for n in ph.non_qualification:
            print(f"    {n.category:<40} {n.hours:>7g} h (non-qualification)")
        print(f"\n  Total {ph.total_hours:g} h → {ph.band} "
              f"(age on 31 Aug {ph.age_on_31_august if ph.age_on_31_august is not None else '?'})")
        act = _input("N) Set non-qualification hours  (Enter = back)").lower()
        if act == "n":
            study_programme.set_non_qual_hours(
                sid, year, _pick("Category", list(study_programme.NON_QUAL_CATEGORIES)),
                _input("Hours", allow_empty=False), _input("Notes"))
            print("  ✓ Saved.")
        _pause()

    def choices() -> None:
        year = _input("Academic year", default=(option_blocks.list_years() or
                                                [_current_year()])[0])
        pattern = option_blocks.blocks(year)
        if not pattern:
            print("  No option blocks for that year (Subjects → Option Blocks).")
            _pause()
            return
        current = {c.block_letter: c for c in option_blocks.list_choices(sid, year)}
        for b, subs in sorted(pattern.items()):
            cur = current.get(b)
            print(f"    Block {b}: {', '.join(subs)}"
                  + (f"   [chosen: {cur.subject}, {cur.status}]" if cur else ""))
        act = _input("S) Set choices  A) Apply as aims  (Enter = back)").lower()
        if act == "s":
            picks = {b: _input(f"Block {b} subject (blank = none)")
                     for b in sorted(pattern)}
            chk = option_blocks.save_choices(sid, year, picks)
            print("  ✓ Saved." if chk.ok else "  ✗ " + "; ".join(chk.errors))
            for w in chk.warnings:
                print(f"    note: {w}")
        elif act == "a":
            made = option_blocks.apply_choices(sid, year, recorded_by=_me())
            print(f"  ✓ {len(made)} aim(s) created.")
        _pause()

    def ids() -> None:
        s = students.get_student(sid)
        print(f"\n  ULN {s.uln or '—'}   UCI {s.uci or '—'}   Candidate no. "
              f"{s.candidate_number or '—'}")
        print("  (UCI is format-checked only — the JCQ check character is not verified)")
        out = students.set_identifiers(
            sid, uln=_input("ULN (10 digits)", default=s.uln or ""),
            uci=_input("UCI (13 chars)", default=s.uci or ""),
            candidate_number=_input("Candidate number", default=s.candidate_number or ""))
        print(f"  ✓ Saved (ULN {'valid' if identifiers.is_valid_uln(out.uln) else '—'}).")
        _pause()

    _menu(f"Study Programme — {student.full_name} ({sid})", [
        ("List learning aims", list_aims), ("Add aim", add), ("Edit aim", edit),
        ("Course change", change), ("Withdraw from aim", withdraw),
        ("Complete aim", complete), ("Qualifying-period check", check),
        ("Change history", history), ("Prior attainment (GCSEs)", prior),
        ("Condition of funding", cof), ("Planned hours & funding band", hours),
        ("Option choices", choices), ("Identifiers (ULN / UCI / candidate no.)", ids),
    ])


# ── Option blocks ───────────────────────────────────────────────────

def run_option_blocks() -> None:
    state = {"year": (option_blocks.list_years() or [_current_year()])[0]}

    def show() -> None:
        print(f"\n  Option blocks for {state['year']}:")
        for e, n in option_blocks.block_uptake(state["year"]):
            print(f"    #{e.entry_id:<4} Block {e.block_letter}  {e.subject:<26} "
                  f"{e.qualification_type:<22} cap {e.capacity or '—':<4} chosen {n}")
        _pause()

    def year() -> None:
        state["year"] = _input("Academic year", default=state["year"])

    def add() -> None:
        option_blocks.add_block_subject(
            state["year"], _pick("Block", list(option_blocks.BLOCK_LETTERS)),
            _input("Subject", allow_empty=False),
            qualification_type=_input("Qualification type (blank = subject's)") or None,
            capacity=_input("Capacity"))
        print("  ✓ Added.")

    def remove() -> None:
        ok = option_blocks.remove_block_subject(int(_input("Entry #", allow_empty=False)))
        print("  ✓ Removed." if ok else "  ✗ Not found.")

    def copy() -> None:
        n = option_blocks.copy_blocks(state["year"], _input("Copy to year", allow_empty=False))
        print(f"  ✓ {n} entr(ies) copied.")

    def combo() -> None:
        assignment, reasons = option_blocks.find_block_assignment(
            state["year"], _input("Subjects (comma separated)", allow_empty=False).split(","))
        print("  Fits: " + ", ".join(f"{b}={s}" for b, s in assignment.items())
              if assignment else "  " + "\n  ".join(reasons))
        _pause()

    _menu("Option Blocks", [("Show blocks", show), ("Change year", year),
                            ("Add subject to block", add), ("Remove entry", remove),
                            ("Copy blocks to another year", copy),
                            ("Check a subject combination", combo)])


# ── Reports ─────────────────────────────────────────────────────────

def _cof_report() -> None:
    only = _input("Non-compliant only? (y/n)", default="y").lower().startswith("y")
    rows = prior_attainment.compliance_report(only_non_compliant=only)
    for r in rows:
        print(f"\n  {r.student_id} {r.student_name}")
        for a in r.condition.areas:
            print(f"    {a.area}: {a.status}")
    print(f"\n  {len(rows)} learner(s).")
    _pause()


def _bands_report() -> None:
    rows = study_programme.band_report(_input("Funding year", default=_current_year()))
    for r in rows:
        print(f"  {r.student_id:<10} {r.student_name:<28} {r.hours.total_hours:>7g} h  "
              f"{r.hours.band}")
    print("\n  " + "  ".join(f"{b}: {n}" for b, n in study_programme.band_counts(rows).items()))
    print("  (Band thresholds must be checked against current ESFA guidance.)")
    _pause()


def _withdrawals_report() -> None:
    only = _input("Only those withdrawn before the qualifying period? (y/n)",
                  default="n").lower().startswith("y")
    rows = learning_aims.withdrawals(
        academic_year=_input("Academic year (blank = all)") or None,
        only_before_qualifying=only)
    for r in rows:
        print(f"  {r.aim.student_id:<10} {r.aim.label:<36} {r.aim.status:<11} "
              f"left {r.aim.withdrawal_date}  {r.check.days_in_learning}/"
              f"{r.check.qualifying_days} days  {'met' if r.check.met else 'NOT met'}"
              f"  {r.aim.withdrawal_reason or ''}")
    print(f"\n  {len(rows)} aim(s).")
    _pause()


def _aims_by_qualification() -> None:
    n = learning_aims.backfill_all()
    if n:
        print(f"  ({n} aim(s) backfilled from subject slots)")
    tally: dict[tuple[str, str], int] = {}
    for a in learning_aims.list_all_aims(status="Active"):
        tally[(a.qualification_type, a.subject)] = tally.get(
            (a.qualification_type, a.subject), 0) + 1
    for (t, s), c in sorted(tally.items()):
        print(f"  {t:<28} {s:<28} {c:>4} active")
    _pause()


def _epq_hours() -> None:
    from education_system.systems.sixth_form.domain.academics.epq import epq
    for proj, chk in epq.projects_below_target():
        print(f"  {proj.student_id:<10} {proj.working_title[:40]:<40} {chk.label}")
    _pause()


def run_reports() -> None:
    _menu("Study Programme Reports", [
        ("Condition of funding (English & maths)", _cof_report),
        ("Planned hours & funding bands", _bands_report),
        ("Withdrawals & qualifying period", _withdrawals_report),
        ("Active aims by qualification", _aims_by_qualification),
        ("EPQ projects under the 120-hour target", _epq_hours),
        ("Option blocks", run_option_blocks),
    ])


def dispatch(label: str) -> bool:
    """Top-level menu hook: "Study Programme" opens the reports menu."""
    if label != "Study Programme":
        return False
    try:
        run_reports()
    except _UserAbort:
        print("\n  Cancelled.")
    return True
