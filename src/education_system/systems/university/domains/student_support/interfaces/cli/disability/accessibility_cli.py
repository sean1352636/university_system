"""
Accessibility Services Portal - CLI Interface

This module provides a command-line interface for students to interact with
accessibility services, submit accommodation requests, and manage their accommodations.

Moved from operations/campus/accessibility on 2026-10-19 as the CLI of the
Disability & Accessibility portal. Students keep their menu (on their own
student number, never the account id); staff get the request queue and
renewals (:meth:`run_staff`). Everything goes through domain/disability/portal.
"""

import os
from datetime import datetime
from typing import Optional

from education_system.systems.university.domains.student_support.domain.disability import access, portal
from education_system.systems.university.infrastructure.shared_context import get_auth


def _days_left(date_text):
    try:
        return (datetime.strptime(str(date_text)[:10], '%Y-%m-%d') - datetime.now()).days
    except (TypeError, ValueError):
        return None


class AccessibilityCLI:
    """CLI interface for accessibility services."""

    def __init__(self, auth=None):
        """Initialize the accessibility CLI."""
        self.service = portal.service()
        self.auth = auth or get_auth()

    def run(self):
        """Run the main accessibility services CLI menu."""
        if not (self.auth and self.auth.current_user):
            print("\nYou must be logged in to access accessibility services.")
            return
        try:
            student_id = portal.my_student_id(self.auth)
        except PermissionError as exc:
            print(f"\n{exc}")
            return

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
        for idx, acc_type in enumerate(portal.ACCOMMODATION_TYPES, 1):
            print(f"{idx}. {acc_type}")

        type_choice = input(f"\nSelect accommodation type (1-{len(portal.ACCOMMODATION_TYPES)}): ").strip()

        try:
            type_idx = int(type_choice) - 1
            if type_idx < 0 or type_idx >= len(portal.ACCOMMODATION_TYPES):
                print("\nInvalid choice.")
                return

            accommodation_type = portal.ACCOMMODATION_TYPES[type_idx]
        except ValueError:
            print("\nInvalid input.")
            return

        # Contact details default to the student's record
        name, email = portal.my_contact(self.auth)
        student_name = input(f"Your full name [{name}]: ").strip() or name
        student_email = input(f"Your email [{email}]: ").strip() or email

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
            request_id = portal.submit_request(
                self.auth, accommodation_type, description,
                contact_name=student_name, contact_email=student_email,
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
        requests = portal.my_requests(self.auth)

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

            doc_id = portal.upload_document(self.auth, request_id, filename, file_content,
                                            doc_type)

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

        requests = portal.my_requests(self.auth)

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

            # Show messages (staff replies are marked read by the portal)
            messages = portal.messages(self.auth, req['request_id'])
            if messages:
                print(f"\nMessages ({len(messages)}):")
                for msg in messages:
                    sender_label = "You" if msg['sender_type'] == 'student' else "Staff"
                    print(f"\n  [{msg['sent_date']}] {sender_label}:")
                    print(f"  {msg['message']}")

    def _message_disability_services(self, student_id: str):
        """Send a message to disability services staff."""
        print("\n" + "-" * 60)
        print("MESSAGE DISABILITY SERVICES")
        print("-" * 60)

        # Get student's requests
        requests = portal.my_requests(self.auth)

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
            message_id = portal.send_message(self.auth, request_id, message)

            print(f"\nMessage sent successfully! (ID: {message_id})")
            print("Replies arrive in your Notifications Hub inbox.")

        except Exception as e:
            print(f"\nError sending message: {e}")

    def _view_active_accommodations(self, student_id: str):
        """View all approved and active accommodations."""
        print("\n" + "-" * 60)
        print("MY ACTIVE ACCOMMODATIONS")
        print("-" * 60)

        accommodations = portal.my_accommodations(self.auth)

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
            days_until_exp = _days_left(acc['expiration_date'])

            if days_until_exp is not None and days_until_exp <= 30:
                print(f"\nWARNING: This accommodation expires in {days_until_exp} days!")
                print("Please submit a renewal request.")

    def _request_renewal(self, student_id: str):
        """Request renewal of an existing accommodation."""
        print("\n" + "-" * 60)
        print("REQUEST ACCOMMODATION RENEWAL")
        print("-" * 60)

        # Get active accommodations
        accommodations = portal.my_accommodations(self.auth)

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
            renewal_id = portal.request_renewal(self.auth, accommodation_id, notes or None)

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

        notifications = portal.my_faculty_notifications(self.auth)

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

        expiring = portal.my_expiring(self.auth, 30)

        if not expiring:
            print("\nNo accommodations expiring in the next 30 days.")
            return

        print(f"\nWARNING: {len(expiring)} accommodation(s) expiring soon!")

        for acc in expiring:
            print("\n" + "=" * 60)
            print(f"Accommodation ID: {acc['accommodation_id']}")
            print(f"Type: {acc['accommodation_type']}")
            print(f"Expiration Date: {acc['expiration_date']}")

            print(f"Days Until Expiration: {_days_left(acc['expiration_date'])}")
            print("\nACTION REQUIRED: Please submit a renewal request to continue your accommodations.")

    # ------------------------------------------------------------------ staff

    def run_staff(self):
        """Disability services' menu: the request queue and renewals."""
        try:
            access.require_staff(self.auth)
        except PermissionError as exc:
            print(f"\n{exc}")
            return
        while True:
            try:
                stats = portal.statistics(self.auth)
                print("\n" + "=" * 60)
                print("DISABILITY SERVICES — REQUESTS")
                print("=" * 60)
                print(f"Waiting: {stats['pending_requests']}   Active: "
                      f"{stats['active_accommodations']}   Ending within 30 days: "
                      f"{stats['expiring_soon']}")
                print("1. Request queue")
                print("2. Open a request (description and documents)")
                print("3. Mark a request under review")
                print("4. Approve a request")
                print("5. Deny a request")
                print("6. Messages on a request (read / reply)")
                print("7. Renewals waiting")
                print("8. Approve or deny a renewal")
                print("9. All requests, including decided ones")
                print("0. Back")
                choice = input("\nEnter your choice: ").strip()
                if choice == '0':
                    return
                action = {
                    '1': lambda: self._staff_queue(False), '2': self._staff_open,
                    '3': self._staff_review, '4': self._staff_approve,
                    '5': self._staff_deny, '6': self._staff_messages,
                    '7': self._staff_renewals, '8': self._staff_decide_renewal,
                    '9': lambda: self._staff_queue(True),
                }.get(choice)
                if action is None:
                    print("\nInvalid choice. Please try again.")
                else:
                    action()
            except (PermissionError, ValueError) as exc:
                print(f"\n{exc}")

    @staticmethod
    def _ask_id(prompt):
        raw = input(prompt).strip().lstrip('#')
        if not raw.isdigit():
            raise ValueError("Enter a number.")
        return int(raw)

    @staticmethod
    def _ask_text(prompt):
        print(prompt + " (Press Enter twice when finished)")
        lines = []
        while True:
            line = input()
            if line == '' and lines and lines[-1] == '':
                break
            lines.append(line)
        return '\n'.join(lines).strip()

    def _staff_queue(self, include_closed):
        rows = portal.queue(self.auth, include_closed=include_closed)
        if not rows:
            print("\nNo requests waiting.")
            return
        print(f"\n{'#':>5}  {'Student':<10} {'Name':<24} {'Type':<20} {'Status':<13} "
              f"{'Submitted':<11} Docs Unread")
        for r in rows:
            print(f"{r['request_id']:>5}  {str(r['student_id']):<10} "
                  f"{(r.get('student_name') or '')[:24]:<24} {r['accommodation_type'][:20]:<20} "
                  f"{r['status']:<13} {str(r.get('submitted_date') or '')[:10]:<11} "
                  f"{r.get('documents') or 0:>4} {r.get('unread') or 0:>6}")

    def _staff_open(self):
        req = portal.request_detail(self.auth, self._ask_id("Request #: "))
        print("\n" + "=" * 60)
        print(f"Request #{req['request_id']} — {req['accommodation_type']} — {req['status']}")
        print(f"Student {req['student_id']}  {req.get('student_name') or ''}  "
              f"{req.get('student_email') or ''}")
        print(f"Submitted {req.get('submitted_date') or req.get('requested_date') or ''}")
        print(f"\n{req.get('description') or ''}")
        notes = req.get('reviewer_notes') or req.get('review_notes')
        if notes:
            print(f"\nReviewer notes: {notes}")
        docs = req.get('documents') or []
        print(f"\nDocuments ({len(docs)}):")
        for d in docs:
            print(f"  - {d['filename']} ({d.get('document_type') or ''}) {d['file_path']}")

    def _staff_review(self):
        portal.mark_under_review(self.auth, self._ask_id("Request #: "))
        print("\nMarked under review; the student has been told.")

    def _staff_approve(self):
        rid = self._ask_id("Request #: ")
        start = input("Starts (YYYY-MM-DD, Enter for today): ").strip() or None
        months = input("Lasts how many months [12]: ").strip() or "12"
        if not months.isdigit():
            raise ValueError("Enter the number of months.")
        note = input("Note to the student (optional): ").strip() or None
        acc_id = portal.approve(self.auth, rid, start_date=start, months=int(months), notes=note)
        print(f"\nApproved. Accommodation #{acc_id} is active and has been passed to exams "
              "and assessments.")

    def _staff_deny(self):
        rid = self._ask_id("Request #: ")
        portal.deny(self.auth, rid, self._ask_text("Reason (sent to the student):"))
        print("\nDenied; the student has been told why.")

    def _staff_messages(self):
        rid = self._ask_id("Request #: ")
        rows = portal.messages(self.auth, rid)
        if not rows:
            print("\nNo messages yet.")
        for m in rows:
            who = "Student" if m['sender_type'] == 'student' else f"Staff ({m['sender_id']})"
            print(f"\n[{m['sent_date']}] {who}:\n  {m['message']}")
        if input("\nReply? (y/n): ").strip().lower() == 'y':
            text = self._ask_text("Your reply:")
            portal.send_message(self.auth, rid, text)
            print("\nSent; it is in the student's inbox.")

    def _staff_renewals(self):
        rows = portal.pending_renewals(self.auth)
        if not rows:
            print("\nNo renewals waiting.")
            return
        for r in rows:
            print(f"#{r['renewal_id']}  student {r['student_id']}  {r['accommodation_type']}  "
                  f"ends {r.get('expiration_date') or 'no end date'}  asked "
                  f"{str(r.get('renewal_request_date') or '')[:10]}  {r.get('notes') or ''}")

    def _staff_decide_renewal(self):
        rid = self._ask_id("Renewal #: ")
        answer = input("Approve (a) or deny (d)? ").strip().lower()
        if answer not in ('a', 'd'):
            raise ValueError("Enter a or d.")
        if answer == 'a':
            months = input("Extend by how many months [12]: ").strip() or "12"
            if not months.isdigit():
                raise ValueError("Enter the number of months.")
            portal.decide_renewal(self.auth, rid, True, None, months=int(months))
            print("\nRenewed; the student has been told.")
        else:
            portal.decide_renewal(self.auth, rid, False,
                                  input("Reason (sent to the student): ").strip())
            print("\nDenied; the student has been told why.")


def main():
    """Main entry point for the accessibility CLI."""
    cli = AccessibilityCLI()
    cli.run()


if __name__ == '__main__':
    main()
