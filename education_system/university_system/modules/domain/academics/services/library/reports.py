from education_system.university_system.infrastructure.database.db import sqlite3, DatabaseManager, get_connection as get_db_conn
from education_system.university_system.infrastructure.shared_context import get_auth
import os
import re
import csv
import pandas as pd
import random
import json
import qrcode
import requests
from datetime import datetime, timedelta
from education_system.university_system.modules.shared.constants.paths import QR_CODES_DIR, BACKUP_DIR
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from education_system.university_system.infrastructure.email import (
    send_book_checkout_confirmation,
    send_book_return_reminder,
    send_overdue_notification,
)
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import hashlib
import uuid
from collections import defaultdict
import matplotlib.pyplot as plt
import seaborn as sns
import shutil
from typing import Any, List, Dict, Optional, Tuple
import logging
from education_system.university_system.utils.logging.log_config import configure_logging

# CONSOLIDATED DATABASE FILE - Using the same database as main system
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
from education_system.university_system.modules.shared.utils.finance_integration import record_payment_to_finance
from education_system.university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)
DATABASE_FILE = str(DEFAULT_DB_PATH)

# Configure logging
logger = configure_logging(name=__name__)

def generate_circulation_report(start_date=None, end_date=None):
    """Generate detailed circulation report"""
    conn = get_db_connection()
    if not conn:
        return None

    cursor = conn.cursor()

    try:
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')

        # Get circulation data
        cursor.execute('''
        SELECT
            date(checkout_date) as checkout_day,
            COUNT(*) as daily_checkouts,
            COUNT(DISTINCT user_id) as unique_borrowers,
            COUNT(DISTINCT book_id) as unique_books
        FROM book_loans
        WHERE date(checkout_date) BETWEEN ? AND ?
        GROUP BY checkout_day
        ORDER BY checkout_day
        ''', (start_date, end_date))

        daily_data = cursor.fetchall()

        # Get returns data
        cursor.execute('''
        SELECT
            date(return_date) as return_day,
            COUNT(*) as daily_returns
        FROM book_loans
        WHERE date(return_date) BETWEEN ? AND ?
        GROUP BY return_day
        ORDER BY return_day
        ''', (start_date, end_date))

        return_data = cursor.fetchall()

        # Get category breakdown
        cursor.execute('''
        SELECT
            b.category,
            COUNT(*) as checkouts
        FROM book_loans bl
        JOIN books b ON bl.book_id = b.book_id
        WHERE date(bl.checkout_date) BETWEEN ? AND ?
        GROUP BY b.category
        ORDER BY checkouts DESC
        ''', (start_date, end_date))

        category_data = cursor.fetchall()

        # Generate report
        report = {
            'period': f"{start_date} to {end_date}",
            'daily_circulation': daily_data,
            'daily_returns': return_data,
            'category_breakdown': category_data,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        conn.close()
        return report

    except sqlite3.Error as e:
        logging.error(f"Error generating circulation report: {e}")
        conn.close()
        return None


def generate_inventory_report():
    """Generate inventory/collection report"""
    conn = get_db_connection()
    if not conn:
        return None

    cursor = conn.cursor()

    try:
        # Collection overview
        cursor.execute('''
        SELECT
            category,
            COUNT(*) as total_books,
            SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available,
            SUM(CASE WHEN status = 'checked_out' THEN 1 ELSE 0 END) as checked_out,
            SUM(CASE WHEN status = 'lost' THEN 1 ELSE 0 END) as lost,
            SUM(CASE WHEN status = 'damaged' THEN 1 ELSE 0 END) as damaged,
            ROUND(AVG(acquisition_cost), 2) as avg_cost,
            SUM(acquisition_cost) as total_value
        FROM books
        GROUP BY category
        ORDER BY total_books DESC
        ''')

        category_stats = cursor.fetchall()

        # Reading level distribution
        cursor.execute('''
        SELECT
            reading_level,
            COUNT(*) as book_count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM books), 2) as percentage
        FROM books
        WHERE reading_level IS NOT NULL
        GROUP BY reading_level
        ORDER BY book_count DESC
        ''')

        reading_level_stats = cursor.fetchall()

        # Publication year analysis
        cursor.execute('''
        SELECT
            CASE
                WHEN year_published >= 2020 THEN '2020+'
                WHEN year_published >= 2010 THEN '2010-2019'
                WHEN year_published >= 2000 THEN '2000-2009'
                WHEN year_published >= 1990 THEN '1990-1999'
                ELSE 'Pre-1990'
            END as year_range,
            COUNT(*) as book_count
        FROM books
        WHERE year_published IS NOT NULL
        GROUP BY year_range
        ORDER BY book_count DESC
        ''')

        publication_stats = cursor.fetchall()

        # Authors with most books
        cursor.execute('''
        SELECT
            author,
            COUNT(*) as book_count
        FROM books
        GROUP BY author
        HAVING book_count > 1
        ORDER BY book_count DESC
        LIMIT 20
        ''')

        author_stats = cursor.fetchall()

        report = {
            'category_statistics': category_stats,
            'reading_level_distribution': reading_level_stats,
            'publication_year_analysis': publication_stats,
            'prolific_authors': author_stats,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        conn.close()
        return report

    except sqlite3.Error as e:
        logging.error(f"Error generating inventory report: {e}")
        conn.close()
        return None


def generate_user_activity_report(days=30):
    """Generate user activity analysis report"""
    conn = get_db_connection()
    if not conn:
        return None

    cursor = conn.cursor()

    try:
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        # Active users analysis
        cursor.execute('''
        SELECT
            user_id,
            COUNT(*) as total_checkouts,
            COUNT(DISTINCT book_id) as unique_books,
            AVG(reading_progress) as avg_reading_progress,
            SUM(fine_amount) as total_fines,
            MIN(checkout_date) as first_checkout,
            MAX(checkout_date) as last_checkout
        FROM book_loans
        WHERE checkout_date >= ?
        GROUP BY user_id
        HAVING total_checkouts > 0
        ORDER BY total_checkouts DESC
        ''', (start_date,))

        user_activity = cursor.fetchall()

        # Category preferences by user
        cursor.execute('''
        SELECT
            bl.user_id,
            b.category,
            COUNT(*) as category_checkouts
        FROM book_loans bl
        JOIN books b ON bl.book_id = b.book_id
        WHERE bl.checkout_date >= ?
        GROUP BY bl.user_id, b.category
        ORDER BY bl.user_id, category_checkouts DESC
        ''', (start_date,))

        category_preferences = cursor.fetchall()

        # Reading completion rates
        cursor.execute('''
        SELECT
            CASE
                WHEN reading_progress >= 90 THEN 'Completed (90-100%)'
                WHEN reading_progress >= 70 THEN 'Mostly Read (70-89%)'
                WHEN reading_progress >= 50 THEN 'Partially Read (50-69%)'
                WHEN reading_progress > 0 THEN 'Started (1-49%)'
                ELSE 'Not Started'
            END as completion_category,
            COUNT(*) as user_count
        FROM book_loans
        WHERE checkout_date >= ?
        GROUP BY completion_category
        ORDER BY user_count DESC
        ''', (start_date,))

        completion_rates = cursor.fetchall()

        # User engagement metrics
        cursor.execute('''
        SELECT
            COUNT(DISTINCT user_id) as total_active_users,
            ROUND(AVG(checkout_count), 2) as avg_checkouts_per_user,
            MAX(checkout_count) as max_checkouts_by_user
        FROM (
            SELECT user_id, COUNT(*) as checkout_count
            FROM book_loans
            WHERE checkout_date >= ?
            GROUP BY user_id
        )
        ''', (start_date,))

        engagement_metrics = cursor.fetchone()

        report = {
            'analysis_period': f"Last {days} days",
            'user_activity_data': user_activity,
            'category_preferences': category_preferences,
            'reading_completion_rates': completion_rates,
            'engagement_metrics': engagement_metrics,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        conn.close()
        return report

    except sqlite3.Error as e:
        logging.error(f"Error generating user activity report: {e}")
        conn.close()
        return None


def generate_analytics_dashboard():
    """Generate comprehensive analytics dashboard"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to view analytics.")
        return

    if not (auth.check_permission('view_reports') or auth.check_permission('generate_reports')):
        print("You don't have permission to view analytics.")
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    print("\n" + "="*80)
    print("                    LIBRARY ANALYTICS DASHBOARD")
    print("="*80)

    try:
        # Current status overview
        cursor.execute('''
        SELECT
            COUNT(*) as total_books,
            COALESCE(SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END), 0) as available,
            COALESCE(SUM(CASE WHEN status = 'checked_out' THEN 1 ELSE 0 END), 0) as checked_out,
            COALESCE(SUM(CASE WHEN status = 'reserved' THEN 1 ELSE 0 END), 0) as reserved,
            COALESCE(SUM(CASE WHEN status IN ('lost', 'damaged') THEN 1 ELSE 0 END), 0) as unavailable
        FROM books
        ''')

        book_stats = cursor.fetchone()
        total_books = book_stats[0]

        print(f"\n📊 COLLECTION OVERVIEW")
        print(f"Total Books: {total_books:,}")
        if total_books > 0:
            print(f"Available: {book_stats[1]:,} ({book_stats[1]/total_books*100:.1f}%)")
            print(f"Checked Out: {book_stats[2]:,} ({book_stats[2]/total_books*100:.1f}%)")
            print(f"Reserved: {book_stats[3]:,}")
            print(f"Unavailable: {book_stats[4]:,}")
        else:
            print("No books in the collection yet.")

        # Active loans and reservations
        cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status IN ("active", "overdue")')
        active_loans = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM book_reservations WHERE status = "active"')
        active_reservations = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status = "overdue"')
        overdue_count = cursor.fetchone()[0]

        print(f"\n🔄 CIRCULATION STATUS")
        print(f"Active Loans: {active_loans:,}")
        print(f"Overdue Items: {overdue_count:,}")
        print(f"Active Reservations: {active_reservations:,}")

        # Top categories
        cursor.execute('''
        SELECT category, COUNT(*) as count
        FROM books
        GROUP BY category
        ORDER BY count DESC
        LIMIT 5
        ''')

        top_categories = cursor.fetchall()

        print(f"\n📚 TOP CATEGORIES")
        for i, (category, count) in enumerate(top_categories, 1):
            print(f"{i}. {category}: {count:,} books")

        # Most active users
        cursor.execute('''
        SELECT user_id, COUNT(*) as loan_count
        FROM book_loans
        WHERE checkout_date >= date('now', '-30 days')
        GROUP BY user_id
        ORDER BY loan_count DESC
        LIMIT 5
        ''')

        active_users = cursor.fetchall()

        print(f"\n👥 MOST ACTIVE USERS (Last 30 days)")
        for i, (user_id, count) in enumerate(active_users, 1):
            print(f"{i}. {user_id}: {count:,} checkouts")

        # Reading level distribution
        cursor.execute('''
        SELECT reading_level, COUNT(*) as count
        FROM books
        WHERE reading_level IS NOT NULL
        GROUP BY reading_level
        ORDER BY count DESC
        ''')

        reading_levels = cursor.fetchall()

        print(f"\n📖 READING LEVEL DISTRIBUTION")
        for level, count in reading_levels:
            print(f"{level}: {count:,} books")

        # Monthly circulation trends
        cursor.execute('''
        SELECT strftime('%Y-%m', checkout_date) as month, COUNT(*) as checkouts
        FROM book_loans
        WHERE checkout_date >= date('now', '-6 months')
        GROUP BY month
        ORDER BY month DESC
        LIMIT 6
        ''')

        monthly_trends = cursor.fetchall()

        print(f"\n📈 CIRCULATION TRENDS (Last 6 months)")
        for month, checkouts in monthly_trends:
            print(f"{month}: {checkouts:,} checkouts")

        # Achievement summary
        cursor.execute('''
        SELECT achievement_type, COUNT(*) as count
        FROM user_achievements
        WHERE earned_date >= date('now', '-30 days')
        GROUP BY achievement_type
        ORDER BY count DESC
        ''')

        achievements = cursor.fetchall()

        if achievements:
            print(f"\n🏆 RECENT ACHIEVEMENTS (Last 30 days)")
            for achievement_type, count in achievements:
                print(f"{achievement_type.replace('_', ' ').title()}: {count:,}")

        # System alerts
        alerts = []

        if overdue_count > 0:
            alerts.append(f"⚠️  {overdue_count} overdue items need attention")

        cursor.execute('SELECT COUNT(*) FROM books WHERE status = "damaged"')
        damaged_count = cursor.fetchone()[0]
        if damaged_count > 0:
            alerts.append(f"🔧 {damaged_count} books need repair")

        cursor.execute('SELECT COUNT(*) FROM book_requests WHERE status = "pending"')
        pending_requests = cursor.fetchone()[0]
        if pending_requests > 0:
            alerts.append(f"📝 {pending_requests} book requests pending")

        if alerts:
            print(f"\n🚨 SYSTEM ALERTS")
            for alert in alerts:
                print(f"   {alert}")

        print("="*80)

        # Offer to export detailed report
        export_choice = input("\nGenerate detailed analytics report? (y/n): ").strip().lower()

        if export_choice == 'y':
            generate_detailed_analytics_report()

    except sqlite3.Error as e:
        print(f"Error generating analytics: {e}")

    conn.close()


def generate_detailed_analytics_report():
    """Generate comprehensive analytics report with visualizations"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"library_analytics_report_{timestamp}.html"

        # Collect comprehensive data
        analytics_data = {}

        # Collection statistics
        cursor.execute('''
        SELECT category,
               COUNT(*) as total,
               SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available,
               SUM(CASE WHEN status = 'checked_out' THEN 1 ELSE 0 END) as checked_out,
               AVG(acquisition_cost) as avg_cost
        FROM books
        GROUP BY category
        ORDER BY total DESC
        ''')
        analytics_data['category_stats'] = cursor.fetchall()

        # Circulation patterns
        cursor.execute('''
        SELECT strftime('%Y-%m', checkout_date) as month,
               COUNT(*) as checkouts,
               COUNT(DISTINCT user_id) as unique_users,
               COUNT(DISTINCT book_id) as unique_books
        FROM book_loans
        WHERE checkout_date >= date('now', '-12 months')
        GROUP BY month
        ORDER BY month
        ''')
        analytics_data['monthly_circulation'] = cursor.fetchall()

        # User engagement
        cursor.execute('''
        SELECT user_id,
               COUNT(*) as total_loans,
               AVG(reading_progress) as avg_progress,
               SUM(fine_amount) as total_fines
        FROM book_loans
        GROUP BY user_id
        HAVING total_loans >= 3
        ORDER BY total_loans DESC
        LIMIT 20
        ''')
        analytics_data['top_users'] = cursor.fetchall()

        # Popular books
        cursor.execute('''
        SELECT b.title, b.author, b.category,
               COUNT(bl.loan_id) as loan_count,
               AVG(COALESCE(r.rating, 0)) as avg_rating
        FROM books b
        LEFT JOIN book_loans bl ON b.book_id = bl.book_id
        LEFT JOIN book_reviews r ON b.book_id = r.book_id AND r.status = 'approved'
        GROUP BY b.book_id
        HAVING loan_count > 0
        ORDER BY loan_count DESC
        LIMIT 15
        ''')
        analytics_data['popular_books'] = cursor.fetchall()

        # Generate HTML report
        html_content = generate_html_analytics_report(analytics_data)

        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"✅ Detailed analytics report generated: {report_filename}")

        conn.close()

    except Exception as e:
        logging.error(f"Error generating detailed analytics: {e}")
        print(f"Error generating report: {e}")


def generate_html_analytics_report(data):
    """Generate HTML analytics report"""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Library Analytics Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .header {{ background: #2c3e50; color: white; padding: 20px; text-align: center; }}
            .section {{ margin: 30px 0; padding: 20px; border: 1px solid #ddd; }}
            .chart {{ width: 100%; height: 400px; margin: 20px 0; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .metric {{ display: inline-block; margin: 10px; padding: 15px; background: #ecf0f1; border-radius: 5px; }}
        </style>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    </head>
    <body>
        <div class="header">
            <h1>📚 Library Analytics Report</h1>
            <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>

        <div class="section">
            <h2>📊 Collection Overview by Category</h2>
            <table>
                <tr>
                    <th>Category</th>
                    <th>Total Books</th>
                    <th>Available</th>
                    <th>Checked Out</th>
                    <th>Avg Cost</th>
                </tr>
    """

    for row in data['category_stats']:
        html += f"""
                <tr>
                    <td>{row[0]}</td>
                    <td>{row[1]}</td>
                    <td>{row[2]}</td>
                    <td>{row[3]}</td>
                    <td>${row[4]:.2f if row[4] else 0}</td>
                </tr>
        """

    html += """
            </table>
        </div>

        <div class="section">
            <h2>📈 Monthly Circulation Trends</h2>
            <canvas id="circulationChart" class="chart"></canvas>
        </div>

        <div class="section">
            <h2>👥 Top Active Users</h2>
            <table>
                <tr>
                    <th>User ID</th>
                    <th>Total Loans</th>
                    <th>Avg Reading Progress</th>
                    <th>Total Fines</th>
                </tr>
    """

    for row in data['top_users']:
        html += f"""
                <tr>
                    <td>{row[0]}</td>
                    <td>{row[1]}</td>
                    <td>{row[2]:.1f}%</td>
                    <td>${row[3]:.2f}</td>
                </tr>
        """

    html += """
            </table>
        </div>

        <div class="section">
            <h2>⭐ Most Popular Books</h2>
            <table>
                <tr>
                    <th>Title</th>
                    <th>Author</th>
                    <th>Category</th>
                    <th>Loan Count</th>
                    <th>Avg Rating</th>
                </tr>
    """

    for row in data['popular_books']:
        html += f"""
                <tr>
                    <td>{row[0]}</td>
                    <td>{row[1]}</td>
                    <td>{row[2]}</td>
                    <td>{row[3]}</td>
                    <td>{row[4]:.1f if row[4] else 'N/A'}</td>
                </tr>
        """

    # Add JavaScript for charts
    months = [row[0] for row in data['monthly_circulation']]
    checkouts = [row[1] for row in data['monthly_circulation']]

    html += f"""
            </table>
        </div>

        <script>
            // Circulation chart
            const ctx = document.getElementById('circulationChart').getContext('2d');
            new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: {months},
                    datasets: [{{
                        label: 'Monthly Checkouts',
                        data: {checkouts},
                        borderColor: 'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        tension: 0.1
                    }}]
                }},
                options: {{
                    responsive: true,
                    scales: {{
                        y: {{
                            beginAtZero: true
                        }}
                    }}
                }}
            }});
        </script>
    </body>
    </html>
    """

    return html


def generate_enhanced_reports():
    """Generate enhanced library reports"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to generate reports.")
        return

    if not (auth.check_permission('generate_reports') or auth.check_permission('view_reports')):
        print("You don't have permission to generate reports.")
        return

    print("\nEnhanced Report Generator:")
    print("=========================")
    print("1. Circulation Report")
    print("2. Collection Analysis Report")
    print("3. User Activity Report")
    print("4. Overdue Items Report")
    print("5. Popular Books Report")
    print("6. Reading Level Analysis")
    print("7. Financial Report")
    print("8. Custom Report Builder")
    print("9. Return to menu")

    choice = input("Select report type (1-9): ").strip()

    if choice == '9':
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if choice == '1':
            # Circulation Report
            print("\nCirculation Report Options:")
            print("1. Monthly circulation summary")
            print("2. Daily circulation details")
            print("3. User circulation patterns")

            sub_choice = input("Select option (1-3): ").strip()

            if sub_choice == '1':
                # Monthly summary
                cursor.execute('''
                SELECT strftime('%Y-%m', checkout_date) as month,
                       COUNT(*) as total_checkouts,
                       COUNT(DISTINCT user_id) as unique_users,
                       COUNT(DISTINCT book_id) as unique_books,
                       AVG(julianday(COALESCE(return_date, date('now'))) - julianday(checkout_date)) as avg_loan_days
                FROM book_loans
                WHERE checkout_date >= date('now', '-12 months')
                GROUP BY month
                ORDER BY month DESC
                ''')

                data = cursor.fetchall()

                report_content = "MONTHLY CIRCULATION SUMMARY\n"
                report_content += "=" * 50 + "\n\n"
                report_content += f"{'Month':<8} {'Checkouts':<10} {'Users':<8} {'Books':<8} {'Avg Days':<10}\n"
                report_content += "-" * 50 + "\n"

                for row in data:
                    month, checkouts, users, books, avg_days = row
                    avg_days_str = f"{avg_days:.1f}" if avg_days else "N/A"
                    report_content += f"{month:<8} {checkouts:<10} {users:<8} {books:<8} {avg_days_str:<10}\n"

                filename = f"circulation_monthly_{timestamp}.txt"

            elif sub_choice == '2':
                # Daily details
                start_date = input("Start date (YYYY-MM-DD): ").strip()
                end_date = input("End date (YYYY-MM-DD): ").strip()

                cursor.execute('''
                SELECT date(checkout_date) as day,
                       COUNT(*) as checkouts,
                       COUNT(CASE WHEN return_date IS NOT NULL THEN 1 END) as returns
                FROM book_loans
                WHERE date(checkout_date) BETWEEN ? AND ?
                GROUP BY day
                ORDER BY day
                ''', (start_date, end_date))

                data = cursor.fetchall()

                report_content = f"DAILY CIRCULATION DETAILS ({start_date} to {end_date})\n"
                report_content += "=" * 50 + "\n\n"
                report_content += f"{'Date':<12} {'Checkouts':<10} {'Returns':<10}\n"
                report_content += "-" * 50 + "\n"

                for day, checkouts, returns in data:
                    report_content += f"{day:<12} {checkouts:<10} {returns:<10}\n"

                filename = f"circulation_daily_{timestamp}.txt"

            # Write report to file
            with open(filename, 'w') as f:
                f.write(report_content)

            print(f"✅ Circulation report generated: {filename}")

        elif choice == '2':
            # Collection Analysis Report
            cursor.execute('''
            SELECT category,
                   COUNT(*) as total_books,
                   SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) as available,
                   SUM(CASE WHEN status = 'checked_out' THEN 1 ELSE 0 END) as checked_out,
                   ROUND(AVG(acquisition_cost), 2) as avg_cost,
                   COUNT(DISTINCT author) as unique_authors
            FROM books
            GROUP BY category
            ORDER BY total_books DESC
            ''')

            collection_data = cursor.fetchall()

            # Get overall statistics
            cursor.execute('''
            SELECT COUNT(*) as total,
                   SUM(acquisition_cost) as total_value,
                   MIN(year_published) as oldest_year,
                   MAX(year_published) as newest_year
            FROM books
            ''')

            overall_stats = cursor.fetchone()

            report_content = "COLLECTION ANALYSIS REPORT\n"
            report_content += "=" * 80 + "\n\n"
            report_content += "OVERALL STATISTICS:\n"
            report_content += f"Total Books: {overall_stats[0]:,}\n"
            report_content += f"Total Value: ${overall_stats[1]:,.2f}\n" if overall_stats[1] else "Total Value: Not calculated\n"
            report_content += f"Publication Range: {overall_stats[2]} - {overall_stats[3]}\n\n"

            report_content += "CATEGORY BREAKDOWN:\n"
            report_content += f"{'Category':<20} {'Total':<8} {'Avail':<8} {'Out':<8} {'Avg Cost':<10} {'Authors':<8}\n"
            report_content += "-" * 80 + "\n"

            for row in collection_data:
                category, total, available, checked_out, avg_cost, authors = row
                avg_cost_str = f"${avg_cost:.2f}" if avg_cost else "N/A"
                report_content += f"{category[:19]:<20} {total:<8} {available:<8} {checked_out:<8} {avg_cost_str:<10} {authors:<8}\n"

            filename = f"collection_analysis_{timestamp}.txt"

            with open(filename, 'w') as f:
                f.write(report_content)

            print(f"✅ Collection analysis report generated: {filename}")

        elif choice == '3':
            # User Activity Report
            days_back = int(input("Number of days to analyze (default 30): ").strip() or 30)

            cursor.execute('''
            SELECT user_id,
                   COUNT(*) as total_loans,
                   COUNT(CASE WHEN status = 'returned' THEN 1 END) as returned,
                   COUNT(CASE WHEN status = 'overdue' THEN 1 END) as overdue,
                   SUM(fine_amount) as total_fines,
                   AVG(reading_progress) as avg_progress
            FROM book_loans
            WHERE checkout_date >= date('now', '-' || ? || ' days')
            GROUP BY user_id
            HAVING total_loans > 0
            ORDER BY total_loans DESC
            LIMIT 50
            ''', (days_back,))

            user_data = cursor.fetchall()

            report_content = f"USER ACTIVITY REPORT (Last {days_back} days)\n"
            report_content += "=" * 80 + "\n\n"
            report_content += f"{'User ID':<15} {'Loans':<8} {'Returned':<10} {'Overdue':<8} {'Fines':<10} {'Avg Progress':<12}\n"
            report_content += "-" * 80 + "\n"

            for row in user_data:
                user_id, loans, returned, overdue, fines, progress = row
                fines_str = f"${fines:.2f}" if fines else "$0.00"
                progress_str = f"{progress:.1f}%" if progress else "N/A"
                report_content += f"{user_id:<15} {loans:<8} {returned:<10} {overdue:<8} {fines_str:<10} {progress_str:<12}\n"

            filename = f"user_activity_{timestamp}.txt"

            with open(filename, 'w') as f:
                f.write(report_content)

            print(f"✅ User activity report generated: {filename}")

        elif choice == '4':
            # Overdue Items Report
            cursor.execute('''
            SELECT bl.user_id, bl.book_id, b.title, bl.due_date,
                   julianday('now') - julianday(bl.due_date) as days_overdue,
                   bl.fine_amount
            FROM book_loans bl
            JOIN books b ON bl.book_id = b.book_id
            WHERE bl.status = 'overdue'
            ORDER BY days_overdue DESC
            ''')

            overdue_data = cursor.fetchall()

            report_content = "OVERDUE ITEMS REPORT\n"
            report_content += "=" * 80 + "\n\n"
            report_content += f"Total Overdue Items: {len(overdue_data)}\n\n"
            report_content += f"{'User ID':<15} {'Book ID':<10} {'Title':<25} {'Due Date':<12} {'Days':<6} {'Fine':<8}\n"
            report_content += "-" * 80 + "\n"

            total_fines = 0
            for row in overdue_data:
                user_id, book_id, title, due_date, days_overdue, fine = row
                title_display = title[:24] if len(title) > 25 else title
                fine_str = f"${fine:.2f}" if fine else "$0.00"
                total_fines += fine if fine else 0

                report_content += f"{user_id:<15} {book_id:<10} {title_display:<25} {due_date[:10]:<12} {int(days_overdue):<6} {fine_str:<8}\n"

            report_content += "-" * 80 + "\n"
            report_content += f"Total Outstanding Fines: ${total_fines:.2f}\n"

            filename = f"overdue_report_{timestamp}.txt"

            with open(filename, 'w') as f:
                f.write(report_content)

            print(f"✅ Overdue items report generated: {filename}")

        elif choice == '5':
            # Popular Books Report
            cursor.execute('''
            SELECT b.book_id, b.title, b.author, b.category,
                   COUNT(bl.loan_id) as loan_count,
                   AVG(COALESCE(r.rating, 0)) as avg_rating,
                   COUNT(r.review_id) as review_count
            FROM books b
            LEFT JOIN book_loans bl ON b.book_id = bl.book_id
            LEFT JOIN book_reviews r ON b.book_id = r.book_id AND r.status = 'approved'
            GROUP BY b.book_id
            HAVING loan_count > 0
            ORDER BY loan_count DESC
            LIMIT 25
            ''')

            popular_data = cursor.fetchall()

            report_content = "POPULAR BOOKS REPORT (Top 25)\n"
            report_content += "=" * 90 + "\n\n"
            report_content += f"{'Rank':<4} {'Book ID':<8} {'Title':<25} {'Author':<20} {'Loans':<6} {'Rating':<8} {'Reviews':<7}\n"
            report_content += "-" * 90 + "\n"

            for i, row in enumerate(popular_data, 1):
                book_id, title, author, category, loans, rating, reviews = row
                title_display = title[:24] if len(title) > 25 else title
                author_display = author[:19] if len(author) > 20 else author
                rating_str = f"{rating:.1f}/5" if rating > 0 else "N/A"

                report_content += f"{i:<4} {book_id:<8} {title_display:<25} {author_display:<20} {loans:<6} {rating_str:<8} {reviews:<7}\n"

            filename = f"popular_books_{timestamp}.txt"

            with open(filename, 'w') as f:
                f.write(report_content)

            print(f"✅ Popular books report generated: {filename}")

        # FIXED: Log the report generation using get_current_user_id() helper function
        log_audit_event(get_current_user_id(), f"Generated report type {choice}", "reports")
    except sqlite3.Error as e:
        print(f"Error generating report: {e}")

    conn.close()


def generate_library_statistics_export():
   """Generate comprehensive statistics export"""
   auth = get_auth()

   if not auth or not auth.current_user:
       print("You must be logged in to export statistics.")
       return

   if not auth.check_permission('generate_reports'):
       print("You don't have permission to export statistics.")
       return

   try:
       timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
       export_filename = f"library_statistics_export_{timestamp}.json"

       # Generate comprehensive statistics
       stats = {
           'export_info': {
               'generated_at': datetime.now().isoformat(),
               'generated_by': get_current_user_id(),
               'system_version': '2.0.0'
           },
           'collection_stats': {},
           'circulation_stats': {},
           'user_stats': {},
           'system_stats': {}
       }

       conn = get_db_connection()
       cursor = conn.cursor()

       # Collection statistics
       cursor.execute('SELECT COUNT(*) FROM books')
       stats['collection_stats']['total_books'] = cursor.fetchone()[0]

       cursor.execute('SELECT COUNT(DISTINCT author) FROM books')
       stats['collection_stats']['unique_authors'] = cursor.fetchone()[0]

       cursor.execute('SELECT COUNT(DISTINCT category) FROM books')
       stats['collection_stats']['unique_categories'] = cursor.fetchone()[0]

       cursor.execute('SELECT category, COUNT(*) FROM books GROUP BY category')
       stats['collection_stats']['books_by_category'] = dict(cursor.fetchall())

       # Circulation statistics
       cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status IN ("active", "overdue")')
       stats['circulation_stats']['active_loans'] = cursor.fetchone()[0]

       cursor.execute('SELECT COUNT(*) FROM book_loans WHERE checkout_date >= date("now", "-30 days")')
       stats['circulation_stats']['monthly_checkouts'] = cursor.fetchone()[0]

       cursor.execute('SELECT COUNT(*) FROM book_reservations WHERE status = "active"')
       stats['circulation_stats']['active_reservations'] = cursor.fetchone()[0]

       # User statistics
       cursor.execute('SELECT COUNT(DISTINCT user_id) FROM book_loans WHERE checkout_date >= date("now", "-30 days")')
       stats['user_stats']['active_users_monthly'] = cursor.fetchone()[0]

       cursor.execute('SELECT COUNT(*) FROM book_reviews WHERE status = "approved"')
       stats['user_stats']['total_reviews'] = cursor.fetchone()[0]

       cursor.execute('SELECT COUNT(*) FROM reading_lists WHERE is_public = 1')
       stats['user_stats']['public_reading_lists'] = cursor.fetchone()[0]

       # System statistics
       cursor.execute('SELECT COUNT(*) FROM audit_log WHERE timestamp >= datetime("now", "-24 hours")')
       stats['system_stats']['daily_activities'] = cursor.fetchone()[0]

       cursor.execute('SELECT COUNT(*) FROM digital_library')
       stats['system_stats']['digital_resources'] = cursor.fetchone()[0]

       conn.close()

       # Export to JSON file
       with open(export_filename, 'w') as f:
           json.dump(stats, f, indent=2, default=str)

       print(f"✅ Statistics exported to: {export_filename}")

       log_audit_event(get_current_user_id(),
                      f"Exported library statistics to {export_filename}",
                      "system")

   except Exception as e:
       logging.error(f"Error exporting statistics: {e}")
       print(f"Error exporting statistics: {e}")


def library_statistics_dashboard():
    """Display comprehensive library statistics"""
    auth = get_auth()

    if not auth or not auth.current_user:
        print("You must be logged in to view statistics.")
        return

    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    print("\n" + "="*80)
    print("                    LIBRARY STATISTICS DASHBOARD")
    print("="*80)

    try:
        # Collection Statistics
        cursor.execute('SELECT COUNT(*) FROM books')
        total_books = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(DISTINCT author) FROM books')
        unique_authors = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(DISTINCT category) FROM books')
        unique_categories = cursor.fetchone()[0]

        cursor.execute('SELECT SUM(acquisition_cost) FROM books WHERE acquisition_cost > 0')
        total_value = cursor.fetchone()[0] or 0

        print(f"\n📚 COLLECTION OVERVIEW")
        print(f"Total Books: {total_books:,}")
        print(f"Unique Authors: {unique_authors:,}")
        print(f"Categories: {unique_categories}")
        print(f"Collection Value: ${total_value:,.2f}")

        # Circulation Statistics
        cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status IN ("active", "overdue")')
        active_loans = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM book_loans WHERE checkout_date >= date("now", "-30 days")')
        monthly_checkouts = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM book_loans WHERE status = "overdue"')
        overdue_books = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM book_reservations WHERE status = "active"')
        active_reservations = cursor.fetchone()[0]

        print(f"\n🔄 CIRCULATION STATISTICS")
        print(f"Active Loans: {active_loans:,}")
        print(f"Monthly Checkouts: {monthly_checkouts:,}")
        print(f"Overdue Items: {overdue_books:,}")
        print(f"Active Reservations: {active_reservations:,}")

        # User Engagement
        cursor.execute('SELECT COUNT(DISTINCT user_id) FROM book_loans WHERE checkout_date >= date("now", "-30 days")')
        active_users = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM book_reviews WHERE status = "approved"')
        total_reviews = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM reading_lists WHERE is_public = 1')
        public_lists = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM user_achievements WHERE earned_date >= date("now", "-30 days")')
        recent_achievements = cursor.fetchone()[0]

        print(f"\n👥 USER ENGAGEMENT")
        print(f"Active Users (30 days): {active_users:,}")
        print(f"Book Reviews: {total_reviews:,}")
        print(f"Public Reading Lists: {public_lists:,}")
        print(f"Recent Achievements: {recent_achievements:,}")

        # System Health
        cursor.execute('SELECT COUNT(*) FROM audit_log WHERE timestamp >= datetime("now", "-24 hours")')
        daily_activities = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM notification_queue WHERE sent = 0')
        pending_notifications = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM book_requests WHERE status = "pending"')
        pending_requests = cursor.fetchone()[0]

        print(f"\n⚙️  SYSTEM HEALTH")
        print(f"Daily Activities: {daily_activities:,}")
        print(f"Pending Notifications: {pending_notifications:,}")
        print(f"Pending Book Requests: {pending_requests:,}")

        # Performance Metrics
        if total_books > 0:
            circulation_rate = (active_loans / total_books) * 100
            print(f"\n📊 PERFORMANCE METRICS")
            print(f"Circulation Rate: {circulation_rate:.1f}%")

            if monthly_checkouts > 0:
                avg_daily_checkouts = monthly_checkouts / 30
                print(f"Avg Daily Checkouts: {avg_daily_checkouts:.1f}")

        print("="*80)

    except sqlite3.Error as e:
        print(f"Error generating statistics: {e}")

    conn.close()


def generate_reports():
    """Generate library reports (calls enhanced version)"""
    generate_enhanced_reports()


