from __future__ import annotations

from datetime import date, timedelta

import pytest

from education_system.systems.alternative_provision.core import dates
from education_system.systems.alternative_provision.core import records as r
from education_system.systems.alternative_provision.modules import learners, placements, referrals

TODAY = date.today()


def ago(days: int) -> str:
    return (TODAY - timedelta(days=days)).isoformat()



def test_school_day_skips_weekends():
    monday = date(2026, 11, 2)
    assert dates.school_day(monday, 6) == date(2026, 11, 9)
    assert dates.school_day(date(2026, 11, 7), 1) == monday + timedelta(days=7)  # Sat -> Mon
    assert dates.weekdays_between(monday, date(2026, 11, 15)) == 10


def test_exclusion_referral_tracks_sixth_day(pupil, make_provider):
    with pytest.raises(r.ValidationError, match="sixth school day"):
        r.save(referrals.REFERRALS, {"learner_id": pupil, "referred_by": "Oak High",
                                     "reason": "Permanent exclusion"})
    ref = r.save(referrals.REFERRALS, {"learner_id": pupil, "referred_by": "Oak High",
                                       "reason": "Permanent exclusion",
                                       "excluded_from": ago(20), "received": ago(19)})
    assert "OVERDUE" in referrals.day6_flag(r.get(referrals.REFERRALS, ref))
    r.save(placements.PLACEMENTS, {"learner_id": pupil, "provider_id": make_provider(),
                                   "hours_per_week": 25, "start_date": ago(15),
                                   "status": "Active"})
    assert referrals.day6_flag(r.get(referrals.REFERRALS, ref)).endswith("met")


def test_referral_decisions(pupil):
    ref = r.save(referrals.REFERRALS, {"learner_id": pupil, "referred_by": "LA",
                                       "reason": "Managed move"})
    with pytest.raises(r.ValidationError, match="open referral"):
        r.save(referrals.REFERRALS, {"learner_id": pupil, "referred_by": "x",
                                     "reason": "Other"})
    with pytest.raises(r.ValidationError, match="reason for declining"):
        r.save(referrals.REFERRALS, {"status": "Declined"}, record_id=ref)
    r.save(referrals.REFERRALS, {"status": "Accepted"}, record_id=ref)
    assert r.get(referrals.REFERRALS, ref)["decision_date"] == TODAY.isoformat()
    with pytest.raises(r.ValidationError, match="An accepted referral"):
        r.save(referrals.REFERRALS, {"status": "New"}, record_id=ref)


def test_risk_assessment_overall_and_supersede(pupil):
    first = r.save(referrals.RISK_ASSESSMENTS, {"learner_id": pupil, "absconding": "Medium"})
    assert r.get(referrals.RISK_ASSESSMENTS, first)["overall"] == "Medium"
    with pytest.raises(r.ValidationError, match="control measures"):
        r.save(referrals.RISK_ASSESSMENTS, {"learner_id": pupil, "risk_to_staff": "High"})
    r.save(referrals.RISK_ASSESSMENTS, {"learner_id": pupil, "risk_to_staff": "High",
                                        "controls": "two staff"})
    assert r.get(referrals.RISK_ASSESSMENTS, first)["status"] == "Superseded"
    assert referrals.current_risk(pupil)["overall"] == "High"


def test_provider_registration_and_unsafe_providers(pupil, make_provider):
    tutor = make_provider("Tutor Co", "Tuition service")
    bad = make_provider("Bad AP", "Unregistered AP provider", ofsted="Inadequate")
    assert r.get(placements.PROVIDERS, tutor)["registered"] == 0
    with pytest.raises(r.ValidationError, match="Inadequate"):
        r.save(placements.PLACEMENTS, {"learner_id": pupil, "provider_id": bad,
                                       "hours_per_week": 10, "part_time_reason": "x"})
    with pytest.raises(r.ValidationError, match="not a registered school"):
        r.save(placements.PLACEMENTS, {"learner_id": pupil, "provider_id": tutor,
                                       "hours_per_week": 20, "part_time_reason": "x"})


def test_part_time_timetable_rules(pupil, make_provider):
    pru = make_provider()
    with pytest.raises(r.ValidationError, match="part-time timetable"):
        r.save(placements.PLACEMENTS, {"learner_id": pupil, "provider_id": pru,
                                       "hours_per_week": 15})
    with pytest.raises(r.ValidationError, match="within 6 weeks"):
        r.save(placements.PLACEMENTS, {
            "learner_id": pupil, "provider_id": pru, "hours_per_week": 15,
            "part_time_reason": "x", "start_date": ago(14),
            "part_time_review": (TODAY + timedelta(days=60)).isoformat()})


def test_active_placement_puts_pupil_on_roll_from_its_start(pupil, placement):
    row = r.get(placements.PLACEMENTS, placement)
    assert row["daily_rate"] == 120 and row["part_time_review"] and row["next_review"]
    who = r.get(learners.LEARNERS, pupil)
    assert who["status"] == "On roll" and who["start_date"] == ago(14)


def test_hours_cap_capacity_and_ending(pupil, placement, make_provider, make_pupil):
    tutor = make_provider("Tutor Co", "Tuition service")
    with pytest.raises(r.ValidationError, match="32.5"):
        r.save(placements.PLACEMENTS, {"learner_id": pupil, "provider_id": tutor,
                                       "hours_per_week": 17.6, "part_time_reason": "x",
                                       "status": "Active", "start_date": ago(1)})
    with pytest.raises(r.ValidationError, match="reason the placement ended"):
        r.save(placements.PLACEMENTS, {"status": "Ended"}, record_id=placement)
    small = make_provider("Small AP", "AP academy / free school", capacity=1)
    other = make_pupil("Cy", "Ray")
    r.save(placements.PLACEMENTS, {"learner_id": other, "provider_id": small,
                                   "hours_per_week": 25, "status": "Active",
                                   "start_date": ago(1)})
    third = make_pupil("Di", "Fox")
    with pytest.raises(r.ValidationError, match="full"):
        r.save(placements.PLACEMENTS, {"learner_id": third, "provider_id": small,
                                       "hours_per_week": 25, "status": "Active",
                                       "start_date": ago(1)})
    with pytest.raises(r.ValidationError, match="1 pupil is placed"):
        r.save(placements.PROVIDERS, {"capacity": 0}, record_id=small)


def test_review_sets_next_review(placement):
    rv = r.save(placements.PLACEMENT_REVIEWS, {"placement_id": placement, "progress": "Some"})
    nxt = r.get(placements.PLACEMENT_REVIEWS, rv)["next_review"]
    assert nxt == dates.add_weeks(TODAY, 6).isoformat()
    assert r.get(placements.PLACEMENTS, placement)["next_review"] == nxt
