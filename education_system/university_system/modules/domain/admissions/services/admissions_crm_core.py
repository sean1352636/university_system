"""
Admissions & Recruitment CRM Core Service

Prospect management, application processing, review workflows,
communication campaigns, campus tours, and yield predictions.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from education_system.university_system.infrastructure.database.db import get_connection, transaction

logger = logging.getLogger("admissions.emails")


def _send_applicant_email(template_name: str, application_id: int,
                          extra_vars: Optional[Dict[str, Any]] = None) -> bool:
    """Render ``admissions/<template_name>`` for the applicant on
    *application_id* and dispatch it via the shared email infrastructure.

    Best-effort: returns False (and logs) on missing applicant, missing email,
    template render failure, or send failure — never raises into the caller."""
    try:
        from education_system.university_system.infrastructure.email.template_utils import (
            render_template,
        )
        from education_system.university_system.infrastructure.email.email_service import (
            send_email,
        )
    except Exception:
        logger.exception("email infrastructure unavailable")
        return False

    try:
        with get_connection() as conn:
            row = conn.execute('''
                SELECT a.application_id, a.program_applied, a.academic_year,
                       a.semester, a.decision, a.decision_date,
                       a.application_fee_paid,
                       p.first_name, p.last_name, p.email
                  FROM admission_applications a
                  JOIN admission_prospects   p ON p.prospect_id = a.prospect_id
                 WHERE a.application_id = ?
            ''', (application_id,)).fetchone()
    except Exception:
        logger.exception("applicant lookup failed app_id=%s", application_id)
        return False

    if not row:
        logger.warning("application %s not found", application_id)
        return False
    recipient = (row['email'] or '').strip()
    if not recipient:
        logger.warning("no email on file for application %s", application_id)
        return False

    name = f"{(row['first_name'] or '').strip()} {(row['last_name'] or '').strip()}".strip()
    vars_ = {
        'applicant_name':   name or 'Applicant',
        'application_id':   row['application_id'],
        'program_applied':  row['program_applied'] or '',
        'academic_year':    row['academic_year'] or '',
        'semester':         row['semester'] or '',
        'decision':         row['decision'] or '',
        'decision_date':    row['decision_date'] or datetime.now().date().isoformat(),
    }
    if extra_vars:
        vars_.update(extra_vars)

    subject, body = render_template(f"admissions/{template_name}", vars_)
    if not subject or not body:
        logger.error("template render failed: admissions/%s", template_name)
        return False

    try:
        send_email(recipient_email=recipient, subject=subject, body=body)
        logger.info("sent admissions/%s to %s (app_id=%s)",
                    template_name, recipient, application_id)
        return True
    except Exception:
        logger.exception("send_email failed admissions/%s recipient=%s",
                         template_name, recipient)
        return False


class ProspectManager:
    """Manages prospective students (leads)"""

    @staticmethod
    def create_prospect(first_name: str, last_name: str, email: str,
                       phone: str = "", date_of_birth: str = "", country: str = "",
                       state: str = "", city: str = "", high_school: str = "",
                       intended_major: str = "", source: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO admission_prospects (
                        first_name, last_name, email, phone, date_of_birth,
                        country, state, city, high_school, intended_major, source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (first_name, last_name, email, phone, date_of_birth,
                      country, state, city, high_school, intended_major, source))
                prospect_id = cursor.lastrowid
                return prospect_id
        except Exception as e:
            raise Exception(f"Error creating prospect: {e}")

    @staticmethod
    def update_prospect_status(prospect_id: int, status: str) -> bool:
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE admission_prospects
                    SET status = ?, last_contact_date = ?
                    WHERE prospect_id = ?
                ''', (status, datetime.now().isoformat(), prospect_id))
                return True
        except Exception as e:
            raise Exception(f"Error updating prospect: {e}")

    @staticmethod
    def log_interaction(prospect_id: int, interaction_type: str, notes: str = "",
                       staff_member: str = "", next_followup_date: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO prospect_interactions (
                        prospect_id, interaction_type, notes, staff_member, next_followup_date
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (prospect_id, interaction_type, notes, staff_member, next_followup_date))
                interaction_id = cursor.lastrowid
                return interaction_id
        except Exception as e:
            raise Exception(f"Error logging interaction: {e}")


class ApplicationManager:
    """Manages admission applications"""

    @staticmethod
    def submit_application(prospect_id: int, application_type: str,
                          program_applied: str, academic_year: str,
                          semester: str, application_fee_paid: bool = False) -> int:
        try:
            with transaction() as conn:
                # Verify prospect exists first
                cursor = conn.execute(
                    'SELECT prospect_id FROM admission_prospects WHERE prospect_id = ?',
                    (prospect_id,)
                )
                if not cursor.fetchone():
                    raise ValueError(f"Prospect ID {prospect_id} does not exist. Please create the prospect first.")

                cursor = conn.execute('''
                    INSERT INTO admission_applications (
                        prospect_id, application_type, program_applied,
                        academic_year, semester, application_fee_paid
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (prospect_id, application_type, program_applied,
                      academic_year, semester, application_fee_paid))
                application_id = cursor.lastrowid
                # Update prospect status
                conn.execute('''
                    UPDATE admission_prospects
                    SET status = 'applicant'
                    WHERE prospect_id = ?
                ''', (prospect_id,))
                return application_id
        except ValueError as ve:
            # Re-raise ValueError with clear message
            raise ve
        except Exception as e:
            # Check for foreign key constraint error
            if "FOREIGN KEY constraint failed" in str(e):
                raise Exception(f"Cannot create application: Prospect ID {prospect_id} does not exist in the system.")
            raise Exception(f"Error submitting application: {e}")

    @staticmethod
    def upload_document(application_id: int, document_type: str,
                       document_name: str, file_url: str) -> int:
        try:
            with transaction() as conn:
                # Verify application exists first
                cursor = conn.execute(
                    'SELECT application_id FROM admission_applications WHERE application_id = ?',
                    (application_id,)
                )
                if not cursor.fetchone():
                    raise ValueError(f"Application ID {application_id} does not exist.")

                cursor = conn.execute('''
                    INSERT INTO documents (
                        source_type, reference_id, reference_type,
                        document_type, document_name, file_path,
                        verification_status
                    ) VALUES ('application', ?, 'application', ?, ?, ?, 'pending')
                ''', (str(application_id), document_type, document_name, file_url))
                document_id = cursor.lastrowid
                return document_id
        except ValueError as ve:
            raise ve
        except Exception as e:
            if "FOREIGN KEY constraint failed" in str(e):
                raise Exception(f"Cannot upload document: Application ID {application_id} does not exist.")
            raise Exception(f"Error uploading document: {e}")

    @staticmethod
    def update_application_status(application_id: int, status: str) -> bool:
        """Update the status of an application"""
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE admission_applications
                    SET status = ?
                    WHERE application_id = ?
                ''', (status, application_id))
                return True
        except Exception as e:
            raise Exception(f"Error updating application status: {e}")

    @staticmethod
    def send_interview_invite(application_id: int, interview_date: str,
                              interview_time: str, interview_format: str = "On campus",
                              interview_location: str = "(to be confirmed)",
                              interviewers: str = "Admissions Committee",
                              interview_duration: int = 30,
                              confirm_by: str = "") -> bool:
        """Email the applicant an interview invitation. Best-effort."""
        try:
            ApplicationManager.update_application_status(application_id, 'interview_scheduled')
        except Exception:
            logger.exception("interview status update failed app_id=%s", application_id)
        return _send_applicant_email('interview_invite', application_id, {
            'interview_date':     interview_date,
            'interview_time':     interview_time,
            'interview_format':   interview_format,
            'interview_location': interview_location,
            'interviewers':       interviewers,
            'interview_duration': interview_duration,
            'confirm_by':         confirm_by or interview_date,
        })

    @staticmethod
    def send_deposit_reminder(application_id: int, deposit_amount,
                              deposit_due: str) -> bool:
        """Email the applicant a deposit-due reminder. Skips when the deposit
        is already marked paid. Best-effort."""
        try:
            with get_connection() as conn:
                row = conn.execute(
                    'SELECT application_fee_paid FROM admission_applications '
                    'WHERE application_id = ?', (application_id,)
                ).fetchone()
            if row and row['application_fee_paid']:
                logger.info("deposit already paid for app_id=%s — skipping reminder",
                            application_id)
                return False
        except Exception:
            logger.exception("deposit paid-status check failed app_id=%s", application_id)

        days_remaining = ""
        try:
            due = datetime.fromisoformat(deposit_due).date()
            days_remaining = str((due - datetime.now().date()).days)
        except Exception:
            pass

        return _send_applicant_email('deposit_reminder', application_id, {
            'deposit_amount': deposit_amount,
            'deposit_due':    deposit_due,
            'days_remaining': days_remaining or '(see portal)',
        })

    @staticmethod
    def make_decision(application_id: int, decision: str, decision_date: str = "") -> bool:
        try:
            with transaction() as conn:
                if not decision_date:
                    decision_date = datetime.now().date().isoformat()
                conn.execute('''
                    UPDATE admission_applications
                    SET decision = ?, decision_date = ?, status = 'decision_made'
                    WHERE application_id = ?
                ''', (decision, decision_date, application_id))
                row = conn.execute(
                    "SELECT prospect_id, application_fee_paid "
                    "FROM admission_applications WHERE application_id = ?",
                    (application_id,),
                ).fetchone()
            try:
                from education_system.university_system.modules.services.integration_bus import (
                    publish_admissions_decision,
                )
                publish_admissions_decision(
                    application_id=int(application_id),
                    decision=decision,
                    applicant_id=str(row[0]) if row and row[0] else None,
                    fee_paid=bool(row[1]) if row else False,
                )
            except Exception:
                pass
            # Notify the applicant: positive decisions use the offer-letter
            # template (deposit details supplied); everything else uses the
            # generic decision-notification template.
            decision_norm = (decision or '').strip().lower()
            if decision_norm in {'accept', 'accepted', 'offer', 'offered',
                                 'admit', 'admitted'}:
                _send_applicant_email('offer_letter', application_id, {
                    'offer_type':       'Unconditional',
                    'offer_conditions': 'None.',
                    'deposit_amount':   '500',
                    'deposit_due':      '(see applicant portal)',
                    'accept_by':        '(see applicant portal)',
                })
            else:
                display = {
                    'reject': 'Unsuccessful',
                    'rejected': 'Unsuccessful',
                    'waitlist': 'Waitlisted',
                    'waitlisted': 'Waitlisted',
                    'defer': 'Deferred',
                    'deferred': 'Deferred',
                }.get(decision_norm, (decision or 'Decision').title())
                message = {
                    'Unsuccessful': "After careful review, the committee is unable to offer you a place on this programme at this time.",
                    'Waitlisted':   "You have been placed on the waiting list. We will be in touch as soon as a place becomes available or a final decision is reached.",
                    'Deferred':     "Your application has been deferred to the next intake. No further action is required from you at this stage.",
                }.get(display, f"Your application has reached the following outcome: {display}.")
                _send_applicant_email('decision_notification', application_id, {
                    'decision_display': display,
                    'decision_message': message,
                    'decision_reason':  '(see committee notes on the applicant portal)',
                })
            return True
        except Exception as e:
            raise Exception(f"Error making decision: {e}")


class ReviewWorkflowManager:
    """Manages application review workflow"""

    @staticmethod
    def assign_reviewer(application_id: int, reviewer_id: str, review_stage: str = "initial") -> int:
        """Assign a reviewer to an application"""
        try:
            with transaction() as conn:
                # Verify application exists first
                cursor = conn.execute(
                    'SELECT application_id FROM admission_applications WHERE application_id = ?',
                    (application_id,)
                )
                if not cursor.fetchone():
                    raise ValueError(f"Application ID {application_id} does not exist.")

                cursor = conn.execute('''
                    INSERT INTO application_reviews (
                        application_id, reviewer_id, review_stage
                    ) VALUES (?, ?, ?)
                ''', (application_id, reviewer_id, review_stage))
                review_id = cursor.lastrowid
                return review_id
        except ValueError as ve:
            raise ve
        except Exception as e:
            if "FOREIGN KEY constraint failed" in str(e):
                raise Exception(f"Cannot assign reviewer: Application ID {application_id} does not exist.")
            raise Exception(f"Error assigning reviewer: {e}")

    @staticmethod
    def create_review(application_id: int, reviewer_id: str, review_stage: str,
                     score: Optional[int], recommendation: str, comments: str = "") -> int:
        try:
            with transaction() as conn:
                # Verify application exists first
                cursor = conn.execute(
                    'SELECT application_id FROM admission_applications WHERE application_id = ?',
                    (application_id,)
                )
                if not cursor.fetchone():
                    raise ValueError(f"Application ID {application_id} does not exist.")

                cursor = conn.execute('''
                    INSERT INTO application_reviews (
                        application_id, reviewer_id, review_stage,
                        score, recommendation, comments
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (application_id, reviewer_id, review_stage, score, recommendation, comments))
                review_id = cursor.lastrowid
                # Update application status
                conn.execute('''
                    UPDATE admission_applications
                    SET status = ?
                    WHERE application_id = ?
                ''', (f"in_review_{review_stage}", application_id))
                return review_id
        except ValueError as ve:
            raise ve
        except Exception as e:
            if "FOREIGN KEY constraint failed" in str(e):
                raise Exception(f"Cannot create review: Application ID {application_id} does not exist.")
            raise Exception(f"Error creating review: {e}")

    @staticmethod
    def get_application_reviews(application_id: int) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM application_reviews
                WHERE application_id = ?
                ORDER BY review_date
            ''', (application_id,))
            return [dict(row) for row in cursor.fetchall()]


class CampaignManager:
    """Manages recruitment communication campaigns"""

    @staticmethod
    def create_campaign(campaign_name: str, campaign_type: str,
                       target_audience: str, start_date: str,
                       end_date: str, message_template: str) -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO recruitment_campaigns (
                        campaign_name, campaign_type, target_audience,
                        start_date, end_date, message_template
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (campaign_name, campaign_type, target_audience,
                      start_date, end_date, message_template))
                campaign_id = cursor.lastrowid
                return campaign_id
        except Exception as e:
            raise Exception(f"Error creating campaign: {e}")

    @staticmethod
    def send_campaign_message(campaign_id: int, prospect_id: int) -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO campaign_messages (campaign_id, prospect_id)
                    VALUES (?, ?)
                ''', (campaign_id, prospect_id))
                message_id = cursor.lastrowid
                # Update campaign stats
                conn.execute('''
                    UPDATE recruitment_campaigns
                    SET sent_count = sent_count + 1
                    WHERE campaign_id = ?
                ''', (campaign_id,))
                return message_id
        except Exception as e:
            raise Exception(f"Error sending message: {e}")


class TourManager:
    """Manages campus tours"""

    @staticmethod
    def create_tour(tour_date: str, tour_time: str, tour_guide: str = "",
                   max_attendees: int = 20, meeting_point: str = "",
                   duration_minutes: int = 90) -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO campus_tours (
                        tour_date, tour_time, tour_guide, max_attendees,
                        meeting_point, duration_minutes
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (tour_date, tour_time, tour_guide, max_attendees,
                      meeting_point, duration_minutes))
                tour_id = cursor.lastrowid
                return tour_id
        except Exception as e:
            raise Exception(f"Error creating tour: {e}")

    @staticmethod
    def register_for_tour(tour_id: int, prospect_id: int, num_guests: int = 0) -> int:
        try:
            with transaction() as conn:
                # Check availability
                cursor = conn.execute('''
                    SELECT current_attendees, max_attendees
                    FROM campus_tours
                    WHERE tour_id = ?
                ''', (tour_id,))
                tour = cursor.fetchone()
                if tour and tour['current_attendees'] >= tour['max_attendees']:
                    raise Exception("Tour is full")

                cursor = conn.execute('''
                    INSERT INTO tour_registrations (tour_id, prospect_id, num_guests)
                    VALUES (?, ?, ?)
                ''', (tour_id, prospect_id, num_guests))
                registration_id = cursor.lastrowid
                # Update attendee count
                conn.execute('''
                    UPDATE campus_tours
                    SET current_attendees = current_attendees + 1 + ?
                    WHERE tour_id = ?
                ''', (num_guests, tour_id))
                return registration_id
        except Exception as e:
            raise Exception(f"Error registering for tour: {e}")


class YieldPredictionManager:
    """Manages yield predictions (enrollment probability)"""

    @staticmethod
    def create_prediction(application_id: int, predicted_probability: float,
                         model_version: str, factors: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO yield_predictions (
                        application_id, predicted_enrollment_probability,
                        model_version, factors
                    ) VALUES (?, ?, ?, ?)
                ''', (application_id, predicted_probability, model_version, factors))
                prediction_id = cursor.lastrowid
                return prediction_id
        except Exception as e:
            raise Exception(f"Error creating prediction: {e}")


def display_admissions_crm_menu(auth):
    """Display the Admissions & Recruitment CRM CLI menu"""
    print("\n" + "="*50)
    print("    ADMISSIONS & RECRUITMENT CRM")
    print("="*50)
    print("1. Manage Prospects")
    print("2. Application Review Workflow")
    print("3. Document Management")
    print("4. Recruitment Campaigns")
    print("5. Schedule Campus Tours")
    print("6. Yield Prediction Analytics")
    print("7. Prospect Communications")
    print("8. Return to Main Menu")
    print("="*50)

    while True:
        try:
            choice = input("\nEnter your choice (1-8): ").strip()
            if choice in ['1', '2', '3', '4', '5', '6', '7']:
                print(f"\n🎯 Feature available via Admissions managers")
                print("Use: from education_system.university_system.modules.domain.admissions.services import ProspectManager")
            elif choice == '8':
                break
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error: {e}")


# GUI launcher function (imported by main_gui.py directly from GUI module)
def launch_admissions_crm_gui(root, auth):
    """Launch the Admissions CRM GUI - placeholder, actual import should be from GUI module"""
    try:
        from education_system.university_system.modules.domain.admissions.gui.admissions_crm_gui import launch_admissions_crm_gui as _launch
        _launch(root, auth)
    except ImportError as e:
        from tkinter import messagebox
        messagebox.showerror("Error", f"Admissions CRM GUI is not available: {e}")



__all__ = [
    'ProspectManager', 'ApplicationManager', 'ReviewWorkflowManager',
    'CampaignManager', 'TourManager', 'YieldPredictionManager',
    'display_admissions_crm_menu',
    'launch_admissions_crm_gui',
]
