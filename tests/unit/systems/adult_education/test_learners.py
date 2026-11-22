from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.adult_education.core import records as r
from education_system.systems.adult_education.modules import learners


def test_new_learner_gets_reference_and_tidied_details():
    lid = r.save(learners.LEARNERS, {"first_name": "Jo", "last_name": "Bloggs",
                                     "dob": "12/03/1980", "gender": "Female",
                                     "postcode": "sw1a1aa", "email": "Jo@x.com"})
    row = r.get(learners.LEARNERS, lid)
    assert row["learner_ref"] == "AE000001"
    assert row["postcode"] == "SW1A 1AA"
    assert row["email"] == "jo@x.com"
    assert row["status"] == "Enquiry"


def test_duplicate_name_and_birthday_refused(learner):
    with pytest.raises(r.ValidationError, match="already on record"):
        r.save(learners.LEARNERS, {"first_name": "Jo", "last_name": "Bloggs",
                                   "dob": "1980-03-12", "gender": "Male"})


def test_under_16_refused():
    dob = (date.today() - timedelta(days=365 * 10)).isoformat()
    with pytest.raises(r.ValidationError, match="16 and over"):
        r.save(learners.LEARNERS, {"first_name": "Kid", "last_name": "X", "dob": dob,
                                   "gender": "Male"})


@pytest.mark.parametrize("values", [{"uln": "1234567890"}, {"ni_number": "BG123456A"}])
def test_bad_uln_and_ni_refused(learner, values):
    with pytest.raises(r.ValidationError):
        r.save(learners.LEARNERS, values, record_id=learner)


def test_status_moves_are_checked(learner):
    with pytest.raises(r.ValidationError, match="Enquiry to Completed"):
        r.save(learners.LEARNERS, {"status": "Completed"}, record_id=learner)


def test_archive_restores_to_previous_status(learner):
    r.save(learners.LEARNERS, {"status": "Archived"}, record_id=learner)
    assert learners.learner_options() == []
    assert learners.learner_options(include_archived=True)
    with pytest.raises(r.ValidationError, match="Enquiry"):
        r.save(learners.LEARNERS, {"status": "Active"}, record_id=learner)
    r.save(learners.LEARNERS, {"status": "Enquiry"}, record_id=learner)
    assert r.get(learners.LEARNERS, learner)["status"] == "Enquiry"


def test_only_one_main_contact(learner):
    rel = learners.RELATIONSHIPS[0]
    first = r.save(learners.CONTACTS, {"learner_id": learner, "name": "A", "relationship": rel,
                                       "phone": "07700900000", "is_primary": 1})
    second = r.save(learners.CONTACTS, {"learner_id": learner, "name": "B", "relationship": rel,
                                        "phone": "07700900001", "is_primary": 1})
    assert r.get(learners.CONTACTS, second)["is_primary"] == 1
    assert r.get(learners.CONTACTS, first)["is_primary"] == 0


def test_prior_qualifications_summary(learner):
    r.save(learners.PRIOR, {"learner_id": learner, "title": "GCSE English",
                            "level": "Level 2", "grade": "5"})
    summary = learners.prior_summary(learner)
    assert summary == {"highest_level": "Level 2", "gcse_english": True, "gcse_maths": False}


def test_uln_check_digit():
    assert not learners.uln_check_digit_ok("1234567890")
    assert not learners.uln_check_digit_ok("abc")
