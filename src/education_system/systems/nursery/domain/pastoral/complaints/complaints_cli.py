"""CLI flows for Sixth Form Complaints."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.nursery.domain.pastoral.complaints import (
    complaints as data,
)
from education_system.systems.nursery.domain.pastoral.complaints.complaints import (
    CATEGORIES,
    COMPLAINANT_ROLES,
    Complaint,
    DEFAULT_CATEGORY,
    DEFAULT_COMPLAINANT_ROLE,
    DEFAULT_SATISFACTION,
    DEFAULT_STAGE,
    DEFAULT_STATUS,
    OUTCOMES,
    SATISFACTIONS,
    SEVERITIES,
    STAGES,
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


def _pick_complaint() -> Complaint:
    rows = data.list_complaints()
    if not rows:
        print("    No complaints yet.")
        raise _UserAbort
    print("\n  Complaints:")
    for i, c in enumerate(rows, 1):
        flag = "!" if c.response_overdue else " "
        print(f"    {i:>3}){flag}#{c.complaint_id}  "
              f"{c.received_on}  {c.complainant_name[:18]:<18}  "
              f"{c.stage[:14]:<14}  sev={c.severity}  "
              f"[{c.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.complaint_id == n), None)
            if match:
                return match
        print("    No matching complaint.")


def _print_table(rows: list[Complaint]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Received':<10}  {'Complainant':<20}  "
          f"{'Category':<22}  {'Stage':<16}  Sev  "
          f"{'Status':<18}  Outcome")
    print("  " + "-" * 130)
    for c in rows:
        out = c.outcome or "—"
        if c.response_overdue:
            out = f"OVERDUE {out}"
        print(f"  {c.complaint_id:>4}  "
              f"{c.received_on:<10}  "
              f"{c.complainant_name[:20]:<20}  "
              f"{c.category[:22]:<22}  "
              f"{c.stage[:16]:<16}  "
              f"{c.severity:>3}  "
              f"{c.status:<18}  {out}")
    print(f"\n  {len(rows)} complaint(s).")


def _print_full(c: Complaint) -> None:
    print()
    print(f"    #{c.complaint_id}  {c.subject}")
    print(f"    Received on        : {c.received_on}")
    print(f"    Complainant        : {c.complainant_name}  "
          f"({c.complainant_role})")
    print(f"    Contact            : "
          f"{c.contact_email or '—'}  "
          f"{c.contact_phone or '—'}")
    print(f"    Category           : {c.category}")
    print(f"    Stage              : {c.stage}")
    print(f"    Severity           : {c.severity}  "
          f"({c.severity_label})")
    print(f"    Assigned to        : {c.assigned_to or '—'}")
    print(f"    Acknowledged on    : {c.acknowledged_on or '—'}")
    print(f"    Target response    : "
          f"{c.target_response_date or '—'}"
          + ("  (OVERDUE)" if c.response_overdue else ""))
    print(f"    Response issued    : {c.response_issued_on or '—'}")
    print(f"    Outcome            : {c.outcome or '—'}")
    print(f"    Complainant informed: "
          f"{'yes' if c.complainant_informed else 'no'}")
    print(f"    Satisfaction       : {c.complainant_satisfaction}")
    print(f"    Stage 2 escalated  : "
          f"{'yes' if c.escalated_to_stage_2 else 'no'}")
    print(f"    Appeal escalated   : "
          f"{'yes' if c.escalated_to_appeal else 'no'}")
    print(f"    Governors informed : "
          f"{'yes' if c.governors_informed else 'no'}")
    print(f"    Linked to          : {c.linked_to or '—'}")
    print(f"    Status             : {c.status}")
    print(f"    Closed on          : {c.closed_on or '—'}"
          + (f"  ({c.days_open} days)"
              if c.days_open is not None else ""))
    for label, val in (
            ("Description",     c.description),
            ("Response summary", c.response_summary),
            ("Actions taken",   c.actions_taken),
            ("Notes",           c.notes),
    ):
        if val:
            print(f"\n    {label}:")
            for line in val.splitlines():
                print(f"      {line}")


# ── Flows ────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Complaints ═══")
    _print_table(data.list_complaints())
    _pause()


def list_open() -> None:
    print("\n═══ Open ═══")
    _print_table(data.list_complaints(open_only=True))
    _pause()


def list_overdue() -> None:
    print("\n═══ Overdue Responses ═══")
    _print_table(data.list_complaints(overdue_only=True))
    _pause()


def list_stage_2() -> None:
    print("\n═══ Stage 2 / Appeal ═══")
    _print_table(data.list_complaints(stage2_or_higher=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        cat = _input(
            f"Category ({'/'.join(CATEGORIES[:2])}…)") or None
        stage = _input(f"Stage ({'/'.join(STAGES)})") or None
        status = _input(f"Status ({'/'.join(STATUSES[:3])}…)") or None
        outcome = _input(f"Outcome ({'/'.join(OUTCOMES)})") or None
        role = _input(
            f"Complainant role ({'/'.join(COMPLAINANT_ROLES[:2])}…)") or None
        sev_raw = _input("Min severity (1-5)") or None
        assigned = _input("Assigned-to contains") or None
        complainant = _input("Complainant contains") or None
        subject = _input("Subject contains") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    sev = int(sev_raw) if sev_raw and sev_raw.isdigit() else None
    try:
        rows = data.list_complaints(
            category=cat, stage=stage, status=status,
            outcome=outcome, complainant_role=role,
            severity_min=sev, assigned_to_like=assigned,
            complainant_like=complainant, subject_like=subject,
            date_from=df, date_to=dt2)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_table(rows)
    _pause()


def view_flow() -> None:
    print("\n═══ View Complaint ═══")
    try:
        c = _pick_complaint()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_full(c)
    _pause()


def _collect_form(existing: Complaint | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["subject"] = _input(
        "Subject (short title)",
        default=(existing.subject if is_edit else ""),
        allow_empty=False)
    payload["received_on"] = _input(
        "Received on (YYYY-MM-DD)",
        default=(existing.received_on if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    payload["complainant_name"] = _input(
        "Complainant name",
        default=(existing.complainant_name if is_edit else ""),
        allow_empty=False)
    payload["complainant_role"] = _pick_from(
        "Complainant role", list(COMPLAINANT_ROLES),
        default=(existing.complainant_role if is_edit
                  else DEFAULT_COMPLAINANT_ROLE))
    payload["contact_email"] = _input(
        "Email",
        default=(existing.contact_email or "")
        if is_edit else "")
    payload["contact_phone"] = _input(
        "Phone",
        default=(existing.contact_phone or "")
        if is_edit else "")
    payload["category"] = _pick_from(
        "Category", list(CATEGORIES),
        default=(existing.category if is_edit
                  else DEFAULT_CATEGORY))
    payload["stage"] = _pick_from(
        "Stage", list(STAGES),
        default=(existing.stage if is_edit else DEFAULT_STAGE))
    payload["severity"] = _input(
        "Severity (1-5)",
        default=(str(existing.severity) if is_edit else "2"))
    payload["assigned_to"] = _input(
        "Assigned to",
        default=(existing.assigned_to or "")
        if is_edit else "")
    payload["acknowledged_on"] = _input(
        "Acknowledged on (YYYY-MM-DD)",
        default=(existing.acknowledged_on or "")
        if is_edit else "")
    payload["target_response_date"] = _input(
        "Target response date (YYYY-MM-DD)",
        default=(existing.target_response_date or "")
        if is_edit else "")
    payload["response_issued_on"] = _input(
        "Response issued on (YYYY-MM-DD)",
        default=(existing.response_issued_on or "")
        if is_edit else "")
    try:
        payload["description"] = _multiline(
            "Description",
            default=(existing.description or "")
            if is_edit else "")
        payload["response_summary"] = _multiline(
            "Response summary",
            default=(existing.response_summary or "")
            if is_edit else "")
        payload["actions_taken"] = _multiline(
            "Actions taken",
            default=(existing.actions_taken or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["outcome"] = _input(
        f"Outcome ({'/'.join(OUTCOMES)} or blank)",
        default=(existing.outcome or "") if is_edit else "")
    payload["complainant_informed"] = _yes_no(
        "Complainant informed?",
        default=(existing.complainant_informed
                  if is_edit else False))
    payload["complainant_satisfaction"] = _pick_from(
        "Satisfaction", list(SATISFACTIONS),
        default=(existing.complainant_satisfaction if is_edit
                  else DEFAULT_SATISFACTION))
    payload["escalated_to_stage_2"] = _yes_no(
        "Escalated to Stage 2?",
        default=(existing.escalated_to_stage_2
                  if is_edit else False))
    payload["escalated_to_appeal"] = _yes_no(
        "Escalated to Appeal?",
        default=(existing.escalated_to_appeal
                  if is_edit else False))
    payload["governors_informed"] = _yes_no(
        "Governors informed?",
        default=(existing.governors_informed
                  if is_edit else False))
    payload["linked_to"] = _input(
        "Linked to (e.g. disciplinary case #)",
        default=(existing.linked_to or "")
        if is_edit else "")
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


def new_complaint() -> None:
    print("\n═══ New Complaint ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        c = data.create_complaint(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created complaint #{c.complaint_id}")
    _pause()


def edit_complaint() -> None:
    print("\n═══ Edit Complaint ═══")
    try:
        c = _pick_complaint()
        payload = _collect_form(c)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_complaint(c.complaint_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{c.complaint_id}")
    _pause()


def acknowledge_flow() -> None:
    print("\n═══ Acknowledge ═══")
    try:
        c = _pick_complaint()
        assigned = _input("Assign to",
                            default=c.assigned_to or "")
        when = _input("Acknowledged on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
        target = _input("Target response date (YYYY-MM-DD)",
                          default=c.target_response_date or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.acknowledge(c.complaint_id,
                              assigned_to=assigned or None,
                              acknowledged_on=when,
                              target_response_date=target or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{c.complaint_id} → Acknowledged")
    _pause()


def start_investigation_flow() -> None:
    print("\n═══ Start Investigation ═══")
    try:
        c = _pick_complaint()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.start_investigation(c.complaint_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{c.complaint_id} → Under Investigation")
    _pause()


def issue_response_flow() -> None:
    print("\n═══ Issue Response ═══")
    try:
        c = _pick_complaint()
        summary = _multiline("Response summary",
                                default=c.response_summary or "")
        if not summary:
            print("  ✗ Summary required.")
            _pause()
            return
        outcome = _pick_from("Outcome", list(OUTCOMES))
        actions = _multiline("Actions taken",
                                default=c.actions_taken or "")
        issued = _input("Issued on (YYYY-MM-DD)",
                           default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.issue_response(c.complaint_id, summary=summary,
                                  outcome=outcome,
                                  issued_on=issued,
                                  actions_taken=actions or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Response issued on #{c.complaint_id}")
    _pause()


def escalate_flow() -> None:
    print("\n═══ Escalate ═══")
    try:
        c = _pick_complaint()
        idx = STAGES.index(c.stage)
        if idx >= len(STAGES) - 1:
            print(f"  Already at final stage: {c.stage}")
            _pause()
            return
        to_stage = _pick_from("Escalate to",
                                  list(STAGES[idx + 1:]),
                                  default=STAGES[idx + 1])
        reason = _multiline("Reason")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.escalate(c.complaint_id, to_stage=to_stage,
                          reason=reason or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{c.complaint_id} → {to_stage}")
    _pause()


def record_satisfaction_flow() -> None:
    print("\n═══ Record Satisfaction ═══")
    try:
        c = _pick_complaint()
        sat = _pick_from("Satisfaction", list(SATISFACTIONS),
                            default=c.complainant_satisfaction)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.record_satisfaction(c.complaint_id,
                                       satisfaction=sat)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Satisfaction recorded on #{c.complaint_id}")
    _pause()


def close_flow() -> None:
    print("\n═══ Close ═══")
    try:
        c = _pick_complaint()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.close_complaint(c.complaint_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{c.complaint_id} → Closed")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        c = _pick_complaint()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=c.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(c.complaint_id, new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{c.complaint_id} → {new_status}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete ═══")
    try:
        c = _pick_complaint()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete #{c.complaint_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_complaint(c.complaint_id):
        print(f"\n  ✓ Deleted #{c.complaint_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Complaints Summary ═══")
    s = data.summary()
    print(f"\n  Total                 : {s.total}")
    print(f"  Open                  : {s.open_count}")
    print(f"  Overdue               : {s.overdue}")
    print(f"  Serious / Major       : {s.serious_or_major}")
    print(f"  Stage 2 / Appeal      : {s.at_stage_2_or_appeal}")
    print(f"  Governors informed    : {s.governors_informed}")
    print(f"  Closed                : {s.closed_count}")
    print(f"  Upheld                : {s.upheld_count}")
    print(f"  Not upheld            : {s.not_upheld_count}")
    print(f"  Avg days to close     : "
          f"{s.average_days_to_close if s.average_days_to_close is not None else '—'}")
    print("\n  By category:")
    for k in CATEGORIES:
        n = s.by_category.get(k, 0)
        if n:
            print(f"    {k:<24}: {n}")
    print("\n  By stage:")
    for k in STAGES:
        n = s.by_stage.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By outcome:")
    for k in OUTCOMES:
        n = s.by_outcome.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",            list_all),
    ("List open",           list_open),
    ("Overdue responses",   list_overdue),
    ("Stage 2 / Appeal",    list_stage_2),
    ("Filter",              filter_flow),
    ("View",                view_flow),
    ("─" * 6,               lambda: None),
    ("New complaint",       new_complaint),
    ("Edit complaint",      edit_complaint),
    ("Acknowledge",         acknowledge_flow),
    ("Start investigation", start_investigation_flow),
    ("Issue response",      issue_response_flow),
    ("Escalate",            escalate_flow),
    ("Record satisfaction", record_satisfaction_flow),
    ("Close",               close_flow),
    ("Change status",       set_status_flow),
    ("Delete",              delete_flow),
    ("─" * 6,               lambda: None),
    ("Summary",             summary_flow),
]


def run() -> None:
    while True:
        print("\n── Complaints ──")
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
            logger.exception("Complaints CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Complaints":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Complaints CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
