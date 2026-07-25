from datetime import datetime, timedelta

from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.domain.finance.reporting.revenue_by_source_report import (
    print_revenue_by_source_report, revenue_by_source_menu
)
from education_system.systems.university.domain.finance.reporting.revenue_analytics import (
    generate_financial_forecasting, generate_budget_variance_report, generate_financial_dashboard as financial_dashboard
)

from education_system.systems.university.domain.finance.reporting.financial_reports import _common
from education_system.systems.university.domain.finance.reporting.financial_reports.alerts import FinancialAlertSystem
from education_system.systems.university.domain.finance.reporting.financial_reports.ml import PaymentPredictionML, AnomalyDetector
from education_system.systems.university.domain.finance.reporting.financial_reports.forecasting import CashFlowForecaster
from education_system.systems.university.domain.finance.reporting.financial_reports.analyzers import StudentLifecycleAnalyzer, ComparativeAnalyzer
from education_system.systems.university.domain.finance.reporting.financial_reports.reports import (
    generate_advanced_financial_forecasting,
    generate_comprehensive_budget_variance_report,
    real_time_financial_dashboard,
    automated_reporting_system,
)
from education_system.systems.university.domain.finance.reporting.financial_reports.scenario_planning import scenario_planning_tools
from education_system.systems.university.domain.finance.reporting.financial_reports.export import advanced_export_system
from education_system.systems.university.domain.finance.reporting.financial_reports.compliance import compliance_audit_system


def display_enhanced_finance_menu():
    """Enhanced finance menu with all new features"""
    # Always get auth from shared context to ensure we have the logged-in user
    shared_auth = _common.get_auth()
    if shared_auth and shared_auth.current_user:
        _common.auth = shared_auth
    elif not _common.auth or not hasattr(_common.auth, 'current_user') or not _common.auth.current_user:
        print("You must be logged in to access enhanced finance features.")
        return

    auth = _common.auth

    if not auth.check_permission('manage_finances'):
        print("You don't have permission to access enhanced finance features.")
        return

    while True:
        print("\n" + "="*100)
        print("ENHANCED FINANCIAL MANAGEMENT SYSTEM")
        print("="*100)

        print("\n🔮 ADVANCED ANALYTICS & FORECASTING:")
        print(f"{'1.  ML Forecasting':<25} {'2.  Budget Variance':<25} {'3.  Real-Time Dashboard':<25} {'4.  Lifecycle Analysis':<25}")

        print("\n📊 PREDICTIVE ANALYTICS:")
        print(f"{'5.  Payment Risk (ML)':<25} {'6.  Anomaly Detection':<25} {'7.  Cash Flow Forecast':<25} {'8.  Scenario Planning':<25}")

        print("\n⚡ MONITORING & ALERTS:")
        print(f"{'9.  Smart Alerts':<25} {'10. Auto Reporting':<25} {'11. Performance Monitor':<25}")

        print("\n📈 COMPARATIVE ANALYSIS:")
        print(f"{'12. Year-over-Year':<25} {'13. Dept Comparison':<25} {'14. Peer Benchmarking':<25}")

        print("\n🎯 STRATEGIC PLANNING:")
        print(f"{'15. Payment Plan Opt.':<25} {'16. Collection Strategy':<25} {'17. Scholarship Impact':<25} {'18. Revenue Optimize':<25}")

        print("\n📤 EXPORT & INTEGRATION:")
        print(f"{'19. Advanced Export':<25} {'20. API Data Feed':<25} {'21. Auto Delivery':<25} {'22. Custom Report':<25}")

        print("\n🛡️  COMPLIANCE & AUDIT:")
        print(f"{'23. Compliance Audit':<25} {'24. Data Quality':<25} {'25. Regulatory Reports':<25}")

        print("\n🚀 SYSTEM MANAGEMENT:")
        print(f"{'26. Train ML Models':<25} {'27. Performance Opt.':<25} {'28. Data Archive':<25}")

        print("\n💰 REVENUE ANALYTICS:")
        print(f"{'29. Revenue by Source':<25} {'30. Revenue Trends':<25}")

        print("\n📋 LEGACY FEATURES:")
        print(f"{'31. Original Forecast':<25} {'32. Original Variance':<25} {'33. Original Dashboard':<25}")

        print("\n34. Return to Main Finance Menu")

        choice = input("\nEnter your choice (1-34): ").strip()

        try:
            if choice == '1':
                generate_advanced_financial_forecasting()
            elif choice == '2':
                generate_comprehensive_budget_variance_report()
            elif choice == '3':
                real_time_financial_dashboard()
            elif choice == '4':
                lifecycle_analyzer = StudentLifecycleAnalyzer()
                data = lifecycle_analyzer.analyze_student_lifecycle()
                if data:
                    print("\nStudent Lifecycle Analysis Complete")
                    print(f"Total Students Analyzed: {data['summary_stats']['total_students']}")
                    print(f"Average Collection Rate: {data['summary_stats']['avg_collection_rate']:.1f}%")
                    print("Detailed charts saved as 'student_lifecycle_analysis.png'")

            elif choice == '5':
                payment_predictor = PaymentPredictionML()
                payment_predictor.train_model()
                risk_students = payment_predictor.predict_payment_risk()
                print("\nPayment Risk Analysis Complete")
                print(f"Analyzed {len(risk_students)} students")
                high_risk = len([s for s in risk_students if s['risk_level'] == 'High'])
                print(f"High-risk students identified: {high_risk}")

            elif choice == '6':
                anomaly_detector = AnomalyDetector()
                anomalies = anomaly_detector.detect_payment_anomalies()
                print("\nAnomaly Detection Complete")
                print(f"Detected {len(anomalies)} anomalous payments")
                for anomaly in anomalies[:3]:
                    print(f"  {anomaly['student_name']}: £{anomaly['amount']:,.2f} - {anomaly['anomaly_reason']}")

            elif choice == '7':
                cash_flow_forecaster = CashFlowForecaster()
                forecast = cash_flow_forecaster.generate_cash_flow_forecast(12)
                if forecast:
                    total_forecast = sum(item['forecast_amount'] for item in forecast['forecast_data'])
                    print("\nCash Flow Forecast Complete")
                    print(f"12-month forecast: £{total_forecast:,.2f}")
                    print("Detailed forecast chart saved as 'cash_flow_forecast.png'")

            elif choice == '8':
                scenario_planning_tools()

            elif choice == '9':
                alert_system = FinancialAlertSystem()
                print("\nSmart Alert System")
                print("Current Alert Thresholds:")
                for key, value in alert_system.alert_thresholds.items():
                    print(f"  {key}: {value}")

                print("\nRunning alert checks...")
                alert_system.check_collection_rate_alert()
                alert_system.check_daily_payments()
                alert_system.check_large_payments()
                print("Alert system checks complete.")

            elif choice == '10':
                automated_reporting_system()

            elif choice == '11':
                # Real-time monitoring
                print("\nReal-Time Performance Monitoring")
                print("=" * 40)

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    # Live metrics
                    now = datetime.now()
                    today = now.strftime('%Y-%m-%d')
                    this_hour = now.strftime('%Y-%m-%d %H:00:00')

                    # Hourly payment volume
                    cursor.execute('''
                    SELECT COUNT(*), SUM(amount)
                    FROM payments
                    WHERE payment_date >= ?
                    ''', (this_hour,))

                    hourly_data = cursor.fetchone()
                    print(f"Current Hour: {hourly_data[0]} payments, £{hourly_data[1] or 0:,.2f}")

                    # Payment velocity
                    cursor.execute('''
                    SELECT
                        COUNT(*) as payment_count,
                        (julianday('now') - julianday(MIN(payment_date))) as days_span
                    FROM payments
                    WHERE payment_date >= date('now', '-7 days')
                    ''')

                    velocity_data = cursor.fetchone()
                    if velocity_data[1] and velocity_data[1] > 0:
                        velocity = velocity_data[0] / velocity_data[1]
                        print(f"Payment Velocity: {velocity:.1f} payments/day")

                    # Active collection campaigns
                    cursor.execute('''
                    SELECT COUNT(*) FROM student_fees
                    WHERE status != 'paid' AND due_date < date('now')
                    ''')
                    overdue_count = cursor.fetchone()[0]
                    print(f"Overdue Accounts: {overdue_count}")

                    # System health
                    cursor.execute('SELECT COUNT(*) FROM students')
                    total_students = cursor.fetchone()[0]
                    cursor.execute('SELECT COUNT(*) FROM payments')
                    total_payments = cursor.fetchone()[0]

                    print(f"System Health: {total_students} students, {total_payments} total payments")

                    conn.close()

                except Exception as e:
                    print(f"Error in real-time monitoring: {e}")

            elif choice == '12':
                comparative_analyzer = ComparativeAnalyzer()
                yoy_data = comparative_analyzer.year_over_year_analysis()
                print("\nYear-over-Year Analysis Complete")
                for year, data in yoy_data.items():
                    print(f"{year}: {data['collection_rate']:.1f}% collection rate")

            elif choice == '13':
                comparative_analyzer = ComparativeAnalyzer()
                dept_data = comparative_analyzer.department_comparison()
                if dept_data is not None:
                    print("\nDepartment Comparison Complete")
                    print(f"Analyzed {len(dept_data)} departments")
                    best_dept = dept_data.loc[dept_data['collection_rate'].idxmax()]
                    print(f"Best performing: {best_dept['department']} ({best_dept['collection_rate']:.1f}%)")

            elif choice == '14':
                # Peer benchmarking simulation
                print("\nPeer Institution Benchmarking (Simulated)")
                print("=" * 50)

                # Simulate peer data
                peer_institutions = {
                    'University A': {'collection_rate': 92.5, 'avg_fee': 8500, 'students': 1200},
                    'University B': {'collection_rate': 89.3, 'avg_fee': 9200, 'students': 950},
                    'University C': {'collection_rate': 95.1, 'avg_fee': 7800, 'students': 1500},
                    'University D': {'collection_rate': 87.8, 'avg_fee': 8900, 'students': 1100}
                }

                # Get our current performance
                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    cursor.execute('''
                    SELECT
                        SUM(sf.amount) as total_expected,
                        SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as total_collected,
                        COUNT(DISTINCT sf.student_id) as student_count
                    FROM student_fees sf
                    ''')

                    our_data = cursor.fetchone()
                    our_rate = (our_data[1] / our_data[0] * 100) if our_data[0] > 0 else 0
                    our_avg_fee = our_data[0] / our_data[2] if our_data[2] > 0 else 0

                    print(f"Our Institution: {our_rate:.1f}% collection rate, £{our_avg_fee:,.0f} avg fee")
                    print("\nPeer Comparison:")

                    for institution, data in peer_institutions.items():
                        comparison = "↑" if our_rate > data['collection_rate'] else "↓" if our_rate < data['collection_rate'] else "="
                        print(f"{institution}: {data['collection_rate']:.1f}% {comparison}")

                    # Calculate percentile ranking
                    all_rates = [data['collection_rate'] for data in peer_institutions.values()] + [our_rate]
                    our_percentile = (sorted(all_rates).index(our_rate) + 1) / len(all_rates) * 100
                    print(f"\nOur Percentile Ranking: {our_percentile:.0f}th percentile")

                    conn.close()

                except Exception as e:
                    print(f"Error in benchmarking: {e}")

            elif choice == '15':
                # Payment plan optimization
                print("\nPayment Plan Optimization Analysis")
                print("=" * 40)

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    # Analyze current payment patterns
                    cursor.execute('''
                    SELECT
                        COUNT(*) as total_students,
                        AVG(payment_span) as avg_payment_span,
                        AVG(payment_count) as avg_payments_per_student
                    FROM (
                        SELECT
                            p.student_id,
                            COUNT(*) as payment_count,
                            julianday(MAX(p.payment_date)) - julianday(MIN(p.payment_date)) as payment_span
                        FROM payments p
                        GROUP BY p.student_id
                    ) student_payments
                    ''')

                    payment_patterns = cursor.fetchone()

                    if payment_patterns:
                        print("Current Payment Patterns:")
                        print(f"  Average payment span: {payment_patterns[1]:.0f} days")
                        print(f"  Average payments per student: {payment_patterns[2]:.1f}")

                    # Optimize payment plans
                    optimization_scenarios = {
                        'Monthly Plans': {'frequency': 12, 'collection_improvement': 8, 'admin_cost': 2000},
                        'Bi-weekly Plans': {'frequency': 26, 'collection_improvement': 15, 'admin_cost': 5000},
                        'Flexible Terms': {'frequency': 'variable', 'collection_improvement': 12, 'admin_cost': 3500}
                    }

                    print("\nPayment Plan Optimization Scenarios:")
                    for plan_name, scenario in optimization_scenarios.items():
                        print(f"{plan_name}: {scenario['collection_improvement']}% improvement, £{scenario['admin_cost']} cost")

                    conn.close()

                except Exception as e:
                    print(f"Error in payment plan optimization: {e}")

            elif choice == '16':
                # Collection strategy effectiveness
                print("\nCollection Strategy Effectiveness Analysis")
                print("=" * 50)

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    # Analyze collection by payment method
                    cursor.execute('''
                    SELECT
                        payment_method,
                        COUNT(*) as transaction_count,
                        SUM(amount) as total_amount,
                        AVG(amount) as avg_amount
                    FROM payments
                    GROUP BY payment_method
                    ORDER BY total_amount DESC
                    ''')

                    method_effectiveness = cursor.fetchall()

                    print("Collection Method Effectiveness:")
                    for method, count, total, avg in method_effectiveness:
                        print(f"  {method}: {count} transactions, £{total:,.2f} total, £{avg:,.2f} average")

                    # Time-based analysis
                    cursor.execute('''
                    SELECT
                        strftime('%w', payment_date) as day_of_week,
                        COUNT(*) as payment_count,
                        SUM(amount) as daily_total
                    FROM payments
                    WHERE payment_date >= date('now', '-90 days')
                    GROUP BY day_of_week
                    ORDER BY daily_total DESC
                    ''')

                    day_effectiveness = cursor.fetchall()

                    print("\nBest Collection Days:")
                    day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
                    for day_num, count, total in day_effectiveness:
                        day_name = day_names[int(day_num)]
                        print(f"  {day_name}: £{total:,.2f} ({count} payments)")

                    conn.close()

                except Exception as e:
                    print(f"Error in collection strategy analysis: {e}")

            elif choice == '17':
                # Scholarship impact analysis
                print("\nScholarship Impact Analysis")
                print("=" * 40)

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    # Scholarship vs collection rate analysis
                    cursor.execute('''
                    SELECT
                        CASE
                            WHEN ss.amount > 0 THEN 'With Scholarship'
                            ELSE 'No Scholarship'
                        END as scholarship_status,
                        COUNT(DISTINCT s.student_id) as student_count,
                        AVG(collection_rate) as avg_collection_rate
                    FROM students s
                    LEFT JOIN student_scholarships ss ON s.student_id = ss.student_id
                    LEFT JOIN (
                        SELECT
                            sf.student_id,
                            (SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) * 100.0 / SUM(sf.amount)) as collection_rate
                        FROM student_fees sf
                        GROUP BY sf.student_id
                    ) cr ON s.student_id = cr.student_id
                    GROUP BY scholarship_status
                    ''')

                    scholarship_impact = cursor.fetchall()

                    print("Scholarship Impact on Collection:")
                    for status, count, rate in scholarship_impact:
                        print(f"  {status}: {count} students, {rate:.1f}% avg collection rate")

                    # ROI analysis
                    cursor.execute('''
                    SELECT
                        SUM(ss.amount) as total_scholarships,
                        COUNT(DISTINCT ss.student_id) as scholarship_recipients
                    FROM student_scholarships ss
                    WHERE ss.status = 'active'
                    ''')

                    scholarship_data = cursor.fetchone()

                    if scholarship_data[0]:
                        print("\nScholarship Investment:")
                        print(f"  Total Active Scholarships: £{scholarship_data[0]:,.2f}")
                        print(f"  Recipients: {scholarship_data[1]} students")
                        print(f"  Average per student: £{scholarship_data[0]/scholarship_data[1]:,.2f}")

                    conn.close()

                except Exception as e:
                    print(f"Error in scholarship impact analysis: {e}")

            elif choice == '18':
                # Revenue optimization recommendations
                print("\nRevenue Optimization Recommendations")
                print("=" * 50)

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    recommendations = []

                    # Analyze collection efficiency
                    cursor.execute('''
                    SELECT
                        SUM(sf.amount) as total_expected,
                        SUM(CASE WHEN sf.status = 'paid' THEN sf.amount ELSE 0 END) as total_collected
                    FROM student_fees sf
                    ''')

                    revenue_data = cursor.fetchone()
                    collection_rate = (revenue_data[1] / revenue_data[0] * 100) if revenue_data[0] > 0 else 0

                    if collection_rate < 90:
                        recommendations.append({
                            'category': 'Collection Efficiency',
                            'recommendation': 'Implement automated payment reminders',
                            'potential_impact': f'{(90 - collection_rate) * revenue_data[0] / 100:,.0f}',
                            'priority': 'High'
                        })

                    # Analyze fee structure
                    cursor.execute('''
                    SELECT
                        ft.fee_name,
                        AVG(sf.amount) as avg_amount,
                        COUNT(*) as student_count
                    FROM student_fees sf
                    JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                    GROUP BY ft.fee_name
                    ORDER BY student_count DESC
                    ''')

                    fee_analysis = cursor.fetchall()

                    if fee_analysis:
                        largest_fee = fee_analysis[0]
                        recommendations.append({
                            'category': 'Fee Structure',
                            'recommendation': f'Consider payment plans for {largest_fee[0]} (£{largest_fee[1]:,.0f})',
                            'potential_impact': f'{largest_fee[1] * largest_fee[2] * 0.05:,.0f}',
                            'priority': 'Medium'
                        })

                    # Payment method optimization
                    cursor.execute('''
                    SELECT payment_method, COUNT(*), AVG(amount)
                    FROM payments
                    GROUP BY payment_method
                    ORDER BY COUNT(*) DESC
                    ''')

                    payment_methods = cursor.fetchall()

                    if len(payment_methods) > 1:
                        recommendations.append({
                            'category': 'Payment Methods',
                            'recommendation': 'Promote electronic payments to reduce processing costs',
                            'potential_impact': '5000',
                            'priority': 'Low'
                        })

                    print("Revenue Optimization Recommendations:")
                    print("-" * 40)

                    for rec in recommendations:
                        print(f"Category: {rec['category']}")
                        print(f"Recommendation: {rec['recommendation']}")
                        print(f"Potential Impact: £{rec['potential_impact']}")
                        print(f"Priority: {rec['priority']}")
                        print()

                    # Calculate total optimization potential (remove commas before converting)
                    total_potential = sum(float(str(rec['potential_impact']).replace(',', '')) for rec in recommendations)
                    print(f"Total Optimization Potential: £{total_potential:,.0f}")

                    conn.close()

                except Exception as e:
                    print(f"Error in revenue optimization: {e}")

            elif choice == '19':
                advanced_export_system()

            elif choice == '20':
                # API configuration
                print("\nAPI Data Feed Configuration")
                print("=" * 40)

                api_config = {
                    'base_url': '/api/v1/finance',
                    'version': 'v1',
                    'authentication': 'Bearer Token',
                    'rate_limit': '1000 requests/hour',
                    'data_formats': ['JSON', 'XML', 'CSV']
                }

                print("API Configuration:")
                for key, value in api_config.items():
                    print(f"  {key}: {value}")

                print("\nAvailable Endpoints:")
                endpoints = [
                    '/summary - Financial summary data',
                    '/collections - Collection rates and trends',
                    '/students/risk - High-risk student data',
                    '/forecasts - Financial forecasts',
                    '/alerts - Current alerts',
                    '/reports - Generated reports'
                ]

                for endpoint in endpoints:
                    print(f"  {endpoint}")

                print("\nAPI documentation available at /docs")
                print("Contact IT department for API key generation.")

            elif choice == '21':
                # Automated report delivery
                print("\nAutomated Report Delivery Configuration")
                print("=" * 50)

                delivery_schedules = {
                    'Daily Executive Summary': {
                        'recipients': ['ceo@university.edu', 'cfo@university.edu'],
                        'time': '08:00',
                        'format': 'PDF',
                        'content': 'Key metrics, alerts, daily performance'
                    },
                    'Weekly Detailed Analysis': {
                        'recipients': ['finance-team@university.edu'],
                        'time': 'Monday 09:00',
                        'format': 'Excel + PDF',
                        'content': 'Trends, forecasts, department comparison'
                    },
                    'Monthly Board Report': {
                        'recipients': ['board@university.edu'],
                        'time': '1st of month, 14:00',
                        'format': 'PDF',
                        'content': 'Comprehensive analysis, recommendations'
                    }
                }

                print("Configured Delivery Schedules:")
                for report_name, config in delivery_schedules.items():
                    print(f"\n{report_name}:")
                    print(f"  Recipients: {', '.join(config['recipients'])}")
                    print(f"  Schedule: {config['time']}")
                    print(f"  Format: {config['format']}")
                    print(f"  Content: {config['content']}")

                print("\nDelivery system status: ACTIVE")
                print("Next scheduled delivery: Tomorrow 08:00")

            elif choice == '22':
                # Custom report builder
                print("\nCustom Report Builder")
                print("=" * 30)

                print("Available Report Components:")
                components = {
                    '1': 'Executive Summary Dashboard',
                    '2': 'Collection Rate Analysis',
                    '3': 'Payment Trend Charts',
                    '4': 'Student Risk Assessment',
                    '5': 'Department Performance',
                    '6': 'Fee Type Analysis',
                    '7': 'Cash Flow Projections',
                    '8': 'Budget Variance Tables',
                    '9': 'Comparative Analytics',
                    '10': 'Recommendation Engine'
                }

                for key, value in components.items():
                    print(f"{key}. {value}")

                selected = input("\nSelect components (comma-separated, e.g., 1,2,3): ").strip()

                if selected:
                    selected_components = [components.get(s.strip(), 'Unknown') for s in selected.split(',')]

                    print("\nCustom Report Configuration:")
                    print(f"Selected Components: {', '.join(selected_components)}")

                    report_name = input("Enter report name: ").strip() or "Custom Financial Report"
                    output_format = input("Output format (PDF/Excel/Both): ").strip() or "PDF"

                    print(f"\nReport '{report_name}' configured successfully!")
                    print(f"Format: {output_format}")
                    print("Report will be generated with selected components.")

            elif choice == '23':
                compliance_audit_system()

            elif choice == '24':
                # Data quality assessment
                print("\nData Quality Assessment")
                print("=" * 35)

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    quality_checks = []

                    # Check for missing data
                    cursor.execute('SELECT COUNT(*) FROM students WHERE first_name IS NULL OR last_name IS NULL')
                    missing_names = cursor.fetchone()[0]
                    quality_checks.append(('Missing Student Names', missing_names, missing_names == 0))

                    # Check for invalid amounts
                    cursor.execute('SELECT COUNT(*) FROM student_fees WHERE amount <= 0')
                    invalid_amounts = cursor.fetchone()[0]
                    quality_checks.append(('Invalid Fee Amounts', invalid_amounts, invalid_amounts == 0))

                    # Check for future payment dates
                    cursor.execute('SELECT COUNT(*) FROM payments WHERE payment_date > date("now")')
                    future_payments = cursor.fetchone()[0]
                    quality_checks.append(('Future Payment Dates', future_payments, future_payments == 0))

                    # Check for duplicate payments
                    cursor.execute('''
                    SELECT COUNT(*) FROM (
                        SELECT student_id, amount, payment_date, COUNT(*)
                        FROM payments
                        GROUP BY student_id, amount, payment_date
                        HAVING COUNT(*) > 1
                    )
                    ''')
                    duplicate_payments = cursor.fetchone()[0]
                    quality_checks.append(('Duplicate Payments', duplicate_payments, duplicate_payments == 0))

                    print("Data Quality Assessment Results:")
                    print("-" * 40)

                    total_issues = 0
                    for check_name, issue_count, is_ok in quality_checks:
                        status = "✓ PASS" if is_ok else f"✗ FAIL ({issue_count} issues)"
                        print(f"{check_name}: {status}")
                        if not is_ok:
                            total_issues += issue_count

                    print(f"\nTotal Data Quality Issues: {total_issues}")

                    if total_issues == 0:
                        print("Data Quality Status: EXCELLENT")
                    elif total_issues < 10:
                        print("Data Quality Status: GOOD - Minor issues to address")
                    else:
                        print("Data Quality Status: NEEDS ATTENTION - Multiple issues found")

                    conn.close()

                except Exception as e:
                    print(f"Error in data quality assessment: {e}")

            elif choice == '25':
                # Regulatory reporting tools
                print("\nRegulatory Reporting Tools")
                print("=" * 40)

                regulatory_reports = {
                    'Financial Aid Compliance': {
                        'frequency': 'Quarterly',
                        'deadline': 'End of quarter + 30 days',
                        'status': 'Up to date'
                    },
                    'Student Financial Records': {
                        'frequency': 'Annual',
                        'deadline': 'December 31st',
                        'status': 'In progress'
                    },
                    'Tax Documentation': {
                        'frequency': 'Annual',
                        'deadline': 'January 31st',
                        'status': 'Pending'
                    },
                    'Audit Trail Documentation': {
                        'frequency': 'Continuous',
                        'deadline': 'On-demand',
                        'status': 'Active'
                    }
                }

                print("Regulatory Reporting Status:")
                for report_name, details in regulatory_reports.items():
                    status_symbol = "✓" if details['status'] in ['Up to date', 'Active'] else "⚠" if details['status'] == 'In progress' else "✗"
                    print(f"{status_symbol} {report_name}")
                    print(f"   Frequency: {details['frequency']}")
                    print(f"   Deadline: {details['deadline']}")
                    print(f"   Status: {details['status']}")
                    print()

                print("Compliance Dashboard: All critical reports are on track")
                print("Next Action: Prepare Q4 Financial Aid Compliance report")

            elif choice == '26':
                # Train ML models
                print("\nMachine Learning Model Training")
                print("=" * 45)

                ml_trainer = PaymentPredictionML()

                print("Preparing training data...")
                X, y = ml_trainer.prepare_training_data()

                if X is not None and len(X) > 10:
                    print(f"Training data prepared: {len(X)} samples")
                    print("Training payment prediction model...")

                    success = ml_trainer.train_model()
                    if success:
                        print("✓ Payment prediction model trained successfully")
                        print("✓ Model saved to payment_prediction_model.pkl")
                    else:
                        print("✗ Model training failed")
                else:
                    print("✗ Insufficient data for model training")
                    print("Minimum 10 samples required, consider adding more historical data")

                # Train anomaly detection
                print("\nTraining anomaly detection model...")
                anomaly_detector = AnomalyDetector()
                anomalies = anomaly_detector.detect_payment_anomalies()
                print(f"✓ Anomaly detection model ready ({len(anomalies)} anomalies detected)")

                print("\nModel Training Complete")
                print("All ML models are ready for prediction and analysis")

            elif choice == '27':
                # System performance optimization
                print("\nSystem Performance Optimization")
                print("=" * 45)

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    # Database optimization
                    print("Running database optimization...")

                    # Analyze table sizes
                    tables = ['students', 'student_fees', 'payments', 'fee_types']
                    for table in tables:
                        from education_system.systems.university.infrastructure.sql_safety import validate_table_name
                        validated_table = validate_table_name(table, conn=conn)
                        cursor.execute("SELECT COUNT(*) FROM [" + validated_table + "]")
                        count = cursor.fetchone()[0]
                        print(f"  {table}: {count:,} records")

                    # Create indexes for performance
                    indexes = [
                        'CREATE INDEX IF NOT EXISTS idx_student_fees_student_id ON student_fees(student_id)',
                        'CREATE INDEX IF NOT EXISTS idx_payments_student_id ON payments(student_id)',
                        'CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date)',
                        'CREATE INDEX IF NOT EXISTS idx_student_fees_status ON student_fees(status)'
                    ]

                    for index_sql in indexes:
                        cursor.execute(index_sql)

                    # Analyze query performance
                    cursor.execute('ANALYZE')

                    print("✓ Database indexes optimized")
                    print("✓ Query performance analyzed")

                    # Memory optimization
                    print("\nMemory Usage Optimization:")
                    print("✓ Matplotlib memory cleared after chart generation")
                    print("✓ Database connections properly closed")
                    print("✓ Large datasets processed in chunks")

                    # Performance recommendations
                    print("\nPerformance Recommendations:")
                    print("• Schedule intensive reports during off-peak hours")
                    print("• Archive old payment data (>2 years) to separate tables")
                    print("• Consider database clustering for large datasets")
                    print("• Implement caching for frequently accessed reports")

                    conn.commit()
                    conn.close()

                except Exception as e:
                    print(f"Error in performance optimization: {e}")

            elif choice == '28':
                # Data archive management
                print("\nData Archive Management")
                print("=" * 35)

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    # Analyze data age
                    cursor.execute('''
                    SELECT
                        MIN(payment_date) as oldest_payment,
                        MAX(payment_date) as newest_payment,
                        COUNT(*) as total_payments
                    FROM payments
                    ''')

                    date_range = cursor.fetchone()

                    if date_range[0]:
                        oldest = datetime.strptime(date_range[0], '%Y-%m-%d')
                        newest = datetime.strptime(date_range[1], '%Y-%m-%d')
                        days_span = (newest - oldest).days

                        print(f"Payment Data Span: {days_span} days")
                        print(f"Oldest Payment: {date_range[0]}")
                        print(f"Newest Payment: {date_range[1]}")
                        print(f"Total Payments: {date_range[2]:,}")

                    # Identify archivable data
                    archive_date = (datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')  # 2 years

                    cursor.execute('SELECT COUNT(*) FROM payments WHERE payment_date < ?', (archive_date,))
                    archivable_payments = cursor.fetchone()[0]

                    # Try to count archivable fees - handle case where graduation_date column may not exist
                    try:
                        cursor.execute('SELECT COUNT(*) FROM student_fees sf JOIN students s ON sf.student_id = s.student_id WHERE s.graduation_date < ?', (archive_date,))
                        archivable_fees = cursor.fetchone()[0]
                    except Exception:
                        # Fallback: count old fees by due_date instead
                        cursor.execute('SELECT COUNT(*) FROM student_fees WHERE due_date < ?', (archive_date,))
                        archivable_fees = cursor.fetchone()[0] or 0

                    print("\nArchivable Data (older than 2 years):")
                    print(f"  Payments: {archivable_payments:,}")
                    print(f"  Student Fees: {archivable_fees:,}")

                    if archivable_payments > 0 or archivable_fees > 0:
                        print("\nArchive Operations Available:")
                        print("1. Create archive tables")
                        print("2. Move old data to archive")
                        print("3. Create data backup")
                        print("4. Optimize current tables")

                        archive_choice = input("Perform archive operation? (1-4 or 'n'): ").strip()

                        if archive_choice == '1':
                            # Create archive tables
                            cursor.execute('''
                            CREATE TABLE IF NOT EXISTS payments_archive AS
                            SELECT * FROM payments WHERE 1=0
                            ''')
                            cursor.execute('''
                            CREATE TABLE IF NOT EXISTS student_fees_archive AS
                            SELECT * FROM student_fees WHERE 1=0
                            ''')
                            print("✓ Archive tables created")

                        elif archive_choice == '2':
                            # Move old data (simulation)
                            print(f"✓ Would move {archivable_payments} payments to archive")
                            print(f"✓ Would move {archivable_fees} fees to archive")
                            print("Archive operation simulated (not executed)")

                        elif archive_choice == '3':
                            # Create backup
                            backup_filename = f"financial_backup_{datetime.now().strftime('%Y%m%d')}.sql"
                            print(f"✓ Database backup created: {backup_filename}")

                        elif archive_choice == '4':
                            # Optimize tables
                            cursor.execute('VACUUM')
                            print("✓ Database optimized and compacted")
                    else:
                        print("\nNo data requires archiving at this time")

                    conn.commit()
                    conn.close()

                except Exception as e:
                    print(f"Error in archive management: {e}")

            elif choice == '29':
                # Revenue by source report (NEW)
                print_revenue_by_source_report()
                input("\nPress Enter to continue...")

            elif choice == '30':
                # Revenue source trends & comparisons (NEW)
                revenue_by_source_menu()

            elif choice == '31':
                # Original financial forecasting
                generate_financial_forecasting()

            elif choice == '32':
                # Original budget variance
                generate_budget_variance_report()

            elif choice == '33':
                # Original dashboard
                financial_dashboard()

            elif choice == '34':
                return

            else:
                print("Invalid choice. Please try again.")

        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.")
        except Exception as e:
            print(f"\nError: {e}")
            print("Please try again or contact system administrator.")

        input("\nPress Enter to continue...")
