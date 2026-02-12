#!/usr/bin/env python3
"""
Comprehensive Security Module
Combines all security features:
- API Security & Rate Limiting
- Password Security Enhancements
- Security Audit & Compliance
- Data Loss Prevention
- Incident Response
- Vulnerability Scanning
"""

import os
import sys
from university_system.infrastructure.database.db import sqlite3
import hashlib
import secrets
import json
import re
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import time

# Import centralized database path and connection utilities
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from modules.shared.constants.paths import DEFAULT_DB_PATH
from university_system.infrastructure.database.db import get_connection
from university_system.core.i18n import get_text, _

class APISecurityManager:
    """API Security with rate limiting and key management"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(DEFAULT_DB_PATH)
        self.db_path = db_path

    def _get_connection(self):
        return get_connection(db_path=self.db_path, row_factory=True)

    def create_api_key(self, user_id: int, key_name: str, permissions: List[str],
                      rate_limit: int = 1000, expires_days: int = 365) -> Dict:
        """Create API key for user"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Generate API key
            api_key = f"uni_{secrets.token_urlsafe(32)}"
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()

            expires_at = datetime.now() + timedelta(days=expires_days)

            cursor.execute("""
                INSERT INTO api_keys (
                    user_id, key_hash, key_name, permissions,
                    expires_at, rate_limit
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, key_hash, key_name, json.dumps(permissions),
                  expires_at, rate_limit))

            conn.commit()

            return {
                'success': True,
                'api_key': api_key,  # Only shown once!
                'key_name': key_name,
                'expires_at': expires_at.isoformat()
            }

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def validate_api_key(self, api_key: str) -> Dict:
        """Validate API key"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()

            cursor.execute("""
                SELECT id, user_id, permissions, expires_at, is_active, rate_limit
                FROM api_keys
                WHERE key_hash = ?
            """, (key_hash,))

            row = cursor.fetchone()

            if not row:
                return {'valid': False, 'reason': 'Invalid API key'}

            key_id, user_id, permissions, expires_at, is_active, rate_limit = row

            if not is_active:
                return {'valid': False, 'reason': 'API key deactivated'}

            if datetime.fromisoformat(expires_at) < datetime.now():
                return {'valid': False, 'reason': 'API key expired'}

            # Update last used
            cursor.execute("""
                UPDATE api_keys SET last_used_at = ? WHERE id = ?
            """, (datetime.now(), key_id))

            conn.commit()

            return {
                'valid': True,
                'key_id': key_id,
                'user_id': user_id,
                'permissions': json.loads(permissions),
                'rate_limit': rate_limit
            }

        finally:
            conn.close()

    def check_rate_limit(self, identifier: str, identifier_type: str,
                        endpoint: str, limit: int = 1000) -> Dict:
        """
        Check and update rate limit

        Args:
            identifier: User ID, API key hash, or IP address
            identifier_type: 'user', 'api_key', or 'ip'
            endpoint: API endpoint
            limit: Requests per hour

        Returns:
            Dict with allowed status and remaining requests
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            now = datetime.now()
            window_start = now - timedelta(hours=1)

            # Get or create rate limit record
            cursor.execute("""
                SELECT id, request_count, window_start
                FROM api_rate_limits
                WHERE identifier = ? AND identifier_type = ? AND endpoint = ?
            """, (identifier, identifier_type, endpoint))

            row = cursor.fetchone()

            if row:
                rate_id, count, window = row
                window_dt = datetime.fromisoformat(window)

                # Check if window expired
                if window_dt < window_start:
                    # Reset counter
                    cursor.execute("""
                        UPDATE api_rate_limits
                        SET request_count = 1, window_start = ?, last_request = ?
                        WHERE id = ?
                    """, (now, now, rate_id))
                    conn.commit()

                    return {'allowed': True, 'remaining': limit - 1, 'reset_at': (now + timedelta(hours=1)).isoformat()}

                # Check limit
                if count >= limit:
                    reset_at = window_dt + timedelta(hours=1)
                    return {
                        'allowed': False,
                        'reason': 'Rate limit exceeded',
                        'limit': limit,
                        'reset_at': reset_at.isoformat()
                    }

                # Increment counter
                cursor.execute("""
                    UPDATE api_rate_limits
                    SET request_count = request_count + 1, last_request = ?
                    WHERE id = ?
                """, (now, rate_id))

                remaining = limit - (count + 1)

            else:
                # Create new record
                cursor.execute("""
                    INSERT INTO api_rate_limits (
                        identifier, identifier_type, endpoint, request_count, window_start
                    )
                    VALUES (?, ?, ?, 1, ?)
                """, (identifier, identifier_type, endpoint, now))

                remaining = limit - 1

            conn.commit()

            reset_at = now + timedelta(hours=1)
            return {
                'allowed': True,
                'remaining': remaining,
                'limit': limit,
                'reset_at': reset_at.isoformat()
            }

        except Exception as e:
            return {'allowed': False, 'error': str(e)}
        finally:
            conn.close()

class PasswordSecurityManager:
    """Enhanced password security"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(DEFAULT_DB_PATH)
        self.db_path = db_path

    def _get_connection(self):
        return get_connection(db_path=self.db_path, row_factory=True)

    def calculate_password_strength(self, password: str) -> Dict:
        """
        Calculate password strength score (0-100)

        Checks:
        - Length
        - Character diversity
        - Common patterns
        - Dictionary words
        """
        score = 0
        feedback = []

        # Length check
        length = len(password)
        if length >= 12:
            score += 25
        elif length >= 8:
            score += 15
            feedback.append("Increase length to 12+ characters")
        else:
            score += 5
            feedback.append("Password too short (minimum 8)")

        # Character diversity
        has_lower = bool(re.search(r'[a-z]', password))
        has_upper = bool(re.search(r'[A-Z]', password))
        has_digit = bool(re.search(r'\d', password))
        has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password))

        diversity_score = sum([has_lower, has_upper, has_digit, has_special]) * 15
        score += diversity_score

        if not has_upper:
            feedback.append("Add uppercase letters")
        if not has_digit:
            feedback.append("Add numbers")
        if not has_special:
            feedback.append("Add special characters")

        # Common patterns penalty
        common_patterns = [
            r'12345', r'password', r'qwerty', r'abc123',
            r'letmein', r'welcome', r'monkey', r'dragon'
        ]

        for pattern in common_patterns:
            if pattern in password.lower():
                score -= 20
                feedback.append("Avoid common patterns")
                break

        # Sequential characters penalty
        if re.search(r'(abc|bcd|cde|123|234|345)', password.lower()):
            score -= 10
            feedback.append("Avoid sequential characters")

        # Repeated characters penalty
        if re.search(r'(.)\1{2,}', password):
            score -= 10
            feedback.append("Avoid repeating characters")

        # Cap score
        score = max(0, min(100, score))

        # Strength rating
        if score >= 80:
            strength = "strong"
        elif score >= 60:
            strength = "good"
        elif score >= 40:
            strength = "fair"
        else:
            strength = "weak"

        return {
            'score': score,
            'strength': strength,
            'feedback': feedback
        }

    def check_compromised_password(self, password: str) -> Dict:
        """
        Check if password has been compromised using Have I Been Pwned API

        Uses k-anonymity - only sends first 5 chars of hash
        """
        try:
            # Hash password
            sha1_hash = hashlib.sha1(password.encode()).hexdigest().upper()
            prefix = sha1_hash[:5]
            suffix = sha1_hash[5:]

            # Query HIBP API
            url = f"https://api.pwnedpasswords.com/range/{prefix}"
            response = requests.get(url, timeout=3)

            if response.status_code == 200:
                # Check if hash suffix exists in response
                hashes = response.text.split('\r\n')
                for hash_line in hashes:
                    hash_suffix, count = hash_line.split(':')
                    if hash_suffix == suffix:
                        return {
                            'compromised': True,
                            'count': int(count),
                            'message': f'This password has appeared in {count} data breaches'
                        }

                return {'compromised': False, 'message': 'Password not found in known breaches'}

            return {'compromised': False, 'error': 'Unable to check'}

        except Exception as e:
            return {'compromised': False, 'error': str(e)}

    def add_to_password_history(self, user_id: int, password_hash: str) -> None:
        """Add password to user's history"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO password_history (user_id, password_hash)
                VALUES (?, ?)
            """, (user_id, password_hash))

            # Keep only last 5 passwords
            cursor.execute("""
                DELETE FROM password_history
                WHERE user_id = ? AND id NOT IN (
                    SELECT id FROM password_history
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT 5
                )
            """, (user_id, user_id))

            # Update policy compliance
            cursor.execute("""
                INSERT INTO password_policy_compliance (
                    user_id, last_password_change
                )
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    last_password_change = ?
            """, (user_id, datetime.now(), datetime.now()))

            conn.commit()

        finally:
            conn.close()

    def check_password_reuse(self, user_id: int, new_password_hash: str) -> bool:
        """Check if password was used before"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT COUNT(*) FROM password_history
                WHERE user_id = ? AND password_hash = ?
            """, (user_id, new_password_hash))

            return cursor.fetchone()[0] > 0

        finally:
            conn.close()

class SecurityAuditManager:
    """Security audit and compliance tracking"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(DEFAULT_DB_PATH)
        self.db_path = db_path

    def _get_connection(self):
        return get_connection(db_path=self.db_path, row_factory=True)

    def log_security_event(self, user_id: Optional[int], event_type: str,
                          details: Dict, severity: str = 'medium',
                          ip_address: str = None) -> None:
        """Log security event"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO security_events (
                    user_id, event_type, details, severity, ip_address
                )
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, event_type, json.dumps(details), severity, ip_address))

            conn.commit()

        finally:
            conn.close()

    def log_data_access(self, user_id: int, resource_type: str,
                       resource_id: int, action: str,
                       session_id: int = None, ip_address: str = None) -> None:
        """Log data access for compliance"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO data_access_log (
                    user_id, resource_type, resource_id, action,
                    session_id, ip_address
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, resource_type, resource_id, action, session_id, ip_address))

            conn.commit()

        finally:
            conn.close()

    def log_permission_change(self, changed_by: int, target_user_id: int,
                             permission_name: str, action: str,
                             reason: str = None) -> None:
        """Log permission changes for audit"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO permission_changes_log (
                    changed_by, target_user_id, permission_name, action, reason
                )
                VALUES (?, ?, ?, ?, ?)
            """, (changed_by, target_user_id, permission_name, action, reason))

            conn.commit()

        finally:
            conn.close()

    def generate_compliance_report(self, start_date: datetime,
                                   end_date: datetime,
                                   report_type: str = 'ferpa') -> Dict:
        """
        Generate compliance report (FERPA/GDPR)

        Args:
            start_date: Report start date
            end_date: Report end date
            report_type: 'ferpa' or 'gdpr'

        Returns:
            Dict with compliance metrics
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            report = {
                'report_type': report_type,
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                }
            }

            # Data access summary
            cursor.execute("""
                SELECT resource_type, action, COUNT(*) as count
                FROM data_access_log
                WHERE accessed_at BETWEEN ? AND ?
                GROUP BY resource_type, action
                ORDER BY count DESC
            """, (start_date, end_date))

            report['data_access'] = [
                {'resource': row[0], 'action': row[1], 'count': row[2]}
                for row in cursor.fetchall()
            ]

            # Security events summary
            cursor.execute("""
                SELECT event_type, severity, COUNT(*) as count
                FROM security_events
                WHERE event_time BETWEEN ? AND ?
                GROUP BY event_type, severity
                ORDER BY count DESC
            """, (start_date, end_date))

            report['security_events'] = [
                {'type': row[0], 'severity': row[1], 'count': row[2]}
                for row in cursor.fetchall()
            ]

            # Permission changes
            cursor.execute("""
                SELECT COUNT(*) FROM permission_changes_log
                WHERE changed_at BETWEEN ? AND ?
            """, (start_date, end_date))

            report['permission_changes'] = cursor.fetchone()[0]

            # Failed login attempts
            cursor.execute("""
                SELECT COUNT(*) FROM security_events
                WHERE event_type = 'failed_login'
                  AND event_time BETWEEN ? AND ?
            """, (start_date, end_date))

            report['failed_logins'] = cursor.fetchone()[0]

            # Bulk exports (potential data leaks)
            cursor.execute("""
                SELECT user_id, export_type, SUM(record_count) as total
                FROM bulk_export_log
                WHERE exported_at BETWEEN ? AND ?
                GROUP BY user_id, export_type
                ORDER BY total DESC
                LIMIT 10
            """, (start_date, end_date))

            report['bulk_exports'] = [
                {'user_id': row[0], 'type': row[1], 'records': row[2]}
                for row in cursor.fetchall()
            ]

            return report

        finally:
            conn.close()

class DataLossPreventionManager:
    """Data Loss Prevention system"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(DEFAULT_DB_PATH)
        self.db_path = db_path

        # Bulk export thresholds
        self.export_thresholds = {
            'student': 100,  # Max 100 student records
            'grade': 500,
            'staff': 50,
            'default': 100
        }

    def _get_connection(self):
        return get_connection(db_path=self.db_path, row_factory=True)

    def request_bulk_export(self, user_id: int, export_type: str,
                           resource_type: str, record_count: int,
                           ip_address: str = None) -> Dict:
        """
        Request permission for bulk export

        Returns:
            Dict with approval status
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            threshold = self.export_thresholds.get(resource_type,
                                                   self.export_thresholds['default'])

            # Log export request
            cursor.execute("""
                INSERT INTO bulk_export_log (
                    user_id, export_type, resource_type, record_count,
                    ip_address, status
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, export_type, resource_type, record_count, ip_address,
                  'pending' if record_count > threshold else 'auto_approved'))

            export_id = cursor.lastrowid

            # Auto-approve if under threshold
            if record_count <= threshold:
                cursor.execute("""
                    UPDATE bulk_export_log
                    SET status = 'auto_approved'
                    WHERE id = ?
                """, (export_id,))

                conn.commit()

                return {
                    'approved': True,
                    'export_id': export_id,
                    'reason': 'Under threshold'
                }

            # Require approval
            conn.commit()

            return {
                'approved': False,
                'export_id': export_id,
                'reason': f'Exceeds threshold ({record_count} > {threshold})',
                'requires_approval': True
            }

        except Exception as e:
            conn.rollback()
            return {'approved': False, 'error': str(e)}
        finally:
            conn.close()

    def detect_pii_in_text(self, text: str) -> List[Dict]:
        """
        Detect PII in text

        Returns:
            List of detected PII with types
        """
        pii_found = []

        # SSN pattern
        ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
        if re.search(ssn_pattern, text):
            pii_found.append({'type': 'SSN', 'pattern': 'XXX-XX-XXXX'})

        # Credit card pattern
        cc_pattern = r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b'
        if re.search(cc_pattern, text):
            pii_found.append({'type': 'Credit Card', 'pattern': 'XXXX-XXXX-XXXX-XXXX'})

        # Email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        if emails:
            pii_found.append({'type': 'Email', 'count': len(emails)})

        # Phone pattern
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        phones = re.findall(phone_pattern, text)
        if phones:
            pii_found.append({'type': 'Phone', 'count': len(phones)})

        return pii_found

class IncidentResponseManager:
    """Security incident response system"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(DEFAULT_DB_PATH)
        self.db_path = db_path

    def _get_connection(self):
        return get_connection(db_path=self.db_path, row_factory=True)

    def create_incident(self, incident_type: str, severity: str,
                       description: str, detected_by: int,
                       affected_users: List[int] = None,
                       affected_resources: List[str] = None) -> Dict:
        """Create security incident"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO security_incidents (
                    category, severity, description, reported_by,
                    status, detected_at
                )
                VALUES (?, ?, ?, ?, 'open', CURRENT_TIMESTAMP)
            """, (
                incident_type, severity, description, detected_by
            ))

            incident_id = cursor.lastrowid
            conn.commit()

            return {
                'success': True,
                'incident_id': incident_id,
                'status': 'open'
            }

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def log_incident_action(self, incident_id: int, action_type: str,
                           action_details: Dict, performed_by: int) -> None:
        """Log incident response action"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO incident_response_actions (
                    incident_id, action_type, action_details, performed_by
                )
                VALUES (?, ?, ?, ?)
            """, (incident_id, action_type, json.dumps(action_details), performed_by))

            conn.commit()

        finally:
            conn.close()

class VulnerabilityScanner:
    """Basic vulnerability scanner"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(DEFAULT_DB_PATH)
        self.db_path = db_path

    def _get_connection(self):
        return get_connection(db_path=self.db_path, row_factory=True)

    def scan_sql_injection(self, query: str) -> Dict:
        """Basic SQL injection detection"""
        dangerous_patterns = [
            r"(\bOR\b.*=.*)",
            r"(\bUNION\b.*\bSELECT\b)",
            r"(--;)",
            r"('.*OR.*'.*=.*')",
            r"(\bDROP\b.*\bTABLE\b)"
        ]

        vulnerabilities = []

        for pattern in dangerous_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                vulnerabilities.append({
                    'type': 'SQL Injection',
                    'pattern': pattern,
                    'severity': 'high'
                })

        return {
            'scan_type': 'sql_injection',
            'vulnerable': len(vulnerabilities) > 0,
            'vulnerabilities': vulnerabilities
        }

    def scan_xss(self, user_input: str) -> Dict:
        """Basic XSS detection"""
        xss_patterns = [
            r"<script.*?>.*?</script>",
            r"javascript:",
            r"onerror\s*=",
            r"onclick\s*=",
            r"<iframe"
        ]

        vulnerabilities = []

        for pattern in xss_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                vulnerabilities.append({
                    'type': 'XSS',
                    'pattern': pattern,
                    'severity': 'high'
                })

        return {
            'scan_type': 'xss',
            'vulnerable': len(vulnerabilities) > 0,
            'vulnerabilities': vulnerabilities
        }

if __name__ == '__main__':
    print("Comprehensive Security System initialized")
    print("\nAvailable managers:")
    print("  - APISecurityManager")
    print("  - PasswordSecurityManager")
    print("  - SecurityAuditManager")
    print("  - DataLossPreventionManager")
    print("  - IncidentResponseManager")
    print("  - VulnerabilityScanner")
