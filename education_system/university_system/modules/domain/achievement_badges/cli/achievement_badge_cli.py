"""Achievement Badge CLI."""


def display_achievement_badge_menu(auth):
    from education_system.university_system.modules.domain.achievement_badges.services.achievement_badge_service import AchievementBadgeService
    service = AchievementBadgeService()
    student_id = auth.current_user.get('username', 'unknown') if auth and auth.current_user else 'unknown'
    is_admin = auth and auth.current_user and auth.current_user.get('role') == 'admin'

    while True:
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 70)
        print("ACHIEVEMENT BADGES".center(70))
        print("=" * 70)
        counts = service.get_student_badge_count(student_id)
        print(f"\n  Your Badges: {counts['count']} | Points: {counts['total_points']}")
        print("\n  1. My Badges")
        print("  2. Available Badges")
        print("  3. Badge Progress")
        print("  4. Leaderboard")
        print("  5. Badge Statistics")
        if is_admin:
            print("  6. Create Badge (Admin)")
            print("  7. Award Badge (Admin)")
        print("\n  0. Back")
        print("=" * 70)

        choice = input("\nSelect: ").strip()
        if choice == '0':
            break
        elif choice == '1':
            badges = service.get_student_badges(student_id)
            if not badges:
                print("\nNo badges earned yet.")
            else:
                for b in badges:
                    print(f"  [{b.get('category', '')}] {b['name']} ({b.get('points', 0)} pts) - {b.get('awarded_at', '')}")
        elif choice == '2':
            badges = service.list_badges()
            print(f"\n{'ID':<5} {'Name':<25} {'Category':<15} {'Points':<8} {'Criteria':<30}")
            print("-" * 85)
            for b in badges:
                print(f"{b['id']:<5} {b['name']:<25} {b.get('category', ''):<15} {b.get('points', 0):<8} {(b.get('criteria', '') or '')[:28]:<30}")
        elif choice == '3':
            progress = service.get_progress(student_id)
            if not progress:
                print("\nNo badge progress tracked yet.")
            else:
                for p in progress:
                    pct = int(p['current_progress'] / p['target_progress'] * 100) if p['target_progress'] > 0 else 0
                    badge_name = p.get('name', 'Badge %s' % p['badge_id'])
                    print(f"  {badge_name} - {p['current_progress']}/{p['target_progress']} ({pct}%)")
        elif choice == '4':
            leaders = service.get_leaderboard()
            print(f"\n{'Rank':<6} {'Student':<25} {'Badges':<10} {'Points':<10}")
            print("-" * 55)
            for i, l in enumerate(leaders, 1):
                print(f"{i:<6} {l['student_id']:<25} {l['badge_count']:<10} {l['total_points']:<10}")
        elif choice == '5':
            stats = service.get_badge_statistics()
            print(f"\n  Total badge types: {stats['total_badges']}")
            print(f"  Total awarded: {stats['total_awarded']}")
            print(f"  Unique students: {stats['unique_students']}")
            for cat, cnt in stats.get('by_category', {}).items():
                print(f"    {cat}: {cnt}")
        elif choice == '6' and is_admin:
            name = input("Badge name: ").strip()
            desc = input("Description: ").strip()
            cat = input("Category (academic/extracurricular/community/leadership/milestone): ").strip()
            criteria = input("Criteria: ").strip()
            points = int(input("Points [10]: ").strip() or '10')
            bid = service.create_badge(name, desc, cat, criteria=criteria, points=points)
            print(f"\nBadge created with ID: {bid}")
        elif choice == '7' and is_admin:
            sid = input("Student ID: ").strip()
            bid = int(input("Badge ID: ").strip())
            reason = input("Reason: ").strip()
            try:
                service.award_badge(sid, bid, reason=reason)
                print("\nBadge awarded!")
            except ValueError as e:
                print(f"\n{e}")
        input("\nPress Enter to continue...")
