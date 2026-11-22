"""GCSE results (domain.gcse_results) on a scratch school DB.

The activity log is redirected, so nothing touches live data.
"""

from __future__ import annotations

import csv

import pytest

from education_system.systems.secondary.modules.examinations.domain import gcse_results as G
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
TEACHER = Principal(username="teacher1", role="teacher")


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


@pytest.fixture
def school():
    S.create({"code": "ENG", "name": "English Language", "ebacc_category": "English",
              "exam_board": "AQA"}, actor=ADMIN)
    S.create({"code": "MATH", "name": "Maths", "ebacc_category": "Maths"}, actor=ADMIN)
    S.create({"code": "BIO", "name": "Biology", "ebacc_category": "Science"}, actor=ADMIN)
    a = P.create_pupil({"legal_first_name": "Amy", "legal_last_name": "Able",
                        "date_of_birth": "2010-01-15", "gender": "Female", "year_group": 11,
                        "admission_date": "2021-09-01"}, actor=ADMIN)
    b = P.create_pupil({"legal_first_name": "Ben", "legal_last_name": "Bold",
                        "date_of_birth": "2010-03-15", "gender": "Male", "year_group": 11,
                        "admission_date": "2021-09-01"}, actor=ADMIN)
    return a, b


def test_only_the_exams_officer_records(school):
    a, _b = school
    with pytest.raises(G.PermissionDenied):
        G.record(a.pupil_id, {"subject": "ENG", "grade": "7"}, actor=TEACHER)


def test_record_defaults_and_resit_replaces(school):
    a, _b = school
    r = G.record(a.pupil_id, {"subject": "eng", "grade": "7"}, actor=ADMIN)
    assert (r.subject_code, r.grade, r.qualification, r.series) == ("ENG", "7", "GCSE", "June")
    assert r.exam_board == "AQA"           # the subject's board
    assert r.exam_year == G._today().year
    r2 = G.record(a.pupil_id, {"subject": "English Language", "grade": "8"}, actor=ADMIN)
    assert r2.result_id == r.result_id and r2.grade == "8"
    assert [h["action"] for h in G.history(a.pupil_id)] == ["change", "record"]


def test_invalid_values_reported_together(school):
    a, _b = school
    with pytest.raises(G.ValidationError) as e:
        G.record(a.pupil_id, {"subject": "XX", "grade": "10", "exam_year": "1999",
                              "exam_board": "Nope", "series": "May"}, actor=ADMIN)
    assert len(e.value.problems) == 5


def test_record_many_is_all_or_nothing(school):
    a, _b = school
    with pytest.raises(G.ValidationError):
        G.record_many(a.pupil_id, [{"subject": "MATH", "grade": "6"},
                                   {"subject": "MATH", "grade": "5"}], actor=ADMIN)
    assert G.for_pupil(a.pupil_id) == []
    assert G.record_many(a.pupil_id, [{"subject": "MATH", "grade": "6"},
                                      {"subject": "BIO", "grade": "u"}], actor=ADMIN) == 2


def test_summary(school):
    a, _b = school
    G.record_many(a.pupil_id, [{"subject": "ENG", "grade": "5"},
                               {"subject": "MATH", "grade": "4"},
                               {"subject": "BIO", "grade": "U"}], actor=ADMIN)
    s = G.summary(a.pupil_id)
    assert s == {"count": 3, "passes": 2, "strong": 1, "english": "5", "maths": "4"}
    assert G.summary_line(a.pupil_id) == "BIO U, ENG 5, MATH 4"


def test_import_is_all_or_nothing_then_counts(school, tmp_path):
    a, b = school
    bad = tmp_path / "bad.csv"
    with open(bad, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Admission no", "Subject", "Grade"])
        w.writerow([a.admission_no, "MATH", "6"])
        w.writerow(["NOPE", "MATH", "5"])
    with pytest.raises(G.ValidationError):
        G.import_csv(bad, actor=ADMIN)
    assert G.for_pupil(a.pupil_id) == []
    G.record(a.pupil_id, {"subject": "MATH", "grade": "6"}, actor=ADMIN)
    good = tmp_path / "good.csv"
    with open(good, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Admission no", "Subject", "Grade", "Board"])
        w.writerow([a.admission_no, "MATH", "6", ""])       # unchanged
        w.writerow([a.admission_no, "ENG", "7", "AQA"])     # new
        w.writerow([b.admission_no, "Biology", "4", "OCR"])  # new
    assert G.import_csv(good, actor=ADMIN) == {"record": 2, "change": 0, "unchanged": 1}


def test_import_needs_the_columns(school, tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("Pupil,Grade\nA,5\n")
    with pytest.raises(G.ValidationError):
        G.import_csv(f, actor=ADMIN)


def test_export_and_handover_list(school, tmp_path):
    a, _b = school
    G.record(a.pupil_id, {"subject": "BIO", "grade": "9", "exam_board": "ocr"}, actor=ADMIN)
    out = tmp_path / "out.csv"
    assert G.export_csv(out, actor=TEACHER) == 1
    assert "BIO" in out.read_text()
    assert G.handover_list(a.pupil_id) == [{
        "subject": "Biology", "subject_code": "BIO", "qualification": "GCSE", "grade": "9",
        "exam_board": "OCR", "year": G._today().year, "series": "June"}]


def test_delete(school):
    a, _b = school
    r = G.record(a.pupil_id, {"subject": "MATH", "grade": "6"}, actor=ADMIN)
    with pytest.raises(G.PermissionDenied):
        G.delete(r.result_id, actor=TEACHER)
    G.delete(r.result_id, actor=ADMIN)
    assert G.for_pupil(a.pupil_id) == []
    assert G.history(a.pupil_id)[0]["action"] == "delete"
