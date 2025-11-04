from __future__ import annotations

from datetime import datetime
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.core.services.student_union_misc.union_context import auto_award_points

def view_active_competitions(cursor):
    """View currently active competitions"""
    try:
        cursor.execute('''
        SELECT c.competition_id, c.competition_name, c.competition_type, 
               c.start_date, c.end_date, c.registration_deadline,
               c.max_participants_per_club, c.status,
               COUNT(DISTINCT cp.club_id) as registered_clubs
        FROM club_competitions c
        LEFT JOIN competition_participants cp ON c.competition_id = cp.competition_id
        WHERE c.status IN ('upcoming', 'active', 'registration_open')
        GROUP BY c.competition_id, c.competition_name, c.competition_type, 
                 c.start_date, c.end_date, c.registration_deadline,
                 c.max_participants_per_club, c.status
        ORDER BY c.start_date
        ''')

        competitions = cursor.fetchall()

        if not competitions:
            print("No active competitions found.")
            return

        print(f"\nActive Competitions:")
        print("=" * 50)

        for comp in competitions:
            print(f"\nID: {comp[0]}")
            print(f"Name: {comp[1]}")
            print(f"Type: {comp[2]}")
            print(f"Start Date: {comp[3]}")
            print(f"End Date: {comp[4]}")
            print(f"Registration Deadline: {comp[5]}")
            print(f"Max Participants per Club: {comp[6]}")
            print(f"Status: {comp[7]}")
            print(f"Registered Clubs: {comp[8]}")

            # Get detailed description
            cursor.execute('SELECT description, prizes FROM club_competitions WHERE competition_id = ?', (comp[0],))
            details = cursor.fetchone()
            if details[0]:
                print(f"Description: {details[0]}")
            if details[1]:
                print(f"Prizes: {details[1]}")

            print("-" * 50)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def view_competition_results(cursor):
    """View results of completed competitions"""
    try:
        cursor.execute('''
        SELECT competition_id, competition_name, competition_type, end_date, status
        FROM club_competitions
        WHERE status IN ('completed', 'active')
        ORDER BY end_date DESC
        ''')

        competitions = cursor.fetchall()

        if not competitions:
            print("No competitions with results available.")
            return

        print("\nCompetitions with results:")
        for i, comp in enumerate(competitions):
            status_text = "Completed" if comp[4] == 'completed' else "Ongoing"
            print(f"{i+1}. {comp[1]} ({comp[2]}) - {comp[3]} [{status_text}]")

        choice = input("Select competition to view results (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(competitions):
            print("Invalid selection.")
            return

        selected_comp = competitions[int(choice)-1]
        competition_id = selected_comp[0]
        competition_name = selected_comp[1]

        # Get competition results
        cursor.execute('''
        SELECT c.club_name, cp.score, cp.rank_position,
               COUNT(cp.student_id) as participant_count
        FROM competition_participants cp
        JOIN student_clubs c ON cp.club_id = c.club_id
        WHERE cp.competition_id = ?
        GROUP BY cp.club_id, c.club_name, cp.score, cp.rank_position
        HAVING COUNT(cp.student_id) > 0
        ORDER BY cp.rank_position, cp.score DESC
        ''')

        results = cursor.fetchall()

        if not results:
            print(f"No results available for {competition_name}.")
            return

        print(f"\nResults for {competition_name}:")
        print("=" * 50)
        print(f"{'Rank':<6} {'Club':<25} {'Score':<10} {'Participants':<12}")
        print("-" * 55)

        for result in results:
            rank = result[2] if result[2] else "TBD"
            score = f"{result[1]:.1f}" if result[1] else "0.0"
            print(f"{rank:<6} {result[0][:25]:<25} {score:<10} {result[3]:<12}")

        # Show individual participants if requested
        show_participants = input("\nShow individual participants? (y/n): ").strip().lower()
        if show_participants == 'y':
            cursor.execute('''
            SELECT s.first_name, s.last_name, c.club_name, cp.score
            FROM competition_participants cp
            JOIN students s ON cp.student_id = s.student_id
            JOIN student_clubs c ON cp.club_id = c.club_id
            WHERE cp.competition_id = ?
            ORDER BY c.club_name, s.last_name, s.first_name
            ''', (competition_id,))

            participants = cursor.fetchall()

            print(f"\nAll Participants:")
            print(f"{'Name':<25} {'Club':<25} {'Individual Score':<15}")
            print("-" * 70)

            for participant in participants:
                score = f"{participant[3]:.1f}" if participant[3] else "N/A"
                print(f"{participant[0]} {participant[1]:<25} {participant[2][:25]:<25} {score:<15}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def view_my_competition_history(student_id, cursor):
    """View student's competition participation history"""
    try:
        cursor.execute('''
        SELECT cc.competition_name, cc.competition_type, cc.start_date, cc.end_date,
               sc.club_name, cp.score, cp.rank_position, cc.status
        FROM competition_participants cp
        JOIN club_competitions cc ON cp.competition_id = cc.competition_id
        JOIN student_clubs sc ON cp.club_id = sc.club_id
        WHERE cp.student_id = ?
        ORDER BY cc.start_date DESC
        ''', (student_id,))

        competitions = cursor.fetchall()

        if not competitions:
            print("You have no competition participation history.")
            return

        print(f"\nYour Competition History:")
        print("=" * 50)
        print(f"{'Competition':<25} {'Type':<15} {'Club':<20} {'Date':<12} {'Score':<8} {'Rank':<6}")
        print("-" * 90)

        for comp in competitions:
            score = f"{comp[5]:.1f}" if comp[5] else "N/A"
            rank = str(comp[6]) if comp[6] else "TBD"
            print(f"{comp[0][:25]:<25} {comp[1]:<15} {comp[4][:20]:<20} {comp[2]:<12} {score:<8} {rank:<6}")

        # Show statistics
        total_competitions = len(competitions)
        completed_competitions = len([c for c in competitions if c[7] == 'completed'])
        wins = len([c for c in competitions if c[6] == 1])
        top_3_finishes = len([c for c in competitions if c[6] and c[6] <= 3])

        print(f"\nYour Competition Statistics:")
        print(f"Total Competitions: {total_competitions}")
        print(f"Completed Competitions: {completed_competitions}")
        print(f"First Place Finishes: {wins}")
        print(f"Top 3 Finishes: {top_3_finishes}")

        if completed_competitions > 0:
            average_rank = sum(c[6] for c in competitions if c[6]) / len([c for c in competitions if c[6]])
            print(f"Average Rank: {average_rank:.1f}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def create_new_competition(organizer_id, cursor, conn):
    """Create a new inter-club competition (admin function)"""
    try:
        print(f"\nCreate New Competition")
        print("=" * 25)

        competition_name = input("Competition name: ").strip()
        if not competition_name:
            print("Competition name cannot be empty.")
            return

        description = input("Competition description: ").strip()

        competition_types = ["Academic", "Sports", "Cultural", "Innovation", "Community Service", "Other"]
        print(f"\nCompetition types:")
        for i, comp_type in enumerate(competition_types):
            print(f"{i+1}. {comp_type}")

        type_choice = input("Select competition type (enter number): ").strip()
        if type_choice.isdigit() and 1 <= int(type_choice) <= len(competition_types):
            competition_type = competition_types[int(type_choice)-1]
        else:
            competition_type = input("Enter custom competition type: ").strip()

        start_date = input("Start date (YYYY-MM-DD): ").strip()
        if not start_date:
            print("Start date cannot be empty.")
            return

        try:
            datetime.strptime(start_date, '%Y-%m-%d')
        except ValueError:
            print("Invalid date format.")
            return

        end_date = input("End date (YYYY-MM-DD): ").strip()
        if not end_date:
            print("End date cannot be empty.")
            return

        try:
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            print("Invalid date format.")
            return

        registration_deadline = input("Registration deadline (YYYY-MM-DD): ").strip()
        if not registration_deadline:
            print("Registration deadline cannot be empty.")
            return

        try:
            datetime.strptime(registration_deadline, '%Y-%m-%d')
        except ValueError:
            print("Invalid date format.")
            return

        try:
            max_participants = int(input("Maximum participants per club: ").strip())
            if max_participants <= 0:
                print("Maximum participants must be positive.")
                return
        except ValueError:
            print("Invalid number format.")
            return

        prizes = input("Prizes description (optional): ").strip()

        # Determine initial status
        current_date = datetime.now().strftime('%Y-%m-%d')
        if current_date < registration_deadline:
            status = 'upcoming'
        elif current_date < start_date:
            status = 'registration_open'
        elif current_date <= end_date:
            status = 'active'
        else:
            status = 'completed'

        cursor.execute('''
        INSERT INTO club_competitions (
            competition_name, description, competition_type, start_date, end_date,
            registration_deadline, max_participants_per_club, prizes, status, organizer_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            competition_name, description, competition_type, start_date, end_date,
            registration_deadline, max_participants, prizes, status, organizer_id
        ))

        conn.commit()
        competition_id = cursor.lastrowid

        print(f"Competition '{competition_name}' created successfully!")
        print(f"Competition ID: {competition_id}")
        print(f"Status: {status}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def update_competition_scores(cursor, conn):
    """Update scores for competition participants (admin function)"""
    try:
        # Show active competitions
        cursor.execute('''
        SELECT competition_id, competition_name, status
        FROM club_competitions
        WHERE status IN ('active', 'completed')
        ORDER BY competition_name
        ''')

        competitions = cursor.fetchall()

        if not competitions:
            print("No active competitions found.")
            return

        print("Competitions with scoring:")
        for i, comp in enumerate(competitions):
            print(f"{i+1}. {comp[1]} ({comp[2]})")

        choice = input("Select competition (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(competitions):
            print("Invalid selection.")
            return

        selected_comp = competitions[int(choice)-1]
        competition_id = selected_comp[0]
        competition_name = selected_comp[1]

        # Show participants
        cursor.execute('''
        SELECT cp.student_id, s.first_name, s.last_name, sc.club_name, cp.score
        FROM competition_participants cp
        JOIN students s ON cp.student_id = s.student_id
        JOIN student_clubs sc ON cp.club_id = sc.club_id
        WHERE cp.competition_id = ?
        ORDER BY sc.club_name, s.last_name, s.first_name
        ''', (competition_id,))

        participants = cursor.fetchall()

        if not participants:
            print(f"No participants found for {competition_name}.")
            return

        print(f"\nParticipants in {competition_name}:")
        print(f"{'#':<3} {'Name':<25} {'Club':<25} {'Current Score':<12}")
        print("-" * 70)

        for i, participant in enumerate(participants):
            score = f"{participant[4]:.1f}" if participant[4] else "No score"
            print(f"{i+1:<3} {participant[1]} {participant[2]:<25} {participant[3][:25]:<25} {score:<12}")

        print("\nScoring options:")
        print("1. Update individual scores")
        print("2. Bulk score update")
        print("3. Calculate rankings")
        print("4. Return to previous menu")

        score_choice = input("Choose option: ").strip()

        if score_choice == '1':
            # Update individual scores
            participant_num = input("Enter participant number to update score: ").strip()
            if not participant_num.isdigit() or int(participant_num) < 1 or int(participant_num) > len(participants):
                print("Invalid participant number.")
                return

            selected_participant = participants[int(participant_num)-1]

            try:
                new_score = float(input(f"Enter new score for {selected_participant[1]} {selected_participant[2]}: ").strip())
            except ValueError:
                print("Invalid score format.")
                return

            cursor.execute('''
            UPDATE competition_participants 
            SET score = ?
            WHERE competition_id = ? AND student_id = ?
            ''', (new_score, competition_id, selected_participant[0]))

            conn.commit()
            print(f"Score updated for {selected_participant[1]} {selected_participant[2]}: {new_score}")

        elif score_choice == '2':
            # Bulk score update
            print("Enter scores for all participants (in order shown above):")
            print("Format: score1,score2,score3... or press Enter to skip")

            bulk_scores = input("Scores: ").strip()
            if not bulk_scores:
                print("No scores entered.")
                return

            try:
                scores = [float(score.strip()) for score in bulk_scores.split(',')]

                if len(scores) != len(participants):
                    print(f"Number of scores ({len(scores)}) doesn't match number of participants ({len(participants)}).")
                    return

                for i, score in enumerate(scores):
                    cursor.execute('''
                    UPDATE competition_participants 
                    SET score = ?
                    WHERE competition_id = ? AND student_id = ?
                    ''', (score, competition_id, participants[i][0]))

                conn.commit()
                print(f"Updated scores for {len(participants)} participants.")

            except ValueError:
                print("Invalid score format. Use numbers separated by commas.")
                return

        elif score_choice == '3':
            # Calculate rankings
            cursor.execute('''
            SELECT cp.student_id, cp.score, cp.club_id
            FROM competition_participants cp
            WHERE cp.competition_id = ? AND cp.score IS NOT NULL
            ORDER BY cp.score DESC
            ''', (competition_id,))

            scored_participants = cursor.fetchall()

            if not scored_participants:
                print("No participants have scores yet.")
                return

            # Calculate individual rankings
            for rank, participant in enumerate(scored_participants, 1):
                cursor.execute('''
                UPDATE competition_participants 
                SET rank_position = ?
                WHERE competition_id = ? AND student_id = ?
                ''', (rank, competition_id, participant[0]))

            conn.commit()
            print(f"Rankings calculated for {len(scored_participants)} participants.")

            # Award points based on rankings
            for rank, participant in enumerate(scored_participants, 1):
                points = max(50 - (rank-1) * 5, 10)  # 50 points for 1st, decreasing by 5 per rank, minimum 10
                auto_award_points(participant[0], "Competition Performance", points,
                                f"Placed #{rank} in {competition_name}", cursor, conn)

        elif score_choice == '4':
            return

        else:
            print("Invalid choice.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
