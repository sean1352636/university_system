"""CLI handlers for SEND."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.primarysch_system.modules.domain.send import (
    send as data,
)
from education_system.primarysch_system.modules.domain.send.send import (
    PROVISION_STAGES, NEED_CATEGORIES, SEND_STATUSES, REVIEW_OUTCOMES,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
    ValidationError, YEAR_GROUPS,
)

logger = logging.getLogger(__name__)


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _safe(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            print(f"  Validation error: {e}")
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            print(f"  Error: {e}")
            print("  See logs for details.")
    return wrapper


def _print_records(rows: list[data.SENDRecord]) -> None:
    if not rows:
        print("  (no records)")
        return
    print(f"  {'ID':<4} {'AYear':<8} {'Pupil':<10} {'Yr':<3} "
          f"{'Stage':<24} {'Primary need':<32} {'Status':<11} "
          f"{'Next review':<11}")
    print(f"  {'-'*4} {'-'*8} {'-'*10} {'-'*3} {'-'*24} {'-'*32} "
          f"{'-'*11} {'-'*11}")
    for r in rows:
        print(f"  {r.send_id:<4} {r.academic_year:<8} {r.pupil_id:<10} "
              f"{(r.pupil_year or '-'):<3} "
              f"{r.provision_stage[:24]:<24} "
              f"{r.primary_need[:32]:<32} {r.status:<11} "
              f"{(r.next_review_date or '-'):<11}")


def _print_reviews(rows: list[data.SENDReview]) -> None:
    if not rows:
        print("  (no reviews)")
        return
    print(f"  {'ID':<5} {'Date':<10} {'Reviewer':<20} "
          f"{'Outcome':<12} {'Next':<11} {'Progress':<32}")
    print(f"  {'-'*5} {'-'*10} {'-'*20} {'-'*12} {'-'*11} {'-'*32}")
    for r in rows:
        print(f"  {r.review_id:<5} {r.review_date:<10} "
              f"{(r.reviewer or '-')[:20]:<20} "
              f"{r.outcome:<12} {(r.next_review_date or '-'):<11} "
              f"{(r.progress or '-')[:32]:<32}")


@_safe
def open_send() -> None:
    logger.debug("CLI: open_send")
    while True:
        print("\n  ── SEND ──")
        print("  Records")
        print("    1) Add / update SEND record")
        print("    2) List register")
        print("    3) View record + review history")
        print("    4) Delete record")
        print("  Reviews")
        print("    5) Add review")
        print("    6) Delete review")
        print("  Reports")
        print("    7) Cohort summary")
        print("    8) Overdue reviews")
        print("    0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _upsert, "2": _list, "3": _view, "4": _delete,
            "5": _add_review, "6": _delete_review,
            "7": _summary, "8": _overdue,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect_record(existing: data.SENDRecord | None = None
                     ) -> dict[str, Any]:
    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")
    f: dict[str, Any] = {}
    f["pupil_id"]      = ask("Pupil ID",
                                  existing.pupil_id if existing else None)
    f["academic_year"] = ask("Academic year (YYYY/YY)",
                                  existing.academic_year if existing
                                  else None)
    if not existing:
        print("  Provision stages:")
        for s in PROVISION_STAGES:
            print(f"    • {s}")
    f["provision_stage"] = ask("Provision stage",
                                    existing.provision_stage if existing
                                    else None)
    if not existing:
        print("  Need categories:")
        for n in NEED_CATEGORIES:
            print(f"    • {n}")
    f["primary_need"]    = ask("Primary need",
                                    existing.primary_need if existing
                                    else None)
    f["secondary_need"]  = ask("Secondary need (blank ok)",
                                    existing.secondary_need if existing
                                    else None)
    f["status"]          = ask(f"Status ({'/'.join(SEND_STATUSES)})",
                                    existing.status if existing
                                    else "Active")
    f["senco"]           = ask("SENCo",
                                    existing.senco if existing else None)
    f["keyworker"]       = ask("Keyworker",
                                    existing.keyworker if existing
                                    else None)
    f["parent_contact"]  = ask("Parent contact",
                                    existing.parent_contact if existing
                                    else None)
    f["parent_email"]    = ask("Parent email",
                                    existing.parent_email if existing
                                    else None)
    f["ehcp_reference"]  = ask("EHCP reference",
                                    existing.ehcp_reference if existing
                                    else None)
    f["start_date"]      = ask("Start date (YYYY-MM-DD, blank = today)",
                                    existing.start_date if existing
                                    else None)
    f["next_review_date"] = ask(
        "Next review date (YYYY-MM-DD, blank ok)",
        existing.next_review_date if existing else None)
    f["provision_summary"] = ask(
        "Provision summary",
        existing.provision_summary if existing else None)
    f["diagnosis"]       = ask("Diagnosis",
                                    existing.diagnosis if existing
                                    else None)
    f["notes"]           = ask("Notes",
                                    existing.notes if existing else None)
    return f


@_safe
def _upsert() -> None:
    print("\n  ── Add / Update SEND Record ──")
    fields = _collect_record()
    r = data.upsert(fields)
    print(f"  Saved #{r.send_id}: {r.pupil_id} ({r.academic_year}) — "
          f"{r.provision_stage} / {r.primary_need} [{r.status}]")


@_safe
def _list() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    ay = _prompt("  Academic year (blank): ") or None
    stage = _prompt("  Stage (blank): ") or None
    need = _prompt("  Primary need (blank): ") or None
    status = _prompt(f"  Status ({'/'.join(SEND_STATUSES)}, blank): ") or None
    rows = data.list_records(year_group=yg, academic_year=ay,
                               provision_stage=stage,
                               primary_need=need, status=status)
    print(f"\n  {len(rows)} SEND record(s):")
    _print_records(rows)
    _prompt("\n  Press Enter to continue...")


def _ask_id(label: str) -> int | None:
    raw = _prompt(f"  {label}: ")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print(f"  {label} must be a number.")
        return None


@_safe
def _view() -> None:
    sid = _ask_id("SEND record ID")
    if sid is None:
        return
    s = data.record_summary(sid)
    r = s["record"]
    print(f"\n  ── SEND record #{r.send_id} ──")
    print(f"  Pupil:        {r.pupil_id} ({r.pupil_name or '-'}, "
          f"Yr {r.pupil_year or '-'})")
    print(f"  Year:         {r.academic_year}    Status: {r.status}")
    print(f"  Stage:        {r.provision_stage}")
    print(f"  Primary need: {r.primary_need}")
    print(f"  Secondary:    {r.secondary_need or '-'}")
    print(f"  SENCo:        {r.senco or '-'}    "
          f"Keyworker: {r.keyworker or '-'}")
    print(f"  Parent:       {r.parent_contact or '-'} / "
          f"{r.parent_email or '-'}")
    print(f"  EHCP ref:     {r.ehcp_reference or '-'}")
    print(f"  Diagnosis:    {r.diagnosis or '-'}")
    print(f"  Period:       {r.start_date} → next review "
          f"{r.next_review_date or '-'}")
    print(f"  Provision:    {r.provision_summary or '-'}")
    print(f"  Notes:        {r.notes or '-'}")
    print(f"\n  Reviews: {s['review_count']}    "
          f"Last: {s['last_review'] or '-'}")
    if s["by_outcome"]:
        print("  By outcome: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_outcome"].items()))
    _print_reviews(s["reviews"])
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    sid = _ask_id("SEND record ID")
    if sid is None:
        return
    r = data.get(sid)
    if r is None:
        print("  No record with that ID.")
        return
    confirm = _prompt(
        f"  Delete SEND record for {r.pupil_id} ({r.academic_year}) "
        f"and ALL its reviews? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete(sid)
    print(f"  Deleted SEND record #{sid}.")


@_safe
def _add_review() -> None:
    sid = _ask_id("SEND record ID")
    if sid is None:
        return
    if data.get(sid) is None:
        print("  No record with that ID.")
        return
    f: dict[str, Any] = {"send_id": sid}
    f["review_date"] = _prompt(
        "  Review date (YYYY-MM-DD, blank = today): ") or None
    f["reviewer"]    = _prompt("  Reviewer: ") or None
    f["progress"]    = _prompt("  Progress notes: ") or None
    f["adjustments"] = _prompt("  Agreed adjustments: ") or None
    f["outcome"]     = _prompt(
        f"  Outcome ({'/'.join(REVIEW_OUTCOMES)}) [Continue]: "
    ) or "Continue"
    f["next_review_date"] = _prompt(
        "  Next review date (YYYY-MM-DD, blank ok): ") or None
    f["notes"]       = _prompt("  Notes: ") or None
    r = data.add_review(f)
    print(f"  Added review #{r.review_id} ({r.outcome}, next "
          f"{r.next_review_date or '-'})")


@_safe
def _delete_review() -> None:
    rid = _ask_id("Review ID")
    if rid is None:
        return
    r = data.get_review(rid)
    if r is None:
        print("  No review with that ID.")
        return
    confirm = _prompt(f"  Delete review #{rid}? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_review(rid)
    print(f"  Deleted review #{rid}.")


@_safe
def _summary() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    ay = _prompt("  Academic year (blank): ") or None
    s = data.cohort_summary(year_group=yg, academic_year=ay)
    print(f"\n  Total: {s['total']}    "
          f"EHCP-stage: {s['ehcp_count']}")
    if s["by_stage"]:
        print("  By stage:")
        for k, v in sorted(s["by_stage"].items(),
                            key=lambda kv: -kv[1]):
            print(f"    {k:<28} {v}")
    if s["by_primary_need"]:
        print("  By primary need:")
        for k, v in sorted(s["by_primary_need"].items(),
                            key=lambda kv: -kv[1]):
            print(f"    {k:<36} {v}")
    if s["by_status"]:
        print("  By status: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_status"].items()))
    _prompt("\n  Press Enter to continue...")


@_safe
def _overdue() -> None:
    rows = data.overdue_reviews()
    print(f"\n  {len(rows)} Active SEND record(s) with overdue reviews:")
    _print_records(rows)
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"SEND": open_send}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching send CLI label: %s", label)
    handler()
    return True
