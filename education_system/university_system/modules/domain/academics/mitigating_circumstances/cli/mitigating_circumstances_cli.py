"""Mitigating Circumstances (MC/EC) CLI."""


def display_mitigating_circumstances_menu(auth):
    from education_system.university_system.modules.domain.academics.mitigating_circumstances.services.mitigating_circumstances_service import (
        MitigatingCircumstancesService, VALID_GROUNDS, VALID_OUTCOMES,
    )
    service = MitigatingCircumstancesService()

    user = (auth.current_user or {}) if auth else {}
    username = user.get('username') or user.get('user_id') or 'unknown'

    while True:
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 70)
        print("MITIGATING CIRCUMSTANCES (MC / EC)".center(70))
        print("=" * 70)
        print("\n  1. Submit Claim")
        print("  2. List Claims")
        print("  3. View Claim Detail")
        print("  4. Add Evidence")
        print("  5. Verify Evidence")
        print("  6. Schedule Panel")
        print("  7. Assign Claim to Panel")
        print("  8. Record Panel Decision")
        print("  9. Grant Deadline Extension")
        print(" 10. List Extensions for Student")
        print(" 11. Statistics")
        print("\n  0. Back")
        print("=" * 70)

        choice = input("\nSelect: ").strip()
        try:
            if choice == '0':
                break
            elif choice == '1':
                sid = input("Student ID: ").strip()
                module = input("Module code: ").strip() or None
                aref = input("Assessment ref: ").strip() or None
                print(f"Grounds options: {', '.join(VALID_GROUNDS)}")
                grounds = input("Grounds: ").strip() or None
                desc = input("Description: ").strip()
                pstart = input("Period start (YYYY-MM-DD): ").strip() or None
                pend = input("Period end (YYYY-MM-DD): ").strip() or None
                impact = input("Impact statement: ").strip() or None
                remedy = input("Requested remedy: ").strip() or None
                cid = service.submit_claim(
                    student_id=sid, module_code=module, assessment_ref=aref,
                    grounds=grounds, description=desc, period_start=pstart,
                    period_end=pend, impact_statement=impact,
                    requested_remedy=remedy, submitted_by=username,
                )
                print(f"\nClaim submitted with ID: {cid}")
            elif choice == '2':
                sid = input("Filter by student ID (Enter for all): ").strip() or None
                claims = service.list_claims(student_id=sid)
                print(f"\n{'ID':<5} {'Student':<12} {'Module':<10} {'Grounds':<14} {'Status':<18}")
                print("-" * 65)
                for c in claims:
                    print(f"{c['id']:<5} {c['student_id']:<12} {(c.get('module_code') or ''):<10} "
                          f"{(c.get('grounds') or ''):<14} {c['status']:<18}")
            elif choice == '3':
                cid = int(input("Claim ID: ").strip())
                claim = service.get_claim(cid)
                if not claim:
                    print("Not found.")
                else:
                    print(f"\nClaim #{claim['id']} — student {claim['student_id']}")
                    print(f"  Status:    {claim['status']}")
                    print(f"  Module:    {claim.get('module_code') or '-'}  "
                          f"Assessment: {claim.get('assessment_ref') or '-'}")
                    print(f"  Grounds:   {claim.get('grounds') or '-'}")
                    print(f"  Period:    {claim.get('period_start') or '-'} → "
                          f"{claim.get('period_end') or '-'}")
                    print(f"  Description: {claim.get('description') or '-'}")
                    print(f"  Impact:    {claim.get('impact_statement') or '-'}")
                    print(f"  Remedy:    {claim.get('requested_remedy') or '-'}")
                    evidence = service.list_evidence(cid)
                    print(f"\n  Evidence ({len(evidence)}):")
                    for e in evidence:
                        verified = '✓' if e.get('verified') else '·'
                        print(f"    [{verified}] {e.get('evidence_type','?'):<14} "
                              f"{e.get('description','')[:40]:<40} {e.get('received_date','')}")
                    extensions = service.list_extensions(claim_id=cid)
                    if extensions:
                        print(f"\n  Extensions ({len(extensions)}):")
                        for ex in extensions:
                            print(f"    {ex['original_deadline']} → {ex['new_deadline']} "
                                  f"(+{ex['extension_days']}d) — {ex.get('reason') or ''}")
            elif choice == '4':
                cid = int(input("Claim ID: ").strip())
                etype = input("Evidence type (medical_letter/death_certificate/email/other): ").strip()
                desc = input("Description: ").strip()
                docref = input("Document ref/path: ").strip() or None
                eid = service.add_evidence(claim_id=cid, evidence_type=etype,
                                           description=desc, document_ref=docref)
                print(f"Evidence #{eid} added.")
            elif choice == '5':
                eid = int(input("Evidence ID: ").strip())
                service.verify_evidence(eid, verified_by=username, verified=True)
                print("Evidence verified.")
            elif choice == '6':
                date = input("Panel date (YYYY-MM-DD): ").strip()
                chair = input("Chair: ").strip() or None
                members = input("Members (comma separated): ").strip() or None
                location = input("Location: ").strip() or None
                pid = service.schedule_panel(date, chair, members, location)
                print(f"Panel #{pid} scheduled.")
            elif choice == '7':
                pid = int(input("Panel ID: ").strip())
                cid = int(input("Claim ID: ").strip())
                service.assign_claim_to_panel(pid, cid)
                print("Claim assigned.")
            elif choice == '8':
                pid = int(input("Panel ID: ").strip())
                cid = int(input("Claim ID: ").strip())
                decision = input("Decision (approved/rejected/deferred): ").strip()
                print(f"Outcome options: {', '.join(VALID_OUTCOMES)}")
                outcome = input("Outcome: ").strip()
                rationale = input("Rationale: ").strip() or None
                service.record_panel_decision(pid, cid, decision, outcome, rationale)
                print("Decision recorded.")
            elif choice == '9':
                cid = int(input("Claim ID: ").strip())
                orig = input("Original deadline (YYYY-MM-DD): ").strip()
                days = input("Extension days (Enter to use new date): ").strip()
                new = None
                if days:
                    days_int = int(days)
                else:
                    new = input("New deadline (YYYY-MM-DD): ").strip()
                    days_int = None
                reason = input("Reason: ").strip() or None
                ext_id = service.grant_extension(
                    claim_id=cid, original_deadline=orig,
                    extension_days=days_int, new_deadline=new,
                    granted_by=username, reason=reason,
                )
                ext = service.list_extensions(claim_id=cid)[0]
                print(f"Extension #{ext_id}: {ext['original_deadline']} → "
                      f"{ext['new_deadline']} (+{ext['extension_days']}d)")
            elif choice == '10':
                sid = input("Student ID: ").strip()
                exts = service.list_extensions(student_id=sid)
                print(f"\n{'ID':<5} {'Module':<10} {'Assessment':<14} {'Original':<12} "
                      f"{'New':<12} {'Days':<6}")
                print("-" * 65)
                for ex in exts:
                    print(f"{ex['id']:<5} {(ex.get('module_code') or ''):<10} "
                          f"{(ex.get('assessment_ref') or ''):<14} "
                          f"{ex['original_deadline']:<12} {ex['new_deadline']:<12} "
                          f"{ex['extension_days']:<6}")
            elif choice == '11':
                stats = service.claim_statistics()
                print(f"\nTotal claims:        {stats['total_claims']}")
                print(f"Extensions granted:  {stats['extensions_granted']}")
                print("\nBy status:")
                for k, v in stats['by_status'].items():
                    print(f"  {k:<20} {v}")
                print("\nBy grounds:")
                for k, v in stats['by_grounds'].items():
                    print(f"  {(k or 'unknown'):<20} {v}")
        except Exception as e:
            print(f"\nError: {e}")
        input("\nPress Enter to continue...")
