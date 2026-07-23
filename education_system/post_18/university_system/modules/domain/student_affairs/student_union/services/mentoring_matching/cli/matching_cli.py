"""Console menu for mentoring matching — mirrors employer_portal_cli.py style."""
from __future__ import annotations

from typing import Any

from education_system.post_18.university_system.modules.domain.student_affairs.student_union.services.mentoring_matching import (
    MentoringMatchingService,
    MentoringMatchingError,
)


auth: Any = None


def set_auth(auth_object: Any) -> None:
    global auth
    auth = auth_object


def _require_login() -> bool:
    if not auth or not getattr(auth, "current_user", None):
        print("You must be logged in to access mentoring matching.")
        return False
    return True


def _set_mentor_profile(svc: MentoringMatchingService) -> None:
    try:
        mid = int(input("Mentor ID: ").strip())
    except ValueError:
        print("Error: invalid id.")
        return
    fields: dict[str, Any] = {}
    yos = input("Year of study (Enter to skip): ").strip()
    if yos:
        try:
            fields["year_of_study"] = int(yos)
        except ValueError:
            print("Error: year must be int.")
            return
    course = input("Course (Enter to skip): ").strip()
    if course:
        fields["course"] = course
    strengths = input("Strengths CSV (Enter to skip): ").strip()
    if strengths:
        fields["strengths_csv"] = strengths
    avail = input("Availability CSV e.g. mon_am,wed_pm (Enter to skip): ").strip()
    if avail:
        fields["availability_csv"] = avail
    langs = input("Languages CSV (Enter to skip): ").strip()
    if langs:
        fields["languages_csv"] = langs
    cap = input("Max mentees (Enter to skip): ").strip()
    if cap:
        try:
            fields["max_mentees"] = int(cap)
        except ValueError:
            print("Error: max_mentees must be int.")
            return
    bio = input("Bio (Enter to skip): ").strip()
    if bio:
        fields["bio"] = bio
    try:
        svc.upsert_mentor_profile(mid, **fields)
        print(f"Mentor profile #{mid} saved.")
    except MentoringMatchingError as exc:
        print(f"Error: {exc}")


def _set_mentee_prefs(svc: MentoringMatchingService) -> None:
    try:
        mid = int(input("Mentee ID: ").strip())
    except ValueError:
        print("Error: invalid id.")
        return
    fields: dict[str, Any] = {}
    course = input("Course (Enter to skip): ").strip()
    if course:
        fields["course"] = course
    goals = input("Learning goals CSV (Enter to skip): ").strip()
    if goals:
        fields["learning_goals_csv"] = goals
    langs = input("Preferred languages CSV (Enter to skip): ").strip()
    if langs:
        fields["preferred_languages_csv"] = langs
    avail = input("Availability CSV (Enter to skip): ").strip()
    if avail:
        fields["availability_csv"] = avail
    pyear = input("Preferred mentor year minimum (Enter to skip): ").strip()
    if pyear:
        try:
            fields["preferred_year_min"] = int(pyear)
        except ValueError:
            print("Error: year must be int.")
            return
    try:
        svc.upsert_mentee_preferences(mid, **fields)
        print(f"Mentee preferences #{mid} saved.")
    except MentoringMatchingError as exc:
        print(f"Error: {exc}")


def _recommend(svc: MentoringMatchingService) -> None:
    try:
        mid = int(input("Mentee ID: ").strip())
        n_raw = input("Top N (default 5): ").strip()
        n = int(n_raw) if n_raw else 5
        recs = svc.recommend_mentors(mid, top_n=n)
    except (MentoringMatchingError, ValueError) as exc:
        print(f"Error: {exc}")
        return
    if not recs:
        print("No mentors found.")
        return
    print(f"\n{'RecID':<6} {'Mentor':<8} {'Score':<6} Reasons")
    print("-" * 80)
    for r in recs:
        print(f"{r.get('recommendation_id', '-'):<6} "
              f"{r['mentor_id']:<8} {r['score']:<6} "
              f"{'; '.join(r['reasons']) or '(no overlap)'}")
    print(f"\nTotal: {len(recs)}")


def _accept_recommendation(svc: MentoringMatchingService) -> None:
    try:
        rid = int(input("Recommendation ID: ").strip())
        svc.accept_recommendation(rid)
        print(f"Recommendation #{rid} accepted.")
    except (MentoringMatchingError, ValueError) as exc:
        print(f"Error: {exc}")


def _decline_recommendation(svc: MentoringMatchingService) -> None:
    try:
        rid = int(input("Recommendation ID: ").strip())
        svc.decline_recommendation(rid)
        print(f"Recommendation #{rid} declined.")
    except (MentoringMatchingError, ValueError) as exc:
        print(f"Error: {exc}")


def _record_outcome(svc: MentoringMatchingService) -> None:
    try:
        pid = int(input("Pair ID (existing relationship_id): ").strip())
        pre = int(input("Confidence pre (e.g. 1-10): ").strip())
        post = int(input("Confidence post (e.g. 1-10): ").strip())
        gm = int(input("Goals met % (0-100): ").strip())
        sat = int(input("Satisfaction (1-5): ").strip())
        wr = int(input("Would recommend? (1=yes, 0=no): ").strip())
        narr = input("Narrative (optional): ").strip() or None
        oid = svc.record_outcome(pid, pre, post, gm, sat, wr, narrative=narr)
        print(f"Outcome #{oid} recorded.")
    except (MentoringMatchingError, ValueError) as exc:
        print(f"Error: {exc}")


def _outcomes_summary(svc: MentoringMatchingService) -> None:
    raw = input("Mentor ID filter (Enter for all): ").strip()
    mid = None
    if raw:
        try:
            mid = int(raw)
        except ValueError:
            print("Error: invalid id.")
            return
    summary = svc.outcomes_summary(mentor_id=mid)
    print("\n=== Outcomes Summary ===")
    print(f"Count:               {summary['count']}")
    print(f"Avg confidence delta:{summary['avg_confidence_delta']}")
    print(f"Avg satisfaction:    {summary['avg_satisfaction']}")
    print(f"% would recommend:   {summary['pct_would_recommend']}")


def display_mentoring_matching_menu() -> None:
    """Top-level mentoring matching menu."""
    if not _require_login():
        return
    db_path = getattr(auth, "_db_path", None)
    svc = MentoringMatchingService(db_path)

    actions = {
        "1": ("Set Mentor Profile",       _set_mentor_profile),
        "2": ("Set Mentee Preferences",   _set_mentee_prefs),
        "3": ("Recommend Mentors",        _recommend),
        "4": ("Accept Recommendation",    _accept_recommendation),
        "5": ("Decline Recommendation",   _decline_recommendation),
        "6": ("Record Outcome",           _record_outcome),
        "7": ("Outcomes Summary",         _outcomes_summary),
    }

    while True:
        print("\n=== Mentoring Matching ===")
        for k, (label, _fn) in actions.items():
            print(f"  {k}. {label}")
        print("  0. Back")
        choice = input("Choice: ").strip()
        if choice == "0":
            return
        action = actions.get(choice)
        if not action:
            print("Invalid choice.")
            continue
        action[1](svc)
