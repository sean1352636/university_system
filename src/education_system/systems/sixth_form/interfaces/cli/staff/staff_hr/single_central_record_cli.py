"""CLI flows for the single central record (SCR).

Reached from the Staff HR submenu ("Single central record") and, for a
top-level entry, :func:`dispatch` with "Single Central Record". DSL /
HR / admin only — the domain layer refuses everyone else.
"""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Callable

from education_system.systems.sixth_form.domain.staff.staff_hr import (
    single_central_record as scr,
)
from education_system.systems.sixth_form.interfaces.cli.staff.staff_hr.staff_hr_cli import (
    _UserAbort,
    _input,
    _pause,
    _yes_no,
)

logger = logging.getLogger(__name__)


def _pick(label: str, options: tuple[str, ...], default: str = "") -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        print(f"    {'*' if opt == default else ' '}{i:>2}) {opt}")
    while True:
        raw = _input(f"Pick #1..{len(options)}", default=default)
        if raw == default and default:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print("    Enter a number.")


def _print_rows(rows: list[scr.SCRRow]) -> None:
    if not rows:
        print("\n  (no staff)")
        return
    for r in rows:
        print(f"\n  {r.staff_id:<8} {r.name:<28} {r.role:<24} "
              + ("COMPLETE" if r.complete else
                 f"MISSING: {', '.join(r.missing)}"))
        for col in scr.SCR_COLUMNS:
            c = r.checks[col]
            if not c.required and c.state == "N/A":
                continue
            mark = "✗" if c.is_gap else "✓" if c.state == "Done" else "·"
            print(f"      {mark} {col:<26} {c.label:<12} "
                  f"{c.checked_by or '':<20} {c.source}")


def report_flow() -> None:
    print("\n═══ Single Central Record ═══")
    rows = scr.scr_report(include_left=_yes_no("Include leavers?"),
                          missing_only=_yes_no("Missing checks only?"))
    _print_rows(rows)
    _pause()


def summary_flow() -> None:
    s = scr.scr_summary()
    print("\n═══ SCR Summary ═══")
    print(f"  Staff              : {s.staff}")
    print(f"  Complete           : {s.complete}")
    print(f"  With missing checks: {s.with_gaps}")
    for check, n in sorted(s.gaps_by_check.items(), key=lambda kv: -kv[1]):
        print(f"    {check:<26}: {n}")
    _pause()


def staff_flow() -> None:
    sid = _input("Staff ID", allow_empty=False)
    _print_rows([scr.scr_for_staff(sid)])
    print("\n  History:")
    for c in scr.checks_for_staff(sid):
        print(f"    #{c.check_id:<4} {c.checked_on}  {c.check_type:<26} "
              f"{c.outcome:<15} {c.checked_by:<18} {c.reference or ''}"
              + (f"  [VOID: {c.voided_reason}]" if c.voided else ""))
    _pause()


def record_flow() -> None:
    print("\n═══ Record an SCR Check ═══")
    sid = _input("Staff ID", allow_empty=False)
    c = scr.record_check(
        sid, _pick("Check", scr.CHECK_TYPES),
        checked_on=_input("Checked on (YYYY-MM-DD)",
                          default=_date.today().isoformat()),
        checked_by=_input("Checked by (blank = you)"),
        outcome=_pick("Outcome", scr.OUTCOMES, default="Clear"),
        reference=_input("Document / reference (optional)"),
        expires_on=_input("Expires on (optional, e.g. visa)"),
        notes=_input("Notes (optional)"))
    print(f"\n  ✓ {c.check_type} recorded for {c.staff_id}")
    _pause()


def void_flow() -> None:
    raw = _input("Check #", allow_empty=False)
    if not raw.isdigit():
        print("  ✗ Must be a number")
        return
    scr.void_check(int(raw), reason=_input("Reason", allow_empty=False))
    print("  ✓ Voided (kept in the history)")
    _pause()


def profile_flow() -> None:
    sid = _input("Staff ID", allow_empty=False)
    prof = scr.get_profile(sid)
    tri = ("From job title", "Yes", "No")

    def to_tri(s: str) -> bool | None:
        return None if s == tri[0] else s == tri[1]

    def cur(v: bool | None) -> str:
        return tri[0] if v is None else (tri[1] if v else tri[2])

    scr.set_profile(
        sid,
        lived_overseas=_yes_no("Lived or worked overseas?",
                               default=prof.lived_overseas),
        overseas_countries=_input("Countries",
                                  default=prof.overseas_countries or ""),
        teaching_role=to_tri(_pick("Teaching role (prohibition check)", tri,
                                   default=cur(prof.teaching_role))),
        management_role=to_tri(_pick("Management role (section 128)", tri,
                                     default=cur(prof.management_role))),
        notes=_input("Notes", default=prof.notes or ""))
    print("  ✓ Saved")
    _pause()


def export_flow() -> None:
    path = scr.export_scr_csv(include_left=_yes_no("Include leavers?"))
    print(f"\n  ✓ Written to {path}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("SCR report (all staff)", report_flow),
    ("SCR summary", summary_flow),
    ("One staff member", staff_flow),
    ("Record a check", record_flow),
    ("Void a check", void_flow),
    ("Overseas / role facts", profile_flow),
    ("Export CSV", export_flow),
]


def run() -> None:
    if not scr.can_access():
        print("\n  ✗ The single central record is restricted to the DSL, HR "
              "and administrators.")
        _pause()
        return
    while True:
        print("\n── Single Central Record ──")
        for i, (label, _) in enumerate(_MENU, 1):
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
        try:
            _MENU[int(choice) - 1][1]()
        except _UserAbort:
            print("\n  Cancelled.")
        except (scr.ValidationError, scr.access.AccessDenied) as e:
            print(f"\n  ✗ {e}")
            _pause()
        except Exception as e:
            logger.exception("SCR CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Single Central Record":
        return False
    run()
    return True
