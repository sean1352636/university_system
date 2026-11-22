from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.alternative_provision.core import dates
from education_system.systems.alternative_provision.core import records as r
from education_system.systems.alternative_provision.modules import (
    attendance,
    behaviour,
    learners,
    placements,
    safeguarding,
)

TODAY = date.today()


def ago(days: int) -> str:
    return (TODAY - timedelta(days=days)).isoformat()


DAY = dates.next_weekday(TODAY - timedelta(days=6))


def test_register_and_rates(pupil, placement, second_pupil):  # noqa: ARG001
    names = [x["learner_id"] for x in attendance.register(DAY, "AM")]
    assert set(names) == {pupil, second_pupil}
    attendance.save_register(DAY, "AM", {pupil: (attendance.MARKS[0], ""),
                                         second_pupil: ("Unauthorised absence (O)", "")},
                             actor="t")
    attendance.save_register(DAY, "AM", {pupil: ("Late (L)", "")}, actor="t")
    attendance.save_register(DAY, "PM", {pupil: ("Attending other school (D)", "")}, actor="t")
    assert attendance.rate(pupil) == 100 and attendance.rate(second_pupil) == 0
    assert len(r.list_records(attendance.ATTENDANCE)) == 3


def test_register_refusals(pupil, placement, make_pupil):  # noqa: ARG001
    with pytest.raises(r.ValidationError, match="reason"):
        attendance.save_register(DAY, "PM", {pupil: ("Illness (I)", "")}, actor="t")
    stranger = make_pupil("Cy", "Ray")
    with pytest.raises(r.ValidationError, match="wasn't on roll"):
        r.save(attendance.ATTENDANCE, {"learner_id": stranger, "session_date": DAY.isoformat(),
                                       "session": "AM", "mark": attendance.MARKS[0]})


def test_reasonable_force_rules(pupil):
    with pytest.raises(r.ValidationError, match="staff involved"):
        r.save(behaviour.INCIDENTS, {"learner_id": pupil, "kind": "Physical assault (adult)",
                                     "description": "x", "reasonable_force": 1})
    inc = r.save(behaviour.INCIDENTS, {"learner_id": pupil, "kind": "Physical assault (adult)",
                                       "description": "x", "reasonable_force": 1,
                                       "force_details": "guided away", "force_staff": "JB"})
    with pytest.raises(r.ValidationError, match="parent or carer was told"):
        r.save(behaviour.INCIDENTS, {"status": "Closed"}, record_id=inc)


def test_suspension_limits(pupil):
    base = {"learner_id": pupil, "reason": "Damage", "decided_by": "Head"}
    r.save(behaviour.SUSPENSIONS, {**base, "days": 40, "start_date": ago(3),
                                   "parent_notified": ago(3)})
    with pytest.raises(r.ValidationError, match="limit is 45"):
        r.save(behaviour.SUSPENSIONS, {**base, "days": 6, "start_date": ago(2),
                                       "parent_notified": ago(2)})
    with pytest.raises(r.ValidationError, match="halves"):
        r.save(behaviour.SUSPENSIONS, {**base, "days": 1.3})
    with pytest.raises(r.ValidationError, match="without delay"):
        r.save(behaviour.SUSPENSIONS, {**base, "days": 1, "start_date": ago(5),
                                       "parent_notified": ago(1)})


def test_permanent_exclusion_takes_pupil_off_roll(pupil, placement):
    r.save(behaviour.SUSPENSIONS, {"learner_id": pupil, "kind": "Permanent exclusion",
                                   "reason": "Damage", "decided_by": "Head"})
    assert r.get(learners.LEARNERS, pupil)["status"] == "Left"
    ended = r.get(placements.PLACEMENTS, placement)
    assert (ended["status"], ended["end_reason"]) == ("Ended", "Permanently excluded")


def test_concern_rules(pupil):
    with pytest.raises(r.ValidationError, match="police referral"):
        r.save(safeguarding.CONCERNS, {"learner_id": pupil, "raised_by": "x",
                                       "category": "Neglect", "details": "x",
                                       "action": "Police"})
    c = r.save(safeguarding.CONCERNS, {"learner_id": pupil, "raised_by": "x",
                                       "category": "Neglect", "details": "x"})
    with pytest.raises(r.ValidationError, match="DSL"):
        r.save(safeguarding.CONCERNS, {"status": "Closed", "outcome": "ok"}, record_id=c)


def test_missing_episode_return_interview(pupil):
    m = r.save(safeguarding.MISSING, {"learner_id": pupil, "missing_on": ago(5),
                                      "returned_on": ago(4), "returned_at": "10:00"})
    assert "OVERDUE" in safeguarding._interview_flag(r.get(safeguarding.MISSING, m))
    with pytest.raises(r.ValidationError, match="before they went missing"):
        r.save(safeguarding.MISSING, {"returned_on": ago(6)}, record_id=m)
