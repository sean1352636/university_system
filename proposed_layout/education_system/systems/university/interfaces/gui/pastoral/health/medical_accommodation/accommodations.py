# accommodations.py
# Accommodation CRUD mixin for AccommodationGUI.

from education_system.systems.university.interfaces.gui.pastoral.health.medical_accommodation._common import (
    tk, messagebox, simpledialog,
    datetime, sqlite3,
    CLI_AVAILABLE, get_connection,
)

if CLI_AVAILABLE:
    from education_system.systems.university.interfaces.gui.pastoral.health.medical_accommodation._common import (
        validate_student_id, log_action,
        cli_notify_student,
    )

from education_system.systems.university.interfaces.gui.pastoral.health.medical_accommodation.utils import check_conflict
from education_system.systems.university.interfaces.gui.pastoral.health.medical_accommodation.dialogs.accommodation_dialog import AccommodationDialog
from education_system.systems.university.interfaces.gui.pastoral.health.medical_accommodation.dialogs.details_dialog import DetailsDialog


class AccommodationCRUDMixin:
    """CRUD operations for accommodations in AccommodationGUI."""

    def add_accommodation_dialog(self):
        """Show dialog to add new accommodation"""
        if not CLI_AVAILABLE:
            messagebox.showerror("Error", "CLI module not available")
            return

        dialog = AccommodationDialog(self.root, "Add Accommodation")
        if dialog.result:
            try:
                if not validate_student_id(dialog.result['student_id']):
                    messagebox.showerror("Error", "Student ID not found in the system")
                    return

                if check_conflict(
                    dialog.result['student_id'],
                    dialog.result['accommodation_type'],
                    dialog.result['start_date'],
                    dialog.result['end_date']
                ):
                    if not messagebox.askyesno(
                        "Conflict",
                        "This accommodation overlaps with an existing record. Continue anyway?"
                    ):
                        return

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        '''
                        INSERT INTO accommodations
                        (student_id, accommodation_type, description, start_date, end_date, status, notes, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''',
                        (
                            dialog.result['student_id'],
                            dialog.result['accommodation_type'],
                            dialog.result['description'],
                            dialog.result['start_date'] if dialog.result['start_date'] else None,
                            dialog.result['end_date'] if dialog.result['end_date'] else None,
                            'active',
                            dialog.result['notes'],
                            now,
                            now
                        )
                    )

                    aid = cursor.lastrowid
                    conn.commit()
                    messagebox.showinfo("Success", f"Accommodation added successfully with ID: {aid}")

                log_action('add_accommodation', aid, f"Added accommodation for student {dialog.result['student_id']}")

                cli_notify_student(
                    dialog.result['student_id'],
                    'Accommodation Added',
                    f"Your accommodation of type '{dialog.result['accommodation_type']}' has been added."
                )

                self.refresh_data()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add accommodation: {str(e)}")

    def update_accommodation_dialog(self):
        """Show dialog to update selected accommodation"""
        selected = self.get_selected_accommodation()
        if not selected:
            return

        accommodation_id = selected['values'][0]

        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM accommodations WHERE id = ?', (accommodation_id,))
                current_data = cursor.fetchone()

            if not current_data:
                messagebox.showerror("Error", "Accommodation not found")
                return

            dialog = AccommodationDialog(self.root, "Update Accommodation", current_data)
            if dialog.result:
                if (dialog.result['start_date'] != current_data['start_date'] or
                    dialog.result['end_date'] != current_data['end_date'] or
                    dialog.result['accommodation_type'] != current_data['accommodation_type']):

                    if check_conflict(dialog.result['student_id'],
                                    dialog.result['accommodation_type'],
                                    dialog.result['start_date'],
                                    dialog.result['end_date'],
                                    excluded_id=accommodation_id):
                        if not messagebox.askyesno("Conflict",
                            "This update creates a conflict with an existing accommodation. Continue anyway?"):
                            return

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE accommodations SET
                        accommodation_type = ?, description = ?, start_date = ?,
                        end_date = ?, status = ?, notes = ?, updated_at = ?
                        WHERE id = ?
                    ''', (
                        dialog.result['accommodation_type'],
                        dialog.result['description'],
                        dialog.result['start_date'],
                        dialog.result['end_date'],
                        dialog.result['status'],
                        dialog.result['notes'],
                        now,
                        accommodation_id
                    ))
                    conn.commit()

                log_action('update', accommodation_id, f"Updated accommodation for student {dialog.result['student_id']}")

                cli_notify_student(dialog.result['student_id'], 'Accommodation Updated',
                             f"Your {dialog.result['accommodation_type']} accommodation has been updated.")

                messagebox.showinfo("Success", "Accommodation updated successfully")
                self.refresh_data()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update accommodation: {str(e)}")

    def remove_accommodation_dialog(self):
        """Show dialog to remove selected accommodation"""
        selected = self.get_selected_accommodation()
        if not selected:
            return

        accommodation_id = selected['values'][0]
        student_id = selected['values'][1]
        acc_type = selected['values'][3]

        if not messagebox.askyesno("Confirm Removal",
            f"Are you sure you want to remove accommodation ID {accommodation_id} "
            f"({acc_type} for student {student_id})?"):
            return

        reason = simpledialog.askstring("Removal Reason",
            "Please enter a reason for removal (optional):", initialvalue="")

        removal_type = messagebox.askyesnocancel("Removal Type",
            "Yes = Mark as expired, No = Permanently delete, Cancel = Cancel operation")

        if removal_type is None:
            return

        try:
            if removal_type:  # Mark as expired
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                note_text = f"Expired: {reason}" if reason else "Expired"

                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE accommodations SET
                        status = 'expired',
                        notes = CASE WHEN notes IS NULL THEN ? ELSE notes || ' | ' || ? END,
                        updated_at = ?
                        WHERE id = ?
                    ''', (note_text, note_text, now, accommodation_id))
                    conn.commit()

                action_msg = "Accommodation marked as expired"

            else:  # Permanent deletion
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "DELETE FROM documents WHERE source_type = 'accommodation'"
                        " AND reference_id = ? AND reference_type = 'accommodation'",
                        (str(accommodation_id),))
                    # Delete from accommodation_renewals to avoid FK mismatch
                    try:
                        cursor.execute('DELETE FROM accommodation_renewals WHERE accommodation_id = ?', (accommodation_id,))
                    except sqlite3.OperationalError:
                        pass  # Table may not exist
                    cursor.execute('DELETE FROM accommodations WHERE id = ?', (accommodation_id,))
                    conn.commit()

                action_msg = "Accommodation permanently deleted"

            log_action('remove', accommodation_id, f"Removed {acc_type} for student {student_id}. Reason: {reason}")

            cli_notify_student(student_id, 'Accommodation Removed',
                         f"Your {acc_type} accommodation has been removed. Reason: {reason}")

            messagebox.showinfo("Success", action_msg)
            self.refresh_data()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to remove accommodation: {str(e)}")

    def view_accommodation_details(self):
        """Show detailed view of selected accommodation"""
        selected = self.get_selected_accommodation()
        if not selected:
            return

        accommodation_id = selected['values'][0]

        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT a.*, s.first_name, s.last_name, s.email_address
                    FROM accommodations a
                    LEFT JOIN students s ON a.student_id = s.student_id
                    WHERE a.id = ?
                ''', (accommodation_id,))

                accommodation = cursor.fetchone()

                if not accommodation:
                    messagebox.showerror("Error", "Accommodation not found")
                    return

                accommodation = dict(accommodation)

                cursor.execute('''
                    SELECT document_id as id, reference_id as accommodation_id,
                           document_name, file_path as document_path,
                           uploaded_by, upload_date as uploaded_at
                    FROM documents
                    WHERE source_type = 'accommodation' AND reference_id = ?
                      AND reference_type = 'accommodation'
                ''', (str(accommodation_id),))

                documents = [dict(doc) for doc in cursor.fetchall()]

            DetailsDialog(self.root, accommodation, documents)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load accommodation details: {str(e)}")
