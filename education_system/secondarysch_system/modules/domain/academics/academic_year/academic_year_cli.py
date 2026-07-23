"""CLI flows for Sixth Form Academic Year."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.secondarysch_system.modules.domain.academics.academic_year import (
    academic_year as data,
)
from education_system.secondarysch_system.modules.domain.academics.academic_year.academic_year import (
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


def _pause() -> None:
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


# ── Submenu ───────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Current Year",        show_current),
    ("List Years",          list_all_years),
    ("View Year",           view_year),
    ("New Year",            new_year),
    ("Edit Year",           edit_year),
    ("Set Current Year",    set_current_year),
    ("Delete Year",         delete_year_flow),
    ("─" * 6,               lambda: None),
    ("List Terms",          list_terms_flow),
    ("New Term",            new_term),
    ("Edit Term",           edit_term),
    ("Delete Term",         delete_term_flow),
    ("─" * 6,               lambda: None),
    ("List Breaks",         list_breaks_flow),
    ("New Break",           new_break),
    ("Edit Break",          edit_break),
    ("Delete Break",        delete_break_flow),
    ("─" * 6,               lambda: None),
    ("What's on this date?", lookup_date),
    ("Year Summary",        summary),
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
