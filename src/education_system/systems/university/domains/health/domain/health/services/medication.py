from __future__ import annotations

from datetime import datetime, timedelta

from education_system.systems.university.domains.health.infrastructure.health.storage import get_connection
from education_system.systems.university.infrastructure.i18n import get_text as _t

def track_medication_adherence(auth):
    """Track medication adherence for students"""
    if not auth.check_permission('manage_health_records'):
        print(_t("health.medication.permission_denied_track", default="Permission Denied Track."))
        return

    conn = get_connection()
    cursor = conn.cursor()

    student_id = input(_t("health.medication.enter_student_id", default="Enter Student ID: "))

    cursor.execute('''
    SELECT p.id, p.medication_name, p.dosage, p.frequency, p.start_date
    FROM prescriptions p
    WHERE p.student_id = ? AND p.status = 'active'
    ORDER BY p.start_date DESC
    ''', (student_id,))

    active_prescriptions = cursor.fetchall()

    if not active_prescriptions:
        print(_t("health.medication.no_active_prescriptions", default="No Active Prescriptions."))
        conn.close()
        return

    print(f"\n===== {_t('health.medication.adherence_tracking_title', student_id=student_id, default='===== ADHERENCE TRACKING ===== {student_id}')} =====")

    for prescription in active_prescriptions:
        presc_id, medication, dosage, frequency, start_date = prescription

        print(f"\n{_t('health.medication.medication_label', default='Medication:')}: {medication} ({dosage})")
        print(f"{_t('health.medication.frequency_label', default='Frequency:')}: {frequency}")
        print(f"{_t('health.medication.started_label', default='Started:')}: {start_date}")

        # The clinician's estimate of doses taken, as a percentage, classed
        # against the usual 80% / 95% thresholds.
        adherence = input(_t("health.medication.adherence_level_prompt", default="Adherence Level: "))
        try:
            adherence_pct = int(adherence)
            if 0 <= adherence_pct <= 100:
                if adherence_pct < 80:
                    print(_t("health.medication.poor_adherence", default="Poor Adherence"))
                elif adherence_pct < 95:
                    print(_t("health.medication.moderate_adherence", default="Moderate Adherence"))
                else:
                    print(_t("health.medication.good_adherence", default="Good Adherence"))
            else:
                print(_t("health.medication.invalid_percentage", default="Enter a percentage between 0 and 100."))
        except ValueError:
            print(_t("health.medication.invalid_input", default="Invalid input. Please try again."))

    conn.close()

def manage_refill_reminders(auth):
    """Manage prescription refill reminders"""
    if not auth.check_permission('manage_health_records'):
        print(_t("health.medication.permission_denied_refill", default="Permission Denied Refill."))
        return

    conn = get_connection()
    cursor = conn.cursor()

    print(f"\n===== {_t('health.medication.refill_reminders_title', default='===== REFILL REMINDERS =====')} =====")

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
        print(_t("health.medication.no_refills_needed", default="No Refills Needed."))
        conn.close()
        return

    print(_t("health.medication.prescriptions_requiring_refills", default="Prescriptions Requiring Refills"))

    for prescription in upcoming_refills:
        presc_id, student_id, first_name, last_name, medication, dosage, end_date, pharmacy = prescription

        print(f"\n{_t('health.medication.student_label', default='Student:')}: {first_name} {last_name} (ID: {student_id})")
        print(f"{_t('health.medication.medication_label', default='Medication:')}: {medication} ({dosage})")
        print(f"{_t('health.medication.expires_label', default='Expires:')}: {end_date}")
        print(f"{_t('health.medication.pharmacy_label', default='Pharmacy:')}: {pharmacy}")

        days_until_expiry = (datetime.strptime(end_date, '%Y-%m-%d') - datetime.now()).days

        if days_until_expiry <= 7:
            print(_t("health.medication.urgent_expires_7_days", default="Urgent Expires 7 Days"))
        elif days_until_expiry <= 14:
            print(_t("health.medication.warning_expires_14_days", default="Warning Expires 14 Days"))
        else:
            print(_t("health.medication.info_expires_30_days", default="Info Expires 30 Days"))

        # Option to send reminder
        send_reminder = input(_t("health.medication.send_reminder_prompt", default="Send Reminder: ")).lower()
        if send_reminder == 'y':
            _send_refill_reminder(cursor, student_id, f"{first_name} {last_name}", medication,
                                  dosage, end_date, pharmacy)

        print("-" * 30)

    conn.close()


def _send_refill_reminder(cursor, student_id, name, medication, dosage, end_date, pharmacy):
    """E-mail the student a refill reminder through the university outbox
    and say honestly what happened to it."""
    from education_system.systems.university.domains.health.application.health import notices
    row = cursor.execute("SELECT email_address FROM students WHERE student_id = ?",
                         (student_id,)).fetchone()
    email = row[0] if row else None
    if not email:
        print(f"No e-mail address on record for {name}; no reminder was sent.")
        return
    try:
        from education_system.systems.university.infrastructure.email.email_service import send_email
        queued = send_email(email, "Prescription refill reminder",
                            f"Dear {name},\n\nYour prescription for {medication} ({dosage}) ends on "
                            f"{end_date}. Please arrange a refill with {pharmacy or 'your pharmacy'} "
                            "or book an appointment at the Health Centre if you still need it.\n\n"
                            "University Health Centre")
    except Exception as exc:
        print(f"The reminder could not be queued: {exc}")
        return
    if not queued:
        print("The reminder could not be queued (the e-mail service refused it).")
        return
    print(_t("health.medication.reminder_sent", name=name, default="Reminder Sent: {name}"))
    print(notices.delivery_note())
