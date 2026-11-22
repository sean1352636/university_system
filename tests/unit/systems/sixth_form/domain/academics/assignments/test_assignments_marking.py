"""Tests for coursework marking, moderation and rubrics.

Covers late penalties, access arrangements, rubric criteria,
per-criterion marking, grade boundaries, second marking and moderation,
standardisation samples, the mark audit trail, the comment bank and
bulk marking.
"""

from __future__ import annotations

import datetime as _dt
import sqlite3

import pytest

from education_system.systems.sixth_form.domain.academics.assignments import (
    assignments_marking as mk,
)
from education_system.systems.sixth_form.domain.academics.assignments import (
    crud as assignments_crud,
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
from education_system.systems.sixth_form.domain.pastoral.accessibility import (
    accessibility as access_mod,
)
from education_system import paths


def _day(offset: int = 0) -> str:
    return (_dt.date.today() + _dt.timedelta(days=offset)).isoformat()


def _seed_students(db_path: str, *first_names: str) -> list[str]:
    """Insert student rows straight into the temp DB.

    Deliberately not ``students.create_student``: that provisions a
    login in the shared platform ``auth.db``, which no test should
    touch. Going in by SQL keeps the fixture inside its temp database
    and gives predictable ids to assert against.
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
def mk_db(tmp_path, monkeypatch):
    """Marking, assignments, students and accessibility on one temp DB."""
    db_path = str(tmp_path / "sixthform.db")
    for mod in (assignments_store, mk, students_mod, subjects_mod, access_mod):
        monkeypatch.setattr(mod, "DB_PATH", db_path)
        monkeypatch.setattr(mod, "_DB_READY", False)
    monkeypatch.setattr(paths, "SIXTH_FORM_COURSEWORK_FILES_DIR",
                         tmp_path / "coursework_files")
    mk.init_db()
    access_mod.init_db()

    class NS:
        pass
    ns = NS()
    ns.students = _seed_students(db_path, "Ada", "Alan", "Grace",
                                  "Edsger")
    ns.s1, ns.s2, ns.s3, ns.s4 = ns.students
    ns.tmp = tmp_path
    return ns


def _assignment(**over):
    payload = {"title": "Source analysis", "subject_name": "History",
               "set_date": _day(-20), "due_date": _day(-4),
               "max_marks": 60, "status": "Set"}
    payload.update(over)
    return assignments_store.create_assignment(payload)


def _rubric(assignment, *sizes):
    return [mk.add_criterion(assignment.assignment_id,
                              {"code": f"AO{i}", "title": f"Objective {i}",
                               "max_marks": size})
            for i, size in enumerate(sizes, 1)]


# ── Late penalties (item 10) ───────────────────────────────────────

def test_penalty_scales_with_days_late(mk_db):
    a = _assignment(late_penalty_percent_per_day=10)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    assignments_submissions.submit_work(sub.submission_id, submitted_on=_day(-1))   # 3 late

    penalty = mk.compute_late_penalty(a, assignments_store.get_submission(
        sub.submission_id))

    assert penalty.days_late == 3
    assert penalty.percent == 30
    assert penalty.apply_to(50) == 35.0


def test_penalty_respects_grace_days(mk_db):
    a = _assignment(late_penalty_percent_per_day=10,
                     late_penalty_grace_days=2)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    assignments_submissions.submit_work(sub.submission_id, submitted_on=_day(-1))   # 3 late

    penalty = mk.compute_late_penalty(a, assignments_store.get_submission(
        sub.submission_id))

    assert penalty.days_late == 3        # still reported as 3 late
    assert penalty.percent == 10         # but only 1 chargeable day


def test_penalty_is_capped(mk_db):
    a = _assignment(set_date=_day(-60), due_date=_day(-30),
                     late_penalty_percent_per_day=10,
                     late_penalty_cap_percent=40)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    assignments_submissions.submit_work(sub.submission_id, submitted_on=_day(0))

    penalty = mk.compute_late_penalty(a, assignments_store.get_submission(
        sub.submission_id))

    assert penalty.percent == 40
    assert penalty.capped is True


def test_raw_mark_is_preserved_under_penalty(mk_db):
    a = _assignment(late_penalty_percent_per_day=10)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    assignments_submissions.submit_work(sub.submission_id, submitted_on=_day(-2))   # 2 late

    out = assignments_crud.mark_submission(sub.submission_id, marks=50,
                              marked_by="JS")

    assert out.raw_marks == 50           # what the marker awarded
    assert out.marks == 40.0             # what counts
    assert out.penalty_percent == 20
    assert out.penalty_days == 2


def test_on_time_work_is_not_penalised(mk_db):
    a = _assignment(due_date=_day(5), late_penalty_percent_per_day=10)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    assignments_submissions.submit_work(sub.submission_id, submitted_on=_day(0))

    out = assignments_crud.mark_submission(sub.submission_id, marks=50)

    assert out.raw_marks == out.marks == 50
    assert out.penalty_percent is None


def test_penalty_clock_runs_from_the_extended_deadline(mk_db):
    a = _assignment(late_penalty_percent_per_day=10)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    assignments_submissions.grant_extension(sub.submission_id, _day(2), reason="Illness")
    assignments_submissions.submit_work(sub.submission_id, submitted_on=_day(0))

    out = assignments_crud.mark_submission(sub.submission_id, marks=50)

    assert out.marks == 50
    assert out.penalty_percent is None


def test_waiving_a_penalty_restores_the_raw_mark(mk_db):
    a = _assignment(late_penalty_percent_per_day=10)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    assignments_submissions.submit_work(sub.submission_id, submitted_on=_day(-2))
    assignments_crud.mark_submission(sub.submission_id, marks=50)

    waived = mk.waive_penalty(sub.submission_id,
                               reason="Server outage on the deadline",
                               waived_by="HoD")

    assert waived.penalty_waived is True
    assert waived.marks == 50
    assert waived.raw_marks == 50
    assert waived.penalty_percent is None


def test_restoring_a_penalty_reapplies_it(mk_db):
    a = _assignment(late_penalty_percent_per_day=10)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    assignments_submissions.submit_work(sub.submission_id, submitted_on=_day(-2))
    assignments_crud.mark_submission(sub.submission_id, marks=50)
    mk.waive_penalty(sub.submission_id, reason="Mistake")

    restored = mk.restore_penalty(sub.submission_id)

    assert restored.penalty_waived is False
    assert restored.marks == 40.0
    assert restored.raw_marks == 50


def test_waiver_needs_a_reason(mk_db):
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    with pytest.raises(assignments_models.ValidationError):
        mk.waive_penalty(sub.submission_id, reason="   ")


def test_no_policy_means_no_deduction(mk_db):
    a = _assignment(due_date=_day(-10))
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    assignments_submissions.submit_work(sub.submission_id, submitted_on=_day(0))

    out = assignments_crud.mark_submission(sub.submission_id, marks=50)

    assert out.marks == 50
    assert "no penalty policy" in mk.compute_late_penalty(
        a, out).message


# ── Access arrangements (item 11) ──────────────────────────────────

def _grant_access(student_id, name):
    return access_mod.create_accommodation(
        {"student_id": student_id, "category": "Exam Access",
         "name": name, "status": "Active"})


def test_extra_time_is_parsed_from_the_arrangement_name(mk_db):
    _grant_access(mk_db.s1, "25% extra time")
    _grant_access(mk_db.s1, "Scribe")

    assert mk.access_arrangements_for(mk_db.s1) == ["25% extra time",
                                                     "Scribe"]
    assert mk.extra_time_percent(mk_db.s1) == 25.0


def test_the_largest_extra_time_entitlement_wins(mk_db):
    _grant_access(mk_db.s1, "25% extra time")
    _grant_access(mk_db.s1, "50% extra time")
    assert mk.extra_time_percent(mk_db.s1) == 50.0


def test_students_without_arrangements_get_nothing(mk_db):
    assert mk.access_arrangements_for(mk_db.s2) == []
    assert mk.extra_time_percent(mk_db.s2) is None


def test_arrangements_without_extra_time_change_no_deadline(mk_db):
    _grant_access(mk_db.s1, "Word processor")
    a = _assignment()

    assert mk.extra_time_percent(mk_db.s1) is None
    assert mk.access_extension_days(a, mk_db.s1) == 0


def test_extra_time_becomes_extra_days_across_the_window(mk_db):
    _grant_access(mk_db.s1, "25% extra time")
    a = _assignment(set_date=_day(0), due_date=_day(20))

    # 25% of a 20-day window is 5 days.
    assert mk.access_extension_days(a, mk_db.s1) == 5


def test_extra_time_rounds_up_to_a_whole_day(mk_db):
    _grant_access(mk_db.s1, "25% extra time")
    a = _assignment(set_date=_day(0), due_date=_day(10))

    # 2.5 days rounds up — never round a student's entitlement down.
    assert mk.access_extension_days(a, mk_db.s1) == 3


def test_adding_a_student_applies_their_arrangements(mk_db):
    _grant_access(mk_db.s1, "50% extra time")
    a = _assignment(set_date=_day(0), due_date=_day(10))

    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)

    stored = assignments_store.get_submission(sub.submission_id)
    assert stored.extended_due_date == _day(15)
    assert "50% extra time" in (stored.extension_reason or "")
    assert stored.access_arrangements == "50% extra time"


def test_arrangements_can_be_switched_off_per_assignment(mk_db):
    _grant_access(mk_db.s1, "50% extra time")
    a = _assignment(set_date=_day(0), due_date=_day(10),
                     honour_access_arrangements=False)

    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)

    assert assignments_store.get_submission(sub.submission_id).extended_due_date is None


def test_applying_arrangements_does_not_overwrite_a_human_extension(mk_db):
    _grant_access(mk_db.s1, "25% extra time")
    a = _assignment(set_date=_day(0), due_date=_day(10),
                     honour_access_arrangements=False)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    assignments_submissions.grant_extension(sub.submission_id, _day(30), reason="Bereavement")

    a = assignments_store.update_assignment(a.assignment_id,
                              {"honour_access_arrangements": True})
    result = mk.apply_access_arrangements(a.assignment_id)

    assert result == {"eligible": 1, "granted": 0, "skipped": 1}
    assert assignments_store.get_submission(sub.submission_id).extended_due_date \
        == _day(30)


def test_applying_arrangements_is_idempotent(mk_db):
    _grant_access(mk_db.s1, "25% extra time")
    a = _assignment(set_date=_day(0), due_date=_day(10))
    assignments_crud.add_student(a.assignment_id, mk_db.s1)

    again = mk.apply_access_arrangements(a.assignment_id)

    assert again["granted"] == 0
    assert again["skipped"] == 1


# ── Rubric criteria (item 12) ──────────────────────────────────────

def test_criteria_are_ordered_and_totalled(mk_db):
    a = _assignment(max_marks=60)
    _rubric(a, 20, 25, 15)

    criteria = mk.list_criteria(a.assignment_id)

    assert [c.position for c in criteria] == [1, 2, 3]
    assert [c.code for c in criteria] == ["AO1", "AO2", "AO3"]
    total = mk.rubric_total(a.assignment_id)
    assert total.total_max == 60
    assert total.matches is True


def test_rubric_mismatch_is_reported_not_blocked(mk_db):
    a = _assignment(max_marks=60)
    _rubric(a, 20)

    total = mk.rubric_total(a.assignment_id)

    assert total.matches is False
    assert "but the assignment max is 60" in total.message


def test_criterion_needs_a_title_and_max_marks(mk_db):
    a = _assignment()
    with pytest.raises(assignments_models.ValidationError):
        mk.add_criterion(a.assignment_id, {"title": "", "max_marks": 10})
    with pytest.raises(assignments_models.ValidationError):
        mk.add_criterion(a.assignment_id, {"title": "AO1"})


def test_reorder_criteria(mk_db):
    a = _assignment()
    c1, c2, c3 = _rubric(a, 10, 10, 10)

    out = mk.reorder_criteria(a.assignment_id,
                               [c3.criterion_id, c1.criterion_id,
                                c2.criterion_id])

    assert [c.criterion_id for c in out] == [c3.criterion_id,
                                              c1.criterion_id,
                                              c2.criterion_id]


def test_reorder_rejects_a_partial_list(mk_db):
    a = _assignment()
    c1, _c2 = _rubric(a, 10, 10)
    with pytest.raises(assignments_models.ValidationError):
        mk.reorder_criteria(a.assignment_id, [c1.criterion_id])


def test_deleting_a_criterion_removes_its_marks(mk_db):
    a = _assignment()
    c1, c2 = _rubric(a, 30, 30)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    mk.set_criterion_mark(sub.submission_id, c1.criterion_id, marks=20)
    mk.set_criterion_mark(sub.submission_id, c2.criterion_id, marks=20)

    mk.delete_criterion(c1.criterion_id)

    remaining = mk.list_criterion_marks(sub.submission_id)
    assert [m.criterion_id for m in remaining] == [c2.criterion_id]


def test_deleting_an_assignment_removes_its_rubric(mk_db):
    a = _assignment()
    _rubric(a, 30, 30)

    assignments_store.delete_assignment(a.assignment_id)

    assert mk.list_criteria(a.assignment_id) == []


# ── Per-criterion marking (item 13) ────────────────────────────────

def test_criterion_marks_sum_to_the_total(mk_db):
    a = _assignment(max_marks=60)
    c1, c2, c3 = _rubric(a, 20, 25, 15)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)

    mk.set_criterion_mark(sub.submission_id, c1.criterion_id, marks=18)
    mk.set_criterion_mark(sub.submission_id, c2.criterion_id, marks=20)
    mk.set_criterion_mark(sub.submission_id, c3.criterion_id, marks=12)

    assert mk.criterion_total(sub.submission_id) == 50
    assert mk.criterion_coverage(sub.submission_id) == (3, 3)


def test_criterion_mark_cannot_exceed_the_criterion_max(mk_db):
    a = _assignment()
    c1, = _rubric(a, 20)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    with pytest.raises(assignments_models.ValidationError):
        mk.set_criterion_mark(sub.submission_id, c1.criterion_id,
                               marks=21)


def test_criterion_must_belong_to_the_same_assignment(mk_db):
    a1 = _assignment(title="One")
    a2 = _assignment(title="Two")
    other, = _rubric(a2, 20)
    sub = assignments_crud.add_student(a1.assignment_id, mk_db.s1)
    with pytest.raises(assignments_models.ValidationError, match="belongs to assignment"):
        mk.set_criterion_mark(sub.submission_id, other.criterion_id,
                               marks=5)


def test_criterion_marks_upsert(mk_db):
    a = _assignment()
    c1, = _rubric(a, 20)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)

    mk.set_criterion_mark(sub.submission_id, c1.criterion_id, marks=10)
    mk.set_criterion_mark(sub.submission_id, c1.criterion_id, marks=15)

    rows = mk.list_criterion_marks(sub.submission_id)
    assert len(rows) == 1
    assert rows[0].marks == 15


def test_first_and_second_markers_score_independently(mk_db):
    a = _assignment()
    c1, = _rubric(a, 20)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)

    mk.set_criterion_mark(sub.submission_id, c1.criterion_id, marks=12,
                           role="First")
    mk.set_criterion_mark(sub.submission_id, c1.criterion_id, marks=16,
                           role="Second")

    assert mk.criterion_total(sub.submission_id, role="First") == 12
    assert mk.criterion_total(sub.submission_id, role="Second") == 16


def test_an_incomplete_rubric_cannot_be_totalled(mk_db):
    a = _assignment()
    c1, _c2 = _rubric(a, 30, 30)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    mk.set_criterion_mark(sub.submission_id, c1.criterion_id, marks=20)

    with pytest.raises(assignments_models.ValidationError, match="Only 1 of 2"):
        mk.apply_criterion_total(sub.submission_id)

    out = mk.apply_criterion_total(sub.submission_id,
                                    require_complete=False)
    assert out.raw_marks == 20


def test_totalling_the_rubric_marks_the_submission(mk_db):
    a = _assignment(due_date=_day(5), max_marks=60)
    c1, c2 = _rubric(a, 30, 30)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    mk.set_criterion_mark(sub.submission_id, c1.criterion_id, marks=24)
    mk.set_criterion_mark(sub.submission_id, c2.criterion_id, marks=21)

    out = mk.apply_criterion_total(sub.submission_id, marked_by="JS")

    assert out.raw_marks == 45
    assert out.marks == 45
    assert out.status == "Returned"
    assert mk.get_mark(sub.submission_id, "First").marks == 45


# ── Grade boundaries (item 14) ─────────────────────────────────────

def test_percentage_defaults_apply_without_overrides(mk_db):
    a = _assignment(max_marks=100)

    assert mk.resolve_grade(a, 91) == (91.0, "A*")
    assert mk.resolve_grade(a, 65) == (65.0, "C")
    assert mk.resolve_grade(a, 12) == (12.0, "U")
    assert mk.resolve_grade(a, None) == (None, None)


def test_pinned_boundaries_win_over_percentages(mk_db):
    a = _assignment(max_marks=60)
    mk.set_grade_boundaries(a.assignment_id,
                             {"A*": 54, "A": 48, "B": 42, "C": 36})

    # 50/60 is 83% — an A by percentage, and an A by raw marks too.
    assert mk.resolve_grade(a, 50)[1] == "A"
    # 44/60 is 73% — a B by percentage; the pinned table also says B.
    assert mk.resolve_grade(a, 44)[1] == "B"
    # 40/60 is 67% — a C by percentage, and below the pinned C of 36?
    # No: 40 >= 36, so C. Same answer, reached from raw marks.
    assert mk.resolve_grade(a, 40)[1] == "C"


def test_partly_pinned_boundaries_fall_back_for_the_rest(mk_db):
    a = _assignment(max_marks=100)
    mk.set_grade_boundaries(a.assignment_id, {"A*": 95})

    assert mk.resolve_grade(a, 96)[1] == "A*"
    # Below the only pinned threshold, the percentage default decides.
    assert mk.resolve_grade(a, 82)[1] == "A"


def test_boundaries_must_descend(mk_db):
    a = _assignment(max_marks=60)
    with pytest.raises(assignments_models.ValidationError, match="cannot be above"):
        mk.set_grade_boundaries(a.assignment_id, {"A*": 40, "A": 50})


def test_boundaries_cannot_exceed_max_marks(mk_db):
    a = _assignment(max_marks=60)
    with pytest.raises(assignments_models.ValidationError, match="exceeds the assignment"):
        mk.set_grade_boundaries(a.assignment_id, {"A*": 70})


def test_boundaries_accept_letters_or_column_names(mk_db):
    a = _assignment(max_marks=60)
    out = mk.set_grade_boundaries(a.assignment_id,
                                   {"a_star": 54, "A": 48})
    assert out.a_star == 54
    assert out.a == 48


def test_marking_derives_the_grade_from_the_boundaries(mk_db):
    a = _assignment(due_date=_day(5), max_marks=60)
    mk.set_grade_boundaries(a.assignment_id, {"A*": 54, "A": 48})
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)

    out = assignments_crud.mark_submission(sub.submission_id, marks=55)

    assert out.grade == "A*"


def test_an_explicit_grade_overrides_the_boundaries(mk_db):
    a = _assignment(due_date=_day(5), max_marks=60)
    mk.set_grade_boundaries(a.assignment_id, {"A*": 54})
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)

    out = assignments_crud.mark_submission(sub.submission_id, marks=55, grade="B")

    assert out.grade == "B"


def test_clearing_boundaries_restores_percentages(mk_db):
    a = _assignment(max_marks=100)
    mk.set_grade_boundaries(a.assignment_id, {"A*": 95})

    assert mk.clear_grade_boundaries(a.assignment_id) is True
    assert mk.get_grade_boundaries(a.assignment_id) is None
    assert mk.resolve_grade(a, 92)[1] == "A*"


def test_the_grade_reflects_the_mark_after_penalty(mk_db):
    """A late piece is graded on what counts, not what was awarded."""
    a = _assignment(max_marks=60, late_penalty_percent_per_day=10)
    mk.set_grade_boundaries(a.assignment_id,
                             {"A*": 54, "A": 48, "B": 42, "C": 36})
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    assignments_submissions.submit_work(sub.submission_id, submitted_on=_day(-2))

    out = assignments_crud.mark_submission(sub.submission_id, marks=50)

    assert out.raw_marks == 50           # would have been an A
    assert out.marks == 40.0
    assert out.grade == "C"


# ── Second marking and moderation (item 15) ────────────────────────

def test_a_second_mark_does_not_change_the_submission(mk_db):
    a = _assignment(due_date=_day(5))
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    assignments_crud.mark_submission(sub.submission_id, marks=45)

    mk.record_mark(sub.submission_id, role="Second", marks=38,
                    marked_by="RT")

    assert assignments_store.get_submission(sub.submission_id).marks == 45


def test_discrepancy_and_tolerance(mk_db):
    a = _assignment(moderation_tolerance=4)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    mk.record_mark(sub.submission_id, role="First", marks=45)
    mk.record_mark(sub.submission_id, role="Second", marks=38)

    state = mk.moderation_state(sub.submission_id)

    assert state.discrepancy == 7
    assert state.is_double_marked is True
    assert state.needs_moderation is True


def test_agreement_inside_tolerance_needs_no_moderation(mk_db):
    a = _assignment(moderation_tolerance=5)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    mk.record_mark(sub.submission_id, role="First", marks=45)
    mk.record_mark(sub.submission_id, role="Second", marks=42)

    state = mk.moderation_state(sub.submission_id)

    assert state.discrepancy == 3
    assert state.needs_moderation is False


def test_no_tolerance_means_no_moderation_queue(mk_db):
    a = _assignment(moderation_tolerance=None)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    mk.record_mark(sub.submission_id, role="First", marks=60)
    mk.record_mark(sub.submission_id, role="Second", marks=10)

    assert mk.moderation_state(sub.submission_id).needs_moderation is False
    assert mk.list_for_moderation() == []


def test_moderation_queue_lists_only_disagreements(mk_db):
    a = _assignment(moderation_tolerance=4)
    close = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    far = assignments_crud.add_student(a.assignment_id, mk_db.s2)
    single = assignments_crud.add_student(a.assignment_id, mk_db.s3)
    for sub, first, second in ((close, 40, 42), (far, 40, 55)):
        mk.record_mark(sub.submission_id, role="First", marks=first)
        mk.record_mark(sub.submission_id, role="Second", marks=second)
    mk.record_mark(single.submission_id, role="First", marks=30)

    queue = mk.list_for_moderation(assignment_id=a.assignment_id)

    assert [m.submission_id for m in queue] == [far.submission_id]


def test_resolving_moderation_sets_the_final_mark(mk_db):
    a = _assignment(due_date=_day(5), moderation_tolerance=4)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    mk.record_mark(sub.submission_id, role="First", marks=40)
    mk.record_mark(sub.submission_id, role="Second", marks=50)

    out = mk.resolve_moderation(sub.submission_id, marks=45,
                                 resolved_by="HoD",
                                 note="Agreed at the meeting")

    assert out.marks == 45
    assert out.raw_marks == 45
    state = mk.moderation_state(sub.submission_id)
    assert state.moderator == 45
    assert state.needs_moderation is False


def test_cannot_resolve_without_two_marks(mk_db):
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    mk.record_mark(sub.submission_id, role="First", marks=40)
    with pytest.raises(assignments_models.ValidationError, match="no first and second"):
        mk.resolve_moderation(sub.submission_id, marks=45)


def test_marks_cannot_exceed_the_assignment_max(mk_db):
    a = _assignment(max_marks=60)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    with pytest.raises(assignments_models.ValidationError, match="exceed max_marks"):
        mk.record_mark(sub.submission_id, role="First", marks=61)


def test_an_invalid_marker_role_is_refused(mk_db):
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    with pytest.raises(assignments_models.ValidationError, match="Marker role"):
        mk.record_mark(sub.submission_id, role="Third", marks=10)


# ── Standardisation samples (item 16) ──────────────────────────────

def test_flag_and_unflag_a_sample(mk_db):
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)

    flagged = mk.flag_sample(sub.submission_id, band="Top",
                              note="Strong exemplar", flagged_by="JS")

    assert flagged.sample_band == "Top"
    assert flagged.is_sample is True
    assert flagged.sample_on == _day(0)
    assert [s.submission_id for s in mk.list_samples()] \
        == [sub.submission_id]

    assert mk.unflag_sample(sub.submission_id).sample_band is None
    assert mk.list_samples() == []


def test_sample_band_is_validated(mk_db):
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    with pytest.raises(assignments_models.ValidationError, match="Sample band"):
        mk.flag_sample(sub.submission_id, band="Best")


def test_auto_sample_spans_the_range(mk_db):
    a = _assignment(due_date=_day(5), max_marks=60)
    marks = [55, 45, 30, 12]
    for student, value in zip(mk_db.students, marks):
        sub = assignments_crud.add_student(a.assignment_id, student)
        assignments_crud.mark_submission(sub.submission_id, marks=value)

    chosen = mk.auto_select_sample(a.assignment_id, per_band=1)

    bands = {s.sample_band for s in chosen}
    assert "Top" in bands and "Bottom" in bands
    assert max(s.marks for s in chosen) == 55
    assert min(s.marks for s in chosen) == 12


def test_auto_sample_replaces_the_previous_selection(mk_db):
    a = _assignment(due_date=_day(5))
    for student in mk_db.students[:2]:
        sub = assignments_crud.add_student(a.assignment_id, student)
        assignments_crud.mark_submission(sub.submission_id, marks=30)
    first = mk.auto_select_sample(a.assignment_id, per_band=1)

    second = mk.auto_select_sample(a.assignment_id, per_band=1)

    assert len(mk.list_samples(assignment_id=a.assignment_id)) \
        == len(second)
    assert len(first) == len(second)


def test_auto_sample_needs_marks(mk_db):
    a = _assignment()
    assignments_crud.add_student(a.assignment_id, mk_db.s1)
    with pytest.raises(assignments_models.ValidationError, match="Nothing is marked"):
        mk.auto_select_sample(a.assignment_id)


# ── Mark audit trail (item 17) ─────────────────────────────────────

def test_marking_writes_an_audit_row(mk_db):
    a = _assignment(due_date=_day(5), max_marks=60)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)

    assignments_crud.mark_submission(sub.submission_id, marks=45, marked_by="JS")

    rows = mk.list_mark_audit(submission_id=sub.submission_id)
    fields = {r.field for r in rows}
    assert {"raw_marks", "marks"} <= fields
    assert all(r.source == "manual" for r in rows)
    assert all(r.changed_by == "JS" for r in rows)


def test_audit_records_the_before_and_after(mk_db):
    a = _assignment(due_date=_day(5))
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    assignments_crud.mark_submission(sub.submission_id, marks=40)

    assignments_crud.mark_submission(sub.submission_id, marks=48)

    change = next(r for r in mk.list_mark_audit(
        submission_id=sub.submission_id, field="marks"))
    assert change.old_value == "40"
    assert change.new_value == "48"


def test_audit_distinguishes_its_sources(mk_db):
    a = _assignment(due_date=_day(5), moderation_tolerance=2)
    c1, = _rubric(a, 60)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    mk.set_criterion_mark(sub.submission_id, c1.criterion_id, marks=40)
    mk.apply_criterion_total(sub.submission_id)
    mk.record_mark(sub.submission_id, role="Second", marks=50)
    mk.resolve_moderation(sub.submission_id, marks=45)

    sources = {r.source for r in mk.list_mark_audit(
        submission_id=sub.submission_id)}

    assert "criterion" in sources
    assert "moderation" in sources


def test_audit_is_newest_first_and_scoped(mk_db):
    a = _assignment(due_date=_day(5))
    one = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    two = assignments_crud.add_student(a.assignment_id, mk_db.s2)
    assignments_crud.mark_submission(one.submission_id, marks=30)
    assignments_crud.mark_submission(two.submission_id, marks=40)

    scoped = mk.list_mark_audit(submission_id=two.submission_id)
    whole = mk.list_mark_audit(assignment_id=a.assignment_id)

    assert all(r.submission_id == two.submission_id for r in scoped)
    assert len(whole) > len(scoped)
    assert whole == sorted(whole, key=lambda r: r.audit_id, reverse=True)


def test_waiving_a_penalty_is_audited(mk_db):
    a = _assignment(late_penalty_percent_per_day=10)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    assignments_submissions.submit_work(sub.submission_id, submitted_on=_day(-2))
    assignments_crud.mark_submission(sub.submission_id, marks=50)

    mk.waive_penalty(sub.submission_id, reason="Outage", waived_by="HoD")

    rows = mk.list_mark_audit(submission_id=sub.submission_id)
    waiver = next(r for r in rows if r.field == "penalty_waived")
    assert waiver.reason == "Outage"
    assert waiver.changed_by == "HoD"
    assert any(r.source == "penalty" and r.field == "marks"
               for r in rows)


def test_an_unknown_audit_source_is_refused(mk_db):
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    with pytest.raises(assignments_models.ValidationError, match="Audit source"):
        mk.record_mark_change(sub.submission_id, field="marks",
                               old_value="1", new_value="2",
                               source="telepathy")


def test_a_mark_edited_outside_the_pipeline_is_still_audited(mk_db):
    a = _assignment(due_date=_day(5))
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    assignments_crud.mark_submission(sub.submission_id, marks=40)

    assignments_crud.update_submission(sub.submission_id, {"marks": 42})

    assert any(r.reason == "Edited directly" for r in
               mk.list_mark_audit(submission_id=sub.submission_id))


# ── Comment bank (item 18) ─────────────────────────────────────────

def test_comment_bank_crud(mk_db):
    c = mk.add_comment({"body": "Strong analysis throughout.",
                         "category": "Strength",
                         "subject_name": "History"})

    assert c.use_count == 0
    assert c.is_active is True

    updated = mk.update_comment(c.comment_id, {"category": "Target"})
    assert updated.category == "Target"
    assert mk.delete_comment(c.comment_id) is True
    assert mk.get_comment(c.comment_id) is None


def test_subject_filter_includes_shared_comments(mk_db):
    mk.add_comment({"body": "History-specific", "subject_name": "History"})
    mk.add_comment({"body": "Applies everywhere"})
    mk.add_comment({"body": "Physics-specific", "subject_name": "Physics"})

    bodies = {c.body for c in mk.list_comments(subject_name="History")}

    assert bodies == {"History-specific", "Applies everywhere"}


def test_comment_category_is_validated(mk_db):
    with pytest.raises(assignments_models.ValidationError, match="Category"):
        mk.add_comment({"body": "x", "category": "Vibes"})


def test_inactive_comments_are_hidden_by_default(mk_db):
    c = mk.add_comment({"body": "Retired wording"})
    mk.update_comment(c.comment_id, {"is_active": False})

    assert mk.list_comments() == []
    assert len(mk.list_comments(include_inactive=True)) == 1


def test_using_a_comment_counts_and_expands_it(mk_db):
    a = _assignment(due_date=_day(5), max_marks=60)
    mk.set_grade_boundaries(a.assignment_id, {"A*": 54, "A": 48})
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    assignments_crud.mark_submission(sub.submission_id, marks=55)
    c = mk.add_comment(
        {"body": "Well done {first_name} — {grade} ({marks}/{max_marks})."})

    text = mk.use_comment(c.comment_id, submission_id=sub.submission_id)

    assert text == "Well done Ada — A* (55/60)."
    assert mk.get_comment(c.comment_id).use_count == 1


def test_unknown_placeholders_are_left_alone(mk_db):
    a = _assignment()
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)

    text = mk.expand_comment("Hi {first_name}, see {mystery}.",
                              sub.submission_id)

    assert text == "Hi Ada, see {mystery}."


def test_the_bank_sorts_by_use(mk_db):
    rare = mk.add_comment({"body": "Rare"})
    common = mk.add_comment({"body": "Common"})
    for _ in range(3):
        mk.use_comment(common.comment_id)
    mk.use_comment(rare.comment_id)

    assert [c.body for c in mk.list_comments()] == ["Common", "Rare"]


# ── Bulk marking (item 19) ─────────────────────────────────────────

def test_bulk_mark_applies_a_whole_class(mk_db):
    a = _assignment(due_date=_day(5), max_marks=60)
    subs = [assignments_crud.add_student(a.assignment_id, s) for s in mk_db.students]

    result = mk.bulk_mark(a.assignment_id, [
        {"student_id": mk_db.s1, "marks": 50},
        {"submission_id": subs[1].submission_id, "marks": 40},
    ], marked_by="JS")

    assert result.applied == 2
    assert result.all_ok is True
    assert assignments_store.get_submission(subs[0].submission_id).marks == 50
    assert assignments_store.get_submission(subs[1].submission_id).marks == 40


def test_bulk_mark_reports_bad_rows_without_losing_good_ones(mk_db):
    a = _assignment(due_date=_day(5), max_marks=60)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)

    result = mk.bulk_mark(a.assignment_id, [
        {"student_id": mk_db.s1, "marks": 50},
        {"student_id": mk_db.s2, "marks": 10},      # not on this one
        {"student_id": mk_db.s1, "marks": 999},     # over max
    ])

    assert result.applied == 1
    assert result.failed == 2
    assert assignments_store.get_submission(sub.submission_id).marks == 50
    assert any("exceed max_marks" in o.message
               for o in result.outcomes if not o.ok)


def test_bulk_mark_can_refuse_to_write_anything_on_error(mk_db):
    a = _assignment(due_date=_day(5), max_marks=60)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)

    result = mk.bulk_mark(a.assignment_id, [
        {"student_id": mk_db.s1, "marks": 50},
        {"student_id": mk_db.s1, "marks": 999},
    ], stop_on_error=True)

    assert result.applied == 0
    assert assignments_store.get_submission(sub.submission_id).marks is None


def test_bulk_mark_applies_late_penalties(mk_db):
    a = _assignment(max_marks=60, late_penalty_percent_per_day=10)
    sub = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    assignments_submissions.submit_work(sub.submission_id, submitted_on=_day(-2))

    result = mk.bulk_mark(a.assignment_id,
                           [{"student_id": mk_db.s1, "marks": 50}])

    out = assignments_store.get_submission(sub.submission_id)
    assert out.raw_marks == 50
    assert out.marks == 40.0
    assert "late penalty" in result.outcomes[0].message


def test_marking_grid_carries_everything_the_marker_needs(mk_db):
    _grant_access(mk_db.s2, "25% extra time")
    a = _assignment(max_marks=60, late_penalty_percent_per_day=10,
                     moderation_tolerance=2)
    c1, = _rubric(a, 60)
    first = assignments_crud.add_student(a.assignment_id, mk_db.s1)
    second = assignments_crud.add_student(a.assignment_id, mk_db.s2)
    assignments_submissions.submit_work(first.submission_id, submitted_on=_day(-2))
    mk.set_criterion_mark(first.submission_id, c1.criterion_id, marks=45)
    mk.record_mark(first.submission_id, role="First", marks=45)
    mk.record_mark(first.submission_id, role="Second", marks=52)

    grid = {g.submission.submission_id: g
            for g in mk.marking_grid(a.assignment_id)}

    late = grid[first.submission_id]
    assert late.criterion_marks[c1.criterion_id] == 45
    assert late.penalty.days_late == 2
    assert late.moderation.needs_moderation is True
    assert late.student_name == "Ada Test"

    entitled = grid[second.submission_id]
    assert entitled.access_arrangements == ["25% extra time"]
