"""CLI flows for Secondary School Announcements."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.secondarysch_system.modules.domain.staff_comms.announcements import (
    announcements as data,
)
from education_system.secondarysch_system.modules.domain.staff_comms.announcements.announcements import (
    AUDIENCES,
    Announcement,
    CATEGORIES,
    DEFAULT_AUDIENCES,
    DEFAULT_CATEGORY,
    DEFAULT_STATUS,
    PRIORITIES,
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


def _pick_audiences(default: list[str]) -> list[str]:
    print("\n  Audiences (enter numbers comma-separated, "
          "blank to keep):")
    for i, a in enumerate(AUDIENCES, 1):
        marker = "*" if a in default else " "
        print(f"    {marker} {i:>2}) {a}")
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
            if 1 <= n <= len(AUDIENCES):
                picks.append(AUDIENCES[n - 1])
    return picks or list(default)


def _pick_announcement() -> Announcement:
    rows = data.list_announcements()
    if not rows:
        print("    No announcements yet.")
        raise _UserAbort
    print("\n  Announcements:")
    for i, a in enumerate(rows, 1):
        flag = "★" if a.pinned else " "
        ban = "[B]" if a.banner else "   "
        print(f"    {i:>3}){flag}{ban} #{a.announcement_id}  "
              f"{a.category[:14]:<14}  P{a.priority}  "
              f"{a.title[:36]:<36}  [{a.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.announcement_id == n), None)
            if match:
                return match
        print("    No matching announcement.")


def _print_table(rows: list[Announcement]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  Pin Ban  {'Category':<18}  P  "
          f"{'Title':<32}  {'Audiences':<22}  "
          f"{'Publish':<10}  {'Expires':<10}  "
          f"{'Status':<12}  Views")
    print("  " + "-" * 140)
    for a in rows:
        pin = "★" if a.pinned else "·"
        ban = "B" if a.banner else "·"
        print(f"  {a.announcement_id:>4}   {pin}   {ban}   "
              f"{a.category[:18]:<18}  "
              f"{a.priority}  "
              f"{a.title[:32]:<32}  "
              f"{','.join(a.audience_list)[:22]:<22}  "
              f"{(a.publish_on or '—'):<10}  "
              f"{(a.expires_on or '—'):<10}  "
              f"{a.status:<12}  {a.view_count:>5}")
    print(f"\n  {len(rows)} announcement(s).")


def _print_full(a: Announcement) -> None:
    print()
    print(f"    #{a.announcement_id}  {a.title}")
    print(f"    Category         : {a.category}")
    print(f"    Priority         : {a.priority}  "
          f"({a.priority_label})")
    print(f"    Audiences        : "
          f"{', '.join(a.audience_list)}")
    print(f"    Pinned / Banner  : "
          f"{'yes' if a.pinned else 'no'} / "
          f"{'yes' if a.banner else 'no'}")
    print(f"    Author           : {a.author or '—'}")
    print(f"    Publish on       : {a.publish_on or '—'}")
    print(f"    Expires on       : {a.expires_on or '—'}"
          + ("  (EXPIRED)" if a.is_expired else ""))
    print(f"    Published on     : {a.published_on or '—'}")
    print(f"    Status           : {a.status}")
    print(f"    Live now?        : "
          f"{'yes' if a.is_live else 'no'}")
    print(f"    Requires ack.    : "
          f"{'yes' if a.requires_acknowledgement else 'no'}")
    print(f"    Comments enabled : "
          f"{'yes' if a.comments_enabled else 'no'}")
    print(f"    Views            : {a.view_count}")
    print(f"    Attachments      : {a.attachments_ref or '—'}")
    print(f"    Linked to        : {a.linked_to or '—'}")
    if a.summary:
        print("\n    Summary:")
        for line in a.summary.splitlines():
            print(f"      {line}")
    if a.body:
        print("\n    Body:")
        for line in a.body.splitlines():
            print(f"      {line}")
    if a.notes:
        print("\n    Notes:")
        for line in a.notes.splitlines():
            print(f"      {line}")


# ── Flows ────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Announcements ═══")
    _print_table(data.list_announcements())
    _pause()


def list_live() -> None:
    print("\n═══ Live Now ═══")
    _print_table(data.list_announcements(live_only=True))
    _pause()


def list_scheduled() -> None:
    print("\n═══ Scheduled ═══")
    _print_table(data.list_announcements(scheduled_only=True))
    _pause()


def list_pinned() -> None:
    print("\n═══ Pinned ═══")
    _print_table(data.list_announcements(pinned_only=True))
    _pause()


def list_banners() -> None:
    print("\n═══ Banner Announcements ═══")
    _print_table(data.list_announcements(banner_only=True))
    _pause()


def list_expired() -> None:
    print("\n═══ Expired (Unarchived) ═══")
    _print_table(data.list_announcements(
        expired_unarchived=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        cat = _input(
            f"Category ({'/'.join(CATEGORIES[:3])}…)") or None
        status = _input(
            f"Status ({'/'.join(STATUSES[:3])}…)") or None
        pri_raw = _input("Min priority (1-5)") or None
        aud = _input(f"Audience ({'/'.join(AUDIENCES[:3])}…)") or None
        author = _input("Author contains") or None
        title = _input("Title contains") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    pri = (int(pri_raw) if pri_raw and pri_raw.isdigit() else None)
    try:
        rows = data.list_announcements(
            category=cat, status=status,
            priority_min=pri, audience=aud,
            author_like=author, title_like=title,
            date_from=df, date_to=dt2)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_table(rows)
    _pause()


def view_flow() -> None:
    print("\n═══ View Announcement ═══")
    try:
        a = _pick_announcement()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_full(a)
    data.increment_views(a.announcement_id, 1)
    _pause()


def _collect_form(existing: Announcement | None
                       ) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["title"] = _input(
        "Title",
        default=(existing.title if is_edit else ""),
        allow_empty=False)
    payload["category"] = _pick_from(
        "Category", list(CATEGORIES),
        default=(existing.category if is_edit
                  else DEFAULT_CATEGORY))
    payload["priority"] = _input(
        "Priority (1-5)",
        default=(str(existing.priority) if is_edit else "2"))
    payload["audiences"] = _pick_audiences(
        existing.audience_list if is_edit
        else list(DEFAULT_AUDIENCES))
    payload["author"] = _input(
        "Author",
        default=(existing.author or "") if is_edit else "")
    try:
        payload["summary"] = _multiline(
            "Summary",
            default=(existing.summary or "") if is_edit else "")
        payload["body"] = _multiline(
            "Body",
            default=(existing.body or "") if is_edit else "")
    except _UserAbort:
        raise
    payload["pinned"] = _yes_no(
        "Pinned?",
        default=(existing.pinned if is_edit else False))
    payload["banner"] = _yes_no(
        "Banner?",
        default=(existing.banner if is_edit else False))
    payload["publish_on"] = _input(
        "Publish on (YYYY-MM-DD)",
        default=(existing.publish_on or "")
        if is_edit else "")
    payload["expires_on"] = _input(
        "Expires on (YYYY-MM-DD)",
        default=(existing.expires_on or "")
        if is_edit else "")
    payload["requires_acknowledgement"] = _yes_no(
        "Requires acknowledgement?",
        default=(existing.requires_acknowledgement
                  if is_edit else False))
    payload["comments_enabled"] = _yes_no(
        "Comments enabled?",
        default=(existing.comments_enabled
                  if is_edit else False))
    payload["attachments_ref"] = _input(
        "Attachments ref",
        default=(existing.attachments_ref or "")
        if is_edit else "")
    payload["linked_to"] = _input(
        "Linked to",
        default=(existing.linked_to or "")
        if is_edit else "")
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_STATUS))
    try:
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "") if is_edit else "")
    except _UserAbort:
        raise
    return payload


def new_announcement() -> None:
    print("\n═══ New Announcement ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_announcement(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created announcement #{a.announcement_id}")
    _pause()


def edit_announcement() -> None:
    print("\n═══ Edit Announcement ═══")
    try:
        a = _pick_announcement()
        payload = _collect_form(a)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_announcement(a.announcement_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{a.announcement_id}")
    _pause()


def publish_flow() -> None:
    print("\n═══ Publish ═══")
    try:
        a = _pick_announcement()
        when = _input("Published on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.publish(a.announcement_id, published_on=when)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{a.announcement_id} → Published")
    _pause()


def schedule_flow() -> None:
    print("\n═══ Schedule ═══")
    try:
        a = _pick_announcement()
        when = _input("Publish on (YYYY-MM-DD)",
                        allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.schedule(a.announcement_id, publish_on=when)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{a.announcement_id} → Scheduled")
    _pause()


def withdraw_flow() -> None:
    print("\n═══ Withdraw ═══")
    try:
        a = _pick_announcement()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.withdraw(a.announcement_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{a.announcement_id} → Withdrawn")
    _pause()


def archive_flow() -> None:
    print("\n═══ Archive ═══")
    try:
        a = _pick_announcement()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.archive(a.announcement_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{a.announcement_id} → Archived")
    _pause()


def toggle_pin_flow() -> None:
    print("\n═══ Toggle Pin ═══")
    try:
        a = _pick_announcement()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a2 = data.toggle_pin(a.announcement_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ pinned = {a2.pinned}")
    _pause()


def toggle_banner_flow() -> None:
    print("\n═══ Toggle Banner ═══")
    try:
        a = _pick_announcement()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a2 = data.toggle_banner(a.announcement_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ banner = {a2.banner}")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        a = _pick_announcement()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=a.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(a.announcement_id, new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{a.announcement_id} → {new_status}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete ═══")
    try:
        a = _pick_announcement()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete announcement #{a.announcement_id}? "
              "Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_announcement(a.announcement_id):
        print(f"\n  ✓ Deleted #{a.announcement_id}")
    _pause()


def auto_expire_flow() -> None:
    print("\n═══ Auto-expire ═══")
    n = data.auto_expire()
    print(f"\n  ✓ {n} announcement(s) moved to Expired")
    _pause()


def summary_flow() -> None:
    print("\n═══ Announcements Summary ═══")
    s = data.summary()
    print(f"\n  Total              : {s.total}")
    print(f"  Drafts             : {s.drafts}")
    print(f"  Scheduled          : {s.scheduled}")
    print(f"  Published          : {s.published}")
    print(f"  Live now           : {s.live_now}")
    print(f"  Expired unarchived : {s.expired_unarchived}")
    print(f"  Pinned             : {s.pinned}")
    print(f"  Banners            : {s.banners}")
    print(f"  Urgent (P≥4)       : {s.urgent_count}")
    print(f"  Total views        : {s.total_views}")
    print("\n  By category:")
    for k in CATEGORIES:
        n = s.by_category.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By priority:")
    for p in PRIORITIES:
        n = s.by_priority.get(p, 0)
        if n:
            print(f"    {p}  {priority_label(p):<12}: {n}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    print("\n  By audience:")
    for k in AUDIENCES:
        n = s.by_audience.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",         list_all),
    ("Live now",         list_live),
    ("Scheduled",        list_scheduled),
    ("Pinned",           list_pinned),
    ("Banners",          list_banners),
    ("Expired (unarch.)", list_expired),
    ("Filter",           filter_flow),
    ("View",             view_flow),
    ("─" * 6,            lambda: None),
    ("New announcement", new_announcement),
    ("Edit",             edit_announcement),
    ("Publish",          publish_flow),
    ("Schedule",         schedule_flow),
    ("Withdraw",         withdraw_flow),
    ("Archive",          archive_flow),
    ("Toggle pin",       toggle_pin_flow),
    ("Toggle banner",    toggle_banner_flow),
    ("Change status",    set_status_flow),
    ("Delete",           delete_flow),
    ("Auto-expire",      auto_expire_flow),
    ("─" * 6,            lambda: None),
    ("Summary",          summary_flow),
]


def run() -> None:
    while True:
        print("\n── Announcements ──")
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
            logger.exception("Announcements CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Announcements":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Announcements CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
