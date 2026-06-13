"""CLI flows for Work Experience & Placements."""

from __future__ import annotations

import logging
from typing import Callable

from education_system.sixthform_system.modules.domain.academics.work_experience import (
    work_experience as data,
)
from education_system.sixthform_system.modules.domain.academics.work_experience.work_experience import (
    DEFAULT_PLACEMENT_STATUS,
    DEFAULT_SECTOR,
    Employer,
    PLACEMENT_STATUSES,
    Placement,
    SECTORS,
    ValidationError,
)
from education_system.sixthform_system.modules.domain.students.students import (
    students as _students,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


# ── Input helpers ────────────────────────────────────────────────

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
    raw = _input(f"{prompt} (y/n)",
                  default="y" if default else "n").strip().lower()
    return raw in ("y", "yes")


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
        print(f"    {marker}{i:>2}) {opt or '(none)'}")
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


def _pick_student() -> str:
    rows = _students.list_students()
    if not rows:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(rows, 1):
        full = f"{getattr(s, 'first_name', '')} " \
               f"{getattr(s, 'last_name', '')}".strip()
        print(f"    {i:>3}) {s.student_id:<12}  {full}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].student_id
        match = next((s for s in rows if s.student_id == raw), None)
        if match:
            return match.student_id
        print("    No matching student.")


def _pick_employer() -> Employer:
    rows = data.list_employers()
    if not rows:
        print("    No employers in directory yet. Add one first.")
        raise _UserAbort
    print("\n  Employers:")
    for i, e in enumerate(rows, 1):
        print(f"    {i:>3}) #{e.employer_id:<4}  "
              f"{e.name[:34]:<34}  {e.sector}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or employer id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows if r.employer_id == n), None)
            if match:
                return match
        print("    No matching employer.")


def _pick_placement() -> Placement:
    rows = data.list_placements()
    if not rows:
        print("    No placements yet.")
        raise _UserAbort
    snames = {s.student_id: s.full_name for s in _students.list_students()}
    emp_names = {e.employer_id: e.name for e in data.list_employers()}
    print("\n  Placements:")
    for i, p in enumerate(rows, 1):
        student = snames.get(p.student_id, "(unknown)")
        emp = emp_names.get(p.employer_id, "(?)")
        print(f"    {i:>3}) #{p.placement_id:<4}  {p.student_id:<10}  "
              f"{student[:18]:<18}  {emp[:24]:<24}  "
              f"{p.start_date}..{p.end_date}  [{p.status}]")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or placement id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows if r.placement_id == n), None)
            if match:
                return match
        print("    No matching placement.")


# ── Rendering ────────────────────────────────────────────────────

def _print_placement_table(rows: list[data.PlacementRow]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Student':<10} {'Name':<18}  {'Employer':<24}  "
          f"{'Role':<18}  {'Start':<10} {'End':<10}  "
          f"{'Hrs':>9}  {'Status':<11}  Flags")
    print("  " + "-" * 140)
    for r in rows:
        p = r.placement
        flags = []
        if not p.parental_consent and p.status != "Cancelled":
            flags.append("CONS")
        if not p.risk_assessment_done and p.status != "Cancelled":
            flags.append("RISK")
        hours_str = (f"{p.hours_completed:>4.0f}/"
                     f"{p.hours_required:.0f}"
                     if p.hours_required else f"{p.hours_completed:>4.0f}/—")
        print(f"  {p.placement_id:>4}  {p.student_id:<10} "
              f"{r.student_name[:18]:<18}  "
              f"{r.employer_name[:24]:<24}  "
              f"{(p.role or '—')[:18]:<18}  "
              f"{p.start_date:<10} {p.end_date:<10}  "
              f"{hours_str:>9}  {p.status:<11}  "
              f"{','.join(flags)}")
    print(f"\n  {len(rows)} placement(s).")


def _print_placement_full(p: Placement) -> None:
    emp = data.get_employer(p.employer_id)
    s = _students.get_student(p.student_id)
    student_name = (getattr(s, "full_name", None) or "(unknown)")
    print()
    print(f"    #{p.placement_id}  Student {p.student_id} ({student_name})")
    print(f"    Employer         : #{p.employer_id}  "
          f"{emp.name if emp else '(unknown)'}  "
          f"({emp.sector if emp else '?'})")
    print(f"    Role             : {p.role or '—'}")
    print(f"    Dates            : {p.start_date} → {p.end_date}")
    hrs = (f"{p.hours_completed:.1f} / {p.hours_required:.1f}"
           if p.hours_required else f"{p.hours_completed:.1f} / —")
    pct = (f" ({p.progress_percent}%)" if p.progress_percent is not None
            else "")
    print(f"    Hours            : {hrs}{pct}")
    print(f"    Status           : {p.status}")
    print(f"    Risk assessment  : "
          f"{'done' if p.risk_assessment_done else 'PENDING'}")
    print(f"    Parental consent : "
          f"{'received' if p.parental_consent else 'PENDING'}")
    print(f"    Supervisor       : {p.supervisor_name or '—'}"
          f"  <{p.supervisor_email or '—'}>")
    if p.notes:
        print("\n    Notes:")
        for line in p.notes.splitlines():
            print(f"      {line}")


def _print_employer_table(rows: list[Employer]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Name':<34}  {'Sector':<18}  "
          f"{'Contact':<22}  Phone")
    print("  " + "-" * 110)
    for e in rows:
        print(f"  {e.employer_id:>4}  {e.name[:34]:<34}  "
              f"{e.sector:<18}  {(e.contact_name or '—')[:22]:<22}  "
              f"{e.contact_phone or '—'}")
    print(f"\n  {len(rows)} employer(s).")


# ── Employer flows ───────────────────────────────────────────────

def list_employers_flow() -> None:
    print("\n═══ Employer Directory ═══")
    _print_employer_table(data.list_employers())
    _pause()


def add_employer() -> None:
    print("\n═══ Add Employer ═══")
    try:
        name = _input("Employer name", allow_empty=False)
        sector = _pick_from("Sector", list(SECTORS),
                              default=DEFAULT_SECTOR)
        contact_name = _input("Contact name")
        contact_email = _input("Contact email")
        contact_phone = _input("Contact phone")
        address = _multiline("Address (optional)")
        notes = _multiline("Notes (optional)")
        e = data.create_employer({
            "name": name, "sector": sector,
            "contact_name": contact_name,
            "contact_email": contact_email,
            "contact_phone": contact_phone,
            "address": address, "notes": notes,
        })
        print(f"\n  ✓ Created employer #{e.employer_id}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("add_employer failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def edit_employer() -> None:
    print("\n═══ Edit Employer ═══")
    try:
        e = _pick_employer()
        name = _input("Employer name", default=e.name, allow_empty=False)
        sector = _pick_from("Sector", list(SECTORS), default=e.sector)
        contact_name = _input("Contact name", default=e.contact_name or "")
        contact_email = _input("Contact email",
                                default=e.contact_email or "")
        contact_phone = _input("Contact phone",
                                default=e.contact_phone or "")
        address = _multiline("Address", default=e.address or "")
        notes = _multiline("Notes", default=e.notes or "")
        out = data.update_employer(e.employer_id, {
            "name": name, "sector": sector,
            "contact_name": contact_name,
            "contact_email": contact_email,
            "contact_phone": contact_phone,
            "address": address, "notes": notes,
        })
        print(f"\n  ✓ Updated employer #{out.employer_id}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("edit_employer failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def delete_employer_flow() -> None:
    print("\n═══ Delete Employer ═══")
    try:
        e = _pick_employer()
        if not _yes_no(f"Delete employer #{e.employer_id} {e.name!r}?"):
            print("  (cancelled)")
            return
        if data.delete_employer(e.employer_id):
            print(f"\n  ✓ Deleted employer #{e.employer_id}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("delete_employer_flow failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


# ── Placement flows ──────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Placements ═══")
    _print_placement_table(data.list_placements_with_detail())
    _pause()


def list_by_status() -> None:
    try:
        status = _pick_from("Filter by status",
                              list(PLACEMENT_STATUSES))
        print(f"\n═══ Placements with status: {status} ═══")
        _print_placement_table(data.list_placements_with_detail(
            status=status))
        _pause()
    except _UserAbort:
        return


def list_consent_pending() -> None:
    print("\n═══ Parental Consent Pending ═══")
    _print_placement_table(data.list_placements_with_detail(
        consent_pending=True))
    _pause()


def list_risk_pending() -> None:
    print("\n═══ Risk-Assessment Pending ═══")
    _print_placement_table(data.list_placements_with_detail(
        risk_pending=True))
    _pause()


def view_placement() -> None:
    try:
        p = _pick_placement()
        _print_placement_full(p)
        _pause()
    except _UserAbort:
        return


def add_placement() -> None:
    print("\n═══ Add Placement ═══")
    try:
        sid = _pick_student()
        emp = _pick_employer()
        start = _input("Start date (YYYY-MM-DD)", allow_empty=False)
        end = _input("End date (YYYY-MM-DD)", allow_empty=False)
        role = _input("Role / job title")
        hours_req = _input(
            "Hours required (blank for n/a; T-level=315)",
            default="")
        status = _pick_from("Status", list(PLACEMENT_STATUSES),
                              default=DEFAULT_PLACEMENT_STATUS)
        ra = _yes_no("Risk assessment completed?")
        consent = _yes_no("Parental consent received?")
        sup_name = _input("Supervisor name")
        sup_email = _input("Supervisor email")
        notes = _multiline("Notes (optional)")
        p = data.create_placement({
            "student_id": sid, "employer_id": emp.employer_id,
            "start_date": start, "end_date": end, "role": role,
            "hours_required": hours_req, "status": status,
            "risk_assessment_done": ra, "parental_consent": consent,
            "supervisor_name": sup_name, "supervisor_email": sup_email,
            "notes": notes,
        })
        print(f"\n  ✓ Created placement #{p.placement_id}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("add_placement failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def edit_placement() -> None:
    print("\n═══ Edit Placement ═══")
    try:
        p = _pick_placement()
        emp_cur = data.get_employer(p.employer_id)
        change_emp = _yes_no(
            f"Current employer: #{p.employer_id} "
            f"{emp_cur.name if emp_cur else '?'}.  Change?")
        emp_id = p.employer_id
        if change_emp:
            emp_id = _pick_employer().employer_id
        start = _input("Start date", default=p.start_date,
                        allow_empty=False)
        end = _input("End date", default=p.end_date, allow_empty=False)
        role = _input("Role / job title", default=p.role or "")
        hours_req = _input(
            "Hours required",
            default=("" if p.hours_required is None
                       else str(p.hours_required)))
        hours_done = _input("Hours completed",
                              default=str(p.hours_completed))
        status = _pick_from("Status", list(PLACEMENT_STATUSES),
                              default=p.status)
        ra = _yes_no("Risk assessment completed?",
                       default=p.risk_assessment_done)
        consent = _yes_no("Parental consent received?",
                            default=p.parental_consent)
        sup_name = _input("Supervisor name",
                            default=p.supervisor_name or "")
        sup_email = _input("Supervisor email",
                             default=p.supervisor_email or "")
        notes = _multiline("Notes", default=p.notes or "")
        out = data.update_placement(p.placement_id, {
            "employer_id": emp_id,
            "start_date": start, "end_date": end, "role": role,
            "hours_required": hours_req,
            "hours_completed": hours_done, "status": status,
            "risk_assessment_done": ra, "parental_consent": consent,
            "supervisor_name": sup_name, "supervisor_email": sup_email,
            "notes": notes,
        })
        print(f"\n  ✓ Updated placement #{out.placement_id}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("edit_placement failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def log_hours_flow() -> None:
    print("\n═══ Log Hours ═══")
    try:
        p = _pick_placement()
        hours = _input("Hours to add (0-24)", allow_empty=False)
        out = data.log_hours(p.placement_id, float(hours))
        print(f"\n  ✓ Hours logged. Total now {out.hours_completed:.1f}"
              f" / {out.hours_required or '—'}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except ValueError:
        print("\n  ✗ Hours must be a number.")
        _pause()
    except Exception as e:
        logger.exception("log_hours_flow failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def delete_placement_flow() -> None:
    print("\n═══ Delete Placement ═══")
    try:
        p = _pick_placement()
        _print_placement_full(p)
        if not _yes_no("\n  Delete this placement?"):
            print("  (cancelled)")
            return
        if data.delete_placement(p.placement_id):
            print(f"\n  ✓ Deleted placement #{p.placement_id}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except Exception as e:
        logger.exception("delete_placement_flow failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def show_summary() -> None:
    print("\n═══ Work Experience Summary ═══")
    try:
        s = data.summary()
        print(f"\n  Total employers          : {s.total_employers}")
        print(f"  Total placements         : {s.total_placements}")
        print(f"  Students with placement  : {s.students_with_placement}")
        print(f"  Total hours completed    : {s.total_hours_completed:.1f}")
        print(f"  Parental consent pending : {s.consent_pending}")
        print(f"  Risk-assessment pending  : {s.risk_pending}")
        print(f"  Upcoming starts (30 d)   : {s.upcoming_start}")
        print("\n  By status:")
        for st, n in s.by_status.items():
            if n:
                print(f"    {st:<14} {n:>3}")
        print("\n  By sector:")
        for sect, n in s.by_sector.items():
            if n:
                print(f"    {sect:<22} {n:>3}")
        _pause()
    except Exception as e:
        logger.exception("show_summary failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


# ── Menu ─────────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all placements",          list_all),
    ("List placements by status",    list_by_status),
    ("Consent pending",              list_consent_pending),
    ("Risk-assessment pending",      list_risk_pending),
    ("View placement",               view_placement),
    ("Add placement",                add_placement),
    ("Edit placement",               edit_placement),
    ("Log hours",                    log_hours_flow),
    ("Delete placement",             delete_placement_flow),
    ("Employer directory",           list_employers_flow),
    ("Add employer",                 add_employer),
    ("Edit employer",                edit_employer),
    ("Delete employer",              delete_employer_flow),
    ("Summary report",               show_summary),
]


def run() -> None:
    while True:
        print("\n══════ Work Experience & Placements ══════")
        for i, (label, _fn) in enumerate(_MENU, 1):
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
        _label, fn = _MENU[int(choice) - 1]
        try:
            fn()
        except _UserAbort:
            print("\n  (cancelled)")
        except Exception as e:
            logger.exception("Work Experience CLI flow crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Work Experience":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Work Experience CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
