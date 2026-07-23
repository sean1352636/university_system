"""
Automation modules for escalations, sentiment analysis, and background tasks.
"""

import datetime
import logging
import threading

logger = logging.getLogger(__name__)

# Import specific functions to avoid issues
try:
    from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.automation.escalations import (
        _process_escalations,
        _apply_escalation_rule,
        _escalate_ticket,
        _create_escalation_notification,
        _reassign_ticket,
    )
except ImportError as e:
    logging.warning(f"Could not import escalations functions: {e}")

    def _process_escalations():
        """Process automatic escalations for tickets past SLA thresholds."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import sqlite3
            from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.config import SUPPORT_DB
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()

            # Check if required tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='support_tickets'")
            if not cursor.fetchone():
                conn.close()
                return

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='escalation_rules'")
            if not cursor.fetchone():
                conn.close()
                return

            # Get active escalation rules
            cursor.execute('SELECT * FROM escalation_rules WHERE is_active = 1')
            rules = cursor.fetchall()

            # Check available columns on support_tickets
            cursor.execute("PRAGMA table_info(support_tickets)")
            columns = [col[1] for col in cursor.fetchall()]

            now = datetime.datetime.now()

            for rule in rules:
                rule_id = rule[0]
                category = rule[2]
                priority = rule[3]
                condition_type = rule[4]
                condition_value = rule[5]
                action_type = rule[6]

                try:
                    query = "SELECT ticket_id FROM support_tickets WHERE status NOT IN ('Resolved', 'Closed', 'Escalated')"
                    params = []

                    if category:
                        query += " AND category = ?"
                        params.append(category)
                    if priority:
                        query += " AND priority = ?"
                        params.append(priority)

                    if condition_type == 'time_based':
                        hours_threshold = float(condition_value)
                        threshold_time = now - datetime.timedelta(hours=hours_threshold)
                        dt_col = 'created_at' if 'created_at' in columns else (
                            'registration_datetime' if 'registration_datetime' in columns else None
                        )
                        if dt_col is None:
                            continue
                        query += f" AND {dt_col} < ?"
                        params.append(threshold_time.strftime('%Y-%m-%d %H:%M:%S'))

                    cursor.execute(query, params)
                    tickets = cursor.fetchall()

                    escalation_time = now.strftime('%Y-%m-%d %H:%M:%S')
                    for ticket in tickets:
                        ticket_id = ticket[0]
                        if action_type == 'escalate':
                            cursor.execute(
                                "UPDATE support_tickets SET status = 'Escalated', updated_at = ? WHERE ticket_id = ?",
                                (escalation_time, ticket_id)
                            )
                        elif action_type == 'reassign':
                            cursor.execute(
                                "UPDATE support_tickets SET assigned_to = ?, updated_at = ? WHERE ticket_id = ?",
                                (rule[7], escalation_time, ticket_id)
                            )
                        logger.info(f"Escalation rule {rule_id} applied to ticket {ticket_id}")
                except Exception as rule_err:
                    logger.error(f"Error applying escalation rule {rule_id}: {rule_err}")

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error processing escalations: {e}")

    def _escalate_ticket(ticket_id, rule_id, cursor):
        """Escalate a ticket (fallback mirroring escalations._escalate_ticket)."""
        escalation_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            "UPDATE support_tickets SET status = 'Escalated', escalated_at = ?, "
            "updated_at = ? WHERE ticket_id = ?",
            (escalation_time, escalation_time, ticket_id),
        )
        cursor.execute(
            "INSERT INTO ticket_responses (ticket_id, responder_id, responder_role, "
            "response_text, response_datetime, is_auto_generated) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                ticket_id, 'system', 'system',
                f'Ticket automatically escalated due to escalation rule #{rule_id}',
                escalation_time, 1,
            ),
        )

    def _create_escalation_notification(ticket_id, target, cursor):
        """Create an escalation notification (fallback mirroring escalations.py)."""
        if not target:
            logger.warning(
                f"Cannot create escalation notification for ticket #{ticket_id}: "
                "target is NULL"
            )
            return
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            "INSERT INTO notifications (user_id, title, message, notification_type, "
            "related_ticket_id, created_datetime) VALUES (?, ?, ?, ?, ?, ?)",
            (
                target, 'Ticket Escalation Alert',
                f'Ticket #{ticket_id} requires attention due to escalation rules.',
                'email', ticket_id, timestamp,
            ),
        )

    def _reassign_ticket(ticket_id, new_assignee, cursor):
        """Reassign a ticket (fallback mirroring escalations._reassign_ticket)."""
        update_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            "UPDATE support_tickets SET assigned_to = ?, updated_at = ? "
            "WHERE ticket_id = ?",
            (new_assignee, update_time, ticket_id),
        )

    def _apply_escalation_rule(rule, cursor):
        """Apply one escalation rule by delegating to the action helpers.

        Fallback mirror of escalations._apply_escalation_rule so that this
        exported symbol performs real work (rather than a silent no-op) when
        the primary escalations module cannot be imported.
        """
        rule_id = rule[0]
        try:
            category = rule[2]
            priority = rule[3]
            condition_type = rule[4]
            condition_value = rule[5]
            action_type = rule[6]
            action_target = rule[7]

            cursor.execute("PRAGMA table_info(support_tickets)")
            columns = [col[1] for col in cursor.fetchall()]

            query = (
                "SELECT ticket_id FROM support_tickets "
                "WHERE status NOT IN ('Resolved', 'Closed', 'Escalated')"
            )
            params = []
            if category:
                query += " AND category = ?"
                params.append(category)
            if priority:
                query += " AND priority = ?"
                params.append(priority)

            if condition_type == 'time_based':
                hours_threshold = float(condition_value)
                threshold_time = datetime.datetime.now() - datetime.timedelta(
                    hours=hours_threshold
                )
                dt_col = 'created_at' if 'created_at' in columns else (
                    'registration_datetime' if 'registration_datetime' in columns else None
                )
                if dt_col is None:
                    logger.warning(
                        f"No suitable datetime column for escalation rule {rule_id}"
                    )
                    return
                query += f" AND {dt_col} < ?"
                params.append(threshold_time.strftime('%Y-%m-%d %H:%M:%S'))

            cursor.execute(query, params)
            tickets = cursor.fetchall()

            for ticket in tickets:
                ticket_id = ticket[0]
                if action_type == 'escalate':
                    _escalate_ticket(ticket_id, rule_id, cursor)
                elif action_type == 'notify':
                    _create_escalation_notification(ticket_id, action_target, cursor)
                elif action_type == 'reassign':
                    _reassign_ticket(ticket_id, action_target, cursor)
        except Exception as rule_err:
            logger.error(f"Error applying escalation rule {rule_id}: {rule_err}")

try:
    from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.automation.sentiment_analysis import (
        _analyze_sentiment,
        _suggest_category,
        _get_auto_assignment,
        _estimate_resolution_time,
    )
except ImportError as e:
    logging.warning(f"Could not import sentiment_analysis functions: {e}")

    def _analyze_sentiment(text):
        """Simple keyword-based sentiment analysis returning dict with sentiment and score."""
        if not text:
            return {'sentiment': 'neutral', 'score': 0.0}

        text_lower = text.lower()

        negative_keywords = [
            'urgent', 'frustrated', 'angry', 'terrible', 'awful', 'horrible',
            'hate', 'worst', 'furious', 'disgusted', 'outraged', 'immediately',
            'ridiculous', 'unacceptable', 'disappointed', 'broken', 'failure'
        ]
        positive_keywords = [
            'thank', 'thanks', 'great', 'excellent', 'wonderful', 'amazing',
            'perfect', 'love', 'fantastic', 'awesome', 'pleased', 'resolved',
            'helpful', 'appreciate', 'good'
        ]

        neg_count = sum(1 for kw in negative_keywords if kw in text_lower)
        pos_count = sum(1 for kw in positive_keywords if kw in text_lower)

        total = neg_count + pos_count
        if total == 0:
            return {'sentiment': 'neutral', 'score': 0.0}

        # Score ranges from -1.0 (very negative) to 1.0 (very positive)
        score = (pos_count - neg_count) / max(total, 1)
        score = max(-1.0, min(1.0, score))

        if score > 0.2:
            sentiment = 'positive'
        elif score < -0.2:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'

        return {'sentiment': sentiment, 'score': round(score, 2)}

    def _suggest_category(title, description):
        """Keyword matching to suggest ticket categories from title and description."""
        text = f"{title or ''} {description or ''}".lower()

        category_keywords = {
            'IT': ['password', 'login', 'computer', 'wifi', 'internet', 'email',
                   'software', 'system', 'app', 'website', 'network', 'printer',
                   'account', 'access', 'reset', 'error', 'bug', 'crash'],
            'Academic': ['grade', 'grades', 'marks', 'course', 'assignment',
                         'professor', 'class', 'exam', 'transcript', 'graduation',
                         'credit', 'lecture', 'syllabus', 'deadline', 'assessment'],
            'Accommodation': ['housing', 'room', 'dorm', 'dormitory', 'roommate',
                              'residence', 'maintenance', 'key', 'heating', 'AC',
                              'apartment', 'lease', 'rent', 'move'],
            'Financial': ['scholarship', 'loan', 'tuition', 'payment', 'financial',
                          'aid', 'grant', 'billing', 'fee', 'refund', 'bursary'],
            'Library': ['library', 'book', 'research', 'database', 'citation',
                        'journal', 'borrow', 'overdue'],
            'Wellbeing': ['counseling', 'stress', 'anxiety', 'depression',
                          'wellness', 'therapy', 'mental', 'health', 'support'],
            'Registration': ['register', 'enrollment', 'enroll', 'schedule',
                             'waitlist', 'drop', 'add', 'prerequisite', 'timetable'],
            'Dining': ['meal', 'food', 'dining', 'cafeteria', 'allergy', 'dietary',
                       'canteen', 'catering'],
            'Parking': ['parking', 'permit', 'car', 'vehicle', 'tow', 'bicycle'],
            'Career': ['job', 'career', 'internship', 'resume', 'interview',
                       'employment', 'placement', 'CV'],
        }

        scores = {}
        for category, keywords in category_keywords.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[category] = score

        if scores:
            return max(scores, key=scores.get)
        return 'General'

    def _get_auto_assignment(category, priority):
        """Return a staff member ID based on category using a simple mapping."""
        # Default staff mapping by category
        default_assignments = {
            'IT': 'staff_it_support',
            'Academic': 'staff_academic_advisor',
            'Accommodation': 'staff_housing_officer',
            'Financial': 'staff_financial_aid',
            'Library': 'staff_librarian',
            'Wellbeing': 'staff_counselor',
            'Registration': 'staff_registrar',
            'Dining': 'staff_dining_services',
            'Parking': 'staff_parking_admin',
            'Career': 'staff_career_services',
            'General': 'staff_general_support',
            'Technical': 'staff_it_support',
            'Housing': 'staff_housing_officer',
            'Financial Aid': 'staff_financial_aid',
            'Mental Health': 'staff_counselor',
            'Library Services': 'staff_librarian',
            'Career Services': 'staff_career_services',
        }

        staff_id = default_assignments.get(category, 'staff_general_support')

        # For critical/urgent priority, prefix with senior
        if priority in ('Critical', 'Urgent'):
            staff_id = f"senior_{staff_id}"

        return staff_id

    def _estimate_resolution_time(category, priority):
        """Return estimated resolution hours based on category and priority."""
        # Base resolution times in hours by category
        base_hours = {
            'IT': 4,
            'Technical': 4,
            'Academic': 24,
            'Accommodation': 12,
            'Housing': 12,
            'Financial': 48,
            'Financial Aid': 48,
            'Library': 2,
            'Library Services': 2,
            'Wellbeing': 1,
            'Mental Health': 1,
            'Registration': 8,
            'Dining': 6,
            'Parking': 4,
            'Career': 24,
            'Career Services': 24,
            'General': 24,
        }

        priority_multipliers = {
            'Critical': 0.25,
            'Urgent': 0.5,
            'High': 0.75,
            'Medium': 1.0,
            'Low': 2.0,
        }

        hours = base_hours.get(category, 24)
        multiplier = priority_multipliers.get(priority, 1.0)
        return round(hours * multiplier, 1)

try:
    from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.automation.background_tasks import (
        _start_background_tasks,
        _process_notification_queue,
        _update_metrics,
        _load_staff_assignments,
    )
except ImportError as e:
    logging.warning(f"Could not import background_tasks functions: {e}")

    _background_timer = None

    def _start_background_tasks():
        """Set up a periodic timer for escalation processing and metrics updates."""
        global _background_timer

        def _run_periodic():
            global _background_timer
            try:
                _process_escalations()
                _process_notification_queue()
                _update_metrics()
            except Exception as e:
                logger.error(f"Background task error: {e}")
            # Schedule next run in 300 seconds (5 minutes)
            _background_timer = threading.Timer(300, _run_periodic)
            _background_timer.daemon = True
            _background_timer.start()

        # Start the first run after a short delay
        _background_timer = threading.Timer(10, _run_periodic)
        _background_timer.daemon = True
        _background_timer.start()
        logger.info("Background tasks started (fallback timer mode)")

    def _process_notification_queue():
        """Process pending notifications by marking expired ones as read."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import sqlite3
            from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.config import SUPPORT_DB
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()

            # Check if notifications table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'")
            if not cursor.fetchone():
                conn.close()
                return

            # Mark expired notifications as read
            cursor.execute('''
                UPDATE notifications
                SET is_read = 1
                WHERE expires_at < datetime('now') AND is_read = 0
            ''')
            expired_count = cursor.rowcount

            if expired_count > 0:
                logger.info(f"Marked {expired_count} expired notifications as read")

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error processing notification queue: {e}")

    def _update_metrics():
        """Calculate and store basic metrics: open tickets, avg resolution time, tickets by category."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import sqlite3
            from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.config import SUPPORT_DB
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()

            # Check if required tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='support_tickets'")
            if not cursor.fetchone():
                conn.close()
                return

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_metrics'")
            if not cursor.fetchone():
                conn.close()
                return

            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Check available columns
            cursor.execute("PRAGMA table_info(support_tickets)")
            columns = [col[1] for col in cursor.fetchall()]

            # Open tickets count
            cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE status NOT IN ('Resolved', 'Closed')")
            open_count = cursor.fetchone()[0] or 0
            cursor.execute(
                "INSERT INTO system_metrics (metric_name, metric_value, category, recorded_datetime) VALUES (?, ?, ?, ?)",
                ('open_tickets', open_count, 'tickets', timestamp)
            )

            # Average resolution time (hours)
            if 'resolved_at' in columns and 'created_at' in columns:
                cursor.execute('''
                    SELECT AVG(julianday(resolved_at) - julianday(created_at)) * 24
                    FROM support_tickets
                    WHERE resolved_at IS NOT NULL AND created_at IS NOT NULL
                ''')
                avg_resolution = cursor.fetchone()[0] or 0
                cursor.execute(
                    "INSERT INTO system_metrics (metric_name, metric_value, category, recorded_datetime) VALUES (?, ?, ?, ?)",
                    ('avg_resolution_hours', round(avg_resolution, 2), 'performance', timestamp)
                )

            # Tickets by category
            cursor.execute('''
                SELECT category, COUNT(*) FROM support_tickets
                WHERE status NOT IN ('Resolved', 'Closed')
                GROUP BY category
            ''')
            for cat, count in cursor.fetchall():
                cursor.execute(
                    "INSERT INTO system_metrics (metric_name, metric_value, category, recorded_datetime) VALUES (?, ?, ?, ?)",
                    (f'tickets_in_{cat}', count, 'tickets_by_category', timestamp)
                )

            conn.commit()
            conn.close()
            logger.debug("Metrics updated successfully")
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")

    def _load_staff_assignments():
        """Load staff-to-category mappings from the database or return defaults."""
        try:
            from education_system.post_18.university_system.infrastructure.database.db import sqlite3
            from education_system.post_18.university_system.modules.domain.student_affairs.services.student_support.config import SUPPORT_DB
            conn = sqlite3.connect(SUPPORT_DB)
            cursor = conn.cursor()

            # Check if staff_assignments table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='staff_assignments'")
            if not cursor.fetchone():
                conn.close()
                logger.info("Staff assignments table not found, returning empty mapping")
                return {}

            cursor.execute('SELECT staff_id, category, is_primary FROM staff_assignments WHERE auto_assign_enabled = 1')
            assignments = {}
            for staff_id, category, is_primary in cursor.fetchall():
                if category not in assignments:
                    assignments[category] = []
                assignments[category].append({
                    'staff_id': staff_id,
                    'is_primary': bool(is_primary)
                })

            conn.close()
            logger.info(f"Loaded staff assignments for {len(assignments)} categories")
            return assignments
        except Exception as e:
            logger.error(f"Error loading staff assignments: {e}")
            return {}

__all__ = [
    '_process_escalations',
    '_apply_escalation_rule',
    '_escalate_ticket',
    '_create_escalation_notification',
    '_reassign_ticket',
    '_analyze_sentiment',
    '_suggest_category',
    '_get_auto_assignment',
    '_estimate_resolution_time',
    '_start_background_tasks',
    '_process_notification_queue',
    '_update_metrics',
    '_load_staff_assignments',
]
