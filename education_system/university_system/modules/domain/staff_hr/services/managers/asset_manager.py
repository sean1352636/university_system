"""
Asset Manager

Handles asset/equipment tracking, assignments, issues,
maintenance scheduling, and asset lifecycle management.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608

try:
    from education_system.university_system.modules.shared.utils.activity_logger import log_activity
except ImportError:
    def log_activity(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)


class AssetManager:
    """Manager for asset/equipment tracking."""

    # ==================== ASSET CATEGORIES ====================

    @staticmethod
    def get_categories(active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all asset categories."""
        with get_connection() as conn:
            if active_only:
                rows = conn.execute('''
                    SELECT * FROM asset_categories WHERE is_active = 1
                    ORDER BY name
                ''').fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM asset_categories ORDER BY name
                ''').fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_category(category_id: int) -> Optional[Dict[str, Any]]:
        """Get a category by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM asset_categories WHERE category_id = ?
            ''', (category_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_category(name: str, **data) -> int:
        """Create a new asset category."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO asset_categories (
                    name, description, depreciation_years,
                    requires_approval, parent_category_id, is_active
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                name,
                data.get('description'),
                data.get('depreciation_years', 5),
                data.get('requires_approval', 0),
                data.get('parent_category_id'),
                data.get('is_active', 1),
            ))
            category_id = cursor.lastrowid
            log_activity('create', 'asset_category',
                        details={'category_id': category_id, 'name': name})
            return category_id

    # ==================== ASSET CRUD ====================

    @staticmethod
    def get_assets(status: Optional[str] = None,
                   category_id: Optional[int] = None,
                   department: Optional[str] = None,
                   location: Optional[str] = None,
                   search: Optional[str] = None,
                   limit: int = 50,
                   offset: int = 0) -> List[Dict[str, Any]]:
        """Get assets with optional filters."""
        with get_connection() as conn:
            query = '''
                SELECT a.*, c.name as category_name
                FROM assets a
                LEFT JOIN asset_categories c ON a.category_id = c.category_id
                WHERE 1=1
            '''
            params = []

            if status:
                query += ' AND a.status = ?'
                params.append(status)

            if category_id:
                query += ' AND a.category_id = ?'
                params.append(category_id)

            if department:
                query += ' AND a.department = ?'
                params.append(department)

            if location:
                query += ' AND (a.location = ? OR a.building = ?)'
                params.extend([location, location])

            if search:
                query += '''
                    AND (a.asset_tag LIKE ?
                         OR a.name LIKE ?
                         OR a.serial_number LIKE ?
                         OR a.description LIKE ?)
                '''
                search_term = f'%{search}%'
                params.extend([search_term] * 4)

            query += ' ORDER BY a.asset_tag LIMIT ? OFFSET ?'
            params.extend([limit, offset])

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_asset(asset_id: int) -> Optional[Dict[str, Any]]:
        """Get a single asset by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT a.*, c.name as category_name
                FROM assets a
                LEFT JOIN asset_categories c ON a.category_id = c.category_id
                WHERE a.asset_id = ?
            ''', (asset_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_asset_by_tag(asset_tag: str) -> Optional[Dict[str, Any]]:
        """Get an asset by its tag."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT a.*, c.name as category_name
                FROM assets a
                LEFT JOIN asset_categories c ON a.category_id = c.category_id
                WHERE a.asset_tag = ?
            ''', (asset_tag,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_asset(name: str, category_id: int, created_by: str,
                     **data) -> Tuple[int, str]:
        """Create a new asset. Returns (asset_id, asset_tag)."""
        with transaction() as conn:
            # Generate asset tag
            asset_tag = data.get('asset_tag') or AssetManager._generate_tag(
                conn, category_id)

            cursor = conn.execute('''
                INSERT INTO assets (
                    asset_tag, name, description, category_id,
                    serial_number, manufacturer, model,
                    purchase_date, purchase_price, supplier,
                    warranty_start, warranty_expiry, warranty_provider,
                    current_value, location, building, room, department,
                    status, condition, barcode, qr_code,
                    image_path, notes, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                asset_tag,
                name,
                data.get('description'),
                category_id,
                data.get('serial_number'),
                data.get('manufacturer'),
                data.get('model'),
                data.get('purchase_date'),
                data.get('purchase_price'),
                data.get('supplier'),
                data.get('warranty_start'),
                data.get('warranty_expiry'),
                data.get('warranty_provider'),
                data.get('current_value') or data.get('purchase_price'),
                data.get('location'),
                data.get('building'),
                data.get('room'),
                data.get('department'),
                data.get('status', 'available'),
                data.get('condition', 'good'),
                data.get('barcode'),
                data.get('qr_code'),
                data.get('image_path'),
                data.get('notes'),
                created_by,
            ))
            asset_id = cursor.lastrowid

            # Create audit log entry
            AssetManager._log_audit(conn, asset_id, 'create', created_by,
                                   new_values={'name': name, 'tag': asset_tag})

            log_activity('create', 'asset', details={
                'asset_id': asset_id, 'asset_tag': asset_tag, 'name': name
            })
            return asset_id, asset_tag

    @staticmethod
    def update_asset(asset_id: int, updated_by: str, **data) -> bool:
        """Update an asset."""
        if not data:
            return False

        # Get current values for audit
        current = AssetManager.get_asset(asset_id)
        if not current:
            return False

        fields = []
        values = []
        old_values = {}
        new_values = {}

        for key, value in data.items():
            if key not in ('asset_id', 'asset_tag', 'created_at', 'created_by'):
                if current.get(key) != value:
                    old_values[key] = current.get(key)
                    new_values[key] = value
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return False

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(asset_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE assets SET ' + ', '.join(fields) + ' WHERE asset_id = ?',
                values)

            # Create audit log entry
            if old_values:
                AssetManager._log_audit(conn, asset_id, 'update', updated_by,
                                       old_values=old_values, new_values=new_values)

            log_activity('update', 'asset', details={'asset_id': asset_id})
            return True

    @staticmethod
    def delete_asset(asset_id: int, deleted_by: str,
                     method: Optional[str] = None) -> bool:
        """Soft delete (dispose) an asset."""
        with transaction() as conn:
            conn.execute('''
                UPDATE assets
                SET status = 'disposed',
                    disposal_date = ?,
                    disposal_method = ?,
                    updated_at = ?
                WHERE asset_id = ?
            ''', (datetime.now().isoformat(), method,
                  datetime.now().isoformat(), asset_id))

            AssetManager._log_audit(conn, asset_id, 'dispose', deleted_by,
                                   new_values={'method': method})

            log_activity('delete', 'asset', details={'asset_id': asset_id})
            return True

    # ==================== ASSET ASSIGNMENTS ====================

    @staticmethod
    def assign_asset(asset_id: int, user_id: str, assigned_by: str,
                     **data) -> int:
        """Assign an asset to a user."""
        with transaction() as conn:
            # Check asset is available
            asset = conn.execute('''
                SELECT status FROM assets WHERE asset_id = ?
            ''', (asset_id,)).fetchone()

            if not asset or asset[0] not in ('available', 'returned'):
                raise ValueError(f"Asset {asset_id} is not available for assignment")

            # Create assignment
            cursor = conn.execute('''
                INSERT INTO asset_assignments (
                    asset_id, user_id, user_name, user_department,
                    assigned_by, assigned_by_name, assigned_date,
                    expected_return_date, purpose, location, checkout_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                asset_id,
                user_id,
                data.get('user_name'),
                data.get('user_department'),
                assigned_by,
                data.get('assigned_by_name'),
                datetime.now().isoformat(),
                data.get('expected_return_date'),
                data.get('purpose'),
                data.get('location'),
                data.get('checkout_notes'),
            ))
            assignment_id = cursor.lastrowid

            # Update asset status
            conn.execute('''
                UPDATE assets
                SET status = 'assigned', updated_at = ?
                WHERE asset_id = ?
            ''', (datetime.now().isoformat(), asset_id))

            AssetManager._log_audit(conn, asset_id, 'assign', assigned_by,
                                   new_values={'assigned_to': user_id})

            log_activity('assign', 'asset', details={
                'asset_id': asset_id, 'user_id': user_id
            })
            return assignment_id

    @staticmethod
    def return_asset(asset_id: int, returned_by: str,
                     condition: str = 'good', **data) -> bool:
        """Return an assigned asset."""
        with transaction() as conn:
            # Find active assignment
            assignment = conn.execute('''
                SELECT assignment_id, user_id FROM asset_assignments
                WHERE asset_id = ? AND status = 'active'
            ''', (asset_id,)).fetchone()

            if not assignment:
                raise ValueError(f"No active assignment found for asset {asset_id}")

            # Update assignment
            conn.execute('''
                UPDATE asset_assignments
                SET status = 'returned',
                    actual_return_date = ?,
                    return_condition = ?,
                    return_notes = ?,
                    return_processed_by = ?,
                    updated_at = ?
                WHERE assignment_id = ?
            ''', (
                datetime.now().isoformat(),
                condition,
                data.get('return_notes'),
                returned_by,
                datetime.now().isoformat(),
                assignment[0],
            ))

            # Update asset status and condition
            conn.execute('''
                UPDATE assets
                SET status = 'available',
                    condition = ?,
                    updated_at = ?
                WHERE asset_id = ?
            ''', (condition, datetime.now().isoformat(), asset_id))

            AssetManager._log_audit(conn, asset_id, 'return', returned_by,
                                   new_values={'condition': condition})

            log_activity('return', 'asset', details={'asset_id': asset_id})
            return True

    @staticmethod
    def get_user_assets(user_id: str,
                        include_history: bool = False) -> List[Dict[str, Any]]:
        """Get assets assigned to a user."""
        with get_connection() as conn:
            if include_history:
                rows = conn.execute('''
                    SELECT aa.*, a.name, a.asset_tag, a.serial_number,
                           c.name as category_name
                    FROM asset_assignments aa
                    JOIN assets a ON aa.asset_id = a.asset_id
                    LEFT JOIN asset_categories c ON a.category_id = c.category_id
                    WHERE aa.user_id = ?
                    ORDER BY aa.assigned_date DESC
                ''', (user_id,)).fetchall()
            else:
                rows = conn.execute('''
                    SELECT aa.*, a.name, a.asset_tag, a.serial_number,
                           c.name as category_name
                    FROM asset_assignments aa
                    JOIN assets a ON aa.asset_id = a.asset_id
                    LEFT JOIN asset_categories c ON a.category_id = c.category_id
                    WHERE aa.user_id = ? AND aa.status = 'active'
                    ORDER BY aa.assigned_date DESC
                ''', (user_id,)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_assignment_history(asset_id: int) -> List[Dict[str, Any]]:
        """Get assignment history for an asset."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM asset_assignments
                WHERE asset_id = ?
                ORDER BY assigned_date DESC
            ''', (asset_id,)).fetchall()
            return [dict(row) for row in rows]

    # ==================== ASSET ISSUES ====================

    @staticmethod
    def report_issue(asset_id: int, reported_by: str, issue_type: str,
                     title: str, description: str, **data) -> int:
        """Report an issue with an asset."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO asset_issues (
                    asset_id, reported_by, reported_by_name,
                    issue_type, severity, priority, title, description,
                    impact, steps_to_reproduce, assigned_to, assigned_to_name,
                    estimated_resolution_date, attachments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                asset_id,
                reported_by,
                data.get('reported_by_name'),
                issue_type,
                data.get('severity', 'medium'),
                data.get('priority', 'normal'),
                title,
                description,
                data.get('impact'),
                data.get('steps_to_reproduce'),
                data.get('assigned_to'),
                data.get('assigned_to_name'),
                data.get('estimated_resolution_date'),
                data.get('attachments'),
            ))
            issue_id = cursor.lastrowid

            # Update asset status if critical
            if data.get('severity') == 'critical':
                conn.execute('''
                    UPDATE assets SET status = 'in_repair', updated_at = ?
                    WHERE asset_id = ?
                ''', (datetime.now().isoformat(), asset_id))

            AssetManager._log_audit(conn, asset_id, 'issue_reported', reported_by,
                                   new_values={'issue_id': issue_id, 'type': issue_type})

            log_activity('create', 'asset_issue', details={
                'asset_id': asset_id, 'issue_id': issue_id
            })
            return issue_id

    @staticmethod
    def get_issues(asset_id: Optional[int] = None,
                   status: Optional[str] = None,
                   severity: Optional[str] = None,
                   limit: int = 50,
                   offset: int = 0) -> List[Dict[str, Any]]:
        """Get asset issues with optional filters."""
        with get_connection() as conn:
            query = '''
                SELECT i.*, a.name as asset_name, a.asset_tag
                FROM asset_issues i
                JOIN assets a ON i.asset_id = a.asset_id
                WHERE 1=1
            '''
            params = []

            if asset_id:
                query += ' AND i.asset_id = ?'
                params.append(asset_id)

            if status:
                query += ' AND i.status = ?'
                params.append(status)

            if severity:
                query += ' AND i.severity = ?'
                params.append(severity)

            query += ' ORDER BY i.reported_date DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def resolve_issue(issue_id: int, resolved_by: str, resolution: str,
                      **data) -> bool:
        """Resolve an asset issue."""
        with transaction() as conn:
            # Get issue details
            issue = conn.execute('''
                SELECT asset_id FROM asset_issues WHERE issue_id = ?
            ''', (issue_id,)).fetchone()

            if not issue:
                return False

            conn.execute('''
                UPDATE asset_issues
                SET status = 'resolved',
                    resolution = ?,
                    resolution_notes = ?,
                    resolved_by = ?,
                    resolved_by_name = ?,
                    resolved_date = ?,
                    resolution_cost = ?,
                    updated_at = ?
                WHERE issue_id = ?
            ''', (
                resolution,
                data.get('resolution_notes'),
                resolved_by,
                data.get('resolved_by_name'),
                datetime.now().isoformat(),
                data.get('resolution_cost'),
                datetime.now().isoformat(),
                issue_id,
            ))

            # Update asset status back to available if needed
            conn.execute('''
                UPDATE assets
                SET status = 'available', updated_at = ?
                WHERE asset_id = ? AND status = 'in_repair'
            ''', (datetime.now().isoformat(), issue[0]))

            log_activity('resolve', 'asset_issue', details={'issue_id': issue_id})
            return True

    # ==================== ASSET MAINTENANCE ====================

    @staticmethod
    def schedule_maintenance(asset_id: int, maintenance_type: str,
                            scheduled_date: str, created_by: str,
                            **data) -> int:
        """Schedule maintenance for an asset."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO asset_maintenance (
                    asset_id, maintenance_type, maintenance_category,
                    title, description, scheduled_date, scheduled_time,
                    vendor, vendor_contact, priority,
                    approval_required, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                asset_id,
                maintenance_type,
                data.get('maintenance_category', 'routine'),
                data.get('title'),
                data.get('description'),
                scheduled_date,
                data.get('scheduled_time'),
                data.get('vendor'),
                data.get('vendor_contact'),
                data.get('priority', 'normal'),
                data.get('approval_required', 0),
                data.get('notes'),
            ))
            maintenance_id = cursor.lastrowid

            AssetManager._log_audit(conn, asset_id, 'maintenance_scheduled',
                                   created_by, new_values={
                                       'maintenance_id': maintenance_id,
                                       'type': maintenance_type
                                   })

            log_activity('create', 'asset_maintenance', details={
                'asset_id': asset_id, 'maintenance_id': maintenance_id
            })
            return maintenance_id

    @staticmethod
    def complete_maintenance(maintenance_id: int, completed_by: str,
                            **data) -> bool:
        """Complete a maintenance task."""
        with transaction() as conn:
            # Get asset_id
            maint = conn.execute('''
                SELECT asset_id FROM asset_maintenance WHERE maintenance_id = ?
            ''', (maintenance_id,)).fetchone()

            if not maint:
                return False

            conn.execute('''
                UPDATE asset_maintenance
                SET status = 'completed',
                    completed_date = ?,
                    performed_by = ?,
                    performed_by_name = ?,
                    cost = ?,
                    labor_cost = ?,
                    parts_cost = ?,
                    parts_replaced = ?,
                    work_performed = ?,
                    findings = ?,
                    recommendations = ?,
                    next_maintenance_date = ?,
                    next_maintenance_type = ?,
                    downtime_hours = ?,
                    updated_at = ?
                WHERE maintenance_id = ?
            ''', (
                datetime.now().isoformat(),
                completed_by,
                data.get('performed_by_name'),
                data.get('cost', 0),
                data.get('labor_cost', 0),
                data.get('parts_cost', 0),
                data.get('parts_replaced'),
                data.get('work_performed'),
                data.get('findings'),
                data.get('recommendations'),
                data.get('next_maintenance_date'),
                data.get('next_maintenance_type'),
                data.get('downtime_hours', 0),
                datetime.now().isoformat(),
                maintenance_id,
            ))

            # Update asset's next inspection date if provided
            if data.get('next_maintenance_date'):
                conn.execute('''
                    UPDATE assets
                    SET next_inspection_date = ?,
                        last_inspection_date = ?,
                        updated_at = ?
                    WHERE asset_id = ?
                ''', (data.get('next_maintenance_date'),
                      datetime.now().isoformat()[:10],
                      datetime.now().isoformat(),
                      maint[0]))

            log_activity('complete', 'asset_maintenance', details={
                'maintenance_id': maintenance_id
            })
            return True

    @staticmethod
    def get_maintenance_schedule(upcoming_days: int = 30,
                                 status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get upcoming maintenance schedule."""
        with get_connection() as conn:
            query = '''
                SELECT m.*, a.name as asset_name, a.asset_tag, a.location
                FROM asset_maintenance m
                JOIN assets a ON m.asset_id = a.asset_id
                WHERE m.scheduled_date <= date('now', '+' || ? || ' days')
            '''
            params = [upcoming_days]

            if status:
                query += ' AND m.status = ?'
                params.append(status)
            else:
                query += " AND m.status IN ('scheduled', 'in_progress')"

            query += ' ORDER BY m.scheduled_date'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    # ==================== ASSET REQUESTS ====================

    @staticmethod
    def create_request(requested_by: str, item_name: str,
                       category_id: int, **data) -> int:
        """Create a new asset request."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO asset_requests (
                    requested_by, requested_by_name, department,
                    category_id, request_type, item_name, item_description,
                    quantity, preferred_vendor, estimated_cost, budget_code,
                    justification, business_case, urgency, needed_by_date,
                    attachments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                requested_by,
                data.get('requested_by_name'),
                data.get('department'),
                category_id,
                data.get('request_type', 'new'),
                item_name,
                data.get('item_description'),
                data.get('quantity', 1),
                data.get('preferred_vendor'),
                data.get('estimated_cost'),
                data.get('budget_code'),
                data.get('justification'),
                data.get('business_case'),
                data.get('urgency', 'normal'),
                data.get('needed_by_date'),
                data.get('attachments'),
            ))
            request_id = cursor.lastrowid

            log_activity('create', 'asset_request', details={
                'request_id': request_id, 'item': item_name
            })
            return request_id

    @staticmethod
    def get_requests(status: Optional[str] = None,
                     requested_by: Optional[str] = None,
                     department: Optional[str] = None,
                     limit: int = 50,
                     offset: int = 0) -> List[Dict[str, Any]]:
        """Get asset requests with optional filters."""
        with get_connection() as conn:
            query = '''
                SELECT r.*, c.name as category_name
                FROM asset_requests r
                LEFT JOIN asset_categories c ON r.category_id = c.category_id
                WHERE 1=1
            '''
            params = []

            if status:
                query += ' AND r.status = ?'
                params.append(status)

            if requested_by:
                query += ' AND r.requested_by = ?'
                params.append(requested_by)

            if department:
                query += ' AND r.department = ?'
                params.append(department)

            query += ' ORDER BY r.created_at DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def approve_request(request_id: int, approved_by: str,
                        approved_amount: Optional[float] = None,
                        comments: Optional[str] = None) -> bool:
        """Approve an asset request."""
        with transaction() as conn:
            conn.execute('''
                UPDATE asset_requests
                SET status = 'approved',
                    approved_by = ?,
                    approved_by_name = ?,
                    approved_date = ?,
                    approved_amount = ?,
                    review_comments = ?,
                    updated_at = ?
                WHERE request_id = ? AND status = 'pending'
            ''', (
                approved_by,
                None,  # Could be populated from user lookup
                datetime.now().isoformat(),
                approved_amount,
                comments,
                datetime.now().isoformat(),
                request_id,
            ))

            log_activity('approve', 'asset_request', details={
                'request_id': request_id
            })
            return True

    @staticmethod
    def reject_request(request_id: int, rejected_by: str,
                       reason: str) -> bool:
        """Reject an asset request."""
        with transaction() as conn:
            conn.execute('''
                UPDATE asset_requests
                SET status = 'rejected',
                    reviewed_by = ?,
                    review_date = ?,
                    rejection_reason = ?,
                    updated_at = ?
                WHERE request_id = ? AND status = 'pending'
            ''', (
                rejected_by,
                datetime.now().isoformat(),
                reason,
                datetime.now().isoformat(),
                request_id,
            ))

            log_activity('reject', 'asset_request', details={
                'request_id': request_id
            })
            return True

    # ==================== AUDIT & REPORTING ====================

    @staticmethod
    def get_audit_log(asset_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit log for an asset."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM asset_audit_log
                WHERE asset_id = ?
                ORDER BY action_date DESC
                LIMIT ?
            ''', (asset_id, limit)).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_asset_stats() -> Dict[str, Any]:
        """Get overall asset statistics."""
        with get_connection() as conn:
            stats = {}

            # Total counts by status
            rows = conn.execute('''
                SELECT status, COUNT(*) as count
                FROM assets
                GROUP BY status
            ''').fetchall()
            stats['by_status'] = {row[0]: row[1] for row in rows}

            # Total counts by category
            rows = conn.execute('''
                SELECT c.name, COUNT(*) as count
                FROM assets a
                JOIN asset_categories c ON a.category_id = c.category_id
                GROUP BY c.name
                ORDER BY count DESC
            ''').fetchall()
            stats['by_category'] = {row[0]: row[1] for row in rows}

            # Total value
            row = conn.execute('''
                SELECT SUM(current_value) FROM assets
                WHERE status NOT IN ('disposed', 'lost', 'stolen')
            ''').fetchone()
            stats['total_value'] = row[0] or 0

            # Open issues
            row = conn.execute('''
                SELECT COUNT(*) FROM asset_issues
                WHERE status IN ('open', 'in_progress')
            ''').fetchone()
            stats['open_issues'] = row[0] or 0

            # Upcoming maintenance
            row = conn.execute('''
                SELECT COUNT(*) FROM asset_maintenance
                WHERE status = 'scheduled'
                  AND scheduled_date <= date('now', '+30 days')
            ''').fetchone()
            stats['upcoming_maintenance'] = row[0] or 0

            return stats

    # ==================== HELPER METHODS ====================

    @staticmethod
    def _generate_tag(conn, category_id: int) -> str:
        """Generate a unique asset tag."""
        # Get category prefix
        category = conn.execute('''
            SELECT name FROM asset_categories WHERE category_id = ?
        ''', (category_id,)).fetchone()

        prefix = 'AST'
        if category:
            prefix = category[0][:3].upper()

        year = datetime.now().strftime('%y')

        # Get next sequence number
        result = conn.execute('''
            SELECT COUNT(*) FROM assets WHERE asset_tag LIKE ?
        ''', (f'{prefix}{year}%',)).fetchone()

        seq = (result[0] if result else 0) + 1
        return f'{prefix}{year}{seq:05d}'

    @staticmethod
    def _log_audit(conn, asset_id: int, action: str, action_by: str,
                   old_values: Optional[Dict] = None,
                   new_values: Optional[Dict] = None,
                   notes: Optional[str] = None):
        """Create an audit log entry."""
        conn.execute('''
            INSERT INTO asset_audit_log (
                asset_id, action, action_by, action_date,
                old_values, new_values, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            asset_id,
            action,
            action_by,
            datetime.now().isoformat(),
            json.dumps(old_values) if old_values else None,
            json.dumps(new_values) if new_values else None,
            notes,
        ))
