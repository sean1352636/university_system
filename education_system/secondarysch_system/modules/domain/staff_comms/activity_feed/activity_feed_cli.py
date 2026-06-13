"""CLI flows for Secondary School Activity Feed."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable
from education_system.secondarysch_system.modules.domain.staff_comms.activity_feed import (
    activity_feed as data,
)
from education_system.secondarysch_system.modules.domain.staff_comms.activity_feed.activity_feed import (
    ACTIONS,
    DEFAULT_SEVERITY,
    DEFAULT_SOURCE,
    Event,
    KNOWN_ENTITY_TYPES,
    SEVERITIES,
    SOURCES,
    ValidationError,
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
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _pick_from(label: str, options: list[str],
                default: str | None = None,
                allow_custom: bool = False) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    if allow_custom:
        print("        (or type a custom value)")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(options):
                return options[n - 1]
            print("    Out of range.")
            continue
        if allow_custom and raw:
            return raw
        print("    Enter a number (or 'cancel' to abort).")


# ── Print helpers ──────────────────────────────────────────────────

_SEV_GLYPH = {"info": "ℹ", "audit": "·", "warning": "⚠", "error": "✗"}


def _print_events(rows: list[Event]) -> None:
    if not rows:
        print("\n  (no events)")
        return
    print()
    print(f"  {'#':>5}  {'When':<19}  {'S':<1}  "
          f"{'Actor':<14}  {'Action':<14}  {'Entity':<22}  Summary")
    print("  " + "-" * 110)
    for e in rows:
        ent = f"{e.entity_type or '—'}#{e.entity_id}" if e.entity_id else (
            e.entity_type or "—")
        print(f"  {e.event_id:>5}  {e.ts[:19]:<19}  "
              f"{_SEV_GLYPH.get(e.severity, '·'):<1}  "
              f"{(e.actor or '—')[:14]:<14}  "
              f"{e.action[:14]:<14}  {ent[:22]:<22}  {e.summary[:60]}")
    print(f"\n  {len(rows)} event(s).")


# ── Flows ──────────────────────────────────────────────────────────

def recent_events() -> None:
    print("\n═══ Recent Activity ═══")
    try:
        n = int(_input("How many?", default="50"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    _print_events(data.recent(limit=n))
    _pause()


def filter_events() -> None:
    print("\n═══ Filter Activity ═══")
    print("  (blank to skip; 'cancel' to abort)\n")
    try:
        actor = _input("Actor (username)") or None
        actor_role = _input("Actor role") or None
        action = _input(f"Action ({'/'.join(ACTIONS)})") or None
        severity = _input(f"Severity ({'/'.join(SEVERITIES)})") or None
        source = _input(f"Source ({'/'.join(SOURCES)})") or None
        ent_type = _input("Entity type") or None
        ent_id = _input("Entity id") or None
        like = _input("Summary contains") or None
        date_from = _input("From (YYYY-MM-DD)") or None
        date_to = _input("To (YYYY-MM-DD)") or None
        limit_raw = _input("Limit", default="200")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        limit = int(limit_raw)
    except ValueError:
        print("  ✗ limit must be a number.")
        _pause()
        return
    try:
        rows = data.list_events(
            actor=actor, actor_role=actor_role, action=action,
            severity=severity, source=source,
            entity_type=ent_type, entity_id=ent_id,
            summary_like=like,
            date_from=date_from, date_to=date_to, limit=limit)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_events(rows)
    _pause()


def per_actor() -> None:
    print("\n═══ Per-Actor Activity ═══")
    try:
        actor = _input("Username", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_events(data.events_for_actor(actor))
    _pause()


def per_entity() -> None:
    print("\n═══ Per-Entity Activity ═══")
    try:
        ent_type = _input("Entity type", allow_empty=False)
        ent_id = _input("Entity id", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_events(data.events_for_entity(ent_type, ent_id))
    _pause()


def view_event() -> None:
    print("\n═══ View Event ═══")
    try:
        eid = int(_input("Event ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    e = data.get_event(eid)
    if e is None:
        print(f"  ✗ No event #{eid}")
        _pause()
        return
    print()
    print(f"    Event ID    : #{e.event_id}")
    print(f"    Timestamp   : {e.ts}")
    print(f"    Severity    : {e.severity}")
    print(f"    Source      : {e.source}")
    print(f"    Actor       : {e.actor or '—'} "
          f"({e.actor_role or '—'})")
    print(f"    IP address  : {e.ip_address or '—'}")
    print(f"    Action      : {e.action}")
    if e.entity_type or e.entity_id:
        ent = f"{e.entity_type or '—'}#{e.entity_id or '—'}"
        print(f"    Entity      : {ent}")
    print()
    print(f"    Summary:")
    for line in e.summary.splitlines() or [""]:
        print(f"      {line}")
    meta = e.metadata_dict
    if meta is not None:
        print()
        print(f"    Metadata:")
        for line in json.dumps(meta, indent=2).splitlines():
            print(f"      {line}")
    elif e.metadata:
        print()
        print(f"    Metadata (raw):")
        for line in e.metadata.splitlines():
            print(f"      {line}")
    _pause()


def new_event() -> None:
    print("\n═══ Log Event Manually ═══")
    try:
        action = _pick_from("Action", list(ACTIONS),
                              default="system", allow_custom=True)
        summary = _input("Summary", allow_empty=False)
        actor = _input("Actor (username)")
        actor_role = _input("Actor role")
        severity = _pick_from("Severity", list(SEVERITIES),
                                default=DEFAULT_SEVERITY)
        source = _pick_from("Source", list(SOURCES),
                              default="cli")
        ent_type = _pick_from(
            "Entity type", [""] + list(KNOWN_ENTITY_TYPES),
            default="", allow_custom=True)
        ent_id = _input("Entity id")
        meta_raw = _input("Metadata (JSON, optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    payload: dict[str, Any] = {
        "action": action, "summary": summary,
        "actor": actor or None, "actor_role": actor_role or None,
        "severity": severity, "source": source,
        "entity_type": ent_type or None,
        "entity_id": ent_id or None,
        "metadata": meta_raw or None,
    }
    try:
        ev = data.create_event(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Logged event #{ev.event_id}")
    _pause()


def delete_event_flow() -> None:
    print("\n═══ Delete Event ═══")
    try:
        eid = int(_input("Event ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_event(eid) is None:
        print(f"  ✗ No event #{eid}")
        _pause()
        return
    if _input(f"Delete event #{eid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_event(eid):
        print(f"\n  ✓ Deleted event #{eid}")
    _pause()


def purge_old() -> None:
    print("\n═══ Purge Old Events ═══")
    try:
        days = int(_input("Older than (days)", default="365"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if _input(f"Delete events older than {days} days? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    try:
        n = data.purge(older_than_days=days)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Removed {n} event(s)")
    _pause()


def summary_flow() -> None:
    print("\n═══ Activity Feed Summary ═══")
    summ = data.summary()
    print(f"\n  Total events       : {summ.total}")
    print(f"  Most recent        : {summ.most_recent_ts or '—'}")
    print(f"\n  Volume:")
    print(f"    Last 24 hours    : {summ.last_24h}")
    print(f"    Last 7 days      : {summ.last_7d}")
    print(f"    Last 30 days     : {summ.last_30d}")
    print(f"\n  By severity:")
    for s in SEVERITIES:
        print(f"    {s:<10} : {summ.by_severity.get(s, 0)}")
    print(f"\n  By source:")
    for s in SOURCES:
        n = summ.by_source.get(s, 0)
        if n:
            print(f"    {s:<10} : {n}")
    print(f"\n  Top actions:")
    for action, n in list(summ.by_action.items())[:10]:
        print(f"    {action:<16} : {n}")
    if summ.by_actor:
        print(f"\n  Top actors:")
        for actor, n in summ.by_actor.items():
            print(f"    {actor:<20} : {n}")
    if summ.by_entity_type:
        print(f"\n  By entity type:")
        for ent, n in summ.by_entity_type.items():
            print(f"    {ent:<22} : {n}")
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Recent",              recent_events),
    ("Filter",              filter_events),
    ("Per-Actor",           per_actor),
    ("Per-Entity",          per_entity),
    ("View Event",          view_event),
    ("Log Event",           new_event),
    ("Delete Event",        delete_event_flow),
    ("Purge Old",           purge_old),
    ("Summary",             summary_flow),
]


def run() -> None:
    while True:
        print("\n── Activity Feed ──")
        for i, (label, _) in enumerate(_MENU, 1):
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
        _, handler = _MENU[int(choice) - 1]
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Activity-feed CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Activity Feed":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Activity-feed CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
