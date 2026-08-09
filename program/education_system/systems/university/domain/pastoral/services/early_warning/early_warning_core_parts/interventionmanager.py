"""Extracted class implementation."""

from .. import early_warning_core_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class InterventionManager:
    """Manages interventions and actions"""

    @staticmethod
    def create_intervention(
        student_id: str,
        trigger_type: str,
        intervention_type: str,
        priority: str,
        description: str,
        assigned_to: str = "",
        scheduled_date: str = ""
    ) -> int:
        """Create a new intervention"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO early_warning_interventions (
                    student_id, trigger_type, intervention_type, priority,
                    description, assigned_to, scheduled_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, trigger_type, intervention_type, priority,
                  description, assigned_to, scheduled_date))

            intervention_id = cursor.lastrowid
            conn.commit()

            # Send notification
            InterventionManager._notify_intervention(intervention_id)

            return intervention_id

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error creating intervention: {e}")
        finally:
            conn.close()

    @staticmethod
    def _notify_intervention(intervention_id: int) -> None:
        """Send notification about new intervention"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT i.*, s.first_name, s.last_name, s.email_address
                FROM early_warning_interventions i
                JOIN students s ON i.student_id = s.student_id
                WHERE i.intervention_id = ?
            ''', (intervention_id,))

            intervention = cursor.fetchone()
            if not intervention:
                return

            # Notify assigned staff
            if intervention['assigned_to']:
                scheduled = intervention['scheduled_date'] if intervention['scheduled_date'] else 'Not scheduled'
                subject, body = render_template('intervention_assigned', {
                    'first_name': intervention['first_name'],
                    'last_name': intervention['last_name'],
                    'priority': intervention['priority'],
                    'intervention_type': intervention['intervention_type'],
                    'description': intervention['description'],
                    'scheduled_date': scheduled
                })

                # Fall back to a plain message if the template is unavailable.
                if not subject:
                    subject = (f"[{intervention['priority']}] Intervention assigned: "
                               f"{intervention['first_name']} {intervention['last_name']}")
                if not body:
                    body = (
                        f"An early-warning intervention has been assigned to you.\n\n"
                        f"Student: {intervention['first_name']} {intervention['last_name']} "
                        f"({intervention['student_id']})\n"
                        f"Priority: {intervention['priority']}\n"
                        f"Type: {intervention['intervention_type']}\n"
                        f"Scheduled: {scheduled}\n\n"
                        f"{intervention['description'] or ''}\n"
                    )

                staff_email = _resolve_staff_email(cursor, intervention['assigned_to'])
                if staff_email and HAS_EMAIL:
                    try:
                        send_email(staff_email, subject, body)
                    except Exception as e:  # never let a mail failure break the workflow
                        print(f"Failed to send intervention notification to {staff_email}: {e}")
                else:
                    # No deliverable address / email offline — record rather than silently drop.
                    print(f"Intervention notification (undelivered - no email): {subject}")

        finally:
            conn.close()

    @staticmethod
    def complete_intervention(intervention_id: int, outcome: str, notes: str = "") -> bool:
        """Mark an intervention as completed"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE early_warning_interventions
                SET status = 'completed', completed_date = ?, outcome = ?, notes = ?, updated_at = ?
                WHERE intervention_id = ?
            ''', (date.today().isoformat(), outcome, notes, datetime.now().isoformat(), intervention_id))

            conn.commit()
            return True

        finally:
            conn.close()

    @staticmethod
    def get_pending_interventions(assigned_to: str = "") -> List[Dict[str, Any]]:
        """Get pending interventions"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            query = '''
                SELECT i.*, s.first_name, s.last_name
                FROM early_warning_interventions i
                JOIN students s ON i.student_id = s.student_id
                WHERE i.status = 'pending'
            '''
            params = []

            if assigned_to:
                query += ' AND i.assigned_to = ?'
                params.append(assigned_to)

            query += ' ORDER BY i.priority DESC, i.created_at'

            cursor.execute(query, params)

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()
