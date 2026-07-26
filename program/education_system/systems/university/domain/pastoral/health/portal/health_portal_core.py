from education_system.systems.university.infrastructure.database.db import sqlite3, DatabaseManager, get_connection
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
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth
from education_system.systems.university.infrastructure.i18n import (
    get_text,
    get_current_language,
)
from education_system.systems.university.infrastructure.utils.language_selector import (
    display_language_menu_option,
)
from education_system.systems.university.infrastructure.database.data_backup import backup_before_operation
from education_system.systems.university.infrastructure.email import (
    send_appointment_confirmation,
    send_health_notification,
)
from education_system.systems.university.infrastructure.logging.log_config import configure_logging
from education_system.systems.university.domain.pastoral.health.services.health_context import cipher_suite

# Configure logging for audit trail
audit_logger = configure_logging(name=__name__)

# Encryption key management
# Optional import for health security features
try:
    from education_system.systems.university.domain.pastoral.health.portal.data_privacy import advanced_security_menu, user_session_management, ip_restriction_management, two_factor_authentication_setup, integration_management, api_key_management, integration_health_check, add_missing_menu_integrations, generate_security_report, population_risk_analysis, review_security_settings, update_security_settings, assess_contact_risk, security_audit_menu, view_audit_log, health_risk_assessment, conduct_risk_assessment, calculate_risk_score, get_risk_factors, generate_risk_recommendations
except ImportError:
    # Provide fallback functions if health_security module is not available
    def advanced_security_menu(*args, **kwargs): print("Advanced security features not available")
    def user_session_management(*args, **kwargs): print("User session management not available")
    def ip_restriction_management(*args, **kwargs): print("IP restriction management not available")
    def two_factor_authentication_setup(*args, **kwargs): print("2FA setup not available")
    def integration_management(*args, **kwargs): print("Integration management not available")
    def api_key_management(*args, **kwargs): print("API key management not available")
    def integration_health_check(*args, **kwargs): print("Integration health check not available")
    def add_missing_menu_integrations(*args, **kwargs): print("Menu integrations not available")
    def generate_security_report(*args, **kwargs): print("Security report generation not available")
    def population_risk_analysis(*args, **kwargs): print("Population risk analysis not available")
    def review_security_settings(*args, **kwargs): print("Security settings review not available")
    def update_security_settings(*args, **kwargs): print("Security settings update not available")
    def assess_contact_risk(*args, **kwargs): return "low"
    def security_audit_menu(*args, **kwargs): print("Security audit menu not available")
    def view_audit_log(*args, **kwargs): print("Audit log viewing not available")
    def health_risk_assessment(*args, **kwargs): print("Health risk assessment not available")
    def conduct_risk_assessment(*args, **kwargs): return {}
    def calculate_risk_score(*args, **kwargs): return 0
    def get_risk_factors(*args, **kwargs): return []
    def generate_risk_recommendations(*args, **kwargs): return []
from education_system.systems.university.domain.pastoral.health.records.data_purge  import update_retention_policy, archive_old_data, data_purge_menu, view_purgeable_data, purge_expired_data, retention_compliance_report, compliance_monitoring, data_retention_management, view_retention_policies, custom_data_purge
from education_system.systems.university.domain.pastoral.health.records.quality_assurance  import generate_quality_metrics_report, clinical_quality_indicators, quality_assurance_menu, data_quality_metrics, show_quality_metrics
from education_system.systems.university.domain.pastoral.health.records.backup_export  import export_vaccination_records, export_appointment_data, export_lab_results, export_custom_dataset, restore_from_backup, manage_backup_schedule, backup_recovery_menu, create_database_backup, view_backup_history, export_data_menu, export_health_records, bulk_import_records
from education_system.systems.university.domain.pastoral.health.appointments.appointment_booking  import manage_provider_schedules, add_provider_schedule, view_provider_schedules, show_upcoming_appointments, provider_dashboard, todays_schedule, manage_screening_schedules, create_screening_schedule, schedule_screening_appointment, manage_provider_time_off, schedule_templates, provider_availability_report, update_provider_schedule, provider_statistics, schedule_appointment, view_appointments, update_appointment_status, generate_provider_utilization_report, generate_appointment_schedule_report, generate_provider_performance_report, show_appointment_utilization_stats, analyze_provider_workload
from education_system.systems.university.domain.pastoral.health.records.admin.advisories import add_health_advisory, view_health_advisories
from education_system.systems.university.domain.pastoral.health.records.admin.permissions import manage_health_records_enhanced, setup_health_permissions
from education_system.systems.university.domain.pastoral.health.records.analytics.population import generate_population_health_report, show_population_health_metrics, generate_student_health_summary
from education_system.systems.university.domain.pastoral.health.records.analytics.quality import patient_safety_metrics
from education_system.systems.university.domain.pastoral.health.records.analytics.reports import generate_public_health_report
from education_system.systems.university.domain.pastoral.health.records.analytics.trends import generate_health_condition_analysis, health_analytics_dashboard, analyze_health_trends
from education_system.systems.university.domain.pastoral.health.records.clinical.allergies import add_allergy, update_allergy, delete_allergy
from education_system.systems.university.domain.pastoral.health.records.clinical.care_plans import manage_care_plans, create_care_plan, view_care_plans, update_care_plan, track_care_plan_progress
from education_system.systems.university.domain.pastoral.health.records.clinical.conditions import manage_medical_conditions, add_medical_condition, view_medical_conditions, update_condition_status, condition_management_plans
from education_system.systems.university.domain.pastoral.health.records.clinical.lab_results import manage_lab_results, add_lab_result, view_lab_results, lab_trends_analysis, recent_lab_results_dashboard
from education_system.systems.university.domain.pastoral.health.records.clinical.prescriptions import manage_prescriptions, add_prescription, view_prescriptions, update_prescription_status
from education_system.systems.university.domain.pastoral.health.records.records.crud import add_health_record, view_health_records, update_health_record, delete_health_record
from education_system.systems.university.domain.pastoral.health.records.records.reports import generate_health_report
from education_system.systems.university.domain.pastoral.health.records.records.templates import enhanced_health_record_templates, health_record_templates
from education_system.systems.university.domain.pastoral.health.records.referrals.referrals import manage_referrals, create_referral, view_referrals, update_referral_status, referral_followup, referral_reports
from education_system.systems.university.domain.pastoral.health.records.screening.guidelines import screening_guidelines, screening_recommendations
from education_system.systems.university.domain.pastoral.health.records.screening.reminders import screening_reminders, population_screening_reports
from education_system.systems.university.domain.pastoral.health.records.screening.results import record_screening_results
from education_system.systems.university.domain.pastoral.health.records.screening.schedules import calculate_screening_due_date, calculate_next_screening_date, view_due_screenings, overdue_screenings
from education_system.systems.university.domain.pastoral.health.records.student.dashboard import student_health_dashboard, show_personal_health_summary, show_health_reminders
from education_system.systems.university.domain.pastoral.health.records.student.insurance import view_insurance_info, update_insurance_info
from education_system.systems.university.domain.pastoral.health.records.student.resources import student_health_resources, view_health_resources
from education_system.systems.university.domain.pastoral.health.records.student.wellness import manage_wellness_goals, track_personal_metrics, quick_wellness_assessment
from education_system.systems.university.domain.pastoral.health.records.vaccinations.management import record_vaccination, view_vaccinations, verify_vaccination
from education_system.systems.university.domain.pastoral.health.records.vaccinations.reports import generate_vaccination_analysis_report, generate_vaccination_status_report, generate_vaccination_coverage_report
from education_system.systems.university.domain.pastoral.health.records.vaccinations.tracking import immunization_status, vaccination_due_list
from education_system.systems.university.domain.pastoral.health.records.wellness.challenges import health_challenges
from education_system.systems.university.domain.pastoral.health.records.wellness.programs import wellness_programs, view_wellness_programs, enroll_in_wellness_program, track_wellness_progress, wellness_program_analytics
from education_system.systems.university.domain.pastoral.health.records.wellness.resources import wellness_resources
from education_system.systems.university.domain.pastoral.health.services  import block_time_slots, patient_queue, critical_alerts_dashboard, pending_tasks, quick_patient_lookup, external_system_connections, use_existing_template, create_new_template, template_usage_statistics, specialist_directory, emergency_information, get_user_student_id, view_failed_logins, generate_disease_surveillance_report, analyze_data_access_patterns, update_emergency_contact, delete_emergency_contact, manage_contact_hierarchy, conduct_contact_tracing, investigate_outbreak, analyze_disease_trends, performance_improvement, manage_allergies, critical_values_alert, view_allergies, check_drug_interactions, check_basic_interactions, track_medication_adherence, manage_refill_reminders, manage_vital_signs, record_vital_signs, check_vital_signs_alerts, view_vital_signs, view_vital_signs_trends, calculate_bmi, generate_custom_report, manage_emergency_contacts, add_emergency_contact, view_emergency_contacts, disease_surveillance_system, report_disease_case, view_disease_cases, validate_csv_format

class SecurityManager:
    @staticmethod
    def check_session_timeout(auth):
        """Check if user session has timed out"""
        if not auth or not auth.current_user:
            return True

        # Get session timeout from security settings
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
            SELECT setting_value FROM security_settings
            WHERE setting_name = 'session_timeout_minutes'
            ''')
            result = cursor.fetchone()
            timeout_minutes = int(result[0]) if result else 30
            conn.close()

            # Check if session has timed out
            # This would need to be implemented based on your auth system
            # For now, return False to disable timeout checking
            return False

        except Exception:
            # If we can't check, don't timeout
            return False

def get_or_create_encryption_key():
    """Get or create encryption key for sensitive data"""
    key_file = 'health_encryption.key'
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(key_file, 'wb') as f:
            f.write(key)
        os.chmod(key_file, 0o600)
        return key

def encrypt_sensitive_data(data):
    """Encrypt sensitive health data"""
    if data is None:
        return None
    return cipher_suite.encrypt(str(data).encode()).decode()

def decrypt_sensitive_data(encrypted_data):
    """Decrypt sensitive health data"""
    if encrypted_data is None:
        return None
    try:
        return cipher_suite.decrypt(encrypted_data.encode()).decode()
    except Exception:
        return encrypted_data  # Return as-is if decryption fails (backwards compatibility)

def log_audit_event(user_id, action, resource_type, resource_id, details=None):
    """Log audit events for compliance"""
    audit_logger.info(f"USER:{user_id} ACTION:{action} RESOURCE:{resource_type}:{resource_id} DETAILS:{details}")

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
            created_at TEXT,
            retention_period_months INTEGER,
            deletion_method TEXT DEFAULT 'soft',
            last_cleanup_date TEXT,
            is_active BOOLEAN DEFAULT 1,
            updated_at TEXT
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

        # Create health_appointments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            appointment_type TEXT,
            appointment_date TEXT,
            appointment_time TEXT,
            provider TEXT,
            reason TEXT,
            status TEXT DEFAULT 'scheduled',
            notes TEXT,
            scheduled_at TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Create vaccination_records table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS vaccination_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            vaccine_name TEXT,
            administered_date TEXT,
            expiry_date TEXT,
            lot_number TEXT,
            manufacturer TEXT,
            administered_by TEXT,
            location TEXT,
            adverse_reaction INTEGER DEFAULT 0,
            reaction_description TEXT,
            verified INTEGER DEFAULT 0,
            verified_by TEXT,
            verified_date TEXT,
            created_at TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id)
        )
        ''')

        # Create health_advisories table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_advisories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            advisory_type TEXT,
            content TEXT,
            priority TEXT,
            target_audience TEXT,
            effective_date TEXT,
            expiry_date TEXT,
            issued_by TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT
        )
        ''')

        # Create insurance_information table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS insurance_information (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            insurance_provider TEXT,
            policy_number TEXT,
            group_number TEXT,
            subscriber_name TEXT,
            relationship_to_subscriber TEXT,
            effective_date TEXT,
            expiry_date TEXT,
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

# Mental Health Helper Functions
def _launch_wellness_cli(auth):
    """Launch the student affairs mental health and wellness hub."""
    try:
        from education_system.systems.university.interfaces.cli.pastoral.wellbeing.wellness.wellness_cli import WellnessCLI
        cli = WellnessCLI()
        cli.auth = auth
        cli.main_menu()
    except ImportError as e:
        print(f"\nMental Health & Wellness Hub is not available: {e}")
        input("Press Enter to continue...")

def _display_crisis_hotline_info():
    """Display crisis hotline and emergency mental health resources"""
    print("\n🚨 CRISIS HOTLINE INFORMATION")
    print("="*50)
    print("\n24/7 Crisis Support:")
    print("  • National Suicide Prevention Lifeline: 988")
    print("  • Crisis Text Line: Text HOME to 741741")
    print("  • National Domestic Violence Hotline: 1-800-799-7233")
    print("\nCampus Resources:")
    print("  • Campus Counseling Center: [Contact your university]")
    print("  • Campus Security (Emergency): [Contact your university]")
    print("  • Student Health Services: [Contact your university]")
    print("\nInternational:")
    print("  • International Association for Suicide Prevention")
    print("    https://www.iasp.info/resources/Crisis_Centres/")
    print("\n⚠️ If you or someone you know is in immediate danger, call 911")
    print("="*50)

def _launch_dentist_cli():
    """Launch the Dental Clinic CLI from within the health portal."""
    try:
        from education_system.systems.university.domain.pastoral.health.portal.dentist_cli import dentist_menu
        dentist_menu()
    except ImportError as e:
        print(f"\n❌ Dental Clinic CLI not available: {e}")
        input("Press Enter to continue...")


def display_health_portal_menu(auth=None):
    if not auth:
        from education_system.systems.university.infrastructure.auth import UserAuth
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
            print(get_text('health.login_required', default="\nYou must be logged in to access the Enhanced Health Portal."))
            return auth

        # Check session timeout
        if SecurityManager.check_session_timeout(auth):
            print(get_text('health.session_timeout', default="\nSession timed out. Please log in again."))
            auth.logout()
            return auth

        print(f"\n===== {get_text('health.title', default='Enhanced University Health Portal')} =====")
        print(get_text('health.logged_in', default='Logged in as: {username} ({role})').format(username=auth.current_user['username'], role=auth.current_user['role']))

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

        # Wellness & Prevention (including Mental Health)
        print("\n🌟 Wellness & Prevention:")

        print(f"{len(menu_options) + 1}. Wellness Programs")
        menu_options.append(("Wellness Programs", wellness_programs))

        if auth.check_permission('view_health_resources'):
            print(f"{len(menu_options) + 1}. Health Resources")
            menu_options.append(("Health Resources", view_health_resources))

        # Mental Health & Wellness Options
        print("\n🧠 Mental Health & Wellness:")

        print(f"{len(menu_options) + 1}. Schedule Counseling Appointment")
        menu_options.append(("Schedule Counseling Appointment", _launch_wellness_cli))

        print(f"{len(menu_options) + 1}. Wellness Check-in")
        menu_options.append(("Wellness Check-in", _launch_wellness_cli))

        print(f"{len(menu_options) + 1}. Peer Support Matching")
        menu_options.append(("Peer Support Matching", _launch_wellness_cli))

        print(f"{len(menu_options) + 1}. Mindfulness & Meditation Resources")
        menu_options.append(("Mindfulness & Meditation", _launch_wellness_cli))

        print(f"{len(menu_options) + 1}. Crisis Hotline Information")
        menu_options.append(("Crisis Hotline Information", lambda auth: _display_crisis_hotline_info()))

        print(f"{len(menu_options) + 1}. View Counselor Profiles")
        menu_options.append(("View Counselor Profiles", _launch_wellness_cli))

        print(f"{len(menu_options) + 1}. Track Wellness Progress")
        menu_options.append(("Track Wellness Progress", _launch_wellness_cli))

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

        # Health Services
        print("\n🦷 Health Services:")
        print(f"{len(menu_options) + 1}. Dental Clinic")
        menu_options.append(("Dental Clinic", lambda auth: _launch_dentist_cli()))

        # Main menu options
        print(f"\n⚙️ {get_text('health.system_options', default='System Options')}:")
        print(f"{len(menu_options) + 1}. {get_text('health.menu.language', default='Language')}")
        print(f"{len(menu_options) + 2}. {get_text('health.menu.return_main', default='Return to Main System')}")
        print(f"{len(menu_options) + 3}. {get_text('health.menu.logout', default='Logout')}")

        # Get user choice
        choice = input(f"\n{get_text('health.prompt.choice', default='Enter your choice')}: ")

        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(menu_options):
                # Call the selected function - FIX: All functions now accept auth parameter
                menu_options[choice_idx][1](auth)
            elif choice_idx == len(menu_options):
                # Language selection
                display_language_menu_option()
            elif choice_idx == len(menu_options) + 1:
                # Return to main system
                print(get_text('health.returning', default='Returning to main system...'))
                return auth
            elif choice_idx == len(menu_options) + 2:
                # Logout
                auth.logout()
                print(get_text('health.logged_out', default='Logged out successfully.'))
                return auth
            else:
                print(get_text('health.invalid_choice', default='Invalid choice. Please try again.'))
        except ValueError:
            print(get_text('health.invalid_input', default='Invalid input. Please enter a number.'))

        input(get_text('health.press_enter', default='\nPress Enter to continue...'))
