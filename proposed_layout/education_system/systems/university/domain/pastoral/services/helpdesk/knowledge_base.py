from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def manage_knowledge_base(auth):
    """Manage knowledge base articles"""
    if not auth or not auth.current_user:
        print("You must be logged in to manage knowledge base.")
        return

    while True:
        print("\nKnowledge Base Management")
        print("=========================")
        print("1. View articles")
        print("2. Create new article")
        print("3. Edit article")
        print("4. Search articles")
        print("5. Article statistics")
        print("6. Return to main menu")

        choice = input("\nEnter your choice: ").strip()

        if choice == '1':
            view_kb_articles(auth)
        elif choice == '2':
            if auth.check_permission('manage_tickets'):
                create_kb_article(auth)
            else:
                print("You don't have permission to create articles.")
        elif choice == '3':
            if auth.check_permission('manage_tickets'):
                edit_kb_article(auth)
            else:
                print("You don't have permission to edit articles.")
        elif choice == '4':
            search_kb_articles(auth)
        elif choice == '5':
            if auth.check_permission('view_all_tickets'):
                kb_statistics(auth)
            else:
                print("You don't have permission to view statistics.")
        elif choice == '6':
            return
        else:
            print("Invalid choice. Please try again.")

def view_kb_articles(auth):
    """View knowledge base articles"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT DISTINCT category FROM knowledge_base
    WHERE status = 'published' AND category IS NOT NULL
    ORDER BY category
    ''')
    categories = [row[0] for row in cursor.fetchall()]

    if categories:
        print("\nCategories:")
        print("0. All categories")
        for i, cat in enumerate(categories, 1):
            print(f"{i}. {cat}")

        cat_choice = input("Select category (0 for all): ").strip()

        where_clause = "WHERE status = 'published'"
        params = []

        try:
            if cat_choice != '0':
                cat_idx = int(cat_choice) - 1
                if 0 <= cat_idx < len(categories):
                    where_clause += " AND category = ?"
                    params.append(categories[cat_idx])
        except ValueError as e:
            logger.debug(f"Invalid knowledge base category input: {e}")

        cursor.execute('''
        SELECT article_id, title, category, views, helpful_votes, unhelpful_votes, updated_at
        FROM knowledge_base
        ''' + where_clause + '''
        ORDER BY helpful_votes DESC, views DESC
        ''', params)

        articles = cursor.fetchall()

        if articles:
            print("\nKnowledge Base Articles:")
            print("=" * 80)
            print(f"{'ID':<5} {'Title':<40} {'Category':<15} {'Views':<8} {'Rating':<10}")
            print("=" * 80)

            for article in articles:
                total_votes = article[4] + article[5]
                rating = f"{article[4]}/{total_votes}" if total_votes > 0 else "No votes"
                print(f"{article[0]:<5} {article[1][:38]:<40} {article[2][:13]:<15} "
                      f"{article[3]:<8} {rating:<10}")

            print("=" * 80)

            article_choice = input("\nEnter article ID to view (or press Enter to return): ")
            if article_choice:
                try:
                    article_id = int(article_choice)
                    view_kb_article_detail(article_id)
                except ValueError:
                    print("Invalid article ID.")
        else:
            print("No articles found.")

    conn.close()

def view_kb_article_detail(article_id):
    """View detailed knowledge base article"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT kb.*, u.username as author
    FROM knowledge_base kb
    LEFT JOIN users u ON kb.author_id = u.id
    WHERE kb.article_id = ?
    ''', (article_id,))

    article = cursor.fetchone()

    if article:
        print(f"\n{'='*60}")
        print(f"ARTICLE #{article[0]}: {article[1]}")
        print(f"{'='*60}")
        print(f"Category: {article[3] or 'Uncategorized'}")
        print(f"Author: {article[-1] or 'Unknown'}")
        print(f"Status: {article[6]}")
        print(f"Views: {article[7]}")
        print(f"Helpful votes: {article[8]}")
        print(f"Unhelpful votes: {article[9]}")
        print(f"Created: {article[11]}")
        print(f"Updated: {article[12]}")
        if article[4]:
            print(f"Tags: {article[4]}")
        print(f"\n{'-'*60}")
        print("CONTENT:")
        print(f"{'-'*60}")
        print(article[2])
        print(f"{'='*60}")

        cursor.execute('''
        UPDATE knowledge_base SET views = views + 1 WHERE article_id = ?
        ''', (article_id,))
        conn.commit()

        rating_choice = input("\nWas this article helpful? (y/n/skip): ").strip().lower()
        if rating_choice == 'y':
            cursor.execute('''
            UPDATE knowledge_base SET helpful_votes = helpful_votes + 1 WHERE article_id = ?
            ''', (article_id,))
            conn.commit()
            print("Thank you for your feedback!")
        elif rating_choice == 'n':
            cursor.execute('''
            UPDATE knowledge_base SET unhelpful_votes = unhelpful_votes + 1 WHERE article_id = ?
            ''', (article_id,))
            conn.commit()
            print("Thank you for your feedback!")
    else:
        print("Article not found.")

    conn.close()

def create_kb_article(auth):
    """Create new knowledge base article"""
    print("\nCreate Knowledge Base Article")
    print("=============================")

    title = input("Article title: ").strip()
    if not title:
        print("Title is required.")
        return

    category = input("Category: ").strip()
    tags = input("Tags (comma-separated): ").strip()

    print("\nEnter article content (type 'done' on a new line when finished):")
    content = ""
    while True:
        line = input()
        if line.lower() == 'done':
            break
        content += line + "\n"

    if not content.strip():
        print("Content is required.")
        return

    keywords = input("Search keywords (comma-separated): ").strip()

    status = 'draft'
    if auth.check_permission('manage_tickets'):
        publish = input("Publish immediately? (y/n): ").strip().lower()
        if publish == 'y':
            status = 'published'

    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        cursor.execute('''
        INSERT INTO knowledge_base
        (title, content, category, tags, author_id, status, search_keywords, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (title, content, category, tags, auth.current_user['id'], status, keywords, now, now))

        conn.commit()
        article_id = cursor.lastrowid

        print(f"\nArticle #{article_id} created successfully!")
        print(f"Status: {status}")

    except sqlite3.Error as e:
        print(f"Error creating article: {e}")
    finally:
        conn.close()

def edit_kb_article(auth):
    """Edit an existing knowledge base article"""
    print("\nEdit Knowledge Base Article")
    print("===========================")

    article_id = input("Enter article ID to edit: ").strip()

    try:
        article_id = int(article_id)

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT * FROM knowledge_base WHERE article_id = ?
        ''', (article_id,))

        article = cursor.fetchone()
        if not article:
            print("Article not found.")
            conn.close()
            return

        if article[5] != auth.current_user['id'] and not auth.check_permission('manage_tickets'):
            print("You don't have permission to edit this article.")
            conn.close()
            return

        print(f"\nEditing Article: {article[1]}")

        new_title = input(f"New title (current: {article[1]}): ").strip()
        new_category = input(f"New category (current: {article[3]}): ").strip()

        edit_content = input("Edit content? (y/n): ").strip().lower()
        new_content = None

        if edit_content == 'y':
            print("Enter new content (type 'done' on a new line when finished):")
            new_content = ""
            while True:
                line = input()
                if line.lower() == 'done':
                    break
                new_content += line + "\n"

        updates = []
        params = []

        if new_title:
            updates.append("title = ?")
            params.append(new_title)

        if new_category:
            updates.append("category = ?")
            params.append(new_category)

        if new_content:
            updates.append("content = ?")
            params.append(new_content)

        if updates:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            updates.append("updated_at = ?")
            params.append(now)
            params.append(article_id)

            cursor.execute(
                'UPDATE knowledge_base SET ' + ", ".join(updates) + ' WHERE article_id = ?',
                params)

            conn.commit()
            print("Article updated successfully!")
        else:
            print("No changes made.")

        conn.close()

    except (ValueError, sqlite3.Error) as e:
        print(f"Error editing article: {e}")

def search_kb_articles(auth):
    """Search knowledge base articles"""
    search_term = input("Enter search term: ").strip()
    if not search_term:
        return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT article_id, title, category, views, helpful_votes, unhelpful_votes
    FROM knowledge_base
    WHERE status = 'published'
    AND (title LIKE ? OR content LIKE ? OR search_keywords LIKE ?)
    ORDER BY helpful_votes DESC, views DESC
    ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))

    results = cursor.fetchall()

    if results:
        print(f"\nSearch Results for '{search_term}':")
        print("=" * 80)
        print(f"{'ID':<5} {'Title':<40} {'Category':<15} {'Views':<8} {'Rating':<10}")
        print("=" * 80)

        for article in results:
            total_votes = article[4] + article[5]
            rating = f"{article[4]}/{total_votes}" if total_votes > 0 else "No votes"
            print(f"{article[0]:<5} {article[1][:38]:<40} {article[2][:13]:<15} "
                  f"{article[3]:<8} {rating:<10}")

        print("=" * 80)

        article_choice = input("\nEnter article ID to view (or press Enter to return): ")
        if article_choice:
            try:
                article_id = int(article_choice)
                view_kb_article_detail(article_id)
            except ValueError:
                print("Invalid article ID.")
    else:
        print(f"No articles found for '{search_term}'.")

    conn.close()

def kb_statistics(auth):
    """Display knowledge base statistics"""
    conn = get_connection()
    cursor = conn.cursor()

    print("\nKnowledge Base Statistics")
    print("=" * 50)

    cursor.execute('SELECT COUNT(*) FROM knowledge_base WHERE status = "published"')
    total_articles = cursor.fetchone()[0]
    print(f"Total Published Articles: {total_articles}")

    print("\nMost Viewed Articles:")
    print("-" * 40)

    cursor.execute('''
    SELECT title, views FROM knowledge_base
    WHERE status = 'published'
    ORDER BY views DESC
    LIMIT 5
    ''')

    top_viewed = cursor.fetchall()

    for title, views in top_viewed:
        print(f"{title[:35]}: {views} views")

    print("\nMost Helpful Articles:")
    print("-" * 40)

    cursor.execute('''
    SELECT title, helpful_votes, unhelpful_votes
    FROM knowledge_base
    WHERE status = 'published' AND (helpful_votes + unhelpful_votes) > 0
    ORDER BY (helpful_votes * 1.0 / (helpful_votes + unhelpful_votes)) DESC
    LIMIT 5
    ''')

    top_helpful = cursor.fetchall()

    for title, helpful, unhelpful in top_helpful:
        total_votes = helpful + unhelpful
        helpfulness = (helpful / total_votes * 100) if total_votes > 0 else 0
        print(f"{title[:35]}: {helpfulness:.1f}% helpful ({total_votes} votes)")

    print("\nArticles by Category:")
    print("-" * 40)

    cursor.execute('''
    SELECT category, COUNT(*) as count
    FROM knowledge_base
    WHERE status = 'published'
    GROUP BY category
    ORDER BY count DESC
    ''')

    categories = cursor.fetchall()

    for category, count in categories:
        print(f"{category or 'Uncategorized'}: {count}")

    conn.close()
