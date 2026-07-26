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

from education_system.systems.university.domain.academics.ai_study.services.ai_study_service import AIStudyService
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
    user_id = current_user.get('id') or current_user.get('username')
    user_role = current_user.get('role', 'student')

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

        # Flashcard options
        print("\n[FLASHCARDS]")
        add_option("Create Flashcard", "create_flashcard")
        add_option("View Flashcard Decks", "view_decks")
        add_option("Start Review Session", "review_session")
        add_option("View Due Flashcards", "view_due")

        # Concept Explainer options
        print("\n[CONCEPT EXPLAINER]")
        add_option("Explain a Concept", "explain_concept")
        add_option("View Explanation History", "view_history")
        add_option("Rate Explanation", "rate_explanation")

        # Analytics options
        print("\n[ANALYTICS]")
        add_option("View Study Analytics", "analytics")

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

    course_id = input("Course ID (optional, press Enter to skip): ").strip() or None

    print("\nEnter exam date (YYYY-MM-DD):")
    exam_date = input("Exam date: ").strip()

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
    hours_per_day = int(hours_input) if hours_input.isdigit() else 2

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
        completed = sum(1 for t in tasks if t['completed'])
        print(f"Completed: {completed}/{len(tasks)}")

        if len(tasks) > 0:
            completion_rate = (completed / len(tasks)) * 100
            print(f"Progress: {completion_rate:.1f}%")

        # Display tasks grouped by status
        print("\n--- PENDING TASKS ---")
        pending_tasks = [t for t in tasks if not t['completed']]
        if not pending_tasks:
            print("No pending tasks!")
        else:
            for task in pending_tasks:
                print(f"\n  Task ID: {task['task_id']}")
                print(f"  Title: {task['task_title']}")
                print(f"  Date: {task['scheduled_date']}")
                print(f"  Duration: {task['duration_minutes']} minutes")
                print(f"  Priority: {task['priority']}")
                if task['task_description']:
                    print(f"  Description: {task['task_description']}")

        print("\n--- COMPLETED TASKS ---")
        completed_tasks = [t for t in tasks if t['completed']]
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
                pending = [t for t in plan_data['tasks'] if not t['completed']]
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

        ai_study_service.complete_study_task(task['task_id'])

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
                response = input("\nDid you get it correct? (y/n/q to quit): ").strip().lower()

                if response == 'q':
                    print("\nReview session ended early.")
                    break
                elif response in ['y', 'n']:
                    correct = (response == 'y')

                    # Update flashcard
                    result = ai_study_service.review_flashcard(card['flashcard_id'], correct)

                    if correct:
                        correct_count += 1
                        print(f"\nCorrect! Next review in {result['days_until_next']} days.")
                    else:
                        incorrect_count += 1
                        print("\nMarked for review. You'll see this again tomorrow.")

                    break
                else:
                    print("Invalid input. Please enter 'y', 'n', or 'q'.")

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

    course_id = input("Course ID (optional, press Enter to skip): ").strip() or None

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
        print("\n" + "-" * 60)
        print(result['explanation'])
        print("-" * 60)

        # Rate the explanation
        rate = input("\nWas this explanation helpful? Rate it (1-5 stars, or press Enter to skip): ").strip()
        if rate.isdigit() and 1 <= int(rate) <= 5:
            ai_study_service.rate_explanation(result['explanation_id'], int(rate))
            print("\nThank you for your feedback!")

        # Option to create flashcards from explanation
        create_fc = input("\nCreate a flashcard from this concept? (y/n): ").strip().lower()
        if create_fc == 'y':
            deck_name = input("Deck name: ").strip()
            if deck_name:
                ai_study_service.create_flashcard(
                    student_id=student_id,
                    course_id=course_id,
                    deck_name=deck_name,
                    question=f"What is {concept_name}?",
                    answer=result['explanation']
                )
                print("\nFlashcard created successfully!")

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

        ai_study_service.rate_explanation(explanation['explanation_id'], int(rating))

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
        total_tasks = tasks.get('total_tasks', 0)
        completed_tasks = tasks.get('completed_tasks', 0)

        print(f"Total Tasks: {total_tasks}")
        print(f"Completed Tasks: {completed_tasks}")
        print(f"Pending Tasks: {total_tasks - completed_tasks}")

        if total_tasks > 0:
            completion_rate = (completed_tasks / total_tasks) * 100
            print(f"Completion Rate: {completion_rate:.1f}%")

            # Progress bar
            bar_length = 20
            filled = int(bar_length * completion_rate / 100)
            bar = "█" * filled + "░" * (bar_length - filled)
            print(f"Progress: [{bar}] {completion_rate:.1f}%")

        total_minutes = tasks.get('total_minutes', 0)
        print(f"Total Study Time: {total_minutes} minutes ({total_minutes // 60} hours {total_minutes % 60} min)")

        # Flashcards section
        print("\n" + "=" * 60)
        print("FLASHCARDS")
        print("=" * 60)

        cards = analytics.get('flashcards', {})
        print(f"Total Cards: {cards.get('total_cards', 0)}")
        print(f"Total Decks: {cards.get('total_decks', 0)}")

        avg_accuracy = cards.get('avg_accuracy', 0) or 0
        print(f"Average Accuracy: {avg_accuracy:.1f}%")

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
