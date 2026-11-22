"""
Appraisal Menu - Performance and goals CLI.

Keyed by the signed-in username; reviews are offered to line managers
(their reports) and HR, and PerformanceManager re-checks every action.
"""

from typing import Any

from education_system.systems.university.domains.staff.domain.staff_hr import access
from education_system.systems.university.domains.staff.domain.staff_hr.services import PerformanceManager
from education_system.systems.university.domains.staff.interfaces.cli.staff_hr.menus.profile_menu import (
    session_actor,
)


def display_appraisal_menu(user_id: str, is_manager: bool = False) -> None:
    """Display performance appraisal menu (``is_manager`` is kept for older
    callers; the line-management records decide)."""
    actor = session_actor(user_id)
    user_id = access.username_of(actor)
    if not user_id:
        print("\nPlease sign in to use Performance & Goals.")
        return
    is_manager = access.can(actor, 'manager')
    while True:
        print("\n" + "=" * 60)
        print("PERFORMANCE & GOALS")
        print("=" * 60)

        # Show active cycle
        cycle = PerformanceManager.get_active_cycle()
        if cycle:
            print(f"\nActive Cycle: {cycle.get('name')}")
            print(f"Period: {cycle.get('start_date')} to {cycle.get('end_date')}")

        print("\n  1. View My Appraisal")
        print("  2. Submit Self-Review")
        print("  3. View My Goals")
        print("  4. Add Goal")
        print("  5. Update Goal Progress")

        if is_manager:
            print("\n--- Manager ---")
            print("  6. View Pending Reviews")
            print("  7. Submit Manager Review")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _view_appraisal(user_id, actor)
        elif choice == '2':
            _submit_self_review(user_id, actor)
        elif choice == '3':
            _view_goals(user_id, actor)
        elif choice == '4':
            _add_goal(user_id, actor)
        elif choice == '5':
            _update_goal(user_id, actor)
        elif choice == '6' and is_manager:
            _view_pending_reviews(actor)
        elif choice == '7' and is_manager:
            _submit_manager_review(actor)
        else:
            print("Invalid choice.")


def _view_appraisal(user_id: str, actor: Any = None) -> None:
    """View current appraisal."""
    cycle = PerformanceManager.get_active_cycle()
    if not cycle:
        print("\nNo active appraisal cycle.")
        input("Press Enter to continue...")
        return

    appraisal = PerformanceManager.get_appraisal(user_id, cycle['cycle_id'])
    print("\n" + "-" * 60)
    print(f"MY APPRAISAL - {cycle.get('name')}")
    print("-" * 60)

    if appraisal:
        print(f"\nStatus: {appraisal.get('status', 'pending').upper()}")
        if appraisal.get('self_rating'):
            print(f"Self Rating: {appraisal.get('self_rating')}")
        if appraisal.get('manager_rating'):
            print(f"Manager Rating: {appraisal.get('manager_rating')}")
        if appraisal.get('final_rating'):
            print(f"Final Rating: {appraisal.get('final_rating')}")
        if appraisal.get('strengths'):
            print(f"\nStrengths: {appraisal.get('strengths')}")
        if appraisal.get('areas_for_improvement'):
            print(f"Areas for Improvement: {appraisal.get('areas_for_improvement')}")
    else:
        print("\nNo appraisal record found. Submit self-review to create one.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _submit_self_review(user_id: str, actor: Any = None) -> None:
    """Submit self-review."""
    cycle = PerformanceManager.get_active_cycle()
    if not cycle:
        print("\nNo active appraisal cycle.")
        input("Press Enter to continue...")
        return

    print(f"\n--- Self-Review for {cycle.get('name')} ---")
    print("Rate yourself on a scale of 1-5:")

    try:
        rating = float(input("Self Rating (1-5): ").strip())
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")

        comments = input("Self-Assessment Comments:\n").strip()
        strengths = input("Key Strengths:\n").strip()
        improvements = input("Areas for Improvement:\n").strip()

        PerformanceManager.submit_self_review(
            user_id, cycle['cycle_id'], rating, comments, actor=actor,
            strengths=strengths or None, areas_for_improvement=improvements or None
        )
        print("\nSelf-review submitted successfully.")
    except ValueError as e:
        print(f"\nError: {e}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _view_goals(user_id: str, actor: Any = None) -> None:
    """View goals."""
    goals = PerformanceManager.get_goals(user_id, actor=actor)
    print("\n" + "-" * 60)
    print("MY GOALS")
    print("-" * 60)

    if goals:
        for g in goals:
            progress = int(g.get('progress') or 0)
            status = g.get('status', 'active')
            bar = '█' * (progress // 10) + '░' * (10 - progress // 10)
            print(f"\n  {g.get('title')}")
            print(f"    [{bar}] {progress}%")
            print(f"    Category: {g.get('category')} | Status: {status}")
            if g.get('target_date'):
                print(f"    Target: {g.get('target_date')}")
    else:
        print("No goals found.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _add_goal(user_id: str, actor: Any = None) -> None:
    """Add a new goal."""
    print("\n--- Add Goal ---")
    title = input("Goal Title: ").strip()
    description = input("Description: ").strip()
    category = input("Category (performance/development/project): ").strip() or 'performance'
    target_date = input("Target Date (YYYY-MM-DD): ").strip()

    if title:
        try:
            cycle = PerformanceManager.get_active_cycle()
            goal_id = PerformanceManager.add_goal(
                user_id, title, actor=actor,
                cycle_id=cycle['cycle_id'] if cycle else None,
                description=description,
                category=category,
                target_date=target_date if target_date else None
            )
            print(f"\nGoal added. ID: {goal_id}")
        except Exception as e:
            print(f"\nError: {e}")
    else:
        print("\nGoal title is required.")

    input("Press Enter to continue...")


def _update_goal(user_id: str, actor: Any = None) -> None:
    """Update goal progress."""
    goals = PerformanceManager.get_goals(user_id, actor=actor)
    active_goals = [g for g in goals if g.get('status') == 'active']

    if not active_goals:
        print("\nNo active goals.")
        input("Press Enter to continue...")
        return

    print("\nActive Goals:")
    for i, g in enumerate(active_goals, 1):
        print(f"  {i}. {g.get('title')} - {g.get('progress', 0)}%")

    try:
        choice = int(input("\nSelect goal (0 to abort): ").strip())
        if choice == 0:
            return
        if 1 <= choice <= len(active_goals):
            goal = active_goals[choice - 1]
            progress = int(input("New progress (0-100): ").strip())
            notes = input("Update notes: ").strip()

            PerformanceManager.update_goal_progress(goal['goal_id'], progress, notes, actor=actor)
            print("\nGoal updated.")
    except ValueError:
        print("\nInvalid input.")
    except PermissionError as e:
        print(f"\n{e}")

    input("Press Enter to continue...")


def _pending(actor: Any) -> list:
    """Self-reviews waiting for the signed-in reviewer (their line; HR: all)."""
    return [r for r in PerformanceManager.get_team_reviews(actor) if r.get('status') != 'completed']


def _view_pending_reviews(actor: Any) -> None:
    """View pending manager reviews."""
    pending = _pending(actor)
    print("\n" + "-" * 60)
    print("PENDING MANAGER REVIEWS")
    print("-" * 60)

    if pending:
        for i, p in enumerate(pending, 1):
            print(f"\n  {i}. {access.display_name(p['user_id'])} ({p['user_id']})")
            print(f"     Cycle: {p.get('cycle_name')} | Status: {p.get('status')}")
            print(f"     Self Rating: {p.get('self_rating') or 'N/A'}")
    else:
        print("No pending reviews.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _submit_manager_review(actor: Any) -> None:
    """Submit manager review."""
    pending = _pending(actor)
    if not pending:
        print("\nNo pending reviews.")
        input("Press Enter to continue...")
        return

    print("\nPending Reviews:")
    for i, p in enumerate(pending, 1):
        print(f"  {i}. {p['user_id']} - Self: {p.get('self_rating') or 'N/A'}")

    try:
        choice = int(input("\nSelect employee (0 to abort): ").strip())
        if choice == 0:
            return
        if 1 <= choice <= len(pending):
            employee = pending[choice - 1]

            print(f"\n--- Review for {access.display_name(employee['user_id'])} ---")
            rating = float(input("Manager Rating (1-5): ").strip())
            comments = input("Comments:\n").strip()
            strengths = input("Strengths:\n").strip()
            improvements = input("Areas for Improvement:\n").strip()

            PerformanceManager.manager_review_by_id(
                employee['appraisal_id'], actor, rating, comments,
                strengths=strengths or None,
                areas_for_improvement=improvements or None
            )
            print("\nManager review submitted.")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")
