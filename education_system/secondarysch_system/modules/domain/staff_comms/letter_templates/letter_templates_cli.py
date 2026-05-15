"""CLI flows for Secondary School Letter Templates."""

from __future__ import annotations

import logging
from typing import Any, Callable

from education_system.secondarysch_system.modules.domain.staff_comms.letter_templates import (
    letter_templates as data,
)
from education_system.secondarysch_system.modules.domain.staff_comms.letter_templates.letter_templates import (
    CATEGORIES,
    DEFAULT_CATEGORY,
    DEFAULT_FORMAT,
    DEFAULT_RECIPIENT_TYPE,
    DEFAULT_STATUS,
    FORMATS,
    RECIPIENT_TYPES,
    STATUSES,
    Template,
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


def _pick_template() -> Template:
    rows = data.list_templates()
    if not rows:
        print("    No templates yet.")
        raise _UserAbort
    print("\n  Templates:")
    for i, t in enumerate(rows, 1):
        print(f"    {i:>3}) #{t.template_id}  "
              f"{t.category[:14]:<14}  "
              f"{t.name[:32]:<32}  [{t.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            k = int(raw)
            if 1 <= k <= len(rows):
                return rows[k - 1]
            match = next((r for r in rows
                            if r.template_id == k), None)
            if match:
                return match
        print("    No matching template.")


def _print_table(rows: list[Template]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Name':<32}  {'Category':<22}  "
          f"{'Recipient':<16}  {'Format':<20}  "
          f"{'Status':<10}  Uses")
    print("  " + "-" * 130)
    for t in rows:
        print(f"  {t.template_id:>4}  "
              f"{t.name[:32]:<32}  "
              f"{t.category[:22]:<22}  "
              f"{t.recipient_type[:16]:<16}  "
              f"{t.format[:20]:<20}  "
              f"{t.status:<10}  {t.use_count:>4}")
    print(f"\n  {len(rows)} template(s).")


def _print_full(t: Template) -> None:
    print()
    print(f"    #{t.template_id}  {t.name}")
    print(f"    Category         : {t.category}")
    print(f"    Recipient type   : {t.recipient_type}")
    print(f"    Format           : {t.format}")
    print(f"    Status           : {t.status}")
    print(f"    Sender role      : {t.sender_role or '—'}")
    print(f"    Created by       : {t.created_by or '—'}")
    print(f"    Last used on     : {t.last_used_on or '—'}")
    print(f"    Use count        : {t.use_count}")
    print(f"    Merge fields     : {t.merge_fields or '—'}")
    print(f"    Detected         : "
          f"{', '.join(t.detected_placeholders) or '—'}")
    print(f"    Attachments ref  : {t.attachments_ref or '—'}")
    if t.description:
        print(f"\n    Description:")
        for line in t.description.splitlines():
            print(f"      {line}")
    if t.letterhead:
        print(f"\n    Letterhead:")
        for line in t.letterhead.splitlines():
            print(f"      {line}")
    if t.subject_line:
        print(f"\n    Subject line     : {t.subject_line}")
    print(f"\n    Body:")
    for line in t.body.splitlines():
        print(f"      {line}")
    if t.signature:
        print(f"\n    Signature:")
        for line in t.signature.splitlines():
            print(f"      {line}")
    if t.footer:
        print(f"\n    Footer:")
        for line in t.footer.splitlines():
            print(f"      {line}")
    if t.notes:
        print(f"\n    Notes:")
        for line in t.notes.splitlines():
            print(f"      {line}")


# ── Flows ────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Templates ═══")
    _print_table(data.list_templates())
    _pause()


def list_active() -> None:
    print("\n═══ Active Templates ═══")
    _print_table(data.list_templates(active_only=True))
    _pause()


def list_drafts() -> None:
    print("\n═══ Drafts ═══")
    _print_table(data.list_templates(status="Draft"))
    _pause()


def list_archived() -> None:
    print("\n═══ Archived ═══")
    _print_table(data.list_templates(status="Archived"))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        cat = _input(
            f"Category ({'/'.join(CATEGORIES[:3])}…)") or None
        rt = _input(
            f"Recipient type "
            f"({'/'.join(RECIPIENT_TYPES[:3])}…)") or None
        fmt = _input(
            f"Format ({'/'.join(FORMATS[:3])}…)") or None
        status = _input(
            f"Status ({'/'.join(STATUSES[:3])}…)") or None
        name = _input("Name contains") or None
        created = _input("Created by contains") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_templates(
            category=cat, recipient_type=rt, format=fmt,
            status=status, name_like=name,
            created_by_like=created)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_table(rows)
    _pause()


def view_flow() -> None:
    print("\n═══ View Template ═══")
    try:
        t = _pick_template()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_full(t)
    _pause()


def _collect_form(existing: Template | None
                       ) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["name"] = _input(
        "Name",
        default=(existing.name if is_edit else ""),
        allow_empty=False)
    payload["description"] = _input(
        "Description",
        default=(existing.description or "")
        if is_edit else "")
    payload["category"] = _pick_from(
        "Category", list(CATEGORIES),
        default=(existing.category if is_edit
                  else DEFAULT_CATEGORY))
    payload["recipient_type"] = _pick_from(
        "Recipient type", list(RECIPIENT_TYPES),
        default=(existing.recipient_type if is_edit
                  else DEFAULT_RECIPIENT_TYPE))
    payload["format"] = _pick_from(
        "Format", list(FORMATS),
        default=(existing.format if is_edit
                  else DEFAULT_FORMAT))
    payload["subject_line"] = _input(
        "Subject line",
        default=(existing.subject_line or "")
        if is_edit else "")
    try:
        payload["body"] = _multiline(
            "Body (use {{placeholder}} for merge fields)",
            default=(existing.body or "") if is_edit else "")
        payload["letterhead"] = _multiline(
            "Letterhead",
            default=(existing.letterhead or "")
            if is_edit else "")
        payload["signature"] = _multiline(
            "Signature",
            default=(existing.signature or "")
            if is_edit else "")
        payload["footer"] = _multiline(
            "Footer",
            default=(existing.footer or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["sender_role"] = _input(
        "Sender role",
        default=(existing.sender_role or "")
        if is_edit else "")
    payload["merge_fields"] = _input(
        "Merge fields (CSV, blank = auto-detect)",
        default=(existing.merge_fields or "")
        if is_edit else "")
    payload["attachments_ref"] = _input(
        "Attachments ref",
        default=(existing.attachments_ref or "")
        if is_edit else "")
    payload["created_by"] = _input(
        "Created by",
        default=(existing.created_by or "")
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


def new_template() -> None:
    print("\n═══ New Template ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        t = data.create_template(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created template #{t.template_id}")
    _pause()


def edit_template() -> None:
    print("\n═══ Edit Template ═══")
    try:
        t = _pick_template()
        payload = _collect_form(t)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_template(t.template_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{t.template_id}")
    _pause()


def activate_flow() -> None:
    print("\n═══ Activate ═══")
    try:
        t = _pick_template()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.activate(t.template_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{t.template_id} → Active")
    _pause()


def archive_flow() -> None:
    print("\n═══ Archive ═══")
    try:
        t = _pick_template()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.archive(t.template_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{t.template_id} → Archived")
    _pause()


def retire_flow() -> None:
    print("\n═══ Retire ═══")
    try:
        t = _pick_template()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.retire(t.template_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{t.template_id} → Retired")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        t = _pick_template()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=t.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(t.template_id, new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{t.template_id} → {new_status}")
    _pause()


def duplicate_flow() -> None:
    print("\n═══ Duplicate ═══")
    try:
        t = _pick_template()
        new_name = _input("New name", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        dup = data.duplicate(t.template_id, new_name=new_name)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Duplicated as #{dup.template_id} "
          f"({dup.status})")
    _pause()


def preview_flow() -> None:
    print("\n═══ Preview (raw template) ═══")
    try:
        t = _pick_template()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    r = data.preview(t)
    print(f"\n    Subject: {r.subject or '—'}")
    print(f"\n    Body:")
    for line in r.body.splitlines():
        print(f"      {line}")
    if r.missing_fields:
        print(f"\n    Placeholders: "
              f"{', '.join(r.missing_fields)}")
    _pause()


def render_flow() -> None:
    print("\n═══ Render Template ═══")
    try:
        t = _pick_template()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    placeholders = t.detected_placeholders
    if not placeholders:
        print("\n  (this template has no placeholders)")
    context: dict[str, str] = {}
    try:
        for p in placeholders:
            v = _input(f"{p}", default="")
            if v:
                context[p] = v
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.render(t, context)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print()
    if r.subject is not None:
        print(f"    Subject: {r.subject}")
        print()
    for line in r.body.splitlines():
        print(f"    {line}")
    if r.missing_fields:
        print(f"\n  ⚠ Missing: {', '.join(r.missing_fields)}")
    else:
        print(f"\n  ✓ Rendered cleanly (use_count incremented).")
    _pause()


def record_use_flow() -> None:
    print("\n═══ Record Use ═══")
    try:
        t = _pick_template()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        t2 = data.record_use(t.template_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ use_count = {t2.use_count}, "
          f"last_used_on = {t2.last_used_on}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete ═══")
    try:
        t = _pick_template()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete template #{t.template_id} "
              f"({t.name})? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_template(t.template_id):
        print(f"\n  ✓ Deleted #{t.template_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Letter Templates Summary ═══")
    s = data.summary()
    print(f"\n  Total            : {s.total}")
    print(f"  Active           : {s.active}")
    print(f"  Drafts           : {s.drafts}")
    print(f"  Archived         : {s.archived}")
    print(f"  Retired          : {s.retired}")
    print(f"  Total uses       : {s.total_uses}")
    if s.most_used_name:
        print(f"  Most used        : {s.most_used_name} "
              f"({s.most_used_count} uses)")
    print("\n  By category:")
    for k in CATEGORIES:
        n = s.by_category.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By recipient type:")
    for k in RECIPIENT_TYPES:
        n = s.by_recipient_type.get(k, 0)
        if n:
            print(f"    {k:<18}: {n}")
    print("\n  By format:")
    for k in FORMATS:
        n = s.by_format.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",         list_all),
    ("Active",           list_active),
    ("Drafts",           list_drafts),
    ("Archived",         list_archived),
    ("Filter",           filter_flow),
    ("View",             view_flow),
    ("─" * 6,            lambda: None),
    ("New template",     new_template),
    ("Edit",             edit_template),
    ("Activate",         activate_flow),
    ("Archive",          archive_flow),
    ("Retire",           retire_flow),
    ("Change status",    set_status_flow),
    ("Duplicate",        duplicate_flow),
    ("Preview",          preview_flow),
    ("Render",           render_flow),
    ("Record use",       record_use_flow),
    ("Delete",           delete_flow),
    ("─" * 6,            lambda: None),
    ("Summary",          summary_flow),
]


def run() -> None:
    while True:
        print("\n── Letter Templates ──")
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
            logger.exception("Letter Templates CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Letter Templates":
        return False
    try:
        run()
    except Exception as e:
        logger.exception(
            "Letter Templates CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
