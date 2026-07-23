from datetime import datetime
from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.core import safe_execute, auth
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.gamification import award_engagement_points


def create_alumni_story():
    """Create an alumni success story or spotlight"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to create alumni stories.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    # Get current user's alumni ID
    alumni_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        alumni_id = result[0]
    elif auth.check_permission('manage_social_features'):
        # Staff can create stories for any alumni
        alumni_id = input("Enter Alumni ID for the story: ")
        cursor.execute('SELECT alumni_id FROM alumni WHERE alumni_id = ?', (alumni_id,))
        if not cursor.fetchone():
            print("Alumni not found.")
            conn.close()
            return
    else:
        print("Alumni profile not found for current user.")
        conn.close()
        return

    print("\nCreate Alumni Story")
    print("===================")

    # Story types
    story_types = [
        "Career Achievement", "Community Service", "Entrepreneurship",
        "Research & Innovation", "Personal Journey", "Alumni Spotlight",
        "Industry Leadership", "Social Impact", "Education & Teaching"
    ]

    print("\nStory Types:")
    for i, stype in enumerate(story_types, 1):
        print(f"{i}. {stype}")

    try:
        type_choice = int(input("Select story type: "))
        if 1 <= type_choice <= len(story_types):
            story_type = story_types[type_choice - 1]
        else:
            story_type = "Alumni Spotlight"
    except ValueError:
        story_type = "Alumni Spotlight"

    title = input("Story Title: ")
    while not title:
        print("Error: Title is required.")
        title = input("Story Title: ")

    print("\nStory Content (press Enter twice to finish):")
    content_lines = []
    while True:
        line = input()
        if line == "" and (not content_lines or content_lines[-1] == ""):
            break
        content_lines.append(line)

    content = "\n".join(content_lines)

    if not content:
        print("Error: Story content is required.")
        conn.close()
        return

    # Categories
    categories = [
        "Professional Success", "Community Impact", "Innovation",
        "Leadership", "Inspiration", "Education", "Technology", "Arts"
    ]

    print("\nStory Categories:")
    for i, category in enumerate(categories, 1):
        print(f"{i}. {category}")

    try:
        cat_choice = int(input("Select category: "))
        if 1 <= cat_choice <= len(categories):
            category = categories[cat_choice - 1]
        else:
            category = "Professional Success"
    except ValueError:
        category = "Professional Success"

    is_featured = False
    if auth.check_permission('manage_social_features'):
        is_featured = input("Feature this story? (y/n): ").lower() == 'y'

    # Insert story
    cursor.execute('''
        INSERT INTO alumni_stories
        (alumni_id, title, content, story_type, publish_date, is_featured, category)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (alumni_id, title, content, story_type,
          datetime.now().strftime('%Y-%m-%d %H:%M:%S'), is_featured, category))

    story_id = cursor.lastrowid

    # Award engagement points
    award_engagement_points(alumni_id, 'story_created', 30)

    conn.commit()
    conn.close()

    print(f"\nAlumni story created successfully! Story ID: {story_id}")
    if is_featured:
        print("Story has been featured on the main page.")

def view_alumni_stories():
    """View alumni stories and spotlights"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to view alumni stories.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\nAlumni Stories")
    print("==============")
    print("1. View Featured Stories")
    print("2. View Recent Stories")
    print("3. Search Stories by Category")
    print("4. Search Stories by Alumni")

    choice = input("Enter your choice: ")

    if choice == '1':
        # Featured stories
        cursor.execute('''
            SELECT s.*, a.first_name, a.last_name, a.graduation_year
            FROM alumni_stories s
            JOIN alumni a ON s.alumni_id = a.alumni_id
            WHERE s.is_featured = 1
            ORDER BY s.publish_date DESC
        ''')

    elif choice == '2':
        # Recent stories
        cursor.execute('''
            SELECT s.*, a.first_name, a.last_name, a.graduation_year
            FROM alumni_stories s
            JOIN alumni a ON s.alumni_id = a.alumni_id
            ORDER BY s.publish_date DESC
            LIMIT 20
        ''')

    elif choice == '3':
        # Search by category
        categories = [
            "Professional Success", "Community Impact", "Innovation",
            "Leadership", "Inspiration", "Education", "Technology", "Arts"
        ]

        print("\nStory Categories:")
        for i, category in enumerate(categories, 1):
            print(f"{i}. {category}")

        try:
            cat_choice = int(input("Select category: "))
            if 1 <= cat_choice <= len(categories):
                selected_category = categories[cat_choice - 1]
                cursor.execute('''
                    SELECT s.*, a.first_name, a.last_name, a.graduation_year
                    FROM alumni_stories s
                    JOIN alumni a ON s.alumni_id = a.alumni_id
                    WHERE s.category = ?
                    ORDER BY s.publish_date DESC
                ''', (selected_category,))
            else:
                print("Invalid category.")
                conn.close()
                return
        except ValueError:
            print("Invalid input.")
            conn.close()
            return

    elif choice == '4':
        # Search by alumni
        search_name = input("Enter alumni name (partial match): ")
        cursor.execute('''
            SELECT s.*, a.first_name, a.last_name, a.graduation_year
            FROM alumni_stories s
            JOIN alumni a ON s.alumni_id = a.alumni_id
            WHERE a.first_name LIKE ? OR a.last_name LIKE ?
            ORDER BY s.publish_date DESC
        ''', (f'%{search_name}%', f'%{search_name}%'))
    else:
        print("Invalid choice.")
        conn.close()
        return

    stories = cursor.fetchall()

    if not stories:
        print("No stories found.")
    else:
        print(f"\nFound {len(stories)} stories:")
        print("-" * 80)

        for i, story in enumerate(stories, 1):
            author_name = f"{story[9]} {story[10]}"
            graduation_year = story[11]

            print(f"{i}. {story[2]} ⭐" if story[6] else f"{i}. {story[2]}")
            print(f"   By: {author_name} (Class of {graduation_year})")
            print(f"   Type: {story[4]} | Category: {story[8]}")
            print(f"   Published: {story[5]}")
            print(f"   Views: {story[7]}")
            print(f"   {story[3][:150]}...")
            print("-" * 80)

        # Option to read full story
        read_choice = input(f"\nEnter story number to read (1-{len(stories)}) or press Enter to continue: ")
        if read_choice.isdigit():
            story_index = int(read_choice) - 1
            if 0 <= story_index < len(stories):
                read_full_story(stories[story_index], cursor)

    conn.close()

def read_full_story(story, cursor):
    """Read full alumni story and update view count"""
    print(f"\n{'='*60}")
    print(f"Title: {story[2]}")
    print(f"Type: {story[4]} | Category: {story[8]}")
    print(f"Published: {story[5]}")
    if story[6]:  # is_featured
        print("⭐ FEATURED STORY")
    print(f"{'='*60}")
    print(story[3])
    print(f"{'='*60}")

    # Update view count
    cursor.execute('''
        UPDATE alumni_stories
        SET view_count = view_count + 1
        WHERE story_id = ?
    ''', (story[0],))
