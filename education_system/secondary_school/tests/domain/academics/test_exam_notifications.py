"""Tests for exam notification service."""

from pathlib import Path
from unittest.mock import patch

import pytest

from education_system.secondary_school.modules.domain.academics.exams.services.exam_notifications import (
    _format_template,
    _get_enrolled_student_user_ids,
    _load_templates,
    send_exam_notification,
    SYSTEM_SENDER_ID,
)


class TestLoadTemplates:
    """Tests for template loading."""

    def test_load_templates_returns_dict(self):
        result = _load_templates()
        assert isinstance(result, dict)

    def test_load_templates_has_expected_events(self):
        result = _load_templates()
        if result:
            assert any(k in result for k in ("scheduled", "updated", "cancelled"))

    def test_load_templates_missing_file_returns_empty(self):
        with patch(
            "education_system.secondary_school.modules.domain.academics.exams.services.exam_notifications.TEMPLATE_PATH",
            Path("/nonexistent/template.json"),
        ):
            result = _load_templates()
            assert result == {}


class TestFormatTemplate:
    """Tests for template formatting."""

    def test_format_basic_template(self):
        template = {
            "subject": "Exam: {exam_title}",
            "body": "Dear {student_name}, your {subject_title} exam is on {date}.",
        }
        exam = {
            "title": "Maths Final",
            "subject_title": "Mathematics",
            "date": "2025-12-15",
            "exam_type": "final",
        }
        subject, body = _format_template(template, exam, "John Doe")
        assert "Maths Final" in subject
        assert "John Doe" in body
        assert "Mathematics" in body
        assert "2025-12-15" in body

    def test_format_missing_fields_use_defaults(self):
        template = {
            "subject": "{exam_title}",
            "body": "Date: {date}, Room: {room}",
        }
        exam = {}
        subject, body = _format_template(template, exam, "Jane")
        assert "TBC" in body

    def test_format_no_subject_in_template(self):
        template = {"body": "Hello {student_name}"}
        exam = {"title": "Test"}
        subject, body = _format_template(template, exam, "Alice")
        assert subject == "Exam Notification"
        assert "Alice" in body


class TestGetEnrolledStudentUserIds:
    """Tests for fetching enrolled student user IDs."""

    def test_no_enrolled_students(self, db_path, sample_subject):
        result = _get_enrolled_student_user_ids(db_path, sample_subject["id"])
        assert result == []

    def test_enrolled_students_returned(self, db_path, enrolled_student, sample_subject):
        from education_system.secondary_school.infrastructure.database.db import connect
        conn = connect(db_path)
        try:
            # Disable FK checks to set a test user_id
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute(
                "UPDATE students SET user_id = ? WHERE id = ?",
                (99, enrolled_student["id"]),
            )
            conn.commit()
            conn.execute("PRAGMA foreign_keys = ON")
        finally:
            conn.close()

        result = _get_enrolled_student_user_ids(db_path, sample_subject["id"])
        assert len(result) == 1
        assert result[0]["first_name"] == "John"

    def test_filter_by_year_group(self, db_path, sample_subject, student_service, enrollment_service):
        s1 = student_service.create_student(
            first_name="Y9", last_name="Student", year_group="9",
        )
        s2 = student_service.create_student(
            first_name="Y10", last_name="Student", year_group="10",
        )
        enrollment_service.enroll_student(s1["id"], sample_subject["id"])
        enrollment_service.enroll_student(s2["id"], sample_subject["id"])

        from education_system.secondary_school.infrastructure.database.db import connect
        conn = connect(db_path)
        try:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("UPDATE students SET user_id = 100 WHERE id = ?", (s1["id"],))
            conn.execute("UPDATE students SET user_id = 101 WHERE id = ?", (s2["id"],))
            conn.commit()
            conn.execute("PRAGMA foreign_keys = ON")
        finally:
            conn.close()

        result = _get_enrolled_student_user_ids(db_path, sample_subject["id"], year_group="9")
        assert len(result) == 1
        assert result[0]["first_name"] == "Y9"


class TestSendExamNotification:
    """Tests for the main send_exam_notification function."""

    def test_no_template_for_event(self, db_path):
        with patch(
            "education_system.secondary_school.modules.domain.academics.exams.services.exam_notifications._load_templates",
            return_value={},
        ):
            send_exam_notification(db_path, {"subject_id": 1, "title": "Test"}, "scheduled")

    def test_no_subject_id_returns_early(self, db_path):
        send_exam_notification(db_path, {"title": "Test"}, "scheduled")

    def test_sends_emails_to_enrolled_students(self, db_path, enrolled_student, sample_subject):
        from education_system.secondary_school.infrastructure.database.db import connect

        conn = connect(db_path)
        try:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute(
                "UPDATE students SET user_id = ? WHERE id = ?",
                (99, enrolled_student["id"]),
            )
            conn.commit()
            conn.execute("PRAGMA foreign_keys = ON")
        finally:
            conn.close()

        exam = {
            "title": "Maths Final",
            "subject_id": sample_subject["id"],
            "subject_title": "Mathematics",
            "exam_type": "end_of_term",
            "date": "2025-12-15",
            "start_time": "09:00",
            "duration_minutes": 90,
            "room": "Hall A",
            "total_marks": 100,
            "year_group": "9",
        }

        # Ensure sender (id=1) and recipient (id=99) users exist so FK on emails is satisfied
        conn = connect(db_path)
        try:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute(
                "INSERT OR IGNORE INTO users (id, username, password_hash, role) "
                "VALUES (1, 'system', 'x', 'admin')"
            )
            conn.execute(
                "INSERT OR IGNORE INTO users (id, username, password_hash, role) "
                "VALUES (99, 'teststudent', 'x', 'student')"
            )
            conn.commit()
            conn.execute("PRAGMA foreign_keys = ON")
        finally:
            conn.close()

        # Provide a mock template since the template file path may not exist in test env
        mock_templates = {
            "scheduled": {
                "subject": "Exam: {exam_title}",
                "body": "Dear {student_name}, {subject_title} exam on {date}.",
            }
        }
        with patch(
            "education_system.secondary_school.modules.domain.academics.exams.services.exam_notifications._load_templates",
            return_value=mock_templates,
        ):
            send_exam_notification(db_path, exam, "scheduled")

        conn = connect(db_path)
        try:
            emails = conn.execute(
                "SELECT * FROM emails WHERE recipient_id = 99"
            ).fetchall()
            assert len(emails) >= 1
            email = dict(emails[0])
            assert email["sender_id"] == SYSTEM_SENDER_ID
        finally:
            conn.close()

    def test_system_sender_id(self):
        assert SYSTEM_SENDER_ID == 1
