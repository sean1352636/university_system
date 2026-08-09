from datetime import datetime
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.domain.learners.alumni.core import get_db_connection, safe_execute, auth
from education_system.systems.university.domain.learners.alumni.gamification import award_engagement_points


def view_my_photos():
    """View photos uploaded by current user"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to view your photos.")
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT photo_id, title, upload_date, status
            FROM alumni_photos
            WHERE user_id = ?
            ORDER BY upload_date DESC
        ''', (auth.current_user['user_id'],))

        photos = cursor.fetchall()
        conn.close()

        if not photos:
            print("\nYou haven't uploaded any photos yet.")
            return

        print("\n--- Your Photos ---")
        print(f"{'Photo ID':<12} {'Title':<30} {'Upload Date':<20} {'Status':<15}")
        print("-" * 80)
        for photo in photos:
            print(f"{photo[0]:<12} {photo[1]:<30} {photo[2]:<20} {photo[3]:<15}")
    except Exception as e:
        print(f"Error viewing photos: {e}")

def moderate_photos():
    """Moderate photos in gallery"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to moderate photos.")
        return

    if not auth.check_permission('manage_alumni'):
        print("You don't have permission to moderate photos.")
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT photo_id, title, user_id, upload_date, status
            FROM alumni_photos
            WHERE status = 'pending'
            ORDER BY upload_date ASC
        ''')

        photos = cursor.fetchall()

        if not photos:
            print("\nNo photos pending moderation.")
            conn.close()
            return

        print("\n--- Photos Pending Moderation ---")
        for photo in photos:
            print(f"\nPhoto ID: {photo[0]}")
            print(f"Title: {photo[1]}")
            print(f"Uploaded by: {photo[2]}")
            print(f"Upload Date: {photo[3]}")

            action = input("Action (approve/reject/skip): ").lower()

            if action == 'approve':
                cursor.execute('UPDATE alumni_photos SET status = "approved" WHERE photo_id = ?', (photo[0],))
                print(f"Photo {photo[0]} approved.")
            elif action == 'reject':
                reason = input("Enter rejection reason: ")
                cursor.execute('UPDATE alumni_photos SET status = "rejected" WHERE photo_id = ?', (photo[0],))
                print(f"Photo {photo[0]} rejected.")
            elif action == 'skip':
                continue

        conn.commit()
        conn.close()
        print("\nModeration complete!")
    except Exception as e:
        print(f"Error moderating photos: {e}")

def manage_photo_gallery():
    """Manage event photo gallery"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to manage photos.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\nPhoto Gallery Management")
    print("========================")
    print("1. View Photo Gallery")
    print("2. Upload Photos")
    print("3. My Uploaded Photos")
    if auth.check_permission('manage_content'):
        print("4. Moderate Photos")

    choice = input("Enter your choice: ")

    if choice == '1':
        view_photo_gallery(cursor)
    elif choice == '2':
        upload_photos(cursor)
    elif choice == '3':
        view_my_photos(cursor)
    elif choice == '4' and auth.check_permission('manage_content'):
        moderate_photos(cursor)
    else:
        print("Invalid choice.")

    conn.close()

def view_photo_gallery(cursor):
    """View photo gallery by events"""
    # Get events with photos
    cursor.execute('''
        SELECT e.event_id, e.title, e.start_datetime, COUNT(p.photo_id) as photo_count
        FROM unified_events e
        LEFT JOIN photo_gallery p ON e.event_id = p.event_id
        WHERE e.source_type = 'alumni'
        GROUP BY e.event_id
        HAVING photo_count > 0
        ORDER BY e.start_datetime DESC
    ''')

    events_with_photos = cursor.fetchall()

    if not events_with_photos:
        print("No photos available in the gallery.")
        return

    print("\nEvents with Photos:")
    print("-" * 60)

    for i, (event_id, event_name, event_date, photo_count) in enumerate(events_with_photos, 1):
        print(f"{i}. {event_name} ({event_date}) - {photo_count} photos")

    try:
        event_choice = int(input(f"\nSelect event to view photos (1-{len(events_with_photos)}): "))
        if 1 <= event_choice <= len(events_with_photos):
            selected_event = events_with_photos[event_choice - 1]
            view_event_photos(selected_event[0], cursor)
        else:
            print("Invalid selection.")
    except ValueError:
        print("Invalid input.")

def view_event_photos(event_id, cursor):
    """View photos for a specific event"""
    cursor.execute('''
        SELECT p.*, a.first_name, a.last_name
        FROM photo_gallery p
        JOIN alumni a ON p.uploaded_by = a.alumni_id
        WHERE p.event_id = ?
        ORDER BY p.is_featured DESC, p.upload_date DESC
    ''', (event_id,))

    photos = cursor.fetchall()

    if photos:
        print(f"\nPhotos for this event ({len(photos)} total):")
        print("-" * 50)

        for photo in photos:
            uploader_name = f"{photo[6]} {photo[7]}"
            featured_mark = "⭐ " if photo[5] else ""

            print(f"{featured_mark}Photo: {photo[3]}")
            print(f"Uploaded by: {uploader_name}")
            print(f"Caption: {photo[4]}")
            print(f"Upload Date: {photo[5]}")
            print(f"Path: {photo[3]}")  # In real implementation, this would display the actual image
            print("-" * 50)
    else:
        print("No photos found for this event.")

def upload_photos(cursor):
    """Upload photos to event gallery"""
    global auth

    # Get current user's alumni ID
    alumni_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        alumni_id = result[0]
    else:
        print("Alumni profile not found for current user.")
        return

    # Get recent events
    cursor.execute('''
        SELECT event_id, title, start_datetime
        FROM unified_events
        WHERE source_type = 'alumni' AND start_datetime >= date('now', '-30 days')
        ORDER BY start_datetime DESC
    ''')

    recent_events = cursor.fetchall()

    if not recent_events:
        print("No recent events available for photo upload.")
        return

    print("\nSelect Event for Photo Upload:")
    for i, (event_id, event_name, event_date) in enumerate(recent_events, 1):
        print(f"{i}. {event_name} ({event_date})")

    try:
        event_choice = int(input(f"Select event (1-{len(recent_events)}): "))
        if 1 <= event_choice <= len(recent_events):
            selected_event = recent_events[event_choice - 1]
            event_id = selected_event[0]
        else:
            print("Invalid selection.")
            return
    except ValueError:
        print("Invalid input.")
        return

    print(f"\nUploading photos for: {selected_event[1]}")

    # In a real implementation, this would handle actual file uploads
    # For now, we'll simulate the process
    photo_path = input("Enter photo file path: ")
    caption = input("Enter photo caption: ")

    if not photo_path:
        print("Photo path is required.")
        return

    # Insert photo record
    cursor.execute('''
        INSERT INTO photo_gallery (event_id, uploaded_by, photo_path, caption, upload_date)
        VALUES (?, ?, ?, ?, ?)
    ''', (event_id, alumni_id, photo_path, caption, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    # Award engagement points
    award_engagement_points(alumni_id, 'photo_uploaded', 5)

    print("Photo uploaded successfully to the gallery!")
