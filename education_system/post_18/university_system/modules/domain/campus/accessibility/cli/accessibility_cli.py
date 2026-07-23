"""
Accessibility Services Portal - CLI Interface

This module provides a command-line interface for students to interact with
accessibility services, submit accommodation requests, and manage their accommodations.
"""

import os
from datetime import datetime
from typing import Optional

from education_system.post_18.university_system.modules.domain.campus.accessibility.services.accessibility_service import AccessibilityService
from education_system.post_18.university_system.infrastructure.shared_context import get_auth


class AccessibilityCLI:
    """CLI interface for accessibility services."""

    def __init__(self):
        """Initialize the accessibility CLI."""
        self.service = AccessibilityService()
        self.auth = get_auth()

    def run(self):
        """Run the main accessibility services CLI menu."""
        if not self.auth.is_logged_in():
            print("\nYou must be logged in to access accessibility services.")
            return

        current_user = self.auth.get_current_user()
        student_id = current_user.get('user_id') or current_user.get('username')

        while True:
            self._display_main_menu()
            choice = input("\nEnter your choice: ").strip()

            if choice == '1':
                self._submit_accommodation_request(student_id)
            elif choice == '2':
                self._upload_documentation(student_id)
            elif choice == '3':
                self._view_my_requests(student_id)
            elif choice == '4':
                self._message_disability_services(student_id)
            elif choice == '5':
                self._view_active_accommodations(student_id)
            elif choice == '6':
                self._request_renewal(student_id)
            elif choice == '7':
                self._view_faculty_notifications(student_id)
            elif choice == '8':
                self._view_expiring_accommodations(student_id)
            elif choice == '9':
                print("\nReturning to main menu...")
                break
            else:
                print("\nInvalid choice. Please try again.")

    def _display_main_menu(self):
        """Display the main accessibility services menu."""
        print("\n" + "=" * 60)
        print("ACCESSIBILITY SERVICES PORTAL")
        print("=" * 60)
        print("1. Submit Accommodation Request")
        print("2. Upload Documentation")
        print("3. View My Requests and Status")
        print("4. Message Disability Services")
        print("5. View Approved Accommodations")
        print("6. Request Renewal")
        print("7. View Faculty Notifications Sent")
        print("8. View Expiring Accommodations")
        print("9. Return to Main Menu")
        print("=" * 60)

    def _submit_accommodation_request(self, student_id: str):
        """Submit a new accommodation request."""
        print("\n" + "-" * 60)
        print("SUBMIT ACCOMMODATION REQUEST")
        print("-" * 60)

        # Display accommodation types
        print("\nAccommodation Types:")
        for idx, acc_type in enumerate(self.service.ACCOMMODATION_TYPES, 1):
            print(f"{idx}. {acc_type}")

        type_choice = input("\nSelect accommodation type (1-6): ").strip()

        try:
            type_idx = int(type_choice) - 1
            if type_idx < 0 or type_idx >= len(self.service.ACCOMMODATION_TYPES):
                print("\nInvalid choice.")
                return

            accommodation_type = self.service.ACCOMMODATION_TYPES[type_idx]
        except ValueError:
            print("\nInvalid input.")
            return

        # Get student information
        student_name = input("Enter your full name: ").strip()
        student_email = input("Enter your email: ").strip()

        print("\nDescribe your accommodation needs in detail:")
        print("(Press Enter twice when finished)")
        description_lines = []
        while True:
            line = input()
            if line == '':
                if description_lines and description_lines[-1] == '':
                    break
            description_lines.append(line)

        description = '\n'.join(description_lines).strip()

        if not description:
            print("\nDescription cannot be empty.")
            return

        # Submit request
        try:
            request_id = self.service.submit_accommodation_request(
                student_id=student_id,
                student_name=student_name,
                student_email=student_email,
                accommodation_type=accommodation_type,
                description=description
            )

            print("\nAccommodation request submitted successfully!")
            print(f"Request ID: {request_id}")
            print(f"Type: {accommodation_type}")
            print("Status: Submitted")
            print("\nYou will receive updates via email. Please upload supporting documentation.")

        except Exception as e:
            print(f"\nError submitting request: {e}")

    def _upload_documentation(self, student_id: str):
        """Upload supporting documentation for a request."""
        print("\n" + "-" * 60)
        print("UPLOAD DOCUMENTATION")
        print("-" * 60)

        # Get student's requests
        requests = self.service.get_student_requests(student_id)

        if not requests:
            print("\nYou have no accommodation requests.")
            return

        print("\nYour Requests:")
        for req in requests:
            print(f"\nRequest ID: {req['request_id']}")
            print(f"Type: {req['accommodation_type']}")
            print(f"Status: {req['status']}")
            print(f"Submitted: {req['submitted_date']}")

        request_id = input("\nEnter Request ID to upload documentation for: ").strip()

        try:
            request_id = int(request_id)
        except ValueError:
            print("\nInvalid Request ID.")
            return

        # Verify request belongs to student
        request = next((r for r in requests if r['request_id'] == request_id), None)
        if not request:
            print("\nRequest not found or does not belong to you.")
            return

        # Get file path
        file_path = input("Enter full path to documentation file: ").strip()

        if not os.path.exists(file_path):
            print(f"\nFile not found: {file_path}")
            return

        filename = os.path.basename(file_path)
        doc_type = input("Document type (default: Medical Documentation): ").strip() or "Medical Documentation"

        # Read file content
        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()

            doc_id = self.service.upload_documentation(
                request_id=request_id,
                student_id=student_id,
                filename=filename,
                file_content=file_content,
                document_type=doc_type
            )

            print("\nDocumentation uploaded successfully!")
            print(f"Document ID: {doc_id}")
            print(f"Filename: {filename}")
            print(f"Type: {doc_type}")

        except Exception as e:
            print(f"\nError uploading documentation: {e}")

    def _view_my_requests(self, student_id: str):
        """View all accommodation requests and their status."""
        print("\n" + "-" * 60)
        print("MY ACCOMMODATION REQUESTS")
        print("-" * 60)

        requests = self.service.get_student_requests(student_id)

        if not requests:
            print("\nYou have no accommodation requests.")
            return

        for req in requests:
            print("\n" + "=" * 60)
            print(f"Request ID: {req['request_id']}")
            print(f"Type: {req['accommodation_type']}")
            print(f"Status: {req['status']}")
            print(f"Submitted: {req['submitted_date']}")

            if req['reviewed_date']:
                print(f"Reviewed: {req['reviewed_date']}")

            if req['reviewer_notes']:
                print("\nReviewer Notes:")
                print(req['reviewer_notes'])

            print("\nDescription:")
            print(req['description'])

            # Show documentation
            docs = self.service.get_documentation(req['request_id'])
            if docs:
                print(f"\nDocumentation ({len(docs)} files):")
                for doc in docs:
                    print(f"  - {doc['filename']} ({doc['document_type']}) - {doc['upload_date']}")

            # Show messages
            messages = self.service.get_messages(req['request_id'])
            if messages:
                print(f"\nMessages ({len(messages)}):")
                for msg in messages:
                    sender_label = "You" if msg['sender_type'] == 'student' else "Staff"
                    print(f"\n  [{msg['sent_date']}] {sender_label}:")
                    print(f"  {msg['message']}")
                    # Mark as read
                    if msg['sender_type'] == 'staff' and not msg['is_read']:
                        self.service.mark_message_as_read(msg['message_id'])

    def _message_disability_services(self, student_id: str):
        """Send a message to disability services staff."""
        print("\n" + "-" * 60)
        print("MESSAGE DISABILITY SERVICES")
        print("-" * 60)

        # Get student's requests
        requests = self.service.get_student_requests(student_id)

        if not requests:
            print("\nYou have no accommodation requests to message about.")
            return

        print("\nYour Requests:")
        for req in requests:
            print(f"\nRequest ID: {req['request_id']}")
            print(f"Type: {req['accommodation_type']}")
            print(f"Status: {req['status']}")

        request_id = input("\nEnter Request ID to message about: ").strip()

        try:
            request_id = int(request_id)
        except ValueError:
            print("\nInvalid Request ID.")
            return

        # Verify request belongs to student
        request = next((r for r in requests if r['request_id'] == request_id), None)
        if not request:
            print("\nRequest not found or does not belong to you.")
            return

        print("\nEnter your message:")
        print("(Press Enter twice when finished)")
        message_lines = []
        while True:
            line = input()
            if line == '':
                if message_lines and message_lines[-1] == '':
                    break
            message_lines.append(line)

        message = '\n'.join(message_lines).strip()

        if not message:
            print("\nMessage cannot be empty.")
            return

        try:
            message_id = self.service.send_message(
                request_id=request_id,
                sender_id=student_id,
                sender_type='student',
                message=message
            )

            print(f"\nMessage sent successfully! (ID: {message_id})")
            print("You will receive a response via email.")

        except Exception as e:
            print(f"\nError sending message: {e}")

    def _view_active_accommodations(self, student_id: str):
        """View all approved and active accommodations."""
        print("\n" + "-" * 60)
        print("MY ACTIVE ACCOMMODATIONS")
        print("-" * 60)

        accommodations = self.service.get_active_accommodations(student_id)

        if not accommodations:
            print("\nYou have no active accommodations.")
            return

        for acc in accommodations:
            print("\n" + "=" * 60)
            print(f"Accommodation ID: {acc['accommodation_id']}")
            print(f"Type: {acc['accommodation_type']}")
            print(f"Description: {acc['description']}")
            print(f"Start Date: {acc['start_date']}")
            print(f"Expiration Date: {acc['expiration_date']}")
            print(f"Approved By: {acc['approved_by']}")

            # Check if expiring soon
            exp_date = datetime.strptime(acc['expiration_date'], '%Y-%m-%d')
            days_until_exp = (exp_date - datetime.now()).days

            if days_until_exp <= 30:
                print(f"\nWARNING: This accommodation expires in {days_until_exp} days!")
                print("Please submit a renewal request.")

    def _request_renewal(self, student_id: str):
        """Request renewal of an existing accommodation."""
        print("\n" + "-" * 60)
        print("REQUEST ACCOMMODATION RENEWAL")
        print("-" * 60)

        # Get active accommodations
        accommodations = self.service.get_active_accommodations(student_id)

        if not accommodations:
            print("\nYou have no active accommodations to renew.")
            return

        print("\nYour Active Accommodations:")
        for acc in accommodations:
            print(f"\nAccommodation ID: {acc['accommodation_id']}")
            print(f"Type: {acc['accommodation_type']}")
            print(f"Expiration Date: {acc['expiration_date']}")

        accommodation_id = input("\nEnter Accommodation ID to renew: ").strip()

        try:
            accommodation_id = int(accommodation_id)
        except ValueError:
            print("\nInvalid Accommodation ID.")
            return

        # Verify accommodation belongs to student
        accommodation = next((a for a in accommodations if a['accommodation_id'] == accommodation_id), None)
        if not accommodation:
            print("\nAccommodation not found or does not belong to you.")
            return

        notes = input("\nAny notes for the renewal request (optional): ").strip()

        try:
            renewal_id = self.service.request_renewal(
                accommodation_id=accommodation_id,
                student_id=student_id,
                notes=notes if notes else None
            )

            print("\nRenewal request submitted successfully!")
            print(f"Renewal ID: {renewal_id}")
            print("Status: Pending")
            print("\nYou will be notified when your renewal is processed.")

        except Exception as e:
            print(f"\nError submitting renewal request: {e}")

    def _view_faculty_notifications(self, student_id: str):
        """View all faculty notifications sent for the student's accommodations."""
        print("\n" + "-" * 60)
        print("FACULTY NOTIFICATIONS")
        print("-" * 60)

        notifications = self.service.get_faculty_notifications(student_id)

        if not notifications:
            print("\nNo faculty notifications have been sent.")
            return

        print(f"\nTotal Notifications Sent: {len(notifications)}")

        for notif in notifications:
            print("\n" + "=" * 60)
            print(f"Notification ID: {notif['notification_id']}")
            print(f"Faculty ID: {notif['faculty_id']}")
            print(f"Course ID: {notif['course_id']}")
            print(f"Sent Date: {notif['sent_date']}")
            print(f"Acknowledged: {'Yes' if notif['acknowledged'] else 'No'}")
            print("\nAccommodation Summary:")
            print(notif['accommodation_summary'])

    def _view_expiring_accommodations(self, student_id: str):
        """View accommodations expiring within 30 days."""
        print("\n" + "-" * 60)
        print("EXPIRING ACCOMMODATIONS (Next 30 Days)")
        print("-" * 60)

        expiring = self.service.get_expiring_accommodations(student_id, days_threshold=30)

        if not expiring:
            print("\nNo accommodations expiring in the next 30 days.")
            return

        print(f"\nWARNING: {len(expiring)} accommodation(s) expiring soon!")

        for acc in expiring:
            print("\n" + "=" * 60)
            print(f"Accommodation ID: {acc['accommodation_id']}")
            print(f"Type: {acc['accommodation_type']}")
            print(f"Expiration Date: {acc['expiration_date']}")

            exp_date = datetime.strptime(acc['expiration_date'], '%Y-%m-%d')
            days_until_exp = (exp_date - datetime.now()).days

            print(f"Days Until Expiration: {days_until_exp}")
            print("\nACTION REQUIRED: Please submit a renewal request to continue your accommodations.")


def main():
    """Main entry point for the accessibility CLI."""
    cli = AccessibilityCLI()
    cli.run()


if __name__ == '__main__':
    main()
