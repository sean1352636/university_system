"""Database connection and student profile loading."""

import json
from typing import Optional

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.utils.ai.university_chatbot.models import StudentProfile


def connect_to_db(db_path: str):
    """Connect to the database"""
    try:
        conn = sqlite3.connect(db_path)
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        return None


def get_student_id_for_user(chatbot, username: str) -> Optional[str]:
    """Get student ID associated with a username"""
    if not chatbot.auth_system:
        return None

    try:
        conn = connect_to_db(chatbot.db_path)
        if not conn:
            return None

        cursor = conn.cursor()

        cursor.execute("""
            SELECT u.student_id
            FROM users u
            JOIN user_accounts ua ON u.id = ua.user_id
            WHERE ua.username = ?
        """, (username,))

        result = cursor.fetchone()
        conn.close()

        return result[0] if result and result[0] else None

    except Exception as e:
        print(f"Error getting student ID for user {username}: {e}")
        return None


def get_student_profile(chatbot, student_id: str) -> Optional[StudentProfile]:
    """Get comprehensive student profile"""
    conn = connect_to_db(chatbot.db_path)
    if not conn:
        return None

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT student_id, email, first_name, last_name, course, year
            FROM students
            WHERE student_id = ?
        """, (student_id,))

        student_data = cursor.fetchone()
        if not student_data:
            return None

        gpa_info = chatbot.calculate_gpa(student_id)

        cursor.execute("""
            SELECT module_code FROM student_modules
            WHERE student_id = ? AND status = 'completed'
        """, (student_id,))
        completed_courses = [row[0] for row in cursor.fetchall()]

        cursor.execute("""
            SELECT module_code FROM student_modules
            WHERE student_id = ? AND status = 'enrolled'
        """, (student_id,))
        current_courses = [row[0] for row in cursor.fetchall()]

        cursor.execute("""
            SELECT interests FROM student_profiles
            WHERE student_id = ?
        """, (student_id,))
        interests_data = cursor.fetchone()
        interests = json.loads(interests_data[0]) if interests_data and interests_data[0] else []

        cursor.execute("""
            SELECT COUNT(*) FROM financial_aid
            WHERE student_id = ? AND status = 'active'
        """, (student_id,))
        has_financial_aid = cursor.fetchone()[0] > 0

        return StudentProfile(
            student_id=student_data[0],
            name=f"{student_data[2]} {student_data[3]}",
            email=student_data[1],
            program=student_data[4],
            year=student_data[5],
            gpa=gpa_info["gpa"],
            completed_courses=completed_courses,
            current_courses=current_courses,
            interests=interests,
            financial_aid=has_financial_aid
        )

    except Exception as e:
        print(f"Student profile error: {e}")
        return None
    finally:
        conn.close()
