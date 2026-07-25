from datetime import datetime
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.domain.learners.alumni.core import safe_execute, auth
from education_system.systems.university.domain.learners.alumni.gamification import award_engagement_points


def manage_alumni_forum():
    """Manage alumni forum discussions"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to access the forum.")
        return

    if not auth.check_permission('access_alumni_directory'):
        print("You don't have permission to access the forum.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    while True:
        print("\nAlumni Forum")
        print("============")
        print("1. View Recent Posts")
        print("2. Create New Post")
        print("3. Search Posts")
        print("4. My Posts")
        if auth.check_permission('moderate_forum'):
            print("5. Moderate Posts")
        print("0. Return to Main Menu")

        choice = input("Enter your choice: ")

        if choice == '1':
            view_forum_posts(cursor)
        elif choice == '2':
            create_forum_post(cursor)
        elif choice == '3':
            search_forum_posts(cursor)
        elif choice == '4':
            view_my_forum_posts(cursor)
        elif choice == '5' and auth.check_permission('moderate_forum'):
            moderate_forum_posts(cursor)
        elif choice == '0':
            break
        else:
            print("Invalid choice.")

    conn.close()

def view_forum_posts(cursor):
    """View recent forum posts"""
    cursor.execute('''
        SELECT p.*, a.first_name, a.last_name
        FROM alumni_forum p
        JOIN alumni a ON p.author_id = a.alumni_id
        ORDER BY p.post_date DESC
        LIMIT 20
    ''')

    posts = cursor.fetchall()

    if not posts:
        print("No forum posts found.")
        return

    print("\nRecent Forum Posts:")
    print("-" * 80)

    for post in posts:
        author_name = f"{post[10]} {post[11]}"
        print(f"Title: {post[2]}")
        print(f"Author: {author_name}")
        print(f"Category: {post[4]}")
        print(f"Date: {post[5]}")
        print(f"Replies: {post[7]} | Views: {post[8]}")
        if post[9]:  # is_pinned
            print("📌 PINNED")
        print(f"Content: {post[3][:100]}...")
        print("-" * 80)

    # Option to view a specific post
    view_choice = input("Enter post number to view details (or press Enter to continue): ")
    if view_choice.isdigit():
        post_index = int(view_choice) - 1
        if 0 <= post_index < len(posts):
            view_forum_post_details(posts[post_index], cursor)

def create_forum_post(cursor):
    """Create a new forum post"""
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

    print("\nCreate New Forum Post")
    print("=====================")

    categories = [
        "General Discussion", "Career Advice", "Networking", "Industry News",
        "Class Updates", "Events", "Mentorship", "Job Opportunities",
        "Alumni Spotlight", "Ask for Help"
    ]

    print("\nAvailable Categories:")
    for i, category in enumerate(categories, 1):
        print(f"{i}. {category}")

    try:
        cat_choice = int(input("Select category: "))
        if 1 <= cat_choice <= len(categories):
            category = categories[cat_choice - 1]
        else:
            category = "General Discussion"
    except ValueError:
        category = "General Discussion"

    title = input("Post Title: ")
    print("\nEnter post content (press Enter twice to finish):")
    content_lines = []
    while True:
        line = input()
        if line == "" and (not content_lines or content_lines[-1] == ""):
            break
        content_lines.append(line)

    content = "\n".join(content_lines)

    if not title or not content:
        print("Title and content are required.")
        return

    # Insert the post
    cursor.execute('''
        INSERT INTO alumni_forum (author_id, title, content, category, post_date, last_updated)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (alumni_id, title, content, category,
          datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
          datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    post_id = cursor.lastrowid

    # Award engagement points
    award_engagement_points(alumni_id, 'forum_post', 15)

    print(f"Forum post created successfully! Post ID: {post_id}")

def view_forum_post_details(post, cursor):
    """View detailed forum post with replies"""
    print(f"\n{'='*60}")
    print(f"Title: {post[2]}")
    print(f"Category: {post[4]}")
    print(f"Date: {post[5]}")
    print(f"{'='*60}")
    print(post[3])
    print(f"{'='*60}")

    # Get replies
    cursor.execute('''
        SELECT r.*, a.first_name, a.last_name
        FROM forum_replies r
        JOIN alumni a ON r.author_id = a.alumni_id
        WHERE r.post_id = ?
        ORDER BY r.reply_date
    ''', (post[0],))

    replies = cursor.fetchall()

    if replies:
        print(f"\nReplies ({len(replies)}):")
        for reply in replies:
            author_name = f"{reply[6]} {reply[7]}"
            print(f"\n{author_name} - {reply[4]}:")
            print(reply[3])

    # Update view count
    cursor.execute('''
        UPDATE alumni_forum
        SET view_count = view_count + 1
        WHERE post_id = ?
    ''', (post[0],))

    # Option to reply
    reply_choice = input("\nWould you like to reply to this post? (y/n): ").lower()
    if reply_choice == 'y':
        add_forum_reply(post[0], cursor)

def add_forum_reply(post_id, cursor):
    """Add a reply to a forum post"""
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

    print("\nAdd Reply")
    print("=========")
    print("Enter your reply (press Enter twice to finish):")
    content_lines = []
    while True:
        line = input()
        if line == "" and (not content_lines or content_lines[-1] == ""):
            break
        content_lines.append(line)

    content = "\n".join(content_lines)

    if not content:
        print("Reply content is required.")
        return

    # Insert the reply
    cursor.execute('''
        INSERT INTO forum_replies (post_id, author_id, content, reply_date)
        VALUES (?, ?, ?, ?)
    ''', (post_id, alumni_id, content, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    # Update reply count
    cursor.execute('''
        UPDATE alumni_forum
        SET reply_count = reply_count + 1, last_updated = ?
        WHERE post_id = ?
    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), post_id))

    # Award engagement points
    award_engagement_points(alumni_id, 'forum_reply', 5)

    print("Reply added successfully!")

def _get_current_alumni_id(cursor):
    """Resolve the logged-in user's alumni ID (usernames starting with 'A')."""
    global auth

    if not auth or not auth.current_user:
        return None

    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        return result[0]
    return None

def _display_forum_post_list(posts, cursor, heading):
    """Render a list of forum posts and let the user drill into one."""
    if not posts:
        print("No forum posts found.")
        return

    print(f"\n{heading}")
    print("-" * 80)

    for index, post in enumerate(posts, 1):
        author_name = f"{post[10]} {post[11]}"
        print(f"{index}. Title: {post[2]}")
        print(f"   Author: {author_name}")
        print(f"   Category: {post[4]}")
        print(f"   Date: {post[5]}")
        print(f"   Replies: {post[7]} | Views: {post[8]}")
        if post[9]:  # is_pinned
            print("   📌 PINNED")
        print(f"   Content: {post[3][:100]}...")
        print("-" * 80)

    view_choice = input("Enter post number to view details (or press Enter to continue): ")
    if view_choice.isdigit():
        post_index = int(view_choice) - 1
        if 0 <= post_index < len(posts):
            view_forum_post_details(posts[post_index], cursor)

def search_forum_posts(cursor):
    """Search forum posts by keyword across title, content and category."""
    keyword = input("\nEnter search keyword: ").strip()
    if not keyword:
        print("Search keyword is required.")
        return

    like = f"%{keyword}%"
    cursor.execute('''
        SELECT p.*, a.first_name, a.last_name
        FROM alumni_forum p
        JOIN alumni a ON p.author_id = a.alumni_id
        WHERE p.title LIKE ? OR p.content LIKE ? OR p.category LIKE ?
        ORDER BY p.is_pinned DESC, p.post_date DESC
        LIMIT 20
    ''', (like, like, like))

    posts = cursor.fetchall()
    _display_forum_post_list(posts, cursor, f"Search Results for '{keyword}':")

def view_my_forum_posts(cursor):
    """View forum posts authored by the current alumni user."""
    alumni_id = _get_current_alumni_id(cursor)
    if not alumni_id:
        print("Alumni profile not found for current user.")
        return

    cursor.execute('''
        SELECT p.*, a.first_name, a.last_name
        FROM alumni_forum p
        JOIN alumni a ON p.author_id = a.alumni_id
        WHERE p.author_id = ?
        ORDER BY p.post_date DESC
    ''', (alumni_id,))

    posts = cursor.fetchall()
    _display_forum_post_list(posts, cursor, "My Forum Posts:")

def moderate_forum_posts(cursor):
    """Moderator tools: pin/unpin or delete forum posts."""
    global auth

    if not auth or not auth.check_permission('moderate_forum'):
        print("You don't have permission to moderate the forum.")
        return

    cursor.execute('''
        SELECT p.*, a.first_name, a.last_name
        FROM alumni_forum p
        JOIN alumni a ON p.author_id = a.alumni_id
        ORDER BY p.is_pinned DESC, p.post_date DESC
        LIMIT 30
    ''')

    posts = cursor.fetchall()

    if not posts:
        print("No forum posts to moderate.")
        return

    print("\nModerate Forum Posts")
    print("=" * 80)
    for index, post in enumerate(posts, 1):
        pin_flag = "📌 " if post[9] else "   "
        author_name = f"{post[10]} {post[11]}"
        print(f"{index}. {pin_flag}{post[2]} — {author_name} ({post[4]}, {post[5]})")
    print("-" * 80)

    selection = input("Enter post number to moderate (or press Enter to cancel): ").strip()
    if not selection.isdigit():
        return

    post_index = int(selection) - 1
    if not (0 <= post_index < len(posts)):
        print("Invalid post number.")
        return

    post = posts[post_index]
    post_id = post[0]
    is_pinned = post[9]

    print(f"\nSelected: {post[2]}")
    print("1. Pin post" if not is_pinned else "1. Unpin post")
    print("2. Delete post")
    print("0. Cancel")

    action = input("Choose an action: ").strip()

    if action == '1':
        new_state = 0 if is_pinned else 1
        cursor.execute(
            'UPDATE alumni_forum SET is_pinned = ? WHERE post_id = ?',
            (new_state, post_id),
        )
        print("Post unpinned." if is_pinned else "Post pinned.")
    elif action == '2':
        confirm = input("Are you sure you want to delete this post? (y/n): ").strip().lower()
        if confirm == 'y':
            cursor.execute('DELETE FROM forum_replies WHERE post_id = ?', (post_id,))
            cursor.execute('DELETE FROM alumni_forum WHERE post_id = ?', (post_id,))
            print("Post and its replies have been deleted.")
        else:
            print("Deletion cancelled.")
    else:
        print("No action taken.")
