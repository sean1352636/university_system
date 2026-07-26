"""
Equipment Manager

Handles lab equipment booking, maintenance scheduling,
category management, and usage reporting.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608


class EquipmentManager:
    """Manager for lab equipment booking and maintenance."""

    # ==================== CATEGORY MANAGEMENT ====================

    @staticmethod
    def create_category(name: str, description: Optional[str] = None,
                        parent_category_id: Optional[int] = None) -> int:
        """Create a new equipment category."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO equipment_categories (
                    name, description, parent_category_id
                ) VALUES (?, ?, ?)
            ''', (name, description, parent_category_id))
            category_id = cursor.lastrowid
            log_activity('create', 'equipment_category', details={
                'category_id': category_id, 'name': name,
            })
            return category_id

    @staticmethod
    def get_categories() -> List[Dict[str, Any]]:
        """Get all equipment categories."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM equipment_categories ORDER BY name
            ''').fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_category(category_id: int, **data) -> None:
        """Update an equipment category."""
        if not data:
            return

        fields = []
        values = []
        for key, value in data.items():
            if key not in ('category_id',):
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return

        values.append(category_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE equipment_categories SET ' + ', '.join(fields)
                + ' WHERE category_id = ?',
                values)
            log_activity('update', 'equipment_category', details={
                'category_id': category_id,
                'updated_fields': list(data.keys()),
            })

    # ==================== EQUIPMENT CRUD ====================

    @staticmethod
    def add_equipment(name: str, category_id: Optional[int] = None,
                      location: Optional[str] = None,
                      building: Optional[str] = None,
                      room_number: Optional[str] = None,
                      serial_number: Optional[str] = None,
                      model: Optional[str] = None,
                      manufacturer: Optional[str] = None,
                      max_booking_hours: int = 8,
                      min_booking_hours: int = 1,
                      requires_approval: bool = False,
                      requires_training: bool = False,
                      description: Optional[str] = None) -> int:
        """Add a new piece of equipment."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO equipment (
                    name, category_id, location, building, room_number,
                    serial_number, model, manufacturer,
                    max_booking_hours, min_booking_hours,
                    requires_approval, requires_training,
                    description, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'available', ?)
            ''', (
                name, category_id, location, building, room_number,
                serial_number, model, manufacturer,
                max_booking_hours, min_booking_hours,
                int(requires_approval), int(requires_training),
                description, datetime.now().isoformat(),
            ))
            equipment_id = cursor.lastrowid
            log_activity('create', 'equipment', details={
                'equipment_id': equipment_id, 'name': name,
            })
            return equipment_id

    @staticmethod
    def get_equipment(equipment_id: int) -> Optional[Dict[str, Any]]:
        """Get a single piece of equipment by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM equipment WHERE equipment_id = ?
            ''', (equipment_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_all_equipment(category_id: Optional[int] = None,
                          status: Optional[str] = None,
                          location: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all equipment with optional filters."""
        with get_connection() as conn:
            query = 'SELECT * FROM equipment WHERE 1=1'
            params = []

            if category_id is not None:
                query += ' AND category_id = ?'
                params.append(category_id)

            if status is not None:
                query += ' AND status = ?'
                params.append(status)

            if location is not None:
                query += ' AND location = ?'
                params.append(location)

            query += ' ORDER BY name'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_equipment(equipment_id: int, **data) -> None:
        """Update equipment details."""
        allowed_fields = {
            'name', 'category_id', 'location', 'building', 'room_number',
            'status', 'max_booking_hours', 'min_booking_hours',
            'requires_approval', 'requires_training', 'description',
        }

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
        values.append(equipment_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE equipment SET ' + ', '.join(fields)
                + ' WHERE equipment_id = ?',
                values)
            log_activity('update', 'equipment', details={
                'equipment_id': equipment_id,
                'updated_fields': list(data.keys()),
            })

    # ==================== BOOKING ====================

    @staticmethod
    def create_booking(equipment_id: int, user_id: str,
                       booking_date: str, start_time: str,
                       end_time: str,
                       purpose: Optional[str] = None) -> int:
        """Create an equipment booking. Checks for conflicts first."""
        with transaction() as conn:
            # Check for conflicts
            conflicts = conn.execute('''
                SELECT COUNT(*) as cnt FROM equipment_bookings
                WHERE equipment_id = ? AND booking_date = ?
                AND status NOT IN ('cancelled', 'rejected')
                AND start_time < ? AND end_time > ?
            ''', (equipment_id, booking_date, end_time, start_time)).fetchone()
            if conflicts['cnt'] > 0:
                raise ValueError("Time slot conflicts with an existing booking")

            # Determine initial status based on equipment approval requirement
            equip = conn.execute('''
                SELECT requires_approval FROM equipment WHERE equipment_id = ?
            ''', (equipment_id,)).fetchone()

            status = 'pending' if equip and equip['requires_approval'] else 'approved'

            cursor = conn.execute('''
                INSERT INTO equipment_bookings (
                    equipment_id, user_id, booking_date,
                    start_time, end_time, purpose,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                equipment_id, user_id, booking_date,
                start_time, end_time, purpose,
                status, datetime.now().isoformat(),
            ))
            booking_id = cursor.lastrowid
            log_activity('create', 'equipment_booking', details={
                'booking_id': booking_id, 'equipment_id': equipment_id,
                'user_id': user_id, 'status': status,
            })
            return booking_id

    @staticmethod
    def get_booking(booking_id: int) -> Optional[Dict[str, Any]]:
        """Get a single booking by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM equipment_bookings WHERE booking_id = ?
            ''', (booking_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_user_bookings(user_id: str,
                          status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get bookings for a user, optionally filtered by status."""
        with get_connection() as conn:
            query = '''
                SELECT * FROM equipment_bookings
                WHERE user_id = ?
            '''
            params = [user_id]

            if status is not None:
                query += ' AND status = ?'
                params.append(status)

            query += ' ORDER BY booking_date DESC'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_equipment_bookings(equipment_id: int,
                               date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get bookings for a piece of equipment, optionally filtered by date."""
        with get_connection() as conn:
            query = '''
                SELECT * FROM equipment_bookings
                WHERE equipment_id = ?
            '''
            params = [equipment_id]

            if date is not None:
                query += ' AND booking_date = ?'
                params.append(date)

            query += ' ORDER BY start_time'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def approve_booking(booking_id: int, approved_by: str) -> None:
        """Approve a pending booking."""
        with transaction() as conn:
            conn.execute('''
                UPDATE equipment_bookings
                SET status = 'approved',
                    approved_by = ?,
                    updated_at = ?
                WHERE booking_id = ?
            ''', (approved_by, datetime.now().isoformat(), booking_id))
            log_activity('approve', 'equipment_booking', details={
                'booking_id': booking_id, 'approved_by': approved_by,
            })

    @staticmethod
    def reject_booking(booking_id: int, approved_by: str,
                       notes: Optional[str] = None) -> None:
        """Reject a pending booking."""
        with transaction() as conn:
            conn.execute('''
                UPDATE equipment_bookings
                SET status = 'rejected',
                    approved_by = ?,
                    notes = ?,
                    updated_at = ?
                WHERE booking_id = ?
            ''', (approved_by, notes, datetime.now().isoformat(), booking_id))
            log_activity('reject', 'equipment_booking', details={
                'booking_id': booking_id, 'approved_by': approved_by,
            })

    @staticmethod
    def cancel_booking(booking_id: int) -> None:
        """Cancel a booking."""
        with transaction() as conn:
            conn.execute('''
                UPDATE equipment_bookings
                SET status = 'cancelled',
                    updated_at = ?
                WHERE booking_id = ?
            ''', (datetime.now().isoformat(), booking_id))
            log_activity('cancel', 'equipment_booking', details={
                'booking_id': booking_id,
            })

    @staticmethod
    def check_in(booking_id: int) -> None:
        """Record check-in for a booking."""
        with transaction() as conn:
            conn.execute('''
                UPDATE equipment_bookings
                SET checked_in_at = ?,
                    updated_at = ?
                WHERE booking_id = ?
            ''', (datetime.now().isoformat(), datetime.now().isoformat(),
                  booking_id))
            log_activity('check_in', 'equipment_booking', details={
                'booking_id': booking_id,
            })

    @staticmethod
    def check_out(booking_id: int) -> None:
        """Record check-out for a booking."""
        with transaction() as conn:
            conn.execute('''
                UPDATE equipment_bookings
                SET checked_out_at = ?,
                    updated_at = ?
                WHERE booking_id = ?
            ''', (datetime.now().isoformat(), datetime.now().isoformat(),
                  booking_id))
            log_activity('check_out', 'equipment_booking', details={
                'booking_id': booking_id,
            })

    # ==================== MAINTENANCE ====================

    @staticmethod
    def schedule_maintenance(equipment_id: int,
                             maintenance_type: str = 'routine',
                             description: Optional[str] = None,
                             scheduled_date: Optional[str] = None,
                             cost: float = 0) -> int:
        """Schedule maintenance for equipment. Sets equipment status to maintenance."""
        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO equipment_maintenance (
                    equipment_id, maintenance_type, description,
                    scheduled_date, cost, status, created_at
                ) VALUES (?, ?, ?, ?, ?, 'scheduled', ?)
            ''', (
                equipment_id, maintenance_type, description,
                scheduled_date, cost, datetime.now().isoformat(),
            ))
            maintenance_id = cursor.lastrowid

            # Set equipment status to maintenance
            conn.execute('''
                UPDATE equipment
                SET status = 'maintenance', updated_at = ?
                WHERE equipment_id = ?
            ''', (datetime.now().isoformat(), equipment_id))

            log_activity('create', 'equipment_maintenance', details={
                'maintenance_id': maintenance_id,
                'equipment_id': equipment_id,
                'maintenance_type': maintenance_type,
            })
            return maintenance_id

    @staticmethod
    def complete_maintenance(maintenance_id: int, performed_by: str,
                             next_due_date: Optional[str] = None,
                             notes: Optional[str] = None) -> None:
        """Complete a maintenance record. Restores equipment to available."""
        with transaction() as conn:
            # Get equipment_id from maintenance record
            maint = conn.execute('''
                SELECT equipment_id FROM equipment_maintenance
                WHERE maintenance_id = ?
            ''', (maintenance_id,)).fetchone()

            if not maint:
                raise ValueError(f"Maintenance record {maintenance_id} not found")

            conn.execute('''
                UPDATE equipment_maintenance
                SET status = 'completed',
                    completed_date = ?,
                    performed_by = ?,
                    next_due_date = ?,
                    notes = ?,
                    updated_at = ?
                WHERE maintenance_id = ?
            ''', (
                datetime.now().isoformat(),
                performed_by,
                next_due_date,
                notes,
                datetime.now().isoformat(),
                maintenance_id,
            ))

            # Restore equipment status to available
            conn.execute('''
                UPDATE equipment
                SET status = 'available', updated_at = ?
                WHERE equipment_id = ?
            ''', (datetime.now().isoformat(), maint['equipment_id']))

            log_activity('complete', 'equipment_maintenance', details={
                'maintenance_id': maintenance_id,
                'equipment_id': maint['equipment_id'],
                'performed_by': performed_by,
            })

    @staticmethod
    def get_maintenance_history(equipment_id: int) -> List[Dict[str, Any]]:
        """Get maintenance history for a piece of equipment."""
        with get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM equipment_maintenance
                WHERE equipment_id = ?
                ORDER BY scheduled_date DESC
            ''', (equipment_id,)).fetchall()
            return [dict(row) for row in rows]

    # ==================== REPORTING ====================

    @staticmethod
    def get_usage_statistics(equipment_id: Optional[int] = None,
                             start_date: Optional[str] = None,
                             end_date: Optional[str] = None) -> Dict[str, Any]:
        """Get usage statistics for equipment bookings."""
        with get_connection() as conn:
            where_clause = '1=1'
            params: list = []

            if equipment_id is not None:
                where_clause += ' AND equipment_id = ?'
                params.append(equipment_id)

            if start_date is not None:
                where_clause += ' AND booking_date >= ?'
                params.append(start_date)

            if end_date is not None:
                where_clause += ' AND booking_date <= ?'
                params.append(end_date)

            # Total bookings
            row = conn.execute(
                'SELECT COUNT(*) as total_bookings'
                ' FROM equipment_bookings WHERE ' + where_clause,
                params).fetchone()

            stats: Dict[str, Any] = {
                'total_bookings': row['total_bookings'] or 0,
            }

            # By status
            rows = conn.execute(
                'SELECT status, COUNT(*) as count'
                ' FROM equipment_bookings WHERE ' + where_clause
                + ' GROUP BY status',
                params).fetchall()
            stats['by_status'] = {r['status']: r['count'] for r in rows}

            # Utilization data: bookings per equipment
            rows = conn.execute(
                'SELECT eb.equipment_id, e.name,'
                ' COUNT(*) as booking_count'
                ' FROM equipment_bookings eb'
                ' JOIN lab_equipment e ON eb.equipment_id = e.equipment_id'
                ' WHERE ' + where_clause.replace('equipment_id', 'eb.equipment_id').replace('booking_date', 'eb.booking_date')
                + ' GROUP BY eb.equipment_id, e.name'
                ' ORDER BY booking_count DESC',
                params).fetchall()
            stats['utilization'] = [
                {
                    'equipment_id': r['equipment_id'],
                    'name': r['name'],
                    'booking_count': r['booking_count'],
                }
                for r in rows
            ]

            return stats
