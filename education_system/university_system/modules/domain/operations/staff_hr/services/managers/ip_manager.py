"""
Intellectual Property Manager

Provides functionality for:
- IP disclosure lifecycle management
- Inventor management
- Patent tracking
- License management
- Revenue recording and reporting
- Portfolio summary
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608


class IPManager:
    """Manager for intellectual property disclosures, patents, and licensing."""

    # ==================== DISCLOSURE LIFECYCLE ====================

    @staticmethod
    def create_disclosure(title: str, created_by: str, ip_type: str = 'invention',
                          description: str = None, development_stage: str = 'concept',
                          funding_source: str = None, department: str = None) -> int:
        """Create a new IP disclosure (draft)."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO ip_disclosures (
                    title, created_by, ip_type, description, development_stage,
                    funding_source, department, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?)
            ''', (
                title, created_by, ip_type, description, development_stage,
                funding_source, department,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            disclosure_id = cursor.lastrowid
            log_activity('create', 'ip_disclosure', details={
                'disclosure_id': disclosure_id, 'created_by': created_by,
                'ip_type': ip_type,
            })
            return disclosure_id

    @staticmethod
    def get_disclosure(disclosure_id: int) -> Optional[Dict[str, Any]]:
        """Get a single disclosure by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM ip_disclosures WHERE disclosure_id = ?
            ''', (disclosure_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_user_disclosures(user_id: str, status: str = None) -> List[Dict[str, Any]]:
        """Get disclosures for a user, optionally filtered by status."""
        with get_connection() as conn:
            query = '''
                SELECT * FROM ip_disclosures
                WHERE created_by = ?
            '''
            params = [user_id]

            if status:
                query += ' AND status = ?'
                params.append(status)

            query += ' ORDER BY created_at DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_disclosure(disclosure_id: int, **data) -> None:
        """Update disclosure fields. Only if status='draft'."""
        allowed_fields = {
            'title', 'description', 'ip_type', 'development_stage', 'funding_source',
        }

        with transaction() as conn:
            # Verify status is draft
            row = conn.execute('''
                SELECT status FROM ip_disclosures WHERE disclosure_id = ?
            ''', (disclosure_id,)).fetchone()

            if not row:
                raise ValueError(f"Disclosure {disclosure_id} not found")
            if row['status'] != 'draft':
                raise ValueError(
                    f"Cannot update disclosure {disclosure_id}: status is '{row['status']}', must be 'draft'"
                )

            fields = []
            values = []
            for key, value in data.items():
                if key in allowed_fields:
                    fields.append(validate_identifier(key, "column") + ' = ?')
                    values.append(value)

            if not fields:
                return

            fields.append('updated_at = ?')
            values.append(datetime.now().isoformat())
            values.append(disclosure_id)

            conn.execute(
                'UPDATE ip_disclosures SET ' + ', '.join(fields) + ' WHERE disclosure_id = ?',
                values)
            log_activity('update', 'ip_disclosure', details={
                'disclosure_id': disclosure_id, 'updated_fields': list(data.keys()),
            })

    @staticmethod
    def submit_disclosure(disclosure_id: int) -> None:
        """Submit a draft disclosure for review."""
        with transaction() as conn:
            conn.execute('''
                UPDATE ip_disclosures
                SET status = 'submitted', submitted_date = ?, updated_at = ?
                WHERE disclosure_id = ?
            ''', (datetime.now().isoformat(), datetime.now().isoformat(), disclosure_id))
            log_activity('update', 'ip_disclosure', details={
                'disclosure_id': disclosure_id, 'action': 'submitted',
            })

    @staticmethod
    def review_disclosure(disclosure_id: int, reviewer_id: str, status: str,
                          comments: str = None) -> None:
        """Review a disclosure (approved/rejected)."""
        with transaction() as conn:
            conn.execute('''
                UPDATE ip_disclosures
                SET status = ?, reviewed_by = ?, review_date = ?,
                    review_comments = ?, updated_at = ?
                WHERE disclosure_id = ?
            ''', (
                status, reviewer_id, datetime.now().isoformat(),
                comments, datetime.now().isoformat(), disclosure_id,
            ))
            log_activity('update', 'ip_disclosure', details={
                'disclosure_id': disclosure_id, 'action': 'reviewed',
                'status': status, 'reviewer': reviewer_id,
            })

    # ==================== INVENTOR MANAGEMENT ====================

    @staticmethod
    def add_inventor(disclosure_id: int, user_id: str,
                     contribution_percentage: float = 0, is_primary: bool = False,
                     patent_id: int = None) -> int:
        """Add an inventor to a disclosure or patent."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO ip_inventors (
                    disclosure_id, user_id, contribution_percentage,
                    is_primary, patent_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                disclosure_id, user_id, contribution_percentage,
                int(is_primary), patent_id, datetime.now().isoformat(),
            ))
            inventor_id = cursor.lastrowid
            log_activity('create', 'ip_inventor', details={
                'inventor_id': inventor_id, 'disclosure_id': disclosure_id,
                'user_id': user_id,
            })
            return inventor_id

    @staticmethod
    def get_inventors(disclosure_id: int = None,
                      patent_id: int = None) -> List[Dict[str, Any]]:
        """Get inventors filtered by disclosure_id or patent_id."""
        with get_connection() as conn:
            query = 'SELECT * FROM ip_inventors WHERE 1=1'
            params: list = []

            if disclosure_id is not None:
                query += ' AND disclosure_id = ?'
                params.append(disclosure_id)

            if patent_id is not None:
                query += ' AND patent_id = ?'
                params.append(patent_id)

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_inventor(inventor_id: int, contribution_percentage: float = None,
                        is_primary: bool = None) -> None:
        """Update inventor details."""
        fields = []
        values = []

        if contribution_percentage is not None:
            fields.append('contribution_percentage = ?')
            values.append(contribution_percentage)

        if is_primary is not None:
            fields.append('is_primary = ?')
            values.append(int(is_primary))

        if not fields:
            return

        values.append(inventor_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE ip_inventors SET ' + ', '.join(fields) + ' WHERE inventor_id = ?',
                values)
            log_activity('update', 'ip_inventor', details={
                'inventor_id': inventor_id,
            })

    @staticmethod
    def remove_inventor(inventor_id: int) -> None:
        """Remove an inventor."""
        with transaction() as conn:
            conn.execute('''
                DELETE FROM ip_inventors WHERE inventor_id = ?
            ''', (inventor_id,))
            log_activity('delete', 'ip_inventor', details={'inventor_id': inventor_id})

    # ==================== PATENT MANAGEMENT ====================

    @staticmethod
    def create_patent(title: str, disclosure_id: int = None,
                      patent_office: str = 'USPTO', status: str = 'pending') -> int:
        """Create a new patent record."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO patents (
                    title, disclosure_id, patent_office, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                title, disclosure_id, patent_office, status,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            patent_id = cursor.lastrowid
            log_activity('create', 'ip_patent', details={
                'patent_id': patent_id, 'title': title,
                'disclosure_id': disclosure_id,
            })
            return patent_id

    @staticmethod
    def get_patent(patent_id: int) -> Optional[Dict[str, Any]]:
        """Get a single patent by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM patents WHERE patent_id = ?
            ''', (patent_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_patents(status: str = None,
                    disclosure_id: int = None) -> List[Dict[str, Any]]:
        """Get patents with optional filters."""
        with get_connection() as conn:
            query = 'SELECT * FROM patents WHERE 1=1'
            params: list = []

            if status:
                query += ' AND status = ?'
                params.append(status)

            if disclosure_id is not None:
                query += ' AND disclosure_id = ?'
                params.append(disclosure_id)

            query += ' ORDER BY created_at DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_patent(patent_id: int, **data) -> None:
        """Update patent fields."""
        allowed_fields = {
            'patent_number', 'title', 'patent_office', 'filing_date',
            'publication_date', 'grant_date', 'expiry_date', 'status',
            'cost_to_date', 'notes',
        }

        if not data:
            return

        fields = []
        values = []
        for key, value in data.items():
            if key in allowed_fields:
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(patent_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE patents SET ' + ', '.join(fields) + ' WHERE patent_id = ?',
                values)
            log_activity('update', 'ip_patent', details={
                'patent_id': patent_id, 'updated_fields': list(data.keys()),
            })

    # ==================== LICENSE MANAGEMENT ====================

    @staticmethod
    def create_license(licensee_name: str, start_date: str,
                       patent_id: int = None, disclosure_id: int = None,
                       license_type: str = 'non_exclusive', royalty_rate: float = 0,
                       territory: str = 'worldwide',
                       annual_fee: float = 0) -> int:
        """Create a new license agreement."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO ip_licenses (
                    licensee_name, start_date, patent_id, disclosure_id,
                    license_type, royalty_rate, territory, annual_fee,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            ''', (
                licensee_name, start_date, patent_id, disclosure_id,
                license_type, royalty_rate, territory, annual_fee,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            license_id = cursor.lastrowid
            log_activity('create', 'ip_license', details={
                'license_id': license_id, 'licensee_name': licensee_name,
                'patent_id': patent_id,
            })
            return license_id

    @staticmethod
    def get_licenses(patent_id: int = None,
                     status: str = None) -> List[Dict[str, Any]]:
        """Get licenses with optional filters."""
        with get_connection() as conn:
            query = 'SELECT * FROM ip_licenses WHERE 1=1'
            params: list = []

            if patent_id is not None:
                query += ' AND patent_id = ?'
                params.append(patent_id)

            if status:
                query += ' AND status = ?'
                params.append(status)

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_license(license_id: int, **data) -> None:
        """Update license fields."""
        if not data:
            return

        fields = []
        values = []
        for key, value in data.items():
            if key not in ('license_id', 'created_at'):
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(license_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE ip_licenses SET ' + ', '.join(fields) + ' WHERE license_id = ?',
                values)
            log_activity('update', 'ip_license', details={
                'license_id': license_id, 'updated_fields': list(data.keys()),
            })

    # ==================== REVENUE ====================

    @staticmethod
    def record_revenue(license_id: int, period: str, total_revenue: float,
                       university_share: float = 0, inventor_share: float = 0,
                       department_share: float = 0) -> int:
        """Record revenue from a license."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO ip_revenue_shares (
                    license_id, period, total_revenue, university_share,
                    inventor_share, department_share, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                license_id, period, total_revenue, university_share,
                inventor_share, department_share,
                datetime.now().isoformat(),
            ))
            revenue_id = cursor.lastrowid
            log_activity('create', 'ip_revenue_shares', details={
                'revenue_id': revenue_id, 'license_id': license_id,
                'period': period, 'total_revenue': total_revenue,
            })
            return revenue_id

    @staticmethod
    def get_revenue(license_id: int = None,
                    period: str = None) -> List[Dict[str, Any]]:
        """Get revenue records with optional filters."""
        with get_connection() as conn:
            query = 'SELECT * FROM ip_revenue_shares WHERE 1=1'
            params: list = []

            if license_id is not None:
                query += ' AND license_id = ?'
                params.append(license_id)

            if period:
                query += ' AND period = ?'
                params.append(period)

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    # ==================== REPORTING ====================

    @staticmethod
    def get_portfolio_summary() -> Dict[str, Any]:
        """Get IP portfolio summary with counts and totals."""
        with get_connection() as conn:
            summary: Dict[str, Any] = {}

            # Disclosures by status
            rows = conn.execute('''
                SELECT status, COUNT(*) as count
                FROM ip_disclosures
                GROUP BY status
            ''').fetchall()
            summary['disclosures_by_status'] = {r['status']: r['count'] for r in rows}

            # Patents by status
            rows = conn.execute('''
                SELECT status, COUNT(*) as count
                FROM patents
                GROUP BY status
            ''').fetchall()
            summary['patents_by_status'] = {r['status']: r['count'] for r in rows}

            # Total revenue
            row = conn.execute('''
                SELECT COALESCE(SUM(total_revenue), 0) as total
                FROM ip_revenue_shares
            ''').fetchone()
            summary['total_revenue'] = row['total'] if row else 0

            # Active licenses count
            row = conn.execute('''
                SELECT COUNT(*) as count
                FROM ip_licenses
                WHERE status = 'active'
            ''').fetchone()
            summary['active_licenses'] = row['count'] if row else 0

            return summary
