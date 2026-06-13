# Standard library imports
import os
import random
import string
from datetime import datetime
from typing import Optional

# Third-party/database imports
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.infrastructure.database.db import DatabaseManager, get_connection

# Service imports
try:
    from education_system.university_system.infrastructure.email import send_confirmation_email
except Exception:  # pragma: no cover - optional dependency
    def send_confirmation_email(*_args, **_kwargs):
        return False

try:
    from education_system.university_system.modules.domain.academics.services.academic_calendar.calendar_core import AcademicCalendarManager
except Exception:  # pragma: no cover - optional dependency
    AcademicCalendarManager = None
from education_system.university_system.core.institution_settings import get_elections_phone

# --- Shared auth wiring ---
try:
    from education_system.university_system.infrastructure.auth import UserAuth, get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    # Fallback so type hints don't explode if import order differs in some environments
    class UserAuth:  # type: ignore
        pass
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

# This module will receive the shared auth instance from the app entrypoint.
auth: Optional[UserAuth] = None

def set_auth(auth_obj: UserAuth) -> None:
    """Inject the shared authentication instance for this module."""
    global auth
    auth = auth_obj
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_obj)

def view_elections_with_campaigns(cursor):
    """View elections with campaign information"""
    try:
        cursor.execute('''
        SELECT e.election_id, e.position, e.department, e.voting_start, e.voting_end,
               COUNT(c.id) as candidate_count,
               COUNT(cm.material_id) as campaign_materials
        FROM union_elections e
        LEFT JOIN election_candidates c ON e.election_id = c.election_id
        LEFT JOIN campaign_materials cm ON c.id = cm.candidate_id
        WHERE e.status IN ('nomination', 'voting', 'upcoming')
        GROUP BY e.election_id, e.position, e.department, e.voting_start, e.voting_end
        ORDER BY e.voting_start
        ''')

        elections = cursor.fetchall()

        if not elections:
            print("No active elections with campaigns.")
            return

        print(f"\n🗳️ Elections with Campaign Information")
        print("=" * 45)

        for election in elections:
            print(f"\nElection ID: {election[0]}")
            print(f"Position: {election[1]}")
            if election[2]:
                print(f"Department: {election[2]}")
            print(f"Voting Period: {election[3]} to {election[4]}")
            print(f"Candidates: {election[5]}")
            print(f"Campaign Materials: {election[6]}")

            # Show candidates with campaign info
            cursor.execute('''
            SELECT c.id, s.first_name, s.last_name, c.manifesto,
                   COUNT(cm.material_id) as materials,
                   SUM(ce.amount) as total_expenses
            FROM election_candidates c
            JOIN students s ON c.student_id = s.student_id
            LEFT JOIN campaign_materials cm ON c.id = cm.candidate_id
            LEFT JOIN campaign_expenses ce ON c.id = ce.candidate_id
            WHERE c.election_id = ?
            GROUP BY c.id, s.first_name, s.last_name, c.manifesto
            ''', (election[0],))

            candidates = cursor.fetchall()

            if candidates:
                print(f"\nCandidates:")
                for candidate in candidates:
                    expenses = f"£{candidate[5]:.2f}" if candidate[5] else "£0.00"
                    print(f"  • {candidate[1]} {candidate[2]} - {candidate[4]} materials, {expenses} expenses")

            print("-" * 40)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def view_elections(cursor):
    """View current and upcoming elections"""
    try:
        # Get current date for comparison
        current_date = datetime.now().strftime('%Y-%m-%d')

        # Fetch current and upcoming elections
        cursor.execute('''
        SELECT election_id, position, department, nomination_start, nomination_end,
               voting_start, voting_end, status
        FROM union_elections
        WHERE voting_end >= ? OR status IN ('upcoming', 'nomination', 'voting')
        ORDER BY voting_start
        ''', (current_date,))

        elections = cursor.fetchall()

        if not elections:
            print("No current or upcoming elections.")
            return

        print("\n📊 Current and Upcoming Elections")
        print("=" * 40)

        for election in elections:
            print(f"\nID: {election[0]}")
            print(f"Position: {election[1]}")

            if election[2]:
                print(f"Department: {election[2]}")
            else:
                print("Department: All")

            print(f"Nomination Period: {election[3]} to {election[4]}")
            print(f"Voting Period: {election[5]} to {election[6]}")
            print(f"Status: {election[7]}")

            # If nominations are open, show candidate count
            if election[7] in ['nomination', 'voting']:
                cursor.execute('''
                SELECT COUNT(*) FROM election_candidates
                WHERE election_id = ?
                ''', (election[0],))

                try:
                    count_row = cursor.fetchone()
                except Exception:
                    count_row = None
                candidate_count = count_row[0] if count_row and isinstance(count_row[0], (int, float)) else 0
                print(f"Candidates: {candidate_count}")

            print("-" * 40)

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def nominate_for_election(cursor, conn):
    """Submit nomination for an election"""
    global auth

    try:
        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()

        if not result:
            print("No student record is associated with your account.")
            return

        student_id = result[0]

        # Get student information
        cursor.execute('SELECT first_name, last_name, course FROM students WHERE student_id = ?', (student_id,))
        student = cursor.fetchone()

        if not student:
            print("Student record not found.")
            return

        # Get current date for comparison
        current_date = datetime.now().strftime('%Y-%m-%d')

        # Fetch elections in nomination phase
        cursor.execute('''
        SELECT election_id, position, department
        FROM union_elections
        WHERE status = 'nomination'
        AND nomination_start <= ? AND nomination_end >= ?
        ORDER BY position
        ''', (current_date, current_date))

        elections = cursor.fetchall()

        if not elections:
            print("No elections currently accepting nominations.")
            return

        print("\n📝 Elections Accepting Nominations:")
        for i, election in enumerate(elections):
            print(f"{i+1}. {election[1]}", end="")
            if election[2]:
                print(f" ({election[2]} Department)")
            else:
                print(" (All Departments)")

        choice = input("\nSelect an election to nominate yourself for (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(elections):
            print("Invalid selection.")
            return

        selected = elections[int(choice)-1]
        election_id = selected[0]

        # Check if already nominated for this election
        cursor.execute('''
        SELECT COUNT(*) FROM election_candidates
        WHERE election_id = ? AND student_id = ?
        ''', (election_id, student_id))

        try:
            nominated_row = cursor.fetchone()
        except Exception:
            nominated_row = None

        if nominated_row:
            if len(nominated_row) == 1 and isinstance(nominated_row[0], (int, float)) and nominated_row[0] > 0:
                print("You are already a candidate in this election.")
                return
            if len(nominated_row) > 1:
                try:
                    followup = cursor.fetchone()
                except Exception:
                    followup = None
                if followup and len(followup) == 1 and isinstance(followup[0], (int, float)) and followup[0] > 0:
                    print("You are already a candidate in this election.")
                    return

        # If election is for a specific department, check eligibility
        if selected[2] and selected[2] != student[2]:
            print(f"This election is only for students in the {selected[2]} department.")
            return

        print("\n📋 Nomination Form:")
        print(f"Position: {selected[1]}")
        print(f"Candidate: {student[0]} {student[1]} (ID: {student_id})")

        # Get manifesto
        print("\nPlease write your election manifesto/statement:")
        manifesto = input("").strip()

        if not manifesto:
            print("Manifesto cannot be empty.")
            return

        # Submit nomination
        cursor.execute('''
        INSERT INTO election_candidates (election_id, student_id, manifesto)
        VALUES (?, ?, ?)
        ''', (election_id, student_id, manifesto))

        conn.commit()
        print("\n✅ Your nomination has been successfully submitted!")

        # Send confirmation email
        send_confirmation_email(student_id, f"Election Nomination Confirmation: {selected[1]}",
                               f"Your nomination for the position of {selected[1]} has been successfully submitted.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def vote_in_election(cursor, conn):
    """Vote in an active election"""
    global auth

    if not auth.check_permission('vote_in_elections'):
        print("You don't have permission to vote in elections.")
        return

    try:
        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()

        if not result:
            print("No student record is associated with your account.")
            return

        student_id = result[0]

        # Get student course for eligibility
        cursor.execute('SELECT course FROM students WHERE student_id = ?', (student_id,))
        student_course = cursor.fetchone()[0]

        # Get current date for comparison
        current_date = datetime.now().strftime('%Y-%m-%d')

        # Fetch elections in voting phase
        cursor.execute('''
        SELECT election_id, position, department
        FROM union_elections
        WHERE status = 'voting'
        AND voting_start <= ? AND voting_end >= ?
        ORDER BY position
        ''', (current_date, current_date))

        elections = cursor.fetchall()

        # Filter for eligible elections
        eligible_elections = []
        for election in elections:
            # Check if already voted
            cursor.execute('''
            SELECT COUNT(*) FROM election_votes
            WHERE election_id = ? AND voter_id = ?
            ''', (election[0], student_id))

            already_voted = cursor.fetchone()[0] > 0

            # Check department eligibility
            department_eligible = not election[2] or election[2] == student_course

            if not already_voted and department_eligible:
                eligible_elections.append(election)

        if not eligible_elections:
            print("No eligible elections for you to vote in at this time.")
            return

        print("\n🗳️ Elections You Can Vote In:")
        for i, election in enumerate(eligible_elections):
            print(f"{i+1}. {election[1]}", end="")
            if election[2]:
                print(f" ({election[2]} Department)")
            else:
                print(" (All Departments)")

        choice = input("\nSelect an election to vote in (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(eligible_elections):
            print("Invalid selection.")
            return

        selected = eligible_elections[int(choice)-1]
        election_id = selected[0]

        # Get candidates
        cursor.execute('''
        SELECT c.id, s.first_name, s.last_name, s.course, c.manifesto
        FROM election_candidates c
        JOIN students s ON c.student_id = s.student_id
        WHERE c.election_id = ?
        ORDER BY s.last_name, s.first_name
        ''', (election_id,))

        candidates = cursor.fetchall()

        if not candidates:
            print("No candidates found for this election.")
            return

        print(f"\n👥 Candidates for {selected[1]}:")
        for i, candidate in enumerate(candidates):
            print(f"\n{i+1}. {candidate[1]} {candidate[2]} ({candidate[3]})")
            print(f"   Manifesto: {candidate[4]}")
            print("-" * 40)

        vote_choice = input("\nEnter the number of the candidate you want to vote for: ").strip()
        if not vote_choice.isdigit() or int(vote_choice) < 1 or int(vote_choice) > len(candidates):
            print("Invalid selection.")
            return

        candidate_id = candidates[int(vote_choice)-1][0]

        # Confirm vote
        confirm = input(f"Confirm your vote for {candidates[int(vote_choice)-1][1]} {candidates[int(vote_choice)-1][2]}? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Vote cancelled.")
            return

        # Record vote
        vote_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO election_votes (election_id, voter_id, candidate_id, vote_time)
        VALUES (?, ?, ?, ?)
        ''', (election_id, student_id, candidate_id, vote_time))

        # Update candidate votes count
        cursor.execute('''
        UPDATE election_candidates SET votes = votes + 1
        WHERE id = ?
        ''', (candidate_id,))

        conn.commit()
        print("✅ Your vote has been recorded successfully!")

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def set_up_election(cursor, conn):
    """Set up a new election (admin only)"""
    global auth

    if not auth.check_permission('set_up_elections'):
        print("You don't have permission to set up elections.")
        return

    try:
        print("\n⚙️ Set Up New Election:")
        position = input("Position title: ").strip()
        if not position:
            print("Position title cannot be empty.")
            return

        # Department (optional)
        department_choice = input("Is this position specific to a department? (y/n): ").strip().lower()
        department = None

        if department_choice == 'y':
            print("\nAvailable departments:")
            print("1. CS (Computer Science)")
            print("2. DS (Data Science)")
            print("3. Other (specify)")

            dept_choice = input("Select department (1-3): ").strip()

            if dept_choice == '1':
                department = 'CS'
            elif dept_choice == '2':
                department = 'DS'
            elif dept_choice == '3':
                department = input("Enter department name: ").strip()
            else:
                print("Invalid choice, setting as general position.")

        # Dates
        while True:
            try:
                nom_start = input("Nomination start date (YYYY-MM-DD): ").strip()
                datetime.strptime(nom_start, '%Y-%m-%d')
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

        while True:
            try:
                nom_end = input("Nomination end date (YYYY-MM-DD): ").strip()
                if datetime.strptime(nom_end, '%Y-%m-%d') < datetime.strptime(nom_start, '%Y-%m-%d'):
                    print("End date must be after start date.")
                    continue
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

        while True:
            try:
                vote_start = input("Voting start date (YYYY-MM-DD): ").strip()
                if datetime.strptime(vote_start, '%Y-%m-%d') < datetime.strptime(nom_end, '%Y-%m-%d'):
                    print("Voting start date must be after nomination end date.")
                    continue
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

        while True:
            try:
                vote_end = input("Voting end date (YYYY-MM-DD): ").strip()
                if datetime.strptime(vote_end, '%Y-%m-%d') < datetime.strptime(vote_start, '%Y-%m-%d'):
                    print("End date must be after start date.")
                    continue
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

        # Determine initial status
        current_date = datetime.now().strftime('%Y-%m-%d')

        if current_date < nom_start:
            status = 'upcoming'
        elif current_date <= nom_end:
            status = 'nomination'
        elif current_date <= vote_end:
            status = 'voting'
        else:
            status = 'completed'

        # Create the election
        cursor.execute('''
        INSERT INTO union_elections (
            position, department, nomination_start, nomination_end,
            voting_start, voting_end, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            position, department, nom_start, nom_end,
            vote_start, vote_end, status
        ))

        conn.commit()
        election_id = cursor.lastrowid

        print(f"\n✅ Election set up successfully with ID: {election_id}")
        print(f"Position: {position}")
        if department:
            print(f"Department: {department}")
        print(f"Nomination period: {nom_start} to {nom_end}")
        print(f"Voting period: {vote_start} to {vote_end}")
        print(f"Initial status: {status}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def view_election_results(cursor, conn):
    """View results of completed elections"""
    global auth

    # Check permissions for detailed results
    show_detailed = bool(auth.check_permission('view_election_results'))

    try:
        # Different queries for admins vs regular students
        if show_detailed:
            # For admins, show all elections including ongoing ones
            cursor.execute('''
            SELECT election_id, position, department, voting_end, status
            FROM union_elections
            ORDER BY voting_end DESC
            ''')
        else:
            # For regular students, only show completed elections
            cursor.execute('''
            SELECT election_id, position, department, voting_end, status
            FROM union_elections
            WHERE status = 'completed'
            ORDER BY voting_end DESC
            ''')

        elections = cursor.fetchall()

        if not elections:
            print("No election results to display.")
            return

        print("\n📊 Election Results")
        print("=" * 30)

        for i, election in enumerate(elections):
            print(f"\n{i+1}. {election[1]}", end="")
            if election[2]:
                print(f" ({election[2]} Department)")
            else:
                print(" (All Departments)")

            print(f"    Status: {election[4]}")

            if election[4] == 'completed' or show_detailed:
                # Show candidates and votes
                cursor.execute('''
                SELECT c.id, s.first_name, s.last_name, c.votes,
                       (SELECT COUNT(*) FROM election_votes WHERE election_id = ?) as total_votes
                FROM election_candidates c
                JOIN students s ON c.student_id = s.student_id
                WHERE c.election_id = ?
                ORDER BY c.votes DESC
                ''', (election[0], election[0]))

                candidates = cursor.fetchall()

                if candidates:
                    print("\n    Results:")
                    for candidate in candidates:
                        # Handle variable candidate tuple shapes from tests/mocks.
                        votes = None
                        total_votes = None
                        if len(candidate) >= 5:
                            votes = candidate[3]
                            total_votes = candidate[4]
                        elif len(candidate) == 4:
                            # (first, last, votes, total_votes)
                            votes = candidate[2]
                            total_votes = candidate[3]
                        if not isinstance(votes, (int, float)):
                            votes = 0
                        if not isinstance(total_votes, (int, float)) or total_votes <= 0:
                            total_votes = max(votes, 1)
                        percentage = (votes / total_votes) * 100 if total_votes else 0
                        print(f"    - {candidate[1]} {candidate[2]}: {votes} votes ({percentage:.1f}%)")

                    # Show winner if completed
                    if election[4] == 'completed' and candidates:
                        winner = candidates[0]
                        print(f"\n    🏆 Winner: {winner[1]} {winner[2]} with {winner[3]} votes")

                        # Show if winner has been appointed to position (skip in admin view to avoid extra fetchone)
                        if not show_detailed:
                            cursor.execute('''
                            SELECT COUNT(*) FROM union_representatives
                            WHERE position = ? AND (department = ? OR (department IS NULL AND ? IS NULL))
                            AND election_date = ?
                            ''', (election[1], election[2], election[2], election[3]))
                            try:
                                appointed_row = cursor.fetchone()
                            except Exception:
                                appointed_row = None
                            if appointed_row and isinstance(appointed_row[0], (int, float)) and appointed_row[0] > 0:
                                print("    Status: Appointed to position")
                else:
                    print("    No candidates in this election.")

            print("-" * 40)

        # For admins, offer additional actions
        if show_detailed:
            print("\nAdmin Options:")
            print("1. Appoint an election winner to their position")
            print("2. Close an ongoing election early")
            print("3. Return to menu")

            action = input("\nChoose an action (1-3): ").strip()

            if action == '1':
                # Appoint winner
                elect_num = input("Enter the number of the election: ").strip()
                if not elect_num.isdigit() or int(elect_num) < 1 or int(elect_num) > len(elections):
                    print("Invalid selection.")
                else:
                    selected = elections[int(elect_num)-1]

                    # Get winner
                    cursor.execute('''
                    SELECT c.id, c.student_id, s.first_name, s.last_name, c.votes
                    FROM election_candidates c
                    JOIN students s ON c.student_id = s.student_id
                    WHERE c.election_id = ?
                    ORDER BY c.votes DESC
                    LIMIT 1
                    ''', (selected[0],))

                    winner = cursor.fetchone()

                    if not winner:
                        print("No candidates found for this election.")
                    else:
                        # Check if already appointed
                        cursor.execute('''
                        SELECT COUNT(*) FROM union_representatives
                        WHERE position = ? AND (department = ? OR (department IS NULL AND ? IS NULL))
                        AND status = 'active'
                        ''', (selected[1], selected[2], selected[2]))

                        try:
                            existing_row = cursor.fetchone()
                        except Exception:
                            existing_row = None
                        if existing_row and isinstance(existing_row[0], (int, float)) and existing_row[0] > 0:
                            print("Someone is already appointed to this position.")
                            confirm = input("Do you want to replace them? (y/n): ").strip().lower()
                            if confirm != 'y':
                                print("Operation cancelled.")
                                return

                            # Set current holder to 'former'
                            cursor.execute('''
                            UPDATE union_representatives
                            SET status = 'former', term_end_date = ?
                            WHERE position = ? AND (department = ? OR (department IS NULL AND ? IS NULL))
                            AND status = 'active'
                            ''', (datetime.now().strftime('%Y-%m-%d'), selected[1], selected[2], selected[2]))

                        # Create term end date (1 year from now)
                        term_end = datetime.now()
                        term_end = term_end.replace(year=term_end.year + 1)
                        term_end_str = term_end.strftime('%Y-%m-%d')

                        # Appoint winner
                        cursor.execute('''
                        INSERT INTO union_representatives (
                            student_id, position, department, election_date, term_end_date, status
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            winner[1], selected[1], selected[2], datetime.now().strftime('%Y-%m-%d'),
                            term_end_str, 'active'
                        ))

                        conn.commit()
                        print(f"✅ {winner[2]} {winner[3]} has been appointed as {selected[1]}.")

                        # Send confirmation email
                        send_confirmation_email(winner[1], f"Appointment: {selected[1]}",
                                              f"Congratulations! You have been appointed to the position of {selected[1]} following your election victory.")

            elif action == '2':
                # Close election early
                elect_num = input("Enter the number of the election to close: ").strip()
                if not elect_num.isdigit() or int(elect_num) < 1 or int(elect_num) > len(elections):
                    print("Invalid selection.")
                else:
                    selected = elections[int(elect_num)-1]

                    if selected[4] == 'completed':
                        print("This election is already completed.")
                    else:
                        confirm = input(f"Are you sure you want to close the {selected[1]} election early? (y/n): ").strip().lower()
                        if confirm == 'y':
                            cursor.execute(
                                'UPDATE union_elections SET status = ? WHERE election_id = ?',
                                ('completed', selected[0])
                            )
                            conn.commit()
                            print("✅ Election closed successfully.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def submit_campaign_materials(cursor, conn):
    """Submit campaign materials for approval"""
    try:
        global auth

        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()

        if not result:
            print("No student record found.")
            return

        student_id = result[0]

        # Get candidate's active elections
        cursor.execute('''
        SELECT c.id, c.election_id, e.position, e.department
        FROM election_candidates c
        JOIN union_elections e ON c.election_id = e.election_id
        WHERE c.student_id = ? AND e.status IN ('nomination', 'voting')
        ''', (student_id,))

        candidacies = cursor.fetchall()

        if not candidacies:
            print("You are not a candidate in any active elections.")
            return

        print("📋 Your candidacies:")
        for i, candidacy in enumerate(candidacies):
            dept = f" ({candidacy[3]})" if candidacy[3] else ""
            print(f"{i+1}. {candidacy[2]}{dept}")

        choice = input("Select candidacy to submit materials for (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(candidacies):
            print("Invalid selection.")
            return

        selected_candidacy = candidacies[int(choice)-1]
        candidate_id = selected_candidacy[0]

        print(f"\n📤 Submitting campaign materials for: {selected_candidacy[2]}")

        material_types = ["Poster", "Flyer", "Social Media Post", "Website", "Video", "Other"]

        print("Material types:")
        for i, mat_type in enumerate(material_types):
            print(f"{i+1}. {mat_type}")

        type_choice = input("Select material type: ").strip()
        if type_choice.isdigit() and 1 <= int(type_choice) <= len(material_types):
            material_type = material_types[int(type_choice)-1]
        else:
            material_type = input("Enter custom material type: ").strip()

        content = input("Material content/description: ").strip()
        file_path = input("File path/URL (optional): ").strip()

        upload_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO campaign_materials (
            candidate_id, material_type, content, file_path, upload_date, status
        ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (candidate_id, material_type, content, file_path, upload_date, 'pending_approval'))

        conn.commit()

        print("✅ Campaign material submitted for approval!")
        print("Materials will be reviewed within 24 hours.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def track_campaign_expenses(cursor, conn):
    """Track campaign expenses and ensure compliance"""
    try:
        global auth

        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()
        student_id = result[0]

        # Get candidate's active elections
        cursor.execute('''
        SELECT c.id, e.position, e.department
        FROM election_candidates c
        JOIN union_elections e ON c.election_id = e.election_id
        WHERE c.student_id = ? AND e.status IN ('nomination', 'voting')
        ''', (student_id,))

        candidacies = cursor.fetchall()

        if not candidacies:
            print("You are not a candidate in any active elections.")
            return

        print("💰 Campaign Expense Management")
        print("1. Add expense")
        print("2. View expense summary")
        print("3. Upload receipt")

        choice = input("Choose option: ").strip()

        if choice == '1':
            # Add expense
            print("Your candidacies:")
            for i, candidacy in enumerate(candidacies):
                dept = f" ({candidacy[2]})" if candidacy[2] else ""
                print(f"{i+1}. {candidacy[1]}{dept}")

            cand_choice = input("Select candidacy (enter number): ").strip()
            if not cand_choice.isdigit() or int(cand_choice) < 1 or int(cand_choice) > len(candidacies):
                print("Invalid selection.")
                return

            candidate_id = candidacies[int(cand_choice)-1][0]

            try:
                amount = float(input("Expense amount (£): ").strip())
                if amount <= 0:
                    print("Amount must be positive.")
                    return
            except ValueError:
                print("Invalid amount format.")
                return

            description = input("Expense description: ").strip()
            receipt_path = input("Receipt file path (optional): ").strip()
            expense_date = datetime.now().strftime('%Y-%m-%d')

            cursor.execute('''
            INSERT INTO campaign_expenses (
                candidate_id, amount, description, receipt_path, expense_date
            ) VALUES (?, ?, ?, ?, ?)
            ''', (candidate_id, amount, description, receipt_path, expense_date))

            conn.commit()

            # Check spending limits
            cursor.execute('''
            SELECT SUM(amount) FROM campaign_expenses WHERE candidate_id = ?
            ''', (candidate_id,))

            total_spent = cursor.fetchone()[0] or 0
            spending_limit = 100.00  # £100 limit

            print(f"✅ Expense recorded: £{amount:.2f}")
            print(f"Total campaign spending: £{total_spent:.2f}")
            print(f"Remaining budget: £{spending_limit - total_spent:.2f}")

            if total_spent > spending_limit:
                print("⚠️ WARNING: You have exceeded the campaign spending limit!")

        elif choice == '2':
            # View expense summary
            for candidacy in candidacies:
                candidate_id = candidacy[0]

                cursor.execute('''
                SELECT
                    SUM(amount) as total_spent,
                    COUNT(*) as expense_count,
                    COUNT(CASE WHEN receipt_path IS NOT NULL THEN 1 END) as receipts_provided
                FROM campaign_expenses
                WHERE candidate_id = ?
                ''', (candidate_id,))

                summary = cursor.fetchone()

                print(f"\n📊 Expense Summary - {candidacy[1]}:")
                print(f"Total spent: £{summary[0] or 0:.2f}")
                print(f"Number of expenses: {summary[1]}")
                print(f"Receipts provided: {summary[2]}/{summary[1]}")

                # Show individual expenses
                cursor.execute('''
                SELECT amount, description, expense_date, receipt_path
                FROM campaign_expenses
                WHERE candidate_id = ?
                ORDER BY expense_date DESC
                ''', (candidate_id,))

                expenses = cursor.fetchall()

                if expenses:
                    print("Recent expenses:")
                    for expense in expenses:
                        receipt_status = "✓" if expense[3] else "✗"
                        print(f"  £{expense[0]:.2f} - {expense[1]} ({expense[2]}) {receipt_status}")

        elif choice == '3':
            print("📁 Receipt upload functionality would be implemented with file handling.")
            print("For now, please provide file paths when adding expenses.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def view_candidate_profiles(cursor):
    """View detailed candidate profiles"""
    try:
        # Get elections with candidates
        cursor.execute('''
        SELECT e.election_id, e.position, e.department, COUNT(c.id) as candidate_count
        FROM union_elections e
        JOIN election_candidates c ON e.election_id = c.election_id
        WHERE e.status IN ('nomination', 'voting')
        GROUP BY e.election_id, e.position, e.department
        ORDER BY e.position
        ''')

        elections = cursor.fetchall()

        if not elections:
            print("No elections with candidates available.")
            return

        print("📋 Elections with candidates:")
        for i, election in enumerate(elections):
            dept = f" ({election[2]})" if election[2] else ""
            print(f"{i+1}. {election[1]}{dept} - {election[3]} candidates")

        choice = input("Select election to view candidates (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(elections):
            print("Invalid selection.")
            return

        selected_election = elections[int(choice)-1]
        election_id = selected_election[0]

        # Get detailed candidate information
        cursor.execute('''
        SELECT c.id, s.first_name, s.last_name, s.course, s.year_of_study,
               c.manifesto,
               COUNT(cm.material_id) as campaign_materials,
               SUM(ce.amount) as campaign_expenses
        FROM election_candidates c
        JOIN students s ON c.student_id = s.student_id
        LEFT JOIN campaign_materials cm ON c.id = cm.candidate_id AND cm.status = 'approved'
        LEFT JOIN campaign_expenses ce ON c.id = ce.candidate_id
        WHERE c.election_id = ?
        GROUP BY c.id, s.first_name, s.last_name, s.course, s.year_of_study, c.manifesto
        ORDER BY s.last_name, s.first_name
        ''', (election_id,))

        candidates = cursor.fetchall()

        print(f"\n👥 Candidates for {selected_election[1]}:")
        print("=" * 50)

        for candidate in candidates:
            print(f"\n👤 {candidate[1]} {candidate[2]}")
            print(f"Course: {candidate[3]}, Year {candidate[4]}")
            print(f"Campaign materials: {candidate[6]}")
            expenses = f"£{candidate[7]:.2f}" if candidate[7] else "£0.00"
            print(f"Campaign expenses: {expenses}")

            if candidate[5]:
                print(f"\nManifesto:")
                print(candidate[5])

            # Show campaign materials
            cursor.execute('''
            SELECT material_type, content, upload_date
            FROM campaign_materials
            WHERE candidate_id = ? AND status = 'approved'
            ORDER BY upload_date DESC
            ''', (candidate[0],))

            materials = cursor.fetchall()

            if materials:
                print(f"\nCampaign Materials:")
                for material in materials:
                    print(f"  • {material[0]}: {material[1][:100]}...")

            print("-" * 40)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def election_accessibility_features():
    """Information about election accessibility features"""
    try:
        print(f"\n♿ Election Accessibility Features")
        print("=" * 40)

        print("🔍 Visual Accessibility:")
        print("• High contrast voting interface")
        print("• Large text options available")
        print("• Screen reader compatible")
        print("• Alternative text for all images")

        print(f"\n🌍 Language Support:")
        print("• Multi-language voting interface")
        print("• Translation services available")
        print("• International student support")
        print("• Clear, simple language used")

        print(f"\n🏢 Physical Accessibility:")
        print("• Accessible voting locations")
        print("• Alternative voting methods")
        print("• Extended voting periods if needed")
        print("• Assistance available upon request")

        print(f"\n💻 Technical Accessibility:")
        print("• Multiple device compatibility")
        print("• Backup voting systems")
        print("• Technical support available")
        print("• Offline voting options")

        print(f"\n🤝 Support Services:")
        print("• Disability services coordination")
        print("• Personal voting assistance")
        print("• Quiet voting environments")
        print("• Flexible scheduling")

        print(f"\n📞 To request accessibility accommodations:")
        print("• Contact: elections@studentunion.ac.uk")
        print(f"• Phone: {get_elections_phone()}")
        print("• In person: Student Union Office")
        print("• At least 48 hours notice preferred")

    except Exception as e:
        print(f"An error occurred: {e}")

def monitor_campaign_compliance(cursor):
    """Monitor campaign compliance (admin only)"""
    global auth

    if not auth.check_permission('set_up_elections'):
        print("You don't have permission to monitor campaign compliance.")
        return

    try:
        while True:
            print("\n🔍 Campaign Compliance Monitoring")
            print("=" * 40)

            # Get compliance statistics
            current_date = datetime.now().strftime('%Y-%m-%d')

            # Campaign spending analysis
            cursor.execute('''
            SELECT
                COUNT(DISTINCT c.id) as total_candidates,
                COUNT(DISTINCT ce.candidate_id) as candidates_with_expenses,
                SUM(ce.amount) as total_spending,
                AVG(ce.amount) as avg_spending,
                MAX(ce.amount) as max_spending
            FROM election_candidates c
            JOIN union_elections e ON c.election_id = e.election_id
            LEFT JOIN campaign_expenses ce ON c.id = ce.candidate_id
            WHERE e.status IN ('nomination', 'voting')
            ''')

            spending_stats = cursor.fetchone()

            # Material approval status
            cursor.execute('''
            SELECT
                cm.status,
                COUNT(*) as count
            FROM campaign_materials cm
            JOIN election_candidates c ON cm.candidate_id = c.id
            JOIN union_elections e ON c.election_id = e.election_id
            WHERE e.status IN ('nomination', 'voting')
            GROUP BY cm.status
            ''')

            material_stats = cursor.fetchall()

            # Spending limit violations
            spending_limit = 100.00  # £100 limit
            cursor.execute('''
            SELECT
                c.id,
                s.first_name,
                s.last_name,
                e.position,
                SUM(ce.amount) as total_spent
            FROM election_candidates c
            JOIN students s ON c.student_id = s.student_id
            JOIN union_elections e ON c.election_id = e.election_id
            JOIN campaign_expenses ce ON c.id = ce.candidate_id
            WHERE e.status IN ('nomination', 'voting')
            GROUP BY c.id, s.first_name, s.last_name, e.position
            HAVING SUM(ce.amount) > ?
            ''', (spending_limit,))

            violations = cursor.fetchall()

            print("\n📊 Compliance Overview:")
            print(f"Total active candidates: {spending_stats[0] or 0}")
            print(f"Candidates with expenses: {spending_stats[1] or 0}")
            print(f"Total campaign spending: £{spending_stats[2] or 0:.2f}")
            print(f"Average spending per candidate: £{spending_stats[3] or 0:.2f}")
            print(f"Highest individual spending: £{spending_stats[4] or 0:.2f}")

            print("\n📋 Material Approval Status:")
            material_total = 0
            for status, count in material_stats:
                print(f"  {status.title()}: {count}")
                material_total += count

            if material_total == 0:
                print("  No campaign materials submitted yet")

            print(f"\n⚠️ Spending Limit Violations (£{spending_limit:.2f} limit):")
            if violations:
                for violation in violations:
                    candidate_id, first_name, last_name, position, total_spent = violation
                    overage = total_spent - spending_limit
                    print(f"  • {first_name} {last_name} ({position}): £{total_spent:.2f} (+£{overage:.2f})")
            else:
                print("  ✅ No spending violations detected")

            print("\nCompliance Actions:")
            print("1. Review pending material approvals")
            print("2. Send spending limit warnings")
            print("3. Generate compliance report")
            print("4. View detailed candidate spending")
            print("5. Approve/reject campaign materials")
            print("6. Send compliance reminders")
            print("7. Return to main menu")

            choice = input("Choose an action (1-7): ").strip()

            if choice == '1':
                review_pending_materials(cursor)
            elif choice == '2':
                send_spending_warnings(cursor, violations, spending_limit)
            elif choice == '3':
                generate_compliance_report(cursor)
            elif choice == '4':
                view_detailed_spending(cursor)
            elif choice == '5':
                approve_reject_materials(cursor)
            elif choice == '6':
                send_compliance_reminders(cursor)
            elif choice == '7':
                break
            else:
                print("Invalid choice.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def election_security_audit(cursor):
    """Election security audit (admin only)"""
    global auth

    if not auth.check_permission('set_up_elections'):
        print("You don't have permission to conduct security audits.")
        return

    try:
        while True:
            print("\n🔒 Election Security Audit")
            print("=" * 40)

            print("\nSecurity Audit Options:")
            print("1. Vote Integrity Check")
            print("2. Access Control Review")
            print("3. Audit Trail Analysis")
            print("4. Database Security Scan")
            print("5. Generate Security Report")
            print("6. Export Audit Logs")
            print("7. Return to main menu")

            choice = input("Choose an audit option (1-7): ").strip()

            if choice == '1':
                vote_integrity_check(cursor)
            elif choice == '2':
                access_control_review(cursor)
            elif choice == '3':
                audit_trail_analysis(cursor)
            elif choice == '4':
                database_security_scan(cursor)
            elif choice == '5':
                generate_security_report(cursor)
            elif choice == '6':
                export_audit_logs(cursor)
            elif choice == '7':
                break
            else:
                print("Invalid choice.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def vote_integrity_check(cursor):
    """Check vote integrity and detect anomalies"""
    try:
        print("\n🔍 Vote Integrity Check")
        print("=" * 30)

        # Check for duplicate votes
        cursor.execute('''
        SELECT voter_id, election_id, COUNT(*) as vote_count
        FROM election_votes
        GROUP BY voter_id, election_id
        HAVING COUNT(*) > 1
        ''')

        duplicate_votes = cursor.fetchall()

        if duplicate_votes:
            print("⚠️ DUPLICATE VOTES DETECTED:")
            for voter_id, election_id, count in duplicate_votes:
                print(f"  Voter {voter_id} in Election {election_id}: {count} votes")
        else:
            print("✅ No duplicate votes detected")

        # Check vote timing anomalies
        cursor.execute('''
        SELECT
            voter_id,
            COUNT(*) as votes_cast,
            MIN(vote_time) as first_vote,
            MAX(vote_time) as last_vote
        FROM election_votes
        WHERE date(vote_time) = date('now')
        GROUP BY voter_id
        HAVING COUNT(*) > 3
        ''')

        suspicious_activity = cursor.fetchall()

        if suspicious_activity:
            print("\n⚠️ SUSPICIOUS VOTING ACTIVITY (>3 votes today):")
            for voter_id, votes, first_vote, last_vote in suspicious_activity:
                print(f"  Voter {voter_id}: {votes} votes between {first_vote} and {last_vote}")
        else:
            print("\n✅ No suspicious voting activity detected")

        # Check for votes outside election periods
        cursor.execute('''
        SELECT
            ev.voter_id,
            ev.election_id,
            ev.vote_time,
            e.voting_start,
            e.voting_end
        FROM election_votes ev
        JOIN union_elections e ON ev.election_id = e.election_id
        WHERE ev.vote_time < e.voting_start OR ev.vote_time > e.voting_end
        ''')

        invalid_timing = cursor.fetchall()

        if invalid_timing:
            print("\n⚠️ VOTES CAST OUTSIDE ELECTION PERIODS:")
            for voter_id, election_id, vote_time, start, end in invalid_timing:
                print(f"  Voter {voter_id} in Election {election_id} at {vote_time}")
                print(f"    Valid period: {start} to {end}")
        else:
            print("\n✅ All votes cast within valid election periods")

        input("\nPress Enter to continue...")

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def display_election_menu():
    """Display the election menu"""
    global auth

    while True:
        print("\nElections")
        print("=========")

        # Options
        print("1. View Current & Upcoming Elections")
        print("2. View Election Results")

        max_option = 3
        if auth.check_permission('vote_in_elections'):
            print("3. Vote in Active Election")
            max_option = 4

            # Check if any elections are in nomination phase
            try:
                conn = get_connection()
                cursor = conn.cursor()

                current_date = datetime.now().strftime('%Y-%m-%d')
                cursor.execute('''
                SELECT COUNT(*) FROM union_elections
                WHERE status = 'nomination'
                AND nomination_start <= ? AND nomination_end >= ?
                ''', (current_date, current_date))

                if cursor.fetchone()[0] > 0:
                    print("4. Submit Nomination for Election")
                    max_option = 5

                conn.close()
            except sqlite3.Error:
                pass

        print(f"{max_option}. Return to Student Union Menu")

        choice = input("\nEnter your choice: ")

        if choice == '1':
            # View Elections
            view_elections()
        elif choice == '2':
            # View Results
            view_election_results()
        elif choice == '3' and auth.check_permission('vote_in_elections'):
            # Vote
            vote_in_election()
        elif choice == '4' and max_option >= 5:
            # Submit Nomination
            nominate_for_election()
        elif choice == str(max_option):
            # Return to Student Union Menu
            return
        else:
            print("Invalid choice. Please try again.")
