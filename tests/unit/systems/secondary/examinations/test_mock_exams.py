"""Mock exams (domain.mock_exams) on a temporary Secondary database."""

from __future__ import annotations

import pytest

from education_system.systems.secondary import SYSTEM_KEY
from education_system.systems.secondary.modules.examinations.domain import mock_exams as MX
from education_system.systems.secondary.modules.assessment.domain import target_grades as TGR
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import sen_details as SEN
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="mx_teach", role="teacher")
OTHER = Principal(username="other", role="teacher")
BOUNDS = "9=72, 8=64, 7=56, 6=46, 5=36, 4=26, 3=18"


@pytest.fixture
def env(tmp_path):
    from education_system.platform.identity.auth.core import UserAuth
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    UserAuth(db_path=str(tmp_path / "auth.db")).provision_user(
        "mx_teach", "Teach!ng-Pass-123", display_name="Ms Maths", email="m@s.org",
        systems=[(SYSTEM_KEY, "teacher")])
    pupils = [P.create_pupil({
        "legal_first_name": n, "legal_last_name": "Mock", "date_of_birth": "2011-01-15",
        "gender": "Female", "year_group": 11, "admission_date": "2021-09-01",
        "sen_status": "K" if n == "Ava" else "N"}, actor=ADMIN)
        for n in ("Ava", "Ben", "Cat", "Dan")]
    maths = S.create({"code": "MATH", "name": "Maths", "is_core": True}, actor=ADMIN)
    sci = S.create({"code": "SCI", "name": "Combined Science", "is_core": True}, actor=ADMIN)
    g = TG.create({"code": "11x/Ma1", "subject_id": maths.subject_id, "year_group": 11,
                   "teacher_username": "mx_teach"}, actor=ADMIN)
    TG.add_pupils([p.pupil_id for p in pupils[:3]], g.group_id, actor=ADMIN)
    yield {"pupils": pupils, "maths": maths, "sci": sci, "path": tmp_path}
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


def _series(name="Y11 Nov mocks", **kw):
    return MX.create_series({"name": name, "year_group": 11, "start_date": "2026-11-09",
                             "end_date": "2026-11-20", **kw}, actor=ADMIN)


def _paper(s, subject, name="Paper 1", day="2026-11-10", tier="Higher", bounds=BOUNDS,
           start="09:00", mx=80):
    return MX.create_paper({"series_id": s.series_id, "subject_id": subject.subject_id,
                            "paper_name": name, "paper_date": day, "start_time": start,
                            "duration_mins": 90, "max_marks": mx, "tier": tier,
                            "grade_boundaries": bounds}, actor=ADMIN)


# ── Grades ───────────────────────────────────────────────────────────

def test_boundaries_and_grades():
    b = MX.parse_boundaries("9=72, 8:64, 7=56", "Higher", 80)
    assert b == {"9": 72.0, "8": 64.0, "7": 56.0}
    assert MX.grade_from(70, b) == "8" and MX.grade_from(72, b) == "9"
    assert MX.grade_from(10, b) == "U" and MX.grade_from(None, b) is None
    with pytest.raises(MX.ValidationError):
        MX.parse_boundaries("9=20, 8=64", "Higher", 80)  # 9 below 8
    with pytest.raises(MX.ValidationError):
        MX.parse_boundaries("9=90", "N/A", 80)  # above max
    with pytest.raises(MX.ValidationError):
        MX.parse_boundaries("9=70", "Foundation", 80)  # foundation tops out at 5
    assert MX.grade_value("6-5") == 5.5 and MX.grade_value("U") == 0
    assert MX.compare("6-6", "6") == "On track"
    assert MX.compare("4", "6") == "Well below" and MX.compare("5", "6") == "Below"
    assert MX.compare(None, "6") == "No data"


# ── Series ───────────────────────────────────────────────────────────

def test_series_rules(env):
    s = _series()
    assert s.status == "Planned" and s.academic_year == "2026/27"
    with pytest.raises(MX.ValidationError):
        _series("y11 nov MOCKS")  # name taken, any case
    with pytest.raises(MX.ValidationError):
        MX.create_series({"name": "Bad", "year_group": 11, "start_date": "2026-11-20",
                          "end_date": "2026-11-09"}, actor=ADMIN)
    with pytest.raises(MX.PermissionDenied):
        MX.create_series({"name": "T", "year_group": 11, "start_date": "2026-11-09",
                          "end_date": "2026-11-10"}, actor=TEACHER)
    _paper(s, env["maths"], day="2026-11-18")
    with pytest.raises(MX.ValidationError):
        MX.update_series(s.series_id, {"end_date": "2026-11-12"}, actor=ADMIN)
    with pytest.raises(MX.ValidationError):
        MX.set_series_status(s.series_id, "Complete", actor=ADMIN)  # not adjacent


def test_paper_date_must_be_in_series(env):
    s = _series()
    with pytest.raises(MX.ValidationError) as e:
        _paper(s, env["maths"], day="2026-12-01")
    assert "within the series" in e.value.problems[0]


# ── Tiers, candidates, clashes ───────────────────────────────────────

def test_tiers_narrow_candidates_and_teachers_only_their_pupils(env):
    ava, ben, cat, dan = env["pupils"]
    s = _series()
    h = _paper(s, env["maths"])
    f = _paper(s, env["maths"], tier="Foundation", bounds="5=70, 4=55, 3=40")
    assert len(MX.candidates(h.paper_id)) == 3  # teaching group, no entries yet
    MX.set_tiers(s.series_id, env["maths"].subject_id,
                 {ava.pupil_id: "Higher", ben.pupil_id: "Higher", cat.pupil_id: "Foundation"},
                 actor=TEACHER)
    assert [c.pupil_id for c in MX.candidates(h.paper_id)] == [ava.pupil_id, ben.pupil_id]
    assert [c.pupil_id for c in MX.candidates(f.paper_id)] == [cat.pupil_id]
    with pytest.raises(MX.PermissionDenied):
        MX.set_tiers(s.series_id, env["maths"].subject_id, {dan.pupil_id: "Higher"},
                     actor=TEACHER)


def test_clashes_and_access_arrangements(env):
    ava = env["pupils"][0]
    SEN.save(ava.pupil_id, {"primary_need": "SPLD", "exam_access": "25% extra time"},
             actor=ADMIN)
    s = _series()
    m = _paper(s, env["maths"])
    _paper(s, env["sci"], name="Bio 1", tier="Combined", bounds="6-6=40, 4-4=28",
           start="10:00", mx=70)
    _paper(s, env["sci"], name="Bio 2", day="2026-11-11", tier="Combined",
           bounds="6-6=40, 4-4=28", mx=70)
    [(p, q, both)] = MX.clashes(s.series_id)
    assert {p.paper_name, q.paper_name} == {"Paper 1", "Bio 1"}
    assert len(both) == 3  # the maths group sit both
    assert MX.access_arrangements(m.paper_id) == {ava.pupil_id: "25% extra time"}


# ── Marks ────────────────────────────────────────────────────────────

def test_marks_only_while_marking_and_by_the_right_people(env):
    ava, ben, cat, dan = env["pupils"]
    s = _series()
    p = _paper(s, env["maths"])
    with pytest.raises(MX.ValidationError):
        MX.upsert_result(p.paper_id, {"pupil_id": ava.pupil_id, "marks_awarded": 60},
                         actor=ADMIN)  # still Planned
    MX.set_series_status(s.series_id, "InProgress", actor=ADMIN)
    r = MX.upsert_result(p.paper_id, {"pupil_id": ava.pupil_id, "marks_awarded": 60},
                         actor=TEACHER)
    assert (r.grade, r.mark_pct, r.grade_source) == ("7", 75.0, "auto")
    with pytest.raises(MX.PermissionDenied):
        MX.upsert_result(p.paper_id, {"pupil_id": ava.pupil_id, "marks_awarded": 61},
                         actor=OTHER)
    r = MX.upsert_result(p.paper_id, {"pupil_id": ben.pupil_id, "grade": "5"},
                         actor=TEACHER)
    assert r.grade_source == "manual" and r.marks_awarded is None


def test_save_sheet_is_all_or_nothing_and_blank_clears(env):
    ava, ben, *_ = env["pupils"]
    s = _series()
    p = _paper(s, env["maths"])
    MX.set_series_status(s.series_id, "InProgress", actor=ADMIN)
    with pytest.raises(MX.ValidationError) as e:
        MX.save_sheet(p.paper_id, {ava.pupil_id: {"marks_awarded": "50"},
                                   ben.pupil_id: {"marks_awarded": "99"}}, actor=ADMIN)
    assert "between 0 and 80" in e.value.problems[0]
    assert MX.list_results(p.paper_id) == []
    assert MX.save_sheet(p.paper_id, {ava.pupil_id: {"marks_awarded": "50"},
                                      ben.pupil_id: {"absent": "Y"}}, actor=ADMIN) == 2
    MX.save_sheet(p.paper_id, {ben.pupil_id: {}}, actor=ADMIN)
    assert [r.pupil_id for r in MX.list_results(p.paper_id)] == [ava.pupil_id]
    with pytest.raises(MX.ValidationError):
        MX.save_sheet(p.paper_id, {ava.pupil_id: {"absent": "Y", "marks_awarded": "3"}},
                      actor=ADMIN)


def test_new_boundaries_regrade_automatic_results_only(env):
    ava, ben, *_ = env["pupils"]
    s = _series()
    p = _paper(s, env["maths"])
    MX.set_series_status(s.series_id, "InProgress", actor=ADMIN)
    MX.save_sheet(p.paper_id, {ava.pupil_id: {"marks_awarded": "60"},
                               ben.pupil_id: {"marks_awarded": "30", "grade": "6"}},
                  actor=ADMIN)
    MX.update_paper(p.paper_id, {"grade_boundaries": "9=70, 8=59, 7=50, 6=40, 5=30"},
                    actor=ADMIN)
    grades = {r.pupil_id: r.grade for r in MX.list_results(p.paper_id)}
    assert grades == {ava.pupil_id: "8", ben.pupil_id: "6"}
    with pytest.raises(MX.ValidationError):
        MX.update_paper(p.paper_id, {"max_marks": 50}, actor=ADMIN)  # below 60
    MX.set_series_status(s.series_id, "Complete", actor=ADMIN)
    with pytest.raises(MX.ValidationError):
        MX.update_paper(p.paper_id, {"paper_date": "2026-11-11"}, actor=ADMIN)  # set-up over


# ── Subject grades, targets, release ─────────────────────────────────

def _marked_series(env):
    ava, ben, cat, dan = env["pupils"]
    s = _series()
    p1 = _paper(s, env["maths"])
    p2 = _paper(s, env["maths"], name="Paper 2", day="2026-11-12")
    MX.set_series_status(s.series_id, "InProgress", actor=ADMIN)
    MX.save_sheet(p1.paper_id, {ava.pupil_id: {"marks_awarded": "60"},
                                ben.pupil_id: {"marks_awarded": "30"},
                                cat.pupil_id: {"marks_awarded": "20"}}, actor=ADMIN)
    MX.save_sheet(p2.paper_id, {ava.pupil_id: {"marks_awarded": "66"},
                                ben.pupil_id: {"absent": "Y", "absence_reason": "Ill"},
                                cat.pupil_id: {"marks_awarded": "20"}}, actor=ADMIN)
    return s, p1, p2


def test_subject_grade_totals_the_papers_against_target(env):
    ava, ben, cat, _ = env["pupils"]
    TGR.upsert({"pupil_id": ava.pupil_id, "subject_id": env["maths"].subject_id,
                "target_grade": "8"}, actor=ADMIN)
    s, *_ = _marked_series(env)
    rows = {r["pupil"].pupil_id: r for r in MX.subject_results(s.series_id)}
    assert rows[ava.pupil_id]["marks"] == 126 and rows[ava.pupil_id]["max"] == 160
    assert rows[ava.pupil_id]["grade"] == "7"  # 126 >= 112 (7+7), < 128 (8+8)
    assert rows[ava.pupil_id]["vs_target"] == "Below"
    assert rows[ben.pupil_id]["grade"] is None
    assert "absent" in rows[ben.pupil_id]["note"]
    assert [r["pupil"].pupil_id for r in MX.below_target(s.series_id)] == [ava.pupil_id]


def test_release_needs_complete_and_locks_results(env):
    ava, *_ = env["pupils"]
    s, p1, _ = _marked_series(env)
    with pytest.raises(MX.ValidationError):
        MX.release_results(s.series_id, actor=ADMIN)  # still in progress
    MX.set_series_status(s.series_id, "Complete", actor=ADMIN)
    assert MX.release_results(s.series_id, actor=ADMIN).released
    with pytest.raises(MX.PermissionDenied):
        MX.upsert_result(p1.paper_id, {"pupil_id": ava.pupil_id, "marks_awarded": 61},
                         actor=TEACHER)
    with pytest.raises(MX.ValidationError):
        MX.update_paper(p1.paper_id, {"grade_boundaries": "9=70, 8=59"}, actor=ADMIN)
    with pytest.raises(MX.ValidationError):
        MX.delete_series(s.series_id, actor=ADMIN)
    with pytest.raises(MX.ValidationError):
        MX.set_series_status(s.series_id, "InProgress", actor=ADMIN)
    assert len(MX.results_for_pupil(ava.pupil_id, released_only=True)) == 2


def test_target_grades_progress_uses_the_latest_complete_mock(env):
    ava, *_ = env["pupils"]
    TGR.upsert({"pupil_id": ava.pupil_id, "subject_id": env["maths"].subject_id,
                "target_grade": "7"}, actor=ADMIN)
    s, *_ = _marked_series(env)
    assert TGR.progress(pupil_id=ava.pupil_id)[0]["current"] is None  # not complete yet
    MX.set_series_status(s.series_id, "Complete", actor=ADMIN)
    [row] = TGR.progress(pupil_id=ava.pupil_id)
    assert (row["current"], row["from"], row["status"]) == ("7", "Y11 Nov mocks", "On track")


def test_combined_science_grade_against_a_target(env):
    assert TGR.progress_status("6", "6-5") == "Below"
    assert TGR.progress_status("6", "7-6") == "Above"


def test_missing_marks_block_release(env):
    ava, ben, cat, _ = env["pupils"]
    s = _series()
    p = _paper(s, env["maths"])
    MX.set_series_status(s.series_id, "InProgress", actor=ADMIN)
    MX.save_sheet(p.paper_id, {ava.pupil_id: {"marks_awarded": "60"}}, actor=ADMIN)
    [(paper, missing)] = MX.missing_marks(s.series_id)
    assert {m.pupil_id for m in missing} == {ben.pupil_id, cat.pupil_id}
    MX.set_series_status(s.series_id, "Complete", actor=ADMIN)
    with pytest.raises(MX.ValidationError) as e:
        MX.release_results(s.series_id, actor=ADMIN)
    assert "2 mark(s)" in e.value.problems[0]


# ── CSV ──────────────────────────────────────────────────────────────

def test_csv_template_import_and_export(env):
    ava, ben, cat, _ = env["pupils"]
    s = _series()
    p = _paper(s, env["maths"])
    MX.set_series_status(s.series_id, "InProgress", actor=ADMIN)
    tpl = env["path"] / "sheet.csv"
    assert MX.export_sheet_template(p.paper_id, tpl, actor=ADMIN) == 3
    rows = tpl.read_text().splitlines()
    assert rows[0].startswith("Admission no,Pupil,Marks")
    filled = env["path"] / "filled.csv"
    filled.write_text("Admission no,Marks,Grade,Absent\n"
                      f"{ava.admission_no},60,,\n{ben.admission_no},,,Y\n"
                      f"{cat.admission_no},,,\n")
    assert MX.import_marks(p.paper_id, filled, actor=ADMIN) == 2
    bad = env["path"] / "bad.csv"
    bad.write_text(f"Admission no,Marks\n{ava.admission_no},500\nNOPE,4\n")
    with pytest.raises(MX.ValidationError) as e:
        MX.import_marks(p.paper_id, bad, actor=ADMIN)
    assert len(e.value.problems) == 2
    out = env["path"] / "out.csv"
    assert MX.export_results(s.series_id, out, actor=ADMIN) >= 2
    assert "Admission no" in out.read_text().splitlines()[0]
