"""CLI flows for Primary School Transport."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.primarysch_system.modules.domain.transport import (
    transport as data,
)
from education_system.primarysch_system.modules.domain.transport.transport import (
    ARRANGEMENT_STATUSES,
    Arrangement,
    DEFAULT_ARRANGEMENT_STATUS,
    DEFAULT_FEE_STATUS,
    DEFAULT_MODE,
    DEFAULT_ROUTE_STATUS,
    DEFAULT_ROUTE_TYPE,
    FEE_STATUSES,
    MODES,
    ROUTE_STATUSES,
    ROUTE_TYPES,
    Route,
    ValidationError,
)
from education_system.primarysch_system.modules.domain import _pupils_bridge as _students

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


def _pick_student() -> str:
    rows = _students.list_students()
    if not rows:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(rows, 1):
        full = f"{getattr(s, 'first_name', '')} " \
               f"{getattr(s, 'last_name', '')}".strip()
        print(f"    {i:>3}) {s.student_id:<12}  {full}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].student_id
        match = next((s for s in rows if s.student_id == raw), None)
        if match:
            return match.student_id
        print("    No matching student.")


def _pick_route(*, optional: bool = False) -> Route | None:
    rows = data.list_routes()
    if not rows:
        if optional:
            return None
        print("    No routes.")
        raise _UserAbort
    print("\n  Routes:")
    if optional:
        print("    0) (none)")
    for i, r in enumerate(rows, 1):
        print(f"    {i:>3}) #{r.route_id}  "
              f"{r.route_name[:30]:<30}  "
              f"{r.route_type[:12]:<12}  [{r.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)}"
                      + (" (0 for none)" if optional else "")
                      + " (or id)",
                      allow_empty=False)
        if optional and raw == "0":
            return None
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.route_id == n), None)
            if match:
                return match
        print("    No matching route.")


def _pick_arrangement() -> Arrangement:
    rows = data.list_arrangements()
    if not rows:
        print("    No arrangements yet.")
        raise _UserAbort
    print("\n  Arrangements:")
    for i, a in enumerate(rows, 1):
        print(f"    {i:>3}) #{a.arrangement_id}  "
              f"{a.student_id:<12}  {a.mode[:14]:<14}  "
              f"{(a.route_name_cache or '—')[:20]:<20}  "
              f"[{a.status}]  fee:{a.fee_status}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.arrangement_id == n), None)
            if match:
                return match
        print("    No matching arrangement.")


# ── Routes ───────────────────────────────────────────────────

def _print_routes(rows: list[Route]) -> None:
    if not rows:
        print("\n  (no routes)")
        return
    print()
    print(f"  {'#':>4}  {'Name':<28}  {'Type':<14}  "
          f"{'Operator':<14}  {'Days':<10}  "
          f"{'AM':<5}  {'PM':<5}  Seats  Status")
    print("  " + "-" * 120)
    for r in rows:
        seats_used = data.route_seats_used(r.route_id)
        seats = (f"{seats_used}/{r.capacity}"
                  if r.capacity is not None
                  else str(seats_used))
        print(f"  {r.route_id:>4}  {r.route_name[:28]:<28}  "
              f"{r.route_type[:14]:<14}  "
              f"{(r.operator or '—')[:14]:<14}  "
              f"{r.days[:10]:<10}  "
              f"{(r.am_pickup_time or '—'):<5}  "
              f"{(r.pm_return_time or '—'):<5}  "
              f"{seats:>6}  {r.status}")
    print(f"\n  {len(rows)} route(s).")


def routes_list() -> None:
    print("\n═══ All Routes ═══")
    _print_routes(data.list_routes())
    _pause()


def routes_active() -> None:
    print("\n═══ Active Routes ═══")
    _print_routes(data.list_routes(active_only=True))
    _pause()


def routes_filter() -> None:
    print("\n═══ Filter Routes ═══")
    try:
        rtype = _input(
            f"Type ({'/'.join(ROUTE_TYPES[:2])}…)") or None
        status = _input(
            f"Status ({'/'.join(ROUTE_STATUSES)})") or None
        op = _input("Operator contains") or None
        name = _input("Name contains") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_routes(route_type=rtype, status=status,
                                 operator_like=op, name_like=name)
    _print_routes(rows)
    _pause()


def _collect_route_form(
        existing: Route | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["route_name"] = _input(
        "Route name",
        default=(existing.route_name if is_edit else ""),
        allow_empty=False)
    payload["route_type"] = _pick_from(
        "Type", list(ROUTE_TYPES),
        default=(existing.route_type if is_edit
                  else DEFAULT_ROUTE_TYPE))
    payload["operator"] = _input(
        "Operator",
        default=(existing.operator or "") if is_edit else "")
    payload["contact_phone"] = _input(
        "Contact phone",
        default=(existing.contact_phone or "")
        if is_edit else "")
    payload["contact_email"] = _input(
        "Contact email",
        default=(existing.contact_email or "")
        if is_edit else "")
    payload["days"] = _input(
        "Days (e.g. 'Mon-Fri')",
        default=(existing.days if is_edit else "Mon-Fri"),
        allow_empty=False)
    payload["am_pickup_time"] = _input(
        "AM pickup time (HH:MM)",
        default=(existing.am_pickup_time or "")
        if is_edit else "")
    payload["pm_return_time"] = _input(
        "PM return time (HH:MM)",
        default=(existing.pm_return_time or "")
        if is_edit else "")
    try:
        payload["pickup_points"] = _multiline(
            "Pickup points",
            default=(existing.pickup_points or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["cost_per_term"] = _input(
        "Cost per term (£)",
        default=(str(existing.cost_per_term)
                  if is_edit and existing.cost_per_term is not None
                  else ""))
    payload["cost_per_year"] = _input(
        "Cost per year (£)",
        default=(str(existing.cost_per_year)
                  if is_edit and existing.cost_per_year is not None
                  else ""))
    payload["capacity"] = _input(
        "Capacity",
        default=(str(existing.capacity)
                  if is_edit and existing.capacity is not None
                  else ""))
    payload["status"] = _pick_from(
        "Status", list(ROUTE_STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_ROUTE_STATUS))
    try:
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "") if is_edit else "")
    except _UserAbort:
        raise
    return payload


def routes_new() -> None:
    print("\n═══ New Route ═══")
    try:
        payload = _collect_route_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.create_route(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created route #{r.route_id}")
    _pause()


def routes_edit() -> None:
    print("\n═══ Edit Route ═══")
    try:
        r = _pick_route()
        if r is None:
            return
        payload = _collect_route_form(r)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_route(r.route_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{r.route_id}")
    _pause()


def routes_set_status() -> None:
    print("\n═══ Change Route Status ═══")
    try:
        r = _pick_route()
        if r is None:
            return
        new_status = _pick_from("New status",
                                  list(ROUTE_STATUSES),
                                  default=r.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_route_status(r.route_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{r.route_id} → {new_status}")
    _pause()


def routes_delete() -> None:
    print("\n═══ Delete Route ═══")
    try:
        r = _pick_route()
        if r is None:
            return
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete route #{r.route_id}? "
              "(arrangements keep history) Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_route(r.route_id):
        print(f"\n  ✓ Deleted #{r.route_id}")
    _pause()


# ── Arrangements ────────────────────────────────────────────

def _print_arrangements(rows: list[Arrangement]) -> None:
    if not rows:
        print("\n  (no arrangements)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<12}  {'Mode':<14}  "
          f"{'Route':<22}  {'Days':<10}  "
          f"{'Start':<10}  Fee         Status")
    print("  " + "-" * 120)
    for a in rows:
        flags = ""
        if a.bursary_supported:
            flags = " BURS"
        if a.pass_expired:
            flags += " EXP"
        print(f"  {a.arrangement_id:>4}  {a.student_id:<12}  "
              f"{a.mode[:14]:<14}  "
              f"{(a.route_name_cache or '—')[:22]:<22}  "
              f"{a.days[:10]:<10}  "
              f"{a.start_date:<10}  "
              f"{a.fee_status:<12}{flags}  {a.status}")
    print(f"\n  {len(rows)} arrangement(s).")


def _print_arr_full(a: Arrangement) -> None:
    print()
    print(f"    #{a.arrangement_id}  Student {a.student_id}")
    print(f"    Mode             : {a.mode}")
    print(f"    Route            : "
          f"{a.route_name_cache or '—'}"
          + (f"  (id #{a.route_id})" if a.route_id else ""))
    print(f"    Pickup → drop    : "
          f"{a.pickup_point or '—'} → "
          f"{a.drop_point or '—'}")
    print(f"    Days             : {a.days}")
    print(f"    Period           : {a.start_date} → "
          f"{a.end_date or '—'}")
    print(f"    Fee status       : {a.fee_status}"
          + (f"  £{a.fee_amount:.2f}"
              if a.fee_amount is not None else ""))
    print(f"    Bursary supported: "
          f"{'yes' if a.bursary_supported else 'no'}")
    print(f"    Pass number      : {a.pass_number or '—'}")
    print(f"    Pass expires on  : {a.pass_expires_on or '—'}"
          + ("  (EXPIRED)" if a.pass_expired else ""))
    print(f"    Emergency contact: "
          f"{a.emergency_contact or '—'}  "
          f"{a.emergency_phone or '—'}")
    print(f"    Status           : {a.status}")
    for label, val in (
            ("Medical notes", a.medical_notes),
            ("Notes",         a.notes),
    ):
        if val:
            print(f"\n    {label}:")
            for line in val.splitlines():
                print(f"      {line}")


def arr_list() -> None:
    print("\n═══ All Arrangements ═══")
    _print_arrangements(data.list_arrangements())
    _pause()


def arr_active() -> None:
    print("\n═══ Active Arrangements ═══")
    _print_arrangements(data.list_arrangements(active_only=True))
    _pause()


def arr_unpaid() -> None:
    print("\n═══ Unpaid / Partial Fees ═══")
    _print_arrangements(data.list_arrangements(unpaid_only=True))
    _pause()


def arr_bursary() -> None:
    print("\n═══ Bursary-Supported ═══")
    _print_arrangements(data.list_arrangements(bursary_only=True))
    _pause()


def arr_expired() -> None:
    print("\n═══ Pass Expired ═══")
    _print_arrangements(data.list_arrangements(pass_expired=True))
    _pause()


def arr_filter() -> None:
    print("\n═══ Filter Arrangements ═══")
    try:
        sid = _input("Student id") or None
        mode = _input(f"Mode ({'/'.join(MODES[:3])}…)") or None
        status = _input(
            f"Status ({'/'.join(ARRANGEMENT_STATUSES[:3])}…)") or None
        fee = _input(
            f"Fee status ({'/'.join(FEE_STATUSES[:3])}…)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_arrangements(student_id=sid, mode=mode,
                                       status=status,
                                       fee_status=fee)
    _print_arrangements(rows)
    _pause()


def arr_per_student() -> None:
    print("\n═══ Per-Student ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_arrangements(data.arrangements_for_student(sid))
    _pause()


def arr_view() -> None:
    print("\n═══ View Arrangement ═══")
    try:
        a = _pick_arrangement()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_arr_full(a)
    _pause()


def _collect_arr_form(
        existing: Arrangement | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["student_id"] = existing.student_id
    else:
        payload["student_id"] = _pick_student()
    payload["mode"] = _pick_from(
        "Mode", list(MODES),
        default=(existing.mode if is_edit else DEFAULT_MODE))
    if _yes_no("Link to a route?",
               default=existing.route_id is not None
               if is_edit else False):
        try:
            r = _pick_route(optional=True)
            payload["route_id"] = r.route_id if r else None
        except _UserAbort:
            payload["route_id"] = None
    else:
        payload["route_id"] = None
    payload["pickup_point"] = _input(
        "Pickup point",
        default=(existing.pickup_point or "")
        if is_edit else "")
    payload["drop_point"] = _input(
        "Drop point",
        default=(existing.drop_point or "")
        if is_edit else "")
    payload["days"] = _input(
        "Days (e.g. 'Mon-Fri')",
        default=(existing.days if is_edit else "Mon-Fri"),
        allow_empty=False)
    payload["start_date"] = _input(
        "Start date (YYYY-MM-DD)",
        default=(existing.start_date if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    payload["end_date"] = _input(
        "End date (YYYY-MM-DD)",
        default=(existing.end_date or "") if is_edit else "")
    payload["fee_status"] = _pick_from(
        "Fee status", list(FEE_STATUSES),
        default=(existing.fee_status if is_edit
                  else DEFAULT_FEE_STATUS))
    payload["fee_amount"] = _input(
        "Fee amount (£)",
        default=(str(existing.fee_amount)
                  if is_edit and existing.fee_amount is not None
                  else ""))
    payload["bursary_supported"] = _yes_no(
        "Bursary supported?",
        default=(existing.bursary_supported
                  if is_edit else False))
    payload["pass_number"] = _input(
        "Pass / ticket number",
        default=(existing.pass_number or "")
        if is_edit else "")
    payload["pass_expires_on"] = _input(
        "Pass expires (YYYY-MM-DD)",
        default=(existing.pass_expires_on or "")
        if is_edit else "")
    payload["emergency_contact"] = _input(
        "Emergency contact",
        default=(existing.emergency_contact or "")
        if is_edit else "")
    payload["emergency_phone"] = _input(
        "Emergency phone",
        default=(existing.emergency_phone or "")
        if is_edit else "")
    try:
        payload["medical_notes"] = _multiline(
            "Medical notes",
            default=(existing.medical_notes or "")
            if is_edit else "")
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "") if is_edit else "")
    except _UserAbort:
        raise
    payload["status"] = _pick_from(
        "Status", list(ARRANGEMENT_STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_ARRANGEMENT_STATUS))
    return payload


def arr_new() -> None:
    print("\n═══ New Arrangement ═══")
    try:
        payload = _collect_arr_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_arrangement(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created arrangement #{a.arrangement_id}")
    _pause()


def arr_edit() -> None:
    print("\n═══ Edit Arrangement ═══")
    try:
        a = _pick_arrangement()
        payload = _collect_arr_form(a)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_arrangement(a.arrangement_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{a.arrangement_id}")
    _pause()


def arr_activate() -> None:
    print("\n═══ Activate ═══")
    try:
        a = _pick_arrangement()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.activate(a.arrangement_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.arrangement_id} → Active")
    _pause()


def arr_suspend() -> None:
    print("\n═══ Suspend ═══")
    try:
        a = _pick_arrangement()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.suspend(a.arrangement_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.arrangement_id} → Suspended")
    _pause()


def arr_end() -> None:
    print("\n═══ End Arrangement ═══")
    try:
        a = _pick_arrangement()
        when = _input("End date (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.end_arrangement(a.arrangement_id, end_date=when)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.arrangement_id} → Ended")
    _pause()


def arr_cancel() -> None:
    print("\n═══ Cancel ═══")
    try:
        a = _pick_arrangement()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.cancel(a.arrangement_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.arrangement_id} → Cancelled")
    _pause()


def arr_set_fee() -> None:
    print("\n═══ Change Fee Status ═══")
    try:
        a = _pick_arrangement()
        new_fee = _pick_from("New fee status",
                                list(FEE_STATUSES),
                                default=a.fee_status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_fee_status(a.arrangement_id, new_fee)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.arrangement_id} fee → {new_fee}")
    _pause()


def arr_set_status() -> None:
    print("\n═══ Change Status ═══")
    try:
        a = _pick_arrangement()
        new_status = _pick_from("New status",
                                  list(ARRANGEMENT_STATUSES),
                                  default=a.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_arrangement_status(a.arrangement_id,
                                          new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.arrangement_id} → {new_status}")
    _pause()


def arr_delete() -> None:
    print("\n═══ Delete Arrangement ═══")
    try:
        a = _pick_arrangement()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete arrangement #{a.arrangement_id}? "
              "Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_arrangement(a.arrangement_id):
        print(f"\n  ✓ Deleted #{a.arrangement_id}")
    _pause()


# ── Summary ──────────────────────────────────────────────

def summary_flow() -> None:
    print("\n═══ Transport Summary ═══")
    s = data.summary()
    print(f"\n  Total routes         : {s.total_routes}")
    print(f"  Active routes        : {s.active_routes}")
    print(f"  Total arrangements   : {s.total_arrangements}")
    print(f"  Active arrangements  : {s.active_arrangements}")
    print(f"  Suspended            : {s.suspended}")
    print(f"  Pending              : {s.pending}")
    print(f"  Unpaid / partial     : {s.unpaid_or_partial}")
    print(f"  Bursary supported    : {s.bursary_supported}")
    print(f"  Pass expired         : {s.pass_expired}")
    print(f"  Distinct students    : {s.distinct_students}")
    print("\n  By mode:")
    for k in MODES:
        n = s.by_mode.get(k, 0)
        if n:
            print(f"    {k:<18}: {n}")
    print("\n  By fee status:")
    for k in FEE_STATUSES:
        n = s.by_fee_status.get(k, 0)
        if n:
            print(f"    {k:<18}: {n}")
    print("\n  By status:")
    for k in ARRANGEMENT_STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    if s.by_route:
        print("\n  By route:")
        for k, v in s.by_route.items():
            print(f"    {k:<28}: {v}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("── Routes ──",         lambda: None),
    ("List all",             routes_list),
    ("List active",          routes_active),
    ("Filter",               routes_filter),
    ("New route",            routes_new),
    ("Edit route",           routes_edit),
    ("Change status",        routes_set_status),
    ("Delete route",         routes_delete),
    ("── Arrangements ──",   lambda: None),
    ("List all",             arr_list),
    ("List active",          arr_active),
    ("Unpaid / partial",     arr_unpaid),
    ("Bursary supported",    arr_bursary),
    ("Pass expired",         arr_expired),
    ("Filter",               arr_filter),
    ("Per-student",          arr_per_student),
    ("View",                 arr_view),
    ("New arrangement",      arr_new),
    ("Edit arrangement",     arr_edit),
    ("Activate",             arr_activate),
    ("Suspend",              arr_suspend),
    ("End",                  arr_end),
    ("Cancel",               arr_cancel),
    ("Change fee status",    arr_set_fee),
    ("Change status",        arr_set_status),
    ("Delete arrangement",   arr_delete),
    ("──",                   lambda: None),
    ("Summary",              summary_flow),
]


def run() -> None:
    while True:
        print("\n── Transport ──")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label}")
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
            logger.exception("Transport CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Transport":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Transport CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
