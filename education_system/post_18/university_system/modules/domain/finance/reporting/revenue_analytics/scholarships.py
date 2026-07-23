from education_system.post_18.university_system.infrastructure.database.db import get_connection
from datetime import datetime, timedelta
import csv
from education_system.post_18.university_system.modules.domain.finance.scholarships.scholarship_programs import scholarship_distribution_summary, scholarship_utilization_analysis
from education_system.post_18.university_system.modules.domain.finance.core.aid import aid_distribution_summary, aid_by_academic_year, aid_effectiveness_analysis


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

        print("\nStudent Scholarship Report")
        print("=" * 90)
        print(f"{'Student ID':<12} {'Name':<25} {'Course':<20} {'Count':<8} {'Total Amount':<15}")
        print("-" * 90)

        for student in students:
            student_id, first_name, last_name, course, count, total = student
            student_name = f"{first_name} {last_name}"
            print(f"{student_id:<12} {student_name:<25} {course:<20} {count:<8} £{total:<14.2f}")

        print("=" * 90)

        conn.close()

    except Exception as e:
        print(f"Error generating student scholarship report: {e}")

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

        print("\nLoan Repayment Status Report:")
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
