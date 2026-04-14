"""Study Recommendations CLI."""


def display_study_recommendation_menu(auth):
    from education_system.university_system.modules.domain.academics.study_recommendations.services.study_recommendation_service import StudyRecommendationService
    service = StudyRecommendationService()
    student_id = auth.current_user.get('username', 'unknown') if auth and auth.current_user else 'unknown'

    while True:
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 70)
        print("STUDY RECOMMENDATIONS".center(70))
        print("=" * 70)
        print("\n  1. My Recommendations")
        print("  2. Generate Recommendations")
        print("  3. Mark Recommendation Complete")
        print("  4. My Study Profile")
        print("  5. Log Study Session")
        print("  6. Study History & Stats")
        print("  7. View Weak Areas")
        print("\n  0. Back")
        print("=" * 70)

        choice = input("\nSelect: ").strip()
        if choice == '0':
            break
        elif choice == '1':
            recs = service.get_recommendations(student_id)
            if not recs:
                print("\nNo active recommendations.")
            else:
                for r in recs:
                    print(f"  [{r['priority']}] {r['id']}: {r['title']} ({r.get('module_code', 'General')})")
                    if r.get('description'):
                        print(f"    {r['description'][:80]}")
        elif choice == '2':
            recs = service.generate_recommendations(student_id)
            print(f"\n{len(recs)} recommendations generated.")
            for r in recs:
                print(f"  [{r['priority']}] {r['title']}")
        elif choice == '3':
            rid = int(input("Recommendation ID: ").strip())
            service.mark_recommendation_completed(rid)
            print("Marked as complete.")
        elif choice == '4':
            profile = service.get_profile(student_id)
            if profile:
                print(f"\n  Learning style: {profile.get('learning_style', 'Not set')}")
                print(f"  Study hours/week: {profile.get('study_hours_per_week', 0)}")
                print(f"  Strengths: {profile.get('strengths', 'Not set')}")
                print(f"  Weaknesses: {profile.get('weaknesses', 'Not set')}")
            else:
                print("\nNo profile yet.")
            if input("\nUpdate profile? (y/n): ").strip().lower() == 'y':
                style = input("Learning style (visual/auditory/reading/kinesthetic): ").strip()
                hours = float(input("Study hours per week: ").strip() or '0')
                strengths = input("Strengths: ").strip()
                weaknesses = input("Weaknesses: ").strip()
                service.create_profile(student_id, style, hours, strengths=strengths, weaknesses=weaknesses)
                print("Profile updated.")
        elif choice == '5':
            module = input("Module code: ").strip()
            topic = input("Topic: ").strip()
            duration = int(input("Duration (minutes): ").strip())
            eff = input("Effectiveness (1-5): ").strip()
            service.log_study_session(student_id, module, topic, duration, int(eff) if eff else None)
            print("Session logged.")
        elif choice == '6':
            stats = service.get_study_stats(student_id)
            print(f"\n  Total study time: {stats['total_hours']} hours ({stats['total_sessions']} sessions)")
            print(f"  Avg effectiveness: {stats['avg_effectiveness']}/5")
            print(f"  Study streak: {service.get_study_streak(student_id)} days")
            history = service.get_study_history(student_id, limit=10)
            if history:
                print("\n  Recent sessions:")
                for h in history:
                    print(f"    [{h.get('studied_at', '')}] {h.get('module_code', '')} - {h.get('topic', '')} ({h.get('duration_minutes', 0)} min)")
        elif choice == '7':
            weak = service.get_weak_areas(student_id)
            if weak:
                print("\n  Weak areas (grades below threshold):")
                for w in weak:
                    print(f"    {w.get('module_code', w.get('course', 'Unknown'))} - Grade: {w.get('grade', w.get('score', 'N/A'))}")
            else:
                print("\nNo weak areas identified (or no grade data).")
        input("\nPress Enter to continue...")
