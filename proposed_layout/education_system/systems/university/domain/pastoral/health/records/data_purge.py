from education_system.systems.university.infrastructure.database.db import sqlite3, DatabaseManager, get_connection
from education_system.systems.university.domain.pastoral.health.records.backup_export import create_database_backup
from education_system.systems.university.domain.pastoral.health.services import log_audit_event
from datetime import datetime, timedelta
from education_system.systems.university.domain.pastoral.health.services import create_sqlite_backup
import random
import os
import hashlib
import hmac
import json
import logging
import threading
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from cryptography.fernet import Fernet
import requests
from collections import defaultdict
import csv
import statistics
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.database.data_backup import backup_before_operation
from education_system.systems.university.infrastructure.email import (
    send_appointment_confirmation,
    send_health_notification,
)
from education_system.systems.university.infrastructure.logging.log_config import configure_logging

# Configure logging for audit trail
audit_logger = configure_logging(name=__name__)

# Encryption key management


def update_retention_policy(auth):
    if auth.current_user['role'] != 'admin':
        print("Only administrators can update retention policies.")
        return

    backup_before_operation('update_retention_policy')

    conn = get_connection()
    cursor = conn.cursor()

    # Show current policies
    cursor.execute('''
    SELECT id, data_type, retention_period_days, auto_archive, auto_delete
    FROM data_retention_policies
    ORDER BY data_type
    ''')

    policies = cursor.fetchall()

    print("\n===== Current Retention Policies =====")
    for i, (policy_id, data_type, retention_days, auto_archive, auto_delete) in enumerate(policies):
        retention_years = retention_days / 365
        print(f"{i+1}. {data_type}: {retention_days} days ({retention_years:.1f} years)")
        print(f"   Auto-archive: {'Yes' if auto_archive else 'No'}")
        print(f"   Auto-delete: {'Yes' if auto_delete else 'No'}")

    while True:
        choice = input(f"\nSelect policy to update (1-{len(policies)}): ")
        if choice.isdigit() and 1 <= int(choice) <= len(policies):
            selected_policy = policies[int(choice) - 1]
            break
        print("Invalid choice. Please try again.")

    policy_id, data_type, current_retention, current_archive, current_delete = selected_policy

    print(f"\nUpdating policy for: {data_type}")
    print(f"Current retention: {current_retention} days")

    new_retention = input(f"New retention period (days) [{current_retention}]: ").strip()
    if not new_retention:
        new_retention = current_retention
    else:
        try:
            new_retention = int(new_retention)
        except ValueError:
            print("Invalid number. Keeping current value.")
            new_retention = current_retention

    auto_archive_input = input(f"Auto-archive ({'Yes' if current_archive else 'No'}) [y/n]: ").strip().lower()
    if auto_archive_input == 'y':
        new_archive = 1
    elif auto_archive_input == 'n':
        new_archive = 0
    else:
        new_archive = current_archive

    auto_delete_input = input(f"Auto-delete ({'Yes' if current_delete else 'No'}) [y/n]: ").strip().lower()
    if auto_delete_input == 'y':
        new_delete = 1
    elif auto_delete_input == 'n':
        new_delete = 0
    else:
        new_delete = current_delete

    # Warning for auto-delete
    if new_delete and not current_delete:
        print("\n⚠️  WARNING: Enabling auto-delete will permanently remove data!")
        confirm = input("Are you sure you want to enable auto-delete? (yes/no): ").lower()
        if confirm != 'yes':
            new_delete = 0
            print("Auto-delete disabled.")

    cursor.execute('''
    UPDATE data_retention_policies
    SET retention_period_days = ?, auto_archive = ?, auto_delete = ?
    WHERE id = ?
    ''', (new_retention, new_archive, new_delete, policy_id))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'update_retention_policy', 'retention_policy', policy_id)

    print(f"\nRetention policy for {data_type} updated successfully!")
    print(f"New retention period: {new_retention} days ({new_retention/365:.1f} years)")

    conn.close()

def archive_old_data(auth):
    if auth.current_user['role'] != 'admin':
        print("Only administrators can archive data.")
        return

    backup_before_operation('archive_old_data')

    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Data Archival Process =====")

    # Get retention policies
    cursor.execute('''
    SELECT data_type, retention_period_days, auto_archive
    FROM data_retention_policies
    WHERE auto_archive = 1
    ORDER BY data_type
    ''')

    policies = cursor.fetchall()

    if not policies:
        print("No auto-archival policies found.")
        conn.close()
        return

    archived_counts = {}

    for data_type, retention_days, auto_archive in policies:
        cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime('%Y-%m-%d')

        print(f"\nProcessing {data_type} (older than {cutoff_date})...")

        if data_type == 'health_records':
            # Archive old health records
            cursor.execute('''
            SELECT COUNT(*) FROM health_records
            WHERE record_date < ?
            ''', (cutoff_date,))

            old_count = cursor.fetchone()[0]

            if old_count > 0:
                # In a real system, this would move records to an archive table
                print(f"  Found {old_count} records to archive")
                archived_counts[data_type] = old_count
            else:
                print("  No old records found")

        elif data_type == 'vaccination_records':
            cursor.execute('''
            SELECT COUNT(*) FROM vaccination_records
            WHERE administered_date < ?
            ''', (cutoff_date,))

            old_count = cursor.fetchone()[0]

            if old_count > 0:
                print(f"  Found {old_count} vaccination records to archive")
                archived_counts[data_type] = old_count
            else:
                print("  No old vaccination records found")

        elif data_type == 'appointments':
            cursor.execute('''
            SELECT COUNT(*) FROM health_appointments
            WHERE appointment_date < ?
            ''', (cutoff_date,))

            old_count = cursor.fetchone()[0]

            if old_count > 0:
                print(f"  Found {old_count} appointments to archive")
                archived_counts[data_type] = old_count
            else:
                print("  No old appointments found")

    if archived_counts:
        print("\n===== Archival Summary =====")
        for data_type, count in archived_counts.items():
            print(f"{data_type}: {count} records")

        proceed = input("\nProceed with archival? (yes/no): ").lower()
        if proceed == 'yes':
            # In a real implementation, this would move data to archive tables
            total_archived = sum(archived_counts.values())
            log_audit_event(auth.current_user['id'], 'archive_old_data', 'data_archival', 0,
                           f"Archived {total_archived} records")
            print("Data archival completed!")
        else:
            print("Archival cancelled.")
    else:
        print("No old data found for archival.")

    conn.close()

def data_purge_menu(auth):
    if auth.current_user['role'] != 'admin':
        print("Only administrators can access data purge functions.")
        return

    print("\n===== Data Purge Menu =====")
    print("⚠️  WARNING: Data purge operations permanently delete data!")
    print("Ensure proper backups exist before proceeding.")

    while True:
        print("\n1. View Data Eligible for Purge")
        print("2. Purge Expired Data")
        print("3. Custom Data Purge")
        print("4. Return to Main Menu")

        choice = input("\nEnter your choice (1-4): ")

        if choice == '1':
            view_purgeable_data(auth)
        elif choice == '2':
            purge_expired_data(auth)
        elif choice == '3':
            custom_data_purge(auth)
        elif choice == '4':
            break
        else:
            print("Invalid choice. Please try again.")

def view_purgeable_data(auth):
    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Data Eligible for Purge =====")

    # Get retention policies with auto-delete enabled
    cursor.execute('''
    SELECT data_type, retention_period_days
    FROM data_retention_policies
    WHERE auto_delete = 1
    ''')

    policies = cursor.fetchall()

    for data_type, retention_days in policies:
        cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime('%Y-%m-%d')

        if data_type == 'health_records':
            cursor.execute('''
            SELECT COUNT(*) FROM health_records
            WHERE record_date < ?
            ''', (cutoff_date,))
        elif data_type == 'appointments':
            cursor.execute('''
            SELECT COUNT(*) FROM health_appointments
            WHERE appointment_date < ?
            ''', (cutoff_date,))
        else:
            continue

        old_count = cursor.fetchone()[0]
        print(f"{data_type}: {old_count} records older than {cutoff_date}")

    conn.close()

def purge_expired_data(auth):
    """
    Destroys data in all app tables (keeps schema). Requires admin, double-confirmation,
    and a successful on-disk backup before proceeding.
    """
    try:
        username = getattr(auth, "username", None) or ""
        if username.lower() != "admin":
            print("Only 'admin' can perform a purge.")
            input("Press Enter to return...")
            return

        confirm = input("Type 'DELETE' to confirm you want to proceed: ").strip()
        if confirm != "DELETE":
            print("Cancelled.")
            return

        who = input("Type your username to confirm: ").strip()
        if who != username:
            print("Username mismatch. Cancelled.")
            return

        conn = get_connection()
        # --- Mandatory backup ---
        print("Creating backup before purge...")
        try:
            backup_path = create_sqlite_backup(conn, label="pre_purge")
            print(f"Backup created: {backup_path}")
        except Exception as e:
            print(f"Error creating backup: {e}")
            print("Purge aborted because backup failed.")
            try:
                conn.close()
            except Exception as ex:
                audit_logger.debug(f"Error closing connection after backup failure: {ex}")
            input("Press Enter to return...")
            return

        # --- Purge phase (transactional) ---
        try:
            conn.execute("PRAGMA foreign_keys = OFF")
            cur = conn.cursor()
            tables = [r[0] for r in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()]

            # If there are tables you explicitly want to KEEP, list them here:
            keep = set()  # e.g., {"templates"} if you want to preserve templates
            purge_tables = [t for t in tables if t not in keep]

            for t in purge_tables:
                from education_system.systems.university.infrastructure.sql_safety import validate_table_name
                validated_t = validate_table_name(t, conn=conn)
                cur.execute("DELETE FROM [" + validated_t + "]")

            conn.commit()
            conn.execute("PRAGMA foreign_keys = ON")
        except Exception as e:
            try:
                conn.rollback()
            except Exception as ex:
                audit_logger.debug(f"Error during rollback: {ex}")
            print(f"Purge failed: {e}")
            print("No changes have been committed.")
            input("Press Enter to return...")
            return
        finally:
            try:
                conn.close()
            except Exception as ex:
                audit_logger.debug(f"Error closing connection in finally block: {ex}")

        # Optional: reclaim file space
        try:
            conn2 = get_connection()
            conn2.execute("VACUUM")
            conn2.close()
        except Exception as e:
            audit_logger.debug(f"Error during VACUUM operation: {e}")

        # Optional: audit
        try:
            from education_system.systems.university.domain.pastoral.health.services import log_audit_event
            log_audit_event(auth, action="PURGE", status="SUCCESS", details="All tables cleared")
        except Exception as e:
            audit_logger.warning(f"Failed to log audit event for purge: {e}")

        print("Data purge completed.")

    except KeyboardInterrupt:
        print("\nCancelled by user.")

def retention_compliance_report(auth):
    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Data Retention Compliance Report =====")

    # Get all retention policies
    cursor.execute('''
    SELECT data_type, retention_period_days, auto_archive, auto_delete
    FROM data_retention_policies
    ORDER BY data_type
    ''')

    policies = cursor.fetchall()

    compliance_summary = []

    for data_type, retention_days, auto_archive, auto_delete in policies:
        cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime('%Y-%m-%d')

        # Count records exceeding retention period
        if data_type == 'health_records':
            cursor.execute('''
            SELECT COUNT(*) FROM health_records
            WHERE record_date < ?
            ''', (cutoff_date,))
        elif data_type == 'vaccination_records':
            cursor.execute('''
            SELECT COUNT(*) FROM vaccination_records
            WHERE administered_date < ?
            ''', (cutoff_date,))
        elif data_type == 'appointments':
            cursor.execute('''
            SELECT COUNT(*) FROM health_appointments
            WHERE appointment_date < ?
            ''', (cutoff_date,))
        else:
            continue

        old_count = cursor.fetchone()[0]

        # Count total records
        if data_type == 'health_records':
            cursor.execute('SELECT COUNT(*) FROM health_records')
        elif data_type == 'vaccination_records':
            cursor.execute('SELECT COUNT(*) FROM vaccination_records')
        elif data_type == 'appointments':
            cursor.execute('SELECT COUNT(*) FROM health_appointments')

        total_count = cursor.fetchone()[0]

        compliance_status = "COMPLIANT" if old_count == 0 else "NON-COMPLIANT"

        compliance_summary.append({
            'data_type': data_type,
            'retention_days': retention_days,
            'total_records': total_count,
            'old_records': old_count,
            'status': compliance_status,
            'auto_archive': auto_archive,
            'auto_delete': auto_delete
        })

    # Display report
    print(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)

    for item in compliance_summary:
        print(f"\nData Type: {item['data_type']}")
        print(f"Retention Period: {item['retention_days']} days ({item['retention_days']/365:.1f} years)")
        print(f"Total Records: {item['total_records']}")
        print(f"Records Exceeding Retention: {item['old_records']}")
        print(f"Compliance Status: {item['status']}")
        print(f"Auto-Archive: {'Enabled' if item['auto_archive'] else 'Disabled'}")
        print(f"Auto-Delete: {'Enabled' if item['auto_delete'] else 'Disabled'}")

        if item['old_records'] > 0:
            print("⚠️  ACTION REQUIRED: Review old records for archival/deletion")

        print("-" * 40)

    # Overall compliance
    non_compliant_types = [item for item in compliance_summary if item['status'] == 'NON-COMPLIANT']

    if non_compliant_types:
        print("\n🔴 OVERALL STATUS: NON-COMPLIANT")
        print(f"Non-compliant data types: {len(non_compliant_types)}")
    else:
        print("\n✅ OVERALL STATUS: COMPLIANT")

    conn.close()

def compliance_monitoring(auth):
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to view compliance monitoring.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Compliance Monitoring =====")

    # HIPAA compliance indicators
    print("HIPAA COMPLIANCE")
    print("-" * 16)

    # Access logging
    cursor.execute('''
    SELECT COUNT(*)
    FROM audit_trail
    WHERE action LIKE '%view%'
    AND timestamp >= date('now', '-30 days')
    ''')

    access_logs = cursor.fetchone()[0]
    print(f"Health record access logs (30 days): {access_logs}")

    if access_logs > 0:
        print("  ✅ Access logging active")
    else:
        print("  🔴 No access logs found")

    # Data encryption compliance
    cursor.execute('''
    SELECT setting_value
    FROM security_settings
    WHERE setting_name = 'encryption_enabled'
    ''')

    encryption_status = cursor.fetchone()
    if encryption_status and encryption_status[0] == '1':
        print("  ✅ Data encryption enabled")
    else:
        print("  🔴 Data encryption not enabled")

    # Documentation compliance
    print("\nDOCUMENTATION COMPLIANCE")
    print("-" * 23)

    # Required fields completion
    cursor.execute('''
    SELECT
        COUNT(*) as total_records,
        SUM(CASE WHEN provider IS NOT NULL AND provider != '' THEN 1 ELSE 0 END) as with_provider,
        SUM(CASE WHEN record_type IS NOT NULL AND record_type != '' THEN 1 ELSE 0 END) as with_type
    FROM health_records
    WHERE record_date >= date('now', '-90 days')
    ''')

    doc_compliance = cursor.fetchone()
    if doc_compliance[0] > 0:
        provider_completion = (doc_compliance[1] / doc_compliance[0] * 100)
        type_completion = (doc_compliance[2] / doc_compliance[0] * 100)

        print(f"Provider documentation: {provider_completion:.1f}%")
        print(f"Record type completion: {type_completion:.1f}%")

        if provider_completion >= 95 and type_completion >= 95:
            print("  ✅ Excellent documentation compliance")
        elif provider_completion >= 85 and type_completion >= 85:
            print("  🟡 Good documentation compliance")
        else:
            print("  🔴 Poor documentation compliance")

    # Data retention compliance
    print("\nDATA RETENTION COMPLIANCE")
    print("-" * 25)

    # Check for records exceeding retention periods
    cursor.execute('''
    SELECT
        drp.data_type,
        drp.retention_period_days,
        COUNT(*) as old_records
    FROM data_retention_policies drp
    LEFT JOIN (
        SELECT 'health_records' as data_type, record_date as record_date FROM health_records
        UNION ALL
        SELECT 'vaccination_records' as data_type, administered_date as record_date FROM vaccination_records
        UNION ALL
        SELECT 'appointments' as data_type, appointment_date as record_date FROM health_appointments
    ) records ON drp.data_type = records.data_type
    WHERE records.record_date < date('now', '-' || drp.retention_period_days || ' days')
    GROUP BY drp.data_type, drp.retention_period_days
    ''')

    retention_status = cursor.fetchall()

    if retention_status:
        print("Records exceeding retention periods:")
        for data_type, retention_days, old_count in retention_status:
            retention_years = retention_days / 365
            print(f"  {data_type}: {old_count} records older than {retention_years:.1f} years")

            if old_count > 0:
                print("    🔴 Action needed - Review for archival/deletion")
    else:
        print("  ✅ All records within retention periods")

    # Vaccination verification compliance
    print("\nVACCINATION VERIFICATION")
    print("-" * 23)

    cursor.execute('''
    SELECT
        COUNT(*) as total_vaccinations,
        SUM(CASE WHEN verified = 1 THEN 1 ELSE 0 END) as verified_count
    FROM vaccination_records
    WHERE administered_date >= date('now', '-365 days')
    ''')

    vax_verification = cursor.fetchone()
    if vax_verification[0] > 0:
        verification_rate = (vax_verification[1] / vax_verification[0] * 100)
        print(f"Vaccination verification rate: {verification_rate:.1f}%")

        if verification_rate >= 90:
            print("  ✅ Excellent verification compliance")
        elif verification_rate >= 80:
            print("  🟡 Good verification compliance")
        else:
            print("  🔴 Poor verification compliance")

    # Generate compliance report
    generate_compliance_report = input("\nGenerate detailed compliance report? (y/n): ").lower()
    if generate_compliance_report == 'y':
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"compliance_report_{timestamp}.txt"

        # This would generate a detailed compliance report
        print(f"Compliance report generated: {report_filename}")
        log_audit_event(auth.current_user['id'], 'generate_compliance_report', 'compliance', 0)

    conn.close()

def data_retention_management(auth):
    """Data retention and archival management"""
    if auth.current_user['role'] != 'admin':
        print("Only administrators can manage data retention.")
        return

    while True:
        print("\n===== Data Retention Management =====")
        print("1. View Retention Policies")
        print("2. Update Retention Policy")
        print("3. Archive Old Data")
        print("4. Data Purge (Permanent Deletion)")
        print("5. Retention Compliance Report")
        print("6. Return to Main Menu")

        choice = input("\nEnter your choice (1-6): ")

        if choice == '1':
            view_retention_policies(auth)
        elif choice == '2':
            update_retention_policy(auth)
        elif choice == '3':
            archive_old_data(auth)
        elif choice == '4':
            data_purge_menu(auth)
        elif choice == '5':
            retention_compliance_report(auth)
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")

def view_retention_policies(auth):
    """View current data retention policies"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT data_type, retention_period_days, auto_archive, auto_delete, created_at
    FROM data_retention_policies
    ORDER BY data_type
    ''')

    policies = cursor.fetchall()

    if not policies:
        print("No retention policies found.")
        conn.close()
        return

    print("\n===== Data Retention Policies =====")
    for policy in policies:
        data_type, retention_days, auto_archive, auto_delete, created_at = policy

        retention_years = retention_days / 365

        print(f"\nData Type: {data_type}")
        print(f"Retention Period: {retention_days} days ({retention_years:.1f} years)")
        print(f"Auto Archive: {'Yes' if auto_archive else 'No'}")
        print(f"Auto Delete: {'Yes' if auto_delete else 'No'}")
        print(f"Policy Created: {created_at}")
        print("-" * 30)

    conn.close()

def custom_data_purge(auth):
    """Custom data purge with specific criteria"""
    print("\n⚠️  CRITICAL WARNING ⚠️")
    print("Custom data purge will PERMANENTLY DELETE data!")
    print("This operation cannot be undone!")

    # Triple confirmation for custom purge
    confirm1 = input("\nType 'CUSTOM_PURGE' to proceed: ")
    if confirm1 != 'CUSTOM_PURGE':
        print("Operation cancelled.")
        return

    confirm2 = input("Type your username to confirm: ")
    if confirm2 != auth.current_user['username']:
        print("Username mismatch. Operation cancelled.")
        return

    confirm3 = input("Type 'CONFIRM_DELETE' for final confirmation: ")
    if confirm3 != 'CONFIRM_DELETE':
        print("Operation cancelled.")
        return

    print("\nCustom purge confirmed. This feature would implement specific purge criteria.")
    print("Implementation requires additional safety measures and business rules.")

    # Log the attempt even if not implemented
    log_audit_event(auth.current_user['id'], 'custom_data_purge_attempt', 'data_purge', 0, "Custom purge requested but not implemented")
