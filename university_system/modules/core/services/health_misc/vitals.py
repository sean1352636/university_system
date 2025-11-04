from __future__ import annotations

from datetime import datetime
from university_system.infrastructure.database.db import get_connection
from university_system.infrastructure.database.data_backup import backup_before_operation
from university_system.modules.core.services.health_misc.audit import log_audit_event

def manage_vital_signs(auth):
    if not auth or not auth.current_user:
        print("You must be logged in to manage vital signs.")
        return

    while True:
        print("\n===== Vital Signs Management =====")
        print("1. Record Vital Signs")
        print("2. View Vital Signs")
        print("3. Vital Signs Trends")
        print("4. BMI Calculator")
        print("5. Return to Main Menu")

        choice = input("\nEnter your choice (1-5): ")

        if choice == '1':
            record_vital_signs(auth)
        elif choice == '2':
            view_vital_signs(auth)
        elif choice == '3':
            view_vital_signs_trends(auth)
        elif choice == '4':
            calculate_bmi(auth)
        elif choice == '5':
            break
        else:
            print("Invalid choice. Please try again.")

def record_vital_signs(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to record vital signs.")
        return

    backup_before_operation('record_vital_signs')

    conn = get_connection()
    cursor = conn.cursor()

    student_id = input("Enter student ID: ")

    # Verify student exists
    cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
    if cursor.fetchone()[0] == 0:
        print("Error: Student ID not found.")
        conn.close()
        return

    while True:
        measurement_date = input("Measurement date (YYYY-MM-DD) [today]: ").strip()
        if not measurement_date:
            measurement_date = datetime.now().strftime('%Y-%m-%d')
            break
        try:
            datetime.strptime(measurement_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    # Blood pressure
    bp_systolic = input("Blood pressure systolic (mmHg): ").strip()
    bp_systolic = int(bp_systolic) if bp_systolic.isdigit() else None

    bp_diastolic = input("Blood pressure diastolic (mmHg): ").strip()
    bp_diastolic = int(bp_diastolic) if bp_diastolic.isdigit() else None

    # Heart rate
    heart_rate = input("Heart rate (bpm): ").strip()
    heart_rate = int(heart_rate) if heart_rate.isdigit() else None

    # Temperature
    temperature = input("Temperature (°F): ").strip()
    temperature = float(temperature) if temperature.replace('.', '').isdigit() else None

    # Weight
    weight = input("Weight (lbs): ").strip()
    weight = float(weight) if weight.replace('.', '').isdigit() else None

    # Height
    height = input("Height (inches): ").strip()
    height = float(height) if height.replace('.', '').isdigit() else None

    # Calculate BMI if both height and weight are provided
    bmi = None
    if height and weight:
        bmi = round((weight / (height ** 2)) * 703, 1)  # BMI formula

    recorded_by = f"{auth.current_user['username']}"
    notes = input("Additional notes: ")
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
    INSERT INTO vital_signs 
    (student_id, measurement_date, blood_pressure_systolic, blood_pressure_diastolic, 
     heart_rate, temperature, weight, height, bmi, recorded_by, notes, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, measurement_date, bp_systolic, bp_diastolic, heart_rate, 
          temperature, weight, height, bmi, recorded_by, notes, created_at))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'record_vital_signs', 'vital_signs', cursor.lastrowid)

    print("\nVital signs recorded successfully!")

    # Show any alerts
    alerts = check_vital_signs_alerts(bp_systolic, bp_diastolic, heart_rate, temperature, bmi)
    if alerts:
        print("\n⚠️  VITAL SIGNS ALERTS:")
        for alert in alerts:
            print(f"- {alert}")

    conn.close()

def check_vital_signs_alerts(bp_sys, bp_dia, hr, temp, bmi):
    """Check for vital signs that are outside normal ranges"""
    alerts = []

    if bp_sys:
        if bp_sys >= 140:
            alerts.append("High systolic blood pressure (≥140 mmHg)")
        elif bp_sys < 90:
            alerts.append("Low systolic blood pressure (<90 mmHg)")

    if bp_dia:
        if bp_dia >= 90:
            alerts.append("High diastolic blood pressure (≥90 mmHg)")
        elif bp_dia < 60:
            alerts.append("Low diastolic blood pressure (<60 mmHg)")

    if hr:
        if hr > 100:
            alerts.append("High heart rate (>100 bpm)")
        elif hr < 60:
            alerts.append("Low heart rate (<60 bpm)")

    if temp:
        if temp >= 100.4:
            alerts.append("Fever (≥100.4°F)")
        elif temp < 96.0:
            alerts.append("Low body temperature (<96.0°F)")

    if bmi:
        if bmi >= 30:
            alerts.append("BMI indicates obesity (≥30)")
        elif bmi < 18.5:
            alerts.append("BMI indicates underweight (<18.5)")

    return alerts

def view_vital_signs(auth):
    if not (auth.check_permission('view_any_health_record') or auth.check_permission('view_own_health_record')):
        print("You don't have permission to view vital signs.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    if auth.check_permission('view_any_health_record'):
        student_id = input("Enter student ID: ")

        cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
        if cursor.fetchone()[0] == 0:
            print("Error: Student ID not found.")
            conn.close()
            return
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return

    cursor.execute('''
    SELECT id, measurement_date, blood_pressure_systolic, blood_pressure_diastolic,
           heart_rate, temperature, weight, height, bmi, recorded_by, notes
    FROM vital_signs
    WHERE student_id = ?
    ORDER BY measurement_date DESC
    ''', (student_id,))

    vital_signs = cursor.fetchall()

    if not vital_signs:
        print("No vital signs records found.")
        conn.close()
        return

    print("\n===== Vital Signs Records =====")
    for record in vital_signs:
        vs_id, date, bp_sys, bp_dia, hr, temp, weight, height, bmi, recorded_by, notes = record

        print(f"\nDate: {date}")
        print(f"Recorded by: {recorded_by}")

        if bp_sys and bp_dia:
            print(f"Blood Pressure: {bp_sys}/{bp_dia} mmHg")

        if hr:
            print(f"Heart Rate: {hr} bpm")

        if temp:
            print(f"Temperature: {temp}°F")

        if weight:
            print(f"Weight: {weight} lbs")

        if height:
            print(f"Height: {height} inches")

        if bmi:
            print(f"BMI: {bmi}")

        if notes:
            print(f"Notes: {notes}")

        # Check for alerts
        alerts = check_vital_signs_alerts(bp_sys, bp_dia, hr, temp, bmi)
        if alerts:
            print("⚠️  Alerts:")
            for alert in alerts:
                print(f"   - {alert}")

        print("-" * 30)

    conn.close()

def view_vital_signs_trends(auth):
    """View trends in vital signs over time"""
    if not (auth.check_permission('view_any_health_record') or auth.check_permission('view_own_health_record')):
        print("You don't have permission to view vital signs trends.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    if auth.check_permission('view_any_health_record'):
        student_id = input("Enter student ID: ")

        cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
        if cursor.fetchone()[0] == 0:
            print("Error: Student ID not found.")
            conn.close()
            return
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return

    # Get last 12 months of data
    twelve_months_ago = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

    cursor.execute('''
    SELECT measurement_date, blood_pressure_systolic, blood_pressure_diastolic,
           heart_rate, temperature, weight, bmi
    FROM vital_signs
    WHERE student_id = ? AND measurement_date >= ?
    ORDER BY measurement_date
    ''', (student_id, twelve_months_ago))

    records = cursor.fetchall()

    if not records:
        print("No vital signs records found in the last 12 months.")
        conn.close()
        return

    print(f"\n===== Vital Signs Trends for Student {student_id} =====")
    print("(Last 12 months)")

    # Calculate trends
    dates = []
    bp_sys_values = []
    bp_dia_values = []
    hr_values = []
    temp_values = []
    weight_values = []
    bmi_values = []

    for record in records:
        date, bp_sys, bp_dia, hr, temp, weight, bmi = record
        dates.append(date)
        if bp_sys: bp_sys_values.append(bp_sys)
        if bp_dia: bp_dia_values.append(bp_dia)
        if hr: hr_values.append(hr)
        if temp: temp_values.append(temp)
        if weight: weight_values.append(weight)
        if bmi: bmi_values.append(bmi)

    # Display trends
    if bp_sys_values:
        avg_bp_sys = sum(bp_sys_values) / len(bp_sys_values)
        print(f"Systolic BP - Average: {avg_bp_sys:.1f} mmHg, Range: {min(bp_sys_values)}-{max(bp_sys_values)}")

    if bp_dia_values:
        avg_bp_dia = sum(bp_dia_values) / len(bp_dia_values)
        print(f"Diastolic BP - Average: {avg_bp_dia:.1f} mmHg, Range: {min(bp_dia_values)}-{max(bp_dia_values)}")

    if hr_values:
        avg_hr = sum(hr_values) / len(hr_values)
        print(f"Heart Rate - Average: {avg_hr:.1f} bpm, Range: {min(hr_values)}-{max(hr_values)}")

    if temp_values:
        avg_temp = sum(temp_values) / len(temp_values)
        print(f"Temperature - Average: {avg_temp:.1f}°F, Range: {min(temp_values):.1f}-{max(temp_values):.1f}")

    if weight_values:
        weight_change = weight_values[-1] - weight_values[0] if len(weight_values) > 1 else 0
        print(f"Weight - Current: {weight_values[-1]} lbs, Change: {weight_change:+.1f} lbs")

    if bmi_values:
        bmi_change = bmi_values[-1] - bmi_values[0] if len(bmi_values) > 1 else 0
        print(f"BMI - Current: {bmi_values[-1]}, Change: {bmi_change:+.1f}")

    print(f"\nTotal measurements: {len(records)}")
    print(f"Date range: {dates[0]} to {dates[-1]}")

    conn.close()

def calculate_bmi(auth):
    """BMI calculator utility"""
    print("\n===== BMI Calculator =====")

    try:
        weight = float(input("Enter weight (lbs): "))
        height = float(input("Enter height (inches): "))

        bmi = round((weight / (height ** 2)) * 703, 1)

        print(f"\nBMI: {bmi}")

        if bmi < 18.5:
            category = "Underweight"
        elif bmi < 25:
            category = "Normal weight"
        elif bmi < 30:
            category = "Overweight"
        else:
            category = "Obese"

        print(f"Category: {category}")

        # Health recommendations
        if bmi < 18.5:
            print("Recommendation: Consider consulting with a nutritionist about healthy weight gain.")
        elif bmi >= 30:
            print("Recommendation: Consider consulting with a healthcare provider about weight management.")
        elif bmi >= 25:
            print("Recommendation: Consider lifestyle modifications for weight management.")
        else:
            print("Recommendation: Maintain current healthy lifestyle.")

    except ValueError:
        print("Invalid input. Please enter numeric values.")
