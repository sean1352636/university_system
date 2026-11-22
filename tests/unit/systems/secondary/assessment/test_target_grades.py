"""Target grade rules (domain.target_grades) on a scratch school DB.

auth.db (for the teacher's login) and the activity log are redirected, so
nothing touches live data.
"""

from __future__ import annotations

import csv
import datetime as dt

import pytest

from education_system.systems.secondary.modules.assessment.domain import target_grades as TGR
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.curriculum.domain import teaching_groups as TG
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="tg_teacher", role="teacher")
OTHER = Principal(username="tg_other", role="teacher")
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
    """Maths and BTEC Sport; 8x/Ma1 (three pupils) taught by tg_teacher; a
    Year 10 pupil and a pupil in no group."""
    from education_system.platform.identity.auth.core import UserAuth
    from education_system.systems.secondary import SYSTEM_KEY
    UserAuth(db_path=accounts._override).provision_user(
        "tg_teacher", "Teach!ng-Pass-123", display_name="Ms Maths", email="m@school.org",
        systems=[(SYSTEM_KEY, "teacher")])
    maths = S.create({"code": "MATH", "name": "Mathematics", "is_core": True}, actor=ADMIN)
    sport = S.create({"code": "SPT", "name": "BTEC Sport", "qualification": "BTEC",
                      "key_stage": "KS4"}, actor=ADMIN)
    g = TG.create({"code": "8x/Ma1", "subject_id": maths.subject_id, "year_group": 8,
                   "teacher_username": "tg_teacher"}, actor=ADMIN)
    pupils = [_pupil(), _pupil(), _pupil()]
    TG.add_pupils([p.pupil_id for p in pupils], g.group_id, actor=ADMIN)
    return {"maths": maths, "sport": sport, "group": g, "pupils": pupils,
            "y10": _pupil(10), "ungrouped": _pupil()}


def _set(pupil, grade="6", actor=ADMIN, subject="MATH", **extra):
    return TGR.upsert({"pupil": pupil.admission_no, "subject": subject,
                       "target_grade": grade, **extra}, actor=actor)


# ── Setting (the old upsert) ─────────────────────────────────────────

def test_upsert_sets_then_updates_one_row(setup):
    a = setup["pupils"][0]
    t = _set(a, "6", minimum_grade="5", aspirational_grade="8", source="fft", notes="n")
    assert (t.target_grade, t.minimum_grade, t.aspirational_grade, t.source, t.set_by,
            t.set_date) == ("6", "5", "8", "FFT", "admin2", dt.date.today().isoformat())
    t2 = _set(a, "7")
    assert t2.target_id == t.target_id and t2.target_grade == "7"
    assert t2.minimum_grade == "5" and t2.notes == "n"  # kept
    assert len(TGR.list_targets()) == 1


def test_grades_checked_against_the_scale(setup):
    a, y10 = setup["pupils"][0], setup["y10"]
    assert _set(a, "sec").target_grade == "Secure"  # KS3 steps allowed in Year 8
    with pytest.raises(TGR.ValidationError):
        _set(y10, "Secure")  # Year 10: GCSE only
    with pytest.raises(TGR.ValidationError):
        _set(a, "A*")
    with pytest.raises(TGR.ValidationError):
        _set(y10, "6", subject="SPT")  # BTEC uses D*/D/M/P
    assert _set(y10, "d*", subject="SPT").target_grade == "D*"


def test_reports_every_problem(setup):
    a = setup["pupils"][0]
    with pytest.raises(TGR.ValidationError) as e:
        TGR.upsert({"pupil": a.admission_no, "subject": "MATH", "target_grade": "",
                    "minimum_grade": "x", "source": "Bob", "set_date": "2099-01-01"},
                   actor=ADMIN)
    text = " ".join(e.value.problems)
    for bit in ("Target grade is required", "Minimum grade 'x'", "Source must be one of",
                "future"):
        assert bit in text


def test_minimum_and_aspirational_must_bracket_the_target(setup):
    a = setup["pupils"][0]
    with pytest.raises(TGR.ValidationError) as e:
        _set(a, "6", minimum_grade="7", aspirational_grade="5")
    assert len(e.value.problems) == 2
    with pytest.raises(TGR.ValidationError):
        _set(a, "6", minimum_grade="Secure")  # different scale


def test_unknown_pupil_or_subject(setup):
    with pytest.raises(TGR.ValidationError):
        TGR.upsert({"pupil": "NOPE", "subject": "MATH", "target_grade": "5"}, actor=ADMIN)
    with pytest.raises(TGR.ValidationError):
        TGR.upsert({"pupil": setup["pupils"][0].admission_no, "subject": "XX",
                    "target_grade": "5"}, actor=ADMIN)


# ── Who ──────────────────────────────────────────────────────────────

def test_teacher_sets_only_for_pupils_they_teach(setup):
    a = setup["pupils"][0]
    assert _set(a, "5", actor=TEACHER).set_by == "tg_teacher"
    with pytest.raises(TGR.PermissionDenied):
        _set(setup["ungrouped"], "5", actor=TEACHER)
    with pytest.raises(TGR.PermissionDenied):
        _set(a, "6", actor=OTHER)


def test_teacher_can_raise_but_not_lower(setup):
    a = setup["pupils"][0]
    _set(a, "5", actor=TEACHER)
    assert _set(a, "6", actor=TEACHER).target_grade == "6"
    with pytest.raises(TGR.PermissionDenied):
        _set(a, "4", actor=TEACHER)


def test_data_manager_lowers_with_a_reason(setup):
    a = setup["pupils"][0]
    _set(a, "6")
    with pytest.raises(TGR.ValidationError):
        _set(a, "5")
    t = TGR.upsert({"pupil": a.admission_no, "subject": "MATH", "target_grade": "5"},
                   actor=ADMIN, reason="Retest")
    assert t.target_grade == "5"
    h = TGR.history(a.pupil_id)
    assert [(x["action"], x["old"], x["new"], x["reason"]) for x in h] == [
        ("change", "6", "5", "Retest"), ("set", None, "6", None)]


def test_switching_scale_is_not_lowering(setup):
    a = setup["pupils"][0]
    _set(a, "6", actor=TEACHER)
    assert _set(a, "Emerging", actor=TEACHER).target_grade == "Emerging"


def test_only_data_manager_deletes(setup):
    a = setup["pupils"][0]
    t = _set(a, "6")
    with pytest.raises(TGR.PermissionDenied):
        TGR.delete(t.target_id, actor=TEACHER)
    TGR.delete(t.target_id, actor=ADMIN, reason="Left set")
    assert TGR.get_for(a.pupil_id, setup["maths"].subject_id) is None
    assert TGR.history(a.pupil_id)[0]["action"] == "delete"
    with pytest.raises(TGR.NotFound):
        TGR.get(t.target_id)


def test_unchanged_save_writes_no_history(setup):
    a = setup["pupils"][0]
    _set(a, "6")
    _set(a, "6")
    assert len(TGR.history(a.pupil_id)) == 1


# ── Lists (old filters) ──────────────────────────────────────────────

def test_list_filters(setup):
    a, b, _c = setup["pupils"]
    _set(a, "6", source="CAT4")
    _set(b, "5")
    _set(setup["y10"], "7")
    assert len(TGR.list_targets(year_group="8")) == 2
    assert [t.pupil_id for t in TGR.list_targets(source="CAT4")] == [a.pupil_id]
    assert [t.pupil_id for t in TGR.list_targets(pupil=a.admission_no)] == [a.pupil_id]
    assert len(TGR.list_targets(group_id=setup["group"].group_id)) == 2
    with pytest.raises(TGR.ValidationError):
        TGR.list_targets(source="Nope")


def test_distribution_best_first(setup):
    a, b, c = setup["pupils"]
    _set(a, "5")
    _set(b, "7")
    _set(c, "5")
    assert list(TGR.distribution(year_group=8).items()) == [("7", 1), ("5", 2)]


# ── Class sheet and missing ──────────────────────────────────────────

def test_class_sheet_all_or_nothing(setup):
    g = setup["group"]
    a, b, c = setup["pupils"]
    with pytest.raises(TGR.ValidationError) as e:
        TGR.save_class(g.group_id, {a.pupil_id: {"target_grade": "6"},
                                    b.pupil_id: {"target_grade": "zz"},
                                    setup["y10"].pupil_id: {"target_grade": "5"}},
                       actor=TEACHER)
    assert len(e.value.problems) == 2
    assert TGR.list_targets() == []
    n = TGR.save_class(g.group_id, {a.pupil_id: {"target_grade": "6", "source": "KS2"},
                                    b.pupil_id: {"target_grade": "Secure"},
                                    c.pupil_id: {"target_grade": ""}}, actor=TEACHER)
    assert n == 2
    sheet = {p.pupil_id: t for p, t in TGR.class_sheet(g.group_id)}
    assert sheet[a.pupil_id].source == "KS2" and sheet[c.pupil_id] is None


def test_class_sheet_lowering_needs_data_manager(setup):
    g = setup["group"]
    a = setup["pupils"][0]
    _set(a, "6")
    with pytest.raises(TGR.PermissionDenied):
        TGR.save_class(g.group_id, {a.pupil_id: {"target_grade": "5"}}, actor=TEACHER)
    assert TGR.save_class(g.group_id, {a.pupil_id: {"target_grade": "5"}}, actor=ADMIN,
                          reason="Moved set") == 1


def test_missing_targets(setup):
    a, b, c = setup["pupils"]
    _set(a, "6")
    rows = TGR.missing()
    assert [(g.code, {p.pupil_id for p in ps}) for g, ps in rows] == [
        ("8x/Ma1", {b.pupil_id, c.pupil_id})]
    assert TGR.missing(teacher="tg_other") == []


# ── Progress against target ──────────────────────────────────────────

def test_progress_status():
    assert TGR.progress_status("6", "7") == "Above"
    assert TGR.progress_status("6", "6") == "On track"
    assert TGR.progress_status("6", "5") == "Below"
    assert TGR.progress_status("6", "3") == "Well below"
    assert TGR.progress_status("6", None) == "No data"
    assert TGR.progress_status("6", "Secure") == "Different scale"
    assert TGR.progress_status("Secure", "Sec") == "On track"


def test_progress_uses_assessment_points_then_gradebook(setup):
    from education_system.systems.secondary.modules.assessment.domain import assessment_points as AP
    from education_system.systems.secondary.modules.assessment.domain import gradebook as GB
    a, b, c = setup["pupils"]
    g = setup["group"]
    _set(a, "Secure")
    _set(b, "Secure")
    _set(c, "6")
    pt = AP.create_point({"name": "Autumn", "year_groups": "8"}, actor=ADMIN)
    AP.set_status(pt.point_id, "Open", actor=ADMIN)
    AP.save_sheet(pt.point_id, g.group_id, {a.pupil_id: {"working_at": "Mastering"},
                                            b.pupil_id: {"working_at": "Emerging"}},
                  actor=TEACHER)
    GB.record_entry({"pupil": c.admission_no, "subject_id": setup["maths"].subject_id,
                     "assessment_name": "T1", "grade": "5"}, actor=ADMIN)
    rows = {r["target"].pupil_id: r for r in TGR.progress()}
    assert (rows[a.pupil_id]["status"], rows[a.pupil_id]["from"]) == ("Above", "Autumn")
    assert rows[b.pupil_id]["status"] == "Well below"
    assert (rows[c.pupil_id]["current"], rows[c.pupil_id]["from"],
            rows[c.pupil_id]["status"]) == ("5", "gradebook", "Below")
    assert TGR.progress_summary()["Well below"] == 1
    assert [r["target"].pupil_id for r in TGR.progress(pupil_id=c.pupil_id)] == [c.pupil_id]
    assert [r["target"].pupil_id for r in TGR.progress(status="Above")] == [a.pupil_id]


# ── CSV ──────────────────────────────────────────────────────────────

def test_export(setup, tmp_path):
    a = setup["pupils"][0]
    _set(a, "6", notes="=sum")
    out = tmp_path / "t.csv"
    assert TGR.export_csv(out, actor=TEACHER) == 1
    row = next(csv.DictReader(out.open()))
    assert row["Target"] == "6" and row["Subject"] == "MATH" and row["Notes"] == "'=sum"


def test_import_is_data_manager_only_and_all_or_nothing(setup, tmp_path):
    a, b, _c = setup["pupils"]
    src = tmp_path / "in.csv"
    src.write_text(f"Admission no,Subject,Target,Minimum\n{a.admission_no},MATH,6,5\n"
                   f"{b.admission_no},math,7,\n")
    with pytest.raises(TGR.PermissionDenied):
        TGR.import_csv(src, actor=TEACHER)
    assert TGR.import_csv(src, actor=ADMIN, source="FFT") == {"set": 2, "changed": 0,
                                                              "unchanged": 0}
    assert TGR.get_for(a.pupil_id, setup["maths"].subject_id).source == "FFT"
    assert TGR.import_csv(src, actor=ADMIN)["unchanged"] == 2
    src.write_text(f"Admission no,Subject,Target\n{a.admission_no},MATH,9\nNOPE,MATH,5\n"
                   f"{b.admission_no},XX,5\n")
    with pytest.raises(TGR.ValidationError) as e:
        TGR.import_csv(src, actor=ADMIN)
    assert len(e.value.problems) == 2
    assert TGR.get_for(a.pupil_id, setup["maths"].subject_id).target_grade == "6"


def test_import_needs_columns_and_no_duplicates(setup, tmp_path):
    a = setup["pupils"][0]
    src = tmp_path / "in.csv"
    src.write_text("Pupil,Grade\nx,y\n")
    with pytest.raises(TGR.ValidationError):
        TGR.import_csv(src, actor=ADMIN)
    src.write_text(f"Admission no,Subject,Target\n{a.admission_no},MATH,6\n"
                   f"{a.admission_no},MATH,7\n")
    with pytest.raises(TGR.ValidationError):
        TGR.import_csv(src, actor=ADMIN)


def test_subject_in_use_cant_be_deleted(setup):
    _set(setup["pupils"][0], "6")
    assert ("target grade(s)", 1) in S.usage(setup["maths"].subject_id)
