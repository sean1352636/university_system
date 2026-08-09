"""
Student Statement Runs — interactive CLI.

Wired to the service in ``finance.statements.service`` (and its ``schema``),
which read/write the shared ``student_records.db`` — the same database the
Statements GUI (``finance/gui/finance/layout/_statements.py``) uses. Any run
generated here is visible in the GUI and vice-versa.

Covers: initialise schema, generate a statement run for a period, list recent
runs, and list the per-student statements in a run (with an "only accounts
with a balance" filter).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from education_system.systems.university.domain.finance.statements import (
    init_statements,
    run_statements_batch,
    list_runs,
    list_statements,
    get_statement,
)


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


def _prompt_bool(text: str, default: bool = False) -> bool:
    d = "Y/n" if default else "y/N"
    raw = input(f"{text} ({d}): ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes", "true", "1")


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


# --------------------------------------------------------------------------- #
# 0. Schema
# --------------------------------------------------------------------------- #
def _init_schema() -> None:
    try:
        init_statements()
        print("\n✓ Statement-run schema is ready.")
    except Exception as e:
        print(f"\n✗ {e}")


# --------------------------------------------------------------------------- #
# 1. Runs
# --------------------------------------------------------------------------- #
def _generate_run(auth) -> None:
    period_end = _prompt("Period end (YYYY-MM-DD)",
                         default=datetime.now().strftime("%Y-%m-%d"))
    if not period_end:
        print("Period end is required.")
        return
    period_start = _prompt("Period start (YYYY-MM-DD, blank = beginning of time)")
    try:
        summary = run_statements_batch(
            period_end, generated_by=_current_username(auth),
            period_start=period_start or None)
        print(f"\n✓ Generated run {summary['run_id']} — "
              f"{summary['total_students']} student(s), "
              f"{summary['total_with_balance']} with a balance.")
    except Exception as e:
        print(f"\n✗ {e}")


def _list_runs() -> None:
    runs = list_runs()
    if not runs:
        print("\nNo statement runs yet.")
        return
    print(f"\n{'ID':<5}{'Period':<26}{'Students':<10}{'W/Balance':<11}{'By':<12}Generated")
    print("-" * 82)
    for r in runs:
        period = f"{r.get('period_start') or '?'} → {r.get('period_end') or '?'}"
        print(f"{r['run_id']:<5}{period[:25]:<26}"
              f"{r.get('total_students') if r.get('total_students') is not None else 0:<10}"
              f"{r.get('total_with_balance') if r.get('total_with_balance') is not None else 0:<11}"
              f"{(r.get('generated_by') or '-')[:11]:<12}"
              f"{(r.get('generated_at') or '')[:19]}")


def _list_statements() -> None:
    run_id = _prompt_int("Run id", allow_blank=False)
    only_balance = _prompt_bool("Only students with a balance?", default=False)
    statements = list_statements(run_id, only_with_balance=only_balance)
    if not statements:
        print("\nNo statements found for that run.")
        return
    print(f"\n{'StmtID':<8}{'Student':<14}{'Opening':>12}{'Charges':>12}"
          f"{'Payments':>12}{'Closing':>12}")
    print("-" * 72)
    for s in statements:
        print(f"{s['statement_id']:<8}{str(s.get('student_id') or '')[:13]:<14}"
              f"{(s.get('opening_balance') or 0):>12.2f}"
              f"{(s.get('charges_in_period') or 0):>12.2f}"
              f"{(s.get('payments_in_period') or 0):>12.2f}"
              f"{(s.get('closing_balance') or 0):>12.2f}")


def _view_statement() -> None:
    run_id = _prompt_int("Run id", allow_blank=False)
    student_id = _prompt("Student id")
    if not student_id:
        print("Student id is required.")
        return
    stmt = get_statement(run_id, student_id)
    if not stmt:
        print(f"\nNo statement for student {student_id} in run {run_id}.")
        return
    print(f"\n--- Statement (run {run_id}, student {student_id}) ---")
    for key in ("period_start", "period_end", "opening_balance",
                "charges_in_period", "payments_in_period",
                "refunds_in_period", "closing_balance"):
        print(f"  {key:<20}: {stmt.get(key) if stmt.get(key) is not None else '-'}")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_statements_menu(auth) -> None:
    """Run the Student Statement Runs CLI loop."""
    while True:
        print("\n" + "=" * 50)
        print("      STUDENT STATEMENT RUNS")
        print("=" * 50)
        print("1. Initialise schema")
        print("2. Generate a statement run")
        print("3. List runs")
        print("4. List statements in a run")
        print("5. View one student's statement")
        print("6. Return to Main Menu")
        print("=" * 50)

        try:
            choice = input("\nEnter your choice (1-6): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return

        try:
            if choice == "1":
                _init_schema()
            elif choice == "2":
                _generate_run(auth)
            elif choice == "3":
                _list_runs()
            elif choice == "4":
                _list_statements()
            elif choice == "5":
                _view_statement()
            elif choice == "6":
                print("Returning to main menu...")
                return
            else:
                print("❌ Invalid choice.")
                continue
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as e:  # keep the menu resilient
            print(f"❌ Error: {e}")
        _pause()
