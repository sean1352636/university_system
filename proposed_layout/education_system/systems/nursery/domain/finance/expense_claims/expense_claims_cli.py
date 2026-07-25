"""CLI flows for Primary School Expense Claims."""

from __future__ import annotations

import logging
from typing import Any, Callable

from education_system.systems.nursery.domain.finance.expense_claims import (
    expense_claims as data,
)
from education_system.systems.nursery.domain.finance.expense_claims.expense_claims import (
    CATEGORIES,
    CLAIM_STATUSES,
    CLAIMANT_TYPES,
    Claim,
    ClaimLine,
    DEFAULT_CATEGORY,
    DEFAULT_CLAIM_STATUS,
    DEFAULT_CLAIMANT_TYPE,
    DEFAULT_PAYMENT_METHOD,
    PAYMENT_METHODS,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


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
            return _input(prompt, default=default,
                            allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _yes_no(prompt: str, *, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)",
                  default="y" if default else "n").strip().lower()
    return raw in ("y", "yes")


def _multiline(prompt: str, *, default: str = "") -> str:
    print(f"\n  {prompt} (end with '.'; ENTER for default)")
    if default:
        for line in default.splitlines():
            print(f"    | {line}")
    lines: list[str] = []
    try:
        while True:
            ln = input("  > ")
            if ln.strip() == ".":
                break
            if not lines and not ln:
                return default
            lines.append(ln)
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    return "\n".join(lines)


def _pick_from(label: str, options: list[str],
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number.")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_claim() -> Claim:
    rows = data.list_claims()
    if not rows:
        print("    No claims yet.")
        raise _UserAbort
    print("\n  Claims:")
    for i, c in enumerate(rows, 1):
        print(f"    {i:>3}) #{c.claim_id}  "
              f"{c.claim_ref[:14]:<14}  "
              f"{c.claimant_type[:6]:<6} "
              f"{c.claimant_id[:8]:<8}  "
              f"{c.title[:30]:<30}  "
              f"£{c.total_amount:>9,.2f}  "
              f"[{c.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            k = int(raw)
            if 1 <= k <= len(rows):
                return rows[k - 1]
            m = next((x for x in rows if x.claim_id == k),
                       None)
            if m:
                return m
        print("    No matching claim.")


def _pick_line(claim_id: int) -> ClaimLine:
    rows = data.lines_for_claim(claim_id)
    if not rows:
        print("    No lines yet.")
        raise _UserAbort
    print("\n  Lines:")
    for i, ln in enumerate(rows, 1):
        print(f"    {i:>3}) #{ln.line_id}  "
              f"{ln.incurred_on}  "
              f"{ln.category[:14]:<14}  "
              f"{(ln.description or '—')[:32]:<32}  "
              f"£{ln.gross_amount:>9,.2f}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            k = int(raw)
            if 1 <= k <= len(rows):
                return rows[k - 1]
            m = next((x for x in rows if x.line_id == k),
                       None)
            if m:
                return m
        print("    No matching line.")


def _print_claims(rows: list[Claim]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Ref':<14}  {'Claimant':<24}  "
          f"{'Title':<32}  {'Category':<14}  "
          f"{'Submitted':<10}  {'Status':<12}  "
          f"{'Lines':>5}  Total")
    print("  " + "-" * 150)
    for c in rows:
        clm = f"{c.claimant_type[:6]}:{c.claimant_id[:14]}"
        print(f"  {c.claim_id:>4}  {c.claim_ref[:14]:<14}  "
              f"{clm[:24]:<24}  {c.title[:32]:<32}  "
              f"{c.category[:14]:<14}  "
              f"{(c.submitted_on or '—'):<10}  "
              f"{c.status:<12}  {c.line_count:>5}  "
              f"£{c.total_amount:>9,.2f}")
    print(f"\n  {len(rows)} claim(s).")


def _print_lines(rows: list[ClaimLine]) -> None:
    if not rows:
        print("\n  (no lines)")
        return
    print()
    print(f"  {'#':>4}  {'Incurred':<10}  "
          f"{'Category':<14}  {'Description':<32}  "
          f"{'Supplier':<16}  Qty   Unit       "
          f"VAT       Gross")
    print("  " + "-" * 140)
    for ln in rows:
        print(f"  {ln.line_id:>4}  {ln.incurred_on:<10}  "
              f"{ln.category[:14]:<14}  "
              f"{(ln.description or '—')[:32]:<32}  "
              f"{(ln.supplier or '—')[:16]:<16}  "
              f"{ln.quantity:>3.1f}  "
              f"£{ln.unit_amount:>8,.2f}  "
              f"£{ln.vat_amount:>7,.2f}  "
              f"£{ln.gross_amount:>9,.2f}")


def _print_claim_full(c: Claim) -> None:
    print()
    print(f"    #{c.claim_id}  {c.claim_ref}  — {c.title}")
    print(f"    Claimant         : {c.claimant_type} :: "
          f"{c.claimant_id}"
          + (f"  ({c.claimant_name})"
              if c.claimant_name else ""))
    print(f"    Department       : {c.department or '—'}")
    print(f"    Category         : {c.category}")
    print(f"    Purpose          : {c.purpose or '—'}")
    print(f"    Incurred         : "
          f"{c.incurred_from or '—'}  to  "
          f"{c.incurred_to or '—'}")
    print(f"    Submitted on     : {c.submitted_on or '—'}")
    print(f"    Approved on/by   : "
          f"{c.approved_on or '—'} / "
          f"{c.approved_by or '—'}")
    print(f"    Rejected on      : {c.rejected_on or '—'}")
    print(f"    Rejection reason : "
          f"{c.rejection_reason or '—'}")
    print(f"    Paid on          : {c.paid_on or '—'}")
    print(f"    Payment method   : {c.payment_method}")
    print(f"    Payment ref      : "
          f"{c.payment_reference or '—'}")
    print(f"    Status           : {c.status}")
    print(f"    Lines / Total    : {c.line_count} / "
          f"£{c.total_amount:,.2f}")
    print(f"    Receipts attached: "
          f"{'yes' if c.receipts_attached else 'no'}")
    if c.description:
        print("\n    Description:")
        for line in c.description.splitlines():
            print(f"      {line}")
    if c.notes:
        print("\n    Notes:")
        for line in c.notes.splitlines():
            print(f"      {line}")
    _print_lines(data.lines_for_claim(c.claim_id))


# ── Claim flows ──────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Claims ═══")
    _print_claims(data.list_claims())
    _pause()


def list_open() -> None:
    print("\n═══ Open Claims ═══")
    _print_claims(data.list_claims(open_only=True))
    _pause()


def list_awaiting_payment() -> None:
    print("\n═══ Awaiting Payment (Approved) ═══")
    _print_claims(data.list_claims(awaiting_payment_only=True))
    _pause()


def list_paid() -> None:
    print("\n═══ Paid Claims ═══")
    _print_claims(data.list_claims(paid_only=True))
    _pause()


def list_for_claimant() -> None:
    print("\n═══ Claims for a Claimant ═══")
    try:
        ct = _pick_from("Claimant type", list(CLAIMANT_TYPES),
                          default=DEFAULT_CLAIMANT_TYPE)
        cid = _input("Claimant id", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_claims(data.list_claims(claimant_type=ct,
                                              claimant_id=cid))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        ct = _input(
            f"Claimant type ({'/'.join(CLAIMANT_TYPES[:3])}…)"
            ) or None
        cat = _input(
            f"Category ({'/'.join(CATEGORIES[:3])}…)"
            ) or None
        st = _input(
            f"Status ({'/'.join(CLAIM_STATUSES[:3])}…)"
            ) or None
        pm = _input(
            f"Payment method ({'/'.join(PAYMENT_METHODS[:3])}…)"
            ) or None
        title = _input("Title contains") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_claims(
            claimant_type=ct, category=cat,
            status=st, payment_method=pm,
            title_like=title, date_from=df, date_to=dt2)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_claims(rows)
    _pause()


def view_flow() -> None:
    print("\n═══ View Claim ═══")
    try:
        c = _pick_claim()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_claim_full(c)
    _pause()


def _collect_claim(existing: Claim | None
                          ) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["claim_ref"] = _input(
        "Claim ref",
        default=(existing.claim_ref if is_edit else ""),
        allow_empty=False)
    payload["claimant_type"] = _pick_from(
        "Claimant type", list(CLAIMANT_TYPES),
        default=(existing.claimant_type if is_edit
                  else DEFAULT_CLAIMANT_TYPE))
    payload["claimant_id"] = _input(
        "Claimant id",
        default=(existing.claimant_id if is_edit else ""),
        allow_empty=False)
    payload["claimant_name"] = _input(
        "Claimant name",
        default=(existing.claimant_name or "")
        if is_edit else "")
    payload["department"] = _input(
        "Department",
        default=(existing.department or "")
        if is_edit else "")
    payload["title"] = _input(
        "Title",
        default=(existing.title if is_edit else ""),
        allow_empty=False)
    payload["category"] = _pick_from(
        "Category", list(CATEGORIES),
        default=(existing.category if is_edit
                  else DEFAULT_CATEGORY))
    payload["purpose"] = _input(
        "Purpose",
        default=(existing.purpose or "")
        if is_edit else "")
    try:
        payload["description"] = _multiline(
            "Description",
            default=(existing.description or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["incurred_from"] = _input(
        "Incurred from (YYYY-MM-DD)",
        default=(existing.incurred_from or "")
        if is_edit else "")
    payload["incurred_to"] = _input(
        "Incurred to (YYYY-MM-DD)",
        default=(existing.incurred_to or "")
        if is_edit else "")
    payload["payment_method"] = _pick_from(
        "Payment method", list(PAYMENT_METHODS),
        default=(existing.payment_method if is_edit
                  else DEFAULT_PAYMENT_METHOD))
    payload["receipts_attached"] = _yes_no(
        "Receipts attached?",
        default=(existing.receipts_attached
                  if is_edit else False))
    payload["status"] = _pick_from(
        "Status", list(CLAIM_STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_CLAIM_STATUS))
    try:
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "")
            if is_edit else "")
    except _UserAbort:
        raise
    return payload


def new_claim() -> None:
    print("\n═══ New Claim ═══")
    try:
        payload = _collect_claim(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        c = data.create_claim(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created claim #{c.claim_id}")
    _pause()


def edit_claim() -> None:
    print("\n═══ Edit Claim ═══")
    try:
        c = _pick_claim()
        payload = _collect_claim(c)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_claim(c.claim_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{c.claim_id}")
    _pause()


def submit_flow() -> None:
    print("\n═══ Submit Claim ═══")
    try:
        c = _pick_claim()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.submit(c.claim_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{c.claim_id} → Submitted")
    _pause()


def review_flow() -> None:
    print("\n═══ Begin Review ═══")
    try:
        c = _pick_claim()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.begin_review(c.claim_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{c.claim_id} → Under Review")
    _pause()


def approve_flow() -> None:
    print("\n═══ Approve ═══")
    try:
        c = _pick_claim()
        by = _input("Approved by",
                      default=c.approved_by or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.approve(c.claim_id, approved_by=by or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{c.claim_id} → Approved")
    _pause()


def reject_flow() -> None:
    print("\n═══ Reject ═══")
    try:
        c = _pick_claim()
        reason = _input("Rejection reason")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.reject(c.claim_id, reason=reason or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{c.claim_id} → Rejected")
    _pause()


def pay_flow() -> None:
    print("\n═══ Pay ═══")
    try:
        c = _pick_claim()
        ref = _input("Payment reference")
        on = _input("Paid on (YYYY-MM-DD)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.pay(c.claim_id,
                    payment_reference=ref or None,
                    paid_on=on or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{c.claim_id} → Paid")
    _pause()


def cancel_flow() -> None:
    print("\n═══ Cancel ═══")
    try:
        c = _pick_claim()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.cancel(c.claim_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{c.claim_id} → Cancelled")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        c = _pick_claim()
        new_status = _pick_from("New status",
                                  list(CLAIM_STATUSES),
                                  default=c.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(c.claim_id, new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{c.claim_id} → {new_status}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete ═══")
    try:
        c = _pick_claim()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete claim #{c.claim_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_claim(c.claim_id):
        print(f"\n  ✓ Deleted #{c.claim_id}")
    _pause()


# ── Line flows ───────────────────────────────────────────

def _collect_line(existing: ClaimLine | None
                         ) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["incurred_on"] = _input(
        "Incurred on (YYYY-MM-DD)",
        default=(existing.incurred_on if is_edit else ""),
        allow_empty=False)
    payload["category"] = _pick_from(
        "Category", list(CATEGORIES),
        default=(existing.category if is_edit
                  else DEFAULT_CATEGORY))
    payload["description"] = _input(
        "Description",
        default=(existing.description or "")
        if is_edit else "")
    payload["supplier"] = _input(
        "Supplier",
        default=(existing.supplier or "")
        if is_edit else "")
    payload["receipt_ref"] = _input(
        "Receipt ref",
        default=(existing.receipt_ref or "")
        if is_edit else "")
    payload["quantity"] = _input(
        "Quantity",
        default=(str(existing.quantity)
                  if is_edit else "1"))
    payload["unit_amount"] = _input(
        "Unit amount (£)",
        default=(str(existing.unit_amount)
                  if is_edit else "0"))
    payload["mileage_miles"] = _input(
        "Mileage miles (blank = N/A)",
        default=(str(existing.mileage_miles or "")
                  if is_edit else ""))
    payload["mileage_rate"] = _input(
        "Mileage rate (£/mile)",
        default=(str(existing.mileage_rate or "")
                  if is_edit else ""))
    payload["vat_amount"] = _input(
        "VAT amount (£)",
        default=(str(existing.vat_amount)
                  if is_edit else "0"))
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "")
        if is_edit else "")
    return payload


def add_line_flow() -> None:
    print("\n═══ Add Line to Claim ═══")
    try:
        c = _pick_claim()
        payload = _collect_line(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        ln = data.add_line(c.claim_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Added line #{ln.line_id}, "
          f"gross £{ln.gross_amount:,.2f}")
    _pause()


def edit_line_flow() -> None:
    print("\n═══ Edit Claim Line ═══")
    try:
        c = _pick_claim()
        ln = _pick_line(c.claim_id)
        payload = _collect_line(ln)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_line(ln.line_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated line #{ln.line_id}")
    _pause()


def delete_line_flow() -> None:
    print("\n═══ Delete Claim Line ═══")
    try:
        c = _pick_claim()
        ln = _pick_line(c.claim_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete line #{ln.line_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_line(ln.line_id):
        print(f"\n  ✓ Deleted line #{ln.line_id}")
    _pause()


def view_lines_flow() -> None:
    print("\n═══ View Claim Lines ═══")
    try:
        c = _pick_claim()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_lines(data.lines_for_claim(c.claim_id))
    _pause()


# ── Summary ─────────────────────────────────────────────

def summary_flow() -> None:
    print("\n═══ Expense Claims Summary ═══")
    s = data.summary()
    print(f"\n  Total claims          : {s.total_claims}")
    print(f"  Drafts                : {s.drafts}")
    print(f"  Submitted             : {s.submitted}")
    print(f"  Under review          : {s.under_review}")
    print(f"  Approved              : {s.approved}")
    print(f"  Paid                  : {s.paid}")
    print(f"  Rejected              : {s.rejected}")
    print(f"  Cancelled             : {s.cancelled}")
    print(f"  Distinct claimants    : {s.distinct_claimants}")
    print(f"\n  Total value           : "
          f"£{s.total_value:,.2f}")
    print(f"  Awaiting payment      : "
          f"£{s.awaiting_payment_value:,.2f}")
    print(f"  Paid value            : "
          f"£{s.paid_value:,.2f}")
    print("\n  By category:")
    for k in CATEGORIES:
        n = s.by_category.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By claimant type:")
    for k in CLAIMANT_TYPES:
        n = s.by_claimant_type.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    print("\n  By status:")
    for k in CLAIM_STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    print("\n  By payment method:")
    for k in PAYMENT_METHODS:
        n = s.by_payment_method.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",          list_all),
    ("Open",              list_open),
    ("Awaiting payment",  list_awaiting_payment),
    ("Paid",              list_paid),
    ("For claimant",      list_for_claimant),
    ("Filter",            filter_flow),
    ("View claim",        view_flow),
    ("View lines",        view_lines_flow),
    ("─" * 6,             lambda: None),
    ("New claim",         new_claim),
    ("Edit claim",        edit_claim),
    ("Add line",          add_line_flow),
    ("Edit line",         edit_line_flow),
    ("Delete line",       delete_line_flow),
    ("Submit",            submit_flow),
    ("Begin review",      review_flow),
    ("Approve",           approve_flow),
    ("Reject",            reject_flow),
    ("Pay",               pay_flow),
    ("Cancel",            cancel_flow),
    ("Change status",     set_status_flow),
    ("Delete claim",      delete_flow),
    ("─" * 6,             lambda: None),
    ("Summary",           summary_flow),
]


def run() -> None:
    while True:
        print("\n── Expense Claims ──")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label * 3}")
            else:
                print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (
                1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        label, handler = _MENU[int(choice) - 1]
        if label.startswith("─"):
            continue
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Expense Claims CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Expense Claims":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Expense Claims CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
