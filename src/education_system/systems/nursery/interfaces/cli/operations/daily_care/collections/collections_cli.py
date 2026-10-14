"""CLI flow for Collections & Late Pickup (Nursery System)."""

from __future__ import annotations

import functools
import getpass
import logging
from typing import Callable

from education_system.systems.nursery.domain.operations.daily_care.collections import (
    collections as data,
)
from education_system.systems.nursery.domain.operations.daily_care.collections.collections import (
    ESCALATION_STAGES,
    FEE_STATUSES,
    RELATIONSHIPS,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _secret(msg: str) -> str:
    """Read a collection password without echoing it to the terminal."""
    try:
        return getpass.getpass(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""
    except Exception:  # noqa: BLE001 — no tty (piped input): fall back to input
        logger.debug("getpass unavailable; falling back to input", exc_info=True)
        return _prompt(msg)


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


def _ask(label: str, current=None) -> str:
    cur = "" if current is None else str(current)
    suffix = f" [{cur}]" if cur else ""
    v = _prompt(f"  {label}{suffix}: ")
    return v if v else cur


def _ask_bool(label: str, current: bool | None) -> str:
    cur = "" if current is None else ("y" if current else "n")
    suffix = f" [{cur}]" if cur else ""
    v = _prompt(f"  {label} (y/n){suffix}: ").lower()
    return v if v else cur


def _yn(flag: bool) -> str:
    return "Yes" if flag else "No"


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


@_safe
def open_manager() -> None:
    logger.debug("CLI: collections open_manager")
    while True:
        s = data.summary()
        print("\n  ── Collections & Late Pickup ──")
        print(f"  Authorised collectors: {s['collectors']} "
              f"({s['active_collectors']} in date, {s['revoked_collectors']} "
              f"revoked, {s['with_password']} with a password)")
        print(f"  Late collections today: {s['late_today']}   "
              f"This month: {s['late_this_month']}   "
              f"Escalated: {s['escalations_this_month']}   "
              f"Fees outstanding: £{s['fees_outstanding']:.2f}")
        if s["children_without_collectors"]:
            print(f"  ⚠ {s['children_without_collectors']} active child(ren) "
                  "have nobody authorised to collect them.")
        if s["id_unchecked"]:
            print(f"  ⚠ {s['id_unchecked']} active collector(s) have no photo "
                  "ID check recorded.")
        print("\n   V) Verify someone at the door    A) Authorised collectors")
        print("   L) Late collection log    G) Children with no collector")
        print("   0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "v":
            open_verify()
        elif choice == "a":
            open_collectors()
        elif choice == "l":
            open_late_log()
        elif choice == "g":
            open_gaps()
        else:
            print("  Invalid selection.")


# ── Door check ───────────────────────────────────────────────────────────────

@_safe
def open_verify() -> None:
    print("\n  ── Verify a Collector ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    listed = data.list_collectors(pupil_id=pid)
    if listed:
        print("  On the authorised list:")
        for c in listed:
            marks = []
            if c.has_password:
                marks.append("password")
            if c.status == "revoked":
                marks.append("REVOKED")
            suffix = f"  [{', '.join(marks)}]" if marks else ""
            print(f"    {c.full_name} ({c.relationship or '-'}){suffix}")
    name = _prompt("  Name of the person collecting: ")
    if not name:
        print("  Cancelled.")
        return

    result = data.verify_collector(pid, name)
    if result.password_required:
        pw = _secret("  Collection password: ")
        result = data.verify_collector(pid, name, pw)

    print()
    if result.allowed:
        print(f"  ✔ ALLOWED — {result.reason}")
    else:
        print(f"  ✘ DO NOT RELEASE THE CHILD — {result.reason}")
        print("  Contact the parent and follow the setting's collection policy.")
    _prompt("  Press Enter to continue...")


# ── Authorised collectors ────────────────────────────────────────────────────

def _print_collectors(rows: list[data.Collector]) -> None:
    if not rows:
        print("  (no authorised collectors)")
        return
    print(f"  {'ID':<8} {'Child':<20} {'Name':<22} {'Relationship':<16} "
          f"{'Phone':<15} {'Pwd':<5} {'ID':<4} {'Esc':<5} {'Status'}")
    print(f"  {'-'*8} {'-'*20} {'-'*22} {'-'*16} {'-'*15} {'-'*5} {'-'*4} "
          f"{'-'*5} {'-'*8}")
    for c in rows:
        print(f"  {c.collector_id:<8} {(c.child_name or c.pupil_id)[:20]:<20} "
              f"{c.full_name[:22]:<22} {(c.relationship or '-')[:16]:<16} "
              f"{(c.phone or '-')[:15]:<15} {_yn(c.has_password):<5} "
              f"{_yn(c.id_checked):<4} {_yn(c.is_escalation_contact):<5} "
              f"{c.status}")


@_safe
def open_collectors() -> None:
    while True:
        print("\n  ── Authorised Collectors ──")
        _print_collectors(data.list_collectors())
        print("\n   A) Add    E) Edit    P) Set collection password")
        print("   R) Revoke    D) Delete    C) For a child    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_add_collector()
        elif choice == "e":
            open_edit_collector()
        elif choice == "p":
            open_set_password()
        elif choice == "r":
            open_revoke_collector()
        elif choice == "d":
            open_delete_collector()
        elif choice == "c":
            pid = _prompt("  Child ID: ")
            _print_collectors(data.list_collectors(pupil_id=pid))
            _prompt("  Press Enter to continue...")
        else:
            print("  Invalid selection.")


def _collect_collector(existing: data.Collector | None = None,
                       *, pupil_id: str | None = None) -> dict[str, str]:
    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    fields["full_name"] = _ask("Full name",
                               existing.full_name if existing else None)
    fields["relationship"] = _ask(f"Relationship ({'/'.join(RELATIONSHIPS)})",
                                  existing.relationship if existing else None)
    fields["phone"] = _ask("Phone", existing.phone if existing else None)
    fields["photo_on_file"] = _ask_bool(
        "Photo on file?", existing.photo_on_file if existing else None)
    fields["id_checked"] = _ask_bool(
        "Photo ID checked?", existing.id_checked if existing else None)
    fields["is_escalation_contact"] = _ask_bool(
        "Escalation contact (call if the parent can't be reached)?",
        existing.is_escalation_contact if existing else None)
    fields["valid_from"] = _ask("Authorised from (YYYY-MM-DD, blank = always)",
                                existing.valid_from if existing else None)
    fields["valid_until"] = _ask("Authorised until (blank = open-ended)",
                                 existing.valid_until if existing else None)
    fields["status"] = _ask("Status (active/revoked)",
                            existing.status if existing else "active")
    fields["notes"] = _ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_add_collector() -> None:
    print("\n  ── Add Authorised Collector ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    fields = _collect_collector(pupil_id=pid)
    pw = _secret("  Collection password (blank for none): ")
    if pw:
        fields["password"] = pw
    c = data.create_collector(fields)
    print(f"\n  Added {c.full_name} ({c.collector_id}) as an authorised "
          f"collector for {c.child_name or pid}.")


@_safe
def open_edit_collector() -> None:
    cid = _prompt("  Collector ID: ")
    if not cid:
        print("  Cancelled.")
        return
    existing = data.get_collector(cid)
    if existing is None:
        print("  No collector with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    c = data.update_collector(cid, _collect_collector(existing))
    print(f"\n  Updated collector {c.collector_id}.")


@_safe
def open_set_password() -> None:
    cid = _prompt("  Collector ID: ")
    if not cid:
        print("  Cancelled.")
        return
    existing = data.get_collector(cid)
    if existing is None:
        print("  No collector with that ID.")
        return
    pw = _secret(f"  New collection password for {existing.full_name}: ")
    if not pw:
        print("  Cancelled.")
        return
    if _secret("  Confirm password: ") != pw:
        print("  Passwords did not match — nothing changed.")
        return
    data.set_collection_password(cid, pw)
    print(f"  Collection password set for {existing.full_name}.")


@_safe
def open_revoke_collector() -> None:
    cid = _prompt("  Collector ID to revoke: ")
    if not cid:
        print("  Cancelled.")
        return
    existing = data.get_collector(cid)
    if existing is None:
        print("  No collector with that ID.")
        return
    reason = _prompt("  Reason: ")
    c = data.revoke_collector(cid, reason or None)
    print(f"  {c.full_name} may no longer collect "
          f"{c.child_name or c.pupil_id}.")


@_safe
def open_delete_collector() -> None:
    cid = _prompt("  Collector ID to delete: ")
    if not cid:
        print("  Cancelled.")
        return
    existing = data.get_collector(cid)
    if existing is None:
        print("  No collector with that ID.")
        return
    print("  Revoking keeps the audit trail; deleting does not.")
    if _prompt(f"  Delete {existing.full_name} ({cid})? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    print(f"  Deleted collector {cid}." if data.delete_collector(cid)
          else "  Could not delete (already removed?).")


# ── Late collection log ──────────────────────────────────────────────────────

def _print_late(rows: list[data.LateCollection]) -> None:
    if not rows:
        print("  (no late collections logged)")
        return
    print(f"  {'ID':<8} {'Child':<20} {'Date':<11} {'Due':<6} {'Got':<6} "
          f"{'Late':<6} {'Fee':<8} {'Fee sts':<9} {'Escalation'}")
    print(f"  {'-'*8} {'-'*20} {'-'*11} {'-'*6} {'-'*6} {'-'*6} {'-'*8} "
          f"{'-'*9} {'-'*24}")
    for r in rows:
        flag = " !" if r.safeguarding_referral else ""
        print(f"  {r.record_id:<8} {(r.child_name or r.pupil_id)[:20]:<20} "
              f"{r.event_date:<11} {r.due_time:<6} "
              f"{(r.collected_time or '-'):<6} {str(r.minutes_late) + 'm':<6} "
              f"{'£' + format(r.fee_amount, '.2f'):<8} {r.fee_status:<9} "
              f"{r.escalation_stage}{flag}")


@_safe
def open_late_log() -> None:
    while True:
        print("\n  ── Late Collection Log ──")
        _print_late(data.list_late_collections())
        print("\n   A) Log a late collection    C) Mark as collected")
        print("   E) Edit    W) Waive fee    D) Delete    0) Back")
        choice = _prompt("  Select: ").lower()
        if choice in ("0", ""):
            return
        if choice == "a":
            open_log_late()
        elif choice == "c":
            open_close_late()
        elif choice == "e":
            open_edit_late()
        elif choice == "w":
            open_waive_fee()
        elif choice == "d":
            open_delete_late()
        else:
            print("  Invalid selection.")


def _collect_late(existing: data.LateCollection | None = None,
                  *, pupil_id: str | None = None) -> dict[str, str]:
    fields: dict[str, str] = {}
    if pupil_id is not None:
        fields["pupil_id"] = pupil_id
    fields["event_date"] = _ask("Date (YYYY-MM-DD)",
                                existing.event_date if existing else data._today())
    fields["due_time"] = _ask("Booked collection time (HH:MM)",
                              existing.due_time if existing else None)
    fields["collected_time"] = _ask(
        "Actually collected at (HH:MM, blank = still here)",
        existing.collected_time if existing else None)
    fields["collected_by"] = _ask("Collected by",
                                  existing.collected_by if existing else None)
    fields["fee_amount"] = _ask(
        "Fee (blank = auto from policy)",
        existing.fee_amount if existing else None)
    fields["fee_status"] = _ask(f"Fee status ({'/'.join(FEE_STATUSES)})",
                                existing.fee_status if existing else "due")
    fields["escalation_stage"] = _ask(
        f"Escalation ({'/'.join(ESCALATION_STAGES)}, blank = auto)",
        existing.escalation_stage if existing else None)
    fields["escalated_to"] = _ask("Escalated to (name)",
                                  existing.escalated_to if existing else None)
    fields["parent_contacted"] = _ask_bool(
        "Parent contacted?", existing.parent_contacted if existing else None)
    fields["safeguarding_referral"] = _ask_bool(
        "Safeguarding referral made?",
        existing.safeguarding_referral if existing else None)
    fields["recorded_by"] = _ask("Recorded by (staff ID)",
                                 existing.recorded_by if existing else None)
    fields["notes"] = _ask("Notes", existing.notes if existing else None)
    return fields


@_safe
def open_log_late() -> None:
    print("\n  ── Log a Late Collection ──")
    _show_children()
    pid = _prompt("  Child ID: ")
    if not pid:
        print("  Cancelled.")
        return
    r = data.log_late_collection(_collect_late(pupil_id=pid))
    print(f"\n  Logged {r.record_id} — {r.child_name or pid} was "
          f"{r.minutes_late} minutes late. Fee £{r.fee_amount:.2f}, "
          f"escalation '{r.escalation_stage}'.")
    if r.minutes_late >= 60:
        print("  This is over an hour — check the uncollected-child procedure "
              "has been followed and the DSL informed.")


@_safe
def open_close_late() -> None:
    rid = _prompt("  Record ID: ")
    if not rid:
        print("  Cancelled.")
        return
    when = _prompt("  Collected at (HH:MM, blank = now): ")
    who = _prompt("  Collected by: ")
    r = data.close_late_collection(rid, when or None, who or None)
    print(f"  {r.child_name or r.pupil_id} collected at {r.collected_time} — "
          f"{r.minutes_late} minutes late, fee £{r.fee_amount:.2f}.")


@_safe
def open_edit_late() -> None:
    rid = _prompt("  Record ID: ")
    if not rid:
        print("  Cancelled.")
        return
    existing = data.get_late_collection(rid)
    if existing is None:
        print("  No record with that ID.")
        return
    print("  Press Enter to keep the existing value.")
    r = data.update_late_collection(rid, _collect_late(existing))
    print(f"\n  Updated late collection {r.record_id}.")


@_safe
def open_waive_fee() -> None:
    rid = _prompt("  Record ID: ")
    if not rid:
        print("  Cancelled.")
        return
    reason = _prompt("  Reason for waiving: ")
    r = data.waive_fee(rid, reason or None)
    print(f"  Fee of £{r.fee_amount:.2f} on {r.record_id} waived.")


@_safe
def open_delete_late() -> None:
    rid = _prompt("  Record ID to delete: ")
    if not rid:
        print("  Cancelled.")
        return
    if data.get_late_collection(rid) is None:
        print("  No record with that ID.")
        return
    if _prompt(f"  Delete {rid}? (y/N): ").lower() != "y":
        print("  Cancelled.")
        return
    print(f"  Deleted {rid}." if data.delete_late_collection(rid)
          else "  Could not delete (already removed?).")


@_safe
def open_gaps() -> None:
    rows = data.children_without_collectors()
    print("\n  ── Children With No Authorised Collector ──")
    if not rows:
        print("  Every active child has someone authorised to collect them.")
    else:
        for pid, name in rows:
            print(f"    {name} ({pid})")
    _prompt("  Press Enter to continue...")


_DISPATCH = {"Collections & Late Pickup": open_manager}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching collections CLI label: %s", label)
    handler()
    return True


def run(auth=None) -> None:
    open_manager()
