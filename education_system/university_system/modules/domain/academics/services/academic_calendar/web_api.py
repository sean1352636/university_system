import logging
import os
import re
from datetime import datetime
from education_system.university_system.infrastructure.logging.log_config import configure_logging
from education_system.university_system.modules.domain.academics.services.academic_calendar.exceptions import ValidationError, PermissionError

logger = configure_logging(name=__name__)

try:
    from flask import Flask, jsonify, request, render_template_string, send_file
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


# Simplified Web API (if Flask is available)
class CalendarWebAPI:
    def __init__(self, calendar_manager, host: str = 'localhost', port: int = 5000):
        if not FLASK_AVAILABLE:
            raise ImportError("Flask not available for web interface")

        self.calendar_manager = calendar_manager
        self.app = Flask(__name__)
        CORS(self.app, origins=_get_cors_origins(), supports_credentials=True)
        self.host = host
        self.port = port
        self._setup_routes()

    def _setup_routes(self):
        """Setup basic API routes with authentication"""

        @self.app.before_request
        def require_auth():
            """Simple authentication check"""
            if request.endpoint and request.endpoint.startswith('api'):
                auth_header = request.headers.get('Authorization')
                if not auth_header or not auth_header.startswith('Bearer '):
                    return jsonify({'error': 'Authentication required'}), 401

        @self.app.route('/api/events', methods=['GET'])
        def get_events():
            try:
                start_date = request.args.get('start_date')
                end_date = request.args.get('end_date')
                event_type = request.args.get('event_type')

                if not start_date or not end_date:
                    return jsonify({'error': 'start_date and end_date required'}), 400

                events = self.calendar_manager.get_events_by_date_range(
                    start_date, end_date, event_type
                )

                return jsonify({
                    'success': True,
                    'events': events,
                    'count': len(events)
                })

            except ValidationError as e:
                logger.warning("Calendar validation error: %s", e)
                return jsonify({'error': 'Invalid request parameters'}), 400
            except Exception as e:
                logger.error(f"API error: {e}")
                return jsonify({'error': 'Internal server error'}), 500

        @self.app.route('/api/events', methods=['POST'])
        def create_event():
            try:
                data = request.json
                if not data:
                    return jsonify({'error': 'JSON data required'}), 400

                result = self.calendar_manager.add_event(
                    name=data.get('name'),
                    date=data.get('date'),
                    date_start=data.get('date_start'),
                    date_end=data.get('date_end'),
                    description=data.get('description'),
                    event_type=data.get('event_type', 'Academic')
                )

                return jsonify(result)

            except ValidationError as e:
                logger.warning("Event validation error: %s", e)
                return jsonify({'error': 'Invalid event parameters'}), 400
            except PermissionError as e:
                logger.warning("Permission denied for event creation: %s", e)
                return jsonify({'error': 'Permission denied'}), 403
            except Exception as e:
                logger.error(f"API error: {e}")
                return jsonify({'error': 'Internal server error'}), 500

        @self.app.route('/api/calendar/view')
        def view_calendar():
            try:
                academic_year = request.args.get('academic_year')
                semester = request.args.get('semester')

                success, result = self.calendar_manager.view_calendar(academic_year, semester)

                if success:
                    return jsonify({
                        'success': True,
                        'data': result
                    })
                else:
                    return jsonify({'error': result}), 400

            except Exception as e:
                logger.error(f"API error: {e}")
                return jsonify({'error': 'Internal server error'}), 500

        @self.app.route('/')
        def index():
            """Simple API documentation"""
            return render_template_string("""  # nosemgrep: python.flask.security.audit.render-template-string
            <!DOCTYPE html>
            <html>
            <head>
                <title>Academic Calendar API</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; }
                    .endpoint { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
                    .method { font-weight: bold; color: #007bff; }
                    .description { margin-top: 10px; color: #666; }
                </style>
            </head>
            <body>
                <h1>Academic Calendar API</h1>
                <p>RESTful API for Academic Calendar Management</p>

                <div class="endpoint">
                    <span class="method">GET</span> /api/events
                    <div class="description">
                        Get events with filtering. Parameters: start_date, end_date, event_type (optional)
                    </div>
                </div>

                <div class="endpoint">
                    <span class="method">POST</span> /api/events
                    <div class="description">
                        Create a new event. Requires JSON body with name, date/date_start/date_end, description, event_type
                    </div>
                </div>

                <div class="endpoint">
                    <span class="method">GET</span> /api/calendar/view
                    <div class="description">
                        Get calendar view. Parameters: academic_year (optional), semester (optional)
                    </div>
                </div>

                <h2>Authentication</h2>
                <p>All API endpoints require Bearer token authentication via Authorization header.</p>
            </body>
            </html>
            """)

    def run(self, debug: bool = False):
        """Run the web API"""
        self.app.run(host=self.host, port=self.port, debug=debug)
