from education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management._imports import (
    datetime, sqlite3, get_connection,
)
import education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management._imports as _state


def manage_interclub_competitions():
    """Main inter-club competition interface"""
    auth = _state.auth

    if not auth or not auth.current_user:
        print("You must be logged in to access competitions.")
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
            print(f"\nInter-club Competitions")
            print("1. View active competitions")
            print("2. Register club for competition")
            print("3. View competition results")
            print("4. My competition history")

            if auth.check_permission('manage_all_clubs') or auth.check_permission('manage_union_reps'):
                print("5. Create new competition")
                print("6. Manage competition")
                print("7. Update scores")
                print("8. Generate competition reports")
                print("9. Return to main menu")
                max_option = 9
            else:
                print("5. Return to main menu")
                max_option = 5

            choice = input("Choose an option: ").strip()

            if choice == '1':
                view_active_competitions(cursor)
            elif choice == '2':
                register_club_for_competition(student_id, cursor, conn)
            elif choice == '3':
                view_competition_results(cursor)
            elif choice == '4':
                view_my_competition_history(student_id, cursor)
            elif choice == '5' and max_option > 5:
                create_new_competition(student_id, cursor, conn)
            elif choice == '6' and max_option > 5:
                manage_competition_admin(cursor, conn)
            elif choice == '7' and max_option > 5:
                update_competition_scores(cursor, conn)
            elif choice == '8' and max_option > 5:
                generate_competition_reports(cursor)
            elif choice == str(max_option):
                break
            else:
                print("Invalid choice.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def register_club_for_competition(student_id, cursor, conn):
    """Register a club for a competition"""
    try:
        # Get clubs where student is an officer
        cursor.execute('''
        SELECT c.club_id, c.club_name
        FROM student_clubs c
        WHERE (c.president_id = ? OR c.treasurer_id = ? OR c.secretary_id = ?)
        AND c.status = 'active'
        ORDER BY c.club_name
        ''', (student_id, student_id, student_id))

        clubs = cursor.fetchall()

        if not clubs:
            print("You are not an officer of any club.")
            return

        # Get competitions open for registration
        cursor.execute('''
        SELECT competition_id, competition_name, competition_type, registration_deadline,
               max_participants_per_club
        FROM club_competitions
        WHERE status IN ('upcoming', 'registration_open')
        AND registration_deadline >= date('now')
        ORDER BY registration_deadline
        ''')

        competitions = cursor.fetchall()

        if not competitions:
            print("No competitions currently open for registration.")
            return

        print("\nYour clubs:")
        for i, club in enumerate(clubs):
            print(f"{i+1}. {club[1]}")

        club_choice = input("Select club to register (enter number): ").strip()
        if not club_choice.isdigit() or int(club_choice) < 1 or int(club_choice) > len(clubs):
            print("Invalid selection.")
            return

        selected_club = clubs[int(club_choice)-1]
        club_id = selected_club[0]
        club_name = selected_club[1]

        print(f"\nCompetitions open for registration:")
        for i, comp in enumerate(competitions):
            print(f"{i+1}. {comp[1]} ({comp[2]}) - Deadline: {comp[3]}")

        comp_choice = input("Select competition (enter number): ").strip()
        if not comp_choice.isdigit() or int(comp_choice) < 1 or int(comp_choice) > len(competitions):
            print("Invalid selection.")
            return

        selected_comp = competitions[int(comp_choice)-1]
        competition_id = selected_comp[0]
        competition_name = selected_comp[1]
        max_participants = selected_comp[4]

        # Check if club is already registered
        cursor.execute('''
        SELECT COUNT(*) FROM competition_participants
        WHERE competition_id = ? AND club_id = ?
        ''', (competition_id, club_id))

        if cursor.fetchone()[0] > 0:
            print(f"{club_name} is already registered for {competition_name}.")
            return

        print(f"\nRegistering {club_name} for {competition_name}")
        print(f"Maximum participants allowed per club: {max_participants}")

        # Get club members to select participants
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.last_name, m.role
        FROM students s
        JOIN club_members m ON s.student_id = m.student_id
        WHERE m.club_id = ?
        ORDER BY m.role, s.last_name, s.first_name
        ''', (club_id,))

        club_members = cursor.fetchall()

        if not club_members:
            print("No members found in this club.")
            return

        print(f"\nClub members:")
        for i, member in enumerate(club_members):
            print(f"{i+1}. {member[1]} {member[2]} ({member[3]})")

        participants = []
        for i in range(min(max_participants, len(club_members))):
            if i == 0:
                participant_choice = input(f"Select participant {i+1} (enter number): ").strip()
            else:
                participant_choice = input(f"Select participant {i+1} (enter number, or press Enter to stop): ").strip()
                if not participant_choice:
                    break

            if (participant_choice.isdigit() and
                1 <= int(participant_choice) <= len(club_members) and
                club_members[int(participant_choice)-1][0] not in [p[0] for p in participants]):

                participants.append(club_members[int(participant_choice)-1])
            else:
                print("Invalid selection or participant already selected.")
                i -= 1  # Try again

        if not participants:
            print("No participants selected.")
            return

        # Register participants
        registration_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for participant in participants:
            cursor.execute('''
            INSERT INTO competition_participants (
                competition_id, club_id, student_id, registration_date
            ) VALUES (?, ?, ?, ?)
            ''', (competition_id, club_id, participant[0], registration_date))

        conn.commit()

        print(f"\nSuccessfully registered {club_name} for {competition_name}!")
        print(f"Participants:")
        for participant in participants:
            print(f"- {participant[1]} {participant[2]}")

        # Award points for participation
        for participant in participants:
            auto_award_points(participant[0], "Competition Registration", 15,
                            f"Registered for {competition_name}", cursor, conn)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


# Placeholder functions called by manage_interclub_competitions
def view_active_competitions(cursor):
    """View active competitions"""
    print("\n=== Active Competitions ===")
    print("Coming soon...")


def view_competition_results(cursor):
    """View competition results"""
    print("\n=== Competition Results ===")
    print("Coming soon...")


def view_my_competition_history(student_id, cursor):
    """View personal competition history"""
    print("\n=== My Competition History ===")
    print("Coming soon...")


def create_new_competition(student_id, cursor, conn):
    """Create a new competition"""
    print("\n=== Create Competition ===")
    print("Coming soon...")


def manage_competition_admin(cursor, conn):
    """Admin competition management"""
    print("\n=== Manage Competition ===")
    print("Coming soon...")


def update_competition_scores(cursor, conn):
    """Update competition scores"""
    print("\n=== Update Scores ===")
    print("Coming soon...")


def generate_competition_reports(cursor):
    """Generate competition reports"""
    print("\n=== Competition Reports ===")
    print("Coming soon...")


def auto_award_points(student_id, activity_type, points, description, cursor, conn):
    """Automatically award points to a student"""
    try:
        earned_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        SELECT COALESCE(SUM(points_earned) - SUM(points_spent), 0)
        FROM student_points WHERE student_id = ?
        ''', (student_id,))

        current_balance = cursor.fetchone()[0]
        new_balance = current_balance + points

        cursor.execute('''
        INSERT INTO student_points (
            student_id, points_earned, current_balance, activity_type,
            activity_description, earned_date
        ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (student_id, points, new_balance, activity_type, description, earned_date))

        conn.commit()
    except Exception:
        pass  # Silently fail for auto-award
