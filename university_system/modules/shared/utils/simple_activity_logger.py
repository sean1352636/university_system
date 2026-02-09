import os
import json
import yaml
import csv
import gzip
from university_system.infrastructure.database.db import sqlite3
import hashlib
import re
import threading
import time
import queue
import asyncio
# aiofiles is optional; if unavailable, asynchronous file operations are disabled
try:
    import aiofiles  # type: ignore
except ImportError:
    aiofiles = None  # type: ignore
import logging
import functools
import traceback
import socket
import uuid
import ipaddress
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
import requests

# Initialize module logger
_logger = logging.getLogger(__name__)
from cryptography.fernet import Fernet
import psutil
import schedule
from university_system.modules.shared.constants import paths


class LogLevel(Enum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class OutputFormat(Enum):
    JSON = "json"
    CSV = "csv"
    DATABASE = "database"
    SYSLOG = "syslog"
    CLOUD = "cloud"


class SecurityLevel(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class LogEntry:
    """Enhanced log entry with comprehensive metadata"""
    timestamp: str
    user_id: str
    username: str
    role: str
    action: str
    module: str
    details: str
    status: str
    log_level: str
    session_id: str
    ip_address: str
    user_agent: str
    request_size: int
    response_size: int
    processing_time: float
    geolocation: Dict[str, str]
    security_level: str
    trace_id: str
    stack_trace: Optional[str] = None
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class PIIDetector:
    """Detect and mask personally identifiable information"""
    
    def __init__(self):
        self.patterns = {
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'phone': re.compile(r'\b\d{3}-\d{3}-\d{4}\b|\b\(\d{3}\)\s*\d{3}-\d{4}\b'),
            'ssn': re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
            'credit_card': re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'),
            'ip_address': re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b')
        }
    
    def detect_and_mask(self, text: str, mask_char: str = '*') -> str:
        """Detect and mask PII in text"""
        if not isinstance(text, str):
            return text
        
        masked_text = text
        for pii_type, pattern in self.patterns.items():
            def mask_match(match):
                return mask_char * len(match.group())
            masked_text = pattern.sub(mask_match, masked_text)
        
        return masked_text


class SecurityMonitor:
    """Monitor for suspicious activities and security threats"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.failed_attempts = {}
        self.suspicious_ips = set()
        self.rate_limits = {}
    
    def check_failed_login(self, user_id: str, ip_address: str) -> bool:
        """Track failed login attempts"""
        key = f"{user_id}:{ip_address}"
        now = datetime.now()
        
        if key not in self.failed_attempts:
            self.failed_attempts[key] = []
        
        # Clean old attempts
        cutoff = now - timedelta(minutes=self.config.get('lockout_window', 15))
        self.failed_attempts[key] = [
            attempt for attempt in self.failed_attempts[key] 
            if attempt > cutoff
        ]
        
        # Add current attempt
        self.failed_attempts[key].append(now)
        
        # Check if exceeded threshold
        max_attempts = self.config.get('max_failed_attempts', 5)
        if len(self.failed_attempts[key]) >= max_attempts:
            self.suspicious_ips.add(ip_address)
            return True
        
        return False
    
    def is_suspicious_activity(self, log_entry: LogEntry) -> bool:
        """Analyze log entry for suspicious patterns"""
        # Check IP reputation
        if log_entry.ip_address in self.suspicious_ips:
            return True
        
        # Check for unusual access patterns
        if self._check_rate_limiting(log_entry):
            return True
        
        # Check for privilege escalation attempts
        if self._check_privilege_escalation(log_entry):
            return True
        
        return False
    
    def _check_rate_limiting(self, log_entry: LogEntry) -> bool:
        """Check for rate limiting violations"""
        key = f"{log_entry.user_id}:{log_entry.action}"
        now = datetime.now()
        
        if key not in self.rate_limits:
            self.rate_limits[key] = []
        
        # Clean old requests
        cutoff = now - timedelta(minutes=1)
        self.rate_limits[key] = [
            req_time for req_time in self.rate_limits[key] 
            if req_time > cutoff
        ]
        
        # Add current request
        self.rate_limits[key].append(now)
        
        # Check rate limit
        max_requests = self.config.get('max_requests_per_minute', 100)
        return len(self.rate_limits[key]) > max_requests
    
    def _check_privilege_escalation(self, log_entry: LogEntry) -> bool:
        """Check for potential privilege escalation"""
        sensitive_actions = self.config.get('sensitive_actions', [
            'delete', 'modify_permissions', 'create_admin', 'export_data'
        ])
        
        if log_entry.action in sensitive_actions:
            if log_entry.role not in self.config.get('privileged_roles', ['admin', 'superuser']):
                return True
        
        return False
    
    def add_suspicious_ip(self, ip_address: str):
        """Manually add IP to suspicious list"""
        self.suspicious_ips.add(ip_address)
    
    def remove_suspicious_ip(self, ip_address: str):
        """Remove IP from suspicious list"""
        self.suspicious_ips.discard(ip_address)
    
    def get_failed_attempts_count(self, user_id: str, ip_address: str) -> int:
        """Get current failed attempts count for user/IP combination"""
        key = f"{user_id}:{ip_address}"
        if key not in self.failed_attempts:
            return 0
        
        now = datetime.now()
        cutoff = now - timedelta(minutes=self.config.get('lockout_window', 15))
        
        # Clean old attempts and return count
        self.failed_attempts[key] = [
            attempt for attempt in self.failed_attempts[key] 
            if attempt > cutoff
        ]
        
        return len(self.failed_attempts[key])
    
    def reset_failed_attempts(self, user_id: str, ip_address: str):
        """Reset failed attempts for user/IP combination"""
        key = f"{user_id}:{ip_address}"
        if key in self.failed_attempts:
            del self.failed_attempts[key]


class LogRotationManager:
    """Handle log rotation and archival"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.max_size = config.get('max_file_size', 100 * 1024 * 1024)  # 100MB
        self.retention_days = config.get('retention_days', 30)
        self.compress_old_logs = config.get('compress_old_logs', True)
    
    def should_rotate(self, file_path: str) -> bool:
        """Check if log file should be rotated"""
        if not os.path.exists(file_path):
            return False
        
        file_size = os.path.getsize(file_path)
        return file_size >= self.max_size
    
    def rotate_log(self, file_path: str) -> str:
        """Rotate log file and return new filename"""
        if not os.path.exists(file_path):
            return file_path
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(file_path)[0]
        rotated_name = f"{base_name}_{timestamp}.log"
        
        # Move current log to rotated name
        os.rename(file_path, rotated_name)
        
        # Compress if enabled
        if self.compress_old_logs:
            self._compress_file(rotated_name)
        
        return file_path
    
    def _compress_file(self, file_path: str):
        """Compress log file using gzip"""
        compressed_path = f"{file_path}.gz"
        
        with open(file_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                f_out.writelines(f_in)
        
        # Remove original file
        os.remove(file_path)
    
    def cleanup_old_logs(self, log_dir: str):
        """Remove logs older than retention period"""
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        
        for file_path in Path(log_dir).glob("*.log*"):
            if file_path.stat().st_mtime < cutoff_date.timestamp():
                try:
                    file_path.unlink()
                    print(f"Removed old log file: {file_path}")
                except Exception as e:
                    print(f"Error removing log file {file_path}: {e}")
    
    def get_log_files_info(self, log_dir: str) -> List[Dict[str, Any]]:
        """Get information about log files in directory"""
        files_info = []
        
        for file_path in Path(log_dir).glob("*.log*"):
            stat = file_path.stat()
            files_info.append({
                'name': file_path.name,
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime),
                'modified': datetime.fromtimestamp(stat.st_mtime),
                'compressed': file_path.suffix == '.gz'
            })
        
        return sorted(files_info, key=lambda x: x['modified'], reverse=True)


class DatabaseManager:
    """Manage database connections and operations"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
    
    def get_connection(self):
        """Get a database connection"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute a SELECT query and return results"""
        with self._lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                results = [dict(row) for row in cursor.fetchall()]
                return results
            finally:
                conn.close()
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Execute an INSERT/UPDATE/DELETE query and return affected rows"""
        with self._lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return cursor.rowcount
            finally:
                conn.close()
    
    def execute_batch(self, query: str, params_list: List[tuple]) -> int:
        """Execute batch operations"""
        with self._lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                cursor.executemany(query, params_list)
                conn.commit()
                return cursor.rowcount
            finally:
                conn.close()


class DatabaseLogger:
    """Handle database logging operations"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with proper schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id TEXT NOT NULL,
                username TEXT NOT NULL,
                role TEXT NOT NULL,
                action TEXT NOT NULL,
                module TEXT NOT NULL,
                details TEXT,
                status TEXT NOT NULL,
                log_level TEXT NOT NULL,
                session_id TEXT,
                ip_address TEXT,
                user_agent TEXT,
                request_size INTEGER,
                response_size INTEGER,
                processing_time REAL,
                geolocation TEXT,
                security_level TEXT,
                trace_id TEXT,
                stack_trace TEXT,
                metadata TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for performance
        indexes = [
            ('idx_timestamp', 'timestamp'),
            ('idx_user_id', 'user_id'),
            ('idx_action', 'action'),
            ('idx_module', 'module'),
            ('idx_status', 'status'),
            ('idx_log_level', 'log_level'),
            ('idx_security_level', 'security_level'),
            ('idx_created_at', 'created_at')
        ]
        
        for index_name, column in indexes:
            cursor.execute(f'CREATE INDEX IF NOT EXISTS {index_name} ON activity_logs({column})')
        
        conn.commit()
        conn.close()
    
    def insert_log(self, log_entry: LogEntry):
        """Insert log entry into database"""
        query = '''
            INSERT INTO activity_logs (
                timestamp, user_id, username, role, action, module, details, status,
                log_level, session_id, ip_address, user_agent, request_size, response_size,
                processing_time, geolocation, security_level, trace_id, stack_trace, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        
        params = (
            log_entry.timestamp, log_entry.user_id, log_entry.username, log_entry.role,
            log_entry.action, log_entry.module, log_entry.details, log_entry.status,
            log_entry.log_level, log_entry.session_id, log_entry.ip_address,
            log_entry.user_agent, log_entry.request_size, log_entry.response_size,
            log_entry.processing_time, json.dumps(log_entry.geolocation),
            log_entry.security_level, log_entry.trace_id, log_entry.stack_trace,
            json.dumps(log_entry.metadata or {})
        )
        
        self.db_manager.execute_update(query, params)
    
    def insert_batch_logs(self, log_entries: List[LogEntry]):
        """Insert multiple log entries in batch"""
        query = '''
            INSERT INTO activity_logs (
                timestamp, user_id, username, role, action, module, details, status,
                log_level, session_id, ip_address, user_agent, request_size, response_size,
                processing_time, geolocation, security_level, trace_id, stack_trace, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        
        params_list = []
        for log_entry in log_entries:
            params = (
                log_entry.timestamp, log_entry.user_id, log_entry.username, log_entry.role,
                log_entry.action, log_entry.module, log_entry.details, log_entry.status,
                log_entry.log_level, log_entry.session_id, log_entry.ip_address,
                log_entry.user_agent, log_entry.request_size, log_entry.response_size,
                log_entry.processing_time, json.dumps(log_entry.geolocation),
                log_entry.security_level, log_entry.trace_id, log_entry.stack_trace,
                json.dumps(log_entry.metadata or {})
            )
            params_list.append(params)
        
        self.db_manager.execute_batch(query, params_list)
    
    def query_logs(self, filters: Dict[str, Any] = None, limit: int = 1000) -> List[Dict]:
        """Query logs with optional filters"""
        query = "SELECT * FROM activity_logs"
        params = []
        
        if filters:
            conditions = []
            for key, value in filters.items():
                if key == 'timestamp_from':
                    conditions.append("timestamp >= ?")
                    params.append(value)
                elif key == 'timestamp_to':
                    conditions.append("timestamp <= ?")
                    params.append(value)
                elif key == 'date_from':
                    conditions.append("DATE(timestamp) >= ?")
                    params.append(value)
                elif key == 'date_to':
                    conditions.append("DATE(timestamp) <= ?")
                    params.append(value)
                elif isinstance(value, list):
                    placeholders = ','.join(['?' for _ in value])
                    conditions.append(f"{key} IN ({placeholders})")
                    params.extend(value)
                else:
                    conditions.append(f"{key} = ?")
                    params.append(value)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
        
        query += f" ORDER BY timestamp DESC LIMIT {limit}"
        
        return self.db_manager.execute_query(query, tuple(params))
    
    def get_log_count(self, filters: Dict[str, Any] = None) -> int:
        """Get count of logs matching filters"""
        query = "SELECT COUNT(*) as count FROM activity_logs"
        params = []
        
        if filters:
            conditions = []
            for key, value in filters.items():
                if key == 'timestamp_from':
                    conditions.append("timestamp >= ?")
                    params.append(value)
                elif key == 'timestamp_to':
                    conditions.append("timestamp <= ?")
                    params.append(value)
                elif isinstance(value, list):
                    placeholders = ','.join(['?' for _ in value])
                    conditions.append(f"{key} IN ({placeholders})")
                    params.extend(value)
                else:
                    conditions.append(f"{key} = ?")
                    params.append(value)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
        
        result = self.db_manager.execute_query(query, tuple(params))
        return result[0]['count'] if result else 0
    
    def delete_old_logs(self, days: int) -> int:
        """Delete logs older than specified days"""
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        query = "DELETE FROM activity_logs WHERE timestamp < ?"
        return self.db_manager.execute_update(query, (cutoff_date,))
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        stats = {}
        
        # Total logs
        stats['total_logs'] = self.get_log_count()
        
        # Logs by level
        level_query = """
            SELECT log_level, COUNT(*) as count 
            FROM activity_logs 
            GROUP BY log_level 
            ORDER BY count DESC
        """
        stats['logs_by_level'] = {
            row['log_level']: row['count'] 
            for row in self.db_manager.execute_query(level_query)
        }
        
        # Recent activity (last 24 hours)
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        stats['recent_activity'] = self.get_log_count({'timestamp_from': yesterday})
        
        # Database size
        try:
            stats['database_size'] = os.path.getsize(self.db_path)
        except (OSError, FileNotFoundError) as e:
            logger.warning(f"Failed to get database size: {e}")
            stats['database_size'] = 0
        
        return stats


class CloudIntegration:
    """Handle cloud service integrations"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled_services = config.get('enabled_services', [])
        self.session = requests.Session()
        self.session.timeout = config.get('timeout', 10)
    
    async def send_to_cloud(self, log_entry: LogEntry):
        """Send log entry to configured cloud services"""
        tasks = []
        
        if 'aws_cloudwatch' in self.enabled_services:
            tasks.append(self._send_to_cloudwatch(log_entry))
        
        if 'elasticsearch' in self.enabled_services:
            tasks.append(self._send_to_elasticsearch(log_entry))
        
        if 'webhook' in self.enabled_services:
            tasks.append(self._send_webhook(log_entry))
        
        if 'splunk' in self.enabled_services:
            tasks.append(self._send_to_splunk(log_entry))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _send_to_cloudwatch(self, log_entry: LogEntry):
        """Send to AWS CloudWatch"""
        try:
            # This would require boto3 in a real implementation
            cloudwatch_config = self.config.get('aws_cloudwatch', {})
            log_group = cloudwatch_config.get('log_group', 'application-logs')
            log_stream = cloudwatch_config.get('log_stream', 'default-stream')
            
            # Placeholder for CloudWatch implementation
            print(f"Would send to CloudWatch: {log_group}/{log_stream}")
            
        except Exception as e:
            print(f"CloudWatch send failed: {e}")
    
    async def _send_to_elasticsearch(self, log_entry: LogEntry):
        """Send to Elasticsearch"""
        try:
            es_config = self.config.get('elasticsearch', {})
            es_url = es_config.get('url', 'http://localhost:9200')
            index_name = es_config.get('index', 'activity-logs')
            
            # Prepare document
            doc = log_entry.to_dict()
            doc['@timestamp'] = log_entry.timestamp
            
            # Send to Elasticsearch
            url = f"{es_url}/{index_name}/_doc"
            headers = {'Content-Type': 'application/json'}
            
            if es_config.get('username') and es_config.get('password'):
                auth = (es_config['username'], es_config['password'])
            else:
                auth = None
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.session.post(url, json=doc, headers=headers, auth=auth)
            )
            response.raise_for_status()
            
        except Exception as e:
            print(f"Elasticsearch send failed: {e}")
    
    async def _send_webhook(self, log_entry: LogEntry):
        """Send to webhook endpoint"""
        webhook_url = self.config.get('webhook_url')
        if not webhook_url:
            return
        
        try:
            payload = {
                'timestamp': log_entry.timestamp,
                'event_type': 'activity_log',
                'data': log_entry.to_dict()
            }
            
            headers = {'Content-Type': 'application/json'}
            webhook_config = self.config.get('webhook', {})
            
            # Add custom headers if configured
            if 'headers' in webhook_config:
                headers.update(webhook_config['headers'])
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.session.post(webhook_url, json=payload, headers=headers)
            )
            response.raise_for_status()
            
        except Exception as e:
            print(f"Webhook send failed: {e}")
    
    async def _send_to_splunk(self, log_entry: LogEntry):
        """Send to Splunk HEC (HTTP Event Collector)"""
        try:
            splunk_config = self.config.get('splunk', {})
            hec_url = splunk_config.get('hec_url')
            hec_token = splunk_config.get('hec_token')
            
            if not hec_url or not hec_token:
                return
            
            # Prepare Splunk event
            event = {
                'time': int(datetime.strptime(log_entry.timestamp, "%Y-%m-%d %H:%M:%S.%f").timestamp()),
                'source': 'activity_logger',
                'sourcetype': 'json',
                'index': splunk_config.get('index', 'main'),
                'event': log_entry.to_dict()
            }
            
            headers = {
                'Authorization': f'Splunk {hec_token}',
                'Content-Type': 'application/json'
            }
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.session.post(hec_url, json=event, headers=headers)
            )
            response.raise_for_status()
            
        except Exception as e:
            print(f"Splunk send failed: {e}")
    
    def test_connectivity(self) -> Dict[str, bool]:
        """Test connectivity to all configured services"""
        results = {}
        
        for service in self.enabled_services:
            try:
                if service == 'webhook':
                    webhook_url = self.config.get('webhook_url')
                    if webhook_url:
                        response = self.session.head(webhook_url, timeout=5)
                        results[service] = response.status_code < 400
                    else:
                        results[service] = False
                
                elif service == 'elasticsearch':
                    es_config = self.config.get('elasticsearch', {})
                    es_url = es_config.get('url', 'http://localhost:9200')
                    response = self.session.get(f"{es_url}/_cluster/health", timeout=5)
                    results[service] = response.status_code == 200
                
                elif service == 'splunk':
                    splunk_config = self.config.get('splunk', {})
                    hec_url = splunk_config.get('hec_url')
                    if hec_url:
                        # Test with a simple health check
                        response = self.session.get(hec_url.replace('/event', '/health'), timeout=5)
                        results[service] = response.status_code < 500
                    else:
                        results[service] = False
                
                else:
                    results[service] = True  # Assume other services are OK
                    
            except Exception as e:
                results[service] = False
                print(f"Connectivity test failed for {service}: {e}")
        
        return results


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
            module = log['module']
            stats['modules'][module] = stats['modules'].get(module, 0) + 1
            
            # Success rate
            if log['status'] == 'success':
                success_count += 1
            else:
                error_count += 1
            
            # Security alerts
            if log['security_level'] in ['HIGH', 'CRITICAL']:
                security_alerts += 1
            
            # Processing times
            if log['processing_time']:
                processing_times.append(log['processing_time'])
            
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
            failed_activities = [a for a in activities if a['status'] == 'failure']
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
            error_count = sum(1 for log in logs if log['status'] != 'success')
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
            'unique_modules': len(set(log['module'] for log in logs)),
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
            module = log['module']
            report['top_modules'][module] = report['top_modules'].get(module, 0) + 1
            
            # Top users
            user = log['username']
            user_counts[user] = user_counts.get(user, 0) + 1
            
            # Error rate
            if log['status'] != 'success':
                error_count += 1
            
            # Security alerts
            if log['security_level'] in ['HIGH', 'CRITICAL']:
                security_alerts += 1
            
            # Processing times
            if log['processing_time']:
                processing_times.append(log['processing_time'])
        
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
            if log['action'] == 'login' and log['status'] == 'failure':
                report['failed_logins'] += 1
                
                # Track by IP
                ip = log.get('ip_address', 'unknown')
                ip_failure_counts[ip] = ip_failure_counts.get(ip, 0) + 1
                
                # Track by user
                user = log.get('username', 'unknown')
                user_failure_counts[user] = user_failure_counts.get(user, 0) + 1
            
            # Failed actions
            if log['status'] == 'failure':
                action = log['action']
                report['failed_actions'][action] = report['failed_actions'].get(action, 0) + 1
            
            # Privilege escalation attempts
            sensitive_actions = ['create_admin', 'modify_permissions', 'delete_user', 'export_data']
            if log['action'] in sensitive_actions and log['role'] not in ['admin', 'superuser']:
                report['privilege_escalation_attempts'] += 1
            
            # Top security events
            if security_level in ['HIGH', 'CRITICAL']:
                event_key = f"{log['action']}_{log['module']}"
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
            if log.get('processing_time') and log['processing_time'] > 0:
                processing_times.append(log['processing_time'])
        
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
                    'module': log['module'],
                    'processing_time': log['processing_time']
                }
                for log in logs 
                if log.get('processing_time', 0) > slow_threshold
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
            if log.get('processing_time') and log['processing_time'] > 0:
                module = log['module']
                action = log['action']
                
                if module not in module_times:
                    module_times[module] = []
                module_times[module].append(log['processing_time'])
                
                if action not in action_times:
                    action_times[action] = []
                action_times[action].append(log['processing_time'])
        
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
            if log['status'] != 'success':
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
            db_path = os.path.join(self.log_dir, 'activity_logs.db')
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
                os.makedirs(self.log_dir, mode=0o755, exist_ok=True)
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
            
            if log['status'] != 'success':
                daily_data[date]['errors'] += 1
            
            daily_data[date]['unique_users'].add(log['username'])
            
            action = log['action']
            daily_data[date]['actions'][action] = daily_data[date]['actions'].get(action, 0) + 1
            
            if log.get('processing_time'):
                daily_data[date]['processing_times'].append(log['processing_time'])
        
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

        return matching_logs

# Enhanced Decorators with full feature support
def enhanced_log_activity(action=None, module=None, description=None, 
                         log_level=LogLevel.INFO, security_level=SecurityLevel.LOW,
                         metadata=None, measure_performance=True):
    """
    Enhanced decorator with performance measurement and rich metadata
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            # Get current user information (simplified - no auth imports)
            user_id = 'system'
            username = 'system'
            role = 'system'
            
            # Try to extract user info from function arguments if available
            if args and hasattr(args[0], '__dict__'):
                obj = args[0]
                if hasattr(obj, 'current_user'):
                    user = obj.current_user
                    user_id = getattr(user, 'id', 'system')
                    username = getattr(user, 'username', 'system')
                    role = getattr(user, 'role', 'system')
            
            # Determine the action, module, and details
            action_name = action or func.__name__
            module_name = module or func.__module__ or 'general'
            details = description or f"Executed {func.__name__}"
            
            # Prepare metadata
            func_metadata = metadata.copy() if metadata else {}
            func_metadata['function_name'] = func.__name__
            func_metadata['function_module'] = func.__module__
            
            if measure_performance:
                func_metadata['function_args_count'] = len(args) + len(kwargs)
            
            try:
                # Execute the original function
                result = func(*args, **kwargs)
                
                # Measure performance
                end_time = time.time()
                processing_time = end_time - start_time
                
                if measure_performance:
                    func_metadata['execution_time'] = processing_time
                    try:
                        func_metadata['memory_usage'] = psutil.Process().memory_info().rss
                    except (ImportError, OSError, AttributeError) as e:
                        _logger.debug(f"Failed to get memory usage: {e}")
                
                # Log successful execution
                logger.log_activity(
                    user_id, username, role, action_name, module_name, 
                    details, "success", log_level, security_level, func_metadata,
                    processing_time=processing_time
                )
                
                return result
                
            except Exception as e:
                # Measure performance even for errors
                end_time = time.time()
                processing_time = end_time - start_time
                
                if measure_performance:
                    func_metadata['execution_time'] = processing_time
                    func_metadata['error_type'] = type(e).__name__
                
                # Log the error with stack trace
                error_details = f"Error in {func.__name__}: {str(e)}"
                func_metadata['stack_trace'] = traceback.format_exc()
                
                logger.log_activity(
                    user_id, username, role, f"{action_name}_error", module_name, 
                    error_details, "failure", LogLevel.ERROR, SecurityLevel.MEDIUM, 
                    func_metadata, processing_time=processing_time
                )
                raise
                
        return wrapper
    return decorator


# Specialized decorators for different operations
def log_create(module, description=None, **kwargs):
    """Enhanced decorator for create operations"""
    return enhanced_log_activity(
        action="create", module=module, description=description,
        security_level=SecurityLevel.MEDIUM, **kwargs
    )

def log_read(module, description=None, **kwargs):
    """Enhanced decorator for read operations"""
    return enhanced_log_activity(
        action="read", module=module, description=description,
        log_level=LogLevel.DEBUG, **kwargs
    )

def log_update(module, description=None, **kwargs):
    """Enhanced decorator for update operations"""
    return enhanced_log_activity(
        action="update", module=module, description=description,
        security_level=SecurityLevel.MEDIUM, **kwargs
    )

def log_delete(module, description=None, **kwargs):
    """Enhanced decorator for delete operations"""
    return enhanced_log_activity(
        action="delete", module=module, description=description,
        log_level=LogLevel.WARNING, security_level=SecurityLevel.HIGH, **kwargs
    )

def log_search(module, description=None, **kwargs):
    """Enhanced decorator for search operations"""
    return enhanced_log_activity(
        action="search", module=module, description=description, **kwargs
    )

def log_export(module, description=None, **kwargs):
    """Enhanced decorator for export operations"""
    return enhanced_log_activity(
        action="export", module=module, description=description,
        security_level=SecurityLevel.HIGH, **kwargs
    )

def log_admin_action(module, description=None, **kwargs):
    """Enhanced decorator for administrative operations"""
    return enhanced_log_activity(
        action="admin", module=module, description=description,
        log_level=LogLevel.WARNING, security_level=SecurityLevel.CRITICAL, **kwargs
    )

def log_menu_navigation(description=None, **kwargs):
    """Enhanced decorator for menu navigation operations"""
    return enhanced_log_activity(
        action="menu_navigation", module="navigation", description=description,
        log_level=LogLevel.DEBUG, **kwargs
    )


# Plugin System
class LoggerPlugin:
    """Base class for logger plugins"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', True)
    
    def before_log(self, log_entry: LogEntry) -> LogEntry:
        """Called before logging - can modify log entry"""
        if not self.enabled:
            return log_entry
        return log_entry
    
    def after_log(self, log_entry: LogEntry, success: bool):
        """Called after logging attempt"""
        if not self.enabled:
            return
    
    def on_shutdown(self):
        """
        Called during logger shutdown

        Override this method in subclasses to perform cleanup operations such as:
        - Flushing pending messages
        - Closing database connections
        - Releasing file handles
        - Cleaning up temporary resources
        - Sending final notifications
        """
        # Base implementation does nothing - subclasses should override
        # to implement their specific cleanup logic
        if self.enabled:
            # Subclasses can add their cleanup logic here
            pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get plugin status information"""
        return {
            'name': self.__class__.__name__,
            'enabled': self.enabled,
            'config': self.config
        }


class PluginManager:
    """Manage logger plugins"""
    
    def __init__(self):
        self.plugins: List[LoggerPlugin] = []
    
    def register_plugin(self, plugin: LoggerPlugin):
        """Register a new plugin"""
        self.plugins.append(plugin)
        print(f"Registered plugin: {plugin.__class__.__name__}")
    
    def unregister_plugin(self, plugin_class: str):
        """Unregister a plugin by class name"""
        self.plugins = [p for p in self.plugins if p.__class__.__name__ != plugin_class]
    
    def before_log(self, log_entry: LogEntry) -> LogEntry:
        """Apply all plugins' before_log methods"""
        for plugin in self.plugins:
            try:
                log_entry = plugin.before_log(log_entry)
            except Exception as e:
                print(f"Plugin {plugin.__class__.__name__} before_log error: {e}")
        return log_entry
    
    def after_log(self, log_entry: LogEntry, success: bool):
        """Apply all plugins' after_log methods"""
        for plugin in self.plugins:
            try:
                plugin.after_log(log_entry, success)
            except Exception as e:
                print(f"Plugin {plugin.__class__.__name__} after_log error: {e}")
    
    def shutdown_plugins(self):
        """Shutdown all plugins"""
        for plugin in self.plugins:
            try:
                plugin.on_shutdown()
            except Exception as e:
                print(f"Plugin {plugin.__class__.__name__} shutdown error: {e}")
    
    def get_plugin_status(self) -> List[Dict[str, Any]]:
        """Get status of all plugins"""
        return [plugin.get_status() for plugin in self.plugins]


# Example plugins
class SlackNotificationPlugin(LoggerPlugin):
    """Plugin to send critical alerts to Slack"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.webhook_url = config.get('slack_webhook_url')
        self.last_notification = {}  # Rate limiting
        self.rate_limit_seconds = config.get('rate_limit_seconds', 300)  # 5 minutes
    
    def after_log(self, log_entry: LogEntry, success: bool):
        if not success or not self.webhook_url:
            return
        
        if (log_entry.security_level == SecurityLevel.CRITICAL.name or 
            log_entry.log_level == LogLevel.CRITICAL.name):
            self._send_slack_notification(log_entry)
    
    def _send_slack_notification(self, log_entry: LogEntry):
        """Send notification to Slack with rate limiting"""
        # Rate limiting by user and action
        key = f"{log_entry.username}:{log_entry.action}"
        now = time.time()
        
        if key in self.last_notification:
            if now - self.last_notification[key] < self.rate_limit_seconds:
                return  # Skip due to rate limiting
        
        self.last_notification[key] = now
        
        try:
            color = "danger" if log_entry.security_level == "CRITICAL" else "warning"
            
            message = {
                "text": f"🚨 Critical Activity Alert",
                "attachments": [{
                    "color": color,
                    "fields": [
                        {"title": "User", "value": log_entry.username, "short": True},
                        {"title": "Action", "value": log_entry.action, "short": True},
                        {"title": "Module", "value": log_entry.module, "short": True},
                        {"title": "Status", "value": log_entry.status, "short": True},
                        {"title": "Timestamp", "value": log_entry.timestamp, "short": True},
                        {"title": "IP Address", "value": log_entry.ip_address, "short": True},
                        {"title": "Details", "value": log_entry.details[:500], "short": False}
                    ],
                    "footer": f"Trace ID: {log_entry.trace_id}"
                }]
            }
            
            response = requests.post(self.webhook_url, json=message, timeout=10)
            response.raise_for_status()
            
        except Exception as e:
            print(f"Failed to send Slack notification: {e}")


class MetricsCollectionPlugin(LoggerPlugin):
    """Plugin to collect metrics for monitoring systems"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.metrics = {
            'total_logs': 0,
            'error_count': 0,
            'security_alerts': 0,
            'action_counts': {},
            'user_activity': {},
            'module_usage': {},
            'hourly_activity': {},
            'last_reset': time.time()
        }
        self.reset_interval = config.get('reset_interval_hours', 24) * 3600
    
    def after_log(self, log_entry: LogEntry, success: bool):
        if not success:
            return
        
        # Check if we need to reset metrics
        if time.time() - self.metrics['last_reset'] > self.reset_interval:
            self._reset_metrics()
        
        self.metrics['total_logs'] += 1
        
        if log_entry.status == 'failure':
            self.metrics['error_count'] += 1
        
        if log_entry.security_level in [SecurityLevel.HIGH.name, SecurityLevel.CRITICAL.name]:
            self.metrics['security_alerts'] += 1
        
        # Count actions
        action = log_entry.action
        self.metrics['action_counts'][action] = self.metrics['action_counts'].get(action, 0) + 1
        
        # Count user activity
        user = log_entry.username
        self.metrics['user_activity'][user] = self.metrics['user_activity'].get(user, 0) + 1
        
        # Count module usage
        module = log_entry.module
        self.metrics['module_usage'][module] = self.metrics['module_usage'].get(module, 0) + 1
        
        # Count hourly activity
        try:
            hour = datetime.strptime(log_entry.timestamp, "%Y-%m-%d %H:%M:%S.%f").hour
            self.metrics['hourly_activity'][hour] = self.metrics['hourly_activity'].get(hour, 0) + 1
        except (ValueError, AttributeError) as e:
            _logger.debug(f"Failed to parse log entry timestamp for metrics: {e}")
    
    def _reset_metrics(self):
        """Reset metrics (keeping structure)"""
        self.metrics = {
            'total_logs': 0,
            'error_count': 0,
            'security_alerts': 0,
            'action_counts': {},
            'user_activity': {},
            'module_usage': {},
            'hourly_activity': {},
            'last_reset': time.time()
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        metrics_copy = self.metrics.copy()
        
        # Add calculated metrics
        if metrics_copy['total_logs'] > 0:
            metrics_copy['error_rate'] = (metrics_copy['error_count'] / metrics_copy['total_logs']) * 100
            metrics_copy['security_alert_rate'] = (metrics_copy['security_alerts'] / metrics_copy['total_logs']) * 100
        else:
            metrics_copy['error_rate'] = 0
            metrics_copy['security_alert_rate'] = 0
        
        # Add top items
        metrics_copy['top_actions'] = dict(sorted(metrics_copy['action_counts'].items(), key=lambda x: x[1], reverse=True)[:10])
        metrics_copy['top_users'] = dict(sorted(metrics_copy['user_activity'].items(), key=lambda x: x[1], reverse=True)[:10])
        metrics_copy['top_modules'] = dict(sorted(metrics_copy['module_usage'].items(), key=lambda x: x[1], reverse=True)[:10])
        
        return metrics_copy
    
    def get_status(self) -> Dict[str, Any]:
        """Get plugin status with current metrics"""
        status = super().get_status()
        status['current_metrics'] = self.get_metrics()
        return status


class EmailNotificationPlugin(LoggerPlugin):
    """Plugin to send email notifications for critical events"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.smtp_server = config.get('smtp_server')
        self.smtp_port = config.get('smtp_port', 587)
        self.smtp_username = config.get('smtp_username')
        self.smtp_password = config.get('smtp_password')
        self.from_email = config.get('from_email')
        self.to_emails = config.get('to_emails', [])
        self.last_notification = {}
        self.rate_limit_seconds = config.get('rate_limit_seconds', 600)  # 10 minutes
    
    def after_log(self, log_entry: LogEntry, success: bool):
        if not success or not self._is_configured():
            return
        
        if log_entry.security_level == SecurityLevel.CRITICAL.name:
            self._send_email_notification(log_entry)
    
    def _is_configured(self) -> bool:
        """Check if email plugin is properly configured"""
        return all([
            self.smtp_server,
            self.smtp_username,
            self.smtp_password,
            self.from_email,
            self.to_emails
        ])
    
    def _send_email_notification(self, log_entry: LogEntry):
        """Send email notification with rate limiting"""
        # Rate limiting
        key = f"{log_entry.username}:{log_entry.action}"
        now = time.time()

        if key in self.last_notification:
            if now - self.last_notification[key] < self.rate_limit_seconds:
                return

        self.last_notification[key] = now

        try:
            from university_system.infrastructure.email.smtp import send_email_via_smtp

            # Prepare template variables
            template_vars = {
                'timestamp': log_entry.timestamp,
                'username': log_entry.username,
                'role': log_entry.role,
                'action': log_entry.action,
                'module': log_entry.module,
                'status': log_entry.status,
                'ip_address': log_entry.ip_address,
                'security_level': log_entry.security_level,
                'details': log_entry.details,
                'trace_id': log_entry.trace_id
            }

            # Try to use template
            try:
                from university_system.infrastructure.email.template_utils import render_template
                subject, body = render_template('security_alert', template_vars)
            except Exception as e:
                # Fallback to hardcoded message
                subject = f"CRITICAL: Security Alert - {log_entry.action}"
                body = f"""
CRITICAL SECURITY ALERT

Timestamp: {log_entry.timestamp}
User: {log_entry.username} ({log_entry.role})
Action: {log_entry.action}
Module: {log_entry.module}
Status: {log_entry.status}
IP Address: {log_entry.ip_address}
Security Level: {log_entry.security_level}

Details: {log_entry.details}

Trace ID: {log_entry.trace_id}

This is an automated alert from the Enhanced Activity Logger.
Please investigate this activity immediately.
            """

            # Send to first recipient with others as CC
            recipient_email = self.to_emails[0]
            cc = self.to_emails[1:] if len(self.to_emails) > 1 else None

            current_time = datetime.now().isoformat()
            success = send_email_via_smtp(
                recipient_email=recipient_email,
                subject=subject,
                body=body,
                cc=cc,
                bcc=None,
                attachments=None,
                current_time=current_time
            )

            if success:
                print(f"Critical alert email sent for {log_entry.username}:{log_entry.action}")
            else:
                print(f"Failed to send email notification for {log_entry.username}:{log_entry.action}")

        except Exception as e:
            print(f"Failed to send email notification: {e}")


class AuditTrailPlugin(LoggerPlugin):
    """Plugin to maintain a separate audit trail for compliance"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.audit_file = config.get('audit_file', 'audit_trail.log')
        self.audit_actions = set(config.get('audit_actions', [
            'create', 'update', 'delete', 'login', 'logout', 'export', 'admin'
        ]))
        self._lock = threading.Lock()
    
    def after_log(self, log_entry: LogEntry, success: bool):
        if not success or log_entry.action not in self.audit_actions:
            return
        
        # Create audit entry
        audit_entry = {
            'timestamp': log_entry.timestamp,
            'trace_id': log_entry.trace_id,
            'user_id': log_entry.user_id,
            'username': log_entry.username,
            'action': log_entry.action,
            'module': log_entry.module,
            'status': log_entry.status,
            'ip_address': log_entry.ip_address,
            'details': log_entry.details,
            'security_level': log_entry.security_level
        }
        
        # Write to audit file (thread-safe)
        with self._lock:
            try:
                with open(self.audit_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(audit_entry) + '\n')
            except Exception as e:
                print(f"Failed to write audit entry: {e}")
    
    def get_audit_stats(self) -> Dict[str, Any]:
        """Get audit trail statistics"""
        if not os.path.exists(self.audit_file):
            return {'total_entries': 0, 'file_size': 0}
        
        try:
            line_count = 0
            with open(self.audit_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        line_count += 1
            
            file_size = os.path.getsize(self.audit_file)
            
            return {
                'total_entries': line_count,
                'file_size': file_size,
                'file_path': self.audit_file
            }
        except Exception as e:
            return {'error': str(e)}


# Create singleton instance with plugin support
logger = EnhancedActivityLogger()
plugin_manager = PluginManager()

# Module-level log_activity function for direct imports
def log_activity(user_id, username, role, action, module, details=None, status="success", **kwargs):
    """
    Module-level wrapper for the logger's log_activity method
    """
    return logger.log_activity(
        user_id, username, role, action, module, 
        details, status, **kwargs
    )


# Helper functions for backward compatibility
def log_login(user_id, username, role, status="success", details=None):
    """Log a user login attempt"""
    return logger.log_activity(
        user_id, username, role, "login", "authentication", 
        details, status, LogLevel.INFO, SecurityLevel.LOW
    )

def log_logout(user_id, username, role):
    """Log a user logout"""
    return logger.log_activity(
        user_id, username, role, "logout", "authentication",
        status="success", log_level=LogLevel.INFO
    )

def log_dynamic_activity(action, module, details=None, **kwargs):
    """
    Log an activity dynamically within a function
    """
    # Simplified user context (no auth imports)
    user_id = 'system'
    username = 'system'
    role = 'system'
    
    return logger.log_activity(user_id, username, role, action, module, details, **kwargs)


# Configuration management
def load_logger_config(config_path: str):
    """Load logger configuration from file"""
    global logger
    if logger:
        logger.shutdown()
    logger = EnhancedActivityLogger(config_path)

def get_logger_instance() -> EnhancedActivityLogger:
    """Get the singleton logger instance"""
    return logger

def register_plugin(plugin: LoggerPlugin):
    """Register a plugin with the logger"""
    plugin_manager.register_plugin(plugin)

def unregister_plugin(plugin_class: str):
    """Unregister a plugin by class name"""
    plugin_manager.unregister_plugin(plugin_class)

def get_plugin_status() -> List[Dict[str, Any]]:
    """Get status of all registered plugins"""
    return plugin_manager.get_plugin_status()


# Utility functions
def create_default_config(output_path: str = 'logger_config.json'):
    """Create a default configuration file"""
    default_config = {
        "log_dir": "enhanced_logs",
        "min_log_level": "INFO",
        "output_formats": ["json", "database"],
        "queue_size": 10000,
        "batch_size": 100,
        "flush_interval": 5,
        "encrypt_logs": False,
        "enable_pii_detection": True,
        "security": {
            "max_failed_attempts": 5,
            "lockout_window": 15,
            "max_requests_per_minute": 100,
            "sensitive_actions": [
                "delete", "modify_permissions", "create_admin", 
                "export_data", "system_config"
            ],
            "privileged_roles": ["admin", "superuser", "root"]
        },
        "rotation": {
            "max_file_size": 100 * 1024 * 1024,
            "retention_days": 30,
            "compress_old_logs": True
        },
        "cloud": {
            "enabled_services": [],
            "webhook_url": None,
            "elasticsearch": {
                "url": "http://localhost:9200",
                "index": "activity-logs"
            }
        },
        "security_alerts": {
            "webhook_enabled": False,
            "webhook_url": None
        }
    }
    
    with open(output_path, 'w') as f:
        json.dump(default_config, f, indent=2)
    
    print(f"Default configuration created at: {output_path}")
    return output_path


# Example usage and configuration
if __name__ == "__main__":
    # Create example configuration
    config_file = create_default_config('example_config.json')
    
    # Initialize logger with config
    enhanced_logger = EnhancedActivityLogger(config_file)
    
    # Register example plugins
    slack_plugin = SlackNotificationPlugin({
        'enabled': True,
        'slack_webhook_url': 'https://hooks.slack.com/your-webhook-url',
        'rate_limit_seconds': 300
    })
    
    metrics_plugin = MetricsCollectionPlugin({
        'enabled': True,
        'reset_interval_hours': 24
    })
    
    audit_plugin = AuditTrailPlugin({
        'enabled': True,
        'audit_file': 'compliance_audit.log',
        'audit_actions': ['create', 'update', 'delete', 'admin', 'export']
    })
    
    register_plugin(slack_plugin)
    register_plugin(metrics_plugin)
    register_plugin(audit_plugin)
    
    # Example usage with decorators
    @log_create("user_management", "Creating new user account")
    def create_user(username, email):
        """Example function with logging decorator"""
        print(f"Creating user: {username} ({email})")
        return {"id": 123, "username": username, "email": email}
    
    @log_delete("user_management", "Deleting user account")
    def delete_user(user_id):
        """Example function that might raise an error"""
        if user_id == "invalid":
            raise ValueError("Invalid user ID")
        print(f"Deleting user: {user_id}")
        return True
    
    # Test the enhanced logger
    try:
        print("Testing Enhanced Activity Logger...")
        
        # Test normal operations
        create_user("john_doe", "john@example.com")
        
        # Test direct logging
        enhanced_logger.log_activity(
            "user_123", "admin", "administrator",
            "system_config", "settings",
            "Updated system configuration",
            "success", LogLevel.WARNING, SecurityLevel.HIGH,
            {"config_section": "security", "changes": ["password_policy", "session_timeout"]}
        )
        
        # Test error handling
        try:
            delete_user("invalid")
        except ValueError as e:
            _logger.debug(f"Expected error in test: {e}")
        
        # Test failed login (security monitoring)
        enhanced_logger.log_activity(
            "user_456", "hacker", "user",
            "login", "authentication",
            "Failed login attempt",
            "failure", LogLevel.WARNING, SecurityLevel.HIGH
        )
        
        # Wait for processing
        time.sleep(2)
        
        # Generate reports if analytics available
        if enhanced_logger.analytics:
            print("\nGenerating summary report...")
            report = enhanced_logger.generate_report("summary")
            print(f"Total activities: {report.get('total_activities', 0)}")
            print(f"Error rate: {report.get('error_rate', 0):.2f}%")
            
            # Get system health
            health = enhanced_logger.get_system_health()
            print(f"\nSystem Health - CPU: {health.get('cpu_usage', 0):.1f}%, Memory: {health.get('memory_usage', 0):.1f}%")
            
            # Check for anomalies
            anomalies = enhanced_logger.detect_anomalies()
            if anomalies:
                print(f"\nFound {len(anomalies)} anomalies:")
                for anomaly in anomalies[:3]:  # Show first 3
                    print(f"  - {anomaly['type']}: {anomaly.get('severity', 'unknown')} severity")
        
        # Show plugin status
        print(f"\nPlugin Status:")
        for plugin_status in get_plugin_status():
            print(f"  - {plugin_status['name']}: {'Enabled' if plugin_status['enabled'] else 'Disabled'}")
        
        # Show metrics
        if hasattr(metrics_plugin, 'get_metrics'):
            metrics = metrics_plugin.get_metrics()
            print(f"\nMetrics - Total logs: {metrics['total_logs']}, Errors: {metrics['error_count']}")
        
        # Flush all pending logs
        print("\nFlushing logs...")
        enhanced_logger.flush_logs(timeout=10)
        
        print("Enhanced Activity Logger test completed successfully!")
        
    except Exception as e:
        print(f"Error during testing: {e}")
        traceback.print_exc()
        
    finally:
        # Graceful shutdown
        print("\nShutting down...")
        plugin_manager.shutdown_plugins()
        enhanced_logger.shutdown(timeout=15)
        print("Shutdown complete.")
