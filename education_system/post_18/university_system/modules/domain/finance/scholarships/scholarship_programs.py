from education_system.post_18.university_system.infrastructure.database.db import sqlite3
import os
import csv
import numpy as np
from datetime import datetime, timedelta
import json
import hashlib
import hmac
import requests
import smtplib
import ssl
import threading
import schedule
import time
import warnings
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
from cryptography.fernet import Fernet
import logging
from flask import Flask, request, jsonify
from io import BytesIO
import base64
from education_system.post_18.university_system.infrastructure.email import send_email
from education_system.post_18.university_system.infrastructure.auth import UserAuth
from education_system.post_18.university_system.infrastructure.shared_context import get_auth
from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
from education_system.post_18.university_system.core.i18n import get_text
from education_system.post_18.university_system.modules.domain.finance.core.students import student_exists, get_student_name
from education_system.post_18.university_system.modules.domain.finance.core.aid import review_pending_aid_applications, approve_reject_aid_application, track_loan_repayments, manage_aid_types, apply_aid_to_fees
from education_system.post_18.university_system.modules.domain.finance.core.security_automation import log_audit_action

# Configure logging
logger = configure_logging(name=__name__)
warnings.filterwarnings('ignore')

try:
    auth = get_auth()
except Exception:
    auth = None
app = Flask(__name__)

# Initialize security headers for all responses
try:
    from education_system.post_18.university_system.infrastructure.security.flask_security_headers import init_security_headers
    init_security_headers(app)
except ImportError:
    pass  # Security headers module not available

# Encryption key for sensitive data
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

# Payment gateway configurations
PAYMENT_GATEWAYS = {
    'stripe': {
        'public_key': os.getenv('STRIPE_PUBLIC_KEY', ''),
        'secret_key': os.getenv('STRIPE_SECRET_KEY', ''),
        'webhook_secret': os.getenv('STRIPE_WEBHOOK_SECRET', '')
    },
    'paypal': {
        'client_id': os.getenv('PAYPAL_CLIENT_ID', ''),
        'client_secret': os.getenv('PAYPAL_CLIENT_SECRET', ''),
        'environment': os.getenv('PAYPAL_ENVIRONMENT', 'sandbox')
    }
}

# Currency exchange API configuration
# WARNING: Never commit real API keys to version control!
# Set these environment variables in your deployment environment
SUPPORTED_CURRENCIES = ['GBP', 'USD', 'EUR', 'CAD', 'AUD']
PAYMENT_GATEWAYS = {
    'stripe': {'public_key': '', 'secret_key': '', 'webhook_secret': ''},
    'paypal': {'client_id': '', 'client_secret': '', 'environment': 'sandbox'}
}
# Load exchange API key from environment variable
EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY', '')



def manage_scholarships():
    """Manage scholarships and grants"""
    from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics.scholarships import scholarship_reports
    global auth

    if not auth or not auth.current_user:
        print(get_text("finance.scholarship_programs.errors.login_required", "You must be logged in to manage scholarships."))
        return

    if not auth.check_permission('manage_finances'):
        print(get_text("finance.scholarship_programs.errors.no_permission", "You don't have permission to manage scholarships."))
        return

    while True:
        print("\n" + "=" * 50)
        print(get_text("finance.scholarship_programs.menu.title", "SCHOLARSHIP MANAGEMENT"))
        print("=" * 50)
        print(get_text("finance.scholarship_programs.menu.view_available", "1. View Available Scholarships"))
        print(get_text("finance.scholarship_programs.menu.create_new", "2. Create New Scholarship"))
        print(get_text("finance.scholarship_programs.menu.award_scholarship", "3. Award Scholarship to Student"))
        print(get_text("finance.scholarship_programs.menu.view_student", "4. View Student Scholarships"))
        print(get_text("finance.scholarship_programs.menu.reports", "5. Scholarship Reports"))
        print(get_text("finance.scholarship_programs.menu.return_finance", "6. Return to Finance Menu"))

        choice = input(get_text("finance.scholarship_programs.prompts.enter_choice_1_6", "Enter your choice (1-6): ")).strip()

        if choice == '1':
            view_available_scholarships()
        elif choice == '2':
            create_new_scholarship()
        elif choice == '3':
            award_scholarship_to_student()
        elif choice == '4':
            view_student_scholarships()
        elif choice == '5':
            scholarship_reports()
        elif choice == '6':
            return
        else:
            print(get_text("finance.scholarship_programs.errors.invalid_choice", "Invalid choice. Please try again."))

def view_available_scholarships():
    """View all available scholarships"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT scholarship_id, scholarship_name, description, amount, academic_year,
               criteria, deadline, is_active
        FROM scholarships
        ORDER BY is_active DESC, deadline
        ''')

        scholarships = cursor.fetchall()

        if not scholarships:
            print(get_text("finance.scholarship_programs.messages.no_scholarships_found", "No scholarships found."))
            return

        print(f"\n{get_text('finance.scholarship_programs.labels.available_scholarships', 'Available Scholarships')}:")
        print("=" * 100)

        for scholarship in scholarships:
            scholar_id, name, description, amount, academic_year, criteria, deadline, is_active = scholarship
            status = get_text("finance.scholarship_programs.labels.active", "Active") if is_active else get_text("finance.scholarship_programs.labels.inactive", "Inactive")

            print(f"{get_text('finance.scholarship_programs.labels.id', 'ID')}: {scholar_id}")
            print(f"{get_text('finance.scholarship_programs.labels.name', 'Name')}: {name}")
            print(f"{get_text('finance.scholarship_programs.labels.description', 'Description')}: {description}")
            print(f"{get_text('finance.scholarship_programs.labels.amount', 'Amount')}: £{amount:.2f}")
            print(f"{get_text('finance.scholarship_programs.labels.academic_year', 'Academic Year')}: {academic_year}")
            print(f"{get_text('finance.scholarship_programs.labels.criteria', 'Criteria')}: {criteria}")
            print(f"{get_text('finance.scholarship_programs.labels.deadline', 'Deadline')}: {deadline}")
            print(f"{get_text('finance.scholarship_programs.labels.status', 'Status')}: {status}")
            print("-" * 100)

        conn.close()

    except Exception as e:
        print(get_text("finance.scholarship_programs.errors.viewing_scholarships", "Error viewing scholarships: {error}").format(error=e))

def create_new_scholarship():
    """Create a new scholarship"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(f"\n{get_text('finance.scholarship_programs.messages.creating_new_scholarship', 'Creating New Scholarship')}:")

        name = input(get_text("finance.scholarship_programs.prompts.enter_scholarship_name", "Enter scholarship name: ")).strip()
        if not name:
            print(get_text("finance.scholarship_programs.errors.scholarship_name_required", "Scholarship name is required."))
            return

        description = input(get_text("finance.scholarship_programs.prompts.enter_description", "Enter description: ")).strip()
        amount = float(input(get_text("finance.scholarship_programs.prompts.enter_scholarship_amount", "Enter scholarship amount: £")))
        academic_year = input(get_text("finance.scholarship_programs.prompts.enter_academic_year", "Enter academic year (e.g., 2024-2025): ")).strip()
        criteria = input(get_text("finance.scholarship_programs.prompts.enter_eligibility_criteria", "Enter eligibility criteria: ")).strip()
        deadline = input(get_text("finance.scholarship_programs.prompts.enter_application_deadline", "Enter application deadline (YYYY-MM-DD): ")).strip()

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO scholarships
        (scholarship_name, description, amount, academic_year, criteria, deadline, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, description, amount, academic_year, criteria, deadline, 1, now, now))

        scholarship_id = cursor.lastrowid

        conn.commit()

        print(f"\n{get_text('finance.scholarship_programs.messages.scholarship_created_success', 'Scholarship created successfully! ID: {id}').format(id=scholarship_id)}")
        print(f"{get_text('finance.scholarship_programs.labels.name', 'Name')}: {name}")
        print(f"{get_text('finance.scholarship_programs.labels.amount', 'Amount')}: £{amount:.2f}")
        print(f"{get_text('finance.scholarship_programs.labels.academic_year', 'Academic Year')}: {academic_year}")

        conn.close()

    except Exception as e:
        print(get_text("finance.scholarship_programs.errors.creating_scholarship", "Error creating scholarship: {error}").format(error=e))

def award_scholarship_to_student():
    """Award a scholarship to a student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id = input(get_text("finance.scholarship_programs.prompts.enter_student_id", "Enter student ID: ")).strip()
        if not student_exists(student_id):
            print(get_text("finance.scholarship_programs.errors.student_not_exist", "Student with ID {student_id} does not exist.").format(student_id=student_id))
            return

        # Get available scholarships
        cursor.execute('''
        SELECT scholarship_id, scholarship_name, amount, criteria
        FROM scholarships
        WHERE is_active = 1
        ORDER BY scholarship_name
        ''')

        scholarships = cursor.fetchall()

        if not scholarships:
            print(get_text("finance.scholarship_programs.messages.no_active_scholarships", "No active scholarships available."))
            return

        print(f"\n{get_text('finance.scholarship_programs.labels.available_scholarships', 'Available Scholarships')}:")
        for i, (scholar_id, name, amount, criteria) in enumerate(scholarships, 1):
            print(f"{i}. {name} - £{amount:.2f}")
            print(f"   {get_text('finance.scholarship_programs.labels.criteria', 'Criteria')}: {criteria}")

        choice = input(get_text("finance.scholarship_programs.prompts.select_scholarship_number", "Select scholarship (number): ")).strip()
        try:
            scholarship_index = int(choice) - 1
            if 0 <= scholarship_index < len(scholarships):
                selected_scholarship = scholarships[scholarship_index]
                scholarship_id = selected_scholarship[0]
                scholarship_name = selected_scholarship[1]
                scholarship_amount = selected_scholarship[2]
            else:
                print(get_text("finance.scholarship_programs.errors.invalid_selection", "Invalid selection."))
                return
        except ValueError:
            print(get_text("finance.scholarship_programs.errors.invalid_input", "Invalid input."))
            return

        # Check if student already has this scholarship
        cursor.execute('''
        SELECT COUNT(*) FROM student_scholarships
        WHERE student_id = ? AND scholarship_id = ? AND status = 'active'
        ''', (student_id, scholarship_id))

        if cursor.fetchone()[0] > 0:
            print(get_text("finance.scholarship_programs.errors.student_already_has_scholarship", "Student already has this scholarship."))
            return

        award_amount = float(input(get_text("finance.scholarship_programs.prompts.enter_award_amount", "Enter award amount (max £{max_amount}): £").format(max_amount=f"{scholarship_amount:.2f}")))

        if award_amount > scholarship_amount:
            print(get_text("finance.scholarship_programs.errors.award_exceeds_max", "Award amount cannot exceed scholarship maximum."))
            return

        # Award the scholarship
        now = datetime.now()
        awarded_date = now.strftime('%Y-%m-%d')
        created_at = now.strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO student_scholarships
        (student_id, scholarship_id, amount, status, awarded_date, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (student_id, scholarship_id, award_amount, 'active', awarded_date, created_at))

        conn.commit()

        print(f"\n{get_text('finance.scholarship_programs.messages.scholarship_awarded_success', 'Scholarship awarded successfully!')}")
        print(f"{get_text('finance.scholarship_programs.labels.student', 'Student')}: {get_student_name(student_id)}")
        print(f"{get_text('finance.scholarship_programs.labels.scholarship', 'Scholarship')}: {scholarship_name}")
        print(f"{get_text('finance.scholarship_programs.labels.amount', 'Amount')}: £{award_amount:.2f}")
        print(f"{get_text('finance.scholarship_programs.labels.awarded_date', 'Awarded Date')}: {awarded_date}")

        conn.close()

    except Exception as e:
        print(get_text("finance.scholarship_programs.errors.awarding_scholarship", "Error awarding scholarship: {error}").format(error=e))

def view_student_scholarships():
    """View scholarships for a specific student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id = input(get_text("finance.scholarship_programs.prompts.enter_student_id", "Enter student ID: ")).strip()
        if not student_exists(student_id):
            print(get_text("finance.scholarship_programs.errors.student_not_exist", "Student with ID {student_id} does not exist.").format(student_id=student_id))
            return

        cursor.execute('''
        SELECT s.scholarship_name, ss.amount, ss.awarded_date, ss.status
        FROM student_scholarships ss
        JOIN scholarships s ON ss.scholarship_id = s.scholarship_id
        WHERE ss.student_id = ?
        ORDER BY ss.awarded_date DESC
        ''', (student_id,))

        student_scholarships = cursor.fetchall()

        if not student_scholarships:
            print(get_text("finance.scholarship_programs.messages.no_scholarships_for_student", "No scholarships found for student {student_id}.").format(student_id=student_id))
            return

        print(f"\n{get_text('finance.scholarship_programs.messages.scholarships_for_student', 'Scholarships for {student_name} ({student_id})').format(student_name=get_student_name(student_id), student_id=student_id)}:")
        print("=" * 80)

        total_awarded = 0
        for scholarship_name, amount, awarded_date, status in student_scholarships:
            print(f"{get_text('finance.scholarship_programs.labels.scholarship', 'Scholarship')}: {scholarship_name}")
            print(f"{get_text('finance.scholarship_programs.labels.amount', 'Amount')}: £{amount:.2f}")
            print(f"{get_text('finance.scholarship_programs.labels.awarded_date', 'Awarded Date')}: {awarded_date}")
            print(f"{get_text('finance.scholarship_programs.labels.status', 'Status')}: {status.title()}")
            print("-" * 80)

            if status == 'active':
                total_awarded += amount

        print(f"{get_text('finance.scholarship_programs.labels.total_active_scholarships', 'Total Active Scholarships')}: £{total_awarded:.2f}")
        print("=" * 80)

        conn.close()

    except Exception as e:
        print(get_text("finance.scholarship_programs.errors.viewing_student_scholarships", "Error viewing student scholarships: {error}").format(error=e))

def scholarship_distribution_summary():
    """Generate scholarship distribution summary"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT s.scholarship_name, s.amount as max_amount,
               COUNT(ss.student_scholarship_id) as recipients,
               SUM(ss.amount) as total_awarded,
               AVG(ss.amount) as avg_awarded
        FROM scholarships s
        LEFT JOIN student_scholarships ss ON s.scholarship_id = ss.scholarship_id AND ss.status = 'active'
        GROUP BY s.scholarship_id, s.scholarship_name, s.amount
        ORDER BY total_awarded DESC
        ''')

        scholarships = cursor.fetchall()

        print(f"\n{get_text('finance.scholarship_programs.reports.distribution_summary_title', 'Scholarship Distribution Summary')}")
        print("=" * 90)
        print(f"{get_text('finance.scholarship_programs.labels.scholarship_name', 'Scholarship Name'):<30} {get_text('finance.scholarship_programs.labels.max_amount', 'Max Amount'):<12} {get_text('finance.scholarship_programs.labels.recipients', 'Recipients'):<12} {get_text('finance.scholarship_programs.labels.total_awarded', 'Total Awarded'):<15} {get_text('finance.scholarship_programs.labels.avg_award', 'Avg Award'):<12}")
        print("-" * 90)

        total_recipients = 0
        total_awarded = 0

        for scholarship in scholarships:
            name, max_amt, recipients, awarded, avg_award = scholarship
            recipients = recipients or 0
            awarded = awarded or 0
            avg_award = avg_award or 0

            print(f"{name:<30} £{max_amt:<11.2f} {recipients:<12} £{awarded:<14.2f} £{avg_award:<11.2f}")
            total_recipients += recipients
            total_awarded += awarded

        print("-" * 90)
        print(f"{get_text('finance.scholarship_programs.labels.total', 'TOTAL'):<30} {'-':<12} {total_recipients:<12} £{total_awarded:<14.2f}")
        print("=" * 90)

        conn.close()

    except Exception as e:
        print(get_text("finance.scholarship_programs.errors.generating_distribution_summary", "Error generating scholarship distribution summary: {error}").format(error=e))

def scholarship_utilization_analysis():
    """Analyze scholarship utilization"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT s.academic_year,
               COUNT(DISTINCT s.scholarship_id) as available_scholarships,
               COUNT(ss.student_scholarship_id) as awards_given,
               SUM(s.amount) as total_available,
               SUM(ss.amount) as total_awarded
        FROM scholarships s
        LEFT JOIN student_scholarships ss ON s.scholarship_id = ss.scholarship_id AND ss.status = 'active'
        WHERE s.is_active = 1
        GROUP BY s.academic_year
        ORDER BY s.academic_year
        ''')

        utilization = cursor.fetchall()

        print(f"\n{get_text('finance.scholarship_programs.reports.utilization_analysis_title', 'Scholarship Utilization Analysis')}")
        print("=" * 80)
        print(f"{get_text('finance.scholarship_programs.labels.academic_year', 'Academic Year'):<15} {get_text('finance.scholarship_programs.labels.available', 'Available'):<12} {get_text('finance.scholarship_programs.labels.awards_given', 'Awards Given'):<12} {get_text('finance.scholarship_programs.labels.utilization_percent', 'Utilization %'):<15}")
        print("-" * 80)

        for year_data in utilization:
            academic_year, available, awards, total_avail, total_awarded = year_data
            utilization_rate = (awards / available * 100) if available > 0 else 0

            print(f"{academic_year:<15} {available:<12} {awards or 0:<12} {utilization_rate:<14.1f}%")

        print("=" * 80)

        conn.close()

    except Exception as e:
        print(get_text("finance.scholarship_programs.errors.analyzing_utilization", "Error analyzing scholarship utilization: {error}").format(error=e))

def manage_financial_aid():
    """Manage financial aid and loans"""
    from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics.scholarships import generate_aid_reports
    global auth

    if not auth or not auth.current_user:
        print(get_text("finance.scholarship_programs.errors.login_required_aid", "You must be logged in to manage financial aid."))
        return

    if not auth.check_permission('manage_finances'):
        print(get_text("finance.scholarship_programs.errors.no_permission_aid", "You don't have permission to manage financial aid."))
        return

    while True:
        print("\n" + "=" * 50)
        print(get_text("finance.scholarship_programs.menu.financial_aid_title", "FINANCIAL AID MANAGEMENT"))
        print("=" * 50)
        print(get_text("finance.scholarship_programs.menu.view_aid_applications", "1. View Financial Aid Applications"))
        print(get_text("finance.scholarship_programs.menu.create_aid_application", "2. Create New Financial Aid Application"))
        print(get_text("finance.scholarship_programs.menu.review_pending", "3. Review Pending Applications"))
        print(get_text("finance.scholarship_programs.menu.approve_reject", "4. Approve/Reject Applications"))
        print(get_text("finance.scholarship_programs.menu.disburse_aid", "5. Disburse Financial Aid"))
        print(get_text("finance.scholarship_programs.menu.track_repayments", "6. Track Loan Repayments"))
        print(get_text("finance.scholarship_programs.menu.generate_reports", "7. Generate Financial Aid Reports"))
        print(get_text("finance.scholarship_programs.menu.manage_aid_types", "8. Manage Aid Types"))
        print(get_text("finance.scholarship_programs.menu.return_finance", "9. Return to Finance Menu"))

        choice = input(get_text("finance.scholarship_programs.prompts.enter_choice_1_9", "Enter your choice (1-9): ")).strip()

        if choice == '1':
            view_financial_aid_applications()
        elif choice == '2':
            create_financial_aid_application()
        elif choice == '3':
            review_pending_aid_applications()
        elif choice == '4':
            approve_reject_aid_application()
        elif choice == '5':
            disburse_financial_aid()
        elif choice == '6':
            track_loan_repayments()
        elif choice == '7':
            generate_aid_reports()
        elif choice == '8':
            manage_aid_types()
        elif choice == '9':
            return
        else:
            print(get_text("finance.scholarship_programs.errors.invalid_choice", "Invalid choice. Please try again."))

def view_financial_aid_applications():
    """View all financial aid applications"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get filter option
        print(f"\n{get_text('finance.scholarship_programs.labels.filter_options', 'Filter options')}:")
        print(get_text("finance.scholarship_programs.menu.filter_all", "1. All applications"))
        print(get_text("finance.scholarship_programs.menu.filter_pending", "2. Pending applications"))
        print(get_text("finance.scholarship_programs.menu.filter_approved", "3. Approved applications"))
        print(get_text("finance.scholarship_programs.menu.filter_by_student", "4. By student ID"))
        print(get_text("finance.scholarship_programs.menu.filter_by_aid_type", "5. By aid type"))

        filter_choice = input(get_text("finance.scholarship_programs.prompts.select_filter", "Select filter (1-5): ")).strip()

        base_query = '''
        SELECT sfa.aid_id, sfa.student_id, s.first_name, s.last_name,
               fat.aid_name, sfa.awarded_amount, sfa.status, sfa.application_date,
               sfa.approval_date, sfa.approved_by
        FROM student_financial_aid sfa
        JOIN students s ON sfa.student_id = s.student_id
        JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
        '''

        params = []

        if filter_choice == '2':
            base_query += " WHERE sfa.status = 'pending'"
        elif filter_choice == '3':
            base_query += " WHERE sfa.status = 'approved'"
        elif filter_choice == '4':
            student_id = input(get_text("finance.scholarship_programs.prompts.enter_student_id", "Enter student ID: ")).strip()
            base_query += " WHERE sfa.student_id = ?"
            params.append(student_id)
        elif filter_choice == '5':
            cursor.execute('SELECT aid_type_id, aid_name FROM financial_aid_types WHERE is_active = 1')
            aid_types = cursor.fetchall()

            if aid_types:
                print(f"\n{get_text('finance.scholarship_programs.labels.available_aid_types', 'Available aid types')}:")
                for i, (aid_id, aid_name) in enumerate(aid_types, 1):
                    print(f"{i}. {aid_name}")

                type_choice = input(get_text("finance.scholarship_programs.prompts.select_aid_type", "Select aid type: ")).strip()
                try:
                    type_index = int(type_choice) - 1
                    if 0 <= type_index < len(aid_types):
                        selected_aid_type = aid_types[type_index][0]
                        base_query += " WHERE sfa.aid_type_id = ?"
                        params.append(selected_aid_type)
                except ValueError:
                    print(get_text("finance.scholarship_programs.errors.invalid_selection", "Invalid selection."))
                    return

        base_query += " ORDER BY sfa.application_date DESC"

        cursor.execute(base_query, params)
        applications = cursor.fetchall()

        if not applications:
            print(get_text("finance.scholarship_programs.messages.no_aid_applications_found", "No financial aid applications found."))
            conn.close()
            return

        print(f"\n{get_text('finance.scholarship_programs.labels.financial_aid_applications', 'Financial Aid Applications')}:")
        print("=" * 120)
        print(f"{get_text('finance.scholarship_programs.labels.aid_id', 'Aid ID'):<8} {get_text('finance.scholarship_programs.labels.student_id', 'Student ID'):<12} {get_text('finance.scholarship_programs.labels.student_name', 'Student Name'):<25} {get_text('finance.scholarship_programs.labels.aid_type', 'Aid Type'):<20} {get_text('finance.scholarship_programs.labels.amount', 'Amount'):<12} {get_text('finance.scholarship_programs.labels.status', 'Status'):<12} {get_text('finance.scholarship_programs.labels.applied', 'Applied'):<12}")
        print("-" * 120)

        for app in applications:
            aid_id, student_id, first_name, last_name, aid_name, amount, status, app_date, approval_date, approved_by = app
            student_name = f"{first_name} {last_name}"

            print(f"{aid_id:<8} {student_id:<12} {student_name:<25} {aid_name:<20} £{amount:<11.2f} {status:<12} {app_date:<12}")

        print("=" * 120)
        print(get_text("finance.scholarship_programs.messages.total_applications", "Total applications: {count}").format(count=len(applications)))

        conn.close()

    except sqlite3.Error as e:
        print(get_text("finance.scholarship_programs.errors.database_error", "Database error: {error}").format(error=e))

def create_financial_aid_application():
    """Create a new financial aid application"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student ID
        student_id = input(get_text("finance.scholarship_programs.prompts.enter_student_id", "Enter student ID: ")).strip()

        if not student_exists(student_id):
            print(get_text("finance.scholarship_programs.errors.student_not_exist", "Student with ID {student_id} does not exist.").format(student_id=student_id))
            conn.close()
            return

        # Get available aid types
        cursor.execute('''
        SELECT aid_type_id, aid_name, aid_category, max_amount, eligibility_criteria
        FROM financial_aid_types
        WHERE is_active = 1
        ORDER BY aid_category, aid_name
        ''')

        aid_types = cursor.fetchall()

        if not aid_types:
            print(get_text("finance.scholarship_programs.messages.no_aid_types_available", "No financial aid types available."))
            conn.close()
            return

        print(f"\n{get_text('finance.scholarship_programs.labels.available_financial_aid_types', 'Available Financial Aid Types')}:")
        for i, (aid_id, aid_name, category, max_amount, criteria) in enumerate(aid_types, 1):
            max_amt_str = f"£{max_amount:.2f}" if max_amount else get_text("finance.scholarship_programs.labels.no_limit", "No limit")
            print(f"{i}. {aid_name} ({category.title()}) - {get_text('finance.scholarship_programs.labels.max', 'Max')}: {max_amt_str}")
            print(f"   {get_text('finance.scholarship_programs.labels.criteria', 'Criteria')}: {criteria}")

        # Select aid type
        type_choice = input(f"\n{get_text('finance.scholarship_programs.prompts.select_aid_type_number', 'Select aid type (number): ')}").strip()
        try:
            type_index = int(type_choice) - 1
            if 0 <= type_index < len(aid_types):
                selected_aid = aid_types[type_index]
                aid_type_id, aid_name, category, max_amount, criteria = selected_aid
            else:
                print(get_text("finance.scholarship_programs.errors.invalid_selection", "Invalid selection."))
                conn.close()
                return
        except ValueError:
            print(get_text("finance.scholarship_programs.errors.invalid_input", "Invalid input."))
            conn.close()
            return

        # Get application details
        print(f"\n{get_text('finance.scholarship_programs.messages.applying_for', 'Applying for')}: {aid_name}")
        print(f"{get_text('finance.scholarship_programs.labels.eligibility_criteria', 'Eligibility criteria')}: {criteria}")

        while True:
            try:
                max_display = f"£{max_amount}" if max_amount else get_text("finance.scholarship_programs.labels.unlimited", "unlimited")
                requested_amount = float(input(get_text("finance.scholarship_programs.prompts.enter_requested_amount", "Enter requested amount (max {max_amount}): £").format(max_amount=max_display)))
                if requested_amount <= 0:
                    print(get_text("finance.scholarship_programs.errors.amount_greater_than_zero", "Amount must be greater than zero."))
                    continue
                if max_amount and requested_amount > max_amount:
                    print(get_text("finance.scholarship_programs.errors.amount_exceeds_max", "Amount exceeds maximum allowed (£{max_amount}).").format(max_amount=f"{max_amount:.2f}"))
                    continue
                break
            except ValueError:
                print(get_text("finance.scholarship_programs.errors.invalid_amount_input", "Invalid input. Please enter a valid amount."))

        # Get justification
        justification = input(get_text("finance.scholarship_programs.prompts.enter_justification", "Enter justification for aid request: ")).strip()
        if not justification:
            print(get_text("finance.scholarship_programs.errors.justification_required", "Justification is required."))
            conn.close()
            return

        # Get supporting documentation
        supporting_docs = input(get_text("finance.scholarship_programs.prompts.enter_supporting_docs", "Enter supporting documentation (optional): ")).strip()

        # Create application
        now = datetime.now()
        application_date = now.strftime('%Y-%m-%d')
        created_at = now.strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO student_financial_aid
        (student_id, aid_type_id, awarded_amount, remaining_amount, status,
         application_date, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, aid_type_id, requested_amount, requested_amount, 'pending',
              application_date, f"Justification: {justification}\nDocs: {supporting_docs}",
              created_at, created_at))

        aid_id = cursor.lastrowid

        conn.commit()

        print(f"\n{get_text('finance.scholarship_programs.messages.aid_application_created_success', 'Financial aid application created successfully!')}")
        print(f"{get_text('finance.scholarship_programs.labels.application_id', 'Application ID')}: {aid_id}")
        print(f"{get_text('finance.scholarship_programs.labels.student', 'Student')}: {get_student_name(student_id)} ({student_id})")
        print(f"{get_text('finance.scholarship_programs.labels.aid_type', 'Aid Type')}: {aid_name}")
        print(f"{get_text('finance.scholarship_programs.labels.requested_amount', 'Requested Amount')}: £{requested_amount:.2f}")
        print(f"{get_text('finance.scholarship_programs.labels.status', 'Status')}: {get_text('finance.scholarship_programs.labels.pending_review', 'Pending Review')}")

        # Log the action
        log_audit_action('create_aid_application', 'student_financial_aid', str(aid_id), {
            'student_id': student_id,
            'aid_type': aid_name,
            'amount': requested_amount
        })

        conn.close()

    except sqlite3.Error as e:
        print(get_text("finance.scholarship_programs.errors.database_error", "Database error: {error}").format(error=e))

def disburse_financial_aid():
    """Disburse approved financial aid"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get approved but not fully disbursed aid
        cursor.execute('''
        SELECT sfa.aid_id, sfa.student_id, s.first_name, s.last_name,
               fat.aid_name, sfa.awarded_amount, sfa.disbursed_amount,
               sfa.remaining_amount, sfa.approval_date
        FROM student_financial_aid sfa
        JOIN students s ON sfa.student_id = s.student_id
        JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
        WHERE sfa.status = 'approved' AND sfa.remaining_amount > 0
        ORDER BY sfa.approval_date
        ''')

        pending_disbursements = cursor.fetchall()

        if not pending_disbursements:
            print(get_text("finance.scholarship_programs.messages.no_pending_disbursements", "No approved financial aid pending disbursement."))
            conn.close()
            return

        print(f"\n{get_text('finance.scholarship_programs.labels.approved_aid_pending_disbursement', 'Approved Financial Aid Pending Disbursement')}:")
        print("=" * 120)
        for i, aid in enumerate(pending_disbursements, 1):
            aid_id, student_id, first_name, last_name, aid_name, awarded, disbursed, remaining, approval_date = aid
            student_name = f"{first_name} {last_name}"

            print(f"{i}. {get_text('finance.scholarship_programs.labels.aid_id', 'Aid ID')} {aid_id} - {student_name} ({student_id})")
            print(f"   {get_text('finance.scholarship_programs.labels.type', 'Type')}: {aid_name}")
            print(f"   {get_text('finance.scholarship_programs.labels.awarded', 'Awarded')}: £{awarded:.2f}, {get_text('finance.scholarship_programs.labels.disbursed', 'Disbursed')}: £{disbursed:.2f}, {get_text('finance.scholarship_programs.labels.remaining', 'Remaining')}: £{remaining:.2f}")
            print(f"   {get_text('finance.scholarship_programs.labels.approved', 'Approved')}: {approval_date}")
            print("-" * 120)

        # Select aid to disburse
        aid_choice = input(f"\n{get_text('finance.scholarship_programs.prompts.select_aid_to_disburse', 'Select aid to disburse (1-{count}): ').format(count=len(pending_disbursements))}").strip()
        try:
            aid_index = int(aid_choice) - 1
            if 0 <= aid_index < len(pending_disbursements):
                selected_aid = pending_disbursements[aid_index]
                aid_id = selected_aid[0]
                remaining_amount = selected_aid[7]
            else:
                print(get_text("finance.scholarship_programs.errors.invalid_selection", "Invalid selection."))
                conn.close()
                return
        except ValueError:
            print(get_text("finance.scholarship_programs.errors.invalid_input", "Invalid input."))
            conn.close()
            return

        # Get disbursement details
        print(f"\n{get_text('finance.scholarship_programs.messages.disbursing_aid_id', 'Disbursing Aid ID')}: {aid_id}")
        print(f"{get_text('finance.scholarship_programs.labels.remaining_amount', 'Remaining amount')}: £{remaining_amount:.2f}")

        while True:
            try:
                disbursement_amount = float(input(get_text("finance.scholarship_programs.prompts.enter_disbursement_amount", "Enter disbursement amount (max £{max_amount}): £").format(max_amount=f"{remaining_amount:.2f}")))
                if disbursement_amount <= 0:
                    print(get_text("finance.scholarship_programs.errors.amount_greater_than_zero", "Amount must be greater than zero."))
                    continue
                if disbursement_amount > remaining_amount:
                    print(get_text("finance.scholarship_programs.errors.disbursement_exceeds_remaining", "Disbursement amount cannot exceed remaining amount."))
                    continue
                break
            except ValueError:
                print(get_text("finance.scholarship_programs.errors.invalid_amount_input", "Invalid input. Please enter a valid amount."))

        # Get disbursement method
        disbursement_methods = ['bank_transfer', 'check', 'direct_to_fees', 'cash']
        print(f"\n{get_text('finance.scholarship_programs.labels.disbursement_methods', 'Disbursement methods')}:")
        method_labels = [
            get_text("finance.scholarship_programs.labels.bank_transfer", "Bank Transfer"),
            get_text("finance.scholarship_programs.labels.check", "Check"),
            get_text("finance.scholarship_programs.labels.direct_to_fees", "Direct To Fees"),
            get_text("finance.scholarship_programs.labels.cash", "Cash")
        ]
        for i, method_label in enumerate(method_labels, 1):
            print(f"{i}. {method_label}")

        method_choice = input(get_text("finance.scholarship_programs.prompts.select_disbursement_method", "Select disbursement method (1-4): ")).strip()
        try:
            method_index = int(method_choice) - 1
            if 0 <= method_index < len(disbursement_methods):
                disbursement_method = disbursement_methods[method_index]
            else:
                print(get_text("finance.scholarship_programs.errors.invalid_selection", "Invalid selection."))
                conn.close()
                return
        except ValueError:
            print(get_text("finance.scholarship_programs.errors.invalid_input", "Invalid input."))
            conn.close()
            return

        # Get disbursement date
        disbursement_date = input(get_text("finance.scholarship_programs.prompts.enter_disbursement_date", "Enter disbursement date (YYYY-MM-DD) or press Enter for today: ")).strip()
        if not disbursement_date:
            disbursement_date = datetime.now().strftime('%Y-%m-%d')

        notes = input(get_text("finance.scholarship_programs.prompts.enter_disbursement_notes", "Enter disbursement notes (optional): ")).strip()

        # Process disbursement
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_disbursed = selected_aid[6] + disbursement_amount
        new_remaining = remaining_amount - disbursement_amount
        new_status = 'completed' if new_remaining == 0 else 'disbursed'

        # Update aid record
        cursor.execute('''
        UPDATE student_financial_aid
        SET disbursed_amount = ?, remaining_amount = ?, status = ?, updated_at = ?
        WHERE aid_id = ?
        ''', (new_disbursed, new_remaining, new_status, now, aid_id))

        # If disbursing directly to fees, apply to student fees
        if disbursement_method == 'direct_to_fees':
            apply_aid_to_fees(selected_aid[1], disbursement_amount, aid_id)

        conn.commit()

        print(f"\n{get_text('finance.scholarship_programs.messages.disbursement_processed_success', 'Disbursement processed successfully!')}")
        print(f"{get_text('finance.scholarship_programs.labels.amount', 'Amount')}: £{disbursement_amount:.2f}")
        print(f"{get_text('finance.scholarship_programs.labels.method', 'Method')}: {method_labels[method_index]}")
        print(f"{get_text('finance.scholarship_programs.labels.date', 'Date')}: {disbursement_date}")
        print(f"{get_text('finance.scholarship_programs.labels.remaining_to_disburse', 'Remaining to disburse')}: £{new_remaining:.2f}")

        # Log the action
        log_audit_action('disburse_aid', 'student_financial_aid', str(aid_id), {
            'disbursement_amount': disbursement_amount,
            'method': disbursement_method,
            'disbursed_by': auth.current_user['username']
        })

        conn.close()

    except sqlite3.Error as e:
        print(get_text("finance.scholarship_programs.errors.database_error", "Database error: {error}").format(error=e))
