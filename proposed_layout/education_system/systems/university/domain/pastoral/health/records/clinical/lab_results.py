from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.systems.university.infrastructure.database.data_backup import backup_before_operation
from education_system.systems.university.domain.pastoral.health.records.db.audit import log_audit_event
from education_system.systems.university.domain.pastoral.health.services import get_user_student_id
from education_system.systems.university.domain.pastoral.health.services import critical_values_alert


def manage_lab_results(auth):
    """Main lab results management menu"""
    if not auth or not auth.current_user:
        print("You must be logged in to manage lab results.")
        return

    while True:
        print("\n===== Lab Results Management =====")
        print("1. Add Lab Result")
        print("2. View Lab Results")
        print("3. Critical Values Alert")
        print("4. Lab Trends Analysis")
        print("5. Return to Main Menu")

        choice = input("\nEnter your choice (1-5): ")

        if choice == '1':
            # Function is in health_health_management.py
            add_lab_result(auth)
        elif choice == '2':
            # Function is in health_health_management.py
            view_lab_results(auth)
        elif choice == '3':
            # Function is in health_misc.py
            critical_values_alert(auth)
        elif choice == '4':
            # Function is in health_health_management.py
            lab_trends_analysis(auth)
        elif choice == '5':
            break
        else:
            print("Invalid choice. Please try again.")



def add_lab_result(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to add lab results.")
        return

    backup_before_operation('add_lab_result')

    conn = get_connection()
    cursor = conn.cursor()

    student_id = input("Enter student ID: ")

    # Verify student exists
    cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
    if cursor.fetchone()[0] == 0:
        print("Error: Student ID not found.")
        conn.close()
        return

    test_name = input("Test name: ")
    test_code = input("Test code (optional): ")
    result_value = input("Result value: ")
    reference_range = input("Reference range: ")
    units = input("Units: ")

    status_options = ['Final', 'Preliminary', 'Corrected', 'Cancelled']
    print("\nStatus Options:")
    for i, status in enumerate(status_options):
        print(f"{i+1}. {status}")

    while True:
        status_choice = input("\nSelect status (1-4): ")
        if status_choice.isdigit() and 1 <= int(status_choice) <= len(status_options):
            status = status_options[int(status_choice) - 1]
            break
        print("Invalid choice. Please try again.")

    while True:
        ordered_date = input("Ordered date (YYYY-MM-DD): ")
        try:
            datetime.strptime(ordered_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    while True:
        collected_date = input("Collected date (YYYY-MM-DD): ")
        try:
            datetime.strptime(collected_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    while True:
        resulted_date = input("Resulted date (YYYY-MM-DD) [today]: ").strip()
        if not resulted_date:
            resulted_date = datetime.now().strftime('%Y-%m-%d')
            break
        try:
            datetime.strptime(resulted_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    ordering_provider = input(f"Ordering provider [Dr. {auth.current_user['username']}]: ").strip()
    if not ordering_provider:
        ordering_provider = f"Dr. {auth.current_user['username']}"

    lab_name = input("Lab name: ")

    # Check for abnormal values
    abnormal_flag = input("Abnormal flag (H/L/blank): ").strip().upper()
    if abnormal_flag not in ['H', 'L', '']:
        abnormal_flag = ''

    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
    INSERT INTO lab_results
    (student_id, test_name, test_code, result_value, reference_range, units,
     status, ordered_date, collected_date, resulted_date, ordering_provider,
     lab_name, abnormal_flag, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, test_name, test_code, result_value, reference_range, units,
          status, ordered_date, collected_date, resulted_date, ordering_provider,
          lab_name, abnormal_flag, created_at))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'add_lab_result', 'lab_result', cursor.lastrowid)

    print("\nLab result added successfully!")

    # Check for critical values
    if abnormal_flag in ['H', 'L']:
        print(f"\n⚠️  ABNORMAL RESULT DETECTED: {test_name} = {result_value} {units} ({abnormal_flag})")
        print("Consider notifying the ordering provider immediately.")

        # Check if this is a critical value that requires immediate attention
        critical_tests = {
            'glucose': {'high': 400, 'low': 50},
            'potassium': {'high': 6.0, 'low': 2.5},
            'sodium': {'high': 160, 'low': 120},
            'creatinine': {'high': 5.0, 'low': None},
            'hemoglobin': {'high': 20, 'low': 6},
            'platelet': {'high': 1000, 'low': 50},
            'white blood cell': {'high': 50, 'low': 1}
        }

        # Check if this test has critical value thresholds
        for test_key, thresholds in critical_tests.items():
            if test_key.lower() in test_name.lower():
                try:
                    numeric_value = float(result_value)
                    is_critical = False

                    if abnormal_flag == 'H' and thresholds['high'] and numeric_value >= thresholds['high']:
                        is_critical = True
                    elif abnormal_flag == 'L' and thresholds['low'] and numeric_value <= thresholds['low']:
                        is_critical = True

                    if is_critical:
                        print("\n🚨 CRITICAL VALUE ALERT! 🚨")
                        print(f"Test: {test_name}")
                        print(f"Value: {result_value} {units}")
                        print("This value requires IMMEDIATE provider notification!")

                        # Log critical value
                        log_audit_event(auth.current_user['id'], 'critical_lab_value', 'lab_result',
                                      cursor.lastrowid, f"Critical {test_name}: {result_value}")

                        # Prompt for provider notification
                        notify_provider = input("Has the ordering provider been notified? (y/n): ").lower()
                        if notify_provider != 'y':
                            print("⚠️  URGENT: Please notify the ordering provider immediately!")
                            print(f"Provider: {ordering_provider}")

                        break

                except ValueError:
                    # Non-numeric result, skip critical value check
                    pass

    # Check for drug interactions if this is a therapeutic drug monitoring test
    therapeutic_tests = ['digoxin', 'lithium', 'phenytoin', 'carbamazepine', 'valproic acid', 'theophylline']

    for therapeutic_test in therapeutic_tests:
        if therapeutic_test.lower() in test_name.lower():
            print("\n💊 THERAPEUTIC DRUG MONITORING ALERT")
            print(f"This is a therapeutic drug monitoring test for {therapeutic_test}")

            # Check for active prescriptions of this medication
            cursor.execute('''
            SELECT medication_name, dosage FROM prescriptions
            WHERE student_id = ? AND status = 'active'
            AND LOWER(medication_name) LIKE ?
            ''', (student_id, f'%{therapeutic_test}%'))

            related_prescriptions = cursor.fetchall()

            if related_prescriptions:
                print("Related active prescriptions found:")
                for med_name, dosage in related_prescriptions:
                    print(f"  - {med_name} ({dosage})")
                print("Consider dose adjustment based on lab results.")
            else:
                print("⚠️  No active prescriptions found for this medication.")
                print("Verify patient is still taking this medication.")

            break

    # Suggest follow-up tests if needed
    follow_up_suggestions = {
        'glucose': ['HbA1c if glucose elevated', 'Repeat fasting glucose'],
        'creatinine': ['BUN', 'Urinalysis', 'Estimated GFR'],
        'liver': ['Complete liver panel if abnormal', 'Hepatitis panel'],
        'cholesterol': ['Lipid panel repeat in 6-12 weeks', 'Liver function tests'],
        'thyroid': ['TSH if T4 abnormal', 'T3 if indicated'],
        'hemoglobin': ['Iron studies', 'B12 and folate', 'Reticulocyte count']
    }

    for test_category, suggestions in follow_up_suggestions.items():
        if test_category.lower() in test_name.lower():
            if abnormal_flag:
                print(f"\n📋 FOLLOW-UP RECOMMENDATIONS for abnormal {test_name}:")
                for suggestion in suggestions:
                    print(f"  • {suggestion}")
            break

    # Check for trends if previous results exist
    cursor.execute('''
    SELECT result_value, resulted_date FROM lab_results
    WHERE student_id = ? AND test_name = ? AND id != ?
    ORDER BY resulted_date DESC LIMIT 3
    ''', (student_id, test_name, cursor.lastrowid))

    previous_results = cursor.fetchall()

    if previous_results:
        print(f"\n📊 PREVIOUS RESULTS for {test_name}:")
        for prev_value, prev_date in previous_results:
            print(f"  {prev_date}: {prev_value} {units}")

        # Calculate trend if values are numeric
        try:
            current_numeric = float(result_value)
            prev_numeric = float(previous_results[0][0])

            change = current_numeric - prev_numeric
            percent_change = (change / prev_numeric * 100) if prev_numeric != 0 else 0

            if abs(percent_change) > 20:  # Significant change threshold
                trend_direction = "↗️ Increasing" if change > 0 else "↘️ Decreasing"
                print(f"  Trend: {trend_direction} ({change:+.2f}, {percent_change:+.1f}%)")

                if abs(percent_change) > 50:
                    print("  ⚠️  Significant change from previous result - verify accuracy")

        except ValueError:
            # Non-numeric values, no trend calculation
            pass

    conn.close()



def view_lab_results(auth):
    if not (auth.check_permission('view_any_health_record') or auth.check_permission('view_own_health_record')):
        print("You don't have permission to view lab results.")
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
    SELECT id, test_name, result_value, reference_range, units, status,
           ordered_date, collected_date, resulted_date, ordering_provider,
           lab_name, abnormal_flag
    FROM lab_results
    WHERE student_id = ?
    ORDER BY resulted_date DESC
    ''', (student_id,))

    results = cursor.fetchall()

    if not results:
        print("No lab results found.")
        conn.close()
        return

    print("\n===== Lab Results =====")
    for result in results:
        result_id, test_name, result_value, reference_range, units, status, ordered_date, collected_date, resulted_date, ordering_provider, lab_name, abnormal_flag = result

        print(f"\nTest: {test_name}")
        print(f"Result: {result_value} {units}")
        print(f"Reference Range: {reference_range}")
        print(f"Status: {status}")
        print(f"Ordered: {ordered_date}")
        print(f"Collected: {collected_date}")
        print(f"Resulted: {resulted_date}")
        print(f"Ordering Provider: {ordering_provider}")
        print(f"Lab: {lab_name}")

        if abnormal_flag:
            if abnormal_flag == 'H':
                print("🔴 HIGH - Above normal range")
            elif abnormal_flag == 'L':
                print("🔵 LOW - Below normal range")
        else:
            print("✅ NORMAL")

        print("-" * 30)

    conn.close()



def lab_trends_analysis(auth):
    """Analyze lab result trends over time"""
    if not (auth.check_permission('view_any_health_record') or auth.check_permission('view_own_health_record')):
        print("You don't have permission to view lab trends.")
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

    # Get available test types
    cursor.execute('''
    SELECT DISTINCT test_name FROM lab_results
    WHERE student_id = ?
    ORDER BY test_name
    ''', (student_id,))

    available_tests = [row[0] for row in cursor.fetchall()]

    if not available_tests:
        print("No lab results found for trend analysis.")
        conn.close()
        return

    print("\nAvailable Tests for Trend Analysis:")
    for i, test in enumerate(available_tests):
        print(f"{i+1}. {test}")

    while True:
        choice = input("\nSelect test for trend analysis (number): ")
        if choice.isdigit() and 1 <= int(choice) <= len(available_tests):
            selected_test = available_tests[int(choice) - 1]
            break
        print("Invalid choice. Please try again.")

    # Get trend data for the selected test
    cursor.execute('''
    SELECT resulted_date, result_value, reference_range, abnormal_flag
    FROM lab_results
    WHERE student_id = ? AND test_name = ?
    ORDER BY resulted_date
    ''', (student_id, selected_test))

    trend_data = cursor.fetchall()

    if len(trend_data) < 2:
        print("Insufficient data for trend analysis (need at least 2 results).")
        conn.close()
        return

    print(f"\n===== Trend Analysis for {selected_test} =====")

    # Display trend data
    print("\nResults Over Time:")
    for date, value, ref_range, abnormal in trend_data:
        status = ""
        if abnormal == 'H':
            status = " (HIGH)"
        elif abnormal == 'L':
            status = " (LOW)"

        print(f"{date}: {value} (Ref: {ref_range}){status}")

    # Calculate trend direction
    try:
        values = [float(result[1]) for result in trend_data if result[1].replace('.', '').replace('-', '').isdigit()]
        if len(values) >= 2:
            if values[-1] > values[0]:
                trend_direction = "Increasing"
            elif values[-1] < values[0]:
                trend_direction = "Decreasing"
            else:
                trend_direction = "Stable"

            change = values[-1] - values[0]
            percent_change = (change / values[0]) * 100 if values[0] != 0 else 0

            print(f"\nTrend Direction: {trend_direction}")
            print(f"Total Change: {change:+.2f}")
            print(f"Percent Change: {percent_change:+.1f}%")
    except ValueError:
        print("\nTrend analysis not available for non-numeric values.")

    conn.close()



def recent_lab_results_dashboard(auth):
    """Dashboard view of recent lab results"""
    conn = get_connection()
    cursor = conn.cursor()

    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

    cursor.execute('''
    SELECT lr.test_name, lr.result_value, lr.reference_range, lr.abnormal_flag,
           lr.resulted_date, s.first_name, s.last_name, s.student_id
    FROM lab_results lr
    JOIN students s ON lr.student_id = s.student_id
    WHERE lr.resulted_date >= ?
    ORDER BY lr.resulted_date DESC, lr.abnormal_flag DESC
    LIMIT 20
    ''', (seven_days_ago,))

    recent_results = cursor.fetchall()

    print("\n===== Recent Lab Results (Last 7 Days) =====")

    if not recent_results:
        print("No lab results in the last 7 days.")
        conn.close()
        return

    critical_count = 0

    for test, value, ref_range, abnormal, date, first_name, last_name, student_id in recent_results:
        if abnormal in ['H', 'L']:
            critical_count += 1
            flag = "🔴 HIGH" if abnormal == 'H' else "🔵 LOW"
            print(f"\n{flag} {test}: {value}")
        else:
            print(f"\n✅ {test}: {value}")

        print(f"   Patient: {first_name} {last_name} (ID: {student_id})")
        print(f"   Date: {date}")
        print(f"   Reference: {ref_range}")

    print(f"\nSummary: {len(recent_results)} results, {critical_count} abnormal")

    if critical_count > 0:
        print("⚠️ Critical values require provider follow-up")

    conn.close()



