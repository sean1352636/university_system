"""CLI flows for Secondary School Notifications."""

from __future__ import annotations

import logging
from datetime import datetime as _dt
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.staff_comms.notifications import (
    notifications as data,
)
from education_system.secondarysch_system.modules.domain.staff_comms.notifications.notifications import (
    CHANNELS,
    DEFAULT_CHANNEL,
    DEFAULT_NOTIFICATION_TYPE,
    DEFAULT_RECIPIENT_TYPE,
    DEFAULT_STATUS,
    Notification,
    NOTIFICATION_TYPES,
    PRIORITIES,
    RECIPIENT_TYPES,
    STATUSES,
    ValidationError,
    priority_label,
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


def _pick_notification() -> Notification:
    rows = data.list_notifications()
    if not rows:
        print("    No notifications yet.")
        raise _UserAbort
    print("\n  Notifications:")
    for i, n in enumerate(rows, 1):
        action = "!" if n.needs_action else " "
        read = "·" if n.is_read else "•"
        print(f"    {i:>3}){action}{read} #{n.notification_id}  "
              f"P{n.priority}  {n.recipient_type[:8]:<8} "
              f"{n.recipient_id[:10]:<10}  "
              f"{n.title[:32]:<32}  [{n.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            k = int(raw)
            if 1 <= k <= len(rows):
                return rows[k - 1]
            match = next((r for r in rows
                            if r.notification_id == k), None)
            if match:
                return match
        print("    No matching notification.")


def _print_table(rows: list[Notification]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4} ! R  P  {'Recipient':<22}  "
          f"{'Type':<14}  {'Channel':<10}  "
          f"{'Title':<32}  {'Sent at':<19}  Status")
    print("  " + "-" * 140)
    for n in rows:
        action = "!" if n.needs_action else " "
        read = "·" if n.is_read else "•"
        rcpt = f"{n.recipient_type[:8]}:{n.recipient_id[:12]}"
        print(f"  {n.notification_id:>4} {action} {read}  "
              f"{n.priority}  {rcpt[:22]:<22}  "
              f"{n.notification_type[:14]:<14}  "
              f"{n.channel[:10]:<10}  "
              f"{n.title[:32]:<32}  "
              f"{(n.sent_at or '—')[:19]:<19}  {n.status}")
    print(f"\n  {len(rows)} notification(s).")


def _print_full(n: Notification) -> None:
    print()
    print(f"    #{n.notification_id}  {n.title}")
    print(f"    Recipient        : {n.recipient_type} :: "
          f"{n.recipient_id}"
          + (f"  ({n.recipient_name})"
              if n.recipient_name else ""))
    print(f"    Type             : {n.notification_type}")
    print(f"    Channel          : {n.channel}")
    print(f"    Priority         : {n.priority}  "
          f"({n.priority_label})")
    print(f"    Status           : {n.status}")
    print(f"    Sent by          : {n.sent_by or '—'}")
    print(f"    Scheduled for    : {n.scheduled_for or '—'}")
    print(f"    Sent at          : {n.sent_at or '—'}")
    print(f"    Delivered at     : {n.delivered_at or '—'}")
    print(f"    Read at          : {n.read_at or '—'}")
    print(f"    Acknowledged at  : {n.acknowledged_at or '—'}")
    print(f"    Dismissed at     : {n.dismissed_at or '—'}")
    print(f"    Expires on       : {n.expires_on or '—'}"
          + ("  (EXPIRED)" if n.is_expired else ""))
    print(f"    Requires action  : "
          f"{'yes' if n.requires_action else 'no'}"
          + (f" — {n.action_label}"
              if n.action_label else "")
          + ("  (completed)" if n.action_completed else ""))
    if n.action_url:
        print(f"    Action URL       : {n.action_url}")
    if n.url:
        print(f"    URL              : {n.url}")
    if n.icon:
        print(f"    Icon             : {n.icon}")
    if n.linked_to:
        print(f"    Linked to        : {n.linked_to}")
    if n.body:
        print(f"\n    Body:")
        for line in n.body.splitlines():
            print(f"      {line}")
    if n.notes:
        print(f"\n    Notes:")
        for line in n.notes.splitlines():
            print(f"      {line}")


# ── Flows ────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Notifications ═══")
    _print_table(data.list_notifications())
    _pause()


def list_unread() -> None:
    print("\n═══ Unread ═══")
    _print_table(data.list_notifications(unread_only=True))
    _pause()


def list_needs_action() -> None:
    print("\n═══ Needs Action ═══")
    _print_table(data.list_notifications(needs_action_only=True))
    _pause()


def list_urgent() -> None:
    print("\n═══ Urgent (Priority ≥ 4, unread) ═══")
    _print_table(data.list_notifications(urgent_only=True))
    _pause()


def list_scheduled() -> None:
    print("\n═══ Scheduled / Draft ═══")
    _print_table(data.list_notifications(pending_only=True))
    _pause()


def list_for_recipient() -> None:
    print("\n═══ Notifications for a Recipient ═══")
    try:
        rt = _pick_from("Recipient type",
                          list(RECIPIENT_TYPES),
                          default=DEFAULT_RECIPIENT_TYPE)
        rid = _input("Recipient id", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_table(data.notifications_for(rt, rid))
    print(f"\n  Unread count for {rt}:{rid} = "
          f"{data.unread_count_for(rt, rid)}")
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        rt = _input(
            f"Recipient type ({'/'.join(RECIPIENT_TYPES[:3])}…)"
            ) or None
        nt = _input(
            f"Notification type "
            f"({'/'.join(NOTIFICATION_TYPES[:3])}…)") or None
        ch = _input(
            f"Channel ({'/'.join(CHANNELS[:3])}…)") or None
        status = _input(
            f"Status ({'/'.join(STATUSES[:3])}…)") or None
        pmin = _input("Min priority (1-5)") or None
        title = _input("Title contains") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    pri = (int(pmin) if pmin and pmin.isdigit() else None)
    try:
        rows = data.list_notifications(
            recipient_type=rt, notification_type=nt,
            channel=ch, status=status, priority_min=pri,
            title_like=title, date_from=df, date_to=dt2)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_table(rows)
    _pause()


def view_flow() -> None:
    print("\n═══ View Notification ═══")
    try:
        n = _pick_notification()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_full(n)
    _pause()


def _collect_form(existing: Notification | None
                       ) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["recipient_type"] = _pick_from(
        "Recipient type", list(RECIPIENT_TYPES),
        default=(existing.recipient_type if is_edit
                  else DEFAULT_RECIPIENT_TYPE))
    payload["recipient_id"] = _input(
        "Recipient id",
        default=(existing.recipient_id if is_edit else ""),
        allow_empty=False)
    payload["recipient_name"] = _input(
        "Recipient name",
        default=(existing.recipient_name or "")
        if is_edit else "")
    payload["title"] = _input(
        "Title",
        default=(existing.title if is_edit else ""),
        allow_empty=False)
    try:
        payload["body"] = _multiline(
            "Body",
            default=(existing.body or "") if is_edit else "")
    except _UserAbort:
        raise
    payload["notification_type"] = _pick_from(
        "Notification type", list(NOTIFICATION_TYPES),
        default=(existing.notification_type if is_edit
                  else DEFAULT_NOTIFICATION_TYPE))
    payload["channel"] = _pick_from(
        "Channel", list(CHANNELS),
        default=(existing.channel if is_edit
                  else DEFAULT_CHANNEL))
    payload["priority"] = _input(
        "Priority (1-5)",
        default=(str(existing.priority) if is_edit
                  else "2"))
    payload["icon"] = _input(
        "Icon",
        default=(existing.icon or "") if is_edit else "")
    payload["url"] = _input(
        "URL",
        default=(existing.url or "") if is_edit else "")
    payload["linked_to"] = _input(
        "Linked to",
        default=(existing.linked_to or "")
        if is_edit else "")
    payload["requires_action"] = _yes_no(
        "Requires action?",
        default=(existing.requires_action
                  if is_edit else False))
    if payload["requires_action"]:
        payload["action_label"] = _input(
            "Action label",
            default=(existing.action_label or "")
            if is_edit else "")
        payload["action_url"] = _input(
            "Action URL",
            default=(existing.action_url or "")
            if is_edit else "")
    payload["sent_by"] = _input(
        "Sent by",
        default=(existing.sent_by or "")
        if is_edit else "")
    payload["scheduled_for"] = _input(
        "Scheduled for (ISO datetime)",
        default=(existing.scheduled_for or "")
        if is_edit else "")
    payload["expires_on"] = _input(
        "Expires on (YYYY-MM-DD)",
        default=(existing.expires_on or "")
        if is_edit else "")
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_STATUS))
    try:
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "")
            if is_edit else "")
    except _UserAbort:
        raise
    return payload


def new_notification() -> None:
    print("\n═══ New Notification ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        n = data.create_notification(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created notification #{n.notification_id}")
    _pause()


def edit_notification() -> None:
    print("\n═══ Edit Notification ═══")
    try:
        n = _pick_notification()
        payload = _collect_form(n)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_notification(n.notification_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{n.notification_id}")
    _pause()


def schedule_flow() -> None:
    print("\n═══ Schedule Notification ═══")
    try:
        n = _pick_notification()
        when = _input("Scheduled for (ISO datetime)",
                        allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.schedule(n.notification_id, scheduled_for=when)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{n.notification_id} → Scheduled")
    _pause()


def mark_sent_flow() -> None:
    print("\n═══ Mark Sent ═══")
    try:
        n = _pick_notification()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.mark_sent(n.notification_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{n.notification_id} → Sent")
    _pause()


def mark_delivered_flow() -> None:
    print("\n═══ Mark Delivered ═══")
    try:
        n = _pick_notification()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.mark_delivered(n.notification_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{n.notification_id} → Delivered")
    _pause()


def mark_read_flow() -> None:
    print("\n═══ Mark Read ═══")
    try:
        n = _pick_notification()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.mark_read(n.notification_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{n.notification_id} → Read")
    _pause()


def acknowledge_flow() -> None:
    print("\n═══ Acknowledge ═══")
    try:
        n = _pick_notification()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.acknowledge(n.notification_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{n.notification_id} → Acknowledged")
    _pause()


def dismiss_flow() -> None:
    print("\n═══ Dismiss ═══")
    try:
        n = _pick_notification()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.dismiss(n.notification_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{n.notification_id} → Dismissed")
    _pause()


def mark_action_completed_flow() -> None:
    print("\n═══ Mark Action Completed ═══")
    try:
        n = _pick_notification()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.mark_action_completed(n.notification_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{n.notification_id} action completed")
    _pause()


def mark_failed_flow() -> None:
    print("\n═══ Mark Failed ═══")
    try:
        n = _pick_notification()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.mark_failed(n.notification_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{n.notification_id} → Failed")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        n = _pick_notification()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=n.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(n.notification_id, new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{n.notification_id} → {new_status}")
    _pause()


def auto_expire_flow() -> None:
    print("\n═══ Auto-expire ═══")
    k = data.auto_expire()
    print(f"\n  ✓ {k} notification(s) moved to Expired")
    _pause()


def broadcast_flow() -> None:
    print("\n═══ Broadcast ═══")
    try:
        rt = _pick_from("Recipient type",
                          list(RECIPIENT_TYPES),
                          default=DEFAULT_RECIPIENT_TYPE)
        ids_raw = _input(
            "Recipient ids (comma-separated)",
            allow_empty=False)
        title = _input("Title", allow_empty=False)
        body = _multiline("Body")
        nt = _pick_from(
            "Notification type", list(NOTIFICATION_TYPES),
            default=DEFAULT_NOTIFICATION_TYPE)
        ch = _pick_from(
            "Channel", list(CHANNELS),
            default=DEFAULT_CHANNEL)
        pri = _input("Priority (1-5)",
                      default="2")
        sent_by = _input("Sent by")
        status = _pick_from("Status", list(STATUSES),
                              default=DEFAULT_STATUS)
        expires = _input("Expires on (YYYY-MM-DD)")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    recipients = [(rt, rid.strip(), None)
                   for rid in ids_raw.split(",")
                   if rid.strip()]
    if not recipients:
        print("\n  ✗ No valid recipient ids.")
        _pause()
        return
    try:
        rows = data.broadcast(
            recipients=recipients,
            title=title, body=body or None,
            notification_type=nt, priority=int(pri),
            channel=ch, sent_by=sent_by or None,
            status=status, expires_on=expires or None)
    except (ValidationError, ValueError) as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Broadcast to {len(rows)} recipient(s).")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete ═══")
    try:
        n = _pick_notification()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete notification #{n.notification_id}? "
              "Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_notification(n.notification_id):
        print(f"\n  ✓ Deleted #{n.notification_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Notifications Summary ═══")
    s = data.summary()
    print(f"\n  Total                : {s.total}")
    print(f"  Unread               : {s.unread}")
    print(f"  Pending              : {s.pending}")
    print(f"  Sent / Active        : {s.sent}")
    print(f"  Scheduled            : {s.scheduled}")
    print(f"  Needs action         : {s.needs_action}")
    print(f"  Urgent unread        : {s.urgent_unread}")
    print(f"  Expired unprocessed  : {s.expired_unprocessed}")
    print(f"  Distinct recipients  : {s.distinct_recipients}")
    print("\n  By type:")
    for k in NOTIFICATION_TYPES:
        n = s.by_type.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By priority:")
    for p in PRIORITIES:
        n = s.by_priority.get(p, 0)
        if n:
            print(f"    {p}  {priority_label(p):<12}: {n}")
    print("\n  By channel:")
    for k in CHANNELS:
        n = s.by_channel.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    print("\n  By recipient type:")
    for k in RECIPIENT_TYPES:
        n = s.by_recipient_type.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",          list_all),
    ("Unread",            list_unread),
    ("Needs action",      list_needs_action),
    ("Urgent",            list_urgent),
    ("Scheduled/Drafts",  list_scheduled),
    ("For recipient",     list_for_recipient),
    ("Filter",            filter_flow),
    ("View",              view_flow),
    ("─" * 6,             lambda: None),
    ("New notification",  new_notification),
    ("Edit",              edit_notification),
    ("Schedule",          schedule_flow),
    ("Mark sent",         mark_sent_flow),
    ("Mark delivered",    mark_delivered_flow),
    ("Mark read",         mark_read_flow),
    ("Acknowledge",       acknowledge_flow),
    ("Dismiss",           dismiss_flow),
    ("Mark action done",  mark_action_completed_flow),
    ("Mark failed",       mark_failed_flow),
    ("Change status",     set_status_flow),
    ("Broadcast",         broadcast_flow),
    ("Auto-expire",       auto_expire_flow),
    ("Delete",            delete_flow),
    ("─" * 6,             lambda: None),
    ("Summary",           summary_flow),
]


def run() -> None:
    while True:
        print("\n── Notifications ──")
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
        if not choice.isdigit() or not (
                1 <= int(choice) <= len(_MENU)):
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
            logger.exception("Notifications CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Notifications":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Notifications CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
