"""Comprehensive tests for Primary School service layer.

Service fixtures are provided by conftest.py. Tests that instantiate
services inline also work — both patterns are supported.
"""

import pytest

from education_system.primary_school.modules.domain.academics.homework.services.homework_service import HomeworkService
from education_system.primary_school.modules.domain.academics.sats.services.sats_service import SATsService
from education_system.primary_school.modules.domain.academics.phonics.services.phonics_service import PhonicsService
from education_system.primary_school.modules.domain.academics.reading_records.services.reading_record_service import ReadingRecordService
from education_system.primary_school.modules.domain.academics.progress.services.progress_service import ProgressService
from education_system.primary_school.modules.domain.academics.timetable.services.timetable_service import TimetableService
from education_system.primary_school.modules.domain.pastoral_care.pastoral.services.pastoral_service import PastoralService
from education_system.primary_school.modules.domain.pastoral_care.safeguarding.services.safeguarding_service import SafeguardingService
from education_system.primary_school.modules.domain.pastoral_care.send.services.send_service import SENDService
from education_system.primary_school.modules.domain.admin.admissions.services.admissions_service import AdmissionsService
from education_system.primary_school.modules.domain.admin.finance.services.finance_service import FinanceService
from education_system.primary_school.modules.domain.communication.announcements.services.announcement_service import AnnouncementService
from education_system.primary_school.modules.domain.communication.calendar.services.calendar_service import CalendarService
from education_system.primary_school.modules.domain.communication.parents_evening.services.parents_evening_service import ParentsEveningService
from education_system.primary_school.modules.domain.pupil_life.clubs.services.club_service import ClubService
from education_system.primary_school.modules.domain.pupil_life.library.services.library_service import LibraryService
from education_system.primary_school.modules.domain.pupil_life.meals.services.meal_service import MealService
from education_system.primary_school.modules.domain.pupil_life.transport.services.transport_service import TransportService
from education_system.primary_school.modules.domain.pupil_life.medical.services.medical_service import MedicalService
from education_system.primary_school.modules.domain.facilities.assets.services.asset_service import AssetService
from education_system.primary_school.modules.domain.facilities.room_booking.services.room_booking_service import RoomBookingService
from education_system.primary_school.modules.domain.staff.hr.services.hr_service import HRService
from education_system.primary_school.modules.domain.staff.cpd.services.cpd_service import CPDService
from education_system.primary_school.core.exceptions import HomeworkError


# ── Homework ──────────────────────────────────────────────────────────────


class TestHomeworkService:
    def test_create_homework(self, db_path, sample_class, sample_subject):
        svc = HomeworkService(db_path)
        hw = svc.create_homework(
            title="Spelling List Week 1",
            class_name=sample_class["class_name"],
            due_date="2026-04-01",
            subject_code=sample_subject["subject_code"],
            description="Learn 10 spellings",
            set_by="STF0001",
        )
        assert hw["homework_id"] > 0
        assert hw["title"] == "Spelling List Week 1"

    def test_list_homework(self, db_path, sample_class, sample_subject):
        svc = HomeworkService(db_path)
        svc.create_homework(title="HW A", class_name=sample_class["class_name"],
                            due_date="2026-04-01", subject_code=sample_subject["subject_code"])
        svc.create_homework(title="HW B", class_name=sample_class["class_name"],
                            due_date="2026-04-02", subject_code=sample_subject["subject_code"])
        items = svc.list_homework(class_name=sample_class["class_name"])
        assert len(items) >= 2

    def test_get_homework(self, db_path, sample_class):
        svc = HomeworkService(db_path)
        hw = svc.create_homework(title="Reading", class_name=sample_class["class_name"],
                                 due_date="2026-04-05")
        fetched = svc.get_homework(hw["homework_id"])
        assert fetched is not None
        assert fetched["title"] == "Reading"

    def test_delete_homework(self, db_path, sample_class):
        svc = HomeworkService(db_path)
        hw = svc.create_homework(title="Delete Me", class_name=sample_class["class_name"],
                                 due_date="2026-04-01")
        assert svc.delete_homework(hw["homework_id"]) is True
        assert svc.get_homework(hw["homework_id"]) is None

    def test_record_submission(self, db_path, sample_class, sample_pupil_ks1):
        svc = HomeworkService(db_path)
        hw = svc.create_homework(title="Maths Sheet", class_name=sample_class["class_name"],
                                 due_date="2026-04-10")
        sub = svc.record_submission(hw["homework_id"], sample_pupil_ks1["pupil_id"],
                                    submitted_date="2026-04-09")
        assert sub["submission_id"] > 0
        assert sub["status"] == "Submitted"

    def test_get_submissions(self, db_path, sample_class, sample_pupil_ks1):
        svc = HomeworkService(db_path)
        hw = svc.create_homework(title="Art Project", class_name=sample_class["class_name"],
                                 due_date="2026-04-15")
        svc.record_submission(hw["homework_id"], sample_pupil_ks1["pupil_id"])
        subs = svc.get_submissions(hw["homework_id"])
        assert len(subs) == 1
        assert subs[0]["pupil_id"] == sample_pupil_ks1["pupil_id"]

    def test_add_teacher_feedback_with_sticker(self, db_path, sample_class, sample_pupil_ks1):
        svc = HomeworkService(db_path)
        hw = svc.create_homework(title="Writing", class_name=sample_class["class_name"],
                                 due_date="2026-04-20")
        sub = svc.record_submission(hw["homework_id"], sample_pupil_ks1["pupil_id"])
        fb = svc.add_teacher_feedback(sub["submission_id"], "Great work!", sticker="gold_star")
        assert fb["teacher_feedback"] == "Great work!"
        assert fb["sticker"] == "gold_star"

    def test_invalid_sticker_raises(self, db_path, sample_class, sample_pupil_ks1):
        svc = HomeworkService(db_path)
        hw = svc.create_homework(title="Test", class_name=sample_class["class_name"],
                                 due_date="2026-04-20")
        sub = svc.record_submission(hw["homework_id"], sample_pupil_ks1["pupil_id"])
        with pytest.raises(HomeworkError):
            svc.add_teacher_feedback(sub["submission_id"], "OK", sticker="invalid")

    def test_list_outstanding(self, db_path, sample_class, sample_pupil_ks1):
        svc = HomeworkService(db_path)
        hw1 = svc.create_homework(title="Outstanding HW", class_name=sample_class["class_name"],
                                  due_date="2026-05-01")
        hw2 = svc.create_homework(title="Done HW", class_name=sample_class["class_name"],
                                  due_date="2026-05-02")
        svc.record_submission(hw2["homework_id"], sample_pupil_ks1["pupil_id"])
        outstanding = svc.list_outstanding(sample_pupil_ks1["pupil_id"])
        hw_ids = [h["id"] for h in outstanding]
        assert hw1["homework_id"] in hw_ids
        assert hw2["homework_id"] not in hw_ids


# ── SATs ──────────────────────────────────────────────────────────────────


class TestSATsService:
    def test_record_result(self, db_path, sample_pupil_ks2):
        svc = SATsService(db_path)
        r = svc.record_result(
            pupil_id=sample_pupil_ks2["pupil_id"],
            academic_year="2025/26", key_stage="KS2",
            subject="English Reading", raw_score=38,
            scaled_score=105, outcome="Expected Standard",
        )
        assert r["result_id"] > 0

    def test_get_results(self, db_path, sample_pupil_ks2):
        svc = SATsService(db_path)
        svc.record_result(sample_pupil_ks2["pupil_id"], "2025/26", "KS2", "Maths",
                          raw_score=40, scaled_score=110, outcome="Higher Standard")
        results = svc.get_results(pupil_id=sample_pupil_ks2["pupil_id"])
        assert len(results) >= 1

    def test_update_result(self, db_path, sample_pupil_ks2):
        svc = SATsService(db_path)
        r = svc.record_result(sample_pupil_ks2["pupil_id"], "2025/26", "KS2", "GPS",
                              raw_score=30, scaled_score=99)
        updated = svc.update_result(r["result_id"], scaled_score=100,
                                    outcome="Expected Standard")
        assert updated["scaled_score"] == 100

    def test_delete_result(self, db_path, sample_pupil_ks2):
        svc = SATsService(db_path)
        r = svc.record_result(sample_pupil_ks2["pupil_id"], "2025/26", "KS2", "Science")
        assert svc.delete_result(r["result_id"]) is True
        assert svc.delete_result(r["result_id"]) is False

    def test_cohort_summary(self, db_path, sample_pupil_ks2, pupil_service):
        svc = SATsService(db_path)
        p2 = pupil_service.create_pupil(first_name="Zara", last_name="Khan",
                                        year_group="Year 6", date_of_birth="2015-01-01")
        svc.record_result(sample_pupil_ks2["pupil_id"], "2025/26", "KS2", "Maths",
                          outcome="Expected Standard")
        svc.record_result(p2["pupil_id"], "2025/26", "KS2", "Maths",
                          outcome="Higher Standard")
        summary = svc.get_cohort_summary("2025/26", "KS2")
        assert "Maths" in summary
        assert summary["Maths"]["total"] == 2


# ── Phonics ───────────────────────────────────────────────────────────────


class TestPhonicsService:
    def test_record_result_pass(self, db_path, sample_pupil_ks1):
        svc = PhonicsService(db_path)
        r = svc.record_result(sample_pupil_ks1["pupil_id"], "2025/26", "Year 1",
                              score=35, threshold=32)
        assert r["passed"] == 1

    def test_record_result_fail(self, db_path, sample_pupil_ks1):
        svc = PhonicsService(db_path)
        r = svc.record_result(sample_pupil_ks1["pupil_id"], "2025/26", "Year 1",
                              score=28, threshold=32)
        assert r["passed"] == 0

    def test_update_recalculates_passed(self, db_path, sample_pupil_ks1):
        svc = PhonicsService(db_path)
        r = svc.record_result(sample_pupil_ks1["pupil_id"], "2025/26", "Year 1",
                              score=28, threshold=32)
        updated = svc.update_result(r["result_id"], score=35)
        assert updated["passed"] == 1

    def test_delete_result(self, db_path, sample_pupil_ks1):
        svc = PhonicsService(db_path)
        r = svc.record_result(sample_pupil_ks1["pupil_id"], "2025/26", "Year 1", score=30)
        assert svc.delete_result(r["result_id"]) is True

    def test_cohort_summary(self, db_path, sample_pupil_ks1, pupil_service):
        svc = PhonicsService(db_path)
        p2 = pupil_service.create_pupil(first_name="Lily", last_name="Brown",
                                        year_group="Year 1", date_of_birth="2019-08-01")
        svc.record_result(sample_pupil_ks1["pupil_id"], "2025/26", "Year 1", score=35)
        svc.record_result(p2["pupil_id"], "2025/26", "Year 1", score=28)
        summary = svc.get_cohort_summary("2025/26", "Year 1")
        assert summary["total"] == 2
        assert summary["passed"] == 1
        assert summary["pass_rate"] == 50.0


# ── Reading Records ───────────────────────────────────────────────────────


class TestReadingRecordService:
    def test_record_reading(self, db_path, sample_pupil):
        svc = ReadingRecordService(db_path)
        r = svc.record_reading(
            pupil_id=sample_pupil["pupil_id"],
            book_title="The Gruffalo", book_level="Purple",
            pages_read=12, reading_date="2026-03-20",
            read_with="Parent", fluency="Good",
            comprehension="Good", recorded_by="STF0001",
        )
        assert r["record_id"] > 0
        assert r["book_title"] == "The Gruffalo"

    def test_get_records_with_date_range(self, db_path, sample_pupil):
        svc = ReadingRecordService(db_path)
        svc.record_reading(sample_pupil["pupil_id"], book_title="Book A",
                           reading_date="2026-03-01")
        svc.record_reading(sample_pupil["pupil_id"], book_title="Book B",
                           reading_date="2026-03-15")
        records = svc.get_records(sample_pupil["pupil_id"],
                                  date_from="2026-03-10", date_to="2026-03-20")
        assert len(records) == 1
        assert records[0]["book_title"] == "Book B"

    def test_update_record(self, db_path, sample_pupil):
        svc = ReadingRecordService(db_path)
        r = svc.record_reading(sample_pupil["pupil_id"], book_title="Old Title")
        updated = svc.update_record(r["record_id"], book_title="New Title")
        assert updated["book_title"] == "New Title"

    def test_delete_record(self, db_path, sample_pupil):
        svc = ReadingRecordService(db_path)
        r = svc.record_reading(sample_pupil["pupil_id"], book_title="Gone")
        assert svc.delete_record(r["record_id"]) is True
        assert svc.delete_record(r["record_id"]) is False


# ── Progress ──────────────────────────────────────────────────────────────


class TestProgressService:
    def test_record_progress(self, db_path, sample_pupil_ks1, sample_subject):
        svc = ProgressService(db_path)
        r = svc.record_progress(
            pupil_id=sample_pupil_ks1["pupil_id"],
            subject_code=sample_subject["subject_code"],
            term="Autumn", academic_year="2025/26",
            year_group="Year 1", baseline_level="Emerging",
            current_level="Developing", target_level="Expected",
        )
        assert r["progress_id"] > 0

    def test_get_progress_filtered(self, db_path, sample_pupil_ks1, sample_subject):
        svc = ProgressService(db_path)
        svc.record_progress(sample_pupil_ks1["pupil_id"], sample_subject["subject_code"],
                            "Autumn", "2025/26")
        svc.record_progress(sample_pupil_ks1["pupil_id"], sample_subject["subject_code"],
                            "Spring", "2025/26")
        results = svc.get_progress(pupil_id=sample_pupil_ks1["pupil_id"],
                                   term="Autumn")
        assert len(results) == 1

    def test_update_progress(self, db_path, sample_pupil_ks1, sample_subject):
        svc = ProgressService(db_path)
        r = svc.record_progress(sample_pupil_ks1["pupil_id"], sample_subject["subject_code"],
                                "Autumn", "2025/26", current_level="Emerging")
        updated = svc.update_progress(r["progress_id"], current_level="Expected",
                                      on_track=1)
        assert updated["current_level"] == "Expected"

    def test_delete_progress(self, db_path, sample_pupil_ks1, sample_subject):
        svc = ProgressService(db_path)
        r = svc.record_progress(sample_pupil_ks1["pupil_id"], sample_subject["subject_code"],
                                "Autumn", "2025/26")
        assert svc.delete_progress(r["progress_id"]) is True


# ── Timetable ─────────────────────────────────────────────────────────────


class TestTimetableService:
    def test_create_slot(self, db_path, sample_class, sample_subject):
        svc = TimetableService(db_path)
        s = svc.create_slot(
            class_name=sample_class["class_name"],
            subject_code=sample_subject["subject_code"],
            day_of_week="Monday", period=1,
            start_time="09:00", end_time="09:45",
            room="Room 3",
        )
        assert s["slot_id"] > 0

    def test_get_timetable(self, db_path, sample_class, sample_subject):
        svc = TimetableService(db_path)
        svc.create_slot(sample_class["class_name"], sample_subject["subject_code"],
                        "Monday", 1)
        svc.create_slot(sample_class["class_name"], sample_subject["subject_code"],
                        "Tuesday", 1)
        slots = svc.get_timetable(class_name=sample_class["class_name"],
                                  day_of_week="Monday")
        assert len(slots) == 1

    def test_delete_slot(self, db_path, sample_class, sample_subject):
        svc = TimetableService(db_path)
        s = svc.create_slot(sample_class["class_name"], sample_subject["subject_code"],
                            "Wednesday", 2)
        assert svc.delete_slot(s["slot_id"]) is True
        assert svc.delete_slot(s["slot_id"]) is False


# ── Pastoral ──────────────────────────────────────────────────────────────


class TestPastoralService:
    def test_create_note(self, db_path, sample_pupil):
        svc = PastoralService(db_path)
        note_id = svc.create_note(
            pupil_id=sample_pupil["pupil_id"],
            note_type="Welfare", subject="Home issues",
            details="Parents separating", recorded_by="STF0001",
            follow_up_required=1, follow_up_date="2026-04-01",
        )
        assert note_id > 0

    def test_get_notes(self, db_path, sample_pupil):
        svc = PastoralService(db_path)
        svc.create_note(sample_pupil["pupil_id"], "Welfare", "Test", "Details")
        notes = svc.get_notes(pupil_id=sample_pupil["pupil_id"])
        assert len(notes) >= 1

    def test_update_note(self, db_path, sample_pupil):
        svc = PastoralService(db_path)
        nid = svc.create_note(sample_pupil["pupil_id"], "Welfare", "X", "Y")
        result = svc.update_note(nid, status="Closed")
        assert result is True

    def test_delete_note(self, db_path, sample_pupil):
        svc = PastoralService(db_path)
        nid = svc.create_note(sample_pupil["pupil_id"], "Welfare", "X", "Y")
        assert svc.delete_note(nid) is True
        assert svc.delete_note(nid) is False


# ── Safeguarding ──────────────────────────────────────────────────────────


class TestSafeguardingService:
    def test_record_concern(self, db_path, sample_pupil):
        svc = SafeguardingService(db_path)
        cid = svc.record_concern(
            pupil_id=sample_pupil["pupil_id"],
            concern_type="Neglect", description="Arriving hungry",
            severity="Medium", reported_by="STF0001",
        )
        assert cid > 0

    def test_get_concerns(self, db_path, sample_pupil):
        svc = SafeguardingService(db_path)
        svc.record_concern(sample_pupil["pupil_id"], "Neglect", "Test", severity="High")
        concerns = svc.get_concerns(pupil_id=sample_pupil["pupil_id"],
                                    severity="High")
        assert len(concerns) >= 1

    def test_close_concern(self, db_path, sample_pupil):
        svc = SafeguardingService(db_path)
        cid = svc.record_concern(sample_pupil["pupil_id"], "Emotional", "Withdrawn")
        result = svc.close_concern(cid, outcome="Referred to CAMHS")
        assert result is True
        closed = svc.get_concerns(pupil_id=sample_pupil["pupil_id"], status="Closed")
        assert len(closed) >= 1

    def test_get_open_count(self, db_path, sample_pupil):
        svc = SafeguardingService(db_path)
        before = svc.get_open_count()
        svc.record_concern(sample_pupil["pupil_id"], "Physical", "Bruise")
        assert svc.get_open_count() == before + 1


# ── SEND ──────────────────────────────────────────────────────────────────


class TestSENDService:
    def test_create_record(self, db_path, sample_pupil):
        svc = SENDService(db_path)
        rid = svc.create_record(
            pupil_id=sample_pupil["pupil_id"],
            sen_status="SEN Support",
            primary_need="Speech, Language and Communication",
        )
        assert rid > 0

    def test_get_record(self, db_path, sample_pupil):
        svc = SENDService(db_path)
        svc.create_record(sample_pupil["pupil_id"], "EHCP", "ASD")
        rec = svc.get_record(sample_pupil["pupil_id"])
        assert rec is not None
        assert rec["sen_status"] == "EHCP"

    def test_list_records_filtered(self, db_path, sample_pupil, sample_pupil_ks1):
        svc = SENDService(db_path)
        svc.create_record(sample_pupil["pupil_id"], "SEN Support", "Dyslexia")
        svc.create_record(sample_pupil_ks1["pupil_id"], "EHCP", "ASD")
        records = svc.list_records(sen_status="EHCP")
        assert len(records) == 1

    def test_update_record(self, db_path, sample_pupil):
        svc = SENDService(db_path)
        svc.create_record(sample_pupil["pupil_id"], "SEN Support", "SEMH")
        result = svc.update_record(sample_pupil["pupil_id"],
                                   sen_status="EHCP", funding_band="Band 3")
        assert result is True

    def test_delete_record(self, db_path, sample_pupil):
        svc = SENDService(db_path)
        svc.create_record(sample_pupil["pupil_id"], "SEN Support", "Dyspraxia")
        assert svc.delete_record(sample_pupil["pupil_id"]) is True
        assert svc.get_record(sample_pupil["pupil_id"]) is None

    def test_add_provision(self, db_path, sample_pupil):
        svc = SENDService(db_path)
        svc.create_record(sample_pupil["pupil_id"], "SEN Support", "SLCN")
        pid = svc.add_provision(
            pupil_id=sample_pupil["pupil_id"],
            provision_type="Speech Therapy",
            description="Weekly 30-min sessions",
            frequency="Weekly", delivered_by="SALT",
            start_date="2026-01-10", review_date="2026-07-10",
        )
        assert pid > 0

    def test_get_provisions(self, db_path, sample_pupil):
        svc = SENDService(db_path)
        svc.create_record(sample_pupil["pupil_id"], "SEN Support", "SLCN")
        svc.add_provision(sample_pupil["pupil_id"], "Speech Therapy")
        provs = svc.get_provisions(pupil_id=sample_pupil["pupil_id"])
        assert len(provs) >= 1


# ── Admissions ────────────────────────────────────────────────────────────


class TestAdmissionsService:
    def test_create_application(self, db_path):
        svc = AdmissionsService(db_path)
        app = svc.create_application(
            first_name="Emma", last_name="Wilson",
            year_group_applied="Reception",
            parent_name="Kate Wilson",
            parent_email="kate@example.com",
        )
        assert app["id"] > 0
        assert app["status"] == "Pending"

    def test_get_application(self, db_path):
        svc = AdmissionsService(db_path)
        app = svc.create_application("Tom", "Brown", "Year 1")
        fetched = svc.get_application(app["id"])
        assert fetched["first_name"] == "Tom"

    def test_approve_application(self, db_path):
        svc = AdmissionsService(db_path)
        app = svc.create_application("Anna", "Green", "Reception")
        result = svc.approve_application(app["id"])
        assert result["status"] == "Approved"

    def test_reject_application(self, db_path):
        svc = AdmissionsService(db_path)
        app = svc.create_application("Ben", "White", "Year 2")
        result = svc.reject_application(app["id"])
        assert result["status"] == "Rejected"


# ── Finance ───────────────────────────────────────────────────────────────


class TestFinanceService:
    def test_record_transaction(self, db_path):
        svc = FinanceService(db_path)
        txn = svc.record_transaction(
            transaction_type="Income", description="Trip payment",
            amount=25.00, category="Trips",
            payment_method="Online", recorded_by="STF0001",
        )
        assert txn["id"] > 0
        assert txn["amount"] == 25.00

    def test_get_transactions_by_category(self, db_path):
        svc = FinanceService(db_path)
        svc.record_transaction("Income", "Trip A", 10.00, category="Trips")
        svc.record_transaction("Expense", "Supplies", 50.00, category="Resources")
        trips = svc.get_transactions(category="Trips")
        assert len(trips) >= 1
        assert all(t["category"] == "Trips" for t in trips)

    def test_create_budget(self, db_path):
        svc = FinanceService(db_path)
        b = svc.create_budget("PE Equipment", 5000.00,
                              category="PE", academic_year="2025/26")
        assert b["id"] > 0

    def test_get_budgets(self, db_path):
        svc = FinanceService(db_path)
        svc.create_budget("Library Books", 3000.00, academic_year="2025/26")
        budgets = svc.get_budgets(academic_year="2025/26")
        assert len(budgets) >= 1


# ── Announcements ─────────────────────────────────────────────────────────


class TestAnnouncementService:
    def test_create_announcement(self, db_path):
        svc = AnnouncementService(db_path)
        ann = svc.create_announcement(
            title="Sports Day", content="Sports day next Friday",
            audience="All", priority="High", created_by="STF0001",
        )
        assert ann["id"] > 0

    def test_list_announcements(self, db_path):
        svc = AnnouncementService(db_path)
        svc.create_announcement("Notice 1", "Content 1", audience="Staff")
        svc.create_announcement("Notice 2", "Content 2", audience="Parents")
        staff = svc.list_announcements(audience="Staff")
        assert len(staff) >= 1

    def test_delete_announcement(self, db_path):
        svc = AnnouncementService(db_path)
        ann = svc.create_announcement("Temp", "Temp content")
        assert svc.delete_announcement(ann["id"]) is True
        assert svc.get_announcement(ann["id"]) is None


# ── Calendar ──────────────────────────────────────────────────────────────


class TestCalendarService:
    def test_create_event(self, db_path):
        svc = CalendarService(db_path)
        ev = svc.create_event(
            title="Nativity Play", start_date="2026-12-15",
            end_date="2026-12-15", start_time="14:00", end_time="15:30",
            event_type="Performance", location="Main Hall",
            all_day=0, year_groups="Reception,Year 1",
        )
        assert ev["id"] > 0

    def test_list_events_by_type(self, db_path):
        svc = CalendarService(db_path)
        svc.create_event("Assembly", "2026-04-01", event_type="Assembly")
        svc.create_event("Trip", "2026-04-02", event_type="Trip")
        assemblies = svc.list_events(event_type="Assembly")
        assert len(assemblies) >= 1

    def test_delete_event(self, db_path):
        svc = CalendarService(db_path)
        ev = svc.create_event("Delete Me", "2026-06-01")
        assert svc.delete_event(ev["id"]) is True
        assert svc.get_event(ev["id"]) is None


# ── Parents Evening ───────────────────────────────────────────────────────


class TestParentsEveningService:
    def test_create_event(self, db_path):
        svc = ParentsEveningService(db_path)
        ev = svc.create_event(
            title="Spring Parents Evening",
            event_date="2026-04-10",
            start_time="15:30", end_time="19:00",
            slot_duration=10, year_groups="Year 1,Year 2",
        )
        assert ev["id"] > 0

    def test_create_and_book_slot(self, db_path, sample_pupil_ks1):
        hr = HRService(db_path)
        staff = hr.create_staff("Slot", "Teacher")
        svc = ParentsEveningService(db_path)
        ev = svc.create_event("PE Test", "2026-04-10")
        slot = svc.create_slot(ev["id"], staff["staff_id"], "15:30")
        assert slot["status"] == "Available"
        booked = svc.book_slot(slot["id"], sample_pupil_ks1["pupil_id"], "David Jones")
        assert booked is True

    def test_cancel_slot(self, db_path, sample_pupil_ks1):
        hr = HRService(db_path)
        staff = hr.create_staff("Cancel", "Teacher")
        svc = ParentsEveningService(db_path)
        ev = svc.create_event("Cancel Test", "2026-04-11")
        slot = svc.create_slot(ev["id"], staff["staff_id"], "16:00")
        svc.book_slot(slot["id"], sample_pupil_ks1["pupil_id"], "David Jones")
        assert svc.cancel_slot(slot["id"]) is True
        slots = svc.get_slots(ev["id"], status="Available")
        assert len(slots) >= 1

    def test_delete_event_cascades_slots(self, db_path):
        hr = HRService(db_path)
        staff = hr.create_staff("Delete", "Teacher")
        svc = ParentsEveningService(db_path)
        ev = svc.create_event("Delete PE", "2026-05-01")
        svc.create_slot(ev["id"], staff["staff_id"], "15:30")
        assert svc.delete_event(ev["id"]) is True
        slots = svc.get_slots(ev["id"])
        assert len(slots) == 0


# ── Clubs ─────────────────────────────────────────────────────────────────


class TestClubService:
    def test_create_club(self, db_path):
        svc = ClubService(db_path)
        c = svc.create_club(
            club_name="Art Club", day_of_week="Tuesday",
            start_time="15:15", end_time="16:15",
            location="Art Room", max_capacity=20,
            year_groups="Year 3,Year 4", term="Spring",
        )
        assert c["id"] > 0

    def test_add_and_get_members(self, db_path, sample_pupil_ks1):
        svc = ClubService(db_path)
        c = svc.create_club("Chess Club", day_of_week="Wednesday")
        svc.add_member(c["id"], sample_pupil_ks1["pupil_id"])
        members = svc.get_members(c["id"])
        assert len(members) == 1

    def test_remove_member(self, db_path, sample_pupil_ks1):
        svc = ClubService(db_path)
        c = svc.create_club("Music Club")
        svc.add_member(c["id"], sample_pupil_ks1["pupil_id"])
        assert svc.remove_member(c["id"], sample_pupil_ks1["pupil_id"]) is True
        assert len(svc.get_members(c["id"])) == 0

    def test_get_pupil_clubs(self, db_path, sample_pupil_ks1):
        svc = ClubService(db_path)
        c1 = svc.create_club("Club A")
        c2 = svc.create_club("Club B")
        svc.add_member(c1["id"], sample_pupil_ks1["pupil_id"])
        svc.add_member(c2["id"], sample_pupil_ks1["pupil_id"])
        clubs = svc.get_pupil_clubs(sample_pupil_ks1["pupil_id"])
        assert len(clubs) == 2

    def test_delete_club(self, db_path):
        svc = ClubService(db_path)
        c = svc.create_club("Temp Club")
        assert svc.delete_club(c["id"]) is True


# ── Library ───────────────────────────────────────────────────────────────


class TestLibraryService:
    def test_add_book(self, db_path):
        svc = LibraryService(db_path)
        b = svc.add_book(
            title="Charlie and the Chocolate Factory",
            author="Roald Dahl", isbn="978-0142410318",
            category="Fiction", reading_level="White",
            copies=3,
        )
        assert b["id"] > 0
        assert b["copies"] == 3

    def test_loan_and_return_book(self, db_path, sample_pupil_ks1):
        svc = LibraryService(db_path)
        b = svc.add_book("Test Book", copies=2)
        loan = svc.loan_book(b["id"], sample_pupil_ks1["pupil_id"],
                             due_date="2026-04-15")
        assert loan["id"] > 0
        loans = svc.get_loans(pupil_id=sample_pupil_ks1["pupil_id"])
        assert len(loans) >= 1
        assert svc.return_book(loan["id"]) is True

    def test_get_overdue_loans(self, db_path, sample_pupil_ks1):
        svc = LibraryService(db_path)
        b = svc.add_book("Overdue Book", copies=1)
        svc.loan_book(b["id"], sample_pupil_ks1["pupil_id"],
                      due_date="2020-01-01")
        overdue = svc.get_overdue_loans()
        assert len(overdue) >= 1

    def test_delete_book(self, db_path):
        svc = LibraryService(db_path)
        b = svc.add_book("Delete Me")
        assert svc.delete_book(b["id"]) is True

    def test_default_loan_days(self, db_path):
        assert LibraryService.DEFAULT_LOAN_DAYS == 14


# ── Meals ─────────────────────────────────────────────────────────────────


class TestMealService:
    def test_record_meal(self, db_path, sample_pupil):
        svc = MealService(db_path)
        m = svc.record_meal(
            pupil_id=sample_pupil["pupil_id"],
            date="2026-03-23", meal_type="Lunch",
            meal_choice="Hot Meal", entitlement="FSM",
            recorded_by="STF0001",
        )
        assert m["id"] > 0

    def test_get_meals(self, db_path, sample_pupil):
        svc = MealService(db_path)
        svc.record_meal(sample_pupil["pupil_id"], "2026-03-23", "Lunch")
        meals = svc.get_meals(pupil_id=sample_pupil["pupil_id"],
                              date="2026-03-23")
        assert len(meals) >= 1

    def test_daily_summary(self, db_path, sample_pupil, sample_pupil_ks1):
        svc = MealService(db_path)
        svc.record_meal(sample_pupil["pupil_id"], "2026-03-23", "Lunch",
                        entitlement="FSM")
        svc.record_meal(sample_pupil_ks1["pupil_id"], "2026-03-23", "Lunch",
                        entitlement="Paid")
        summary = svc.get_daily_summary("2026-03-23")
        assert len(summary) >= 1
        total = sum(s["count"] for s in summary)
        assert total == 2


# ── Transport ─────────────────────────────────────────────────────────────


class TestTransportService:
    def test_create_record(self, db_path, sample_pupil):
        svc = TransportService(db_path)
        r = svc.create_record(
            pupil_id=sample_pupil["pupil_id"],
            transport_type="Bus", route="Route 7",
            pickup_point="High Street", pickup_time="08:15",
            contact_name="Sarah Smith", contact_phone="07700900001",
        )
        assert r["id"] > 0

    def test_list_records(self, db_path, sample_pupil, sample_pupil_ks1):
        svc = TransportService(db_path)
        svc.create_record(sample_pupil["pupil_id"], "Bus", route="R1")
        svc.create_record(sample_pupil_ks1["pupil_id"], "Walk")
        bus_records = svc.list_records(transport_type="Bus")
        assert len(bus_records) >= 1

    def test_delete_record(self, db_path, sample_pupil):
        svc = TransportService(db_path)
        r = svc.create_record(sample_pupil["pupil_id"], "Car")
        assert svc.delete_record(r["id"]) is True


# ── Medical ───────────────────────────────────────────────────────────────


class TestMedicalService:
    def test_create_record(self, db_path, sample_pupil):
        svc = MedicalService(db_path)
        r = svc.create_record(
            pupil_id=sample_pupil["pupil_id"],
            condition="Asthma", medication="Salbutamol inhaler",
            dosage="2 puffs as needed",
            allergy="Peanuts", allergy_severity="Severe",
            emergency_protocol="Administer EpiPen",
            doctor_name="Dr Smith", doctor_phone="01onal",
        )
        assert r["id"] > 0

    def test_get_records(self, db_path, sample_pupil):
        svc = MedicalService(db_path)
        svc.create_record(sample_pupil["pupil_id"], condition="Eczema")
        records = svc.get_records(pupil_id=sample_pupil["pupil_id"])
        assert len(records) >= 1

    def test_get_allergies(self, db_path, sample_pupil):
        svc = MedicalService(db_path)
        svc.create_record(sample_pupil["pupil_id"], allergy="Dairy",
                          allergy_severity="Moderate")
        allergies = svc.get_allergies()
        assert len(allergies) >= 1
        assert any(a["allergy"] == "Dairy" for a in allergies)

    def test_delete_record(self, db_path, sample_pupil):
        svc = MedicalService(db_path)
        r = svc.create_record(sample_pupil["pupil_id"], condition="Test")
        assert svc.delete_record(r["id"]) is True


# ── Assets ────────────────────────────────────────────────────────────────


class TestAssetService:
    def test_create_asset(self, db_path):
        svc = AssetService(db_path)
        a = svc.create_asset(
            asset_name="Interactive Whiteboard",
            asset_type="IT Equipment", serial_number="IWB-001",
            location="Room 5", purchase_date="2025-09-01",
            purchase_cost=2500.00, condition="Good",
        )
        assert a["id"] > 0

    def test_list_assets(self, db_path):
        svc = AssetService(db_path)
        svc.create_asset("Laptop Cart", asset_type="IT Equipment")
        svc.create_asset("Football Goals", asset_type="PE Equipment")
        it_assets = svc.list_assets(asset_type="IT Equipment")
        assert len(it_assets) >= 1

    def test_delete_asset(self, db_path):
        svc = AssetService(db_path)
        a = svc.create_asset("Old Projector")
        assert svc.delete_asset(a["id"]) is True
        assert svc.get_asset(a["id"]) is None


# ── Room Bookings ─────────────────────────────────────────────────────────


class TestRoomBookingService:
    def test_create_booking(self, db_path):
        svc = RoomBookingService(db_path)
        b = svc.create_booking(
            room_name="Main Hall", booked_by="STF0001",
            booking_date="2026-04-15", start_time="09:00",
            end_time="10:00", purpose="Assembly",
        )
        assert b["id"] > 0

    def test_check_availability_conflict(self, db_path):
        svc = RoomBookingService(db_path)
        svc.create_booking("Main Hall", "STF0001", "2026-04-15",
                           "09:00", "10:00")
        available = svc.check_availability("Main Hall", "2026-04-15",
                                           "09:30", "10:30")
        assert available is False

    def test_check_availability_no_conflict(self, db_path):
        svc = RoomBookingService(db_path)
        svc.create_booking("Main Hall", "STF0001", "2026-04-15",
                           "09:00", "10:00")
        available = svc.check_availability("Main Hall", "2026-04-15",
                                           "10:00", "11:00")
        assert available is True

    def test_delete_booking(self, db_path):
        svc = RoomBookingService(db_path)
        b = svc.create_booking("Library", "STF0001", "2026-04-16",
                               "14:00", "15:00")
        assert svc.delete_booking(b["id"]) is True


# ── HR ────────────────────────────────────────────────────────────────────


class TestHRService:
    def test_create_staff(self, db_path):
        svc = HRService(db_path)
        s = svc.create_staff(
            first_name="Jane", last_name="Taylor",
            role="Teacher", email="jane.taylor@school.ac.uk",
            class_teacher_of="1A", department="KS1",
        )
        assert s["staff_id"].startswith("STF")
        assert s["role"] == "Teacher"

    def test_list_staff(self, db_path):
        svc = HRService(db_path)
        svc.create_staff("Alice", "Brown", role="Teacher")
        svc.create_staff("Bob", "Green", role="TA")
        teachers = svc.list_staff(role="Teacher")
        assert len(teachers) >= 1

    def test_delete_staff(self, db_path):
        svc = HRService(db_path)
        s = svc.create_staff("Temp", "Staff")
        assert svc.delete_staff(s["staff_id"]) is True
        assert svc.get_staff(s["staff_id"]) is None

    def test_record_and_approve_leave(self, db_path):
        svc = HRService(db_path)
        s = svc.create_staff("Leave", "Test")
        leave_id = svc.record_leave(
            s["staff_id"], "Annual", "2026-04-14", "2026-04-18",
            reason="Holiday",
        )
        assert leave_id > 0
        pending = svc.get_leave(staff_id=s["staff_id"], status="Pending")
        assert len(pending) == 1
        assert svc.approve_leave(leave_id, approved_by="admin") is True


# ── CPD ───────────────────────────────────────────────────────────────────


class TestCPDService:
    def test_create_record(self, db_path):
        hr = HRService(db_path)
        staff = hr.create_staff("CPD", "User")
        svc = CPDService(db_path)
        rid = svc.create_record(
            staff_id=staff["staff_id"],
            title="Phonics Training",
            provider="Read Write Inc",
            cpd_type="Course", hours=6,
            completion_date="2026-03-01",
            status="Completed",
        )
        assert rid > 0

    def test_get_records(self, db_path):
        hr = HRService(db_path)
        staff = hr.create_staff("CPD", "Getter")
        svc = CPDService(db_path)
        svc.create_record(staff["staff_id"], "Safeguarding Level 1",
                          status="Completed")
        svc.create_record(staff["staff_id"], "First Aid", status="Planned")
        completed = svc.get_records(staff_id=staff["staff_id"],
                                    status="Completed")
        assert len(completed) == 1

    def test_delete_record(self, db_path):
        hr = HRService(db_path)
        staff = hr.create_staff("CPD", "Deleter")
        svc = CPDService(db_path)
        rid = svc.create_record(staff["staff_id"], "Remove Me")
        assert svc.delete_record(rid) is True
        assert svc.delete_record(rid) is False
