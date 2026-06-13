"""CLI handlers for pupil reports."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.primarysch_system.modules.domain.pupil_reports import (
    pupil_reports as data,
)
from education_system.primarysch_system.modules.domain.pupil_reports.pupil_reports import (
    STATUSES, TERMS,
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


def _prompt_multiline(label: str, default: str = "") -> str:
    print(f"  {label} (end with a blank line; leave blank to keep default):")
    if default:
        first = default.splitlines()[0] if default else ""
        more = " (...)" if "\n" in default else ""
        print(f"  [default: {first[:60]}{more}]")
    lines: list[str] = []
    while True:
        try:
            line = input("  > ")
        except (EOFError, KeyboardInterrupt):
            break
        if line == "":
            break
        lines.append(line)
    if not lines:
        return default
    return "\n".join(lines)


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


def _print_table(rows: list[tuple]) -> None:
    if not rows:
        print("  (no reports)")
        return
    print(f"  {'#':<5} {'Pupil':<10} {'Name':<22} {'Yr':<3} "
          f"{'AcYr':<9} {'Term':<7} {'Status':<10} {'Att%':<6} "
          f"{'Published':<11}")
    print(f"  {'-'*5} {'-'*10} {'-'*22} {'-'*3} {'-'*9} {'-'*7} "
          f"{'-'*10} {'-'*6} {'-'*11}")
    for rec, p in rows:
        name = p.full_name if p else "(unknown)"
        yr = p.year_group if p else "-"
        att = "-" if rec.attendance_pct is None else f"{rec.attendance_pct:.1f}"
        print(f"  {rec.report_id:<5} {rec.pupil_id:<10} {name[:22]:<22} "
              f"{yr:<3} {rec.academic_year:<9} {rec.term:<7} "
              f"{rec.status:<10} {att:<6} {(rec.published_on or '-'):<11}")


@_safe
def open_pupil_reports() -> None:
    logger.debug("CLI: open_pupil_reports")
    while True:
        print("\n  -- Pupil Reports --")
        years = data.known_years()
        if years:
            print(f"  Years recorded: {', '.join(years)}")
        print("\n   1) List all reports")
        print("   2) Filter reports")
        print("   3) View report (full text)")
        print("   4) Pupil's reports")
        print("   5) Summary")
        print("   6) Create report (draft)")
        print("   7) Edit draft")
        print("   8) Publish")
        print("   9) Revert to draft")
        print("  10) Delete report")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _list_all,
            "2": _list_filtered,
            "3": _view,
            "4": _view_pupil,
            "5": _summary,
            "6": _create,
            "7": _update,
            "8": _publish,
            "9": _revert,
            "10": _delete,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _list_all() -> None:
    rows = data.list_reports()
    print(f"\n  {len(rows)} report(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _list_filtered() -> None:
    ay = _prompt("  Academic year (blank for any): ").strip() or None
    print(f"  Terms: {', '.join(TERMS)} (blank for any)")
    term = _prompt("  Term: ").strip().title() or None
    print(f"  Statuses: {', '.join(STATUSES)} (blank for any)")
    st = _prompt("  Status: ").strip().lower() or None
    print(f"  Year groups: {', '.join(YEAR_GROUPS)} (blank for any)")
    yg = _prompt("  Pupil year group: ").strip() or None
    rows = data.list_reports(academic_year=ay, term=term,
                             status=st, year_group=yg)
    print(f"\n  {len(rows)} report(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _view() -> None:
    raw = _prompt("  Report ID: ")
    if not raw or not raw.isdigit():
        return
    rec = data.get(int(raw))
    if rec is None:
        print(f"  No report #{raw}")
        return
    print(f"\n  -- Report #{rec.report_id} --")
    print(f"  Pupil:        {rec.pupil_id}")
    print(f"  Year / term:  {rec.academic_year}  {rec.term}")
    print(f"  Status:       {rec.status}")
    print(f"  Authored by:  {rec.authored_by or '-'}")
    print(f"  Published on: {rec.published_on or '-'}")
    att = "-" if rec.attendance_pct is None else f"{rec.attendance_pct:.1f}%"
    print(f"  Attendance:   {att}")
    print(f"  Behaviour:    {rec.behaviour or '-'}")
    print(f"\n  Headline:\n    {rec.headline or '-'}")
    print(f"\n  Summary:\n    {(rec.summary or '-')}")
    print(f"\n  Strengths:\n    {(rec.strengths or '-')}")
    print(f"\n  Next steps:\n    {(rec.next_steps or '-')}")
    print(f"\n  Notes:\n    {(rec.notes or '-')}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _view_pupil() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    rows = data.list_for_pupil(pid)
    print(f"\n  {len(rows)} report(s) for pupil {pid}:")
    if not rows:
        print("    (none)")
    else:
        for r in rows:
            att = "-" if r.attendance_pct is None else f"{r.attendance_pct:.1f}%"
            print(f"    #{r.report_id} {r.academic_year} {r.term}: "
                  f"{r.status}  att={att}  pub={r.published_on or '-'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _summary() -> None:
    ay = _prompt("  Academic year (blank for all): ").strip() or None
    print(f"  Terms: {', '.join(TERMS)} (blank for any)")
    term = _prompt("  Term: ").strip().title() or None
    s = data.summary(academic_year=ay, term=term)
    print(f"\n  -- Summary --")
    print(f"  Total:       {s['total']}")
    print(f"  Draft:       {s['draft']}")
    print(f"  Published:   {s['published']} ({s['published_pct']:.1f}%)")
    if s['average_attendance'] is not None:
        print(f"  Avg attendance (n={s['attendance_count']}): "
              f"{s['average_attendance']:.1f}%")
    _prompt("\n  Press Enter to continue...")


def _collect_short(defaults: dict | None = None) -> dict:
    d = defaults or {}
    out: dict = {}
    out["pupil_id"]      = _prompt(f"  Pupil ID [{d.get('pupil_id','')}]: ") or d.get("pupil_id", "")
    out["academic_year"] = _prompt(f"  Academic year (e.g. 2025-26) [{d.get('academic_year','')}]: ") or d.get("academic_year", "")
    print(f"  Terms: {', '.join(TERMS)}")
    out["term"]          = _prompt(f"  Term [{d.get('term','')}]: ") or d.get("term", "")
    out["headline"]      = _prompt(f"  Headline [{d.get('headline','')}]: ") or d.get("headline", "")
    out["authored_by"]   = _prompt(f"  Authored by [{d.get('authored_by','')}]: ") or d.get("authored_by", "")
    att_default = "" if d.get("attendance_pct") in (None, "") else f"{d['attendance_pct']:g}"
    out["attendance_pct"] = _prompt(f"  Attendance % [{att_default}]: ") or att_default
    out["behaviour"]     = _prompt(f"  Behaviour [{d.get('behaviour','')}]: ") or d.get("behaviour", "")
    out["summary"]       = _prompt_multiline("Summary", d.get("summary", "") or "")
    out["strengths"]     = _prompt_multiline("Strengths", d.get("strengths", "") or "")
    out["next_steps"]    = _prompt_multiline("Next steps", d.get("next_steps", "") or "")
    out["notes"]         = _prompt(f"  Notes [{d.get('notes','')}]: ") or d.get("notes", "")
    return out


@_safe
def _create() -> None:
    print("\n  -- Create Report (draft) --")
    payload = _collect_short()
    payload["status"] = "draft"
    rec = data.create(payload)
    print(f"  Created draft #{rec.report_id}: pupil {rec.pupil_id} "
          f"{rec.academic_year} {rec.term}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _update() -> None:
    raw = _prompt("  Report ID to edit: ")
    if not raw or not raw.isdigit():
        return
    existing = data.get(int(raw))
    if existing is None:
        print(f"  No report #{raw}")
        return
    if existing.is_published:
        print("  Report is published — revert to draft first.")
        return
    defaults = {
        "pupil_id": existing.pupil_id,
        "academic_year": existing.academic_year,
        "term": existing.term,
        "headline": existing.headline or "",
        "summary": existing.summary or "",
        "strengths": existing.strengths or "",
        "next_steps": existing.next_steps or "",
        "attendance_pct": existing.attendance_pct,
        "behaviour": existing.behaviour or "",
        "authored_by": existing.authored_by or "",
        "notes": existing.notes or "",
    }
    payload = _collect_short(defaults)
    payload["status"] = existing.status
    rec = data.update(int(raw), payload)
    print(f"  Updated draft #{rec.report_id}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _publish() -> None:
    raw = _prompt("  Report ID to publish: ")
    if not raw or not raw.isdigit():
        return
    pub_on = _prompt("  Published on YYYY-MM-DD (blank for today): ")
    rec = data.publish(int(raw), published_on=pub_on or None)
    print(f"  Report #{rec.report_id} published on {rec.published_on}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _revert() -> None:
    raw = _prompt("  Report ID to revert to draft: ")
    if not raw or not raw.isdigit():
        return
    rec = data.revert_to_draft(int(raw))
    print(f"  Report #{rec.report_id} reverted to {rec.status}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    raw = _prompt("  Report ID to delete: ")
    if not raw or not raw.isdigit():
        return
    confirm = _prompt(f"  Delete report #{raw}? Type 'DELETE' to confirm: ")
    if confirm != "DELETE":
        print("  Cancelled.")
        return
    ok = data.delete(int(raw))
    print(f"  {'Deleted' if ok else 'No such report'}: #{raw}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Pupil Reports": open_pupil_reports}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching pupil_reports CLI label: %s", label)
    handler()
    return True
