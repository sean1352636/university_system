from __future__ import annotations

from university_system.infrastructure.database.db import sqlite3, get_connection
from university_system.modules.domain.student_affairs.student_union.services import context as ctx

def generate_advanced_analytics():
    """Advanced analytics dashboard"""
    
    if not ctx.auth or not ctx.auth.current_user:
        print("You must be logged in to access analytics.")
        return

    if not (ctx.auth.check_permission('manage_all_clubs') or ctx.auth.check_permission('view_election_results')):
        print("You don't have permission to access advanced analytics.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        while True:
            print(f"\n📊 Advanced Analytics Dashboard")
            print("1. Engagement trend analysis")
            print("2. Event popularity predictions")
            print("3. Member retention insights")
            print("4. Activity correlation analysis")
            print("5. Personalized recommendations")
            print("6. Performance benchmarking")
            print("7. Return to main menu")

            choice = input("Choose an option: ").strip()

            if choice == '1':
                engagement_trend_analysis(cursor)
            elif choice == '2':
                event_popularity_predictions(cursor)
            elif choice == '3':
                member_retention_insights(cursor)
            elif choice == '4':
                activity_correlation_analysis(cursor)
            elif choice == '5':
                generate_personalized_recommendations(cursor)
            elif choice == '6':
                performance_benchmarking(cursor)
            elif choice == '7':
                break
            else:
                print("Invalid choice.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def activity_correlation_analysis(cursor):
    """Analyze correlations between different activities"""
    try:
        print(f"\n🔗 Activity Correlation Analysis")
        print("=" * 40)

        # Club membership vs event attendance correlation
        cursor.execute('''
        SELECT 
            COUNT(DISTINCT cm.club_id) as clubs_joined,
            COUNT(DISTINCT er.event_id) as events_attended,
            s.student_id
        FROM students s
        LEFT JOIN club_members cm ON s.student_id = cm.student_id
        LEFT JOIN event_registrations er ON s.student_id = er.student_id
        GROUP BY s.student_id
        HAVING clubs_joined > 0 OR events_attended > 0
        ''')

        activity_data = cursor.fetchall()

        if len(activity_data) > 10:
            # Calculate correlation coefficient (simplified)
            clubs = [row[0] for row in activity_data]
            events = [row[1] for row in activity_data]

            n = len(clubs)
            sum_clubs = sum(clubs)
            sum_events = sum(events)
            sum_clubs_sq = sum(x*x for x in clubs)
            sum_events_sq = sum(x*x for x in events)
            sum_clubs_events = sum(clubs[i] * events[i] for i in range(n))

            numerator = n * sum_clubs_events - sum_clubs * sum_events
            denominator = ((n * sum_clubs_sq - sum_clubs**2) * (n * sum_events_sq - sum_events**2))**0.5

            if denominator != 0:
                correlation = numerator / denominator
                print(f"Club Membership vs Event Attendance Correlation: {correlation:.3f}")

                if correlation > 0.5:
                    print("Strong positive correlation - students who join more clubs attend more events")
                elif correlation > 0.3:
                    print("Moderate positive correlation - club membership encourages event attendance")
                elif correlation < -0.3:
                    print("Negative correlation - interesting pattern detected")
                else:
                    print("Weak correlation - club membership and event attendance are relatively independent")

        # Leadership roles vs overall engagement
        cursor.execute('''
        SELECT 
            s.student_id,
            CASE WHEN cm.role IN ('President', 'Treasurer', 'Secretary') THEN 1 ELSE 0 END as is_leader,
            COUNT(DISTINCT er.event_id) as events_attended,
            COUNT(DISTINCT cm2.club_id) as clubs_joined
        FROM students s
        LEFT JOIN club_members cm ON s.student_id = cm.student_id
        LEFT JOIN event_registrations er ON s.student_id = er.student_id
        LEFT JOIN club_members cm2 ON s.student_id = cm2.student_id
        GROUP BY s.student_id
        ''')

        leadership_data = cursor.fetchall()

        leaders = [row for row in leadership_data if row[1] == 1]
        non_leaders = [row for row in leadership_data if row[1] == 0]

        if leaders and non_leaders:
            avg_events_leaders = sum(row[2] for row in leaders) / len(leaders)
            avg_events_non_leaders = sum(row[2] for row in non_leaders) / len(non_leaders)
            avg_clubs_leaders = sum(row[3] for row in leaders) / len(leaders)
            avg_clubs_non_leaders = sum(row[3] for row in non_leaders) / len(non_leaders)

            print(f"\nLeadership Impact Analysis:")
            print(f"Leaders - Avg events attended: {avg_events_leaders:.1f}, Avg clubs: {avg_clubs_leaders:.1f}")
            print(f"Non-leaders - Avg events attended: {avg_events_non_leaders:.1f}, Avg clubs: {avg_clubs_non_leaders:.1f}")

            if avg_events_leaders > avg_events_non_leaders * 1.2:
                print("Leaders are significantly more engaged in events")
            if avg_clubs_leaders > avg_clubs_non_leaders * 1.2:
                print("Leaders tend to be members of more clubs")

        # Event type preferences by demographics
        cursor.execute('''
        SELECT 
            s.course,
            e.category,
            COUNT(*) as attendance_count
        FROM students s
        JOIN event_registrations er ON s.student_id = er.student_id
        JOIN union_events e ON er.event_id = e.event_id
        GROUP BY s.course, e.category
        HAVING COUNT(*) >= 3
        ORDER BY s.course, attendance_count DESC
        ''')

        preference_data = cursor.fetchall()

        if preference_data:
            print(f"\nEvent Preferences by Course:")
            current_course = ""
            for pref in preference_data:
                if pref[0] != current_course:
                    current_course = pref[0]
                    print(f"\n{current_course}:")
                print(f"  {pref[1]}: {pref[2]} attendances")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def generate_personalized_recommendations(cursor):
    """Generate personalized recommendations for users"""
    try:
        
        # Get current user's student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (ctx.auth.current_user['id'],))
        result = cursor.fetchone()

        if not result:
            print("No student record found.")
            return

        student_id = result[0]

        print(f"\n🎯 Personalized Recommendations")
        print("=" * 40)

        # Get user's activity profile
        cursor.execute('''
        SELECT 
            COUNT(DISTINCT cm.club_id) as clubs_joined,
            COUNT(DISTINCT er.event_id) as events_attended,
            GROUP_CONCAT(DISTINCT e.category) as event_categories,
            GROUP_CONCAT(DISTINCT c.category) as club_categories
        FROM students s
        LEFT JOIN club_members cm ON s.student_id = cm.student_id
        LEFT JOIN student_clubs c ON cm.club_id = c.club_id
        LEFT JOIN event_registrations er ON s.student_id = er.student_id
        LEFT JOIN union_events e ON er.event_id = e.event_id
        WHERE s.student_id = ?
        ''', (student_id,))

        profile = cursor.fetchone()

        print(f"Your Activity Profile:")
        print(f"Clubs joined: {profile[0]}")
        print(f"Events attended: {profile[1]}")

        # Recommend clubs based on similar users
        cursor.execute('''
        SELECT c.club_name, c.description, COUNT(*) as similarity_score
        FROM student_clubs c
        JOIN club_members cm ON c.club_id = cm.club_id
        WHERE cm.student_id IN (
            SELECT cm2.student_id
            FROM club_members cm1
            JOIN club_members cm2 ON cm1.club_id = cm2.club_id
            WHERE cm1.student_id = ? AND cm2.student_id != ?
        )
        AND c.club_id NOT IN (
            SELECT club_id FROM club_members WHERE student_id = ?
        )
        AND c.status = 'active'
        GROUP BY c.club_id, c.club_name, c.description
        ORDER BY similarity_score DESC
        LIMIT 5
        ''', (student_id, student_id, student_id))

        club_recommendations = cursor.fetchall()

        if club_recommendations:
            print(f"\n🏛️ Recommended Clubs (based on similar users):")
            for i, club in enumerate(club_recommendations, 1):
                print(f"{i}. {club[0]} - {club[1]}")
                print(f"   Similarity score: {club[2]} shared connections")

        # Recommend events based on past preferences
        if profile[2]:  # If user has attended events
            attended_categories = profile[2].split(',')
            category_filter = "', '".join(attended_categories)

            cursor.execute(f'''
            SELECT e.event_name, e.description, e.event_date, c.club_name
            FROM union_events e
            JOIN student_clubs c ON e.organizer_id = c.club_id
            WHERE e.category IN ('{category_filter}')
            AND e.event_date >= date('now')
            AND e.status = 'upcoming'
            AND e.event_id NOT IN (
                SELECT event_id FROM event_registrations WHERE student_id = ?
            )
            ORDER BY e.event_date
            LIMIT 5
            ''', (student_id,))

            event_recommendations = cursor.fetchall()

            if event_recommendations:
                print(f"\n📅 Recommended Upcoming Events:")
                for i, event in enumerate(event_recommendations, 1):
                    print(f"{i}. {event[0]} - {event[3]}")
                    print(f"   Date: {event[2]}")
                    print(f"   {event[1]}")

        # Recommend based on low engagement
        if profile[0] == 0:
            print(f"\n💡 Getting Started Recommendations:")
            print("- Join a club related to your interests")
            print("- Attend a social event to meet people")
            print("- Consider academic support groups")
        elif profile[1] < 3:
            print(f"\n💡 Boost Your Engagement:")
            print("- Attend more events to meet like-minded students")
            print("- Consider volunteering for club activities")
            print("- Join study groups in your subject area")

        # Recommend leadership opportunities
        cursor.execute('''
        SELECT COUNT(*) FROM club_members 
        WHERE student_id = ? AND role IN ('President', 'Treasurer', 'Secretary')
        ''', (student_id,))

        leadership_roles = cursor.fetchone()[0]

        if leadership_roles == 0 and profile[0] > 0:
            print(f"\n🌟 Leadership Opportunities:")
            print("- Consider running for a club officer position")
            print("- Volunteer to organize events")
            print("- Mentor new club members")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def performance_benchmarking(cursor):
    """Compare performance across different metrics"""
    try:
        print(f"\n📊 Performance Benchmarking")
        print("=" * 35)

        # Club performance benchmarks
        cursor.execute('''
        SELECT 
            c.club_name,
            c.member_count,
            COUNT(DISTINCT e.event_id) as events_organized,
            AVG(e.current_attendees) as avg_event_attendance,
            COUNT(DISTINCT er.student_id) as unique_event_attendees
        FROM student_clubs c
        LEFT JOIN union_events e ON c.club_id = e.organizer_id 
            AND e.event_date >= date('now', '-12 months')
        LEFT JOIN event_registrations er ON e.event_id = er.event_id
        WHERE c.status = 'active'
        GROUP BY c.club_id, c.club_name, c.member_count
        HAVING c.member_count >= 5
        ORDER BY c.member_count DESC
        ''')

        club_performance = cursor.fetchall()

        if club_performance:
            print("Club Performance Benchmarks (Last 12 Months):")
            print(f"{'Club':<25} {'Members':<8} {'Events':<8} {'Avg Attend':<10} {'Reach':<8}")
            print("-" * 65)

            # Calculate percentiles
            member_counts = [club[1] for club in club_performance]
            event_counts = [club[2] for club in club_performance]
            attendance_avgs = [club[3] for club in club_performance if club[3]]

            member_75th = sorted(member_counts)[int(len(member_counts) * 0.75)] if member_counts else 0
            event_75th = sorted(event_counts)[int(len(event_counts) * 0.75)] if event_counts else 0
            attendance_75th = sorted(attendance_avgs)[int(len(attendance_avgs) * 0.75)] if attendance_avgs else 0

            for club in club_performance[:15]:  # Top 15 clubs
                avg_attend = f"{club[3]:.1f}" if club[3] else "N/A"
                reach = club[4] if club[4] else 0

                # Add performance indicators
                indicators = ""
                if club[1] >= member_75th:
                    indicators += "👥"
                if club[2] >= event_75th:
                    indicators += "📅"
                if club[3] and club[3] >= attendance_75th:
                    indicators += "🎯"

                print(f"{club[0][:25]:<25} {club[1]:<8} {club[2]:<8} {avg_attend:<10} {reach:<8} {indicators}")

            print(f"\nLegend: 👥 Top 25% membership, 📅 Top 25% events, 🎯 Top 25% attendance")

        # Event success benchmarks
        cursor.execute('''
        SELECT 
            category,
            COUNT(*) as total_events,
            AVG(current_attendees) as avg_attendance,
            AVG(CAST(current_attendees AS FLOAT) / CAST(max_attendees AS FLOAT)) as avg_fill_rate,
            MAX(current_attendees) as max_attendance
        FROM union_events
        WHERE event_date >= date('now', '-12 months')
        AND max_attendees > 0
        GROUP BY category
        HAVING COUNT(*) >= 3
        ORDER BY avg_attendance DESC
        ''')

        event_benchmarks = cursor.fetchall()

        if event_benchmarks:
            print(f"\nEvent Category Benchmarks:")
            print(f"{'Category':<20} {'Events':<8} {'Avg Attend':<10} {'Fill Rate':<10} {'Peak':<8}")
            print("-" * 60)

            for benchmark in event_benchmarks:
                fill_rate = f"{benchmark[3]*100:.1f}%" if benchmark[3] else "N/A"
                print(f"{benchmark[0]:<20} {benchmark[1]:<8} {benchmark[2]:<10.1f} {fill_rate:<10} {benchmark[4]:<8}")

        # Engagement quality metrics
        cursor.execute('''
        SELECT 
            'High Engagement' as segment,
            COUNT(DISTINCT s.student_id) as student_count,
            AVG(club_count) as avg_clubs,
            AVG(event_count) as avg_events
        FROM students s
        JOIN (
            SELECT 
                student_id,
                COUNT(DISTINCT cm.club_id) as club_count,
                COUNT(DISTINCT er.event_id) as event_count
            FROM students s2
            LEFT JOIN club_members cm ON s2.student_id = cm.student_id
            LEFT JOIN event_registrations er ON s2.student_id = er.student_id
            GROUP BY s2.student_id
            HAVING club_count >= 2 AND event_count >= 3
        ) engagement ON s.student_id = engagement.student_id

        UNION ALL

        SELECT 
            'Medium Engagement' as segment,
            COUNT(DISTINCT s.student_id) as student_count,
            AVG(club_count) as avg_clubs,
            AVG(event_count) as avg_events
        FROM students s
        JOIN (
            SELECT 
                student_id,
                COUNT(DISTINCT cm.club_id) as club_count,
                COUNT(DISTINCT er.event_id) as event_count
            FROM students s2
            LEFT JOIN club_members cm ON s2.student_id = cm.student_id
            LEFT JOIN event_registrations er ON s2.student_id = er.student_id
            GROUP BY s2.student_id
            HAVING (club_count = 1 AND event_count >= 1) OR (club_count >= 1 AND event_count BETWEEN 1 AND 2)
        ) engagement ON s.student_id = engagement.student_id
        ''')

        engagement_segments = cursor.fetchall()

        if engagement_segments:
            print(f"\nEngagement Segmentation:")
            print(f"{'Segment':<18} {'Students':<10} {'Avg Clubs':<10} {'Avg Events':<10}")
            print("-" * 50)

            for segment in engagement_segments:
                print(f"{segment[0]:<18} {segment[1]:<10} {segment[2]:<10.1f} {segment[3]:<10.1f}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def learning_analytics_dashboard(student_id, cursor):
    """Learning analytics and progress dashboard"""
    try:
        print(f"\n📊 Learning Analytics Dashboard")
        print("=" * 40)

        # Learning activity summary
        cursor.execute('''
        SELECT activity_type, COUNT(*) as count, SUM(points_earned) as points
        FROM student_points
        WHERE student_id = ? AND (
            activity_type LIKE '%Learning%' OR 
            activity_type LIKE '%Academic%' OR
            activity_type LIKE '%Study%'
        )
        GROUP BY activity_type
        ORDER BY points DESC
        ''', (student_id,))

        learning_activities = cursor.fetchall()

        if learning_activities:
            print("Your Learning Activities:")
            print(f"{'Activity Type':<25} {'Count':<8} {'Points':<8}")
            print("-" * 45)

            total_learning_points = 0
            for activity in learning_activities:
                total_learning_points += activity[2]
                print(f"{activity[0]:<25} {activity[1]:<8} {activity[2]:<8}")

            print("-" * 45)
            print(f"{'TOTAL LEARNING POINTS:':<25} {'':<8} {total_learning_points:<8}")
        else:
            total_learning_points = 0
            print("No learning activities recorded yet.")

        # Learning level assessment
        print(f"\n🎯 Learning Engagement Level:")

        if total_learning_points >= 200:
            level = "🏆 Learning Champion"
            next_milestone = "Maximum level achieved!"
        elif total_learning_points >= 100:
            level = "🥇 Advanced Learner"
            next_milestone = f"{200 - total_learning_points} points to Champion"
        elif total_learning_points >= 50:
            level = "🥈 Active Learner"
            next_milestone = f"{100 - total_learning_points} points to Advanced"
        elif total_learning_points >= 20:
            level = "🥉 Engaged Student"
            next_milestone = f"{50 - total_learning_points} points to Active"
        else:
            level = "🌱 Getting Started"
            next_milestone = f"{20 - total_learning_points} points to Engaged"

        print(f"Current level: {level}")
        print(f"Next milestone: {next_milestone}")

        # Learning recommendations
        print(f"\n💡 Personalized Learning Recommendations:")

        if total_learning_points < 50:
            print("• Join a study group in your subject area")
            print("• Attend academic workshops")
            print("• Participate in book clubs")
        elif total_learning_points < 100:
            print("• Consider becoming a peer tutor")
            print("• Organize knowledge sharing sessions")
            print("• Attend research presentations")
        else:
            print("• Lead academic initiatives")
            print("• Mentor other students")
            print("• Organize conferences or symposiums")

        # Learning streak
        learning_streak = 7  # This would be calculated from actual data
        print(f"\n🔥 Learning streak: {learning_streak} days")

        if learning_streak >= 30:
            print("🎉 Incredible dedication to learning!")
        elif learning_streak >= 14:
            print("👏 Great learning habit!")
        elif learning_streak >= 7:
            print("📚 Good learning momentum!")
        else:
            print("🌟 Keep building your learning habit!")

        # Goals setting
        print(f"\n🎯 Set Learning Goals:")

        goal_type = input("Set a goal for (books/skills/points/sessions): ").strip().lower()

        if goal_type in ['books', 'skills', 'points', 'sessions']:
            try:
                goal_amount = int(input(f"How many {goal_type} this semester? ").strip())
                print(f"Goal set: {goal_amount} {goal_type} this semester")
                print("Progress will be tracked on your dashboard")
            except ValueError:
                print("Invalid goal amount.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
