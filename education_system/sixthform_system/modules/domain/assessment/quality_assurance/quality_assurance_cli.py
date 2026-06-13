"""CLI flows for Sixth Form Quality Assurance."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.assessment.quality_assurance import (
    quality_assurance as data,
)
from education_system.sixthform_system.modules.domain.assessment.quality_assurance.quality_assurance import (
    ACTIVITY_TYPES,
    DEFAULT_ACTIVITY_TYPE,
    DEFAULT_FOCUS_AREA,
    DEFAULT_STATUS,
    FOCUS_AREAS,
    JUDGEMENTS,
    QAActivity,
    STATUSES,
    ValidationError,
    judgement_label,
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
            print("    Enter a number (or 'cancel').")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_activity() -> QAActivity:
    rows = data.list_activities()
    if not rows:
        print("    No QA activities yet.")
        raise _UserAbort
    print("\n  QA Activities:")
    for i, a in enumerate(rows, 1):
        flag = "!" if a.action_overdue else " "
        print(f"    {i:>3}){flag}#{a.activity_id}  "
              f"{a.activity_date}  {a.activity_type[:14]:<14}  "
              f"{a.title[:30]:<30}  J={a.judgement or '—'}  "
              f"[{a.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((a for a in rows
                            if a.activity_id == n), None)
            if match:
                return match
        print("    No matching activity.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_table(rows: list[QAActivity]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Date':<10}  {'Type':<14}  "
          f"{'Title':<30}  {'Lead':<14}  J  "
          f"{'Status':<18}  Action")
    print("  " + "-" * 130)
    for a in rows:
        action = "—"
        if a.action_summary:
            action = "✓" if a.action_completed else (
                "OVERDUE" if a.action_overdue else "open")
            if a.action_due and not a.action_completed:
                action = f"{action} ({a.action_due})"
        print(f"  {a.activity_id:>4}  "
              f"{a.activity_date:<10}  "
              f"{a.activity_type[:14]:<14}  "
              f"{a.title[:30]:<30}  "
              f"{a.lead[:14]:<14}  "
              f"{a.judgement or '—'}  "
              f"{a.status:<18}  {action}")
    print(f"\n  {len(rows)} activity(ies).")


def _print_full(a: QAActivity) -> None:
    print()
    print(f"    #{a.activity_id}  {a.title}")
    print(f"    Date / type      : {a.activity_date}  "
          f"{a.activity_type}")
    print(f"    Lead             : {a.lead}")
    print(f"    Participants     : {a.participants or '—'}")
    print(f"    Focus area       : {a.focus_area or '—'}")
    print(f"    Subject / dept   : "
          f"{a.subject or '—'} / {a.department or '—'}")
    print(f"    Judgement        : {a.judgement or '—'}  "
          f"({a.judgement_label})")
    print(f"    Status           : {a.status}")
    for label, val in (
            ("Strengths",        a.strengths),
            ("Areas to develop", a.areas_to_develop),
            ("Evidence",         a.evidence),
    ):
        if val:
            print(f"\n    {label}:")
            for line in val.splitlines():
                print(f"      {line}")
    if a.action_summary:
        print(f"\n    Action: {a.action_summary}")
        print(f"      Owner : {a.action_owner or '—'}")
        print(f"      Due   : {a.action_due or '—'}"
              + ("  (OVERDUE)" if a.action_overdue else ""))
        print(f"      Done  : {'yes' if a.action_completed else 'no'}")
    if a.impact_review:
        print(f"\n    Impact review ({a.impact_reviewed_on or '—'}):")
        for line in a.impact_review.splitlines():
            print(f"      {line}")
    if a.notes:
        print("\n    Notes:")
        for line in a.notes.splitlines():
            print(f"      {line}")


# ── Flows ──────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All QA Activities ═══")
    _print_table(data.list_activities())
    _pause()


def list_open() -> None:
    print("\n═══ Open QA Activities ═══")
    _print_table(data.list_activities(open_only=True))
    _pause()


def list_actions_open() -> None:
    print("\n═══ Outstanding Actions ═══")
    _print_table(data.list_activities(action_outstanding=True))
    _pause()


def list_actions_overdue() -> None:
    print("\n═══ Overdue Actions ═══")
    _print_table(data.list_activities(action_overdue=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        atype = _input(
            f"Type ({'/'.join(ACTIVITY_TYPES[:3])}…)") or None
        focus = _input(
            f"Focus ({'/'.join(FOCUS_AREAS[:3])}…)") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        lead = _input("Lead contains") or None
        subject = _input("Subject contains") or None
        department = _input("Department contains") or None
        judgement_raw = _input("Judgement (1-4)") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    j = int(judgement_raw) if judgement_raw and judgement_raw.isdigit() else None
    try:
        rows = data.list_activities(
            activity_type=atype, focus_area=focus,
            status=status, lead_like=lead,
            subject=subject, department=department,
            judgement=j, date_from=df, date_to=dt2)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_table(rows)
    _pause()


def view_flow() -> None:
    print("\n═══ View Activity ═══")
    try:
        a = _pick_activity()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_full(a)
    _pause()


def _collect_form(existing: QAActivity | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["title"] = _input(
        "Title",
        default=(existing.title if is_edit else ""),
        allow_empty=False)
    payload["activity_date"] = _input(
        "Date (YYYY-MM-DD)",
        default=(existing.activity_date if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    payload["activity_type"] = _pick_from(
        "Type", list(ACTIVITY_TYPES),
        default=(existing.activity_type if is_edit
                  else DEFAULT_ACTIVITY_TYPE))
    payload["focus_area"] = _pick_from(
        "Focus area", [""] + list(FOCUS_AREAS),
        default=(existing.focus_area if is_edit
                  else DEFAULT_FOCUS_AREA))
    payload["lead"] = _input(
        "Lead",
        default=(existing.lead if is_edit else ""),
        allow_empty=False)
    payload["participants"] = _input(
        "Participants",
        default=(existing.participants or "") if is_edit else "")
    payload["subject"] = _input(
        "Subject",
        default=(existing.subject or "") if is_edit else "")
    payload["department"] = _input(
        "Department",
        default=(existing.department or "") if is_edit else "")
    payload["judgement"] = _input(
        "Judgement (1-4, blank = none)",
        default=(str(existing.judgement)
                  if is_edit and existing.judgement is not None
                  else ""))
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    try:
        payload["strengths"] = _multiline(
            "Strengths",
            default=(existing.strengths or "") if is_edit else "")
        payload["areas_to_develop"] = _multiline(
            "Areas to develop",
            default=(existing.areas_to_develop or "")
            if is_edit else "")
        payload["evidence"] = _multiline(
            "Evidence",
            default=(existing.evidence or "") if is_edit else "")
        payload["action_summary"] = _multiline(
            "Action summary",
            default=(existing.action_summary or "")
            if is_edit else "")
    except _UserAbort:
        raise
    if payload["action_summary"]:
        payload["action_owner"] = _input(
            "Action owner",
            default=(existing.action_owner or "")
            if is_edit else "")
        payload["action_due"] = _input(
            "Action due (YYYY-MM-DD)",
            default=(existing.action_due or "")
            if is_edit else "")
        payload["action_completed"] = _yes_no(
            "Action completed?",
            default=(existing.action_completed
                      if is_edit else False))
        if payload["action_completed"]:
            try:
                payload["impact_review"] = _multiline(
                    "Impact review",
                    default=(existing.impact_review or "")
                    if is_edit else "")
            except _UserAbort:
                raise
            payload["impact_reviewed_on"] = _input(
                "Impact reviewed on (YYYY-MM-DD)",
                default=(existing.impact_reviewed_on or "")
                if is_edit else "")
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_activity() -> None:
    print("\n═══ New QA Activity ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_activity(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created #{a.activity_id}")
    _pause()


def edit_activity() -> None:
    print("\n═══ Edit QA Activity ═══")
    try:
        a = _pick_activity()
        payload = _collect_form(a)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_activity(a.activity_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{a.activity_id}")
    _pause()


def record_findings_flow() -> None:
    print("\n═══ Record Findings ═══")
    try:
        a = _pick_activity()
        strengths = _multiline("Strengths",
                                  default=a.strengths or "")
        areas = _multiline("Areas to develop",
                              default=a.areas_to_develop or "")
        evidence = _multiline("Evidence", default=a.evidence or "")
        j_raw = _input("Judgement (1-4, blank to keep)",
                          default=str(a.judgement) if a.judgement else "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    j = int(j_raw) if j_raw and j_raw.isdigit() else None
    try:
        data.record_findings(a.activity_id, strengths=strengths,
                                  areas=areas, evidence=evidence,
                                  judgement=j)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Findings recorded for #{a.activity_id}")
    _pause()


def set_action_flow() -> None:
    print("\n═══ Set Action ═══")
    try:
        a = _pick_activity()
        summary = _input("Action summary",
                            default=a.action_summary or "",
                            allow_empty=False)
        owner = _input("Action owner",
                          default=a.action_owner or "",
                          allow_empty=False)
        due = _input("Due (YYYY-MM-DD)", default=a.action_due or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_action(a.activity_id, summary=summary,
                            owner=owner, due=due or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Action set on #{a.activity_id}")
    _pause()


def complete_action_flow() -> None:
    print("\n═══ Complete Action ═══")
    try:
        a = _pick_activity()
        impact = _multiline("Impact review",
                              default=a.impact_review or "")
        when = _input("Reviewed on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.complete_action(a.activity_id, impact=impact,
                                  reviewed_on=when)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Action completed on #{a.activity_id}")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        a = _pick_activity()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=a.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(a.activity_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{a.activity_id} → {new_status}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete ═══")
    try:
        a = _pick_activity()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete #{a.activity_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_activity(a.activity_id):
        print(f"\n  ✓ Deleted #{a.activity_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ QA Summary ═══")
    s = data.summary()
    print(f"\n  Total                 : {s.total}")
    print(f"  Open                  : {s.open_count}")
    print(f"  Actions outstanding   : {s.actions_outstanding}")
    print(f"  Actions overdue       : {s.actions_overdue}")
    print(f"  Average judgement     : "
          f"{s.average_judgement if s.average_judgement is not None else '—'}")
    print(f"  Distinct leads        : {s.distinct_leads}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<22} : {n}")
    print("\n  By type:")
    for k in ACTIVITY_TYPES:
        n = s.by_type.get(k, 0)
        if n:
            print(f"    {k:<22} : {n}")
    print("\n  By judgement:")
    for j in JUDGEMENTS:
        n = s.by_judgement.get(j, 0)
        if n:
            print(f"    {j}  {judgement_label(j):<24}: {n}")
    if s.by_focus:
        print("\n  By focus area:")
        for f, n in s.by_focus.items():
            print(f"    {f:<24} : {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",              list_all),
    ("List open",             list_open),
    ("Actions outstanding",   list_actions_open),
    ("Actions overdue",       list_actions_overdue),
    ("Filter",                filter_flow),
    ("View",                  view_flow),
    ("─" * 6,                 lambda: None),
    ("New activity",          new_activity),
    ("Edit activity",         edit_activity),
    ("Record findings",       record_findings_flow),
    ("Set action",            set_action_flow),
    ("Complete action",       complete_action_flow),
    ("Change status",         set_status_flow),
    ("Delete",                delete_flow),
    ("─" * 6,                 lambda: None),
    ("Summary",               summary_flow),
]


def run() -> None:
    while True:
        print("\n── Quality Assurance ──")
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
            logger.exception("QA CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Quality Assurance":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("QA CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
