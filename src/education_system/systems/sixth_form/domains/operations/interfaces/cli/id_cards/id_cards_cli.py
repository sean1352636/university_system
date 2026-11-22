"""CLI flows for Sixth Form ID cards."""

from __future__ import annotations

import logging
from typing import Callable

from education_system.systems.sixth_form.domains.operations.domain.id_cards import (
    id_cards as data,
)
from education_system.systems.sixth_form.interfaces.cli.operations._ops_cli import (
    ask,
    ask_int,
    choose,
    pause,
    pick_staff,
    pick_student,
    run_menu,
    table,
    yes_no,
)

logger = logging.getLogger(__name__)


def _show(rows) -> None:
    table(["ID", "Card no.", "Holder", "Holder ID", "Name", "Issued",
           "Expires", "Status", "Print", "Photo", "Charge", "Reason"],
          [(c.card_id, c.card_number, c.holder_type, c.holder_id,
            c.holder_name, c.issued_on, c.expires_on, c.status,
            c.print_status, c.photo_ref or "(none)",
            (f"£{c.charge:.2f} {'paid' if c.charge_paid else 'due'}"
             if c.charge else ""),
            c.replacement_reason or c.status_reason) for c in rows])


def _pick_card(active_only: bool = True) -> int:
    q = ask("Card number, holder id or name", required=True)
    c = data.get_card_by_number(q)
    if c:
        return c.card_id
    rows = data.list_cards(name_like=q,
                           status=data.ACTIVE if active_only else None)
    label = choose("Card", [f"{c.card_id} — {c.card_number} · "
                            f"{c.holder_name or c.holder_id} · {c.status}"
                            for c in rows])
    if label is None:
        raise ValueError("No matching cards")
    return int(label.split(" — ")[0])


def list_cards() -> None:
    status = choose("Status filter", data.STATUSES, allow_blank=True)
    htype = choose("Holder filter", data.HOLDER_TYPES, allow_blank=True)
    _show(data.list_cards(status=status, holder_type=htype))
    pause()


def find_card() -> None:
    q = ask("Card number, holder id or name", required=True)
    _show(data.list_cards(name_like=q))
    pause()


def issue() -> None:
    htype = choose("Holder type", data.HOLDER_TYPES)
    hid = pick_staff() if htype == "Staff" else pick_student()
    c = data.issue_card(
        htype, hid, photo_ref=ask("Photo reference (file path)") or None,
        issued_on=ask("Issued on (blank = today)") or None,
        expires_on=ask("Expires on (blank = default)") or None,
        issued_by=ask("Issued by"), notes=ask("Notes"))
    print(f"\n  ✓ Issued {c.card_number}, expires {c.expires_on} "
          "(added to the printing list)")
    pause()


def edit() -> None:
    c = data.get_card(_pick_card(active_only=False))
    out = data.update_card(c.card_id, {
        "photo_ref": ask("Photo reference", default=c.photo_ref or ""),
        "expires_on": ask("Expires on", default=c.expires_on),
        "notes": ask("Notes", default=c.notes or "")})
    print(f"\n  ✓ Updated {out.card_number} ({out.print_status})")
    pause()


def replace() -> None:
    cid = _pick_card()
    reason = choose("Reason", data.REPLACEMENT_REASONS, default="Lost")
    raw = ask(f"Charge £ (blank = default; standard "
              f"£{data.replacement_charge():.2f})")
    new = data.replace_card(cid, reason=reason,
                            charge=float(raw) if raw else None,
                            photo_ref=ask("New photo reference "
                                          "(blank = keep)") or None,
                            issued_by=ask("Issued by"))
    print(f"\n  ✓ Replacement {new.card_number} issued"
          + (f"; charge £{new.charge:.2f} due" if new.charge else ""))
    pause()


def mark_lost() -> None:
    cid = _pick_card()
    if yes_no("Issue a replacement now?", default=True):
        new = data.report_lost(cid, stolen=yes_no("Stolen?"))
        print(f"\n  ✓ Replacement {new.card_number} issued; charge "
              f"£{new.charge:.2f}")
    else:
        old = data.report_lost(cid, replace=False)
        print(f"\n  ✓ {old.card_number} marked Lost")
    pause()


def charge_paid() -> None:
    _show(data.list_cards(charges_outstanding=True))
    cid = _pick_card(active_only=False)
    out = data.record_charge_paid(cid)
    print(f"\n  ✓ £{out.charge:.2f} recorded as paid")
    pause()


def cancel() -> None:
    cid = _pick_card()
    out = data.cancel_card(cid, reason=ask("Reason", required=True))
    print(f"\n  ✓ {out.card_number} cancelled")
    pause()


def printing_list() -> None:
    rows = data.print_queue()
    _show(rows)
    if rows and yes_no("Mark all of these printed?"):
        n = data.mark_printed([c.card_id for c in rows],
                              printed_by=ask("Printed by"))
        print(f"\n  ✓ {n} card(s) marked printed")
    pause()


def reprint() -> None:
    out = data.reprint(_pick_card())
    print(f"\n  ✓ {out.card_number} back on the printing list")
    pause()


def expiring() -> None:
    _show(data.expiring(ask_int("Within days", default=30)))
    pause()


def without_card() -> None:
    rows = data.students_without_card()
    table(["Student ID", "Name"], rows)
    pause()


def history() -> None:
    htype = choose("Holder type", data.HOLDER_TYPES)
    hid = pick_staff() if htype == "Staff" else pick_student()
    _show(data.history_for(htype, hid))
    pause()


def delete() -> None:
    cid = _pick_card(active_only=False)
    if yes_no("Delete this unprinted card?"):
        data.delete_card(cid)
        print("\n  ✓ Deleted")
    pause()


def settings() -> None:
    charge = ask("Replacement charge £",
                 default=f"{data.replacement_charge():.2f}")
    years = ask_int("Staff card validity (years)",
                    default=data.staff_validity_years())
    data.set_replacement_charge(charge)
    data.set_staff_validity_years(years)
    print("\n  ✓ Settings saved")
    pause()


def summary_flow() -> None:
    s = data.summary()
    print("\n═══ ID Cards Summary ═══")
    print(f"  Cards on file:         {s.total}")
    print(f"  Active:                {s.active} "
          + ", ".join(f"{k}: {v}" for k, v in s.by_holder_type.items()))
    print(f"  Awaiting print:        {s.awaiting_print}")
    print(f"  Active without photo:  {s.no_photo}")
    print(f"  Expiring 30 days:      {s.expiring_30}")
    print(f"  Students without card: {s.students_without_card}")
    print(f"  Charges outstanding:   £{s.charges_outstanding:.2f}")
    print(f"  Charges collected:     £{s.charges_collected:.2f}")
    for k, v in s.by_status.items():
        print(f"    {k:<10} {v}")
    pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List cards",              list_cards),
    ("Find card",               find_card),
    ("Printing list",           printing_list),
    ("Expiring cards",          expiring),
    ("Students without a card", without_card),
    ("Card history for holder", history),
    ("─" * 6,                   lambda: None),
    ("Issue card",              issue),
    ("Edit card (photo / expiry)", edit),
    ("Lost / stolen card",      mark_lost),
    ("Replace card",            replace),
    ("Record charge paid",      charge_paid),
    ("Reprint card",            reprint),
    ("Cancel card",             cancel),
    ("Delete unprinted card",   delete),
    ("─" * 6,                   lambda: None),
    ("Settings",                settings),
    ("Summary",                 summary_flow),
]


def run() -> None:
    run_menu("ID Cards", _MENU)


def id_cards_menu() -> None:
    """Entry point for the main CLI menu."""
    run()


def dispatch(label: str) -> bool:
    if label != "ID Cards":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("ID cards CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        pause()
    return True
