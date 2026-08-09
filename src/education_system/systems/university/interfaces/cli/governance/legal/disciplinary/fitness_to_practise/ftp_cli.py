"""
Fitness to Practise — interactive CLI.

Wired to ``FtPDataAccess`` in
``fitness_to_practise.services.ftp_service``, which reads/writes the four
``ftp_*`` tables on the shared ``student_records.db`` — the same database the
FtP Portal GUI (``ftp_portal_gui.py``) uses. Anything created here is visible
in the GUI and vice-versa.

Covers the four areas the GUI advertises: Cases (list/create/view/change
stage/close/delete), Concerns, Events (audit trail), and Outcomes.
"""

from __future__ import annotations

from typing import Optional

from education_system.systems.university.domain.governance.legal.disciplinary.fitness_to_practise._db_init import (
    CONCERN_CATEGORIES,
    OUTCOMES,
    REGULATORS,
    STAGES,
)
from education_system.systems.university.domain.governance.legal.disciplinary.fitness_to_practise.services.ftp_service import (
    FtPDataAccess,
)


# --------------------------------------------------------------------------- #
# Shared data-access handle
# --------------------------------------------------------------------------- #
_db = FtPDataAccess()


# --------------------------------------------------------------------------- #
# Input helpers
# --------------------------------------------------------------------------- #
def _prompt(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or default


def _prompt_int(text: str, *, allow_blank: bool = True) -> Optional[int]:
    while True:
        raw = input(f"{text}: ").strip()
        if not raw:
            if allow_blank:
                return None
            print("A value is required.")
            continue
        try:
            return int(raw)
        except ValueError:
            print("Please enter a whole number.")


def _prompt_choice(text: str, options, default: str = "") -> str:
    """Prompt for a value, showing the accepted options. Free text allowed."""
    print(f"  Options: {', '.join(options)}")
    return _prompt(text, default)


def _pause() -> None:
    input("\nPress Enter to continue...")


def _header(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def _current_username(auth) -> str:
    try:
        user = getattr(auth, "current_user", None)
        if isinstance(user, dict):
            return user.get("username") or user.get("name") or "cli-user"
    except Exception:
        pass
    return "cli-user"


def _require_case_id() -> Optional[int]:
    """Prompt for a case id and confirm it exists; None if not found/blank."""
    case_id = _prompt_int("Case id", allow_blank=False)
    if not _db.get_case(case_id):
        print(f"\nNo case with id {case_id}.")
        return None
    return case_id


# --------------------------------------------------------------------------- #
# 1. Cases
# --------------------------------------------------------------------------- #
def _list_cases() -> None:
    stage = _prompt("Stage filter (blank = all)")
    regulator = _prompt("Regulator filter (blank = all)")
    search = _prompt("Search student/programme (optional)")
    rows = _db.list_cases(stage=stage or None, regulator=regulator or None,
                          search=search or None)
    if not rows:
        print("\nNo FtP cases found.")
        return
    print(f"\n{'ID':<5}{'Student':<12}{'Name':<22}{'Regulator':<11}"
          f"{'Stage':<22}{'Risk':<8}Opened")
    print("-" * 92)
    for r in rows:
        # (case_id, student_id, name, programme, regulator, stage,
        #  risk_level, case_officer, date_opened)
        print(f"{r[0]:<5}{(r[1] or '')[:11]:<12}{(r[2] or '')[:21]:<22}"
              f"{(r[4] or '')[:10]:<11}{(r[5] or '')[:21]:<22}"
              f"{(r[6] or '')[:7]:<8}{(r[8] or '')[:10]}")


def _view_case() -> None:
    case_id = _prompt_int("Case id", allow_blank=False)
    row = _db.get_case(case_id)
    if not row:
        print(f"\nNo case with id {case_id}.")
        return
    labels = ("case_id", "student_id", "programme", "regulator",
              "registration_no", "stage", "risk_level", "interim_order",
              "placement_status", "date_opened", "date_closed",
              "case_officer", "panel_chair", "summary", "source_record_id")
    print(f"\n--- FtP Case {case_id} ---")
    for label, val in zip(labels, row):
        print(f"  {label:<18}: {val if val is not None else '-'}")

    concerns = _db.list_concerns(case_id)
    print(f"\n  Concerns ({len(concerns)}):")
    for c in concerns:
        print(f"    [{c[0]}] {c[1]}: {(c[2] or '')[:60]} "
              f"(by {c[3] or '-'} on {c[4] or '?'})")

    events = _db.list_events(case_id)
    print(f"\n  Events ({len(events)}):")
    for e in events:
        print(f"    [{e[4] or '?'}] {e[1]} — {(e[2] or '')[:50]} "
              f"(by {e[3] or '-'})")

    outcomes = _db.list_outcomes(case_id)
    print(f"\n  Outcomes ({len(outcomes)}):")
    for o in outcomes:
        print(f"    [{o[0]}] {o[1]} — sanction: {o[2] or '-'} "
              f"(by {o[5] or '-'} on {o[6] or '?'})")


def _create_case(auth) -> None:
    student_id = _prompt("Student ID")
    if not student_id:
        print("Student ID is required.")
        return
    programme = _prompt("Programme (optional)")
    regulator = _prompt_choice("Regulator", REGULATORS, default="NMC")
    registration_no = _prompt("Registration # (optional)")
    stage = _prompt_choice("Stage", STAGES, default="Concern Raised")
    risk_level = _prompt_choice("Risk level", ("Low", "Medium", "High"),
                               default="Medium")
    interim_order = _prompt("Interim order (optional)")
    placement_status = _prompt_choice(
        "Placement status", ("Continuing", "Suspended", "Withdrawn"),
        default="Continuing")
    case_officer = _prompt("Case officer", default=_current_username(auth))
    panel_chair = _prompt("Panel chair (optional)")
    summary = _prompt("Summary (optional)")
    source_record_id = _prompt_int("Source disciplinary record id (optional)")
    data = {
        "student_id": student_id,
        "programme": programme,
        "regulator": regulator,
        "registration_no": registration_no,
        "stage": stage,
        "risk_level": risk_level,
        "interim_order": interim_order,
        "placement_status": placement_status,
        "case_officer": case_officer,
        "panel_chair": panel_chair,
        "summary": summary,
        "source_record_id": source_record_id,
    }
    try:
        case_id = _db.create_case(data)
        print(f"\n✓ Opened FtP case #{case_id} for student {student_id}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _change_stage() -> None:
    case_id = _require_case_id()
    if case_id is None:
        return
    new_stage = _prompt_choice("New stage", STAGES)
    if not new_stage:
        print("Stage is required.")
        return
    notes = _prompt("Notes (optional)")
    try:
        _db.update_stage(case_id, new_stage, notes)
        print(f"\n✓ Case #{case_id} → {new_stage}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _delete_case() -> None:
    case_id = _require_case_id()
    if case_id is None:
        return
    confirm = _prompt(f"Type YES to delete case #{case_id} and all its "
                      "concerns/events/outcomes")
    if confirm != "YES":
        print("Cancelled.")
        return
    try:
        _db.delete_case(case_id)
        print(f"\n✓ Deleted case #{case_id}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _cases_menu(auth) -> None:
    while True:
        _header("FtP Cases")
        print("[1] List cases")
        print("[2] View case (+ concerns/events/outcomes)")
        print("[3] Create case")
        print("[4] Change stage")
        print("[5] Close case (shortcut → Closed)")
        print("[6] Delete case")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_cases()
        elif choice == "2":
            _view_case()
        elif choice == "3":
            _create_case(auth)
        elif choice == "4":
            _change_stage()
        elif choice == "5":
            case_id = _require_case_id()
            if case_id is not None:
                try:
                    _db.update_stage(case_id, "Closed",
                                     _prompt("Closing notes (optional)"))
                    print(f"\n✓ Case #{case_id} closed.")
                except Exception as e:
                    print(f"\n✗ {e}")
        elif choice == "6":
            _delete_case()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 2. Concerns
# --------------------------------------------------------------------------- #
def _list_concerns() -> None:
    case_id = _require_case_id()
    if case_id is None:
        return
    rows = _db.list_concerns(case_id)
    if not rows:
        print(f"\nNo concerns recorded for case #{case_id}.")
        return
    print(f"\n{'ID':<5}{'Category':<28}{'Raised By':<16}{'Raised At':<20}"
          f"Description")
    print("-" * 92)
    for r in rows:
        print(f"{r[0]:<5}{(r[1] or '')[:27]:<28}{(r[3] or '')[:15]:<16}"
              f"{(r[4] or '')[:19]:<20}{(r[2] or '')[:30]}")


def _add_concern() -> None:
    case_id = _require_case_id()
    if case_id is None:
        return
    category = _prompt_choice("Category", CONCERN_CATEGORIES)
    description = _prompt("Description")
    if not category or not description:
        print("Category and description are required.")
        return
    try:
        _db.add_concern(case_id, category, description)
        print(f"\n✓ Added concern to case #{case_id}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _concerns_menu(auth) -> None:
    while True:
        _header("Concerns")
        print("[1] List concerns for a case")
        print("[2] Add concern")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_concerns()
        elif choice == "2":
            _add_concern()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 3. Events (audit trail)
# --------------------------------------------------------------------------- #
def _list_events() -> None:
    case_id = _require_case_id()
    if case_id is None:
        return
    rows = _db.list_events(case_id)
    if not rows:
        print(f"\nNo events recorded for case #{case_id}.")
        return
    print(f"\n{'ID':<5}{'Type':<22}{'Actor':<16}{'When':<20}Notes")
    print("-" * 90)
    for r in rows:
        print(f"{r[0]:<5}{(r[1] or '')[:21]:<22}{(r[3] or '')[:15]:<16}"
              f"{(r[4] or '')[:19]:<20}{(r[2] or '')[:28]}")


def _add_event() -> None:
    case_id = _require_case_id()
    if case_id is None:
        return
    event_type = _prompt("Event type (e.g. Hearing Scheduled, Correspondence)")
    if not event_type:
        print("Event type is required.")
        return
    notes = _prompt("Notes (optional)")
    try:
        _db.add_event(case_id, event_type, notes)
        print(f"\n✓ Logged event on case #{case_id}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _events_menu(auth) -> None:
    while True:
        _header("Events / Audit Trail")
        print("[1] List events for a case")
        print("[2] Add event")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_events()
        elif choice == "2":
            _add_event()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 4. Outcomes
# --------------------------------------------------------------------------- #
def _list_outcomes() -> None:
    case_id = _require_case_id()
    if case_id is None:
        return
    rows = _db.list_outcomes(case_id)
    if not rows:
        print(f"\nNo outcomes recorded for case #{case_id}.")
        return
    print(f"\n{'ID':<5}{'Outcome':<30}{'Sanction':<18}{'Review':<12}"
          f"{'Decided By':<16}Decided At")
    print("-" * 100)
    for r in rows:
        # (outcome_id, outcome, sanction, conditions, review_date,
        #  decided_by, decided_at)
        print(f"{r[0]:<5}{(r[1] or '')[:29]:<30}{(r[2] or '')[:17]:<18}"
              f"{(r[4] or '')[:11]:<12}{(r[5] or '')[:15]:<16}"
              f"{(r[6] or '')[:19]}")


def _record_outcome() -> None:
    case_id = _require_case_id()
    if case_id is None:
        return
    outcome = _prompt_choice("Outcome", OUTCOMES)
    if not outcome:
        print("Outcome is required.")
        return
    sanction = _prompt("Sanction (optional)")
    conditions = _prompt("Conditions (optional)")
    review = _prompt("Review date (YYYY-MM-DD, optional)")
    try:
        _db.add_outcome(case_id, outcome, sanction, conditions, review)
        print(f"\n✓ Recorded outcome for case #{case_id}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _outcomes_menu(auth) -> None:
    while True:
        _header("Outcomes")
        print("[1] List outcomes for a case")
        print("[2] Record outcome")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_outcomes()
        elif choice == "2":
            _record_outcome()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_ftp_menu(auth) -> None:
    """Run the Fitness to Practise CLI loop."""
    while True:
        print("\n" + "=" * 50)
        print("    FITNESS TO PRACTISE")
        try:
            s = _db.stats()
            print(f"  Total: {s['total']}   Open: {s['open']}   "
                  f"At Hearing: {s['hearing']}   High Risk: {s['high']}")
        except Exception:
            pass
        print("=" * 50)
        print("1. Cases")
        print("2. Concerns")
        print("3. Events / Audit Trail")
        print("4. Outcomes")
        print("5. Return to Main Menu")
        print("=" * 50)

        try:
            choice = input("\nEnter your choice (1-5): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return

        try:
            if choice == "1":
                _cases_menu(auth)
            elif choice == "2":
                _concerns_menu(auth)
            elif choice == "3":
                _events_menu(auth)
            elif choice == "4":
                _outcomes_menu(auth)
            elif choice == "5":
                print("Returning to main menu...")
                return
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as e:  # keep the menu resilient
            print(f"❌ Error: {e}")
