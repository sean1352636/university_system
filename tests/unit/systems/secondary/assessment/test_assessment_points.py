"""Assessment point rules (domain.assessment_points) on a scratch school DB.

auth.db (for the teacher's login), the outbox and the activity log are
redirected, so nothing touches live data.
"""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.assessment.domain import assessment_points as AP
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="ap_teacher", role="teacher")
OTHER = Principal(username="ap_other", role="teacher")
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
    """Maths; 8x/Ma1 (three pupils) and 10x/Ma1 (one pupil) taught by ap_teacher."""
    from education_system.platform.identity.auth.core import UserAuth
    from education_system.systems.secondary import SYSTEM_KEY
    UserAuth(db_path=accounts._override).provision_user(
        "ap_teacher", "Teach!ng-Pass-123", display_name="Ms Maths", email="m@school.org",
        systems=[(SYSTEM_KEY, "teacher")])
    maths = S.create({"code": "MATH", "name": "Mathematics", "is_core": True}, actor=ADMIN)
    g8 = TG.create({"code": "8x/Ma1", "subject_id": maths.subject_id, "year_group": 8,
                    "teacher_username": "ap_teacher"}, actor=ADMIN)
    g10 = TG.create({"code": "10x/Ma1", "subject_id": maths.subject_id, "year_group": 10,
                     "teacher_username": "ap_teacher"}, actor=ADMIN)
    pupils = [_pupil(), _pupil(), _pupil()]
    TG.add_pupils([p.pupil_id for p in pupils], g8.group_id, actor=ADMIN)
    y10 = _pupil(10)
    TG.add_pupils([y10.pupil_id], g10.group_id, actor=ADMIN)
    return {"maths": maths, "group": g8, "g10": g10, "pupils": pupils, "y10": y10}


def _open(name="Autumn", years="8,10", **extra):
    pt = AP.create_point({"name": name, "year_groups": years, **extra}, actor=ADMIN)
    return AP.set_status(pt.point_id, "Open", actor=ADMIN)


# ── Points ───────────────────────────────────────────────────────────

def test_create_point_defaults():
    pt = AP.create_point({"name": "Autumn", "year_groups": [10, 8, 8]}, actor=ADMIN)
    assert pt.years == (8, 10) and pt.status == "Draft"
    assert pt.academic_year == TG.current_year()
    assert (pt.ks3_scale, pt.ks4_scale) == ("KS3 steps", "GCSE 9-1")
    assert pt.collect_predicted and pt.collect_attitude
    assert not pt.collect_homework and not pt.collect_comment
    assert pt.scale_for(8) == AP.SCALES["KS3 steps"] and pt.scale_for(11)[0] == "9"


def test_create_point_reports_every_problem():
    with pytest.raises(AP.ValidationError) as e:
        AP.create_point({"name": "", "year_groups": "5", "ks3_scale": "Levels",
                         "opens_on": "2026-12-01", "deadline": "2026-11-01"}, actor=ADMIN)
    text = " ".join(e.value.problems)
    for bit in ("name", "7 to 11", "KS3 scale", "deadline can't be before"):
        assert bit in text


def test_duplicate_name_in_a_year_refused():
    AP.create_point({"name": "Autumn", "year_groups": "8"}, actor=ADMIN)
    with pytest.raises(AP.ValidationError):
        AP.create_point({"name": "autumn", "year_groups": "9"}, actor=ADMIN)


def test_only_editors_manage_points():
    with pytest.raises(AP.PermissionDenied):
        AP.create_point({"name": "Autumn", "year_groups": "8"}, actor=TEACHER)
    pt = AP.create_point({"name": "Autumn", "year_groups": "8"}, actor=ADMIN)
    for call in (lambda: AP.update_point(pt.point_id, {"name": "X"}, actor=TEACHER),
                 lambda: AP.set_status(pt.point_id, "Open", actor=TEACHER),
                 lambda: AP.delete_point(pt.point_id, actor=TEACHER)):
        with pytest.raises(AP.PermissionDenied):
            call()


def test_status_moves(setup):
    pt = AP.create_point({"name": "Autumn", "year_groups": "8"}, actor=ADMIN)
    with pytest.raises(AP.ValidationError):
        AP.set_status(pt.point_id, "Published", actor=ADMIN)
    pt = AP.set_status(pt.point_id, "Open", actor=ADMIN)
    AP.save_sheet(pt.point_id, setup["group"].group_id,
                  {setup["pupils"][0].pupil_id: {"working_at": "Secure"}}, actor=TEACHER)
    with pytest.raises(AP.ValidationError):
        AP.set_status(pt.point_id, "Draft", actor=ADMIN)  # grades already in
    for to in ("Closed", "Published", "Closed", "Open"):
        assert AP.set_status(pt.point_id, to, actor=ADMIN).status == to


def test_only_this_years_points_open():
    pt = AP.create_point({"name": "Old", "year_groups": "8", "academic_year": "2020/21"},
                         actor=ADMIN)
    with pytest.raises(AP.ValidationError):
        AP.set_status(pt.point_id, "Open", actor=ADMIN)


def test_scales_and_used_years_fixed_once_grades_are_in(setup):
    pt = _open()
    AP.save_sheet(pt.point_id, setup["group"].group_id,
                  {setup["pupils"][0].pupil_id: {"working_at": "Secure"}}, actor=TEACHER)
    with pytest.raises(AP.ValidationError):
        AP.update_point(pt.point_id, {"ks3_scale": "GCSE 9-1"}, actor=ADMIN)
    with pytest.raises(AP.ValidationError):
        AP.update_point(pt.point_id, {"year_groups": "10"}, actor=ADMIN)
    assert AP.update_point(pt.point_id, {"year_groups": "8"}, actor=ADMIN).years == (8,)
    assert AP.update_point(pt.point_id, {"deadline": "2027-01-01"},
                           actor=ADMIN).deadline == "2027-01-01"


def test_published_point_cant_be_edited_or_deleted(setup):
    pt = _open()
    AP.set_status(pt.point_id, "Closed", actor=ADMIN)
    AP.set_status(pt.point_id, "Published", actor=ADMIN)
    with pytest.raises(AP.ValidationError):
        AP.update_point(pt.point_id, {"name": "X"}, actor=ADMIN)
    with pytest.raises(AP.ValidationError):
        AP.delete_point(pt.point_id, actor=ADMIN)


def test_delete_removes_grades(setup):
    pt = _open()
    AP.save_sheet(pt.point_id, setup["group"].group_id,
                  {setup["pupils"][0].pupil_id: {"working_at": "Secure"}}, actor=TEACHER)
    AP.delete_point(pt.point_id, actor=ADMIN)
    assert AP.list_points() == []
    with database.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM assessment_point_grades").fetchone()[0] == 0


def test_overdue(monkeypatch):
    pt = _open(years="8", deadline="2026-11-05")
    monkeypatch.setattr(AP, "_today", lambda: dt.date(2026, 11, 6))
    assert AP.get_point(pt.point_id).overdue


# ── Entering grades ──────────────────────────────────────────────────

def test_groups_for_point(setup):
    pt = _open()
    assert [g.code for g in AP.groups_for(pt)] == ["8x/Ma1", "10x/Ma1"]
    assert AP.groups_for(pt, teacher="ap_other") == []


def test_teacher_enters_own_group_while_open(setup):
    pt = AP.create_point({"name": "Autumn", "year_groups": "8"}, actor=ADMIN)
    g, (a, b, _c) = setup["group"], setup["pupils"]
    with pytest.raises(AP.PermissionDenied):
        AP.save_sheet(pt.point_id, g.group_id, {a.pupil_id: {"working_at": "Secure"}},
                      actor=TEACHER)  # still a draft
    AP.set_status(pt.point_id, "Open", actor=ADMIN)
    with pytest.raises(AP.PermissionDenied):
        AP.save_sheet(pt.point_id, g.group_id, {a.pupil_id: {"working_at": "Secure"}},
                      actor=OTHER)
    n = AP.save_sheet(pt.point_id, g.group_id,
                      {a.pupil_id: {"working_at": "secure", "predicted": "Mastering",
                                    "attitude": "2"},
                       b.pupil_id: {"working_at": "Emerging", "attitude": 4}}, actor=TEACHER)
    assert n == 2
    rows = {x.pupil_id: x for x in AP.grades(pt.point_id)}
    assert (rows[a.pupil_id].working_at, rows[a.pupil_id].predicted,
            rows[a.pupil_id].attitude) == ("Secure", "Mastering", 2)
    assert rows[a.pupil_id].group_code == "8x/Ma1" and rows[a.pupil_id].entered_by == \
        "ap_teacher"


def test_closed_point_only_data_manager_enters(setup):
    pt = _open()
    AP.set_status(pt.point_id, "Closed", actor=ADMIN)
    a = setup["pupils"][0]
    with pytest.raises(AP.PermissionDenied):
        AP.save_sheet(pt.point_id, setup["group"].group_id,
                      {a.pupil_id: {"working_at": "Secure"}}, actor=TEACHER)
    assert AP.save_sheet(pt.point_id, setup["group"].group_id,
                         {a.pupil_id: {"working_at": "Secure"}}, actor=ADMIN) == 1
    AP.set_status(pt.point_id, "Published", actor=ADMIN)
    with pytest.raises(AP.PermissionDenied):
        AP.save_sheet(pt.point_id, setup["group"].group_id,
                      {a.pupil_id: {"working_at": "Developing"}}, actor=ADMIN)


def test_sheet_is_all_or_nothing_and_checks_the_scale(setup):
    pt = _open()
    (a, b, _c), y10 = setup["pupils"], setup["y10"]
    with pytest.raises(AP.ValidationError) as e:
        AP.save_sheet(pt.point_id, setup["group"].group_id,
                      {a.pupil_id: {"working_at": "Secure"},
                       b.pupil_id: {"working_at": "7", "attitude": 9},
                       y10.pupil_id: {"working_at": "Secure"}}, actor=TEACHER)
    text = " ".join(e.value.problems)
    assert "isn't on the" in text and "1 (excellent) to 4" in text and "isn't in 8x/Ma1" in text
    assert AP.grades(pt.point_id) == []
    # Year 10 uses GCSE 9-1.
    AP.save_sheet(pt.point_id, setup["g10"].group_id,
                  {y10.pupil_id: {"working_at": "6", "predicted": "7"}}, actor=TEACHER)
    with pytest.raises(AP.ValidationError):
        AP.save_sheet(pt.point_id, setup["g10"].group_id,
                      {y10.pupil_id: {"working_at": "Secure"}}, actor=TEACHER)


def test_fields_not_collected_are_ignored_and_blank_row_clears(setup):
    pt = _open(years="8", collect_predicted=False, collect_attitude=False)
    a = setup["pupils"][0]
    g = setup["group"]
    AP.save_sheet(pt.point_id, g.group_id, {a.pupil_id: {"working_at": "Secure",
                                                         "predicted": "Mastering",
                                                         "attitude": 1,
                                                         "comment": "x"}}, actor=TEACHER)
    x = AP.grades(pt.point_id)[0]
    assert (x.predicted, x.attitude, x.comment) == (None, None, None)
    AP.save_sheet(pt.point_id, g.group_id, {a.pupil_id: {"working_at": ""}}, actor=TEACHER)
    assert AP.grades(pt.point_id) == []


def test_sheet_lists_members_with_their_grades(setup):
    pt = _open()
    a = setup["pupils"][0]
    AP.save_sheet(pt.point_id, setup["group"].group_id, {a.pupil_id: {"working_at": "Secure"}},
                  actor=TEACHER)
    rows = AP.sheet(pt.point_id, setup["group"].group_id)
    assert len(rows) == 3
    assert {p.pupil_id: (x.working_at if x else None) for p, x in rows}[a.pupil_id] == "Secure"


def test_from_gradebook_suggests_grades_on_the_scale(setup):
    from education_system.systems.secondary.modules.assessment.domain import gradebook as GB
    pt = _open()
    a, b, _c = setup["pupils"]
    sid = setup["maths"].subject_id
    GB.record_entry({"pupil": a.admission_no, "subject_id": sid, "assessment_name": "T1",
                     "grade": "Secure"}, actor=ADMIN)
    GB.record_entry({"pupil": b.admission_no, "subject_id": sid, "assessment_name": "T1",
                     "grade": "6"}, actor=ADMIN)  # not on the KS3 scale
    assert AP.from_gradebook(pt.point_id, setup["group"].group_id) == {a.pupil_id: "Secure"}


# ── Reports ──────────────────────────────────────────────────────────

def test_completion_and_summary(setup):
    pt = _open()
    a, b, _c = setup["pupils"]
    AP.save_sheet(pt.point_id, setup["group"].group_id,
                  {a.pupil_id: {"working_at": "Secure"}, b.pupil_id: {"attitude": 2}},
                  actor=TEACHER)  # b has no working-at grade: not done
    rows = {r["group"].code: r for r in AP.completion(pt.point_id)}
    assert (rows["8x/Ma1"]["done"], rows["8x/Ma1"]["pupils"], rows["8x/Ma1"]["pct"]) == (1, 3, 33)
    assert rows["10x/Ma1"]["done"] == 0
    s = AP.summary(pt.point_id)
    assert (s["groups"], s["complete"], s["pupils"], s["done"]) == (2, 0, 4, 1)


def test_chase_emails_teachers_with_unfinished_groups(setup):
    pt = _open()
    with pytest.raises(AP.PermissionDenied):
        AP.chase(pt.point_id, actor=TEACHER)
    r = AP.chase(pt.point_id, actor=ADMIN)
    assert len(r["sent"]) == 1 and r["no_email"] == []  # one teacher, both groups


def test_chase_when_all_done_refused(setup):
    pt = _open(years="10")
    AP.save_sheet(pt.point_id, setup["g10"].group_id,
                  {setup["y10"].pupil_id: {"working_at": "5"}}, actor=TEACHER)
    with pytest.raises(AP.ValidationError):
        AP.chase(pt.point_id, actor=ADMIN)


def test_distribution(setup):
    pt = _open()
    a, b, c = setup["pupils"]
    AP.save_sheet(pt.point_id, setup["group"].group_id,
                  {a.pupil_id: {"working_at": "Emerging", "attitude": 4},
                   b.pupil_id: {"working_at": "Mastering"},
                   c.pupil_id: {"working_at": "Emerging"}}, actor=TEACHER)
    d = AP.distribution(pt.point_id)
    assert list(d["subjects"]["MATH"].items()) == [("Mastering", 1), ("Emerging", 2)]
    assert d["attitude"] == {"Cause for concern": 1}


def test_progress_against_an_earlier_point(setup):
    a, b, c = setup["pupils"]
    g = setup["group"].group_id
    first = _open("Autumn", years="8")
    AP.save_sheet(first.point_id, g, {a.pupil_id: {"working_at": "Secure"},
                                      b.pupil_id: {"working_at": "Developing"},
                                      c.pupil_id: {"working_at": "Secure"}}, actor=TEACHER)
    AP.set_status(first.point_id, "Closed", actor=ADMIN)
    second = _open("Spring", years="8")
    AP.save_sheet(second.point_id, g, {a.pupil_id: {"working_at": "Mastering"},
                                       b.pupil_id: {"working_at": "Developing"},
                                       c.pupil_id: {"working_at": "Emerging"}}, actor=TEACHER)
    r = AP.progress(second.point_id, first.point_id)
    assert (r["up"], r["same"], r["down"]) == (1, 1, 1)
    assert [(d["pupil_id"], d["before"], d["now"]) for d in r["declines"]] == [
        (c.pupil_id, "Secure", "Emerging")]


def test_attitude_concerns(setup):
    pt = _open()
    a, b, _c = setup["pupils"]
    sci = S.create({"code": "SCI", "name": "Science", "is_core": True}, actor=ADMIN)
    gs = TG.create({"code": "8x/Sc1", "subject_id": sci.subject_id, "year_group": 8,
                    "teacher_username": "ap_teacher"}, actor=ADMIN)
    TG.add_pupils([a.pupil_id, b.pupil_id], gs.group_id, actor=ADMIN)
    AP.save_sheet(pt.point_id, setup["group"].group_id,
                  {a.pupil_id: {"attitude": 3}, b.pupil_id: {"attitude": 4}}, actor=TEACHER)
    AP.save_sheet(pt.point_id, gs.group_id,
                  {a.pupil_id: {"attitude": 4}, b.pupil_id: {"attitude": 1}}, actor=TEACHER)
    rows = AP.attitude_concerns(pt.point_id)
    assert [r["pupil_id"] for r in rows] == [a.pupil_id]
    assert rows[0]["count"] == 2
    assert {r["pupil_id"] for r in AP.attitude_concerns(pt.point_id, min_subjects=1,
                                                        worst=4)} == {a.pupil_id, b.pupil_id}


def test_for_pupil_prefers_published(setup):
    a = setup["pupils"][0]
    g = setup["group"].group_id
    first = _open("Autumn", years="8")
    AP.save_sheet(first.point_id, g, {a.pupil_id: {"working_at": "Secure"}}, actor=TEACHER)
    AP.set_status(first.point_id, "Closed", actor=ADMIN)
    AP.set_status(first.point_id, "Published", actor=ADMIN)
    second = _open("Spring", years="8")
    AP.save_sheet(second.point_id, g, {a.pupil_id: {"working_at": "Mastering"}},
                  actor=TEACHER)
    pt, rows = AP.for_pupil(a.pupil_id)
    assert pt.name == "Autumn" and rows[0].working_at == "Secure"
    assert AP.for_pupil(setup["pupils"][2].pupil_id) is None


# ── CSV ──────────────────────────────────────────────────────────────

def test_export_and_import(setup, tmp_path):
    pt = _open(years="8", collect_comment=True)
    a, b, _c = setup["pupils"]
    g = setup["group"].group_id
    AP.save_sheet(pt.point_id, g, {a.pupil_id: {"working_at": "Secure", "predicted": "Mastering",
                                                "comment": "=cmd"}}, actor=TEACHER)
    out = tmp_path / "out.csv"
    assert AP.export_point(pt.point_id, out, actor=TEACHER) == 1
    row = next(csv.DictReader(out.open()))
    assert row["Working at"] == "Secure" and row["Comment"] == "'=cmd"
    src = tmp_path / "in.csv"
    src.write_text(f"Admission no,Working at\n{a.admission_no},Developing\n"
                   f"{b.admission_no},Emerging\n")
    assert AP.import_grades(pt.point_id, g, src, actor=TEACHER) == 2
    rows = {x.pupil_id: x for x in AP.grades(pt.point_id)}
    # Columns the file leaves out keep their values.
    assert (rows[a.pupil_id].working_at, rows[a.pupil_id].predicted,
            rows[a.pupil_id].comment) == ("Developing", "Mastering", "=cmd")
    assert rows[b.pupil_id].working_at == "Emerging"


def test_import_rejects_bad_files(setup, tmp_path):
    pt = _open(years="8")
    src = tmp_path / "in.csv"
    src.write_text("Pupil,Grade\nx,y\n")
    with pytest.raises(AP.ValidationError):
        AP.import_grades(pt.point_id, setup["group"].group_id, src, actor=TEACHER)
    src.write_text("Admission no,Working at\nNOPE,Secure\n")
    with pytest.raises(AP.ValidationError):
        AP.import_grades(pt.point_id, setup["group"].group_id, src, actor=TEACHER)
    assert AP.grades(pt.point_id) == []


def test_history_records_changes(setup):
    pt = _open(years="8")
    AP.save_sheet(pt.point_id, setup["group"].group_id,
                  {setup["pupils"][0].pupil_id: {"working_at": "Secure"}}, actor=TEACHER)
    assert [h["action"] for h in AP.history(pt.point_id)] == ["grades", "status", "create"]
