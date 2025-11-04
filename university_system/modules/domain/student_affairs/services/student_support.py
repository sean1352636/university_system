from university_system.infrastructure.database.db import sqlite3, DatabaseManager
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
import traceback
import re
import os
import datetime
import logging
import json
import hashlib
import mimetypes
import base64
import secrets
import time
from university_system.infrastructure.email.email_manager import send_email
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import threading
from functools import wraps
from university_system.infrastructure.database.db import get_connection
from university_system.utils.logging.log_config import get_log_file

# Enhanced imports for new features
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Import auth instance management from user_authentication
try:
    from university_system.infrastructure.auth.user_authentication import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)

# Enhanced logging with multiple handlers
def setup_enhanced_logging():
    """Set up comprehensive logging system"""
    logger = logging.getLogger('student_support')
    logger.setLevel(logging.DEBUG)
    
    # File handler for all logs
    file_handler = logging.FileHandler(get_log_file("student_support.log"))
    file_handler.setLevel(logging.INFO)
    
    # File handler for errors only
    error_handler = logging.FileHandler(get_log_file("student_support_errors.log"))
    error_handler.setLevel(logging.ERROR)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    
    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s')
    file_handler.setFormatter(formatter)
    error_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_enhanced_logging()

# Enhanced Constants
SUPPORT_DB = str(DEFAULT_DB_PATH)
TICKET_STATUSES = ['Open', 'In Progress', 'Resolved', 'Closed', 'Escalated', 'On Hold']
TICKET_PRIORITIES = ['Low', 'Medium', 'High', 'Urgent', 'Critical']
SUPPORT_CATEGORIES = [
    'Academic', 'Technical', 'Financial Aid', 
    'Library Services', 'Accommodation', 'Accessibility',
    'Mental Health', 'Registration', 'Housing', 'Dining',
    'Parking', 'Career Services', 'Student Activities', 'Other'
]

# New enums for enhanced features
class NotificationType(Enum):
    EMAIL = "email"
    IN_APP = "in_app"
    PUSH = "push"

class TicketSentiment(Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    FRUSTRATED = "frustrated"

class FileType(Enum):
    IMAGE = "image"
    DOCUMENT = "document"
    VIDEO = "video"
    OTHER = "other"

# Configuration class
@dataclass
class SupportConfig:
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_file_types: List[str] = None
    auto_assign_enabled: bool = True
    escalation_time_hours: int = 24
    satisfaction_survey_enabled: bool = True
    ai_suggestions_enabled: bool = True
    
    def __post_init__(self):
        if self.allowed_file_types is None:
            self.allowed_file_types = [
                '.pdf', '.doc', '.docx', '.txt', '.png', '.jpg', '.jpeg', 
                '.gif', '.bmp', '.zip', '.rar', '.csv', '.xlsx'
            ]

# Audit trail decorator
def audit_action(action_type: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Log successful action
                audit_data = {
                    'action': action_type,
                    'function': func.__name__,
                    'user': auth.current_user['username'] if auth and auth.current_user else 'system',
                    'success': True,
                    'duration': duration,
                    'timestamp': datetime.datetime.now().isoformat()
                }
                
                # Store in audit table
                if hasattr(args[0], '_log_audit'):
                    args[0]._log_audit(audit_data)
                
                logger.info(f"Action {action_type} completed successfully in {duration:.2f}s")
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                # Log failed action
                audit_data = {
                    'action': action_type,
                    'function': func.__name__,
                    'user': auth.current_user['username'] if auth and auth.current_user else 'system',
                    'success': False,
                    'error': str(e),
                    'duration': duration,
                    'timestamp': datetime.datetime.now().isoformat()
                }
                
                if hasattr(args[0], '_log_audit'):
                    args[0]._log_audit(audit_data)
                
                logger.error(f"Action {action_type} failed after {duration:.2f}s: {e}")
                raise
                
        return wrapper
    return decorator

class EnhancedStudentSupport:
    def __init__(self, config: Optional[SupportConfig] = None):
        """Initialize the enhanced student support system."""
        self.config = config or SupportConfig()
        self.notification_queue = []
        self.staff_assignments = {}  # category -> staff_member mapping
        
        try:
            self.init_enhanced_db()
            self._load_staff_assignments()
            self._start_background_tasks()
            logger.info("Enhanced StudentSupport initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Enhanced StudentSupport: {e}")
            raise

    def init_enhanced_db(self):
        """Initialize the enhanced support database with new tables."""
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            # Create original tables first
            self._create_original_tables(cursor)
            
            # Create enhanced tables
            self._create_enhanced_tables(cursor)
            
            # Initialize default data
            self._initialize_default_data(cursor)
            
            conn.commit()
            conn.close()
            
            logger.info("Enhanced database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize enhanced database: {e}")
            raise

    # Add this method to the EnhancedStudentSupport class
    def submit_satisfaction_rating(self, ticket_id, rating, feedback=None):
        """Submit satisfaction rating for a resolved ticket"""
        if not auth or not auth.current_user:
            raise PermissionError("You must be logged in to submit ratings")
        
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")
        
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            # Verify ticket exists and is resolved
            cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ? AND status = "Resolved"', (ticket_id,))
            ticket = cursor.fetchone()
            
            if not ticket:
                raise ValueError("Ticket not found or not resolved")
            
            # Check if user owns the ticket (for students)
            if auth.current_user['role'] == 'student':
                conn_main = get_connection()
                cursor_main = conn_main.cursor()
                cursor_main.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
                result = cursor_main.fetchone()
                conn_main.close()
                
                if not result or result[0] != ticket[1]:  # ticket[1] is student_id
                    raise PermissionError("You can only rate your own tickets")
            
            # Update satisfaction rating
            cursor.execute('''
            UPDATE support_tickets 
            SET satisfaction_rating = ?, satisfaction_feedback = ?
            WHERE ticket_id = ?
            ''', (rating, feedback, ticket_id))
            
            # Log the rating
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
            INSERT INTO system_metrics (
                metric_name, metric_value, category, recorded_datetime, metadata
            ) VALUES (?, ?, ?, ?, ?)
            ''', (
                'satisfaction_rating', rating, 'satisfaction', timestamp,
                json.dumps({'ticket_id': ticket_id, 'user_id': auth.current_user['id'], 'feedback': feedback})
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Satisfaction rating {rating} submitted for ticket #{ticket_id} by {auth.current_user['username']}")
            return True
            
        except Exception as e:
            logger.error(f"Error submitting satisfaction rating: {e}")
            raise

    # Add this method to the EnhancedStudentSupport class
    def get_user_notifications(self, user_id=None, unread_only=False):
        """Get notifications for a user"""
        if not user_id:
            user_id = auth.current_user['id'] if auth and auth.current_user else None
        
        if not user_id:
            raise ValueError("User ID required")
        
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = '''
            SELECT * FROM notifications 
            WHERE user_id = ? 
            AND (expires_at IS NULL OR expires_at > datetime('now'))
            '''
            params = [user_id]
            
            if unread_only:
                query += ' AND is_read = 0'
            
            query += ' ORDER BY created_datetime DESC'
            
            cursor.execute(query, params)
            notifications = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            return notifications
            
        except Exception as e:
            logger.error(f"Error getting user notifications: {e}")
            return []

    # Add this method to the EnhancedStudentSupport class  
    def mark_notification_read(self, notification_id, user_id=None):
        """Mark a notification as read"""
        if not user_id:
            user_id = auth.current_user['id'] if auth and auth.current_user else None
        
        if not user_id:
            raise ValueError("User ID required")
        
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            UPDATE notifications 
            SET is_read = 1, read_datetime = ?
            WHERE notification_id = ? AND user_id = ?
            ''', (timestamp, notification_id, user_id))
            
            conn.commit()
            conn.close()
            
            return cursor.rowcount > 0
            
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            return False

    def display_faq_list(faqs, title):
        """Display a list of FAQs"""
        print(f"\n❓ {title}")
        print("="*50)
        
        if not faqs:
            print("📭 No FAQs found.")
            return
        
        for i, faq in enumerate(faqs[:10], 1):  # Show first 10
            views = faq.get('view_count', 0)
            votes = faq.get('helpful_votes', 0)
            print(f"{i}. Q: {faq['question']}")
            print(f"   👁️ {views} views | 👍 {votes} helpful")
        
        if len(faqs) > 10:
            print(f"\n... and {len(faqs) - 10} more FAQs")
        
        # View FAQ option
        view_choice = input(f"\nView FAQ (1-{min(len(faqs), 10)}) or press Enter to go back: ").strip()
        if view_choice.isdigit() and 1 <= int(view_choice) <= min(len(faqs), 10):
            faq = faqs[int(view_choice) - 1]
            display_full_faq(faq)

    def display_full_faq(faq):
        """Display full FAQ with answer"""
        print(f"\n❓ {faq['question']}")
        print("="*60)
        print(f"📂 Category: {faq['category']}")
        print(f"👁️ Views: {faq.get('view_count', 0)}")
        print(f"👍 Helpful: {faq.get('helpful_votes', 0)}")
        
        print(f"\n💡 Answer:")
        print("-" * 40)
        print(faq['answer'])
        print("-" * 40)
        
        # Actions
        print("\n🔧 Actions:")
        print("1. Mark as helpful")
        print("2. Back")
        
        action = input("Choose action: ").strip()
        
        if action == '1':
            print("✅ Marked as helpful. Thank you for your feedback!")

    def display_resource_list(resources, title):
        """Display a list of support resources"""
        print(f"\n📋 {title}")
        print("="*50)
        
        if not resources:
            print("📭 No resources found.")
            return
        
        for i, resource in enumerate(resources[:10], 1):  # Show first 10
            access_count = resource.get('access_count', 0)
            print(f"{i}. 📄 {resource['title']}")
            print(f"   📂 Category: {resource['category']}")
            print(f"   👁️ {access_count} accesses")
            print(f"   📝 {resource['description'][:80]}...")
        
        if len(resources) > 10:
            print(f"\n... and {len(resources) - 10} more resources")
        
        # View resource option
        view_choice = input(f"\nView resource (1-{min(len(resources), 10)}) or press Enter to go back: ").strip()
        if view_choice.isdigit() and 1 <= int(view_choice) <= min(len(resources), 10):
            resource = resources[int(view_choice) - 1]
            display_full_resource(resource)

    def display_full_resource(resource):
        """Display full resource details"""
        print(f"\n📄 {resource['title']}")
        print("="*60)
        print(f"📂 Category: {resource['category']}")
        print(f"✍️ Created by: {resource['created_by']}")
        print(f"📅 Created: {resource['created_datetime']}")
        print(f"👁️ Accesses: {resource.get('access_count', 0)}")
        
        if resource.get('tags'):
            tags = json.loads(resource['tags']) if isinstance(resource['tags'], str) else resource['tags']
            if tags:
                print(f"🏷️ Tags: {', '.join(tags)}")
        
        print(f"\n📝 Description:")
        print("-" * 40)
        print(resource['description'])
        print("-" * 40)
        
        if resource.get('url'):
            print(f"🔗 URL: {resource['url']}")
        
        if resource.get('file_path'):
            print(f"📁 File: {resource['file_path']}")

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
        print(f"📂 Category: {article['category']}")
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

    def perform_bulk_assign(support, ticket_ids, assigned_to):
        """Perform bulk assignment of tickets to a user"""
        if not ticket_ids:
            print("❌ No ticket IDs provided.")
            return
        
        # Validate ticket IDs exist
        try:
            valid_ids = [str(t.get('id', '')) for t in support.get_all_tickets()]
            ticket_ids = [tid for tid in ticket_ids if tid in valid_ids]
        except ValueError:
            print("❌ Invalid ticket IDs.")
            return
        
        if not ticket_ids:
            print("❌ No valid ticket IDs provided.")
            return
        
        # Confirm operation
        print(f"\n📋 Assigning {len(ticket_ids)} tickets to {assigned_to}")
        confirm = input("Confirm bulk assignment? (y/n): ").lower()
        
        if confirm == 'y':
            try:
                updates = {'assigned_to': assigned_to}
                updated_count = support.bulk_update_tickets(ticket_ids, updates)
                print(f"✅ Successfully assigned {updated_count} tickets to {assigned_to}")
            except Exception as e:
                print(f"❌ Error during bulk assignment: {e}")
        else:
            print("❌ Bulk assignment cancelled.")
    
    def _search_knowledge_base(self, query, filters):
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

    def _get_search_suggestions(self, query, results):
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

    def get_dashboard_data(self, user_role, user_id):
        """Get dashboard data based on user role"""
        # Check if we have user information
        if not user_role or not user_id:
            raise PermissionError("You must be logged in to view dashboard")

        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            dashboard_data = {}
            
            if user_role == 'student':
                dashboard_data = self._get_student_dashboard(user_id, cursor)
            elif user_role in ('staff', 'admin'):
                dashboard_data = self._get_staff_dashboard(user_id, cursor)
            
            # Add common data
            dashboard_data['notifications'] = self._get_recent_notifications(user_id, cursor)
            dashboard_data['system_status'] = self._get_system_status()
            
            conn.close()
            
            logger.info(f"Dashboard data retrieved for {user_role} {user_id}")
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            raise

    def _get_student_dashboard(self, user_id, cursor):
        """Get dashboard data for students"""
        # Get student ID
        conn_main = get_connection()
        cursor_main = conn_main.cursor()
        cursor_main.execute('SELECT student_id FROM users WHERE id = ?', (user_id,))
        result = cursor_main.fetchone()
        conn_main.close()
        
        if not result:
            return {}
        
        student_id = result[0]
        
        # Get ticket statistics
        cursor.execute('SELECT status, COUNT(*) FROM support_tickets WHERE student_id = ? GROUP BY status', (student_id,))
        ticket_stats = dict(cursor.fetchall())
        
        # Get recent tickets
        cursor.execute('''
        SELECT ticket_id, title, status, created_datetime 
        FROM support_tickets 
        WHERE student_id = ? 
        ORDER BY created_datetime DESC 
        LIMIT 5
        ''', (student_id,))
        recent_tickets = [dict(zip(['ticket_id', 'title', 'status', 'created_datetime'], row)) for row in cursor.fetchall()]
        
        # Get featured resources
        cursor.execute('SELECT * FROM support_resources WHERE is_featured = 1 LIMIT 5')
        featured_resources = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
        
        return {
            'ticket_stats': ticket_stats,
            'recent_tickets': recent_tickets,
            'featured_resources': featured_resources,
            'quick_actions': [
                {'name': 'Create Ticket', 'action': 'create_ticket'},
                {'name': 'View FAQs', 'action': 'view_faqs'},
                {'name': 'Search Resources', 'action': 'search_resources'}
            ]
        }

    def _get_staff_dashboard(self, user_id, cursor):
        """Get dashboard data for staff"""
        # Get username from user_id
        conn_main = get_connection()
        cursor_main = conn_main.cursor()
        cursor_main.execute('SELECT username FROM users WHERE id = ?', (user_id,))
        result = cursor_main.fetchone()
        conn_main.close()

        if not result:
            return {}

        username = result[0]

        # Get assigned tickets
        cursor.execute('''
        SELECT status, COUNT(*)
        FROM support_tickets
        WHERE assigned_to = ?
        GROUP BY status
        ''', (username,))
        assigned_stats = dict(cursor.fetchall())
        
        # Get high priority tickets
        cursor.execute('''
        SELECT ticket_id, title, priority, created_datetime, student_id
        FROM support_tickets 
        WHERE priority IN ('High', 'Critical', 'Urgent') 
        AND status NOT IN ('Resolved', 'Closed')
        ORDER BY 
            CASE priority 
                WHEN 'Critical' THEN 1
                WHEN 'Urgent' THEN 2
                WHEN 'High' THEN 3
            END,
            created_datetime ASC
        LIMIT 10
        ''')
        priority_tickets = [dict(zip(['ticket_id', 'title', 'priority', 'created_datetime', 'student_id'], row)) for row in cursor.fetchall()]
        
        # Get team performance metrics
        cursor.execute('''
        SELECT 
            COUNT(*) as total_tickets,
            AVG(CASE WHEN resolved_at IS NOT NULL 
                THEN julianday(resolved_at) - julianday(created_datetime) 
                END) as avg_resolution_days,
            COUNT(CASE WHEN status = 'Resolved' THEN 1 END) as resolved_count
        FROM support_tickets 
        WHERE created_datetime >= date('now', '-30 days')
        ''')
        
        performance_data = cursor.fetchone()
        performance_metrics = {
            'total_tickets_month': performance_data[0] or 0,
            'avg_resolution_time': round(performance_data[1] or 0, 2),
            'resolution_rate': round((performance_data[2] or 0) / max(performance_data[0] or 1, 1) * 100, 1)
        }
        
        # Get recent activity
        cursor.execute('''
        SELECT tr.ticket_id, st.title, tr.response_datetime, tr.responder_role
        FROM ticket_responses tr
        JOIN support_tickets st ON tr.ticket_id = st.ticket_id
        WHERE tr.response_datetime >= datetime('now', '-24 hours')
        ORDER BY tr.response_datetime DESC
        LIMIT 10
        ''')
        recent_activity = [dict(zip(['ticket_id', 'title', 'datetime', 'responder_role'], row)) for row in cursor.fetchall()]
        
        return {
            'assigned_stats': assigned_stats,
            'priority_tickets': priority_tickets,
            'performance_metrics': performance_metrics,
            'recent_activity': recent_activity,
            'quick_actions': [
                {'name': 'View Assigned Tickets', 'action': 'view_assigned'},
                {'name': 'Manage Templates', 'action': 'manage_templates'},
                {'name': 'View Reports', 'action': 'view_reports'}
            ]
        }

    def _get_recent_notifications(self, user_id, cursor):
        """Get recent notifications for user"""
        cursor.execute('''
        SELECT notification_id, title, message, notification_type, created_datetime, is_read
        FROM notifications 
        WHERE user_id = ? 
        AND (expires_at IS NULL OR expires_at > datetime('now'))
        ORDER BY created_datetime DESC 
        LIMIT 10
        ''', (user_id,))
        
        return [
            dict(zip(
                ['notification_id', 'title', 'message', 'type', 'created', 'is_read'],
                row
            ))
            for row in cursor.fetchall()
        ]

    def _get_system_status(self):
        """Get current system status"""
        return {
            'status': 'operational',
            'last_maintenance': '2024-01-15 02:00:00',
            'next_maintenance': '2024-02-15 02:00:00',
            'active_incidents': 0
        }

    def generate_reports(self, report_type, date_range, filters=None):
        """Generate various types of reports"""
        if not auth or not auth.current_user or auth.current_user['role'] not in ('staff', 'admin'):
            raise PermissionError("You must be staff or admin to generate reports")
        
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            report_data = {}
            
            if report_type == 'ticket_summary':
                report_data = self._generate_ticket_summary_report(cursor, date_range, filters)
            elif report_type == 'performance':
                report_data = self._generate_performance_report(cursor, date_range, filters)
            elif report_type == 'satisfaction':
                report_data = self._generate_satisfaction_report(cursor, date_range, filters)
            elif report_type == 'category_analysis':
                report_data = self._generate_category_analysis_report(cursor, date_range, filters)
            
            conn.close()
            
            # Record report generation
            self._log_report_generation(report_type, auth.current_user['id'])
            
            logger.info(f"Report '{report_type}' generated by {auth.current_user['username']}")
            return report_data
            
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            raise

    def _generate_ticket_summary_report(self, cursor, date_range, filters):
        """Generate ticket summary report"""
        date_params = (date_range['start'], date_range['end'])

        # Total tickets
        cursor.execute('SELECT COUNT(*) FROM support_tickets WHERE created_datetime BETWEEN ? AND ?', date_params)
        total_tickets = cursor.fetchone()[0]

        # Tickets by status
        cursor.execute('SELECT status, COUNT(*) FROM support_tickets WHERE created_datetime BETWEEN ? AND ? GROUP BY status', date_params)
        status_breakdown = dict(cursor.fetchall())

        # Tickets by category
        cursor.execute('SELECT category, COUNT(*) FROM support_tickets WHERE created_datetime BETWEEN ? AND ? GROUP BY category', date_params)
        category_breakdown = dict(cursor.fetchall())

        # Tickets by priority
        cursor.execute('SELECT priority, COUNT(*) FROM support_tickets WHERE created_datetime BETWEEN ? AND ? GROUP BY priority', date_params)
        priority_breakdown = dict(cursor.fetchall())

        # Daily ticket creation
        cursor.execute('''
        SELECT DATE(created_datetime) as date, COUNT(*) as count
        FROM support_tickets
        WHERE created_datetime BETWEEN ? AND ?
        GROUP BY DATE(created_datetime)
        ORDER BY date
        ''', date_params)
        daily_creation = [{'date': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        return {
            'total_tickets': total_tickets,
            'status_breakdown': status_breakdown,
            'category_breakdown': category_breakdown,
            'priority_breakdown': priority_breakdown,
            'daily_creation': daily_creation,
            'date_range': date_range
        }

    def _generate_performance_report(self, cursor, date_range, filters):
        """Generate performance metrics report"""
        date_params = (date_range['start'], date_range['end'])

        # Resolution time statistics
        cursor.execute('''
        SELECT
            AVG(julianday(resolved_at) - julianday(created_datetime)) * 24 as avg_hours,
            MIN(julianday(resolved_at) - julianday(created_datetime)) * 24 as min_hours,
            MAX(julianday(resolved_at) - julianday(created_datetime)) * 24 as max_hours,
            COUNT(*) as resolved_count
        FROM support_tickets
        WHERE created_datetime BETWEEN ? AND ? AND resolved_at IS NOT NULL
        ''', date_params)

        resolution_stats = cursor.fetchone()

        # Staff performance
        cursor.execute('''
        SELECT
            assigned_to,
            COUNT(*) as total_assigned,
            COUNT(CASE WHEN status = 'Resolved' THEN 1 END) as resolved,
            AVG(CASE WHEN resolved_at IS NOT NULL
                THEN julianday(resolved_at) - julianday(created_datetime)
                END) * 24 as avg_resolution_hours
        FROM support_tickets
        WHERE created_datetime BETWEEN ? AND ? AND assigned_to IS NOT NULL
        GROUP BY assigned_to
        ''', date_params)
        
        staff_performance = [
            {
                'staff_member': row[0],
                'total_assigned': row[1],
                'resolved': row[2],
                'resolution_rate': round(row[2] / row[1] * 100, 1) if row[1] > 0 else 0,
                'avg_resolution_hours': round(row[3] or 0, 1)
            }
            for row in cursor.fetchall()
        ]
        
        return {
            'resolution_stats': {
                'avg_hours': round(resolution_stats[0] or 0, 1),
                'min_hours': round(resolution_stats[1] or 0, 1),
                'max_hours': round(resolution_stats[2] or 0, 1),
                'resolved_count': resolution_stats[3]
            },
            'staff_performance': staff_performance,
            'date_range': date_range
        }

    def _generate_satisfaction_report(self, cursor, date_range, filters):
        """Generate satisfaction survey report"""
        date_params = (date_range['start'], date_range['end'])

        # Average satisfaction rating
        cursor.execute('''
        SELECT
            AVG(satisfaction_rating) as avg_rating,
            COUNT(satisfaction_rating) as response_count,
            COUNT(*) as total_resolved
        FROM support_tickets
        WHERE resolved_at BETWEEN ? AND ? AND satisfaction_rating IS NOT NULL
        ''', date_params)

        satisfaction_data = cursor.fetchone()

        # Rating distribution
        cursor.execute('''
        SELECT satisfaction_rating, COUNT(*)
        FROM support_tickets
        WHERE resolved_at BETWEEN ? AND ? AND satisfaction_rating IS NOT NULL
        GROUP BY satisfaction_rating
        ORDER BY satisfaction_rating
        ''', date_params)
        
        rating_distribution = dict(cursor.fetchall())
        
        return {
            'avg_rating': round(satisfaction_data[0] or 0, 2),
            'response_rate': round(satisfaction_data[1] / max(satisfaction_data[2], 1) * 100, 1),
            'total_responses': satisfaction_data[1],
            'rating_distribution': rating_distribution,
            'date_range': date_range
        }

    def _generate_category_analysis_report(self, cursor, date_range, filters):
        """Generate category analysis report"""
        date_params = (date_range['start'], date_range['end'])

        # Category statistics
        cursor.execute('''
        SELECT
            category,
            COUNT(*) as total_tickets,
            COUNT(CASE WHEN status = 'Resolved' THEN 1 END) as resolved,
            AVG(CASE WHEN resolved_at IS NOT NULL
                THEN julianday(resolved_at) - julianday(created_datetime)
                END) * 24 as avg_resolution_hours,
            AVG(satisfaction_rating) as avg_satisfaction
        FROM support_tickets
        WHERE created_datetime BETWEEN ? AND ?
        GROUP BY category
        ORDER BY total_tickets DESC
        ''', date_params)
        
        category_stats = [
            {
                'category': row[0],
                'total_tickets': row[1],
                'resolved': row[2],
                'resolution_rate': round(row[2] / row[1] * 100, 1) if row[1] > 0 else 0,
                'avg_resolution_hours': round(row[3] or 0, 1),
                'avg_satisfaction': round(row[4] or 0, 2)
            }
            for row in cursor.fetchall()
        ]
        
        return {
            'category_stats': category_stats,
            'date_range': date_range
        }

    def _log_report_generation(self, report_type, user_id):
        """Log report generation for audit"""
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT INTO system_metrics (
                metric_name, metric_value, category, recorded_datetime, metadata
            ) VALUES (?, ?, ?, ?, ?)
            ''', (
                'report_generated', 1, 'reports', 
                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                json.dumps({'report_type': report_type, 'user_id': user_id})
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error logging report generation: {e}")

    def _process_escalations(self):
        """Process automatic escalations based on rules"""
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            # Check if table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='escalation_rules'")
            if not cursor.fetchone():
                logger.debug("Escalation rules table doesn't exist yet, skipping escalation processing")
                conn.close()
                return
            
            # Get active escalation rules
            cursor.execute('SELECT * FROM escalation_rules WHERE is_active = 1')
            rules = cursor.fetchall()
            
            for rule in rules:
                self._apply_escalation_rule(rule, cursor)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error processing escalations: {e}")
        
    def _apply_escalation_rule(self, rule, cursor):
        """Apply a specific escalation rule with improved error handling"""
        rule_id, name, category, priority, condition_type, condition_value, action_type, action_target, is_active, created_by, created_datetime = rule
        
        try:
            # Check if required columns exist in support_tickets table
            cursor.execute("PRAGMA table_info(support_tickets)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'created_datetime' not in columns:
                # Fall back to registration_datetime or skip time-based rules
                if condition_type == 'time_based':
                    logger.warning(f"Skipping time-based escalation rule {rule_id}: created_datetime column missing")
                    return
            
            # Build query based on rule conditions
            query = "SELECT * FROM support_tickets WHERE status NOT IN ('Resolved', 'Closed', 'Escalated')"
            params = []
            
            if category:
                query += " AND category = ?"
                params.append(category)
            
            if priority:
                query += " AND priority = ?"
                params.append(priority)
            
            if condition_type == 'time_based':
                hours_threshold = float(condition_value)
                threshold_time = datetime.datetime.now() - datetime.timedelta(hours=hours_threshold)
                
                # Use created_datetime if available, otherwise fall back to registration_datetime
                if 'created_datetime' in columns:
                    query += " AND created_datetime < ?"
                else:
                    # Check if there's a registration_datetime column as fallback
                    if 'registration_datetime' in columns:
                        query += " AND registration_datetime < ?"
                        logger.info(f"Using registration_datetime as fallback for escalation rule {rule_id}")
                    else:
                        logger.warning(f"No suitable datetime column found for escalation rule {rule_id}")
                        return
                
                params.append(threshold_time.strftime('%Y-%m-%d %H:%M:%S'))
            
            cursor.execute(query, params)
            tickets = cursor.fetchall()
            
            # Apply actions to matching tickets
            for ticket in tickets:
                if action_type == 'escalate':
                    self._escalate_ticket(ticket[0], rule_id, cursor)  # ticket[0] is ticket_id
                elif action_type == 'notify':
                    self._create_escalation_notification(ticket[0], action_target, cursor)
                elif action_type == 'reassign':
                    self._reassign_ticket(ticket[0], action_target, cursor)
            
        except Exception as e:
            logger.error(f"Error applying escalation rule {rule_id}: {e}")

    def _escalate_ticket(self, ticket_id, rule_id, cursor):
        """Escalate a ticket"""
        escalation_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Update ticket status
        cursor.execute('''
        UPDATE support_tickets 
        SET status = 'Escalated', escalated_at = ?, last_updated_datetime = ?
        WHERE ticket_id = ?
        ''', (escalation_time, escalation_time, ticket_id))
        
        # Add escalation response
        cursor.execute('''
        INSERT INTO ticket_responses (
            ticket_id, responder_id, responder_role, response_text,
            response_datetime, is_auto_generated
        ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            ticket_id, 'system', 'system',
            f'Ticket automatically escalated due to escalation rule #{rule_id}',
            escalation_time, 1
        ))

    def _create_escalation_notification(self, ticket_id, target, cursor):
        """Create notification for escalation"""
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO notifications (
            user_id, title, message, notification_type,
            related_ticket_id, created_datetime
        ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            target, 'Ticket Escalation Alert',
            f'Ticket #{ticket_id} requires attention due to escalation rules.',
            NotificationType.EMAIL.value, ticket_id, timestamp
        ))

    def _reassign_ticket(self, ticket_id, new_assignee, cursor):
        """Reassign a ticket"""
        update_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        UPDATE support_tickets 
        SET assigned_to = ?, last_updated_datetime = ?
        WHERE ticket_id = ?
        ''', (new_assignee, update_time, ticket_id))

    def _process_notification_queue(self):
        """Process pending notifications"""
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            # Check if table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'")
            if not cursor.fetchone():
                logger.debug("Notifications table doesn't exist yet, skipping notification processing")
                conn.close()
                return
            
            # Mark expired notifications
            cursor.execute('''
            UPDATE notifications 
            SET is_read = 1 
            WHERE expires_at < datetime('now') AND is_read = 0
            ''')
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error processing notification queue: {e}")
            


    def _update_metrics(self):
        """Update system performance metrics with improved error handling"""
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            # Check if table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_metrics'")
            if not cursor.fetchone():
                logger.debug("System metrics table doesn't exist yet, skipping metrics update")
                conn.close()
                return
            
            # Check if support_tickets table has required columns
            cursor.execute("PRAGMA table_info(support_tickets)")
            columns = [column[1] for column in cursor.fetchall()]
            
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Calculate current metrics with fallback handling
            metrics = []
            
            # Active tickets metric
            try:
                cursor.execute('SELECT COUNT(*) FROM support_tickets WHERE status NOT IN ("Resolved", "Closed")')
                active_count = cursor.fetchone()[0] or 0
                metrics.append(('active_tickets', active_count, 'tickets'))
            except Exception as e:
                logger.warning(f"Could not calculate active tickets metric: {e}")
            
            # Average response time metric
            try:
                if 'last_updated_datetime' in columns and 'created_datetime' in columns:
                    cursor.execute('''
                    SELECT AVG(julianday(last_updated_datetime) - julianday(created_datetime)) * 24 
                    FROM support_tickets 
                    WHERE last_updated_datetime IS NOT NULL AND created_datetime IS NOT NULL
                    ''')
                else:
                    # Skip this metric if required columns don't exist
                    logger.debug("Skipping response time metric: required datetime columns missing")
                    cursor.execute('SELECT 0')  # Placeholder query
                
                avg_response_time = cursor.fetchone()[0] or 0
                metrics.append(('avg_response_time', avg_response_time, 'performance'))
            except Exception as e:
                logger.warning(f"Could not calculate response time metric: {e}")
            
            # User satisfaction metric
            try:
                cursor.execute('SELECT AVG(satisfaction_rating) FROM support_tickets WHERE satisfaction_rating IS NOT NULL')
                avg_satisfaction = cursor.fetchone()[0] or 0
                metrics.append(('user_satisfaction', avg_satisfaction, 'satisfaction'))
            except Exception as e:
                logger.warning(f"Could not calculate satisfaction metric: {e}")
            
            # Insert calculated metrics
            for metric_name, value, category in metrics:
                try:
                    cursor.execute('''
                    INSERT INTO system_metrics (
                        metric_name, metric_value, category, recorded_datetime
                    ) VALUES (?, ?, ?, ?)
                    ''', (metric_name, value, category, timestamp))
                except Exception as e:
                    logger.warning(f"Could not insert metric {metric_name}: {e}")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
        
    # Template management methods
    def get_ticket_templates(self):
        """Get all active ticket templates"""
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM ticket_templates WHERE is_active = 1 ORDER BY usage_count DESC')
            templates = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            return templates
            
        except Exception as e:
            logger.error(f"Error getting ticket templates: {e}")
            return []

    def get_response_templates(self, category=None):
        """Get response templates, optionally filtered by category"""
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if category:
                cursor.execute('SELECT * FROM response_templates WHERE is_active = 1 AND (category = ? OR category IS NULL) ORDER BY usage_count DESC', (category,))
            else:
                cursor.execute('SELECT * FROM response_templates WHERE is_active = 1 ORDER BY usage_count DESC')
            
            templates = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            return templates
            
        except Exception as e:
            logger.error(f"Error getting response templates: {e}")
            return []


    def get_ticket_details(self, ticket_id):
        """Get detailed information about a specific ticket"""
        if not auth or not auth.current_user:
            raise PermissionError("You must be logged in to view ticket details")
        
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get ticket
            cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
            ticket = cursor.fetchone()
            
            if not ticket:
                raise ValueError(f"Ticket #{ticket_id} not found")
            
            # Check permissions
            if auth.current_user['role'] == 'student':
                conn_main = get_connection()
                cursor_main = conn_main.cursor()
                cursor_main.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
                result = cursor_main.fetchone()
                conn_main.close()
                
                if not result or result[0] != ticket['student_id']:
                    raise PermissionError("You can only view your own support tickets")
            
            # Get responses
            cursor.execute('''
            SELECT * FROM ticket_responses 
            WHERE ticket_id = ? 
            ORDER BY response_datetime ASC
            ''', (ticket_id,))
            responses = [dict(row) for row in cursor.fetchall()]
            
            # Get attachments
            cursor.execute('SELECT * FROM ticket_attachments WHERE ticket_id = ?', (ticket_id,))
            attachments = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            
            ticket_dict = dict(ticket)
            ticket_dict['responses'] = responses
            ticket_dict['attachments'] = attachments
            
            return ticket_dict
            
        except Exception as e:
            logger.error(f"Error getting ticket details: {e}")
            raise

    def display_enhanced_faqs(support):
        """Display enhanced FAQ interface"""
        try:
            print("\n❓ FREQUENTLY ASKED QUESTIONS")
            print("="*50)
            
            # Get FAQ categories
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT category FROM faqs ORDER BY category')
            categories = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if not categories:
                print("📭 No FAQs available.")
                return
            
            print("📂 Categories:")
            print("0. All Categories")
            for i, category in enumerate(categories, 1):
                print(f"{i}. {category}")
            
            print(f"{len(categories) + 1}. Search FAQs")
            print(f"{len(categories) + 2}. Back")
            
            choice = input("\nSelect option: ").strip()
            
            if choice == '0':
                # Show all FAQs
                faqs = support._search_faqs('', None)
                display_faq_list(faqs, "All FAQs")
            elif choice.isdigit() and 1 <= int(choice) <= len(categories):
                # Show FAQs in category
                category = categories[int(choice) - 1]
                faqs = support._search_faqs('', {'category': category})
                display_faq_list(faqs, f"{category} FAQs")
            elif choice == str(len(categories) + 1):
                # Search FAQs
                search_query = input("Enter search query: ").strip()
                if search_query:
                    faqs = support._search_faqs(search_query, None)
                    display_faq_list(faqs, f"Search Results for '{search_query}'")
            elif choice == str(len(categories) + 2):
                return
            else:
                print("❌ Invalid choice.")
        
        except Exception as e:
            print(f"❌ Error displaying FAQs: {e}")
        
        input("\nPress Enter to continue...")

    def display_faq_list(faqs, title):
        """Display a list of FAQs"""
        print(f"\n❓ {title}")
        print("="*50)
        
        if not faqs:
            print("📭 No FAQs found.")
            return
        
        for i, faq in enumerate(faqs[:10], 1):  # Show first 10
            views = faq.get('view_count', 0)
            votes = faq.get('helpful_votes', 0)
            print(f"{i}. Q: {faq['question']}")
            print(f"   👁️ {views} views | 👍 {votes} helpful")
        
        if len(faqs) > 10:
            print(f"\n... and {len(faqs) - 10} more FAQs")
        
        # View FAQ option
        view_choice = input(f"\nView FAQ (1-{min(len(faqs), 10)}) or press Enter to go back: ").strip()
        if view_choice.isdigit() and 1 <= int(view_choice) <= min(len(faqs), 10):
            faq = faqs[int(view_choice) - 1]
            display_full_faq(faq)

    def display_full_faq(faq):
        """Display full FAQ with answer"""
        print(f"\n❓ {faq['question']}")
        print("="*60)
        print(f"📂 Category: {faq['category']}")
        print(f"👁️ Views: {faq.get('view_count', 0)}")
        print(f"👍 Helpful: {faq.get('helpful_votes', 0)}")
        
        print(f"\n💡 Answer:")
        print("-" * 40)
        print(faq['answer'])
        print("-" * 40)
        
        # Actions
        print("\n🔧 Actions:")
        print("1. Mark as helpful")
        print("2. Back")
        
        action = input("Choose action: ").strip()
        
        if action == '1':
            print("✅ Marked as helpful. Thank you for your feedback!")

    def display_enhanced_resources(support):
        """Display enhanced resources interface"""
        try:
            print("\n📋 SUPPORT RESOURCES")
            print("="*50)
            
            # Get resource categories
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT category FROM support_resources ORDER BY category')
            categories = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if not categories:
                print("📭 No resources available.")
                return
            
            print("📂 Categories:")
            print("0. All Categories")
            for i, category in enumerate(categories, 1):
                print(f"{i}. {category}")
            
            print(f"{len(categories) + 1}. Featured Resources")
            print(f"{len(categories) + 2}. Search Resources")
            print(f"{len(categories) + 3}. Back")
            
            choice = input("\nSelect option: ").strip()
            
            if choice == '0':
                # Show all resources
                resources = support._search_resources('', None)
                display_resource_list(resources, "All Resources")
            elif choice.isdigit() and 1 <= int(choice) <= len(categories):
                # Show resources in category
                category = categories[int(choice) - 1]
                resources = support._search_resources('', {'category': category})
                display_resource_list(resources, f"{category} Resources")
            elif choice == str(len(categories) + 1):
                # Featured resources
                conn = sqlite3.connect(SUPPORT_DB)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM support_resources WHERE is_featured = 1 ORDER BY access_count DESC')
                resources = [dict(row) for row in cursor.fetchall()]
                conn.close()
                display_resource_list(resources, "Featured Resources")
            elif choice == str(len(categories) + 2):
                # Search resources
                search_query = input("Enter search query: ").strip()
                if search_query:
                    resources = support._search_resources(search_query, None)
                    display_resource_list(resources, f"Search Results for '{search_query}'")
            elif choice == str(len(categories) + 3):
                return
            else:
                print("❌ Invalid choice.")
        
        except Exception as e:
            print(f"❌ Error displaying resources: {e}")
        
        input("\nPress Enter to continue...")

    def display_resource_list(resources, title):
        """Display a list of support resources"""
        print(f"\n📋 {title}")
        print("="*50)
        
        if not resources:
            print("📭 No resources found.")
            return
        
        for i, resource in enumerate(resources[:10], 1):  # Show first 10
            access_count = resource.get('access_count', 0)
            print(f"{i}. 📄 {resource['title']}")
            print(f"   📂 Category: {resource['category']}")
            print(f"   👁️ {access_count} accesses")
            print(f"   📝 {resource['description'][:80]}...")
        
        if len(resources) > 10:
            print(f"\n... and {len(resources) - 10} more resources")
        
        # View resource option
        view_choice = input(f"\nView resource (1-{min(len(resources), 10)}) or press Enter to go back: ").strip()
        if view_choice.isdigit() and 1 <= int(view_choice) <= min(len(resources), 10):
            resource = resources[int(view_choice) - 1]
            display_full_resource(resource)

    def display_full_resource(resource):
        """Display full resource details"""
        print(f"\n📄 {resource['title']}")
        print("="*60)
        print(f"📂 Category: {resource['category']}")
        print(f"✍️ Created by: {resource['created_by']}")
        print(f"📅 Created: {resource['created_datetime']}")
        print(f"👁️ Accesses: {resource.get('access_count', 0)}")
        
        if resource.get('tags'):
            tags = json.loads(resource['tags']) if isinstance(resource['tags'], str) else resource['tags']
            if tags:
                print(f"🏷️ Tags: {', '.join(tags)}")
        
        print(f"\n📝 Description:")
        print("-" * 40)
        print(resource['description'])
        print("-" * 40)
        
        if resource.get('url'):
            print(f"🔗 URL: {resource['url']}")
        
        if resource.get('file_path'):
            print(f"📁 File: {resource['file_path']}")

    def view_my_tickets_enhanced(support):
        """View student's own tickets with enhanced filtering"""
        try:
            print("\n🎫 MY SUPPORT TICKETS")
            print("="*50)
            
            # Get student ID
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                print("❌ No student ID associated with your account.")
                return
            
            student_id = result[0]
            
            # Filter options
            print("📊 Filter Options:")
            print("1. All tickets")
            print("2. Open tickets")
            print("3. In Progress tickets")
            print("4. Resolved tickets")
            print("5. By category")
            print("6. By priority")
            print("7. Search tickets")
            
            choice = input("\nSelect filter: ").strip()
            
            filters = {}
            
            if choice == '2':
                filters['status'] = 'Open'
            elif choice == '3':
                filters['status'] = 'In Progress'
            elif choice == '4':
                filters['status'] = 'Resolved'
            elif choice == '5':
                print("\nCategories:")
                for i, cat in enumerate(SUPPORT_CATEGORIES, 1):
                    print(f"{i}. {cat}")
                cat_choice = input(f"Select category (1-{len(SUPPORT_CATEGORIES)}): ").strip()
                if cat_choice.isdigit() and 1 <= int(cat_choice) <= len(SUPPORT_CATEGORIES):
                    filters['category'] = SUPPORT_CATEGORIES[int(cat_choice) - 1]
            elif choice == '6':
                print("\nPriorities:")
                for i, pri in enumerate(TICKET_PRIORITIES, 1):
                    print(f"{i}. {pri}")
                pri_choice = input(f"Select priority (1-{len(TICKET_PRIORITIES)}): ").strip()
                if pri_choice.isdigit() and 1 <= int(pri_choice) <= len(TICKET_PRIORITIES):
                    filters['priority'] = TICKET_PRIORITIES[int(pri_choice) - 1]
            elif choice == '7':
                search_query = input("Enter search query: ").strip()
                if search_query:
                    filters['search'] = search_query
            
            # Get tickets
            result = support.get_student_tickets(student_id, filters, page=1, per_page=20)
            tickets = result['tickets']
            
            if not tickets:
                print("📭 No tickets found with the selected filters.")
                return
            
            # Display tickets
            print(f"\n🎫 Found {result['total_count']} tickets (showing page {result['page']} of {result['total_pages']}):")
            print("="*80)
            
            for ticket in tickets:
                status_emoji = {'Open': '🔓', 'In Progress': '⏳', 'Resolved': '✅', 'Closed': '🔒'}.get(ticket['status'], '❓')
                priority_emoji = {'Critical': '🔴', 'Urgent': '🟠', 'High': '🟡', 'Medium': '🔵', 'Low': '🟢'}.get(ticket['priority'], '⚪')
                
                print(f"{status_emoji} #{ticket['ticket_id']} - {ticket['title']}")
                print(f"   📂 {ticket['category']} | {priority_emoji} {ticket['priority']} | 📅 {ticket['created_datetime']}")
                
                if ticket.get('assigned_to'):
                    print(f"   👨‍💼 Assigned to: {ticket['assigned_to']}")
                
                if ticket.get('attachment_count', 0) > 0:
                    print(f"   📎 {ticket['attachment_count']} attachments")
                
                last_response = ticket.get('last_response_by')
                if last_response:
                    print(f"   💬 Last response: {last_response['role']} on {last_response['datetime']}")
                
                print()
            
            # View specific ticket
            if tickets:
                ticket_choice = input(f"View ticket details (enter ticket #) or press Enter to go back: ").strip()
                if ticket_choice.isdigit():
                    ticket_id = int(ticket_choice)
                    if any(t['ticket_id'] == ticket_id for t in tickets):
                        display_ticket_details_enhanced(support, ticket_id)
                    else:
                        print("❌ Ticket not found in current list.")
        
        except Exception as e:
            print(f"❌ Error viewing tickets: {e}")
        
        input("\nPress Enter to continue...")

    def use_ticket_template(support):
        """Create ticket using a template"""
        try:
            print("\n📋 USE TICKET TEMPLATE")
            print("="*50)
            
            templates = support.get_ticket_templates()
            
            if not templates:
                print("📭 No ticket templates available.")
                return
            
            print("📋 Available Templates:")
            for i, template in enumerate(templates, 1):
                print(f"{i}. {template['name']}")
                print(f"   📂 Category: {template['category']} | 🔥 Priority: {template['priority']}")
                print(f"   📈 Used {template.get('usage_count', 0)} times")
                print()
            
            choice = input(f"Select template (1-{len(templates)}): ").strip()
            
            if not choice.isdigit() or not 1 <= int(choice) <= len(templates):
                print("❌ Invalid choice.")
                return
            
            template = templates[int(choice) - 1]
            
            # Get student ID
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                print("❌ No student ID associated with your account.")
                return
            
            student_id = result[0]
            
            print(f"\n📋 Using template: {template['name']}")
            print("="*50)
            
            # Pre-fill from template
            title = template['title_template']
            description = template['description_template']
            category = template['category']
            priority = template['priority']
            
            print(f"Title: {title}")
            print(f"Category: {category}")
            print(f"Priority: {priority}")
            print(f"\nDescription:\n{description}")
            
            # Allow customization
            print("\n🔧 Customize Template:")
            custom_title = input(f"Custom title (or press Enter to keep '{title}'): ").strip()
            if custom_title:
                title = custom_title
            
            print("Additional description (press Enter twice to finish):")
            additional_lines = []
            while True:
                line = input()
                if not line and (not additional_lines or not additional_lines[-1]):
                    break
                additional_lines.append(line)
            
            if additional_lines:
                description += "\n\n" + '\n'.join(additional_lines)
            
            # Create ticket
            print("\n🎫 Creating ticket from template...")
            ticket_id = support.create_support_ticket(
                student_id, title, description, category, priority,
                template_id=template['template_id']
            )
            
            print(f"✅ Support ticket #{ticket_id} created successfully from template!")
            
            # View ticket details
            view_choice = input("\nView ticket details? (y/n): ").lower()
            if view_choice == 'y':
                display_ticket_details_enhanced(support, ticket_id)
        
        except Exception as e:
            print(f"❌ Error using template: {e}")
        
        input("\nPress Enter to continue...")

    def view_all_tickets_enhanced(support):
        """View all tickets with advanced filtering (staff only)"""
        try:
            print("\n🎫 ALL SUPPORT TICKETS")
            print("="*50)
            
            # Advanced filter menu
            print("📊 Filter Options:")
            print("1. All tickets")
            print("2. By status")
            print("3. By category")
            print("4. By priority")
            print("5. By assigned staff")
            print("6. By date range")
            print("7. Unassigned tickets")
            print("8. High priority tickets")
            print("9. Overdue tickets")
            print("10. Search tickets")
            
            choice = input("\nSelect filter: ").strip()
            
            filters = {}
            
            if choice == '2':
                print("\nStatuses:")
                for i, status in enumerate(TICKET_STATUSES, 1):
                    print(f"{i}. {status}")
                status_choice = input(f"Select status (1-{len(TICKET_STATUSES)}): ").strip()
                if status_choice.isdigit() and 1 <= int(status_choice) <= len(TICKET_STATUSES):
                    filters['status'] = TICKET_STATUSES[int(status_choice) - 1]
            elif choice == '3':
                print("\nCategories:")
                for i, cat in enumerate(SUPPORT_CATEGORIES, 1):
                    print(f"{i}. {cat}")
                cat_choice = input(f"Select category (1-{len(SUPPORT_CATEGORIES)}): ").strip()
                if cat_choice.isdigit() and 1 <= int(cat_choice) <= len(SUPPORT_CATEGORIES):
                    filters['category'] = SUPPORT_CATEGORIES[int(cat_choice) - 1]
            elif choice == '4':
                print("\nPriorities:")
                for i, pri in enumerate(TICKET_PRIORITIES, 1):
                    print(f"{i}. {pri}")
                pri_choice = input(f"Select priority (1-{len(TICKET_PRIORITIES)}): ").strip()
                if pri_choice.isdigit() and 1 <= int(pri_choice) <= len(TICKET_PRIORITIES):
                    filters['priority'] = TICKET_PRIORITIES[int(pri_choice) - 1]
            elif choice == '5':
                assigned_to = input("Enter staff username: ").strip()
                if assigned_to:
                    filters['assigned_to'] = assigned_to
            elif choice == '6':
                date_from = input("From date (YYYY-MM-DD): ").strip()
                date_to = input("To date (YYYY-MM-DD): ").strip()
                if date_from:
                    filters['date_from'] = date_from
                if date_to:
                    filters['date_to'] = date_to
            elif choice == '7':
                filters['assigned_to'] = None
            elif choice == '8':
                filters['priority'] = 'High'  # Could be expanded to include Critical, Urgent
            elif choice == '10':
                search_query = input("Enter search query: ").strip()
                if search_query:
                    filters['search'] = search_query
            
            # Get tickets
            result = support.get_student_tickets(None, filters, page=1, per_page=20)
            tickets = result['tickets']
            
            if not tickets:
                print("📭 No tickets found with the selected filters.")
                return
            
            # Display tickets
            print(f"\n🎫 Found {result['total_count']} tickets (showing page {result['page']} of {result['total_pages']}):")
            print("="*100)
            
            for ticket in tickets:
                status_emoji = {'Open': '🔓', 'In Progress': '⏳', 'Resolved': '✅', 'Closed': '🔒', 'Escalated': '🚨'}.get(ticket['status'], '❓')
                priority_emoji = {'Critical': '🔴', 'Urgent': '🟠', 'High': '🟡', 'Medium': '🔵', 'Low': '🟢'}.get(ticket['priority'], '⚪')
                
                print(f"{status_emoji} #{ticket['ticket_id']} - {ticket['title']}")
                print(f"   👤 Student: {ticket['student_id']} | 📂 {ticket['category']} | {priority_emoji} {ticket['priority']}")
                print(f"   📅 Created: {ticket['created_datetime']}")
                
                if ticket.get('assigned_to'):
                    print(f"   👨‍💼 Assigned to: {ticket['assigned_to']}")
                else:
                    print(f"   ❌ Unassigned")
                
                if ticket.get('sentiment') and ticket['sentiment'] != 'neutral':
                    sentiment_emoji = {'positive': '😊', 'negative': '😞', 'frustrated': '😤'}.get(ticket['sentiment'], '😐')
                    print(f"   {sentiment_emoji} Sentiment: {ticket['sentiment']}")
                
                print()
            
            # Actions menu
            print("🔧 Actions:")
            print("1. View ticket details")
            print("2. Bulk assign tickets")
            print("3. Bulk update status")
            print("4. Export filtered results")
            print("5. Back")
            
            action = input("\nSelect action: ").strip()
            
            if action == '1':
                ticket_choice = input("Enter ticket #: ").strip()
                if ticket_choice.isdigit():
                    ticket_id = int(ticket_choice)
                    if any(t['ticket_id'] == ticket_id for t in tickets):
                        display_ticket_details_enhanced(support, ticket_id)
                    else:
                        print("❌ Ticket not found in current list.")
            elif action == '2':
                perform_bulk_assign(support, tickets)
            elif action == '3':
                perform_bulk_status_update(support, tickets)
            elif action == '4':
                export_filtered_results(support, filters)
        
        except Exception as e:
            print(f"❌ Error viewing tickets: {e}")
        
        input("\nPress Enter to continue...")

    def manage_templates_menu(support):
        """Manage ticket and response templates (staff only)"""
        try:
            print("\n📋 MANAGE TEMPLATES")
            print("="*40)
            
            print("1. View ticket templates")
            print("2. Create ticket template")
            print("3. View response templates")
            print("4. Create response template")
            print("5. Template usage statistics")
            print("6. Back")
            
            choice = input("\nSelect option: ").strip()
            
            if choice == '1':
                view_ticket_templates(support)
            elif choice == '2':
                create_ticket_template_interactive(support)
            elif choice == '3':
                view_response_templates(support)
            elif choice == '4':
                create_response_template_interactive(support)
            elif choice == '5':
                show_template_statistics(support)
            elif choice == '6':
                return
            else:
                print("❌ Invalid choice.")
        
        except Exception as e:
            print(f"❌ Error managing templates: {e}")
        
        input("\nPress Enter to continue...")

    def view_ticket_templates(support):
        """View all ticket templates"""
        templates = support.get_ticket_templates()
        
        if not templates:
            print("📭 No ticket templates found.")
            return
        
        print("\n📋 TICKET TEMPLATES")
        print("="*50)
        
        for template in templates:
            print(f"📄 {template['name']}")
            print(f"   📂 Category: {template['category']} | 🔥 Priority: {template['priority']}")
            print(f"   📈 Used {template.get('usage_count', 0)} times")
            print(f"   ✍️ Created by: {template['created_by']} on {template['created_datetime']}")
            print(f"   📝 Title: {template['title_template'][:60]}...")
            print()

    def create_ticket_template_interactive(support):
        """Interactive ticket template creation"""
        print("\n📋 CREATE TICKET TEMPLATE")
        print("="*40)
        
        name = input("Template name: ").strip()
        if not name:
            print("❌ Template name is required.")
            return
        
        title_template = input("Title template: ").strip()
        if not title_template:
            print("❌ Title template is required.")
            return
        
        print("Description template (press Enter twice to finish):")
        lines = []
        while True:
            line = input()
            if not line and (not lines or not lines[-1]):
                break
            lines.append(line)
        
        description_template = '\n'.join(lines)
        if not description_template:
            print("❌ Description template is required.")
            return
        
        print("\nCategories:")
        for i, cat in enumerate(SUPPORT_CATEGORIES, 1):
            print(f"{i}. {cat}")
        
        cat_choice = input(f"Select category (1-{len(SUPPORT_CATEGORIES)}): ").strip()
        if not cat_choice.isdigit() or not 1 <= int(cat_choice) <= len(SUPPORT_CATEGORIES):
            print("❌ Invalid category.")
            return
        
        category = SUPPORT_CATEGORIES[int(cat_choice) - 1]
        
        print("\nPriorities:")
        for i, pri in enumerate(TICKET_PRIORITIES, 1):
            print(f"{i}. {pri}")
        
        pri_choice = input(f"Select priority (1-{len(TICKET_PRIORITIES)}): ").strip()
        if not pri_choice.isdigit() or not 1 <= int(pri_choice) <= len(TICKET_PRIORITIES):
            print("❌ Invalid priority.")
            return
        
        priority = TICKET_PRIORITIES[int(pri_choice) - 1]
        
        # Create template
        template_id = support.create_ticket_template(name, title_template, description_template, category, priority)
        print(f"✅ Ticket template '{name}' created successfully (ID: {template_id})!")

    def view_response_templates(support):
        """View all response templates"""
        templates = support.get_response_templates()
        
        if not templates:
            print("📭 No response templates found.")
            return
        
        print("\n💬 RESPONSE TEMPLATES")
        print("="*50)
        
        for template in templates:
            print(f"💬 {template['name']}")
            if template.get('category'):
                print(f"   📂 Category: {template['category']}")
            print(f"   📈 Used {template.get('usage_count', 0)} times")
            print(f"   ✍️ Created by: {template['created_by']} on {template['created_datetime']}")
            if template.get('subject'):
                print(f"   📧 Subject: {template['subject']}")
            print(f"   📝 Content: {template['content'][:100]}...")
            print()

    def create_response_template_interactive(support):
        """Interactive response template creation"""
        print("\n💬 CREATE RESPONSE TEMPLATE")
        print("="*40)
        
        name = input("Template name: ").strip()
        if not name:
            print("❌ Template name is required.")
            return
        
        subject = input("Email subject (optional): ").strip()
        
        print("Template content (press Enter twice to finish):")
        lines = []
        while True:
            line = input()
            if not line and (not lines or not lines[-1]):
                break
            lines.append(line)
        
        content = '\n'.join(lines)
        if not content:
            print("❌ Template content is required.")
            return
        
        category = input("Category (optional): ").strip() or None
        
        variables_input = input("Variables (comma-separated, e.g., TICKET_ID,USER_NAME): ").strip()
        variables = [var.strip() for var in variables_input.split(',')] if variables_input else []
        
        # Create template
        template_id = support.create_response_template(name, subject, content, category, variables)
        print(f"✅ Response template '{name}' created successfully (ID: {template_id})!")

    def show_template_statistics(support):
        """Show template usage statistics"""
        print("\n📊 TEMPLATE USAGE STATISTICS")
        print("="*50)
        
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            # Ticket template stats
            cursor.execute('''
            SELECT name, usage_count, created_datetime 
            FROM ticket_templates 
            WHERE is_active = 1 
            ORDER BY usage_count DESC
            ''')
            ticket_templates = cursor.fetchall()
            
            print("🎫 TICKET TEMPLATES:")
            if ticket_templates:
                for name, usage_count, created_date in ticket_templates:
                    print(f"   📋 {name}: {usage_count} uses (created {created_date})")
            else:
                print("   📭 No ticket templates found.")
            
            # Response template stats
            cursor.execute('''
            SELECT name, usage_count, created_datetime 
            FROM response_templates 
            WHERE is_active = 1 
            ORDER BY usage_count DESC
            ''')
            response_templates = cursor.fetchall()
            
            print("\n💬 RESPONSE TEMPLATES:")
            if response_templates:
                for name, usage_count, created_date in response_templates:
                    print(f"   💬 {name}: {usage_count} uses (created {created_date})")
            else:
                print("   📭 No response templates found.")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ Error getting template statistics: {e}")

    def manage_knowledge_base_menu(support):
        """Manage knowledge base articles (staff only)"""
        try:
            print("\n📚 MANAGE KNOWLEDGE BASE")
            print("="*40)
            
            print("1. View all articles")
            print("2. Create new article")
            print("3. Publish article")
            print("4. Article statistics")
            print("5. Back")
            
            choice = input("\nSelect option: ").strip()
            
            if choice == '1':
                view_all_kb_articles(support)
            elif choice == '2':
                create_kb_article_interactive(support)
            elif choice == '3':
                publish_kb_article_interactive(support)
            elif choice == '4':
                show_kb_statistics(support)
            elif choice == '5':
                return
            else:
                print("❌ Invalid choice.")
        
        except Exception as e:
            print(f"❌ Error managing knowledge base: {e}")
        
        input("\nPress Enter to continue...")

    def view_all_kb_articles(support):
        """View all knowledge base articles"""
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
            print(f"   ✍️ Author: {article['author_id']} | 📅 Created: {article['created_datetime']}")
            print(f"   👁️ Views: {article.get('view_count', 0)} | 👍 Helpful: {article.get('helpful_votes', 0)}")
            if article.get('summary'):
                print(f"   📝 {article['summary'][:80]}...")
            print()

    def create_kb_article_interactive(support):
        """Interactive knowledge base article creation"""
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

    def show_kb_statistics(support):
        """Show knowledge base statistics"""
        print("\n📊 KNOWLEDGE BASE STATISTICS")
        print("="*50)
        
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            # Overall stats
            cursor.execute('SELECT COUNT(*) FROM kb_articles WHERE is_published = 1')
            published_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM kb_articles WHERE is_published = 0')
            draft_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT SUM(view_count) FROM kb_articles')
            total_views = cursor.fetchone()[0] or 0
            
            cursor.execute('SELECT SUM(helpful_votes) FROM kb_articles')
            total_helpful = cursor.fetchone()[0] or 0
            
            print(f"📚 Total Articles: {published_count + draft_count}")
            print(f"✅ Published: {published_count}")
            print(f"📝 Drafts: {draft_count}")
            print(f"👁️ Total Views: {total_views}")
            print(f"👍 Total Helpful Votes: {total_helpful}")
            
            # Most viewed articles
            cursor.execute('''
            SELECT title, view_count 
            FROM kb_articles 
            WHERE is_published = 1 
            ORDER BY view_count DESC 
            LIMIT 5
            ''')
            most_viewed = cursor.fetchall()
            
            print("\n🔥 MOST VIEWED ARTICLES:")
            for title, views in most_viewed:
                print(f"   👁️ {title}: {views} views")
            
            # Most helpful articles
            cursor.execute('''
            SELECT title, helpful_votes 
            FROM kb_articles 
            WHERE is_published = 1 
            ORDER BY helpful_votes DESC 
            LIMIT 5
            ''')
            most_helpful = cursor.fetchall()
            
            print("\n👍 MOST HELPFUL ARTICLES:")
            for title, votes in most_helpful:
                print(f"   👍 {title}: {votes} votes")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ Error getting knowledge base statistics: {e}")

    def bulk_operations_menu(support):
        """Bulk operations menu (staff only)"""
        try:
            print("\n📦 BULK OPERATIONS")
            print("="*40)
            
            print("1. Bulk assign tickets")
            print("2. Bulk update ticket status")
            print("3. Bulk update ticket priority")
            print("4. Bulk update ticket category")
            print("5. Merge tickets")
            print("6. Back")
            
            choice = input("\nSelect operation: ").strip()
            
            if choice == '1':
                bulk_assign_tickets_menu(support)
            elif choice == '2':
                bulk_update_status_menu(support)
            elif choice == '3':
                bulk_update_priority_menu(support)
            elif choice == '4':
                bulk_update_category_menu(support)
            elif choice == '5':
                merge_tickets_menu(support)
            elif choice == '6':
                return
            else:
                print("❌ Invalid choice.")
        
        except Exception as e:
            print(f"❌ Error in bulk operations: {e}")
        
        input("\nPress Enter to continue...")

    def bulk_assign_tickets_menu(support):
        """Bulk assign tickets to staff"""
        print("\n👨‍💼 BULK ASSIGN TICKETS")
        print("="*40)
        
        # Get ticket IDs
        ticket_ids_input = input("Enter ticket IDs (comma-separated): ").strip()
        if not ticket_ids_input:
            print("❌ No ticket IDs provided.")
            return
        
        try:
            ticket_ids = [int(id.strip()) for id in ticket_ids_input.split(',')]
        except ValueError:
            print("❌ Invalid ticket IDs. Please enter numbers only.")
            return
        
        assigned_to = input("Assign to (username): ").strip()
        if not assigned_to:
            print("❌ Staff username is required.")
            return
        
        # Confirm operation
        print(f"\n📋 Assigning {len(ticket_ids)} tickets to {assigned_to}")
        confirm = input("Confirm bulk assignment? (y/n): ").lower()
        
        if confirm == 'y':
            try:
                updates = {'assigned_to': assigned_to}
                updated_count = support.bulk_update_tickets(ticket_ids, updates)
                print(f"✅ Successfully assigned {updated_count} tickets to {assigned_to}")
            except Exception as e:
                print(f"❌ Error during bulk assignment: {e}")
        else:
            print("❌ Bulk assignment cancelled.")

    def bulk_update_status_menu(support):
        """Bulk update ticket status"""
        print("\n📊 BULK UPDATE STATUS")
        print("="*40)
        
        # Get ticket IDs
        ticket_ids_input = input("Enter ticket IDs (comma-separated): ").strip()
        if not ticket_ids_input:
            print("❌ No ticket IDs provided.")
            return
        
        try:
            ticket_ids = [int(id.strip()) for id in ticket_ids_input.split(',')]
        except ValueError:
            print("❌ Invalid ticket IDs. Please enter numbers only.")
            return
        
        # Select new status
        print("\nStatuses:")
        for i, status in enumerate(TICKET_STATUSES, 1):
            print(f"{i}. {status}")
        
        status_choice = input(f"Select new status (1-{len(TICKET_STATUSES)}): ").strip()
        if not status_choice.isdigit() or not 1 <= int(status_choice) <= len(TICKET_STATUSES):
            print("❌ Invalid status choice.")
            return
        
        new_status = TICKET_STATUSES[int(status_choice) - 1]
        
        # Confirm operation
        print(f"\n📋 Updating {len(ticket_ids)} tickets to status '{new_status}'")
        confirm = input("Confirm bulk status update? (y/n): ").lower()
        
        if confirm == 'y':
            try:
                updates = {'status': new_status}
                updated_count = support.bulk_update_tickets(ticket_ids, updates)
                print(f"✅ Successfully updated status for {updated_count} tickets")
            except Exception as e:
                print(f"❌ Error during bulk status update: {e}")
        else:
            print("❌ Bulk status update cancelled.")

    def bulk_update_priority_menu(support):
        """Bulk update ticket priority"""
        print("\n🔥 BULK UPDATE PRIORITY")
        print("="*40)
        
        # Get ticket IDs
        ticket_ids_input = input("Enter ticket IDs (comma-separated): ").strip()
        if not ticket_ids_input:
            print("❌ No ticket IDs provided.")
            return
        
        try:
            ticket_ids = [int(id.strip()) for id in ticket_ids_input.split(',')]
        except ValueError:
            print("❌ Invalid ticket IDs. Please enter numbers only.")
            return
        
        # Select new priority
        print("\nPriorities:")
        for i, priority in enumerate(TICKET_PRIORITIES, 1):
            print(f"{i}. {priority}")
        
        priority_choice = input(f"Select new priority (1-{len(TICKET_PRIORITIES)}): ").strip()
        if not priority_choice.isdigit() or not 1 <= int(priority_choice) <= len(TICKET_PRIORITIES):
            print("❌ Invalid priority choice.")
            return
        
        new_priority = TICKET_PRIORITIES[int(priority_choice) - 1]
        
        # Confirm operation
        print(f"\n📋 Updating {len(ticket_ids)} tickets to priority '{new_priority}'")
        confirm = input("Confirm bulk priority update? (y/n): ").lower()
        
        if confirm == 'y':
            try:
                updates = {'priority': new_priority}
                updated_count = support.bulk_update_tickets(ticket_ids, updates)
                print(f"✅ Successfully updated priority for {updated_count} tickets")
            except Exception as e:
                print(f"❌ Error during bulk priority update: {e}")
        else:
            print("❌ Bulk priority update cancelled.")

    def bulk_update_category_menu(support):
        """Bulk update ticket category"""
        print("\n📂 BULK UPDATE CATEGORY")
        print("="*40)
        
        # Get ticket IDs
        ticket_ids_input = input("Enter ticket IDs (comma-separated): ").strip()
        if not ticket_ids_input:
            print("❌ No ticket IDs provided.")
            return
        
        try:
            ticket_ids = [int(id.strip()) for id in ticket_ids_input.split(',')]
        except ValueError:
            print("❌ Invalid ticket IDs. Please enter numbers only.")
            return
        
        # Select new category
        print("\nCategories:")
        for i, category in enumerate(SUPPORT_CATEGORIES, 1):
            print(f"{i}. {category}")
        
        category_choice = input(f"Select new category (1-{len(SUPPORT_CATEGORIES)}): ").strip()
        if not category_choice.isdigit() or not 1 <= int(category_choice) <= len(SUPPORT_CATEGORIES):
            print("❌ Invalid category choice.")
            return
        
        new_category = SUPPORT_CATEGORIES[int(category_choice) - 1]
        
        # Confirm operation
        print(f"\n📋 Updating {len(ticket_ids)} tickets to category '{new_category}'")
        confirm = input("Confirm bulk category update? (y/n): ").lower()
        
        if confirm == 'y':
            try:
                updates = {'category': new_category}
                updated_count = support.bulk_update_tickets(ticket_ids, updates)
                print(f"✅ Successfully updated category for {updated_count} tickets")
            except Exception as e:
                print(f"❌ Error during bulk category update: {e}")
        else:
            print("❌ Bulk category update cancelled.")

    def merge_tickets_menu(support):
        """Merge multiple tickets into one"""
        print("\n🔗 MERGE TICKETS")
        print("="*40)
        
        primary_id_input = input("Enter primary ticket ID: ").strip()
        if not primary_id_input.isdigit():
            print("❌ Invalid primary ticket ID.")
            return
        
        primary_ticket_id = int(primary_id_input)
        
        secondary_ids_input = input("Enter secondary ticket IDs to merge (comma-separated): ").strip()
        if not secondary_ids_input:
            print("❌ No secondary ticket IDs provided.")
            return
        
        try:
            secondary_ticket_ids = [int(id.strip()) for id in secondary_ids_input.split(',')]
        except ValueError:
            print("❌ Invalid secondary ticket IDs. Please enter numbers only.")
            return
        
        merge_reason = input("Reason for merge: ").strip()
        if not merge_reason:
            print("❌ Merge reason is required.")
            return
        
        # Confirm operation
        print(f"\n📋 Merging tickets {secondary_ticket_ids} into primary ticket #{primary_ticket_id}")
        print(f"Reason: {merge_reason}")
        confirm = input("Confirm ticket merge? (y/n): ").lower()
        
        if confirm == 'y':
            try:
                support.merge_tickets(primary_ticket_id, secondary_ticket_ids, merge_reason)
                print(f"✅ Successfully merged {len(secondary_ticket_ids)} tickets into #{primary_ticket_id}")
            except Exception as e:
                print(f"❌ Error during ticket merge: {e}")
        else:
            print("❌ Ticket merge cancelled.")

    def export_data_menu(support):
        """Export data menu (staff only)"""
        try:
            print("\n📤 EXPORT DATA")
            print("="*40)
            
            print("1. Export tickets")
            print("2. Export responses")
            print("3. Export metrics")
            print("4. Export filtered ticket results")
            print("5. Back")
            
            choice = input("\nSelect export type: ").strip()
            
            if choice == '1':
                export_tickets_menu(support)
            elif choice == '2':
                export_responses_menu(support)
            elif choice == '3':
                export_metrics_menu(support)
            elif choice == '4':
                export_filtered_tickets_menu(support)
            elif choice == '5':
                return
            else:
                print("❌ Invalid choice.")
        
        except Exception as e:
            print(f"❌ Error in export menu: {e}")
        
        input("\nPress Enter to continue...")

    def export_tickets_menu(support):
        """Export tickets with filters"""
        print("\n📤 EXPORT TICKETS")
        print("="*40)
        
        # Date range
        date_from = input("From date (YYYY-MM-DD, optional): ").strip() or None
        date_to = input("To date (YYYY-MM-DD, optional): ").strip() or None
        
        # Status filter
        status = input(f"Status filter ({', '.join(TICKET_STATUSES)}, optional): ").strip() or None
        if status and status not in TICKET_STATUSES:
            print("❌ Invalid status.")
            return
        
        # Format
        print("\nExport formats:")
        print("1. CSV")
        print("2. JSON")
        
        format_choice = input("Select format (1-2): ").strip()
        export_format = 'csv' if format_choice == '1' else 'json'
        
        # Build filters
        filters = {}
        if date_from:
            filters['date_from'] = date_from
        if date_to:
            filters['date_to'] = date_to
        if status:
            filters['status'] = status
        
        try:
            # Export data
            print("\n📊 Exporting tickets...")
            exported_data = support.export_data('tickets', filters, export_format)
            
            # Save to file
            ext = 'csv' if export_format == 'csv' else 'json'
            filename = f"tickets_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
            
            with open(filename, 'w') as f:
                f.write(exported_data)
            
            print(f"✅ Tickets exported to {filename}")
            
        except Exception as e:
            print(f"❌ Error exporting tickets: {e}")

    def export_responses_menu(support):
        """Export responses with filters"""
        print("\n📤 EXPORT RESPONSES")
        print("="*40)
        
        # Date range
        date_from = input("From date (YYYY-MM-DD, optional): ").strip() or None
        date_to = input("To date (YYYY-MM-DD, optional): ").strip() or None
        
        # Format
        print("\nExport formats:")
        print("1. CSV")
        print("2. JSON")
        
        format_choice = input("Select format (1-2): ").strip()
        export_format = 'csv' if format_choice == '1' else 'json'
        
        # Build filters
        filters = {}
        if date_from:
            filters['date_from'] = date_from
        if date_to:
            filters['date_to'] = date_to
        
        try:
            # Export data
            print("\n📊 Exporting responses...")
            exported_data = support.export_data('responses', filters, export_format)
            
            # Save to file
            ext = 'csv' if export_format == 'csv' else 'json'
            filename = f"responses_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
            
            with open(filename, 'w') as f:
                f.write(exported_data)
            
            print(f"✅ Responses exported to {filename}")
            
        except Exception as e:
            print(f"❌ Error exporting responses: {e}")

    def export_metrics_menu(support):
        """Export metrics with filters"""
        print("\n📤 EXPORT METRICS")
        print("="*40)
        
        # Date range
        date_from = input("From date (YYYY-MM-DD, optional): ").strip() or None
        date_to = input("To date (YYYY-MM-DD, optional): ").strip() or None
        
        # Category filter
        category = input("Metric category (tickets, performance, satisfaction, optional): ").strip() or None
        
        # Format
        print("\nExport formats:")
        print("1. CSV")
        print("2. JSON")
        
        format_choice = input("Select format (1-2): ").strip()
        export_format = 'csv' if format_choice == '1' else 'json'
        
        # Build filters
        filters = {}
        if date_from:
            filters['date_from'] = date_from
        if date_to:
            filters['date_to'] = date_to
        if category:
            filters['category'] = category
        
        try:
            # Export data
            print("\n📊 Exporting metrics...")
            exported_data = support.export_data('metrics', filters, export_format)
            
            # Save to file
            ext = 'csv' if export_format == 'csv' else 'json'
            filename = f"metrics_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
            
            with open(filename, 'w') as f:
                f.write(exported_data)
            
            print(f"✅ Metrics exported to {filename}")
            
        except Exception as e:
            print(f"❌ Error exporting metrics: {e}")

    def export_filtered_tickets_menu(support):
        """Export tickets with advanced filters"""
        print("\n📤 EXPORT FILTERED TICKETS")
        print("="*50)
        
        # This would typically be called from the main ticket view
        # For now, provide a simplified version
        filters = {}
        
        # Interactive filter building
        print("Build export filters:")
        
        status = input(f"Status ({', '.join(TICKET_STATUSES)}, optional): ").strip()
        if status and status in TICKET_STATUSES:
            filters['status'] = status
        
        category = input(f"Category ({', '.join(SUPPORT_CATEGORIES)}, optional): ").strip()
        if category and category in SUPPORT_CATEGORIES:
            filters['category'] = category
        
        priority = input(f"Priority ({', '.join(TICKET_PRIORITIES)}, optional): ").strip()
        if priority and priority in TICKET_PRIORITIES:
            filters['priority'] = priority
        
        date_from = input("From date (YYYY-MM-DD, optional): ").strip()
        if date_from:
            filters['date_from'] = date_from
        
        date_to = input("To date (YYYY-MM-DD, optional): ").strip()
        if date_to:
            filters['date_to'] = date_to
        
        # Format selection
        print("\nExport formats:")
        print("1. CSV")
        print("2. JSON")
        
        format_choice = input("Select format (1-2): ").strip()
        export_format = 'csv' if format_choice == '1' else 'json'
        
        try:
            # Export data
            print("\n📊 Exporting filtered tickets...")
            exported_data = support.export_data('tickets', filters, export_format)
            
            # Save to file
            ext = 'csv' if export_format == 'csv' else 'json'
            filename = f"filtered_tickets_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
            
            with open(filename, 'w') as f:
                f.write(exported_data)
            
            print(f"✅ Filtered tickets exported to {filename}")
            
        except Exception as e:
            print(f"❌ Error exporting filtered tickets: {e}")

    @audit_action("create_template")
    def create_ticket_template(self, name, title_template, description_template, category, priority):
        """Create a new ticket template"""
        if not auth or not auth.current_user or auth.current_user['role'] not in ('staff', 'admin'):
            raise PermissionError("Only staff can create ticket templates")
        
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            created_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO ticket_templates (
                name, title_template, description_template, category, priority,
                created_by, created_datetime
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, title_template, description_template, category, priority, auth.current_user['username'], created_time))
            
            template_id = cursor.lastrowid
            
            conn.commit()
            conn.close()
            
            logger.info(f"Ticket template '{name}' created by {auth.current_user['username']}")
            return template_id
            
        except Exception as e:
            logger.error(f"Error creating ticket template: {e}")
            raise

    @audit_action("create_response_template")
    def create_response_template(self, name, subject, content, category=None, variables=None):
        """Create a new response template"""
        if not auth or not auth.current_user or auth.current_user['role'] not in ('staff', 'admin'):
            raise PermissionError("Only staff can create response templates")
        
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            created_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO response_templates (
                name, subject, content, category, created_by, created_datetime, variables
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, subject, content, category, auth.current_user['username'], created_time, json.dumps(variables or [])))
            
            template_id = cursor.lastrowid
            
            conn.commit()
            conn.close()
            
            logger.info(f"Response template '{name}' created by {auth.current_user['username']}")
            return template_id
            
        except Exception as e:
            logger.error(f"Error creating response template: {e}")
            raise

    # File management methods
    def get_ticket_attachments(self, ticket_id):
        """Get all attachments for a ticket"""
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM ticket_attachments WHERE ticket_id = ? ORDER BY uploaded_datetime DESC', (ticket_id,))
            attachments = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            return attachments
            
        except Exception as e:
            logger.error(f"Error getting ticket attachments: {e}")
            return []

    def download_attachment(self, attachment_id):
        """Download a ticket attachment"""
        if not auth or not auth.current_user:
            raise PermissionError("You must be logged in to download attachments")

        try:
            # Open DB connection
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()

            cursor.execute('SELECT file_path, original_filename FROM ticket_attachments WHERE attachment_id = ?', (attachment_id,))
            result = cursor.fetchone()
            conn.close()

            if not result:
                raise FileNotFoundError(f"Attachment with ID {attachment_id} not found")

            file_path, original_filename = result

            if not os.path.isfile(file_path):
                raise FileNotFoundError(f"File does not exist at path: {file_path}")

            with open(file_path, 'rb') as f:
                file_data = f.read()

            logger.info(f"Attachment {attachment_id} downloaded by {auth.current_user['username']}")
            return {
                'filename': original_filename,
                'data': file_data
            }

        except sqlite3.Error as e:
            logger.error(f"Database error during attachment download: {e}")
            raise Exception(f"Failed to retrieve attachment: {e}")

        except Exception as e:
            logger.error(f"Unexpected error during attachment download: {e}")
            raise

    def _create_original_tables(self, cursor):
        """Create the original tables with enhancements"""
        # Enhanced support tickets table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT NOT NULL,
            created_datetime TEXT NOT NULL,
            last_updated_datetime TEXT,
            assigned_to TEXT,
            escalated_at TEXT,
            resolved_at TEXT,
            closed_at TEXT,
            estimated_resolution TEXT,
            sentiment TEXT DEFAULT 'neutral',
            satisfaction_rating INTEGER,
            tags TEXT,  -- JSON array of tags
            parent_ticket_id INTEGER,  -- For merged tickets
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (parent_ticket_id) REFERENCES support_tickets (ticket_id)
        )
        ''')
        
        # Check if table exists but is missing columns, then add them
        cursor.execute("PRAGMA table_info(support_tickets)")
        existing_columns = [column[1] for column in cursor.fetchall()]
        
        required_columns = {
            'created_datetime': 'TEXT NOT NULL DEFAULT ""',
            'last_updated_datetime': 'TEXT',
            'escalated_at': 'TEXT',
            'resolved_at': 'TEXT',
            'closed_at': 'TEXT',
            'estimated_resolution': 'TEXT',
            'sentiment': 'TEXT DEFAULT "neutral"',
            'satisfaction_rating': 'INTEGER',
            'tags': 'TEXT',
            'parent_ticket_id': 'INTEGER',
            'subject': 'TEXT',
            'message': 'TEXT'
        }
        
        for column_name, column_def in required_columns.items():
            if column_name not in existing_columns:
                try:
                    cursor.execute(f'ALTER TABLE support_tickets ADD COLUMN {column_name} {column_def}')
                    print(f"✅ Added column '{column_name}' to support_tickets table")
                except Exception as e:
                    print(f"⚠️ Could not add column '{column_name}': {e}")
        
        # Enhanced ticket responses table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_responses (
            response_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            responder_id TEXT NOT NULL,
            responder_role TEXT NOT NULL,
            response_text TEXT NOT NULL,
            response_datetime TEXT NOT NULL,
            is_internal BOOLEAN DEFAULT 0,
            is_auto_generated BOOLEAN DEFAULT 0,
            template_used TEXT,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id)
        )
        ''')
        
        # Enhanced support resources table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_resources (
            resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            url TEXT,
            file_path TEXT,
            created_by TEXT NOT NULL,
            created_datetime TEXT NOT NULL,
            updated_datetime TEXT,
            access_count INTEGER DEFAULT 0,
            tags TEXT,  -- JSON array
            content_type TEXT,
            is_featured BOOLEAN DEFAULT 0,
            requires_auth BOOLEAN DEFAULT 0
        )
        ''')
        
        # Enhanced FAQ table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS faqs (
            faq_id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            category TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_datetime TEXT NOT NULL,
            updated_datetime TEXT,
            view_count INTEGER DEFAULT 0,
            helpful_votes INTEGER DEFAULT 0,
            tags TEXT,  -- JSON array
            is_featured BOOLEAN DEFAULT 0
        )
        ''')
    
    def _create_enhanced_tables(self, cursor):
        """Create new enhanced tables"""
        
        # File attachments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_attachments (
            attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            file_type TEXT NOT NULL,
            mime_type TEXT,
            uploaded_by TEXT NOT NULL,
            uploaded_datetime TEXT NOT NULL,
            is_public BOOLEAN DEFAULT 0,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id)
        )
        ''')
        
        # Notifications table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            notification_type TEXT NOT NULL,
            related_ticket_id INTEGER,
            is_read BOOLEAN DEFAULT 0,
            created_datetime TEXT NOT NULL,
            read_datetime TEXT,
            expires_at TEXT,
            data TEXT,  -- JSON data
            FOREIGN KEY (related_ticket_id) REFERENCES support_tickets (ticket_id)
        )
        ''')
        
        # Staff assignments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff_assignments (
            assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id TEXT NOT NULL,
            category TEXT NOT NULL,
            is_primary BOOLEAN DEFAULT 0,
            max_concurrent_tickets INTEGER DEFAULT 10,
            current_ticket_count INTEGER DEFAULT 0,
            expertise_level INTEGER DEFAULT 1,  -- 1-5 scale
            auto_assign_enabled BOOLEAN DEFAULT 1
        )
        ''')
        
        # Ticket templates table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            title_template TEXT NOT NULL,
            description_template TEXT NOT NULL,
            category TEXT NOT NULL,
            priority TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_datetime TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            usage_count INTEGER DEFAULT 0
        )
        ''')
        
        # Response templates table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS response_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            subject TEXT,
            content TEXT NOT NULL,
            category TEXT,
            created_by TEXT NOT NULL,
            created_datetime TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            usage_count INTEGER DEFAULT 0,
            variables TEXT  -- JSON array of variable names
        )
        ''')
        
        # User preferences table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id TEXT PRIMARY KEY,
            email_notifications BOOLEAN DEFAULT 1,
            in_app_notifications BOOLEAN DEFAULT 1,
            push_notifications BOOLEAN DEFAULT 1,
            digest_frequency TEXT DEFAULT 'daily',  -- immediate, daily, weekly
            theme TEXT DEFAULT 'light',
            language TEXT DEFAULT 'en',
            timezone TEXT DEFAULT 'UTC',
            preferences_json TEXT  -- Additional JSON preferences
        )
        ''')
        
        # System metrics table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_metrics (
            metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            category TEXT NOT NULL,
            recorded_datetime TEXT NOT NULL,
            metadata TEXT  -- JSON data
        )
        ''')
        
        # Search analytics table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_analytics (
            search_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            search_query TEXT NOT NULL,
            search_type TEXT NOT NULL,  -- faq, resource, ticket, global
            results_count INTEGER NOT NULL,
            clicked_result_id TEXT,
            search_datetime TEXT NOT NULL,
            session_id TEXT
        )
        ''')
        
        # Audit trail table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_trail (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id TEXT,
            old_values TEXT,  -- JSON
            new_values TEXT,  -- JSON
            ip_address TEXT,
            user_agent TEXT,
            success BOOLEAN NOT NULL,
            error_message TEXT,
            duration REAL,
            timestamp TEXT NOT NULL
        )
        ''')
        
        # Escalation rules table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS escalation_rules (
            rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            priority TEXT,
            condition_type TEXT NOT NULL,  -- time_based, status_based, keyword_based
            condition_value TEXT NOT NULL,
            action_type TEXT NOT NULL,  -- escalate, reassign, notify
            action_target TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            created_by TEXT NOT NULL,
            created_datetime TEXT NOT NULL
        )
        ''')
        
        # Knowledge base articles table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS kb_articles (
            article_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            summary TEXT,
            category TEXT NOT NULL,
            tags TEXT,  -- JSON array
            author_id TEXT NOT NULL,
            created_datetime TEXT NOT NULL,
            updated_datetime TEXT,
            published_datetime TEXT,
            is_published BOOLEAN DEFAULT 0,
            view_count INTEGER DEFAULT 0,
            helpful_votes INTEGER DEFAULT 0,
            not_helpful_votes INTEGER DEFAULT 0,
            search_keywords TEXT,  -- Space-separated keywords for search
            related_articles TEXT  -- JSON array of related article IDs
        )
        ''')
        
        # System integrations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_integrations (
            integration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,  -- sso, lms, sis, calendar, etc.
            config TEXT NOT NULL,  -- JSON configuration
            is_active BOOLEAN DEFAULT 0,
            last_sync_datetime TEXT,
            sync_status TEXT DEFAULT 'never',
            error_log TEXT
        )
        ''')

    def _initialize_default_data(self, cursor):
        """Initialize default data for enhanced tables"""
        
        # Add default escalation rules
        cursor.execute('SELECT COUNT(*) FROM escalation_rules')
        if cursor.fetchone()[0] == 0:
            # FIXED: Changed to use 9 parameters instead of 10
            # Removed 'category' and 'priority' from the tuples since they're None
            default_rules = [
                ('High Priority Escalation', 'High', 'time_based', '2', 'notify', 'supervisor', 1, 'system', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                ('Critical Priority Immediate Escalation', 'Critical', 'time_based', '0.5', 'escalate', 'supervisor', 1, 'system', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                ('Long Open Ticket', None, 'time_based', '72', 'notify', 'supervisor', 1, 'system', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            ]
            
            # FIXED: Updated SQL to match the actual data being provided
            cursor.executemany(
                '''INSERT INTO escalation_rules 
                   (name, priority, condition_type, condition_value, action_type, action_target, is_active, created_by, created_datetime) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                default_rules
            )
        
        # Add default response templates
        cursor.execute('SELECT COUNT(*) FROM response_templates')
        if cursor.fetchone()[0] == 0:
            default_templates = [
                ('Acknowledgment', 'Ticket Received', 'Thank you for contacting support. We have received your request and will respond within [RESPONSE_TIME]. Your ticket number is [TICKET_ID].', 'General', 'system', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 1, 0, '["RESPONSE_TIME", "TICKET_ID"]'),
                ('Password Reset', 'Password Reset Instructions', 'To reset your password, please visit [RESET_URL] and follow the instructions. If you continue to have issues, please reply to this ticket.', 'Technical', 'system', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 1, 0, '["RESET_URL"]'),
                ('Resolution', 'Issue Resolved', 'Your issue has been resolved. If you continue to experience problems, please reply to this ticket or create a new one.', 'General', 'system', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 1, 0, '[]'),
            ]
            cursor.executemany(
                'INSERT INTO response_templates (name, subject, content, category, created_by, created_datetime, is_active, usage_count, variables) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                default_templates
            )
        
        # Add default ticket templates
        cursor.execute('SELECT COUNT(*) FROM ticket_templates')
        if cursor.fetchone()[0] == 0:
            default_ticket_templates = [
                ('Password Reset Request', 'Password Reset Request', 'I need help resetting my password for: [SYSTEM_NAME]\nMy username is: [USERNAME]\nIssue details: [DETAILS]', 'Technical', 'Medium', 'system', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 1, 0),
                ('Grade Inquiry', 'Grade Inquiry for [COURSE_CODE]', 'I have a question about my grade in [COURSE_CODE].\nAssignment/Exam: [ASSIGNMENT_NAME]\nConcern: [CONCERN_DETAILS]', 'Academic', 'Medium', 'system', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 1, 0),
                ('Housing Issue', 'Housing Issue - [ISSUE_TYPE]', 'Location: [BUILDING_NAME], Room [ROOM_NUMBER]\nIssue Type: [ISSUE_TYPE]\nDescription: [ISSUE_DESCRIPTION]\nUrgency: [URGENCY_LEVEL]', 'Housing', 'Medium', 'system', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 1, 0),
            ]
            cursor.executemany(
                'INSERT INTO ticket_templates (name, title_template, description_template, category, priority, created_by, created_datetime, is_active, usage_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                default_ticket_templates
            )
        
    def _load_staff_assignments(self):
        """Load staff assignment mappings from database"""
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            # Check if table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='staff_assignments'")
            if not cursor.fetchone():
                logger.info("Staff assignments table doesn't exist yet, using empty assignments")
                self.staff_assignments = {}
                conn.close()
                return
            
            cursor.execute('SELECT staff_id, category, is_primary FROM staff_assignments WHERE auto_assign_enabled = 1')
            
            self.staff_assignments = {}
            for staff_id, category, is_primary in cursor.fetchall():
                if category not in self.staff_assignments:
                    self.staff_assignments[category] = []
                self.staff_assignments[category].append({
                    'staff_id': staff_id,
                    'is_primary': bool(is_primary)
                })
            
            conn.close()
            logger.info(f"Loaded staff assignments for {len(self.staff_assignments)} categories")
            
        except Exception as e:
            logger.error(f"Error loading staff assignments: {e}")
            self.staff_assignments = {}
        
    def _start_background_tasks(self):
        """Start background tasks for escalation and notifications"""
        def background_worker():
            while True:
                try:
                    self._process_escalations()
                    self._process_notification_queue()
                    self._update_metrics()
                    time.sleep(300)  # Run every 5 minutes
                except Exception as e:
                    logger.error(f"Background task error: {e}")
                    time.sleep(60)  # Wait 1 minute before retrying
        
        # Only start background tasks if auth is available
        if auth and auth.current_user:
            background_thread = threading.Thread(target=background_worker, daemon=True)
            background_thread.start()
            logger.info("Background tasks started")
        else:
            logger.info("Background tasks not started - no authentication available")
            
    def _log_audit(self, audit_data: Dict[str, Any]):
        """Log audit trail information"""
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT INTO audit_trail (
                user_id, action, resource_type, resource_id, old_values, 
                new_values, success, error_message, duration, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                audit_data.get('user', 'system'),
                audit_data.get('action'),
                audit_data.get('function', 'unknown'),
                audit_data.get('resource_id'),
                json.dumps(audit_data.get('old_values', {})),
                json.dumps(audit_data.get('new_values', {})),
                audit_data.get('success', True),
                audit_data.get('error'),
                audit_data.get('duration', 0),
                audit_data.get('timestamp')
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to log audit trail: {e}")

    @audit_action("create_ticket")
    def create_support_ticket(self, student_id, title, description, category, priority='Medium', 
                            template_id=None, attachments=None, tags=None):
        """Create a new support ticket with enhanced features."""
        if not auth or not auth.current_user:
            raise PermissionError("You must be logged in to create a support ticket")
        
        try:
            # Validate inputs
            self._validate_ticket_inputs(title, description, category, priority)
            
            # Permission check
            self._check_ticket_creation_permission(student_id)
            
            # Sentiment analysis
            sentiment = self._analyze_sentiment(description)
            
            # Auto-suggest category if not provided correctly
            if category not in SUPPORT_CATEGORIES:
                suggested_category = self._suggest_category(title + " " + description)
                if suggested_category:
                    category = suggested_category
                else:
                    raise ValueError(f"Invalid category. Choose from: {', '.join(SUPPORT_CATEGORIES)}")
            
            # Create the ticket
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            created_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Auto-assign staff if enabled
            assigned_to = None
            if self.config.auto_assign_enabled:
                assigned_to = self._get_auto_assignment(category, priority)
            
            # Estimate resolution time
            estimated_resolution = self._estimate_resolution_time(category, priority)
            
            cursor.execute('''
            INSERT INTO support_tickets (
                student_id, title, description, category, priority, status, 
                created_datetime, assigned_to, sentiment, estimated_resolution, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                student_id, title, description, category, priority, 'Open', 
                created_time, assigned_to, sentiment, estimated_resolution, 
                json.dumps(tags or [])
            ))
            
            ticket_id = cursor.lastrowid
            
            # Handle attachments
            if attachments:
                self._process_attachments(ticket_id, attachments, cursor)
            
            # Create auto-acknowledgment response
            self._create_auto_response(ticket_id, 'acknowledgment', cursor)
            
            # Create notifications
            self._create_ticket_notifications(ticket_id, student_id, assigned_to, 'created')
            
            conn.commit()
            conn.close()
            
            logger.info(f"Support ticket #{ticket_id} created for student {student_id} with sentiment {sentiment}")
            return ticket_id
            
        except Exception as e:
            logger.error(f"Error creating support ticket: {e}")
            raise

    def _validate_ticket_inputs(self, title, description, category, priority):
        """Validate ticket creation inputs"""
        if not title or not description or not category:
            raise ValueError("Title, description and category are required")
        
        if len(title) > 200:
            raise ValueError("Title must be 200 characters or less")
        
        if len(description) > 5000:
            raise ValueError("Description must be 5000 characters or less")
        
        if priority not in TICKET_PRIORITIES:
            raise ValueError(f"Invalid priority. Choose from: {', '.join(TICKET_PRIORITIES)}")

    def _check_ticket_creation_permission(self, student_id):
        """Check if user has permission to create ticket for student_id"""
        if auth.current_user['role'] == 'student':
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
            result = cursor.fetchone()
            conn.close()
            
            if not result or result[0] != student_id:
                raise PermissionError("You can only create support tickets for your own account")

    def _analyze_sentiment(self, text):
        """Simple sentiment analysis based on keywords"""
        frustrated_keywords = [
            'frustrated', 'angry', 'terrible', 'awful', 'horrible', 'hate',
            'worst', 'furious', 'disgusted', 'outraged', 'urgent', 'immediately',
            'ridiculous', 'unacceptable', 'disappointed'
        ]
        
        positive_keywords = [
            'thank', 'appreciate', 'great', 'excellent', 'wonderful', 'amazing',
            'perfect', 'love', 'fantastic', 'awesome', 'pleased'
        ]
        
        text_lower = text.lower()
        
        frustrated_count = sum(1 for keyword in frustrated_keywords if keyword in text_lower)
        positive_count = sum(1 for keyword in positive_keywords if keyword in text_lower)
        
        if frustrated_count > 2:
            return TicketSentiment.FRUSTRATED.value
        elif frustrated_count > 0:
            return TicketSentiment.NEGATIVE.value
        elif positive_count > 0:
            return TicketSentiment.POSITIVE.value
        else:
            return TicketSentiment.NEUTRAL.value

    def _suggest_category(self, text):
        """AI-powered category suggestion based on text content"""
        category_keywords = {
            'Technical': ['password', 'login', 'computer', 'wifi', 'internet', 'email', 'software', 'system', 'app', 'website'],
            'Academic': ['grade', 'course', 'assignment', 'professor', 'class', 'exam', 'transcript', 'graduation', 'credit'],
            'Financial Aid': ['scholarship', 'loan', 'tuition', 'payment', 'financial', 'aid', 'grant', 'billing'],
            'Housing': ['dorm', 'room', 'roommate', 'housing', 'residence', 'maintenance', 'key', 'AC', 'heating'],
            'Library Services': ['library', 'book', 'research', 'database', 'citation', 'librarian'],
            'Mental Health': ['counseling', 'stress', 'anxiety', 'depression', 'wellness', 'therapy'],
            'Registration': ['register', 'enrollment', 'schedule', 'waitlist', 'drop', 'add', 'prerequisite'],
            'Dining': ['meal', 'food', 'dining', 'cafeteria', 'allergy', 'dietary'],
            'Parking': ['parking', 'permit', 'ticket', 'car', 'vehicle', 'tow'],
            'Career Services': ['job', 'career', 'internship', 'resume', 'interview', 'employment']
        }
        
        text_lower = text.lower()
        category_scores = {}
        
        for category, keywords in category_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                category_scores[category] = score
        
        if category_scores:
            return max(category_scores, key=category_scores.get)
        
        return None

    def _get_auto_assignment(self, category, priority):
        """Get staff member for auto-assignment"""
        if category not in self.staff_assignments:
            return None
        
        # Simple round-robin assignment (in a real system, you'd consider workload)
        staff_list = self.staff_assignments[category]
        if not staff_list:
            return None
        
        # Prefer primary staff for high priority tickets
        if priority in ['High', 'Critical', 'Urgent']:
            primary_staff = [s for s in staff_list if s['is_primary']]
            if primary_staff:
                return primary_staff[0]['staff_id']
        
        return staff_list[0]['staff_id']

    def _estimate_resolution_time(self, category, priority):
        """Estimate resolution time based on category and priority"""
        base_times = {
            'Technical': 4,  # hours
            'Academic': 24,
            'Financial Aid': 48,
            'Housing': 12,
            'Library Services': 2,
            'Mental Health': 1,
            'Registration': 8,
            'Other': 24
        }
        
        priority_multipliers = {
            'Critical': 0.25,
            'Urgent': 0.5,
            'High': 0.75,
            'Medium': 1.0,
            'Low': 2.0
        }
        
        base_hours = base_times.get(category, 24)
        multiplier = priority_multipliers.get(priority, 1.0)
        estimated_hours = base_hours * multiplier
        
        resolution_time = datetime.datetime.now() + datetime.timedelta(hours=estimated_hours)
        return resolution_time.strftime('%Y-%m-%d %H:%M:%S')

    def _process_attachments(self, ticket_id, attachments, cursor):
        """Process and store ticket attachments"""
        for attachment in attachments:
            if not self._validate_file(attachment):
                continue
                
            # Generate secure filename
            secure_filename = self._generate_secure_filename(attachment['filename'])
            file_path = os.path.join('uploads', 'tickets', str(ticket_id), secure_filename)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Save file
            with open(file_path, 'wb') as f:
                f.write(attachment['data'])
            
            # Store in database
            cursor.execute('''
            INSERT INTO ticket_attachments (
                ticket_id, filename, original_filename, file_path, file_size,
                file_type, mime_type, uploaded_by, uploaded_datetime
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ticket_id, secure_filename, attachment['filename'], file_path,
                len(attachment['data']), self._get_file_type(attachment['filename']),
                attachment.get('mime_type'), auth.current_user['id'],
                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))

    def _validate_file(self, attachment):
        """Validate uploaded file"""
        if len(attachment['data']) > self.config.max_file_size:
            logger.warning(f"File too large: {len(attachment['data'])} bytes")
            return False
            
        ext = os.path.splitext(attachment['filename'])[1].lower()
        if ext not in self.config.allowed_file_types:
            logger.warning(f"File type not allowed: {ext}")
            return False
            
        return True

    def _generate_secure_filename(self, filename):
        """Generate a secure filename"""
        name, ext = os.path.splitext(filename)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        random_suffix = secrets.token_hex(4)
        return f"{timestamp}_{random_suffix}{ext}"

    def _get_file_type(self, filename):
        """Determine file type from filename"""
        ext = os.path.splitext(filename)[1].lower()
        
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
            return FileType.IMAGE.value
        elif ext in ['.pdf', '.doc', '.docx', '.txt', '.rtf']:
            return FileType.DOCUMENT.value
        elif ext in ['.mp4', '.avi', '.mov', '.wmv']:
            return FileType.VIDEO.value
        else:
            return FileType.OTHER.value

    def _create_auto_response(self, ticket_id, template_name, cursor):
        """Create an automatic response using a template"""
        try:
            # Get template
            cursor.execute('SELECT content, variables FROM response_templates WHERE name = ? AND is_active = 1', (template_name,))
            template_data = cursor.fetchone()
            
            if not template_data:
                return
                
            content, variables_json = template_data
            variables = json.loads(variables_json or '[]')
            
            # Replace variables
            replacements = {
                'TICKET_ID': str(ticket_id),
                'RESPONSE_TIME': '24 hours',
                'USER_NAME': auth.current_user.get('username', 'Student')
            }
            
            for var in variables:
                if var in replacements:
                    content = content.replace(f'[{var}]', replacements[var])
            
            # Create response
            cursor.execute('''
            INSERT INTO ticket_responses (
                ticket_id, responder_id, responder_role, response_text,
                response_datetime, is_auto_generated, template_used
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                ticket_id, 'system', 'system', content,
                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                1, template_name
            ))
            
        except Exception as e:
            logger.error(f"Error creating auto response: {e}")

    def _create_ticket_notifications(self, ticket_id, student_id, assigned_to, action):
        """Create notifications for ticket events"""
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            notifications = []
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Notify student
            if action == 'created':
                notifications.append((
                    student_id, 'Ticket Created', 
                    f'Your support ticket #{ticket_id} has been created successfully.',
                    NotificationType.EMAIL.value, ticket_id, timestamp
                ))
            
            # Notify assigned staff
            if assigned_to:
                notifications.append((
                    assigned_to, 'New Ticket Assignment',
                    f'You have been assigned to ticket #{ticket_id}.',
                    NotificationType.IN_APP.value, ticket_id, timestamp
                ))
            
            for notification in notifications:
                cursor.execute('''
                INSERT INTO notifications (
                    user_id, title, message, notification_type, 
                    related_ticket_id, created_datetime
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''', notification)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error creating notifications: {e}")

    @audit_action("view_tickets")
    def get_student_tickets(self, student_id=None, filters=None, page=1, per_page=20):
        """Get support tickets with enhanced filtering and pagination."""
        if not auth or not auth.current_user:
            raise PermissionError("You must be logged in to view support tickets")
        
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Build query based on user role and filters
            query, params = self._build_ticket_query(student_id, filters, auth.current_user)
            
            # Add pagination
            offset = (page - 1) * per_page
            query += f" LIMIT {per_page} OFFSET {offset}"
            
            cursor.execute(query, params)
            tickets = [dict(row) for row in cursor.fetchall()]
            
            # Get total count for pagination
            count_query = query.replace('SELECT *', 'SELECT COUNT(*)').split('ORDER BY')[0]
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()[0]
            
            # Enhance ticket data
            for ticket in tickets:
                ticket['tags'] = json.loads(ticket.get('tags', '[]'))
                ticket['attachment_count'] = self._get_attachment_count(ticket['ticket_id'], cursor)
                ticket['last_response_by'] = self._get_last_response_info(ticket['ticket_id'], cursor)
            
            conn.close()
            
            result = {
                'tickets': tickets,
                'total_count': total_count,
                'page': page,
                'per_page': per_page,
                'total_pages': (total_count + per_page - 1) // per_page
            }
            
            logger.info(f"Retrieved {len(tickets)} tickets (page {page}) for user {auth.current_user['username']}")
            return result
            
        except Exception as e:
            logger.error(f"Error retrieving tickets: {e}")
            raise

    def _build_ticket_query(self, student_id, filters, current_user):
        """Build SQL query for ticket retrieval with filters"""
        base_query = "SELECT * FROM support_tickets WHERE 1=1"
        params = []
        
        # Role-based filtering
        if current_user['role'] == 'student':
            if not student_id:
                # Get student's own ID
                conn_main = get_connection()
                cursor_main = conn_main.cursor()
                cursor_main.execute('SELECT student_id FROM users WHERE id = ?', (current_user['id'],))
                result = cursor_main.fetchone()
                conn_main.close()
                
                if result:
                    student_id = result[0]
                else:
                    raise ValueError("No student ID associated with your account")
            
            base_query += " AND student_id = ?"
            params.append(student_id)
        elif student_id:
            base_query += " AND student_id = ?"
            params.append(student_id)
        
        # Apply filters
        if filters:
            if filters.get('status'):
                base_query += " AND status = ?"
                params.append(filters['status'])
            
            if filters.get('category'):
                base_query += " AND category = ?"
                params.append(filters['category'])
            
            if filters.get('priority'):
                base_query += " AND priority = ?"
                params.append(filters['priority'])
            
            if filters.get('assigned_to'):
                base_query += " AND assigned_to = ?"
                params.append(filters['assigned_to'])
            
            if filters.get('date_from'):
                base_query += " AND created_datetime >= ?"
                params.append(filters['date_from'])
            
            if filters.get('date_to'):
                base_query += " AND created_datetime <= ?"
                params.append(filters['date_to'])
            
            if filters.get('search'):
                base_query += " AND (title LIKE ? OR description LIKE ?)"
                search_term = f"%{filters['search']}%"
                params.extend([search_term, search_term])
        
        base_query += " ORDER BY created_datetime DESC"
        return base_query, params

    def _get_attachment_count(self, ticket_id, cursor):
        """Get number of attachments for a ticket"""
        cursor.execute('SELECT COUNT(*) FROM ticket_attachments WHERE ticket_id = ?', (ticket_id,))
        return cursor.fetchone()[0]

    def _get_last_response_info(self, ticket_id, cursor):
        """Get information about the last response to a ticket"""
        cursor.execute('''
        SELECT responder_role, response_datetime FROM ticket_responses 
        WHERE ticket_id = ? ORDER BY response_datetime DESC LIMIT 1
        ''', (ticket_id,))
        
        result = cursor.fetchone()
        if result:
            return {'role': result[0], 'datetime': result[1]}
        return None

    @audit_action("add_response")
    def add_ticket_response(self, ticket_id, response_text, template_id=None, is_internal=False, attachments=None):
        """Add a response to a support ticket with enhanced features."""
        if not auth or not auth.current_user:
            raise PermissionError("You must be logged in to respond to a ticket")
        
        try:
            if not response_text:
                raise ValueError("Response text is required")
            
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            # Check if ticket exists and get details
            cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
            ticket = cursor.fetchone()
            
            if not ticket:
                raise ValueError(f"Ticket #{ticket_id} not found")
            
            # Check permissions
            self._check_response_permission(ticket, auth.current_user)
            
            # Process template if provided
            if template_id:
                response_text = self._apply_response_template(template_id, ticket_id, response_text, cursor)
            
            # Add the response
            response_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO ticket_responses (
                ticket_id, responder_id, responder_role, response_text, 
                response_datetime, is_internal, template_used
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                ticket_id, auth.current_user['id'], auth.current_user['role'], 
                response_text, response_time, is_internal, template_id
            ))
            
            # Handle attachments
            if attachments:
                self._process_attachments(ticket_id, attachments, cursor)
            
            # Update ticket
            self._update_ticket_on_response(ticket_id, ticket, response_time, cursor)
            
            # Create notifications
            if not is_internal:
                self._create_response_notifications(ticket_id, ticket[1], auth.current_user)  # ticket[1] is student_id
            
            # Update template usage count
            if template_id:
                cursor.execute('UPDATE response_templates SET usage_count = usage_count + 1 WHERE template_id = ?', (template_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Added response to ticket #{ticket_id} by {auth.current_user['username']}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding ticket response: {e}")
            raise

    def _check_response_permission(self, ticket, current_user):
        """Check if user can respond to ticket"""
        if current_user['role'] == 'student':
            # Verify it's their own ticket
            conn_main = get_connection()
            cursor_main = conn_main.cursor()
            cursor_main.execute('SELECT student_id FROM users WHERE id = ?', (current_user['id'],))
            result = cursor_main.fetchone()
            conn_main.close()
            
            if not result or result[0] != ticket[1]:  # ticket[1] is student_id
                raise PermissionError("You can only respond to your own support tickets")

    def _apply_response_template(self, template_id, ticket_id, response_text, cursor):
        """Apply response template with variable substitution"""
        cursor.execute('SELECT content, variables FROM response_templates WHERE template_id = ? AND is_active = 1', (template_id,))
        template_data = cursor.fetchone()
        
        if not template_data:
            return response_text
        
        template_content, variables_json = template_data
        variables = json.loads(variables_json or '[]')
        
        # Replace variables
        replacements = {
            'TICKET_ID': str(ticket_id),
            'USER_NAME': auth.current_user.get('username', 'User'),
            'CURRENT_DATE': datetime.datetime.now().strftime('%Y-%m-%d'),
            'CURRENT_TIME': datetime.datetime.now().strftime('%H:%M:%S')
        }
        
        for var in variables:
            if var in replacements:
                template_content = template_content.replace(f'[{var}]', replacements[var])
        
        # Combine template with additional text
        if response_text and response_text != template_content:
            return f"{template_content}\n\n{response_text}"
        
        return template_content

    def _update_ticket_on_response(self, ticket_id, ticket, response_time, cursor):
        """Update ticket status and metadata when response is added"""
        new_status = ticket[6]  # Current status
        assigned_to = ticket[9]  # Current assigned_to
        
        # Auto-update status based on responder role
        if ticket[6] == 'Open' and auth.current_user['role'] in ('staff', 'admin'):
            new_status = 'In Progress'
            if not assigned_to:
                assigned_to = auth.current_user['username']
        
        cursor.execute('''
        UPDATE support_tickets 
        SET last_updated_datetime = ?, status = ?, assigned_to = ?
        WHERE ticket_id = ?
        ''', (response_time, new_status, assigned_to, ticket_id))

    def _create_response_notifications(self, ticket_id, student_id, responder):
        """Create notifications for ticket responses"""
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if responder['role'] in ('staff', 'admin'):
                # Notify student of staff response
                cursor.execute('''
                INSERT INTO notifications (
                    user_id, title, message, notification_type, 
                    related_ticket_id, created_datetime
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    student_id, 'Support Response Received',
                    f'Your support ticket #{ticket_id} has received a new response.',
                    NotificationType.EMAIL.value, ticket_id, timestamp
                ))
            else:
                # Notify assigned staff of student response
                # Get assigned staff
                cursor.execute('SELECT assigned_to FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
                result = cursor.fetchone()
                if result and result[0]:
                    cursor.execute('''
                    INSERT INTO notifications (
                        user_id, title, message, notification_type, 
                        related_ticket_id, created_datetime
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        result[0], 'Student Response Received',
                        f'Ticket #{ticket_id} has received a new response from the student.',
                        NotificationType.IN_APP.value, ticket_id, timestamp
                    ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error creating response notifications: {e}")

    @audit_action("update_status")
    def update_ticket_status(self, ticket_id, new_status, resolution_notes=None):
        """Update the status of a support ticket with enhanced tracking."""
        if not auth or not auth.current_user:
            raise PermissionError("You must be logged in to update a ticket status")
        
        if auth.current_user['role'] not in ('staff', 'admin'):
            raise PermissionError("Only staff members can update ticket status")
        
        try:
            if new_status not in TICKET_STATUSES:
                raise ValueError(f"Invalid status. Choose from: {', '.join(TICKET_STATUSES)}")
            
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            # Get current ticket
            cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
            ticket = cursor.fetchone()
            
            if not ticket:
                raise ValueError(f"Ticket #{ticket_id} not found")
            
            old_status = ticket[6]
            update_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Build update query based on status
            update_fields = {
                'status': new_status,
                'last_updated_datetime': update_time,
                'assigned_to': auth.current_user['username']
            }
            
            if new_status == 'Resolved':
                update_fields['resolved_at'] = update_time
            elif new_status == 'Closed':
                update_fields['closed_at'] = update_time
            
            # Build SQL
            set_clause = ', '.join([f"{k} = ?" for k in update_fields.keys()])
            values = list(update_fields.values()) + [ticket_id]
            
            cursor.execute(f'UPDATE support_tickets SET {set_clause} WHERE ticket_id = ?', values)
            
            # Add system response about status change
            response_text = f"Ticket status updated from '{old_status}' to '{new_status}'"
            if resolution_notes:
                response_text += f"\n\nResolution Notes: {resolution_notes}"
            
            cursor.execute('''
            INSERT INTO ticket_responses (
                ticket_id, responder_id, responder_role, response_text, 
                response_datetime, is_auto_generated
            ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                ticket_id, auth.current_user['id'], auth.current_user['role'], 
                response_text, update_time, 1
            ))
            
            # Create notifications
            self._create_status_update_notifications(ticket_id, ticket[1], old_status, new_status)
            
            # Record metrics
            self._record_status_change_metrics(ticket_id, old_status, new_status, update_time)
            
            # Trigger satisfaction survey for resolved tickets
            if new_status == 'Resolved' and self.config.satisfaction_survey_enabled:
                self._trigger_satisfaction_survey(ticket_id, ticket[1])
            
            conn.commit()
            conn.close()
            
            logger.info(f"Updated status of ticket #{ticket_id} from '{old_status}' to '{new_status}' by {auth.current_user['username']}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating ticket status: {e}")
            raise

    def _create_status_update_notifications(self, ticket_id, student_id, old_status, new_status):
        """Create notifications for status updates"""
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Notify student
            cursor.execute('''
            INSERT INTO notifications (
                user_id, title, message, notification_type, 
                related_ticket_id, created_datetime
            ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                student_id, 'Ticket Status Updated',
                f'Your support ticket #{ticket_id} status has been updated to {new_status}.',
                NotificationType.EMAIL.value, ticket_id, timestamp
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error creating status update notifications: {e}")

    def _record_status_change_metrics(self, ticket_id, old_status, new_status, timestamp):
        """Record metrics for status changes"""
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            # Record the status change
            cursor.execute('''
            INSERT INTO system_metrics (
                metric_name, metric_value, category, recorded_datetime, metadata
            ) VALUES (?, ?, ?, ?, ?)
            ''', (
                'status_change', 1, 'tickets', timestamp,
                json.dumps({
                    'ticket_id': ticket_id,
                    'old_status': old_status,
                    'new_status': new_status,
                    'changed_by': auth.current_user['username']
                })
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error recording status change metrics: {e}")

    def _trigger_satisfaction_survey(self, ticket_id, student_id):
        """Trigger satisfaction survey for resolved ticket"""
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            # Create survey notification
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            expires_at = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO notifications (
                user_id, title, message, notification_type, 
                related_ticket_id, created_datetime, expires_at, data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                student_id, 'Rate Your Support Experience',
                f'Please rate your support experience for ticket #{ticket_id}.',
                NotificationType.IN_APP.value, ticket_id, timestamp, expires_at,
                json.dumps({'survey_type': 'satisfaction', 'ticket_id': ticket_id})
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error triggering satisfaction survey: {e}")

    def advanced_search(self, query, search_type='global', filters=None, page=1, per_page=20):
        """Advanced search across tickets, FAQs, and resources with analytics"""
        if not auth or not auth.current_user:
            raise PermissionError("You must be logged in to search")
        
        try:
            # Log search analytics
            self._log_search_analytics(query, search_type, auth.current_user['id'])
            
            results = {}
            
            if search_type in ['global', 'tickets']:
                results['tickets'] = self._search_tickets(query, filters, page, per_page)
            
            if search_type in ['global', 'faqs']:
                results['faqs'] = self._search_faqs(query, filters)
            
            if search_type in ['global', 'resources']:
                results['resources'] = self._search_resources(query, filters)
            
            if search_type in ['global', 'kb']:
                results['kb_articles'] = self._search_knowledge_base(query, filters)
            
            # Suggest related content
            if self.config.ai_suggestions_enabled:
                results['suggestions'] = self._get_search_suggestions(query, results)
            
            logger.info(f"Advanced search performed by {auth.current_user['username']}: '{query}' ({search_type})")
            return results
            
        except Exception as e:
            logger.error(f"Error performing advanced search: {e}")
            raise

    def _log_search_analytics(self, query, search_type, user_id):
        """Log search analytics for improvement"""
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            session_id = getattr(auth.current_user, 'session_id', 'unknown')
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

    def _search_tickets(self, query, filters, page, per_page):
        """Search tickets with full-text search"""
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Permission check
            base_query = "SELECT * FROM support_tickets WHERE "
            params = []
            
            if auth.current_user['role'] == 'student':
                # Get student's own tickets only
                conn_main = get_connection()
                cursor_main = conn_main.cursor()
                cursor_main.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
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

    def _search_faqs(self, query, filters):
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

    def _search_resources(self, query, filters):
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
    def get_user_preferences(self, user_id=None):
        """Get user notification and display preferences"""
        if not user_id:
            user_id = auth.current_user['id'] if auth and auth.current_user else None
        
        if not user_id:
            raise ValueError("User ID required")
        
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM user_preferences WHERE user_id = ?', (user_id,))
            prefs = cursor.fetchone()
            
            if not prefs:
                # Create default preferences
                default_prefs = {
                    'email_notifications': True,
                    'in_app_notifications': True,
                    'push_notifications': True,
                    'digest_frequency': 'daily',
                    'theme': 'light',
                    'language': 'en',
                    'timezone': 'UTC'
                }
                
                cursor.execute('''
                INSERT INTO user_preferences (
                    user_id, email_notifications, in_app_notifications, 
                    push_notifications, digest_frequency, theme, language, timezone
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, True, True, True, 'daily', 'light', 'en', 'UTC'))
                
                conn.commit()
                conn.close()
                return default_prefs
            
            conn.close()
            
            # Convert to dict and parse JSON preferences
            prefs_dict = dict(prefs)
            if prefs_dict.get('preferences_json'):
                additional_prefs = json.loads(prefs_dict['preferences_json'])
                prefs_dict.update(additional_prefs)
            
            return prefs_dict
            
        except Exception as e:
            logger.error(f"Error getting user preferences: {e}")
            return {}

    @audit_action("update_preferences")
    def update_user_preferences(self, preferences, user_id=None):
        """Update user preferences"""
        if not user_id:
            user_id = auth.current_user['id'] if auth and auth.current_user else None
        
        if not user_id:
            raise ValueError("User ID required")
        
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            # Extract known preferences
            known_prefs = {
                'email_notifications': preferences.get('email_notifications', True),
                'in_app_notifications': preferences.get('in_app_notifications', True),
                'push_notifications': preferences.get('push_notifications', True),
                'digest_frequency': preferences.get('digest_frequency', 'daily'),
                'theme': preferences.get('theme', 'light'),
                'language': preferences.get('language', 'en'),
                'timezone': preferences.get('timezone', 'UTC')
            }
            
            # Store additional preferences as JSON
            additional_prefs = {k: v for k, v in preferences.items() if k not in known_prefs}
            
            # Update or insert preferences
            cursor.execute('SELECT user_id FROM user_preferences WHERE user_id = ?', (user_id,))
            exists = cursor.fetchone()
            
            if exists:
                cursor.execute('''
                UPDATE user_preferences SET
                    email_notifications = ?, in_app_notifications = ?, push_notifications = ?,
                    digest_frequency = ?, theme = ?, language = ?, timezone = ?, preferences_json = ?
                WHERE user_id = ?
                ''', (
                    known_prefs['email_notifications'], known_prefs['in_app_notifications'],
                    known_prefs['push_notifications'], known_prefs['digest_frequency'],
                    known_prefs['theme'], known_prefs['language'], known_prefs['timezone'],
                    json.dumps(additional_prefs), user_id
                ))
            else:
                cursor.execute('''
                INSERT INTO user_preferences (
                    user_id, email_notifications, in_app_notifications, push_notifications,
                    digest_frequency, theme, language, timezone, preferences_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id, known_prefs['email_notifications'], known_prefs['in_app_notifications'],
                    known_prefs['push_notifications'], known_prefs['digest_frequency'],
                    known_prefs['theme'], known_prefs['language'], known_prefs['timezone'],
                    json.dumps(additional_prefs)
                ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"User preferences updated for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating user preferences: {e}")
            raise

    # Knowledge base methods
    @audit_action("create_kb_article")
    def create_kb_article(self, title, content, category, summary=None, tags=None, is_published=False):
        """Create a new knowledge base article"""
        if not auth or not auth.current_user or auth.current_user['role'] not in ('staff', 'admin'):
            raise PermissionError("Only staff can create knowledge base articles")
        
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            created_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            published_time = created_time if is_published else None
            
            # Generate search keywords from title and content
            search_keywords = self._generate_search_keywords(title + " " + content)
            
            cursor.execute('''
            INSERT INTO kb_articles (
                title, content, summary, category, tags, author_id, created_datetime,
                published_datetime, is_published, search_keywords
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                title, content, summary, category, json.dumps(tags or []),
                auth.current_user['id'], created_time, published_time, is_published, search_keywords
            ))
            
            article_id = cursor.lastrowid
            
            conn.commit()
            conn.close()
            
            logger.info(f"Knowledge base article '{title}' created by {auth.current_user['username']}")
            return article_id
            
        except Exception as e:
            logger.error(f"Error creating knowledge base article: {e}")
            raise

    def _generate_search_keywords(self, text):
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

    def get_kb_articles(self, category=None, published_only=True):
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
                article['tags'] = json.loads(article.get('tags', '[]'))
                if article.get('related_articles'):
                    article['related_articles'] = json.loads(article['related_articles'])
            
            conn.close()
            return articles
            
        except Exception as e:
            logger.error(f"Error getting knowledge base articles: {e}")
            return []

    @audit_action("publish_kb_article")
    def publish_kb_article(self, article_id):
        """Publish a knowledge base article"""
        if not auth or not auth.current_user or auth.current_user['role'] not in ('staff', 'admin'):
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
            
            logger.info(f"Knowledge base article {article_id} published by {auth.current_user['username']}")
            return True
            
        except Exception as e:
            logger.error(f"Error publishing knowledge base article: {e}")
            raise

    # Helper functions for bulk operations
    def perform_bulk_assign(support, tickets):
        """Helper function for bulk assignment from ticket list"""
        print("\n👨‍💼 BULK ASSIGN FROM LIST")
        print("="*40)
        
        assigned_to = input("Assign to (username): ").strip()
        if not assigned_to:
            print("❌ Staff username is required.")
            return
        
        # Get ticket IDs to assign
        ticket_ids_input = input("Enter ticket numbers to assign (comma-separated) or 'all' for all tickets: ").strip()
        
        if ticket_ids_input.lower() == 'all':
            ticket_ids = [t['ticket_id'] for t in tickets]
        else:
            try:
                ticket_ids = [int(id.strip()) for id in ticket_ids_input.split(',')]
                # Validate ticket IDs are in the current list
                valid_ids = [t['ticket_id'] for t in tickets]
                ticket_ids = [tid for tid in ticket_ids if tid in valid_ids]
            except ValueError:
                print("❌ Invalid ticket IDs.")
                return
        
        if not ticket_ids:
            print("❌ No valid ticket IDs provided.")
            return
        
        # Confirm operation
        print(f"\n📋 Updating {len(ticket_ids)} tickets to status '{new_status}'")
        confirm = input("Confirm bulk status update? (y/n): ").lower()
        
        if confirm == 'y':
            try:
                updates = {'status': new_status}
                updated_count = support.bulk_update_tickets(ticket_ids, updates)
                print(f"✅ Successfully updated status for {updated_count} tickets")
            except Exception as e:
                print(f"❌ Error during bulk status update: {e}")
        else:
            print("❌ Bulk status update cancelled.")

    def export_filtered_results(support, filters):
        """Helper function to export filtered results"""
        print("\n📤 EXPORT FILTERED RESULTS")
        print("="*40)
        
        # Format selection
        print("Export formats:")
        print("1. CSV")
        print("2. JSON")
        
        format_choice = input("Select format (1-2): ").strip()
        export_format = 'csv' if format_choice == '1' else 'json'
        
        try:
            # Export data
            print("\n📊 Exporting filtered results...")
            exported_data = support.export_data('tickets', filters, export_format)
            
            # Save to file
            ext = 'csv' if export_format == 'csv' else 'json'
            filename = f"filtered_results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
            
            with open(filename, 'w') as f:
                f.write(exported_data)
            
            print(f"✅ Filtered results exported to {filename}")
            
        except Exception as e:
            print(f"❌ Error exporting filtered results: {e}")

    def update_status_enhanced(support, ticket_id):
        """Enhanced status update with resolution notes"""
        try:
            print(f"\n📊 UPDATE TICKET #{ticket_id} STATUS")
            print("="*50)
            
            # Show current status
            ticket = support.get_ticket_details(ticket_id)
            print(f"Current Status: {ticket['status']}")
            
            # Status selection
            print("\nNew Status:")
            for i, status in enumerate(TICKET_STATUSES, 1):
                print(f"{i}. {status}")
            
            choice = input(f"Select new status (1-{len(TICKET_STATUSES)}): ").strip()
            
            if not choice.isdigit() or not 1 <= int(choice) <= len(TICKET_STATUSES):
                print("❌ Invalid status choice.")
                return
            
            new_status = TICKET_STATUSES[int(choice) - 1]
            
            # Resolution notes for resolved/closed tickets
            resolution_notes = None
            if new_status in ['Resolved', 'Closed']:
                print(f"\nResolution notes for {new_status} status:")
                lines = []
                while True:
                    line = input()
                    if not line and (not lines or not lines[-1]):
                        break
                    lines.append(line)
                
                if lines:
                    resolution_notes = '\n'.join(lines)
            
            # Update status
            support.update_ticket_status(ticket_id, new_status, resolution_notes)
            print(f"✅ Ticket #{ticket_id} status updated to '{new_status}'")
            
        except Exception as e:
            print(f"❌ Error updating status: {e}")

    def add_internal_note(support, ticket_id):
        """Add internal note to ticket"""
        try:
            print(f"\n🔒 ADD INTERNAL NOTE TO TICKET #{ticket_id}")
            print("="*50)
            
            print("Internal note (visible only to staff, press Enter twice to finish):")
            lines = []
            while True:
                line = input()
                if not line and (not lines or not lines[-1]):
                    break
                lines.append(line)
            
            note_text = '\n'.join(lines)
            
            if not note_text:
                print("❌ Note cannot be empty.")
                return
            
            # Add as internal response
            support.add_ticket_response(ticket_id, note_text, is_internal=True)
            print("✅ Internal note added successfully!")
            
        except Exception as e:
            print(f"❌ Error adding internal note: {e}")

    def view_ticket_history(support, ticket_id):
        """View complete ticket history"""
        try:
            print(f"\n📚 TICKET #{ticket_id} HISTORY")
            print("="*60)
            
            history = support.get_ticket_history(ticket_id)
            ticket = history['ticket']
            timeline = history['timeline']
            
            print(f"🎫 {ticket['title']}")
            print(f"👤 Student: {ticket['student_id']}")
            print(f"📊 Current Status: {ticket['status']}")
            print(f"🔥 Priority: {ticket['priority']}")
            print(f"📂 Category: {ticket['category']}")
            
            print(f"\n📅 TIMELINE ({len(timeline)} events):")
            print("="*60)
            
            for event in timeline:
                event_type = event['type']
                data = event['data']
                datetime_str = event['datetime']
                
                if event_type == 'creation':
                    print(f"🎫 [{datetime_str}] Ticket Created")
                    print(f"   📝 {data['description'][:100]}...")
                    
                elif event_type == 'response':
                    responder = data['responder_role']
                    is_internal = data.get('is_internal', False)
                    is_auto = data.get('is_auto_generated', False)
                    
                    internal_tag = " 🔒" if is_internal else ""
                    auto_tag = " 🤖" if is_auto else ""
                    
                    print(f"💬 [{datetime_str}] Response by {responder}{internal_tag}{auto_tag}")
                    print(f"   📝 {data['response_text'][:100]}...")
                    
                elif event_type == 'attachment':
                    print(f"📎 [{datetime_str}] Attachment Added")
                    print(f"   📄 {data['original_filename']} ({data['file_size']} bytes)")
                    
                elif event_type == 'audit':
                    print(f"🔍 [{datetime_str}] System Event")
                    print(f"   ⚙️ {data['action']} by {data.get('user_id', 'system')}")
                
                print()
            
            # Pagination for large histories
            if len(timeline) > 20:
                print(f"... showing first 20 of {len(timeline)} events")
                show_all = input("Show all events? (y/n): ").lower()
                if show_all == 'y':
                    for event in timeline[20:]:
                        # Display remaining events (same format as above)
                        pass
            
        except Exception as e:
            print(f"❌ Error viewing ticket history: {e}")
        
        input("\nPress Enter to continue...")

    def download_attachment_menu(support, attachments):
        """Download attachment menu"""
        try:
            print(f"\n📎 DOWNLOAD ATTACHMENTS")
            print("="*40)
            
            print("Available attachments:")
            for i, att in enumerate(attachments, 1):
                size_mb = att['file_size'] / (1024 * 1024)
                print(f"{i}. 📄 {att['original_filename']} ({size_mb:.1f}MB)")
                print(f"   📅 Uploaded: {att['uploaded_datetime']}")
                print(f"   👤 By: {att['uploaded_by']}")
            
            choice = input(f"\nSelect attachment to download (1-{len(attachments)}): ").strip()
            
            if not choice.isdigit() or not 1 <= int(choice) <= len(attachments):
                print("❌ Invalid choice.")
                return
            
            attachment = attachments[int(choice) - 1]
            attachment_id = attachment['attachment_id']
            
            # Download attachment
            print(f"📥 Downloading {attachment['original_filename']}...")
            
            file_info = support.download_attachment(attachment_id)
            
            # Save to current directory
            filename = file_info['filename']
            with open(filename, 'wb') as f:
                f.write(file_info['data'])
            
            print(f"✅ File downloaded as {filename}")
            
        except Exception as e:
            print(f"❌ Error downloading attachment: {e}")
        
        input("\nPress Enter to continue...")

    # Ticket management enhancements
    def merge_tickets(self, primary_ticket_id, secondary_ticket_ids, merge_reason):
        """Merge multiple tickets into one primary ticket"""
        if not auth or not auth.current_user or auth.current_user['role'] not in ('staff', 'admin'):
            raise PermissionError("Only staff can merge tickets")
        
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            # Validate primary ticket exists
            cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ?', (primary_ticket_id,))
            primary_ticket = cursor.fetchone()
            
            if not primary_ticket:
                raise ValueError(f"Primary ticket {primary_ticket_id} not found")
            
            merge_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Merge each secondary ticket
            for secondary_id in secondary_ticket_ids:
                # Validate secondary ticket
                cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ?', (secondary_id,))
                secondary_ticket = cursor.fetchone()
                
                if not secondary_ticket:
                    logger.warning(f"Secondary ticket {secondary_id} not found, skipping")
                    continue
                
                # Update secondary ticket to reference primary
                cursor.execute('''
                UPDATE support_tickets 
                SET parent_ticket_id = ?, status = 'Closed', closed_at = ?
                WHERE ticket_id = ?
                ''', (primary_ticket_id, merge_time, secondary_id))
                
                # Copy responses from secondary to primary
                cursor.execute('''
                INSERT INTO ticket_responses (
                    ticket_id, responder_id, responder_role, response_text, 
                    response_datetime, is_internal
                )
                SELECT ?, responder_id, responder_role, 
                       '[MERGED FROM TICKET #' || ? || '] ' || response_text,
                       response_datetime, 1
                FROM ticket_responses 
                WHERE ticket_id = ?
                ''', (primary_ticket_id, secondary_id, secondary_id))
                
                # Copy attachments
                cursor.execute('''
                UPDATE ticket_attachments 
                SET ticket_id = ? 
                WHERE ticket_id = ?
                ''', (primary_ticket_id, secondary_id))
            
            # Add merge note to primary ticket
            cursor.execute('''
            INSERT INTO ticket_responses (
                ticket_id, responder_id, responder_role, response_text,
                response_datetime, is_auto_generated
            ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                primary_ticket_id, auth.current_user['id'], auth.current_user['role'],
                f"Tickets merged: {', '.join(map(str, secondary_ticket_ids))}. Reason: {merge_reason}",
                merge_time, 1
            ))
            
            # Update primary ticket timestamp
            cursor.execute('''
            UPDATE support_tickets 
            SET last_updated_datetime = ?
            WHERE ticket_id = ?
            ''', (merge_time, primary_ticket_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Tickets {secondary_ticket_ids} merged into {primary_ticket_id} by {auth.current_user['username']}")
            return True
            
        except Exception as e:
            logger.error(f"Error merging tickets: {e}")
            raise

    def bulk_update_tickets(self, ticket_ids, updates):
        """Bulk update multiple tickets"""
        if not auth or not auth.current_user or auth.current_user['role'] not in ('staff', 'admin'):
            raise PermissionError("Only staff can perform bulk updates")
        
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            update_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            updated_count = 0
            
            for ticket_id in ticket_ids:
                # Validate ticket exists
                cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
                ticket = cursor.fetchone()
                
                if not ticket:
                    logger.warning(f"Ticket {ticket_id} not found, skipping")
                    continue
                
                # Build update query
                update_fields = []
                params = []
                
                if 'status' in updates:
                    update_fields.append('status = ?')
                    params.append(updates['status'])
                
                if 'priority' in updates:
                    update_fields.append('priority = ?')
                    params.append(updates['priority'])
                
                if 'assigned_to' in updates:
                    update_fields.append('assigned_to = ?')
                    params.append(updates['assigned_to'])
                
                if 'category' in updates:
                    update_fields.append('category = ?')
                    params.append(updates['category'])
                
                if update_fields:
                    update_fields.append('last_updated_datetime = ?')
                    params.append(update_time)
                    params.append(ticket_id)
                    
                    query = f"UPDATE support_tickets SET {', '.join(update_fields)} WHERE ticket_id = ?"
                    cursor.execute(query, params)
                    
                    # Add bulk update note
                    cursor.execute('''
                    INSERT INTO ticket_responses (
                        ticket_id, responder_id, responder_role, response_text,
                        response_datetime, is_auto_generated
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        ticket_id, auth.current_user['id'], auth.current_user['role'],
                        f"Bulk update applied: {', '.join([f'{k}={v}' for k, v in updates.items()])}",
                        update_time, 1
                    ))
                    
                    updated_count += 1
            
            conn.commit()
            conn.close()
            
            logger.info(f"Bulk update applied to {updated_count} tickets by {auth.current_user['username']}")
            return updated_count
            
        except Exception as e:
            logger.error(f"Error performing bulk update: {e}")
            raise

    def get_ticket_history(self, ticket_id):
        """Get complete history of a ticket including all changes"""
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get ticket details
            cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
            ticket = cursor.fetchone()
            
            if not ticket:
                raise ValueError(f"Ticket {ticket_id} not found")
            
            # Check permissions
            if auth.current_user['role'] == 'student':
                conn_main = get_connection()
                cursor_main = conn_main.cursor()
                cursor_main.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
                result = cursor_main.fetchone()
                conn_main.close()
                
                if not result or result[0] != ticket['student_id']:
                    raise PermissionError("You can only view history of your own tickets")
            
            # Get all responses
            cursor.execute('''
            SELECT * FROM ticket_responses 
            WHERE ticket_id = ? 
            ORDER BY response_datetime ASC
            ''', (ticket_id,))
            responses = [dict(row) for row in cursor.fetchall()]
            
            # Get attachments
            cursor.execute('SELECT * FROM ticket_attachments WHERE ticket_id = ?', (ticket_id,))
            attachments = [dict(row) for row in cursor.fetchall()]
            
            # Get related audit trail
            cursor.execute('''
            SELECT * FROM audit_trail 
            WHERE resource_id = ? AND resource_type LIKE '%ticket%'
            ORDER BY timestamp ASC
            ''', (str(ticket_id),))
            audit_entries = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            
            # Combine into timeline
            timeline = []
            
            # Add ticket creation
            timeline.append({
                'type': 'creation',
                'datetime': ticket['created_datetime'],
                'data': dict(ticket)
            })
            
            # Add responses
            for response in responses:
                timeline.append({
                    'type': 'response',
                    'datetime': response['response_datetime'],
                    'data': response
                })
            
            # Add attachments
            for attachment in attachments:
                timeline.append({
                    'type': 'attachment',
                    'datetime': attachment['uploaded_datetime'],
                    'data': attachment
                })
            
            # Add audit entries
            for audit in audit_entries:
                timeline.append({
                    'type': 'audit',
                    'datetime': audit['timestamp'],
                    'data': audit
                })
            
            # Sort by datetime
            timeline.sort(key=lambda x: x['datetime'])
            
            return {
                'ticket': dict(ticket),
                'timeline': timeline
            }
            
        except Exception as e:
            logger.error(f"Error getting ticket history: {e}")
            raise

    def export_data(self, export_type, filters=None, format='csv'):
        """Export support data in various formats"""
        if not auth or not auth.current_user or auth.current_user['role'] not in ('staff', 'admin'):
            raise PermissionError("Only staff can export data")
        
        try:
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()
            
            if export_type == 'tickets':
                data = self._export_tickets(cursor, filters)
            elif export_type == 'responses':
                data = self._export_responses(cursor, filters)
            elif export_type == 'metrics':
                data = self._export_metrics(cursor, filters)
            else:
                raise ValueError(f"Unknown export type: {export_type}")
            
            conn.close()
            
            # Format data
            if format == 'csv':
                return self._format_as_csv(data)
            elif format == 'json':
                return json.dumps(data, indent=2)
            else:
                raise ValueError(f"Unknown format: {format}")
            
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            raise

    def _export_tickets(self, cursor, filters):
        """Export ticket data"""
        query = "SELECT * FROM support_tickets WHERE 1=1"
        params = []
        
        if filters:
            if filters.get('date_from'):
                query += " AND created_datetime >= ?"
                params.append(filters['date_from'])
            
            if filters.get('date_to'):
                query += " AND created_datetime <= ?"
                params.append(filters['date_to'])
            
            if filters.get('status'):
                query += " AND status = ?"
                params.append(filters['status'])
        
        query += " ORDER BY created_datetime DESC"
        
        cursor.execute(query, params)
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        
        return {
            'columns': columns,
            'rows': rows
        }

    def _export_responses(self, cursor, filters):
        """Export response data"""
        query = """
        SELECT tr.*, st.title, st.category, st.priority
        FROM ticket_responses tr
        JOIN support_tickets st ON tr.ticket_id = st.ticket_id
        WHERE 1=1
        """
        params = []
        
        if filters:
            if filters.get('date_from'):
                query += " AND tr.response_datetime >= ?"
                params.append(filters['date_from'])
            
            if filters.get('date_to'):
                query += " AND tr.response_datetime <= ?"
                params.append(filters['date_to'])
        
        query += " ORDER BY tr.response_datetime DESC"
        
        cursor.execute(query, params)
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        
        return {
            'columns': columns,
            'rows': rows
        }

    def _export_metrics(self, cursor, filters):
        """Export metrics data"""
        query = "SELECT * FROM system_metrics WHERE 1=1"
        params = []
        
        if filters:
            if filters.get('date_from'):
                query += " AND recorded_datetime >= ?"
                params.append(filters['date_from'])
            
            if filters.get('date_to'):
                query += " AND recorded_datetime <= ?"
                params.append(filters['date_to'])
            
            if filters.get('category'):
                query += " AND category = ?"
                params.append(filters['category'])
        
        query += " ORDER BY recorded_datetime DESC"
        
        cursor.execute(query, params)
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        
        return {
            'columns': columns,
            'rows': rows
        }

    def _format_as_csv(self, data):
        """Format data as CSV string"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(data['columns'])
        
        # Write rows
        for row in data['rows']:
            writer.writerow(row)
        
        return output.getvalue()


def display_enhanced_faqs(support):
    """Display enhanced FAQ interface"""
    try:
        print("\n❓ FREQUENTLY ASKED QUESTIONS")
        print("="*50)
        
        # Get FAQ categories
        conn = sqlite3.connect("student_records.db")
        cursor = conn.cursor()
        
        # Check if faqs table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='faqs'")
        if not cursor.fetchone():
            print("📭 No FAQs available (table not found).")
            conn.close()
            return
            
        cursor.execute('SELECT DISTINCT category FROM faqs ORDER BY category')
        categories = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        if not categories:
            print("📭 No FAQs available.")
            return
        
        print("📂 Categories:")
        print("0. All Categories")
        for i, category in enumerate(categories, 1):
            print(f"{i}. {category}")
        
        print(f"{len(categories) + 1}. Search FAQs")
        print(f"{len(categories) + 2}. Back")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == '0':
            # Show all FAQs
            faqs = support._search_faqs('', None)
            display_faq_list(faqs, "All FAQs")
        elif choice.isdigit() and 1 <= int(choice) <= len(categories):
            # Show FAQs in category
            category = categories[int(choice) - 1]
            faqs = support._search_faqs('', {'category': category})
            display_faq_list(faqs, f"{category} FAQs")
        elif choice == str(len(categories) + 1):
            # Search FAQs
            search_query = input("Enter search query: ").strip()
            if search_query:
                faqs = support._search_faqs(search_query, None)
                display_faq_list(faqs, f"Search Results for '{search_query}'")
        elif choice == str(len(categories) + 2):
            return
        else:
            print("❌ Invalid choice.")
    
    except Exception as e:
        print(f"❌ Error displaying FAQs: {e}")
    
    input("\nPress Enter to continue...")

def display_faq_list(faqs, title):
    """Display a list of FAQs"""
    print(f"\n❓ {title}")
    print("="*50)
    
    if not faqs:
        print("📭 No FAQs found.")
        return
    
    for i, faq in enumerate(faqs[:10], 1):  # Show first 10
        views = faq.get('view_count', 0)
        votes = faq.get('helpful_votes', 0)
        print(f"{i}. Q: {faq['question']}")
        print(f"   👁️ {views} views | 👍 {votes} helpful")
    
    if len(faqs) > 10:
        print(f"\n... and {len(faqs) - 10} more FAQs")
    
    # View FAQ option
    view_choice = input(f"\nView FAQ (1-{min(len(faqs), 10)}) or press Enter to go back: ").strip()
    if view_choice.isdigit() and 1 <= int(view_choice) <= min(len(faqs), 10):
        faq = faqs[int(view_choice) - 1]
        display_full_faq(faq)

def display_full_faq(faq):
    """Display full FAQ with answer"""
    print(f"\n❓ {faq['question']}")
    print("="*60)
    print(f"📂 Category: {faq['category']}")
    print(f"👁️ Views: {faq.get('view_count', 0)}")
    print(f"👍 Helpful: {faq.get('helpful_votes', 0)}")
    
    print(f"\n💡 Answer:")
    print("-" * 40)
    print(faq['answer'])
    print("-" * 40)
    
    # Actions
    print("\n🔧 Actions:")
    print("1. Mark as helpful")
    print("2. Back")
    
    action = input("Choose action: ").strip()
    
    if action == '1':
        print("✅ Marked as helpful. Thank you for your feedback!")

def display_enhanced_resources(support):
    """Display enhanced resources interface"""
    try:
        print("\n📋 SUPPORT RESOURCES")
        print("="*50)
        
        # Get resource categories
        conn = sqlite3.connect("student_records.db")
        cursor = conn.cursor()
        
        # Check if support_resources table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='support_resources'")
        if not cursor.fetchone():
            print("📭 No resources available (table not found).")
            conn.close()
            return
            
        cursor.execute('SELECT DISTINCT category FROM support_resources ORDER BY category')
        categories = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        if not categories:
            print("📭 No resources available.")
            return
        
        print("📂 Categories:")
        print("0. All Categories")
        for i, category in enumerate(categories, 1):
            print(f"{i}. {category}")
        
        print(f"{len(categories) + 1}. Featured Resources")
        print(f"{len(categories) + 2}. Search Resources")
        print(f"{len(categories) + 3}. Back")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == '0':
            # Show all resources
            resources = support._search_resources('', None)
            display_resource_list(resources, "All Resources")
        elif choice.isdigit() and 1 <= int(choice) <= len(categories):
            # Show resources in category
            category = categories[int(choice) - 1]
            resources = support._search_resources('', {'category': category})
            display_resource_list(resources, f"{category} Resources")
        elif choice == str(len(categories) + 1):
            # Featured resources
            conn = sqlite3.connect("student_records.db")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM support_resources WHERE is_featured = 1 ORDER BY access_count DESC')
            resources = [dict(row) for row in cursor.fetchall()]
            conn.close()
            display_resource_list(resources, "Featured Resources")
        elif choice == str(len(categories) + 2):
            # Search resources
            search_query = input("Enter search query: ").strip()
            if search_query:
                resources = support._search_resources(search_query, None)
                display_resource_list(resources, f"Search Results for '{search_query}'")
        elif choice == str(len(categories) + 3):
            return
        else:
            print("❌ Invalid choice.")
    
    except Exception as e:
        print(f"❌ Error displaying resources: {e}")
    
    input("\nPress Enter to continue...")

def display_resource_list(resources, title):
    """Display a list of support resources"""
    print(f"\n📋 {title}")
    print("="*50)
    
    if not resources:
        print("📭 No resources found.")
        return
    
    for i, resource in enumerate(resources[:10], 1):  # Show first 10
        access_count = resource.get('access_count', 0)
        print(f"{i}. 📄 {resource['title']}")
        print(f"   📂 Category: {resource['category']}")
        print(f"   👁️ {access_count} accesses")
        print(f"   📝 {resource['description'][:80]}...")
    
    if len(resources) > 10:
        print(f"\n... and {len(resources) - 10} more resources")
    
    # View resource option
    view_choice = input(f"\nView resource (1-{min(len(resources), 10)}) or press Enter to go back: ").strip()
    if view_choice.isdigit() and 1 <= int(view_choice) <= min(len(resources), 10):
        resource = resources[int(view_choice) - 1]
        display_full_resource(resource)

def display_full_resource(resource):
    """Display full resource details"""
    print(f"\n📄 {resource['title']}")
    print("="*60)
    print(f"📂 Category: {resource['category']}")
    print(f"✏️ Created by: {resource['created_by']}")
    print(f"📅 Created: {resource['created_datetime']}")
    print(f"👁️ Accesses: {resource.get('access_count', 0)}")
    
    if resource.get('tags'):
        try:
            tags = json.loads(resource['tags']) if isinstance(resource['tags'], str) else resource['tags']
            if tags:
                print(f"🏷️ Tags: {', '.join(tags)}")
        except (json.JSONDecodeError, TypeError):
            pass
    
    print(f"\n📝 Description:")
    print("-" * 40)
    print(resource['description'])
    print("-" * 40)
    
    if resource.get('url'):
        print(f"🔗 URL: {resource['url']}")
    
    if resource.get('file_path'):
        print(f"📁 File: {resource['file_path']}")

def view_all_tickets_enhanced(support):
    """View all tickets with advanced filtering (staff only)"""
    try:
        print("\n🎫 ALL SUPPORT TICKETS")
        print("="*50)
        
        # Advanced filter menu
        print("📊 Filter Options:")
        print("1. All tickets")
        print("2. By status")
        print("3. By category")
        print("4. By priority")
        print("5. By assigned staff")
        print("6. By date range")
        print("7. Unassigned tickets")
        print("8. High priority tickets")
        print("9. Search tickets")
        
        choice = input("\nSelect filter: ").strip()
        
        filters = {}
        
        if choice == '2':
            status_options = ['Open', 'In Progress', 'Resolved', 'Closed', 'Escalated', 'On Hold']
            print("\nStatuses:")
            for i, status in enumerate(status_options, 1):
                print(f"{i}. {status}")
            status_choice = input(f"Select status (1-{len(status_options)}): ").strip()
            if status_choice.isdigit() and 1 <= int(status_choice) <= len(status_options):
                filters['status'] = status_options[int(status_choice) - 1]
        elif choice == '3':
            category_options = ['Academic', 'Technical', 'Financial Aid', 'Library Services', 'Other']
            print("\nCategories:")
            for i, cat in enumerate(category_options, 1):
                print(f"{i}. {cat}")
            cat_choice = input(f"Select category (1-{len(category_options)}): ").strip()
            if cat_choice.isdigit() and 1 <= int(cat_choice) <= len(category_options):
                filters['category'] = category_options[int(cat_choice) - 1]
        elif choice == '5':
            assigned_to = input("Enter staff username: ").strip()
            if assigned_to:
                filters['assigned_to'] = assigned_to
        elif choice == '7':
            filters['assigned_to'] = None
        elif choice == '9':
            search_query = input("Enter search query: ").strip()
            if search_query:
                filters['search'] = search_query
        
        # Get tickets
        try:
            result = support.get_student_tickets(None, filters, page=1, per_page=20)
            tickets = result['tickets']
        except Exception as e:
            print(f"❌ Error retrieving tickets: {e}")
            return
        
        if not tickets:
            print("📭 No tickets found with the selected filters.")
            return
        
        # Display tickets
        print(f"\n🎫 Found {result['total_count']} tickets (showing page {result['page']} of {result['total_pages']}):")
        print("="*100)
        
        for ticket in tickets:
            status_emoji = {'Open': '🟢', 'In Progress': '⏳', 'Resolved': '✅', 'Closed': '🔒', 'Escalated': '🚨'}.get(ticket['status'], '❓')
            priority_emoji = {'Critical': '🔴', 'Urgent': '🟠', 'High': '🟡', 'Medium': '🔵', 'Low': '🟢'}.get(ticket['priority'], '⚪')
            
            print(f"{status_emoji} #{ticket['ticket_id']} - {ticket['title']}")
            print(f"   👤 Student: {ticket['student_id']} | 📂 {ticket['category']} | {priority_emoji} {ticket['priority']}")
            print(f"   📅 Created: {ticket['created_datetime']}")
            
            if ticket.get('assigned_to'):
                print(f"   👨‍💼 Assigned to: {ticket['assigned_to']}")
            else:
                print(f"   ❌ Unassigned")
            
            print()
        
        # View specific ticket
        if tickets:
            ticket_choice = input(f"View ticket details (enter ticket #) or press Enter to go back: ").strip()
            if ticket_choice.isdigit():
                ticket_id = int(ticket_choice)
                if any(t['ticket_id'] == ticket_id for t in tickets):
                    try:
                        display_ticket_details_enhanced(support, ticket_id)
                    except Exception as e:
                        print(f"❌ Error displaying ticket: {e}")
                else:
                    print("❌ Ticket not found in current list.")
    
    except Exception as e:
        print(f"❌ Error viewing tickets: {e}")
    
    input("\nPress Enter to continue...")

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
        
        conn = sqlite3.connect("student_records.db")
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

def manage_templates_menu(support):
    """Manage ticket and response templates (staff only)"""
    try:
        print("\n📋 MANAGE TEMPLATES")
        print("="*40)
        
        print("1. View ticket templates")
        print("2. Create ticket template")
        print("3. View response templates")
        print("4. Create response template")
        print("5. Template usage statistics")
        print("6. Back")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == '1':
            view_ticket_templates(support)
        elif choice == '2':
            create_ticket_template_interactive(support)
        elif choice == '3':
            view_response_templates(support)
        elif choice == '4':
            create_response_template_interactive(support)
        elif choice == '5':
            show_template_statistics(support)
        elif choice == '6':
            return
        else:
            print("❌ Invalid choice.")
    
    except Exception as e:
        print(f"❌ Error managing templates: {e}")
    
    input("\nPress Enter to continue...")

def view_ticket_templates(support):
    """View all ticket templates"""
    try:
        templates = support.get_ticket_templates()
        
        if not templates:
            print("📭 No ticket templates found.")
            return
        
        print("\n📋 TICKET TEMPLATES")
        print("="*50)
        
        for template in templates:
            print(f"📄 {template['name']}")
            print(f"   📂 Category: {template['category']} | 🔥 Priority: {template['priority']}")
            print(f"   📈 Used {template.get('usage_count', 0)} times")
            print(f"   ✏️ Created by: {template['created_by']} on {template['created_datetime']}")
            print(f"   📝 Title: {template['title_template'][:60]}...")
            print()
    except Exception as e:
        print(f"❌ Error viewing templates: {e}")

def create_ticket_template_interactive(support):
    """Interactive ticket template creation"""
    try:
        print("\n📋 CREATE TICKET TEMPLATE")
        print("="*40)
        
        name = input("Template name: ").strip()
        if not name:
            print("❌ Template name is required.")
            return
        
        title_template = input("Title template: ").strip()
        if not title_template:
            print("❌ Title template is required.")
            return
        
        print("Description template (press Enter twice to finish):")
        lines = []
        while True:
            line = input()
            if not line and (not lines or not lines[-1]):
                break
            lines.append(line)
        
        description_template = '\n'.join(lines)
        if not description_template:
            print("❌ Description template is required.")
            return
        
        categories = ['Academic', 'Technical', 'Financial Aid', 'Library Services', 'Other']
        print("\nCategories:")
        for i, cat in enumerate(categories, 1):
            print(f"{i}. {cat}")
        
        cat_choice = input(f"Select category (1-{len(categories)}): ").strip()
        if not cat_choice.isdigit() or not 1 <= int(cat_choice) <= len(categories):
            print("❌ Invalid category.")
            return
        
        category = categories[int(cat_choice) - 1]
        
        priorities = ['Low', 'Medium', 'High', 'Urgent', 'Critical']
        print("\nPriorities:")
        for i, pri in enumerate(priorities, 1):
            print(f"{i}. {pri}")
        
        pri_choice = input(f"Select priority (1-{len(priorities)}): ").strip()
        if not pri_choice.isdigit() or not 1 <= int(pri_choice) <= len(priorities):
            print("❌ Invalid priority.")
            return
        
        priority = priorities[int(pri_choice) - 1]
        
        # Create template
        template_id = support.create_ticket_template(name, title_template, description_template, category, priority)
        print(f"✅ Ticket template '{name}' created successfully (ID: {template_id})!")
    
    except Exception as e:
        print(f"❌ Error creating template: {e}")

def view_response_templates(support):
    """View all response templates"""
    try:
        templates = support.get_response_templates()
        
        if not templates:
            print("📭 No response templates found.")
            return
        
        print("\n💬 RESPONSE TEMPLATES")
        print("="*50)
        
        for template in templates:
            print(f"💬 {template['name']}")
            if template.get('category'):
                print(f"   📂 Category: {template['category']}")
            print(f"   📈 Used {template.get('usage_count', 0)} times")
            print(f"   ✏️ Created by: {template['created_by']} on {template['created_datetime']}")
            if template.get('subject'):
                print(f"   📧 Subject: {template['subject']}")
            print(f"   📝 Content: {template['content'][:100]}...")
            print()
    except Exception as e:
        print(f"❌ Error viewing templates: {e}")

def create_response_template_interactive(support):
    """Interactive response template creation"""
    try:
        print("\n💬 CREATE RESPONSE TEMPLATE")
        print("="*40)
        
        name = input("Template name: ").strip()
        if not name:
            print("❌ Template name is required.")
            return
        
        subject = input("Email subject (optional): ").strip()
        
        print("Template content (press Enter twice to finish):")
        lines = []
        while True:
            line = input()
            if not line and (not lines or not lines[-1]):
                break
            lines.append(line)
        
        content = '\n'.join(lines)
        if not content:
            print("❌ Template content is required.")
            return
        
        category = input("Category (optional): ").strip() or None
        
        variables_input = input("Variables (comma-separated, e.g., TICKET_ID,USER_NAME): ").strip()
        variables = [var.strip() for var in variables_input.split(',')] if variables_input else []
        
        # Create template
        template_id = support.create_response_template(name, subject, content, category, variables)
        print(f"✅ Response template '{name}' created successfully (ID: {template_id})!")
    
    except Exception as e:
        print(f"❌ Error creating template: {e}")

def show_template_statistics(support):
    """Show template usage statistics"""
    try:
        print("\n📊 TEMPLATE USAGE STATISTICS")
        print("="*50)
        
        conn = sqlite3.connect("student_records.db")
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ticket_templates'")
        has_ticket_templates = cursor.fetchone() is not None
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='response_templates'")
        has_response_templates = cursor.fetchone() is not None
        
        # Ticket template stats
        print("🎫 TICKET TEMPLATES:")
        if has_ticket_templates:
            cursor.execute('''
            SELECT name, usage_count, created_datetime 
            FROM ticket_templates 
            WHERE is_active = 1 
            ORDER BY usage_count DESC
            ''')
            ticket_templates = cursor.fetchall()
            
            if ticket_templates:
                for name, usage_count, created_date in ticket_templates:
                    print(f"   📋 {name}: {usage_count} uses (created {created_date})")
            else:
                print("   📭 No ticket templates found.")
        else:
            print("   📭 Ticket templates table not found.")
        
        # Response template stats
        print("\n💬 RESPONSE TEMPLATES:")
        if has_response_templates:
            cursor.execute('''
            SELECT name, usage_count, created_datetime 
            FROM response_templates 
            WHERE is_active = 1 
            ORDER BY usage_count DESC
            ''')
            response_templates = cursor.fetchall()
            
            if response_templates:
                for name, usage_count, created_date in response_templates:
                    print(f"   💬 {name}: {usage_count} uses (created {created_date})")
            else:
                print("   📭 No response templates found.")
        else:
            print("   📭 Response templates table not found.")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error getting template statistics: {e}")

# Database schema fix for user_preferences table
def fix_user_preferences_table():
    """Fix the user_preferences table schema"""
    try:
        conn = sqlite3.connect("student_records.db")
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'")
        if not cursor.fetchone():
            # Create the table with proper schema
            cursor.execute('''
            CREATE TABLE user_preferences (
                user_id TEXT PRIMARY KEY,
                email_notifications BOOLEAN DEFAULT 1,
                in_app_notifications BOOLEAN DEFAULT 1,
                push_notifications BOOLEAN DEFAULT 1,
                digest_frequency TEXT DEFAULT 'daily',
                theme TEXT DEFAULT 'light',
                language TEXT DEFAULT 'en',
                timezone TEXT DEFAULT 'UTC',
                preferences_json TEXT
            )
            ''')
            print("✅ Created user_preferences table")
        else:
            # Check existing columns
            cursor.execute("PRAGMA table_info(user_preferences)")
            existing_columns = [column[1] for column in cursor.fetchall()]
            
            required_columns = {
                'email_notifications': 'BOOLEAN DEFAULT 1',
                'in_app_notifications': 'BOOLEAN DEFAULT 1', 
                'push_notifications': 'BOOLEAN DEFAULT 1',
                'digest_frequency': 'TEXT DEFAULT "daily"',
                'theme': 'TEXT DEFAULT "light"',
                'language': 'TEXT DEFAULT "en"',
                'timezone': 'TEXT DEFAULT "UTC"',
                'preferences_json': 'TEXT'
            }
            
            for column_name, column_def in required_columns.items():
                if column_name not in existing_columns:
                    try:
                        cursor.execute(f'ALTER TABLE user_preferences ADD COLUMN {column_name} {column_def}')
                        print(f"✅ Added column '{column_name}' to user_preferences table")
                    except Exception as e:
                        print(f"⚠️ Could not add column '{column_name}': {e}")
        
        conn.commit()
        conn.close()
        print("✅ User preferences table schema fixed")
        
    except Exception as e:
        print(f"❌ Error fixing user_preferences table: {e}")

# Enhanced get_user_preferences method to handle missing columns gracefully
def get_user_preferences_safe(support_instance, user_id=None):
    """Safely get user preferences with fallback for missing columns"""
    if not user_id and hasattr(support_instance, 'auth') and support_instance.auth and support_instance.auth.current_user:
        user_id = support_instance.auth.current_user['id']
    
    if not user_id:
        return {
            'email_notifications': True,
            'in_app_notifications': True,
            'push_notifications': True,
            'digest_frequency': 'daily',
            'theme': 'light',
            'language': 'en',
            'timezone': 'UTC'
        }
    
    try:
        conn = sqlite3.connect("student_records.db")
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'")
        if not cursor.fetchone():
            conn.close()
            return {
                'email_notifications': True,
                'in_app_notifications': True,
                'push_notifications': True,
                'digest_frequency': 'daily',
                'theme': 'light',
                'language': 'en',
                'timezone': 'UTC'
            }
        
        # Get table columns
        cursor.execute("PRAGMA table_info(user_preferences)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Build safe query with only existing columns
        available_columns = []
        default_values = {
            'email_notifications': True,
            'in_app_notifications': True,
            'push_notifications': True,
            'digest_frequency': 'daily',
            'theme': 'light',
            'language': 'en',
            'timezone': 'UTC',
            'preferences_json': None
        }
        
        for col in default_values.keys():
            if col in columns:
                available_columns.append(col)
        
        if available_columns:
            query = f"SELECT {', '.join(available_columns)} FROM user_preferences WHERE user_id = ?"
            cursor.execute(query, (user_id,))
            result = cursor.fetchone()
            
            if result:
                prefs = {}
                for i, col in enumerate(available_columns):
                    prefs[col] = result[i]
                
                # Fill in missing columns with defaults
                for col, default_val in default_values.items():
                    if col not in prefs:
                        prefs[col] = default_val
                
                # Parse JSON preferences if available
                if prefs.get('preferences_json'):
                    try:
                        additional_prefs = json.loads(prefs['preferences_json'])
                        prefs.update(additional_prefs)
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                conn.close()
                return prefs
        
        conn.close()
        return default_values
        
    except Exception as e:
        print(f"❌ Error getting user preferences: {e}")
        return {
            'email_notifications': True,
            'in_app_notifications': True,
            'push_notifications': True,
            'digest_frequency': 'daily',
            'theme': 'light',
            'language': 'en',
            'timezone': 'UTC'
        }

# Additional missing helper functions
def display_ticket_details_enhanced(support, ticket_id):
    """Display enhanced ticket details"""
    try:
        ticket = support.get_ticket_details(ticket_id)
        
        print(f"\n🎫 TICKET #{ticket['ticket_id']}")
        print("="*50)
        print(f"📋 Title: {ticket['title']}")
        print(f"👤 Student: {ticket['student_id']}")
        print(f"📊 Status: {ticket['status']}")
        print(f"🔥 Priority: {ticket['priority']}")
        print(f"📂 Category: {ticket['category']}")
        print(f"📅 Created: {ticket['created_datetime']}")
        
        if ticket.get('assigned_to'):
            print(f"👨‍💼 Assigned to: {ticket['assigned_to']}")
        
        if ticket.get('estimated_resolution'):
            print(f"⏰ Est. Resolution: {ticket['estimated_resolution']}")
        
        if ticket.get('sentiment'):
            sentiment_emoji = {'positive': '😊', 'neutral': '😐', 'negative': '😞', 'frustrated': '😤'}
            print(f"😊 Sentiment: {sentiment_emoji.get(ticket['sentiment'], '😐')} {ticket['sentiment']}")
        
        if ticket.get('tags'):
            try:
                tags = json.loads(ticket['tags']) if isinstance(ticket['tags'], str) else ticket['tags']
                if tags:
                    print(f"🏷️ Tags: {', '.join(tags)}")
            except (json.JSONDecodeError, TypeError):
                pass
        
        print(f"\n📝 Description:")
        print(ticket['description'])
        
        # Attachments
        attachments = ticket.get('attachments', [])
        if attachments:
            print(f"\n📎 Attachments ({len(attachments)}):")
            for att in attachments:
                size_mb = att['file_size'] / (1024 * 1024)
                print(f"  📄 {att['original_filename']} ({size_mb:.1f}MB)")
        
        # Responses
        responses = ticket.get('responses', [])
        if responses:
            print(f"\n💬 Responses ({len(responses)}):")
            for response in responses:
                auto_tag = " 🤖" if response.get('is_auto_generated') else ""
                internal_tag = " 🔒" if response.get('is_internal') else ""
                print(f"\n[{response['response_datetime']}] {response['responder_role']}{auto_tag}{internal_tag}:")
                print(f"  {response['response_text']}")
    
    except Exception as e:
        print(f"❌ Error displaying ticket: {e}")

def view_my_tickets_enhanced(support):
    """View student's own tickets with enhanced filtering"""
    try:
        print("\n🎫 MY SUPPORT TICKETS")
        print("="*50)
        
        # Get student ID from auth
        from university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        
        # Access auth through the global variable or support instance
        import sys
        auth = getattr(sys.modules.get('src.core.services.student_support'), 'auth', None)
        if not auth or not auth.current_user:
            print("❌ You must be logged in to view tickets.")
            conn.close()
            return
        
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            print("❌ No student ID associated with your account.")
            return
        
        student_id = result[0]
        
        # Filter options
        print("📊 Filter Options:")
        print("1. All tickets")
        print("2. Open tickets")
        print("3. In Progress tickets")
        print("4. Resolved tickets")
        print("5. Search tickets")
        
        choice = input("\nSelect filter: ").strip()
        
        filters = {}
        
        if choice == '2':
            filters['status'] = 'Open'
        elif choice == '3':
            filters['status'] = 'In Progress'
        elif choice == '4':
            filters['status'] = 'Resolved'
        elif choice == '5':
            search_query = input("Enter search query: ").strip()
            if search_query:
                filters['search'] = search_query
        
        # Get tickets
        try:
            result = support.get_student_tickets(student_id, filters, page=1, per_page=20)
            tickets = result['tickets']
        except Exception as e:
            print(f"❌ Error retrieving tickets: {e}")
            return
        
        if not tickets:
            print("📭 No tickets found with the selected filters.")
            return
        
        # Display tickets
        print(f"\n🎫 Found {result['total_count']} tickets:")
        print("="*80)
        
        for ticket in tickets:
            status_emoji = {'Open': '🟢', 'In Progress': '⏳', 'Resolved': '✅', 'Closed': '🔒'}.get(ticket['status'], '❓')
            priority_emoji = {'Critical': '🔴', 'Urgent': '🟠', 'High': '🟡', 'Medium': '🔵', 'Low': '🟢'}.get(ticket['priority'], '⚪')
            
            print(f"{status_emoji} #{ticket['ticket_id']} - {ticket['title']}")
            print(f"   📂 {ticket['category']} | {priority_emoji} {ticket['priority']} | 📅 {ticket['created_datetime']}")
            
            if ticket.get('assigned_to'):
                print(f"   👨‍💼 Assigned to: {ticket['assigned_to']}")
            
            print()
        
        # View specific ticket
        if tickets:
            ticket_choice = input(f"View ticket details (enter ticket #) or press Enter to go back: ").strip()
            if ticket_choice.isdigit():
                ticket_id = int(ticket_choice)
                if any(t['ticket_id'] == ticket_id for t in tickets):
                    display_ticket_details_enhanced(support, ticket_id)
                else:
                    print("❌ Ticket not found in current list.")
    
    except Exception as e:
        print(f"❌ Error viewing tickets: {e}")
    
    input("\nPress Enter to continue...")

def use_ticket_template(support):
    """Create ticket using a template"""
    try:
        print("\n📋 USE TICKET TEMPLATE")
        print("="*50)
        
        templates = support.get_ticket_templates()
        
        if not templates:
            print("📭 No ticket templates available.")
            return
        
        print("📋 Available Templates:")
        for i, template in enumerate(templates, 1):
            print(f"{i}. {template['name']}")
            print(f"   📂 Category: {template['category']} | 🔥 Priority: {template['priority']}")
            print(f"   📈 Used {template.get('usage_count', 0)} times")
            print()
        
        choice = input(f"Select template (1-{len(templates)}): ").strip()
        
        if not choice.isdigit() or not 1 <= int(choice) <= len(templates):
            print("❌ Invalid choice.")
            return
        
        template = templates[int(choice) - 1]
        
        # Get student ID
        from university_system.infrastructure.database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        
        # Access auth
        import sys
        auth = getattr(sys.modules.get('src.core.services.student_support'), 'auth', None)
        if not auth or not auth.current_user:
            print("❌ You must be logged in to create tickets.")
            conn.close()
            return
        
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            print("❌ No student ID associated with your account.")
            return
        
        student_id = result[0]
        
        print(f"\n📋 Using template: {template['name']}")
        print("="*50)
        
        # Pre-fill from template
        title = template['title_template']
        description = template['description_template']
        category = template['category']
        priority = template['priority']
        
        print(f"Title: {title}")
        print(f"Category: {category}")
        print(f"Priority: {priority}")
        print(f"\nDescription:\n{description}")
        
        # Allow customization
        print("\n🔧 Customize Template:")
        custom_title = input(f"Custom title (or press Enter to keep '{title}'): ").strip()
        if custom_title:
            title = custom_title
        
        print("Additional description (press Enter twice to finish):")
        additional_lines = []
        while True:
            line = input()
            if not line and (not additional_lines or not additional_lines[-1]):
                break
            additional_lines.append(line)
        
        if additional_lines:
            description += "\n\n" + '\n'.join(additional_lines)
        
        # Create ticket
        print("\n🎫 Creating ticket from template...")
        ticket_id = support.create_support_ticket(
            student_id, title, description, category, priority,
            template_id=template['template_id']
        )
        
        print(f"✅ Support ticket #{ticket_id} created successfully from template!")
        
        # View ticket details
        view_choice = input("\nView ticket details? (y/n): ").lower()
        if view_choice == 'y':
            display_ticket_details_enhanced(support, ticket_id)
    
    except Exception as e:
        print(f"❌ Error using template: {e}")
    
    input("\nPress Enter to continue...")

# Module-level helper functions exposed for GUI/CLI integrations
def validate_ticket_permissions(ticket, current_user):
    """Validate if user has permission to access ticket"""
    if current_user['role'] in ('staff', 'admin'):
        return True

    if current_user['role'] == 'student':
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (current_user['id'],))
        result = cursor.fetchone()
        conn.close()

        if result and result[0] == ticket['student_id']:
            return True

    return False


def format_ticket_status_display(status):
    """Format ticket status for display with emoji"""
    status_emojis = {
        'Open': '🔓',
        'In Progress': '⏳',
        'Resolved': '✅',
        'Closed': '🔒',
        'Escalated': '🚨',
        'On Hold': '⏸️'
    }
    return f"{status_emojis.get(status, '❓')} {status}"


def format_priority_display(priority):
    """Format ticket priority for display with emoji"""
    priority_emojis = {
        'Critical': '🔴',
        'Urgent': '🟠',
        'High': '🟡',
        'Medium': '🔵',
        'Low': '🟢'
    }
    return f"{priority_emojis.get(priority, '⚪')} {priority}"


def format_file_size(size_bytes):
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0B"

    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1

    return f"{size_bytes:.1f}{size_names[i]}"


def truncate_text(text, max_length=100):
    """Truncate text to specified length with ellipsis"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


def handle_support_error(error, context=""):
    """Standard error handling for support operations"""
    error_msg = str(error)

    if "PermissionError" in str(type(error)):
        return f"❌ Permission denied: {error_msg}"
    elif "ValueError" in str(type(error)):
        return f"❌ Invalid input: {error_msg}"
    elif "FileNotFoundError" in str(type(error)):
        return f"❌ File not found: {error_msg}"
    else:
        logger.error(f"Unexpected error in {context}: {error}")
        return f"❌ An unexpected error occurred. Please try again or contact support."


# Patch for the EnhancedStudentSupport class to use safe preferences method
def patch_enhanced_student_support():
    """Patch the EnhancedStudentSupport class with the safe preferences method"""
    try:
        # Import the class
        from university_system.modules.domain.student_affairs.services.student_support import EnhancedStudentSupport
        
        # Replace the problematic method
        EnhancedStudentSupport.get_user_preferences = lambda self, user_id=None: get_user_preferences_safe(self, user_id)
        
        print("✅ Patched EnhancedStudentSupport.get_user_preferences method")
        
    except ImportError as e:
        print(f"⚠️ Could not patch EnhancedStudentSupport class: {e}")

# Function to apply all fixes
def apply_student_support_fixes():
    """Apply all the fixes for the student support system"""
    print("🔧 Applying student support system fixes...")
    
    # Fix database schema
    fix_user_preferences_table()
    
    # Patch the class method
    patch_enhanced_student_support()
    
    print("✅ All fixes applied successfully!")

# Integration with existing CLI
def display_support_menu():
    """Enhanced version of the support menu with new features"""
    global auth
    
    if auth is None:
        from university_system.infrastructure.auth.user_authentication import UserAuth
        try:
            auth = UserAuth()
        except Exception as e:
            print(f"Error initializing authentication system: {e}")
            return
    
    # Initialize enhanced support system
    try:
        config = SupportConfig()
        support = EnhancedStudentSupport(config)
    except Exception as e:
        print(f"Error initializing enhanced student support system: {e}")
        return
    
    while True:
        print("\n" + "="*60)
        print("🎓 ENHANCED STUDENT SUPPORT PORTAL")
        print("="*60)
        
        if not auth or not auth.current_user:
            print("❌ You must be logged in to access the support portal.")
            break
        
        user_role = auth.current_user['role']
        print(f"👤 Logged in as: {auth.current_user['username']} ({user_role})")
        
        options = []
        option_num = 1
        
        # Dashboard
        print(f"{option_num}. 📊 View Dashboard")
        options.append('dashboard')
        option_num += 1
        
        # Common features
        print(f"{option_num}. 🔍 Advanced Search")
        options.append('advanced_search')
        option_num += 1
        
        print(f"{option_num}. ❓ Browse FAQs")
        options.append('view_faqs')
        option_num += 1
        
        print(f"{option_num}. 📚 Knowledge Base")
        options.append('knowledge_base')
        option_num += 1
        
        print(f"{option_num}. 📋 Support Resources")
        options.append('view_resources')
        option_num += 1
        
        # Student features
        if user_role == 'student':
            print(f"{option_num}. 🎫 Create Support Ticket")
            options.append('create_ticket')
            option_num += 1
            
            print(f"{option_num}. 📋 My Support Tickets")
            options.append('my_tickets')
            option_num += 1
            
            print(f"{option_num}. 📋 Use Ticket Template")
            options.append('use_template')
            option_num += 1
        
        # Staff features
        if user_role in ('staff', 'admin'):
            print(f"{option_num}. 🎫 All Support Tickets")
            options.append('all_tickets')
            option_num += 1
            
            print(f"{option_num}. 📊 Generate Reports")
            options.append('reports')
            option_num += 1
            
            print(f"{option_num}. 🔧 Manage Templates")
            options.append('manage_templates')
            option_num += 1
            
            print(f"{option_num}. 📝 Manage Knowledge Base")
            options.append('manage_kb')
            option_num += 1
            
            print(f"{option_num}. 🔄 Bulk Operations")
            options.append('bulk_operations')
            option_num += 1
            
            print(f"{option_num}. 📤 Export Data")
            options.append('export_data')
            option_num += 1
        
        # Settings and preferences
        print(f"{option_num}. ⚙️ Preferences")
        options.append('preferences')
        option_num += 1
        
        print(f"{option_num}. 🔔 Notifications")
        options.append('notifications')
        option_num += 1
        
        print(f"{option_num}. ↩️ Return to Main Menu")
        
        print("\n" + "-"*60)
        choice = input("Enter your choice: ").strip()
        
        if choice.isdigit() and 1 <= int(choice) <= len(options) + 1:
            idx = int(choice) - 1
            if idx == len(options):
                break
            
            action = options[idx]
            
            try:
                if action == 'dashboard':
                    display_dashboard(support)
                elif action == 'advanced_search':
                    perform_advanced_search(support)
                elif action == 'view_faqs':
                    display_enhanced_faqs(support)
                elif action == 'knowledge_base':
                    browse_knowledge_base(support)
                elif action == 'view_resources':
                    display_enhanced_resources(support)
                elif action == 'create_ticket':
                    create_enhanced_ticket(support)
                elif action == 'my_tickets':
                    view_my_tickets_enhanced(support)
                elif action == 'use_template':
                    use_ticket_template(support)
                elif action == 'all_tickets':
                    view_all_tickets_enhanced(support)
                elif action == 'reports':
                    generate_reports_menu(support)
                elif action == 'manage_templates':
                    manage_templates_menu(support)
                elif action == 'manage_kb':
                    manage_knowledge_base_menu(support)
                elif action == 'bulk_operations':
                    bulk_operations_menu(support)
                elif action == 'export_data':
                    export_data_menu(support)
                elif action == 'preferences':
                    manage_preferences(support)
                elif action == 'notifications':
                    view_notifications(support)
            
            except Exception as e:
                print(f"\n❌ Error: {e}")
                input("Press Enter to continue...")
        
        else:
            print("❌ Invalid choice. Please try again.")

# Enhanced CLI functions (simplified for brevity)
def display_dashboard(support):
    """Display user dashboard"""
    try:
        dashboard_data = support.get_dashboard_data(auth.current_user['role'], auth.current_user['id'])
        
        print("\n📊 DASHBOARD")
        print("="*50)
        
        if auth.current_user['role'] == 'student':
            # Student dashboard
            stats = dashboard_data.get('ticket_stats', {})
            print(f"🎫 Your Tickets: Open: {stats.get('Open', 0)}, In Progress: {stats.get('In Progress', 0)}, Resolved: {stats.get('Resolved', 0)}")
            
            print("\n📋 Recent Tickets:")
            for ticket in dashboard_data.get('recent_tickets', [])[:5]:
                print(f"  #{ticket['ticket_id']} - {ticket['title']} ({ticket['status']})")
            
            print("\n⭐ Featured Resources:")
            for resource in dashboard_data.get('featured_resources', [])[:3]:
                print(f"  📄 {resource['title']} - {resource['description'][:50]}...")
        
        else:
            # Staff dashboard
            stats = dashboard_data.get('assigned_stats', {})
            print(f"🎫 Assigned Tickets: Open: {stats.get('Open', 0)}, In Progress: {stats.get('In Progress', 0)}")
            
            metrics = dashboard_data.get('performance_metrics', {})
            print(f"📈 Performance (30 days): {metrics.get('total_tickets_month', 0)} tickets, {metrics.get('avg_resolution_time', 0)} days avg resolution")
            
            print("\n🚨 High Priority Tickets:")
            for ticket in dashboard_data.get('priority_tickets', [])[:5]:
                print(f"  #{ticket['ticket_id']} - {ticket['title']} ({ticket['priority']})")
        
        # Notifications
        notifications = dashboard_data.get('notifications', [])
        if notifications:
            print(f"\n🔔 Recent Notifications ({len(notifications)}):")
            for notif in notifications[:3]:
                status = "📫" if notif['is_read'] else "📬"
                print(f"  {status} {notif['title']}")
        
    except Exception as e:
        print(f"Error loading dashboard: {e}")
    
    input("\nPress Enter to continue...")

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

def create_enhanced_ticket(support):
    """Create a new ticket with enhanced features"""
    try:
        print("\n🎫 CREATE SUPPORT TICKET")
        print("="*40)
        
        # Get student ID
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            print("❌ No student ID associated with your account.")
            return
        
        student_id = result[0]
        
        # Show templates option
        templates = support.get_ticket_templates()
        if templates:
            print("📋 Available Templates:")
            print("0. Create from scratch")
            for i, template in enumerate(templates, 1):
                print(f"{i}. {template['name']} ({template['category']})")
            
            template_choice = input("\nSelect template (0 for scratch): ").strip()
            
            if template_choice.isdigit() and 1 <= int(template_choice) <= len(templates):
                template = templates[int(template_choice) - 1]
                title = template['title_template']
                description = template['description_template']
                category = template['category']
                priority = template['priority']
                
                print(f"\n📝 Using template: {template['name']}")
                print("You can modify the pre-filled content:")
                
                title = input(f"Title [{title}]: ").strip() or title
                print("Description (press Enter twice to finish):")
                print(f"Current: {description}")
                print("Additional/Modified content:")
                
                lines = []
                while True:
                    line = input()
                    if not line and (not lines or not lines[-1]):
                        break
                    lines.append(line)
                
                if lines:
                    description = '\n'.join(lines)
            else:
                # Create from scratch
                title = input("Title: ").strip()
                if not title:
                    print("❌ Title is required.")
                    return
                
                print("Description (press Enter twice to finish):")
                lines = []
                while True:
                    line = input()
                    if not line and (not lines or not lines[-1]):
                        break
                    lines.append(line)
                
                description = '\n'.join(lines)
                if not description:
                    print("❌ Description is required.")
                    return
                
                # Category selection with AI suggestion
                suggested_category = support._suggest_category(title + " " + description)
                
                print("\nCategories:")
                for i, cat in enumerate(SUPPORT_CATEGORIES, 1):
                    marker = " 🤖 (Suggested)" if cat == suggested_category else ""
                    print(f"{i}. {cat}{marker}")
                
                category_choice = input(f"\nSelect category (1-{len(SUPPORT_CATEGORIES)}): ").strip()
                try:
                    category_index = int(category_choice) - 1
                    if not 0 <= category_index < len(SUPPORT_CATEGORIES):
                        print("❌ Invalid category.")
                        return
                    category = SUPPORT_CATEGORIES[category_index]
                except ValueError:
                    print("❌ Invalid category.")
                    return
                
                # Priority selection
                print("\nPriorities:")
                for i, pri in enumerate(TICKET_PRIORITIES, 1):
                    print(f"{i}. {pri}")
                
                priority_choice = input(f"\nSelect priority (1-{len(TICKET_PRIORITIES)}) [default: Medium]: ").strip()
                if priority_choice:
                    try:
                        priority_index = int(priority_choice) - 1
                        if 0 <= priority_index < len(TICKET_PRIORITIES):
                            priority = TICKET_PRIORITIES[priority_index]
                        else:
                            priority = 'Medium'
                    except ValueError:
                        priority = 'Medium'
                else:
                    priority = 'Medium'
        else:
            # No templates available, create from scratch
            title = input("Title: ").strip()
            if not title:
                print("❌ Title is required.")
                return
            
            print("Description (press Enter twice to finish):")
            lines = []
            while True:
                line = input()
                if not line and (not lines or not lines[-1]):
                    break
                lines.append(line)
            
            description = '\n'.join(lines)
            if not description:
                print("❌ Description is required.")
                return
            
            # Category and priority selection (same as above)
            category = 'Other'  # Simplified for this example
            priority = 'Medium'
        
        # Tags
        tags_input = input("\nTags (comma-separated, optional): ").strip()
        tags = [tag.strip() for tag in tags_input.split(',')] if tags_input else []
        
        # File attachments
        attachments = []
        attach_more = input("\nAdd file attachment? (y/n): ").lower() == 'y'
        while attach_more:
            file_path = input("File path: ").strip()
            if file_path and os.path.exists(file_path):
                try:
                    with open(file_path, 'rb') as f:
                        file_data = f.read()
                    
                    attachments.append({
                        'filename': os.path.basename(file_path),
                        'data': file_data,
                        'mime_type': mimetypes.guess_type(file_path)[0]
                    })
                    print(f"✅ Added {os.path.basename(file_path)}")
                except Exception as e:
                    print(f"❌ Error reading file: {e}")
            else:
                print("❌ File not found.")
            
            attach_more = input("Add another file? (y/n): ").lower() == 'y'
        
        # Create ticket
        print("\n🎫 Creating ticket...")
        ticket_id = support.create_support_ticket(
            student_id, title, description, category, priority,
            attachments=attachments, tags=tags
        )
        
        print(f"✅ Support ticket #{ticket_id} created successfully!")
        
        # Show ticket details
        view_choice = input("\nView ticket details? (y/n): ").lower()
        if view_choice == 'y':
            display_ticket_details_enhanced(support, ticket_id)
    
    except Exception as e:
        print(f"❌ Error creating ticket: {e}")
    
    input("\nPress Enter to continue...")

def display_ticket_details_enhanced(support, ticket_id):
    """Display enhanced ticket details"""
    try:
        ticket = support.get_ticket_details(ticket_id)
        
        print(f"\n🎫 TICKET #{ticket['ticket_id']}")
        print("="*50)
        print(f"📋 Title: {ticket['title']}")
        print(f"👤 Student: {ticket['student_id']}")
        print(f"📊 Status: {ticket['status']}")
        print(f"🔥 Priority: {ticket['priority']}")
        print(f"📁 Category: {ticket['category']}")
        print(f"📅 Created: {ticket['created_datetime']}")
        
        if ticket.get('assigned_to'):
            print(f"👨‍💼 Assigned to: {ticket['assigned_to']}")
        
        if ticket.get('estimated_resolution'):
            print(f"⏰ Est. Resolution: {ticket['estimated_resolution']}")
        
        if ticket.get('sentiment'):
            sentiment_emoji = {'positive': '😊', 'neutral': '😐', 'negative': '😞', 'frustrated': '😤'}
            print(f"😊 Sentiment: {sentiment_emoji.get(ticket['sentiment'], '😐')} {ticket['sentiment']}")
        
        if ticket.get('tags'):
            tags = json.loads(ticket['tags']) if isinstance(ticket['tags'], str) else ticket['tags']
            if tags:
                print(f"🏷️ Tags: {', '.join(tags)}")
        
        print(f"\n📝 Description:")
        print(ticket['description'])
        
        # Attachments
        attachments = support.get_ticket_attachments(ticket_id)
        if attachments:
            print(f"\n📎 Attachments ({len(attachments)}):")
            for att in attachments:
                size_mb = att['file_size'] / (1024 * 1024)
                print(f"  📄 {att['original_filename']} ({size_mb:.1f}MB)")
        
        # Responses
        responses = ticket.get('responses', [])
        if responses:
            print(f"\n💬 Responses ({len(responses)}):")
            for response in responses:
                auto_tag = " 🤖" if response.get('is_auto_generated') else ""
                internal_tag = " 🔒" if response.get('is_internal') else ""
                print(f"\n[{response['response_datetime']}] {response['responder_role']}{auto_tag}{internal_tag}:")
                print(f"  {response['response_text']}")
        
        # Actions menu
        print(f"\n🔧 Actions:")
        print("1. Add response")
        if auth.current_user['role'] in ('staff', 'admin'):
            print("2. Update status")
            print("3. Add internal note")
            print("4. View full history")
        print("5. Download attachment")
        print("6. Back")
        
        action = input("\nChoose action: ").strip()
        
        if action == '1':
            add_response_enhanced(support, ticket_id)
        elif action == '2' and auth.current_user['role'] in ('staff', 'admin'):
            update_status_enhanced(support, ticket_id)
        elif action == '3' and auth.current_user['role'] in ('staff', 'admin'):
            add_internal_note(support, ticket_id)
        elif action == '4' and auth.current_user['role'] in ('staff', 'admin'):
            view_ticket_history(support, ticket_id)
        elif action == '5' and attachments:
            download_attachment_menu(support, attachments)
        elif action == '6':
            return
        else:
            print("❌ Invalid choice or insufficient permissions.")
    
    except Exception as e:
        print(f"❌ Error displaying ticket: {e}")

def add_response_enhanced(support, ticket_id):
    """Add response with template support"""
    try:
        # Get response templates
        templates = support.get_response_templates()
        
        if templates and auth.current_user['role'] in ('staff', 'admin'):
            print("\n📝 Response Templates:")
            print("0. Write custom response")
            for i, template in enumerate(templates[:10], 1):  # Show first 10
                print(f"{i}. {template['name']}")
            
            template_choice = input("\nSelect template (0 for custom): ").strip()
            
            if template_choice.isdigit() and 1 <= int(template_choice) <= len(templates):
                template = templates[int(template_choice) - 1]
                response_text = template['content']
                print(f"\nUsing template: {template['name']}")
                print(f"Template content:\n{response_text}")
                
                additional = input("\nAdditional text (optional): ").strip()
                if additional:
                    response_text += f"\n\n{additional}"
                
                template_id = template['template_id']
            else:
                response_text = input("\nEnter your response: ").strip()
                template_id = None
        else:
            response_text = input("\nEnter your response: ").strip()
            template_id = None
        
        if not response_text:
            print("❌ Response cannot be empty.")
            return
        
        # Internal note option for staff
        is_internal = False
        if auth.current_user['role'] in ('staff', 'admin'):
            is_internal = input("Internal note (visible only to staff)? (y/n): ").lower() == 'y'
        
        # Add response
        support.add_ticket_response(ticket_id, response_text, template_id, is_internal)
        print("✅ Response added successfully!")
        
    except Exception as e:
        print(f"❌ Error adding response: {e}")

def generate_reports_menu(support):
    """Generate reports menu"""
    try:
        print("\n📊 GENERATE REPORTS")
        print("="*40)
        print("1. Ticket Summary Report")
        print("2. Performance Report")
        print("3. Satisfaction Report")
        print("4. Category Analysis Report")
        print("5. Back")
        
        choice = input("\nSelect report type: ").strip()
        
        if choice == '5':
            return
        
        report_types = {
            '1': 'ticket_summary',
            '2': 'performance',
            '3': 'satisfaction',
            '4': 'category_analysis'
        }
        
        report_type = report_types.get(choice)
        if not report_type:
            print("❌ Invalid choice.")
            return
        
        # Date range
        print("\nDate Range:")
        start_date = input("Start date (YYYY-MM-DD) [30 days ago]: ").strip()
        if not start_date:
            start_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        
        end_date = input("End date (YYYY-MM-DD) [today]: ").strip()
        if not end_date:
            end_date = datetime.datetime.now().strftime('%Y-%m-%d')
        
        date_range = {'start': start_date, 'end': end_date}
        
        print(f"\n📈 Generating {report_type} report...")
        report_data = support.generate_reports(report_type, date_range)
        
        # Display report summary
        print(f"\n📋 REPORT: {report_type.upper()}")
        print("="*50)
        
        if report_type == 'ticket_summary':
            print(f"📊 Total Tickets: {report_data['total_tickets']}")
            print(f"📈 Status Breakdown: {report_data['status_breakdown']}")
            print(f"📁 Category Breakdown: {report_data['category_breakdown']}")
        
        elif report_type == 'performance':
            stats = report_data['resolution_stats']
            print(f"⏱️ Average Resolution Time: {stats['avg_hours']} hours")
            print(f"✅ Resolved Tickets: {stats['resolved_count']}")
            print(f"👥 Staff Performance: {len(report_data['staff_performance'])} staff members")
        
        elif report_type == 'satisfaction':
            print(f"⭐ Average Rating: {report_data['avg_rating']}/5")
            print(f"📊 Response Rate: {report_data['response_rate']}%")
            print(f"📝 Total Responses: {report_data['total_responses']}")
        
        # Export option
        export_choice = input("\nExport report? (y/n): ").lower()
        if export_choice == 'y':
            filename = f"{report_type}_report_{start_date}_to_{end_date}.json"
            with open(filename, 'w') as f:
                json.dump(report_data, f, indent=2)
            print(f"✅ Report exported to {filename}")
    
    except Exception as e:
        print(f"❌ Error generating report: {e}")
    
    input("\nPress Enter to continue...")

def manage_preferences(support):
    """Manage user preferences"""
    try:
        print("\n⚙️ USER PREFERENCES")
        print("="*40)
        
        # Get current preferences
        current_prefs = support.get_user_preferences()
        
        print("Current Settings:")
        print(f"📧 Email Notifications: {'✅' if current_prefs.get('email_notifications', True) else '❌'}")
        print(f"🔔 In-App Notifications: {'✅' if current_prefs.get('in_app_notifications', True) else '❌'}")
        print(f"📱 Push Notifications: {'✅' if current_prefs.get('push_notifications', True) else '❌'}")
        print(f"📅 Digest Frequency: {current_prefs.get('digest_frequency', 'daily')}")
        print(f"🎨 Theme: {current_prefs.get('theme', 'light')}")
        print(f"🌍 Language: {current_prefs.get('language', 'en')}")
        print(f"🕐 Timezone: {current_prefs.get('timezone', 'UTC')}")
        
        print("\nWhat would you like to change?")
        print("1. Email Notifications")
        print("2. In-App Notifications") 
        print("3. Push Notifications")
        print("4. Digest Frequency")
        print("5. Theme")
        print("6. Language")
        print("7. Timezone")
        print("8. Save and Exit")
        print("9. Cancel")
        
        updated_prefs = current_prefs.copy()
        
        while True:
            choice = input("\nSelect option: ").strip()
            
            if choice == '1':
                updated_prefs['email_notifications'] = input("Enable email notifications? (y/n): ").lower() == 'y'
            elif choice == '2':
                updated_prefs['in_app_notifications'] = input("Enable in-app notifications? (y/n): ").lower() == 'y'
            elif choice == '3':
                updated_prefs['push_notifications'] = input("Enable push notifications? (y/n): ").lower() == 'y'
            elif choice == '4':
                print("Digest frequency options: immediate, daily, weekly")
                freq = input("Enter frequency: ").strip()
                if freq in ['immediate', 'daily', 'weekly']:
                    updated_prefs['digest_frequency'] = freq
            elif choice == '5':
                print("Theme options: light, dark")
                theme = input("Enter theme: ").strip()
                if theme in ['light', 'dark']:
                    updated_prefs['theme'] = theme
            elif choice == '6':
                updated_prefs['language'] = input("Enter language code (e.g., en, es, fr): ").strip() or 'en'
            elif choice == '7':
                updated_prefs['timezone'] = input("Enter timezone (e.g., UTC, EST, PST): ").strip() or 'UTC'
            elif choice == '8':
                # Save preferences
                support.update_user_preferences(updated_prefs)
                print("✅ Preferences saved successfully!")
                break
            elif choice == '9':
                print("❌ Changes cancelled.")
                break
            else:
                print("❌ Invalid choice.")
    
    except Exception as e:
        print(f"❌ Error managing preferences: {e}")
    
    input("\nPress Enter to continue...")

def view_notifications(support):
    """View user notifications"""
    try:
        print("\n🔔 NOTIFICATIONS")
        print("="*40)
        
        # Get notifications from dashboard data
        dashboard_data = support.get_dashboard_data(auth.current_user['role'], auth.current_user['id'])
        notifications = dashboard_data.get('notifications', [])
        
        if not notifications:
            print("📭 No notifications.")
            return
        
        print(f"📬 You have {len(notifications)} notifications:")
        
        for i, notif in enumerate(notifications, 1):
            status_icon = "📫" if notif['is_read'] else "📬"
            print(f"\n{i}. {status_icon} {notif['title']}")
            print(f"   📝 {notif['message']}")
            print(f"   📅 {notif['created']}")
            print(f"   🏷️ Type: {notif['type']}")
        
        # Mark as read option
        mark_read = input(f"\nMark all as read? (y/n): ").lower()
        if mark_read == 'y':
            # In a real implementation, this would update the database
            print("✅ All notifications marked as read.")
    
    except Exception as e:
        print(f"❌ Error viewing notifications: {e}")
    
    input("\nPress Enter to continue...")

# Additional helper functions for enhanced features
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
