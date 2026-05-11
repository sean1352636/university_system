"""CLI flows for Sixth Form Notices & Bulletins."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.sixthform_system.modules.domain.notices import notices
from education_system.sixthform_system.modules.domain.staff import staff as data
from education_system.sixthform_system.modules.domain.staff import staff as staff_data
from education_system.sixthform_system.modules.domain.notices.notices import (
    AUDIENCES,
    CATEGORIES,
    DEFAULT_AUDIENCE,
    DEFAULT_CATEGORY,
    DEFAULT_PRIORITY,
    DEFAULT_STATUS,
    Notice,
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
            print("    Enter a number (or 'cancel' to abort).")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _yes_no(prompt: str, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)", default="y" if default else "n")
    return raw.lower() in ("y", "yes")


def _read_body(default: str = "") -> str:
    print("\n  Body (single line — use the GUI for multi-line):")
    raw = _input("Body", default=default, allow_empty=False)
    return raw


# ── Print helpers ──────────────────────────────────────────────────

def _author_names() -> dict[str, str]:
    return {t.staff_id: t.full_name for t in staff_data.list_staff()}


def _print_rows(rows: list[Notice]) -> None:
    if not rows:
        print("\n  (no notices)")
        return
    authors = _author_names()
    print()
    print(f"  {'#':>4}  {'Status':<10}  {'Pri':<6}  P  {'Cat':<14}  "
          f"{'Aud':<22}  {'From':<10}  {'Until':<10}  "
          f"{'Views':>5}  Title")
    print("  " + "-" * 130)
    for n in rows:
        pinned = "★" if n.pinned else " "
        print(f"  {n.notice_id:>4}  {n.status:<10}  "
              f"{n.priority:<6}  {pinned}  {n.category[:14]:<14}  "
              f"{n.audience[:22]:<22}  "
              f"{(n.publish_from or '—'):<10}  "
              f"{(n.publish_until or '—'):<10}  "
              f"{n.view_count:>5}  {n.title[:50]}")
    print(f"\n  {len(rows)} notice(s).")


# ── Flows ──────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Notices ═══")
    _print_rows(data.list_notices())
    _row_action_loop()


def list_visible() -> None:
    print("\n═══ Currently Visible ═══")
    _print_rows(data.list_notices(active_on=_date.today().isoformat()))
    _row_action_loop()


def list_drafts() -> None:
    print("\n═══ Draft Notices ═══")
    _print_rows(data.list_notices(status="Draft"))
    _row_action_loop()


def list_archived() -> None:
    print("\n═══ Archived Notices ═══")
    _print_rows(data.list_notices(status="Archived"))
    _row_action_loop()


def filter_notices() -> None:
    print("\n═══ Filter Notices ═══")
    print("  (blank to skip; 'cancel' to abort)\n")
    try:
        cat = _input("Category") or None
        aud = _input("Audience") or None
        pri = _input(f"Priority ({'/'.join(PRIORITIES)})") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        author = _input("Author staff ID") or None
        pinned = _yes_no("Pinned only?", default=False)
        active = _yes_no("Visible today only?", default=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_notices(
            category=cat, audience=aud, priority=pri, status=status,
            author_staff_id=author, pinned_only=pinned,
            active_on=_date.today().isoformat() if active else None,
        )
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_rows(rows)
    _row_action_loop()


def feed_for_audience() -> None:
    print("\n═══ Feed for Audience ═══")
    try:
        aud = _pick_from("Audience", list(AUDIENCES),
                            default=DEFAULT_AUDIENCE)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.feed(aud)
    print(f"\n  Notices visible today for: {aud}")
    _print_rows(rows)
    _row_action_loop()


def search_notices() -> None:
    print("\n═══ Search Notices ═══")
    try:
        q = _input("Query", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_rows(data.search_notices(q))
    _row_action_loop()


def view_notice(notice_id: int | None = None) -> None:
    print("\n═══ View Notice ═══")
    try:
        nid = notice_id if notice_id is not None else int(
            _input("Notice ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    n = data.get_notice(nid)
    if n is None:
        print(f"  ✗ No notice #{nid}")
        _pause()
        return
    data.increment_view(nid)
    authors = _author_names()
    print()
    print(f"    Notice ID    : #{n.notice_id}")
    print(f"    Title        : {n.title}")
    print(f"    Status       : {n.status}  "
          f"{'(★ pinned)' if n.pinned else ''}")
    print(f"    Category     : {n.category}")
    print(f"    Audience     : {n.audience}")
    print(f"    Priority     : {n.priority}")
    print(f"    Author       : "
          f"{authors.get(n.author_staff_id, n.author_staff_id or '—')}")
    print(f"    Publish from : {n.publish_from or '—'}")
    print(f"    Publish until: {n.publish_until or '—'}")
    print(f"    Visible today: "
          f"{'Yes' if n.is_visible_today else 'No'}")
    print(f"    Views        : {n.view_count + 1}")
    if n.attachments_note:
        print(f"    Attachments  : {n.attachments_note}")
    print()
    print("    Body:")
    for line in (n.body.splitlines() or [""]):
        print(f"      {line}")
    _pause()


def _collect_form(existing: Notice | None) -> dict[str, Any]:
    is_edit = existing is not None
    p: dict[str, Any] = {}
    p["title"] = _input(
        "Title",
        default=existing.title if is_edit else "",
        allow_empty=False)
    p["body"] = _read_body(default=existing.body if is_edit else "")
    p["category"] = _pick_from(
        "Category", list(CATEGORIES),
        default=(existing.category if is_edit else DEFAULT_CATEGORY))
    p["audience"] = _pick_from(
        "Audience", list(AUDIENCES),
        default=(existing.audience if is_edit else DEFAULT_AUDIENCE))
    p["priority"] = _pick_from(
        "Priority", list(PRIORITIES),
        default=(existing.priority if is_edit else DEFAULT_PRIORITY))
    p["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    p["author_staff_id"] = _input(
        "Author staff ID (optional)",
        default=(existing.author_staff_id or "") if is_edit else "")
    p["publish_from"] = _input(
        "Publish from (YYYY-MM-DD)",
        default=(existing.publish_from or "") if is_edit
        else (_date.today().isoformat()
              if p["status"] == "Published" else ""))
    p["publish_until"] = _input(
        "Publish until (YYYY-MM-DD, blank=never)",
        default=(existing.publish_until or "") if is_edit else "")
    p["pinned"] = _yes_no(
        "Pinned?", default=existing.pinned if is_edit else False)
    p["attachments_note"] = _input(
        "Attachments note (optional)",
        default=(existing.attachments_note or "") if is_edit else "")
    return p


def new_notice() -> None:
    print("\n═══ New Notice ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        n = data.create_notice(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created notice #{n.notice_id} ({n.title})")
    _pause()


def edit_notice(notice_id: int | None = None) -> None:
    print("\n═══ Edit Notice ═══")
    try:
        nid = notice_id if notice_id is not None else int(
            _input("Notice ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_notice(nid)
    if existing is None:
        print(f"  ✗ No notice #{nid}")
        _pause()
        return
    try:
        payload = _collect_form(existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_notice(nid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{nid}")
    _pause()


def publish_flow(notice_id: int | None = None) -> None:
    print("\n═══ Publish Notice ═══")
    try:
        nid = notice_id if notice_id is not None else int(
            _input("Notice ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_notice(nid)
    if existing is None:
        print(f"  ✗ No notice #{nid}")
        _pause()
        return
    try:
        pf = _input("Publish from (YYYY-MM-DD)",
                     default=existing.publish_from
                            or _date.today().isoformat(),
                     allow_empty=False)
        pu = _input("Publish until (blank = never)",
                     default=existing.publish_until or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.publish(nid, publish_from=pf, publish_until=pu)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Published #{nid}")
    _pause()


def archive_flow(notice_id: int | None = None) -> None:
    print("\n═══ Archive Notice ═══")
    try:
        nid = notice_id if notice_id is not None else int(
            _input("Notice ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_notice(nid) is None:
        print(f"  ✗ No notice #{nid}")
        _pause()
        return
    try:
        data.archive(nid)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Archived #{nid}")
    _pause()


def toggle_pin_flow(notice_id: int | None = None) -> None:
    print("\n═══ Toggle Pin ═══")
    try:
        nid = notice_id if notice_id is not None else int(
            _input("Notice ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_notice(nid)
    if existing is None:
        print(f"  ✗ No notice #{nid}")
        _pause()
        return
    new_state = not existing.pinned
    try:
        data.set_pinned(nid, new_state)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{nid} pinned = {new_state}")
    _pause()


def delete_notice_flow(notice_id: int | None = None) -> None:
    print("\n═══ Delete Notice ═══")
    try:
        nid = notice_id if notice_id is not None else int(
            _input("Notice ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_notice(nid)
    if existing is None:
        print(f"  ✗ No notice #{nid}")
        _pause()
        return
    if _input(f"Delete notice #{nid} ({existing.title!r})? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_notice(nid):
        print(f"\n  ✓ Deleted #{nid}")
    _pause()


def auto_archive_flow() -> None:
    print("\n═══ Auto-Archive Expired ═══")
    n = data.auto_archive_expired()
    print(f"\n  Archived {n} expired notice(s).")
    _pause()


def summary() -> None:
    print("\n═══ Notices Summary ═══")
    try:
        window = int(_input("Expiring-window (days)", default="7"))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    summ = data.summary(expiring_window_days=window)
    print(f"\n  Total       : {summ.total}")
    print(f"  Drafts      : {summ.drafts}")
    print(f"  Published   : {summ.published}")
    print(f"  Archived    : {summ.archived}")
    print(f"\n  Right now:")
    print(f"    Visible today  : {summ.visible_today}")
    print(f"    Pinned visible : {summ.pinned}")
    print(f"    Urgent visible : {summ.urgent_visible}")
    print(f"    Expiring in {window}d: {summ.expiring_within}")
    print("\n  By category:")
    for c in CATEGORIES:
        n = summ.by_category.get(c, 0)
        if n:
            print(f"    {c:<22} : {n}")
    print("\n  By audience:")
    for a in AUDIENCES:
        n = summ.by_audience.get(a, 0)
        if n:
            print(f"    {a:<22} : {n}")
    print("\n  By priority:")
    for p in PRIORITIES:
        print(f"    {p:<10} : {summ.by_priority.get(p, 0)}")
    if summ.top_viewed:
        print("\n  Top viewed:")
        for nid, title, views in summ.top_viewed:
            print(f"    #{nid:<4}  {views:>4} views  {title[:60]}")
    _pause()


# ── Row-action loop ───────────────────────────────────────────────

def _row_action_loop() -> None:
    print()
    print("  Actions:  V) View   E) Edit   P) Publish   A) Archive   "
          "T) Toggle pin   D) Delete   (Enter to go back)")
    while True:
        try:
            choice = input("  Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not choice:
            return
        if choice not in ("v", "e", "p", "a", "t", "d"):
            print("    Pick V, E, P, A, T, D, or Enter.")
            continue
        try:
            raw = _input("Notice ID", allow_empty=False)
        except _UserAbort:
            return
        try:
            nid = int(raw)
        except ValueError:
            print("    Notice ID must be a whole number.")
            continue
        if choice == "v":
            view_notice(nid)
        elif choice == "e":
            edit_notice(nid)
        elif choice == "p":
            publish_flow(nid)
        elif choice == "a":
            archive_flow(nid)
        elif choice == "t":
            toggle_pin_flow(nid)
        elif choice == "d":
            delete_notice_flow(nid)
        return


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Currently Visible",   list_visible),
    ("All Notices",         list_all),
    ("Drafts",              list_drafts),
    ("Archived",            list_archived),
    ("Filter",              filter_notices),
    ("Feed for Audience",   feed_for_audience),
    ("Search",              search_notices),
    ("View Notice",         view_notice),
    ("New Notice",          new_notice),
    ("Edit Notice",         edit_notice),
    ("Publish",             publish_flow),
    ("Archive",             archive_flow),
    ("Toggle Pin",          toggle_pin_flow),
    ("Delete Notice",       delete_notice_flow),
    ("Auto-Archive Expired", auto_archive_flow),
    ("Summary",             summary),
]


def run() -> None:
    while True:
        print("\n── Notices & Bulletins ──")
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
            logger.exception("Notices CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Notices & Bulletins":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Notices CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
