"""CLI flows for Sixth Form SEF Builder."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.assessment.sef_builder import (
    sef_builder as data,
)
from education_system.post_16.sixthform_system.modules.domain.assessment.sef_builder.sef_builder import (
    AREAS,
    DEFAULT_AREA,
    DEFAULT_STATUS,
    JUDGEMENTS,
    SEFSection,
    STATUSES,
    ValidationError,
    judgement_label,
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
        print(f"    {marker}{i:>2}) {opt}")
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


def _pick_section() -> SEFSection:
    rows = data.list_sections()
    if not rows:
        print("    No SEF sections yet.")
        raise _UserAbort
    print("\n  SEF Sections:")
    for i, s in enumerate(rows, 1):
        print(f"    {i:>3}) #{s.section_id}  "
              f"{s.cycle}  {s.area[:30]:<30}  "
              f"J={s.judgement or '—'}  [{s.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((s for s in rows
                            if s.section_id == n), None)
            if match:
                return match
        print("    No matching section.")


# ── Print helpers ─────────────────────────────────────────────────

def _print_table(rows: list[SEFSection]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Cycle':<12}  {'Area':<28}  "
          f"J  {'Status':<12}  {'Author':<16}  Approved")
    print("  " + "-" * 100)
    for s in rows:
        print(f"  {s.section_id:>4}  {s.cycle:<12}  "
              f"{s.area[:28]:<28}  "
              f"{s.judgement or '—'}  {s.status:<12}  "
              f"{(s.author or '—')[:16]:<16}  "
              f"{s.approved_on or '—'}")
    print(f"\n  {len(rows)} section(s).")


def _print_full(s: SEFSection) -> None:
    print()
    print(f"    #{s.section_id}  {s.cycle}  — {s.area}")
    print(f"    Judgement     : {s.judgement or '—'}  "
          f"({s.judgement_label})")
    print(f"    Status        : {s.status}")
    print(f"    Author        : {s.author or '—'}")
    print(f"    Reviewer      : {s.reviewer or '—'}")
    print(f"    Approved by   : {s.approved_by or '—'}  "
          f"on {s.approved_on or '—'}")
    print(f"    Last updated  : {s.last_updated}")
    for label, val in (
            ("Summary",                  s.summary_statement),
            ("Strengths",                s.strengths),
            ("Areas to develop",         s.areas_to_develop),
            ("Evidence",                 s.evidence),
            ("Improvement actions",      s.improvement_actions),
    ):
        if val:
            print(f"\n    {label}:")
            for line in val.splitlines():
                print(f"      {line}")


# ── Flows ─────────────────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All SEF Sections ═══")
    _print_table(data.list_sections())
    _pause()


def list_open() -> None:
    print("\n═══ Open (Draft / In Review) ═══")
    _print_table(data.list_sections(open_only=True))
    _pause()


def list_published() -> None:
    print("\n═══ Published ═══")
    _print_table(data.list_sections(published_only=True))
    _pause()


def per_cycle_flow() -> None:
    print("\n═══ Per-Cycle ═══")
    cycles = data.list_cycles()
    if not cycles:
        print("\n  No cycles yet.")
        _pause()
        return
    try:
        cycle = _pick_from("Cycle", cycles, default=cycles[0])
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_table(data.list_sections(cycle=cycle))
    cs = data.cycle_summary(cycle)
    print(f"\n  Cycle {cs.cycle}:")
    print(f"    Sections       : {cs.total}")
    print(f"    Published      : {cs.published}")
    print(f"    Average judge. : "
          f"{cs.average_judgement if cs.average_judgement is not None else '—'}")
    print("    Per-area judgements:")
    for area in AREAS:
        j = cs.judgement_by_area.get(area)
        if j is not None:
            print(f"      {area:<28} : {j}  "
                  f"({judgement_label(j)})")
    _pause()


def view_flow() -> None:
    print("\n═══ View Section ═══")
    try:
        s = _pick_section()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_full(s)
    _pause()


def _collect_form(existing: SEFSection | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["cycle"] = _input(
        "Cycle (e.g. 2025-2026)",
        default=(existing.cycle if is_edit
                  else f"{_date.today().year}-{_date.today().year + 1}"),
        allow_empty=False)
    payload["area"] = _pick_from(
        "Area", list(AREAS),
        default=(existing.area if is_edit else DEFAULT_AREA))
    payload["judgement"] = _input(
        "Judgement (1-4, blank = none)",
        default=(str(existing.judgement)
                  if is_edit and existing.judgement is not None
                  else ""))
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    try:
        payload["summary_statement"] = _multiline(
            "Summary statement",
            default=(existing.summary_statement or "")
            if is_edit else "")
        payload["strengths"] = _multiline(
            "Strengths",
            default=(existing.strengths or "") if is_edit else "")
        payload["areas_to_develop"] = _multiline(
            "Areas to develop",
            default=(existing.areas_to_develop or "")
            if is_edit else "")
        payload["evidence"] = _multiline(
            "Evidence",
            default=(existing.evidence or "") if is_edit else "")
        payload["improvement_actions"] = _multiline(
            "Improvement actions",
            default=(existing.improvement_actions or "")
            if is_edit else "")
    except _UserAbort:
        raise
    payload["author"] = _input(
        "Author",
        default=(existing.author or "") if is_edit else "")
    payload["reviewer"] = _input(
        "Reviewer",
        default=(existing.reviewer or "") if is_edit else "")
    payload["approved_by"] = _input(
        "Approved by",
        default=(existing.approved_by or "") if is_edit else "")
    payload["approved_on"] = _input(
        "Approved on (YYYY-MM-DD)",
        default=(existing.approved_on or "") if is_edit else "")
    return payload


def new_section() -> None:
    print("\n═══ New SEF Section ═══")
    try:
        payload = _collect_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        s = data.create_section(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created #{s.section_id}")
    _pause()


def edit_section() -> None:
    print("\n═══ Edit SEF Section ═══")
    try:
        s = _pick_section()
        payload = _collect_form(s)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_section(s.section_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{s.section_id}")
    _pause()


def submit_for_review_flow() -> None:
    print("\n═══ Submit for Review ═══")
    try:
        s = _pick_section()
        reviewer = _input("Reviewer (optional)",
                            default=s.reviewer or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.submit_for_review(s.section_id,
                                    reviewer=reviewer or None)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{s.section_id} → In Review")
    _pause()


def approve_flow() -> None:
    print("\n═══ Approve ═══")
    try:
        s = _pick_section()
        approved_by = _input("Approved by",
                                default=s.approved_by or "",
                                allow_empty=False)
        when = _input("Approved on (YYYY-MM-DD)",
                        default=_date.today().isoformat())
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.approve(s.section_id, approved_by=approved_by,
                          approved_on=when)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{s.section_id} → Approved")
    _pause()


def publish_flow() -> None:
    print("\n═══ Publish ═══")
    try:
        s = _pick_section()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.publish(s.section_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{s.section_id} → Published")
    _pause()


def archive_flow() -> None:
    print("\n═══ Archive ═══")
    try:
        s = _pick_section()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.archive(s.section_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{s.section_id} → Archived")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        s = _pick_section()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=s.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(s.section_id, new_status)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{s.section_id} → {new_status}")
    _pause()


def delete_flow() -> None:
    print("\n═══ Delete ═══")
    try:
        s = _pick_section()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete #{s.section_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_section(s.section_id):
        print(f"\n  ✓ Deleted #{s.section_id}")
    _pause()


def summary_flow() -> None:
    print("\n═══ SEF Summary ═══")
    s = data.summary()
    print(f"\n  Total              : {s.total}")
    print(f"  Open               : {s.open_count}")
    print(f"  Published          : {s.published}")
    print(f"  Distinct cycles    : {s.distinct_cycles}")
    print(f"  Average judgement  : "
          f"{s.average_judgement if s.average_judgement is not None else '—'}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<14} : {n}")
    print("\n  By area:")
    for k in AREAS:
        n = s.by_area.get(k, 0)
        if n:
            print(f"    {k:<28} : {n}")
    print("\n  By judgement:")
    for j in JUDGEMENTS:
        n = s.by_judgement.get(j, 0)
        if n:
            print(f"    {j}  {judgement_label(j):<24}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",             list_all),
    ("List open",            list_open),
    ("List published",       list_published),
    ("Per cycle",            per_cycle_flow),
    ("View",                 view_flow),
    ("─" * 6,                lambda: None),
    ("New section",          new_section),
    ("Edit section",         edit_section),
    ("Submit for review",    submit_for_review_flow),
    ("Approve",              approve_flow),
    ("Publish",              publish_flow),
    ("Archive",              archive_flow),
    ("Change status",        set_status_flow),
    ("Delete",               delete_flow),
    ("─" * 6,                lambda: None),
    ("Summary",              summary_flow),
]


def run() -> None:
    while True:
        print("\n── SEF Builder ──")
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
            logger.exception("SEF CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "SEF Builder":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("SEF CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
