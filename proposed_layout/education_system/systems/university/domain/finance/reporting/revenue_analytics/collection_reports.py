from education_system.systems.university.infrastructure.database.db import get_connection


def generate_collection_reports():
    """Generate collection management reports"""
    from education_system.systems.university.domain.finance.core.analytics import recovery_rate_analysis
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

            print("\nCollection Performance Summary:")
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
                print("\nMonthly Collection Case Trends (Last 12 Months):")
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

        print("\nCollection Agency Performance Report:")
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

        print("\nAging Analysis Report:")
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

        print("\nRisk Assessment:")
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

        print("\nCollection Case Status Report:")
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
            print("\nMonthly Case Creation Trend:")
            print("-" * 40)
            for month, cases in trend_data:
                print(f"{month}: {cases} new cases")

        conn.close()

    except Exception as e:
        print(f"Error generating collection case status report: {e}")
