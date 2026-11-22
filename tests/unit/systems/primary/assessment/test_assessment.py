"""Assessment records (domain.assessment.assessment)."""

from __future__ import annotations

import pytest

from education_system.systems.primary.domain.assessment import assessment as AS
from education_system.systems.primary.domain.learners.pupils import pupils as P

_n = 0


def _pupil(year="3", first=None):
    global _n
    _n += 1
    return P.create_pupil({"first_name": first or f"Pupil{_n}", "last_name": f"Test{_n:03d}",
                           "year_group": year, "date_of_birth": "2017-03-01"})


def _rec(pupil, **extra):
    data = {"pupil_id": pupil.pupil_id, "academic_year": "2025-26", "term": "Autumn",
            "subject": "Maths", "grade": "EXS"}
    data.update(extra)
    return AS.create(data)


# ── create / get ─────────────────────────────────────────────────────

def test_create_stores_every_field_and_get_reads_it_back():
    p = _pupil()
    rec = _rec(p, score="72.5", assessed_on="2025-12-01", comment="  Solid  ")
    got = AS.get(rec.assessment_id)
    assert got == rec
    assert (got.pupil_id, got.academic_year, got.term, got.subject, got.grade) == (
        p.pupil_id, "2025-26", "Autumn", "Maths", "EXS")
    assert got.score == 72.5
    assert got.assessed_on == "2025-12-01"
    assert got.comment == "Solid"


def test_create_normalises_term_and_grade_case():
    rec = _rec(_pupil(), term="  spring ", grade="gds")
    assert rec.term == "Spring" and rec.grade == "GDS"


def test_blank_optional_fields_become_none():
    rec = _rec(_pupil(), score="", assessed_on="  ", comment="   ")
    assert rec.score is None and rec.assessed_on is None and rec.comment is None


def test_get_unknown_id_is_none():
    assert AS.get(9999) is None


def test_academic_year_accepts_single_and_long_forms():
    p = _pupil()
    assert _rec(p, academic_year="2025").academic_year == "2025"
    assert _rec(p, academic_year="2025-2026").academic_year == "2025-2026"


def test_score_bounds_are_inclusive():
    p = _pupil()
    assert _rec(p, score=0).score == 0.0
    assert _rec(p, subject="Reading", score=100).score == 100.0


# ── validation ───────────────────────────────────────────────────────

@pytest.mark.parametrize("field, value, message", [
    ("pupil_id", "", "Pupil ID is required"),
    ("academic_year", "", "Academic year is required"),
    ("academic_year", "25-26", "Academic year must look like"),
    ("academic_year", "2025/26", "Academic year must look like"),
    ("term", "", "Term is required"),
    ("term", "Winter", "Term must be one of Autumn, Spring, Summer"),
    ("subject", "  ", "Subject is required"),
    ("subject", "x" * 65, "64 characters or fewer"),
    ("grade", "", "Grade is required"),
    ("grade", "A*", "Grade must be one of BLW, WTS, EXS, GDS"),
    ("score", "lots", "Score must be a number"),
    ("score", -0.5, "Score must be between 0 and 100"),
    ("score", 100.1, "Score must be between 0 and 100"),
    ("assessed_on", "01/12/2025", "Assessed-on date must be YYYY-MM-DD"),
])
def test_create_refuses_invalid_field(field, value, message):
    p = _pupil()
    with pytest.raises(P.ValidationError, match=message):
        _rec(p, **{field: value})
    assert AS.list_records() == []


def test_subject_of_exactly_64_characters_is_allowed():
    assert len(_rec(_pupil(), subject="s" * 64).subject) == 64


def test_create_refuses_unknown_pupil():
    with pytest.raises(P.ValidationError, match="No pupil with id P9999999"):
        AS.create({"pupil_id": "P9999999", "academic_year": "2025-26", "term": "Autumn",
                   "subject": "Maths", "grade": "EXS"})


def test_one_record_per_pupil_year_term_subject():
    p = _pupil()
    first = _rec(p)
    with pytest.raises(P.ValidationError, match=f"#{first.assessment_id}"):
        _rec(p, grade="GDS")
    # A different term, subject or year is a separate record.
    _rec(p, term="Spring")
    _rec(p, subject="Reading")
    _rec(p, academic_year="2026-27")
    assert len(AS.list_for_pupil(p.pupil_id)) == 4


# ── update / delete ──────────────────────────────────────────────────

def test_update_changes_only_given_fields():
    p = _pupil()
    rec = _rec(p, score=50, comment="first")
    up = AS.update(rec.assessment_id, {"grade": "gds", "score": 91})
    assert up.grade == "GDS" and up.score == 91.0
    assert up.comment == "first" and up.subject == "Maths" and up.term == "Autumn"
    assert AS.get(rec.assessment_id).grade == "GDS"


def test_update_can_clear_the_score():
    rec = _rec(_pupil(), score=40)
    assert AS.update(rec.assessment_id, {"score": ""}).score is None


def test_update_unknown_record_is_refused():
    with pytest.raises(P.ValidationError, match="No assessment record #42"):
        AS.update(42, {"grade": "EXS"})


def test_update_validates_like_create():
    rec = _rec(_pupil())
    with pytest.raises(P.ValidationError, match="Grade must be one of"):
        AS.update(rec.assessment_id, {"grade": "Z"})
    with pytest.raises(P.ValidationError, match="No pupil with id"):
        AS.update(rec.assessment_id, {"pupil_id": "P0000000"})
    assert AS.get(rec.assessment_id).grade == "EXS"


def test_update_cannot_collide_with_another_record():
    p = _pupil()
    _rec(p, term="Autumn")
    spring = _rec(p, term="Spring")
    with pytest.raises(P.ValidationError, match="Another assessment"):
        AS.update(spring.assessment_id, {"term": "Autumn"})
    # Saving a record onto its own key is fine.
    assert AS.update(spring.assessment_id, {"term": "Spring", "grade": "WTS"}).grade == "WTS"


def test_delete_removes_once():
    rec = _rec(_pupil())
    assert AS.delete(rec.assessment_id) is True
    assert AS.get(rec.assessment_id) is None
    assert AS.delete(rec.assessment_id) is False


# ── listing ──────────────────────────────────────────────────────────

def _seed():
    y3, y5 = _pupil("3"), _pupil("5")
    _rec(y3, term="Autumn", subject="Maths", grade="EXS", score=60)
    _rec(y3, term="Spring", subject="Maths", grade="GDS", score=90)
    _rec(y3, term="Autumn", subject="Reading", grade="WTS", score=30)
    _rec(y5, term="Autumn", subject="Maths", grade="BLW")
    _rec(y5, academic_year="2024-25", term="Summer", subject="Writing", grade="EXS", score=70)
    return y3, y5


def test_empty_database_lists_and_summarises_nothing():
    assert AS.list_records() == []
    assert AS.known_years() == [] and AS.known_subjects() == []
    s = AS.grade_summary()
    assert s == {"total": 0, "by_grade": {"BLW": 0, "WTS": 0, "EXS": 0, "GDS": 0},
                 "at_or_above_exs": 0, "at_or_above_exs_pct": 0.0, "average_score": None}


def test_list_records_filters():
    y3, y5 = _seed()
    assert len(AS.list_records()) == 5
    assert len(AS.list_records(academic_year="2025-26")) == 4
    assert {r.subject for r, _ in AS.list_records(term="Autumn")} == {"Maths", "Reading"}
    assert len(AS.list_records(subject="Maths")) == 3
    assert [r.grade for r, _ in AS.list_records(grade="GDS")] == ["GDS"]
    assert {r.pupil_id for r, _ in AS.list_records(pupil_id=y5.pupil_id)} == {y5.pupil_id}
    rows = AS.list_records(year_group="3")
    assert len(rows) == 3 and all(p.pupil_id == y3.pupil_id for _, p in rows)
    assert AS.list_records(year_group="6") == []


def test_list_records_pairs_each_record_with_its_pupil():
    y3, _ = _seed()
    for rec, pupil in AS.list_records(pupil_id=y3.pupil_id):
        assert pupil.pupil_id == rec.pupil_id and pupil.year_group == "3"


def test_list_records_orders_newest_year_first_then_term_subject():
    _seed()
    keys = [(r.academic_year, r.term, r.subject) for r, _ in AS.list_records()]
    assert keys[0][0] == "2025-26" and keys[-1] == ("2024-25", "Summer", "Writing")
    assert keys[:4] == sorted(keys[:4], key=lambda k: (k[1], k[2]))


@pytest.mark.parametrize("kwargs, message", [
    ({"term": "Winter"}, "Term filter"),
    ({"grade": "A"}, "Grade filter"),
    ({"year_group": "7"}, "Year filter"),
])
def test_list_records_refuses_bad_filters(kwargs, message):
    with pytest.raises(P.ValidationError, match=message):
        AS.list_records(**kwargs)


def test_list_for_pupil_and_unknown_pupil():
    y3, _ = _seed()
    rows = AS.list_for_pupil(y3.pupil_id)
    assert [(r.term, r.subject) for r in rows] == [
        ("Autumn", "Maths"), ("Autumn", "Reading"), ("Spring", "Maths")]
    assert AS.list_for_pupil(_pupil().pupil_id) == []
    with pytest.raises(P.ValidationError, match="No pupil"):
        AS.list_for_pupil("P0000000")


def test_known_years_and_subjects():
    _seed()
    assert AS.known_years() == ["2025-26", "2024-25"]
    assert AS.known_subjects() == ["Maths", "Reading", "Writing"]


def test_known_subjects_sorts_case_insensitively():
    p = _pupil()
    _rec(p, subject="art")
    _rec(p, subject="Maths")
    _rec(p, subject="DT")
    assert AS.known_subjects() == ["art", "DT", "Maths"]


# ── grade summary ────────────────────────────────────────────────────

def test_grade_summary_counts_and_averages():
    _seed()
    s = AS.grade_summary(academic_year="2025-26")
    assert s["total"] == 4
    assert s["by_grade"] == {"BLW": 1, "WTS": 1, "EXS": 1, "GDS": 1}
    assert s["at_or_above_exs"] == 2
    assert s["at_or_above_exs_pct"] == 50.0
    # Scores 60, 90, 30 (the BLW row has none): (60 + 90 + 30) / 3 = 60.
    assert s["average_score"] == pytest.approx(60.0)


def test_grade_summary_filters_by_term_and_subject():
    _seed()
    s = AS.grade_summary(academic_year="2025-26", term="Autumn", subject="Maths")
    assert s["total"] == 2 and s["at_or_above_exs"] == 1
    assert s["average_score"] == 60.0
    whole = AS.grade_summary()
    assert whole["total"] == 5
    assert whole["at_or_above_exs_pct"] == pytest.approx(60.0)   # 3 of 5


def test_grade_rank_orders_grades():
    assert sorted(AS.GRADES, key=AS.GRADE_RANK.get) == ["BLW", "WTS", "EXS", "GDS"]
    assert set(AS.GRADE_LABELS) == set(AS.GRADES)
