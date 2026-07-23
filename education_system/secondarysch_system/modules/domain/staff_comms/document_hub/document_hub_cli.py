"""CLI flows for Secondary School Document Hub."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.staff_comms.document_hub import (
    document_hub as data,
)
from education_system.secondarysch_system.modules.domain.staff_comms.document_hub.document_hub import (
    ACCESS_LEVELS,
    AUDIENCES,
    CATEGORIES,
    DEFAULT_ACCESS,
    DEFAULT_AUDIENCE,
    DEFAULT_CATEGORY,
    DEFAULT_STATUS,
    Document,
    STATUSES,
    ValidationError,
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


def _pick_document() -> Document:
    rows = data.list_documents()
    if not rows:
        print("    No documents yet.")
        raise _UserAbort
    print("\n  Documents:")
    for i, d in enumerate(rows, 1):
        flag = "!" if d.is_overdue_review else " "
        print(f"    {i:>3}){flag} #{d.document_id}  "
              f"{d.category[:14]:<14}  v{d.version[:6]:<6}  "
              f"{d.title[:36]:<36}  [{d.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            k = int(raw)
            if 1 <= k <= len(rows):
                return rows[k - 1]
            match = next((r for r in rows
                            if r.document_id == k), None)
            if match:
                return match
        print("    No matching document.")


def _print_table(rows: list[Document]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4} ! {'Title':<32}  {'Category':<16}  "
          f"{'Audience':<18}  {'Access':<14}  "
          f"{'Version':<8}  {'Issued':<10}  "
          f"{'Review':<10}  {'Status':<12}  Downloads")
    print("  " + "-" * 150)
    for d in rows:
        ov = "!" if d.is_overdue_review else " "
        print(f"  {d.document_id:>4} {ov} "
              f"{d.title[:32]:<32}  "
              f"{d.category[:16]:<16}  "
              f"{d.audience[:18]:<18}  "
              f"{d.access_level[:14]:<14}  "
              f"{d.version[:8]:<8}  "
              f"{(d.issued_on or '—'):<10}  "
              f"{(d.review_on or '—'):<10}  "
              f"{d.status:<12}  {d.download_count:>5}")
    print(f"\n  {len(rows)} document(s).")


def _print_full(d: Document) -> None:
    print()
    print(f"    #{d.document_id}  {d.title}  v{d.version}")
    print(f"    Category         : {d.category}")
    print(f"    Audience         : {d.audience}")
    print(f"    Access level     : {d.access_level}")
    print(f"    Status           : {d.status}")
    print(f"    Author           : {d.author or '—'}")
    print(f"    Owner department : {d.owner_department or '—'}")
    print(f"    Approved by      : {d.approved_by or '—'}")
    print(f"    Issued on        : {d.issued_on or '—'}")
    print(f"    Review on        : {d.review_on or '—'}"
          + ("  (OVERDUE)" if d.is_overdue_review else ""))
    print(f"    Expires on       : {d.expires_on or '—'}"
          + ("  (EXPIRED)" if d.is_expired else ""))
    print(f"    Supersedes id    : {d.supersedes_id or '—'}")
    print(f"    File ref         : {d.file_ref or '—'}")
    print(f"    File format      : {d.file_format or '—'}")
    print(f"    File size (kB)   : "
          f"{d.file_size_kb if d.file_size_kb is not None else '—'}")
    print(f"    Downloads        : {d.download_count}")
    print(f"    Keywords         : {d.keywords or '—'}")
    print(f"    Linked to        : {d.linked_to or '—'}")
    if d.description:
        print("\n    Description:")
        for line in d.description.splitlines():
            print(f"      {line}")
    if d.notes:
        print("\n    Notes:")
        for line in d.notes.splitlines():
            print(f"      {line}")


# ── Flows ────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Documents ═══")
    _print_table(data.list_documents())
    _pause()


def list_current() -> None:
    print("\n═══ Current (Approved / Published) ═══")
    _print_table(data.list_documents(current_only=True))
    _pause()


def list_overdue() -> None:
    print("\n═══ Overdue for Review ═══")
    _print_table(data.list_documents(overdue_review_only=True))
    _pause()


def list_drafts() -> None:
    print("\n═══ Drafts ═══")
    _print_table(data.list_documents(status="Draft"))
    _pause()


def list_under_review() -> None:
    print("\n═══ Under Review ═══")
    _print_table(data.list_documents(status="Under Review"))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        cat = _input(
            f"Category ({'/'.join(CATEGORIES[:3])}…)") or None
        aud = _input(
            f"Audience ({'/'.join(AUDIENCES[:3])}…)") or None
        access = _input(
            f"Access ({'/'.join(ACCESS_LEVELS)})") or None
        status = _input(
            f"Status ({'/'.join(STATUSES[:3])}…)") or None
        title = _input("Title contains") or None
        kw = _input("Keyword contains") or None
        author = _input("Author contains") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_documents(
            category=cat, audience=aud,
            access_level=access, status=status,
            title_like=title, keyword_like=kw,
            author_like=author)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_table(rows)
    _pause()


def view_flow() -> None:
    print("\n═══ View Document ═══")
    try:
        d = _pick_document()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_full(d)
    data.increment_downloads(d.document_id, by=1)
    _pause()


def _collect_form(existing: Document | None
                       ) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
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
    payload["audience"] = _pick_from(
        "Audience", list(AUDIENCES),
        default=(existing.audience if is_edit
                  else DEFAULT_AUDIENCE))
    payload["access_level"] = _pick_from(
        "Access level", list(ACCESS_LEVELS),
        default=(existing.access_level if is_edit
                  else DEFAULT_ACCESS))
    payload["version"] = _input(
        "Version",
        default=(existing.version if is_edit else "1.0"))
    payload["file_ref"] = _input(
        "File ref / URL",
        default=(existing.file_ref or "")
        if is_edit else "")
    payload["file_format"] = _input(
        "File format (e.g. PDF, DOCX)",
        default=(existing.file_format or "")
        if is_edit else "")
    payload["file_size_kb"] = _input(
        "File size (kB)",
        default=(str(existing.file_size_kb or "")
                  if is_edit else ""))
    payload["author"] = _input(
        "Author",
        default=(existing.author or "")
        if is_edit else "")
    payload["owner_department"] = _input(
        "Owner department",
        default=(existing.owner_department or "")
        if is_edit else "")
    payload["approved_by"] = _input(
        "Approved by",
        default=(existing.approved_by or "")
        if is_edit else "")
    payload["keywords"] = _input(
        "Keywords (CSV)",
        default=(existing.keywords or "")
        if is_edit else "")
    payload["issued_on"] = _input(
        "Issued on (YYYY-MM-DD)",
        default=(existing.issued_on or "")
        if is_edit else "")
    payload["review_on"] = _input(
        "Review on (YYYY-MM-DD)",
        default=(existing.review_on or "")
        if is_edit else "")
    payload["expires_on"] = _input(
        "Expires on (YYYY-MM-DD)",
        default=(existing.expires_on or "")
        if is_edit else "")
    payload["supersedes_id"] = _input(
        "Supersedes id",
        default=(str(existing.supersedes_id or "")
                  if is_edit else ""))
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
            default=(existing.notes or "")
            if is_edit else "")
    except _UserAbort:
        raise
    return payload


def new_document() -> None:
    print("\n═══ New Document ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        d = data.create_document(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created document #{d.document_id}")
    _pause()


def edit_document() -> None:
    print("\n═══ Edit Document ═══")
    try:
        d = _pick_document()
        payload = _collect_form(d)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_document(d.document_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{d.document_id}")
    _pause()


def submit_for_review_flow() -> None:
    print("\n═══ Submit for Review ═══")
    try:
        d = _pick_document()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.submit_for_review(d.document_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{d.document_id} → Under Review")
    _pause()


def approve_flow() -> None:
    print("\n═══ Approve ═══")
    try:
        d = _pick_document()
        approver = _input("Approved by",
                            default=d.approved_by or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.approve(d.document_id,
                          approved_by=approver or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{d.document_id} → Approved")
    _pause()


def publish_flow() -> None:
    print("\n═══ Publish ═══")
    try:
        d = _pick_document()
        when = _input("Issued on (YYYY-MM-DD)",
                        default=d.issued_on
                                or _date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.publish(d.document_id, issued_on=when)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{d.document_id} → Published")
    _pause()


def withdraw_flow() -> None:
    print("\n═══ Withdraw ═══")
    try:
        d = _pick_document()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.withdraw(d.document_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{d.document_id} → Withdrawn")
    _pause()


def archive_flow() -> None:
    print("\n═══ Archive ═══")
    try:
        d = _pick_document()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.archive(d.document_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{d.document_id} → Archived")
    _pause()


def supersede_flow() -> None:
    print("\n═══ Supersede (create new version) ═══")
    try:
        d = _pick_document()
        new_v = _input(f"New version (current: {d.version})",
                         allow_empty=False)
        carry = _yes_no("Carry over all fields?", default=True)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        new_d = data.supersede(d.document_id,
                                       new_version=new_v,
                                       carry_over=carry)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created draft #{new_d.document_id} "
          f"v{new_d.version}; old #{d.document_id} → "
          "Superseded")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        d = _pick_document()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=d.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(d.document_id, new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{d.document_id} → {new_status}")
    _pause()


def auto_archive_flow() -> None:
    print("\n═══ Auto-archive Expired ═══")
    n = data.auto_archive_expired()
    print(f"\n  ✓ {n} document(s) archived")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete ═══")
    try:
        d = _pick_document()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete document #{d.document_id}? "
              "Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_document(d.document_id):
        print(f"\n  ✓ Deleted #{d.document_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Document Hub Summary ═══")
    s = data.summary()
    print(f"\n  Total                : {s.total}")
    print(f"  Drafts               : {s.drafts}")
    print(f"  Under review         : {s.under_review}")
    print(f"  Approved             : {s.approved}")
    print(f"  Published            : {s.published}")
    print(f"  Superseded           : {s.superseded}")
    print(f"  Archived             : {s.archived}")
    print(f"  Overdue for review   : {s.overdue_review}")
    print(f"  Expired unprocessed  : {s.expired_unprocessed}")
    print(f"  Confidential         : {s.confidential}")
    print(f"  Total downloads      : {s.total_downloads}")
    print("\n  By category:")
    for k in CATEGORIES:
        n = s.by_category.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By audience:")
    for k in AUDIENCES:
        n = s.by_audience.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By access:")
    for k in ACCESS_LEVELS:
        n = s.by_access.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",          list_all),
    ("Current",           list_current),
    ("Overdue review",    list_overdue),
    ("Drafts",            list_drafts),
    ("Under review",      list_under_review),
    ("Filter",            filter_flow),
    ("View",              view_flow),
    ("─" * 6,             lambda: None),
    ("New document",      new_document),
    ("Edit",              edit_document),
    ("Submit for review", submit_for_review_flow),
    ("Approve",           approve_flow),
    ("Publish",           publish_flow),
    ("Withdraw",          withdraw_flow),
    ("Archive",           archive_flow),
    ("Supersede (new ver)", supersede_flow),
    ("Change status",     set_status_flow),
    ("Auto-archive expired", auto_archive_flow),
    ("Delete",            delete_flow),
    ("─" * 6,             lambda: None),
    ("Summary",           summary_flow),
]


def run() -> None:
    while True:
        print("\n── Document Hub ──")
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
            logger.exception("Document Hub CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Document Hub":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Document Hub CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
