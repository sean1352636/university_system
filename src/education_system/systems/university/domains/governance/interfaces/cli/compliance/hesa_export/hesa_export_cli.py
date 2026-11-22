"""HESA Data Export CLI."""


def display_hesa_export_menu(auth):
    from education_system.systems.university.domains.governance.domain.compliance.hesa_export.services.hesa_export_service import HESAExportService
    service = HESAExportService()

    while True:
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 70)
        print("HESA DATA EXPORT".center(70))
        print("=" * 70)
        print("\n  1. List Returns")
        print("  2. Create New Return")
        print("  3. Generate XML Export")
        print("  4. Submit Return")
        print("  5. Manage Field Mappings")
        print("  6. View Submission Log")
        print("  7. Return Statistics")
        print("  8. Data Futures (reference periods, validation, SIDs, coding frames)")
        print("  9. Student Loans Company (census confirmation, change notices)")
        print("\n  0. Back")
        print("=" * 70)

        choice = input("\nSelect: ").strip()
        if choice == '0':
            break
        elif choice == '1':
            returns = service.list_returns()
            print(f"\n{'ID':<5} {'Year':<12} {'Type':<12} {'Status':<12} {'Created':<20}")
            print("-" * 65)
            for r in returns:
                print(f"{r['id']:<5} {r['academic_year']:<12} {r['return_type']:<12} {r['status']:<12} {r.get('created_at', ''):<20}")
        elif choice == '2':
            year = input("Academic year (e.g. 2025/26): ").strip()
            rtype = input("Return type (Student/Staff/Finance/Unistats): ").strip()
            rid = service.create_return(year, rtype)
            print(f"\nReturn created with ID: {rid}")
        elif choice == '3':
            rid = int(input("Return ID: ").strip())
            try:
                xml = service.generate_xml_export(rid, actor=getattr(auth, "current_user", None))
            except (ValueError, PermissionError) as exc:
                print(f"\n✗ {exc}")
                input("\nPress Enter to continue...")
                continue
            from education_system.systems.university.application.statutory import hesa_return
            built = hesa_return.report(getattr(auth, "current_user", None), rid)
            print(f"\nXML built ({len(xml)} characters): {built['report'].get('errors', 0)} "
                  f"error(s), {built['report'].get('warnings', 0)} warning(s).")
            print(f"Upload file: {built['return'].get('output_path') or 'none - fix the errors first'}")
            show = input("Display XML? (y/n): ").strip().lower()
            if show == 'y':
                print(xml[:2000])
        elif choice == '4':
            rid = int(input("Return ID: ").strip())
            service.update_return_status(rid, 'submitted')
            print("\nReturn submitted.")
        elif choice == '5':
            mappings = service.get_field_mappings()
            print(f"\n{'ID':<5} {'Type':<12} {'HESA Field':<20} {'Local Field':<20}")
            print("-" * 60)
            for m in mappings:
                print(f"{m['id']:<5} {m['return_type']:<12} {m['hesa_field']:<20} {m['local_field']:<20}")
            if input("\nAdd mapping? (y/n): ").strip().lower() == 'y':
                rt = input("Return type: ").strip()
                hf = input("HESA field: ").strip()
                lf = input("Local field: ").strip()
                service.add_field_mapping(rt, hf, lf)
                print("Mapping added.")
        elif choice == '6':
            rid = int(input("Return ID: ").strip())
            logs = service.get_submission_log(rid)
            for log in logs:
                print(f"  [{log.get('performed_at', '')}] {log['action']} - {log.get('details', '')}")
        elif choice == '8':
            from education_system.systems.university.domains.governance.interfaces.cli.compliance.statutory_returns.statutory_cli import (
                hesa_menu,
            )
            hesa_menu(auth)
            continue
        elif choice == '9':
            from education_system.systems.university.domains.governance.interfaces.cli.compliance.statutory_returns.statutory_cli import (
                slc_menu,
            )
            slc_menu(auth)
            continue
        elif choice == '7':
            stats = service.get_return_statistics()
            print(f"\nTotal returns: {stats['total']}")
            for s, c in stats.get('by_status', {}).items():
                print(f"  {s}: {c}")
        input("\nPress Enter to continue...")
