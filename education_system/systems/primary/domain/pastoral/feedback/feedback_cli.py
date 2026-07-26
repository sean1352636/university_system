"""CLI flows for Sixth Form Feedback."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.primary.domain.pastoral.feedback import (
    feedback as data,
)
from education_system.systems.primary.domain.pastoral.feedback.feedback import (
    CATEGORIES,
    DEFAULT_CATEGORY,
    DEFAULT_FEEDBACK_TYPE,
    DEFAULT_SOURCE,
    DEFAULT_STATUS,
    DEFAULT_SUBMITTER_ROLE,
    FEEDBACK_TYPES,
    Feedback,
    RATINGS,
    SOURCES,
    STATUSES,
    SUBMITTER_ROLES,
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


def _pick_feedback() -> Feedback:
    rows = data.list_feedback()
    if not rows:
        print("    No feedback yet.")
        raise _UserAbort
    print("\n  Feedback:")
    for i, f in enumerate(rows, 1):
        print(f"    {i:>3}) #{f.feedback_id}  "
              f"{f.received_on}  {f.feedback_type[:10]:<10}  "
              f"{f.category[:18]:<18}  "
              f"{f.subject[:30]:<30}  [{f.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.feedback_id == n), None)
            if match:
                return match
        print("    No matching feedback.")


def _print_table(rows: list[Feedback]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Received':<10}  {'Type':<12}  "
          f"{'Category':<22}  {'Subject':<32}  Rate  "
          f"{'Source':<14}  Status")
    print("  " + "-" * 130)
    for f in rows:
        rate = (f"{f.rating}/5" if f.rating else "—")
        print(f"  {f.feedback_id:>4}  {f.received_on:<10}  "
              f"{f.feedback_type[:12]:<12}  "
              f"{f.category[:22]:<22}  "
              f"{f.subject[:32]:<32}  "
              f"{rate:>4}  "
              f"{f.source[:14]:<14}  {f.status}")
    print(f"\n  {len(rows)} feedback item(s).")


def _print_full(f: Feedback) -> None:
    print()
    print(f"    #{f.feedback_id}  {f.subject}")
    print(f"    Received on        : {f.received_on}")
    print(f"    Source             : {f.source}")
    print(f"    Submitter          : "
          f"{f.submitter_name or '—'}  "
          f"({f.submitter_role})"
          + ("  ANONYMOUS" if f.anonymous else ""))
    print(f"    Contact            : "
          f"{f.contact_email or '—'}  "
          f"{f.contact_phone or '—'}")
    print(f"    Type               : {f.feedback_type}")
    print(f"    Category           : {f.category}")
    print(f"    Rating             : "
          f"{f.rating}/5" if f.rating else
          "    Rating             : —")
    print(f"    Assigned to        : {f.assigned_to or '—'}")
    print(f"    Status             : {f.status}")
    print(f"    Public shareable   : "
          f"{'yes' if f.public_shareable else 'no'}")
    print(f"    Linked to          : {f.linked_to or '—'}")
    print(f"    Closed on          : {f.closed_on or '—'}")
    for label, val in (
            ("Description",   f.description),
            ("Response",      f.response),
            ("Notes",         f.notes),
    ):
        if val:
            print(f"\n    {label}"
                  + (f" ({f.response_by} on {f.response_on})"
                      if label == "Response"
                      and (f.response_by or f.response_on)
                      else "")
                  + ":")
            for line in val.splitlines():
                print(f"      {line}")


# ── Flows ────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Feedback ═══")
    _print_table(data.list_feedback())
    _pause()


def list_open() -> None:
    print("\n═══ Open ═══")
    _print_table(data.list_feedback(open_only=True))
    _pause()


def list_awaiting() -> None:
    print("\n═══ Awaiting Response ═══")
    _print_table(data.list_feedback(awaiting_response=True))
    _pause()


def list_public() -> None:
    print("\n═══ Public Shareable ═══")
    _print_table(data.list_feedback(public_only=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        ftype = _input(
            f"Type ({'/'.join(FEEDBACK_TYPES[:3])}…)") or None
        cat = _input(
            f"Category ({'/'.join(CATEGORIES[:2])}…)") or None
        source = _input(f"Source ({'/'.join(SOURCES[:2])}…)") or None
        role = _input(
            f"Submitter role ({'/'.join(SUBMITTER_ROLES[:2])}…)") or None
        status = _input(f"Status ({'/'.join(STATUSES[:3])}…)") or None
        rmin = _input("Min rating (1-5)") or None
        assigned = _input("Assigned-to contains") or None
        subject = _input("Subject contains") or None
        df = _input("From (YYYY-MM-DD)") or None
        dt2 = _input("To (YYYY-MM-DD)") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    r = int(rmin) if rmin and rmin.isdigit() else None
    try:
        rows = data.list_feedback(
            feedback_type=ftype, category=cat, source=source,
            submitter_role=role, status=status, rating_min=r,
            assigned_to_like=assigned, subject_like=subject,
            date_from=df, date_to=dt2)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_table(rows)
    _pause()


def view_flow() -> None:
    print("\n═══ View Feedback ═══")
    try:
        f = _pick_feedback()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_full(f)
    _pause()


def _collect_form(existing: Feedback | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["subject"] = _input(
        "Subject",
        default=(existing.subject if is_edit else ""),
        allow_empty=False)
    payload["received_on"] = _input(
        "Received on (YYYY-MM-DD)",
        default=(existing.received_on if is_edit
                  else _date.today().isoformat()),
        allow_empty=False)
    payload["source"] = _pick_from(
        "Source", list(SOURCES),
        default=(existing.source if is_edit else DEFAULT_SOURCE))
    payload["submitter_role"] = _pick_from(
        "Submitter role", list(SUBMITTER_ROLES),
        default=(existing.submitter_role if is_edit
                  else DEFAULT_SUBMITTER_ROLE))
    payload["anonymous"] = _yes_no(
        "Anonymous?",
        default=(existing.anonymous if is_edit else False))
    if not payload["anonymous"]:
        payload["submitter_name"] = _input(
            "Submitter name",
            default=(existing.submitter_name or "")
            if is_edit else "")
    payload["contact_email"] = _input(
        "Email",
        default=(existing.contact_email or "")
        if is_edit else "")
    payload["contact_phone"] = _input(
        "Phone",
        default=(existing.contact_phone or "")
        if is_edit else "")
    payload["feedback_type"] = _pick_from(
        "Type", list(FEEDBACK_TYPES),
        default=(existing.feedback_type if is_edit
                  else DEFAULT_FEEDBACK_TYPE))
    payload["category"] = _pick_from(
        "Category", list(CATEGORIES),
        default=(existing.category if is_edit
                  else DEFAULT_CATEGORY))
    payload["rating"] = _input(
        "Rating (1-5, blank = none)",
        default=(str(existing.rating)
                  if is_edit and existing.rating is not None
                  else ""))
    try:
        payload["description"] = _multiline(
            "Description",
            default=(existing.description or "")
            if is_edit else "")
        payload["response"] = _multiline(
            "Response",
            default=(existing.response or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["response_by"] = _input(
        "Response by",
        default=(existing.response_by or "")
        if is_edit else "")
    payload["response_on"] = _input(
        "Response on (YYYY-MM-DD)",
        default=(existing.response_on or "")
        if is_edit else "")
    payload["assigned_to"] = _input(
        "Assigned to",
        default=(existing.assigned_to or "")
        if is_edit else "")
    payload["public_shareable"] = _yes_no(
        "Public shareable?",
        default=(existing.public_shareable
                  if is_edit else False))
    payload["linked_to"] = _input(
        "Linked to",
        default=(existing.linked_to or "")
        if is_edit else "")
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    payload["closed_on"] = _input(
        "Closed on (YYYY-MM-DD)",
        default=(existing.closed_on or "") if is_edit else "")
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_feedback() -> None:
    print("\n═══ New Feedback ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        f = data.create_feedback(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created feedback #{f.feedback_id}")
    _pause()


def edit_feedback() -> None:
    print("\n═══ Edit Feedback ═══")
    try:
        f = _pick_feedback()
        payload = _collect_form(f)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_feedback(f.feedback_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{f.feedback_id}")
    _pause()


def assign_flow() -> None:
    print("\n═══ Assign ═══")
    try:
        f = _pick_feedback()
        to = _input("Assign to",
                       default=f.assigned_to or "",
                       allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.assign(f.feedback_id, to=to)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Assigned #{f.feedback_id} to {to}")
    _pause()


def respond_flow() -> None:
    print("\n═══ Respond ═══")
    try:
        f = _pick_feedback()
        response = _multiline("Response",
                                 default=f.response or "")
        if not response:
            print("  ✗ Response required.")
            _pause()
            return
        by = _input("Response by",
                       default=f.response_by or "",
                       allow_empty=False)
        when = _input("Response on (YYYY-MM-DD)",
                         default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.respond(f.feedback_id, response=response,
                        response_by=by, response_on=when)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Response recorded on #{f.feedback_id}")
    _pause()


def mark_acted_flow() -> None:
    print("\n═══ Mark Acted ═══")
    try:
        f = _pick_feedback()
        notes = _multiline("Action notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.mark_acted(f.feedback_id, notes=notes or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{f.feedback_id} → Acted")
    _pause()


def close_flow() -> None:
    print("\n═══ Close ═══")
    try:
        f = _pick_feedback()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.close_feedback(f.feedback_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{f.feedback_id} → Closed")
    _pause()


def archive_flow() -> None:
    print("\n═══ Archive ═══")
    try:
        f = _pick_feedback()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.archive(f.feedback_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{f.feedback_id} → Archived")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        f = _pick_feedback()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=f.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(f.feedback_id, new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{f.feedback_id} → {new_status}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete ═══")
    try:
        f = _pick_feedback()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete #{f.feedback_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_feedback(f.feedback_id):
        print(f"\n  ✓ Deleted #{f.feedback_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ Feedback Summary ═══")
    s = data.summary()
    print(f"\n  Total              : {s.total}")
    print(f"  Open               : {s.open_count}")
    print(f"  Awaiting response  : {s.awaiting_response}")
    print(f"  Positive           : {s.positive_count}")
    print(f"  Negative           : {s.negative_count}")
    print(f"  Suggestions        : {s.suggestions_count}")
    print(f"  Public shareable   : {s.public_count}")
    print(f"  Average rating     : "
          f"{s.average_rating if s.average_rating is not None else '—'}")
    print("\n  By type:")
    for k in FEEDBACK_TYPES:
        n = s.by_type.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    print("\n  By category:")
    for k in CATEGORIES:
        n = s.by_category.get(k, 0)
        if n:
            print(f"    {k:<24}: {n}")
    print("\n  By source:")
    for k in SOURCES:
        n = s.by_source.get(k, 0)
        if n:
            print(f"    {k:<18}: {n}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    if s.by_rating:
        print("\n  By rating:")
        for r in RATINGS:
            n = s.by_rating.get(r, 0)
            if n:
                print(f"    {r}/5 : {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",          list_all),
    ("List open",         list_open),
    ("Awaiting response", list_awaiting),
    ("Public shareable",  list_public),
    ("Filter",            filter_flow),
    ("View",              view_flow),
    ("─" * 6,             lambda: None),
    ("New feedback",      new_feedback),
    ("Edit feedback",     edit_feedback),
    ("Assign",            assign_flow),
    ("Respond",           respond_flow),
    ("Mark acted",        mark_acted_flow),
    ("Close",             close_flow),
    ("Archive",           archive_flow),
    ("Change status",     set_status_flow),
    ("Delete",            delete_flow),
    ("─" * 6,             lambda: None),
    ("Summary",           summary_flow),
]


def run() -> None:
    while True:
        print("\n── Feedback ──")
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
            logger.exception("Feedback CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Feedback":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Feedback CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
