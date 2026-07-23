"""CLI flows for Primary School Attachments."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable

from education_system.primarysch_system.modules.domain.attachments import (
    attachments as data,
)
from education_system.primarysch_system.modules.domain.attachments.attachments import (
    Attachment,
    CATEGORIES,
    DEFAULT_CATEGORY,
    DEFAULT_ENTITY_TYPE,
    DEFAULT_STATUS,
    DEFAULT_VISIBILITY,
    ENTITY_TYPES,
    STATUSES,
    ValidationError,
    VISIBILITY,
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


def _pick_attachment() -> Attachment:
    rows = data.list_attachments()
    if not rows:
        print("    No attachments yet.")
        raise _UserAbort
    print("\n  Attachments:")
    for i, a in enumerate(rows, 1):
        pii = "P" if a.contains_pii else " "
        ret = "!" if a.is_expired_retention else " "
        print(f"    {i:>3}){pii}{ret} #{a.attachment_id}  "
              f"{a.entity_type[:8]:<8} "
              f"{a.entity_id[:10]:<10}  "
              f"{a.title[:32]:<32}  [{a.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            k = int(raw)
            if 1 <= k <= len(rows):
                return rows[k - 1]
            match = next((r for r in rows
                            if r.attachment_id == k), None)
            if match:
                return match
        print("    No matching attachment.")


def _print_table(rows: list[Attachment]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4} P R  {'Entity':<22}  "
          f"{'Title':<32}  {'Category':<14}  "
          f"{'Visibility':<14}  {'Format':<8}  "
          f"{'Uploaded':<12}  {'Status':<12}  Size")
    print("  " + "-" * 150)
    for a in rows:
        pii = "P" if a.contains_pii else " "
        ret = "!" if a.is_expired_retention else " "
        ent = f"{a.entity_type[:8]}:{a.entity_id[:12]}"
        size = (f"{a.file_size_kb}kB"
                  if a.file_size_kb is not None else "—")
        print(f"  {a.attachment_id:>4} {pii} {ret}  "
              f"{ent[:22]:<22}  "
              f"{a.title[:32]:<32}  "
              f"{a.category[:14]:<14}  "
              f"{a.visibility[:14]:<14}  "
              f"{(a.file_format or '—')[:8]:<8}  "
              f"{a.uploaded_on[:10]:<12}  "
              f"{a.status:<12}  {size}")
    print(f"\n  {len(rows)} attachment(s).")


def _print_full(a: Attachment) -> None:
    print()
    print(f"    #{a.attachment_id}  {a.title}")
    print(f"    Entity           : {a.entity_type} :: "
          f"{a.entity_id}")
    print(f"    Category         : {a.category}")
    print(f"    Visibility       : {a.visibility}")
    print(f"    Status           : {a.status}")
    print(f"    File ref         : {a.file_ref}")
    print(f"    File name        : {a.file_name or '—'}")
    print(f"    File format      : {a.file_format or '—'}")
    print(f"    File size (kB)   : "
          f"{a.file_size_kb if a.file_size_kb is not None else '—'}")
    print(f"    MIME type        : {a.mime_type or '—'}")
    print(f"    Checksum         : {a.checksum or '—'}")
    print(f"    Uploaded by      : {a.uploaded_by or '—'}")
    print(f"    Uploaded on      : {a.uploaded_on}")
    print(f"    Last accessed on : {a.last_accessed_on or '—'}")
    print(f"    Downloads        : {a.download_count}")
    print(f"    Contains PII     : "
          f"{'yes' if a.contains_pii else 'no'}")
    print(f"    Consent recorded : "
          f"{'yes' if a.consent_recorded else 'no'}")
    print(f"    Retention until  : "
          f"{a.retention_until or '—'}"
          + ("  (EXPIRED)" if a.is_expired_retention
              else ""))
    print(f"    Keywords         : {a.tagged_keywords or '—'}")
    if a.description:
        print("\n    Description:")
        for line in a.description.splitlines():
            print(f"      {line}")
    if a.notes:
        print("\n    Notes:")
        for line in a.notes.splitlines():
            print(f"      {line}")


# ── Flows ────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Attachments ═══")
    _print_table(data.list_attachments())
    _pause()


def list_active() -> None:
    print("\n═══ Active Attachments ═══")
    _print_table(data.list_attachments(active_only=True))
    _pause()


def list_pii() -> None:
    print("\n═══ Attachments Containing PII ═══")
    _print_table(data.list_attachments(pii_only=True))
    _pause()


def list_retention_expired() -> None:
    print("\n═══ Retention Expired (Active) ═══")
    _print_table(data.list_attachments(
        retention_expired_only=True))
    _pause()


def list_quarantined() -> None:
    print("\n═══ Quarantined ═══")
    _print_table(data.list_attachments(status="Quarantined"))
    _pause()


def list_for_entity() -> None:
    print("\n═══ Attachments for an Entity ═══")
    try:
        et = _pick_from("Entity type", list(ENTITY_TYPES),
                          default=DEFAULT_ENTITY_TYPE)
        eid = _input("Entity id", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_table(data.attachments_for(et, eid))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        et = _input(
            f"Entity type ({'/'.join(ENTITY_TYPES[:3])}…)"
            ) or None
        cat = _input(
            f"Category ({'/'.join(CATEGORIES[:3])}…)") or None
        vis = _input(
            f"Visibility ({'/'.join(VISIBILITY)})") or None
        status = _input(
            f"Status ({'/'.join(STATUSES[:3])}…)") or None
        title = _input("Title contains") or None
        kw = _input("Keyword contains") or None
        upl = _input("Uploaded by contains") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_attachments(
            entity_type=et, category=cat, visibility=vis,
            status=status, title_like=title,
            keyword_like=kw, uploaded_by_like=upl)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_table(rows)
    _pause()


def view_flow() -> None:
    print("\n═══ View Attachment ═══")
    try:
        a = _pick_attachment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_full(a)
    data.record_access(a.attachment_id)
    _pause()


def _collect_form(existing: Attachment | None
                       ) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["entity_type"] = _pick_from(
        "Entity type", list(ENTITY_TYPES),
        default=(existing.entity_type if is_edit
                  else DEFAULT_ENTITY_TYPE))
    payload["entity_id"] = _input(
        "Entity id",
        default=(existing.entity_id if is_edit else ""),
        allow_empty=False)
    payload["title"] = _input(
        "Title",
        default=(existing.title if is_edit else ""),
        allow_empty=False)
    payload["description"] = _input(
        "Description",
        default=(existing.description or "")
        if is_edit else "")
    payload["category"] = _pick_from(
        "Category", list(CATEGORIES),
        default=(existing.category if is_edit
                  else DEFAULT_CATEGORY))
    payload["visibility"] = _pick_from(
        "Visibility", list(VISIBILITY),
        default=(existing.visibility if is_edit
                  else DEFAULT_VISIBILITY))
    payload["file_ref"] = _input(
        "File ref / URL",
        default=(existing.file_ref if is_edit else ""),
        allow_empty=False)
    payload["file_name"] = _input(
        "File name",
        default=(existing.file_name or "")
        if is_edit else "")
    payload["file_format"] = _input(
        "File format (e.g. PDF, JPG)",
        default=(existing.file_format or "")
        if is_edit else "")
    payload["file_size_kb"] = _input(
        "File size (kB)",
        default=(str(existing.file_size_kb or "")
                  if is_edit else ""))
    payload["mime_type"] = _input(
        "MIME type",
        default=(existing.mime_type or "")
        if is_edit else "")
    payload["checksum"] = _input(
        "Checksum",
        default=(existing.checksum or "")
        if is_edit else "")
    payload["uploaded_by"] = _input(
        "Uploaded by",
        default=(existing.uploaded_by or "")
        if is_edit else "")
    payload["uploaded_on"] = _input(
        "Uploaded on (YYYY-MM-DD)",
        default=(existing.uploaded_on if is_edit
                  else _date.today().isoformat()))
    payload["tagged_keywords"] = _input(
        "Keywords (CSV)",
        default=(existing.tagged_keywords or "")
        if is_edit else "")
    payload["contains_pii"] = _yes_no(
        "Contains PII?",
        default=(existing.contains_pii
                  if is_edit else False))
    payload["consent_recorded"] = _yes_no(
        "Consent recorded?",
        default=(existing.consent_recorded
                  if is_edit else False))
    payload["retention_until"] = _input(
        "Retention until (YYYY-MM-DD)",
        default=(existing.retention_until or "")
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


def new_attachment() -> None:
    print("\n═══ New Attachment ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_attachment(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created attachment #{a.attachment_id}")
    _pause()


def edit_attachment() -> None:
    print("\n═══ Edit Attachment ═══")
    try:
        a = _pick_attachment()
        payload = _collect_form(a)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_attachment(a.attachment_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{a.attachment_id}")
    _pause()


def quarantine_flow() -> None:
    print("\n═══ Quarantine ═══")
    try:
        a = _pick_attachment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.quarantine(a.attachment_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{a.attachment_id} → Quarantined")
    _pause()


def restore_flow() -> None:
    print("\n═══ Restore (→ Active) ═══")
    try:
        a = _pick_attachment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.restore(a.attachment_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{a.attachment_id} → Active")
    _pause()


def archive_flow() -> None:
    print("\n═══ Archive ═══")
    try:
        a = _pick_attachment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.archive(a.attachment_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{a.attachment_id} → Archived")
    _pause()


def soft_delete_flow() -> None:
    print("\n═══ Soft-delete (status = Deleted) ═══")
    try:
        a = _pick_attachment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.soft_delete(a.attachment_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{a.attachment_id} → Deleted")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        a = _pick_attachment()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=a.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(a.attachment_id, new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{a.attachment_id} → {new_status}")
    _pause()


def record_access_flow() -> None:
    print("\n═══ Record Access ═══")
    try:
        a = _pick_attachment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a2 = data.record_access(a.attachment_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ downloads = {a2.download_count}, "
          f"last_accessed = {a2.last_accessed_on}")
    _pause()


def purge_retention_flow() -> None:
    print("\n═══ Purge Retention-Expired ═══")
    hard = _yes_no("Hard-delete (otherwise soft-delete)?",
                     default=False)
    n = data.purge_expired_retention(hard_delete=hard)
    print(f"\n  ✓ {n} attachment(s) "
          f"{'hard-deleted' if hard else 'soft-deleted'}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Hard Delete ═══")
    try:
        a = _pick_attachment()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Hard-delete attachment #{a.attachment_id}? "
              "Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_attachment(a.attachment_id):
        print(f"\n  ✓ Deleted #{a.attachment_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Attachments Summary ═══")
    s = data.summary()
    print(f"\n  Total                : {s.total}")
    print(f"  Active               : {s.active}")
    print(f"  Quarantined          : {s.quarantined}")
    print(f"  Archived             : {s.archived}")
    print(f"  Deleted              : {s.deleted}")
    print(f"  Confidential         : {s.confidential}")
    print(f"  Contains PII         : {s.contains_pii}")
    print(f"  Retention expired    : {s.retention_expired}")
    print(f"  Total size (kB)      : {s.total_size_kb}")
    print(f"  Total downloads      : {s.total_downloads}")
    print(f"  Distinct entities    : {s.distinct_entities}")
    print("\n  By entity type:")
    for k in ENTITY_TYPES:
        n = s.by_entity_type.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By category:")
    for k in CATEGORIES:
        n = s.by_category.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By visibility:")
    for k in VISIBILITY:
        n = s.by_visibility.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    print("\n  By format:")
    for fmt, n in sorted(s.by_format.items(),
                              key=lambda kv: -kv[1]):
        if n:
            print(f"    {fmt:<14}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",            list_all),
    ("Active",              list_active),
    ("Contains PII",        list_pii),
    ("Retention expired",   list_retention_expired),
    ("Quarantined",         list_quarantined),
    ("For entity",          list_for_entity),
    ("Filter",              filter_flow),
    ("View",                view_flow),
    ("─" * 6,               lambda: None),
    ("New attachment",      new_attachment),
    ("Edit",                edit_attachment),
    ("Quarantine",          quarantine_flow),
    ("Restore",             restore_flow),
    ("Archive",             archive_flow),
    ("Soft-delete",         soft_delete_flow),
    ("Change status",       set_status_flow),
    ("Record access",       record_access_flow),
    ("Purge retention-exp", purge_retention_flow),
    ("Hard delete",         delete_flow),
    ("─" * 6,               lambda: None),
    ("Summary",             summary_flow),
]


def run() -> None:
    while True:
        print("\n── Attachments ──")
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
            logger.exception("Attachments CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Attachments":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Attachments CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
