import logging
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from education_system.university_system.utils.logging.log_config import configure_logging

logger = configure_logging(name=__name__)

try:
    from flask import Flask, jsonify, request
    from flask_cors import CORS
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

_ORIGIN_RE = re.compile(r"^https?://[a-zA-Z0-9._-]+(:\d{1,5})?$")
_DEV_ENVS = {"development", "dev", "local"}


def _get_cors_origins() -> list:
    """Build a validated list of allowed CORS origins."""
    app_env = os.environ.get("APP_ENV", "production").lower()
    is_dev = app_env in _DEV_ENVS

    env_origins = os.environ.get("CORS_ALLOWED_ORIGINS")
    if env_origins is not None:
        raw = [o.strip() for o in env_origins.split(",") if o.strip()]
    elif is_dev:
        raw = ["http://localhost:3000"]
    else:
        logger.warning(
            "CORS_ALLOWED_ORIGINS is not set and APP_ENV=%s; "
            "no cross-origin requests will be allowed",
            app_env,
        )
        return []

    valid = []
    for origin in raw:
        if _ORIGIN_RE.match(origin):
            valid.append(origin)
        else:
            logger.warning("Ignoring invalid CORS origin: %r", origin)
    return valid


class MobileAPIManager:
    """Enhanced REST API optimized for mobile applications"""

    def __init__(self, calendar_manager):
        self.calendar_manager = calendar_manager
        if FLASK_AVAILABLE:
            self.app = Flask(__name__)
            CORS(self.app, origins=_get_cors_origins(), supports_credentials=True)
            self._setup_mobile_routes()

    def _setup_mobile_routes(self):
        """Setup mobile-optimized API routes"""

        @self.app.route('/api/mobile/events', methods=['GET'])
        def get_mobile_events():
            """Get events optimized for mobile view"""
            try:
                # Get parameters
                date = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))
                view_type = request.args.get('view', 'day')  # day, week, month
                limit = min(int(request.args.get('limit', 50)), 100)

                # Calculate date range based on view type
                base_date = datetime.strptime(date, "%Y-%m-%d")

                if view_type == 'day':
                    start_date = end_date = base_date
                elif view_type == 'week':
                    start_date = base_date - timedelta(days=base_date.weekday())
                    end_date = start_date + timedelta(days=6)
                elif view_type == 'month':
                    start_date = base_date.replace(day=1)
                    next_month = start_date + timedelta(days=32)
                    end_date = next_month.replace(day=1) - timedelta(days=1)

                events = self.calendar_manager.get_events_by_date_range(
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d")
                )

                # Optimize for mobile
                mobile_events = []
                for event in events[:limit]:
                    mobile_events.append({
                        'id': event['id'],
                        'title': event['name'],
                        'date': event['date'] or event['date_start'],
                        'endDate': event.get('date_end'),
                        'type': event['event_type'],
                        'description': event.get('description', '')[:200],  # Truncate for mobile
                        'isAllDay': bool(event['date']),
                        'color': self._get_event_color(event['event_type'])
                    })

                return jsonify({
                    'success': True,
                    'events': mobile_events,
                    'viewType': view_type,
                    'dateRange': {
                        'start': start_date.strftime("%Y-%m-%d"),
                        'end': end_date.strftime("%Y-%m-%d")
                    },
                    'hasMore': len(events) > limit
                })

            except Exception as e:
                logger.error("Error retrieving mobile events: %s", e)
                return jsonify({'success': False, 'error': 'Internal server error'}), 500

        @self.app.route('/api/mobile/events/<event_id>', methods=['GET'])
        def get_mobile_event_details(event_id):
            """Get detailed event information for mobile"""
            try:
                rows = self.calendar_manager.db_manager.execute_query(
                    "SELECT * FROM academic_calendar_events WHERE id = ?", (event_id,)
                )

                if not rows:
                    return jsonify({'success': False, 'error': 'Event not found'}), 404

                event = dict(rows[0])

                # Get additional mobile-relevant information
                event_details = {
                    'id': event['id'],
                    'title': event['name'],
                    'description': event.get('description', ''),
                    'date': event['date'] or event['date_start'],
                    'endDate': event.get('date_end'),
                    'type': event['event_type'],
                    'isAllDay': bool(event['date']),
                    'color': self._get_event_color(event['event_type']),
                    'canEdit': self._can_user_edit_event(event_id),
                    'reminders': self._get_event_reminders(event_id),
                    'location': self._get_event_location(event_id),
                    'attachments': self._get_event_attachments(event_id)
                }

                return jsonify({
                    'success': True,
                    'event': event_details
                })

            except Exception as e:
                logger.error("Error retrieving mobile event details: %s", e)
                return jsonify({'success': False, 'error': 'Internal server error'}), 500

        @self.app.route('/api/mobile/sync', methods=['POST'])
        def mobile_sync():
            """Sync mobile app data with server"""
            try:
                data = request.json
                last_sync = data.get('lastSync')

                # Get events modified since last sync
                if last_sync:
                    query = '''
                    SELECT * FROM academic_calendar_events
                    WHERE last_modified > ?
                    ORDER BY last_modified DESC
                    '''
                    rows = self.calendar_manager.db_manager.execute_query(
                        query, (last_sync,)
                    )
                else:
                    # First sync - get recent events
                    rows = self.calendar_manager.db_manager.execute_query('''
                    SELECT * FROM academic_calendar_events
                    WHERE date >= date('now', '-30 days')
                    ORDER BY date
                    ''')

                sync_data = {
                    'events': [dict(row) for row in rows],
                    'syncTime': datetime.now().isoformat(),
                    'hasMore': False  # Could implement pagination here
                }

                return jsonify({
                    'success': True,
                    'data': sync_data
                })

            except Exception as e:
                logger.error("Error syncing mobile data: %s", e)
                return jsonify({'success': False, 'error': 'Internal server error'}), 500

    def _get_event_color(self, event_type: str) -> str:
        """Get color for event type"""
        color_map = {
            'Academic': '#1E3A8A',
            'Administrative': '#7C2D12',
            'Social': '#15803D',
            'Sports': '#DC2626',
            'Holiday': '#7C3AED',
            'Deadline': '#EA580C'
        }
        return color_map.get(event_type, '#6B7280')

    def _can_user_edit_event(self, event_id: str) -> bool:
        """Check if current user can edit event"""
        try:
            return self.calendar_manager.auth_manager.check_permission('manage_schedules')
        except (AttributeError, Exception):
            return False

    def _get_event_reminders(self, event_id: str) -> List[Dict]:
        """Get reminders for an event"""
        try:
            rows = self.calendar_manager.db_manager.execute_query('''
            SELECT * FROM notification_queue
            WHERE event_id = ? AND status = 'pending'
            ''', (event_id,))
            return [dict(row) for row in rows]
        except Exception:
            return []

    def _get_event_location(self, event_id: str) -> Optional[str]:
        """Get event location from resource bookings"""
        try:
            rows = self.calendar_manager.db_manager.execute_query('''
            SELECT r.location FROM resource_bookings rb
            JOIN resources r ON rb.resource_id = r.id
            WHERE rb.event_id = ? AND rb.status = 'confirmed'
            LIMIT 1
            ''', (event_id,))
            return rows[0]['location'] if rows else None
        except Exception:
            return None

    def _get_event_attachments(self, event_id: str) -> List[Dict]:
        """Get event attachments (placeholder for future implementation)"""
        return []
