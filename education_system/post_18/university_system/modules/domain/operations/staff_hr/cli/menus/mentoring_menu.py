"""
Mentoring Menu - Mentoring relationships, sessions and goals CLI.

Wired to MentoringManager (the same manager the mentoring GUI uses).
"""

from datetime import datetime

from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.mentoring_manager import (
    MentoringManager,
)


def display_mentoring_menu(user_id: str, is_admin: bool = False) -> None:
    """Display the mentoring programme menu."""
    while True:
        print("\n" + "=" * 60)
        print("MENTORING PROGRAMME")
        print("=" * 60)

        print("\n  1. My Mentoring Relationships")
        print("  2. Browse Programmes")
        print("  3. Find Mentors")
        print("  4. Register as Mentor")
        print("  5. View Sessions")
        print("  6. Log Session")
        print("  7. Complete Session")
        print("  8. View Goals")
        print("  9. Add Goal")
        print("  10. Update Goal Progress")
        print("  11. Complete Goal")

        if is_admin:
            print("\n--- Administration ---")
            print("  12. Create Programme")
            print("  13. Create & Activate Match")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _my_matches(user_id)
        elif choice == '2':
            _browse_programmes()
        elif choice == '3':
            _find_mentors()
        elif choice == '4':
            _register_mentor(user_id)
        elif choice == '5':
            _view_sessions(user_id)
        elif choice == '6':
            _log_session(user_id)
        elif choice == '7':
            _complete_session(user_id)
        elif choice == '8':
            _view_goals(user_id)
        elif choice == '9':
            _add_goal(user_id)
        elif choice == '10':
            _update_goal(user_id)
        elif choice == '11':
            _complete_goal(user_id)
        elif choice == '12' and is_admin:
            _create_programme(user_id)
        elif choice == '13' and is_admin:
            _create_match(user_id)
        else:
            print("Invalid choice.")


def _programme_name(programme_id) -> str:
    """Resolve a programme name from its id."""
    try:
        prog = MentoringManager.get_programme(programme_id)
        return prog.get('name', str(programme_id)) if prog else str(programme_id)
    except Exception:
        return str(programme_id)


def _pick_match(user_id: str):
    """Prompt the user to select one of their mentoring matches. Returns match_id or None."""
    matches = MentoringManager.get_user_matches(user_id)
    if not matches:
        print("\nNo mentoring matches found.")
        return None

    print("\nYour matches:")
    for i, m in enumerate(matches, 1):
        match_id = m.get('match_id') or m.get('id')
        prog = _programme_name(m.get('programme_id'))
        print(f"  {i}. #{match_id}  {prog}  [{m.get('status', '')}]")

    try:
        idx = int(input("\nSelect match (0 to abort): ").strip())
        if 1 <= idx <= len(matches):
            m = matches[idx - 1]
            return m.get('match_id') or m.get('id')
    except ValueError:
        pass
    return None


def _my_matches(user_id: str) -> None:
    """List the user's mentoring relationships."""
    matches = MentoringManager.get_user_matches(user_id)
    print("\n" + "-" * 60)
    print("MY MENTORING RELATIONSHIPS")
    print("-" * 60)

    if matches:
        for m in matches:
            match_id = m.get('match_id') or m.get('id')
            role = 'Mentee' if str(m.get('mentee_user_id') or m.get('mentee_id')) == str(user_id) else 'Mentor'
            print(f"\n  #{match_id}  {_programme_name(m.get('programme_id'))}")
            print(f"    Role: {role}  |  Status: {m.get('status', '').replace('_', ' ').title()}  |  "
                  f"Start: {m.get('start_date', '') or 'N/A'}")
    else:
        print("\n  No mentoring relationships.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _browse_programmes() -> None:
    """List mentoring programmes."""
    programmes = MentoringManager.get_programmes()
    print("\n" + "-" * 60)
    print("MENTORING PROGRAMMES")
    print("-" * 60)

    if programmes:
        for p in programmes:
            pid = p.get('programme_id') or p.get('id')
            print(f"\n  #{pid}  {p.get('name', '')}  ({p.get('programme_type', '')})")
            print(f"    Dept: {p.get('department', 'N/A')}  |  Status: {p.get('status', '').title()}")
    else:
        print("\n  No programmes found.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _find_mentors() -> None:
    """List available mentors."""
    mentors = MentoringManager.get_mentors()
    print("\n" + "-" * 60)
    print("AVAILABLE MENTORS")
    print("-" * 60)

    if mentors:
        for m in mentors:
            mid = m.get('mentor_id') or m.get('id')
            current = m.get('current_mentees', 0) or 0
            max_m = m.get('max_mentees', 0) or 0
            print(f"\n  #{mid}  {m.get('user_id', '')}  ({_programme_name(m.get('programme_id'))})")
            print(f"    Slots: {current}/{max_m}  |  Availability: "
                  f"{(m.get('availability') or '').replace('_', ' ').title()}")
            if m.get('expertise_areas') or m.get('expertise'):
                print(f"    Expertise: {m.get('expertise_areas', m.get('expertise', ''))}")
    else:
        print("\n  No mentors found.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _register_mentor(user_id: str) -> None:
    """Register the current user as a mentor on a programme."""
    programmes = MentoringManager.get_programmes()
    if not programmes:
        print("\nNo programmes available to register with.")
        input("Press Enter to continue...")
        return

    print("\nProgrammes:")
    for i, p in enumerate(programmes, 1):
        pid = p.get('programme_id') or p.get('id')
        print(f"  {i}. #{pid}  {p.get('name', '')}")

    try:
        idx = int(input("\nSelect programme (0 to abort): ").strip())
        if idx == 0 or not (1 <= idx <= len(programmes)):
            return
        programme = programmes[idx - 1]
        programme_id = programme.get('programme_id') or programme.get('id')

        expertise = input("Expertise areas: ").strip()
        if not expertise:
            print("\nExpertise is required.")
            input("Press Enter to continue...")
            return
        max_mentees = int(input("Max mentees [3]: ").strip() or '3')
        bio = input("Bio (optional): ").strip()

        mentor_id = MentoringManager.register_mentor(
            user_id=user_id, programme_id=programme_id,
            expertise_areas=expertise, max_mentees=max_mentees, bio=bio,
        )
        print(f"\nRegistered as mentor. ID: {mentor_id}")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _view_sessions(user_id: str) -> None:
    """List sessions for a selected match."""
    match_id = _pick_match(user_id)
    if not match_id:
        input("\nPress Enter to continue...")
        return

    sessions = MentoringManager.get_sessions(match_id)
    print("\n" + "-" * 60)
    print(f"SESSIONS - Match #{match_id}")
    print("-" * 60)

    if sessions:
        for s in sessions:
            sid = s.get('session_id') or s.get('id')
            print(f"\n  #{sid}  {s.get('session_date', '')}  "
                  f"({(s.get('session_type') or '').replace('_', ' ').title()})")
            print(f"    Duration: {s.get('duration_minutes', 'N/A')} min  |  "
                  f"Status: {s.get('status', '').replace('_', ' ').title()}")
    else:
        print("\n  No sessions.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _log_session(user_id: str) -> None:
    """Log a mentoring session for a selected match."""
    match_id = _pick_match(user_id)
    if not match_id:
        input("\nPress Enter to continue...")
        return

    print("\n--- Log Session ---")
    session_date = input(f"Date (YYYY-MM-DD) [{datetime.now().strftime('%Y-%m-%d')}]: ").strip() \
        or datetime.now().strftime('%Y-%m-%d')

    try:
        duration = int(input("Duration (minutes) [60]: ").strip() or '60')
        session_type = input("Type (one_on_one/group/virtual/workshop) [one_on_one]: ").strip() or 'one_on_one'
        location = input("Location (optional): ").strip()
        virtual_link = input("Virtual link (optional): ").strip()
        topics = input("Topics discussed (optional): ").strip()
        action_items = input("Action items (optional): ").strip()

        session_id = MentoringManager.log_session(
            match_id=match_id, session_date=session_date,
            duration_minutes=duration, session_type=session_type,
            location=location, virtual_link=virtual_link,
            topics_discussed=topics, action_items=action_items,
        )
        print(f"\nSession logged. ID: {session_id}")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _complete_session(user_id: str) -> None:
    """Mark a session as completed."""
    match_id = _pick_match(user_id)
    if not match_id:
        input("\nPress Enter to continue...")
        return

    sessions = MentoringManager.get_sessions(match_id)
    open_sessions = [s for s in sessions if s.get('status', '').lower() != 'completed']
    if not open_sessions:
        print("\nNo open sessions to complete.")
        input("Press Enter to continue...")
        return

    for i, s in enumerate(open_sessions, 1):
        sid = s.get('session_id') or s.get('id')
        print(f"  {i}. #{sid}  {s.get('session_date', '')}  [{s.get('status', '')}]")

    try:
        idx = int(input("\nSelect session (0 to abort): ").strip())
        if 1 <= idx <= len(open_sessions):
            s = open_sessions[idx - 1]
            MentoringManager.complete_session(s.get('session_id') or s.get('id'))
            print("\nSession completed.")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _view_goals(user_id: str) -> None:
    """List goals for a selected match."""
    match_id = _pick_match(user_id)
    if not match_id:
        input("\nPress Enter to continue...")
        return

    goals = MentoringManager.get_goals(match_id)
    print("\n" + "-" * 60)
    print(f"GOALS - Match #{match_id}")
    print("-" * 60)

    if goals:
        for g in goals:
            gid = g.get('goal_id') or g.get('id')
            progress = g.get('progress_pct', g.get('progress', 0)) or 0
            print(f"\n  #{gid}  {g.get('title', '')}")
            print(f"    Progress: {progress}%  |  Status: {g.get('status', '').replace('_', ' ').title()}  |  "
                  f"Target: {g.get('target_date', '') or 'N/A'}")
    else:
        print("\n  No goals.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _add_goal(user_id: str) -> None:
    """Add a goal to a selected match."""
    match_id = _pick_match(user_id)
    if not match_id:
        input("\nPress Enter to continue...")
        return

    print("\n--- Add Goal ---")
    title = input("Title: ").strip()
    if not title:
        print("\nTitle is required.")
        input("Press Enter to continue...")
        return
    description = input("Description: ").strip()
    target_date = input("Target date (YYYY-MM-DD): ").strip()

    try:
        goal_id = MentoringManager.create_goal(
            match_id=match_id, title=title,
            description=description, target_date=target_date,
        )
        print(f"\nGoal created. ID: {goal_id}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _update_goal(user_id: str) -> None:
    """Update progress on a goal."""
    match_id = _pick_match(user_id)
    if not match_id:
        input("\nPress Enter to continue...")
        return

    goals = MentoringManager.get_goals(match_id)
    if not goals:
        print("\nNo goals to update.")
        input("Press Enter to continue...")
        return

    for i, g in enumerate(goals, 1):
        gid = g.get('goal_id') or g.get('id')
        progress = g.get('progress_pct', g.get('progress', 0)) or 0
        print(f"  {i}. #{gid}  {g.get('title', '')} - {progress}%")

    try:
        idx = int(input("\nSelect goal (0 to abort): ").strip())
        if 1 <= idx <= len(goals):
            g = goals[idx - 1]
            progress = int(input("New progress (0-100): ").strip())
            if not 0 <= progress <= 100:
                raise ValueError("Progress must be between 0 and 100")
            MentoringManager.update_goal(g.get('goal_id') or g.get('id'), progress_pct=progress)
            print("\nGoal updated.")
    except ValueError as e:
        print(f"\nInvalid input: {e}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _complete_goal(user_id: str) -> None:
    """Mark a goal as completed."""
    match_id = _pick_match(user_id)
    if not match_id:
        input("\nPress Enter to continue...")
        return

    goals = MentoringManager.get_goals(match_id)
    open_goals = [g for g in goals if g.get('status', '').lower() != 'completed']
    if not open_goals:
        print("\nNo open goals to complete.")
        input("Press Enter to continue...")
        return

    for i, g in enumerate(open_goals, 1):
        gid = g.get('goal_id') or g.get('id')
        print(f"  {i}. #{gid}  {g.get('title', '')}")

    try:
        idx = int(input("\nSelect goal (0 to abort): ").strip())
        if 1 <= idx <= len(open_goals):
            g = open_goals[idx - 1]
            MentoringManager.complete_goal(g.get('goal_id') or g.get('id'))
            print("\nGoal completed.")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _create_programme(user_id: str) -> None:
    """Create a mentoring programme (admin)."""
    print("\n--- Create Programme ---")
    name = input("Name: ").strip()
    if not name:
        print("\nName is required.")
        input("Press Enter to continue...")
        return
    description = input("Description: ").strip()
    programme_type = input("Type (research/teaching/buddy/leadership/general) [general]: ").strip() or 'general'
    department = input("Department: ").strip()

    try:
        duration = int(input("Duration (months) [12]: ").strip() or '12')
        programme_id = MentoringManager.create_programme(
            name=name, description=description, programme_type=programme_type,
            department=department, max_mentees_per_mentor=3,
            duration_months=duration, created_by=user_id,
        )
        print(f"\nProgramme created. ID: {programme_id}")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _create_match(user_id: str) -> None:
    """Create and activate a mentor-mentee match (admin)."""
    programmes = MentoringManager.get_programmes()
    if not programmes:
        print("\nNo programmes available.")
        input("Press Enter to continue...")
        return

    print("\nProgrammes:")
    for i, p in enumerate(programmes, 1):
        pid = p.get('programme_id') or p.get('id')
        print(f"  {i}. #{pid}  {p.get('name', '')}")

    try:
        idx = int(input("\nSelect programme (0 to abort): ").strip())
        if idx == 0 or not (1 <= idx <= len(programmes)):
            return
        programme = programmes[idx - 1]
        programme_id = programme.get('programme_id') or programme.get('id')

        mentors = MentoringManager.get_mentors(programme_id=programme_id)
        if not mentors:
            print("\nNo mentors registered for this programme.")
            input("Press Enter to continue...")
            return

        print("\nMentors:")
        for i, m in enumerate(mentors, 1):
            mid = m.get('mentor_id') or m.get('id')
            print(f"  {i}. #{mid}  {m.get('user_id', '')}")

        midx = int(input("\nSelect mentor (0 to abort): ").strip())
        if midx == 0 or not (1 <= midx <= len(mentors)):
            return
        mentor = mentors[midx - 1]
        mentor_id = mentor.get('mentor_id') or mentor.get('id')

        mentee_user_id = input("Mentee user ID: ").strip()
        if not mentee_user_id:
            print("\nMentee user ID is required.")
            input("Press Enter to continue...")
            return
        match_reason = input("Match reason (optional): ").strip()

        match_id = MentoringManager.create_match(
            programme_id=programme_id, mentor_id=mentor_id,
            mentee_user_id=mentee_user_id, match_reason=match_reason,
            matched_by=user_id,
        )
        try:
            MentoringManager.activate_match(
                match_id=match_id, start_date=datetime.now().strftime('%Y-%m-%d'),
            )
            print(f"\nMatch created and activated. ID: {match_id}")
        except Exception:
            print(f"\nMatch created (activation skipped). ID: {match_id}")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")
