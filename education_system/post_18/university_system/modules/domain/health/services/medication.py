from __future__ import annotations

from datetime import datetime, timedelta

from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.core.i18n import get_text as _t

def track_medication_adherence(auth):
    """Track medication adherence for students"""
    if not auth.check_permission('manage_health_records'):
        print(_t("health.medication.permission_denied_track"))
        return

    conn = get_connection()
    cursor = conn.cursor()

    student_id = input(_t("health.medication.enter_student_id"))

    cursor.execute('''
    SELECT p.id, p.medication_name, p.dosage, p.frequency, p.start_date
    FROM prescriptions p
    WHERE p.student_id = ? AND p.status = 'active'
    ORDER BY p.start_date DESC
    ''', (student_id,))

    active_prescriptions = cursor.fetchall()

    if not active_prescriptions:
        print(_t("health.medication.no_active_prescriptions"))
        conn.close()
        return

    print(f"\n===== {_t('health.medication.adherence_tracking_title', student_id=student_id)} =====")

    for prescription in active_prescriptions:
        presc_id, medication, dosage, frequency, start_date = prescription

        print(f"\n{_t('health.medication.medication_label')}: {medication} ({dosage})")
        print(f"{_t('health.medication.frequency_label')}: {frequency}")
        print(f"{_t('health.medication.started_label')}: {start_date}")

        # Simple adherence tracking (in real system, this would be more sophisticated)
        adherence = input(_t("health.medication.adherence_level_prompt"))
        try:
            adherence_pct = int(adherence)
            if 0 <= adherence_pct <= 100:
                if adherence_pct < 80:
                    print(_t("health.medication.poor_adherence"))
                elif adherence_pct < 95:
                    print(_t("health.medication.moderate_adherence"))
                else:
                    print(_t("health.medication.good_adherence"))
            else:
                print(_t("health.medication.invalid_percentage"))
        except ValueError:
            print(_t("health.medication.invalid_input"))

    conn.close()

def manage_refill_reminders(auth):
    """Manage prescription refill reminders"""
    if not auth.check_permission('manage_health_records'):
        print(_t("health.medication.permission_denied_refill"))
        return

    conn = get_connection()
    cursor = conn.cursor()

    print(f"\n===== {_t('health.medication.refill_reminders_title')} =====")

    # Find prescriptions that might need refills soon
    thirty_days_from_now = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

    cursor.execute('''
    SELECT p.id, s.student_id, s.first_name, s.last_name, p.medication_name,
           p.dosage, p.end_date, p.pharmacy
    FROM prescriptions p
    JOIN students s ON p.student_id = s.student_id
    WHERE p.status = 'active' AND p.end_date IS NOT NULL AND p.end_date <= ?
    ORDER BY p.end_date
    ''', (thirty_days_from_now,))

    upcoming_refills = cursor.fetchall()

    if not upcoming_refills:
        print(_t("health.medication.no_refills_needed"))
        conn.close()
        return

    print(_t("health.medication.prescriptions_requiring_refills"))

    for prescription in upcoming_refills:
        presc_id, student_id, first_name, last_name, medication, dosage, end_date, pharmacy = prescription

        print(f"\n{_t('health.medication.student_label')}: {first_name} {last_name} (ID: {student_id})")
        print(f"{_t('health.medication.medication_label')}: {medication} ({dosage})")
        print(f"{_t('health.medication.expires_label')}: {end_date}")
        print(f"{_t('health.medication.pharmacy_label')}: {pharmacy}")

        days_until_expiry = (datetime.strptime(end_date, '%Y-%m-%d') - datetime.now()).days

        if days_until_expiry <= 7:
            print(_t("health.medication.urgent_expires_7_days"))
        elif days_until_expiry <= 14:
            print(_t("health.medication.warning_expires_14_days"))
        else:
            print(_t("health.medication.info_expires_30_days"))

        # Option to send reminder
        send_reminder = input(_t("health.medication.send_reminder_prompt")).lower()
        if send_reminder == 'y':
            # In a real system, this would send an email or SMS
            print(_t("health.medication.reminder_sent", name=f"{first_name} {last_name}"))

        print("-" * 30)

    conn.close()
