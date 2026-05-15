"""CLI flows for Sixth Form First Aid."""

from __future__ import annotations

import logging
from datetime import date as _date
from datetime import datetime as _dt
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.pastoral.first_aid import (
    first_aid as data,
)
from education_system.sixthform_system.modules.domain.pastoral.first_aid.first_aid import (
    DEFAULT_NATURE,
    DEFAULT_STATUS,
    Incident,
    NATURES,
    SEVERITIES,
    STATUSES,
    ValidationError,
    severity_label,
)
from education_system.sixthform_system.modules.domain.students.students import (
    students as _students,
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


def _pick_incident() -> Incident:
    rows = data.list_incidents()
    if not rows:
        print("    No incidents yet.")
        raise _UserAbort
    print("\n  Incidents:")
    for i, inc in enumerate(rows, 1):
        flag = "!" if inc.follow_up_overdue else " "
        print(f"    {i:>3}){flag}#{inc.incident_id}  "
              f"{inc.incident_date}  {inc.student_id:<12}  "
              f"{inc.nature[:18]:<18}  sev={inc.severity}  "
              f"[{inc.status}]")
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


def _print_table(rows: list[Incident]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Date':<10} {'Time':<5}  "
          f"{'Student':<12}  {'Nature':<22}  Sev  "
          f"{'First aider':<14}  {'Status':<18}  Flags")
    print("  " + "-" * 130)
    for i in rows:
        flags = []
        if i.ambulance_called:
            flags.append("AMB")
        if i.hospital_referral:
            flags.append("HOSP")
        if i.sent_home:
            flags.append("HOME")
        if not i.parent_informed and i.is_open:
            flags.append("P-PEND")
        if i.follow_up_overdue:
            flags.append("FU-OVERDUE")
        print(f"  {i.incident_id:>4}  "
              f"{i.incident_date:<10} {(i.incident_time or '—'):<5}  "
              f"{i.student_id:<12}  "
              f"{i.nature[:22]:<22}  "
              f"{i.severity:>3}  "
              f"{i.first_aider[:14]:<14}  "
              f"{i.status:<18}  {','.join(flags)}")
    print(f"\n  {len(rows)} incident(s).")


def _print_full(i: Incident) -> None:
    print()
    print(f"    #{i.incident_id}  Student {i.student_id}")
    print(f"    Date / time      : {i.incident_date}  "
          f"{i.incident_time or '—'}")
    print(f"    Location         : {i.location or '—'}")
    print(f"    Nature           : {i.nature}")
    print(f"    Severity         : {i.severity}  "
          f"({i.severity_label})")
    print(f"    First aider      : {i.first_aider}")
    print(f"    Ambulance        : "
          f"{'yes' if i.ambulance_called else 'no'}")
    print(f"    Hospital referral: "
          f"{'yes' if i.hospital_referral else 'no'}")
    print(f"    Sent home        : "
          f"{'yes' if i.sent_home else 'no'}")
    print(f"    Parent informed  : "
          f"{'yes' if i.parent_informed else 'no'}"
          f"  on {i.parent_informed_on or '—'}")
    print(f"    Follow-up        : "
          f"{'required' if i.follow_up_required else 'no'}"
          + (f"; due {i.follow_up_due}"
              if i.follow_up_required and i.follow_up_due
              else "")
          + ("  (OVERDUE)" if i.follow_up_overdue else ""))
    print(f"    Accident book ref: "
          f"{i.accident_book_ref or '—'}")
    print(f"    Status           : {i.status}")
    for label, val in (
            ("Description",      i.description),
            ("Treatment given",  i.treatment_given),
            ("Follow-up notes",  i.follow_up_notes),
            ("Notes",            i.notes),
    ):
        if val:
            print(f"\n    {label}:")
            for line in val.splitlines():
                print(f"      {line}")


# ── Flows ────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Incidents ═══")
    _print_table(data.list_incidents())
    _pause()


def list_open() -> None:
    print("\n═══ Open Incidents ═══")
    _print_table(data.list_incidents(open_only=True))
    _pause()


def list_parent_pending() -> None:
    print("\n═══ Parent Not Yet Informed ═══")
    _print_table(data.list_incidents(parent_pending=True))
    _pause()


def list_follow_up() -> None:
    print("\n═══ Follow-Up Pending ═══")
    _print_table(data.list_incidents(follow_up_pending=True))
    _pause()


def list_overdue() -> None:
    print("\n═══ Follow-Up Overdue ═══")
    _print_table(data.list_incidents(follow_up_overdue=True))
    _pause()


def list_ambulance() -> None:
    print("\n═══ Ambulance Called ═══")
    _print_table(data.list_incidents(ambulance_only=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        student = _input("Student id") or None
        nature = _input(
            f"Nature ({'/'.join(NATURES[:2])}…)") or None
        status = _input(f"Status ({'/'.join(STATUSES[:3])}…)") or None
        sev_raw = _input("Min severity (1-5)") or None
        aider = _input("First aider contains") or None
        location = _input("Location contains") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    sev = (int(sev_raw) if sev_raw and sev_raw.isdigit() else None)
    try:
        rows = data.list_incidents(
            student_id=student, nature=nature, status=status,
            severity_min=sev, first_aider_like=aider,
            location_like=location, date_from=df, date_to=dt2)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_table(rows)
    _pause()


def per_student_flow() -> None:
    print("\n═══ Per-Student ═══")
    try:
        sid = _pick_student()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_table(data.incidents_for_student(sid))
    _pause()


def view_flow() -> None:
    print("\n═══ View Incident ═══")
    try:
        i = _pick_incident()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_full(i)
    _pause()


def _collect_form(existing: Incident | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["student_id"] = existing.student_id
    else:
        payload["student_id"] = _pick_student()
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
    payload["location"] = _input(
        "Location",
        default=(existing.location or "") if is_edit else "")
    payload["nature"] = _pick_from(
        "Nature", list(NATURES),
        default=(existing.nature if is_edit else DEFAULT_NATURE))
    payload["severity"] = _input(
        "Severity (1-5)",
        default=(str(existing.severity) if is_edit else "2"))
    payload["first_aider"] = _input(
        "First aider",
        default=(existing.first_aider if is_edit else ""),
        allow_empty=False)
    try:
        payload["description"] = _multiline(
            "Description",
            default=(existing.description or "")
            if is_edit else "")
        payload["treatment_given"] = _multiline(
            "Treatment given",
            default=(existing.treatment_given or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["ambulance_called"] = _yes_no(
        "Ambulance called?",
        default=(existing.ambulance_called if is_edit else False))
    payload["hospital_referral"] = _yes_no(
        "Hospital referral?",
        default=(existing.hospital_referral if is_edit else False))
    payload["sent_home"] = _yes_no(
        "Sent home?",
        default=(existing.sent_home if is_edit else False))
    payload["parent_informed"] = _yes_no(
        "Parent informed?",
        default=(existing.parent_informed if is_edit else False))
    if payload["parent_informed"]:
        payload["parent_informed_on"] = _input(
            "Parent informed on (YYYY-MM-DD)",
            default=(existing.parent_informed_on
                      or _date.today().isoformat())
            if is_edit else _date.today().isoformat())
    payload["follow_up_required"] = _yes_no(
        "Follow-up required?",
        default=(existing.follow_up_required
                  if is_edit else False))
    if payload["follow_up_required"]:
        payload["follow_up_due"] = _input(
            "Follow-up due (YYYY-MM-DD)",
            default=(existing.follow_up_due or "")
            if is_edit else "")
        try:
            payload["follow_up_notes"] = _multiline(
                "Follow-up notes",
                default=(existing.follow_up_notes or "")
                if is_edit else "")
        except _UserAbort:
            raise
    payload["accident_book_ref"] = _input(
        "Accident book ref",
        default=(existing.accident_book_ref or "")
        if is_edit else "")
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_incident() -> None:
    print("\n═══ New First Aid Incident ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        i = data.create_incident(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created incident #{i.incident_id}")
    _pause()


def edit_incident() -> None:
    print("\n═══ Edit Incident ═══")
    try:
        i = _pick_incident()
        payload = _collect_form(i)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_incident(i.incident_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{i.incident_id}")
    _pause()


def inform_parent_flow() -> None:
    print("\n═══ Inform Parent ═══")
    try:
        i = _pick_incident()
        when = _input("Informed on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.inform_parent(i.incident_id, informed_on=when)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{i.incident_id} → parent informed")
    _pause()


def complete_follow_up_flow() -> None:
    print("\n═══ Complete Follow-Up ═══")
    try:
        i = _pick_incident()
        notes = _multiline("Closing notes (optional)",
                              default=i.follow_up_notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.mark_follow_up_complete(i.incident_id,
                                            notes=notes or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Follow-up closed on #{i.incident_id}")
    _pause()


def close_flow() -> None:
    print("\n═══ Close Incident ═══")
    try:
        i = _pick_incident()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.close_incident(i.incident_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{i.incident_id} → Closed")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        i = _pick_incident()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=i.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(i.incident_id, new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{i.incident_id} → {new_status}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete ═══")
    try:
        i = _pick_incident()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete #{i.incident_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_incident(i.incident_id):
        print(f"\n  ✓ Deleted #{i.incident_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ First Aid Summary ═══")
    s = data.summary()
    print(f"\n  Total                : {s.total}")
    print(f"  Open                 : {s.open_count}")
    print(f"  Serious / Critical   : {s.serious_or_critical}")
    print(f"  Ambulance called     : {s.ambulance_called}")
    print(f"  Sent home            : {s.sent_home}")
    print(f"  Parent pending       : {s.parent_pending}")
    print(f"  Follow-up pending    : {s.follow_up_pending}")
    print(f"  Follow-up overdue    : {s.follow_up_overdue}")
    print(f"  Distinct students    : {s.distinct_students}")
    print(f"  Average severity     : "
          f"{s.average_severity if s.average_severity is not None else '—'}")
    print("\n  By nature:")
    for k in NATURES:
        n = s.by_nature.get(k, 0)
        if n:
            print(f"    {k:<24}: {n}")
    print("\n  By severity:")
    for sev in SEVERITIES:
        n = s.by_severity.get(sev, 0)
        if n:
            print(f"    {sev}  {severity_label(sev):<12}: {n}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<18}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",          list_all),
    ("List open",         list_open),
    ("Parent pending",    list_parent_pending),
    ("Follow-up pending", list_follow_up),
    ("Follow-up overdue", list_overdue),
    ("Ambulance called",  list_ambulance),
    ("Filter",            filter_flow),
    ("Per-student",       per_student_flow),
    ("View",              view_flow),
    ("─" * 6,             lambda: None),
    ("New incident",      new_incident),
    ("Edit incident",     edit_incident),
    ("Inform parent",     inform_parent_flow),
    ("Complete follow-up", complete_follow_up_flow),
    ("Close",             close_flow),
    ("Change status",     set_status_flow),
    ("Delete",            delete_flow),
    ("─" * 6,             lambda: None),
    ("Summary",           summary_flow),
]


def run() -> None:
    while True:
        print("\n── First Aid ──")
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
            logger.exception("First Aid CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "First Aid":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("First Aid CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
