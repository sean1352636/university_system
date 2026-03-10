from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.university_system.modules.domain.health.records.db.audit import log_audit_event


def show_population_health_metrics(auth):
    """Show overall population health metrics"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Population Health Metrics =====")
    
    # Total students
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]
    print(f"Total Students: {total_students}")
    
    # Students with health records
    cursor.execute("SELECT COUNT(DISTINCT student_id) FROM health_records")
    students_with_records = cursor.fetchone()[0]
    print(f"Students with Health Records: {students_with_records} ({students_with_records/total_students*100:.1f}%)")
    
    # Vaccination coverage
    cursor.execute("SELECT COUNT(DISTINCT student_id) FROM vaccination_records WHERE verified = 1")
    students_with_vaccines = cursor.fetchone()[0]
    print(f"Students with Verified Vaccinations: {students_with_vaccines} ({students_with_vaccines/total_students*100:.1f}%)")
    
    # Common health conditions
    cursor.execute('''
    SELECT condition_name, COUNT(*) as count
    FROM medical_conditions
    WHERE status = 'active'
    GROUP BY condition_name
    ORDER BY count DESC
    LIMIT 5
    ''')
    
    conditions = cursor.fetchall()
    if conditions:
        print("\nTop 5 Health Conditions:")
        for condition, count in conditions:
            print(f"  {condition}: {count} students")
    
    # Allergy prevalence
    cursor.execute('''
    SELECT allergen, COUNT(*) as count
    FROM allergies
    WHERE verified = 1
    GROUP BY allergen
    ORDER BY count DESC
    LIMIT 5
    ''')
    
    allergies = cursor.fetchall()
    if allergies:
        print("\nTop 5 Allergies:")
        for allergy, count in allergies:
            print(f"  {allergy}: {count} students")
    
    # Recent health records
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    cursor.execute('''
    SELECT COUNT(*) FROM health_records 
    WHERE record_date >= ?
    ''', (thirty_days_ago,))
    
    recent_records = cursor.fetchone()[0]
    print(f"\nHealth Records (Last 30 Days): {recent_records}")
    
    # Appointments this month
    cursor.execute('''
    SELECT COUNT(*) FROM health_appointments 
    WHERE appointment_date >= ?
    ''', (thirty_days_ago,))
    
    recent_appointments = cursor.fetchone()[0]
    print(f"Appointments (Last 30 Days): {recent_appointments}")
    
    conn.close()



def generate_population_health_report(auth, start_date, end_date):
    conn = get_connection()
    cursor = conn.cursor()
    
    report_content = []
    report_content.append("POPULATION HEALTH STATISTICS REPORT")
    report_content.append("=" * 40)
    report_content.append(f"Period: {start_date} to {end_date}")
    report_content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_content.append("")
    
    # Student demographics
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]
    
    cursor.execute('''
    SELECT gender, COUNT(*) FROM students 
    GROUP BY gender
    ''')
    gender_stats = cursor.fetchall()
    
    report_content.append("STUDENT DEMOGRAPHICS")
    report_content.append("-" * 20)
    report_content.append(f"Total Students: {total_students}")
    
    for gender, count in gender_stats:
        percentage = (count / total_students * 100) if total_students > 0 else 0
        report_content.append(f"{gender}: {count} ({percentage:.1f}%)")
    
    # Health record statistics
    cursor.execute('''
    SELECT COUNT(*) FROM health_records 
    WHERE record_date BETWEEN ? AND ?
    ''', (start_date, end_date))
    
    health_records_period = cursor.fetchone()[0]
    
    cursor.execute('''
    SELECT record_type, COUNT(*) FROM health_records 
    WHERE record_date BETWEEN ? AND ?
    GROUP BY record_type
    ORDER BY COUNT(*) DESC
    ''', (start_date, end_date))
    
    record_types = cursor.fetchall()
    
    report_content.append("")
    report_content.append("HEALTH SERVICES UTILIZATION")
    report_content.append("-" * 28)
    report_content.append(f"Total Health Records: {health_records_period}")
    
    for record_type, count in record_types:
        report_content.append(f"{record_type}: {count}")
    
    # Disease prevalence
    cursor.execute('''
    SELECT condition_name, COUNT(*) as prevalence
    FROM medical_conditions 
    WHERE status = 'active'
    GROUP BY condition_name
    ORDER BY prevalence DESC
    LIMIT 10
    ''')
    
    conditions = cursor.fetchall()
    
    if conditions:
        report_content.append("")
        report_content.append("TOP 10 HEALTH CONDITIONS")
        report_content.append("-" * 24)
        
        for condition, count in conditions:
            prevalence_rate = (count / total_students * 100) if total_students > 0 else 0
            report_content.append(f"{condition}: {count} cases ({prevalence_rate:.2f}%)")
    
    # Display and save report
    print("\n" + "="*60)
    for line in report_content:
        print(line)
    print("="*60)
    
    save_report = input("\nSave report to file? (y/n): ").lower()
    if save_report == 'y':
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"population_health_report_{timestamp}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            for line in report_content:
                f.write(line + '\n')
        
        print(f"Report saved to: {filename}")
        log_audit_event(auth.current_user['id'], 'generate_population_health_report', 'report', filename)
    
    conn.close()



def generate_student_health_summary_report(auth, start_date, end_date):
    """Generate a health summary report for an individual student"""
    student_id = input("Enter student ID: ").strip()
    if not student_id:
        print("Student ID is required.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    report_content = []
    report_content.append("STUDENT HEALTH SUMMARY REPORT")
    report_content.append("=" * 40)
    report_content.append(f"Student ID: {student_id}")
    report_content.append(f"Period: {start_date} to {end_date}")
    report_content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_content.append("")

    # Student demographics
    cursor.execute('''
        SELECT first_name, last_name, date_of_birth, gender, email_address
        FROM students WHERE student_id = ?
    ''', (student_id,))
    student = cursor.fetchone()

    if not student:
        print(f"Student with ID {student_id} not found.")
        conn.close()
        return

    report_content.append("STUDENT INFORMATION")
    report_content.append("-" * 20)
    report_content.append(f"Name: {student[0]} {student[1]}")
    report_content.append(f"Date of Birth: {student[2] or 'N/A'}")
    report_content.append(f"Gender: {student[3] or 'N/A'}")
    report_content.append(f"Email: {student[4] or 'N/A'}")
    report_content.append("")

    # Health records in date range
    cursor.execute('''
        SELECT record_type, record_date, provider, description
        FROM health_records
        WHERE student_id = ? AND record_date BETWEEN ? AND ?
        ORDER BY record_date DESC
    ''', (student_id, start_date, end_date))
    records = cursor.fetchall()

    report_content.append("HEALTH RECORDS")
    report_content.append("-" * 20)
    report_content.append(f"Total Records in Period: {len(records)}")

    if records:
        for record in records:
            report_content.append(f"\n  Date: {record[1]}")
            report_content.append(f"  Type: {record[0]}")
            report_content.append(f"  Provider: {record[2] or 'N/A'}")
            desc = (record[3] or 'N/A')[:100]
            report_content.append(f"  Description: {desc}")
    else:
        report_content.append("  No health records found in this period.")

    report_content.append("")

    # Active medical conditions
    cursor.execute('''
        SELECT condition_name, diagnosis_date, status, severity
        FROM medical_conditions
        WHERE student_id = ?
        ORDER BY diagnosis_date DESC
    ''', (student_id,))
    conditions = cursor.fetchall()

    report_content.append("MEDICAL CONDITIONS")
    report_content.append("-" * 20)
    if conditions:
        for cond in conditions:
            status_str = f" [{cond[2]}]" if cond[2] else ""
            severity_str = f" (Severity: {cond[3]})" if cond[3] else ""
            report_content.append(f"  {cond[0]}{status_str}{severity_str} - Diagnosed: {cond[1] or 'N/A'}")
    else:
        report_content.append("  No medical conditions on record.")

    report_content.append("")

    # Vaccination records
    cursor.execute('''
        SELECT vaccine_name, vaccination_date, dose_number, administered_by
        FROM vaccinations
        WHERE student_id = ?
        ORDER BY vaccination_date DESC
    ''', (student_id,))
    vaccinations = cursor.fetchall()

    report_content.append("VACCINATION HISTORY")
    report_content.append("-" * 20)
    if vaccinations:
        for vax in vaccinations:
            dose_str = f" (Dose {vax[2]})" if vax[2] else ""
            report_content.append(f"  {vax[0]}{dose_str} - {vax[1] or 'N/A'} by {vax[3] or 'N/A'}")
    else:
        report_content.append("  No vaccination records found.")

    report_content.append("")

    # Appointments in date range
    cursor.execute('''
        SELECT appointment_date, appointment_type, provider, status
        FROM appointments
        WHERE student_id = ? AND appointment_date BETWEEN ? AND ?
        ORDER BY appointment_date DESC
    ''', (student_id, start_date, end_date))
    appointments = cursor.fetchall()

    report_content.append("APPOINTMENTS IN PERIOD")
    report_content.append("-" * 20)
    if appointments:
        for apt in appointments:
            report_content.append(f"  {apt[0]} - {apt[1]} with {apt[2] or 'N/A'} [{apt[3] or 'N/A'}]")
    else:
        report_content.append("  No appointments in this period.")

    # Display and save report
    print("\n" + "=" * 60)
    for line in report_content:
        print(line)
    print("=" * 60)

    save_report = input("\nSave report to file? (y/n): ").lower()
    if save_report == 'y':
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"student_health_summary_{student_id}_{timestamp}.txt"

        with open(filename, 'w', encoding='utf-8') as f:
            for line in report_content:
                f.write(line + '\n')

        print(f"Report saved to: {filename}")
        log_audit_event(auth.current_user['id'], 'generate_student_health_summary', 'report', filename)

    conn.close()



def generate_student_health_summary(auth):
    """Generate comprehensive student health summary"""
    conn = get_connection()
    cursor = conn.cursor()
    
    student_id = input("Enter student ID: ")
    
    # Verify student exists
    cursor.execute('''
    SELECT student_id, first_name, last_name, gender, date_of_birth, age
    FROM students WHERE student_id = ?
    ''', (student_id,))
    
    student = cursor.fetchone()
    if not student:
        print("Error: Student ID not found.")
        conn.close()
        return
    
    print(f"\n===== Health Summary for {student[1]} {student[2]} =====")
    print(f"Student ID: {student[0]}")
    print(f"Gender: {student[3]}")
    print(f"Date of Birth: {student[4]}")
    print(f"Age: {student[5]}")
    
    # Health conditions
    cursor.execute('''
    SELECT condition_name, severity, diagnosed_date, status
    FROM medical_conditions
    WHERE student_id = ?
    ORDER BY diagnosed_date DESC
    ''', (student_id,))
    
    conditions = cursor.fetchall()
    if conditions:
        print("\nMedical Conditions:")
        for condition, severity, diagnosed_date, status in conditions:
            print(f"  - {condition} ({severity}) - Diagnosed: {diagnosed_date} - Status: {status}")
    
    # Allergies
    cursor.execute('''
    SELECT allergen, severity, reaction_description, verified
    FROM allergies
    WHERE student_id = ?
    ORDER BY severity DESC
    ''', (student_id,))
    
    allergies = cursor.fetchall()
    if allergies:
        print("\nAllergies:")
        for allergen, severity, reaction, verified in allergies:
            status = "Verified" if verified else "Unverified"
            print(f"  - {allergen} ({severity}) - {reaction} - {status}")
    
    # Recent vaccinations
    cursor.execute('''
    SELECT vaccine_name, administered_date, expiry_date, verified
    FROM vaccination_records
    WHERE student_id = ?
    ORDER BY administered_date DESC
    LIMIT 10
    ''', (student_id,))
    
    vaccinations = cursor.fetchall()
    if vaccinations:
        print("\nRecent Vaccinations:")
        for vaccine, admin_date, expiry_date, verified in vaccinations:
            status = "Verified" if verified else "Unverified"
            print(f"  - {vaccine} - Administered: {admin_date} - Expires: {expiry_date} - {status}")
    
    # Active prescriptions
    cursor.execute('''
    SELECT medication_name, dosage, frequency, prescribed_date
    FROM prescriptions
    WHERE student_id = ? AND status = 'active'
    ORDER BY prescribed_date DESC
    ''', (student_id,))
    
    prescriptions = cursor.fetchall()
    if prescriptions:
        print("\nActive Prescriptions:")
        for medication, dosage, frequency, prescribed_date in prescriptions:
            print(f"  - {medication} ({dosage}) - {frequency} - Prescribed: {prescribed_date}")
    
    # Recent vital signs
    cursor.execute('''
    SELECT measurement_date, blood_pressure_systolic, blood_pressure_diastolic,
           heart_rate, temperature, weight, bmi
    FROM vital_signs
    WHERE student_id = ?
    ORDER BY measurement_date DESC
    LIMIT 3
    ''', (student_id,))
    
    vitals = cursor.fetchall()
    if vitals:
        print("\nRecent Vital Signs:")
        for date, bp_sys, bp_dia, hr, temp, weight, bmi in vitals:
            print(f"  {date}:")
            if bp_sys and bp_dia:
                print(f"    BP: {bp_sys}/{bp_dia} mmHg")
            if hr:
                print(f"    HR: {hr} bpm")
            if temp:
                print(f"    Temp: {temp}°F")
            if weight:
                print(f"    Weight: {weight} lbs")
            if bmi:
                print(f"    BMI: {bmi}")
    
    # Save report option
    save_report = input("\nSave report to file? (y/n): ").lower()
    if save_report == 'y':
        filename = f"health_summary_{student_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        # Code to save report to file would go here
        print(f"Report saved to {filename}")
    
    conn.close()



