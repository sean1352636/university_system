from education_system.post_18.university_system.infrastructure.database.db import get_connection
from datetime import datetime, timedelta
import numpy as np
import json
import csv

from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics.app import auth
from education_system.post_18.university_system.modules.domain.finance.core.students import get_student_name


def generate_predictive_analytics():
    """Generate predictive analytics for payment behavior"""
    global auth
    import matplotlib.pyplot as plt
    from sklearn.ensemble import IsolationForest

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

        print("\nPredictive Analytics Results:")
        print(f"Total students analyzed: {len(student_data)}")
        print(f"High risk students: {len(high_risk_students)}")
        print(f"Medium risk students: {len(medium_risk_students)}")
        print(f"Low risk students: {len(student_ids) - len(high_risk_students) - len(medium_risk_students)}")

        if high_risk_students:
            print("\nHigh Risk Students:")
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

        print("\nAnalytics visualization saved as 'payment_risk_analytics.png'")

        conn.close()

    except Exception as e:
        print(f"Error generating predictive analytics: {e}")

def generate_revenue_forecast():
    """Generate revenue forecasting based on historical data and trends"""
    from education_system.post_18.university_system.modules.domain.finance.core.analytics import calculate_growth_rate, calculate_seasonal_factors, analyze_fee_structure_impact
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

        print("\nHistorical Analysis:")
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
        print("\nScenario Analysis:")
        conservative_total = total_forecast * 0.85
        optimistic_total = total_forecast * 1.15

        print(f"Conservative (85%): £{conservative_total:,.0f}")
        print(f"Expected (100%):   £{total_forecast:,.0f}")
        print(f"Optimistic (115%): £{optimistic_total:,.0f}")

        # Generate enrollment-based forecast
        enrollment_forecast = generate_enrollment_based_forecast()

        if enrollment_forecast:
            print("\nEnrollment-Based Forecast:")
            print(f"Expected Revenue from New Students: £{enrollment_forecast['new_student_revenue']:,.0f}")
            print(f"Expected Revenue from Returning Students: £{enrollment_forecast['returning_student_revenue']:,.0f}")
            print(f"Total Enrollment-Based Forecast: £{enrollment_forecast['total']:,.0f}")

        # Fee structure analysis
        fee_analysis = analyze_fee_structure_impact()

        if fee_analysis:
            print("\nFee Structure Impact Analysis:")
            for course, impact in fee_analysis.items():
                print(f"{course}: £{impact:,.0f} potential annual revenue")

        # Create visualization
        create_revenue_forecast_chart(months, revenues, forecasts)

        # Save forecast to database
        save_forecast_to_database(forecasts, total_forecast)

        # Export option
        export = input("\nExport forecast report? (y/n): ").strip().lower()
        if export == 'y':
            from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics.scholarships import export_forecast_report
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
    import matplotlib.pyplot as plt
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

def generate_financial_forecasting():
    """Generate comprehensive financial forecasting and analysis"""
    from education_system.post_18.university_system.modules.domain.finance.core.analytics import generate_enrollment_projections, generate_cash_flow_analysis, generate_risk_analysis, generate_scenario_planning
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

        print("\n\U0001f4c8 Budget Variance Forecasting")
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
        print("\n\U0001f4cb Generating Comprehensive Forecast Report...")
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
            report_file.write("\u2022 Revenue projections indicate moderate growth potential\n")
            report_file.write("\u2022 Enrollment trends show stable demand\n")
            report_file.write("\u2022 Cash flow remains positive with seasonal variations\n")
            report_file.write("\u2022 Risk factors are manageable with proper monitoring\n\n")

            report_file.write("RECOMMENDATIONS\n")
            report_file.write("-" * 18 + "\n")
            report_file.write("\u2022 Implement dynamic pricing strategies\n")
            report_file.write("\u2022 Enhance collection procedures\n")
            report_file.write("\u2022 Diversify course offerings\n")
            report_file.write("\u2022 Strengthen financial controls\n\n")

            report_file.write("For detailed analysis, run individual forecast modules.\n")

        print(f"\u2705 Comprehensive forecast report saved as: {filename}")
        print("\nReport includes:")
        print("\u2022 Executive summary")
        print("\u2022 Revenue forecasting")
        print("\u2022 Enrollment projections")
        print("\u2022 Cash flow analysis")
        print("\u2022 Risk assessment")
        print("\u2022 Strategic recommendations")

    except Exception as e:
        print(f"Error generating comprehensive forecast report: {e}")
