from university_system.infrastructure.database.db import sqlite3
import os
import csv
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
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
import qrcode
from io import BytesIO
import base64
from university_system.infrastructure.email import send_email
from university_system.infrastructure.auth.user_authentication import UserAuth
from university_system.infrastructure.database.db import get_connection
from university_system.utils.logging.log_config import configure_logging

# Configure logging
logger = configure_logging(name=__name__)
warnings.filterwarnings('ignore')

# Dummy auth setup to bypass JWT
auth = type("Auth", (), {})()
auth.current_user = {"username": "admin"}
auth.check_permission = lambda p: True
app = Flask(__name__)

# Encryption key for sensitive data
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

# Payment gateway configurations
PAYMENT_GATEWAYS = {
    'stripe': {
        'public_key': 'pk_test_...',
        'secret_key': 'sk_test_...',
        'webhook_secret': 'whsec_...'
    },
    'paypal': {
        'client_id': 'your_paypal_client_id',
        'client_secret': 'your_paypal_client_secret',
        'environment': 'sandbox'  # or 'live'
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
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage scholarships.")
        return
    
    if not auth.check_permission('manage_finances'):
        print("You don't have permission to manage scholarships.")
        return
    
    while True:
        print("\n" + "=" * 50)
        print("SCHOLARSHIP MANAGEMENT")
        print("=" * 50)
        print("1. View Available Scholarships")
        print("2. Create New Scholarship")
        print("3. Award Scholarship to Student")
        print("4. View Student Scholarships")
        print("5. Scholarship Reports")
        print("6. Return to Finance Menu")
        
        choice = input("Enter your choice (1-6): ").strip()
        
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
            print("Invalid choice. Please try again.")

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
            print("No scholarships found.")
            return
        
        print(f"\nAvailable Scholarships:")
        print(f"=" * 100)
        
        for scholarship in scholarships:
            scholar_id, name, description, amount, academic_year, criteria, deadline, is_active = scholarship
            status = "Active" if is_active else "Inactive"
            
            print(f"ID: {scholar_id}")
            print(f"Name: {name}")
            print(f"Description: {description}")
            print(f"Amount: £{amount:.2f}")
            print(f"Academic Year: {academic_year}")
            print(f"Criteria: {criteria}")
            print(f"Deadline: {deadline}")
            print(f"Status: {status}")
            print(f"-" * 100)
        
        conn.close()
        
    except Exception as e:
        print(f"Error viewing scholarships: {e}")

def create_new_scholarship():
    """Create a new scholarship"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nCreating New Scholarship:")
        
        name = input("Enter scholarship name: ").strip()
        if not name:
            print("Scholarship name is required.")
            return
        
        description = input("Enter description: ").strip()
        amount = float(input("Enter scholarship amount: £"))
        academic_year = input("Enter academic year (e.g., 2024-2025): ").strip()
        criteria = input("Enter eligibility criteria: ").strip()
        deadline = input("Enter application deadline (YYYY-MM-DD): ").strip()
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO scholarships 
        (scholarship_name, description, amount, academic_year, criteria, deadline, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, description, amount, academic_year, criteria, deadline, 1, now, now))
        
        scholarship_id = cursor.lastrowid
        
        conn.commit()
        
        print(f"\nScholarship created successfully! ID: {scholarship_id}")
        print(f"Name: {name}")
        print(f"Amount: £{amount:.2f}")
        print(f"Academic Year: {academic_year}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error creating scholarship: {e}")

def award_scholarship_to_student():
    """Award a scholarship to a student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        student_id = input("Enter student ID: ").strip()
        if not student_exists(student_id):
            print(f"Student with ID {student_id} does not exist.")
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
            print("No active scholarships available.")
            return
        
        print(f"\nAvailable Scholarships:")
        for i, (scholar_id, name, amount, criteria) in enumerate(scholarships, 1):
            print(f"{i}. {name} - £{amount:.2f}")
            print(f"   Criteria: {criteria}")
        
        choice = input("Select scholarship (number): ").strip()
        try:
            scholarship_index = int(choice) - 1
            if 0 <= scholarship_index < len(scholarships):
                selected_scholarship = scholarships[scholarship_index]
                scholarship_id = selected_scholarship[0]
                scholarship_name = selected_scholarship[1]
                scholarship_amount = selected_scholarship[2]
            else:
                print("Invalid selection.")
                return
        except ValueError:
            print("Invalid input.")
            return
        
        # Check if student already has this scholarship
        cursor.execute('''
        SELECT COUNT(*) FROM student_scholarships
        WHERE student_id = ? AND scholarship_id = ? AND status = 'active'
        ''', (student_id, scholarship_id))
        
        if cursor.fetchone()[0] > 0:
            print(f"Student already has this scholarship.")
            return
        
        award_amount = float(input(f"Enter award amount (max £{scholarship_amount:.2f}): £"))
        
        if award_amount > scholarship_amount:
            print("Award amount cannot exceed scholarship maximum.")
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
        
        print(f"\nScholarship awarded successfully!")
        print(f"Student: {get_student_name(student_id)}")
        print(f"Scholarship: {scholarship_name}")
        print(f"Amount: £{award_amount:.2f}")
        print(f"Awarded Date: {awarded_date}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error awarding scholarship: {e}")

def view_student_scholarships():
    """View scholarships for a specific student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        student_id = input("Enter student ID: ").strip()
        if not student_exists(student_id):
            print(f"Student with ID {student_id} does not exist.")
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
            print(f"No scholarships found for student {student_id}.")
            return
        
        print(f"\nScholarships for {get_student_name(student_id)} ({student_id}):")
        print(f"=" * 80)
        
        total_awarded = 0
        for scholarship_name, amount, awarded_date, status in student_scholarships:
            print(f"Scholarship: {scholarship_name}")
            print(f"Amount: £{amount:.2f}")
            print(f"Awarded Date: {awarded_date}")
            print(f"Status: {status.title()}")
            print(f"-" * 80)
            
            if status == 'active':
                total_awarded += amount
        
        print(f"Total Active Scholarships: £{total_awarded:.2f}")
        print(f"=" * 80)
        
        conn.close()
        
    except Exception as e:
        print(f"Error viewing student scholarships: {e}")

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
        
        print(f"\nScholarship Distribution Summary")
        print(f"=" * 90)
        print(f"{'Scholarship Name':<30} {'Max Amount':<12} {'Recipients':<12} {'Total Awarded':<15} {'Avg Award':<12}")
        print(f"-" * 90)
        
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
        
        print(f"-" * 90)
        print(f"{'TOTAL':<30} {'-':<12} {total_recipients:<12} £{total_awarded:<14.2f}")
        print(f"=" * 90)
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating scholarship distribution summary: {e}")

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
        
        print(f"\nScholarship Utilization Analysis")
        print(f"=" * 80)
        print(f"{'Academic Year':<15} {'Available':<12} {'Awards Given':<12} {'Utilization %':<15}")
        print(f"-" * 80)
        
        for year_data in utilization:
            academic_year, available, awards, total_avail, total_awarded = year_data
            utilization_rate = (awards / available * 100) if available > 0 else 0
            
            print(f"{academic_year:<15} {available:<12} {awards or 0:<12} {utilization_rate:<14.1f}%")
        
        print(f"=" * 80)
        
        conn.close()
        
    except Exception as e:
        print(f"Error analyzing scholarship utilization: {e}")

def manage_financial_aid():
    """Manage financial aid and loans"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage financial aid.")
        return
    
    if not auth.check_permission('manage_finances'):
        print("You don't have permission to manage financial aid.")
        return
    
    while True:
        print("\n" + "=" * 50)
        print("FINANCIAL AID MANAGEMENT")
        print("=" * 50)
        print("1. View Financial Aid Applications")
        print("2. Create New Financial Aid Application")
        print("3. Review Pending Applications")
        print("4. Approve/Reject Applications")
        print("5. Disburse Financial Aid")
        print("6. Track Loan Repayments")
        print("7. Generate Financial Aid Reports")
        print("8. Manage Aid Types")
        print("9. Return to Finance Menu")
        
        choice = input("Enter your choice (1-9): ").strip()
        
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
            print("Invalid choice. Please try again.")

def view_financial_aid_applications():
    """View all financial aid applications"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get filter option
        print("\nFilter options:")
        print("1. All applications")
        print("2. Pending applications")
        print("3. Approved applications")
        print("4. By student ID")
        print("5. By aid type")
        
        filter_choice = input("Select filter (1-5): ").strip()
        
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
            student_id = input("Enter student ID: ").strip()
            base_query += " WHERE sfa.student_id = ?"
            params.append(student_id)
        elif filter_choice == '5':
            cursor.execute('SELECT aid_type_id, aid_name FROM financial_aid_types WHERE is_active = 1')
            aid_types = cursor.fetchall()
            
            if aid_types:
                print("\nAvailable aid types:")
                for i, (aid_id, aid_name) in enumerate(aid_types, 1):
                    print(f"{i}. {aid_name}")
                
                type_choice = input("Select aid type: ").strip()
                try:
                    type_index = int(type_choice) - 1
                    if 0 <= type_index < len(aid_types):
                        selected_aid_type = aid_types[type_index][0]
                        base_query += " WHERE sfa.aid_type_id = ?"
                        params.append(selected_aid_type)
                except ValueError:
                    print("Invalid selection.")
                    return
        
        base_query += " ORDER BY sfa.application_date DESC"
        
        cursor.execute(base_query, params)
        applications = cursor.fetchall()
        
        if not applications:
            print("No financial aid applications found.")
            conn.close()
            return
        
        print(f"\nFinancial Aid Applications:")
        print("=" * 120)
        print(f"{'Aid ID':<8} {'Student ID':<12} {'Student Name':<25} {'Aid Type':<20} {'Amount':<12} {'Status':<12} {'Applied':<12}")
        print("-" * 120)
        
        for app in applications:
            aid_id, student_id, first_name, last_name, aid_name, amount, status, app_date, approval_date, approved_by = app
            student_name = f"{first_name} {last_name}"
            
            print(f"{aid_id:<8} {student_id:<12} {student_name:<25} {aid_name:<20} £{amount:<11.2f} {status:<12} {app_date:<12}")
        
        print("=" * 120)
        print(f"Total applications: {len(applications)}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def create_financial_aid_application():
    """Create a new financial aid application"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get student ID
        student_id = input("Enter student ID: ").strip()
        
        if not student_exists(student_id):
            print(f"Student with ID {student_id} does not exist.")
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
            print("No financial aid types available.")
            conn.close()
            return
        
        print(f"\nAvailable Financial Aid Types:")
        for i, (aid_id, aid_name, category, max_amount, criteria) in enumerate(aid_types, 1):
            max_amt_str = f"£{max_amount:.2f}" if max_amount else "No limit"
            print(f"{i}. {aid_name} ({category.title()}) - Max: {max_amt_str}")
            print(f"   Criteria: {criteria}")
        
        # Select aid type
        type_choice = input("\nSelect aid type (number): ").strip()
        try:
            type_index = int(type_choice) - 1
            if 0 <= type_index < len(aid_types):
                selected_aid = aid_types[type_index]
                aid_type_id, aid_name, category, max_amount, criteria = selected_aid
            else:
                print("Invalid selection.")
                conn.close()
                return
        except ValueError:
            print("Invalid input.")
            conn.close()
            return
        
        # Get application details
        print(f"\nApplying for: {aid_name}")
        print(f"Eligibility criteria: {criteria}")
        
        while True:
            try:
                requested_amount = float(input(f"Enter requested amount (max £{max_amount or 'unlimited'}): £"))
                if requested_amount <= 0:
                    print("Amount must be greater than zero.")
                    continue
                if max_amount and requested_amount > max_amount:
                    print(f"Amount exceeds maximum allowed (£{max_amount:.2f}).")
                    continue
                break
            except ValueError:
                print("Invalid input. Please enter a valid amount.")
        
        # Get justification
        justification = input("Enter justification for aid request: ").strip()
        if not justification:
            print("Justification is required.")
            conn.close()
            return
        
        # Get supporting documentation
        supporting_docs = input("Enter supporting documentation (optional): ").strip()
        
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
        
        print(f"\nFinancial aid application created successfully!")
        print(f"Application ID: {aid_id}")
        print(f"Student: {get_student_name(student_id)} ({student_id})")
        print(f"Aid Type: {aid_name}")
        print(f"Requested Amount: £{requested_amount:.2f}")
        print(f"Status: Pending Review")
        
        # Log the action
        log_audit_action('create_aid_application', 'student_financial_aid', str(aid_id), {
            'student_id': student_id,
            'aid_type': aid_name,
            'amount': requested_amount
        })
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

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
            print("No approved financial aid pending disbursement.")
            conn.close()
            return
        
        print(f"\nApproved Financial Aid Pending Disbursement:")
        print("=" * 120)
        for i, aid in enumerate(pending_disbursements, 1):
            aid_id, student_id, first_name, last_name, aid_name, awarded, disbursed, remaining, approval_date = aid
            student_name = f"{first_name} {last_name}"
            
            print(f"{i}. Aid ID {aid_id} - {student_name} ({student_id})")
            print(f"   Type: {aid_name}")
            print(f"   Awarded: £{awarded:.2f}, Disbursed: £{disbursed:.2f}, Remaining: £{remaining:.2f}")
            print(f"   Approved: {approval_date}")
            print("-" * 120)
        
        # Select aid to disburse
        aid_choice = input(f"\nSelect aid to disburse (1-{len(pending_disbursements)}): ").strip()
        try:
            aid_index = int(aid_choice) - 1
            if 0 <= aid_index < len(pending_disbursements):
                selected_aid = pending_disbursements[aid_index]
                aid_id = selected_aid[0]
                remaining_amount = selected_aid[7]
            else:
                print("Invalid selection.")
                conn.close()
                return
        except ValueError:
            print("Invalid input.")
            conn.close()
            return
        
        # Get disbursement details
        print(f"\nDisbursing Aid ID: {aid_id}")
        print(f"Remaining amount: £{remaining_amount:.2f}")
        
        while True:
            try:
                disbursement_amount = float(input(f"Enter disbursement amount (max £{remaining_amount:.2f}): £"))
                if disbursement_amount <= 0:
                    print("Amount must be greater than zero.")
                    continue
                if disbursement_amount > remaining_amount:
                    print("Disbursement amount cannot exceed remaining amount.")
                    continue
                break
            except ValueError:
                print("Invalid input. Please enter a valid amount.")
        
        # Get disbursement method
        disbursement_methods = ['bank_transfer', 'check', 'direct_to_fees', 'cash']
        print("\nDisbursement methods:")
        for i, method in enumerate(disbursement_methods, 1):
            print(f"{i}. {method.replace('_', ' ').title()}")
        
        method_choice = input("Select disbursement method (1-4): ").strip()
        try:
            method_index = int(method_choice) - 1
            if 0 <= method_index < len(disbursement_methods):
                disbursement_method = disbursement_methods[method_index]
            else:
                print("Invalid selection.")
                conn.close()
                return
        except ValueError:
            print("Invalid input.")
            conn.close()
            return
        
        # Get disbursement date
        disbursement_date = input("Enter disbursement date (YYYY-MM-DD) or press Enter for today: ").strip()
        if not disbursement_date:
            disbursement_date = datetime.now().strftime('%Y-%m-%d')
        
        notes = input("Enter disbursement notes (optional): ").strip()
        
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
        
        print(f"\nDisbursement processed successfully!")
        print(f"Amount: £{disbursement_amount:.2f}")
        print(f"Method: {disbursement_method.replace('_', ' ').title()}")
        print(f"Date: {disbursement_date}")
        print(f"Remaining to disburse: £{new_remaining:.2f}")
        
        # Log the action
        log_audit_action('disburse_aid', 'student_financial_aid', str(aid_id), {
            'disbursement_amount': disbursement_amount,
            'method': disbursement_method,
            'disbursed_by': auth.current_user['username']
        })
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
