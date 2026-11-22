"""Subject catalogue and curriculum plan rules (domain.subjects) on a scratch DB.

auth.db and the activity log are redirected, so nothing touches live data.
"""

from __future__ import annotations

import pytest

from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="teacher1", role="teacher")


@pytest.fixture(autouse=True)
def scratch(tmp_path):
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    activity_log.use_log_file(tmp_path / "activity.log")
    yield
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


def _subject(code="MATH", name="Mathematics", **extra):
    return S.create({"code": code, "name": name, **extra}, actor=ADMIN)


# ── Catalogue ────────────────────────────────────────────────────────

def test_create_cleans_and_defaults():
    s = _subject(" math ", "  Mathematics ", department="Maths", ebacc_category="maths",
                 exam_board="aqa", spec_code="8300", is_core="yes",
                 head_of_subject_email="HoS@School.org")
    assert (s.code, s.name, s.key_stage, s.qualification) == ("MATH", "Mathematics", "Both",
                                                              "GCSE")
    assert (s.ebacc_category, s.exam_board, s.is_core, s.is_active) == ("Maths", "AQA", True,
                                                                        True)
    assert s.head_of_subject_email == "hos@school.org" and s.years == (7, 8, 9, 10, 11)
    assert [h["action"] for h in S.history(s.subject_id)] == ["create"]


def test_ks3_subject_defaults_to_no_qualification():
    s = _subject("SCI", "Science", key_stage="KS3")
    assert s.qualification == "KS3" and s.years == (7, 8, 9)


@pytest.mark.parametrize("data", [
    {"code": "", "name": "X"}, {"code": "M", "name": "X"}, {"code": "MATHEMATICS", "name": "X"},
    {"code": "MA-TH", "name": "X"}, {"code": "MATH", "name": ""},
    {"code": "MATH", "name": "x" * 65}, {"code": "MATH", "name": "X", "key_stage": "KS5"},
    {"code": "MATH", "name": "X", "qualification": "A level"},
    {"code": "MATH", "name": "X", "exam_board": "Board X"},
    {"code": "MATH", "name": "X", "ebacc_category": "Art"},
    {"code": "MATH", "name": "X", "head_of_subject_email": "nope"},
    {"code": "MATH", "name": "X", "is_core": "maybe"},
    {"code": "MATH", "name": "X", "key_stage": "KS3", "qualification": "GCSE"},
    {"code": "MATH", "name": "X", "key_stage": "KS4", "qualification": "KS3"},
    {"code": "SCI", "name": "X", "key_stage": "KS3", "exam_board": "AQA"},
    {"code": "MATH", "name": "X", "colour": "red"},
])
def test_bad_subjects_refused(data):
    with pytest.raises(S.ValidationError):
        S.create(data, actor=ADMIN)
    assert S.list_subjects(active_only=False) == []


def test_code_and_name_unique():
    _subject()
    with pytest.raises(S.ValidationError, match="code MATH"):
        _subject("MATH", "Maths again")
    with pytest.raises(S.ValidationError, match="called"):
        _subject("MATHS", "MATHEMATICS")
    other = _subject("ENG", "English")
    with pytest.raises(S.ValidationError, match="code MATH"):
        S.update(other.subject_id, {"code": "math"}, actor=ADMIN)


def test_update_reports_changes_and_validates_whole_record():
    s = _subject()
    s2, changed = S.update(s.subject_id, {"department": "Maths", "spec_code": "8300"},
                           actor=ADMIN)
    assert changed == ["department", "spec_code"] and s2.department == "Maths"
    assert S.update(s.subject_id, {"department": "Maths"}, actor=ADMIN)[1] == []
    with pytest.raises(S.ValidationError, match="KS3-only"):
        S.update(s.subject_id, {"key_stage": "KS3"}, actor=ADMIN)  # still GCSE


def test_teacher_can_view_but_not_change():
    s = _subject()
    for call in (lambda: S.create({"code": "ENG", "name": "English"}, actor=TEACHER),
                 lambda: S.update(s.subject_id, {"name": "Maths"}, actor=TEACHER),
                 lambda: S.toggle_active(s.subject_id, actor=TEACHER),
                 lambda: S.delete(s.subject_id, actor=TEACHER),
                 lambda: S.set_lessons(s.subject_id, {7: 4}, actor=TEACHER),
                 lambda: S.set_periods_per_week(30, actor=TEACHER),
                 lambda: S.add_standard(actor=TEACHER)):
        with pytest.raises(S.PermissionDenied):
            call()
    assert S.get(s.subject_id).name == "Mathematics"


def test_filters():
    _subject("MATH", "Mathematics", department="Maths")
    _subject("SCI", "Science", key_stage="KS3")
    _subject("BIO", "Biology", key_stage="KS4")
    old = _subject("LAT", "Latin", qualification="Other")
    S.toggle_active(old.subject_id, actor=ADMIN)
    assert [s.code for s in S.list_subjects()] == ["BIO", "MATH", "SCI"]
    assert [s.code for s in S.list_subjects(key_stage="KS3")] == ["MATH", "SCI"]
    assert [s.code for s in S.list_subjects(key_stage="KS4")] == ["BIO", "MATH"]
    assert [s.code for s in S.list_subjects(qualification="Other", active_only=False)] == ["LAT"]
    assert [s.code for s in S.list_subjects(search="math")] == ["MATH"]
    assert [s.code for s in S.list_subjects(year_group=10)] == ["BIO", "MATH"]
    assert S.counts() == {"total": 4, "active": 3, "inactive": 1, "core": 0}


def test_toggle_and_delete():
    s = _subject()
    assert not S.toggle_active(s.subject_id, actor=ADMIN).is_active
    assert S.toggle_active(s.subject_id, actor=ADMIN).is_active
    S.set_lessons(s.subject_id, {7: 4}, actor=ADMIN)
    S.delete(s.subject_id, actor=ADMIN)
    with pytest.raises(S.NotFound):
        S.get(s.subject_id)
    assert S.history(s.subject_id)[0]["action"] == "delete"
    assert S.plan(active_only=False) == {}  # lessons went with it


def test_delete_refused_while_used():
    s = _subject()
    with database.connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS test_usage_groups (subject_id INTEGER)")
        conn.execute("INSERT INTO test_usage_groups VALUES (?)", (s.subject_id,))
    S.register_usage("test_usage_groups", "subject_id", "teaching group(s)")
    try:
        assert S.usage(s.subject_id) == [("teaching group(s)", 1)]
        with pytest.raises(S.ValidationError, match="1 teaching group"):
            S.delete(s.subject_id, actor=ADMIN)
    finally:
        S._USAGES.remove(("test_usage_groups", "subject_id", "teaching group(s)"))
    with pytest.raises(ValueError):
        S.register_usage("x; DROP TABLE subjects", "subject_id", "bad")


# ── Curriculum plan ──────────────────────────────────────────────────

def test_set_lessons_and_totals():
    m = _subject()
    sci = _subject("SCI", "Science", key_stage="KS3")
    now, warnings = S.set_lessons(m.subject_id, {7: "4", 8: 4, "9": 4, 10: 5, 11: 5},
                                  actor=ADMIN)
    assert now == {7: 4, 8: 4, 9: 4, 10: 5, 11: 5} and warnings == []
    S.set_lessons(sci.subject_id, {7: 3, 8: 3}, actor=ADMIN)
    assert S.year_totals() == {7: 7, 8: 7, 9: 4, 10: 5, 11: 5}
    now, _ = S.set_lessons(m.subject_id, {10: "", 11: 0}, actor=ADMIN)  # blank/0 removes
    assert now == {7: 4, 8: 4, 9: 4}
    assert S.history(m.subject_id)[0]["detail"]["10"] == {"from": 5, "to": 0}


@pytest.mark.parametrize("plan, msg", [
    ({10: 3}, "isn't in SCI's key stage"), ({7: 21}, "from 0 to 20"), ({7: -1}, "from 0"),
    ({7: "lots"}, "whole number"), ({6: 2}, "Unknown year"),
])
def test_bad_lessons_refused(plan, msg):
    sci = _subject("SCI", "Science", key_stage="KS3")
    with pytest.raises(S.ValidationError, match=msg):
        S.set_lessons(sci.subject_id, plan, actor=ADMIN)
    assert S.lessons(sci.subject_id) == {}


def test_over_the_week_is_a_warning_and_week_is_a_setting():
    assert S.periods_per_week() == S.DEFAULT_PERIODS_PER_WEEK
    S.set_periods_per_week("10", actor=ADMIN)
    m = _subject()
    _now, warnings = S.set_lessons(m.subject_id, {7: 11}, actor=ADMIN)
    assert warnings == ["Year 7 has 11 lessons planned - the timetable week has 10"]
    assert S.lessons(m.subject_id) == {7: 11}  # saved anyway
    for bad in ("9", "61", "x"):
        with pytest.raises(S.ValidationError):
            S.set_periods_per_week(bad, actor=ADMIN)


def test_core_subject_without_lessons_flagged():
    m = _subject(is_core=True)
    S.set_lessons(m.subject_id, {7: 4, 8: 4, 9: 4}, actor=ADMIN)
    assert "Core subject MATH has no lessons planned in Year 10, 11" in S.plan_warnings()


def test_narrowing_key_stage_drops_lessons_outside_it():
    s = _subject("HIST", "History", qualification="GCSE")
    S.set_lessons(s.subject_id, {7: 2, 10: 3}, actor=ADMIN)
    S.update(s.subject_id, {"key_stage": "KS4"}, actor=ADMIN)
    assert S.lessons(s.subject_id) == {10: 3}


def test_inactive_subjects_leave_the_plan():
    s = _subject()
    S.set_lessons(s.subject_id, {7: 4}, actor=ADMIN)
    S.toggle_active(s.subject_id, actor=ADMIN)
    assert S.plan() == {} and S.year_totals()[7] == 0
    assert S.plan(active_only=False) == {s.subject_id: {7: 4}}


# ── Standard subjects ────────────────────────────────────────────────

def test_add_standard_only_adds_missing():
    _subject("MATH", "Mathematics")
    _subject("FR", "French")  # same name, other code: not added again
    missing = {d["code"] for d in S.missing_standard()}
    assert "MATH" not in missing and "FREN" not in missing and "ENG" in missing
    made = S.add_standard(["ENG", "SCI", "PE"], actor=ADMIN)
    assert sorted(s.code for s in made) == ["ENG", "PE", "SCI"]
    assert S.get_by_code("SCI").qualification == "KS3"
    rest = S.add_standard(actor=ADMIN)
    assert len(rest) == len(S.STANDARD_SUBJECTS) - 5
    assert S.missing_standard() == [] and S.add_standard(actor=ADMIN) == []
