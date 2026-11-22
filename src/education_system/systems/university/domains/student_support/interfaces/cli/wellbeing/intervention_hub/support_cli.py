"""Console menu for intervention support cases — the CLI side of the
Interventions window's Support Cases tab, over the same records."""
from __future__ import annotations

from typing import Any, Optional

from education_system.systems.university.domains.student_support.domain.wellbeing.student_wellbeing.services.intervention_records import (
    FIELDS, INTERVENTION_TYPES, RISK_LEVELS, STATUSES,
    InterventionRecordsError, InterventionRecordsService, build_report,
)


def _pick(prompt: str, options: tuple[str, ...], default: Optional[str]) -> str:
    """Numbered choice; Enter keeps ``default``."""
    for i, opt in enumerate(options, start=1):
        print(f"  {i}. {opt}")
    raw = input(f"{prompt} [{default or ''}]: ").strip()
    if not raw:
        return default or options[0]
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1]
    if raw in options:
        return raw
    print("  Not an option — keeping the current value.")
    return default or options[0]


def _ask(label: str, current: str = "") -> str:
    raw = input(f"{label} [{current}]: ").strip()
    return raw or current


def _print_table(rows: list[dict]) -> None:
    if not rows:
        print("\nNo records found.")
        return
    print(f"\n{'ID':<10} {'Name':<22} {'Program':<20} {'Risk':<9} {'GPA':<5} "
          f"{'Status':<11} {'Last Contact':<12}")
    print("-" * 94)
    for r in rows:
        print(f"{(r.get('student_id') or '')[:10]:<10} {(r.get('name') or '')[:22]:<22} "
              f"{(r.get('program') or '')[:20]:<20} {(r.get('risk') or '')[:9]:<9} "
              f"{(r.get('gpa') or '')[:5]:<5} {(r.get('status') or '')[:11]:<11} "
              f"{(r.get('last_contact') or 'N/A')[:12]:<12}")
    print(f"\nTotal: {len(rows)}")


def _print_stats(rows: list[dict]) -> None:
    print(f"\nTotal Cases: {len(rows)}   "
          f"Critical: {sum(1 for s in rows if s.get('risk') == 'Critical')}   "
          f"High Risk: {sum(1 for s in rows if s.get('risk') == 'High')}   "
          f"Active: {sum(1 for s in rows if s.get('status') == 'Active')}")


def _list(svc: InterventionRecordsService) -> None:
    search = input("Search name or ID (Enter for all): ").strip()
    print("Risk level filter:")
    risk = _pick("Choose", ("All", *RISK_LEVELS), "All")
    rows = InterventionRecordsService.filter(svc.load_all(), search, risk)
    _print_stats(rows)
    _print_table(rows)


def _view(svc: InterventionRecordsService) -> None:
    rec = svc.get(input("Student ID: ").strip())
    if not rec:
        print("Student record not found.")
        return
    print()
    for f in FIELDS:
        if f != "notes":
            print(f"  {f.replace('_', ' ').title():<14} {rec.get(f) or '-'}")
    print("\n  Notes / Case History:")
    print("  " + (rec.get("notes") or "(none)").replace("\n", "\n  "))


def _edit_fields(rec: dict) -> dict:
    rec["name"] = _ask("Full Name", rec.get("name", ""))
    rec["program"] = _ask("Program", rec.get("program", ""))
    rec["gpa"] = _ask("GPA", rec.get("gpa", ""))
    rec["email"] = _ask("Email", rec.get("email", ""))
    print("Risk Level:")
    rec["risk"] = _pick("Choose", RISK_LEVELS, rec.get("risk") or "Low")
    print("Status:")
    rec["status"] = _pick("Choose", STATUSES, rec.get("status") or "Active")
    print("Intervention:")
    rec["intervention"] = _pick("Choose", INTERVENTION_TYPES,
                                rec.get("intervention") or "Academic Advising")
    extra = input("Add a note (Enter to skip): ").strip()
    if extra:
        rec["notes"] = ((rec.get("notes") or "") + "\n" + extra).strip()
    return rec


def _add(svc: InterventionRecordsService) -> None:
    rec = {f: "" for f in FIELDS}
    rec["student_id"] = input("Student ID: ").strip()
    rec = _edit_fields(rec)
    try:
        svc.add(rec)
        print(f"Student {rec['name']} added successfully.")
    except InterventionRecordsError as exc:
        print(f"Error: {exc}")


def _update(svc: InterventionRecordsService) -> None:
    rec = svc.get(input("Student ID: ").strip())
    if not rec:
        print("Student record not found.")
        return
    try:
        svc.update(_edit_fields(rec))
        print("Student record updated.")
    except InterventionRecordsError as exc:
        print(f"Error: {exc}")


def _delete(svc: InterventionRecordsService) -> None:
    sid = input("Student ID: ").strip()
    if input(f"Delete record for student {sid}? (y/n): ").strip().lower() != "y":
        print("Cancelled.")
        return
    try:
        svc.delete(sid)
        print("Student record deleted.")
    except InterventionRecordsError as exc:
        print(f"Error: {exc}")


def _log_contact(svc: InterventionRecordsService) -> None:
    try:
        svc.log_contact(input("Student ID: ").strip())
        print("Contact has been logged.")
    except InterventionRecordsError as exc:
        print(f"Error: {exc}")


def _report(svc: InterventionRecordsService) -> None:
    print()
    print(build_report(svc.load_all()))


def display_intervention_support_menu(auth: Any) -> None:
    user = getattr(auth, "current_user", None) if auth else None
    if not user:
        print("You must be logged in to access intervention support.")
        return
    svc = InterventionRecordsService(
        actor=user.get("username") or user.get("email") or str(user.get("id") or ""))

    actions = {
        "1": ("List / Search Cases",  _list),
        "2": ("View Case",            _view),
        "3": ("Add New Case",         _add),
        "4": ("Update Case",          _update),
        "5": ("Delete Case",          _delete),
        "6": ("Log Contact",          _log_contact),
        "7": ("Generate Report",      _report),
    }
    while True:
        print("\nSupport Cases")
        print("=" * 30)
        for k, (label, _) in actions.items():
            print(f"{k}. {label}")
        print("0. Return to Previous Menu")
        choice = input("\nEnter your choice: ").strip()
        if choice == "0":
            return
        action = actions.get(choice)
        if not action:
            print("Invalid choice.")
            continue
        try:
            action[1](svc)
        except KeyboardInterrupt:
            print("\nCancelled.")
        except InterventionRecordsError as exc:
            print(f"Error: {exc}")
