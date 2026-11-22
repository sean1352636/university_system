"""
Automatic ticket escalation.

Each active ``escalation_rules`` row acts at most once on a ticket: the first
time it does, a ``support_escalation_fires`` row is written in the same
transaction, so a 'notify' rule tells people once rather than every pass of
the background worker.

When is a ticket due? :func:`ticket_due_sql` is the one place that decides
for the rules: a ticket with an ``sla_due_at`` is due once that time has
passed; otherwise a time-based rule of N hours fires when the ticket has had
no response for N hours since it was raised, or — once answered — no
activity for N hours.

SLA alerts (:func:`_process_sla_breaches`) are separate from the rules: for
every active ticket under an SLA (``sla_due_at`` set — tickets raised before
SLAs existed are not), a warning an hour before the first-response or
resolution target and a breach once it passes, each once per ticket
(``support_escalation_fires`` rows with the reserved rule ids in
:data:`SLA_FIRES`). Warnings go to the assignee (the team when nobody has
it); breaches to the team's leads and the assignee, with an internal note.
Resolution alerts wait while the ticket is waiting on the student, and the
resolution clock is paused then too (``sla.sync_pause``), so the time it
waited is not counted against the team.
"""

import datetime
import logging

from education_system.systems.university.domains.student_support.domain.student_support import (
    notify, routing, schema, sla, store,
)
from education_system.systems.university.domains.student_support.domain.student_support.auth import ADMIN_ROLES
from education_system.systems.university.domains.student_support.domain.student_support.utils.audit import log_audit

logger = logging.getLogger(__name__)

# Statuses a rule can still act on (an escalated ticket is already escalated).
_ELIGIBLE = ('open', 'in_progress', 'waiting_on_student')


def _now():
    return datetime.datetime.now()


def ticket_due_sql(alias='t', pausable=False):
    """SQL true when a ticket counts as overdue for a time-based rule; bind
    it with :func:`_due_params` (now, then the rule's threshold twice).
    ``pausable``: the table has ``sla_paused_at`` — a ticket whose SLA is
    paused (waiting on the student) is not due."""
    p = f"{alias}."
    paused = f" AND {p}sla_paused_at IS NULL" if pausable else ""
    return (f"(({p}sla_due_at IS NOT NULL AND {p}sla_due_at <= ?{paused}) OR "
            f"({p}sla_due_at IS NULL AND {p}first_response_at IS NULL AND {p}created_at < ?) OR "
            f"({p}sla_due_at IS NULL AND {p}first_response_at IS NOT NULL AND "
            f"COALESCE({p}last_activity_at, {p}updated_at, {p}first_response_at) < ?))")


def _due_params(threshold, now):
    return [now, threshold, threshold]


def _recipients(conn, target, ticket):
    """Usernames a rule's ``action_target`` names: a user, a role, or
    'supervisor' (the admins); the ticket's assignee is always told too."""
    target = str(target or '').strip()
    names = []
    if target:
        row = conn.execute("SELECT username FROM users WHERE username = ?", (target,)).fetchone()
        if row:
            names.append(row[0])
        else:
            roles = list(ADMIN_ROLES) if target.lower() in ('supervisor', 'supervisors') else [target]
            marks = ", ".join("?" * len(roles))
            names += [r[0] for r in conn.execute(
                f"SELECT username FROM users WHERE role IN ({marks}) ORDER BY id",  # nosec B608
                roles).fetchall()]
    if ticket['assigned_to']:
        names.append(str(ticket['assigned_to']))
    return list(dict.fromkeys(names))


def _process_escalations():
    """One pass over the active escalation rules; returns how many tickets
    were acted on."""
    acted, notices = 0, []
    try:
        with store.writing() as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' "
                                "AND name = 'escalation_rules'").fetchone():
                return 0
            rules = conn.execute("SELECT * FROM escalation_rules WHERE is_active = 1 "
                                 "ORDER BY rule_id").fetchall()
            cursor = conn.cursor()
            for rule in rules:
                count, rule_notices = _apply_escalation_rule(rule, cursor)
                acted += count
                notices += rule_notices
            notify.deliver_in_app(conn, notices)
    except Exception as e:
        logger.error(f"Error processing escalations: {e}")
        return acted
    notify.after_commit(notices)
    return acted


def _apply_escalation_rule(rule, cursor):
    """Apply one rule to the tickets it matches and has not acted on yet.

    Returns ``(tickets acted on, notices to deliver)``.
    """
    conn = cursor.connection
    rule_id = rule['rule_id']
    condition_type = rule['condition_type']
    action_type = rule['action_type']
    marks = ", ".join("?" * len(_ELIGIBLE))
    query = (f"SELECT t.* FROM support_tickets t LEFT JOIN support_escalation_fires f "
             f"ON f.ticket_id = t.ticket_id AND f.rule_id = ? "
             f"WHERE f.fire_id IS NULL AND t.status IN ({marks})")  # nosec B608 - fixed fragments
    params = [rule_id, *_ELIGIBLE]
    if rule['category']:
        query += " AND lower(t.category) = lower(?)"
        params.append(rule['category'])
    if rule['priority']:
        query += " AND lower(t.priority) = lower(?)"
        params.append(rule['priority'])
    now = _now()
    if condition_type == 'time_based':
        try:
            hours = float(rule['condition_value'])
        except (TypeError, ValueError):
            logger.warning("Escalation rule %s has a non-numeric time '%s'; skipped",
                           rule_id, rule['condition_value'])
            return 0, []
        threshold = (now - datetime.timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        pausable = 'sla_paused_at' in {r[1] for r in conn.execute(
            "PRAGMA table_info(support_tickets)").fetchall()}
        query += " AND " + ticket_due_sql('t', pausable)
        params += _due_params(threshold, now.strftime('%Y-%m-%d %H:%M:%S'))
    elif condition_type == 'status_based':
        query += " AND t.status = ?"
        params.append(schema.normalize_status(rule['condition_value'], default=str(rule['condition_value'])))
    elif condition_type == 'keyword_based':
        query += " AND (lower(t.subject) LIKE ? OR lower(t.description) LIKE ?)"
        term = f"%{str(rule['condition_value']).lower()}%"
        params += [term, term]
    else:
        logger.warning("Escalation rule %s has unknown condition '%s'; skipped", rule_id, condition_type)
        return 0, []

    stamp = now.strftime('%Y-%m-%d %H:%M:%S')
    acted, notices = 0, []
    for ticket in cursor.execute(query, params).fetchall():
        tid = ticket['ticket_id']
        if action_type == 'escalate':
            _escalate_ticket(tid, rule_id, cursor)
            for name in _recipients(conn, rule['action_target'], ticket):
                notices += notify.escalation_alert(tid, ticket['subject'], name,
                                                   f"escalated by rule '{rule['name']}'")
        elif action_type == 'notify':
            for name in _recipients(conn, rule['action_target'], ticket):
                notices += notify.escalation_alert(tid, ticket['subject'], name,
                                                   f"rule '{rule['name']}'")
        elif action_type == 'reassign':
            if not _reassign_ticket(tid, rule['action_target'], cursor):
                continue
            notices += notify.assigned(tid, ticket['subject'], str(rule['action_target']))
        else:
            logger.warning("Escalation rule %s has unknown action '%s'; skipped", rule_id, action_type)
            return acted, notices
        conn.execute("INSERT OR IGNORE INTO support_escalation_fires "
                     "(ticket_id, rule_id, action_type, fired_at) VALUES (?, ?, ?, ?)",
                     (tid, rule_id, action_type, stamp))
        log_audit(f'escalation_rule_{action_type}', resource_id=tid, conn=conn,
                  details={'rule_id': rule_id, 'rule': rule['name']})
        acted += 1
    return acted, notices


def _escalate_ticket(ticket_id, rule_id, cursor):
    """Escalate a ticket (status, time, level) with an internal note naming the rule."""
    escalation_time = _now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
    UPDATE support_tickets
    SET status = 'escalated', escalated_at = ?, updated_at = ?,
        escalation_level = COALESCE(escalation_level, 0) + 1
    WHERE ticket_id = ?
    ''', (escalation_time, escalation_time, ticket_id))
    cursor.execute('''
    INSERT INTO ticket_responses (
        ticket_id, responder_id, responder_role, response_text,
        response_datetime, is_internal, is_auto_generated
    ) VALUES (?, ?, ?, ?, ?, 1, 1)
    ''', (ticket_id, 'system', 'system',
          f'Ticket automatically escalated by escalation rule #{rule_id}', escalation_time))
    # Escalating ends a pause for waiting on the student.
    sla.sync_pause(cursor.connection, ticket_id)


def _create_escalation_notification(ticket_id, target, cursor):
    """Tell ``target`` (a username, a role or 'supervisor') about a ticket
    needing attention, as in-app messages on ``cursor``'s transaction."""
    conn = cursor.connection
    ticket = conn.execute("SELECT * FROM support_tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
    if ticket is None or not target:
        logger.warning(f"Cannot create escalation notification for ticket #{ticket_id}: "
                       "no ticket or no target")
        return []
    notices = []
    for name in _recipients(conn, target, ticket):
        notices += notify.escalation_alert(ticket_id, ticket['subject'], name, 'escalation rules')
    return notify.deliver_in_app(conn, notices)


def _reassign_ticket(ticket_id, new_assignee, cursor):
    """Reassign a ticket to the support staff member ``new_assignee``;
    False (nothing changed) when there is no such user."""
    row = cursor.connection.execute("SELECT username FROM users WHERE username = ?",
                                    (str(new_assignee or ''),)).fetchone()
    if row is None:
        logger.warning("Escalation reassign target '%s' is not a user; ticket #%s left as is",
                       new_assignee, ticket_id)
        return False
    update_time = _now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
    UPDATE support_tickets
    SET assigned_to = ?, updated_at = ?
    WHERE ticket_id = ?
    ''', (row[0], update_time, ticket_id))
    return True


# ── SLA warnings and breaches ────────────────────────────────────────────

# support_escalation_fires.rule_id for each SLA alert (rules have ids >= 1).
SLA_FIRES = {
    'first_response_warning': -1,
    'first_response_breach': -2,
    'resolution_warning': -3,
    'resolution_breach': -4,
}
WARN_HOURS = 1.0
_SLA_TEXT = {
    'first_response_warning': "is due a first response within the hour",
    'first_response_breach': "has missed its first-response target",
    'resolution_warning': "is due to be resolved within the hour",
    'resolution_breach': "has missed its resolution target",
}


def _sla_kinds(ticket, state, now):
    """The SLA alerts a ticket is due now (warnings before breaches)."""
    kinds = []
    status = schema.normalize_status(ticket['status'], default='open')
    pairs = [('first_response', state['first_response_due'], ticket['first_response_at'] is None)]
    if status != 'waiting_on_student':
        pairs.append(('resolution', state['resolution_due'], True))
    for name, due, live in pairs:
        if not live:
            continue
        left = (sla.parse(due) - now).total_seconds() / 3600
        if left <= 0:
            kinds.append(f'{name}_breach')
        elif left <= WARN_HOURS:
            kinds.append(f'{name}_warning')
    return kinds


def _sla_recipients(conn, ticket, kind):
    team = ticket['team'] or routing.route(ticket['category'], ticket['subcategory'])
    assignee = str(ticket['assigned_to']) if ticket['assigned_to'] else None
    if kind.endswith('breach'):
        names = set(routing.team_leads(team, conn))
    else:
        names = set() if assignee else set(routing.team_members(team, conn))
    if assignee:
        names.add(assignee)
    return sorted(names)


def _process_sla_breaches(now=None):
    """One pass of SLA warnings and breaches; returns how many alerts fired."""
    now = sla.parse(now) or _now()
    stamp = now.strftime('%Y-%m-%d %H:%M:%S')
    fired, notices = 0, []
    try:
        with store.writing() as conn:
            # Statuses written without sync_pause (older code paths).
            sla.sync_all_pauses(conn, now)
            marks = ", ".join("?" * len(schema.ACTIVE_STATUSES))
            tickets = conn.execute(
                f"SELECT * FROM support_tickets WHERE status IN ({marks}) "  # nosec B608
                "AND sla_due_at IS NOT NULL ORDER BY ticket_id", schema.ACTIVE_STATUSES).fetchall()
            done = {(r[0], r[1]) for r in conn.execute(
                "SELECT ticket_id, rule_id FROM support_escalation_fires WHERE rule_id < 0")}
            clock = sla.Clock(conn)
            for ticket in tickets:
                tid = ticket['ticket_id']
                state = sla.ticket_sla(conn, ticket, now, clock)
                for kind in _sla_kinds(ticket, state, now):
                    rule_id = SLA_FIRES[kind]
                    if (tid, rule_id) in done:
                        continue
                    if kind.endswith('warning') and (tid, rule_id - 1) in done:
                        continue        # already breached: no late warning
                    conn.execute("INSERT OR IGNORE INTO support_escalation_fires "
                                 "(ticket_id, rule_id, action_type, fired_at) VALUES (?, ?, ?, ?)",
                                 (tid, rule_id, f'sla_{kind}', stamp))
                    done.add((tid, rule_id))
                    due = state['first_response_due' if kind.startswith('first') else 'resolution_due']
                    if kind.endswith('breach'):
                        conn.execute(
                            "INSERT INTO ticket_responses (ticket_id, responder_id, responder_role, "
                            "response_text, response_datetime, is_internal, is_auto_generated) "
                            "VALUES (?, 'system', 'system', ?, ?, 1, 1)",
                            (tid, f"SLA breach: this ticket {_SLA_TEXT[kind]} (due {due}).", stamp))
                    for name in _sla_recipients(conn, ticket, kind):
                        notices += notify.sla_alert(tid, ticket['subject'], name, kind=kind,
                                                    what=_SLA_TEXT[kind], due=due)
                    log_audit(f'sla_{kind}', resource_id=tid, conn=conn,
                              details={'due': due, 'team': ticket['team']})
                    fired += 1
            notify.deliver_in_app(conn, notices)
    except Exception as e:
        logger.error(f"Error checking SLA breaches: {e}")
        return fired
    notify.after_commit(notices)
    return fired
