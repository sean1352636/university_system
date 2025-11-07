"""
Admissions & Recruitment CRM Core Service

Prospect management, application processing, review workflows,
communication campaigns, campus tours, and yield predictions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from university_system.infrastructure.database.db import get_connection, transaction


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
        except Exception as e:
            raise Exception(f"Error submitting application: {e}")

    @staticmethod
    def upload_document(application_id: int, document_type: str,
                       document_name: str, file_url: str) -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO application_documents (
                        application_id, document_type, document_name, file_url
                    ) VALUES (?, ?, ?, ?)
                ''', (application_id, document_type, document_name, file_url))
                document_id = cursor.lastrowid
                return document_id
        except Exception as e:
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
                cursor = conn.execute('''
                    INSERT INTO application_reviews (
                        application_id, reviewer_id, review_stage
                    ) VALUES (?, ?, ?)
                ''', (application_id, reviewer_id, review_stage))
                review_id = cursor.lastrowid
                return review_id
        except Exception as e:
            raise Exception(f"Error assigning reviewer: {e}")

    @staticmethod
    def create_review(application_id: int, reviewer_id: str, review_stage: str,
                     score: Optional[int], recommendation: str, comments: str = "") -> int:
        try:
            with transaction() as conn:
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
        except Exception as e:
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
                print("Use: from university_system.modules.domain.admissions.services import ProspectManager")
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
        from university_system.modules.domain.admissions.gui.admissions_crm_gui import launch_admissions_crm_gui as _launch
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
