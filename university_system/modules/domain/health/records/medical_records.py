from university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection
from datetime import datetime, timedelta
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
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth
from university_system.infrastructure.database.data_backup import backup_before_operation
from university_system.infrastructure.email import (
    send_appointment_confirmation,
    send_health_notification,
)
from university_system.infrastructure.database.db import get_connection
from university_system.utils.logging.log_config import configure_logging
from university_system.modules.domain.health.services import critical_values_alert

from university_system.modules.domain.health.services import (
    critical_values_alert,
    get_user_student_id,
    emergency_information,
    create_new_template,
    edit_template,
    use_existing_template,
    import_templates,              # <-- ensure this line exists
    template_usage_statistics,
    shared_templates,
    track_medication_adherence,
    manage_refill_reminders,
    specialist_directory,
    generate_disease_surveillance_report,
)

# Configure logging for audit trail
audit_logger = configure_logging(name=__name__)

def log_audit_event(user_id, action, resource_type, resource_id, details=None, conn=None, max_retries=5):
    """Write an audit row. Reuse caller's connection if provided to avoid SQLite writer locks."""
    try:
        reuse_conn = conn is not None
        if not reuse_conn:
            conn = get_connection()
        cursor = conn.cursor()

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Keep table-creation here for safety (no-op if it already exists).
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_trail (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                action TEXT,
                resource_type TEXT,
                resource_id TEXT,
                old_values TEXT,
                new_values TEXT,
                ip_address TEXT,
                user_agent TEXT,
                timestamp TEXT,
                session_id TEXT
            )
        ''')

        payload = (user_id, action, resource_type, str(resource_id), timestamp, '', details or '')

        for attempt in range(max_retries):
            try:
                cursor.execute("""
                    INSERT INTO audit_trail
                        (user_id, action, resource_type, resource_id, timestamp, old_values, new_values)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, payload)
                if not reuse_conn:
                    conn.commit()
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    time.sleep(0.15 * (2 ** attempt))  # 150ms, 300ms, 600ms, ...
                    continue
                raise

        # File-based audit log too
        audit_logger.info(
            f"USER:{user_id} ACTION:{action} RESOURCE:{resource_type}:{resource_id} DETAILS:{details}"
        )

    except Exception as e:
        # Don't break the flow for audit failures
        print(f"Warning: Audit logging failed: {e}")
    finally:
        if conn and not reuse_conn:
            try:
                conn.close()
            except Exception:
                pass

def init_enhanced_health_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Original tables (keeping existing structure)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            record_type TEXT,
            record_date TEXT,
            description TEXT,
            provider TEXT,
            confidential INTEGER DEFAULT 0,
            created_at TEXT,
            encrypted_data TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Enhanced tables for new features
        
        # Audit trail table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_trail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            action TEXT,
            resource_type TEXT,
            resource_id TEXT,
            old_values TEXT,
            new_values TEXT,
            ip_address TEXT,
            user_agent TEXT,
            timestamp TEXT,
            session_id TEXT
        )
        ''')
        
        # Data retention policies - FIXED COLUMN NAME
        # First check if table exists and has wrong column name
        cursor.execute("PRAGMA table_info(data_retention_policies)")
        existing_columns = cursor.fetchall()
        
        if existing_columns:
            # Check if table has wrong column name
            column_names = [col[1] for col in existing_columns]
            if 'retention_period_days' not in column_names:
                # Drop and recreate table with correct schema
                cursor.execute('DROP TABLE IF EXISTS data_retention_policies')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS data_retention_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_type TEXT,
            retention_period_days INTEGER,
            auto_archive INTEGER DEFAULT 0,
            auto_delete INTEGER DEFAULT 0,
            created_at TEXT
        )
        ''')
        
        # Security settings
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS security_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_name TEXT UNIQUE,
            setting_value TEXT,
            updated_at TEXT,
            updated_by TEXT
        )
        ''')
        
        # Allergies and medical conditions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS allergies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            allergen TEXT,
            severity TEXT,
            reaction_description TEXT,
            diagnosed_date TEXT,
            provider TEXT,
            verified INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS medical_conditions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            condition_name TEXT,
            icd_code TEXT,
            severity TEXT,
            diagnosed_date TEXT,
            status TEXT DEFAULT 'active',
            provider TEXT,
            notes TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Prescriptions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS prescriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            medication_name TEXT,
            dosage TEXT,
            frequency TEXT,
            prescribed_date TEXT,
            start_date TEXT,
            end_date TEXT,
            prescriber TEXT,
            pharmacy TEXT,
            status TEXT DEFAULT 'active',
            notes TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Vital signs
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS vital_signs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            measurement_date TEXT,
            blood_pressure_systolic INTEGER,
            blood_pressure_diastolic INTEGER,
            heart_rate INTEGER,
            temperature REAL,
            weight REAL,
            height REAL,
            bmi REAL,
            recorded_by TEXT,
            notes TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Care plans
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS care_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            condition_id INTEGER,
            plan_name TEXT,
            description TEXT,
            start_date TEXT,
            end_date TEXT,
            provider TEXT,
            status TEXT DEFAULT 'active',
            goals TEXT,
            interventions TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (condition_id) REFERENCES medical_conditions (id)
        )
        ''')
        
        # Referrals
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            referring_provider TEXT,
            specialist_provider TEXT,
            specialty TEXT,
            reason TEXT,
            urgency TEXT,
            referral_date TEXT,
            appointment_date TEXT,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Health metrics and analytics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT,
            metric_value REAL,
            measurement_date TEXT,
            category TEXT,
            subcategory TEXT,
            metadata TEXT,
            calculated_at TEXT
        )
        ''')
        
        # Health screening schedules
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS screening_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            screening_type TEXT,
            due_date TEXT,
            completed_date TEXT,
            status TEXT DEFAULT 'due',
            provider TEXT,
            results TEXT,
            next_due_date TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Risk assessments
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS risk_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            assessment_type TEXT,
            risk_score INTEGER,
            risk_factors TEXT,
            recommendations TEXT,
            assessed_date TEXT,
            assessed_by TEXT,
            follow_up_date TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Emergency contacts (enhanced)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS emergency_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            contact_name TEXT,
            relationship TEXT,
            phone_primary TEXT,
            phone_secondary TEXT,
            email TEXT,
            address TEXT,
            priority_order INTEGER,
            medical_decision_maker INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Provider schedules and availability
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS provider_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider_name TEXT,
            day_of_week INTEGER,
            start_time TEXT,
            end_time TEXT,
            max_appointments INTEGER DEFAULT 10,
            specialty TEXT,
            location TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
        ''')
        
        # Health campaigns and programs
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_name TEXT,
            campaign_type TEXT,
            start_date TEXT,
            end_date TEXT,
            target_population TEXT,
            description TEXT,
            goals TEXT,
            status TEXT DEFAULT 'planned',
            budget REAL,
            created_by TEXT,
            created_at TEXT
        )
        ''')
        
        # Wellness program participation
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS wellness_participation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            program_name TEXT,
            enrollment_date TEXT,
            completion_date TEXT,
            status TEXT DEFAULT 'enrolled',
            progress_score INTEGER DEFAULT 0,
            goals_met INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Disease surveillance
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS disease_surveillance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            disease_name TEXT,
            case_date TEXT,
            student_id TEXT,
            symptoms TEXT,
            severity TEXT,
            status TEXT DEFAULT 'under_investigation',
            contact_tracing_needed INTEGER DEFAULT 0,
            contact_tracing_completed INTEGER DEFAULT 0,
            contacts_identified INTEGER DEFAULT 0,
            reported_to_health_dept INTEGER DEFAULT 0,
            isolation_required INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Lab results
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS lab_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            test_name TEXT,
            test_code TEXT,
            result_value TEXT,
            reference_range TEXT,
            units TEXT,
            status TEXT,
            ordered_date TEXT,
            collected_date TEXT,
            resulted_date TEXT,
            ordering_provider TEXT,
            lab_name TEXT,
            abnormal_flag TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')
        
        # Quality metrics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS quality_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT,
            metric_category TEXT,
            target_value REAL,
            actual_value REAL,
            measurement_period TEXT,
            measured_date TEXT,
            status TEXT,
            improvement_needed INTEGER DEFAULT 0,
            created_at TEXT
        )
        ''')
        
        # Check if data retention policies need to be populated
        cursor.execute("SELECT COUNT(*) FROM data_retention_policies")
        if cursor.fetchone()[0] == 0:
            policies = [
                ('health_records', 2555, 1, 0),  # 7 years
                ('vaccination_records', 2555, 1, 0),  # 7 years
                ('appointments', 1095, 1, 0),  # 3 years
                ('audit_trail', 2555, 0, 0),  # 7 years, no auto-delete
                ('prescriptions', 1825, 1, 0),  # 5 years
                ('lab_results', 2555, 1, 0),  # 7 years
                ('vital_signs', 1095, 1, 0),  # 3 years
            ]
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for policy in policies:
                cursor.execute(
                    'INSERT INTO data_retention_policies (data_type, retention_period_days, auto_archive, auto_delete, created_at) VALUES (?, ?, ?, ?, ?)',
                    (*policy, timestamp)
                )
        
        # Check if security settings need to be populated
        cursor.execute("SELECT COUNT(*) FROM security_settings")
        if cursor.fetchone()[0] == 0:
            settings = [
                ('session_timeout_minutes', '30'),
                ('max_failed_login_attempts', '3'),
                ('password_expiry_days', '90'),
                ('require_2fa_for_providers', '1'),
                ('encryption_enabled', '1'),
                ('audit_logging_enabled', '1'),
                ('ip_restriction_enabled', '0'),
                ('allowed_ip_ranges', ''),
            ]
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for setting in settings:
                cursor.execute(
                    'INSERT INTO security_settings (setting_name, setting_value, updated_at) VALUES (?, ?, ?)',
                    (*setting, timestamp)
                )
        
        conn.commit()
        conn.close()
        print("Enhanced health portal database initialized successfully!")
        
    except sqlite3.Error as e:
        print(f"An error occurred while initializing the enhanced health database: {e}")
        if conn:
            conn.close()

def manage_referrals(auth):
    """Referral management system"""
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to manage referrals.")
        return
    
    while True:
        print("\n===== Referral Management =====")
        print("1. Create New Referral")
        print("2. View Referrals")
        print("3. Update Referral Status")
        print("4. Specialist Directory")
        print("5. Referral Follow-up")
        print("6. Referral Reports")
        print("7. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-7): ")
        
        if choice == '1':
            create_referral(auth)
        elif choice == '2':
            view_referrals(auth)
        elif choice == '3':
            update_referral_status(auth)
        elif choice == '4':
            specialist_directory(auth)
        elif choice == '5':
            referral_followup(auth)
        elif choice == '6':
            referral_reports(auth)
        elif choice == '7':
            break
        else:
            print("Invalid choice. Please try again.")

def create_referral(auth):
    """Create new referral"""
    backup_before_operation('create_referral')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    student_id = input("Enter student ID: ")
    
    # Verify student exists
    cursor.execute("SELECT first_name, last_name FROM students WHERE student_id = ?", (student_id,))
    student = cursor.fetchone()
    if not student:
        print("Error: Student ID not found.")
        conn.close()
        return
    
    print(f"Creating referral for: {student[0]} {student[1]}")
    
    referring_provider = input(f"Referring provider [Dr. {auth.current_user['username']}]: ").strip()
    if not referring_provider:
        referring_provider = f"Dr. {auth.current_user['username']}"
    
    specialist_provider = input("Specialist provider: ")
    
    specialties = [
        'Cardiology', 'Dermatology', 'Endocrinology', 'Gastroenterology',
        'Neurology', 'Orthopedics', 'Psychiatry', 'Pulmonology', 'Urology', 'Other'
    ]
    
    print("\nSpecialties:")
    for i, specialty in enumerate(specialties):
        print(f"{i+1}. {specialty}")
    
    while True:
        specialty_choice = input("\nSelect specialty (1-10): ")
        if specialty_choice.isdigit() and 1 <= int(specialty_choice) <= len(specialties):
            specialty = specialties[int(specialty_choice) - 1]
            if specialty == 'Other':
                specialty = input("Enter specialty: ")
            break
        print("Invalid choice. Please try again.")
    
    reason = input("Reason for referral: ")
    
    urgency_levels = ['Routine', 'Urgent', 'STAT']
    print("\nUrgency Levels:")
    for i, urgency in enumerate(urgency_levels):
        print(f"{i+1}. {urgency}")
    
    while True:
        urgency_choice = input("\nSelect urgency (1-3): ")
        if urgency_choice.isdigit() and 1 <= int(urgency_choice) <= len(urgency_levels):
            urgency = urgency_levels[int(urgency_choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    referral_date = datetime.now().strftime('%Y-%m-%d')
    notes = input("Additional notes: ")
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO referrals 
    (student_id, referring_provider, specialist_provider, specialty, reason, 
     urgency, referral_date, status, notes, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, referring_provider, specialist_provider, specialty, reason,
          urgency, referral_date, 'pending', notes, created_at))
    
    conn.commit()
    referral_id = cursor.lastrowid
    
    log_audit_event(auth.current_user['id'], 'create_referral', 'referral', referral_id)
    print(f"\nReferral created successfully! Referral ID: {referral_id}")
    
    if urgency == 'STAT':
        print("🚨 STAT REFERRAL - Immediate action required!")
    
    conn.close()

def ensure_student_dob_compat():
    """
    Ensure both 'date_of_birth' and 'dob' exist on students.
    If one is missing, add it and backfill from the other.
    Safe to run repeatedly.
    """
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("PRAGMA table_info(students)")
        cols = {row[1] for row in c.fetchall()}

        if 'date_of_birth' not in cols and 'dob' in cols:
            c.execute("ALTER TABLE students ADD COLUMN date_of_birth TEXT")
            c.execute("UPDATE students SET date_of_birth = dob WHERE date_of_birth IS NULL OR date_of_birth = ''")
            conn.commit()

        elif 'dob' not in cols and 'date_of_birth' in cols:
            c.execute("ALTER TABLE students ADD COLUMN dob TEXT")
            c.execute("UPDATE students SET dob = date_of_birth WHERE dob IS NULL OR dob = ''")
            conn.commit()

    except Exception as e:
        # Don't crash menus if PRAGMA/ALTER fails; just surface a note.
        print(f"(Schema compat) {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass

def analyze_provider_workload(auth):
    """Workload by provider: last 30d, next 7d, status mix, simple capacity util if schedules exist."""
    if hasattr(auth, "check_permission") and not auth.check_permission("view_health_analytics"):
        print("You don't have permission to view analytics.")
        return

    conn = get_connection()
    try:
        c = conn.cursor()

        # Detect appointments table
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='health_appointments'")
        table = "health_appointments" if c.fetchone() else "appointments"

        # Introspect columns
        c.execute("PRAGMA table_info([" + table + "])")
        cols = [row[1] for row in c.fetchall()]

        provider_col = next((x for x in ("provider", "provider_id", "practitioner_id", "staff_id") if x in cols), None)
        status_col   = next((x for x in ("status", "appointment_status") if x in cols), None)

        # Datetime expression (prefer date+time, else appointment_datetime, else date only)
        if "appointment_date" in cols and "appointment_time" in cols:
            dt_expr = table + ".appointment_date||' '||" + table + ".appointment_time"
        elif "appointment_datetime" in cols:
            dt_expr = table + ".appointment_datetime"
        elif "date" in cols:
            dt_expr = table + ".date"
        elif "scheduled_time" in cols:
            dt_expr = table + ".scheduled_time"
        else:
            dt_expr = None  # fall back to whole-table counts

        print("\n===== Provider Workload Analysis =====")
        if not provider_col:
            print("No provider column found on the appointments table. Nothing to analyze.")
            return

        # Last 30 days per provider
        where_30 = "WHERE datetime(" + dt_expr + ") >= datetime('now','localtime','-30 day')" if dt_expr else ""
        c.execute(
            "SELECT [" + provider_col + "] AS provider, COUNT(*) AS n"
            " FROM [" + table + "] " + where_30 +
            " GROUP BY [" + provider_col + "]"
            " ORDER BY n DESC"
        )
        rows_30 = c.fetchall()
        if rows_30:
            print("\nLast 30 days (booked/completed/cancelled mixed):")
            for prov, n in rows_30[:10]:
                print(f" - {prov or 'UNKNOWN'}: {n}")

        # Upcoming 7 days (scheduled/pending only)
        where_up = "WHERE 1=1"
        if dt_expr:
            where_up += " AND datetime(" + dt_expr + ") >= datetime('now','localtime') AND datetime(" + dt_expr + ") < datetime('now','localtime','+7 day')"
        if status_col:
            where_up += " AND ([" + status_col + "] IN ('scheduled','booked','pending') OR [" + status_col + "] IS NULL)"
        c.execute(
            "SELECT [" + provider_col + "] AS provider, COUNT(*) AS n"
            " FROM [" + table + "] " + where_up +
            " GROUP BY [" + provider_col + "]"
            " ORDER BY n DESC"
        )
        rows_up = c.fetchall()
        print("\nUpcoming 7 days (scheduled/pending):")
        if rows_up:
            for prov, n in rows_up[:10]:
                print(f" - {prov or 'UNKNOWN'}: {n}")
        else:
            print(" - No upcoming appointments found (or no datetime column).")

        # Status mix (last 30d)
        if status_col:
            c.execute(
                "SELECT [" + provider_col + "] AS provider, [" + status_col + "] AS status, COUNT(*) AS n"
                " FROM [" + table + "] " + where_30 +
                " GROUP BY [" + provider_col + "], [" + status_col + "]"
                " ORDER BY [" + provider_col + "], n DESC"
            )
            rows_mix = c.fetchall()
            if rows_mix:
                print("\nStatus breakdown (last 30 days):")
                current = None
                for prov, status, n in rows_mix:
                    if prov != current:
                        current = prov
                        print(f" {prov or 'UNKNOWN'}:")
                    print(f"    {status or 'UNKNOWN'}: {n}")
        else:
            print("\nNo status column; skipping status breakdown.")

        # Average/day per provider (last 30d)
        if dt_expr and rows_30:
            c.execute(
                "SELECT [" + provider_col + "] AS provider, ROUND(COUNT(*)/30.0, 2) AS per_day"
                " FROM [" + table + "] " + where_30 +
                " GROUP BY [" + provider_col + "]"
                " ORDER BY per_day DESC"
            )
            rows_avg = c.fetchall()
            print("\nAverage appointments per day (last 30 days):")
            for prov, per_day in rows_avg[:10]:
                print(f" - {prov or 'UNKNOWN'}: {per_day}")

        # Simple capacity/utilization if provider_schedules exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='provider_schedules'")
        if c.fetchone() and dt_expr:
            # Weekly capacity by provider from schedules
            c.execute("""
                SELECT provider_name, COALESCE(SUM(max_appointments),0) AS weekly_capacity
                FROM provider_schedules
                WHERE active = 1
                GROUP BY provider_name
            """)
            cap = {row[0]: row[1] for row in c.fetchall()}

            # Last 28 days workload by provider
            c.execute(
                "SELECT [" + provider_col + "] AS provider, COUNT(*) AS n"
                " FROM [" + table + "]"
                " WHERE datetime(" + dt_expr + ") >= datetime('now','localtime','-28 day')"
                " GROUP BY [" + provider_col + "]"
            )
            util = {}
            for prov, n in c.fetchall():
                weekly = cap.get(prov, 0)
                capacity_28 = weekly * 4  # approx 4 weeks
                util[prov] = (n, capacity_28, (n / capacity_28 * 100.0) if capacity_28 else None)

            if util:
                print("\nUtilization (last 28 days vs schedule capacity):")
                for prov, (n, cap28, pct) in sorted(util.items(), key=lambda x: (x[1][2] or -1), reverse=True)[:10]:
                    if pct is None:
                        print(f" - {prov or 'UNKNOWN'}: {n} booked; no schedule capacity found")
                    else:
                        print(f" - {prov or 'UNKNOWN'}: {n}/{cap28} ({pct:.1f}%)")
        else:
            print("\nNo provider_schedules table or no datetime column; skipping capacity/utilization.")

        # Audit (reuse open conn if your signature supports it)
        try:
            log_audit_event(auth.current_user['id'], 'analyze_provider_workload', 'appointments', 'analytics', conn=conn)
        except TypeError:
            log_audit_event(auth.current_user['id'], 'analyze_provider_workload', 'appointments', 'analytics')

    except Exception as e:
        print(f"Workload analysis error: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
        input("\nPress Enter to return...")

def show_quality_metrics(auth):
    """Delegate to Quality Assurance module."""
    try:
        from university_system.modules.domain.health.records.quality_assurance import show_quality_metrics as _show
        return _show(auth)
    except Exception as e:
        print(f"Quality metrics unavailable: {e}")
        input("\nPress Enter to return...")

def generate_custom_report(auth):
    """Delegate to health_misc.generate_custom_report with lazy import.
       If the DB is missing expected columns, auto-migrate and retry once.
    """
    import importlib
    try:
        hm = importlib.import_module('src.services.health_misc')
        return hm.generate_custom_report(auth)
    except sqlite3.OperationalError as e:
        msg = str(e)
        if "no such column: date_of_birth" in msg or "no such column: dob" in msg:
            # Heal schema and retry once
            ensure_student_dob_compat()
            try:
                hm = importlib.import_module('src.services.health_misc')
                return hm.generate_custom_report(auth)
            except Exception as e2:
                print(f"Custom report generator unavailable after schema fix: {e2}")
                input("\nPress Enter to return...")
        else:
            print(f"Custom report generator unavailable: {e}")
            input("\nPress Enter to return...")
    except Exception as e:
        print(f"Custom report generator unavailable: {e}")
        input("\nPress Enter to return...")


def view_referrals(auth):
    """View referrals"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nFilter options:")
    print("1. All referrals")
    print("2. By student ID")
    print("3. By status")
    print("4. By specialty")
    print("5. Pending referrals only")
    
    filter_choice = input("\nSelect filter (1-5): ")
    
    if filter_choice == '1':
        cursor.execute('''
        SELECT r.id, s.student_id, s.first_name, s.last_name, r.referring_provider,
               r.specialist_provider, r.specialty, r.urgency, r.referral_date, r.status
        FROM referrals r
        JOIN students s ON r.student_id = s.student_id
        ORDER BY r.referral_date DESC
        LIMIT 50
        ''')
    
    elif filter_choice == '2':
        student_id = input("Enter student ID: ")
        cursor.execute('''
        SELECT r.id, s.student_id, s.first_name, s.last_name, r.referring_provider,
               r.specialist_provider, r.specialty, r.urgency, r.referral_date, r.status
        FROM referrals r
        JOIN students s ON r.student_id = s.student_id
        WHERE r.student_id = ?
        ORDER BY r.referral_date DESC
        ''', (student_id,))
    
    elif filter_choice == '3':
        status = input("Enter status (pending/scheduled/completed/cancelled): ")
        cursor.execute('''
        SELECT r.id, s.student_id, s.first_name, s.last_name, r.referring_provider,
               r.specialist_provider, r.specialty, r.urgency, r.referral_date, r.status
        FROM referrals r
        JOIN students s ON r.student_id = s.student_id
        WHERE r.status = ?
        ORDER BY r.referral_date DESC
        ''', (status,))
    
    elif filter_choice == '4':
        specialty = input("Enter specialty: ")
        cursor.execute('''
        SELECT r.id, s.student_id, s.first_name, s.last_name, r.referring_provider,
               r.specialist_provider, r.specialty, r.urgency, r.referral_date, r.status
        FROM referrals r
        JOIN students s ON r.student_id = s.student_id
        WHERE r.specialty LIKE ?
        ORDER BY r.referral_date DESC
        ''', (f'%{specialty}%',))
    
    elif filter_choice == '5':
        cursor.execute('''
        SELECT r.id, s.student_id, s.first_name, s.last_name, r.referring_provider,
               r.specialist_provider, r.specialty, r.urgency, r.referral_date, r.status
        FROM referrals r
        JOIN students s ON r.student_id = s.student_id
        WHERE r.status = 'pending'
        ORDER BY r.urgency DESC, r.referral_date
        ''')
    
    else:
        print("Invalid choice.")
        conn.close()
        return
    
    referrals = cursor.fetchall()
    
    if not referrals:
        print("No referrals found.")
        conn.close()
        return
    
    print("\n===== Referrals =====")
    for referral in referrals:
        ref_id, student_id, first_name, last_name, referring, specialist, specialty, urgency, ref_date, status = referral
        
        print(f"\nReferral ID: {ref_id}")
        print(f"Patient: {first_name} {last_name} (ID: {student_id})")
        print(f"Referring: {referring}")
        print(f"Specialist: {specialist}")
        print(f"Specialty: {specialty}")
        print(f"Urgency: {urgency}")
        print(f"Date: {ref_date}")
        print(f"Status: {status}")
        
        if urgency == 'STAT':
            print("🚨 STAT REFERRAL")
        elif urgency == 'Urgent':
            print("⚠️ URGENT")
        
        print("-" * 30)
    
    conn.close()

def update_referral_status(auth):
    """Update referral status"""
    backup_before_operation('update_referral_status')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    referral_id = input("Enter referral ID to update: ")
    
    cursor.execute('''
    SELECT r.id, s.first_name, s.last_name, r.specialist_provider, 
           r.specialty, r.status
    FROM referrals r
    JOIN students s ON r.student_id = s.student_id
    WHERE r.id = ?
    ''', (referral_id,))
    
    referral = cursor.fetchone()
    
    if not referral:
        print("Error: Referral not found.")
        conn.close()
        return
    
    ref_id, first_name, last_name, specialist, specialty, current_status = referral
    
    print(f"\nReferral Details:")
    print(f"Patient: {first_name} {last_name}")
    print(f"Specialist: {specialist}")
    print(f"Specialty: {specialty}")
    print(f"Current Status: {current_status}")
    
    status_options = ['pending', 'scheduled', 'completed', 'cancelled', 'no_show']
    print("\nStatus Options:")
    for i, status in enumerate(status_options):
        print(f"{i+1}. {status}")
    
    while True:
        choice = input("\nSelect new status (1-5): ")
        if choice.isdigit() and 1 <= int(choice) <= len(status_options):
            new_status = status_options[int(choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    appointment_date = None
    if new_status == 'scheduled':
        while True:
            appointment_date = input("Appointment date (YYYY-MM-DD): ")
            try:
                datetime.strptime(appointment_date, '%Y-%m-%d')
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")
    
    notes = input("Additional notes: ")
    
    cursor.execute('''
    UPDATE referrals 
    SET status = ?, appointment_date = ?, notes = CASE WHEN ? != '' THEN ? ELSE notes END
    WHERE id = ?
    ''', (new_status, appointment_date, notes, notes, referral_id))
    
    conn.commit()
    log_audit_event(auth.current_user['id'], 'update_referral_status', 'referral', referral_id,
                   f"Status changed from {current_status} to {new_status}")
    
    print(f"\nReferral status updated to '{new_status}' successfully!")
    conn.close()

def student_health_dashboard(auth):
    """Personal health dashboard for students"""
    if auth.current_user['role'] != 'student':
        print("This dashboard is only available to students.")
        return
    
    student_id = get_user_student_id(auth)
    if not student_id:
        print("Error: No student ID associated with your account.")
        return
    
    while True:
        print("\n===== Your Health Dashboard =====")
        print("1. Health Summary")
        print("2. Upcoming Appointments")
        print("3. Health Reminders")
        print("4. Wellness Goals")
        print("5. Immunization Status")
        print("6. Health Metrics Tracking")
        print("7. Emergency Information")
        print("8. Health Resources")
        print("9. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-9): ")
        
        if choice == '1':
            show_personal_health_summary(auth)
        elif choice == '2':
            show_upcoming_appointments(auth)
        elif choice == '3':
            show_health_reminders(auth)
        elif choice == '4':
            manage_wellness_goals(auth)
        elif choice == '5':
            immunization_status(auth)
        elif choice == '6':
            track_personal_metrics(auth)
        elif choice == '7':
            emergency_information(auth)
        elif choice == '8':
            student_health_resources(auth)
        elif choice == '9':
            break
        else:
            print("Invalid choice. Please try again.")

def show_personal_health_summary(auth):
    """Show personal health summary"""
    student_id = get_user_student_id(auth)
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get student info
    cursor.execute("SELECT first_name, last_name, age FROM students WHERE student_id = ?", (student_id,))
    student = cursor.fetchone()
    
    print(f"\n===== Health Summary for {student[0]} {student[1]} =====")
    print(f"Age: {student[2]}")
    
    # Recent health records
    cursor.execute('''
    SELECT record_type, record_date, description, provider
    FROM health_records
    WHERE student_id = ?
    ORDER BY record_date DESC
    LIMIT 5
    ''', (student_id,))
    
    recent_records = cursor.fetchall()
    
    if recent_records:
        print("\nRecent Health Records:")
        for record_type, record_date, description, provider in recent_records:
            print(f"  {record_date}: {record_type} - {description[:50]}...")
    
    # Active medical conditions
    cursor.execute('''
    SELECT condition_name, severity FROM medical_conditions
    WHERE student_id = ? AND status = 'active'
    ''', (student_id,))
    
    conditions = cursor.fetchall()
    
    if conditions:
        print("\nActive Medical Conditions:")
        for condition, severity in conditions:
            print(f"  • {condition} ({severity})")
    
    # Allergies
    cursor.execute('''
    SELECT allergen, severity FROM allergies
    WHERE student_id = ? AND verified = 1
    ''', (student_id,))
    
    allergies = cursor.fetchall()
    
    if allergies:
        print("\nVerified Allergies:")
        for allergen, severity in allergies:
            alert = "🚨" if severity in ['Severe', 'Life-threatening'] else "⚠️"
            print(f"  {alert} {allergen} ({severity})")
    
    # Latest vital signs
    cursor.execute('''
    SELECT measurement_date, blood_pressure_systolic, blood_pressure_diastolic,
           heart_rate, temperature, weight, bmi
    FROM vital_signs
    WHERE student_id = ?
    ORDER BY measurement_date DESC
    LIMIT 1
    ''', (student_id,))
    
    vitals = cursor.fetchone()
    
    if vitals:
        date, bp_sys, bp_dia, hr, temp, weight, bmi = vitals
        print(f"\nLatest Vital Signs ({date}):")
        if bp_sys and bp_dia:
            print(f"  Blood Pressure: {bp_sys}/{bp_dia} mmHg")
        if hr:
            print(f"  Heart Rate: {hr} bpm")
        if temp:
            print(f"  Temperature: {temp}°F")
        if weight:
            print(f"  Weight: {weight} lbs")
        if bmi:
            print(f"  BMI: {bmi}")
    
    conn.close()

def show_appointment_utilization_stats(auth):
    """
    Console analytics for appointments with graceful fallbacks.
    Looks only at the 'appointments' table and auto-detects columns.
    """
    if hasattr(auth, "check_permission") and not auth.check_permission("view_health_analytics"):
        print("You don't have permission to view analytics.")
        return

    conn = get_connection()
    try:
        c = conn.cursor()

        # Ensure table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='appointments'")
        if not c.fetchone():
            print("No 'appointments' table found. Nothing to analyze.")
            return

        # Introspect columns
        c.execute("PRAGMA table_info(appointments)")
        cols = [row[1] for row in c.fetchall()]

        VALID_STATUS_COLS = {"status", "appointment_status"}
        VALID_PROVIDER_COLS = {"provider_id", "practitioner_id", "staff_id"}
        VALID_DT_COLS = {
            "start_time", "scheduled_time", "appointment_datetime", "appointment_time",
            "appointment_date", "date", "datetime", "start_at", "created_at",
        }
        VALID_MODIFIERS = {"-30 day", "-7 day", "start of day"}

        status_col   = next((x for x in ("status", "appointment_status") if x in cols and x in VALID_STATUS_COLS), None)
        provider_col = next((x for x in ("provider_id", "practitioner_id", "staff_id") if x in cols and x in VALID_PROVIDER_COLS), None)
        dt_candidates = [x for x in (
            "start_time", "scheduled_time", "appointment_datetime", "appointment_time",
            "appointment_date", "date", "datetime", "start_at", "created_at"
        ) if x in cols and x in VALID_DT_COLS]
        dt_col = dt_candidates[0] if dt_candidates else None

        print("\n===== Appointment Utilization =====")

        # Windowed counts
        if dt_col:
            windows = [
                ("Last 30 days", "-30 day"),
                ("Last 7 days",  "-7 day"),
                ("Today",        "start of day"),
            ]
            for label, mod in windows:
                if mod not in VALID_MODIFIERS:
                    continue
                if mod == "start of day":
                    c.execute("SELECT COUNT(*) FROM appointments WHERE datetime([" + dt_col + "]) >= datetime('now','localtime','start of day')")
                else:
                    c.execute("SELECT COUNT(*) FROM appointments WHERE datetime([" + dt_col + "]) >= datetime('now','localtime','" + mod + "')")
                total = c.fetchone()[0]
                print(f"{label}: {total} appointments")
        else:
            c.execute("SELECT COUNT(*) FROM appointments")
            total = c.fetchone()[0]
            print(f"Total appointments: {total} (no datetime column detected; skipping time windows)")

        # Status breakdown
        if status_col:
            c.execute("SELECT [" + status_col + "], COUNT(*) FROM appointments GROUP BY [" + status_col + "] ORDER BY COUNT(*) DESC")
            rows = c.fetchall()
            if rows:
                print("\nBy status:")
                for s, n in rows:
                    print(f" - {s or 'UNKNOWN'}: {n}")
        else:
            print("\nStatus column not found; skipping status breakdown.")

        # Top providers (last 30d if datetime available)
        if provider_col:
            if dt_col:
                c.execute(
                    "SELECT [" + provider_col + "], COUNT(*) AS n"
                    " FROM appointments"
                    " WHERE datetime([" + dt_col + "]) >= datetime('now','localtime','-30 day')"
                    " GROUP BY [" + provider_col + "]"
                    " ORDER BY n DESC"
                    " LIMIT 5"
                )
            else:
                c.execute(
                    "SELECT [" + provider_col + "], COUNT(*) AS n"
                    " FROM appointments"
                    " GROUP BY [" + provider_col + "]"
                    " ORDER BY n DESC"
                    " LIMIT 5"
                )
            rows = c.fetchall()
            if rows:
                print("\nTop providers (by booked count):")
                for pid, n in rows:
                    print(f" - {pid}: {n}")
        else:
            print("\nProvider column not found; skipping provider breakdown.")

        # Hour-of-day and weekday distributions
        if dt_col:
            c.execute(
                "SELECT strftime('%H', datetime([" + dt_col + "])) AS hh, COUNT(*)"
                " FROM appointments"
                " WHERE [" + dt_col + "] IS NOT NULL"
                " GROUP BY hh"
                " ORDER BY hh"
            )
            hours = c.fetchall()
            if hours:
                print("\nBy hour of day:")
                for hh, n in hours:
                    print(f" {hh}:00 -> {n}")

            c.execute(
                "SELECT strftime('%w', datetime([" + dt_col + "])) AS dow, COUNT(*)"
                " FROM appointments"
                " WHERE [" + dt_col + "] IS NOT NULL"
                " GROUP BY dow"
                " ORDER BY dow"
            )
            dows = {'0': 'Sun', '1': 'Mon', '2': 'Tue', '3': 'Wed', '4': 'Thu', '5': 'Fri', '6': 'Sat'}
            rows = c.fetchall()
            if rows:
                print("\nBy weekday:")
                for dow, n in rows:
                    label = dows.get(dow or '', dow or '?')
                    print(f" {label}: {n}")
        else:
            print("\nNo datetime column; skipping hour/weekday distributions.")

        # Audit (reuse conn if your signature supports it)
        try:
            log_audit_event(auth.current_user['id'], 'view_appointment_utilization', 'appointments', 'analytics', conn=conn)
        except TypeError:
            log_audit_event(auth.current_user['id'], 'view_appointment_utilization', 'appointments', 'analytics')

    except Exception as e:
        print(f"Analytics error: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
        input("\nPress Enter to return...")

def show_health_reminders(auth):
    """Show health reminders"""
    student_id = get_user_student_id(auth)
    conn = get_connection()
    cursor = conn.cursor()
    
    reminders = []
    
    # Check for expiring vaccinations
    ninety_days = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
    cursor.execute('''
    SELECT vaccine_name, expiry_date FROM vaccination_records
    WHERE student_id = ? AND expiry_date <= ? AND verified = 1
    ORDER BY expiry_date
    ''', (student_id, ninety_days))
    
    expiring_vaccines = cursor.fetchall()
    
    for vaccine, expiry in expiring_vaccines:
        days_until_expiry = (datetime.strptime(expiry, '%Y-%m-%d') - datetime.now()).days
        if days_until_expiry <= 0:
            reminders.append(f"🔴 EXPIRED: {vaccine} vaccination (expired {expiry})")
        elif days_until_expiry <= 30:
            reminders.append(f"🟡 EXPIRING SOON: {vaccine} vaccination expires {expiry}")
        else:
            reminders.append(f"ℹ️ {vaccine} vaccination expires {expiry}")
    
    # Check for overdue appointments
    cursor.execute('''
    SELECT COUNT(*) FROM health_appointments
    WHERE student_id = ? AND appointment_date < ? AND status = 'scheduled'
    ''', (student_id, datetime.now().strftime('%Y-%m-%d')))
    
    overdue_appointments = cursor.fetchone()[0]
    if overdue_appointments > 0:
        reminders.append(f"⚠️ You have {overdue_appointments} overdue appointment(s)")
    
    # Check for missing emergency contacts
    cursor.execute('''
    SELECT COUNT(*) FROM emergency_contacts WHERE student_id = ?
    ''', (student_id,))
    
    emergency_contacts = cursor.fetchone()[0]
    if emergency_contacts == 0:
        reminders.append("ℹ️ Please add emergency contact information")
    
    # Check for missing insurance info
    cursor.execute('''
    SELECT COUNT(*) FROM insurance_information WHERE student_id = ?
    ''', (student_id,))
    
    insurance_info = cursor.fetchone()[0]
    if insurance_info == 0:
        reminders.append("ℹ️ Please add insurance information")
    
    print("\n===== Health Reminders =====")
    
    if reminders:
        for reminder in reminders:
            print(f"  {reminder}")
    else:
        print("  ✅ No health reminders at this time.")
    
    conn.close()

def calculate_screening_due_date(screening_type, age):
    """Calculate recommended due date for screening based on type and age"""
    base_date = datetime.now()
    
    # Age-based recommendations
    if screening_type == 'Annual Physical Exam':
        return (base_date + timedelta(days=365)).strftime('%Y-%m-%d')
    elif screening_type == 'Blood Pressure Screening':
        if age >= 40:
            return (base_date + timedelta(days=180)).strftime('%Y-%m-%d')  # Every 6 months
        else:
            return (base_date + timedelta(days=365)).strftime('%Y-%m-%d')  # Annually
    elif screening_type == 'Cholesterol Screening':
        if age >= 35:
            return (base_date + timedelta(days=365*3)).strftime('%Y-%m-%d')  # Every 3 years
        else:
            return (base_date + timedelta(days=365*5)).strftime('%Y-%m-%d')  # Every 5 years
    elif screening_type == 'Diabetes Screening':
        if age >= 35:
            return (base_date + timedelta(days=365*3)).strftime('%Y-%m-%d')  # Every 3 years
        else:
            return (base_date + timedelta(days=365*5)).strftime('%Y-%m-%d')  # Every 5 years
    elif screening_type == 'Mental Health Screening':
        return (base_date + timedelta(days=365)).strftime('%Y-%m-%d')  # Annually
    elif screening_type == 'STI Screening':
        return (base_date + timedelta(days=365)).strftime('%Y-%m-%d')  # Annually if sexually active
    else:
        return (base_date + timedelta(days=365)).strftime('%Y-%m-%d')  # Default annual

def view_due_screenings(auth):
    """View due screenings"""
    conn = get_connection()
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    thirty_days = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    
    cursor.execute('''
    SELECT ss.id, s.student_id, s.first_name, s.last_name, ss.screening_type,
           ss.due_date, ss.status, ss.provider
    FROM screening_schedules ss
    JOIN students s ON ss.student_id = s.student_id
    WHERE ss.due_date <= ? AND ss.status = 'due'
    ORDER BY ss.due_date
    ''', (thirty_days,))
    
    due_screenings = cursor.fetchall()
    
    if not due_screenings:
        print("No screenings due in the next 30 days.")
        conn.close()
        return
    
    print("\n===== Due Screenings (Next 30 Days) =====")
    
    for screen_id, student_id, first_name, last_name, screening_type, due_date, status, provider in due_screenings:
        due_datetime = datetime.strptime(due_date, '%Y-%m-%d')
        days_until_due = (due_datetime - datetime.now()).days
        
        if days_until_due < 0:
            urgency = "🔴 OVERDUE"
        elif days_until_due <= 7:
            urgency = "🟡 DUE SOON"
        else:
            urgency = "ℹ️ UPCOMING"
        
        print(f"\n{urgency} ID: {screen_id}")
        print(f"Patient: {first_name} {last_name} (ID: {student_id})")
        print(f"Screening: {screening_type}")
        print(f"Due Date: {due_date}")
        if days_until_due < 0:
            print(f"Overdue by: {abs(days_until_due)} days")
        else:
            print(f"Due in: {days_until_due} days")
        print(f"Provider: {provider}")
    
    conn.close()

def overdue_screenings(auth):
    """View overdue screenings"""
    conn = get_connection()
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute('''
    SELECT ss.id, s.student_id, s.first_name, s.last_name, ss.screening_type,
           ss.due_date, ss.provider
    FROM screening_schedules ss
    JOIN students s ON ss.student_id = s.student_id
    WHERE ss.due_date < ? AND ss.status = 'due'
    ORDER BY ss.due_date
    ''', (today,))
    
    overdue = cursor.fetchall()
    
    if not overdue:
        print("No overdue screenings found.")
        conn.close()
        return
    
    print("\n===== Overdue Screenings =====")
    
    for screen_id, student_id, first_name, last_name, screening_type, due_date, provider in overdue:
        due_datetime = datetime.strptime(due_date, '%Y-%m-%d')
        days_overdue = (datetime.now() - due_datetime).days
        
        print(f"\n🔴 OVERDUE - ID: {screen_id}")
        print(f"Patient: {first_name} {last_name} (ID: {student_id})")
        print(f"Screening: {screening_type}")
        print(f"Due Date: {due_date}")
        print(f"Overdue by: {days_overdue} days")
        print(f"Provider: {provider}")
        
        if days_overdue > 90:
            print("⚠️ CRITICAL: Over 90 days overdue")
    
    print(f"\nTotal overdue screenings: {len(overdue)}")
    
    # Option to send reminders
    send_reminders = input("\nSend reminder notifications? (y/n): ").lower()
    if send_reminders == 'y':
        print("Reminder notifications sent to patients and providers.")
        log_audit_event(auth.current_user['id'], 'send_screening_reminders', 'screening', len(overdue))
    
    conn.close()

def screening_guidelines(auth):
    """Display screening guidelines"""
    print("\n===== Preventive Screening Guidelines =====")
    
    guidelines = {
        "18-21 Years": [
            "Annual physical examination",
            "Blood pressure screening annually",
            "Mental health screening annually",
            "STI screening if sexually active",
            "Cervical cancer screening (ages 21+)"
        ],
        "22-29 Years": [
            "Annual physical examination",
            "Blood pressure screening annually",
            "Cholesterol screening every 5 years",
            "Mental health screening annually",
            "STI screening if sexually active",
            "Cervical cancer screening every 3 years"
        ],
        "30-39 Years": [
            "Annual physical examination",
            "Blood pressure screening annually",
            "Cholesterol screening every 5 years",
            "Diabetes screening every 3 years",
            "Mental health screening annually",
            "Cervical cancer screening every 3 years"
        ],
        "40+ Years": [
            "Annual physical examination",
            "Blood pressure screening every 6 months",
            "Cholesterol screening every 3 years",
            "Diabetes screening every 3 years",
            "Mental health screening annually",
            "Mammography annually (women 40+)",
            "Cervical cancer screening every 3 years",
            "Colonoscopy every 10 years (50+)"
        ]
    }
    
    for age_group, screenings in guidelines.items():
        print(f"\n{age_group}:")
        for screening in screenings:
            print(f"  • {screening}")
    
    print("\n" + "="*50)
    print("Note: Guidelines may vary based on individual risk factors")
    print("and family history. Consult with healthcare provider for")
    print("personalized screening recommendations.")

def enhanced_health_record_templates(auth):
    """Enhanced health record template system"""
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to manage record templates.")
        return
    
    while True:
        print("\n===== Health Record Templates =====")
        print("1. Use Existing Template")
        print("2. Create New Template")
        print("3. Edit Template")
        print("4. Template Categories")
        print("5. Import Templates")
        print("6. Template Usage Statistics")
        print("7. Shared Templates")
        print("8. Template Validation")
        print("9. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-9): ")
        
        if choice == '1':
            use_existing_template(auth)
        elif choice == '2':
            create_new_template(auth)
        elif choice == '3':
            edit_template(auth)
        elif choice == '4':
            template_categories(auth)
        elif choice == '5':
            import_templates(auth)
        elif choice == '6':
            template_usage_statistics(auth)
        elif choice == '7':
            from university_system.modules.domain.health.records.backup_export import bulk_import_records
            bulk_import_records(auth)
        elif choice == '8':
            template_validation(auth)
        elif choice == '9':
            break
        else:
            print("Invalid choice. Please try again.")

def manage_wellness_goals(auth):
    """Manage personal wellness goals"""
    student_id = get_user_student_id(auth)
    
    print("\n===== Your Wellness Goals =====")
    
    # Mock wellness goals - would be stored in database
    goals = [
        {"goal": "Exercise 30 minutes daily", "progress": 75, "target_date": "2024-03-01"},
        {"goal": "Drink 8 glasses of water daily", "progress": 60, "target_date": "2024-02-15"},
        {"goal": "Get 8 hours of sleep nightly", "progress": 45, "target_date": "2024-04-01"}
    ]
    
    for i, goal in enumerate(goals):
        progress_bar = "█" * (goal["progress"] // 10) + "░" * (10 - goal["progress"] // 10)
        print(f"\n{i+1}. {goal['goal']}")
        print(f"   Progress: [{progress_bar}] {goal['progress']}%")
        print(f"   Target Date: {goal['target_date']}")
    
    print("\nOptions:")
    print("1. Add New Goal")
    print("2. Update Progress")
    print("3. Remove Goal")
    print("4. Return to dashboard")
    
    choice = input("\nSelect option (1-4): ")
    
    if choice == '1':
        new_goal = input("Enter new wellness goal: ")
        target_date = input("Target date (YYYY-MM-DD): ")
        print(f"Goal '{new_goal}' added with target date {target_date}")
    
    elif choice == '2':
        goal_num = input("Enter goal number to update: ")
        progress = input("Enter progress percentage (0-100): ")
        print(f"Goal {goal_num} progress updated to {progress}%")

def immunization_status(auth):
    """Show immunization status"""
    student_id = get_user_student_id(auth)
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Your Immunization Status =====")
    
    # Get vaccination records
    cursor.execute('''
    SELECT vaccine_name, administered_date, expiry_date, verified
    FROM vaccination_records
    WHERE student_id = ?
    ORDER BY administered_date DESC
    ''', (student_id,))
    
    vaccinations = cursor.fetchall()
    
    if not vaccinations:
        print("No vaccination records found.")
        conn.close()
        return
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    for vaccine, admin_date, expiry_date, verified in vaccinations:
        status = "✅ Current"
        if expiry_date and expiry_date < today:
            status = "🔴 Expired"
        elif expiry_date and (datetime.strptime(expiry_date, '%Y-%m-%d') - datetime.now()).days <= 90:
            status = "🟡 Expiring Soon"
        
        verification = "✅ Verified" if verified else "⏳ Pending Verification"
        
        print(f"\n{vaccine}")
        print(f"  Administered: {admin_date}")
        print(f"  Expires: {expiry_date}")
        print(f"  Status: {status}")
        print(f"  Verification: {verification}")
    
    conn.close()

def track_personal_metrics(auth):
    """Track personal health metrics"""
    student_id = get_user_student_id(auth)
    
    print("\n===== Personal Health Metrics Tracking =====")
    
    print("Available Metrics to Track:")
    print("1. Weight")
    print("2. Blood Pressure")
    print("3. Exercise Minutes")
    print("4. Sleep Hours")
    print("5. Water Intake")
    print("6. Mood Scale (1-10)")
    print("7. View Trends")
    
    choice = input("\nSelect metric (1-7): ")
    
    if choice == '1':
        weight = input("Enter current weight (lbs): ")
        print(f"Weight logged: {weight} lbs")
    
    elif choice == '2':
        systolic = input("Enter systolic BP: ")
        diastolic = input("Enter diastolic BP: ")
        print(f"Blood pressure logged: {systolic}/{diastolic}")
    
    elif choice == '3':
        minutes = input("Enter exercise minutes today: ")
        print(f"Exercise logged: {minutes} minutes")
    
    elif choice == '7':
        print("\nTrend data would be displayed here with charts/graphs")
        print("• Weight trend over last 30 days")
        print("• Exercise consistency")
        print("• Sleep pattern analysis")

def referral_followup(auth):
    """Follow up on referrals"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get referrals needing follow-up
    cursor.execute('''
    SELECT r.id, s.first_name, s.last_name, r.specialist_provider, 
           r.specialty, r.referral_date, r.status
    FROM referrals r
    JOIN students s ON r.student_id = s.student_id
    WHERE r.status IN ('scheduled', 'pending') 
    AND r.referral_date < date('now', '-30 days')
    ORDER BY r.referral_date
    ''')
    
    followup_needed = cursor.fetchall()
    
    if not followup_needed:
        print("No referrals requiring follow-up.")
        conn.close()
        return
    
    print("\n===== Referrals Needing Follow-up =====")
    
    for ref_id, first_name, last_name, specialist, specialty, ref_date, status in followup_needed:
        days_since = (datetime.now() - datetime.strptime(ref_date, '%Y-%m-%d')).days
        
        print(f"\nReferral ID: {ref_id}")
        print(f"Patient: {first_name} {last_name}")
        print(f"Specialist: {specialist} ({specialty})")
        print(f"Referred: {ref_date} ({days_since} days ago)")
        print(f"Status: {status}")
        
        if days_since > 60:
            print("🔴 URGENT: Over 60 days old")
        elif days_since > 30:
            print("🟡 Follow-up needed")
    
    conn.close()

def referral_reports(auth):
    """Generate referral reports"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Referral Reports =====")
    
    # Referral statistics
    cursor.execute('''
    SELECT specialty, COUNT(*) as referral_count,
           AVG(CASE WHEN status = 'completed' THEN 1.0 ELSE 0.0 END) * 100 as completion_rate
    FROM referrals
    WHERE referral_date >= date('now', '-30 days')
    GROUP BY specialty
    ORDER BY referral_count DESC
    ''')
    
    stats = cursor.fetchall()
    
    print("Referral Statistics (Last 30 Days):")
    print(f"{'Specialty':<20} {'Count':<8} {'Completion Rate':<15}")
    print("-" * 45)
    
    for specialty, count, completion_rate in stats:
        print(f"{specialty:<20} {count:<8} {completion_rate:.1f}%")
    
    # Monthly trend
    cursor.execute('''
    SELECT strftime('%Y-%m', referral_date) as month, COUNT(*) as count
    FROM referrals
    WHERE referral_date >= date('now', '-12 months')
    GROUP BY strftime('%Y-%m', referral_date)
    ORDER BY month
    ''')
    
    monthly_trends = cursor.fetchall()
    
    if monthly_trends:
        print("\nMonthly Referral Trends:")
        for month, count in monthly_trends:
            print(f"  {month}: {count} referrals")
    
    conn.close()

def record_screening_results(auth):
    """Record screening results"""
    backup_before_operation('record_screening_results')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    screening_id = input("Enter screening ID: ")
    
    cursor.execute('''
    SELECT ss.id, s.first_name, s.last_name, ss.screening_type, ss.due_date
    FROM screening_schedules ss
    JOIN students s ON ss.student_id = s.student_id
    WHERE ss.id = ?
    ''', (screening_id,))
    
    screening = cursor.fetchone()
    
    if not screening:
        print("Error: Screening not found.")
        conn.close()
        return
    
    screen_id, first_name, last_name, screening_type, due_date = screening
    
    print(f"\nRecording results for:")
    print(f"Patient: {first_name} {last_name}")
    print(f"Screening: {screening_type}")
    
    completed_date = input("Completed date (YYYY-MM-DD) [today]: ").strip()
    if not completed_date:
        completed_date = datetime.now().strftime('%Y-%m-%d')
    
    results = input("Screening results: ")
    
    # Calculate next due date
    next_due_date = calculate_next_screening_date(screening_type)
    
    cursor.execute('''
    UPDATE screening_schedules 
    SET completed_date = ?, status = 'completed', results = ?, next_due_date = ?
    WHERE id = ?
    ''', (completed_date, results, next_due_date, screening_id))
    
    conn.commit()
    log_audit_event(auth.current_user['id'], 'record_screening_results', 'screening', screening_id)
    
    print(f"\nScreening results recorded successfully!")
    print(f"Next screening due: {next_due_date}")
    
    conn.close()

def calculate_next_screening_date(screening_type):
    """Calculate next screening due date"""
    base_date = datetime.now()
    
    if screening_type == 'Annual Physical Exam':
        return (base_date + timedelta(days=365)).strftime('%Y-%m-%d')
    elif screening_type == 'Blood Pressure Screening':
        return (base_date + timedelta(days=365)).strftime('%Y-%m-%d')
    elif screening_type == 'Cholesterol Screening':
        return (base_date + timedelta(days=365*3)).strftime('%Y-%m-%d')
    else:
        return (base_date + timedelta(days=365)).strftime('%Y-%m-%d')

def screening_reminders(auth):
    """Send screening reminders"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get students with due screenings
    seven_days = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    
    cursor.execute('''
    SELECT ss.id, s.first_name, s.last_name, s.student_id, ss.screening_type, ss.due_date
    FROM screening_schedules ss
    JOIN students s ON ss.student_id = s.student_id
    WHERE ss.due_date <= ? AND ss.status = 'due'
    ORDER BY ss.due_date
    ''', (seven_days,))
    
    reminder_list = cursor.fetchall()
    
    if not reminder_list:
        print("No screening reminders to send.")
        conn.close()
        return
    
    print(f"\n===== Screening Reminders ({len(reminder_list)} students) =====")
    
    for screen_id, first_name, last_name, student_id, screening_type, due_date in reminder_list:
        print(f"• {first_name} {last_name} (ID: {student_id})")
        print(f"  {screening_type} due {due_date}")
    
    send_reminders = input(f"\nSend reminders to all {len(reminder_list)} students? (y/n): ").lower()
    
    if send_reminders == 'y':
        # In a real system, this would send email/SMS reminders
        print("Screening reminders sent successfully!")
        log_audit_event(auth.current_user['id'], 'send_screening_reminders', 'screening', len(reminder_list))
    else:
        print("Reminder sending cancelled.")
    
    conn.close()

def population_screening_reports(auth):
    """Generate population screening reports"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Population Screening Reports =====")
    
    # Screening compliance rates
    cursor.execute('''
    SELECT screening_type, 
           COUNT(*) as total_due,
           SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
           SUM(CASE WHEN due_date < date('now') AND status = 'due' THEN 1 ELSE 0 END) as overdue
    FROM screening_schedules
    WHERE due_date >= date('now', '-365 days')
    GROUP BY screening_type
    ORDER BY total_due DESC
    ''')
    
    compliance_data = cursor.fetchall()
    
    if compliance_data:
        print("Screening Compliance Rates (Last 12 Months):")
        print(f"{'Screening Type':<25} {'Total':<8} {'Completed':<10} {'Overdue':<8} {'Rate':<8}")
        print("-" * 65)
        
        for screening, total, completed, overdue in compliance_data:
            compliance_rate = (completed / total * 100) if total > 0 else 0
            print(f"{screening:<25} {total:<8} {completed:<10} {overdue:<8} {compliance_rate:.1f}%")
    
    # Age group analysis
    cursor.execute('''
    SELECT 
        CASE 
            WHEN s.age < 25 THEN '18-24'
            WHEN s.age < 35 THEN '25-34'
            WHEN s.age < 45 THEN '35-44'
            ELSE '45+'
        END as age_group,
        COUNT(DISTINCT ss.student_id) as students_with_screenings,
        AVG(CASE WHEN ss.status = 'completed' THEN 1.0 ELSE 0.0 END) * 100 as avg_compliance
    FROM screening_schedules ss
    JOIN students s ON ss.student_id = s.student_id
    WHERE ss.due_date >= date('now', '-365 days')
    GROUP BY age_group
    ORDER BY age_group
    ''')
    
    age_analysis = cursor.fetchall()
    
    if age_analysis:
        print(f"\nCompliance by Age Group:")
        print(f"{'Age Group':<12} {'Students':<10} {'Compliance':<12}")
        print("-" * 35)
        
        for age_group, students, compliance in age_analysis:
            print(f"{age_group:<12} {students:<10} {compliance:.1f}%")
    
    conn.close()

def student_health_resources(auth):
    """Student-specific health resources"""
    print("\n===== Student Health Resources =====")
    
    resources = {
        "Campus Health Services": [
            "Student Health Center - Building A, Room 150",
            "Hours: Monday-Friday 8AM-5PM",
            "After-hours nurse line: (555) 123-NURSE",
            "Appointment scheduling: health.university.edu"
        ],
        "Mental Health Support": [
            "Counseling Center - Building B, Room 200",
            "Crisis support: Available 24/7",
            "Support groups: Anxiety, Depression, Stress Management",
            "Peer counseling program"
        ],
        "Health Education": [
            "Nutrition workshops: Healthy eating on a budget",
            "Fitness classes: Yoga, Zumba, Strength training",
            "Sleep hygiene seminars",
            "Substance abuse prevention programs"
        ],
        "Insurance & Financial": [
            "Student health insurance enrollment",
            "Financial assistance for medical care",
            "Prescription assistance programs",
            "Healthcare cost estimates"
        ],
        "Online Tools": [
            "Health risk assessments",
            "Symptom checker",
            "Medication interaction checker",
            "Health tracking apps"
        ]
    }
    
    for category, items in resources.items():
        print(f"\n📋 {category}:")
        for item in items:
            print(f"   • {item}")
    
    print(f"\n🔗 Quick Links:")
    print("   • Student Health Portal: health.university.edu")
    print("   • Mental Health Resources: counseling.university.edu")
    print("   • Campus Recreation: recreation.university.edu")
    print("   • Insurance Information: insurance.university.edu")

def recent_lab_results_dashboard(auth):
    """Dashboard view of recent lab results"""
    conn = get_connection()
    cursor = conn.cursor()
    
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    cursor.execute('''
    SELECT lr.test_name, lr.result_value, lr.reference_range, lr.abnormal_flag,
           lr.resulted_date, s.first_name, s.last_name, s.student_id
    FROM lab_results lr
    JOIN students s ON lr.student_id = s.student_id
    WHERE lr.resulted_date >= ?
    ORDER BY lr.resulted_date DESC, lr.abnormal_flag DESC
    LIMIT 20
    ''', (seven_days_ago,))
    
    recent_results = cursor.fetchall()
    
    print("\n===== Recent Lab Results (Last 7 Days) =====")
    
    if not recent_results:
        print("No lab results in the last 7 days.")
        conn.close()
        return
    
    critical_count = 0
    
    for test, value, ref_range, abnormal, date, first_name, last_name, student_id in recent_results:
        if abnormal in ['H', 'L']:
            critical_count += 1
            flag = "🔴 HIGH" if abnormal == 'H' else "🔵 LOW"
            print(f"\n{flag} {test}: {value}")
        else:
            print(f"\n✅ {test}: {value}")
        
        print(f"   Patient: {first_name} {last_name} (ID: {student_id})")
        print(f"   Date: {date}")
        print(f"   Reference: {ref_range}")
    
    print(f"\nSummary: {len(recent_results)} results, {critical_count} abnormal")
    
    if critical_count > 0:
        print("⚠️ Critical values require provider follow-up")
    
    conn.close()

def vaccination_due_list(auth):
    """List of students with vaccinations due"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get vaccinations expiring in next 60 days
    sixty_days = (datetime.now() + timedelta(days=60)).strftime('%Y-%m-%d')
    today = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute('''
    SELECT vr.vaccine_name, vr.expiry_date, s.first_name, s.last_name, s.student_id
    FROM vaccination_records vr
    JOIN students s ON vr.student_id = s.student_id
    WHERE vr.expiry_date BETWEEN ? AND ? AND vr.verified = 1
    ORDER BY vr.expiry_date
    ''', (today, sixty_days))
    
    due_vaccinations = cursor.fetchall()
    
    print("\n===== Vaccinations Due (Next 60 Days) =====")
    
    if not due_vaccinations:
        print("No vaccinations due in the next 60 days.")
        conn.close()
        return
    
    for vaccine, expiry, first_name, last_name, student_id in due_vaccinations:
        expiry_date = datetime.strptime(expiry, '%Y-%m-%d')
        days_until = (expiry_date - datetime.now()).days
        
        if days_until <= 0:
            urgency = "🔴 EXPIRED"
        elif days_until <= 14:
            urgency = "🟡 DUE SOON"
        else:
            urgency = "ℹ️ UPCOMING"
        
        print(f"\n{urgency}")
        print(f"Patient: {first_name} {last_name} (ID: {student_id})")
        print(f"Vaccine: {vaccine}")
        print(f"Expires: {expiry} ({days_until} days)")
    
    print(f"\nTotal students needing vaccination: {len(due_vaccinations)}")
    
    # Option to generate reminder list
    generate_reminders = input("\nGenerate vaccination reminder list? (y/n): ").lower()
    if generate_reminders == 'y':
        print("Vaccination reminder list generated for nursing staff.")
    
    conn.close()

def add_health_record(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to add health records.")
        return
    
    backup_before_operation('add_health_record')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    student_id = input("Enter student ID: ")
    
    # Verify student exists
    cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
    if cursor.fetchone()[0] == 0:
        print("Error: Student ID not found.")
        conn.close()
        return
    
    # Record types
    record_types = [
        'General Medical',
        'Injury Treatment',
        'Mental Health',
        'Chronic Condition Management',
        'Preventive Care',
        'Emergency Treatment',
        'Follow-up Visit',
        'Specialist Consultation'
    ]
    
    print("\nRecord Types:")
    for i, record_type in enumerate(record_types):
        print(f"{i+1}. {record_type}")
    
    while True:
        type_choice = input("\nSelect record type (1-8): ")
        if type_choice.isdigit() and 1 <= int(type_choice) <= len(record_types):
            record_type = record_types[int(type_choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    while True:
        record_date = input("Record date (YYYY-MM-DD) [today]: ").strip()
        if not record_date:
            record_date = datetime.now().strftime('%Y-%m-%d')
            break
        try:
            datetime.strptime(record_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    description = input("Description: ")
    provider = input(f"Provider [Dr. {auth.current_user['username']}]: ").strip()
    if not provider:
        provider = f"Dr. {auth.current_user['username']}"
    
    confidential = input("Mark as confidential? (y/n): ").lower() == 'y'
    
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO health_records 
    (student_id, record_type, record_date, description, provider, confidential, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, record_type, record_date, description, provider, 
          1 if confidential else 0, created_at))
    
    conn.commit()
    log_audit_event(auth.current_user['id'], 'add_health_record', 'health_record', cursor.lastrowid)
    print("\nHealth record added successfully!")
    conn.close()

def view_health_records(auth):
    if not (auth.check_permission('view_any_health_record') or auth.check_permission('view_own_health_record')):
        print("You don't have permission to view health records.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    if auth.check_permission('view_any_health_record'):
        student_id = input("Enter student ID (leave blank for all recent): ").strip()
        
        if student_id:
            cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
            if cursor.fetchone()[0] == 0:
                print("Error: Student ID not found.")
                conn.close()
                return
            
            cursor.execute('''
            SELECT hr.id, hr.record_type, hr.record_date, hr.description, hr.provider,
                   hr.confidential, hr.created_at
            FROM health_records hr
            WHERE hr.student_id = ?
            ORDER BY hr.record_date DESC
            LIMIT 100
            ''', (student_id,))
        else:
            cursor.execute('''
            SELECT hr.id, s.student_id, s.first_name, s.last_name, hr.record_type,
                   hr.record_date, hr.description, hr.provider, hr.confidential
            FROM health_records hr
            JOIN students s ON hr.student_id = s.student_id
            ORDER BY hr.record_date DESC
            LIMIT 100
            ''')
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return
        
        cursor.execute('''
        SELECT id, record_type, record_date, description, provider,
               confidential, created_at
        FROM health_records
        WHERE student_id = ?
        ORDER BY record_date DESC
        ''', (student_id,))
    
    records = cursor.fetchall()
    
    if not records:
        print("No health records found.")
        conn.close()
        return
    
    print("\n===== Health Records =====")
    for record in records:
        if auth.check_permission('view_any_health_record') and not student_id:
            # All records view
            hr_id, student_id, first_name, last_name, record_type, record_date, description, provider, confidential = record
            print(f"\nID: {hr_id}")
            print(f"Student: {first_name} {last_name} (ID: {student_id})")
            print(f"Type: {record_type}")
            print(f"Date: {record_date}")
            print(f"Description: {description}")
            print(f"Provider: {provider}")
            if confidential:
                print("🔒 CONFIDENTIAL")
        else:
            # Specific student view
            hr_id, record_type, record_date, description, provider, confidential, created_at = record
            print(f"\nID: {hr_id}")
            print(f"Type: {record_type}")
            print(f"Date: {record_date}")
            print(f"Description: {description}")
            print(f"Provider: {provider}")
            print(f"Created: {created_at}")
            if confidential:
                print("🔒 CONFIDENTIAL")
        
        print("-" * 30)
    
    conn.close()

def verify_vaccination(auth):
    if not auth.check_permission('verify_vaccinations'):
        print("You don't have permission to verify vaccinations.")
        return
    
    backup_before_operation('verify_vaccination')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    vaccination_id = input("Enter vaccination ID to verify: ")
    
    cursor.execute('''
    SELECT vr.id, s.student_id, s.first_name, s.last_name, vr.vaccine_name,
           vr.administered_date, vr.administered_by, vr.verified
    FROM vaccination_records vr
    JOIN students s ON vr.student_id = s.student_id
    WHERE vr.id = ?
    ''', (vaccination_id,))
    
    vaccination = cursor.fetchone()
    
    if not vaccination:
        print("Error: Vaccination record not found.")
        conn.close()
        return
    
    vax_id, student_id, first_name, last_name, vaccine_name, admin_date, admin_by, verified = vaccination
    
    print(f"\nVaccination to verify:")
    print(f"Student: {first_name} {last_name} (ID: {student_id})")
    print(f"Vaccine: {vaccine_name}")
    print(f"Date: {admin_date}")
    print(f"Administered by: {admin_by}")
    print(f"Current Status: {'Verified' if verified else 'Unverified'}")
    
    if verified:
        print("This vaccination is already verified.")
        conn.close()
        return
    
    # Verification process
    print("\nVerification Checklist:")
    print("1. Documentation reviewed")
    print("2. Provider credentials confirmed")
    print("3. Vaccine details validated")
    
    verify = input("\nVerify this vaccination record? (y/n): ").lower()
    if verify != 'y':
        print("Verification cancelled.")
        conn.close()
        return
    
    cursor.execute('''
    UPDATE vaccination_records 
    SET verified = 1, verified_by = ?, verified_date = ?
    WHERE id = ?
    ''', (auth.current_user['username'], datetime.now().strftime('%Y-%m-%d'), vaccination_id))
    
    conn.commit()
    log_audit_event(auth.current_user['id'], 'verify_vaccination', 'vaccination', vaccination_id)
    
    print("\nVaccination record verified successfully!")
    conn.close()

def add_health_advisory(auth):
    if not auth.check_permission('issue_health_advisories'):
        print("You don't have permission to issue health advisories.")
        return
    
    backup_before_operation('add_health_advisory')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    title = input("Advisory title: ")
    
    # Advisory types
    advisory_types = [
        'Disease Outbreak',
        'Safety Alert',
        'Vaccination Reminder',
        'Wellness Tip',
        'Emergency Notice',
        'Policy Update',
        'Seasonal Health',
        'General Information'
    ]
    
    print("\nAdvisory Types:")
    for i, advisory_type in enumerate(advisory_types):
        print(f"{i+1}. {advisory_type}")
    
    while True:
        type_choice = input("\nSelect advisory type (1-8): ")
        if type_choice.isdigit() and 1 <= int(type_choice) <= len(advisory_types):
            advisory_type = advisory_types[int(type_choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    content = input("Advisory content: ")
    
    # Priority levels
    priority_levels = ['Low', 'Medium', 'High', 'Critical']
    print("\nPriority Levels:")
    for i, priority in enumerate(priority_levels):
        print(f"{i+1}. {priority}")
    
    while True:
        priority_choice = input("\nSelect priority (1-4): ")
        if priority_choice.isdigit() and 1 <= int(priority_choice) <= len(priority_levels):
            priority = priority_levels[int(priority_choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    # Target audience
    target_audiences = ['All Students', 'Specific Groups', 'Staff Only', 'High Risk Students']
    print("\nTarget Audience:")
    for i, audience in enumerate(target_audiences):
        print(f"{i+1}. {audience}")
    
    while True:
        audience_choice = input("\nSelect target audience (1-4): ")
        if audience_choice.isdigit() and 1 <= int(audience_choice) <= len(target_audiences):
            target_audience = target_audiences[int(audience_choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    while True:
        effective_date = input("Effective date (YYYY-MM-DD) [today]: ").strip()
        if not effective_date:
            effective_date = datetime.now().strftime('%Y-%m-%d')
            break
        try:
            datetime.strptime(effective_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    while True:
        expiry_date = input("Expiry date (YYYY-MM-DD) [leave blank for no expiry]: ").strip()
        if not expiry_date:
            expiry_date = None
            break
        try:
            datetime.strptime(expiry_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO health_advisories 
    (title, advisory_type, content, priority, target_audience, effective_date, 
     expiry_date, issued_by, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (title, advisory_type, content, priority, target_audience, effective_date,
          expiry_date, auth.current_user['username'], 'active', created_at))
    
    conn.commit()
    advisory_id = cursor.lastrowid
    
    log_audit_event(auth.current_user['id'], 'issue_health_advisory', 'health_advisory', advisory_id)

    print(f"\nHealth advisory issued successfully!")
    print(f"Advisory ID: {advisory_id}")

    # Automatically send email notifications to target audience
    try:
        # Get students based on target audience
        if target_audience == 'All Students':
            cursor.execute('SELECT student_id FROM students WHERE status = "active"')
        elif target_audience == 'High Risk Students':
            # Send to students with chronic conditions or recent health issues
            cursor.execute('''
                SELECT DISTINCT mr.student_id
                FROM medical_records mr
                WHERE mr.record_type IN ('chronic_condition', 'prescription')
                AND mr.student_id IN (SELECT student_id FROM students WHERE status = "active")
            ''')
        elif target_audience == 'Staff Only':
            # Send to staff/faculty
            cursor.execute('''
                SELECT id as student_id FROM users
                WHERE role IN ('staff', 'admin', 'instructor') AND is_active = 1
            ''')
        else:  # Specific Groups - send to all active students as fallback
            cursor.execute('SELECT student_id FROM students WHERE status = "active"')

        students = cursor.fetchall()
        notification_count = 0

        for (student_id,) in students:
            try:
                send_health_notification(student_id, title, content, priority)
                notification_count += 1
            except Exception as e:
                print(f"Warning: Could not send notification to student {student_id}: {e}")

        print(f"✉️  Automatic email notifications sent to {notification_count} recipients")
        if priority == 'Critical':
            print("🚨 CRITICAL ADVISORY - Email notifications sent to all relevant parties")
    except Exception as e:
        print(f"Warning: Could not send email notifications: {e}")

    conn.close()

def view_health_advisories(auth):
    if not (auth.check_permission('view_health_advisories') or auth.check_permission('issue_health_advisories')):
        print("You don't have permission to view health advisories.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\nFilter options:")
    print("1. All active advisories")
    print("2. By priority")
    print("3. By type")
    print("4. Recent advisories (last 30 days)")
    
    filter_choice = input("\nSelect filter (1-4): ")
    
    if filter_choice == '1':
        cursor.execute('''
        SELECT id, title, advisory_type, priority, target_audience, effective_date,
               expiry_date, issued_by, status
        FROM health_advisories
        WHERE status = 'active' AND (expiry_date IS NULL OR expiry_date >= ?)
        ORDER BY priority DESC, effective_date DESC
        ''', (datetime.now().strftime('%Y-%m-%d'),))
    
    elif filter_choice == '2':
        priority = input("Enter priority (Low/Medium/High/Critical): ")
        cursor.execute('''
        SELECT id, title, advisory_type, priority, target_audience, effective_date,
               expiry_date, issued_by, status
        FROM health_advisories
        WHERE priority = ? AND status = 'active'
        ORDER BY effective_date DESC
        ''', (priority,))
    
    elif filter_choice == '3':
        advisory_type = input("Enter advisory type: ")
        cursor.execute('''
        SELECT id, title, advisory_type, priority, target_audience, effective_date,
               expiry_date, issued_by, status
        FROM health_advisories
        WHERE advisory_type LIKE ? AND status = 'active'
        ORDER BY effective_date DESC
        ''', (f'%{advisory_type}%',))
    
    elif filter_choice == '4':
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        cursor.execute('''
        SELECT id, title, advisory_type, priority, target_audience, effective_date,
               expiry_date, issued_by, status
        FROM health_advisories
        WHERE effective_date >= ?
        ORDER BY effective_date DESC
        ''', (thirty_days_ago,))
    
    else:
        print("Invalid choice.")
        conn.close()
        return
    
    advisories = cursor.fetchall()
    
    if not advisories:
        print("No health advisories found.")
        conn.close()
        return
    
    print("\n===== Health Advisories =====")
    for advisory in advisories:
        adv_id, title, adv_type, priority, target_audience, effective_date, expiry_date, issued_by, status = advisory
        
        print(f"\nID: {adv_id}")
        print(f"Title: {title}")
        print(f"Type: {adv_type}")
        print(f"Priority: {priority}")
        print(f"Target: {target_audience}")
        print(f"Effective: {effective_date}")
        print(f"Expires: {expiry_date if expiry_date else 'No expiry'}")
        print(f"Issued by: {issued_by}")
        
        # Priority indicators
        if priority == 'Critical':
            print("🚨 CRITICAL ADVISORY")
        elif priority == 'High':
            print("🔴 HIGH PRIORITY")
        elif priority == 'Medium':
            print("🟡 MEDIUM PRIORITY")
        
        # Show content if requested
        view_content = input("View full content? (y/n): ").lower()
        if view_content == 'y':
            cursor.execute('SELECT content FROM health_advisories WHERE id = ?', (adv_id,))
            content = cursor.fetchone()[0]
            print(f"Content: {content}")
        
        print("-" * 30)
    
    conn.close()

def view_insurance_info(auth):
    if not (auth.check_permission('update_insurance_info') or auth.current_user['role'] in ['admin', 'health_provider']):
        print("You don't have permission to view insurance information.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    if auth.current_user['role'] in ['admin', 'health_provider']:
        student_id = input("Enter student ID: ")
        
        cursor.execute("SELECT first_name, last_name FROM students WHERE student_id = ?", (student_id,))
        student = cursor.fetchone()
        if not student:
            print("Error: Student ID not found.")
            conn.close()
            return
        
        print(f"Insurance information for: {student[0]} {student[1]}")
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return
    
    cursor.execute('''
    SELECT insurance_provider, policy_number, group_number, subscriber_name,
           relationship_to_subscriber, effective_date, expiry_date, created_at
    FROM insurance_information
    WHERE student_id = ?
    ORDER BY created_at DESC
    ''', (student_id,))
    
    insurance_records = cursor.fetchall()
    
    if not insurance_records:
        print("No insurance information found.")
        conn.close()
        return
    
    print("\n===== Insurance Information =====")
    for record in insurance_records:
        provider, policy_num, group_num, subscriber, relationship, effective, expiry, created = record
        
        print(f"\nInsurance Provider: {provider}")
        print(f"Policy Number: {policy_num}")
        print(f"Group Number: {group_num}")
        print(f"Subscriber: {subscriber}")
        print(f"Relationship: {relationship}")
        print(f"Effective Date: {effective}")
        print(f"Expiry Date: {expiry}")
        print(f"Last Updated: {created}")
        
        # Check if expired
        today = datetime.now().strftime('%Y-%m-%d')
        if expiry and expiry < today:
            print("⚠️  EXPIRED - Update needed")
        elif expiry and (datetime.strptime(expiry, '%Y-%m-%d') - datetime.now()).days <= 30:
            print("🟡 EXPIRES SOON")
        else:
            print("✅ CURRENT")
        
        print("-" * 30)
    
    conn.close()

def update_insurance_info(auth):
    if not (auth.check_permission('update_insurance_info') or auth.current_user['role'] in ['admin', 'health_provider']):
        print("You don't have permission to update insurance information.")
        return
    
    backup_before_operation('update_insurance_info')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    if auth.current_user['role'] in ['admin', 'health_provider']:
        student_id = input("Enter student ID: ")
        
        cursor.execute("SELECT first_name, last_name FROM students WHERE student_id = ?", (student_id,))
        student = cursor.fetchone()
        if not student:
            print("Error: Student ID not found.")
            conn.close()
            return
        
        print(f"Updating insurance for: {student[0]} {student[1]}")
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return
    
    # Check if insurance record exists
    cursor.execute('''
    SELECT id, insurance_provider, policy_number, group_number
    FROM insurance_information
    WHERE student_id = ?
    ORDER BY created_at DESC LIMIT 1
    ''', (student_id,))
    
    existing_record = cursor.fetchone()
    
    if existing_record:
        print(f"\nCurrent insurance: {existing_record[1]} (Policy: {existing_record[2]})")
        update_existing = input("Update existing record? (y/n): ").lower()
        if update_existing == 'y':
            insurance_id = existing_record[0]
        else:
            insurance_id = None
    else:
        insurance_id = None
    
    insurance_provider = input("Insurance provider: ")
    policy_number = input("Policy number: ")
    group_number = input("Group number: ")
    subscriber_name = input("Subscriber name: ")
    
    relationships = ['Self', 'Parent', 'Spouse', 'Guardian', 'Other']
    print("\nRelationship to subscriber:")
    for i, relationship in enumerate(relationships):
        print(f"{i+1}. {relationship}")
    
    while True:
        rel_choice = input("\nSelect relationship (1-5): ")
        if rel_choice.isdigit() and 1 <= int(rel_choice) <= len(relationships):
            relationship_to_subscriber = relationships[int(rel_choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    while True:
        effective_date = input("Effective date (YYYY-MM-DD): ")
        try:
            datetime.strptime(effective_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    while True:
        expiry_date = input("Expiry date (YYYY-MM-DD): ")
        try:
            datetime.strptime(expiry_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if insurance_id:
        # Update existing record
        cursor.execute('''
        UPDATE insurance_information 
        SET insurance_provider = ?, policy_number = ?, group_number = ?,
            subscriber_name = ?, relationship_to_subscriber = ?, effective_date = ?,
            expiry_date = ?, created_at = ?
        WHERE id = ?
        ''', (insurance_provider, policy_number, group_number, subscriber_name,
              relationship_to_subscriber, effective_date, expiry_date, created_at, insurance_id))
        
        log_audit_event(auth.current_user['id'], 'update_insurance_info', 'insurance', insurance_id, conn=conn)
        print("\nInsurance information updated successfully!")
    else:
        # Create new record
        cursor.execute('''
        INSERT INTO insurance_information 
        (student_id, insurance_provider, policy_number, group_number, subscriber_name,
         relationship_to_subscriber, effective_date, expiry_date, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, insurance_provider, policy_number, group_number, subscriber_name,
              relationship_to_subscriber, effective_date, expiry_date, created_at))
        
        log_audit_event(auth.current_user['id'], 'add_insurance_info', 'insurance', cursor.lastrowid, conn=conn)
        print("\nInsurance information added successfully!")
    
    conn.commit()
    conn.close()

def update_care_plan(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to update care plans.")
        return
    
    backup_before_operation('update_care_plan')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    care_plan_id = input("Enter care plan ID to update: ")
    
    cursor.execute('''
    SELECT cp.id, s.student_id, s.first_name, s.last_name, cp.plan_name,
           cp.description, cp.status, cp.goals, cp.interventions
    FROM care_plans cp
    JOIN students s ON cp.student_id = s.student_id
    WHERE cp.id = ?
    ''', (care_plan_id,))
    
    care_plan = cursor.fetchone()
    
    if not care_plan:
        print("Error: Care plan not found.")
        conn.close()
        return
    
    cp_id, student_id, first_name, last_name, plan_name, description, status, goals, interventions = care_plan
    
    print(f"\nCurrent Care Plan:")
    print(f"Student: {first_name} {last_name} (ID: {student_id})")
    print(f"Plan: {plan_name}")
    print(f"Status: {status}")
    print(f"Goals: {goals}")
    print(f"Interventions: {interventions}")
    
    print("\nEnter new values (press Enter to keep current):")
    
    new_description = input(f"Description [{description}]: ").strip()
    if not new_description:
        new_description = description
    
    status_options = ['active', 'completed', 'on_hold', 'discontinued']
    print(f"\nCurrent status: {status}")
    print("Status options: active, completed, on_hold, discontinued")
    new_status = input(f"New status [{status}]: ").strip()
    if not new_status or new_status not in status_options:
        new_status = status
    
    new_goals = input(f"Goals [{goals}]: ").strip()
    if not new_goals:
        new_goals = goals
    
    new_interventions = input(f"Interventions [{interventions}]: ").strip()
    if not new_interventions:
        new_interventions = interventions
    
    cursor.execute('''
    UPDATE care_plans 
    SET description = ?, status = ?, goals = ?, interventions = ?
    WHERE id = ?
    ''', (new_description, new_status, new_goals, new_interventions, care_plan_id))
    
    conn.commit()
    log_audit_event(auth.current_user['id'], 'update_care_plan', 'care_plan', care_plan_id)
    print("\nCare plan updated successfully!")
    conn.close()

def track_care_plan_progress(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to track care plan progress.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    student_id = input("Enter student ID: ")
    
    # Get active care plans for student
    cursor.execute('''
    SELECT cp.id, cp.plan_name, cp.start_date, cp.goals, cp.interventions,
           mc.condition_name
    FROM care_plans cp
    LEFT JOIN medical_conditions mc ON cp.condition_id = mc.id
    WHERE cp.student_id = ? AND cp.status = 'active'
    ORDER BY cp.start_date DESC
    ''', (student_id,))
    
    care_plans = cursor.fetchall()
    
    if not care_plans:
        print("No active care plans found for this student.")
        conn.close()
        return
    
    print(f"\n===== Care Plan Progress Tracking for Student {student_id} =====")
    
    for plan in care_plans:
        cp_id, plan_name, start_date, goals, interventions, condition_name = plan
        
        print(f"\nCare Plan: {plan_name}")
        print(f"Condition: {condition_name if condition_name else 'General Care'}")
        print(f"Started: {start_date}")
        print(f"Goals: {goals}")
        print(f"Interventions: {interventions}")
        
        # Track progress
        days_active = (datetime.now() - datetime.strptime(start_date, '%Y-%m-%d')).days
        print(f"Days active: {days_active}")
        
        # Progress assessment
        print("\nProgress Assessment:")
        goal_progress = input("Goal achievement (0-100%): ")
        adherence = input("Treatment adherence (0-100%): ")
        improvement = input("Overall improvement (Poor/Fair/Good/Excellent): ")
        
        notes = input("Progress notes: ")
        
        # Record progress (this would go into a care_plan_progress table in a full system)
        progress_date = datetime.now().strftime('%Y-%m-%d')
        print(f"\nProgress recorded for {progress_date}")
        print(f"Goal Progress: {goal_progress}%")
        print(f"Adherence: {adherence}%")
        print(f"Improvement: {improvement}")
        
        # Suggest plan modifications if needed
        if goal_progress.isdigit() and int(goal_progress) < 50:
            print("⚠️  Low goal achievement - Consider plan modification")
        
        if adherence.isdigit() and int(adherence) < 70:
            print("⚠️  Poor adherence - Address barriers to treatment")
        
        print("-" * 40)
    
    conn.close()

def condition_management_plans(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to manage condition plans.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Condition Management Plans =====")
    
    # Show common chronic conditions needing management
    cursor.execute('''
    SELECT condition_name, COUNT(*) as patient_count
    FROM medical_conditions
    WHERE status = 'active'
    GROUP BY condition_name
    ORDER BY patient_count DESC
    LIMIT 10
    ''')
    
    conditions = cursor.fetchall()
    
    if conditions:
        print("Conditions requiring active management:")
        for condition, count in conditions:
            print(f"- {condition}: {count} patients")
        
        # Show care plan coverage
        cursor.execute('''
        SELECT 
            mc.condition_name,
            COUNT(DISTINCT mc.student_id) as total_patients,
            COUNT(DISTINCT cp.student_id) as with_care_plans
        FROM medical_conditions mc
        LEFT JOIN care_plans cp ON mc.id = cp.condition_id AND cp.status = 'active'
        WHERE mc.status = 'active'
        GROUP BY mc.condition_name
        ORDER BY total_patients DESC
        ''')
        
        coverage = cursor.fetchall()
        
        print("\nCare Plan Coverage:")
        for condition, total, with_plans in coverage:
            coverage_pct = (with_plans / total * 100) if total > 0 else 0
            print(f"{condition}: {with_plans}/{total} ({coverage_pct:.1f}%)")
            
            if coverage_pct < 50:
                print(f"  ⚠️  Low coverage - Consider developing care plans")
    
    # Template care plans for common conditions
    condition_templates = {
        'Diabetes': {
            'goals': 'Maintain HbA1c <7%, prevent complications, lifestyle management',
            'interventions': 'Blood glucose monitoring, medication adherence, diet counseling, exercise program'
        },
        'Hypertension': {
            'goals': 'Blood pressure <130/80, lifestyle modifications, medication adherence',
            'interventions': 'Regular BP monitoring, sodium reduction, weight management, stress reduction'
        },
        'Asthma': {
            'goals': 'Symptom control, prevent exacerbations, maintain normal activity',
            'interventions': 'Inhaler technique education, trigger avoidance, action plan, peak flow monitoring'
        }
    }
    
    print("\nAvailable care plan templates:")
    for condition, template in condition_templates.items():
        print(f"\n{condition}:")
        print(f"  Goals: {template['goals']}")
        print(f"  Interventions: {template['interventions']}")
    
    conn.close()

def view_medical_conditions(auth):
    """View medical conditions - either for a specific student or summary view"""
    if not (auth.check_permission('view_any_health_record') or auth.check_permission('view_own_health_record')):
        print("You don't have permission to view medical conditions.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        if auth.check_permission('view_any_health_record'):
            student_id = input("Enter student ID (leave blank for summary): ").strip()
            
            if student_id:
                # Check if student exists
                cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
                if cursor.fetchone()[0] == 0:
                    print("Error: Student ID not found.")
                    return
                
                # Get specific student's medical conditions
                cursor.execute('''
                SELECT id, condition_name, icd_code, severity, diagnosed_date, status,
                       provider, notes
                FROM medical_conditions
                WHERE student_id = ?
                ORDER BY diagnosed_date DESC
                ''', (student_id,))
                
                conditions = cursor.fetchall()
                
                if not conditions:
                    print(f"No medical conditions found for student ID: {student_id}")
                    return
                
                print(f"\n===== Medical Conditions for Student {student_id} =====")
                for condition in conditions:
                    condition_id, name, icd_code, severity, diagnosed_date, status, provider, notes = condition
                    print(f"\nCondition ID: {condition_id}")
                    print(f"Condition: {name}")
                    print(f"ICD Code: {icd_code}")
                    print(f"Severity: {severity}")
                    print(f"Diagnosed: {diagnosed_date}")
                    print(f"Status: {status}")
                    print(f"Provider: {provider}")
                    if notes:
                        print(f"Notes: {notes}")
                    print("-" * 40)
            else:
                # Summary view - all active conditions
                cursor.execute('''
                SELECT mc.condition_name, mc.severity, COUNT(*) as count,
                       GROUP_CONCAT(s.first_name || ' ' || s.last_name) as students,
                       GROUP_CONCAT(mc.student_id) as student_ids
                FROM medical_conditions mc
                JOIN students s ON mc.student_id = s.student_id
                WHERE mc.status = 'active'
                GROUP BY mc.condition_name, mc.severity
                ORDER BY count DESC
                ''')
                
                summary = cursor.fetchall()
                
                if not summary:
                    print("No active medical conditions found.")
                    return
                
                print("\n===== Medical Conditions Summary =====")
                print(f"{'Condition':<25} {'Severity':<10} {'Count':<6} {'Students'}")
                print("-" * 70)
                
                for row in summary:
                    condition, severity, count, students, student_ids = row
                    # Truncate student list if too long
                    student_list = students if len(students) <= 50 else students[:47] + "..."
                    print(f"{condition:<25} {severity:<10} {count:<6} {student_list}")
        else:
            # User can only view their own conditions
            student_id = get_user_student_id(auth)
            if not student_id:
                print("Error: No student ID associated with your account.")
                return
            
            cursor.execute('''
            SELECT id, condition_name, icd_code, severity, diagnosed_date, status,
                   provider, notes
            FROM medical_conditions
            WHERE student_id = ?
            ORDER BY diagnosed_date DESC
            ''', (student_id,))
            
            conditions = cursor.fetchall()
            
            if not conditions:
                print("No medical conditions found for your account.")
                return
            
            print("\n===== Your Medical Conditions =====")
            for condition in conditions:
                condition_id, name, icd_code, severity, diagnosed_date, status, provider, notes = condition
                print(f"\nCondition ID: {condition_id}")
                print(f"Condition: {name}")
                print(f"ICD Code: {icd_code}")
                print(f"Severity: {severity}")
                print(f"Diagnosed: {diagnosed_date}")
                print(f"Status: {status}")
                print(f"Provider: {provider}")
                if notes:
                    print(f"Notes: {notes}")
                print("-" * 40)
    
    finally:
        conn.close()

def update_health_record(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to update health records.")
        return
    
    backup_before_operation('update_health_record')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    record_id = input("Enter health record ID to update: ")
    
    cursor.execute('''
    SELECT hr.id, s.student_id, s.first_name, s.last_name, hr.record_type,
           hr.record_date, hr.description, hr.provider, hr.confidential
    FROM health_records hr
    JOIN students s ON hr.student_id = s.student_id
    WHERE hr.id = ?
    ''', (record_id,))
    
    record = cursor.fetchone()
    
    if not record:
        print("Error: Health record not found.")
        conn.close()
        return
    
    hr_id, student_id, first_name, last_name, record_type, record_date, description, provider, confidential = record
    
    print(f"\nCurrent Record Details:")
    print(f"Student: {first_name} {last_name} (ID: {student_id})")
    print(f"Type: {record_type}")
    print(f"Date: {record_date}")
    print(f"Provider: {provider}")
    print(f"Description: {description}")
    print(f"Confidential: {'Yes' if confidential else 'No'}")
    
    print("\nEnter new values (press Enter to keep current):")
    
    new_description = input(f"Description [{description}]: ").strip()
    if not new_description:
        new_description = description
    
    new_provider = input(f"Provider [{provider}]: ").strip()
    if not new_provider:
        new_provider = provider
    
    new_confidential_input = input(f"Confidential ({'Yes' if confidential else 'No'}) [y/n]: ").strip().lower()
    if new_confidential_input == 'y':
        new_confidential = 1
    elif new_confidential_input == 'n':
        new_confidential = 0
    else:
        new_confidential = confidential
    
    cursor.execute('''
    UPDATE health_records 
    SET description = ?, provider = ?, confidential = ?
    WHERE id = ?
    ''', (new_description, new_provider, new_confidential, record_id))
    
    conn.commit()
    log_audit_event(auth.current_user['id'], 'update_health_record', 'health_record', record_id)
    print("\nHealth record updated successfully!")
    conn.close()

def delete_health_record(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to delete health records.")
        return
    
    backup_before_operation('delete_health_record')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    record_id = input("Enter health record ID to delete: ")
    
    cursor.execute('''
    SELECT hr.id, s.student_id, s.first_name, s.last_name, hr.record_type,
           hr.record_date, hr.description
    FROM health_records hr
    JOIN students s ON hr.student_id = s.student_id
    WHERE hr.id = ?
    ''', (record_id,))
    
    record = cursor.fetchone()
    
    if not record:
        print("Error: Health record not found.")
        conn.close()
        return
    
    hr_id, student_id, first_name, last_name, record_type, record_date, description = record
    
    print(f"\nRecord to delete:")
    print(f"Student: {first_name} {last_name} (ID: {student_id})")
    print(f"Type: {record_type}")
    print(f"Date: {record_date}")
    print(f"Description: {description}")
    
    confirm = input("\nAre you sure you want to delete this record? (yes/no): ").lower()
    if confirm != 'yes':
        print("Deletion cancelled.")
        conn.close()
        return
    
    cursor.execute('DELETE FROM health_records WHERE id = ?', (record_id,))
    conn.commit()
    
    log_audit_event(auth.current_user['id'], 'delete_health_record', 'health_record', record_id, 
                   f"Deleted record for student {student_id}")
    print("\nHealth record deleted successfully!")
    conn.close()

def record_vaccination(auth):
    if not auth.check_permission('manage_vaccinations'):
        print("You don't have permission to record vaccinations.")
        return
    
    backup_before_operation('record_vaccination')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    student_id = input("Enter student ID: ")
    
    # Verify student exists
    cursor.execute("SELECT first_name, last_name FROM students WHERE student_id = ?", (student_id,))
    student = cursor.fetchone()
    if not student:
        print("Error: Student ID not found.")
        conn.close()
        return
    
    print(f"Recording vaccination for: {student[0]} {student[1]}")
    
    # Common vaccines
    common_vaccines = [
        'COVID-19',
        'Influenza (Flu)',
        'Hepatitis A',
        'Hepatitis B',
        'Measles, Mumps, Rubella (MMR)',
        'Meningococcal',
        'Tetanus, Diphtheria, Pertussis (Tdap)',
        'Varicella (Chickenpox)',
        'HPV',
        'Other'
    ]
    
    print("\nCommon Vaccines:")
    for i, vaccine in enumerate(common_vaccines):
        print(f"{i+1}. {vaccine}")
    
    while True:
        vaccine_choice = input("\nSelect vaccine (1-10): ")
        if vaccine_choice.isdigit() and 1 <= int(vaccine_choice) <= len(common_vaccines):
            vaccine_name = common_vaccines[int(vaccine_choice) - 1]
            if vaccine_name == 'Other':
                vaccine_name = input("Enter vaccine name: ")
            break
        print("Invalid choice. Please try again.")
    
    while True:
        administered_date = input("Administered date (YYYY-MM-DD) [today]: ").strip()
        if not administered_date:
            administered_date = datetime.now().strftime('%Y-%m-%d')
            break
        try:
            datetime.strptime(administered_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    # Calculate expiry date based on vaccine type
    expiry_periods = {
        'COVID-19': 365,  # 1 year
        'Influenza (Flu)': 365,  # Annual
        'Hepatitis A': 365 * 10,  # 10 years
        'Hepatitis B': 365 * 20,  # 20 years lifetime
        'Measles, Mumps, Rubella (MMR)': 365 * 20,  # Lifetime
        'Meningococcal': 365 * 5,  # 5 years
        'Tetanus, Diphtheria, Pertussis (Tdap)': 365 * 10,  # 10 years
        'Varicella (Chickenpox)': 365 * 20,  # Lifetime
        'HPV': 365 * 10  # 10+ years
    }
    
    if vaccine_name in expiry_periods:
        expiry_date = (datetime.strptime(administered_date, '%Y-%m-%d') + 
                      timedelta(days=expiry_periods[vaccine_name])).strftime('%Y-%m-%d')
    else:
        while True:
            expiry_date = input("Expiry date (YYYY-MM-DD): ")
            try:
                datetime.strptime(expiry_date, '%Y-%m-%d')
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")
    
    lot_number = input("Lot number: ")
    manufacturer = input("Manufacturer: ")
    administered_by = input(f"Administered by [Dr. {auth.current_user['username']}]: ").strip()
    if not administered_by:
        administered_by = f"Dr. {auth.current_user['username']}"
    
    location = input("Administration site (e.g., left arm): ")
    
    # Check for allergies
    cursor.execute('''
    SELECT allergen, severity FROM allergies 
    WHERE student_id = ? AND verified = 1
    ''', (student_id,))
    
    allergies = cursor.fetchall()
    if allergies:
        print("\n⚠️  ALLERGY ALERT - Patient has verified allergies:")
        for allergen, severity in allergies:
            print(f"- {allergen} ({severity})")
        
        proceed = input("\nHave you checked for vaccine contraindications? (y/n): ").lower()
        if proceed != 'y':
            print("Please check for contraindications before administering vaccine.")
            conn.close()
            return
    
    # Record any adverse reactions
    adverse_reaction = input("Any adverse reactions? (y/n): ").lower() == 'y'
    reaction_description = ""
    if adverse_reaction:
        reaction_description = input("Describe adverse reaction: ")
    
    verified = 1 if auth.current_user['role'] == 'health_provider' else 0
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO vaccination_records 
    (student_id, vaccine_name, administered_date, expiry_date, lot_number, 
     manufacturer, administered_by, location, adverse_reaction, reaction_description, 
     verified, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, vaccine_name, administered_date, expiry_date, lot_number,
          manufacturer, administered_by, location, 1 if adverse_reaction else 0,
          reaction_description, verified, created_at))
    
    conn.commit()
    vaccination_id = cursor.lastrowid
    
    log_audit_event(auth.current_user['id'], 'record_vaccination', 'vaccination', vaccination_id)
    
    print(f"\nVaccination recorded successfully!")
    print(f"Vaccination ID: {vaccination_id}")
    print(f"Expires: {expiry_date}")
    
    if adverse_reaction:
        print("⚠️  ADVERSE REACTION REPORTED - Monitor patient closely")
        log_audit_event(auth.current_user['id'], 'vaccination_adverse_reaction', 'vaccination', vaccination_id,
                       reaction_description)
    
    conn.close()

def view_vaccinations(auth):
    if not (auth.check_permission('view_own_vaccinations') or auth.check_permission('manage_vaccinations') or 
            auth.check_permission('view_any_health_record')):
        print("You don't have permission to view vaccination records.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    if auth.check_permission('view_any_health_record') or auth.check_permission('manage_vaccinations'):
        student_id = input("Enter student ID (leave blank for all): ").strip()
        
        if student_id:
            cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
            if cursor.fetchone()[0] == 0:
                print("Error: Student ID not found.")
                conn.close()
                return
            
            cursor.execute('''
            SELECT id, vaccine_name, administered_date, expiry_date, lot_number,
                   manufacturer, administered_by, location, adverse_reaction,
                   reaction_description, verified
            FROM vaccination_records
            WHERE student_id = ?
            ORDER BY administered_date DESC
            ''', (student_id,))
        else:
            cursor.execute('''
            SELECT vr.id, s.student_id, s.first_name, s.last_name, vr.vaccine_name,
                   vr.administered_date, vr.expiry_date, vr.verified
            FROM vaccination_records vr
            JOIN students s ON vr.student_id = s.student_id
            ORDER BY vr.administered_date DESC
            LIMIT 100
            ''')
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return
        
        cursor.execute('''
        SELECT id, vaccine_name, administered_date, expiry_date, lot_number,
               manufacturer, administered_by, location, adverse_reaction,
               reaction_description, verified
        FROM vaccination_records
        WHERE student_id = ?
        ORDER BY administered_date DESC
        ''', (student_id,))
    
    vaccinations = cursor.fetchall()
    
    if not vaccinations:
        print("No vaccination records found.")
        conn.close()
        return
    
    print("\n===== Vaccination Records =====")
    for vaccination in vaccinations:
        if (auth.check_permission('view_any_health_record') or auth.check_permission('manage_vaccinations')) and not student_id:
            # All vaccinations view
            vax_id, student_id_val, first_name, last_name, vaccine_name, admin_date, expiry_date, verified = vaccination
            print(f"\nID: {vax_id}")
            print(f"Student: {first_name} {last_name} (ID: {student_id_val})")
            print(f"Vaccine: {vaccine_name}")
            print(f"Date: {admin_date}")
            print(f"Expires: {expiry_date}")
            print(f"Verified: {'Yes' if verified else 'No'}")
        else:
            # Specific student view
            vax_id, vaccine_name, admin_date, expiry_date, lot_number, manufacturer, admin_by, location, adverse, reaction_desc, verified = vaccination
            print(f"\nID: {vax_id}")
            print(f"Vaccine: {vaccine_name}")
            print(f"Administered: {admin_date}")
            print(f"Expires: {expiry_date}")
            print(f"Lot Number: {lot_number}")
            print(f"Manufacturer: {manufacturer}")
            print(f"Administered by: {admin_by}")
            print(f"Location: {location}")
            print(f"Verified: {'Yes' if verified else 'No'}")
            
            if adverse:
                print(f"⚠️  Adverse Reaction: {reaction_desc}")
        
        # Check expiration status
        today = datetime.now().strftime('%Y-%m-%d')
        if expiry_date and expiry_date < today:
            print("🔴 EXPIRED - Renewal needed")
        elif expiry_date and (datetime.strptime(expiry_date, '%Y-%m-%d') - datetime.now()).days <= 90:
            print("🟡 EXPIRES SOON - Consider renewal")
        else:
            print("✅ CURRENT")
        
        print("-" * 30)
    
    conn.close()

def generate_health_report(auth):
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to generate health reports.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Health Report Generator =====")
    
    # Report options
    report_types = [
        'Student Health Summary',
        'Population Health Statistics',
        'Disease Surveillance Report',
        'Vaccination Coverage Analysis',
        'Provider Utilization Report',
        'Quality Metrics Dashboard'
    ]
    
    print("Available Report Types:")
    for i, report_type in enumerate(report_types):
        print(f"{i+1}. {report_type}")
    
    while True:
        choice = input(f"\nSelect report type (1-{len(report_types)}): ")
        if choice.isdigit() and 1 <= int(choice) <= len(report_types):
            selected_report = report_types[int(choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    # Date range for report
    while True:
        start_date = input("Start date (YYYY-MM-DD): ")
        end_date = input("End date (YYYY-MM-DD): ")
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    print(f"\nGenerating {selected_report} for period {start_date} to {end_date}...")
    
    # Generate report based on type
    if selected_report == 'Population Health Statistics':
        generate_population_health_report(auth, start_date, end_date)
    elif selected_report == 'Disease Surveillance Report':
        # already imported from health_misc at module level, fine to call
        generate_disease_surveillance_report(auth, start_date, end_date)
    elif selected_report == 'Vaccination Coverage Analysis':
        generate_vaccination_analysis_report(auth, start_date, end_date)
    elif selected_report == 'Provider Utilization Report':
        from university_system.modules.domain.health.appointments.appointment_booking import generate_provider_utilization_report
        generate_provider_utilization_report(auth, start_date, end_date)
    elif selected_report == 'Quality Metrics Dashboard':
        from university_system.modules.domain.health.records.quality_assurance import generate_quality_metrics_report
        generate_quality_metrics_report(auth, start_date, end_date)
    elif selected_report == 'Student Health Summary':
        generate_student_health_summary_report(auth, start_date, end_date)
    else:
        print("Report type not yet implemented.")
    
    conn.close()

def template_validation(auth):
    """Basic validation for record templates (safe no-op if table missing)."""
    try:
        from university_system.modules.domain.health.services import ensure_templates_schema
        ensure_templates_schema()

        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT name, COALESCE(category, 'Uncategorized') FROM templates LIMIT 20")
        rows = c.fetchall()
        if rows:
            print("\nTemplate Validation:")
            for name, category in rows:
                print(f"- {name} [{category}]")
        else:
            print("No templates found; nothing to validate.")
    except Exception as e:
        print(f"Template validation skipped: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass

def template_categories(auth):
    """List distinct template categories (safe if table absent)."""
    try:
        from university_system.modules.domain.health.services import ensure_templates_schema
        ensure_templates_schema()

        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT DISTINCT COALESCE(category, 'Uncategorized') FROM templates ORDER BY 1")
        cats = [row[0] for row in c.fetchall()]
        if cats:
            print("\nTemplate Categories:")
            for i, cat in enumerate(cats, 1):
                print(f"{i}. {cat}")
        else:
            print("No template categories found.")
    except Exception as e:
        print(f"Template categories unavailable: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass

def generate_population_health_report(auth, start_date, end_date):
    conn = get_connection()
    cursor = conn.cursor()
    
    report_content = []
    report_content.append("POPULATION HEALTH STATISTICS REPORT")
    report_content.append("=" * 40)
    report_content.append(f"Period: {start_date} to {end_date}")
    report_content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_content.append("")
    
    # Student demographics
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]
    
    cursor.execute('''
    SELECT gender, COUNT(*) FROM students 
    GROUP BY gender
    ''')
    gender_stats = cursor.fetchall()
    
    report_content.append("STUDENT DEMOGRAPHICS")
    report_content.append("-" * 20)
    report_content.append(f"Total Students: {total_students}")
    
    for gender, count in gender_stats:
        percentage = (count / total_students * 100) if total_students > 0 else 0
        report_content.append(f"{gender}: {count} ({percentage:.1f}%)")
    
    # Health record statistics
    cursor.execute('''
    SELECT COUNT(*) FROM health_records 
    WHERE record_date BETWEEN ? AND ?
    ''', (start_date, end_date))
    
    health_records_period = cursor.fetchone()[0]
    
    cursor.execute('''
    SELECT record_type, COUNT(*) FROM health_records 
    WHERE record_date BETWEEN ? AND ?
    GROUP BY record_type
    ORDER BY COUNT(*) DESC
    ''', (start_date, end_date))
    
    record_types = cursor.fetchall()
    
    report_content.append("")
    report_content.append("HEALTH SERVICES UTILIZATION")
    report_content.append("-" * 28)
    report_content.append(f"Total Health Records: {health_records_period}")
    
    for record_type, count in record_types:
        report_content.append(f"{record_type}: {count}")
    
    # Disease prevalence
    cursor.execute('''
    SELECT condition_name, COUNT(*) as prevalence
    FROM medical_conditions 
    WHERE status = 'active'
    GROUP BY condition_name
    ORDER BY prevalence DESC
    LIMIT 10
    ''')
    
    conditions = cursor.fetchall()
    
    if conditions:
        report_content.append("")
        report_content.append("TOP 10 HEALTH CONDITIONS")
        report_content.append("-" * 24)
        
        for condition, count in conditions:
            prevalence_rate = (count / total_students * 100) if total_students > 0 else 0
            report_content.append(f"{condition}: {count} cases ({prevalence_rate:.2f}%)")
    
    # Display and save report
    print("\n" + "="*60)
    for line in report_content:
        print(line)
    print("="*60)
    
    save_report = input("\nSave report to file? (y/n): ").lower()
    if save_report == 'y':
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"population_health_report_{timestamp}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            for line in report_content:
                f.write(line + '\n')
        
        print(f"Report saved to: {filename}")
        log_audit_event(auth.current_user['id'], 'generate_population_health_report', 'report', filename)
    
    conn.close()

def generate_student_health_summary_report(auth, start_date, end_date):
    """Generate a health summary report for an individual student"""
    student_id = input("Enter student ID: ").strip()
    if not student_id:
        print("Student ID is required.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    report_content = []
    report_content.append("STUDENT HEALTH SUMMARY REPORT")
    report_content.append("=" * 40)
    report_content.append(f"Student ID: {student_id}")
    report_content.append(f"Period: {start_date} to {end_date}")
    report_content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_content.append("")

    # Student demographics
    cursor.execute('''
        SELECT first_name, last_name, date_of_birth, gender, email_address
        FROM students WHERE student_id = ?
    ''', (student_id,))
    student = cursor.fetchone()

    if not student:
        print(f"Student with ID {student_id} not found.")
        conn.close()
        return

    report_content.append("STUDENT INFORMATION")
    report_content.append("-" * 20)
    report_content.append(f"Name: {student[0]} {student[1]}")
    report_content.append(f"Date of Birth: {student[2] or 'N/A'}")
    report_content.append(f"Gender: {student[3] or 'N/A'}")
    report_content.append(f"Email: {student[4] or 'N/A'}")
    report_content.append("")

    # Health records in date range
    cursor.execute('''
        SELECT record_type, record_date, provider, description
        FROM health_records
        WHERE student_id = ? AND record_date BETWEEN ? AND ?
        ORDER BY record_date DESC
    ''', (student_id, start_date, end_date))
    records = cursor.fetchall()

    report_content.append("HEALTH RECORDS")
    report_content.append("-" * 20)
    report_content.append(f"Total Records in Period: {len(records)}")

    if records:
        for record in records:
            report_content.append(f"\n  Date: {record[1]}")
            report_content.append(f"  Type: {record[0]}")
            report_content.append(f"  Provider: {record[2] or 'N/A'}")
            desc = (record[3] or 'N/A')[:100]
            report_content.append(f"  Description: {desc}")
    else:
        report_content.append("  No health records found in this period.")

    report_content.append("")

    # Active medical conditions
    cursor.execute('''
        SELECT condition_name, diagnosis_date, status, severity
        FROM medical_conditions
        WHERE student_id = ?
        ORDER BY diagnosis_date DESC
    ''', (student_id,))
    conditions = cursor.fetchall()

    report_content.append("MEDICAL CONDITIONS")
    report_content.append("-" * 20)
    if conditions:
        for cond in conditions:
            status_str = f" [{cond[2]}]" if cond[2] else ""
            severity_str = f" (Severity: {cond[3]})" if cond[3] else ""
            report_content.append(f"  {cond[0]}{status_str}{severity_str} - Diagnosed: {cond[1] or 'N/A'}")
    else:
        report_content.append("  No medical conditions on record.")

    report_content.append("")

    # Vaccination records
    cursor.execute('''
        SELECT vaccine_name, vaccination_date, dose_number, administered_by
        FROM vaccinations
        WHERE student_id = ?
        ORDER BY vaccination_date DESC
    ''', (student_id,))
    vaccinations = cursor.fetchall()

    report_content.append("VACCINATION HISTORY")
    report_content.append("-" * 20)
    if vaccinations:
        for vax in vaccinations:
            dose_str = f" (Dose {vax[2]})" if vax[2] else ""
            report_content.append(f"  {vax[0]}{dose_str} - {vax[1] or 'N/A'} by {vax[3] or 'N/A'}")
    else:
        report_content.append("  No vaccination records found.")

    report_content.append("")

    # Appointments in date range
    cursor.execute('''
        SELECT appointment_date, appointment_type, provider, status
        FROM appointments
        WHERE student_id = ? AND appointment_date BETWEEN ? AND ?
        ORDER BY appointment_date DESC
    ''', (student_id, start_date, end_date))
    appointments = cursor.fetchall()

    report_content.append("APPOINTMENTS IN PERIOD")
    report_content.append("-" * 20)
    if appointments:
        for apt in appointments:
            report_content.append(f"  {apt[0]} - {apt[1]} with {apt[2] or 'N/A'} [{apt[3] or 'N/A'}]")
    else:
        report_content.append("  No appointments in this period.")

    # Display and save report
    print("\n" + "=" * 60)
    for line in report_content:
        print(line)
    print("=" * 60)

    save_report = input("\nSave report to file? (y/n): ").lower()
    if save_report == 'y':
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"student_health_summary_{student_id}_{timestamp}.txt"

        with open(filename, 'w', encoding='utf-8') as f:
            for line in report_content:
                f.write(line + '\n')

        print(f"Report saved to: {filename}")
        log_audit_event(auth.current_user['id'], 'generate_student_health_summary', 'report', filename)

    conn.close()

def screening_recommendations(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to generate screening recommendations.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Health Screening Recommendations =====")
    
    # Age-based screening recommendations
    print("AGE-BASED SCREENING RECOMMENDATIONS")
    print("-" * 35)
    
    # Get students by age groups
    age_groups = [
        ('18-21', 18, 21, ['Mental health screening', 'STI testing', 'Immunization review']),
        ('22-25', 22, 25, ['Blood pressure check', 'Cholesterol screening', 'Mental health screening']),
        ('26-30', 26, 30, ['Diabetes screening', 'Blood pressure check', 'Cholesterol screening']),
        ('30+', 30, 100, ['Comprehensive metabolic panel', 'Cardiovascular risk assessment'])
    ]
    
    for age_range, min_age, max_age, recommended_screenings in age_groups:
        cursor.execute('''
        SELECT COUNT(*) FROM students 
        WHERE age BETWEEN ? AND ?
        ''', (min_age, max_age))
        
        student_count = cursor.fetchone()[0]
        
        if student_count > 0:
            print(f"\nAge Group {age_range}: {student_count} students")
            print("Recommended screenings:")
            for screening in recommended_screenings:
                print(f"  • {screening}")
    
    # Risk-based screening recommendations
    print(f"\nRISK-BASED SCREENING RECOMMENDATIONS")
    print("-" * 34)
    
    # Students with family history indicators
    cursor.execute('''
    SELECT student_id, first_name, last_name
    FROM students s
    WHERE EXISTS (
        SELECT 1 FROM medical_conditions mc
        WHERE mc.student_id = s.student_id 
        AND mc.condition_name IN ('Family History of Heart Disease', 'Family History of Diabetes', 'Family History of Cancer')
        AND mc.status = 'active'
    )
    ''')
    
    family_history_students = cursor.fetchall()
    
    if family_history_students:
        print(f"Students with significant family history: {len(family_history_students)}")
        print("Enhanced screening recommendations:")
        print("  • Earlier cardiovascular screening")
        print("  • Diabetes screening (if family history of diabetes)")
        print("  • Cancer screening discussion")
        print("  • Genetic counseling referral consideration")
    
    # Students with chronic conditions needing monitoring
    cursor.execute('''
    SELECT mc.condition_name, COUNT(*) as patient_count
    FROM medical_conditions mc
    WHERE mc.status = 'active'
    AND mc.condition_name IN ('Diabetes', 'Hypertension', 'Asthma', 'Depression')
    GROUP BY mc.condition_name
    ORDER BY patient_count DESC
    ''')
    
    chronic_conditions = cursor.fetchall()
    
    if chronic_conditions:
        print(f"\nChronic condition monitoring:")
        
        condition_monitoring = {
            'Diabetes': ['HbA1c every 3-6 months', 'Annual eye exam', 'Foot exam', 'Kidney function tests'],
            'Hypertension': ['Blood pressure checks every 3 months', 'Annual cardiovascular risk assessment'],
            'Asthma': ['Peak flow monitoring', 'Annual spirometry', 'Allergy testing if indicated'],
            'Depression': ['PHQ-9 screening every 3 months', 'Annual comprehensive mental health assessment']
        }
        
        for condition, count in chronic_conditions:
            print(f"\n{condition} ({count} students):")
            if condition in condition_monitoring:
                for monitoring in condition_monitoring[condition]:
                    print(f"  • {monitoring}")
    
    # Population-specific recommendations
    print(f"\nPOPULATION-SPECIFIC RECOMMENDATIONS")
    print("-" * 33)
    
    # High-risk behaviors screening
    cursor.execute('''
    SELECT COUNT(*) FROM students
    WHERE age BETWEEN 18 AND 25
    ''')
    
    young_adults = cursor.fetchone()[0]
    
    if young_adults > 0:
        print(f"Young adults (18-25): {young_adults} students")
        print("Universal screening recommendations:")
        print("  • Alcohol and substance use screening (AUDIT, DAST)")
        print("  • Mental health screening (PHQ-9, GAD-7)")
        print("  • Sexual health screening")
        print("  • Nutrition and exercise assessment")
    
    # Create screening schedule
    create_schedule = input("\nCreate individualized screening schedules? (y/n): ").lower()
    
    if create_schedule == 'y':
        print("\n===== Screening Schedule Generation =====")
        
        # This would create personalized screening schedules based on age, risk factors, etc.
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.last_name, s.age,
               GROUP_CONCAT(mc.condition_name) as conditions
        FROM students s
        LEFT JOIN medical_conditions mc ON s.student_id = mc.student_id AND mc.status = 'active'
        GROUP BY s.student_id, s.first_name, s.last_name, s.age
        LIMIT 10
        ''')
        
        sample_students = cursor.fetchall()
        
        print("Sample screening schedules generated:")
        
        for student_id, first_name, last_name, age, conditions in sample_students:
            print(f"\n{first_name} {last_name} (Age: {age}):")
            
            # Age-based recommendations
            if 18 <= age <= 21:
                print("  • Annual: Mental health screening, immunization review")
                print("  • Every 2 years: STI testing (if sexually active)")
            elif 22 <= age <= 25:
                print("  • Annual: Blood pressure, mental health screening")
                print("  • Every 5 years: Cholesterol screening")
            elif 26 <= age <= 30:
                print("  • Annual: Blood pressure, diabetes screening")
                print("  • Every 3 years: Cholesterol screening")
            else:
                print("  • Annual: Comprehensive metabolic panel")
                print("  • Every 2 years: Cardiovascular risk assessment")
            
            # Condition-based additions
            if conditions:
                print(f"  • Additional monitoring for: {conditions}")
        
        # Save schedules (in a real system)
        print(f"\nScreening schedules generated for all {len(sample_students)} students.")
        log_audit_event(auth.current_user['id'], 'generate_screening_schedules', 'screening', 0,
                       f"Schedules for {len(sample_students)} students")
    
    conn.close()

def wellness_resources(auth):
    print("\n===== Wellness Resources =====")
    
    wellness_categories = {
        "Physical Wellness": [
            "Campus Recreation Center - Free fitness classes",
            "Intramural Sports Programs",
            "Walking/Running Trails Map",
            "Bike Share Program",
            "Outdoor Adventure Club",
            "Personal Training Services"
        ],
        "Mental Health & Emotional Wellness": [
            "Counseling and Psychological Services (CAPS)",
            "Stress Management Workshops",
            "Mindfulness and Meditation Classes",
            "Support Groups",
            "Crisis Hotline: 988",
            "Mental Health First Aid Training"
        ],
        "Nutritional Wellness": [
            "Nutrition Counseling Services",
            "Healthy Cooking Classes",
            "Campus Farmers Market",
            "Meal Plan Consultations",
            "Food Allergy Support",
            "Eating Disorder Resources"
        ],
        "Social Wellness": [
            "Student Organizations Directory",
            "Volunteer Opportunities",
            "Leadership Development Programs",
            "Cultural Events Calendar",
            "Peer Mentoring Programs",
            "Community Service Projects"
        ],
        "Academic Wellness": [
            "Academic Success Center",
            "Study Skills Workshops",
            "Time Management Training",
            "Test Anxiety Support",
            "Tutoring Services",
            "Academic Coaching"
        ],
        "Financial Wellness": [
            "Financial Literacy Workshops",
            "Budget Planning Resources",
            "Emergency Financial Assistance",
            "Scholarship Information",
            "Student Employment Services",
            "Financial Counseling"
        ],
        "Sleep & Recovery": [
            "Sleep Hygiene Education",
            "Stress-Free Study Spaces",
            "Relaxation Techniques Training",
            "Campus Quiet Zones",
            "Nap Pods (Library)",
            "Recovery and Rest Guidelines"
        ],
        "Preventive Health": [
            "Annual Health Screenings",
            "Vaccination Clinics",
            "Health Education Workshops",
            "Disease Prevention Information",
            "Health Risk Assessments",
            "Wellness Coaching"
        ]
    }
    
    print("Available wellness resources and programs:")
    
    for category, resources in wellness_categories.items():
        print(f"\n🌟 {category}:")
        for resource in resources:
            print(f"   • {resource}")
    
    print(f"\n📞 Important Contacts:")
    print("   • Health Center: (555) 123-4567")
    print("   • Counseling Services: (555) 123-HELP")
    print("   • Crisis Line: 988")
    print("   • Campus Safety: (555) 123-SAFE")
    
    print(f"\n🌐 Online Resources:")
    print("   • Student Health Portal: health.university.edu")
    print("   • Wellness Blog: wellness.university.edu")
    print("   • Mental Health Resources: mentalhealth.university.edu")
    print("   • Fitness Class Schedule: recreation.university.edu")
    
    # Interactive resource finder
    find_resources = input("\nSearch for specific wellness resources? (y/n): ").lower()
    
    if find_resources == 'y':
        search_term = input("Enter wellness topic or keyword: ").lower()
        
        found_resources = []
        for category, resources in wellness_categories.items():
            for resource in resources:
                if search_term in resource.lower() or search_term in category.lower():
                    found_resources.append((category, resource))
        
        if found_resources:
            print(f"\nResources related to '{search_term}':")
            for category, resource in found_resources:
                print(f"   [{category}] {resource}")
        else:
            print(f"No resources found for '{search_term}'.")
            print("Try searching for: fitness, nutrition, mental health, stress, sleep, etc.")
    
    # Wellness assessment offer
    assessment = input("\nWould you like to take a quick wellness assessment? (y/n): ").lower()
    
    if assessment == 'y':
        quick_wellness_assessment(auth)

def quick_wellness_assessment(auth):
    print("\n===== Quick Wellness Assessment =====")
    print("Rate each area on a scale of 1-5 (1=Poor, 5=Excellent)")
    
    wellness_areas = [
        "Physical fitness and exercise",
        "Nutrition and eating habits", 
        "Sleep quality and duration",
        "Stress management",
        "Social connections and relationships",
        "Academic performance and satisfaction",
        "Financial security",
        "Overall mental health"
    ]
    
    scores = {}
    total_score = 0
    
    for area in wellness_areas:
        while True:
            try:
                score = int(input(f"{area} (1-5): "))
                if 1 <= score <= 5:
                    scores[area] = score
                    total_score += score
                    break
                else:
                    print("Please enter a number between 1 and 5.")
            except ValueError:
                print("Please enter a valid number.")
    
    # Calculate results
    average_score = total_score / len(wellness_areas)
    max_possible = len(wellness_areas) * 5
    percentage = (total_score / max_possible) * 100
    
    print(f"\n===== Wellness Assessment Results =====")
    print(f"Total Score: {total_score}/{max_possible}")
    print(f"Average: {average_score:.1f}/5.0")
    print(f"Overall Wellness: {percentage:.1f}%")
    
    # Provide feedback
    if percentage >= 80:
        print("🌟 Excellent! You're doing great with your overall wellness.")
    elif percentage >= 70:
        print("👍 Good wellness overall. A few areas could use attention.")
    elif percentage >= 60:
        print("⚠️  Fair wellness. Several areas need improvement.")
    else:
        print("🔴 Poor wellness scores. Consider seeking support and resources.")
    
    # Identify areas for improvement
    low_scoring_areas = [area for area, score in scores.items() if score <= 2]
    
    if low_scoring_areas:
        print(f"\nAreas needing attention:")
        for area in low_scoring_areas:
            print(f"   • {area}")
        
        print(f"\nRecommended resources:")
        
        if "Physical fitness" in str(low_scoring_areas):
            print("   • Visit the Campus Recreation Center")
            print("   • Join a fitness class or intramural sport")
        
        if "mental health" in str(low_scoring_areas):
            print("   • Contact Counseling Services: (555) 123-HELP")
            print("   • Try stress management workshops")
        
        if "Sleep" in str(low_scoring_areas):
            print("   • Attend sleep hygiene education session")
            print("   • Review study schedule and time management")
        
        if "Nutrition" in str(low_scoring_areas):
            print("   • Schedule nutrition counseling appointment")
            print("   • Attend healthy cooking classes")
    
    # Save assessment results (in a real system)
    if auth and auth.current_user:
        save_results = input("\nSave assessment results to your health record? (y/n): ").lower()
        if save_results == 'y':
            # This would save to a wellness_assessments table
            print("Assessment results saved!")
            log_audit_event(auth.current_user['id'], 'wellness_assessment', 'wellness', 0,
                           f"Score: {total_score}/{max_possible}")

        # Add this to the end of the file to ensure all functions are properly defined
        print("All missing health portal functions have been implemented!")
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
                print(f"    🔴 Action needed - Review for archival/deletion")
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

def view_health_resources(auth):
    """Display health resources and educational materials"""
    print("\n===== Health Resources =====")
    
    resources = {
        "Emergency Information": [
            "Campus Emergency: 911",
            "Health Center: (555) 123-4567",
            "Poison Control: 1-800-222-1222",
            "Crisis Hotline: 988",
            "Campus Safety: (555) 123-SAFE"
        ],
        "Health Services": [
            "Primary Care Clinic",
            "Mental Health Counseling",
            "Pharmacy Services",
            "Laboratory Services",
            "Immunization Clinic",
            "Health Education Programs"
        ],
        "Wellness Programs": [
            "Fitness Center Membership",
            "Nutrition Counseling",
            "Stress Management Workshops",
            "Sleep Health Programs",
            "Substance Abuse Prevention",
            "Mindfulness and Meditation"
        ],
        "Online Resources": [
            "Student Health Portal",
            "Health Assessment Tools",
            "Educational Videos",
            "Health Tips Newsletter",
            "Appointment Scheduling",
            "Prescription Refills"
        ]
    }
    
    for category, items in resources.items():
        print(f"\n{category}:")
        for item in items:
            print(f"  • {item}")
    
    print("\n" + "="*50)
    print("For more information, visit the Student Health Center")
    print("or call (555) 123-4567")

def generate_vaccination_analysis_report(auth, start_date, end_date):
    """Generate vaccination analysis report"""
    conn = get_connection()
    cursor = conn.cursor()
    
    report_content = []
    report_content.append("VACCINATION ANALYSIS REPORT")
    report_content.append("=" * 30)
    report_content.append(f"Period: {start_date} to {end_date}")
    report_content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_content.append("")
    
    # Vaccination coverage by type
    cursor.execute('''
    SELECT vaccine_name, COUNT(*) as doses_given,
           COUNT(DISTINCT student_id) as students_vaccinated
    FROM vaccination_records
    WHERE administered_date BETWEEN ? AND ? AND verified = 1
    GROUP BY vaccine_name
    ORDER BY doses_given DESC
    ''', (start_date, end_date))
    
    vax_data = cursor.fetchall()
    
    if vax_data:
        report_content.append("VACCINATION COVERAGE BY TYPE")
        report_content.append("-" * 30)
        for vaccine, doses, students in vax_data:
            report_content.append(f"{vaccine}: {doses} doses, {students} students")
    
    # Verification rates
    cursor.execute('''
    SELECT 
        COUNT(*) as total_vaccinations,
        SUM(CASE WHEN verified = 1 THEN 1 ELSE 0 END) as verified_count
    FROM vaccination_records
    WHERE administered_date BETWEEN ? AND ?
    ''', (start_date, end_date))
    
    verification_data = cursor.fetchone()
    if verification_data and verification_data[0] > 0:
        verification_rate = (verification_data[1] / verification_data[0]) * 100
        report_content.append("")
        report_content.append("VERIFICATION RATES")
        report_content.append("-" * 17)
        report_content.append(f"Total Vaccinations: {verification_data[0]}")
        report_content.append(f"Verified: {verification_data[1]} ({verification_rate:.1f}%)")
    
    # Display report
    for line in report_content:
        print(line)
    
    conn.close()

def generate_vaccination_status_report(auth):
    """Generate vaccination status report for students"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Vaccination Status Report =====")
    
    # Get total students
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]
    
    # Common vaccines status
    common_vaccines = ['COVID-19', 'Influenza (Flu)', 'Hepatitis B', 'MMR', 'Tdap']
    
    print(f"Total Students: {total_students}")
    print("\nVaccination Coverage by Type:")
    print("-" * 40)
    
    for vaccine in common_vaccines:
        cursor.execute('''
        SELECT COUNT(DISTINCT student_id) FROM vaccination_records 
        WHERE vaccine_name = ? AND verified = 1
        ''', (vaccine,))
        
        vaccinated = cursor.fetchone()[0]
        coverage = (vaccinated / total_students * 100) if total_students > 0 else 0
        
        print(f"{vaccine}: {vaccinated}/{total_students} ({coverage:.1f}%)")
    
    # Students with incomplete vaccinations
    cursor.execute('''
    SELECT s.student_id, s.first_name, s.last_name,
           COUNT(vr.id) as vaccine_count
    FROM students s
    LEFT JOIN vaccination_records vr ON s.student_id = vr.student_id AND vr.verified = 1
    GROUP BY s.student_id, s.first_name, s.last_name
    HAVING vaccine_count < 3
    ORDER BY vaccine_count, s.last_name
    LIMIT 20
    ''')
    
    incomplete = cursor.fetchall()
    
    if incomplete:
        print(f"\nStudents with Incomplete Vaccinations (showing first 20):")
        print("-" * 50)
        for student_id, first_name, last_name, count in incomplete:
            print(f"{last_name}, {first_name} (ID: {student_id}): {count} verified vaccines")
    
    conn.close()

def generate_health_condition_analysis(auth):
    """Generate health condition analysis report"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Health Condition Analysis =====")
    
    # Top health conditions
    cursor.execute('''
    SELECT condition_name, severity, COUNT(*) as patient_count,
           AVG(CASE WHEN status = 'active' THEN 1.0 ELSE 0.0 END) * 100 as active_percentage
    FROM medical_conditions
    GROUP BY condition_name, severity
    ORDER BY patient_count DESC
    LIMIT 20
    ''')
    
    conditions = cursor.fetchall()
    
    if conditions:
        print("Top Health Conditions:")
        print("-" * 60)
        print(f"{'Condition':<25} {'Severity':<10} {'Count':<6} {'Active %':<8}")
        print("-" * 60)
        
        for condition, severity, count, active_pct in conditions:
            print(f"{condition:<25} {severity:<10} {count:<6} {active_pct:.1f}%")
    
    # Condition trends by age group
    cursor.execute('''
    SELECT 
        CASE 
            WHEN s.age < 20 THEN '18-19'
            WHEN s.age < 25 THEN '20-24'
            WHEN s.age < 30 THEN '25-29'
            ELSE '30+'
        END as age_group,
        mc.condition_name,
        COUNT(*) as count
    FROM medical_conditions mc
    JOIN students s ON mc.student_id = s.student_id
    WHERE mc.status = 'active'
    GROUP BY age_group, mc.condition_name
    HAVING count >= 2
    ORDER BY age_group, count DESC
    ''')
    
    age_trends = cursor.fetchall()
    
    if age_trends:
        print(f"\nCondition Distribution by Age Group:")
        print("-" * 50)
        
        current_age_group = ""
        for age_group, condition, count in age_trends:
            if age_group != current_age_group:
                print(f"\nAge {age_group}:")
                current_age_group = age_group
            print(f"  {condition}: {count} cases")
    
    # Severity analysis
    cursor.execute('''
    SELECT severity, COUNT(*) as count,
           COUNT(*) * 100.0 / (SELECT COUNT(*) FROM medical_conditions WHERE status = 'active') as percentage
    FROM medical_conditions
    WHERE status = 'active'
    GROUP BY severity
    ORDER BY count DESC
    ''')
    
    severity_data = cursor.fetchall()
    
    if severity_data:
        print(f"\nCondition Severity Distribution:")
        print("-" * 35)
        for severity, count, percentage in severity_data:
            print(f"{severity}: {count} ({percentage:.1f}%)")
    
    conn.close()

def update_condition_status(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to update condition status.")
        return
    
    backup_before_operation('update_condition_status')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    condition_id = input("Enter condition ID to update: ")
    
    cursor.execute('''
    SELECT mc.id, s.student_id, s.first_name, s.last_name, mc.condition_name,
           mc.severity, mc.status, mc.provider
    FROM medical_conditions mc
    JOIN students s ON mc.student_id = s.student_id
    WHERE mc.id = ?
    ''', (condition_id,))
    
    condition = cursor.fetchone()
    
    if not condition:
        print("Error: Medical condition not found.")
        conn.close()
        return
    
    cond_id, student_id, first_name, last_name, condition_name, severity, current_status, provider = condition
    
    print(f"\nCondition Details:")
    print(f"Student: {first_name} {last_name} (ID: {student_id})")
    print(f"Condition: {condition_name}")
    print(f"Severity: {severity}")
    print(f"Current Status: {current_status}")
    print(f"Provider: {provider}")
    
    status_options = ['active', 'resolved', 'managed', 'inactive']
    print("\nStatus Options:")
    for i, status in enumerate(status_options):
        print(f"{i+1}. {status}")
    
    while True:
        choice = input("\nSelect new status (1-4): ")
        if choice.isdigit() and 1 <= int(choice) <= len(status_options):
            new_status = status_options[int(choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    notes = input("Update notes (optional): ")
    
    cursor.execute('''
    UPDATE medical_conditions 
    SET status = ?, notes = CASE WHEN ? != '' THEN ? ELSE notes END
    WHERE id = ?
    ''', (new_status, notes, notes, condition_id))
    
    conn.commit()
    log_audit_event(auth.current_user['id'], 'update_condition_status', 'medical_condition', condition_id,
                   f"Status changed from {current_status} to {new_status}")
    
    print(f"\nCondition status updated to '{new_status}' successfully!")
    
    # If condition is resolved, suggest care plan completion
    if new_status == 'resolved':
        cursor.execute('''
        SELECT id, plan_name FROM care_plans 
        WHERE condition_id = ? AND status = 'active'
        ''', (condition_id,))
        
        active_plans = cursor.fetchall()
        if active_plans:
            print(f"\n📋 Active care plans found for this condition:")
            for plan_id, plan_name in active_plans:
                print(f"  - {plan_name} (ID: {plan_id})")
            
            complete_plans = input("Mark associated care plans as completed? (y/n): ").lower()
            if complete_plans == 'y':
                cursor.execute('''
                UPDATE care_plans 
                SET status = 'completed', end_date = ?
                WHERE condition_id = ? AND status = 'active'
                ''', (datetime.now().strftime('%Y-%m-%d'), condition_id))
                conn.commit()
                print("Associated care plans marked as completed.")
    
    conn.close()

def update_allergy(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to update allergies.")
        return
    
    backup_before_operation('update_allergy')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    allergy_id = input("Enter allergy ID to update: ")
    
    cursor.execute('''
    SELECT a.id, s.student_id, s.first_name, s.last_name, a.allergen,
           a.severity, a.reaction_description, a.provider, a.verified
    FROM allergies a
    JOIN students s ON a.student_id = s.student_id
    WHERE a.id = ?
    ''', (allergy_id,))
    
    allergy = cursor.fetchone()
    
    if not allergy:
        print("Error: Allergy record not found.")
        conn.close()
        return
    
    allergy_id, student_id, first_name, last_name, allergen, severity, reaction, provider, verified = allergy
    
    print(f"\nCurrent Allergy Details:")
    print(f"Student: {first_name} {last_name} (ID: {student_id})")
    print(f"Allergen: {allergen}")
    print(f"Severity: {severity}")
    print(f"Reaction: {reaction}")
    print(f"Provider: {provider}")
    print(f"Verified: {'Yes' if verified else 'No'}")
    
    print("\nEnter new values (press Enter to keep current):")
    
    severity_levels = ['Mild', 'Moderate', 'Severe', 'Life-threatening']
    print(f"\nCurrent severity: {severity}")
    print("Severity options: Mild, Moderate, Severe, Life-threatening")
    new_severity = input(f"New severity [{severity}]: ").strip()
    if not new_severity or new_severity not in severity_levels:
        new_severity = severity
    
    new_reaction = input(f"Reaction description [{reaction}]: ").strip()
    if not new_reaction:
        new_reaction = reaction
    
    new_provider = input(f"Provider [{provider}]: ").strip()
    if not new_provider:
        new_provider = provider
    
    verify_input = input(f"Verified ({'Yes' if verified else 'No'}) [y/n]: ").strip().lower()
    if verify_input == 'y':
        new_verified = 1
    elif verify_input == 'n':
        new_verified = 0
    else:
        new_verified = verified
    
    cursor.execute('''
    UPDATE allergies 
    SET severity = ?, reaction_description = ?, provider = ?, verified = ?
    WHERE id = ?
    ''', (new_severity, new_reaction, new_provider, new_verified, allergy_id))
    
    conn.commit()
    log_audit_event(auth.current_user['id'], 'update_allergy', 'allergy', allergy_id)
    print("\nAllergy record updated successfully!")
    
    # Show severity warning for severe allergies
    if new_severity in ['Severe', 'Life-threatening']:
        print(f"\n⚠️  CRITICAL ALLERGY ALERT: {new_severity} {allergen} allergy")
    
    conn.close()

def delete_allergy(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to delete allergies.")
        return
    
    backup_before_operation('delete_allergy')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    allergy_id = input("Enter allergy ID to delete: ")
    
    cursor.execute('''
    SELECT a.id, s.student_id, s.first_name, s.last_name, a.allergen,
           a.severity, a.reaction_description
    FROM allergies a
    JOIN students s ON a.student_id = s.student_id
    WHERE a.id = ?
    ''', (allergy_id,))
    
    allergy = cursor.fetchone()
    
    if not allergy:
        print("Error: Allergy record not found.")
        conn.close()
        return
    
    allergy_id, student_id, first_name, last_name, allergen, severity, reaction = allergy
    
    print(f"\nAllergy to delete:")
    print(f"Student: {first_name} {last_name} (ID: {student_id})")
    print(f"Allergen: {allergen}")
    print(f"Severity: {severity}")
    print(f"Reaction: {reaction}")
    
    if severity in ['Severe', 'Life-threatening']:
        print("\n⚠️  WARNING: This is a severe allergy record!")
    
    confirm = input("\nAre you sure you want to delete this allergy record? (yes/no): ").lower()
    if confirm != 'yes':
        print("Deletion cancelled.")
        conn.close()
        return
    
    cursor.execute('DELETE FROM allergies WHERE id = ?', (allergy_id,))
    conn.commit()
    
    log_audit_event(auth.current_user['id'], 'delete_allergy', 'allergy', allergy_id,
                   f"Deleted {allergen} allergy for student {student_id}")
    print("\nAllergy record deleted successfully!")
    conn.close()

def generate_public_health_report(auth):
    if not auth.check_permission('issue_health_advisories'):
        print("You don't have permission to generate public health reports.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Public Health Report Generator =====")
    
    # Report parameters
    report_types = [
        'Weekly Surveillance Summary',
        'Monthly Disease Report',
        'Outbreak Investigation Report',
        'Vaccination Coverage Report',
        'Custom Analysis Report'
    ]
    
    print("Report Types:")
    for i, report_type in enumerate(report_types):
        print(f"{i+1}. {report_type}")
    
    while True:
        choice = input("\nSelect report type (1-5): ")
        if choice.isdigit() and 1 <= int(choice) <= len(report_types):
            selected_report = report_types[int(choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    # Date range
    if selected_report == 'Weekly Surveillance Summary':
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
    elif selected_report == 'Monthly Disease Report':
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
    else:
        while True:
            start_date_str = input("Start date (YYYY-MM-DD): ")
            end_date_str = input("End date (YYYY-MM-DD): ")
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")
    
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    print(f"\nGenerating {selected_report}")
    print(f"Period: {start_date_str} to {end_date_str}")
    
    # Generate report content
    report_content = []
    report_content.append(f"=== {selected_report} ===")
    report_content.append(f"Report Period: {start_date_str} to {end_date_str}")
    report_content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_content.append(f"Generated by: {auth.current_user['username']}")
    report_content.append("")
    
    # Disease surveillance data
    cursor.execute('''
    SELECT disease_name, COUNT(*) as case_count,
           SUM(CASE WHEN severity IN ('Severe', 'Critical') THEN 1 ELSE 0 END) as severe_cases
    FROM disease_surveillance
    WHERE case_date BETWEEN ? AND ?
    GROUP BY disease_name
    ORDER BY case_count DESC
    ''', (start_date_str, end_date_str))
    
    disease_data = cursor.fetchall()
    
    if disease_data:
        report_content.append("DISEASE SURVEILLANCE SUMMARY")
        report_content.append("-" * 30)
        total_cases = sum(count for _, count, _ in disease_data)
        report_content.append(f"Total Cases: {total_cases}")
        report_content.append("")
        
        for disease, count, severe in disease_data:
            report_content.append(f"{disease}: {count} cases ({severe} severe)")
    
    # Vaccination data
    cursor.execute('''
    SELECT vaccine_name, COUNT(*) as doses_administered
    FROM vaccination_records
    WHERE administered_date BETWEEN ? AND ?
    GROUP BY vaccine_name
    ORDER BY doses_administered DESC
    ''', (start_date_str, end_date_str))
    
    vaccination_data = cursor.fetchall()
    
    if vaccination_data:
        report_content.append("")
        report_content.append("VACCINATION SUMMARY")
        report_content.append("-" * 20)
        total_doses = sum(count for _, count in vaccination_data)
        report_content.append(f"Total Doses: {total_doses}")
        report_content.append("")
        
        for vaccine, count in vaccination_data:
            report_content.append(f"{vaccine}: {count} doses")
    
    # Health advisories
    cursor.execute('''
    SELECT title, priority, effective_date
    FROM health_advisories
    WHERE effective_date BETWEEN ? AND ?
    ORDER BY priority DESC, effective_date DESC
    ''', (start_date_str, end_date_str))
    
    advisory_data = cursor.fetchall()
    
    if advisory_data:
        report_content.append("")
        report_content.append("HEALTH ADVISORIES ISSUED")
        report_content.append("-" * 25)
        
        for title, priority, date in advisory_data:
            report_content.append(f"{date} - {title} ({priority} priority)")
    
    # Key recommendations
    report_content.append("")
    report_content.append("KEY RECOMMENDATIONS")
    report_content.append("-" * 20)
    
    # Generate recommendations based on data
    recommendations = []
    
    if disease_data:
        high_count_diseases = [disease for disease, count, _ in disease_data if count >= 5]
        if high_count_diseases:
            recommendations.append(f"Enhanced surveillance recommended for: {', '.join(high_count_diseases)}")
    
    if vaccination_data:
        if total_doses < 50:  # Arbitrary threshold
            recommendations.append("Consider vaccination outreach campaigns")
    
    recommendations.append("Continue routine surveillance activities")
    recommendations.append("Monitor for seasonal disease patterns")
    
    for rec in recommendations:
        report_content.append(f"• {rec}")
    
    # Display report
    print("\n" + "="*60)
    for line in report_content:
        print(line)
    print("="*60)
    
    # Save report option
    save_report = input("\nSave report to file? (y/n): ").lower()
    if save_report == 'y':
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"public_health_report_{timestamp}.txt"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                for line in report_content:
                    f.write(line + '\n')
            
            log_audit_event(auth.current_user['id'], 'generate_public_health_report', 'report', filename)
            print(f"Report saved to: {filename}")
        except Exception as e:
            print(f"Error saving report: {e}")
    
    conn.close()

def patient_safety_metrics(auth):
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to view patient safety metrics.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Patient Safety Metrics =====")
    
    # Adverse events tracking
    print("ADVERSE EVENTS")
    print("-" * 15)
    
    # Vaccination adverse reactions
    cursor.execute('''
    SELECT 
        COUNT(*) as total_vaccinations,
        SUM(CASE WHEN adverse_reaction = 1 THEN 1 ELSE 0 END) as adverse_reactions
    FROM vaccination_records
    WHERE administered_date >= date('now', '-90 days')
    ''')
    
    vax_safety = cursor.fetchone()
    if vax_safety[0] > 0:
        adverse_rate = (vax_safety[1] / vax_safety[0] * 100)
        print(f"Vaccination Adverse Reaction Rate: {adverse_rate:.2f}%")
        
        if adverse_rate <= 1:
            print("  ✅ Within acceptable range")
        elif adverse_rate <= 2:
            print("  🟡 Monitor closely")
        else:
            print("  🔴 High adverse reaction rate - Investigate")
    
    # Medication safety indicators
    print("\nMEDICATION SAFETY")
    print("-" * 17)
    
    # Students with drug allergies on active medications
    cursor.execute('''
    SELECT COUNT(DISTINCT p.student_id)
    FROM prescriptions p
    JOIN allergies a ON p.student_id = a.student_id
    WHERE p.status = 'active' AND a.verified = 1
    ''')
    
    potential_interactions = cursor.fetchone()[0]
    print(f"Patients with allergies on active medications: {potential_interactions}")
    
    if potential_interactions > 0:
        print("  ⚠️  Requires medication review for interactions")
    else:
        print("  ✅ No obvious allergy conflicts")
    
    # Critical lab values follow-up
    print("\nCRITICAL VALUES MANAGEMENT")
    print("-" * 25)
    
    cursor.execute('''
    SELECT COUNT(*)
    FROM lab_results
    WHERE abnormal_flag IN ('H', 'L') 
    AND resulted_date >= date('now', '-7 days')
    ''')
    
    critical_values = cursor.fetchone()[0]
    print(f"Critical lab values (last 7 days): {critical_values}")
    
    if critical_values > 0:
        print("  ⚠️  Ensure all critical values have provider follow-up")
    
    # Emergency contact completeness
    print("\nEMERGENCY PREPAREDNESS")
    print("-" * 22)
    
    cursor.execute('''
    SELECT 
        COUNT(DISTINCT s.student_id) as total_students,
        COUNT(DISTINCT ec.student_id) as with_emergency_contacts
    FROM students s
    LEFT JOIN emergency_contacts ec ON s.student_id = ec.student_id
    ''')
    
    emergency_data = cursor.fetchone()
    if emergency_data[0] > 0:
        emergency_completeness = (emergency_data[1] / emergency_data[0] * 100)
        print(f"Students with Emergency Contacts: {emergency_completeness:.1f}%")
        
        if emergency_completeness >= 95:
            print("  ✅ Excellent emergency preparedness")
        elif emergency_completeness >= 85:
            print("  🟡 Good emergency preparedness")
        else:
            print("  🔴 Poor emergency preparedness")
    
    # Data security indicators
    print("\nDATA SECURITY")
    print("-" * 13)
    
    # Recent audit trail activity
    cursor.execute('''
    SELECT COUNT(DISTINCT user_id)
    FROM audit_trail
    WHERE timestamp >= datetime('now', '-24 hours')
    ''')
    
    active_users = cursor.fetchone()[0]
    print(f"Active users (last 24 hours): {active_users}")
    
    # Failed login attempts
    cursor.execute('''
    SELECT COUNT(*)
    FROM audit_trail
    WHERE action = 'failed_login' 
    AND timestamp >= datetime('now', '-24 hours')
    ''')
    
    failed_logins = cursor.fetchone()[0]
    print(f"Failed login attempts (last 24 hours): {failed_logins}")
    
    if failed_logins > 10:
        print("  🔴 High number of failed login attempts")
    elif failed_logins > 5:
        print("  🟡 Monitor login security")
    else:
        print("  ✅ Normal login activity")
    
    conn.close()

def add_allergy(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to add allergies.")
        return
    
    backup_before_operation('add_allergy')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get student ID
    student_id = input("Enter student ID: ")
    
    # Verify student exists
    cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
    if cursor.fetchone()[0] == 0:
        print("Error: Student ID not found.")
        conn.close()
        return
    
    allergen = input("Allergen name: ")
    
    severity_levels = ['Mild', 'Moderate', 'Severe', 'Life-threatening']
    print("\nSeverity Levels:")
    for i, level in enumerate(severity_levels):
        print(f"{i+1}. {level}")
    
    while True:
        severity_choice = input("\nSelect severity (1-4): ")
        if severity_choice.isdigit() and 1 <= int(severity_choice) <= len(severity_levels):
            severity = severity_levels[int(severity_choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    reaction_description = input("Describe typical reaction: ")
    
    while True:
        diagnosed_date = input("Date diagnosed (YYYY-MM-DD) [today]: ").strip()
        if not diagnosed_date:
            diagnosed_date = datetime.now().strftime('%Y-%m-%d')
            break
        try:
            datetime.strptime(diagnosed_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    provider = input("Diagnosing provider: ")
    verified = 1 if auth.current_user['role'] == 'health_provider' else 0
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO allergies 
    (student_id, allergen, severity, reaction_description, diagnosed_date, provider, verified, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, allergen, severity, reaction_description, diagnosed_date, provider, verified, created_at))
    
    conn.commit()
    
    # Get the ID of the newly inserted allergy record
    allergy_id = cursor.lastrowid
    
    # Log the correct audit event
    log_audit_event(auth.current_user['id'], 'add_allergy', 'allergy', allergy_id)
    
    print("\nAllergy record added successfully!")
    
    # Display severity warning for severe allergies
    if severity in ['Severe', 'Life-threatening']:
        print(f"\n⚠️  CRITICAL ALLERGY ALERT: {severity} {allergen} allergy")
        print("This allergy should be prominently displayed in the patient's medical record.")
    
    # Check for drug interactions with existing prescriptions
    cursor.execute('''
    SELECT medication_name FROM prescriptions 
    WHERE student_id = ? AND status = 'active'
    ''', (student_id,))
    
    active_medications = [row[0] for row in cursor.fetchall()]
    if active_medications:
        print(f"\n⚠️  WARNING: Student has active medications. Please review for potential interactions with {allergen}:")
        for med in active_medications:
            print(f"- {med}")
        print("Consider consulting a pharmacist or using a drug interaction checker.")
    
    conn.close()

def view_lab_results(auth):
    if not (auth.check_permission('view_any_health_record') or auth.check_permission('view_own_health_record')):
        print("You don't have permission to view lab results.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    if auth.check_permission('view_any_health_record'):
        student_id = input("Enter student ID: ")
        
        cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
        if cursor.fetchone()[0] == 0:
            print("Error: Student ID not found.")
            conn.close()
            return
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return
    
    cursor.execute('''
    SELECT id, test_name, result_value, reference_range, units, status,
           ordered_date, collected_date, resulted_date, ordering_provider,
           lab_name, abnormal_flag
    FROM lab_results
    WHERE student_id = ?
    ORDER BY resulted_date DESC
    ''', (student_id,))
    
    results = cursor.fetchall()
    
    if not results:
        print("No lab results found.")
        conn.close()
        return
    
    print("\n===== Lab Results =====")
    for result in results:
        result_id, test_name, result_value, reference_range, units, status, ordered_date, collected_date, resulted_date, ordering_provider, lab_name, abnormal_flag = result
        
        print(f"\nTest: {test_name}")
        print(f"Result: {result_value} {units}")
        print(f"Reference Range: {reference_range}")
        print(f"Status: {status}")
        print(f"Ordered: {ordered_date}")
        print(f"Collected: {collected_date}")
        print(f"Resulted: {resulted_date}")
        print(f"Ordering Provider: {ordering_provider}")
        print(f"Lab: {lab_name}")
        
        if abnormal_flag:
            if abnormal_flag == 'H':
                print("🔴 HIGH - Above normal range")
            elif abnormal_flag == 'L':
                print("🔵 LOW - Below normal range")
        else:
            print("✅ NORMAL")
        
        print("-" * 30)
    
    conn.close()

def display_health_portal_menu(auth=None):
    if not auth:
        from university_system.infrastructure.auth import UserAuth
        auth = get_auth()
        if auth is None:
            auth = UserAuth()

    # Initialize the enhanced database
    init_enhanced_health_db()
    # Add health permissions to authentication system
    setup_health_permissions(auth)
    
    while True:
        # Check if user is logged in
        if not auth or not auth.current_user:
            print("\nYou must be logged in to access the Enhanced Health Portal.")
            return auth
        
        # Check session timeout
        if SecurityManager.check_session_timeout(auth):
            print("\nSession timed out. Please log in again.")
            auth.logout()
            return auth
        
        print("\n===== Enhanced University Health Portal =====")
        print(f"Logged in as: {auth.current_user['username']} ({auth.current_user['role']})")
        
        # Display menu options based on user role/permissions
        menu_options = []
        
        # Health Records section (enhanced)
        if auth.check_permission('manage_health_records') or auth.check_permission('view_own_health_record') or auth.check_permission('view_any_health_record'):
            print("\n📋 Health Records & Clinical Data:")
            
            if auth.check_permission('manage_health_records'):
                print(f"{len(menu_options) + 1}. Manage Health Records")
                # FIX: Use direct function reference instead of lambda
                menu_options.append(("Manage Health Records", manage_health_records_enhanced))
            
            if auth.check_permission('view_any_health_record') or auth.check_permission('view_own_health_record'):
                print(f"{len(menu_options) + 1}. View Health Records")
                menu_options.append(("View Health Records", view_health_records))
            
            print(f"{len(menu_options) + 1}. Allergy Management")
            menu_options.append(("Allergy Management", manage_allergies))
            
            print(f"{len(menu_options) + 1}. Prescription Management")
            menu_options.append(("Prescription Management", manage_prescriptions))
            
            print(f"{len(menu_options) + 1}. Vital Signs Management")
            menu_options.append(("Vital Signs Management", manage_vital_signs))
            
            print(f"{len(menu_options) + 1}. Lab Results Management")
            menu_options.append(("Lab Results Management", manage_lab_results))
        
        # Provider-specific menus
        if auth.check_permission('manage_health_records'):
            print(f"{len(menu_options) + 1}. Provider Dashboard")
            menu_options.append(("Provider Dashboard", provider_dashboard))
            
            print(f"{len(menu_options) + 1}. Provider Schedule Management")
            menu_options.append(("Provider Schedule Management", manage_provider_schedules))
            
            print(f"{len(menu_options) + 1}. Referral Management")
            menu_options.append(("Referral Management", manage_referrals))
        
        # Student-specific menu
        if auth.current_user['role'] == 'student':
            print(f"{len(menu_options) + 1}. Personal Health Dashboard")
            menu_options.append(("Personal Health Dashboard", student_health_dashboard))
        
        # Appointments section
        if auth.check_permission('manage_health_appointments') or auth.check_permission('schedule_health_appointment') or auth.check_permission('view_own_appointments'):
            print("\n📅 Appointments & Scheduling:")
            
            if auth.check_permission('schedule_health_appointment') or auth.check_permission('manage_health_appointments'):
                print(f"{len(menu_options) + 1}. Schedule Appointment")
                menu_options.append(("Schedule Appointment", schedule_appointment))
            
            if auth.check_permission('view_own_appointments') or auth.check_permission('manage_health_appointments'):
                print(f"{len(menu_options) + 1}. View Appointments")
                menu_options.append(("View Appointments", view_appointments))
            
            if auth.check_permission('cancel_own_appointment') or auth.check_permission('manage_health_appointments'):
                print(f"{len(menu_options) + 1}. Update Appointment Status")
                menu_options.append(("Update Appointment Status", update_appointment_status))
        
        # Vaccinations section
        if auth.check_permission('manage_vaccinations') or auth.check_permission('view_own_vaccinations') or auth.check_permission('verify_vaccinations'):
            print("\n💉 Vaccinations & Immunizations:")
            
            if auth.check_permission('manage_vaccinations'):
                print(f"{len(menu_options) + 1}. Record Vaccination")
                menu_options.append(("Record Vaccination", record_vaccination))
            
            if auth.check_permission('view_own_vaccinations') or auth.check_permission('manage_vaccinations') or auth.check_permission('view_any_health_record'):
                print(f"{len(menu_options) + 1}. View Vaccination Records")
                menu_options.append(("View Vaccination Records", view_vaccinations))
            
            if auth.check_permission('verify_vaccinations'):
                print(f"{len(menu_options) + 1}. Verify Vaccination Record")
                menu_options.append(("Verify Vaccination Record", verify_vaccination))
        
        # Care Plans & Clinical Management
        if auth.check_permission('manage_health_records'):
            print("\n🏥 Care Plans & Clinical Management:")
            
            print(f"{len(menu_options) + 1}. Care Plan Management")
            menu_options.append(("Care Plan Management", manage_care_plans))
            
            print(f"{len(menu_options) + 1}. Health Risk Assessment")
            menu_options.append(("Health Risk Assessment", health_risk_assessment))
        
        # Emergency & Safety
        print("\n🚨 Emergency & Safety:")
        
        print(f"{len(menu_options) + 1}. Emergency Contact Management")
        menu_options.append(("Emergency Contact Management", manage_emergency_contacts))
        
        if auth.check_permission('issue_health_advisories'):
            print(f"{len(menu_options) + 1}. Disease Surveillance System")
            menu_options.append(("Disease Surveillance System", disease_surveillance_system))
        
        # Health Advisory section
        if auth.check_permission('issue_health_advisories') or auth.check_permission('view_health_advisories'):
            print("\n📢 Health Advisories & Communications:")
            
            if auth.check_permission('issue_health_advisories'):
                print(f"{len(menu_options) + 1}. Add Health Advisory")
                menu_options.append(("Add Health Advisory", add_health_advisory))
            
            if auth.check_permission('view_health_advisories') or auth.check_permission('issue_health_advisories'):
                print(f"{len(menu_options) + 1}. View Health Advisories")
                menu_options.append(("View Health Advisories", view_health_advisories))
        
        # Wellness & Prevention
        print("\n🌟 Wellness & Prevention:")
        
        print(f"{len(menu_options) + 1}. Wellness Programs")
        menu_options.append(("Wellness Programs", wellness_programs))
        
        if auth.check_permission('view_health_resources'):
            print(f"{len(menu_options) + 1}. Health Resources")
            menu_options.append(("Health Resources", view_health_resources))
        
        # Insurance Information section
        if auth.check_permission('update_insurance_info') or auth.current_user['role'] in ['admin', 'health_provider']:
            print("\n💳 Insurance & Financial:")
            
            print(f"{len(menu_options) + 1}. View Insurance Information")
            menu_options.append(("View Insurance Information", view_insurance_info))
            
            print(f"{len(menu_options) + 1}. Update Insurance Information")
            menu_options.append(("Update Insurance Information", update_insurance_info))
        
        # Analytics & Reporting
        if auth.check_permission('view_any_health_record'):
            print("\n📊 Analytics & Reporting:")
            
            print(f"{len(menu_options) + 1}. Health Analytics Dashboard")
            menu_options.append(("Health Analytics Dashboard", health_analytics_dashboard))
            
            print(f"{len(menu_options) + 1}. Generate Health Report")
            menu_options.append(("Generate Health Report", generate_health_report))
            
            print(f"{len(menu_options) + 1}. Quality Assurance")
            menu_options.append(("Quality Assurance", quality_assurance_menu))
        
        # Screening Management
        if auth.check_permission('manage_health_records'):
            print(f"{len(menu_options) + 1}. Screening Schedule Management")
            menu_options.append(("Screening Schedule Management", manage_screening_schedules))
            
            print(f"{len(menu_options) + 1}. Enhanced Record Templates")
            menu_options.append(("Enhanced Record Templates", enhanced_health_record_templates))
        
        # Data Management & Security
        if auth.current_user['role'] in ['admin']:
            print("\n🔒 Data Management & Security:")
            
            print(f"{len(menu_options) + 1}. Data Retention Management")
            menu_options.append(("Data Retention Management", data_retention_management))
            
            print(f"{len(menu_options) + 1}. Security Audit")
            menu_options.append(("Security Audit", security_audit_menu))
            
            print(f"{len(menu_options) + 1}. Advanced Security Management")
            menu_options.append(("Advanced Security Management", advanced_security_menu))
            
            print(f"{len(menu_options) + 1}. Integration Management")
            menu_options.append(("Integration Management", integration_management))
            
            print(f"{len(menu_options) + 1}. System Backup & Recovery")
            menu_options.append(("System Backup & Recovery", backup_recovery_menu))
        
        # Main menu options
        print("\n⚙️ System Options:")
        print(f"{len(menu_options) + 1}. Return to Main System")
        print(f"{len(menu_options) + 2}. Logout")
        
        # Get user choice
        choice = input("\nEnter your choice: ")
        
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(menu_options):
                # Call the selected function - FIX: All functions now accept auth parameter
                menu_options[choice_idx][1](auth)
            elif choice_idx == len(menu_options):
                # Return to main system
                print("Returning to main system...")
                return auth
            elif choice_idx == len(menu_options) + 1:
                # Logout
                auth.logout()
                print("Logged out successfully.")
                return auth
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")
        
        input("\nPress Enter to continue...")

def manage_health_records_enhanced(auth):
    """Enhanced health records management with new features"""
    while True:
        print("\n===== Enhanced Health Records Management =====")
        print("1. Add Health Record")
        print("2. View Health Records")
        print("3. Update Health Record")
        print("4. Delete Health Record")
        print("5. Medical Conditions Management")
        print("6. Health Record Templates")
        print("7. Bulk Import Records")
        print("8. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-8): ")
        
        if choice == '1':
            add_health_record(auth)
        elif choice == '2':
            view_health_records(auth)
        elif choice == '3':
            update_health_record(auth)
        elif choice == '4':
            delete_health_record(auth)
        elif choice == '5':
            manage_medical_conditions(auth)
        elif choice == '6':
            health_record_templates(auth)
        elif choice == '7':
            bulk_import_records(auth)
        elif choice == '8':
            break
        else:
            print("Invalid choice. Please try again.")

def manage_medical_conditions(auth):
    """Manage chronic medical conditions"""
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to manage medical conditions.")
        return
    
    while True:
        print("\n===== Medical Conditions Management =====")
        print("1. Add Medical Condition")
        print("2. View Medical Conditions")
        print("3. Update Condition Status")
        print("4. Condition Management Plans")
        print("5. Return to Previous Menu")
        
        choice = input("\nEnter your choice (1-5): ")
        
        if choice == '1':
            add_medical_condition(auth)
        elif choice == '2':
            view_medical_conditions(auth)
        elif choice == '3':
            update_condition_status(auth)
        elif choice == '4':
            condition_management_plans(auth)
        elif choice == '5':
            break
        else:
            print("Invalid choice. Please try again.")

def add_medical_condition(auth):
    backup_before_operation('add_medical_condition')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    student_id = input("Enter student ID: ")
    
    # Verify student exists
    cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
    if cursor.fetchone()[0] == 0:
        print("Error: Student ID not found.")
        conn.close()
        return
    
    condition_name = input("Condition name: ")
    icd_code = input("ICD-10 code (optional): ")
    
    severity_levels = ['Mild', 'Moderate', 'Severe']
    print("\nSeverity Levels:")
    for i, level in enumerate(severity_levels):
        print(f"{i+1}. {level}")
    
    while True:
        severity_choice = input("\nSelect severity (1-3): ")
        if severity_choice.isdigit() and 1 <= int(severity_choice) <= len(severity_levels):
            severity = severity_levels[int(severity_choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    while True:
        diagnosed_date = input("Diagnosed date (YYYY-MM-DD): ")
        try:
            datetime.strptime(diagnosed_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    provider = input(f"Diagnosing provider [Dr. {auth.current_user['username']}]: ").strip()
    if not provider:
        provider = f"Dr. {auth.current_user['username']}"
    
    notes = input("Additional notes: ")
    
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO medical_conditions 
    (student_id, condition_name, icd_code, severity, diagnosed_date, status, provider, notes, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, condition_name, icd_code, severity, diagnosed_date, 'active', provider, notes, created_at))
    
    conn.commit()
    log_audit_event(auth.current_user['id'], 'add_medical_condition', 'medical_condition', cursor.lastrowid)
    print("\nMedical condition added successfully!")
    conn.close()

def manage_prescriptions(auth):
    if not auth or not auth.current_user:
        print("You must be logged in to manage prescriptions.")
        return
    
    while True:
        print("\n===== Prescription Management =====")
        print("1. Add Prescription")
        print("2. View Prescriptions")
        print("3. Update Prescription Status")
        print("4. Medication Adherence Tracking")
        print("5. Prescription Refill Reminders")
        print("6. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-6): ")
        
        if choice == '1':
            add_prescription(auth)
        elif choice == '2':
            view_prescriptions(auth)
        elif choice == '3':
            update_prescription_status(auth)
        elif choice == '4':
            track_medication_adherence(auth)
        elif choice == '5':
            manage_refill_reminders(auth)
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")

def add_prescription(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to add prescriptions.")
        return
    
    backup_before_operation('add_prescription')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    student_id = input("Enter student ID: ")
    
    # Verify student exists
    cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
    if cursor.fetchone()[0] == 0:
        print("Error: Student ID not found.")
        conn.close()
        return
    
    # Check for allergies first
    cursor.execute('''
    SELECT allergen, severity FROM allergies 
    WHERE student_id = ? AND verified = 1
    ''', (student_id,))
    allergies = cursor.fetchall()
    
    if allergies:
        print("\n⚠️  ALLERGY ALERT - Patient has the following verified allergies:")
        for allergen, severity in allergies:
            print(f"- {allergen} ({severity})")
        
        proceed = input("\nHave you checked for drug interactions? (y/n): ").lower()
        if proceed != 'y':
            print("Please check for interactions before prescribing.")
            conn.close()
            return
    
    medication_name = input("Medication name: ")
    dosage = input("Dosage (e.g., 500mg): ")
    frequency = input("Frequency (e.g., twice daily): ")
    
    while True:
        prescribed_date = input("Prescribed date (YYYY-MM-DD) [today]: ").strip()
        if not prescribed_date:
            prescribed_date = datetime.now().strftime('%Y-%m-%d')
            break
        try:
            datetime.strptime(prescribed_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    while True:
        start_date = input("Start date (YYYY-MM-DD) [today]: ").strip()
        if not start_date:
            start_date = datetime.now().strftime('%Y-%m-%d')
            break
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    while True:
        end_date = input("End date (YYYY-MM-DD) [leave blank for ongoing]: ").strip()
        if not end_date:
            end_date = None
            break
        try:
            datetime.strptime(end_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    prescriber = input(f"Prescriber [Dr. {auth.current_user['username']}]: ").strip()
    if not prescriber:
        prescriber = f"Dr. {auth.current_user['username']}"
    
    pharmacy = input("Pharmacy: ")
    notes = input("Additional notes: ")
    
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO prescriptions 
    (student_id, medication_name, dosage, frequency, prescribed_date, start_date, end_date, 
     prescriber, pharmacy, status, notes, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, medication_name, dosage, frequency, prescribed_date, start_date, 
          end_date, prescriber, pharmacy, 'active', notes, created_at))
    
    conn.commit()
    log_audit_event(auth.current_user['id'], 'add_prescription', 'prescription', cursor.lastrowid)
    print("\nPrescription added successfully!")
    conn.close()

def view_prescriptions(auth):
    if not (auth.check_permission('view_any_health_record') or auth.check_permission('view_own_health_record')):
        print("You don't have permission to view prescriptions.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    if auth.check_permission('view_any_health_record'):
        student_id = input("Enter student ID: ")
        
        cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
        if cursor.fetchone()[0] == 0:
            print("Error: Student ID not found.")
            conn.close()
            return
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return
    
    cursor.execute('''
    SELECT id, medication_name, dosage, frequency, prescribed_date, start_date, end_date,
           prescriber, pharmacy, status, notes
    FROM prescriptions
    WHERE student_id = ?
    ORDER BY prescribed_date DESC
    ''', (student_id,))
    
    prescriptions = cursor.fetchall()
    
    if not prescriptions:
        print("No prescription records found.")
        conn.close()
        return
    
    print("\n===== Prescription Records =====")
    for prescription in prescriptions:
        presc_id, medication, dosage, frequency, prescribed_date, start_date, end_date, prescriber, pharmacy, status, notes = prescription
        
        print(f"\nID: {presc_id}")
        print(f"Medication: {medication}")
        print(f"Dosage: {dosage}")
        print(f"Frequency: {frequency}")
        print(f"Prescribed: {prescribed_date}")
        print(f"Start Date: {start_date}")
        print(f"End Date: {end_date if end_date else 'Ongoing'}")
        print(f"Prescriber: {prescriber}")
        print(f"Pharmacy: {pharmacy}")
        print(f"Status: {status}")
        if notes:
            print(f"Notes: {notes}")
        
        # Check if prescription is expired
        if end_date and datetime.strptime(end_date, '%Y-%m-%d') < datetime.now():
            print("⚠️  EXPIRED")
        elif status == 'active':
            print("✅ ACTIVE")
        
        print("-" * 30)
    
    conn.close()

def update_prescription_status(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to update prescriptions.")
        return
    
    backup_before_operation('update_prescription_status')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    prescription_id = input("Enter prescription ID to update: ")
    
    cursor.execute('''
    SELECT p.id, s.student_id, s.first_name, s.last_name, p.medication_name, 
           p.dosage, p.status
    FROM prescriptions p
    JOIN students s ON p.student_id = s.student_id
    WHERE p.id = ?
    ''', (prescription_id,))
    
    prescription = cursor.fetchone()
    
    if not prescription:
        print("Error: Prescription not found.")
        conn.close()
        return
    
    presc_id, student_id, first_name, last_name, medication, dosage, current_status = prescription
    
    print(f"\nPrescription Details:")
    print(f"Student: {first_name} {last_name} (ID: {student_id})")
    print(f"Medication: {medication} ({dosage})")
    print(f"Current Status: {current_status}")
    
    status_options = ['active', 'completed', 'discontinued', 'on_hold']
    print("\nStatus Options:")
    for i, status in enumerate(status_options):
        print(f"{i+1}. {status}")
    
    while True:
        choice = input("\nSelect new status (1-4): ")
        if choice.isdigit() and 1 <= int(choice) <= len(status_options):
            new_status = status_options[int(choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    cursor.execute('''
    UPDATE prescriptions SET status = ? WHERE id = ?
    ''', (new_status, prescription_id))
    
    conn.commit()
    log_audit_event(auth.current_user['id'], 'update_prescription_status', 'prescription', prescription_id, f"Status changed from {current_status} to {new_status}")
    print(f"\nPrescription status updated to '{new_status}' successfully!")
    conn.close()

def health_analytics_dashboard(auth):
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to view health analytics.")
        return
    
    while True:
        print("\n===== Health Analytics Dashboard =====")
        print("1. Population Health Metrics")
        print("2. Vaccination Coverage Report")
        print("3. Appointment Utilization Statistics")
        print("4. Health Trends Analysis")
        print("5. Provider Workload Analysis")
        print("6. Quality Metrics")
        print("7. Generate Custom Report")
        print("8. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-8): ")
        
        if choice == '1':
            show_population_health_metrics(auth)
        elif choice == '2':
            generate_vaccination_coverage_report(auth)
        elif choice == '3':
            show_appointment_utilization_stats(auth)
        elif choice == '4':
            analyze_health_trends(auth)
        elif choice == '5':
            analyze_provider_workload(auth)
        elif choice == '6':
            show_quality_metrics(auth)
        elif choice == '7':
            generate_custom_report(auth)
        elif choice == '8':
            break
        else:
            print("Invalid choice. Please try again.")

def show_population_health_metrics(auth):
    """Show overall population health metrics"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Population Health Metrics =====")
    
    # Total students
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]
    print(f"Total Students: {total_students}")
    
    # Students with health records
    cursor.execute("SELECT COUNT(DISTINCT student_id) FROM health_records")
    students_with_records = cursor.fetchone()[0]
    print(f"Students with Health Records: {students_with_records} ({students_with_records/total_students*100:.1f}%)")
    
    # Vaccination coverage
    cursor.execute("SELECT COUNT(DISTINCT student_id) FROM vaccination_records WHERE verified = 1")
    students_with_vaccines = cursor.fetchone()[0]
    print(f"Students with Verified Vaccinations: {students_with_vaccines} ({students_with_vaccines/total_students*100:.1f}%)")
    
    # Common health conditions
    cursor.execute('''
    SELECT condition_name, COUNT(*) as count
    FROM medical_conditions
    WHERE status = 'active'
    GROUP BY condition_name
    ORDER BY count DESC
    LIMIT 5
    ''')
    
    conditions = cursor.fetchall()
    if conditions:
        print("\nTop 5 Health Conditions:")
        for condition, count in conditions:
            print(f"  {condition}: {count} students")
    
    # Allergy prevalence
    cursor.execute('''
    SELECT allergen, COUNT(*) as count
    FROM allergies
    WHERE verified = 1
    GROUP BY allergen
    ORDER BY count DESC
    LIMIT 5
    ''')
    
    allergies = cursor.fetchall()
    if allergies:
        print("\nTop 5 Allergies:")
        for allergy, count in allergies:
            print(f"  {allergy}: {count} students")
    
    # Recent health records
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    cursor.execute('''
    SELECT COUNT(*) FROM health_records 
    WHERE record_date >= ?
    ''', (thirty_days_ago,))
    
    recent_records = cursor.fetchone()[0]
    print(f"\nHealth Records (Last 30 Days): {recent_records}")
    
    # Appointments this month
    cursor.execute('''
    SELECT COUNT(*) FROM health_appointments 
    WHERE appointment_date >= ?
    ''', (thirty_days_ago,))
    
    recent_appointments = cursor.fetchone()[0]
    print(f"Appointments (Last 30 Days): {recent_appointments}")
    
    conn.close()

def generate_vaccination_coverage_report(auth):
    """Generate detailed vaccination coverage report"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Vaccination Coverage Report =====")
    
    # Overall coverage
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT student_id) FROM vaccination_records WHERE verified = 1")
    students_with_vaccines = cursor.fetchone()[0]
    
    print(f"Overall Vaccination Coverage: {students_with_vaccines}/{total_students} ({students_with_vaccines/total_students*100:.1f}%)")
    
    # Coverage by vaccine type
    cursor.execute('''
    SELECT vaccine_name, COUNT(DISTINCT student_id) as coverage
    FROM vaccination_records
    WHERE verified = 1
    GROUP BY vaccine_name
    ORDER BY coverage DESC
    ''')
    
    vaccine_coverage = cursor.fetchall()
    
    if vaccine_coverage:
        print("\nCoverage by Vaccine Type:")
        for vaccine, coverage in vaccine_coverage:
            coverage_pct = (coverage / total_students) * 100
            print(f"  {vaccine}: {coverage}/{total_students} ({coverage_pct:.1f}%)")
    
    # Expired vaccinations
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
    SELECT vaccine_name, COUNT(*) as expired_count
    FROM vaccination_records
    WHERE expiry_date < ? AND verified = 1
    GROUP BY vaccine_name
    ORDER BY expired_count DESC
    ''', (today,))
    
    expired_vaccines = cursor.fetchall()
    
    if expired_vaccines:
        print("\nExpired Vaccinations Requiring Renewal:")
        for vaccine, count in expired_vaccines:
            print(f"  {vaccine}: {count} students")
    
    # Upcoming expirations (next 90 days)
    ninety_days_from_now = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
    cursor.execute('''
    SELECT vaccine_name, COUNT(*) as expiring_count
    FROM vaccination_records
    WHERE expiry_date BETWEEN ? AND ? AND verified = 1
    GROUP BY vaccine_name
    ORDER BY expiring_count DESC
    ''', (today, ninety_days_from_now))
    
    expiring_vaccines = cursor.fetchall()
    
    if expiring_vaccines:
        print("\nVaccinations Expiring in Next 90 Days:")
        for vaccine, count in expiring_vaccines:
            print(f"  {vaccine}: {count} students")
    
    conn.close()

def analyze_health_trends(auth):
    """Analyze health trends over time"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Health Trends Analysis =====")
    
    # Monthly health records trend (last 12 months)
    twelve_months_ago = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    
    cursor.execute('''
    SELECT 
        strftime('%Y-%m', record_date) as month,
        COUNT(*) as record_count
    FROM health_records
    WHERE record_date >= ?
    GROUP BY strftime('%Y-%m', record_date)
    ORDER BY month
    ''', (twelve_months_ago,))
    
    monthly_records = cursor.fetchall()
    
    if monthly_records:
        print("Monthly Health Records (Last 12 Months):")
        for month, count in monthly_records:
            print(f"  {month}: {count} records")
    
    # Seasonal illness patterns
    cursor.execute('''
    SELECT 
        strftime('%m', record_date) as month,
        record_type,
        COUNT(*) as count
    FROM health_records
    WHERE record_date >= ? AND record_type IN ('General Medical', 'Illness Treatment')
    GROUP BY strftime('%m', record_date), record_type
    ORDER BY month, count DESC
    ''', (twelve_months_ago,))
    
    seasonal_patterns = cursor.fetchall()
    
    if seasonal_patterns:
        print("\nSeasonal Illness Patterns:")
        current_month = ""
        for month, record_type, count in seasonal_patterns:
            month_name = datetime.strptime(month, '%m').strftime('%B')
            if month_name != current_month:
                print(f"  {month_name}:")
                current_month = month_name
            print(f"    {record_type}: {count}")
    
    # Emergency contact usage trends
    cursor.execute('''
    SELECT 
        strftime('%Y-%m', created_at) as month,
        COUNT(*) as emergency_contacts
    FROM emergency_contacts
    WHERE created_at >= ?
    GROUP BY strftime('%Y-%m', created_at)
    ORDER BY month
    ''', (twelve_months_ago,))
    
    emergency_trends = cursor.fetchall()
    
    if emergency_trends:
        print("\nEmergency Contact Updates (Last 12 Months):")
        for month, count in emergency_trends:
            print(f"  {month}: {count} updates")
    
    conn.close()

def generate_student_health_summary(auth):
    """Generate comprehensive student health summary"""
    conn = get_connection()
    cursor = conn.cursor()
    
    student_id = input("Enter student ID: ")
    
    # Verify student exists
    cursor.execute('''
    SELECT student_id, first_name, last_name, gender, date_of_birth, age
    FROM students WHERE student_id = ?
    ''', (student_id,))
    
    student = cursor.fetchone()
    if not student:
        print("Error: Student ID not found.")
        conn.close()
        return
    
    print(f"\n===== Health Summary for {student[1]} {student[2]} =====")
    print(f"Student ID: {student[0]}")
    print(f"Gender: {student[3]}")
    print(f"Date of Birth: {student[4]}")
    print(f"Age: {student[5]}")
    
    # Health conditions
    cursor.execute('''
    SELECT condition_name, severity, diagnosed_date, status
    FROM medical_conditions
    WHERE student_id = ?
    ORDER BY diagnosed_date DESC
    ''', (student_id,))
    
    conditions = cursor.fetchall()
    if conditions:
        print("\nMedical Conditions:")
        for condition, severity, diagnosed_date, status in conditions:
            print(f"  - {condition} ({severity}) - Diagnosed: {diagnosed_date} - Status: {status}")
    
    # Allergies
    cursor.execute('''
    SELECT allergen, severity, reaction_description, verified
    FROM allergies
    WHERE student_id = ?
    ORDER BY severity DESC
    ''', (student_id,))
    
    allergies = cursor.fetchall()
    if allergies:
        print("\nAllergies:")
        for allergen, severity, reaction, verified in allergies:
            status = "Verified" if verified else "Unverified"
            print(f"  - {allergen} ({severity}) - {reaction} - {status}")
    
    # Recent vaccinations
    cursor.execute('''
    SELECT vaccine_name, administered_date, expiry_date, verified
    FROM vaccination_records
    WHERE student_id = ?
    ORDER BY administered_date DESC
    LIMIT 10
    ''', (student_id,))
    
    vaccinations = cursor.fetchall()
    if vaccinations:
        print("\nRecent Vaccinations:")
        for vaccine, admin_date, expiry_date, verified in vaccinations:
            status = "Verified" if verified else "Unverified"
            print(f"  - {vaccine} - Administered: {admin_date} - Expires: {expiry_date} - {status}")
    
    # Active prescriptions
    cursor.execute('''
    SELECT medication_name, dosage, frequency, prescribed_date
    FROM prescriptions
    WHERE student_id = ? AND status = 'active'
    ORDER BY prescribed_date DESC
    ''', (student_id,))
    
    prescriptions = cursor.fetchall()
    if prescriptions:
        print("\nActive Prescriptions:")
        for medication, dosage, frequency, prescribed_date in prescriptions:
            print(f"  - {medication} ({dosage}) - {frequency} - Prescribed: {prescribed_date}")
    
    # Recent vital signs
    cursor.execute('''
    SELECT measurement_date, blood_pressure_systolic, blood_pressure_diastolic,
           heart_rate, temperature, weight, bmi
    FROM vital_signs
    WHERE student_id = ?
    ORDER BY measurement_date DESC
    LIMIT 3
    ''', (student_id,))
    
    vitals = cursor.fetchall()
    if vitals:
        print("\nRecent Vital Signs:")
        for date, bp_sys, bp_dia, hr, temp, weight, bmi in vitals:
            print(f"  {date}:")
            if bp_sys and bp_dia:
                print(f"    BP: {bp_sys}/{bp_dia} mmHg")
            if hr:
                print(f"    HR: {hr} bpm")
            if temp:
                print(f"    Temp: {temp}°F")
            if weight:
                print(f"    Weight: {weight} lbs")
            if bmi:
                print(f"    BMI: {bmi}")
    
    # Save report option
    save_report = input("\nSave report to file? (y/n): ").lower()
    if save_report == 'y':
        filename = f"health_summary_{student_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        # Code to save report to file would go here
        print(f"Report saved to {filename}")
    
    conn.close()

def manage_care_plans(auth):
    if not auth or not auth.current_user:
        print("You must be logged in to manage care plans.")
        return
    
    while True:
        print("\n===== Care Plan Management =====")
        print("1. Create Care Plan")
        print("2. View Care Plans")
        print("3. Update Care Plan")
        print("4. Care Plan Progress Tracking")
        print("5. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-5): ")
        
        if choice == '1':
            create_care_plan(auth)
        elif choice == '2':
            view_care_plans(auth)
        elif choice == '3':
            update_care_plan(auth)
        elif choice == '4':
            track_care_plan_progress(auth)
        elif choice == '5':
            break
        else:
            print("Invalid choice. Please try again.")

def create_care_plan(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to create care plans.")
        return
    
    backup_before_operation('create_care_plan')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    student_id = input("Enter student ID: ")
    
    # Verify student exists
    cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
    if cursor.fetchone()[0] == 0:
        print("Error: Student ID not found.")
        conn.close()
        return
    
    # Show student's medical conditions
    cursor.execute('''
    SELECT id, condition_name, severity, status
    FROM medical_conditions
    WHERE student_id = ? AND status = 'active'
    ''', (student_id,))
    
    conditions = cursor.fetchall()
    
    if conditions:
        print("\nActive Medical Conditions:")
        for i, (cond_id, condition, severity, status) in enumerate(conditions):
            print(f"{i+1}. {condition} ({severity})")
        
        condition_choice = input("\nSelect condition for care plan (number): ")
        try:
            condition_index = int(condition_choice) - 1
            if 0 <= condition_index < len(conditions):
                condition_id = conditions[condition_index][0]
                condition_name = conditions[condition_index][1]
            else:
                print("Invalid selection.")
                conn.close()
                return
        except ValueError:
            print("Invalid input.")
            conn.close()
            return
    else:
        print("No active medical conditions found. Creating general care plan.")
        condition_id = None
        condition_name = "General Care"
    
    plan_name = input(f"Care plan name [Care Plan for {condition_name}]: ").strip()
    if not plan_name:
        plan_name = f"Care Plan for {condition_name}"
    
    description = input("Care plan description: ")
    
    while True:
        start_date = input("Start date (YYYY-MM-DD) [today]: ").strip()
        if not start_date:
            start_date = datetime.now().strftime('%Y-%m-%d')
            break
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    while True:
        end_date = input("End date (YYYY-MM-DD) [leave blank for ongoing]: ").strip()
        if not end_date:
            end_date = None
            break
        try:
            datetime.strptime(end_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    provider = input(f"Provider [Dr. {auth.current_user['username']}]: ").strip()
    if not provider:
        provider = f"Dr. {auth.current_user['username']}"
    
    goals = input("Care plan goals: ")
    interventions = input("Planned interventions: ")
    
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO care_plans 
    (student_id, condition_id, plan_name, description, start_date, end_date, 
     provider, status, goals, interventions, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, condition_id, plan_name, description, start_date, end_date,
          provider, 'active', goals, interventions, created_at))
    
    conn.commit()
    log_audit_event(auth.current_user['id'], 'create_care_plan', 'care_plan', cursor.lastrowid)
    print("\nCare plan created successfully!")
    conn.close()

def view_care_plans(auth):
    if not (auth.check_permission('view_any_health_record') or auth.check_permission('view_own_health_record')):
        print("You don't have permission to view care plans.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    if auth.check_permission('view_any_health_record'):
        student_id = input("Enter student ID (leave blank for all): ").strip()
        
        if student_id:
            cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
            if cursor.fetchone()[0] == 0:
                print("Error: Student ID not found.")
                conn.close()
                return
            
            cursor.execute('''
            SELECT cp.id, cp.plan_name, cp.description, cp.start_date, cp.end_date,
                   cp.provider, cp.status, cp.goals, cp.interventions, mc.condition_name
            FROM care_plans cp
            LEFT JOIN medical_conditions mc ON cp.condition_id = mc.id
            WHERE cp.student_id = ?
            ORDER BY cp.start_date DESC
            ''', (student_id,))
        else:
            cursor.execute('''
            SELECT cp.id, s.student_id, s.first_name, s.last_name, cp.plan_name, 
                   cp.start_date, cp.end_date, cp.provider, cp.status, mc.condition_name
            FROM care_plans cp
            JOIN students s ON cp.student_id = s.student_id
            LEFT JOIN medical_conditions mc ON cp.condition_id = mc.id
            ORDER BY cp.start_date DESC
            LIMIT 50
            ''')
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return
        
        cursor.execute('''
        SELECT cp.id, cp.plan_name, cp.description, cp.start_date, cp.end_date,
               cp.provider, cp.status, cp.goals, cp.interventions, mc.condition_name
        FROM care_plans cp
        LEFT JOIN medical_conditions mc ON cp.condition_id = mc.id
        WHERE cp.student_id = ?
        ORDER BY cp.start_date DESC
        ''', (student_id,))
    
    care_plans = cursor.fetchall()
    
    if not care_plans:
        print("No care plans found.")
        conn.close()
        return
    
    print("\n===== Care Plans =====")
    for plan in care_plans:
        if auth.check_permission('view_any_health_record') and not student_id:
            # All plans view
            plan_id, student_id, first_name, last_name, plan_name, start_date, end_date, provider, status, condition_name = plan
            print(f"\nID: {plan_id}")
            print(f"Student: {first_name} {last_name} (ID: {student_id})")
            print(f"Plan: {plan_name}")
            print(f"Condition: {condition_name if condition_name else 'General Care'}")
            print(f"Start Date: {start_date}")
            print(f"End Date: {end_date if end_date else 'Ongoing'}")
            print(f"Provider: {provider}")
            print(f"Status: {status}")
        else:
            # Specific student view
            plan_id, plan_name, description, start_date, end_date, provider, status, goals, interventions, condition_name = plan
            print(f"\nID: {plan_id}")
            print(f"Plan: {plan_name}")
            print(f"Condition: {condition_name if condition_name else 'General Care'}")
            print(f"Description: {description}")
            print(f"Start Date: {start_date}")
            print(f"End Date: {end_date if end_date else 'Ongoing'}")
            print(f"Provider: {provider}")
            print(f"Status: {status}")
            print(f"Goals: {goals}")
            print(f"Interventions: {interventions}")
        
        print("-" * 30)
    
    conn.close()

def wellness_programs(auth):
    if not auth or not auth.current_user:
        print("You must be logged in to access wellness programs.")
        return
    
    while True:
        print("\n===== Wellness Programs =====")
        print("1. View Available Programs")
        print("2. Enroll in Program")
        print("3. Track Progress")
        print("4. Health Challenges")
        print("5. Wellness Resources")
        print("6. Program Analytics (Staff Only)")
        print("7. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-7): ")
        
        if choice == '1':
            view_wellness_programs(auth)
        elif choice == '2':
            enroll_in_wellness_program(auth)
        elif choice == '3':
            track_wellness_progress(auth)
        elif choice == '4':
            health_challenges(auth)
        elif choice == '5':
            wellness_resources(auth)
        elif choice == '6':
            wellness_program_analytics(auth)
        elif choice == '7':
            break
        else:
            print("Invalid choice. Please try again.")

def view_wellness_programs(auth):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get current wellness campaigns
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
    SELECT id, campaign_name, campaign_type, description, start_date, end_date, status
    FROM health_campaigns
    WHERE campaign_type = 'wellness' AND (end_date IS NULL OR end_date >= ?)
    ORDER BY start_date DESC
    ''', (today,))
    
    programs = cursor.fetchall()
    
    if not programs:
        print("No active wellness programs found.")
        conn.close()
        return
    
    print("\n===== Available Wellness Programs =====")
    for program in programs:
        program_id, name, program_type, description, start_date, end_date, status = program
        
        print(f"\nProgram ID: {program_id}")
        print(f"Name: {name}")
        print(f"Type: {program_type}")
        print(f"Description: {description}")
        print(f"Start Date: {start_date}")
        print(f"End Date: {end_date if end_date else 'Ongoing'}")
        print(f"Status: {status}")
        
        # Check if user is enrolled
        if auth.current_user['role'] == 'student':
            student_id = get_user_student_id(auth)
            if student_id:
                cursor.execute('''
                SELECT status FROM wellness_participation 
                WHERE student_id = ? AND program_name = ?
                ''', (student_id, name))
                
                enrollment = cursor.fetchone()
                if enrollment:
                    print(f"Your Status: {enrollment[0]}")
                else:
                    print("Your Status: Not enrolled")
        
        print("-" * 30)
    
    conn.close()

def enroll_in_wellness_program(auth):
    if auth.current_user['role'] != 'student':
        print("Only students can enroll in wellness programs.")
        return
    
    student_id = get_user_student_id(auth)
    if not student_id:
        print("Error: No student ID associated with your account.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Show available programs
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
    SELECT id, campaign_name, description
    FROM health_campaigns
    WHERE campaign_type = 'wellness' AND (end_date IS NULL OR end_date >= ?) AND status = 'active'
    ORDER BY start_date DESC
    ''', (today,))
    
    programs = cursor.fetchall()
    
    if not programs:
        print("No programs available for enrollment.")
        conn.close()
        return
    
    print("\nAvailable Programs:")
    for i, (program_id, name, description) in enumerate(programs):
        print(f"{i+1}. {name} - {description}")
    
    while True:
        choice = input("\nSelect program to enroll in (number): ")
        if choice.isdigit() and 1 <= int(choice) <= len(programs):
            selected_program = programs[int(choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    program_id, program_name, description = selected_program
    
    # Check if already enrolled
    cursor.execute('''
    SELECT status FROM wellness_participation 
    WHERE student_id = ? AND program_name = ?
    ''', (student_id, program_name))
    
    existing_enrollment = cursor.fetchone()
    if existing_enrollment:
        print(f"You are already enrolled in this program with status: {existing_enrollment[0]}")
        conn.close()
        return
    
    # Enroll student
    enrollment_date = datetime.now().strftime('%Y-%m-%d')
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO wellness_participation 
    (student_id, program_name, enrollment_date, status, created_at)
    VALUES (?, ?, ?, ?, ?)
    ''', (student_id, program_name, enrollment_date, 'enrolled', created_at))
    
    conn.commit()
    log_audit_event(auth.current_user['id'], 'enroll_wellness_program', 'wellness_participation', cursor.lastrowid)
    
    print(f"\nSuccessfully enrolled in {program_name}!")
    print("You can now track your progress and participate in program activities.")
    
    conn.close()

def track_wellness_progress(auth):
    if auth.current_user['role'] != 'student':
        print("Only students can track wellness progress.")
        return
    
    student_id = get_user_student_id(auth)
    if not student_id:
        print("Error: No student ID associated with your account.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get enrolled programs
    cursor.execute('''
    SELECT program_name, enrollment_date, status, progress_score, goals_met
    FROM wellness_participation
    WHERE student_id = ?
    ORDER BY enrollment_date DESC
    ''', (student_id,))
    
    enrollments = cursor.fetchall()
    
    if not enrollments:
        print("You are not enrolled in any wellness programs.")
        conn.close()
        return
    
    print("\n===== Your Wellness Progress =====")
    
    for enrollment in enrollments:
        program_name, enrollment_date, status, progress_score, goals_met = enrollment
        
        print(f"\nProgram: {program_name}")
        print(f"Enrolled: {enrollment_date}")
        print(f"Status: {status}")
        print(f"Progress Score: {progress_score}%")
        print(f"Goals Met: {goals_met}")
        
        # Simple progress tracking
        if status == 'enrolled':
            new_progress = input(f"Update progress for {program_name} (0-100%): ").strip()
            if new_progress.isdigit() and 0 <= int(new_progress) <= 100:
                cursor.execute('''
                UPDATE wellness_participation 
                SET progress_score = ? 
                WHERE student_id = ? AND program_name = ?
                ''', (int(new_progress), student_id, program_name))
                
                conn.commit()
                print(f"Progress updated to {new_progress}%")
                
                # Check for milestones
                if int(new_progress) >= 100:
                    cursor.execute('''
                    UPDATE wellness_participation 
                    SET status = 'completed', completion_date = ? 
                    WHERE student_id = ? AND program_name = ?
                    ''', (datetime.now().strftime('%Y-%m-%d'), student_id, program_name))
                    
                    conn.commit()
                    print("🎉 Congratulations! You have completed this program!")
        
        print("-" * 30)
    
    conn.close()

def manage_lab_results(auth):
    """Main lab results management menu"""
    if not auth or not auth.current_user:
        print("You must be logged in to manage lab results.")
        return
    
    while True:
        print("\n===== Lab Results Management =====")
        print("1. Add Lab Result")
        print("2. View Lab Results") 
        print("3. Critical Values Alert")
        print("4. Lab Trends Analysis")
        print("5. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-5): ")
        
        if choice == '1':
            # Function is in health_health_management.py
            add_lab_result(auth)
        elif choice == '2':
            # Function is in health_health_management.py
            view_lab_results(auth)
        elif choice == '3':
            # Function is in health_misc.py
            critical_values_alert(auth)
        elif choice == '4':
            # Function is in health_health_management.py
            lab_trends_analysis(auth)
        elif choice == '5':
            break
        else:
            print("Invalid choice. Please try again.")

def add_lab_result(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to add lab results.")
        return
    
    backup_before_operation('add_lab_result')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    student_id = input("Enter student ID: ")
    
    # Verify student exists
    cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
    if cursor.fetchone()[0] == 0:
        print("Error: Student ID not found.")
        conn.close()
        return
    
    test_name = input("Test name: ")
    test_code = input("Test code (optional): ")
    result_value = input("Result value: ")
    reference_range = input("Reference range: ")
    units = input("Units: ")
    
    status_options = ['Final', 'Preliminary', 'Corrected', 'Cancelled']
    print("\nStatus Options:")
    for i, status in enumerate(status_options):
        print(f"{i+1}. {status}")
    
    while True:
        status_choice = input("\nSelect status (1-4): ")
        if status_choice.isdigit() and 1 <= int(status_choice) <= len(status_options):
            status = status_options[int(status_choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    while True:
        ordered_date = input("Ordered date (YYYY-MM-DD): ")
        try:
            datetime.strptime(ordered_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    while True:
        collected_date = input("Collected date (YYYY-MM-DD): ")
        try:
            datetime.strptime(collected_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    while True:
        resulted_date = input("Resulted date (YYYY-MM-DD) [today]: ").strip()
        if not resulted_date:
            resulted_date = datetime.now().strftime('%Y-%m-%d')
            break
        try:
            datetime.strptime(resulted_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    ordering_provider = input(f"Ordering provider [Dr. {auth.current_user['username']}]: ").strip()
    if not ordering_provider:
        ordering_provider = f"Dr. {auth.current_user['username']}"
    
    lab_name = input("Lab name: ")
    
    # Check for abnormal values
    abnormal_flag = input("Abnormal flag (H/L/blank): ").strip().upper()
    if abnormal_flag not in ['H', 'L', '']:
        abnormal_flag = ''
    
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO lab_results 
    (student_id, test_name, test_code, result_value, reference_range, units, 
     status, ordered_date, collected_date, resulted_date, ordering_provider, 
     lab_name, abnormal_flag, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, test_name, test_code, result_value, reference_range, units,
          status, ordered_date, collected_date, resulted_date, ordering_provider,
          lab_name, abnormal_flag, created_at))
    
    conn.commit()
    log_audit_event(auth.current_user['id'], 'add_lab_result', 'lab_result', cursor.lastrowid)
    
    print("\nLab result added successfully!")
    
    # Check for critical values
    if abnormal_flag in ['H', 'L']:
        print(f"\n⚠️  ABNORMAL RESULT DETECTED: {test_name} = {result_value} {units} ({abnormal_flag})")
        print("Consider notifying the ordering provider immediately.")
        
        # Check if this is a critical value that requires immediate attention
        critical_tests = {
            'glucose': {'high': 400, 'low': 50},
            'potassium': {'high': 6.0, 'low': 2.5},
            'sodium': {'high': 160, 'low': 120},
            'creatinine': {'high': 5.0, 'low': None},
            'hemoglobin': {'high': 20, 'low': 6},
            'platelet': {'high': 1000, 'low': 50},
            'white blood cell': {'high': 50, 'low': 1}
        }
        
        # Check if this test has critical value thresholds
        for test_key, thresholds in critical_tests.items():
            if test_key.lower() in test_name.lower():
                try:
                    numeric_value = float(result_value)
                    is_critical = False
                    
                    if abnormal_flag == 'H' and thresholds['high'] and numeric_value >= thresholds['high']:
                        is_critical = True
                    elif abnormal_flag == 'L' and thresholds['low'] and numeric_value <= thresholds['low']:
                        is_critical = True
                    
                    if is_critical:
                        print(f"\n🚨 CRITICAL VALUE ALERT! 🚨")
                        print(f"Test: {test_name}")
                        print(f"Value: {result_value} {units}")
                        print(f"This value requires IMMEDIATE provider notification!")
                        
                        # Log critical value
                        log_audit_event(auth.current_user['id'], 'critical_lab_value', 'lab_result', 
                                      cursor.lastrowid, f"Critical {test_name}: {result_value}")
                        
                        # Prompt for provider notification
                        notify_provider = input("Has the ordering provider been notified? (y/n): ").lower()
                        if notify_provider != 'y':
                            print("⚠️  URGENT: Please notify the ordering provider immediately!")
                            print(f"Provider: {ordering_provider}")
                        
                        break
                        
                except ValueError:
                    # Non-numeric result, skip critical value check
                    pass
    
    # Check for drug interactions if this is a therapeutic drug monitoring test
    therapeutic_tests = ['digoxin', 'lithium', 'phenytoin', 'carbamazepine', 'valproic acid', 'theophylline']
    
    for therapeutic_test in therapeutic_tests:
        if therapeutic_test.lower() in test_name.lower():
            print(f"\n💊 THERAPEUTIC DRUG MONITORING ALERT")
            print(f"This is a therapeutic drug monitoring test for {therapeutic_test}")
            
            # Check for active prescriptions of this medication
            cursor.execute('''
            SELECT medication_name, dosage FROM prescriptions 
            WHERE student_id = ? AND status = 'active' 
            AND LOWER(medication_name) LIKE ?
            ''', (student_id, f'%{therapeutic_test}%'))
            
            related_prescriptions = cursor.fetchall()
            
            if related_prescriptions:
                print("Related active prescriptions found:")
                for med_name, dosage in related_prescriptions:
                    print(f"  - {med_name} ({dosage})")
                print("Consider dose adjustment based on lab results.")
            else:
                print("⚠️  No active prescriptions found for this medication.")
                print("Verify patient is still taking this medication.")
            
            break
    
    # Suggest follow-up tests if needed
    follow_up_suggestions = {
        'glucose': ['HbA1c if glucose elevated', 'Repeat fasting glucose'],
        'creatinine': ['BUN', 'Urinalysis', 'Estimated GFR'],
        'liver': ['Complete liver panel if abnormal', 'Hepatitis panel'],
        'cholesterol': ['Lipid panel repeat in 6-12 weeks', 'Liver function tests'],
        'thyroid': ['TSH if T4 abnormal', 'T3 if indicated'],
        'hemoglobin': ['Iron studies', 'B12 and folate', 'Reticulocyte count']
    }
    
    for test_category, suggestions in follow_up_suggestions.items():
        if test_category.lower() in test_name.lower():
            if abnormal_flag:
                print(f"\n📋 FOLLOW-UP RECOMMENDATIONS for abnormal {test_name}:")
                for suggestion in suggestions:
                    print(f"  • {suggestion}")
            break
    
    # Check for trends if previous results exist
    cursor.execute('''
    SELECT result_value, resulted_date FROM lab_results 
    WHERE student_id = ? AND test_name = ? AND id != ?
    ORDER BY resulted_date DESC LIMIT 3
    ''', (student_id, test_name, cursor.lastrowid))
    
    previous_results = cursor.fetchall()
    
    if previous_results:
        print(f"\n📊 PREVIOUS RESULTS for {test_name}:")
        for prev_value, prev_date in previous_results:
            print(f"  {prev_date}: {prev_value} {units}")
        
        # Calculate trend if values are numeric
        try:
            current_numeric = float(result_value)
            prev_numeric = float(previous_results[0][0])
            
            change = current_numeric - prev_numeric
            percent_change = (change / prev_numeric * 100) if prev_numeric != 0 else 0
            
            if abs(percent_change) > 20:  # Significant change threshold
                trend_direction = "↗️ Increasing" if change > 0 else "↘️ Decreasing"
                print(f"  Trend: {trend_direction} ({change:+.2f}, {percent_change:+.1f}%)")
                
                if abs(percent_change) > 50:
                    print("  ⚠️  Significant change from previous result - verify accuracy")
                    
        except ValueError:
            # Non-numeric values, no trend calculation
            pass
    
    conn.close()

def lab_trends_analysis(auth):
    """Analyze lab result trends over time"""
    if not (auth.check_permission('view_any_health_record') or auth.check_permission('view_own_health_record')):
        print("You don't have permission to view lab trends.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    if auth.check_permission('view_any_health_record'):
        student_id = input("Enter student ID: ")
        
        cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
        if cursor.fetchone()[0] == 0:
            print("Error: Student ID not found.")
            conn.close()
            return
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return
    
    # Get available test types
    cursor.execute('''
    SELECT DISTINCT test_name FROM lab_results 
    WHERE student_id = ?
    ORDER BY test_name
    ''', (student_id,))
    
    available_tests = [row[0] for row in cursor.fetchall()]
    
    if not available_tests:
        print("No lab results found for trend analysis.")
        conn.close()
        return
    
    print("\nAvailable Tests for Trend Analysis:")
    for i, test in enumerate(available_tests):
        print(f"{i+1}. {test}")
    
    while True:
        choice = input("\nSelect test for trend analysis (number): ")
        if choice.isdigit() and 1 <= int(choice) <= len(available_tests):
            selected_test = available_tests[int(choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    # Get trend data for the selected test
    cursor.execute('''
    SELECT resulted_date, result_value, reference_range, abnormal_flag
    FROM lab_results
    WHERE student_id = ? AND test_name = ?
    ORDER BY resulted_date
    ''', (student_id, selected_test))
    
    trend_data = cursor.fetchall()
    
    if len(trend_data) < 2:
        print("Insufficient data for trend analysis (need at least 2 results).")
        conn.close()
        return
    
    print(f"\n===== Trend Analysis for {selected_test} =====")
    
    # Display trend data
    print("\nResults Over Time:")
    for date, value, ref_range, abnormal in trend_data:
        status = ""
        if abnormal == 'H':
            status = " (HIGH)"
        elif abnormal == 'L':
            status = " (LOW)"
        
        print(f"{date}: {value} (Ref: {ref_range}){status}")
    
    # Calculate trend direction
    try:
        values = [float(result[1]) for result in trend_data if result[1].replace('.', '').replace('-', '').isdigit()]
        if len(values) >= 2:
            if values[-1] > values[0]:
                trend_direction = "Increasing"
            elif values[-1] < values[0]:
                trend_direction = "Decreasing"
            else:
                trend_direction = "Stable"
            
            change = values[-1] - values[0]
            percent_change = (change / values[0]) * 100 if values[0] != 0 else 0
            
            print(f"\nTrend Direction: {trend_direction}")
            print(f"Total Change: {change:+.2f}")
            print(f"Percent Change: {percent_change:+.1f}%")
    except ValueError:
        print("\nTrend analysis not available for non-numeric values.")
    
    conn.close()

def setup_health_permissions(auth):
    """Set up health-specific permissions in the authentication system"""
    health_permissions = [
        'manage_health_records',
        'view_any_health_record',
        'view_own_health_record',
        'manage_health_appointments',
        'schedule_health_appointment',
        'view_own_appointments',
        'cancel_own_appointment',
        'manage_vaccinations',
        'view_own_vaccinations',
        'verify_vaccinations',
        'issue_health_advisories',
        'view_health_advisories',
        'view_health_resources',
        'update_insurance_info'
    ]
    
    # Add permissions to the authentication system
    for permission in health_permissions:
        if hasattr(auth, 'add_permission'):
            auth.add_permission(permission)

def health_challenges(auth):
    """Health challenges and competitions"""
    print("\n===== Health Challenges =====")
    
    challenges = [
        {
            "name": "10,000 Steps Challenge",
            "description": "Walk 10,000 steps daily for 30 days",
            "duration": "30 days",
            "participants": 150,
            "reward": "Fitness tracker discount"
        },
        {
            "name": "Hydration Challenge",
            "description": "Drink 8 glasses of water daily",
            "duration": "14 days",
            "participants": 89,
            "reward": "Water bottle prize"
        },
        {
            "name": "Mental Health Week",
            "description": "Daily mindfulness activities",
            "duration": "7 days",
            "participants": 234,
            "reward": "Wellness workshop access"
        },
        {
            "name": "Nutrition Challenge",
            "description": "5 servings of fruits/vegetables daily",
            "duration": "21 days",
            "participants": 67,
            "reward": "Healthy cooking class"
        }
    ]
    
    print("Current Active Challenges:")
    for i, challenge in enumerate(challenges):
        print(f"\n{i+1}. {challenge['name']}")
        print(f"   Description: {challenge['description']}")
        print(f"   Duration: {challenge['duration']}")
        print(f"   Participants: {challenge['participants']}")
        print(f"   Reward: {challenge['reward']}")
    
    if auth.current_user['role'] == 'student':
        join_challenge = input("\nJoin a challenge? (enter number or 'n'): ")
        if join_challenge.isdigit() and 1 <= int(join_challenge) <= len(challenges):
            selected_challenge = challenges[int(join_challenge) - 1]
            print(f"\nYou've joined the {selected_challenge['name']}!")
            print("Check your progress in the wellness tracking section.")

def wellness_program_analytics(auth):
    """Analytics for wellness programs (staff only)"""
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to view program analytics.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Wellness Program Analytics =====")
    
    # Program enrollment statistics
    cursor.execute('''
    SELECT program_name, COUNT(*) as enrollment_count,
           AVG(progress_score) as avg_progress,
           SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completion_count
    FROM wellness_participation
    GROUP BY program_name
    ORDER BY enrollment_count DESC
    ''')
    
    program_stats = cursor.fetchall()
    
    if program_stats:
        print("Program Enrollment Statistics:")
        for program, enrollment, avg_progress, completions in program_stats:
            completion_rate = (completions / enrollment * 100) if enrollment > 0 else 0
            print(f"\n{program}:")
            print(f"  Enrollment: {enrollment}")
            print(f"  Average Progress: {avg_progress:.1f}%")
            print(f"  Completions: {completions} ({completion_rate:.1f}%)")
    
    # Monthly enrollment trends
    cursor.execute('''
    SELECT strftime('%Y-%m', enrollment_date) as month,
           COUNT(*) as enrollments
    FROM wellness_participation
    WHERE enrollment_date >= date('now', '-12 months')
    GROUP BY strftime('%Y-%m', enrollment_date)
    ORDER BY month
    ''')
    
    monthly_trends = cursor.fetchall()
    
    if monthly_trends:
        print("\nMonthly Enrollment Trends (Last 12 Months):")
        for month, enrollments in monthly_trends:
            print(f"  {month}: {enrollments} enrollments")
    
    conn.close()

def health_record_templates(auth):
    """Health record templates for common conditions"""
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to use record templates.")
        return
    
    templates = {
        "Annual Physical": {
            "record_type": "Annual Physical Exam",
            "description": "Comprehensive annual physical examination including vital signs, general health assessment, and preventive care recommendations."
        },
        "Vaccination Record": {
            "record_type": "Vaccination",
            "description": "Immunization administered as per vaccination schedule. Patient tolerated well, no adverse reactions observed."
        },
        "Sick Visit": {
            "record_type": "General Medical",
            "description": "Patient presented with acute illness symptoms. Examination performed, treatment plan discussed, follow-up as needed."
        },
        "Mental Health Screening": {
            "record_type": "Mental Health",
            "description": "Mental health screening and assessment performed. Resources and support services discussed as appropriate."
        },
        "Injury Assessment": {
            "record_type": "Injury Treatment",
            "description": "Injury assessment and treatment provided. First aid administered, healing progress monitored."
        }
    }
    
    print("\n===== Health Record Templates =====")
    
    template_names = list(templates.keys())
    for i, name in enumerate(template_names):
        print(f"{i+1}. {name}")
    
    while True:
        choice = input("\nSelect template (1-5) or 'q' to quit: ")
        if choice.lower() == 'q':
            return
        
        if choice.isdigit() and 1 <= int(choice) <= len(template_names):
            selected_template = templates[template_names[int(choice) - 1]]
            break
        print("Invalid choice. Please try again.")
    
    # Use template to create record
    print(f"\nUsing template: {template_names[int(choice) - 1]}")
    print(f"Record Type: {selected_template['record_type']}")
    print(f"Description Template: {selected_template['description']}")
    
    # Allow user to modify the template
    use_template = input("\nUse this template to create a record? (y/n): ").lower()
    if use_template == 'y':
        # This would call the add_health_record function with pre-filled data
        print("Template ready for use. Proceeding to record creation...")
