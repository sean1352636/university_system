from education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management._imports import (
    datetime, sqlite3, send_confirmation_email, get_auth,
)
import education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management._imports as _state
from education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management import clubs as _clubs

def _view_clubs():
    try:
        import sys
        pkg = sys.modules.get(
            "education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management"
        )
        if pkg is not None and hasattr(pkg, "view_clubs"):
            return pkg.view_clubs()
    except Exception:
        pass
    return _clubs.view_clubs()


def join_club():
    """Join a club/society"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to join a club.")
        return

    if not auth.check_permission('join_clubs'):
        print("You don't have permission to join clubs.")
        return

    # Get the student ID associated with the current user
    try:
        conn = _state.resolve_get_connection()()
        cursor = conn.cursor()

        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()

        if not result:
            print("No student record is associated with your account.")
            conn.close()
            return

        student_id = result[0]

        # First show available clubs
        _view_clubs()

        club_id = input("\nEnter the ID of the club you want to join: ").strip()
        if not club_id.isdigit():
            print("Invalid club ID.")
            conn.close()
            return

        # Check if club exists and is active
        cursor.execute('SELECT club_name FROM student_clubs WHERE club_id = ? AND status = "active"', (club_id,))
        club = cursor.fetchone()

        if not club:
            print("Club not found or not active.")
            conn.close()
            return

        # Check if already a member
        cursor.execute('SELECT COUNT(*) FROM club_members WHERE club_id = ? AND student_id = ?', (club_id, student_id))
        if cursor.fetchone()[0] > 0:
            print(f"You are already a member of {club[0]}.")
            conn.close()
            return

        # Add as member
        join_date = datetime.now().strftime('%Y-%m-%d')

        cursor.execute(
            'INSERT INTO club_members (club_id, student_id, join_date, role) VALUES (?, ?, ?, ?)',
            (club_id, student_id, join_date, 'Member')
        )

        # Update member count
        cursor.execute(
            'UPDATE student_clubs SET member_count = member_count + 1 WHERE club_id = ?',
            (club_id,)
        )

        conn.commit()
        print(f"You have successfully joined {club[0]}!")

        # Send confirmation email
        _state.resolve_send_confirmation_email()(
            student_id,
            f"Club Membership: {club[0]}",
            f"You have successfully joined the {club[0]} club. Welcome!"
        )

        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")


def view_my_clubs():
    """View clubs I am a member of"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to view your clubs.")
        return

    try:
        conn = _state.resolve_get_connection()()
        cursor = conn.cursor()

        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()

        if not result:
            print("No student record is associated with your account.")
            conn.close()
            return

        student_id = result[0]

        # Get clubs the student is a member of
        cursor.execute('''
        SELECT c.club_id, c.club_name, c.category, m.role, m.join_date
        FROM student_clubs c
        JOIN club_members m ON c.club_id = m.club_id
        WHERE m.student_id = ? AND c.status = 'active'
        ORDER BY c.club_name
        ''', (student_id,))

        clubs = cursor.fetchall()

        if not clubs:
            print("You are not a member of any clubs.")
            conn.close()
            return

        print("\nYour Club Memberships:")
        print("======================")

        for club in clubs:
            print(f"\nID: {club[0]}")
            print(f"Name: {club[1]}")
            print(f"Category: {club[2]}")
            print(f"Your Role: {club[3]}")
            print(f"Joined on: {club[4]}")
            print("-" * 40)

        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")


def club_member_directory():
    """View club member directory with contact info"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to view member directory.")
        return

    try:
        conn = _state.resolve_get_connection()()
        cursor = conn.cursor()

        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()

        if not result:
            print("No student record is associated with your account.")
            conn.close()
            return

        student_id = result[0]

        # Get clubs the student is a member of
        cursor.execute('''
        SELECT c.club_id, c.club_name
        FROM student_clubs c
        JOIN club_members m ON c.club_id = m.club_id
        WHERE m.student_id = ? AND c.status = 'active'
        ORDER BY c.club_name
        ''', (student_id,))

        clubs = cursor.fetchall()

        if not clubs:
            print("You are not a member of any clubs.")
            conn.close()
            return

        print("\nYour clubs:")
        for i, club in enumerate(clubs):
            print(f"{i+1}. {club[1]}")

        choice = input("Select a club to view member directory (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(clubs):
            print("Invalid selection.")
            conn.close()
            return

        selected_club = clubs[int(choice)-1]
        club_id = selected_club[0]
        club_name = selected_club[1]

        # Get all members of the selected club
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.last_name, s.email, s.course,
               m.role, m.join_date
        FROM club_members m
        JOIN students s ON m.student_id = s.student_id
        WHERE m.club_id = ?
        ORDER BY
            CASE m.role
                WHEN 'President' THEN 1
                WHEN 'Treasurer' THEN 2
                WHEN 'Secretary' THEN 3
                ELSE 4
            END,
            s.last_name, s.first_name
        ''', (club_id,))

        members = cursor.fetchall()

        if not members:
            print("No members found.")
            conn.close()
            return

        print(f"\nMember Directory - {club_name}")
        print("=" * 80)
        print(f"{'Student ID':<12} {'Name':<25} {'Role':<15} {'Course':<8} {'Email':<25} {'Joined':<12}")
        print("-" * 100)

        officers = []
        regular_members = []

        for member in members:
            if member[5] in ['President', 'Treasurer', 'Secretary']:
                officers.append(member)
            else:
                regular_members.append(member)

        # Display officers first
        if officers:
            print("OFFICERS:")
            for member in officers:
                print(f"{member[0]:<12} {member[1]} {member[2]:<25} {member[5]:<15} {member[4]:<8} {member[3]:<25} {member[6]:<12}")
            print()

        # Display regular members
        if regular_members:
            print("MEMBERS:")
            for member in regular_members:
                print(f"{member[0]:<12} {member[1]} {member[2]:<25} {member[5]:<15} {member[4]:<8} {member[3]:<25} {member[6]:<12}")

        print(f"\nTotal Members: {len(members)}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
