from education_system.university_system.infrastructure.database.db import get_connection
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np

from .app import auth


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
