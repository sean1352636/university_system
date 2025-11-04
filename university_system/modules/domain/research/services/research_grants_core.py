"""
Research & Grants Management Core Service

Research projects, grant applications, publications, milestones,
equipment tracking, and IRB/ethics reviews.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.feature_gui_factory import create_gui_launcher


class ResearchProjectManager:
    """Manages research projects"""

    @staticmethod
    def create_project(project_title: str, principal_investigator_id: str,
                      department: str, project_type: str, start_date: str,
                      description: str = "", total_budget: float = 0) -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO research_projects (
                        project_title, principal_investigator_id, department,
                        project_type, start_date, project_description, total_budget
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (project_title, principal_investigator_id, department,
                      project_type, start_date, description, total_budget))
                project_id = cursor.lastrowid
                return project_id
        except Exception as e:
            raise Exception(f"Error creating research project: {e}")

    @staticmethod
    def add_team_member(project_id: int, staff_id: str, role: str,
                       contribution_percentage: float = 0) -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO research_team_members (
                        project_id, staff_id, role, contribution_percentage
                    ) VALUES (?, ?, ?, ?)
                ''', (project_id, staff_id, role, contribution_percentage))
                member_id = cursor.lastrowid
                return member_id
        except Exception as e:
            raise Exception(f"Error adding team member: {e}")


class GrantApplicationManager:
    """Manages grant applications"""

    @staticmethod
    def submit_application(grant_name: str, funding_agency: str,
                          principal_investigator_id: str, requested_amount: float,
                          application_deadline: str, project_id: int = None) -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO grant_applications (
                        grant_name, funding_agency, principal_investigator_id,
                        requested_amount, application_deadline, project_id
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (grant_name, funding_agency, principal_investigator_id,
                      requested_amount, application_deadline, project_id))
                application_id = cursor.lastrowid
                return application_id
        except Exception as e:
            raise Exception(f"Error submitting grant application: {e}")

    @staticmethod
    def update_decision(application_id: int, decision_status: str,
                       awarded_amount: float = 0, grant_period_start: str = "",
                       grant_period_end: str = "") -> bool:
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE grant_applications
                    SET decision_status = ?, decision_date = ?, awarded_amount = ?,
                        grant_period_start = ?, grant_period_end = ?
                    WHERE application_id = ?
                ''', (decision_status, datetime.now().date().isoformat(),
                      awarded_amount, grant_period_start, grant_period_end, application_id))
                return True
        except Exception as e:
            raise Exception(f"Error updating grant decision: {e}")


class PublicationManager:
    """Manages research publications"""

    @staticmethod
    def record_publication(title: str, authors: str, publication_type: str,
                          project_id: int = None, journal_name: str = "",
                          publication_date: str = "", doi: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO research_publications (
                        project_id, title, authors, publication_type,
                        journal_name, publication_date, doi
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (project_id, title, authors, publication_type,
                      journal_name, publication_date, doi))
                publication_id = cursor.lastrowid

                # Update project publication count
                if project_id:
                    conn.execute('''
                        UPDATE research_projects
                        SET publications_count = publications_count + 1
                        WHERE project_id = ?
                    ''', (project_id,))

                return publication_id
        except Exception as e:
            raise Exception(f"Error recording publication: {e}")


class MilestoneManager:
    """Manages research milestones"""

    @staticmethod
    def create_milestone(project_id: int, milestone_name: str,
                        target_date: str, description: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO research_milestones (
                        project_id, milestone_name, milestone_description, target_date
                    ) VALUES (?, ?, ?, ?)
                ''', (project_id, milestone_name, description, target_date))
                milestone_id = cursor.lastrowid
                return milestone_id
        except Exception as e:
            raise Exception(f"Error creating milestone: {e}")


class EquipmentManager:
    """Manages research equipment"""

    @staticmethod
    def register_equipment(equipment_name: str, equipment_type: str,
                          serial_number: str = "", purchase_cost: float = 0) -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO research_equipment (
                        equipment_name, equipment_type, serial_number, purchase_cost
                    ) VALUES (?, ?, ?, ?)
                ''', (equipment_name, equipment_type, serial_number, purchase_cost))
                equipment_id = cursor.lastrowid
                return equipment_id
        except Exception as e:
            raise Exception(f"Error registering equipment: {e}")


class EthicsReviewManager:
    """Manages IRB/ethics reviews"""

    @staticmethod
    def submit_ethics_review(project_id: int, review_type: str,
                            submission_date: str) -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO ethics_reviews (
                        project_id, review_type, submission_date
                    ) VALUES (?, ?, ?)
                ''', (project_id, review_type, submission_date))
                review_id = cursor.lastrowid
                return review_id
        except Exception as e:
            raise Exception(f"Error submitting ethics review: {e}")


def display_research_grants_menu(auth):
    """Display the Research & Grants Management CLI menu"""
    print("\n" + "="*50)
    print("    RESEARCH & GRANTS MANAGEMENT")
    print("="*50)
    print("1. Research Projects")
    print("2. Grant Applications")
    print("3. Publications Tracking")
    print("4. Milestone Management")
    print("5. Equipment Inventory")
    print("6. Ethics Review Board")
    print("7. Research Reports")
    print("8. Return to Main Menu")
    print("="*50)

    while True:
        try:
            choice = input("\nEnter your choice (1-8): ").strip()
            if choice in ['1', '2', '3', '4', '5', '6', '7']:
                print(f"\n🔬 Feature available via Research managers")
                print("Use: from university_system.modules.domain.research.services import ResearchProjectManager")
            elif choice == '8':
                break
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error: {e}")


# Use factory to create GUI launcher
launch_research_grants_gui = create_gui_launcher(
    title="Research & Grants Management",
    description="""Manage research projects, grants, publications, and equipment.

Features:
• Research project tracking
• Grant applications
• Publications management
• Milestone tracking
• Equipment inventory
• Ethics review board""",
    cli_instruction="Use CLI: Research & Grants Management"
)



__all__ = [
    'ResearchProjectManager', 'GrantApplicationManager', 'PublicationManager',
    'MilestoneManager', 'EquipmentManager', 'EthicsReviewManager',
    'display_research_grants_menu',
    'launch_research_grants_gui',
]
