import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Union

import psutil

from .storage import DatabaseLogger

_logger = logging.getLogger(__name__)


def _log_detail(log: dict, field: str, default=None):
    """Extract a field from a log entry's details JSON.

    The activity_log table stores only id, user_id, username, action,
    details (JSON), timestamp, and ip_address.  Fields like status,
    module, security_level, processing_time, and role live inside the
    details JSON blob.
    """
    # Return directly if the field happens to be a real column
    if field in ('id', 'user_id', 'username', 'action', 'timestamp', 'ip_address'):
        return log.get(field, default)
    try:
        details = log.get('details', '{}')
        if isinstance(details, str):
            details = json.loads(details)
        if isinstance(details, dict):
            return details.get(field, default)
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass
    return default


class AnalyticsEngine:
    """Provide analytics and reporting capabilities"""

    def __init__(self, db_logger: DatabaseLogger):
        self.db_logger = db_logger

    def get_user_activity_stats(self, user_id: str, days: int = 7) -> Dict[str, Any]:
        """Get activity statistics for a user"""
        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

        logs = self.db_logger.query_logs({
            'user_id': user_id,
            'timestamp_from': from_date
        }, limit=10000)

        stats = {
            'total_activities': len(logs),
            'actions': {},
            'modules': {},
            'success_rate': 0,
            'most_active_hours': {},
            'average_processing_time': 0,
            'daily_activity': {},
            'error_rate': 0,
            'security_alerts': 0
        }

        if not logs:
            return stats

        # Count actions and modules
        processing_times = []
        success_count = 0
        error_count = 0
        security_alerts = 0

        for log in logs:
            # Actions
            action = log['action']
            stats['actions'][action] = stats['actions'].get(action, 0) + 1

            # Modules
            module = _log_detail(log, 'module', 'unknown')
            stats['modules'][module] = stats['modules'].get(module, 0) + 1

            # Success rate
            if _log_detail(log, 'status') == 'success':
                success_count += 1
            else:
                error_count += 1

            # Security alerts
            if _log_detail(log, 'security_level', 'LOW') in ['HIGH', 'CRITICAL']:
                security_alerts += 1

            # Processing times
            pt = _log_detail(log, 'processing_time')
            if pt:
                processing_times.append(pt)

            # Activity by hour
            try:
                hour = datetime.strptime(log['timestamp'], "%Y-%m-%d %H:%M:%S").hour
                stats['most_active_hours'][hour] = stats['most_active_hours'].get(hour, 0) + 1
            except (ValueError, KeyError) as e:
                _logger.debug(f"Failed to parse timestamp for hourly stats: {e}")

            # Daily activity
            try:
                date = log['timestamp'][:10]  # Extract date part
                stats['daily_activity'][date] = stats['daily_activity'].get(date, 0) + 1
            except (KeyError, TypeError, IndexError) as e:
                _logger.debug(f"Failed to extract date for daily stats: {e}")

        # Calculate rates and averages
        total_logs = len(logs)
        stats['success_rate'] = (success_count / total_logs) * 100 if total_logs > 0 else 0
        stats['error_rate'] = (error_count / total_logs) * 100 if total_logs > 0 else 0
        stats['security_alerts'] = security_alerts
        stats['average_processing_time'] = sum(processing_times) / len(processing_times) if processing_times else 0

        return stats

    def get_system_health_metrics(self) -> Dict[str, Any]:
        """Get system health and performance metrics"""
        try:
            return {
                'cpu_usage': psutil.cpu_percent(interval=1),
                'memory_usage': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent,
                'active_connections': len(psutil.net_connections()),
                'uptime': time.time() - psutil.boot_time(),
                'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0],
                'available_memory': psutil.virtual_memory().available,
                'total_memory': psutil.virtual_memory().total,
                'disk_io': psutil.disk_io_counters()._asdict() if psutil.disk_io_counters() else {},
                'network_io': psutil.net_io_counters()._asdict() if psutil.net_io_counters() else {}
            }
        except Exception as e:
            print(f"Error getting system metrics: {e}")
            return {
                'cpu_usage': 0,
                'memory_usage': 0,
                'disk_usage': 0,
                'active_connections': 0,
                'uptime': 0,
                'error': str(e)
            }

    def detect_anomalies(self, threshold_multiplier: float = 2.0) -> List[Dict[str, Any]]:
        """Detect anomalous activity patterns"""
        # Get recent activity data
        logs = self.db_logger.query_logs({
            'timestamp_from': (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        }, limit=50000)

        anomalies = []

        # Group by user and analyze patterns
        user_activities = {}
        for log in logs:
            user_id = log['user_id']
            if user_id not in user_activities:
                user_activities[user_id] = []
            user_activities[user_id].append(log)

        # Detect anomalies for each user
        for user_id, activities in user_activities.items():
            # Check for unusual activity volume
            daily_counts = {}
            for activity in activities:
                date = activity['timestamp'][:10]  # Extract date part
                daily_counts[date] = daily_counts.get(date, 0) + 1

            if daily_counts:
                avg_daily = sum(daily_counts.values()) / len(daily_counts)
                max_daily = max(daily_counts.values())

                if max_daily > avg_daily * threshold_multiplier and avg_daily > 5:
                    anomalies.append({
                        'type': 'unusual_activity_volume',
                        'user_id': user_id,
                        'avg_daily': avg_daily,
                        'max_daily': max_daily,
                        'severity': 'medium',
                        'detected_at': datetime.now().isoformat()
                    })

            # Check for unusual time patterns
            hour_counts = {}
            for activity in activities:
                try:
                    hour = datetime.strptime(activity['timestamp'], "%Y-%m-%d %H:%M:%S").hour
                    hour_counts[hour] = hour_counts.get(hour, 0) + 1
                except (ValueError, KeyError) as e:
                    _logger.debug(f"Failed to parse activity timestamp: {e}")
                    continue

            # Detect activity during unusual hours (late night/early morning)
            unusual_hours = list(range(0, 6)) + list(range(22, 24))
            unusual_activity = sum(hour_counts.get(hour, 0) for hour in unusual_hours)
            total_activity = sum(hour_counts.values())

            if total_activity > 50 and unusual_activity / total_activity > 0.3:
                anomalies.append({
                    'type': 'unusual_time_pattern',
                    'user_id': user_id,
                    'unusual_hours_percentage': (unusual_activity / total_activity) * 100,
                    'severity': 'low',
                    'detected_at': datetime.now().isoformat()
                })

            # Check for rapid succession of failed attempts
            # Status is stored in the JSON details field, not as a column
            def _is_failure(a):
                try:
                    details = json.loads(a.get('details', '{}')) if isinstance(a.get('details'), str) else (a.get('details') or {})
                    return details.get('status') == 'failure'
                except (json.JSONDecodeError, AttributeError):
                    return False
            failed_activities = [a for a in activities if _is_failure(a)]
            if len(failed_activities) > 10:
                # Group by time windows
                time_windows = {}
                for activity in failed_activities:
                    try:
                        timestamp = datetime.strptime(activity['timestamp'], "%Y-%m-%d %H:%M:%S")
                        window = timestamp.replace(minute=(timestamp.minute // 5) * 5, second=0, microsecond=0)
                        window_key = window.isoformat()
                        time_windows[window_key] = time_windows.get(window_key, 0) + 1
                    except (ValueError, KeyError) as e:
                        _logger.debug(f"Failed to calculate time window: {e}")
                        continue

                max_failures_in_window = max(time_windows.values()) if time_windows else 0
                if max_failures_in_window > 5:
                    anomalies.append({
                        'type': 'rapid_failure_sequence',
                        'user_id': user_id,
                        'max_failures_in_5min': max_failures_in_window,
                        'severity': 'high',
                        'detected_at': datetime.now().isoformat()
                    })

        # System-wide anomalies
        if logs:
            # Check overall error rate
            error_count = sum(1 for log in logs if _log_detail(log, 'status') != 'success')
            error_rate = (error_count / len(logs)) * 100

            if error_rate > 20:  # More than 20% errors
                anomalies.append({
                    'type': 'high_system_error_rate',
                    'error_rate': error_rate,
                    'total_logs': len(logs),
                    'error_count': error_count,
                    'severity': 'high',
                    'detected_at': datetime.now().isoformat()
                })

        return anomalies

    def generate_report(self, report_type: str = 'summary', format: str = 'json') -> Union[Dict, str]:
        """Generate various types of reports"""
        if report_type == 'summary':
            return self._generate_summary_report(format)
        elif report_type == 'security':
            return self._generate_security_report(format)
        elif report_type == 'performance':
            return self._generate_performance_report(format)
        elif report_type == 'user_activity':
            return self._generate_user_activity_report(format)
        elif report_type == 'system_health':
            return self._generate_system_health_report(format)
        else:
            raise ValueError(f"Unknown report type: {report_type}")

    def _generate_summary_report(self, format: str) -> Union[Dict, str]:
        """Generate summary report"""
        logs = self.db_logger.query_logs(limit=10000)

        report = {
            'generated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'report_type': 'summary',
            'period': 'recent_activity',
            'total_activities': len(logs),
            'unique_users': len(set(log['user_id'] for log in logs)),
            'unique_modules': len(set(_log_detail(log, 'module', 'unknown') for log in logs)),
            'top_actions': {},
            'top_modules': {},
            'top_users': {},
            'error_rate': 0,
            'security_alert_rate': 0,
            'avg_processing_time': 0
        }

        if not logs:
            return self._format_report(report, format)

        # Calculate statistics
        error_count = 0
        security_alerts = 0
        processing_times = []
        user_counts = {}

        for log in logs:
            # Top actions
            action = log['action']
            report['top_actions'][action] = report['top_actions'].get(action, 0) + 1

            # Top modules
            module = _log_detail(log, 'module', 'unknown')
            report['top_modules'][module] = report['top_modules'].get(module, 0) + 1

            # Top users
            user = log['username']
            user_counts[user] = user_counts.get(user, 0) + 1

            # Error rate
            if _log_detail(log, 'status') != 'success':
                error_count += 1

            # Security alerts
            if _log_detail(log, 'security_level', 'LOW') in ['HIGH', 'CRITICAL']:
                security_alerts += 1

            # Processing times
            pt = _log_detail(log, 'processing_time')
            if pt:
                processing_times.append(pt)

        # Calculate rates
        total_logs = len(logs)
        report['error_rate'] = (error_count / total_logs) * 100
        report['security_alert_rate'] = (security_alerts / total_logs) * 100
        report['avg_processing_time'] = sum(processing_times) / len(processing_times) if processing_times else 0

        # Sort and limit top items
        report['top_actions'] = dict(sorted(report['top_actions'].items(), key=lambda x: x[1], reverse=True)[:10])
        report['top_modules'] = dict(sorted(report['top_modules'].items(), key=lambda x: x[1], reverse=True)[:10])
        report['top_users'] = dict(sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10])

        return self._format_report(report, format)

    def _generate_security_report(self, format: str) -> Union[Dict, str]:
        """Generate security-focused report"""
        # Get logs from last 7 days
        from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        logs = self.db_logger.query_logs({'timestamp_from': from_date}, limit=50000)

        report = {
            'generated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'report_type': 'security',
            'period': 'last_7_days',
            'total_logs_analyzed': len(logs),
            'failed_logins': 0,
            'security_alerts': {
                'LOW': 0,
                'MEDIUM': 0,
                'HIGH': 0,
                'CRITICAL': 0
            },
            'suspicious_ips': set(),
            'failed_actions': {},
            'privilege_escalation_attempts': 0,
            'unusual_access_patterns': [],
            'top_security_events': {},
            'recommendations': []
        }

        if not logs:
            return self._format_report(report, format)

        # Analyze security events
        ip_failure_counts = {}
        user_failure_counts = {}

        for log in logs:
            # Count security levels
            security_level = log.get('security_level', 'LOW')
            if security_level in report['security_alerts']:
                report['security_alerts'][security_level] += 1

            # Failed logins
            if log['action'] == 'login' and _log_detail(log, 'status') == 'failure':
                report['failed_logins'] += 1

                # Track by IP
                ip = log.get('ip_address', 'unknown')
                ip_failure_counts[ip] = ip_failure_counts.get(ip, 0) + 1

                # Track by user
                user = log.get('username', 'unknown')
                user_failure_counts[user] = user_failure_counts.get(user, 0) + 1

            # Failed actions
            if _log_detail(log, 'status') == 'failure':
                action = log['action']
                report['failed_actions'][action] = report['failed_actions'].get(action, 0) + 1

            # Privilege escalation attempts
            sensitive_actions = ['create_admin', 'modify_permissions', 'delete_user', 'export_data']
            if log['action'] in sensitive_actions and _log_detail(log, 'role') not in ['admin', 'superuser']:
                report['privilege_escalation_attempts'] += 1

            # Top security events
            if security_level in ['HIGH', 'CRITICAL']:
                event_key = f"{log['action']}_{_log_detail(log, 'module', 'unknown')}"
                report['top_security_events'][event_key] = report['top_security_events'].get(event_key, 0) + 1

        # Identify suspicious IPs (more than 10 failed attempts)
        report['suspicious_ips'] = {ip: count for ip, count in ip_failure_counts.items() if count > 10}

        # Generate recommendations
        if report['failed_logins'] > 100:
            report['recommendations'].append("High number of failed logins detected. Consider implementing account lockout policies.")

        if report['suspicious_ips']:
            report['recommendations'].append(f"Found {len(report['suspicious_ips'])} suspicious IP addresses. Consider IP blocking.")

        if report['privilege_escalation_attempts'] > 0:
            report['recommendations'].append("Privilege escalation attempts detected. Review user permissions and access controls.")

        if report['security_alerts']['CRITICAL'] > 0:
            report['recommendations'].append("Critical security alerts found. Immediate investigation required.")

        # Convert set to list for JSON serialization
        report['suspicious_ips'] = dict(report['suspicious_ips'])

        return self._format_report(report, format)

    def _generate_performance_report(self, format: str) -> Union[Dict, str]:
        """Generate performance-focused report"""
        from_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        logs = self.db_logger.query_logs({'timestamp_from': from_date}, limit=50000)

        report = {
            'generated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'report_type': 'performance',
            'period': 'last_24_hours',
            'total_requests': len(logs),
            'avg_processing_time': 0,
            'median_processing_time': 0,
            'max_processing_time': 0,
            'min_processing_time': 0,
            'slow_requests': [],
            'requests_per_hour': {},
            'performance_by_module': {},
            'performance_by_action': {},
            'system_metrics': self.get_system_health_metrics(),
            'recommendations': []
        }

        if not logs:
            return self._format_report(report, format)

        # Extract processing times
        processing_times = []
        for log in logs:
            pt = _log_detail(log, 'processing_time', 0)
            if pt and pt > 0:
                processing_times.append(pt)

        if processing_times:
            processing_times.sort()
            report['avg_processing_time'] = sum(processing_times) / len(processing_times)
            report['median_processing_time'] = processing_times[len(processing_times) // 2]
            report['max_processing_time'] = max(processing_times)
            report['min_processing_time'] = min(processing_times)

            # Find slow requests (top 1% or > 5 seconds)
            slow_threshold = max(5.0, processing_times[int(len(processing_times) * 0.99)])
            report['slow_requests'] = [
                {
                    'timestamp': log['timestamp'],
                    'user': log['username'],
                    'action': log['action'],
                    'module': _log_detail(log, 'module', 'unknown'),
                    'processing_time': _log_detail(log, 'processing_time', 0)
                }
                for log in logs
                if _log_detail(log, 'processing_time', 0) > slow_threshold
            ][:20]  # Limit to top 20

        # Requests per hour
        for log in logs:
            try:
                hour = datetime.strptime(log['timestamp'], "%Y-%m-%d %H:%M:%S").hour
                report['requests_per_hour'][hour] = report['requests_per_hour'].get(hour, 0) + 1
            except (ValueError, KeyError) as e:
                _logger.debug(f"Failed to parse log timestamp for hourly report: {e}")
                continue

        # Performance by module and action
        module_times = {}
        action_times = {}

        for log in logs:
            pt = _log_detail(log, 'processing_time', 0)
            if pt and pt > 0:
                module = _log_detail(log, 'module', 'unknown')
                action = log['action']

                if module not in module_times:
                    module_times[module] = []
                module_times[module].append(pt)

                if action not in action_times:
                    action_times[action] = []
                action_times[action].append(pt)

        # Calculate averages
        for module, times in module_times.items():
            report['performance_by_module'][module] = {
                'avg_time': sum(times) / len(times),
                'max_time': max(times),
                'request_count': len(times)
            }

        for action, times in action_times.items():
            report['performance_by_action'][action] = {
                'avg_time': sum(times) / len(times),
                'max_time': max(times),
                'request_count': len(times)
            }

        # Generate recommendations
        if report['avg_processing_time'] > 2.0:
            report['recommendations'].append("Average processing time is high. Consider performance optimization.")

        if len(report['slow_requests']) > 10:
            report['recommendations'].append("Many slow requests detected. Investigate bottlenecks.")

        if report['system_metrics'].get('cpu_usage', 0) > 80:
            report['recommendations'].append("High CPU usage detected. Consider scaling resources.")

        if report['system_metrics'].get('memory_usage', 0) > 85:
            report['recommendations'].append("High memory usage detected. Monitor for memory leaks.")

        return self._format_report(report, format)

    def _generate_user_activity_report(self, format: str) -> Union[Dict, str]:
        """Generate user activity report"""
        from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        logs = self.db_logger.query_logs({'timestamp_from': from_date}, limit=50000)

        report = {
            'generated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'report_type': 'user_activity',
            'period': 'last_7_days',
            'total_activities': len(logs),
            'unique_users': 0,
            'most_active_users': {},
            'user_login_patterns': {},
            'inactive_users': [],
            'new_users': [],
            'user_errors': {},
            'recommendations': []
        }

        if not logs:
            return self._format_report(report, format)

        # Analyze user activities
        user_activities = {}
        user_logins = {}
        user_errors = {}
        user_first_seen = {}

        for log in logs:
            user = log['username']
            timestamp = log['timestamp']

            # Track activities
            if user not in user_activities:
                user_activities[user] = 0
            user_activities[user] += 1

            # Track logins
            if log['action'] == 'login':
                if user not in user_logins:
                    user_logins[user] = []
                user_logins[user].append(timestamp)

            # Track errors
            if _log_detail(log, 'status') != 'success':
                if user not in user_errors:
                    user_errors[user] = 0
                user_errors[user] += 1

            # Track first seen (for new users)
            if user not in user_first_seen:
                user_first_seen[user] = timestamp
            else:
                if timestamp < user_first_seen[user]:
                    user_first_seen[user] = timestamp

        report['unique_users'] = len(user_activities)
        report['most_active_users'] = dict(sorted(user_activities.items(), key=lambda x: x[1], reverse=True)[:20])
        report['user_errors'] = dict(sorted(user_errors.items(), key=lambda x: x[1], reverse=True)[:10])

        # Analyze login patterns
        for user, login_times in user_logins.items():
            if len(login_times) > 1:
                # Calculate login frequency
                time_diffs = []
                sorted_times = sorted(login_times)
                for i in range(1, len(sorted_times)):
                    try:
                        t1 = datetime.strptime(sorted_times[i-1], "%Y-%m-%d %H:%M:%S")
                        t2 = datetime.strptime(sorted_times[i], "%Y-%m-%d %H:%M:%S")
                        time_diffs.append((t2 - t1).total_seconds() / 3600)  # hours
                    except (ValueError, IndexError) as e:
                        _logger.debug(f"Failed to calculate login time difference: {e}")
                        continue

                if time_diffs:
                    report['user_login_patterns'][user] = {
                        'total_logins': len(login_times),
                        'avg_hours_between_logins': sum(time_diffs) / len(time_diffs),
                        'first_login': min(login_times),
                        'last_login': max(login_times)
                    }

        # Find inactive users (no activity in last 3 days)
        three_days_ago = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        recent_logs = self.db_logger.query_logs({'timestamp_from': three_days_ago}, limit=10000)
        recent_users = set(log['username'] for log in recent_logs)

        all_recent_users = set(user_activities.keys())
        report['inactive_users'] = list(all_recent_users - recent_users)

        # Find new users (first seen in last 7 days)
        seven_days_ago = datetime.now() - timedelta(days=7)
        for user, first_seen in user_first_seen.items():
            try:
                first_seen_dt = datetime.strptime(first_seen, "%Y-%m-%d %H:%M:%S")
                if first_seen_dt > seven_days_ago:
                    report['new_users'].append({
                        'username': user,
                        'first_seen': first_seen,
                        'total_activities': user_activities[user]
                    })
            except (KeyError, ValueError) as e:
                _logger.debug(f"Failed to process inactive user {user}: {e}")
                continue

        # Generate recommendations
        if len(report['inactive_users']) > 10:
            report['recommendations'].append(f"Found {len(report['inactive_users'])} inactive users. Consider account cleanup.")

        high_error_users = [user for user, errors in user_errors.items() if errors > 50]
        if high_error_users:
            report['recommendations'].append(f"Users with high error rates: {', '.join(high_error_users[:5])}. Consider training or support.")

        if len(report['new_users']) > 20:
            report['recommendations'].append("High number of new users. Ensure proper onboarding processes.")

        return self._format_report(report, format)

    def _generate_system_health_report(self, format: str) -> Union[Dict, str]:
        """Generate system health report"""
        report = {
            'generated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'report_type': 'system_health',
            'system_metrics': self.get_system_health_metrics(),
            'database_stats': self.db_logger.get_database_stats(),
            'log_file_stats': {},
            'anomalies': self.detect_anomalies(),
            'recommendations': []
        }

        # Get log file statistics (if logger has rotation manager)
        try:
            # This would need to be passed from the main logger
            # For now, just include placeholder
            report['log_file_stats'] = {
                'total_files': 0,
                'total_size': 0,
                'oldest_file': None,
                'newest_file': None
            }
        except (OSError, IOError, KeyError) as e:
            _logger.warning(f"Failed to get log file info: {e}")

        # Generate health recommendations
        metrics = report['system_metrics']

        if metrics.get('cpu_usage', 0) > 80:
            report['recommendations'].append("High CPU usage detected. Consider optimizing processes or scaling resources.")

        if metrics.get('memory_usage', 0) > 85:
            report['recommendations'].append("High memory usage detected. Monitor for memory leaks and consider increasing memory.")

        if metrics.get('disk_usage', 0) > 90:
            report['recommendations'].append("Disk space is running low. Clean up old files or expand storage.")

        if len(report['anomalies']) > 0:
            report['recommendations'].append(f"Found {len(report['anomalies'])} anomalies that require investigation.")

        db_stats = report['database_stats']
        if db_stats.get('database_size', 0) > 1024 * 1024 * 1024:  # 1GB
            report['recommendations'].append("Database size is large. Consider archiving old logs.")

        return self._format_report(report, format)

    def _format_report(self, report: Dict, format: str) -> Union[Dict, str]:
        """Format report in requested format"""
        if format == 'json':
            return report
        elif format == 'csv':
            return self._dict_to_csv(report)
        else:
            return json.dumps(report, indent=2, default=str)

    def _dict_to_csv(self, data: Dict) -> str:
        """Convert dictionary to CSV format"""
        lines = ['key,value']

        def flatten_dict(d, prefix=''):
            for key, value in d.items():
                full_key = f"{prefix}.{key}" if prefix else key
                if isinstance(value, dict):
                    lines.extend(flatten_dict(value, full_key))
                elif isinstance(value, list):
                    lines.append(f"{full_key},{len(value)} items")
                else:
                    lines.append(f"{full_key},{value}")

        flatten_dict(data)
        return '\n'.join(lines)

    def get_trending_data(self, metric: str, days: int = 30) -> Dict[str, Any]:
        """Get trending data for specific metrics"""
        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        logs = self.db_logger.query_logs({'timestamp_from': from_date}, limit=100000)

        trending_data = {
            'metric': metric,
            'period': f'last_{days}_days',
            'data_points': {},
            'trend': 'stable',
            'total_change': 0
        }

        if not logs:
            return trending_data

        # Group by date
        daily_data = {}
        for log in logs:
            date = log['timestamp'][:10]  # Extract date part

            if date not in daily_data:
                daily_data[date] = {
                    'total_logs': 0,
                    'errors': 0,
                    'unique_users': set(),
                    'actions': {},
                    'processing_times': []
                }

            daily_data[date]['total_logs'] += 1

            if _log_detail(log, 'status') != 'success':
                daily_data[date]['errors'] += 1

            daily_data[date]['unique_users'].add(log['username'])

            action = log['action']
            daily_data[date]['actions'][action] = daily_data[date]['actions'].get(action, 0) + 1

            pt = _log_detail(log, 'processing_time')
            if pt:
                daily_data[date]['processing_times'].append(pt)

        # Calculate metric values by date
        for date, data in daily_data.items():
            if metric == 'total_activity':
                trending_data['data_points'][date] = data['total_logs']
            elif metric == 'error_rate':
                trending_data['data_points'][date] = (data['errors'] / data['total_logs']) * 100 if data['total_logs'] > 0 else 0
            elif metric == 'unique_users':
                trending_data['data_points'][date] = len(data['unique_users'])
            elif metric == 'avg_processing_time':
                if data['processing_times']:
                    trending_data['data_points'][date] = sum(data['processing_times']) / len(data['processing_times'])
                else:
                    trending_data['data_points'][date] = 0

        # Calculate trend
        if len(trending_data['data_points']) >= 2:
            sorted_dates = sorted(trending_data['data_points'].keys())
            first_value = trending_data['data_points'][sorted_dates[0]]
            last_value = trending_data['data_points'][sorted_dates[-1]]

            if last_value > first_value * 1.1:
                trending_data['trend'] = 'increasing'
            elif last_value < first_value * 0.9:
                trending_data['trend'] = 'decreasing'

            trending_data['total_change'] = ((last_value - first_value) / first_value) * 100 if first_value > 0 else 0

        return trending_data
