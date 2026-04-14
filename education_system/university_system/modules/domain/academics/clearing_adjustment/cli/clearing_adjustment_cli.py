"""Clearing & Adjustment CLI."""


def display_clearing_adjustment_menu(auth):
    from education_system.university_system.modules.domain.academics.clearing_adjustment.services.clearing_adjustment_service import ClearingAdjustmentService
    service = ClearingAdjustmentService()

    while True:
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 70)
        print("CLEARING & ADJUSTMENT".center(70))
        print("=" * 70)
        print("\n  1. View Available Vacancies")
        print("  2. Add Vacancy")
        print("  3. Submit Clearing Application")
        print("  4. View Applications")
        print("  5. Process Application")
        print("  6. Auto-Shortlist")
        print("  7. Submit Adjustment Request")
        print("  8. View Adjustment Requests")
        print("  9. Statistics")
        print("\n  0. Back")
        print("=" * 70)

        choice = input("\nSelect: ").strip()
        if choice == '0':
            break
        elif choice == '1':
            vacs = service.list_vacancies()
            print(f"\n{'ID':<5} {'Course':<25} {'Dept':<15} {'Places':<8} {'Min Tariff':<10}")
            print("-" * 65)
            for v in vacs:
                print(f"{v['id']:<5} {v['course_name']:<25} {v.get('department', ''):<15} {v['available_places']:<8} {v['minimum_tariff']:<10}")
        elif choice == '2':
            code = input("Course code: ").strip()
            name = input("Course name: ").strip()
            dept = input("Department: ").strip()
            places = int(input("Available places: ").strip())
            tariff = int(input("Minimum tariff: ").strip())
            service.add_vacancy(code, name, dept, places, tariff)
            print("\nVacancy added.")
        elif choice == '3':
            name = input("Applicant name: ").strip()
            email = input("Email: ").strip()
            phone = input("Phone: ").strip()
            ucas = input("UCAS ID: ").strip()
            tariff = int(input("Tariff points: ").strip())
            quals = input("Qualifications: ").strip()
            course = input("Preferred course: ").strip()
            aid = service.submit_clearing_application(name, email, phone, ucas, tariff, quals, course)
            print(f"\nApplication submitted with ID: {aid}")
        elif choice == '4':
            status = input("Filter by status (or Enter for all): ").strip() or None
            apps = service.list_applications(status)
            print(f"\n{'ID':<5} {'Name':<20} {'UCAS':<12} {'Tariff':<8} {'Course':<20} {'Status':<12}")
            print("-" * 80)
            for a in apps:
                print(f"{a['id']:<5} {a['applicant_name']:<20} {a.get('ucas_id', ''):<12} {a.get('tariff_points', 0):<8} {a.get('preferred_course', ''):<20} {a['status']:<12}")
        elif choice == '5':
            aid = int(input("Application ID: ").strip())
            status = input("New status (shortlisted/offered/accepted/rejected): ").strip()
            service.update_application_status(aid, status)
            print("Application updated.")
        elif choice == '6':
            shortlisted = service.auto_shortlist()
            print(f"\n{len(shortlisted)} applications auto-shortlisted.")
        elif choice == '7':
            sid = auth.current_user.get('username', '') if auth and auth.current_user else input("Student ID: ").strip()
            orig = input("Original course: ").strip()
            req = input("Requested course: ").strip()
            reason = input("Reason: ").strip()
            grades = input("Current grades: ").strip()
            rid = service.submit_adjustment_request(sid, orig, req, reason, grades)
            print(f"\nRequest submitted with ID: {rid}")
        elif choice == '8':
            reqs = service.list_adjustment_requests()
            for r in reqs:
                print(f"  {r['id']}: {r.get('student_id', '')} | {r.get('original_course', '')} -> {r.get('requested_course', '')} | {r['status']}")
        elif choice == '9':
            stats = service.get_clearing_statistics()
            print(f"\n  Total applications: {stats['total_applications']}")
            print(f"  Places remaining: {stats['total_places_remaining']}")
            for s, c in stats.get('by_status', {}).items():
                print(f"    {s}: {c}")
        input("\nPress Enter to continue...")
