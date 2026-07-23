"""
Bank Reconciliation — interactive CLI.

Wired to the service in ``finance.bank_rec.service`` (and its ``schema``),
which read/write the shared ``student_records.db`` — the same database the
Bank Reconciliation GUI (``finance/gui/finance/layout/_bank_rec.py``) uses.
Anything imported or matched here is visible in the GUI and vice-versa.

Covers the areas the GUI exposes: initialise schema, import a statement CSV,
list statements, list statement lines, run the auto-matcher, manually match a
line to a payment/refund, unmatch, and discard.
"""

from __future__ import annotations

from typing import Optional

from education_system.post_18.university_system.modules.domain.finance.bank_rec import (
    init_bank_rec,
    import_csv,
    auto_match_statement,
    manual_match,
    unmatch,
    discard,
    list_statements,
    list_lines,
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


def _prompt_float(text: str, *, allow_blank: bool = True) -> Optional[float]:
    while True:
        raw = input(f"{text}: ").strip()
        if not raw:
            if allow_blank:
                return None
            print("A value is required.")
            continue
        try:
            return float(raw)
        except ValueError:
            print("Please enter a number.")


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
        init_bank_rec()
        print("\n✓ Bank reconciliation schema is ready.")
    except Exception as e:
        print(f"\n✗ {e}")


# --------------------------------------------------------------------------- #
# 1. Statements
# --------------------------------------------------------------------------- #
def _list_statements() -> None:
    statements = list_statements()
    if not statements:
        print("\nNo statements imported yet.")
        return
    print(f"\n{'ID':<5}{'Account':<22}{'Period':<24}{'Lines':<7}{'Unmatched':<10}By")
    print("-" * 80)
    for s in statements:
        period = f"{s.get('period_start') or '?'} → {s.get('period_end') or '?'}"
        print(f"{s['statement_id']:<5}{(s.get('account_name') or '')[:21]:<22}"
              f"{period[:23]:<24}{s.get('lines') if s.get('lines') is not None else 0:<7}"
              f"{s.get('unmatched') if s.get('unmatched') is not None else 0:<10}"
              f"{s.get('imported_by') or '-'}")


def _import_statement(auth) -> None:
    path = _prompt("CSV file path (columns: date, amount, description, reference)")
    account = _prompt("Account name")
    if not path or not account:
        print("File path and account name are required.")
        return
    period_start = _prompt("Period start (YYYY-MM-DD, optional)")
    period_end = _prompt("Period end (YYYY-MM-DD, optional)")
    opening = _prompt_float("Opening balance (optional)")
    closing = _prompt_float("Closing balance (optional)")
    try:
        summary = import_csv(
            path, account, imported_by=_current_username(auth),
            period_start=period_start or None, period_end=period_end or None,
            opening_balance=opening, closing_balance=closing)
        if summary.get('statement_id'):
            print(f"\n✓ Imported statement {summary['statement_id']} — "
                  f"{summary['lines_imported']} line(s).")
        else:
            print("\n✗ Import failed.")
        for err in summary.get('errors', []):
            print(f"  ⚠ {err}")
    except Exception as e:
        print(f"\n✗ {e}")


# --------------------------------------------------------------------------- #
# 2. Lines
# --------------------------------------------------------------------------- #
def _list_lines() -> None:
    sid = _prompt_int("Statement id", allow_blank=False)
    status = _prompt("Status filter "
                     "(unmatched/matched_auto/matched_manual/discarded, blank = all)")
    lines = list_lines(sid, status_filter=status or None)
    if not lines:
        print("\nNo lines found.")
        return
    print(f"\n{'Line':<6}{'No':<5}{'Date':<12}{'Amount':<12}{'Status':<16}Description")
    print("-" * 78)
    for ln in lines:
        amount = ln.get('amount')
        amt_str = f"{amount:.2f}" if amount is not None else "-"
        print(f"{ln['line_id']:<6}{ln.get('line_no') or '-':<5}"
              f"{(ln.get('txn_date') or '')[:11]:<12}{amt_str:<12}"
              f"{(ln.get('status') or '')[:15]:<16}"
              f"{(ln.get('description') or '')[:28]}")


def _auto_match() -> None:
    sid = _prompt_int("Statement id", allow_blank=False)
    window = _prompt_int("Match window in days (blank = default 3)")
    try:
        if window is not None:
            summary = auto_match_statement(sid, window_days=window)
        else:
            summary = auto_match_statement(sid)
        print(f"\n✓ Auto-match complete: scanned {summary['scanned']}, "
              f"matched {summary['matched']}, ambiguous {summary['ambiguous']}.")
        for err in summary.get('errors', []):
            print(f"  ⚠ {err}")
    except Exception as e:
        print(f"\n✗ {e}")


def _manual_match(auth) -> None:
    line_id = _prompt_int("Line id", allow_blank=False)
    print("Match against exactly one of:")
    payment_id = _prompt_int("  Payment id (blank to match a refund instead)")
    refund_id = None
    if payment_id is None:
        refund_id = _prompt_int("  Refund id")
    if (payment_id is None) == (refund_id is None):
        print("Provide exactly one of payment id or refund id.")
        return
    try:
        manual_match(line_id, payment_id=payment_id, refund_id=refund_id,
                     by=_current_username(auth))
        target = f"payment {payment_id}" if payment_id else f"refund {refund_id}"
        print(f"\n✓ Line {line_id} manually matched to {target}.")
    except Exception as e:
        print(f"\n✗ {e}")


def _unmatch() -> None:
    line_id = _prompt_int("Line id to reset to 'unmatched'", allow_blank=False)
    try:
        unmatch(line_id)
        print(f"\n✓ Line {line_id} reset to 'unmatched'.")
    except Exception as e:
        print(f"\n✗ {e}")


def _discard(auth) -> None:
    line_id = _prompt_int("Line id to discard (e.g. bank fee / interest)",
                          allow_blank=False)
    reason = _prompt("Reason (optional)")
    try:
        discard(line_id, reason=reason, by=_current_username(auth))
        print(f"\n✓ Line {line_id} discarded.")
    except Exception as e:
        print(f"\n✗ {e}")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_bank_rec_menu(auth) -> None:
    """Run the Bank Reconciliation CLI loop."""
    while True:
        print("\n" + "=" * 50)
        print("       BANK RECONCILIATION")
        print("=" * 50)
        print("1. Initialise schema")
        print("2. Import statement (CSV)")
        print("3. List statements")
        print("4. List statement lines")
        print("5. Auto-match a statement")
        print("6. Manual match a line")
        print("7. Unmatch a line")
        print("8. Discard a line")
        print("9. Return to Main Menu")
        print("=" * 50)

        try:
            choice = input("\nEnter your choice (1-9): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return

        try:
            if choice == "1":
                _init_schema()
            elif choice == "2":
                _import_statement(auth)
            elif choice == "3":
                _list_statements()
            elif choice == "4":
                _list_lines()
            elif choice == "5":
                _auto_match()
            elif choice == "6":
                _manual_match(auth)
            elif choice == "7":
                _unmatch()
            elif choice == "8":
                _discard(auth)
            elif choice == "9":
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
