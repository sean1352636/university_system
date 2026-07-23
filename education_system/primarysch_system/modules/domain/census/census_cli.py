"""CLI flows for Primary School Census / ILR."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable

from education_system.primarysch_system.modules.domain.census import (
    census as data,
)
from education_system.primarysch_system.modules.domain.census.census import (
    AIM_TYPES,
    CensusReturn,
    DEFAULT_AIM_TYPE,
    DEFAULT_FUNDING_MODEL,
    DEFAULT_LEARNER_AIM_STATUS,
    DEFAULT_RETURN_STATUS,
    DEFAULT_RETURN_TYPE,
    FUNDING_MODELS,
    LearnerAim,
    LEARNER_AIM_STATUSES,
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


def _pick_aim() -> LearnerAim:
    rows = data.list_aims()
    if not rows:
        print("    No aims yet.")
        raise _UserAbort
    print("\n  Aims:")
    for i, a in enumerate(rows, 1):
        print(f"    {i:>3}) #{a.aim_id}  "
              f"{a.learner_ref[:10]:<10}  "
              f"{a.aim_reference[:14]:<14}  "
              f"{(a.aim_title or '—')[:28]:<28}  "
              f"[{a.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            k = int(raw)
            if 1 <= k <= len(rows):
                return rows[k - 1]
            m = next((x for x in rows if x.aim_id == k),
                       None)
            if m:
                return m
        print("    No matching aim.")


def _print_returns(rows: list[CensusReturn]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4} ! {'Type':<22}  {'Year':<8}  "
          f"{'Ref date':<10}  {'Deadline':<10}  "
          f"{'Submitted':<10}  {'Learners':>8}  "
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


def _print_aims(rows: list[LearnerAim]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Learner':<10}  "
          f"{'Ref':<14}  {'Title':<30}  "
          f"{'Model':<28}  {'Start':<10}  "
          f"{'Status':<14}  Hours  Value")
    print("  " + "-" * 150)
    for a in rows:
        print(f"  {a.aim_id:>4}  "
              f"{a.learner_ref[:10]:<10}  "
              f"{a.aim_reference[:14]:<14}  "
              f"{(a.aim_title or '—')[:30]:<30}  "
              f"{a.funding_model[:28]:<28}  "
              f"{a.start_date:<10}  "
              f"{a.status[:14]:<14}  "
              f"{(a.planned_hours or 0):>5}  "
              f"£{(a.funding_band_value or 0):>8,.0f}")
    print(f"\n  {len(rows)} aim(s).")


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
    print(f"    Learner count     : {r.learner_count}")
    print(f"    Errors / Warnings : "
          f"{r.error_count} / {r.warning_count}")
    print(f"    File ref          : {r.file_ref or '—'}")
    if r.notes:
        print("\n    Notes:")
        for line in r.notes.splitlines():
            print(f"      {line}")
    aim_rows = data.aims_for_return(r.return_id)
    if aim_rows:
        print(f"\n    Aims ({len(aim_rows)}):")
        _print_aims(aim_rows)


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
        "Learner count",
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


# ── Aim flows ────────────────────────────────────────────

def list_all_aims() -> None:
    print("\n═══ All Aims ═══")
    _print_aims(data.list_aims())
    _pause()


def list_active_aims() -> None:
    print("\n═══ Active Aims ═══")
    _print_aims(data.list_aims(active_only=True))
    _pause()


def list_aims_for_return_flow() -> None:
    print("\n═══ Aims for a Return ═══")
    try:
        r = _pick_return()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_aims(data.aims_for_return(r.return_id))
    _pause()


def list_aims_for_learner_flow() -> None:
    print("\n═══ Aims for a Learner ═══")
    try:
        ref = _input("Learner ref", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_aims(data.aims_for_learner(ref))
    _pause()


def _collect_aim(existing: LearnerAim | None
                       ) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["return_id"] = _input(
        "Return id (blank = none)",
        default=(str(existing.return_id or "")
                  if is_edit else ""))
    payload["learner_ref"] = _input(
        "Learner ref",
        default=(existing.learner_ref if is_edit else ""),
        allow_empty=False)
    payload["learner_name"] = _input(
        "Learner name",
        default=(existing.learner_name or "")
        if is_edit else "")
    payload["ukprn"] = _input(
        "UKPRN",
        default=(existing.ukprn or "")
        if is_edit else "")
    payload["uln"] = _input(
        "ULN",
        default=(existing.uln or "")
        if is_edit else "")
    payload["aim_type"] = _pick_from(
        "Aim type", list(AIM_TYPES),
        default=(existing.aim_type if is_edit
                  else DEFAULT_AIM_TYPE))
    payload["aim_reference"] = _input(
        "Aim reference",
        default=(existing.aim_reference if is_edit else ""),
        allow_empty=False)
    payload["aim_title"] = _input(
        "Aim title",
        default=(existing.aim_title or "")
        if is_edit else "")
    payload["funding_model"] = _pick_from(
        "Funding model", list(FUNDING_MODELS),
        default=(existing.funding_model if is_edit
                  else DEFAULT_FUNDING_MODEL))
    payload["start_date"] = _input(
        "Start date (YYYY-MM-DD)",
        default=(existing.start_date if is_edit else ""),
        allow_empty=False)
    payload["planned_end_date"] = _input(
        "Planned end date (YYYY-MM-DD)",
        default=(existing.planned_end_date or "")
        if is_edit else "")
    payload["actual_end_date"] = _input(
        "Actual end date (YYYY-MM-DD)",
        default=(existing.actual_end_date or "")
        if is_edit else "")
    payload["completion_code"] = _input(
        "Completion code (1/2/3/6/7/10)",
        default=(str(existing.completion_code or "")
                  if is_edit else ""))
    payload["outcome_code"] = _input(
        "Outcome code",
        default=(existing.outcome_code or "")
        if is_edit else "")
    payload["status"] = _pick_from(
        "Status", list(LEARNER_AIM_STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_LEARNER_AIM_STATUS))
    payload["planned_hours"] = _input(
        "Planned hours",
        default=(str(existing.planned_hours or "")
                  if is_edit else ""))
    payload["actual_hours"] = _input(
        "Actual hours",
        default=(str(existing.actual_hours or "")
                  if is_edit else ""))
    payload["funding_band_value"] = _input(
        "Funding band value",
        default=(str(existing.funding_band_value or "")
                  if is_edit else ""))
    payload["delivery_location"] = _input(
        "Delivery location",
        default=(existing.delivery_location or "")
        if is_edit else "")
    payload["partner_ukprn"] = _input(
        "Partner UKPRN",
        default=(existing.partner_ukprn or "")
        if is_edit else "")
    try:
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "")
            if is_edit else "")
    except _UserAbort:
        raise
    return payload


def new_aim() -> None:
    print("\n═══ New Aim ═══")
    try:
        payload = _collect_aim(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_aim(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created aim #{a.aim_id}")
    _pause()


def edit_aim() -> None:
    print("\n═══ Edit Aim ═══")
    try:
        a = _pick_aim()
        payload = _collect_aim(a)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_aim(a.aim_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{a.aim_id}")
    _pause()


def delete_aim_flow() -> None:
    print("\n═══ Delete Aim ═══")
    try:
        a = _pick_aim()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete aim #{a.aim_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_aim(a.aim_id):
        print(f"\n  ✓ Deleted #{a.aim_id}")
    _pause()


# ── Summary ─────────────────────────────────────────────

def summary_flow() -> None:
    print("\n═══ Census / ILR Summary ═══")
    s = data.summary()
    print(f"\n  Total returns        : {s.total_returns}")
    print(f"  Planned              : {s.planned}")
    print(f"  In progress          : {s.in_progress}")
    print(f"  Submitted            : {s.submitted}")
    print(f"  Accepted             : {s.accepted}")
    print(f"  Rejected             : {s.rejected}")
    print(f"  Overdue              : {s.overdue}")
    print(f"  Open windows         : {s.open_windows}")
    print(f"\n  Total aims           : {s.total_aims}")
    print(f"  Distinct learners    : {s.distinct_learners}")
    print(f"  Continuing           : {s.continuing_aims}")
    print(f"  Completed            : {s.completed_aims}")
    print(f"  Achieved             : {s.achieved_aims}")
    print(f"  Withdrawn            : {s.withdrawn_aims}")
    print(f"  Total planned hours  : {s.total_planned_hours}")
    print(f"  Total funding value  : "
          f"£{s.total_funding_value:,.2f}")
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
    print("\n  By funding model:")
    for k in FUNDING_MODELS:
        n = s.by_funding_model.get(k, 0)
        if n:
            print(f"    {k:<36}: {n}")
    print("\n  By aim status:")
    for k in LEARNER_AIM_STATUSES:
        n = s.by_aim_status.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
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
    ("List all aims",         list_all_aims),
    ("Active aims",           list_active_aims),
    ("Aims for return",       list_aims_for_return_flow),
    ("Aims for learner",      list_aims_for_learner_flow),
    ("New aim",               new_aim),
    ("Edit aim",              edit_aim),
    ("Delete aim",            delete_aim_flow),
    ("─" * 6,                 lambda: None),
    ("Summary",               summary_flow),
]


def run() -> None:
    while True:
        print("\n── Census / ILR ──")
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
            logger.exception("Census/ILR CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "School Census":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Census/ILR CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
