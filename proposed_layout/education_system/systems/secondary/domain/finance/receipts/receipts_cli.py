"""CLI flows for Secondary School Receipts."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.secondary.domain.finance.receipts import receipts
from education_system.systems.secondary.domain.finance.receipts import receipts as data
from education_system.systems.secondary.domain.pastoral import _pupils_bridge as student_data
from education_system.systems.secondary.domain.finance.receipts.receipts import (
    CURRENCY_SYMBOL,
    DEFAULT_LINE_KIND,
    DEFAULT_METHOD,
    DEFAULT_STATUS,
    LINE_KINDS,
    PAYMENT_METHODS,
    Receipt,
    STATUSES,
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


def _pick_student_optional() -> str | None:
    students = student_data.list_students()
    if not students:
        return None
    print("\n  Students (blank = skip):")
    for i, s in enumerate(students, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    raw = _input("Pick # or student ID (blank=skip)")
    if not raw:
        return None
    if raw.isdigit():
        n = int(raw)
        if 1 <= n <= len(students):
            return students[n - 1].student_id
    m = next((s for s in students
               if s.student_id.lower() == raw.lower()), None)
    return m.student_id if m else None


def _money(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{CURRENCY_SYMBOL}{v:.2f}"


# ── Print helpers ──────────────────────────────────────────────────

def _print_receipts(rows: list[Receipt]) -> None:
    if not rows:
        print("\n  (no receipts)")
        return
    print()
    print(f"  {'#':>4}  {'Number':<14}  {'Date':<10}  "
          f"{'Student':<10}  {'Payer':<24}  "
          f"{'Method':<14}  {'Total':>10}  Status")
    print("  " + "-" * 110)
    issued_t = voided_t = 0.0
    for r in rows:
        if r.status == "Issued":
            issued_t += r.total_amount
        elif r.status == "Voided":
            voided_t += r.total_amount
        print(f"  {r.receipt_id:>4}  {r.receipt_number:<14}  "
              f"{r.issued_date:<10}  "
              f"{(r.student_id or '—'):<10}  "
              f"{r.payer_name[:24]:<24}  "
              f"{r.method:<14}  {_money(r.total_amount):>10}  "
              f"{r.status}")
    print(f"\n  {len(rows)} receipt(s).  "
          f"Issued total: {_money(round(issued_t, 2))}  "
          f"Voided total: {_money(round(voided_t, 2))}")


def _print_view(rv: data.ReceiptView) -> None:
    r = rv.receipt
    print()
    print(f"  ╔══ Receipt {r.receipt_number} ══╗")
    print(f"    Receipt ID  : #{r.receipt_id}")
    print(f"    Issued      : {r.issued_date}")
    print(f"    Status      : {r.status}")
    print(f"    Payer       : {r.payer_name}")
    if r.student_id:
        print(f"    Student     : {r.student_id}"
              + (f"  ({rv.student_name})" if rv.student_name else ""))
    print(f"    Method      : {r.method}")
    print(f"    Received by : {r.received_by or '—'}")
    print(f"    Reference   : {r.reference or '—'}")
    if r.is_voided:
        print(f"    Voided at   : {r.voided_at}")
        print(f"    Reason      : {r.void_reason}")
    print()
    print(f"    {'Description':<48}  {'Kind':<10}  {'Amount':>10}")
    print("    " + "-" * 74)
    for l in rv.lines:
        print(f"    {l.description[:48]:<48}  {l.kind:<10}  "
              f"{_money(l.amount):>10}")
    print("    " + "-" * 74)
    print(f"    {'TOTAL':<60}  {_money(r.total_amount):>10}")
    if r.notes:
        print("\n    Notes:")
        for line in r.notes.splitlines() or [""]:
            print(f"      {line}")


# ── Flows ──────────────────────────────────────────────────────────

def list_issued() -> None:
    print("\n═══ Issued Receipts ═══")
    _print_receipts(data.list_receipts(issued_only=True))
    _row_action_loop()


def list_drafts() -> None:
    print("\n═══ Draft Receipts ═══")
    _print_receipts(data.list_receipts(status="Draft"))
    _row_action_loop()


def list_voided() -> None:
    print("\n═══ Voided Receipts ═══")
    _print_receipts(data.list_receipts(voided_only=True))
    _row_action_loop()


def list_all() -> None:
    print("\n═══ All Receipts ═══")
    _print_receipts(data.list_receipts())
    _row_action_loop()


def filter_receipts() -> None:
    print("\n═══ Filter Receipts ═══")
    print("  (blank to skip; 'cancel' to abort)\n")
    try:
        sid = _input("Student ID") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        method = _input("Method") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_receipts(
            student_id=sid, status=status, method=method,
            date_from=df, date_to=dt)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_receipts(rows)
    _row_action_loop()


def search() -> None:
    print("\n═══ Search Receipts ═══")
    try:
        q = _input("Query (number / payer / reference / student)",
                    allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_receipts(data.search_receipts(q))
    _row_action_loop()


def per_student() -> None:
    print("\n═══ Per-Student Receipts ═══")
    sid = _pick_student_optional()
    if sid is None:
        print("\n  Cancelled.")
        return
    s = student_data.get_student(sid)
    print(f"\n  {s.student_id}  {s.full_name}")
    _print_receipts(data.receipts_for_student(sid))
    _row_action_loop()


def view_receipt(receipt_id: int | None = None) -> None:
    print("\n═══ View Receipt ═══")
    try:
        rid = receipt_id if receipt_id is not None else int(
            _input("Receipt ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    rv = data.view_receipt(rid)
    if rv is None:
        print(f"  ✗ No receipt #{rid}")
        _pause()
        return
    _print_view(rv)
    _pause()


def _collect_lines(existing_lines: list = None) -> list[dict[str, Any]]:
    print("\n  Line items (enter 'done' when finished):")
    lines: list[dict[str, Any]] = []
    if existing_lines:
        for el in existing_lines:
            print(f"    [keep] {el.description}  "
                  f"{_money(el.amount)}  ({el.kind})")
            lines.append({
                "description": el.description,
                "amount":      el.amount,
                "kind":        el.kind,
                "source_id":   el.source_id,
                "notes":       el.notes,
            })
        if _input("Replace lines? (y/n)", default="n").lower() \
                in ("y", "yes"):
            lines = []
        else:
            return lines
    while True:
        try:
            desc = _input(f"Line {len(lines) + 1} — Description "
                            "(or 'done')",
                            allow_empty=False)
        except _UserAbort:
            raise
        if desc.lower() == "done":
            if not lines:
                print("    ✗ At least one line is required.")
                continue
            return lines
        try:
            amount = _input(f"  Amount ({CURRENCY_SYMBOL})",
                              allow_empty=False)
            kind = _pick_from("  Kind", list(LINE_KINDS),
                                 default=DEFAULT_LINE_KIND)
            src = _input("  Source ID (optional)")
            notes = _input("  Notes (optional)")
        except _UserAbort:
            raise
        lines.append({
            "description": desc, "amount": amount,
            "kind": kind, "source_id": src, "notes": notes,
        })
        print(f"    ✓ {desc} — {_money(float(amount))} ({kind})")


def new_receipt() -> None:
    print("\n═══ New Receipt ═══")
    today = _date.today().isoformat()
    try:
        issued_date = _input("Issued date", default=today,
                                allow_empty=False)
        payer = _input("Payer name", allow_empty=False)
        student_id = _pick_student_optional() or ""
        method = _pick_from("Payment method", list(PAYMENT_METHODS),
                              default=DEFAULT_METHOD)
        received_by = _input("Received by (optional)")
        reference = _input("Reference (optional)")
        notes = _input("Notes (optional)")
        lines = _collect_lines()
        status = _pick_from("Status", list(STATUSES),
                              default=DEFAULT_STATUS)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.create_receipt(
            {
                "issued_date": issued_date,
                "payer_name":  payer,
                "student_id":  student_id,
                "method":      method,
                "status":      status,
                "received_by": received_by,
                "reference":   reference,
                "notes":       notes,
            },
            lines,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created receipt {r.receipt_number} "
          f"(#{r.receipt_id}, {_money(r.total_amount)}, "
          f"status={r.status})")
    _pause()


def edit_receipt(receipt_id: int | None = None) -> None:
    print("\n═══ Edit Receipt ═══")
    try:
        rid = receipt_id if receipt_id is not None else int(
            _input("Receipt ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_receipt(rid)
    if existing is None:
        print(f"  ✗ No receipt #{rid}")
        _pause()
        return
    if existing.is_voided:
        print("  ✗ Voided receipts cannot be edited.")
        _pause()
        return

    if existing.is_issued:
        print("  (Issued — only notes/reference/received_by can change.)")
        try:
            ref = _input("Reference", default=existing.reference or "")
            by = _input("Received by",
                          default=existing.received_by or "")
            notes = _input("Notes", default=existing.notes or "")
        except _UserAbort:
            print("\n  Cancelled.")
            return
        try:
            data.update_receipt(rid, {
                "reference": ref, "received_by": by, "notes": notes,
            })
        except ValidationError as e:
            print(f"\n  ✗ {e}")
            _pause()
            return
        print(f"\n  ✓ Updated {existing.receipt_number}")
        _pause()
        return

    # Draft: full edit
    try:
        issued_date = _input("Issued date",
                                default=existing.issued_date,
                                allow_empty=False)
        payer = _input("Payer name", default=existing.payer_name,
                          allow_empty=False)
        student_id = _input("Student ID",
                                default=existing.student_id or "")
        method = _pick_from("Method", list(PAYMENT_METHODS),
                              default=existing.method)
        ref = _input("Reference", default=existing.reference or "")
        by = _input("Received by",
                      default=existing.received_by or "")
        notes = _input("Notes", default=existing.notes or "")
        existing_lines = data.list_lines(rid)
        lines = _collect_lines(existing_lines)
        status = _pick_from("Status", list(STATUSES),
                              default=existing.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_receipt(rid, {
            "issued_date": issued_date, "payer_name": payer,
            "student_id":  student_id, "method": method,
            "status":      status, "received_by": by,
            "reference":   ref, "notes": notes,
        }, lines)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated {existing.receipt_number}")
    _pause()


def issue_flow(receipt_id: int | None = None) -> None:
    print("\n═══ Issue Receipt ═══")
    try:
        rid = receipt_id if receipt_id is not None else int(
            _input("Receipt ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_receipt(rid) is None:
        print(f"  ✗ No receipt #{rid}")
        _pause()
        return
    try:
        r = data.issue(rid)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Issued {r.receipt_number}")
    _pause()


def void_flow(receipt_id: int | None = None) -> None:
    print("\n═══ Void Receipt ═══")
    try:
        rid = receipt_id if receipt_id is not None else int(
            _input("Receipt ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_receipt(rid) is None:
        print(f"  ✗ No receipt #{rid}")
        _pause()
        return
    try:
        reason = _input("Reason (required)", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.void_receipt(rid, reason)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Voided {r.receipt_number}")
    _pause()


def delete_flow(receipt_id: int | None = None) -> None:
    print("\n═══ Delete Receipt ═══")
    print("  ⚠ Only Draft receipts can be deleted. Void issued ones.")
    try:
        rid = receipt_id if receipt_id is not None else int(
            _input("Receipt ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_receipt(rid)
    if existing is None:
        print(f"  ✗ No receipt #{rid}")
        _pause()
        return
    if _input(f"Delete {existing.receipt_number}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        if data.delete_receipt(rid):
            print(f"\n  ✓ Deleted {existing.receipt_number}")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
    _pause()


def import_fee_payment_flow() -> None:
    print("\n═══ Import Fee Payment ═══")
    try:
        pid = int(_input("Fee payment ID", allow_empty=False))
        received_by = _input("Received by (optional)")
        issued = _input("Issue immediately? (y/n)",
                          default="y").lower() in ("y", "yes")
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = data.receipt_from_fee_payment(pid, received_by or None,
                                            issued=issued)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created receipt {r.receipt_number} "
          f"({_money(r.total_amount)})")
    _pause()


def import_trip_payment_flow() -> None:
    print("\n═══ Import Trip Payment ═══")
    try:
        pid = int(_input("Trip payment ID", allow_empty=False))
        received_by = _input("Received by (optional)")
        issued = _input("Issue immediately? (y/n)",
                          default="y").lower() in ("y", "yes")
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        r = data.receipt_from_trip_payment(pid, received_by or None,
                                              issued=issued)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created receipt {r.receipt_number} "
          f"({_money(r.total_amount)})")
    _pause()


def summary() -> None:
    print("\n═══ Receipts Summary ═══")
    s = data.summary()
    print(f"\n  Total receipts        : {s.total_receipts}")
    print(f"  Drafts                : {s.drafts}")
    print(f"  Issued                : {s.issued}")
    print(f"  Voided                : {s.voided}")
    print()
    print(f"  Issued total          : {_money(s.total_issued_amount)}")
    print(f"  Voided total          : {_money(s.total_voided_amount)}")
    print()
    print(f"  Today (issued)        : {_money(s.daily_today)}")
    print(f"  This week (issued)    : {_money(s.daily_this_week)}")
    print(f"  This month (issued)   : {_money(s.daily_this_month)}")
    print("\n  By method (issued):")
    for m in PAYMENT_METHODS:
        v = s.by_method.get(m, 0.0)
        if v:
            print(f"    {m:<18} : {_money(v)}")
    print("\n  By line kind (issued):")
    for k in LINE_KINDS:
        v = s.by_kind.get(k, 0.0)
        if v:
            print(f"    {k:<10} : {_money(v)}")
    if s.top_payers:
        print("\n  Top payers (issued):")
        for name, amt in s.top_payers:
            print(f"    {name[:28]:<28}  {_money(amt)}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop() -> None:
    print()
    print("  Actions:  V) View   E) Edit   I) Issue   X) Void   "
          "D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "i", "x", "d"):
            print("    Pick V, E, I, X, D, or Enter.")
            continue
        try:
            raw = _input("Receipt ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            rid = int(raw)
        except ValueError:
            print("    Receipt ID must be a whole number.")
            continue
        if choice == "v":
            view_receipt(rid)
        elif choice == "e":
            edit_receipt(rid)
        elif choice == "i":
            issue_flow(rid)
        elif choice == "x":
            void_flow(rid)
        elif choice == "d":
            delete_flow(rid)
        return


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Issued Receipts",       list_issued),
    ("Draft Receipts",        list_drafts),
    ("Voided Receipts",       list_voided),
    ("All Receipts",          list_all),
    ("Filter",                filter_receipts),
    ("Search",                search),
    ("Per-Student",           per_student),
    ("View Receipt",          view_receipt),
    ("New Receipt",           new_receipt),
    ("Edit Receipt",          edit_receipt),
    ("Issue",                 issue_flow),
    ("Void",                  void_flow),
    ("Delete (Draft)",        delete_flow),
    ("Import Fee Payment",    import_fee_payment_flow),
    ("Import Trip Payment",   import_trip_payment_flow),
    ("Summary",               summary),
]


def run() -> None:
    while True:
        print("\n── Receipts ──")
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
            logger.exception("Receipts CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Receipts":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Receipts CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
