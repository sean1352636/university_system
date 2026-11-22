"""Results Analysis (modules.reporting.domain.results_analysis) on a scratch DB."""

from __future__ import annotations

import csv

import pytest

from education_system.systems.secondary.modules.assessment.domain import assessment_points as AP
from education_system.systems.secondary.modules.assessment.domain import target_grades as TGR
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.reporting.domain import results_analysis as RA
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="ann", role="teacher")


@pytest.fixture(autouse=True)
def scratch(tmp_path):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    yield tmp_path
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


_n = 0


def _pupil(**extra):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Pupil{_n}", "legal_last_name": f"Test{_n:03d}",
        "date_of_birth": "2012-01-15", "gender": "Female", "year_group": 10,
        "form_group": "10A", "admission_date": "2024-09-01", **extra}, actor=ADMIN)


def _point(name, grades, school):
    pt = AP.create_point({"name": name, "year_groups": "10"}, actor=ADMIN)
    pt = AP.set_status(pt.point_id, "Open", actor=ADMIN)
    for code, by_pupil in grades.items():
        AP.save_sheet(pt.point_id, school["groups"][code].group_id,
                      {school["pupils"][i].pupil_id: {"working_at": g}
                       for i, g in enumerate(by_pupil)}, actor=ADMIN)
    return pt


@pytest.fixture
def school():
    maths = S.create({"code": "MATH", "name": "Mathematics", "is_core": True}, actor=ADMIN)
    eng = S.create({"code": "ENG", "name": "English Language", "is_core": True}, actor=ADMIN)
    pupils = [_pupil(), _pupil(gender="Male", fsm_eligible=True), _pupil(sen_status="K")]
    groups = {}
    for s in (maths, eng):
        g = TG.create({"code": f"10x/{s.code}", "subject_id": s.subject_id, "year_group": 10},
                      actor=ADMIN)
        TG.add_pupils([p.pupil_id for p in pupils], g.group_id, actor=ADMIN)
        groups[s.code] = g
    sch = {"maths": maths, "eng": eng, "pupils": pupils, "groups": groups}
    sch["autumn"] = _point("Autumn", {"MATH": ["6", "4", "7"], "ENG": ["5", "3", "7"]}, sch)
    for i, subj, grade in ((0, maths, "6"), (1, maths, "6"), (2, eng, "6")):
        TGR.upsert({"pupil_id": pupils[i].pupil_id, "subject_id": subj.subject_id,
                    "target_grade": grade}, actor=ADMIN)
    return sch


def test_subject_measures_targets_and_residuals(school):
    a = RA.analyse(ADMIN, f"point:{school['autumn'].point_id}")
    subj = {s["code"]: s for s in a.subjects()}
    m, e = subj["MATH"], subj["ENG"]
    assert (m["results"], m["average"], m["pct_4"], m["pct_7"]) == (3, 5.67, 100.0, 33.3)
    assert e["pct_4"] == 66.7 and e["distribution"] == {"7": 1, "5": 1, "3": 1}
    assert (m["on_track"], m["well_below"], m["no_target"]) == (1, 1, 1)
    assert e["above"] == 1
    assert m["residual"] == 0.67 and e["residual"] == -0.67
    h = a.headline()
    assert (h["pupils"], h["results"], h["eng_maths_4"], h["eng_maths_5"]) == (3, 6, 2, 2)
    assert h["target_Well below"] == 1


def test_groups_pupils_and_filters(school):
    a = RA.analyse(ADMIN, ("point", school["autumn"].point_id))
    groups = {g["group"]: g for g in a.groups()}
    assert groups["FSM eligible"]["average"] == 3.5 and groups["Male"]["pupils"] == 1
    assert groups["SEN support (K)"]["pct_7"] == 100.0
    worst = a.pupils()[0]
    assert worst["pupil"].pupil_id == school["pupils"][1].pupil_id and worst["below"] == 1
    only = RA.analyse(ADMIN, f"point:{school['autumn'].point_id}",
                      subject_id=school["maths"].subject_id)
    assert {r.subject_code for r in only.results} == {"MATH"}
    assert "MATH" in RA.pupil_text(a, school["pupils"][0].pupil_id)


def test_compare_two_points(school):
    spring = _point("Spring", {"MATH": ["7", "4", "6"]}, school)
    c = RA.compare(ADMIN, f"point:{school['autumn'].point_id}", f"point:{spring.point_id}")
    assert len(c["pairs"]) == 3 and c["only_first"] == 3          # English only in autumn
    m = c["subjects"][0]
    assert (m["up"], m["same"], m["down"], m["avg_diff"]) == (1, 1, 1, 0.0)


def test_sources_tables_export(school, scratch):
    srcs = RA.sources(TEACHER)
    assert any(s.kind == "point" and s.source_id == school["autumn"].point_id for s in srcs)
    a = RA.analyse(TEACHER, f"point:{school['autumn'].point_id}")
    for section in ("subjects", "distribution", "targets", "groups", "pupils", "headline"):
        assert RA.table(a, section)[0]
    path = scratch / "res.csv"
    RA.export_csv(path, a, "distribution", actor=TEACHER)
    rows = list(csv.reader(open(path, encoding="utf-8")))
    assert rows[0] == ["Subject", "7", "6", "5", "4", "3", "Total"]
    with pytest.raises(RA.ValidationError):
        RA.analyse(ADMIN, "nonsense")
    a8 = RA.a8p8(ADMIN, year_group=10)
    assert RA.table(None, "a8p8", a8=a8)[1][0][0] == "All pupils"
    with pytest.raises(RA.PermissionDenied):
        RA.sources(Principal(username="p", role="parent"))


def test_cli_menu(school, monkeypatch, capsys):
    from education_system.systems.secondary.modules.reporting.cli import results_analysis_cli as M
    M._state.clear()
    answers = iter(["1", "1", "", "", "", "", "3", "", "5", "", "0"])
    monkeypatch.setattr("builtins.input", lambda _p="": next(answers))
    M.menu(TEACHER)
    out = capsys.readouterr().out
    assert "6 result(s)" in out and "Well below" in out
