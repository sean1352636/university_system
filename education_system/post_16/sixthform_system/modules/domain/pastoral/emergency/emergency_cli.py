"""CLI flows for Sixth Form Emergency Incidents."""

from __future__ import annotations

import logging
from datetime import date as _date
from datetime import datetime as _dt
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.pastoral.emergency import (
    emergency as data,
)
from education_system.post_16.sixthform_system.modules.domain.pastoral.emergency.emergency import (
    DEFAULT_EMERGENCY_TYPE,
    DEFAULT_STATUS,
    EMERGENCY_TYPES,
    Emergency,
    SEVERITIES,
    STATUSES,
    ValidationError,
    severity_label,
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


def _pick_incident() -> Emergency:
    rows = data.list_incidents()
    if not rows:
        print("    No incidents yet.")
        raise _UserAbort
    print("\n  Emergency incidents:")
    for i, e in enumerate(rows, 1):
        print(f"    {i:>3}) #{e.incident_id}  "
              f"{e.incident_date}  "
              f"{e.incident_type[:18]:<18}  sev={e.severity}  "
              f"[{e.status}]  {e.title[:32]}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.incident_id == n), None)
            if match:
                return match
        print("    No matching incident.")


def _print_table(rows: list[Emergency]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Date':<10} {'Time':<5}  "
          f"{'Type':<22}  Sev  {'Title':<28}  "
          f"{'Status':<12}  Flags")
    print("  " + "-" * 130)
    for e in rows:
        flags = []
        if e.evacuation:
            flags.append("EVAC")
        if e.lockdown:
            flags.append("LOCK")
        if e.police_called:
            flags.append("POL")
        if e.fire_called:
            flags.append("FIRE")
        if e.ambulance_called:
            flags.append("AMB")
        print(f"  {e.incident_id:>4}  "
              f"{e.incident_date:<10} {(e.incident_time or '—'):<5}  "
              f"{e.incident_type[:22]:<22}  "
              f"{e.severity:>3}  "
              f"{e.title[:28]:<28}  "
              f"{e.status:<12}  {','.join(flags)}")
    print(f"\n  {len(rows)} incident(s).")


def _print_full(e: Emergency) -> None:
    print()
    print(f"    #{e.incident_id}  {e.title}")
    print(f"    Date / time      : {e.incident_date}  "
          f"{e.incident_time or '—'}")
    print(f"    Type             : {e.incident_type}")
    print(f"    Severity         : {e.severity}  "
          f"({e.severity_label})")
    print(f"    Location         : {e.location or '—'}")
    print(f"    Reported by      : {e.reported_by}")
    print(f"    Lead responder   : {e.lead_responder or '—'}")
    print(f"    Status           : {e.status}")
    print(f"    Resolved         : "
          f"{e.resolved_on or '—'}  {e.resolved_time or ''}")
    print(f"    Debriefed on     : {e.debriefed_on or '—'}")
    print(f"    Evacuation/Lockd : "
          f"{'EVAC ' if e.evacuation else ''}"
          f"{'LOCKDOWN' if e.lockdown else ''}".strip() or "—")
    services = []
    if e.police_called:
        services.append("Police")
    if e.fire_called:
        services.append("Fire")
    if e.ambulance_called:
        services.append("Ambulance")
    print(f"    Services         : "
          f"{', '.join(services) if services else 'none'}")
    print(f"    Parents informed : "
          f"{'yes' if e.parents_informed else 'no'}")
    print(f"    Governors        : "
          f"{'informed' if e.governors_informed else 'no'}")
    if e.students_affected:
        print(f"    Students affected: {e.students_affected}")
    if e.staff_affected:
        print(f"    Staff affected   : {e.staff_affected}")
    for label, val in (
            ("Description",     e.description),
            ("Incident log",    e.incident_log),
            ("Actions taken",   e.actions_taken),
            ("Follow-up notes", e.follow_up_notes),
            ("Debrief notes",   e.debrief_notes),
            ("Lessons learned", e.lessons_learned),
            ("Notes",           e.notes),
    ):
        if val:
            print(f"\n    {label}:")
            for line in val.splitlines():
                print(f"      {line}")


# ── Flows ────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Emergency Incidents ═══")
    _print_table(data.list_incidents())
    _pause()


def list_open() -> None:
    print("\n═══ Open ═══")
    _print_table(data.list_incidents(open_only=True))
    _pause()


def list_awaiting_debrief() -> None:
    print("\n═══ Awaiting Debrief ═══")
    _print_table(data.list_incidents(awaiting_debrief=True))
    _pause()


def list_evacuations() -> None:
    print("\n═══ Evacuations ═══")
    _print_table(data.list_incidents(evacuation_only=True))
    _pause()


def list_lockdowns() -> None:
    print("\n═══ Lockdowns ═══")
    _print_table(data.list_incidents(lockdown_only=True))
    _pause()


def list_services() -> None:
    print("\n═══ Emergency Services Called ═══")
    _print_table(data.list_incidents(services_only=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        etype = _input(
            f"Type ({'/'.join(EMERGENCY_TYPES[:2])}…)") or None
        status = _input(f"Status ({'/'.join(STATUSES[:3])}…)") or None
        sev_raw = _input("Min severity (1-5)") or None
        rep = _input("Reported by contains") or None
        loc = _input("Location contains") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    sev = int(sev_raw) if sev_raw and sev_raw.isdigit() else None
    try:
        rows = data.list_incidents(
            incident_type=etype, status=status,
            severity_min=sev, reported_by_like=rep,
            location_like=loc, date_from=df, date_to=dt2)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_table(rows)
    _pause()


def view_flow() -> None:
    print("\n═══ View Incident ═══")
    try:
        e = _pick_incident()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_full(e)
    _pause()


def _collect_form(existing: Emergency | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["title"] = _input(
        "Title",
        default=(existing.title if is_edit else ""),
        allow_empty=False)
    payload["incident_date"] = _input(
        "Incident date (YYYY-MM-DD)",
        default=(existing.incident_date if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    payload["incident_time"] = _input(
        "Time (HH:MM)",
        default=(existing.incident_time
                  if is_edit and existing.incident_time
                  else _dt.now().strftime("%H:%M")))
    payload["incident_type"] = _pick_from(
        "Type", list(EMERGENCY_TYPES),
        default=(existing.incident_type if is_edit
                  else DEFAULT_EMERGENCY_TYPE))
    payload["severity"] = _input(
        "Severity (1-5)",
        default=(str(existing.severity) if is_edit else "2"))
    payload["location"] = _input(
        "Location",
        default=(existing.location or "") if is_edit else "")
    payload["reported_by"] = _input(
        "Reported by",
        default=(existing.reported_by if is_edit else ""),
        allow_empty=False)
    payload["lead_responder"] = _input(
        "Lead responder",
        default=(existing.lead_responder or "")
        if is_edit else "")
    try:
        payload["description"] = _multiline(
            "Description",
            default=(existing.description or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["evacuation"] = _yes_no(
        "Evacuation?",
        default=(existing.evacuation if is_edit else False))
    payload["lockdown"] = _yes_no(
        "Lockdown?",
        default=(existing.lockdown if is_edit else False))
    payload["police_called"] = _yes_no(
        "Police called?",
        default=(existing.police_called if is_edit else False))
    payload["fire_called"] = _yes_no(
        "Fire called?",
        default=(existing.fire_called if is_edit else False))
    payload["ambulance_called"] = _yes_no(
        "Ambulance called?",
        default=(existing.ambulance_called if is_edit else False))
    payload["students_affected"] = _input(
        "Students affected (free text)",
        default=(existing.students_affected or "")
        if is_edit else "")
    payload["staff_affected"] = _input(
        "Staff affected",
        default=(existing.staff_affected or "")
        if is_edit else "")
    payload["parents_informed"] = _yes_no(
        "Parents informed?",
        default=(existing.parents_informed if is_edit else False))
    payload["governors_informed"] = _yes_no(
        "Governors informed?",
        default=(existing.governors_informed
                  if is_edit else False))
    try:
        payload["incident_log"] = _multiline(
            "Incident log",
            default=(existing.incident_log or "")
            if is_edit else "")
        payload["actions_taken"] = _multiline(
            "Actions taken",
            default=(existing.actions_taken or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["resolved_on"] = _input(
        "Resolved on (YYYY-MM-DD)",
        default=(existing.resolved_on or "") if is_edit else "")
    payload["resolved_time"] = _input(
        "Resolved time (HH:MM)",
        default=(existing.resolved_time or "")
        if is_edit else "")
    payload["follow_up_required"] = _yes_no(
        "Follow-up required?",
        default=(existing.follow_up_required
                  if is_edit else False))
    if payload["follow_up_required"]:
        try:
            payload["follow_up_notes"] = _multiline(
                "Follow-up notes",
                default=(existing.follow_up_notes or "")
                if is_edit else "")
        except _UserAbort:
            raise
    try:
        payload["debrief_notes"] = _multiline(
            "Debrief notes",
            default=(existing.debrief_notes or "")
            if is_edit else "")
        payload["lessons_learned"] = _multiline(
            "Lessons learned",
            default=(existing.lessons_learned or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["debriefed_on"] = _input(
        "Debriefed on (YYYY-MM-DD)",
        default=(existing.debriefed_on or "")
        if is_edit else "")
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_incident() -> None:
    print("\n═══ New Emergency Incident ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        e = data.create_incident(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created incident #{e.incident_id}")
    _pause()


def edit_incident() -> None:
    print("\n═══ Edit Incident ═══")
    try:
        e = _pick_incident()
        payload = _collect_form(e)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_incident(e.incident_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{e.incident_id}")
    _pause()


def append_log_flow() -> None:
    print("\n═══ Append to Log ═══")
    try:
        e = _pick_incident()
        entry = _multiline("Log entry")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not entry:
        print("  ✗ Entry required.")
        _pause()
        return
    try:
        data.append_log(e.incident_id, entry=entry)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Log entry added to #{e.incident_id}")
    _pause()


def start_response_flow() -> None:
    print("\n═══ Start Response ═══")
    try:
        e = _pick_incident()
        lead = _input("Lead responder",
                         default=e.lead_responder or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.start_response(e.incident_id,
                                  lead_responder=lead or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{e.incident_id} → Responding")
    _pause()


def resolve_flow() -> None:
    print("\n═══ Resolve ═══")
    try:
        e = _pick_incident()
        actions = _multiline("Actions taken",
                                default=e.actions_taken or "")
        when = _input("Resolved on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
        time_ = _input("Resolved time (HH:MM)",
                          default=_dt.now().strftime("%H:%M"))
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.resolve(e.incident_id,
                        actions_taken=actions or None,
                        resolved_on=when,
                        resolved_time=time_ or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{e.incident_id} → Resolved")
    _pause()


def debrief_flow() -> None:
    print("\n═══ Record Debrief ═══")
    try:
        e = _pick_incident()
        notes = _multiline("Debrief notes",
                              default=e.debrief_notes or "")
        if not notes:
            print("  ✗ Debrief notes required.")
            _pause()
            return
        lessons = _multiline("Lessons learned",
                                default=e.lessons_learned or "")
        when = _input("Debriefed on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.record_debrief(e.incident_id, debrief_notes=notes,
                                  lessons_learned=lessons or None,
                                  debriefed_on=when)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{e.incident_id} → Debriefed")
    _pause()


def close_flow() -> None:
    print("\n═══ Close ═══")
    try:
        e = _pick_incident()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.close_incident(e.incident_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{e.incident_id} → Closed")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        e = _pick_incident()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=e.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(e.incident_id, new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{e.incident_id} → {new_status}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete ═══")
    try:
        e = _pick_incident()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete #{e.incident_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_incident(e.incident_id):
        print(f"\n  ✓ Deleted #{e.incident_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Emergency Summary ═══")
    s = data.summary()
    print(f"\n  Total                : {s.total}")
    print(f"  Open                 : {s.open_count}")
    print(f"  Major / Critical     : {s.major_or_critical}")
    print(f"  Services called      : {s.services_called}")
    print(f"  Evacuations          : {s.evacuations}")
    print(f"  Lockdowns            : {s.lockdowns}")
    print(f"  Drills               : {s.drills}")
    print(f"  Awaiting debrief     : {s.awaiting_debrief}")
    print(f"  Average severity     : "
          f"{s.average_severity if s.average_severity is not None else '—'}")
    print("\n  By type:")
    for k in EMERGENCY_TYPES:
        n = s.by_type.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By severity:")
    for sev in SEVERITIES:
        n = s.by_severity.get(sev, 0)
        if n:
            print(f"    {sev}  {severity_label(sev):<14}: {n}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",            list_all),
    ("List open",           list_open),
    ("Awaiting debrief",    list_awaiting_debrief),
    ("Evacuations",         list_evacuations),
    ("Lockdowns",           list_lockdowns),
    ("Services called",     list_services),
    ("Filter",              filter_flow),
    ("View",                view_flow),
    ("─" * 6,               lambda: None),
    ("New incident",        new_incident),
    ("Edit incident",       edit_incident),
    ("Append to log",       append_log_flow),
    ("Start response",      start_response_flow),
    ("Resolve",             resolve_flow),
    ("Record debrief",      debrief_flow),
    ("Close",               close_flow),
    ("Change status",       set_status_flow),
    ("Delete",              delete_flow),
    ("─" * 6,               lambda: None),
    ("Summary",             summary_flow),
]


def run() -> None:
    while True:
        print("\n── Emergency ──")
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
            logger.exception("Emergency CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Emergency":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Emergency CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
