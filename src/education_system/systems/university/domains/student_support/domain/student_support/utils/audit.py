"""
Audit logging for Student Support.

Every support audit entry goes to ``audit_trail`` through :func:`log_audit`.
That table has been defined three times over the years and the live one has
both an ``id`` key and an ``audit_id`` column, ``user_id`` as an integer and a
``username`` text column; :func:`log_audit` writes whichever of its columns
exist, with the local ``users.id`` and the username of the person acting.
"""

import datetime
import json
import logging
import time
from functools import wraps
from typing import Any, Dict, Optional

from education_system.systems.university.domains.student_support.domain.student_support import auth as _auth_mod

logger = logging.getLogger(__name__)

MODULE_NAME = 'student_support'


def _columns(conn) -> set:
    return {row[1] for row in conn.execute("PRAGMA table_info(audit_trail)").fetchall()}


def log_audit(action: str, *, resource_id=None, resource_type: str = 'support_ticket',
              details: Optional[Dict[str, Any]] = None, old_values=None, new_values=None,
              success: bool = True, error: Optional[str] = None,
              duration: Optional[float] = None, function_name: Optional[str] = None,
              actor: Any = None, conn=None) -> bool:
    """Write one ``audit_trail`` row for a support action.

    Pass ``conn`` to write inside the caller's transaction (the entry then
    commits or rolls back with the change). Without it the entry is written
    on its own connection, best effort. Returns True when a row was written.
    """
    user = _auth_mod.user_of(actor)
    username = (user or {}).get('username') or 'system'
    own = conn is None
    try:
        if own:
            from education_system.systems.university.domains.student_support.domain.student_support import (
                store,
            )
            conn = store.connect(row_factory=False, timeout=10)
        cols = _columns(conn)
        if not cols:
            return False
        users_id = None
        if username != 'system':
            row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            users_id = row[0] if row else None
        detail_text = json.dumps(details, default=str) if details else None
        values = {
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'action': action,
            'resource_type': resource_type,
            'resource_id': None if resource_id is None else str(resource_id),
            # user_id is NOT NULL TEXT in one historic shape, INTEGER in the
            # live one: the local id when there is one, else the username.
            'user_id': users_id if users_id is not None else username,
            'username': username,
            'details': detail_text,
            'function_name': function_name,
            'module_name': MODULE_NAME,
            'success': 1 if success else 0,
            'error_message': error,
            'duration': duration,
            'old_values': json.dumps(old_values, default=str) if old_values is not None else None,
            'new_values': json.dumps(new_values, default=str) if new_values is not None else detail_text,
        }
        values = {k: v for k, v in values.items() if k in cols}
        names = ", ".join(values)
        marks = ", ".join("?" * len(values))
        conn.execute(f"INSERT INTO audit_trail ({names}) VALUES ({marks})",  # nosec B608
                     tuple(values.values()))
        if own:
            conn.commit()
        return True
    except Exception as e:
        if not own:
            raise
        logger.error(f"Failed to log audit trail: {e}")
        return False
    finally:
        if own and conn is not None:
            conn.close()


def _log_audit(audit_data: Dict[str, Any]):
    """Write an audit entry from the decorator's dict (kept for callers)."""
    return log_audit(
        audit_data.get('action') or 'unknown',
        resource_id=audit_data.get('resource_id'),
        resource_type=audit_data.get('resource_type', 'support'),
        details={k: audit_data[k] for k in ('details',) if audit_data.get(k)} or None,
        old_values=audit_data.get('old_values'),
        new_values=audit_data.get('new_values'),
        success=audit_data.get('success', True),
        error=audit_data.get('error'),
        duration=audit_data.get('duration'),
        function_name=audit_data.get('function'),
    )


def audit_action(action_type: str):
    """
    Decorator that writes an ``audit_trail`` entry for a support operation:
    the action, the function, who did it, success or failure (with the
    error) and how long it took. The entry goes through the object's
    ``_log_audit`` when the first argument has one, else :func:`_log_audit`.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            audit_data = {
                'action': action_type,
                'function': func.__name__,
                'user': _auth_mod.auth.current_user['username'] if _auth_mod.auth and _auth_mod.auth.current_user else 'system',
                'timestamp': datetime.datetime.now().isoformat(),
            }
            sink = args[0]._log_audit if args and hasattr(args[0], '_log_audit') else _log_audit
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                audit_data.update(success=False, error=str(e), duration=time.time() - start_time)
                sink(audit_data)
                logger.error(f"Action {action_type} failed after {audit_data['duration']:.2f}s: {e}")
                raise
            audit_data.update(success=True, duration=time.time() - start_time)
            sink(audit_data)
            logger.info(f"Action {action_type} completed successfully in {audit_data['duration']:.2f}s")
            return result

        return wrapper
    return decorator
