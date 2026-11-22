"""
Metrics tracking and recording.
"""

import datetime
import json
import logging

from education_system.systems.university.domains.student_support.domain.student_support import auth as _auth_mod
from education_system.systems.university.domains.student_support.domain.student_support import schema, store

logger = logging.getLogger(__name__)

__all__ = [
    'submit_satisfaction_rating',
    '_record_status_change_metrics',
    '_update_metrics',
]


def submit_satisfaction_rating(ticket_id, rating, feedback=None):
    """The signed-in requester rates their resolved ticket (1-5)."""
    if not _auth_mod.auth or not _auth_mod.auth.current_user:
        raise PermissionError("You must be logged in to submit ratings")
    from education_system.systems.university.domains.student_support.domain.student_support import (
        service as _service,
    )
    _service.rate_ticket(_auth_mod.auth, ticket_id, rating, feedback)
    logger.info(f"Satisfaction rating {rating} submitted for ticket #{ticket_id} by {_auth_mod.auth.current_user['username']}")
    return True


def _record_status_change_metrics(ticket_id, old_status, new_status, timestamp):
    """Record a status change in ``system_metrics`` (best effort).

    ``service.set_status`` records its own changes inside its transaction;
    this is for callers that change a status some other way.
    """
    username = (_auth_mod.user_of() or {}).get('username', 'unknown')
    try:
        with store.writing() as conn:
            conn.execute('''
            INSERT INTO system_metrics (metric_name, metric_value, category, recorded_datetime, metadata)
            VALUES (?, ?, ?, ?, ?)''', ('status_change', 1, 'tickets', timestamp, json.dumps({
                'ticket_id': ticket_id, 'old_status': old_status, 'new_status': new_status,
                'changed_by': username})))
    except Exception as e:
        logger.error(f"Error recording status change metrics: {e}")


def _update_metrics():
    """Snapshot the support metrics into ``system_metrics``: active tickets,
    average hours to first response, average satisfaction."""
    active = ", ".join(f"'{s}'" for s in schema.ACTIVE_STATUSES)
    queries = (
        ('active_tickets', 'tickets',
         f"SELECT COUNT(*) FROM support_tickets WHERE status IN ({active})"),  # nosec B608 - fixed vocabulary
        ('avg_response_time', 'performance',
         "SELECT AVG(julianday(first_response_at) - julianday(created_at)) * 24 "
         "FROM support_tickets WHERE first_response_at IS NOT NULL AND created_at IS NOT NULL"),
        ('user_satisfaction', 'satisfaction',
         "SELECT AVG(satisfaction_rating) FROM support_tickets "
         "WHERE satisfaction_rating IS NOT NULL"),
    )
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        with store.writing() as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' "
                                "AND name = 'system_metrics'").fetchone():
                return
            for name, category, sql in queries:
                try:
                    value = conn.execute(sql).fetchone()[0] or 0
                except Exception as e:
                    logger.warning(f"Could not calculate metric {name}: {e}")
                    continue
                conn.execute('''
                INSERT INTO system_metrics (metric_name, metric_value, category, recorded_datetime)
                VALUES (?, ?, ?, ?)''', (name, value, category, timestamp))
    except Exception as e:
        logger.error(f"Error updating metrics: {e}")
