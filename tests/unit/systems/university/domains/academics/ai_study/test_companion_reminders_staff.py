"""Study companion reminders, settings, the staff view and the slippage signal."""

from __future__ import annotations

import pytest

from datetime import date as _date, timedelta as _timedelta


def day(offset: int) -> str:
    return (_date.today() + _timedelta(days=offset)).isoformat()

ADMIN = {"username": "admin", "role": "admin"}
STUDENT = {"username": "s1", "role": "student", "student_id": "S1"}


def _due_card(service, db, sid="S1"):
    _, transaction = db
    fid = service.create_flashcard(sid, None, "D", "Q", "A")
    with transaction() as conn:
        conn.execute("UPDATE flashcards SET next_review = ? WHERE flashcard_id = ?", (day(0), fid))
    return fid


class TestReminders:
    def test_today_summary(self, service, student, db):
        _, transaction = db
        _due_card(service, db)
        with transaction() as conn:
            conn.execute("INSERT INTO exams (module_code, date, start_time, end_time) "
                         "VALUES ('CS101', ?, '09:00', '11:00')", (day(3),))
            conn.execute("INSERT INTO assignments (module_code, title, due_date) "
                         "VALUES ('CS102', 'Lab 2', ?)", (day(2) + " 17:00",))
        service.generate_study_plan(student, "CS101", day(3))
        today = service.today(student)
        assert today["due_cards"] == 1
        assert today["tasks_today"]
        assert [e["module_code"] for e in today["exams_soon"]] == ["CS101"]
        assert [d["title"] for d in today["deadlines_soon"]] == ["Lab 2"]

    def test_submitted_assignment_is_not_a_deadline(self, service, student, db):
        _, transaction = db
        with transaction() as conn:
            aid = conn.execute("INSERT INTO assignments (module_code, title, due_date) "
                               "VALUES ('CS102', 'Lab 2', ?)", (day(2),)).lastrowid
            conn.execute("INSERT INTO assignment_submissions (assignment_id, student_id) "
                         "VALUES (?, 'S1')", (aid,))
        assert service.today(student)["deadlines_soon"] == []

    def test_sent_once_a_day_to_the_inbox(self, service, student, db):
        get_connection, _ = db
        _due_card(service, db)
        first = service.send_my_reminder(student)
        second = service.send_my_reminder(student)
        assert first["sent"] is True
        assert (second["sent"], second["reason"]) == (False, "already sent today")
        with get_connection() as conn:
            rows = conn.execute("SELECT m.subject FROM messages m JOIN users u ON u.id = "
                                "m.recipient_id WHERE u.student_id = 'S1'").fetchall()
        assert len(rows) == 1 and "Study companion" in rows[0][0]

    def test_nothing_due_sends_nothing(self, service, student):
        assert service.send_my_reminder(student)["reason"] == "nothing due"

    def test_turned_off(self, service, student, db):
        _due_card(service, db)
        service.save_settings(student, reminders_enabled=False)
        assert service.send_my_reminder(student)["reason"] == "turned off"

    def test_email_only_when_asked(self, service, student, db):
        _due_card(service, db)
        service.save_settings(student, email_reminders=True)
        assert service.send_my_reminder(student)["emailed"] == 1

    def test_send_all(self, service, student, db):
        _due_card(service, db, "S1")
        _due_card(service, db, "S2")
        result = service.send_all_reminders()
        assert result["checked"] == 2 and result["sent"] >= 1

    def test_settings_validation(self, service):
        with pytest.raises(ValueError):
            service.save_settings("S1", daily_card_limit=0)
        assert service.get_settings("nobody")["share_with_tutor"] == 1


class TestStaffView:
    def test_admin_sees_everyone_student_sees_self(self, service, student):
        service.generate_study_plan(student, None, day(5))
        rows = service.staff_overview(ADMIN)
        assert [r["student_id"] for r in rows] == ["S1"] and rows[0]["name"] == "Ada Lovelace"
        with pytest.raises(PermissionError):
            service.staff_overview(STUDENT)
        assert service.can_view_student(STUDENT, "S1")
        assert not service.can_view_student(STUDENT, "S2")

    def test_teaching_staff_see_their_module_students(self, service, student, db):
        _, transaction = db
        lecturer = {"username": "lect", "role": "instructor"}
        assert not service.can_view_student(lecturer, "S1")
        with transaction() as conn:
            conn.execute("INSERT INTO module_staff (module_code, username, role) "
                         "VALUES ('CS101', 'lect', 'lecturer')")
        assert service.can_view_student(lecturer, "S1")
        service.generate_study_plan(student, None, day(5))
        assert [r["student_id"] for r in service.staff_overview(lecturer, "CS101")] == ["S1"]
        assert service.staff_overview(lecturer, "CS999") == []

    def test_opt_out_hides_detail(self, service, student):
        service.generate_study_plan(student, None, day(5))
        service.save_settings(student, share_with_tutor=False)
        row = service.staff_overview(ADMIN)[0]
        assert row["shared"] is False and "tasks_missed" not in row
        detail = service.staff_student_detail(ADMIN, student)
        assert detail["shared"] is False and "plans" not in detail

    def test_detail_never_has_card_text(self, service, student):
        service.create_flashcard(student, "CS101", "Deck", "Secret question", "Secret answer")
        detail = service.staff_student_detail(ADMIN, student)
        assert "Secret" not in repr(detail)
        assert detail["decks"][0]["cards"] == 1


class TestSlippage:
    def _slip(self, service, db, sid):
        _, transaction = db
        result = service.generate_study_plan(sid, None, day(10))
        with transaction() as conn:
            conn.execute("UPDATE study_plan_tasks SET scheduled_date = ? WHERE plan_id = ?",
                         (day(-3), result["plan_id"]))
        return result["plan_id"]

    def test_raised_once_then_resolved(self, service, student, db):
        get_connection, _ = db
        plan_id = self._slip(service, db, student)
        assert service.engagement_scan() == {"raised": 1, "resolved": 0}
        assert service.engagement_scan() == {"raised": 0, "resolved": 0}
        with get_connection() as conn:
            row = conn.execute("SELECT indicator_type, severity FROM early_warning_indicators "
                               "WHERE student_id = 'S1' AND is_resolved = 0").fetchone()
        assert tuple(row) == ("study_plan_slippage", "low")
        service.reschedule_missed(plan_id, student)
        assert service.engagement_scan() == {"raised": 0, "resolved": 1}

    def test_not_for_opted_out_or_non_students(self, service, student, db):
        self._slip(service, db, student)
        self._slip(service, db, "staffer")  # no students row
        service.save_settings(student, share_with_tutor=False)
        assert service.engagement_scan()["raised"] == 0
