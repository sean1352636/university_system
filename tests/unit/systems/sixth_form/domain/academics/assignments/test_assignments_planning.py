"""Tests for coursework authoring, reuse and scheduling.

Covers specification metadata, templates, the department library,
cloning, differentiated variants, estimated-hours workload, set-date
publishing, due-date reminders, missing-work chasers, parent-portal
visibility and calendar integration.
"""

from __future__ import annotations

import datetime as _dt
import sqlite3

import pytest

from education_system.systems.sixth_form.domain.academics.academic_year import (
    academic_year as ay,
)
from education_system.systems.sixth_form.domain.academics.assignments import (
    assignments_assessment as assess,
    assignments_catalogue as cat,
    assignments_feedback as fb,
    assignments_marking as mk,
    assignments_scheduling as sched,
)
from education_system.systems.sixth_form.domain.academics.assignments import (
    crud as assignments_crud,
    integrity as assignments_integrity,
    models as assignments_models,
    store as assignments_store,
    submissions as assignments_submissions,
)
from education_system.systems.sixth_form.domain.academics.subjects import (
    subjects as subjects_mod,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as students_mod,
)
from education_system import paths


def _day(offset: int = 0) -> str:
    return (_dt.date.today() + _dt.timedelta(days=offset)).isoformat()


def _seed_students(db_path: str, *first_names: str) -> list[str]:
    """Insert student rows straight into the temp DB.

    Deliberately not ``students.create_student``: that provisions a
    login in the shared platform ``auth.db``, which no test should
    touch.
    """
    conn = sqlite3.connect(db_path)
    ids = []
    for i, name in enumerate(first_names, 1):
        student_id = f"T{i:04d}"
        conn.execute(
            "INSERT INTO students (student_id, first_name, last_name, "
            "email, subject_1, subject_2, subject_3, status) "
            "VALUES (?, ?, 'Test', ?, 'Mathematics', 'Physics', "
            "'Chemistry', 'Active')",
            (student_id, name, f"{student_id.lower()}@example.test"))
        ids.append(student_id)
    conn.commit()
    conn.close()
    return ids


@pytest.fixture
def plan_db(tmp_path, monkeypatch):
    """Every coursework module plus the academic year on one temp DB."""
    db_path = str(tmp_path / "sixthform.db")
    for mod in (assignments_store, mk, fb, assess, cat, sched, students_mod,
                 subjects_mod, ay):
        monkeypatch.setattr(mod, "DB_PATH", db_path)
        monkeypatch.setattr(mod, "_DB_READY", False)
    monkeypatch.setattr(paths, "SIXTH_FORM_COURSEWORK_FILES_DIR",
                         tmp_path / "coursework_files")
    cat.init_db()
    sched.init_db()
    assess.init_db()

    class NS:
        pass
    ns = NS()
    ns.students = _seed_students(db_path, "Ada", "Alan", "Grace")
    ns.s1, ns.s2, ns.s3 = ns.students
    ns.tmp = tmp_path
    ns.db = db_path
    return ns


def _assignment(**over):
    payload = {"title": "Source analysis", "subject_name": "History",
               "set_date": _day(-10), "due_date": _day(5),
               "max_marks": 60, "status": "Set"}
    payload.update(over)
    return assignments_store.create_assignment(payload)


# ── Specification metadata (item 30) ───────────────────────────────

def test_specification_is_recorded_and_formatted(plan_db):
    a = _assignment()

    out = cat.set_specification(
        a.assignment_id, qualification="A-Level", exam_board="AQA",
        spec_code="7042", unit_code="2S", component_code="NEA",
        objectives=["AO1", "AO2"])

    assert out.spec_reference == "AQA · 7042 · 2S · NEA"
    assert out.objective_list == ["AO1", "AO2"]
    assert out.qualification == "A-Level"


def test_objectives_accept_a_string_or_a_list(plan_db):
    a = _assignment()

    from_string = cat.set_specification(a.assignment_id,
                                         objectives="AO1, AO3 ,AO2")
    assert from_string.objective_list == ["AO1", "AO3", "AO2"]

    from_list = cat.set_specification(a.assignment_id,
                                       objectives=["AO4"])
    assert from_list.objective_list == ["AO4"]


def test_objective_coverage_counts_assignments(plan_db):
    first = _assignment(title="One")
    second = _assignment(title="Two")
    cat.set_specification(first.assignment_id, objectives=["AO1", "AO2"])
    cat.set_specification(second.assignment_id, objectives=["AO1"])

    coverage = cat.objective_coverage(subject_name="History")

    assert coverage == {"AO1": 2, "AO2": 1}


def test_specification_gaps_are_the_point(plan_db):
    a = _assignment()
    cat.set_specification(a.assignment_id, objectives=["AO1"])

    gaps = cat.specification_gaps("History", required=["AO1", "AO2",
                                                        "AO3"])

    assert gaps == ["AO2", "AO3"]


def test_find_by_specification(plan_db):
    aqa = _assignment(title="AQA piece")
    ocr = _assignment(title="OCR piece")
    cat.set_specification(aqa.assignment_id, exam_board="AQA",
                           spec_code="7042", objectives=["AO1"])
    cat.set_specification(ocr.assignment_id, exam_board="OCR")

    assert [x.assignment_id for x in
            cat.list_by_specification(exam_board="AQA")] \
        == [aqa.assignment_id]
    assert [x.assignment_id for x in
            cat.list_by_specification(objective="AO1")] \
        == [aqa.assignment_id]
    assert cat.list_by_specification(spec_code="9999") == []


# ── Templates and the library (items 31 and 32) ────────────────────

def test_saving_a_template_keeps_the_original_intact(plan_db):
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, plan_db.s1)

    out = cat.save_as_template(a.assignment_id,
                                template_name="House style essay")

    assert out.is_template is True
    assert out.template_name == "House style essay"
    assert out.shared_with_department is True
    # The original still has its cohort.
    assert [s.submission_id for s in
            assignments_store.list_submissions(assignment_id=a.assignment_id)] \
        == [sub.submission_id]


def test_library_lists_shared_and_template_assignments(plan_db):
    template = _assignment(title="Template")
    shared = _assignment(title="Shared")
    _assignment(title="Private")
    cat.save_as_template(template.assignment_id)
    cat.share_with_department(shared.assignment_id)

    entries = cat.list_library(subject_name="History")

    assert {e.assignment.title for e in entries} == {"Template",
                                                     "Shared"}
    assert cat.list_library(templates_only=True)[0].assignment.title \
        == "Template"


def test_library_ranks_by_reuse(plan_db):
    rare = _assignment(title="Rarely used")
    popular = _assignment(title="Popular")
    for a in (rare, popular):
        cat.save_as_template(a.assignment_id)
    for _ in range(3):
        cat.clone_assignment(popular.assignment_id)
    cat.clone_assignment(rare.assignment_id)

    entries = cat.list_library(subject_name="History")

    assert [e.assignment.title for e in entries][:2] \
        == ["Popular", "Rarely used"]


def test_library_search_matches_title_and_spec(plan_db):
    a = _assignment(title="Cold War essay")
    cat.set_specification(a.assignment_id, exam_board="AQA",
                           spec_code="7042")
    cat.save_as_template(a.assignment_id)

    assert len(cat.list_library(query="cold war")) == 1
    assert len(cat.list_library(query="7042")) == 1
    assert cat.list_library(query="nothing here") == []


def test_clone_copies_the_design(plan_db):
    source = _assignment(word_limit=2000, anonymous_marking=True)
    cat.set_specification(source.assignment_id, exam_board="AQA",
                           objectives=["AO1"])
    mk.add_criterion(source.assignment_id,
                      {"title": "Knowledge", "max_marks": 30})
    mk.add_criterion(source.assignment_id,
                      {"title": "Analysis", "max_marks": 30})
    mk.set_grade_boundaries(source.assignment_id, {"A*": 54, "A": 48})
    assess.add_question(source.assignment_id, {
        "prompt": "Year?", "options": "1945|1949",
        "answer_key": "1949"})
    cat.add_variant(source.assignment_id, {"name": "Scaffolded",
                                            "tier": "Scaffolded"})

    result = cat.clone_assignment(source.assignment_id,
                                   title="Next year's version",
                                   due_date=_day(30))

    clone = result.assignment
    assert clone.title == "Next year's version"
    assert result.criteria == 2
    assert result.questions == 1
    assert result.variants == 1
    assert clone.word_limit == 2000
    assert clone.anonymous_marking is True
    assert clone.exam_board == "AQA"
    assert clone.objective_list == ["AO1"]
    boundaries = mk.get_grade_boundaries(clone.assignment_id)
    assert boundaries is not None and boundaries.a_star == 54


def test_clone_never_copies_students_or_marks(plan_db):
    """A new run of an assignment starts empty."""
    source = _assignment()
    sub = assignments_crud.add_student(source.assignment_id, plan_db.s1)
    assignments_crud.mark_submission(sub.submission_id, marks=50)

    result = cat.clone_assignment(source.assignment_id)

    assert assignments_store.list_submissions(
        assignment_id=result.assignment.assignment_id) == []


def test_clone_is_not_itself_a_template(plan_db):
    source = _assignment()
    cat.save_as_template(source.assignment_id)

    clone = cat.clone_assignment(source.assignment_id).assignment

    assert clone.is_template is False
    assert clone.shared_with_department is False
    assert clone.status == "Draft"


def test_clone_records_its_source_and_bumps_reuse(plan_db):
    source = _assignment()

    clone = cat.clone_assignment(source.assignment_id).assignment

    assert clone.source_assignment_id == source.assignment_id
    assert assignments_store.get_assignment(source.assignment_id).times_reused == 1


def test_clone_lineage_walks_back(plan_db):
    first = _assignment(title="Original")
    second = cat.clone_assignment(first.assignment_id).assignment
    third = cat.clone_assignment(second.assignment_id).assignment

    lineage = cat.clone_lineage(third.assignment_id)

    assert [a.assignment_id for a in lineage] \
        == [second.assignment_id, first.assignment_id]
    assert cat.clone_lineage(first.assignment_id) == []


def test_clone_copies_teaching_material_not_submitted_work(plan_db):
    source = _assignment()
    brief = plan_db.tmp / "brief.pdf"
    brief.write_bytes(b"brief bytes")
    assignments_submissions.attach_file(source_path=brief,
                    assignment_id=source.assignment_id, kind="Brief")
    sub = assignments_crud.add_student(source.assignment_id, plan_db.s1)
    work = plan_db.tmp / "essay.docx"
    work.write_bytes(b"student work")
    assignments_submissions.submit_work(sub.submission_id, files=[work])

    result = cat.clone_assignment(source.assignment_id)

    copied = assignments_submissions.list_attachments(
        assignment_id=result.assignment.assignment_id)
    assert [a.filename for a in copied] == ["brief.pdf"]
    assert result.attachments == 1


def test_clone_refuses_an_impossible_date_range(plan_db):
    source = _assignment()
    with pytest.raises(assignments_models.ValidationError, match="before set date"):
        cat.clone_assignment(source.assignment_id, set_date=_day(10),
                              due_date=_day(1))


# ── Differentiated variants (item 33) ──────────────────────────────

def test_variants_are_named_per_assignment(plan_db):
    a = _assignment()
    cat.add_variant(a.assignment_id, {"name": "Higher",
                                       "tier": "Higher"})
    with pytest.raises(assignments_models.ValidationError, match="already has a variant"):
        cat.add_variant(a.assignment_id, {"name": "Higher"})


def test_variant_tier_is_validated(plan_db):
    a = _assignment()
    with pytest.raises(assignments_models.ValidationError, match="Variant tier"):
        cat.add_variant(a.assignment_id, {"name": "X", "tier": "Middle"})


def test_only_one_variant_is_default(plan_db):
    a = _assignment()
    first = cat.add_variant(a.assignment_id, {"name": "A",
                                               "is_default": True})
    second = cat.add_variant(a.assignment_id, {"name": "B",
                                                "is_default": True})

    assert cat.get_variant(first.variant_id).is_default is False
    assert cat.get_variant(second.variant_id).is_default is True


def test_issuing_a_variant_changes_the_brief_a_student_sees(plan_db):
    a = _assignment(brief="Standard brief")
    variant = cat.add_variant(a.assignment_id, {
        "name": "Scaffolded", "tier": "Scaffolded",
        "brief": "Use the writing frame"})
    sub = assignments_crud.add_student(a.assignment_id, plan_db.s1)

    assert cat.variant_brief(sub.submission_id) == "Standard brief"

    cat.assign_variant(sub.submission_id, variant.variant_id)

    assert cat.variant_brief(sub.submission_id) \
        == "Use the writing frame"


def test_a_variant_without_a_brief_falls_back(plan_db):
    a = _assignment(brief="Standard brief")
    variant = cat.add_variant(a.assignment_id, {"name": "Higher",
                                                 "tier": "Higher"})
    sub = assignments_crud.add_student(a.assignment_id, plan_db.s1)
    cat.assign_variant(sub.submission_id, variant.variant_id)

    assert cat.variant_brief(sub.submission_id) == "Standard brief"


def test_a_variant_must_belong_to_the_same_assignment(plan_db):
    a1 = _assignment(title="One")
    a2 = _assignment(title="Two")
    other = cat.add_variant(a2.assignment_id, {"name": "X"})
    sub = assignments_crud.add_student(a1.assignment_id, plan_db.s1)

    with pytest.raises(assignments_models.ValidationError, match="belongs to assignment"):
        cat.assign_variant(sub.submission_id, other.variant_id)


def test_default_variants_are_applied_in_bulk(plan_db):
    a = _assignment()
    variant = cat.add_variant(a.assignment_id, {"name": "Core",
                                                 "is_default": True})
    subs = [assignments_crud.add_student(a.assignment_id, s)
            for s in plan_db.students]
    cat.assign_variant(subs[0].submission_id, variant.variant_id)

    assert cat.assign_default_variants(a.assignment_id) == 2
    assert all(assignments_store.get_submission(s.submission_id).variant_id
               == variant.variant_id for s in subs)


def test_deleting_a_variant_returns_students_to_the_base(plan_db):
    a = _assignment(brief="Standard brief")
    variant = cat.add_variant(a.assignment_id, {"name": "Scaffolded",
                                                 "brief": "Frame"})
    sub = assignments_crud.add_student(a.assignment_id, plan_db.s1)
    cat.assign_variant(sub.submission_id, variant.variant_id)

    assert cat.delete_variant(variant.variant_id) is True

    assert assignments_store.get_submission(sub.submission_id).variant_id is None
    assert cat.variant_brief(sub.submission_id) == "Standard brief"


def test_variant_spread(plan_db):
    a = _assignment()
    variant = cat.add_variant(a.assignment_id, {"name": "Higher",
                                                 "tier": "Higher"})
    subs = [assignments_crud.add_student(a.assignment_id, s)
            for s in plan_db.students]
    cat.assign_variant(subs[0].submission_id, variant.variant_id)

    spread = cat.variant_spread(a.assignment_id)

    assert spread["Higher (Higher)"] == 1
    assert spread["(base brief)"] == 2


# ── Estimated hours and workload (item 34) ─────────────────────────

def test_workload_buckets_hours_into_the_due_week(plan_db):
    a = _assignment(due_date=_day(5), estimated_hours=6)
    assignments_crud.add_student(a.assignment_id, plan_db.s1)

    report = cat.student_workload(plan_db.s1)

    assert len(report.weeks) == 1
    assert report.total_hours == 6.0
    assert report.weeks[0].assignments[0][2] == 6.0


def test_a_variant_overrides_the_base_hours(plan_db):
    a = _assignment(estimated_hours=6)
    variant = cat.add_variant(a.assignment_id, {
        "name": "Scaffolded", "estimated_hours": 10})
    sub = assignments_crud.add_student(a.assignment_id, plan_db.s1)
    cat.assign_variant(sub.submission_id, variant.variant_id)

    assert cat.submission_hours(
        assignments_store.get_submission(sub.submission_id), a) == 10
    assert cat.student_workload(plan_db.s1).total_hours == 10.0


def test_workload_sums_across_subjects_in_one_week(plan_db):
    """The point of aggregating: no department sees the other's load."""
    for title, subject, hours in (("Essay", "History", 6),
                                   ("Lab", "History", 5),
                                   ("Project", "History", 4)):
        a = _assignment(title=title, subject_name=subject,
                         due_date=_day(3), estimated_hours=hours)
        assignments_crud.add_student(a.assignment_id, plan_db.s1)

    report = cat.student_workload(plan_db.s1)

    assert report.total_hours == 15.0
    assert len(report.weeks) == 1
    assert report.weeks[0].is_heavy is True


def test_assignments_without_estimates_are_skipped(plan_db):
    a = _assignment(estimated_hours=None)
    assignments_crud.add_student(a.assignment_id, plan_db.s1)

    report = cat.student_workload(plan_db.s1)

    assert report.weeks == []
    assert "No estimated hours" in report.message


def test_extension_moves_the_hours_to_the_new_week(plan_db):
    a = _assignment(due_date=_day(1), estimated_hours=8)
    sub = assignments_crud.add_student(a.assignment_id, plan_db.s1)
    before = cat.student_workload(plan_db.s1).weeks[0].week_start

    assignments_submissions.grant_extension(sub.submission_id, _day(15), reason="Illness")
    after = cat.student_workload(plan_db.s1).weeks[0].week_start

    assert after != before


def test_heavy_weeks_reports_the_overloaded(plan_db):
    for title, hours in (("A", 8), ("B", 8)):
        a = _assignment(title=title, due_date=_day(3),
                         estimated_hours=hours)
        assignments_crud.add_student(a.assignment_id, plan_db.s1)
    light = _assignment(title="C", due_date=_day(3), estimated_hours=2)
    assignments_crud.add_student(light.assignment_id, plan_db.s2)

    rows = cat.heavy_weeks()

    assert [student_id for student_id, _week in rows] == [plan_db.s1]


def test_assignment_hours_summary(plan_db):
    a = _assignment(estimated_hours=5)
    for student in plan_db.students:
        assignments_crud.add_student(a.assignment_id, student)

    summary = cat.assignment_hours_summary(a.assignment_id)

    assert summary["students"] == 3
    assert summary["total_hours"] == 15.0
    assert summary["average_hours"] == 5.0


# ── Set-date publishing (item 35) ──────────────────────────────────

def test_publishing_moves_a_draft_to_set(plan_db):
    a = _assignment(status="Draft")

    out = sched.publish_assignment(a.assignment_id, notify=False)

    assert out.status == "Set"
    assert out.published_on == _day(0)


def test_publishing_twice_changes_nothing(plan_db):
    a = _assignment(status="Draft")
    first = sched.publish_assignment(a.assignment_id, notify=False,
                                      published_on=_day(-3))

    second = sched.publish_assignment(a.assignment_id, notify=False)

    assert second.published_on == first.published_on == _day(-3)


def test_auto_publish_fires_on_the_set_date(plan_db):
    due = _assignment(title="Due", status="Draft", auto_publish=True,
                       set_date=_day(-1))
    later = _assignment(title="Later", status="Draft",
                         auto_publish=True, set_date=_day(5),
                         due_date=_day(30))
    manual = _assignment(title="Manual", status="Draft",
                          set_date=_day(-1))

    result = sched.publish_due(notify=False)

    assert result.actioned == 1
    assert assignments_store.get_assignment(due.assignment_id).status == "Set"
    assert assignments_store.get_assignment(later.assignment_id).status == "Draft"
    assert assignments_store.get_assignment(manual.assignment_id).status == "Draft"


def test_publish_sweep_is_idempotent(plan_db):
    _assignment(status="Draft", auto_publish=True, set_date=_day(-1))
    sched.publish_due(notify=False)

    again = sched.publish_due(notify=False)

    assert again.actioned == 0


def test_scheduled_lists_what_is_waiting(plan_db):
    waiting = _assignment(title="Waiting", status="Draft",
                           auto_publish=True, set_date=_day(5),
                           due_date=_day(30))
    _assignment(title="Ready", status="Draft", auto_publish=True,
                 set_date=_day(-1))

    assert [a.assignment_id for a in sched.list_scheduled()] \
        == [waiting.assignment_id]


# ── Due-date reminders (item 36) ───────────────────────────────────

def test_reminders_use_the_assignment_offsets(plan_db):
    a = _assignment(reminder_days="10,5")
    assert sched.reminder_offsets(a) == [10, 5]

    b = _assignment(title="Default")
    assert sched.reminder_offsets(b) == list(sched.DEFAULT_REMINDER_DAYS)


def test_a_reminder_fires_once_per_offset(plan_db):
    a = _assignment(due_date=_day(5), reminder_days="7,3,1")
    sub = assignments_crud.add_student(a.assignment_id, plan_db.s1)

    first = sched.sweep_reminders(notify=False)
    repeat = sched.sweep_reminders(notify=False)

    assert first.actioned == 1
    assert repeat.actioned == 0
    assert assignments_store.get_submission(sub.submission_id).reminders_sent_list \
        == [7]


def test_a_closer_offset_fires_later(plan_db):
    a = _assignment(due_date=_day(5), reminder_days="7,3,1")
    sub = assignments_crud.add_student(a.assignment_id, plan_db.s1)
    sched.sweep_reminders(notify=False)

    sched.sweep_reminders(today=_day(3), notify=False)

    assert assignments_store.get_submission(sub.submission_id).reminders_sent_list \
        == [7, 3]


def test_a_catch_up_run_sends_one_reminder_not_three(plan_db):
    """A job that did not run for a week must not fire three emails."""
    a = _assignment(due_date=_day(1), reminder_days="7,3,1")
    sub = assignments_crud.add_student(a.assignment_id, plan_db.s1)

    result = sched.sweep_reminders(notify=False)

    assert result.actioned == 1
    notices = sched.list_notices(submission_id=sub.submission_id)
    assert len(notices) == 1
    assert notices[0].offset_days == 1
    # The wider offsets are marked spent so they cannot fire late.
    assert assignments_store.get_submission(sub.submission_id).reminders_sent_list \
        == [7, 3, 1]


def test_submitted_work_is_not_reminded(plan_db):
    a = _assignment(due_date=_day(3), reminder_days="7")
    sub = assignments_crud.add_student(a.assignment_id, plan_db.s1)
    assignments_submissions.submit_work(sub.submission_id, submitted_on=_day(0))

    assert sched.sweep_reminders(notify=False).actioned == 0


def test_reminders_stop_after_the_deadline(plan_db):
    a = _assignment(due_date=_day(-2), reminder_days="7,3,1")
    assignments_crud.add_student(a.assignment_id, plan_db.s1)

    assert sched.sweep_reminders(notify=False).actioned == 0


def test_reminders_honour_an_extension(plan_db):
    a = _assignment(due_date=_day(-2), reminder_days="7")
    sub = assignments_crud.add_student(a.assignment_id, plan_db.s1)
    assignments_submissions.grant_extension(sub.submission_id, _day(4), reason="Illness")

    assert sched.sweep_reminders(notify=False).actioned == 1


def test_reminder_dry_run_sends_nothing(plan_db):
    a = _assignment(due_date=_day(5), reminder_days="7")
    sub = assignments_crud.add_student(a.assignment_id, plan_db.s1)

    result = sched.sweep_reminders(dry_run=True)

    assert result.scanned == 1
    assert result.actioned == 0
    assert assignments_store.get_submission(sub.submission_id).reminders_sent is None


# ── Missing-work chasers (item 37) ─────────────────────────────────

def test_chasing_escalates_one_step_at_a_time(plan_db):
    a = _assignment(due_date=_day(-5))
    sub = assignments_crud.add_student(a.assignment_id, plan_db.s1)

    first = sched.chase_submission(sub.submission_id, notify=False)

    assert first is not None
    assert first.level == 1
    assert first.recipient == "Student"
    assert assignments_store.get_submission(sub.submission_id).chase_level == 1


def test_chasing_stops_at_the_top_of_the_ladder(plan_db):
    a = _assignment(set_date=_day(-40), due_date=_day(-20))
    sub = assignments_crud.add_student(a.assignment_id, plan_db.s1)
    for offset in (0, 4, 8):
        sched.chase_submission(sub.submission_id, notify=False,
                                today=_day(offset))

    assert assignments_store.get_submission(sub.submission_id).chase_level == 3
    assert sched.chase_submission(sub.submission_id,
                                   notify=False) is None


def test_the_chase_interval_prevents_same_day_repeats(plan_db):
    a = _assignment(due_date=_day(-5))
    assignments_crud.add_student(a.assignment_id, plan_db.s1)
    sched.sweep_chasers(notify=False)

    again = sched.sweep_chasers(notify=False)

    assert again.actioned == 0
    assert again.skipped == 1


def test_the_chase_interval_expires(plan_db):
    a = _assignment(due_date=_day(-10))
    sub = assignments_crud.add_student(a.assignment_id, plan_db.s1)
    sched.sweep_chasers(notify=False)

    later = sched.sweep_chasers(
        today=_day(sched.CHASE_INTERVAL_DAYS), notify=False)

    assert later.actioned == 1
    assert assignments_store.get_submission(sub.submission_id).chase_level == 2


def test_chasing_can_be_switched_off(plan_db):
    a = _assignment(due_date=_day(-5), chase_enabled=False)
    assignments_crud.add_student(a.assignment_id, plan_db.s1)

    assert sched.sweep_chasers(notify=False).actioned == 0


def test_submitted_work_is_not_chased(plan_db):
    a = _assignment(due_date=_day(-5))
    sub = assignments_crud.add_student(a.assignment_id, plan_db.s1)
    assignments_submissions.submit_work(sub.submission_id, submitted_on=_day(-6))

    assert sched.sweep_chasers(notify=False).actioned == 0


def test_work_already_marked_missing_is_still_chased(plan_db):
    a = _assignment(due_date=_day(-5))
    sub = assignments_crud.add_student(a.assignment_id, plan_db.s1)
    assignments_integrity.sweep_late_submissions()
    assert assignments_store.get_submission(sub.submission_id).status == "Missing"

    assert sched.sweep_chasers(notify=False).actioned == 1


def test_resetting_a_chase_clears_the_ladder(plan_db):
    a = _assignment(due_date=_day(-5))
    sub = assignments_crud.add_student(a.assignment_id, plan_db.s1)
    sched.chase_submission(sub.submission_id, notify=False)

    out = sched.reset_chase(sub.submission_id)

    assert out.chase_level == 0
    assert out.last_chased_on is None


def test_escalation_report(plan_db):
    a = _assignment(due_date=_day(-10))
    chased = assignments_crud.add_student(a.assignment_id, plan_db.s1)
    assignments_crud.add_student(a.assignment_id, plan_db.s2)
    sched.chase_submission(chased.submission_id, notify=False)

    rows = sched.escalation_report()

    assert [sub.submission_id for sub, _level in rows] \
        == [chased.submission_id]
    assert rows[0][1] == "Student"


def test_notices_are_logged(plan_db):
    a = _assignment(due_date=_day(-5))
    sub = assignments_crud.add_student(a.assignment_id, plan_db.s1)
    sched.chase_submission(sub.submission_id, notify=False)

    notices = sched.list_notices(assignment_id=a.assignment_id,
                                 kind="chase")

    assert len(notices) == 1
    assert notices[0].label == "Chase level 1 (Student)"


# ── Parent portal visibility (item 38) ─────────────────────────────

def test_parent_view_shows_state_without_marks_until_released(plan_db):
    a = _assignment(due_date=_day(-2), release_policy="Manual")
    sub = assignments_crud.add_student(a.assignment_id, plan_db.s1)
    assignments_submissions.submit_work(sub.submission_id, submitted_on=_day(-3))
    assignments_crud.mark_submission(sub.submission_id, marks=45)

    held = sched.parent_view(plan_db.s1)[0]
    assert held.submitted is True
    assert held.marks is None
    assert held.state == "Handed in"

    fb.release_submission(sub.submission_id, notify=False)
    released = sched.parent_view(plan_db.s1)[0]
    assert released.marks == 45
    assert released.state == "Marked"


def test_parent_view_respects_the_visibility_flag(plan_db):
    visible = _assignment(title="Visible")
    hidden = _assignment(title="Hidden", parent_visible=False)
    for a in (visible, hidden):
        assignments_crud.add_student(a.assignment_id, plan_db.s1)

    titles = {v.title for v in sched.parent_view(plan_db.s1)}

    assert titles == {"Visible"}


def test_unpublished_drafts_are_hidden_from_parents(plan_db):
    draft = _assignment(title="Draft", status="Draft")
    assignments_crud.add_student(draft.assignment_id, plan_db.s1)

    assert sched.parent_view(plan_db.s1) == []

    sched.publish_assignment(draft.assignment_id, notify=False)
    assert len(sched.parent_view(plan_db.s1)) == 1


def test_parent_view_flags_missing_work(plan_db):
    a = _assignment(due_date=_day(-3))
    assignments_crud.add_student(a.assignment_id, plan_db.s1)

    view = sched.parent_view(plan_db.s1)[0]

    assert view.is_missing is True
    assert view.state == "Not handed in"


def test_parent_summary_counts(plan_db):
    handed = _assignment(title="In", due_date=_day(-3))
    missing = _assignment(title="Out", due_date=_day(-3))
    sub = assignments_crud.add_student(handed.assignment_id, plan_db.s1)
    assignments_submissions.submit_work(sub.submission_id, submitted_on=_day(-4))
    assignments_crud.add_student(missing.assignment_id, plan_db.s1)

    summary = sched.parent_summary(plan_db.s1)

    assert summary["total"] == 2
    assert summary["handed_in"] == 1
    assert summary["missing"] == 1


def test_visibility_can_be_toggled(plan_db):
    a = _assignment()
    assignments_crud.add_student(a.assignment_id, plan_db.s1)

    sched.set_parent_visibility(a.assignment_id, visible=False)
    assert sched.parent_view(plan_db.s1) == []

    sched.set_parent_visibility(a.assignment_id, visible=True)
    assert len(sched.parent_view(plan_db.s1)) == 1


# ── Calendar integration (item 39) ─────────────────────────────────

@pytest.fixture
def academic_year(plan_db):
    return ay.create_year({"name": "2026/27",
                            "start_date": _day(-200),
                            "end_date": _day(160)})


def test_pushing_to_the_calendar_creates_an_event(plan_db,
                                                  academic_year):
    a = _assignment(due_date=_day(10))

    event_id = sched.push_to_calendar(a.assignment_id)

    assert event_id is not None
    assert assignments_store.get_assignment(a.assignment_id).calendar_event_id \
        == event_id
    event = next(e for e in ay.list_events(year_id=academic_year.year_id)
                 if e.event_id == event_id)
    assert event.date == _day(10)
    assert a.title in event.name


def test_pushing_twice_reuses_the_event(plan_db, academic_year):
    a = _assignment(due_date=_day(10))
    first = sched.push_to_calendar(a.assignment_id)

    assert sched.push_to_calendar(a.assignment_id) == first
    assert len(ay.list_events(year_id=academic_year.year_id)) == 1


def test_an_assignment_without_a_due_date_is_not_placed(plan_db,
                                                         academic_year):
    a = _assignment(due_date=None)
    assert sched.push_to_calendar(a.assignment_id) is None


def test_a_date_outside_every_year_is_reported_not_failed(plan_db,
                                                           academic_year):
    a = _assignment(set_date=_day(300), due_date=_day(400))

    result = sched.sync_calendar()

    assert result.actioned == 0
    assert result.failures == 0
    assert result.skipped >= 1


def test_removing_from_the_calendar(plan_db, academic_year):
    a = _assignment(due_date=_day(10))
    sched.push_to_calendar(a.assignment_id)

    assert sched.remove_from_calendar(a.assignment_id) is True
    assert assignments_store.get_assignment(a.assignment_id).calendar_event_id is None


def test_calendar_sync_is_idempotent(plan_db, academic_year):
    _assignment(due_date=_day(10))
    first = sched.sync_calendar()

    second = sched.sync_calendar()

    assert first.actioned == 1
    assert second.actioned == 0
    assert second.skipped == 1


def test_deadline_clashes(plan_db):
    _assignment(title="One", subject_name="History", due_date=_day(3))
    _assignment(title="Two", subject_name="History", due_date=_day(4))
    _assignment(title="Alone", subject_name="History", due_date=_day(40))

    clashes = sched.deadline_clashes()

    assert len(clashes) == 1
    assert clashes[0]["count"] == 2


# ── The daily job ──────────────────────────────────────────────────

def test_daily_job_runs_every_sweep(plan_db, academic_year):
    scheduled = _assignment(title="Scheduled", status="Draft",
                             auto_publish=True, set_date=_day(-1),
                             due_date=_day(5), reminder_days="7")
    overdue = _assignment(title="Overdue", due_date=_day(-5))
    assignments_crud.add_student(scheduled.assignment_id, plan_db.s1)
    assignments_crud.add_student(overdue.assignment_id, plan_db.s2)

    results = sched.run_daily(notify=False)

    assert set(results) == {"published", "marked_missing", "reminders",
                            "chasers", "calendar"}
    assert results["published"].actioned == 1
    assert results["marked_missing"].actioned == 1
    assert results["chasers"].actioned == 1


def test_daily_job_is_safe_to_run_twice(plan_db, academic_year):
    a = _assignment(status="Draft", auto_publish=True,
                     set_date=_day(-1), due_date=_day(5),
                     reminder_days="7")
    assignments_crud.add_student(a.assignment_id, plan_db.s1)
    sched.run_daily(notify=False)

    second = sched.run_daily(notify=False)

    assert all(r.actioned == 0 for r in second.values())
