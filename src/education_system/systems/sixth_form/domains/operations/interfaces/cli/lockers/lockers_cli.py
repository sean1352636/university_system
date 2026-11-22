"""CLI flows for Sixth Form Lockers."""

from __future__ import annotations

import logging
from typing import Callable

from education_system.systems.sixth_form.domains.operations.domain.lockers import (
    lockers as data,
)
from education_system.systems.sixth_form.interfaces.cli.operations._ops_cli import (
    ask,
    ask_int,
    choose,
    pause,
    pick_student,
    run_menu,
    table,
    yes_no,
)

logger = logging.getLogger(__name__)


def _pick_bank() -> int:
    banks = data.list_banks()
    label = choose("Bank", [f"{b.bank_id} — {b.name}" for b in banks])
    if label is None:
        raise ValueError("Create a locker bank first")
    return int(label.split(" — ")[0])


def _pick_locker(status: str | None = None) -> int:
    bank_id = _pick_bank()
    rows = data.list_lockers(bank_id=bank_id, status=status)
    label = choose("Locker", [f"{lk.locker_id} — {lk.number} ({lk.status})"
                              for lk in rows])
    if label is None:
        raise ValueError("No matching lockers in that bank")
    return int(label.split(" — ")[0])


def _pick_allocation(active_only: bool = True) -> int:
    sid = ask("Student id (blank = choose from list)")
    rows = data.list_allocations(student_id=sid or None,
                                 active_only=active_only)
    label = choose("Allocation", [
        f"{a.allocation_id} — {a.locker_label} · {a.student_id} "
        f"{a.student_name or ''} · {a.academic_year} · {a.status}"
        for a in rows])
    if label is None:
        raise ValueError("No matching allocations")
    return int(label.split(" — ")[0])


def _show_allocations(rows) -> None:
    table(["ID", "Locker", "Student", "Name", "Year", "Allocated", "Key",
           "Code", "Deposit", "Dep. status", "Status", "Returned",
           "Condition"],
          [(a.allocation_id, a.locker_label, a.student_id, a.student_name,
            a.academic_year, a.allocated_on, "Y" if a.key_issued else "N",
            a.code_issued, f"£{a.deposit_amount:.2f}", a.deposit_status,
            a.status, a.returned_on, a.return_condition) for a in rows])


# ── Banks ───────────────────────────────────────────────────────────

def list_banks() -> None:
    table(["ID", "Name", "Location", "Size", "Active"],
          [(b.bank_id, b.name, b.location, b.locker_size,
            "Y" if b.active else "N") for b in data.list_banks()])
    pause()


def new_bank() -> None:
    b = data.create_bank({
        "name": ask("Bank name", required=True),
        "location": ask("Location"),
        "locker_size": choose("Locker size", data.LOCKER_SIZES,
                              default=data.DEFAULT_LOCKER_SIZE),
        "notes": ask("Notes"),
    })
    print(f"\n  ✓ Created bank #{b.bank_id} {b.name}")
    if yes_no("Add numbered lockers now?", default=True):
        _add_run(b.bank_id)
    pause()


def edit_bank() -> None:
    b = data.get_bank(_pick_bank())
    out = data.update_bank(b.bank_id, {
        "name": ask("Bank name", default=b.name),
        "location": ask("Location", default=b.location or ""),
        "locker_size": choose("Locker size", data.LOCKER_SIZES,
                              default=b.locker_size),
        "active": yes_no("Active", default=b.active),
        "notes": ask("Notes", default=b.notes or ""),
    })
    print(f"\n  ✓ Updated {out.name}")
    pause()


def _add_run(bank_id: int) -> None:
    prefix = ask("Number prefix (e.g. A)")
    first = ask_int("First number", default=1)
    count = ask_int("How many", default=10)
    width = ask_int("Zero-pad to width (0 = none)", default=0)
    made = data.add_lockers(bank_id, first, count, prefix=prefix,
                            width=width)
    print(f"\n  ✓ Added {len(made)} locker(s)")


def add_lockers() -> None:
    _add_run(_pick_bank())
    pause()


def delete_bank() -> None:
    bid = _pick_bank()
    if yes_no("Delete this (empty) bank?"):
        data.delete_bank(bid)
        print("\n  ✓ Deleted")
    pause()


# ── Lockers ─────────────────────────────────────────────────────────

def list_lockers() -> None:
    status = choose("Status filter", data.LOCKER_STATUSES, allow_blank=True)
    active = {a.locker_id: a for a in data.list_allocations(
        active_only=True)}
    rows = data.list_lockers(status=status)
    table(["ID", "Bank", "Number", "Code", "Key", "Status", "Holder"],
          [(lk.locker_id, lk.bank_name, lk.number, lk.code, lk.key_number,
            lk.status,
            (f"{active[lk.locker_id].student_id} "
             f"{active[lk.locker_id].student_name or ''}")
            if lk.locker_id in active else "") for lk in rows])
    pause()


def new_locker() -> None:
    lk = data.create_locker({
        "bank_id": _pick_bank(),
        "number": ask("Locker number", required=True),
        "code": ask("Combination code"),
        "key_number": ask("Key number"),
        "notes": ask("Notes"),
    })
    print(f"\n  ✓ Created locker {lk.label}")
    pause()


def edit_locker() -> None:
    lk = data.get_locker(_pick_locker())
    out = data.update_locker(lk.locker_id, {
        "number": ask("Locker number", default=lk.number),
        "code": ask("Combination code", default=lk.code or ""),
        "key_number": ask("Key number", default=lk.key_number or ""),
        "notes": ask("Notes", default=lk.notes or ""),
    })
    print(f"\n  ✓ Updated {out.label}")
    pause()


def out_of_order() -> None:
    lk = data.get_locker(_pick_locker())
    new = (data.AVAILABLE if lk.status == data.OUT_OF_ORDER
           else data.OUT_OF_ORDER)
    if yes_no(f"Mark {lk.label} {new}?", default=True):
        data.set_locker_status(lk.locker_id, new)
        print("\n  ✓ Done")
    pause()


def delete_locker() -> None:
    lid = _pick_locker()
    if yes_no("Delete this locker?"):
        data.delete_locker(lid)
        print("\n  ✓ Deleted")
    pause()


# ── Allocations ─────────────────────────────────────────────────────

def allocate() -> None:
    lid = _pick_locker(status=data.AVAILABLE)
    lk = data.get_locker(lid)
    sid = pick_student()
    a = data.allocate(
        lid, sid,
        academic_year=ask("Academic year",
                          default=data.current_academic_year()),
        deposit_amount=float(ask("Deposit £",
                                 default=f"{data.DEFAULT_DEPOSIT:.2f}")),
        deposit_paid=yes_no("Deposit paid now?"),
        key_issued=yes_no("Key issued now?"),
        code=ask("Code given to student", default=lk.code or ""),
        allocated_by=ask("Allocated by"),
        notes=ask("Notes"))
    print(f"\n  ✓ {a.locker_label} allocated to {a.student_id} "
          f"for {a.academic_year} (deposit {a.deposit_status})")
    pause()


def list_allocations() -> None:
    year = ask("Academic year (blank = all)")
    _show_allocations(data.list_allocations(
        academic_year=year or None,
        active_only=yes_no("Active only?", default=True)))
    pause()


def student_locker() -> None:
    sid = pick_student()
    _show_allocations(data.list_allocations(student_id=sid))
    pause()


def deposit_paid() -> None:
    a = data.record_deposit_paid(_pick_allocation())
    print(f"\n  ✓ Deposit £{a.deposit_amount:.2f} recorded as paid")
    pause()


def key_issued() -> None:
    aid = _pick_allocation()
    code = ask("Code given (blank = unchanged)")
    data.issue_key(aid, key_issued=True, code=code or None)
    print("\n  ✓ Key / code recorded")
    pause()


def return_locker() -> None:
    aid = _pick_allocation()
    a = data.get_allocation(aid)
    cond = choose("Condition", data.RETURN_CONDITIONS, default="Good")
    refund = True
    reason = None
    if a.deposit_status == data.DEPOSIT_PAID:
        refund = yes_no(f"Refund deposit £{a.deposit_amount:.2f}?",
                        default=True)
        if not refund:
            reason = ask("Reason for retaining", required=True)
    out = data.return_locker(aid, returned_on=ask("Returned on "
                                                  "(blank = today)") or None,
                             condition=cond, refund_deposit=refund,
                             retain_reason=reason, notes=ask("Notes"))
    print(f"\n  ✓ Returned ({out.return_condition}); deposit "
          f"{out.deposit_status}")
    pause()


def overdue() -> None:
    year = ask("All still out for academic year (blank = past year end)")
    _show_allocations(data.overdue_returns(academic_year=year or None))
    pause()


def summary_flow() -> None:
    s = data.summary()
    print("\n═══ Lockers Summary ═══")
    print(f"  Banks:              {s.banks}")
    print(f"  Lockers:            {s.lockers}")
    for k, v in s.by_status.items():
        print(f"    {k:<16} {v}")
    print(f"  Active allocations: {s.active_allocations}")
    print(f"  Overdue returns:    {s.overdue_returns}")
    print(f"  Deposits held:      £{s.deposits_held:.2f}")
    print(f"  Deposits due:       {s.deposits_due}")
    print(f"  Deposits retained:  £{s.deposits_retained:.2f}")
    pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List lockers",            list_lockers),
    ("List allocations",        list_allocations),
    ("Student's locker",        student_locker),
    ("Overdue returns",         overdue),
    ("─" * 6,                   lambda: None),
    ("Allocate locker",         allocate),
    ("Record deposit paid",     deposit_paid),
    ("Record key / code issued", key_issued),
    ("Return locker",           return_locker),
    ("─" * 6,                   lambda: None),
    ("List banks",              list_banks),
    ("New bank",                new_bank),
    ("Edit bank",               edit_bank),
    ("Add numbered lockers",    add_lockers),
    ("Delete bank",             delete_bank),
    ("New locker",              new_locker),
    ("Edit locker",             edit_locker),
    ("Out of order / back in use", out_of_order),
    ("Delete locker",           delete_locker),
    ("─" * 6,                   lambda: None),
    ("Summary",                 summary_flow),
]


def run() -> None:
    run_menu("Lockers", _MENU)


def lockers_menu() -> None:
    """Entry point for the main CLI menu."""
    run()


def dispatch(label: str) -> bool:
    if label != "Lockers":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Lockers CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        pause()
    return True
