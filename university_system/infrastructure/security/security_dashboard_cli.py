#!/usr/bin/env python3
"""
Comprehensive Security & Compliance Dashboard - CLI Interface
Provides command-line access to all security features
"""

import os
import sys
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

try:
    from tabulate import tabulate
    TABULATE_AVAILABLE = True
except ImportError:
    TABULATE_AVAILABLE = False
    # Fallback simple table function
    def tabulate(data, headers=None, tablefmt='grid'):
        """Simple fallback for tabulate"""
        if not data:
            return "No data"

        if headers:
            # Calculate column widths
            col_widths = [len(str(h)) for h in headers]
            for row in data:
                for i, cell in enumerate(row):
                    col_widths[i] = max(col_widths[i], len(str(cell)))

            # Build table
            result = []
            result.append("-" * (sum(col_widths) + len(headers) * 3 + 1))
            header_line = "| " + " | ".join(str(h).ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"
            result.append(header_line)
            result.append("-" * (sum(col_widths) + len(headers) * 3 + 1))

            for row in data:
                row_line = "| " + " | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)) + " |"
                result.append(row_line)

            result.append("-" * (sum(col_widths) + len(headers) * 3 + 1))
            return "\n".join(result)
        else:
            return "\n".join(str(row) for row in data)

# Import centralized database path and connection utilities
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from modules.shared.constants.paths import DEFAULT_DB_PATH
from university_system.infrastructure.database.db import get_connection

# Import full security modules for complete access
from university_system.infrastructure.security import session_management as session_mgmt
from university_system.infrastructure.security import data_encryption as encryption
from university_system.infrastructure.security import comprehensive_security as comp_security
from university_system.infrastructure.security import init_security_tables as security_tables

# Import individual classes for backwards compatibility
from university_system.infrastructure.security.session_management import SessionManager
from university_system.infrastructure.security.data_encryption import EncryptionManager
from university_system.infrastructure.security.comprehensive_security import (
    APISecurityManager,
    PasswordSecurityManager,
    SecurityAuditManager,
    DataLossPreventionManager,
    IncidentResponseManager,
    VulnerabilityScanner
)
from university_system.infrastructure.security.init_security_tables import init_security_tables
from university_system.modules.shared.utils.i18n import get_text, _

# Import full authentication module
try:
    import university_system.infrastructure.auth as auth_module
    from university_system.infrastructure.auth import mfa_service as mfa_module
    from university_system.infrastructure.auth import mfa_integration as mfa_integration_module
    AUTH_MODULE_AVAILABLE = True
    AUTH_CLI_AVAILABLE = True
except ImportError as e:
    auth_module = None
    mfa_module = None
    mfa_integration_module = None
    AUTH_MODULE_AVAILABLE = False
    AUTH_CLI_AVAILABLE = False
    print(f"Warning: Authentication modules not available: {e}")


class SecurityDashboardCLI:
    """CLI Security Dashboard"""

    def __init__(self, admin_user_id: int):
        self.admin_user_id = admin_user_id

        # Initialize security database tables first
        init_security_tables()

        # Initialize managers
        self.session_mgr = SessionManager()
        self.encryption_mgr = EncryptionManager()
        self.api_mgr = APISecurityManager()
        self.password_mgr = PasswordSecurityManager()
        self.audit_mgr = SecurityAuditManager()
        self.dlp_mgr = DataLossPreventionManager()
        self.incident_mgr = IncidentResponseManager()
        self.vuln_scanner = VulnerabilityScanner()

        self.db_path = str(DEFAULT_DB_PATH)

    def _get_connection(self):
        return get_connection(db_path=self.db_path, row_factory=True)

    def display_overview(self):
        """Display security overview"""
        print("\n" + "="*80)
        print("🛡️  SECURITY & COMPLIANCE DASHBOARD - OVERVIEW")
        print("="*80)

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Gather statistics
            stats = {}

            # Active sessions
            cursor.execute("SELECT COUNT(*) FROM sessions WHERE is_active = 1")
            stats['Active Sessions'] = cursor.fetchone()[0]

            # Failed logins (24h)
            cursor.execute("""
                SELECT COUNT(*) FROM security_events
                WHERE event_type = 'failed_login'
                  AND event_time > datetime('now', '-1 day')
            """)
            stats['Failed Logins (24h)'] = cursor.fetchone()[0]

            # Security events (24h)
            cursor.execute("""
                SELECT COUNT(*) FROM security_events
                WHERE event_time > datetime('now', '-1 day')
            """)
            stats['Security Events (24h)'] = cursor.fetchone()[0]

            # Encrypted fields
            cursor.execute("SELECT COUNT(*) FROM encrypted_fields_metadata")
            stats['Encrypted Fields'] = cursor.fetchone()[0]

            # Active API keys
            cursor.execute("SELECT COUNT(*) FROM api_keys WHERE is_active = 1")
            stats['Active API Keys'] = cursor.fetchone()[0]

            # Open incidents
            cursor.execute("SELECT COUNT(*) FROM security_incidents WHERE status = 'open'")
            stats['Open Incidents'] = cursor.fetchone()[0]

            # Pending exports
            cursor.execute("SELECT COUNT(*) FROM bulk_export_log WHERE status = 'pending'")
            stats['Pending Exports'] = cursor.fetchone()[0]

            # High vulnerabilities
            cursor.execute("""
                SELECT COUNT(*) FROM vulnerability_scan_results
                WHERE severity = 'high' AND fixed = 0
            """)
            stats['High Vulnerabilities'] = cursor.fetchone()[0]

            # Display statistics
            print("\n📊 Security Statistics:")
            print("-" * 80)
            table_data = [[key, value] for key, value in stats.items()]
            print(tabulate(table_data, headers=['Metric', 'Count'], tablefmt='grid'))

            # Recent alerts
            cursor.execute("""
                SELECT event_type, severity, details, event_time
                FROM security_events
                WHERE severity IN ('high', 'critical')
                ORDER BY event_time DESC
                LIMIT 10
            """)

            alerts = cursor.fetchall()
            if alerts:
                print("\n🚨 Recent Security Alerts:")
                print("-" * 80)
                alert_data = []
                for event_type, severity, details, event_time in alerts:
                    alert_data.append([
                        event_time[:19],
                        severity.upper(),
                        event_type,
                        details[:50] + '...' if len(details) > 50 else details
                    ])
                print(tabulate(alert_data, headers=['Time', 'Severity', 'Type', 'Details'], tablefmt='grid'))
            else:
                print("\n✅ No recent high-severity alerts")

        finally:
            conn.close()

    def display_sessions(self):
        """Display active sessions"""
        print("\n" + "="*80)
        print("🔐 ACTIVE SESSIONS")
        print("="*80)

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT s.id, u.username, s.ip_address, s.location, s.created_at, s.last_activity
                FROM sessions s
                LEFT JOIN users u ON s.user_id = u.id
                WHERE s.is_active = 1
                ORDER BY s.last_activity DESC
            """)

            sessions = cursor.fetchall()
            if sessions:
                session_data = []
                for sid, username, ip, location, created, last_activity in sessions:
                    session_data.append([
                        sid,
                        username or 'N/A',
                        ip or 'N/A',
                        location or 'N/A',
                        created[:19] if created else 'N/A',
                        last_activity[:19] if last_activity else 'N/A'
                    ])
                print(tabulate(session_data,
                             headers=['ID', 'User', 'IP Address', 'Location', 'Created', 'Last Activity'],
                             tablefmt='grid'))
            else:
                print("\n✅ No active sessions")

        finally:
            conn.close()

    def display_encryption_status(self):
        """Display encryption keys and fields"""
        print("\n" + "="*80)
        print("🔒 ENCRYPTION STATUS")
        print("="*80)

        # Display keys
        print("\n📋 Encryption Keys:")
        print("-" * 80)
        keys = self.encryption_mgr.get_key_rotation_status()

        if keys:
            key_data = []
            for key in keys:
                key_data.append([
                    key['key_id'],
                    key['type'],
                    key['created_at'][:10],
                    f"{key['age_days']} days",
                    'Active' if key['is_active'] else 'Rotated',
                    '⚠️ Yes' if key['needs_rotation'] else 'No'
                ])
            print(tabulate(key_data,
                         headers=['Key ID', 'Type', 'Created', 'Age', 'Status', 'Needs Rotation'],
                         tablefmt='grid'))
        else:
            print("No encryption keys found")

        # Display encrypted fields
        print("\n📋 Encrypted Database Fields:")
        print("-" * 80)
        fields = self.encryption_mgr.list_encrypted_fields()

        if fields:
            field_data = []
            for field in fields:
                field_data.append([
                    field['table'],
                    field['column'],
                    field['key_id'],
                    field['encrypted_at'][:19] if field['encrypted_at'] else 'N/A'
                ])
            print(tabulate(field_data,
                         headers=['Table', 'Column', 'Key ID', 'Encrypted At'],
                         tablefmt='grid'))
        else:
            print("No encrypted fields found")

    def display_api_security(self):
        """Display API keys and rate limits"""
        print("\n" + "="*80)
        print("🔑 API SECURITY")
        print("="*80)

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT ak.id, ak.key_name, u.username, ak.created_at, ak.last_used_at,
                       ak.rate_limit, ak.is_active
                FROM api_keys ak
                LEFT JOIN users u ON ak.user_id = u.id
                ORDER BY ak.created_at DESC
            """)

            keys = cursor.fetchall()
            if keys:
                key_data = []
                for kid, name, username, created, last_used, rate_limit, is_active in keys:
                    key_data.append([
                        kid,
                        name,
                        username or 'N/A',
                        created[:10] if created else 'N/A',
                        last_used[:19] if last_used else 'Never',
                        rate_limit,
                        '✅ Active' if is_active else '❌ Inactive'
                    ])
                print(tabulate(key_data,
                             headers=['ID', 'Name', 'User', 'Created', 'Last Used', 'Rate Limit', 'Status'],
                             tablefmt='grid'))
            else:
                print("\n✅ No API keys found")

        finally:
            conn.close()

    def display_audit_log(self):
        """Display security audit log"""
        print("\n" + "="*80)
        print("📜 SECURITY AUDIT LOG")
        print("="*80)

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT se.event_time, u.username, se.event_type, se.severity, se.details
                FROM security_events se
                LEFT JOIN users u ON se.user_id = u.id
                ORDER BY se.event_time DESC
                LIMIT 50
            """)

            events = cursor.fetchall()
            if events:
                event_data = []
                for event_time, username, event_type, severity, details in events:
                    event_data.append([
                        event_time[:19],
                        username or 'System',
                        event_type,
                        severity.upper(),
                        details[:40] + '...' if len(details) > 40 else details
                    ])
                print(tabulate(event_data,
                             headers=['Time', 'User', 'Event Type', 'Severity', 'Details'],
                             tablefmt='grid'))
            else:
                print("\n✅ No security events recorded")

        finally:
            conn.close()

    def display_incidents(self):
        """Display security incidents"""
        print("\n" + "="*80)
        print("🚨 SECURITY INCIDENTS")
        print("="*80)

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT id, incident_type, severity, status, detected_at, description
                FROM security_incidents
                ORDER BY detected_at DESC
                LIMIT 20
            """)

            incidents = cursor.fetchall()
            if incidents:
                incident_data = []
                for iid, itype, severity, status, detected, description in incidents:
                    incident_data.append([
                        iid,
                        itype,
                        severity.upper(),
                        status,
                        detected[:19] if detected else 'N/A',
                        description[:40] + '...' if len(description) > 40 else description
                    ])
                print(tabulate(incident_data,
                             headers=['ID', 'Type', 'Severity', 'Status', 'Detected', 'Description'],
                             tablefmt='grid'))
            else:
                print("\n✅ No security incidents recorded")

        finally:
            conn.close()

    def display_dlp_exports(self):
        """Display data loss prevention export requests"""
        print("\n" + "="*80)
        print("📊 DATA LOSS PREVENTION - EXPORT REQUESTS")
        print("="*80)

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT bel.id, u.username, bel.resource_type, bel.record_count,
                       bel.status, bel.exported_at
                FROM bulk_export_log bel
                LEFT JOIN users u ON bel.user_id = u.id
                ORDER BY bel.exported_at DESC
                LIMIT 30
            """)

            exports = cursor.fetchall()
            if exports:
                export_data = []
                for eid, username, resource_type, count, status, exported in exports:
                    export_data.append([
                        eid,
                        username or 'N/A',
                        resource_type,
                        count,
                        status,
                        exported[:19] if exported else 'N/A'
                    ])
                print(tabulate(export_data,
                             headers=['ID', 'User', 'Resource Type', 'Records', 'Status', 'Requested'],
                             tablefmt='grid'))
            else:
                print("\n✅ No export requests found")

        finally:
            conn.close()

    def display_vulnerabilities(self):
        """Display vulnerability scan results"""
        print("\n" + "="*80)
        print("🔍 VULNERABILITY SCAN RESULTS")
        print("="*80)

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT scan_type, target, severity, vulnerable, details, scanned_at
                FROM vulnerability_scan_results
                ORDER BY scanned_at DESC
                LIMIT 30
            """)

            vulns = cursor.fetchall()
            if vulns:
                vuln_data = []
                for scan_type, target, severity, vulnerable, details, scanned in vulns:
                    vuln_data.append([
                        scan_type,
                        target[:30] + '...' if len(target) > 30 else target,
                        severity.upper(),
                        '🔴 Yes' if vulnerable else '✅ No',
                        scanned[:19] if scanned else 'N/A'
                    ])
                print(tabulate(vuln_data,
                             headers=['Scan Type', 'Target', 'Severity', 'Vulnerable', 'Scanned'],
                             tablefmt='grid'))
            else:
                print("\n✅ No vulnerability scans found")

        finally:
            conn.close()

    def generate_compliance_report(self, report_type: str = 'ferpa'):
        """Generate and display compliance report"""
        print("\n" + "="*80)
        print(f"📋 {report_type.upper()} COMPLIANCE REPORT")
        print("="*80)

        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()

        report = self.audit_mgr.generate_compliance_report(start_date, end_date, report_type)

        print(f"\nReport Period: {report['period']['start'][:10]} to {report['period']['end'][:10]}")
        print("-" * 80)

        # Data access summary
        if report.get('data_access'):
            print("\n📊 Data Access Summary:")
            access_data = [[item['resource'], item['action'], item['count']]
                          for item in report['data_access'][:10]]
            print(tabulate(access_data, headers=['Resource', 'Action', 'Count'], tablefmt='grid'))

        # Security events summary
        if report.get('security_events'):
            print("\n🚨 Security Events Summary:")
            event_data = [[item['type'], item['severity'], item['count']]
                         for item in report['security_events'][:10]]
            print(tabulate(event_data, headers=['Type', 'Severity', 'Count'], tablefmt='grid'))

        # Summary statistics
        print("\n📈 Summary Statistics:")
        print(f"   Permission Changes: {report.get('permission_changes', 0)}")
        print(f"   Failed Logins: {report.get('failed_logins', 0)}")

        if report.get('bulk_exports'):
            print("\n📤 Top Bulk Exports:")
            export_data = [[item['user_id'], item['type'], item['records']]
                          for item in report['bulk_exports'][:10]]
            print(tabulate(export_data, headers=['User ID', 'Type', 'Records'], tablefmt='grid'))


def display_security_dashboard_menu(admin_user_id: int = 1):
    """Main security dashboard menu"""
    dashboard = SecurityDashboardCLI(admin_user_id)

    while True:
        print("\n" + "="*100)
        print("🛡️  SECURITY & COMPLIANCE DASHBOARD")
        print("="*100)

        print("\n📊 MONITORING & REPORTS:")
        print(f"{'1.  Security Overview':<25} {'2.  Active Sessions':<25} {'3.  Encryption Status':<25} {'4.  API Security & Keys':<25}")
        print(f"{'5.  Audit Log (Adv)':<25} {'6.  Security Incidents':<25} {'7.  DLP (Exports)':<25} {'8.  Vulnerability Scans':<25}")

        print("\n🔧 MANAGEMENT TOOLS:")
        print(f"{'11. Session Management':<25} {'12. API Key Mgmt':<25} {'13. Incident Mgmt':<25} {'14. Encryption Keys':<25}")
        print(f"{'15. Password Security':<25} {'16. Export Approval':<25} {'17. User Management':<25} {'18. Role & Permissions':<25}")
        print(f"{'19. My Account Settings':<25}")

        print("\n📋 COMPLIANCE & REPORTING:")
        print(f"{'21. FERPA Report':<25} {'22. GDPR Report':<25} {'23. Security Events':<25} {'24. Access Audit':<25}")

        print("\n🔍 SECURITY SCANNING:")
        print(f"{'31. Vulnerability Scan':<25} {'32. Password Checker':<25} {'33. Compromised Check':<25}")

        print("\n🔬 DEVELOPER TOOLS:")
        print(f"{'41. Module Explorer':<25} {'42. Quick Module Info':<25}")

        print("\n0.  Back to Main Menu")
        print("="*100)

        choice = input("\nEnter your choice: ").strip()

        if choice == '0':
            break
        # Monitoring & Reports
        elif choice == '1':
            dashboard.display_overview()
        elif choice == '2':
            dashboard.display_sessions()
        elif choice == '3':
            dashboard.display_encryption_status()
        elif choice == '4':
            dashboard.display_api_security()
        elif choice == '5':
            audit_log_menu(dashboard)
        elif choice == '6':
            dashboard.display_incidents()
        elif choice == '7':
            dashboard.display_dlp_exports()
        elif choice == '8':
            dashboard.display_vulnerabilities()
        # Management Tools
        elif choice == '11':
            session_management_menu(dashboard)
        elif choice == '12':
            api_key_management_menu(dashboard)
        elif choice == '13':
            incident_management_menu(dashboard)
        elif choice == '14':
            encryption_management_menu(dashboard)
        elif choice == '15':
            password_security_menu(dashboard)
        elif choice == '16':
            data_export_approval_menu(dashboard)
        elif choice == '17':
            user_management_cli_menu(dashboard)
        elif choice == '18':
            role_management_cli_menu(dashboard)
        elif choice == '19':
            my_account_cli_menu(dashboard)
        # Compliance & Reporting
        elif choice == '21':
            dashboard.generate_compliance_report('ferpa')
        elif choice == '22':
            dashboard.generate_compliance_report('gdpr')
        elif choice == '23':
            security_events_report_menu(dashboard)
        elif choice == '24':
            access_audit_report_menu(dashboard)
        # Security Scanning
        elif choice == '31':
            vulnerability_scan_menu(dashboard)
        elif choice == '32':
            password_strength_checker_menu(dashboard)
        elif choice == '33':
            compromised_password_check_menu(dashboard)
        # Developer Tools
        elif choice == '41':
            display_module_functions_menu()
        elif choice == '42':
            display_available_modules_info()
        else:
            print("\n❌ Invalid choice. Please try again.")

        input("\nPress Enter to continue...")


def session_management_menu(dashboard):
    """Session management submenu"""
    print("\n" + "="*80)
    print("🔐 SESSION MANAGEMENT")
    print("="*80)

    # First display active sessions
    dashboard.display_sessions()

    print("\n1. Terminate Session by ID")
    print("2. Terminate All Sessions for User")
    print("0. Back")

    choice = input("\nEnter your choice: ").strip()

    if choice == '1':
        session_id = input("Enter session ID to terminate: ").strip()
        try:
            dashboard.session_mgr.terminate_session(int(session_id))
            print(f"\n✅ Session {session_id} terminated successfully")
        except Exception as e:
            print(f"\n❌ Error terminating session: {e}")
    elif choice == '2':
        user_id = input("Enter user ID: ").strip()
        try:
            dashboard.session_mgr.terminate_user_sessions(int(user_id))
            print(f"\n✅ All sessions for user {user_id} terminated")
        except Exception as e:
            print(f"\n❌ Error terminating sessions: {e}")


def api_key_management_menu(dashboard):
    """API key management submenu"""
    print("\n" + "="*80)
    print("🔑 API KEY MANAGEMENT")
    print("="*80)

    print("\n1. Create API Key")
    print("2. Revoke API Key")
    print("3. List All API Keys")
    print("0. Back")

    choice = input("\nEnter your choice: ").strip()

    if choice == '1':
        user_id = input("Enter user ID: ").strip()
        key_name = input("Enter key name: ").strip()
        permissions_str = input("Enter permissions (comma-separated): ").strip()
        permissions = [p.strip() for p in permissions_str.split(',')]
        rate_limit = input("Enter rate limit (default 1000): ").strip() or "1000"

        try:
            result = dashboard.api_mgr.create_api_key(
                int(user_id), key_name, permissions, int(rate_limit)
            )
            if result.get('success'):
                print(f"\n✅ API Key created successfully!")
                print(f"   Key: {result['api_key']}")
                print(f"   Expires: {result['expires_at']}")
                print("\n⚠️  Save this key now - it won't be shown again!")
            else:
                print(f"\n❌ Error: {result.get('error')}")
        except Exception as e:
            print(f"\n❌ Error creating API key: {e}")

    elif choice == '2':
        dashboard.display_api_security()
        key_id = input("\nEnter API key ID to revoke: ").strip()
        try:
            conn = dashboard._get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE api_keys SET is_active = 0 WHERE id = ?", (int(key_id),))
            conn.commit()
            conn.close()
            print(f"\n✅ API key {key_id} revoked successfully")
        except Exception as e:
            print(f"\n❌ Error revoking key: {e}")

    elif choice == '3':
        dashboard.display_api_security()


def incident_management_menu(dashboard):
    """Incident management submenu"""
    print("\n" + "="*80)
    print("🚨 INCIDENT MANAGEMENT")
    print("="*80)

    print("\n1. Create Incident")
    print("2. Resolve Incident")
    print("3. View Incident Details")
    print("0. Back")

    choice = input("\nEnter your choice: ").strip()

    if choice == '1':
        incident_type = input("Enter incident type: ").strip()
        severity = input("Enter severity (low/medium/high/critical): ").strip()
        description = input("Enter description: ").strip()

        try:
            result = dashboard.incident_mgr.create_incident(
                incident_type, severity, description, dashboard.admin_user_id
            )
            if result.get('success'):
                print(f"\n✅ Incident created with ID: {result['incident_id']}")
            else:
                print(f"\n❌ Error: {result.get('error')}")
        except Exception as e:
            print(f"\n❌ Error creating incident: {e}")

    elif choice == '2':
        dashboard.display_incidents()
        incident_id = input("\nEnter incident ID to resolve: ").strip()
        resolution = input("Enter resolution notes: ").strip()

        try:
            conn = dashboard._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE security_incidents
                SET status = 'resolved', resolved_at = ?, resolution = ?
                WHERE id = ?
            """, (datetime.now(), resolution, int(incident_id)))
            conn.commit()
            conn.close()
            print(f"\n✅ Incident {incident_id} resolved successfully")
        except Exception as e:
            print(f"\n❌ Error resolving incident: {e}")


def vulnerability_scan_menu(dashboard):
    """Vulnerability scanning submenu"""
    print("\n" + "="*80)
    print("🔍 VULNERABILITY SCANNER")
    print("="*80)

    print("\n1. Scan for SQL Injection")
    print("2. Scan for XSS")
    print("3. View Scan Results")
    print("0. Back")

    choice = input("\nEnter your choice: ").strip()

    if choice == '1':
        query = input("Enter SQL query to test: ").strip()
        result = dashboard.vuln_scanner.scan_sql_injection(query)

        if result['vulnerable']:
            print("\n🔴 VULNERABLE!")
            print(f"   Found {len(result['vulnerabilities'])} potential SQL injection issues")
            for vuln in result['vulnerabilities']:
                print(f"   - Pattern: {vuln['pattern']}")
        else:
            print("\n✅ No SQL injection vulnerabilities detected")

    elif choice == '2':
        user_input = input("Enter user input to test: ").strip()
        result = dashboard.vuln_scanner.scan_xss(user_input)

        if result['vulnerable']:
            print("\n🔴 VULNERABLE!")
            print(f"   Found {len(result['vulnerabilities'])} potential XSS issues")
            for vuln in result['vulnerabilities']:
                print(f"   - Pattern: {vuln['pattern']}")
        else:
            print("\n✅ No XSS vulnerabilities detected")

    elif choice == '3':
        dashboard.display_vulnerabilities()


def audit_log_menu(dashboard):
    """Advanced audit log menu with filtering"""
    print("\n" + "="*80)
    print("📜 ADVANCED AUDIT LOG")
    print("="*80)

    print("\n1. View All Security Events")
    print("2. Filter by Severity (high/critical)")
    print("3. Filter by Event Type")
    print("4. Filter by Date Range")
    print("5. Filter by User")
    print("0. Back")

    choice = input("\nEnter your choice: ").strip()

    if choice == '1':
        dashboard.display_audit_log()
    elif choice == '2':
        severity = input("Enter severity (high/critical): ").strip()
        conn = dashboard._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT se.event_time, u.username, se.event_type, se.severity, se.details
            FROM security_events se
            LEFT JOIN users u ON se.user_id = u.id
            WHERE se.severity = ?
            ORDER BY se.event_time DESC
            LIMIT 50
        """, (severity,))
        events = cursor.fetchall()
        conn.close()

        if events:
            event_data = [[e[0][:19], e[1] or 'System', e[2], e[3].upper(), e[4][:40]]
                         for e in events]
            print("\n" + tabulate(event_data,
                                 headers=['Time', 'User', 'Event', 'Severity', 'Details'],
                                 tablefmt='grid'))
        else:
            print(f"\n✅ No events found with severity: {severity}")

    elif choice == '3':
        event_type = input("Enter event type: ").strip()
        conn = dashboard._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT se.event_time, u.username, se.event_type, se.severity, se.details
            FROM security_events se
            LEFT JOIN users u ON se.user_id = u.id
            WHERE se.event_type LIKE ?
            ORDER BY se.event_time DESC
            LIMIT 50
        """, (f"%{event_type}%",))
        events = cursor.fetchall()
        conn.close()

        if events:
            event_data = [[e[0][:19], e[1] or 'System', e[2], e[3].upper(), e[4][:40]]
                         for e in events]
            print("\n" + tabulate(event_data,
                                 headers=['Time', 'User', 'Event', 'Severity', 'Details'],
                                 tablefmt='grid'))
        else:
            print(f"\n✅ No events found for type: {event_type}")


def encryption_management_menu(dashboard):
    """Encryption key management menu"""
    print("\n" + "="*80)
    print("🔒 ENCRYPTION KEY MANAGEMENT")
    print("="*80)

    print("\n1. View Encryption Keys")
    print("2. View Encrypted Fields")
    print("3. Check Key Rotation Status")
    print("4. Generate Key Rotation Report")
    print("0. Back")

    choice = input("\nEnter your choice: ").strip()

    if choice == '1' or choice == '2':
        dashboard.display_encryption_status()
    elif choice == '3':
        keys = dashboard.encryption_mgr.get_key_rotation_status()
        print("\n🔑 Key Rotation Status:")
        print("-" * 80)
        for key in keys:
            status = "⚠️ NEEDS ROTATION" if key['needs_rotation'] else "✅ OK"
            print(f"Key {key['key_id']}: {key['age_days']} days old - {status}")
    elif choice == '4':
        keys = dashboard.encryption_mgr.get_key_rotation_status()
        needs_rotation = [k for k in keys if k['needs_rotation']]
        print("\n📋 Key Rotation Report:")
        print(f"   Total Keys: {len(keys)}")
        print(f"   Need Rotation: {len(needs_rotation)}")
        if needs_rotation:
            print("\n   Keys requiring rotation:")
            for key in needs_rotation:
                print(f"   - {key['key_id']} ({key['age_days']} days old)")


def password_security_menu(dashboard):
    """Password security management menu"""
    print("\n" + "="*80)
    print("🔐 PASSWORD SECURITY MANAGEMENT")
    print("="*80)

    print("\n1. Check Password Strength")
    print("2. Check if Password is Compromised")
    print("3. View Password Policy Compliance")
    print("4. View Password History (User)")
    print("0. Back")

    choice = input("\nEnter your choice: ").strip()

    if choice == '1':
        password = input("Enter password to test: ").strip()
        result = dashboard.password_mgr.calculate_password_strength(password)

        print(f"\n📊 Password Strength Analysis:")
        print(f"   Score: {result['score']}/100")
        print(f"   Strength: {result['strength'].upper()}")
        if result['feedback']:
            print("\n   Suggestions:")
            for suggestion in result['feedback']:
                print(f"   - {suggestion}")

    elif choice == '2':
        password = input("Enter password to check: ").strip()
        result = dashboard.password_mgr.check_compromised_password(password)

        if result.get('compromised'):
            print(f"\n⚠️ WARNING: This password has been compromised!")
            print(f"   Found in {result['count']} data breaches")
        else:
            print("\n✅ Password not found in known breaches")

    elif choice == '3':
        conn = dashboard._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.username, ppc.last_password_change, ppc.must_change
            FROM password_policy_compliance ppc
            JOIN users u ON ppc.user_id = u.id
            ORDER BY ppc.last_password_change ASC
            LIMIT 50
        """)
        compliance = cursor.fetchall()
        conn.close()

        if compliance:
            comp_data = [[c[0], c[1][:19] if c[1] else 'Never', '⚠️ Yes' if c[2] else 'No']
                        for c in compliance]
            print("\n" + tabulate(comp_data,
                                 headers=['Username', 'Last Changed', 'Must Change'],
                                 tablefmt='grid'))
        else:
            print("\n✅ No compliance data found")


def data_export_approval_menu(dashboard):
    """Data export approval menu"""
    print("\n" + "="*80)
    print("📊 DATA EXPORT APPROVAL")
    print("="*80)

    dashboard.display_dlp_exports()

    print("\n1. Approve Export Request")
    print("2. Deny Export Request")
    print("3. View Pending Requests Only")
    print("0. Back")

    choice = input("\nEnter your choice: ").strip()

    if choice == '1':
        export_id = input("Enter export ID to approve: ").strip()
        try:
            conn = dashboard._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE bulk_export_log
                SET status = 'approved', approved_by = ?, approved_at = ?
                WHERE id = ?
            """, (dashboard.admin_user_id, datetime.now(), int(export_id)))
            conn.commit()
            conn.close()
            print(f"\n✅ Export request {export_id} approved")
        except Exception as e:
            print(f"\n❌ Error approving export: {e}")

    elif choice == '2':
        export_id = input("Enter export ID to deny: ").strip()
        try:
            conn = dashboard._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE bulk_export_log
                SET status = 'denied', approved_by = ?, approved_at = ?
                WHERE id = ?
            """, (dashboard.admin_user_id, datetime.now(), int(export_id)))
            conn.commit()
            conn.close()
            print(f"\n✅ Export request {export_id} denied")
        except Exception as e:
            print(f"\n❌ Error denying export: {e}")

    elif choice == '3':
        conn = dashboard._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT bel.id, u.username, bel.resource_type, bel.record_count,
                   bel.status, bel.exported_at
            FROM bulk_export_log bel
            LEFT JOIN users u ON bel.user_id = u.id
            WHERE bel.status = 'pending'
            ORDER BY bel.exported_at DESC
        """)
        exports = cursor.fetchall()
        conn.close()

        if exports:
            export_data = [[e[0], e[1] or 'N/A', e[2], e[3], e[4], e[5][:19] if e[5] else 'N/A']
                          for e in exports]
            print("\n" + tabulate(export_data,
                                 headers=['ID', 'User', 'Resource', 'Records', 'Status', 'Requested'],
                                 tablefmt='grid'))
        else:
            print("\n✅ No pending export requests")


def security_events_report_menu(dashboard):
    """Security events report menu"""
    print("\n" + "="*80)
    print("📈 SECURITY EVENTS REPORT")
    print("="*80)

    days = input("Enter number of days to analyze (default 30): ").strip() or "30"

    conn = dashboard._get_connection()
    cursor = conn.cursor()

    # Event type summary
    cursor.execute("""
        SELECT event_type, COUNT(*) as count
        FROM security_events
        WHERE event_time > datetime('now', ?)
        GROUP BY event_type
        ORDER BY count DESC
    """, (f"-{days} days",))

    events = cursor.fetchall()

    if events:
        print(f"\n📊 Event Types (Last {days} days):")
        event_data = [[e[0], e[1]] for e in events]
        print(tabulate(event_data, headers=['Event Type', 'Count'], tablefmt='grid'))

    # Severity summary
    cursor.execute("""
        SELECT severity, COUNT(*) as count
        FROM security_events
        WHERE event_time > datetime('now', ?)
        GROUP BY severity
        ORDER BY
            CASE severity
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
            END
    """, (f"-{days} days",))

    severity = cursor.fetchall()

    if severity:
        print(f"\n⚠️ Event Severity (Last {days} days):")
        severity_data = [[s[0].upper(), s[1]] for s in severity]
        print(tabulate(severity_data, headers=['Severity', 'Count'], tablefmt='grid'))

    conn.close()


def access_audit_report_menu(dashboard):
    """Access audit report menu"""
    print("\n" + "="*80)
    print("📋 ACCESS AUDIT REPORT")
    print("="*80)

    days = input("Enter number of days to analyze (default 30): ").strip() or "30"

    conn = dashboard._get_connection()
    cursor = conn.cursor()

    # Most accessed resources
    cursor.execute("""
        SELECT resource_type, action, COUNT(*) as count
        FROM data_access_log
        WHERE accessed_at > datetime('now', ?)
        GROUP BY resource_type, action
        ORDER BY count DESC
        LIMIT 20
    """, (f"-{days} days",))

    access = cursor.fetchall()

    if access:
        print(f"\n📊 Most Accessed Resources (Last {days} days):")
        access_data = [[a[0], a[1], a[2]] for a in access]
        print(tabulate(access_data, headers=['Resource', 'Action', 'Count'], tablefmt='grid'))

    # Top users by activity
    cursor.execute("""
        SELECT u.username, COUNT(*) as count
        FROM data_access_log dal
        LEFT JOIN users u ON dal.user_id = u.id
        WHERE dal.accessed_at > datetime('now', ?)
        GROUP BY dal.user_id
        ORDER BY count DESC
        LIMIT 10
    """, (f"-{days} days",))

    users = cursor.fetchall()

    if users:
        print(f"\n👥 Most Active Users (Last {days} days):")
        user_data = [[u[0] or 'Unknown', u[1]] for u in users]
        print(tabulate(user_data, headers=['Username', 'Actions'], tablefmt='grid'))

    conn.close()


def password_strength_checker_menu(dashboard):
    """Password strength checker menu"""
    print("\n" + "="*80)
    print("🔐 PASSWORD STRENGTH CHECKER")
    print("="*80)

    password = input("\nEnter password to test: ").strip()

    if not password:
        print("\n❌ No password entered")
        return

    result = dashboard.password_mgr.calculate_password_strength(password)

    print("\n" + "="*80)
    print("📊 PASSWORD STRENGTH ANALYSIS")
    print("="*80)

    # Visual strength indicator
    score = result['score']
    bars = int(score / 10)
    bar_display = "█" * bars + "░" * (10 - bars)

    print(f"\nStrength: [{bar_display}] {score}/100")
    print(f"Rating: {result['strength'].upper()}")

    if result['feedback']:
        print("\n💡 Suggestions for improvement:")
        for i, suggestion in enumerate(result['feedback'], 1):
            print(f"   {i}. {suggestion}")
    else:
        print("\n✅ This is a strong password!")


def compromised_password_check_menu(dashboard):
    """Compromised password check menu"""
    print("\n" + "="*80)
    print("🔍 COMPROMISED PASSWORD CHECK")
    print("="*80)

    password = input("\nEnter password to check: ").strip()

    if not password:
        print("\n❌ No password entered")
        return

    print("\n⏳ Checking against breach databases...")

    result = dashboard.password_mgr.check_compromised_password(password)

    print("\n" + "="*80)
    if result.get('compromised'):
        print("⚠️  PASSWORD COMPROMISED!")
        print("="*80)
        print(f"\n🔴 This password has appeared in {result['count']} data breaches")
        print("\n⚠️  RECOMMENDATION: Do NOT use this password!")
        print("   Choose a different, unique password immediately.")
    else:
        print("✅ PASSWORD SAFE")
        print("="*80)
        print("\n✅ This password was not found in known breach databases")
        print("   However, always use strong, unique passwords for each account.")

    if result.get('error'):
        print(f"\n⚠️ Note: {result['error']}")


def user_management_cli_menu(dashboard):
    """User management CLI menu wrapper - provides access to all auth_module.user_authentication functions"""
    print("\n" + "="*80)
    print("👥 USER MANAGEMENT")
    print("="*80)

    if not AUTH_MODULE_AVAILABLE:
        print("\n❌ User management CLI is not available")
        print("   This feature requires the authentication module.")
        print("\nAvailable auth_module functions (if imported):")
        if auth_module:
            funcs = [f for f in dir(auth_module) if not f.startswith('_') and callable(getattr(auth_module, f))]
            print(f"   Total functions available: {len(funcs)}")
            print(f"   Key functions: display_user_management_menu, UserAuth, create_user, etc.")
        return

    # We need an auth object to call the user management menu
    # Get it from the global context or create a temporary one
    try:
        from university_system.infrastructure.shared_context import get_auth
        auth = get_auth()

        if auth and auth.current_user:
            # Use the full auth_module to call the function
            auth_module.display_user_management_menu(auth)
        else:
            print("\n❌ No active authentication session")
            print("   Please ensure you're logged in through the main CLI menu")
            print("\nNote: Full auth_module is available for direct function calls")
    except Exception as e:
        print(f"\n❌ Error accessing user management: {e}")
        print("\nManual User Management:")
        print("1. List Users")
        print("2. View User Count")
        print("0. Back")

        choice = input("\nEnter your choice: ").strip()

        if choice == '1':
            conn = dashboard._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, role, is_active, two_fa_enabled, last_login
                FROM users
                ORDER BY id
                LIMIT 50
            """)
            users = cursor.fetchall()
            conn.close()

            if users:
                user_data = [[u[0], u[1], u[2], '✅' if u[3] else '❌',
                             '🔐' if u[4] else '🔓', u[5][:19] if u[5] else 'Never']
                            for u in users]
                print("\n" + tabulate(user_data,
                                     headers=['ID', 'Username', 'Role', 'Active', '2FA', 'Last Login'],
                                     tablefmt='grid'))
            else:
                print("\n✅ No users found")

        elif choice == '2':
            conn = dashboard._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
            active_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users WHERE two_fa_enabled = 1")
            mfa_count = cursor.fetchone()[0]
            conn.close()

            print(f"\n📊 User Statistics:")
            print(f"   Total Users: {count}")
            print(f"   Active Users: {active_count}")
            print(f"   Users with 2FA: {mfa_count}")


def role_management_cli_menu(dashboard):
    """Role management CLI menu wrapper - provides access to all auth_module functions"""
    print("\n" + "="*80)
    print("🔑 ROLE & PERMISSION MANAGEMENT")
    print("="*80)

    if not AUTH_MODULE_AVAILABLE:
        print("\n❌ Role management CLI is not available")
        print("   This feature requires the authentication module.")
        print("\nAvailable auth_module functions (if imported):")
        if auth_module:
            role_funcs = [f for f in dir(auth_module) if 'role' in f.lower() or 'permission' in f.lower()]
            print(f"   Role/Permission functions: {', '.join(role_funcs[:10])}")
        return

    try:
        from university_system.infrastructure.shared_context import get_auth
        auth = get_auth()

        if auth and auth.current_user:
            # Use the full auth_module to call the function
            auth_module.display_role_management_menu(auth)
        else:
            print("\n❌ No active authentication session")
            print("   Please ensure you're logged in through the main CLI menu")
            print("\nNote: Full auth_module is available for direct function calls")
    except Exception as e:
        print(f"\n❌ Error accessing role management: {e}")
        print("\nQuick Role Overview:")

        conn = dashboard._get_connection()
        cursor = conn.cursor()

        # List roles
        cursor.execute("SELECT id, name, description FROM roles ORDER BY id")
        roles = cursor.fetchall()

        if roles:
            role_data = [[r[0], r[1], r[2][:50] if r[2] else 'N/A'] for r in roles]
            print("\n" + tabulate(role_data,
                                 headers=['ID', 'Role', 'Description'],
                                 tablefmt='grid'))
        else:
            print("\n✅ No roles found")

        # List permissions
        cursor.execute("SELECT id, name, description FROM permissions ORDER BY name LIMIT 20")
        perms = cursor.fetchall()

        if perms:
            print("\n📋 Available Permissions (showing 20):")
            perm_data = [[p[0], p[1], p[2][:50] if p[2] else 'N/A'] for p in perms]
            print(tabulate(perm_data,
                          headers=['ID', 'Permission', 'Description'],
                          tablefmt='grid'))

        conn.close()


def my_account_cli_menu(dashboard):
    """My account CLI menu wrapper - provides access to all auth_module account functions"""
    print("\n" + "="*80)
    print("👤 MY ACCOUNT SETTINGS")
    print("="*80)

    if not AUTH_MODULE_AVAILABLE:
        print("\n❌ Account management CLI is not available")
        print("   This feature requires the authentication module.")
        print("\nAvailable auth_module functions (if imported):")
        if auth_module:
            account_funcs = [f for f in dir(auth_module) if 'account' in f.lower() or 'profile' in f.lower() or 'password' in f.lower()]
            print(f"   Account functions: {', '.join(account_funcs[:10])}")
        return

    try:
        from university_system.infrastructure.shared_context import get_auth
        auth = get_auth()

        if auth and auth.current_user:
            # Use the full auth_module to call the function
            auth_module.display_my_account_menu(auth)
        else:
            print("\n❌ No active authentication session")
            print("   This feature is available when logged in through the main CLI")
            print("\nNote: Full auth_module is available for direct function calls")
    except Exception as e:
        print(f"\n❌ Error accessing account settings: {e}")
        print("\nAccount management requires an active login session")
        print(f"\nAvailable via auth_module: {len([f for f in dir(auth_module) if callable(getattr(auth_module, f))])} functions")


def display_available_modules_info():
    """Display information about all available imported modules and their functions"""
    print("\n" + "="*80)
    print("📦 AVAILABLE SECURITY MODULES & FUNCTIONS")
    print("="*80)

    modules_info = {
        'session_mgmt': ('Session Management Module', session_mgmt),
        'encryption': ('Data Encryption Module', encryption),
        'comp_security': ('Comprehensive Security Module', comp_security),
        'security_tables': ('Security Tables Initialization', security_tables),
        'auth_module': ('User Authentication Module', auth_module if AUTH_MODULE_AVAILABLE else None),
        'mfa_module': ('Multi-Factor Authentication Module', mfa_module if AUTH_MODULE_AVAILABLE else None),
        'mfa_integration_module': ('MFA Integration Module', mfa_integration_module if AUTH_MODULE_AVAILABLE else None),
    }

    for module_var, (name, module_obj) in modules_info.items():
        print(f"\n{'='*80}")
        print(f"📚 {name} ({module_var})")
        print(f"{'='*80}")

        if module_obj is None:
            print("   ❌ Module not available")
            continue

        # Get all functions and classes
        all_items = dir(module_obj)
        functions = [item for item in all_items if not item.startswith('_') and callable(getattr(module_obj, item, None))]
        classes = [item for item in all_items if not item.startswith('_') and isinstance(getattr(module_obj, item, None), type)]

        print(f"   ✅ Module loaded successfully")
        print(f"   📊 Total public items: {len([i for i in all_items if not i.startswith('_')])}")
        print(f"   🔧 Functions: {len(functions)}")
        print(f"   📦 Classes: {len(classes)}")

        if classes:
            print(f"\n   Key Classes:")
            for cls in classes[:10]:  # Show first 10
                print(f"      • {cls}")
            if len(classes) > 10:
                print(f"      ... and {len(classes) - 10} more")

        if functions:
            print(f"\n   Key Functions:")
            for func in functions[:15]:  # Show first 15
                print(f"      • {func}")
            if len(functions) > 15:
                print(f"      ... and {len(functions) - 15} more")

    print("\n" + "="*80)
    print("💡 USAGE EXAMPLES")
    print("="*80)
    print("\nYou can call any function directly from the imported modules:")
    print("\nExample 1: Session Management")
    print("   from security_dashboard_cli import session_mgmt")
    print("   session_mgr = session_mgmt.SessionManager()")
    print("   session_mgr.get_active_sessions()")
    print("\nExample 2: User Authentication")
    if AUTH_MODULE_AVAILABLE:
        print("   from security_dashboard_cli import auth_module")
        print("   auth = auth_module.UserAuth()")
        print("   auth.create_user('username', 'password', 'role')")
    else:
        print("   ❌ Not available - install authentication module")
    print("\nExample 3: Encryption")
    print("   from security_dashboard_cli import encryption")
    print("   enc_mgr = encryption.EncryptionManager()")
    print("   enc_mgr.encrypt_field('table', 'column', 'value')")
    print("\nExample 4: Security Audit")
    print("   from security_dashboard_cli import comp_security")
    print("   audit = comp_security.SecurityAuditManager()")
    print("   audit.log_security_event('event_type', user_id, 'high')")
    print("\n" + "="*80)


def display_module_functions_menu():
    """Interactive menu to explore module functions"""
    while True:
        print("\n" + "="*80)
        print("🔍 MODULE EXPLORER")
        print("="*80)
        print("\n1. View All Available Modules")
        print("2. Explore Session Management Functions")
        print("3. Explore Encryption Functions")
        print("4. Explore Comprehensive Security Functions")
        print("5. Explore Authentication Functions")
        print("6. Explore MFA Functions")
        print("7. Search for Function by Name")
        print("0. Back")

        choice = input("\nEnter your choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            display_available_modules_info()
        elif choice == '2':
            explore_module(session_mgmt, "Session Management")
        elif choice == '3':
            explore_module(encryption, "Data Encryption")
        elif choice == '4':
            explore_module(comp_security, "Comprehensive Security")
        elif choice == '5':
            if AUTH_MODULE_AVAILABLE:
                explore_module(auth_module, "User Authentication")
            else:
                print("\n❌ Authentication module not available")
        elif choice == '6':
            if AUTH_MODULE_AVAILABLE:
                explore_module(mfa_module, "Multi-Factor Authentication")
            else:
                print("\n❌ MFA module not available")
        elif choice == '7':
            search_functions()
        else:
            print("\n❌ Invalid choice")

        input("\nPress Enter to continue...")


def explore_module(module_obj, module_name):
    """Explore a specific module's functions"""
    print("\n" + "="*80)
    print(f"📚 {module_name} Module")
    print("="*80)

    if module_obj is None:
        print("\n❌ Module not available")
        return

    functions = [item for item in dir(module_obj) if not item.startswith('_') and callable(getattr(module_obj, item, None))]
    classes = [item for item in dir(module_obj) if not item.startswith('_') and isinstance(getattr(module_obj, item, None), type)]

    print(f"\n📦 Classes ({len(classes)}):")
    for cls in sorted(classes):
        print(f"   • {cls}")

    print(f"\n🔧 Functions ({len(functions)}):")
    for func in sorted(functions):
        func_obj = getattr(module_obj, func)
        doc = func_obj.__doc__
        doc_summary = doc.split('\n')[0] if doc else "No documentation"
        print(f"   • {func}")
        print(f"     └─ {doc_summary[:70]}")


def search_functions():
    """Search for functions across all modules"""
    search_term = input("\nEnter search term: ").strip().lower()

    if not search_term:
        print("\n❌ No search term entered")
        return

    print("\n" + "="*80)
    print(f"🔍 Search Results for: '{search_term}'")
    print("="*80)

    modules = {
        'session_mgmt': session_mgmt,
        'encryption': encryption,
        'comp_security': comp_security,
        'auth_module': auth_module if AUTH_MODULE_AVAILABLE else None,
        'mfa_module': mfa_module if AUTH_MODULE_AVAILABLE else None,
    }

    found_count = 0
    for module_name, module_obj in modules.items():
        if module_obj is None:
            continue

        items = [item for item in dir(module_obj) if not item.startswith('_') and search_term in item.lower()]

        if items:
            print(f"\n📦 {module_name}:")
            for item in sorted(items):
                print(f"   • {item}")
                found_count += 1

    if found_count == 0:
        print(f"\n❌ No matches found for '{search_term}'")
    else:
        print(f"\n✅ Found {found_count} matches")


if __name__ == '__main__':
    # Test the CLI dashboard
    display_security_dashboard_menu(admin_user_id=1)
