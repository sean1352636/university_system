"""Student Union elections: create, update, delete, nominate, vote, results.

Split out of ``student_union_core.py``, which re-exports every name here;
callers keep importing from ``student_union_core``.
"""

from datetime import datetime

from education_system.systems.university.domains.student_life.domain.student_life.student_union.calendar_bridge import mirror as _mirror_to_calendar
from education_system.systems.university.infrastructure.database.db import get_connection

from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.union_core.common import (
    _club_current_student,
)


def view_elections():
    """View elections, active ones first."""
    print("\n=== Elections ===")
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT e.id, e.title, e.description, e.start_date, e.end_date,
                   COALESCE(e.status, 'active'),
                   (SELECT COUNT(*) FROM election_candidates c WHERE c.election_id = e.id),
                   (SELECT COUNT(*) FROM election_votes v WHERE v.election_id = e.id)
            FROM elections e
            ORDER BY CASE WHEN COALESCE(e.status, 'active') = 'active' THEN 0 ELSE 1 END,
                     e.start_date DESC
        ''')
        elections = cursor.fetchall()

        if not elections:
            print("There are no elections yet.")
            return

        for eid, title, desc, start, end, status, candidates, votes in elections:
            print(f"\n{eid}. {title}  [{status}]")
            print(f"   Period: {start or 'start TBC'} to {end or 'end TBC'}")
            print(f"   Candidates: {candidates}   Votes cast: {votes}")
            if desc:
                print(f"   {desc}")

        print(f"\n{len(elections)} election(s).")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def _pick_election(cursor, prompt="Select an election", statuses=None):
    """Show elections and let the operator pick one. Returns the row or None."""
    if statuses:
        placeholders = ','.join('?' * len(statuses))
        # db-audit: ignore[DBW001] - join of placeholders
        cursor.execute(
            "SELECT id, title, description, start_date, end_date,"
            " COALESCE(status,'active') FROM elections"
            f" WHERE COALESCE(status,'active') IN ({placeholders})"
            " ORDER BY start_date DESC", tuple(statuses))
    else:
        cursor.execute(
            "SELECT id, title, description, start_date, end_date,"
            " COALESCE(status,'active') FROM elections ORDER BY start_date DESC")
    elections = cursor.fetchall()
    if not elections:
        print("There are no elections to choose from.")
        return None

    print(f"\n{prompt}:")
    for index, (_eid, title, _desc, start, end, status) in enumerate(elections, 1):
        print(f"{index}. {title}")
        print(f"     {start or 'start TBC'} to {end or 'end TBC'} · {status}")

    while True:
        raw = input(f"\nSelect an election (1-{len(elections)}, blank to cancel): ").strip()
        if not raw:
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(elections):
            return elections[int(raw) - 1]
        print(f"Please enter a number between 1 and {len(elections)}.")


def create_election():
    """Create a new election."""
    print("\n=== Create Election ===")
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        title = input("Election title (blank to cancel): ").strip()
        if not title:
            print("Election creation cancelled.")
            return

        cursor.execute(
            "SELECT 1 FROM elections WHERE LOWER(TRIM(title)) = LOWER(TRIM(?)) LIMIT 1",
            (title,))
        if cursor.fetchone():
            print(f"An election called '{title}' already exists. "
                  "Please choose a different title.")
            return

        description = input("Description: ").strip()

        start_date = None
        while start_date is None:
            raw = input("Start date (YYYY-MM-DD, blank to cancel): ").strip()
            if not raw:
                print("Election creation cancelled.")
                return
            try:
                datetime.strptime(raw, '%Y-%m-%d')
                start_date = raw
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

        end_date = None
        while end_date is None:
            raw = input("End date (YYYY-MM-DD, blank to cancel): ").strip()
            if not raw:
                print("Election creation cancelled.")
                return
            try:
                if datetime.strptime(raw, '%Y-%m-%d') < datetime.strptime(start_date, '%Y-%m-%d'):
                    print("The end date must be on or after the start date.")
                    continue
                end_date = raw
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

        cursor.execute(
            "INSERT INTO elections (title, description, start_date, end_date, status,"
            " voting_start, voting_end, created_at)"
            " VALUES (?, ?, ?, ?, 'active', ?, ?, ?)",
            (title, description or None, start_date, end_date, start_date, end_date,
             datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        election_id = cursor.lastrowid
        print(f"\n✓ Election '{title}' created (ID {election_id}).")

        if _mirror_to_calendar(
            name=f"SU Election: {title}", kind="election",
            date_start=start_date, date_end=end_date,
            description=description or "Student Union election — voting open",
            source_table="elections", source_id=election_id,
            conn=conn,
        ):
            print("  Added to the university academic calendar.")

    except Exception as e:
        print(f"Error creating election: {e}")
    finally:
        if conn:
            conn.close()


def update_election():
    """Update an election's details."""
    print("\n=== Update Election ===")
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        chosen = _pick_election(cursor, "Select the election to update")
        if not chosen:
            print("Update cancelled.")
            return
        election_id, title, description, start_date, end_date, status = chosen

        print("\nLeave a field blank to keep its current value.")
        new_title = title
        while True:
            entered = input(f"Title [{title}]: ").strip()
            if not entered:
                break
            cursor.execute(
                "SELECT 1 FROM elections WHERE LOWER(TRIM(title)) = LOWER(TRIM(?))"
                " AND id != ? LIMIT 1", (entered, election_id))
            if cursor.fetchone():
                print(f"An election called '{entered}' already exists. "
                      "Please choose a different title.")
                continue
            new_title = entered
            break

        new_description = input(f"Description [{description or 'none'}]: ").strip() or description

        new_start = start_date
        while True:
            raw = input(f"Start date [{start_date or 'not set'}]: ").strip()
            if not raw:
                break
            try:
                datetime.strptime(raw, '%Y-%m-%d')
                new_start = raw
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

        new_end = end_date
        while True:
            raw = input(f"End date [{end_date or 'not set'}]: ").strip()
            if not raw:
                break
            try:
                datetime.strptime(raw, '%Y-%m-%d')
                new_end = raw
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

        new_status = input(f"Status (active/closed) [{status}]: ").strip() or status

        changes = [(label, old, new) for label, old, new in (
            ("Title", title, new_title),
            ("Description", description, new_description),
            ("Start date", start_date, new_start),
            ("End date", end_date, new_end),
            ("Status", status, new_status),
        ) if (old or '') != (new or '')]

        if not changes:
            print("\nNothing was changed.")
            return

        print("\nAbout to apply these changes:")
        for label, old, new in changes:
            print(f"  - {label}: '{old or 'not set'}' -> '{new or 'not set'}'")
        if input("\nApply these changes? (y/n): ").strip().lower() != 'y':
            print("Update cancelled. Nothing has been changed.")
            return

        cursor.execute(
            "UPDATE elections SET title = ?, description = ?, start_date = ?,"
            " end_date = ?, voting_start = ?, voting_end = ?, status = ? WHERE id = ?",
            (new_title, new_description, new_start, new_end, new_start, new_end,
             new_status, election_id))
        conn.commit()
        print(f"\n✓ Election {election_id} updated ({len(changes)} change(s)).")

    except Exception as e:
        print(f"Error updating election: {e}")
    finally:
        if conn:
            conn.close()


def delete_election():
    """Delete an election, along with its candidates and votes."""
    print("\n=== Delete Election ===")
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        chosen = _pick_election(cursor, "Select the election to delete")
        if not chosen:
            print("Deletion cancelled.")
            return
        election_id, title = chosen[0], chosen[1]

        cursor.execute("SELECT COUNT(*) FROM election_candidates WHERE election_id = ?",
                       (election_id,))
        candidates = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM election_votes WHERE election_id = ?",
                       (election_id,))
        votes = cursor.fetchone()[0]

        print(f"\nAbout to delete '{title}'.")
        print(f"It has {candidates} candidate(s) and {votes} vote(s) recorded.")
        if votes:
            print("Deleting it destroys the ballot record — this cannot be undone.")

        if input("\nDelete this election? (yes/no): ").strip().lower() != 'yes':
            print("Deletion cancelled. Nothing has been changed.")
            return

        cursor.execute("DELETE FROM election_votes WHERE election_id = ?", (election_id,))
        cursor.execute("DELETE FROM election_candidates WHERE election_id = ?", (election_id,))
        cursor.execute("DELETE FROM elections WHERE id = ?", (election_id,))
        conn.commit()
        print(f"\n✓ Election '{title}' deleted.")

    except Exception as e:
        print(f"Error deleting election: {e}")
    finally:
        if conn:
            conn.close()


def nominate_for_election():
    """Nominate the signed-in student for an election."""
    print("\n=== Election Nomination ===")
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id, student_name, _email = _club_current_student(conn)
        if not student_id:
            print("You must be signed in as a student to nominate yourself.")
            return
        print(f"Nominating: {student_name} ({student_id})")

        chosen = _pick_election(cursor, "Select the election to stand in",
                                statuses=("active", "nomination"))
        if not chosen:
            print("Nomination cancelled.")
            return
        election_id, title = chosen[0], chosen[1]

        cursor.execute(
            "SELECT 1 FROM election_candidates WHERE election_id = ? AND student_id = ? LIMIT 1",
            (election_id, student_id))
        if cursor.fetchone():
            print(f"You are already standing in {title}.")
            return

        manifesto = input("Your manifesto (what you would do): ").strip()

        cursor.execute(
            "INSERT INTO election_candidates (election_id, student_id, manifesto, votes)"
            " VALUES (?, ?, ?, 0)", (election_id, student_id, manifesto or None))
        conn.commit()
        print(f"✓ Nomination submitted for {title}!")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def vote_in_election():
    """Cast the signed-in student's vote.

    The votes table uses voter_id and vote_time; this used to write student_id
    and vote_date, so voting failed outright.
    """
    print("\n=== Cast Vote ===")
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id, student_name, _email = _club_current_student(conn)
        if not student_id:
            print("You must be signed in as a student to vote.")
            return
        print(f"Voting as: {student_name} ({student_id})")

        chosen = _pick_election(cursor, "Select the election", statuses=("active",))
        if not chosen:
            print("Voting cancelled.")
            return
        election_id, title = chosen[0], chosen[1]

        # One vote per person.
        cursor.execute(
            "SELECT 1 FROM election_votes WHERE election_id = ? AND voter_id = ? LIMIT 1",
            (election_id, student_id))
        if cursor.fetchone():
            print(f"You have already voted in {title}.")
            return

        cursor.execute('''
            SELECT c.id, c.student_id, s.first_name, s.last_name, c.manifesto
            FROM election_candidates c
            LEFT JOIN students s ON c.student_id = s.student_id
            WHERE c.election_id = ?
            ORDER BY s.last_name, s.first_name
        ''', (election_id,))
        candidates = cursor.fetchall()
        if not candidates:
            print(f"There are no candidates standing in {title} yet.")
            return

        print(f"\nCandidates for {title}:")
        for index, (_cid, sid, first, last, manifesto) in enumerate(candidates, 1):
            who = f"{first or ''} {last or ''}".strip() or sid
            print(f"{index}. {who} ({sid})")
            if manifesto:
                print(f"     {manifesto}")

        candidate = None
        while candidate is None:
            raw = input(f"\nSelect a candidate (1-{len(candidates)}, blank to cancel): ").strip()
            if not raw:
                print("Voting cancelled. No vote has been recorded.")
                return
            if raw.isdigit() and 1 <= int(raw) <= len(candidates):
                candidate = candidates[int(raw) - 1]
            else:
                print(f"Please enter a number between 1 and {len(candidates)}.")

        candidate_id, candidate_sid, first, last, _m = candidate
        who = f"{first or ''} {last or ''}".strip() or candidate_sid
        if input(f"\nCast your vote for {who}? This cannot be changed. (yes/no): ").strip().lower() != 'yes':
            print("Voting cancelled. No vote has been recorded.")
            return

        cursor.execute(
            "INSERT INTO election_votes (election_id, voter_id, candidate_id, vote_time)"
            " VALUES (?, ?, ?, ?)",
            (election_id, student_id, candidate_id,
             datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        cursor.execute(
            "UPDATE election_candidates SET votes = COALESCE(votes, 0) + 1 WHERE id = ?",
            (candidate_id,))
        conn.commit()
        print(f"✓ Vote cast for {who} in {title}.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def view_election_results():
    """View the results of an election.

    This used to ask for an election ID and then print raw candidate row ids
    against vote counts, which told nobody anything.
    """
    print("\n=== Election Results ===")
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        chosen = _pick_election(cursor, "Select an election")
        if not chosen:
            print("Cancelled.")
            return
        election_id, title, _desc, _start, _end, status = chosen

        cursor.execute('''
            SELECT c.id, c.student_id, s.first_name, s.last_name,
                   (SELECT COUNT(*) FROM election_votes v WHERE v.candidate_id = c.id)
            FROM election_candidates c
            LEFT JOIN students s ON c.student_id = s.student_id
            WHERE c.election_id = ?
        ''', (election_id,))
        candidates = cursor.fetchall()

        if not candidates:
            print(f"\nNobody stood in {title}.")
            return

        tallies = sorted(candidates, key=lambda row: row[4], reverse=True)
        total = sum(row[4] for row in tallies)

        print(f"\n{title}  [{status}]")
        print(f"Total votes cast: {total}")
        if not total:
            print("\nNo votes have been cast yet.")
            return

        print("\nResults:")
        for position, (_cid, sid, first, last, votes) in enumerate(tallies, 1):
            who = f"{first or ''} {last or ''}".strip() or sid
            share = (votes / total) * 100
            print(f"  {position}. {who} ({sid}): {votes} vote(s) — {share:.1f}%")

        top = tallies[0][4]
        leaders = [row for row in tallies if row[4] == top]
        if len(leaders) == 1:
            _cid, sid, first, last, votes = leaders[0]
            who = f"{first or ''} {last or ''}".strip() or sid
            label = "Winner" if status != 'active' else "Currently leading"
            print(f"\n{label}: {who} with {votes} vote(s).")
        else:
            names = ', '.join(
                (f"{row[2] or ''} {row[3] or ''}".strip() or row[1]) for row in leaders)
            print(f"\nTied on {top} vote(s): {names}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()
