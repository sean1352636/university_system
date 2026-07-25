"""CLI flows for Sixth Form UCAS Applications."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.progression.ucas import ucas as data
from education_system.systems.sixth_form.domain.progression.ucas.ucas import (
    APP_STATUSES,
    Application,
    Choice,
    DECISION_STATUSES,
    DEFAULT_APP_STATUS,
    DEFAULT_DECISION_STATUS,
    FINAL_DECISIONS,
    MAX_CHOICES,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


def _default_cycle_year() -> int:
    today = _date.today()
    return today.year + 1 if today.month >= 9 else today.year


# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "", allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _pick_from(label: str, options: list[str], default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}", default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel' to abort).")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print(f"    Out of range (1..{len(options)}).")
            continue
        return options[n - 1]


def _pick_student() -> str:
    students = student_data.list_students()
    if not students:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(students, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    while True:
        raw = _input(f"  Pick #1..{len(students)} (or student ID)",
                     allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(students):
                return students[n - 1].student_id
            print(f"    Out of range (1..{len(students)}).")
            continue
        match = next((s for s in students
                      if s.student_id.lower() == raw.lower()), None)
        if match:
            return match.student_id
        print("    No matching student.")


def _pick_application() -> int:
    rows = data.list_applications_with_detail()
    if not rows:
        print("    No applications exist.")
        raise _UserAbort
    print("\n  Applications:")
    for i, r in enumerate(rows, 1):
        a = r.application
        print(f"    {i:>3}) #{a.application_id:<3}  {a.student_id:<10}  "
              f"{r.student_name[:24]:<24}  cycle {a.cycle_year}  "
              f"({a.status}, {r.n_choices} choice(s))")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or application ID)",
                     allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].application.application_id
            target = next((r.application.application_id for r in rows
                           if r.application.application_id == n), None)
            if target:
                return target
            print(f"    Out of range (1..{len(rows)}).")


# ── Listing ───────────────────────────────────────────────────────

def _print_applications(rows: list[Application]) -> None:
    if not rows:
        print("\n  (no applications)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Cycle':>5}  {'Status':<10}  "
          f"{'UCAS ID':<11}  {'Submitted':<10}  Choices")
    print("  " + "-" * 78)
    for a in rows:
        n = len(data.list_choices(a.application_id))
        print(f"  {a.application_id:>4}  {a.student_id:<10}  "
              f"{a.cycle_year:>5}  {a.status:<10}  "
              f"{(a.ucas_id or '—'):<11}  {(a.submitted_at or '—'):<10}  {n}")
    print(f"\n  {len(rows)} application(s).")


def list_all() -> None:
    print("\n═══ UCAS Applications ═══")
    try:
        rows = data.list_applications()
    except Exception as e:
        logger.exception("list_applications failed")
        print(f"  ✗ Error: {e}")
        _pause()
        return
    _print_applications(rows)
    _row_action_loop(rows)


def filter_applications() -> None:
    print("\n═══ Filter Applications ═══")
    print("  (leave any field blank to skip; 'cancel' to abort)\n")
    try:
        sid = _input("Student ID") or None
        cycle_raw = _input("Cycle year")
        status = _input(f"Status ({'/'.join(APP_STATUSES)})") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    cycle = None
    if cycle_raw:
        try:
            cycle = int(cycle_raw)
        except ValueError:
            print("  ✗ Cycle year must be a number.")
            _pause()
            return
    try:
        rows = data.list_applications(
            student_id=sid, cycle_year=cycle, status=status)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_applications(rows)
    _row_action_loop(rows)


def new_application() -> None:
    print("\n═══ New UCAS Application ═══")
    print("  (type 'cancel' at any prompt to abort)")
    try:
        sid = _pick_student()
        cycle = _input("Cycle year",
                       default=str(_default_cycle_year()), allow_empty=False)
        ucas_id = _input("UCAS personal ID (10 digits, optional)")
        status = _pick_from("Status", list(APP_STATUSES),
                             default=DEFAULT_APP_STATUS)
        submitted = _input("Submitted at (YYYY-MM-DD, optional)")
        notes = _input("Notes (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_application({
            "student_id": sid, "cycle_year": cycle,
            "ucas_id": ucas_id, "status": status,
            "submitted_at": submitted, "notes": notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("create_application crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Created application #{a.application_id} for {sid} "
          f"(cycle {a.cycle_year})")
    _pause()


def view_application(application_id: int | None = None) -> None:
    print("\n═══ View Application ═══")
    try:
        aid = application_id if application_id is not None else _pick_application()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    a = data.get_application(aid)
    if a is None:
        print(f"  ✗ No application #{aid}")
        _pause()
        return
    student = student_data.get_student(a.student_id)
    print()
    print(f"    Application ID   : #{a.application_id}")
    print(f"    Student          : {a.student_id} "
          f"({student.full_name if student else '(deleted)'})")
    print(f"    Cycle year       : {a.cycle_year}")
    print(f"    UCAS personal ID : {a.ucas_id or '—'}")
    print(f"    Status           : {a.status}")
    print(f"    Submitted        : {a.submitted_at or '—'}")
    print(f"    Created          : {a.created_at}")
    if a.personal_statement:
        print("\n    Personal statement:")
        for line in a.personal_statement.splitlines() or [""]:
            print(f"      {line}")
    if a.notes:
        print(f"\n    Notes: {a.notes}")
    choices = data.list_choices(a.application_id)
    print(f"\n    Choices ({len(choices)} / {MAX_CHOICES}):")
    for c in choices:
        final = f"  Final: {c.final_decision}" if c.final_decision else ""
        print(f"      {c.choice_order}) {c.university}  "
              f"— {c.course_name}"
              + (f" ({c.course_code})" if c.course_code else "")
              + f"  [{c.decision_status}]{final}")
        if c.offer_terms:
            print(f"         offer: {c.offer_terms}")
        if c.notes:
            print(f"         notes: {c.notes}")
    _pause()


def edit_application(application_id: int | None = None) -> None:
    print("\n═══ Edit Application ═══")
    try:
        aid = application_id if application_id is not None else _pick_application()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_application(aid)
    if existing is None:
        print(f"  ✗ No application #{aid}")
        _pause()
        return
    print(f"\n  Editing application #{aid} for {existing.student_id}")
    try:
        cycle = _input("Cycle year", default=str(existing.cycle_year),
                       allow_empty=False)
        ucas_id = _input("UCAS personal ID", default=existing.ucas_id or "")
        status = _pick_from("Status", list(APP_STATUSES),
                             default=existing.status)
        submitted = _input("Submitted at",
                           default=existing.submitted_at or "")
        notes = _input("Notes", default=existing.notes or "")
        edit_ps = _input("Edit personal statement? (y/N)",
                         default="n").lower() in ("y", "yes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    payload = {
        "cycle_year":   cycle,
        "ucas_id":      ucas_id,
        "status":       status,
        "submitted_at": submitted,
        "notes":        notes,
    }
    if edit_ps:
        print("  Type personal statement (single line; for multi-line "
              "use the GUI):")
        try:
            ps = _input("Personal statement",
                        default=existing.personal_statement or "")
        except _UserAbort:
            print("\n  Cancelled.")
            return
        payload["personal_statement"] = ps
    try:
        data.update_application(aid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    except Exception as e:
        logger.exception("update_application crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
        return
    print(f"\n  ✓ Updated application #{aid}")
    _pause()


def delete_application_flow(application_id: int | None = None) -> None:
    print("\n═══ Delete Application ═══")
    try:
        aid = application_id if application_id is not None else _pick_application()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    existing = data.get_application(aid)
    if existing is None:
        print(f"  ✗ No application #{aid}")
        _pause()
        return
    n = len(data.list_choices(aid))
    confirm = _input(
        f"Delete application #{aid} ({existing.student_id}, "
        f"cycle {existing.cycle_year})? "
        + (f"{n} choice(s) will go too. " if n else "")
        + "Type 'yes' to confirm",
        default="no")
    if confirm.lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_application(aid):
            print(f"\n  ✓ Deleted #{aid}")
    except Exception as e:
        logger.exception("delete_application crashed")
        print(f"\n  ✗ Unexpected error: {e}")
    _pause()


# ── Choice management ─────────────────────────────────────────────

def manage_choices() -> None:
    print("\n═══ Manage Choices ═══")
    try:
        aid = _pick_application()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _manage_choices_for(aid)


def _manage_choices_for(aid: int) -> None:
    a = data.get_application(aid)
    if a is None:
        print(f"  ✗ No application #{aid}")
        _pause()
        return

    while True:
        choices = data.list_choices(aid)
        print(f"\n  Application #{aid}  ·  {a.student_id}  ·  cycle {a.cycle_year}")
        print(f"  Choices ({len(choices)}/{MAX_CHOICES}):")
        if not choices:
            print("    (none yet)")
        for c in choices:
            final = f"  Final: {c.final_decision}" if c.final_decision else ""
            print(f"    {c.choice_order}) #{c.choice_id}  {c.university}  "
                  f"— {c.course_name}  [{c.decision_status}]{final}")

        print("\n  1) Add choice   2) Edit choice   3) Delete choice   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if choice == "1":
            if len(choices) >= MAX_CHOICES:
                print(f"  ✗ Application already has {MAX_CHOICES} choices.")
                _pause()
                continue
            _add_choice_flow(aid)
        elif choice == "2":
            try:
                raw = _input("Choice ID to edit", allow_empty=False)
                cid = int(raw)
            except (ValueError, _UserAbort):
                continue
            _edit_choice_flow(cid)
        elif choice == "3":
            try:
                raw = _input("Choice ID to delete", allow_empty=False)
                cid = int(raw)
            except (ValueError, _UserAbort):
                continue
            c = data.get_choice(cid)
            if c is None or c.application_id != aid:
                print(f"  ✗ Choice #{cid} doesn't belong to this application.")
                _pause()
                continue
            confirm = _input(
                f"Delete slot {c.choice_order}: "
                f"{c.university} — {c.course_name}? Type 'yes'",
                default="no")
            if confirm.lower() == "yes":
                try:
                    data.delete_choice(cid)
                    print(f"  ✓ Deleted #{cid}")
                except Exception as e:
                    logger.exception("delete_choice crashed")
                    print(f"  ✗ {e}")
                _pause()
        else:
            print("  Invalid selection.")


def _add_choice_flow(application_id: int) -> None:
    used = {c.choice_order for c in data.list_choices(application_id)}
    available = [n for n in range(1, MAX_CHOICES + 1) if n not in used]
    if not available:
        print(f"  ✗ All {MAX_CHOICES} slots full.")
        _pause()
        return
    try:
        slot = _pick_from("Choice slot", [str(n) for n in available],
                           default=str(available[0]))
        uni = _input("University", allow_empty=False)
        course = _input("Course name", allow_empty=False)
        code = _input("Course code (optional)")
        year = _input("Entry year (optional)",
                      default=str(_default_cycle_year()))
        decision = _pick_from(
            "Decision status", list(DECISION_STATUSES),
            default=DEFAULT_DECISION_STATUS)
        terms = _input("Offer terms (optional)")
        final = _pick_from("Final decision",
                            ["None", *FINAL_DECISIONS], default="None")
        if final == "None":
            final = ""
        notes = _input("Notes (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.create_choice(application_id, {
            "choice_order":    slot,
            "university":      uni,
            "course_name":     course,
            "course_code":     code,
            "entry_year":      year,
            "decision_status": decision,
            "offer_terms":     terms,
            "final_decision":  final,
            "notes":           notes,
        })
        print(f"  ✓ Added choice in slot {slot}")
    except ValidationError as e:
        print(f"  ✗ {e}")
    except Exception as e:
        logger.exception("create_choice crashed")
        print(f"  ✗ Unexpected error: {e}")
    _pause()


def _edit_choice_flow(choice_id: int) -> None:
    existing = data.get_choice(choice_id)
    if existing is None:
        print(f"  ✗ No choice #{choice_id}")
        _pause()
        return
    print(f"\n  Editing choice #{choice_id} (slot {existing.choice_order})")
    try:
        slot = _input("Choice slot",
                      default=str(existing.choice_order),
                      allow_empty=False)
        uni = _input("University", default=existing.university,
                     allow_empty=False)
        course = _input("Course name", default=existing.course_name,
                        allow_empty=False)
        code = _input("Course code", default=existing.course_code or "")
        year = _input("Entry year",
                      default=(str(existing.entry_year)
                               if existing.entry_year else ""))
        decision = _pick_from(
            "Decision status", list(DECISION_STATUSES),
            default=existing.decision_status)
        terms = _input("Offer terms", default=existing.offer_terms or "")
        final = _pick_from(
            "Final decision", ["None", *FINAL_DECISIONS],
            default=existing.final_decision or "None")
        if final == "None":
            final = ""
        notes = _input("Notes", default=existing.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_choice(choice_id, {
            "choice_order":    slot,
            "university":      uni,
            "course_name":     course,
            "course_code":     code,
            "entry_year":      year,
            "decision_status": decision,
            "offer_terms":     terms,
            "final_decision":  final,
            "notes":           notes,
        })
        print(f"  ✓ Updated choice #{choice_id}")
    except ValidationError as e:
        print(f"  ✗ {e}")
    except Exception as e:
        logger.exception("update_choice crashed")
        print(f"  ✗ Unexpected error: {e}")
    _pause()


# ── Summary ───────────────────────────────────────────────────────

def summary() -> None:
    print("\n═══ Cycle Summary ═══")
    try:
        raw = _input("Cycle year (blank = all)",
                     default=str(_default_cycle_year()))
    except _UserAbort:
        print("\n  Cancelled.")
        return
    year = None
    if raw:
        try:
            year = int(raw)
        except ValueError:
            print("  ✗ Cycle year must be a number.")
            _pause()
            return

    summ = data.cycle_summary(year)
    print(f"\n  Applications: {summ.total_applications}")
    print(f"  Choices     : {summ.total_choices}")
    if summ.total_applications:
        print("\n  Application status:")
        for st in APP_STATUSES:
            print(f"    {st:<12} : {summ.by_status.get(st, 0)}")
        print("\n  Choice decision status:")
        for ds in DECISION_STATUSES:
            print(f"    {ds:<22} : {summ.by_decision_status.get(ds, 0)}")
        print("\n  Final decisions:")
        for fd in FINAL_DECISIONS:
            print(f"    {fd:<12} : {summ.by_final_decision.get(fd, 0)}")
        not_decided = summ.by_final_decision.get("", 0)
        if not_decided:
            print(f"    {'Not decided':<12} : {not_decided}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop(rows: list[Application]) -> None:
    if not rows:
        _pause()
        return
    print()
    print("  Actions:  V) View   E) Edit   C) Choices   "
          "D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "c", "d"):
            print("    Pick V, E, C, D, or Enter.")
            continue
        try:
            raw = _input("Application ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            aid = int(raw)
        except ValueError:
            print("    Application ID must be a whole number.")
            continue
        if choice == "v":
            view_application(aid)
        elif choice == "e":
            edit_application(aid)
        elif choice == "c":
            _manage_choices_for(aid)
        elif choice == "d":
            delete_application_flow(aid)
        return


# ── Submenu dispatcher ────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List Applications",   list_all),
    ("Filter Applications", filter_applications),
    ("View Application",    view_application),
    ("New Application",     new_application),
    ("Manage Choices",      manage_choices),
    ("Edit Application",    edit_application),
    ("Delete Application",  delete_application_flow),
    ("Cycle Summary",       summary),
]


def run() -> None:
    while True:
        print("\n── UCAS Applications ──")
        for i, (label, _) in enumerate(_MENU, 1):
            print(f"  {i}) {label}")
        print("  0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        _, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("UCAS CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "UCAS Applications":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("UCAS CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
