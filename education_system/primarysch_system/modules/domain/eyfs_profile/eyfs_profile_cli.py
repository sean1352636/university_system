"""CLI handlers for EYFS Profile."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.primarysch_system.modules.domain.eyfs_profile import (
    eyfs_profile as data,
)
from education_system.primarysch_system.modules.domain.eyfs_profile.eyfs_profile import (
    AREAS, ELG_AREAS, ELG_CODES, ELG_GLD, ELG_LABELS, GLD_CODES, STATUSES,
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


def _print_profile(profile, pupil) -> None:
    print(f"\n  -- EYFS Profile: {pupil.full_name} ({pupil.pupil_id}) --")
    print(f"  Year:               {pupil.year_group}")
    print(f"  Academic year:      {profile.academic_year}")
    print(f"  ELGs recorded:      {profile.elgs_recorded}/{profile.elgs_total}")
    print(f"  Expected count:     {profile.expected_count}")
    print(f"  Good Lvl of Dev:    {'YES' if profile.has_gld else 'no'}")
    if not profile.has_gld and profile.gld_missing:
        print(f"  Missing for GLD:    {', '.join(profile.gld_missing)}")
    print()
    for area in AREAS:
        print(f"  {area}")
        for code in ELG_CODES:
            if ELG_AREAS[code] != area:
                continue
            rec = profile.by_code.get(code)
            mark = "[ ]" if rec is None else (
                "[E]" if rec.status == "Expected" else "[e]")
            gld_tag = " *" if ELG_GLD[code] else "  "
            status = (rec.status if rec else "—")
            print(f"    {mark}{gld_tag} {code}  {ELG_LABELS[code]:<42}  "
                  f"{status}")


@_safe
def open_eyfs_profile() -> None:
    logger.debug("CLI: open_eyfs_profile")
    while True:
        print("\n  -- EYFS Profile --")
        years = data.known_years()
        if years:
            print(f"  Years recorded: {', '.join(years)}")
        print("  ELGs marked '*' contribute to Good Level of Development (GLD).")
        print("\n   1) List profiles for a year")
        print("   2) View pupil profile")
        print("   3) Record / update single ELG")
        print("   4) Cohort summary (GLD %)")
        print("   5) Delete a single ELG entry")
        print("   6) Clear entire pupil-year profile")
        print("   7) Show ELG codes")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _list_year,
            "2": _view_profile,
            "3": _set_elg,
            "4": _summary,
            "5": _delete_one,
            "6": _clear_year,
            "7": _show_codes,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _list_year() -> None:
    ay = _prompt("  Academic year: ")
    if not ay:
        return
    rows = data.list_pupils_with_profiles(ay)
    print(f"\n  {len(rows)} pupil(s) with profile records in {ay}:")
    if not rows:
        print("    (none)")
    else:
        print(f"  {'Pupil ID':<10} {'Name':<26} {'Year':<5} "
              f"{'ELGs':<8} {'Exp':<5} {'GLD':<4}")
        print(f"  {'-'*10} {'-'*26} {'-'*5} {'-'*8} {'-'*5} {'-'*4}")
        for pupil, pr in rows:
            print(f"  {pupil.pupil_id:<10} {pupil.full_name[:26]:<26} "
                  f"{pupil.year_group:<5} "
                  f"{pr.elgs_recorded}/{pr.elgs_total:<5} "
                  f"{pr.expected_count:<5} "
                  f"{'yes' if pr.has_gld else 'no':<4}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _view_profile() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    ay = _prompt("  Academic year: ")
    if not ay:
        return
    profile = data.get_profile(pid, ay)
    from education_system.primarysch_system.modules.domain.pupils import pupils as pupils_data
    pupil = pupils_data.get_pupil(pid)
    if pupil is None:
        print(f"  No pupil with id {pid}")
        return
    _print_profile(profile, pupil)
    _prompt("\n  Press Enter to continue...")


@_safe
def _set_elg() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    ay = _prompt("  Academic year (e.g. 2025-26): ")
    if not ay:
        return
    print(f"  ELG codes: {', '.join(ELG_CODES)}")
    code = _prompt("  ELG code: ").strip().upper()
    if not code:
        return
    print(f"  Statuses: {', '.join(STATUSES)}")
    status = _prompt("  Status: ").strip().title()
    assessed_on = _prompt("  Assessed on YYYY-MM-DD (optional): ")
    notes = _prompt("  Notes (optional): ")
    rec = data.set_elg(pid, ay, code, status,
                       assessed_on=assessed_on or None,
                       notes=notes or None)
    print(f"  Recorded {rec.elg_code} for {pid} ({rec.academic_year}) "
          f"-> {rec.status}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _summary() -> None:
    ay = _prompt("  Academic year: ")
    if not ay:
        return
    print(f"  Year groups: {', '.join(YEAR_GROUPS)} (blank for any)")
    yg = _prompt("  Pupil year group: ").strip() or None
    s = data.cohort_summary(ay, year_group=yg)
    print(f"\n  -- {s['academic_year']} cohort summary --")
    print(f"  Pupils with any record: {s['pupils']}")
    print(f"  Complete profiles:      {s['complete_profiles']}")
    print(f"  Good Lvl of Dev (GLD):  {s['gld_count']} ({s['gld_pct']:.1f}%)")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete_one() -> None:
    raw = _prompt("  Result ID to delete: ")
    if not raw or not raw.isdigit():
        return
    confirm = _prompt(f"  Delete result #{raw}? (y/N): ")
    if confirm.lower() != "y":
        print("  Cancelled.")
        return
    ok = data.delete(int(raw))
    print(f"  {'Deleted' if ok else 'No such result'}: #{raw}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _clear_year() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    ay = _prompt("  Academic year: ")
    if not ay:
        return
    confirm = _prompt(f"  Clear ALL EYFS entries for pupil {pid} in {ay}? "
                     f"Type 'CLEAR' to confirm: ")
    if confirm != "CLEAR":
        print("  Cancelled.")
        return
    n = data.clear_pupil_year(pid, ay)
    print(f"  Removed {n} ELG entry(ies).")
    _prompt("\n  Press Enter to continue...")


@_safe
def _show_codes() -> None:
    print("\n  -- Early Learning Goals (ELGs) --")
    for area in AREAS:
        print(f"\n  {area}:")
        for code in ELG_CODES:
            if ELG_AREAS[code] != area:
                continue
            tag = " *GLD" if ELG_GLD[code] else ""
            print(f"    {code}  {ELG_LABELS[code]}{tag}")
    print(f"\n  GLD = 'Expected' in all of: {', '.join(GLD_CODES)}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"EYFS Profile": open_eyfs_profile}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching EYFS CLI label: %s", label)
    handler()
    return True
