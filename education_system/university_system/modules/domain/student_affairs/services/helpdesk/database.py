from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def init_helpdesk_db() -> bool:
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create support_tickets table with enhanced fields
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            assigned_to INTEGER,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT,
            status TEXT DEFAULT 'open',
            priority TEXT DEFAULT 'medium',
            impact TEXT DEFAULT 'low',
            urgency TEXT DEFAULT 'low',
            source TEXT DEFAULT 'web',
            resolution TEXT,
            satisfaction_rating INTEGER,
            satisfaction_feedback TEXT,
            estimated_hours REAL,
            actual_hours REAL,
            due_date TEXT,
            resolved_at TEXT,
            first_response_at TEXT,
            last_activity_at TEXT,
            escalation_level INTEGER DEFAULT 0,
            tags TEXT,
            department TEXT,
            organization_id INTEGER,
            parent_ticket_id INTEGER,
            knowledge_base_articles TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (assigned_to) REFERENCES users (id),
            FOREIGN KEY (parent_ticket_id) REFERENCES support_tickets (ticket_id)
        )
        ''')

        # Create ticket_replies table with enhanced fields
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_replies (
            reply_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            user_id INTEGER,
            message TEXT NOT NULL,
            is_internal BOOLEAN DEFAULT 0,
            reply_type TEXT DEFAULT 'comment',
            time_spent REAL DEFAULT 0,
            created_at TEXT,
            edited_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')

        # Create ticket_attachments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_attachments (
            attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            reply_id INTEGER,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_size INTEGER,
            mime_type TEXT,
            file_hash TEXT,
            uploaded_by INTEGER,
            upload_path TEXT,
            created_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
            FOREIGN KEY (reply_id) REFERENCES ticket_replies (reply_id),
            FOREIGN KEY (uploaded_by) REFERENCES users (id)
        )
        ''')

        # Create ticket_assignments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_assignments (
            assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            assigned_from INTEGER,
            assigned_to INTEGER,
            assignment_reason TEXT,
            created_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
            FOREIGN KEY (assigned_from) REFERENCES users (id),
            FOREIGN KEY (assigned_to) REFERENCES users (id)
        )
        ''')

        # Create helpdesk_ticket_templates table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS helpdesk_ticket_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            subject_template TEXT,
            message_template TEXT,
            default_priority TEXT,
            default_impact TEXT,
            default_urgency TEXT,
            form_fields TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_by INTEGER,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''')

        # Create sla_policies table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sla_policies (
            sla_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            priority TEXT,
            impact TEXT,
            urgency TEXT,
            first_response_hours INTEGER,
            resolution_hours INTEGER,
            escalation_hours INTEGER,
            business_hours_only BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
        ''')

        # Create ticket_workflows table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_workflows (
            workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            trigger_type TEXT NOT NULL,
            trigger_conditions TEXT,
            actions TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_by INTEGER,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''')

        # Create ticket_time_tracking table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_time_tracking (
            time_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            user_id INTEGER,
            start_time TEXT,
            end_time TEXT,
            duration_minutes INTEGER,
            description TEXT,
            billable BOOLEAN DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')

        # Create ticket_escalations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_escalations (
            escalation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            escalation_level INTEGER,
            escalated_to INTEGER,
            escalated_by INTEGER,
            escalation_reason TEXT,
            resolved BOOLEAN DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
            FOREIGN KEY (escalated_to) REFERENCES users (id),
            FOREIGN KEY (escalated_by) REFERENCES users (id)
        )
        ''')

        # Create ticket_links table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_links (
            link_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            linked_ticket_id INTEGER,
            link_type TEXT,
            created_by INTEGER,
            created_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
            FOREIGN KEY (linked_ticket_id) REFERENCES support_tickets (ticket_id),
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
        ''')

        # Create ticket_audit_log table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ticket_audit_log (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            user_id INTEGER,
            action TEXT NOT NULL,
            old_values TEXT,
            new_values TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at TEXT,
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')

        # Create knowledge_base table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS knowledge_base (
            article_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT,
            tags TEXT,
            author_id INTEGER,
            status TEXT DEFAULT 'draft',
            views INTEGER DEFAULT 0,
            helpful_votes INTEGER DEFAULT 0,
            unhelpful_votes INTEGER DEFAULT 0,
            search_keywords TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (author_id) REFERENCES users (id)
        )
        ''')

        # Create departments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS departments (
            dept_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            manager_id INTEGER,
            email TEXT,
            sla_policy_id INTEGER,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (manager_id) REFERENCES users (id),
            FOREIGN KEY (sla_policy_id) REFERENCES sla_policies (sla_id)
        )
        ''')

        # Create organizations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS organizations (
            org_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            domain TEXT,
            contact_email TEXT,
            phone TEXT,
            address TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
        ''')

        # Create saved_searches table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_searches (
            search_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            search_criteria TEXT,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')

        conn.commit()
        conn.close()
        print("Enhanced helpdesk database initialized successfully!")

        # Initialize default data
        init_default_data()

    except sqlite3.Error as e:
        print(f"An error occurred while initializing the helpdesk database: {e}")

def init_default_data():
    """Initialize default SLA policies, templates, and workflows"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Insert default SLA policies
        cursor.execute("SELECT COUNT(*) FROM sla_policies")
        if cursor.fetchone()[0] == 0:
            default_slas = [
                ('Standard Low Priority', 'Standard SLA for low priority tickets', 'low', 'low', 'low', 24, 72, 48, 1, 1),
                ('Standard Medium Priority', 'Standard SLA for medium priority tickets', 'medium', 'medium', 'medium', 8, 48, 24, 1, 1),
                ('Standard High Priority', 'Standard SLA for high priority tickets', 'high', 'high', 'high', 2, 24, 8, 1, 1),
                ('Critical', 'SLA for critical issues', 'high', 'high', 'high', 1, 8, 4, 0, 1)
            ]

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for sla in default_slas:
                cursor.execute('''
                INSERT INTO sla_policies
                (name, description, priority, impact, urgency, first_response_hours,
                 resolution_hours, escalation_hours, business_hours_only, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', sla + (timestamp,))

        # Insert default ticket templates
        cursor.execute("SELECT COUNT(*) FROM helpdesk_ticket_templates")
        if cursor.fetchone()[0] == 0:
            default_templates = [
                ('Password Reset Request', 'Template for password reset requests', 'Account Access',
                 'Password Reset Request', 'I need to reset my password for:\n\nAccount: [ACCOUNT_NAME]\nReason: [REASON]\n\nAdditional details:\n[DETAILS]',
                 'medium', 'low', 'medium', '{"fields": [{"name": "account_name", "type": "text", "required": true}, {"name": "reason", "type": "select", "options": ["Forgot password", "Account locked", "Security concern"]}, {"name": "details", "type": "textarea", "required": false}]}'),

                ('Technical Issue Report', 'Template for technical problems', 'Technical Support',
                 'Technical Issue: [ISSUE_TYPE]', 'Issue Description:\n[DESCRIPTION]\n\nSteps to reproduce:\n1. [STEP_1]\n2. [STEP_2]\n3. [STEP_3]\n\nExpected behavior:\n[EXPECTED]\n\nActual behavior:\n[ACTUAL]\n\nBrowser/System info:\n[SYSTEM_INFO]',
                 'medium', 'medium', 'medium', '{"fields": [{"name": "issue_type", "type": "select", "options": ["Login problem", "Performance issue", "Feature not working", "Error message"]}, {"name": "description", "type": "textarea", "required": true}, {"name": "steps", "type": "textarea", "required": true}]}'),

                ('Financial Services Request', 'Template for financial inquiries', 'Financial Services',
                 'Financial Services: [REQUEST_TYPE]', 'Request Type: [REQUEST_TYPE]\n\nStudent ID: [STUDENT_ID]\n\nDetails:\n[DETAILS]\n\nUrgency: [URGENCY_REASON]',
                 'high', 'medium', 'high', '{"fields": [{"name": "request_type", "type": "select", "options": ["Payment plan", "Refund request", "Financial aid", "Billing inquiry"]}, {"name": "student_id", "type": "text", "required": true}, {"name": "amount", "type": "number", "required": false}]}')
            ]

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for template in default_templates:
                cursor.execute('''
                INSERT INTO helpdesk_ticket_templates
                (name, description, category, subject_template, message_template,
                 default_priority, default_impact, default_urgency, form_fields, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', template + (timestamp,))

        # Insert default departments
        cursor.execute("SELECT COUNT(*) FROM departments")
        if cursor.fetchone()[0] == 0:
            # Look up actual SLA policy IDs by name
            sla_ids = {}
            cursor.execute("SELECT sla_id, name FROM sla_policies")
            for row in cursor.fetchall():
                sla_ids[row[1]] = row[0]

            low_sla = sla_ids.get('Standard Low Priority')
            med_sla = sla_ids.get('Standard Medium Priority')
            high_sla = sla_ids.get('Standard High Priority')

            default_departments = [
                ('IT Support', 'Information Technology Support Department', None, 'itsupport@school.edu', low_sla),
                ('Academic Affairs', 'Academic Affairs Department', None, 'academic@school.edu', med_sla),
                ('Financial Services', 'Financial Services Department', None, 'finance@school.edu', high_sla),
                ('Student Services', 'Student Services Department', None, 'students@school.edu', med_sla)
            ]

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for dept in default_departments:
                cursor.execute('''
                INSERT INTO departments
                (name, description, manager_id, email, sla_policy_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', dept + (timestamp,))

        # Insert default workflows
        cursor.execute("SELECT COUNT(*) FROM ticket_workflows")
        if cursor.fetchone()[0] == 0:
            default_workflows = [
                ('Auto-assign IT tickets', 'Automatically assign technical support tickets to IT department',
                 'ticket_created', '{"category": "Technical Support"}',
                 '{"assign_to_department": "IT Support", "set_priority": "medium"}'),

                ('High priority escalation', 'Escalate high priority tickets after 2 hours',
                 'time_based', '{"priority": "high", "hours_without_response": 2}',
                 '{"escalate_to_manager": true, "send_notification": true}'),

                ('Auto-close resolved tickets', 'Auto-close tickets marked as resolved after 48 hours',
                 'time_based', '{"status": "resolved", "hours_inactive": 48}',
                 '{"change_status": "closed", "send_survey": true}')
            ]

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for workflow in default_workflows:
                cursor.execute('''
                INSERT INTO ticket_workflows
                (name, description, trigger_type, trigger_conditions, actions, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', workflow + (timestamp,))

        conn.commit()
        print("Default helpdesk data initialized successfully!")

    except sqlite3.Error as e:
        print(f"Error initializing default data: {e}")
    finally:
        conn.close()
