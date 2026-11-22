# Standard library imports
import logging

logger = logging.getLogger(__name__)

import csv
import hashlib
import hmac
import json
import logging
import os
import random
import requests
import smtplib
from education_system.systems.university.domains.health.infrastructure.health.storage import sqlite3
import statistics
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Third-party imports
from cryptography.fernet import Fernet

# Project imports - database
from education_system.systems.university.domains.health.infrastructure.health.storage import DatabaseManager, get_connection
from education_system.systems.university.infrastructure.database.data_backup import backup_before_operation

# Project imports - authentication
from education_system.systems.university.infrastructure.auth import UserAuth

# Project imports - core/utils
from education_system.systems.university.infrastructure.logging.log_config import configure_logging
from education_system.systems.university.infrastructure.email import (
    send_appointment_confirmation,
    send_health_notification,
)

# Project imports - services
from education_system.systems.university.domains.health.domain.health.services import (
    critical_alerts_dashboard,
    pending_tasks,
    quick_patient_lookup,
    patient_queue,
    block_time_slots,
    get_user_student_id,
    log_audit_event,
)
from education_system.systems.university.domains.health.domain.health.records.screening.guidelines import screening_guidelines
from education_system.systems.university.domains.health.domain.health.records.screening.reminders import screening_reminders, population_screening_reports
from education_system.systems.university.domains.health.domain.health.records.screening.results import record_screening_results
from education_system.systems.university.domains.health.domain.health.records.screening.schedules import calculate_screening_due_date, view_due_screenings, overdue_screenings
from education_system.systems.university.domains.health.domain.health.records.clinical.lab_results import recent_lab_results_dashboard
from education_system.systems.university.domains.health.domain.health.records.vaccinations.tracking import vaccination_due_list
from education_system.systems.university.domains.health.domain.health.prompting import ask as _ask
from education_system.systems.university.domains.health.domain.health.appointments.clinic_diary_cli import (  # noqa: E402,F401
    manage_provider_time_off, schedule_templates, manage_waiting_list, give_appointment_feedback,
    _reschedule_into_new, _other_clinic_appointments,
)

# Configure logging for audit trail
audit_logger = configure_logging(name=__name__)

# Encryption key management


# ---------------------------------------------------------------------------
# Notifying the student
# ---------------------------------------------------------------------------
# Appointments go through the university email system
# (infrastructure.email): render_template fills one of the JSON templates
# under assets/templates/email/campus_services/health/ and send_email stores
# the mail *and* raises the student's inbox message, so it appears in the
# Email module like any other university mail.

_APPOINTMENT_TEMPLATE_DIR = "campus_services/health"
APPOINTMENT_CREATED_TEMPLATE = f"{_APPOINTMENT_TEMPLATE_DIR}/health_appointment_created"
APPOINTMENT_UPDATED_TEMPLATE = f"{_APPOINTMENT_TEMPLATE_DIR}/health_appointment_updated"

_appointment_logger = logging.getLogger(__name__)


def _send_appointment_email(template_name, recipient_email, template_vars):
    """Render *template_name* and hand it to the university email system.

    Best-effort: a missing address or a delivery failure is logged and
    reported as False rather than raised — the appointment is already
    committed by the time we notify, so failing here would misreport a
    booking that did happen.
    """
    address = (recipient_email or '').strip()
    if not address:
        _appointment_logger.warning(
            "Appointment email '%s' not sent: no recipient address", template_name)
        return False
    try:
        from education_system.systems.university.infrastructure.email.email_service import (
            send_email,
        )
        from education_system.systems.university.infrastructure.email.template_utils import (
            render_template,
        )
    except ImportError as exc:
        _appointment_logger.warning(
            "Appointment email '%s' not sent: email system unavailable (%s)",
            template_name, exc)
        return False
    try:
        subject, body = render_template(template_name, template_vars)
        if subject is None or body is None:
            _appointment_logger.error(
                "Appointment email '%s' not sent: template failed to render",
                template_name)
            return False
        send_email(recipient_email=address, subject=subject, body=body)
        return True
    except Exception as exc:
        _appointment_logger.exception(
            "Appointment email '%s' to %s failed: %s", template_name, address, exc)
        return False


def _appointment_email_context(cursor, appointment_id):
    """Everything the appointment emails need, or None if it is gone."""
    cursor.execute('''
    SELECT ha.id, ha.student_id, s.first_name, s.last_name, s.email_address,
           ha.appointment_type, ha.appointment_date, ha.appointment_time,
           ha.provider, ha.reason, ha.status, ha.notes, ha.scheduled_at
    FROM health_appointments ha
    JOIN students s ON ha.student_id = s.student_id
    WHERE ha.id = ?
    ''', (appointment_id,))
    row = cursor.fetchone()
    if not row:
        return None
    return {
        'appointment_id': row[0],
        'student_id': row[1],
        'student_name': f"{row[2] or ''} {row[3] or ''}".strip() or row[1],
        'student_email': row[4],
        'appointment_type': row[5],
        'appointment_date': row[6],
        'appointment_time': row[7],
        'provider': row[8],
        'reason': row[9] or 'Not recorded.',
        'status': row[10],
        'notes': row[11] or 'None recorded.',
        'scheduled_at': row[12],
    }


def _appointment_base_vars(context):
    return {k: v for k, v in context.items() if k != 'student_email'}


def notify_appointment_created(context):
    """Tell the student their appointment has been booked."""
    return _send_appointment_email(APPOINTMENT_CREATED_TEMPLATE,
                                   context.get('student_email'),
                                   _appointment_base_vars(context))


def notify_appointment_updated(context, changes, updated_by):
    """Tell the student their appointment changed, and exactly what changed.

    *changes* is ``[(field, old, new), ...]``.
    """
    if changes:
        change_list = "\n".join(
            f"  - {field}: '{old if old not in (None, '') else 'not set'}' "
            f"-> '{new if new not in (None, '') else 'not set'}'"
            for field, old, new in changes)
    else:
        change_list = "  (no changes recorded)"

    template_vars = _appointment_base_vars(context)
    template_vars.update({
        'change_list': change_list,
        'updated_by': updated_by,
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    })
    return _send_appointment_email(APPOINTMENT_UPDATED_TEMPLATE,
                                   context.get('student_email'), template_vars)


def manage_provider_schedules(auth):
    """Provider schedule management system"""
    if not auth.check_permission('manage_health_appointments'):
        print("You don't have permission to manage provider schedules.")
        return
    
    while True:
        print("\n===== Provider Schedule Management =====")
        print("1. Add Provider Schedule")
        print("2. View Provider Schedules")
        print("3. Update Schedule")
        print("4. Block Time Slots")
        print("5. Holiday/Vacation Management")
        print("6. Schedule Templates")
        print("7. Provider Availability Report")
        print("8. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-8): ")
        
        if choice == '1':
            add_provider_schedule(auth)
        elif choice == '2':
            view_provider_schedules(auth)
        elif choice == '3':
            update_provider_schedule(auth)
        elif choice == '4':
            block_time_slots(auth)
        elif choice == '5':
            manage_provider_time_off(auth)
        elif choice == '6':
            schedule_templates(auth)
        elif choice == '7':
            provider_availability_report(auth)
        elif choice == '8':
            break
        else:
            print("Invalid choice. Please try again.")

def add_provider_schedule(auth, values=None):
    """Add provider schedule"""
    backup_before_operation('add_provider_schedule')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    provider_name = _ask(values, "provider_name", "Provider name: ")
    
    days_of_week = [
        ('Monday', 1), ('Tuesday', 2), ('Wednesday', 3), ('Thursday', 4),
        ('Friday', 5), ('Saturday', 6), ('Sunday', 0)
    ]
    
    print("\nDays of Week:")
    for i, (day_name, day_num) in enumerate(days_of_week):
        print(f"{i+1}. {day_name}")
    
    while True:
        day_choice = _ask(values, "day", "\nSelect day (1-7): ")
        if day_choice.isdigit() and 1 <= int(day_choice) <= 7:
            day_of_week = days_of_week[int(day_choice) - 1][1]
            break
        print("Invalid choice. Please try again.")
    
    while True:
        start_time = _ask(values, "start_time", "Start time (HH:MM): ")
        try:
            datetime.strptime(start_time, '%H:%M')
            break
        except ValueError:
            print("Invalid time format. Please use HH:MM.")
    
    while True:
        end_time = _ask(values, "end_time", "End time (HH:MM): ")
        try:
            datetime.strptime(end_time, '%H:%M')
            break
        except ValueError:
            print("Invalid time format. Please use HH:MM.")
    
    max_appointments = _ask(values, "max_appointments", "Maximum appointments per hour [4]: ").strip()
    if not max_appointments:
        max_appointments = 4
    else:
        max_appointments = int(max_appointments)
    
    specialty = _ask(values, "specialty", "Specialty: ")
    location = _ask(values, "location", "Location: ")
    
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO provider_schedules 
    (provider_name, day_of_week, start_time, end_time, max_appointments, 
     specialty, location, active, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (provider_name, day_of_week, start_time, end_time, max_appointments,
          specialty, location, 1, created_at))
    
    conn.commit()
    log_audit_event(auth.current_user['id'], 'add_provider_schedule', 'provider_schedule', cursor.lastrowid)
    print("\nProvider schedule added successfully!")
    conn.close()

def view_provider_schedules(auth, values=None):
    """View provider schedules"""
    conn = get_connection()
    cursor = conn.cursor()
    
    provider_filter = _ask(values, "provider_filter", "Filter by provider name (leave blank for all): ").strip()
    
    if provider_filter:
        cursor.execute('''
        SELECT id, provider_name, day_of_week, start_time, end_time, 
               max_appointments, specialty, location, active
        FROM provider_schedules
        WHERE provider_name LIKE ? AND active = 1
        ORDER BY provider_name, day_of_week
        ''', (f'%{provider_filter}%',))
    else:
        cursor.execute('''
        SELECT id, provider_name, day_of_week, start_time, end_time, 
               max_appointments, specialty, location, active
        FROM provider_schedules
        WHERE active = 1
        ORDER BY provider_name, day_of_week
        ''')
    
    schedules = cursor.fetchall()
    
    if not schedules:
        print("No provider schedules found.")
        conn.close()
        return
    
    print("\n===== Provider Schedules =====")
    
    days_map = {0: 'Sunday', 1: 'Monday', 2: 'Tuesday', 3: 'Wednesday', 
                4: 'Thursday', 5: 'Friday', 6: 'Saturday'}
    
    current_provider = ""
    for schedule in schedules:
        sched_id, provider, day_num, start_time, end_time, max_appts, specialty, location, active = schedule
        
        if provider != current_provider:
            print(f"\nProvider: {provider}")
            print(f"Specialty: {specialty}")
            print(f"Location: {location}")
            print("-" * 40)
            current_provider = provider
        
        day_name = days_map.get(day_num, f"Day {day_num}")
        print(f"  {day_name}: {start_time} - {end_time} (Max: {max_appts} appts/hour)")
    
    conn.close()

def show_upcoming_appointments(auth):
    """Show upcoming appointments"""
    student_id = get_user_student_id(auth)
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get upcoming appointments
    today = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute('''
    SELECT appointment_type, appointment_date, appointment_time, provider, reason, status
    FROM health_appointments
    WHERE student_id = ? AND appointment_date >= ? AND status = 'scheduled'
    ORDER BY appointment_date, appointment_time
    LIMIT 10
    ''', (student_id, today))
    
    appointments = cursor.fetchall()
    
    if not appointments:
        print("\nNo upcoming appointments scheduled.")
        conn.close()
        return
    
    print("\n===== Your Upcoming Appointments =====")
    
    for apt_type, apt_date, apt_time, provider, reason, status in appointments:
        print(f"\nDate: {apt_date} at {apt_time}")  # lgtm[py/clear-text-logging-sensitive-data]
        print(f"Type: {apt_type}")  # lgtm[py/clear-text-logging-sensitive-data]
        print(f"Provider: {provider}")  # lgtm[py/clear-text-logging-sensitive-data]
        print(f"Reason: {reason}")  # lgtm[py/clear-text-logging-sensitive-data]

        # Calculate days until appointment
        apt_datetime = datetime.strptime(apt_date, '%Y-%m-%d')
        days_until = (apt_datetime - datetime.now()).days
        
        if days_until == 0:
            print("📅 TODAY")
        elif days_until == 1:
            print("📅 TOMORROW")
        elif days_until <= 7:
            print(f"📅 In {days_until} days")
        
        print("-" * 30)
    
    conn.close()

def provider_dashboard(auth):
    """Healthcare provider dashboard"""
    if not auth.check_permission('manage_health_records'):
        print("This dashboard is only available to healthcare providers.")
        return
    
    while True:
        print("\n===== Provider Dashboard =====")
        print("1. Today's Schedule")
        print("2. Patient Queue")
        print("3. Critical Alerts")
        print("4. Pending Tasks")
        print("5. Recent Lab Results")
        print("6. Vaccination Due List")
        print("7. Provider Statistics")
        print("8. Quick Patient Lookup")
        print("9. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-9): ")
        
        if choice == '1':
            todays_schedule(auth)
        elif choice == '2':
            patient_queue(auth)
        elif choice == '3':
            critical_alerts_dashboard(auth)
        elif choice == '4':
            pending_tasks(auth)
        elif choice == '5':
            recent_lab_results_dashboard(auth)
        elif choice == '6':
            vaccination_due_list(auth)
        elif choice == '7':
            provider_statistics(auth)
        elif choice == '8':
            quick_patient_lookup(auth)
        elif choice == '9':
            break
        else:
            print("Invalid choice. Please try again.")

def todays_schedule(auth):
    """Show today's schedule for provider"""
    conn = get_connection()
    cursor = conn.cursor()
    
    provider_name = f"Dr. {auth.current_user['username']}"
    today = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute('''
    SELECT ha.appointment_time, s.first_name, s.last_name, s.student_id,
           ha.appointment_type, ha.reason, ha.status
    FROM health_appointments ha
    JOIN students s ON ha.student_id = s.student_id
    WHERE ha.provider = ? AND ha.appointment_date = ?
    ORDER BY ha.appointment_time
    ''', (provider_name, today))
    
    appointments = cursor.fetchall()
    
    print(f"\n===== Today's Schedule ({today}) =====")
    print(f"Provider: {provider_name}")
    
    if not appointments:
        print("No appointments scheduled for today.")
        conn.close()
        return
    
    current_time = datetime.now().time()
    
    for apt_time, first_name, last_name, student_id, apt_type, reason, status in appointments:
        apt_time_obj = datetime.strptime(apt_time, '%H:%M').time()
        
        # Status indicator
        if apt_time_obj < current_time:
            if status == 'completed':
                indicator = "✅"
            elif status == 'no-show':
                indicator = "❌"
            else:
                indicator = "⏰"  # Past due
        else:
            indicator = "📅"  # Upcoming
        
        print(f"\n{indicator} {apt_time} - {first_name} {last_name} (ID: {student_id})")
        print(f"    Type: {apt_type}")
        print(f"    Reason: {reason}")
        print(f"    Status: {status}")
    
    conn.close()

def manage_screening_schedules(auth):
    """Preventive screening schedule management"""
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to manage screening schedules.")
        return
    
    while True:
        print("\n===== Screening Schedule Management =====")
        print("1. Create Screening Schedule")
        print("2. View Due Screenings")
        print("3. Schedule Screening Appointment")
        print("4. Record Screening Results")
        print("5. Screening Reminders")
        print("6. Population Screening Reports")
        print("7. Screening Guidelines")
        print("8. Overdue Screenings")
        print("9. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-9): ")
        
        if choice == '1':
            create_screening_schedule(auth)
        elif choice == '2':
            view_due_screenings(auth)
        elif choice == '3':
            schedule_screening_appointment(auth)
        elif choice == '4':
            record_screening_results(auth)
        elif choice == '5':
            screening_reminders(auth)
        elif choice == '6':
            population_screening_reports(auth)
        elif choice == '7':
            screening_guidelines(auth)
        elif choice == '8':
            overdue_screenings(auth)
        elif choice == '9':
            break
        else:
            print("Invalid choice. Please try again.")

def create_screening_schedule(auth, values=None):
    """Create screening schedule for student"""
    backup_before_operation('create_screening_schedule')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    student_id = _ask(values, "student_id", "Enter student ID: ")
    
    # Verify student exists
    cursor.execute("SELECT first_name, last_name, age FROM students WHERE student_id = ?", (student_id,))
    student = cursor.fetchone()
    if not student:
        print("Error: Student ID not found.")
        conn.close()
        return
    
    first_name, last_name, age = student
    print(f"Creating screening schedule for: {first_name} {last_name} (Age: {age})")
    
    # Common screening types
    screening_types = [
        'Annual Physical Exam',
        'Blood Pressure Screening',
        'Cholesterol Screening',
        'Diabetes Screening',
        'Mental Health Screening',
        'STI Screening',
        'Cancer Screening',
        'Vision Screening',
        'Hearing Screening',
        'Other'
    ]
    
    print("\nScreening Types:")
    for i, screening in enumerate(screening_types):
        print(f"{i+1}. {screening}")
    
    while True:
        choice = _ask(values, "screening_type_choice", "\nSelect screening type (1-10): ")
        if choice.isdigit() and 1 <= int(choice) <= len(screening_types):
            screening_type = screening_types[int(choice) - 1]
            if screening_type == 'Other':
                screening_type = _ask(values, "screening_type", "Enter screening type: ")
            break
        print("Invalid choice. Please try again.")
    
    # Calculate due date based on age and screening type
    due_date = calculate_screening_due_date(screening_type, age)
    
    while True:
        due_date_input = _ask(values, "due_date", f"Due date (YYYY-MM-DD) [recommended: {due_date}]: ").strip()
        if not due_date_input:
            due_date_input = due_date
            break
        try:
            datetime.strptime(due_date_input, '%Y-%m-%d')
            due_date = due_date_input
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    provider = _ask(values, "provider", f"Provider [Dr. {auth.current_user['username']}]: ").strip()
    if not provider:
        provider = f"Dr. {auth.current_user['username']}"
    
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
    INSERT INTO screening_schedules 
    (student_id, screening_type, due_date, status, provider, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (student_id, screening_type, due_date, 'due', provider, created_at))
    
    conn.commit()
    log_audit_event(auth.current_user['id'], 'create_screening_schedule', 'screening_schedule', cursor.lastrowid)
    
    print("\nScreening schedule created successfully!")
    print(f"Screening: {screening_type}")
    print(f"Due Date: {due_date}")
    
    conn.close()

def schedule_screening_appointment(auth, values=None):
    """Schedule appointment for screening"""
    backup_before_operation('schedule_screening_appointment')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    screening_id = _ask(values, "screening_id", "Enter screening ID to schedule: ")
    
    cursor.execute('''
    SELECT ss.id, s.student_id, s.first_name, s.last_name, ss.screening_type
    FROM screening_schedules ss
    JOIN students s ON ss.student_id = s.student_id
    WHERE ss.id = ? AND ss.status = 'due'
    ''', (screening_id,))
    
    screening = cursor.fetchone()
    
    if not screening:
        print("Error: Screening not found or already completed.")
        conn.close()
        return
    
    screen_id, student_id, first_name, last_name, screening_type = screening
    
    print("\nScheduling appointment for:")
    print(f"Patient: {first_name} {last_name}")
    print(f"Screening: {screening_type}")
    
    while True:
        appointment_date = _ask(values, "appointment_date", "Appointment date (YYYY-MM-DD): ")
        try:
            datetime.strptime(appointment_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    while True:
        appointment_time = _ask(values, "appointment_time", "Appointment time (HH:MM): ")
        try:
            datetime.strptime(appointment_time, '%H:%M')
            break
        except ValueError:
            print("Invalid time format. Please use HH:MM.")
    
    provider = _ask(values, "provider", f"Provider [Dr. {auth.current_user['username']}]: ").strip()
    if not provider:
        provider = f"Dr. {auth.current_user['username']}"
    
    # Same booking checks as every other screen (application/health/diary).
    from education_system.systems.university.domains.health.application.health import diary
    diary.ensure_schema(conn)
    check = diary.check_booking(conn, student_id=student_id, provider=provider,
                                date=appointment_date, time=appointment_time)
    override_reason = None
    if not check.ok:
        print("⚠️  " + check.summary().replace("\n", "\n⚠️  "))
        if not check.blocked:
            override_reason = _ask(values, "override_reason",
                                   "Book anyway? Enter the reason (blank to cancel): ").strip()
        if not override_reason or len(override_reason) < 5:
            print("Not booked.")
            conn.close()
            return

    # Create appointment
    appointment_id = diary.book(conn, student_id=student_id, appointment_type=screening_type,
                                date=appointment_date, time=appointment_time, provider=provider,
                                reason=f"Screening: {screening_type}",
                                has_conflict=bool(override_reason))
    if override_reason:
        diary.record_booking_override(conn, auth.current_user.get('username'), appointment_id,
                                      check, override_reason)
    
    # Update screening schedule
    cursor.execute('''
    UPDATE screening_schedules 
    SET status = 'scheduled'
    WHERE id = ?
    ''', (screening_id,))
    
    conn.commit()
    log_audit_event(auth.current_user['id'], 'schedule_screening_appointment', 'appointment', appointment_id)
    
    print("\nScreening appointment scheduled successfully!")
    print(f"Appointment ID: {appointment_id}")
    print(f"Date: {appointment_date} at {appointment_time}")
    print(f"Provider: {provider}")
    
    conn.close()
    diary.publish_booking(appointment_id, student_id=student_id, date=appointment_date,
                          time=appointment_time, provider=provider,
                          appointment_type=screening_type)

def provider_availability_report(auth):
    """Generate provider availability report"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Provider Availability Report =====")
    
    # Get provider schedules
    cursor.execute('''
    SELECT provider_name, day_of_week, start_time, end_time, max_appointments
    FROM provider_schedules
    WHERE active = 1
    ORDER BY provider_name, day_of_week
    ''')
    
    schedules = cursor.fetchall()
    
    if not schedules:
        print("No provider schedules found.")
        conn.close()
        return
    
    # Calculate weekly availability
    days_map = {0: 'Sunday', 1: 'Monday', 2: 'Tuesday', 3: 'Wednesday', 
                4: 'Thursday', 5: 'Friday', 6: 'Saturday'}
    
    provider_availability = {}
    
    for provider, day_num, start_time, end_time, max_appts in schedules:
        if provider not in provider_availability:
            provider_availability[provider] = {}
        
        # Calculate hours per day
        start_hour = int(start_time.split(':')[0])
        end_hour = int(end_time.split(':')[0])
        hours_per_day = end_hour - start_hour
        
        provider_availability[provider][day_num] = {
            'hours': hours_per_day,
            'max_appointments': max_appts * hours_per_day,
            'day_name': days_map[day_num]
        }
    
    print("Weekly Provider Availability:")
    for provider, schedule in provider_availability.items():
        total_hours = sum(day_info['hours'] for day_info in schedule.values())
        total_capacity = sum(day_info['max_appointments'] for day_info in schedule.values())
        
        print(f"\n{provider}:")
        print(f"  Total Weekly Hours: {total_hours}")
        print(f"  Total Weekly Capacity: {total_capacity} appointments")
        
        for day_num in sorted(schedule.keys()):
            day_info = schedule[day_num]
            print(f"  {day_info['day_name']}: {day_info['hours']} hours, {day_info['max_appointments']} appointments")
    
    conn.close()

def update_provider_schedule(auth, values=None):
    """Update existing provider schedule"""
    backup_before_operation('update_provider_schedule')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Show existing schedules
    cursor.execute('''
    SELECT id, provider_name, day_of_week, start_time, end_time, max_appointments
    FROM provider_schedules
    WHERE active = 1
    ORDER BY provider_name, day_of_week
    ''')
    
    schedules = cursor.fetchall()
    
    if not schedules:
        print("No provider schedules found.")
        conn.close()
        return
    
    print("\nExisting Provider Schedules:")
    days_map = {0: 'Sunday', 1: 'Monday', 2: 'Tuesday', 3: 'Wednesday', 
                4: 'Thursday', 5: 'Friday', 6: 'Saturday'}
    
    for schedule in schedules:
        sched_id, provider, day_num, start_time, end_time, max_appts = schedule
        day_name = days_map.get(day_num, f"Day {day_num}")
        print(f"{sched_id}. {provider} - {day_name}: {start_time}-{end_time} (Max: {max_appts})")
    
    schedule_id = _ask(values, "schedule_id", "\nEnter schedule ID to update: ")
    
    cursor.execute('''
    SELECT id, provider_name, day_of_week, start_time, end_time, max_appointments
    FROM provider_schedules
    WHERE id = ?
    ''', (schedule_id,))
    
    current_schedule = cursor.fetchone()
    
    if not current_schedule:
        print("Error: Schedule not found.")
        conn.close()
        return
    
    sched_id, provider, day_num, current_start, current_end, current_max = current_schedule
    day_name = days_map.get(day_num, f"Day {day_num}")
    
    print(f"\nUpdating schedule for {provider} on {day_name}")
    print(f"Current: {current_start}-{current_end}, Max appointments: {current_max}")
    
    new_start = _ask(values, "start_time", f"New start time (HH:MM) [{current_start}]: ").strip()
    if not new_start:
        new_start = current_start
    
    new_end = _ask(values, "end_time", f"New end time (HH:MM) [{current_end}]: ").strip()
    if not new_end:
        new_end = current_end
    
    new_max = _ask(values, "max_appointments", f"New max appointments [{current_max}]: ").strip()
    if not new_max:
        new_max = current_max
    else:
        new_max = int(new_max)
    
    cursor.execute('''
    UPDATE provider_schedules 
    SET start_time = ?, end_time = ?, max_appointments = ?
    WHERE id = ?
    ''', (new_start, new_end, new_max, schedule_id))
    
    conn.commit()
    log_audit_event(auth.current_user['id'], 'update_provider_schedule', 'provider_schedule', schedule_id)
    
    print("\nProvider schedule updated successfully!")
    print(f"New schedule: {new_start}-{new_end}, Max appointments: {new_max}")
    
    conn.close()

def provider_statistics(auth):
    """Provider performance statistics"""
    conn = get_connection()
    cursor = conn.cursor()
    
    provider_name = f"Dr. {auth.current_user['username']}"
    
    print(f"\n===== Statistics for {provider_name} =====")
    
    # This month's statistics
    first_day_of_month = datetime.now().replace(day=1).strftime('%Y-%m-%d')
    
    # Appointments
    cursor.execute('''
    SELECT 
        COUNT(*) as total_appointments,
        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
        SUM(CASE WHEN status = 'no-show' THEN 1 ELSE 0 END) as no_shows,
        SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled
    FROM health_appointments
    WHERE provider = ? AND appointment_date >= ?
    ''', (provider_name, first_day_of_month))
    
    apt_stats = cursor.fetchone()
    
    if apt_stats and apt_stats[0] > 0:
        total, completed, no_shows, cancelled = apt_stats
        completion_rate = (completed / total * 100) if total > 0 else 0
        no_show_rate = (no_shows / total * 100) if total > 0 else 0
        
        print("📅 APPOINTMENT STATISTICS (This Month):")
        print(f"   Total Scheduled: {total}")
        print(f"   Completed: {completed} ({completion_rate:.1f}%)")
        print(f"   No-Shows: {no_shows} ({no_show_rate:.1f}%)")
        print(f"   Cancelled: {cancelled}")
    
    # Health records created
    cursor.execute('''
    SELECT COUNT(*) FROM health_records
    WHERE provider = ? AND record_date >= ?
    ''', (provider_name, first_day_of_month))
    
    records_created = cursor.fetchone()[0]
    
    print("\n📋 DOCUMENTATION:")
    print(f"   Health Records Created: {records_created}")
    
    # Vaccinations administered
    cursor.execute('''
    SELECT COUNT(*) FROM vaccination_records
    WHERE administered_by = ? AND administered_date >= ?
    ''', (provider_name, first_day_of_month))
    
    vaccinations = cursor.fetchone()[0]
    
    print(f"   Vaccinations Administered: {vaccinations}")
    
    # Referrals made
    cursor.execute('''
    SELECT COUNT(*) FROM referrals
    WHERE referring_provider = ? AND referral_date >= ?
    ''', (provider_name, first_day_of_month))
    
    referrals = cursor.fetchone()[0]
    
    print(f"   Referrals Made: {referrals}")
    
    # Patient satisfaction: real post-appointment feedback (appointment_feedback).
    from education_system.systems.university.domains.health.application.health import diary
    sat = diary.satisfaction(conn, provider_name, since=first_day_of_month)
    print("\n⭐ PATIENT SATISFACTION (this month):")
    if not sat["responses"]:
        print("   No feedback received yet.")
    else:
        print(f"   Average Rating: {sat['average']}/5.0 ({sat['responses']} response(s))")
        if sat["response_rate"] is not None:
            print(f"   Response Rate: {sat['response_rate']}%")
        print(f"   Rated 4 or 5: {sat['positive_pct']}%")
    
    conn.close()

def schedule_appointment(auth):
    if not (auth.check_permission('schedule_health_appointment') or auth.check_permission('manage_health_appointments')):
        print("You don't have permission to schedule appointments.")
        return
    
    backup_before_operation('schedule_appointment')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    if auth.current_user['role'] in ['admin', 'health_provider']:
        student_id = input("Enter student ID: ")
        
        cursor.execute("SELECT first_name, last_name FROM students WHERE student_id = ?", (student_id,))
        student = cursor.fetchone()
        if not student:
            print("Error: Student ID not found.")
            conn.close()
            return
        
        print(f"Scheduling appointment for: {student[0]} {student[1]}")
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return
    
    # Appointment types
    appointment_types = [
        'General Check-up',
        'Follow-up Visit',
        'Vaccination',
        'Mental Health Consultation',
        'Injury Assessment',
        'Chronic Care Management',
        'Preventive Screening',
        'Emergency Consultation'
    ]
    
    print("\nAppointment Types:")
    for i, apt_type in enumerate(appointment_types):
        print(f"{i+1}. {apt_type}")
    
    while True:
        type_choice = input("\nSelect appointment type (1-8): ")
        if type_choice.isdigit() and 1 <= int(type_choice) <= len(appointment_types):
            appointment_type = appointment_types[int(type_choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    while True:
        appointment_date = input("Appointment date (YYYY-MM-DD): ")
        try:
            datetime.strptime(appointment_date, '%Y-%m-%d')
            # Check if date is not in the past
            if datetime.strptime(appointment_date, '%Y-%m-%d') < datetime.now():
                print("Cannot schedule appointments in the past.")
                continue
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
    
    while True:
        appointment_time = input("Appointment time (HH:MM): ")
        try:
            datetime.strptime(appointment_time, '%H:%M')
            break
        except ValueError:
            print("Invalid time format. Please use HH:MM (24-hour format).")
    
    provider = input("Provider: ")
    reason = input("Reason for appointment: ")
    
    # Booking checks across every clinic (application/health/diary): time
    # off blocks; a clash (provider or student) or a schedule problem
    # (outside hours / day full) needs an override with a reason.
    from education_system.systems.university.domains.health.application.health import diary
    diary.ensure_schema(conn)
    check = diary.check_booking(conn, student_id=student_id, provider=provider,
                                date=appointment_date, time=appointment_time)
    override_reason = None
    if not check.ok:
        print("⚠️  " + check.summary().replace("\n", "\n⚠️  "))
        if not check.blocked and auth.current_user['role'] in ['admin', 'health_provider']:
            override_reason = input("Book anyway? Enter the reason (blank to cancel): ").strip()
            if len(override_reason) < 5:
                override_reason = None
        if not override_reason:
            if input("Join the waiting list for this appointment type instead? (y/n): ").strip().lower() == 'y':
                wid = diary.join_waitlist(conn, student_id=student_id, appointment_type=appointment_type,
                                          provider=provider or None, preferred_from=appointment_date,
                                          notes=reason, by=auth.current_user.get('username'))
                conn.commit()
                print(f"Added to the waiting list (entry {wid}); a freed slot will be offered by e-mail.")
            conn.close()
            return

    appointment_id = diary.book(conn, student_id=student_id, appointment_type=appointment_type,
                                date=appointment_date, time=appointment_time, provider=provider,
                                reason=reason, has_conflict=bool(override_reason))
    if override_reason:
        diary.record_booking_override(conn, auth.current_user.get('username'), appointment_id,
                                      check, override_reason)
    conn.commit()

    log_audit_event(auth.current_user['id'], 'schedule_appointment', 'appointment', appointment_id)

    print("\nAppointment scheduled successfully!")
    print(f"Appointment ID: {appointment_id}")
    print(f"Date: {appointment_date} at {appointment_time}")
    print(f"Provider: {provider}")

    try:
        from education_system.systems.university.services.bus.integration_bus import (
            publish_health_appointment,
        )
        publish_health_appointment(
            appointment_id=int(appointment_id),
            student_id=str(student_id),
            appointment_date=str(appointment_date),
            appointment_time=str(appointment_time),
            provider=provider,
            appointment_type=appointment_type,
        )
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)
    
    # Confirmation email.
    #
    # This used to call send_appointment_confirmation(...) without
    # appointment_type — a required positional — so every booking logged
    #   send_appointment_confirmation() missing 1 required positional
    #   argument: 'appointment_type'
    # and no student was ever told. It also printed "Confirmation email sent."
    # from inside the try regardless of whether anything was sent. It now goes
    # through the same notifier the update path uses, reading back the
    # committed row so the email states what was actually stored.
    context = _appointment_email_context(cursor, appointment_id)
    conn.close()

    if context:
        if notify_appointment_created(context):
            print(f"Confirmation emailed to {context['student_email']}.")
        else:
            print("Note: the confirmation email could not be sent.")

def view_appointments(auth):
    if not (auth.check_permission('view_own_appointments') or auth.check_permission('manage_health_appointments')):
        print("You don't have permission to view appointments.")
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    if auth.check_permission('manage_health_appointments'):
        view_option = input("View appointments for: (1) Specific student (2) All students (3) Specific provider: ")
        
        if view_option == '1':
            student_id = input("Enter student ID: ")
            cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
            if cursor.fetchone()[0] == 0:
                print("Error: Student ID not found.")
                conn.close()
                return
            
            cursor.execute('''
            SELECT id, appointment_type, appointment_date, appointment_time, provider,
                   reason, status, scheduled_at
            FROM health_appointments
            WHERE student_id = ?
            ORDER BY appointment_date DESC, appointment_time DESC
            ''', (student_id,))
        
        elif view_option == '2':
            cursor.execute('''
            SELECT ha.id, s.student_id, s.first_name, s.last_name, ha.appointment_type,
                   ha.appointment_date, ha.appointment_time, ha.provider, ha.status
            FROM health_appointments ha
            JOIN students s ON ha.student_id = s.student_id
            ORDER BY ha.appointment_date DESC, ha.appointment_time DESC
            LIMIT 100
            ''')
        
        elif view_option == '3':
            provider = input("Enter provider name: ")
            cursor.execute('''
            SELECT ha.id, s.student_id, s.first_name, s.last_name, ha.appointment_type,
                   ha.appointment_date, ha.appointment_time, ha.reason, ha.status
            FROM health_appointments ha
            JOIN students s ON ha.student_id = s.student_id
            WHERE ha.provider LIKE ?
            ORDER BY ha.appointment_date DESC, ha.appointment_time DESC
            ''', (f'%{provider}%',))
        
        else:
            print("Invalid option.")
            conn.close()
            return
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return
        
        cursor.execute('''
        SELECT id, appointment_type, appointment_date, appointment_time, provider,
               reason, status, scheduled_at
        FROM health_appointments
        WHERE student_id = ?
        ORDER BY appointment_date DESC, appointment_time DESC
        ''', (student_id,))
    
    appointments = cursor.fetchall()
    
    if not appointments:
        print("No appointments found.")
        try:
            if not auth.check_permission('manage_health_appointments') or view_option == '1':
                _other_clinic_appointments(conn, student_id=student_id)
            elif view_option == '3':
                _other_clinic_appointments(conn, provider=provider)
        except Exception:
            logger.debug("Other clinics' appointments not listed", exc_info=True)
        conn.close()
        return
    
    print("\n===== Appointments =====")
    for appointment in appointments:
        if auth.check_permission('manage_health_appointments') and view_option in ['2', '3']:
            # All appointments or provider view
            apt_id, student_id, first_name, last_name, apt_type, apt_date, apt_time, provider_or_reason, status = appointment
            print(f"\nID: {apt_id}")
            print(f"Student: {first_name} {last_name} (ID: {student_id})")
            print(f"Type: {apt_type}")
            print(f"Date: {apt_date} at {apt_time}")
            if view_option == '2':
                print(f"Provider: {provider_or_reason}")
            else:
                print(f"Reason: {provider_or_reason}")
            print(f"Status: {status}")
        else:
            # Specific student view
            apt_id, apt_type, apt_date, apt_time, provider, reason, status, scheduled_at = appointment
            print(f"\nID: {apt_id}")
            print(f"Type: {apt_type}")
            print(f"Date: {apt_date} at {apt_time}")
            print(f"Provider: {provider}")
            print(f"Reason: {reason}")
            print(f"Status: {status}")
            print(f"Scheduled: {scheduled_at}")
        
        # Status indicators
        if status == 'scheduled':
            print("📅 SCHEDULED")
        elif status == 'completed':
            print("✅ COMPLETED")
        elif status == 'cancelled':
            print("❌ CANCELLED")
        elif status == 'no-show':
            print("⚠️ NO-SHOW")
        
        print("-" * 30)

    try:
        if auth.check_permission('manage_health_appointments') and view_option == '3':
            _other_clinic_appointments(conn, provider=provider)
        elif not auth.check_permission('manage_health_appointments') or view_option == '1':
            _other_clinic_appointments(conn, student_id=student_id)
    except Exception:
        logger.debug("Other clinics' appointments not listed", exc_info=True)
    
    conn.close()

def update_appointment(auth):
    """Edit an appointment's details and tell the student exactly what changed.

    Separate from update_appointment_status: that moves the appointment
    through its lifecycle, this changes the booking itself (type, date, time,
    provider, reason, notes).
    """
    if not auth.check_permission('manage_health_appointments'):
        print("You don't have permission to update appointments.")
        return

    backup_before_operation('update_appointment')

    conn = get_connection()
    cursor = conn.cursor()

    appointment_id = input("Enter appointment ID to update: ").strip()
    if not appointment_id:
        print("An appointment ID is required.")
        conn.close()
        return

    before = _appointment_email_context(cursor, appointment_id)
    if not before:
        print("Error: Appointment not found.")
        conn.close()
        return

    print("\nCurrent Appointment Details:")
    print(f"Student:  {before['student_name']} ({before['student_id']})")
    print(f"Type:     {before['appointment_type']}")
    print(f"Date:     {before['appointment_date']}")
    print(f"Time:     {before['appointment_time']}")
    print(f"Provider: {before['provider']}")
    print(f"Reason:   {before['reason']}")
    print(f"Notes:    {before['notes']}")
    print(f"Status:   {before['status']}")

    print("\nLeave a field blank to keep its current value.")

    appointment_type = input(f"Appointment type [{before['appointment_type']}]: ").strip() \
        or before['appointment_type']

    appointment_date = before['appointment_date']
    while True:
        raw = input(f"Date YYYY-MM-DD [{appointment_date}]: ").strip()
        if not raw:
            break
        try:
            datetime.strptime(raw, '%Y-%m-%d')
            appointment_date = raw
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    appointment_time = before['appointment_time']
    while True:
        raw = input(f"Time HH:MM [{appointment_time}]: ").strip()
        if not raw:
            break
        try:
            datetime.strptime(raw, '%H:%M')
            appointment_time = raw
            break
        except ValueError:
            print("Invalid time format. Please use HH:MM.")

    provider = input(f"Provider [{before['provider']}]: ").strip() or before['provider']

    current_reason = '' if before['reason'] == 'Not recorded.' else before['reason']
    reason = input(f"Reason [{current_reason or 'none'}]: ").strip() or current_reason

    current_notes = '' if before['notes'] == 'None recorded.' else before['notes']
    notes = input(f"Notes [{current_notes or 'none'}]: ").strip() or current_notes

    changes = []
    for label, old, new in [
        ("Type", before['appointment_type'], appointment_type),
        ("Date", before['appointment_date'], appointment_date),
        ("Time", before['appointment_time'], appointment_time),
        ("Provider", before['provider'], provider),
        ("Reason", current_reason, reason),
        ("Notes", current_notes, notes),
    ]:
        if (old or '') != (new or ''):
            changes.append((label, old, new))

    if not changes:
        print("\nNothing was changed.")
        conn.close()
        return

    print("\nAbout to apply these changes:")
    for label, old, new in changes:
        print(f"  - {label}: '{old or 'not set'}' -> '{new or 'not set'}'")

    if input("\nApply these changes? (y/n): ").strip().lower() != 'y':
        print("Operation cancelled. Nothing has been changed.")
        conn.close()
        return

    cursor.execute('''
    UPDATE health_appointments
    SET appointment_type = ?, appointment_date = ?, appointment_time = ?,
        provider = ?, reason = ?, notes = ?
    WHERE id = ?
    ''', (appointment_type, appointment_date, appointment_time, provider,
          reason, notes, appointment_id))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'update_appointment', 'appointment',
                    appointment_id,
                    "; ".join(f"{label}: {old} -> {new}" for label, old, new in changes))

    after = _appointment_email_context(cursor, appointment_id)
    conn.close()

    print(f"\nAppointment {appointment_id} updated ({len(changes)} change(s)).")

    if after:
        updated_by = auth.current_user.get('username', 'the Health Centre')
        if notify_appointment_updated(after, changes, updated_by):
            print(f"Update emailed to {after['student_email']}.")
        else:
            print("Note: the update email could not be sent.")


def update_appointment_status(auth):
    if not auth.check_permission('manage_health_appointments'):
        print("You don't have permission to update appointment status.")
        return
    
    backup_before_operation('update_appointment_status')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    appointment_id = input("Enter appointment ID to update: ")
    
    cursor.execute('''
    SELECT ha.id, s.student_id, s.first_name, s.last_name, ha.appointment_type,
           ha.appointment_date, ha.appointment_time, ha.provider, ha.status
    FROM health_appointments ha
    JOIN students s ON ha.student_id = s.student_id
    WHERE ha.id = ?
    ''', (appointment_id,))
    
    appointment = cursor.fetchone()
    
    if not appointment:
        print("Error: Appointment not found.")
        conn.close()
        return
    
    apt_id, student_id, first_name, last_name, apt_type, apt_date, apt_time, provider, current_status = appointment
    
    print("\nAppointment Details:")
    print(f"Student: {first_name} {last_name} (ID: {student_id})")
    print(f"Type: {apt_type}")
    print(f"Date: {apt_date} at {apt_time}")
    print(f"Provider: {provider}")
    print(f"Current Status: {current_status}")
    
    status_options = ['scheduled', 'completed', 'cancelled', 'no-show', 'rescheduled']
    print("\nStatus Options:")
    for i, status in enumerate(status_options):
        print(f"{i+1}. {status}")
    
    while True:
        choice = input("\nSelect new status (1-5): ")
        if choice.isdigit() and 1 <= int(choice) <= len(status_options):
            new_status = status_options[int(choice) - 1]
            break
        print("Invalid choice. Please try again.")
    
    notes = input("Additional notes (optional): ")
    
    cursor.execute('''
    UPDATE health_appointments 
    SET status = ?, notes = ?
    WHERE id = ?
    ''', (new_status, notes, appointment_id))
    # A cancelled or rescheduled slot is offered to the waiting list.
    from education_system.systems.university.domains.health.application.health import diary
    offers = []
    if new_status in ('cancelled', 'rescheduled'):
        offers = diary.offer_freed_slot(conn, date=apt_date, time=apt_time, provider=provider,
                                        appointment_type=apt_type)
    conn.commit()
    diary.send_emails(offers)
    if offers:
        print("The freed slot was offered to the waiting list.")
    log_audit_event(auth.current_user['id'], 'update_appointment_status', 'appointment', appointment_id,
                   f"Status changed from {current_status} to {new_status}")
    
    print(f"\nAppointment status updated to '{new_status}' successfully!")

    # A status change is exactly the kind of thing the student needs to hear
    # about — a cancellation they never learn of is a wasted slot and a missed
    # appointment. Reuses the update email so the change is spelled out.
    after = _appointment_email_context(cursor, appointment_id)

    # If rescheduled, book the new time now (same type and provider), with the
    # same checks as a new booking, and send the rescheduled e-mail.
    if new_status == 'rescheduled':
        reschedule = input("Schedule new appointment now? (y/n): ").lower()
        if reschedule == 'y':
            _reschedule_into_new(auth, conn, student_id, apt_type, provider, apt_date, apt_time,
                                 after)
    elif new_status == 'completed':
        print("The patient will be asked for feedback by e-mail.")
        rating = input("Is the patient here to rate it now? Rating 1-5 (blank to skip): ").strip()
        if rating.isdigit():
            try:
                diary.submit_feedback(conn, source="health_appointments", appointment_id=apt_id,
                                      student_id=student_id, rating=int(rating),
                                      comments=input("Comments (optional): ").strip() or None)
                conn.commit()
                print("Feedback recorded.")
            except (ValueError, LookupError) as exc:
                print(f"Feedback not recorded: {exc}")

    conn.close()

    if after:
        updated_by = auth.current_user.get('username', 'the Health Centre')
        status_change = [("Status", current_status, new_status)]
        if notes and notes != (after.get('notes') or ''):
            status_change.append(("Notes", '', notes))
        if notify_appointment_updated(after, status_change, updated_by):
            print(f"Status change emailed to {after['student_email']}.")
        else:
            print("Note: the status-change email could not be sent.")

def generate_provider_utilization_report(auth, start_date, end_date):
    """Generate provider utilization report"""
    conn = get_connection()
    cursor = conn.cursor()
    
    report_content = []
    report_content.append("PROVIDER UTILIZATION REPORT")
    report_content.append("=" * 30)
    report_content.append(f"Period: {start_date} to {end_date}")
    report_content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_content.append("")
    
    # Provider workload from appointments
    cursor.execute('''
    SELECT provider, COUNT(*) as appointment_count,
           SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
           SUM(CASE WHEN status = 'no-show' THEN 1 ELSE 0 END) as no_shows
    FROM health_appointments
    WHERE appointment_date BETWEEN ? AND ?
    GROUP BY provider
    ORDER BY appointment_count DESC
    ''', (start_date, end_date))
    
    provider_data = cursor.fetchall()
    
    if provider_data:
        report_content.append("APPOINTMENT STATISTICS BY PROVIDER")
        report_content.append("-" * 35)
        for provider, total, completed, no_shows in provider_data:
            completion_rate = (completed / total * 100) if total > 0 else 0
            no_show_rate = (no_shows / total * 100) if total > 0 else 0
            report_content.append(f"{provider}:")
            report_content.append(f"  Total: {total}, Completed: {completed} ({completion_rate:.1f}%)")
            report_content.append(f"  No-shows: {no_shows} ({no_show_rate:.1f}%)")
    
    # Health records by provider
    cursor.execute('''
    SELECT provider, COUNT(*) as record_count
    FROM health_records
    WHERE record_date BETWEEN ? AND ?
    GROUP BY provider
    ORDER BY record_count DESC
    ''', (start_date, end_date))
    
    records_data = cursor.fetchall()
    
    if records_data:
        report_content.append("")
        report_content.append("HEALTH RECORDS BY PROVIDER")
        report_content.append("-" * 27)
        for provider, count in records_data:
            report_content.append(f"{provider}: {count} records")
    
    # Display report
    for line in report_content:
        print(line)
    
    conn.close()

def generate_appointment_schedule_report(auth):
    """Generate appointment schedule report"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Appointment Schedule Report =====")
    
    # Get date range
    start_date = input("Start date (YYYY-MM-DD) [today]: ").strip()
    if not start_date:
        start_date = datetime.now().strftime('%Y-%m-%d')
    
    end_date = input("End date (YYYY-MM-DD) [7 days from start]: ").strip()
    if not end_date:
        end_date = (datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=7)).strftime('%Y-%m-%d')
    
    # Appointments by date
    cursor.execute('''
    SELECT appointment_date, appointment_time, provider, appointment_type,
           s.first_name, s.last_name, ha.status
    FROM health_appointments ha
    JOIN students s ON ha.student_id = s.student_id
    WHERE ha.appointment_date BETWEEN ? AND ?
    ORDER BY ha.appointment_date, ha.appointment_time
    ''', (start_date, end_date))
    
    appointments = cursor.fetchall()
    
    if not appointments:
        print("No appointments found in the specified date range.")
        conn.close()
        return
    
    print(f"\nAppointments from {start_date} to {end_date}:")
    print("-" * 80)
    
    current_date = ""
    for apt_date, apt_time, provider, apt_type, first_name, last_name, status in appointments:
        if apt_date != current_date:
            print(f"\n{apt_date}:")
            current_date = apt_date
        
        status_indicator = "✓" if status == "completed" else "○" if status == "scheduled" else "✗"
        print(f"  {apt_time} - {provider} - {apt_type}")
        print(f"    Patient: {first_name} {last_name} {status_indicator}")
    
    # Summary statistics
    cursor.execute('''
    SELECT provider, COUNT(*) as appointment_count
    FROM health_appointments
    WHERE appointment_date BETWEEN ? AND ?
    GROUP BY provider
    ORDER BY appointment_count DESC
    ''', (start_date, end_date))
    
    provider_stats = cursor.fetchall()
    
    if provider_stats:
        print("\nProvider Workload Summary:")
        print("-" * 30)
        for provider, count in provider_stats:
            print(f"{provider}: {count} appointments")
    
    conn.close()

def generate_provider_performance_report(auth):
    """Generate provider performance report"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Provider Performance Report =====")
    
    # Get date range
    start_date = input("Start date (YYYY-MM-DD) [30 days ago]: ").strip()
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    end_date = input("End date (YYYY-MM-DD) [today]: ").strip()
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    print(f"\nProvider Performance: {start_date} to {end_date}")
    print("-" * 60)
    
    # Appointment metrics by provider
    cursor.execute('''
    SELECT provider,
           COUNT(*) as total_appointments,
           SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
           SUM(CASE WHEN status = 'no-show' THEN 1 ELSE 0 END) as no_shows,
           SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled
    FROM health_appointments
    WHERE appointment_date BETWEEN ? AND ?
    GROUP BY provider
    ORDER BY total_appointments DESC
    ''', (start_date, end_date))
    
    appointment_metrics = cursor.fetchall()
    
    if appointment_metrics:
        print("Appointment Performance:")
        print(f"{'Provider':<20} {'Total':<6} {'Completed':<10} {'No-Shows':<9} {'Cancelled':<9}")
        print("-" * 60)
        
        for provider, total, completed, no_shows, cancelled in appointment_metrics:
            completion_rate = (completed / total * 100) if total > 0 else 0
            no_show_rate = (no_shows / total * 100) if total > 0 else 0
            
            print(f"{provider:<20} {total:<6} {completed:<3}({completion_rate:.1f}%) {no_shows:<3}({no_show_rate:.1f}%) {cancelled:<9}")
    
    # Health records documentation
    cursor.execute('''
    SELECT provider, COUNT(*) as record_count,
           AVG(LENGTH(description)) as avg_description_length
    FROM health_records
    WHERE record_date BETWEEN ? AND ?
    AND provider IS NOT NULL AND provider != ''
    GROUP BY provider
    ORDER BY record_count DESC
    ''', (start_date, end_date))
    
    documentation_metrics = cursor.fetchall()
    
    if documentation_metrics:
        print("\nDocumentation Quality:")
        print(f"{'Provider':<20} {'Records':<8} {'Avg Length':<12}")
        print("-" * 45)
        
        for provider, count, avg_length in documentation_metrics:
            avg_length = avg_length or 0
            print(f"{provider:<20} {count:<8} {avg_length:.1f} chars")
    
    # Patient satisfaction metrics require patient feedback data.
    print("\nPatient Satisfaction:")
    print("(Patient feedback system required for satisfaction metrics)")
    
    conn.close()

def show_appointment_utilization_stats(auth):
    """Show appointment utilization statistics"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Appointment Utilization Statistics =====")
    
    # This month's appointments
    first_day_of_month = datetime.now().replace(day=1).strftime('%Y-%m-%d')
    last_day_of_month = (datetime.now().replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    last_day_of_month = last_day_of_month.strftime('%Y-%m-%d')
    
    cursor.execute('''
    SELECT status, COUNT(*) as count
    FROM health_appointments
    WHERE appointment_date BETWEEN ? AND ?
    GROUP BY status
    ''', (first_day_of_month, last_day_of_month))
    
    monthly_stats = cursor.fetchall()
    
    if monthly_stats:
        print("This Month's Appointments:")
        total_appointments = sum(count for _, count in monthly_stats)
        for status, count in monthly_stats:
            print(f"  {status}: {count} ({count/total_appointments*100:.1f}%)")
    
    # Appointments by type
    cursor.execute('''
    SELECT appointment_type, COUNT(*) as count
    FROM health_appointments
    WHERE appointment_date >= ?
    GROUP BY appointment_type
    ORDER BY count DESC
    ''', (first_day_of_month,))
    
    appointment_types = cursor.fetchall()
    
    if appointment_types:
        print("\nAppointments by Type (This Month):")
        for apt_type, count in appointment_types:
            print(f"  {apt_type}: {count}")
    
    # Provider utilization
    cursor.execute('''
    SELECT provider, COUNT(*) as count
    FROM health_appointments
    WHERE appointment_date >= ?
    GROUP BY provider
    ORDER BY count DESC
    ''', (first_day_of_month,))
    
    provider_utilization = cursor.fetchall()
    
    if provider_utilization:
        print("\nProvider Utilization (This Month):")
        for provider, count in provider_utilization:
            print(f"  {provider}: {count} appointments")
    
    # No-show rate
    cursor.execute('''
    SELECT 
        SUM(CASE WHEN status = 'no-show' THEN 1 ELSE 0 END) as no_shows,
        COUNT(*) as total_appointments
    FROM health_appointments
    WHERE appointment_date >= ?
    ''', (first_day_of_month,))
    
    no_show_data = cursor.fetchone()
    if no_show_data and no_show_data[1] > 0:
        no_show_rate = (no_show_data[0] / no_show_data[1]) * 100
        print(f"\nNo-Show Rate: {no_show_data[0]}/{no_show_data[1]} ({no_show_rate:.1f}%)")
    
    conn.close()

def analyze_provider_workload(auth):
    """Analyze provider workload and performance"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Provider Workload Analysis =====")
    
    # This month's workload
    first_day_of_month = datetime.now().replace(day=1).strftime('%Y-%m-%d')
    
    cursor.execute('''
    SELECT 
        provider,
        COUNT(*) as appointment_count,
        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_count,
        SUM(CASE WHEN status = 'no-show' THEN 1 ELSE 0 END) as no_show_count
    FROM health_appointments
    WHERE appointment_date >= ?
    GROUP BY provider
    ORDER BY appointment_count DESC
    ''', (first_day_of_month,))
    
    provider_stats = cursor.fetchall()
    
    if provider_stats:
        print("Provider Workload (This Month):")
        for provider, appointments, completed, no_shows in provider_stats:
            completion_rate = (completed / appointments * 100) if appointments > 0 else 0
            no_show_rate = (no_shows / appointments * 100) if appointments > 0 else 0
            print(f"  {provider}:")
            print(f"    Total Appointments: {appointments}")
            print(f"    Completed: {completed} ({completion_rate:.1f}%)")
            print(f"    No-shows: {no_shows} ({no_show_rate:.1f}%)")
    
    # Health records created by provider
    cursor.execute('''
    SELECT 
        provider,
        COUNT(*) as record_count
    FROM health_records
    WHERE record_date >= ?
    GROUP BY provider
    ORDER BY record_count DESC
    ''', (first_day_of_month,))
    
    provider_records = cursor.fetchall()
    
    if provider_records:
        print("\nHealth Records Created (This Month):")
        for provider, count in provider_records:
            print(f"  {provider}: {count} records")
    
    conn.close()
