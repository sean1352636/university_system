"""Student Union clubs: create, update, delete, browse, join, manage.

Split out of ``student_union_core.py``, which re-exports every name here;
callers keep importing from ``student_union_core``.
"""

from datetime import datetime

from education_system.systems.university.domains.student_life.domain.student_life.student_union.calendar_bridge import mirror as _mirror_to_calendar
from education_system.systems.university.infrastructure.database.db import get_connection

from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.union_core.common import (
    _club_current_student,
    get_current_user,
    logger,
    _send_club_email,
)


CLUB_REMOVED_TEMPLATE = "student_life/clubs/club_removed"

# PLACEHOLDER FUNCTIONS FOR MISSING MODULES
# These functions need to be implemented to replace the missing imports


# ---------------------------------------------------------------------------
# Club helpers
# ---------------------------------------------------------------------------
# These screens used to ask the signed-in student to type their own student ID
# — which they may not know, and which let anyone join a club as anyone else.
# The id now comes from the authenticated session.

CLUB_JOIN_TEMPLATE = "student_life/clubs/club_join_confirmation"


def _club_name_exists(cursor, club_name, exclude_id=None):
    """Whether a club of this name already exists (case-insensitive)."""
    query = ("SELECT id FROM student_union_clubs"
             " WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))")
    params = [club_name]
    if exclude_id is not None:
        query += " AND id != ?"
        params.append(exclude_id)
    cursor.execute(query + " LIMIT 1", params)
    return cursor.fetchone() is not None


def create_club():
    """Create a new student club."""
    print("\n=== Create New Club ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create clubs table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_union_clubs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                category TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        ''')

        # Names must be unique. Nothing stopped two "Chess Club" rows before,
        # which makes every later "enter the club ID" prompt ambiguous and
        # splits members across duplicates. Re-ask rather than abandoning what
        # they have already typed.
        club_name = None
        while club_name is None:
            entered = input("Enter club name (blank to cancel): ").strip()
            if not entered:
                print("Club creation cancelled.")
                return
            if _club_name_exists(cursor, entered):
                print(f"A club called '{entered}' already exists. "
                      "Please choose a different name.")
                continue
            club_name = entered

        description = input("Enter club description: ").strip()
        category = input("Enter category (Academic/Social/Sports/Cultural/Other): ").strip()

        cursor.execute('''
            INSERT INTO student_union_clubs (name, description, category)
            VALUES (?, ?, ?)
        ''', (club_name, description, category))

        conn.commit()
        club_id = cursor.lastrowid
        print(f"\n✓ Club '{club_name}' created successfully! (ID {club_id})")

        # A club has no date of its own — it goes on the calendar as a
        # founding entry so the union's activity is visible there too.
        if _mirror_to_calendar(
            name=f"SU Club founded: {club_name}", kind="club",
            description=description or f"{category or 'Student Union'} club",
            source_table="student_union_clubs", source_id=club_id,
            conn=conn,
        ):
            print("  Added to the university academic calendar.")

    except Exception as e:
        print(f"Error creating club: {e}")
    finally:
        if conn:
            conn.close()


def update_club():
    """Update an existing club's details."""
    print("\n=== Update Club ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        club_id = input("Enter club ID to update (blank to cancel): ").strip()
        if not club_id:
            return

        cursor.execute(
            'SELECT id, name, description, category, status'
            ' FROM student_union_clubs WHERE id = ?', (club_id,))
        club = cursor.fetchone()
        if not club:
            print("Club not found.")
            return

        _cid, name, description, category, status = club
        print(f"\nCurrent details:")
        print(f"  Name:        {name}")
        print(f"  Description: {description or '(none)'}")
        print(f"  Category:    {category or '(none)'}")
        print(f"  Status:      {status}")
        print("\nLeave a field blank to keep its current value.")

        new_name = name
        while True:
            entered = input(f"Name [{name}]: ").strip()
            if not entered:
                break
            if _club_name_exists(cursor, entered, exclude_id=club_id):
                print(f"A club called '{entered}' already exists. "
                      "Please choose a different name.")
                continue
            new_name = entered
            break

        new_description = input(f"Description [{description or 'none'}]: ").strip() or description
        new_category = input(f"Category [{category or 'none'}]: ").strip() or category
        new_status = input(f"Status (active/inactive) [{status}]: ").strip() or status

        changes = [(label, old, new) for label, old, new in (
            ("Name", name, new_name),
            ("Description", description, new_description),
            ("Category", category, new_category),
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

        cursor.execute('''
            UPDATE student_union_clubs
            SET name = ?, description = ?, category = ?, status = ?
            WHERE id = ?
        ''', (new_name, new_description, new_category, new_status, club_id))
        conn.commit()
        print(f"\n✓ Club {club_id} updated ({len(changes)} change(s)).")

    except Exception as e:
        print(f"Error updating club: {e}")
    finally:
        if conn:
            conn.close()


def delete_club():
    """Delete a club, telling its members it is closing."""
    print("\n=== Delete Club ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        club_id = input("Enter club ID to delete (blank to cancel): ").strip()
        if not club_id:
            return

        cursor.execute(
            'SELECT id, name, category FROM student_union_clubs WHERE id = ?', (club_id,))
        club = cursor.fetchone()
        if not club:
            print("Club not found.")
            return
        _cid, club_name, category = club

        # Who is affected — gathered before the delete, so the notice can be
        # sent to people whose membership is about to disappear.
        members = []
        try:
            cursor.execute('''
                SELECT m.student_id, s.first_name, s.last_name, s.email_address
                FROM club_memberships m
                LEFT JOIN students s ON m.student_id = s.student_id
                WHERE m.club_id = ? AND m.status = 'active'
            ''', (club_id,))
            for sid, first, last, email in cursor.fetchall():
                members.append({
                    'student_id': sid,
                    'name': f"{first or ''} {last or ''}".strip() or sid,
                    'email': email,
                })
        except Exception as exc:
            print(f"(Could not read the member list: {exc})")

        print(f"\nAbout to delete '{club_name}' ({category or 'uncategorised'}).")
        if members:
            reachable = sum(1 for m in members if (m['email'] or '').strip())
            print(f"It has {len(members)} member(s); {reachable} can be emailed.")
            for member in members[:10]:
                mark = '' if (member['email'] or '').strip() else '  (no email on file)'
                print(f"  • {member['name']} ({member['student_id']}){mark}")
            if len(members) > 10:
                print(f"  … and {len(members) - 10} more")
        else:
            print("It has no members.")

        if input("\nDelete this club? (yes/no): ").strip().lower() != 'yes':
            print("Deletion cancelled. Nothing has been changed.")
            return

        reason = input("Reason for closing (shown to members, optional): ").strip()

        closed_by = 'the Students\' Union'
        try:
            user = get_current_user()
            if user:
                closed_by = user.get('username', closed_by)
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        cursor.execute('DELETE FROM club_memberships WHERE club_id = ?', (club_id,))
        cursor.execute('DELETE FROM student_union_clubs WHERE id = ?', (club_id,))
        conn.commit()
        print(f"\n✓ Club '{club_name}' deleted.")

        # Notify after the commit, so nobody is told about a deletion that
        # rolled back.
        if members:
            sent = failed = no_address = 0
            for member in members:
                if not (member['email'] or '').strip():
                    no_address += 1
                    continue
                if _send_club_email(CLUB_REMOVED_TEMPLATE, member['email'], {
                        'club_name': club_name,
                        'student_name': member['name'],
                        'category': category or 'Not specified',
                        'closed_date': datetime.now().strftime('%Y-%m-%d'),
                        'closed_by': closed_by,
                        'reason': reason or 'No reason was recorded.'}):
                    sent += 1
                else:
                    failed += 1
            summary = f"Member notices: {sent} sent"
            if failed:
                summary += f", {failed} failed"
            if no_address:
                summary += f", {no_address} with no address on file"
            print(summary + ".")

    except Exception as e:
        print(f"Error deleting club: {e}")
    finally:
        if conn:
            conn.close()

def view_clubs():
    """View all available clubs"""
    print("\n=== Available Clubs ===")
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, name, description, category, status
            FROM student_union_clubs
            WHERE status = 'active'
            ORDER BY category, name
        ''')

        clubs = cursor.fetchall()

        if not clubs:
            print("No clubs available.")
            return

        current_category = None
        for club in clubs:
            club_id, name, description, category, status = club
            if category != current_category:
                print(f"\n--- {category or 'Uncategorized'} ---")
                current_category = category
            print(f"{club_id}. {name}")
            if description:
                print(f"   {description}")

    except Exception as e:
        print(f"Error viewing clubs: {e}")
    finally:
        if conn:
            conn.close()

def join_club():
    """Join a student club as the signed-in student."""
    print("\n=== Join Club ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Identify the student from the session rather than asking them to
        # type their own id — they may not know it, and typing someone else's
        # would have enrolled that person instead.
        student_id, student_name, student_email = _club_current_student(conn)
        if not student_id:
            print("You must be signed in as a student to join a club.")
            return
        print(f"Joining as: {student_name} ({student_id})")

        club_id = input("Enter club ID to join: ").strip()
        if not club_id:
            print("Club ID required.")
            return

        # Create memberships table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS club_memberships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                club_id INTEGER,
                student_id TEXT,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        ''')

        # The club has to exist and be open. Nothing checked this before, so
        # a mistyped id created a membership of a club that does not exist —
        # invisible in "my memberships" (it joins on the clubs table) but
        # counted everywhere that trusts club_memberships.
        cursor.execute(
            'SELECT name, status FROM student_union_clubs WHERE id = ?', (club_id,))
        club = cursor.fetchone()
        if not club:
            print(f"No club with ID {club_id}. Use 'View Available Clubs' to see the list.")
            return
        club_name, club_status = club
        if (club_status or 'active').lower() != 'active':
            print(f"'{club_name}' is not currently active, so you cannot join it.")
            return

        # Check if already member
        cursor.execute('SELECT id FROM club_memberships WHERE club_id = ? AND student_id = ? AND status = "active"',
                      (club_id, student_id))
        if cursor.fetchone():
            print(f"You are already a member of {club_name}.")
            return

        cursor.execute('INSERT INTO club_memberships (club_id, student_id) VALUES (?, ?)',
                      (club_id, student_id))
        conn.commit()
        print(f"✓ Successfully joined {club_name}!")

        first, _, last = (student_name or '').partition(' ')
        if _send_club_email(CLUB_JOIN_TEMPLATE, student_email, {
                'club_name': club_name,
                'first_name': first or student_name or 'Student',
                'last_name': last or '',
                'student_name': student_name or 'Student'}):
            print(f"📧 Confirmation emailed to {student_email}.")
        elif student_email:
            print("Note: the confirmation email could not be sent.")
        else:
            print("No email address on file, so no confirmation was sent.")

    except Exception as e:
        print(f"Error joining club: {e}")
    finally:
        if conn:
            conn.close()

def view_my_clubs():
    """View the signed-in student's club memberships."""
    print("\n=== My Clubs ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Same as join_club: the id comes from the session, not a prompt.
        student_id, student_name, _email = _club_current_student(conn)
        if not student_id:
            print("You must be signed in as a student to view your memberships.")
            return
        print(f"Memberships for {student_name} ({student_id}):")

        cursor.execute('''
            SELECT c.name, c.category, m.join_date
            FROM club_memberships m
            JOIN student_union_clubs c ON m.club_id = c.id
            WHERE m.student_id = ? AND m.status = 'active'
            ORDER BY m.join_date DESC
        ''', (student_id,))

        clubs = cursor.fetchall()
        if not clubs:
            print("You are not a member of any clubs.")
            return

        for name, category, join_date in clubs:
            print(f"\n• {name} ({category})")
            print(f"  Joined: {join_date}")

    except Exception as e:
        print(f"Error viewing clubs: {e}")
    finally:
        if conn:
            conn.close()

def manage_club():
    """Manage club settings and members"""
    print("\n=== Manage Club ===")
    club_id = input("Enter club ID to manage: ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT name FROM student_union_clubs WHERE id = ?', (club_id,))
        club = cursor.fetchone()
        if not club:
            print("Club not found.")
            return

        print(f"\nManaging: {club[0]}")
        print("1. Update club info")
        print("2. View members")
        print("3. Remove member")
        choice = input("Select option: ").strip()

        if choice == '1':
            new_desc = input("New description (or press Enter to skip): ").strip()
            if new_desc:
                cursor.execute('UPDATE student_union_clubs SET description = ? WHERE id = ?',
                             (new_desc, club_id))
                conn.commit()
                print("✓ Club updated!")
        elif choice == '2':
            cursor.execute('''
                SELECT student_id, join_date FROM club_memberships
                WHERE club_id = ? AND status = 'active'
            ''', (club_id,))
            members = cursor.fetchall()
            print(f"\nMembers ({len(members)}):")
            for sid, join_date in members:
                print(f"  • {sid} (joined {join_date})")

    except Exception as e:
        print(f"Error managing club: {e}")
    finally:
        if conn:
            conn.close()
