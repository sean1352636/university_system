from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection
from education_system.university_system.modules.domain.health.records.analytics.quality import patient_safety_metrics
from education_system.university_system.modules.domain.health.records.data_purge import compliance_monitoring
from education_system.university_system.modules.domain.health.services import log_audit_event
from education_system.university_system.modules.domain.health.services import performance_improvement
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
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.database.data_backup import backup_before_operation
from education_system.university_system.infrastructure.email import (
    send_appointment_confirmation,
    send_health_notification,
)
from education_system.university_system.utils.logging.log_config import configure_logging

# Configure logging for audit trail
audit_logger = configure_logging(name=__name__)

# Encryption key management


def generate_quality_metrics_report(auth, start_date, end_date):
    """Generate quality metrics report"""
    conn = get_connection()
    cursor = conn.cursor()
    
    report_content = []
    report_content.append("QUALITY METRICS REPORT")
    report_content.append("=" * 22)
    report_content.append(f"Period: {start_date} to {end_date}")
    report_content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_content.append("")
    
    # Appointment completion rates
    cursor.execute('''
    SELECT 
        COUNT(*) as total_appointments,
        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
        SUM(CASE WHEN status = 'no-show' THEN 1 ELSE 0 END) as no_shows,
        SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled
    FROM health_appointments
    WHERE appointment_date BETWEEN ? AND ?
    ''', (start_date, end_date))
    
    apt_data = cursor.fetchone()
    
    if apt_data and apt_data[0] > 0:
        total, completed, no_shows, cancelled = apt_data
        completion_rate = (completed / total * 100)
        no_show_rate = (no_shows / total * 100)
        cancellation_rate = (cancelled / total * 100)
        
        report_content.append("APPOINTMENT QUALITY METRICS")
        report_content.append("-" * 27)
        report_content.append(f"Total Appointments: {total}")
        report_content.append(f"Completion Rate: {completion_rate:.1f}%")
        report_content.append(f"No-Show Rate: {no_show_rate:.1f}%")
        report_content.append(f"Cancellation Rate: {cancellation_rate:.1f}%")
    
    # Documentation quality
    cursor.execute('''
    SELECT 
        COUNT(*) as total_records,
        SUM(CASE WHEN provider IS NOT NULL AND provider != '' THEN 1 ELSE 0 END) as with_provider,
        SUM(CASE WHEN description IS NOT NULL AND LENGTH(description) > 10 THEN 1 ELSE 0 END) as adequate_description
    FROM health_records
    WHERE record_date BETWEEN ? AND ?
    ''', (start_date, end_date))
    
    doc_data = cursor.fetchone()
    
    if doc_data and doc_data[0] > 0:
        total_records, with_provider, adequate_desc = doc_data
        provider_documentation = (with_provider / total_records * 100)
        description_quality = (adequate_desc / total_records * 100)
        
        report_content.append("")
        report_content.append("DOCUMENTATION QUALITY")
        report_content.append("-" * 20)
        report_content.append(f"Total Records: {total_records}")
        report_content.append(f"Provider Documentation: {provider_documentation:.1f}%")
        report_content.append(f"Adequate Descriptions: {description_quality:.1f}%")
    
    # Display report
    for line in report_content:
        print(line)
    
    conn.close()

def clinical_quality_indicators(auth):
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to view clinical quality indicators.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Clinical Quality Indicators =====")
    
    # Preventive care indicators
    print("PREVENTIVE CARE INDICATORS")
    print("-" * 30)
    
    # Vaccination coverage rates
    cursor.execute("SELECT COUNT(DISTINCT student_id) FROM students")
    total_students = cursor.fetchone()[0]
    
    # Common vaccines coverage
    common_vaccines = ['COVID-19', 'Influenza (Flu)', 'Hepatitis B', 'MMR']
    
    for vaccine in common_vaccines:
        cursor.execute('''
        SELECT COUNT(DISTINCT student_id) 
        FROM vaccination_records 
        WHERE vaccine_name = ? AND verified = 1
        ''', (vaccine,))
        
        vaccinated = cursor.fetchone()[0]
        coverage_rate = (vaccinated / total_students * 100) if total_students > 0 else 0
        
        print(f"{vaccine} Coverage: {vaccinated}/{total_students} ({coverage_rate:.1f}%)")
        
        # Quality threshold check
        if coverage_rate >= 90:
            print("  ✅ Excellent coverage")
        elif coverage_rate >= 80:
            print("  🟡 Good coverage")
        elif coverage_rate >= 70:
            print("  🟠 Fair coverage")
        else:
            print("  🔴 Poor coverage - Action needed")
    
    # Care coordination indicators
    print("\nCARE COORDINATION INDICATORS")
    print("-" * 30)
    
    # Students with chronic conditions having care plans
    cursor.execute('''
    SELECT 
        COUNT(DISTINCT mc.student_id) as total_chronic,
        COUNT(DISTINCT cp.student_id) as with_care_plans
    FROM medical_conditions mc
    LEFT JOIN care_plans cp ON mc.student_id = cp.student_id AND cp.status = 'active'
    WHERE mc.status = 'active' AND mc.condition_name IN 
        ('Diabetes', 'Hypertension', 'Asthma', 'Depression', 'Anxiety')
    ''')
    
    care_coord = cursor.fetchone()
    if care_coord[0] > 0:
        care_plan_rate = (care_coord[1] / care_coord[0] * 100)
        print(f"Chronic Conditions with Care Plans: {care_coord[1]}/{care_coord[0]} ({care_plan_rate:.1f}%)")
        
        if care_plan_rate >= 80:
            print("  ✅ Excellent care coordination")
        elif care_plan_rate >= 60:
            print("  🟡 Good care coordination")
        else:
            print("  🔴 Poor care coordination - Improve care planning")
    
    # Follow-up compliance
    cursor.execute('''
    SELECT 
        COUNT(*) as total_appointments,
        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
        SUM(CASE WHEN status = 'no-show' THEN 1 ELSE 0 END) as no_shows
    FROM health_appointments
    WHERE appointment_date >= date('now', '-30 days')
    ''')
    
    appt_data = cursor.fetchone()
    if appt_data[0] > 0:
        completion_rate = (appt_data[1] / appt_data[0] * 100)
        no_show_rate = (appt_data[2] / appt_data[0] * 100)
        
        print(f"Appointment Completion Rate: {completion_rate:.1f}%")
        print(f"No-Show Rate: {no_show_rate:.1f}%")
        
        if completion_rate >= 85:
            print("  ✅ Excellent follow-up compliance")
        elif completion_rate >= 75:
            print("  🟡 Good follow-up compliance")
        else:
            print("  🔴 Poor follow-up compliance")
    
    # Documentation quality
    print("\nDOCUMENTATION QUALITY")
    print("-" * 20)
    
    # Health records with provider documentation
    cursor.execute('''
    SELECT 
        COUNT(*) as total_records,
        SUM(CASE WHEN provider IS NOT NULL AND provider != '' THEN 1 ELSE 0 END) as with_provider
    FROM health_records
    WHERE record_date >= date('now', '-30 days')
    ''')
    
    doc_data = cursor.fetchone()
    if doc_data[0] > 0:
        provider_documentation = (doc_data[1] / doc_data[0] * 100)
        print(f"Records with Provider Documentation: {provider_documentation:.1f}%")
        
        if provider_documentation >= 95:
            print("  ✅ Excellent documentation")
        elif provider_documentation >= 85:
            print("  🟡 Good documentation")
        else:
            print("  🔴 Poor documentation quality")
    
    conn.close()

def quality_assurance_menu(auth):
    """Quality assurance and improvement menu"""
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to access quality assurance.")
        return
    
    while True:
        print("\n===== Quality Assurance =====")
        print("1. Data Quality Metrics")
        print("2. Clinical Quality Indicators")
        print("3. Patient Safety Metrics")
        print("4. Performance Improvement")
        print("5. Compliance Monitoring")
        print("6. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-6): ")
        
        if choice == '1':
            data_quality_metrics(auth)
        elif choice == '2':
            clinical_quality_indicators(auth)
        elif choice == '3':
            patient_safety_metrics(auth)
        elif choice == '4':
            performance_improvement(auth)
        elif choice == '5':
            compliance_monitoring(auth)
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")

def data_quality_metrics(auth):
    """Show data quality metrics"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Data Quality Metrics =====")
    
    # Completeness metrics
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]
    
    # Students with complete emergency contacts
    cursor.execute('''
    SELECT COUNT(DISTINCT student_id) FROM emergency_contacts
    ''')
    students_with_emergency_contacts = cursor.fetchone()[0]
    emergency_completeness = (students_with_emergency_contacts / total_students * 100) if total_students > 0 else 0
    
    # Students with insurance information
    cursor.execute('''
    SELECT COUNT(DISTINCT student_id) FROM insurance_information
    ''')
    students_with_insurance = cursor.fetchone()[0]
    insurance_completeness = (students_with_insurance / total_students * 100) if total_students > 0 else 0
    
    # Vaccination verification rate
    cursor.execute('''
    SELECT 
        COUNT(*) as total_vaccinations,
        SUM(CASE WHEN verified = 1 THEN 1 ELSE 0 END) as verified_count
    FROM vaccination_records
    ''')
    vax_data = cursor.fetchone()
    vaccination_verification = (vax_data[1] / vax_data[0] * 100) if vax_data[0] > 0 else 0
    
    # Health records with provider information
    cursor.execute('''
    SELECT 
        COUNT(*) as total_records,
        SUM(CASE WHEN provider IS NOT NULL AND provider != '' THEN 1 ELSE 0 END) as with_provider
    FROM health_records
    ''')
    provider_data = cursor.fetchone()
    provider_completeness = (provider_data[1] / provider_data[0] * 100) if provider_data[0] > 0 else 0
    
    print(f"Emergency Contact Completeness: {emergency_completeness:.1f}%")
    print(f"Insurance Information Completeness: {insurance_completeness:.1f}%")
    print(f"Vaccination Verification Rate: {vaccination_verification:.1f}%")
    print(f"Health Records with Provider Info: {provider_completeness:.1f}%")
    
    # Data freshness metrics
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    cursor.execute('''
    SELECT COUNT(*) FROM health_records WHERE record_date >= ?
    ''', (thirty_days_ago,))
    recent_health_records = cursor.fetchone()[0]
    
    cursor.execute('''
    SELECT COUNT(*) FROM vital_signs WHERE measurement_date >= ?
    ''', (thirty_days_ago,))
    recent_vital_signs = cursor.fetchone()[0]
    
    print(f"\nData Freshness (Last 30 Days):")
    print(f"Health Records: {recent_health_records}")
    print(f"Vital Signs: {recent_vital_signs}")
    
    conn.close()

def show_quality_metrics(auth):
    """Show quality metrics and performance indicators"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Quality Metrics =====")
    
    # Patient satisfaction would require a separate table, but we can show other metrics
    
    # Vaccination verification rate
    cursor.execute('''
    SELECT 
        COUNT(*) as total_vaccinations,
        SUM(CASE WHEN verified = 1 THEN 1 ELSE 0 END) as verified_count
    FROM vaccination_records
    ''')
    
    vax_verification = cursor.fetchone()
    if vax_verification and vax_verification[0] > 0:
        verification_rate = (vax_verification[1] / vax_verification[0]) * 100
        print(f"Vaccination Verification Rate: {vax_verification[1]}/{vax_verification[0]} ({verification_rate:.1f}%)")
    
    # Appointment completion rate
    cursor.execute('''
    SELECT 
        COUNT(*) as total_appointments,
        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_count
    FROM health_appointments
    WHERE appointment_date < ?
    ''', (datetime.now().strftime('%Y-%m-%d'),))
    
    appointment_completion = cursor.fetchone()
    if appointment_completion and appointment_completion[0] > 0:
        completion_rate = (appointment_completion[1] / appointment_completion[0]) * 100
        print(f"Appointment Completion Rate: {appointment_completion[1]}/{appointment_completion[0]} ({completion_rate:.1f}%)")
    
    # Follow-up care tracking
    cursor.execute('''
    SELECT COUNT(*) FROM care_plans WHERE status = 'active'
    ''')
    active_care_plans = cursor.fetchone()[0]
    print(f"Active Care Plans: {active_care_plans}")
    
    # Data completeness metrics
    cursor.execute('''
    SELECT 
        COUNT(*) as total_students,
        SUM(CASE WHEN EXISTS (SELECT 1 FROM emergency_contacts WHERE emergency_contacts.student_id = students.student_id) THEN 1 ELSE 0 END) as with_emergency_contacts,
        SUM(CASE WHEN EXISTS (SELECT 1 FROM insurance_information WHERE insurance_information.student_id = students.student_id) THEN 1 ELSE 0 END) as with_insurance
    FROM students
    ''')
    
    completeness = cursor.fetchone()
    if completeness and completeness[0] > 0:
        emergency_completeness = (completeness[1] / completeness[0]) * 100
        insurance_completeness = (completeness[2] / completeness[0]) * 100
        print(f"Emergency Contact Completeness: {completeness[1]}/{completeness[0]} ({emergency_completeness:.1f}%)")
        print(f"Insurance Information Completeness: {completeness[2]}/{completeness[0]} ({insurance_completeness:.1f}%)")
    
    conn.close()

def patient_safety_metrics(auth):
    """No-show/cancel rates, adverse reactions, overdue follow-ups."""
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to view patient safety metrics.")
        return

    conn = get_connection()
    c = conn.cursor()
    try:
        print("\n===== Patient Safety Metrics =====")

        # Appointments table (health_appointments)
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='health_appointments'")
        has_appt = bool(c.fetchone())

        total = noshow = canc = 0
        if has_appt:
            c.execute("""
                SELECT
                    COUNT(*),
                    SUM(CASE WHEN status IN ('no_show','no-show','missed') THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status IN ('cancelled','canceled') THEN 1 ELSE 0 END)
                FROM health_appointments
                WHERE date(appointment_date) >= date('now','localtime','-90 day')
            """)
            total, noshow, canc = [x or 0 for x in c.fetchone()]
            rate_ns = f"{(noshow/total*100):.1f}%" if total else "n/a"
            rate_c  = f"{(canc/total*100):.1f}%" if total else "n/a"
            print(f"Appointment window (last 90d): {total} total | No-shows: {noshow} ({rate_ns}) | Cancelled: {canc} ({rate_c})")
        else:
            print("No 'health_appointments' table; skipping no-show/cancel metrics.")

        # Adverse reactions from vaccination_records
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vaccination_records'")
        if c.fetchone():
            c.execute("""
                SELECT COUNT(*), SUM(CASE WHEN adverse_reaction=1 THEN 1 ELSE 0 END)
                FROM vaccination_records
                WHERE date(administered_date) >= date('now','localtime','-365 day')
            """)
            total_vax, adverse = [x or 0 for x in c.fetchone()]
            rate_adv = f"{(adverse/total_vax*100):.2f}%" if total_vax else "n/a"
            print(f"Vaccinations (last 12mo): {total_vax} total | Adverse reactions: {adverse} ({rate_adv})")
        else:
            print("No 'vaccination_records' table; skipping adverse reactions.")

        # Overdue follow-ups from risk_assessments
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='risk_assessments'")
        if c.fetchone():
            c.execute("""
                SELECT COUNT(*) FROM risk_assessments
                WHERE follow_up_date IS NOT NULL AND date(follow_up_date) < date('now','localtime')
            """)
            overdue = c.fetchone()[0] or 0
            print(f"Overdue follow-ups: {overdue}")
        else:
            print("No 'risk_assessments' table; skipping follow-up metric.")

        # Audit
        try:
            log_audit_event(auth.current_user['id'], 'patient_safety_metrics', 'quality', 'safety')
        except TypeError:
            log_audit_event(auth.current_user['id'], 'patient_safety_metrics', 'quality', 'safety')

    finally:
        try:
            conn.close()
        except Exception:
            pass
    input("\nPress Enter to return...")


def performance_improvement(auth):
    """Show metrics flagged for improvement and quick wins."""
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to view improvement actions.")
        return

    conn = get_connection()
    c = conn.cursor()
    try:
        print("\n===== Performance Improvement =====")

        # Use quality_metrics table if present
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quality_metrics'")
        if c.fetchone():
            c.execute("""
                SELECT metric_name, metric_category, target_value, actual_value, status, improvement_needed
                FROM quality_metrics
                ORDER BY measured_date DESC, id DESC
                LIMIT 50
            """)
            rows = c.fetchall()
            if rows:
                print("Tracked quality metrics:")
                for mname, mcat, target, actual, status, imp in rows:
                    flag = " (⚠️ needs improvement)" if imp else ""
                    print(f" - [{mcat or 'general'}] {mname or 'metric'}: {actual} / target {target} [{status or 'n/a'}]{flag}")
            else:
                print("No quality metrics recorded.")
        else:
            print("No 'quality_metrics' table; showing proxy signals.")

        # Proxy: recent no-show rate (last 30d)
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='health_appointments'")
        if c.fetchone():
            c.execute("""
                SELECT COUNT(*),
                       SUM(CASE WHEN status IN ('no_show','no-show','missed') THEN 1 ELSE 0 END)
                FROM health_appointments
                WHERE date(appointment_date) >= date('now','localtime','-30 day')
            """)
            total, noshow = [x or 0 for x in c.fetchone()]
            rate = (noshow/total*100) if total else None
            if rate is not None:
                print(f"\nNo-show rate (30d): {rate:.1f}%")
                if rate > 5:
                    print("  Recommendation: enable reminders + same-day waitlist fills for open slots.")

        # Proxy: data completeness
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='emergency_contacts'")
        has_em = bool(c.fetchone())
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='insurance_information'")
        has_ins = bool(c.fetchone())
        if has_em and has_ins:
            c.execute("SELECT COUNT(*) FROM students"); total_students = c.fetchone()[0] or 0
            c.execute("SELECT COUNT(DISTINCT student_id) FROM emergency_contacts"); em_cov = c.fetchone()[0] or 0
            c.execute("SELECT COUNT(DISTINCT student_id) FROM insurance_information"); ins_cov = c.fetchone()[0] or 0
            em_rate = f"{(em_cov/max(total_students,1)*100):.1f}%" if total_students else "n/a"
            ins_rate = f"{(ins_cov/max(total_students,1)*100):.1f}%" if total_students else "n/a"
            print(f"\nCoverage: Emergency contacts {em_rate} | Insurance {ins_rate}")

        try:
            log_audit_event(auth.current_user['id'], 'performance_improvement', 'quality', 'improvement')
        except TypeError:
            log_audit_event(auth.current_user['id'], 'performance_improvement', 'quality', 'improvement')

    finally:
        try:
            conn.close()
        except Exception:
            pass
    input("\nPress Enter to return...")


def compliance_monitoring(auth):
    """Lightweight compliance view: audit volume, record completeness, retention policy presence."""
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to view compliance.")
        return

    conn = get_connection()
    c = conn.cursor()
    try:
        print("\n===== Compliance Monitoring =====")

        # Audit log volume (last 30d)
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_trail'")
        if c.fetchone():
            c.execute("""
                SELECT COUNT(*) FROM audit_trail
                WHERE timestamp IS NOT NULL
                  AND datetime(timestamp) >= datetime('now','localtime','-30 day')
            """)
            n = c.fetchone()[0] or 0
            print(f"Audit events (30d): {n}")
        else:
            print("No 'audit_trail' table found.")

        # Health record completeness proxy: % with provider assigned
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='health_records'")
        if c.fetchone():
            c.execute("""
                SELECT COUNT(*),
                       SUM(CASE WHEN provider IS NOT NULL AND provider != '' THEN 1 ELSE 0 END)
                FROM health_records
            """)
            total, with_provider = [x or 0 for x in c.fetchone()]
            rate = f"{(with_provider/max(total,1)*100):.1f}%" if total else "n/a"
            print(f"Health records with provider recorded: {with_provider}/{total} ({rate})")
        else:
            print("No 'health_records' table; skipping record completeness.")

        # Retention policies exist?
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='data_retention_policies'")
        if c.fetchone():
            c.execute("SELECT COUNT(*) FROM data_retention_policies")
            cnt = c.fetchone()[0] or 0
            print(f"Data retention policies configured: {cnt}")
        else:
            print("No 'data_retention_policies' table.")

        try:
            log_audit_event(auth.current_user['id'], 'compliance_monitoring', 'quality', 'compliance')
        except TypeError:
            log_audit_event(auth.current_user['id'], 'compliance_monitoring', 'quality', 'compliance')

    finally:
        try:
            conn.close()
        except Exception:
            pass
    input("\nPress Enter to return...")
