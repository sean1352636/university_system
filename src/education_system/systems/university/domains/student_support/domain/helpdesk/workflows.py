from education_system.systems.university.infrastructure.database.db import get_connection
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


def run_ticket_workflows(ticket_id, trigger_type, **kwargs):
    """Run the active workflows for ``trigger_type`` on a ticket (each
    action through the ticket service, as the automated ``system`` actor)."""
    with get_connection() as conn:
        workflows = conn.execute('''
        SELECT workflow_id, name, trigger_conditions, actions
        FROM ticket_workflows
        WHERE trigger_type = ? AND is_active = 1
        ''', (trigger_type,)).fetchall()

    for workflow in workflows:
        workflow_id, name, conditions_json, actions_json = workflow

        try:
            conditions = json.loads(conditions_json) if conditions_json else {}
            actions = json.loads(actions_json) if actions_json else {}

            # Check if conditions are met
            if check_workflow_conditions(ticket_id, conditions, **kwargs):
                execute_workflow_actions(ticket_id, actions)
                logger.info("Executed workflow %s on ticket %s", name, ticket_id)

        except json.JSONDecodeError:
            logger.warning("Workflow %s has unreadable conditions or actions", name)

# Ticket columns a workflow condition may test (never the ticket's text).
_CONDITION_COLUMNS = ('category', 'subcategory', 'priority', 'status', 'team', 'source',
                      'department', 'assigned_to', 'impact', 'urgency', 'channel',
                      'confidentiality', 'escalation_level', 'crisis_flag')


def check_workflow_conditions(ticket_id, conditions, **kwargs):
    """True when every condition holds for the ticket (its fields — the
    status in the lower-case vocabulary — or the trigger's ``kwargs``)."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        schema, store,
    )
    with store.reading() as conn:
        row = conn.execute(
            f"SELECT {', '.join(_CONDITION_COLUMNS)} FROM support_tickets "  # nosec B608 - fixed columns
            "WHERE ticket_id = ?", (ticket_id,)).fetchone()
    if row is None or row['crisis_flag']:
        # Crisis tickets are the safeguarding team's: no automation acts on them.
        return False
    ticket = dict(row)
    for field, expected in conditions.items():
        if field in ticket:
            actual = ticket[field]
            if field == 'status':
                actual = schema.normalize_status(actual, default=str(actual))
                expected = schema.normalize_status(expected, default=str(expected))
            elif isinstance(actual, str) and isinstance(expected, str):
                actual, expected = actual.lower(), expected.lower()
            if actual != expected:
                return False
        elif field in kwargs:
            if kwargs[field] != expected:
                return False
        else:
            # A condition this trigger cannot answer (e.g. a time-based
            # threshold) does not hold.
            return False
    return True


def _department_team(department):
    """The routing team a Helpdesk department name stands for (None if none)."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        routing,
    )
    with get_connection() as conn:
        row = conn.execute("SELECT team_key FROM departments WHERE name = ?",
                           (department,)).fetchone()
    return (row[0] if row and row[0] else None) or routing.team_key(department)


def execute_workflow_actions(ticket_id, actions, actor=None):
    """Carry out a workflow's actions through the ticket service, as the
    automated ``system`` actor unless ``actor`` is given."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        routing, service,
    )
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.cli_support import (
        SYSTEM_ACTOR,
    )
    actor = actor or SYSTEM_ACTOR
    for action, value in actions.items():
        try:
            if action == 'assign_to_department':
                team = _department_team(value)
                assignee = routing.pick_assignee(team) if team else None
                if assignee:
                    service.assign(actor, ticket_id, assignee)
                else:
                    logger.info("Workflow: nobody free in %s for ticket %s", value, ticket_id)
            elif action == 'set_priority':
                service.bulk_update(actor, [ticket_id], {'priority': value})
            elif action == 'change_status':
                service.set_status(actor, ticket_id, value, note="Changed by an automated workflow")
            elif action == 'escalate_to_manager':
                if value:
                    escalate_ticket(ticket_id, 'workflow_auto_escalation', actor=actor)
            elif action == 'send_survey':
                if value:
                    from education_system.systems.university.domains.student_support.domain.helpdesk.notifications import send_satisfaction_survey
                    send_satisfaction_survey(ticket_id)
        except (PermissionError, ValueError) as e:
            logger.warning("Workflow action %s on ticket %s not applied: %s", action, ticket_id, e)


def _manager_username(team, department):
    """Who an escalation goes to: the department's manager, else the team's
    leads (admins when it has none)."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        routing,
    )
    if department:
        with get_connection() as conn:
            row = conn.execute("SELECT u.username FROM departments d JOIN users u ON u.id = d.manager_id "
                               "WHERE d.name = ?", (department,)).fetchone()
        if row:
            return row[0]
    leads = sorted(routing.team_leads(team)) if team else []
    return leads[0] if leads else None


def escalate_ticket(ticket_id, reason='manual', actor=None):
    """Escalate a ticket one level (status escalated) through the ticket
    service, and hand it to the department's manager (else a team lead)
    when they may work it. ``actor``: who escalates — left out, the
    signed-in support session. Returns the service's result, or None after
    printing why it could not."""
    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as support_auth, service,
    )
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets.cli_support import (
        local_user_id,
    )
    actor = actor or support_auth.get_auth_instance()
    try:
        ticket = service.get_ticket(actor, ticket_id)
        result = service.escalate(actor, ticket_id, reason)
    except (PermissionError, ValueError) as e:
        print(f"Ticket #{ticket_id} could not be escalated: {e}")
        return None

    manager = _manager_username(ticket.get('team'), ticket.get('department'))
    escalated_to = None
    if manager and manager != ticket.get('assigned_to'):
        try:
            service.assign(actor, ticket_id, manager)
            escalated_to = manager
        except (PermissionError, ValueError) as e:
            logger.info("Escalation of ticket %s not handed to %s: %s", ticket_id, manager, e)

    level = (ticket.get('escalation_level') or 0) + 1
    with get_connection() as conn:
        to_id = conn.execute("SELECT id FROM users WHERE username = ?",
                             (escalated_to,)).fetchone() if escalated_to else None
        conn.execute('''
        INSERT INTO ticket_escalations
        (ticket_id, escalation_level, escalated_to, escalated_by, escalation_reason, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (ticket_id, level, to_id[0] if to_id else None, local_user_id(actor), reason,
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
    print(f"Ticket #{ticket_id} escalated to level {level}"
          + (f" and handed to {escalated_to}" if escalated_to else ""))
    return result


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
