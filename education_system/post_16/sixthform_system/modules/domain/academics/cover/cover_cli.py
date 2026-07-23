"""CLI flows for Sixth Form Cover."""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.academics.cover import (
    cover as data,
)
from education_system.post_16.sixthform_system.modules.domain.academics.cover.cover import (
    ABSENCE_REASONS,
    COVER_TYPES,
    CoverRequest,
    DEFAULT_COVER_TYPE,
    DEFAULT_REASON,
    DEFAULT_STATUS,
    STATUSES,
    ValidationError,
    YEAR_GROUPS,
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


def _pick_agency() -> int:
    from education_system.post_16.sixthform_system.modules.domain.academics.cover_agency import (
        cover_agency as _ag,
    )
    rows = _ag.list_agencies(active_only=True)
    if not rows:
        print("    No active agencies configured.")
        raise _UserAbort
    print("\n  Active agencies:")
    for i, a in enumerate(rows, 1):
        print(f"    {i:>3}) #{a.agency_id}  {a.name}  "
              f"{a.stars}  {a.rate_label}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].agency_id
            match = next((a for a in rows if a.agency_id == n), None)
            if match:
                return match.agency_id
        print("    No matching agency.")


def _pick_request() -> CoverRequest:
    rows = data.list_requests()
    if not rows:
        print("    No cover requests.")
        raise _UserAbort
    print("\n  Cover requests:")
    for i, r in enumerate(rows, 1):
        print(f"    {i:>3}) #{r.cover_id}  {r.absent_date}  "
              f"{r.absent_teacher[:18]:<18}  "
              f"{r.subject or '—':<14}  [{r.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows if r.cover_id == n), None)
            if match:
                return match
        print("    No matching cover.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_requests(rows: list[CoverRequest]) -> None:
    if not rows:
        print("\n  (no cover requests)")
        return
    print()
    print(f"  {'#':>4}  {'Date':<10}  {'Periods':<10}  "
          f"{'Absent':<16}  {'Subject':<14}  "
          f"{'Cover':<24}  Status")
    print("  " + "-" * 100)
    for r in rows:
        print(f"  {r.cover_id:>4}  {r.absent_date:<10}  "
              f"{(r.periods or '—')[:10]:<10}  "
              f"{r.absent_teacher[:16]:<16}  "
              f"{(r.subject or '—')[:14]:<14}  "
              f"{r.cover_label[:24]:<24}  {r.status}")
    print(f"\n  {len(rows)} request(s).")


# ── Flows ──────────────────────────────────────────────────────────

def list_today() -> None:
    print("\n═══ Today's Cover ═══")
    _print_requests(data.list_requests(today_only=True))
    _pause()


def list_open() -> None:
    print("\n═══ Open Cover ═══")
    _print_requests(data.list_requests(open_only=True))
    _pause()


def list_all() -> None:
    print("\n═══ All Cover ═══")
    _print_requests(data.list_requests())
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter Cover ═══")
    try:
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        ctype = _input(f"Type ({'/'.join(COVER_TYPES)})") or None
        absent = _input("Absent teacher contains") or None
        subject = _input("Subject contains") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_requests(
            status=status, cover_type=ctype,
            absent_teacher=absent, subject_like=subject,
            date_from=df, date_to=dt2,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_requests(rows)
    _pause()


def view_request_flow() -> None:
    print("\n═══ View Cover Request ═══")
    try:
        r = _pick_request()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    agency_name = None
    if r.agency_id is not None:
        try:
            from education_system.post_16.sixthform_system.modules.domain.academics.cover_agency import (
                cover_agency as _ag,
            )
            a = _ag.get_agency(r.agency_id)
            agency_name = a.name if a else None
        except Exception:
            pass
    print()
    print(f"    #{r.cover_id}  {r.absent_teacher}  on {r.absent_date}")
    print(f"    Reason            : {r.absent_reason or '—'}")
    print(f"    Periods           : {r.periods or '—'}")
    print(f"    Subject           : {r.subject or '—'}")
    print(f"    Year group        : {r.year_group or '—'}")
    print(f"    Class group       : "
          f"#{r.class_group_id or '—'}  {r.class_group_label or '—'}")
    print(f"    Room              : {r.room or '—'}")
    print(f"    Cover type        : {r.cover_type}")
    if r.cover_type == "Agency":
        print(f"    Agency            : "
              f"#{r.agency_id} {agency_name or '?'}")
        print(f"    Agency teacher    : {r.agency_teacher or '—'}")
    else:
        print(f"    Cover staff       : {r.cover_staff or '—'}")
    print(f"    Status            : {r.status}")
    print(f"    Requested on      : {r.requested_on or '—'}")
    print(f"    Allocated on      : {r.allocated_on or '—'}")
    print(f"    Confirmed on      : {r.confirmed_on or '—'}")
    print(f"    Completed on      : {r.completed_on or '—'}")
    if r.cost is not None:
        print(f"    Cost              : £{r.cost:.2f}")
    if r.notes:
        print()
        print("    Notes:")
        for line in r.notes.splitlines():
            print(f"      {line}")
    _pause()


def _collect_form(existing: CoverRequest | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["absent_teacher"] = _input(
        "Absent teacher",
        default=(existing.absent_teacher if is_edit else ""),
        allow_empty=False)
    payload["absent_reason"] = _pick_from(
        "Reason", [""] + list(ABSENCE_REASONS),
        default=(existing.absent_reason
                  if is_edit and existing.absent_reason
                  else DEFAULT_REASON))
    payload["absent_date"] = _input(
        "Absent date (YYYY-MM-DD)",
        default=(existing.absent_date if is_edit
                  else _dt.date.today().isoformat()),
        allow_empty=False)
    payload["periods"] = _input(
        "Periods (e.g. P1-P3)",
        default=(existing.periods or "") if is_edit else "")
    payload["subject"] = _input(
        "Subject",
        default=(existing.subject or "") if is_edit else "")
    payload["year_group"] = _pick_from(
        "Year group", [""] + list(YEAR_GROUPS),
        default=(existing.year_group if is_edit else ""))
    payload["class_group_id"] = _input(
        "Class group id (optional)",
        default=(str(existing.class_group_id)
                  if is_edit and existing.class_group_id
                  else ""))
    payload["class_group_label"] = _input(
        "Class group label",
        default=(existing.class_group_label or "") if is_edit else "")
    payload["room"] = _input(
        "Room",
        default=(existing.room or "") if is_edit else "")

    payload["cover_type"] = _pick_from(
        "Cover type", list(COVER_TYPES),
        default=(existing.cover_type if is_edit
                  else DEFAULT_COVER_TYPE))
    if payload["cover_type"] == "Agency":
        try:
            payload["agency_id"] = _pick_agency()
        except _UserAbort:
            raise
        payload["agency_teacher"] = _input(
            "Agency teacher name",
            default=(existing.agency_teacher or "")
            if is_edit else "")
    elif payload["cover_type"] == "Internal":
        payload["cover_staff"] = _input(
            "Cover staff",
            default=(existing.cover_staff or "")
            if is_edit else "")

    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["cost"] = _input(
        "Cost (£, optional)",
        default=(f"{existing.cost:.2f}"
                  if is_edit and existing.cost is not None else ""))
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_request() -> None:
    print("\n═══ New Cover Request ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.create_request(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created cover #{r.cover_id} for "
          f"{r.absent_teacher} on {r.absent_date}")
    _pause()


def edit_request() -> None:
    print("\n═══ Edit Cover Request ═══")
    try:
        r = _pick_request()
        payload = _collect_form(r)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_request(r.cover_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{r.cover_id}")
    _pause()


def allocate_flow() -> None:
    print("\n═══ Allocate Cover ═══")
    try:
        r = _pick_request()
        ctype = _pick_from("Cover type", list(COVER_TYPES),
                              default=r.cover_type)
        payload: dict[str, Any] = {"cover_type": ctype}
        if ctype == "Agency":
            payload["agency_id"] = _pick_agency()
            payload["agency_teacher"] = _input("Agency teacher name")
        elif ctype == "Internal":
            payload["cover_staff"] = _input(
                "Cover staff",
                default=r.cover_staff or "",
                allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.allocate(r.cover_id, **payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Allocated #{r.cover_id}")
    _pause()


def confirm_flow() -> None:
    print("\n═══ Confirm Cover ═══")
    try:
        r = _pick_request()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.confirm(r.cover_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Confirmed #{r.cover_id}")
    _pause()


def complete_flow() -> None:
    print("\n═══ Complete Cover ═══")
    try:
        r = _pick_request()
        cost = _input("Cost (£, optional)",
                       default=(f"{r.cost:.2f}"
                                  if r.cost is not None else ""))
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.complete(r.cover_id,
                        cost=float(cost) if cost else None)
    except (ValueError, ValidationError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Completed #{r.cover_id}")
    _pause()


def cancel_flow() -> None:
    print("\n═══ Cancel Cover ═══")
    try:
        r = _pick_request()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.cancel(r.cover_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Cancelled #{r.cover_id}")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        r = _pick_request()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=r.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(r.cover_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{r.cover_id} → {new_status}")
    _pause()


def delete_request_flow() -> None:
    print("\n═══ Delete Cover ═══")
    try:
        r = _pick_request()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete cover #{r.cover_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_request(r.cover_id):
        print(f"\n  ✓ Deleted #{r.cover_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Cover Summary ═══")
    try:
        win = int(_input("Upcoming window (days)", default="14"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = data.summary(upcoming_window_days=win)
    print(f"\n  Total requests    : {summ.total}")
    print(f"  Open              : {summ.open_count}")
    print(f"  Today             : {summ.today_count}")
    print(f"  This week         : {summ.this_week_count}")
    print(f"  Upcoming ({win}d)    : {summ.upcoming}")
    print(f"  Total cost        : £{summ.total_cost:.2f}")
    print("\n  By status:")
    for s in STATUSES:
        n = summ.by_status.get(s, 0)
        if n:
            print(f"    {s:<14} : {n}")
    print("\n  By type:")
    for t in COVER_TYPES:
        n = summ.by_type.get(t, 0)
        if n:
            print(f"    {t:<14} : {n}")
    print("\n  By reason:")
    for r in ABSENCE_REASONS:
        n = summ.by_reason.get(r, 0)
        if n:
            print(f"    {r:<22} : {n}")
    if summ.top_absent_teachers:
        print("\n  Most absent teachers:")
        for t, n in summ.top_absent_teachers.items():
            print(f"    {t:<22} : {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Today",               list_today),
    ("Open",                list_open),
    ("All",                 list_all),
    ("Filter",              filter_flow),
    ("View",                view_request_flow),
    ("New request",         new_request),
    ("Edit",                edit_request),
    ("Allocate",            allocate_flow),
    ("Confirm",             confirm_flow),
    ("Complete",            complete_flow),
    ("Cancel",              cancel_flow),
    ("Change status",       set_status_flow),
    ("Delete",              delete_request_flow),
    ("Summary",             summary_flow),
]


def run() -> None:
    while True:
        print("\n── Cover ──")
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
            logger.exception("Cover CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Cover":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Cover CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
