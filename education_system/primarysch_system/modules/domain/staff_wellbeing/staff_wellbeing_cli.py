"""CLI flows for Primary School Staff Wellbeing."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.primarysch_system.modules.domain.staff_wellbeing import (
    staff_wellbeing as data,
)
from education_system.primarysch_system.modules.domain.staff_wellbeing.staff_wellbeing import (
    ACTION_TYPES,
    CONCERN_FLAGS,
    DEFAULT_ENTRY_TYPE,
    DEFAULT_STATUS,
    ENTRY_TYPES,
    LIKERTS,
    STATUSES,
    ValidationError,
    WellbeingEntry,
    likert_label,
)
from education_system.primarysch_system.modules.domain.staff import (
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


def _pick_concerns(default: list[str]) -> list[str]:
    print("\n  Concern flags (enter numbers comma-separated, "
          "or blank to keep):")
    for i, c in enumerate(CONCERN_FLAGS, 1):
        marker = "*" if c in default else " "
        print(f"    {marker} {i:>2}) {c}")
    try:
        raw = input("  > ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    if not raw:
        return list(default)
    picks: list[str] = []
    for tok in raw.split(","):
        tok = tok.strip()
        if tok.isdigit():
            n = int(tok)
            if 1 <= n <= len(CONCERN_FLAGS):
                picks.append(CONCERN_FLAGS[n - 1])
    return picks


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


def _pick_entry() -> WellbeingEntry:
    rows = data.list_entries()
    if not rows:
        print("    No entries yet.")
        raise _UserAbort
    print("\n  Wellbeing entries:")
    for i, e in enumerate(rows, 1):
        flag = "!" if e.at_risk else " "
        print(f"    {i:>3}){flag} #{e.entry_id}  "
              f"{e.entry_date}  {e.staff_id:<12}  "
              f"{e.entry_type[:22]:<22}  "
              f"avg={e.average_score}  [{e.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.entry_id == n), None)
            if match:
                return match
        print("    No matching entry.")


def _print_table(rows: list[WellbeingEntry]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Date':<10}  {'Staff':<12}  "
          f"{'Type':<26}  Avg   {'Status':<14}  Flags")
    print("  " + "-" * 130)
    for e in rows:
        flags = []
        if e.at_risk:
            flags.append("AT-RISK")
        if e.follow_up_overdue:
            flags.append("FU-OVERDUE")
        if e.confidential:
            flags.append("CONFID")
        avg = (f"{e.average_score:.2f}"
                if e.average_score is not None else " — ")
        print(f"  {e.entry_id:>4}  {e.entry_date:<10}  "
              f"{e.staff_id:<12}  "
              f"{e.entry_type[:26]:<26}  "
              f"{avg}  {e.status:<14}  "
              f"{','.join(flags)}")
    print(f"\n  {len(rows)} entry(ies).")


def _print_full(e: WellbeingEntry) -> None:
    print()
    print(f"    #{e.entry_id}  Staff {e.staff_id}")
    print(f"    Date            : {e.entry_date}")
    print(f"    Type            : {e.entry_type}")
    print(f"    Recorded by     : {e.recorded_by or '—'}")
    print(f"    Confidential    : "
          f"{'yes' if e.confidential else 'no'}")
    print(f"    Anonymous       : "
          f"{'yes' if e.anonymous else 'no'}")
    print(f"    Consent to share: "
          f"{'yes' if e.consent_to_share else 'no'}")
    print(f"    Status          : {e.status}")
    print()
    print(f"    Ratings (1=Very Low .. 5=Very High):")
    for label, v in (
            ("Mood",              e.mood),
            ("Stress",            e.stress),
            ("Workload pressure", e.workload_pressure),
            ("Job satisfaction",  e.job_satisfaction),
            ("Energy",            e.energy),
    ):
        print(f"      {label:<20}: {v if v is not None else '—'}"
              + (f"  ({likert_label(v)})" if v else ""))
    avg = e.average_score
    if avg is not None:
        print(f"      Average             : {avg}")
    if e.at_risk:
        print("      ** AT RISK indicators present **")
    if e.concern_flag_list:
        print(f"\n    Concern flags: "
              f"{', '.join(e.concern_flag_list)}")
    if e.action_type:
        print(f"    Action type   : {e.action_type}")
    if e.referred_to:
        print(f"    Referred to   : {e.referred_to}")
    print(f"    Follow-up due : {e.follow_up_due or '—'}"
          + ("  (OVERDUE)" if e.follow_up_overdue else ""))
    print(f"    Follow-up done: {e.follow_up_done_on or '—'}")
    print(f"    Closed on     : {e.closed_on or '—'}")
    for label, val in (
            ("Presenting issue", e.presenting_issue),
            ("Summary notes",    e.summary_notes),
            ("Actions taken",    e.actions_taken),
            ("Support plan",     e.support_plan),
            ("Notes",            e.notes),
    ):
        if val:
            print(f"\n    {label}:")
            for line in val.splitlines():
                print(f"      {line}")


# ── Flows ──────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Entries ═══")
    _print_table(data.list_entries())
    _pause()


def list_open() -> None:
    print("\n═══ Open Entries ═══")
    _print_table(data.list_entries(open_only=True))
    _pause()


def list_at_risk() -> None:
    print("\n═══ At-Risk ═══")
    _print_table(data.list_entries(at_risk_only=True))
    _pause()


def list_follow_up_overdue() -> None:
    print("\n═══ Follow-Up Overdue ═══")
    _print_table(data.list_entries(follow_up_overdue=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        sid = _input("Staff id") or None
        et = _input(
            f"Entry type ({'/'.join(ENTRY_TYPES[:2])}…)") or None
        status = _input(
            f"Status ({'/'.join(STATUSES[:3])}…)") or None
        action = _input(
            f"Action type ({'/'.join(ACTION_TYPES[:2])}…)") or None
        flag = _input(
            f"Concern flag contains "
            f"({'/'.join(CONCERN_FLAGS[:2])}…)") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_entries(staff_id=sid, entry_type=et,
                                      status=status,
                                      action_type=action,
                                      with_concern_flag=flag,
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
    _print_table(data.entries_for_staff(sid))
    _pause()


def view_flow() -> None:
    print("\n═══ View Entry ═══")
    try:
        e = _pick_entry()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_full(e)
    _pause()


def _collect_form(existing: WellbeingEntry | None
                       ) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        payload["staff_id"] = existing.staff_id
    else:
        payload["staff_id"] = _pick_staff()
    payload["entry_date"] = _input(
        "Entry date (YYYY-MM-DD)",
        default=(existing.entry_date if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    payload["entry_type"] = _pick_from(
        "Entry type", list(ENTRY_TYPES),
        default=(existing.entry_type if is_edit
                  else DEFAULT_ENTRY_TYPE))
    payload["recorded_by"] = _input(
        "Recorded by",
        default=(existing.recorded_by or "")
        if is_edit else "")
    payload["confidential"] = _yes_no(
        "Confidential?",
        default=(existing.confidential if is_edit else True))
    payload["anonymous"] = _yes_no(
        "Anonymous?",
        default=(existing.anonymous if is_edit else False))
    payload["consent_to_share"] = _yes_no(
        "Consent to share with line manager?",
        default=(existing.consent_to_share
                  if is_edit else False))
    print("\n  Ratings (1=Very Low .. 5=Very High; blank to skip):")
    for k, label in (
            ("mood",              "Mood"),
            ("stress",            "Stress"),
            ("workload_pressure", "Workload pressure"),
            ("job_satisfaction",  "Job satisfaction"),
            ("energy",            "Energy"),
    ):
        current = getattr(existing, k) if is_edit else None
        payload[k] = _input(
            label,
            default=(str(current) if current is not None
                      else ""))
    payload["concern_flags"] = _pick_concerns(
        existing.concern_flag_list if is_edit else [])
    try:
        payload["presenting_issue"] = _multiline(
            "Presenting issue",
            default=(existing.presenting_issue or "")
            if is_edit else "")
        payload["summary_notes"] = _multiline(
            "Summary notes",
            default=(existing.summary_notes or "")
            if is_edit else "")
        payload["actions_taken"] = _multiline(
            "Actions taken",
            default=(existing.actions_taken or "")
            if is_edit else "")
        payload["support_plan"] = _multiline(
            "Support plan",
            default=(existing.support_plan or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["action_type"] = _pick_from(
        "Action type", [""] + list(ACTION_TYPES),
        default=(existing.action_type if is_edit else ""))
    payload["referred_to"] = _input(
        "Referred to",
        default=(existing.referred_to or "")
        if is_edit else "")
    payload["follow_up_due"] = _input(
        "Follow-up due (YYYY-MM-DD)",
        default=(existing.follow_up_due or "")
        if is_edit else "")
    payload["follow_up_done_on"] = _input(
        "Follow-up done on (YYYY-MM-DD)",
        default=(existing.follow_up_done_on or "")
        if is_edit else "")
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_STATUS))
    payload["closed_on"] = _input(
        "Closed on (YYYY-MM-DD)",
        default=(existing.closed_on or "")
        if is_edit else "")
    try:
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "") if is_edit else "")
    except _UserAbort:
        raise
    return payload


def new_entry() -> None:
    print("\n═══ New Wellbeing Entry ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        e = data.create_entry(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created entry #{e.entry_id}")
    _pause()


def edit_entry() -> None:
    print("\n═══ Edit Entry ═══")
    try:
        e = _pick_entry()
        payload = _collect_form(e)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_entry(e.entry_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{e.entry_id}")
    _pause()


def set_action_plan_flow() -> None:
    print("\n═══ Set Action Plan ═══")
    try:
        e = _pick_entry()
        action = _pick_from("Action type", list(ACTION_TYPES),
                                default=e.action_type
                                or ACTION_TYPES[0])
        actions = _multiline("Actions taken",
                                default=e.actions_taken or "")
        if not actions:
            print("  ✗ Actions required.")
            _pause()
            return
        support = _multiline("Support plan",
                                default=e.support_plan or "")
        follow_up = _input("Follow-up due (YYYY-MM-DD)",
                              default=e.follow_up_due or "")
        referred = _input("Referred to",
                              default=e.referred_to or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_action_plan(e.entry_id,
                                  action_type=action,
                                  actions_taken=actions,
                                  support_plan=support or None,
                                  follow_up_due=follow_up or None,
                                  referred_to=referred or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Action plan set on #{e.entry_id}")
    _pause()


def complete_follow_up_flow() -> None:
    print("\n═══ Complete Follow-Up ═══")
    try:
        e = _pick_entry()
        when = _input("Done on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
        notes = _multiline("Follow-up notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.complete_follow_up(e.entry_id, done_on=when,
                                      notes=notes or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Follow-up completed on #{e.entry_id}")
    _pause()


def resolve_flow() -> None:
    print("\n═══ Resolve ═══")
    try:
        e = _pick_entry()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.resolve(e.entry_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{e.entry_id} → Resolved")
    _pause()


def close_flow() -> None:
    print("\n═══ Close ═══")
    try:
        e = _pick_entry()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.close_entry(e.entry_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{e.entry_id} → Closed")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        e = _pick_entry()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=e.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(e.entry_id, new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{e.entry_id} → {new_status}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete ═══")
    try:
        e = _pick_entry()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete entry #{e.entry_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_entry(e.entry_id):
        print(f"\n  ✓ Deleted #{e.entry_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Staff Wellbeing Summary ═══")
    s = data.summary()
    print(f"\n  Total entries        : {s.total}")
    print(f"  Open                 : {s.open_count}")
    print(f"  At risk              : {s.at_risk}")
    print(f"  Follow-up overdue    : {s.follow_up_overdue}")
    print(f"  Referrals made       : {s.referrals_made}")
    print(f"  Distinct staff       : {s.distinct_staff}")
    print(f"  Avg mood             : "
          f"{s.average_mood if s.average_mood is not None else '—'}")
    print(f"  Avg stress           : "
          f"{s.average_stress if s.average_stress is not None else '—'}")
    print(f"  Avg workload pres.   : "
          f"{s.average_workload if s.average_workload is not None else '—'}")
    print(f"  Avg satisfaction     : "
          f"{s.average_satisfaction if s.average_satisfaction is not None else '—'}")
    print(f"  Avg energy           : "
          f"{s.average_energy if s.average_energy is not None else '—'}")
    print("\n  By entry type:")
    for k in ENTRY_TYPES:
        n = s.by_type.get(k, 0)
        if n:
            print(f"    {k:<32}: {n}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<16}: {n}")
    if s.by_action:
        print("\n  By action type:")
        for k in ACTION_TYPES:
            n = s.by_action.get(k, 0)
            if n:
                print(f"    {k:<28}: {n}")
    if s.by_concern_flag:
        print("\n  By concern flag:")
        for k in CONCERN_FLAGS:
            n = s.by_concern_flag.get(k, 0)
            if n:
                print(f"    {k:<22}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",            list_all),
    ("Open only",           list_open),
    ("At risk",             list_at_risk),
    ("Follow-up overdue",   list_follow_up_overdue),
    ("Filter",              filter_flow),
    ("Per-staff",           per_staff_flow),
    ("View",                view_flow),
    ("─" * 6,               lambda: None),
    ("New entry",           new_entry),
    ("Edit entry",          edit_entry),
    ("Set action plan",     set_action_plan_flow),
    ("Complete follow-up",  complete_follow_up_flow),
    ("Resolve",             resolve_flow),
    ("Close",               close_flow),
    ("Change status",       set_status_flow),
    ("Delete",              delete_flow),
    ("─" * 6,               lambda: None),
    ("Summary",             summary_flow),
]


def run() -> None:
    while True:
        print("\n── Staff Wellbeing ──")
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
            logger.exception("Staff Wellbeing CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Staff Wellbeing":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Staff Wellbeing CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
