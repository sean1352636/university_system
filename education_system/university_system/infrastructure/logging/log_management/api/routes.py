"""Flask API route endpoints for log management."""

import os
import json
import time
import secrets
from datetime import datetime, timedelta

from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH as _DB_PATH
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants.paths import TEMP_DIR
from education_system.university_system.modules.shared.utils.simple_activity_logger import logger

from education_system.university_system.infrastructure.logging.log_management.api import app, request, jsonify, send_file
from education_system.university_system.infrastructure.logging.log_management.api.auth import token_required, admin_required
from education_system.university_system.infrastructure.logging.log_management.config import config


def _get_log_manager():
    """Lazy import to avoid circular dependency."""
    from education_system.university_system.infrastructure.logging.log_management.manager import get_log_manager
    return get_log_manager()


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

        log_manager = _get_log_manager()
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

        log_manager = _get_log_manager()
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

        log_manager = _get_log_manager()
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

        log_manager = _get_log_manager()
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

        log_manager = _get_log_manager()
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

        log_manager = _get_log_manager()
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
        log_manager = _get_log_manager()
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
        log_manager = _get_log_manager()
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
    log_manager = _get_log_manager()
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
        log_manager = _get_log_manager()

        def log_callback(log_entry):
            return f"data: {json.dumps(log_entry)}\n\n"

        log_manager.monitor.subscribe(log_callback)

        try:
            yield "data: {\"status\": \"connected\"}\n\n"

            while True:
                # This is a simplified version - in production, use proper SSE
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
    log_manager = _get_log_manager()
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

        log_manager = _get_log_manager()
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
        log_manager = _get_log_manager()
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
        import hmac
        import hashlib as _hashlib

        webhook_secret = config.get('webhook_secret', '')
        if not webhook_secret:
            return jsonify({'error': 'Webhook not configured'}), 500

        # Validate timestamp to prevent replay attacks (5 min window)
        webhook_ts = request.headers.get('X-Webhook-Timestamp', '')
        if not webhook_ts:
            return jsonify({'error': 'Missing timestamp header'}), 401
        try:
            ts = datetime.fromisoformat(webhook_ts)
            if abs((datetime.utcnow() - ts).total_seconds()) > 300:
                return jsonify({'error': 'Request timestamp expired'}), 401
        except ValueError:
            return jsonify({'error': 'Invalid timestamp format'}), 401

        # Verify HMAC-SHA256 signature of request body
        signature = request.headers.get('X-Webhook-Signature', '')
        if not signature:
            # Fall back to legacy key-based auth
            webhook_key = request.headers.get('X-Webhook-Key')
            if not webhook_key or not secrets.compare_digest(webhook_key, webhook_secret):
                return jsonify({'error': 'Invalid webhook key'}), 401
        else:
            body = request.get_data()
            expected = hmac.new(
                webhook_secret.encode(), webhook_ts.encode() + b'.' + body, _hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                return jsonify({'error': 'Invalid webhook signature'}), 401

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
        log_manager = _get_log_manager()
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
