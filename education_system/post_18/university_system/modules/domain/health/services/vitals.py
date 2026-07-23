from __future__ import annotations

from datetime import datetime, timedelta
from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.infrastructure.database.data_backup import backup_before_operation
from education_system.post_18.university_system.modules.domain.health.services.audit import log_audit_event
from education_system.post_18.university_system.modules.domain.health.services.contacts import get_user_student_id
from education_system.post_18.university_system.core.i18n import get_text as _t

def manage_vital_signs(auth):
    if not auth or not auth.current_user:
        print(_t("health_misc.vitals.login_required"))
        return

    while True:
        print(_t("health_misc.vitals.menu_title"))
        print(_t("health_misc.vitals.menu_option_record"))
        print(_t("health_misc.vitals.menu_option_view"))
        print(_t("health_misc.vitals.menu_option_trends"))
        print(_t("health_misc.vitals.menu_option_bmi"))
        print(_t("health_misc.vitals.menu_option_return"))

        choice = input(_t("health_misc.vitals.enter_choice"))

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
            print(_t("health_misc.vitals.invalid_choice"))

def record_vital_signs(auth):
    if not auth.check_permission('manage_health_records'):
        print(_t("health_misc.vitals.no_permission_record"))
        return

    backup_before_operation('record_vital_signs')

    conn = get_connection()
    cursor = conn.cursor()

    student_id = input(_t("health_misc.vitals.enter_student_id"))

    # Verify student exists
    cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
    if cursor.fetchone()[0] == 0:
        print(_t("health_misc.vitals.error_student_not_found"))
        conn.close()
        return

    while True:
        measurement_date = input(_t("health_misc.vitals.measurement_date_prompt")).strip()
        if not measurement_date:
            measurement_date = datetime.now().strftime('%Y-%m-%d')
            break
        try:
            datetime.strptime(measurement_date, '%Y-%m-%d')
            break
        except ValueError:
            print(_t("health_misc.vitals.invalid_date_format"))

    # Blood pressure
    bp_systolic = input(_t("health_misc.vitals.bp_systolic_prompt")).strip()
    bp_systolic = int(bp_systolic) if bp_systolic.isdigit() else None

    bp_diastolic = input(_t("health_misc.vitals.bp_diastolic_prompt")).strip()
    bp_diastolic = int(bp_diastolic) if bp_diastolic.isdigit() else None

    # Heart rate
    heart_rate = input(_t("health_misc.vitals.heart_rate_prompt")).strip()
    heart_rate = int(heart_rate) if heart_rate.isdigit() else None

    # Temperature
    temperature = input(_t("health_misc.vitals.temperature_prompt")).strip()
    temperature = float(temperature) if temperature.replace('.', '').isdigit() else None

    # Weight
    weight = input(_t("health_misc.vitals.weight_prompt")).strip()
    weight = float(weight) if weight.replace('.', '').isdigit() else None

    # Height
    height = input(_t("health_misc.vitals.height_prompt")).strip()
    height = float(height) if height.replace('.', '').isdigit() else None

    # Calculate BMI if both height and weight are provided
    bmi = None
    if height and weight:
        bmi = round((weight / (height ** 2)) * 703, 1)  # BMI formula

    recorded_by = f"{auth.current_user['username']}"
    notes = input(_t("health_misc.vitals.additional_notes_prompt"))
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

    print(_t("health_misc.vitals.record_success"))

    # Show any alerts
    alerts = check_vital_signs_alerts(bp_systolic, bp_diastolic, heart_rate, temperature, bmi)
    if alerts:
        print(_t("health_misc.vitals.alerts_header"))
        for alert in alerts:
            print(_t("health_misc.vitals.alert_item", alert=alert))

    conn.close()

def check_vital_signs_alerts(bp_sys, bp_dia, hr, temp, bmi):
    """Check for vital signs that are outside normal ranges"""
    alerts = []

    if bp_sys:
        if bp_sys >= 140:
            alerts.append(_t("health_misc.vitals.alert_high_systolic_bp"))
        elif bp_sys < 90:
            alerts.append(_t("health_misc.vitals.alert_low_systolic_bp"))

    if bp_dia:
        if bp_dia >= 90:
            alerts.append(_t("health_misc.vitals.alert_high_diastolic_bp"))
        elif bp_dia < 60:
            alerts.append(_t("health_misc.vitals.alert_low_diastolic_bp"))

    if hr:
        if hr > 100:
            alerts.append(_t("health_misc.vitals.alert_high_heart_rate"))
        elif hr < 60:
            alerts.append(_t("health_misc.vitals.alert_low_heart_rate"))

    if temp:
        if temp >= 100.4:
            alerts.append(_t("health_misc.vitals.alert_fever"))
        elif temp < 96.0:
            alerts.append(_t("health_misc.vitals.alert_low_temperature"))

    if bmi:
        if bmi >= 30:
            alerts.append(_t("health_misc.vitals.alert_bmi_obesity"))
        elif bmi < 18.5:
            alerts.append(_t("health_misc.vitals.alert_bmi_underweight"))

    return alerts

def view_vital_signs(auth):
    if not (auth.check_permission('view_any_health_record') or auth.check_permission('view_own_health_record')):
        print(_t("health_misc.vitals.no_permission_view"))
        return

    conn = get_connection()
    cursor = conn.cursor()

    if auth.check_permission('view_any_health_record'):
        student_id = input(_t("health_misc.vitals.enter_student_id"))

        cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
        if cursor.fetchone()[0] == 0:
            print(_t("health_misc.vitals.error_student_not_found"))
            conn.close()
            return
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print(_t("health_misc.vitals.error_no_student_id"))
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
        print(_t("health_misc.vitals.no_records_found"))
        conn.close()
        return

    print(_t("health_misc.vitals.records_title"))
    for record in vital_signs:
        vs_id, date, bp_sys, bp_dia, hr, temp, weight, height, bmi, recorded_by, notes = record

        print(_t("health_misc.vitals.record_date", date=date))
        print(_t("health_misc.vitals.record_recorded_by", recorded_by=recorded_by))

        if bp_sys and bp_dia:
            print(_t("health_misc.vitals.record_blood_pressure", systolic=bp_sys, diastolic=bp_dia))

        if hr:
            print(_t("health_misc.vitals.record_heart_rate", rate=hr))

        if temp:
            print(_t("health_misc.vitals.record_temperature", temp=temp))

        if weight:
            print(_t("health_misc.vitals.record_weight", weight=weight))

        if height:
            print(_t("health_misc.vitals.record_height", height=height))

        if bmi:
            print(_t("health_misc.vitals.record_bmi", bmi=bmi))

        if notes:
            print(_t("health_misc.vitals.record_notes", notes=notes))

        # Check for alerts
        alerts = check_vital_signs_alerts(bp_sys, bp_dia, hr, temp, bmi)
        if alerts:
            print(_t("health_misc.vitals.alerts_label"))
            for alert in alerts:
                print(_t("health_misc.vitals.alert_item_indented", alert=alert))

        print("-" * 30)

    conn.close()

def view_vital_signs_trends(auth):
    """View trends in vital signs over time"""
    if not (auth.check_permission('view_any_health_record') or auth.check_permission('view_own_health_record')):
        print(_t("health_misc.vitals.no_permission_trends"))
        return

    conn = get_connection()
    cursor = conn.cursor()

    if auth.check_permission('view_any_health_record'):
        student_id = input(_t("health_misc.vitals.enter_student_id"))

        cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
        if cursor.fetchone()[0] == 0:
            print(_t("health_misc.vitals.error_student_not_found"))
            conn.close()
            return
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print(_t("health_misc.vitals.error_no_student_id"))
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
        print(_t("health_misc.vitals.no_records_12_months"))
        conn.close()
        return

    print(_t("health_misc.vitals.trends_title", student_id=student_id))
    print(_t("health_misc.vitals.trends_period"))

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
        print(_t("health_misc.vitals.trend_systolic_bp", avg=f"{avg_bp_sys:.1f}", min_val=min(bp_sys_values), max_val=max(bp_sys_values)))

    if bp_dia_values:
        avg_bp_dia = sum(bp_dia_values) / len(bp_dia_values)
        print(_t("health_misc.vitals.trend_diastolic_bp", avg=f"{avg_bp_dia:.1f}", min_val=min(bp_dia_values), max_val=max(bp_dia_values)))

    if hr_values:
        avg_hr = sum(hr_values) / len(hr_values)
        print(_t("health_misc.vitals.trend_heart_rate", avg=f"{avg_hr:.1f}", min_val=min(hr_values), max_val=max(hr_values)))

    if temp_values:
        avg_temp = sum(temp_values) / len(temp_values)
        print(_t("health_misc.vitals.trend_temperature", avg=f"{avg_temp:.1f}", min_val=f"{min(temp_values):.1f}", max_val=f"{max(temp_values):.1f}"))

    if weight_values:
        weight_change = weight_values[-1] - weight_values[0] if len(weight_values) > 1 else 0
        print(_t("health_misc.vitals.trend_weight", current=weight_values[-1], change=f"{weight_change:+.1f}"))

    if bmi_values:
        bmi_change = bmi_values[-1] - bmi_values[0] if len(bmi_values) > 1 else 0
        print(_t("health_misc.vitals.trend_bmi", current=bmi_values[-1], change=f"{bmi_change:+.1f}"))

    print(_t("health_misc.vitals.total_measurements", count=len(records)))
    print(_t("health_misc.vitals.date_range", start=dates[0], end=dates[-1]))

    conn.close()

def calculate_bmi(auth):
    """BMI calculator utility"""
    print(_t("health_misc.vitals.bmi_calculator_title"))

    try:
        weight = float(input(_t("health_misc.vitals.bmi_enter_weight")))
        height = float(input(_t("health_misc.vitals.bmi_enter_height")))

        bmi = round((weight / (height ** 2)) * 703, 1)

        print(_t("health_misc.vitals.bmi_result", bmi=bmi))

        if bmi < 18.5:
            category = _t("health_misc.vitals.bmi_category_underweight")
        elif bmi < 25:
            category = _t("health_misc.vitals.bmi_category_normal")
        elif bmi < 30:
            category = _t("health_misc.vitals.bmi_category_overweight")
        else:
            category = _t("health_misc.vitals.bmi_category_obese")

        print(_t("health_misc.vitals.bmi_category_label", category=category))

        # Health recommendations
        if bmi < 18.5:
            print(_t("health_misc.vitals.recommendation_underweight"))
        elif bmi >= 30:
            print(_t("health_misc.vitals.recommendation_obese"))
        elif bmi >= 25:
            print(_t("health_misc.vitals.recommendation_overweight"))
        else:
            print(_t("health_misc.vitals.recommendation_normal"))

    except ValueError:
        print(_t("health_misc.vitals.invalid_numeric_input"))
