"""CLI flows for Sixth Form Visitors."""

from __future__ import annotations

import logging
from datetime import date as _date
from datetime import datetime as _dt
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.staff_comms.visitors import (
    visitors as data,
)
from education_system.post_16.sixthform_system.modules.domain.staff_comms.visitors.visitors import (
    DEFAULT_ID_TYPE,
    DEFAULT_STATUS,
    DEFAULT_VISITOR_TYPE,
    ID_TYPES,
    STATUSES,
    VISITOR_TYPES,
    ValidationError,
    Visitor,
)
from education_system.post_16.sixthform_system.modules.domain.staff_comms.staff import (
    staff as _staff,
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
        print(f"    {marker}{i:>2}) {opt or '(none)'}")
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


def _pick_staff(*, optional: bool = False) -> str | None:
    rows = _staff.list_staff()
    if not rows:
        if optional:
            return None
        print("    No staff.")
        raise _UserAbort
    print("\n  Staff:")
    if optional:
        print("    0) (none)")
    for i, s in enumerate(rows, 1):
        full = f"{getattr(s, 'first_name', '')} " \
               f"{getattr(s, 'last_name', '')}".strip()
        print(f"    {i:>3}) {s.staff_id:<12}  {full}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)}"
                      + (" (0 for none)" if optional else "")
                      + " (or id)",
                      allow_empty=optional)
        if optional and (not raw or raw == "0"):
            return None
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].staff_id
        match = next((s for s in rows
                        if s.staff_id == raw.upper()), None)
        if match:
            return match.staff_id
        print("    No matching staff.")


def _pick_visitor() -> Visitor:
    rows = data.list_visitors()
    if not rows:
        print("    No visitors yet.")
        raise _UserAbort
    print("\n  Visitors:")
    for i, v in enumerate(rows, 1):
        flag = "!" if v.is_overdue else " "
        print(f"    {i:>3}){flag} #{v.visitor_id}  "
              f"{v.visit_date}  "
              f"{v.visitor_name[:24]:<24}  "
              f"{v.visitor_type[:18]:<18}  "
              f"[{v.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.visitor_id == n), None)
            if match:
                return match
        print("    No matching visitor.")


def _print_table(rows: list[Visitor]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Date':<10}  {'Name':<24}  "
          f"{'Type':<18}  {'Host':<14}  "
          f"{'Badge':<10}  {'Status':<12}  Flags")
    print("  " + "-" * 130)
    for v in rows:
        flags = []
        if v.is_overdue:
            flags.append("OVERDUE")
        if v.safeguarding_concern:
            flags.append("SG")
        if v.escort_required and not v.escorted_by:
            flags.append("ESC")
        print(f"  {v.visitor_id:>4}  {v.visit_date:<10}  "
              f"{v.visitor_name[:24]:<24}  "
              f"{v.visitor_type[:18]:<18}  "
              f"{(v.host_staff_id or v.host_name or '—')[:14]:<14}  "
              f"{(v.badge_number or '—')[:10]:<10}  "
              f"{v.status:<12}  {','.join(flags)}")
    print(f"\n  {len(rows)} visitor(s).")


def _print_full(v: Visitor) -> None:
    print()
    print(f"    #{v.visitor_id}  {v.visitor_name}")
    print(f"    Organisation     : {v.organisation or '—'}")
    print(f"    Type             : {v.visitor_type}")
    print(f"    Purpose          : {v.purpose or '—'}")
    print(f"    Host             : "
          f"{v.host_staff_id or '—'}  "
          f"{v.host_name or ''}")
    print(f"    Badge            : {v.badge_number or '—'}")
    print(f"    Visit date       : {v.visit_date}")
    print(f"    Arrived at       : {v.arrived_at or '—'}")
    print(f"    Expected depart. : "
          f"{v.expected_departure or '—'}"
          + ("  (OVERDUE)" if v.is_overdue else ""))
    print(f"    Signed out at    : {v.signed_out_at or '—'}")
    print(f"    ID check         : {v.id_check}")
    print(f"    DBS seen         : "
          f"{'yes' if v.dbs_seen else 'no'}")
    print(f"    Photo ID seen    : "
          f"{'yes' if v.photo_id_seen else 'no'}")
    print(f"    Induction        : "
          f"{'yes' if v.induction_given else 'no'}")
    print(f"    Safeguarding br. : "
          f"{'yes' if v.safeguarding_briefing else 'no'}")
    print(f"    Car registration : "
          f"{v.car_registration or '—'}")
    print(f"    Car park used    : {v.car_park_used or '—'}")
    print(f"    Contact phone    : {v.contact_phone or '—'}")
    print(f"    Contact email    : {v.contact_email or '—'}")
    print(f"    Escort required  : "
          f"{'yes' if v.escort_required else 'no'}")
    print(f"    Escorted by      : {v.escorted_by or '—'}")
    print(f"    Safeguarding c.  : "
          f"{'yes' if v.safeguarding_concern else 'no'}")
    print(f"    Status           : {v.status}")
    if v.notes:
        print("\n    Notes:")
        for line in v.notes.splitlines():
            print(f"      {line}")


# ── Flows ────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Visitors ═══")
    _print_table(data.list_visitors())
    _pause()


def list_on_site() -> None:
    print("\n═══ On Site Now ═══")
    _print_table(data.list_visitors(on_site_only=True))
    _pause()


def list_overdue() -> None:
    print("\n═══ Overdue Departure ═══")
    _print_table(data.list_visitors(overdue_only=True))
    _pause()


def list_today() -> None:
    print("\n═══ Today's Visitors ═══")
    _print_table(data.list_visitors(today_only=True))
    _pause()


def list_no_shows() -> None:
    print("\n═══ No-Shows ═══")
    _print_table(data.list_visitors(no_show_only=True))
    _pause()


def list_safeguarding() -> None:
    print("\n═══ Safeguarding Concerns ═══")
    _print_table(data.list_visitors(safeguarding_only=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        vt = _input(
            f"Type ({'/'.join(VISITOR_TYPES[:2])}…)") or None
        status = _input(
            f"Status ({'/'.join(STATUSES[:3])}…)") or None
        name = _input("Name contains") or None
        org = _input("Organisation contains") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_visitors(visitor_type=vt,
                                       status=status,
                                       name_like=name,
                                       org_like=org,
                                       date_from=df, date_to=dt2)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_table(rows)
    _pause()


def per_host_flow() -> None:
    print("\n═══ Per-Host ═══")
    try:
        sid = _pick_staff()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_table(data.visitors_for_host(sid))
    _pause()


def view_flow() -> None:
    print("\n═══ View Visitor ═══")
    try:
        v = _pick_visitor()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_full(v)
    _pause()


def _collect_form(existing: Visitor | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["visitor_name"] = _input(
        "Visitor name",
        default=(existing.visitor_name if is_edit else ""),
        allow_empty=False)
    payload["organisation"] = _input(
        "Organisation",
        default=(existing.organisation or "")
        if is_edit else "")
    payload["visitor_type"] = _pick_from(
        "Visitor type", list(VISITOR_TYPES),
        default=(existing.visitor_type if is_edit
                  else DEFAULT_VISITOR_TYPE))
    payload["purpose"] = _input(
        "Purpose",
        default=(existing.purpose or "") if is_edit else "")
    if _yes_no("Set host staff member?",
               default=is_edit and bool(existing.host_staff_id)):
        try:
            sid = _pick_staff(optional=True)
            payload["host_staff_id"] = sid
        except _UserAbort:
            payload["host_staff_id"] = None
    else:
        payload["host_staff_id"] = None
    payload["host_name"] = _input(
        "Host name",
        default=(existing.host_name or "") if is_edit else "")
    payload["badge_number"] = _input(
        "Badge number",
        default=(existing.badge_number or "")
        if is_edit else "")
    payload["visit_date"] = _input(
        "Visit date (YYYY-MM-DD)",
        default=(existing.visit_date if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    payload["arrived_at"] = _input(
        "Arrived at (YYYY-MM-DDTHH:MM)",
        default=(existing.arrived_at or "")
        if is_edit else "")
    payload["expected_departure"] = _input(
        "Expected departure (YYYY-MM-DDTHH:MM)",
        default=(existing.expected_departure or "")
        if is_edit else "")
    payload["signed_out_at"] = _input(
        "Signed out at (YYYY-MM-DDTHH:MM)",
        default=(existing.signed_out_at or "")
        if is_edit else "")
    payload["id_check"] = _pick_from(
        "ID check", list(ID_TYPES),
        default=(existing.id_check if is_edit
                  else DEFAULT_ID_TYPE))
    payload["dbs_seen"] = _yes_no(
        "DBS seen?",
        default=(existing.dbs_seen if is_edit else False))
    payload["photo_id_seen"] = _yes_no(
        "Photo ID seen?",
        default=(existing.photo_id_seen if is_edit else False))
    payload["induction_given"] = _yes_no(
        "Induction given?",
        default=(existing.induction_given
                  if is_edit else False))
    payload["safeguarding_briefing"] = _yes_no(
        "Safeguarding briefing given?",
        default=(existing.safeguarding_briefing
                  if is_edit else False))
    payload["car_registration"] = _input(
        "Car registration",
        default=(existing.car_registration or "")
        if is_edit else "")
    payload["car_park_used"] = _input(
        "Car park used",
        default=(existing.car_park_used or "")
        if is_edit else "")
    payload["contact_phone"] = _input(
        "Contact phone",
        default=(existing.contact_phone or "")
        if is_edit else "")
    payload["contact_email"] = _input(
        "Contact email",
        default=(existing.contact_email or "")
        if is_edit else "")
    payload["escort_required"] = _yes_no(
        "Escort required?",
        default=(existing.escort_required
                  if is_edit else False))
    payload["escorted_by"] = _input(
        "Escorted by",
        default=(existing.escorted_by or "")
        if is_edit else "")
    payload["safeguarding_concern"] = _yes_no(
        "Safeguarding concern?",
        default=(existing.safeguarding_concern
                  if is_edit else False))
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_STATUS))
    try:
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "") if is_edit else "")
    except _UserAbort:
        raise
    return payload


def new_visitor() -> None:
    print("\n═══ New Visitor ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        v = data.create_visitor(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created visitor #{v.visitor_id}")
    _pause()


def edit_visitor() -> None:
    print("\n═══ Edit Visitor ═══")
    try:
        v = _pick_visitor()
        payload = _collect_form(v)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_visitor(v.visitor_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{v.visitor_id}")
    _pause()


def sign_in_flow() -> None:
    print("\n═══ Sign In ═══")
    try:
        v = _pick_visitor()
        badge = _input("Badge number",
                          default=v.badge_number or "")
        arrived = _input("Arrived at (YYYY-MM-DDTHH:MM)",
                            default=_dt.now().isoformat(
                                timespec="minutes"))
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.sign_in(v.visitor_id,
                        badge_number=badge or None,
                        arrived_at=arrived)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{v.visitor_id} → Signed In")
    _pause()


def sign_out_flow() -> None:
    print("\n═══ Sign Out ═══")
    try:
        v = _pick_visitor()
        when = _input("Signed out at (YYYY-MM-DDTHH:MM)",
                        default=_dt.now().isoformat(
                            timespec="minutes"))
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.sign_out(v.visitor_id, signed_out_at=when)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{v.visitor_id} → Signed Out")
    _pause()


def overstay_flow() -> None:
    print("\n═══ Mark Overstay ═══")
    try:
        v = _pick_visitor()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.mark_overstay(v.visitor_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{v.visitor_id} → Overstay")
    _pause()


def no_show_flow() -> None:
    print("\n═══ Mark No-Show ═══")
    try:
        v = _pick_visitor()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.mark_no_show(v.visitor_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{v.visitor_id} → No-Show")
    _pause()


def refuse_entry_flow() -> None:
    print("\n═══ Refuse Entry ═══")
    try:
        v = _pick_visitor()
        reason = _multiline("Reason")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.refuse_entry(v.visitor_id, reason=reason or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{v.visitor_id} → Refused Entry")
    _pause()


def safeguarding_flow() -> None:
    print("\n═══ Raise Safeguarding Concern ═══")
    try:
        v = _pick_visitor()
        detail = _multiline("Detail")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.raise_safeguarding(v.visitor_id,
                                      detail=detail or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Concern raised on #{v.visitor_id}")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        v = _pick_visitor()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=v.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(v.visitor_id, new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{v.visitor_id} → {new_status}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete ═══")
    try:
        v = _pick_visitor()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete visitor #{v.visitor_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_visitor(v.visitor_id):
        print(f"\n  ✓ Deleted #{v.visitor_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Visitors Summary ═══")
    s = data.summary()
    print(f"\n  Total                 : {s.total}")
    print(f"  On site now           : {s.on_site_now}")
    print(f"  Overdue               : {s.overdue}")
    print(f"  Expected today        : {s.expected_today}")
    print(f"  No-shows              : {s.no_shows}")
    print(f"  Safeguarding concerns : {s.safeguarding_concerns}")
    print(f"  Contractors on site   : {s.contractors_on_site}")
    print(f"  DBS seen count        : {s.dbs_seen_count}")
    print("\n  By type:")
    for k in VISITOR_TYPES:
        n = s.by_type.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    print("\n  By ID check:")
    for k in ID_TYPES:
        n = s.by_id_check.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",            list_all),
    ("On site now",         list_on_site),
    ("Overdue",             list_overdue),
    ("Today",               list_today),
    ("No-shows",            list_no_shows),
    ("Safeguarding",        list_safeguarding),
    ("Filter",              filter_flow),
    ("Per-host",            per_host_flow),
    ("View",                view_flow),
    ("─" * 6,               lambda: None),
    ("New visitor",         new_visitor),
    ("Edit visitor",        edit_visitor),
    ("Sign in",             sign_in_flow),
    ("Sign out",            sign_out_flow),
    ("Mark Overstay",       overstay_flow),
    ("Mark No-Show",        no_show_flow),
    ("Refuse Entry",        refuse_entry_flow),
    ("Raise safeguarding",  safeguarding_flow),
    ("Change status",       set_status_flow),
    ("Delete",              delete_flow),
    ("─" * 6,               lambda: None),
    ("Summary",             summary_flow),
]


def run() -> None:
    while True:
        print("\n── Visitors ──")
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
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
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
            logger.exception("Visitors CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Visitors":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Visitors CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
