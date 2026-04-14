"""External Examiner CLI."""


def display_external_examiner_menu(auth):
    from education_system.university_system.modules.domain.academics.external_examiners.services.external_examiner_service import ExternalExaminerService
    service = ExternalExaminerService()

    while True:
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 70)
        print("EXTERNAL EXAMINERS".center(70))
        print("=" * 70)
        print("\n  1. List Examiners")
        print("  2. Add Examiner")
        print("  3. Schedule Visit")
        print("  4. Record Findings")
        print("  5. Manage Action Items")
        print("  6. View Examiner History")
        print("  7. Department Summary")
        print("  8. Overdue Actions")
        print("\n  0. Back")
        print("=" * 70)

        choice = input("\nSelect: ").strip()
        if choice == '0':
            break
        elif choice == '1':
            examiners = service.list_examiners()
            print(f"\n{'ID':<5} {'Name':<25} {'Institution':<25} {'Status':<10}")
            print("-" * 65)
            for e in examiners:
                print(f"{e['id']:<5} {e['name']:<25} {e.get('institution', ''):<25} {e['status']:<10}")
        elif choice == '2':
            name = input("Name: ").strip()
            email = input("Email: ").strip()
            inst = input("Institution: ").strip()
            spec = input("Specialisation: ").strip()
            eid = service.add_examiner(name, email, inst, spec)
            print(f"\nExaminer added with ID: {eid}")
        elif choice == '3':
            eid = int(input("Examiner ID: ").strip())
            date = input("Visit date (YYYY-MM-DD): ").strip()
            dept = input("Department: ").strip()
            purpose = input("Purpose: ").strip()
            vid = service.schedule_visit(eid, date, dept, purpose)
            print(f"\nVisit scheduled with ID: {vid}")
        elif choice == '4':
            vid = int(input("Visit ID: ").strip())
            findings = input("Findings: ").strip()
            recs = input("Recommendations: ").strip()
            rating = input("Rating (excellent/good/satisfactory/concerns): ").strip()
            service.record_findings(vid, findings, recs, rating)
            print("\nFindings recorded.")
        elif choice == '5':
            vid = int(input("Visit ID: ").strip())
            actions = service.get_actions_by_visit(vid)
            print(f"\n{'ID':<5} {'Description':<30} {'Responsible':<20} {'Deadline':<12} {'Status':<12}")
            print("-" * 80)
            for a in actions:
                print(f"{a['id']:<5} {a['action_description'][:28]:<30} {a.get('responsible_person', ''):<20} {a.get('deadline', ''):<12} {a['status']:<12}")
            sub = input("\n(a)dd action, (u)pdate status, or Enter to go back: ").strip().lower()
            if sub == 'a':
                desc = input("Action description: ").strip()
                resp = input("Responsible person: ").strip()
                dl = input("Deadline (YYYY-MM-DD): ").strip()
                service.add_action_item(vid, desc, resp, dl)
                print("Action added.")
            elif sub == 'u':
                aid = int(input("Action ID: ").strip())
                status = input("New status (pending/in_progress/completed): ").strip()
                service.update_action_status(aid, status)
                print("Status updated.")
        elif choice == '6':
            eid = int(input("Examiner ID: ").strip())
            history = service.get_examiner_history(eid)
            ex = history['examiner']
            print(f"\n{ex['name']} - {ex.get('institution', '')} ({history['total_visits']} visits)")
            for v in history['visits']:
                print(f"  [{v['visit_date']}] {v.get('department', '')} - {v.get('overall_rating', 'N/A')}")
        elif choice == '7':
            summaries = service.get_department_summary()
            print(f"\n{'Department':<25} {'Visits':<10} {'Last Visit':<15}")
            print("-" * 50)
            for s in summaries:
                print(f"{s.get('department', 'N/A'):<25} {s['visit_count']:<10} {s.get('last_visit', ''):<15}")
        elif choice == '8':
            overdue = service.get_overdue_actions()
            if overdue:
                for a in overdue:
                    print(f"  [{a.get('deadline', '')}] {a['action_description']} - {a.get('responsible_person', '')}")
            else:
                print("\nNo overdue actions.")
        input("\nPress Enter to continue...")
