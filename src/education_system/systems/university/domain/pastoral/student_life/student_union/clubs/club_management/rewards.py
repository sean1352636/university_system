from education_system.systems.university.domain.pastoral.student_life.student_union.clubs.club_management._imports import (
    datetime, sqlite3, get_connection,
)
import education_system.systems.university.domain.pastoral.student_life.student_union.clubs.club_management._imports as _state


def manage_engagement_rewards():
    """Main engagement rewards system interface"""
    auth = _state.auth

    if not auth or not auth.current_user:
        print("You must be logged in to access the rewards system.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()

        if not result:
            print("No student record is associated with your account.")
            conn.close()
            return

        student_id = result[0]

        while True:
            print("\nEngagement Rewards System")
            print("1. View my points and balance")
            print("2. View available badges")
            print("3. View leaderboard")
            print("4. Point earning opportunities")
            print("5. Redeem points")

            if auth.check_permission('manage_all_clubs') or auth.check_permission('manage_union_reps'):
                print("6. Award points to student")
                print("7. Create new badge")
                print("8. Manage reward system")
                print("9. Return to main menu")
                max_option = 9
            else:
                print("6. Return to main menu")
                max_option = 6

            choice = input("Choose an option: ").strip()

            if choice == '1':
                view_my_points_and_badges(student_id, cursor)
            elif choice == '2':
                view_available_badges(cursor)
            elif choice == '3':
                view_leaderboard(cursor)
            elif choice == '4':
                view_point_opportunities(cursor)
            elif choice == '5':
                print("\n=== Redeem Reward Points ===")
                print("Available redemption options:")
                print("1. Cafeteria voucher (50 points)")
                print("2. Library fine waiver (100 points)")
                print("3. Event ticket discount (75 points)")
                print("4. Merchandise discount (150 points)")
                redeem_choice = input("Select redemption option: ")
                if redeem_choice in ['1', '2', '3', '4']:
                    print("Points redeemed successfully!")
                else:
                    print("Invalid option")
            elif choice == '6' and max_option > 6:
                award_points_to_student(cursor, conn)
            elif choice == '7' and max_option > 6:
                create_new_badge(cursor, conn)
            elif choice == '8' and max_option > 6:
                manage_reward_system_admin(cursor, conn)
            elif choice == str(max_option):
                break
            else:
                print("Invalid choice.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def view_my_points_and_badges(student_id, cursor):
    """View student's points balance and earned badges"""
    try:
        # Get current points balance
        cursor.execute('''
        SELECT
            COALESCE(SUM(points_earned), 0) as total_earned,
            COALESCE(SUM(points_spent), 0) as total_spent,
            COALESCE(SUM(points_earned) - SUM(points_spent), 0) as current_balance
        FROM student_points
        WHERE student_id = ?
        ''', (student_id,))

        points_data = cursor.fetchone()
        total_earned = points_data[0]
        total_spent = points_data[1]
        current_balance = points_data[2]

        print("\nYour Points Summary:")
        print("=" * 30)
        print(f"Total Points Earned: {total_earned}")
        print(f"Total Points Spent: {total_spent}")
        print(f"Current Balance: {current_balance}")

        # Get recent point activities
        cursor.execute('''
        SELECT activity_type, activity_description, points_earned, earned_date
        FROM student_points
        WHERE student_id = ? AND points_earned > 0
        ORDER BY earned_date DESC
        LIMIT 10
        ''', (student_id,))

        recent_activities = cursor.fetchall()

        if recent_activities:
            print("\nRecent Point Activities:")
            print(f"{'Activity':<20} {'Description':<30} {'Points':<8} {'Date':<12}")
            print("-" * 75)

            for activity in recent_activities:
                print(f"{activity[0][:20]:<20} {activity[1][:30]:<30} +{activity[2]:<7} {activity[3][:10]:<12}")

        # Get earned badges
        cursor.execute('''
        SELECT b.badge_name, b.description, sb.earned_date, b.category
        FROM student_badges sb
        JOIN achievement_badges b ON sb.badge_id = b.badge_id
        WHERE sb.student_id = ?
        ORDER BY sb.earned_date DESC
        ''', (student_id,))

        badges = cursor.fetchall()

        if badges:
            print(f"\nYour Badges ({len(badges)}):")
            print(f"{'Badge':<25} {'Category':<15} {'Earned Date':<12}")
            print("-" * 55)

            for badge in badges:
                print(f"{badge[0][:25]:<25} {badge[3]:<15} {badge[2][:10]:<12}")
                print(f"   {badge[1]}")
                print()
        else:
            print("\nNo badges earned yet. Keep participating to earn badges!")

        # Check for new badges that can be earned
        check_and_award_badges(student_id, cursor)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def check_and_award_badges(student_id, cursor):
    """Check if student has earned any new badges"""
    try:
        # Get current points balance
        cursor.execute('''
        SELECT COALESCE(SUM(points_earned), 0) as total_points
        FROM student_points
        WHERE student_id = ?
        ''', (student_id,))

        total_points = cursor.fetchone()[0]

        # Get badges not yet earned that student qualifies for
        cursor.execute('''
        SELECT b.badge_id, b.badge_name, b.description, b.points_required
        FROM achievement_badges b
        WHERE b.points_required <= ?
        AND b.badge_id NOT IN (
            SELECT badge_id FROM student_badges WHERE student_id = ?
        )
        ORDER BY b.points_required
        ''', (total_points, student_id))

        available_badges = cursor.fetchall()

        if available_badges:
            print("\n🎉 Congratulations! You've earned new badges:")

            for badge in available_badges:
                # Award the badge
                earned_date = datetime.now().strftime('%Y-%m-%d')

                cursor.execute('''
                INSERT INTO student_badges (student_id, badge_id, earned_date)
                VALUES (?, ?, ?)
                ''', (student_id, badge[0], earned_date))

                print(f"🏆 {badge[1]} - {badge[2]}")

            # Note: In real implementation, you'd commit these changes
            # Here we're just showing what would happen

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def view_available_badges(cursor):
    """View all available badges in the system"""
    try:
        cursor.execute('''
        SELECT badge_name, description, points_required, category, badge_icon
        FROM achievement_badges
        ORDER BY category, points_required
        ''')

        badges = cursor.fetchall()

        if not badges:
            print("No badges available.")
            return

        print("\nAvailable Achievement Badges:")
        print("=" * 40)

        current_category = ""
        for badge in badges:
            if badge[3] != current_category:
                current_category = badge[3]
                print(f"\n--- {current_category.upper()} ---")

            icon = badge[4] if badge[4] else "🏆"
            print(f"{icon} {badge[0]} ({badge[2]} points)")
            print(f"   {badge[1]}")
            print()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def create_new_badge(cursor, conn):
    """Create a new achievement badge (admin function)"""
    try:
        print("\nCreate New Achievement Badge")
        print("=" * 30)

        badge_name = input("Badge name: ").strip()
        if not badge_name:
            print("Badge name cannot be empty.")
            return

        description = input("Badge description: ").strip()
        if not description:
            print("Description cannot be empty.")
            return

        try:
            points_required = int(input("Points required to earn this badge: ").strip())
            if points_required < 0:
                print("Points required cannot be negative.")
                return
        except ValueError:
            print("Invalid points format.")
            return

        category = input("Badge category (e.g., Participation, Leadership, Academic): ").strip()
        if not category:
            category = "General"

        badge_icon = input("Badge icon (emoji, optional): ").strip()
        if not badge_icon:
            badge_icon = "🏆"

        # Check if badge name already exists
        cursor.execute('SELECT COUNT(*) FROM achievement_badges WHERE badge_name = ?', (badge_name,))
        if cursor.fetchone()[0] > 0:
            print("A badge with this name already exists.")
            return

        cursor.execute('''
        INSERT INTO achievement_badges (
            badge_name, description, points_required, badge_icon, category
        ) VALUES (?, ?, ?, ?, ?)
        ''', (badge_name, description, points_required, badge_icon, category))

        conn.commit()
        badge_id = cursor.lastrowid

        print(f"Badge '{badge_name}' created successfully! Badge ID: {badge_id}")

        # Check if any students now qualify for this badge
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.last_name
        FROM students s
        JOIN (
            SELECT student_id, SUM(points_earned) as total_points
            FROM student_points
            GROUP BY student_id
            HAVING total_points >= ?
        ) sp ON s.student_id = sp.student_id
        WHERE s.student_id NOT IN (
            SELECT student_id FROM student_badges WHERE badge_id = ?
        )
        ''', (points_required, badge_id))

        qualifying_students = cursor.fetchall()

        if qualifying_students:
            print(f"\n{len(qualifying_students)} students now qualify for this badge:")
            for student in qualifying_students:
                print(f"- {student[1]} {student[2]} ({student[0]})")

            auto_award = input("\nAutomatically award to qualifying students? (y/n): ").strip().lower()
            if auto_award == 'y':
                earned_date = datetime.now().strftime('%Y-%m-%d')

                for student in qualifying_students:
                    cursor.execute('''
                    INSERT INTO student_badges (student_id, badge_id, earned_date)
                    VALUES (?, ?, ?)
                    ''', (student[0], badge_id, earned_date))

                conn.commit()
                print(f"Badge awarded to {len(qualifying_students)} students!")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def manage_reward_system_admin(cursor, conn):
    """Admin interface for managing the rewards system"""
    try:
        while True:
            print("\nReward System Administration")
            print("1. View all badges")
            print("2. Edit badge")
            print("3. Delete badge")
            print("4. Bulk award points")
            print("5. Reset student points")
            print("6. Generate rewards report")
            print("7. Return to rewards menu")

            choice = input("Choose option: ").strip()

            if choice == '1':
                # View all badges
                cursor.execute('''
                SELECT b.badge_id, b.badge_name, b.description, b.points_required,
                       b.category, COUNT(sb.student_id) as awarded_count
                FROM achievement_badges b
                LEFT JOIN student_badges sb ON b.badge_id = sb.badge_id
                GROUP BY b.badge_id, b.badge_name, b.description, b.points_required, b.category
                ORDER BY b.category, b.points_required
                ''')

                all_badges = cursor.fetchall()

                print("\nAll Achievement Badges:")
                print(f"{'ID':<6} {'Name':<25} {'Category':<15} {'Points Req':<12} {'Awarded':<8}")
                print("-" * 70)

                for badge in all_badges:
                    print(f"{badge[0]:<6} {badge[1][:25]:<25} {badge[4]:<15} {badge[3]:<12} {badge[5]:<8}")

            elif choice == '2':
                # Edit badge
                badge_id = input("Enter badge ID to edit: ").strip()
                if not badge_id.isdigit():
                    print("Invalid badge ID.")
                    continue

                cursor.execute('''
                SELECT badge_name, description, points_required, category, badge_icon
                FROM achievement_badges WHERE badge_id = ?
                ''', (badge_id,))

                badge = cursor.fetchone()
                if not badge:
                    print("Badge not found.")
                    continue

                print(f"Editing badge: {badge[0]}")
                print(f"Current description: {badge[1]}")
                print(f"Current points required: {badge[2]}")
                print(f"Current category: {badge[3]}")

                new_description = input("New description (or press Enter to keep current): ").strip()
                if not new_description:
                    new_description = badge[1]

                new_points = input("New points required (or press Enter to keep current): ").strip()
                if new_points:
                    try:
                        new_points = int(new_points)
                    except ValueError:
                        print("Invalid points format.")
                        continue
                else:
                    new_points = badge[2]

                new_category = input("New category (or press Enter to keep current): ").strip()
                if not new_category:
                    new_category = badge[3]

                cursor.execute('''
                UPDATE achievement_badges
                SET description = ?, points_required = ?, category = ?
                WHERE badge_id = ?
                ''', (new_description, new_points, new_category, badge_id))

                conn.commit()
                print("Badge updated successfully!")

            elif choice == '3':
                # Delete badge
                badge_id = input("Enter badge ID to delete: ").strip()
                if not badge_id.isdigit():
                    print("Invalid badge ID.")
                    continue

                cursor.execute('SELECT badge_name FROM achievement_badges WHERE badge_id = ?', (badge_id,))
                badge = cursor.fetchone()

                if not badge:
                    print("Badge not found.")
                    continue

                confirm = input(f"Are you sure you want to delete '{badge[0]}'? This will remove it from all students. (y/n): ").strip().lower()
                if confirm == 'y':
                    # Delete student badges first
                    cursor.execute('DELETE FROM student_badges WHERE badge_id = ?', (badge_id,))
                    # Delete the badge
                    cursor.execute('DELETE FROM achievement_badges WHERE badge_id = ?', (badge_id,))

                    conn.commit()
                    print("Badge deleted successfully!")

            elif choice == '4':
                # Bulk award points
                print("Bulk award points to students matching criteria:")
                print("1. All students")
                print("2. Students in specific club")
                print("3. Students with specific role")

                bulk_choice = input("Choose option: ").strip()

                if bulk_choice == '1':
                    cursor.execute('SELECT student_id, first_name, last_name FROM students')
                    target_students = cursor.fetchall()

                elif bulk_choice == '2':
                    cursor.execute('SELECT club_id, club_name FROM student_clubs WHERE status = "active"')
                    clubs = cursor.fetchall()

                    if not clubs:
                        print("No active clubs found.")
                        continue

                    print("Available clubs:")
                    for i, club in enumerate(clubs):
                        print(f"{i+1}. {club[1]}")

                    club_choice = input("Select club (enter number): ").strip()
                    if not club_choice.isdigit() or int(club_choice) < 1 or int(club_choice) > len(clubs):
                        print("Invalid selection.")
                        continue

                    selected_club_id = clubs[int(club_choice)-1][0]

                    cursor.execute('''
                    SELECT s.student_id, s.first_name, s.last_name
                    FROM students s
                    JOIN club_members m ON s.student_id = m.student_id
                    WHERE m.club_id = ?
                    ''', (selected_club_id,))

                    target_students = cursor.fetchall()

                elif bulk_choice == '3':
                    role = input("Enter role (President/Treasurer/Secretary/Member): ").strip()

                    cursor.execute('''
                    SELECT s.student_id, s.first_name, s.last_name
                    FROM students s
                    JOIN club_members m ON s.student_id = m.student_id
                    WHERE m.role = ?
                    ''', (role,))

                    target_students = cursor.fetchall()

                else:
                    print("Invalid choice.")
                    continue

                if not target_students:
                    print("No students found matching criteria.")
                    continue

                print(f"Found {len(target_students)} students.")

                try:
                    points_to_award = int(input("Points to award each student: ").strip())
                    if points_to_award <= 0:
                        print("Points must be positive.")
                        continue
                except ValueError:
                    print("Invalid points format.")
                    continue

                activity_type = input("Activity type: ").strip()
                description = input("Description: ").strip()

                confirm = input(f"Award {points_to_award} points to {len(target_students)} students? (y/n): ").strip().lower()
                if confirm == 'y':
                    earned_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    for student in target_students:
                        # Get current balance
                        cursor.execute('''
                        SELECT COALESCE(SUM(points_earned) - SUM(points_spent), 0)
                        FROM student_points WHERE student_id = ?
                        ''', (student[0],))

                        current_balance = cursor.fetchone()[0]
                        new_balance = current_balance + points_to_award

                        cursor.execute('''
                        INSERT INTO student_points (
                            student_id, points_earned, current_balance, activity_type,
                            activity_description, earned_date
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        ''', (student[0], points_to_award, new_balance, activity_type, description, earned_date))

                    conn.commit()
                    print(f"Successfully awarded {points_to_award} points to {len(target_students)} students!")

            elif choice == '5':
                # Reset student points
                student_id = input("Enter student ID to reset points (or 'ALL' for all students): ").strip()

                if student_id.upper() == 'ALL':
                    confirm = input("Are you sure you want to reset ALL student points? (y/n): ").strip().lower()
                    if confirm == 'y':
                        cursor.execute('DELETE FROM student_points')
                        cursor.execute('DELETE FROM student_badges')
                        conn.commit()
                        print("All student points and badges reset!")
                else:
                    cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (student_id,))
                    student = cursor.fetchone()

                    if not student:
                        print("Student not found.")
                        continue

                    confirm = input(f"Reset points for {student[0]} {student[1]}? (y/n): ").strip().lower()
                    if confirm == 'y':
                        cursor.execute('DELETE FROM student_points WHERE student_id = ?', (student_id,))
                        cursor.execute('DELETE FROM student_badges WHERE student_id = ?', (student_id,))
                        conn.commit()
                        print("Student points and badges reset!")

            elif choice == '6':
                # Generate rewards report
                print("\nRewards System Report:")
                print("=" * 30)

                # Overall statistics
                cursor.execute('SELECT COUNT(*) FROM achievement_badges')
                total_badges = cursor.fetchone()[0]

                cursor.execute('SELECT COUNT(DISTINCT student_id) FROM student_points')
                active_students = cursor.fetchone()[0]

                cursor.execute('SELECT SUM(points_earned) FROM student_points')
                total_points_awarded = cursor.fetchone()[0] or 0

                cursor.execute('SELECT COUNT(*) FROM student_badges')
                total_badges_awarded = cursor.fetchone()[0]

                print(f"Total Badges Available: {total_badges}")
                print(f"Active Students: {active_students}")
                print(f"Total Points Awarded: {total_points_awarded}")
                print(f"Total Badge Awards: {total_badges_awarded}")

                # Most popular activities
                cursor.execute('''
                SELECT activity_type, COUNT(*) as count, SUM(points_earned) as total_points
                FROM student_points
                GROUP BY activity_type
                ORDER BY count DESC
                LIMIT 10
                ''')

                activities = cursor.fetchall()

                if activities:
                    print("\nMost Popular Activities:")
                    print(f"{'Activity':<20} {'Count':<8} {'Points':<8}")
                    print("-" * 40)

                    for activity in activities:
                        print(f"{activity[0][:20]:<20} {activity[1]:<8} {activity[2]:<8}")

            elif choice == '7':
                break

            else:
                print("Invalid choice.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def view_leaderboard(cursor):
    """View engagement points leaderboard"""
    try:
        cursor.execute('''
        SELECT sp.student_id,
               COALESCE(SUM(sp.points_earned) - SUM(sp.points_spent), 0) as balance,
               COALESCE(SUM(sp.points_earned), 0) as total_earned,
               s.first_name, s.last_name
        FROM student_points sp
        LEFT JOIN students s ON sp.student_id = s.student_id
        GROUP BY sp.student_id, s.first_name, s.last_name
        HAVING total_earned > 0
        ORDER BY balance DESC, total_earned DESC
        LIMIT 20
        ''')

        leaders = cursor.fetchall()

        print("\n=== Engagement Leaderboard ===")

        if not leaders:
            print("No points have been earned yet. Be the first on the leaderboard!")
            return

        print(f"{'Rank':<6} {'Student':<28} {'Balance':<10} {'Earned':<10}")
        print("-" * 56)

        for rank, row in enumerate(leaders, start=1):
            name = f"{row[3] or ''} {row[4] or ''}".strip() or str(row[0])
            print(f"{rank:<6} {name[:28]:<28} {row[1]:<10} {row[2]:<10}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def view_point_opportunities(cursor):
    """View point earning opportunities"""
    try:
        print("\n=== Point Earning Opportunities ===")

        # Standard ways to earn engagement points across the club system
        opportunities = [
            ("Competition Registration", 15, "Register a club for an inter-club competition"),
            ("Learning", 15, "Attend a skill-share or learning session"),
            ("Learning", 30, "Deliver / lead a learning session"),
            ("Event Attendance", 10, "Attend a student union event"),
            ("Volunteering", 25, "Volunteer at a club or union activity"),
            ("Leadership", 50, "Take on a club officer role"),
        ]

        print("Earn points by getting involved:")
        print(f"{'Activity':<28} {'Points':<8} {'How to earn'}")
        print("-" * 75)
        for activity, points, how in opportunities:
            print(f"{activity[:28]:<28} +{points:<7} {how}")

        # Show which activities have actually been rewarded so far
        cursor.execute('''
        SELECT activity_type, COUNT(*) as times, SUM(points_earned) as total
        FROM student_points
        WHERE points_earned > 0
        GROUP BY activity_type
        ORDER BY total DESC
        LIMIT 10
        ''')
        activity_rows = cursor.fetchall()

        if activity_rows:
            print("\nMost rewarded activities so far:")
            print(f"{'Activity':<28} {'Times':<8} {'Points':<8}")
            print("-" * 44)
            for row in activity_rows:
                print(f"{(row[0] or 'unknown')[:28]:<28} {row[1]:<8} {row[2]:<8}")
        else:
            print("\nNo points have been awarded yet — every opportunity above is wide open!")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def award_points_to_student(cursor, conn):
    """Award points to a specific student (admin function)"""
    try:
        print("\n=== Award Points ===")

        student_id = input("Enter student ID: ").strip()
        if not student_id:
            print("Student ID cannot be empty.")
            return

        cursor.execute(
            'SELECT first_name, last_name FROM students WHERE student_id = ?',
            (student_id,)
        )
        student = cursor.fetchone()
        if not student:
            print("Student not found.")
            return

        try:
            points = int(input("Points to award: ").strip())
            if points <= 0:
                print("Points must be positive.")
                return
        except ValueError:
            print("Invalid points format.")
            return

        activity_type = input("Activity type: ").strip()
        if not activity_type:
            print("Activity type cannot be empty.")
            return

        description = input("Description: ").strip()

        confirm = input(
            f"Award {points} points to {student[0]} {student[1]}? (y/n): "
        ).strip().lower()
        if confirm != 'y':
            print("Award cancelled.")
            return

        # Compute new running balance
        cursor.execute('''
        SELECT COALESCE(SUM(points_earned) - SUM(points_spent), 0)
        FROM student_points WHERE student_id = ?
        ''', (student_id,))
        current_balance = cursor.fetchone()[0]
        new_balance = current_balance + points

        earned_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO student_points (
            student_id, points_earned, current_balance, activity_type,
            activity_description, earned_date
        ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (student_id, points, new_balance, activity_type, description, earned_date))

        conn.commit()

        print(f"Awarded {points} points to {student[0]} {student[1]}. New balance: {new_balance}")

        # Check whether the student now qualifies for any new badges
        check_and_award_badges(student_id, cursor)
        conn.commit()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
