"""
Learning Management System (LMS) Core Service

This module provides core functionality for the LMS including course management,
content delivery, quizzes, discussions, and gradebook integration.
"""

from __future__ import annotations

import json
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.exceptions import (
    DatabaseError,
    CourseNotFoundError,
    ValidationError,
)
from education_system.systems.university.infrastructure.i18n import (
    get_text,
    get_current_language,
)
from education_system.systems.university.infrastructure.utils.language_selector import (
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

# ---------------------------------------------------------------------------
# CLI helper: list LMS courses and let user pick one
# ---------------------------------------------------------------------------

def _list_lms_courses(cursor):
    """Return list of (lms_course_id, module_code, description, is_published)."""
    cursor.execute("""
    SELECT lms_course_id, module_code, course_description, is_published
    FROM lms_courses ORDER BY lms_course_id
    """)
    return cursor.fetchall()


def _pick_lms_course(cursor, prompt="Select course"):
    rows = _list_lms_courses(cursor)
    if not rows:
        print("No LMS courses found."); return None
    print("\nLMS Courses:")
    for i, r in enumerate(rows, 1):
        pub = "Published" if r[3] else "Draft"
        desc = (r[2] or "")[:30]
        print(f"  {i}. [{r[1]}] {desc} ({pub})")
    while True:
        raw = input(f"{prompt} (or Enter to go back): ").strip()
        if not raw: return None
        try:
            idx = int(raw)
            if 1 <= idx <= len(rows):
                return rows[idx - 1]
            print("Invalid choice.")
        except ValueError:
            print("Please enter a number.")


# ---------------------------------------------------------------------------
# 1. Course Management CLI
# ---------------------------------------------------------------------------

def _cli_manage_courses(auth):
    while True:
        print("\n" + "-"*40)
        print("LMS Course Management")
        print("-"*40)
        print("1. Create course")
        print("2. List courses")
        print("3. View course details")
        print("4. Publish course")
        print("0. Back")

        choice = input("Choice: ").strip()
        if choice == '0' or not choice:
            return

        try:
            if choice == '1':
                code = input("Module code (e.g. CIS0001): ").strip()
                if not code: continue
                instr = input("Instructor ID: ").strip()
                desc = input("Description: ").strip()
                syllabus = input("Syllabus URL (optional): ").strip()
                start = input("Start date YYYY-MM-DD (optional): ").strip()
                end = input("End date YYYY-MM-DD (optional): ").strip()
                limit_str = input("Enrollment limit (0=unlimited): ").strip()
                limit = int(limit_str) if limit_str.isdigit() else 0

                cid = LMSCourseManager.create_lms_course(
                    code, instr, desc, syllabus, start, end, limit)
                print(f"\nCourse created (ID: {cid})")

            elif choice == '2':
                conn = get_connection()
                rows = _list_lms_courses(conn.cursor())
                conn.close()
                if not rows:
                    print("No courses found.")
                else:
                    print(f"\n{'ID':<5} {'Module':<12} {'Description':<35} {'Status':<10}")
                    print("-"*62)
                    for r in rows:
                        pub = "Published" if r[3] else "Draft"
                        print(f"{r[0]:<5} {r[1]:<12} {(r[2] or '')[:35]:<35} {pub:<10}")

            elif choice == '3':
                cid = input("Course ID: ").strip()
                if not cid: continue
                details = LMSCourseManager.get_course_details(int(cid))
                if details:
                    for k, v in details.items():
                        print(f"  {k}: {v}")
                else:
                    print("Course not found.")

            elif choice == '4':
                cid = input("Course ID to publish: ").strip()
                if not cid: continue
                LMSCourseManager.publish_course(int(cid))
                print("Course published.")

        except Exception as e:
            print(f"Error: {e}")

        input("\nPress Enter to continue...")


# ---------------------------------------------------------------------------
# 2. Content Management CLI
# ---------------------------------------------------------------------------

def _cli_content_management(auth):
    while True:
        print("\n" + "-"*40)
        print("Course Content Management")
        print("-"*40)
        print("1. Add content to course")
        print("2. View course content")
        print("0. Back")

        choice = input("Choice: ").strip()
        if choice == '0' or not choice:
            return

        try:
            if choice == '1':
                conn = get_connection()
                course = _pick_lms_course(conn.cursor(), "Select course to add content")
                conn.close()
                if not course: continue

                types = ["lecture", "reading", "assignment", "lab", "resource"]
                print("\nContent types:")
                for i, t in enumerate(types, 1):
                    print(f"  {i}. {t}")
                tidx = input("Select type: ").strip()
                ctype = types[int(tidx) - 1] if tidx.isdigit() and 1 <= int(tidx) <= len(types) else "lecture"

                title = input("Title: ").strip()
                if not title: continue
                desc = input("Description: ").strip()
                url = input("Content URL (optional): ").strip()
                order = input("Display order (default 0): ").strip()
                order = int(order) if order.isdigit() else 0

                cid = LMSContentManager.add_content(
                    course[0], ctype, title, desc, url, order)
                print(f"\nContent added (ID: {cid})")

            elif choice == '2':
                conn = get_connection()
                course = _pick_lms_course(conn.cursor(), "Select course")
                conn.close()
                if not course: continue

                content = LMSContentManager.get_course_content(course[0])
                if not content:
                    print("No published content found.")
                else:
                    print(f"\n{'#':<4} {'Type':<12} {'Title':<35} {'URL':<20}")
                    print("-"*71)
                    for i, c in enumerate(content, 1):
                        print(f"{i:<4} {c.get('content_type',''):<12} {c.get('title','')[:35]:<35} {(c.get('content_url','') or '')[:20]}")

        except Exception as e:
            print(f"Error: {e}")

        input("\nPress Enter to continue...")


# ---------------------------------------------------------------------------
# 3. Video Lectures CLI
# ---------------------------------------------------------------------------

def _cli_video_lectures(auth):
    while True:
        print("\n" + "-"*40)
        print("Video Lectures")
        print("-"*40)
        print("1. Add video lecture")
        print("2. View videos for a course")
        print("0. Back")

        choice = input("Choice: ").strip()
        if choice == '0' or not choice:
            return

        try:
            if choice == '1':
                content_id = input("Content ID to attach video to: ").strip()
                if not content_id: continue
                url = input("Video URL: ").strip()
                if not url: continue
                dur = input("Duration (minutes): ").strip()
                dur = int(dur) if dur.isdigit() else 0
                quality = input("Quality (360p/480p/720p/1080p) [720p]: ").strip() or "720p"

                vid = LMSContentManager.add_video_lecture(
                    int(content_id), url, dur, video_quality=quality)
                print(f"\nVideo added (ID: {vid})")

            elif choice == '2':
                conn = get_connection()
                course = _pick_lms_course(conn.cursor(), "Select course")
                if not course: conn.close(); continue
                cursor = conn.cursor()
                cursor.execute("""
                SELECT v.video_id, c.title, v.video_url, v.duration_minutes,
                       v.view_count, v.video_quality
                FROM lms_video_lectures v
                JOIN lms_course_content c ON v.content_id = c.content_id
                WHERE c.lms_course_id = ?
                ORDER BY c.content_order
                """, (course[0],))
                videos = cursor.fetchall()
                conn.close()

                if not videos:
                    print("No videos found.")
                else:
                    print(f"\n{'ID':<5} {'Title':<30} {'Duration':<10} {'Views':<8} {'Quality':<8}")
                    print("-"*61)
                    for v in videos:
                        print(f"{v[0]:<5} {(v[1] or '')[:30]:<30} {v[2] or 0:<10} {v[3] or 0:<8} {v[4] or '':<8}")

        except Exception as e:
            print(f"Error: {e}")

        input("\nPress Enter to continue...")


# ---------------------------------------------------------------------------
# 4. Discussion Forums CLI
# ---------------------------------------------------------------------------

def _cli_discussion_forums(auth):
    user_id = auth.current_user.get('username', 'system') if isinstance(auth.current_user, dict) else str(auth.current_user)

    while True:
        print("\n" + "-"*40)
        print("Discussion Forums")
        print("-"*40)
        print("1. Create forum")
        print("2. View forums for a course")
        print("3. View posts in a forum")
        print("4. Add a post")
        print("0. Back")

        choice = input("Choice: ").strip()
        if choice == '0' or not choice:
            return

        try:
            if choice == '1':
                conn = get_connection()
                course = _pick_lms_course(conn.cursor(), "Select course")
                conn.close()
                if not course: continue
                topic = input("Forum topic: ").strip()
                if not topic: continue
                desc = input("Description: ").strip()
                pinned = input("Pin this forum? (y/n) [n]: ").strip().lower() == 'y'
                fid = LMSDiscussionManager.create_forum(
                    course[0], topic, desc, user_id, pinned)
                print(f"\nForum created (ID: {fid})")

            elif choice == '2':
                conn = get_connection()
                course = _pick_lms_course(conn.cursor(), "Select course")
                if not course: conn.close(); continue
                cursor = conn.cursor()
                cursor.execute("""
                SELECT forum_id, topic, description, created_by, is_pinned, created_at
                FROM lms_discussion_forums WHERE lms_course_id = ?
                ORDER BY is_pinned DESC, created_at DESC
                """, (course[0],))
                forums = cursor.fetchall()
                conn.close()

                if not forums:
                    print("No forums found.")
                else:
                    print(f"\n{'ID':<5} {'Topic':<30} {'By':<15} {'Pinned':<7}")
                    print("-"*57)
                    for f in forums:
                        pin = "Yes" if f[4] else ""
                        print(f"{f[0]:<5} {(f[1] or '')[:30]:<30} {(f[3] or '')[:15]:<15} {pin:<7}")

            elif choice == '3':
                fid = input("Forum ID: ").strip()
                if not fid: continue
                posts = LMSDiscussionManager.get_forum_posts(int(fid))
                if not posts:
                    print("No posts found.")
                else:
                    for p in posts:
                        reply = f"  (reply to #{p.get('parent_post_id')})" if p.get('parent_post_id') else ""
                        print(f"\n  #{p['post_id']} by {p.get('user_id','?')}{reply} — {p.get('created_at','')}")
                        print(f"  {p.get('content','')}")
                        print(f"  Likes: {p.get('likes_count', 0)}")

            elif choice == '4':
                fid = input("Forum ID: ").strip()
                if not fid: continue
                content = input("Your post: ").strip()
                if not content: continue
                reply = input("Reply to post ID (or Enter for new post): ").strip()
                parent = int(reply) if reply.isdigit() else None
                pid = LMSDiscussionManager.add_post(int(fid), user_id, content, parent)
                print(f"\nPost added (ID: {pid})")

        except Exception as e:
            print(f"Error: {e}")

        input("\nPress Enter to continue...")


# ---------------------------------------------------------------------------
# 5. Quizzes & Assessments CLI
# ---------------------------------------------------------------------------

def _cli_quizzes(auth):
    user_id = auth.current_user.get('username', 'system') if isinstance(auth.current_user, dict) else str(auth.current_user)

    while True:
        print("\n" + "-"*40)
        print("Quizzes & Assessments")
        print("-"*40)
        print("1. Create quiz")
        print("2. Add question to quiz")
        print("3. List quizzes for a course")
        print("4. Take a quiz")
        print("5. View quiz results")
        print("0. Back")

        choice = input("Choice: ").strip()
        if choice == '0' or not choice:
            return

        try:
            if choice == '1':
                conn = get_connection()
                course = _pick_lms_course(conn.cursor(), "Select course")
                conn.close()
                if not course: continue
                title = input("Quiz title: ").strip()
                if not title: continue
                desc = input("Description: ").strip()
                dur = input("Duration (minutes) [60]: ").strip()
                dur = int(dur) if dur.isdigit() else 60
                passing = input("Passing score % [70]: ").strip()
                passing = float(passing) if passing else 70.0
                attempts = input("Max attempts [1]: ").strip()
                attempts = int(attempts) if attempts.isdigit() else 1

                qid = LMSQuizManager.create_quiz(
                    course[0], title, desc, dur, passing, attempts)
                print(f"\nQuiz created (ID: {qid})")

            elif choice == '2':
                qid = input("Quiz ID: ").strip()
                if not qid: continue
                text = input("Question text: ").strip()
                if not text: continue
                qtypes = ["multiple_choice", "true_false", "short_answer"]
                print("Question types: 1. Multiple Choice  2. True/False  3. Short Answer")
                qt = input("Type [1]: ").strip()
                qtype = qtypes[int(qt)-1] if qt.isdigit() and 1 <= int(qt) <= 3 else "multiple_choice"

                if qtype == "multiple_choice":
                    opts = input("Options (comma-separated): ").strip()
                else:
                    opts = ""
                answer = input("Correct answer: ").strip()
                pts = input("Points [1]: ").strip()
                pts = int(pts) if pts.isdigit() else 1
                explanation = input("Explanation (optional): ").strip()

                quid = LMSQuizManager.add_question(
                    int(qid), text, qtype, answer, pts, opts, explanation)
                print(f"\nQuestion added (ID: {quid})")

            elif choice == '3':
                conn = get_connection()
                course = _pick_lms_course(conn.cursor(), "Select course")
                if not course: conn.close(); continue
                cursor = conn.cursor()
                cursor.execute("""
                SELECT quiz_id, title, duration_minutes, passing_score, max_attempts, is_published
                FROM lms_quizzes WHERE lms_course_id = ?
                ORDER BY quiz_id
                """, (course[0],))
                quizzes = cursor.fetchall()
                conn.close()

                if not quizzes:
                    print("No quizzes found.")
                else:
                    print(f"\n{'ID':<5} {'Title':<30} {'Duration':<10} {'Pass %':<8} {'Attempts':<9} {'Status':<8}")
                    print("-"*70)
                    for q in quizzes:
                        pub = "Live" if q[5] else "Draft"
                        print(f"{q[0]:<5} {(q[1] or '')[:30]:<30} {q[2]:<10} {q[3]:<8} {q[4]:<9} {pub:<8}")

            elif choice == '4':
                qid = input("Quiz ID to take: ").strip()
                if not qid: continue
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT question_id, question_text, question_type, options, points FROM lms_quiz_questions WHERE quiz_id = ? ORDER BY question_id", (int(qid),))
                questions = cursor.fetchall()
                conn.close()

                if not questions:
                    print("No questions in this quiz."); continue

                print(f"\n--- Quiz ({len(questions)} questions) ---\n")
                answers = {}
                for q in questions:
                    print(f"Q{q[0]} ({q[4]} pts): {q[1]}")
                    if q[3]:  # has options
                        for opt in q[3].split(','):
                            print(f"    - {opt.strip()}")
                    ans = input("Your answer: ").strip()
                    answers[q[0]] = ans

                sid, score = LMSQuizManager.submit_quiz(int(qid), user_id, answers, 0)
                print(f"\nSubmitted! Score: {score:.1f}%")

            elif choice == '5':
                qid = input("Quiz ID: ").strip()
                if not qid: continue
                student = input(f"Student ID [{user_id}]: ").strip() or user_id
                results = LMSQuizManager.get_quiz_results(int(qid), student)
                if not results:
                    print("No results found.")
                else:
                    print(f"\n{'Attempt':<8} {'Score':<8} {'Time':<8}")
                    print("-"*24)
                    for r in results:
                        print(f"{r.get('attempt_number',''):<8} {r.get('score',0):.1f}%  {r.get('time_taken_minutes',0):<8}")

        except Exception as e:
            print(f"Error: {e}")

        input("\nPress Enter to continue...")


# ---------------------------------------------------------------------------
# 6. Gradebook CLI
# ---------------------------------------------------------------------------

def _cli_gradebook(auth):
    while True:
        print("\n" + "-"*40)
        print("Gradebook")
        print("-"*40)
        print("1. Add grade entry")
        print("2. View student grades")
        print("3. Calculate course grade")
        print("0. Back")

        choice = input("Choice: ").strip()
        if choice == '0' or not choice:
            return

        try:
            if choice == '1':
                conn = get_connection()
                course = _pick_lms_course(conn.cursor(), "Select course")
                conn.close()
                if not course: continue
                student = input("Student ID: ").strip()
                if not student: continue
                atype = input("Assignment type (quiz/assignment/exam/project): ").strip() or "assignment"
                aid = input("Assignment ID: ").strip()
                aid = int(aid) if aid.isdigit() else 0
                score = input("Score: ").strip()
                score = float(score) if score else 0.0
                max_score = input("Max score: ").strip()
                max_score = float(max_score) if max_score else 100.0
                weight = input("Weight [1.0]: ").strip()
                weight = float(weight) if weight else 1.0
                feedback = input("Feedback (optional): ").strip()
                grader = auth.current_user.get('username', 'system') if isinstance(auth.current_user, dict) else 'system'

                eid = LMSGradebookManager.add_grade_entry(
                    course[0], student, atype, aid, score, max_score, weight, feedback, grader)
                print(f"\nGrade entry added (ID: {eid})")

            elif choice == '2':
                conn = get_connection()
                course = _pick_lms_course(conn.cursor(), "Select course")
                conn.close()
                if not course: continue
                student = input("Student ID: ").strip()
                if not student: continue
                grades = LMSGradebookManager.get_student_grades(course[0], student)
                if not grades:
                    print("No grades found.")
                else:
                    print(f"\n{'Type':<12} {'Score':<12} {'Weight':<8} {'Feedback':<25}")
                    print("-"*57)
                    for g in grades:
                        score_str = f"{g.get('score',0)}/{g.get('max_score',0)}"
                        print(f"{g.get('assignment_type',''):<12} {score_str:<12} {g.get('weight',1):<8} {(g.get('feedback','') or '')[:25]}")

            elif choice == '3':
                conn = get_connection()
                course = _pick_lms_course(conn.cursor(), "Select course")
                conn.close()
                if not course: continue
                student = input("Student ID: ").strip()
                if not student: continue
                grade = LMSGradebookManager.calculate_course_grade(course[0], student)
                print(f"\nOverall course grade: {grade:.1f}%")

        except Exception as e:
            print(f"Error: {e}")

        input("\nPress Enter to continue...")


# ---------------------------------------------------------------------------
# 7. Student Progress CLI
# ---------------------------------------------------------------------------

def _cli_progress_tracking(auth):
    while True:
        print("\n" + "-"*40)
        print("Student Progress Tracking")
        print("-"*40)
        print("1. View enrolled students")
        print("2. View student's grades summary")
        print("3. View quiz history for student")
        print("0. Back")

        choice = input("Choice: ").strip()
        if choice == '0' or not choice:
            return

        try:
            if choice == '1':
                conn = get_connection()
                course = _pick_lms_course(conn.cursor(), "Select course")
                if not course: conn.close(); continue
                cursor = conn.cursor()
                cursor.execute("""
                SELECT e.student_id, e.enrollment_date, e.status
                FROM lms_student_enrollment e
                WHERE e.lms_course_id = ?
                ORDER BY e.enrollment_date
                """, (course[0],))
                enrollments = cursor.fetchall()
                conn.close()

                if not enrollments:
                    print("No students enrolled.")
                else:
                    print(f"\n{'Student ID':<15} {'Enrolled':<20} {'Status':<10}")
                    print("-"*45)
                    for e in enrollments:
                        print(f"{e[0]:<15} {(e[1] or '')[:20]:<20} {e[2] or 'active':<10}")

            elif choice == '2':
                conn = get_connection()
                course = _pick_lms_course(conn.cursor(), "Select course")
                conn.close()
                if not course: continue
                student = input("Student ID: ").strip()
                if not student: continue

                grades = LMSGradebookManager.get_student_grades(course[0], student)
                overall = LMSGradebookManager.calculate_course_grade(course[0], student)

                if not grades:
                    print("No grades found for this student.")
                else:
                    print(f"\n{'Type':<12} {'Score':<12} {'Weight':<8} {'Date':<20}")
                    print("-"*52)
                    for g in grades:
                        score_str = f"{g.get('score',0)}/{g.get('max_score',0)}"
                        print(f"{g.get('assignment_type',''):<12} {score_str:<12} {g.get('weight',1):<8} {(g.get('graded_at','') or '')[:20]}")
                    print(f"\nOverall grade: {overall:.1f}%")

            elif choice == '3':
                conn = get_connection()
                course = _pick_lms_course(conn.cursor(), "Select course")
                if not course: conn.close(); continue
                student = input("Student ID: ").strip()
                if not student: conn.close(); continue
                cursor = conn.cursor()
                cursor.execute("""
                SELECT q.title, s.attempt_number, s.score, s.time_taken_minutes, s.submitted_at
                FROM lms_quiz_submissions s
                JOIN lms_quizzes q ON s.quiz_id = q.quiz_id
                WHERE q.lms_course_id = ? AND s.student_id = ?
                ORDER BY s.submitted_at DESC
                """, (course[0], student))
                subs = cursor.fetchall()
                conn.close()

                if not subs:
                    print("No quiz submissions found.")
                else:
                    print(f"\n{'Quiz':<25} {'Attempt':<8} {'Score':<8} {'Time':<8} {'Date':<20}")
                    print("-"*69)
                    for s in subs:
                        print(f"{(s[0] or '')[:25]:<25} {s[1]:<8} {s[2]:.1f}%  {s[3]:<8} {(s[4] or '')[:20]}")

        except Exception as e:
            print(f"Error: {e}")

        input("\nPress Enter to continue...")


# ---------------------------------------------------------------------------
# Main LMS menu
# ---------------------------------------------------------------------------

def _switch_to_lms_gui(auth):
    """Switch from LMS CLI to LMS GUI."""
    try:
        import tkinter as tk
        from education_system.platform.features.lms.lms_gui import LMSFrame
        print("\nLaunching LMS GUI...")
        root = tk.Tk()
        root.title("Learning Management System")
        root.geometry("1200x800")
        # Determine role
        role = 'student'
        if auth and auth.current_user:
            role = auth.current_user.get('role', 'student').lower()
            if role in ('admin', 'administrator', 'instructor'):
                role = 'staff'
        frame = LMSFrame(root, role=role)
        frame.pack(fill=tk.BOTH, expand=True)
        root.mainloop()
    except ImportError:
        # Try the university-specific LMS tab
        try:
            import tkinter as tk
            from education_system.systems.university.interfaces.gui.academics.course_management_gui import CourseManagementGUI
            print("\nLaunching Course Management GUI (with LMS tab)...")
            root = tk.Tk()
            root.title("Course Management — LMS")
            root.geometry("1200x800")
            app = CourseManagementGUI(root, auth_system=auth)
            root.mainloop()
        except Exception as e2:
            print(f"\nLMS GUI not available: {e2}")
            input("Press Enter to continue...")
    except Exception as e:
        print(f"\nError launching LMS GUI: {e}")
        input("Press Enter to continue...")


def display_lms_menu(auth):
    """Display the LMS (Learning Management System) CLI menu"""
    # Ensure LMS tables exist
    try:
        from education_system.systems.university.domain.academics.services.lms.db_schema import initialize_lms_database
        initialize_lms_database()
    except Exception:
        pass

    while True:
        print("\n" + "="*60)
        print(f"    {get_text('lms.title', default='LMS (LEARNING MANAGEMENT SYSTEM)')}")
        print("="*60)
        print(f"  1. {get_text('lms.menu.manage_courses', default='Manage Courses')}")
        print(f"  2. {get_text('lms.menu.content_mgmt', default='Course Content Management')}")
        print(f"  3. {get_text('lms.menu.video_lectures', default='Video Lectures')}")
        print(f"  4. {get_text('lms.menu.discussion_forums', default='Discussion Forums')}")
        print(f"  5. {get_text('lms.menu.quizzes', default='Quizzes & Assessments')}")
        print(f"  6. {get_text('lms.menu.gradebook', default='Gradebook')}")
        print(f"  7. {get_text('lms.menu.progress_tracking', default='Student Progress Tracking')}")
        print(f"  8. {get_text('lms.menu.language', default='Language')}")
        print("  9. Switch to GUI")
        print(f"  0. {get_text('lms.menu.return_main', default='Return to Main Menu')}")
        print("="*60)

        try:
            choice = input(f"\n{get_text('lms.enter_choice', default='Enter your choice')} (0-9): ").strip()
            if choice == '0' or not choice:
                break
            elif choice == '1':
                _cli_manage_courses(auth)
            elif choice == '2':
                _cli_content_management(auth)
            elif choice == '3':
                _cli_video_lectures(auth)
            elif choice == '4':
                _cli_discussion_forums(auth)
            elif choice == '5':
                _cli_quizzes(auth)
            elif choice == '6':
                _cli_gradebook(auth)
            elif choice == '7':
                _cli_progress_tracking(auth)
            elif choice == '8':
                display_language_menu_option()
            elif choice == '9':
                _switch_to_lms_gui(auth)
                return
            else:
                print(get_text('lms.invalid_choice', default='Invalid choice.'))
        except (KeyboardInterrupt, EOFError):
            break
        except Exception as e:
            print(f"Error: {e}")
            input("Press Enter to continue...")


__all__ = [
    'LMSCourseManager',
    'LMSContentManager',
    'LMSDiscussionManager',
    'LMSQuizManager',
    'LMSGradebookManager',
    'display_lms_menu',
]
