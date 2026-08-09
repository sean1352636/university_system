"""Extracted class implementation."""

from .. import early_warning_core_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class IndicatorManager:
    """Manages risk indicators and flags"""

    @staticmethod
    def add_indicator(
        student_id: str,
        indicator_type: str,
        indicator_value: str,
        severity: str,
        notes: str = ""
    ) -> int:
        """Add a risk indicator for a student"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO early_warning_indicators (
                    student_id, indicator_type, indicator_value, severity, notes
                )
                VALUES (?, ?, ?, ?, ?)
            ''', (student_id, indicator_type, indicator_value, severity, notes))

            indicator_id = cursor.lastrowid
            conn.commit()

            # Trigger intervention if high severity
            if severity in ['high', 'critical']:
                InterventionManager.create_intervention(
                    student_id,
                    indicator_type,
                    f"auto_{indicator_type}",
                    severity,
                    f"Automated intervention triggered by {indicator_type} indicator"
                )

            return indicator_id

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error adding indicator: {e}")
        finally:
            conn.close()

    @staticmethod
    def resolve_indicator(indicator_id: int, notes: str = "") -> bool:
        """Mark an indicator as resolved"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE early_warning_indicators
                SET is_resolved = 1, resolved_at = ?, notes = ?
                WHERE indicator_id = ?
            ''', (datetime.now().isoformat(), notes, indicator_id))

            conn.commit()
            return True

        finally:
            conn.close()

    @staticmethod
    def get_active_indicators(student_id: str) -> List[Dict[str, Any]]:
        """Get active indicators for a student"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT * FROM early_warning_indicators
                WHERE student_id = ? AND is_resolved = 0
                ORDER BY detected_at DESC
            ''', (student_id,))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()
