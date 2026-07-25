"""
Comprehensive Financial Aid Manager
Handles financial aid applications, FAFSA data, aid packages, and disbursements
"""

from education_system.systems.university.infrastructure.database.db import sqlite3
import json
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH
from education_system.systems.university.infrastructure.i18n import get_text

class FinancialAidManager:
    """Comprehensive manager for financial aid operations"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DEFAULT_DB_PATH

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    # ==== Financial Aid Applications ====
    def create_application(
        self,
        student_id: int,
        academic_year: str,
        application_data: Optional[Dict[str, Any]] = None,
        family_income: Optional[float] = None,
        household_size: Optional[int] = None,
        special_circumstances: Optional[str] = None,
        submitted_by: Optional[int] = None
    ) -> Optional[int]:
        """
        Create a new financial aid application

        Args:
            student_id: Student ID
            academic_year: Academic year (e.g., "2024-2025")
            application_data: Dict containing application data (alternative to individual params)
            family_income: Household income (or from application_data)
            household_size: Number in household (or from application_data)
            special_circumstances: Special circumstances text (or from application_data)
            submitted_by: User ID who submitted

        Returns:
            Application ID if successful, None otherwise
        """
        try:
            # Extract from application_data if provided
            if application_data:
                family_income = application_data.get('household_income', family_income)
                household_size = application_data.get('dependents', household_size)
                special_circumstances = application_data.get('additional_info', special_circumstances)

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO financial_aid_applications (
                        student_id, academic_year, family_income, household_size,
                        special_circumstances, submitted_by
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (student_id, academic_year, family_income, household_size,
                      special_circumstances, submitted_by))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(get_text("financial_aid.aid_manager.error_creating_application", "Error creating financial aid application: {e}").format(e=e))
            return None

    def update_application_status(
        self,
        application_id: int,
        status: str,
        reviewed_by: Optional[int] = None,
        review_notes: Optional[str] = None
    ) -> bool:
        """Update application status"""
        valid_statuses = ['pending', 'under_review', 'approved', 'denied']
        if status not in valid_statuses:
            return False

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE financial_aid_applications
                    SET status = ?, reviewed_by = ?, review_date = CURRENT_TIMESTAMP,
                        review_notes = ?
                    WHERE application_id = ?
                """, (status, reviewed_by, review_notes, application_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(get_text("financial_aid.aid_manager.error_updating_application_status", "Error updating application status: {e}").format(e=e))
            return False

    # ==== FAFSA Management ====
    def import_fafsa_data(
        self,
        student_id: int,
        academic_year: str,
        efc: int,
        submission_date: date,
        sai: Optional[int] = None,
        dependency_status: str = 'dependent',
        pell_eligible: bool = False,
        pell_amount: float = 0
    ) -> Optional[int]:
        """Import FAFSA data for a student"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO fafsa_data (
                        student_id, academic_year, efc, submission_date, sai,
                        dependency_status, pell_eligible, pell_amount
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(student_id, academic_year) DO UPDATE SET
                        efc = excluded.efc,
                        submission_date = excluded.submission_date,
                        sai = excluded.sai,
                        dependency_status = excluded.dependency_status,
                        pell_eligible = excluded.pell_eligible,
                        pell_amount = excluded.pell_amount,
                        imported_at = CURRENT_TIMESTAMP
                """, (student_id, academic_year, efc, submission_date, sai,
                      dependency_status, 1 if pell_eligible else 0, pell_amount))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(get_text("financial_aid.aid_manager.error_importing_fafsa_data", "Error importing FAFSA data: {e}").format(e=e))
            return None

    def get_fafsa_data(self, student_id: int, academic_year: str) -> Optional[Dict[str, Any]]:
        """Get FAFSA data for a student"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM fafsa_data
                    WHERE student_id = ? AND academic_year = ?
                """, (student_id, academic_year))

                row = cursor.fetchone()
                if row:
                    columns = [d[0] for d in cursor.description]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            print(get_text("financial_aid.aid_manager.error_getting_fafsa_data", "Error getting FAFSA data: {e}").format(e=e))
            return None

    # ==== Aid Packages ====
    def create_aid_package(
        self,
        student_id: int,
        academic_year: str,
        created_by: Optional[int] = None,
        response_deadline: Optional[date] = None
    ) -> Optional[int]:
        """Create an aid package for a student"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Use student_financial_aid table instead of aid_packages
                # Check if table exists first
                table_check = cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='student_financial_aid'
                """).fetchone()

                if not table_check:
                    print(get_text("financial_aid.aid_manager.error_table_not_exists", "Error: student_financial_aid table does not exist"))
                    return None

                # Insert into student_financial_aid table with appropriate fields
                cursor.execute("""
                    INSERT INTO student_financial_aid (
                        student_id, aid_type_id, awarded_amount, disbursed_amount,
                        remaining_amount, status, application_date
                    ) VALUES (?, 1, 0, 0, 0, 'pending', CURRENT_DATE)
                """, (student_id,))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(get_text("financial_aid.aid_manager.error_creating_aid_package", "Error creating aid package: {e}").format(e=e))
            return None

    def add_aid_component(
        self,
        package_id: int,
        aid_type: str,
        name: str,
        amount: float,
        source: str = 'institutional',
        is_need_based: bool = False,
        is_renewable: bool = False,
        disbursement_plan: Optional[List[Dict]] = None
    ) -> Optional[int]:
        """Add a component to an aid package"""
        valid_types = ['grant', 'scholarship', 'loan', 'work_study']
        if aid_type not in valid_types:
            return None

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                disbursement_json = json.dumps(disbursement_plan) if disbursement_plan else None

                cursor.execute("""
                    INSERT INTO aid_components (
                        package_id, aid_type, source, name, amount,
                        disbursement_plan, is_need_based, is_renewable
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (package_id, aid_type, source, name, amount,
                      disbursement_json, 1 if is_need_based else 0, 1 if is_renewable else 0))

                # Update package totals
                from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608
                total_col = "total_" + aid_type + "s"
                validate_identifier(total_col, "column")
                cursor.execute(
                    "UPDATE aid_packages"
                    " SET [" + total_col + "] = [" + total_col + "] + ?,"
                    " total_aid_amount = total_aid_amount + ?"
                    " WHERE package_id = ?",
                    (amount, amount, package_id))

                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(get_text("financial_aid.aid_manager.error_adding_aid_component", "Error adding aid component: {e}").format(e=e))
            return None

    def get_aid_package(self, student_id: int, academic_year: str) -> Optional[Dict[str, Any]]:
        """Get complete aid package for a student"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get package
                cursor.execute("""
                    SELECT * FROM aid_packages
                    WHERE student_id = ? AND academic_year = ?
                """, (student_id, academic_year))

                package_row = cursor.fetchone()
                if not package_row:
                    return None

                columns = [d[0] for d in cursor.description]
                package = dict(zip(columns, package_row))

                # Get components
                cursor.execute("""
                    SELECT * FROM aid_components
                    WHERE package_id = ?
                    ORDER BY aid_type, amount DESC
                """, (package['package_id'],))

                component_columns = [d[0] for d in cursor.description]
                package['components'] = [
                    dict(zip(component_columns, row))
                    for row in cursor.fetchall()
                ]

                return package
        except Exception as e:
            print(get_text("financial_aid.aid_manager.error_getting_aid_package", "Error getting aid package: {e}").format(e=e))
            return None

    def accept_aid_package(self, package_id: int) -> bool:
        """Student accepts aid package"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE aid_packages
                    SET package_status = 'accepted',
                        response_date = CURRENT_DATE
                    WHERE package_id = ?
                """, (package_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(get_text("financial_aid.aid_manager.error_accepting_aid_package", "Error accepting aid package: {e}").format(e=e))
            return False

    # ==== Disbursements ====
    def create_disbursement(
        self,
        student_id: int,
        amount: float,
        disbursement_date: date,
        disbursement_type: str,
        academic_term: str,
        award_id: Optional[int] = None,
        component_id: Optional[int] = None
    ) -> Optional[int]:
        """Create a disbursement"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO disbursements (
                        student_id, amount, disbursement_date, disbursement_type,
                        academic_term, award_id, component_id, scheduled_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (student_id, amount, disbursement_date, disbursement_type,
                      academic_term, award_id, component_id, disbursement_date))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(get_text("financial_aid.aid_manager.error_creating_disbursement", "Error creating disbursement: {e}").format(e=e))
            return None

    def process_disbursement(
        self,
        disbursement_id: int,
        processed_by: int,
        transaction_id: Optional[str] = None
    ) -> bool:
        """Process a pending disbursement"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE disbursements
                    SET status = 'processed',
                        processed_by = ?,
                        processed_at = CURRENT_TIMESTAMP,
                        transaction_id = ?
                    WHERE disbursement_id = ? AND status = 'pending'
                """, (processed_by, transaction_id, disbursement_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(get_text("financial_aid.aid_manager.error_processing_disbursement", "Error processing disbursement: {e}").format(e=e))
            return False

    def get_pending_disbursements(self, academic_term: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all pending disbursements"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT d.*, s.first_name, s.last_name
                    FROM disbursements d
                    LEFT JOIN students s ON d.student_id = s.student_id
                    WHERE d.status = 'pending'
                """
                params = []

                if academic_term:
                    query += " AND d.academic_term = ?"
                    params.append(academic_term)

                query += " ORDER BY d.disbursement_date ASC"

                cursor.execute(query, params)
                columns = [d[0] for d in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(get_text("financial_aid.aid_manager.error_getting_pending_disbursements", "Error getting pending disbursements: {e}").format(e=e))
            return []
