"""
Learning Management System (LMS) Core Service

This module provides core functionality for the LMS including course management,
content delivery, quizzes, discussions, and gradebook integration.
"""

from __future__ import annotations

import json
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from university_system.infrastructure.database.db import get_connection
from university_system.infrastructure.exceptions import (
    DatabaseError,
    CourseNotFoundError,
    ValidationError,
)
from university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)

class LMSCourseManager:
    """Manages LMS courses and course content"""

    @staticmethod
    def create_lms_course(
        module_code: str,
        instructor_id: str,
        course_description: str = "",
        syllabus_url: str = "",
        start_date: str = "",
        end_date: str = "",
        enrollment_limit: int = 0
    ) -> int:
        """Create a new LMS course"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO lms_courses (
                    module_code, instructor_id, course_description, syllabus_url,
                    start_date, end_date, enrollment_limit
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (module_code, instructor_id, course_description, syllabus_url,
                  start_date, end_date, enrollment_limit))

            course_id = cursor.lastrowid
            conn.commit()
            return course_id

        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error creating LMS course: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def publish_course(lms_course_id: int) -> bool:
        """Publish an LMS course to make it visible to students"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE lms_courses
                SET is_published = 1, updated_at = ?
                WHERE lms_course_id = ?
            ''', (datetime.now().isoformat(), lms_course_id))

            conn.commit()
            return True

        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error publishing course: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def get_course_details(lms_course_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed information about an LMS course"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT * FROM lms_courses
                WHERE lms_course_id = ?
            ''', (lms_course_id,))

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

        finally:
            conn.close()

    @staticmethod
    def get_instructor_courses(instructor_id: str) -> List[Dict[str, Any]]:
        """Get all courses taught by a specific instructor"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT * FROM lms_courses
                WHERE instructor_id = ?
                ORDER BY created_at DESC
            ''', (instructor_id,))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

class LMSContentManager:
    """Manages course content and materials"""

    @staticmethod
    def add_content(
        lms_course_id: int,
        content_type: str,
        title: str,
        description: str = "",
        content_url: str = "",
        content_order: int = 0,
        release_date: str = ""
    ) -> int:
        """Add content to a course"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO lms_course_content (
                    lms_course_id, content_type, title, description,
                    content_url, content_order, release_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (lms_course_id, content_type, title, description,
                  content_url, content_order, release_date))

            content_id = cursor.lastrowid
            conn.commit()
            return content_id

        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error adding content: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def get_course_content(lms_course_id: int) -> List[Dict[str, Any]]:
        """Get all content for a specific course"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT * FROM lms_course_content
                WHERE lms_course_id = ? AND is_published = 1
                ORDER BY content_order, created_at
            ''', (lms_course_id,))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

    @staticmethod
    def add_video_lecture(
        content_id: int,
        video_url: str,
        duration_minutes: int,
        thumbnail_url: str = "",
        transcript_url: str = "",
        video_quality: str = "720p"
    ) -> int:
        """Add a video lecture to content"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO lms_video_lectures (
                    content_id, video_url, duration_minutes, thumbnail_url,
                    transcript_url, video_quality
                )
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (content_id, video_url, duration_minutes, thumbnail_url,
                  transcript_url, video_quality))

            video_id = cursor.lastrowid
            conn.commit()
            return video_id

        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error adding video lecture: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def increment_video_view(video_id: int) -> None:
        """Increment view count for a video"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE lms_video_lectures
                SET view_count = view_count + 1
                WHERE video_id = ?
            ''', (video_id,))

            conn.commit()

        finally:
            conn.close()

class LMSDiscussionManager:
    """Manages discussion forums and posts"""

    @staticmethod
    def create_forum(
        lms_course_id: int,
        topic: str,
        description: str,
        created_by: str,
        is_pinned: bool = False
    ) -> int:
        """Create a new discussion forum"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO lms_discussion_forums (
                    lms_course_id, topic, description, created_by, is_pinned
                )
                VALUES (?, ?, ?, ?, ?)
            ''', (lms_course_id, topic, description, created_by, is_pinned))

            forum_id = cursor.lastrowid
            conn.commit()
            return forum_id

        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error creating forum: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def add_post(
        forum_id: int,
        user_id: str,
        content: str,
        parent_post_id: Optional[int] = None,
        attachments: str = ""
    ) -> int:
        """Add a post or reply to a forum"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO lms_discussion_posts (
                    forum_id, user_id, content, parent_post_id, attachments
                )
                VALUES (?, ?, ?, ?, ?)
            ''', (forum_id, user_id, content, parent_post_id, attachments))

            post_id = cursor.lastrowid
            conn.commit()
            return post_id

        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error adding post: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def get_forum_posts(forum_id: int) -> List[Dict[str, Any]]:
        """Get all posts in a forum"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT * FROM lms_discussion_posts
                WHERE forum_id = ?
                ORDER BY created_at ASC
            ''', (forum_id,))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

    @staticmethod
    def like_post(post_id: int) -> None:
        """Increment likes for a post"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE lms_discussion_posts
                SET likes_count = likes_count + 1
                WHERE post_id = ?
            ''', (post_id,))

            conn.commit()

        finally:
            conn.close()

class LMSQuizManager:
    """Manages quizzes and assessments"""

    @staticmethod
    def create_quiz(
        lms_course_id: int,
        title: str,
        description: str = "",
        duration_minutes: int = 60,
        passing_score: float = 70.0,
        max_attempts: int = 1,
        available_from: str = "",
        available_until: str = ""
    ) -> int:
        """Create a new quiz"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO lms_quizzes (
                    lms_course_id, title, description, duration_minutes,
                    passing_score, max_attempts, available_from, available_until
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (lms_course_id, title, description, duration_minutes,
                  passing_score, max_attempts, available_from, available_until))

            quiz_id = cursor.lastrowid
            conn.commit()
            return quiz_id

        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error creating quiz: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def add_question(
        quiz_id: int,
        question_text: str,
        question_type: str,
        correct_answer: str,
        points: int = 1,
        options: str = "",
        explanation: str = ""
    ) -> int:
        """Add a question to a quiz"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO lms_quiz_questions (
                    quiz_id, question_text, question_type, correct_answer,
                    points, options, explanation
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (quiz_id, question_text, question_type, correct_answer,
                  points, options, explanation))

            question_id = cursor.lastrowid
            conn.commit()
            return question_id

        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error adding question: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def submit_quiz(
        quiz_id: int,
        student_id: str,
        answers: Dict[int, str],
        time_taken_minutes: int
    ) -> Tuple[int, float]:
        """Submit a quiz and calculate score"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Get attempt number
            cursor.execute('''
                SELECT COUNT(*) as attempt_count
                FROM lms_quiz_submissions
                WHERE quiz_id = ? AND student_id = ?
            ''', (quiz_id, student_id))

            attempt_number = cursor.fetchone()['attempt_count'] + 1

            # Get quiz questions
            cursor.execute('''
                SELECT question_id, correct_answer, points
                FROM lms_quiz_questions
                WHERE quiz_id = ?
            ''', (quiz_id,))

            questions = {row['question_id']: row for row in cursor.fetchall()}

            # Calculate score
            score = 0
            total_points = sum(q['points'] for q in questions.values())

            for question_id, student_answer in answers.items():
                if question_id in questions:
                    if student_answer.strip().lower() == questions[question_id]['correct_answer'].strip().lower():
                        score += questions[question_id]['points']

            percentage = (score / total_points * 100) if total_points > 0 else 0

            # Record submission
            cursor.execute('''
                INSERT INTO lms_quiz_submissions (
                    quiz_id, student_id, attempt_number, score, total_points, time_taken_minutes
                )
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (quiz_id, student_id, attempt_number, percentage, total_points, time_taken_minutes))

            submission_id = cursor.lastrowid
            conn.commit()

            return submission_id, percentage

        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error submitting quiz: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def get_quiz_results(quiz_id: int, student_id: str) -> List[Dict[str, Any]]:
        """Get all quiz attempts for a student"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT * FROM lms_quiz_submissions
                WHERE quiz_id = ? AND student_id = ?
                ORDER BY attempt_number
            ''', (quiz_id, student_id))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

class LMSGradebookManager:
    """Manages gradebook entries and calculations"""

    @staticmethod
    def add_grade_entry(
        lms_course_id: int,
        student_id: str,
        assignment_type: str,
        assignment_id: int,
        score: float,
        max_score: float,
        weight: float = 1.0,
        feedback: str = "",
        graded_by: str = ""
    ) -> int:
        """Add an entry to the gradebook"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO lms_gradebook (
                    lms_course_id, student_id, assignment_type, assignment_id,
                    score, max_score, weight, feedback, graded_by, graded_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (lms_course_id, student_id, assignment_type, assignment_id,
                  score, max_score, weight, feedback, graded_by,
                  datetime.now().isoformat()))

            entry_id = cursor.lastrowid
            conn.commit()
            return entry_id

        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error adding grade entry: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def get_student_grades(lms_course_id: int, student_id: str) -> List[Dict[str, Any]]:
        """Get all grade entries for a student in a course"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT * FROM lms_gradebook
                WHERE lms_course_id = ? AND student_id = ?
                ORDER BY graded_at DESC
            ''', (lms_course_id, student_id))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

    @staticmethod
    def calculate_course_grade(lms_course_id: int, student_id: str) -> float:
        """Calculate overall course grade for a student"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT score, max_score, weight
                FROM lms_gradebook
                WHERE lms_course_id = ? AND student_id = ?
            ''', (lms_course_id, student_id))

            entries = cursor.fetchall()

            if not entries:
                return 0.0

            total_weighted_score = 0
            total_weight = 0

            for entry in entries:
                percentage = (entry['score'] / entry['max_score'] * 100) if entry['max_score'] > 0 else 0
                total_weighted_score += percentage * entry['weight']
                total_weight += entry['weight']

            return (total_weighted_score / total_weight) if total_weight > 0 else 0.0

        finally:
            conn.close()

def display_lms_menu(auth):
    """Display the LMS (Learning Management System) CLI menu"""
    while True:
        print("\n" + "="*50)
        print(f"    {get_text('lms.title', default='LMS (LEARNING MANAGEMENT SYSTEM)')}")
        print("="*50)
        print(f"1. {get_text('lms.menu.manage_courses', default='Manage Courses')}")
        print(f"2. {get_text('lms.menu.content_mgmt', default='Course Content Management')}")
        print(f"3. {get_text('lms.menu.video_lectures', default='Video Lectures')}")
        print(f"4. {get_text('lms.menu.discussion_forums', default='Discussion Forums')}")
        print(f"5. {get_text('lms.menu.quizzes', default='Quizzes & Assessments')}")
        print(f"6. {get_text('lms.menu.gradebook', default='Gradebook')}")
        print(f"7. {get_text('lms.menu.progress_tracking', default='Student Progress Tracking')}")
        print(f"8. {get_text('lms.menu.language', default='Language')}")
        print(f"9. {get_text('lms.menu.return_main', default='Return to Main Menu')}")
        print("="*50)

        try:
            choice = input(f"\n{get_text('lms.enter_choice', default='Enter your choice')} (1-9): ").strip()
            if choice == '1':
                print(f"\n📚 {get_text('lms.feature_via_managers', default='Course Management - Feature available via managers')}")
                print("Use: from university_system.modules.domain.academics.services.lms import LMSCourseManager")
            elif choice in ['2', '3', '4', '5', '6', '7']:
                print(f"\n📋 {get_text('lms.feature_available', default='Feature available via LMS managers')}")
            elif choice == '8':
                display_language_menu_option()
            elif choice == '9':
                break
            else:
                print(get_text('lms.invalid_choice', default='Invalid choice.'))
        except (KeyboardInterrupt, EOFError):
            break
        except Exception as e:
            print(get_text('lms.error', default='Error: {error}').format(error=e))
            break

# Import the real GUI launcher
try:
    from university_system.modules.domain.academics.gui.lms_gui import launch_lms_gui
except ImportError as e:
    print(f"Warning: Could not import LMS GUI: {e}")
    # Fallback to factory if GUI not available
    from university_system.modules.shared.feature_gui_factory import create_gui_launcher
    launch_lms_gui = create_gui_launcher(
        title="LMS (Learning Management System)",
        description="""Learning Management System with course content, video lectures, quizzes, discussions, and gradebook.

Features:
• Course content management
• Video lectures & resources
• Discussion forums
• Quizzes & assessments
• Gradebook & grading
• Student progress tracking""",
        cli_instruction="Use CLI: LMS (Learning Management System)"
    )

__all__ = [
    'LMSCourseManager',
    'LMSContentManager',
    'LMSDiscussionManager',
    'LMSQuizManager',
    'LMSGradebookManager',
    'display_lms_menu',
    'launch_lms_gui',
]
