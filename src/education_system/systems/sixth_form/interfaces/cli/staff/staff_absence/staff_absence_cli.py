"""CLI flows for Sixth Form Staff Absence."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.staff.staff_absence import (
    staff_absence as data,
)
from education_system.systems.sixth_form.domain.staff.staff_absence.staff_absence import (
    ABSENCE_TYPES,
    Absence,
    CERTIFICATE_TYPES,
    COVER_SOURCES,
    DEFAULT_ABSENCE_TYPE,
    DEFAULT_CERTIFICATE_TYPE,
    DEFAULT_COVER_SOURCE,
    DEFAULT_NOTIFICATION_METHOD,
    DEFAULT_STATUS,
    NOTIFICATION_METHODS,
    STATUSES,
    ValidationError,
)
from education_system.systems.sixth_form.domain.staff import (
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


def _pick_staff() -> str:
    rows = _staff.list_staff()
    if not rows:
        print("    No staff.")
        raise _UserAbort
    print("\n  Staff:")
    for i, s in enumerate(rows, 1):
        full = f"{getattr(s, 'first_name', '')} " \
               f"{getattr(s, 'last_name', '')}".strip()
        print(f"    {i:>3}) {s.staff_id:<12}  {full}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].staff_id
        match = next((s for s in rows
                        if s.staff_id == raw.upper()), None)
        if match:
            return match.staff_id
        print("    No matching staff.")


def _pick_absence() -> Absence:
    rows = data.list_absences()
    if not rows:
        print("    No absences yet.")
        raise _UserAbort
    print("\n  Absences:")
    for i, a in enumerate(rows, 1):
        flag = ""
        if a.cover_outstanding:
            flag += "C"
        if a.critical:
            flag += "!"
        print(f"    {i:>3}){flag:<2} #{a.absence_id}  "
              f"{a.absence_date}  {a.staff_id:<12}  "
              f"{a.absence_type[:18]:<18}  [{a.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.absence_id == n), None)
            if match:
                return match
        print("    No matching absence.")


def _print_table(rows: list[Absence]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Date':<10}  {'Staff':<12}  "
          f"{'Type':<22}  {'Exp Return':<12}  "
          f"{'Status':<12}  {'Cover':<14}  Flags")
    print("  " + "-" * 130)
    for a in rows:
        flags = []
        if a.critical:
            flags.append("CRIT")
        if a.cover_outstanding:
            flags.append("COVER-PEND")
        if a.return_overdue:
            flags.append("RET-OVERDUE")
        if a.rtw_overdue:
            flags.append("RTW")
        print(f"  {a.absence_id:>4}  {a.absence_date:<10}  "
              f"{a.staff_id:<12}  "
              f"{a.absence_type[:22]:<22}  "
              f"{(a.expected_return or '—'):<12}  "
              f"{a.status:<12}  "
              f"{a.cover_source[:14]:<14}  "
              f"{','.join(flags)}")
    print(f"\n  {len(rows)} absence(s).")


def _print_full(a: Absence) -> None:
    print()
    print(f"    #{a.absence_id}  Staff {a.staff_id}")
    print(f"    Absence date     : {a.absence_date}")
    print(f"    Expected return  : {a.expected_return or '—'}"
          + ("  (OVERDUE)" if a.return_overdue else ""))
    print(f"    Actual return    : {a.actual_return or '—'}")
    print(f"    Type             : {a.absence_type}")
    print(f"    Reason           : {a.reason or '—'}")
    print(f"    Notified on      : {a.notified_on or '—'}")
    print(f"    Notification     : {a.notification_method}")
    print(f"    Notified by      : {a.notified_by or '—'}")
    print(f"    Certificate      : {a.certificate_type}  "
          f"received {a.cert_received_on or '—'}")
    print(f"    Cover required   : "
          f"{'yes' if a.cover_required else 'no'}")
    print(f"    Cover source     : {a.cover_source}"
          + ("  (PENDING)" if a.cover_outstanding else ""))
    print(f"    Cover arranged by: {a.cover_arranged_by or '—'}")
    print(f"    Critical         : "
          f"{'yes' if a.critical else 'no'}")
    print(f"    Parents informed : "
          f"{'yes' if a.parents_informed else 'no'}")
    print(f"    SLT informed     : "
          f"{'yes' if a.slt_informed else 'no'}")
    print(f"    RTW required     : "
          f"{'yes' if a.rtw_required else 'no'}")
    print(f"    RTW meeting on   : {a.rtw_meeting_on or '—'}"
          + ("  (OVERDUE)" if a.rtw_overdue else ""))
    print(f"    RTW completed by : {a.rtw_completed_by or '—'}")
    print(f"    Days lost        : "
          f"{a.days_lost if a.days_lost is not None else '—'}")
    print(f"    Status           : {a.status}")
    for label, val in (
            ("Cover notes", a.cover_notes),
            ("Notes",       a.notes),
    ):
        if val:
            print(f"\n    {label}:")
            for line in val.splitlines():
                print(f"      {line}")


# ── Flows ────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Absences ═══")
    _print_table(data.list_absences())
    _pause()


def list_open() -> None:
    print("\n═══ Open Absences ═══")
    _print_table(data.list_absences(open_only=True))
    _pause()


def list_active_today() -> None:
    print("\n═══ Active Today ═══")
    _print_table(data.list_absences(active_today=True))
    _pause()


def list_critical() -> None:
    print("\n═══ Critical Open ═══")
    _print_table(data.list_absences(critical_only=True,
                                          open_only=True))
    _pause()


def list_cover_outstanding() -> None:
    print("\n═══ Cover Outstanding ═══")
    _print_table(data.list_absences(cover_outstanding=True))
    _pause()


def list_return_overdue() -> None:
    print("\n═══ Return Overdue ═══")
    _print_table(data.list_absences(return_overdue=True))
    _pause()


def list_rtw_overdue() -> None:
    print("\n═══ RTW Overdue ═══")
    _print_table(data.list_absences(rtw_overdue=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        sid = _input("Staff id") or None
        at = _input(
            f"Type ({'/'.join(ABSENCE_TYPES[:3])}…)") or None
        status = _input(
            f"Status ({'/'.join(STATUSES[:3])}…)") or None
        cs = _input(
            f"Cover source ({'/'.join(COVER_SOURCES[:3])}…)") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_absences(staff_id=sid, absence_type=at,
                                       status=status, cover_source=cs,
                                       date_from=df, date_to=dt2)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_table(rows)
    _pause()


def per_staff_flow() -> None:
    print("\n═══ Per-Staff ═══")
    try:
        sid = _pick_staff()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_table(data.absences_for_staff(sid))
    _pause()


def view_flow() -> None:
    print("\n═══ View Absence ═══")
    try:
        a = _pick_absence()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_full(a)
    _pause()


def _collect_form(existing: Absence | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["staff_id"] = existing.staff_id
    else:
        payload["staff_id"] = _pick_staff()
    payload["absence_date"] = _input(
        "Absence date (YYYY-MM-DD)",
        default=(existing.absence_date if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    payload["expected_return"] = _input(
        "Expected return (YYYY-MM-DD)",
        default=(existing.expected_return or "")
        if is_edit else "")
    payload["actual_return"] = _input(
        "Actual return (YYYY-MM-DD)",
        default=(existing.actual_return or "")
        if is_edit else "")
    payload["absence_type"] = _pick_from(
        "Absence type", list(ABSENCE_TYPES),
        default=(existing.absence_type if is_edit
                  else DEFAULT_ABSENCE_TYPE))
    payload["reason"] = _input(
        "Reason",
        default=(existing.reason or "") if is_edit else "")
    payload["notified_on"] = _input(
        "Notified on (YYYY-MM-DD)",
        default=(existing.notified_on
                  or _date.today().isoformat())
        if is_edit else _date.today().isoformat())
    payload["notification_method"] = _pick_from(
        "Notification method", list(NOTIFICATION_METHODS),
        default=(existing.notification_method if is_edit
                  else DEFAULT_NOTIFICATION_METHOD))
    payload["notified_by"] = _input(
        "Notified by",
        default=(existing.notified_by or "")
        if is_edit else "")
    payload["certificate_type"] = _pick_from(
        "Certificate", list(CERTIFICATE_TYPES),
        default=(existing.certificate_type if is_edit
                  else DEFAULT_CERTIFICATE_TYPE))
    payload["cert_received_on"] = _input(
        "Cert received on (YYYY-MM-DD)",
        default=(existing.cert_received_on or "")
        if is_edit else "")
    payload["cover_required"] = _yes_no(
        "Cover required?",
        default=(existing.cover_required if is_edit else True))
    payload["cover_source"] = _pick_from(
        "Cover source", list(COVER_SOURCES),
        default=(existing.cover_source if is_edit
                  else DEFAULT_COVER_SOURCE))
    payload["cover_arranged_by"] = _input(
        "Cover arranged by",
        default=(existing.cover_arranged_by or "")
        if is_edit else "")
    try:
        payload["cover_notes"] = _multiline(
            "Cover notes",
            default=(existing.cover_notes or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["critical"] = _yes_no(
        "Critical absence?",
        default=(existing.critical if is_edit else False))
    payload["parents_informed"] = _yes_no(
        "Parents informed?",
        default=(existing.parents_informed if is_edit
                  else False))
    payload["slt_informed"] = _yes_no(
        "SLT informed?",
        default=(existing.slt_informed if is_edit else False))
    payload["rtw_required"] = _yes_no(
        "RTW meeting required?",
        default=(existing.rtw_required if is_edit else False))
    if payload["rtw_required"]:
        payload["rtw_meeting_on"] = _input(
            "RTW meeting on (YYYY-MM-DD)",
            default=(existing.rtw_meeting_on or "")
            if is_edit else "")
        payload["rtw_completed_by"] = _input(
            "RTW completed by",
            default=(existing.rtw_completed_by or "")
            if is_edit else "")
    payload["days_lost"] = _input(
        "Days lost",
        default=(str(existing.days_lost)
                  if is_edit and existing.days_lost is not None
                  else ""))
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


def new_absence() -> None:
    print("\n═══ New Absence ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_absence(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created absence #{a.absence_id}")
    _pause()


def edit_absence() -> None:
    print("\n═══ Edit Absence ═══")
    try:
        a = _pick_absence()
        payload = _collect_form(a)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_absence(a.absence_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{a.absence_id}")
    _pause()


def confirm_flow() -> None:
    print("\n═══ Confirm Absence ═══")
    try:
        a = _pick_absence()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.confirm_absence(a.absence_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{a.absence_id} confirmed")
    _pause()


def arrange_cover_flow() -> None:
    print("\n═══ Arrange Cover ═══")
    try:
        a = _pick_absence()
        source = _pick_from("Cover source",
                                list(COVER_SOURCES),
                                default=a.cover_source)
        arranged = _input("Arranged by",
                              default=a.cover_arranged_by or "")
        notes = _multiline("Cover notes",
                              default=a.cover_notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.arrange_cover(a.absence_id, source=source,
                                arranged_by=arranged or None,
                                notes=notes or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Cover arranged on #{a.absence_id}")
    _pause()


def record_return_flow() -> None:
    print("\n═══ Record Return ═══")
    try:
        a = _pick_absence()
        when = _input("Returned on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
        days_raw = _input("Days lost (blank = auto)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    days = (float(days_raw) if days_raw
            and days_raw.replace(".", "", 1).isdigit() else None)
    try:
        data.record_return(a.absence_id, returned_on=when,
                                days_lost=days)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Return recorded on #{a.absence_id}")
    _pause()


def complete_rtw_flow() -> None:
    print("\n═══ Complete RTW ═══")
    try:
        a = _pick_absence()
        by = _input("Completed by",
                       default=a.rtw_completed_by or "",
                       allow_empty=False)
        when = _input("Meeting on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.complete_rtw(a.absence_id, completed_by=by,
                              meeting_on=when)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ RTW completed on #{a.absence_id}")
    _pause()


def close_flow() -> None:
    print("\n═══ Close ═══")
    try:
        a = _pick_absence()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.close_absence(a.absence_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{a.absence_id} → Closed")
    _pause()


def cancel_flow() -> None:
    print("\n═══ Cancel ═══")
    try:
        a = _pick_absence()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.cancel_absence(a.absence_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{a.absence_id} → Cancelled")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        a = _pick_absence()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=a.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(a.absence_id, new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{a.absence_id} → {new_status}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete ═══")
    try:
        a = _pick_absence()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete absence #{a.absence_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_absence(a.absence_id):
        print(f"\n  ✓ Deleted #{a.absence_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Staff Absence Summary ═══")
    s = data.summary()
    print(f"\n  Total                : {s.total}")
    print(f"  Open                 : {s.open_count}")
    print(f"  Active today         : {s.active_today}")
    print(f"  Cover outstanding    : {s.cover_outstanding}")
    print(f"  Critical open        : {s.critical_open}")
    print(f"  RTW overdue          : {s.rtw_overdue}")
    print(f"  Return overdue       : {s.return_overdue}")
    print(f"  Awaiting certificate : {s.awaiting_cert}")
    print(f"  Parents pending      : {s.parents_pending}")
    print(f"  Distinct staff       : {s.distinct_staff}")
    print(f"  Total days lost      : {s.total_days_lost}")
    print("\n  By type:")
    for k in ABSENCE_TYPES:
        n = s.by_type.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    print("\n  By cover source:")
    for k in COVER_SOURCES:
        n = s.by_cover_source.get(k, 0)
        if n:
            print(f"    {k:<18}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",          list_all),
    ("Open only",         list_open),
    ("Active today",      list_active_today),
    ("Critical open",     list_critical),
    ("Cover outstanding", list_cover_outstanding),
    ("Return overdue",    list_return_overdue),
    ("RTW overdue",       list_rtw_overdue),
    ("Filter",            filter_flow),
    ("Per-staff",         per_staff_flow),
    ("View",              view_flow),
    ("─" * 6,             lambda: None),
    ("New absence",       new_absence),
    ("Edit absence",      edit_absence),
    ("Confirm",           confirm_flow),
    ("Arrange cover",     arrange_cover_flow),
    ("Record return",     record_return_flow),
    ("Complete RTW",      complete_rtw_flow),
    ("Close",             close_flow),
    ("Cancel",            cancel_flow),
    ("Change status",     set_status_flow),
    ("Delete",            delete_flow),
    ("─" * 6,             lambda: None),
    ("Summary",           summary_flow),
]


def run() -> None:
    while True:
        print("\n── Staff Absence ──")
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
            logger.exception("Staff Absence CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Staff Absence":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Staff Absence CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
