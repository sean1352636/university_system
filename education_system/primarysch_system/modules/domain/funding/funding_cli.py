"""CLI flows for Primary School Funding."""

from __future__ import annotations

import logging
from typing import Any, Callable

from education_system.primarysch_system.modules.domain.funding import (
    funding as data,
)
from education_system.primarysch_system.modules.domain.funding.funding import (
    ALLOCATION_STATUSES,
    DEFAULT_ALLOCATION_STATUS,
    DEFAULT_FUNDER,
    DEFAULT_FUNDING_BAND,
    DEFAULT_STREAM_STATUS,
    DEFAULT_STREAM_TYPE,
    FUNDERS,
    FUNDING_BANDS,
    FundingStream,
    LearnerAllocation,
    STREAM_STATUSES,
    STREAM_TYPES,
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


def _pick_stream() -> FundingStream:
    rows = data.list_streams()
    if not rows:
        print("    No streams yet.")
        raise _UserAbort
    print("\n  Streams:")
    for i, s in enumerate(rows, 1):
        over = "!" if s.is_overcommitted else " "
        print(f"    {i:>3}){over} #{s.stream_id}  "
              f"{s.name[:28]:<28}  "
              f"{s.academic_year:<8}  "
              f"£{s.allocated_amount:>12,.0f}  "
              f"[{s.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            k = int(raw)
            if 1 <= k <= len(rows):
                return rows[k - 1]
            m = next((x for x in rows if x.stream_id == k),
                       None)
            if m:
                return m
        print("    No matching stream.")


def _pick_allocation() -> LearnerAllocation:
    rows = data.list_allocations()
    if not rows:
        print("    No allocations yet.")
        raise _UserAbort
    print("\n  Allocations:")
    for i, a in enumerate(rows, 1):
        print(f"    {i:>3}) #{a.allocation_id}  "
              f"{a.learner_ref[:10]:<10}  "
              f"{a.funding_band[:22]:<22}  "
              f"£{a.committed_amount:>10,.2f}  "
              f"draw £{a.drawn_down_amount:>10,.2f}  "
              f"[{a.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            k = int(raw)
            if 1 <= k <= len(rows):
                return rows[k - 1]
            m = next((x for x in rows
                        if x.allocation_id == k), None)
            if m:
                return m
        print("    No matching allocation.")


def _print_streams(rows: list[FundingStream]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4} ! {'Name':<32}  "
          f"{'Type':<24}  {'Funder':<14}  "
          f"{'Year':<8}  {'Allocated':>12}  "
          f"{'Committed':>12}  {'Drawn':>12}  "
          f"{'Util%':>6}  {'Status':<12}")
    print("  " + "-" * 170)
    for s in rows:
        over = "!" if s.is_overcommitted else " "
        print(f"  {s.stream_id:>4} {over} "
              f"{s.name[:32]:<32}  "
              f"{s.stream_type[:24]:<24}  "
              f"{s.funder[:14]:<14}  "
              f"{s.academic_year:<8}  "
              f"£{s.allocated_amount:>11,.0f}  "
              f"£{s.committed_amount:>11,.0f}  "
              f"£{s.drawn_down_amount:>11,.0f}  "
              f"{s.utilisation_pct:>5}%  "
              f"{s.status:<12}")
    print(f"\n  {len(rows)} stream(s).")


def _print_allocations(rows: list[LearnerAllocation]
                                ) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Stream':<6}  {'Learner':<10}  "
          f"{'Band':<22}  {'Start':<10}  "
          f"{'Value':>10}  {'Committed':>10}  "
          f"{'Drawn':>10}  {'Status':<12}")
    print("  " + "-" * 160)
    for a in rows:
        print(f"  {a.allocation_id:>4}  "
              f"{(str(a.stream_id) if a.stream_id else '—'):<6}  "
              f"{a.learner_ref[:10]:<10}  "
              f"{a.funding_band[:22]:<22}  "
              f"{a.starts_on:<10}  "
              f"£{a.band_value:>9,.2f}  "
              f"£{a.committed_amount:>9,.2f}  "
              f"£{a.drawn_down_amount:>9,.2f}  "
              f"{a.status:<12}")
    print(f"\n  {len(rows)} allocation(s).")


def _print_stream_full(s: FundingStream) -> None:
    print()
    print(f"    #{s.stream_id}  {s.name}")
    print(f"    Type             : {s.stream_type}")
    print(f"    Funder           : {s.funder}")
    print(f"    Academic year    : {s.academic_year}")
    print(f"    Reference        : {s.reference or '—'}")
    print(f"    Period           : "
          f"{s.starts_on or '—'} to {s.ends_on or '—'}")
    print(f"    Allocated        : "
          f"£{s.allocated_amount:,.2f}")
    print(f"    Committed        : "
          f"£{s.committed_amount:,.2f}")
    print(f"    Drawn down       : "
          f"£{s.drawn_down_amount:,.2f}")
    print(f"    Remaining        : £{s.remaining:,.2f}"
          + ("  (OVERCOMMITTED)"
              if s.is_overcommitted else ""))
    print(f"    Utilisation      : {s.utilisation_pct}%")
    print(f"    Status           : {s.status}")
    print(f"    Owner            : {s.owner or '—'}")
    if s.notes:
        print(f"\n    Notes:")
        for line in s.notes.splitlines():
            print(f"      {line}")
    rows = data.allocations_for_stream(s.stream_id)
    if rows:
        print(f"\n    Allocations ({len(rows)}):")
        _print_allocations(rows)


# ── Stream flows ─────────────────────────────────────────

def list_all_streams() -> None:
    print("\n═══ All Streams ═══")
    _print_streams(data.list_streams())
    _pause()


def list_active_streams() -> None:
    print("\n═══ Active Streams ═══")
    _print_streams(data.list_streams(active_only=True))
    _pause()


def list_overcommitted() -> None:
    print("\n═══ Overcommitted Streams ═══")
    _print_streams(data.list_streams(
        overcommitted_only=True))
    _pause()


def filter_streams_flow() -> None:
    print("\n═══ Filter Streams ═══")
    try:
        st = _input(
            f"Type ({'/'.join(STREAM_TYPES[:3])}…)"
            ) or None
        funder = _input(
            f"Funder ({'/'.join(FUNDERS[:3])}…)"
            ) or None
        ay = _input("Academic year") or None
        status = _input(
            f"Status ({'/'.join(STREAM_STATUSES[:3])}…)"
            ) or None
        name = _input("Name contains") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        rows = data.list_streams(stream_type=st,
                                          funder=funder,
                                          academic_year=ay,
                                          status=status,
                                          name_like=name)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    _print_streams(rows)
    _pause()


def view_stream_flow() -> None:
    print("\n═══ View Stream ═══")
    try:
        s = _pick_stream()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_stream_full(s)
    _pause()


def _collect_stream(existing: FundingStream | None
                            ) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["name"] = _input(
        "Name",
        default=(existing.name if is_edit else ""),
        allow_empty=False)
    payload["stream_type"] = _pick_from(
        "Type", list(STREAM_TYPES),
        default=(existing.stream_type if is_edit
                  else DEFAULT_STREAM_TYPE))
    payload["funder"] = _pick_from(
        "Funder", list(FUNDERS),
        default=(existing.funder if is_edit
                  else DEFAULT_FUNDER))
    payload["academic_year"] = _input(
        "Academic year (e.g. 2025-26)",
        default=(existing.academic_year if is_edit else ""),
        allow_empty=False)
    payload["reference"] = _input(
        "Reference",
        default=(existing.reference or "")
        if is_edit else "")
    payload["allocated_amount"] = _input(
        "Allocated amount (£)",
        default=(str(existing.allocated_amount)
                  if is_edit else "0"))
    payload["starts_on"] = _input(
        "Starts on (YYYY-MM-DD)",
        default=(existing.starts_on or "")
        if is_edit else "")
    payload["ends_on"] = _input(
        "Ends on (YYYY-MM-DD)",
        default=(existing.ends_on or "")
        if is_edit else "")
    payload["status"] = _pick_from(
        "Status", list(STREAM_STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_STREAM_STATUS))
    payload["owner"] = _input(
        "Owner",
        default=(existing.owner or "") if is_edit else "")
    if is_edit:
        payload["committed_amount"] = existing.committed_amount
        payload["drawn_down_amount"] = (
            existing.drawn_down_amount)
    try:
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "")
            if is_edit else "")
    except _UserAbort:
        raise
    return payload


def new_stream() -> None:
    print("\n═══ New Stream ═══")
    try:
        payload = _collect_stream(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        s = data.create_stream(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created stream #{s.stream_id}")
    _pause()


def edit_stream() -> None:
    print("\n═══ Edit Stream ═══")
    try:
        s = _pick_stream()
        payload = _collect_stream(s)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_stream(s.stream_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{s.stream_id}")
    _pause()


def _stream_action(callable_, label: str) -> None:
    print(f"\n═══ {label} ═══")
    try:
        s = _pick_stream()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        callable_(s.stream_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{s.stream_id} {label.lower()}")
    _pause()


def confirm_stream_flow() -> None:
    _stream_action(data.confirm_stream, "Confirm Stream")


def activate_stream_flow() -> None:
    _stream_action(data.activate_stream, "Activate Stream")


def close_stream_flow() -> None:
    _stream_action(data.close_stream, "Close Stream")


def reconcile_stream_flow() -> None:
    _stream_action(data.reconcile_stream, "Reconcile Stream")


def set_stream_status_flow() -> None:
    print("\n═══ Change Stream Status ═══")
    try:
        s = _pick_stream()
        new_status = _pick_from("New status",
                                  list(STREAM_STATUSES),
                                  default=s.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_stream_status(s.stream_id, new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{s.stream_id} → {new_status}")
    _pause()


def delete_stream_flow() -> None:
    print("\n═══ Delete Stream ═══")
    try:
        s = _pick_stream()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete stream #{s.stream_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_stream(s.stream_id):
        print(f"\n  ✓ Deleted #{s.stream_id}")
    _pause()


# ── Allocation flows ─────────────────────────────────────

def list_all_allocations() -> None:
    print("\n═══ All Allocations ═══")
    _print_allocations(data.list_allocations())
    _pause()


def list_active_allocations() -> None:
    print("\n═══ Active Allocations ═══")
    _print_allocations(data.list_allocations(active_only=True))
    _pause()


def allocations_for_learner_flow() -> None:
    print("\n═══ Allocations for a Learner ═══")
    try:
        ref = _input("Learner ref", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_allocations(data.allocations_for_learner(ref))
    _pause()


def allocations_for_stream_flow() -> None:
    print("\n═══ Allocations for a Stream ═══")
    try:
        s = _pick_stream()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_allocations(data.allocations_for_stream(s.stream_id))
    _pause()


def _collect_allocation(existing: LearnerAllocation | None
                                ) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["stream_id"] = _input(
        "Stream id (blank = none)",
        default=(str(existing.stream_id or "")
                  if is_edit else ""))
    payload["learner_ref"] = _input(
        "Learner ref",
        default=(existing.learner_ref if is_edit else ""),
        allow_empty=False)
    payload["learner_name"] = _input(
        "Learner name",
        default=(existing.learner_name or "")
        if is_edit else "")
    payload["funding_band"] = _pick_from(
        "Funding band", list(FUNDING_BANDS),
        default=(existing.funding_band if is_edit
                  else DEFAULT_FUNDING_BAND))
    payload["band_value"] = _input(
        "Band value (£)",
        default=(str(existing.band_value)
                  if is_edit else "0"))
    payload["committed_amount"] = _input(
        "Committed amount (£)",
        default=(str(existing.committed_amount)
                  if is_edit else "0"))
    payload["drawn_down_amount"] = _input(
        "Drawn-down amount (£)",
        default=(str(existing.drawn_down_amount)
                  if is_edit else "0"))
    payload["starts_on"] = _input(
        "Starts on (YYYY-MM-DD)",
        default=(existing.starts_on if is_edit else ""),
        allow_empty=False)
    payload["ends_on"] = _input(
        "Ends on (YYYY-MM-DD)",
        default=(existing.ends_on or "")
        if is_edit else "")
    payload["status"] = _pick_from(
        "Status", list(ALLOCATION_STATUSES),
        default=(existing.status if is_edit
                  else DEFAULT_ALLOCATION_STATUS))
    payload["purpose"] = _input(
        "Purpose",
        default=(existing.purpose or "")
        if is_edit else "")
    payload["approved_by"] = _input(
        "Approved by",
        default=(existing.approved_by or "")
        if is_edit else "")
    try:
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "")
            if is_edit else "")
    except _UserAbort:
        raise
    return payload


def new_allocation() -> None:
    print("\n═══ New Allocation ═══")
    try:
        payload = _collect_allocation(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a = data.create_allocation(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created allocation #{a.allocation_id}")
    _pause()


def edit_allocation() -> None:
    print("\n═══ Edit Allocation ═══")
    try:
        a = _pick_allocation()
        payload = _collect_allocation(a)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_allocation(a.allocation_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{a.allocation_id}")
    _pause()


def _alloc_action(callable_, label: str) -> None:
    print(f"\n═══ {label} ═══")
    try:
        a = _pick_allocation()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        callable_(a.allocation_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{a.allocation_id} {label.lower()}")
    _pause()


def approve_allocation_flow() -> None:
    print("\n═══ Approve Allocation ═══")
    try:
        a = _pick_allocation()
        by = _input("Approved by",
                      default=a.approved_by or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.approve_allocation(a.allocation_id,
                                          approved_by=by or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{a.allocation_id} → Approved")
    _pause()


def activate_allocation_flow() -> None:
    _alloc_action(data.activate_allocation,
                       "Activate Allocation")


def suspend_allocation_flow() -> None:
    _alloc_action(data.suspend_allocation,
                       "Suspend Allocation")


def close_allocation_flow() -> None:
    _alloc_action(data.close_allocation, "Close Allocation")


def withdraw_allocation_flow() -> None:
    _alloc_action(data.withdraw_allocation,
                       "Withdraw Allocation")


def drawdown_flow() -> None:
    print("\n═══ Record Drawdown ═══")
    try:
        a = _pick_allocation()
        amt = _input("Drawdown amount (£)",
                       allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        a2 = data.record_drawdown(a.allocation_id,
                                            amount=float(amt))
    except (ValidationError, ValueError) as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Drawn £{amt}; total drawn "
          f"£{a2.drawn_down_amount:,.2f}, "
          f"remaining £{a2.remaining:,.2f}, "
          f"status {a2.status}")
    _pause()


def set_allocation_status_flow() -> None:
    print("\n═══ Change Allocation Status ═══")
    try:
        a = _pick_allocation()
        new_status = _pick_from("New status",
                                  list(ALLOCATION_STATUSES),
                                  default=a.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_allocation_status(a.allocation_id,
                                              new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{a.allocation_id} → {new_status}")
    _pause()


def delete_allocation_flow() -> None:
    print("\n═══ Delete Allocation ═══")
    try:
        a = _pick_allocation()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete allocation #{a.allocation_id}? "
              "Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_allocation(a.allocation_id):
        print(f"\n  ✓ Deleted #{a.allocation_id}")
    _pause()


# ── Summary ─────────────────────────────────────────────

def summary_flow() -> None:
    print("\n═══ Funding Summary ═══")
    s = data.summary()
    print(f"\n  Total streams        : {s.total_streams}")
    print(f"  Planned              : {s.planned}")
    print(f"  Active               : {s.active}")
    print(f"  Closed/Reconciled    : {s.closed}")
    print(f"  Overcommitted        : {s.overcommitted}")
    print(f"\n  Total allocated      : "
          f"£{s.total_allocated:,.2f}")
    print(f"  Total committed      : "
          f"£{s.total_committed:,.2f}")
    print(f"  Total drawn down     : "
          f"£{s.total_drawn_down:,.2f}")
    print(f"  Total remaining      : "
          f"£{s.total_remaining:,.2f}")
    print(f"  Avg utilisation      : "
          f"{s.avg_utilisation_pct}%")
    print(f"\n  Total allocations    : {s.total_allocations}")
    print(f"  Distinct learners    : {s.distinct_learners}")
    print("\n  By stream type:")
    for k in STREAM_TYPES:
        n = s.by_stream_type.get(k, 0)
        if n:
            print(f"    {k:<36}: {n}")
    print("\n  By funder:")
    for k in FUNDERS:
        n = s.by_funder.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By stream status:")
    for k in STREAM_STATUSES:
        n = s.by_stream_status.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    print("\n  By band:")
    for k in FUNDING_BANDS:
        n = s.by_band.get(k, 0)
        if n:
            print(f"    {k:<26}: {n}")
    print("\n  By allocation status:")
    for k in ALLOCATION_STATUSES:
        n = s.by_allocation_status.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List streams",         list_all_streams),
    ("Active streams",       list_active_streams),
    ("Overcommitted",        list_overcommitted),
    ("Filter streams",       filter_streams_flow),
    ("View stream",          view_stream_flow),
    ("─" * 6,                lambda: None),
    ("New stream",           new_stream),
    ("Edit stream",          edit_stream),
    ("Confirm stream",       confirm_stream_flow),
    ("Activate stream",      activate_stream_flow),
    ("Close stream",         close_stream_flow),
    ("Reconcile stream",     reconcile_stream_flow),
    ("Change stream status", set_stream_status_flow),
    ("Delete stream",        delete_stream_flow),
    ("─" * 6,                lambda: None),
    ("List allocations",     list_all_allocations),
    ("Active allocations",   list_active_allocations),
    ("Allocs for learner",   allocations_for_learner_flow),
    ("Allocs for stream",    allocations_for_stream_flow),
    ("New allocation",       new_allocation),
    ("Edit allocation",      edit_allocation),
    ("Approve allocation",   approve_allocation_flow),
    ("Activate allocation",  activate_allocation_flow),
    ("Suspend allocation",   suspend_allocation_flow),
    ("Close allocation",     close_allocation_flow),
    ("Withdraw allocation",  withdraw_allocation_flow),
    ("Record drawdown",      drawdown_flow),
    ("Change alloc status",  set_allocation_status_flow),
    ("Delete allocation",    delete_allocation_flow),
    ("─" * 6,                lambda: None),
    ("Summary",              summary_flow),
]


def run() -> None:
    while True:
        print("\n── Funding ──")
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
            logger.exception("Funding CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Funding":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Funding CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
