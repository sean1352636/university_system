"""
AI Study Companion Service

Provides personalized study assistance with AI-powered features.
"""

from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import json
import random

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

class AIStudyService:
    """Service for AI-powered study assistance."""

    def __init__(self):
        """Initialize the AI Study Service."""
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        """Create database tables if they don't exist."""
        with transaction() as conn:
            # Study Plans table
            # Note: Removed FOREIGN KEY constraint on student_id to allow flexibility
            # with different authentication systems (users vs students tables)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS study_plans (
                    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    course_id TEXT,
                    plan_name TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    total_hours INTEGER DEFAULT 0,
                    difficulty_level TEXT DEFAULT 'Medium',
                    status TEXT DEFAULT 'Active',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Study Plan Tasks table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS study_plan_tasks (
                    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER NOT NULL,
                    task_title TEXT NOT NULL,
                    task_description TEXT,
                    scheduled_date TEXT NOT NULL,
                    duration_minutes INTEGER DEFAULT 60,
                    priority TEXT DEFAULT 'Medium',
                    completed BOOLEAN DEFAULT 0,
                    completed_at TEXT,
                    FOREIGN KEY (plan_id) REFERENCES study_plans(plan_id) ON DELETE CASCADE
                )
            """)

            # Flashcards table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS flashcards (
                    flashcard_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    course_id TEXT,
                    deck_name TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    difficulty_rating INTEGER DEFAULT 0,
                    last_reviewed TEXT,
                    next_review TEXT,
                    review_count INTEGER DEFAULT 0,
                    correct_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Concept Explanations table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS concept_explanations (
                    explanation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    course_id TEXT,
                    concept_name TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    difficulty_level TEXT DEFAULT 'Beginner',
                    helpful_rating INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            log_activity('create', 'ai_study_tables', details={'status': 'AI Study tables created'})

    # ========== Study Plan Generation ==========

    def generate_study_plan(self, student_id: str, course_id: Optional[str],
                           exam_date: str, hours_per_day: int = 2) -> Dict:
        """
        Generate a personalized study plan based on upcoming exams.

        Args:
            student_id: Student's ID
            course_id: Course ID (optional)
            exam_date: Exam date (YYYY-MM-DD format)
            hours_per_day: Hours available per day

        Returns:
            Dictionary containing the generated study plan
        """
        # Calculate days until exam
        exam_datetime = datetime.strptime(exam_date, '%Y-%m-%d')
        days_until_exam = (exam_datetime - datetime.now()).days

        if days_until_exam < 0:
            raise ValueError("Exam date must be in the future")

        total_hours = days_until_exam * hours_per_day

        with transaction() as conn:
            # Create study plan
            cursor = conn.execute("""
                INSERT INTO study_plans
                (student_id, course_id, plan_name, start_date, end_date, total_hours)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (student_id, course_id, f"Exam Prep - {exam_date}",
                  datetime.now().strftime('%Y-%m-%d'), exam_date, total_hours))

            plan_id = cursor.lastrowid

            # Generate study tasks
            tasks = self._generate_study_tasks(plan_id, days_until_exam, hours_per_day)

            for task in tasks:
                conn.execute("""
                    INSERT INTO study_plan_tasks
                    (plan_id, task_title, task_description, scheduled_date, duration_minutes, priority)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (plan_id, task['title'], task['description'],
                      task['date'], task['duration'], task['priority']))

            log_activity('create', 'study_plan',
                        details={'plan_id': plan_id, 'student_id': student_id, 'exam_date': exam_date})

            return {
                'plan_id': plan_id,
                'total_hours': total_hours,
                'days_until_exam': days_until_exam,
                'tasks_generated': len(tasks)
            }

    def _generate_study_tasks(self, plan_id: int, days: int, hours_per_day: int) -> List[Dict]:
        """Generate study tasks for the plan."""
        tasks = []
        topics = [
            "Review lecture notes",
            "Practice problems",
            "Read textbook chapters",
            "Watch tutorial videos",
            "Create summary notes",
            "Practice past exams",
            "Review key concepts",
            "Memorize formulas/definitions",
            "Group study session",
            "Final review"
        ]

        # Distribute topics across available days
        for day in range(days):
            date = (datetime.now() + timedelta(days=day)).strftime('%Y-%m-%d')

            # Prioritize differently based on proximity to exam
            if day < days * 0.3:  # First 30% - learning phase
                priority = "Low"
                selected_topics = topics[:4]
            elif day < days * 0.7:  # Middle 40% - practice phase
                priority = "Medium"
                selected_topics = topics[4:8]
            else:  # Last 30% - review phase
                priority = "High"
                selected_topics = topics[6:]

            # Select task for this day
            topic = random.choice(selected_topics)
            duration = hours_per_day * 60  # Convert to minutes

            tasks.append({
                'title': topic,
                'description': f"Spend {hours_per_day} hour(s) on {topic.lower()}",
                'date': date,
                'duration': duration,
                'priority': priority
            })

        return tasks

    def get_study_plan(self, plan_id: int) -> Optional[Dict]:
        """Retrieve a study plan by ID."""
        with get_connection() as conn:
            # Get plan details
            plan_row = conn.execute("""
                SELECT * FROM study_plans WHERE plan_id = ?
            """, (plan_id,)).fetchone()

            if not plan_row:
                return None

            # Get tasks
            tasks = conn.execute("""
                SELECT * FROM study_plan_tasks
                WHERE plan_id = ?
                ORDER BY scheduled_date, priority DESC
            """, (plan_id,)).fetchall()

            return {
                'plan': dict(plan_row),
                'tasks': [dict(task) for task in tasks]
            }

    def get_student_study_plans(self, student_id: str) -> List[Dict]:
        """Get all study plans for a student."""
        with get_connection() as conn:
            plans = conn.execute("""
                SELECT * FROM study_plans
                WHERE student_id = ?
                ORDER BY created_at DESC
            """, (student_id,)).fetchall()

            return [dict(plan) for plan in plans]

    def complete_study_task(self, task_id: int) -> bool:
        """Mark a study task as completed."""
        with transaction() as conn:
            conn.execute("""
                UPDATE study_plan_tasks
                SET completed = 1, completed_at = ?
                WHERE task_id = ?
            """, (datetime.now().isoformat(), task_id))

            log_activity('update', 'study_task', task_id=task_id,
                        details={'status': 'completed'})
            return True

    # ========== Flashcard System ==========

    def create_flashcard(self, student_id: str, course_id: Optional[str],
                        deck_name: str, question: str, answer: str) -> int:
        """
        Create a new flashcard for spaced repetition learning.

        Args:
            student_id: Student's ID
            course_id: Course ID (optional)
            deck_name: Name of the flashcard deck
            question: Question text
            answer: Answer text

        Returns:
            Flashcard ID
        """
        next_review = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO flashcards
                (student_id, course_id, deck_name, question, answer, next_review)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (student_id, course_id, deck_name, question, answer, next_review))

            flashcard_id = cursor.lastrowid

            log_activity('create', 'flashcard',
                        details={'flashcard_id': flashcard_id, 'deck': deck_name})

            return flashcard_id

    def get_due_flashcards(self, student_id: str, deck_name: Optional[str] = None) -> List[Dict]:
        """Get flashcards due for review using spaced repetition."""
        with get_connection() as conn:
            query = """
                SELECT * FROM flashcards
                WHERE student_id = ?
                AND (next_review IS NULL OR next_review <= ?)
            """
            params = [student_id, datetime.now().strftime('%Y-%m-%d')]

            if deck_name:
                query += " AND deck_name = ?"
                params.append(deck_name)

            query += " ORDER BY next_review LIMIT 20"

            flashcards = conn.execute(query, params).fetchall()
            return [dict(card) for card in flashcards]

    def review_flashcard(self, flashcard_id: int, correct: bool) -> Dict:
        """
        Review a flashcard and update spaced repetition schedule.

        Args:
            flashcard_id: Flashcard ID
            correct: Whether the answer was correct

        Returns:
            Dictionary with next review date
        """
        with transaction() as conn:
            # Get current flashcard data
            card = conn.execute("""
                SELECT review_count, difficulty_rating, correct_count
                FROM flashcards WHERE flashcard_id = ?
            """, (flashcard_id,)).fetchone()

            review_count = card['review_count'] + 1
            correct_count = card['correct_count'] + (1 if correct else 0)

            # Calculate next review interval using spaced repetition
            if correct:
                # Increase interval: 1, 3, 7, 14, 30 days
                intervals = [1, 3, 7, 14, 30, 60, 120]
                interval_index = min(review_count, len(intervals) - 1)
                days_until_next = intervals[interval_index]
            else:
                # Reset to 1 day if incorrect
                days_until_next = 1

            next_review = (datetime.now() + timedelta(days=days_until_next)).strftime('%Y-%m-%d')

            # Update flashcard
            conn.execute("""
                UPDATE flashcards
                SET review_count = ?,
                    correct_count = ?,
                    last_reviewed = ?,
                    next_review = ?
                WHERE flashcard_id = ?
            """, (review_count, correct_count, datetime.now().isoformat(),
                  next_review, flashcard_id))

            log_activity('update', 'flashcard_review',
                        details={'flashcard_id': flashcard_id, 'correct': correct, 'next_review': next_review})

            return {
                'next_review': next_review,
                'days_until_next': days_until_next,
                'review_count': review_count
            }

    def get_flashcard_decks(self, student_id: str) -> List[Dict]:
        """Get all flashcard decks for a student with statistics."""
        with get_connection() as conn:
            decks = conn.execute("""
                SELECT
                    deck_name,
                    course_id,
                    COUNT(*) as total_cards,
                    SUM(CASE WHEN next_review <= ? THEN 1 ELSE 0 END) as due_count,
                    AVG(CAST(correct_count AS FLOAT) / NULLIF(review_count, 0)) * 100 as accuracy
                FROM flashcards
                WHERE student_id = ?
                GROUP BY deck_name, course_id
                ORDER BY deck_name
            """, (datetime.now().strftime('%Y-%m-%d'), student_id)).fetchall()

            return [dict(deck) for deck in decks]

    # ========== Concept Explainer ==========

    def explain_concept(self, student_id: str, course_id: Optional[str],
                       concept_name: str, difficulty_level: str = "Beginner") -> Dict:
        """
        Generate an AI-powered explanation for a difficult concept.

        Args:
            student_id: Student's ID
            course_id: Course ID (optional)
            concept_name: Name of the concept to explain
            difficulty_level: 'Beginner', 'Intermediate', or 'Advanced'

        Returns:
            Dictionary containing the explanation
        """
        # Generate explanation based on difficulty level
        explanations = {
            "Beginner": f"""
**{concept_name}** - Simple Explanation:

Let me break this down in simple terms:

• **What it is**: {concept_name} is a fundamental concept that helps you understand...
• **Why it matters**: This is important because...
• **Key points**: Remember these main ideas:
  1. First key point
  2. Second key point
  3. Third key point

**Example**: Think of it like...

**Common misconceptions**: Students often confuse this with...
            """,
            "Intermediate": f"""
**{concept_name}** - Detailed Explanation:

**Definition**: {concept_name} refers to...

**How it works**:
1. First, understand that...
2. Then, consider how...
3. Finally, apply this to...

**Real-world applications**:
• Application 1
• Application 2
• Application 3

**Practice problems**: Try solving...
            """,
            "Advanced": f"""
**{concept_name}** - Advanced Analysis:

**Theoretical foundation**: {concept_name} is rooted in...

**Mathematical/Technical details**:
• Formula/Principle 1
• Formula/Principle 2

**Edge cases and limitations**: Consider these scenarios...

**Related concepts**: This connects to...

**Research applications**: Current research explores...
            """
        }

        explanation = explanations.get(difficulty_level, explanations["Beginner"])

        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO concept_explanations
                (student_id, course_id, concept_name, explanation, difficulty_level)
                VALUES (?, ?, ?, ?, ?)
            """, (student_id, course_id, concept_name, explanation, difficulty_level))

            explanation_id = cursor.lastrowid

            log_activity('create', 'concept_explanation',
                        details={'explanation_id': explanation_id, 'concept': concept_name, 'level': difficulty_level})

            return {
                'explanation_id': explanation_id,
                'concept_name': concept_name,
                'explanation': explanation,
                'difficulty_level': difficulty_level
            }

    def rate_explanation(self, explanation_id: int, rating: int) -> bool:
        """Rate the helpfulness of an explanation (1-5 stars)."""
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")

        with transaction() as conn:
            conn.execute("""
                UPDATE concept_explanations
                SET helpful_rating = ?
                WHERE explanation_id = ?
            """, (rating, explanation_id))

            log_activity('update', 'concept_explanation_rating',
                        explanation_id=explanation_id, details={'rating': rating})
            return True

    def get_explanation_history(self, student_id: str) -> List[Dict]:
        """Get all concept explanations for a student."""
        with get_connection() as conn:
            explanations = conn.execute("""
                SELECT * FROM concept_explanations
                WHERE student_id = ?
                ORDER BY created_at DESC
                LIMIT 50
            """, (student_id,)).fetchall()

            return [dict(exp) for exp in explanations]

    # ========== Analytics ==========

    def get_study_analytics(self, student_id: str) -> Dict:
        """Get comprehensive study analytics for a student."""
        with get_connection() as conn:
            # Study plan stats
            plan_stats = conn.execute("""
                SELECT
                    COUNT(*) as total_plans,
                    SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) as active_plans,
                    SUM(total_hours) as planned_hours
                FROM study_plans
                WHERE student_id = ?
            """, (student_id,)).fetchone()

            # Task completion stats
            task_stats = conn.execute("""
                SELECT
                    COUNT(*) as total_tasks,
                    SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed_tasks,
                    SUM(duration_minutes) as total_minutes
                FROM study_plan_tasks spt
                JOIN study_plans sp ON spt.plan_id = sp.plan_id
                WHERE sp.student_id = ?
            """, (student_id,)).fetchone()

            # Flashcard stats
            flashcard_stats = conn.execute("""
                SELECT
                    COUNT(*) as total_cards,
                    COUNT(DISTINCT deck_name) as total_decks,
                    AVG(CAST(correct_count AS FLOAT) / NULLIF(review_count, 0)) * 100 as avg_accuracy
                FROM flashcards
                WHERE student_id = ?
            """, (student_id,)).fetchone()

            return {
                'study_plans': dict(plan_stats) if plan_stats else {},
                'tasks': dict(task_stats) if task_stats else {},
                'flashcards': dict(flashcard_stats) if flashcard_stats else {}
            }
