"""CLI flows for Sixth Form Equality & Diversity."""

from __future__ import annotations

import logging
from datetime import date as _date
from datetime import datetime as _dt
from typing import Any, Callable
from education_system.secondarysch_system.modules.domain.pastoral.equality_diversity import (
    equality_diversity as data,
)
from education_system.secondarysch_system.modules.domain.pastoral.equality_diversity.equality_diversity import (
    DEFAULT_CHARACTERISTIC,
    DEFAULT_INCIDENT_TYPE,
    DEFAULT_STATUS,
    DEFAULT_SUBJECT_ROLE,
    EDIncident,
    INCIDENT_TYPES,
    PROTECTED_CHARACTERISTICS,
    SEVERITIES,
    STATUSES,
    SUBJECT_ROLES,
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


def _pick_incident() -> EDIncident:
    rows = data.list_incidents()
    if not rows:
        print("    No incidents yet.")
        raise _UserAbort
    print("\n  Incidents:")
    for i, inc in enumerate(rows, 1):
        print(f"    {i:>3}) #{inc.incident_id}  "
              f"{inc.incident_date}  "
              f"{inc.incident_type[:18]:<18}  "
              f"{inc.protected_characteristic[:18]:<18}  "
              f"sev={inc.severity}  [{inc.status}]")
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


def _print_table(rows: list[EDIncident]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Date':<10}  {'Type':<22}  "
          f"{'Characteristic':<22}  Sev  "
          f"{'Reporter':<14}  {'Status':<18}  Flags")
    print("  " + "-" * 130)
    for i in rows:
        flags = []
        if i.anonymous:
            flags.append("ANON")
        if i.escalated_to_head:
            flags.append("HEAD")
        if i.escalated_to_dsl:
            flags.append("DSL")
        if i.governors_informed:
            flags.append("GOV")
        print(f"  {i.incident_id:>4}  "
              f"{i.incident_date:<10}  "
              f"{i.incident_type[:22]:<22}  "
              f"{i.protected_characteristic[:22]:<22}  "
              f"{i.severity:>3}  "
              f"{i.reporter[:14]:<14}  "
              f"{i.status:<18}  {','.join(flags)}")
    print(f"\n  {len(rows)} incident(s).")


def _print_full(i: EDIncident) -> None:
    print()
    print(f"    #{i.incident_id}")
    print(f"    Date / time      : {i.incident_date}  "
          f"{i.incident_time or '—'}")
    print(f"    Reported on      : {i.reported_on}")
    print(f"    Reporter         : {i.reporter}  "
          f"({i.reporter_role})"
          + ("  ANONYMOUS" if i.anonymous else ""))
    print(f"    Subject          : "
          f"{i.subject_name or '—'}  ({i.subject_role})")
    print(f"    Alleged perp.    : "
          f"{i.alleged_perpetrator or '—'}  "
          f"({i.perpetrator_role})")
    print(f"    Type             : {i.incident_type}")
    print(f"    Characteristic   : {i.protected_characteristic}")
    print(f"    Severity         : {i.severity}  "
          f"({i.severity_label})")
    print(f"    Location         : {i.location or '—'}")
    print(f"    Status           : {i.status}")
    if i.closed_on:
        print(f"    Closed on        : {i.closed_on}")
    print(f"    Investigated by  : {i.investigated_by or '—'}")
    print(f"    Outcome          : {i.outcome or '—'}")
    print(f"    Complainant inf. : "
          f"{'yes' if i.complainant_informed else 'no'}")
    print(f"    Perpetrator inf. : "
          f"{'yes' if i.perpetrator_informed else 'no'}")
    print(f"    Training reqd    : "
          f"{'yes' if i.training_required else 'no'}")
    esc = []
    if i.escalated_to_head:
        esc.append("Head")
    if i.escalated_to_dsl:
        esc.append("DSL")
    if i.governors_informed:
        esc.append("Governors")
    print(f"    Escalation       : "
          f"{', '.join(esc) if esc else 'none'}")
    for label, val in (
            ("Description",          i.description),
            ("Witnesses",            i.witnesses),
            ("Investigation notes",  i.investigation_notes),
            ("Actions taken",        i.actions_taken),
            ("Notes",                i.notes),
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
    print("\n═══ Open ═══")
    _print_table(data.list_incidents(open_only=True))
    _pause()


def list_substantiated() -> None:
    print("\n═══ Substantiated ═══")
    _print_table(data.list_incidents(substantiated_only=True))
    _pause()


def list_escalated() -> None:
    print("\n═══ Escalated (Head / DSL / Governors) ═══")
    _print_table(data.list_incidents(escalated_only=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        itype = _input(
            f"Type ({'/'.join(INCIDENT_TYPES[:2])}…)") or None
        char = _input(
            f"Characteristic ({'/'.join(PROTECTED_CHARACTERISTICS[:2])}…)") or None
        status = _input(f"Status ({'/'.join(STATUSES[:3])}…)") or None
        sev_raw = _input("Min severity (1-5)") or None
        reporter = _input("Reporter contains") or None
        subject = _input("Subject/perp contains") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    sev = int(sev_raw) if sev_raw and sev_raw.isdigit() else None
    try:
        rows = data.list_incidents(
            incident_type=itype, characteristic=char,
            status=status, severity_min=sev,
            reporter_like=reporter, subject_like=subject,
            date_from=df, date_to=dt2)
    except ValidationError as e:
        print(f"  ✗ {e}")
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
    _print_full(i)
    _pause()


def _collect_form(existing: EDIncident | None) -> dict[str, Any]:
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
    payload["reported_on"] = _input(
        "Reported on (YYYY-MM-DD)",
        default=(existing.reported_on if is_edit
                  else _date.today().isoformat()))
    payload["reporter"] = _input(
        "Reporter",
        default=(existing.reporter if is_edit else ""),
        allow_empty=False)
    payload["reporter_role"] = _pick_from(
        "Reporter role", list(SUBJECT_ROLES),
        default=(existing.reporter_role if is_edit
                  else "Staff"))
    payload["anonymous"] = _yes_no(
        "Anonymous?",
        default=(existing.anonymous if is_edit else False))
    payload["subject_name"] = _input(
        "Subject name (person reported about)",
        default=(existing.subject_name or "")
        if is_edit else "")
    payload["subject_role"] = _pick_from(
        "Subject role", list(SUBJECT_ROLES),
        default=(existing.subject_role if is_edit
                  else DEFAULT_SUBJECT_ROLE))
    payload["alleged_perpetrator"] = _input(
        "Alleged perpetrator",
        default=(existing.alleged_perpetrator or "")
        if is_edit else "")
    payload["perpetrator_role"] = _pick_from(
        "Perpetrator role", list(SUBJECT_ROLES),
        default=(existing.perpetrator_role if is_edit
                  else DEFAULT_SUBJECT_ROLE))
    payload["incident_type"] = _pick_from(
        "Incident type", list(INCIDENT_TYPES),
        default=(existing.incident_type if is_edit
                  else DEFAULT_INCIDENT_TYPE))
    payload["protected_characteristic"] = _pick_from(
        "Protected characteristic",
        list(PROTECTED_CHARACTERISTICS),
        default=(existing.protected_characteristic if is_edit
                  else DEFAULT_CHARACTERISTIC))
    payload["severity"] = _input(
        "Severity (1-5)",
        default=(str(existing.severity) if is_edit else "2"))
    payload["location"] = _input(
        "Location",
        default=(existing.location or "") if is_edit else "")
    try:
        payload["description"] = _multiline(
            "Description",
            default=(existing.description or "")
            if is_edit else "")
        payload["witnesses"] = _multiline(
            "Witnesses",
            default=(existing.witnesses or "")
            if is_edit else "")
        payload["investigation_notes"] = _multiline(
            "Investigation notes",
            default=(existing.investigation_notes or "")
            if is_edit else "")
        payload["actions_taken"] = _multiline(
            "Actions taken",
            default=(existing.actions_taken or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["investigated_by"] = _input(
        "Investigated by",
        default=(existing.investigated_by or "")
        if is_edit else "")
    payload["outcome"] = _input(
        "Outcome",
        default=(existing.outcome or "") if is_edit else "")
    payload["training_required"] = _yes_no(
        "Training required?",
        default=(existing.training_required
                  if is_edit else False))
    payload["complainant_informed"] = _yes_no(
        "Complainant informed?",
        default=(existing.complainant_informed
                  if is_edit else False))
    payload["perpetrator_informed"] = _yes_no(
        "Perpetrator informed?",
        default=(existing.perpetrator_informed
                  if is_edit else False))
    payload["escalated_to_head"] = _yes_no(
        "Escalated to Head?",
        default=(existing.escalated_to_head
                  if is_edit else False))
    payload["escalated_to_dsl"] = _yes_no(
        "Escalated to DSL?",
        default=(existing.escalated_to_dsl if is_edit else False))
    payload["governors_informed"] = _yes_no(
        "Governors informed?",
        default=(existing.governors_informed
                  if is_edit else False))
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["closed_on"] = _input(
        "Closed on (YYYY-MM-DD)",
        default=(existing.closed_on or "") if is_edit else "")
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_incident() -> None:
    print("\n═══ New E&D Incident ═══")
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
    print(f"\n  ✓ Created #{i.incident_id}")
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


def start_investigation_flow() -> None:
    print("\n═══ Start Investigation ═══")
    try:
        i = _pick_incident()
        by = _input("Investigator",
                       default=i.investigated_by or "",
                       allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.start_investigation(i.incident_id,
                                       investigated_by=by)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{i.incident_id} → Under Investigation")
    _pause()


def record_outcome_flow() -> None:
    print("\n═══ Record Outcome ═══")
    try:
        i = _pick_incident()
        substantiated = _yes_no("Substantiated?", default=True)
        outcome = _multiline("Outcome",
                                default=i.outcome or "")
        notes = _multiline("Investigation notes",
                              default=i.investigation_notes or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not outcome:
        print("  ✗ Outcome required.")
        _pause()
        return
    try:
        data.record_outcome(i.incident_id,
                                  substantiated=substantiated,
                                  outcome=outcome,
                                  investigation_notes=notes or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Outcome recorded on #{i.incident_id}")
    _pause()


def set_actions_flow() -> None:
    print("\n═══ Set Actions ═══")
    try:
        i = _pick_incident()
        actions = _multiline("Actions taken",
                                default=i.actions_taken or "")
        training = _yes_no("Training required?",
                              default=i.training_required)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if not actions:
        print("  ✗ Actions required.")
        _pause()
        return
    try:
        data.set_actions(i.incident_id, actions_taken=actions,
                            training_required=training)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Actions set on #{i.incident_id}")
    _pause()


def resolve_flow() -> None:
    print("\n═══ Resolve ═══")
    try:
        i = _pick_incident()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.resolve(i.incident_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{i.incident_id} → Resolved")
    _pause()


def close_flow() -> None:
    print("\n═══ Close ═══")
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
    print("\n═══ E&D Summary ═══")
    s = data.summary()
    print(f"\n  Total                : {s.total}")
    print(f"  Open                 : {s.open_count}")
    print(f"  Serious / Critical   : {s.serious_or_critical}")
    print(f"  Substantiated        : {s.substantiated}")
    print(f"  Awaiting action      : {s.awaiting_action}")
    print(f"  Governors informed   : {s.governors_informed}")
    print("\n  By type:")
    for k in INCIDENT_TYPES:
        n = s.by_type.get(k, 0)
        if n:
            print(f"    {k:<24}: {n}")
    print("\n  By protected characteristic:")
    for k in PROTECTED_CHARACTERISTICS:
        n = s.by_characteristic.get(k, 0)
        if n:
            print(f"    {k:<30}: {n}")
    print("\n  By severity:")
    for sev in SEVERITIES:
        n = s.by_severity.get(sev, 0)
        if n:
            print(f"    {sev}  {severity_label(sev):<12}: {n}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",            list_all),
    ("List open",           list_open),
    ("Substantiated",       list_substantiated),
    ("Escalated",           list_escalated),
    ("Filter",              filter_flow),
    ("View",                view_flow),
    ("─" * 6,               lambda: None),
    ("New incident",        new_incident),
    ("Edit incident",       edit_incident),
    ("Start investigation", start_investigation_flow),
    ("Record outcome",      record_outcome_flow),
    ("Set actions",         set_actions_flow),
    ("Resolve",             resolve_flow),
    ("Close",               close_flow),
    ("Change status",       set_status_flow),
    ("Delete",              delete_flow),
    ("─" * 6,               lambda: None),
    ("Summary",             summary_flow),
]


def run() -> None:
    while True:
        print("\n── Equality & Diversity ──")
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
            logger.exception("E&D CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Equality & Diversity":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("E&D CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
