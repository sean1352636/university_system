"""
Curriculum Menu - Curriculum design and programme management CLI.

Wired to CurriculumManager (programmes, module mapping, learning
outcomes, and the programme approval workflow).
"""

from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers import (
    CurriculumManager,
)


def display_curriculum_menu(user_id: str, is_admin: bool = False) -> None:
    """Display the curriculum design menu."""
    while True:
        print("\n" + "=" * 60)
        print("CURRICULUM DESIGN")
        print("=" * 60)

        print("\n  1. List Programmes")
        print("  2. Create Programme")
        print("  3. Update Programme")
        print("  4. View Programme Structure")
        print("  5. Add Module to Programme")
        print("  6. Programme Learning Outcomes")
        print("  7. Create Learning Outcome")
        print("  8. Submit Programme for Approval")

        if is_admin:
            print("\n--- Approvals ---")
            print("  9. Pending Approvals")
            print("  10. Review Programme")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _list_programmes()
        elif choice == '2':
            _create_programme(user_id)
        elif choice == '3':
            _update_programme()
        elif choice == '4':
            _view_structure()
        elif choice == '5':
            _add_module()
        elif choice == '6':
            _list_outcomes()
        elif choice == '7':
            _create_outcome()
        elif choice == '8':
            _submit_for_approval(user_id)
        elif choice == '9' and is_admin:
            _list_pending(user_id)
        elif choice == '10' and is_admin:
            _review_programme(user_id)
        else:
            print("Invalid choice.")


def _prompt_int(label: str, default: int | None = None) -> int | None:
    """Prompt for an integer, returning default on empty input."""
    raw = input(label).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print("Invalid number.")
        return default


def _list_programmes() -> None:
    """List programmes."""
    status = input("Filter by status (blank for all): ").strip() or None
    programmes = CurriculumManager.get_programmes(status=status)
    print("\n" + "-" * 60)
    print("PROGRAMMES")
    print("-" * 60)
    if programmes:
        for p in programmes:
            print(f"  {p.get('programme_id')}. [{p.get('code')}] "
                  f"{p.get('name')} - {p.get('level')} "
                  f"[{p.get('status')}]")
            if p.get('department'):
                print(f"      Dept: {p.get('department')} | "
                      f"Credits: {p.get('total_credits')}")
    else:
        print("  No programmes found.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _create_programme(user_id: str) -> None:
    """Create a programme."""
    print("\n--- Create Programme ---")
    code = input("Programme Code: ").strip()
    name = input("Programme Name: ").strip()
    if not code or not name:
        print("Code and name are required.")
        input("Press Enter to continue...")
        return
    level = input("Level [undergraduate]: ").strip() or 'undergraduate'
    department = input("Department (optional): ").strip() or None
    total_credits = _prompt_int("Total Credits [360]: ", default=360)
    duration_years = _prompt_int("Duration Years [3]: ", default=3)
    description = input("Description (optional): ").strip() or None
    try:
        programme_id = CurriculumManager.create_programme(
            code, name, level=level, department=department,
            total_credits=total_credits, duration_years=duration_years,
            description=description, created_by=user_id)
        print(f"\nProgramme created (draft). ID: {programme_id}")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _update_programme() -> None:
    """Update programme fields."""
    print("\n--- Update Programme ---")
    programme_id = _prompt_int("Programme ID: ")
    if programme_id is None:
        return
    name = input("New Name (blank to skip): ").strip()
    department = input("New Department (blank to skip): ").strip()
    description = input("New Description (blank to skip): ").strip()
    data = {}
    if name:
        data['name'] = name
    if department:
        data['department'] = department
    if description:
        data['description'] = description
    if not data:
        print("Nothing to update.")
        input("Press Enter to continue...")
        return
    try:
        CurriculumManager.update_programme(programme_id, **data)
        print("\nProgramme updated.")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _view_structure() -> None:
    """View a programme's module structure."""
    programme_id = _prompt_int("Programme ID: ")
    if programme_id is None:
        return
    structure = CurriculumManager.get_programme_structure(programme_id)
    print("\n" + "-" * 60)
    print(f"PROGRAMME STRUCTURE - #{programme_id}")
    print("-" * 60)
    years = structure.get('years', {})
    if years:
        for year in sorted(years.keys()):
            print(f"\n  Year {year}:")
            semesters = years[year].get('semesters', {})
            for sem in sorted(semesters.keys()):
                print(f"    Semester {sem}:")
                for m in semesters[sem]:
                    core = 'core' if m.get('is_core') else 'optional'
                    print(f"      - [{m.get('module_code')}] "
                          f"{m.get('module_name') or ''} "
                          f"({m.get('credits')} cr, {core})")
    else:
        print("  No modules mapped.")
    print(f"\n  Total Credits: {structure.get('total_credits', 0)}")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _add_module() -> None:
    """Add a module to a programme."""
    print("\n--- Add Module to Programme ---")
    programme_id = _prompt_int("Programme ID: ")
    if programme_id is None:
        return
    module_code = input("Module Code: ").strip()
    if not module_code:
        print("Module code is required.")
        input("Press Enter to continue...")
        return
    module_name = input("Module Name (optional): ").strip() or None
    year_of_study = _prompt_int("Year of Study [1]: ", default=1)
    semester = _prompt_int("Semester [1]: ", default=1)
    is_core = input("Is Core? (Y/n): ").strip().lower() != 'n'
    credits = _prompt_int("Credits [20]: ", default=20)
    try:
        mapping_id = CurriculumManager.add_module_to_programme(
            programme_id, module_code, module_name=module_name,
            year_of_study=year_of_study, semester=semester,
            is_core=is_core, credits=credits)
        print(f"\nModule added. Mapping ID: {mapping_id}")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _list_outcomes() -> None:
    """List a programme's learning outcomes."""
    programme_id = _prompt_int("Programme ID: ")
    if programme_id is None:
        return
    outcomes = CurriculumManager.get_programme_outcomes(programme_id)
    print("\n" + "-" * 60)
    print(f"LEARNING OUTCOMES - Programme #{programme_id}")
    print("-" * 60)
    if outcomes:
        for o in outcomes:
            print(f"  {o.get('outcome_id')}. [{o.get('code')}] "
                  f"{o.get('description')} ({o.get('bloom_level')})")
    else:
        print("  No outcomes found.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _create_outcome() -> None:
    """Create a programme-level learning outcome."""
    print("\n--- Create Learning Outcome ---")
    programme_id = _prompt_int("Programme ID: ")
    if programme_id is None:
        return
    code = input("Outcome Code: ").strip()
    description = input("Description: ").strip()
    if not code or not description:
        print("Code and description are required.")
        input("Press Enter to continue...")
        return
    bloom_level = input("Bloom Level [understand]: ").strip() or 'understand'
    try:
        outcome_id = CurriculumManager.create_outcome(
            code, description, programme_id=programme_id,
            bloom_level=bloom_level, outcome_type='programme')
        print(f"\nOutcome created. ID: {outcome_id}")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _submit_for_approval(user_id: str) -> None:
    """Submit a programme for approval."""
    programme_id = _prompt_int("Programme ID to submit: ")
    if programme_id is None:
        return
    try:
        CurriculumManager.submit_for_approval(programme_id, submitted_by=user_id)
        print("\nProgramme submitted for approval.")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _list_pending(user_id: str) -> None:
    """List pending programme approvals."""
    pending = CurriculumManager.get_pending_approvals(reviewer_id=user_id)
    print("\n" + "-" * 60)
    print("PENDING PROGRAMME APPROVALS")
    print("-" * 60)
    if pending:
        for p in pending:
            print(f"  Approval {p.get('approval_id')} "
                  f"(level: {p.get('approval_level')}) - "
                  f"[{p.get('programme_code')}] {p.get('programme_name')}")
    else:
        print("  No pending approvals.")
    print("-" * 60)
    input("\nPress Enter to continue...")


def _review_programme(user_id: str) -> None:
    """Review (approve/reject) a programme approval."""
    print("\n--- Review Programme ---")
    approval_id = _prompt_int("Approval ID: ")
    if approval_id is None:
        return
    status = input("Decision (approved/rejected): ").strip().lower()
    if status not in ('approved', 'rejected'):
        print("Decision must be 'approved' or 'rejected'.")
        input("Press Enter to continue...")
        return
    comments = input("Comments (optional): ").strip() or None
    try:
        CurriculumManager.review_programme(
            approval_id, user_id, status, comments=comments)
        print("\nReview recorded.")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")
