"""Health portal CLI workflow extracted from the legacy module."""

from __future__ import annotations

import csv
import json
import logging
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

from education_system.systems.university.infrastructure.database.db import (
    DEFAULT_DB_PATH,
    get_connection,
)
from education_system import paths

logger = logging.getLogger(__name__)

def security_audit_menu(auth):
    """Security and audit tools menu."""
    print("\n--- Security & Audit Tools ---")

    while True:
        print("\n" + "="*60)
        print("           SECURITY & AUDIT TOOLS")
        print("="*60)
        print("1. View Audit Log")
        print("2. Export Audit Log")
        print("3. View Access Summary")
        print("4. View Failed Login Attempts")
        print("5. Generate Security Report")
        print("0. Return to Main Menu")
        print("="*60)

        choice = input("Enter your choice (0-5): ").strip()

        if choice == '0':
            break
        elif choice == '1':
            view_audit_log(auth)
        elif choice == '2':
            export_audit_log(auth)
        elif choice == '3':
            view_access_summary(auth)
        elif choice == '4':
            view_failed_logins(auth)
        elif choice == '5':
            generate_security_report(auth)
        else:
            print("Invalid choice. Please try again.")

def view_audit_log(auth):
    """View audit log with filtering."""
    print("\n--- Audit Log ---")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create audit_trail table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_trail (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                action TEXT NOT NULL,
                table_name TEXT,
                record_id TEXT,
                details TEXT,
                ip_address TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.commit()

        # Filter options
        print("\nFilter options:")
        print("1. All records")
        print("2. My records only")
        print("3. Last 24 hours")
        print("4. Last 7 days")

        filter_choice = input("Select filter (1-4): ").strip()

        query = "SELECT * FROM audit_trail"
        params = []

        if filter_choice == '2':
            username = auth.get_username()
            query += " WHERE username = ?"
            params.append(username)
        elif filter_choice == '3':
            cutoff = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            query += " WHERE timestamp >= ?"
            params.append(cutoff)
        elif filter_choice == '4':
            cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            query += " WHERE timestamp >= ?"
            params.append(cutoff)

        query += " ORDER BY timestamp DESC LIMIT 50"

        cursor.execute(query, params)
        logs = cursor.fetchall()
        conn.close()

        if logs:
            print("\n" + "="*90)
            print(f"{'ID':<6} {'User':<15} {'Action':<15} {'Table':<15} {'Timestamp':<20}")
            print("="*90)
            for log in logs:
                print(f"{log['id']:<6} {log['username'] or 'System':<15} "
                      f"{log['action']:<15} {log['table_name'] or 'N/A':<15} "
                      f"{log['timestamp']:<20}")
                if log['details']:
                    print(f"       Details: {log['details'][:70]}")
            print("="*90)
            print(f"\nShowing {len(logs)} records")
        else:
            print("\nNo audit log entries found.")

    except Exception as e:
        logger.error(f"Error viewing audit log: {e}")
        print(f"\nError viewing audit log: {e}")

def export_audit_log(auth):
    """Export audit log to CSV."""
    print("\n--- Export Audit Log ---")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Date range filter
        print("\nDate range options:")
        print("1. All time")
        print("2. Last 30 days")
        print("3. Last 90 days")
        print("4. Custom date range")

        range_choice = input("Select range (1-4): ").strip()

        query = "SELECT * FROM audit_trail"
        params = []

        if range_choice == '2':
            cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
            query += " WHERE timestamp >= ?"
            params.append(cutoff)
        elif range_choice == '3':
            cutoff = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d %H:%M:%S')
            query += " WHERE timestamp >= ?"
            params.append(cutoff)
        elif range_choice == '4':
            start_date = input("Start date (YYYY-MM-DD): ").strip()
            end_date = input("End date (YYYY-MM-DD): ").strip()
            query += " WHERE date(timestamp) BETWEEN ? AND ?"
            params.extend([start_date, end_date])

        query += " ORDER BY timestamp DESC"

        cursor.execute(query, params)
        logs = cursor.fetchall()
        conn.close()

        if not logs:
            print("\nNo audit log entries found for the selected period.")
            return

        # Create exports directory
        export_dir = paths.UNIVERSITY_DATA_DIR / 'exports' / 'audit'
        export_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = export_dir / f'audit_log_{timestamp}.csv'

        # Write CSV
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['ID', 'User ID', 'Username', 'Action', 'Table', 'Record ID', 'Details', 'IP Address', 'Timestamp'])
            for log in logs:
                writer.writerow([
                    log['id'],
                    log['user_id'] or '',
                    log['username'] or 'System',
                    log['action'],
                    log['table_name'] or '',
                    log['record_id'] or '',
                    log['details'] or '',
                    log['ip_address'] or '',
                    log['timestamp']
                ])

        print(f"\n✓ Audit log exported to: {filename}")
        print(f"  Total records: {len(logs)}")
        logger.info(f"Audit log exported by {auth.get_username()}")

    except Exception as e:
        logger.error(f"Error exporting audit log: {e}")
        print(f"\nError exporting audit log: {e}")

def view_access_summary(auth):
    """View access summary statistics."""
    print("\n--- Access Summary ---")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\n" + "="*70)
        print("ACCESS SUMMARY STATISTICS")
        print("="*70)

        # Total audit entries
        cursor.execute("SELECT COUNT(*) as count FROM audit_trail")
        total = cursor.fetchone()['count']
        print(f"\nTotal Audit Entries: {total}")

        # Entries by user
        cursor.execute("""
            SELECT username, COUNT(*) as count
            FROM audit_trail
            WHERE username IS NOT NULL
            GROUP BY username
            ORDER BY count DESC
            LIMIT 10
        """)
        user_stats = cursor.fetchall()

        if user_stats:
            print("\nTop 10 Users by Activity:")
            print(f"{'Username':<20} {'Actions':<10}")
            print("-"*30)
            for stat in user_stats:
                print(f"{stat['username']:<20} {stat['count']:<10}")

        # Entries by action type
        cursor.execute("""
            SELECT action, COUNT(*) as count
            FROM audit_trail
            GROUP BY action
            ORDER BY count DESC
        """)
        action_stats = cursor.fetchall()

        if action_stats:
            print("\nActions by Type:")
            print(f"{'Action':<20} {'Count':<10}")
            print("-"*30)
            for stat in action_stats:
                print(f"{stat['action']:<20} {stat['count']:<10}")

        # Recent activity (last 24 hours)
        cutoff = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM audit_trail
            WHERE timestamp >= ?
        """, (cutoff,))
        recent = cursor.fetchone()['count']
        print(f"\nActivity in Last 24 Hours: {recent}")

        # Activity by table
        cursor.execute("""
            SELECT table_name, COUNT(*) as count
            FROM audit_trail
            WHERE table_name IS NOT NULL
            GROUP BY table_name
            ORDER BY count DESC
            LIMIT 5
        """)
        table_stats = cursor.fetchall()

        if table_stats:
            print("\nMost Accessed Tables:")
            print(f"{'Table':<25} {'Accesses':<10}")
            print("-"*35)
            for stat in table_stats:
                print(f"{stat['table_name']:<25} {stat['count']:<10}")

        print("="*70)

        conn.close()

    except Exception as e:
        logger.error(f"Error viewing access summary: {e}")
        print(f"\nError viewing access summary: {e}")

def view_failed_logins(auth):
    """View failed login attempts."""
    print("\n--- Failed Login Attempts ---")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Create failed_logins table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS failed_logins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                ip_address TEXT,
                reason TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        # Query recent failed logins
        cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("""
            SELECT username, ip_address, reason, timestamp
            FROM failed_logins
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT 50
        """, (cutoff,))

        failed = cursor.fetchall()
        conn.close()

        if failed:
            print("\n" + "="*80)
            print("FAILED LOGIN ATTEMPTS (Last 7 Days)")
            print("="*80)
            print(f"{'Username':<20} {'IP Address':<18} {'Reason':<20} {'Timestamp':<20}")
            print("-"*80)
            for attempt in failed:
                print(f"{attempt['username'] or 'Unknown':<20} "
                      f"{attempt['ip_address'] or 'N/A':<18} "
                      f"{attempt['reason'] or 'N/A':<20} "
                      f"{attempt['timestamp']:<20}")
            print("="*80)
            print(f"\nTotal failed attempts: {len(failed)}")

            # Summary by username
            print("\nFailed Attempts by Username:")
            username_counts = {}
            for attempt in failed:
                username = attempt['username'] or 'Unknown'
                username_counts[username] = username_counts.get(username, 0) + 1

            for username, count in sorted(username_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"  {username}: {count} attempts")

        else:
            print("\n✓ No failed login attempts in the last 7 days.")

    except Exception as e:
        logger.error(f"Error viewing failed logins: {e}")
        print(f"\nError viewing failed logins: {e}")

def generate_security_report(auth):
    """Generate comprehensive security report."""
    print("\n--- Security Report ---")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\n" + "="*70)
        print("SECURITY COMPLIANCE REPORT")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)

        # User access statistics
        cursor.execute("SELECT COUNT(DISTINCT username) as count FROM audit_trail WHERE username IS NOT NULL")
        unique_users = cursor.fetchone()['count']
        print(f"\nActive Users (with audit trail): {unique_users}")

        # Recent audit activity
        cutoff_24h = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
        cutoff_7d = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute("SELECT COUNT(*) as count FROM audit_trail WHERE timestamp >= ?", (cutoff_24h,))
        activity_24h = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM audit_trail WHERE timestamp >= ?", (cutoff_7d,))
        activity_7d = cursor.fetchone()['count']

        print("\nAudit Trail Activity:")
        print(f"  Last 24 hours: {activity_24h} events")
        print(f"  Last 7 days: {activity_7d} events")

        # Failed login analysis
        cursor.execute("""
            SELECT COUNT(*) as count FROM failed_logins
            WHERE timestamp >= ?
        """, (cutoff_7d,))
        failed_7d = cursor.fetchone()['count']

        cursor.execute("""
            SELECT username, COUNT(*) as count
            FROM failed_logins
            WHERE timestamp >= ?
            GROUP BY username
            ORDER BY count DESC
            LIMIT 5
        """, (cutoff_7d,))
        top_failed = cursor.fetchall()

        print("\nSecurity Events (Last 7 Days):")
        print(f"  Failed Login Attempts: {failed_7d}")

        if top_failed:
            print("\n  Top Accounts with Failed Logins:")
            for record in top_failed:
                print(f"    {record['username'] or 'Unknown'}: {record['count']} attempts")

        # Data access by table
        cursor.execute("""
            SELECT table_name, COUNT(*) as count
            FROM audit_trail
            WHERE table_name IN ('health_records', 'medical_history', 'vaccinations')
              AND timestamp >= ?
            GROUP BY table_name
        """, (cutoff_7d,))
        sensitive_access = cursor.fetchall()

        if sensitive_access:
            print("\n  Sensitive Data Access (Last 7 Days):")
            for record in sensitive_access:
                print(f"    {record['table_name']}: {record['count']} accesses")

        # Recommendations
        print("\nSecurity Recommendations:")
        if failed_7d > 10:
            print("  ⚠ High number of failed login attempts detected")
            print("    → Review failed login patterns and consider additional security measures")
        else:
            print("  ✓ Failed login attempts within normal range")

        if activity_24h == 0:
            print("  ⚠ No audit trail activity in last 24 hours")
            print("    → Verify audit logging is functioning correctly")
        else:
            print("  ✓ Audit logging is active")

        print("\n" + "="*70)
        print("End of Security Report")
        print("="*70)

        conn.close()
        logger.info(f"Security report generated by {auth.get_username()}")

    except Exception as e:
        logger.error(f"Error generating security report: {e}")
        print(f"\nError generating security report: {e}")
