from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.systems.university.domain.pastoral.health.records.db.audit import log_audit_event


def generate_vaccination_status_report(auth):
    """Generate vaccination status report for students"""
    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Vaccination Status Report =====")

    # Get total students
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    # Common vaccines status
    common_vaccines = ['COVID-19', 'Influenza (Flu)', 'Hepatitis B', 'MMR', 'Tdap']

    print(f"Total Students: {total_students}")
    print("\nVaccination Coverage by Type:")
    print("-" * 40)

    for vaccine in common_vaccines:
        cursor.execute('''
        SELECT COUNT(DISTINCT student_id) FROM vaccination_records
        WHERE vaccine_name = ? AND verified = 1
        ''', (vaccine,))

        vaccinated = cursor.fetchone()[0]
        coverage = (vaccinated / total_students * 100) if total_students > 0 else 0

        print(f"{vaccine}: {vaccinated}/{total_students} ({coverage:.1f}%)")

    # Students with incomplete vaccinations
    cursor.execute('''
    SELECT s.student_id, s.first_name, s.last_name,
           COUNT(vr.id) as vaccine_count
    FROM students s
    LEFT JOIN vaccination_records vr ON s.student_id = vr.student_id AND vr.verified = 1
    GROUP BY s.student_id, s.first_name, s.last_name
    HAVING vaccine_count < 3
    ORDER BY vaccine_count, s.last_name
    LIMIT 20
    ''')

    incomplete = cursor.fetchall()

    if incomplete:
        print("\nStudents with Incomplete Vaccinations (showing first 20):")
        print("-" * 50)
        for student_id, first_name, last_name, count in incomplete:
            print(f"{last_name}, {first_name} (ID: {student_id}): {count} verified vaccines")

    conn.close()



def generate_vaccination_coverage_report(auth):
    """Generate detailed vaccination coverage report"""
    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Vaccination Coverage Report =====")

    # Overall coverage
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT student_id) FROM vaccination_records WHERE verified = 1")
    students_with_vaccines = cursor.fetchone()[0]

    print(f"Overall Vaccination Coverage: {students_with_vaccines}/{total_students} ({students_with_vaccines/total_students*100:.1f}%)")

    # Coverage by vaccine type
    cursor.execute('''
    SELECT vaccine_name, COUNT(DISTINCT student_id) as coverage
    FROM vaccination_records
    WHERE verified = 1
    GROUP BY vaccine_name
    ORDER BY coverage DESC
    ''')

    vaccine_coverage = cursor.fetchall()

    if vaccine_coverage:
        print("\nCoverage by Vaccine Type:")
        for vaccine, coverage in vaccine_coverage:
            coverage_pct = (coverage / total_students) * 100
            print(f"  {vaccine}: {coverage}/{total_students} ({coverage_pct:.1f}%)")

    # Expired vaccinations
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
    SELECT vaccine_name, COUNT(*) as expired_count
    FROM vaccination_records
    WHERE expiry_date < ? AND verified = 1
    GROUP BY vaccine_name
    ORDER BY expired_count DESC
    ''', (today,))

    expired_vaccines = cursor.fetchall()

    if expired_vaccines:
        print("\nExpired Vaccinations Requiring Renewal:")
        for vaccine, count in expired_vaccines:
            print(f"  {vaccine}: {count} students")

    # Upcoming expirations (next 90 days)
    ninety_days_from_now = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
    cursor.execute('''
    SELECT vaccine_name, COUNT(*) as expiring_count
    FROM vaccination_records
    WHERE expiry_date BETWEEN ? AND ? AND verified = 1
    GROUP BY vaccine_name
    ORDER BY expiring_count DESC
    ''', (today, ninety_days_from_now))

    expiring_vaccines = cursor.fetchall()

    if expiring_vaccines:
        print("\nVaccinations Expiring in Next 90 Days:")
        for vaccine, count in expiring_vaccines:
            print(f"  {vaccine}: {count} students")

    conn.close()



def generate_vaccination_analysis_report(auth, start_date, end_date):
    """Generate vaccination analysis report"""
    conn = get_connection()
    cursor = conn.cursor()

    report_content = []
    report_content.append("VACCINATION ANALYSIS REPORT")
    report_content.append("=" * 30)
    report_content.append(f"Period: {start_date} to {end_date}")
    report_content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_content.append("")

    # Vaccination coverage by type
    cursor.execute('''
    SELECT vaccine_name, COUNT(*) as doses_given,
           COUNT(DISTINCT student_id) as students_vaccinated
    FROM vaccination_records
    WHERE administered_date BETWEEN ? AND ? AND verified = 1
    GROUP BY vaccine_name
    ORDER BY doses_given DESC
    ''', (start_date, end_date))

    vax_data = cursor.fetchall()

    if vax_data:
        report_content.append("VACCINATION COVERAGE BY TYPE")
        report_content.append("-" * 30)
        for vaccine, doses, students in vax_data:
            report_content.append(f"{vaccine}: {doses} doses, {students} students")

    # Verification rates
    cursor.execute('''
    SELECT
        COUNT(*) as total_vaccinations,
        SUM(CASE WHEN verified = 1 THEN 1 ELSE 0 END) as verified_count
    FROM vaccination_records
    WHERE administered_date BETWEEN ? AND ?
    ''', (start_date, end_date))

    verification_data = cursor.fetchone()
    if verification_data and verification_data[0] > 0:
        verification_rate = (verification_data[1] / verification_data[0]) * 100
        report_content.append("")
        report_content.append("VERIFICATION RATES")
        report_content.append("-" * 17)
        report_content.append(f"Total Vaccinations: {verification_data[0]}")
        report_content.append(f"Verified: {verification_data[1]} ({verification_rate:.1f}%)")

    # Display report
    for line in report_content:
        print(line)

    conn.close()



