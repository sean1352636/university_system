import os
import json
import yaml
import csv
import asyncio
import threading
import time
import queue
import logging
import socket
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Union
from urllib.parse import urlparse

import requests
import psutil
import schedule
from cryptography.fernet import Fernet

from education_system.university_system.modules.shared.constants import paths

from education_system.university_system.modules.shared.utils.simple_activity_logger.models import LogLevel, OutputFormat, SecurityLevel, LogEntry
from education_system.university_system.modules.shared.utils.simple_activity_logger.security import PIIDetector, SecurityMonitor
from education_system.university_system.modules.shared.utils.simple_activity_logger.storage import LogRotationManager, DatabaseLogger
from education_system.university_system.modules.shared.utils.simple_activity_logger.cloud import CloudIntegration
from education_system.university_system.modules.shared.utils.simple_activity_logger.analytics import AnalyticsEngine

_logger = logging.getLogger(__name__)


class EnhancedActivityLogger:
    """
    Enhanced Activity Logger with comprehensive features:
    - Multiple log levels and filtering
    - Asynchronous processing with queues
    - Log rotation and archival
    - Security monitoring and PII protection
    - Multiple output formats and destinations
    - Real-time analytics and reporting
    - Cloud integration capabilities
    - Plugin system for extensibility
    """

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the enhanced logger with configuration"""
        self.config = self._load_config(config_path)
        self.log_dir = self.config.get('log_dir', str(paths.LOG_DIR))
        self.min_log_level = LogLevel[self.config.get('min_log_level', 'INFO')]

        # Initialize components
        self.pii_detector = PIIDetector()
        self.security_monitor = SecurityMonitor(self.config.get('security', {}))
        self.rotation_manager = LogRotationManager(self.config.get('rotation', {}))
        self.cloud_integration = CloudIntegration(self.config.get('cloud', {}))

        # Initialize database logger if enabled
        self.db_logger = None
        if OutputFormat.DATABASE in [OutputFormat(f) for f in self.config.get('output_formats', ['json'])]:
            db_path = str(paths.DEFAULT_DB_PATH)
            self.db_logger = DatabaseLogger(db_path)

        # Initialize analytics engine
        self.analytics = AnalyticsEngine(self.db_logger) if self.db_logger else None

        # Initialize async processing
        self.log_queue = queue.Queue(maxsize=self.config.get('queue_size', 10000))
        self.processing_thread = None
        self.shutdown_event = threading.Event()

        # Initialize encryption if enabled
        self.encryption_key = None
        if self.config.get('encrypt_logs', False):
            self.encryption_key = self._get_or_create_encryption_key()

        # Performance metrics
        self.metrics = {
            'logs_processed': 0,
            'logs_failed': 0,
            'queue_overflows': 0,
            'processing_errors': 0
        }

        # Ensure log directory exists
        self.ensure_log_directory()

        # Start background processing
        self.start_background_processing()

        # Schedule maintenance tasks
        self._schedule_maintenance_tasks()

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load configuration from file or use defaults"""
        default_config = {
            'log_dir': str(paths.LOG_DIR),
            'min_log_level': 'INFO',
            'output_formats': ['json', 'database'],
            'queue_size': 10000,
            'batch_size': 100,
            'flush_interval': 5,
            'encrypt_logs': False,
            'enable_pii_detection': True,
            'security': {
                'max_failed_attempts': 5,
                'lockout_window': 15,
                'max_requests_per_minute': 100,
                'sensitive_actions': ['delete', 'modify_permissions', 'create_admin', 'export_data'],
                'privileged_roles': ['admin', 'superuser']
            },
            'rotation': {
                'max_file_size': 100 * 1024 * 1024,  # 100MB
                'retention_days': 30,
                'compress_old_logs': True
            },
            'cloud': {
                'enabled_services': [],
                'webhook_url': None
            },
            'security_alerts': {
                'email_enabled': False,
                'webhook_enabled': False,
                'webhook_url': None
            }
        }

        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                if config_path.endswith('.yaml') or config_path.endswith('.yml'):
                    user_config = yaml.safe_load(f)
                else:
                    user_config = json.load(f)

            # Merge with defaults (deep merge)
            self._deep_merge(default_config, user_config)

        return default_config

    def _deep_merge(self, base_dict: Dict, update_dict: Dict) -> Dict:
        """Deep merge two dictionaries"""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_merge(base_dict[key], value)
            else:
                base_dict[key] = value
        return base_dict

    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for log encryption"""
        key_file = os.path.join(self.log_dir, '.encryption_key')

        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            os.chmod(key_file, 0o600)  # Restrict permissions
            return key

    def ensure_log_directory(self):
        """Create the log directory if it doesn't exist"""
        if not os.path.exists(self.log_dir):
            try:
                os.makedirs(self.log_dir, mode=0o700, exist_ok=True)
                print(f"Created log directory: {self.log_dir}")
            except Exception as e:
                print(f"Error creating log directory: {e}")
                raise

    def start_background_processing(self):
        """Start background thread for processing log queue"""
        if self.processing_thread is None or not self.processing_thread.is_alive():
            self.processing_thread = threading.Thread(
                target=self._process_log_queue,
                daemon=True,
                name="LogProcessor"
            )
            self.processing_thread.start()
            print("Started background log processing thread")

    def _process_log_queue(self):
        """Background thread to process log entries from queue"""
        batch = []
        last_flush = time.time()
        batch_size = self.config.get('batch_size', 100)
        flush_interval = self.config.get('flush_interval', 5)

        print("Log processing thread started")

        while not self.shutdown_event.is_set():
            try:
                # Try to get log entry with timeout
                try:
                    log_entry = self.log_queue.get(timeout=1)
                    batch.append(log_entry)
                    self.log_queue.task_done()
                except queue.Empty:
                    # Queue is empty, continue to check if should flush
                    _logger.debug("Log queue empty, checking flush conditions")

                # Flush batch if size limit reached or time interval passed
                current_time = time.time()
                should_flush = (
                    len(batch) >= batch_size or
                    (batch and current_time - last_flush >= flush_interval)
                )

                if should_flush:
                    self._flush_batch(batch)
                    batch = []
                    last_flush = current_time

            except Exception as e:
                print(f"Error in background processing: {e}")
                self.metrics['processing_errors'] += 1
                time.sleep(1)

        # Flush remaining logs on shutdown
        if batch:
            self._flush_batch(batch)

        print("Log processing thread stopped")

    def _flush_batch(self, batch: List[LogEntry]):
        """Flush a batch of log entries to configured outputs"""
        if not batch:
            return

        try:
            # Write to configured output formats
            output_formats = self.config.get('output_formats', ['json'])

            if 'json' in output_formats:
                for log_entry in batch:
                    self._write_json_log(log_entry)

            if 'csv' in output_formats:
                for log_entry in batch:
                    self._write_csv_log(log_entry)

            if 'database' in output_formats and self.db_logger:
                self.db_logger.insert_batch_logs(batch)

            # Send to cloud services if configured
            if self.config.get('cloud', {}).get('enabled_services'):
                for log_entry in batch:
                    try:
                        asyncio.create_task(self.cloud_integration.send_to_cloud(log_entry))
                    except RuntimeError as e:
                        # No event loop running, skip cloud integration
                        _logger.debug(f"No event loop for cloud integration: {e}")

            self.metrics['logs_processed'] += len(batch)

        except Exception as e:
            print(f"Error flushing batch: {e}")
            self.metrics['logs_failed'] += len(batch)

    def _write_json_log(self, log_entry: LogEntry):
        """Write log entry to JSON file"""
        today = datetime.now().strftime("%Y-%m-%d")
        log_filename = os.path.join(self.log_dir, f"activity_log_{today}.json")

        # Check for rotation
        if self.rotation_manager.should_rotate(log_filename):
            self.rotation_manager.rotate_log(log_filename)

        try:
            # For JSON logs, we'll append each entry as a separate line (JSONL format)
            # This is more efficient for large files and easier to process
            log_data = log_entry.to_json()

            # Encrypt if enabled
            if self.encryption_key:
                cipher = Fernet(self.encryption_key)
                log_data = cipher.encrypt(log_data.encode()).decode()

            # Append to file
            with open(log_filename, 'a', encoding='utf-8') as f:
                f.write(log_data + '\n')

        except Exception as e:
            print(f"Error writing JSON log: {e}")
            raise

    def _write_csv_log(self, log_entry: LogEntry):
        """Write log entry to CSV file"""
        today = datetime.now().strftime("%Y-%m-%d")
        log_filename = os.path.join(self.log_dir, f"activity_log_{today}.csv")

        # Check for rotation
        if self.rotation_manager.should_rotate(log_filename):
            self.rotation_manager.rotate_log(log_filename)

        # Write CSV header if file doesn't exist
        write_header = not os.path.exists(log_filename)

        try:
            with open(log_filename, 'a', newline='', encoding='utf-8') as f:
                # Convert complex fields to JSON strings for CSV
                csv_data = log_entry.to_dict().copy()
                csv_data['geolocation'] = json.dumps(csv_data['geolocation'])
                csv_data['metadata'] = json.dumps(csv_data['metadata'] or {})

                writer = csv.DictWriter(f, fieldnames=csv_data.keys())

                if write_header:
                    writer.writeheader()

                writer.writerow(csv_data)

        except Exception as e:
            print(f"Error writing CSV log: {e}")
            raise

    def _schedule_maintenance_tasks(self):
        """Schedule regular maintenance tasks"""
        # Schedule log cleanup
        schedule.every().day.at("02:00").do(
            self._safe_execute,
            lambda: self.rotation_manager.cleanup_old_logs(self.log_dir),
            "log_cleanup"
        )

        # Schedule health checks
        schedule.every().hour.do(
            self._safe_execute,
            self._perform_health_check,
            "health_check"
        )

        # Schedule database cleanup (if enabled)
        if self.db_logger:
            schedule.every().week.do(
                self._safe_execute,
                lambda: self.db_logger.delete_old_logs(self.config.get('rotation', {}).get('retention_days', 30)),
                "database_cleanup"
            )

        # Start scheduler in background thread
        def run_scheduler():
            print("Maintenance scheduler started")
            while not self.shutdown_event.is_set():
                try:
                    schedule.run_pending()
                    time.sleep(60)
                except Exception as e:
                    print(f"Scheduler error: {e}")
                    time.sleep(60)
            print("Maintenance scheduler stopped")

        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True, name="MaintenanceScheduler")
        scheduler_thread.start()

    def _safe_execute(self, func: Callable, task_name: str):
        """Safely execute a maintenance task"""
        try:
            func()
            print(f"Maintenance task '{task_name}' completed successfully")
        except Exception as e:
            print(f"Maintenance task '{task_name}' failed: {e}")

    def _perform_health_check(self):
        """Perform system health check"""
        try:
            # Check disk space
            disk_usage = psutil.disk_usage(self.log_dir).percent
            if disk_usage > 90:
                self.log_activity(
                    'system', 'system', 'system',
                    'health_alert', 'system',
                    f'High disk usage: {disk_usage}%',
                    'warning', LogLevel.WARNING, SecurityLevel.MEDIUM
                )

            # Check queue size
            queue_size = self.log_queue.qsize()
            max_queue_size = self.config.get('queue_size', 10000)
            if queue_size > max_queue_size * 0.8:
                self.log_activity(
                    'system', 'system', 'system',
                    'health_alert', 'system',
                    f'High queue utilization: {queue_size}/{max_queue_size}',
                    'warning', LogLevel.WARNING, SecurityLevel.MEDIUM
                )

            # Check processing thread
            if not self.processing_thread.is_alive():
                print("Processing thread died, restarting...")
                self.start_background_processing()
                self.log_activity(
                    'system', 'system', 'system',
                    'thread_restart', 'system',
                    'Processing thread was restarted',
                    'warning', LogLevel.WARNING, SecurityLevel.HIGH
                )

        except Exception as e:
            print(f"Health check error: {e}")

    def _get_session_context(self) -> Dict[str, Any]:
        """Get current session context"""
        try:
            # Try to get session info from request context if available
            # This is a placeholder - in real implementation, you'd integrate
            # with your web framework (Flask, Django, FastAPI, etc.)

            return {
                'session_id': str(uuid.uuid4()),
                'ip_address': self._get_client_ip(),
                'user_agent': self._get_user_agent(),
                'request_size': 0,
                'response_size': 0,
                'processing_time': 0.0,
                'geolocation': self._get_geolocation(''),
                'trace_id': str(uuid.uuid4())
            }
        except Exception:
            return {
                'session_id': 'unknown',
                'ip_address': 'unknown',
                'user_agent': 'unknown',
                'request_size': 0,
                'response_size': 0,
                'processing_time': 0.0,
                'geolocation': {},
                'trace_id': str(uuid.uuid4())
            }

    def _get_client_ip(self) -> str:
        """Get client IP address"""
        try:
            # Try to get from environment or request context
            # This is a simplified version
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            return local_ip
        except Exception:
            return '127.0.0.1'

    def _get_user_agent(self) -> str:
        """Get user agent string"""
        try:
            # This would typically come from HTTP headers
            # For now, return a default value
            return 'ActivityLogger/1.0'
        except Exception:
            return 'unknown'

    def _get_geolocation(self, ip_address: str) -> Dict[str, str]:
        """Get geolocation data for IP address"""
        try:
            # This is a placeholder - in real implementation, you'd use
            # a geolocation service like MaxMind GeoIP2 or similar
            if not ip_address or ip_address in ['127.0.0.1', 'localhost', 'unknown']:
                return {
                    'country': 'Local',
                    'region': 'Local',
                    'city': 'Local',
                    'timezone': 'Local'
                }

            # Placeholder for external geolocation service
            return {
                'country': 'Unknown',
                'region': 'Unknown',
                'city': 'Unknown',
                'timezone': 'Unknown'
            }
        except Exception:
            return {}

    def log_activity(self, user_id: str, username: str, role: str, action: str,
                    module: str, details: Optional[str] = None, status: str = "success",
                    log_level: LogLevel = LogLevel.INFO, security_level: SecurityLevel = SecurityLevel.LOW,
                    metadata: Optional[Dict[str, Any]] = None,
                    processing_time: Optional[float] = None) -> bool:
        """
        Enhanced log activity method with comprehensive logging
        """
        # Check log level filtering
        if log_level.value < self.min_log_level.value:
            return True

        # Get session context
        context = self._get_session_context()

        # Override processing time if provided
        if processing_time is not None:
            context['processing_time'] = processing_time

        # Apply PII detection if enabled
        if self.config.get('enable_pii_detection', True):
            if details:
                details = self.pii_detector.detect_and_mask(details)
            if metadata:
                metadata = metadata.copy()  # Don't modify original
                for key, value in metadata.items():
                    if isinstance(value, str):
                        metadata[key] = self.pii_detector.detect_and_mask(value)

        # Create enhanced log entry
        log_entry = LogEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            user_id=user_id,
            username=username,
            role=role,
            action=action,
            module=module,
            details=details or "No additional details",
            status=status,
            log_level=log_level.name,
            session_id=context['session_id'],
            ip_address=context['ip_address'],
            user_agent=context['user_agent'],
            request_size=context['request_size'],
            response_size=context['response_size'],
            processing_time=context['processing_time'],
            geolocation=context['geolocation'],
            security_level=security_level.name,
            trace_id=context['trace_id'],
            metadata=metadata
        )

        # Security monitoring
        if status == 'failure' and action == 'login':
            is_suspicious = self.security_monitor.check_failed_login(user_id, context['ip_address'])
            if is_suspicious:
                log_entry.security_level = SecurityLevel.HIGH.name
                self._trigger_security_alert(log_entry)

        if self.security_monitor.is_suspicious_activity(log_entry):
            log_entry.security_level = SecurityLevel.CRITICAL.name
            self._trigger_security_alert(log_entry)

        # Add to processing queue
        try:
            self.log_queue.put_nowait(log_entry)
            return True
        except queue.Full:
            print("Log queue is full - dropping log entry")
            self.metrics['queue_overflows'] += 1
            return False

    def _trigger_security_alert(self, log_entry: LogEntry):
        """Trigger security alert for suspicious activity"""
        alert_config = self.config.get('security_alerts', {})

        if alert_config.get('webhook_enabled'):
            self._send_security_webhook(log_entry)

        # Log the security alert (but avoid infinite recursion)
        try:
            alert_entry = LogEntry(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                user_id='system',
                username='security_monitor',
                role='system',
                action='security_alert',
                module='security',
                details=f'Suspicious activity detected: {log_entry.action} by {log_entry.username}',
                status='warning',
                log_level=LogLevel.WARNING.name,
                session_id=str(uuid.uuid4()),
                ip_address='system',
                user_agent='security_monitor',
                request_size=0,
                response_size=0,
                processing_time=0.0,
                geolocation={},
                security_level=SecurityLevel.HIGH.name,
                trace_id=str(uuid.uuid4()),
                metadata={'original_log_id': log_entry.trace_id}
            )

            # Add directly to queue to avoid recursion
            self.log_queue.put_nowait(alert_entry)

        except Exception as e:
            print(f"Error logging security alert: {e}")

    def _send_security_webhook(self, log_entry: LogEntry):
        """Send security alert webhook"""
        webhook_url = self.config.get('security_alerts', {}).get('webhook_url')
        if not webhook_url:
            return

        # Validate webhook URL scheme to prevent SSRF
        parsed = urlparse(webhook_url)
        if parsed.scheme not in ('https', 'http'):
            print(f"Invalid webhook URL scheme: {parsed.scheme}")
            return
        # Block requests to private/internal networks
        hostname = parsed.hostname or ''
        if hostname in ('localhost', '127.0.0.1', '0.0.0.0', '::1') or hostname.startswith('10.') or hostname.startswith('192.168.') or hostname.startswith('172.'):
            print(f"Webhook URL points to internal network, blocked for security")
            return

        try:
            payload = {
                'alert_type': 'security',
                'severity': log_entry.security_level,
                'timestamp': log_entry.timestamp,
                'user': log_entry.username,
                'action': log_entry.action,
                'details': log_entry.details,
                'ip_address': log_entry.ip_address,
                'trace_id': log_entry.trace_id
            }

            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()

        except Exception as e:
            print(f"Failed to send security webhook: {e}")

    def wait_for_queue_empty(self, timeout: float = 30.0) -> bool:
        """Wait for log queue to be empty"""
        start_time = time.time()
        while not self.log_queue.empty() and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        return self.log_queue.empty()

    def flush_logs(self, timeout: float = 30.0) -> bool:
        """Force flush all pending logs"""
        # Wait for queue to be processed
        return self.wait_for_queue_empty(timeout)

    def get_metrics(self) -> Dict[str, Any]:
        """Get logger performance metrics"""
        return {
            **self.metrics,
            'queue_size': self.log_queue.qsize(),
            'queue_maxsize': self.log_queue.maxsize,
            'processing_thread_alive': self.processing_thread.is_alive() if self.processing_thread else False,
            'config': self.config
        }

    def update_config(self, new_config: Dict[str, Any]):
        """Update logger configuration"""
        self._deep_merge(self.config, new_config)

        # Update components that depend on config
        if 'min_log_level' in new_config:
            self.min_log_level = LogLevel[new_config['min_log_level']]

        if 'security' in new_config:
            self.security_monitor.config.update(new_config['security'])

        if 'rotation' in new_config:
            self.rotation_manager.config.update(new_config['rotation'])

        if 'cloud' in new_config:
            self.cloud_integration.config.update(new_config['cloud'])

    def shutdown(self, timeout: float = 30.0):
        """Gracefully shutdown the logger"""
        print("Shutting down Enhanced Activity Logger...")

        # Signal shutdown
        self.shutdown_event.set()

        # Wait for queue to be processed
        if not self.wait_for_queue_empty(timeout):
            print(f"Warning: {self.log_queue.qsize()} log entries may be lost")

        # Wait for processing thread to finish
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=10)
            if self.processing_thread.is_alive():
                print("Warning: Processing thread did not shut down cleanly")

        print("Enhanced Activity Logger shutdown complete")

    # Query and Analytics Methods
    def query_logs(self, filters: Dict[str, Any] = None, limit: int = 1000) -> List[Dict]:
        """Query logs with filters"""
        if not self.db_logger:
            raise RuntimeError("Database logging not enabled")
        return self.db_logger.query_logs(filters, limit)

    def get_user_stats(self, user_id: str, days: int = 7) -> Dict[str, Any]:
        """Get user activity statistics"""
        if not self.analytics:
            raise RuntimeError("Analytics not available - database logging required")
        return self.analytics.get_user_activity_stats(user_id, days)

    def get_system_health(self) -> Dict[str, Any]:
        """Get system health metrics"""
        if not self.analytics:
            raise RuntimeError("Analytics not available")
        return self.analytics.get_system_health_metrics()

    def detect_anomalies(self, threshold: float = 2.0) -> List[Dict[str, Any]]:
        """Detect anomalous activity patterns"""
        if not self.analytics:
            raise RuntimeError("Analytics not available")
        return self.analytics.detect_anomalies(threshold)

    def generate_report(self, report_type: str = 'summary', format: str = 'json') -> Union[Dict, str]:
        """Generate reports"""
        if not self.analytics:
            raise RuntimeError("Analytics not available")
        return self.analytics.generate_report(report_type, format)

    def export_logs(self, start_date: str, end_date: str, format: str = 'json',
                   output_file: Optional[str] = None, filters: Dict[str, Any] = None) -> str:
        """Export logs for a date range"""
        if not self.db_logger:
            raise RuntimeError("Database logging not enabled")

        export_filters = filters or {}
        export_filters.update({
            'timestamp_from': start_date,
            'timestamp_to': end_date
        })

        logs = self.db_logger.query_logs(export_filters, limit=100000)

        if format == 'json':
            content = json.dumps(logs, indent=2, default=str)
            extension = '.json'
        elif format == 'csv':
            if logs:
                output = []
                headers = logs[0].keys()
                output.append(','.join(headers))
                for log in logs:
                    row = ','.join(str(log.get(header, '')).replace(',', ';') for header in headers)
                    output.append(row)
                content = '\n'.join(output)
            else:
                content = 'No logs found for the specified criteria'
            extension = '.csv'
        else:
            raise ValueError(f"Unsupported format: {format}")

        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(self.log_dir, f"exported_logs_{timestamp}{extension}")

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)

        return output_file

    def get_log_stats(self) -> Dict[str, Any]:
        """Get comprehensive log statistics"""
        if not self.db_logger:
            return {"error": "Database logging not enabled"}

        return {
            'database_stats': self.db_logger.get_database_stats(),
            'file_stats': self.rotation_manager.get_log_files_info(self.log_dir),
            'system_health': self.get_system_health() if self.analytics else {},
            'logger_metrics': self.get_metrics(),
            'anomalies': self.detect_anomalies() if self.analytics else []
        }

    def search_logs(self, search_term: str, fields: List[str] = None,
                   limit: int = 100) -> List[Dict]:
        """Search logs for specific terms"""
        if not self.db_logger:
            raise RuntimeError("Database logging not enabled")

        # Simple text search implementation
        search_fields = fields or ['details', 'action', 'module', 'username']

        all_logs = self.db_logger.query_logs(limit=50000)
        matching_logs = []

        search_term_lower = search_term.lower()

        for log in all_logs:
            for field in search_fields:
                if field in log and log[field]:
                    if search_term_lower in str(log[field]).lower():
                        matching_logs.append(log)
                        break

            if len(matching_logs) >= limit:
                break

        return matching_logs
