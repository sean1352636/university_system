"""Database connection and student profile loading."""

import json
from typing import Dict, List, Optional

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


# ---------------------------------------------------------------------------
# Student Services queries
# ---------------------------------------------------------------------------

def get_fee_balance(chatbot, student_id: str) -> Dict:
    """Get student fee balance and payment deadlines."""
    conn = connect_to_db(chatbot.db_path)
    if not conn:
        return {"error": "Database unavailable"}
    try:
        cursor = conn.cursor()
        # Try student_fees / invoices table
        for table, cols in [
            ("student_fees", "amount, paid_amount, due_date, status, fee_type"),
            ("invoices", "total_amount, paid_amount, due_date, status, description"),
        ]:
            try:
                cursor.execute(f"""
                    SELECT {cols} FROM {table}
                    WHERE student_id = ? ORDER BY due_date DESC LIMIT 10
                """, (student_id,))
                rows = cursor.fetchall()
                if rows:
                    items = []
                    for r in rows:
                        items.append({
                            "amount": r[0], "paid": r[1], "due_date": r[2],
                            "status": r[3], "description": r[4]
                        })
                    return {"fees": items}
            except Exception:
                continue
        return {"fees": []}
    finally:
        conn.close()


def get_transcript_requests(chatbot, student_id: str) -> List[Dict]:
    """Get existing transcript / certificate requests."""
    conn = connect_to_db(chatbot.db_path)
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        for table in ("transcript_requests", "document_requests"):
            try:
                cursor.execute(f"""
                    SELECT id, request_type, status, request_date
                    FROM {table} WHERE student_id = ?
                    ORDER BY request_date DESC LIMIT 10
                """, (student_id,))
                return [{"id": r[0], "type": r[1], "status": r[2], "date": r[3]}
                        for r in cursor.fetchall()]
            except Exception:
                continue
        return []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Academic Support queries
# ---------------------------------------------------------------------------

def get_upcoming_deadlines(chatbot, student_id: str) -> List[Dict]:
    """Get upcoming assignment and exam deadlines for a student."""
    conn = connect_to_db(chatbot.db_path)
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.title, a.due_date, a.module_code, a.assignment_type
            FROM assignments a
            WHERE a.module_code IN (
                SELECT module_code FROM student_modules
                WHERE student_id = ? AND LOWER(status) = 'enrolled'
            )
            AND a.due_date >= date('now')
            ORDER BY a.due_date ASC LIMIT 15
        """, (student_id,))
        return [{"title": r[0], "due": r[1], "module": r[2], "type": r[3]}
                for r in cursor.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


def get_exam_schedule(chatbot, student_id: str) -> List[Dict]:
    """Get exam schedule with room locations."""
    conn = connect_to_db(chatbot.db_path)
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        for query in [
            """SELECT e.module_code, e.exam_date, e.start_time, e.end_time,
                      r.room_number, r.building
               FROM exams e
               LEFT JOIN rooms r ON e.room_id = r.id
               WHERE e.module_code IN (
                   SELECT module_code FROM student_modules
                   WHERE student_id = ? AND LOWER(status) = 'enrolled'
               ) AND e.exam_date >= date('now')
               ORDER BY e.exam_date ASC""",
            """SELECT module_code, exam_date, start_time, end_time, location, ''
               FROM exam_schedule
               WHERE module_code IN (
                   SELECT module_code FROM student_modules
                   WHERE student_id = ? AND LOWER(status) = 'enrolled'
               ) AND exam_date >= date('now')
               ORDER BY exam_date ASC""",
        ]:
            try:
                cursor.execute(query, (student_id,))
                rows = cursor.fetchall()
                if rows:
                    return [{"module": r[0], "date": r[1], "start": r[2],
                             "end": r[3], "room": r[4], "building": r[5]}
                            for r in rows]
            except Exception:
                continue
        return []
    finally:
        conn.close()


def search_library(chatbot, query: str) -> List[Dict]:
    """Search library catalogue."""
    conn = connect_to_db(chatbot.db_path)
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        like_q = f"%{query}%"
        cursor.execute("""
            SELECT book_id, title, author, isbn, available_copies, total_copies
            FROM books
            WHERE title LIKE ? OR author LIKE ? OR isbn LIKE ?
            ORDER BY title LIMIT 15
        """, (like_q, like_q, like_q))
        return [{"id": r[0], "title": r[1], "author": r[2], "isbn": r[3],
                 "available": r[4], "total": r[5]}
                for r in cursor.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


def get_academic_calendar(chatbot) -> List[Dict]:
    """Get academic calendar events."""
    conn = connect_to_db(chatbot.db_path)
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        for table in ("academic_calendar", "calendar_events"):
            try:
                cursor.execute(f"""
                    SELECT event_name, start_date, end_date, event_type
                    FROM {table}
                    WHERE start_date >= date('now', '-30 days')
                    ORDER BY start_date ASC LIMIT 20
                """)
                rows = cursor.fetchall()
                if rows:
                    return [{"name": r[0], "start": r[1], "end": r[2], "type": r[3]}
                            for r in rows]
            except Exception:
                continue
        return []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Admissions queries
# ---------------------------------------------------------------------------

def get_application_status(chatbot, identifier: str) -> List[Dict]:
    """Look up application status by student_id or email."""
    conn = connect_to_db(chatbot.db_path)
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        for table in ("applications", "admissions"):
            try:
                cursor.execute(f"""
                    SELECT id, programme, status, submitted_date, decision_date
                    FROM {table}
                    WHERE applicant_id = ? OR email = ?
                    ORDER BY submitted_date DESC LIMIT 5
                """, (identifier, identifier))
                rows = cursor.fetchall()
                if rows:
                    return [{"id": r[0], "programme": r[1], "status": r[2],
                             "submitted": r[3], "decision": r[4]}
                            for r in rows]
            except Exception:
                continue
        return []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Administrative queries
# ---------------------------------------------------------------------------

def search_staff_directory(chatbot, query: str) -> List[Dict]:
    """Search staff directory by name or department."""
    conn = connect_to_db(chatbot.db_path)
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        like_q = f"%{query}%"
        for sql in [
            """SELECT name, email, department, role, phone, office_location
               FROM staff_directory
               WHERE name LIKE ? OR department LIKE ? OR role LIKE ?
               ORDER BY name LIMIT 10""",
            """SELECT first_name || ' ' || last_name, email, department, role, phone, ''
               FROM staff
               WHERE first_name LIKE ? OR last_name LIKE ? OR department LIKE ?
               ORDER BY last_name LIMIT 10""",
        ]:
            try:
                cursor.execute(sql, (like_q, like_q, like_q))
                rows = cursor.fetchall()
                if rows:
                    return [{"name": r[0], "email": r[1], "department": r[2],
                             "role": r[3], "phone": r[4], "office": r[5]}
                            for r in rows]
            except Exception:
                continue
        return []
    finally:
        conn.close()


def get_room_bookings(chatbot, student_id: str) -> List[Dict]:
    """Get room/facility bookings for a user."""
    conn = connect_to_db(chatbot.db_path)
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        for table in ("room_bookings", "facility_bookings"):
            try:
                cursor.execute(f"""
                    SELECT id, room_name, booking_date, start_time, end_time, status
                    FROM {table}
                    WHERE user_id = ? AND booking_date >= date('now')
                    ORDER BY booking_date ASC LIMIT 10
                """, (student_id,))
                rows = cursor.fetchall()
                if rows:
                    return [{"id": r[0], "room": r[1], "date": r[2],
                             "start": r[3], "end": r[4], "status": r[5]}
                            for r in rows]
            except Exception:
                continue
        return []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Wellbeing & Campus Life queries
# ---------------------------------------------------------------------------

def get_clubs_and_societies(chatbot) -> List[Dict]:
    """Get list of student clubs and societies."""
    conn = connect_to_db(chatbot.db_path)
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        for table in ("clubs", "student_clubs", "societies"):
            try:
                cursor.execute(f"""
                    SELECT name, description, category, contact_email
                    FROM {table}
                    WHERE COALESCE(is_active, 1) = 1
                    ORDER BY name LIMIT 20
                """)
                rows = cursor.fetchall()
                if rows:
                    return [{"name": r[0], "description": r[1],
                             "category": r[2], "contact": r[3]}
                            for r in rows]
            except Exception:
                continue
        return []
    finally:
        conn.close()


def get_transport_schedule(chatbot) -> List[Dict]:
    """Get campus shuttle / transport schedules."""
    conn = connect_to_db(chatbot.db_path)
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        for table in ("transport_schedule", "shuttle_schedule"):
            try:
                cursor.execute(f"""
                    SELECT route_name, departure_time, arrival_time,
                           departure_location, arrival_location
                    FROM {table}
                    ORDER BY departure_time LIMIT 20
                """)
                rows = cursor.fetchall()
                if rows:
                    return [{"route": r[0], "depart_time": r[1],
                             "arrive_time": r[2], "from": r[3], "to": r[4]}
                            for r in rows]
            except Exception:
                continue
        return []
    finally:
        conn.close()


def get_lost_found_items(chatbot, query: str = "") -> List[Dict]:
    """Search lost and found items."""
    conn = connect_to_db(chatbot.db_path)
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        for table in ("lost_found", "lost_and_found"):
            try:
                if query:
                    like_q = f"%{query}%"
                    cursor.execute(f"""
                        SELECT id, item_description, location_found, date_reported, status
                        FROM {table}
                        WHERE item_description LIKE ? AND status != 'claimed'
                        ORDER BY date_reported DESC LIMIT 10
                    """, (like_q,))
                else:
                    cursor.execute(f"""
                        SELECT id, item_description, location_found, date_reported, status
                        FROM {table}
                        WHERE status != 'claimed'
                        ORDER BY date_reported DESC LIMIT 10
                    """)
                rows = cursor.fetchall()
                if rows:
                    return [{"id": r[0], "description": r[1], "location": r[2],
                             "date": r[3], "status": r[4]}
                            for r in rows]
            except Exception:
                continue
        return []
    finally:
        conn.close()


def get_mental_health_resources(chatbot) -> List[Dict]:
    """Get mental health and wellbeing resources."""
    # These are typically static resources, not DB-driven
    return [
        {"name": "University Counselling Service",
         "contact": "counselling@university.ac.uk",
         "description": "Free, confidential counselling for all students. Book via the student portal."},
        {"name": "Student Wellbeing Centre",
         "contact": "wellbeing@university.ac.uk",
         "description": "Drop-in support, workshops, and group sessions."},
        {"name": "24/7 Crisis Helpline",
         "contact": "0800-XXX-XXXX",
         "description": "Immediate support available around the clock."},
        {"name": "Disability & Inclusion Service",
         "contact": "disability@university.ac.uk",
         "description": "Support for students with disabilities, learning differences, or mental health conditions."},
        {"name": "Peer Support Network",
         "contact": "peersupport@university.ac.uk",
         "description": "Trained student volunteers offering peer-to-peer support."},
    ]
