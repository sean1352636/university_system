"""Linked-platform items of the superadmin CLI (menu 17-24).

Text equivalents of the dashboard's cross-system sections: tasks, Learner
360, the transfer monitor, the event monitor, the system registry, identity,
cross-system reports and the per-boundary transfer boards. Same rules as the
GUI: read-mostly, every action gated on the cross-system permissions in
``role_manager``, and workflow functions still being built elsewhere are
looked up when chosen so a missing one prints a message instead of failing.
"""

from __future__ import annotations

import json
import logging

from education_system import paths as _paths
from education_system.platform.identity.auth.role_manager import (
    PERM_EVENTS_VIEW,
    PERM_IDENTITY_MERGE,
    PERM_LEARNER360_VIEW,
    PERM_TRANSFER_VIEW,
    has_cross_system_permission,
    is_superadmin_systems,
)

logger = logging.getLogger(__name__)

SYSTEM_LABELS = dict(_paths.SYSTEM_LABELS)


def _label(system) -> str:
    if not system:
        return "-"
    return SYSTEM_LABELS.get(system, str(system).replace("_", " ").title())


def _header(title):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def _pause():
    input("\n  Press Enter to continue...")


def _systems(user_info) -> list:
    return list((user_info or {}).get("systems", []))


def _can(user_info, permission, system=None) -> bool:
    return has_cross_system_permission(_systems(user_info), permission, system)


def _actor(user_info):
    uid = (user_info or {}).get("user_id") or (user_info or {}).get("id")
    return (uid if isinstance(uid, int) else None), str((user_info or {}).get("username") or "")


def _table(rows, columns):
    """Print ``rows`` (dicts) as a fixed-width table of ``(key, heading, width)``."""
    if not rows:
        print("\n  (none)")
        return
    print("\n  " + " ".join(f"{h:{w}.{w}s}" for _, h, w in columns))
    print("  " + "-" * (sum(w + 1 for _, _, w in columns) - 1))
    for i, row in enumerate(rows, 1):
        cells = [f"{str(row.get(k, '') if row.get(k) is not None else ''):{w}.{w}s}"
                 for k, _, w in columns]
        print(f"  {' '.join(cells)}  [{i}]")


def _pick(rows, prompt="Select # (blank to go back): "):
    choice = input(f"\n  {prompt}").strip()
    if not choice:
        return None
    try:
        return rows[int(choice) - 1]
    except (ValueError, IndexError):
        print("  Invalid selection.")
        return None


# ---------------------------------------------------------------------------
# 17. Cross-system Tasks
# ---------------------------------------------------------------------------

def tasks(user_info):
    _header("Cross-system Tasks")
    from education_system.platform.features.calendar.cross_system_tasks import list_tasks
    try:
        rows = list_tasks(_systems(user_info))
    except Exception as exc:
        print(f"\n  [!] Tasks unavailable: {exc}")
        _pause()
        return
    for row in rows:
        row["system_label"] = _label(row.get("system"))
    _table(rows, [("priority", "Priority", 8), ("kind", "Type", 11),
                  ("title", "Task", 46), ("system_label", "System", 18)])
    _pause()


# ---------------------------------------------------------------------------
# 18. Learner 360
# ---------------------------------------------------------------------------

def learner_360(user_info):
    _header("Learner 360")
    if not _can(user_info, PERM_LEARNER360_VIEW):
        print("\n  You do not hold learner360.view in any system.")
        _pause()
        return
    from education_system.platform.features.analytics import transfer_monitor as tm
    query = input("\n  Name, journey id or student id: ").strip()
    rows = tm.search_learners(query)
    for row in rows:
        row["current_label"] = _label(row.get("current_system"))
    _table(rows, [("name", "Name", 26), ("date_of_birth", "DOB", 10),
                  ("current_label", "Current", 18), ("journey_id", "Journey", 36)])
    picked = _pick(rows) if rows else None
    if picked is None:
        return
    jid = picked["journey_id"]
    while True:
        print(f"\n  {picked['name']}  ({jid})")
        print("    1) Journey overview   2) Transfers   3) Enrolments   "
              "4) Learner 360 record   0) Back")
        choice = input("  Select: ").strip()
        if choice == "1":
            from education_system.platform.cross_system import student_view
            print(student_view.format_overview_text(student_view.build_overview(jid)))
        elif choice == "2":
            _table(tm.search_transitions(journey_id=jid, limit=500), [
                ("source_label", "From", 18), ("destination_label", "To", 18),
                ("status", "Status", 17), ("awaiting_action", "Next action", 30)])
        elif choice == "3":
            from education_system.platform.cross_system import enrolments
            _table(enrolments.list_enrolments(jid), [
                ("system", "System", 16), ("status", "Status", 12),
                ("local_student_id", "Local id", 14), ("start_date", "Start", 10),
                ("end_date", "End", 10)])
        elif choice == "4":
            record = tm.learner_360_record(jid)
            if record is None:
                record = {"note": "learner_360.build_learner_360 is not available yet"}
            print(json.dumps(record, indent=2, default=str)[:6000])
        elif choice == "0":
            return
        _pause()


# ---------------------------------------------------------------------------
# 19. Transfer Monitor
# ---------------------------------------------------------------------------

def transfer_monitor(user_info):
    _header("Transfer Monitor")
    if not _can(user_info, PERM_TRANSFER_VIEW):
        print("\n  You do not hold transfer.view in any system.")
        _pause()
        return
    from education_system.platform.features.analytics import transfer_monitor as tm
    status = input("\n  Status filter (blank = all open, 'all' = everything): ").strip()
    rows = tm.search_transitions(
        status=None if status in ("", "all") else status,
        open_only=status == "", limit=500)
    _table(rows, [("source_label", "From", 16), ("destination_label", "To", 16),
                  ("status", "Status", 17), ("awaiting_action", "Next action", 28),
                  ("effective_date", "Effective", 10)])
    picked = _pick(rows) if rows else None
    if picked is None:
        return
    tid = picked["transition_id"]
    while True:
        detail = tm.transition_detail(tid) or {}
        row = detail.get("transition") or picked
        print(f"\n  Transition {tid}")
        print(f"  {row['source_label']} -> {row['destination_label']}   "
              f"status {row['status']}   journey {row['journey_id']}")
        print(f"\n  Step history ({detail.get('events_source', '?')}):")
        for event in detail.get("events", []):
            shown = tm.event_display(event)
            print(f"    {shown['when']:16s}  {shown['what']:24s} {shown['detail']}")
        checklist = detail.get("checklist")
        print("\n  Checklist:" if checklist is not None else
              "\n  Checklist: (not available yet)")
        for item in checklist or []:
            mark = "x" if tm.checklist_item_done(item) else " "
            print(f"    [{mark}] {item.get('label') or item.get('key')}  "
                  f"({item.get('owner') or 'destination'})")
        print("\n    a) Approve  r) Reject  k) Acknowledge  c) Complete  0) Back")
        choice = input("  Select: ").strip().lower()
        action = {"a": "approve", "r": "reject", "k": "acknowledge",
                  "c": "complete"}.get(choice)
        if choice == "0" or not choice:
            return
        if action is None:
            continue
        if row["status"] in tm.CLOSED_STATUSES:
            print("  This transfer is closed.")
            continue
        system = tm.action_system(action, row)
        if not _can(user_info, tm.action_permission(action), system):
            print(f"  You need {tm.action_permission(action)} in {_label(system)}.")
            continue
        reason = start_date = None
        if action == "reject":
            reason = input("  Reason: ").strip()
            if not reason:
                continue
        if action == "complete":
            start_date = input("  Start date (YYYY-MM-DD, blank for none): ").strip() or None
        uid, username = _actor(user_info)
        try:
            tm.perform_action(action, tid, actor_user_id=uid, actor=username,
                              reason=reason, start_date=start_date)
            print(f"  Done: {action}.")
        except tm.ActionUnavailable as exc:
            print(f"  Not available: {exc}")
        except Exception as exc:
            print(f"  Failed: {exc}")


# ---------------------------------------------------------------------------
# 20. Event Monitor
# ---------------------------------------------------------------------------

def event_monitor(user_info):
    _header("Event Monitor")
    if not _can(user_info, PERM_EVENTS_VIEW):
        print("\n  You do not hold events.view in any system.")
        _pause()
        return
    from education_system.platform.integrations.external import cross_system_bus as bus
    superadmin = is_superadmin_systems(_systems(user_info))
    name = input("\n  Event name filter (blank = all): ").strip() or None
    status = input(f"  Delivery status ({'/'.join(bus.DELIVERY_STATUSES)}, "
                   "blank = all): ").strip() or None
    try:
        rows = bus.list_events(event_name=name, status=status, limit=50,
                               include_payload=False)
    except ValueError as exc:
        print(f"  {exc}")
        _pause()
        return
    for row in rows:
        row["route"] = f"{row['source_system']}->{row['target_system'] or '*'}"
    _table(rows, [("created_at", "Published", 19), ("event_name", "Event", 30),
                  ("route", "Route", 24), ("delivery_status", "Delivery", 11)])
    dead = bus.list_failed_deliveries(limit=100)
    print(f"\n  Failed / dead-letter deliveries: {len(dead)}")
    _table(dead, [("event_name", "Event", 28), ("consumer_system", "Consumer", 12),
                  ("consumer_handler", "Handler", 34), ("attempts", "Tries", 5)])
    from education_system.platform.cross_system import sync_failures
    try:
        failed_syncs = sync_failures.list_failures(limit=100)
    except Exception as exc:
        logger.exception("Could not list cross-system sync failures")
        print(f"\n  Could not read failed syncs: {exc}")
        failed_syncs = []
    for row in failed_syncs:
        row["error_short"] = (row.get("error_message") or "")[:40]
    print(f"\n  Failed linked-record syncs (before the bus): {len(failed_syncs)}")
    _table(failed_syncs, [("created_at", "When", 19), ("operation", "Operation", 24),
                          ("system", "System", 12), ("local_id", "Local id", 12),
                          ("attempts", "Tries", 5), ("error_short", "Error", 40)])
    if not superadmin or not (dead or failed_syncs):
        _pause()
        return
    which = "d"
    if dead and failed_syncs:
        which = input("\n  d) Act on a delivery  s) Act on a sync failure  "
                      "(blank to go back): ").strip().lower()
    elif failed_syncs:
        which = "s"
    if which == "s":
        _act_on_sync_failure(failed_syncs, user_info)
        return
    if which != "d":
        return
    picked = _pick(dead, "Retry/abandon # (blank to go back): ")
    if picked is None:
        return
    key = (picked["event_id"], picked["consumer_system"], picked["consumer_handler"])
    choice = input("  r) Retry  a) Abandon: ").strip().lower()
    if choice == "r":
        print("  Queued for retry." if bus.retry_failed_delivery(*key)
              else "  Already changed.")
    elif choice == "a":
        reason = input("  Reason: ").strip()
        if reason:
            print("  Abandoned." if bus.abandon_failed_delivery(*key, reason=reason)
                  else "  Already changed.")
    _pause()


def _act_on_sync_failure(rows, user_info):
    from education_system.platform.cross_system import sync_failures
    picked = _pick(rows, "Retry/abandon # (blank to go back): ")
    if picked is None:
        return
    actor = _actor(user_info)[1] or "superadmin"
    choice = input("  r) Retry now  a) Abandon: ").strip().lower()
    if choice == "r":
        try:
            sync_failures.retry(picked["failure_id"], actor=actor)
            print("  Retried successfully.")
        except Exception as exc:
            print(f"  Retry failed again: {exc}")
    elif choice == "a":
        reason = input("  Reason: ").strip()
        if reason:
            print("  Abandoned." if sync_failures.abandon(
                picked["failure_id"], reason=reason, actor=actor)
                else "  Already changed.")
    _pause()


# ---------------------------------------------------------------------------
# 21. System Registry
# ---------------------------------------------------------------------------

def system_registry(user_info):
    _header("System Registry")
    from education_system.platform.features.analytics.platform_registry import (
        describe_systems,
    )
    rows = describe_systems()
    for row in rows:
        caps = row["adapter_capabilities"]
        row["adapter"] = (f"{sum(caps.values())}/4" if row["adapter_registered"]
                          else "none")
        intake = row["intake"]
        row["intake_text"] = (f"ok {intake.get('delivered', '?')} / fail "
                              f"{intake.get('failed', '?')} / dead "
                              f"{intake.get('dead_letter', '?')} / waiting "
                              f"{intake.get('undelivered', '?')}")
        row["open_text"] = (f"in {row['open_inbound_transitions']} / out "
                            f"{row['open_outbound_transitions']}")
    _table(rows, [("key", "Key", 16), ("display_name", "Name", 26),
                  ("adapter", "Adapter", 7), ("intake_text", "Intake", 40),
                  ("open_text", "Transfers", 16)])
    if is_superadmin_systems(_systems(user_info)):
        choice = input("\n  d) Drain shared consumers now  s) Sync calendar  "
                       "(blank to go back): ").strip().lower()
        if choice == "d":
            from education_system.platform.integrations.external.bus_drainer import (
                drain_platform_once,
            )
            print(f"  Dispatched {drain_platform_once()} event/handler pair(s).")
        elif choice == "s":
            from education_system.platform.features.calendar.transition_sync import (
                sync_transition_dates,
            )
            print(f"  Calendar: {sync_transition_dates()}")
    _pause()


# ---------------------------------------------------------------------------
# 22. Identity
# ---------------------------------------------------------------------------

def identity(user_info):
    _header("Identity & Duplicates")
    from education_system.platform.cross_system import identity_service
    from education_system.platform.features.analytics.transfer_monitor import (
        call_flexible,
        duplicate_candidates,
    )
    candidates = duplicate_candidates()
    if candidates is None:
        print("\n  Duplicate detection is not available yet.")
        candidates = []
    # "a" is the suggested survivor, "b" the suggested duplicate.
    pairs = [{"a": c["journey_id"], "b": c["duplicate_id"],
              "why": f"{c.get('score')}: " + "; ".join(c.get("reasons") or [])}
             for c in candidates]
    _table(pairs, [("a", "Journey A", 36), ("b", "Journey B", 36), ("why", "Why", 20)])
    print("\n    m) Merge a pair   b) Run identity backfills   0) Back")
    choice = input("  Select: ").strip().lower()
    if choice == "m" and pairs:
        if not _can(user_info, PERM_IDENTITY_MERGE):
            print("  Merging needs identity.merge (platform superadmin).")
        else:
            picked = _pick(pairs)
            merger = getattr(identity_service, "merge_journeys", None)
            if picked and merger is None:
                print("  Merging is not available yet.")
            elif picked:
                keep = input(f"  Keep which? a) {picked['a']}  b) {picked['b']}: ").strip()
                keep_id, drop_id = ((picked["a"], picked["b"]) if keep == "a"
                                    else (picked["b"], picked["a"]))
                reason = input("  Reason: ").strip()
                if reason and input("  Type MERGE to confirm: ").strip() == "MERGE":
                    _uid, username = _actor(user_info)
                    try:
                        # merge_journeys(survivor_id, duplicate_id, *, actor, reason)
                        result = call_flexible(merger, keep_id, drop_id,
                                               actor=username or "superadmin",
                                               reason=reason)
                        print(json.dumps(result, indent=2, default=str))
                    except Exception as exc:
                        print(f"  Merge failed: {exc}")
    elif choice == "b":
        if not is_superadmin_systems(_systems(user_info)):
            print("  Backfills are superadmin-only.")
        else:
            from education_system.platform.cross_system import identity_backfill
            runner = getattr(identity_backfill, "run_all", None)
            if runner is None:
                print("  identity_backfill.run_all is not available yet.")
            else:
                print(json.dumps(call_flexible(runner), indent=2, default=str))
    _pause()


# ---------------------------------------------------------------------------
# 23. Cross-system Reports
# ---------------------------------------------------------------------------

def cross_system_reports(user_info):
    _header("Cross-system Reports")
    from education_system.platform.features.analytics import journey_analytics
    from education_system.platform.features.analytics.warehouse import Warehouse
    try:
        funnel = Warehouse().retention_funnel()
        print(f"\n  Journeys in the registry: {funnel.get('_total_journeys', 0)}")
    except Exception as exc:
        print(f"\n  [!] Warehouse unavailable: {exc}")
    flow = journey_analytics.cohort_flow_all_systems()
    _table(flow["stage_presence"], [("label", "System", 22),
                                    ("reached", "Ever reached", 12),
                                    ("active", "Active now", 10)])
    for row in flow["boundaries"]:
        row["route"] = f"{row['source_label']} -> {row['destination_label']}"
    _table(flow["boundaries"], [("route", "Route", 40), ("total", "Total", 6),
                                ("completed", "Done", 6), ("cancelled", "Cancel", 6),
                                ("in_progress", "Open", 6),
                                ("completion_rate", "Rate %", 7)])
    outcomes = journey_analytics.destination_outcomes()
    print(f"\n  Destination outcomes (source: {outcomes['source']})")
    if outcomes["source"] == "destinations":
        print(json.dumps(outcomes["summary"], indent=2, default=str)[:4000])
    else:
        _table(outcomes["by_destination"], [("source_label", "From", 22),
                                            ("destination_label", "To", 22),
                                            ("count", "Learners", 8)])
    _pause()


# ---------------------------------------------------------------------------
# 24. Transfer Boards
# ---------------------------------------------------------------------------

_BOARDS = [
    ("University applications - Sixth Form",
     "university_applications_cli", "dashboard", ("sixth_form",)),
    ("University applications - FE College",
     "university_applications_cli", "dashboard", ("fe_college",)),
    ("University applications - Apprenticeships",
     "university_applications_cli", "dashboard", ("apprenticeships",)),
    ("Post-16 destinations - Secondary", "secondary_post16_cli", "menu", ()),
    ("Apprenticeship applications - Sixth Form",
     "apprenticeship_applications_cli", "menu", ("sixth_form",)),
    ("Apprenticeship applications - FE College",
     "apprenticeship_applications_cli", "menu", ("fe_college",)),
    ("Apprenticeship applications - University",
     "apprenticeship_applications_cli", "menu", ("university",)),
]


def transfer_boards(user_info):
    import importlib
    while True:
        _header("Transfer Boards")
        for i, (label, *_rest) in enumerate(_BOARDS, 1):
            print(f"   {i}) {label}")
        print("   0) Back")
        choice = input("\n  Select: ").strip()
        if choice in ("", "0"):
            return
        try:
            label, module, func, args = _BOARDS[int(choice) - 1]
        except (ValueError, IndexError):
            print("  Invalid option.")
            continue
        try:
            mod = importlib.import_module(f"education_system.platform.cross_system.{module}")
            getattr(mod, func)(*args)
        except Exception as exc:
            print(f"\n  [!] {label} failed: {exc}")
        _pause()


MENU_ITEMS: dict[str, tuple[str, object]] = {
    "17": ("Cross-system Tasks", tasks),
    "18": ("Learner 360", learner_360),
    "19": ("Transfer Monitor", transfer_monitor),
    "20": ("Event Monitor", event_monitor),
    "21": ("System Registry", system_registry),
    "22": ("Identity & Duplicates", identity),
    "23": ("Cross-system Reports", cross_system_reports),
    "24": ("Transfer Boards", transfer_boards),
}


__all__ = ["MENU_ITEMS"]
