"""Apprenticeship Employer Portal CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.employer_portal.services.employer_portal_service import EmployerPortalService
from education_system.college_system.infrastructure.auth.core import UserAuth


def _list_employers(svc):
    """List employers."""
    print_header("List Employers")
    try:
        show_all = input("  Include inactive? (y/n, default=n): ").strip().lower() == "y"
        employers = svc.list_employers(active_only=not show_all)
        if not employers:
            print("\n  No employers found.")
        else:
            print(f"\n  {'ID':<5} {'Company':<22} {'Contact':<15} {'Sector':<14} "
                  f"{'Size':<8} {'Levy':<5} {'Portal':<7} {'Active':<7}")
            print("  " + "-" * 88)
            for e in employers:
                levy = "Yes" if e.get('levy_payer') else "No"
                portal = "Yes" if e.get('portal_access_enabled') else "No"
                active = "Yes" if e.get('is_active') else "No"
                print(f"  {e['id']:<5} {(e.get('company_name') or '')[:22]:<22} "
                      f"{(e.get('contact_name') or '')[:15]:<15} "
                      f"{(e.get('sector') or '-')[:14]:<14} "
                      f"{(e.get('company_size') or '-'):<8} "
                      f"{levy:<5} {portal:<7} {active:<7}")
            print(f"\n  Total: {len(employers)} employer(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


def _register_employer(svc):
    """Register a new employer."""
    print_header("Register Employer")
    try:
        name = input("  Company name: ").strip()
        if not name:
            print("\n  Error: Company name is required.")
            return
        contact = input("  Contact name: ").strip()
        email = input("  Contact email: ").strip()
        phone = input("  Contact phone: ").strip()
        sector = input("  Sector: ").strip()
        size = input("  Company size (small/medium/large, default=small): ").strip() or "small"
        levy = input("  Levy payer? (y/n, default=n): ").strip().lower() == "y"
        result = svc.register_employer(name, contact, email, phone, sector,
                                       company_size=size, levy_payer=1 if levy else 0)
        eid = result if isinstance(result, int) else result.get('id', result)
        print(f"\n  Employer #{eid} registered.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_employer(svc):
    """Update employer details."""
    print_header("Update Employer")
    try:
        eid = int(input("  Employer ID: ").strip())
        updates = {}
        for field, prompt in [
            ("company_name", "  New company name (Enter to keep): "),
            ("contact_name", "  New contact (Enter to keep): "),
            ("contact_email", "  New email (Enter to keep): "),
            ("contact_phone", "  New phone (Enter to keep): "),
            ("sector", "  New sector (Enter to keep): "),
            ("company_size", "  New size (Enter to keep): "),
        ]:
            val = input(prompt).strip()
            if val:
                updates[field] = val
        levy = input("  Levy payer? (y/n/Enter to keep): ").strip().lower()
        if levy in ("y", "n"):
            updates["levy_payer"] = 1 if levy == "y" else 0
        portal = input("  Portal access? (y/n/Enter to keep): ").strip().lower()
        if portal in ("y", "n"):
            updates["portal_access_enabled"] = 1 if portal == "y" else 0
        if updates:
            svc.update_employer(eid, **updates)
            print("\n  Employer updated.")
        else:
            print("\n  No changes made.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _link_learner(svc):
    """Link a learner to an employer."""
    print_header("Link Learner")
    try:
        eid = int(input("  Employer ID: ").strip())
        sid = int(input("  Student ID: ").strip())
        std = input("  Apprenticeship standard: ").strip()
        sd = input("  Start date (YYYY-MM-DD): ").strip()
        ed = input("  Expected end date (YYYY-MM-DD): ").strip()
        if not std or not sd or not ed:
            print("\n  Error: Standard, start date, and end date are required.")
            return
        mentor = input("  Mentor name (blank=none): ").strip() or None
        mentor_email = input("  Mentor email (blank=none): ").strip() or None
        result = svc.link_learner(eid, sid, std, sd, ed,
                                  mentor_name=mentor, mentor_email=mentor_email)
        lid = result if isinstance(result, int) else result.get('id', result)
        print(f"\n  Learner link #{lid} created.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_links(svc):
    """List learner-employer links."""
    print_header("List Learner Links")
    try:
        eid = input("  Employer ID filter (Enter for all): ").strip()
        eid = int(eid) if eid else None
        sid = input("  Student ID filter (Enter for all): ").strip()
        sid = int(sid) if sid else None
        status = input("  Status filter (Enter for all): ").strip() or None
        links = svc.list_learner_links(employer_id=eid, student_id=sid, status=status)
        if not links:
            print("\n  No learner links found.")
        else:
            print(f"\n  {'ID':<5} {'Employer':>9} {'Student':>8} {'Standard':<20} "
                  f"{'Start':<12} {'End':<12} {'Mentor':<12} {'Status':<10}")
            print("  " + "-" * 93)
            for ll in links:
                print(f"  {ll['id']:<5} {ll.get('employer_id', ''):>9} "
                      f"{ll.get('student_id', ''):>8} "
                      f"{(ll.get('apprenticeship_standard') or '')[:20]:<20} "
                      f"{(ll.get('start_date') or '-'):<12} "
                      f"{(ll.get('expected_end_date') or '-'):<12} "
                      f"{(ll.get('mentor_name') or '-')[:12]:<12} "
                      f"{(ll.get('status') or '-'):<10}")
            print(f"\n  Total: {len(links)} link(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_link(svc):
    """Update a learner link."""
    print_header("Update Learner Link")
    try:
        lid = int(input("  Learner link ID: ").strip())
        updates = {}
        for field, prompt in [
            ("apprenticeship_standard", "  New standard (Enter to keep): "),
            ("expected_end_date", "  New expected end (Enter to keep): "),
            ("mentor_name", "  New mentor name (Enter to keep): "),
            ("mentor_email", "  New mentor email (Enter to keep): "),
            ("status", "  New status (active/completed/withdrawn, Enter to keep): "),
        ]:
            val = input(prompt).strip()
            if val:
                updates[field] = val
        if updates:
            svc.update_learner_link(lid, **updates)
            print("\n  Learner link updated.")
        else:
            print("\n  No changes made.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _schedule_review(svc):
    """Schedule a progress review."""
    print_header("Schedule Review")
    try:
        llid = int(input("  Learner link ID: ").strip())
        rd = input("  Review date (YYYY-MM-DD): ").strip()
        rt = input("  Review type (monthly/tripartite/gateway, default=monthly): ").strip() or "monthly"
        result = svc.schedule_review(llid, rd, review_type=rt)
        rid = result if isinstance(result, int) else result.get('id', result)
        print(f"\n  Review #{rid} scheduled.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_reviews(svc):
    """List progress reviews."""
    print_header("List Reviews")
    try:
        llid = input("  Learner link ID filter (Enter for all): ").strip()
        llid = int(llid) if llid else None
        status = input("  Status filter (scheduled/completed, Enter for all): ").strip() or None
        reviews = svc.list_reviews(learner_link_id=llid, status=status)
        if not reviews:
            print("\n  No reviews found.")
        else:
            print(f"\n  {'ID':<5} {'Link':>5} {'Date':<12} {'Type':<12} "
                  f"{'On Track':<9} {'OTJ Hrs':>8} {'Status':<12}")
            print("  " + "-" * 68)
            for r in reviews:
                on_track = "Yes" if r.get('on_track') else ("No" if r.get('on_track') is not None and not r.get('on_track') else "-")
                otj = r.get('off_the_job_hours')
                otj_str = f"{otj:>8.1f}" if otj is not None else "       -"
                print(f"  {r['id']:<5} {r.get('learner_link_id', ''):>5} "
                      f"{(r.get('review_date') or '-'):<12} "
                      f"{(r.get('review_type') or '-'):<12} "
                      f"{on_track:<9} "
                      f"{otj_str} "
                      f"{(r.get('status') or '-'):<12}")
            print(f"\n  Total: {len(reviews)} review(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


def _complete_review(svc):
    """Complete a progress review."""
    print_header("Complete Review")
    try:
        rid = int(input("  Review ID: ").strip())
        on_track = input("  On track? (y/n): ").strip().lower() == "y"
        ksbm = input("  KSBM progress: ").strip()
        otj = float(input("  Off-the-job hours: ").strip())
        efb = input("  Employer feedback: ").strip()
        actions = input("  Actions (blank=none): ").strip() or None
        next_review = input("  Next review date (YYYY-MM-DD, blank=none): ").strip() or None
        svc.complete_review(rid, on_track, ksbm, otj, efb,
                            actions=actions, next_review_date=next_review)
        print("\n  Review completed.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _sign_off_review(svc):
    """Sign off a progress review."""
    print_header("Sign Off Review")
    try:
        rid = int(input("  Review ID: ").strip())
        st = input("  Signer type (employer/learner/assessor): ").strip()
        sn = input("  Signer name: ").strip()
        if not st or not sn:
            print("\n  Error: Signer type and name are required.")
            return
        comments = input("  Comments (blank=none): ").strip() or None
        svc.sign_off_review(rid, st, sn, comments=comments)
        print("\n  Review signed off.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _learner_progress(svc):
    """Learner progress summary."""
    print_header("Learner Progress")
    try:
        sid = int(input("  Student ID: ").strip())
        progress = svc.get_learner_progress(sid)
        if progress.get('status') == 'no_active_link':
            print(f"\n  No active learner link found for student {sid}.")
            return

        link = progress.get('link', {})
        print(f"\n  Student ID:    {sid}")
        print(f"  Standard:      {link.get('apprenticeship_standard', '-')}")
        print(f"  Start Date:    {link.get('start_date', '-')}")
        print(f"  Expected End:  {link.get('expected_end_date', '-')}")
        print(f"  Mentor:        {link.get('mentor_name', '-')}")
        print(f"  Completion:    {progress.get('completion_pct', 0):.1f}%")
        print(f"  Total Reviews: {progress.get('num_reviews', 0)}")
        print(f"  OTJ Hours:     {progress.get('total_otj_hours', 0):.1f} "
              f"(target: {progress.get('otj_target', 0)})")

        reviews = progress.get('reviews', [])
        if reviews:
            print(f"\n  Recent Reviews:")
            print(f"  {'Date':<12} {'Type':<12} {'On Track':<9} {'OTJ':>8} {'Status':<10}")
            print("  " + "-" * 55)
            for r in reviews[:5]:
                on_track = "Yes" if r.get('on_track') else ("No" if r.get('on_track') is not None else "-")
                otj = r.get('off_the_job_hours')
                otj_str = f"{otj:>8.1f}" if otj is not None else "       -"
                print(f"  {(r.get('review_date') or '-'):<12} "
                      f"{(r.get('review_type') or '-'):<12} "
                      f"{on_track:<9} {otj_str} "
                      f"{(r.get('status') or '-'):<10}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _employer_dashboard(svc):
    """Employer dashboard."""
    print_header("Employer Dashboard")
    try:
        eid = int(input("  Employer ID: ").strip())
        dash = svc.get_employer_dashboard(eid)
        print(f"\n  Employer ID:      {eid}")
        print(f"  Total Learners:   {dash.get('total_learners', 0)}")
        print(f"  Active Learners:  {dash.get('active_learners', 0)}")

        summaries = dash.get('learner_summaries', [])
        if summaries:
            print(f"\n  {'Student':>8} {'Standard':<20} {'Status':<10} "
                  f"{'Reviews':>8} {'On Track':>9} {'OTJ':>8}")
            print("  " + "-" * 68)
            total_on_track = 0
            total_reviews = 0
            for s in summaries:
                rs = s.get('review_summary', {})
                completed = rs.get('completed', 0) or 0
                on_track = rs.get('on_track', 0) or 0
                otj = rs.get('total_otj', 0) or 0
                total_on_track += on_track
                total_reviews += completed
                print(f"  {s.get('student_id', ''):>8} "
                      f"{(s.get('apprenticeship_standard') or '')[:20]:<20} "
                      f"{(s.get('status') or '-'):<10} "
                      f"{completed:>8} {on_track:>9} {otj:>8.1f}")
            if total_reviews > 0:
                pct = total_on_track * 100.0 / total_reviews
                print(f"\n  On-track rate: {pct:.1f}%")
    except Exception as e:
        print(f"\n  Error: {e}")


def _otj_summary(svc):
    """Off-the-job hours summary."""
    print_header("OTJ Summary")
    try:
        llid = int(input("  Learner link ID: ").strip())
        summary = svc.get_off_the_job_summary(llid)
        print(f"\n  {'Metric':<25} {'Value':>12}")
        print("  " + "-" * 40)
        print(f"  {'Total OTJ Hours':<25} {summary.get('total_hours', 0):>12.1f}")
        print(f"  {'Target Hours':<25} {summary.get('target_hours', 0):>12.1f}")
        print(f"  {'% Complete':<25} {summary.get('percentage_complete', 0):>11.1f}%")
    except Exception as e:
        print(f"\n  Error: {e}")


def _overdue_reviews(svc):
    """Show overdue reviews."""
    print_header("Overdue Reviews")
    try:
        reviews = svc.get_overdue_reviews()
        if not reviews:
            print("\n  No overdue reviews found.")
        else:
            print(f"\n  {'ID':<5} {'Link':>5} {'Student':>8} {'Employer':>9} "
                  f"{'Standard':<18} {'Scheduled':<12} {'Type':<10}")
            print("  " + "-" * 72)
            for r in reviews:
                print(f"  {r['id']:<5} {r.get('learner_link_id', ''):>5} "
                      f"{r.get('student_id', ''):>8} "
                      f"{r.get('employer_id', ''):>9} "
                      f"{(r.get('apprenticeship_standard') or '')[:18]:<18} "
                      f"{(r.get('review_date') or '-'):<12} "
                      f"{(r.get('review_type') or '-'):<10}")
            print(f"\n  {len(reviews)} overdue review(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


def _epa_readiness(svc):
    """EPA readiness check."""
    print_header("EPA Readiness Check")
    try:
        llid = int(input("  Learner link ID: ").strip())
        epa = svc.get_epa_readiness(llid)
        print(f"\n  {'Metric':<25} {'Value':>12}")
        print("  " + "-" * 40)
        print(f"  {'Total Reviews':<25} {epa.get('total_reviews', 0):>12}")
        print(f"  {'Completed Reviews':<25} {epa.get('completed_reviews', 0):>12}")
        print(f"  {'OTJ Hours':<25} {epa.get('otj_hours', 0):>12.1f}")
        print(f"  {'OTJ Target':<25} {epa.get('otj_target', 0):>12.1f}")
        print(f"  {'OTJ Met':<25} {'Yes' if epa.get('otj_met') else 'No':>12}")
        print(f"  {'Gateway Signed':<25} {'Yes' if epa.get('gateway_signed') else 'No':>12}")
        ready = epa.get('ready_for_epa', False)
        print(f"\n  EPA Readiness: {'READY' if ready else 'NOT READY'}")
    except Exception as e:
        print(f"\n  Error: {e}")


def employer_portal_menu(auth: UserAuth):
    """Apprenticeship Employer Portal management menu."""
    svc = EmployerPortalService(auth._db_path)

    while True:
        print_header("Apprenticeship Employer Portal")
        options = [
            ("1", "List Employers"),
            ("2", "Register Employer"),
            ("3", "Update Employer"),
            ("4", "Link Learner"),
            ("5", "List Learner Links"),
            ("6", "Update Learner Link"),
            ("7", "Schedule Review"),
            ("8", "List Reviews"),
            ("9", "Complete Review"),
            ("10", "Sign Off Review"),
            ("11", "Learner Progress"),
            ("12", "Employer Dashboard"),
            ("13", "OTJ Summary"),
            ("14", "Overdue Reviews"),
            ("15", "EPA Readiness Check"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            _list_employers(svc)
        elif choice == "2":
            _register_employer(svc)
        elif choice == "3":
            _update_employer(svc)
        elif choice == "4":
            _link_learner(svc)
        elif choice == "5":
            _list_links(svc)
        elif choice == "6":
            _update_link(svc)
        elif choice == "7":
            _schedule_review(svc)
        elif choice == "8":
            _list_reviews(svc)
        elif choice == "9":
            _complete_review(svc)
        elif choice == "10":
            _sign_off_review(svc)
        elif choice == "11":
            _learner_progress(svc)
        elif choice == "12":
            _employer_dashboard(svc)
        elif choice == "13":
            _otj_summary(svc)
        elif choice == "14":
            _overdue_reviews(svc)
        elif choice == "15":
            _epa_readiness(svc)
        else:
            print("\n  Invalid option.")
