"""CLI handlers for medical records."""

from __future__ import annotations

import functools
import logging
from typing import Callable

from education_system.systems.primary.domain.pastoral.health.medical_records import (
    medical_records as data,
)
from education_system.systems.primary.domain.pastoral.health.medical_records.medical_records import (
    RECORD_TYPES, RECORD_TYPE_LABELS, SEVERITIES, SEVERITY_LABELS,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
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


def _print_table(rows: list[tuple]) -> None:
    if not rows:
        print("  (no records)")
        return
    print(f"  {'#':<5} {'Pupil':<10} {'Name':<22} {'Yr':<3} "
          f"{'Type':<12} {'Severity':<9} {'Title':<28} {'Active':<6}")
    print(f"  {'-'*5} {'-'*10} {'-'*22} {'-'*3} {'-'*12} {'-'*9} "
          f"{'-'*28} {'-'*6}")
    for rec, p in rows:
        name = p.full_name if p else "(unknown)"
        yr = p.year_group if p else "-"
        sev = rec.severity.upper() if rec.is_critical else rec.severity
        print(f"  {rec.record_id:<5} {rec.pupil_id:<10} {name[:22]:<22} "
              f"{yr:<3} {rec.record_type:<12} {sev:<9} "
              f"{rec.title[:28]:<28} {'yes' if rec.is_active else 'no':<6}")


@_safe
def open_medical() -> None:
    logger.debug("CLI: open_medical")
    while True:
        print("\n  -- Medical Records --")
        try:
            s = data.summary()
        except Exception:
            s = {"total": 0, "active": 0, "critical_active": 0,
                 "pupils_with_records": 0}
        print(f"  Active: {s['active']}/{s['total']}   "
              f"Critical (active): {s['critical_active']}   "
              f"Pupils with records: {s['pupils_with_records']}")
        print("\n   1) List active records")
        print("   2) List ALL records (incl. inactive)")
        print("   3) List CRITICAL records")
        print("   4) Filter records")
        print("   5) Search by title / text")
        print("   6) View pupil's records")
        print("   7) View record")
        print("   8) Create record")
        print("   9) Update record")
        print("  10) Toggle active")
        print("  11) Delete record")
        print("  12) Show types / severities")
        print("   0) Back")
        choice = _prompt("  Select: ")
        if choice == "0" or choice == "":
            return
        actions = {
            "1": _list_active,
            "2": _list_all,
            "3": _list_critical,
            "4": _filter,
            "5": _search,
            "6": _view_pupil,
            "7": _view,
            "8": _create,
            "9": _update,
            "10": _toggle,
            "11": _delete,
            "12": _show_help,
        }
        action = actions.get(choice)
        if action is None:
            print("  Invalid selection.")
            continue
        action()


@_safe
def _list_active() -> None:
    rows = data.list_records(active_only=True)
    print(f"\n  {len(rows)} active record(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _list_all() -> None:
    rows = data.list_records()
    print(f"\n  {len(rows)} record(s) total:")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _list_critical() -> None:
    rows = data.list_records(active_only=True, critical_only=True)
    print(f"\n  {len(rows)} active CRITICAL record(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _filter() -> None:
    print(f"  Types: {', '.join(RECORD_TYPES)} (blank for any)")
    rt = _prompt("  Type: ").strip().lower() or None
    print(f"  Severities: {', '.join(SEVERITIES)} (blank for any)")
    sev = _prompt("  Severity: ").strip().lower() or None
    print(f"  Year groups: {', '.join(YEAR_GROUPS)} (blank for any)")
    yg = _prompt("  Pupil year group: ").strip() or None
    pid = _prompt("  Pupil ID (blank for any): ").strip() or None
    active_only = _prompt("  Active only? (y/N): ").lower() == "y"
    rows = data.list_records(record_type=rt, severity=sev,
                             pupil_id=pid, year_group=yg,
                             active_only=active_only)
    print(f"\n  {len(rows)} record(s):")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _search() -> None:
    q = _prompt("  Search text: ")
    if not q:
        return
    rows = data.list_records(search=q)
    print(f"\n  {len(rows)} match(es) for {q!r}:")
    _print_table(rows)
    _prompt("\n  Press Enter to continue...")


@_safe
def _view_pupil() -> None:
    pid = _prompt("  Pupil ID: ")
    if not pid:
        return
    active_only = _prompt("  Active only? (y/N): ").lower() == "y"
    rows = data.list_for_pupil(pid, active_only=active_only)
    print(f"\n  {len(rows)} record(s) for pupil {pid}:")
    if not rows:
        print("    (none)")
    else:
        for r in rows:
            sev = r.severity.upper() if r.is_critical else r.severity
            print(f"    #{r.record_id} [{r.record_type}] {r.title}  "
                  f"({sev}, {'active' if r.is_active else 'inactive'})")
    _prompt("\n  Press Enter to continue...")


@_safe
def _view() -> None:
    raw = _prompt("  Record ID: ")
    if not raw or not raw.isdigit():
        return
    rec = data.get(int(raw))
    if rec is None:
        print(f"  No record #{raw}")
        return
    print(f"\n  -- Medical record #{rec.record_id} --")
    print(f"  Pupil:        {rec.pupil_id}")
    print(f"  Type:         {rec.record_type} ({RECORD_TYPE_LABELS[rec.record_type]})")
    print(f"  Title:        {rec.title}")
    print(f"  Severity:     {rec.severity} ({SEVERITY_LABELS[rec.severity]})")
    print(f"  Active:       {'yes' if rec.is_active else 'no'}")
    print(f"  Dates:        {rec.start_date or '-'} -> {rec.end_date or '-'}")
    print(f"  Contact:      {rec.contact_name or '-'}   "
          f"{rec.contact_phone or '-'}")
    print(f"\n  Description:\n    {rec.description or '-'}")
    print(f"\n  Action plan:\n    {rec.action_plan or '-'}")
    print(f"\n  Notes:\n    {rec.notes or '-'}")
    _prompt("\n  Press Enter to continue...")


def _collect(defaults: dict | None = None) -> dict:
    d = defaults or {}
    print(f"  (Types: {', '.join(RECORD_TYPES)})")
    print(f"  (Severities: {', '.join(SEVERITIES)})")
    out: dict = {}
    out["pupil_id"]      = _prompt(f"  Pupil ID [{d.get('pupil_id','')}]: ") or d.get("pupil_id", "")
    out["record_type"]   = _prompt(f"  Type [{d.get('record_type','')}]: ") or d.get("record_type", "")
    out["title"]         = _prompt(f"  Title [{d.get('title','')}]: ") or d.get("title", "")
    out["description"]   = _prompt(f"  Description [{d.get('description','')}]: ") or d.get("description", "")
    out["severity"]      = _prompt(f"  Severity [{d.get('severity','low')}]: ") or d.get("severity", "low")
    out["start_date"]    = _prompt(f"  Start date YYYY-MM-DD [{d.get('start_date','')}]: ") or d.get("start_date", "")
    out["end_date"]      = _prompt(f"  End date YYYY-MM-DD [{d.get('end_date','')}]: ") or d.get("end_date", "")
    out["action_plan"]   = _prompt(f"  Action plan [{d.get('action_plan','')}]: ") or d.get("action_plan", "")
    out["contact_name"]  = _prompt(f"  Contact name [{d.get('contact_name','')}]: ") or d.get("contact_name", "")
    out["contact_phone"] = _prompt(f"  Contact phone [{d.get('contact_phone','')}]: ") or d.get("contact_phone", "")
    out["notes"]         = _prompt(f"  Notes [{d.get('notes','')}]: ") or d.get("notes", "")
    return out


@_safe
def _create() -> None:
    print("\n  -- Create Medical Record --")
    payload = _collect()
    rec = data.create(payload)
    print(f"  Created record #{rec.record_id} for pupil {rec.pupil_id} "
          f"({rec.record_type}, {rec.severity})")
    _prompt("\n  Press Enter to continue...")


@_safe
def _update() -> None:
    raw = _prompt("  Record ID to update: ")
    if not raw or not raw.isdigit():
        return
    existing = data.get(int(raw))
    if existing is None:
        print(f"  No record #{raw}")
        return
    defaults = {
        "pupil_id": existing.pupil_id,
        "record_type": existing.record_type,
        "title": existing.title,
        "description": existing.description or "",
        "severity": existing.severity,
        "start_date": existing.start_date or "",
        "end_date": existing.end_date or "",
        "action_plan": existing.action_plan or "",
        "contact_name": existing.contact_name or "",
        "contact_phone": existing.contact_phone or "",
        "notes": existing.notes or "",
    }
    payload = _collect(defaults)
    rec = data.update(int(raw), payload)
    print(f"  Updated record #{rec.record_id}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _toggle() -> None:
    raw = _prompt("  Record ID to toggle: ")
    if not raw or not raw.isdigit():
        return
    rec = data.toggle_active(int(raw))
    print(f"  Record #{rec.record_id} -> "
          f"{'active' if rec.is_active else 'inactive'}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _delete() -> None:
    raw = _prompt("  Record ID to delete: ")
    if not raw or not raw.isdigit():
        return
    confirm = _prompt(f"  Delete record #{raw}? Type 'DELETE' to confirm: ")
    if confirm != "DELETE":
        print("  Cancelled.")
        return
    ok = data.delete(int(raw))
    print(f"  {'Deleted' if ok else 'No such record'}: #{raw}")
    _prompt("\n  Press Enter to continue...")


@_safe
def _show_help() -> None:
    print("\n  -- Record types --")
    for t in RECORD_TYPES:
        print(f"   {t:<14} {RECORD_TYPE_LABELS[t]}")
    print("\n  -- Severities --")
    for s in SEVERITIES:
        print(f"   {s:<9} {SEVERITY_LABELS[s]}")
    _prompt("\n  Press Enter to continue...")


_DISPATCH = {"Medical Records": open_medical}


def dispatch(label: str) -> bool:
    handler = _DISPATCH.get(label)
    if handler is None:
        return False
    logger.debug("Dispatching medical CLI label: %s", label)
    handler()
    return True
