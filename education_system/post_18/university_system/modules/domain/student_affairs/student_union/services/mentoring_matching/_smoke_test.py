"""Standalone smoke test for MentoringMatchingService.

Run directly:
    /home/seancatchpole989/venv/bin/python -m education_system.post_18.university_system.modules.domain.student_affairs.student_union.services.mentoring_matching._smoke_test
"""
import os
import sys
import tempfile

from education_system.post_18.university_system.modules.domain.student_affairs.student_union.services.mentoring_matching import (
    MentoringMatchingService,
    MentoringMatchingError,
)


def run_basic() -> None:
    db = tempfile.mktemp(suffix=".db")
    svc = MentoringMatchingService(db)
    svc.upsert_mentee_preferences(
        100,
        course="Computer Science",
        learning_goals_csv="python, algorithms, debugging",
        preferred_languages_csv="english, spanish",
        availability_csv="mon_am, wed_pm, fri_pm",
        preferred_year_min=2,
    )
    svc.upsert_mentor_profile(
        1, year_of_study=3, course="Computer Science",
        strengths_csv="python, algorithms, debugging",
        availability_csv="mon_am, wed_pm",
        languages_csv="english, spanish", max_mentees=5, bio="3rd-yr CS",
    )
    svc.upsert_mentor_profile(
        2, year_of_study=2, course="Mathematics",
        strengths_csv="algorithms", availability_csv="mon_am",
        languages_csv="english", max_mentees=5,
    )
    svc.upsert_mentor_profile(
        3, year_of_study=4, course="History",
        strengths_csv="essay-writing", availability_csv="sat_am",
        languages_csv="french", max_mentees=5,
    )

    recs = svc.recommend_mentors(100, top_n=3)
    print("Recs:")
    for r in recs:
        print(" ", r)
    assert len(recs) == 3
    assert recs[0]["mentor_id"] == 1, recs[0]
    assert recs[0]["reasons"], "reasons must be populated"
    # 30 (course) + 40 (avail cap) + 30 (lang cap) + 30 (strength cap) = 130
    assert recs[0]["score"] == 130, recs[0]["score"]

    svc.record_outcome(555, 4, 8, 80, 5, 1, "Great")
    s = svc.outcomes_summary()
    print("Summary:", s)
    assert s["count"] == 1
    assert s["avg_confidence_delta"] == 4.0
    assert s["pct_would_recommend"] == 100.0
    assert s["avg_satisfaction"] == 5.0
    assert svc.get_outcome(555)["confidence_post"] == 8
    os.unlink(db)
    print("BASIC OK")


def run_capacity_cap() -> None:
    db = tempfile.mktemp(suffix=".db")
    counter = lambda mid: {1: 5, 2: 0}.get(mid, 0)
    svc = MentoringMatchingService(db, count_active_mentees=counter)
    svc.upsert_mentee_preferences(
        7, course="Computer Science",
        learning_goals_csv="python", preferred_languages_csv="english",
        availability_csv="mon_am",
    )
    svc.upsert_mentor_profile(
        1, course="Computer Science", strengths_csv="python",
        languages_csv="english", availability_csv="mon_am", max_mentees=5,
    )
    svc.upsert_mentor_profile(
        2, course="Computer Science", strengths_csv="python",
        languages_csv="english", availability_csv="mon_am", max_mentees=5,
    )
    recs = svc.recommend_mentors(7, top_n=2)
    by = {r["mentor_id"]: r for r in recs}
    print("Capacity recs:")
    for r in recs:
        print(" ", r)
    # base 30+20+15+10 = 75; mentor 1 -> 25; mentor 2 -> 75
    assert by[1]["score"] == 25, by[1]
    assert by[2]["score"] == 75, by[2]
    assert any("capacity" in t for t in by[1]["reasons"]), by[1]["reasons"]

    svc.accept_recommendation(by[2]["recommendation_id"])
    try:
        svc.accept_recommendation(999999)
    except MentoringMatchingError:
        pass
    else:
        raise AssertionError("expected MentoringMatchingError")
    os.unlink(db)
    print("CAPACITY OK")


if __name__ == "__main__":
    run_basic()
    run_capacity_cap()
    print("ALL SMOKE TESTS PASSED")
    sys.exit(0)
