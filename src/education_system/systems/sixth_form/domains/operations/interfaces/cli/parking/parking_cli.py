"""CLI flows for Sixth Form Parking Permits."""

from __future__ import annotations

import logging
from typing import Callable

from education_system.systems.sixth_form.domains.operations.domain.parking import (
    parking as data,
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


def _show_permits(rows) -> None:
    table(["ID", "Permit", "Holder", "Holder ID", "Name", "Reg", "Vehicle",
           "Type", "Issued", "Expires", "Space", "Status"],
          [(p.permit_id, p.permit_number, p.holder_type, p.holder_id,
            p.holder_name, p.vehicle_reg,
            " ".join(x for x in (p.vehicle_colour, p.vehicle_make) if x),
            p.permit_type, p.issued_on, p.expires_on, p.space_label,
            p.status) for p in rows])


def _pick_permit(active_only: bool = False) -> int:
    q = ask("Permit number or reg (blank = list)")
    if q:
        p = data.get_permit_by_number(q)
        if p:
            return p.permit_id
        rows = data.find_by_reg(q)
    else:
        rows = data.list_permits(active_only=active_only)
    if active_only:
        rows = [p for p in rows if p.status == data.ACTIVE]
    label = choose("Permit", [f"{p.permit_id} — {p.permit_number} · "
                              f"{p.vehicle_reg} · {p.holder_name or ''} · "
                              f"{p.status}" for p in rows])
    if label is None:
        raise ValueError("No matching permits")
    return int(label.split(" — ")[0])


def _pick_space(holder_type: str, permit_type: str,
                keep: int | None = None) -> int | None:
    options = []
    for s in data.list_spaces(active_only=True):
        if s.space_type == "Visitor":
            continue
        if s.space_type in ("Staff", "Student") and s.space_type != \
                holder_type:
            continue
        if s.space_type == "Disabled" and permit_type != "Blue Badge":
            continue
        if s.is_free or s.space_id == keep:
            options.append(f"{s.space_id} — {s.label} ({s.space_type})")
    if not options:
        print("    No suitable free spaces.")
        return None
    label = choose("Space (blank = none)", options, allow_blank=True)
    return int(label.split(" — ")[0]) if label else None


# ── Permits ─────────────────────────────────────────────────────────

def list_active() -> None:
    _show_permits(data.list_permits(active_only=True))
    pause()


def list_all() -> None:
    status = choose("Status filter", data.STATUSES, allow_blank=True)
    htype = choose("Holder filter", data.HOLDER_TYPES, allow_blank=True)
    _show_permits(data.list_permits(status=status, holder_type=htype))
    pause()


def find_reg() -> None:
    _show_permits(data.find_by_reg(ask("Registration", required=True)))
    pause()


def expiring() -> None:
    _show_permits(data.expiring_soon(ask_int("Within days", default=30)))
    pause()


def issue() -> None:
    htype = choose("Holder type", data.HOLDER_TYPES)
    hid = pick_staff() if htype == "Staff" else pick_student()
    ptype = choose("Permit type", data.PERMIT_TYPES,
                   default=data.DEFAULT_PERMIT_TYPE)
    reg = ask("Vehicle registration", required=True)
    make = ask("Make / model")
    colour = ask("Colour")
    issued = ask("Issued on (blank = today)")
    expires = ask("Expires on (blank = default for type)")
    space = _pick_space(htype, ptype) if yes_no("Allocate a space?") \
        else None
    p = data.issue_permit({
        "holder_type": htype, "holder_id": hid, "permit_type": ptype,
        "vehicle_reg": reg, "vehicle_make": make, "vehicle_colour": colour,
        "issued_on": issued, "expires_on": expires, "space_id": space,
        "issued_by": ask("Issued by"), "notes": ask("Notes")})
    print(f"\n  ✓ Issued {p.permit_number} for {p.vehicle_reg}, expires "
          f"{p.expires_on}" + (f", space {p.space_label}"
                               if p.space_label else ""))
    pause()


def edit() -> None:
    p = data.get_permit(_pick_permit())
    out = data.update_permit(p.permit_id, {
        "vehicle_reg": ask("Vehicle registration", default=p.vehicle_reg),
        "vehicle_make": ask("Make / model", default=p.vehicle_make or ""),
        "vehicle_colour": ask("Colour", default=p.vehicle_colour or ""),
        "permit_type": choose("Permit type", data.PERMIT_TYPES,
                              default=p.permit_type),
        "issued_on": ask("Issued on", default=p.issued_on),
        "expires_on": ask("Expires on", default=p.expires_on),
        "notes": ask("Notes", default=p.notes or ""),
    })
    print(f"\n  ✓ Updated {out.permit_number}")
    pause()


def assign() -> None:
    p = data.get_permit(_pick_permit(active_only=True))
    space = _pick_space(p.holder_type, p.permit_type, keep=p.space_id)
    out = data.assign_space(p.permit_id, space)
    print(f"\n  ✓ {out.permit_number} → {out.space_label or 'no space'}")
    pause()


def revoke() -> None:
    pid = _pick_permit(active_only=True)
    out = data.revoke_permit(pid, reason=ask("Reason", required=True))
    print(f"\n  ✓ Revoked {out.permit_number}")
    pause()


def renew() -> None:
    pid = _pick_permit()
    new = ask("New expiry (blank = next period for type)")
    out = data.renew_permit(pid, expires_on=new or None)
    print(f"\n  ✓ {out.permit_number} now expires {out.expires_on}")
    pause()


def delete_permit() -> None:
    pid = _pick_permit()
    if yes_no("Delete this permit? (Revoke for a real one)"):
        data.delete_permit(pid)
        print("\n  ✓ Deleted")
    pause()


# ── Spaces ──────────────────────────────────────────────────────────

def list_spaces() -> None:
    free = yes_no("Free spaces only?")
    rows = data.list_spaces(free_only=free)
    table(["ID", "Car park", "Space", "Type", "In use", "Held by"],
          [(s.space_id, s.car_park, s.space_number, s.space_type,
            "Y" if s.active else "N", s.permit_number) for s in rows])
    pause()


def new_space() -> None:
    s = data.create_space({
        "car_park": ask("Car park", required=True),
        "space_number": ask("Space number", required=True),
        "space_type": choose("Space type", data.SPACE_TYPES,
                             default=data.DEFAULT_SPACE_TYPE),
        "notes": ask("Notes")})
    print(f"\n  ✓ Created {s.label}")
    pause()


def add_spaces() -> None:
    made = data.add_spaces(
        ask("Car park", required=True), ask_int("First number", default=1),
        ask_int("How many", default=10),
        space_type=choose("Space type", data.SPACE_TYPES,
                          default=data.DEFAULT_SPACE_TYPE),
        prefix=ask("Number prefix"))
    print(f"\n  ✓ Added {len(made)} space(s)")
    pause()


def _pick_space_any() -> int:
    rows = data.list_spaces()
    label = choose("Space", [f"{s.space_id} — {s.label} ({s.space_type})"
                             for s in rows])
    if label is None:
        raise ValueError("No spaces yet")
    return int(label.split(" — ")[0])


def edit_space() -> None:
    s = data.get_space(_pick_space_any())
    out = data.update_space(s.space_id, {
        "car_park": ask("Car park", default=s.car_park),
        "space_number": ask("Space number", default=s.space_number),
        "space_type": choose("Space type", data.SPACE_TYPES,
                             default=s.space_type),
        "active": yes_no("In use", default=s.active),
        "notes": ask("Notes", default=s.notes or "")})
    print(f"\n  ✓ Updated {out.label}")
    pause()


def delete_space() -> None:
    sid = _pick_space_any()
    if yes_no("Delete this space?"):
        data.delete_space(sid)
        print("\n  ✓ Deleted")
    pause()


def summary_flow() -> None:
    s = data.summary()
    print("\n═══ Parking Summary ═══")
    print(f"  Spaces in use:   {s.spaces} ({s.free_spaces} free)")
    for t in data.SPACE_TYPES:
        print(f"    {t:<10} {s.by_space_type[t]:>4} total, "
              f"{s.free_by_type[t]:>4} free")
    print(f"  Active permits:  {s.active_permits} (staff "
          f"{s.staff_permits}, students {s.student_permits})")
    print(f"  Expiring 30d:    {s.expiring_soon}")
    for k, v in s.by_status.items():
        print(f"    {k:<10} {v}")
    pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Active permits",          list_active),
    ("All permits (filter)",    list_all),
    ("Find by registration",    find_reg),
    ("Expiring soon",           expiring),
    ("─" * 6,                   lambda: None),
    ("Issue permit",            issue),
    ("Edit permit",             edit),
    ("Assign / change space",   assign),
    ("Renew permit",            renew),
    ("Revoke permit",           revoke),
    ("Delete permit",           delete_permit),
    ("─" * 6,                   lambda: None),
    ("List spaces",             list_spaces),
    ("New space",               new_space),
    ("Add numbered spaces",     add_spaces),
    ("Edit space",              edit_space),
    ("Delete space",            delete_space),
    ("─" * 6,                   lambda: None),
    ("Summary",                 summary_flow),
]


def run() -> None:
    run_menu("Parking Permits", _MENU)


def parking_menu() -> None:
    """Entry point for the main CLI menu."""
    run()


def dispatch(label: str) -> bool:
    if label != "Parking Permits":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Parking CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        pause()
    return True
