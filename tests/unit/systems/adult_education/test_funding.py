from __future__ import annotations

from datetime import date

import pytest

from education_system.systems.adult_education.core import records as r
from education_system.systems.adult_education.modules import funding, learners

YEAR = date(2026, 8, 1)
UK = funding.RESIDENCY[0]


def _eval(**kw):
    base = dict(dob=date(1990, 1, 1), year_start=YEAR, residency=UK, employment="Employed",
                course_type="General course", course_level="Level 2")
    return funding.evaluate(**{**base, **kw}).outcome


def test_unemployed_adult_fully_funded():
    assert _eval(dob=date(2000, 1, 1), employment="Unemployed (looking for work)") == funding.FULLY


def test_under_19_not_adult_skills_funded():
    assert _eval(dob=date(2010, 1, 1)) == funding.NONE


def test_level_4_needs_a_loan():
    assert _eval(course_level="Level 4") == funding.LOAN


def test_assessment_fills_gcse_from_prior_and_cannot_be_edited(learner):
    r.save(learners.PRIOR, {"learner_id": learner, "title": "GCSE English",
                            "level": "Level 2", "grade": "5"})
    aid = r.save(funding.ELIGIBILITY, {"learner_id": learner, "course_type": "English or maths",
                                       "course_level": "Level 2", "residency": UK,
                                       "employment": "Employed", "annual_income": 30000})
    row = r.get(funding.ELIGIBILITY, aid)
    assert row["outcome"] == funding.FULLY and row["gcse_english"] == 1
    assert funding.latest_outcome(learner) == funding.FULLY
    with pytest.raises(r.ValidationError, match="can't be edited"):
        r.save(funding.ELIGIBILITY, {"course_level": "Level 3"}, record_id=aid)


def test_esol_capped_at_level_2(learner):
    with pytest.raises(r.ValidationError, match="ESOL"):
        r.save(funding.ELIGIBILITY, {"learner_id": learner, "course_type": "ESOL",
                                     "course_level": "Level 3", "residency": UK,
                                     "employment": "Employed"})
