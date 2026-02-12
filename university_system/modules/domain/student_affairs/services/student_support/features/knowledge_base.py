"""
Knowledge base article management.
"""

import datetime
import json
import logging
import time
import re
import os
import hashlib
import mimetypes
import base64
import secrets
import traceback
from typing import Optional, List, Dict, Any
from functools import wraps

from university_system.infrastructure.database.db import get_connection, sqlite3, DatabaseManager
from university_system.infrastructure.email.email_manager import send_email
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH, TICKET_TEMPLATES_DIR, UPLOAD_DIR
from university_system.utils.logging.log_config import get_log_file

from ..config import (
    SUPPORT_DB, TICKET_STATUSES, TICKET_PRIORITIES, SUPPORT_CATEGORIES,
    NotificationType, TicketSentiment, FileType, SupportConfig
)
from .. import auth as _auth_mod
from ..auth import get_current_user_safe, require_auth, has_staff_permissions
from ..utils.audit import audit_action

logger = logging.getLogger(__name__)

def create_kb_article(title, content, category, summary=None, tags=None, is_published=False):
    """Create a new knowledge base article"""
    if not _auth_mod.auth or not _auth_mod.auth.current_user or _auth_mod.auth.current_user['role'] not in ('staff', 'admin'):
        raise PermissionError("Only staff can create knowledge base articles")
    
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()
        
        created_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        published_time = created_time if is_published else None
        
        # Generate search keywords from title and content
        search_keywords = _generate_search_keywords(title + " " + content)
        
        cursor.execute('''
        INSERT INTO kb_articles (
            title, content, summary, category, tags, author_id, created_datetime,
            published_datetime, is_published, search_keywords
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            title, content, summary, category, json.dumps(tags or []),
            _auth_mod.auth.current_user['id'], created_time, published_time, is_published, search_keywords
        ))
        
        article_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        logger.info(f"Knowledge base article '{title}' created by {_auth_mod.auth.current_user['username']}")
        return article_id
        
    except Exception as e:
        logger.error(f"Error creating knowledge base article: {e}")
        raise

def get_kb_articles(category=None, published_only=True):
    """Get knowledge base articles"""
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM kb_articles WHERE 1=1"
        params = []
        
        if published_only:
            query += " AND is_published = 1"
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        query += " ORDER BY view_count DESC, created_datetime DESC"
        
        cursor.execute(query, params)
        articles = [dict(row) for row in cursor.fetchall()]
        
        # Parse JSON fields
        for article in articles:
            article['tags'] = json.loads(article.get('tags') or '[]')
            if article.get('related_articles'):
                article['related_articles'] = json.loads(article.get('related_articles') or '[]')
        
        conn.close()
        return articles
        
    except Exception as e:
        logger.error(f"Error getting knowledge base articles: {e}")
        return []

@audit_action("publish_kb_article")

def publish_kb_article(article_id):
    """Publish a knowledge base article"""
    if not _auth_mod.auth or not _auth_mod.auth.current_user or _auth_mod.auth.current_user['role'] not in ('staff', 'admin'):
        raise PermissionError("Only staff can publish knowledge base articles")
    
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()
        
        published_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        UPDATE kb_articles 
        SET is_published = 1, published_datetime = ?
        WHERE article_id = ?
        ''', (published_time, article_id))
        
        if cursor.rowcount == 0:
            raise ValueError(f"Knowledge base article {article_id} not found")
        
        conn.commit()
        conn.close()
        
        logger.info(f"Knowledge base article {article_id} published by {_auth_mod.auth.current_user['username']}")
        return True
        
    except Exception as e:
        logger.error(f"Error publishing knowledge base article: {e}")
        raise

# Helper functions for bulk operations

def _generate_search_keywords(text):
    """Generate search keywords from text content"""
    import re
    
    # Remove HTML tags and special characters
    clean_text = re.sub(r'<[^>]+>', '', text)
    clean_text = re.sub(r'[^\w\s]', ' ', clean_text)
    
    # Split into words and filter
    words = clean_text.lower().split()
    
    # Remove common stop words
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
        'by', 'from', 'this', 'that', 'these', 'those', 'is', 'are', 'was', 'were', 'be',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'
    }
    
    # Filter and deduplicate
    keywords = list(set([word for word in words if len(word) > 2 and word not in stop_words]))
    
    return ' '.join(keywords[:50])  # Limit to 50 keywords

def _search_knowledge_base(query, filters):
    """Search knowledge base articles"""
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        base_query = """
        SELECT *, 
               (CASE WHEN title LIKE ? THEN 5 ELSE 0 END +
                CASE WHEN summary LIKE ? THEN 3 ELSE 0 END +
                CASE WHEN content LIKE ? THEN 2 ELSE 0 END +
                CASE WHEN search_keywords LIKE ? THEN 1 ELSE 0 END) as relevance_score
        FROM kb_articles 
        WHERE is_published = 1 
        AND (title LIKE ? OR summary LIKE ? OR content LIKE ? OR search_keywords LIKE ?)
        """
        
        search_term = f"%{query}%"
        params = [search_term] * 8
        
        if filters and filters.get('category'):
            base_query += " AND category = ?"
            params.append(filters['category'])
        
        base_query += " ORDER BY relevance_score DESC, view_count DESC"
        
        cursor.execute(base_query, params)
        articles = [dict(row) for row in cursor.fetchall()]
        
        # Update view counts
        for article in articles:
            cursor.execute('UPDATE kb_articles SET view_count = view_count + 1 WHERE article_id = ?', (article['article_id'],))
        
        conn.commit()
        conn.close()
        
        return articles
        
    except Exception as e:
        logger.error(f"Error searching knowledge base: {e}")
        return []

def manage_knowledge_base_menu(support):
    """Manage knowledge base articles (staff only)"""
    try:
        print("\n📚 MANAGE KNOWLEDGE BASE")
        print("="*40)
        
        print("1. View all articles")
        print("2. Create new article")
        print("3. Article statistics")
        print("4. Back")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == '1':
            view_all_kb_articles(support)
        elif choice == '2':
            create_kb_article_interactive(support)
        elif choice == '3':
            show_kb_statistics(support)
        elif choice == '4':
            return
        else:
            print("❌ Invalid choice.")
    
    except Exception as e:
        print(f"❌ Error managing knowledge base: {e}")
    
    input("\nPress Enter to continue...")

def view_all_kb_articles(support):
    """View all knowledge base articles"""
    try:
        articles = support.get_kb_articles(published_only=False)
        
        if not articles:
            print("📭 No knowledge base articles found.")
            return
        
        print("\n📚 ALL KNOWLEDGE BASE ARTICLES")
        print("="*60)
        
        for article in articles:
            status = "✅ Published" if article['is_published'] else "📝 Draft"
            print(f"📖 {article['title']}")
            print(f"   📂 Category: {article['category']} | {status}")
            print(f"   ✏️ Author: {article['author_id']} | 📅 Created: {article['created_datetime']}")
            print(f"   👁️ Views: {article.get('view_count', 0)} | 👍 Helpful: {article.get('helpful_votes', 0)}")
            if article.get('summary'):
                print(f"   📝 {article['summary'][:80]}...")
            print()
    except Exception as e:
        print(f"❌ Error viewing articles: {e}")

def create_kb_article_interactive(support):
    """Interactive knowledge base article creation"""
    try:
        print("\n📖 CREATE KNOWLEDGE BASE ARTICLE")
        print("="*50)
        
        title = input("Article title: ").strip()
        if not title:
            print("❌ Article title is required.")
            return
        
        summary = input("Article summary (optional): ").strip() or None
        
        print("Article content (press Enter twice to finish):")
        lines = []
        while True:
            line = input()
            if not line and (not lines or not lines[-1]):
                break
            lines.append(line)
        
        content = '\n'.join(lines)
        if not content:
            print("❌ Article content is required.")
            return
        
        # Category selection
        categories = ['Technical', 'Academic', 'Financial Aid', 'Housing', 'General', 'Other']
        print("\nCategories:")
        for i, cat in enumerate(categories, 1):
            print(f"{i}. {cat}")
        
        cat_choice = input(f"Select category (1-{len(categories)}): ").strip()
        if not cat_choice.isdigit() or not 1 <= int(cat_choice) <= len(categories):
            print("❌ Invalid category.")
            return
        
        category = categories[int(cat_choice) - 1]
        
        tags_input = input("Tags (comma-separated, optional): ").strip()
        tags = [tag.strip() for tag in tags_input.split(',')] if tags_input else []
        
        publish_now = input("Publish immediately? (y/n): ").lower() == 'y'
        
        # Create article
        article_id = support.create_kb_article(title, content, category, summary, tags, publish_now)
        
        status_msg = "and published" if publish_now else "as draft"
        print(f"✅ Knowledge base article '{title}' created {status_msg} successfully (ID: {article_id})!")
    
    except Exception as e:
        print(f"❌ Error creating article: {e}")

def show_kb_statistics(support):
    """Show knowledge base statistics"""
    try:
        print("\n📊 KNOWLEDGE BASE STATISTICS")
        print("="*50)
        
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()
        
        # Check if kb_articles table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='kb_articles'")
        if not cursor.fetchone():
            print("📭 No knowledge base data available.")
            conn.close()
            return
        
        # Overall stats
        cursor.execute('SELECT COUNT(*) FROM kb_articles WHERE is_published = 1')
        published_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM kb_articles WHERE is_published = 0')
        draft_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COALESCE(SUM(view_count), 0) FROM kb_articles')
        total_views = cursor.fetchone()[0]
        
        cursor.execute('SELECT COALESCE(SUM(helpful_votes), 0) FROM kb_articles')
        total_helpful = cursor.fetchone()[0]
        
        print(f"📚 Total Articles: {published_count + draft_count}")
        print(f"✅ Published: {published_count}")
        print(f"📝 Drafts: {draft_count}")
        print(f"👁️ Total Views: {total_views}")
        print(f"👍 Total Helpful Votes: {total_helpful}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error getting knowledge base statistics: {e}")

def browse_knowledge_base(support):
    """Browse knowledge base articles"""
    try:
        print("\n📚 KNOWLEDGE BASE")
        print("="*40)
        
        articles = support.get_kb_articles()
        
        if not articles:
            print("📭 No knowledge base articles available.")
            return
        
        # Group by category
        categories = {}
        for article in articles:
            cat = article['category']
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(article)
        
        print("📁 Categories:")
        cat_list = list(categories.keys())
        for i, cat in enumerate(cat_list, 1):
            count = len(categories[cat])
            print(f"{i}. {cat} ({count} articles)")
        
        print(f"{len(cat_list) + 1}. View all articles")
        print(f"{len(cat_list) + 2}. Search articles")
        print(f"{len(cat_list) + 3}. Back")
        
        choice = input("\nSelect option: ").strip()
        
        if choice.isdigit():
            choice_num = int(choice)
            if 1 <= choice_num <= len(cat_list):
                # Show articles in category
                category = cat_list[choice_num - 1]
                articles_to_show = categories[category]
                display_article_list(articles_to_show, f"{category} Articles")
            elif choice_num == len(cat_list) + 1:
                # Show all articles
                display_article_list(articles, "All Articles")
            elif choice_num == len(cat_list) + 2:
                # Search articles
                search_query = input("Enter search query: ").strip()
                if search_query:
                    results = support._search_knowledge_base(search_query, None)
                    display_article_list(results, f"Search Results for '{search_query}'")
    
    except Exception as e:
        print(f"❌ Error browsing knowledge base: {e}")
    
    input("\nPress Enter to continue...")

def display_article_list(articles, title):
    """Display a list of knowledge base articles"""
    print(f"\n📖 {title}")
    print("="*50)
    
    if not articles:
        print("📭 No articles found.")
        return
    
    for i, article in enumerate(articles[:10], 1):  # Show first 10
        views = article.get('view_count', 0)
        votes = article.get('helpful_votes', 0)
        print(f"{i}. 📄 {article['title']}")
        print(f"   👁️ {views} views | 👍 {votes} helpful")
        if article.get('summary'):
            print(f"   📝 {article['summary'][:80]}...")
    
    if len(articles) > 10:
        print(f"\n... and {len(articles) - 10} more articles")
    
    # View article option
    view_choice = input(f"\nView article (1-{min(len(articles), 10)}) or press Enter to go back: ").strip()
    if view_choice.isdigit() and 1 <= int(view_choice) <= min(len(articles), 10):
        article = articles[int(view_choice) - 1]
        display_full_article(article)

def display_full_article(article):
    """Display full knowledge base article"""
    print(f"\n📖 {article['title']}")
    print("="*60)
    print(f"📁 Category: {article['category']}")
    print(f"✍️ Author: {article['author_id']}")
    print(f"📅 Published: {article.get('published_datetime', 'Not published')}")
    print(f"👁️ Views: {article.get('view_count', 0)}")
    print(f"👍 Helpful: {article.get('helpful_votes', 0)} | 👎 Not Helpful: {article.get('not_helpful_votes', 0)}")
    
    if article.get('tags'):
        tags = json.loads(article['tags']) if isinstance(article['tags'], str) else article['tags']
        if tags:
            print(f"🏷️ Tags: {', '.join(tags)}")
    
    print(f"\n📝 Content:")
    print("-" * 40)
    print(article['content'])
    print("-" * 40)
    
    # Actions
    print("\n🔧 Actions:")
    print("1. Mark as helpful")
    print("2. Mark as not helpful")
    print("3. Back")
    
    action = input("Choose action: ").strip()
    
    if action == '1':
        # In real implementation, would update helpful_votes
        print("✅ Marked as helpful. Thank you for your feedback!")
    elif action == '2':
        # In real implementation, would update not_helpful_votes
        print("📝 Marked as not helpful. Thank you for your feedback!")

# Main integration function
if __name__ == "__main__":
    display_support_menu()

def publish_kb_article_interactive(support):
    """Interactive knowledge base article publishing"""
    print("\n📤 PUBLISH KNOWLEDGE BASE ARTICLE")
    print("="*50)
    
    # Get unpublished articles
    articles = support.get_kb_articles(published_only=False)
    unpublished = [a for a in articles if not a['is_published']]
    
    if not unpublished:
        print("📭 No unpublished articles found.")
        return
    
    print("📝 UNPUBLISHED ARTICLES:")
    for i, article in enumerate(unpublished, 1):
        print(f"{i}. {article['title']}")
        print(f"   📂 Category: {article['category']} | ✍️ Author: {article['author_id']}")
        if article.get('summary'):
            print(f"   📝 {article['summary'][:60]}...")
        print()
    
    choice = input(f"Select article to publish (1-{len(unpublished)}): ").strip()
    
    if not choice.isdigit() or not 1 <= int(choice) <= len(unpublished):
        print("❌ Invalid choice.")
        return
    
    article = unpublished[int(choice) - 1]
    
    # Confirm publication
    print(f"\n📖 Publishing: {article['title']}")
    confirm = input("Confirm publication? (y/n): ").lower()
    
    if confirm == 'y':
        support.publish_kb_article(article['article_id'])
        print(f"✅ Article '{article['title']}' published successfully!")
    else:
        print("❌ Publication cancelled.")
