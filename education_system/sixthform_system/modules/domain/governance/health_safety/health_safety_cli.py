"""CLI flows for Sixth Form Health & Safety register."""

from __future__ import annotations

import logging
from datetime import date as _date
from datetime import datetime as _dt
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.governance.health_safety import (
    health_safety as data,
)
from education_system.sixthform_system.modules.domain.governance.health_safety.health_safety import (
    ACTION_PRIORITIES,
    ACTION_STATUSES,
    AFFECTED_PARTIES,
    CATEGORIES,
    DEFAULT_ACTION_PRIORITY,
    DEFAULT_ACTION_STATUS,
    DEFAULT_CATEGORY,
    DEFAULT_INCIDENT_TYPE,
    DEFAULT_SEVERITY,
    DEFAULT_STATUS,
    INCIDENT_TYPES,
    SEVERITIES,
    STATUSES,
    Action,
    Incident,
    ValidationError,
)
from education_system.sixthform_system.modules.domain.staff_comms.staff import (
    staff as _staff,
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
                default: str | None = None,
                allow_blank: bool = False) -> str:
    print(f"\n  {label}:")
    opts = (["(none)"] + options) if allow_blank else options
    for i, opt in enumerate(opts, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(opts)}",
                      default=default or "")
        if default and raw == default and default in opts:
            return "" if default == "(none)" else default
        if not raw.isdigit():
            print("    Enter a number.")
            continue
        n = int(raw)
        if not (1 <= n <= len(opts)):
            print("    Out of range.")
            continue
        chosen = opts[n - 1]
        return "" if (allow_blank and chosen == "(none)") else chosen


def _pick_staff(*, optional: bool = True) -> str | None:
    try:
        rows = _staff.list_staff()
    except Exception:
        rows = []
    if not rows:
        if optional:
            return None
        print("    No staff records.")
        raise _UserAbort
    print("\n  Staff:")
    for i, s in enumerate(rows, 1):
        full = getattr(s, "full_name", "") or ""
        print(f"    {i:>3}) {s.staff_id:<10}  {full}")
    suffix = " (blank to skip)" if optional else ""
    while True:
        raw = _input(f"  Pick #1..{len(rows)} or id{suffix}",
                      allow_empty=optional)
        if not raw:
            return None
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].staff_id
        match = next((s for s in rows if s.staff_id == raw), None)
        if match:
            return match.staff_id
        print("    No matching staff.")


def _pick_student(*, optional: bool = True) -> str | None:
    try:
        rows = _students.list_students()
    except Exception:
        rows = []
    if not rows:
        return None
    print("\n  Students:")
    for i, s in enumerate(rows, 1):
        full = getattr(s, "full_name", "") or ""
        print(f"    {i:>3}) {s.student_id:<12}  {full}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} or id (blank to skip)",
                      allow_empty=optional)
        if not raw:
            return None
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
        print(f"    {i:>3}) #{inc.incident_id}  "
              f"{inc.incident_date}  "
              f"{inc.location[:18]:<18}  "
              f"{inc.category[:16]:<16}  "
              f"{inc.severity[:10]:<10}  [{inc.status}]")
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


def _pick_action(incident_id: int) -> Action:
    rows = data.list_actions(incident_id=incident_id)
    if not rows:
        print("    No actions for this incident.")
        raise _UserAbort
    print("\n  Actions:")
    for i, a in enumerate(rows, 1):
        flag = "!" if a.is_overdue else " "
        print(f"    {i:>3}){flag}#{a.action_id}  "
              f"{a.action[:36]:<36}  "
              f"{(a.due_date or '—'):<10}  "
              f"[{a.priority}]  [{a.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.action_id == n), None)
            if match:
                return match
        print("    No matching action.")


def _print_table(rows: list[Incident]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Date':<10} {'Loc':<18}  {'Cat':<18}  "
          f"{'Sev':<12}  {'Type':<10}  {'Status':<16}  RIDDOR")
    print("  " + "-" * 110)
    for i in rows:
        print(f"  {i.incident_id:>4}  "
              f"{i.incident_date:<10} "
              f"{(i.location or '—')[:18]:<18}  "
              f"{i.category[:18]:<18}  "
              f"{i.severity[:12]:<12}  "
              f"{i.incident_type[:10]:<10}  "
              f"{i.status[:16]:<16}  "
              f"{'Y' if i.riddor_reportable else ' '}")
    print(f"\n  {len(rows)} incident(s).")


def _print_full(view) -> None:
    i = view.incident
    print()
    print(f"    #{i.incident_id}  [{i.status}]")
    print(f"    Date / time      : {i.incident_date}  "
          f"{i.incident_time or '—'}")
    print(f"    Location         : {i.location}")
    print(f"    Category         : {i.category}")
    print(f"    Severity         : {i.severity}")
    print(f"    Type             : {i.incident_type}")
    print(f"    Affected         : "
          f"{view.affected_display or '—'}")
    print(f"    Reported by      : "
          f"{view.reporter_name or '—'}")
    print(f"    Assessor         : "
          f"{view.assessor_name or '—'}")
    print(f"    RIDDOR           : "
          f"{'reportable' if i.riddor_reportable else 'no'}"
          + (f"; ref {i.riddor_reference}"
              if i.riddor_reference else "")
          + (f"; on {i.riddor_reported_on}"
              if i.riddor_reported_on else ""))
    print(f"    Parent informed  : "
          f"{'yes' if i.parent_informed else 'no'}")
    print(f"    HSE notified     : "
          f"{'yes' if i.hse_notified else 'no'}")
    print(f"    Review due       : {i.review_due or '—'}")
    for label, val in (
            ("Description",       i.description),
            ("Immediate action",  i.immediate_action),
            ("Root cause",        i.root_cause),
            ("Lessons learned",   i.lessons_learned),
            ("Notes",             i.notes),
    ):
        if val:
            print(f"\n    {label}:")
            for line in val.splitlines():
                print(f"      {line}")
    print(f"\n    Actions: {view.actions_count}  "
          f"(open {len(view.open_actions)}, "
          f"completed {len(view.completed_actions)})")
    for a in view.open_actions + view.completed_actions:
        flag = "!" if a.is_overdue else " "
        print(f"      {flag}#{a.action_id}  "
              f"{a.action[:50]:<50}  "
              f"due {a.due_date or '—'}  "
              f"[{a.priority}]  [{a.status}]")


# ── Flows ────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Incidents ═══")
    _print_table(data.list_incidents())
    _pause()


def list_open() -> None:
    print("\n═══ Open Incidents ═══")
    _print_table(data.list_incidents(open_only=True))
    _pause()


def list_riddor() -> None:
    print("\n═══ RIDDOR-Reportable ═══")
    _print_table(data.list_incidents(riddor_only=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        status = _input(f"Status ({'/'.join(STATUSES[:3])}…)") or None
        severity = _input(f"Severity ({'/'.join(SEVERITIES[:3])}…)") or None
        category = _input("Category contains exact name") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
        search = _input("Search description/location/notes") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_incidents(
            status=status, severity=severity, category=category,
            date_from=df, date_to=dt2, search=search)
    except ValidationError as exc:
        print(f"  ✗ {exc}")
        _pause()
        return
    _print_table(rows)
    _pause()


def view_flow() -> None:
    print("\n═══ View Incident ═══")
    try:
        i = _pick_incident()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    v = data.view_incident(i.incident_id)
    if v is None:
        print("  Not found.")
        _pause()
        return
    _print_full(v)
    _pause()


def _collect_incident_form(existing: Incident | None
                              ) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
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
        default=(existing.location if is_edit else ""),
        allow_empty=False)
    payload["category"] = _pick_from(
        "Category", list(CATEGORIES),
        default=(existing.category if is_edit
                  else DEFAULT_CATEGORY))
    payload["severity"] = _pick_from(
        "Severity", list(SEVERITIES),
        default=(existing.severity if is_edit
                  else DEFAULT_SEVERITY))
    payload["incident_type"] = _pick_from(
        "Incident type", list(INCIDENT_TYPES),
        default=(existing.incident_type if is_edit
                  else DEFAULT_INCIDENT_TYPE))
    payload["affected_party"] = _pick_from(
        "Affected party", list(AFFECTED_PARTIES),
        default=(existing.affected_party
                  if is_edit and existing.affected_party
                  else "None"),
        allow_blank=True) or None
    if payload["affected_party"] == "Student":
        payload["affected_student_id"] = _pick_student()
        payload["affected_staff_id"] = None
        payload["affected_name"] = None
    elif payload["affected_party"] == "Staff":
        payload["affected_staff_id"] = _pick_staff()
        payload["affected_student_id"] = None
        payload["affected_name"] = None
    elif payload["affected_party"] in (
            "Visitor", "Contractor", "Public", "Other"):
        payload["affected_name"] = _input(
            "Affected person / party name",
            default=(existing.affected_name
                      if is_edit and existing.affected_name else ""))
        payload["affected_student_id"] = None
        payload["affected_staff_id"] = None
    else:
        payload["affected_student_id"] = None
        payload["affected_staff_id"] = None
        payload["affected_name"] = None
    try:
        payload["description"] = _multiline(
            "Description",
            default=(existing.description if is_edit else ""))
        if not payload["description"]:
            raise ValidationError("Description is required")
        payload["immediate_action"] = _multiline(
            "Immediate action",
            default=(existing.immediate_action or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["riddor_reportable"] = _yes_no(
        "RIDDOR reportable?",
        default=(existing.riddor_reportable if is_edit else False))
    if payload["riddor_reportable"]:
        payload["riddor_reference"] = _input(
            "RIDDOR reference",
            default=(existing.riddor_reference or "")
            if is_edit else "")
        payload["riddor_reported_on"] = _input(
            "RIDDOR reported on (YYYY-MM-DD)",
            default=(existing.riddor_reported_on
                      or _date.today().isoformat())
            if is_edit else _date.today().isoformat(),
            allow_empty=False)
    print("\n  Reported by:")
    payload["reported_by"] = _pick_staff()
    print("\n  Assessor:")
    payload["assessor_id"] = _pick_staff()
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["parent_informed"] = _yes_no(
        "Parent informed?",
        default=(existing.parent_informed if is_edit else False))
    payload["hse_notified"] = _yes_no(
        "HSE notified?",
        default=(existing.hse_notified if is_edit else False))
    payload["root_cause"] = _input(
        "Root cause",
        default=(existing.root_cause or "") if is_edit else "")
    payload["lessons_learned"] = _input(
        "Lessons learned",
        default=(existing.lessons_learned or "") if is_edit else "")
    payload["review_due"] = _input(
        "Review due (YYYY-MM-DD)",
        default=(existing.review_due or "") if is_edit else "")
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_incident() -> None:
    print("\n═══ New H&S Incident ═══")
    try:
        payload = _collect_incident_form(None)
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
        payload = _collect_incident_form(i)
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


# ── Actions sub-menu ────────────────────────────────────────────

def _collect_action_form(existing: Action | None
                            ) -> dict[str, Any]:
    is_edit = existing is not None
    payload: dict[str, Any] = {}
    payload["action"] = _input(
        "Action description",
        default=(existing.action if is_edit else ""),
        allow_empty=False)
    print("\n  Owner:")
    payload["owner_id"] = _pick_staff()
    payload["due_date"] = _input(
        "Due date (YYYY-MM-DD)",
        default=(existing.due_date or "") if is_edit else "")
    payload["priority"] = _pick_from(
        "Priority", list(ACTION_PRIORITIES),
        default=(existing.priority if is_edit
                  else DEFAULT_ACTION_PRIORITY))
    payload["status"] = _pick_from(
        "Status", list(ACTION_STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_ACTION_STATUS))
    if payload["status"] == "Completed":
        payload["completed_on"] = _input(
            "Completed on (YYYY-MM-DD)",
            default=(existing.completed_on
                      or _date.today().isoformat())
            if is_edit else _date.today().isoformat())
    else:
        payload["completed_on"] = (existing.completed_on
                                          if is_edit else None)
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def actions_flow() -> None:
    print("\n═══ Manage Actions ═══")
    try:
        inc = _pick_incident()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    while True:
        acts = data.list_actions(incident_id=inc.incident_id)
        print(f"\n  Actions for incident #{inc.incident_id} "
              f"({inc.category} @ {inc.location})")
        if not acts:
            print("    (none)")
        for a in acts:
            flag = "!" if a.is_overdue else " "
            print(f"   {flag}#{a.action_id}  "
                  f"{a.action[:40]:<40}  "
                  f"due {a.due_date or '—'}  "
                  f"[{a.priority}]  [{a.status}]")
        print("\n    a) Add  c) Complete  e) Edit  "
              "d) Delete  0) Back")
        try:
            choice = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return
        if choice in ("0", "", "b", "back"):
            return
        try:
            if choice == "a":
                payload = _collect_action_form(None)
                a = data.add_action(inc.incident_id, payload)
                print(f"  ✓ Action #{a.action_id} added")
            elif choice == "c":
                a = _pick_action(inc.incident_id)
                when = _input("Completed on (YYYY-MM-DD)",
                                default=_date.today().isoformat())
                data.complete_action(a.action_id,
                                          completed_on=when)
                print(f"  ✓ Action #{a.action_id} completed")
            elif choice == "e":
                a = _pick_action(inc.incident_id)
                payload = _collect_action_form(a)
                data.update_action(a.action_id, payload)
                print(f"  ✓ Action #{a.action_id} updated")
            elif choice == "d":
                a = _pick_action(inc.incident_id)
                if _input(f"Delete action #{a.action_id}? "
                            "Type 'yes'",
                            default="no").lower() == "yes":
                    data.delete_action(a.action_id)
                    print(f"  ✓ Deleted #{a.action_id}")
            else:
                print("  Invalid selection.")
        except _UserAbort:
            print("  Cancelled.")
        except ValidationError as exc:
            print(f"  ✗ {exc}")


def summary_flow() -> None:
    print("\n═══ Health & Safety Summary ═══")
    s = data.summary()
    print(f"\n  Total incidents      : {s.total}")
    print(f"  Open incidents       : {s.open_incidents}")
    print(f"  RIDDOR-reportable    : {s.riddor_reportable}")
    print(f"  Open actions         : {s.open_actions}")
    print(f"  Overdue actions      : {s.overdue_actions}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<18}: {n}")
    print("\n  By severity:")
    for k in SEVERITIES:
        n = s.by_severity.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    print("\n  By category:")
    for k in CATEGORIES:
        n = s.by_category.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By type:")
    for k in INCIDENT_TYPES:
        n = s.by_type.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",          list_all),
    ("List open",         list_open),
    ("RIDDOR-reportable", list_riddor),
    ("Filter",            filter_flow),
    ("View incident",     view_flow),
    ("─" * 6,             lambda: None),
    ("New incident",      new_incident),
    ("Edit incident",     edit_incident),
    ("Change status",     set_status_flow),
    ("Delete incident",   delete_flow),
    ("─" * 6,             lambda: None),
    ("Manage actions",    actions_flow),
    ("─" * 6,             lambda: None),
    ("Summary",           summary_flow),
]


def run() -> None:
    while True:
        print("\n── Health & Safety ──")
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
        if (not choice.isdigit()
                or not (1 <= int(choice) <= len(_MENU))):
            print("  Invalid selection.")
            continue
        label, handler = _MENU[int(choice) - 1]
        if label.startswith("─"):
            continue
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except ValidationError as exc:
            print(f"\n  ✗ {exc}")
            _pause()
        except Exception as exc:
            logger.exception("H&S CLI crashed")
            print(f"\n  ✗ Unexpected error: {exc}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Health & Safety":
        return False
    try:
        run()
    except Exception as exc:
        logger.exception("H&S CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {exc}")
        _pause()
    return True
