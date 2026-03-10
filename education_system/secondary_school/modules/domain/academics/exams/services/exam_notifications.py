"""Exam email notifications — sends internal emails to enrolled students."""

import json
import logging
from pathlib import Path

from education_system.secondary_school.infrastructure.database.db import connect

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).resolve().parents[4] / "data" / "config" / "exam_email_templates.json"

# System sender user ID — emails come from the admin account (id=1)
SYSTEM_SENDER_ID = 1


def _load_templates() -> dict:
    """Load email templates from JSON file."""
    try:
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to load exam email templates: %s", e)
        return {}


def _get_enrolled_student_user_ids(db_path: str | None, subject_id: int,
                                    year_group: str | None = None) -> list[dict]:
    """Get user_id and name for students enrolled in a subject."""
    conn = connect(db_path)
    try:
        sql = """SELECT s.user_id, s.first_name, s.last_name
                 FROM enrollments e
                 JOIN students s ON e.student_id = s.id
                 WHERE e.subject_id = ? AND e.status = 'enrolled'
                   AND s.user_id IS NOT NULL"""
        params: list = [subject_id]
        if year_group:
            sql += " AND s.year_group = ?"
            params.append(year_group)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _format_template(template: dict, exam: dict, student_name: str) -> tuple[str, str]:
    """Format subject and body from template with exam data."""
    placeholders = {
        "exam_title": exam.get("title") or "",
        "subject_title": exam.get("subject_title") or "",
        "exam_type": exam.get("exam_type") or "",
        "date": exam.get("date") or "TBC",
        "start_time": exam.get("start_time") or "TBC",
        "duration_minutes": str(exam.get("duration_minutes") or ""),
        "room": exam.get("room") or "TBC",
        "invigilator": exam.get("invigilator") or "TBC",
        "total_marks": str(exam.get("total_marks") or ""),
        "status": exam.get("status") or "",
        "student_name": student_name,
    }
    subject = template.get("subject", "Exam Notification").format(**placeholders)
    body = template.get("body", "").format(**placeholders)
    return subject, body


def send_exam_notification(db_path: str | None, exam: dict, event: str):
    """Send internal emails to all enrolled students for an exam event.

    Args:
        db_path: Database path.
        exam: Exam dict (must include subject_id and subject_title).
        event: One of 'scheduled', 'updated', 'cancelled'.
    """
    templates = _load_templates()
    template = templates.get(event)
    if not template:
        logger.warning("No email template for event '%s'", event)
        return

    subject_id = exam.get("subject_id")
    if not subject_id:
        return

    students = _get_enrolled_student_user_ids(db_path, subject_id,
                                               year_group=exam.get("year_group"))
    if not students:
        logger.info("No enrolled students to notify for exam %s", exam.get("title"))
        return

    conn = connect(db_path)
    sent = 0
    try:
        for stu in students:
            user_id = stu["user_id"]
            name = f"{stu['first_name']} {stu['last_name']}"
            subj, body = _format_template(template, exam, name)

            conn.execute(
                """INSERT INTO emails (sender_id, recipient_id, subject, body)
                   VALUES (?, ?, ?, ?)""",
                (SYSTEM_SENDER_ID, user_id, subj, body),
            )
            sent += 1

        conn.commit()
        logger.info("Sent %d exam notification email(s) for '%s' (%s)",
                     sent, exam.get("title"), event)
    except Exception as e:
        conn.rollback()
        logger.error("Failed to send exam notifications: %s", e)
    finally:
        conn.close()
