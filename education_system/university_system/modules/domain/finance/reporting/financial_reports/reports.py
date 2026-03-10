from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import pandas as pd

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.finance.reporting.revenue_analytics import (
    generate_financial_forecasting, generate_budget_variance_report, generate_financial_dashboard as financial_dashboard
)

from . import _common
from .alerts import FinancialAlertSystem
from .ml import PaymentPredictionML, AnomalyDetector
from .forecasting import CashFlowForecaster
from .analyzers import StudentLifecycleAnalyzer, ComparativeAnalyzer


def generate_advanced_financial_forecasting():
    """Enhanced financial forecasting with ML and advanced analytics"""
    auth = _common.auth

    if not auth or not auth.current_user:
        print("You must be logged in to access advanced financial forecasting.")
        return

    if not auth.check_permission('manage_finances'):
        print("You don't have permission to access advanced financial forecasting.")
        return

    print("\nAdvanced Financial Forecasting & Analytics")
    print("=" * 60)

    # Initialize components
    cash_flow_forecaster = CashFlowForecaster()
    payment_predictor = PaymentPredictionML()
    anomaly_detector = AnomalyDetector()
    lifecycle_analyzer = StudentLifecycleAnalyzer()

    # 1. Traditional forecasting (from original function)
    print("1. Generating traditional forecast...")
    generate_financial_forecasting()

    # 2. Advanced cash flow forecasting
    print("\n2. Advanced Cash Flow Forecasting...")
    cash_flow_data = cash_flow_forecaster.generate_cash_flow_forecast(12)

    if cash_flow_data:
        print("\nCash Flow Forecast (Next 12 Months):")
        print("-" * 60)

        total_forecast = sum(item['forecast_amount'] for item in cash_flow_data['forecast_data'])
        print(f"Total Forecasted Revenue: £{total_forecast:,.2f}")
        print(f"Monthly Baseline: £{cash_flow_data['baseline_monthly']:,.2f}")
        print(f"Trend: £{cash_flow_data['trend']:,.2f} per month")

        # Show monthly breakdown
        for item in cash_flow_data['forecast_data'][:6]:  # Show first 6 months
            print(f"{item['month']}: £{item['forecast_amount']:,.2f} (Confidence: {item['confidence']:.1%})")

        # Create cash flow visualization
        months = [item['month'] for item in cash_flow_data['forecast_data']]
        amounts = [item['forecast_amount'] for item in cash_flow_data['forecast_data']]
        confidence = [item['confidence'] for item in cash_flow_data['forecast_data']]

        plt.figure(figsize=(14, 8))

        # Main forecast line
        plt.subplot(2, 2, 1)
        plt.plot(months, amounts, marker='o', linewidth=2)
        plt.fill_between(months,
                        [a * (1 - (1-c)*0.2) for a, c in zip(amounts, confidence)],
                        [a * (1 + (1-c)*0.2) for a, c in zip(amounts, confidence)],
                        alpha=0.3)
        plt.title('Cash Flow Forecast')
        plt.xlabel('Month')
        plt.ylabel('Amount (£)')
        plt.xticks(rotation=45)

        # Cumulative cash flow
        cumulative = [item['cumulative_cash'] for item in cash_flow_data['forecast_data']]
        plt.subplot(2, 2, 2)
        plt.plot(months, cumulative, marker='s', color='green')
        plt.title('Cumulative Cash Flow')
        plt.xlabel('Month')
        plt.ylabel('Cumulative Amount (£)')
        plt.xticks(rotation=45)

        # Seasonal factors
        seasonal_factors = [item['seasonal_factor'] for item in cash_flow_data['forecast_data']]
        plt.subplot(2, 2, 3)
        plt.bar(months, seasonal_factors, color='orange', alpha=0.7)
        plt.title('Seasonal Factors')
        plt.xlabel('Month')
        plt.ylabel('Factor')
        plt.xticks(rotation=45)

        # Confidence levels
        plt.subplot(2, 2, 4)
        plt.plot(months, [c*100 for c in confidence], marker='^', color='red')
        plt.title('Forecast Confidence')
        plt.xlabel('Month')
        plt.ylabel('Confidence (%)')
        plt.xticks(rotation=45)

        plt.tight_layout()
        plt.savefig('advanced_cash_flow_forecast.png', dpi=300, bbox_inches='tight')
        plt.close()

        print("Advanced cash flow chart saved as 'advanced_cash_flow_forecast.png'")

    # 3. Payment risk prediction
    print("\n3. Payment Risk Analysis...")
    high_risk_students = payment_predictor.predict_payment_risk()

    if high_risk_students:
        print(f"\nHigh-Risk Students (Top 10):")
        print("-" * 60)

        for student in high_risk_students[:10]:
            print(f"{student['student_name']} ({student['student_id']}): "
                  f"{student['risk_level']} Risk ({student['risk_score']:.2%}) - "
                  f"£{student['total_fees']:,.2f} total fees")

        # Create risk distribution chart
        risk_levels = [s['risk_level'] for s in high_risk_students]
        risk_counts = pd.Series(risk_levels).value_counts()

        plt.figure(figsize=(10, 6))
        plt.subplot(1, 2, 1)
        plt.pie(risk_counts.values, labels=risk_counts.index, autopct='%1.1f%%')
        plt.title('Payment Risk Distribution')

        # Risk vs fees scatter
        plt.subplot(1, 2, 2)
        risk_scores = [s['risk_score'] for s in high_risk_students]
        total_fees = [s['total_fees'] for s in high_risk_students]
        plt.scatter(risk_scores, total_fees, alpha=0.6)
        plt.xlabel('Risk Score')
        plt.ylabel('Total Fees (£)')
        plt.title('Risk Score vs Total Fees')

        plt.tight_layout()
        plt.savefig('payment_risk_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()

        print("Payment risk analysis chart saved as 'payment_risk_analysis.png'")

    # 4. Anomaly detection
    print("\n4. Payment Anomaly Detection...")
    anomalies = anomaly_detector.detect_payment_anomalies()

    if anomalies:
        print(f"\nDetected {len(anomalies)} payment anomalies:")
        print("-" * 60)

        for anomaly in anomalies[:5]:  # Show top 5
            print(f"{anomaly['student_name']}: £{anomaly['amount']:,.2f} on {anomaly['payment_date']}")
            print(f"  Reason: {anomaly['anomaly_reason']}")

    # 5. Student lifecycle analysis
    print("\n5. Student Lifecycle Analysis...")
    lifecycle_data = lifecycle_analyzer.analyze_student_lifecycle()

    if lifecycle_data:
        print(f"\nLifecycle Summary:")
        print(f"Total Students: {lifecycle_data['summary_stats']['total_students']}")
        print(f"Average Collection Rate: {lifecycle_data['summary_stats']['avg_collection_rate']:.1f}%")
        print(f"High-Risk Students: {lifecycle_data['summary_stats']['high_risk_students']}")

        # Create lifecycle visualization
        lifecycle_summary = lifecycle_data['student_data'].groupby('lifecycle_stage').agg({
            'collection_rate': 'mean',
            'student_id': 'count'
        }).round(1)

        plt.figure(figsize=(12, 8))

        # Collection rate by lifecycle stage
        plt.subplot(2, 2, 1)
        lifecycle_summary['collection_rate'].plot(kind='bar')
        plt.title('Collection Rate by Lifecycle Stage')
        plt.ylabel('Collection Rate (%)')
        plt.xticks(rotation=45)

        # Student count by lifecycle stage
        plt.subplot(2, 2, 2)
        lifecycle_summary['student_id'].plot(kind='pie', autopct='%1.1f%%')
        plt.title('Students by Lifecycle Stage')

        # Collection rate distribution
        plt.subplot(2, 2, 3)
        plt.hist(lifecycle_data['student_data']['collection_rate'], bins=20, alpha=0.7, edgecolor='black')
        plt.title('Collection Rate Distribution')
        plt.xlabel('Collection Rate (%)')
        plt.ylabel('Number of Students')

        # Scholarship vs Collection Rate
        plt.subplot(2, 2, 4)
        plt.scatter(lifecycle_data['student_data']['scholarship_percentage'],
                   lifecycle_data['student_data']['collection_rate'], alpha=0.6)
        plt.xlabel('Scholarship Percentage (%)')
        plt.ylabel('Collection Rate (%)')
        plt.title('Scholarship Impact on Collection')

        plt.tight_layout()
        plt.savefig('student_lifecycle_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()

        print("Student lifecycle analysis chart saved as 'student_lifecycle_analysis.png'")


def generate_comprehensive_budget_variance_report():
    """Enhanced budget variance with predictive analytics"""
    auth = _common.auth

    if not auth or not auth.current_user:
        print("You must be logged in to generate comprehensive budget variance reports.")
        return

    if not auth.check_permission('manage_finances'):
        print("You don't have permission to generate comprehensive budget variance reports.")
        return

    print("\nComprehensive Budget Variance & Performance Analysis")
    print("=" * 70)

    # Run original budget variance
    generate_budget_variance_report()

    # Add comparative analysis
    print("\n6. Comparative Analysis...")
    comparative_analyzer = ComparativeAnalyzer()

    # Year-over-year analysis
    yoy_data = comparative_analyzer.year_over_year_analysis()
    if yoy_data:
        print("\nYear-over-Year Performance:")
        print("-" * 40)

        for year, data in yoy_data.items():
            print(f"{year}: £{data['total_collected']:,.2f} collected "
                  f"({data['collection_rate']:.1f}% rate) - "
                  f"{data['student_count']} students")

        # Create YoY visualization
        years = list(yoy_data.keys())
        collections = [yoy_data[year]['total_collected'] for year in years]
        rates = [yoy_data[year]['collection_rate'] for year in years]

        plt.figure(figsize=(12, 6))

        plt.subplot(1, 2, 1)
        plt.bar(years, collections)
        plt.title('Revenue Collection by Year')
        plt.ylabel('Amount Collected (£)')
        plt.xticks(rotation=45)

        plt.subplot(1, 2, 2)
        plt.plot(years, rates, marker='o', linewidth=2)
        plt.title('Collection Rate Trend')
        plt.ylabel('Collection Rate (%)')
        plt.xticks(rotation=45)

        plt.tight_layout()
        plt.savefig('year_over_year_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()

        print("Year-over-year analysis chart saved as 'year_over_year_analysis.png'")

    # Department comparison
    dept_data = comparative_analyzer.department_comparison()
    if dept_data is not None and len(dept_data) > 0:
        print("\nDepartment Performance:")
        print("-" * 40)

        for _, row in dept_data.head(5).iterrows():
            print(f"{row['department']}: {row['collection_rate']:.1f}% collection rate, "
                  f"£{row['avg_fee_per_student']:,.2f} avg fee per student")

        # Create department comparison visualization
        plt.figure(figsize=(14, 10))

        # Collection rate by department
        plt.subplot(2, 2, 1)
        top_depts = dept_data.head(8)
        plt.barh(range(len(top_depts)), top_depts['collection_rate'])
        plt.yticks(range(len(top_depts)), top_depts['department'])
        plt.xlabel('Collection Rate (%)')
        plt.title('Collection Rate by Department')

        # Revenue by department
        plt.subplot(2, 2, 2)
        plt.barh(range(len(top_depts)), top_depts['total_fees'])
        plt.yticks(range(len(top_depts)), top_depts['department'])
        plt.xlabel('Total Fees (£)')
        plt.title('Revenue by Department')

        # Student count vs collection rate
        plt.subplot(2, 2, 3)
        plt.scatter(dept_data['student_count'], dept_data['collection_rate'],
                   s=dept_data['total_fees']/1000, alpha=0.6)
        plt.xlabel('Student Count')
        plt.ylabel('Collection Rate (%)')
        plt.title('Students vs Collection Rate\n(Bubble size = Revenue)')

        # Scholarship rate impact
        plt.subplot(2, 2, 4)
        plt.scatter(dept_data['scholarship_rate'], dept_data['collection_rate'], alpha=0.6)
        plt.xlabel('Scholarship Rate (%)')
        plt.ylabel('Collection Rate (%)')
        plt.title('Scholarship Impact on Collection')

        plt.tight_layout()
        plt.savefig('department_comparison_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()

        print("Department comparison chart saved as 'department_comparison_analysis.png'")


def real_time_financial_dashboard():
    """Enhanced real-time financial dashboard with live metrics"""
    auth = _common.auth

    if not auth or not auth.current_user:
        print("You must be logged in to access the real-time financial dashboard.")
        return

    if not auth.check_permission('manage_finances'):
        print("You don't have permission to access the real-time financial dashboard.")
        return

    print("\nReal-Time Financial Performance Dashboard")
    print("=" * 60)

    # Initialize alert system
    alert_system = FinancialAlertSystem()

    # Run all alert checks
    print("Running real-time monitoring checks...")
    alert_system.check_collection_rate_alert()
    alert_system.check_daily_payments()
    alert_system.check_large_payments()

    # Run original dashboard
    financial_dashboard()

    # Add real-time KPIs
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Real-time metrics
        today = datetime.now().strftime('%Y-%m-%d')
        this_week = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        this_month = datetime.now().strftime('%Y-%m-01')

        print("\nReal-Time Performance Indicators:")
        print("-" * 60)

        # Today's payments
        cursor.execute('SELECT COUNT(*), SUM(amount) FROM payments WHERE payment_date = ?', (today,))
        today_data = cursor.fetchone()
        print(f"Today's Payments: {today_data[0]} transactions, £{today_data[1] or 0:,.2f}")

        # This week's payments
        cursor.execute('SELECT COUNT(*), SUM(amount) FROM payments WHERE payment_date >= ?', (this_week,))
        week_data = cursor.fetchone()
        print(f"This Week: {week_data[0]} transactions, £{week_data[1] or 0:,.2f}")

        # This month's payments
        cursor.execute('SELECT COUNT(*), SUM(amount) FROM payments WHERE payment_date >= ?', (this_month,))
        month_data = cursor.fetchone()
        print(f"This Month: {month_data[0]} transactions, £{month_data[1] or 0:,.2f}")

        # Payment velocity (payments per day)
        cursor.execute('''
        SELECT COUNT(*) / COUNT(DISTINCT payment_date) as daily_velocity
        FROM payments
        WHERE payment_date >= date('now', '-30 days')
        ''')
        velocity = cursor.fetchone()[0] or 0
        print(f"Payment Velocity: {velocity:.1f} payments/day (30-day avg)")

        # Outstanding balance aging
        cursor.execute('''
        SELECT
            SUM(CASE WHEN julianday('now') - julianday(sf.due_date) <= 30 THEN sf.amount ELSE 0 END) as current_30,
            SUM(CASE WHEN julianday('now') - julianday(sf.due_date) BETWEEN 31 AND 60 THEN sf.amount ELSE 0 END) as days_31_60,
            SUM(CASE WHEN julianday('now') - julianday(sf.due_date) BETWEEN 61 AND 90 THEN sf.amount ELSE 0 END) as days_61_90,
            SUM(CASE WHEN julianday('now') - julianday(sf.due_date) > 90 THEN sf.amount ELSE 0 END) as over_90
        FROM student_fees sf
        WHERE sf.status != 'paid'
        ''')

        aging_data = cursor.fetchone()
        if aging_data:
            print("\nOutstanding Balance Aging:")
            print(f"  0-30 days: £{aging_data[0] or 0:,.2f}")
            print(f"  31-60 days: £{aging_data[1] or 0:,.2f}")
            print(f"  61-90 days: £{aging_data[2] or 0:,.2f}")
            print(f"  90+ days: £{aging_data[3] or 0:,.2f}")

        # Recent alerts
        cursor.execute('''
        SELECT alert_type, message, created_date
        FROM financial_alerts
        WHERE created_date >= date('now', '-7 days')
        ORDER BY created_date DESC
        LIMIT 5
        ''')

        recent_alerts = cursor.fetchall()
        if recent_alerts:
            print("\nRecent Alerts (Last 7 Days):")
            for alert_type, message, created_date in recent_alerts:
                print(f"  {created_date}: [{alert_type}] {message}")

        # Create comprehensive dashboard visualization
        plt.figure(figsize=(16, 12))

        # Payment trend (last 30 days)
        cursor.execute('''
        SELECT payment_date, SUM(amount), COUNT(*)
        FROM payments
        WHERE payment_date >= date('now', '-30 days')
        GROUP BY payment_date
        ORDER BY payment_date
        ''')

        daily_payments = cursor.fetchall()
        if daily_payments:
            dates = [row[0] for row in daily_payments]
            amounts = [row[1] for row in daily_payments]
            counts = [row[2] for row in daily_payments]

            plt.subplot(3, 3, 1)
            plt.plot(dates, amounts, marker='o')
            plt.title('Daily Payment Amounts (30 days)')
            plt.xticks(rotation=45)
            plt.ylabel('Amount (£)')

            plt.subplot(3, 3, 2)
            plt.plot(dates, counts, marker='s', color='green')
            plt.title('Daily Payment Count (30 days)')
            plt.xticks(rotation=45)
            plt.ylabel('Count')

        # Payment method distribution
        cursor.execute('''
        SELECT payment_method, COUNT(*), SUM(amount)
        FROM payments
        WHERE payment_date >= date('now', '-30 days')
        GROUP BY payment_method
        ''')

        method_data = cursor.fetchall()
        if method_data:
            methods = [row[0] for row in method_data]
            method_amounts = [row[2] for row in method_data]

            plt.subplot(3, 3, 3)
            plt.pie(method_amounts, labels=methods, autopct='%1.1f%%')
            plt.title('Payment Methods (30 days)')

        # Outstanding balance aging visualization
        if aging_data:
            aging_labels = ['0-30 days', '31-60 days', '61-90 days', '90+ days']
            aging_amounts = [aging_data[0] or 0, aging_data[1] or 0,
                           aging_data[2] or 0, aging_data[3] or 0]

            plt.subplot(3, 3, 4)
            plt.bar(aging_labels, aging_amounts, color=['green', 'yellow', 'orange', 'red'])
            plt.title('Outstanding Balance Aging')
            plt.ylabel('Amount (£)')
            plt.xticks(rotation=45)

        # Collection rate trend
        cursor.execute('''
        SELECT
            strftime('%Y-%m', sf.created_date) as month,
            SUM(sf.amount) as total,
            SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as collected
        FROM student_fees sf
        WHERE sf.created_date >= date('now', '-12 months')
        GROUP BY month
        ORDER BY month
        ''')

        monthly_collection = cursor.fetchall()
        if monthly_collection:
            months = [row[0] for row in monthly_collection]
            collection_rates = [(row[2]/row[1]*100) if row[1] > 0 else 0 for row in monthly_collection]

            plt.subplot(3, 3, 5)
            plt.plot(months, collection_rates, marker='o', linewidth=2)
            plt.title('Monthly Collection Rate Trend')
            plt.ylabel('Collection Rate (%)')
            plt.xticks(rotation=45)

        # Payment size distribution
        cursor.execute('''
        SELECT amount FROM payments WHERE payment_date >= date('now', '-90 days')
        ''')

        payment_amounts = [row[0] for row in cursor.fetchall()]
        if payment_amounts:
            plt.subplot(3, 3, 6)
            plt.hist(payment_amounts, bins=20, alpha=0.7, edgecolor='black')
            plt.title('Payment Amount Distribution')
            plt.xlabel('Amount (£)')
            plt.ylabel('Frequency')

        # Top paying students (this month)
        cursor.execute('''
        SELECT s.first_name, s.last_name, SUM(p.amount) as total_paid
        FROM payments p
        JOIN students s ON p.student_id = s.student_id
        WHERE p.payment_date >= ?
        GROUP BY s.student_id, s.first_name, s.last_name
        ORDER BY total_paid DESC
        LIMIT 10
        ''', (this_month,))

        top_payers = cursor.fetchall()
        if top_payers:
            names = [f"{row[0]} {row[1]}" for row in top_payers]
            amounts = [row[2] for row in top_payers]

            plt.subplot(3, 3, 7)
            plt.barh(range(len(names)), amounts)
            plt.yticks(range(len(names)), names)
            plt.title('Top Payers This Month')
            plt.xlabel('Amount Paid (£)')

        # Fee type performance
        cursor.execute('''
        SELECT
            ft.fee_name,
            SUM(sf.amount) as total,
            SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as collected
        FROM student_fees sf
        JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
        GROUP BY ft.fee_name
        HAVING total > 0
        ORDER BY total DESC
        LIMIT 5
        ''')

        fee_performance = cursor.fetchall()
        if fee_performance:
            fee_names = [row[0] for row in fee_performance]
            collection_rates = [(row[2]/row[1]*100) if row[1] > 0 else 0 for row in fee_performance]

            plt.subplot(3, 3, 8)
            plt.bar(fee_names, collection_rates)
            plt.title('Collection Rate by Fee Type')
            plt.ylabel('Collection Rate (%)')
            plt.xticks(rotation=45)

        # Alert frequency
        cursor.execute('''
        SELECT
            DATE(created_date) as alert_date,
            COUNT(*) as alert_count
        FROM financial_alerts
        WHERE created_date >= date('now', '-30 days')
        GROUP BY alert_date
        ORDER BY alert_date
        ''')

        alert_data = cursor.fetchall()
        if alert_data:
            alert_dates = [row[0] for row in alert_data]
            alert_counts = [row[1] for row in alert_data]

            plt.subplot(3, 3, 9)
            plt.plot(alert_dates, alert_counts, marker='o', color='red')
            plt.title('Daily Alert Frequency')
            plt.ylabel('Alert Count')
            plt.xticks(rotation=45)

        plt.tight_layout()
        plt.savefig('comprehensive_realtime_dashboard.png', dpi=300, bbox_inches='tight')
        plt.close()

        print("\nComprehensive dashboard saved as 'comprehensive_realtime_dashboard.png'")

        conn.close()

    except Exception as e:
        print(f"Error generating real-time dashboard: {e}")


def automated_reporting_system():
    """Set up automated report generation and delivery"""
    auth = _common.auth

    if not auth or not auth.current_user:
        print("You must be logged in to configure automated reporting.")
        return

    if not auth.check_permission('manage_finances'):
        print("You don't have permission to configure automated reporting.")
        return

    print("\nAutomated Financial Reporting System")
    print("=" * 50)

    # Create automated reports configuration
    report_configs = {
        'daily_summary': {
            'frequency': 'daily',
            'time': '08:00',
            'recipients': ['finance@university.edu'],
            'reports': ['daily_payments', 'collection_status', 'alerts']
        },
        'weekly_analysis': {
            'frequency': 'weekly',
            'day': 'Monday',
            'time': '09:00',
            'recipients': ['finance@university.edu', 'admin@university.edu'],
            'reports': ['payment_trends', 'risk_analysis', 'cash_flow']
        },
        'monthly_comprehensive': {
            'frequency': 'monthly',
            'day': 1,
            'time': '10:00',
            'recipients': ['finance@university.edu', 'admin@university.edu', 'board@university.edu'],
            'reports': ['full_forecast', 'budget_variance', 'comparative_analysis']
        }
    }

    print("Automated Report Configurations:")
    print("-" * 40)

    for config_name, config in report_configs.items():
        print(f"\n{config_name.replace('_', ' ').title()}:")
        print(f"  Frequency: {config['frequency']}")
        print(f"  Recipients: {', '.join(config['recipients'])}")
        print(f"  Reports: {', '.join(config['reports'])}")

    # Simulate report scheduling
    print(f"\nReport scheduling system configured.")
    print("In production, this would integrate with cron jobs or task schedulers.")

    # Create sample automated report
    print("\nGenerating sample automated daily report...")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')

        # Daily summary data
        cursor.execute('SELECT COUNT(*), SUM(amount) FROM payments WHERE payment_date = ?', (today,))
        daily_payments = cursor.fetchone()

        cursor.execute('SELECT COUNT(*) FROM student_fees WHERE status != "paid"', )
        outstanding_count = cursor.fetchone()[0]

        # Try to get alert count - handle case where table/column may not exist
        try:
            cursor.execute('SELECT COUNT(*) FROM financial_alerts WHERE DATE(created_date) = ?', (today,))
            alert_count = cursor.fetchone()[0] or 0
        except Exception:
            alert_count = 0

        # Generate automated report content
        report_content = f"""
        DAILY FINANCIAL SUMMARY - {today}
        ========================================

        Daily Payments: {daily_payments[0]} transactions, £{daily_payments[1] or 0:,.2f}
        Outstanding Fees: {outstanding_count} items
        Alerts Generated: {alert_count}

        Status: {'✓ Normal' if alert_count == 0 else '⚠ Attention Required'}

        Next Actions:
        - Review high-risk students if payment volume is low
        - Follow up on overdue accounts
        - Process any manual interventions needed

        This is an automated report. For detailed analysis,
        access the full dashboard system.
        """

        print(report_content)

        # Save automated report
        report_filename = f'automated_daily_report_{today}.txt'
        with open(report_filename, 'w') as f:
            f.write(report_content)

        print(f"Automated report saved as '{report_filename}'")

        conn.close()

    except Exception as e:
        print(f"Error generating automated report: {e}")
