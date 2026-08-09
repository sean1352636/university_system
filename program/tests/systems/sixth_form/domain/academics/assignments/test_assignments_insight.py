"""Tests for coursework analysis and administration.

Covers deadline clashes, teacher digests, cover handover, student
history, target comparison, cohort analytics, trend tracking, the
non-submission dashboard, CSV import/export, coversheets and weighted
subject grades.
"""

from __future__ import annotations

import datetime as _dt
import sqlite3

import pytest

from education_system.systems.sixth_form.domain.academics.assignments import (
    assignments as cw,
    assignments_admin as admin,
    assignments_analytics as an,
    assignments_marking as mk,
)
from education_system.systems.sixth_form.domain.academics.subjects import (
    subjects as subjects_mod,
)
from education_system.systems.sixth_form.domain.assessment.target_setting import (
    target_setting as targets_mod,
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
def ins_db(tmp_path, monkeypatch):
    """Coursework, marking, analytics, admin and targets on one DB."""
    db_path = str(tmp_path / "sixthform.db")
    # ``assignments_analytics`` is deliberately absent: it owns no
    # tables and reads through core, which is redirected here.
    for mod in (cw, mk, admin, students_mod, subjects_mod,
                 targets_mod):
        monkeypatch.setattr(mod, "DB_PATH", db_path)
        monkeypatch.setattr(mod, "_DB_READY", False)
    monkeypatch.setattr(paths, "SIXTH_FORM_COURSEWORK_FILES_DIR",
                         tmp_path / "coursework_files")
    admin.init_db()
    mk.init_db()
    targets_mod.init_db()

    class NS:
        pass
    ns = NS()
    ns.students = _seed_students(db_path, "Ada", "Alan", "Grace")
    ns.s1, ns.s2, ns.s3 = ns.students
    ns.tmp = tmp_path
    return ns


def _assignment(**over):
    payload = {"title": "Essay", "subject_name": "History",
               "teacher": "Ms Owner", "year_group": "Year 12",
               "set_date": _day(-40), "due_date": _day(-10),
               "max_marks": 50, "status": "Set"}
    payload.update(over)
    return cw.create_assignment(payload)


def _marked(assignment, student_id, marks, *, submitted=-15):
    sub = cw.add_student(assignment.assignment_id, student_id)
    cw.submit_work(sub.submission_id, submitted_on=_day(submitted))
    cw.mark_submission(sub.submission_id, marks=marks,
                        marked_by="Ms Owner")
    return cw.get_submission(sub.submission_id)


# ── Deadline clashes (item 40) ─────────────────────────────────────

def test_clashes_group_by_week_and_year(ins_db):
    _assignment(title="A", subject_name="History", due_date=_day(3))
    _assignment(title="B", subject_name="Physics", due_date=_day(4))
    _assignment(title="Alone", subject_name="Chemistry",
                 due_date=_day(40))

    clashes = admin.clashes()

    assert len(clashes) == 1
    assert clashes[0].count == 2
    assert clashes[0].subjects == ["History", "Physics"]
    assert clashes[0].year_group == "Year 12"


def test_a_clash_needs_the_same_year_group(ins_db):
    _assignment(title="Y12", year_group="Year 12", due_date=_day(3))
    _assignment(title="Y13", year_group="Year 13", due_date=_day(4))

    assert admin.clashes() == []


def _next_monday(offset_weeks: int = 1) -> _dt.date:
    """A Monday in the future, so a run of dates cannot straddle two
    weeks and split a clash in half."""
    today = _dt.date.today()
    return (today + _dt.timedelta(days=(7 - today.weekday())
                                   + 7 * (offset_weeks - 1)))


def test_severe_clashes_are_flagged(ins_db):
    monday = _next_monday()
    for i in range(admin.CLASH_THRESHOLD):
        _assignment(title=f"Piece {i}",
                     due_date=(monday
                               + _dt.timedelta(days=i)).isoformat(),
                     estimated_hours=5)

    clash = admin.clashes()[0]

    assert clash.is_severe is True
    assert clash.estimated_hours == 15.0
    assert "⚠" in clash.message


def test_student_clashes_see_an_unusual_combination(ins_db):
    """A student's own timetable can clash when the year group's does
    not."""
    first = _assignment(title="A", year_group="Year 12",
                         due_date=_day(3))
    second = _assignment(title="B", year_group="Year 13",
                          due_date=_day(4))
    for a in (first, second):
        cw.add_student(a.assignment_id, ins_db.s1)

    assert admin.clashes() == []
    student = admin.student_clashes(ins_db.s1)
    assert len(student) == 1
    assert student[0].count == 2


def test_submitted_work_is_not_a_clash(ins_db):
    first = _assignment(title="A", due_date=_day(3))
    second = _assignment(title="B", due_date=_day(4))
    done = cw.add_student(first.assignment_id, ins_db.s1)
    cw.add_student(second.assignment_id, ins_db.s1)
    cw.submit_work(done.submission_id, submitted_on=_day(0))

    assert admin.student_clashes(ins_db.s1) == []


def test_reschedule_suggests_moving_the_smallest_cohort(ins_db):
    big = _assignment(title="Big", due_date=_day(3))
    small = _assignment(title="Small", due_date=_day(4))
    for student in ins_db.students:
        cw.add_student(big.assignment_id, student)
    cw.add_student(small.assignment_id, ins_db.s1)

    suggestions = admin.suggest_reschedule(admin.clashes()[0])

    assert suggestions[0][0] == small.assignment_id
    assert suggestions[0][2] == _day(11)


# ── Teacher digest (item 41) ───────────────────────────────────────

def test_digest_collects_marking_and_missing(ins_db):
    a = _assignment(due_date=_day(-5))
    handed = cw.add_student(a.assignment_id, ins_db.s1)
    cw.submit_work(handed.submission_id, submitted_on=_day(-6))
    cw.add_student(a.assignment_id, ins_db.s2)
    cw.sweep_late_submissions()

    digest = admin.build_digest("Ms Owner")

    assert digest.total_unmarked == 1
    assert digest.total_missing == 1
    assert "to mark" in digest.message
    assert "COURSEWORK DIGEST" in digest.as_text().upper()


def test_digest_lists_upcoming_deadlines(ins_db):
    _assignment(title="Soon", due_date=_day(2))
    _assignment(title="Far", due_date=_day(60))
    a = _assignment(title="Soon", due_date=_day(2))
    cw.add_student(a.assignment_id, ins_db.s1)

    digest = admin.build_digest("Ms Owner", period="Weekly")

    titles = {line.assignment.title for line in digest.upcoming}
    assert "Soon" in titles
    assert "Far" not in titles


def test_a_digest_only_covers_that_teacher(ins_db):
    mine = _assignment(title="Mine", teacher="Ms Owner",
                        due_date=_day(-5))
    _assignment(title="Theirs", teacher="Mr Other", due_date=_day(-5))
    cw.add_student(mine.assignment_id, ins_db.s1)
    cw.sweep_late_submissions()

    digest = admin.build_digest("Ms Owner")

    assert all(line.assignment.teacher == "Ms Owner"
               for line in digest.missing)


def test_an_empty_digest_is_not_sent(ins_db):
    """An empty digest every morning trains people to ignore them."""
    _assignment(due_date=_day(60))

    assert admin.send_digest("Ms Owner", notify=False) is None
    assert admin.send_digest("Ms Owner", notify=False,
                              skip_if_empty=False) is not None


def test_sending_a_digest_is_logged(ins_db):
    a = _assignment(due_date=_day(-5))
    cw.add_student(a.assignment_id, ins_db.s1)
    cw.sweep_late_submissions()

    admin.send_digest("Ms Owner", notify=False)

    log = admin.digest_log(teacher="Ms Owner")
    assert len(log) == 1
    assert log[0]["missing"] == 1


def test_an_invalid_digest_period_is_refused(ins_db):
    with pytest.raises(cw.ValidationError, match="Digest period"):
        admin.build_digest("Ms Owner", period="Hourly")


# ── Cover handover (item 42) ───────────────────────────────────────

def test_cover_preserves_the_substantive_teacher(ins_db):
    a = _assignment(teacher="Ms Owner")

    out = admin.assign_cover(a.assignment_id,
                              cover_marker="Mr Cover",
                              cover_until=_day(14), reason="Illness")

    assert out.teacher == "Ms Owner"
    assert out.cover_marker == "Mr Cover"
    assert out.marker_on() == "Mr Cover"
    assert out.is_covered is True


def test_cover_only_applies_inside_its_window(ins_db):
    a = _assignment(teacher="Ms Owner")
    out = admin.assign_cover(a.assignment_id, cover_marker="Mr Cover",
                              cover_from=_day(2), cover_until=_day(9))

    assert out.marker_on(_day(0)) == "Ms Owner"
    assert out.marker_on(_day(5)) == "Mr Cover"
    assert out.marker_on(_day(20)) == "Ms Owner"


def test_a_teacher_cannot_cover_themselves(ins_db):
    a = _assignment(teacher="Ms Owner")
    with pytest.raises(cw.ValidationError, match="already owns"):
        admin.assign_cover(a.assignment_id, cover_marker="Ms Owner")


def test_cover_cannot_end_before_it_starts(ins_db):
    a = _assignment()
    with pytest.raises(cw.ValidationError, match="end before"):
        admin.assign_cover(a.assignment_id, cover_marker="Mr Cover",
                            cover_from=_day(10), cover_until=_day(2))


def test_covering_a_whole_load_in_one_action(ins_db):
    for title in ("A", "B", "C"):
        _assignment(title=title, teacher="Ms Owner")
    _assignment(title="Other", teacher="Mr Other")

    rows = admin.cover_for_teacher("Ms Owner",
                                    cover_marker="Mr Cover",
                                    reason="Staff absence")

    assert len(rows) == 3
    assert all(a.cover_marker == "Mr Cover" for a in rows)
    assert len(admin.list_covered()) == 3


def test_ending_cover_returns_the_assignment(ins_db):
    a = _assignment(teacher="Ms Owner")
    admin.assign_cover(a.assignment_id, cover_marker="Mr Cover")

    out = admin.end_cover(a.assignment_id)

    assert out.cover_marker is None
    assert out.marker_on() == "Ms Owner"
    assert admin.list_covered() == []


def test_expired_cover_is_reported_not_enforced(ins_db):
    a = _assignment(teacher="Ms Owner")
    admin.assign_cover(a.assignment_id, cover_marker="Mr Cover",
                        cover_from=_day(-20), cover_until=_day(-5))

    assert admin.list_covered() == []
    assert [x.assignment_id for x in admin.expired_cover()] \
        == [a.assignment_id]
    assert cw.get_assignment(a.assignment_id).marker_on() == "Ms Owner"


def test_a_cover_marker_sees_the_work_in_their_digest(ins_db):
    a = _assignment(teacher="Ms Owner", due_date=_day(-5))
    cw.add_student(a.assignment_id, ins_db.s1)
    cw.sweep_late_submissions()
    admin.assign_cover(a.assignment_id, cover_marker="Mr Cover")

    covering = admin.build_digest("Mr Cover")
    owner = admin.build_digest("Ms Owner")

    assert [x.assignment_id for x in covering.covering_for] \
        == [a.assignment_id]
    assert owner.is_empty is True


# ── Student history (item 43) ──────────────────────────────────────

def test_history_spans_subjects_oldest_first(ins_db):
    history_a = _assignment(title="Early", subject_name="History",
                             due_date=_day(-30))
    physics = _assignment(title="Later", subject_name="Physics",
                           due_date=_day(-10))
    _marked(history_a, ins_db.s1, 40, submitted=-32)
    _marked(physics, ins_db.s1, 30, submitted=-12)

    history = an.student_history(ins_db.s1)

    assert [e.assignment.title for e in history.entries] \
        == ["Early", "Later"]
    assert history.subjects == ["History", "Physics"]
    assert history.average_percent == 70.0


def test_history_reports_state_per_entry(ins_db):
    marked = _assignment(title="Marked")
    missing = _assignment(title="Missing", due_date=_day(-5))
    _marked(marked, ins_db.s1, 40)
    cw.add_student(missing.assignment_id, ins_db.s1)
    cw.sweep_late_submissions()

    states = {e.assignment.title: e.state
              for e in an.student_history(ins_db.s1).entries}

    assert states == {"Marked": "Marked", "Missing": "Missing"}


def test_history_can_be_filtered_by_subject(ins_db):
    history_a = _assignment(subject_name="History")
    physics = _assignment(subject_name="Physics")
    for a in (history_a, physics):
        _marked(a, ins_db.s1, 40)

    filtered = an.student_history(ins_db.s1, subject_name="Physics")

    assert len(filtered.entries) == 1


def test_subject_breakdown(ins_db):
    for subject in ("History", "Physics"):
        _marked(_assignment(subject_name=subject), ins_db.s1, 40)

    breakdown = an.subject_breakdown(ins_db.s1)

    assert set(breakdown) == {"History", "Physics"}
    assert all(len(h.entries) == 1 for h in breakdown.values())


# ── Target comparison (item 44) ────────────────────────────────────

def test_comparison_reads_the_existing_target(ins_db):
    a = _assignment(subject_name="History", max_marks=50)
    _marked(a, ins_db.s1, 30)        # 60% → C
    targets_mod.create_target({"student_id": ins_db.s1,
                                "subject_name": "History",
                                "mte_grade": "A"})

    comparison = an.target_comparison(ins_db.s1, "History")

    assert comparison.target_grade == "A"
    assert comparison.actual_grade == "C"
    assert comparison.grades_below_target == 2
    assert comparison.is_underperforming is True
    assert comparison.is_serious is True


def test_at_target_is_not_underperforming(ins_db):
    a = _assignment(subject_name="History", max_marks=50)
    _marked(a, ins_db.s1, 45)        # 90% → A*
    targets_mod.create_target({"student_id": ins_db.s1,
                                "subject_name": "History",
                                "mte_grade": "B"})

    comparison = an.target_comparison(ins_db.s1, "History")

    assert comparison.grades_below_target == 0
    assert comparison.is_underperforming is False


def test_no_target_means_no_comparison(ins_db):
    a = _assignment(subject_name="History")
    _marked(a, ins_db.s1, 30)

    comparison = an.target_comparison(ins_db.s1, "History")

    assert comparison.target_grade is None
    assert comparison.grades_below_target is None
    assert comparison.is_underperforming is False
    assert "no target set" in comparison.message


def test_underperformers_are_ranked_by_gap(ins_db):
    a = _assignment(subject_name="History", max_marks=50)
    _marked(a, ins_db.s1, 20)        # 40% → E
    _marked(a, ins_db.s2, 35)        # 70% → B
    for student in (ins_db.s1, ins_db.s2):
        targets_mod.create_target({"student_id": student,
                                    "subject_name": "History",
                                    "mte_grade": "A"})

    rows = an.underperformers(subject_name="History")

    assert [r.student_id for r in rows] == [ins_db.s1, ins_db.s2]
    assert rows[0].grades_below_target > rows[1].grades_below_target


# ── Trend tracking (item 46) ───────────────────────────────────────

def test_a_falling_run_is_declining(ins_db):
    for offset, marks in ((-40, 45), (-30, 40), (-20, 25), (-10, 20)):
        a = _assignment(title=f"Piece {offset}", set_date=_day(-50),
                         due_date=_day(offset))
        _marked(a, ins_db.s1, marks, submitted=offset - 1)

    trend = an.student_trend(ins_db.s1)

    assert trend.direction == "Declining"
    assert trend.change < 0
    assert trend.is_declining is True


def test_a_rising_run_is_improving(ins_db):
    for offset, marks in ((-40, 20), (-30, 25), (-20, 40), (-10, 45)):
        a = _assignment(title=f"Piece {offset}", set_date=_day(-50),
                         due_date=_day(offset))
        _marked(a, ins_db.s1, marks, submitted=offset - 1)

    assert an.student_trend(ins_db.s1).direction == "Improving"


def test_small_movement_is_flat(ins_db):
    for offset, marks in ((-30, 30), (-20, 31), (-10, 30)):
        a = _assignment(title=f"Piece {offset}", set_date=_day(-50),
                         due_date=_day(offset))
        _marked(a, ins_db.s1, marks, submitted=offset - 1)

    assert an.student_trend(ins_db.s1).direction == "Flat"


def test_one_mark_is_not_a_trend(ins_db):
    _marked(_assignment(), ins_db.s1, 40)

    trend = an.student_trend(ins_db.s1)

    assert trend.direction == "Insufficient data"
    assert "Not enough" in trend.message


def test_declining_students_lists_the_worst_first(ins_db):
    for student, marks in ((ins_db.s1, (45, 40)),
                            (ins_db.s2, (45, 10))):
        for offset, mark in zip((-30, -10), marks):
            a = _assignment(title=f"{student} {offset}",
                             set_date=_day(-50), due_date=_day(offset))
            _marked(a, student, mark, submitted=offset - 1)

    rows = an.declining_students()

    assert rows[0].student_id == ins_db.s2


# ── Cohort analytics (item 45) ─────────────────────────────────────

def test_assignment_distribution(ins_db):
    a = _assignment(max_marks=50)
    for student, marks in zip(ins_db.students, (45, 30, 20)):
        _marked(a, student, marks)

    distribution = an.assignment_distribution(a.assignment_id)

    assert distribution.count == 3
    assert distribution.highest == 90.0
    assert distribution.lowest == 40.0
    assert distribution.median == 60.0
    assert distribution.by_grade.get("A*") == 1


def test_criterion_weaknesses_rank_weakest_first(ins_db):
    a = _assignment(max_marks=50)
    strong = mk.add_criterion(a.assignment_id,
                               {"title": "Strong", "max_marks": 25})
    weak = mk.add_criterion(a.assignment_id,
                             {"title": "Weak", "max_marks": 25})
    for student in ins_db.students:
        sub = cw.add_student(a.assignment_id, student)
        mk.set_criterion_mark(sub.submission_id,
                               strong.criterion_id, marks=22)
        mk.set_criterion_mark(sub.submission_id,
                               weak.criterion_id, marks=8)

    rows = an.criterion_weaknesses(a.assignment_id)

    assert rows[0].label == "Weak"
    assert rows[0].facility == 32.0
    assert rows[1].facility == 88.0


def test_compare_subjects_and_teachers(ins_db):
    history = _assignment(subject_name="History", teacher="Ms Owner",
                           max_marks=50)
    physics = _assignment(subject_name="Physics", teacher="Mr Other",
                           max_marks=50)
    _marked(history, ins_db.s1, 45)
    _marked(physics, ins_db.s1, 20)

    subjects = an.compare_subjects()
    teachers = an.compare_teachers()

    assert list(subjects) == ["Physics", "History"]   # weakest first
    assert teachers["Ms Owner"].mean == 90.0
    assert teachers["Mr Other"].mean == 40.0


def test_cohort_summary(ins_db):
    a = _assignment(due_date=_day(-5))
    _marked(a, ins_db.s1, 40)
    cw.add_student(a.assignment_id, ins_db.s2)
    cw.sweep_late_submissions()

    summary = an.cohort_summary()

    assert summary["assignments"] == 1
    assert summary["submissions"] == 2
    assert summary["marked"] == 1
    assert summary["missing"] == 1
    assert summary["marked_percent"] == 50.0


def test_an_empty_distribution_is_honest(ins_db):
    a = _assignment()
    cw.add_student(a.assignment_id, ins_db.s1)

    distribution = an.assignment_distribution(a.assignment_id)

    assert distribution.count == 0
    assert distribution.mean is None
    assert distribution.message == "Nothing marked"


# ── Non-submission (item 47) ───────────────────────────────────────

def test_non_submitters_are_ranked_and_levelled(ins_db):
    for i in range(an.REFERRAL_THRESHOLD):
        a = _assignment(title=f"Piece {i}", due_date=_day(-5))
        cw.add_student(a.assignment_id, ins_db.s1)
        if i < an.CONCERN_THRESHOLD:
            cw.add_student(a.assignment_id, ins_db.s2)
    cw.sweep_late_submissions()

    rows = an.non_submitters()

    assert rows[0].student_id == ins_db.s1
    assert rows[0].needs_referral is True
    assert rows[0].level == "Referral"
    assert rows[1].level == "Concern"


def test_the_rate_matters_as_well_as_the_count(ins_db):
    """Two of three missing is a different conversation from two of
    twenty."""
    for i in range(6):
        a = _assignment(title=f"Piece {i}", due_date=_day(-5))
        cw.add_student(a.assignment_id, ins_db.s1)
        if i < 2:
            cw.add_student(a.assignment_id, ins_db.s2)
    cw.sweep_late_submissions()

    rows = {r.student_id: r for r in an.non_submitters()}

    assert rows[ins_db.s1].rate == 100.0
    assert rows[ins_db.s2].rate == 100.0
    assert rows[ins_db.s1].missing > rows[ins_db.s2].missing


def test_submitted_work_keeps_a_student_off_the_list(ins_db):
    a = _assignment(due_date=_day(-5))
    sub = cw.add_student(a.assignment_id, ins_db.s1)
    cw.submit_work(sub.submission_id, submitted_on=_day(-6))
    cw.sweep_late_submissions()

    assert an.non_submitters(minimum=1) == []


def test_referral_candidates_only(ins_db):
    for i in range(an.CONCERN_THRESHOLD):
        a = _assignment(title=f"Piece {i}", due_date=_day(-5))
        cw.add_student(a.assignment_id, ins_db.s1)
    cw.sweep_late_submissions()

    assert an.non_submitters() != []
    assert an.referral_candidates() == []


def test_one_student_s_record(ins_db):
    a = _assignment(due_date=_day(-5))
    cw.add_student(a.assignment_id, ins_db.s1)
    cw.sweep_late_submissions()

    record = an.student_non_submission(ins_db.s1)

    assert record.missing == 1
    assert record.subjects == ["History"]


# ── Weighted subject grade (item 50) ───────────────────────────────

def test_weighted_grade_uses_the_weights(ins_db):
    first = _assignment(title="Half A", max_marks=50,
                         weight_percent=50)
    second = _assignment(title="Half B", max_marks=100,
                          weight_percent=50)
    _marked(first, ins_db.s1, 40)        # 80%
    _marked(second, ins_db.s1, 60)       # 60%

    grade = an.weighted_grade(ins_db.s1, "History")

    assert grade.percent == 70.0
    assert grade.grade == "B"
    assert grade.pieces == 2
    assert grade.is_complete is True


def test_unweighted_pieces_do_not_move_the_grade(ins_db):
    weighted = _assignment(title="Counts", max_marks=50,
                            weight_percent=100)
    formative = _assignment(title="Practice", max_marks=50,
                             weight_percent=None)
    _marked(weighted, ins_db.s1, 40)     # 80%
    _marked(formative, ins_db.s1, 5)     # 10% — must not count

    grade = an.weighted_grade(ins_db.s1, "History")

    assert grade.percent == 80.0
    assert grade.pieces == 1


def test_a_partial_grade_rescales_to_what_is_marked(ins_db):
    done = _assignment(title="Done", max_marks=50, weight_percent=40)
    _assignment(title="To come", max_marks=50, weight_percent=60)
    _marked(done, ins_db.s1, 45)         # 90%

    grade = an.weighted_grade(ins_db.s1, "History")

    assert grade.percent == 90.0
    assert grade.is_complete is False
    assert grade.weight_counted == 40.0
    # The denominator is the subject's whole scheme, so the piece not
    # yet set still counts towards "how much is left".
    assert grade.weight_total == 100.0


def test_including_unmarked_drags_the_grade_down(ins_db):
    done = _assignment(title="Done", max_marks=50, weight_percent=50)
    todo = _assignment(title="To come", max_marks=50,
                        weight_percent=50)
    _marked(done, ins_db.s1, 45)         # 90%
    cw.add_student(todo.assignment_id, ins_db.s1)

    optimistic = an.weighted_grade(ins_db.s1, "History")
    pessimistic = an.weighted_grade(ins_db.s1, "History",
                                     include_unmarked=True)

    assert optimistic.percent == 90.0
    assert pessimistic.percent == 45.0


def test_weight_audit_spots_an_unbalanced_subject(ins_db):
    _assignment(title="A", weight_percent=40)
    _assignment(title="B", weight_percent=45)

    audit = an.weight_audit("History")

    assert audit["total_weight"] == 85.0
    assert audit["balanced"] is False
    assert audit["weighted_assignments"] == 2


def test_a_balanced_subject_audits_clean(ins_db):
    _assignment(title="A", weight_percent=60)
    _assignment(title="B", weight_percent=40)

    assert an.weight_audit("History")["balanced"] is True


def test_subject_weighted_grades_rank_highest_first(ins_db):
    a = _assignment(max_marks=50, weight_percent=100)
    _marked(a, ins_db.s1, 45)
    _marked(a, ins_db.s2, 20)

    rows = an.subject_weighted_grades("History")

    assert [g.student_id for g in rows] == [ins_db.s1, ins_db.s2]


# ── CSV export and import (item 48) ────────────────────────────────

def test_export_separates_raw_penalty_and_final(ins_db):
    a = _assignment(due_date=_day(-10),
                     late_penalty_percent_per_day=10, max_marks=50)
    sub = cw.add_student(a.assignment_id, ins_db.s1)
    cw.submit_work(sub.submission_id, submitted_on=_day(-8))
    cw.mark_submission(sub.submission_id, marks=40)

    text = admin.export_marks(a.assignment_id)
    header, row = text.strip().splitlines()[:2]

    assert "raw_marks" in header and "penalty_percent" in header
    fields = [f.strip() for f in row.split(",")]
    # Stored as REAL, so they come back as 40.0 rather than 40.
    assert "40.0" in fields        # raw, before the penalty
    assert "20.0" in fields        # 2 days late at 10%/day
    assert "32.0" in fields        # what actually counts


def test_export_can_be_written_to_a_file(ins_db, tmp_path):
    a = _assignment()
    _marked(a, ins_db.s1, 40)
    target = tmp_path / "out" / "marks.csv"

    admin.export_marks(a.assignment_id, path=target)

    assert target.is_file()
    assert "assignment_id" in target.read_text()


def test_released_only_filters_the_export(ins_db):
    a = _assignment(release_policy="Manual")
    _marked(a, ins_db.s1, 40)

    full = admin.export_marks(a.assignment_id)
    filtered = admin.export_marks(a.assignment_id, released_only=True)

    assert len(full.strip().splitlines()) == 2
    assert len(filtered.strip().splitlines()) == 1     # header only


def test_a_blank_mark_sheet_carries_the_cohort(ins_db):
    a = _assignment()
    for student in ins_db.students:
        cw.add_student(a.assignment_id, student)

    text = admin.export_template(a.assignment_id)

    assert len(text.strip().splitlines()) == 4         # header + 3
    assert ins_db.s1 in text


def test_import_accepts_alternative_headers(ins_db):
    a = _assignment(max_marks=50)
    cw.add_student(a.assignment_id, ins_db.s1)

    result = admin.import_marks(f"candidate,score\n{ins_db.s1},42\n",
                                 a.assignment_id)

    assert result.applied == 1
    subs = cw.list_submissions(assignment_id=a.assignment_id)
    assert subs[0].marks == 42


def test_import_refuses_a_file_with_a_bad_row(ins_db):
    """One bad row is fixed and re-imported, not half-applied."""
    a = _assignment(max_marks=50)
    cw.add_student(a.assignment_id, ins_db.s1)
    cw.add_student(a.assignment_id, ins_db.s2)

    result = admin.import_marks(
        f"student_id,marks\n{ins_db.s1},40\n{ins_db.s2},999\n",
        a.assignment_id)

    assert result.applied == 0
    assert len(result.errors) == 1
    assert cw.list_submissions(
        assignment_id=a.assignment_id)[0].marks is None


def test_import_can_be_forced_to_apply_the_good_rows(ins_db):
    a = _assignment(max_marks=50)
    cw.add_student(a.assignment_id, ins_db.s1)
    cw.add_student(a.assignment_id, ins_db.s2)

    result = admin.import_marks(
        f"student_id,marks\n{ins_db.s1},40\n{ins_db.s2},999\n",
        a.assignment_id, allow_partial=True)

    assert result.applied == 1
    assert len(result.errors) == 1


def test_import_dry_run_writes_nothing(ins_db):
    a = _assignment(max_marks=50)
    sub = cw.add_student(a.assignment_id, ins_db.s1)

    result = admin.import_marks(f"student_id,marks\n{ins_db.s1},40\n",
                                 a.assignment_id, dry_run=True)

    assert result.applied == 0
    assert result.is_valid is True
    assert cw.get_submission(sub.submission_id).marks is None


def test_import_rejects_an_unknown_student(ins_db):
    a = _assignment()
    result = admin.import_marks("student_id,marks\nZZZZ,40\n",
                                 a.assignment_id)

    assert result.errors[0].message == "No submission on this assignment"


def test_import_needs_a_marks_column(ins_db):
    a = _assignment()
    with pytest.raises(cw.ValidationError, match="marks column"):
        admin.import_marks(f"student_id\n{ins_db.s1}\n",
                            a.assignment_id)


def test_import_applies_the_late_penalty(ins_db):
    a = _assignment(due_date=_day(-10),
                     late_penalty_percent_per_day=10, max_marks=50)
    sub = cw.add_student(a.assignment_id, ins_db.s1)
    cw.submit_work(sub.submission_id, submitted_on=_day(-8))

    admin.import_marks(f"student_id,marks\n{ins_db.s1},40\n",
                        a.assignment_id)

    out = cw.get_submission(sub.submission_id)
    assert out.raw_marks == 40
    assert out.marks == 32.0


def test_an_export_and_import_round_trip(ins_db):
    a = _assignment(max_marks=50)
    for student in ins_db.students:
        cw.add_student(a.assignment_id, student)
    rows = "\n".join(f"{s},{30 + i}"
                     for i, s in enumerate(ins_db.students))

    admin.import_marks(f"student_id,marks\n{rows}\n", a.assignment_id)
    text = admin.export_marks(a.assignment_id)

    assert len(text.strip().splitlines()) == 4
    assert all(str(30 + i) in text for i in range(3))


def test_history_export(ins_db):
    a = _assignment(subject_name="History")
    _marked(a, ins_db.s1, 40)

    text = admin.export_history(ins_db.s1)

    assert "subject_name" in text
    assert "History" in text


# ── Coversheets (item 49) ──────────────────────────────────────────

def test_a_coversheet_carries_the_rubric_and_mark(ins_db):
    a = _assignment(max_marks=50, exam_board="AQA", spec_code="7042")
    criterion = mk.add_criterion(a.assignment_id,
                                  {"code": "AO1", "title": "Knowledge",
                                   "max_marks": 50})
    sub = _marked(a, ins_db.s1, 40)
    mk.set_criterion_mark(sub.submission_id, criterion.criterion_id,
                           marks=40, comment="Well evidenced")

    sheet = admin.build_coversheet(sub.submission_id)

    assert "COURSEWORK COVERSHEET" in sheet
    assert "AQA · 7042" in sheet
    assert "AO1 Knowledge" in sheet
    assert "Well evidenced" in sheet
    assert "own work" in sheet


def test_a_coversheet_shows_the_penalty_separately(ins_db):
    a = _assignment(due_date=_day(-10),
                     late_penalty_percent_per_day=10, max_marks=50)
    sub = cw.add_student(a.assignment_id, ins_db.s1)
    cw.submit_work(sub.submission_id, submitted_on=_day(-8))
    cw.mark_submission(sub.submission_id, marks=40)

    sheet = admin.build_coversheet(sub.submission_id)

    assert "Raw mark" in sheet
    assert "Late penalty" in sheet
    assert "20%" in sheet


def test_a_coversheet_names_the_cover_marker(ins_db):
    a = _assignment(teacher="Ms Owner")
    sub = _marked(a, ins_db.s1, 40)
    admin.assign_cover(a.assignment_id, cover_marker="Mr Cover")

    sheet = admin.build_coversheet(sub.submission_id)

    assert "Mr Cover (cover)" in sheet


def test_feedback_can_be_left_off(ins_db):
    a = _assignment()
    sub = cw.add_student(a.assignment_id, ins_db.s1)
    cw.mark_submission(sub.submission_id, marks=40,
                        feedback="Detailed comments here")

    assert "Detailed comments here" in admin.build_coversheet(
        sub.submission_id)
    assert "Detailed comments here" not in admin.build_coversheet(
        sub.submission_id, include_feedback=False)


def test_coversheets_are_written_per_student(ins_db, tmp_path):
    a = _assignment()
    for student in ins_db.students:
        cw.add_student(a.assignment_id, student)

    written = admin.write_coversheets(a.assignment_id,
                                       directory=tmp_path / "sheets")

    assert len(written) == 3
    assert all(p.is_file() for p in written)


def test_a_sample_pack_needs_a_sample(ins_db):
    a = _assignment()
    _marked(a, ins_db.s1, 40)

    with pytest.raises(cw.ValidationError, match="standardisation"):
        admin.build_sample_pack(a.assignment_id)


def test_a_sample_pack_collects_the_sampled_scripts(ins_db):
    a = _assignment(max_marks=50)
    for student, marks in zip(ins_db.students, (45, 30, 15)):
        _marked(a, student, marks)
    mk.auto_select_sample(a.assignment_id, per_band=1)

    pack = admin.build_sample_pack(a.assignment_id)

    assert "STANDARDISATION SAMPLE" in pack
    assert pack.count("COURSEWORK COVERSHEET") >= 2
