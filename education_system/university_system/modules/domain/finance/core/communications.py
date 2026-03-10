from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import ssl
import requests

from education_system.university_system.modules.domain.finance.core.finance_context import get_connection
from education_system.university_system.modules.shared.utils.i18n import get_text
from education_system.university_system.modules.domain.finance.core.security_automation import (
    send_email_notification,
    send_sms_notification,
)
from education_system.university_system.infrastructure.email.template_utils import render_template


EMAIL_CONFIG = {
    "sender_email": "finance@university.ac.uk",
    "sender_password": "",
    "sender_name": "Finance Department",
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
}

SENDGRID_CONFIG = {
    "api_key": "",
    "from_email": "finance@university.ac.uk",
    "from_name": "Finance Department",
}

AWS_SNS_CONFIG = {
    "aws_access_key_id": "",
    "aws_secret_access_key": "",
    "region_name": "us-east-1",
}

TWILIO_CONFIG = {
    "account_sid": "",
    "auth_token": "",
    "from_phone": "+447000000000",
}

def send_email_smtp(to_email, subject, body):
    """Send email using centralized SMTP system"""
    try:
        # Use centralized email system
        from education_system.university_system.infrastructure.email.smtp import send_email_via_smtp
        from datetime import datetime

        current_time = datetime.now().isoformat()
        success = send_email_via_smtp(
            recipient_email=to_email,
            subject=subject,
            body=body,
            cc=None,
            bcc=None,
            attachments=None,
            current_time=current_time
        )

        if success:
            print(get_text("finance.communications.email_sent_success", to_email=to_email))
        else:
            print(get_text("finance.communications.email_send_failed", to_email=to_email))

        return success

    except Exception as e:
        print(get_text("finance.communications.smtp_email_failed", error=e))
        return False

def send_email_sendgrid(to_email, subject, body):
    """
    Send email using SendGrid API.

    DEPRECATED: This function now uses central email infrastructure.
    Use university_system.modules.shared.utils.communication_integration.send_email_unified() directly.
    """
    print(get_text("finance.communications.deprecated_sendgrid"))

    try:
        from education_system.university_system.modules.shared.utils.communication_integration import send_email_unified

        # Use central email service instead of direct SendGrid
        success = send_email_unified(
            recipient=to_email,
            subject=subject,
            body=body,
            sender_type='system'
        )

        if success:
            print(get_text("finance.communications.email_sent_via_central", to_email=to_email))
        else:
            print(get_text("finance.communications.email_send_failed", to_email=to_email))

        return success

    except Exception as e:
        print(get_text("finance.communications.email_failed", error=e))
        return False

def send_email_aws_ses(to_email, subject, body):
    """
    Send email using AWS SES.

    DEPRECATED: This function now uses central email infrastructure.
    Use university_system.modules.shared.utils.communication_integration.send_email_unified() directly.
    """
    print(get_text("finance.communications.deprecated_aws_ses"))

    try:
        from education_system.university_system.modules.shared.utils.communication_integration import send_email_unified

        # Use central email service instead of direct AWS SES
        success = send_email_unified(
            recipient=to_email,
            subject=subject,
            body=body,
            sender_type='system'
        )

        if success:
            print(get_text("finance.communications.email_sent_via_central", to_email=to_email))
        else:
            print(get_text("finance.communications.email_send_failed", to_email=to_email))

        return success

    except Exception as e:
        print(get_text("finance.communications.email_failed", error=e))
        return False

def setup_email_config():
    """Interactive setup for email configuration"""
    print("\n" + get_text("finance.communications.email_config_setup_title"))
    print("=" * 40)

    print(get_text("finance.communications.choose_email_service"))
    print(get_text("finance.communications.option_gmail_smtp"))
    print(get_text("finance.communications.option_sendgrid"))
    print(get_text("finance.communications.option_aws_ses"))

    choice = input("Select service (1-3): ").strip()

    if choice == '1':
        EMAIL_CONFIG['sender_email'] = input("Enter sender email: ").strip()
        EMAIL_CONFIG['sender_password'] = input("Enter app password: ").strip()
        EMAIL_CONFIG['sender_name'] = input("Enter sender name: ").strip()
        EMAIL_CONFIG['smtp_server'] = input(f"SMTP server ({EMAIL_CONFIG['smtp_server']}): ").strip() or EMAIL_CONFIG['smtp_server']

    elif choice == '2':
        SENDGRID_CONFIG['api_key'] = input("Enter SendGrid API key: ").strip()
        SENDGRID_CONFIG['from_email'] = input("Enter from email: ").strip()
        SENDGRID_CONFIG['from_name'] = input("Enter from name: ").strip()

    elif choice == '3':
        AWS_SNS_CONFIG['aws_access_key_id'] = input("Enter AWS Access Key ID: ").strip()
        AWS_SNS_CONFIG['aws_secret_access_key'] = input("Enter AWS Secret Access Key: ").strip()
        AWS_SNS_CONFIG['region_name'] = input(f"Enter AWS region ({AWS_SNS_CONFIG['region_name']}): ").strip() or AWS_SNS_CONFIG['region_name']

    print(get_text("finance.communications.email_config_updated"))

def setup_sms_config():
    """Interactive setup for SMS configuration"""
    print("\n" + get_text("finance.communications.sms_config_setup_title"))
    print("=" * 40)

    print(get_text("finance.communications.choose_sms_service"))
    print(get_text("finance.communications.option_twilio"))
    print(get_text("finance.communications.option_aws_sns"))

    choice = input("Select service (1-2): ").strip()

    if choice == '1':
        TWILIO_CONFIG['account_sid'] = input("Enter Twilio Account SID: ").strip()
        TWILIO_CONFIG['auth_token'] = input("Enter Twilio Auth Token: ").strip()
        TWILIO_CONFIG['from_phone'] = input("Enter Twilio phone number: ").strip()

    elif choice == '2':
        AWS_SNS_CONFIG['aws_access_key_id'] = input("Enter AWS Access Key ID: ").strip()
        AWS_SNS_CONFIG['aws_secret_access_key'] = input("Enter AWS Secret Access Key: ").strip()
        AWS_SNS_CONFIG['region_name'] = input(f"Enter AWS region ({AWS_SNS_CONFIG['region_name']}): ").strip() or AWS_SNS_CONFIG['region_name']

    print(get_text("finance.communications.sms_config_updated"))

def send_sms_twilio(phone_number, message):
    """
    Send SMS using Twilio API.

    DEPRECATED: This function now uses central SMS infrastructure.
    Use university_system.modules.shared.utils.communication_integration.send_sms_unified() directly.
    """
    print(get_text("finance.communications.deprecated_twilio"))

    try:
        from education_system.university_system.modules.shared.utils.communication_integration import send_sms_unified

        # Use central SMS service instead of direct Twilio
        success = send_sms_unified(
            phone_number=phone_number,
            message=f"University Finance: {message}",
            related_to='finance'
        )

        if success:
            print(get_text("finance.communications.sms_sent_via_central", phone_number=phone_number))
        else:
            print(get_text("finance.communications.sms_send_failed", phone_number=phone_number))

        return success

    except Exception as e:
        print(get_text("finance.communications.sms_failed", error=e))
        return False

def send_sms_aws_sns(phone_number, message):
    """
    Send SMS using AWS SNS.

    DEPRECATED: This function now uses central SMS infrastructure.
    Use university_system.modules.shared.utils.communication_integration.send_sms_unified() directly.
    """
    print("⚠️  DEPRECATED: send_sms_aws_sns() now uses central SMS service")

    try:
        from education_system.university_system.modules.shared.utils.communication_integration import send_sms_unified

        # Use central SMS service instead of direct AWS SNS
        success = send_sms_unified(
            phone_number=phone_number,
            message=f"University Finance: {message}",
            related_to='finance'
        )

        if success:
            print(f"✅ SMS sent successfully to {phone_number} (via central service)")
        else:
            print(f"⚠️ SMS sending failed for {phone_number}")

        return success

    except Exception as e:
        print(f"❌ SMS failed: {e}")
        return False

def test_email_service():
    """Test email service functionality"""
    print("\n📧 Testing Email Service...")

    try:
        test_email = input("Enter test email address: ").strip()
        if not test_email:
            test_email = "test@example.com"

        # Use email template
        from education_system.university_system.infrastructure.email.template_utils import render_template

        subject, body = render_template('finance_system_test', {})

        if not subject or not body:
            print("Failed to load email template.")
            return

        print(f"Sending test email to {test_email}...")

        # Note: This will fail without proper SMTP configuration
        # but shows the email would be sent
        success = send_email_notification(test_email, subject, body)

        if success:
            print("✅ Email test successful!")
        else:
            print("❌ Email test failed - check SMTP configuration")
            print("💡 Configure EMAIL_CONFIG variables for actual email sending")

    except Exception as e:
        print(f"❌ Email test error: {e}")

def test_sms_service():
    """Test SMS service functionality"""
    print("\n📱 Testing SMS Service...")

    try:
        student_id = input("Enter student ID for SMS test: ").strip()
        if not student_id:
            student_id = "STU001"

        message = "This is a test SMS from the Finance Management System."

        print(f"Sending test SMS to student {student_id}...")

        # Note: This will fail without proper SMS configuration
        # but shows the SMS would be sent
        success = send_sms_notification(student_id, message)

        if success:
            print("✅ SMS test successful!")
        else:
            print("❌ SMS test failed - check SMS configuration")
            print("💡 Configure TWILIO_CONFIG or AWS_SNS_CONFIG for actual SMS sending")

    except Exception as e:
        print(f"❌ SMS test error: {e}")

def send_arrangement_confirmation(student_id, case_id, schedule_info):
    """Send payment arrangement confirmation to student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student details
        cursor.execute('''
        SELECT first_name, last_name, email_address
        FROM students
        WHERE student_id = ?
        ''', (student_id,))

        student = cursor.fetchone()

        if student:
            first_name, last_name, email = student
            student_name = f"{first_name} {last_name}"

            template_vars = {
                'name': student_name,
                'case_id': case_id,
                'schedule_info': schedule_info
            }
            subject, body = render_template('payment_arrangement_confirmation', template_vars)

            if send_email_notification(email, subject, body):
                print(f"Payment arrangement confirmation sent to {email}")
            else:
                print("Failed to send arrangement confirmation")

        conn.close()

    except Exception as e:
        print(f"Error sending arrangement confirmation: {e}")
