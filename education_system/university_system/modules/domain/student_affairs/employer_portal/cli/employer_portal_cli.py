"""Console menu for the employer portal — mirrors internship_management.py style."""
from __future__ import annotations

from typing import Any

from education_system.university_system.modules.domain.student_affairs.employer_portal.services.employer_portal_service import (
    EmployerPortalService,
    EmployerPortalError,
)


auth: Any = None


def set_auth(auth_object: Any) -> None:
    global auth
    auth = auth_object


def _require_login() -> bool:
    if not auth or not getattr(auth, "current_user", None):
        print("You must be logged in to access the employer portal.")
        return False
    return True


def _list_employers(svc: EmployerPortalService) -> None:
    show_all = input("Include inactive? (y/n, default=n): ").strip().lower() == "y"
    employers = svc.list_employers(active_only=not show_all)
    if not employers:
        print("No employers found.")
        return
    print(f"\n{'ID':<5} {'Company':<24} {'Contact':<18} {'Email':<25} "
          f"{'Sector':<12} {'Size':<8} {'Active':<6}")
    print("-" * 100)
    for e in employers:
        print(f"{e['employer_id']:<5} "
              f"{(e.get('company_name') or '')[:24]:<24} "
              f"{(e.get('contact_name') or '-')[:18]:<18} "
              f"{(e.get('contact_email') or '-')[:25]:<25} "
              f"{(e.get('sector') or '-')[:12]:<12} "
              f"{(e.get('company_size') or '-'):<8} "
              f"{'Yes' if e.get('is_active') else 'No':<6}")
    print(f"\nTotal: {len(employers)}")


def _register_employer(svc: EmployerPortalService) -> None:
    name = input("Company name: ").strip()
    if not name:
        print("Error: company name is required.")
        return
    contact = input("Contact name: ").strip()
    email = input("Contact email: ").strip()
    phone = input("Contact phone: ").strip()
    sector = input("Sector: ").strip()
    size = input("Size (small/medium/large, default=small): ").strip() or "small"
    try:
        eid = svc.register_employer(name, contact, email, phone, sector, company_size=size)
        print(f"Employer #{eid} registered.")
    except EmployerPortalError as exc:
        print(f"Error: {exc}")


def _update_employer(svc: EmployerPortalService) -> None:
    try:
        eid = int(input("Employer ID: ").strip())
    except ValueError:
        print("Error: invalid id.")
        return
    updates: dict[str, Any] = {}
    for field, prompt in [
        ("company_name",  "New company (Enter to keep): "),
        ("contact_name",  "New contact (Enter to keep): "),
        ("contact_email", "New email (Enter to keep): "),
        ("contact_phone", "New phone (Enter to keep): "),
        ("sector",        "New sector (Enter to keep): "),
    ]:
        v = input(prompt).strip()
        if v:
            updates[field] = v
    portal = input("Portal access? (y/n/Enter to keep): ").strip().lower()
    if portal in ("y", "n"):
        updates["portal_access_enabled"] = 1 if portal == "y" else 0
    active = input("Active? (y/n/Enter to keep): ").strip().lower()
    if active in ("y", "n"):
        updates["is_active"] = 1 if active == "y" else 0
    if updates:
        try:
            svc.update_employer(eid, **updates)
            print("Employer updated.")
        except EmployerPortalError as exc:
            print(f"Error: {exc}")
    else:
        print("No changes made.")


def _schedule_review(svc: EmployerPortalService) -> None:
    try:
        pid = int(input("Placement ID: ").strip())
        date = input("Review date (YYYY-MM-DD): ").strip()
        rtype = input("Type (monthly/tripartite/midterm/final, default=monthly): ").strip() or "monthly"
        rid = svc.schedule_review(pid, date, review_type=rtype)
        print(f"Review #{rid} scheduled.")
    except (EmployerPortalError, ValueError) as exc:
        print(f"Error: {exc}")


def _list_reviews(svc: EmployerPortalService) -> None:
    pid = input("Placement ID filter (Enter for all): ").strip()
    status = input("Status filter (scheduled/completed/cancelled, Enter for all): ").strip() or None
    try:
        rows = svc.list_reviews(
            placement_id=int(pid) if pid else None, status=status,
        )
    except EmployerPortalError as exc:
        print(f"Error: {exc}")
        return
    if not rows:
        print("No reviews found.")
        return
    print(f"\n{'ID':<5} {'Plac':<5} {'Date':<12} {'Type':<12} "
          f"{'OnTrack':<8} {'Hrs':>6} {'E':<2} {'S':<2} {'Sup':<3} {'Status':<10}")
    print("-" * 75)
    for r in rows:
        on = "Yes" if r.get("on_track") else ("No" if r.get("on_track") == 0 else "-")
        print(f"{r['review_id']:<5} {r['placement_id']:<5} "
              f"{(r.get('review_date') or '-'):<12} "
              f"{(r.get('review_type') or '-'):<12} "
              f"{on:<8} {r.get('hours_logged') or 0:>6} "
              f"{'Y' if r.get('employer_signed') else 'N':<2} "
              f"{'Y' if r.get('student_signed') else 'N':<2} "
              f"{'Y' if r.get('supervisor_signed') else 'N':<3} "
              f"{r.get('status', '-'):<10}")
    print(f"\nTotal: {len(rows)}")


def _complete_review(svc: EmployerPortalService) -> None:
    try:
        rid = int(input("Review ID: ").strip())
        on_track = input("On track? (y/n): ").strip().lower() == "y"
        comp = input("Competency progress: ").strip()
        hours = float(input("Hours logged: ").strip() or 0)
        emp_fb = input("Employer feedback: ").strip()
        stu_fb = input("Student feedback (blank=none): ").strip() or None
        sup_fb = input("Supervisor feedback (blank=none): ").strip() or None
        actions = input("Actions (blank=none): ").strip() or None
        nxt = input("Next review date YYYY-MM-DD (blank=none): ").strip() or None
        svc.complete_review(rid, on_track, comp, hours, emp_fb,
                            student_feedback=stu_fb, supervisor_feedback=sup_fb,
                            actions=actions, next_review_date=nxt)
        print("Review completed.")
    except (EmployerPortalError, ValueError) as exc:
        print(f"Error: {exc}")


def _sign_off_review(svc: EmployerPortalService) -> None:
    try:
        rid = int(input("Review ID: ").strip())
        st = input("Signer type (employer/student/supervisor): ").strip()
        sn = input("Signer name: ").strip()
        comments = input("Comments (blank=none): ").strip() or None
        svc.sign_off_review(rid, st, sn, comments=comments)
        print("Review signed off.")
    except (EmployerPortalError, ValueError) as exc:
        print(f"Error: {exc}")


def _employer_dashboard(svc: EmployerPortalService) -> None:
    try:
        eid = int(input("Employer ID: ").strip())
        dash = svc.get_employer_dashboard(eid)
    except (EmployerPortalError, ValueError) as exc:
        print(f"Error: {exc}")
        return
    emp = dash["employer"]
    print(f"\nEmployer: {emp['company_name']} (ID {emp['employer_id']})")
    print(f"Contact: {emp.get('contact_name','-')} <{emp.get('contact_email','-')}>")
    print(f"Total placements:  {dash['total_placements']}")
    print(f"Active placements: {dash['active_placements']}")
    if not dash["placements"]:
        return
    print(f"\n{'Plac':<5} {'Student':<10} {'Title':<28} {'Status':<10} "
          f"{'Reviews':<10} {'OnTrack':<8} {'Hours':>7}")
    print("-" * 80)
    for s in dash["placements"]:
        rs = s.get("review_summary") or {}
        print(f"{s['placement_id']:<5} {str(s.get('student_id','-')):<10} "
              f"{(s.get('title') or '')[:28]:<28} "
              f"{(s.get('status') or '-'):<10} "
              f"{(rs.get('completed') or 0)}/{(rs.get('total') or 0):<8} "
              f"{rs.get('on_track') or 0:<8} "
              f"{rs.get('total_hours') or 0:>7}")


def _placement_progress(svc: EmployerPortalService) -> None:
    try:
        pid = int(input("Placement ID: ").strip())
        data = svc.get_placement_progress(pid)
    except (EmployerPortalError, ValueError) as exc:
        print(f"Error: {exc}")
        return
    p = data["placement"]
    print(f"\nPlacement #{p['placement_id']} — {p.get('title','')} @ {p.get('company','')}")
    print(f"Student: {p.get('student_id','-')}   Supervisor: {p.get('supervisor_name','-')}")
    print(f"Dates: {p.get('start_date','-')} → {p.get('end_date','-')}")
    print(f"Completion: {data['completion_pct']}%   Total hours: {data['total_hours_logged']}   "
          f"Reviews: {data['review_count']}")


def _overdue_reviews(svc: EmployerPortalService) -> None:
    rows = svc.get_overdue_reviews()
    if not rows:
        print("No overdue reviews.")
        return
    print(f"\n{'ID':<5} {'Plac':<5} {'Student':<10} {'Date':<12} "
          f"{'Type':<12} {'Title':<25} {'Company':<20}")
    print("-" * 92)
    for r in rows:
        print(f"{r['review_id']:<5} {r['placement_id']:<5} "
              f"{str(r.get('student_id','-')):<10} "
              f"{(r.get('review_date') or '-'):<12} "
              f"{(r.get('review_type') or '-'):<12} "
              f"{(r.get('title') or '')[:25]:<25} "
              f"{(r.get('company') or '')[:20]:<20}")
    print(f"\n{len(rows)} overdue review(s)")


def display_employer_portal_menu() -> None:
    """Top-level employer portal menu."""
    if not _require_login():
        return
    db_path = getattr(auth, "_db_path", None)
    svc = EmployerPortalService(db_path)

    actions = {
        "1":  ("List Employers",         _list_employers),
        "2":  ("Register Employer",      _register_employer),
        "3":  ("Update Employer",        _update_employer),
        "4":  ("Schedule Review",        _schedule_review),
        "5":  ("List Reviews",           _list_reviews),
        "6":  ("Complete Review",        _complete_review),
        "7":  ("Sign Off Review",        _sign_off_review),
        "8":  ("Employer Dashboard",     _employer_dashboard),
        "9":  ("Placement Progress",     _placement_progress),
        "10": ("Overdue Reviews",        _overdue_reviews),
    }
    while True:
        print("\nEmployer Portal")
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
        except EmployerPortalError as exc:
            print(f"Error: {exc}")
