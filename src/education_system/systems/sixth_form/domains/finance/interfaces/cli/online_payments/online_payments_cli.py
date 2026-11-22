"""CLI flows for Sixth Form Online Payments.

* :func:`online_payments_menu` — the staff menu (FINANCE).
* :func:`pay_menu` — the parent / student menu: ``pay_menu("parent",
  account_id)`` from the parent-portal CLI, ``pay_menu("student",
  student_id)`` from the student-portal CLI.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.sixth_form.domains.finance.domain.online_payments import (
    online_payments as data,
)
from education_system.systems.sixth_form.interfaces.cli.operations._ops_cli import (
    ask,
    choose,
    pause,
    pick_student,
    run_menu,
    table,
    yes_no,
)

logger = logging.getLogger(__name__)


def _show(rows: list[data.PaymentRequest]) -> None:
    table(["ID", "Reference", "Created", "Student", "Item", "Amount",
           "Status", "Provider", "Posted", "Note"],
          [(r.request_id, r.reference, r.created_at[:16],
            r.student_name or r.student_id, r.description,
            data.money(r.amount_pence), r.status, r.provider,
            "Y" if r.is_posted else "", r.failure_reason or "")
           for r in rows])


def _pick_request(rows: list[data.PaymentRequest]) -> data.PaymentRequest:
    label = choose("Payment", [
        f"{r.request_id} — {r.reference} {r.student_name or r.student_id} "
        f"{data.money(r.amount_pence)} {r.status}" for r in rows[:40]])
    if label is None:
        raise ValueError("No matching payments")
    rid = int(label.split(" — ")[0])
    return next(r for r in rows if r.request_id == rid)


def _pick_item(items: list[data.PayableItem]) -> data.PayableItem:
    label = choose("Item", [
        f"{i} — {it.student_name}: {it.description} "
        f"({'any amount' if it.balance_pence is None else data.money(it.balance_pence)})"
        + (f" [in progress {it.pending_reference}]" if it.pending_reference else "")
        for i, it in enumerate(items, 1)])
    if label is None:
        raise ValueError("Nothing to pay")
    return items[int(label.split(" — ")[0]) - 1]


def _print_state() -> data.ProviderState:
    st = data.provider_state()
    print(f"\n  {st.message}")
    return st


# ── Staff ───────────────────────────────────────────────────────────

def list_flow() -> None:
    status = choose("Status (blank = all)", data.STATUSES, allow_blank=True)
    _show(data.list_requests(status=status, search=ask("Search") or None))
    pause()


def check_flow() -> None:
    r = _pick_request(data.list_requests(status=data.PENDING)
                      + [x for x in data.list_requests(status=data.PAID)
                         if not x.is_posted])
    out = data.check_status(r.request_id)
    print(f"\n  {out.reference}: {out.status}"
          + (f" — {out.failure_reason}" if out.failure_reason else ""))
    pause()


def check_all_flow() -> None:
    c = data.check_pending()
    print(f"\n  Checked {c['checked']}: {c['paid']} paid, {c['failed']} failed,"
          f" {c['still_pending']} still pending, {c['errors']} errors")
    pause()


def offline_flow() -> None:
    sid = pick_student()
    it = _pick_item(data.payable_for_student(sid))
    amount = ask("Amount (£)", default="" if it.balance_pence is None
                 else f"{it.balance_pence / 100:.2f}", required=True)
    method = choose("Method", data.OFFLINE_METHODS, default="Cash")
    ref = ask("Reference (cheque no., bank ref; blank for cash)")
    who = ask("Paid by (name)")
    out = data.record_offline_payment(
        it.item_kind, amount=amount, method=method or "Cash",
        target_id=it.target_id, student_id=it.student_id, reference=ref,
        payer_name=who)
    print(f"\n  ✓ {out.reference} posted"
          + (f"; receipt #{out.receipt_id}" if out.receipt_id else ""))
    pause()


def link_flow() -> None:
    if not _print_state().ready:
        pause()
        return
    sid = pick_student()
    it = _pick_item(data.payable_for_student(sid))
    amount = ask("Amount (£)", default="" if it.balance_pence is None
                 else f"{it.balance_pence / 100:.2f}", required=True)
    out = data.start_payment(data.PAYER_STAFF, None, it.item_kind,
                             amount=amount, target_id=it.target_id,
                             student_id=it.student_id)
    print(f"\n  ✓ {out.reference}: send this link to the family:\n\n"
          f"    {out.checkout_url}\n")
    pause()


def cancel_flow() -> None:
    r = _pick_request(data.list_requests(status=data.PENDING))
    if yes_no(f"Cancel {r.reference}?"):
        out = data.cancel(r.request_id, reason=ask("Reason") or "Cancelled by finance")
        print(f"\n  ✓ {out.reference} {out.status}")
    pause()


def refund_flow() -> None:
    r = _pick_request([x for x in data.list_requests(status=data.PAID)
                       if x.is_posted])
    amount = ask("Amount (£, blank = all remaining)")
    reason = ask("Reason", required=True)
    method = None
    if r.is_offline:
        method = choose("Money given back by", data.OFFLINE_METHODS)
    if yes_no(f"Refund {amount or 'the rest'} on {r.reference}?"):
        out = data.refund(r.request_id, reason=reason, amount=amount or None,
                          method=method)
        print(f"\n  ✓ {out.reference}: refunded {data.money(out.refunded_pence)}"
              f" ({out.status})")
    pause()


def repair_flow() -> None:
    rows = [x for x in data.list_requests(status=data.PAID) if not x.is_posted]
    r = _pick_request(rows)
    out = data.repair(r.request_id)
    print(f"\n  ✓ {out.reference} posted")
    pause()


def recon_flow() -> None:
    rows = data.reconciliation(date_from=ask("From (YYYY-MM-DD)") or None,
                               date_to=ask("To (YYYY-MM-DD)") or None,
                               issues_only=yes_no("Issues only?", default=True))
    table(["Reference", "Status", "Requested", "Provider", "Posted",
           "Receipt", "Issues"],
          [(x.request.reference, x.request.status,
            data.money(x.request.amount_pence),
            data.money(x.request.provider_amount_pence),
            data.money(x.posted_amount_pence), x.receipt_number,
            "; ".join(x.issues)) for x in rows])
    if yes_no("Compare with the provider's records too?"):
        days = ask("Look back (days)", default="7")
        found = data.compare_with_provider(int(days))
        table(["Reference", "Session", "Amount", "Created", "Issue"],
              [(f["reference"], f["session_id"], data.money(f["amount_pence"]),
                f["created_at"], f["issue"]) for f in found])
    pause()


def provider_flow() -> None:
    from education_system.systems.sixth_form.domains.finance.infrastructure.payments import (
        stripe_checkout,
    )
    st = _print_state()
    print(f"  Return address: {st.return_url or '(not set)'}")
    print(f"  Secret key: env {stripe_checkout.ENV_VAR} or file "
          f"{stripe_checkout.secret_file()}")
    if yes_no("Set the return address now?"):
        data.set_return_url(ask("https:// address", default=st.return_url or "",
                                required=True))
        print("  ✓ Saved")
    pause()


def summary_flow() -> None:
    s = data.summary()
    print("\n  Online payments summary")
    for k, v in s.by_status.items():
        print(f"    {k:<12} {v}")
    print(f"\n    Taken      {data.money(s.paid_pence)} "
          f"(card {data.money(s.online_paid_pence)}, offline "
          f"{data.money(s.offline_paid_pence)})")
    print(f"    Refunded   {data.money(s.refunded_pence)}")
    print(f"    Pending    {data.money(s.pending_pence)}")
    print(f"    Issues     {s.issues}")
    pause()


_MENU = [
    ("List payment requests", list_flow),
    ("Check status of a payment", check_flow),
    ("Check all pending payments", check_all_flow),
    ("─" * 6, lambda: None),
    ("Record offline payment", offline_flow),
    ("Card payment link for a family", link_flow),
    ("Cancel a pending payment", cancel_flow),
    ("Refund a payment", refund_flow),
    ("Repair posting", repair_flow),
    ("─" * 6, lambda: None),
    ("Reconciliation", recon_flow),
    ("Provider set-up", provider_flow),
    ("Summary", summary_flow),
]


def online_payments_menu() -> None:
    """Entry point for the main CLI menu."""
    run_menu("Online Payments", _MENU)


def dispatch(label: str) -> bool:
    if label != "Online Payments":
        return False
    try:
        online_payments_menu()
    except Exception as e:
        logger.exception("Online Payments CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        pause()
    return True


# ── Parent / student ────────────────────────────────────────────────

def pay_menu(payer_kind: str, payer_id: Any) -> None:
    """The parent/student "Pay online" menu."""

    def pay() -> None:
        if not _print_state().ready:
            pause()
            return
        it = _pick_item(data.payable_items(payer_kind, payer_id))
        amount = ask("Amount (£)", default="" if it.balance_pence is None
                     else f"{it.balance_pence / 100:.2f}", required=True)
        out = data.start_payment(payer_kind, payer_id, it.item_kind,
                                 amount=amount, target_id=it.target_id,
                                 student_id=it.student_id)
        print(f"\n  Payment {out.reference}: open this page to pay by card:\n\n"
              f"    {out.checkout_url}\n\n"
              "  When you have paid, choose 'Check my payments'.")
        pause()

    def mine() -> None:
        _show(data.requests_for_payer(payer_kind, payer_id))
        pause()

    def check() -> None:
        c = data.check_pending(payer_kind=payer_kind, payer_id=payer_id)
        print(f"\n  {c['paid']} confirmed paid, {c['still_pending']} still "
              f"waiting, {c['failed']} not paid.")
        mine()

    def owed() -> None:
        items = data.payable_items(payer_kind, payer_id)
        table(["Student", "Item", "Owed", "Due", "In progress"],
              [(i.student_name, i.description,
                "any" if i.balance_pence is None else data.money(i.balance_pence),
                i.due_date, i.pending_reference) for i in items])
        pause()

    def cancel() -> None:
        r = _pick_request([x for x in data.requests_for_payer(payer_kind, payer_id)
                           if x.status == data.PENDING])
        if yes_no(f"Cancel {r.reference}?"):
            data.cancel(r.request_id, reason="Cancelled by payer")
            print("  ✓ Cancelled")
        pause()

    _print_state()
    run_menu("Pay Online", [
        ("What I can pay", owed),
        ("Pay by card", pay),
        ("Check my payments", check),
        ("My payments", mine),
        ("Cancel a payment", cancel),
    ])
