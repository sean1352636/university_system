"""CLI flows for Sixth Form Email / Messaging."""

from __future__ import annotations

import logging
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.staff_comms.messages import messages
from education_system.sixthform_system.modules.domain.staff_comms.parent_contacts import parent_contacts
from education_system.sixthform_system.modules.domain.staff_comms.staff import staff
from education_system.sixthform_system.modules.domain.staff_comms.messages import messages as data
from education_system.sixthform_system.modules.domain.staff_comms.parent_contacts import parent_contacts as pc_data
from education_system.sixthform_system.modules.domain.staff_comms.staff import staff as staff_data
from education_system.sixthform_system.modules.domain.students.students import students as student_data
from education_system.sixthform_system.modules.domain.staff_comms.messages.messages import (
    CATEGORIES,
    CHANNELS,
    DEFAULT_CATEGORY,
    DEFAULT_CHANNEL,
    DEFAULT_PRIORITY,
    DEFAULT_STATUS,
    DIRECTIONS,
    Message,
    PRIORITIES,
    STATUSES,
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
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}", default=default or "")
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


def _yes_no(prompt: str, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)", default="y" if default else "n")
    return raw.lower() in ("y", "yes")


def _pick_student_optional() -> str | None:
    students = student_data.list_students()
    if not students:
        return None
    print("\n  Students (Enter to skip):")
    for i, s in enumerate(students, 1):
        print(f"    {i:>3}) {s.student_id}  {s.full_name}")
    raw = _input("Pick # or student ID (blank=skip)")
    if not raw:
        return None
    if raw.isdigit():
        n = int(raw)
        if 1 <= n <= len(students):
            return students[n - 1].student_id
    m = next((s for s in students
               if s.student_id.lower() == raw.lower()), None)
    return m.student_id if m else None


def _pick_staff_optional() -> str | None:
    staff = staff_data.list_staff(active_only=True)
    if not staff:
        return None
    print("\n  Staff (Enter to skip):")
    for i, t in enumerate(staff, 1):
        print(f"    {i:>3}) {t.staff_id}  {t.full_name} ({t.role})")
    raw = _input("Pick # or staff ID (blank=skip)")
    if not raw:
        return None
    if raw.isdigit():
        n = int(raw)
        if 1 <= n <= len(staff):
            return staff[n - 1].staff_id
    m = next((t for t in staff
               if t.staff_id.lower() == raw.lower()), None)
    return m.staff_id if m else None


# ── Print helpers ──────────────────────────────────────────────────

def _print_rows(rows: list[Message]) -> None:
    if not rows:
        print("\n  (no messages)")
        return
    print()
    print(f"  {'#':>4}  {'Dir':<3}  {'Channel':<10}  {'Status':<10}  "
          f"{'Pri':<6}  {'When':<19}  {'Student':<10}  "
          f"{'To':<22}  Subject")
    print("  " + "-" * 130)
    for m in rows:
        when = m.sent_at or m.received_at or m.created_at
        dir_short = "OUT" if m.direction == "Outgoing" else "IN"
        print(f"  {m.message_id:>4}  {dir_short:<3}  {m.channel[:10]:<10}  "
              f"{m.status:<10}  {m.priority:<6}  "
              f"{(when or '—')[:19]:<19}  "
              f"{(m.student_id or '—'):<10}  "
              f"{(m.to_name or '—')[:22]:<22}  "
              f"{m.subject[:50]}")
    print(f"\n  {len(rows)} message(s).")


def _print_threads(rows: list[data.Thread]) -> None:
    if not rows:
        print("\n  (no threads)")
        return
    print()
    print(f"  {'Thread':<14}  {'Msgs':>4}  {'Last at':<19}  "
          f"{'Last':<10}  Subject")
    print("  " + "-" * 100)
    for t in rows:
        print(f"  {t.thread_id:<14}  {t.message_count:>4}  "
              f"{(t.last_at or '')[:19]:<19}  "
              f"{t.last_status:<10}  {t.subject[:50]}")
    print(f"\n  {len(rows)} thread(s).")


# ── Flows ──────────────────────────────────────────────────────────

def inbox() -> None:
    print("\n═══ Inbox (Incoming) ═══")
    _print_rows(data.list_messages(direction="Incoming"))
    _row_action_loop()


def outbox() -> None:
    print("\n═══ Outbox (Outgoing — sent) ═══")
    _print_rows(data.list_messages(direction="Outgoing", sent_only=True))
    _row_action_loop()


def drafts() -> None:
    print("\n═══ Drafts ═══")
    _print_rows(data.list_messages(drafts_only=True))
    _row_action_loop()


def queued() -> None:
    print("\n═══ Queued ═══")
    _print_rows(data.list_messages(status="Queued"))
    _row_action_loop()


def list_all() -> None:
    print("\n═══ All Messages ═══")
    _print_rows(data.list_messages())
    _row_action_loop()


def filter_messages() -> None:
    print("\n═══ Filter Messages ═══")
    print("  (blank to skip; 'cancel' to abort)\n")
    try:
        d = _input(f"Direction ({'/'.join(DIRECTIONS)})") or None
        ch = _input(f"Channel") or None
        cat = _input("Category") or None
        st = _input(f"Status ({'/'.join(STATUSES)})") or None
        sid = _input("Student ID") or None
        stid = _input("Staff ID") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_messages(
            direction=d, channel=ch, category=cat, status=st,
            student_id=sid, staff_id=stid)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_rows(rows)
    _row_action_loop()


def search_messages() -> None:
    print("\n═══ Search Messages ═══")
    try:
        q = _input("Query", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_rows(data.search_messages(q))
    _row_action_loop()


def list_threads_flow() -> None:
    print("\n═══ Threads ═══")
    _print_threads(data.list_threads())
    try:
        tid = _input("Open thread (thread ID, blank=back)")
    except _UserAbort:
        return
    if not tid:
        return
    rows = data.thread(tid)
    if not rows:
        print(f"  ✗ No thread {tid}")
        _pause()
        return
    print(f"\n  Thread {tid}  ({len(rows)} message(s))")
    _print_rows(rows)
    _row_action_loop()


def per_student() -> None:
    print("\n═══ Per-Student Messages ═══")
    sid = _pick_student_optional()
    if sid is None:
        print("\n  Cancelled.")
        return
    s = student_data.get_student(sid)
    print(f"\n  {s.student_id}  {s.full_name}")
    _print_rows(data.list_messages(student_id=sid))
    _row_action_loop()


def view_message(message_id: int | None = None) -> None:
    print("\n═══ View Message ═══")
    try:
        mid = message_id if message_id is not None else int(
            _input("Message ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    m = data.get_message(mid)
    if m is None:
        print(f"  ✗ No message #{mid}")
        _pause()
        return
    print()
    print(f"    Message ID   : #{m.message_id}")
    print(f"    Thread       : {m.thread_id}"
          + (f"  (reply to #{m.reply_to_message_id})"
              if m.reply_to_message_id else ""))
    print(f"    Direction    : {m.direction}")
    print(f"    Channel      : {m.channel}")
    print(f"    Category     : {m.category}")
    print(f"    Priority     : {m.priority}")
    print(f"    Status       : {m.status}")
    print(f"    Subject      : {m.subject}")
    print(f"    From         : "
          f"{m.from_name or '—'}  <{m.from_address or '—'}>")
    print(f"    To           : "
          f"{m.to_name or '—'}  <{m.to_address or '—'}>")
    if m.cc_address:
        print(f"    CC           : {m.cc_address}")
    print(f"    Student      : {m.student_id or '—'}")
    print(f"    Staff        : {m.staff_id or '—'}")
    print(f"    Sent at      : {m.sent_at or '—'}")
    print(f"    Received at  : {m.received_at or '—'}")
    if m.tags:
        print(f"    Tags         : {m.tags}")
    if m.attachments_note:
        print(f"    Attachments  : {m.attachments_note}")
    print()
    print("    Body:")
    for line in (m.body.splitlines() or [""]):
        print(f"      {line}")
    if m.notes:
        print("\n    Notes:")
        for line in m.notes.splitlines() or [""]:
            print(f"      {line}")
    _pause()


def _collect_form(existing: Message | None) -> dict[str, Any]:
    is_edit = existing is not None
    p: dict[str, Any] = {}
    p["direction"] = _pick_from(
        "Direction", list(DIRECTIONS),
        default=existing.direction if is_edit else "Outgoing")
    p["channel"] = _pick_from(
        "Channel", list(CHANNELS),
        default=existing.channel if is_edit else DEFAULT_CHANNEL)
    p["category"] = _pick_from(
        "Category", list(CATEGORIES),
        default=existing.category if is_edit else DEFAULT_CATEGORY)
    p["priority"] = _pick_from(
        "Priority", list(PRIORITIES),
        default=existing.priority if is_edit else DEFAULT_PRIORITY)
    p["status"] = _pick_from(
        "Status", list(STATUSES),
        default=existing.status if is_edit else DEFAULT_STATUS)
    p["subject"] = _input(
        "Subject", default=existing.subject if is_edit else "",
        allow_empty=False)
    print("\n  Body (single line — use the GUI for multi-line):")
    p["body"] = _input(
        "Body", default=existing.body if is_edit else "",
        allow_empty=False)
    p["from_name"] = _input(
        "From name",
        default=(existing.from_name or "") if is_edit else "")
    p["from_address"] = _input(
        "From address",
        default=(existing.from_address or "") if is_edit else "")
    p["to_name"] = _input(
        "To name",
        default=(existing.to_name or "") if is_edit else "")
    p["to_address"] = _input(
        "To address",
        default=(existing.to_address or "") if is_edit else "")
    p["cc_address"] = _input(
        "CC",
        default=(existing.cc_address or "") if is_edit else "")

    if is_edit:
        p["student_id"] = existing.student_id or ""
        p["staff_id"]   = existing.staff_id or ""
    else:
        print("\n  Link to a student (optional):")
        p["student_id"] = _pick_student_optional() or ""
        print("\n  Link to a staff member (optional):")
        p["staff_id"] = _pick_staff_optional() or ""

    p["sent_at"] = _input(
        "Sent at (YYYY-MM-DD HH:MM, optional)",
        default=(existing.sent_at or "") if is_edit else "")
    p["received_at"] = _input(
        "Received at (optional)",
        default=(existing.received_at or "") if is_edit else "")
    p["attachments_note"] = _input(
        "Attachments note (optional)",
        default=(existing.attachments_note or "") if is_edit else "")
    p["tags"] = _input(
        "Tags (comma-separated)",
        default=(existing.tags or "") if is_edit else "")
    p["notes"] = _input(
        "Notes (optional)",
        default=(existing.notes or "") if is_edit else "")
    return p


def new_message() -> None:
    print("\n═══ New Message ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        m = data.create_message(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created message #{m.message_id} (thread {m.thread_id})")
    _pause()


def edit_message(message_id: int | None = None) -> None:
    print("\n═══ Edit Message ═══")
    try:
        mid = message_id if message_id is not None else int(
            _input("Message ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_message(mid)
    if existing is None:
        print(f"  ✗ No message #{mid}")
        _pause()
        return
    try:
        payload = _collect_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_message(mid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{mid}")
    _pause()


def send_message_flow(message_id: int | None = None) -> None:
    print("\n═══ Send Message ═══")
    try:
        mid = message_id if message_id is not None else int(
            _input("Message ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    try:
        m = data.send_message(mid)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Sent #{m.message_id} at {m.sent_at}")
    _pause()


def reply_flow(message_id: int | None = None) -> None:
    print("\n═══ Reply ═══")
    try:
        mid = message_id if message_id is not None else int(
            _input("Reply to message ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    parent = data.get_message(mid)
    if parent is None:
        print(f"  ✗ No message #{mid}")
        _pause()
        return
    try:
        subject = _input("Subject",
                          default=("Re: " + parent.subject
                                   if not parent.subject.startswith("Re:")
                                   else parent.subject),
                          allow_empty=False)
        body = _input("Body", allow_empty=False)
        status = _pick_from("Status", list(STATUSES),
                              default=DEFAULT_STATUS)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        m = data.reply(mid, {"subject": subject, "body": body,
                              "status": status})
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created reply #{m.message_id} in thread {m.thread_id}")
    _pause()


def set_status_flow(message_id: int | None = None) -> None:
    print("\n═══ Change Status ═══")
    try:
        mid = message_id if message_id is not None else int(
            _input("Message ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_message(mid)
    if existing is None:
        print(f"  ✗ No message #{mid}")
        _pause()
        return
    try:
        new_status = _pick_from("New status", list(STATUSES),
                                  default=existing.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(mid, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{mid} → {new_status}")
    _pause()


def delete_message_flow(message_id: int | None = None) -> None:
    print("\n═══ Delete Message ═══")
    try:
        mid = message_id if message_id is not None else int(
            _input("Message ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_message(mid)
    if existing is None:
        print(f"  ✗ No message #{mid}")
        _pause()
        return
    if _input(f"Delete message #{mid} ({existing.subject!r})? "
              f"Type 'yes'", default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_message(mid):
        print(f"\n  ✓ Deleted #{mid}")
    _pause()


def bulk_send_flow() -> None:
    print("\n═══ Bulk Send ═══")
    print("  Sends one message per recipient, all sharing a thread.")
    try:
        target = _pick_from(
            "Recipient type",
            ["Students", "Parent contacts (all)",
             "Parent contacts (primary)", "All active staff"])
        subject = _input("Subject", allow_empty=False)
        body = _input("Body (single line)", allow_empty=False)
        channel = _pick_from("Channel", list(CHANNELS),
                               default=DEFAULT_CHANNEL)
        category = _pick_from("Category", list(CATEGORIES),
                                default=DEFAULT_CATEGORY)
        priority = _pick_from("Priority", list(PRIORITIES),
                                default=DEFAULT_PRIORITY)
        immediate = _yes_no("Mark all as Sent now?", default=True)
        sender = _pick_staff_optional()
        tags = _input("Tags (comma-separated, optional)")
    except _UserAbort:
        print("\n  Cancelled.")
        return

    student_ids: list[str] = []
    contact_ids: list[int] = []
    staff_ids: list[str] = []
    if target == "Students":
        student_ids = [s.student_id for s in student_data.list_students()]
    elif target == "Parent contacts (all)":
        contact_ids = [c.contact_id for c in pc_data.list_contacts()]
    elif target == "Parent contacts (primary)":
        contact_ids = [c.contact_id
                        for c in pc_data.list_contacts(primary_only=True)]
    elif target == "All active staff":
        staff_ids = [t.staff_id
                      for t in staff_data.list_staff(active_only=True)]
    if not (student_ids or contact_ids or staff_ids):
        print("  ✗ No recipients matched.")
        _pause()
        return
    try:
        result = data.bulk_send(
            subject=subject, body=body,
            student_ids=student_ids, contact_ids=contact_ids,
            staff_ids=staff_ids,
            channel=channel, category=category, priority=priority,
            status="Sent" if immediate else "Draft",
            sender_staff_id=sender,
            tags=tags or None,
        )
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Thread {result.thread_id}: "
          f"{len(result.created)} created, "
          f"{len(result.failed)} failed.")
    for label, reason in result.failed[:10]:
        print(f"    ✗ {label}: {reason}")
    _pause()


def summary() -> None:
    print("\n═══ Messages Summary ═══")
    summ = data.summary()
    print(f"\n  Total      : {summ.total}")
    print(f"  Drafts     : {summ.drafts}")
    print(f"  Queued     : {summ.queued}")
    print(f"  Sent       : {summ.sent}")
    print(f"  Failed     : {summ.failed}")
    print(f"  Incoming   : {summ.incoming}")
    print(f"  Outgoing   : {summ.outgoing}")
    print(f"  Threads    : {summ.threads}")
    print("\n  By channel:")
    for c in CHANNELS:
        n = summ.by_channel.get(c, 0)
        if n:
            print(f"    {c:<18} : {n}")
    print("\n  By category:")
    for c in CATEGORIES:
        n = summ.by_category.get(c, 0)
        if n:
            print(f"    {c:<22} : {n}")
    print("\n  By status:")
    for s in STATUSES:
        n = summ.by_status.get(s, 0)
        if n:
            print(f"    {s:<14} : {n}")
    print("\n  By priority:")
    for p in PRIORITIES:
        print(f"    {p:<8} : {summ.by_priority.get(p, 0)}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop() -> None:
    print()
    print("  Actions:  V) View   E) Edit   S) Send   R) Reply   "
          "T) Status   D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "s", "r", "t", "d"):
            print("    Pick V, E, S, R, T, D, or Enter.")
            continue
        try:
            raw = _input("Message ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            mid = int(raw)
        except ValueError:
            print("    Message ID must be a whole number.")
            continue
        if choice == "v":
            view_message(mid)
        elif choice == "e":
            edit_message(mid)
        elif choice == "s":
            send_message_flow(mid)
        elif choice == "r":
            reply_flow(mid)
        elif choice == "t":
            set_status_flow(mid)
        elif choice == "d":
            delete_message_flow(mid)
        return


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Inbox",              inbox),
    ("Outbox (Sent)",      outbox),
    ("Drafts",             drafts),
    ("Queued",             queued),
    ("All Messages",       list_all),
    ("Filter",             filter_messages),
    ("Search",             search_messages),
    ("Threads",            list_threads_flow),
    ("Per-Student",        per_student),
    ("View Message",       view_message),
    ("New Message",        new_message),
    ("Edit Message",       edit_message),
    ("Send",               send_message_flow),
    ("Reply",              reply_flow),
    ("Change Status",      set_status_flow),
    ("Delete Message",     delete_message_flow),
    ("Bulk Send",          bulk_send_flow),
    ("Summary",            summary),
]


def run() -> None:
    while True:
        print("\n── Email / Messaging ──")
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
            logger.exception("Messages CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Email / Messaging":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Messages CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
