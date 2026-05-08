"""Communication logging and health mixin for CommunicationDashboard."""

from __future__ import annotations

import queue
import threading

from education_system.university_system.infrastructure.email.admin._imports import (
    datetime,
    timedelta,
    execute_db_operation,
    get_system_health_info,
    handle_exception,
    log_event,
    log_manager,
    logger,
    queue_email,
    LOG_MANAGEMENT_AVAILABLE,
)


# Lazy, process-wide background mirror for the central audit trail.
# Posting `_log_communication_action` synchronously to AuditLogger added
# 50–100 ms to every chat moderation action because it opens a separate
# sqlite connection on a different DB. This worker drains a queue from a
# daemon thread so the caller returns immediately.
_audit_queue: "queue.Queue[dict] | None" = None
_audit_worker_started = False
_audit_worker_lock = threading.Lock()


def _audit_worker_loop():
    from education_system.university_system.infrastructure.security.audit_trail import (
        AuditLogger,
    )
    while True:
        try:
            entry = _audit_queue.get()
        except Exception:
            return
        if entry is None:  # shutdown sentinel
            return
        try:
            AuditLogger().log(**entry)
        except Exception as e:
            try:
                logger.debug(f"Async audit-trail mirror failed: {e}")
            except Exception:
                pass
        finally:
            try:
                _audit_queue.task_done()
            except Exception:
                pass


def _ensure_audit_worker():
    global _audit_queue, _audit_worker_started
    if _audit_worker_started:
        return _audit_queue
    with _audit_worker_lock:
        if _audit_worker_started:
            return _audit_queue
        _audit_queue = queue.Queue(maxsize=1000)
        threading.Thread(
            target=_audit_worker_loop,
            name="chat-audit-mirror",
            daemon=True,
        ).start()
        _audit_worker_started = True
    return _audit_queue


class _LoggingMixin:
    """Mixin providing logging, analytics, and system health features."""

    def get_communication_logs(self, days=7, limit=100, user_filter=None, action_filter=None):
        """Get communication-related logs from the enhanced logging system"""
        if not LOG_MANAGEMENT_AVAILABLE or not log_manager:
            return []

        try:
            # Get logs from the last N days for communication activities
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            filters = {
                'date_from': start_date,
                'date_to': end_date,
                'module': 'email_manager'
            }

            # Add optional filters
            if user_filter:
                filters['username'] = user_filter
            if action_filter:
                filters['action'] = action_filter

            return log_manager.db.search_logs(filters, limit=limit)
        except Exception as e:
            log_event('error', f"Error retrieving communication logs: {e}")
            return []

    def _log_communication_action(self, user_id, action_type, action_details, cursor=None):
        """Enhanced communication action logging using both systems.

        Args:
            user_id: The user performing the action
            action_type: Type of action being logged
            action_details: Details about the action
            cursor: Optional cursor to reuse existing database connection.
                    If provided, uses the cursor directly to avoid nested transactions.
                    If None, opens a new database connection.
        """

        def _log_action(cur):
            performed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cur.execute('''
            INSERT INTO communication_log (user_id, action_type, action_details, performed_at)
            VALUES (?, ?, ?, ?)
            ''', (user_id, action_type, action_details, performed_at))
            return True

        try:
            # Log to communication system
            # If cursor is provided, use it directly to avoid nested transactions/deadlock
            if cursor is not None:
                result = _log_action(cursor)
            else:
                result = execute_db_operation(_log_action)

            # Also log to enhanced logging system if available
            # Note: This is deferred to avoid nested transactions
            if LOG_MANAGEMENT_AVAILABLE and log_manager:
                try:
                    # Get user info for enhanced logging
                    def _get_user_info(cur):
                        cur.execute("SELECT username, role FROM users WHERE id = ?", (user_id,))
                        return cur.fetchone()

                    # Reuse cursor if provided, otherwise open new connection
                    if cursor is not None:
                        user_info = _get_user_info(cursor)
                    else:
                        user_info = execute_db_operation(_get_user_info)

                    if user_info:
                        username, role = user_info

                        activity_data = {
                            'timestamp': datetime.now().isoformat(),
                            'user_id': user_id,
                            'username': username,
                            'role': role,
                            'action': action_type,
                            'module': 'communication_dashboard',
                            'details': action_details,
                            'status': 'success'
                        }

                        log_manager.db.insert_log(activity_data)

                except Exception as e:
                    # Don't fail the main operation for enhanced logging issues
                    logger.warning(f"Enhanced communication logging failed: {e}")

            # Mirror into the central audit trail asynchronously so chat
            # moderation actions show up in audit_log_viewer_gui without
            # adding the audit DB's connection-open latency to the caller.
            # Best-effort: never propagate failures.
            try:
                username = None
                cur_user = getattr(getattr(self, 'auth', None), 'current_user', None)
                if isinstance(cur_user, dict):
                    username = cur_user.get('username')
                q = _ensure_audit_worker()
                if q is not None:
                    try:
                        q.put_nowait({
                            'action': action_type,
                            'resource_type': 'chat',
                            'resource_id': None,
                            'user_id': user_id,
                            'username': username,
                            'details': {'description': action_details},
                            'function_name': '_log_communication_action',
                            'module_name': 'communication_dashboard',
                        })
                    except queue.Full:
                        # Audit queue saturated — drop and log; never block.
                        logger.warning(
                            "Audit-trail mirror queue full; dropping entry"
                        )
            except Exception as e:
                logger.debug(f"Central audit-trail mirror dispatch failed: {e}")

            return result

        except Exception as e:
            log_event('warning', f"Communication log failed: {e}")
            return False

    @handle_exception
    def _send_email_notification(self, recipient_email, subject, message):
        """Send an email notification using the integrated email system"""
        return queue_email(recipient_email, subject, message)

    @handle_exception
    def get_integrated_system_health_info():
        """Get comprehensive system health information for both systems"""
        health_info = {
            'email_system': 'operational',
            'message_system': 'operational',
            'chat_system': 'operational',
            'database_status': 'operational',
            'enhanced_logging': 'not_available',
            'queue_size': 0,
            'log_entries_today': 0,
            'active_users': 0,
            'last_check': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        try:
            # Check basic communication system health
            base_health = get_system_health_info()
            health_info.update(base_health)

            # Check enhanced logging system if available
            if LOG_MANAGEMENT_AVAILABLE and log_manager:
                health_info['enhanced_logging'] = 'operational'

                try:
                    # Get today's log count
                    today = datetime.now().strftime('%Y-%m-%d')
                    filters = {
                        'date_from': today,
                        'date_to': today,
                        'module': 'email_manager'
                    }

                    today_logs = log_manager.db.search_logs(filters, limit=10000)
                    health_info['log_entries_today'] = len(today_logs)

                    # Get active users count (users who performed actions today)
                    unique_users = set()
                    for log in today_logs:
                        if log.get('user_id'):
                            unique_users.add(log['user_id'])
                    health_info['active_users'] = len(unique_users)

                except Exception as e:
                    health_info['enhanced_logging'] = 'degraded'
                    log_event('warning', f"Enhanced logging health check failed: {e}")

        except Exception as e:
            log_event('error', f"Error checking integrated system health: {e}")
            health_info['database_status'] = 'error'

        return health_info

    def display_system_health():
        """Display comprehensive system health information"""
        health = get_integrated_system_health_info()

        logger.info("\nIntegrated System Health Report:")
        logger.info("=" * 40)
        logger.info(f"Email System: {health['email_system'].upper()}")
        logger.info(f"Message System: {health['message_system'].upper()}")
        logger.info(f"Chat System: {health['chat_system'].upper()}")
        logger.info(f"Database: {health['database_status'].upper()}")
        logger.info(f"Enhanced Logging: {health['enhanced_logging'].upper()}")

        logger.info(f"\nSystem Metrics:")
        logger.info(f"Email Queue Size: {health['queue_size']}")
        logger.info(f"Log Entries Today: {health['log_entries_today']}")
        logger.info(f"Active Users Today: {health['active_users']}")
        logger.info(f"Last Check: {health['last_check']}")

        # Show any issues
        issues = []
        if health['email_system'] != 'operational':
            issues.append("Email system issues detected")
        if health['database_status'] != 'operational':
            issues.append("Database connectivity issues")
        if health['enhanced_logging'] == 'degraded':
            issues.append("Enhanced logging experiencing issues")

        if issues:
            logger.info(f"\nIssues Detected:")
            for issue in issues:
                logger.info(f"  - {issue}")
        else:
            logger.info(f"\nAll systems operational.")

        input("\nPress Enter to continue...")

    def get_communication_analytics(self, days=30):
        """Get analytics for communication activities"""
        if not LOG_MANAGEMENT_AVAILABLE or not log_manager:
            return None

        try:
            # Use log manager's analytics if available
            return log_manager.analytics.generate_activity_summary(days)
        except Exception as e:
            log_event('error', f"Error getting communication analytics: {e}")
            return None
