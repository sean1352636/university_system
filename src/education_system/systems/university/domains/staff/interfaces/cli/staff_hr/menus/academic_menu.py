"""
Academic Menu - Academic staff features CLI.

Everything is keyed on the signed-in username. Publications and grants are
the Research Office's records (``application.research_outputs`` /
``research_grants``) and teaching evaluations come from lecturer feedback
(shown only past their anonymity threshold).
"""

from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.domains.staff.domain.staff_hr.services import AcademicStaffManager
from education_system.systems.university.domains.staff.interfaces.cli.staff_hr.menus.profile_menu import (
    _run,
    session_actor,
)
from education_system.systems.university.infrastructure.database.db import get_connection, transaction


def display_academic_menu(user_id: str, is_admin: bool = False) -> None:
    """Display academic staff menu."""
    actor = session_actor(user_id)
    me = access.username_of(actor)
    is_admin = access.can(actor, 'hr')
    while True:
        print("\n" + "=" * 60)
        print("ACADEMIC STAFF")
        print("=" * 60)

        print("\n--- Teaching ---")
        print("  1. My Teaching Portfolio")
        print("  2. View Teaching Assignments")
        print("  3. Teaching Evaluations")

        print("\n--- Research ---")
        print("  4. My Research Profile")
        print("  5. Publications")
        print("  6. Research Grants")

        print("\n--- Supervision ---")
        print("  7. My Supervisions")
        print("  8. Supervision Requests")

        print("\n--- Professional ---")
        print("  9. Peer Observations")
        print("  10. External Examiner Duties")

        if is_admin:
            print("\n--- Admin ---")
            print("  11. Manage Teaching Loads")
            print("  12. Supervision Overview")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _run(lambda: _view_teaching_portfolio(actor, me))
        elif choice == '2':
            _run(lambda: _view_teaching_assignments(actor, me))
        elif choice == '3':
            _run(lambda: _view_evaluations(actor, me, is_admin))
        elif choice == '4':
            _run(lambda: _view_research_profile(actor, me))
        elif choice == '5':
            _run(lambda: _manage_publications(actor, me))
        elif choice == '6':
            _run(lambda: _view_grants(actor))
        elif choice == '7':
            _run(lambda: _view_supervisions(actor, me))
        elif choice == '8':
            _run(lambda: _supervision_requests(actor))
        elif choice == '9':
            _run(lambda: _peer_observations(actor, me))
        elif choice == '10':
            _run(lambda: _external_examiner(actor, me))
        elif choice == '11' and is_admin:
            _run(lambda: _manage_teaching_loads(actor))
        elif choice == '12' and is_admin:
            _run(lambda: _supervision_overview(actor))
        else:
            print("Invalid choice.")


def _researcher(conn, actor):
    from education_system.systems.university.application.research import access as research_access
    return research_access.researcher(conn, access.username_of(actor), access.role_of(actor))


def _view_teaching_portfolio(actor, me: str) -> None:
    """View teaching portfolio."""
    portfolio = AcademicStaffManager.get_teaching_portfolio(me, actor=actor)
    print("\n" + "-" * 60)
    print("MY TEACHING PORTFOLIO")
    print("-" * 60)

    if portfolio:
        print(f"\nTeaching Philosophy:\n{(portfolio.get('teaching_philosophy') or 'Not set')[:200]}")
        print(f"\nTeaching Interests: {portfolio.get('teaching_interests') or 'N/A'}")
        print(f"Innovations: {portfolio.get('teaching_innovations') or 'N/A'}")
        print(f"Professional Development: {portfolio.get('professional_development') or 'N/A'}")

        if portfolio.get('courses_taught'):
            print(f"\nCourses Taught: {portfolio.get('courses_taught')}")
        if portfolio.get('awards_recognition'):
            print(f"Teaching Awards: {portfolio.get('awards_recognition')}")
    else:
        print("No teaching portfolio found. Use 'Update Portfolio' to create one.")

    print("-" * 60)

    update = input("\nUpdate portfolio? (y/n): ").strip().lower()
    if update == 'y':
        _update_teaching_portfolio(actor, me)
    else:
        input("Press Enter to continue...")


def _update_teaching_portfolio(actor, me: str) -> None:
    """Update teaching portfolio."""
    print("\n--- Update Teaching Portfolio ---")
    philosophy = input("Teaching Philosophy:\n").strip()
    interests = input("Teaching Interests (comma-separated): ").strip()
    courses = input("Courses Taught: ").strip()

    updates = {}
    if philosophy:
        updates['teaching_philosophy'] = philosophy
    if interests:
        updates['teaching_interests'] = interests
    if courses:
        updates['courses_taught'] = courses

    if updates:
        AcademicStaffManager.update_teaching_portfolio(me, actor=actor, **updates)
        print("\nPortfolio updated.")
    else:
        print("\nNo changes made.")

    input("Press Enter to continue...")


def _view_teaching_assignments(actor, me: str) -> None:
    """View teaching assignments."""
    assignments = AcademicStaffManager.get_teaching_assignments(me, actor=actor)
    print("\n" + "-" * 60)
    print("MY TEACHING ASSIGNMENTS")
    print("-" * 60)

    if assignments:
        for a in assignments:
            print(f"\n  {a.get('course_code') or 'N/A'} - {a.get('course_name') or 'N/A'}")
            print(f"    Role: {a.get('role') or 'Instructor'}  ({a['source']})")
            print(f"    Term: {a.get('term') or 'N/A'} | Year: {a.get('academic_year') or 'N/A'}")
            if a.get('hours_per_week') is not None:
                print(f"    Hours/Week: {a['hours_per_week']}")
            if a.get('hours') is not None:
                print(f"    Hours: {a['hours']}")
    else:
        print("No teaching assignments found.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _view_evaluations(actor, me: str, is_admin: bool) -> None:
    """View teaching evaluations (lecturer feedback past its threshold)."""
    from education_system.systems.university.application.evaluation import lecturer_feedback
    with get_connection() as conn:
        result = lecturer_feedback.results(conn, me, me, admin=is_admin)
    print("\n" + "-" * 60)
    print("TEACHING EVALUATIONS")
    print("-" * 60)

    if result['modules']:
        for m in result['modules']:
            print(f"\n  {m['module_code']} - {m['academic_year']}")
            if m['withheld']:
                print(f"    Withheld: {m['responses']} of the {m['threshold']} responses needed")
                continue
            print(f"    Overall Rating: {m['means'].get('overall', 'N/A')}/5")
            print(f"    Responses: {m['responses']} of {m['invited']} invited")
            for comment in m['comments'][:3]:
                print(f"    \"{comment[:70]}\"")
        comparison = result['comparison']
        if comparison.get('last_year') is not None:
            print(f"\n  Last year overall: {comparison['last_year']}")
        if comparison['department'].get('overall') is not None:
            print(f"  Department overall: {comparison['department']['overall']} "
                  f"({comparison['department']['lecturers']} lecturers)")
    else:
        print("No evaluations found.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _view_research_profile(actor, me: str) -> None:
    """View research profile."""
    profile = AcademicStaffManager.get_research_profile(me, actor=actor)
    print("\n" + "-" * 60)
    print("MY RESEARCH PROFILE")
    print("-" * 60)

    if profile:
        print(f"\nResearch Interests: {profile.get('research_interests') or 'N/A'}")
        print("\nMetrics:")
        print(f"  Publications: {profile.get('total_publications') or 0}")
        print(f"  Citations: {profile.get('total_citations') or 0}")
        print(f"  H-Index: {profile.get('h_index') or 0}")
        if profile.get('orcid_id'):
            print(f"\nORCID: {profile.get('orcid_id')}")
        if profile.get('google_scholar_id'):
            print(f"Google Scholar: {profile.get('google_scholar_id')}")
        if profile.get('scopus_id'):
            print(f"Scopus: {profile.get('scopus_id')}")
    else:
        print("No research profile found.")

    print("-" * 60)

    update = input("\nUpdate profile? (y/n): ").strip().lower()
    if update == 'y':
        _update_research_profile(actor, me)
    else:
        input("Press Enter to continue...")


def _update_research_profile(actor, me: str) -> None:
    """Update research profile."""
    print("\n--- Update Research Profile ---")
    interests = input("Research Interests:\n").strip()
    orcid = input("ORCID ID: ").strip()
    h_index = input("H-Index (Enter to keep): ").strip()

    updates = {}
    if interests:
        updates['research_interests'] = interests
    if orcid:
        updates['orcid_id'] = orcid
    if h_index:
        updates['h_index'] = h_index

    if updates:
        AcademicStaffManager.update_research_profile(me, actor=actor, **updates)
        print("\nProfile updated.")
    else:
        print("\nNo changes made.")

    input("Press Enter to continue...")


def _manage_publications(actor, me: str) -> None:
    """Manage publications."""
    publications = AcademicStaffManager.get_publications(me, actor=actor)
    print("\n" + "-" * 60)
    print("MY PUBLICATIONS")
    print("-" * 60)

    if publications:
        for p in publications:
            pub_type = (p.get('publication_type') or 'output').upper()
            print(f"\n  [{pub_type}] {p.get('title', 'N/A')}")
            print(f"    Authors: {p.get('authors') or 'N/A'}")
            year = (p.get('publication_date') or '')[:4] or 'N/A'
            print(f"    {p.get('journal_name') or p.get('venue') or 'N/A'} ({year})")
            if p.get('citation_count'):
                print(f"    Citations: {p.get('citation_count')}")
            if p.get('doi'):
                print(f"    DOI: {p.get('doi')}")
    else:
        print("No publications found.")

    print("-" * 60)

    add = input("\nAdd publication? (y/n): ").strip().lower()
    if add == 'y':
        _add_publication(actor, me)
    else:
        input("Press Enter to continue...")


def _add_publication(actor, me: str) -> None:
    """Record an output with the Research Office (you must be an author)."""
    from education_system.systems.university.application.research import (
        outputs as research_outputs,
    )
    print("\n--- Add Publication ---")
    print("Types: " + ", ".join(research_outputs.TYPES))
    pub_type = input("Publication Type: ").strip() or 'Journal article'
    title = input("Title: ").strip()
    print(f"Authors, separated by ';' - mark colleagues with [username], e.g. Smith, J. [{me}]")
    authors = input("Authors: ").strip()
    journal = input("Journal/Venue: ").strip()
    date = input("Publication Date (YYYY-MM-DD): ").strip()
    doi = input("DOI: ").strip()

    if not title:
        print("\nTitle is required.")
    else:
        with transaction() as conn:
            pub_id = research_outputs.create(
                conn, _researcher(conn, actor),
                {'title': title, 'publication_type': pub_type, 'venue': journal or None,
                 'journal_name': journal or None, 'publication_date': date or None,
                 'doi': doi or None},
                authors or f"{access.display_name(me)} [{me}]")
        print(f"\nPublication added. ID: {pub_id}")

    input("Press Enter to continue...")


def _view_grants(actor) -> None:
    """View research grants you lead, co-investigate or oversee."""
    from education_system.systems.university.application.research import grants as research_grants
    with get_connection() as conn:
        grants = research_grants.listing(conn, _researcher(conn, actor))
    print("\n" + "-" * 60)
    print("RESEARCH GRANTS")
    print("-" * 60)

    me = access.username_of(actor)
    if grants:
        for g in grants:
            status = (g.get('status') or 'draft').upper()
            amount = g.get('awarded_amount') or g.get('requested_amount') or 0
            print(f"\n  [{status}] {g.get('grant_name') or g.get('title') or 'N/A'}")
            print(f"    Funder: {g.get('funding_agency') or 'N/A'}")
            print(f"    Amount: £{float(amount):,.2f}")
            print(f"    Period: {g.get('grant_period_start') or 'N/A'} to {g.get('grant_period_end') or 'N/A'}")
            print(f"    Role: {'PI' if g.get('principal_investigator_id') == me else 'Co-I / oversight'}")
    else:
        print("No grants found.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _view_supervisions(actor, me: str) -> None:
    """View supervisions."""
    supervisions = [s for s in AcademicStaffManager.get_supervisions(me, actor=actor)
                    if s.get('status') not in ('requested', 'declined')]
    print("\n" + "-" * 60)
    print("MY SUPERVISIONS")
    print("-" * 60)

    if supervisions:
        # Group by type
        def kind(s):
            return (s.get('program_type') or '').lower()
        phd = [s for s in supervisions if kind(s) == 'phd']
        masters = [s for s in supervisions if kind(s) == 'masters']
        other = [s for s in supervisions if kind(s) not in ('phd', 'masters')]

        if phd:
            print("\n[PhD Students]")
            for s in phd:
                print(f"  - {s.get('student_name') or 'N/A'} ({s.get('status') or 'active'})")
                print(f"    Topic: {(s.get('thesis_title') or 'N/A')[:50]}")
                print(f"    Role: {s.get('supervision_role') or 'primary'}")

        if masters:
            print("\n[Masters Students]")
            for s in masters:
                print(f"  - {s.get('student_name') or 'N/A'} ({s.get('status') or 'active'})")
                print(f"    Topic: {(s.get('thesis_title') or 'N/A')[:50]}")

        if other:
            print("\n[Other Supervisions]")
            for s in other:
                print(f"  - {s.get('student_name') or 'N/A'} - {s.get('program_type') or 'other'}")
    else:
        print("No active supervisions.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _supervision_requests(actor) -> None:
    """Handle supervision requests."""
    requests = AcademicStaffManager.get_supervision_requests(actor)
    print("\n" + "-" * 60)
    print("SUPERVISION REQUESTS")
    print("-" * 60)

    if not requests:
        print("No pending supervision requests.")
        input("\nPress Enter to continue...")
        return

    for i, r in enumerate(requests, 1):
        print(f"\n  {i}. {r.get('student_name') or 'N/A'}")
        print(f"     Program: {r.get('program_type') or 'N/A'}")
        print(f"     Topic: {(r.get('thesis_title') or 'N/A')[:60]}")
        print(f"     Requested: {(r.get('created_at') or 'N/A')[:10]}")

    print("-" * 60)

    try:
        choice = int(input("\nSelect request to respond (0 to abort): ").strip())
    except ValueError:
        print("\nInvalid input.")
        input("Press Enter to continue...")
        return
    if choice == 0:
        return
    if 1 <= choice <= len(requests):
        request = requests[choice - 1]
        action = input("(A)ccept or (D)ecline? ").strip().upper()

        if action == 'A':
            AcademicStaffManager.accept_supervision(request['supervision_id'], actor)
            print("\nSupervision accepted.")
        elif action == 'D':
            reason = input("Reason for declining: ").strip()
            AcademicStaffManager.decline_supervision(request['supervision_id'], reason, actor)
            print("\nRequest declined.")

    input("Press Enter to continue...")


def _peer_observations(actor, me: str) -> None:
    """View peer observations; acknowledge ones written about you."""
    observations = AcademicStaffManager.get_peer_observations(me, actor=actor)
    print("\n" + "-" * 60)
    print("PEER OBSERVATIONS")
    print("-" * 60)

    received = [o for o in observations if o.get('observee_id') == me]
    given = [o for o in observations if o.get('observer_id') == me]

    if received:
        print("\n[Observations Received]")
        for o in received:
            print(f"  - #{o['observation_id']} {o.get('observation_date') or 'N/A'}: "
                  f"{o.get('course_name') or o.get('course_code') or 'N/A'} ({o.get('status')})")
            print(f"    Observer: {o.get('observer_name') or 'N/A'}")
            if o.get('overall_rating'):
                print(f"    Rating: {o.get('overall_rating')}/5")
            if o.get('strengths'):
                print(f"    Strengths: {o['strengths'][:60]}")
            if o.get('areas_for_development'):
                print(f"    To develop: {o['areas_for_development'][:60]}")

    if given:
        print("\n[Observations Given]")
        for o in given:
            print(f"  - #{o['observation_id']} {o.get('observation_date') or 'N/A'}: "
                  f"{o.get('observee_name') or 'N/A'} ({o.get('status')})")
            print(f"    Course: {o.get('course_name') or o.get('course_code') or 'N/A'}")

    if not observations:
        print("No peer observations found.")

    print("-" * 60)
    waiting = [o for o in received if o.get('status') == 'submitted']
    if waiting:
        pick = input("\nAcknowledge observation # (Enter to skip): ").strip()
        if pick:
            AcademicStaffManager.acknowledge_observation(int(pick), actor=actor)
            print("Acknowledged.")
    input("\nPress Enter to continue...")


def _external_examiner(actor, me: str) -> None:
    """View examining duties."""
    duties = AcademicStaffManager.get_examining_duties(me, actor=actor)
    print("\n" + "-" * 60)
    print("EXTERNAL EXAMINER DUTIES")
    print("-" * 60)

    if duties:
        for d in duties:
            status = (d.get('status') or 'active').upper()
            print(f"\n  [{status}] {d.get('title') or 'N/A'}")
            print(f"    {d['kind']}: {d.get('detail') or ''}")
            print(f"    Date: {d.get('date') or 'N/A'}")
    else:
        print("No external examiner duties found.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _manage_teaching_loads(actor) -> None:
    """Admin: Manage teaching loads."""
    print("\n--- Teaching Load Overview ---")
    loads = AcademicStaffManager.teaching_load_summary(actor)

    if loads:
        print("\nStaff Teaching Hours:")
        for row in loads:
            print(f"  {row['name']}: {row['contact_hours']} contact hrs/week, "
                  f"{row['module_hours']} module-team hrs")
            print(f"    Courses: {row['course_count']} | Credits: {row['credits']} | "
                  f"Status: {row['load_status']}")
    else:
        print("No teaching load data.")

    input("\nPress Enter to continue...")


def _supervision_overview(actor) -> None:
    """Admin: Supervision overview."""
    print("\n--- Supervision Overview ---")
    summary = AcademicStaffManager.supervision_summary(actor)

    print("\nSupervision Statistics:")
    print(f"  Total PhD Students: {summary['phd_count']}")
    print(f"  Total Masters Students: {summary['masters_count']}")
    print(f"  Other Research Students: {summary['other_count']}")
    print(f"  Supervisors at Capacity ({summary['capacity']}+): {summary['at_capacity']}")
    print(f"  Available Supervisors: {summary['available']}")

    if summary['by_department']:
        print("\nBy Department:")
        for dept, count in summary['by_department'].items():
            print(f"  {dept}: {count}")

    input("\nPress Enter to continue...")
