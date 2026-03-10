from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


def run_ticket_workflows(ticket_id, trigger_type, **kwargs):
    """Run automated workflows based on triggers"""
    conn = get_connection()
    cursor = conn.cursor()

    # Get active workflows for this trigger
    cursor.execute('''
    SELECT workflow_id, name, trigger_conditions, actions
    FROM ticket_workflows
    WHERE trigger_type = ? AND is_active = 1
    ''', (trigger_type,))

    workflows = cursor.fetchall()

    for workflow in workflows:
        workflow_id, name, conditions_json, actions_json = workflow

        try:
            conditions = json.loads(conditions_json) if conditions_json else {}
            actions = json.loads(actions_json) if actions_json else {}

            # Check if conditions are met
            if check_workflow_conditions(ticket_id, conditions, **kwargs):
                execute_workflow_actions(ticket_id, actions)
                print(f"Executed workflow: {name}")

        except json.JSONDecodeError:
            print(f"Error parsing workflow {name}")

    conn.close()

def check_workflow_conditions(ticket_id, conditions, **kwargs):
    """Check if workflow conditions are met"""
    conn = get_connection()
    cursor = conn.cursor()

    # Get ticket details
    cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
    ticket = cursor.fetchone()

    if not ticket:
        conn.close()
        return False

    # Convert to dict for easier access
    columns = [desc[0] for desc in cursor.description]
    ticket_dict = dict(zip(columns, ticket))

    # Check each condition
    for field, expected_value in conditions.items():
        if field in ticket_dict:
            if ticket_dict[field] != expected_value:
                conn.close()
                return False
        elif field in kwargs:
            if kwargs[field] != expected_value:
                conn.close()
                return False

    conn.close()
    return True

def execute_workflow_actions(ticket_id, actions):
    """Execute workflow actions"""
    conn = get_connection()
    cursor = conn.cursor()

    for action, value in actions.items():
        if action == 'assign_to_department':
            # Find available staff in department
            cursor.execute('''
            SELECT u.id FROM users u
            JOIN departments d ON u.department = d.name
            WHERE d.name = ? AND u.role IN ('staff', 'admin') AND u.is_active = 1
            ORDER BY u.last_login_at DESC LIMIT 1
            ''', (value,))

            staff = cursor.fetchone()
            if staff:
                cursor.execute('''
                UPDATE support_tickets
                SET assigned_to = ?, department = ?, updated_at = ?
                WHERE ticket_id = ?
                ''', (staff[0], value, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ticket_id))

        elif action == 'set_priority':
            cursor.execute('''
            UPDATE support_tickets
            SET priority = ?, updated_at = ?
            WHERE ticket_id = ?
            ''', (value, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ticket_id))

        elif action == 'change_status':
            cursor.execute('''
            UPDATE support_tickets
            SET status = ?, updated_at = ?
            WHERE ticket_id = ?
            ''', (value, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ticket_id))

        elif action == 'escalate_to_manager':
            if value:
                escalate_ticket(ticket_id, 'workflow_auto_escalation')

        elif action == 'send_survey':
            if value:
                from education_system.university_system.modules.domain.student_affairs.services.helpdesk.notifications import send_satisfaction_survey
                send_satisfaction_survey(ticket_id)

    conn.commit()
    conn.close()

def escalate_ticket(ticket_id, reason='manual'):
    """Escalate a ticket to higher level"""
    conn = get_connection()
    cursor = conn.cursor()

    # Get current ticket info
    cursor.execute('''
    SELECT assigned_to, department, escalation_level
    FROM support_tickets
    WHERE ticket_id = ?
    ''', (ticket_id,))

    ticket_info = cursor.fetchone()
    if not ticket_info:
        conn.close()
        return

    current_assigned, department, current_level = ticket_info
    new_level = current_level + 1

    # Find manager to escalate to
    escalate_to = None

    if department:
        cursor.execute('''
        SELECT manager_id FROM departments WHERE name = ?
        ''', (department,))
        dept_manager = cursor.fetchone()
        if dept_manager and dept_manager[0]:
            escalate_to = dept_manager[0]

    if not escalate_to:
        # Escalate to any admin
        cursor.execute('''
        SELECT id FROM users WHERE role = 'admin' AND is_active = 1 LIMIT 1
        ''')
        admin = cursor.fetchone()
        if admin:
            escalate_to = admin[0]

    if escalate_to:
        # Update ticket
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
        UPDATE support_tickets
        SET assigned_to = ?, escalation_level = ?, updated_at = ?
        WHERE ticket_id = ?
        ''', (escalate_to, new_level, now, ticket_id))

        # Record escalation
        cursor.execute('''
        INSERT INTO ticket_escalations
        (ticket_id, escalation_level, escalated_to, escalation_reason, created_at)
        VALUES (?, ?, ?, ?, ?)
        ''', (ticket_id, new_level, escalate_to, reason, now))

        conn.commit()
        print(f"Ticket #{ticket_id} escalated to level {new_level}")

    conn.close()

def log_ticket_action(ticket_id, user_id, action, old_values, new_values, ip_address=None, user_agent=None):
    """Log ticket actions for audit trail"""
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
    INSERT INTO ticket_audit_log
    (ticket_id, user_id, action, old_values, new_values, ip_address, user_agent, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (ticket_id, user_id, action, json.dumps(old_values), json.dumps(new_values),
          ip_address, user_agent, now))

    conn.commit()
    conn.close()
