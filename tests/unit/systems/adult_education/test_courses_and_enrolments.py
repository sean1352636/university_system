from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.adult_education.core import records as r
from education_system.systems.adult_education.modules import courses, enrolments, learners

LAST_WEEK = date.today() - timedelta(days=7)


def test_course_code_upper_cased(course):
    assert r.get(courses.COURSES, course)["code"] == "ENG1"


def test_class_times_and_delivery(make_class):
    cl = make_class()
    assert courses.delivery(r.get(courses.CLASSES, cl)) == "Evening"
    with pytest.raises(r.ValidationError, match="HH:MM"):
        r.save(courses.CLASSES, {"start_time": "7pm"}, record_id=cl)
    with pytest.raises(r.ValidationError):
        r.save(courses.CLASSES, {"capacity": 0}, record_id=cl)


def test_enrolment_activates_learner_and_full_class_waitlists(learner, second_learner,
                                                              make_class):
    cl = make_class(capacity=1)
    en = r.save(enrolments.ENROLMENTS, {"learner_id": learner, "class_id": cl})
    assert r.get(enrolments.ENROLMENTS, en)["status"] == "Enrolled"
    assert r.get(learners.LEARNERS, learner)["status"] == "Active"
    en2 = r.save(enrolments.ENROLMENTS, {"learner_id": second_learner, "class_id": cl})
    assert r.get(enrolments.ENROLMENTS, en2)["status"] == "Waiting list"
    with pytest.raises(r.ValidationError, match="already on this class"):
        r.save(enrolments.ENROLMENTS, {"learner_id": learner, "class_id": cl})
    with pytest.raises(r.ValidationError, match="reason"):
        r.save(enrolments.ENROLMENTS, {"status": "Withdrawn"}, record_id=en)
    r.save(enrolments.ENROLMENTS, {"status": "Withdrawn", "withdrawal_reason": "moved"},
           record_id=en)
    assert r.get(enrolments.ENROLMENTS, en2)["status"] == "Enrolled"
    assert r.get(learners.LEARNERS, second_learner)["status"] == "Active"


def test_refund_cannot_exceed_paid(learner, make_class):
    en = r.save(enrolments.ENROLMENTS, {"learner_id": learner, "class_id": make_class(),
                                        "fee_due": 200})
    r.save(enrolments.PAYMENTS, {"enrolment_id": en, "amount": 50})
    with pytest.raises(r.ValidationError, match="refund"):
        r.save(enrolments.PAYMENTS, {"enrolment_id": en, "amount": 80, "kind": "Refund"})
    assert enrolments.paid(en) == 50


def test_register_save_and_update(learner, second_learner, make_class):
    cl = make_class(capacity=1)
    r.save(enrolments.ENROLMENTS, {"learner_id": learner, "class_id": cl})
    r.save(enrolments.ENROLMENTS, {"learner_id": second_learner, "class_id": cl})  # waiting
    assert [x["learner_id"] for x in enrolments.register(cl, LAST_WEEK)] == [learner]
    assert enrolments.save_register(cl, LAST_WEEK, {learner: "Present"}, actor="t") == 1
    enrolments.save_register(cl, LAST_WEEK, {learner: "Late"}, actor="t")
    marks = r.list_records(enrolments.ATTENDANCE)
    assert [(m["learner_id"], m["mark"]) for m in marks] == [(learner, "Late")]
    with pytest.raises(r.ValidationError, match="isn't enrolled"):
        r.save(enrolments.ATTENDANCE, {"class_id": cl, "learner_id": second_learner,
                                       "session_date": LAST_WEEK.isoformat(),
                                       "mark": "Present"})
