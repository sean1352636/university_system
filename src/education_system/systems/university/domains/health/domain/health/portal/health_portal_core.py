from education_system.systems.university.domains.health.infrastructure.health.storage import sqlite3, DatabaseManager, get_connection
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
from education_system.systems.university.domains.health.domain.health.services.health_context import cipher_suite

# Configure logging for audit trail
audit_logger = configure_logging(name=__name__)

# Encryption key management
# Optional import for health security features
try:
    from education_system.systems.university.domains.health.domain.health.portal.data_privacy import advanced_security_menu, user_session_management, ip_restriction_management, two_factor_authentication_setup, integration_management, api_key_management, integration_health_check, add_missing_menu_integrations, generate_security_report, population_risk_analysis, review_security_settings, update_security_settings, assess_contact_risk, security_audit_menu, view_audit_log, health_risk_assessment, conduct_risk_assessment, calculate_risk_score, get_risk_factors, generate_risk_recommendations
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
from education_system.systems.university.domains.health.domain.health.records.data_purge  import update_retention_policy, archive_old_data, data_purge_menu, view_purgeable_data, purge_expired_data, retention_compliance_report, compliance_monitoring, data_retention_management, view_retention_policies, custom_data_purge
from education_system.systems.university.domains.health.domain.health.records.quality_assurance  import generate_quality_metrics_report, clinical_quality_indicators, quality_assurance_menu, data_quality_metrics, show_quality_metrics
from education_system.systems.university.domains.health.domain.health.records.backup_export  import export_vaccination_records, export_appointment_data, export_lab_results, export_custom_dataset, restore_from_backup, manage_backup_schedule, backup_recovery_menu, create_database_backup, view_backup_history, export_data_menu, export_health_records, bulk_import_records
from education_system.systems.university.domains.health.domain.health.appointments.appointment_booking  import manage_provider_schedules, add_provider_schedule, view_provider_schedules, show_upcoming_appointments, provider_dashboard, todays_schedule, manage_screening_schedules, create_screening_schedule, schedule_screening_appointment, manage_provider_time_off, schedule_templates, provider_availability_report, update_provider_schedule, provider_statistics, schedule_appointment, view_appointments, update_appointment, update_appointment_status, generate_provider_utilization_report, generate_appointment_schedule_report, generate_provider_performance_report, show_appointment_utilization_stats, analyze_provider_workload, manage_waiting_list, give_appointment_feedback
from education_system.systems.university.domains.health.domain.health.records.admin.advisories import add_health_advisory, view_health_advisories
from education_system.systems.university.domains.health.domain.health.records.admin.permissions import manage_health_records_enhanced, setup_health_permissions
from education_system.systems.university.domains.health.domain.health.records.analytics.population import generate_population_health_report, show_population_health_metrics, generate_student_health_summary
from education_system.systems.university.domains.health.domain.health.records.analytics.quality import patient_safety_metrics
from education_system.systems.university.domains.health.domain.health.records.analytics.reports import generate_public_health_report
from education_system.systems.university.domains.health.domain.health.records.analytics.trends import generate_health_condition_analysis, health_analytics_dashboard, analyze_health_trends
from education_system.systems.university.domains.health.domain.health.records.clinical.allergies import add_allergy, update_allergy, delete_allergy
from education_system.systems.university.domains.health.domain.health.records.clinical.care_plans import manage_care_plans, create_care_plan, view_care_plans, update_care_plan, track_care_plan_progress
from education_system.systems.university.domains.health.domain.health.records.clinical.conditions import manage_medical_conditions, add_medical_condition, view_medical_conditions, update_condition_status, condition_management_plans
from education_system.systems.university.domains.health.domain.health.records.clinical.lab_results import manage_lab_results, add_lab_result, view_lab_results, lab_trends_analysis, recent_lab_results_dashboard
from education_system.systems.university.domains.health.domain.health.records.clinical.prescriptions import manage_prescriptions, add_prescription, view_prescriptions, update_prescription_status
from education_system.systems.university.domains.health.domain.health.records.records.crud import add_health_record, view_health_records, update_health_record, delete_health_record
from education_system.systems.university.domains.health.domain.health.records.records.reports import generate_health_report
from education_system.systems.university.domains.health.domain.health.records.records.templates import enhanced_health_record_templates, health_record_templates
from education_system.systems.university.domains.health.domain.health.records.referrals.referrals import manage_referrals, create_referral, view_referrals, update_referral_status, referral_followup, referral_reports
from education_system.systems.university.domains.health.domain.health.records.screening.guidelines import screening_guidelines, screening_recommendations
from education_system.systems.university.domains.health.domain.health.records.screening.reminders import screening_reminders, population_screening_reports
from education_system.systems.university.domains.health.domain.health.records.screening.results import record_screening_results
from education_system.systems.university.domains.health.domain.health.records.screening.schedules import calculate_screening_due_date, calculate_next_screening_date, view_due_screenings, overdue_screenings
from education_system.systems.university.domains.health.domain.health.records.student.dashboard import student_health_dashboard, show_personal_health_summary, show_health_reminders
from education_system.systems.university.domains.health.domain.health.records.student.insurance import view_insurance_info, update_insurance_info
from education_system.systems.university.domains.health.domain.health.records.student.resources import student_health_resources, view_health_resources
from education_system.systems.university.domains.health.domain.health.records.student.wellness import manage_wellness_goals, track_personal_metrics, quick_wellness_assessment
from education_system.systems.university.domains.health.domain.health.records.vaccinations.management import record_vaccination, view_vaccinations, verify_vaccination
from education_system.systems.university.domains.health.domain.health.records.vaccinations.reports import generate_vaccination_analysis_report, generate_vaccination_status_report, generate_vaccination_coverage_report
from education_system.systems.university.domains.health.domain.health.records.vaccinations.tracking import immunization_status, vaccination_due_list
from education_system.systems.university.domains.health.domain.health.records.wellness.challenges import health_challenges
from education_system.systems.university.domains.health.domain.health.records.wellness.programs import wellness_programs, view_wellness_programs, enroll_in_wellness_program, track_wellness_progress, wellness_program_analytics
from education_system.systems.university.domains.health.domain.health.records.wellness.resources import wellness_resources
from education_system.systems.university.domains.health.domain.health.services  import block_time_slots, patient_queue, critical_alerts_dashboard, pending_tasks, quick_patient_lookup, external_system_connections, use_existing_template, create_new_template, template_usage_statistics, specialist_directory, emergency_information, get_user_student_id, view_failed_logins, generate_disease_surveillance_report, analyze_data_access_patterns, update_emergency_contact, delete_emergency_contact, manage_contact_hierarchy, conduct_contact_tracing, investigate_outbreak, analyze_disease_trends, performance_improvement, manage_allergies, critical_values_alert, view_allergies, check_drug_interactions, check_basic_interactions, track_medication_adherence, manage_refill_reminders, manage_vital_signs, record_vital_signs, check_vital_signs_alerts, view_vital_signs, view_vital_signs_trends, calculate_bmi, generate_custom_report, manage_emergency_contacts, add_emergency_contact, view_emergency_contacts, disease_surveillance_system, report_disease_case, view_disease_cases, validate_csv_format

class SecurityManager:
    DEFAULT_TIMEOUT_MINUTES = 30

    @staticmethod
    def session_timeout_minutes() -> int:
        """``security_settings.session_timeout_minutes`` (30 when unset or
        unreadable - an unreadable setting never disables the timeout)."""
        try:
            conn = get_connection()
            try:
                row = conn.execute("SELECT setting_value FROM security_settings "
                                   "WHERE setting_name = 'session_timeout_minutes'").fetchone()
            finally:
                conn.close()
            minutes = int(row[0]) if row and str(row[0]).strip() else 0
        except Exception:
            minutes = 0
        return minutes if minutes > 0 else SecurityManager.DEFAULT_TIMEOUT_MINUTES

    @staticmethod
    def check_session_timeout(auth):
        """True when the user has been idle in the health portal for longer
        than the session timeout. Each check that passes counts as activity,
        so the timeout runs from the last menu action."""
        if not auth or not auth.current_user:
            return True
        now = time.monotonic()
        last = getattr(auth, "_health_last_activity", None)
        if not isinstance(last, (int, float)):
            last = None
        if last is not None and now - last > SecurityManager.session_timeout_minutes() * 60:
            try:
                del auth._health_last_activity
            except AttributeError:
                pass
            return True
        auth._health_last_activity = now
        return False

def get_or_create_encryption_key():
    """The managed health field key (``var/secrets/health_field_key``),
    created once when missing. It used to be written to the current working
    directory."""
    from education_system.systems.university.domains.health.infrastructure.health import (
        field_crypto,
    )
    return field_crypto.key_bytes()

def encrypt_sensitive_data(data):
    """Seal sensitive health data with the managed key."""
    from education_system.systems.university.domains.health.infrastructure.health import (
        field_crypto,
    )
    if data is None:
        return None
    return field_crypto.seal(str(data))

def decrypt_sensitive_data(encrypted_data):
    """Unseal a stored value; values written before sealing pass through.
    A sealed value that cannot be decrypted raises (never shown garbled)."""
    from education_system.systems.university.domains.health.infrastructure.health import (
        field_crypto,
    )
    if encrypted_data is None:
        return None
    return field_crypto.unseal(encrypted_data)

def log_audit_event(user_id, action, resource_type, resource_id, details=None, conn=None,
                    reason=None):
    """Log audit events for compliance: the health audit trail and the
    immutable audit log (``records/db/audit``); raises if it can't be
    written. It used to write only to a log file."""
    from education_system.systems.university.domains.health.domain.health.records.db.audit import (
        log_audit_event as _record,
    )
    _record(user_id, action, resource_type, resource_id, details, conn=conn, reason=reason)

def init_enhanced_health_db():
    """The health tables, once per database file: one schema
    (``infrastructure/health/health_schema``, also applied by migration
    ``a0d2f4b6c8e1``). It used to declare 24 tables here on every launch."""
    from education_system.systems.university.domains.health.infrastructure.health import (
        health_schema,
    )
    try:
        health_schema.ensure()
    except sqlite3.Error as e:
        print(f"An error occurred while initializing the enhanced health database: {e}")

# Mental Health Helper Functions
def _launch_wellness_cli(auth):
    """Launch the student affairs mental health and wellness hub."""
    try:
        from education_system.systems.university.domains.student_support.interfaces.cli.wellbeing.wellness.wellness_cli import WellnessCLI
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
    print("\n24/7 Crisis Support (UK):")
    print("  • Emergency services: 999")
    print("  • NHS 111 (urgent medical and mental health help; poisons advice): 111")
    print("  • Samaritans: 116 123 (free, 24/7)")
    print("  • Shout: text SHOUT to 85258 (free, 24/7)")
    print("\nCampus Resources:")
    # The university's own numbers, as set in Chatbot Care settings (one
    # place, so the chatbot's crisis reply and this list agree).
    contacts = []
    try:
        from education_system.systems.university.application.chatbot import care as chatbot_care
        conn = get_connection(row_factory=False)
        try:
            contacts = chatbot_care.university_contacts(conn)
        finally:
            conn.close()
    except Exception:
        logging.getLogger(__name__).debug("Campus contacts unavailable", exc_info=True)
    for label, value in contacts:
        print(f"  • {label}: {value}")
    if not contacts:
        print("  • The university's own support numbers have not been set up yet")
        print("    (an administrator adds them under Chatbot Care settings).")
    print("\n⚠️ If you or someone you know is in immediate danger, call 999")
    print("="*50)

def _launch_dentist_cli(auth=None):
    """Launch the Dental Clinic CLI from within the health portal, as the
    portal's signed-in user."""
    try:
        from education_system.systems.university.domains.health.domain.health.portal.dentist_cli import dentist_menu
        dentist_menu(auth)
    except ImportError as e:
        print(f"\n❌ Dental Clinic CLI not available: {e}")
        input("Press Enter to continue...")


def _break_glass_cli(auth):
    """Emergency access to one student's record for someone outside the
    health team: a written reason, logged, and the health administrators
    told. The grant is time-limited (application/health/access)."""
    from education_system.systems.university.domains.health.application.health import (
        access as health_access,
    )
    print("\nHealth records are for the health team and the student themselves.")
    print("Use this only in an emergency. Your reason is recorded and the health")
    print("administrators are told.")
    student_id = input("Student ID: ").strip()
    if not student_id:
        return
    reason = input("Why do you need this record now? ").strip()
    if not reason:
        print("A reason is required.")
        return
    try:
        emails = health_access.break_glass(health_access.from_user(auth.current_user),
                                           student_id, reason)
    except (PermissionError, ValueError) as exc:
        print(exc)
        return
    try:
        from education_system.systems.university.infrastructure.ui.record_screens import (
            send_emails,
        )
        send_emails(emails)
    except Exception:
        logging.getLogger(__name__).debug("Break-glass notice not sent", exc_info=True)
    print(f"Access to {student_id}'s health record granted for "
          f"{health_access.BREAK_GLASS_MINUTES} minutes.")
    _show_break_glass_record(auth, student_id)


def _show_break_glass_record(auth, student_id):
    """Read-only view of the granted student's health records (audited)."""
    from education_system.systems.university.domains.health.application.health import (
        access as health_access, sealed_fields,
    )
    who = health_access.from_user(auth.current_user)
    try:
        health_access.require_view(who, student_id)
        health_access.record_view(who, "break_glass:health_records", student_id=student_id)
    except PermissionError as exc:
        print(exc)
        return
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT record_type, record_date, description, provider FROM health_records "
            "WHERE student_id = ? ORDER BY record_date DESC LIMIT 100",
            (student_id,)).fetchall()
    finally:
        conn.close()
    print(f"\n===== Health records for {student_id} (break-glass) =====")
    if not rows:
        print("No health records found.")
    for record_type, record_date, description, provider in rows:
        print(f"{record_date}  {record_type}  ({provider or 'provider not recorded'})")
        print(f"    {sealed_fields.reveal(description) or ''}")


def _pick_from(options, prompt):
    for number, option in enumerate(options, 1):
        print(f"  {number}. {option}")
    choice = input(prompt).strip()
    if choice.isdigit() and 1 <= int(choice) <= len(options):
        return options[int(choice) - 1]
    return choice or None


def _email_status_cli(auth):
    """The health e-mails in the university outbox and what happened to
    each (the Email Manager's view, for the health portal)."""
    from education_system.systems.university.domains.health.application.health import notices
    print(f"\n===== Health e-mails (delivery mode: {notices.delivery_mode()}) =====")
    print(notices.delivery_note())
    conn = get_connection(row_factory=False)
    try:
        rows = notices.recent_health_emails(conn)
    finally:
        conn.close()
    if not rows:
        print("\nNo health e-mails in the outbox.")
        return
    print(f"\n{'#':>6}  {'Status':<10} {'Created':<19}  {'To':<30} Subject")
    for r in rows:
        print(f"{r['message_id']:>6}  {r['status']:<10} {str(r['created_at'])[:19]:<19}  "
              f"{str(r['to_address'])[:30]:<30} {r['subject']}")
        if r.get("last_error"):
            print(f"{'':>8}last error: {r['last_error']}")


def _send_report_email_cli(auth):
    """E-mail a student a health report summary (health team only)."""
    from education_system.systems.university.domains.health.application.health import (
        access as health_access, notices,
    )
    who = health_access.from_user(auth.current_user)
    try:
        health_access.require_clinician(who, "e-mail health reports")
    except PermissionError as exc:
        print(exc)
        return
    student_id = input("Student ID: ").strip()
    conn = get_connection(row_factory=False)
    try:
        contact = notices.student_contact(conn, student_id)
    finally:
        conn.close()
    if not contact:
        print("Student not found.")
        return
    name, email = contact
    title = input("Report title: ").strip() or "Health Report"
    print("Report type:")
    report_type = _pick_from(list(notices.REPORT_TYPES), "Choose (or type your own): ")
    summary = input("Summary for the student: ").strip()
    health_access.record_view(who, "cli:email_health_report", student_id=student_id)
    if notices.send_report_email(email, name, title=title, report_type=report_type,
                                 summary=summary, practitioner=who.username):
        print(f"\nReport e-mail for {name} queued in the university outbox.")
        print(notices.delivery_note())
    else:
        print(f"\nThe report e-mail to {name} could not be queued "
              "(no e-mail address, or the e-mail service is unavailable).")


def _send_record_notice_cli(auth):
    """Tell a student their record is ready in the portal (no contents)."""
    from education_system.systems.university.domains.health.application.health import (
        access as health_access, notices,
    )
    who = health_access.from_user(auth.current_user)
    try:
        health_access.require_clinician(who, "send health record notices")
    except PermissionError as exc:
        print(exc)
        return
    student_id = input("Student ID: ").strip()
    conn = get_connection(row_factory=False)
    try:
        contact = notices.student_contact(conn, student_id)
    finally:
        conn.close()
    if not contact:
        print("Student not found.")
        return
    name, email = contact
    print("Record:")
    record_type = _pick_from(list(notices.RECORD_TYPES), "Choose (or type your own): ")
    date_range = input("Date range [all dates]: ").strip() or "all dates"
    health_access.record_view(who, "cli:email_health_record", student_id=student_id)
    if notices.send_record_notice(email, name, record_type=record_type, date_range=date_range):
        print(f"\nNotice for {name} queued. Record contents are never sent by e-mail; "
              "the student reads the record in the portal.")
        print(notices.delivery_note())
    else:
        print(f"\nThe notice to {name} could not be queued "
              "(no e-mail address, or the e-mail service is unavailable).")


def _accessibility_tools_cli(auth):
    from education_system.systems.university.domains.student_support.domain.accessibility_tools import (
        display_accessibility_menu,
    )
    display_accessibility_menu(auth)


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

        # ── Build the categories ────────────────────────────────────────
        # This menu used to print all ~46 actions as one flat numbered list,
        # which ran off the screen and made the numbering shift as soon as a
        # permission changed. It is now grouped the same way the main
        # university CLI is: pick a category, then pick an action inside it,
        # with 0 to go back. A category with nothing in it (because the user
        # lacks the permissions) is never shown at all.
        can = auth.check_permission
        role = auth.current_user.get('role', '')
        # Need-to-know (application/health/access): the health team sees
        # every student; a student only their own record; everyone else
        # only the break-glass option.
        from education_system.systems.university.domains.health.application.health import (
            access as health_access,
        )
        who = health_access.from_user(auth.current_user)
        clinician = bool(who and who.is_clinician)
        student = bool(who and who.is_student and who.student_id)
        patient = clinician or student
        # Staff outside the health team may ask for break-glass access;
        # parents and alumni may not.
        outside_team = not patient and role in ('staff', 'instructor')

        categories = []

        def category(title, items):
            """Register *title* if any of its items survived the permission filter."""
            live = [entry for entry in items if entry]
            if live:
                categories.append({'title': title, 'items': live})

        def item(label, action, allowed=True):
            return (label, action) if allowed else None

        category("📋 Health Records & Clinical Data", [
            item("Manage Health Records", manage_health_records_enhanced,
                 clinician and can('manage_health_records')),
            item("View Health Records", view_health_records, patient),
            item("Personal Health Dashboard", student_health_dashboard, student),
            item("Allergy Management", manage_allergies, clinician),
            item("Prescription Management", manage_prescriptions, clinician),
            item("Vital Signs Management", manage_vital_signs, clinician),
            item("Lab Results Management", manage_lab_results, clinician),
        ] if patient else [])

        category("🩺 Providers & Referrals", [
            item("Provider Dashboard", provider_dashboard),
            item("Provider Schedule Management", manage_provider_schedules),
            item("Referral Management", manage_referrals),
        ] if clinician else [])

        category("📅 Appointments & Scheduling", [
            item("Schedule Appointment", schedule_appointment, patient),
            item("View Appointments", view_appointments, patient),
            item("Update Appointment", update_appointment, clinician),
            item("Update Appointment Status", update_appointment_status, clinician),
            item("Appointment Waiting List", manage_waiting_list, patient),
            item("Give Appointment Feedback", give_appointment_feedback, student),
        ])

        category("💉 Vaccinations & Immunizations", [
            item("Record Vaccination", record_vaccination, clinician),
            item("View Vaccination Records", view_vaccinations, patient),
            item("Verify Vaccination Record", verify_vaccination, clinician),
        ])

        category("🏥 Care Plans & Clinical Management", [
            item("Care Plan Management", manage_care_plans),
            item("Health Risk Assessment", health_risk_assessment),
        ] if clinician else [])

        category("🚨 Emergency & Safety", [
            item("Emergency Contact Management", manage_emergency_contacts, patient),
            item("Disease Surveillance System", disease_surveillance_system,
                 clinician and can('issue_health_advisories')),
            item("Emergency access (break-glass)", _break_glass_cli, outside_team),
        ])

        category("📢 Health Advisories & Communications", [
            item("Add Health Advisory", add_health_advisory, can('issue_health_advisories')),
            item("View Health Advisories", view_health_advisories,
                 can('view_health_advisories') or can('issue_health_advisories')),
        ])

        category("🌟 Wellness & Prevention", [
            item("Wellness Programs", wellness_programs, patient),
            item("Health Resources", view_health_resources, can('view_health_resources')),
        ])

        category("🧠 Mental Health & Wellness", [
            item("Schedule Counseling Appointment", _launch_wellness_cli, patient),
            item("Wellness Check-in", _launch_wellness_cli, patient),
            item("Peer Support Matching", _launch_wellness_cli, patient),
            item("Mindfulness & Meditation Resources", _launch_wellness_cli, patient),
            item("Crisis Hotline Information", lambda auth: _display_crisis_hotline_info()),
            item("View Counselor Profiles", _launch_wellness_cli, patient),
            item("Track Wellness Progress", _launch_wellness_cli, patient),
        ])

        category("💳 Insurance & Financial", [
            item("View Insurance Information", view_insurance_info),
            item("Update Insurance Information", update_insurance_info),
        ] if patient else [])

        category("📊 Analytics & Reporting", [
            item("Health Analytics Dashboard", health_analytics_dashboard, clinician),
            item("Generate Health Report", generate_health_report, clinician),
            item("Quality Assurance", quality_assurance_menu, clinician),
            item("Screening Schedule Management", manage_screening_schedules, clinician),
            item("Enhanced Record Templates", enhanced_health_record_templates, clinician),
        ])

        category("🔒 Data Management & Security", [
            item("Data Retention Management", data_retention_management),
            item("Security Audit", security_audit_menu),
            item("Advanced Security Management", advanced_security_menu),
            item("Integration Management", integration_management),
            item("System Backup & Recovery", backup_recovery_menu),
        ] if role == 'admin' else [])

        category("✉️ Integration & Communications", [
            item(get_text('health.menu.email_status', default="Health E-mails & Outbox Status"),
                 _email_status_cli, clinician),
            item(get_text('health.menu.send_report_email', default="Send Health Report E-mail"),
                 _send_report_email_cli, clinician),
            item(get_text('health.menu.send_record_email', default="Send Health Record Notice"),
                 _send_record_notice_cli, clinician),
        ])

        category("♿ Accessibility & Accommodations", [
            item(get_text('health.menu.accessibility_tools', default="Accessibility Tools"),
                 _accessibility_tools_cli),
        ])

        category("🦷 Health Services", [
            item("Dental Clinic", _launch_dentist_cli, patient),
        ])

        # ── Top level: the categories ───────────────────────────────────
        print(f"\n{'=' * 70}")
        print(get_text('health.title',
                       default='Enhanced University Health Portal').center(70))
        print('=' * 70)
        print(get_text('health.logged_in', default='Logged in as: {username} ({role})').format(
            username=auth.current_user['username'], role=auth.current_user['role']))
        print('-' * 70)

        for number, group in enumerate(categories, 1):
            print(f"  {number:>2}. {group['title']}  ({len(group['items'])})")
        print(f"\n   0. {get_text('health.menu.return_main', default='Return to Main System')}")
        print('=' * 70)

        chosen = input(f"\n{get_text('health.prompt.choice', default='Enter your choice')} "
                       f"(0-{len(categories)}): ").strip()

        if chosen in ('0', ''):
            print(get_text('health.returning', default='Returning to main system...'))
            return auth

        if not (chosen.isdigit() and 1 <= int(chosen) <= len(categories)):
            print(get_text('health.invalid_choice', default='Invalid choice. Please try again.'))
            continue

        group = categories[int(chosen) - 1]

        # ── Second level: stay in the category until the user goes back ──
        while True:
            print(f"\n{'=' * 70}")
            print(group['title'].center(70))
            print('=' * 70)
            for number, (label, _action) in enumerate(group['items'], 1):
                print(f"  {number:>2}. {label}")
            print(f"\n   0. {get_text('health.menu.back', default='Back to Health Portal Menu')}")
            print('=' * 70)

            picked = input(f"\n{get_text('health.prompt.choice', default='Enter your choice')} "
                           f"(0-{len(group['items'])}): ").strip()

            if picked in ('0', ''):
                break

            if not (picked.isdigit() and 1 <= int(picked) <= len(group['items'])):
                print(get_text('health.invalid_choice', default='Invalid choice. Please try again.'))
                continue

            label, action = group['items'][int(picked) - 1]
            # Every health action is recorded (who, what, whose: the
            # student's own number, or "(all)" for the health team); when
            # the record can't be written the action does not run.
            try:
                health_access.record_view(
                    who, "cli:" + label,
                    student_id=(who.student_id if student else "(all)"))
            except PermissionError as exc:
                print(exc)
                input(get_text('health.press_enter', default='\nPress Enter to continue...'))
                continue
            try:
                action(auth)
            except Exception as exc:
                # One failing action must not drop the operator out of the
                # portal — report it and stay on the menu.
                logging.getLogger(__name__).exception(
                    "Health portal action %r failed", label)
                print(get_text('health.action_failed',
                               default='Error running this option: ') + str(exc))

            input(get_text('health.press_enter', default='\nPress Enter to continue...'))
