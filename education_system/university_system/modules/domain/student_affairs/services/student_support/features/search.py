"""
Advanced search functionality.
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

from education_system.university_system.infrastructure.database.db import get_connection, sqlite3, DatabaseManager
from education_system.university_system.infrastructure.email.email_manager import send_email
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH, TICKET_TEMPLATES_DIR, UPLOAD_DIR
from education_system.university_system.utils.logging.log_config import get_log_file

from ..config import (
    SUPPORT_DB, TICKET_STATUSES, TICKET_PRIORITIES, SUPPORT_CATEGORIES,
    NotificationType, TicketSentiment, FileType, SupportConfig
)
from .. import auth as _auth_mod
from ..auth import get_current_user_safe, require_auth, has_staff_permissions
from .knowledge_base import _search_knowledge_base

logger = logging.getLogger(__name__)

def advanced_search(query, search_type='global', filters=None, page=1, per_page=20):
    """Advanced search across tickets, FAQs, and resources with analytics"""
    if not _auth_mod.auth or not _auth_mod.auth.current_user:
        raise PermissionError("You must be logged in to search")
    
    try:
        # Log search analytics
        _log_search_analytics(query, search_type, _auth_mod.auth.current_user['id'])
        
        results = {}
        
        if search_type in ['global', 'tickets']:
            results['tickets'] = _search_tickets(query, filters, page, per_page)
        
        if search_type in ['global', 'faqs']:
            results['faqs'] = _search_faqs(query, filters)
        
        if search_type in ['global', 'resources']:
            results['resources'] = _search_resources(query, filters)
        
        if search_type in ['global', 'kb']:
            results['kb_articles'] = _search_knowledge_base(query, filters)
        
        # Suggest related content
        try:
            support_config = SupportConfig()
            if support_config.ai_suggestions_enabled:
                results['suggestions'] = _get_search_suggestions(query, results)
        except Exception:
            results['suggestions'] = _get_search_suggestions(query, results)
        
        logger.info(f"Advanced search performed by {_auth_mod.auth.current_user['username']}: '{query}' ({search_type})")
        return results
        
    except Exception as e:
        logger.error(f"Error performing advanced search: {e}")
        raise

def _search_tickets(query, filters, page, per_page):
    """Search tickets with full-text search"""
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Permission check
        base_query = "SELECT * FROM support_tickets WHERE "
        params = []
        
        if _auth_mod.auth.current_user['role'] == 'student':
            # Get student's own tickets only
            conn_main = get_connection()
            cursor_main = conn_main.cursor()
            cursor_main.execute('SELECT student_id FROM users WHERE id = ?', (_auth_mod.auth.current_user['id'],))
            result = cursor_main.fetchone()
            conn_main.close()
            
            if result:
                base_query += "student_id = ? AND "
                params.append(result[0])
            else:
                return {'tickets': [], 'total_count': 0}
        
        # Add search condition
        base_query += "(title LIKE ? OR description LIKE ?)"
        search_term = f"%{query}%"
        params.extend([search_term, search_term])
        
        # Apply additional filters
        if filters:
            if filters.get('category'):
                base_query += " AND category = ?"
                params.append(filters['category'])
            
            if filters.get('status'):
                base_query += " AND status = ?"
                params.append(filters['status'])
        
        # Get total count
        count_query = base_query.replace('SELECT *', 'SELECT COUNT(*)')
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]
        
        # Add pagination and ordering
        base_query += " ORDER BY created_datetime DESC LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        
        cursor.execute(base_query, params)
        tickets = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            'tickets': tickets,
            'total_count': total_count,
            'page': page,
            'per_page': per_page
        }
        
    except Exception as e:
        logger.error(f"Error searching tickets: {e}")
        return {'tickets': [], 'total_count': 0}

def _search_faqs(query, filters):
    """Search FAQs with relevance scoring"""
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        base_query = """
        SELECT *, 
               (CASE WHEN question LIKE ? THEN 3 ELSE 0 END +
                CASE WHEN answer LIKE ? THEN 1 ELSE 0 END) as relevance_score
        FROM faqs 
        WHERE (question LIKE ? OR answer LIKE ?)
        """
        
        search_term = f"%{query}%"
        params = [search_term, search_term, search_term, search_term]
        
        if filters and filters.get('category'):
            base_query += " AND category = ?"
            params.append(filters['category'])
        
        base_query += " ORDER BY relevance_score DESC, view_count DESC"
        
        cursor.execute(base_query, params)
        faqs = [dict(row) for row in cursor.fetchall()]
        
        # Update view counts for returned FAQs
        for faq in faqs:
            cursor.execute('UPDATE faqs SET view_count = view_count + 1 WHERE faq_id = ?', (faq['faq_id'],))
        
        conn.commit()
        conn.close()
        
        return faqs
        
    except Exception as e:
        logger.error(f"Error searching FAQs: {e}")
        return []

def _search_resources(query, filters):
    """Search support resources"""
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        base_query = """
        SELECT *, 
               (CASE WHEN title LIKE ? THEN 3 ELSE 0 END +
                CASE WHEN description LIKE ? THEN 2 ELSE 0 END +
                CASE WHEN tags LIKE ? THEN 1 ELSE 0 END) as relevance_score
        FROM support_resources 
        WHERE (title LIKE ? OR description LIKE ? OR tags LIKE ?)
        """

        search_term = f"%{query}%"
        params = [search_term] * 6

        if filters and filters.get('category'):
            base_query += " AND category = ?"
            params.append(filters['category'])

        base_query += " ORDER BY relevance_score DESC, access_count DESC"

        cursor.execute(base_query, params)
        resources = [dict(row) for row in cursor.fetchall()]

        # Update access count
        for resource in resources:
            cursor.execute('UPDATE support_resources SET access_count = access_count + 1 WHERE resource_id = ?', (resource['resource_id'],))

        conn.commit()
        conn.close()

        return resources

    except Exception as e:
        logger.error(f"Error searching support resources: {e}")
        return []

# User preference methods

def _get_search_suggestions(query, results):
    """Get AI-powered search suggestions"""
    suggestions = []
    
    # Suggest based on common patterns
    common_suggestions = {
        'password': ['How to reset password', 'Password requirements', 'Account security'],
        'grade': ['View grades', 'Grade appeals', 'Transcript requests'],
        'email': ['Email setup', 'Email forwarding', 'Email quota'],
        'wifi': ['WiFi setup', 'Network troubleshooting', 'VPN access'],
        'library': ['Library hours', 'Database access', 'Book renewal'],
    }
    
    query_lower = query.lower()
    for keyword, suggestion_list in common_suggestions.items():
        if keyword in query_lower:
            suggestions.extend(suggestion_list)
    
    # Suggest based on popular content
    if not suggestions:
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            # Get popular FAQs
            cursor.execute('SELECT question FROM faqs ORDER BY view_count DESC LIMIT 3')
            popular_faqs = [row[0] for row in cursor.fetchall()]
            suggestions.extend(popular_faqs)
            
            conn.close()
        except Exception as e:
            logger.error(f"Error getting popular suggestions: {e}")
    
    return suggestions[:5]  # Return top 5 suggestions

def _log_search_analytics(query, search_type, user_id):
    """Log search analytics for improvement"""
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()
        
        session_id = getattr(_auth_mod.auth.current_user, 'session_id', 'unknown')
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO search_analytics (
            user_id, search_query, search_type, results_count, search_datetime, session_id
        ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, query, search_type, 0, timestamp, session_id))  # results_count updated later
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error logging search analytics: {e}")

def perform_advanced_search(support):
    """Perform advanced search across all content"""
    try:
        print("\n🔍 ADVANCED SEARCH")
        print("="*40)
        
        query = input("Enter search query: ").strip()
        if not query:
            print("Search query cannot be empty.")
            return
        
        print("\nSearch in:")
        print("1. Everything (Global)")
        print("2. Tickets only")
        print("3. FAQs only")
        print("4. Resources only")
        print("5. Knowledge Base only")
        
        search_type_map = {
            '1': 'global',
            '2': 'tickets',
            '3': 'faqs',
            '4': 'resources',
            '5': 'kb'
        }
        
        choice = input("Choose search type (1-5): ").strip()
        search_type = search_type_map.get(choice, 'global')
        
        print(f"\n🔎 Searching for '{query}'...")
        results = support.advanced_search(query, search_type)
        
        # Display results
        total_results = 0
        
        if 'tickets' in results:
            tickets = results['tickets']['tickets']
            print(f"\n🎫 TICKETS ({len(tickets)} found):")
            for ticket in tickets[:5]:
                print(f"  #{ticket['ticket_id']} - {ticket['title']} ({ticket['status']})")
            total_results += len(tickets)
        
        if 'faqs' in results:
            faqs = results['faqs']
            print(f"\n❓ FAQs ({len(faqs)} found):")
            for faq in faqs[:5]:
                print(f"  Q: {faq['question'][:60]}...")
            total_results += len(faqs)
        
        if 'resources' in results:
            resources = results['resources']
            print(f"\n📋 RESOURCES ({len(resources)} found):")
            for resource in resources[:5]:
                print(f"  📄 {resource['title']} - {resource['description'][:50]}...")
            total_results += len(resources)
        
        if 'kb_articles' in results:
            articles = results['kb_articles']
            print(f"\n📚 KNOWLEDGE BASE ({len(articles)} found):")
            for article in articles[:5]:
                print(f"  📖 {article['title']} - {article.get('summary', '')[:50]}...")
            total_results += len(articles)
        
        if 'suggestions' in results and results['suggestions']:
            print(f"\n💡 SUGGESTIONS:")
            for suggestion in results['suggestions']:
                print(f"  💭 {suggestion}")
        
        if total_results == 0:
            print("\n❌ No results found. Try different keywords or check spelling.")
        
    except Exception as e:
        print(f"Search error: {e}")
    
    input("\nPress Enter to continue...")
