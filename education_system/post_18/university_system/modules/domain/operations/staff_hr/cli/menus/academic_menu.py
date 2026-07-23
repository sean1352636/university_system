"""
Academic Menu - Academic staff features CLI.
"""

from education_system.post_18.university_system.modules.domain.operations.staff_hr.services import AcademicStaffManager


def display_academic_menu(user_id: str, is_admin: bool = False) -> None:
    """Display academic staff menu."""
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
            _view_teaching_portfolio(user_id)
        elif choice == '2':
            _view_teaching_assignments(user_id)
        elif choice == '3':
            _view_evaluations(user_id)
        elif choice == '4':
            _view_research_profile(user_id)
        elif choice == '5':
            _manage_publications(user_id)
        elif choice == '6':
            _view_grants(user_id)
        elif choice == '7':
            _view_supervisions(user_id)
        elif choice == '8':
            _supervision_requests(user_id)
        elif choice == '9':
            _peer_observations(user_id)
        elif choice == '10':
            _external_examiner(user_id)
        elif choice == '11' and is_admin:
            _manage_teaching_loads()
        elif choice == '12' and is_admin:
            _supervision_overview()
        else:
            print("Invalid choice.")


def _view_teaching_portfolio(user_id: str) -> None:
    """View teaching portfolio."""
    portfolio = AcademicStaffManager.get_teaching_portfolio(user_id)
    print("\n" + "-" * 60)
    print("MY TEACHING PORTFOLIO")
    print("-" * 60)

    if portfolio:
        print(f"\nTeaching Philosophy:\n{portfolio.get('teaching_philosophy', 'Not set')[:200]}")
        print(f"\nSpecializations: {portfolio.get('specializations', 'N/A')}")
        print(f"Teaching Style: {portfolio.get('teaching_style', 'N/A')}")
        print(f"Years Teaching: {portfolio.get('years_teaching', 'N/A')}")

        if portfolio.get('courses_taught'):
            print(f"\nCourses Taught: {portfolio.get('courses_taught')}")
        if portfolio.get('awards'):
            print(f"Teaching Awards: {portfolio.get('awards')}")
    else:
        print("No teaching portfolio found. Use 'Update Portfolio' to create one.")

    print("-" * 60)

    update = input("\nUpdate portfolio? (y/n): ").strip().lower()
    if update == 'y':
        _update_teaching_portfolio(user_id)
    else:
        input("Press Enter to continue...")


def _update_teaching_portfolio(user_id: str) -> None:
    """Update teaching portfolio."""
    print("\n--- Update Teaching Portfolio ---")
    philosophy = input("Teaching Philosophy:\n").strip()
    specializations = input("Specializations (comma-separated): ").strip()
    style = input("Teaching Style: ").strip()

    updates = {}
    if philosophy:
        updates['teaching_philosophy'] = philosophy
    if specializations:
        updates['specializations'] = specializations
    if style:
        updates['teaching_style'] = style

    if updates:
        AcademicStaffManager.update_teaching_portfolio(user_id, **updates)
        print("\nPortfolio updated.")
    else:
        print("\nNo changes made.")

    input("Press Enter to continue...")


def _view_teaching_assignments(user_id: str) -> None:
    """View teaching assignments."""
    assignments = AcademicStaffManager.get_teaching_assignments(user_id)
    print("\n" + "-" * 60)
    print("MY TEACHING ASSIGNMENTS")
    print("-" * 60)

    if assignments:
        for a in assignments:
            print(f"\n  {a.get('course_code', 'N/A')} - {a.get('course_name', 'N/A')}")
            print(f"    Role: {a.get('role', 'Instructor')}")
            print(f"    Term: {a.get('term', 'N/A')} | Year: {a.get('academic_year', 'N/A')}")
            print(f"    Hours/Week: {a.get('hours_per_week', 'N/A')}")
            if a.get('room'):
                print(f"    Room: {a.get('room')}")
    else:
        print("No teaching assignments found.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _view_evaluations(user_id: str) -> None:
    """View teaching evaluations."""
    evaluations = AcademicStaffManager.get_teaching_evaluations(user_id)
    print("\n" + "-" * 60)
    print("TEACHING EVALUATIONS")
    print("-" * 60)

    if evaluations:
        for e in evaluations:
            print(f"\n  {e.get('course_code', 'N/A')} - {e.get('term', 'N/A')}")
            print(f"    Overall Rating: {e.get('overall_rating', 'N/A')}/5")
            print(f"    Response Rate: {e.get('response_rate', 'N/A')}%")
            if e.get('strengths'):
                print(f"    Strengths: {e.get('strengths')[:60]}...")
            if e.get('improvements'):
                print(f"    Areas for Improvement: {e.get('improvements')[:60]}...")
    else:
        print("No evaluations found.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _view_research_profile(user_id: str) -> None:
    """View research profile."""
    profile = AcademicStaffManager.get_research_profile(user_id)
    print("\n" + "-" * 60)
    print("MY RESEARCH PROFILE")
    print("-" * 60)

    if profile:
        print(f"\nResearch Interests: {profile.get('research_interests', 'N/A')}")
        print(f"Research Areas: {profile.get('research_areas', 'N/A')}")
        print("\nMetrics:")
        print(f"  Publications: {profile.get('publication_count', 0)}")
        print(f"  Citations: {profile.get('citation_count', 0)}")
        print(f"  H-Index: {profile.get('h_index', 0)}")
        print(f"  i10-Index: {profile.get('i10_index', 0)}")
        if profile.get('orcid'):
            print(f"\nORCID: {profile.get('orcid')}")
        if profile.get('google_scholar_id'):
            print(f"Google Scholar: {profile.get('google_scholar_id')}")
    else:
        print("No research profile found.")

    print("-" * 60)

    update = input("\nUpdate profile? (y/n): ").strip().lower()
    if update == 'y':
        _update_research_profile(user_id)
    else:
        input("Press Enter to continue...")


def _update_research_profile(user_id: str) -> None:
    """Update research profile."""
    print("\n--- Update Research Profile ---")
    interests = input("Research Interests:\n").strip()
    areas = input("Research Areas (comma-separated): ").strip()
    orcid = input("ORCID ID: ").strip()

    updates = {}
    if interests:
        updates['research_interests'] = interests
    if areas:
        updates['research_areas'] = areas
    if orcid:
        updates['orcid'] = orcid

    if updates:
        AcademicStaffManager.update_research_profile(user_id, **updates)
        print("\nProfile updated.")
    else:
        print("\nNo changes made.")

    input("Press Enter to continue...")


def _manage_publications(user_id: str) -> None:
    """Manage publications."""
    publications = AcademicStaffManager.get_publications(user_id)
    print("\n" + "-" * 60)
    print("MY PUBLICATIONS")
    print("-" * 60)

    if publications:
        for p in publications:
            pub_type = p.get('publication_type', 'article').upper()
            print(f"\n  [{pub_type}] {p.get('title', 'N/A')}")
            print(f"    Authors: {p.get('authors', 'N/A')}")
            print(f"    {p.get('journal_name') or p.get('venue', 'N/A')} ({p.get('year', 'N/A')})")
            if p.get('citations'):
                print(f"    Citations: {p.get('citations')}")
            if p.get('doi'):
                print(f"    DOI: {p.get('doi')}")
    else:
        print("No publications found.")

    print("-" * 60)

    add = input("\nAdd publication? (y/n): ").strip().lower()
    if add == 'y':
        _add_publication(user_id)
    else:
        input("Press Enter to continue...")


def _add_publication(user_id: str) -> None:
    """Add a publication."""
    print("\n--- Add Publication ---")
    print("Types: journal_article, conference_paper, book_chapter, book, thesis, report")
    pub_type = input("Publication Type: ").strip() or 'journal_article'
    title = input("Title: ").strip()
    authors = input("Authors (comma-separated): ").strip()
    journal = input("Journal/Venue: ").strip()
    year = input("Year: ").strip()
    doi = input("DOI: ").strip()

    if title:
        try:
            pub_id = AcademicStaffManager.add_publication(
                user_id, title,
                publication_type=pub_type,
                authors=authors,
                journal_name=journal,
                year=int(year) if year else None,
                doi=doi if doi else None
            )
            print(f"\nPublication added. ID: {pub_id}")
        except Exception as e:
            print(f"\nError: {e}")
    else:
        print("\nTitle is required.")

    input("Press Enter to continue...")


def _view_grants(user_id: str) -> None:
    """View research grants."""
    grants = AcademicStaffManager.get_grants(user_id)
    print("\n" + "-" * 60)
    print("RESEARCH GRANTS")
    print("-" * 60)

    if grants:
        for g in grants:
            status = g.get('status', 'active').upper()
            print(f"\n  [{status}] {g.get('title', 'N/A')}")
            print(f"    Funder: {g.get('funding_body', 'N/A')}")
            print(f"    Amount: £{g.get('amount', 0):,.2f}")
            print(f"    Period: {g.get('start_date', 'N/A')} to {g.get('end_date', 'N/A')}")
            print(f"    Role: {g.get('role', 'PI')}")
    else:
        print("No grants found.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _view_supervisions(user_id: str) -> None:
    """View supervisions."""
    supervisions = AcademicStaffManager.get_supervisions(user_id)
    print("\n" + "-" * 60)
    print("MY SUPERVISIONS")
    print("-" * 60)

    if supervisions:
        # Group by type
        phd = [s for s in supervisions if s.get('supervision_type') == 'phd']
        masters = [s for s in supervisions if s.get('supervision_type') == 'masters']
        other = [s for s in supervisions if s.get('supervision_type') not in ('phd', 'masters')]

        if phd:
            print("\n[PhD Students]")
            for s in phd:
                status = s.get('status', 'active')
                print(f"  - {s.get('student_name', 'N/A')} ({status})")
                print(f"    Topic: {s.get('thesis_title', 'N/A')[:50]}...")
                print(f"    Role: {s.get('role', 'Principal Supervisor')}")

        if masters:
            print("\n[Masters Students]")
            for s in masters:
                status = s.get('status', 'active')
                print(f"  - {s.get('student_name', 'N/A')} ({status})")
                print(f"    Topic: {s.get('thesis_title', 'N/A')[:50]}...")

        if other:
            print("\n[Other Supervisions]")
            for s in other:
                print(f"  - {s.get('student_name', 'N/A')} - {s.get('supervision_type')}")
    else:
        print("No active supervisions.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _supervision_requests(user_id: str) -> None:
    """Handle supervision requests."""
    requests = AcademicStaffManager.get_supervision_requests(user_id)
    print("\n" + "-" * 60)
    print("SUPERVISION REQUESTS")
    print("-" * 60)

    if not requests:
        print("No pending supervision requests.")
        input("\nPress Enter to continue...")
        return

    for i, r in enumerate(requests, 1):
        print(f"\n  {i}. {r.get('student_name', 'N/A')}")
        print(f"     Program: {r.get('program', 'N/A')}")
        print(f"     Topic: {r.get('proposed_topic', 'N/A')[:60]}...")
        print(f"     Requested: {r.get('request_date', 'N/A')[:10]}")

    print("-" * 60)

    try:
        choice = int(input("\nSelect request to respond (0 to abort): ").strip())
        if choice == 0:
            return
        if 1 <= choice <= len(requests):
            request = requests[choice - 1]
            action = input("(A)ccept or (D)ecline? ").strip().upper()

            if action == 'A':
                AcademicStaffManager.accept_supervision(request['request_id'], user_id)
                print("\nSupervision accepted.")
            elif action == 'D':
                reason = input("Reason for declining: ").strip()
                AcademicStaffManager.decline_supervision(request['request_id'], reason)
                print("\nRequest declined.")
    except ValueError:
        print("\nInvalid input.")

    input("Press Enter to continue...")


def _peer_observations(user_id: str) -> None:
    """View and manage peer observations."""
    observations = AcademicStaffManager.get_peer_observations(user_id)
    print("\n" + "-" * 60)
    print("PEER OBSERVATIONS")
    print("-" * 60)

    received = [o for o in observations if o.get('observed_id') == user_id]
    given = [o for o in observations if o.get('observer_id') == user_id]

    if received:
        print("\n[Observations Received]")
        for o in received:
            print(f"  - {o.get('observation_date', 'N/A')}: {o.get('course_code', 'N/A')}")
            print(f"    Observer: {o.get('observer_name', 'N/A')}")
            if o.get('overall_rating'):
                print(f"    Rating: {o.get('overall_rating')}/5")
            if o.get('feedback'):
                print(f"    Feedback: {o.get('feedback')[:60]}...")

    if given:
        print("\n[Observations Given]")
        for o in given:
            print(f"  - {o.get('observation_date', 'N/A')}: {o.get('observed_name', 'N/A')}")
            print(f"    Course: {o.get('course_code', 'N/A')}")

    if not observations:
        print("No peer observations found.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _external_examiner(user_id: str) -> None:
    """View external examiner duties."""
    duties = AcademicStaffManager.get_external_examiner_duties(user_id)
    print("\n" + "-" * 60)
    print("EXTERNAL EXAMINER DUTIES")
    print("-" * 60)

    if duties:
        for d in duties:
            status = d.get('status', 'active').upper()
            print(f"\n  [{status}] {d.get('institution', 'N/A')}")
            print(f"    Program: {d.get('program_name', 'N/A')}")
            print(f"    Period: {d.get('start_date', 'N/A')} to {d.get('end_date', 'N/A')}")
            print(f"    Role: {d.get('role', 'External Examiner')}")
    else:
        print("No external examiner duties found.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _manage_teaching_loads() -> None:
    """Admin: Manage teaching loads."""
    print("\n--- Teaching Load Overview ---")
    loads = AcademicStaffManager.get_teaching_load_summary()

    if loads:
        print("\nStaff Teaching Hours:")
        for l in loads:
            name = f"{l.get('first_name', '')} {l.get('last_name', '')}"
            print(f"  {name.strip()}: {l.get('total_hours', 0)} hrs")
            print(f"    Courses: {l.get('course_count', 0)} | Status: {l.get('load_status', 'N/A')}")
    else:
        print("No teaching load data.")

    input("\nPress Enter to continue...")


def _supervision_overview() -> None:
    """Admin: Supervision overview."""
    print("\n--- Supervision Overview ---")
    summary = AcademicStaffManager.get_supervision_summary()

    if summary:
        print("\nSupervision Statistics:")
        print(f"  Total PhD Students: {summary.get('phd_count', 0)}")
        print(f"  Total Masters Students: {summary.get('masters_count', 0)}")
        print(f"  Supervisors at Capacity: {summary.get('at_capacity', 0)}")
        print(f"  Available Supervisors: {summary.get('available', 0)}")

        if summary.get('by_department'):
            print("\nBy Department:")
            for dept, count in summary['by_department'].items():
                print(f"  {dept}: {count}")
    else:
        print("No supervision data.")

    input("\nPress Enter to continue...")
