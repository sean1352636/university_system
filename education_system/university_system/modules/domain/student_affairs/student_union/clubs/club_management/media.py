from education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management._imports import (
    datetime, sqlite3, get_connection,
)
import education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management._imports as _state


def manage_club_media():
    """Manage club photo/video sharing"""
    auth = _state.auth

    if not auth or not auth.current_user:
        print("You must be logged in to manage club media.")
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

        choice = input("Select a club to manage media (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(clubs):
            print("Invalid selection.")
            conn.close()
            return

        selected_club = clubs[int(choice)-1]
        club_id = selected_club[0]
        club_name = selected_club[1]

        while True:
            print(f"\nClub Media - {club_name}")
            print("1. View recent media")
            print("2. Upload new media")
            print("3. View event galleries")
            print("4. Search media")
            print("5. Return to previous menu")

            action = input("Choose an action: ").strip()

            if action == '1':
                # View recent media
                cursor.execute('''
                SELECT m.media_id, m.file_path, m.file_type, m.caption,
                       s.first_name, s.last_name, m.upload_date, e.event_name
                FROM club_media m
                JOIN students s ON m.uploader_id = s.student_id
                LEFT JOIN union_events e ON m.event_id = e.event_id
                WHERE m.club_id = ?
                ORDER BY m.upload_date DESC
                LIMIT 20
                ''', (club_id,))

                media_files = cursor.fetchall()

                if not media_files:
                    print("No media files found.")
                else:
                    print(f"\nRecent Media:")
                    print(f"{'ID':<6} {'Type':<8} {'Caption':<30} {'Uploader':<20} {'Date':<12} {'Event':<20}")
                    print("-" * 100)

                    for media in media_files:
                        event_name = media[7] if media[7] else "General"
                        print(f"{media[0]:<6} {media[2]:<8} {media[3][:30]:<30} {media[4]} {media[5]:<20} {media[6][:10]:<12} {event_name[:20]:<20}")

            elif action == '2':
                # Upload new media
                file_path = input("File path: ").strip()
                if not file_path:
                    print("File path cannot be empty.")
                    continue

                # Determine file type from extension
                file_extension = file_path.split('.')[-1].lower() if '.' in file_path else ''
                if file_extension in ['jpg', 'jpeg', 'png', 'gif']:
                    file_type = 'image'
                elif file_extension in ['mp4', 'avi', 'mov', 'wmv']:
                    file_type = 'video'
                else:
                    file_type = input("File type (image/video/document): ").strip().lower()

                caption = input("Caption (optional): ").strip()

                # Link to event (optional)
                cursor.execute('''
                SELECT e.event_id, e.event_name
                FROM union_events e
                WHERE e.organizer_id = ? AND e.event_date >= date('now', '-30 days')
                ORDER BY e.event_date DESC
                LIMIT 10
                ''', (club_id,))

                recent_events = cursor.fetchall()

                event_id = None
                if recent_events:
                    print("\nLink to recent event (optional):")
                    print("0. No event")
                    for i, event in enumerate(recent_events):
                        print(f"{i+1}. {event[1]}")

                    event_choice = input("Select event (enter number): ").strip()
                    if event_choice.isdigit() and 1 <= int(event_choice) <= len(recent_events):
                        event_id = recent_events[int(event_choice)-1][0]

                upload_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO club_media (
                    club_id, uploader_id, event_id, file_path, file_type, caption, upload_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (club_id, student_id, event_id, file_path, file_type, caption, upload_date))

                conn.commit()
                print("Media uploaded successfully!")

            elif action == '3':
                # View event galleries
                cursor.execute('''
                SELECT e.event_id, e.event_name, COUNT(m.media_id) as media_count
                FROM union_events e
                LEFT JOIN club_media m ON e.event_id = m.event_id
                WHERE e.organizer_id = ?
                GROUP BY e.event_id, e.event_name
                HAVING COUNT(m.media_id) > 0
                ORDER BY e.event_date DESC
                ''', (club_id,))

                events_with_media = cursor.fetchall()

                if not events_with_media:
                    print("No events with media found.")
                else:
                    print(f"\nEvents with Media:")
                    for i, event in enumerate(events_with_media):
                        print(f"{i+1}. {event[1]} ({event[2]} files)")

                    event_choice = input("Select event to view gallery (enter number): ").strip()
                    if event_choice.isdigit() and 1 <= int(event_choice) <= len(events_with_media):
                        selected_event = events_with_media[int(event_choice)-1]

                        cursor.execute('''
                        SELECT m.media_id, m.file_path, m.file_type, m.caption,
                               s.first_name, s.last_name, m.upload_date
                        FROM club_media m
                        JOIN students s ON m.uploader_id = s.student_id
                        WHERE m.event_id = ?
                        ORDER BY m.upload_date
                        ''', (selected_event[0],))

                        event_media = cursor.fetchall()

                        print(f"\nGallery for {selected_event[1]}:")
                        for media in event_media:
                            print(f"- {media[2]}: {media[1]}")
                            if media[3]:
                                print(f"  Caption: {media[3]}")
                            print(f"  Uploaded by: {media[4]} {media[5]} on {media[6]}")
                            print()

            elif action == '4':
                # Search media
                search_term = input("Enter search term: ").strip()
                if not search_term:
                    print("Search term cannot be empty.")
                    continue

                cursor.execute('''
                SELECT m.media_id, m.file_path, m.file_type, m.caption,
                       s.first_name, s.last_name, m.upload_date
                FROM club_media m
                JOIN students s ON m.uploader_id = s.student_id
                WHERE m.club_id = ? AND (m.caption LIKE ? OR m.file_path LIKE ?)
                ORDER BY m.upload_date DESC
                ''', (club_id, f'%{search_term}%', f'%{search_term}%'))

                results = cursor.fetchall()

                if not results:
                    print("No matching media found.")
                else:
                    print(f"Search results for '{search_term}':")
                    for result in results:
                        print(f"- {result[1]} ({result[2]})")
                        if result[3]:
                            print(f"  Caption: {result[3]}")
                        print(f"  By: {result[4]} {result[5]} on {result[6]}")
                        print()

            elif action == '5':
                break

            else:
                print("Invalid choice.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
