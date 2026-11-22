"""CLI flows: device loans and the IT acceptable-use policy."""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Callable

from education_system.systems.sixth_form.domains.operations.domain.device_loans import (
    acceptable_use as aup,
)
from education_system.systems.sixth_form.domains.operations.domain.device_loans import (
    device_loans as data,
)
from education_system.systems.sixth_form.interfaces.cli.operations._ops_cli import (
    ask,
    choose,
    pause,
    pick_staff,
    pick_student,
    run_menu,
    table,
    yes_no,
)

logger = logging.getLogger(__name__)


def _today() -> str:
    return _dt.date.today().isoformat()


def _show_devices(rows) -> None:
    table(["Asset", "Tag", "Name", "Pool", "Condition", "Status", "Charger",
           "On loan to", "Due"],
          [(d.asset_id, d.asset_tag, d.name, d.loan_pool, d.condition,
            d.asset_status, "Y" if d.includes_charger else "N",
            d.borrower or "", d.due_on or "") for d in rows])


def _show_loans(rows) -> None:
    today = _today()
    table(["Loan", "Device", "Borrower", "Issued", "Due", "Status",
           "Back/lost", "Bursary", "Charge", "AUP"],
          [(ln.loan_id, ln.device_label,
            f"{ln.borrower_id} {ln.borrower_name or ''}", ln.issued_on,
            ln.due_on + (" !" if ln.is_overdue(today) else ""), ln.status,
            ln.returned_on or ln.lost_on, "Y" if ln.bursary_funded else "",
            f"£{ln.charge_amount:.2f} {ln.charge_status}"
            if ln.charge_amount else "", ln.aup_version) for ln in rows])


def _pick_device(available: bool = False) -> int:
    rows = data.list_devices(available_only=available)
    label = choose("Device", [f"{d.asset_id} — {d.label} ({d.asset_status})"
                              for d in rows])
    if label is None:
        raise ValueError("No matching devices in the pool")
    return int(label.split(" — ")[0])


def _pick_loan(open_only: bool = True) -> int:
    who = ask("Student / staff id (blank = choose from list)")
    rows = data.list_loans(
        student_id=who if who and not who.upper().startswith("T") else None,
        staff_id=who if who.upper().startswith("T") else None,
        open_only=open_only)
    label = choose("Loan", [f"{ln.loan_id} — {ln.device_label} · "
                            f"{ln.borrower_id} · due {ln.due_on} · "
                            f"{ln.status}" for ln in rows[:60]])
    if label is None:
        raise ValueError("No matching loans")
    return int(label.split(" — ")[0])


# ── Devices ─────────────────────────────────────────────────────────

def list_devices() -> None:
    _show_devices(data.list_devices(available_only=yes_no(
        "Available only?")))
    pause()


def _pool_answers(d=None) -> dict:
    return {
        "loan_pool": ask("Loan pool", default=d.loan_pool if d
                         else data.DEFAULT_POOL),
        "includes_charger": yes_no("Goes out with a charger?",
                                   default=d.includes_charger if d else True),
        "accessories": ask("Other accessories",
                           default=(d.accessories or "") if d else ""),
        "default_loan_days": ask("Usual loan length (days)",
                                 default=str(d.default_loan_days if d
                                             else data.DEFAULT_LOAN_DAYS)),
    }


def register_device() -> None:
    from education_system.systems.sixth_form.domains.operations.domain.assets import (
        assets as _assets,
    )
    d = data.register_device({
        "asset_tag": ask("Asset tag", required=True),
        "name": ask("Name", required=True),
        "category": choose("Category", _assets.CATEGORIES,
                           default=data.DEFAULT_CATEGORY),
        "manufacturer": ask("Manufacturer"), "model": ask("Model"),
        "serial_number": ask("Serial number"),
        "location": ask("Kept at", required=True),
        "condition": choose("Condition", data.conditions(), default="Good"),
        **_pool_answers()})
    print(f"\n  ✓ {d.label} added to the {d.loan_pool} pool")
    pause()


def add_existing() -> None:
    options = [f"{a.asset_id} — {a.asset_tag} {a.name} ({a.category})"
               for a in data.assets_not_in_pool()]
    label = choose("Asset", options)
    if label is None:
        raise ValueError("No assets to add")
    d = data.add_to_pool(int(label.split(" — ")[0]), _pool_answers())
    print(f"\n  ✓ {d.label} added")
    pause()


def edit_device() -> None:
    d = data.get_device(_pick_device())
    payload = _pool_answers(d)
    payload["loanable"] = yes_no("Available for loan?", default=d.loanable)
    data.update_device(d.asset_id, payload)
    print("\n  ✓ Updated")
    pause()


def repair() -> None:
    d = data.get_device(_pick_device())
    if d.asset_status == "Awaiting Repair":
        data.send_for_repair(d.asset_id, repaired=True,
                             notes=ask("What was done"))
        print("\n  ✓ Back in storage")
    else:
        data.send_for_repair(d.asset_id)
        print("\n  ✓ Awaiting repair")
    pause()


def remove_device() -> None:
    d = data.get_device(_pick_device())
    if yes_no(f"Take {d.label} out of the pool?"):
        gone = data.remove_from_pool(d.asset_id)
        print("\n  ✓ Removed" if gone else
              "\n  ✓ Has loan history — marked not available")
    pause()


def device_history() -> None:
    _show_loans(data.device_history(_pick_device()))
    pause()


# ── Loans ───────────────────────────────────────────────────────────

def issue() -> None:
    aid = _pick_device(available=True)
    d = data.get_device(aid)
    btype = choose("Borrower is a", data.BORROWER_TYPES,
                   default=data.STUDENT)
    payload: dict = {"borrower_type": btype}
    if btype == data.STUDENT:
        payload["student_id"] = pick_student()
        awards = data.bursary_awards_for(payload["student_id"])
        if awards and yes_no("Funded by a bursary award?"):
            label = choose("Award", [f"{a.application_id} — {a.bursary_type}"
                                     f" {a.academic_year or ''}"
                                     for a in awards])
            payload["bursary_application_id"] = (label or "").split(" — ")[0]
    else:
        payload["staff_id"] = pick_staff()
    payload.update({
        "due_on": ask("Due back (YYYY-MM-DD, blank = usual length)") or None,
        "condition_out": choose("Condition out", data.conditions(),
                                default=d.condition),
        "charger_issued": yes_no("Charger issued?",
                                 default=d.includes_charger),
        "notes": ask("Notes"),
    })
    ln = data.issue_loan(aid, payload)
    print(f"\n  ✓ Loan #{ln.loan_id}: {ln.device_label} to {ln.borrower_id} "
          f"until {ln.due_on} (AUP v{ln.aup_version})")
    pause()


def list_loans() -> None:
    _show_loans(data.list_loans(open_only=yes_no("Open only?",
                                                 default=True)))
    pause()


def overdue() -> None:
    _show_loans(data.overdue_loans())
    pause()


def borrower_loans() -> None:
    if choose("Borrower is a", data.BORROWER_TYPES,
              default=data.STUDENT) == data.STUDENT:
        _show_loans(data.loans_for_student(pick_student()))
    else:
        _show_loans(data.loans_for_staff(pick_staff()))
    pause()


def extend() -> None:
    lid = _pick_loan()
    data.extend_loan(lid, ask("New due date", required=True),
                     reason=ask("Reason"))
    print("\n  ✓ Extended")
    pause()


def return_device() -> None:
    lid = _pick_loan()
    ln = data.get_loan(lid)
    cond = choose("Condition", data.conditions(), default=ln.condition_out)
    out = data.return_loan(
        lid, returned_on=ask("Returned on", default=_today()),
        condition_in=cond,
        charger_returned=yes_no("Charger back?", default=True)
        if ln.charger_issued else None,
        damage_notes=ask("Describe the damage", required=True)
        if cond == "Damaged" else None,
        charge_amount=ask("Charge to borrower £ (blank = none)") or None,
        notes=ask("Notes"))
    print(f"\n  ✓ {out.status}; charge {out.charge_status}")
    pause()


def lost() -> None:
    lid = _pick_loan()
    data.report_lost(lid, lost_on=ask("Lost on", default=_today()),
                     charge_amount=ask("Charge £ (blank = none)") or None,
                     notes=ask("What happened"))
    print("\n  ✓ Recorded as lost; asset marked Lost/Stolen")
    pause()


def found() -> None:
    rows = data.list_loans(status=data.LOST)
    label = choose("Lost loan", [f"{ln.loan_id} — {ln.device_label} · "
                                 f"{ln.borrower_id}" for ln in rows])
    if label is None:
        raise ValueError("No lost devices")
    lid = int(label.split(" — ")[0])
    data.mark_found(lid, condition_in=choose("Condition", data.conditions(),
                                             default="Good"),
                    notes=ask("Notes"))
    print("\n  ✓ Back in storage")
    pause()


def charges() -> None:
    rows = data.list_loans(charge_status=data.CHARGE_DUE)
    _show_loans(rows)
    if not rows:
        pause()
        return
    label = choose("Settle loan", [f"{ln.loan_id} — £{ln.charge_amount:.2f}"
                                   f" {ln.borrower_id}" for ln in rows],
                   allow_blank=True)
    if label:
        lid = int(label.split(" — ")[0])
        if choose("Action", ("Paid", "Waive")) == "Paid":
            data.record_charge_paid(lid)
        else:
            data.waive_charge(lid, ask("Reason", required=True))
        print("\n  ✓ Settled")
    pause()


def cancel() -> None:
    lid = _pick_loan()
    if yes_no("Delete this loan as issued in error today?"):
        data.cancel_loan(lid)
        print("\n  ✓ Cancelled")
    pause()


# ── Acceptable use ──────────────────────────────────────────────────

def aup_status() -> None:
    cur = aup.current_aup()
    if cur is None:
        print("\n  No IT acceptable-use policy is set up.")
    else:
        print(f"\n  {cur.title} — current version {cur.version} "
              f"(approved {cur.approved_on or '—'})")
        for r in aup.versions():
            print(f"    v{r.version}  {r.revised_on}  {r.changes or ''}")
        print(f"\n  Students yet to accept: {len(aup.outstanding())}")
    pause()


def setup_aup() -> None:
    pol = aup.create_aup_policy({
        "title": ask("Title", default="IT Acceptable Use Policy"),
        "version": ask("Version", default="1.0"),
        "approved_by": ask("Approved by"),
        "document_ref": ask("Where the text is (link / file ref)"),
    })
    print(f"\n  ✓ Policy #{pol.policy_id} is the IT AUP")
    pause()


def use_existing_policy() -> None:
    from education_system.systems.sixth_form.domain.governance.policies import (
        policies as _pol,
    )
    label = choose("Policy", [f"{p.policy_id} — {p.title} v{p.version} "
                              f"({p.status})" for p in _pol.list_policies()])
    if label is None:
        raise ValueError("The policy register is empty")
    aup.set_aup_policy(int(label.split(" — ")[0]))
    print("\n  ✓ Set")
    pause()


def publish_version() -> None:
    cur = aup.publish_version({"version": ask("New version", required=True),
                               "changes": ask("What changed"),
                               "approved_by": ask("Approved by")})
    print(f"\n  ✓ Version {cur.version} is current; everyone must accept "
          "it again")
    pause()


def record_acceptance() -> None:
    ut = choose("Person is a", aup.USER_TYPES, default=aup.STUDENT)
    pid = pick_student() if ut == aup.STUDENT else pick_staff()
    a = aup.record_acceptance(ut, pid,
                              accepted_on=ask("Accepted on",
                                              default=_today()),
                              method=choose("How", aup.METHODS,
                                            default=aup.DEFAULT_METHOD))
    print(f"\n  ✓ {a.person_id} accepted v{a.version}")
    pause()


def list_acceptances() -> None:
    rows = aup.list_acceptances(current_only=yes_no(
        "Current version only?", default=True))
    table(["ID", "Who", "Person", "Name", "Version", "Accepted", "How",
           "Withdrawn"],
          [(a.acceptance_id, a.user_type, a.person_id, a.person_name,
            a.version, a.accepted_on, a.method, a.withdrawn_on or "")
           for a in rows])
    pause()


def withdraw() -> None:
    rows = aup.list_acceptances(include_withdrawn=False)
    label = choose("Acceptance", [f"{a.acceptance_id} — {a.person_id} "
                                  f"v{a.version} {a.accepted_on}"
                                  for a in rows[:60]])
    if label is None:
        raise ValueError("No live acceptances")
    aup.withdraw_acceptance(int(label.split(" — ")[0]),
                            ask("Reason", required=True))
    print("\n  ✓ Withdrawn")
    pause()


def not_accepted() -> None:
    ut = choose("Who", aup.USER_TYPES, default=aup.STUDENT)
    table(["ID", "Name"], aup.outstanding(ut))
    pause()


def summary_flow() -> None:
    s = data.summary()
    print("\n═══ Device Loans ═══")
    print(f"  Devices {s.devices}: available {s.available}, on loan "
          f"{s.on_loan}, unusable {s.unusable}")
    print(f"  Overdue {s.overdue}; bursary-funded out {s.bursary_funded_open}")
    print(f"  Lost {s.lost}; returned damaged {s.damaged}")
    print(f"  Charges due £{s.charges_due:.2f}; paid £{s.charges_paid:.2f}")
    print(f"  AUP version {s.aup_version or '(none)'}; students yet to "
          f"accept {s.students_without_aup}")
    pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List devices",            list_devices),
    ("List loans",              list_loans),
    ("Overdue loans",           overdue),
    ("A borrower's loans",      borrower_loans),
    ("─" * 6,                   lambda: None),
    ("Lend a device",           issue),
    ("Extend a loan",           extend),
    ("Return a device",         return_device),
    ("Report lost",             lost),
    ("Lost device found",       found),
    ("Charges due",             charges),
    ("Cancel loan issued in error", cancel),
    ("─" * 6,                   lambda: None),
    ("Register device",         register_device),
    ("Add existing asset to pool", add_existing),
    ("Edit device",             edit_device),
    ("Send for repair / repaired", repair),
    ("Device history",          device_history),
    ("Remove from pool",        remove_device),
    ("─" * 6,                   lambda: None),
    ("Acceptable-use policy status", aup_status),
    ("Set up acceptable-use policy", setup_aup),
    ("Use an existing policy as the AUP", use_existing_policy),
    ("Publish new AUP version", publish_version),
    ("Record acceptance",       record_acceptance),
    ("List acceptances",        list_acceptances),
    ("Withdraw acceptance",     withdraw),
    ("Not yet accepted",        not_accepted),
    ("─" * 6,                   lambda: None),
    ("Summary",                 summary_flow),
]


def run() -> None:
    run_menu("Device Loans", _MENU)


def device_loans_menu() -> None:
    """Entry point for the main CLI menu."""
    run()
