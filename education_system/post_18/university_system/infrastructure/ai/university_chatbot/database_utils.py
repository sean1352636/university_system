"""Database connection and student profile loading."""

import json
from typing import Dict, List, Optional

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.infrastructure.ai.university_chatbot.models import StudentProfile


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
            SELECT student_id, email_address, first_name, last_name, course, year
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

        # The optional student_profiles table may not exist in every DB; don't
        # let a missing table sink the whole profile load.
        interests = []
        try:
            cursor.execute("""
                SELECT interests FROM student_profiles
                WHERE student_id = ?
            """, (student_id,))
            interests_data = cursor.fetchone()
            interests = json.loads(interests_data[0]) if interests_data and interests_data[0] else []
        except Exception:
            interests = []

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
            # calculate_gpa returns an {"error": ...} dict for students with no
            # graded modules, so default to 0.0 rather than KeyError'ing.
            gpa=(gpa_info.get("gpa", 0.0) if isinstance(gpa_info, dict) else 0.0),
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
        # Primary: student_fees joined to fee_types for the human-readable name.
        # The table has no paid_amount column, so 'status' conveys paid/unpaid.
        queries = [
            """SELECT sf.amount, NULL, sf.due_date, sf.status,
                      COALESCE(ft.fee_name, 'Fee')
               FROM student_fees sf
               LEFT JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
               WHERE sf.student_id = ? ORDER BY sf.due_date DESC LIMIT 10""",
            """SELECT total_amount, paid_amount, due_date, status, description
               FROM invoices
               WHERE student_id = ? ORDER BY due_date DESC LIMIT 10""",
        ]
        for sql in queries:
            try:
                cursor.execute(sql, (student_id,))
                rows = cursor.fetchall()
                if rows:
                    return {"fees": [
                        {"amount": r[0], "paid": r[1], "due_date": r[2],
                         "status": r[3], "description": r[4]}
                        for r in rows
                    ]}
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
        # Real schemas differ per table, so query each with its own columns.
        queries = [
            ("""SELECT id, 'Transcript', status, COALESCE(generated_at, created_at)
                FROM transcript_requests WHERE student_id = ?
                ORDER BY COALESCE(generated_at, created_at) DESC LIMIT 10"""),
            ("""SELECT id, document_type, status, requested_at
                FROM document_requests WHERE student_id = ?
                ORDER BY requested_at DESC LIMIT 10"""),
        ]
        for sql in queries:
            try:
                cursor.execute(sql, (student_id,))
                rows = cursor.fetchall()
                if rows:
                    return [{"id": r[0], "type": r[1], "status": r[2], "date": r[3]}
                            for r in rows]
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
            # Actual exams table: `date` (not exam_date) and a text `room`
            # column (no room_id FK). Compare on the date prefix so timestamped
            # values like '2026-06-17 09:00' are still matched.
            """SELECT module_code, date, start_time, end_time, room, ''
               FROM exams
               WHERE module_code IN (
                   SELECT module_code FROM student_modules
                   WHERE student_id = ? AND LOWER(status) = 'enrolled'
               ) AND substr(date, 1, 10) >= date('now')
               ORDER BY date ASC""",
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
        # books has `quantity` and `status` (no available_copies/total_copies);
        # treat an 'available' status as one available copy of `quantity`.
        cursor.execute("""
            SELECT book_id, title, author, isbn,
                   CASE WHEN LOWER(COALESCE(status,'available'))='available'
                        THEN COALESCE(quantity, 1) ELSE 0 END,
                   COALESCE(quantity, 1)
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
    """Get upcoming academic calendar events.

    Reads the single canonical ``academic_calendar_events`` table (exams,
    assignment and assessment deadlines, etc.) plus term boundaries from
    ``semesters``.
    """
    conn = connect_to_db(chatbot.db_path)
    if not conn:
        return []
    events: List[Dict] = []
    try:
        cursor = conn.cursor()

        # Primary source: academic_calendar_events. ``date`` holds single-day
        # events; ``date_start``/``date_end`` hold ranged events (e.g. exams).
        try:
            cursor.execute("""
                SELECT name,
                       COALESCE(date_start, date) AS ev_start,
                       COALESCE(date_end, date_start, date) AS ev_end,
                       event_type
                FROM academic_calendar_events
                WHERE COALESCE(date_start, date) >= date('now', '-30 days')
                ORDER BY ev_start ASC LIMIT 20
            """)
            events.extend({"name": r[0], "start": r[1], "end": r[2], "type": r[3]}
                          for r in cursor.fetchall())
        except Exception as e:
            print(f"get_academic_calendar (events) error: {e}")

        # Term dates from the semesters table.
        try:
            cursor.execute("""
                SELECT name, start_date, end_date
                FROM semesters
                WHERE end_date >= date('now')
                ORDER BY start_date ASC LIMIT 6
            """)
            events.extend({"name": f"{r[0]} term", "start": r[1], "end": r[2],
                           "type": "Term"} for r in cursor.fetchall())
        except Exception as e:
            print(f"get_academic_calendar (semesters) error: {e}")

        # Combine and sort chronologically (ISO dates sort lexicographically).
        events.sort(key=lambda e: e.get("start") or "")
        return events[:20]
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
        # Actual `applications` table is keyed by student_id and has no
        # programme/decision columns; surface notes as the programme label.
        queries = [
            ("""SELECT id, COALESCE(notes, 'Application'), status, application_date, NULL
                FROM applications
                WHERE student_id = ?
                ORDER BY application_date DESC LIMIT 5""", (identifier,)),
            # Prospect-based admissions applications, matched via the prospect's
            # email or id.
            ("""SELECT aa.application_id, aa.program_applied, aa.status,
                       aa.submission_date, aa.decision_date
                FROM admission_applications aa
                LEFT JOIN admission_prospects ap ON aa.prospect_id = ap.prospect_id
                WHERE ap.email = ? OR CAST(ap.prospect_id AS TEXT) = ?
                ORDER BY aa.submission_date DESC LIMIT 5""", (identifier, identifier)),
        ]
        for sql, params in queries:
            try:
                cursor.execute(sql, params)
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
            # Actual staff table: single `name` column, role, email, phone;
            # no department/office columns.
            """SELECT name, email, '' AS department, role, phone, '' AS office
               FROM staff
               WHERE name LIKE ? OR role LIKE ? OR email LIKE ?
               ORDER BY name LIMIT 10""",
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
    """Get upcoming facility/room bookings for a user.

    Reads the ``facility_bookings`` table, matching either the textual
    ``booker_id`` (a username) or the numeric ``user_id``, so it works whether
    the caller passes a username or a numeric id.
    """
    conn = connect_to_db(chatbot.db_path)
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT booking_id, facility_name, booking_date, start_time, end_time, status
                FROM facility_bookings
                WHERE (booker_id = ? OR CAST(user_id AS TEXT) = ?)
                  AND booking_date >= date('now')
                  AND COALESCE(status, '') != 'cancelled'
                ORDER BY booking_date ASC, start_time ASC LIMIT 10
            """, (str(student_id), str(student_id)))
            rows = cursor.fetchall()
            return [{"id": r[0], "room": r[1], "date": r[2],
                     "start": r[3], "end": r[4], "status": r[5] or "confirmed"}
                    for r in rows]
        except Exception as e:
            print(f"get_room_bookings error: {e}")
            return []
    finally:
        conn.close()


def get_user_email(chatbot, username: str):
    """Return (email, display_name) for a username, or (None, username)."""
    conn = connect_to_db(chatbot.db_path)
    if not conn:
        return None, username
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT email, first_name, last_name FROM users WHERE username = ?",
            (str(username),),
        )
        row = cursor.fetchone()
        if not row:
            return None, username
        email = row[0]
        name = " ".join(p for p in (row[1], row[2]) if p) or username
        return (email or None), name
    except Exception as e:
        print(f"get_user_email error: {e}")
        return None, username
    finally:
        conn.close()


def create_facility_booking(chatbot, booker, facility_name, booking_date,
                            start_time, end_time, purpose=""):
    """Create a facility booking for ``booker`` (a username).

    Returns a dict: ``{"ok": bool, "error": str|None, "booking": {...},
    "email": str|None, "name": str}``. Performs a simple clash check against
    existing (non-cancelled) bookings for the same facility and date.
    """
    from datetime import datetime

    facility_name = (facility_name or "").strip()
    booking_date = (booking_date or "").strip()
    start_time = (start_time or "").strip()
    end_time = (end_time or "").strip()

    if not facility_name:
        return {"ok": False, "error": "Please choose a facility."}
    if not booking_date or not start_time or not end_time:
        return {"ok": False, "error": "Date, start time and end time are all required."}
    # Basic format validation.
    try:
        datetime.strptime(booking_date, "%Y-%m-%d")
        start_dt = datetime.strptime(start_time, "%H:%M")
        end_dt = datetime.strptime(end_time, "%H:%M")
    except ValueError:
        return {"ok": False, "error": "Use date YYYY-MM-DD and times HH:MM."}
    if end_dt <= start_dt:
        return {"ok": False, "error": "End time must be after start time."}

    email, name = get_user_email(chatbot, booker)

    conn = connect_to_db(chatbot.db_path)
    if not conn:
        return {"ok": False, "error": "Could not connect to the booking database."}
    try:
        cursor = conn.cursor()

        # Clash check: same facility/date with an overlapping time window.
        cursor.execute("""
            SELECT start_time, end_time FROM facility_bookings
            WHERE facility_name = ? AND booking_date = ?
              AND COALESCE(status, '') != 'cancelled'
        """, (facility_name, booking_date))
        for existing_start, existing_end in cursor.fetchall():
            if existing_start and existing_end and start_time < existing_end and end_time > existing_start:
                return {"ok": False,
                        "error": f"{facility_name} is already booked "
                                 f"{existing_start}–{existing_end} on {booking_date}."}

        # Resolve numeric user id if available (column exists but may be NULL).
        cursor.execute("SELECT id FROM users WHERE username = ?", (str(booker),))
        row = cursor.fetchone()
        numeric_user_id = row[0] if row else None

        cursor.execute("""
            INSERT INTO facility_bookings
                (facility_name, user_id, booking_date, start_time, end_time,
                 purpose, status, booker_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'confirmed', ?, ?)
        """, (facility_name, numeric_user_id, booking_date, start_time, end_time,
              purpose or "", str(booker), datetime.now().isoformat(timespec="seconds")))
        conn.commit()
        booking_id = cursor.lastrowid

        return {
            "ok": True,
            "error": None,
            "booking": {"id": booking_id, "room": facility_name,
                        "date": booking_date, "start": start_time,
                        "end": end_time, "status": "confirmed",
                        "purpose": purpose or ""},
            "email": email,
            "name": name,
        }
    except Exception as e:
        print(f"create_facility_booking error: {e}")
        return {"ok": False, "error": f"Could not save the booking: {e}"}
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
        # Column names differ per table (club_name vs name); no contact_email.
        queries = [
            """SELECT club_name, description, category, ''
               FROM student_clubs
               WHERE LOWER(COALESCE(status, 'active')) = 'active'
               ORDER BY club_name LIMIT 20""",
            """SELECT name, description, category, ''
               FROM student_union_clubs
               WHERE LOWER(COALESCE(status, 'active')) = 'active'
               ORDER BY name LIMIT 20""",
        ]
        for sql in queries:
            try:
                cursor.execute(sql)
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
        queries = [
            # Per-student transport allocations.
            """SELECT route_name, pickup_time, dropoff_time,
                      pickup_location, dropoff_location
               FROM transportation
               WHERE COALESCE(active, 1) = 1
               ORDER BY pickup_time LIMIT 20""",
            # Campus shuttle routes.
            """SELECT route_name, start_time, end_time, '', description
               FROM shuttle_routes
               WHERE COALESCE(is_active, 1) = 1
               ORDER BY start_time LIMIT 20""",
        ]
        for sql in queries:
            try:
                cursor.execute(sql)
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
        # lost_found uses `found_date` and a `claimed` flag (no date_reported).
        try:
            if query:
                like_q = f"%{query}%"
                cursor.execute("""
                    SELECT id, item_description, location_found, found_date,
                           COALESCE(status, 'unclaimed')
                    FROM lost_found
                    WHERE item_description LIKE ? AND COALESCE(claimed, 0) = 0
                    ORDER BY found_date DESC LIMIT 10
                """, (like_q,))
            else:
                cursor.execute("""
                    SELECT id, item_description, location_found, found_date,
                           COALESCE(status, 'unclaimed')
                    FROM lost_found
                    WHERE COALESCE(claimed, 0) = 0
                    ORDER BY found_date DESC LIMIT 10
                """)
            return [{"id": r[0], "description": r[1], "location": r[2],
                     "date": r[3], "status": r[4]}
                    for r in cursor.fetchall()]
        except Exception as e:
            print(f"get_lost_found_items error: {e}")
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
