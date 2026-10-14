"""CLI flows for Sixth Form Cover Agencies."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.academics.cover_agency import (
    cover_agency as data,
)
from education_system.systems.sixth_form.domain.academics.cover_agency.cover_agency import (
    Agency,
    DEFAULT_STATUS,
    SPECIALISMS,
    STATUSES,
    ValidationError,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

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
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


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
            print("    Enter a number (or 'cancel' to abort).")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_agency() -> Agency:
    rows = data.list_agencies()
    if not rows:
        print("    No agencies.")
        raise _UserAbort
    print("\n  Agencies:")
    for i, a in enumerate(rows, 1):
        print(f"    {i:>3}) #{a.agency_id}  {a.name[:26]:<26}  "
              f"{a.stars}  [{a.status}]  {a.rate_label}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((a for a in rows if a.agency_id == n), None)
            if match:
                return match
        print("    No matching agency.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_agencies(rows: list[Agency]) -> None:
    if not rows:
        print("\n  (no agencies)")
        return
    print()
    print(f"  {'#':>4}  {'Name':<28}  {'Status':<10}  "
          f"{'Rating':<8}  {'Rate':<28}  Contact")
    print("  " + "-" * 100)
    for a in rows:
        contact = (a.contact_name or "—")
        if a.email:
            contact += f"  ·  {a.email}"
        print(f"  {a.agency_id:>4}  {a.name[:28]:<28}  "
              f"{a.status:<10}  {a.stars:<8}  "
              f"{a.rate_label[:28]:<28}  {contact[:30]}")
    print(f"\n  {len(rows)} agency/agencies.")


# ── Flows ──────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ Agencies ═══")
    _print_agencies(data.list_agencies())
    _pause()


def list_active() -> None:
    print("\n═══ Active Agencies ═══")
    _print_agencies(data.list_agencies(active_only=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter Agencies ═══")
    try:
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        min_rate = _input("Min rating (1-5)") or None
        spec = _input("Specialism contains") or None
        search = _input("Search (name/contact/email)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_agencies(
            status=status,
            min_rating=int(min_rate) if min_rate else None,
            specialism_like=spec, search=search,
        )
    except (ValueError, ValidationError) as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_agencies(rows)
    _pause()


def view_agency_flow() -> None:
    print("\n═══ View Agency ═══")
    try:
        a = _pick_agency()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    print()
    print(f"    #{a.agency_id}  {a.name}")
    print(f"    Status         : {a.status}")
    print(f"    Rating         : {a.stars}  "
          f"({a.rating if a.rating else '—'}/5)")
    print(f"    Contact        : {a.contact_name or '—'}")
    print(f"    Email          : {a.email or '—'}")
    print(f"    Phone          : {a.phone or '—'}")
    print(f"    Website        : {a.website or '—'}")
    print(f"    Address        : {a.address or '—'}")
    print(f"    Specialisms    : {a.specialisms or '—'}")
    print(f"    Hourly rate    : £{a.hourly_rate:.2f}"
          if a.hourly_rate is not None else "    Hourly rate    : —")
    print(f"    Daily rate     : £{a.daily_rate:.2f}"
          if a.daily_rate is not None else "    Daily rate     : —")
    print(f"    Onboarded on   : {a.onboarded_on or '—'}")
    print(f"    Last used on   : {a.last_used_on or '—'}")
    if a.notes:
        print()
        print("    Notes:")
        for line in a.notes.splitlines():
            print(f"      {line}")
    _pause()


def _collect_form(existing: Agency | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["name"] = _input(
        "Name",
        default=(existing.name if is_edit else ""),
        allow_empty=False)
    payload["contact_name"] = _input(
        "Contact name",
        default=(existing.contact_name or "") if is_edit else "")
    payload["email"] = _input(
        "Email",
        default=(existing.email or "") if is_edit else "")
    payload["phone"] = _input(
        "Phone",
        default=(existing.phone or "") if is_edit else "")
    payload["website"] = _input(
        "Website",
        default=(existing.website or "") if is_edit else "")
    payload["address"] = _input(
        "Address",
        default=(existing.address or "") if is_edit else "")
    payload["specialisms"] = _input(
        f"Specialisms (e.g. {SPECIALISMS[0]}, {SPECIALISMS[1]})",
        default=(existing.specialisms or "") if is_edit else "")
    payload["hourly_rate"] = _input(
        "Hourly rate (£)",
        default=(f"{existing.hourly_rate:.2f}"
                  if is_edit and existing.hourly_rate is not None
                  else ""))
    payload["daily_rate"] = _input(
        "Daily rate (£)",
        default=(f"{existing.daily_rate:.2f}"
                  if is_edit and existing.daily_rate is not None
                  else ""))
    payload["rating"] = _input(
        "Rating (1-5)",
        default=(str(existing.rating)
                  if is_edit and existing.rating is not None
                  else ""))
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["onboarded_on"] = _input(
        "Onboarded on (YYYY-MM-DD)",
        default=(existing.onboarded_on or "") if is_edit else "")
    payload["last_used_on"] = _input(
        "Last used on (YYYY-MM-DD)",
        default=(existing.last_used_on or "") if is_edit else "")
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_agency() -> None:
    print("\n═══ New Agency ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_agency(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created agency #{a.agency_id} {a.name!r}")
    _pause()


def edit_agency() -> None:
    print("\n═══ Edit Agency ═══")
    try:
        a = _pick_agency()
        payload = _collect_form(a)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_agency(a.agency_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{a.agency_id}")
    _pause()


def set_rating_flow() -> None:
    print("\n═══ Set Rating ═══")
    try:
        a = _pick_agency()
        n = int(_input("Rating (1-5)",
                          default=str(a.rating) if a.rating else "",
                          allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        data.set_rating(a.agency_id, n)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.agency_id} → {n}/5")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        a = _pick_agency()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=a.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(a.agency_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.agency_id} → {new_status}")
    _pause()


def record_use_flow() -> None:
    print("\n═══ Record Use ═══")
    try:
        a = _pick_agency()
        when = _input("When (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.record_use(a.agency_id, when=when)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.agency_id} last_used_on = {when}")
    _pause()


def delete_agency_flow() -> None:
    print("\n═══ Delete Agency ═══")
    try:
        a = _pick_agency()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(
            f"Delete agency #{a.agency_id} ({a.name})? Type 'yes'",
            default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_agency(a.agency_id):
        print(f"\n  ✓ Deleted #{a.agency_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Cover Agency Summary ═══")
    summ = data.summary()
    print(f"\n  Total agencies     : {summ.total}")
    print(f"  Active             : {summ.active_count}")
    print(f"  Used in last 30d   : {summ.used_recently}")
    print(f"  Average rating     : "
          f"{summ.average_rating if summ.average_rating is not None else '—'}")
    print(f"  Avg daily rate     : "
          f"{('£' + format(summ.rate_average_daily, '.2f')) if summ.rate_average_daily is not None else '—'}")
    print(f"  Avg hourly rate    : "
          f"{('£' + format(summ.rate_average_hourly, '.2f')) if summ.rate_average_hourly is not None else '—'}")
    print("\n  By status:")
    for s in STATUSES:
        n = summ.by_status.get(s, 0)
        if n:
            print(f"    {s:<14} : {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",         list_all),
    ("List active",      list_active),
    ("Filter",           filter_flow),
    ("View",             view_agency_flow),
    ("New",              new_agency),
    ("Edit",             edit_agency),
    ("Set rating",       set_rating_flow),
    ("Change status",    set_status_flow),
    ("Record use",       record_use_flow),
    ("Delete",           delete_agency_flow),
    ("Summary",          summary_flow),
]


def run() -> None:
    while True:
        print("\n── Cover Agencies ──")
        for i, (label, _) in enumerate(_MENU, 1):
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
        _, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Cover-agency CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Cover Agency":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Cover-agency CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
