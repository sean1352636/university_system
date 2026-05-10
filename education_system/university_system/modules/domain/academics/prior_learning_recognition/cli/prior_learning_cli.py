"""Accreditation of Prior Learning (APL/RPL) CLI."""


def display_prior_learning_menu(auth):
    from education_system.university_system.modules.domain.academics.prior_learning_recognition.services.prior_learning_service import (
        CLAIM_TYPES,
        PriorLearningService,
    )

    service = PriorLearningService()
    user = auth.current_user.get("username") if auth and auth.current_user else "system"

    while True:
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 70)
        print("ACCREDITATION OF PRIOR LEARNING (APL/RPL)".center(70))
        print("=" * 70)
        print("\n  1. Create Claim")
        print("  2. List Claims")
        print("  3. View Claim Detail")
        print("  4. Add Evidence")
        print("  5. Verify Evidence")
        print("  6. Submit Claim")
        print("  7. Review Claim (approve / partial / reject)")
        print("  8. Award Credits")
        print("  9. Statistics")
        print("\n  0. Back")
        print("=" * 70)

        choice = input("\nSelect: ").strip()
        if choice == "0":
            break
        elif choice == "1":
            claimant = input("Claimant ID: ").strip()
            claimant_name = input("Claimant name: ").strip() or None
            print(f"  Types: {', '.join(CLAIM_TYPES)}")
            ctype = input("Claim type: ").strip()
            target = input("Target course (optional): ").strip() or None
            qual = input("Target qualification (optional): ").strip() or None
            summary = input("Summary: ").strip() or None
            try:
                credits = int(input("Credits requested: ").strip() or "0")
            except ValueError:
                credits = 0
            try:
                cid = service.create_claim(
                    claimant, ctype, target, qual, claimant_name, summary, credits
                )
                print(f"\nClaim created with ID: {cid}")
            except ValueError as e:
                print(f"\n❌ {e}")
        elif choice == "2":
            status = input("Filter by status (Enter for all): ").strip() or None
            claims = service.list_claims(status=status)
            print(f"\n{'ID':<5} {'Claimant':<15} {'Type':<22} {'Course':<20} "
                  f"{'Req':<5} {'Awd':<5} {'Status':<12}")
            print("-" * 90)
            for c in claims:
                print(
                    f"{c['id']:<5} {(c.get('claimant_id') or '')[:14]:<15} "
                    f"{(c.get('claim_type') or '')[:21]:<22} "
                    f"{(c.get('target_course') or '')[:19]:<20} "
                    f"{c.get('credits_requested', 0):<5} "
                    f"{c.get('credits_awarded', 0):<5} "
                    f"{c.get('status', ''):<12}"
                )
        elif choice == "3":
            try:
                cid = int(input("Claim ID: ").strip())
            except ValueError:
                print("Invalid ID.")
                input("\nPress Enter to continue...")
                continue
            claim = service.get_claim(cid)
            if not claim:
                print("Not found.")
            else:
                print("\n--- Claim ---")
                for k, v in claim.items():
                    print(f"  {k}: {v}")
                print("\n--- Evidence ---")
                for ev in service.list_evidence(cid):
                    mark = "✓" if ev.get("verified") else " "
                    print(f"  [{mark}] {ev['id']}: {ev.get('title')} "
                          f"({ev.get('evidence_type') or '?'})")
                print("\n--- Credit Awards ---")
                for aw in service.list_awards(cid):
                    print(f"  {aw['id']}: {aw.get('module_code') or ''} "
                          f"{aw.get('module_name') or ''} — "
                          f"{aw.get('credits_awarded')} credits "
                          f"(L{aw.get('level') or '?'})")
        elif choice == "4":
            try:
                cid = int(input("Claim ID: ").strip())
            except ValueError:
                print("Invalid ID.")
                input("\nPress Enter to continue...")
                continue
            title = input("Title: ").strip()
            etype = input("Evidence type (certificate/letter/portfolio/other): ").strip() or None
            desc = input("Description: ").strip() or None
            issuer = input("Issuing body: ").strip() or None
            issue_date = input("Issue date (YYYY-MM-DD): ").strip() or None
            file_path = input("File path (optional): ").strip() or None
            eid = service.add_evidence(cid, title, etype, desc, file_path, issuer, issue_date)
            print(f"\nEvidence added with ID: {eid}")
        elif choice == "5":
            try:
                eid = int(input("Evidence ID: ").strip())
            except ValueError:
                print("Invalid ID.")
                input("\nPress Enter to continue...")
                continue
            service.verify_evidence(eid, verified_by=user)
            print("Evidence verified.")
        elif choice == "6":
            try:
                cid = int(input("Claim ID: ").strip())
            except ValueError:
                print("Invalid ID.")
                input("\nPress Enter to continue...")
                continue
            service.submit_claim(cid)
            print("Claim submitted.")
        elif choice == "7":
            try:
                cid = int(input("Claim ID: ").strip())
            except ValueError:
                print("Invalid ID.")
                input("\nPress Enter to continue...")
                continue
            decision = input("Decision (approved/partial/rejected/under_review): ").strip()
            notes = input("Notes: ").strip() or None
            try:
                service.review_claim(cid, decision, reviewed_by=user, notes=notes)
                print("Decision recorded.")
            except ValueError as e:
                print(f"\n❌ {e}")
        elif choice == "8":
            try:
                cid = int(input("Claim ID: ").strip())
                credits = int(input("Credits to award: ").strip())
            except ValueError:
                print("Invalid input.")
                input("\nPress Enter to continue...")
                continue
            module_code = input("Module code: ").strip() or None
            module_name = input("Module name: ").strip() or None
            try:
                level = int(input("Level (4/5/6/7): ").strip() or "0") or None
            except ValueError:
                level = None
            grade = input("Grade (optional): ").strip() or None
            notes = input("Notes: ").strip() or None
            aid = service.award_credits(
                cid, credits, module_code, module_name, level, grade, user, notes
            )
            print(f"\nCredit award recorded with ID: {aid}")
        elif choice == "9":
            stats = service.get_statistics()
            print(f"\n  Total claims:        {stats['total_claims']}")
            print(f"  Credits requested:   {stats['credits_requested']}")
            print(f"  Credits awarded:     {stats['credits_awarded']}")
            print(f"  Approval rate:       {stats['approval_rate_pct']}%")
            print("\n  By status:")
            for s, c in stats.get("by_status", {}).items():
                print(f"    {s}: {c}")
            print("\n  By type:")
            for t, c in stats.get("by_type", {}).items():
                print(f"    {t}: {c}")

        input("\nPress Enter to continue...")
