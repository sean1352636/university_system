from education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management._imports import (
    datetime, sqlite3, get_connection,
)
import education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management._imports as _state


def manage_club_discussions():
    """Manage club discussion boards"""
    auth = _state.auth

    if not auth or not auth.current_user:
        print("You must be logged in to access club discussions.")
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

        # Get clubs the student is a member of
        cursor.execute('''
        SELECT c.club_id, c.club_name, m.role
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
            print(f"{i+1}. {club[1]} ({club[2]})")

        choice = input("Select a club to view discussions (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(clubs):
            print("Invalid selection.")
            conn.close()
            return

        selected_club = clubs[int(choice)-1]
        club_id = selected_club[0]
        club_name = selected_club[1]
        user_role = selected_club[2]

        while True:
            print(f"\nClub Discussions - {club_name}")
            print("1. View recent discussions")
            print("2. View announcements")
            print("3. Create new discussion")
            print("4. Search discussions")

            if user_role in ['President', 'Secretary'] or auth.check_permission('manage_all_clubs'):
                print("5. Create announcement")
                print("6. Manage discussions")
                print("7. Return to previous menu")
                max_option = 7
            else:
                print("5. Return to previous menu")
                max_option = 5

            action = input("Choose an action: ").strip()

            if action == '1':
                # View recent discussions
                cursor.execute('''
                SELECT d.discussion_id, d.title, s.first_name, s.last_name,
                       d.post_date, d.is_announcement, d.pinned
                FROM club_discussions d
                JOIN students s ON d.author_id = s.student_id
                WHERE d.club_id = ?
                ORDER BY d.pinned DESC, d.post_date DESC
                LIMIT 20
                ''', (club_id,))

                discussions = cursor.fetchall()

                if not discussions:
                    print("No discussions found.")
                else:
                    print(f"\nRecent Discussions:")
                    print(f"{'ID':<6} {'Title':<40} {'Author':<20} {'Date':<12} {'Type':<12}")
                    print("-" * 95)

                    for disc in discussions:
                        disc_type = "📌 Pinned" if disc[6] else ("📢 Announcement" if disc[5] else "💬 Discussion")
                        print(f"{disc[0]:<6} {disc[1][:40]:<40} {disc[2]} {disc[3]:<20} {disc[4][:10]:<12} {disc_type:<12}")

                    # Allow viewing specific discussion
                    view_id = input("\nEnter discussion ID to view details (or press Enter to continue): ").strip()
                    if view_id.isdigit():
                        view_discussion_details(int(view_id), cursor, student_id, user_role)

            elif action == '2':
                # View announcements only
                cursor.execute('''
                SELECT d.discussion_id, d.title, s.first_name, s.last_name,
                       d.post_date, d.content
                FROM club_discussions d
                JOIN students s ON d.author_id = s.student_id
                WHERE d.club_id = ? AND d.is_announcement = 1
                ORDER BY d.pinned DESC, d.post_date DESC
                ''', (club_id,))

                announcements = cursor.fetchall()

                if not announcements:
                    print("No announcements found.")
                else:
                    print(f"\nClub Announcements:")
                    for ann in announcements:
                        print(f"\n📢 {ann[1]}")
                        print(f"   By: {ann[2]} {ann[3]} on {ann[4]}")
                        print(f"   {ann[5][:200]}{'...' if len(ann[5]) > 200 else ''}")
                        print("-" * 60)

            elif action == '3':
                # Create new discussion
                title = input("Discussion title: ").strip()
                if not title:
                    print("Title cannot be empty.")
                    continue

                content = input("Discussion content: ").strip()
                if not content:
                    print("Content cannot be empty.")
                    continue

                post_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO club_discussions (
                    club_id, author_id, title, content, post_date, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (club_id, student_id, title, content, post_date, post_date))

                conn.commit()
                print("Discussion created successfully!")

            elif action == '4':
                # Search discussions
                search_term = input("Enter search term: ").strip()
                if not search_term:
                    print("Search term cannot be empty.")
                    continue

                cursor.execute('''
                SELECT d.discussion_id, d.title, s.first_name, s.last_name,
                       d.post_date, d.is_announcement
                FROM club_discussions d
                JOIN students s ON d.author_id = s.student_id
                WHERE d.club_id = ? AND (d.title LIKE ? OR d.content LIKE ?)
                ORDER BY d.post_date DESC
                ''', (club_id, f'%{search_term}%', f'%{search_term}%'))

                results = cursor.fetchall()

                if not results:
                    print("No matching discussions found.")
                else:
                    print(f"\nSearch Results for '{search_term}':")
                    print(f"{'ID':<6} {'Title':<40} {'Author':<20} {'Date':<12}")
                    print("-" * 80)

                    for result in results:
                        print(f"{result[0]:<6} {result[1][:40]:<40} {result[2]} {result[3]:<20} {result[4][:10]:<12}")

            elif action == '5' and user_role in ['President', 'Secretary']:
                # Create announcement
                title = input("Announcement title: ").strip()
                if not title:
                    print("Title cannot be empty.")
                    continue

                content = input("Announcement content: ").strip()
                if not content:
                    print("Content cannot be empty.")
                    continue

                pin_choice = input("Pin this announcement? (y/n): ").strip().lower()
                pinned = pin_choice == 'y'

                post_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO club_discussions (
                    club_id, author_id, title, content, post_date, last_updated,
                    is_announcement, pinned
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (club_id, student_id, title, content, post_date, post_date, 1, pinned))

                conn.commit()
                print("Announcement created successfully!")

            elif action == '6' and user_role in ['President', 'Secretary']:
                # Manage discussions
                manage_discussions_admin(club_id, cursor, conn)

            elif action == str(max_option):
                break

            else:
                print("Invalid choice.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def view_discussion_details(discussion_id, cursor, viewer_id, viewer_role):
    """View detailed discussion content"""
    try:
        cursor.execute('''
        SELECT d.title, d.content, s.first_name, s.last_name, d.post_date,
               d.last_updated, d.is_announcement, d.pinned, d.author_id
        FROM club_discussions d
        JOIN students s ON d.author_id = s.student_id
        WHERE d.discussion_id = ?
        ''', (discussion_id,))

        discussion = cursor.fetchone()

        if not discussion:
            print("Discussion not found.")
            return

        print(f"\n{'='*60}")
        if discussion[6]:  # is_announcement
            print(f"📢 ANNOUNCEMENT: {discussion[0]}")
        else:
            print(f"💬 DISCUSSION: {discussion[0]}")

        if discussion[7]:  # pinned
            print("📌 PINNED")

        print(f"By: {discussion[2]} {discussion[3]}")
        print(f"Posted: {discussion[4]}")
        if discussion[5] != discussion[4]:
            print(f"Last updated: {discussion[5]}")

        print(f"\n{discussion[1]}")
        print("="*60)

        # Show options if user is author or has admin rights
        if discussion[8] == viewer_id or viewer_role in ['President', 'Secretary']:
            print("\nOptions:")
            print("1. Edit")
            print("2. Delete")
            print("3. Toggle pin status")

            action = input("Choose action (or press Enter to return): ").strip()

            if action == '1':
                new_content = input("New content: ").strip()
                if new_content:
                    update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute('''
                    UPDATE club_discussions
                    SET content = ?, last_updated = ?
                    WHERE discussion_id = ?
                    ''', (new_content, update_time, discussion_id))
                    print("Discussion updated.")

            elif action == '2':
                confirm = input("Are you sure you want to delete this discussion? (y/n): ").strip().lower()
                if confirm == 'y':
                    cursor.execute('DELETE FROM club_discussions WHERE discussion_id = ?', (discussion_id,))
                    print("Discussion deleted.")

            elif action == '3':
                new_pin_status = not discussion[7]
                cursor.execute('''
                UPDATE club_discussions
                SET pinned = ?
                WHERE discussion_id = ?
                ''', (new_pin_status, discussion_id))
                pin_text = "pinned" if new_pin_status else "unpinned"
                print(f"Discussion {pin_text}.")

    except Exception as e:
        print(f"Error viewing discussion: {e}")


def manage_discussions_admin(club_id, cursor, conn):
    """Admin interface for managing discussions"""
    try:
        while True:
            print(f"\nDiscussion Management")
            print("1. View all discussions")
            print("2. Delete discussion")
            print("3. Pin/Unpin discussion")
            print("4. Convert discussion to announcement")
            print("5. Return to discussions menu")

            action = input("Choose an action: ").strip()

            if action == '1':
                cursor.execute('''
                SELECT d.discussion_id, d.title, s.first_name, s.last_name,
                       d.post_date, d.is_announcement, d.pinned
                FROM club_discussions d
                JOIN students s ON d.author_id = s.student_id
                WHERE d.club_id = ?
                ORDER BY d.post_date DESC
                ''', (club_id,))

                discussions = cursor.fetchall()

                print(f"{'ID':<6} {'Title':<30} {'Author':<20} {'Date':<12} {'Type':<8} {'Pin':<6}")
                print("-" * 85)

                for disc in discussions:
                    disc_type = "Ann" if disc[5] else "Disc"
                    pinned = "Yes" if disc[6] else "No"
                    print(f"{disc[0]:<6} {disc[1][:30]:<30} {disc[2]} {disc[3]:<20} {disc[4][:10]:<12} {disc_type:<8} {pinned:<6}")

            elif action == '2':
                disc_id = input("Enter discussion ID to delete: ").strip()
                if disc_id.isdigit():
                    confirm = input("Are you sure you want to delete this discussion? (y/n): ").strip().lower()
                    if confirm == 'y':
                        cursor.execute('DELETE FROM club_discussions WHERE discussion_id = ? AND club_id = ?',
                                     (disc_id, club_id))
                        if cursor.rowcount > 0:
                            conn.commit()
                            print("Discussion deleted.")
                        else:
                            print("Discussion not found.")

            elif action == '3':
                disc_id = input("Enter discussion ID to toggle pin status: ").strip()
                if disc_id.isdigit():
                    cursor.execute('''
                    UPDATE club_discussions
                    SET pinned = NOT pinned
                    WHERE discussion_id = ? AND club_id = ?
                    ''', (disc_id, club_id))

                    if cursor.rowcount > 0:
                        conn.commit()
                        print("Pin status toggled.")
                    else:
                        print("Discussion not found.")

            elif action == '4':
                disc_id = input("Enter discussion ID to convert to announcement: ").strip()
                if disc_id.isdigit():
                    cursor.execute('''
                    UPDATE club_discussions
                    SET is_announcement = 1
                    WHERE discussion_id = ? AND club_id = ?
                    ''', (disc_id, club_id))

                    if cursor.rowcount > 0:
                        conn.commit()
                        print("Discussion converted to announcement.")
                    else:
                        print("Discussion not found.")

            elif action == '5':
                break

            else:
                print("Invalid choice.")

    except Exception as e:
        print(f"Error in discussion management: {e}")
