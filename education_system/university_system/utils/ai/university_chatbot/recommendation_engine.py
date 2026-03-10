"""Course recommendation scoring and GPA calculation."""

import json
from typing import Dict, List, Optional, Tuple

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.utils.ai.university_chatbot.models import StudentProfile


def get_course_recommendations(chatbot, student_id: str, num_recommendations: int = 5) -> List[Dict]:
    """Get personalized course recommendations"""
    student_profile = chatbot.get_student_profile(student_id)
    if not student_profile:
        return []

    conn = chatbot.connect_to_db()
    if not conn:
        return []

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT module_code, module_name, module_type, prerequisites, credits, difficulty_level
            FROM modules
            WHERE module_code NOT IN (
                SELECT module_code FROM student_modules WHERE student_id = ? AND status = 'completed'
            )
        """, (student_id,))

        available_courses = cursor.fetchall()

        recommendations = []
        for course in available_courses:
            score = calculate_course_score(course, student_profile)
            if score > 0:
                recommendations.append({
                    "course_code": course[0],
                    "course_name": course[1],
                    "type": course[2],
                    "credits": course[4],
                    "difficulty": course[5],
                    "recommendation_score": score,
                    "reasons": get_recommendation_reasons(course, student_profile)
                })

        recommendations.sort(key=lambda x: x["recommendation_score"], reverse=True)
        return recommendations[:num_recommendations]

    except Exception as e:
        print(f"Recommendation error: {e}")
        return []
    finally:
        conn.close()


def calculate_course_score(course: Tuple, student_profile: StudentProfile) -> float:
    """Calculate recommendation score for a course"""
    score = 0.0

    # Base score
    score += 1.0

    # GPA factor
    if student_profile.gpa < 2.5 and course[5] == "advanced":
        score -= 0.5
    elif student_profile.gpa > 3.5 and course[5] == "beginner":
        score -= 0.3

    # Program relevance
    if course[2] == "core" and course[2] in student_profile.program.lower():
        score += 0.8

    # Interest matching
    for interest in student_profile.interests:
        if interest.lower() in course[1].lower():
            score += 0.6

    # Prerequisites check
    if course[3]:
        prereq_courses = course[3].split(',')
        for prereq in prereq_courses:
            if prereq.strip() not in student_profile.completed_courses:
                score = 0
                break

    # Workload consideration
    current_credits = len(student_profile.current_courses) * 3
    if current_credits + course[4] > 18:
        score -= 0.4

    return max(0, score)


def get_recommendation_reasons(course: Tuple, student_profile: StudentProfile) -> List[str]:
    """Get reasons for course recommendation"""
    reasons = []

    if course[2] == "core":
        reasons.append("Required for your program")

    for interest in student_profile.interests:
        if interest.lower() in course[1].lower():
            reasons.append(f"Matches your interest in {interest}")

    if student_profile.gpa > 3.5 and course[5] == "advanced":
        reasons.append("You're performing well academically")

    if len(student_profile.current_courses) < 4:
        reasons.append("Good addition to your current course load")

    return reasons


def calculate_gpa(chatbot, student_id: str, semester: Optional[str] = None) -> Dict:
    """Calculate GPA for student"""
    conn = chatbot.connect_to_db()
    if not conn:
        return {"error": "Database connection failed"}

    try:
        cursor = conn.cursor()

        if semester:
            cursor.execute("""
                SELECT grade, credits FROM student_grades
                WHERE student_id = ? AND semester = ?
            """, (student_id, semester))
        else:
            cursor.execute("""
                SELECT grade, credits FROM student_grades
                WHERE student_id = ?
            """, (student_id,))

        grades = cursor.fetchall()

        if not grades:
            return {"gpa": 0.0, "total_credits": 0, "grade_points": 0.0}

        grade_points_map = {'A+': 4.0, 'A': 4.0, 'A-': 3.7, 'B+': 3.3, 'B': 3.0, 'B-': 2.7,
                          'C+': 2.3, 'C': 2.0, 'C-': 1.7, 'D': 1.0, 'F': 0.0}

        total_grade_points = 0.0
        total_credits = 0

        for grade, credits in grades:
            if grade in grade_points_map:
                total_grade_points += grade_points_map[grade] * credits
                total_credits += credits

        gpa = total_grade_points / total_credits if total_credits > 0 else 0.0

        return {
            "gpa": round(gpa, 2),
            "total_credits": total_credits,
            "grade_points": round(total_grade_points, 2),
            "semester": semester
        }

    except Exception as e:
        return {"error": f"GPA calculation error: {e}"}
    finally:
        conn.close()
