"""Gradebook rules (domain.gradebook) on a scratch school DB.

auth.db (for the teacher's login) and the activity log are redirected, so
nothing touches live data.
"""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.assessment.domain import gradebook as GB
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="gb_teacher", role="teacher")
OTHER = Principal(username="gb_other", role="teacher")
DOB = {y: f"{2026 - y - 4}-01-15" for y in P.YEAR_GROUPS}


@pytest.fixture(autouse=True)
def scratch(tmp_path):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    yield
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


_n = 0


def _pupil(year=8, **extra):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Pupil{_n}", "legal_last_name": f"Test{_n:03d}",
        "date_of_birth": DOB[year], "gender": "Female", "year_group": year,
        "admission_date": "2024-09-01", **extra}, actor=ADMIN)


@pytest.fixture
def setup():
    """Maths and English, 8x/Ma1 taught by gb_teacher with three pupils."""
    from education_system.platform.identity.auth.core import UserAuth
    from education_system.systems.secondary import SYSTEM_KEY
    UserAuth(db_path=accounts._override).provision_user(
        "gb_teacher", "Teach!ng-Pass-123", display_name="Ms Maths", email="m@school.org",
        systems=[(SYSTEM_KEY, "teacher")])
    maths = S.create({"code": "MATH", "name": "Mathematics", "is_core": True}, actor=ADMIN)
    eng = S.create({"code": "ENG", "name": "English", "is_core": True}, actor=ADMIN)
    g = TG.create({"code": "8x/Ma1", "subject_id": maths.subject_id, "year_group": 8,
                   "teacher_username": "gb_teacher"}, actor=ADMIN)
    pupils = [_pupil(), _pupil(), _pupil()]
    TG.add_pupils([p.pupil_id for p in pupils], g.group_id, actor=ADMIN)
    return {"maths": maths, "eng": eng, "group": g, "pupils": pupils}


def _test(setup, name="Fractions", max_marks=40, **extra):
    return GB.create({"name": name, "group_id": setup["group"].group_id,
                      "max_marks": max_marks, **extra}, actor=TEACHER)


# ── Assessments ──────────────────────────────────────────────────────

def test_create_for_a_group_fills_subject_year_and_teacher(setup):
    a = _test(setup)
    assert (a.subject_code, a.year_group, a.group_code, a.teacher, a.status) == (
        "MATH", 8, "8x/Ma1", "Ms Maths", "Open")
    assert a.academic_year == TG.current_year() and a.term == GB.term_for(dt.date.today())
    assert [h["action"] for h in GB.history(a.assessment_id)] == ["create"]


def test_create_reports_every_problem():
    with pytest.raises(GB.ValidationError) as e:
        GB.create({"name": "", "max_marks": "0", "assessment_type": "zz", "term": "winter"},
                  actor=ADMIN)
    text = " ".join(e.value.problems)
    for bit in ("subject", "year group", "name", "Type", "Term", "Max marks"):
        assert bit in text


def test_group_and_subject_must_agree(setup):
    with pytest.raises(GB.ValidationError, match="MATH group"):
        GB.create({"name": "X", "group_id": setup["group"].group_id,
                   "subject_id": setup["eng"].subject_id}, actor=TEACHER)


def test_only_the_groups_teacher_sets_its_assessments(setup):
    with pytest.raises(GB.PermissionDenied, match="don't teach"):
        GB.create({"name": "X", "group_id": setup["group"].group_id}, actor=OTHER)
    a = _test(setup)
    with pytest.raises(GB.PermissionDenied):
        GB.record_marks(a.assessment_id, {setup["pupils"][0].pupil_id: {"marks_awarded": 1}},
                        actor=OTHER)
    with pytest.raises(GB.PermissionDenied):
        GB.update(a.assessment_id, {"name": "Y"}, actor=OTHER)


def test_year_group_assessment_without_a_group(setup):
    a = GB.create({"name": "Essay", "subject_id": setup["eng"].subject_id, "year_group": 8,
                   "max_marks": 30}, actor=OTHER)
    assert (a.group_id, a.for_label) == (None, "Year 8")
    assert GB.pupils_for(a) == []


# ── Marks ────────────────────────────────────────────────────────────

def test_marks_give_percent_and_boundary_grades(setup):
    GB.set_subject_boundaries(setup["maths"].subject_id, GB.GCSE_BOUNDARIES, actor=ADMIN)
    a = _test(setup)
    p1, p2, p3 = setup["pupils"]
    assert GB.record_marks(a.assessment_id, {
        p1.pupil_id: {"marks_awarded": 36}, p2.pupil_id: {"marks_awarded": "12",
                                                          "grade": "4"},
        p3.pupil_id: {"status": "absent"}}, actor=TEACHER) == 3
    got = {e.pupil_id: (e.marks_label, e.mark_pct, e.grade, e.status)
           for e in GB.entries(a.assessment_id)}
    assert got == {p1.pupil_id: ("36/40", 90.0, "9", "Marked"),
                   p2.pupil_id: ("12/40", 30.0, "4", "Marked"),
                   p3.pupil_id: ("Absent", None, None, "Absent")}


def test_bad_marks_are_all_or_nothing(setup):
    a = _test(setup)
    p1, p2, _p3 = setup["pupils"]
    with pytest.raises(GB.ValidationError) as e:
        GB.record_marks(a.assessment_id, {p1.pupil_id: {"marks_awarded": 50},
                                          p2.pupil_id: {"marks_awarded": 10},
                                          _p3.pupil_id: {}}, actor=TEACHER)
    assert len(e.value.problems) == 2
    assert GB.entries(a.assessment_id) == []


def test_wrong_year_pupil_refused(setup):
    a = _test(setup)
    with pytest.raises(GB.ValidationError, match="Year 9"):
        GB.record_marks(a.assessment_id, {_pupil(9).pupil_id: {"marks_awarded": 1}},
                        actor=TEACHER)


def test_grades_only_assessment(setup):
    a = _test(setup, max_marks=None)
    p = setup["pupils"][0]
    with pytest.raises(GB.ValidationError, match="no maximum"):
        GB.record_marks(a.assessment_id, {p.pupil_id: {"marks_awarded": 5}}, actor=TEACHER)
    GB.record_marks(a.assessment_id, {p.pupil_id: {"grade": "A*"}}, actor=TEACHER)
    assert GB.entries(a.assessment_id)[0].grade == "A*"


def test_new_boundaries_rework_worked_out_grades_but_keep_typed_ones(setup):
    GB.set_subject_boundaries(setup["maths"].subject_id, GB.GCSE_BOUNDARIES, actor=ADMIN)
    a = _test(setup)
    p1, p2, _p3 = setup["pupils"]
    GB.record_marks(a.assessment_id, {p1.pupil_id: {"marks_awarded": 36},
                                      p2.pupil_id: {"marks_awarded": 12, "grade": "4"}},
                    actor=TEACHER)
    GB.update(a.assessment_id, {"boundaries": "A:80, B:60, C:0"}, actor=TEACHER)
    got = {e.pupil_id: e.grade for e in GB.entries(a.assessment_id)}
    assert got == {p1.pupil_id: "A", p2.pupil_id: "4"}


def test_max_marks_cannot_drop_below_a_mark(setup):
    a = _test(setup)
    GB.record_marks(a.assessment_id, {setup["pupils"][0].pupil_id: {"marks_awarded": 36}},
                    actor=TEACHER)
    with pytest.raises(GB.ValidationError, match="can't be lower"):
        GB.update(a.assessment_id, {"max_marks": 20}, actor=TEACHER)
    a = GB.update(a.assessment_id, {"max_marks": 72}, actor=TEACHER)
    assert GB.entries(a.assessment_id)[0].mark_pct == 50.0


def test_boundaries_validated():
    assert GB.parse_boundaries("7:65, 9:85,8:75") == [("9", 85.0), ("8", 75.0), ("7", 65.0)]
    with pytest.raises(GB.ValidationError):
        GB.parse_boundaries("9:85, x")
    with pytest.raises(GB.ValidationError, match="twice"):
        GB.parse_boundaries("9:85, 9:80")
    assert GB.grade_for(30, GB.parse_boundaries(GB.GCSE_BOUNDARIES)) == "3"


def test_only_editors_set_subject_boundaries(setup):
    with pytest.raises(GB.PermissionDenied):
        GB.set_subject_boundaries(setup["maths"].subject_id, "A:70", actor=TEACHER)
    assert GB.set_subject_boundaries(setup["maths"].subject_id, "A:70, B:0",
                                     actor=ADMIN) == "A:70, B:0"
    assert GB.set_subject_boundaries(setup["maths"].subject_id, "", actor=ADMIN) is None


def test_locking(setup):
    a = _test(setup)
    p = setup["pupils"][0]
    GB.set_locked(a.assessment_id, True, actor=TEACHER)
    with pytest.raises(GB.ValidationError, match="locked"):
        GB.record_marks(a.assessment_id, {p.pupil_id: {"marks_awarded": 1}}, actor=TEACHER)
    with pytest.raises(GB.PermissionDenied):
        GB.set_locked(a.assessment_id, False, actor=TEACHER)
    GB.set_locked(a.assessment_id, False, actor=ADMIN)
    GB.record_marks(a.assessment_id, {p.pupil_id: {"marks_awarded": 1}}, actor=TEACHER)


def test_delete_with_marks_needs_an_editor(setup):
    a = _test(setup)
    GB.record_marks(a.assessment_id, {setup["pupils"][0].pupil_id: {"marks_awarded": 1}},
                    actor=TEACHER)
    with pytest.raises(GB.PermissionDenied, match="head of department"):
        GB.delete(a.assessment_id, actor=TEACHER)
    GB.delete(a.assessment_id, actor=ADMIN)
    with pytest.raises(GB.NotFound):
        GB.get(a.assessment_id)
    empty = _test(setup, "Empty")
    GB.delete(empty.assessment_id, actor=TEACHER)


# ── The old single entry ─────────────────────────────────────────────

def test_record_entry_files_marks_under_one_assessment(setup):
    p1, p2, _p3 = setup["pupils"]
    sid = setup["maths"].subject_id
    e1 = GB.record_entry({"pupil": p1.admission_no, "subject_id": sid,
                          "assessment_name": "Quiz 1", "assessment_type": "Quiz",
                          "marks_awarded": 8, "max_marks": 10}, actor=TEACHER)
    e2 = GB.record_entry({"pupil": p2.admission_no, "subject_id": sid,
                          "assessment_name": "quiz 1", "marks_awarded": 3,
                          "max_marks": 10}, actor=TEACHER)
    assert e1.assessment_id == e2.assessment_id and e1.group_code == "8x/Ma1"
    assert (e1.marks_label, e1.assessment_type) == ("8/10", "Quiz")
    with pytest.raises(GB.ValidationError, match="out of 10"):
        GB.record_entry({"pupil": p2.admission_no, "subject_id": sid,
                         "assessment_name": "Quiz 1", "marks_awarded": 3, "max_marks": 20},
                        actor=TEACHER)
    e3 = GB.record_entry({"pupil": p1.admission_no, "subject_id": sid,
                          "assessment_name": "Quiz 1", "marks_awarded": 9,
                          "max_marks": 10}, actor=TEACHER)
    assert e3.mark_id == e1.mark_id and e3.marks_awarded == 9


def test_record_entry_for_a_pupil_in_no_group_is_year_level(setup):
    p = _pupil()
    e = GB.record_entry({"pupil": p.admission_no, "subject_id": setup["eng"].subject_id,
                         "assessment_name": "Essay", "grade": "6"}, actor=OTHER)
    assert (e.group_code, e.grade, e.marks_label) == (None, "6", "-")
    GB.delete_entry(e.mark_id, actor=OTHER)
    assert GB.entries(e.assessment_id) == []


def test_list_entries_filters(setup):
    a = _test(setup, assessment_type="Quiz", term="Spring")
    GB.record_marks(a.assessment_id, {p.pupil_id: {"marks_awarded": 10}
                                      for p in setup["pupils"]}, actor=TEACHER)
    assert len(GB.list_entries(year_group=8)) == 3
    assert GB.list_entries(term="Autumn") == []
    assert len(GB.list_entries(assessment_type="Quiz",
                               pupil_id=setup["pupils"][0].pupil_id)) == 1
    with pytest.raises(GB.ValidationError):
        GB.list_entries(term="Winter")


# ── Summaries ────────────────────────────────────────────────────────

def test_cohort_summary(setup):
    a = _test(setup)
    p1, p2, p3 = setup["pupils"]
    GB.record_marks(a.assessment_id, {p1.pupil_id: {"marks_awarded": 30, "grade": "7"},
                                      p2.pupil_id: {"marks_awarded": 10, "grade": "3"}},
                    actor=TEACHER)
    s = GB.assessment_summary(a.assessment_id)
    assert (s["count"], s["avg_pct"], s["median_pct"], s["max_pct"], s["min_pct"]) == (
        2, 50.0, 50.0, 75.0, 25.0)
    assert s["grades"] == {"3": 1, "7": 1}
    assert [p.pupil_id for p in s["missing"]] == [p3.pupil_id]
    assert [e.pupil_id for e in s["entries"]] == [p1.pupil_id, p2.pupil_id]


def test_pupil_subject_summary_is_weighted(setup):
    p = setup["pupils"][0]
    a = _test(setup, "Mock", weight=3)
    b = _test(setup, "Quiz", max_marks=10)
    GB.record_marks(a.assessment_id, {p.pupil_id: {"marks_awarded": 40}}, actor=TEACHER)
    GB.record_marks(b.assessment_id, {p.pupil_id: {"marks_awarded": 6, "grade": "5"}},
                    actor=TEACHER)
    s = GB.pupil_subject_summary(p.pupil_id, setup["maths"].subject_id)
    assert (s["count"], s["avg_pct"], s["latest_grade"]) == (2, 90.0, "5")
    [row] = GB.pupil_overview(p.pupil_id)
    assert (row["subject_code"], row["avg_pct"]) == ("MATH", 90.0)


def test_markbook_grid(setup):
    p1, p2, p3 = setup["pupils"]
    a, b = _test(setup, "A"), _test(setup, "B", max_marks=10)
    GB.record_marks(a.assessment_id, {p1.pupil_id: {"marks_awarded": 20}}, actor=TEACHER)
    GB.record_marks(b.assessment_id, {p1.pupil_id: {"marks_awarded": 10},
                                      p2.pupil_id: {"status": "Excused"}}, actor=TEACHER)
    mb = GB.markbook(group_id=setup["group"].group_id)
    assert [x.name for x in mb["assessments"]] == ["A", "B"]
    rows = {r["pupil"].pupil_id: r for r in mb["rows"]}
    assert rows[p1.pupil_id]["avg_pct"] == 75.0
    assert rows[p2.pupil_id]["avg_pct"] is None and rows[p3.pupil_id]["cells"] == {}
    with pytest.raises(GB.ValidationError):
        GB.markbook()


def test_missing_marks_for_my_groups(setup):
    a = _test(setup)
    GB.record_marks(a.assessment_id, {setup["pupils"][0].pupil_id: {"marks_awarded": 1}},
                    actor=TEACHER)
    assert [(x.assessment_id, n) for x, n in GB.missing_marks(TEACHER)] == [
        (a.assessment_id, 2)]
    assert GB.missing_marks(OTHER) == []
    assert len(GB.missing_marks(OTHER, everyone=True)) == 1


def test_concerns_low_average_and_drop(setup):
    p1, p2, _p3 = setup["pupils"]
    a, b = _test(setup, "A"), _test(setup, "B")  # same day: A's marks are entered first
    GB.record_marks(a.assessment_id, {p1.pupil_id: {"marks_awarded": 36},
                                      p2.pupil_id: {"marks_awarded": 8}}, actor=TEACHER)
    GB.record_marks(b.assessment_id, {p1.pupil_id: {"marks_awarded": 20},
                                      p2.pupil_id: {"marks_awarded": 8}}, actor=TEACHER)
    got = {c["pupil_id"]: c["why"] for c in GB.concerns(below=40, drop=15)}
    assert "below 40%" in got[p2.pupil_id]
    assert "latest 50% vs 90% before" in got[p1.pupil_id]


# ── Import / export ──────────────────────────────────────────────────

def test_export_and_import(setup, tmp_path):
    a = _test(setup)
    p1, p2, p3 = setup["pupils"]
    path = tmp_path / "in.csv"
    path.write_text(f"Admission no,Mark,Comments\n{p1.admission_no},20,=bad\n"
                    f"{p2.admission_no},,\n{p3.admission_no},30,\n", encoding="utf-8")
    n, notes = GB.import_marks(a.assessment_id, path, actor=TEACHER)
    assert n == 2 and "skipped" in notes[0]
    out = tmp_path / "mb.csv"
    assert GB.export_markbook(out, actor=TEACHER, group_id=setup["group"].group_id) == 3
    rows = list(csv.reader(out.open(encoding="utf-8")))
    assert rows[0][3].startswith("Fractions") and rows[1][3] == "20/40"
    bad = tmp_path / "bad.csv"
    bad.write_text("Admission no,Mark\nZZZ,1\n", encoding="utf-8")
    with pytest.raises(GB.ValidationError, match="no pupil ZZZ"):
        GB.import_marks(a.assessment_id, bad, actor=TEACHER)


def test_subject_in_use_cannot_be_deleted(setup):
    _test(setup)
    usage = dict(S.usage(setup["maths"].subject_id))
    assert usage.get("gradebook assessment(s)") == 1
