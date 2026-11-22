"""
AI Study Companion CLI

Provides menu-driven interface for:
- AI-powered study plan generation
- Spaced repetition flashcards
- Concept explanations
- Study analytics
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from education_system.systems.university.domains.student_life.domain.ai_study.services.ai_study_service import AIStudyService
from education_system.systems.university.domains.student_life.domain.study_hub.services import study_context
from education_system.systems.university.infrastructure.activity_logger import log_activity

try:
    from education_system.systems.university.infrastructure.shared_context import get_auth
except ImportError:
    get_auth = lambda: None

logger = logging.getLogger(__name__)

# Global instances
auth = None
ai_study_service = None


def init_ai_study() -> bool:
    """Initialize AI Study Companion database tables."""
    try:
        global ai_study_service
        ai_study_service = AIStudyService()
        logger.info("AI Study Companion initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing AI Study Companion: {e}")
        return False


def set_auth(auth_instance: Any) -> None:
    """Set the global auth instance for the module."""
    global auth
    auth = auth_instance


def display_ai_study_menu() -> None:
    """Display the main AI Study Companion menu."""
    global auth, ai_study_service

    if not auth:
        auth = get_auth()

    if not auth or not getattr(auth, 'current_user', None):
        print("\n" + "=" * 60)
        print("You must be logged in to access AI Study Companion features.")
        print("=" * 60)
        input("Press Enter to continue...")
        return

    if not ai_study_service:
        ai_study_service = AIStudyService()

    current_user = auth.current_user
    # Companion rows key on the student number (or a staff username), not
    # current_user['id'] — the users-table row id.
    user_id = study_context.owner_id(current_user)
    user_role = current_user.get('role', 'student')
    staff = study_context.is_staff(current_user)
    if not staff:
        try:
            ai_study_service.send_my_reminder(user_id)
        except Exception:
            logger.debug("Study reminder failed", exc_info=True)

    while True:
        print("\n" + "=" * 70)
        print("AI STUDY COMPANION")
        print("=" * 70)
        print(f"User: {current_user.get('username', 'Unknown')} | Role: {user_role.capitalize()}")
        print("=" * 70)

        options = []
        option_num = 1

        def add_option(label: str, key: str) -> None:
            nonlocal option_num
            print(f"  {option_num}. {label}")
            options.append(key)
            option_num += 1

        # Study Plan options
        print("\n[STUDY PLANS]")
        add_option("Generate Study Plan", "generate_plan")
        add_option("View My Study Plans", "view_plans")
        add_option("View Plan Tasks", "view_tasks")
        add_option("Complete Study Task", "complete_task")
        add_option("Manage a Plan (edit, pause, archive, delete, reschedule missed)", "manage_plan")
        add_option("Manage Plan Tasks (skip, move, edit, add, delete, undo)", "manage_tasks")

        # Flashcard options
        print("\n[FLASHCARDS]")
        add_option("Create Flashcard", "create_flashcard")
        add_option("View Flashcard Decks", "view_decks")
        add_option("Start Review Session", "review_session")
        add_option("View Due Flashcards", "view_due")
        add_option("Generate Flashcards from Notes", "generate_cards")
        add_option("Manage Cards and Decks", "manage_cards")

        # Concept Explainer options
        print("\n[CONCEPT EXPLAINER]")
        add_option("Explain a Concept", "explain_concept")
        add_option("View Explanation History", "view_history")
        add_option("Rate Explanation", "rate_explanation")

        # Analytics options
        print("\n[ANALYTICS]")
        add_option("View Study Analytics", "analytics")

        print("\n[THIS WEEK & SETTINGS]")
        add_option("Today and the Weeks Ahead", "this_week")
        add_option("Reminder and Sharing Settings", "settings")

        if staff:
            print("\n[STAFF]")
            add_option("Student Overview", "staff_overview")
            add_option("Student Details", "staff_student")
            add_option("Send Reminders Now", "send_reminders")
            add_option("Check Study-Plan Slippage (early warning)", "engagement_scan")

        print(f"\n  {option_num}. Back to Main Menu")
        print("=" * 70)

        choice = input("\nSelect option: ").strip()

        if not choice.isdigit():
            print("Invalid input. Please enter a number.")
            continue

        choice_idx = int(choice) - 1

        if choice_idx == len(options):
            break
        elif 0 <= choice_idx < len(options):
            option_key = options[choice_idx]

            try:
                if option_key == "generate_plan":
                    generate_study_plan_menu(user_id)
                elif option_key == "view_plans":
                    view_study_plans_menu(user_id)
                elif option_key == "view_tasks":
                    view_plan_tasks_menu(user_id)
                elif option_key == "complete_task":
                    complete_task_menu(user_id)
                elif option_key == "create_flashcard":
                    create_flashcard_menu(user_id)
                elif option_key == "view_decks":
                    view_flashcard_decks_menu(user_id)
                elif option_key == "review_session":
                    start_review_session_menu(user_id)
                elif option_key == "view_due":
                    view_due_flashcards_menu(user_id)
                elif option_key == "explain_concept":
                    explain_concept_menu(user_id)
                elif option_key == "view_history":
                    view_explanation_history_menu(user_id)
                elif option_key == "rate_explanation":
                    rate_explanation_menu(user_id)
                elif option_key == "analytics":
                    view_analytics_menu(user_id)
                elif option_key == "manage_plan":
                    manage_plan_menu(user_id)
                elif option_key == "manage_tasks":
                    manage_tasks_menu(user_id)
                elif option_key == "generate_cards":
                    generate_flashcards_menu(user_id)
                elif option_key == "manage_cards":
                    manage_cards_menu(user_id)
                elif option_key == "this_week":
                    this_week_menu(user_id)
                elif option_key == "settings":
                    settings_menu(user_id)
                elif option_key == "staff_overview":
                    staff_overview_menu(current_user)
                elif option_key == "staff_student":
                    staff_student_menu(current_user)
                elif option_key == "send_reminders":
                    send_reminders_menu()
                elif option_key == "engagement_scan":
                    engagement_scan_menu(current_user)
            except Exception as e:
                logger.error(f"Error in AI Study menu: {e}")
                print(f"\nError: {e}")
                input("Press Enter to continue...")
        else:
            print("Invalid option. Please try again.")


# ========== Study Plan Functions ==========

def generate_study_plan_menu(student_id: str) -> None:
    """Generate a personalized study plan."""
    print("\n" + "=" * 60)
    print("GENERATE STUDY PLAN")
    print("=" * 60)

    course_id = _choose_module(student_id)

    suggested = None
    if course_id:
        exam = ai_study_service.exam_for_module(student_id, course_id)
        if exam:
            suggested = exam['date']
            print(f"\nPublished exam: {exam['name']} on {exam['date']} "
                  f"{exam.get('start_time') or ''} {exam.get('room') or ''}".rstrip())

    print("\nEnter exam date (YYYY-MM-DD):")
    exam_date = input(f"Exam date{f' [{suggested}]' if suggested else ''}: ").strip() or (suggested or "")

    if not exam_date:
        print("Exam date is required.")
        input("\nPress Enter to continue...")
        return

    # Validate date format
    try:
        datetime.strptime(exam_date, '%Y-%m-%d')
    except ValueError:
        print("Invalid date format. Please use YYYY-MM-DD.")
        input("\nPress Enter to continue...")
        return

    hours_input = input("Hours per day available for study [2]: ").strip()
    try:
        hours_per_day = float(hours_input) if hours_input else 2
    except ValueError:
        hours_per_day = 2

    try:
        result = ai_study_service.generate_study_plan(
            student_id=student_id,
            course_id=course_id,
            exam_date=exam_date,
            hours_per_day=hours_per_day
        )

        print("\n" + "=" * 60)
        print("STUDY PLAN GENERATED SUCCESSFULLY")
        print("=" * 60)
        print(f"Plan ID: {result['plan_id']}")
        print(f"Days until exam: {result['days_until_exam']}")
        print(f"Total study hours: {result['total_hours']}")
        print(f"Tasks generated: {result['tasks_generated']}")
        for warning in result.get('warnings') or []:
            print(f"  • {warning}")
        print("\nYour personalized study schedule has been created!")
        print("View it using 'View My Study Plans' option.")

        log_activity('create', 'ai_study_plan', user_id=student_id,
                    details={'plan_id': result['plan_id'], 'exam_date': exam_date})

    except Exception as e:
        print(f"\nError generating study plan: {e}")

    input("\nPress Enter to continue...")


def view_study_plans_menu(student_id: str) -> None:
    """View all study plans for a student."""
    print("\n" + "=" * 60)
    print("MY STUDY PLANS")
    print("=" * 60)

    try:
        plans = ai_study_service.get_student_study_plans(student_id)

        if not plans:
            print("\nNo study plans found.")
            print("Create your first plan using 'Generate Study Plan' option!")
            input("\nPress Enter to continue...")
            return

        for i, plan in enumerate(plans, 1):
            print(f"\n{i}. {plan['plan_name']}")
            print(f"   Plan ID: {plan['plan_id']}")
            print(f"   Course: {plan.get('course_id', 'General Study')}")
            print(f"   Start Date: {plan['start_date']}")
            print(f"   Exam Date: {plan['end_date']}")
            print(f"   Total Hours: {plan['total_hours']}")
            print(f"   Difficulty: {plan['difficulty_level']}")
            print(f"   Status: {plan['status']}")

        # Option to view detailed tasks
        view_detail = input("\nEnter plan number to view tasks (or press Enter to go back): ").strip()
        if view_detail.isdigit() and 1 <= int(view_detail) <= len(plans):
            plan_id = plans[int(view_detail) - 1]['plan_id']
            view_plan_details(plan_id)

    except Exception as e:
        print(f"\nError retrieving study plans: {e}")

    input("\nPress Enter to continue...")


def view_plan_tasks_menu(student_id: str) -> None:
    """View tasks for a specific study plan."""
    print("\n" + "=" * 60)
    print("VIEW PLAN TASKS")
    print("=" * 60)

    try:
        plans = ai_study_service.get_student_study_plans(student_id)

        if not plans:
            print("\nNo study plans found.")
            input("\nPress Enter to continue...")
            return

        # List plans
        for i, plan in enumerate(plans, 1):
            print(f"{i}. {plan['plan_name']} - Exam: {plan['end_date']}")

        plan_choice = input("\nSelect plan to view tasks (or press Enter to cancel): ").strip()
        if not plan_choice.isdigit() or not (1 <= int(plan_choice) <= len(plans)):
            return

        plan_id = plans[int(plan_choice) - 1]['plan_id']
        view_plan_details(plan_id)

    except Exception as e:
        print(f"\nError viewing plan tasks: {e}")

    input("\nPress Enter to continue...")


def view_plan_details(plan_id: int) -> None:
    """View detailed tasks for a study plan."""
    print("\n" + "=" * 60)
    print("STUDY PLAN TASKS")
    print("=" * 60)

    try:
        plan_data = ai_study_service.get_study_plan(plan_id)

        if not plan_data:
            print("\nPlan not found.")
            return

        plan = plan_data['plan']
        tasks = plan_data['tasks']

        print(f"\nPlan: {plan['plan_name']}")
        print(f"Exam Date: {plan['end_date']}")
        print(f"Total Tasks: {len(tasks)}")

        # Count completed tasks
        completed = sum(1 for t in tasks if _state(t) == 'done')
        print(f"Completed: {completed}/{len(tasks)}")

        if len(tasks) > 0:
            completion_rate = (completed / len(tasks)) * 100
            print(f"Progress: {completion_rate:.1f}%")

        # Display tasks grouped by status
        print("\n--- PENDING TASKS ---")
        pending_tasks = [t for t in tasks if _state(t) == 'pending']
        if not pending_tasks:
            print("No pending tasks!")
        else:
            for task in pending_tasks:
                print(f"\n  Task ID: {task['task_id']}")
                print(f"  Title: {task['task_title']}")
                missed = " (missed)" if str(task['scheduled_date'])[:10] < datetime.now().strftime('%Y-%m-%d') else ""
                print(f"  Date: {task['scheduled_date']}{missed}")
                print(f"  Duration: {task['duration_minutes']} minutes")
                print(f"  Priority: {task['priority']}")
                if task['task_description']:
                    print(f"  Description: {task['task_description']}")

        print("\n--- COMPLETED TASKS ---")
        completed_tasks = [t for t in tasks if _state(t) == 'done']
        if not completed_tasks:
            print("No completed tasks yet.")
        else:
            for task in completed_tasks:
                print(f"\n  Task: {task['task_title']}")
                print(f"  Completed: {task['completed_at']}")

    except Exception as e:
        print(f"\nError retrieving plan details: {e}")


def complete_task_menu(student_id: str) -> None:
    """Mark a study task as completed."""
    print("\n" + "=" * 60)
    print("COMPLETE STUDY TASK")
    print("=" * 60)

    try:
        plans = ai_study_service.get_student_study_plans(student_id)

        if not plans:
            print("\nNo study plans found.")
            input("\nPress Enter to continue...")
            return

        # Find all pending tasks
        all_pending_tasks = []
        for plan in plans:
            plan_data = ai_study_service.get_study_plan(plan['plan_id'])
            if plan_data:
                pending = [t for t in plan_data['tasks'] if _state(t) == 'pending']
                for task in pending:
                    task['plan_name'] = plan['plan_name']
                all_pending_tasks.extend(pending)

        if not all_pending_tasks:
            print("\nNo pending tasks found. Great job!")
            input("\nPress Enter to continue...")
            return

        print("\nPending Tasks:")
        for i, task in enumerate(all_pending_tasks, 1):
            print(f"\n{i}. {task['task_title']}")
            print(f"   Plan: {task['plan_name']}")
            print(f"   Date: {task['scheduled_date']}")
            print(f"   Duration: {task['duration_minutes']} min")
            print(f"   Priority: {task['priority']}")

        task_choice = input("\nSelect task to complete (or press Enter to cancel): ").strip()
        if not task_choice.isdigit() or not (1 <= int(task_choice) <= len(all_pending_tasks)):
            return

        task = all_pending_tasks[int(task_choice) - 1]

        # Confirm completion
        confirm = input(f"\nMark '{task['task_title']}' as completed? (y/n): ").strip().lower()
        if confirm != 'y':
            return

        ai_study_service.complete_study_task(task['task_id'], student_id=student_id)

        print("\n" + "=" * 60)
        print("TASK COMPLETED!")
        print("=" * 60)
        print("Great job! Keep up the good work!")

        log_activity('update', 'ai_study_task', user_id=student_id,
                    details={'task_id': task['task_id'], 'status': 'completed'})

    except Exception as e:
        print(f"\nError completing task: {e}")

    input("\nPress Enter to continue...")


# ========== Flashcard Functions ==========

def create_flashcard_menu(student_id: str) -> None:
    """Create a new flashcard."""
    print("\n" + "=" * 60)
    print("CREATE FLASHCARD")
    print("=" * 60)

    deck_name = input("Deck name: ").strip()
    if not deck_name:
        print("Deck name is required.")
        input("\nPress Enter to continue...")
        return

    course_id = input("Course ID (optional, press Enter to skip): ").strip() or None

    question = input("Question: ").strip()
    if not question:
        print("Question is required.")
        input("\nPress Enter to continue...")
        return

    answer = input("Answer: ").strip()
    if not answer:
        print("Answer is required.")
        input("\nPress Enter to continue...")
        return

    try:
        flashcard_id = ai_study_service.create_flashcard(
            student_id=student_id,
            course_id=course_id,
            deck_name=deck_name,
            question=question,
            answer=answer
        )

        print("\n" + "=" * 60)
        print("FLASHCARD CREATED SUCCESSFULLY")
        print("=" * 60)
        print(f"Flashcard ID: {flashcard_id}")
        print(f"Deck: {deck_name}")
        print("\nThis flashcard will be available for review tomorrow!")

        log_activity('create', 'ai_study_flashcard', user_id=student_id,
                    details={'flashcard_id': flashcard_id, 'deck': deck_name})

    except Exception as e:
        print(f"\nError creating flashcard: {e}")

    input("\nPress Enter to continue...")


def view_flashcard_decks_menu(student_id: str) -> None:
    """View all flashcard decks with statistics."""
    print("\n" + "=" * 60)
    print("MY FLASHCARD DECKS")
    print("=" * 60)

    try:
        decks = ai_study_service.get_flashcard_decks(student_id)

        if not decks:
            print("\nNo flashcard decks found.")
            print("Create your first flashcard using 'Create Flashcard' option!")
            input("\nPress Enter to continue...")
            return

        print(f"\nTotal Decks: {len(decks)}")

        for i, deck in enumerate(decks, 1):
            accuracy = deck.get('accuracy', 0) or 0
            print(f"\n{i}. {deck['deck_name']}")
            print(f"   Course: {deck.get('course_id', 'N/A')}")
            print(f"   Total Cards: {deck['total_cards']}")
            print(f"   Due for Review: {deck['due_count']}")
            print(f"   Accuracy: {accuracy:.1f}%")

    except Exception as e:
        print(f"\nError retrieving flashcard decks: {e}")

    input("\nPress Enter to continue...")


def view_due_flashcards_menu(student_id: str) -> None:
    """View flashcards due for review."""
    print("\n" + "=" * 60)
    print("DUE FLASHCARDS")
    print("=" * 60)

    deck_name = input("Deck name (optional, press Enter for all decks): ").strip() or None

    try:
        flashcards = ai_study_service.get_due_flashcards(student_id, deck_name)

        if not flashcards:
            print("\nNo flashcards due for review!")
            print("Great job staying on top of your studies!")
            input("\nPress Enter to continue...")
            return

        print(f"\nTotal Due: {len(flashcards)}")

        for i, card in enumerate(flashcards[:10], 1):  # Show first 10
            print(f"\n{i}. Deck: {card['deck_name']}")
            print(f"   Question: {card['question'][:60]}...")
            print(f"   Review Count: {card['review_count']}")
            print(f"   Last Reviewed: {card['last_reviewed'] or 'Never'}")

        if len(flashcards) > 10:
            print(f"\n... and {len(flashcards) - 10} more")

        print("\nUse 'Start Review Session' to review these flashcards!")

    except Exception as e:
        print(f"\nError retrieving due flashcards: {e}")

    input("\nPress Enter to continue...")


def start_review_session_menu(student_id: str) -> None:
    """Start an interactive flashcard review session."""
    print("\n" + "=" * 60)
    print("FLASHCARD REVIEW SESSION")
    print("=" * 60)

    try:
        decks = ai_study_service.get_flashcard_decks(student_id)

        if not decks:
            print("\nNo flashcard decks found.")
            input("\nPress Enter to continue...")
            return

        # List decks
        print("\nAvailable Decks:")
        for i, deck in enumerate(decks, 1):
            print(f"{i}. {deck['deck_name']} - {deck['due_count']} due")

        deck_choice = input("\nSelect deck to review (or press Enter to review all): ").strip()

        deck_name = None
        if deck_choice.isdigit() and 1 <= int(deck_choice) <= len(decks):
            deck_name = decks[int(deck_choice) - 1]['deck_name']

        # Get due flashcards
        flashcards = ai_study_service.get_due_flashcards(student_id, deck_name)

        if not flashcards:
            print("\nNo flashcards due for review in this deck!")
            input("\nPress Enter to continue...")
            return

        print(f"\n{len(flashcards)} flashcards to review. Let's begin!")
        input("Press Enter to start...")

        # Review session
        correct_count = 0
        incorrect_count = 0

        for i, card in enumerate(flashcards, 1):
            print("\n" + "=" * 60)
            print(f"CARD {i} of {len(flashcards)}")
            print("=" * 60)
            print(f"Deck: {card['deck_name']}")
            print(f"\nQuestion:\n{card['question']}")
            print("\n" + "-" * 60)

            input("\nPress Enter to reveal answer...")

            print(f"\nAnswer:\n{card['answer']}")
            print("\n" + "-" * 60)

            while True:
                response = input("\nDid you get it correct? (y/n, or h=hard, e=easy, q to quit): ").strip().lower()

                if response == 'q':
                    print("\nReview session ended early.")
                    break
                elif response in ['y', 'n', 'h', 'e']:
                    grade = {'y': 'good', 'n': 'again', 'h': 'hard', 'e': 'easy'}[response]

                    # Update flashcard (SM-2)
                    result = ai_study_service.review_flashcard(card['flashcard_id'], quality=grade,
                                                               student_id=student_id)

                    if result['correct']:
                        correct_count += 1
                        print(f"\nCorrect! Next review in {result['days_until_next']} days.")
                    else:
                        incorrect_count += 1
                        print("\nMarked for review. You'll see this again tomorrow.")
                        follow = input("Make a follow-up card from this mistake? "
                                       "Type what you answered, '-' for a reversed card, "
                                       "or Enter to skip: ").strip()
                        if follow:
                            try:
                                ai_study_service.card_from_mistake(
                                    card['flashcard_id'], None if follow == '-' else follow,
                                    student_id)
                                print("Follow-up card added to this deck.")
                            except Exception as e:
                                print(f"Could not make the card: {e}")

                    break
                else:
                    print("Invalid input. Please enter 'y', 'n', 'h', 'e' or 'q'.")

            if response == 'q':
                break

        # Session summary
        print("\n" + "=" * 60)
        print("REVIEW SESSION COMPLETE")
        print("=" * 60)
        print(f"Cards Reviewed: {correct_count + incorrect_count}")
        print(f"Correct: {correct_count}")
        print(f"Incorrect: {incorrect_count}")

        if correct_count + incorrect_count > 0:
            accuracy = (correct_count / (correct_count + incorrect_count)) * 100
            print(f"Accuracy: {accuracy:.1f}%")

        print("\nGreat work! Consistent review is key to retention!")

        log_activity('update', 'ai_study_review_session', user_id=student_id,
                    details={'cards_reviewed': correct_count + incorrect_count,
                            'correct': correct_count})

    except Exception as e:
        print(f"\nError during review session: {e}")

    input("\nPress Enter to continue...")


# ========== Concept Explainer Functions ==========

def explain_concept_menu(student_id: str) -> None:
    """Get AI explanation for a difficult concept."""
    print("\n" + "=" * 60)
    print("CONCEPT EXPLAINER")
    print("=" * 60)

    concept_name = input("Concept name: ").strip()
    if not concept_name:
        print("Concept name is required.")
        input("\nPress Enter to continue...")
        return

    course_id = _choose_module(student_id)

    print("\nDifficulty Level:")
    print("1. Beginner - Simple explanation with examples")
    print("2. Intermediate - Detailed explanation with applications")
    print("3. Advanced - Technical analysis with research context")

    level_choice = input("\nSelect difficulty level [1]: ").strip()
    level_map = {
        '1': 'Beginner',
        '2': 'Intermediate',
        '3': 'Advanced'
    }
    difficulty_level = level_map.get(level_choice, 'Beginner')

    try:
        result = ai_study_service.explain_concept(
            student_id=student_id,
            course_id=course_id,
            concept_name=concept_name,
            difficulty_level=difficulty_level
        )

        print("\n" + "=" * 60)
        print(f"EXPLANATION: {concept_name}")
        print("=" * 60)
        print(f"Difficulty Level: {difficulty_level}")
        print(f"Explanation ID: {result['explanation_id']}")
        print({"claude": "Written by Claude (AI) — check it against your course materials.",
               "course_materials": "From your module records and your own cards (AI is not configured)."}
              .get(result.get('source'), ""))
        print("\n" + "-" * 60)
        print(result['explanation'])
        print("-" * 60)

        # Rate the explanation
        rate = input("\nWas this explanation helpful? Rate it (1-5 stars, or press Enter to skip): ").strip()
        if rate.isdigit() and 1 <= int(rate) <= 5:
            ai_study_service.rate_explanation(result['explanation_id'], int(rate),
                                              student_id=student_id)
            print("\nThank you for your feedback!")

        # Option to create flashcards from explanation
        create_fc = input("\nMake flashcards from this explanation? (y/n): ").strip().lower()
        if create_fc == 'y':
            deck_name = input(f"Deck name [{concept_name}]: ").strip() or concept_name
            made = ai_study_service.flashcards_from_explanation(
                result['explanation_id'], deck_name, student_id=student_id)
            if made['created']:
                print(f"\n{len(made['created'])} flashcard(s) added to '{deck_name}'.")
            else:
                print("\nNo flashcards could be made from this explanation.")

        log_activity('create', 'ai_study_explanation', user_id=student_id,
                    details={'explanation_id': result['explanation_id'], 'concept': concept_name})

    except Exception as e:
        print(f"\nError explaining concept: {e}")

    input("\nPress Enter to continue...")


def view_explanation_history_menu(student_id: str) -> None:
    """View history of concept explanations."""
    print("\n" + "=" * 60)
    print("EXPLANATION HISTORY")
    print("=" * 60)

    try:
        explanations = ai_study_service.get_explanation_history(student_id)

        if not explanations:
            print("\nNo explanation history found.")
            print("Use 'Explain a Concept' to get AI-powered explanations!")
            input("\nPress Enter to continue...")
            return

        print(f"\nTotal Explanations: {len(explanations)}")

        for i, exp in enumerate(explanations[:20], 1):  # Show first 20
            rating_stars = "★" * exp['helpful_rating'] + "☆" * (5 - exp['helpful_rating']) if exp['helpful_rating'] > 0 else "Not rated"

            print(f"\n{i}. {exp['concept_name']}")
            print(f"   Level: {exp['difficulty_level']}")
            print(f"   Course: {exp.get('course_id', 'N/A')}")
            print(f"   Rating: {rating_stars}")
            print(f"   Date: {exp['created_at']}")

        # Option to view full explanation
        view_detail = input("\nEnter number to view full explanation (or press Enter to go back): ").strip()
        if view_detail.isdigit() and 1 <= int(view_detail) <= len(explanations[:20]):
            exp = explanations[int(view_detail) - 1]
            print("\n" + "=" * 60)
            print(f"CONCEPT: {exp['concept_name']}")
            print("=" * 60)
            print(exp['explanation'])
            print("=" * 60)

    except Exception as e:
        print(f"\nError retrieving explanation history: {e}")

    input("\nPress Enter to continue...")


def rate_explanation_menu(student_id: str) -> None:
    """Rate a previous explanation."""
    print("\n" + "=" * 60)
    print("RATE EXPLANATION")
    print("=" * 60)

    try:
        explanations = ai_study_service.get_explanation_history(student_id)

        if not explanations:
            print("\nNo explanations to rate.")
            input("\nPress Enter to continue...")
            return

        # Show recent explanations
        print("\nRecent Explanations:")
        for i, exp in enumerate(explanations[:10], 1):
            current_rating = "★" * exp['helpful_rating'] + "☆" * (5 - exp['helpful_rating']) if exp['helpful_rating'] > 0 else "Not rated"
            print(f"{i}. {exp['concept_name']} - {current_rating}")

        exp_choice = input("\nSelect explanation to rate (or press Enter to cancel): ").strip()
        if not exp_choice.isdigit() or not (1 <= int(exp_choice) <= len(explanations[:10])):
            return

        explanation = explanations[int(exp_choice) - 1]

        print(f"\nConcept: {explanation['concept_name']}")
        print(f"Current rating: {explanation['helpful_rating']}/5")

        rating = input("\nNew rating (1-5 stars): ").strip()
        if not rating.isdigit() or not (1 <= int(rating) <= 5):
            print("Invalid rating. Must be 1-5.")
            input("\nPress Enter to continue...")
            return

        ai_study_service.rate_explanation(explanation['explanation_id'], int(rating),
                                          student_id=student_id)

        print("\n" + "=" * 60)
        print("RATING SAVED")
        print("=" * 60)
        print("Thank you for your feedback!")

        log_activity('update', 'ai_study_explanation_rating', user_id=student_id,
                    details={'explanation_id': explanation['explanation_id'], 'rating': int(rating)})

    except Exception as e:
        print(f"\nError rating explanation: {e}")

    input("\nPress Enter to continue...")


# ========== Analytics Functions ==========

def view_analytics_menu(student_id: str) -> None:
    """View comprehensive study analytics."""
    print("\n" + "=" * 60)
    print("STUDY ANALYTICS")
    print("=" * 60)

    try:
        analytics = ai_study_service.get_study_analytics(student_id)

        # Study Plans section
        print("\n" + "=" * 60)
        print("STUDY PLANS")
        print("=" * 60)

        plans = analytics.get('study_plans', {})
        print(f"Total Plans Created: {plans.get('total_plans', 0)}")
        print(f"Active Plans: {plans.get('active_plans', 0)}")
        print(f"Total Hours Planned: {plans.get('planned_hours', 0)}")

        # Tasks section
        print("\n" + "=" * 60)
        print("STUDY TASKS")
        print("=" * 60)

        tasks = analytics.get('tasks', {})
        total_tasks = tasks.get('total_tasks', 0) or 0
        completed_tasks = tasks.get('completed_tasks', 0) or 0

        print(f"Total Tasks: {total_tasks}")
        print(f"Completed Tasks: {completed_tasks}")
        print(f"Pending Tasks: {total_tasks - (completed_tasks or 0) - (tasks.get('skipped_tasks') or 0)}")

        if total_tasks > 0:
            completion_rate = (completed_tasks / total_tasks) * 100
            print(f"Completion Rate: {completion_rate:.1f}%")

            # Progress bar
            bar_length = 20
            filled = int(bar_length * completion_rate / 100)
            bar = "█" * filled + "░" * (bar_length - filled)
            print(f"Progress: [{bar}] {completion_rate:.1f}%")

        total_minutes = tasks.get('completed_minutes', 0) or 0
        print(f"Total Study Time: {total_minutes} minutes ({total_minutes // 60} hours {total_minutes % 60} min)")
        print(f"Missed (not yet done): {tasks.get('overdue_tasks', 0) or 0}   Skipped: {tasks.get('skipped_tasks', 0) or 0}")
        print(f"Study streak: {analytics.get('streak_days', 0)} day(s)")

        # Flashcards section
        print("\n" + "=" * 60)
        print("FLASHCARDS")
        print("=" * 60)

        cards = analytics.get('flashcards', {})
        print(f"Total Cards: {cards.get('total_cards', 0)}")
        print(f"Total Decks: {cards.get('total_decks', 0)}")

        avg_accuracy = cards.get('avg_accuracy', 0) or 0
        print(f"Average Accuracy: {avg_accuracy:.1f}%")
        reviews = analytics.get('reviews', {}) or {}
        retention = reviews.get('retention_pct')
        print(f"Reviews in the last 30 days: {reviews.get('last_30_days', 0)}"
              + (f" (recalled {retention:.0f}%)" if retention is not None else ""))
        for weak in analytics.get('weak_modules') or []:
            print(f"• Give {weak['module_code']} more time: {'; '.join(weak['reasons'])}")

        if avg_accuracy > 0:
            if avg_accuracy >= 90:
                print("Performance: Excellent! Keep it up!")
            elif avg_accuracy >= 75:
                print("Performance: Good! You're learning well.")
            elif avg_accuracy >= 60:
                print("Performance: Fair. Keep practicing!")
            else:
                print("Performance: Needs improvement. Review more frequently.")

        # Overall insights
        print("\n" + "=" * 60)
        print("INSIGHTS & RECOMMENDATIONS")
        print("=" * 60)

        if total_tasks > 0 and completed_tasks / total_tasks < 0.5:
            print("• Consider completing more study tasks to stay on track")

        if cards.get('total_cards', 0) > 0:
            # Get due flashcards count
            due_cards = ai_study_service.get_due_flashcards(student_id)
            if len(due_cards) > 0:
                print(f"• You have {len(due_cards)} flashcards due for review")

        if plans.get('active_plans', 0) == 0:
            print("• Create a study plan for your upcoming exams")

        if cards.get('total_decks', 0) == 0:
            print("• Start creating flashcards to improve retention")

    except Exception as e:
        print(f"\nError retrieving analytics: {e}")

    input("\nPress Enter to continue...")


# ========== Helpers ==========

def _state(task: dict) -> str:
    """pending / done / skipped (older rows only have ``completed``)."""
    return task.get('status') or ('done' if task.get('completed') else 'pending')


def _pick(items: list, label) -> Optional[Any]:
    """Number-pick one of ``items`` (``label(item)`` prints it), or ``None``."""
    for i, item in enumerate(items, 1):
        print(f"  {i}. {label(item)}")
    choice = input("\nSelect (or press Enter to cancel): ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(items):
        return items[int(choice) - 1]
    return None


def _choose_module(student_id: str) -> Optional[str]:
    """Pick one of the student's modules, type a code, or none."""
    try:
        modules = ai_study_service.available_modules(student_id)
    except Exception:
        modules = []
    if modules:
        print("\nYour modules:")
        for i, m in enumerate(modules, 1):
            print(f"  {i}. {m['module_code']} - {m['module_name']}")
        choice = input("Module number or code (press Enter for none): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(modules):
            return modules[int(choice) - 1]['module_code']
        return choice or None
    return input("Module code (optional, press Enter to skip): ").strip() or None


def _pick_plan(student_id: str) -> Optional[dict]:
    plans = ai_study_service.get_student_study_plans(student_id)
    if not plans:
        print("\nNo study plans found.")
        return None
    return _pick(plans, lambda p: f"{p['plan_name']} — exam {p['end_date']} — {p.get('status') or 'Active'} "
                                  f"({p.get('done_count') or 0}/{p.get('task_count') or 0} done)")


def _pick_deck(student_id: str) -> Optional[str]:
    decks = ai_study_service.get_flashcard_decks(student_id)
    if not decks:
        print("\nNo flashcard decks found.")
        return None
    deck = _pick(decks, lambda d: f"{d['deck_name']} — {d['total_cards']} cards, {d['due_count']} due")
    return deck['deck_name'] if deck else None


# ========== Plan and Task Management ==========

def manage_plan_menu(student_id: str) -> None:
    """Edit, pause, archive, delete or catch up a study plan."""
    print("\n" + "=" * 60)
    print("MANAGE A STUDY PLAN")
    print("=" * 60)
    try:
        plan = _pick_plan(student_id)
        if not plan:
            input("\nPress Enter to continue...")
            return
        pid = plan['plan_id']
        print("\n  1. Rename\n  2. Change exam date\n  3. Edit notes\n  4. Reschedule missed tasks"
              "\n  5. Pause / resume\n  6. Mark completed\n  7. Archive\n  8. Delete")
        action = input("\nAction: ").strip()
        if action == '1':
            name = input(f"New name [{plan['plan_name']}]: ").strip()
            if name:
                ai_study_service.update_plan(pid, student_id, plan_name=name)
                print("Renamed.")
        elif action == '2':
            new = input(f"New exam date (YYYY-MM-DD) [{plan['end_date']}]: ").strip()
            if new:
                result = ai_study_service.update_plan(pid, student_id, exam_date=new)
                print(f"Exam date changed. {result['tasks_skipped']} task(s) after it were skipped.")
        elif action == '3':
            notes = input("Notes: ").strip()
            ai_study_service.update_plan(pid, student_id, notes=notes)
            print("Notes saved.")
        elif action == '4':
            result = ai_study_service.reschedule_missed(pid, student_id)
            print(f"Moved {result['moved']} missed task(s); {result['skipped']} could not fit.")
        elif action == '5':
            status = 'Active' if (plan.get('status') or 'Active') == 'Paused' else 'Paused'
            ai_study_service.set_plan_status(pid, status, student_id)
            print(f"Plan is now {status}.")
        elif action == '6':
            ai_study_service.set_plan_status(pid, 'Completed', student_id)
            print("Plan marked completed.")
        elif action == '7':
            ai_study_service.set_plan_status(pid, 'Archived', student_id)
            print("Plan archived.")
        elif action == '8':
            if input("Delete this plan and all its tasks? (y/n): ").strip().lower() == 'y':
                ai_study_service.delete_plan(pid, student_id)
                print("Plan deleted. Study time already logged is kept.")
    except Exception as e:
        print(f"\nError: {e}")
    input("\nPress Enter to continue...")


def manage_tasks_menu(student_id: str) -> None:
    """Skip, move, edit, add, delete or un-complete plan tasks."""
    print("\n" + "=" * 60)
    print("MANAGE PLAN TASKS")
    print("=" * 60)
    try:
        plan = _pick_plan(student_id)
        if not plan:
            input("\nPress Enter to continue...")
            return
        pid = plan['plan_id']
        while True:
            data = ai_study_service.get_study_plan(pid)
            p = data['progress']
            print(f"\n{data['plan']['plan_name']}: {p['done']}/{p['total']} done, {p['overdue']} missed")
            print("\n  a. Add a task   (or pick a task number below)")
            tasks = data['tasks']
            for i, t in enumerate(tasks, 1):
                print(f"  {i}. [{_state(t)}] {t['scheduled_date']} {t['task_title']} "
                      f"({t['duration_minutes']} min, {t['priority']})")
            choice = input("\nChoice (Enter to finish): ").strip().lower()
            if not choice:
                break
            if choice == 'a':
                title = input("Title: ").strip()
                when = input("Date (YYYY-MM-DD): ").strip()
                minutes = input("Minutes [60]: ").strip() or "60"
                priority = input("Priority (Low/Medium/High) [Medium]: ").strip() or "Medium"
                ai_study_service.add_task(pid, title, when, int(minutes), priority,
                                          student_id=student_id)
                print("Task added.")
                continue
            if not (choice.isdigit() and 1 <= int(choice) <= len(tasks)):
                print("Invalid choice.")
                continue
            task = tasks[int(choice) - 1]
            tid = task['task_id']
            print("  1. Complete  2. Undo complete  3. Skip  4. Move to another date  5. Edit  6. Delete")
            action = input("Action: ").strip()
            if action == '1':
                ai_study_service.complete_study_task(tid, student_id=student_id)
            elif action == '2':
                ai_study_service.uncomplete_task(tid, student_id)
            elif action == '3':
                ai_study_service.skip_task(tid, student_id)
            elif action == '4':
                ai_study_service.reschedule_task(tid, input("New date (YYYY-MM-DD): ").strip(), student_id)
            elif action == '5':
                title = input(f"Title [{task['task_title']}]: ").strip() or None
                minutes = input(f"Minutes [{task['duration_minutes']}]: ").strip()
                priority = input(f"Priority [{task['priority']}]: ").strip() or None
                notes = input("Notes (Enter to keep): ").strip() or None
                ai_study_service.update_task(tid, student_id, title=title,
                                             duration_minutes=int(minutes) if minutes else None,
                                             priority=priority, notes=notes)
            elif action == '6':
                if input("Delete this task? (y/n): ").strip().lower() == 'y':
                    ai_study_service.delete_task(tid, student_id)
            print("Done.")
    except Exception as e:
        print(f"\nError: {e}")
    input("\nPress Enter to continue...")


# ========== More Flashcard Functions ==========

def generate_flashcards_menu(student_id: str) -> None:
    """Paste notes; Claude (or the definitions in them) writes the cards."""
    print("\n" + "=" * 60)
    print("GENERATE FLASHCARDS FROM NOTES")
    print("=" * 60)
    deck_name = input("Deck name: ").strip()
    if not deck_name:
        print("Deck name is required.")
        input("\nPress Enter to continue...")
        return
    course_id = _choose_module(student_id)
    count = input("How many cards [10]: ").strip()
    print("\nPaste your notes. Finish with a line containing only END.")
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    try:
        print("\nWriting cards…")
        result = ai_study_service.generate_flashcards(student_id, course_id, deck_name,
                                                      "\n".join(lines),
                                                      int(count) if count.isdigit() else 10)
        if not result['created']:
            print("\nNo cards could be made. Without AI, cards come from lines like "
                  "'Term: definition' or 'X is a …'.")
        else:
            print(f"\n{len(result['created'])} card(s) added to '{deck_name}' "
                  f"({'written by Claude' if result['source'] == 'claude' else 'taken from definitions in your notes'}):")
            for card in result['cards']:
                print(f"  Q: {card['question']}\n  A: {card['answer']}\n")
    except Exception as e:
        print(f"\nError: {e}")
    input("\nPress Enter to continue...")


def manage_cards_menu(student_id: str) -> None:
    """Edit, suspend or delete cards; rename or delete a deck."""
    print("\n" + "=" * 60)
    print("MANAGE CARDS AND DECKS")
    print("=" * 60)
    try:
        deck = _pick_deck(student_id)
        if not deck:
            input("\nPress Enter to continue...")
            return
        print("\n  1. Edit / suspend / delete a card\n  2. Rename deck\n  3. Delete deck")
        action = input("Action: ").strip()
        if action == '1':
            cards = ai_study_service.list_flashcards(student_id, deck)
            card = _pick(cards, lambda c: f"{'[suspended] ' if c.get('suspended') else ''}"
                                          f"{c['question'][:60]} — next {c.get('next_review') or 'now'}")
            if card:
                print("  1. Edit  2. Suspend / unsuspend  3. Delete")
                what = input("Action: ").strip()
                if what == '1':
                    q = input(f"Question [{card['question']}]: ").strip() or None
                    a = input(f"Answer [{card['answer']}]: ").strip() or None
                    ai_study_service.update_flashcard(card['flashcard_id'], student_id, question=q, answer=a)
                elif what == '2':
                    ai_study_service.set_flashcard_suspended(card['flashcard_id'],
                                                             not card.get('suspended'), student_id)
                elif what == '3':
                    ai_study_service.delete_flashcard(card['flashcard_id'], student_id)
                print("Done.")
        elif action == '2':
            new = input("New deck name: ").strip()
            if new:
                print(f"{ai_study_service.rename_deck(student_id, deck, new)} card(s) moved.")
        elif action == '3':
            if input(f"Delete '{deck}' and all its cards? (y/n): ").strip().lower() == 'y':
                print(f"{ai_study_service.delete_deck(student_id, deck)} card(s) deleted.")
    except Exception as e:
        print(f"\nError: {e}")
    input("\nPress Enter to continue...")


# ========== This Week and Settings ==========

def this_week_menu(student_id: str) -> None:
    """Today's work and the next four weeks' exams and deadlines."""
    print("\n" + "=" * 60)
    print("TODAY AND THE WEEKS AHEAD")
    print("=" * 60)
    try:
        today = ai_study_service.today(student_id)
        ahead = ai_study_service.upcoming(student_id, 28)
        print(f"\n{today['date']}: {today['due_cards']} flashcard(s) due")
        for t in today['tasks_today']:
            print(f"  • Today: {t['task_title']} ({t['duration_minutes'] or 0} min) — {t['plan_name']}")
        if today['overdue_tasks']:
            print(f"  ⚠ {len(today['overdue_tasks'])} missed task(s) — use 'Manage a Plan' → "
                  "'Reschedule missed tasks'")
        print("\nExams (next 4 weeks):")
        for e in ahead['exams'] or []:
            print(f"  • {e['date']} {e.get('start_time') or ''} {e['module_code']} {e['name']} {e.get('room') or ''}")
        if not ahead['exams']:
            print("  None published.")
        print("\nDeadlines (next 4 weeks):")
        for d in ahead['deadlines'] or []:
            print(f"  • {str(d['due_date'])[:16]} {d['module_code']} {d['title']}")
        if not ahead['deadlines']:
            print("  None outstanding.")
    except Exception as e:
        print(f"\nError: {e}")
    input("\nPress Enter to continue...")


def settings_menu(student_id: str) -> None:
    """Reminder and sharing choices."""
    print("\n" + "=" * 60)
    print("REMINDER AND SHARING SETTINGS")
    print("=" * 60)
    try:
        prefs = ai_study_service.get_settings(student_id)

        def ask(label, current):
            value = input(f"{label} (y/n) [{'y' if current else 'n'}]: ").strip().lower()
            return current if value not in ('y', 'n') else value == 'y'

        reminders = ask("Daily reminder in my Hub inbox", prefs['reminders_enabled'])
        email = ask("Also email the reminder", prefs['email_reminders'])
        share = ask("Let my tutors and module staff see my study activity", prefs['share_with_tutor'])
        limit = input(f"Cards per review session [{prefs['daily_card_limit']}]: ").strip()
        ai_study_service.save_settings(student_id, reminders_enabled=reminders,
                                       email_reminders=email, share_with_tutor=share,
                                       daily_card_limit=int(limit) if limit.isdigit()
                                       else prefs['daily_card_limit'])
        print("\nSettings saved.")
    except Exception as e:
        print(f"\nError: {e}")
    input("\nPress Enter to continue...")


# ========== Staff ==========

def staff_overview_menu(viewer: dict) -> None:
    print("\n" + "=" * 60)
    print("STUDY COMPANION — STUDENT OVERVIEW")
    print("=" * 60)
    try:
        module = input("Module code to filter by (Enter for all your students): ").strip() or None
        rows = ai_study_service.staff_overview(viewer, module)
        if not rows:
            print("\nNone of your students use the study companion yet.")
        for r in rows:
            if not r['shared']:
                print(f"  {r['student_id']:<10} {r['name']:<28} (not shared)")
                continue
            completion = f"{r['completion_pct']:.0f}%" if r['completion_pct'] is not None else "—"
            print(f"  {r['student_id']:<10} {r['name']:<28} plans {r['active_plans']}  "
                  f"done {r['tasks_done']}  missed {r['tasks_missed']}  ({completion})  "
                  f"cards {r['cards_reviewed']}  last {r['last_active'] or '—'}")
    except Exception as e:
        print(f"\nError: {e}")
    input("\nPress Enter to continue...")


def staff_student_menu(viewer: dict) -> None:
    print("\n" + "=" * 60)
    print("STUDY COMPANION — STUDENT DETAILS")
    print("=" * 60)
    student_id = input("Student ID: ").strip()
    if not student_id:
        return
    try:
        d = ai_study_service.staff_student_detail(viewer, student_id)
        print(f"\n{d['name']} ({student_id})")
        if not d.get('shared'):
            print("This student has chosen not to share their study activity.")
        else:
            print(f"Last 14 days: {d['tasks_done']} done, {d['tasks_missed']} missed of {d['tasks_due']}; "
                  f"{d['cards_reviewed']} card reviews; last active {d.get('last_active') or '—'}")
            for p in d.get('plans', []):
                print(f"  • {p['plan_name']} — exam {p['end_date']}, {p['done'] or 0}/{p['tasks'] or 0} done, {p['status']}")
            for w in d.get('weak_modules', []):
                print(f"  ⚠ {w['module_code']}: {'; '.join(w['reasons'])}")
    except Exception as e:
        print(f"\nError: {e}")
    input("\nPress Enter to continue...")


def send_reminders_menu() -> None:
    try:
        result = ai_study_service.send_all_reminders()
        print(f"\nReminders sent: {result['sent']} of {result['checked']} companion user(s); "
              f"emails: {result['emailed']}. Each student gets at most one a day.")
    except Exception as e:
        print(f"\nError: {e}")
    input("\nPress Enter to continue...")


def engagement_scan_menu(viewer: dict) -> None:
    try:
        result = ai_study_service.engagement_scan(actor=viewer.get('username') or 'staff')
        print(f"\nEarly-warning indicators raised: {result['raised']}; resolved: {result['resolved']} "
              "(type 'study_plan_slippage').")
    except Exception as e:
        print(f"\nError: {e}")
    input("\nPress Enter to continue...")


# Main entry point for direct CLI usage
class AIStudyCLI:
    """CLI class for AI Study Companion."""

    def __init__(self):
        """Initialize the CLI."""
        self.service = AIStudyService()
        self.auth = get_auth()

    def run(self) -> None:
        """Run the CLI."""
        display_ai_study_menu()

    def main_menu(self) -> None:
        """Alias for run()."""
        self.run()


def main():
    """Main entry point."""
    cli = AIStudyCLI()
    cli.run()


if __name__ == "__main__":
    main()
