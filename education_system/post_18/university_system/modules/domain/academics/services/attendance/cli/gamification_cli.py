"""CLI handlers for gamification, leaderboards, and achievements."""

import datetime
import json
from collections import Counter
from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.modules.domain.academics.services.attendance.gamification import update_gamification_points


def handle_gamification_portal():
    """Handle gamification portal"""
    print("\n🎮 STUDENT GAMIFICATION PORTAL")
    print("1. View Student Points & Level")
    print("2. View Student Achievements")
    print("3. Award Manual Points")
    print("4. View Attendance Streaks")

    choice = input("Enter your choice (1-4): ")

    if choice == '1':
        student_id = input("Enter student ID: ")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT ag.*, s.first_name, s.last_name
            FROM attendance_gamification ag
            JOIN students s ON ag.student_id = s.student_id
            WHERE ag.student_id = ?
            ''', (student_id,))

            result = cursor.fetchone()
            conn.close()

            if result:
                (_, student_id, points, level, badges, achievements, streak_days,
                 best_streak, last_attendance, total_rewards, created_at, updated_at,
                 first_name, last_name) = result

                print(f"\n🎮 GAMIFICATION PROFILE: {first_name} {last_name}")
                print("=" * 50)
                print(f"Student ID: {student_id}")
                print(f"Current Points: {points:,}")
                print(f"Level: {level}")
                print(f"Current Streak: {streak_days} days")
                print(f"Best Streak: {best_streak} days")
                print(f"Total Rewards: {total_rewards:,}")
                print(f"Last Attendance: {last_attendance}")

                # Display badges
                badge_list = json.loads(badges) if badges else []
                if badge_list:
                    print(f"\n🏆 BADGES: {', '.join(badge_list)}")
                else:
                    print("\n🏆 BADGES: None yet")

                # Display recent achievements
                achievement_list = json.loads(achievements) if achievements else []
                if achievement_list:
                    print("\n🎯 RECENT ACHIEVEMENTS:")
                    for achievement in achievement_list[-5:]:  # Show last 5
                        print(f"  • {achievement.get('description', 'Achievement')} ({achievement.get('date', 'Unknown date')})")

                # Progress to next level
                points_to_next_level = (level * 1000) - points
                if points_to_next_level > 0:
                    print(f"\n📈 Points to next level: {points_to_next_level}")
            else:
                print("Student not found in gamification system.")

        except Exception as e:
            print(f"Error retrieving gamification data: {e}")

    elif choice == '2':
        student_id = input("Enter student ID: ")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT achievements FROM attendance_gamification WHERE student_id = ?
            ''', (student_id,))

            result = cursor.fetchone()
            conn.close()

            if result and result[0]:
                achievement_list = json.loads(result[0])

                print(f"\n🎯 ALL ACHIEVEMENTS FOR STUDENT {student_id}")
                print("=" * 50)

                if achievement_list:
                    for i, achievement in enumerate(achievement_list, 1):
                        print(f"{i}. {achievement.get('badge', 'Unknown')}")
                        print(f"   Description: {achievement.get('description', 'No description')}")
                        print(f"   Earned: {achievement.get('date', 'Unknown date')}")
                        print()
                else:
                    print("No achievements yet.")
            else:
                print("Student not found or has no achievements.")

        except Exception as e:
            print(f"Error retrieving achievements: {e}")

    elif choice == '3':
        student_id = input("Enter student ID: ")

        try:
            points = int(input("Enter points to award: "))
            reason = input("Enter reason for points: ")

            update_gamification_points(student_id, 'manual', bonus_multiplier=1.0)

            # Manually add the specified points
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            UPDATE attendance_gamification
            SET points = points + ?, total_rewards = total_rewards + ?, updated_at = ?
            WHERE student_id = ?
            ''', (points, points, datetime.datetime.now().isoformat(), student_id))

            conn.commit()
            conn.close()

            print(f"✅ Awarded {points} points to student {student_id} for: {reason}")

        except ValueError:
            print("Invalid points value.")
        except Exception as e:
            print(f"Error awarding points: {e}")

    elif choice == '4':
        print("\n📅 ATTENDANCE STREAKS LEADERBOARD")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT ag.student_id, s.first_name, s.last_name, ag.streak_days, ag.best_streak
            FROM attendance_gamification ag
            JOIN students s ON ag.student_id = s.student_id
            ORDER BY ag.streak_days DESC, ag.best_streak DESC
            LIMIT 20
            ''')

            results = cursor.fetchall()
            conn.close()

            if results:
                print(f"{'Rank':<5} {'Student ID':<12} {'Name':<25} {'Current':<10} {'Best':<10}")
                print("-" * 70)

                for rank, (student_id, first_name, last_name, current_streak, best_streak) in enumerate(results, 1):
                    name = f"{first_name} {last_name}"
                    print(f"{rank:<5} {student_id:<12} {name:<25} {current_streak:<10} {best_streak:<10}")
            else:
                print("No streak data available.")

        except Exception as e:
            print(f"Error retrieving streak data: {e}")


def handle_leaderboards():
    """Handle leaderboards"""
    print("\n🏆 ATTENDANCE LEADERBOARDS")
    print("1. Points Leaderboard")
    print("2. Attendance Rate Leaderboard")
    print("3. Module-specific Leaderboard")
    print("4. Weekly Performance")

    choice = input("Enter your choice (1-4): ")

    if choice == '1':
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT ag.student_id, s.first_name, s.last_name, ag.points, ag.level
            FROM attendance_gamification ag
            JOIN students s ON ag.student_id = s.student_id
            ORDER BY ag.points DESC
            LIMIT 20
            ''')

            results = cursor.fetchall()
            conn.close()

            if results:
                print("\n🏆 TOP 20 POINTS LEADERBOARD")
                print("=" * 60)
                print(f"{'Rank':<5} {'Student ID':<12} {'Name':<25} {'Points':<10} {'Level'}")
                print("-" * 60)

                for rank, (student_id, first_name, last_name, points, level) in enumerate(results, 1):
                    name = f"{first_name} {last_name}"
                    medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else ""
                    print(f"{rank:<5} {student_id:<12} {name:<25} {points:<10,} {level} {medal}")
            else:
                print("No gamification data available.")

        except Exception as e:
            print(f"Error retrieving leaderboard: {e}")

    elif choice == '2':
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT
                ar.student_id,
                s.first_name,
                s.last_name,
                AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as attendance_rate,
                COUNT(*) as total_sessions
            FROM attendance_records ar
            JOIN students s ON ar.student_id = s.student_id
            WHERE ar.date >= date('now', '-30 days')
            GROUP BY ar.student_id, s.first_name, s.last_name
            HAVING COUNT(*) >= 5
            ORDER BY attendance_rate DESC
            LIMIT 20
            ''')

            results = cursor.fetchall()
            conn.close()

            if results:
                print("\n📊 TOP 20 ATTENDANCE RATE LEADERBOARD (Last 30 Days)")
                print("=" * 70)
                print(f"{'Rank':<5} {'Student ID':<12} {'Name':<25} {'Rate':<10} {'Sessions'}")
                print("-" * 70)

                for rank, (student_id, first_name, last_name, rate, sessions) in enumerate(results, 1):
                    name = f"{first_name} {last_name}"
                    medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else ""
                    print(f"{rank:<5} {student_id:<12} {name:<25} {rate:<10.1f}% {sessions} {medal}")
            else:
                print("No attendance data available.")

        except Exception as e:
            print(f"Error retrieving attendance leaderboard: {e}")


def handle_achievements():
    """Handle achievement management"""
    print("\n🎯 ACHIEVEMENT MANAGEMENT")
    print("1. View All Achievements")
    print("2. Student Achievement History")
    print("3. Award Custom Achievement")
    print("4. Achievement Statistics")

    choice = input("Enter your choice (1-4): ")

    if choice == '1':
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get all unique achievements
            cursor.execute('''
            SELECT achievements FROM attendance_gamification
            WHERE achievements IS NOT NULL AND achievements != '[]'
            ''')

            all_achievements = []
            for result in cursor.fetchall():
                if result[0]:
                    achievements = json.loads(result[0])
                    all_achievements.extend(achievements)

            conn.close()

            # Count achievements
            achievement_counts = Counter(achievement['badge'] for achievement in all_achievements)

            if achievement_counts:
                print("\n🏆 ALL ACHIEVEMENTS")
                print("=" * 50)
                print(f"{'Achievement':<30} {'Earned Count'}")
                print("-" * 50)

                for badge, count in achievement_counts.most_common():
                    print(f"{badge:<30} {count}")
            else:
                print("No achievements found.")

        except Exception as e:
            print(f"Error retrieving achievements: {e}")

    elif choice == '2':
        student_id = input("Enter student ID: ")

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT achievements, s.first_name, s.last_name
            FROM attendance_gamification ag
            JOIN students s ON ag.student_id = s.student_id
            WHERE ag.student_id = ?
            ''', (student_id,))

            result = cursor.fetchone()
            conn.close()

            if result and result[0]:
                achievements, first_name, last_name = result
                achievement_list = json.loads(achievements)

                print(f"\n🎯 ACHIEVEMENT HISTORY: {first_name} {last_name}")
                print("=" * 60)

                if achievement_list:
                    for i, achievement in enumerate(achievement_list, 1):
                        print(f"{i}. {achievement.get('badge', 'Unknown Badge')}")
                        print(f"   Description: {achievement.get('description', 'No description')}")
                        print(f"   Earned: {achievement.get('date', 'Unknown date')}")
                        print()
                else:
                    print("No achievements yet.")
            else:
                print("Student not found or has no achievements.")

        except Exception as e:
            print(f"Error retrieving student achievements: {e}")
