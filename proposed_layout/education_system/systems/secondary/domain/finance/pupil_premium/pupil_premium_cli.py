"""CLI handlers for Pupil Premium."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from education_system.systems.secondary.domain.finance.pupil_premium import (
    pupil_premium as data,
)
from education_system.systems.secondary.domain.finance.pupil_premium.pupil_premium import (
    CATEGORIES, PP_STATUSES, INTERVENTION_STATUSES, IMPACT_RATINGS,
)
from education_system.systems.secondary.domain.learners.pupils.pupils import (
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


def _print_records(rows: list[data.PupilPremiumRecord]) -> None:
    if not rows:
        print("  (no records)")
        return
    print(f"  {'ID':<4} {'AYear':<8} {'Pupil':<10} {'Yr':<3} "
          f"{'Category':<28} {'Status':<11} {'Funding':<10} "
          f"{'Keyworker':<18}")
    print(f"  {'-'*4} {'-'*8} {'-'*10} {'-'*3} {'-'*28} {'-'*11} "
          f"{'-'*10} {'-'*18}")
    for r in rows:
        fund = (f"£{r.funding_amount:.2f}"
                if r.funding_amount is not None else "-")
        print(f"  {r.pp_id:<4} {r.academic_year:<8} {r.pupil_id:<10} "
              f"{(r.pupil_year or '-'):<3} "
              f"{r.category[:28]:<28} {r.status:<11} {fund:<10} "
              f"{(r.keyworker or '-')[:18]:<18}")


def _print_interventions(rows: list[data.PPIntervention]) -> None:
    if not rows:
        print("  (no interventions)")
        return
    print(f"  {'ID':<5} {'Start':<10} {'Status':<10} {'Spend':<10} "
          f"{'Impact':<18} {'Title':<32}")
    print(f"  {'-'*5} {'-'*10} {'-'*10} {'-'*10} {'-'*18} {'-'*32}")
    for i in rows:
        print(f"  {i.intervention_id:<5} {i.start_date:<10} "
              f"{i.status:<10} £{i.spend:<9.2f} "
              f"{i.impact_rating[:18]:<18} "
              f"{i.title[:32]:<32}")


@_safe
def open_pupil_premium() -> None:
    logger.debug("CLI: open_pupil_premium")
    while True:
        print("\n  ── Pupil Premium ──")
        print("  Records")
        print("    1) Set / update eligibility")
        print("    2) List records")
        print("    3) View record + interventions")
        print("    4) Delete record")
        print("  Interventions")
        print("    5) Add intervention")
        print("    6) Edit intervention")
        print("    7) Delete intervention")
        print("  Reports")
        print("    8) Cohort summary")
        print("    0) Back")
        choice = _prompt("  Select: ")
        if choice in ("0", ""):
            return
        actions = {
            "1": _upsert, "2": _list, "3": _view,
            "4": _delete,
            "5": _add_intervention, "6": _edit_intervention,
            "7": _delete_intervention,
            "8": _summary,
        }
        handler = actions.get(choice)
        if handler is None:
            print("  Invalid selection.")
            continue
        handler()


def _collect_record(existing: data.PupilPremiumRecord | None = None
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
    f["category"]      = ask(f"Category ({'/'.join(CATEGORIES)})",
                                  existing.category if existing
                                  else "Ever 6 FSM")
    f["status"]        = ask(f"Status ({'/'.join(PP_STATUSES)})",
                                  existing.status if existing
                                  else "Eligible")
    f["funding_amount"] = ask("Funding amount (£, blank ok)",
                                   existing.funding_amount if existing
                                   else None)
    f["start_date"]    = ask("Start date (YYYY-MM-DD, blank = today)",
                                  existing.start_date if existing
                                  else None)
    f["end_date"]      = ask("End date (YYYY-MM-DD, blank ok)",
                                  existing.end_date if existing
                                  else None)
    f["eligibility_source"] = ask(
        "Eligibility source",
        existing.eligibility_source if existing else None)
    f["keyworker"]     = ask("Keyworker",
                                  existing.keyworker if existing
                                  else None)
    f["notes"]         = ask("Notes",
                                  existing.notes if existing else None)
    return f


@_safe
def _upsert() -> None:
    print("\n  ── Set / Update PP Eligibility ──")
    fields = _collect_record()
    r = data.upsert(fields)
    print(f"  Saved record #{r.pp_id}: {r.pupil_id} "
          f"({r.academic_year}, {r.category}, {r.status})")


@_safe
def _list() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    ay = _prompt("  Academic year (blank): ") or None
    cat = _prompt(f"  Category ({'/'.join(CATEGORIES)}, blank): ") or None
    status = _prompt(f"  Status ({'/'.join(PP_STATUSES)}, blank): ") or None
    pid = _prompt("  Pupil ID (blank): ") or None
    rows = data.list_records(year_group=yg, academic_year=ay,
                               category=cat, status=status,
                               pupil_id=pid)
    print(f"\n  {len(rows)} record(s):")
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
    pp = _ask_id("PP record ID")
    if pp is None:
        return
    s = data.record_summary(pp)
    r = s["record"]
    print(f"\n  ── PP record #{r.pp_id} ──")
    print(f"  Pupil:    {r.pupil_id} ({r.pupil_name or '-'}, "
          f"Yr {r.pupil_year or '-'})")
    print(f"  Year:     {r.academic_year}")
    print(f"  Category: {r.category}    Status: {r.status}")
    print(f"  Funding:  £{r.funding_amount:.2f}"
          if r.funding_amount is not None else "  Funding:  -")
    print(f"  Period:   {r.start_date} → {r.end_date or '-'}")
    print(f"  Source:   {r.eligibility_source or '-'}    "
          f"Keyworker: {r.keyworker or '-'}")
    print(f"  Notes:    {r.notes or '-'}")
    print(f"\n  Interventions: {len(s['interventions'])}    "
          f"Total spend: £{s['total_spend']:.2f}    "
          f"Remaining: "
          f"{('£' + format(s['remaining'], '.2f')) if s['remaining'] is not None else '-'}")
    if s["by_status"]:
        print("  By status: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_status"].items()))
    _print_interventions(s["interventions"])
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    pp = _ask_id("PP record ID")
    if pp is None:
        return
    r = data.get(pp)
    if r is None:
        print("  No record with that ID.")
        return
    confirm = _prompt(
        f"  Delete PP record for {r.pupil_id} ({r.academic_year}) "
        f"and ALL its interventions? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete(pp)
    print(f"  Deleted PP record #{pp}.")


@_safe
def _add_intervention() -> None:
    pp = _ask_id("PP record ID")
    if pp is None:
        return
    if data.get(pp) is None:
        print("  No record with that ID.")
        return
    f: dict[str, Any] = {"pp_id": pp}
    f["title"]         = _prompt("  Title: ")
    f["description"]   = _prompt("  Description: ") or None
    f["spend"]         = _prompt("  Spend (£, blank = 0): ") or None
    f["start_date"]    = _prompt(
        "  Start date (YYYY-MM-DD, blank = today): ") or None
    f["end_date"]      = _prompt(
        "  End date (YYYY-MM-DD, blank): ") or None
    f["status"]        = _prompt(
        f"  Status ({'/'.join(INTERVENTION_STATUSES)}) [Planned]: "
    ) or "Planned"
    f["impact_rating"] = _prompt(
        f"  Impact ({'/'.join(IMPACT_RATINGS)}) [Not yet assessed]: "
    ) or "Not yet assessed"
    f["impact_notes"]  = _prompt("  Impact notes: ") or None
    f["notes"]         = _prompt("  Notes: ") or None
    i = data.add_intervention(f)
    print(f"  Added intervention #{i.intervention_id} (£{i.spend:.2f}, "
          f"{i.status})")


@_safe
def _edit_intervention() -> None:
    iid = _ask_id("Intervention ID")
    if iid is None:
        return
    existing = data.get_intervention(iid)
    if existing is None:
        print("  No intervention with that ID.")
        return

    def ask(label: str, current) -> str:
        suffix = f" [{current}]" if current not in (None, "") else ""
        v = _prompt(f"  {label}{suffix}: ")
        return v if v else (str(current) if current not in (None, "") else "")

    f: dict[str, Any] = {
        "title":         ask("Title", existing.title),
        "description":   ask("Description", existing.description),
        "spend":         ask("Spend (£)", existing.spend),
        "start_date":    ask("Start date", existing.start_date),
        "end_date":      ask("End date", existing.end_date),
        "status":        ask(
            f"Status ({'/'.join(INTERVENTION_STATUSES)})",
            existing.status),
        "impact_rating": ask(
            f"Impact ({'/'.join(IMPACT_RATINGS)})",
            existing.impact_rating),
        "impact_notes":  ask("Impact notes", existing.impact_notes),
        "notes":         ask("Notes", existing.notes),
    }
    i = data.update_intervention(iid, f)
    print(f"  Updated intervention #{i.intervention_id}")


@_safe
def _delete_intervention() -> None:
    iid = _ask_id("Intervention ID")
    if iid is None:
        return
    i = data.get_intervention(iid)
    if i is None:
        print("  No intervention with that ID.")
        return
    confirm = _prompt(
        f"  Delete intervention #{iid} ({i.title})? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    data.delete_intervention(iid)
    print(f"  Deleted intervention #{iid}.")


@_safe
def _summary() -> None:
    yg = _prompt(f"  Year ({'/'.join(YEAR_GROUPS)}, blank): ") or None
    ay = _prompt("  Academic year (blank): ") or None
    s = data.cohort_summary(year_group=yg, academic_year=ay)
    print(f"\n  Records: {s['total']}    "
          f"Funding: £{s['total_funding']:.2f}    "
          f"Spend: £{s['total_spend']:.2f}    "
          f"Remaining: £{s['remaining']:.2f}")
    print(f"  Interventions: {s['interventions']}")
    if s["by_category"]:
        print("  By category:")
        for k, v in sorted(s["by_category"].items(),
                            key=lambda kv: -kv[1]):
            print(f"    {k:<28} {v}")
    if s["by_status"]:
        print("  By status: "
              + "   ".join(f"{k}: {v}"
                            for k, v in s["by_status"].items()))
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Pupil Premium": open_pupil_premium}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching pupil_premium CLI label: %s", label)
    handler()
    return True
