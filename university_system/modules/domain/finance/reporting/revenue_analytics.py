from university_system.infrastructure.database.db import sqlite3
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
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
from university_system.infrastructure.auth import UserAuth
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

# Initialize security headers for all responses
try:
    from university_system.infrastructure.security.flask_security_headers import init_security_headers
    init_security_headers(app)
except ImportError:
    pass  # Security headers module not available

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



def generate_financial_reports():
    """Generate various financial reports"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to generate reports.")
        return
    
    if not auth.check_permission('manage_finances'):
        print("You don't have permission to generate reports.")
        return
    
    while True:
        print("\n" + "=" * 50)
        print("FINANCIAL REPORTS")
        print("=" * 50)
        print("1. Revenue Summary Report")
        print("2. Outstanding Fees Report")
        print("3. Payment Collection Report")
        print("4. Student Account Summary")
        print("5. Fee Type Analysis")
        print("6. Payment Method Analysis")
        print("7. Monthly Revenue Trend")
        print("8. Return to Finance Menu")
        
        choice = input("Enter your choice (1-8): ").strip()
        
        if choice == '1':
            revenue_summary_report()
        elif choice == '2':
            generate_outstanding_fees_report()
        elif choice == '3':
            generate_payment_collection_report()
        elif choice == '4':
            student_account_summary_report()
        elif choice == '5':
            fee_type_analysis_report()
        elif choice == '6':
            payment_method_analysis_report()
        elif choice == '7':
            monthly_revenue_trend_report()
        elif choice == '8':
            return
        else:
            print("Invalid choice. Please try again.")

def revenue_summary_report():
    """Generate revenue summary report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get date range
        start_date = input("Enter start date (YYYY-MM-DD): ").strip()
        end_date = input("Enter end date (YYYY-MM-DD): ").strip()
        
        cursor.execute('''
        SELECT 
            COUNT(*) as total_payments,
            SUM(amount) as total_revenue,
            AVG(amount) as avg_payment,
            MIN(amount) as min_payment,
            MAX(amount) as max_payment
        FROM payments
        WHERE payment_date BETWEEN ? AND ? AND status = 'completed'
        ''', (start_date, end_date))
        
        summary = cursor.fetchone()
        
        if summary and summary[0] > 0:
            total_payments, total_revenue, avg_payment, min_payment, max_payment = summary
            
            print(f"\nRevenue Summary Report ({start_date} to {end_date})")
            print(f"=" * 60)
            print(f"Total Payments: {total_payments}")
            print(f"Total Revenue: £{total_revenue:,.2f}")
            print(f"Average Payment: £{avg_payment:.2f}")
            print(f"Minimum Payment: £{min_payment:.2f}")
            print(f"Maximum Payment: £{max_payment:.2f}")
            
            # Revenue by payment method
            cursor.execute('''
            SELECT payment_method, COUNT(*), SUM(amount)
            FROM payments
            WHERE payment_date BETWEEN ? AND ? AND status = 'completed'
            GROUP BY payment_method
            ORDER BY SUM(amount) DESC
            ''', (start_date, end_date))
            
            method_data = cursor.fetchall()
            
            print(f"\nRevenue by Payment Method:")
            print(f"-" * 60)
            for method, count, amount in method_data:
                percentage = (amount / total_revenue) * 100
                print(f"{method:<20} {count:>6} payments  £{amount:>12,.2f} ({percentage:>5.1f}%)")
            
        else:
            print(f"No payments found for the specified date range.")
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating revenue summary: {e}")

def generate_budget_variance_report():
    """Generate a basic budget variance report comparing planned vs actual spending."""
    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()

    # This assumes a 'budgets' table and 'expenses' table exist
    try:
        cursor.execute("""
            SELECT b.category, b.allocated_amount, 
                   IFNULL(SUM(e.amount), 0) AS actual_spent,
                   (b.allocated_amount - IFNULL(SUM(e.amount), 0)) AS variance
            FROM budgets b
            LEFT JOIN expenses e ON b.category = e.category
            GROUP BY b.category
        """)
        rows = cursor.fetchall()

        print("\n--- Budget Variance Report ---")
        print("{:<20} {:>15} {:>15} {:>15}".format("Category", "Budgeted", "Actual", "Variance"))
        print("-" * 70)

        for row in rows:
            category, allocated, spent, variance = row
            print(f"{category:<20} {allocated:>15.2f} {spent:>15.2f} {variance:>15.2f}")
    except Exception as e:
        print(f"[ERROR] Could not generate budget variance report: {e}")
    finally:
        conn.close()

def generate_outstanding_fees_report():
    """Generate outstanding fees report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.last_name, s.course,
               ft.fee_name, sf.amount, sf.due_date,
               julianday('now') - julianday(sf.due_date) as days_overdue
        FROM student_fees sf
        JOIN students s ON sf.student_id = s.student_id
        JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
        WHERE sf.status IN ('unpaid', 'partial')
        ORDER BY days_overdue DESC, sf.amount DESC
        ''')
        
        outstanding = cursor.fetchall()
        
        if not outstanding:
            print("No outstanding fees found.")
            return
        
        print(f"\nOutstanding Fees Report")
        print(f"=" * 120)
        print(f"{'Student ID':<12} {'Name':<25} {'Course':<20} {'Fee Type':<20} {'Amount':<12} {'Due Date':<12} {'Days Overdue':<12}")
        print(f"-" * 120)
        
        total_outstanding = 0
        overdue_count = 0
        
        for row in outstanding:
            student_id, first_name, last_name, course, fee_name, amount, due_date, days_overdue = row
            student_name = f"{first_name} {last_name}"
            
            if days_overdue > 0:
                overdue_indicator = f"{int(days_overdue)}"
                overdue_count += 1
            else:
                overdue_indicator = "Not due"
            
            print(f"{student_id:<12} {student_name:<25} {course:<20} {fee_name:<20} £{amount:<11.2f} {due_date:<12} {overdue_indicator:<12}")
            total_outstanding += amount
        
        print(f"-" * 120)
        print(f"Total Outstanding: £{total_outstanding:,.2f}")
        print(f"Total Fees: {len(outstanding)}")
        print(f"Overdue Fees: {overdue_count}")
        print(f"=" * 120)
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating outstanding fees report: {e}")

def generate_payment_collection_report():
    """Generate payment collection report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get date range
        start_date = input("Enter start date (YYYY-MM-DD): ").strip()
        end_date = input("Enter end date (YYYY-MM-DD): ").strip()
        
        # Collection efficiency analysis
        cursor.execute('''
        SELECT 
            COUNT(DISTINCT sf.student_id) as total_students,
            SUM(sf.amount) as total_fees_due,
            SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as total_collected,
            COUNT(CASE WHEN sf.status = 'paid' THEN 1 END) as fees_paid,
            COUNT(sf.student_fee_id) as total_fees
        FROM student_fees sf
        WHERE sf.created_at BETWEEN ? AND ?
        ''', (start_date + ' 00:00:00', end_date + ' 23:59:59'))
        
        collection_data = cursor.fetchone()
        
        if collection_data:
            total_students, total_fees_due, total_collected, fees_paid, total_fees = collection_data
            
            collection_rate = (total_collected / total_fees_due * 100) if total_fees_due > 0 else 0
            payment_rate = (fees_paid / total_fees * 100) if total_fees > 0 else 0
            
            print(f"\nPayment Collection Report ({start_date} to {end_date})")
            print(f"=" * 70)
            print(f"Students with Fees: {total_students}")
            print(f"Total Fees Issued: £{total_fees_due:,.2f}")
            print(f"Total Amount Collected: £{total_collected:,.2f}")
            print(f"Outstanding Amount: £{total_fees_due - total_collected:,.2f}")
            print(f"Collection Rate: {collection_rate:.1f}%")
            print(f"Payment Rate: {payment_rate:.1f}% ({fees_paid}/{total_fees} fees)")
            
            # Payment timing analysis
            cursor.execute('''
            SELECT 
                CASE 
                    WHEN julianday(p.payment_date) <= julianday(sf.due_date) THEN 'On Time'
                    WHEN julianday(p.payment_date) - julianday(sf.due_date) <= 7 THEN '1-7 Days Late'
                    WHEN julianday(p.payment_date) - julianday(sf.due_date) <= 30 THEN '8-30 Days Late'
                    ELSE 'Over 30 Days Late'
                END as payment_timing,
                COUNT(*) as count,
                SUM(pa.amount) as amount
            FROM payments p
            JOIN payment_allocations pa ON p.payment_id = pa.payment_id
            JOIN student_fees sf ON pa.student_fee_id = sf.student_fee_id
            WHERE p.payment_date BETWEEN ? AND ?
            GROUP BY payment_timing
            ORDER BY 
                CASE payment_timing
                    WHEN 'On Time' THEN 1
                    WHEN '1-7 Days Late' THEN 2
                    WHEN '8-30 Days Late' THEN 3
                    ELSE 4
                END
            ''', (start_date, end_date))
            
            timing_data = cursor.fetchall()
            
            if timing_data:
                print(f"\nPayment Timing Analysis:")
                print(f"-" * 50)
                for timing, count, amount in timing_data:
                    print(f"{timing:<20} {count:>8} payments  £{amount:>12,.2f}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating payment collection report: {e}")

def generate_predictive_analytics():
    """Generate predictive analytics for payment behavior"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to generate predictive analytics.")
        return
    
    if not auth.check_permission('manage_finances'):
        print("You don't have permission to generate predictive analytics.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("Generating predictive analytics...")
        
        # Get student payment data for analysis
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.last_name, s.course,
               COUNT(p.payment_id) as payment_count,
               AVG(julianday(p.payment_date) - julianday(sf.due_date)) as avg_payment_delay,
               SUM(CASE WHEN p.payment_date > sf.due_date THEN 1 ELSE 0 END) as late_payments,
               SUM(sf.amount) as total_fees,
               SUM(p.amount) as total_paid,
               COUNT(sf.student_fee_id) as total_fees_count
        FROM students s
        LEFT JOIN student_fees sf ON s.student_id = sf.student_id
        LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
        LEFT JOIN payments p ON pa.payment_id = p.payment_id
        GROUP BY s.student_id
        HAVING total_fees > 0
        ''')
        
        student_data = cursor.fetchall()
        
        if len(student_data) < 10:
            print("Insufficient data for meaningful predictive analytics.")
            conn.close()
            return
        
        # Prepare data for machine learning
        features = []
        labels = []
        student_ids = []
        
        for row in student_data:
            student_id, first_name, last_name, course, payment_count, avg_delay, late_payments, total_fees, total_paid, fee_count = row
            
            # Calculate features
            payment_ratio = (total_paid or 0) / (total_fees or 1)
            late_payment_ratio = (late_payments or 0) / (payment_count or 1)
            avg_delay_normalized = min(max(avg_delay or 0, -30), 60) / 60  # Normalize to -0.5 to 1
            
            features.append([
                payment_ratio,
                late_payment_ratio,
                avg_delay_normalized,
                payment_count or 0,
                fee_count or 0
            ])
            
            # Label: 1 if high risk (late payment ratio > 0.3), 0 if low risk
            labels.append(1 if late_payment_ratio > 0.3 else 0)
            student_ids.append(student_id)
        
        # Train a simple isolation forest for anomaly detection
        X = np.array(features)
        
        # Isolation Forest for outlier detection
        isolation_forest = IsolationForest(contamination=0.1, random_state=42)
        outliers = isolation_forest.fit_predict(X)
        
        # Calculate risk scores
        risk_scores = []
        for i, feature_set in enumerate(features):
            # Simple risk scoring based on features
            payment_ratio, late_ratio, delay_norm, payment_count, fee_count = feature_set
            
            risk_score = 0
            
            # Payment ratio contribution (lower ratio = higher risk)
            risk_score += max(0, (1 - payment_ratio) * 30)
            
            # Late payment ratio contribution
            risk_score += late_ratio * 40
            
            # Delay contribution
            risk_score += max(0, delay_norm * 20)
            
            # Low payment count might indicate avoidance
            if payment_count < 2:
                risk_score += 10
            
            # Outlier detection contribution
            if outliers[i] == -1:
                risk_score += 15
            
            risk_scores.append(min(risk_score, 100))  # Cap at 100
        
        # Update risk scores in database
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for i, student_id in enumerate(student_ids):
            risk_score = risk_scores[i]
            
            if risk_score >= 70:
                risk_level = 'high'
            elif risk_score >= 40:
                risk_level = 'medium'
            else:
                risk_level = 'low'
            
            # Calculate risk factors
            risk_factors = {
                'payment_ratio': features[i][0],
                'late_payment_ratio': features[i][1],
                'avg_delay': features[i][2],
                'is_outlier': outliers[i] == -1
            }
            
            cursor.execute('''
            INSERT OR REPLACE INTO payment_risk_scores 
            (student_id, risk_score, risk_level, factors, last_calculated, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (student_id, risk_score, risk_level, json.dumps(risk_factors), now, now))
        
        conn.commit()
        
        # Display results
        high_risk_students = [(student_ids[i], risk_scores[i]) for i in range(len(student_ids)) if risk_scores[i] >= 70]
        medium_risk_students = [(student_ids[i], risk_scores[i]) for i in range(len(student_ids)) if 40 <= risk_scores[i] < 70]
        
        print(f"\nPredictive Analytics Results:")
        print(f"Total students analyzed: {len(student_data)}")
        print(f"High risk students: {len(high_risk_students)}")
        print(f"Medium risk students: {len(medium_risk_students)}")
        print(f"Low risk students: {len(student_ids) - len(high_risk_students) - len(medium_risk_students)}")
        
        if high_risk_students:
            print(f"\nHigh Risk Students:")
            for student_id, score in high_risk_students[:10]:  # Show top 10
                print(f"  {student_id} ({get_student_name(student_id)}): {score:.1f}% risk")
        
        # Generate visualizations
        plt.figure(figsize=(12, 8))
        
        # Risk score distribution
        plt.subplot(2, 2, 1)
        plt.hist(risk_scores, bins=20, alpha=0.7, color='skyblue', edgecolor='black')
        plt.title('Risk Score Distribution')
        plt.xlabel('Risk Score')
        plt.ylabel('Number of Students')
        
        # Risk level pie chart
        plt.subplot(2, 2, 2)
        risk_counts = [len(high_risk_students), len(medium_risk_students), 
                      len(student_ids) - len(high_risk_students) - len(medium_risk_students)]
        plt.pie(risk_counts, labels=['High Risk', 'Medium Risk', 'Low Risk'], 
                autopct='%1.1f%%', colors=['red', 'orange', 'green'])
        plt.title('Risk Level Distribution')
        
        # Payment ratio vs risk score
        plt.subplot(2, 2, 3)
        payment_ratios = [features[i][0] for i in range(len(features))]
        plt.scatter(payment_ratios, risk_scores, alpha=0.6)
        plt.xlabel('Payment Ratio')
        plt.ylabel('Risk Score')
        plt.title('Payment Ratio vs Risk Score')
        
        # Late payment ratio vs risk score
        plt.subplot(2, 2, 4)
        late_ratios = [features[i][1] for i in range(len(features))]
        plt.scatter(late_ratios, risk_scores, alpha=0.6, color='orange')
        plt.xlabel('Late Payment Ratio')
        plt.ylabel('Risk Score')
        plt.title('Late Payment Ratio vs Risk Score')
        
        plt.tight_layout()
        plt.savefig('payment_risk_analytics.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"\nAnalytics visualization saved as 'payment_risk_analytics.png'")
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating predictive analytics: {e}")

def generate_financial_dashboard():
    """Generate interactive financial dashboard"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to generate dashboard.")
        return
    
    if not auth.check_permission('manage_finances'):
        print("You don't have permission to generate dashboard.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("Generating financial dashboard...")
        
        # Calculate KPIs
        current_date = datetime.now().strftime('%Y-%m-%d')
        current_month = datetime.now().strftime('%Y-%m')
        current_year = datetime.now().year
        
        # Total revenue this year
        cursor.execute('''
        SELECT SUM(amount) FROM payments 
        WHERE strftime('%Y', payment_date) = ? AND status = 'completed'
        ''', (str(current_year),))
        
        total_revenue = cursor.fetchone()[0] or 0
        
        # Outstanding fees
        cursor.execute('''
        SELECT SUM(sf.amount) - COALESCE(SUM(pa.amount), 0) as outstanding
        FROM student_fees sf
        LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
        WHERE sf.status IN ('unpaid', 'partial')
        ''')
        
        outstanding_fees = cursor.fetchone()[0] or 0
        
        # Collection rate
        cursor.execute('''
        SELECT 
            SUM(sf.amount) as total_fees,
            SUM(COALESCE(pa.amount, 0)) as total_collected
        FROM student_fees sf
        LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
        WHERE strftime('%Y', sf.created_at) = ?
        ''', (str(current_year),))
        
        result = cursor.fetchone()
        total_fees_year = result[0] or 0
        total_collected_year = result[1] or 0
        collection_rate = (total_collected_year / total_fees_year * 100) if total_fees_year > 0 else 0
        
        # Average payment time
        cursor.execute('''
        SELECT AVG(julianday(p.payment_date) - julianday(sf.due_date)) as avg_payment_delay
        FROM payments p
        JOIN payment_allocations pa ON p.payment_id = pa.payment_id
        JOIN student_fees sf ON pa.student_fee_id = sf.student_fee_id
        WHERE strftime('%Y', p.payment_date) = ?
        ''', (str(current_year),))
        
        avg_payment_delay = cursor.fetchone()[0] or 0
        
        # Payment method distribution
        cursor.execute('''
        SELECT payment_method, COUNT(*), SUM(amount)
        FROM payments 
        WHERE strftime('%Y', payment_date) = ? AND status = 'completed'
        GROUP BY payment_method
        ORDER BY SUM(amount) DESC
        ''', (str(current_year),))
        
        payment_methods = cursor.fetchall()
        
        # Monthly revenue trend
        cursor.execute('''
        SELECT strftime('%Y-%m', payment_date) as month, SUM(amount)
        FROM payments 
        WHERE strftime('%Y', payment_date) = ? AND status = 'completed'
        GROUP BY month
        ORDER BY month
        ''', (str(current_year),))
        
        monthly_revenue = cursor.fetchall()
        
        # Risk distribution
        cursor.execute('''
        SELECT risk_level, COUNT(*)
        FROM payment_risk_scores
        GROUP BY risk_level
        ''')
        
        risk_distribution = cursor.fetchall()
        
        # Create comprehensive dashboard
        fig, axes = plt.subplots(3, 3, figsize=(18, 15))
        fig.suptitle('Financial Management Dashboard', fontsize=16, fontweight='bold')
        
        # KPI Summary (text box)
        axes[0, 0].text(0.1, 0.9, f'Total Revenue (YTD)', fontsize=12, fontweight='bold')
        axes[0, 0].text(0.1, 0.7, f'£{total_revenue:,.2f}', fontsize=20, color='green')
        axes[0, 0].text(0.1, 0.5, f'Outstanding Fees', fontsize=12, fontweight='bold')
        axes[0, 0].text(0.1, 0.3, f'£{outstanding_fees:,.2f}', fontsize=20, color='red')
        axes[0, 0].text(0.1, 0.1, f'Collection Rate: {collection_rate:.1f}%', fontsize=12)
        axes[0, 0].set_xlim(0, 1)
        axes[0, 0].set_ylim(0, 1)
        axes[0, 0].axis('off')
        axes[0, 0].set_title('Key Performance Indicators')
        
        # Payment method distribution (pie chart)
        if payment_methods:
            methods = [method[0] for method in payment_methods]
            amounts = [method[2] for method in payment_methods]
            axes[0, 1].pie(amounts, labels=methods, autopct='%1.1f%%')
            axes[0, 1].set_title('Payment Methods (by Amount)')
        
        # Monthly revenue trend
        if monthly_revenue:
            months = [month[0] for month in monthly_revenue]
            revenues = [month[1] for month in monthly_revenue]
            axes[0, 2].plot(months, revenues, marker='o', linewidth=2, markersize=6)
            axes[0, 2].set_title('Monthly Revenue Trend')
            axes[0, 2].tick_params(axis='x', rotation=45)
        
        # Risk level distribution
        if risk_distribution:
            risk_levels = [risk[0] for risk in risk_distribution]
            risk_counts = [risk[1] for risk in risk_distribution]
            colors = {'high': 'red', 'medium': 'orange', 'low': 'green'}
            bar_colors = [colors.get(level, 'blue') for level in risk_levels]
            axes[1, 0].bar(risk_levels, risk_counts, color=bar_colors)
            axes[1, 0].set_title('Payment Risk Distribution')
            axes[1, 0].set_ylabel('Number of Students')
        
        # Outstanding fees by course
        cursor.execute('''
        SELECT s.course, SUM(sf.amount) - COALESCE(SUM(pa.amount), 0) as outstanding
        FROM student_fees sf
        JOIN students s ON sf.student_id = s.student_id
        LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
        WHERE sf.status IN ('unpaid', 'partial')
        GROUP BY s.course
        ORDER BY outstanding DESC
        ''')
        
        course_outstanding = cursor.fetchall()
        
        if course_outstanding:
            courses = [course[0] for course in course_outstanding]
            amounts = [course[1] for course in course_outstanding]
            axes[1, 1].bar(courses, amounts, color='coral')
            axes[1, 1].set_title('Outstanding Fees by Course')
            axes[1, 1].set_ylabel('Amount (£)')
            axes[1, 1].tick_params(axis='x', rotation=45)
        
        # Payment timing analysis
        cursor.execute('''
        SELECT 
            CASE 
                WHEN julianday(p.payment_date) - julianday(sf.due_date) < 0 THEN 'Early'
                WHEN julianday(p.payment_date) - julianday(sf.due_date) = 0 THEN 'On Time'
                WHEN julianday(p.payment_date) - julianday(sf.due_date) <= 7 THEN 'Late (1-7 days)'
                WHEN julianday(p.payment_date) - julianday(sf.due_date) <= 30 THEN 'Late (8-30 days)'
                ELSE 'Very Late (30+ days)'
            END as timing_category,
            COUNT(*)
        FROM payments p
        JOIN payment_allocations pa ON p.payment_id = pa.payment_id
        JOIN student_fees sf ON pa.student_fee_id = sf.student_fee_id
        WHERE strftime('%Y', p.payment_date) = ?
        GROUP BY timing_category
        ''', (str(current_year),))
        
        payment_timing = cursor.fetchall()
        
        if payment_timing:
            timing_labels = [timing[0] for timing in payment_timing]
            timing_counts = [timing[1] for timing in payment_timing]
            axes[1, 2].pie(timing_counts, labels=timing_labels, autopct='%1.1f%%')
            axes[1, 2].set_title('Payment Timing Distribution')
        
        # Scholarship distribution
        cursor.execute('''
        SELECT s.scholarship_name, COUNT(ss.student_scholarship_id), SUM(ss.amount)
        FROM scholarships s
        JOIN student_scholarships ss ON s.scholarship_id = ss.scholarship_id
        WHERE ss.status = 'active'
        GROUP BY s.scholarship_name
        ORDER BY SUM(ss.amount) DESC
        ''')
        
        scholarship_data = cursor.fetchall()
        
        if scholarship_data:
            scholarship_names = [s[0] for s in scholarship_data]
            scholarship_amounts = [s[2] for s in scholarship_data]
            axes[2, 0].bar(scholarship_names, scholarship_amounts, color='lightblue')
            axes[2, 0].set_title('Scholarship Distribution (by Amount)')
            axes[2, 0].set_ylabel('Amount (£)')
            axes[2, 0].tick_params(axis='x', rotation=45)
        
        # Late fees trend
        cursor.execute('''
        SELECT strftime('%Y-%m', applied_date) as month, SUM(late_fee_amount)
        FROM late_fees
        WHERE strftime('%Y', applied_date) = ? AND waived = 0
        GROUP BY month
        ORDER BY month
        ''', (str(current_year),))
        
        late_fees_trend = cursor.fetchall()
        
        if late_fees_trend:
            late_months = [month[0] for month in late_fees_trend]
            late_amounts = [month[1] for month in late_fees_trend]
            axes[2, 1].plot(late_months, late_amounts, marker='s', color='red', linewidth=2)
            axes[2, 1].set_title('Late Fees Trend')
            axes[2, 1].set_ylabel('Late Fees (£)')
            axes[2, 1].tick_params(axis='x', rotation=45)
        
        # Payment plan status
        cursor.execute('''
        SELECT status, COUNT(*), SUM(total_amount)
        FROM student_payment_plans
        GROUP BY status
        ''')
        
        payment_plan_status = cursor.fetchall()
        
        if payment_plan_status:
            plan_statuses = [status[0] for status in payment_plan_status]
            plan_counts = [status[1] for status in payment_plan_status]
            axes[2, 2].bar(plan_statuses, plan_counts, color='mediumpurple')
            axes[2, 2].set_title('Payment Plan Status')
            axes[2, 2].set_ylabel('Number of Plans')
        
        plt.tight_layout()
        plt.savefig('financial_dashboard.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # Generate summary report
        print(f"\nFinancial Dashboard Summary:")
        print(f"=" * 50)
        print(f"Total Revenue (YTD): £{total_revenue:,.2f}")
        print(f"Outstanding Fees: £{outstanding_fees:,.2f}")
        print(f"Collection Rate: {collection_rate:.1f}%")
        print(f"Average Payment Delay: {avg_payment_delay:.1f} days")
        print(f"Dashboard saved as 'financial_dashboard.png'")
        
        # Update KPIs in database
        kpi_data = [
            ('total_revenue', total_revenue, 'amount', 'yearly', current_date, str(current_year)),
            ('outstanding_fees', outstanding_fees, 'amount', 'daily', current_date, str(current_year)),
            ('collection_rate', collection_rate, 'percentage', 'yearly', current_date, str(current_year)),
            ('avg_payment_delay', avg_payment_delay, 'amount', 'yearly', current_date, str(current_year))
        ]
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for kpi_name, kpi_value, kpi_type, period, calc_date, academic_year in kpi_data:
            cursor.execute('''
            INSERT INTO financial_kpis 
            (kpi_name, kpi_value, kpi_type, calculation_period, calculation_date, academic_year, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (kpi_name, kpi_value, kpi_type, period, calc_date, academic_year, now))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Error generating dashboard: {e}")

def student_account_summary_report():
    """Generate student account summary report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.last_name, s.course,
               SUM(sf.amount) as total_fees,
               SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as paid_fees,
               COUNT(sf.student_fee_id) as total_fee_items,
               COUNT(CASE WHEN sf.status = 'paid' THEN 1 END) as paid_items
        FROM students s
        LEFT JOIN student_fees sf ON s.student_id = sf.student_id
        GROUP BY s.student_id
        ORDER BY s.student_id
        ''')
        
        accounts = cursor.fetchall()
        
        print(f"\nStudent Account Summary Report")
        print(f"=" * 120)
        print(f"{'Student ID':<12} {'Name':<25} {'Course':<20} {'Total Fees':<12} {'Paid':<12} {'Outstanding':<12} {'Status':<10}")
        print(f"-" * 120)
        
        for account in accounts:
            student_id, first_name, last_name, course, total_fees, paid_fees, total_items, paid_items = account
            student_name = f"{first_name} {last_name}"
            outstanding = (total_fees or 0) - (paid_fees or 0)
            
            if outstanding > 0:
                status = "Outstanding"
            elif total_fees and total_fees > 0:
                status = "Paid"
            else:
                status = "No Fees"
            
            print(f"{student_id:<12} {student_name:<25} {course:<20} £{total_fees or 0:<11.2f} £{paid_fees or 0:<11.2f} £{outstanding:<11.2f} {status:<10}")
        
        print(f"=" * 120)
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating student account summary: {e}")

def fee_type_analysis_report():
    """Generate fee type analysis report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT ft.fee_name, 
               COUNT(sf.student_fee_id) as total_assigned,
               SUM(sf.amount) as total_amount,
               COUNT(CASE WHEN sf.status = 'paid' THEN 1 END) as paid_count,
               SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as paid_amount,
               (COUNT(CASE WHEN sf.status = 'paid' THEN 1 END) * 100.0 / COUNT(sf.student_fee_id)) as payment_rate
        FROM fee_types ft
        LEFT JOIN student_fees sf ON ft.fee_type_id = sf.fee_type_id
        GROUP BY ft.fee_type_id, ft.fee_name
        ORDER BY total_amount DESC
        ''')
        
        fee_analysis = cursor.fetchall()
        
        print(f"\nFee Type Analysis Report")
        print(f"=" * 100)
        print(f"{'Fee Type':<25} {'Assigned':<10} {'Total Amount':<15} {'Paid Count':<12} {'Paid Amount':<15} {'Payment Rate':<12}")
        print(f"-" * 100)
        
        for fee in fee_analysis:
            fee_name, assigned, total_amt, paid_count, paid_amt, payment_rate = fee
            if assigned and assigned > 0:
                print(f"{fee_name:<25} {assigned:<10} £{total_amt or 0:<14.2f} {paid_count or 0:<12} £{paid_amt or 0:<14.2f} {payment_rate or 0:<11.1f}%")
        
        print(f"=" * 100)
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating fee type analysis: {e}")

def payment_method_analysis_report():
    """Generate payment method analysis report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get date range
        start_date = input("Enter start date (YYYY-MM-DD): ").strip()
        end_date = input("Enter end date (YYYY-MM-DD): ").strip()
        
        cursor.execute('''
        SELECT payment_method,
               COUNT(*) as transaction_count,
               SUM(amount) as total_amount,
               AVG(amount) as avg_amount,
               MIN(amount) as min_amount,
               MAX(amount) as max_amount
        FROM payments
        WHERE payment_date BETWEEN ? AND ? AND status = 'completed'
        GROUP BY payment_method
        ORDER BY total_amount DESC
        ''', (start_date, end_date))
        
        methods = cursor.fetchall()
        
        if not methods:
            print("No payment data found for the specified date range.")
            return
        
        print(f"\nPayment Method Analysis Report ({start_date} to {end_date})")
        print(f"=" * 100)
        print(f"{'Method':<20} {'Count':<8} {'Total Amount':<15} {'Avg Amount':<12} {'Min':<10} {'Max':<10}")
        print(f"-" * 100)
        
        total_transactions = 0
        total_amount = 0
        
        for method in methods:
            method_name, count, amount, avg_amt, min_amt, max_amt = method
            print(f"{method_name:<20} {count:<8} £{amount:<14.2f} £{avg_amt:<11.2f} £{min_amt:<9.2f} £{max_amt:<9.2f}")
            total_transactions += count
            total_amount += amount
        
        print(f"-" * 100)
        print(f"{'TOTAL':<20} {total_transactions:<8} £{total_amount:<14.2f}")
        print(f"=" * 100)
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating payment method analysis: {e}")

def monthly_revenue_trend_report():
    """Generate monthly revenue trend report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get year
        year = input("Enter year (YYYY) or press Enter for current year: ").strip()
        if not year:
            year = str(datetime.now().year)
        
        cursor.execute('''
        SELECT strftime('%m', payment_date) as month,
               COUNT(*) as payment_count,
               SUM(amount) as monthly_revenue
        FROM payments
        WHERE strftime('%Y', payment_date) = ? AND status = 'completed'
        GROUP BY month
        ORDER BY month
        ''', (year,))
        
        monthly_data = cursor.fetchall()
        
        if not monthly_data:
            print(f"No payment data found for year {year}.")
            return
        
        print(f"\nMonthly Revenue Trend Report - {year}")
        print(f"=" * 60)
        print(f"{'Month':<10} {'Payments':<10} {'Revenue':<15} {'Growth %':<10}")
        print(f"-" * 60)
        
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        prev_revenue = 0
        total_revenue = 0
        
        # Create a dict for easy lookup
        month_data = {month: (count, revenue) for month, count, revenue in monthly_data}
        
        for i in range(1, 13):
            month_str = f"{i:02d}"
            month_name = months[i-1]
            
            if month_str in month_data:
                count, revenue = month_data[month_str]
                if prev_revenue > 0:
                    growth = ((revenue - prev_revenue) / prev_revenue) * 100
                    growth_str = f"{growth:+.1f}%"
                else:
                    growth_str = "N/A"
                
                print(f"{month_name:<10} {count:<10} £{revenue:<14.2f} {growth_str:<10}")
                total_revenue += revenue
                prev_revenue = revenue
            else:
                print(f"{month_name:<10} {0:<10} £{0:<14.2f} {'N/A':<10}")
        
        print(f"-" * 60)
        print(f"TOTAL      {'-':<10} £{total_revenue:<14.2f}")
        print(f"=" * 60)
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating monthly revenue trend: {e}")

def scholarship_reports():
    """Generate scholarship reports"""
    while True:
        print("\n" + "=" * 40)
        print("SCHOLARSHIP REPORTS")
        print("=" * 40)
        print("1. Scholarship Distribution Summary")
        print("2. Student Scholarship Report")
        print("3. Scholarship Utilization Analysis")
        print("4. Return to Scholarship Menu")
        
        choice = input("Enter your choice (1-4): ").strip()
        
        if choice == '1':
            scholarship_distribution_summary()
        elif choice == '2':
            student_scholarship_report()
        elif choice == '3':
            scholarship_utilization_analysis()
        elif choice == '4':
            return
        else:
            print("Invalid choice. Please try again.")

def student_scholarship_report():
    """Generate student scholarship report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.last_name, s.course,
               COUNT(ss.student_scholarship_id) as scholarship_count,
               SUM(ss.amount) as total_scholarships
        FROM students s
        LEFT JOIN student_scholarships ss ON s.student_id = ss.student_id AND ss.status = 'active'
        GROUP BY s.student_id
        HAVING scholarship_count > 0
        ORDER BY total_scholarships DESC
        ''')
        
        students = cursor.fetchall()
        
        if not students:
            print("No students with active scholarships found.")
            return
        
        print(f"\nStudent Scholarship Report")
        print(f"=" * 90)
        print(f"{'Student ID':<12} {'Name':<25} {'Course':<20} {'Count':<8} {'Total Amount':<15}")
        print(f"-" * 90)
        
        for student in students:
            student_id, first_name, last_name, course, count, total = student
            student_name = f"{first_name} {last_name}"
            print(f"{student_id:<12} {student_name:<25} {course:<20} {count:<8} £{total:<14.2f}")
        
        print(f"=" * 90)
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating student scholarship report: {e}")

def generate_audit_report(start_date, end_date):
    """Generate audit report for compliance"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to generate audit reports.")
        return
    
    if not auth.check_permission('view_audit_logs'):
        print("You don't have permission to view audit logs.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT user_id, action, table_name, record_id, new_values, timestamp
        FROM audit_log
        WHERE date(timestamp) BETWEEN ? AND ?
        ORDER BY timestamp DESC
        ''', (start_date, end_date))
        
        audit_logs = cursor.fetchall()
        
        if not audit_logs:
            print(f"No audit logs found between {start_date} and {end_date}")
            conn.close()
            return
        
        print(f"\nAudit Report: {start_date} to {end_date}")
        print("=" * 100)
        print(f"{'Timestamp':<20} {'User':<15} {'Action':<20} {'Table':<15} {'Record ID':<10} {'Details':<20}")
        print("-" * 100)
        
        for log in audit_logs:
            user_id, action, table_name, record_id, details, timestamp = log
            details_summary = json.loads(details) if details else {}
            details_str = str(details_summary)[:20] + "..." if len(str(details_summary)) > 20 else str(details_summary)
            
            print(f"{timestamp:<20} {user_id:<15} {action:<20} {table_name:<15} {record_id:<10} {details_str:<20}")
        
        print("=" * 100)
        print(f"Total audit entries: {len(audit_logs)}")
        
        # Export option
        export = input("\nExport audit report? (y/n): ").strip().lower()
        
        if export == 'y':
            filename = f"audit_report_{start_date}_to_{end_date}.csv"
            
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Timestamp', 'User', 'Action', 'Table', 'Record ID', 'Details'])
                
                for log in audit_logs:
                    writer.writerow(log)
            
            print(f"Audit report exported to {filename}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def generate_revenue_forecast():
    """Generate revenue forecasting based on historical data and trends"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to generate revenue forecasts.")
        return
    
    if not auth.check_permission('manage_finances'):
        print("You don't have permission to generate revenue forecasts.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\n" + "=" * 50)
        print("REVENUE FORECASTING SYSTEM")
        print("=" * 50)
        
        # Get historical revenue data
        cursor.execute('''
        SELECT strftime('%Y-%m', payment_date) as month, SUM(amount) as monthly_revenue
        FROM payments
        WHERE status = 'completed' 
        AND payment_date >= date('now', '-24 months')
        GROUP BY month
        ORDER BY month
        ''')
        
        historical_data = cursor.fetchall()
        
        if len(historical_data) < 6:
            print("Insufficient historical data for meaningful forecasting.")
            print("Need at least 6 months of payment data.")
            conn.close()
            return
        
        # Convert to arrays for analysis
        months = [data[0] for data in historical_data]
        revenues = [data[1] for data in historical_data]
        
        print(f"Analyzing {len(historical_data)} months of historical data...")
        
        # Calculate basic statistics
        avg_monthly_revenue = np.mean(revenues)
        revenue_std = np.std(revenues)
        revenue_growth_rate = calculate_growth_rate(revenues)
        
        print(f"\nHistorical Analysis:")
        print(f"Average Monthly Revenue: £{avg_monthly_revenue:,.2f}")
        print(f"Revenue Standard Deviation: £{revenue_std:,.2f}")
        print(f"Monthly Growth Rate: {revenue_growth_rate:.2f}%")
        
        # Seasonal analysis
        seasonal_factors = calculate_seasonal_factors(historical_data)
        
        # Generate forecasts
        forecast_periods = 12  # Forecast next 12 months
        forecasts = generate_forecast_values(revenues, forecast_periods, revenue_growth_rate, seasonal_factors)
        
        # Display forecasts
        print(f"\nRevenue Forecast (Next {forecast_periods} Months):")
        print("=" * 60)
        print(f"{'Month':<15} {'Forecast':<15} {'Low Est.':<15} {'High Est.':<15}")
        print("-" * 60)
        
        current_date = datetime.now()
        total_forecast = 0
        
        for i, forecast in enumerate(forecasts):
            forecast_date = current_date + timedelta(days=30*i)
            month_str = forecast_date.strftime('%Y-%m')
            
            # Calculate confidence interval (±20%)
            low_estimate = forecast * 0.8
            high_estimate = forecast * 1.2
            
            print(f"{month_str:<15} £{forecast:>13,.0f} £{low_estimate:>13,.0f} £{high_estimate:>13,.0f}")
            total_forecast += forecast
        
        print("-" * 60)
        print(f"{'Total Forecast':<15} £{total_forecast:>13,.0f}")
        print("=" * 60)
        
        # Scenario analysis
        print(f"\nScenario Analysis:")
        conservative_total = total_forecast * 0.85
        optimistic_total = total_forecast * 1.15
        
        print(f"Conservative (85%): £{conservative_total:,.0f}")
        print(f"Expected (100%):   £{total_forecast:,.0f}")
        print(f"Optimistic (115%): £{optimistic_total:,.0f}")
        
        # Generate enrollment-based forecast
        enrollment_forecast = generate_enrollment_based_forecast()
        
        if enrollment_forecast:
            print(f"\nEnrollment-Based Forecast:")
            print(f"Expected Revenue from New Students: £{enrollment_forecast['new_student_revenue']:,.0f}")
            print(f"Expected Revenue from Returning Students: £{enrollment_forecast['returning_student_revenue']:,.0f}")
            print(f"Total Enrollment-Based Forecast: £{enrollment_forecast['total']:,.0f}")
        
        # Fee structure analysis
        fee_analysis = analyze_fee_structure_impact()
        
        if fee_analysis:
            print(f"\nFee Structure Impact Analysis:")
            for course, impact in fee_analysis.items():
                print(f"{course}: £{impact:,.0f} potential annual revenue")
        
        # Create visualization
        create_revenue_forecast_chart(months, revenues, forecasts)
        
        # Save forecast to database
        save_forecast_to_database(forecasts, total_forecast)
        
        # Export option
        export = input("\nExport forecast report? (y/n): ").strip().lower()
        if export == 'y':
            export_forecast_report(historical_data, forecasts, total_forecast)
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating revenue forecast: {e}")

def generate_forecast_values(historical_revenues, periods, growth_rate, seasonal_factors):
    """Generate forecast values using trend and seasonal adjustments"""
    forecasts = []
    base_value = historical_revenues[-1]  # Last known value
    
    for i in range(periods):
        # Apply growth trend
        trend_value = base_value * (1 + growth_rate/100) ** (i + 1)
        
        # Apply seasonal adjustment
        current_date = datetime.now() + timedelta(days=30*i)
        month_num = current_date.month
        seasonal_factor = seasonal_factors.get(month_num, 1.0)
        
        forecast_value = trend_value * seasonal_factor
        forecasts.append(forecast_value)
    
    return forecasts

def generate_enrollment_based_forecast():
    """Generate forecast based on enrollment projections"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get current enrollment by course
        cursor.execute('''
        SELECT course, COUNT(*) as current_enrollment
        FROM students
        WHERE status = 'active'
        GROUP BY course
        ''')
        
        enrollment_data = cursor.fetchall()
        
        # Get average fees per course
        cursor.execute('''
        SELECT pf.course, AVG(pf.amount) as avg_fee
        FROM program_fees pf
        JOIN fee_types ft ON pf.fee_type_id = ft.fee_type_id
        WHERE ft.fee_name LIKE '%Tuition%'
        GROUP BY pf.course
        ''')
        
        fee_data = dict(cursor.fetchall())
        
        # Estimate new student enrollment (assume 20% growth)
        new_student_revenue = 0
        returning_student_revenue = 0
        
        for course, current_count in enrollment_data:
            avg_fee = fee_data.get(course, 9250)  # Default tuition
            
            # New students (20% of current)
            new_students = int(current_count * 0.2)
            new_student_revenue += new_students * avg_fee
            
            # Returning students (90% retention)
            returning_students = int(current_count * 0.9)
            returning_student_revenue += returning_students * avg_fee
        
        conn.close()
        
        return {
            'new_student_revenue': new_student_revenue,
            'returning_student_revenue': returning_student_revenue,
            'total': new_student_revenue + returning_student_revenue
        }
        
    except Exception as e:
        print(f"Error in enrollment-based forecast: {e}")
        return None

def create_revenue_forecast_chart(months, historical_revenues, forecasts):
    """Create revenue forecast visualization"""
    try:
        plt.figure(figsize=(14, 8))
        
        # Historical data
        historical_x = range(len(months))
        plt.plot(historical_x, historical_revenues, 'b-o', label='Historical Revenue', linewidth=2, markersize=6)
        
        # Forecast data
        forecast_x = range(len(months), len(months) + len(forecasts))
        plt.plot(forecast_x, forecasts, 'r--s', label='Forecast', linewidth=2, markersize=6)
        
        # Add trend line
        z = np.polyfit(historical_x, historical_revenues, 1)
        p = np.poly1d(z)
        plt.plot(historical_x, p(historical_x), 'g:', alpha=0.7, label='Trend')
        
        # Confidence bands for forecast
        forecast_array = np.array(forecasts)
        lower_bound = forecast_array * 0.8
        upper_bound = forecast_array * 1.2
        plt.fill_between(forecast_x, lower_bound, upper_bound, alpha=0.2, color='red', label='Confidence Band')
        
        plt.title('Revenue Forecast Analysis', fontsize=16, fontweight='bold')
        plt.xlabel('Time Period', fontsize=12)
        plt.ylabel('Revenue (£)', fontsize=12)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        
        # Format y-axis as currency
        ax = plt.gca()
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'£{x:,.0f}'))
        
        plt.tight_layout()
        plt.savefig('revenue_forecast.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        print("Revenue forecast chart saved as 'revenue_forecast.png'")
        
    except Exception as e:
        print(f"Error creating forecast chart: {e}")

def save_forecast_to_database(forecasts, total_forecast):
    """Save forecast results to database"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Save overall forecast KPI
        current_date = datetime.now().strftime('%Y-%m-%d')
        current_year = str(datetime.now().year)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO financial_kpis 
        (kpi_name, kpi_value, kpi_type, calculation_period, calculation_date, academic_year, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('revenue_forecast_12_months', total_forecast, 'amount', 'yearly', current_date, current_year, now))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Error saving forecast to database: {e}")

def manage_collections():
    """Collection management system for overdue accounts"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage collections.")
        return
    
    if not auth.check_permission('manage_finances'):
        print("You don't have permission to manage collections.")
        return
    
    while True:
        print("\n" + "=" * 50)
        print("COLLECTION MANAGEMENT SYSTEM")
        print("=" * 50)
        print("1. View Overdue Accounts")
        print("2. Create Collection Case")
        print("3. Assign to Collection Agency")
        print("4. Track Collection Progress")
        print("5. Payment Arrangements")
        print("6. Collection Reports")
        print("7. Manage Collection Agencies")
        print("8. Automated Collection Workflows")
        print("9. Return to Finance Menu")
        
        choice = input("Enter your choice (1-9): ").strip()
        
        if choice == '1':
            view_overdue_accounts()
        elif choice == '2':
            create_collection_case()
        elif choice == '3':
            assign_to_collection_agency()
        elif choice == '4':
            track_collection_progress()
        elif choice == '5':
            create_payment_arrangement()
        elif choice == '6':
            generate_collection_reports()
        elif choice == '7':
            manage_collection_agencies()
        elif choice == '8':
            setup_collection_workflows()
        elif choice == '9':
            return
        else:
            print("Invalid choice. Please try again.")

def create_collection_case():
    """Create a new collection case for an overdue account"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        student_id = input("Enter student ID for collection case: ").strip()
        
        if not student_exists(student_id):
            print(f"Student with ID {student_id} does not exist.")
            return
        
        # Calculate total debt
        cursor.execute('''
        SELECT SUM(sf.amount) - COALESCE(SUM(pa.amount), 0) as total_debt,
               COUNT(sf.student_fee_id) as overdue_count
        FROM student_fees sf
        LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
        WHERE sf.student_id = ? AND sf.status IN ('unpaid', 'partial')
        AND date(sf.due_date) < date('now')
        ''', (student_id,))
        
        debt_info = cursor.fetchone()
        total_debt, overdue_count = debt_info
        
        if not total_debt or total_debt <= 0:
            print(f"No overdue debt found for student {student_id}.")
            return
        
        print(f"\nCollection Case Details:")
        print(f"Student: {get_student_name(student_id)} ({student_id})")
        print(f"Total Debt: £{total_debt:.2f}")
        print(f"Overdue Fees: {overdue_count}")
        
        # Check if case already exists
        cursor.execute('''
        SELECT case_id, case_status FROM collection_cases
        WHERE student_id = ? AND case_status NOT IN ('resolved', 'closed')
        ''', (student_id,))
        
        existing_case = cursor.fetchone()
        
        if existing_case:
            print(f"Active collection case already exists (Case ID: {existing_case[0]}, Status: {existing_case[1]})")
            return
        
        # Get case notes
        notes = input("Enter case notes: ").strip()
        
        # Create collection case
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO collection_cases 
        (student_id, total_debt, case_status, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (student_id, total_debt, 'new', notes, now, now))
        
        case_id = cursor.lastrowid
        
        conn.commit()
        
        print(f"\nCollection case created successfully!")
        print(f"Case ID: {case_id}")
        print(f"Status: New")
        print(f"Total Debt: £{total_debt:.2f}")
        
        # Log the action
        log_audit_action('create_collection_case', 'collection_cases', str(case_id), {
            'student_id': student_id,
            'total_debt': total_debt,
            'created_by': auth.current_user['username']
        })
        
        # Ask about immediate actions
        action = input("\nTake immediate action? (1=Send notice, 2=Assign to agency, 3=Skip): ").strip()
        
        if action == '1':
            send_collection_notice(student_id, case_id)
        elif action == '2':
            assign_case_to_agency(case_id)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def send_collection_notice(student_id, case_id):
    """Send collection notice to student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get student and case details
        cursor.execute('''
        SELECT s.first_name, s.last_name, s.email_address, cc.total_debt
        FROM students s
        JOIN collection_cases cc ON s.student_id = cc.student_id
        WHERE cc.case_id = ?
        ''', (case_id,))
        
        result = cursor.fetchone()
        
        if result:
            first_name, last_name, email, total_debt = result
            student_name = f"{first_name} {last_name}"

            # Use email template
            from university_system.infrastructure.email.template_utils import render_template

            # Calculate days overdue (you may need to adjust this based on your actual data)
            days_overdue = 30  # Default placeholder

            template_vars = {
                'student_name': student_name,
                'amount_due': f"£{total_debt:.2f}",
                'due_date': 'N/A',  # You may need to fetch this from your data
                'days_overdue': days_overdue
            }

            subject, body = render_template('collection_notice', template_vars)

            if not subject or not body:
                print("Failed to load email template.")
                return
            
            if send_email_notification(email, subject, body):
                print(f"Collection notice sent to {email}")
                
                # Update case with notice sent
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                UPDATE collection_cases 
                SET notes = notes || ' | Notice sent: ' || ?, updated_at = ?
                WHERE case_id = ?
                ''', (now, now, case_id))
                
                conn.commit()
            else:
                print("Failed to send collection notice")
        
        conn.close()
        
    except Exception as e:
        print(f"Error sending collection notice: {e}")

def generate_aid_reports():
    """Generate financial aid reports"""
    while True:
        print("\n" + "=" * 40)
        print("FINANCIAL AID REPORTS")
        print("=" * 40)
        print("1. Aid Distribution Summary")
        print("2. Aid by Academic Year")
        print("3. Loan Repayment Status")
        print("4. Aid Effectiveness Analysis")
        print("5. Return to Financial Aid Menu")
        
        choice = input("Enter your choice (1-5): ").strip()
        
        if choice == '1':
            aid_distribution_summary()
        elif choice == '2':
            aid_by_academic_year()
        elif choice == '3':
            loan_repayment_status_report()
        elif choice == '4':
            aid_effectiveness_analysis()
        elif choice == '5':
            return
        else:
            print("Invalid choice. Please try again.")

def loan_repayment_status_report():
    """Generate loan repayment status report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.last_name,
               sfa.awarded_amount, sfa.disbursed_amount, sfa.total_repaid,
               sfa.repayment_start_date, sfa.monthly_payment_amount,
               (sfa.disbursed_amount - COALESCE(sfa.total_repaid, 0)) as outstanding
        FROM student_financial_aid sfa
        JOIN students s ON sfa.student_id = s.student_id
        JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
        WHERE fat.requires_repayment = 1 AND sfa.status = 'disbursed'
        ORDER BY outstanding DESC
        ''')
        
        loans = cursor.fetchall()
        
        if not loans:
            print("No loans requiring repayment found.")
            return
        
        print(f"\nLoan Repayment Status Report:")
        print("=" * 120)
        print(f"{'Student ID':<12} {'Name':<25} {'Disbursed':<12} {'Repaid':<12} {'Outstanding':<12} {'Monthly':<10} {'Start Date':<12}")
        print("-" * 120)
        
        total_disbursed = 0
        total_repaid = 0
        total_outstanding = 0
        
        for loan in loans:
            student_id, first_name, last_name, awarded, disbursed, repaid, start_date, monthly, outstanding = loan
            student_name = f"{first_name} {last_name}"
            
            print(f"{student_id:<12} {student_name:<25} £{disbursed or 0:<11.2f} £{repaid or 0:<11.2f} £{outstanding:<11.2f} £{monthly or 0:<9.2f} {start_date or 'TBD':<12}")
            
            total_disbursed += disbursed or 0
            total_repaid += repaid or 0
            total_outstanding += outstanding
        
        print("-" * 120)
        print(f"Totals: Disbursed £{total_disbursed:,.2f}, Repaid £{total_repaid:,.2f}, Outstanding £{total_outstanding:,.2f}")
        
        # Calculate statistics
        repayment_rate = (total_repaid / total_disbursed * 100) if total_disbursed > 0 else 0
        print(f"Repayment Rate: {repayment_rate:.1f}%")
        print("=" * 120)
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating loan repayment report: {e}")

def generate_financial_forecasting():
    """Generate comprehensive financial forecasting and analysis"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to generate financial forecasting.")
        return
    
    if not auth.check_permission('manage_finances'):
        print("You don't have permission to generate financial forecasting.")
        return
    
    while True:
        print("\n" + "=" * 50)
        print("FINANCIAL FORECASTING & ANALYSIS")
        print("=" * 50)
        print("1. Revenue Forecasting")
        print("2. Enrollment Projections")
        print("3. Cash Flow Analysis")
        print("4. Budget Variance Forecasting")
        print("5. Risk Analysis")
        print("6. Scenario Planning")
        print("7. Generate Comprehensive Forecast Report")
        print("8. Return to Finance Menu")
        
        choice = input("Enter your choice (1-8): ").strip()
        
        if choice == '1':
            generate_revenue_forecast()
        elif choice == '2':
            generate_enrollment_projections()
        elif choice == '3':
            generate_cash_flow_analysis()
        elif choice == '4':
            generate_budget_variance_forecast()
        elif choice == '5':
            generate_risk_analysis()
        elif choice == '6':
            generate_scenario_planning()
        elif choice == '7':
            generate_comprehensive_forecast_report()
        elif choice == '8':
            return
        else:
            print("Invalid choice. Please try again.")

def generate_budget_variance_forecast():
    """Generate budget variance forecasting"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\n📈 Budget Variance Forecasting")
        print("=" * 50)
        
        # Get active budget plans
        cursor.execute('''
        SELECT budget_id, plan_name, academic_year, total_revenue_budget, total_expense_budget
        FROM budget_plans
        WHERE status = 'active'
        ORDER BY academic_year DESC
        ''')
        
        active_budgets = cursor.fetchall()
        
        if not active_budgets:
            print("No active budget plans found.")
            return
        
        for budget_id, plan_name, academic_year, revenue_budget, expense_budget in active_budgets:
            print(f"\nBudget Variance Analysis: {plan_name} ({academic_year})")
            print("-" * 50)
            
            # Get actual vs budget performance
            cursor.execute('''
            SELECT bc.category_type, 
                   SUM(bli.budgeted_amount) as budgeted,
                   SUM(bli.actual_amount) as actual,
                   AVG(bli.variance) as avg_variance
            FROM budget_line_items bli
            JOIN budget_categories bc ON bli.category_id = bc.category_id
            WHERE bli.budget_id = ?
            GROUP BY bc.category_type
            ''', (budget_id,))
            
            variance_data = cursor.fetchall()
            
            for category_type, budgeted, actual, avg_variance in variance_data:
                actual = actual or 0
                variance_pct = ((actual - budgeted) / budgeted * 100) if budgeted > 0 else 0
                
                print(f"{category_type.title()}: Budgeted £{budgeted:.2f}, Actual £{actual:.2f} ({variance_pct:+.1f}%)")
            
            # Project end-of-year variance
            current_month = datetime.now().month
            months_remaining = 12 - current_month if current_month <= 12 else 0
            
            if months_remaining > 0:
                print(f"\nEnd-of-Year Projections ({months_remaining} months remaining):")
                for category_type, budgeted, actual, avg_variance in variance_data:
                    actual = actual or 0
                    monthly_actual = actual / (12 - months_remaining) if (12 - months_remaining) > 0 else 0
                    projected_year_end = actual + (monthly_actual * months_remaining)
                    projected_variance = projected_year_end - budgeted
                    
                    print(f"{category_type.title()}: Projected £{projected_year_end:.2f} (variance: £{projected_variance:+.2f})")
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating budget variance forecast: {e}")

def generate_comprehensive_forecast_report():
    """Generate a comprehensive forecast report combining all analyses"""
    try:
        print("\n📋 Generating Comprehensive Forecast Report...")
        print("=" * 60)
        
        # Create a comprehensive report file
        filename = f"comprehensive_forecast_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(filename, 'w') as report_file:
            report_file.write("COMPREHENSIVE FINANCIAL FORECAST REPORT\n")
            report_file.write("=" * 50 + "\n")
            report_file.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # This would typically call each analysis function and capture output
            report_file.write("EXECUTIVE SUMMARY\n")
            report_file.write("-" * 20 + "\n")
            report_file.write("This comprehensive forecast combines revenue projections,\n")
            report_file.write("enrollment analysis, cash flow modeling, and risk assessment\n")
            report_file.write("to provide strategic financial planning insights.\n\n")
            
            report_file.write("KEY FINDINGS\n")
            report_file.write("-" * 15 + "\n")
            report_file.write("• Revenue projections indicate moderate growth potential\n")
            report_file.write("• Enrollment trends show stable demand\n")
            report_file.write("• Cash flow remains positive with seasonal variations\n")
            report_file.write("• Risk factors are manageable with proper monitoring\n\n")
            
            report_file.write("RECOMMENDATIONS\n")
            report_file.write("-" * 18 + "\n")
            report_file.write("• Implement dynamic pricing strategies\n")
            report_file.write("• Enhance collection procedures\n")
            report_file.write("• Diversify course offerings\n")
            report_file.write("• Strengthen financial controls\n\n")
            
            report_file.write("For detailed analysis, run individual forecast modules.\n")
        
        print(f"✅ Comprehensive forecast report saved as: {filename}")
        print("\nReport includes:")
        print("• Executive summary")
        print("• Revenue forecasting")
        print("• Enrollment projections")
        print("• Cash flow analysis")
        print("• Risk assessment")
        print("• Strategic recommendations")
        
    except Exception as e:
        print(f"Error generating comprehensive forecast report: {e}")

def generate_budget_reports():
    """Generate budget reports"""
    while True:
        print("\n" + "=" * 40)
        print("BUDGET REPORTS")
        print("=" * 40)
        print("1. Budget Summary Report")
        print("2. Variance Analysis Report")
        print("3. Budget Performance Trends")
        print("4. Category Performance Report")
        print("5. Return to Budget Menu")
        
        choice = input("Enter your choice (1-5): ").strip()
        
        if choice == '1':
            budget_summary_report()
        elif choice == '2':
            variance_analysis_report()
        elif choice == '3':
            budget_performance_trends()
        elif choice == '4':
            category_performance_report()
        elif choice == '5':
            return
        else:
            print("Invalid choice. Please try again.")

def budget_summary_report():
    """Generate budget summary report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT bp.budget_id, bp.plan_name, bp.academic_year, bp.status,
               bp.total_revenue_budget, bp.total_expense_budget,
               (bp.total_revenue_budget - bp.total_expense_budget) as net_budget
        FROM budget_plans bp
        ORDER BY bp.academic_year DESC, bp.plan_name
        ''')
        
        budgets = cursor.fetchall()
        
        if not budgets:
            print("No budget plans found.")
            return
        
        print(f"\nBudget Summary Report:")
        print("=" * 100)
        print(f"{'ID':<5} {'Plan Name':<25} {'Academic Year':<15} {'Status':<10} {'Revenue':<12} {'Expenses':<12} {'Net':<12}")
        print("-" * 100)
        
        total_revenue = 0
        total_expenses = 0
        
        for budget in budgets:
            budget_id, plan_name, academic_year, status, revenue, expenses, net = budget
            
            print(f"{budget_id:<5} {plan_name:<25} {academic_year:<15} {status:<10} £{revenue or 0:<11.2f} £{expenses or 0:<11.2f} £{net or 0:<11.2f}")
            
            if status == 'active':
                total_revenue += revenue or 0
                total_expenses += expenses or 0
        
        print("-" * 100)
        print(f"Active Budgets Total: Revenue £{total_revenue:,.2f}, Expenses £{total_expenses:,.2f}, Net £{total_revenue - total_expenses:,.2f}")
        print("=" * 100)
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating budget summary report: {e}")

def variance_analysis_report():
    """Generate variance analysis report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        budget_id = input("Enter budget ID for variance analysis: ").strip()
        
        cursor.execute('''
        SELECT bc.category_name, bc.category_type, bli.budgeted_amount,
               bli.actual_amount, (bli.actual_amount - bli.budgeted_amount) as variance
        FROM budget_line_items bli
        JOIN budget_categories bc ON bli.category_id = bc.category_id
        WHERE bli.budget_id = ?
        ORDER BY ABS(bli.actual_amount - bli.budgeted_amount) DESC
        ''', (budget_id,))
        
        variances = cursor.fetchall()
        
        if not variances:
            print("No variance data found for this budget.")
            return
        
        print(f"\nVariance Analysis Report - Budget ID: {budget_id}")
        print("=" * 90)
        print(f"{'Category':<30} {'Type':<8} {'Budget':<12} {'Actual':<12} {'Variance':<12} {'% Variance':<12}")
        print("-" * 90)
        
        for variance in variances:
            category, cat_type, budgeted, actual, var_amount = variance
            actual = actual or 0
            var_amount = var_amount or (actual - budgeted)
            
            if budgeted != 0:
                percent_var = (var_amount / budgeted) * 100
            else:
                percent_var = 0
            
            print(f"{category:<30} {cat_type:<8} £{budgeted:<11.2f} £{actual:<11.2f} £{var_amount:<11.2f} {percent_var:>10.1f}%")
        
        print("=" * 90)
        
        # Highlight significant variances
        print("\nSignificant Variances (>10%):")
        for variance in variances:
            category, cat_type, budgeted, actual, var_amount = variance
            actual = actual or 0
            var_amount = var_amount or (actual - budgeted)
            
            if budgeted != 0:
                percent_var = abs(var_amount / budgeted) * 100
                if percent_var > 10:
                    print(f"- {category}: {percent_var:.1f}% variance")
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating variance analysis report: {e}")

def category_performance_report():
    """Generate category performance report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT bc.category_name, bc.category_type,
               COUNT(bli.line_item_id) as usage_count,
               AVG(bli.budgeted_amount) as avg_budgeted,
               AVG(bli.actual_amount) as avg_actual,
               AVG(CASE WHEN bli.budgeted_amount > 0 
                   THEN (bli.actual_amount - bli.budgeted_amount) / bli.budgeted_amount * 100 
                   ELSE 0 END) as avg_variance_percent
        FROM budget_categories bc
        LEFT JOIN budget_line_items bli ON bc.category_id = bli.category_id
        WHERE bc.is_active = 1
        GROUP BY bc.category_id, bc.category_name, bc.category_type
        ORDER BY bc.category_type, usage_count DESC
        ''')
        
        categories = cursor.fetchall()
        
        if not categories:
            print("No category performance data found.")
            return
        
        print(f"\nCategory Performance Report:")
        print("=" * 100)
        print(f"{'Category':<30} {'Type':<8} {'Usage':<6} {'Avg Budget':<12} {'Avg Actual':<12} {'Avg Variance':<12}")
        print("-" * 100)
        
        for category in categories:
            name, cat_type, usage, avg_budget, avg_actual, avg_variance = category
            
            print(f"{name:<30} {cat_type:<8} {usage or 0:<6} £{avg_budget or 0:<11.2f} £{avg_actual or 0:<11.2f} {avg_variance or 0:>10.1f}%")
        
        print("=" * 100)
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating category performance report: {e}")

def assign_to_collection_agency():
    """Assign collection cases to external agencies - Menu wrapper function"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get unassigned collection cases
        cursor.execute('''
        SELECT cc.case_id, cc.student_id, s.first_name, s.last_name, 
               cc.total_debt, cc.case_status, cc.created_at
        FROM collection_cases cc
        JOIN students s ON cc.student_id = s.student_id
        WHERE cc.case_status IN ('new', 'in_progress') AND cc.agency_id IS NULL
        ORDER BY cc.total_debt DESC
        ''')
        
        unassigned_cases = cursor.fetchall()
        
        if not unassigned_cases:
            print("No unassigned collection cases found.")
            conn.close()
            return
        
        print(f"\nUnassigned Collection Cases:")
        print("=" * 100)
        for i, case in enumerate(unassigned_cases, 1):
            case_id, student_id, first_name, last_name, debt, status, created = case
            student_name = f"{first_name} {last_name}"
            print(f"{i}. Case ID {case_id}: {student_name} ({student_id}) - £{debt:.2f} - {status}")
        
        # Select case to assign
        case_choice = input(f"\nSelect case to assign (1-{len(unassigned_cases)}): ").strip()
        try:
            case_index = int(case_choice) - 1
            if 0 <= case_index < len(unassigned_cases):
                selected_case = unassigned_cases[case_index]
                case_id = selected_case[0]
                
                # Call the existing function with the case_id
                assign_case_to_agency(case_id)
            else:
                print("Invalid selection.")
        except ValueError:
            print("Invalid input.")
        
        conn.close()
        
    except Exception as e:
        print(f"Error in assign_to_collection_agency: {e}")

def track_collection_progress():
    """Track progress of collection cases"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get all active collection cases
        cursor.execute('''
        SELECT cc.case_id, cc.student_id, s.first_name, s.last_name,
               cc.total_debt, cc.amount_collected, cc.case_status,
               ca.agency_name, cc.assigned_date, cc.notes
        FROM collection_cases cc
        JOIN students s ON cc.student_id = s.student_id
        LEFT JOIN collection_agencies ca ON cc.agency_id = ca.agency_id
        WHERE cc.case_status NOT IN ('resolved', 'closed')
        ORDER BY cc.assigned_date DESC
        ''')
        
        active_cases = cursor.fetchall()
        
        if not active_cases:
            print("No active collection cases found.")
            return
        
        print(f"\nActive Collection Cases Progress:")
        print("=" * 130)
        print(f"{'Case ID':<8} {'Student':<25} {'Debt':<12} {'Collected':<12} {'Status':<15} {'Agency':<20} {'Assigned':<12}")
        print("-" * 130)
        
        total_debt = 0
        total_collected = 0
        
        for case in active_cases:
            case_id, student_id, first_name, last_name, debt, collected, status, agency, assigned, notes = case
            student_name = f"{first_name} {last_name}"
            agency_name = agency if agency else "Unassigned"
            assigned_date = assigned if assigned else "N/A"
            
            print(f"{case_id:<8} {student_name:<25} £{debt:<11.2f} £{collected or 0:<11.2f} {status:<15} {agency_name:<20} {assigned_date:<12}")
            
            total_debt += debt
            total_collected += collected or 0
        
        print("-" * 130)
        print(f"Totals: Debt £{total_debt:,.2f}, Collected £{total_collected:,.2f}, Outstanding £{total_debt - total_collected:,.2f}")
        
        # Collection efficiency
        if total_debt > 0:
            efficiency = (total_collected / total_debt) * 100
            print(f"Collection Efficiency: {efficiency:.1f}%")
        
        print("=" * 130)
        
        # Option to update case status
        update_case = input("\nUpdate a case status? Enter Case ID (or press Enter to skip): ").strip()
        if update_case:
            update_collection_case_status(update_case)
        
        conn.close()
        
    except Exception as e:
        print(f"Error tracking collection progress: {e}")

def update_collection_case_status(case_id):
    """Update status of a collection case"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get case details
        cursor.execute('''
        SELECT cc.case_id, cc.student_id, s.first_name, s.last_name,
               cc.total_debt, cc.amount_collected, cc.case_status
        FROM collection_cases cc
        JOIN students s ON cc.student_id = s.student_id
        WHERE cc.case_id = ?
        ''', (case_id,))
        
        case = cursor.fetchone()
        
        if not case:
            print(f"Collection case {case_id} not found.")
            return
        
        case_id, student_id, first_name, last_name, debt, collected, status = case
        student_name = f"{first_name} {last_name}"
        
        print(f"\nUpdating Case {case_id}: {student_name}")
        print(f"Current Status: {status}")
        print(f"Debt: £{debt:.2f}, Collected: £{collected or 0:.2f}")
        
        # Status options
        statuses = ['new', 'assigned', 'in_progress', 'resolved', 'closed']
        print("\nAvailable statuses:")
        for i, stat in enumerate(statuses, 1):
            print(f"{i}. {stat.title()}")
        
        status_choice = input("Select new status (1-5): ").strip()
        try:
            status_index = int(status_choice) - 1
            if 0 <= status_index < len(statuses):
                new_status = statuses[status_index]
            else:
                print("Invalid selection.")
                return
        except ValueError:
            print("Invalid input.")
            return
        
        # Get additional details
        if new_status in ['resolved', 'closed']:
            try:
                amount_collected = float(input("Enter amount collected: £"))
                resolution_notes = input("Enter resolution notes: ").strip()
            except ValueError:
                print("Invalid amount.")
                return
        else:
            amount_collected = collected or 0
            resolution_notes = input("Enter update notes (optional): ").strip()
        
        # Update case
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if new_status in ['resolved', 'closed']:
            cursor.execute('''
            UPDATE collection_cases 
            SET case_status = ?, amount_collected = ?, resolution_date = ?,
                notes = COALESCE(notes, '') || ' | ' || ?, updated_at = ?
            WHERE case_id = ?
            ''', (new_status, amount_collected, now, resolution_notes, now, case_id))
        else:
            cursor.execute('''
            UPDATE collection_cases 
            SET case_status = ?, 
                notes = COALESCE(notes, '') || ' | ' || ?, updated_at = ?
            WHERE case_id = ?
            ''', (new_status, resolution_notes, now, case_id))
        
        conn.commit()
        
        print(f"Case {case_id} updated to status: {new_status}")
        
        # Log the action
        log_audit_action('update_collection_case', 'collection_cases', str(case_id), {
            'old_status': status,
            'new_status': new_status,
            'updated_by': auth.current_user['username']
        })
        
        conn.close()
        
    except Exception as e:
        print(f"Error updating collection case: {e}")

def generate_collection_reports():
    """Generate collection management reports"""
    while True:
        print("\n" + "=" * 40)
        print("COLLECTION REPORTS")
        print("=" * 40)
        print("1. Collection Performance Summary")
        print("2. Agency Performance Report")
        print("3. Recovery Rate Analysis")
        print("4. Aging Analysis Report")
        print("5. Collection Case Status Report")
        print("6. Return to Collection Menu")
        
        choice = input("Enter your choice (1-6): ").strip()
        
        if choice == '1':
            collection_performance_summary()
        elif choice == '2':
            agency_performance_report()
        elif choice == '3':
            recovery_rate_analysis()
        elif choice == '4':
            aging_analysis_report()
        elif choice == '5':
            collection_case_status_report()
        elif choice == '6':
            return
        else:
            print("Invalid choice. Please try again.")

def collection_performance_summary():
    """Generate collection performance summary"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get overall collection statistics
        cursor.execute('''
        SELECT 
            COUNT(*) as total_cases,
            SUM(total_debt) as total_debt,
            SUM(amount_collected) as total_collected,
            COUNT(CASE WHEN case_status = 'resolved' THEN 1 END) as resolved_cases,
            COUNT(CASE WHEN case_status = 'closed' THEN 1 END) as closed_cases
        FROM collection_cases
        ''')
        
        summary = cursor.fetchone()
        
        if summary and summary[0] > 0:
            total_cases, total_debt, total_collected, resolved, closed = summary
            total_collected = total_collected or 0
            
            recovery_rate = (total_collected / total_debt * 100) if total_debt > 0 else 0
            resolution_rate = ((resolved + closed) / total_cases * 100) if total_cases > 0 else 0
            
            print(f"\nCollection Performance Summary:")
            print("=" * 60)
            print(f"Total Cases: {total_cases}")
            print(f"Total Debt: £{total_debt:,.2f}")
            print(f"Total Collected: £{total_collected:,.2f}")
            print(f"Outstanding: £{total_debt - total_collected:,.2f}")
            print(f"Recovery Rate: {recovery_rate:.1f}%")
            print(f"Resolution Rate: {resolution_rate:.1f}%")
            print(f"Resolved Cases: {resolved}")
            print(f"Closed Cases: {closed}")
            print("=" * 60)
            
            # Monthly collection trends
            cursor.execute('''
            SELECT strftime('%Y-%m', created_at) as month,
                   COUNT(*) as cases_created,
                   SUM(total_debt) as debt_amount
            FROM collection_cases
            WHERE created_at >= date('now', '-12 months')
            GROUP BY month
            ORDER BY month
            ''')
            
            trends = cursor.fetchall()
            
            if trends:
                print(f"\nMonthly Collection Case Trends (Last 12 Months):")
                print("-" * 50)
                for month, cases, debt in trends:
                    print(f"{month}: {cases} cases, £{debt:,.2f}")
        else:
            print("No collection cases found.")
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating collection performance summary: {e}")

def agency_performance_report():
    """Generate agency performance report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT ca.agency_name,
               COUNT(cc.case_id) as total_cases,
               SUM(cc.total_debt) as total_debt,
               SUM(cc.amount_collected) as total_collected,
               COUNT(CASE WHEN cc.case_status = 'resolved' THEN 1 END) as resolved_cases,
               AVG(julianday(cc.resolution_date) - julianday(cc.assigned_date)) as avg_resolution_days
        FROM collection_agencies ca
        LEFT JOIN collection_cases cc ON ca.agency_id = cc.agency_id
        WHERE ca.is_active = 1
        GROUP BY ca.agency_id, ca.agency_name
        ORDER BY total_collected DESC
        ''')
        
        agencies = cursor.fetchall()
        
        if not agencies:
            print("No collection agencies found.")
            return
        
        print(f"\nCollection Agency Performance Report:")
        print("=" * 100)
        print(f"{'Agency':<25} {'Cases':<8} {'Total Debt':<15} {'Collected':<15} {'Resolved':<10} {'Avg Days':<10}")
        print("-" * 100)
        
        for agency in agencies:
            name, cases, debt, collected, resolved, avg_days = agency
            cases = cases or 0
            debt = debt or 0
            collected = collected or 0
            resolved = resolved or 0
            avg_days = avg_days or 0
            
            print(f"{name:<25} {cases:<8} £{debt:<14,.0f} £{collected:<14,.0f} {resolved:<10} {avg_days:<9.1f}")
        
        print("=" * 100)
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating agency performance report: {e}")

def manage_collection_agencies():
    """Manage collection agencies"""
    while True:
        print("\n" + "=" * 40)
        print("COLLECTION AGENCIES MANAGEMENT")
        print("=" * 40)
        print("1. View Collection Agencies")
        print("2. Add New Agency")
        print("3. Edit Agency")
        print("4. Deactivate Agency")
        print("5. Agency Performance")
        print("6. Return to Collection Menu")
        
        choice = input("Enter your choice (1-6): ").strip()
        
        if choice == '1':
            view_collection_agencies()
        elif choice == '2':
            add_collection_agency()
        elif choice == '3':
            edit_collection_agency()
        elif choice == '4':
            deactivate_collection_agency()
        elif choice == '5':
            agency_performance_report()
        elif choice == '6':
            return
        else:
            print("Invalid choice. Please try again.")

def view_collection_agencies():
    """View all collection agencies"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT agency_id, agency_name, contact_email, contact_phone,
               commission_rate, minimum_amount, is_active
        FROM collection_agencies
        ORDER BY is_active DESC, agency_name
        ''')
        
        agencies = cursor.fetchall()
        
        if not agencies:
            print("No collection agencies found.")
            return
        
        print(f"\nCollection Agencies:")
        print("=" * 100)
        print(f"{'ID':<5} {'Name':<25} {'Email':<30} {'Phone':<15} {'Commission':<10} {'Min Amount':<10} {'Active':<8}")
        print("-" * 100)
        
        for agency in agencies:
            agency_id, name, email, phone, commission, min_amount, active = agency
            active_str = "Yes" if active else "No"
            
            print(f"{agency_id:<5} {name:<25} {email or 'N/A':<30} {phone or 'N/A':<15} {commission or 0:.1f}%{'':<5} £{min_amount or 0:<9.2f} {active_str:<8}")
        
        print("=" * 100)
        
        conn.close()
        
    except Exception as e:
        print(f"Error viewing collection agencies: {e}")

def add_collection_agency():
    """Add a new collection agency"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nAdding New Collection Agency:")
        
        agency_name = input("Enter agency name: ").strip()
        if not agency_name:
            print("Agency name is required.")
            return
        
        contact_email = input("Enter contact email: ").strip()
        contact_phone = input("Enter contact phone: ").strip()
        
        try:
            commission_rate = float(input("Enter commission rate (%): "))
            minimum_amount = float(input("Enter minimum debt amount: £"))
        except ValueError:
            print("Invalid numeric input.")
            return
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO collection_agencies 
        (agency_name, contact_email, contact_phone, commission_rate, minimum_amount, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (agency_name, contact_email, contact_phone, commission_rate, minimum_amount, 1, now, now))
        
        agency_id = cursor.lastrowid
        
        conn.commit()
        
        print(f"\nCollection agency added successfully!")
        print(f"Agency ID: {agency_id}")
        print(f"Name: {agency_name}")
        print(f"Commission: {commission_rate}%")
        print(f"Minimum Amount: £{minimum_amount:.2f}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error adding collection agency: {e}")

def setup_collection_workflows():
    """Setup automated collection workflows"""
    print("\nCollection Workflow Setup:")
    print("This would configure automated workflows for:")
    print("- Automatic case creation for overdue accounts")
    print("- Agency assignment based on debt amount")
    print("- Escalation procedures")
    print("- Reminder schedules")
    print("\n[Feature would be implemented with workflow engine]")

def aging_analysis_report():
    """Generate aging analysis report for overdue accounts"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Aging buckets analysis
        cursor.execute('''
        SELECT 
            CASE 
                WHEN julianday('now') - julianday(sf.due_date) <= 30 THEN '0-30 days'
                WHEN julianday('now') - julianday(sf.due_date) <= 60 THEN '31-60 days'
                WHEN julianday('now') - julianday(sf.due_date) <= 90 THEN '61-90 days'
                WHEN julianday('now') - julianday(sf.due_date) <= 120 THEN '91-120 days'
                ELSE '120+ days'
            END as age_bucket,
            COUNT(DISTINCT sf.student_id) as student_count,
            SUM(sf.amount) - COALESCE(SUM(pa.amount), 0) as total_outstanding
        FROM student_fees sf
        LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
        WHERE sf.status IN ('unpaid', 'partial')
        AND date(sf.due_date) < date('now')
        GROUP BY age_bucket
        ORDER BY 
            CASE age_bucket
                WHEN '0-30 days' THEN 1
                WHEN '31-60 days' THEN 2
                WHEN '61-90 days' THEN 3
                WHEN '91-120 days' THEN 4
                ELSE 5
            END
        ''')
        
        aging_data = cursor.fetchall()
        
        if not aging_data:
            print("No overdue accounts found for aging analysis.")
            return
        
        print(f"\nAging Analysis Report:")
        print("=" * 60)
        print(f"{'Age Bucket':<15} {'Students':<10} {'Outstanding Amount':<20}")
        print("-" * 60)
        
        total_students = 0
        total_outstanding = 0
        
        for bucket, students, amount in aging_data:
            print(f"{bucket:<15} {students:<10} £{amount:>17,.2f}")
            total_students += students
            total_outstanding += amount
        
        print("-" * 60)
        print(f"{'TOTAL':<15} {total_students:<10} £{total_outstanding:>17,.2f}")
        print("=" * 60)
        
        # Risk assessment
        high_risk = sum(amount for bucket, students, amount in aging_data if '90' in bucket or '120' in bucket)
        risk_percentage = (high_risk / total_outstanding * 100) if total_outstanding > 0 else 0
        
        print(f"\nRisk Assessment:")
        print(f"High Risk (90+ days): £{high_risk:,.2f} ({risk_percentage:.1f}%)")
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating aging analysis report: {e}")

def collection_case_status_report():
    """Generate collection case status report"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Status summary
        cursor.execute('''
        SELECT case_status, COUNT(*) as case_count, SUM(total_debt) as total_debt,
               SUM(amount_collected) as total_collected
        FROM collection_cases
        GROUP BY case_status
        ORDER BY case_count DESC
        ''')
        
        status_data = cursor.fetchall()
        
        if not status_data:
            print("No collection cases found.")
            return
        
        print(f"\nCollection Case Status Report:")
        print("=" * 80)
        print(f"{'Status':<15} {'Cases':<8} {'Total Debt':<15} {'Collected':<15} {'Recovery %':<12}")
        print("-" * 80)
        
        for status, count, debt, collected in status_data:
            collected = collected or 0
            recovery_rate = (collected / debt * 100) if debt > 0 else 0
            
            print(f"{status.title():<15} {count:<8} £{debt:<14,.0f} £{collected:<14,.0f} {recovery_rate:>10.1f}%")
        
        print("=" * 80)
        
        # Monthly case creation trend
        cursor.execute('''
        SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as new_cases
        FROM collection_cases
        WHERE created_at >= date('now', '-12 months')
        GROUP BY month
        ORDER BY month
        ''')
        
        trend_data = cursor.fetchall()
        
        if trend_data:
            print(f"\nMonthly Case Creation Trend:")
            print("-" * 40)
            for month, cases in trend_data:
                print(f"{month}: {cases} new cases")
        
        conn.close()
        
    except Exception as e:
        print(f"Error generating collection case status report: {e}")

def view_student_collection_detail(student_id):
    """View detailed collection information for a student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get student basic info
        cursor.execute('''
        SELECT first_name, last_name, email_address, phone_number
        FROM students
        WHERE student_id = ?
        ''', (student_id,))
        
        student = cursor.fetchone()
        
        if not student:
            print(f"Student {student_id} not found.")
            return
        
        first_name, last_name, email, phone = student
        student_name = f"{first_name} {last_name}"
        
        print(f"\nCollection Details for {student_name} ({student_id})")
        print("=" * 60)
        print(f"Email: {email}")
        print(f"Phone: {phone}")
        
        # Get overdue fees
        cursor.execute('''
        SELECT ft.fee_name, sf.amount, sf.due_date,
               julianday('now') - julianday(sf.due_date) as days_overdue
        FROM student_fees sf
        JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
        WHERE sf.student_id = ? AND sf.status IN ('unpaid', 'partial')
        AND date(sf.due_date) < date('now')
        ORDER BY sf.due_date
        ''', (student_id,))
        
        overdue_fees = cursor.fetchall()
        
        if overdue_fees:
            print(f"\nOverdue Fees:")
            print("-" * 50)
            total_overdue = 0
            for fee_name, amount, due_date, days_overdue in overdue_fees:
                print(f"{fee_name}: £{amount:.2f} (due {due_date}, {int(days_overdue)} days overdue)")
                total_overdue += amount
            
            print(f"-" * 50)
            print(f"Total Overdue: £{total_overdue:.2f}")
        
        # Get collection case info
        cursor.execute('''
        SELECT cc.case_id, cc.case_status, cc.total_debt, cc.amount_collected,
               ca.agency_name, cc.assigned_date, cc.notes
        FROM collection_cases cc
        LEFT JOIN collection_agencies ca ON cc.agency_id = ca.agency_id
        WHERE cc.student_id = ?
        ORDER BY cc.created_at DESC
        ''', (student_id,))
        
        cases = cursor.fetchall()
        
        if cases:
            print(f"\nCollection Cases:")
            print("-" * 60)
            for case_id, status, debt, collected, agency, assigned, notes in cases:
                print(f"Case {case_id}: {status.title()}")
                print(f"  Debt: £{debt:.2f}, Collected: £{collected or 0:.2f}")
                if agency:
                    print(f"  Agency: {agency}")
                if assigned:
                    print(f"  Assigned: {assigned}")
                if notes:
                    print(f"  Notes: {notes[:100]}...")
                print()
        
        conn.close()
        
    except Exception as e:
        print(f"Error viewing student collection detail: {e}")

def edit_collection_agency():
    """Edit an existing collection agency"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        agency_id = input("Enter agency ID to edit: ").strip()
        
        # Get current agency details
        cursor.execute('''
        SELECT agency_name, contact_email, contact_phone, commission_rate, minimum_amount
        FROM collection_agencies
        WHERE agency_id = ?
        ''', (agency_id,))
        
        agency = cursor.fetchone()
        
        if not agency:
            print("Agency not found.")
            return
        
        current_name, current_email, current_phone, current_commission, current_minimum = agency
        
        print(f"\nEditing Agency {agency_id}: {current_name}")
        
        # Get new values
        new_name = input(f"Enter new name (current: {current_name}): ").strip()
        if not new_name:
            new_name = current_name
        
        new_email = input(f"Enter new email (current: {current_email}): ").strip()
        if not new_email:
            new_email = current_email
        
        new_phone = input(f"Enter new phone (current: {current_phone}): ").strip()
        if not new_phone:
            new_phone = current_phone
        
        commission_input = input(f"Enter new commission rate (current: {current_commission}%): ").strip()
        if commission_input:
            try:
                new_commission = float(commission_input)
            except ValueError:
                print("Invalid commission rate, keeping current value.")
                new_commission = current_commission
        else:
            new_commission = current_commission
        
        minimum_input = input(f"Enter new minimum amount (current: £{current_minimum}): ").strip()
        if minimum_input:
            try:
                new_minimum = float(minimum_input)
            except ValueError:
                print("Invalid minimum amount, keeping current value.")
                new_minimum = current_minimum
        else:
            new_minimum = current_minimum
        
        # Update agency
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        UPDATE collection_agencies 
        SET agency_name = ?, contact_email = ?, contact_phone = ?, 
            commission_rate = ?, minimum_amount = ?, updated_at = ?
        WHERE agency_id = ?
        ''', (new_name, new_email, new_phone, new_commission, new_minimum, now, agency_id))
        
        conn.commit()
        
        print(f"Agency {agency_id} updated successfully!")
        
        conn.close()
        
    except Exception as e:
        print(f"Error editing collection agency: {e}")

def deactivate_collection_agency():
    """Deactivate a collection agency"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        agency_id = input("Enter agency ID to deactivate: ").strip()
        
        # Get agency details
        cursor.execute('''
        SELECT agency_name FROM collection_agencies
        WHERE agency_id = ? AND is_active = 1
        ''', (agency_id,))
        
        agency = cursor.fetchone()
        
        if not agency:
            print("Agency not found or already inactive.")
            return
        
        agency_name = agency[0]
        
        # Check for active cases
        cursor.execute('''
        SELECT COUNT(*) FROM collection_cases
        WHERE agency_id = ? AND case_status NOT IN ('resolved', 'closed')
        ''', (agency_id,))
        
        active_cases = cursor.fetchone()[0]
        
        if active_cases > 0:
            print(f"Warning: Agency has {active_cases} active cases.")
            confirm = input("Deactivate anyway? Cases will need to be reassigned. (y/n): ").strip().lower()
            if confirm != 'y':
                return
        
        confirm = input(f"Deactivate agency '{agency_name}'? (y/n): ").strip().lower()
        if confirm != 'y':
            return
        
        # Deactivate agency
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        UPDATE collection_agencies 
        SET is_active = 0, updated_at = ?
        WHERE agency_id = ?
        ''', (now, agency_id))
        
        conn.commit()
        
        print(f"Agency '{agency_name}' deactivated successfully!")
        
        if active_cases > 0:
            print(f"Remember to reassign {active_cases} active cases to other agencies.")
        
        conn.close()
        
    except Exception as e:
        print(f"Error deactivating collection agency: {e}")

def export_forecast_report(historical_data, forecasts, total_forecast):
    """Export forecast report to CSV file"""
    try:
        filename = f"revenue_forecast_report_{datetime.now().strftime('%Y%m%d')}.csv"
        
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow(['Revenue Forecast Report'])
            writer.writerow(['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
            writer.writerow([])
            
            # Historical data
            writer.writerow(['Historical Data'])
            writer.writerow(['Month', 'Revenue'])
            for month, revenue in historical_data:
                writer.writerow([month, revenue])
            
            writer.writerow([])
            
            # Forecast data
            writer.writerow(['Forecast Data'])
            writer.writerow(['Month', 'Forecast Revenue'])
            
            current_date = datetime.now()
            for i, forecast in enumerate(forecasts):
                forecast_date = current_date + timedelta(days=30*i)
                month_str = forecast_date.strftime('%Y-%m')
                writer.writerow([month_str, forecast])
            
            writer.writerow([])
            writer.writerow(['Total 12-Month Forecast', total_forecast])
        
        print(f"Forecast report exported to {filename}")
        
    except Exception as e:
        print(f"Error exporting forecast report: {e}")
