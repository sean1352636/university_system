"""CLI flow for Parent Self-Service Requests (Nursery System)."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.nursery.domain.operations.communications.parent_requests import (
    parent_requests as data,
)
from education_system.systems.nursery.domain.operations.communications.parent_requests.parent_requests import (
    CONTACT_FIELDS,
    REQUEST_TYPES,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _safe(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(f"  Validation error: {e}")
        except Exception as e:  # noqa: BLE001
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _show_children() -> None:
    try:
        choices = data.list_pupil_choices()
    except Exception:
        logger.exception("Could not load child choices")
        return
    if choices:
        print("  Children:")
        for _id, label in choices:
            print(f"    {label}")


def _print_table(rows: list[data.ParentRequest]) -> None:
    if not rows:
        print("  (no requests)")
        return
    print(f"  {'ID':<8} {'Child':<20} {'Type':<15} {'Submitted':<20} "
          f"{'Status':<10} {'What was asked for'}")
    print(f"  {'-'*8} {'-'*20} {'-'*15} {'-'*20} {'-'*10} {'-'*40}")
    for r in rows:
        mark = " *" if r.is_open else "  "
        print(f" {mark}{r.request_id:<8} {(r.child_name or r.pupil_id)[:20]:<20} "
              f"{r.request_type:<15} {(r.submitted_at or '')[:19]:<20} "
              f"{r.status:<10} {r.summary_line[:40]}")


def _print_detail(r: data.ParentRequest) -> None:
    print(f"\n  ── Request {r.request_id} ──")
    print(f"  Child:        {r.child_name or '-'} ({r.pupil_id})")
    print(f"  Type:         {r.request_type}")
    print(f"  Submitted by: {r.submitted_by or '-'} at {r.submitted_at}")
    print(f"  Status:       {r.status}")
    print(f"  Asked for:    {r.summary_line}")
    for key, value in r.payload.items():
        print(f"    {key}: {value}")
    if r.decided_at:
        print(f"  Decided by:   {r.decided_by_name or r.decided_by or '-'} "
              f"at {r.decided_at}")
        print(f"  Note:         {r.decision_note or '-'}")
    if r.applied_ref:
        print(f"  Applied as:   {r.applied_ref}")


@_safe
def open_manager() -> None:
    logger.debug("CLI: parent_requests open_manager")
    while True:
        s = data.summary()
        print("\n  ── Parent Self-Service Requests ──")
        print(f"  Pending: {s['pending']}   Approved: {s['approved']}   "
              f"Declined: {s['declined']}   Today: {s['submitted_today']}")
        by_type = ", ".join(f"{t}: {n}" for t, n in s["pending_by_type"].items()
                            if n)
        if by_type:
            print(f"  Waiting on staff — {by_type}")
        if s["overdue"]:
            print(f"  ⚠ {s['overdue']} pending request(s) are for dates that "
                  "have already passed.")
        _print_table(data.list_requests())
        print("\n   V) View    A) Approve (applies it)    D) Decline")
        print("   S) Submit on a parent's behalf    I) Invoices & balance")
        print("   P) Pending only    X) Delete    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "v":
            open_view()
        elif choice == "a":
            open_approve()
        elif choice == "d":
            open_decline()
        elif choice == "s":
            open_submit()
        elif choice == "i":
            open_statement()
        elif choice == "p":
            _print_table(data.pending())
            _prompt("  Press Enter to continue...")
        elif choice == "x":
            open_delete()
        else:
            print("  Invalid selection.")


@_safe
def open_view() -> None:
    rid = _prompt("  Request ID: ")
    r = data.get_request(rid)
    if r is None:
        print("  No request with that ID.")
        return
    _print_detail(r)
    if r.is_open:
        print(f"\n  If approved: {data.preview(rid)}")
    _prompt("  Press Enter to continue...")


@_safe
def open_approve() -> None:
    rid = _prompt("  Request ID to approve: ")
    if not rid:
        print("  Cancelled.")
        return
    r = data.get_request(rid)
    if r is None:
        print("  No request with that ID.")
        return
    print(f"\n  {data.preview(rid)}")
    if _prompt("  Approve and apply? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    staff_id = _prompt("  Your staff ID: ")
    note = _prompt("  Note (optional): ")
    out = data.approve(rid, staff_id or None, note or None)
    print(f"  Approved {out.request_id} — applied as {out.applied_ref}. "
          "Nothing needs re-entering.")


@_safe
def open_decline() -> None:
    rid = _prompt("  Request ID to decline: ")
    if not rid:
        print("  Cancelled.")
        return
    staff_id = _prompt("  Your staff ID: ")
    note = _prompt("  Reason for the parent: ")
    out = data.decline(rid, staff_id or None, note or None)
    print(f"  Declined {out.request_id}.")


@_safe
def open_delete() -> None:
    rid = _prompt("  Request ID to delete: ")
    if not rid:
        print("  Cancelled.")
        return
    if data.get_request(rid) is None:
        print("  No request with that ID.")
        return
    if _prompt(f"  Delete {rid}? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    print(f"  Deleted {rid}." if data.delete_request(rid)
          else "  Could not delete (already removed?).")


@_safe
def open_statement() -> None:
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    st = data.statement(pid)
    print(f"\n  ── Account for {pid} ──")
    if st["invoices"]:
        print(f"  {'Invoice':<10} {'Period':<14} {'Issued':<12} {'Total':<10} "
              f"{'Status'}")
        for inv in st["invoices"]:
            print(f"  {inv['invoice_id']:<10} {(inv.get('period') or '-'):<14} "
                  f"{(inv.get('issue_date') or '-'):<12} "
                  f"£{float(inv.get('total_amount') or 0):<9.2f} "
                  f"{inv.get('status')}")
    else:
        print("  (no invoices)")
    print(f"\n  Invoiced: £{st['total_invoiced']:.2f}   "
          f"Paid: £{st['total_paid']:.2f}   "
          f"Balance: £{st['balance']:.2f}")
    _prompt("  Press Enter to continue...")


# ── Submitting on a parent's behalf (phone call, paper form) ─────────────────

@_safe
def open_submit() -> None:
    print("\n  ── Log a Parent Request ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    print(f"  Types: {', '.join(REQUEST_TYPES)}")
    rtype = _prompt("  Request type: ").lower()
    if rtype not in REQUEST_TYPES:
        print("  Invalid request type.")
        return

    payload: dict[str, str] = {}
    if rtype == "session":
        payload["session_date"] = _prompt("  Session date (YYYY-MM-DD): ")
        payload["session_type"] = _prompt(
            "  Session (am/pm/all-day) [all-day]: ") or "all-day"
        payload["kind"] = _prompt("  Kind (extra/cancellation) [extra]: ") \
            or "extra"
        payload["room"] = _prompt("  Room (optional): ")
        payload["reason"] = _prompt("  Reason: ")
    elif rtype == "absence":
        payload["absence_date"] = _prompt("  Absence date (YYYY-MM-DD): ")
        payload["status"] = _prompt(
            "  Status (absent/sick/holiday) [sick]: ") or "sick"
        payload["reason"] = _prompt("  Reason: ")
        payload["expected_return"] = _prompt("  Expected back (optional): ")
    elif rtype == "contact-update":
        for field in CONTACT_FIELDS:
            value = _prompt(f"  New {field.replace('_', ' ')} (blank = skip): ")
            if value:
                payload[field] = value
    elif rtype == "consent":
        payload["consent_type"] = _prompt("  Consent type: ")
        payload["consent_status"] = _prompt(
            "  Answer (granted/refused) [granted]: ") or "granted"
        payload["expiry_date"] = _prompt("  Expiry (optional): ")
    else:
        payload["message"] = _prompt("  Message: ")

    submitted_by = _prompt("  Parent name: ")
    r = data.submit({"pupil_id": pid, "request_type": rtype,
                     "payload": {k: v for k, v in payload.items() if v},
                     "submitted_by": submitted_by or None})
    print(f"\n  Logged request {r.request_id} — {r.summary_line}")


_DISPATCH = {"Parent Self-Service Requests": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching parent_requests CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
