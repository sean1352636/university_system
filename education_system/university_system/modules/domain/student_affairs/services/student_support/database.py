"""
Database initialization and schema management for Student Support.

This module handles all database table creation, migrations, and
initialization of default data for the student support system.
"""

from education_system.university_system.infrastructure.database.db import sqlite3
import datetime
import json
import logging

from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from education_system.university_system.core.sql_safety import validate_identifier

from .config import SUPPORT_DB

logger = logging.getLogger(__name__)

def init_enhanced_db():
    """Initialize the enhanced support database with new tables."""
    try:
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()
        
        # Create original tables first
        _create_original_tables(cursor)
        
        # Create enhanced tables
        _create_enhanced_tables(cursor)
        
        # Initialize default data
        _initialize_default_data(cursor)
        
        conn.commit()
        conn.close()
        
        logger.info("Enhanced database initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize enhanced database: {e}")
        raise

def _create_original_tables(cursor):
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
                safe_col = validate_identifier(column_name, "column")
                cursor.execute('ALTER TABLE support_tickets ADD COLUMN ' + safe_col + ' ' + column_def)
                print(f"Added column '{column_name}' to support_tickets table")
            except Exception as e:
                print(f"Could not add column '{column_name}': {e}")
    
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

def _create_enhanced_tables(cursor):
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
        notification_type TEXT NOT NULL DEFAULT 'in_app',
        related_ticket_id INTEGER,
        is_read BOOLEAN DEFAULT 0,
        created_datetime TEXT NOT NULL,
        read_datetime TEXT,
        expires_at TEXT,
        data TEXT,  -- JSON data
        FOREIGN KEY (related_ticket_id) REFERENCES support_tickets (ticket_id)
    )
    ''')

    # Migrate notifications table if missing columns
    cursor.execute("PRAGMA table_info(notifications)")
    existing_cols = [col[1] for col in cursor.fetchall()]
    notifications_columns = {
        'user_id': 'TEXT',
        'title': 'TEXT',
        'message': 'TEXT',
        'notification_type': "TEXT NOT NULL DEFAULT 'in_app'",
        'related_ticket_id': 'INTEGER',
        'is_read': 'BOOLEAN DEFAULT 0',
        'created_datetime': "TEXT DEFAULT CURRENT_TIMESTAMP",
        'read_datetime': 'TEXT',
        'expires_at': 'TEXT',
        'data': 'TEXT',
    }
    for col_name, col_def in notifications_columns.items():
        if col_name not in existing_cols:
            try:
                safe_col = validate_identifier(col_name, "column")
                cursor.execute('ALTER TABLE notifications ADD COLUMN ' + safe_col + ' ' + col_def)
                logger.info(f"Added column '{col_name}' to notifications table")
            except Exception as e:
                logger.warning(f"Could not add column '{col_name}' to notifications: {e}")
    
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

    # Migration: Ensure audit_trail has all required columns
    cursor.execute("PRAGMA table_info(audit_trail)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    audit_trail_migrations = [
        ('old_values', 'TEXT'),
        ('new_values', 'TEXT'),
        ('ip_address', 'TEXT'),
        ('user_agent', 'TEXT'),
        ('duration', 'REAL'),
        ('error_message', 'TEXT'),
    ]

    for col_name, col_type in audit_trail_migrations:
        if col_name not in existing_columns:
            try:
                safe_col = validate_identifier(col_name, "column")
                cursor.execute('ALTER TABLE audit_trail ADD COLUMN ' + safe_col + ' ' + col_type)
                logger.info(f"Added missing column '{col_name}' to audit_trail table")
            except Exception as e:
                logger.warning(f"Could not add column '{col_name}' to audit_trail: {e}")

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

def _initialize_default_data(cursor):
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
    

