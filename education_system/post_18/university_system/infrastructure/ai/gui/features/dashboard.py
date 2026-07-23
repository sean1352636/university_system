import logging
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)


class DashboardMixin:
    """Mixin for student dashboard quick-action methods."""

    def show_my_courses(self):
        """Show user's enrolled courses with real database data"""
        try:
            context = self.get_user_context()
            courses = context.get('courses', [])

            if not courses:
                response = "You are not currently enrolled in any courses. Visit the registration page to enroll in courses."
                self.add_chat_message("Chatbot", response, "bot")
                return

            response = f"\U0001f4da **Your Enrolled Courses ({len(courses)} total):**\n\n"
            for course in courses:
                response += f"\u2022 **{course['name']}** (ID: {course['id']})\n"
                response += f"  Credits: {course.get('credits', 'N/A')}\n\n"

            response += "Would you like more details about any specific course?"

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'courses', None, details={'user': self.current_user.get('username')})

        except Exception as e:
            error_msg = f"Error fetching courses: {e}"
            self.add_chat_message("Chatbot", error_msg, "bot")

    def show_my_grades(self):
        """Show user's recent grades with real database data"""
        try:
            context = self.get_user_context()
            grades = context.get('grades', [])

            if not grades:
                response = "No grades are currently available. Grades will appear here once your instructors post them."
                self.add_chat_message("Chatbot", response, "bot")
                return

            response = f"\U0001f4ca **Your Recent Grades ({len(grades)} entries):**\n\n"
            for grade in grades:
                response += f"\u2022 **{grade['course']}**\n"
                response += f"  Grade: {grade['grade']} ({grade['points']} points)\n"
                response += f"  Posted: {grade['date']}\n\n"

            # Calculate average if possible
            try:
                numeric_grades = [g['points'] for g in grades if g['points'] is not None]
                if numeric_grades:
                    avg = sum(numeric_grades) / len(numeric_grades)
                    response += f"\n**Average: {avg:.2f} points**"
            except Exception as e:
                logger.debug(f"Error calculating grade average: {e}")

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'grades', None, details={'user': self.current_user.get('username')})

        except Exception as e:
            error_msg = f"Error fetching grades: {e}"
            self.add_chat_message("Chatbot", error_msg, "bot")

    def show_financial_aid(self):
        """Show financial aid information"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Try to get user's financial aid applications
                try:
                    cursor.execute('''
                        SELECT academic_year, status, family_income, application_date
                        FROM financial_aid_applications
                        WHERE student_id = ?
                        ORDER BY application_date DESC
                        LIMIT 5
                    ''', (self.current_user.get('username'),))
                    applications = cursor.fetchall()

                    if applications:
                        response = "\U0001f4b0 **Your Financial Aid Applications:**\n\n"
                        for app in applications:
                            response += f"\u2022 **{app[0]}**\n"
                            response += f"  Status: {app[1]}\n"
                            response += f"  Applied: {app[3]}\n\n"
                    else:
                        response = "You have no financial aid applications on record.\n\n"
                except Exception:
                    response = ""

                # Show available aid programs
                response += "**Available Financial Aid Programs:**\n\n"
                response += "\u2022 Merit Scholarships\n"
                response += "\u2022 Need-Based Grants\n"
                response += "\u2022 Student Loans\n"
                response += "\u2022 Work-Study Programs\n\n"
                response += "Visit the Financial Aid office for personalized assistance or to apply."

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'financial_aid', None, details={'user': self.current_user.get('username')})

        except Exception as e:
            error_msg = f"Error fetching financial aid info: {e}"
            self.add_chat_message("Chatbot", error_msg, "bot")

    def show_my_schedule(self):
        """Show user's class schedule"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Get schedule from module_schedule (linked by module_code)
                try:
                    cursor.execute('''
                        SELECT ms.module_code, ms.day_of_week, ms.start_time, ms.end_time,
                               ms.session_type, r.room_number, r.building
                        FROM module_schedule ms
                        LEFT JOIN rooms r ON ms.room_id = r.id
                        WHERE ms.module_code IN (
                            SELECT module_code FROM student_modules
                            WHERE student_id = ? AND LOWER(status) = 'enrolled'
                        )
                        ORDER BY
                            CASE ms.day_of_week
                                WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2
                                WHEN 'Wednesday' THEN 3 WHEN 'Thursday' THEN 4
                                WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6
                                WHEN 'Sunday' THEN 7 ELSE 8
                            END,
                            ms.start_time
                    ''', (self.current_user.get('username'),))
                    schedule = cursor.fetchall()

                    if schedule:
                        response = "\U0001f4c5 **Your Class Schedule:**\n\n"
                        for item in schedule:
                            module, day, start, end, stype, room_num, building = item
                            room_str = f"{room_num or ''}"
                            if building:
                                room_str += f" ({building})" if room_str else building
                            response += f"\u2022 {module} — {stype or 'Class'}\n"
                            response += f"  Day: {day or 'TBD'}\n"
                            response += f"  Time: {start or '?'} - {end or '?'}\n"
                            response += f"  Room: {room_str or 'TBD'}\n\n"
                    else:
                        response = "No schedule information available. Your courses may not have scheduled times yet."

                except Exception as e:
                    logger.debug(f"Schedule query error: {e}")
                    # Fallback: show courses without schedule
                    context = self.get_user_context()
                    courses = context.get('courses', [])
                    if courses:
                        response = "\U0001f4c5 **Your Courses:**\n\n"
                        for course in courses:
                            response += f"\u2022 {course['name']}\n"
                        response += "\n(Detailed schedule times not yet available)"
                    else:
                        response = "No courses found. Enroll in courses to see your schedule."

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'schedule', None, details={'user': self.current_user.get('username')})

        except Exception as e:
            error_msg = f"Error fetching schedule: {e}"
            self.add_chat_message("Chatbot", error_msg, "bot")

    def _build_welcome_summary(self):
        """Build a personalized welcome summary with real data from the database."""
        role = (self.current_user or {}).get('role') if self.current_user else None
        if role == 'alumni':
            return self._build_alumni_welcome()

        username = self.current_user.get('username', 'Student') if self.current_user else 'Student'
        lines = [f"Welcome, {username}! Here's your summary:\n"]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Active course count
                try:
                    cursor.execute(
                        "SELECT COUNT(*) FROM student_modules WHERE student_id = ? AND LOWER(status) = 'enrolled'",
                        (username,))
                    count = cursor.fetchone()[0]
                    lines.append(f"Courses: {count} active enrollment{'s' if count != 1 else ''}")
                except Exception:
                    pass

                # Upcoming assignments (next 7 days, not yet submitted)
                try:
                    cursor.execute('''
                        SELECT COUNT(*) FROM assignments a
                        LEFT JOIN assignment_submissions sub
                            ON a.id = sub.assignment_id AND sub.student_id = ?
                        WHERE a.module_code IN (
                            SELECT module_code FROM student_modules WHERE student_id = ? AND LOWER(status) = 'enrolled'
                        )
                        AND a.due_date BETWEEN date('now') AND date('now', '+7 days')
                        AND sub.id IS NULL
                    ''', (username, username))
                    count = cursor.fetchone()[0]
                    if count:
                        lines.append(f"Upcoming: {count} assignment{'s' if count != 1 else ''} due this week")
                except Exception:
                    pass

                # Library books checked out
                try:
                    cursor.execute('''
                        SELECT COUNT(*), MIN(due_date) FROM book_loans
                        WHERE user_id = ? AND status IN ('active', 'overdue')
                    ''', (username,))
                    row = cursor.fetchone()
                    count = row[0] if row else 0
                    if count:
                        nearest = row[1] or 'unknown'
                        lines.append(f"Library: {count} book{'s' if count != 1 else ''} checked out (nearest due: {nearest})")
                except Exception:
                    pass

                # Unread notifications
                try:
                    cursor.execute(
                        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
                        (username,))
                    count = cursor.fetchone()[0]
                    if count:
                        lines.append(f"Notifications: {count} unread")
                except Exception:
                    pass

                # Open support tickets
                try:
                    cursor.execute(
                        "SELECT COUNT(*) FROM support_tickets WHERE user_id = ? AND status NOT IN ('Closed', 'Resolved')",
                        (username,))
                    count = cursor.fetchone()[0]
                    if count:
                        lines.append(f"Support: {count} open ticket{'s' if count != 1 else ''}")
                except Exception:
                    pass

        except Exception as e:
            logger.debug(f"Error building welcome summary: {e}")

        if len(lines) == 1:
            lines.append("No summary data available yet.")

        lines.append("\nUse the quick actions below or type a question.")
        return "\n".join(lines)

    def _build_alumni_welcome(self):
        """Welcome summary tailored to alumni (no courses/assignments/fees)."""
        username = self.current_user.get('username', 'there') if self.current_user else 'there'
        lines = [
            f"Welcome back, {username}! \U0001f393\n",
            "Great to have you in the alumni community. I can help you with:",
            "  • Official transcripts and certificates",
            "  • Alumni events, reunions and announcements",
            "  • Staff and department contacts",
            "  • Booking facilities and library access",
            "  • Support tickets and general questions",
        ]

        # A couple of live, alumni-relevant counts.
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                try:
                    cursor.execute(
                        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
                        (username,))
                    count = cursor.fetchone()[0]
                    if count:
                        lines.append(f"\nNotifications: {count} unread")
                except Exception:
                    pass

                try:
                    cursor.execute(
                        "SELECT COUNT(*) FROM support_tickets WHERE user_id = ? AND status NOT IN ('Closed', 'Resolved')",
                        (username,))
                    count = cursor.fetchone()[0]
                    if count:
                        lines.append(f"Support: {count} open ticket{'s' if count != 1 else ''}")
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Error building alumni welcome summary: {e}")

        lines.append("\nUse the quick actions below or type a question.")
        return "\n".join(lines)

    def show_my_assignments(self):
        """Show the student's assignments with submission status."""
        try:
            username = self.current_user.get('username', '')
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT a.title, a.due_date, a.max_marks, a.assignment_type,
                           sub.status, sub.grade
                    FROM assignments a
                    LEFT JOIN assignment_submissions sub
                        ON a.id = sub.assignment_id AND sub.student_id = ?
                    WHERE a.module_code IN (
                        SELECT module_code FROM student_modules WHERE student_id = ? AND LOWER(status) = 'enrolled'
                    )
                    ORDER BY a.due_date ASC
                    LIMIT 15
                ''', (username, username))
                rows = cursor.fetchall()

            if not rows:
                self.add_chat_message("Chatbot",
                    "No assignments found for your enrolled modules.", "bot")
                return

            response = f"Assignments ({len(rows)}):\n\n"
            for r in rows:
                title, due, max_marks, atype, status, grade = r
                status_label = status if status else ("overdue" if due and due < datetime.now().strftime('%Y-%m-%d') else "pending")
                response += f"  {title}\n"
                response += f"    Type: {atype or 'N/A'}  |  Due: {due or 'N/A'}  |  Max: {max_marks or 'N/A'}\n"
                response += f"    Status: {status_label}"
                if grade is not None:
                    response += f"  |  Grade: {grade}"
                response += "\n\n"

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'assignments', None, details={'user': username})

        except Exception as e:
            self.add_chat_message("Chatbot", f"Error fetching assignments: {e}", "bot")

    def show_my_library_books(self):
        """Show the student's checked-out library books."""
        try:
            username = self.current_user.get('username', '')
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT b.title, b.author, bl.checkout_date, bl.due_date,
                           bl.status, bl.fine_amount
                    FROM book_loans bl
                    JOIN books b ON bl.book_id = b.book_id
                    WHERE bl.user_id = ? AND bl.status IN ('active', 'overdue')
                    ORDER BY bl.due_date ASC
                ''', (username,))
                rows = cursor.fetchall()

            if not rows:
                self.add_chat_message("Chatbot",
                    "You have no books currently checked out.", "bot")
                return

            response = f"Library Books ({len(rows)} checked out):\n\n"
            for r in rows:
                title, author, checkout, due, status, fine = r
                response += f"  {title}\n"
                response += f"    Author: {author or 'N/A'}  |  Due: {due or 'N/A'}  |  Status: {status}\n"
                if fine and float(fine) > 0:
                    response += f"    Fine: £{float(fine):.2f}\n"
                response += "\n"

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'library_books', None, details={'user': username})

        except Exception as e:
            self.add_chat_message("Chatbot", f"Error fetching library books: {e}", "bot")

    def show_my_attendance(self):
        """Show per-module attendance summary."""
        try:
            username = self.current_user.get('username', '')
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT module_code,
                           COUNT(*) as total,
                           SUM(CASE WHEN LOWER(status) = 'present' THEN 1 ELSE 0 END) as present
                    FROM attendance_records
                    WHERE student_id = ?
                    GROUP BY module_code
                ''', (username,))
                rows = cursor.fetchall()

            if not rows:
                self.add_chat_message("Chatbot",
                    "No attendance records found.", "bot")
                return

            response = "Attendance Summary:\n\n"
            for module, total, present in rows:
                pct = (present / total * 100) if total else 0
                response += f"  {module}: {present}/{total} - {pct:.0f}%\n"

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'attendance', None, details={'user': username})

        except Exception as e:
            self.add_chat_message("Chatbot", f"Error fetching attendance: {e}", "bot")

    def show_my_tickets(self):
        """Show the student's open support tickets."""
        try:
            username = self.current_user.get('username', '')
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT ticket_id, subject, category, priority, status, created_at
                    FROM support_tickets
                    WHERE user_id = ? AND status NOT IN ('Closed')
                    ORDER BY created_at DESC
                    LIMIT 10
                ''', (username,))
                rows = cursor.fetchall()

            if not rows:
                self.add_chat_message("Chatbot",
                    "You have no open support tickets.", "bot")
                return

            response = f"Support Tickets ({len(rows)} open):\n\n"
            for r in rows:
                tid, title, cat, pri, status, created = r
                response += f"  #{tid}: {title}\n"
                response += f"    Category: {cat or 'N/A'}  |  Priority: {pri or 'N/A'}  |  Status: {status}\n"
                response += f"    Created: {created or 'N/A'}\n\n"

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'support_tickets', None, details={'user': username})

        except Exception as e:
            self.add_chat_message("Chatbot", f"Error fetching support tickets: {e}", "bot")

    def show_my_notifications(self):
        """Show the student's recent notifications."""
        try:
            username = self.current_user.get('username', '')
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT message, created_at, is_read
                    FROM notifications
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT 10
                ''', (username,))
                rows = cursor.fetchall()

            if not rows:
                self.add_chat_message("Chatbot",
                    "You have no notifications.", "bot")
                return

            response = f"Notifications ({len(rows)} recent):\n\n"
            for msg, created, is_read in rows:
                indicator = "  " if is_read else "* "
                response += f"  {indicator}{msg}\n"
                response += f"    {created or ''}\n\n"

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'notifications', None, details={'user': username})

        except Exception as e:
            self.add_chat_message("Chatbot", f"Error fetching notifications: {e}", "bot")

    def show_upcoming_events(self):
        """Show upcoming campus events."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                # Try campus_events first, fall back to union_events
                rows = []
                for table in ('campus_events', 'union_events'):
                    try:
                        cursor.execute(f'''
                            SELECT event_name, event_date, location, category
                            FROM {table}
                            WHERE event_date >= date('now')
                            ORDER BY event_date ASC
                            LIMIT 10
                        ''')
                        rows = cursor.fetchall()
                        if rows:
                            break
                    except Exception:
                        continue

            if not rows:
                self.add_chat_message("Chatbot",
                    "No upcoming events found.", "bot")
                return

            response = f"Upcoming Events ({len(rows)}):\n\n"
            for name, date_val, location, category in rows:
                response += f"  {name}\n"
                response += f"    Date: {date_val or 'TBD'}  |  Location: {location or 'TBD'}"
                if category:
                    response += f"  |  Category: {category}"
                response += "\n\n"

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'events', None, details={'user': self.current_user.get('username')})

        except Exception as e:
            self.add_chat_message("Chatbot", f"Error fetching events: {e}", "bot")

    def show_announcements(self):
        """Show recent announcements."""
        try:
            username = self.current_user.get('username', '')
            role = self.current_user.get('role', 'student')
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT title, content, created_at
                    FROM announcements
                    WHERE is_active = 1
                      AND (target_audience IN ('all', ?) OR target_audience IS NULL)
                    ORDER BY created_at DESC
                    LIMIT 5
                ''', (role,))
                rows = cursor.fetchall()

            if not rows:
                self.add_chat_message("Chatbot",
                    "No announcements at this time.", "bot")
                return

            response = f"Announcements ({len(rows)} recent):\n\n"
            for title, content, created in rows:
                snippet = (content[:120] + '...') if content and len(content) > 120 else (content or '')
                response += f"  {title}\n"
                response += f"    {snippet}\n"
                response += f"    Posted: {created or 'N/A'}\n\n"

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'announcements', None, details={'user': username})

        except Exception as e:
            self.add_chat_message("Chatbot", f"Error fetching announcements: {e}", "bot")

    def show_quick_help(self):
        """Show a formatted list of what the chatbot can do."""
        help_text = (
            "Quick Help\n\n"
            "Student Services:\n"
            "  My Courses      - View enrolled courses\n"
            "  My Grades       - Grades and GPA\n"
            "  Timetable       - Class schedule / timetable\n"
            "  Financial Aid   - Aid applications and programs\n"
            "  Fee Balance     - Fees, payments, and deadlines\n"
            "  Transcripts     - Request transcripts and certificates\n\n"
            "Academic Support:\n"
            "  Assignments     - Due dates and submissions\n"
            "  Deadlines       - Upcoming deadlines\n"
            "  Exam Schedule   - Exam dates, times, and rooms\n"
            "  Library Search  - Search library catalogue\n"
            "  Academic Calendar - Term dates, holidays\n"
            "  Attendance      - Attendance summary\n\n"
            "Admin & Admissions:\n"
            "  Application Status - Track your application\n"
            "  Staff Directory    - Find staff and contacts\n"
            "  Room Booking       - Book rooms and facilities\n"
            "  ID Card Help       - Replacement guidance\n"
            "  Leave/Deferral     - Request guidance\n"
            "  Support Tickets    - Open support requests\n\n"
            "Campus Life:\n"
            "  Events           - Upcoming campus events\n"
            "  Clubs & Societies - Student clubs info\n"
            "  Wellbeing        - Mental health resources\n"
            "  Lost & Found     - Report or find lost items\n"
            "  Transport        - Shuttle schedules\n"
            "  Notifications    - Recent notifications\n\n"
            "Example Questions:\n"
            "  'What courses am I enrolled in?'\n"
            "  'When is my next exam?'\n"
            "  'What is my fee balance?'\n"
            "  'Search library for machine learning'\n"
            "  'Find Dr Smith in staff directory'\n"
            "  'What mental health support is available?'\n"
            "  'I lost my laptop on campus'\n\n"
            "Keyboard Shortcuts:\n"
            "  Enter          - Send message\n"
            "  Ctrl+Enter     - New line\n"
            "  Escape         - Clear input\n"
            "  F1             - User guide\n"
        )
        self.add_chat_message("Chatbot", help_text, "bot")

    # ------------------------------------------------------------------
    # Student Services
    # ------------------------------------------------------------------

    def show_fee_balance(self):
        """Show student fee balance and payment deadlines."""
        self.quick_message("What is my fee balance?")

    def show_transcript_request(self):
        """Show transcript and certificate request info."""
        self.quick_message("How do I request a transcript or enrollment certificate?")

    # ------------------------------------------------------------------
    # Academic Support
    # ------------------------------------------------------------------

    def show_deadlines(self):
        """Show upcoming assignment and exam deadlines."""
        try:
            username = self.current_user.get('username', '')
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT a.title, a.due_date, a.module_code, a.assignment_type
                    FROM assignments a
                    LEFT JOIN assignment_submissions sub
                        ON a.id = sub.assignment_id AND sub.student_id = ?
                    WHERE a.module_code IN (
                        SELECT module_code FROM student_modules
                        WHERE student_id = ? AND LOWER(status) = 'enrolled'
                    )
                    AND a.due_date >= date('now')
                    AND sub.id IS NULL
                    ORDER BY a.due_date ASC LIMIT 15
                ''', (username, username))
                rows = cursor.fetchall()

            if not rows:
                self.add_chat_message("Chatbot",
                    "No upcoming deadlines. You're all caught up!", "bot")
                return

            response = f"Upcoming Deadlines ({len(rows)}):\n\n"
            for title, due, module, atype in rows:
                response += f"  {title} ({module})\n"
                response += f"    Type: {atype or 'N/A'}  |  Due: {due}\n\n"

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'deadlines', None, details={'user': username})

        except Exception as e:
            self.add_chat_message("Chatbot", f"Error fetching deadlines: {e}", "bot")

    def show_exam_schedule(self):
        """Show exam schedule with room locations."""
        try:
            username = self.current_user.get('username', '')
            with get_connection() as conn:
                cursor = conn.cursor()
                rows = []
                # Try exams table with rooms join
                try:
                    cursor.execute('''
                        SELECT e.module_code, e.exam_date, e.start_time, e.end_time,
                               r.room_number, r.building
                        FROM exams e
                        LEFT JOIN rooms r ON e.room_id = r.id
                        WHERE e.module_code IN (
                            SELECT module_code FROM student_modules
                            WHERE student_id = ? AND LOWER(status) = 'enrolled'
                        ) AND e.exam_date >= date('now')
                        ORDER BY e.exam_date ASC
                    ''', (username,))
                    rows = cursor.fetchall()
                except Exception:
                    pass

                if not rows:
                    # Fallback: exam_schedule table
                    try:
                        cursor.execute('''
                            SELECT module_code, exam_date, start_time, end_time, location, ''
                            FROM exam_schedule
                            WHERE module_code IN (
                                SELECT module_code FROM student_modules
                                WHERE student_id = ? AND LOWER(status) = 'enrolled'
                            ) AND exam_date >= date('now')
                            ORDER BY exam_date ASC
                        ''', (username,))
                        rows = cursor.fetchall()
                    except Exception:
                        pass

            if not rows:
                self.add_chat_message("Chatbot",
                    "No upcoming exams found for your modules.", "bot")
                return

            response = f"Exam Schedule ({len(rows)} exams):\n\n"
            for module, date_val, start, end, room, building in rows:
                room_str = room or 'TBD'
                if building:
                    room_str += f" ({building})"
                response += f"  {module}\n"
                response += f"    Date: {date_val}  |  Time: {start or '?'} - {end or '?'}  |  Room: {room_str}\n\n"

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'exam_schedule', None, details={'user': username})

        except Exception as e:
            self.add_chat_message("Chatbot", f"Error fetching exam schedule: {e}", "bot")

    def show_library_search(self):
        """Prompt user for library search query."""
        self.add_chat_message("Chatbot",
            "Library Search:\n\n"
            "Type a book title, author, or ISBN to search the library catalogue.\n"
            "Example: 'Search library for Python programming'", "bot")

    def show_academic_calendar(self):
        """Show academic calendar events."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                rows = []
                try:
                    cursor.execute('''
                        SELECT name,
                               COALESCE(date_start, date) AS ev_start,
                               COALESCE(date_end, date_start, date) AS ev_end,
                               event_type
                        FROM academic_calendar_events
                        WHERE COALESCE(date_start, date) >= date('now', '-30 days')
                        ORDER BY ev_start ASC LIMIT 20
                    ''')
                    rows = cursor.fetchall()
                except Exception:
                    rows = []

            if not rows:
                self.add_chat_message("Chatbot",
                    "Academic calendar information is not currently available.\n"
                    "Check the university website for term dates and holidays.", "bot")
                return

            response = f"Academic Calendar ({len(rows)} events):\n\n"
            for name, start, end, etype in rows:
                end_str = f" to {end}" if end else ""
                response += f"  {name}\n"
                response += f"    Date: {start}{end_str}  |  Type: {etype or 'N/A'}\n\n"

            self.add_chat_message("Chatbot", response, "bot")
            log_activity('view', 'academic_calendar', None,
                        details={'user': self.current_user.get('username')})

        except Exception as e:
            self.add_chat_message("Chatbot", f"Error fetching academic calendar: {e}", "bot")

    # ------------------------------------------------------------------
    # Admissions & Admin
    # ------------------------------------------------------------------

    def show_application_status(self):
        """Show application status."""
        self.quick_message("What is my application status?")

    def show_staff_directory(self):
        """Prompt for staff directory search."""
        self.add_chat_message("Chatbot",
            "Staff Directory:\n\n"
            "Type a name, department, or role to search.\n"
            "Example: 'Find Dr Smith' or 'Contact Computer Science department'", "bot")

    def show_room_bookings(self):
        """Show room bookings or booking instructions."""
        self.quick_message("Show my room bookings")

    def show_id_card_help(self):
        """Show ID card replacement guidance."""
        self.quick_message("How do I replace my ID card?")

    def show_leave_guidance(self):
        """Show leave of absence / deferral guidance."""
        self.quick_message("How do I apply for a leave of absence?")

    # ------------------------------------------------------------------
    # Wellbeing & Campus Life
    # ------------------------------------------------------------------

    def show_clubs_societies(self):
        """Show student clubs and societies."""
        self.quick_message("What clubs and societies are available?")

    def show_mental_health_resources(self):
        """Show mental health and wellbeing resources."""
        resources = [
            ("University Counselling Service",
             "Free, confidential counselling for all students. Book via the student portal.",
             "counselling@university.ac.uk"),
            ("Student Wellbeing Centre",
             "Drop-in support, workshops, and group sessions.",
             "wellbeing@university.ac.uk"),
            ("24/7 Crisis Helpline",
             "Immediate support available around the clock.",
             "0800-XXX-XXXX"),
            ("Disability & Inclusion Service",
             "Support for students with disabilities, learning differences, or mental health conditions.",
             "disability@university.ac.uk"),
            ("Peer Support Network",
             "Trained student volunteers offering peer-to-peer support.",
             "peersupport@university.ac.uk"),
        ]
        response = "Mental Health & Wellbeing Resources:\n\n"
        for name, desc, contact in resources:
            response += f"  {name}\n"
            response += f"    {desc}\n"
            response += f"    Contact: {contact}\n\n"
        response += "Remember: it's okay to ask for help. You are not alone."
        self.add_chat_message("Chatbot", response, "bot")
        log_activity('view', 'mental_health_resources', None,
                    details={'user': self.current_user.get('username')})

    def show_lost_found(self):
        """Show lost and found info."""
        self.quick_message("Show lost and found items")

    def show_transport_schedule(self):
        """Show campus transport schedule."""
        self.quick_message("What is the shuttle schedule?")
