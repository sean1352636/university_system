"""Attainment 8, Progress 8 and the headline measures (domain.headline_measures)."""

from __future__ import annotations

import pytest

from education_system.systems.secondary.modules.examinations.domain import gcse_results as G
from education_system.systems.secondary.modules.assessment.domain import headline_measures as HM
from education_system.systems.secondary.modules.assessment.domain import target_grades as TGR
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="teacher1", role="teacher")
YEAR = HM.current_year()


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


def _pupil(year=11, **extra):
    global _n
    _n += 1
    return P.create_pupil({
        "legal_first_name": f"Pupil{_n}", "legal_last_name": f"Test{_n:03d}",
        "date_of_birth": f"{2026 - year - 4}-01-15", "gender": "Female", "year_group": year,
        "admission_date": "2021-09-01", **extra}, actor=ADMIN)


SUBJECTS = [("ENLA", "English Language", "English", "GCSE"),
            ("ENLI", "English Literature", "English", "GCSE"),
            ("MATH", "Mathematics", "Maths", "GCSE"),
            ("CSCI", "Combined Science", "Science", "GCSE"),
            ("HIST", "History", "Humanities", "GCSE"),
            ("FREN", "French", "Languages", "GCSE"),
            ("ART", "Art", None, "GCSE"),
            ("SPT", "BTEC Sport", None, "BTEC"),
            ("MUS", "Music", None, "GCSE")]


@pytest.fixture
def school():
    subs = {code: S.create({"code": code, "name": name, "key_stage": "KS4",
                            "qualification": q, "ebacc_category": cat}, actor=ADMIN)
            for code, name, cat, q in SUBJECTS}
    return {"s": subs, "ava": _pupil(fsm_eligible=True), "ben": _pupil(gender="Male"),
            "cy": _pupil()}


def _results(pupil, grades):
    for code, grade in grades.items():
        G.record(pupil.pupil_id, {"subject": code, "grade": grade,
                                  "exam_year": int(YEAR[:4])}, actor=ADMIN)


AVA = {"ENLA": "6", "ENLI": "7", "MATH": "5", "CSCI": "6", "HIST": "8", "FREN": "4",
       "ART": "9", "MUS": "3"}


# ── The slot rules ───────────────────────────────────────────────────

def test_slots_follow_the_dfe_rules():
    s = HM.slot_grades([(n, c, q, g) for (_code, n, c, q), g in zip(SUBJECTS, (
        "6", "7", "5", "6-5", "8", "4", "9", "D*", "3"))])
    # English: both taken, better (7) counts twice; language (6) can go in Open.
    assert s["english_grade"] == "7" and s["english_double"] and s["english_points"] == 14
    assert s["maths_points"] == 10
    # EBacc: History 8, combined science 5.5 x2 (French 4 is fourth best).
    assert sorted([s["ebacc1_grade"], s["ebacc2_grade"], s["ebacc3_grade"]]) == [
        "6-5", "6-5", "8"]
    assert s["ebacc_points"] == 19
    # Open: Art 9, BTEC D* 8.5, then English language 6.
    assert s["open_points"] == 23.5
    assert s["total_points"] == 66.5 and s["ebacc_entered"] is True
    assert {d["subject"] for d in s["detail"] if d["slot"].startswith("Open")} == {
        "Art", "BTEC Sport", "English Language"}


def test_one_english_counts_once_and_empty_slots_score_nothing():
    s = HM.slot_grades([("English Language", "English", "GCSE", "5"),
                        ("Mathematics", "Maths", "GCSE", "U"),
                        ("Food", None, "GCSE short course", "7"),
                        ("Cookery", None, "Other", "Pass")])
    assert s["english_points"] == 5 and not s["english_double"]
    assert s["total_points"] == 5 and s["ebacc1_grade"] is None and s["open1_grade"] is None
    assert {d["subject"]: d["note"] for d in s["detail"] if d["slot"] == "Not counted"} == {
        "Food": "short course - not counted", "Cookery": "no points scale"}
    assert s["ebacc_entered"] is False


# ── Calculated records ───────────────────────────────────────────────

def test_actual_a8_from_released_results(school):
    _results(school["ava"], AVA)
    _results(school["ben"], {"ENLA": "4", "MATH": "4"})
    out = HM.calculate(11, "Actual", actor=ADMIN)
    assert out["saved"] == [school["ava"].admission_no, school["ben"].admission_no]
    assert out["no_data"] == [school["cy"].admission_no]
    a = HM.get_for(school["ava"].pupil_id, YEAR, "Actual")
    # 14 (Eng lit 7 x2) + 10 + History 8 + science 6 x2 + Art 9, Eng lang 6, French 4
    assert a.total_points == 14 + 10 + 8 + 12 + 9 + 6 + 4 and a.method == "Calculated"
    assert a.average_grade == round(a.total_points / 10, 2) and a.ebacc_entered
    b = HM.get_for(school["ben"].pupil_id, YEAR, "Actual")
    assert b.total_points == 4 + 8  # one English: single weight
    with pytest.raises(HM.PermissionDenied):
        HM.calculate(11, "Actual", actor=TEACHER)


def test_target_a8_and_entered_records_are_kept(school):
    ava = school["ava"]
    for code in ("ENLA", "ENLI", "MATH", "HIST"):
        TGR.upsert({"pupil": ava.admission_no, "subject": code, "target_grade": "7"},
                   actor=ADMIN)
    HM.calculate(11, "Target", actor=ADMIN)
    # English 7 x2, maths 7 x2, History 7 (EBacc), the other English 7 (Open)
    assert HM.get_for(ava.pupil_id, YEAR, "Target").total_points == 14 + 14 + 7 + 7
    rec = HM.upsert({"pupil": ava.admission_no, "academic_year": YEAR,
                     "record_source": "Estimated", "english_grade": "6", "maths_grade": "5",
                     "ebacc1_grade": "6-5", "open1_grade": "X"}, actor=ADMIN)
    assert rec.method == "Entered" and rec.total_points == 12 + 10 + 5.5
    with pytest.raises(HM.ValidationError):
        HM.upsert({"pupil": ava.admission_no, "english_grade": "A*"}, actor=ADMIN)
    edited = HM.update(rec.record_id, {"maths_grade": "6"}, actor=ADMIN)
    assert edited.total_points == 12 + 12 + 5.5
    s = HM.cohort_summary(academic_year=YEAR)
    assert s["records"] == 2 and s["by_source"] == {"Target": 1, "Estimated": 1}
    assert HM.delete(rec.record_id, actor=ADMIN)
    assert HM.get_for(ava.pupil_id, YEAR, "Estimated") is None


def test_recalculating_leaves_hand_entered_records(school):
    _results(school["ava"], AVA)
    HM.upsert({"pupil": school["ava"].admission_no, "record_source": "Actual",
               "english_grade": "9"}, actor=ADMIN)
    out = HM.calculate(11, "Actual", actor=ADMIN)
    assert out["kept"] == [school["ava"].admission_no]
    assert HM.get_for(school["ava"].pupil_id, YEAR, "Actual").total_points == 18
    HM.calculate(11, "Actual", actor=ADMIN, overwrite_entered=True)
    assert HM.get_for(school["ava"].pupil_id, YEAR, "Actual").method == "Calculated"


# ── KS2, estimates and Progress 8 ────────────────────────────────────

def _estimates():
    for ks2, a8, eng in ((80, 20.0, 4.0), (100, 45.0, 10.0), (110, 65.0, 14.0)):
        HM.set_estimate(YEAR, {"ks2_from": ks2, "expected_a8": a8, "expected_english": eng},
                        actor=ADMIN)


def test_ks2_prior_attainment(school, scratch):
    ava = school["ava"]
    k = HM.set_ks2(ava.pupil_id, {"reading_scaled": 104, "maths_scaled": 101}, actor=ADMIN)
    assert k.prior == 102.5
    for bad in ({"reading_scaled": 6}, {"maths_scaled": 121}, {}):
        with pytest.raises(HM.ValidationError):
            HM.set_ks2(ava.pupil_id, bad, actor=ADMIN)
    f = scratch / "ks2.csv"
    f.write_text(f"admission_no,reading,maths\n{school['ben'].admission_no},95,\n"
                 "NOPE,100,100\n")
    with pytest.raises(HM.ValidationError):  # all or nothing
        HM.import_ks2(f, actor=ADMIN)
    f.write_text(f"admission_no,reading,maths\n{school['ben'].admission_no},95,\n")
    assert HM.import_ks2(f, actor=ADMIN) == {"imported": 1}
    assert HM.get_ks2(school["ben"].pupil_id).prior == 95
    assert [p.pupil_id for p, _k in HM.ks2_list(year_group=11, missing_only=True)] == [
        school["cy"].pupil_id]


def test_progress_8_from_estimates(school):
    ava, ben = school["ava"], school["ben"]
    _results(ava, AVA)
    _results(ben, {"ENLA": "4", "MATH": "4"})
    HM.calculate(11, "Actual", actor=ADMIN)
    HM.set_ks2(ava.pupil_id, {"reading_scaled": 104, "maths_scaled": 101}, actor=ADMIN)
    with pytest.raises(HM.ValidationError) as e:  # no estimates yet
        HM.calculate_p8(11, actor=ADMIN)
    assert "estimates" in e.value.problems[0]
    _estimates()
    out = HM.calculate_p8(11, actor=ADMIN)
    assert out["saved"] == [ava.admission_no]
    assert set(out["no_ks2"]) == {ben.admission_no, school["cy"].admission_no}
    r = HM.get_p8_for(ava.pupil_id, YEAR)
    assert r.ks2_prior == 102.5 and r.expected_a8 == 45.0 and r.a8_source == "Actual"
    assert r.progress_8 == round((63 - 45) / 10, 2)
    assert r.p8_english == round((14 - 10) / 2, 2) and r.p8_maths is None
    s = HM.p8_summary(academic_year=YEAR)
    assert s["records"] == 1 and s["average_p8"] == r.progress_8


def test_progress_8_by_hand_and_refresh(school):
    ben = school["ben"]
    _estimates()
    rec = HM.upsert_p8({"pupil": ben.admission_no, "ks2_prior": 112, "attainment_8": 60},
                       actor=ADMIN)
    assert rec.expected_a8 == 65.0 and rec.progress_8 == -0.5 and rec.a8_source == "Entered"
    with pytest.raises(HM.ValidationError):
        HM.upsert_p8({"pupil": ben.admission_no, "ks2_prior": 5}, actor=ADMIN)
    with pytest.raises(HM.ValidationError):
        HM.refresh_a8(rec.record_id, actor=ADMIN)  # no A8 record yet
    _results(ben, {"ENLA": "7", "ENLI": "7", "MATH": "7"})
    HM.calculate(11, "Actual", actor=ADMIN)
    got = HM.refresh_a8(rec.record_id, actor=ADMIN)
    assert got.attainment_8 == 14 + 14 + 7 and got.a8_source == "Actual"
    assert got.progress_8 == round((35 - 65) / 10, 2)
    assert HM.delete_p8(rec.record_id, actor=ADMIN)


def test_estimates_import_and_copy(school, scratch):
    f = scratch / "est.csv"
    f.write_text("ks2_from,expected_a8,expected_english\n80,18.5,3\n100,46.1,9.8\n")
    assert HM.import_estimates(YEAR, f, actor=ADMIN) == {"imported": 2}
    nxt = f"{int(YEAR[:4]) + 1}/{(int(YEAR[:4]) + 2) % 100:02d}"
    assert HM.copy_estimates(YEAR, nxt, actor=ADMIN) == 2
    assert HM.estimate_for(nxt, 104).expected_a8 == 46.1
    assert HM.estimate_for(nxt, None) is None
    f.write_text("ks2_from,expected_a8\n100,95\n")
    with pytest.raises(HM.ValidationError):
        HM.import_estimates(YEAR, f, actor=ADMIN)
    assert len(HM.estimates(YEAR)) == 2  # nothing replaced


# ── Headline measures ────────────────────────────────────────────────

def test_headline_measures_and_disadvantaged_gap(school, scratch):
    ava, ben = school["ava"], school["ben"]  # Ava is FSM, Ben isn't
    _results(ava, AVA)
    _results(ben, {"ENLA": "4", "MATH": "4"})
    HM.calculate(11, "Actual", actor=ADMIN)
    for p in (ava, ben):
        HM.set_ks2(p.pupil_id, {"reading_scaled": 104, "maths_scaled": 101}, actor=ADMIN)
    _estimates()
    HM.calculate_p8(11, actor=ADMIN)
    h = HM.headline(year_group=11, academic_year=YEAR, record_source="Actual")
    by = {g["key"]: g for g in h["groups"]}
    assert by["all"]["pupils"] == 3 and by["all"]["with_a8"] == 2
    assert by["all"]["average_a8"] == round((63 + 12) / 2, 1)
    assert by["all"]["eng_maths_4"] == 100.0 and by["all"]["eng_maths_5"] == 50.0
    assert by["all"]["ebacc_entry"] == 50.0
    assert by["fsm"]["average_a8"] == 63 and by["not_fsm"]["average_a8"] == 12
    assert h["disadvantaged_gap"]["average_a8"] == 51
    assert [p.pupil_id for p in h["missing_a8"]] == [school["cy"].pupil_id]
    assert HM.export_csv(scratch / "a8.csv", actor=ADMIN, academic_year=YEAR) == 2
    assert "progress_8" in (scratch / "a8.csv").read_text().splitlines()[0]
    assert HM.for_pupil(ava.pupil_id)["a8"]["Actual"].total_points == 63


def test_an_unreadable_file_is_a_problem_not_a_crash(school, scratch):
    with pytest.raises(HM.ValidationError) as e:
        HM.import_ks2(scratch / "missing.csv", actor=ADMIN)
    assert "Couldn't read missing.csv" in e.value.problems[0]
    with pytest.raises(HM.ValidationError):
        HM.import_estimates(YEAR, scratch / "missing.csv", actor=ADMIN)
