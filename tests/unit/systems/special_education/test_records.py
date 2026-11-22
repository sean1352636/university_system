"""The shared record layer: defaults, normalising, refusals and history."""

from __future__ import annotations

import pytest

from education_system.systems.special_education.core import records as r
from education_system.systems.special_education.modules import learners, people, provision


def test_new_record_takes_defaults(learner):
    row = r.get(learners.LEARNERS, learner)
    assert row["sen_status"] == "SEN Support"
    assert row["status"] == "Active"


def test_uk_dates_and_money_are_normalised(learner):
    pid = r.save(provision.PROVISION, {"learner_id": learner, "name": "PT",
                                       "provision_type": "1:1 support",
                                       "start_date": "01/09/2026", "cost_per_week": "£1,250.5"})
    row = r.get(provision.PROVISION, pid)
    assert row["start_date"] == "2026-09-01"
    assert row["cost_per_week"] == 1250.5
    assert row["learner_name"] == "Amy Smith"


@pytest.mark.parametrize("values, message", [
    ({"first_name": "", "last_name": "X", "dob": "2015-01-01"}, "First name is required"),
    ({"first_name": "A", "last_name": "X", "dob": "31/02/2015"}, "not a date"),
    ({"first_name": "A", "last_name": "X", "dob": "2015-01-01", "sen_status": "Bogus"},
     "must be one of"),
])
def test_bad_values_are_refused(values, message):
    with pytest.raises(r.ValidationError, match=message):
        r.save(learners.LEARNERS, values)


def test_negative_money_refused(learner):
    with pytest.raises(r.ValidationError, match="negative"):
        r.save(provision.PROVISION, {"learner_id": learner, "name": "PT",
                                     "provision_type": "Therapy", "cost_per_week": "-1"})


def test_learner_with_records_cannot_be_deleted(learner):
    r.save(provision.PROVISION, {"learner_id": learner, "name": "PT",
                                 "provision_type": "Therapy"})
    with pytest.raises(r.ValidationError, match="Archive the learner"):
        r.delete(learners.LEARNERS, learner)
    assert r.get(learners.LEARNERS, learner) is not None


def test_referenced_professional_cannot_be_deleted(learner):
    pro = r.save(people.PROFESSIONALS, {"name": "Dr X", "role": "Paediatrician"})
    r.save(people.INVOLVEMENT, {"learner_id": learner, "professional_id": pro})
    with pytest.raises(r.ValidationError):
        r.delete(people.PROFESSIONALS, pro)


def test_history_is_the_learner_chronology(learner):
    r.save(learners.LEARNERS, {"key_worker": "Ms Brown"}, record_id=learner, actor="senco")
    rows = r.history(learner_id=learner)
    assert [x["action"] for x in rows] == ["updated", "added"]
    assert "Key worker" in rows[0]["summary"] and rows[0]["actor"] == "senco"


def test_search_and_filters(learner):
    r.save(learners.LEARNERS, {"first_name": "Ben", "last_name": "Jones", "dob": "2012-01-01",
                               "sen_status": "Monitoring"})
    assert [x["first_name"] for x in r.list_records(learners.LEARNERS, search="jon")] == ["Ben"]
    assert len(r.list_records(learners.LEARNERS, equals={"sen_status": "SEN Support"})) == 1
