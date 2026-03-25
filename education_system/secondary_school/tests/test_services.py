"""Comprehensive tests for secondary school services.

All service fixtures are provided by conftest.py.
"""

import pytest


# ---------------------------------------------------------------------------
# Exam Service
# ---------------------------------------------------------------------------

class TestExamService:
    def test_create_exam(self, exam_service, sample_subject):
        exam = exam_service.create_exam(
            subject_id=sample_subject["id"],
            title="Mock GCSE Maths",
            exam_type="mock",
            year_group="10",
            date="2026-01-20",
            start_time="09:00",
            duration_minutes=120,
            room="Main Hall",
            total_marks=80,
        )
        assert exam["id"] > 0
        assert exam["title"] == "Mock GCSE Maths"
        assert exam["exam_type"] == "mock"
        assert exam["total_marks"] == 80

    def test_list_exams(self, exam_service, sample_subject):
        exam_service.create_exam(subject_id=sample_subject["id"], title="Test A",
                                 exam_type="class_test", year_group="9")
        exam_service.create_exam(subject_id=sample_subject["id"], title="Test B",
                                 exam_type="class_test", year_group="10")
        results = exam_service.list_exams(year_group="9")
        assert any(e["title"] == "Test A" for e in results)
        assert not any(e["title"] == "Test B" for e in results)

    def test_update_exam(self, exam_service, sample_exam):
        updated = exam_service.update_exam(sample_exam["id"], title="Updated Title", room="Hall B")
        assert updated["title"] == "Updated Title"
        assert updated["room"] == "Hall B"

    def test_update_exam_status(self, exam_service, sample_exam):
        exam_service.update_exam_status(sample_exam["id"], "completed")
        exams = exam_service.list_exams()
        found = [e for e in exams if e["id"] == sample_exam["id"]]
        assert found[0]["status"] == "completed"

    def test_delete_exam(self, exam_service, sample_exam):
        exam_service.delete_exam(sample_exam["id"])
        exams = exam_service.list_exams()
        assert not any(e["id"] == sample_exam["id"] for e in exams)

    def test_record_result(self, exam_service, sample_exam, sample_student):
        result = exam_service.record_result(
            exam_id=sample_exam["id"],
            student_id=sample_student["id"],
            marks_obtained=85,
            grade="7",
        )
        assert result["marks_obtained"] == 85
        assert result["grade"] == "7"

    def test_get_exam_results(self, exam_service, sample_exam, sample_student):
        exam_service.record_result(sample_exam["id"], sample_student["id"],
                                   marks_obtained=72, grade="6")
        results = exam_service.get_exam_results(sample_exam["id"])
        assert len(results) == 1
        assert results[0]["marks_obtained"] == 72

    def test_get_student_exam_results(self, exam_service, sample_exam, sample_student):
        exam_service.record_result(sample_exam["id"], sample_student["id"],
                                   marks_obtained=90, grade="8")
        results = exam_service.get_student_exam_results(sample_student["id"])
        assert len(results) >= 1
        assert results[0]["grade"] == "8"


# ---------------------------------------------------------------------------
# Homework Service
# ---------------------------------------------------------------------------

class TestHomeworkService:
    def test_create_homework(self, homework_service, sample_subject):
        hw = homework_service.create_homework(
            subject_id=sample_subject["id"],
            title="Quadratics Worksheet",
            due_date="2026-02-15",
            year_group="10",
            description="Complete all questions",
            max_marks=40,
        )
        assert hw["id"] > 0
        assert hw["title"] == "Quadratics Worksheet"

    def test_list_homework(self, homework_service, sample_homework):
        items = homework_service.list_homework(year_group="9")
        assert any(h["title"] == "Algebra Practice" for h in items)

    def test_submit_homework(self, homework_service, sample_homework, sample_student):
        homework_service.submit(sample_homework["id"], sample_student["id"])
        subs = homework_service.get_submissions(sample_homework["id"])
        assert len(subs) == 1
        assert subs[0]["status"] == "submitted"

    def test_mark_submission(self, homework_service, sample_homework, sample_student):
        homework_service.submit(sample_homework["id"], sample_student["id"])
        homework_service.mark_submission(sample_homework["id"], sample_student["id"],
                                         marks=42, feedback="Well done")
        subs = homework_service.get_submissions(sample_homework["id"])
        assert subs[0]["status"] == "marked"
        assert subs[0]["marks"] == 42

    def test_delete_homework(self, homework_service, sample_homework):
        homework_service.delete_homework(sample_homework["id"])
        items = homework_service.list_homework()
        assert not any(h["id"] == sample_homework["id"] for h in items)

    def test_get_submission_stats(self, homework_service, sample_homework, sample_student):
        homework_service.submit(sample_homework["id"], sample_student["id"])
        stats = homework_service.get_submission_stats(sample_homework["id"])
        assert stats["total_submissions"] == 1
        assert stats["submitted_count"] == 1


# ---------------------------------------------------------------------------
# Timetable Service
# ---------------------------------------------------------------------------

class TestTimetableService:
    def test_add_slot(self, timetable_service, sample_subject):
        slot = timetable_service.add_slot(
            subject_id=sample_subject["id"],
            day_of_week="Monday",
            period=1,
            room="M1",
            teacher="Mr Smith",
            year_group="9",
            term="Autumn",
        )
        assert slot["id"] > 0
        assert slot["day_of_week"] == "Monday"
        assert slot["period"] == 1

    def test_get_timetable(self, timetable_service, sample_subject):
        timetable_service.add_slot(sample_subject["id"], "Tuesday", 2,
                                   year_group="9", term="Autumn")
        slots = timetable_service.get_timetable(year_group="9", term="Autumn")
        assert len(slots) >= 1

    def test_clash_detection(self, timetable_service, sample_subject):
        timetable_service.add_slot(sample_subject["id"], "Wednesday", 3,
                                   year_group="9", term="Autumn")
        from education_system.secondary_school.core.exceptions import TimetableError
        with pytest.raises(TimetableError, match="Clash"):
            timetable_service.add_slot(sample_subject["id"], "Wednesday", 3,
                                       year_group="9", term="Autumn")

    def test_delete_slot(self, timetable_service, sample_subject):
        slot = timetable_service.add_slot(sample_subject["id"], "Thursday", 4,
                                          year_group="9", term="Autumn")
        timetable_service.delete_slot(slot["id"])
        slots = timetable_service.get_timetable(year_group="9", term="Autumn")
        assert not any(s["id"] == slot["id"] for s in slots)

    def test_clear_timetable(self, timetable_service, sample_subject):
        timetable_service.add_slot(sample_subject["id"], "Friday", 1,
                                   year_group="9", term="Spring")
        timetable_service.add_slot(sample_subject["id"], "Friday", 2,
                                   year_group="9", term="Spring")
        timetable_service.clear_timetable("9", "Spring")
        slots = timetable_service.get_timetable(year_group="9", term="Spring")
        assert len(slots) == 0


# ---------------------------------------------------------------------------
# Progress Service
# ---------------------------------------------------------------------------

class TestProgressService:
    def test_set_target(self, progress_service, sample_student, sample_subject):
        progress_service.set_target(
            student_id=sample_student["id"],
            subject_id=sample_subject["id"],
            academic_year="2025/2026",
            baseline_grade="5",
            target_grade="7",
        )
        progress = progress_service.list_student_progress(
            sample_student["id"], "2025/2026")
        assert len(progress) == 1
        assert progress[0]["target_grade"] == "7"

    def test_update_grade(self, progress_service, sample_student, sample_subject):
        progress_service.set_target(sample_student["id"], sample_subject["id"],
                                    baseline_grade="4", target_grade="6")
        progress = progress_service.list_student_progress(sample_student["id"])
        target_id = progress[0]["id"]
        progress_service.update_grade(target_id, "autumn", "5", effort="2",
                                      comment="Good start")
        updated = progress_service.list_student_progress(sample_student["id"])
        assert updated[0]["current_grade"] == "5"
        assert updated[0]["autumn_grade"] == "5"

    def test_list_subject_progress(self, progress_service, sample_student,
                                    sample_student_ks4, sample_subject):
        progress_service.set_target(sample_student["id"], sample_subject["id"],
                                    target_grade="7")
        progress_service.set_target(sample_student_ks4["id"], sample_subject["id"],
                                    target_grade="8")
        results = progress_service.list_subject_progress(sample_subject["id"])
        assert len(results) == 2

    def test_delete_target(self, progress_service, sample_student, sample_subject):
        progress_service.set_target(sample_student["id"], sample_subject["id"],
                                    target_grade="6")
        progress = progress_service.list_student_progress(sample_student["id"])
        progress_service.delete_target(progress[0]["id"])
        assert len(progress_service.list_student_progress(sample_student["id"])) == 0


# ---------------------------------------------------------------------------
# Pastoral Service
# ---------------------------------------------------------------------------

class TestPastoralService:
    def test_add_note(self, pastoral_service, sample_student):
        note = pastoral_service.add_note(
            student_id=sample_student["id"],
            content="Student seems withdrawn lately",
            note_type="welfare",
            recorded_by="Mrs Jones",
            follow_up_date="2026-04-01",
        )
        assert note["id"] > 0
        assert note["note_type"] == "welfare"

    def test_list_notes(self, pastoral_service, sample_student):
        pastoral_service.add_note(sample_student["id"], "Note A", note_type="general")
        pastoral_service.add_note(sample_student["id"], "Note B", note_type="welfare")
        notes = pastoral_service.list_notes(sample_student["id"], note_type="welfare")
        assert all(n["note_type"] == "welfare" for n in notes)

    def test_mark_follow_up_done(self, pastoral_service, sample_student):
        note = pastoral_service.add_note(sample_student["id"], "Need follow up",
                                         follow_up_date="2026-04-01")
        pastoral_service.mark_follow_up_done(note["id"])
        notes = pastoral_service.list_notes(sample_student["id"])
        found = [n for n in notes if n["id"] == note["id"]]
        assert found[0]["follow_up_done"] == 1

    def test_delete_note(self, pastoral_service, sample_student):
        note = pastoral_service.add_note(sample_student["id"], "To delete")
        pastoral_service.delete_note(note["id"])
        notes = pastoral_service.list_notes(sample_student["id"])
        assert not any(n["id"] == note["id"] for n in notes)

    def test_award_house_points(self, pastoral_service, sample_student):
        pastoral_service.award_house_points(
            sample_student["id"], "Gryffindor", points=5,
            reason="Excellent work", awarded_by="Mr Smith",
        )
        points = pastoral_service.student_house_points(sample_student["id"])
        assert len(points) == 1
        assert points[0]["points"] == 5

    def test_house_points_summary(self, pastoral_service, sample_student):
        pastoral_service.award_house_points(sample_student["id"], "Ravenclaw", points=10)
        summary = pastoral_service.house_points_summary()
        assert any(h["house"] == "Ravenclaw" for h in summary)


# ---------------------------------------------------------------------------
# Safeguarding Service
# ---------------------------------------------------------------------------

class TestSafeguardingService:
    def test_log_concern(self, safeguarding_service, sample_student):
        concern = safeguarding_service.log_concern(
            student_id=sample_student["id"],
            reported_by="Mrs Smith",
            concern_type="welfare",
            severity="medium",
            description="Unexplained absences",
            incident_date="2026-03-01",
        )
        assert concern["id"] > 0
        assert concern["severity"] == "medium"

    def test_list_concerns(self, safeguarding_service, sample_student):
        safeguarding_service.log_concern(sample_student["id"], "Teacher A",
                                         description="Concern 1")
        concerns = safeguarding_service.list_concerns(is_resolved=False)
        assert len(concerns) >= 1

    def test_resolve_concern(self, safeguarding_service, sample_student):
        concern = safeguarding_service.log_concern(
            sample_student["id"], "Teacher B", description="Test concern")
        safeguarding_service.resolve_concern(concern["id"], outcome="Resolved with parents")
        resolved = safeguarding_service.list_concerns(is_resolved=True)
        assert any(c["id"] == concern["id"] for c in resolved)

    def test_update_concern(self, safeguarding_service, sample_student):
        concern = safeguarding_service.log_concern(
            sample_student["id"], "Teacher C", severity="low")
        safeguarding_service.update_concern(concern["id"], severity="high",
                                            action_taken="Referred to DSL")
        # Verify by listing all unresolved
        concerns = safeguarding_service.list_concerns(is_resolved=False)
        found = [c for c in concerns if c["id"] == concern["id"]]
        assert found[0]["severity"] == "high"

    def test_delete_concern(self, safeguarding_service, sample_student):
        concern = safeguarding_service.log_concern(
            sample_student["id"], "Teacher D", description="To delete")
        safeguarding_service.delete_concern(concern["id"])
        concerns = safeguarding_service.list_concerns()
        assert not any(c["id"] == concern["id"] for c in concerns)


# ---------------------------------------------------------------------------
# SEND Service
# ---------------------------------------------------------------------------

class TestSENDService:
    def test_create_record(self, send_service, sample_student):
        record = send_service.create_record(
            student_id=sample_student["id"],
            sen_type="SEN Support",
            primary_need="Cognition & Learning",
            key_worker="Mrs SENCO",
            strategies="Extra time, visual aids",
        )
        assert record["id"] > 0
        assert record["sen_type"] == "SEN Support"

    def test_list_records(self, send_service, sample_student):
        send_service.create_record(sample_student["id"], sen_type="EHCP")
        records = send_service.list_records()
        assert len(records) >= 1

    def test_update_record(self, send_service, sample_student):
        record = send_service.create_record(sample_student["id"])
        send_service.update_record(record["id"], key_worker="New SENCO",
                                   strategies="Modified approach")
        records = send_service.list_records()
        found = [r for r in records if r["id"] == record["id"]]
        assert found[0]["key_worker"] == "New SENCO"

    def test_delete_record(self, send_service, sample_student):
        record = send_service.create_record(sample_student["id"])
        send_service.delete_record(record["id"])
        records = send_service.list_records()
        assert not any(r["id"] == record["id"] for r in records)

    def test_add_provision(self, send_service, sample_student):
        record = send_service.create_record(sample_student["id"])
        provision = send_service.add_provision(
            send_record_id=record["id"],
            provision_type="1:1 support",
            description="Weekly reading intervention",
            frequency="Weekly",
            staff_responsible="Mrs TA",
            start_date="2026-01-10",
        )
        assert provision["id"] > 0
        assert provision["provision_type"] == "1:1 support"

    def test_list_provisions(self, send_service, sample_student):
        record = send_service.create_record(sample_student["id"])
        send_service.add_provision(record["id"], "Speech therapy", frequency="Fortnightly")
        send_service.add_provision(record["id"], "Reading group", frequency="Daily")
        provisions = send_service.list_provisions(record["id"])
        assert len(provisions) == 2


# ---------------------------------------------------------------------------
# Rewards Service
# ---------------------------------------------------------------------------

class TestRewardsService:
    def test_award(self, rewards_service, sample_student):
        reward = rewards_service.award(
            student_id=sample_student["id"],
            reason="Outstanding homework",
            reward_type="merit",
            category="academic",
            points=5,
            awarded_by="Mr Maths",
        )
        assert reward["id"] > 0
        assert reward["points"] == 5

    def test_list_rewards(self, rewards_service, sample_student):
        rewards_service.award(sample_student["id"], "Good effort", reward_type="commendation")
        items = rewards_service.list_rewards(student_id=sample_student["id"])
        assert len(items) >= 1

    def test_delete_reward(self, rewards_service, sample_student):
        reward = rewards_service.award(sample_student["id"], "To remove")
        rewards_service.delete_reward(reward["id"])
        items = rewards_service.list_rewards(student_id=sample_student["id"])
        assert not any(r["id"] == reward["id"] for r in items)

    def test_student_totals(self, rewards_service, sample_student):
        rewards_service.award(sample_student["id"], "Test", points=3)
        rewards_service.award(sample_student["id"], "Test 2", points=7)
        totals = rewards_service.student_totals()
        assert len(totals) >= 1
        assert totals[0]["total_points"] == 10

    def test_leaderboard(self, rewards_service, sample_student, sample_student_ks4):
        rewards_service.award(sample_student["id"], "A", points=10)
        rewards_service.award(sample_student_ks4["id"], "B", points=20)
        board = rewards_service.leaderboard(limit=5)
        assert len(board) == 2
        assert board[0]["total_points"] >= board[1]["total_points"]


# ---------------------------------------------------------------------------
# Admissions Service
# ---------------------------------------------------------------------------

class TestAdmissionsService:
    def test_create_application(self, admissions_service):
        app = admissions_service.create_application(
            first_name="Tom",
            last_name="Applicant",
            year_group="7",
            parent_name="Mrs Applicant",
            parent_email="parent@example.com",
        )
        assert app["id"] > 0
        assert app["applicant_first_name"] == "Tom"
        assert app["status"] == "received"

    def test_list_applications(self, admissions_service):
        admissions_service.create_application("Alice", "One", "7", "Parent One")
        admissions_service.create_application("Bob", "Two", "8", "Parent Two")
        apps = admissions_service.list_applications(year_group="7")
        assert any(a["applicant_first_name"] == "Alice" for a in apps)

    def test_update_status(self, admissions_service):
        app = admissions_service.create_application("Eve", "Test", "9", "Parent")
        admissions_service.update_status(app["id"], "offered", decision_by="Head")
        apps = admissions_service.list_applications()
        found = [a for a in apps if a["id"] == app["id"]]
        assert found[0]["status"] == "offered"
        assert found[0]["decision_by"] == "Head"

    def test_delete_application(self, admissions_service):
        app = admissions_service.create_application("Del", "Test", "7", "Parent")
        admissions_service.delete_application(app["id"])
        apps = admissions_service.list_applications()
        assert not any(a["id"] == app["id"] for a in apps)

    def test_status_summary(self, admissions_service):
        admissions_service.create_application("A", "One", "7", "P1")
        admissions_service.create_application("B", "Two", "7", "P2")
        summary = admissions_service.status_summary()
        assert any(s["status"] == "received" for s in summary)


# ---------------------------------------------------------------------------
# Finance Service
# ---------------------------------------------------------------------------

class TestFinanceService:
    def test_add_transaction_income(self, finance_service):
        txn = finance_service.add_transaction(
            transaction_type="income",
            category="government_funding",
            amount=50000.00,
            description="Annual funding allocation",
        )
        assert txn["id"] > 0
        assert txn["amount"] == 50000.00

    def test_add_transaction_expense(self, finance_service):
        txn = finance_service.add_transaction(
            transaction_type="expense",
            category="supplies",
            amount=1200.50,
            description="Textbooks for Year 9",
        )
        assert txn["transaction_type"] == "expense"

    def test_list_transactions(self, finance_service):
        finance_service.add_transaction("income", "donations", 500.00)
        finance_service.add_transaction("expense", "equipment", 300.00)
        items = finance_service.list_transactions(transaction_type="income")
        assert all(t["transaction_type"] == "income" for t in items)

    def test_delete_transaction(self, finance_service):
        txn = finance_service.add_transaction("income", "other_income", 100.00)
        finance_service.delete_transaction(txn["id"])
        items = finance_service.list_transactions()
        assert not any(t["id"] == txn["id"] for t in items)

    def test_get_summary(self, finance_service):
        finance_service.add_transaction("income", "tuition_fees", 10000.00)
        finance_service.add_transaction("expense", "salaries", 4000.00)
        summary = finance_service.get_summary()
        assert summary["total_income"] >= 10000.00
        assert summary["total_expense"] >= 4000.00
        assert summary["balance"] == summary["total_income"] - summary["total_expense"]

    def test_set_budget(self, finance_service):
        budget = finance_service.set_budget("Maths", 15000.00, notes="FY 2025/26")
        assert budget["id"] > 0
        assert budget["allocated"] == 15000.00

    def test_list_budgets(self, finance_service):
        finance_service.set_budget("Science", 12000.00, academic_year="2025/2026")
        budgets = finance_service.list_budgets(academic_year="2025/2026")
        assert any(b["department"] == "Science" for b in budgets)

    def test_update_budget_spent(self, finance_service):
        budget = finance_service.set_budget("English", 10000.00)
        finance_service.update_budget_spent(budget["id"], 3500.00)
        budgets = finance_service.list_budgets()
        found = [b for b in budgets if b["id"] == budget["id"]]
        assert found[0]["spent"] == 3500.00

    def test_delete_budget(self, finance_service):
        budget = finance_service.set_budget("Art", 5000.00)
        finance_service.delete_budget(budget["id"])
        budgets = finance_service.list_budgets()
        assert not any(b["id"] == budget["id"] for b in budgets)


# ---------------------------------------------------------------------------
# Announcement Service
# ---------------------------------------------------------------------------

class TestAnnouncementService:
    def test_create(self, announcement_service):
        ann = announcement_service.create(
            title="School Closure",
            body="School closed for snow day",
            audience="all",
            priority="urgent",
            created_by="admin",
        )
        assert ann["id"] > 0
        assert ann["priority"] == "urgent"

    def test_list_announcements(self, announcement_service):
        announcement_service.create("Test 1", "Body 1", audience="staff")
        # New announcements default to published=1
        items = announcement_service.list_announcements(audience="staff")
        assert any(a["title"] == "Test 1" for a in items)

    def test_toggle_publish(self, announcement_service):
        ann = announcement_service.create("Draft", "Draft body")
        # Toggle to unpublish
        announcement_service.toggle_publish(ann["id"])
        items = announcement_service.list_announcements(published_only=True)
        assert not any(a["id"] == ann["id"] for a in items)
        # Toggle back to publish
        announcement_service.toggle_publish(ann["id"])
        items = announcement_service.list_announcements(published_only=True)
        assert any(a["id"] == ann["id"] for a in items)

    def test_delete(self, announcement_service):
        ann = announcement_service.create("To Delete", "Body")
        announcement_service.delete(ann["id"])
        items = announcement_service.list_announcements(published_only=False)
        assert not any(a["id"] == ann["id"] for a in items)


# ---------------------------------------------------------------------------
# Calendar Service
# ---------------------------------------------------------------------------

class TestCalendarService:
    def test_add_event(self, calendar_service):
        event = calendar_service.add_event(
            title="Sports Day",
            date="2026-07-10",
            event_type="sports_day",
            location="Playing Fields",
            is_whole_school=True,
            created_by="admin",
        )
        assert event["id"] > 0
        assert event["event_type"] == "sports_day"

    def test_list_events(self, calendar_service):
        calendar_service.add_event("INSET Day", "2026-09-01", event_type="inset_day")
        calendar_service.add_event("Year 9 Trip", "2026-06-15", event_type="trip",
                                   year_group="9")
        events = calendar_service.list_events(event_type="inset_day")
        assert all(e["event_type"] == "inset_day" for e in events)

    def test_delete_event(self, calendar_service):
        event = calendar_service.add_event("To Remove", "2026-12-01")
        calendar_service.delete_event(event["id"])
        events = calendar_service.list_events()
        assert not any(e["id"] == event["id"] for e in events)


# ---------------------------------------------------------------------------
# Parents Evening Service
# ---------------------------------------------------------------------------

class TestParentsEveningService:
    def test_create_event(self, parents_evening_service):
        event = parents_evening_service.create_event(
            title="Year 9 Parents Evening",
            date="2026-03-20",
            year_group="9",
            start_time="16:00",
            end_time="19:00",
            slot_duration_minutes=5,
        )
        assert event["id"] > 0
        assert event["slot_duration_minutes"] == 5

    def test_list_events(self, parents_evening_service):
        parents_evening_service.create_event("PE Event", "2026-04-01", year_group="10")
        events = parents_evening_service.list_events()
        assert len(events) >= 1

    def test_book_slot(self, parents_evening_service, sample_student):
        event = parents_evening_service.create_event("Booking Test", "2026-05-01")
        slot = parents_evening_service.book_slot(
            event_id=event["id"],
            teacher="Mr Smith",
            student_id=sample_student["id"],
            time_slot="16:05",
            parent_name="Mrs Doe",
        )
        assert slot["id"] > 0
        assert slot["teacher"] == "Mr Smith"

    def test_list_slots(self, parents_evening_service, sample_student):
        event = parents_evening_service.create_event("Slot List Test", "2026-05-10")
        parents_evening_service.book_slot(event["id"], "Ms Jones",
                                          sample_student["id"], "16:10")
        slots = parents_evening_service.list_slots(event["id"])
        assert len(slots) == 1

    def test_cancel_slot(self, parents_evening_service, sample_student):
        event = parents_evening_service.create_event("Cancel Test", "2026-05-15")
        slot = parents_evening_service.book_slot(event["id"], "Mr Adams",
                                                  sample_student["id"], "17:00")
        parents_evening_service.cancel_slot(slot["id"])
        slots = parents_evening_service.list_slots(event["id"])
        assert not any(s["id"] == slot["id"] for s in slots)

    def test_double_booking_raises(self, parents_evening_service, sample_student,
                                    sample_student_ks4):
        event = parents_evening_service.create_event("Double Test", "2026-06-01")
        parents_evening_service.book_slot(event["id"], "Mr X",
                                          sample_student["id"], "16:30")
        from education_system.secondary_school.core.exceptions import ParentsEveningError
        with pytest.raises(ParentsEveningError, match="already booked"):
            parents_evening_service.book_slot(event["id"], "Mr X",
                                              sample_student_ks4["id"], "16:30")

    def test_delete_event(self, parents_evening_service):
        event = parents_evening_service.create_event("To Delete", "2026-07-01")
        parents_evening_service.delete_event(event["id"])
        events = parents_evening_service.list_events()
        assert not any(e["id"] == event["id"] for e in events)


# ---------------------------------------------------------------------------
# Asset Service
# ---------------------------------------------------------------------------

class TestAssetService:
    def test_add_asset(self, asset_service):
        asset = asset_service.add_asset(
            asset_tag="IT-001",
            name="Dell Laptop",
            category="IT",
            serial_number="SN123456",
            location="Room 101",
            purchase_cost=850.00,
        )
        assert asset["id"] > 0
        assert asset["asset_tag"] == "IT-001"

    def test_list_assets(self, asset_service):
        asset_service.add_asset("IT-002", "Projector", category="IT")
        asset_service.add_asset("FUR-001", "Desk", category="furniture")
        items = asset_service.list_assets(category="IT")
        assert all(a["category"] == "IT" for a in items)

    def test_update_asset(self, asset_service):
        asset = asset_service.add_asset("IT-003", "Keyboard")
        asset_service.update_asset(asset["id"], location="Room 202", condition="fair")
        items = asset_service.list_assets(search="Keyboard")
        found = [a for a in items if a["id"] == asset["id"]]
        assert found[0]["location"] == "Room 202"
        assert found[0]["condition"] == "fair"

    def test_delete_asset(self, asset_service):
        asset = asset_service.add_asset("DEL-001", "Old Monitor")
        asset_service.delete_asset(asset["id"])
        items = asset_service.list_assets()
        assert not any(a["id"] == asset["id"] for a in items)

    def test_asset_summary(self, asset_service):
        asset_service.add_asset("SUM-001", "Item A", category="IT", purchase_cost=500)
        asset_service.add_asset("SUM-002", "Item B", category="IT", purchase_cost=300)
        summary = asset_service.asset_summary()
        it_row = [s for s in summary if s["category"] == "IT"]
        assert it_row[0]["cnt"] >= 2


# ---------------------------------------------------------------------------
# Room Booking Service
# ---------------------------------------------------------------------------

class TestRoomBookingService:
    def test_book_room(self, room_booking_service):
        booking = room_booking_service.book_room(
            room="Hall A",
            date="2026-04-15",
            start_time="09:00",
            end_time="10:00",
            purpose="Assembly",
            booked_by="Mr Head",
        )
        assert booking["id"] > 0
        assert booking["room"] == "Hall A"

    def test_list_bookings(self, room_booking_service):
        room_booking_service.book_room("Lab 1", "2026-04-16", "10:00", "11:00", "Science")
        bookings = room_booking_service.list_bookings(room="Lab 1")
        assert len(bookings) >= 1

    def test_clash_detection(self, room_booking_service):
        room_booking_service.book_room("Room 1", "2026-05-01", "09:00", "10:00", "Meeting A")
        from education_system.secondary_school.core.exceptions import RoomBookingError
        with pytest.raises(RoomBookingError, match="already booked"):
            room_booking_service.book_room("Room 1", "2026-05-01", "09:30", "10:30", "Meeting B")

    def test_cancel_booking(self, room_booking_service):
        booking = room_booking_service.book_room("Room 2", "2026-05-05",
                                                  "14:00", "15:00", "Test")
        room_booking_service.cancel_booking(booking["id"])
        bookings = room_booking_service.list_bookings(room="Room 2", date="2026-05-05")
        found = [b for b in bookings if b["id"] == booking["id"]]
        assert found[0]["status"] == "cancelled"

    def test_delete_booking(self, room_booking_service):
        booking = room_booking_service.book_room("Room 3", "2026-06-01",
                                                  "08:00", "09:00", "Delete test")
        room_booking_service.delete_booking(booking["id"])
        bookings = room_booking_service.list_bookings()
        assert not any(b["id"] == booking["id"] for b in bookings)

    def test_get_rooms(self, room_booking_service):
        room_booking_service.book_room("Gym", "2026-06-10", "12:00", "13:00", "PE")
        rooms = room_booking_service.get_rooms()
        assert "Gym" in rooms


# ---------------------------------------------------------------------------
# HR Service
# ---------------------------------------------------------------------------

class TestHRService:
    def test_create_staff(self, hr_service):
        staff = hr_service.create_staff(
            first_name="Bob",
            last_name="Builder",
            email="bob@school.local",
            department="DT",
            job_title="Teacher",
            contract_type="permanent",
        )
        assert staff["id"] > 0
        assert staff["first_name"] == "Bob"
        assert staff["staff_id"].startswith("STF")

    def test_list_staff(self, hr_service, sample_staff):
        staff_list = hr_service.list_staff(department="Maths")
        assert any(s["id"] == sample_staff["id"] for s in staff_list)

    def test_get_staff(self, hr_service, sample_staff):
        found = hr_service.get_staff(sample_staff["id"])
        assert found["email"] == "alice.teacher@school.local"

    def test_update_staff(self, hr_service, sample_staff):
        updated = hr_service.update_staff(sample_staff["id"], department="Science",
                                          phone="07700900001")
        assert updated["department"] == "Science"

    def test_delete_staff(self, hr_service, sample_staff):
        hr_service.delete_staff(sample_staff["id"])
        assert hr_service.get_staff(sample_staff["id"]) is None

    def test_request_leave(self, hr_service, sample_staff):
        leave = hr_service.request_leave(
            staff_hr_id=sample_staff["id"],
            leave_type="annual",
            start_date="2026-08-01",
            end_date="2026-08-05",
            days=5,
            reason="Holiday",
        )
        assert leave["id"] > 0
        assert leave["status"] == "pending"

    def test_approve_leave(self, hr_service, sample_staff):
        leave = hr_service.request_leave(sample_staff["id"], "sick",
                                          "2026-03-10", "2026-03-11", days=2)
        hr_service.approve_leave(leave["id"], approved_by="Head Teacher")
        leaves = hr_service.list_leave(sample_staff["id"])
        found = [l for l in leaves if l["id"] == leave["id"]]
        assert found[0]["status"] == "approved"

    def test_reject_leave(self, hr_service, sample_staff):
        leave = hr_service.request_leave(sample_staff["id"], "annual",
                                          "2026-12-20", "2026-12-24", days=5)
        hr_service.reject_leave(leave["id"])
        leaves = hr_service.list_leave(sample_staff["id"])
        found = [l for l in leaves if l["id"] == leave["id"]]
        assert found[0]["status"] == "rejected"


# ---------------------------------------------------------------------------
# CPD Service
# ---------------------------------------------------------------------------

class TestCPDService:
    def test_add_record(self, cpd_service):
        record = cpd_service.add_record(
            staff_name="Alice Teacher",
            training_title="Safeguarding Level 2",
            date="2026-01-15",
            category="safeguarding",
            provider="Local Authority",
            duration_hours=6,
            cost=150.00,
            certificate=True,
        )
        assert record["id"] > 0
        assert record["category"] == "safeguarding"

    def test_list_records(self, cpd_service):
        cpd_service.add_record("Alice Teacher", "First Aid", "2026-02-01",
                               category="first_aid")
        cpd_service.add_record("Bob Builder", "IT Training", "2026-02-10",
                               category="ict")
        records = cpd_service.list_records(staff_name="Alice Teacher")
        assert all(r["staff_name"] == "Alice Teacher" for r in records)

    def test_delete_record(self, cpd_service):
        record = cpd_service.add_record("Test Staff", "To Delete", "2026-03-01")
        cpd_service.delete_record(record["id"])
        records = cpd_service.list_records()
        assert not any(r["id"] == record["id"] for r in records)

    def test_staff_summary(self, cpd_service):
        cpd_service.add_record("Alice Teacher", "Course A", "2026-01-01",
                               duration_hours=3)
        cpd_service.add_record("Alice Teacher", "Course B", "2026-02-01",
                               duration_hours=5)
        summary = cpd_service.staff_summary()
        alice = [s for s in summary if s["staff_name"] == "Alice Teacher"]
        assert alice[0]["courses"] == 2
        assert alice[0]["total_hours"] == 8


# ---------------------------------------------------------------------------
# Clubs Service (no conftest fixture — create inline)
# ---------------------------------------------------------------------------

class TestClubsService:
    def test_create_club(self, clubs_service):
        club = clubs_service.create_club(
            name="Chess Club",
            category="academic",
            day_of_week="Wednesday",
            teacher="Mr King",
            max_members=20,
        )
        assert club["id"] > 0
        assert club["name"] == "Chess Club"

    def test_list_clubs(self, clubs_service):
        clubs_service.create_club("Football", category="sport")
        clubs = clubs_service.list_clubs(status="active")
        assert any(c["name"] == "Football" for c in clubs)

    def test_add_and_list_members(self, clubs_service, sample_student):
        club = clubs_service.create_club("Drama Club", category="drama")
        clubs_service.add_member(club["id"], sample_student["id"])
        members = clubs_service.list_members(club["id"])
        assert len(members) == 1
        assert members[0]["first_name"] == "John"

    def test_remove_member(self, clubs_service, sample_student):
        club = clubs_service.create_club("Art Club")
        clubs_service.add_member(club["id"], sample_student["id"])
        members = clubs_service.list_members(club["id"])
        clubs_service.remove_member(members[0]["id"])
        assert clubs_service.member_count(club["id"]) == 0

    def test_member_count(self, clubs_service, sample_student, sample_student_ks4):
        club = clubs_service.create_club("Science Club")
        clubs_service.add_member(club["id"], sample_student["id"])
        clubs_service.add_member(club["id"], sample_student_ks4["id"])
        assert clubs_service.member_count(club["id"]) == 2

    def test_delete_club(self, clubs_service):
        club = clubs_service.create_club("Temp Club")
        clubs_service.delete_club(club["id"])
        clubs = clubs_service.list_clubs()
        assert not any(c["id"] == club["id"] for c in clubs)


# ---------------------------------------------------------------------------
# Library Service (no conftest fixture — create inline)
# ---------------------------------------------------------------------------

class TestLibraryService:
    def test_add_book(self, library_service):
        book = library_service.add_book(
            title="To Kill a Mockingbird",
            author="Harper Lee",
            isbn="978-0061120084",
            category="fiction",
            copies=3,
        )
        assert book["id"] > 0
        assert book["copies_total"] == 3
        assert book["copies_available"] == 3

    def test_list_books(self, library_service):
        library_service.add_book("1984", author="George Orwell", category="fiction")
        library_service.add_book("Biology GCSE", category="textbook")
        books = library_service.list_books(category="fiction")
        assert all(b["category"] == "fiction" for b in books)

    def test_search_books(self, library_service):
        library_service.add_book("Great Expectations", author="Charles Dickens")
        results = library_service.list_books(search="Dickens")
        assert len(results) >= 1

    def test_update_book(self, library_service):
        book = library_service.add_book("Test Book")
        library_service.update_book(book["id"], author="Updated Author",
                                    category="reference")
        books = library_service.list_books(search="Test Book")
        assert books[0]["author"] == "Updated Author"

    def test_delete_book(self, library_service):
        book = library_service.add_book("Delete Me")
        library_service.delete_book(book["id"])
        books = library_service.list_books()
        assert not any(b["id"] == book["id"] for b in books)

    def test_issue_and_return_loan(self, library_service, sample_student):
        book = library_service.add_book("Loan Test Book", copies=2)
        library_service.issue_loan(book["id"], sample_student["id"])
        loans = library_service.list_loans(status="borrowed")
        assert len(loans) >= 1
        # Check copies decremented
        books = library_service.list_books(search="Loan Test Book")
        assert books[0]["copies_available"] == 1
        # Return the book
        library_service.return_book(loans[0]["id"])
        books = library_service.list_books(search="Loan Test Book")
        assert books[0]["copies_available"] == 2

    def test_no_copies_available(self, library_service, sample_student):
        book = library_service.add_book("Single Copy", copies=1)
        library_service.issue_loan(book["id"], sample_student["id"])
        from education_system.secondary_school.core.exceptions import LibraryError
        with pytest.raises(LibraryError, match="No copies available"):
            library_service.issue_loan(book["id"], sample_student["id"])


# ---------------------------------------------------------------------------
# Transport Service (no conftest fixture — create inline)
# ---------------------------------------------------------------------------

class TestTransportService:
    def test_create_route(self, transport_service):
        route = transport_service.create_route(
            route_name="Route A",
            operator="Arriva",
            vehicle_type="bus",
            capacity=50,
            departure_time="07:30",
            return_time="15:45",
        )
        assert route["id"] > 0
        assert route["route_name"] == "Route A"

    def test_list_routes(self, transport_service):
        transport_service.create_route("Route B", vehicle_type="minibus")
        routes = transport_service.list_routes(status="active")
        assert any(r["route_name"] == "Route B" for r in routes)

    def test_add_and_list_stops(self, transport_service):
        route = transport_service.create_route("Route C")
        transport_service.add_stop(route["id"], "High Street", pickup_time="07:35",
                                   sort_order=1)
        transport_service.add_stop(route["id"], "Park Lane", pickup_time="07:40",
                                   sort_order=2)
        stops = transport_service.list_stops(route["id"])
        assert len(stops) == 2
        assert stops[0]["stop_name"] == "High Street"

    def test_assign_student(self, transport_service, sample_student):
        route = transport_service.create_route("Route D")
        transport_service.assign_student(route["id"], sample_student["id"])
        students = transport_service.list_route_students(route["id"])
        assert len(students) == 1

    def test_remove_student(self, transport_service, sample_student):
        route = transport_service.create_route("Route E")
        transport_service.assign_student(route["id"], sample_student["id"])
        students = transport_service.list_route_students(route["id"])
        transport_service.remove_student(students[0]["id"])
        assert transport_service.student_count(route["id"]) == 0

    def test_student_count(self, transport_service, sample_student, sample_student_ks4):
        route = transport_service.create_route("Route F")
        transport_service.assign_student(route["id"], sample_student["id"])
        transport_service.assign_student(route["id"], sample_student_ks4["id"])
        assert transport_service.student_count(route["id"]) == 2

    def test_delete_route(self, transport_service):
        route = transport_service.create_route("Route G")
        transport_service.delete_route(route["id"])
        routes = transport_service.list_routes()
        assert not any(r["id"] == route["id"] for r in routes)


# ---------------------------------------------------------------------------
# Medical Service (no conftest fixture — create inline)
# ---------------------------------------------------------------------------

class TestMedicalService:
    def test_add_condition(self, medical_service, sample_student):
        condition = medical_service.add_condition(
            student_id=sample_student["id"],
            condition_name="Asthma",
            severity="medium",
            medications="Salbutamol inhaler",
            care_plan="Use inhaler before PE",
        )
        assert condition["id"] > 0
        assert condition["condition_name"] == "Asthma"

    def test_list_conditions(self, medical_service, sample_student):
        medical_service.add_condition(sample_student["id"], "Nut Allergy",
                                      severity="high", allergies="Peanuts, tree nuts")
        conditions = medical_service.list_conditions(student_id=sample_student["id"])
        assert len(conditions) >= 1

    def test_delete_condition(self, medical_service, sample_student):
        cond = medical_service.add_condition(sample_student["id"], "Eczema")
        medical_service.delete_condition(cond["id"])
        conditions = medical_service.list_conditions(student_id=sample_student["id"])
        assert not any(c["id"] == cond["id"] for c in conditions)

    def test_log_incident(self, medical_service, sample_student):
        incident = medical_service.log_incident(
            student_id=sample_student["id"],
            description="Fell in playground",
            location="Playground",
            treatment="Ice pack applied",
            treated_by="Mrs Nurse",
            parent_notified=True,
        )
        assert incident["id"] > 0
        assert incident["parent_notified"] == 1

    def test_list_incidents(self, medical_service, sample_student):
        medical_service.log_incident(sample_student["id"], "Headache",
                                     incident_date="2026-03-15")
        incidents = medical_service.list_incidents(student_id=sample_student["id"])
        assert len(incidents) >= 1

    def test_delete_incident(self, medical_service, sample_student):
        incident = medical_service.log_incident(sample_student["id"], "Minor cut")
        medical_service.delete_incident(incident["id"])
        incidents = medical_service.list_incidents(student_id=sample_student["id"])
        assert not any(i["id"] == incident["id"] for i in incidents)
