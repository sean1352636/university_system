"""CLI flows for Sixth Form Fees."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.finance.fees import fees
from education_system.systems.sixth_form.domain.finance.fees import fees as data
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.finance.fees.fees import (
    CATEGORIES,
    CURRENCY_SYMBOL,
    DEFAULT_CATEGORY,
    DEFAULT_METHOD,
    DEFAULT_PAYMENT_STATUS,
    FeeItem,
    PAYMENT_METHODS,
    PAYMENT_STATUSES,
    Payment,
    STATUSES,
    STORED_STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

def _input(prompt: str, *, default: str = "",
            allow_empty: bool = True) -> str:
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


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}", default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number (or 'cancel').")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
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
            continue
        match = next((s for s in students
                       if s.student_id.lower() == raw.lower()), None)
        if match:
            return match.student_id
        print("    No matching student.")


def _money(v: float) -> str:
    sign = "-" if v < 0 else ""
    return f"{sign}{CURRENCY_SYMBOL}{abs(v):.2f}"


# ── Print helpers ──────────────────────────────────────────────────

def _print_views(rows: list[data.FeeView]) -> None:
    if not rows:
        print("\n  (no fees)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<10}  {'Name':<22}  "
          f"{'Category':<14}  {'Issued':<10}  {'Due':<10}  "
          f"{'Amount':>10}  {'Paid':>10}  {'Balance':>10}  Status")
    print("  " + "-" * 130)
    total_amt = total_paid = total_bal = 0.0
    for v in rows:
        total_amt  += v.item.amount
        total_paid += v.paid
        total_bal  += v.balance
        print(f"  {v.item.fee_id:>4}  {v.item.student_id:<10}  "
              f"{v.student_name[:22]:<22}  "
              f"{v.item.category[:14]:<14}  "
              f"{v.item.issued_date:<10}  "
              f"{(v.item.due_date or '—'):<10}  "
              f"{_money(v.item.amount):>10}  "
              f"{_money(v.paid):>10}  "
              f"{_money(v.balance):>10}  {v.effective_status}")
    print("  " + "-" * 130)
    print(f"  {'':<4}  {'':<10}  {'':<22}  {'':<14}  {'':<10}  "
          f"{'TOTALS':>10}  "
          f"{_money(total_amt):>10}  {_money(total_paid):>10}  "
          f"{_money(total_bal):>10}")
    print(f"\n  {len(rows)} fee(s).")


def _print_payments(rows: list[Payment]) -> None:
    if not rows:
        print("\n  (no payments)")
        return
    print()
    print(f"  {'#':>4}  {'Fee':>4}  {'Paid on':<10}  "
          f"{'Amount':>10}  {'Method':<14}  {'Status':<10}  Reference")
    print("  " + "-" * 92)
    total = 0.0
    for p in rows:
        if p.status == "Cleared":
            total += p.amount
        print(f"  {p.payment_id:>4}  {p.fee_id:>4}  {p.paid_on:<10}  "
              f"{_money(p.amount):>10}  "
              f"{p.method:<14}  {p.status:<10}  "
              f"{p.reference or '—'}")
    print(f"\n  {len(rows)} payment(s).  "
          f"Cleared total: {_money(round(total, 2))}")


# ── Item flows ────────────────────────────────────────────────────

def list_active() -> None:
    print("\n═══ Active Fees ═══")
    _print_views(data.list_views(active_only=True))
    _item_action_loop()


def list_all() -> None:
    print("\n═══ All Fees ═══")
    _print_views(data.list_views())
    _item_action_loop()


def list_overdue() -> None:
    print("\n═══ Overdue Fees ═══")
    _print_views(data.list_views(overdue_only=True))
    _item_action_loop()


def filter_items() -> None:
    print("\n═══ Filter Fees ═══")
    try:
        sid = _input("Student ID") or None
        cat = _input("Category") or None
        year = _input("Academic year (e.g. 2025-26)") or None
        status = _input(f"Effective status ({'/'.join(STATUSES)})") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_views(student_id=sid, category=cat,
                                academic_year=year,
                                effective_status=status)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_views(rows)
    _item_action_loop()


def per_student() -> None:
    print("\n═══ Student Statement ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    student = student_data.get_student(sid)
    rows = data.statement(sid)
    print(f"\n  {student.student_id}  {student.full_name}")
    _print_views(rows)
    print(f"\n  Outstanding balance: "
          f"{_money(data.student_balance(sid))}")
    _item_action_loop()


def view_item(fee_id: int | None = None) -> None:
    print("\n═══ View Fee ═══")
    try:
        fid = fee_id if fee_id is not None else int(
            _input("Fee ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    v = data.view_item(fid)
    if v is None:
        print(f"  ✗ No fee #{fid}")
        _pause()
        return
    it = v.item
    print()
    print(f"    Fee ID       : #{it.fee_id}")
    print(f"    Student      : {it.student_id}  {v.student_name}")
    print(f"    Description  : {it.description}")
    print(f"    Category     : {it.category}")
    print(f"    Amount       : {_money(it.amount)}")
    print(f"    Issued       : {it.issued_date}")
    print(f"    Due          : {it.due_date or '—'}")
    print(f"    Academic year: {it.academic_year or '—'}")
    print(f"    Paid         : {_money(v.paid)}")
    print(f"    Balance      : {_money(v.balance)}")
    print(f"    Status       : {v.effective_status}")
    if it.stored_status:
        print(f"    Stored status: {it.stored_status}")
    if it.notes:
        print("\n    Notes:")
        for line in it.notes.splitlines() or [""]:
            print(f"      {line}")
    print(f"\n  Payments ({v.payment_count}):")
    _print_payments(data.list_payments(fee_id=it.fee_id))
    _pause()


def _collect_item_form(existing: FeeItem | None) -> dict[str, Any]:
    is_edit = existing is not None
    p: dict[str, Any] = {}
    if is_edit:
        print(f"\n  Editing fee #{existing.fee_id} for {existing.student_id}")
        p["student_id"] = existing.student_id
    else:
        p["student_id"] = _pick_student()

    p["description"] = _input(
        "Description",
        default=existing.description if is_edit else "",
        allow_empty=False)
    p["category"] = _pick_from(
        "Category", list(CATEGORIES),
        default=existing.category if is_edit else DEFAULT_CATEGORY)
    p["amount"] = _input(
        f"Amount ({CURRENCY_SYMBOL})",
        default=f"{existing.amount:.2f}" if is_edit else "",
        allow_empty=False)
    p["issued_date"] = _input(
        "Issued date (YYYY-MM-DD)",
        default=existing.issued_date if is_edit
        else _date.today().isoformat(), allow_empty=False)
    p["due_date"] = _input(
        "Due date (optional)",
        default=(existing.due_date or "") if is_edit else "")
    p["academic_year"] = _input(
        "Academic year (e.g. 2025-26, optional)",
        default=(existing.academic_year or "") if is_edit else "")
    if is_edit:
        p["stored_status"] = _input(
            "Stored status "
            f"({'/'.join(STORED_STATUSES)}, blank=auto)",
            default=(existing.stored_status or "") if is_edit else "")
    p["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return p


def new_item() -> None:
    print("\n═══ New Fee ═══")
    try:
        payload = _collect_item_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        v = data.create_item(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created fee #{v.fee_id} ({_money(v.amount)})")
    _pause()


def edit_item(fee_id: int | None = None) -> None:
    print("\n═══ Edit Fee ═══")
    try:
        fid = fee_id if fee_id is not None else int(
            _input("Fee ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_item(fid)
    if existing is None:
        print(f"  ✗ No fee #{fid}")
        _pause()
        return
    try:
        payload = _collect_item_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_item(fid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{fid}")
    _pause()


def set_stored_status_flow(fee_id: int | None = None) -> None:
    print("\n═══ Set Stored Status (Waived/Refunded/…) ═══")
    try:
        fid = fee_id if fee_id is not None else int(
            _input("Fee ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_item(fid) is None:
        print(f"  ✗ No fee #{fid}")
        _pause()
        return
    try:
        new = _pick_from("Stored status (or 'Clear')",
                            list(STORED_STATUSES) + ["Clear"])
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_stored_status(fid, None if new == "Clear" else new)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{fid} stored_status set.")
    _pause()


def delete_item_flow(fee_id: int | None = None) -> None:
    print("\n═══ Delete Fee ═══")
    print("  ⚠ This deletes the fee AND its payments.")
    try:
        fid = fee_id if fee_id is not None else int(
            _input("Fee ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_item(fid)
    if existing is None:
        print(f"  ✗ No fee #{fid}")
        _pause()
        return
    if _input(f"Delete fee #{fid} ({existing.description!r})? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_item(fid):
        print(f"\n  ✓ Deleted #{fid}")
    _pause()


# ── Payment flows ─────────────────────────────────────────────────

def add_payment_flow(fee_id: int | None = None) -> None:
    print("\n═══ Record Payment ═══")
    try:
        fid = fee_id if fee_id is not None else int(
            _input("Fee ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    v = data.view_item(fid)
    if v is None:
        print(f"  ✗ No fee #{fid}")
        _pause()
        return
    print(f"\n  Fee #{fid}: {v.item.description}")
    print(f"    Amount  : {_money(v.item.amount)}")
    print(f"    Paid    : {_money(v.paid)}")
    print(f"    Balance : {_money(v.balance)}")
    today = _date.today().isoformat()
    try:
        amount = _input(
            f"Amount ({CURRENCY_SYMBOL})",
            default=f"{v.balance:.2f}" if v.balance > 0 else "",
            allow_empty=False)
        paid_on = _input("Paid on", default=today, allow_empty=False)
        method = _pick_from("Method", list(PAYMENT_METHODS),
                              default=DEFAULT_METHOD)
        status = _pick_from("Status", list(PAYMENT_STATUSES),
                              default=DEFAULT_PAYMENT_STATUS)
        ref = _input("Reference (optional)")
        by = _input("Recorded by (optional)")
        notes = _input("Notes (optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        p = data.create_payment(fid, {
            "amount": amount, "paid_on": paid_on,
            "method": method, "status": status,
            "reference": ref, "recorded_by": by, "notes": notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Payment #{p.payment_id} recorded "
          f"({_money(p.amount)}, {p.method})")
    _pause()


def list_payments_flow() -> None:
    print("\n═══ List Payments ═══")
    try:
        sid = _input("Student ID (optional)") or None
        method = _input("Method (optional)") or None
        df = _input("From (YYYY-MM-DD, optional)") or None
        dt = _input("To (YYYY-MM-DD, optional)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_payments(student_id=sid, method=method,
                                    date_from=df, date_to=dt)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_payments(rows)
    _pause()


def edit_payment_flow() -> None:
    print("\n═══ Edit Payment ═══")
    try:
        pid = int(_input("Payment ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_payment(pid)
    if existing is None:
        print(f"  ✗ No payment #{pid}")
        _pause()
        return
    try:
        amount = _input(
            f"Amount ({CURRENCY_SYMBOL})",
            default=f"{existing.amount:.2f}", allow_empty=False)
        paid_on = _input("Paid on", default=existing.paid_on,
                          allow_empty=False)
        method = _pick_from("Method", list(PAYMENT_METHODS),
                              default=existing.method)
        status = _pick_from("Status", list(PAYMENT_STATUSES),
                              default=existing.status)
        ref = _input("Reference", default=existing.reference or "")
        by = _input("Recorded by", default=existing.recorded_by or "")
        notes = _input("Notes", default=existing.notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_payment(pid, {
            "amount": amount, "paid_on": paid_on, "method": method,
            "status": status, "reference": ref,
            "recorded_by": by, "notes": notes,
        })
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated payment #{pid}")
    _pause()


def delete_payment_flow() -> None:
    print("\n═══ Delete Payment ═══")
    try:
        pid = int(_input("Payment ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_payment(pid) is None:
        print(f"  ✗ No payment #{pid}")
        _pause()
        return
    if _input(f"Delete payment #{pid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_payment(pid):
        print(f"\n  ✓ Deleted #{pid}")
    _pause()


# ── Summary ──────────────────────────────────────────────────────

def summary() -> None:
    print("\n═══ Fees Summary ═══")
    s = data.summary()
    print(f"\n  Items charged    : {s.total_items}")
    print(f"  Total charged    : {_money(s.total_charged)}")
    print(f"  Total paid       : {_money(s.total_paid)}")
    print(f"  Outstanding      : {_money(s.total_outstanding)}")
    print(f"  Overdue items    : {s.overdue_count}  "
          f"({_money(s.overdue_total)})")
    print(f"  Active students  : {s.active_students}")
    print(f"  Written off      : {_money(s.written_off)}")
    print(f"  Waived           : {_money(s.waived)}")
    print(f"  Refunded payments: {_money(s.refunded_payments)}")
    print("\n  By status:")
    for st in STATUSES:
        n = s.by_status.get(st, 0)
        if n:
            print(f"    {st:<14} : {n}")
    print("\n  Charges by category:")
    for c in CATEGORIES:
        v = s.by_category.get(c, 0.0)
        if v:
            print(f"    {c:<18} : {_money(v)}")
    print("\n  Payments by method:")
    for m in PAYMENT_METHODS:
        v = s.by_method.get(m, 0.0)
        if v:
            print(f"    {m:<18} : {_money(v)}")
    if s.top_debtors:
        print("\n  Top debtors:")
        for sid, name, bal in s.top_debtors:
            print(f"    {sid}  {name[:24]:<24}  {_money(bal)}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _item_action_loop() -> None:
    print()
    print("  Actions:  V) View   E) Edit   P) Add payment   "
          "S) Stored status   D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "p", "s", "d"):
            print("    Pick V, E, P, S, D, or Enter.")
            continue
        try:
            raw = _input("Fee ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            fid = int(raw)
        except ValueError:
            print("    Fee ID must be a whole number.")
            continue
        if choice == "v":
            view_item(fid)
        elif choice == "e":
            edit_item(fid)
        elif choice == "p":
            add_payment_flow(fid)
        elif choice == "s":
            set_stored_status_flow(fid)
        elif choice == "d":
            delete_item_flow(fid)
        return


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Active Fees",         list_active),
    ("All Fees",            list_all),
    ("Overdue Fees",        list_overdue),
    ("Filter",              filter_items),
    ("Student Statement",   per_student),
    ("View Fee",            view_item),
    ("New Fee",             new_item),
    ("Edit Fee",            edit_item),
    ("Set Stored Status",   set_stored_status_flow),
    ("Delete Fee",          delete_item_flow),
    ("Record Payment",      add_payment_flow),
    ("List Payments",       list_payments_flow),
    ("Edit Payment",        edit_payment_flow),
    ("Delete Payment",      delete_payment_flow),
    ("Summary",             summary),
]


def run() -> None:
    while True:
        print("\n── Fees ──")
        for i, (label, _) in enumerate(_MENU, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
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
            logger.exception("Fees CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Fees":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Fees CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
