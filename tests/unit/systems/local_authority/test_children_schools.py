"""Children, parents/carers and the schools register."""

from __future__ import annotations

from datetime import date

import pytest

from education_system.systems.local_authority.core import records as r
from education_system.systems.local_authority.modules import children, schools


def test_urn_and_pan_rules():
    with pytest.raises(r.ValidationError, match="six digits"):
        r.save(schools.SCHOOLS, {"name": "X", "urn": "12", "phase": "Primary"})
    with pytest.raises(r.ValidationError, match="capacity"):
        r.save(schools.SCHOOLS, {"name": "X", "urn": "100009", "phase": "Primary", "pan": 60,
                                 "capacity": 30})


def test_admission_authority_and_surplus(world):
    oak = r.get(schools.SCHOOLS, world.oak)
    assert oak["la_admits"] == 1
    assert r.get(schools.SCHOOLS, world.elm)["la_admits"] == 0   # academy
    assert schools.surplus(oak) == "10 (5%)"


def test_reference_year_group_and_duplicates(make_child, world):
    cid = make_child(school_id=world.oak)
    row = r.get(children.CHILDREN, cid)
    assert row["child_ref"] == "LA000001"
    assert children.year_group(date(2015, 9, 1), date(2020, 9, 1)) == "Reception"
    assert children.year_group(date(2015, 8, 31), date(2020, 9, 1)) == "Year 1"
    with pytest.raises(r.ValidationError, match="same name and date of birth"):
        make_child(school_id=world.oak)


def test_at_school_needs_a_school(make_child):
    with pytest.raises(r.ValidationError, match="choose the school"):
        make_child(education="At school")


def test_upn_check_letter(make_child, world):
    valid = next(l + "123456789012" for l in "ABCDEFGHJKLMNPQRTUVWXYZ"
                 if children.upn_ok(l + "123456789012"))
    wrong = next(l + "123456789012" for l in "ABCDEFGHJKLMNPQRTUVWXYZ"
                 if not children.upn_ok(l + "123456789012"))
    with pytest.raises(r.ValidationError, match="UPN"):
        make_child(school_id=world.oak, upn=wrong)
    make_child(school_id=world.oak, upn=valid)


def test_age_limit(make_child):
    with pytest.raises(r.ValidationError, match="25"):
        make_child(age=30)


def test_one_main_contact(make_child, world):
    cid = make_child(school_id=world.oak)
    r.save(children.CONTACTS, {"learner_id": cid, "name": "Mum", "relationship": "Mother",
                               "phone": "0161 111 2222", "is_primary": 1})
    r.save(children.CONTACTS, {"learner_id": cid, "name": "Dad", "relationship": "Father",
                               "phone": "0161 111 2223", "is_primary": 1})
    assert children.main_contact(cid)["name"] == "Dad"
    with pytest.raises(r.ValidationError, match="released"):
        r.save(children.CONTACTS, {"learner_id": cid, "name": "X", "relationship": "Other",
                                   "phone": "0161 111 2224", "is_primary": 1,
                                   "no_contact": 1})
