from education_system.post_18.university_system.modules.domain.student_affairs.student_union.clubs.club_management._imports import (
    datetime, sqlite3, get_connection,
)
import education_system.post_18.university_system.modules.domain.student_affairs.student_union.clubs.club_management._imports as _state
import logging

logger = logging.getLogger(__name__)


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
            print("\nInter-club Competitions")
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

        print("\nCompetitions open for registration:")
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

        print("\nClub members:")
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
        print("Participants:")
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


# Functions called by manage_interclub_competitions
def view_active_competitions(cursor):
    """View competitions that are currently open or in progress"""
    try:
        cursor.execute('''
        SELECT c.competition_id, c.competition_name, c.competition_type, c.start_date,
               c.end_date, c.registration_deadline, c.status, c.prizes,
               COUNT(DISTINCT p.club_id) as club_count,
               COUNT(p.participant_id) as participant_count
        FROM club_competitions c
        LEFT JOIN competition_participants p ON c.competition_id = p.competition_id
        WHERE c.status IN ('upcoming', 'registration_open', 'active', 'in_progress')
        GROUP BY c.competition_id, c.competition_name, c.competition_type, c.start_date,
                 c.end_date, c.registration_deadline, c.status, c.prizes
        ORDER BY c.start_date
        ''')

        competitions = cursor.fetchall()

        print("\n=== Active Competitions ===")

        if not competitions:
            print("No active competitions yet.")
            return

        for comp in competitions:
            print(f"\n[{comp[0]}] {comp[1]} ({comp[2]})")
            print(f"   Status: {comp[6]}")
            print(f"   Runs: {comp[3]} to {comp[4]}")
            print(f"   Registration deadline: {comp[5]}")
            print(f"   Registered: {comp[8]} club(s), {comp[9]} participant(s)")
            if comp[7]:
                print(f"   Prizes: {comp[7]}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def view_competition_results(cursor):
    """View results of completed competitions"""
    try:
        cursor.execute('''
        SELECT competition_id, competition_name, competition_type, end_date, prizes
        FROM club_competitions
        WHERE status IN ('completed', 'finished', 'closed')
        ORDER BY end_date DESC
        ''')

        competitions = cursor.fetchall()

        print("\n=== Competition Results ===")

        if not competitions:
            print("No completed competitions yet.")
            return

        for comp in competitions:
            print(f"\n[{comp[0]}] {comp[1]} ({comp[2]}) - Ended: {comp[3]}")
            if comp[4]:
                print(f"   Prizes: {comp[4]}")

            cursor.execute('''
            SELECT p.rank_position, p.score, s.first_name, s.last_name,
                   c.club_name
            FROM competition_participants p
            LEFT JOIN students s ON p.student_id = s.student_id
            LEFT JOIN student_clubs c ON p.club_id = c.club_id
            WHERE p.competition_id = ?
            ORDER BY
                CASE WHEN p.rank_position IS NULL THEN 1 ELSE 0 END,
                p.rank_position,
                p.score DESC
            ''', (comp[0],))

            results = cursor.fetchall()

            if not results:
                print("   No participants recorded.")
                continue

            print(f"   {'Rank':<6} {'Participant':<28} {'Club':<22} {'Score':<8}")
            print("   " + "-" * 66)
            for r in results:
                rank = r[0] if r[0] is not None else '-'
                name = f"{r[2] or ''} {r[3] or ''}".strip() or 'Unknown'
                club = r[4] or '-'
                score = r[1] if r[1] is not None else '-'
                print(f"   {str(rank):<6} {name[:28]:<28} {club[:22]:<22} {str(score):<8}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def view_my_competition_history(student_id, cursor):
    """View personal competition history"""
    try:
        cursor.execute('''
        SELECT c.competition_name, c.competition_type, c.status,
               p.registration_date, p.score, p.rank_position, cl.club_name
        FROM competition_participants p
        JOIN club_competitions c ON p.competition_id = c.competition_id
        LEFT JOIN student_clubs cl ON p.club_id = cl.club_id
        WHERE p.student_id = ?
        ORDER BY p.registration_date DESC
        ''', (student_id,))

        history = cursor.fetchall()

        print("\n=== My Competition History ===")

        if not history:
            print("You have not participated in any competitions yet.")
            return

        print(f"Total competitions entered: {len(history)}")
        for h in history:
            print(f"\n{h[0]} ({h[1]}) - {h[2]}")
            print(f"   Club: {h[6] or '-'}")
            print(f"   Registered: {h[3]}")
            score = h[4] if h[4] is not None else 'not scored'
            rank = h[5] if h[5] is not None else 'unranked'
            print(f"   Score: {score}   Rank: {rank}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def create_new_competition(student_id, cursor, conn):
    """Create a new competition (admin function)"""
    try:
        print("\n=== Create Competition ===")

        competition_name = input("Competition name: ").strip()
        if not competition_name:
            print("Competition name cannot be empty.")
            return

        # Check for duplicate name
        cursor.execute(
            'SELECT COUNT(*) FROM club_competitions WHERE competition_name = ?',
            (competition_name,)
        )
        if cursor.fetchone()[0] > 0:
            print("A competition with this name already exists.")
            return

        description = input("Description: ").strip()
        competition_type = input("Competition type (e.g., Sports, Academic, Arts): ").strip()
        if not competition_type:
            competition_type = "General"

        start_date = input("Start date (YYYY-MM-DD): ").strip()
        end_date = input("End date (YYYY-MM-DD): ").strip()
        registration_deadline = input("Registration deadline (YYYY-MM-DD): ").strip()

        max_participants = input("Max participants per club [5]: ").strip()
        if max_participants:
            try:
                max_participants = int(max_participants)
                if max_participants < 1:
                    print("Max participants must be at least 1.")
                    return
            except ValueError:
                print("Invalid number.")
                return
        else:
            max_participants = 5

        prizes = input("Prizes (optional): ").strip()

        cursor.execute('''
        INSERT INTO club_competitions (
            competition_name, description, competition_type, start_date, end_date,
            registration_deadline, max_participants_per_club, prizes, status, organizer_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (competition_name, description, competition_type, start_date, end_date,
              registration_deadline, max_participants, prizes, 'registration_open', student_id))

        conn.commit()
        competition_id = cursor.lastrowid

        print(f"\nCompetition '{competition_name}' created successfully! ID: {competition_id}")
        print("Status set to 'registration_open'.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def manage_competition_admin(cursor, conn):
    """Admin competition management"""
    try:
        while True:
            print("\n=== Manage Competition ===")
            print("1. List all competitions")
            print("2. Change competition status")
            print("3. View registrations for a competition")
            print("4. Delete a competition")
            print("5. Return to competitions menu")

            choice = input("Choose option: ").strip()

            if choice == '1':
                cursor.execute('''
                SELECT c.competition_id, c.competition_name, c.competition_type,
                       c.status, COUNT(p.participant_id) as participants
                FROM club_competitions c
                LEFT JOIN competition_participants p ON c.competition_id = p.competition_id
                GROUP BY c.competition_id, c.competition_name, c.competition_type, c.status
                ORDER BY c.competition_id
                ''')
                comps = cursor.fetchall()

                if not comps:
                    print("No competitions yet.")
                    continue

                print(f"\n{'ID':<6} {'Name':<28} {'Type':<15} {'Status':<18} {'Parts':<6}")
                print("-" * 75)
                for c in comps:
                    print(f"{c[0]:<6} {c[1][:28]:<28} {(c[2] or '')[:15]:<15} "
                          f"{(c[3] or '')[:18]:<18} {c[4]:<6}")

            elif choice == '2':
                comp_id = input("Enter competition ID: ").strip()
                if not comp_id.isdigit():
                    print("Invalid competition ID.")
                    continue

                cursor.execute(
                    'SELECT competition_name, status FROM club_competitions WHERE competition_id = ?',
                    (comp_id,)
                )
                comp = cursor.fetchone()
                if not comp:
                    print("Competition not found.")
                    continue

                print(f"Current status of '{comp[0]}': {comp[1]}")
                print("Options: registration_open, active, in_progress, completed, cancelled")
                new_status = input("New status: ").strip()
                if new_status not in ('registration_open', 'active', 'in_progress',
                                      'completed', 'cancelled'):
                    print("Invalid status.")
                    continue

                cursor.execute(
                    'UPDATE club_competitions SET status = ? WHERE competition_id = ?',
                    (new_status, comp_id)
                )
                conn.commit()
                print("Status updated successfully!")

            elif choice == '3':
                comp_id = input("Enter competition ID: ").strip()
                if not comp_id.isdigit():
                    print("Invalid competition ID.")
                    continue

                cursor.execute('''
                SELECT s.first_name, s.last_name, cl.club_name, p.registration_date,
                       p.score, p.rank_position
                FROM competition_participants p
                LEFT JOIN students s ON p.student_id = s.student_id
                LEFT JOIN student_clubs cl ON p.club_id = cl.club_id
                WHERE p.competition_id = ?
                ORDER BY cl.club_name, s.last_name
                ''', (comp_id,))
                regs = cursor.fetchall()

                if not regs:
                    print("No registrations for this competition yet.")
                    continue

                print(f"\n{'Participant':<28} {'Club':<22} {'Score':<8} {'Rank':<6}")
                print("-" * 66)
                for r in regs:
                    name = f"{r[0] or ''} {r[1] or ''}".strip() or 'Unknown'
                    score = r[4] if r[4] is not None else '-'
                    rank = r[5] if r[5] is not None else '-'
                    print(f"{name[:28]:<28} {(r[2] or '-')[:22]:<22} {str(score):<8} {str(rank):<6}")

            elif choice == '4':
                comp_id = input("Enter competition ID to delete: ").strip()
                if not comp_id.isdigit():
                    print("Invalid competition ID.")
                    continue

                cursor.execute(
                    'SELECT competition_name FROM club_competitions WHERE competition_id = ?',
                    (comp_id,)
                )
                comp = cursor.fetchone()
                if not comp:
                    print("Competition not found.")
                    continue

                confirm = input(f"Delete '{comp[0]}' and all its registrations? (y/n): ").strip().lower()
                if confirm == 'y':
                    cursor.execute(
                        'DELETE FROM competition_participants WHERE competition_id = ?',
                        (comp_id,)
                    )
                    cursor.execute(
                        'DELETE FROM club_competitions WHERE competition_id = ?',
                        (comp_id,)
                    )
                    conn.commit()
                    print("Competition deleted successfully!")

            elif choice == '5':
                break

            else:
                print("Invalid choice.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def update_competition_scores(cursor, conn):
    """Update competition scores and recompute rankings"""
    try:
        print("\n=== Update Scores ===")

        cursor.execute('''
        SELECT competition_id, competition_name, status
        FROM club_competitions
        WHERE status IN ('active', 'in_progress', 'completed')
        ORDER BY competition_id
        ''')
        comps = cursor.fetchall()

        if not comps:
            print("No competitions available for scoring yet.")
            return

        print("Competitions available for scoring:")
        for i, c in enumerate(comps):
            print(f"{i+1}. {c[1]} ({c[2]})")

        comp_choice = input("Select competition (enter number): ").strip()
        if not comp_choice.isdigit() or int(comp_choice) < 1 or int(comp_choice) > len(comps):
            print("Invalid selection.")
            return

        competition_id = comps[int(comp_choice)-1][0]

        cursor.execute('''
        SELECT p.participant_id, s.first_name, s.last_name, cl.club_name, p.score
        FROM competition_participants p
        LEFT JOIN students s ON p.student_id = s.student_id
        LEFT JOIN student_clubs cl ON p.club_id = cl.club_id
        WHERE p.competition_id = ?
        ORDER BY cl.club_name, s.last_name
        ''', (competition_id,))
        participants = cursor.fetchall()

        if not participants:
            print("No participants registered for this competition yet.")
            return

        print("\nEnter scores (press Enter to skip a participant):")
        for p in participants:
            name = f"{p[1] or ''} {p[2] or ''}".strip() or 'Unknown'
            current = p[4] if p[4] is not None else 'none'
            raw = input(f"  {name} ({p[3] or '-'}) [current: {current}]: ").strip()
            if not raw:
                continue
            try:
                score = float(raw)
            except ValueError:
                print("   Invalid score, skipping.")
                continue
            cursor.execute(
                'UPDATE competition_participants SET score = ? WHERE participant_id = ?',
                (score, p[0])
            )

        conn.commit()

        # Recompute rank positions based on score (highest score = rank 1)
        cursor.execute('''
        SELECT participant_id, score
        FROM competition_participants
        WHERE competition_id = ? AND score IS NOT NULL
        ORDER BY score DESC
        ''', (competition_id,))
        ranked = cursor.fetchall()

        for rank, row in enumerate(ranked, start=1):
            cursor.execute(
                'UPDATE competition_participants SET rank_position = ? WHERE participant_id = ?',
                (rank, row[0])
            )

        conn.commit()
        print(f"\nScores saved and {len(ranked)} participant(s) ranked.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def generate_competition_reports(cursor):
    """Generate competition reports"""
    try:
        print("\n=== Competition Reports ===")

        cursor.execute('SELECT COUNT(*) FROM club_competitions')
        total_comps = cursor.fetchone()[0]

        if total_comps == 0:
            print("No competitions recorded yet.")
            return

        cursor.execute('''
        SELECT status, COUNT(*) FROM club_competitions
        GROUP BY status ORDER BY COUNT(*) DESC
        ''')
        by_status = cursor.fetchall()

        cursor.execute('SELECT COUNT(*) FROM competition_participants')
        total_participants = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(DISTINCT club_id) FROM competition_participants')
        clubs_involved = cursor.fetchone()[0]

        print(f"Total Competitions: {total_comps}")
        print(f"Total Participant Registrations: {total_participants}")
        print(f"Distinct Clubs Involved: {clubs_involved}")

        print("\nCompetitions by Status:")
        for s in by_status:
            print(f"   {s[0] or 'unknown':<20} {s[1]}")

        # Competitions by type
        cursor.execute('''
        SELECT competition_type, COUNT(*) FROM club_competitions
        GROUP BY competition_type ORDER BY COUNT(*) DESC
        ''')
        by_type = cursor.fetchall()

        if by_type:
            print("\nCompetitions by Type:")
            for t in by_type:
                print(f"   {(t[0] or 'unknown'):<20} {t[1]}")

        # Most participated competitions
        cursor.execute('''
        SELECT c.competition_name, COUNT(p.participant_id) as participants
        FROM club_competitions c
        LEFT JOIN competition_participants p ON c.competition_id = p.competition_id
        GROUP BY c.competition_id, c.competition_name
        HAVING participants > 0
        ORDER BY participants DESC
        LIMIT 10
        ''')
        popular = cursor.fetchall()

        if popular:
            print("\nMost Participated Competitions:")
            print(f"   {'Competition':<35} {'Participants':<12}")
            print("   " + "-" * 47)
            for pc in popular:
                print(f"   {pc[0][:35]:<35} {pc[1]:<12}")
        else:
            print("\nNo participant registrations recorded yet.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


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
        # Auto-award is best-effort, but a failure means the student's points
        # were not recorded — surface it for debugging rather than hiding it.
        logger.warning(
            "Failed to auto-award %s points to student_id=%s (%s)",
            points, student_id, activity_type, exc_info=True)
