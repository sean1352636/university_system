"""Staff Recruitment CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.recruitment.services.recruitment_service import RecruitmentService
from education_system.college_system.infrastructure.auth.core import UserAuth


def recruitment_menu(auth: UserAuth):
    """Staff Recruitment management menu."""
    svc = RecruitmentService(auth._db_path)

    while True:
        print_header("Staff Recruitment")
        options = [
            ("1", "List Vacancies"),
            ("2", "New Vacancy"),
            ("3", "View Vacancy"),
            ("4", "Edit Vacancy"),
            ("5", "Publish Vacancy"),
            ("6", "Close Vacancy"),
            ("7", "Delete Vacancy"),
            ("8", "List Applications"),
            ("9", "New Application"),
            ("A", "View Application"),
            ("B", "Edit Application"),
            ("C", "Shortlist Application"),
            ("D", "Schedule Interview"),
            ("E", "Record Interview Score"),
            ("F", "Make Offer"),
            ("G", "Delete Application"),
            ("H", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice().upper()
        if choice == "1":
            _list_vacancies(svc)
        elif choice == "2":
            _new_vacancy(svc)
        elif choice == "3":
            _view_vacancy(svc)
        elif choice == "4":
            _edit_vacancy(svc)
        elif choice == "5":
            _publish_vacancy(svc)
        elif choice == "6":
            _close_vacancy(svc)
        elif choice == "7":
            _delete_vacancy(svc)
        elif choice == "8":
            _list_applications(svc)
        elif choice == "9":
            _new_application(svc)
        elif choice == "A":
            _view_application(svc)
        elif choice == "B":
            _edit_application(svc)
        elif choice == "C":
            _shortlist_application(svc)
        elif choice == "D":
            _schedule_interview(svc)
        elif choice == "E":
            _record_score(svc)
        elif choice == "F":
            _make_offer(svc)
        elif choice == "G":
            _delete_application(svc)
        elif choice == "H":
            _show_stats(svc)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


# ── Vacancy helpers ────────────────────────────────────────────────────

def _list_vacancies(svc):
    print_header("Vacancies")
    try:
        status = input("  Filter by status (draft/open/closed) or Enter for all: ").strip() or None
        dept = input("  Filter by department or Enter for all: ").strip() or None
        vacancies = svc.list_vacancies(status=status, department=dept)
        if not vacancies:
            print("\n  No vacancies found.")
            return
        print(f"\n  {'ID':<5} {'Title':<28} {'Dept':<14} {'Contract':<12} {'Status':<8} {'Closing'}")
        print(f"  {'-'*80}")
        for v in vacancies:
            print(f"  {v['id']:<5} {v['job_title'][:26]:<28} "
                  f"{(v.get('department') or '-')[:12]:<14} "
                  f"{v['contract_type']:<12} {v['status']:<8} "
                  f"{v.get('closing_date') or '-'}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_vacancy(svc):
    print_header("New Vacancy")
    try:
        title = input("  Job Title: ").strip()
        if not title:
            print("\n  Job title is required.")
            return
        department = input("  Department: ").strip() or None
        contract_type = input("  Contract Type [permanent]: ").strip() or "permanent"
        hours = input("  Hours [full-time]: ").strip() or "full-time"
        salary_range = input("  Salary Range: ").strip() or None
        closing_date = input("  Closing Date (YYYY-MM-DD): ").strip() or None
        start_date = input("  Start Date (YYYY-MM-DD): ").strip() or None
        description = input("  Description: ").strip() or None
        person_spec = input("  Person Specification: ").strip() or None
        hm = input("  Hiring Manager ID: ").strip()

        v = svc.create_vacancy(
            job_title=title, department=department,
            contract_type=contract_type, hours=hours,
            salary_range=salary_range, closing_date=closing_date,
            start_date=start_date, description=description,
            person_spec=person_spec,
            hiring_manager_id=int(hm) if hm else None,
        )
        print(f"\n  Vacancy created (ID: {v['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_vacancy(svc):
    try:
        vid = int(input("  Vacancy ID: ").strip())
        v = svc.get_vacancy(vid)
        if not v:
            print("\n  Vacancy not found.")
            return
        print(f"\n  ID:           {v['id']}")
        print(f"  Title:        {v['job_title']}")
        print(f"  Department:   {v.get('department') or '-'}")
        print(f"  Contract:     {v['contract_type']}")
        print(f"  Hours:        {v['hours']}")
        print(f"  Salary:       {v.get('salary_range') or '-'}")
        print(f"  Closing Date: {v.get('closing_date') or '-'}")
        print(f"  Start Date:   {v.get('start_date') or '-'}")
        print(f"  Status:       {v['status']}")
        print(f"  Manager ID:   {v.get('hiring_manager_id') or '-'}")
        print(f"  Created:      {v['created_at']}")
        if v.get("description"):
            print(f"  Description:  {v['description']}")
        if v.get("person_spec"):
            print(f"  Person Spec:  {v['person_spec']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _edit_vacancy(svc):
    try:
        vid = int(input("  Vacancy ID: ").strip())
        v = svc.get_vacancy(vid)
        if not v:
            print("\n  Vacancy not found.")
            return
        print("  (Press Enter to keep current value)")
        updates = {}
        for key, prompt, cur in [
            ("job_title", "Job Title", v["job_title"]),
            ("department", "Department", v.get("department") or ""),
            ("contract_type", "Contract Type", v["contract_type"]),
            ("hours", "Hours", v["hours"]),
            ("salary_range", "Salary Range", v.get("salary_range") or ""),
            ("closing_date", "Closing Date", v.get("closing_date") or ""),
            ("start_date", "Start Date", v.get("start_date") or ""),
            ("description", "Description", v.get("description") or ""),
            ("person_spec", "Person Spec", v.get("person_spec") or ""),
        ]:
            val = input(f"  {prompt} [{cur}]: ").strip()
            if val:
                updates[key] = val
        if not updates:
            print("\n  No changes.")
            return
        svc.update_vacancy(vid, **updates)
        print("\n  Vacancy updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _publish_vacancy(svc):
    try:
        vid = int(input("  Vacancy ID to publish: ").strip())
        svc.publish_vacancy(vid)
        print("\n  Vacancy published (status: open).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _close_vacancy(svc):
    try:
        vid = int(input("  Vacancy ID to close: ").strip())
        svc.close_vacancy(vid)
        print("\n  Vacancy closed.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_vacancy(svc):
    try:
        vid = int(input("  Vacancy ID to delete: ").strip())
        confirm = input("  This will delete all applications too. Confirm? (y/n): ").strip().lower()
        if confirm != "y":
            print("\n  Cancelled.")
            return
        svc.delete_vacancy(vid)
        print("\n  Vacancy and applications deleted.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Application helpers ────────────────────────────────────────────────

def _list_applications(svc):
    print_header("Applications")
    try:
        vac = input("  Vacancy ID (or Enter for all): ").strip()
        vac_id = int(vac) if vac else None
        status = input("  Filter by status or Enter for all: ").strip() or None
        apps = svc.list_applications(vacancy_id=vac_id, status=status)
        if not apps:
            print("\n  No applications found.")
            return
        print(f"\n  {'ID':<5} {'Applicant':<22} {'Email':<24} {'Date':<12} {'Short':<6} {'Status'}")
        print(f"  {'-'*78}")
        for a in apps:
            short = "Yes" if a["shortlisted"] else "No"
            print(f"  {a['id']:<5} {a['applicant_name'][:20]:<22} "
                  f"{(a.get('email') or '-')[:22]:<24} "
                  f"{a['application_date']:<12} {short:<6} {a['status']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_application(svc):
    print_header("New Application")
    try:
        vid = int(input("  Vacancy ID: ").strip())
        name = input("  Applicant Name: ").strip()
        if not name:
            print("\n  Applicant name is required.")
            return
        email = input("  Email: ").strip() or None
        phone = input("  Phone: ").strip() or None
        cv_path = input("  CV Path: ").strip() or None
        cover_letter = input("  Cover Letter: ").strip() or None

        a = svc.create_application(
            vacancy_id=vid, applicant_name=name,
            email=email, phone=phone,
            cv_path=cv_path, cover_letter=cover_letter,
        )
        print(f"\n  Application created (ID: {a['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_application(svc):
    try:
        aid = int(input("  Application ID: ").strip())
        a = svc.get_application(aid)
        if not a:
            print("\n  Application not found.")
            return
        print(f"\n  ID:               {a['id']}")
        print(f"  Vacancy ID:       {a['vacancy_id']}")
        print(f"  Applicant:        {a['applicant_name']}")
        print(f"  Email:            {a.get('email') or '-'}")
        print(f"  Phone:            {a.get('phone') or '-'}")
        print(f"  CV Path:          {a.get('cv_path') or '-'}")
        print(f"  Applied:          {a['application_date']}")
        print(f"  Shortlisted:      {'Yes' if a['shortlisted'] else 'No'}")
        print(f"  Interview Date:   {a.get('interview_date') or '-'}")
        score = a.get('interview_score')
        print(f"  Interview Score:  {score if score is not None else '-'}")
        print(f"  Refs Received:    {'Yes' if a.get('references_received') else 'No'}")
        print(f"  Offer Made:       {'Yes' if a.get('offer_made') else 'No'}")
        print(f"  Offer Accepted:   {'Yes' if a.get('offer_accepted') else 'No'}")
        print(f"  Status:           {a['status']}")
        if a.get("interview_notes"):
            print(f"  Interview Notes:  {a['interview_notes']}")
        if a.get("cover_letter"):
            print(f"  Cover Letter:     {a['cover_letter']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _edit_application(svc):
    try:
        aid = int(input("  Application ID: ").strip())
        a = svc.get_application(aid)
        if not a:
            print("\n  Application not found.")
            return
        print("  (Press Enter to keep current value)")
        updates = {}
        for key, prompt, cur in [
            ("applicant_name", "Applicant Name", a["applicant_name"]),
            ("email", "Email", a.get("email") or ""),
            ("phone", "Phone", a.get("phone") or ""),
            ("cv_path", "CV Path", a.get("cv_path") or ""),
            ("status", "Status", a["status"]),
        ]:
            val = input(f"  {prompt} [{cur}]: ").strip()
            if val:
                updates[key] = val
        if not updates:
            print("\n  No changes.")
            return
        svc.update_application(aid, **updates)
        print("\n  Application updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _shortlist_application(svc):
    try:
        aid = int(input("  Application ID: ").strip())
        svc.shortlist_application(aid)
        print("\n  Application shortlisted.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _schedule_interview(svc):
    try:
        aid = int(input("  Application ID: ").strip())
        date = input("  Interview Date (YYYY-MM-DD): ").strip()
        if not date:
            print("\n  Date is required.")
            return
        svc.schedule_interview(aid, date)
        print("\n  Interview scheduled.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _record_score(svc):
    try:
        aid = int(input("  Application ID: ").strip())
        score = float(input("  Interview Score: ").strip())
        notes = input("  Interview Notes: ").strip() or None
        svc.record_interview_score(aid, score, notes)
        print("\n  Score recorded.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _make_offer(svc):
    try:
        aid = int(input("  Application ID: ").strip())
        svc.make_offer(aid)
        print("\n  Offer made.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_application(svc):
    try:
        aid = int(input("  Application ID: ").strip())
        confirm = input("  Confirm delete? (y/n): ").strip().lower()
        if confirm != "y":
            print("\n  Cancelled.")
            return
        svc.delete_application(aid)
        print("\n  Application deleted.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _show_stats(svc):
    print_header("Recruitment Statistics")
    try:
        s = svc.get_stats()
        print(f"\n  Total Vacancies: {s['total_vacancies']}")
        for status, cnt in s.get("vacancies_by_status", {}).items():
            print(f"    {status}: {cnt}")
        print(f"\n  Total Applications: {s['total_applications']}")
        print(f"  Shortlisted:        {s['shortlisted']}")
        print(f"  Offers Made:        {s['offers_made']}")
        print(f"  Offers Accepted:    {s['offers_accepted']}")
    except Exception as e:
        print(f"\n  Error: {e}")
