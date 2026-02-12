from university_system.infrastructure.database.db import DEFAULT_DB_PATH as _DB_PATH  # injected
# Standard library
import os
import json
import csv
import hashlib
from university_system.infrastructure.database.db import sqlite3, DatabaseManager, ensure_parent_dir
import threading
import smtplib
import zipfile
import re
import secrets
import time
import warnings
import queue
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import Any, Dict, List, Optional
from pathlib import Path
from university_system.modules.shared.constants.paths import LOG_DIR, TEMP_DIR
from university_system.modules.shared.utils.sql_safety import (
    validate_table_name,
    SQLIdentifierError,
)

# i18n support
try:
    from university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    def _t(key, **kwargs):
        """Fallback translation function"""
        return key

# Third-party scheduling / plotting / data
# Attempt to import optional third-party libraries.  These may not be
# installed in the execution environment (e.g. schedule for job
# scheduling, matplotlib/seaborn for charting, pandas for data
# manipulation, tabulate for pretty printing).  When unavailable,
# substitute them with dummy stubs or None so that importing this
# module does not fail.  Callers should check availability before
# using these features.
try:
    import schedule  # type: ignore
    SCHEDULE_AVAILABLE = True
except Exception:
    SCHEDULE_AVAILABLE = False
    # Provide a stub that absorbs chained method calls gracefully.  This
    # replicates the fluent interface of the `schedule` library without
    # performing any actual scheduling.  Each method returns itself so
    # chained calls do not raise AttributeError.
    class _ScheduleJobStub:
        def __getattr__(self, name):  # pragma: no cover
            return self
        def __call__(self, *args, **kwargs):  # pragma: no cover
            return self

    class _ScheduleStub:
        def __getattr__(self, name):  # pragma: no cover
            return _ScheduleJobStub()
        def __call__(self, *args, **kwargs):  # pragma: no cover
            return _ScheduleJobStub()
    schedule = _ScheduleStub()

try:
    import matplotlib.pyplot as plt  # type: ignore
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False
    # Dummy object that ignores attribute access and calls
    class _MatplotlibDummy:
        def __getattr__(self, name):
            return self
        def __call__(self, *args, **kwargs):  # pragma: no cover
            return None
    plt = _MatplotlibDummy()

try:
    import pandas as pd  # type: ignore
except Exception:
    pd = None  # type: ignore

try:
    import seaborn as sns  # type: ignore
    SEABORN_AVAILABLE = True
except Exception:
    SEABORN_AVAILABLE = False
    # Create dummy seaborn object to avoid NameError when accessed
    class _SeabornDummy:
        def __getattr__(self, name):
            return self
        def __call__(self, *args, **kwargs):  # pragma: no cover
            return None
    sns = _SeabornDummy()

try:
    from tabulate import tabulate  # type: ignore
except Exception:
    # Provide a fallback implementation of tabulate that returns
    # simple CSV-like strings.  This is sufficient for basic logging
    # output when the real library is not installed.
    def tabulate(data, headers=(), tablefmt=None):  # pragma: no cover
        lines = []
        if headers:
            lines.append(','.join(str(h) for h in headers))
        for row in data:
            lines.append(','.join(str(col) for col in row))
        return '\n'.join(lines)

# Email utilities
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Web framework
# Attempt to import Flask and JWT libraries for the web API.  If these
# dependencies are unavailable (common in constrained environments),
# provide fallback stubs that expose the minimal interfaces used in this
# module.  The stubs allow the module to be imported without
# triggering ImportError; however, API routes will not be functional.
try:
    from flask import Flask, request, jsonify, send_file  # type: ignore
    from functools import wraps  # type: ignore
    import jwt  # type: ignore
    FLASK_AVAILABLE = True
except Exception:
    FLASK_AVAILABLE = False
    # Define dummy Flask app and related objects
    class _RequestDummy:
        """A minimal request-like object exposing args and headers dicts."""
        args: Dict[str, Any] = {}
        headers: Dict[str, Any] = {}
        def get_json(self):  # pragma: no cover
            return {}
        def get(self, *args, **kwargs):  # pragma: no cover
            return None
    # jsonify returns the input unchanged
    def jsonify(response):  # pragma: no cover
        return response
    def send_file(*args, **kwargs):  # pragma: no cover
        return None
    def wraps(func):  # pragma: no cover
        return func
    class _FlaskDummy:
        """A minimal Flask-like class used when Flask is not installed."""
        def __init__(self, *args, **kwargs):
            # Provide a config dict so assignments like app.config['SECRET_KEY'] work
            self.config: Dict[str, Any] = {}
        def route(self, *args, **kwargs):  # pragma: no cover
            def decorator(func):
                return func
            return decorator
        def run(self, *args, **kwargs):  # pragma: no cover
            print("Flask is not available; cannot run web server")
        def __call__(self, *args, **kwargs):  # pragma: no cover
            return self
        def errorhandler(self, *args, **kwargs):  # pragma: no cover
            """Dummy errorhandler decorator that returns the function unchanged."""
            def decorator(func):
                return func
            return decorator
        def response_class(self, *args, **kwargs):  # pragma: no cover
            """Fallback for Flask's response_class.  Returns a minimal dict-like object."""
            class _Response:
                def __init__(self, response=None, status=200, mimetype=None, *a, **kw):
                    self.response = response
                    self.status = status
                    self.mimetype = mimetype
                def __call__(self, *a, **kw):  # pragma: no cover
                    return self
            return _Response(*args, **kwargs)
    Flask = _FlaskDummy
    request = _RequestDummy()
    # Provide a minimal JWT stub with encode/decode functions
    class _JWTStub:
        def encode(self, payload, key, algorithm='HS256'):  # pragma: no cover
            # Return a dummy token representation (not secure)
            return f"token-{payload.get('user_id', '')}".encode()
        def decode(self, token, key, algorithms=None):  # pragma: no cover
            # Return a dummy payload; in a real environment this would
            # verify and decode the token.  Here we simply return a
            # dictionary with the user_id extracted from the token.
            tok = token.decode() if isinstance(token, bytes) else str(token)
            if tok.startswith('token-'):
                return {'user_id': tok[6:]}
            return {'user_id': tok}
    jwt = _JWTStub()

warnings.filterwarnings('ignore')

# Import the original logger
# Use the logger from the refactored utils module
from university_system.modules.shared.utils.simple_activity_logger import logger

# Initialize Flask app
app = Flask(__name__)

# Initialize security headers for all responses
try:
    from university_system.infrastructure.security.flask_security_headers import init_security_headers
    init_security_headers(app)
except ImportError:
    pass  # Security headers module not available

class LogConfig:
    """Configuration management for the log system"""
    
    def __init__(self):
        from university_system.modules.shared.constants import paths
        self.config_file = str(paths.LOG_DIR / "log_config.json")
        self.default_config = {
            "retention_days": 90,
            "auto_archive_days": 30,
            "max_log_size_mb": 100,
            "enable_real_time": True,
            "enable_alerts": True,
            "alert_email": "",
            "smtp_server": "",
            "smtp_port": 587,
            "smtp_username": "",
            "smtp_password": "",
            "enable_encryption": True,
            "api_enabled": False,
            "api_secret_key": os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32)),
            "webhook_secret": "webhook-secret-key-change-this",
            "max_search_results": 1000,
            "enable_analytics": True,
            "chart_export_format": "png"
        }
        self.load_config()
    
    def load_config(self):
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.config = {**self.default_config, **json.load(f)}
            else:
                self.config = self.default_config.copy()
                self.save_config()
        except Exception as e:
            print(f"Error loading config: {e}")
            self.config = self.default_config.copy()
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get(self, key, default=None):
        """Get configuration value"""
        return self.config.get(key, default)
    
    def set(self, key, value):
        """Set configuration value"""
        self.config[key] = value
        self.save_config()

# Create global config instance
config = LogConfig()

# JWT Configuration - now config is defined
app.config['SECRET_KEY'] = config.get('api_secret_key', os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32)))

def token_required(f):
    """Decorator for API authentication.  When Flask/JWT are unavailable
    this decorator still allows the wrapped function to execute, simply
    passing through the original function without enforcing authentication.
    """
    # Define inner wrapper without relying on functools.wraps, since
    # functools may not be available or wraps may be shadowed.
    def decorated(*args, **kwargs):
        """Wrapper function injected by token_required decorator."""
        # If request and jwt are available, attempt to verify the token.
        try:
            token = request.headers.get('Authorization')  # type: ignore
        except Exception:
            token = None
        if not token:
            # In a non-authenticated context, simply call the function with None
            return f(None, *args, **kwargs)
        try:
            if isinstance(token, str) and token.startswith('Bearer '):
                token = token[7:]
            data = jwt.decode(token, app.config.get('SECRET_KEY'), algorithms=['HS256'])  # type: ignore
            current_user = data.get('user_id') if isinstance(data, dict) else None
        except Exception:
            current_user = None
        return f(current_user, *args, **kwargs)
    # Preserve the original function's name to avoid Flask endpoint collisions
    try:
        decorated.__name__ = f.__name__  # type: ignore
    except Exception:
        pass
    return decorated

def admin_required(f):
    """Decorator for admin-only endpoints.  When authentication is not
    enforced, this decorator simply forwards the call."""
    def decorated(current_user, *args, **kwargs):
        """Wrapper function injected by admin_required decorator."""
        # In a real system, check current_user for admin privileges
        return f(current_user, *args, **kwargs)
    # Preserve the original function's name to avoid Flask endpoint collisions
    try:
        decorated.__name__ = f.__name__  # type: ignore
    except Exception:
        pass
    return decorated

# Simple in-memory rate limiter for login
_login_attempts = {}

def _check_login_rate_limit(ip_address):
    """Check if IP has exceeded login rate limit (5 attempts per minute)."""
    import time
    now = time.time()
    attempts = _login_attempts.get(ip_address, [])
    # Remove attempts older than 60 seconds
    attempts = [t for t in attempts if now - t < 60]
    _login_attempts[ip_address] = attempts
    if len(attempts) >= 5:
        return False
    attempts.append(now)
    _login_attempts[ip_address] = attempts
    return True

# Authentication Endpoints
@app.route('/api/auth/login', methods=['POST'])
def login():
    """API login endpoint"""
    # Rate limiting
    client_ip = request.remote_addr
    if not _check_login_rate_limit(client_ip):
        return jsonify({'error': 'Too many login attempts. Please try again later.'}), 429

    data = request.get_json()

    username = data.get('username')
    password = data.get('password')

    # This would typically validate against your user database
    # For demonstration, we'll create a simple token
    if username and password:
        token = jwt.encode({
            'user_id': username,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm='HS256')

        return jsonify({
            'token': token,
            'expires_in': 86400,
            'user_id': username
        })

    return jsonify({'error': 'Invalid credentials'}), 401

# Log Query Endpoints
@app.route('/api/logs/search', methods=['POST'])
@token_required
@admin_required
def search_logs(current_user):
    """Search logs with filters"""
    try:
        filters = request.get_json()
        
        # Validate filters
        allowed_filters = ['date_from', 'date_to', 'user_id', 'username', 
                          'action', 'module', 'status', 'search_text']
        
        validated_filters = {k: v for k, v in filters.items() 
                           if k in allowed_filters and v}
        
        limit = min(filters.get('limit', 100), 1000)  # Max 1000 results
        
        results = log_manager.db.search_logs(validated_filters, limit=limit)
        
        return jsonify({
            'success': True,
            'count': len(results),
            'results': results,
            'filters_applied': validated_filters
        })
        
    except Exception as e:
        logger.error(f"Search logs error: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

@app.route('/api/logs/recent', methods=['GET'])
@token_required
def get_recent_logs(current_user):
    """Get recent logs"""
    try:
        hours = request.args.get('hours', 1, type=int)
        limit = min(request.args.get('limit', 50, type=int), 200)
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        filters = {
            'date_from': cutoff_time.strftime('%Y-%m-%d'),
            'date_to': datetime.now().strftime('%Y-%m-%d')
        }
        
        results = log_manager.db.search_logs(filters, limit=limit)
        
        return jsonify({
            'success': True,
            'count': len(results),
            'results': results,
            'timeframe': f'Last {hours} hours'
        })
        
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

@app.route('/api/logs/user/<user_id>', methods=['GET'])
@token_required
@admin_required
def get_user_logs(current_user, user_id):
    """Get logs for a specific user"""
    try:
        days = request.args.get('days', 7, type=int)
        limit = min(request.args.get('limit', 100, type=int), 500)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        filters = {
            'date_from': start_date.strftime('%Y-%m-%d'),
            'date_to': end_date.strftime('%Y-%m-%d'),
            'user_id': user_id
        }
        
        results = log_manager.db.search_logs(filters, limit=limit)
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'count': len(results),
            'results': results,
            'timeframe': f'Last {days} days'
        })
        
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

# Analytics Endpoints
@app.route('/api/analytics/summary', methods=['GET'])
@token_required
@admin_required
def get_analytics_summary(current_user):
    """Get activity analytics summary"""
    try:
        days = request.args.get('days', 7, type=int)
        
        summary = log_manager.analytics.generate_activity_summary(days)
        
        return jsonify({
            'success': True,
            'summary': summary
        })
        
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

@app.route('/api/analytics/user/<user_id>', methods=['GET'])
@token_required
@admin_required
def get_user_analytics(current_user, user_id):
    """Get analytics for a specific user"""
    try:
        days = request.args.get('days', 30, type=int)
        
        report = log_manager.analytics.generate_user_activity_report(user_id, days)
        
        return jsonify({
            'success': True,
            'report': report
        })
        
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

@app.route('/api/analytics/chart', methods=['POST'])
@token_required
@admin_required
def generate_chart(current_user):
    """Generate and return activity chart"""
    try:
        data = request.get_json()
        days = data.get('days', 7)
        chart_type = data.get('type', 'daily')

        # Generate chart and save to temp file
        temp_path = TEMP_DIR / f"chart_{current_user}_{datetime.now().timestamp()}.png"

        chart_path = log_manager.analytics.create_activity_chart(
            chart_type, days, temp_path
        )
        
        if chart_path and os.path.exists(chart_path):
            return send_file(chart_path, as_attachment=True, 
                           download_name=f'activity_chart_{days}days.png')
        else:
            return jsonify({'error': 'Chart generation failed'}), 500
            
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

# Alert Endpoints
@app.route('/api/alerts', methods=['GET'])
@token_required
@admin_required
def get_alerts(current_user):
    """Get recent alerts"""
    try:
        hours = request.args.get('hours', 24, type=int)
        
        # sqlite3 is imported globally from university_system.infrastructure.database.db
        conn = sqlite3.connect(str(_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM alerts
            WHERE triggered_at > datetime('now', ? || ' hours')
            ORDER BY triggered_at DESC
        ''', (f'-{hours}',))
        
        alerts = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'count': len(alerts),
            'alerts': alerts
        })
        
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

@app.route('/api/alerts/check', methods=['POST'])
@token_required
@admin_required
def run_alert_check(current_user):
    """Manually trigger alert checks"""
    try:
        alerts = log_manager.alerts.run_alert_checks()
        
        return jsonify({
            'success': True,
            'alerts_generated': len(alerts),
            'alerts': alerts
        })
        
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

# Export Endpoints
@app.route('/api/export/logs', methods=['POST'])
@token_required
@admin_required
def export_logs(current_user):
    """Export logs with filters"""
    try:
        data = request.get_json()
        filters = data.get('filters', {})
        format_type = data.get('format', 'json')  # json, csv, excel
        
        # Search logs with filters
        results = log_manager.db.search_logs(filters, limit=10000)
        
        if not results:
            return jsonify({'error': 'No logs found matching criteria'}), 404
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if format_type == 'csv':
            import pandas as pd
            df = pd.DataFrame(results)
            filename = f'logs_export_{timestamp}.csv'
            filepath = TEMP_DIR / filename
            df.to_csv(filepath, index=False)
            
            return send_file(filepath, as_attachment=True, download_name=filename)
            
        elif format_type == 'excel':
            import pandas as pd
            df = pd.DataFrame(results)
            filename = f'logs_export_{timestamp}.xlsx'
            filepath = TEMP_DIR / filename
            df.to_excel(filepath, index=False)
            
            return send_file(filepath, as_attachment=True, download_name=filename)
            
        else:  # JSON
            return jsonify({
                'success': True,
                'count': len(results),
                'export_data': results,
                'filters': filters,
                'exported_at': datetime.now().isoformat()
            })
        
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

# Real-time Endpoints
@app.route('/api/realtime/status', methods=['GET'])
@token_required
def get_realtime_status(current_user):
    """Get real-time monitoring status"""
    return jsonify({
        'success': True,
        'realtime_monitoring': log_manager.monitor.running,
        'subscribers': len(log_manager.monitor.subscribers)
    })

@app.route('/api/realtime/logs/stream', methods=['GET'])
@token_required
def stream_logs(current_user):
    """Server-Sent Events endpoint for real-time log streaming"""
    def generate():
        def log_callback(log_entry):
            return f"data: {json.dumps(log_entry)}\n\n"
        
        log_manager.monitor.subscribe(log_callback)
        
        try:
            yield "data: {\"status\": \"connected\"}\n\n"
            
            while True:
                # This is a simplified version - in production, use proper SSE
                import time
                time.sleep(1)
                yield "data: {\"heartbeat\": true}\n\n"
                
        except GeneratorExit:
            log_manager.monitor.unsubscribe(log_callback)
    
    return app.response_class(generate(), mimetype='text/plain')

# Configuration Endpoints
@app.route('/api/config', methods=['GET'])
@token_required
@admin_required
def get_config(current_user):
    """Get system configuration"""
    return jsonify({
        'success': True,
        'config': log_manager.config.config
    })

@app.route('/api/config', methods=['PUT'])
@token_required
@admin_required
def update_config(current_user):
    """Update system configuration"""
    try:
        data = request.get_json()
        
        # Validate configuration keys
        allowed_keys = [
            'retention_days', 'auto_archive_days', 'max_log_size_mb',
            'enable_real_time', 'enable_alerts', 'max_search_results',
            'enable_analytics'
        ]
        
        updated = {}
        for key, value in data.items():
            if key in allowed_keys:
                log_manager.config.set(key, value)
                updated[key] = value
        
        return jsonify({
            'success': True,
            'updated': updated
        })
        
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

# System Status Endpoints
@app.route('/api/system/status', methods=['GET'])
@token_required
@admin_required
def get_system_status(current_user):
    """Get system status and health"""
    try:
        # Database size
        db_size = os.path.getsize(log_manager.db.db_path) if os.path.exists(log_manager.db.db_path) else 0
        
        # Recent activity count
        recent_filters = {
            'date_from': (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d')
        }
        recent_count = len(log_manager.db.search_logs(recent_filters, limit=10000))
        
        return jsonify({
            'success': True,
            'status': {
                'database_size_bytes': db_size,
                'database_size_mb': round(db_size / 1024 / 1024, 2),
                'realtime_monitoring': log_manager.monitor.running,
                'recent_24h_activities': recent_count,
                'configuration': {
                    'retention_days': log_manager.config.get('retention_days'),
                    'alerts_enabled': log_manager.config.get('enable_alerts'),
                    'analytics_enabled': log_manager.config.get('enable_analytics')
                }
            }
        })
        
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

# Webhook Endpoints
@app.route('/api/webhooks/log', methods=['POST'])
def webhook_log_entry():
    """Webhook endpoint for receiving log entries from external systems"""
    try:
        # Verify webhook authenticity
        webhook_key = request.headers.get('X-Webhook-Key')
        if not webhook_key or not secrets.compare_digest(webhook_key, config.get('webhook_secret', '')):
            return jsonify({'error': 'Invalid webhook key'}), 401

        # Validate timestamp to prevent replay attacks (5 min window)
        webhook_ts = request.headers.get('X-Webhook-Timestamp', '')
        if webhook_ts:
            try:
                ts = datetime.fromisoformat(webhook_ts)
                if abs((datetime.utcnow() - ts).total_seconds()) > 300:
                    return jsonify({'error': 'Request timestamp expired'}), 401
            except ValueError:
                pass

        log_data = request.get_json()
        
        # Validate required fields
        required_fields = ['timestamp', 'user_id', 'username', 'action', 'module']
        if not all(field in log_data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Add default values
        log_data.setdefault('role', 'external')
        log_data.setdefault('status', 'success')
        log_data.setdefault('details', '')
        
        # Store in database
        log_manager.db.insert_log(log_data)
        
        # Trigger real-time updates
        if log_manager.monitor.running:
            log_manager.monitor.add_log_entry(log_data)
        
        return jsonify({
            'success': True,
            'message': 'Log entry received and stored'
        })
        
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

# Error Handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# Health Check
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

class LogSecurity:
    """Security features for log management"""
    
    @staticmethod
    def generate_hash(data):
        """Generate SHA-256 hash for data integrity"""
        return hashlib.sha256(str(data).encode()).hexdigest()
    
    @staticmethod
    def verify_integrity(log_entry, stored_hash):
        """Verify log entry integrity"""
        return LogSecurity.generate_hash(log_entry) == stored_hash
    
    @staticmethod
    def anonymize_data(data, fields_to_anonymize=['username', 'user_id']):
        """Anonymize sensitive data in logs"""
        anonymized = data.copy()
        for field in fields_to_anonymize:
            if field in anonymized:
                # Replace with hashed version
                anonymized[field] = hashlib.md5(str(anonymized[field]).encode()).hexdigest()[:8]
        return anonymized
    
    @staticmethod
    def encrypt_log(log_data, key):
        """Simple encryption for log data (in production, use proper encryption)"""
        # This is a simplified example - use proper encryption libraries in production
        import base64
        encoded = base64.b64encode(json.dumps(log_data).encode()).decode()
        return encoded
    
    @staticmethod
    def decrypt_log(encrypted_data, key):
        """Decrypt log data"""
        import base64
        try:
            decoded = base64.b64decode(encrypted_data.encode()).decode()
            return json.loads(decoded)
        except (ValueError, TypeError, Exception):
            return None

class LogDatabase:
    """SQLite database for enhanced log storage and querying"""

    def __init__(self, db_path=None):
        self.db_path = db_path if db_path else str(_DB_PATH)
        ensure_parent_dir(self.db_path)
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(str(_DB_PATH))
        cursor = conn.cursor()
        
        # Main logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id TEXT NOT NULL,
                username TEXT NOT NULL,
                role TEXT NOT NULL,
                action TEXT NOT NULL,
                module TEXT NOT NULL,
                details TEXT,
                status TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                session_id TEXT,
                hash TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL,
                triggered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                resolved BOOLEAN DEFAULT FALSE,
                resolved_at DATETIME,
                resolved_by TEXT
            )
        ''')
        
        # Saved searches table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS saved_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                user_id TEXT NOT NULL,
                search_params TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_user_id ON logs(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_action ON logs(action)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_module ON logs(module)')
        
        conn.commit()
        conn.close()
    
    def insert_log(self, log_data):
        """Insert a log entry into the database"""
        try:
            conn = sqlite3.connect(str(_DB_PATH))
            cursor = conn.cursor()

            # Generate hash for integrity
            log_hash = LogSecurity.generate_hash(log_data)

            # Handle user_id - convert 'system' to None to avoid FK constraint
            user_id = log_data.get('user_id')
            if user_id == 'system' or (user_id and not str(user_id).isdigit()):
                user_id = None

            cursor.execute('''
                INSERT INTO activity_log
                (timestamp, user_id, username, role, action, module, details, status, hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                log_data.get('timestamp'),
                user_id,
                log_data.get('username'),
                log_data.get('role', ''),
                log_data.get('action'),
                log_data.get('module', ''),
                log_data.get('details', ''),
                log_data.get('status', ''),
                log_hash
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error inserting log: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def search_logs(self, filters, limit=1000):
        """Advanced log search with filters"""
        try:
            conn = sqlite3.connect(str(_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM activity_log WHERE 1=1"
            params = []

            if filters.get('date_from'):
                query += " AND date(timestamp) >= ?"
                params.append(filters['date_from'])

            if filters.get('date_to'):
                query += " AND date(timestamp) <= ?"
                params.append(filters['date_to'])

            if filters.get('user_id'):
                query += " AND user_id = ?"
                params.append(filters['user_id'])

            if filters.get('username'):
                query += " AND username LIKE ?"
                params.append(f"%{filters['username']}%")

            if filters.get('action'):
                query += " AND action = ?"
                params.append(filters['action'])

            if filters.get('module'):
                query += " AND module = ?"
                params.append(filters['module'])

            if filters.get('status'):
                query += " AND status = ?"
                params.append(filters['status'])

            if filters.get('search_text'):
                query += " AND (details LIKE ? OR module LIKE ?)"
                search_term = f"%{filters['search_text']}%"
                params.extend([search_term, search_term])

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()

            return [dict(row) for row in results]
        except Exception as e:
            print(f"Error searching logs: {e}")
            import traceback
            traceback.print_exc()
            return []

class LogAnalytics:
    """Analytics and reporting for logs"""
    
    def __init__(self, db: LogDatabase):
        self.db = db
    
    def generate_activity_summary(self, days=7):
        """Generate activity summary for the last N days"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        filters = {
            'date_from': start_date.strftime('%Y-%m-%d'),
            'date_to': end_date.strftime('%Y-%m-%d')
        }
        
        logs = self.db.search_logs(filters, limit=10000)
        
        if not logs:
            return {"error": "No logs found for the specified period"}
        
        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(logs)
        
        summary = {
            "period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            "total_activities": len(logs),
            "unique_users": df['username'].nunique(),
            "most_active_users": df['username'].value_counts().head(5).to_dict(),
            "activity_by_action": df['action'].value_counts().to_dict(),
            "activity_by_module": df['module'].value_counts().to_dict(),
            "success_rate": (df['status'] == 'success').mean() * 100,
            "failed_activities": len(df[df['status'] == 'failure']),
            "peak_activity_hour": pd.to_datetime(df['timestamp']).dt.hour.value_counts().index[0]
        }
        
        return summary
    
    def generate_user_activity_report(self, user_id, days=30):
        """Generate detailed activity report for a specific user"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        filters = {
            'date_from': start_date.strftime('%Y-%m-%d'),
            'date_to': end_date.strftime('%Y-%m-%d'),
            'user_id': user_id
        }
        
        logs = self.db.search_logs(filters, limit=5000)
        
        if not logs:
            return {"error": f"No activities found for user {user_id}"}
        
        df = pd.DataFrame(logs)
        
        report = {
            "user_id": user_id,
            "username": df['username'].iloc[0],
            "period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            "total_activities": len(logs),
            "activities_by_day": df.groupby(pd.to_datetime(df['timestamp']).dt.date).size().to_dict(),
            "modules_used": df['module'].value_counts().to_dict(),
            "actions_performed": df['action'].value_counts().to_dict(),
            "success_rate": (df['status'] == 'success').mean() * 100,
            "most_active_days": df.groupby(pd.to_datetime(df['timestamp']).dt.date).size().nlargest(5).to_dict(),
            "activity_hours": pd.to_datetime(df['timestamp']).dt.hour.value_counts().to_dict()
        }
        
        return report
    
    def create_activity_chart(self, chart_type="daily", days=7, save_path=None):
        """Create activity visualization charts"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        filters = {
            'date_from': start_date.strftime('%Y-%m-%d'),
            'date_to': end_date.strftime('%Y-%m-%d')
        }
        
        logs = self.db.search_logs(filters, limit=10000)
        
        if not logs:
            print("No data available for chart generation")
            return None
        
        df = pd.DataFrame(logs)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        plt.style.use('seaborn-v0_8' if 'seaborn-v0_8' in plt.style.available else 'default')
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle(f'Activity Analysis - Last {days} Days', fontsize=16)
        
        # Daily activity trend
        daily_activity = df.groupby(df['timestamp'].dt.date).size()
        axes[0, 0].plot(daily_activity.index, daily_activity.values, marker='o')
        axes[0, 0].set_title('Daily Activity Trend')
        axes[0, 0].set_xlabel('Date')
        axes[0, 0].set_ylabel('Number of Activities')
        axes[0, 0].tick_params(axis='x', rotation=45)
        
        # Activity by action type
        action_counts = df['action'].value_counts()
        axes[0, 1].pie(action_counts.values, labels=action_counts.index, autopct='%1.1f%%')
        axes[0, 1].set_title('Activity Distribution by Action Type')
        
        # Hourly activity pattern
        hourly_activity = df['timestamp'].dt.hour.value_counts().sort_index()
        axes[1, 0].bar(hourly_activity.index, hourly_activity.values)
        axes[1, 0].set_title('Activity Pattern by Hour')
        axes[1, 0].set_xlabel('Hour of Day')
        axes[1, 0].set_ylabel('Number of Activities')
        
        # Top modules
        module_counts = df['module'].value_counts().head(10)
        axes[1, 1].barh(module_counts.index, module_counts.values)
        axes[1, 1].set_title('Top 10 Most Used Modules')
        axes[1, 1].set_xlabel('Number of Activities')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Chart saved to {save_path}")
        else:
            plt.show()
        
        plt.close()
        return save_path

class LogAlerts:
    """Alert system for suspicious activities"""
    
    def __init__(self, db: LogDatabase, config: LogConfig):
        self.db = db
        self.config = config
        self.alert_rules = [
            {"name": "Multiple Failed Logins", "check": self.check_failed_logins},
            {"name": "Unusual Activity Hours", "check": self.check_unusual_hours},
            {"name": "Rapid Fire Actions", "check": self.check_rapid_actions},
            {"name": "Admin Actions", "check": self.check_admin_actions}
        ]
    
    def check_failed_logins(self, recent_logs):
        """Check for multiple failed login attempts"""
        failed_logins = defaultdict(int)
        cutoff_time = datetime.now() - timedelta(minutes=15)
        
        for log in recent_logs:
            if (log['action'] == 'login' and 
                log['status'] == 'failure' and
                datetime.fromisoformat(log['timestamp']) > cutoff_time):
                failed_logins[log['user_id']] += 1
        
        alerts = []
        for user_id, count in failed_logins.items():
            if count >= 5:
                alerts.append({
                    "type": "security",
                    "severity": "high",
                    "message": f"User {user_id} has {count} failed login attempts in the last 15 minutes"
                })
        
        return alerts
    
    def check_unusual_hours(self, recent_logs):
        """Check for activities during unusual hours (e.g., 2-6 AM)"""
        alerts = []
        unusual_hours = range(2, 6)
        
        for log in recent_logs:
            log_time = datetime.fromisoformat(log['timestamp'])
            if log_time.hour in unusual_hours:
                alerts.append({
                    "type": "anomaly",
                    "severity": "medium",
                    "message": f"Activity by {log['username']} at unusual hour: {log_time.strftime('%H:%M')}"
                })
        
        return alerts
    
    def check_rapid_actions(self, recent_logs):
        """Check for rapid-fire actions from the same user"""
        user_actions = defaultdict(list)
        cutoff_time = datetime.now() - timedelta(minutes=5)
        
        for log in recent_logs:
            if datetime.fromisoformat(log['timestamp']) > cutoff_time:
                user_actions[log['user_id']].append(log['timestamp'])
        
        alerts = []
        for user_id, timestamps in user_actions.items():
            if len(timestamps) > 20:  # More than 20 actions in 5 minutes
                alerts.append({
                    "type": "anomaly",
                    "severity": "medium",
                    "message": f"User {user_id} performed {len(timestamps)} actions in the last 5 minutes"
                })
        
        return alerts
    
    def check_admin_actions(self, recent_logs):
        """Alert on sensitive admin actions"""
        alerts = []
        sensitive_actions = ['delete', 'system_config', 'user_management']
        
        for log in recent_logs:
            if log['action'] in sensitive_actions or log['module'] in sensitive_actions:
                alerts.append({
                    "type": "audit",
                    "severity": "low",
                    "message": f"Admin action: {log['username']} performed {log['action']} on {log['module']}"
                })
        
        return alerts
    
    def run_alert_checks(self):
        """Run all alert checks on recent logs"""
        # Get logs from the last hour
        cutoff_time = datetime.now() - timedelta(hours=1)
        filters = {
            'date_from': cutoff_time.strftime('%Y-%m-%d'),
            'date_to': datetime.now().strftime('%Y-%m-%d')
        }
        
        recent_logs = self.db.search_logs(filters, limit=1000)
        
        all_alerts = []
        for rule in self.alert_rules:
            try:
                alerts = rule["check"](recent_logs)
                all_alerts.extend(alerts)
            except Exception as e:
                print(f"Error in alert rule {rule['name']}: {e}")
        
        # Store alerts in database
        for alert in all_alerts:
            self.store_alert(alert)
        
        return all_alerts
    
    def store_alert(self, alert):
        """Store alert in database"""
        conn = sqlite3.connect(str(_DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO alerts (alert_type, message, severity)
            VALUES (?, ?, ?)
        ''', (alert['type'], alert['message'], alert['severity']))
        
        conn.commit()
        conn.close()

class RealTimeMonitor:
    """Real-time log monitoring"""
    
    def __init__(self, db: LogDatabase):
        self.db = db
        self.subscribers = []
        self.running = False
        self.log_queue = queue.Queue()
        
    def subscribe(self, callback):
        """Subscribe to real-time log updates"""
        self.subscribers.append(callback)
    
    def unsubscribe(self, callback):
        """Unsubscribe from real-time log updates"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
    
    def notify_subscribers(self, log_entry):
        """Notify all subscribers of new log entry"""
        for callback in self.subscribers:
            try:
                callback(log_entry)
            except Exception as e:
                print(f"Error notifying subscriber: {e}")
    
    def add_log_entry(self, log_entry):
        """Add a new log entry for real-time processing"""
        self.log_queue.put(log_entry)
        self.notify_subscribers(log_entry)
    
    def start_monitoring(self):
        """Start real-time monitoring"""
        self.running = True
        monitor_thread = threading.Thread(target=self._monitor_loop)
        monitor_thread.daemon = True
        monitor_thread.start()
        print("Real-time monitoring started")
    
    def stop_monitoring(self):
        """Stop real-time monitoring"""
        self.running = False
        print("Real-time monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Process queued log entries
                while not self.log_queue.empty():
                    log_entry = self.log_queue.get_nowait()
                    # Process the log entry (store in DB, check alerts, etc.)
                    self.db.insert_log(log_entry)
                
                time.sleep(1)  # Check every second
            except Exception as e:
                print(f"Error in monitoring loop: {e}")

class LogRetention:
    """Log retention and archival management"""
    
    def __init__(self, config: LogConfig, db: LogDatabase):
        self.config = config
        self.db = db
    
    def archive_old_logs(self):
        """Archive logs older than configured days"""
        cutoff_date = datetime.now() - timedelta(days=self.config.get('auto_archive_days', 30))
        
        # Get old logs
        filters = {
            'date_to': cutoff_date.strftime('%Y-%m-%d')
        }
        
        old_logs = self.db.search_logs(filters, limit=50000)
        
        if not old_logs:
            print("No logs to archive")
            return
        
        # Create archive
        archive_path = LOG_DIR / "archives"
        archive_path.mkdir(parents=True, exist_ok=True)
        archive_path = str(archive_path)
        
        archive_file = os.path.join(archive_path, f"logs_archive_{cutoff_date.strftime('%Y%m%d')}.zip")
        
        with zipfile.ZipFile(archive_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Export to JSON and add to zip
            json_data = json.dumps(old_logs, indent=2)
            zipf.writestr(f"archived_logs_{cutoff_date.strftime('%Y%m%d')}.json", json_data)
        
        print(f"Archived {len(old_logs)} logs to {archive_file}")
        
        # Remove old logs from database (in production, be very careful with this)
        # This is commented out for safety
        # self._delete_old_logs(cutoff_date)
    
    def cleanup_old_logs(self):
        """Delete logs older than retention period"""
        retention_days = self.config.get('retention_days', 90)
        cutoff_date = datetime.now() - timedelta(days=retention_days)

        # Clean database entries
        conn = sqlite3.connect(str(_DB_PATH))
        cursor = conn.cursor()

        cursor.execute('DELETE FROM activity_log WHERE timestamp < ?', (cutoff_date.isoformat(),))
        deleted_db_count = cursor.rowcount

        conn.commit()
        conn.close()

        # Clean old log files
        deleted_files_count = 0
        cutoff_timestamp = cutoff_date.timestamp()

        import os
        for filename in os.listdir(LOG_DIR):
            filepath = LOG_DIR / filename
            if filepath.is_file():
                # Check if it's an old log file
                if any(filename.startswith(prefix) for prefix in ['activity.', 'activity_log_', 'enhanced_log_']):
                    try:
                        file_mtime = os.path.getmtime(filepath)
                        if file_mtime < cutoff_timestamp:
                            os.remove(filepath)
                            deleted_files_count += 1
                    except Exception as e:
                        print(f"Warning: Could not delete {filename}: {e}")

        print(f"Deleted {deleted_db_count} database logs and {deleted_files_count} log files older than {retention_days} days")

class EnhancedLogManager:
    """Main enhanced log management class"""
    
    def __init__(self):
        self.config = LogConfig()
        self.db = LogDatabase()
        self.analytics = LogAnalytics(self.db)
        self.alerts = LogAlerts(self.db, self.config)
        self.monitor = RealTimeMonitor(self.db)
        self.retention = LogRetention(self.config, self.db)
        
        # Set up scheduled tasks
        self.setup_scheduled_tasks()
        
        # Start real-time monitoring if enabled
        if self.config.get('enable_real_time'):
            self.monitor.start_monitoring()
    
    def setup_scheduled_tasks(self):
        """Set up automated tasks"""
        # Daily cleanup and archival
        schedule.every().day.at("02:00").do(self.retention.archive_old_logs)
        schedule.every().day.at("03:00").do(self.retention.cleanup_old_logs)
        
        # Hourly alert checks
        schedule.every().hour.do(self.alerts.run_alert_checks)
        
        # Start scheduler thread
        scheduler_thread = threading.Thread(target=self._run_scheduler)
        scheduler_thread.daemon = True
        scheduler_thread.start()
    
    def _run_scheduler(self):
        """Run scheduled tasks"""
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

# Create global log manager instance (but only when needed)
log_manager = None

def get_log_manager():
    """Get the global log manager instance, creating it if necessary"""
    global log_manager
    if log_manager is None:
        log_manager = EnhancedLogManager()
    return log_manager

def display_log_management_menu(auth):
    """Display the basic log management menu"""
    if not auth or not auth.current_user:
        print("You must be logged in to access log management.")
        return
    
    if not auth.check_permission('system_config') and not auth.check_permission('view_logs'):
        print("You don't have permission to access log management.")
        return

    # Initialize log manager if needed
    global log_manager
    if log_manager is None:
        log_manager = get_log_manager()

    while True:
        print("\n" + "="*50)
        print("LOG MANAGEMENT SYSTEM")
        print("="*50)
        print("1. View Recent Activity Logs")
        print("2. Search Activity Logs")
        print("3. Generate Activity Report")
        print("4. System Configuration")
        print("5. Enhanced Log Management")
        print("6. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-6): ")
        
        if choice == '1':
            view_recent_logs(log_manager, auth)
        elif choice == '2':
            search_logs_basic(log_manager, auth)
        elif choice == '3':
            generate_basic_report(log_manager, auth)
        elif choice == '4':
            basic_config_menu(log_manager, auth)
        elif choice == '5':
            display_enhanced_log_menu(log_manager, auth)
        elif choice == '6':
            return
        else:
            print("Invalid choice. Please try again.")

def view_recent_logs(log_manager, auth):
    """View recent activity logs"""
    print("\n📋 RECENT ACTIVITY LOGS")
    print("="*30)
    
    hours = input("Show logs from last how many hours? (default: 24): ")
    try:
        hours = int(hours) if hours else 24
    except ValueError:
        hours = 24
    
    cutoff_time = datetime.now() - timedelta(hours=hours)
    filters = {
        'date_from': cutoff_time.strftime('%Y-%m-%d'),
        'date_to': datetime.now().strftime('%Y-%m-%d')
    }
    
    logs = log_manager.db.search_logs(filters, limit=50)
    
    if not logs:
        print(f"No logs found in the last {hours} hours.")
        return
    
    print(f"\nShowing {len(logs)} logs from the last {hours} hours:")
    print("-" * 80)
    
    for log in logs:
        timestamp = log.get('timestamp', '')[:19]
        user = log.get('username', '')
        action = log.get('action', '')
        module = log.get('module', '')
        status = log.get('status', '')
        
        status_symbol = "✅" if status == "success" else "❌"
        print(f"{timestamp} | {status_symbol} {user:15} | {action:15} | {module}")
    
    input("\nPress Enter to continue...")

def search_logs_basic(log_manager, auth):
    """Basic log search"""
    print("\n🔍 SEARCH LOGS")
    print("="*20)
    
    username = input("Username (optional): ")
    action = input("Action (optional): ")
    module = input("Module (optional): ")
    
    filters = {}
    if username:
        filters['username'] = username
    if action:
        filters['action'] = action
    if module:
        filters['module'] = module
    
    # Default to last 7 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    filters['date_from'] = start_date.strftime('%Y-%m-%d')
    filters['date_to'] = end_date.strftime('%Y-%m-%d')
    
    logs = log_manager.db.search_logs(filters, limit=100)
    
    if not logs:
        print("No logs found matching your criteria.")
        return
    
    print(f"\nFound {len(logs)} logs:")
    print("-" * 80)
    
    for log in logs[:20]:  # Show first 20
        timestamp = log.get('timestamp', '')[:19]
        user = log.get('username', '')
        action = log.get('action', '')
        module = log.get('module', '')
        status = log.get('status', '')
        
        status_symbol = "✅" if status == "success" else "❌"
        print(f"{timestamp} | {status_symbol} {user:15} | {action:15} | {module}")
    
    if len(logs) > 20:
        print(f"... and {len(logs) - 20} more results")
    
    input("\nPress Enter to continue...")

def generate_basic_report(log_manager, auth):
    """Generate basic activity report"""
    print("\n📊 ACTIVITY REPORT")
    print("="*25)
    
    days = input("Generate report for last how many days? (default: 7): ")
    try:
        days = int(days) if days else 7
    except ValueError:
        days = 7
    
    summary = log_manager.analytics.generate_activity_summary(days)
    
    if "error" in summary:
        print(summary["error"])
        return
    
    print(f"\nActivity Summary - Last {days} Days")
    print("="*40)
    print(f"Total Activities: {summary['total_activities']:,}")
    print(f"Unique Users: {summary['unique_users']}")
    print(f"Success Rate: {summary['success_rate']:.1f}%")
    print(f"Failed Activities: {summary['failed_activities']}")
    
    print("\nTop 5 Most Active Users:")
    for user, count in list(summary['most_active_users'].items())[:5]:
        print(f"  {user}: {count} activities")
    
    print("\nTop Actions:")
    for action, count in list(summary['activity_by_action'].items())[:5]:
        print(f"  {action}: {count}")
    
    input("\nPress Enter to continue...")

def basic_config_menu(log_manager, auth):
    """Basic configuration menu"""
    print("\n⚙️ BASIC CONFIGURATION")
    print("="*25)
    
    print("Current Settings:")
    print(f"1. Log Retention: {log_manager.config.get('retention_days')} days")
    print(f"2. Real-time Monitoring: {log_manager.config.get('enable_real_time')}")
    print(f"3. Alerts Enabled: {log_manager.config.get('enable_alerts')}")
    print("4. Return")
    
    choice = input("\nSelect setting to change (1-4): ")
    
    if choice == '1':
        days = input("Enter new retention period (days): ")
        try:
            days = int(days)
            log_manager.config.set('retention_days', days)
            print(f"Retention period set to {days} days")
        except ValueError:
            print("Invalid number")
    elif choice == '2':
        enable = input("Enable real-time monitoring? (y/n): ")
        log_manager.config.set('enable_real_time', enable.lower() == 'y')
        print(f"Real-time monitoring {'enabled' if enable.lower() == 'y' else 'disabled'}")
    elif choice == '3':
        enable = input("Enable alerts? (y/n): ")
        log_manager.config.set('enable_alerts', enable.lower() == 'y')
        print(f"Alerts {'enabled' if enable.lower() == 'y' else 'disabled'}")

def display_enhanced_log_menu(log_manager, auth):
    """Enhanced log management menu"""
    if not auth or not auth.current_user:
        print("You must be logged in to access log management.")
        return
    
    if not auth.check_permission('system_config') and not auth.check_permission('view_logs'):
        print("You don't have permission to access log management.")
        return

    while True:
        print("\n" + "="*60)
        print("ENHANCED LOG MANAGEMENT SYSTEM")
        print("="*60)
        print("📊 ANALYTICS & REPORTS")
        print("1.  Activity Dashboard")
        print("2.  Generate Activity Summary")
        print("3.  User Activity Report")
        print("4.  Create Activity Charts")
        print("5.  Scheduled Reports")
        
        print("\n🔍 SEARCH & MONITORING")
        print("6.  Advanced Log Search")
        print("7.  Saved Searches")
        print("8.  Real-time Monitor")
        print("9.  View Alerts")
        
        print("\n🔒 SECURITY & COMPLIANCE")
        print("10. Security Analysis")
        print("11. Data Retention Settings")
        print("12. Log Integrity Check")
        print("13. Anonymize Data")
        
        print("\n📤 EXPORT & INTEGRATION")
        print("14. Enhanced Export")
        print("15. Bulk Operations")
        print("16. API Management")
        
        print("\n⚙️  ADMINISTRATION")
        print("17. System Configuration")
        print("18. Database Maintenance")
        print("19. Performance Metrics")
        print("20. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-20): ")
        
        try:
            if choice == '1':
                display_activity_dashboard(log_manager, auth)
            elif choice == '2':
                generate_activity_summary_menu(log_manager, auth)
            elif choice == '3':
                user_activity_report_menu(log_manager, auth)
            elif choice == '4':
                create_charts_menu(log_manager, auth)
            elif choice == '5':
                scheduled_reports_menu(log_manager, auth)
            elif choice == '6':
                advanced_search_menu(log_manager, auth)
            elif choice == '7':
                saved_searches_menu(log_manager, auth)
            elif choice == '8':
                real_time_monitor_menu(log_manager, auth)
            elif choice == '9':
                view_alerts_menu(log_manager, auth)
            elif choice == '10':
                security_analysis_menu(log_manager, auth)
            elif choice == '11':
                retention_settings_menu(log_manager, auth)
            elif choice == '12':
                integrity_check_menu(log_manager, auth)
            elif choice == '13':
                anonymize_data_menu(log_manager, auth)
            elif choice == '14':
                enhanced_export_menu(log_manager, auth)
            elif choice == '15':
                bulk_operations_menu(log_manager, auth)
            elif choice == '16':
                api_management_menu(log_manager, auth)
            elif choice == '17':
                system_config_menu(log_manager, auth)
            elif choice == '18':
                database_maintenance_menu(log_manager, auth)
            elif choice == '19':
                performance_metrics_menu(log_manager, auth)
            elif choice == '20':
                return
            else:
                print("Invalid choice. Please try again.")
        except Exception as e:
            print(f"Error: {e}")
            print("Please try again.")

# Individual menu functions for each feature
def display_activity_dashboard(log_manager, auth):
    """Display activity dashboard"""
    print("\n📊 ACTIVITY DASHBOARD")
    print("="*50)
    
    # Quick stats for last 7 days
    summary = log_manager.analytics.generate_activity_summary(7)
    
    if "error" in summary:
        print(summary["error"])
        return
    
    print(f"Period: {summary['period']}")
    print(f"Total Activities: {summary['total_activities']:,}")
    print(f"Unique Users: {summary['unique_users']}")
    print(f"Success Rate: {summary['success_rate']:.1f}%")
    print(f"Failed Activities: {summary['failed_activities']}")
    print(f"Peak Activity Hour: {summary['peak_activity_hour']}:00")
    
    print("\n🔥 Most Active Users:")
    for user, count in list(summary['most_active_users'].items())[:5]:
        print(f"  {user}: {count} activities")
    
    print("\n📋 Activity by Action:")
    for action, count in list(summary['activity_by_action'].items())[:5]:
        print(f"  {action}: {count}")
    
    print("\n🔧 Activity by Module:")
    for module, count in list(summary['activity_by_module'].items())[:5]:
        print(f"  {module}: {count}")
    
    input("\nPress Enter to continue...")

def generate_activity_summary_menu(log_manager, auth):
    """Generate activity summary menu"""
    print("\n📊 GENERATE ACTIVITY SUMMARY")
    print("="*40)
    
    days = input("Enter number of days to analyze (default: 7): ")
    try:
        days = int(days) if days else 7
    except ValueError:
        days = 7
    
    print(f"\nGenerating summary for last {days} days...")
    summary = log_manager.analytics.generate_activity_summary(days)
    
    if "error" in summary:
        print(summary["error"])
        return
    
    # Display detailed summary
    print("\n" + "="*60)
    print(f"ACTIVITY SUMMARY - LAST {days} DAYS")
    print("="*60)
    print(f"Period: {summary['period']}")
    print(f"Total Activities: {summary['total_activities']:,}")
    print(f"Unique Users: {summary['unique_users']}")
    print(f"Success Rate: {summary['success_rate']:.2f}%")
    print(f"Failed Activities: {summary['failed_activities']}")
    print(f"Peak Activity Hour: {summary['peak_activity_hour']}:00")
    
    print(f"\n{'Top Users':<20} {'Activities':<10}")
    print("-" * 30)
    for user, count in list(summary['most_active_users'].items())[:10]:
        print(f"{user:<20} {count:<10}")
    
    print(f"\n{'Actions':<20} {'Count':<10}")
    print("-" * 30)
    for action, count in summary['activity_by_action'].items():
        print(f"{action:<20} {count:<10}")
    
    print(f"\n{'Modules':<20} {'Count':<10}")
    print("-" * 30)
    for module, count in summary['activity_by_module'].items():
        print(f"{module:<20} {count:<10}")
    
    # Option to export
    export = input("\nExport summary to file? (y/n): ")
    if export.lower() == 'y':
        filename = f"activity_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        reports_dir = LOG_DIR / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        filepath = str(reports_dir / filename)
        
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"Summary exported to {filepath}")
    
    input("\nPress Enter to continue...")

def user_activity_report_menu(log_manager, auth):
    """User activity report menu"""
    print("\n👤 USER ACTIVITY REPORT")
    print("="*30)
    
    user_id = input("Enter user ID: ")
    if not user_id:
        print("User ID is required.")
        return
    
    days = input("Enter number of days to analyze (default: 30): ")
    try:
        days = int(days) if days else 30
    except ValueError:
        days = 30
    
    print(f"\nGenerating report for user {user_id} (last {days} days)...")
    
    report = log_manager.analytics.generate_user_activity_report(user_id, days)
    
    if "error" in report:
        print(report["error"])
        return
    
    # Display report
    print("\n" + "="*60)
    print(f"USER ACTIVITY REPORT: {report['username']} ({report['user_id']})")
    print("="*60)
    print(f"Period: {report['period']}")
    print(f"Total Activities: {report['total_activities']:,}")
    print(f"Success Rate: {report['success_rate']:.2f}%")
    
    print(f"\n{'Modules Used':<25} {'Count':<10}")
    print("-" * 35)
    for module, count in list(report['modules_used'].items())[:10]:
        print(f"{module:<25} {count:<10}")
    
    print(f"\n{'Actions Performed':<25} {'Count':<10}")
    print("-" * 35)
    for action, count in report['actions_performed'].items():
        print(f"{action:<25} {count:<10}")
    
    print(f"\n{'Most Active Hours':<15} {'Activities':<10}")
    print("-" * 25)
    sorted_hours = sorted(report['activity_hours'].items(), key=lambda x: x[1], reverse=True)
    for hour, count in sorted_hours[:5]:
        print(f"{hour:02d}:00{'':<9} {count:<10}")
    
    input("\nPress Enter to continue...")

def create_charts_menu(log_manager, auth):
    """Create activity charts menu"""
    print("\n📈 CREATE ACTIVITY CHARTS")
    print("="*30)
    
    days = input("Enter number of days to analyze (default: 7): ")
    try:
        days = int(days) if days else 7
    except ValueError:
        days = 7
    
    save_path = input("Enter save path (or press Enter for auto-path): ")
    if not save_path:
        charts_dir = LOG_DIR / "charts"
        charts_dir.mkdir(parents=True, exist_ok=True)
        save_path = str(charts_dir / f"activity_chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
    
    print(f"\nGenerating activity charts for last {days} days...")
    
    try:
        result_path = log_manager.analytics.create_activity_chart("daily", days, save_path)
        if result_path:
            print(f"Charts saved to: {result_path}")
        else:
            print("Chart generation completed (displayed on screen)")
    except Exception as e:
        print(f"Error generating charts: {e}")
    
    input("\nPress Enter to continue...")

def advanced_search_menu(log_manager, auth):
    """Advanced search menu"""
    print("\n🔍 ADVANCED LOG SEARCH")
    print("="*30)
    
    print("Enter search criteria (leave blank to skip):")
    
    filters = {}
    
    date_from = input("From date (YYYY-MM-DD): ")
    if date_from:
        try:
            datetime.strptime(date_from, "%Y-%m-%d")
            filters['date_from'] = date_from
        except ValueError:
            print("Invalid date format")
            return
    
    date_to = input("To date (YYYY-MM-DD): ")
    if date_to:
        try:
            datetime.strptime(date_to, "%Y-%m-%d")
            filters['date_to'] = date_to
        except ValueError:
            print("Invalid date format")
            return
    
    user_id = input("User ID: ")
    if user_id:
        filters['user_id'] = user_id
    
    username = input("Username (supports partial match): ")
    if username:
        filters['username'] = username
    
    action = input("Action (login, logout, create, read, update, delete): ")
    if action:
        filters['action'] = action
    
    module = input("Module: ")
    if module:
        filters['module'] = module
    
    status = input("Status (success, failure): ")
    if status:
        filters['status'] = status
    
    search_text = input("Search in details: ")
    if search_text:
        filters['search_text'] = search_text
    
    max_results = input("Maximum results (default: 100): ")
    try:
        max_results = int(max_results) if max_results else 100
    except ValueError:
        max_results = 100
    
    print(f"\nSearching logs...")
    
    results = log_manager.db.search_logs(filters, limit=max_results)
    
    if not results:
        print("No logs found matching the criteria.")
        return
    
    # Display results
    print(f"\nFound {len(results)} logs:")
    print("="*80)
    
    headers = ["Time", "User", "Action", "Module", "Status", "Details"]
    table_data = []
    
    for log in results[:20]:  # Show first 20
        details = log.get('details', '')
        if len(details) > 40:
            details = details[:37] + '...'
        
        table_data.append([
            log.get('timestamp', '')[:16],  # Truncate timestamp
            f"{log.get('username', '')}",
            log.get('action', ''),
            log.get('module', ''),
            log.get('status', ''),
            details
        ])
    
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    if len(results) > 20:
        print(f"\n... and {len(results) - 20} more results")
    
    # Options
    print("\nOptions:")
    print("1. Export results")
    print("2. Save search")
    print("3. View more details")
    print("4. Return")
    
    choice = input("Choose option: ")
    
    if choice == '1':
        export_search_results(results, filters)
    elif choice == '2':
        save_search(log_manager, auth, filters)
    elif choice == '3':
        view_detailed_results(results)

def export_search_results(results, filters):
    """Export search results"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    print("\nExport format:")
    print("1. CSV")
    print("2. JSON")
    print("3. Excel")
    
    format_choice = input("Choose format: ")

    export_dir = LOG_DIR / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    export_dir = str(export_dir)
    
    if format_choice == '1':
        filename = os.path.join(export_dir, f"search_results_{timestamp}.csv")
        df = pd.DataFrame(results)
        df.to_csv(filename, index=False)
    elif format_choice == '2':
        filename = os.path.join(export_dir, f"search_results_{timestamp}.json")
        with open(filename, 'w') as f:
            json.dump({"filters": filters, "results": results}, f, indent=2)
    elif format_choice == '3':
        filename = os.path.join(export_dir, f"search_results_{timestamp}.xlsx")
        df = pd.DataFrame(results)
        df.to_excel(filename, index=False)
    else:
        print("Invalid format choice")
        return
    
    print(f"Results exported to: {filename}")

def save_search(log_manager, auth, filters):
    """Save search filters for later use"""
    name = input("Enter name for this search: ")
    if not name:
        print("Search name is required")
        return
    
    try:
        conn = sqlite3.connect(str(_DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO saved_searches (name, user_id, search_params)
            VALUES (?, ?, ?)
        ''', (name, auth.current_user['id'], json.dumps(filters)))
        
        conn.commit()
        conn.close()
        
        print(f"Search '{name}' saved successfully!")
    except Exception as e:
        print(f"Error saving search: {e}")

def view_detailed_results(results):
    """View detailed results"""
    if not results:
        return
    
    print("\nDetailed Results:")
    print("="*60)
    
    for i, log in enumerate(results[:10], 1):  # Show first 10 in detail
        print(f"\n{i}. Log Entry:")
        print(f"   Timestamp: {log.get('timestamp', 'N/A')}")
        print(f"   User: {log.get('username', 'N/A')} (ID: {log.get('user_id', 'N/A')})")
        print(f"   Role: {log.get('role', 'N/A')}")
        print(f"   Action: {log.get('action', 'N/A')}")
        print(f"   Module: {log.get('module', 'N/A')}")
        print(f"   Status: {log.get('status', 'N/A')}")
        print(f"   Details: {log.get('details', 'N/A')}")
        if log.get('ip_address'):
            print(f"   IP Address: {log.get('ip_address')}")
        print("-" * 50)
    
    if len(results) > 10:
        print(f"\n... and {len(results) - 10} more entries")
    
    input("\nPress Enter to continue...")

def saved_searches_menu(log_manager, auth):
    """Saved searches management"""
    print("\n💾 SAVED SEARCHES")
    print("="*20)
    
    try:
        conn = sqlite3.connect(str(_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM saved_searches 
            WHERE user_id = ? 
            ORDER BY created_at DESC
        ''', (auth.current_user['id'],))
        
        searches = cursor.fetchall()
        conn.close()
        
        if not searches:
            print("No saved searches found.")
            return
        
        print("\nYour saved searches:")
        for i, search in enumerate(searches, 1):
            print(f"{i}. {search['name']} (created: {search['created_at'][:19]})")
        
        print(f"\n{len(searches)+1}. Return")
        
        choice = input("Select search to run: ")
        
        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(searches):
                selected_search = searches[choice_num - 1]
                filters = json.loads(selected_search['search_params'])
                
                print(f"\nRunning search: {selected_search['name']}")
                results = log_manager.db.search_logs(filters, limit=100)
                
                if results:
                    print(f"Found {len(results)} results")
                    view_detailed_results(results[:5])  # Show first 5
                else:
                    print("No results found")
            
        except ValueError:
            print("Invalid choice")
            
    except Exception as e:
        print(f"Error accessing saved searches: {e}")
    
    input("\nPress Enter to continue...")

def real_time_monitor_menu(log_manager, auth):
    """Real-time monitoring menu"""
    print("\n⏱️  REAL-TIME LOG MONITOR")
    print("="*30)
    
    if not log_manager.monitor.running:
        start = input("Real-time monitoring is not running. Start it? (y/n): ")
        if start.lower() == 'y':
            log_manager.monitor.start_monitoring()
    
    print("Real-time monitor is active.")
    print("Monitoring recent log activity...")
    print("Press Ctrl+C to stop monitoring")
    
    def print_log_update(log_entry):
        """Callback for real-time log updates"""
        timestamp = log_entry.get('timestamp', '')[:19]
        user = log_entry.get('username', '')
        action = log_entry.get('action', '')
        module = log_entry.get('module', '')
        status = log_entry.get('status', '')
        
        status_symbol = "✅" if status == "success" else "❌"
        print(f"{timestamp} | {status_symbol} {user} - {action} on {module}")
    
    # Subscribe to updates
    log_manager.monitor.subscribe(print_log_update)
    
    try:
        # Show recent activity
        recent_filters = {
            'date_from': (datetime.now() - timedelta(hours=1)).strftime('%Y-%m-%d'),
            'date_to': datetime.now().strftime('%Y-%m-%d')
        }
        recent_logs = log_manager.db.search_logs(recent_filters, limit=10)
        
        print(f"\nLast 10 activities:")
        for log in recent_logs:
            print_log_update(log)
        
        print(f"\nMonitoring live activity... (Press Enter to stop)")
        input()
        
    except KeyboardInterrupt:
        pass
    finally:
        log_manager.monitor.unsubscribe(print_log_update)
        print("\nStopped real-time monitoring")

def view_alerts_menu(log_manager, auth):
    """View alerts menu"""
    print("\n🚨 SECURITY ALERTS")
    print("="*20)
    
    # Run alert checks
    print("Running alert checks...")
    alerts = log_manager.alerts.run_alert_checks()
    
    if not alerts:
        print("No new alerts found.")
    else:
        print(f"Found {len(alerts)} alerts:")
        
        for i, alert in enumerate(alerts, 1):
            severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(alert['severity'], "⚪")
            print(f"{i}. {severity_icon} [{alert['type'].upper()}] {alert['message']}")
    
    # Show recent alerts from database
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM alerts 
        WHERE triggered_at > datetime('now', '-24 hours')
        ORDER BY triggered_at DESC
        LIMIT 20
    ''')
    
    recent_alerts = cursor.fetchall()
    conn.close()
    
    if recent_alerts:
        print(f"\nRecent alerts (last 24 hours):")
        for alert in recent_alerts:
            severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(alert['severity'], "⚪")
            resolved_status = "✅ Resolved" if alert['resolved'] else "❌ Active"
            print(f"{severity_icon} {alert['triggered_at'][:19]} - {alert['message']} ({resolved_status})")
    
    input("\nPress Enter to continue...")

def security_analysis_menu(log_manager, auth):
    """Security analysis menu"""
    print("\n🔒 SECURITY ANALYSIS")
    print("="*25)
    
    print("1. Failed Login Analysis")
    print("2. Unusual Activity Detection")
    print("3. Admin Action Audit")
    print("4. User Behavior Analysis")
    print("5. Return")
    
    choice = input("Choose analysis: ")
    
    if choice == '1':
        analyze_failed_logins(log_manager)
    elif choice == '2':
        detect_unusual_activity(log_manager)
    elif choice == '3':
        audit_admin_actions(log_manager)
    elif choice == '4':
        analyze_user_behavior(log_manager)

def analyze_failed_logins(log_manager):
    """Analyze failed login attempts"""
    print("\n🔐 FAILED LOGIN ANALYSIS")
    print("="*30)
    
    # Get failed logins from last 24 hours
    filters = {
        'date_from': (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d'),
        'action': 'login',
        'status': 'failure'
    }
    
    failed_logins = log_manager.db.search_logs(filters, limit=1000)
    
    if not failed_logins:
        print("No failed logins found in the last 24 hours.")
        return
    
    # Analyze by user
    user_failures = defaultdict(int)
    for login in failed_logins:
        user_failures[login['username']] += 1
    
    print(f"Total failed logins: {len(failed_logins)}")
    print(f"Unique users with failures: {len(user_failures)}")
    
    print("\nTop users with failed logins:")
    sorted_failures = sorted(user_failures.items(), key=lambda x: x[1], reverse=True)
    for user, count in sorted_failures[:10]:
        print(f"  {user}: {count} failures")
    
    # Users with excessive failures (potential brute force)
    suspicious_users = [user for user, count in user_failures.items() if count >= 5]
    if suspicious_users:
        print(f"\n⚠️ Users with 5+ failed logins (potential brute force):")
        for user in suspicious_users:
            print(f"  {user}: {user_failures[user]} failures")
    
    input("\nPress Enter to continue...")

def detect_unusual_activity(log_manager):
    """Detect unusual activity patterns"""
    print("\n🕵️ UNUSUAL ACTIVITY DETECTION")
    print("="*35)
    
    # Get activities from last 7 days
    filters = {
        'date_from': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    }
    
    activities = log_manager.db.search_logs(filters, limit=5000)
    
    if not activities:
        print("No activities found for analysis.")
        return
    
    # Analyze by hour
    hour_activity = defaultdict(int)
    unusual_hours = []
    
    for activity in activities:
        try:
            hour = datetime.fromisoformat(activity['timestamp']).hour
            hour_activity[hour] += 1

            # Flag activities between 2-6 AM as unusual
            if 2 <= hour <= 6:
                unusual_hours.append(activity)
        except (ValueError, KeyError, TypeError):
            continue
    
    print("Activity by hour of day:")
    for hour in range(24):
        count = hour_activity.get(hour, 0)
        bar = "█" * (count // 10)  # Simple bar chart
        print(f"{hour:02d}:00 | {count:4d} | {bar}")
    
    if unusual_hours:
        print(f"\n⚠️ Activities during unusual hours (2-6 AM): {len(unusual_hours)}")
        recent_unusual = unusual_hours[-5:]  # Show last 5
        for activity in recent_unusual:
            timestamp = activity['timestamp'][:19]
            user = activity['username']
            action = activity['action']
            print(f"  {timestamp} - {user}: {action}")
    
    input("\nPress Enter to continue...")

def audit_admin_actions(log_manager):
    """Audit administrative actions"""
    print("\n👨‍💼 ADMIN ACTION AUDIT")
    print("="*25)
    
    # Get admin actions from last 30 days
    filters = {
        'date_from': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
        'role': 'admin'
    }
    
    admin_actions = log_manager.db.search_logs(filters, limit=1000)
    
    if not admin_actions:
        print("No admin actions found in the last 30 days.")
        return
    
    # Categorize actions
    sensitive_actions = ['delete', 'user_management', 'system_config']
    regular_actions = ['create', 'read', 'update']
    
    sensitive_count = 0
    regular_count = 0
    action_breakdown = defaultdict(int)
    admin_breakdown = defaultdict(int)
    
    for action in admin_actions:
        action_type = action['action']
        admin_user = action['username']
        
        action_breakdown[action_type] += 1
        admin_breakdown[admin_user] += 1
        
        if action_type in sensitive_actions:
            sensitive_count += 1
        else:
            regular_count += 1
    
    print(f"Total admin actions: {len(admin_actions)}")
    print(f"Sensitive actions: {sensitive_count}")
    print(f"Regular actions: {regular_count}")
    
    print("\nActions by type:")
    for action_type, count in sorted(action_breakdown.items(), key=lambda x: x[1], reverse=True):
        sensitivity = "⚠️" if action_type in sensitive_actions else "✅"
        print(f"  {sensitivity} {action_type}: {count}")
    
    print("\nActions by admin:")
    for admin, count in sorted(admin_breakdown.items(), key=lambda x: x[1], reverse=True):
        print(f"  {admin}: {count} actions")
    
    # Show recent sensitive actions
    recent_sensitive = [a for a in admin_actions if a['action'] in sensitive_actions][-10:]
    if recent_sensitive:
        print("\nRecent sensitive admin actions:")
        for action in recent_sensitive:
            timestamp = action['timestamp'][:19]
            user = action['username']
            action_type = action['action']
            module = action['module']
            print(f"  {timestamp} - {user}: {action_type} on {module}")
    
    input("\nPress Enter to continue...")

def analyze_user_behavior(log_manager):
    """Analyze user behavior patterns"""
    print("\n👥 USER BEHAVIOR ANALYSIS")
    print("="*30)
    
    # Get activities from last 7 days
    filters = {
        'date_from': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    }
    
    activities = log_manager.db.search_logs(filters, limit=5000)
    
    if not activities:
        print("No activities found for analysis.")
        return
    
    # Analyze user patterns
    user_stats = defaultdict(lambda: {
        'total_actions': 0,
        'unique_modules': set(),
        'actions_by_hour': defaultdict(int),
        'success_rate': 0,
        'failures': 0
    })
    
    for activity in activities:
        user = activity['username']
        stats = user_stats[user]
        
        stats['total_actions'] += 1
        stats['unique_modules'].add(activity['module'])
        
        try:
            hour = datetime.fromisoformat(activity['timestamp']).hour
            stats['actions_by_hour'][hour] += 1
        except (ValueError, KeyError, TypeError):
            pass
        
        if activity['status'] == 'failure':
            stats['failures'] += 1
    
    # Calculate success rates
    for user, stats in user_stats.items():
        if stats['total_actions'] > 0:
            stats['success_rate'] = ((stats['total_actions'] - stats['failures']) / stats['total_actions']) * 100
        stats['unique_modules'] = len(stats['unique_modules'])
    
    # Sort by activity level
    sorted_users = sorted(user_stats.items(), key=lambda x: x[1]['total_actions'], reverse=True)
    
    print(f"User behavior analysis for {len(sorted_users)} users:")
    print(f"{'User':<15} {'Actions':<8} {'Modules':<8} {'Success%':<8} {'Failures':<8}")
    print("-" * 60)
    
    for user, stats in sorted_users[:15]:  # Top 15 users
        print(f"{user:<15} {stats['total_actions']:<8} {stats['unique_modules']:<8} "
              f"{stats['success_rate']:<7.1f}% {stats['failures']:<8}")
    
    # Identify unusual patterns
    print("\nUnusual patterns detected:")
    
    # Users with low success rates
    low_success_users = [(user, stats) for user, stats in user_stats.items() 
                        if stats['success_rate'] < 80 and stats['total_actions'] > 10]
    
    if low_success_users:
        print("Users with low success rates (<80%):")
        for user, stats in low_success_users:
            print(f"  {user}: {stats['success_rate']:.1f}% success rate ({stats['failures']} failures)")
    
    # Users with very high activity
    high_activity_users = [(user, stats) for user, stats in user_stats.items() 
                          if stats['total_actions'] > 100]
    
    if high_activity_users:
        print("Users with very high activity (>100 actions):")
        for user, stats in high_activity_users:
            print(f"  {user}: {stats['total_actions']} actions")
    
    input("\nPress Enter to continue...")

def retention_settings_menu(log_manager, auth):
    """Data retention settings menu"""
    print("\n🗄️ DATA RETENTION SETTINGS")
    print("="*30)
    
    current_retention = log_manager.config.get('retention_days', 90)
    current_archive = log_manager.config.get('auto_archive_days', 30)
    
    print(f"Current Settings:")
    print(f"Log Retention: {current_retention} days")
    print(f"Auto Archive: {current_archive} days")
    
    print("\n1. Change retention period")
    print("2. Change archive period")
    print("3. Manual archive")
    print("4. Manual cleanup")
    print("5. Return")
    
    choice = input("Choose option: ")
    
    if choice == '1':
        new_retention = input(f"Enter new retention period in days (current: {current_retention}): ")
        try:
            days = int(new_retention)
            log_manager.config.set('retention_days', days)
            print(f"Retention period updated to {days} days")
        except ValueError:
            print("Invalid number")
    
    elif choice == '2':
        new_archive = input(f"Enter new archive period in days (current: {current_archive}): ")
        try:
            days = int(new_archive)
            log_manager.config.set('auto_archive_days', days)
            print(f"Archive period updated to {days} days")
        except ValueError:
            print("Invalid number")
    
    elif choice == '3':
        confirm = input("Archive old logs now? This may take some time (y/n): ")
        if confirm.lower() == 'y':
            log_manager.retention.archive_old_logs()
    
    elif choice == '4':
        confirm = input("⚠️ Delete old logs permanently? This cannot be undone! (y/n): ")
        if confirm.lower() == 'y':
            confirm2 = input("Type 'DELETE' to confirm: ")
            if confirm2 == 'DELETE':
                log_manager.retention.cleanup_old_logs()
            else:
                print("Cleanup cancelled")

def integrity_check_menu(log_manager, auth):
    """Log integrity check menu"""
    print("\n🔍 LOG INTEGRITY CHECK")
    print("="*25)
    
    print("Checking log integrity...")
    
    # Sample check of recent logs
    filters = {
        'date_from': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    }
    
    recent_logs = log_manager.db.search_logs(filters, limit=1000)
    
    if not recent_logs:
        print("No recent logs to check.")
        return
    
    corrupted_count = 0
    checked_count = 0
    
    for log in recent_logs:
        if log.get('hash'):
            # Verify hash
            log_data = {k: v for k, v in log.items() if k != 'hash'}
            calculated_hash = LogSecurity.generate_hash(log_data)
            
            if calculated_hash != log['hash']:
                corrupted_count += 1
            
            checked_count += 1
    
    print(f"Integrity check completed:")
    print(f"Logs checked: {checked_count}")
    print(f"Corrupted logs: {corrupted_count}")
    
    if corrupted_count > 0:
        print("⚠️ Warning: Some logs may have been tampered with!")
    else:
        print("✅ All checked logs passed integrity verification")
    
    input("\nPress Enter to continue...")

def anonymize_data_menu(log_manager, auth):
    """Data anonymization menu"""
    print("\n🔒 DATA ANONYMIZATION")
    print("="*25)
    
    print("⚠️ Warning: This will anonymize user data in logs.")
    print("This operation cannot be reversed!")
    
    confirm = input("Continue? (y/n): ")
    if confirm.lower() != 'y':
        return
    
    # Get date range for anonymization
    days = input("Anonymize logs older than how many days? (default: 90): ")
    try:
        days = int(days) if days else 90
    except ValueError:
        days = 90
    
    cutoff_date = datetime.now() - timedelta(days=days)
    
    print(f"Anonymizing logs older than {cutoff_date.strftime('%Y-%m-%d')}...")
    
    # This is a simplified example - in production, implement proper anonymization
    filters = {
        'date_to': cutoff_date.strftime('%Y-%m-%d')
    }
    
    old_logs = log_manager.db.search_logs(filters, limit=10000)
    
    if not old_logs:
        print("No logs found for anonymization.")
        return
    
    anonymized_count = 0
    
    # In a real implementation, you would update the database
    # For demo purposes, we'll just show what would be anonymized
    for log in old_logs[:10]:  # Show first 10 as examples
        anonymized_log = LogSecurity.anonymize_data(log)
        print(f"Original: {log['username']} -> Anonymized: {anonymized_log['username']}")
        anonymized_count += 1
    
    print(f"\nWould anonymize {len(old_logs)} log entries")
    print("(This is a demonstration - actual anonymization not performed)")
    
    input("\nPress Enter to continue...")

def enhanced_export_menu(log_manager, auth):
    """Enhanced export menu"""
    print("\n📤 ENHANCED EXPORT")
    print("="*20)
    
    print("1. Export with filters")
    print("2. Scheduled export")
    print("3. Custom format export")
    print("4. Bulk export by date range")
    print("5. Return")
    
    choice = input("Choose export option: ")
    
    if choice == '1':
        export_with_filters(log_manager, auth)
    elif choice == '2':
        schedule_export(log_manager, auth)
    elif choice == '3':
        custom_format_export(log_manager, auth)
    elif choice == '4':
        bulk_export_by_date(log_manager, auth)

def export_with_filters(log_manager, auth):
    """Export logs with custom filters"""
    print("\n📊 EXPORT WITH FILTERS")
    print("="*25)
    
    # Get filters from user (simplified version)
    filters = {}
    
    user_filter = input("Filter by username (optional): ")
    if user_filter:
        filters['username'] = user_filter
    
    module_filter = input("Filter by module (optional): ")
    if module_filter:
        filters['module'] = module_filter
    
    days = input("Export last how many days? (default: 7): ")
    try:
        days = int(days) if days else 7
    except ValueError:
        days = 7
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    filters['date_from'] = start_date.strftime('%Y-%m-%d')
    filters['date_to'] = end_date.strftime('%Y-%m-%d')
    
    # Export
    results = log_manager.db.search_logs(filters, limit=10000)
    
    if not results:
        print("No logs found matching filters.")
        return

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    export_dir = LOG_DIR / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    export_dir = str(export_dir)
    
    # Export as JSON
    filename = os.path.join(export_dir, f"filtered_export_{timestamp}.json")
    
    export_data = {
        "export_info": {
            "timestamp": datetime.now().isoformat(),
            "filters": filters,
            "record_count": len(results)
        },
        "logs": results
    }
    
    with open(filename, 'w') as f:
        json.dump(export_data, f, indent=2)
    
    print(f"Exported {len(results)} logs to {filename}")

def bulk_operations_menu(log_manager, auth):
    """Bulk operations menu"""
    print("\n📦 BULK OPERATIONS")
    print("="*20)
    
    print("1. Bulk log import")
    print("2. Bulk data cleanup")
    print("3. Bulk export by criteria")
    print("4. Database optimization")
    print("5. Return")
    
    choice = input("Choose operation: ")
    
    if choice == '1':
        bulk_import_logs(log_manager, auth)
    elif choice == '2':
        bulk_cleanup_data(log_manager, auth)
    elif choice == '3':
        bulk_export_by_criteria(log_manager, auth)
    elif choice == '4':
        optimize_database(log_manager, auth)

def bulk_import_logs(log_manager, auth):
    """Bulk import logs from file"""
    print("\n📥 BULK LOG IMPORT")
    print("="*20)
    
    file_path = input("Enter path to JSON log file: ")
    
    if not os.path.exists(file_path):
        print("File not found.")
        return
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Expect format: {"logs": [...]}
        logs = data.get('logs', [])
        
        if not logs:
            print("No logs found in file.")
            return
        
        print(f"Found {len(logs)} logs to import.")
        confirm = input("Continue with import? (y/n): ")
        
        if confirm.lower() == 'y':
            imported_count = 0
            for log in logs:
                try:
                    log_manager.db.insert_log(log)
                    imported_count += 1
                except Exception as e:
                    print(f"Error importing log: {e}")
            
            print(f"Successfully imported {imported_count}/{len(logs)} logs")
        
    except Exception as e:
        print(f"Error reading file: {e}")

def bulk_cleanup_data(log_manager, auth):
    """Bulk cleanup of old data"""
    print("\n🧹 BULK DATA CLEANUP")
    print("="*22)
    
    print("⚠️ Warning: This will permanently delete data!")
    
    days = input("Delete logs older than how many days? ")
    try:
        days = int(days)
    except ValueError:
        print("Invalid number.")
        return
    
    cutoff_date = datetime.now() - timedelta(days=days)
    
    # Count logs to be deleted
    filters = {'date_to': cutoff_date.strftime('%Y-%m-%d')}
    logs_to_delete = log_manager.db.search_logs(filters, limit=50000)
    
    print(f"Found {len(logs_to_delete)} logs older than {days} days")
    
    if not logs_to_delete:
        print("No logs to delete.")
        return
    
    confirm = input(f"Delete {len(logs_to_delete)} logs? Type 'DELETE' to confirm: ")
    
    if confirm == 'DELETE':
        # Perform deletion (simplified for demo)
        print("Deletion would be performed here...")
        print("(Actual deletion not implemented for safety)")
    else:
        print("Cleanup cancelled.")

def api_management_menu(log_manager, auth):
    """API management menu"""
    print("\n🔌 API MANAGEMENT")
    print("="*18)
    
    api_enabled = log_manager.config.get('api_enabled', False)
    
    print(f"API Status: {'Enabled' if api_enabled else 'Disabled'}")
    
    print("\n1. Enable/Disable API")
    print("2. Generate API Key")
    print("3. View API Statistics")
    print("4. API Documentation")
    print("5. Return")
    
    choice = input("Choose option: ")
    
    if choice == '1':
        toggle_api(log_manager)
    elif choice == '2':
        generate_api_key(log_manager)
    elif choice == '3':
        view_api_stats(log_manager)
    elif choice == '4':
        show_api_docs()

def toggle_api(log_manager):
    """Toggle API on/off"""
    current_status = log_manager.config.get('api_enabled', False)
    new_status = not current_status

    log_manager.config.set('api_enabled', new_status)

    status_text = "enabled" if new_status else "disabled"
    print(f"API has been {status_text}")

def generate_api_key(log_manager):
    """Generate new API key"""
    import secrets
    new_key = secrets.token_urlsafe(32)
    
    log_manager.config.set('api_secret_key', new_key)
    
    print("New API key generated:")
    print(f"Key: {new_key}")
    print("⚠️ Store this key securely - it won't be shown again!")

def show_api_docs():
    """Show API documentation"""
    print("\n📚 API DOCUMENTATION")
    print("="*22)
    
    docs = """
    Log Management API Endpoints:
    
    Authentication:
    POST /api/auth/login - Get authentication token
    
    Log Operations:
    POST /api/logs/search - Search logs with filters
    GET  /api/logs/recent - Get recent logs
    GET  /api/logs/user/{user_id} - Get logs for specific user
    
    Analytics:
    GET  /api/analytics/summary - Get activity summary
    GET  /api/analytics/user/{user_id} - Get user analytics
    POST /api/analytics/chart - Generate activity chart
    
    Alerts:
    GET  /api/alerts - Get recent alerts
    POST /api/alerts/check - Trigger alert checks
    
    Export:
    POST /api/export/logs - Export logs with filters
    
    System:
    GET  /api/system/status - Get system status
    GET  /api/config - Get configuration
    PUT  /api/config - Update configuration
    
    Health:
    GET  /api/health - Health check
    
    All endpoints require authentication via Bearer token.
    """
    
    print(docs)
    input("\nPress Enter to continue...")

def database_maintenance_menu(log_manager, auth):
    """Database maintenance menu"""
    print("\n🔧 DATABASE MAINTENANCE")
    print("="*26)
    
    print("1. Check database size")
    print("2. Optimize database")
    print("3. Rebuild indexes")
    print("4. Vacuum database")
    print("5. Database statistics")
    print("6. Return")
    
    choice = input("Choose maintenance option: ")
    
    if choice == '1':
        check_database_size(log_manager)
    elif choice == '2':
        optimize_database(log_manager, auth)
    elif choice == '3':
        rebuild_indexes(log_manager)
    elif choice == '4':
        vacuum_database(log_manager)
    elif choice == '5':
        show_database_stats(log_manager)

def check_database_size(log_manager):
    """Check database size and usage"""
    print("\n💾 DATABASE SIZE CHECK")
    print("="*24)
    
    db_path = log_manager.db.db_path
    
    if os.path.exists(db_path):
        size_bytes = os.path.getsize(db_path)
        size_mb = size_bytes / (1024 * 1024)
        size_gb = size_mb / 1024
        
        print(f"Database file: {db_path}")
        print(f"Size: {size_bytes:,} bytes")
        print(f"Size: {size_mb:.2f} MB")
        print(f"Size: {size_gb:.3f} GB")
        
        # Get record counts
        conn = sqlite3.connect(str(_DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM activity_log")
        log_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM alerts")
        alert_count = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"\nRecord counts:")
        print(f"Logs: {log_count:,}")
        print(f"Alerts: {alert_count:,}")
        
        # Estimate average sizes
        if log_count > 0:
            avg_log_size = size_bytes / log_count
            print(f"Average log size: {avg_log_size:.0f} bytes")
    else:
        print("Database file not found.")
    
    input("\nPress Enter to continue...")

def optimize_database(log_manager, auth):
    """Optimize database performance"""
    print("\n⚡ DATABASE OPTIMIZATION")
    print("="*26)
    
    print("This will optimize the database for better performance.")
    confirm = input("Continue? (y/n): ")
    
    if confirm.lower() != 'y':
        return
    
    try:
        conn = sqlite3.connect(str(_DB_PATH))
        cursor = conn.cursor()
        
        print("Running optimization...")
        
        # Analyze tables
        cursor.execute("ANALYZE")
        print("✓ Table analysis completed")
        
        # Update statistics
        cursor.execute("PRAGMA optimize")
        print("✓ Statistics updated")
        
        conn.commit()
        conn.close()
        
        print("Database optimization completed!")
        
    except Exception as e:
        print(f"Error during optimization: {e}")
    
    input("\nPress Enter to continue...")

def rebuild_indexes(log_manager):
    """Rebuild database indexes"""
    print("\n🏗️ REBUILD INDEXES")
    print("="*18)
    
    confirm = input("Rebuild all database indexes? (y/n): ")
    
    if confirm.lower() != 'y':
        return
    
    try:
        conn = sqlite3.connect(str(_DB_PATH))
        cursor = conn.cursor()
        
        print("Rebuilding indexes...")
        
        # Drop and recreate indexes
        indexes = [
            "DROP INDEX IF EXISTS idx_logs_timestamp",
            "DROP INDEX IF EXISTS idx_logs_user_id", 
            "DROP INDEX IF EXISTS idx_logs_action",
            "DROP INDEX IF EXISTS idx_logs_module",
            "CREATE INDEX idx_logs_timestamp ON logs(timestamp)",
            "CREATE INDEX idx_logs_user_id ON logs(user_id)",
            "CREATE INDEX idx_logs_action ON logs(action)",
            "CREATE INDEX idx_logs_module ON logs(module)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
            print(".", end="", flush=True)
        
        conn.commit()
        conn.close()
        
        print("\nIndexes rebuilt successfully!")
        
    except Exception as e:
        print(f"Error rebuilding indexes: {e}")
    
    input("\nPress Enter to continue...")

def vacuum_database(log_manager):
    """Vacuum database to reclaim space"""
    print("\n🧹 VACUUM DATABASE")
    print("="*19)
    
    print("This will reclaim unused space in the database.")
    print("⚠️ This operation may take some time for large databases.")
    
    confirm = input("Continue? (y/n): ")
    
    if confirm.lower() != 'y':
        return
    
    try:
        # Get size before
        size_before = os.path.getsize(log_manager.db.db_path)
        
        conn = sqlite3.connect(str(_DB_PATH))
        cursor = conn.cursor()
        
        print("Running VACUUM...")
        cursor.execute("VACUUM")
        
        conn.close()
        
        # Get size after
        size_after = os.path.getsize(log_manager.db.db_path)
        space_saved = size_before - size_after
        
        print(f"VACUUM completed!")
        print(f"Space reclaimed: {space_saved:,} bytes ({space_saved/(1024*1024):.2f} MB)")
        
    except Exception as e:
        print(f"Error during VACUUM: {e}")
    
    input("\nPress Enter to continue...")

def show_database_stats(log_manager):
    """Show detailed database statistics"""
    print("\n📊 DATABASE STATISTICS")
    print("="*24)
    
    try:
        conn = sqlite3.connect(str(_DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Table information
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        print("Database Tables:")
        for table in tables:
            # Validate table name using SQL safety utility
            try:
                validated_table = validate_table_name(table, conn=conn)
                # Use bracket quoting for additional safety
                cursor.execute(f"SELECT COUNT(*) FROM [{validated_table}]")
                count = cursor.fetchone()[0]
                print(f"  {validated_table}: {count:,} records")
            except SQLIdentifierError:
                print(f"  {table}: Invalid table (skipped)")
        
        # Index information
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]
        
        print(f"\nIndexes: {len(indexes)}")
        for index in indexes:
            if not index.startswith('sqlite_'):  # Skip system indexes
                print(f"  {index}")
        
        # Recent activity stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN date(timestamp) = date('now') THEN 1 END) as today,
                COUNT(CASE WHEN date(timestamp) >= date('now', '-7 days') THEN 1 END) as last_week
            FROM activity_log
        """)
        
        stats = cursor.fetchone()
        
        print(f"\nActivity Statistics:")
        print(f"  Total logs: {stats['total']:,}")
        print(f"  Today: {stats['today']:,}")
        print(f"  Last 7 days: {stats['last_week']:,}")
        
        # Performance info
        cursor.execute("PRAGMA page_count")
        page_count = cursor.fetchone()[0]
        
        cursor.execute("PRAGMA page_size") 
        page_size = cursor.fetchone()[0]
        
        print(f"\nPerformance Info:")
        print(f"  Page count: {page_count:,}")
        print(f"  Page size: {page_size:,} bytes")
        print(f"  Estimated size: {(page_count * page_size)/(1024*1024):.2f} MB")
        
        conn.close()
        
    except Exception as e:
        print(f"Error retrieving statistics: {e}")
    
    input("\nPress Enter to continue...")

def performance_metrics_menu(log_manager, auth):
    """Performance metrics menu"""
    print("\n📈 PERFORMANCE METRICS")
    print("="*24)
    
    print("1. Query performance test")
    print("2. Insert performance test") 
    print("3. System resource usage")
    print("4. Database response times")
    print("5. Return")
    
    choice = input("Choose metric: ")
    
    if choice == '1':
        test_query_performance(log_manager)
    elif choice == '2':
        test_insert_performance(log_manager)
    elif choice == '3':
        show_system_resources()
    elif choice == '4':
        test_database_response_times(log_manager)

def test_query_performance(log_manager):
    """Test query performance"""
    print("\n🔍 QUERY PERFORMANCE TEST")
    print("="*27)
    
    queries = [
        ("Simple select", "SELECT COUNT(*) FROM activity_log"),
        ("Date filter", "SELECT COUNT(*) FROM activity_log WHERE date(timestamp) >= date('now', '-7 days')"),
        ("User filter", "SELECT COUNT(*) FROM activity_log WHERE user_id = 'admin'"),
        ("Complex filter", "SELECT COUNT(*) FROM activity_log WHERE action = 'login' AND status = 'success'")
    ]
    
    conn = sqlite3.connect(str(_DB_PATH))
    
    print("Running performance tests...")
    print(f"{'Query':<20} {'Time (ms)':<12} {'Result':<10}")
    print("-" * 45)
    
    for name, query in queries:
        start_time = time.time()
        
        try:
            cursor = conn.cursor()
            cursor.execute(query)
            result = cursor.fetchone()[0]
            
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            
            print(f"{name:<20} {duration_ms:<11.2f} {result:<10}")
            
        except Exception as e:
            print(f"{name:<20} ERROR: {e}")
    
    conn.close()
    input("\nPress Enter to continue...")

def test_insert_performance(log_manager):
    """Test insert performance"""
    print("\n📝 INSERT PERFORMANCE TEST")
    print("="*28)
    
    print("This will insert test log entries to measure performance.")
    test_count = input("Number of test entries to insert (default: 100): ")
    
    try:
        test_count = int(test_count) if test_count else 100
    except ValueError:
        test_count = 100
    
    confirm = input(f"Insert {test_count} test entries? (y/n): ")
    if confirm.lower() != 'y':
        return
    
    print(f"Inserting {test_count} test entries...")
    
    start_time = time.time()
    
    for i in range(test_count):
        test_log = {
            'timestamp': datetime.now().isoformat(),
            'user_id': f'test_user_{i}',
            'username': f'testuser{i}',
            'role': 'test',
            'action': 'test_action',
            'module': 'performance_test',
            'details': f'Test entry {i}',
            'status': 'success'
        }
        
        log_manager.db.insert_log(test_log)
        
        if (i + 1) % 50 == 0:
            print(f"  Inserted {i + 1}/{test_count}")
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"\nPerformance Results:")
    print(f"Total time: {duration:.2f} seconds")
    print(f"Average per insert: {(duration/test_count)*1000:.2f} ms")
    print(f"Inserts per second: {test_count/duration:.1f}")
    
    # Cleanup test entries
    cleanup = input("\nCleanup test entries? (y/n): ")
    if cleanup.lower() == 'y':
        conn = sqlite3.connect(str(_DB_PATH))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM activity_log WHERE module = 'performance_test'")
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        print(f"Deleted {deleted} test entries")
    
    input("\nPress Enter to continue...")

def show_system_resources():
    """Show system resource usage"""
    print("\n💻 SYSTEM RESOURCE USAGE")
    print("="*26)
    
    try:
        import psutil
        
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        print(f"CPU Usage: {cpu_percent}%")
        
        # Memory usage
        memory = psutil.virtual_memory()
        print(f"Memory Usage: {memory.percent}%")
        print(f"Available Memory: {memory.available / (1024**3):.2f} GB")
        print(f"Total Memory: {memory.total / (1024**3):.2f} GB")
        
        # Disk usage
        disk = psutil.disk_usage('/')
        print(f"Disk Usage: {(disk.used / disk.total) * 100:.1f}%")
        print(f"Free Disk Space: {disk.free / (1024**3):.2f} GB")
        
        # Process info
        process = psutil.Process()
        print(f"\nCurrent Process:")
        print(f"Memory Usage: {process.memory_info().rss / (1024**2):.2f} MB")
        print(f"CPU Usage: {process.cpu_percent()}%")
        
    except ImportError:
        print("psutil library not available.")
        print("Install with: pip install psutil")
    except Exception as e:
        print(f"Error retrieving system info: {e}")
    
    input("\nPress Enter to continue...")

def test_database_response_times(log_manager):
    """Test database response times"""
    print("\n⏱️ DATABASE RESPONSE TIMES")
    print("="*28)
    
    print("Testing database response times...")
    
    # Test different types of operations
    tests = [
        ("Connection", lambda: sqlite3.connect(str(_DB_PATH))),
        ("Simple Query", lambda: test_simple_query(log_manager)),
        ("Complex Query", lambda: test_complex_query(log_manager)),
        ("Insert Operation", lambda: test_insert_operation(log_manager))
    ]
    
    results = []
    
    for test_name, test_func in tests:
        times = []
        
        # Run each test 5 times
        for _ in range(5):
            start_time = time.time()
            try:
                result = test_func()
                if hasattr(result, 'close'):
                    result.close()
                end_time = time.time()
                times.append((end_time - start_time) * 1000)  # Convert to ms
            except Exception as e:
                print(f"Error in {test_name}: {e}")
                times.append(float('inf'))
        
        # Calculate statistics
        if times and all(t != float('inf') for t in times):
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            
            results.append((test_name, avg_time, min_time, max_time))
    
    # Display results
    print(f"\n{'Test':<20} {'Avg (ms)':<10} {'Min (ms)':<10} {'Max (ms)':<10}")
    print("-" * 55)
    
    for test_name, avg_time, min_time, max_time in results:
        print(f"{test_name:<20} {avg_time:<9.2f} {min_time:<9.2f} {max_time:<9.2f}")
    
    input("\nPress Enter to continue...")

def test_simple_query(log_manager):
    """Helper function for simple query test"""
    conn = sqlite3.connect(str(_DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM activity_log LIMIT 1")
    result = cursor.fetchone()
    conn.close()
    return result

def test_complex_query(log_manager):
    """Helper function for complex query test"""
    conn = sqlite3.connect(str(_DB_PATH))
    cursor = conn.cursor()
    cursor.execute("""
        SELECT username, COUNT(*) as count 
        FROM activity_log 
        WHERE date(timestamp) >= date('now', '-7 days')
        GROUP BY username 
        ORDER BY count DESC 
        LIMIT 10
    """)
    result = cursor.fetchall()
    conn.close()
    return result

def test_insert_operation(log_manager):
    """Helper function for insert operation test"""
    test_log = {
        'timestamp': datetime.now().isoformat(),
        'user_id': 'perf_test',
        'username': 'performance_test',
        'role': 'test',
        'action': 'test',
        'module': 'test',
        'details': 'Performance test entry',
        'status': 'success'
    }
    
    log_manager.db.insert_log(test_log)
    
    # Clean up immediately
    conn = sqlite3.connect(str(_DB_PATH))
    cursor = conn.cursor()
    cursor.execute("DELETE FROM activity_log WHERE username = 'performance_test'")
    conn.commit()
    conn.close()

def scheduled_reports_menu(log_manager, auth):
    """Scheduled reports menu"""
    print("\n📅 SCHEDULED REPORTS")
    print("="*25)
    
    print("1. Setup Daily Summary Email")
    print("2. Setup Weekly Analytics Report")
    print("3. Setup Security Alert Notifications")
    print("4. View Scheduled Tasks")
    print("5. Return")
    
    choice = input("Choose option: ")
    
    if choice == '1':
        setup_daily_email_report(log_manager, auth)
    elif choice == '2':
        setup_weekly_report(log_manager, auth)
    elif choice == '3':
        setup_security_alerts(log_manager, auth)
    elif choice == '4':
        view_scheduled_tasks(log_manager)

def setup_daily_email_report(log_manager, auth):
    """Setup daily email reports"""
    print("\n📧 SETUP DAILY EMAIL REPORT")
    print("="*35)
    
    email = input("Email address for reports: ")
    if not email:
        print("Email address is required")
        return
    
    log_manager.config.set('alert_email', email)
    
    smtp_server = input("SMTP server (e.g., smtp.gmail.com): ")
    smtp_port = input("SMTP port (default: 587): ")
    smtp_username = input("SMTP username: ")
    smtp_password = input("SMTP password: ")
    
    log_manager.config.set('smtp_server', smtp_server)
    log_manager.config.set('smtp_port', int(smtp_port) if smtp_port else 587)
    log_manager.config.set('smtp_username', smtp_username)
    log_manager.config.set('smtp_password', smtp_password)
    
    print("Daily email reports configured!")
    print("Reports will be sent at 08:00 daily")

def setup_weekly_report(log_manager, auth):
    """Setup weekly analytics report"""
    print("\n📊 SETUP WEEKLY ANALYTICS REPORT")
    print("="*38)
    
    email = input("Email address for weekly reports: ")
    if not email:
        print("Email address is required")
        return
    
    log_manager.config.set('weekly_report_email', email)
    
    day = input("Day of week for reports (Monday=1, Sunday=7, default=1): ")
    try:
        day = int(day) if day else 1
        if not 1 <= day <= 7:
            day = 1
    except ValueError:
        day = 1
    
    log_manager.config.set('weekly_report_day', day)
    
    print(f"Weekly analytics reports configured!")
    print(f"Reports will be sent every {'Monday Tuesday Wednesday Thursday Friday Saturday Sunday'.split()[day-1]}")

def setup_security_alerts(log_manager, auth):
    """Setup security alert notifications"""
    print("\n🚨 SETUP SECURITY ALERTS")
    print("="*28)
    
    email = input("Email address for security alerts: ")
    if not email:
        print("Email address is required")
        return
    
    log_manager.config.set('security_alert_email', email)
    
    print("Alert thresholds:")
    
    failed_login_threshold = input("Failed login threshold (default: 5): ")
    try:
        threshold = int(failed_login_threshold) if failed_login_threshold else 5
    except ValueError:
        threshold = 5
    
    log_manager.config.set('failed_login_threshold', threshold)
    
    print(f"Security alerts configured!")
    print(f"Alerts will be sent for {threshold}+ failed logins")

def view_scheduled_tasks(log_manager):
    """View configured scheduled tasks"""
    print("\n📋 SCHEDULED TASKS")
    print("="*20)
    
    print("Current scheduled tasks:")
    print("- Daily log archival at 02:00")
    print("- Daily log cleanup at 03:00") 
    print("- Hourly alert checks")
    
    if log_manager.config.get('alert_email'):
        print(f"- Daily email reports to: {log_manager.config.get('alert_email')}")
    
    if log_manager.config.get('weekly_report_email'):
        day_name = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_index = log_manager.config.get('weekly_report_day', 1) - 1
        print(f"- Weekly analytics reports to: {log_manager.config.get('weekly_report_email')} ({day_name[day_index]})")
    
    if log_manager.config.get('security_alert_email'):
        threshold = log_manager.config.get('failed_login_threshold', 5)
        print(f"- Security alerts to: {log_manager.config.get('security_alert_email')} (threshold: {threshold})")
    
    input("\nPress Enter to continue...")

# Initialize log manager when module is imported
if __name__ == "__main__":
    # Create global log manager instance for testing
    log_manager = EnhancedLogManager()
    config = LogConfig()
    
    print("Enhanced Log Management System initialized")
    print("Import this module and call display_log_management_menu(auth) to start")

    # Check if API is enabled
    if config.get('api_enabled', False):
        print("Starting Log Management API Server...")
        print("API Documentation available at /api/docs")
        app.run(host='0.0.0.0', port=5000, debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
    else:
        print("API is disabled. Enable it in configuration to start the server.")