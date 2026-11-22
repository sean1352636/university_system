
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.domains.health.interfaces.gui.health._dialogs import make_toplevel
# bulk_operations.py
# Bulk operations dialog for AccommodationGUI.

from education_system.systems.university.domains.health.interfaces.gui.health.medical_accommodation._common import (
    tk, ttk, messagebox, datetime,
    get_connection,
)


class BulkOperationsDialog:
    """Dialog for bulk operations"""

    def __init__(self, parent, gui_parent):
        self.gui_parent = gui_parent

        self.dialog = make_toplevel(parent)
        self.dialog.title(_t('gui.pastoral.health.medical_accommodation.bulk_operations.windows.bulk_operations', default="Bulk Operations"))
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Operation selection
        operation_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.health.medical_accommodation.bulk_operations.labels.select_operation', default="Select Operation"))
        operation_frame.pack(fill=tk.X, pady=10)

        self.operation_var = tk.StringVar(value=_t('gui.pastoral.health.medical_accommodation.bulk_operations.values.update_status', default="update_status"))
        ttk.Radiobutton(operation_frame, text=_t('gui.pastoral.health.medical_accommodation.bulk_operations.buttons.update_status', default="Update Status"),
                       variable=self.operation_var, value="update_status").pack(anchor='w')
        ttk.Radiobutton(operation_frame, text=_t('gui.pastoral.health.medical_accommodation.bulk_operations.buttons.update_type', default="Update Type"),
                       variable=self.operation_var, value="update_type").pack(anchor='w')
        ttk.Radiobutton(operation_frame, text=_t('gui.pastoral.health.medical_accommodation.bulk_operations.buttons.add_notes', default="Add Notes"),
                       variable=self.operation_var, value="add_notes").pack(anchor='w')
        ttk.Radiobutton(operation_frame, text=_t('gui.pastoral.health.medical_accommodation.bulk_operations.buttons.set_end_date', default="Set End Date"),
                       variable=self.operation_var, value="set_end_date").pack(anchor='w')

        # Criteria frame
        criteria_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.health.medical_accommodation.bulk_operations.labels.selection_criteria', default="Selection Criteria"))
        criteria_frame.pack(fill=tk.X, pady=10)

        ttk.Label(criteria_frame, text=_t('gui.pastoral.health.medical_accommodation.bulk_operations.labels.student_id_optional', default="Student ID (optional):")).grid(row=0, column=0, sticky='w')
        self.student_id_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=self.student_id_var, width=20).grid(row=0, column=1, padx=5)

        ttk.Label(criteria_frame, text=_t('gui.pastoral.health.medical_accommodation.bulk_operations.labels.current_status', default="Current Status:")).grid(row=0, column=2, sticky='w', padx=(20,0))
        self.current_status_var = tk.StringVar()
        ttk.Combobox(criteria_frame, textvariable=self.current_status_var,
                    values=['', 'active', 'pending', 'suspended', 'expired']).grid(row=0, column=3, padx=5)

        # Value frame
        value_frame = ttk.LabelFrame(main_frame, text=_t('gui.pastoral.health.medical_accommodation.bulk_operations.labels.new_value', default="New Value"))
        value_frame.pack(fill=tk.X, pady=10)

        ttk.Label(value_frame, text=_t('gui.pastoral.health.medical_accommodation.bulk_operations.labels.value', default="Value:")).pack(anchor='w')
        self.new_value_var = tk.StringVar()
        ttk.Entry(value_frame, textvariable=self.new_value_var, width=50).pack(fill=tk.X, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=20)

        ttk.Button(button_frame, text=_t('gui.pastoral.health.medical_accommodation.bulk_operations.buttons.execute', default="Execute"), command=self.execute).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.pastoral.health.medical_accommodation.bulk_operations.buttons.preview', default="Preview"), command=self.preview).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.pastoral.health.medical_accommodation.bulk_operations.buttons.close', default="Close"), command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def preview(self):
        """Preview which records would be affected"""
        try:
            query, params = self.build_selection_query()

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                results = cursor.fetchall()

            preview_text = f"This operation will affect {len(results)} record(s):\n\n"
            for result in results[:10]:
                preview_text += f"ID: {result[0]}, Student: {result[1]}, Type: {result[2]}\n"

            if len(results) > 10:
                preview_text += f"... and {len(results) - 10} more records"

            messagebox.showinfo(_t('gui.pastoral.health.medical_accommodation.bulk_operations.dialogs.preview', default="Preview"), preview_text)

        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.health.medical_accommodation.bulk_operations.dialogs.error', default="Error"), f"Preview failed: {str(e)}")

    def build_selection_query(self):
        """Build SQL query based on criteria"""
        query = "SELECT id, student_id, accommodation_type FROM accommodations WHERE 1=1"
        params = []

        if self.student_id_var.get().strip():
            query += " AND student_id = ?"
            params.append(self.student_id_var.get().strip())

        if self.current_status_var.get().strip():
            query += " AND status = ?"
            params.append(self.current_status_var.get().strip())

        return query, params

    def execute(self):
        """Execute the bulk operation"""
        if not self.new_value_var.get().strip():
            messagebox.showerror(_t('gui.pastoral.health.medical_accommodation.bulk_operations.dialogs.error', default="Error"), _t('gui.pastoral.health.medical_accommodation.bulk_operations.dialogs.new_value_is_required', default="New value is required"))
            return

        if not messagebox.askyesno(_t('gui.pastoral.health.medical_accommodation.bulk_operations.dialogs.confirm', default="Confirm"), _t('gui.pastoral.health.medical_accommodation.bulk_operations.dialogs.execute_bulk_operation_this_cannot_be_undone', default="Execute bulk operation? This cannot be undone.")):
            return

        try:
            query, params = self.build_selection_query()
            operation = self.operation_var.get()
            new_value = self.new_value_var.get().strip()

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                affected_records = cursor.fetchall()

                if not affected_records:
                    messagebox.showinfo(_t('gui.pastoral.health.medical_accommodation.bulk_operations.dialogs.info', default="Info"), _t('gui.pastoral.health.medical_accommodation.bulk_operations.dialogs.no_records_match_the_criteria', default="No records match the criteria"))
                    return

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                if operation == "update_status":
                    for record_id, _, _ in affected_records:
                        cursor.execute(
                            "UPDATE accommodations SET status = ?, updated_at = ? WHERE id = ?",
                            (new_value, now, record_id)
                        )
                elif operation == "update_type":
                    for record_id, _, _ in affected_records:
                        cursor.execute(
                            "UPDATE accommodations SET accommodation_type = ?, updated_at = ? WHERE id = ?",
                            (new_value, now, record_id)
                        )
                elif operation == "add_notes":
                    for record_id, _, _ in affected_records:
                        cursor.execute(
                            "UPDATE accommodations SET notes = CASE WHEN notes IS NULL THEN ? ELSE notes || ' | ' || ? END, updated_at = ? WHERE id = ?",
                            (new_value, new_value, now, record_id)
                        )
                elif operation == "set_end_date":
                    for record_id, _, _ in affected_records:
                        cursor.execute(
                            "UPDATE accommodations SET end_date = ?, updated_at = ? WHERE id = ?",
                            (new_value, now, record_id)
                        )

                conn.commit()
                # Carry it to exams, assessments and module staff (consent-gated).
                from education_system.systems.university.services.bus import accommodation_bus
                accommodation_bus.after_change()

            messagebox.showinfo(_t('gui.pastoral.health.medical_accommodation.bulk_operations.dialogs.success', default="Success"), f"Updated {len(affected_records)} record(s)")
            self.gui_parent.refresh_data()

        except Exception as e:
            messagebox.showerror(_t('gui.pastoral.health.medical_accommodation.bulk_operations.dialogs.error', default="Error"), f"Bulk operation failed: {str(e)}")
