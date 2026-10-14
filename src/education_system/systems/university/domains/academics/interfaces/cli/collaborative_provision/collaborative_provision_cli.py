"""Collaborative (partner) provision CLI."""

from __future__ import annotations


def _print_table(rows, columns) -> None:
    """columns is a sequence of (heading, key, width)."""
    if not rows:
        print("\n  (none)")
        return
    header = " ".join(f"{h:<{w}}" for h, _, w in columns)
    print("\n" + header)
    print("-" * len(header))
    for r in rows:
        print(" ".join(f"{str(r.get(k, '') or '')[:w]:<{w}}"
                       for _, k, w in columns))


def display_collaborative_provision_menu(auth=None):
    from education_system.systems.university.domains.academics.domain.collaborative_provision._db_init import (
        AGREEMENT_STATUSES, DELIVERY_MODELS, PARTNER_TYPES, REVIEW_TYPES,
    )
    from education_system.systems.university.domains.academics.domain.collaborative_provision.services.collaborative_provision_service import (
        CollaborativeProvisionService,
    )

    service = CollaborativeProvisionService()

    while True:
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 70)
        print("COLLABORATIVE (PARTNER) PROVISION".center(70))
        print("=" * 70)
        try:
            s = service.summary()
            print(f"\n  {s['partners']} partners · {s['agreements_live']} live "
                  f"agreements · {s['programmes']} programmes · "
                  f"{s['students']} students")
            if s["overdue_reviews"]:
                print(f"  ⚠ {s['overdue_reviews']} agreement(s) overdue review")
        except Exception as exc:  # noqa: BLE001 - summary must never block the menu
            print(f"\n  (summary unavailable: {exc})")

        print("\n  1. List Partners")
        print("  2. Add Partner")
        print("  3. List Agreements")
        print("  4. Add Agreement")
        print("  5. Add Programme to Agreement")
        print("  6. Record Cohort Numbers")
        print("  7. Record Review / Due Diligence")
        print("  8. Overdue Reviews")
        print("  9. Over-Recruited Agreements")
        print(" 10. Provision Map (all off-site delivery)")
        print(" 11. Programmes Not Linked to Governance")
        print("\n  0. Back")
        print("=" * 70)

        choice = input("\nSelect: ").strip()
        if choice == "0":
            break

        try:
            if choice == "1":
                _print_table(service.list_partners(active_only=False), (
                    ("ID", "partner_id", 5), ("Name", "name", 32),
                    ("Type", "partner_type", 26), ("Country", "country", 14),
                    ("Risk", "risk_level", 7), ("Agmts", "agreement_count", 6)))
            elif choice == "2":
                name = input("Partner name: ").strip()
                print("  Types: " + ", ".join(
                    f"{i + 1}={t}" for i, t in enumerate(PARTNER_TYPES)))
                sel = input("Type number (Enter to skip): ").strip()
                ptype = PARTNER_TYPES[int(sel) - 1] if sel.isdigit() and \
                    1 <= int(sel) <= len(PARTNER_TYPES) else None
                country = input("Country: ").strip() or None
                city = input("City: ").strip() or None
                contact = input("Contact name: ").strip() or None
                email = input("Contact email: ").strip() or None
                risk = input("Risk (Low/Medium/High) [Medium]: ").strip() or "Medium"
                pid = service.add_partner(name, partner_type=ptype,
                                          country=country, city=city,
                                          contact_name=contact,
                                          contact_email=email, risk_level=risk)
                print(f"\n  Partner added with ID {pid}.")
            elif choice == "3":
                _print_table(service.list_agreements(), (
                    ("ID", "agreement_id", 5), ("Partner", "partner_name", 28),
                    ("Model", "delivery_model", 22), ("Status", "status", 18),
                    ("Ends", "end_date", 12), ("Review", "review_due", 12)))
            elif choice == "4":
                pid = int(input("Partner ID: ").strip())
                print("  Models: " + ", ".join(
                    f"{i + 1}={m}" for i, m in enumerate(DELIVERY_MODELS)))
                model = DELIVERY_MODELS[int(input("Model number: ").strip()) - 1]
                print("  Statuses: " + ", ".join(
                    f"{i + 1}={s}" for i, s in enumerate(AGREEMENT_STATUSES)))
                sel = input("Status number [1]: ").strip() or "1"
                status = AGREEMENT_STATUSES[int(sel) - 1]
                start = input("Start date (YYYY-MM-DD): ").strip() or None
                end = input("End date (YYYY-MM-DD): ").strip() or None
                review = input("Review due (YYYY-MM-DD): ").strip() or None
                cap = input("Max students (Enter to skip): ").strip()
                aid = service.add_agreement(
                    pid, model, status=status, start_date=start, end_date=end,
                    review_due=review,
                    max_students=int(cap) if cap.isdigit() else None)
                print(f"\n  Agreement added with ID {aid}.")
            elif choice == "5":
                aid = int(input("Agreement ID: ").strip())
                title = input("Programme title: ").strip()
                code = input("Programme code (Enter to skip): ").strip() or None
                award = input("Award (e.g. BSc (Hons)): ").strip() or None
                site = input("Delivery site: ").strip() or None
                tutor = input("Link tutor: ").strip() or None
                cid = service.add_programme(aid, title, programme_code=code,
                                            award=award, delivery_site=site,
                                            link_tutor=tutor)
                print(f"\n  Programme added with ID {cid}.")
            elif choice == "6":
                _print_table(service.list_programmes(), (
                    ("ID", "collab_programme_id", 5),
                    ("Partner", "partner_name", 26),
                    ("Programme", "programme_title", 34),
                    ("Code", "programme_code", 12)))
                cpid = int(input("\nProgramme ID: ").strip())
                year = input("Academic year (e.g. 2026/27): ").strip()
                planned = input("Planned headcount: ").strip()
                actual = input("Actual headcount: ").strip()
                service.add_cohort(
                    cpid, year,
                    planned_headcount=int(planned) if planned.isdigit() else None,
                    actual_headcount=int(actual) if actual.isdigit() else None)
                print("\n  Cohort recorded.")
            elif choice == "7":
                pid = int(input("Partner ID: ").strip())
                print("  Types: " + ", ".join(
                    f"{i + 1}={t}" for i, t in enumerate(REVIEW_TYPES)))
                rtype = REVIEW_TYPES[int(input("Review type number: ").strip()) - 1]
                rdate = input("Review date (YYYY-MM-DD): ").strip()
                reviewer = input("Reviewer: ").strip() or None
                outcome = input("Outcome: ").strip() or None
                findings = input("Findings: ").strip() or None
                nxt = input("Next review due (YYYY-MM-DD): ").strip() or None
                aid = input("Agreement ID (Enter to skip): ").strip()
                service.add_review(pid, rtype, rdate,
                                   agreement_id=int(aid) if aid.isdigit() else None,
                                   reviewer=reviewer, outcome=outcome,
                                   findings=findings, next_review_due=nxt)
                print("\n  Review recorded.")
            elif choice == "8":
                _print_table(service.overdue_reviews(), (
                    ("ID", "agreement_id", 5), ("Partner", "partner_name", 30),
                    ("Model", "delivery_model", 22), ("Risk", "risk_level", 7),
                    ("Due", "review_due", 12)))
            elif choice == "9":
                rows = service.over_recruited()
                _print_table(rows, (
                    ("ID", "agreement_id", 5), ("Partner", "partner_name", 30),
                    ("Cap", "max_students", 6), ("Enrolled", "enrolled", 9)))
            elif choice == "10":
                _print_table(service.provision_map(), (
                    ("Partner", "partner_name", 26),
                    ("Country", "country", 12),
                    ("Model", "delivery_model", 20),
                    ("Programme", "programme_title", 30),
                    ("Students", "students", 8)))
            elif choice == "11":
                rows = service.unlinked_programmes()
                if not rows:
                    print("\n  Every partner programme maps to a governed programme.")
                else:
                    _print_table(rows, (
                        ("ID", "collab_programme_id", 5),
                        ("Partner", "partner_name", 28),
                        ("Programme", "programme_title", 34),
                        ("Code", "programme_code", 12)))
        except (ValueError, IndexError) as exc:
            print(f"\n  ✗ {exc}")

        input("\nPress Enter to continue...")
