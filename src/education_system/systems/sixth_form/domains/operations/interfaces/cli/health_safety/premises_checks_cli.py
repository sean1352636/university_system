"""CLI flows for fire drills and recurring premises checks (Health &
Safety). Also reachable from the Health & Safety menu."""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Callable

from education_system.systems.sixth_form.domains.operations.domain.health_safety import (
    premises_checks as data,
)
from education_system.systems.sixth_form.interfaces.cli.operations._ops_cli import (
    ask,
    ask_int,
    choose,
    pause,
    run_menu,
    table,
    yes_no,
)

logger = logging.getLogger(__name__)


def _pick_type() -> int:
    types = data.list_check_types(active_only=True)
    label = choose("Check", [f"{t.type_id} — {t.name} ({t.frequency})"
                             for t in types])
    if label is None:
        raise ValueError("No check types yet — add some or install the "
                         "standard list")
    return int(label.split(" — ")[0])


def _pick_rollcall() -> int:
    rows = data.recent_rollcalls()
    label = choose("Roll call", [f"{r.drill_id} — {r.kind} {r.date} "
                                 f"{r.started_at[-8:-3]} ({r.state})"
                                 for r in rows])
    if label is None:
        raise ValueError("No roll calls recorded in attendance")
    return int(label.split(" — ")[0])


def _due(rows) -> None:
    table(["Check", "Frequency", "Last done", "Result", "Next due", "State",
           "Days late"],
          [(d.name, d.frequency, d.last_done, d.last_result, d.next_due,
            d.state, d.days_overdue or "") for d in rows])


def register_flow() -> None:
    _due(data.check_register())
    pause()


def overdue_flow() -> None:
    _due(data.overdue_checks(include_due_soon=yes_no("Include due soon?",
                                                     default=True)))
    pause()


def record_check_flow() -> None:
    tid = _pick_type()
    result = choose("Result", data.RESULTS, default=data.PASS)
    payload = {
        "type_id": tid, "result": result,
        "checked_on": ask("Date", default=_dt.date.today().isoformat()),
        "checked_at": ask("Time (HH:MM)"),
        "location": ask("Where (call point, zone, outlet)"),
        "findings": ask("Findings", required=result != data.PASS),
        "checked_by": ask("Checked by (blank = you)")}
    if result != data.PASS and yes_no("Raise a follow-up action?",
                                      default=True):
        payload.update(action=ask("Action", required=True),
                       action_owner=ask("Owner"),
                       action_due=ask("Due (YYYY-MM-DD)"))
    c = data.record_check(payload)
    print(f"\n  ✓ {c.type_name}: {c.result} on {c.checked_on}")
    pause()


def checks_flow() -> None:
    tid = _pick_type() if yes_no("One check type only?") else None
    table(["Date", "Check", "Where", "Result", "Findings", "By"],
          [(c.checked_on, c.type_name, c.location, c.result, c.findings,
            c.checked_by) for c in data.list_checks(type_id=tid, limit=100)])
    pause()


def failed_flow() -> None:
    table(["Date", "Check", "Where", "Result", "Findings"],
          [(c.checked_on, c.type_name, c.location, c.result, c.findings)
           for c in data.failed_checks()])
    pause()


def log_drill_flow() -> None:
    payload = {
        "drill_date": ask("Date", default=_dt.date.today().isoformat()),
        "drill_time": ask("Time of alarm (HH:MM)"),
        "drill_type": choose("Type", data.DRILL_TYPES,
                             default=data.DEFAULT_DRILL_TYPE),
        "scenario": ask("Scenario / zone / call point"),
        "evacuation_time": ask("Building clear in (m:ss)"),
        "assembly_point": ask("Assembly point"),
        "people_evacuated": ask("People evacuated"),
        "rollcall_complete": yes_no("Roll call completed?", default=True),
        "rollcall_time": ask("Roll call took (m:ss)"),
        "issues_found": ask("Issues found"),
        "led_by": ask("Led by"), "notes": ask("Notes")}
    if yes_no("Link the attendance roll call?"):
        payload["rollcall_id"] = _pick_rollcall()
    d = data.log_drill(payload)
    print(f"\n  ✓ Fire drill #{d.drill_id} logged")
    if d.issues_found and yes_no("Raise an action for the issues?",
                                 default=True):
        _add_action({"drill_id": d.drill_id})
    pause()


def from_rollcall_flow() -> None:
    d = data.log_drill_from_rollcall(
        _pick_rollcall(), scenario=ask("Scenario / zone"),
        issues_found=ask("Issues found"))
    print(f"\n  ✓ Fire drill #{d.drill_id}: roll call "
          f"{'complete' if d.rollcall_complete else 'incomplete'}, "
          f"{d.rollcall_missing or 0} missing")
    pause()


def drills_flow() -> None:
    table(["#", "Date", "Time", "Type", "Clear in", "Roll call", "Issues"],
          [(d.drill_id, d.drill_date, d.drill_time, d.drill_type,
            d.evacuation_label,
            "complete" if d.rollcall_complete else "incomplete",
            d.issues_found) for d in data.list_drills()])
    pause()


def drill_report_flow() -> None:
    r = data.drill_report(date_from=ask("From (blank = all)") or None,
                          date_to=ask("To (blank = today)") or None)
    print(f"\n  Drills logged:       {r['drills']}")
    for k, v in r["by_type"].items():
        print(f"    {k:<28} {v}")
    print(f"  Average evacuation:  {r['average_evacuation'] or '—'}")
    print(f"  Slowest evacuation:  {r['slowest_evacuation'] or '—'}")
    print(f"  Roll calls complete: {r['rollcalls_complete']}")
    print(f"  Actions:             {r['actions']} ({r['actions_open']} open)")
    pause()


def _add_action(link: dict) -> None:
    a = data.add_action({**link, "action": ask("Action", required=True),
                         "owner": ask("Owner"),
                         "due_date": ask("Due (YYYY-MM-DD)")})
    print(f"  ✓ Action #{a.action_id} raised")


def actions_flow() -> None:
    rows = data.list_actions(open_only=yes_no("Open only?", default=True))
    table(["#", "From", "Action", "Owner", "Due", "Status"],
          [(a.action_id, a.source, a.action, a.owner,
            (a.due_date or "") + (" !" if a.is_overdue else ""), a.status)
           for a in rows])
    pause()


def action_drill_flow() -> None:
    _add_action({"drill_id": ask_int("Fire drill #")})
    pause()


def close_action_flow() -> None:
    aid = ask_int("Action #")
    status = choose("Status", (data.ACTION_DONE, data.ACTION_CANCELLED),
                    default=data.ACTION_DONE)
    data.set_action_status(aid, status, notes=ask("Note"))
    print("\n  ✓ Updated")
    pause()


def types_flow() -> None:
    table(["ID", "Check", "Category", "Frequency", "Warn", "Active"],
          [(t.type_id, t.name, t.category, t.frequency, t.due_soon_days,
            "Y" if t.active else "N") for t in data.list_check_types()])
    pause()


def new_type_flow() -> None:
    t = data.create_check_type({
        "name": ask("Check", required=True),
        "category": choose("Category", data.CHECK_CATEGORIES,
                           default="General"),
        "frequency": choose("Frequency", list(data.FREQUENCIES),
                            default="Monthly"),
        "due_soon_days": ask("Warn days before", default="7"),
        "guidance": ask("Guidance / standard"),
        "responsible": ask("Responsible")})
    print(f"\n  ✓ Added {t.name}")
    pause()


def edit_type_flow() -> None:
    t = data.get_check_type(_pick_type())
    t = data.update_check_type(t.type_id, {
        "name": ask("Check", default=t.name),
        "frequency": choose("Frequency", list(data.FREQUENCIES),
                            default=t.frequency),
        "due_soon_days": ask("Warn days before",
                             default=str(t.due_soon_days)),
        "responsible": ask("Responsible", default=t.responsible or ""),
        "active": yes_no("Active", default=t.active)})
    print(f"\n  ✓ Updated {t.name}")
    pause()


def install_flow() -> None:
    if yes_no("Add the standard UK premises check list (existing checks "
              "unchanged, nothing marked done)?", default=True):
        print(f"\n  ✓ Added {len(data.install_default_check_types())} "
              "check type(s)")
    pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Due register",               register_flow),
    ("Overdue checks",             overdue_flow),
    ("Record a check",             record_check_flow),
    ("Check log",                  checks_flow),
    ("Fails and advisories",       failed_flow),
    ("─" * 6,                      lambda: None),
    ("Log fire drill",             log_drill_flow),
    ("Log drill from roll call",   from_rollcall_flow),
    ("Fire drill log",             drills_flow),
    ("Fire drill report",          drill_report_flow),
    ("─" * 6,                      lambda: None),
    ("Actions",                    actions_flow),
    ("Raise action on a drill",    action_drill_flow),
    ("Close an action",            close_action_flow),
    ("─" * 6,                      lambda: None),
    ("Check types",                types_flow),
    ("New check type",             new_type_flow),
    ("Edit check type",            edit_type_flow),
    ("Add standard UK list",       install_flow),
]


def run() -> None:
    data.init_db()
    run_menu("Fire Drills & Premises Checks", _MENU)


def premises_checks_menu() -> None:
    """Entry point for the main CLI menu."""
    run()


def dispatch(label: str) -> bool:
    if label not in ("Fire Drills & Checks", "Fire Drills & Premises Checks"):
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Premises checks CLI crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        pause()
    return True
