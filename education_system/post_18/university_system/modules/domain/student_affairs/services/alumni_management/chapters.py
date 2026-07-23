from datetime import datetime
from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.core import get_db_connection, safe_execute, auth
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.gamification import award_engagement_points


def view_my_chapters():
    """View chapters user belongs to"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to view your chapters.")
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT ac.chapter_id, ac.name, ac.location, acm.role, acm.join_date
            FROM alumni_chapters ac
            JOIN alumni_chapter_members acm ON ac.chapter_id = acm.chapter_id
            WHERE acm.user_id = ?
            ORDER BY acm.join_date DESC
        ''', (auth.current_user['user_id'],))

        chapters = cursor.fetchall()
        conn.close()

        if not chapters:
            print("\nYou are not a member of any chapters yet.")
            return

        print("\n--- Your Chapters ---")
        print(f"{'Chapter ID':<15} {'Name':<25} {'Location':<20} {'Your Role':<15} {'Join Date':<15}")
        print("-" * 95)
        for chapter in chapters:
            print(f"{chapter[0]:<15} {chapter[1]:<25} {chapter[2]:<20} {chapter[3]:<15} {chapter[4]:<15}")
    except Exception as e:
        print(f"Error viewing chapters: {e}")

def admin_manage_chapters():
    """Admin management of chapters"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to manage chapters.")
        return

    if not auth.check_permission('manage_alumni'):
        print("You don't have permission to manage chapters.")
        return

    try:
        print("\n--- Manage Chapters ---")
        print("1. Create New Chapter")
        print("2. View All Chapters")
        print("3. Update Chapter")
        print("4. Delete Chapter")
        choice = input("Enter your choice (1-4): ")

        conn = get_db_connection()
        cursor = conn.cursor()

        if choice == '1':
            name = input("Enter chapter name: ")
            location = input("Enter location: ")
            description = input("Enter description: ")

            cursor.execute('''
                INSERT INTO alumni_chapters (name, location, description, created_date, status)
                VALUES (?, ?, ?, ?, 'active')
            ''', (name, location, description, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            conn.commit()
            print("Chapter created successfully!")

        elif choice == '2':
            cursor.execute('SELECT chapter_id, name, location, status FROM alumni_chapters')
            chapters = cursor.fetchall()

            print("\n--- All Chapters ---")
            print(f"{'Chapter ID':<15} {'Name':<30} {'Location':<25} {'Status':<12}")
            print("-" * 85)
            for chapter in chapters:
                print(f"{chapter[0]:<15} {chapter[1]:<30} {chapter[2]:<25} {chapter[3]:<12}")

        elif choice == '3':
            chapter_id = input("Enter chapter ID to update: ")
            new_name = input("Enter new name (or press Enter to skip): ")
            new_location = input("Enter new location (or press Enter to skip): ")

            if new_name:
                cursor.execute('UPDATE alumni_chapters SET name = ? WHERE chapter_id = ?', (new_name, chapter_id))
            if new_location:
                cursor.execute('UPDATE alumni_chapters SET location = ? WHERE chapter_id = ?', (new_location, chapter_id))

            conn.commit()
            print("Chapter updated successfully!")

        elif choice == '4':
            chapter_id = input("Enter chapter ID to delete: ")
            confirm = input(f"Are you sure you want to delete chapter {chapter_id}? (yes/no): ")

            if confirm.lower() == 'yes':
                cursor.execute('DELETE FROM alumni_chapters WHERE chapter_id = ?', (chapter_id,))
                conn.commit()
                print("Chapter deleted.")

        conn.close()
    except Exception as e:
        print(f"Error managing chapters: {e}")

def manage_regional_chapters():
    """Manage regional alumni chapters"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to manage regional chapters.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\nRegional Chapter Management")
    print("===========================")
    print("1. View All Chapters")
    print("2. Create New Chapter")
    print("3. Join a Chapter")
    print("4. My Chapters")
    if auth.check_permission('manage_social_features'):
        print("5. Manage Chapter (Admin)")

    choice = input("Enter your choice: ")

    if choice == '1':
        view_regional_chapters(cursor)
    elif choice == '2':
        create_regional_chapter(cursor)
    elif choice == '3':
        join_regional_chapter(cursor)
    elif choice == '4':
        view_my_chapters(cursor)
    elif choice == '5' and auth.check_permission('manage_social_features'):
        admin_manage_chapters(cursor)
    else:
        print("Invalid choice.")

    conn.close()

def view_regional_chapters(cursor):
    """View all regional chapters"""
    cursor.execute('''
        SELECT c.*, a.first_name, a.last_name
        FROM regional_chapters c
        LEFT JOIN alumni a ON c.coordinator_id = a.alumni_id
        ORDER BY c.chapter_name
    ''')

    chapters = cursor.fetchall()

    if not chapters:
        print("No regional chapters found.")
        return

    print("\nRegional Alumni Chapters:")
    print("-" * 60)

    for chapter in chapters:
        coordinator_name = f"{chapter[7]} {chapter[8]}" if chapter[7] else "No coordinator"

        print(f"Chapter: {chapter[1]}")
        print(f"Location: {chapter[2]}")
        print(f"Coordinator: {coordinator_name}")
        print(f"Members: {chapter[6]}")
        print(f"Description: {chapter[4]}")
        print(f"Created: {chapter[5]}")
        print("-" * 60)

def create_regional_chapter(cursor):
    """Create a new regional chapter"""
    global auth

    if not auth.check_permission('manage_social_features'):
        print("You don't have permission to create regional chapters.")
        return

    print("\nCreate Regional Chapter")
    print("=======================")

    chapter_name = input("Chapter Name: ")
    while not chapter_name:
        print("Error: Chapter name is required.")
        chapter_name = input("Chapter Name: ")

    location = input("Chapter Location (city, state/country): ")
    while not location:
        print("Error: Location is required.")
        location = input("Chapter Location: ")

    description = input("Chapter Description: ")

    coordinator_id = input("Coordinator Alumni ID: ")

    # Verify coordinator exists
    cursor.execute('SELECT alumni_id FROM alumni WHERE alumni_id = ?', (coordinator_id,))
    if not cursor.fetchone():
        print("Coordinator not found.")
        return

    # Insert chapter
    cursor.execute('''
        INSERT INTO regional_chapters
        (chapter_name, location, coordinator_id, description, created_date)
        VALUES (?, ?, ?, ?, ?)
    ''', (chapter_name, location, coordinator_id, description,
          datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    chapter_id = cursor.lastrowid

    # Add coordinator as first member
    cursor.execute('''
        INSERT INTO chapter_memberships (chapter_id, alumni_id, join_date, role)
        VALUES (?, ?, ?, ?)
    ''', (chapter_id, coordinator_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'coordinator'))

    # Update member count
    cursor.execute('UPDATE regional_chapters SET member_count = 1 WHERE chapter_id = ?', (chapter_id,))

    print(f"\nRegional chapter created successfully! Chapter ID: {chapter_id}")

def join_regional_chapter(cursor):
    """Join a regional chapter"""
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

    # Show available chapters
    cursor.execute('SELECT * FROM regional_chapters ORDER BY chapter_name')
    chapters = cursor.fetchall()

    if not chapters:
        print("No regional chapters available.")
        return

    print("\nAvailable Regional Chapters:")
    for i, chapter in enumerate(chapters, 1):
        print(f"{i}. {chapter[1]} ({chapter[2]}) - {chapter[6]} members")

    try:
        chapter_choice = int(input(f"Select chapter to join (1-{len(chapters)}): "))
        if 1 <= chapter_choice <= len(chapters):
            selected_chapter = chapters[chapter_choice - 1]
            chapter_id = selected_chapter[0]
        else:
            print("Invalid selection.")
            return
    except ValueError:
        print("Invalid input.")
        return

    # Check if already a member
    cursor.execute('''
        SELECT * FROM chapter_memberships
        WHERE chapter_id = ? AND alumni_id = ?
    ''', (chapter_id, alumni_id))

    if cursor.fetchone():
        print("You are already a member of this chapter.")
        return

    # Join chapter
    cursor.execute('''
        INSERT INTO chapter_memberships (chapter_id, alumni_id, join_date, role)
        VALUES (?, ?, ?, ?)
    ''', (chapter_id, alumni_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'member'))

    # Update member count
    cursor.execute('''
        UPDATE regional_chapters
        SET member_count = member_count + 1
        WHERE chapter_id = ?
    ''', (chapter_id,))

    # Award engagement points
    award_engagement_points(alumni_id, 'chapter_joined', 15)

    print(f"Successfully joined {selected_chapter[1]}!")
