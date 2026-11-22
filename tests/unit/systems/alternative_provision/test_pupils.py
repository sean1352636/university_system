from __future__ import annotations

from datetime import date

import pytest

from education_system.systems.alternative_provision.core import records as r
from education_system.systems.alternative_provision.modules import learners


def _valid_upn(digits: str = "201234567890") -> str:
    total = sum(int(c) * w for w, c in enumerate(digits, start=2))
    return "ABCDEFGHJKLMNPQRTUVWXYZ"[total % 23] + digits


def test_new_pupil_gets_reference_and_starts_referred(make_pupil):
    pid = make_pupil("Sam", "Jones", postcode="m11aa")
    row = r.get(learners.LEARNERS, pid)
    assert (row["pupil_ref"], row["status"], row["postcode"]) == ("AP000001", "Referred",
                                                                  "M1 1AA")


def test_duplicate_and_age_refused(pupil, make_pupil):
    with pytest.raises(r.ValidationError, match="already on record"):
        make_pupil("Sam", "Jones")
    with pytest.raises(r.ValidationError, match="aged 4 to 19"):
        r.save(learners.LEARNERS, {"first_name": "Old", "last_name": "X", "dob": "1990-01-01",
                                   "gender": "Male", "year_group": "Year 11"})


def test_year_group_must_fit_age(pupil):
    with pytest.raises(r.ValidationError, match="age group"):
        r.save(learners.LEARNERS, {"year_group": "Year 3"}, record_id=pupil)


def test_year_group_for():
    assert learners.year_group_for(date(2012, 9, 1), date(2026, 11, 8)) == "Year 9"
    assert learners.year_group_for(date(2013, 8, 31), date(2026, 11, 8)) == "Year 9"
    assert learners.year_group_for(date(2022, 1, 1), date(2026, 11, 8)) == "Reception"


def test_upn_check_letter(pupil, make_pupil):
    good = _valid_upn()
    assert learners.upn_ok(good) and learners.upn_ok("A20123456789A")
    assert not learners.upn_ok("A201234567890" if good[0] != "A" else "B201234567890")
    r.save(learners.LEARNERS, {"upn": good.lower()}, record_id=pupil)
    assert r.get(learners.LEARNERS, pupil)["upn"] == good
    with pytest.raises(r.ValidationError, match="already on pupil"):
        make_pupil("Ann", "Other", upn=good)


def test_status_moves_and_archive_restore(pupil):
    with pytest.raises(r.ValidationError, match="Referred to Reintegrated"):
        r.save(learners.LEARNERS, {"status": "Reintegrated"}, record_id=pupil)
    r.save(learners.LEARNERS, {"status": "Archived"}, record_id=pupil)
    with pytest.raises(r.ValidationError, match="Referred"):
        r.save(learners.LEARNERS, {"status": "On roll"}, record_id=pupil)
    r.save(learners.LEARNERS, {"status": "Referred"}, record_id=pupil)
    assert r.get(learners.LEARNERS, pupil)["status"] == "Referred"


def test_leaving_refused_with_active_placement(pupil, placement):  # noqa: ARG001
    with pytest.raises(r.ValidationError, match="active placement"):
        r.save(learners.LEARNERS, {"status": "Left"}, record_id=pupil)


def test_one_main_contact_and_no_contact_person(pupil):
    with pytest.raises(r.ValidationError, match="main contact"):
        r.save(learners.CONTACTS, {"learner_id": pupil, "name": "X", "relationship": "Father",
                                   "no_contact": 1, "is_primary": 1, "phone": "0161 123 4567"})
    first = r.save(learners.CONTACTS, {"learner_id": pupil, "name": "Mum",
                                       "relationship": "Mother", "is_primary": 1,
                                       "phone": "0161 123 4567"})
    r.save(learners.CONTACTS, {"learner_id": pupil, "name": "Gran",
                               "relationship": "Grandparent", "is_primary": 1,
                               "phone": "0161 123 4568"})
    assert learners.main_contact(pupil)["name"] == "Gran"
    assert r.get(learners.CONTACTS, first)["is_primary"] == 0
