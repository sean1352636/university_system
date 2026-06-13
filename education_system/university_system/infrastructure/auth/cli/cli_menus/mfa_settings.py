"""Split from cli_menus.py — assembled in package __init__.py."""
from __future__ import annotations

import sys
import json
import logging
import random
import secrets
import string
from pathlib import Path
from datetime import datetime

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.core.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    DatabaseError,
)

logger = logging.getLogger("education_system.university_system.infrastructure.auth.cli.cli_menus")

from .account_linking import _display_account_linking_menu
from .webauthn import _display_webauthn_menu
from .biometric import _display_biometric_menu
from .delegated_access import _display_delegated_access_menu

def display_mfa_settings_menu(auth, user):
    """Display MFA settings menu (Email Verification) - syncs with GUI"""
    try:
        from education_system.university_system.infrastructure.auth.mfa_service import MFAService
        mfa_service = MFAService()
    except ImportError as e:
        print(f"\n❌ MFA module not available: {e}")
        return

    user_id = user.get('id')
    username = user.get('username')

    if not user_id:
        print("\n❌ Unable to get user information")
        return

    while True:
        print("\n" + "=" * 50)
        print("MFA Settings (Email Verification)")
        print("=" * 50)

        # Get current MFA status
        try:
            is_verification_disabled = mfa_service.is_verification_disabled(user_id)
            methods_result = mfa_service.get_user_mfa_methods(user_id)
            saved_methods_result = mfa_service.get_saved_mfa_methods(user_id)

            active_methods = []
            if methods_result and methods_result.get('success'):
                active_methods = methods_result.get('methods', [])

            saved_methods = []
            if saved_methods_result and saved_methods_result.get('success'):
                saved_methods = saved_methods_result.get('methods', [])

            has_saved_disabled = any(
                not m.get('is_enabled', True)
                for m in saved_methods
                if m and isinstance(m, dict)
            ) if saved_methods else False

        except Exception as e:
            print(f"\n❌ Error getting MFA status: {e}")
            return

        # Display current status
        if is_verification_disabled:
            print(f"\nStatus: ❌ DISABLED (Password only login)")
        elif active_methods:
            print(f"\nStatus: ✅ ENABLED")
        else:
            print(f"\nStatus: ⚠️  NOT CONFIGURED")

        # Show configured methods
        if active_methods:
            print("\nActive Methods:")
            for method in active_methods:
                if method and isinstance(method, dict):
                    method_type = str(method.get('type', 'Unknown')).upper()
                    identifier = method.get('identifier', '')
                    # Mask identifier
                    if identifier and '@' in str(identifier):
                        parts = str(identifier).split('@')
                        masked = parts[0][:2] + '***@' + parts[1]
                    elif identifier:
                        masked = str(identifier)[:3] + '****'
                    else:
                        masked = 'Configured'
                    print(f"  • {method_type}: {masked}")
        elif has_saved_disabled:
            print("\nSaved Methods (Disabled):")
            for method in saved_methods:
                if method and isinstance(method, dict) and not method.get('is_enabled'):
                    method_type = str(method.get('type', 'Unknown')).upper()
                    identifier = method.get('identifier', '')
                    if identifier and '@' in str(identifier):
                        parts = str(identifier).split('@')
                        masked = parts[0][:2] + '***@' + parts[1]
                    elif identifier:
                        masked = str(identifier)[:3] + '****'
                    else:
                        masked = 'Configured'
                    print(f"  • {method_type}: {masked}")

        print("\n" + "-" * 50)

        # Show appropriate options based on status
        if active_methods or not is_verification_disabled:
            # MFA is enabled
            print("1. Change Email Address")
            print("2. Disable MFA")
            print("3. Back")
            max_choice = 3
        elif has_saved_disabled:
            # MFA disabled but has saved settings
            print("1. Re-enable MFA (use saved settings)")
            print("2. Setup New MFA")
            print("3. Back")
            max_choice = 3
        else:
            # No MFA configured
            print("1. Setup MFA")
            print("2. Back")
            max_choice = 2

        choice = input(f"\nEnter your choice (1-{max_choice}): ").strip()

        if active_methods or not is_verification_disabled:
            # MFA is enabled
            if choice == '1':
                # Change email
                _cli_setup_mfa_email(mfa_service, user_id, username)
            elif choice == '2':
                # Disable MFA
                _cli_disable_mfa(mfa_service, user_id)
            elif choice == '3':
                return
            else:
                print("Invalid choice.")

        elif has_saved_disabled:
            # MFA disabled with saved settings
            if choice == '1':
                # Re-enable with saved settings
                _cli_reenable_mfa(mfa_service, user_id, username, saved_methods)
            elif choice == '2':
                # Setup new
                _cli_setup_mfa_email(mfa_service, user_id, username)
            elif choice == '3':
                return
            else:
                print("Invalid choice.")

        else:
            # No MFA configured
            if choice == '1':
                # Setup MFA
                _cli_setup_mfa_email(mfa_service, user_id, username)
            elif choice == '2':
                return
            else:
                print("Invalid choice.")

# ============================================================================
# MFA Helper Functions
# ============================================================================

def _cli_setup_mfa_email(mfa_service, user_id, username):
    """Setup or update email MFA via CLI"""
    print("\n" + "=" * 50)
    print("Setup Email MFA")
    print("=" * 50)

    email = input("\nEnter your email address: ").strip()

    if not email or '@' not in email:
        print("\n❌ Invalid email address")
        return

    # Confirm
    confirm = input(f"\nSetup MFA with email: {email}? (y/n): ").lower().strip()
    if confirm != 'y':
        print("Cancelled.")
        return

    try:
        # Send verification OTP
        print(f"\n📧 Sending verification code to {email}...")
        otp_result = mfa_service.generate_email_otp(user_id, email)

        if not otp_result.get('success'):
            print(f"\n❌ Failed to send verification code: {otp_result.get('error')}")
            return

        if otp_result.get('email_failed'):
            # Show code on screen as fallback
            code = otp_result.get('code', '')
            print(f"\n⚠️  Email delivery failed. Your verification code is: {code}")
        else:
            print(f"\n✅ Verification code sent to {email}")

        # Verify the code
        max_attempts = 3
        for attempt in range(max_attempts):
            code_input = input("\nEnter 6-digit verification code: ").strip()

            verify_result = mfa_service.verify_email_otp(user_id, code_input)
            if verify_result.get('success'):
                # Update/save the MFA method
                update_result = mfa_service.update_mfa_method(user_id, 'email', email)
                if update_result.get('success'):
                    print("\n✅ MFA has been successfully configured!")
                    print(f"   Email: {email}")
                    print("\n   You will receive verification codes at this email when logging in.")
                else:
                    print(f"\n❌ Failed to save MFA settings: {update_result.get('error')}")
                return
            else:
                remaining = max_attempts - attempt - 1
                if remaining > 0:
                    print(f"❌ Invalid code. {remaining} attempt(s) remaining.")
                else:
                    print("❌ Too many failed attempts. Setup cancelled.")

    except Exception as e:
        print(f"\n❌ Error setting up MFA: {e}")

def _cli_disable_mfa(mfa_service, user_id):
    """Disable MFA via CLI"""
    print("\n" + "=" * 50)
    print("Disable MFA")
    print("=" * 50)
    print("\n⚠️  Warning: Disabling MFA makes your account less secure.")
    print("   Your settings will be saved and can be restored later.")

    confirm = input("\nAre you sure you want to disable MFA? (y/n): ").lower().strip()
    if confirm != 'y':
        print("Cancelled.")
        return

    try:
        result = mfa_service.disable_mfa(user_id)
        if result.get('success'):
            print("\n✅ MFA has been disabled.")
            print("   Your settings have been saved for 90 days.")
            print("   You can re-enable MFA from CLI or GUI at any time.")
        else:
            print(f"\n❌ Failed to disable MFA: {result.get('error')}")
    except Exception as e:
        print(f"\n❌ Error disabling MFA: {e}")

def _cli_reenable_mfa(mfa_service, user_id, username, saved_methods):
    """Re-enable MFA with saved settings via CLI"""
    print("\n" + "=" * 50)
    print("Re-enable MFA")
    print("=" * 50)

    print("\nYour previously saved MFA settings will be restored.")

    confirm = input("\nRe-enable MFA with saved settings? (y/n): ").lower().strip()
    if confirm != 'y':
        print("Cancelled.")
        return

    try:
        result = mfa_service.reenable_mfa(user_id)
        if result.get('success'):
            print("\n✅ MFA has been re-enabled!")
            print(f"   {result.get('methods_count', 1)} method(s) restored.")

            # Try to send confirmation email
            email_to_notify = None
            if saved_methods:
                for method in saved_methods:
                    if method and method.get('type') == 'email' and method.get('identifier'):
                        email_to_notify = method.get('identifier')
                        break

            if email_to_notify:
                try:
                    from education_system.university_system.infrastructure.auth.email_otp_service import SMTPEmailProvider
                    from education_system.university_system.infrastructure.email.template_utils import render_template
                    import smtplib
                    from email.mime.text import MIMEText
                    from email.mime.multipart import MIMEMultipart

                    smtp_provider = SMTPEmailProvider()

                    # Load template from file (same as GUI)
                    template_vars = {
                        'username': username,
                        'email': email_to_notify,
                        'methods_count': str(result.get('methods_count', 1))
                    }
                    subject, body = render_template('authentication/mfa_reenabled', template_vars)

                    # Fallback if template fails
                    if not subject or not body:
                        subject = "MFA Re-enabled for Your Account"
                        body = f"Hello {username},\n\nMFA has been re-enabled for your account.\n\nUniversity System Security Team"

                    msg = MIMEMultipart()
                    msg['Subject'] = subject
                    msg['From'] = f"{smtp_provider.from_name} <{smtp_provider.from_email}>"
                    msg['To'] = email_to_notify
                    msg.attach(MIMEText(body, 'plain'))

                    with smtplib.SMTP(smtp_provider.smtp_server, smtp_provider.smtp_port) as server:
                        server.starttls()
                        server.login(smtp_provider.username, smtp_provider.password)
                        server.send_message(msg)

                    print(f"\n   Confirmation email sent to: {email_to_notify}")
                except Exception as email_error:
                    print(f"\n   (Confirmation email could not be sent)")

        else:
            print(f"\n❌ Failed to re-enable MFA: {result.get('error')}")
    except Exception as e:
        print(f"\n❌ Error re-enabling MFA: {e}")

# ============================================================================
# Account Linking Menu
# ============================================================================

