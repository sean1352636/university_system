from __future__ import annotations

import pytest

from education_system.systems.special_education.core import records as r
from education_system.systems.special_education.modules import learners


def test_upn_is_upper_cased_and_unique(learner):
    r.save(learners.LEARNERS, {"upn": "a123456789012"}, record_id=learner)
    assert r.get(learners.LEARNERS, learner)["upn"] == "A123456789012"
    with pytest.raises(r.ValidationError, match="already belongs to Amy Smith"):
        r.save(learners.LEARNERS, {"first_name": "B", "last_name": "C", "dob": "2014-01-01",
                                   "upn": "A123456789012"})


def test_bad_upn_refused(learner):
    with pytest.raises(r.ValidationError, match="13 characters"):
        r.save(learners.LEARNERS, {"upn": "12345"}, record_id=learner)


def test_future_dob_refused():
    with pytest.raises(r.ValidationError, match="future"):
        r.save(learners.LEARNERS, {"first_name": "A", "last_name": "B", "dob": "2099-01-01"})


def test_contact_needs_phone_or_email(learner):
    with pytest.raises(r.ValidationError, match="phone number or an e-mail"):
        r.save(learners.CONTACTS, {"learner_id": learner, "name": "Mum",
                                   "relationship": "Mother"})
    with pytest.raises(r.ValidationError, match="e-mail address"):
        r.save(learners.CONTACTS, {"learner_id": learner, "name": "Mum",
                                   "relationship": "Mother", "email": "nope"})
