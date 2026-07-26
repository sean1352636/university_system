"""
General Ledger — interactive CLI.

Wired to the ledger package (``finance.ledger``: schema, posting, periods,
reports), which read/write the shared ``student_records.db`` — the same
database the Ledger GUI (``finance/gui/finance/layout/_ledger.py``) uses.
Anything initialised, backfilled, or closed here is visible in the GUI and
vice-versa.

Covers: Trial Balance (init schema / backfill operational events / view),
Journals (browse headers + drill into lines), and Period management
(list / close / reopen / lock).
"""

from __future__ import annotations

from typing import Optional

from education_system.systems.university.domain.finance.ledger import (
    init_ledger,
    backfill,
    trial_balance,
    list_periods,
    close_period,
    lock_period,
    reopen_period,
)
from education_system.systems.university.domain.finance.ledger.reports import (
    journals_list,
    journal_lines,
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
# 1. Trial Balance
# --------------------------------------------------------------------------- #
def _init_ledger() -> None:
    try:
        init_ledger()
        print("\n✓ Ledger schema, chart of accounts and periods are ready.")
    except Exception as e:
        print(f"\n✗ {e}")


def _backfill(auth) -> None:
    print("\nReplaying operational events (payments, refunds, fees) into the ledger...")
    try:
        summary = backfill(posted_by=_current_username(auth))
        print(f"\n✓ Backfill complete: posted {summary['posted']}, "
              f"skipped {summary['skipped']}.")
        for src_type, src_id, msg in summary.get('errors', [])[:20]:
            print(f"  ⚠ {src_type} {src_id}: {msg}")
        extra = len(summary.get('errors', [])) - 20
        if extra > 0:
            print(f"  ... and {extra} more error(s).")
    except Exception as e:
        print(f"\n✗ {e}")


def _view_trial_balance() -> None:
    start = _prompt("Start date (YYYY-MM-DD, optional)")
    end = _prompt("End date (YYYY-MM-DD, optional)")
    entity_id = _prompt_int("Entity id (optional)")
    try:
        rows = trial_balance(start_date=start or None, end_date=end or None,
                             entity_id=entity_id)
    except Exception as e:
        print(f"\n✗ {e}")
        return
    if not rows:
        print("\nNo ledger activity in that range.")
        return
    print(f"\n{'Code':<8}{'Account':<30}{'Type':<11}{'Debit':>13}{'Credit':>13}")
    print("-" * 75)
    total_dr = total_cr = 0.0
    for r in rows:
        dr = r.get('debit_total') or 0
        cr = r.get('credit_total') or 0
        total_dr += dr
        total_cr += cr
        print(f"{(r.get('account_code') or ''):<8}"
              f"{(r.get('account_name') or '')[:29]:<30}"
              f"{(r.get('account_type') or '')[:10]:<11}"
              f"{dr:>13.2f}{cr:>13.2f}")
    print("-" * 75)
    print(f"{'TOTALS':<49}{total_dr:>13.2f}{total_cr:>13.2f}")
    if abs(total_dr - total_cr) < 0.005:
        print("✓ Trial balance is balanced (debits = credits).")
    else:
        print(f"⚠ Out of balance by {total_dr - total_cr:.2f}.")


def _trial_balance_menu(auth) -> None:
    while True:
        _header("Trial Balance")
        print("[1] Initialise ledger schema (chart + periods)")
        print("[2] Backfill operational events into the ledger")
        print("[3] View trial balance")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _init_ledger()
        elif choice == "2":
            _backfill(auth)
        elif choice == "3":
            _view_trial_balance()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 2. Journals
# --------------------------------------------------------------------------- #
def _list_journals() -> None:
    start = _prompt("Start date (YYYY-MM-DD, optional)")
    end = _prompt("End date (YYYY-MM-DD, optional)")
    source_type = _prompt("Source type filter (payment/refund/fee..., blank = all)")
    try:
        journals = journals_list(start_date=start or None, end_date=end or None,
                                 source_type=source_type or None)
    except Exception as e:
        print(f"\n✗ {e}")
        return
    if not journals:
        print("\nNo journals found.")
        return
    print(f"\n{'ID':<6}{'Date':<12}{'Per':<5}{'Source':<20}{'Amount':>13}  Description")
    print("-" * 82)
    for j in journals:
        src = f"{j.get('source_type') or '-'}:{j.get('source_id') or '-'}"
        print(f"{j['journal_id']:<6}{(j.get('journal_date') or '')[:11]:<12}"
              f"{j.get('period_id') or '-':<5}{src[:19]:<20}"
              f"{(j.get('amount') or 0):>13.2f}  {(j.get('description') or '')[:24]}")


def _view_journal() -> None:
    jid = _prompt_int("Journal id", allow_blank=False)
    try:
        lines = journal_lines(jid)
    except Exception as e:
        print(f"\n✗ {e}")
        return
    if not lines:
        print(f"\nNo lines for journal {jid}.")
        return
    print(f"\n--- Journal {jid} lines ---")
    print(f"{'Code':<8}{'Account':<30}{'Debit':>13}{'Credit':>13}")
    print("-" * 64)
    for ln in lines:
        print(f"{(ln.get('account_code') or ''):<8}"
              f"{(ln.get('account_name') or '')[:29]:<30}"
              f"{(ln.get('debit') or 0):>13.2f}{(ln.get('credit') or 0):>13.2f}")


def _journals_menu(auth) -> None:
    while True:
        _header("Journals")
        print("[1] Browse journals")
        print("[2] View journal lines")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_journals()
        elif choice == "2":
            _view_journal()
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# 3. Periods
# --------------------------------------------------------------------------- #
def _list_periods() -> None:
    fy = _prompt_int("Fiscal year filter (optional)")
    try:
        periods = list_periods(fiscal_year=fy)
    except Exception as e:
        print(f"\n✗ {e}")
        return
    if not periods:
        print("\nNo periods found.")
        return
    print(f"\n{'ID':<5}{'FY':<7}{'No':<5}{'Start':<12}{'End':<12}{'Status':<9}Journals")
    print("-" * 62)
    for p in periods:
        print(f"{p['period_id']:<5}{p.get('fiscal_year') or '-':<7}"
              f"{p.get('period_no') or '-':<5}"
              f"{(p.get('start_date') or '')[:11]:<12}"
              f"{(p.get('end_date') or '')[:11]:<12}"
              f"{(p.get('status') or '')[:8]:<9}"
              f"{p.get('journal_count') if p.get('journal_count') is not None else 0}")


def _close_period(auth) -> None:
    pid = _prompt_int("Period id to close (open → closed)", allow_blank=False)
    try:
        close_period(pid, _current_username(auth))
        print(f"\n✓ Period {pid} closed.")
    except Exception as e:
        print(f"\n✗ {e}")


def _reopen_period() -> None:
    pid = _prompt_int("Period id to reopen (closed → open)", allow_blank=False)
    try:
        reopen_period(pid)
        print(f"\n✓ Period {pid} reopened.")
    except Exception as e:
        print(f"\n✗ {e}")


def _lock_period(auth) -> None:
    pid = _prompt_int("Period id to lock (cannot be reversed)", allow_blank=False)
    confirm = _prompt("Locking is permanent. Type 'lock' to confirm")
    if confirm.lower() != "lock":
        print("Cancelled.")
        return
    try:
        lock_period(pid, _current_username(auth))
        print(f"\n✓ Period {pid} locked.")
    except Exception as e:
        print(f"\n✗ {e}")


def _periods_menu(auth) -> None:
    while True:
        _header("Period Management")
        print("[1] List periods")
        print("[2] Close period")
        print("[3] Reopen period")
        print("[4] Lock period")
        print("[0] Back")
        choice = input("\nChoice: ").strip()
        if choice == "1":
            _list_periods()
        elif choice == "2":
            _close_period(auth)
        elif choice == "3":
            _reopen_period()
        elif choice == "4":
            _lock_period(auth)
        elif choice == "0":
            return
        else:
            print("Invalid choice.")
            continue
        _pause()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run_ledger_menu(auth) -> None:
    """Run the General Ledger CLI loop."""
    while True:
        print("\n" + "=" * 50)
        print("        GENERAL LEDGER")
        print("=" * 50)
        print("1. Trial Balance (init / backfill / view)")
        print("2. Journals")
        print("3. Period Management")
        print("4. Return to Main Menu")
        print("=" * 50)

        try:
            choice = input("\nEnter your choice (1-4): ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return

        try:
            if choice == "1":
                _trial_balance_menu(auth)
            elif choice == "2":
                _journals_menu(auth)
            elif choice == "3":
                _periods_menu(auth)
            elif choice == "4":
                print("Returning to main menu...")
                return
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as e:  # keep the menu resilient
            print(f"❌ Error: {e}")
