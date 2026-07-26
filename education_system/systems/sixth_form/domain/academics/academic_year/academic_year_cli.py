"""CLI flows for Sixth Form Academic Year."""

from __future__ import annotations

import datetime as _dt
import json
import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.academics.academic_year import (
    academic_year as data,
)
from education_system.systems.sixth_form.domain.academics.academic_year.academic_year import (
    AcademicYear,
    Break,
    BREAK_TYPES,
    DEFAULT_BREAK_TYPE,
    DEFAULT_TERM_NAME,
    DEFAULT_YEAR_STATUS,
    Term,
    TERM_NAMES,
    ValidationError,
    YEAR_STATUSES,
)
# Reuse the pure helpers from the views module.
from education_system.systems.sixth_form.domain.academics.academic_year import (
    academic_year_views as _views,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Prompt helpers ─────────────────────────────────────────────────

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
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


# Module-level toggles for --no-pause / --no-color (set by argv entry).
NO_PAUSE: bool = False
NO_COLOR: bool = False


def _pause() -> None:
    if NO_PAUSE:
        return
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _yes_no(prompt: str, *, default: bool = False) -> bool:
    d = "y" if default else "n"
    raw = _input(f"{prompt} (y/n)", default=d).strip().lower()
    return raw in ("y", "yes")


def _pick_from(label: str, options: list[str],
                default: str | None = None,
                allow_custom: bool = False) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt}")
    if allow_custom:
        print("        (or type a custom value)")
    while True:
        raw = _input(f"  Pick #1..{len(options)}", default=default or "")
        if default and raw == default:
            return default
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(options):
                return options[n - 1]
            print("    Out of range.")
            continue
        if allow_custom and raw:
            return raw
        print("    Enter a number (or 'cancel' to abort).")


def _pick_year() -> AcademicYear:
    years = data.list_years()
    if not years:
        print("    No academic years yet.")
        raise _UserAbort
    print("\n  Academic years:")
    for i, y in enumerate(years, 1):
        cur = " *" if y.is_current else "  "
        print(f"    {cur}{i:>3}) #{y.year_id}  {y.name}  "
              f"({y.start_date}..{y.end_date}, {y.status})")
    while True:
        raw = _input(f"  Pick #1..{len(years)} (or year id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(years):
                return years[n - 1]
            match = next((y for y in years if y.year_id == n), None)
            if match:
                return match
        print("    No matching year.")


# ── Print helpers ──────────────────────────────────────────────────

def _print_years(rows: list[AcademicYear]) -> None:
    if not rows:
        print("\n  (no academic years)")
        return
    print()
    print(f"  {'#':>4}  {'Name':<12}  {'Start':<10}  {'End':<10}  "
          f"{'Days':>5}  {'Status':<10}  Current")
    print("  " + "-" * 70)
    for y in rows:
        print(f"  {y.year_id:>4}  {y.name:<12}  "
              f"{y.start_date:<10}  {y.end_date:<10}  "
              f"{y.day_count:>5}  {y.status:<10}  "
              f"{'  *' if y.is_current else '   '}")
    print(f"\n  {len(rows)} year(s).")


def _print_terms(rows: list[Term]) -> None:
    if not rows:
        print("\n  (no terms)")
        return
    print()
    print(f"  {'#':>4}  {'Year#':>5}  {'Name':<14}  "
          f"{'Start':<10}  {'End':<10}  {'Days':>5}")
    print("  " + "-" * 60)
    for t in rows:
        print(f"  {t.term_id:>4}  {t.year_id:>5}  {t.name:<14}  "
              f"{t.start_date:<10}  {t.end_date:<10}  {t.day_count:>5}")
    print(f"\n  {len(rows)} term(s).")


def _print_breaks(rows: list[Break]) -> None:
    if not rows:
        print("\n  (no breaks)")
        return
    print()
    print(f"  {'#':>4}  {'Year#':>5}  {'Name':<22}  "
          f"{'Start':<10}  {'End':<10}  {'Days':>5}  Type")
    print("  " + "-" * 80)
    for b in rows:
        print(f"  {b.break_id:>4}  {b.year_id:>5}  {b.name[:22]:<22}  "
              f"{b.start_date:<10}  {b.end_date:<10}  "
              f"{b.day_count:>5}  {b.type}")
    print(f"\n  {len(rows)} break(s).")


# ── Year flows ─────────────────────────────────────────────────────

def list_all_years() -> None:
    print("\n═══ Academic Years ═══")
    _print_years(data.list_years())
    _pause()


def show_current() -> None:
    print("\n═══ Current Academic Year ═══")
    y = data.current_year()
    if y is None:
        print("\n  (no year flagged current)")
        _pause()
        return
    summ = data.year_summary(y.year_id)
    print(f"\n  #{y.year_id}  {y.name}")
    print(f"  Range          : {y.start_date} → {y.end_date} "
          f"({y.day_count} days)")
    print(f"  Status         : {y.status}")
    print(f"  Teaching days  : {summ.teaching_days}")
    print(f"  Non-teaching   : {summ.non_teaching_days}  "
          f"(weekday breaks / INSET)")
    print(f"  Weekend days   : {summ.weekend_days}")
    print(f"  Terms          : {len(summ.terms)}")
    print(f"  Breaks         : {len(summ.breaks)}")
    if y.notes:
        print("\n  Notes:")
        for line in y.notes.splitlines():
            print(f"    {line}")
    _pause()


def view_year() -> None:
    print("\n═══ View Year ═══")
    try:
        y = _pick_year()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    summ = data.year_summary(y.year_id)
    print()
    print(f"  #{y.year_id}  {y.name}  "
          f"{'(current)' if y.is_current else ''}")
    print(f"  Range          : {y.start_date} → {y.end_date}")
    print(f"  Status         : {y.status}")
    print(f"  Teaching days  : {summ.teaching_days}")
    print(f"  Non-teaching   : {summ.non_teaching_days}")
    print(f"  Weekend days   : {summ.weekend_days}")
    _print_terms(summ.terms)
    _print_breaks(summ.breaks)
    _pause()


def _collect_year_form(existing: AcademicYear | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    if is_edit:
        print(f"\n  Editing year #{existing.year_id}")
    payload["name"] = _input(
        "Name (e.g. 2025/26)",
        default=(existing.name if is_edit else ""),
        allow_empty=False)
    payload["start_date"] = _input(
        "Start date (YYYY-MM-DD)",
        default=(existing.start_date if is_edit else ""),
        allow_empty=False)
    payload["end_date"] = _input(
        "End date (YYYY-MM-DD)",
        default=(existing.end_date if is_edit else ""),
        allow_empty=False)
    payload["status"] = _pick_from(
        "Status", list(YEAR_STATUSES),
        default=(existing.status if is_edit else DEFAULT_YEAR_STATUS))
    payload["is_current"] = _yes_no(
        "Flag as current year?",
        default=(existing.is_current if is_edit else False))
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_year() -> None:
    print("\n═══ New Academic Year ═══")
    try:
        payload = _collect_year_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        y = data.create_year(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created year #{y.year_id} {y.name!r}")
    _pause()


def edit_year() -> None:
    print("\n═══ Edit Year ═══")
    try:
        y = _pick_year()
        payload = _collect_year_form(y)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_year(y.year_id, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated #{y.year_id}")
    _pause()


def set_current_year() -> None:
    print("\n═══ Set Current Year ═══")
    try:
        y = _pick_year()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_current(y.year_id)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Current → #{y.year_id} {y.name!r}")
    _pause()


def delete_year_flow() -> None:
    print("\n═══ Delete Year ═══")
    try:
        y = _pick_year()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(
            f"Delete year #{y.year_id} {y.name!r}? "
            "Also wipes its terms and breaks. Type 'yes'",
            default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_year(y.year_id):
        print(f"\n  ✓ Deleted #{y.year_id}")
    _pause()


# ── Term flows ─────────────────────────────────────────────────────

def list_terms_flow() -> None:
    print("\n═══ Terms ═══")
    try:
        y = _pick_year()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_terms(year_id=y.year_id)
    print(f"\n  Year: #{y.year_id} {y.name}")
    _print_terms(rows)
    _pause()


def _collect_term_form(year: AcademicYear,
                       existing: Term | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"year_id": year.year_id}
    is_edit = existing is not None
    payload["name"] = _pick_from(
        "Term name", list(TERM_NAMES),
        default=(existing.name if is_edit else DEFAULT_TERM_NAME),
        allow_custom=True)
    payload["start_date"] = _input(
        "Start date (YYYY-MM-DD)",
        default=(existing.start_date if is_edit else year.start_date),
        allow_empty=False)
    payload["end_date"] = _input(
        "End date (YYYY-MM-DD)",
        default=(existing.end_date if is_edit else year.end_date),
        allow_empty=False)
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_term() -> None:
    print("\n═══ New Term ═══")
    try:
        y = _pick_year()
        payload = _collect_term_form(y, None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        t = data.create_term(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created term #{t.term_id} {t.name!r}")
    _pause()


def edit_term() -> None:
    print("\n═══ Edit Term ═══")
    try:
        tid = int(_input("Term ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_term(tid)
    if existing is None:
        print(f"  ✗ No term #{tid}")
        _pause()
        return
    year = data.get_year(existing.year_id)
    if year is None:
        print(f"  ✗ Term #{tid} has no year")
        _pause()
        return
    try:
        payload = _collect_term_form(year, existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_term(tid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated term #{tid}")
    _pause()


def delete_term_flow() -> None:
    print("\n═══ Delete Term ═══")
    try:
        tid = int(_input("Term ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_term(tid) is None:
        print(f"  ✗ No term #{tid}")
        _pause()
        return
    if _input(f"Delete term #{tid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_term(tid):
        print(f"\n  ✓ Deleted term #{tid}")
    _pause()


# ── Break flows ────────────────────────────────────────────────────

def list_breaks_flow() -> None:
    print("\n═══ Breaks / Holidays ═══")
    try:
        y = _pick_year()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_breaks(year_id=y.year_id)
    print(f"\n  Year: #{y.year_id} {y.name}")
    _print_breaks(rows)
    _pause()


def _collect_break_form(year: AcademicYear,
                        existing: Break | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"year_id": year.year_id}
    is_edit = existing is not None
    payload["name"] = _input(
        "Name (e.g. 'October half-term')",
        default=(existing.name if is_edit else ""),
        allow_empty=False)
    payload["type"] = _pick_from(
        "Type", list(BREAK_TYPES),
        default=(existing.type if is_edit else DEFAULT_BREAK_TYPE))
    payload["start_date"] = _input(
        "Start date (YYYY-MM-DD)",
        default=(existing.start_date if is_edit else year.start_date),
        allow_empty=False)
    payload["end_date"] = _input(
        "End date (YYYY-MM-DD)",
        default=(existing.end_date if is_edit else year.start_date),
        allow_empty=False)
    payload["notes"] = _input(
        "Notes",
        default=(existing.notes or "") if is_edit else "")
    return payload


def new_break() -> None:
    print("\n═══ New Break ═══")
    try:
        y = _pick_year()
        payload = _collect_break_form(y, None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        b = data.create_break(payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created break #{b.break_id} {b.name!r} ({b.type})")
    _pause()


def edit_break() -> None:
    print("\n═══ Edit Break ═══")
    try:
        bid = int(_input("Break ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    existing = data.get_break(bid)
    if existing is None:
        print(f"  ✗ No break #{bid}")
        _pause()
        return
    year = data.get_year(existing.year_id)
    if year is None:
        print(f"  ✗ Break #{bid} has no year")
        _pause()
        return
    try:
        payload = _collect_break_form(year, existing)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_break(bid, payload)
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Updated break #{bid}")
    _pause()


def delete_break_flow() -> None:
    print("\n═══ Delete Break ═══")
    try:
        bid = int(_input("Break ID", allow_empty=False))
    except (ValueError, _UserAbort):
        print("\n  Cancelled / bad input.")
        return
    if data.get_break(bid) is None:
        print(f"  ✗ No break #{bid}")
        _pause()
        return
    if _input(f"Delete break #{bid}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_break(bid):
        print(f"\n  ✓ Deleted break #{bid}")
    _pause()


# ── Lookup ─────────────────────────────────────────────────────────

def lookup_date() -> None:
    print("\n═══ What's on this date? ═══")
    try:
        s = _input("Date (YYYY-MM-DD)",
                    default=_date.today().isoformat(),
                    allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    cur = data.current_year()
    if cur is None:
        years = data.list_years()
        if not years:
            print("\n  No academic years configured.")
            _pause()
            return
        cur = years[0]
        print(f"\n  (no current year — using #{cur.year_id} {cur.name!r})")
    try:
        term = data.find_term_on(cur.year_id, s)
        brk = data.is_break(cur.year_id, s)
    except ValidationError as e:
        print(f"  ✗ {e}")
        _pause()
        return
    import datetime as _dt
    d = _dt.date.fromisoformat(s)
    weekday = d.strftime("%A")
    print(f"\n  Date    : {s} ({weekday})")
    print(f"  Year    : #{cur.year_id} {cur.name}")
    print(f"  Term    : {term.name if term else '— (outside any term)'}")
    if brk:
        print(f"  Break   : {brk.name} ({brk.type})")
    elif d.weekday() >= 5:
        print("  Status  : Weekend (non-teaching)")
    else:
        print("  Status  : Teaching day")
    _pause()


# ── Summary ────────────────────────────────────────────────────────

def summary() -> None:
    print("\n═══ Academic Year Summary ═══")
    try:
        y = _pick_year()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    summ = data.year_summary(y.year_id)
    print(f"\n  #{y.year_id}  {y.name}  "
          f"({y.start_date} → {y.end_date})")
    print(f"  Status            : {y.status} "
          f"{'(current)' if y.is_current else ''}")
    print(f"  Total days        : {y.day_count}")
    print(f"  Teaching days     : {summ.teaching_days}")
    print(f"  Non-teaching days : {summ.non_teaching_days}")
    print(f"  Weekend days      : {summ.weekend_days}")
    print(f"  Terms             : {len(summ.terms)}")
    print(f"  Breaks            : {len(summ.breaks)}")
    print("\n  Breaks by type:")
    by_type: dict[str, int] = {t: 0 for t in BREAK_TYPES}
    for b in summ.breaks:
        by_type[b.type] = by_type.get(b.type, 0) + 1
    for t in BREAK_TYPES:
        n = by_type.get(t, 0)
        if n:
            print(f"    {t:<14} : {n}")
    _pause()


# ── Year extras (duplicate, archive) ──────────────────────────────

def duplicate_year_flow() -> None:
    print("\n═══ Duplicate Year (+365 days) ═══")
    try:
        src = _pick_year()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        new_name = _views._bump_year_name(src.name)
        new_start = _views._shift_iso(src.start_date, 365)
        new_end = _views._shift_iso(src.end_date, 365)
    except Exception as e:
        print(f"\n  ✗ Can't build new year: {e}")
        _pause()
        return
    print(f"\n  Source : #{src.year_id} {src.name} "
          f"({src.start_date} → {src.end_date})")
    print(f"  New    : {new_name} ({new_start} → {new_end})")
    print("  Status : Planning, is_current=False")
    print("  Cloning terms and breaks shifted by +365 days.")
    if not _yes_no("Proceed?", default=True):
        print("\n  Cancelled.")
        return
    try:
        new_year = data.create_year({
            "name": new_name,
            "start_date": new_start,
            "end_date": new_end,
            "status": "Planning",
            "is_current": False,
            "notes": src.notes,
        })
    except (ValidationError, Exception) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    errs = 0
    for t in data.list_terms(year_id=src.year_id):
        try:
            data.create_term({
                "year_id": new_year.year_id,
                "name": t.name,
                "start_date": _views._shift_iso(t.start_date, 365),
                "end_date": _views._shift_iso(t.end_date, 365),
                "notes": t.notes,
            })
        except ValidationError as e:
            errs += 1
            print(f"    ⚠ skipped term {t.name!r}: {e}")
    for b in data.list_breaks(year_id=src.year_id):
        try:
            data.create_break({
                "year_id": new_year.year_id,
                "name": b.name, "type": b.type,
                "start_date": _views._shift_iso(b.start_date, 365),
                "end_date": _views._shift_iso(b.end_date, 365),
                "notes": b.notes,
            })
        except ValidationError as e:
            errs += 1
            print(f"    ⚠ skipped break {b.name!r}: {e}")
    print(f"\n  ✓ Created #{new_year.year_id} {new_year.name!r}"
          + (f" ({errs} row(s) skipped)" if errs else ""))
    _pause()


def approve_year_flow() -> None:
    print("\n═══ Approve Year (Sign-off) ═══")
    try:
        y = _pick_year()
        approver = _input("Approver name", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        ay = data.approve_year(y.year_id, approver=approver)
    except (ValidationError, Exception) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{ay.year_id} {ay.name!r} approved by "
          f"{ay.approved_by} at {ay.approved_at}")
    _pause()


def unapprove_year_flow() -> None:
    print("\n═══ Remove Year Approval ═══")
    try:
        y = _pick_year()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.unapprove_year(y.year_id)
    except Exception as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Approval cleared for #{y.year_id}")
    _pause()


def set_campus_flow() -> None:
    print("\n═══ Set Year Campus ═══")
    try:
        y = _pick_year()
        campus = _input("Campus id (blank to clear)",
                          default=y.campus_id or "")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        ay = data.update_year(y.year_id, {"campus_id": campus or None})
    except (ValidationError, Exception) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{ay.year_id} campus_id={ay.campus_id!r}")
    _pause()


def archive_year_flow() -> None:
    print("\n═══ Archive / Unarchive Year ═══")
    try:
        y = _pick_year()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if y.status == "Archived":
        new_status = _pick_from(
            "Move from Archived to",
            [s for s in YEAR_STATUSES if s != "Archived"],
            default="Active")
    else:
        new_status = "Archived"
    try:
        data.update_year(y.year_id, {"status": new_status})
    except (ValidationError, Exception) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ #{y.year_id} {y.name!r} → status={new_status}")
    _pause()


# ── Term extras (auto-fill, copy, suggest half-terms, export) ─────

def autofill_terms_flow() -> None:
    print("\n═══ Auto-fill 3 Standard Terms ═══")
    try:
        y = _pick_year()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    plan = _views._split_even_three(y)
    existing = {t.name for t in data.list_terms(year_id=y.year_id)}
    print(f"\n  Year #{y.year_id} {y.name}")
    for name, s, e in plan:
        skip = " (already exists — skip)" if name in existing else ""
        print(f"    • {name:<8} {s} → {e}{skip}")
    if not _yes_no("Create the missing term(s)?", default=True):
        print("\n  Cancelled.")
        return
    added = 0
    for name, s, e in plan:
        if name in existing:
            continue
        try:
            data.create_term({
                "year_id": y.year_id, "name": name,
                "start_date": s, "end_date": e, "notes": None,
            })
            added += 1
        except ValidationError as ex:
            print(f"    ⚠ {name}: {ex}")
    print(f"\n  ✓ Added {added} term(s).")
    _pause()


def suggest_halfterms_flow() -> None:
    print("\n═══ Suggest Half-Terms ═══")
    try:
        y = _pick_year()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    terms = data.list_terms(year_id=y.year_id)
    sugg = _views._suggest_halfterms(y.year_id, terms)
    if not sugg:
        print("\n  No Autumn/Spring/Summer terms to base "
              "suggestions on.")
        _pause()
        return
    existing = {(b.name, b.start_date)
                 for b in data.list_breaks(year_id=y.year_id)}
    new = [s for s in sugg if (s[0], s[1]) not in existing]
    if not new:
        print("\n  All suggestions already exist.")
        _pause()
        return
    print()
    for n, s, e in new:
        print(f"    • {n:<20} {s} → {e}")
    if not _yes_no(f"Insert {len(new)} half-term break(s)?",
                     default=True):
        print("\n  Cancelled.")
        return
    added = 0
    for n, s, e in new:
        try:
            data.create_break({
                "year_id": y.year_id, "name": n,
                "type": "Half-Term",
                "start_date": s, "end_date": e, "notes": None,
            })
            added += 1
        except ValidationError as ex:
            print(f"    ⚠ {n}: {ex}")
    print(f"\n  ✓ Added {added} break(s).")
    _pause()


def copy_terms_flow() -> None:
    print("\n═══ Copy Terms From Another Year ═══")
    years = data.list_years()
    if len(years) < 2:
        print("\n  Need at least two years to copy between.")
        _pause()
        return
    print("\n  DESTINATION year:")
    try:
        dest = _pick_year()
        print("\n  SOURCE year:")
        src = _pick_year()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if src.year_id == dest.year_id:
        print("\n  Source and destination are the same.")
        _pause()
        return
    try:
        shift = (_dt.date.fromisoformat(dest.start_date)
                  - _dt.date.fromisoformat(src.start_date)).days
    except ValueError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    src_terms = data.list_terms(year_id=src.year_id)
    if not src_terms:
        print(f"\n  Source year {src.name!r} has no terms.")
        _pause()
        return
    print(f"\n  Will copy {len(src_terms)} term(s) shifted by "
          f"{shift:+d} day(s). Existing names are skipped.")
    if not _yes_no("Proceed?", default=True):
        print("\n  Cancelled.")
        return
    existing = {t.name for t in data.list_terms(year_id=dest.year_id)}
    added = 0
    for t in src_terms:
        if t.name in existing:
            print(f"    – skipped {t.name!r} (exists)")
            continue
        try:
            data.create_term({
                "year_id": dest.year_id,
                "name": t.name,
                "start_date": _views._shift_iso(t.start_date, shift),
                "end_date": _views._shift_iso(t.end_date, shift),
                "notes": t.notes,
            })
            added += 1
        except ValidationError as ex:
            print(f"    ⚠ {t.name}: {ex}")
    print(f"\n  ✓ Copied {added} term(s).")
    _pause()


def bulk_delete_terms_flow() -> None:
    print("\n═══ Bulk Delete Terms ═══")
    raw = _input("Term IDs (comma-separated)", allow_empty=False)
    ids: list[int] = []
    for tok in raw.replace(" ", "").split(","):
        if not tok:
            continue
        try:
            ids.append(int(tok))
        except ValueError:
            print(f"  ✗ Not a number: {tok!r}")
            _pause()
            return
    if not ids:
        print("\n  Nothing to delete.")
        return
    if _input(f"Delete {len(ids)} term(s)? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    ok = errs = 0
    for tid in ids:
        try:
            if data.delete_term(tid):
                ok += 1
            else:
                print(f"    – #{tid} not found")
        except Exception as e:
            errs += 1
            print(f"    ⚠ #{tid}: {e}")
    print(f"\n  ✓ Deleted {ok}, errors {errs}.")
    _pause()


def export_terms_flow() -> None:
    print("\n═══ Export Terms ═══")
    try:
        y = _pick_year()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    terms = data.list_terms(year_id=y.year_id)
    if not terms:
        print("\n  No terms to export.")
        _pause()
        return
    fmt = _pick_from("Format", ["csv", "ics"], default="csv")
    default_path = f"./terms_{y.name.replace('/', '-')}.{fmt}"
    path = _input("Output path", default=default_path,
                    allow_empty=False)
    try:
        if fmt == "csv":
            _write_terms_csv(path, y, terms)
        else:
            _write_terms_ics(path, y, terms)
    except OSError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Wrote {len(terms)} term(s) to {path}")
    _pause()


def _write_terms_csv(path: str, year: AcademicYear,
                       terms: list[Term]) -> None:
    import csv
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["term_id", "year_id", "name",
                      "start_date", "end_date",
                      "calendar_days", "teaching_days", "notes"])
        for t in terms:
            try:
                td = data.teaching_days_in(
                    year.year_id, date_from=t.start_date,
                    date_to=t.end_date)
            except Exception:
                td = 0
            w.writerow([t.term_id, t.year_id, t.name,
                          t.start_date, t.end_date,
                          t.day_count, td, t.notes or ""])


def _write_terms_ics(path: str, year: AcademicYear,
                       terms: list[Term]) -> None:
    stamp = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SixthForm//AcademicYear//EN",
        "CALSCALE:GREGORIAN",
    ]
    for t in terms:
        try:
            s = _dt.date.fromisoformat(t.start_date)
            e = (_dt.date.fromisoformat(t.end_date)
                   + _dt.timedelta(days=1))
        except ValueError:
            continue
        lines += [
            "BEGIN:VEVENT",
            f"UID:term-{t.term_id}-y{year.year_id}@sixthform",
            f"DTSTAMP:{stamp}",
            f"SUMMARY:{t.name} ({year.name})",
            f"DTSTART;VALUE=DATE:{s.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{e.strftime('%Y%m%d')}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\r\n".join(lines) + "\r\n")


def terms_check_flow() -> None:
    print("\n═══ Term Layout Check ═══")
    try:
        y = _pick_year()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    terms = data.list_terms(year_id=y.year_id)
    if not terms:
        print("\n  No terms.")
        _pause()
        return
    status = _views._classify_terms(y, terms)
    print(f"\n  Year #{y.year_id} {y.name}")
    print(f"  {'#':>4}  {'Name':<14}  {'Start':<10}  "
          f"{'End':<10}  {'Teach':>5}  Status")
    print("  " + "-" * 64)
    issues = 0
    for t in sorted(terms, key=lambda x: x.start_date):
        try:
            td = data.teaching_days_in(
                y.year_id, date_from=t.start_date,
                date_to=t.end_date)
        except Exception:
            td = 0
        s = status.get(t.term_id, "ok")
        if s != "ok":
            issues += 1
        print(f"  {t.term_id:>4}  {t.name:<14}  "
              f"{t.start_date:<10}  {t.end_date:<10}  "
              f"{td:>5}  {_views._STATUS_BADGES.get(s, s)}")
    print(f"\n  {len(terms)} term(s) — {issues} with warnings.")
    _pause()


# ── Break extras (INSET quick, bank holidays, recurring, ics) ─────

def quick_inset_flow() -> None:
    print("\n═══ Add INSET Day ═══")
    try:
        y = _pick_year()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    today = _date.today().isoformat()
    default_date = (today
                     if y.start_date <= today <= y.end_date
                     else y.start_date)
    try:
        name = _input("Name", default="INSET Day", allow_empty=False)
        date = _input("Date (YYYY-MM-DD)",
                        default=default_date, allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        b = data.create_break({
            "year_id": y.year_id, "name": name, "type": "INSET",
            "start_date": date, "end_date": date, "notes": None,
        })
    except (ValidationError, Exception) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Created INSET break #{b.break_id} on {date}")
    _pause()


def import_bank_holidays_flow() -> None:
    print("\n═══ Import UK Bank Holidays ═══")
    try:
        y = _pick_year()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        ys = _dt.date.fromisoformat(y.start_date)
        ye = _dt.date.fromisoformat(y.end_date)
    except ValueError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    candidates = _views._uk_bank_holidays(ys, ye)
    if not candidates:
        print(f"\n  No bank holidays in 2024-2027 table fall within "
              f"{y.name}.")
        _pause()
        return
    existing = {(b.name, b.start_date)
                 for b in data.list_breaks(year_id=y.year_id)}
    new = [(n, d) for (n, d) in candidates
            if (n, d) not in existing]
    if not new:
        print("\n  All bank holidays already exist.")
        _pause()
        return
    print()
    for n, d in new:
        print(f"    • {n:<28} {d}")
    if not _yes_no(f"Import {len(new)} bank holiday(s)?",
                     default=True):
        print("\n  Cancelled.")
        return
    added = 0
    for n, d in new:
        try:
            data.create_break({
                "year_id": y.year_id, "name": n,
                "type": "Bank Holiday",
                "start_date": d, "end_date": d, "notes": None,
            })
            added += 1
        except ValidationError as ex:
            print(f"    ⚠ {n}: {ex}")
    print(f"\n  ✓ Imported {added}.")
    _pause()


def recurring_breaks_flow() -> None:
    print("\n═══ Recurring Break Template ═══")
    try:
        y = _pick_year()
        name = _input("Name prefix", default="PD Afternoon",
                        allow_empty=False)
        btype = _pick_from("Type", list(BREAK_TYPES),
                             default="INSET")
        every = int(_input("Every N weeks", default="1",
                              allow_empty=False))
        dow_lbl = _pick_from(
            "On weekday",
            ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            default="Fri")
        frm = _input("From (YYYY-MM-DD)",
                       default=y.start_date, allow_empty=False)
        to = _input("To (YYYY-MM-DD)",
                      default=y.end_date, allow_empty=False)
    except (_UserAbort, ValueError) as e:
        print(f"\n  Cancelled / bad input: {e}")
        return
    try:
        fd = _dt.date.fromisoformat(frm)
        td = _dt.date.fromisoformat(to)
    except ValueError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    dow_map = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3,
                 "Fri": 4, "Sat": 5, "Sun": 6}
    dow = dow_map[dow_lbl]
    shift = (dow - fd.weekday()) % 7
    cur = fd + _dt.timedelta(days=shift)
    step = _dt.timedelta(days=7 * max(1, every))
    dates: list[_dt.date] = []
    while cur <= td:
        dates.append(cur)
        cur += step
    if not dates:
        print("\n  No dates produced.")
        _pause()
        return
    print(f"\n  Will create {len(dates)} {btype} break(s):")
    for d in dates[:10]:
        print(f"    • {name} — {d.isoformat()} ({d.strftime('%a')})")
    if len(dates) > 10:
        print(f"    …and {len(dates) - 10} more")
    if not _yes_no("Proceed?", default=True):
        print("\n  Cancelled.")
        return
    added = 0
    for d in dates:
        iso = d.isoformat()
        try:
            data.create_break({
                "year_id": y.year_id, "name": name, "type": btype,
                "start_date": iso, "end_date": iso, "notes": None,
            })
            added += 1
        except ValidationError as ex:
            print(f"    ⚠ {iso}: {ex}")
    print(f"\n  ✓ Created {added}.")
    _pause()


def import_ics_flow() -> None:
    print("\n═══ Import Breaks From .ics ═══")
    try:
        y = _pick_year()
        path = _input("Path to .ics file", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    events = _views._parse_ics(text)
    in_range = [(n, s, e) for (n, s, e) in events
                  if not (e < y.start_date or s > y.end_date)]
    if not in_range:
        print(f"\n  No events fall within {y.name}.")
        _pause()
        return
    print()
    for n, s, e in in_range[:10]:
        print(f"    • {n:<28} {s} → {e}")
    if len(in_range) > 10:
        print(f"    …and {len(in_range) - 10} more")
    if not _yes_no(
            f"Import {len(in_range)} as Holiday breaks?",
            default=True):
        print("\n  Cancelled.")
        return
    added = 0
    for n, s, e in in_range:
        try:
            data.create_break({
                "year_id": y.year_id, "name": n, "type": "Holiday",
                "start_date": s, "end_date": e, "notes": None,
            })
            added += 1
        except ValidationError as ex:
            print(f"    ⚠ {n}: {ex}")
    print(f"\n  ✓ Imported {added}.")
    _pause()


def bulk_delete_breaks_flow() -> None:
    print("\n═══ Bulk Delete Breaks ═══")
    raw = _input("Break IDs (comma-separated)", allow_empty=False)
    ids: list[int] = []
    for tok in raw.replace(" ", "").split(","):
        if not tok:
            continue
        try:
            ids.append(int(tok))
        except ValueError:
            print(f"  ✗ Not a number: {tok!r}")
            _pause()
            return
    if not ids:
        return
    if _input(f"Delete {len(ids)} break(s)? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    ok = errs = 0
    for bid in ids:
        try:
            if data.delete_break(bid):
                ok += 1
            else:
                print(f"    – #{bid} not found")
        except Exception as e:
            errs += 1
            print(f"    ⚠ #{bid}: {e}")
    print(f"\n  ✓ Deleted {ok}, errors {errs}.")
    _pause()


def breaks_outside_terms_flow() -> None:
    print("\n═══ Breaks Outside Any Term ═══")
    try:
        y = _pick_year()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    terms = data.list_terms(year_id=y.year_id)
    ranges = [(t.start_date, t.end_date) for t in terms]
    breaks = data.list_breaks(year_id=y.year_id)
    outside = [b for b in breaks
                if not any(not (b.end_date < s or b.start_date > e)
                              for s, e in ranges)]
    if not outside:
        print("\n  All breaks fall within at least one term.")
        _pause()
        return
    _print_breaks(outside)
    _pause()


# ── Window-level (JSON export / import) ───────────────────────────

def export_year_json_flow() -> None:
    print("\n═══ Export Year (JSON) ═══")
    try:
        y = _pick_year()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    terms = data.list_terms(year_id=y.year_id)
    breaks = data.list_breaks(year_id=y.year_id)
    payload = {
        "schema": "sixthform.academic_year/v1",
        "year": {
            "name":       y.name,
            "start_date": y.start_date,
            "end_date":   y.end_date,
            "status":     y.status,
            "is_current": y.is_current,
            "notes":      y.notes,
        },
        "terms": [
            {"name": t.name, "start_date": t.start_date,
              "end_date": t.end_date, "notes": t.notes}
            for t in terms
        ],
        "breaks": [
            {"name": b.name, "type": b.type,
              "start_date": b.start_date, "end_date": b.end_date,
              "notes": b.notes}
            for b in breaks
        ],
    }
    default_path = f"./academic_year_{y.name.replace('/', '-')}.json"
    path = _input("Output path", default=default_path,
                    allow_empty=False)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
    except OSError as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    print(f"\n  ✓ Wrote year {y.name!r} "
          f"({len(terms)} term(s), {len(breaks)} break(s)) to {path}")
    _pause()


def import_year_json_flow() -> None:
    print("\n═══ Import Year (JSON) ═══")
    try:
        path = _input("Path to JSON file", allow_empty=False)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, ValueError) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    if not isinstance(payload, dict) or "year" not in payload:
        print("\n  ✗ File doesn't look like a year export.")
        _pause()
        return
    yp = payload["year"]
    name = yp.get("name", "Imported Year")
    if data.get_year_by_name(name):
        i = 2
        while data.get_year_by_name(f"{name} ({i})"):
            i += 1
        name = f"{name} ({i})"
    print("\n  Will create year:")
    print(f"    Name   : {name}")
    print(f"    Span   : {yp.get('start_date')} → {yp.get('end_date')}")
    print(f"    Terms  : {len(payload.get('terms', []))}")
    print(f"    Breaks : {len(payload.get('breaks', []))}")
    print("    Status : Planning, is_current=False")
    if not _yes_no("Proceed?", default=True):
        print("\n  Cancelled.")
        return
    try:
        new_year = data.create_year({
            "name": name,
            "start_date": yp.get("start_date"),
            "end_date": yp.get("end_date"),
            "status": "Planning",
            "is_current": False,
            "notes": yp.get("notes"),
        })
    except (ValidationError, Exception) as e:
        print(f"\n  ✗ {e}")
        _pause()
        return
    errs = 0
    for t in payload.get("terms", []):
        try:
            data.create_term({
                "year_id": new_year.year_id,
                "name": t.get("name"),
                "start_date": t.get("start_date"),
                "end_date": t.get("end_date"),
                "notes": t.get("notes"),
            })
        except (ValidationError, Exception) as ex:
            errs += 1
            print(f"    ⚠ term {t.get('name')!r}: {ex}")
    for b in payload.get("breaks", []):
        try:
            data.create_break({
                "year_id": new_year.year_id,
                "name": b.get("name"),
                "type": b.get("type", DEFAULT_BREAK_TYPE),
                "start_date": b.get("start_date"),
                "end_date": b.get("end_date"),
                "notes": b.get("notes"),
            })
        except (ValidationError, Exception) as ex:
            errs += 1
            print(f"    ⚠ break {b.get('name')!r}: {ex}")
    print(f"\n  ✓ Created year #{new_year.year_id} {new_year.name!r}"
          + (f" ({errs} row(s) skipped)" if errs else ""))
    _pause()


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Current Year",        show_current),
    ("List Years",          list_all_years),
    ("View Year",           view_year),
    ("New Year",            new_year),
    ("Edit Year",           edit_year),
    ("Set Current Year",    set_current_year),
    ("Duplicate Year (+1)", duplicate_year_flow),
    ("Approve Year (Sign-off)", approve_year_flow),
    ("Unapprove Year", unapprove_year_flow),
    ("Set Year Campus",   set_campus_flow),
    ("Archive / Unarchive Year", archive_year_flow),
    ("Delete Year",         delete_year_flow),
    ("─" * 6,               lambda: None),
    ("List Terms",          list_terms_flow),
    ("New Term",            new_term),
    ("Edit Term",           edit_term),
    ("Delete Term",         delete_term_flow),
    ("Bulk Delete Terms",   bulk_delete_terms_flow),
    ("Auto-fill 3 Terms",   autofill_terms_flow),
    ("Copy Terms From Year", copy_terms_flow),
    ("Term Layout Check",   terms_check_flow),
    ("Export Terms (CSV/ICS)", export_terms_flow),
    ("─" * 6,               lambda: None),
    ("List Breaks",         list_breaks_flow),
    ("New Break",           new_break),
    ("Edit Break",          edit_break),
    ("Delete Break",        delete_break_flow),
    ("Bulk Delete Breaks",  bulk_delete_breaks_flow),
    ("Quick INSET Day",     quick_inset_flow),
    ("Suggest Half-Terms",  suggest_halfterms_flow),
    ("Import UK Bank Holidays", import_bank_holidays_flow),
    ("Recurring Breaks Template", recurring_breaks_flow),
    ("Import .ics → Breaks", import_ics_flow),
    ("Breaks Outside Any Term", breaks_outside_terms_flow),
    ("─" * 6,               lambda: None),
    ("What's on this date?", lookup_date),
    ("Year Summary",        summary),
    ("Export Year (JSON)",  export_year_json_flow),
    ("Import Year (JSON)",  import_year_json_flow),
]


def run() -> None:
    while True:
        print("\n── Academic Year ──")
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
            logger.exception("Academic-year CLI handler crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Academic Year":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Academic-year CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
