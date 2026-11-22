"""Admin-only console menu for the institutional connectors, the university
event queue and record retention — mirrors sso_providers_cli.

* Connectors (UCAS, HESA, SLC, UKVI, payments, library, VLE, IdP, timetable,
  degree verification): switch on/off, choose the transport (a daily file
  to upload, or HTTPS), see the receipts. ``application/connectors``.
* Event queue: what is waiting, what was dead-lettered and why; requeue a
  dead event; run a delivery pass now. ``application/outbox_dispatcher``.
* Record retention: which record types are past their period, and switching
  disposal on per type. ``domains/governance/infrastructure/data_lifecycle_store``.
"""
from __future__ import annotations

import json
from typing import Any

from education_system.systems.university.application import connectors, outbox_dispatcher
from education_system.systems.university.domains.governance.infrastructure import (
    data_lifecycle_store,
)
from education_system.systems.university.infrastructure.auth import sso_admin
from education_system.systems.university.infrastructure.connector_adapters import OUTBOUND_DIR
from education_system.systems.university.infrastructure.i18n import get_text

auth: Any = None


def set_auth(auth_object: Any) -> None:
    global auth
    auth = auth_object


def _actor() -> str:
    user = getattr(auth, "current_user", None) or {}
    return str(user.get("username") or user.get("id") or "unknown")


def _require_admin() -> bool:
    user = getattr(auth, "current_user", None) if auth else None
    if not user:
        print(get_text("cli.connectors.login_required",
                       default="You must be logged in to manage connectors."))
        return False
    if not sso_admin.is_admin(user):
        print(get_text("cli.connectors.admin_only",
                       default="Connector and event-queue management is admin only."))
        return False
    return True


def _list_connectors() -> None:
    print(f"\n{'Connector':<20} {'On':<4} {'Transport':<10} {'Status':<13} {'Sent':>5}  Last error")
    for c in connectors.overview():
        print(f"{c['connector_name']:<20} {'yes' if c['enabled'] else 'no':<4} "
              f"{c['config'].get('transport', 'file'):<10} {c['status']:<13} "
              f"{c['receipts']:>5}  {c['last_error'] or ''}")
    print(f"\nFiles are written to {OUTBOUND_DIR}/<connector>/<date>.jsonl")


def _pick_connector() -> str | None:
    name = input("Connector name: ").strip()
    if name not in connectors.SUPPORTED_CONNECTORS:
        print("Unknown connector.")
        return None
    return name


def _configure() -> None:
    name = _pick_connector()
    if not name:
        return
    current = next(c for c in connectors.overview() if c["connector_name"] == name)
    transport = (input(f"Transport (file/http) [{current['config'].get('transport', 'file')}]: ")
                 .strip().lower() or current["config"].get("transport", "file"))
    config: dict[str, Any] = {"transport": transport}
    if transport == "http":
        config["endpoint"] = input("HTTPS endpoint: ").strip()
        config["token_env"] = input("Environment variable holding the token (blank: none): ").strip()
        if not config["token_env"]:
            config.pop("token_env")
            token_file = input("Token file under var/secrets (blank: none): ").strip()
            if token_file:
                config["token_file"] = token_file
        if not config["endpoint"].lower().startswith("https://"):
            print("The endpoint must start with https://")
            return
    elif transport != "file":
        print("Transport must be file or http.")
        return
    enable = input("Switch it on now? (y/N): ").strip().lower() == "y"
    connectors.configure(name, config, enabled=enable)
    print(f"{name} saved ({'on' if enable else 'off'}).")


def _set_enabled(enabled: bool) -> None:
    name = _pick_connector()
    if not name:
        return
    current = next(c for c in connectors.overview() if c["connector_name"] == name)
    connectors.configure(name, current["config"] or {"transport": "file"}, enabled=enabled)
    print(f"{name} is now {'on' if enabled else 'off'}.")


def _receipts() -> None:
    name = _pick_connector()
    if not name:
        return
    rows = connectors.receipts(name, limit=30)
    if not rows:
        print("Nothing sent yet.")
    for r in rows:
        print(f"  {str(r['processed_at'])[:19]}  {r['outcome']:<10} "
              f"{r['external_reference'] or '-':<28} {r['idempotency_key']}")


def _queue() -> None:
    s = outbox_dispatcher.summary()
    print(f"\nEvents: {s['waiting']} waiting, {s['dead_lettered']} dead-lettered, "
          f"{s['delivered']} delivered")
    print(f"Lifecycle actions: {s['actions_pending']} pending, {s['actions_failed']} failed, "
          f"{s['actions_completed']} completed")
    for state in ("waiting", "dead"):
        rows = outbox_dispatcher.events(state, limit=20)
        if rows:
            print(f"\n{state.title()}:")
        for e in rows:
            print(f"  {e['event_id'][:8]}  {e['event_name']:<34} {e['aggregate_id']:<12} "
                  f"tries {e['attempts']}  {e['last_error'] or ''}")
    actions = outbox_dispatcher.lifecycle_actions(limit=20)
    if actions:
        print("\nLifecycle actions not yet done:")
    for a in actions:
        print(f"  #{a['action_id']:<5} {a['student_id']:<10} {a['target_system']:<18} "
              f"{a['action']:<18} {a['status']:<8} {a['last_error'] or ''}")


def _requeue() -> None:
    prefix = input("Event id (or its first 8 characters): ").strip()
    matches = [e for e in outbox_dispatcher.events("dead", limit=500)
               if e["event_id"].startswith(prefix)] if prefix else []
    if len(matches) != 1:
        print("No single dead-lettered event matches that id.")
        return
    if outbox_dispatcher.requeue(matches[0]["event_id"]):
        print("Requeued; it will be tried on the next pass.")


def _run_now() -> None:
    print(json.dumps(outbox_dispatcher.run_once(), indent=2, default=str))


def _retention() -> None:
    on = data_lifecycle_store.settings()
    print(f"\n{'Record type':<16} {'Disposal':<9} Due now")
    for record_type in ("applicant", "student_record"):
        print(f"{record_type:<16} {'on' if on[record_type] else 'off':<9} "
              f"{len(data_lifecycle_store.due(record_type))}")
    print("(finance, health and safeguarding records are handled by their own retention jobs)")
    record_type = input("\nRecord type to switch (blank: none): ").strip()
    if not record_type:
        return
    if record_type not in ("applicant", "student_record"):
        print("Unknown record type.")
        return
    enable = input("Turn disposal on? (y/N): ").strip().lower() == "y"
    if enable and input("Due records will be redacted at the next daily run. "
                        "Type REDACT to confirm: ").strip() != "REDACT":
        print("Not changed.")
        return
    data_lifecycle_store.set_enabled(record_type, enable, actor_id=_actor())
    print(f"{record_type} disposal is now {'on' if enable else 'off'}.")


def display_connectors_menu() -> None:
    """Top-level connectors / event queue / retention menu (admin only)."""
    if not _require_admin():
        return
    actions = {
        "1": ("List connectors", _list_connectors),
        "2": ("Configure a connector", _configure),
        "3": ("Switch a connector on", lambda: _set_enabled(True)),
        "4": ("Switch a connector off", lambda: _set_enabled(False)),
        "5": ("What a connector has sent", _receipts),
        "6": ("Event queue and lifecycle actions", _queue),
        "7": ("Requeue a dead-lettered event", _requeue),
        "8": ("Run a delivery pass now", _run_now),
        "9": ("Record retention", _retention),
    }
    while True:
        print("\n" + get_text("cli.connectors.title", default="Connectors & Event Queue"))
        print("=" * 30)
        for key, (label, _) in actions.items():
            print(f"{key}. {label}")
        print("0. " + get_text("cli.menu.return", default="Return to Previous Menu"))
        choice = input("\nEnter your choice: ").strip()
        if choice == "0":
            return
        action = actions.get(choice)
        if not action:
            print("Invalid choice.")
            continue
        try:
            action[1]()
        except Exception as exc:
            print(f"Error: {exc}")
