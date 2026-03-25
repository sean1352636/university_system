from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.domain.student_affairs.services.alumni_management.core import safe_execute, auth


def award_engagement_points(alumni_id, activity_type, points):
    """Award engagement points for various activities"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Award points
        cursor.execute('''
            INSERT INTO engagement_points (alumni_id, activity_type, points_earned, activity_date, description)
            VALUES (?, ?, ?, ?, ?)
        ''', (alumni_id, activity_type, points,
              datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              get_activity_description(activity_type)))

        # Update total engagement score
        cursor.execute('''
            UPDATE alumni
            SET engagement_score = engagement_score + ?, last_activity = ?
            WHERE alumni_id = ?
        ''', (points, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), alumni_id))

        # Check for badge achievements
        check_badge_achievements(alumni_id, cursor)

        conn.commit()
        conn.close()

        print(f"\U0001f389 Earned {points} engagement points for {activity_type}!")

    except Exception as e:
        print(f"Error awarding points: {e}")

def get_activity_description(activity_type):
    """Get description for activity type"""
    descriptions = {
        'profile_complete': 'Completed alumni profile',
        'event_attendance': 'Attended an alumni event',
        'donation_made': 'Made a donation',
        'mentorship_created': 'Started a mentorship',
        'job_posted': 'Posted a job opportunity',
        'job_application': 'Applied for a job',
        'forum_post': 'Created a forum post',
        'forum_reply': 'Replied to a forum discussion',
        'story_created': 'Shared an alumni story',
        'connection_made': 'Made a networking connection',
        'chapter_joined': 'Joined a regional chapter',
        'newsletter_opened': 'Opened a newsletter',
        'profile_updated': 'Updated profile information'
    }
    return descriptions.get(activity_type, f'Completed {activity_type}')

def check_badge_achievements(alumni_id, cursor):
    """Check if alumni has earned any new badges"""
    # Get current total points
    cursor.execute('''
        SELECT SUM(points_earned) as total_points
        FROM engagement_points
        WHERE alumni_id = ?
    ''', (alumni_id,))

    result = cursor.fetchone()
    total_points = result[0] if result[0] else 0

    # Get badges not yet earned
    cursor.execute('''
        SELECT b.badge_id, b.badge_name, b.points_required
        FROM achievement_badges b
        WHERE b.badge_id NOT IN (
            SELECT badge_id FROM alumni_badges WHERE alumni_id = ?
        ) AND b.points_required <= ?
        ORDER BY b.points_required
    ''', (alumni_id, total_points))

    new_badges = cursor.fetchall()

    for badge_id, badge_name, points_required in new_badges:
        # Award the badge
        cursor.execute('''
            INSERT INTO alumni_badges (alumni_id, badge_id, earned_date)
            VALUES (?, ?, ?)
        ''', (alumni_id, badge_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        print(f"\U0001f3c6 Congratulations! You've earned the '{badge_name}' badge!")

def view_engagement_leaderboard():
    """View alumni engagement leaderboard"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to view the leaderboard.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\nAlumni Engagement Leaderboard")
    print("=============================")
    print("1. Overall Leaderboard")
    print("2. Monthly Leaderboard")
    print("3. My Ranking")
    print("4. Badge Leaderboard")

    choice = input("Enter your choice: ")

    if choice == '1':
        # Overall leaderboard
        cursor.execute('''
            SELECT a.first_name, a.last_name, a.graduation_year, a.engagement_score,
                   COUNT(ab.badge_id) as badge_count
            FROM alumni a
            LEFT JOIN alumni_badges ab ON a.alumni_id = ab.alumni_id
            WHERE a.engagement_score > 0
            GROUP BY a.alumni_id
            ORDER BY a.engagement_score DESC
            LIMIT 20
        ''')

        results = cursor.fetchall()

        if results:
            print("\nTop 20 Engaged Alumni (All Time):")
            print("-" * 70)
            print(f"{'Rank':<5} {'Name':<25} {'Class':<8} {'Points':<8} {'Badges':<8}")
            print("-" * 70)

            for i, (first_name, last_name, grad_year, points, badges) in enumerate(results, 1):
                name = f"{first_name} {last_name}"
                print(f"{i:<5} {name[:24]:<25} {grad_year:<8} {points:<8} {badges:<8}")
        else:
            print("No engagement data found.")

    elif choice == '2':
        # Monthly leaderboard
        current_month = datetime.now().strftime('%Y-%m')
        cursor.execute('''
            SELECT a.first_name, a.last_name, a.graduation_year,
                   SUM(ep.points_earned) as monthly_points
            FROM alumni a
            JOIN engagement_points ep ON a.alumni_id = ep.alumni_id
            WHERE ep.activity_date LIKE ?
            GROUP BY a.alumni_id
            ORDER BY monthly_points DESC
            LIMIT 20
        ''', (f'{current_month}%',))

        results = cursor.fetchall()

        if results:
            print(f"\nTop 20 Engaged Alumni (This Month - {current_month}):")
            print("-" * 60)
            print(f"{'Rank':<5} {'Name':<25} {'Class':<8} {'Points':<8}")
            print("-" * 60)

            for i, (first_name, last_name, grad_year, points) in enumerate(results, 1):
                name = f"{first_name} {last_name}"
                print(f"{i:<5} {name[:24]:<25} {grad_year:<8} {points:<8}")
        else:
            print("No engagement data for this month.")

    elif choice == '3':
        # My ranking
        cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()
        if result and result[0].startswith('A'):
            alumni_id = result[0]

            # Get my ranking
            cursor.execute('''
                SELECT COUNT(*) + 1 as rank
                FROM alumni
                WHERE engagement_score > (
                    SELECT engagement_score FROM alumni WHERE alumni_id = ?
                )
            ''', (alumni_id,))

            rank = cursor.fetchone()[0]

            # Get my stats
            cursor.execute('''
                SELECT a.engagement_score, COUNT(ab.badge_id) as badge_count,
                       SUM(CASE WHEN ep.activity_date LIKE ? THEN ep.points_earned ELSE 0 END) as monthly_points
                FROM alumni a
                LEFT JOIN alumni_badges ab ON a.alumni_id = ab.alumni_id
                LEFT JOIN engagement_points ep ON a.alumni_id = ep.alumni_id
                WHERE a.alumni_id = ?
                GROUP BY a.alumni_id
            ''', (datetime.now().strftime('%Y-%m') + '%', alumni_id))

            stats = cursor.fetchone()

            if stats:
                total_points, badges, monthly_points = stats
                monthly_points = monthly_points if monthly_points else 0

                print(f"\nYour Engagement Stats:")
                print(f"Overall Ranking: #{rank}")
                print(f"Total Points: {total_points}")
                print(f"Badges Earned: {badges}")
                print(f"Points This Month: {monthly_points}")

                # Show recent activities
                cursor.execute('''
                    SELECT activity_type, points_earned, activity_date, description
                    FROM engagement_points
                    WHERE alumni_id = ?
                    ORDER BY activity_date DESC
                    LIMIT 10
                ''', (alumni_id,))

                recent_activities = cursor.fetchall()

                if recent_activities:
                    print("\nRecent Activities:")
                    for activity in recent_activities:
                        print(f"  {activity[3]} (+{activity[1]} points) - {activity[2]}")
            else:
                print("No engagement data found for your profile.")
        else:
            print("Alumni profile not found.")

    elif choice == '4':
        # Badge leaderboard
        cursor.execute('''
            SELECT a.first_name, a.last_name, a.graduation_year, COUNT(ab.badge_id) as badge_count
            FROM alumni a
            LEFT JOIN alumni_badges ab ON a.alumni_id = ab.alumni_id
            GROUP BY a.alumni_id
            HAVING badge_count > 0
            ORDER BY badge_count DESC, a.engagement_score DESC
            LIMIT 20
        ''')

        results = cursor.fetchall()

        if results:
            print("\nTop 20 Badge Collectors:")
            print("-" * 60)
            print(f"{'Rank':<5} {'Name':<25} {'Class':<8} {'Badges':<8}")
            print("-" * 60)

            for i, (first_name, last_name, grad_year, badges) in enumerate(results, 1):
                name = f"{first_name} {last_name}"
                print(f"{i:<5} {name[:24]:<25} {grad_year:<8} {badges:<8}")
        else:
            print("No badge data found.")
    else:
        print("Invalid choice.")

    conn.close()

def view_my_badges():
    """View badges earned by current user"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to view your badges.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    # Get current user's alumni ID
    alumni_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        alumni_id = result[0]
    else:
        print("Alumni profile not found for current user.")
        conn.close()
        return

    # Get earned badges
    cursor.execute('''
        SELECT b.badge_name, b.badge_description, b.category, ab.earned_date
        FROM achievement_badges b
        JOIN alumni_badges ab ON b.badge_id = ab.badge_id
        WHERE ab.alumni_id = ?
        ORDER BY ab.earned_date DESC
    ''', (alumni_id,))

    earned_badges = cursor.fetchall()

    # Get available badges
    cursor.execute('''
        SELECT b.badge_name, b.badge_description, b.points_required, b.category
        FROM achievement_badges b
        WHERE b.badge_id NOT IN (
            SELECT badge_id FROM alumni_badges WHERE alumni_id = ?
        )
        ORDER BY b.points_required
    ''', (alumni_id,))

    available_badges = cursor.fetchall()

    # Get current points
    cursor.execute('''
        SELECT SUM(points_earned) as total_points
        FROM engagement_points
        WHERE alumni_id = ?
    ''', (alumni_id,))

    total_points = cursor.fetchone()[0] or 0

    print(f"\nYour Alumni Badges (Total Points: {total_points})")
    print("=" * 50)

    if earned_badges:
        print("\n\U0001f3c6 Earned Badges:")
        print("-" * 40)
        for badge_name, description, category, earned_date in earned_badges:
            print(f"\u2705 {badge_name}")
            print(f"   {description}")
            print(f"   Category: {category} | Earned: {earned_date}")
            print()
    else:
        print("\nNo badges earned yet. Keep engaging to earn your first badge!")

    if available_badges:
        print("\n\U0001f3af Available Badges:")
        print("-" * 40)
        for badge_name, description, points_required, category in available_badges:
            progress = "\u2705 Ready to claim!" if total_points >= points_required else f"Need {points_required - total_points} more points"
            print(f"\U0001f3c5 {badge_name} ({points_required} points required)")
            print(f"   {description}")
            print(f"   Category: {category} | Status: {progress}")
            print()

    conn.close()

def generate_engagement_recommendations():
    """Generate personalized engagement recommendations for alumni"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to get recommendations.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    # Get current user's alumni ID
    alumni_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        alumni_id = result[0]
    else:
        print("Alumni profile not found for current user.")
        conn.close()
        return

    print("\nPersonalized Engagement Recommendations")
    print("=======================================")

    # Get alumni profile and activity data
    cursor.execute('''
        SELECT a.*,
               SUM(ep.points_earned) as total_points,
               MAX(ep.activity_date) as last_activity,
               COUNT(DISTINCT ep.activity_type) as activity_variety
        FROM alumni a
        LEFT JOIN engagement_points ep ON a.alumni_id = ep.alumni_id
        WHERE a.alumni_id = ?
        GROUP BY a.alumni_id
    ''', (alumni_id,))

    profile_data = cursor.fetchone()

    if not profile_data:
        print("Profile data not found.")
        conn.close()
        return

    # Extract profile information
    industry = profile_data[13]
    graduation_year = profile_data[9]
    is_donor = profile_data[20]
    is_mentor = profile_data[21]
    total_points = profile_data[23] or 0
    last_activity = profile_data[24]
    activity_variety = profile_data[25] or 0

    recommendations = []

    # Analyze engagement patterns and generate recommendations

    # Low engagement recommendations
    if total_points < 50:
        recommendations.append({
            'type': 'engagement',
            'title': 'Get Started with Alumni Engagement',
            'description': 'Complete your profile and connect with fellow alumni to earn your first badges!',
            'action': 'Update your profile with skills and achievements',
            'points': 20
        })

    # Activity-based recommendations
    if activity_variety < 3:
        recommendations.append({
            'type': 'variety',
            'title': 'Explore More Alumni Activities',
            'description': 'Try different ways to engage with the alumni community.',
            'action': 'Join the alumni forum or attend an event',
            'points': 25
        })

    # Industry-specific recommendations
    if industry:
        cursor.execute('''
            SELECT COUNT(*) FROM job_postings
            WHERE industry = ? AND is_active = 1
        ''', (industry,))

        industry_jobs = cursor.fetchone()[0]

        if industry_jobs > 0:
            recommendations.append({
                'type': 'career',
                'title': f'Explore {industry} Opportunities',
                'description': f'There are {industry_jobs} active job postings in your industry.',
                'action': 'Check the job board for new opportunities',
                'points': 10
            })

    # Mentorship recommendations
    if not is_mentor and graduation_year and graduation_year < (datetime.now().year - 3):
        recommendations.append({
            'type': 'mentorship',
            'title': 'Become a Mentor',
            'description': 'Share your experience with recent graduates and current students.',
            'action': 'Sign up to become a mentor',
            'points': 50
        })

    # Donation recommendations
    if not is_donor:
        recommendations.append({
            'type': 'giving',
            'title': 'Support Your Alma Mater',
            'description': 'Make your first donation to support current students and programs.',
            'action': 'Browse active fundraising campaigns',
            'points': 30
        })

    # Event recommendations
    cursor.execute('''
        SELECT COUNT(*) FROM unified_events
        WHERE source_type = 'alumni' AND start_datetime > datetime('now') AND registration_required = 1
    ''', ())

    upcoming_events = cursor.fetchone()[0]

    if upcoming_events > 0:
        recommendations.append({
            'type': 'events',
            'title': 'Attend Upcoming Events',
            'description': f'There are {upcoming_events} upcoming alumni events you can attend.',
            'action': 'Register for an upcoming event',
            'points': 20
        })

    # Social recommendations
    cursor.execute('''
        SELECT COUNT(*) FROM networking_connections
        WHERE requester_id = ? OR recipient_id = ?
    ''', (alumni_id, alumni_id))

    connections = cursor.fetchone()[0]

    if connections < 5:
        recommendations.append({
            'type': 'networking',
            'title': 'Expand Your Network',
            'description': 'Connect with more alumni in your field or location.',
            'action': 'Search the alumni directory and send connection requests',
            'points': 15
        })

    # Display recommendations
    if recommendations:
        print(f"Based on your profile and activity, here are your personalized recommendations:")
        print("-" * 70)

        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec['title']} \U0001f3af")
            print(f"   {rec['description']}")
            print(f"   \U0001f4a1 Action: {rec['action']}")
            print(f"   \U0001f3c6 Potential Points: {rec['points']}")
            print(f"   Category: {rec['type'].title()}")
            print("-" * 70)

        # Option to mark recommendations as completed
        mark_choice = input("\nWould you like to mark any recommendations as completed? (y/n): ").lower()
        if mark_choice == 'y':
            try:
                rec_num = int(input(f"Enter recommendation number (1-{len(recommendations)}): "))
                if 1 <= rec_num <= len(recommendations):
                    selected_rec = recommendations[rec_num - 1]

                    # Award points for following recommendation
                    award_engagement_points(alumni_id, f"recommendation_{selected_rec['type']}", selected_rec['points'])
                    print(f"Great! You've earned {selected_rec['points']} points for following the recommendation!")
                else:
                    print("Invalid recommendation number.")
            except ValueError:
                print("Invalid input.")
    else:
        print("\U0001f389 You're doing great! Keep up your excellent engagement with the alumni community.")

    conn.close()
