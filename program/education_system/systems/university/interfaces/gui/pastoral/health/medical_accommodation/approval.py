# approval.py
# Approval workflow mixin and ApprovalDialog for AccommodationGUI.

from education_system.systems.university.interfaces.gui.pastoral.health.medical_accommodation._common import (
    tk, ttk, messagebox, simpledialog,
    datetime, sqlite3,
    CLI_AVAILABLE, get_connection, logger,
)

if CLI_AVAILABLE:
    from education_system.systems.university.interfaces.gui.pastoral.health.medical_accommodation._common import log_action, cli_notify_student

from education_system.systems.university.interfaces.gui.pastoral.health.medical_accommodation.utils import resolve_user_identifier


class ApprovalMixin:
    """Approval workflow methods for AccommodationGUI."""

    def approve_selected(self):
        """Approve selected accommodation"""
        self.process_approval('approve')

    def reject_selected(self):
        """Reject selected accommodation"""
        self.process_approval('reject')

    def process_approval(self, action):
        """Process approval or rejection"""
        selected = self.get_selected_accommodation()
        if not selected:
            return

        accommodation_id = selected['values'][0]
        status = selected['values'][6]

        if status != 'pending':
            messagebox.showwarning("Invalid Status",
                "Only pending accommodations can be approved or rejected")
            return

        # Ask for reason
        reason = simpledialog.askstring(f"{action.title()} Reason",
            f"Enter reason for {action} (optional):", initialvalue="")

        try:
            # Get student info
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT student_id, accommodation_type FROM accommodations WHERE id = ?',
                             (accommodation_id,))
                acc_info = cursor.fetchone()
                student_id, acc_type = acc_info

                # Update status
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                user = resolve_user_identifier(auth_instance=self.auth)

                new_status = 'active' if action == 'approve' else 'rejected'
                note_text = f"{action.title()}: {reason}" if reason else f"{action.title()}"

                cursor.execute('''
                    UPDATE accommodations SET
                    status = ?,
                    approved_by = ?,
                    approval_date = ?,
                    notes = CASE WHEN notes IS NULL THEN ? ELSE notes || ' | ' || ? END,
                    updated_at = ?
                    WHERE id = ?
                ''', (new_status, user, now, note_text, note_text, now, accommodation_id))

                conn.commit()

            # Log action
            log_action(action, accommodation_id, f"{action.title()} accommodation for {student_id}: {reason}")

            # Notify student
            message = f"Your {acc_type} accommodation has been {action}d."
            if reason:
                message += f" {action.title()} reason: {reason}"

            cli_notify_student(student_id, f'Accommodation {action.title()}d', message)

            messagebox.showinfo("Success", f"Accommodation {action}d successfully")
            self.refresh_data()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to {action} accommodation: {str(e)}")

    def approve_accommodation_dialog(self):
        """Show approval management dialog"""
        ApprovalDialog(self.root, self)


class ApprovalDialog:
    """Dialog for approval management"""

    def __init__(self, parent, gui_parent):
        self.gui_parent = gui_parent

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Approval Management")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)

        self.create_widgets()
        self.load_pending_approvals()

    def create_widgets(self):
        """Create approval widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        ttk.Label(main_frame, text="Pending Accommodations", font=('Arial', 12, 'bold')).pack(pady=10)

        # Approval tree
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.approval_tree = ttk.Treeview(tree_frame, columns=(
            'ID', 'Student ID', 'Name', 'Type', 'Start Date', 'End Date', 'Description'
        ), show='headings')

        columns = {
            'ID': 50,
            'Student ID': 100,
            'Name': 120,
            'Type': 150,
            'Start Date': 100,
            'End Date': 100,
            'Description': 200
        }

        for col, width in columns.items():
            self.approval_tree.heading(col, text=col)
            self.approval_tree.column(col, width=width, minwidth=50)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.approval_tree.yview)
        self.approval_tree.configure(yscrollcommand=scrollbar.set)

        self.approval_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Approve", command=self.approve_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Reject", command=self.reject_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Request Info", command=self.request_info).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.load_pending_approvals).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def load_pending_approvals(self):
        """Load pending approvals"""
        if not CLI_AVAILABLE:
            return

        # Clear existing items
        for item in self.approval_tree.get_children():
            self.approval_tree.delete(item)

        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT a.id, a.student_id, a.accommodation_type, a.description,
                           a.start_date, a.end_date, s.first_name, s.last_name
                    FROM accommodations a
                    JOIN students s ON a.student_id = s.student_id
                    WHERE a.status = 'pending'
                    ORDER BY a.created_at DESC
                ''')

                pending = cursor.fetchall()

                for acc in pending:
                    student_name = f"{acc['first_name'] or ''} {acc['last_name'] or ''}".strip() or 'N/A'

                    self.approval_tree.insert('', 'end', values=(
                        acc['id'],
                        acc['student_id'],
                        student_name,
                        acc['accommodation_type'],
                        acc['start_date'] or 'N/A',
                        acc['end_date'] or 'N/A',
                        acc['description'] or 'N/A'
                    ))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load pending approvals: {str(e)}")

    def get_selected_approval(self):
        """Get selected approval"""
        selection = self.approval_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an accommodation to process")
            return None
        return self.approval_tree.item(selection[0])

    def approve_selected(self):
        """Approve selected accommodation"""
        self.process_approval_action('approve')

    def reject_selected(self):
        """Reject selected accommodation"""
        self.process_approval_action('reject')

    def request_info(self):
        """Request more information"""
        self.process_approval_action('request_info')

    def process_approval_action(self, action):
        """Process approval action"""
        selected = self.get_selected_approval()
        if not selected:
            return

        accommodation_id = selected['values'][0]
        student_id = selected['values'][1]
        acc_type = selected['values'][3]

        # Get reason/comments
        reason = simpledialog.askstring(f"{action.replace('_', ' ').title()}",
            "Enter reason or comments (optional):", initialvalue="")

        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            user = resolve_user_identifier(auth_instance=getattr(self.gui_parent, 'auth', None))

            with get_connection() as conn:
                cursor = conn.cursor()

                if action == 'approve':
                    new_status = 'active'
                    note_text = f"Approved: {reason}" if reason else "Approved"
                    message = f"Your {acc_type} accommodation has been approved."

                elif action == 'reject':
                    new_status = 'rejected'
                    note_text = f"Rejected: {reason}" if reason else "Rejected"
                    message = f"Your {acc_type} accommodation has been rejected."

                else:  # request_info
                    new_status = 'pending'  # Keep as pending
                    note_text = f"More info requested: {reason}" if reason else "More info requested"
                    message = f"More information is required for your {acc_type} accommodation."

                if reason:
                    message += f" Comments: {reason}"

                cursor.execute('''
                    UPDATE accommodations SET
                    status = ?,
                    approved_by = ?,
                    approval_date = ?,
                    notes = CASE WHEN notes IS NULL THEN ? ELSE notes || ' | ' || ? END,
                    updated_at = ?
                    WHERE id = ?
                ''', (new_status, user, now, note_text, note_text, now, accommodation_id))

                conn.commit()

            # Log action
            log_action(action, accommodation_id, f"{action} accommodation for {student_id}: {reason}")

            # Notify student using template system
            try:
                from education_system.systems.university.infrastructure.email.template_utils import render_template
                template_subject, template_message = render_template("accommodation_notification", {
                    "action_type": action.replace('_', ' ').title(),
                    "accommodation_type": acc_type,
                    "status": new_status,
                    "reason": reason if reason else "",
                    "message": message
                })

                if template_subject and template_message:
                    cli_notify_student(student_id, template_subject, template_message)
                else:
                    subject = f"Accommodation {action.replace('_', ' ').title()}"
                    cli_notify_student(student_id, subject, message)
            except Exception:
                subject = f"Accommodation {action.replace('_', ' ').title()}"
                cli_notify_student(student_id, subject, message)

            messagebox.showinfo("Success", f"Accommodation {action}d successfully")
            self.load_pending_approvals()
            self.gui_parent.refresh_data()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to {action} accommodation: {str(e)}")
