"""Background tasks: scheduling, analytics, alerts, and run modes."""

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Dict

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.shared.ai.chatbot.fallbacks import (
    LIBRARIES_AVAILABLE,
    schedule,
)

logger = logging.getLogger(__name__)


def run(chatbot):
    """Enhanced run method - uses existing authentication"""
    if hasattr(chatbot, 'auth_system') and chatbot.auth_system and chatbot.auth_system.current_user:
        chatbot.run_authenticated_console_interface()
    else:
        run_console_interface(chatbot)


def run_console_interface(chatbot):
    """Run the console-based chatbot interface with voice support"""
    print("Enhanced University Chatbot with Voice Support")
    print("=" * 50)

    user_id = input("Enter your student/staff ID: ")
    print(f"Welcome! Authenticated as {user_id}")

    if chatbot.voice_interface.enabled:
        print("Voice interface is available! Say 'start voice mode' or 'voice help' for voice commands.")

    print("Type 'exit' to end the conversation, 'help' for commands.")

    while True:
        try:
            user_input = input(f"\n{user_id}: ")

            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("Chatbot: Goodbye! Have a great day!")
                if chatbot.voice_interface.enabled:
                    chatbot.voice_interface.cleanup()
                break

            if user_input.lower() == 'help':
                print("Available commands:")
                print("- Ask about courses, registration, grades, fees")
                print("- Request course recommendations")
                print("- Check academic progress")
                print("- Get help with technical issues")
                if chatbot.voice_interface.enabled:
                    print("- Voice commands: 'start voice mode', 'test voice', 'voice help'")
                continue

            if not user_input.strip():
                print("Chatbot: Please enter a message.")
                continue

            response = chatbot.process_message(user_input, user_id)
            print(f"Chatbot: {response}")

        except KeyboardInterrupt:
            print("\nChatbot: Goodbye!")
            if chatbot.voice_interface.enabled:
                chatbot.voice_interface.cleanup()
            break
        except Exception as e:
            print(f"Chatbot: I encountered an error: {e}")


def run_web_server(chatbot, host='0.0.0.0', port=5000):
    """Run the web server for API access"""
    if LIBRARIES_AVAILABLE['flask']:
        chatbot.app.run(host=host, port=port, debug=False)
    else:
        print("Flask not available - cannot start web server")


def setup_scheduled_tasks(chatbot):
    """Setup background scheduled tasks"""
    schedule.every().day.at("09:00").do(lambda: send_proactive_alerts(chatbot))
    schedule.every().day.at("23:59").do(lambda: generate_daily_analytics(chatbot))
    schedule.every().week.do(lambda: cleanup_old_sessions(chatbot))

    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)

    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()


def generate_daily_analytics(chatbot):
    """Generate daily analytics report"""
    analytics = generate_usage_analytics(chatbot)

    today = datetime.now().strftime("%Y-%m-%d")
    analytics_file = os.path.join(chatbot.log_dir, f"analytics_{today}.json")

    with open(analytics_file, 'w') as f:
        json.dump(analytics, f, indent=4)


def cleanup_old_sessions(chatbot):
    """Clean up expired sessions"""
    current_time = datetime.now()
    expired_sessions = []

    for token, session in chatbot.active_sessions.items():
        if (current_time - session.last_activity).seconds > chatbot.config["security"]["session_timeout"]:
            expired_sessions.append(token)

    for token in expired_sessions:
        del chatbot.active_sessions[token]


def generate_usage_analytics(chatbot) -> Dict:
    """Usage figures from the conversation log in the database (counts
    only; the old per-day JSON log files are no longer written)."""
    from education_system.systems.university.infrastructure.database.db import get_connection
    analytics = {
        "total_conversations": 0,
        "unique_users": 0,
        "popular_intents": {},
        "response_times": [],
        "user_satisfaction": {},
        "error_rates": {},
        "peak_usage_hours": {},
        "department_queries": {},
        "voice_usage": {"total": 0, "successful": 0, "failed": 0}
    }
    conn = get_connection(getattr(chatbot, "db_path", None), row_factory=False)
    try:
        total, users = conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT username) FROM chatbot_conversations").fetchone()
        analytics["total_conversations"], analytics["unique_users"] = total, users
        analytics["popular_intents"] = dict(conn.execute(
            "SELECT COALESCE(intent, 'unknown'), COUNT(*) FROM chatbot_conversations "
            "GROUP BY 1 ORDER BY 2 DESC").fetchall())
        analytics["peak_usage_hours"] = {int(h): n for h, n in conn.execute(
            "SELECT strftime('%H', timestamp), COUNT(*) FROM chatbot_conversations "
            "WHERE timestamp IS NOT NULL GROUP BY 1").fetchall() if h is not None}
        helpful = conn.execute(
            "SELECT SUM(helpful), COUNT(*) FROM chatbot_feedback").fetchone()
        analytics["user_satisfaction"] = {"helpful": helpful[0] or 0, "ratings": helpful[1]}
    except sqlite3.Error as e:
        logger.debug(f"Chatbot usage analytics unavailable: {e}")
    finally:
        conn.close()
    return analytics


def send_proactive_alerts(chatbot):
    """Send proactive notifications based on deadlines and events"""
    try:
        conn = sqlite3.connect(str(chatbot.db_path))
        cursor = conn.cursor()

        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        week_ahead = today + timedelta(days=7)

        alerts_sent = 0

        try:
            cursor.execute("""
                SELECT DISTINCT sm.student_id,
                       COALESCE(a.course_name, a.module_code),
                       COALESCE(a.assignment_name, a.title), a.due_date
                FROM assignments a
                JOIN student_modules sm ON sm.module_code = a.module_code
                WHERE LOWER(sm.status) = 'enrolled'
                AND a.due_date BETWEEN ? AND ?
                AND NOT EXISTS (SELECT 1 FROM assignment_submissions sub
                                WHERE sub.assignment_id = a.id AND sub.student_id = sm.student_id)
            """, (today.isoformat(), tomorrow.isoformat()))

            urgent_assignments = cursor.fetchall()
            for student_id, course, assignment, due_date in urgent_assignments:
                logger.info(f"Alert: Assignment '{assignment}' for {course} due tomorrow for student {student_id}")
                alerts_sent += 1
        except sqlite3.OperationalError as e:
            logger.debug(f"Assignment table not available for alerts: {e}")

        try:
            cursor.execute("""
                SELECT DISTINCT sm.student_id, e.module_name,
                       COALESCE(e.exam_name, e.module_name), e.date
                FROM exams e
                JOIN student_modules sm ON sm.module_code = e.module_code
                WHERE LOWER(sm.status) = 'enrolled'
                AND COALESCE(e.status, 'published') = 'published'
                AND e.date BETWEEN ? AND ?
            """, (today.isoformat(), week_ahead.isoformat()))

            upcoming_exams = cursor.fetchall()
            for student_id, course, exam, exam_date in upcoming_exams:
                days_until = (datetime.fromisoformat(exam_date).date() - today).days
                logger.info(f"Alert: Exam '{exam}' for {course} in {days_until} days for student {student_id}")
                alerts_sent += 1
        except sqlite3.OperationalError as e:
            logger.debug(f"Exams table not available for alerts: {e}")

        try:
            cursor.execute("""
                SELECT DISTINCT student_id, module_code, grade
                FROM grades
                WHERE grade < 60 AND grade > 0
                AND created_at >= date('now', '-7 days')
            """)

            low_grades = cursor.fetchall()
            for student_id, course, grade in low_grades:
                logger.info(f"Alert: Low grade ({grade}%) in {course} for student {student_id} - recommend tutoring")
                alerts_sent += 1
        except sqlite3.OperationalError as e:
            logger.debug(f"Grades table not available for alerts: {e}")

        try:
            cursor.execute("""
                SELECT student_id, course_name, COUNT(*) as absences
                FROM attendance
                WHERE status = 'absent'
                AND date >= date('now', '-30 days')
                GROUP BY student_id, course_name
                HAVING COUNT(*) >= 3
            """)

            high_absences = cursor.fetchall()
            for student_id, course, count in high_absences:
                logger.info(f"Alert: High absence rate ({count} absences) in {course} for student {student_id}")
                alerts_sent += 1
        except sqlite3.OperationalError as e:
            logger.debug(f"Attendance table not available for alerts: {e}")

        conn.close()

        if alerts_sent > 0:
            logger.info(f"Proactive alerts completed: {alerts_sent} alerts processed")

    except Exception as e:
        logger.error(f"Error sending proactive alerts: {e}")
