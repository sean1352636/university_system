"""Tests for coursework release, appeals and assessment instruments.

Covers marking turnaround, anonymous marking, feedback release,
acknowledgement, appeals, objective auto-marking, group assignments,
peer assessment, self-assessment and multi-part components.
"""

from __future__ import annotations

import datetime as _dt
import sqlite3

import pytest

from education_system.systems.sixth_form.domain.academics.assignments import (
    assignments as cw,
    assignments_assessment as assess,
    assignments_feedback as fb,
    assignments_marking as mk,
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
def wf_db(tmp_path, monkeypatch):
    """Every coursework module on one temp DB with four students."""
    db_path = str(tmp_path / "sixthform.db")
    for mod in (cw, mk, fb, assess, students_mod, subjects_mod):
        monkeypatch.setattr(mod, "DB_PATH", db_path)
        monkeypatch.setattr(mod, "_DB_READY", False)
    monkeypatch.setattr(paths, "SIXTH_FORM_COURSEWORK_FILES_DIR",
                         tmp_path / "coursework_files")
    assess.init_db()
    fb.init_db()

    class NS:
        pass
    ns = NS()
    ns.students = _seed_students(db_path, "Ada", "Alan", "Grace",
                                  "Edsger")
    ns.s1, ns.s2, ns.s3, ns.s4 = ns.students
    return ns


def _assignment(**over):
    payload = {"title": "Source analysis", "subject_name": "History",
               "set_date": _day(-20), "due_date": _day(-5),
               "max_marks": 50, "status": "Set"}
    payload.update(over)
    return cw.create_assignment(payload)


def _marked(assignment, student_id, marks, *, submitted=-5):
    """Add a student, submit and mark in one step."""
    sub = cw.add_student(assignment.assignment_id, student_id)
    cw.submit_work(sub.submission_id, submitted_on=_day(submitted))
    cw.mark_submission(sub.submission_id, marks=marks,
                        feedback="Solid work", marked_by="J Smith")
    return cw.get_submission(sub.submission_id)


# ── Feedback release (item 22) ─────────────────────────────────────

def test_immediate_policy_shows_a_mark_at_once(wf_db):
    a = _assignment(release_policy="Immediate")
    sub = _marked(a, wf_db.s1, 40)

    assert fb.is_visible_to_student(sub, a) is True


def test_manual_policy_holds_a_mark_back(wf_db):
    a = _assignment(release_policy="Manual")
    sub = _marked(a, wf_db.s1, 40)

    assert fb.is_visible_to_student(sub, a) is False
    assert [s.submission_id for s in fb.list_pending_release()] \
        == [sub.submission_id]


def test_on_date_policy_waits_for_the_date(wf_db):
    a = _assignment(release_policy="On date", release_on=_day(3))
    sub = _marked(a, wf_db.s1, 40)

    assert fb.is_visible_to_student(sub, a, today=_day(0)) is False
    assert fb.is_visible_to_student(sub, a, today=_day(3)) is True
    assert fb.is_visible_to_student(sub, a, today=_day(9)) is True


def test_on_date_policy_needs_a_date(wf_db):
    with pytest.raises(cw.ValidationError, match="release date"):
        _assignment(release_policy="On date")


def test_unmarked_work_is_never_visible(wf_db):
    a = _assignment(release_policy="Immediate")
    sub = cw.add_student(a.assignment_id, wf_db.s1)

    assert fb.is_visible_to_student(sub, a) is False


def test_releasing_a_class_publishes_together(wf_db):
    a = _assignment(release_policy="Manual")
    first = _marked(a, wf_db.s1, 40)
    second = _marked(a, wf_db.s2, 30)
    unmarked = cw.add_student(a.assignment_id, wf_db.s3)

    result = fb.release_assignment(a.assignment_id,
                                    released_by="HoD", notify=False)

    assert result.released == 2
    assert result.skipped_unmarked == 1
    for sub in (first, second):
        out = cw.get_submission(sub.submission_id)
        assert out.feedback_released is True
        assert out.feedback_released_on == _day(0)
        assert out.feedback_released_by == "HoD"
    assert cw.get_submission(
        unmarked.submission_id).feedback_released is False


def test_release_is_idempotent(wf_db):
    a = _assignment(release_policy="Manual")
    _marked(a, wf_db.s1, 40)
    fb.release_assignment(a.assignment_id, notify=False)

    again = fb.release_assignment(a.assignment_id, notify=False)

    assert again.released == 0
    assert again.already_released == 1


def test_releasing_nothing_to_release_is_refused(wf_db):
    a = _assignment(release_policy="Manual")
    sub = cw.add_student(a.assignment_id, wf_db.s1)
    with pytest.raises(cw.ValidationError, match="nothing to release"):
        fb.release_submission(sub.submission_id)


def test_a_result_can_be_withdrawn(wf_db):
    a = _assignment(release_policy="Manual")
    sub = _marked(a, wf_db.s1, 40)
    fb.release_submission(sub.submission_id, notify=False)

    out = fb.unrelease_submission(sub.submission_id)

    assert out.feedback_released is False
    assert out.feedback_released_on is None
    assert fb.is_visible_to_student(out, a) is False


def test_scheduled_release_publishes_only_what_is_due(wf_db):
    due = _assignment(title="Due", release_policy="On date",
                       release_on=_day(-1))
    later = _assignment(title="Later", release_policy="On date",
                         release_on=_day(5))
    due_sub = _marked(due, wf_db.s1, 40)
    later_sub = _marked(later, wf_db.s2, 30)

    result = fb.release_due()

    assert result.released == 1
    assert cw.get_submission(
        due_sub.submission_id).feedback_released is True
    assert cw.get_submission(
        later_sub.submission_id).feedback_released is False


# ── Anonymous marking (item 21) ────────────────────────────────────

def test_anonymous_marking_hides_the_name(wf_db):
    a = _assignment(anonymous_marking=True, release_policy="Manual")
    sub = _marked(a, wf_db.s1, 40)

    assert fb.is_anonymous(sub, a) is True
    assert fb.display_name(sub, a) == f"Candidate {sub.submission_id:04d}"
    assert fb.display_student_id(sub, a) \
        == f"Candidate {sub.submission_id:04d}"


def test_anonymity_lifts_on_release(wf_db):
    a = _assignment(anonymous_marking=True, release_policy="Manual")
    sub = _marked(a, wf_db.s1, 40)
    fb.release_submission(sub.submission_id, notify=False)

    out = cw.get_submission(sub.submission_id)

    assert fb.is_anonymous(out, a) is False
    assert fb.display_name(out, a) == "Ada Test"
    assert fb.display_student_id(out, a) == wf_db.s1


def test_anonymity_can_be_overridden_for_staff(wf_db):
    a = _assignment(anonymous_marking=True, release_policy="Manual")
    sub = _marked(a, wf_db.s1, 40)

    assert fb.display_name(sub, a, reveal=True) == "Ada Test"


def test_names_show_when_anonymity_is_off(wf_db):
    a = _assignment(anonymous_marking=False, release_policy="Manual")
    sub = _marked(a, wf_db.s1, 40)

    assert fb.is_anonymous(sub, a) is False
    assert fb.display_name(sub, a) == "Ada Test"


def test_anonymous_labels_are_stable(wf_db):
    a = _assignment(anonymous_marking=True)
    sub = _marked(a, wf_db.s1, 40)
    assert fb.anonymous_label(sub) == fb.anonymous_label(sub)


# ── Acknowledgement (item 23) ──────────────────────────────────────

def test_acknowledging_records_the_date_and_response(wf_db):
    a = _assignment(release_policy="Immediate")
    sub = _marked(a, wf_db.s1, 40)

    out = fb.acknowledge(sub.submission_id,
                          response="I see where AO2 lost marks.")

    assert out.acknowledged_on == _day(0)
    assert out.is_acknowledged is True
    assert out.student_response == "I see where AO2 lost marks."


def test_unreleased_feedback_cannot_be_acknowledged(wf_db):
    a = _assignment(release_policy="Manual")
    sub = _marked(a, wf_db.s1, 40)

    with pytest.raises(cw.ValidationError, match="not been released"):
        fb.acknowledge(sub.submission_id)


def test_unacknowledged_lists_only_visible_feedback(wf_db):
    a = _assignment(release_policy="Immediate")
    seen = _marked(a, wf_db.s1, 40)
    unseen = _marked(a, wf_db.s2, 30)
    cw.add_student(a.assignment_id, wf_db.s3)      # unmarked
    fb.acknowledge(seen.submission_id)

    outstanding = fb.list_unacknowledged(assignment_id=a.assignment_id)

    assert [s.submission_id for s in outstanding] \
        == [unseen.submission_id]
    assert fb.acknowledgement_rate(assignment_id=a.assignment_id) \
        == (1, 2)


def test_acknowledgement_can_be_cleared(wf_db):
    a = _assignment(release_policy="Immediate")
    sub = _marked(a, wf_db.s1, 40)
    fb.acknowledge(sub.submission_id, response="Noted")

    out = fb.clear_acknowledgement(sub.submission_id)

    assert out.acknowledged_on is None
    assert out.student_response is None


# ── Marking turnaround SLA (item 20) ───────────────────────────────

def test_turnaround_measures_submission_to_marked(wf_db):
    a = _assignment(marking_sla_days=5)
    sub = cw.add_student(a.assignment_id, wf_db.s1)
    cw.submit_work(sub.submission_id, submitted_on=_day(-8))
    cw.mark_submission(sub.submission_id, marks=40)

    report = fb.turnaround_report(assignment_id=a.assignment_id)
    row = report.rows[0]

    assert row.days_taken == 8
    assert row.within_target is False
    assert "over the 5-day target" in row.message


def test_unmarked_work_past_target_is_overdue(wf_db):
    a = _assignment(marking_sla_days=3)
    sub = cw.add_student(a.assignment_id, wf_db.s1)
    cw.submit_work(sub.submission_id, submitted_on=_day(-10))

    report = fb.turnaround_report(assignment_id=a.assignment_id)
    row = report.rows[0]

    assert row.is_overdue is True
    assert row.days_waiting == 10
    assert [r.submission.submission_id for r in fb.overdue_marking()] \
        == [sub.submission_id]


def test_unsubmitted_work_is_not_a_marking_delay(wf_db):
    a = _assignment(marking_sla_days=3)
    cw.add_student(a.assignment_id, wf_db.s1)

    report = fb.turnaround_report(assignment_id=a.assignment_id)

    assert report.rows == []
    assert fb.overdue_marking() == []


def test_turnaround_aggregates(wf_db):
    a = _assignment(marking_sla_days=5)
    for student, submitted in ((wf_db.s1, -3), (wf_db.s2, -9)):
        sub = cw.add_student(a.assignment_id, student)
        cw.submit_work(sub.submission_id, submitted_on=_day(submitted))
        cw.mark_submission(sub.submission_id, marks=40)

    report = fb.turnaround_report(assignment_id=a.assignment_id)

    assert report.average_days == 6.0
    assert report.within_target_percent == 50.0
    assert len(report.marked) == 2


def test_default_sla_applies_without_one_set(wf_db):
    a = _assignment(marking_sla_days=None)
    assert fb.sla_target(a) == fb.DEFAULT_MARKING_SLA_DAYS


def test_teacher_sla_summary_groups_by_marker(wf_db):
    one = _assignment(title="One", teacher="A Teacher",
                       marking_sla_days=2)
    two = _assignment(title="Two", teacher="B Teacher",
                       marking_sla_days=2)
    for a in (one, two):
        sub = cw.add_student(a.assignment_id, wf_db.s1)
        cw.submit_work(sub.submission_id, submitted_on=_day(-10))

    summary = fb.teacher_sla_summary()

    assert set(summary) == {"A Teacher", "B Teacher"}
    assert all(len(r.overdue) == 1 for r in summary.values())


# ── Appeals (item 24) ──────────────────────────────────────────────

def test_appeal_snapshots_the_mark(wf_db):
    a = _assignment(release_policy="Immediate")
    sub = _marked(a, wf_db.s1, 40)

    appeal = fb.raise_appeal(sub.submission_id,
                              grounds="AO2 credits my third paragraph",
                              raised_by=wf_db.s1)

    assert appeal.status == "Submitted"
    assert appeal.marks_at_appeal == 40
    assert appeal.is_open is True
    assert appeal.raised_on == _day(0)


def test_an_unreleased_mark_cannot_be_appealed(wf_db):
    a = _assignment(release_policy="Manual")
    sub = _marked(a, wf_db.s1, 40)

    with pytest.raises(cw.ValidationError, match="released"):
        fb.raise_appeal(sub.submission_id, grounds="Too harsh")


def test_only_one_appeal_may_be_open_at_a_time(wf_db):
    a = _assignment(release_policy="Immediate")
    sub = _marked(a, wf_db.s1, 40)
    fb.raise_appeal(sub.submission_id, grounds="First")

    with pytest.raises(cw.ValidationError, match="already an open"):
        fb.raise_appeal(sub.submission_id, grounds="Second")


def test_appeal_window_closes(wf_db):
    a = _assignment(release_policy="Immediate", appeal_window_days=7)
    sub = _marked(a, wf_db.s1, 40)

    assert fb.appeal_deadline(sub, a) == _day(7)
    with pytest.raises(cw.ValidationError, match="window closed"):
        fb.raise_appeal(sub.submission_id, grounds="Late",
                         raised_on=_day(30))

    late = fb.raise_appeal(sub.submission_id, grounds="Late",
                            raised_on=_day(30),
                            allow_out_of_window=True)
    assert late.raised_on == _day(30)


def test_appeal_window_runs_from_release_not_marking(wf_db):
    """A mark held back for a fortnight must not eat the window."""
    a = _assignment(release_policy="Manual", appeal_window_days=7)
    sub = _marked(a, wf_db.s1, 40)
    fb.release_submission(sub.submission_id, notify=False)

    out = cw.get_submission(sub.submission_id)

    assert out.feedback_released_on == _day(0)
    assert fb.appeal_deadline(out, a) == _day(7)


def test_upheld_appeal_changes_the_mark(wf_db):
    a = _assignment(release_policy="Immediate")
    sub = _marked(a, wf_db.s1, 40)
    appeal = fb.raise_appeal(sub.submission_id, grounds="AO2")
    fb.start_review(appeal.appeal_id, reviewer="HoD")

    out = fb.resolve_appeal(appeal.appeal_id, status="Upheld",
                             outcome="AO2 re-credited", new_marks=45,
                             resolved_by="HoD")

    assert out.status == "Upheld"
    assert out.marks_after == 45
    assert out.mark_changed == 5.0
    assert out.is_open is False
    assert cw.get_submission(sub.submission_id).marks == 45


def test_a_rejected_appeal_cannot_change_the_mark(wf_db):
    a = _assignment(release_policy="Immediate")
    sub = _marked(a, wf_db.s1, 40)
    appeal = fb.raise_appeal(sub.submission_id, grounds="Too harsh")

    with pytest.raises(cw.ValidationError, match="cannot also change"):
        fb.resolve_appeal(appeal.appeal_id, status="Rejected",
                           outcome="Mark stands", new_marks=45)


def test_appeal_mark_change_is_audited(wf_db):
    a = _assignment(release_policy="Immediate")
    sub = _marked(a, wf_db.s1, 40)
    appeal = fb.raise_appeal(sub.submission_id, grounds="AO2")
    fb.resolve_appeal(appeal.appeal_id, status="Upheld",
                       outcome="Re-credited", new_marks=45,
                       resolved_by="HoD")

    rows = mk.list_mark_audit(submission_id=sub.submission_id)

    assert any(f"Appeal #{appeal.appeal_id}" in (r.reason or "")
               for r in rows)


def test_withdrawn_appeal_closes_without_a_change(wf_db):
    a = _assignment(release_policy="Immediate")
    sub = _marked(a, wf_db.s1, 40)
    appeal = fb.raise_appeal(sub.submission_id, grounds="Second thoughts")

    out = fb.withdraw_appeal(appeal.appeal_id, reason="Changed my mind")

    assert out.status == "Withdrawn"
    assert out.is_open is False
    assert cw.get_submission(sub.submission_id).marks == 40


def test_appeal_summary_counts(wf_db):
    a = _assignment(release_policy="Immediate")
    first = _marked(a, wf_db.s1, 40)
    second = _marked(a, wf_db.s2, 30)
    upheld = fb.raise_appeal(first.submission_id, grounds="AO2")
    fb.resolve_appeal(upheld.appeal_id, status="Upheld",
                       outcome="Re-credited")
    fb.raise_appeal(second.submission_id, grounds="Harsh")

    summary = fb.appeal_summary(assignment_id=a.assignment_id)

    assert summary["_total"] == 2
    assert summary["_open"] == 1
    assert summary["_upheld"] == 1


# ── Objective questions and auto-marking (item 25) ─────────────────

def _quiz(**over):
    return _assignment(title="Quiz", due_date=_day(5), max_marks=10,
                        **over)


def test_multiple_choice_auto_marks(wf_db):
    a = _quiz()
    q = assess.add_question(a.assignment_id, {
        "question_type": "Multiple choice", "prompt": "Capital?",
        "options": "London|Paris|Rome", "answer_key": "Paris",
        "marks": 2})
    sub = cw.add_student(a.assignment_id, wf_db.s1)

    right = assess.record_answer(sub.submission_id, q.question_id,
                                  response="Paris")
    assert right.is_correct is True
    assert right.marks_awarded == 2

    wrong = assess.record_answer(sub.submission_id, q.question_id,
                                  response="Rome")
    assert wrong.is_correct is False
    assert wrong.marks_awarded == 0


def test_short_answer_ignores_case_space_and_punctuation(wf_db):
    a = _quiz()
    q = assess.add_question(a.assignment_id, {
        "question_type": "Short answer", "prompt": "Process?",
        "answer_key": "photosynthesis", "marks": 3})
    sub = cw.add_student(a.assignment_id, wf_db.s1)

    for response in ("photosynthesis", "  Photosynthesis. ",
                      "PHOTOSYNTHESIS!"):
        answer = assess.record_answer(sub.submission_id, q.question_id,
                                       response=response)
        assert answer.is_correct is True, response


def test_short_answer_accepts_any_listed_key(wf_db):
    a = _quiz()
    q = assess.add_question(a.assignment_id, {
        "question_type": "Short answer", "prompt": "Process?",
        "answer_key": "photosynthesis|carbon fixation", "marks": 3})
    sub = cw.add_student(a.assignment_id, wf_db.s1)

    for response in ("photosynthesis", "Carbon Fixation"):
        answer = assess.record_answer(sub.submission_id, q.question_id,
                                       response=response)
        assert answer.is_correct is True, response


def test_short_answer_normalises_punctuation_but_not_spacing(wf_db):
    """A hyphen is typography; a space is a different answer.

    Stripping spaces too would make "the cat sat" match "thecatsat",
    so an unlisted spacing variant is a miss the teacher can override.
    """
    a = _quiz()
    q = assess.add_question(a.assignment_id, {
        "question_type": "Short answer", "prompt": "Process?",
        "answer_key": "photo-synthesis", "marks": 3})
    sub = cw.add_student(a.assignment_id, wf_db.s1)

    assert assess.record_answer(
        sub.submission_id, q.question_id,
        response="photosynthesis").is_correct is True
    assert assess.record_answer(
        sub.submission_id, q.question_id,
        response="photo synthesis").is_correct is False


def test_numeric_answers_honour_tolerance(wf_db):
    a = _quiz()
    q = assess.add_question(a.assignment_id, {
        "question_type": "Numeric", "prompt": "Pi to 2dp?",
        "answer_key": "3.14", "marks": 2, "tolerance": 0.01})
    sub = cw.add_student(a.assignment_id, wf_db.s1)

    assert assess.record_answer(sub.submission_id, q.question_id,
                                 response="3.145").is_correct is True
    assert assess.record_answer(sub.submission_id, q.question_id,
                                 response="3.2").is_correct is False


def test_numeric_key_must_be_a_number(wf_db):
    a = _quiz()
    with pytest.raises(cw.ValidationError, match="not a number"):
        assess.add_question(a.assignment_id, {
            "question_type": "Numeric", "prompt": "?",
            "answer_key": "about three"})


def test_multiple_choice_needs_options(wf_db):
    a = _quiz()
    with pytest.raises(cw.ValidationError, match="options list"):
        assess.add_question(a.assignment_id, {
            "question_type": "Multiple choice", "prompt": "?",
            "answer_key": "A"})


def test_multiple_response_ignores_order(wf_db):
    a = _quiz()
    q = assess.add_question(a.assignment_id, {
        "question_type": "Multiple response", "prompt": "Which two?",
        "options": "A|B|C|D", "answer_key": "A|C", "marks": 2})
    sub = cw.add_student(a.assignment_id, wf_db.s1)

    assert assess.record_answer(sub.submission_id, q.question_id,
                                 response="C|A").is_correct is True
    assert assess.record_answer(sub.submission_id, q.question_id,
                                 response="A|B").is_correct is False


def test_a_blank_answer_scores_nothing(wf_db):
    a = _quiz()
    q = assess.add_question(a.assignment_id, {
        "question_type": "Short answer", "prompt": "?",
        "answer_key": "x", "marks": 2})
    sub = cw.add_student(a.assignment_id, wf_db.s1)

    answer = assess.record_answer(sub.submission_id, q.question_id,
                                   response="   ")
    assert answer.is_correct is False
    assert answer.marks_awarded == 0


def test_auto_mark_totals_onto_the_submission(wf_db):
    a = _quiz()
    q1 = assess.add_question(a.assignment_id, {
        "prompt": "A?", "options": "X|Y", "answer_key": "X", "marks": 2})
    q2 = assess.add_question(a.assignment_id, {
        "prompt": "B?", "options": "X|Y", "answer_key": "Y", "marks": 3})
    sub = cw.add_student(a.assignment_id, wf_db.s1)
    assess.record_answer(sub.submission_id, q1.question_id, response="X")
    assess.record_answer(sub.submission_id, q2.question_id, response="X")

    result = assess.auto_mark(sub.submission_id)

    assert result.correct == 1
    assert result.marks_awarded == 2
    assert result.marks_available == 5
    assert result.percent == 40.0
    assert cw.get_submission(sub.submission_id).objective_marks == 2


def test_objective_marks_do_not_become_the_submission_mark(wf_db):
    """A mixed paper still has an essay for the teacher to mark."""
    a = _quiz()
    q = assess.add_question(a.assignment_id, {
        "prompt": "A?", "options": "X|Y", "answer_key": "X", "marks": 2})
    sub = cw.add_student(a.assignment_id, wf_db.s1)
    assess.record_answer(sub.submission_id, q.question_id, response="X")

    assess.auto_mark(sub.submission_id)

    out = cw.get_submission(sub.submission_id)
    assert out.objective_marks == 2
    assert out.marks is None


def test_an_override_survives_re_marking(wf_db):
    a = _quiz()
    q = assess.add_question(a.assignment_id, {
        "question_type": "Short answer", "prompt": "?",
        "answer_key": "alpha", "marks": 2})
    sub = cw.add_student(a.assignment_id, wf_db.s1)
    assess.record_answer(sub.submission_id, q.question_id,
                          response="alpha particle")

    assess.override_answer(sub.submission_id, q.question_id, marks=2,
                            overridden_by="J Smith",
                            reason="Acceptable phrasing")
    result = assess.auto_mark(sub.submission_id)

    assert result.marks_awarded == 2
    assert result.overridden == 1


def test_re_answering_clears_an_override(wf_db):
    a = _quiz()
    q = assess.add_question(a.assignment_id, {
        "question_type": "Short answer", "prompt": "?",
        "answer_key": "alpha", "marks": 2})
    sub = cw.add_student(a.assignment_id, wf_db.s1)
    assess.record_answer(sub.submission_id, q.question_id, response="x")
    assess.override_answer(sub.submission_id, q.question_id, marks=2,
                            overridden_by="JS")

    answer = assess.record_answer(sub.submission_id, q.question_id,
                                   response="y")

    assert answer.is_overridden is False
    assert answer.marks_awarded == 0


def test_override_cannot_exceed_the_question_marks(wf_db):
    a = _quiz()
    q = assess.add_question(a.assignment_id, {
        "prompt": "?", "options": "X|Y", "answer_key": "X", "marks": 2})
    sub = cw.add_student(a.assignment_id, wf_db.s1)
    assess.record_answer(sub.submission_id, q.question_id, response="Y")

    with pytest.raises(cw.ValidationError):
        assess.override_answer(sub.submission_id, q.question_id,
                                marks=5, overridden_by="JS")


def test_question_analysis_reports_facility(wf_db):
    a = _quiz()
    q = assess.add_question(a.assignment_id, {
        "prompt": "?", "options": "X|Y", "answer_key": "X", "marks": 1})
    for student, response in ((wf_db.s1, "X"), (wf_db.s2, "Y"),
                               (wf_db.s3, "Y")):
        sub = cw.add_student(a.assignment_id, student)
        assess.record_answer(sub.submission_id, q.question_id,
                              response=response)

    row = assess.question_analysis(a.assignment_id)[0]

    assert row["answered"] == 3
    assert row["correct"] == 1
    assert row["facility"] == 33.3


def test_a_question_belongs_to_its_own_assignment(wf_db):
    a1 = _quiz()
    a2 = _quiz()
    q = assess.add_question(a2.assignment_id, {
        "prompt": "?", "options": "X|Y", "answer_key": "X"})
    sub = cw.add_student(a1.assignment_id, wf_db.s1)

    with pytest.raises(cw.ValidationError, match="belongs to assignment"):
        assess.record_answer(sub.submission_id, q.question_id,
                              response="X")


# ── Group assignments (item 26) ────────────────────────────────────

def test_group_marks_apply_with_per_member_adjustment(wf_db):
    a = _assignment(due_date=_day(5), max_marks=40,
                     is_group_assignment=True)
    members = [cw.add_student(a.assignment_id, s)
               for s in (wf_db.s1, wf_db.s2, wf_db.s3)]
    group = assess.create_group(a.assignment_id, "Team A")
    assess.add_group_member(group.group_id, members[0].submission_id)
    assess.add_group_member(group.group_id, members[1].submission_id,
                             adjustment=4,
                             adjustment_reason="Led the build")
    assess.add_group_member(group.group_id, members[2].submission_id,
                             adjustment=-8,
                             adjustment_reason="Contributed little")
    assess.set_group_marks(group.group_id, 30, marked_by="J Smith")

    applied = assess.apply_group_marks(group.group_id)

    # Members come back in student-id order, which is not the order
    # they were added, so compare by student rather than by position.
    by_student = {s.student_id: s.marks for s in applied}
    assert by_student == {wf_db.s1: 30.0, wf_db.s2: 34.0,
                          wf_db.s3: 22.0}


def test_group_marks_are_capped_at_the_maximum(wf_db):
    a = _assignment(due_date=_day(5), max_marks=40,
                     is_group_assignment=True)
    sub = cw.add_student(a.assignment_id, wf_db.s1)
    group = assess.create_group(a.assignment_id, "Team A")
    assess.add_group_member(group.group_id, sub.submission_id,
                             adjustment=20)
    assess.set_group_marks(group.group_id, 38)

    applied = assess.apply_group_marks(group.group_id)

    assert applied[0].marks == 40.0


def test_an_adjustment_cannot_push_a_mark_below_zero(wf_db):
    a = _assignment(due_date=_day(5), max_marks=40,
                     is_group_assignment=True)
    sub = cw.add_student(a.assignment_id, wf_db.s1)
    group = assess.create_group(a.assignment_id, "Team A")
    member = assess.add_group_member(group.group_id,
                                      sub.submission_id,
                                      adjustment=-50)

    assert member.effective_marks(30) == 0.0


def test_group_marks_must_be_set_before_applying(wf_db):
    a = _assignment(is_group_assignment=True)
    sub = cw.add_student(a.assignment_id, wf_db.s1)
    group = assess.create_group(a.assignment_id, "Team A")
    assess.add_group_member(group.group_id, sub.submission_id)

    with pytest.raises(cw.ValidationError, match="Set the group's mark"):
        assess.apply_group_marks(group.group_id)


def test_a_student_belongs_to_one_group(wf_db):
    a = _assignment(is_group_assignment=True)
    sub = cw.add_student(a.assignment_id, wf_db.s1)
    first = assess.create_group(a.assignment_id, "Team A")
    second = assess.create_group(a.assignment_id, "Team B")
    assess.add_group_member(first.group_id, sub.submission_id)

    assess.add_group_member(second.group_id, sub.submission_id)

    assert assess.list_group_members(first.group_id) == []
    assert len(assess.list_group_members(second.group_id)) == 1


def test_group_names_are_unique_per_assignment(wf_db):
    a = _assignment(is_group_assignment=True)
    assess.create_group(a.assignment_id, "Team A")
    with pytest.raises(cw.ValidationError, match="already has a group"):
        assess.create_group(a.assignment_id, "Team A")


def test_a_member_must_be_on_the_same_assignment(wf_db):
    a1 = _assignment(title="One", is_group_assignment=True)
    a2 = _assignment(title="Two")
    other = cw.add_student(a2.assignment_id, wf_db.s1)
    group = assess.create_group(a1.assignment_id, "Team A")

    with pytest.raises(cw.ValidationError, match="is on assignment"):
        assess.add_group_member(group.group_id, other.submission_id)


def test_ungrouped_submissions(wf_db):
    a = _assignment(is_group_assignment=True)
    grouped = cw.add_student(a.assignment_id, wf_db.s1)
    loose = cw.add_student(a.assignment_id, wf_db.s2)
    group = assess.create_group(a.assignment_id, "Team A")
    assess.add_group_member(group.group_id, grouped.submission_id)

    assert [s.submission_id for s in
            assess.ungrouped_submissions(a.assignment_id)] \
        == [loose.submission_id]


def test_disbanding_a_group_keeps_marks(wf_db):
    a = _assignment(due_date=_day(5), max_marks=40,
                     is_group_assignment=True)
    sub = cw.add_student(a.assignment_id, wf_db.s1)
    group = assess.create_group(a.assignment_id, "Team A")
    assess.add_group_member(group.group_id, sub.submission_id)
    assess.set_group_marks(group.group_id, 30)
    assess.apply_group_marks(group.group_id)

    assert assess.delete_group(group.group_id) is True

    out = cw.get_submission(sub.submission_id)
    assert out.marks == 30.0
    assert out.group_id is None


# ── Peer assessment (item 27) ──────────────────────────────────────

def test_peer_scores_combine_by_mode(wf_db):
    a = _assignment(due_date=_day(5), max_marks=20)
    sub = cw.add_student(a.assignment_id, wf_db.s1)
    for reviewer, mark in ((wf_db.s2, 14), (wf_db.s3, 18),
                            (wf_db.s4, 10)):
        assess.record_peer_review(sub.submission_id,
                                   reviewer_student=reviewer,
                                   marks=mark)

    average = assess.peer_summary(sub.submission_id, store=False)
    median = assess.peer_summary(sub.submission_id, mode="Median",
                                  store=False)
    trimmed = assess.peer_summary(sub.submission_id,
                                   mode="Trimmed mean", store=False)

    assert average.reviewer_count == 3
    assert average.score == 14.0
    assert average.spread == 8.0
    assert median.score == 14.0
    assert trimmed.score == 14.0        # drops the 10 and the 18


def test_a_student_cannot_review_their_own_work(wf_db):
    a = _assignment()
    sub = cw.add_student(a.assignment_id, wf_db.s1)
    with pytest.raises(cw.ValidationError, match="own work"):
        assess.record_peer_review(sub.submission_id,
                                   reviewer_student=wf_db.s1, marks=10)


def test_peer_reviews_upsert_per_reviewer(wf_db):
    a = _assignment(max_marks=20)
    sub = cw.add_student(a.assignment_id, wf_db.s1)
    assess.record_peer_review(sub.submission_id,
                               reviewer_student=wf_db.s2, marks=10)
    assess.record_peer_review(sub.submission_id,
                               reviewer_student=wf_db.s2, marks=15)

    reviews = assess.list_peer_reviews(submission_id=sub.submission_id)

    assert len(reviews) == 1
    assert reviews[0].marks == 15


def test_peer_marks_are_capped_by_the_criterion(wf_db):
    a = _assignment(max_marks=50)
    criterion = mk.add_criterion(a.assignment_id,
                                  {"title": "AO1", "max_marks": 10})
    sub = cw.add_student(a.assignment_id, wf_db.s1)

    with pytest.raises(cw.ValidationError):
        assess.record_peer_review(sub.submission_id,
                                   reviewer_student=wf_db.s2,
                                   criterion_id=criterion.criterion_id,
                                   marks=11)


def test_one_reviewer_scoring_several_criteria_counts_once(wf_db):
    a = _assignment(max_marks=50)
    c1 = mk.add_criterion(a.assignment_id,
                           {"title": "AO1", "max_marks": 10})
    c2 = mk.add_criterion(a.assignment_id,
                           {"title": "AO2", "max_marks": 10})
    sub = cw.add_student(a.assignment_id, wf_db.s1)
    assess.record_peer_review(sub.submission_id,
                               reviewer_student=wf_db.s2,
                               criterion_id=c1.criterion_id, marks=8)
    assess.record_peer_review(sub.submission_id,
                               reviewer_student=wf_db.s2,
                               criterion_id=c2.criterion_id, marks=6)

    summary = assess.peer_summary(sub.submission_id, store=False)

    assert summary.reviewer_count == 1
    assert summary.score == 14.0


def test_blending_uses_the_assignment_weight(wf_db):
    a = _assignment(due_date=_day(5), max_marks=20,
                     peer_assessment_weight=25)
    sub = cw.add_student(a.assignment_id, wf_db.s1)
    assess.record_peer_review(sub.submission_id,
                               reviewer_student=wf_db.s2, marks=12)

    blended = assess.blended_marks(sub.submission_id,
                                    teacher_marks=16)

    assert blended == 15.0        # 16 * 0.75 + 12 * 0.25


def test_blending_without_a_weight_leaves_the_teacher_mark(wf_db):
    a = _assignment(due_date=_day(5), max_marks=20,
                     peer_assessment_weight=None)
    sub = cw.add_student(a.assignment_id, wf_db.s1)
    assess.record_peer_review(sub.submission_id,
                               reviewer_student=wf_db.s2, marks=5)

    assert assess.blended_marks(sub.submission_id,
                                 teacher_marks=16) is None
    out = assess.apply_peer_blend(sub.submission_id, teacher_marks=16)
    assert out.marks == 16


def test_blending_without_reviews_leaves_the_teacher_mark(wf_db):
    a = _assignment(due_date=_day(5), max_marks=20,
                     peer_assessment_weight=25)
    sub = cw.add_student(a.assignment_id, wf_db.s1)

    assert assess.blended_marks(sub.submission_id,
                                 teacher_marks=16) is None


def test_peer_coverage(wf_db):
    a = _assignment(max_marks=20)
    reviewed = cw.add_student(a.assignment_id, wf_db.s1)
    cw.add_student(a.assignment_id, wf_db.s2)
    assess.record_peer_review(reviewed.submission_id,
                               reviewer_student=wf_db.s2, marks=10)

    coverage = assess.peer_review_coverage(a.assignment_id)

    assert coverage == {"submissions": 2, "reviewed": 1,
                        "awaiting_review": 1, "active_reviewers": 1}


# ── Self-assessment (item 28) ──────────────────────────────────────

def test_self_assessment_compares_to_the_actual_mark(wf_db):
    a = _assignment(due_date=_day(5), max_marks=50,
                     release_policy="Manual")
    sub = cw.add_student(a.assignment_id, wf_db.s1)
    assess.record_self_assessment(sub.submission_id,
                                   predicted_marks=40,
                                   note="Felt strong")
    cw.mark_submission(sub.submission_id, marks=32)

    result = assess.get_self_assessment(sub.submission_id)

    assert result.predicted == 40
    assert result.actual == 32
    assert result.gap == -8.0
    assert result.accuracy == "Overestimated"


def test_a_prediction_after_release_is_refused(wf_db):
    a = _assignment(due_date=_day(5), release_policy="Immediate")
    sub = _marked(a, wf_db.s1, 40)

    with pytest.raises(cw.ValidationError, match="already been released"):
        assess.record_self_assessment(sub.submission_id,
                                       predicted_marks=45)


def test_a_prediction_cannot_exceed_the_maximum(wf_db):
    a = _assignment(max_marks=50, release_policy="Manual")
    sub = cw.add_student(a.assignment_id, wf_db.s1)
    with pytest.raises(cw.ValidationError):
        assess.record_self_assessment(sub.submission_id,
                                       predicted_marks=60)


def test_calibration_summary(wf_db):
    a = _assignment(due_date=_day(5), max_marks=50,
                     release_policy="Manual")
    for student, predicted, actual in ((wf_db.s1, 40, 30),
                                        (wf_db.s2, 20, 30),
                                        (wf_db.s3, 25, 25)):
        sub = cw.add_student(a.assignment_id, student)
        assess.record_self_assessment(sub.submission_id,
                                       predicted_marks=predicted)
        cw.mark_submission(sub.submission_id, marks=actual)

    summary = assess.calibration_summary(a.assignment_id)

    assert summary["assessed"] == 3
    assert summary["over"] == 1
    assert summary["under"] == 1
    assert summary["accurate"] == 1
    assert summary["average_gap"] == 0.0
    assert summary["mean_absolute_gap"] == 6.67


def test_missing_self_assessments_only_when_required(wf_db):
    required = _assignment(title="Required", release_policy="Manual",
                            self_assessment_required=True)
    optional = _assignment(title="Optional", release_policy="Manual")
    cw.add_student(required.assignment_id, wf_db.s1)
    cw.add_student(optional.assignment_id, wf_db.s1)

    assert len(assess.missing_self_assessments(
        required.assignment_id)) == 1
    assert assess.missing_self_assessments(
        optional.assignment_id) == []


# ── Multi-part assignments (item 29) ───────────────────────────────

def _components(parent, *specs):
    return [cw.create_assignment(
        {"title": f"Part {i}", "subject_name": "History",
         "due_date": _day(5), "max_marks": max_marks,
         "parent_assignment_id": parent.assignment_id,
         "component_weight": weight})
        for i, (max_marks, weight) in enumerate(specs, 1)]


def test_components_roll_up_by_weight(wf_db):
    parent = _assignment(title="NEA", due_date=_day(30), max_marks=100)
    first, second = _components(parent, (40, 25), (60, 75))
    cw.add_student(parent.assignment_id, wf_db.s1)
    a_sub = cw.add_student(first.assignment_id, wf_db.s1)
    b_sub = cw.add_student(second.assignment_id, wf_db.s1)
    cw.mark_submission(a_sub.submission_id, marks=32)       # 80%
    cw.mark_submission(b_sub.submission_id, marks=39)       # 65%

    rollup = cw.component_rollup(parent.assignment_id, wf_db.s1)

    assert rollup.complete is True
    assert rollup.weighted_percent == 68.75    # 80*.25 + 65*.75
    assert rollup.overall_marks == 68.75


def test_unweighted_components_split_evenly(wf_db):
    parent = _assignment(title="NEA", due_date=_day(30), max_marks=100)
    _components(parent, (10, None), (10, None), (10, None))

    weights = cw.component_weights(parent.assignment_id)

    assert len(weights) == 3
    for weight in weights.values():
        assert weight == pytest.approx(33.3333, abs=0.001)


def test_partly_weighted_components_share_the_remainder(wf_db):
    parent = _assignment(title="NEA", due_date=_day(30), max_marks=100)
    first, second, third = _components(parent, (10, 50), (10, None),
                                        (10, None))

    weights = cw.component_weights(parent.assignment_id)

    assert weights[first.assignment_id] == 50
    assert weights[second.assignment_id] == 25
    assert weights[third.assignment_id] == 25


def test_a_partial_rollup_rescales_to_what_is_marked(wf_db):
    """A part-marked NEA reports standing so far, not a dragged-down
    figure."""
    parent = _assignment(title="NEA", due_date=_day(30), max_marks=100)
    first, _second = _components(parent, (40, 25), (60, 75))
    a_sub = cw.add_student(first.assignment_id, wf_db.s1)
    cw.mark_submission(a_sub.submission_id, marks=32)       # 80%

    rollup = cw.component_rollup(parent.assignment_id, wf_db.s1)

    assert rollup.complete is False
    assert rollup.weighted_percent == 80.0


def test_rollup_writes_onto_the_parent(wf_db):
    parent = _assignment(title="NEA", due_date=_day(30), max_marks=100)
    first, second = _components(parent, (40, 50), (60, 50))
    parent_sub = cw.add_student(parent.assignment_id, wf_db.s1)
    a_sub = cw.add_student(first.assignment_id, wf_db.s1)
    b_sub = cw.add_student(second.assignment_id, wf_db.s1)
    cw.mark_submission(a_sub.submission_id, marks=40)       # 100%
    cw.mark_submission(b_sub.submission_id, marks=30)       # 50%

    result = cw.rollup_all(parent.assignment_id, marked_by="HoD")

    assert result == {"applied": 1, "skipped": 0}
    assert cw.get_submission(parent_sub.submission_id).marks == 75.0


def test_rollup_needs_a_parent_submission_row(wf_db):
    parent = _assignment(title="NEA", due_date=_day(30), max_marks=100)
    first, = _components(parent, (40, 100))
    a_sub = cw.add_student(first.assignment_id, wf_db.s1)
    cw.mark_submission(a_sub.submission_id, marks=40)

    assert cw.apply_component_rollup(parent.assignment_id,
                                      wf_db.s1) is None


def test_components_cannot_nest(wf_db):
    parent = _assignment(title="NEA", due_date=_day(30))
    child, = _components(parent, (40, 100))

    with pytest.raises(cw.ValidationError, match="cannot be nested"):
        cw.create_assignment({
            "title": "Sub-part", "subject_name": "History",
            "parent_assignment_id": child.assignment_id})


def test_an_assignment_cannot_be_its_own_parent(wf_db):
    a = _assignment()
    with pytest.raises(cw.ValidationError, match="its own parent"):
        cw.update_assignment(a.assignment_id,
                              {"parent_assignment_id": a.assignment_id})


def test_a_parent_cannot_become_a_component(wf_db):
    parent = _assignment(title="NEA", due_date=_day(30))
    _components(parent, (40, 100))
    other = _assignment(title="Other")

    with pytest.raises(cw.ValidationError, match="already has components"):
        cw.update_assignment(parent.assignment_id,
                              {"parent_assignment_id":
                                  other.assignment_id})


def test_a_missing_parent_is_refused(wf_db):
    with pytest.raises(cw.ValidationError, match="to be a parent"):
        cw.create_assignment({"title": "Orphan",
                               "subject_name": "History",
                               "parent_assignment_id": 9999})


def test_components_can_be_unlinked(wf_db):
    parent = _assignment(title="NEA", due_date=_day(30))
    child, = _components(parent, (40, 100))

    cw.update_assignment(child.assignment_id,
                          {"parent_assignment_id": None,
                           "component_weight": None})

    assert cw.list_components(parent.assignment_id) == []
    assert cw.get_assignment(
        child.assignment_id).is_component is False
