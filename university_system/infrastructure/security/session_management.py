#!/usr/bin/env python3
"""
Advanced Session Management System
Features:
- Concurrent session limiting
- Session activity logging (IP, device, location)
- Remote session termination
- Session timeout policies by role
- Suspicious login detection (impossible travel, unusual hours)
"""

import os
import sys
from university_system.infrastructure.database.db import sqlite3
import secrets
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests
from dataclasses import dataclass

# Import centralized database path and connection utilities
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from modules.shared.constants.paths import DEFAULT_DB_PATH
from university_system.infrastructure.database.db import get_connection
from university_system.core.i18n import get_text, _

# Import immutable audit logging for compliance
try:
    from university_system.infrastructure.security.audit_helpers import safe_log_security_event
    from university_system.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

# Import security alerting for real-time notifications
try:
    from university_system.infrastructure.security.security_alerts import (
        alert_suspicious_login,
    )
    SECURITY_ALERTS_AVAILABLE = True
except ImportError:
    SECURITY_ALERTS_AVAILABLE = False

@dataclass
class SessionInfo:
    """Session information container"""
    session_id: str
    user_id: int
    ip_address: str
    user_agent: str
    device_fingerprint: str
    location: Dict
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    is_active: bool

class SessionManager:
    """Advanced Session Management System"""

    def __init__(self, db_path: str = None):
        """Initialize session manager"""
        if db_path is None:
            db_path = str(DEFAULT_DB_PATH)

        self.db_path = db_path

        # Session timeout policies by role (in minutes)
        self.timeout_policies = {
            'admin': 30,      # 30 minutes
            'staff': 60,      # 1 hour
            'instructor': 120,  # 2 hours
            'student': 240,   # 4 hours
            'parent': 240     # 4 hours
        }

        # Concurrent session limits by role
        self.session_limits = {
            'admin': 2,
            'staff': 3,
            'instructor': 5,
            'student': 3,
            'parent': 2
        }

        # Suspicious activity thresholds
        self.impossible_travel_speed_kmh = 800  # ~500 mph
        self.unusual_hours = [(0, 5), (23, 24)]  # 12am-5am, 11pm-12am

    def _get_connection(self):
        """Get database connection using centralized pool"""
        return get_connection(db_path=self.db_path, row_factory=True)

    def _hash_session_id(self, session_id: str) -> str:
        """Hash session ID for storage"""
        return hashlib.sha256(session_id.encode()).hexdigest()

    def create_session(self, user_id: int, role: str, ip_address: str,
                      user_agent: str, device_fingerprint: str = None) -> Dict:
        """
        Create new session with security checks

        Returns:
            Dict with session_id and warnings
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Check concurrent session limit
            active_sessions = self._get_active_sessions(user_id, cursor)
            limit = self.session_limits.get(role, 3)

            warnings = []

            if len(active_sessions) >= limit:
                # Terminate oldest session
                oldest = min(active_sessions, key=lambda s: s['last_activity'])
                self._terminate_session(oldest['session_id'], cursor)
                warnings.append(f'Terminated oldest session due to limit ({limit} concurrent sessions)')

            # Get location from IP
            location = self._get_location_from_ip(ip_address)

            # Check for suspicious activity
            suspicious_flags = self._detect_suspicious_login(
                user_id, ip_address, location, cursor
            )

            if suspicious_flags:
                warnings.extend(suspicious_flags)

            # Generate session ID
            session_id = secrets.token_urlsafe(32)
            session_hash = self._hash_session_id(session_id)

            # Calculate expiration
            timeout_minutes = self.timeout_policies.get(role, 60)
            expires_at = datetime.now() + timedelta(minutes=timeout_minutes)

            # Create session record
            cursor.execute("""
                INSERT INTO sessions (
                    session_id_hash, user_id, ip_address, user_agent,
                    device_fingerprint, location, created_at, last_activity,
                    expires_at, is_active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                session_hash, user_id, ip_address, user_agent,
                device_fingerprint or '', json.dumps(location),
                datetime.now(), datetime.now(), expires_at
            ))

            session_db_id = cursor.lastrowid

            # Log session creation
            self._log_session_activity(
                session_db_id, user_id, 'session_created',
                {'ip': ip_address, 'location': location, 'warnings': warnings},
                cursor
            )

            # Log suspicious activity if detected
            if suspicious_flags:
                self._log_security_event(
                    user_id, 'suspicious_login', {
                        'flags': suspicious_flags,
                        'ip': ip_address,
                        'location': location
                    }, cursor
                )

                # Immutable audit log for suspicious activity
                if IMMUTABLE_AUDIT_AVAILABLE:
                    safe_log_security_event(
                        action=AuditAction.SUSPICIOUS_ACTIVITY,
                        user_id=str(user_id),
                        resource_type='session',
                        ip_address=ip_address,
                        details={
                            'flags': suspicious_flags,
                            'location': location
                        }
                    )

                # Send real-time security alert
                if SECURITY_ALERTS_AVAILABLE:
                    alert_suspicious_login(
                        user_id=str(user_id),
                        ip_address=ip_address,
                        reason='; '.join(suspicious_flags),
                        country=location.get('country', 'Unknown'),
                        additional_details={'flags': suspicious_flags}
                    )

            conn.commit()

            # Immutable audit log for session creation
            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.LOGIN_SUCCESS,
                    user_id=str(user_id),
                    resource_type='session',
                    resource_id=str(session_db_id),
                    ip_address=ip_address,
                    user_agent=user_agent,
                    details={
                        'location': location,
                        'role': role,
                        'warnings': warnings
                    }
                )

            return {
                'success': True,
                'session_id': session_id,
                'expires_at': expires_at.isoformat(),
                'warnings': warnings,
                'suspicious': len(suspicious_flags) > 0
            }

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def validate_session(self, session_id: str, user_id: int,
                        ip_address: str = None) -> Dict:
        """
        Validate session and update activity

        Returns:
            Dict with validation result and session info
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            session_hash = self._hash_session_id(session_id)

            # Get session
            cursor.execute("""
                SELECT id, user_id, ip_address, expires_at, is_active,
                       last_activity, device_fingerprint, location
                FROM sessions
                WHERE session_id_hash = ? AND user_id = ?
            """, (session_hash, user_id))

            row = cursor.fetchone()

            if not row:
                return {'valid': False, 'reason': 'Session not found'}

            (session_db_id, stored_user_id, stored_ip, expires_at,
             is_active, last_activity, device_fp, location) = row

            # Check if active
            if not is_active:
                return {'valid': False, 'reason': 'Session terminated'}

            # Check expiration
            expires_dt = datetime.fromisoformat(expires_at)
            if datetime.now() > expires_dt:
                # Expire session
                self._terminate_session(session_id, cursor)
                conn.commit()
                return {'valid': False, 'reason': 'Session expired'}

            # Check IP address consistency (optional)
            warnings = []
            if ip_address and ip_address != stored_ip:
                warnings.append('IP address changed')
                # Log IP change
                self._log_session_activity(
                    session_db_id, user_id, 'ip_changed',
                    {'old_ip': stored_ip, 'new_ip': ip_address},
                    cursor
                )

            # Update last activity
            cursor.execute("""
                UPDATE sessions
                SET last_activity = ?
                WHERE id = ?
            """, (datetime.now(), session_db_id))

            # Log activity
            self._log_session_activity(
                session_db_id, user_id, 'activity',
                {'ip': ip_address or stored_ip},
                cursor
            )

            conn.commit()

            return {
                'valid': True,
                'session_id': session_id,
                'user_id': stored_user_id,
                'expires_at': expires_at,
                'warnings': warnings,
                'location': json.loads(location) if location else {}
            }

        except Exception as e:
            return {'valid': False, 'reason': f'Error: {e}'}
        finally:
            conn.close()

    def terminate_session(self, session_id: str, user_id: int,
                         reason: str = 'user_logout') -> Dict:
        """
        Terminate a session

        Args:
            session_id: Session ID to terminate
            user_id: User ID (for verification)
            reason: Reason for termination
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            session_hash = self._hash_session_id(session_id)

            # Verify session belongs to user
            cursor.execute("""
                SELECT id FROM sessions
                WHERE session_id_hash = ? AND user_id = ? AND is_active = 1
            """, (session_hash, user_id))

            row = cursor.fetchone()

            if not row:
                return {'success': False, 'error': 'Session not found or already terminated'}

            session_db_id = row[0]

            # Terminate session
            cursor.execute("""
                UPDATE sessions
                SET is_active = 0, terminated_at = ?, termination_reason = ?
                WHERE id = ?
            """, (datetime.now(), reason, session_db_id))

            # Log termination
            self._log_session_activity(
                session_db_id, user_id, 'session_terminated',
                {'reason': reason},
                cursor
            )

            conn.commit()

            # Immutable audit log for session termination
            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.LOGOUT,
                    user_id=str(user_id),
                    resource_type='session',
                    resource_id=str(session_db_id),
                    details={'reason': reason}
                )

            return {'success': True, 'message': 'Session terminated'}

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def terminate_all_sessions(self, user_id: int, except_session: str = None,
                              reason: str = 'user_logout_all') -> Dict:
        """
        Terminate all user sessions except optionally one

        Args:
            user_id: User ID
            except_session: Session ID to keep active (optional)
            reason: Reason for termination
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            if except_session:
                except_hash = self._hash_session_id(except_session)
                cursor.execute("""
                    UPDATE sessions
                    SET is_active = 0, terminated_at = ?, termination_reason = ?
                    WHERE user_id = ? AND is_active = 1 AND session_id_hash != ?
                """, (datetime.now(), reason, user_id, except_hash))
            else:
                cursor.execute("""
                    UPDATE sessions
                    SET is_active = 0, terminated_at = ?, termination_reason = ?
                    WHERE user_id = ? AND is_active = 1
                """, (datetime.now(), reason, user_id))

            count = cursor.rowcount

            # Log bulk termination
            self._log_security_event(
                user_id, 'bulk_session_termination',
                {'count': count, 'reason': reason},
                cursor
            )

            conn.commit()

            # Immutable audit log for bulk session termination
            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.LOGOUT,
                    user_id=str(user_id),
                    resource_type='session',
                    details={
                        'reason': reason,
                        'terminated_count': count,
                        'bulk_termination': True
                    }
                )

            return {'success': True, 'terminated_count': count}

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def get_user_sessions(self, user_id: int, include_inactive: bool = False) -> List[Dict]:
        """
        Get all sessions for a user

        Returns:
            List of session dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            query = """
                SELECT session_id_hash, ip_address, user_agent, device_fingerprint,
                       location, created_at, last_activity, expires_at, is_active,
                       terminated_at, termination_reason
                FROM sessions
                WHERE user_id = ?
            """

            if not include_inactive:
                query += " AND is_active = 1"

            query += " ORDER BY last_activity DESC"

            cursor.execute(query, (user_id,))

            sessions = []
            for row in cursor.fetchall():
                sessions.append({
                    'session_id_hash': row[0][:16] + '...',  # Truncate for display
                    'ip_address': row[1],
                    'user_agent': row[2],
                    'device_fingerprint': row[3],
                    'location': json.loads(row[4]) if row[4] else {},
                    'created_at': row[5],
                    'last_activity': row[6],
                    'expires_at': row[7],
                    'is_active': bool(row[8]),
                    'terminated_at': row[9],
                    'termination_reason': row[10]
                })

            return sessions

        finally:
            conn.close()

    def get_all_active_sessions(self) -> List[Dict]:
        """
        Get all active sessions across all users

        Returns:
            List of session dictionaries with username information
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Join with users table to get username
            cursor.execute("""
                SELECT s.session_id_hash, s.user_id, s.ip_address, s.user_agent,
                       s.device_fingerprint, s.location, s.created_at, s.last_activity,
                       s.expires_at, COALESCE(u.username, 'Unknown') as username
                FROM sessions s
                LEFT JOIN users u ON s.user_id = u.id
                WHERE s.is_active = 1 AND s.expires_at > datetime('now')
                ORDER BY s.last_activity DESC
            """)

            sessions = []
            for row in cursor.fetchall():
                location_data = row[5]
                if location_data:
                    try:
                        location = json.loads(location_data)
                        location_str = f"{location.get('city', 'Unknown')}, {location.get('country', 'Unknown')}"
                    except (json.JSONDecodeError, TypeError):
                        location_str = str(location_data)
                else:
                    location_str = 'Unknown'

                sessions.append({
                    'session_id_hash': row[0][:16] + '...' if row[0] else 'N/A',
                    'user_id': row[1],
                    'ip_address': row[2] or 'N/A',
                    'user_agent': row[3] or 'N/A',
                    'device_fingerprint': row[4] or '',
                    'location': location_str,
                    'created_at': row[6] or '',
                    'last_activity': row[7] or '',
                    'expires_at': row[8] or '',
                    'username': row[9] or 'Unknown'
                })

            return sessions

        finally:
            conn.close()

    def _get_active_sessions(self, user_id: int, cursor) -> List[Dict]:
        """Get active sessions for a user"""
        cursor.execute("""
            SELECT session_id_hash, last_activity, ip_address, location
            FROM sessions
            WHERE user_id = ? AND is_active = 1 AND expires_at > ?
        """, (user_id, datetime.now()))

        return [
            {
                'session_id': row[0],
                'last_activity': row[1],
                'ip_address': row[2],
                'location': json.loads(row[3]) if row[3] else {}
            }
            for row in cursor.fetchall()
        ]

    def _terminate_session(self, session_id_hash: str, cursor):
        """Internal method to terminate session"""
        cursor.execute("""
            UPDATE sessions
            SET is_active = 0, terminated_at = ?, termination_reason = ?
            WHERE session_id_hash = ?
        """, (datetime.now(), 'session_limit_exceeded', session_id_hash))

    def _get_location_from_ip(self, ip_address: str) -> Dict:
        """
        Get approximate location from IP address using free API

        Returns:
            Dict with city, country, lat, lon
        """
        # Skip for localhost/private IPs
        if ip_address in ['127.0.0.1', 'localhost'] or ip_address.startswith('192.168.'):
            return {
                'city': 'Local',
                'country': 'Local',
                'latitude': 0,
                'longitude': 0
            }

        try:
            # Use free IP geolocation API
            response = requests.get(
                f'http://ip-api.com/json/{ip_address}',
                timeout=2
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return {
                        'city': data.get('city', 'Unknown'),
                        'country': data.get('country', 'Unknown'),
                        'latitude': data.get('lat', 0),
                        'longitude': data.get('lon', 0),
                        'region': data.get('regionName', ''),
                        'isp': data.get('isp', '')
                    }
        except Exception as e:
            print(f"Geolocation failed: {e}")

        return {
            'city': 'Unknown',
            'country': 'Unknown',
            'latitude': 0,
            'longitude': 0
        }

    def _detect_suspicious_login(self, user_id: int, ip_address: str,
                                 location: Dict, cursor) -> List[str]:
        """
        Detect suspicious login patterns

        Returns:
            List of suspicious activity flags
        """
        flags = []

        # Get last login
        cursor.execute("""
            SELECT ip_address, location, created_at
            FROM sessions
            WHERE user_id = ? AND is_active = 1
            ORDER BY created_at DESC
            LIMIT 1
        """, (user_id,))

        last_login = cursor.fetchone()

        if last_login:
            last_ip, last_location_json, last_time = last_login
            last_location = json.loads(last_location_json) if last_location_json else {}

            # Check impossible travel
            if self._is_impossible_travel(last_location, location, last_time):
                flags.append('impossible_travel')

            # Check IP change from different country
            if (last_ip != ip_address and
                last_location.get('country') != location.get('country') and
                location.get('country') not in ['Unknown', 'Local']):
                flags.append('country_change')

        # Check unusual hours
        current_hour = datetime.now().hour
        for start, end in self.unusual_hours:
            if start <= current_hour < end:
                flags.append('unusual_hours')
                break

        # Check multiple failed logins recently
        cursor.execute("""
            SELECT COUNT(*) FROM security_events
            WHERE user_id = ? AND event_type = 'failed_login'
              AND event_time > datetime('now', '-1 hour')
        """, (user_id,))

        failed_count = cursor.fetchone()[0]
        if failed_count >= 3:
            flags.append('multiple_failed_attempts')

        return flags

    def _is_impossible_travel(self, loc1: Dict, loc2: Dict, last_time: str) -> bool:
        """
        Check if travel between two locations is impossible

        Uses haversine formula to calculate distance
        """
        if not all([loc1.get('latitude'), loc1.get('longitude'),
                   loc2.get('latitude'), loc2.get('longitude')]):
            return False

        # Calculate distance
        from math import radians, sin, cos, sqrt, atan2

        lat1 = radians(loc1['latitude'])
        lon1 = radians(loc1['longitude'])
        lat2 = radians(loc2['latitude'])
        lon2 = radians(loc2['longitude'])

        dlon = lon2 - lon1
        dlat = lat2 - lat1

        a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        distance_km = 6371 * c  # Earth radius in km

        # Calculate time difference
        last_dt = datetime.fromisoformat(last_time)
        time_diff_hours = (datetime.now() - last_dt).total_seconds() / 3600

        if time_diff_hours == 0:
            return False

        # Calculate required speed
        required_speed = distance_km / time_diff_hours

        # Check if speed exceeds threshold
        return required_speed > self.impossible_travel_speed_kmh

    def _log_session_activity(self, session_id: int, user_id: int,
                              activity_type: str, details: Dict, cursor):
        """Log session activity"""
        cursor.execute("""
            INSERT INTO session_activity_log (
                session_id, user_id, activity_type, details, activity_time
            )
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, user_id, activity_type, json.dumps(details), datetime.now()))

    def _log_security_event(self, user_id: int, event_type: str,
                           details: Dict, cursor):
        """Log security event"""
        cursor.execute("""
            INSERT INTO security_events (
                user_id, event_type, details, event_time, severity
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id, event_type, json.dumps(details), datetime.now(),
            'high' if 'suspicious' in event_type else 'medium'
        ))

    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions

        Returns:
            Number of sessions cleaned up
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE sessions
                SET is_active = 0, terminated_at = ?, termination_reason = 'expired'
                WHERE is_active = 1 AND expires_at < ?
            """, (datetime.now(), datetime.now()))

            count = cursor.rowcount
            conn.commit()

            return count

        finally:
            conn.close()

    def get_session_statistics(self, user_id: int = None) -> Dict:
        """
        Get session statistics

        Args:
            user_id: Optional user ID to filter stats
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            stats = {}

            # Active sessions
            query = "SELECT COUNT(*) FROM sessions WHERE is_active = 1"
            params = []

            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)

            cursor.execute(query, params)
            stats['active_sessions'] = cursor.fetchone()[0]

            # Total sessions today
            query = """
                SELECT COUNT(*) FROM sessions
                WHERE created_at > datetime('now', '-1 day')
            """
            if user_id:
                query += " AND user_id = ?"

            cursor.execute(query, params)
            stats['sessions_today'] = cursor.fetchone()[0]

            # Suspicious logins today
            query = """
                SELECT COUNT(*) FROM security_events
                WHERE event_type = 'suspicious_login'
                  AND event_time > datetime('now', '-1 day')
            """
            if user_id:
                query += " AND user_id = ?"

            cursor.execute(query, params)
            stats['suspicious_today'] = cursor.fetchone()[0]

            return stats

        finally:
            conn.close()

# Convenience functions
def create_session(user_id: int, role: str, ip_address: str, user_agent: str) -> Dict:
    """Quick create session"""
    manager = SessionManager()
    return manager.create_session(user_id, role, ip_address, user_agent)

def validate_session(session_id: str, user_id: int, ip_address: str = None) -> Dict:
    """Quick validate session"""
    manager = SessionManager()
    return manager.validate_session(session_id, user_id, ip_address)

if __name__ == '__main__':
    print("Session Management System initialized")
    manager = SessionManager()
    print(f"Database: {manager.db_path}")
    print(f"Timeout policies: {manager.timeout_policies}")
    print(f"Session limits: {manager.session_limits}")
