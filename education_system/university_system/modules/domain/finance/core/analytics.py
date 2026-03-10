from __future__ import annotations

from datetime import datetime, timedelta
import numpy as np
import schedule
import threading
import time
from education_system.university_system.infrastructure.database.db import sqlite3

from education_system.university_system.modules.domain.finance.core.finance_context import get_connection
from education_system.university_system.modules.domain.finance.core.security_automation import send_email_notification
from education_system.university_system.modules.domain.finance.reporting.revenue_analytics import view_student_collection_detail
from education_system.university_system.modules.domain.finance.billing.fee_structure import calculate_late_fees, update_exchange_rates
from education_system.university_system.modules.domain.finance.core.security_automation import (
    detect_payment_fraud,
    send_automated_notifications,
)

def calculate_growth_rate(revenues):
    """Calculate average monthly growth rate"""
    if len(revenues) < 2:
        return 0

    growth_rates = []
    for i in range(1, len(revenues)):
        if revenues[i-1] > 0:
            growth_rate = ((revenues[i] - revenues[i-1]) / revenues[i-1]) * 100
            growth_rates.append(growth_rate)

    return np.mean(growth_rates) if growth_rates else 0

def calculate_seasonal_factors(historical_data):
    """Calculate seasonal adjustment factors"""
    seasonal_factors = {}

    # Group by month
    monthly_data = {}
    for month_str, revenue in historical_data:
        month_num = int(month_str.split('-')[1])
        if month_num not in monthly_data:
            monthly_data[month_num] = []
        monthly_data[month_num].append(revenue)

    # Calculate average for each month
    overall_avg = np.mean([revenue for _, revenue in historical_data])

    for month_num in range(1, 13):
        if month_num in monthly_data:
            month_avg = np.mean(monthly_data[month_num])
            seasonal_factors[month_num] = month_avg / overall_avg
        else:
            seasonal_factors[month_num] = 1.0  # No seasonal adjustment

    return seasonal_factors

def analyze_fee_structure_impact():
    """Analyze impact of different fee structures"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get potential revenue by course based on current enrollment
        cursor.execute('''
        SELECT s.course, COUNT(*) as enrollment, AVG(pf.amount) as avg_fee
        FROM students s
        JOIN program_fees pf ON s.course = pf.course
        JOIN fee_types ft ON pf.fee_type_id = ft.fee_type_id
        WHERE s.status = 'active' AND ft.fee_name LIKE '%Tuition%'
        GROUP BY s.course
        ''')

        impact_analysis = {}

        for course, enrollment, avg_fee in cursor.fetchall():
            # Calculate potential revenue with 10% fee increase
            current_revenue = enrollment * avg_fee
            increased_revenue = enrollment * (avg_fee * 1.1)
            impact = increased_revenue - current_revenue

            impact_analysis[course] = impact

        conn.close()
        return impact_analysis

    except Exception as e:
        print(f"Error in fee structure analysis: {e}")
        return None

def view_overdue_accounts():
    """View all overdue student accounts"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get overdue accounts
        cursor.execute('''
        SELECT sf.student_id, s.first_name, s.last_name, s.email_address, s.phone_number,
               SUM(sf.amount) - COALESCE(SUM(pa.amount), 0) as total_overdue,
               MIN(sf.due_date) as earliest_due_date,
               COUNT(sf.student_fee_id) as overdue_fees_count,
               MAX(julianday('now') - julianday(sf.due_date)) as days_overdue
        FROM student_fees sf
        JOIN students s ON sf.student_id = s.student_id
        LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
        WHERE sf.status IN ('unpaid', 'partial')
        AND date(sf.due_date) < date('now')
        GROUP BY sf.student_id
        HAVING total_overdue > 0
        ORDER BY days_overdue DESC, total_overdue DESC
        ''')

        overdue_accounts = cursor.fetchall()

        if not overdue_accounts:
            print("No overdue accounts found.")
            conn.close()
            return

        print(f"\nOverdue Accounts ({len(overdue_accounts)} students):")
        print("=" * 130)
        print(f"{'Student ID':<12} {'Name':<25} {'Email':<30} {'Amount Due':<12} {'Days Overdue':<12} {'Fees Count':<11}")
        print("-" * 130)

        total_overdue = 0

        for account in overdue_accounts:
            student_id, first_name, last_name, email, phone, amount_due, earliest_due, fee_count, days_overdue = account
            student_name = f"{first_name} {last_name}"

            print(f"{student_id:<12} {student_name:<25} {email:<30} £{amount_due:<11.2f} {int(days_overdue):<12} {fee_count:<11}")
            total_overdue += amount_due

        print("-" * 130)
        print(f"Total Overdue Amount: £{total_overdue:,.2f}")
        print("=" * 130)

        # Categorize by overdue period
        print(f"\nOverdue Analysis:")

        cursor.execute('''
        SELECT 
            CASE 
                WHEN MAX(julianday('now') - julianday(sf.due_date)) <= 30 THEN '1-30 days'
                WHEN MAX(julianday('now') - julianday(sf.due_date)) <= 60 THEN '31-60 days'
                WHEN MAX(julianday('now') - julianday(sf.due_date)) <= 90 THEN '61-90 days'
                ELSE '90+ days'
            END as overdue_period,
            COUNT(DISTINCT sf.student_id) as student_count,
            SUM(sf.amount) - COALESCE(SUM(pa.amount), 0) as total_amount
        FROM student_fees sf
        LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
        WHERE sf.status IN ('unpaid', 'partial')
        AND date(sf.due_date) < date('now')
        GROUP BY sf.student_id
        HAVING total_amount > 0
        ''')

        # Re-execute with proper grouping
        cursor.execute('''
        SELECT 
            CASE 
                WHEN days_overdue <= 30 THEN '1-30 days'
                WHEN days_overdue <= 60 THEN '31-60 days'
                WHEN days_overdue <= 90 THEN '61-90 days'
                ELSE '90+ days'
            END as overdue_period,
            COUNT(*) as student_count,
            SUM(total_overdue) as total_amount
        FROM (
            SELECT sf.student_id,
                   SUM(sf.amount) - COALESCE(SUM(pa.amount), 0) as total_overdue,
                   MAX(julianday('now') - julianday(sf.due_date)) as days_overdue
            FROM student_fees sf
            LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
            WHERE sf.status IN ('unpaid', 'partial')
            AND date(sf.due_date) < date('now')
            GROUP BY sf.student_id
            HAVING total_overdue > 0
        ) overdue_summary
        GROUP BY overdue_period
        ORDER BY 
            CASE overdue_period
                WHEN '1-30 days' THEN 1
                WHEN '31-60 days' THEN 2
                WHEN '61-90 days' THEN 3
                ELSE 4
            END
        ''')

        period_analysis = cursor.fetchall()

        for period, count, amount in period_analysis:
            print(f"{period}: {count} students, £{amount:,.2f}")

        # Detailed view option
        view_student = input("\nView detailed account? Enter Student ID (or press Enter to skip): ").strip()

        if view_student:
            view_student_collection_detail(view_student)

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def assign_case_to_agency(case_id):
    """Assign collection case to external agency"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get available agencies
        cursor.execute('''
        SELECT agency_id, agency_name, commission_rate, minimum_amount
        FROM collection_agencies
        WHERE is_active = 1
        ORDER BY agency_name
        ''')

        agencies = cursor.fetchall()

        if not agencies:
            print("No active collection agencies available.")
            return

        print("\nAvailable Collection Agencies:")
        for i, (agency_id, name, commission, min_amount) in enumerate(agencies, 1):
            print(f"{i}. {name} - {commission}% commission (min: £{min_amount:.2f})")

        agency_choice = input("Select agency (number): ").strip()
        try:
            agency_index = int(agency_choice) - 1
            if 0 <= agency_index < len(agencies):
                selected_agency = agencies[agency_index]
                agency_id = selected_agency[0]
            else:
                print("Invalid selection.")
                return
        except ValueError:
            print("Invalid input.")
            return

        # Assign case
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        UPDATE collection_cases 
        SET agency_id = ?, case_status = 'assigned', assigned_date = ?, updated_at = ?
        WHERE case_id = ?
        ''', (agency_id, now, now, case_id))

        conn.commit()

        print(f"Case {case_id} assigned to {selected_agency[1]}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def start_background_scheduler():
    """Start background scheduler for automated tasks"""
    def run_scheduled_tasks():
        # Schedule automated notifications
        schedule.every().day.at("09:00").do(send_automated_notifications)
        schedule.every().day.at("18:00").do(send_automated_notifications)

        # Schedule late fee calculations
        schedule.every().day.at("02:00").do(calculate_late_fees)

        # Schedule fraud detection
        schedule.every().day.at("03:00").do(detect_payment_fraud)

        # Schedule exchange rate updates
        schedule.every().day.at("06:00").do(update_exchange_rates)

        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

    # Run scheduler in background thread
    scheduler_thread = threading.Thread(target=run_scheduled_tasks, daemon=True)
    scheduler_thread.start()
    print("Background scheduler started for automated finance tasks.")

def generate_enrollment_projections():
    """Generate enrollment-based financial projections"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\n📊 Enrollment-Based Financial Projections")
        print("=" * 50)

        # Get current enrollment by course
        cursor.execute('''
        SELECT course, COUNT(*) as current_enrollment, 
               AVG(CASE WHEN sf.amount IS NOT NULL THEN sf.amount ELSE 0 END) as avg_fees
        FROM students s
        LEFT JOIN student_fees sf ON s.student_id = sf.student_id
        WHERE s.status = 'active'
        GROUP BY course
        ORDER BY current_enrollment DESC
        ''')

        enrollment_data = cursor.fetchall()

        if not enrollment_data:
            print("No enrollment data found.")
            return

        print("Current Enrollment Analysis:")
        print("-" * 50)
        print(f"{'Course':<25} {'Students':<10} {'Avg Fees':<12} {'Total Revenue':<15}")
        print("-" * 50)

        total_students = 0
        total_revenue = 0
        projections = []

        for course, enrollment, avg_fees in enrollment_data:
            course_revenue = enrollment * (avg_fees or 0)
            total_students += enrollment
            total_revenue += course_revenue

            print(f"{course:<25} {enrollment:<10} £{avg_fees or 0:<11.2f} £{course_revenue:<14.2f}")

            # Project growth scenarios
            conservative_growth = enrollment * 1.05  # 5% growth
            moderate_growth = enrollment * 1.10      # 10% growth
            optimistic_growth = enrollment * 1.15    # 15% growth

            projections.append({
                'course': course,
                'current': enrollment,
                'conservative': conservative_growth,
                'moderate': moderate_growth,
                'optimistic': optimistic_growth,
                'avg_fees': avg_fees or 0
            })

        print("-" * 50)
        print(f"{'Total':<25} {total_students:<10} {'':<12} £{total_revenue:<14.2f}")
        print("=" * 50)

        # Projection scenarios
        print("\nEnrollment Growth Projections (Next Academic Year):")
        print("=" * 80)
        print(f"{'Course':<20} {'Current':<8} {'Conservative':<12} {'Moderate':<10} {'Optimistic':<10}")
        print(f"{'':<20} {'':<8} {'(+5%)':<12} {'(+10%)':<10} {'(+15%)':<10}")
        print("-" * 80)

        conservative_total = 0
        moderate_total = 0
        optimistic_total = 0

        for proj in projections:
            print(f"{proj['course']:<20} {proj['current']:<8} {proj['conservative']:<12.0f} {proj['moderate']:<10.0f} {proj['optimistic']:<10.0f}")

            conservative_total += proj['conservative'] * proj['avg_fees']
            moderate_total += proj['moderate'] * proj['avg_fees']
            optimistic_total += proj['optimistic'] * proj['avg_fees']

        print("-" * 80)
        print("\nRevenue Projections:")
        print(f"Conservative Scenario: £{conservative_total:,.2f} (+{((conservative_total - total_revenue) / total_revenue * 100) if total_revenue > 0 else 0:.1f}%)")
        print(f"Moderate Scenario:     £{moderate_total:,.2f} (+{((moderate_total - total_revenue) / total_revenue * 100) if total_revenue > 0 else 0:.1f}%)")
        print(f"Optimistic Scenario:   £{optimistic_total:,.2f} (+{((optimistic_total - total_revenue) / total_revenue * 100) if total_revenue > 0 else 0:.1f}%)")

        conn.close()

    except Exception as e:
        print(f"Error generating enrollment projections: {e}")

def generate_cash_flow_analysis():
    """Generate cash flow analysis and projections"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\n💰 Cash Flow Analysis")
        print("=" * 50)

        # Get monthly cash flow data for the past 12 months
        cursor.execute('''
        SELECT strftime('%Y-%m', payment_date) as month,
               SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as inflows
        FROM payments
        WHERE payment_date >= date('now', '-12 months') AND status = 'completed'
        GROUP BY month
        ORDER BY month
        ''')

        cash_inflows = cursor.fetchall()

        # Estimate monthly outflows (simplified - would need expense tracking)
        print("Monthly Cash Flow Analysis (Last 12 Months):")
        print("-" * 60)
        print(f"{'Month':<10} {'Inflows':<15} {'Net Flow':<15} {'Cumulative':<15}")
        print("-" * 60)

        cumulative = 0
        monthly_data = []

        for month, inflows in cash_inflows:
            # Estimate outflows as 70% of inflows (would use actual expense data in practice)
            estimated_outflows = inflows * 0.7
            net_flow = inflows - estimated_outflows
            cumulative += net_flow

            monthly_data.append({
                'month': month,
                'inflows': inflows,
                'outflows': estimated_outflows,
                'net_flow': net_flow,
                'cumulative': cumulative
            })

            print(f"{month:<10} £{inflows:<14.2f} £{net_flow:<14.2f} £{cumulative:<14.2f}")

        print("-" * 60)

        # Cash flow projections
        if monthly_data:
            avg_net_flow = sum(item['net_flow'] for item in monthly_data) / len(monthly_data)

            print(f"\nCash Flow Projections (Next 6 Months):")
            print(f"Average Monthly Net Flow: £{avg_net_flow:.2f}")
            print("-" * 40)

            current_date = datetime.now()
            projected_cumulative = cumulative

            for i in range(6):
                future_date = current_date + timedelta(days=30*i)
                month_str = future_date.strftime('%Y-%m')
                projected_cumulative += avg_net_flow

                print(f"{month_str}: £{projected_cumulative:.2f}")

        conn.close()

    except Exception as e:
        print(f"Error generating cash flow analysis: {e}")

def generate_risk_analysis():
    """Generate financial risk analysis"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\n⚠️  Financial Risk Analysis")
        print("=" * 50)

        # Calculate key risk metrics

        # 1. Outstanding Debt Risk
        cursor.execute('''
        SELECT SUM(sf.amount) - COALESCE(SUM(pa.amount), 0) as total_outstanding,
               COUNT(DISTINCT sf.student_id) as students_with_debt
        FROM student_fees sf
        LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
        WHERE sf.status IN ('unpaid', 'partial')
        ''')

        debt_risk = cursor.fetchone()
        total_outstanding, students_with_debt = debt_risk
        total_outstanding = total_outstanding or 0

        # 2. Overdue Debt Risk
        cursor.execute('''
        SELECT SUM(sf.amount) - COALESCE(SUM(pa.amount), 0) as overdue_amount,
               COUNT(DISTINCT sf.student_id) as overdue_students
        FROM student_fees sf
        LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
        WHERE sf.status IN ('unpaid', 'partial') AND date(sf.due_date) < date('now')
        ''')

        overdue_risk = cursor.fetchone()
        overdue_amount, overdue_students = overdue_risk
        overdue_amount = overdue_amount or 0

        # 3. Collection Risk by Age
        cursor.execute('''
        SELECT 
            CASE 
                WHEN julianday('now') - julianday(sf.due_date) <= 30 THEN 'Low Risk (0-30 days)'
                WHEN julianday('now') - julianday(sf.due_date) <= 90 THEN 'Medium Risk (31-90 days)'
                ELSE 'High Risk (90+ days)'
            END as risk_category,
            SUM(sf.amount) - COALESCE(SUM(pa.amount), 0) as amount,
            COUNT(DISTINCT sf.student_id) as students
        FROM student_fees sf
        LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
        WHERE sf.status IN ('unpaid', 'partial') AND date(sf.due_date) < date('now')
        GROUP BY risk_category
        ''')

        collection_risk = cursor.fetchall()

        print("Debt Risk Analysis:")
        print("-" * 30)
        print(f"Total Outstanding Debt: £{total_outstanding:,.2f}")
        print(f"Students with Debt: {students_with_debt or 0}")
        print(f"Overdue Amount: £{overdue_amount:,.2f}")
        print(f"Students Overdue: {overdue_students or 0}")

        if total_outstanding > 0:
            overdue_percentage = (overdue_amount / total_outstanding) * 100
            print(f"Overdue Percentage: {overdue_percentage:.1f}%")

        print("\nCollection Risk by Age:")
        print("-" * 40)
        for risk_category, amount, students in collection_risk:
            print(f"{risk_category}: £{amount:,.2f} ({students} students)")

        # 4. Revenue Concentration Risk
        cursor.execute('''
        SELECT s.course, 
               SUM(sf.amount) as course_revenue,
               COUNT(DISTINCT s.student_id) as students
        FROM students s
        JOIN student_fees sf ON s.student_id = sf.student_id
        WHERE s.status = 'active'
        GROUP BY s.course
        ORDER BY course_revenue DESC
        ''')

        course_revenue = cursor.fetchall()

        if course_revenue:
            total_revenue = sum(row[1] for row in course_revenue)

            print("\nRevenue Concentration Risk:")
            print("-" * 40)
            for course, revenue, students in course_revenue:
                percentage = (revenue / total_revenue * 100) if total_revenue > 0 else 0
                print(f"{course}: {percentage:.1f}% of revenue ({students} students)")

        # 5. Risk Score Summary
        risk_score = 0

        # Add points for high overdue percentage
        if total_outstanding > 0:
            overdue_pct = (overdue_amount / total_outstanding) * 100
            if overdue_pct > 20:
                risk_score += 30
            elif overdue_pct > 10:
                risk_score += 15

        # Add points for high concentration
        if course_revenue:
            max_course_pct = max((revenue / total_revenue * 100) for course, revenue, students in course_revenue) if total_revenue > 0 else 0
            if max_course_pct > 50:
                risk_score += 25
            elif max_course_pct > 30:
                risk_score += 15

        print(f"\nOverall Financial Risk Score: {risk_score}/100")
        if risk_score >= 50:
            print("⚠️  HIGH RISK - Immediate attention required")
        elif risk_score >= 25:
            print("⚡ MEDIUM RISK - Monitor closely")
        else:
            print("✅ LOW RISK - Stable financial position")

        conn.close()

    except Exception as e:
        print(f"Error generating risk analysis: {e}")

def generate_scenario_planning():
    """Generate scenario planning analysis"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\n🎯 Financial Scenario Planning")
        print("=" * 50)

        # Get current baseline data
        cursor.execute('''
        SELECT SUM(amount) as total_revenue
        FROM payments
        WHERE strftime('%Y', payment_date) = strftime('%Y', 'now') AND status = 'completed'
        ''')

        current_revenue = cursor.fetchone()[0] or 0

        cursor.execute('''
        SELECT COUNT(*) as total_students
        FROM students
        WHERE status = 'active'
        ''')

        current_students = cursor.fetchone()[0] or 0

        print("Baseline Scenario (Current Year):")
        print("-" * 30)
        print(f"Current Revenue: £{current_revenue:,.2f}")
        print(f"Current Students: {current_students}")

        # Define scenarios
        scenarios = [
            {
                'name': 'Conservative',
                'description': 'Economic downturn, enrollment decline',
                'enrollment_change': -0.10,  # -10%
                'fee_change': 0.02,          # +2%
                'collection_rate': 0.85      # 85%
            },
            {
                'name': 'Baseline',
                'description': 'Current conditions continue',
                'enrollment_change': 0.05,   # +5%
                'fee_change': 0.03,          # +3%
                'collection_rate': 0.92      # 92%
            },
            {
                'name': 'Optimistic',
                'description': 'Economic growth, expansion',
                'enrollment_change': 0.15,   # +15%
                'fee_change': 0.05,          # +5%
                'collection_rate': 0.95      # 95%
            }
        ]

        print("\nScenario Analysis (Next Academic Year):")
        print("=" * 70)
        print(f"{'Scenario':<12} {'Students':<10} {'Avg Revenue':<15} {'Collection':<12} {'Net Revenue':<15}")
        print("-" * 70)

        avg_revenue_per_student = current_revenue / current_students if current_students > 0 else 0

        for scenario in scenarios:
            projected_students = current_students * (1 + scenario['enrollment_change'])
            projected_avg_revenue = avg_revenue_per_student * (1 + scenario['fee_change'])
            gross_revenue = projected_students * projected_avg_revenue
            net_revenue = gross_revenue * scenario['collection_rate']

            print(f"{scenario['name']:<12} {projected_students:<10.0f} £{projected_avg_revenue:<14.2f} {scenario['collection_rate']*100:<11.0f}% £{net_revenue:<14.2f}")

        print("-" * 70)

        # Risk factors analysis
        print("\nKey Risk Factors to Monitor:")
        print("-" * 40)
        print("• Economic conditions affecting student enrollment")
        print("• Competition from other institutions")
        print("• Government funding changes")
        print("• Student satisfaction and retention rates")
        print("• Payment collection efficiency")
        print("• Course demand fluctuations")

        # Recommendations
        print("\nRecommendations:")
        print("-" * 20)
        print("• Diversify revenue streams")
        print("• Implement early warning systems for at-risk students")
        print("• Maintain flexible fee structures")
        print("• Strengthen collection procedures")
        print("• Monitor competitor activities")

        conn.close()

    except Exception as e:
        print(f"Error generating scenario planning: {e}")

def recovery_rate_analysis():
    """Analyze recovery rates by different criteria"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(f"\nRecovery Rate Analysis:")
        print("=" * 60)

        # Recovery by debt amount ranges
        print("Recovery Rate by Debt Amount:")
        print("-" * 40)

        debt_ranges = [
            (0, 500, "£0 - £500"),
            (500, 1000, "£500 - £1,000"),
            (1000, 2000, "£1,000 - £2,000"),
            (2000, 5000, "£2,000 - £5,000"),
            (5000, float('inf'), "£5,000+")
        ]

        for min_debt, max_debt, range_label in debt_ranges:
            if max_debt == float('inf'):
                cursor.execute('''
                SELECT COUNT(*), SUM(total_debt), SUM(amount_collected)
                FROM collection_cases
                WHERE total_debt >= ?
                ''', (min_debt,))
            else:
                cursor.execute('''
                SELECT COUNT(*), SUM(total_debt), SUM(amount_collected)
                FROM collection_cases
                WHERE total_debt >= ? AND total_debt < ?
                ''', (min_debt, max_debt))

            result = cursor.fetchone()
            if result and result[0] > 0:
                cases, debt, collected = result
                collected = collected or 0
                recovery_rate = (collected / debt * 100) if debt > 0 else 0
                print(f"{range_label:<15}: {recovery_rate:>6.1f}% ({cases} cases)")

        # Recovery by case age
        print("\nRecovery Rate by Case Age:")
        print("-" * 40)

        cursor.execute('''
        SELECT 
            CASE 
                WHEN julianday('now') - julianday(created_at) <= 30 THEN '0-30 days'
                WHEN julianday('now') - julianday(created_at) <= 60 THEN '31-60 days'
                WHEN julianday('now') - julianday(created_at) <= 90 THEN '61-90 days'
                ELSE '90+ days'
            END as age_range,
            COUNT(*) as cases,
            SUM(total_debt) as debt,
            SUM(amount_collected) as collected
        FROM collection_cases
        GROUP BY age_range
        ORDER BY 
            CASE age_range
                WHEN '0-30 days' THEN 1
                WHEN '31-60 days' THEN 2
                WHEN '61-90 days' THEN 3
                ELSE 4
            END
        ''')

        age_analysis = cursor.fetchall()

        for age_range, cases, debt, collected in age_analysis:
            collected = collected or 0
            recovery_rate = (collected / debt * 100) if debt > 0 else 0
            print(f"{age_range:<12}: {recovery_rate:>6.1f}% ({cases} cases)")

        print("=" * 60)

        conn.close()

    except Exception as e:
        print(f"Error in recovery rate analysis: {e}")

def update_actual_amounts(budget_id):
    """Update actual amounts in budget"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get revenue actuals from payments
        cursor.execute('''
        UPDATE budget_line_items 
        SET actual_amount = (
            SELECT COALESCE(SUM(p.amount), 0)
            FROM payments p
            JOIN students s ON p.student_id = s.student_id
            WHERE p.status = 'completed'
            AND strftime('%Y', p.payment_date) = (
                SELECT substr(academic_year, 1, 4)
                FROM budget_plans
                WHERE budget_id = ?
            )
        ),
        variance = actual_amount - budgeted_amount,
        updated_at = ?
        WHERE budget_id = ? 
        AND category_id IN (
            SELECT category_id FROM budget_categories 
            WHERE category_type = 'revenue'
        )
        ''', (budget_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), budget_id))

        conn.commit()
        print("Actual amounts updated from financial data.")
        conn.close()

    except Exception as e:
        print(f"Error updating actual amounts: {e}")
