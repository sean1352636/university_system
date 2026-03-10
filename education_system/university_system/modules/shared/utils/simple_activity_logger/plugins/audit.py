import os
import json
import threading
from typing import Dict, Any

from ..models import LogEntry
from .base import LoggerPlugin


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
