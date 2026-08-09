"""
Email notification functions for housing accommodation system.

This module handles all email-related functionality for housing:
- Application receipts and approvals
- Maintenance request notifications
- Payment confirmations
"""

from datetime import datetime, timedelta
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.utils.activity_logger import log_create

# Import email service for sending confirmations
try:
    from education_system.systems.university.infrastructure.email.email_service import send_email, send_email_as_system
    from education_system.systems.university.infrastructure.email.template_utils import render_template
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available")


def send_housing_email(email_type, student_id, application_data, additional_vars=None):
    """
    Send housing-related emails to students

    Args:
        email_type: Type of email ('receipt', 'approved', 'rejected')
        student_id: Student ID to send email to
        application_data: Dictionary containing application details
        additional_vars: Additional template variables (optional)

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    if not EMAIL_SERVICE_AVAILABLE:
        print(f"Email service not available - cannot send {email_type} email to student {student_id}")
        return False

    try:
        # Get student email and name from database
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT email_address, first_name, last_name
            FROM students
            WHERE student_id = ?
        ''', (student_id,))
        student_info = cursor.fetchone()
        conn.close()

        if not student_info or not student_info[0]:
            print(f"No email address found for student {student_id}")
            return False

        student_email = student_info[0]
        student_name = f"{student_info[1] or ''} {student_info[2] or ''}".strip() or "Student"

        # Map email types to template names
        template_map = {
            'receipt': 'accommodation_application_receipt',
            'approved': 'accommodation_approved',
            'rejected': 'accommodation_rejected'
        }

        template_name = template_map.get(email_type)
        if not template_name:
            print(f"Unknown email type: {email_type}")
            return False

        # Prepare template variables
        template_vars = {
            'student_name': student_name,
            'student_id': student_id,
            'accommodation_id': application_data.get('application_id', 'N/A'),
            'accommodation_type': application_data.get('preferred_room_type', 'N/A'),
            'description': application_data.get('special_requirements', 'No special requirements'),
            'start_date': application_data.get('requested_move_in_date', 'N/A'),
            'end_date': 'N/A',  # Calculate if duration available
            'status': application_data.get('status', 'N/A'),
            'submission_date': application_data.get('application_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        }

        # Calculate end date if duration available
        if application_data.get('requested_duration_months') and application_data.get('requested_move_in_date'):
            try:
                start_date = datetime.strptime(application_data['requested_move_in_date'], '%Y-%m-%d')
                duration = int(application_data['requested_duration_months'])
                end_date = start_date + timedelta(days=duration * 30)
                template_vars['end_date'] = end_date.strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                pass

        # Add additional variables if provided
        if additional_vars:
            template_vars.update(additional_vars)

        # Render template
        subject, body = render_template(template_name, template_vars)

        # Send email (using correct parameter name: recipient_email not recipient)
        send_email(
            recipient_email=student_email,
            subject=subject,
            body=body
        )

        # Log the email activity
        log_create('housing_email', f"Sent {email_type} email ({template_name}) to student {student_id}")

        print(f"✓ {email_type.title()} email sent to {student_name} ({student_email})")
        return True

    except Exception as e:
        print(f"✗ Failed to send {email_type} email to student {student_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


def send_maintenance_email(email_type, request_id, request_data, additional_vars=None):
    """
    Send maintenance request-related emails to students

    Args:
        email_type: Type of email ('created', 'completed', 'investigation')
        request_id: Request ID
        request_data: Dictionary containing request details
        additional_vars: Additional template variables (optional)

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    if not EMAIL_SERVICE_AVAILABLE:
        print(f"Email service not available - cannot send {email_type} email for request {request_id}")
        return False

    try:
        # Get student email and name from database
        student_id = request_data.get('student_id')
        if not student_id:
            print(f"No student_id provided for request {request_id}")
            return False

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT email_address, first_name, last_name
            FROM students
            WHERE student_id = ?
        ''', (student_id,))
        student_info = cursor.fetchone()
        conn.close()

        if not student_info or not student_info[0]:
            print(f"No email address found for student {student_id}")
            return False

        student_email = student_info[0]
        student_name = f"{student_info[1] or ''} {student_info[2] or ''}".strip() or "Student"

        # Map email types to template names
        template_map = {
            'created': 'maintenance_request_created',
            'completed': 'maintenance_request_completed',
            'investigation': 'maintenance_request_investigation'
        }

        template_name = template_map.get(email_type)
        if not template_name:
            print(f"Unknown email type: {email_type}")
            return False

        # Prepare template variables with comprehensive defaults
        template_vars = {
            'student_name': student_name,
            'student_id': student_id,
            'request_id': request_id,
            'issue_type': request_data.get('issue_type', 'N/A'),
            'priority': request_data.get('priority', 'Medium'),
            'created_by': student_name,
            'created_date': request_data.get('request_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            'location': request_data.get('location', 'N/A'),
            'description': request_data.get('description', 'No description provided'),
            'status': request_data.get('status', 'Open'),
            'assigned_to': request_data.get('assigned_to', 'Maintenance Team'),
            'scheduled_date': request_data.get('scheduled_date', 'To be determined'),
            'completion_date': request_data.get('completion_date', 'N/A'),
            'feedback': request_data.get('feedback', ''),
            'estimated_response': request_data.get('estimated_response', '2-3 business days'),
            'estimated_completion': request_data.get('estimated_completion', '5-7 business days'),

            # Additional variables for completed emails
            'completed_by': request_data.get('completed_by', 'Maintenance Team'),
            'resolution_time': request_data.get('resolution_time', 'N/A'),
            'work_performed': request_data.get('work_performed', request_data.get('feedback', 'Repair completed')),
            'resolution_notes': request_data.get('resolution_notes', ''),
            'materials_used': request_data.get('materials_used', 'Standard materials'),
            'follow_up_info': request_data.get('follow_up_info', 'None required'),
            'maintenance_tips': request_data.get('maintenance_tips', 'None'),
            'warranty_period': request_data.get('warranty_period', '30 days'),
            'warranty_coverage': request_data.get('warranty_coverage', 'Standard repair warranty'),
            'warranty_restrictions': request_data.get('warranty_restrictions', 'None'),

            # Additional variables for investigation emails
            'reviewed_by': request_data.get('reviewed_by', 'Maintenance Team'),
            'review_date': request_data.get('review_date', datetime.now().strftime('%Y-%m-%d')),
            'investigation_reason': request_data.get('investigation_reason', 'Further assessment required'),
            'root_cause_details': request_data.get('root_cause_details', 'To be determined during inspection'),
            'scope_details': request_data.get('scope_details', 'To be assessed'),
            'resource_requirements': request_data.get('resource_requirements', 'To be determined'),
            'inspection_date': request_data.get('inspection_date', 'To be scheduled'),
            'inspector_name': request_data.get('inspector_name', 'Maintenance Technician'),
            'inspection_scope': request_data.get('inspection_scope', 'Full diagnostic assessment'),
            'specialist_info': request_data.get('specialist_info', 'Will be determined if needed'),
            'parts_assessment': request_data.get('parts_assessment', 'To be evaluated'),
            'investigation_start': request_data.get('investigation_start', datetime.now().strftime('%Y-%m-%d')),
            'investigation_duration': request_data.get('investigation_duration', '2-3 business days'),
            'assessment_target': request_data.get('assessment_target', 'Within 1 week'),
            'inspection_appointment': request_data.get('inspection_appointment', 'To be scheduled'),
            'inspection_time': request_data.get('inspection_time', '30-60 minutes'),
            'special_requirements': request_data.get('special_requirements', 'None'),
            'access_instructions': request_data.get('access_instructions', 'Please ensure access to the affected area'),
            'action_item_1': request_data.get('action_item_1', 'Keep the area accessible'),
            'action_item_2': request_data.get('action_item_2', 'Respond to scheduling requests promptly'),
            'action_item_3': request_data.get('action_item_3', 'Report any changes in the issue'),
            'temporary_measures': request_data.get('temporary_measures', 'None currently in place'),
            'priority_update': request_data.get('priority_update', 'Priority remains unchanged'),
            'cost_information': request_data.get('cost_information', 'No charge for standard repairs'),
            'alternative_arrangements': request_data.get('alternative_arrangements', 'None needed at this time'),
            'additional_notes': request_data.get('additional_notes', ''),
            'next_update_date': request_data.get('next_update_date', 'When investigation is complete'),
            'contact_person': request_data.get('contact_person', 'Maintenance Office'),
            'contact_email': request_data.get('contact_email', 'maintenance@university.edu'),
            'contact_phone': request_data.get('contact_phone', '(555) 123-4567')
        }

        # Add any additional variables
        if additional_vars:
            template_vars.update(additional_vars)

        # Render template
        subject, body = render_template(template_name, template_vars)

        # Send email
        send_email(
            recipient_email=student_email,
            subject=subject,
            body=body
        )

        # Log the email activity
        log_create('maintenance_email', f"Sent {email_type} email ({template_name}) for request {request_id} to student {student_id}")

        print(f"✓ {email_type.title()} email sent to {student_name} ({student_email}) for request {request_id}")
        return True

    except Exception as e:
        print(f"✗ Failed to send {email_type} email for request {request_id}: {e}")
        import traceback
        traceback.print_exc()
        return False
