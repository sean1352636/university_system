"""CLI flows for the Primary School Census."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable

from education_system.systems.primary.domain.governance.compliance.census import (
    census as data,
)
from education_system.systems.primary.domain.governance.compliance.census.census import (
    CensusReturn,
    DEFAULT_RETURN_STATUS,
    DEFAULT_RETURN_TYPE,
    RETURN_STATUSES,
    RETURN_TYPES,
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


def _pick_return() -> CensusReturn:
    rows = data.list_returns()
    if not rows:
        print("    No returns yet.")
        raise _UserAbort
    print("\n  Returns:")
    for i, r in enumerate(rows, 1):
        ov = "!" if r.is_overdue else " "
        print(f"    {i:>3}){ov} #{r.return_id}  "
              f"{r.return_type[:22]:<22}  "
              f"{r.academic_year[:8]:<8}  "
              f"deadline {r.submission_deadline or '—':<10}  "
              f"[{r.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            k = int(raw)
            if 1 <= k <= len(rows):
                return rows[k - 1]
            m = next((x for x in rows if x.return_id == k),
                       None)
            if m:
                return m
        print("    No matching return.")


def _print_returns(rows: list[CensusReturn]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4} ! {'Type':<22}  {'Year':<8}  "
          f"{'Ref date':<10}  {'Deadline':<10}  "
          f"{'Submitted':<10}  {'Pupils':>8}  "
          f"{'Errs':>4}  {'Wrns':>4}  {'Status':<12}")
    print("  " + "-" * 130)
    for r in rows:
        ov = "!" if r.is_overdue else " "
        print(f"  {r.return_id:>4} {ov} "
              f"{r.return_type[:22]:<22}  "
              f"{r.academic_year[:8]:<8}  "
              f"{(r.reference_date or '—'):<10}  "
              f"{(r.submission_deadline or '—'):<10}  "
              f"{(r.submitted_on or '—'):<10}  "
              f"{r.learner_count:>8}  "
              f"{r.error_count:>4}  {r.warning_count:>4}  "
              f"{r.status:<12}")
    print(f"\n  {len(rows)} return(s).")


def _print_return_full(r: CensusReturn) -> None:
    print()
    print(f"    #{r.return_id}  {r.return_type}  "
          f"({r.academic_year})")
    print(f"    Reference date    : {r.reference_date or '—'}")
    print(f"    Window            : "
          f"{r.window_opens or '—'}  to  "
          f"{r.window_closes or '—'}"
          + ("  (OPEN NOW)" if r.is_open_window else ""))
    print(f"    Submission due    : "
          f"{r.submission_deadline or '—'}"
          + ("  (OVERDUE)" if r.is_overdue else ""))
    print(f"    Status            : {r.status}")
    print(f"    Submitted on      : {r.submitted_on or '—'}")
    print(f"    Submitted by      : {r.submitted_by or '—'}")
    print(f"    Accepted on       : {r.accepted_on or '—'}")
    print(f"    Pupils on roll    : {r.learner_count}")
    print(f"    Errors / Warnings : "
          f"{r.error_count} / {r.warning_count}")
    print(f"    File ref          : {r.file_ref or '—'}")
    if r.notes:
        print("\n    Notes:")
        for line in r.notes.splitlines():
            print(f"      {line}")


# ── Return flows ─────────────────────────────────────────

def list_all_returns() -> None:
    print("\n═══ All Returns ═══")
    _print_returns(data.list_returns())
    _pause()


def list_overdue() -> None:
    print("\n═══ Overdue Returns ═══")
    _print_returns(data.list_returns(overdue_only=True))
    _pause()


def list_open_window() -> None:
    print("\n═══ Open Submission Windows ═══")
    _print_returns(data.list_returns(open_window_only=True))
    _pause()


def list_by_status(status_label: str) -> Callable[[], None]:
    def _go() -> None:
        print(f"\n═══ {status_label} Returns ═══")
        _print_returns(data.list_returns(status=status_label))
        _pause()
    return _go


def filter_returns_flow() -> None:
    print("\n═══ Filter Returns ═══")
    try:
        rt = _input(f"Type ({'/'.join(RETURN_TYPES[:3])}…)"
                      ) or None
        ay = _input("Academic year (e.g. 2025-26)") or None
        st = _input(f"Status ({'/'.join(RETURN_STATUSES[:3])}…)"
                      ) or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_returns(return_type=rt,
                                          academic_year=ay,
                                          status=st)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_returns(rows)
    _pause()


def view_return_flow() -> None:
    print("\n═══ View Return ═══")
    try:
        r = _pick_return()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_return_full(r)
    _pause()


def _collect_return(existing: CensusReturn | None
                            ) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["return_type"] = _pick_from(
        "Return type", list(RETURN_TYPES),
        default=(existing.return_type if is_edit
                  else DEFAULT_RETURN_TYPE))
    payload["academic_year"] = _input(
        "Academic year (e.g. 2025-26)",
        default=(existing.academic_year if is_edit else ""),
        allow_empty=False)
    payload["reference_date"] = _input(
        "Reference date (YYYY-MM-DD)",
        default=(existing.reference_date or "")
        if is_edit else "")
    payload["window_opens"] = _input(
        "Window opens (YYYY-MM-DD)",
        default=(existing.window_opens or "")
        if is_edit else "")
    payload["window_closes"] = _input(
        "Window closes (YYYY-MM-DD)",
        default=(existing.window_closes or "")
        if is_edit else "")
    payload["submission_deadline"] = _input(
        "Submission deadline (YYYY-MM-DD)",
        default=(existing.submission_deadline or "")
        if is_edit else "")
    payload["status"] = _pick_from(
        "Status", list(RETURN_STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_RETURN_STATUS))
    payload["submitted_on"] = _input(
        "Submitted on (YYYY-MM-DD)",
        default=(existing.submitted_on or "")
        if is_edit else "")
    payload["submitted_by"] = _input(
        "Submitted by",
        default=(existing.submitted_by or "")
        if is_edit else "")
    payload["accepted_on"] = _input(
        "Accepted on (YYYY-MM-DD)",
        default=(existing.accepted_on or "")
        if is_edit else "")
    payload["learner_count"] = _input(
        "Pupils on roll",
        default=(str(existing.learner_count)
                  if is_edit else "0"))
    payload["error_count"] = _input(
        "Error count",
        default=(str(existing.error_count)
                  if is_edit else "0"))
    payload["warning_count"] = _input(
        "Warning count",
        default=(str(existing.warning_count)
                  if is_edit else "0"))
    payload["file_ref"] = _input(
        "File ref",
        default=(existing.file_ref or "")
        if is_edit else "")
    try:
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "")
            if is_edit else "")
    except _UserAbort:
        raise
    return payload


def new_return() -> None:
    print("\n═══ New Return ═══")
    try:
        payload = _collect_return(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.create_return(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created return #{r.return_id}")
    _pause()


def edit_return() -> None:
    print("\n═══ Edit Return ═══")
    try:
        r = _pick_return()
        payload = _collect_return(r)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_return(r.return_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{r.return_id}")
    _pause()


def _action(callable_, action_label: str) -> None:
    print(f"\n═══ {action_label} ═══")
    try:
        r = _pick_return()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        callable_(r.return_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{r.return_id} {action_label.lower()}")
    _pause()


def validate_flow() -> None:
    _action(data.validate_return, "Mark Validated")


def submit_flow() -> None:
    print("\n═══ Submit Return ═══")
    try:
        r = _pick_return()
        by = _input("Submitted by")
        file_ref = _input("File ref")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.submit_return(r.return_id,
                                  submitted_by=by or None,
                                  file_ref=file_ref or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{r.return_id} → Submitted")
    _pause()


def accept_flow() -> None:
    _action(data.accept_return, "Accept")


def reject_flow() -> None:
    _action(data.reject_return, "Reject")


def resubmit_flow() -> None:
    _action(data.resubmit_return, "Resubmit")


def archive_flow() -> None:
    _action(data.archive_return, "Archive")


def validation_counts_flow() -> None:
    print("\n═══ Record Validation Counts ═══")
    try:
        r = _pick_return()
        errs = _input("Errors", default=str(r.error_count))
        wrns = _input("Warnings",
                        default=str(r.warning_count))
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.record_validation_counts(
            r.return_id,
            errors=int(errs), warnings=int(wrns))
    except (ValidationError, ValueError) as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Recorded {errs} errors, {wrns} warnings")
    _pause()


def set_return_status_flow() -> None:
    print("\n═══ Change Return Status ═══")
    try:
        r = _pick_return()
        new_status = _pick_from("New status",
                                  list(RETURN_STATUSES),
                                  default=r.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_return_status(r.return_id, new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{r.return_id} → {new_status}")
    _pause()


def delete_return_flow() -> None:
    print("\n═══ Delete Return ═══")
    try:
        r = _pick_return()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete return #{r.return_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_return(r.return_id):
        print(f"\n  ✓ Deleted #{r.return_id}")
    _pause()


# ── Summary ─────────────────────────────────────────────

def summary_flow() -> None:
    print("\n═══ School Census Summary ═══")
    s = data.summary()
    print(f"\n  Total returns        : {s.total_returns}")
    print(f"  Planned              : {s.planned}")
    print(f"  In progress          : {s.in_progress}")
    print(f"  Submitted            : {s.submitted}")
    print(f"  Accepted             : {s.accepted}")
    print(f"  Rejected             : {s.rejected}")
    print(f"  Overdue              : {s.overdue}")
    print(f"  Open windows         : {s.open_windows}")
    print(f"\n  Pupils on roll       : {s.pupils_on_roll}")
    print("\n  By return type:")
    for k in RETURN_TYPES:
        n = s.by_return_type.get(k, 0)
        if n:
            print(f"    {k:<32}: {n}")
    print("\n  By return status:")
    for k in RETURN_STATUSES:
        n = s.by_return_status.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all returns",      list_all_returns),
    ("Overdue returns",       list_overdue),
    ("Open windows",          list_open_window),
    ("Drafts",                list_by_status("Draft")),
    ("Submitted",             list_by_status("Submitted")),
    ("Accepted",              list_by_status("Accepted")),
    ("Filter returns",        filter_returns_flow),
    ("View return",           view_return_flow),
    ("─" * 6,                 lambda: None),
    ("New return",            new_return),
    ("Edit return",           edit_return),
    ("Mark validated",        validate_flow),
    ("Submit",                submit_flow),
    ("Accept",                accept_flow),
    ("Reject",                reject_flow),
    ("Resubmit",              resubmit_flow),
    ("Archive",               archive_flow),
    ("Record validation cnt", validation_counts_flow),
    ("Change return status",  set_return_status_flow),
    ("Delete return",         delete_return_flow),
    ("─" * 6,                 lambda: None),
    ("Summary",               summary_flow),
]


def run() -> None:
    while True:
        print("\n── School Census ──")
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
            logger.exception("School Census CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "School Census":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("School Census CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
