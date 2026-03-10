"""
Disbursement management mixin for AdminPortal.
"""

from ._imports import (
    tk, ttk, logging, datetime, date,
    get_connection, transaction, log_activity,
    get_current_user, confirm_action,
    clear_frame, create_stat_card,
    format_currency, format_date,
    show_error, show_success, show_warning,
    export_to_csv,
    get_text,
)

logger = logging.getLogger(__name__)


class DisbursementsMixin:
    """Methods for managing disbursements."""

    def show_disbursements(self):
        """Show comprehensive disbursements management interface"""
        # Ensure we have a valid parent frame/window
        parent = self._ensure_valid_parent()
        self.parent_frame = parent

        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text=get_text("financial_aid.admin_portal.disbursements.title", "Disbursement Management"), style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text=get_text("financial_aid.admin_portal.buttons.back_to_dashboard", "Back to Dashboard"), command=self.show_dashboard).pack(side='right')

        # Stats summary
        stats_frame = ttk.Frame(self.parent_frame)
        stats_frame.pack(fill='x', padx=10, pady=10)

        try:
            with get_connection() as conn:
                # Get disbursement statistics
                pending_result = conn.execute("""
                    SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total
                    FROM disbursements WHERE status = 'pending'
                """).fetchone()

                processed_result = conn.execute("""
                    SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total
                    FROM disbursements WHERE status = 'processed'
                    AND DATE(processed_at) = DATE('now')
                """).fetchone()

                # Display stats
                stat_frame1 = create_stat_card(stats_frame, get_text("financial_aid.admin_portal.stats.pending_disbursements", "Pending Disbursements"),
                                               f"{pending_result['count']}", 'warning')
                stat_frame1.pack(side='left', padx=10, fill='both', expand=True)

                stat_frame2 = create_stat_card(stats_frame, get_text("financial_aid.admin_portal.stats.pending_amount", "Pending Amount"),
                                               format_currency(pending_result['total']), 'warning')
                stat_frame2.pack(side='left', padx=10, fill='both', expand=True)

                stat_frame3 = create_stat_card(stats_frame, get_text("financial_aid.admin_portal.stats.processed_today", "Processed Today"),
                                               f"{processed_result['count']}", 'success')
                stat_frame3.pack(side='left', padx=10, fill='both', expand=True)

                stat_frame4 = create_stat_card(stats_frame, get_text("financial_aid.admin_portal.stats.amount_processed_today", "Amount Processed Today"),
                                               format_currency(processed_result['total']), 'success')
                stat_frame4.pack(side='left', padx=10, fill='both', expand=True)

        except Exception as e:
            logger.error(f"Error loading disbursement stats: {e}")

        # Action buttons
        action_frame = ttk.Frame(self.parent_frame)
        action_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(action_frame, text=get_text("financial_aid.admin_portal.buttons.create_disbursement", "Create Disbursement"),
                  command=self._show_create_disbursement_dialog,
                  style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(action_frame, text=get_text("financial_aid.admin_portal.buttons.process_selected", "Process Selected"),
                  command=lambda: self._process_selected_disbursements(tree),
                  style='Primary.TButton').pack(side='left', padx=5)
        ttk.Button(action_frame, text=get_text("financial_aid.admin_portal.buttons.process_all_pending", "Process All Pending"),
                  command=self._process_all_pending_disbursements,
                  style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(action_frame, text=get_text("financial_aid.admin_portal.buttons.cancel_selected", "Cancel Selected"),
                  command=lambda: self._cancel_selected_disbursements(tree),
                  style='Danger.TButton').pack(side='left', padx=5)
        ttk.Button(action_frame, text=get_text("financial_aid.admin_portal.buttons.view_details", "View Details"),
                  command=lambda: self._view_disbursement_details(tree)).pack(side='left', padx=5)
        ttk.Button(action_frame, text=get_text("financial_aid.admin_portal.buttons.export_report", "Export Report"),
                  command=self._export_disbursement_report).pack(side='left', padx=5)

        # Tabs for different views
        notebook = ttk.Notebook(self.parent_frame)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Pending disbursements tab
        pending_frame = ttk.Frame(notebook)
        notebook.add(pending_frame, text=get_text("financial_aid.admin_portal.tabs.pending_disbursements", "Pending Disbursements"))

        columns_pending = [get_text("financial_aid.admin_portal.columns.select", "Select"), get_text("financial_aid.admin_portal.columns.id", "ID"), get_text("financial_aid.admin_portal.columns.student_name", "Student Name"), get_text("financial_aid.admin_portal.columns.student_id", "Student ID"), get_text("financial_aid.admin_portal.columns.type", "Type"), get_text("financial_aid.admin_portal.columns.amount", "Amount"),
                          get_text("financial_aid.admin_portal.columns.scheduled_date", "Scheduled Date"), get_text("financial_aid.admin_portal.columns.term", "Term"), get_text("financial_aid.admin_portal.columns.method", "Method"), get_text("financial_aid.admin_portal.columns.transaction_id", "Transaction ID")]
        tree = ttk.Treeview(pending_frame, columns=columns_pending, show='tree headings', height=15)

        # Configure columns
        tree.column('#0', width=0, stretch=False)
        tree.column(get_text("financial_aid.admin_portal.columns.select", "Select"), width=50, anchor='center')
        tree.column(get_text("financial_aid.admin_portal.columns.id", "ID"), width=60)
        tree.column(get_text("financial_aid.admin_portal.columns.student_name", "Student Name"), width=150)
        tree.column(get_text("financial_aid.admin_portal.columns.student_id", "Student ID"), width=100)
        tree.column(get_text("financial_aid.admin_portal.columns.type", "Type"), width=120)
        tree.column(get_text("financial_aid.admin_portal.columns.amount", "Amount"), width=100, anchor='e')
        tree.column(get_text("financial_aid.admin_portal.columns.scheduled_date", "Scheduled Date"), width=120)
        tree.column(get_text("financial_aid.admin_portal.columns.term", "Term"), width=100)
        tree.column(get_text("financial_aid.admin_portal.columns.method", "Method"), width=120)
        tree.column(get_text("financial_aid.admin_portal.columns.transaction_id", "Transaction ID"), width=150)

        for col in columns_pending:
            tree.heading(col, text=col)

        # Scrollbars
        vsb = ttk.Scrollbar(pending_frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(pending_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        pending_frame.grid_rowconfigure(0, weight=1)
        pending_frame.grid_columnconfigure(0, weight=1)

        # Bind click event for checkbox toggle
        tree.bind('<Button-1>', lambda e: self._toggle_selection(tree, e))

        # Load pending disbursements
        self._load_pending_disbursements(tree)

        # Processed disbursements tab
        processed_frame = ttk.Frame(notebook)
        notebook.add(processed_frame, text=get_text("financial_aid.admin_portal.tabs.processed_disbursements", "Processed Disbursements"))

        columns_processed = [get_text("financial_aid.admin_portal.columns.id", "ID"), get_text("financial_aid.admin_portal.columns.student_name", "Student Name"), get_text("financial_aid.admin_portal.columns.student_id", "Student ID"), get_text("financial_aid.admin_portal.columns.type", "Type"), get_text("financial_aid.admin_portal.columns.amount", "Amount"),
                            get_text("financial_aid.admin_portal.columns.disbursement_date", "Disbursement Date"), get_text("financial_aid.admin_portal.columns.processed_date", "Processed Date"), get_text("financial_aid.admin_portal.columns.processed_by", "Processed By"), get_text("financial_aid.admin_portal.columns.transaction_id", "Transaction ID")]
        processed_tree = ttk.Treeview(processed_frame, columns=columns_processed, show='headings', height=15)

        for col in columns_processed:
            processed_tree.heading(col, text=col)
            processed_tree.column(col, width=100)

        vsb2 = ttk.Scrollbar(processed_frame, orient="vertical", command=processed_tree.yview)
        hsb2 = ttk.Scrollbar(processed_frame, orient="horizontal", command=processed_tree.xview)
        processed_tree.configure(yscrollcommand=vsb2.set, xscrollcommand=hsb2.set)

        processed_tree.grid(row=0, column=0, sticky='nsew')
        vsb2.grid(row=0, column=1, sticky='ns')
        hsb2.grid(row=1, column=0, sticky='ew')

        processed_frame.grid_rowconfigure(0, weight=1)
        processed_frame.grid_columnconfigure(0, weight=1)

        # Load processed disbursements
        self._load_processed_disbursements(processed_tree)

        # Failed/cancelled disbursements tab
        failed_frame = ttk.Frame(notebook)
        notebook.add(failed_frame, text=get_text("financial_aid.admin_portal.tabs.failed_cancelled", "Failed/Cancelled"))

        columns_failed = [get_text("financial_aid.admin_portal.columns.id", "ID"), get_text("financial_aid.admin_portal.columns.student", "Student"), get_text("financial_aid.admin_portal.columns.amount", "Amount"), get_text("financial_aid.admin_portal.columns.scheduled_date", "Scheduled Date"), get_text("financial_aid.admin_portal.columns.status", "Status"), get_text("financial_aid.admin_portal.columns.error_message", "Error Message")]
        failed_tree = ttk.Treeview(failed_frame, columns=columns_failed, show='headings', height=15)

        for col in columns_failed:
            failed_tree.heading(col, text=col)
            failed_tree.column(col, width=120)

        vsb3 = ttk.Scrollbar(failed_frame, orient="vertical", command=failed_tree.yview)
        failed_tree.configure(yscrollcommand=vsb3.set)

        failed_tree.grid(row=0, column=0, sticky='nsew')
        vsb3.grid(row=0, column=1, sticky='ns')

        failed_frame.grid_rowconfigure(0, weight=1)
        failed_frame.grid_columnconfigure(0, weight=1)

        # Load failed/cancelled disbursements
        self._load_failed_disbursements(failed_tree)

    def _load_pending_disbursements(self, tree):
        """Load pending disbursements into tree"""
        try:
            # Clear existing items
            for item in tree.get_children():
                tree.delete(item)

            with get_connection() as conn:
                disbursements = conn.execute("""
                    SELECT d.*, s.first_name, s.last_name, s.student_id as sid
                    FROM disbursements d
                    LEFT JOIN students s ON d.student_id = s.student_id
                    WHERE d.status = 'pending'
                    ORDER BY d.scheduled_date ASC
                """).fetchall()

                for disb in disbursements:
                    # Convert Row to dict
                    d = dict(disb)
                    student_name = f"{d.get('first_name', 'N/A')} {d.get('last_name', '')}"
                    tree.insert('', 'end', values=(
                        '\u2610',  # Checkbox
                        d['disbursement_id'],
                        student_name,
                        d.get('sid', d['student_id']),
                        d.get('disbursement_type', get_text("financial_aid.admin_portal.values.general_aid", "General Aid")),
                        format_currency(d['amount']),
                        format_date(d.get('scheduled_date', d.get('disbursement_date'))),
                        d.get('academic_term', 'N/A'),
                        d.get('payment_method', 'account_credit'),
                        d.get('transaction_id', get_text("financial_aid.admin_portal.values.pending", "Pending"))
                    ))

        except Exception as e:
            logger.error(f"Error loading pending disbursements: {e}")

    def _load_processed_disbursements(self, tree):
        """Load processed disbursements into tree"""
        try:
            # Clear existing items
            for item in tree.get_children():
                tree.delete(item)

            with get_connection() as conn:
                disbursements = conn.execute("""
                    SELECT d.*, s.first_name, s.last_name, s.student_id as sid,
                           u.username as processor_name
                    FROM disbursements d
                    LEFT JOIN students s ON d.student_id = s.student_id
                    LEFT JOIN users u ON d.processed_by = u.id
                    WHERE d.status = 'processed'
                    ORDER BY d.processed_at DESC
                    LIMIT 100
                """).fetchall()

                for disb in disbursements:
                    # Convert Row to dict
                    d = dict(disb)
                    student_name = f"{d.get('first_name', 'N/A')} {d.get('last_name', '')}"
                    tree.insert('', 'end', values=(
                        d['disbursement_id'],
                        student_name,
                        d.get('sid', d['student_id']),
                        d.get('disbursement_type', get_text("financial_aid.admin_portal.values.general_aid", "General Aid")),
                        format_currency(d['amount']),
                        format_date(d.get('disbursement_date')),
                        format_date(d.get('processed_at')),
                        d.get('processor_name', get_text("financial_aid.admin_portal.values.system", "System")),
                        d.get('transaction_id', 'N/A')
                    ))

        except Exception as e:
            logger.error(f"Error loading processed disbursements: {e}")

    def _load_failed_disbursements(self, tree):
        """Load failed/cancelled disbursements into tree"""
        try:
            # Clear existing items
            for item in tree.get_children():
                tree.delete(item)

            with get_connection() as conn:
                disbursements = conn.execute("""
                    SELECT d.*, s.first_name, s.last_name
                    FROM disbursements d
                    LEFT JOIN students s ON d.student_id = s.student_id
                    WHERE d.status IN ('failed', 'cancelled')
                    ORDER BY d.scheduled_date DESC
                    LIMIT 100
                """).fetchall()

                for disb in disbursements:
                    # Convert Row to dict
                    d = dict(disb)
                    student_name = f"{d.get('first_name', 'N/A')} {d.get('last_name', '')}"
                    tree.insert('', 'end', values=(
                        d['disbursement_id'],
                        student_name,
                        format_currency(d['amount']),
                        format_date(d.get('scheduled_date')),
                        d['status'].upper(),
                        d.get('error_message', get_text("financial_aid.admin_portal.values.no_error_message", "No error message"))
                    ))

        except Exception as e:
            logger.error(f"Error loading failed disbursements: {e}")

    def _process_selected_disbursements(self, tree):
        """Process selected disbursements"""
        selected_items = []
        for item in tree.get_children():
            values = tree.item(item)['values']
            if values[0] == '\u2611':  # Checked
                selected_items.append(values[1])  # disbursement_id

        if not selected_items:
            show_warning(get_text("financial_aid.admin_portal.dialogs.no_selection", "No Selection"), get_text("financial_aid.admin_portal.messages.select_disbursements_to_process", "Please select disbursements to process by clicking the checkbox column."))
            return

        if not confirm_action(get_text("financial_aid.admin_portal.messages.confirm_process_disbursements", "Process {count} selected disbursement(s)?\n\nThis action cannot be undone.").format(count=len(selected_items))):
            return

        success_count = 0
        error_count = 0

        try:
            auth_user = get_current_user()
            user_id = None
            if auth_user:
                user_dict = auth_user.to_dict() if hasattr(auth_user, 'to_dict') else auth_user.__dict__ if hasattr(auth_user, '__dict__') else auth_user
                user_id = user_dict.get('id', user_dict.get('user_id', 1))

            for disb_id in selected_items:
                success = self.aid_manager.process_disbursement(
                    disbursement_id=disb_id,
                    processed_by=user_id,
                    transaction_id=f"TXN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{disb_id}"
                )
                if success:
                    success_count += 1
                    log_activity('process', 'disbursement', disb_id, {'processed_by': user_id})
                else:
                    error_count += 1

            # Refresh the table
            self._load_pending_disbursements(tree)

            show_success(get_text("financial_aid.admin_portal.dialogs.processing_complete", "Processing Complete"),
                        get_text("financial_aid.admin_portal.messages.processing_results", "Successfully processed: {success}\nFailed: {failed}").format(success=success_count, failed=error_count))

        except Exception as e:
            logger.error(f"Error processing disbursements: {e}")
            show_error(get_text("financial_aid.admin_portal.dialogs.processing_error", "Processing Error"), get_text("financial_aid.admin_portal.errors.error_occurred", "An error occurred: {error}").format(error=str(e)))

    def _process_all_pending_disbursements(self):
        """Process all pending disbursements"""
        try:
            with get_connection() as conn:
                pending_count = conn.execute("""
                    SELECT COUNT(*) as count FROM disbursements WHERE status = 'pending'
                """).fetchone()['count']

                if pending_count == 0:
                    show_warning(get_text("financial_aid.admin_portal.dialogs.no_pending", "No Pending Disbursements"), get_text("financial_aid.admin_portal.messages.no_pending_disbursements", "There are no pending disbursements to process."))
                    return

                if not confirm_action(get_text("financial_aid.admin_portal.messages.confirm_process_all", "Process ALL {count} pending disbursement(s)?\n\nThis will process every pending disbursement in the system.\nThis action cannot be undone.").format(count=pending_count)):
                    return

                auth_user = get_current_user()
                user_id = None
                if auth_user:
                    user_dict = auth_user.to_dict() if hasattr(auth_user, 'to_dict') else auth_user.__dict__ if hasattr(auth_user, '__dict__') else auth_user
                    user_id = user_dict.get('id', user_dict.get('user_id', 1))

                # Get all pending disbursements
                pending = conn.execute("""
                    SELECT disbursement_id FROM disbursements WHERE status = 'pending'
                """).fetchall()

                success_count = 0
                for row in pending:
                    success = self.aid_manager.process_disbursement(
                        disbursement_id=row['disbursement_id'],
                        processed_by=user_id,
                        transaction_id=f"TXN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{row['disbursement_id']}"
                    )
                    if success:
                        success_count += 1
                        log_activity('process', 'disbursement', row['disbursement_id'], {'batch': True})

                show_success(get_text("financial_aid.admin_portal.dialogs.batch_processing_complete", "Batch Processing Complete"),
                            get_text("financial_aid.admin_portal.messages.batch_processing_results", "Successfully processed {success} out of {total} disbursements.").format(success=success_count, total=pending_count))

                # Refresh the view
                self.show_disbursements()

        except Exception as e:
            logger.error(f"Error in batch processing: {e}")
            show_error(get_text("financial_aid.admin_portal.dialogs.batch_processing_error", "Batch Processing Error"), get_text("financial_aid.admin_portal.errors.error_occurred", "An error occurred: {error}").format(error=str(e)))

    def _cancel_selected_disbursements(self, tree):
        """Cancel selected disbursements"""
        selected_items = []
        for item in tree.get_children():
            values = tree.item(item)['values']
            if values[0] == '\u2611':  # Checked
                selected_items.append(values[1])  # disbursement_id

        if not selected_items:
            show_warning(get_text("financial_aid.admin_portal.dialogs.no_selection", "No Selection"), get_text("financial_aid.admin_portal.messages.select_disbursements_to_cancel", "Please select disbursements to cancel."))
            return

        if not confirm_action(get_text("financial_aid.admin_portal.messages.confirm_cancel_disbursements", "Cancel {count} selected disbursement(s)?").format(count=len(selected_items))):
            return

        try:
            with transaction() as conn:
                for disb_id in selected_items:
                    conn.execute("""
                        UPDATE disbursements
                        SET status = 'cancelled', error_message = 'Cancelled by administrator'
                        WHERE disbursement_id = ?
                    """, (disb_id,))
                    log_activity('cancel', 'disbursement', disb_id, {'reason': 'admin_action'})

            show_success(get_text("financial_aid.admin_portal.dialogs.cancellation_complete", "Cancellation Complete"), get_text("financial_aid.admin_portal.messages.cancellation_results", "Successfully cancelled {count} disbursement(s).").format(count=len(selected_items)))
            self._load_pending_disbursements(tree)

        except Exception as e:
            logger.error(f"Error cancelling disbursements: {e}")
            show_error(get_text("financial_aid.admin_portal.dialogs.cancellation_error", "Cancellation Error"), get_text("financial_aid.admin_portal.errors.error_occurred", "An error occurred: {error}").format(error=str(e)))

    def _view_disbursement_details(self, tree):
        """View detailed information about selected disbursement"""
        selection = tree.selection()
        if not selection:
            show_warning(get_text("financial_aid.admin_portal.dialogs.no_selection", "No Selection"), get_text("financial_aid.admin_portal.messages.select_disbursement_to_view", "Please select a disbursement to view details."))
            return

        values = tree.item(selection[0])['values']
        disb_id = values[1]  # disbursement_id

        try:
            with get_connection() as conn:
                disb = conn.execute("""
                    SELECT d.*, s.first_name, s.last_name, s.email, s.student_id as sid,
                           u.username as processor_name
                    FROM disbursements d
                    LEFT JOIN students s ON d.student_id = s.student_id
                    LEFT JOIN users u ON d.processed_by = u.id
                    WHERE d.disbursement_id = ?
                """, (disb_id,)).fetchone()

                if not disb:
                    show_error(get_text("financial_aid.admin_portal.dialogs.not_found", "Not Found"), get_text("financial_aid.admin_portal.errors.disbursement_not_found", "Disbursement not found."))
                    return

                # Convert Row to dict
                d = dict(disb)

                # Create details window
                details_window = tk.Toplevel(self.parent_frame)
                details_window.title(get_text("financial_aid.admin_portal.dialogs.disbursement_details", "Disbursement Details") + f" - ID: {disb_id}")
                details_window.geometry("600x700")

                # Title
                ttk.Label(details_window, text=get_text("financial_aid.admin_portal.details.disbursement_num", "Disbursement #{num}").format(num=disb_id), font=('Arial', 14, 'bold')).pack(pady=10)

                # Details frame
                details_frame = ttk.Frame(details_window, padding=20)
                details_frame.pack(fill='both', expand=True)

                def add_detail(label, value):
                    row_frame = ttk.Frame(details_frame)
                    row_frame.pack(fill='x', pady=5)
                    ttk.Label(row_frame, text=f"{label}:", font=('Arial', 10, 'bold'), width=20).pack(side='left')
                    ttk.Label(row_frame, text=str(value), font=('Arial', 10)).pack(side='left')

                add_detail(get_text("financial_aid.admin_portal.details.status", "Status"), d['status'].upper())
                add_detail(get_text("financial_aid.admin_portal.details.student_name", "Student Name"), f"{d.get('first_name', 'N/A')} {d.get('last_name', '')}")
                add_detail(get_text("financial_aid.admin_portal.details.student_id", "Student ID"), d.get('sid', d['student_id']))
                add_detail(get_text("financial_aid.admin_portal.details.student_email", "Student Email"), d.get('email', 'N/A'))
                add_detail(get_text("financial_aid.admin_portal.details.disbursement_type", "Disbursement Type"), d.get('disbursement_type', get_text("financial_aid.admin_portal.values.general_aid", "General Aid")))
                add_detail(get_text("financial_aid.admin_portal.details.amount", "Amount"), format_currency(d['amount']))
                add_detail(get_text("financial_aid.admin_portal.details.academic_term", "Academic Term"), d.get('academic_term', 'N/A'))
                add_detail(get_text("financial_aid.admin_portal.details.payment_method", "Payment Method"), d.get('payment_method', 'N/A'))
                add_detail(get_text("financial_aid.admin_portal.details.transaction_id", "Transaction ID"), d.get('transaction_id', get_text("financial_aid.admin_portal.values.pending", "Pending")))
                add_detail(get_text("financial_aid.admin_portal.details.scheduled_date", "Scheduled Date"), format_date(d.get('scheduled_date')))
                add_detail(get_text("financial_aid.admin_portal.details.disbursement_date", "Disbursement Date"), format_date(d.get('disbursement_date', 'N/A')))

                if d.get('processed_at'):
                    add_detail(get_text("financial_aid.admin_portal.details.processed_date", "Processed Date"), format_date(d['processed_at']))
                    add_detail(get_text("financial_aid.admin_portal.details.processed_by", "Processed By"), d.get('processor_name', get_text("financial_aid.admin_portal.values.system", "System")))

                if d.get('award_id'):
                    add_detail(get_text("financial_aid.admin_portal.details.award_id", "Award ID"), d['award_id'])
                if d.get('component_id'):
                    add_detail(get_text("financial_aid.admin_portal.details.component_id", "Component ID"), d['component_id'])

                if d.get('error_message'):
                    add_detail(get_text("financial_aid.admin_portal.details.error_message", "Error Message"), d['error_message'])

                # Close button
                ttk.Button(details_window, text=get_text("financial_aid.admin_portal.buttons.close", "Close"), command=details_window.destroy).pack(pady=10)

        except Exception as e:
            logger.error(f"Error viewing disbursement details: {e}")
            show_error(get_text("financial_aid.admin_portal.dialogs.error", "Error"), get_text("financial_aid.admin_portal.errors.error_occurred", "An error occurred: {error}").format(error=str(e)))

    def _show_create_disbursement_dialog(self):
        """Show dialog to create new disbursement"""
        dialog = tk.Toplevel(self.parent_frame)
        dialog.title(get_text("financial_aid.admin_portal.dialogs.create_disbursement", "Create New Disbursement"))
        dialog.geometry("500x600")

        ttk.Label(dialog, text=get_text("financial_aid.admin_portal.dialogs.create_disbursement", "Create New Disbursement"), font=('Arial', 14, 'bold')).pack(pady=10)

        # Form
        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill='both', expand=True)

        fields = {}

        # Student ID
        ttk.Label(form_frame, text=get_text("financial_aid.admin_portal.labels.student_id", "Student ID:")).pack(anchor='w', pady=(5, 0))
        fields['student_id'] = ttk.Entry(form_frame, width=40)
        fields['student_id'].pack(fill='x', pady=(0, 10))

        # Amount
        ttk.Label(form_frame, text=get_text("financial_aid.admin_portal.labels.amount_dollars", "Amount ($):")).pack(anchor='w', pady=(5, 0))
        fields['amount'] = ttk.Entry(form_frame, width=40)
        fields['amount'].pack(fill='x', pady=(0, 10))

        # Type
        ttk.Label(form_frame, text=get_text("financial_aid.admin_portal.labels.disbursement_type", "Disbursement Type:")).pack(anchor='w', pady=(5, 0))
        fields['type'] = ttk.Combobox(form_frame, values=[get_text("financial_aid.admin_portal.disbursements.types.scholarship", "Scholarship"), get_text("financial_aid.admin_portal.disbursements.types.grant", "Grant"), get_text("financial_aid.admin_portal.disbursements.types.loan", "Loan"), get_text("financial_aid.admin_portal.disbursements.types.work_study", "Work-Study"), get_text("financial_aid.admin_portal.disbursements.types.refund", "Refund")], width=38)
        fields['type'].set('grant')
        fields['type'].pack(fill='x', pady=(0, 10))

        # Academic Term
        ttk.Label(form_frame, text=get_text("financial_aid.admin_portal.labels.academic_term", "Academic Term:")).pack(anchor='w', pady=(5, 0))
        fields['term'] = ttk.Combobox(form_frame, values=[get_text("financial_aid.admin_portal.disbursements.terms.fall", "Fall"), get_text("financial_aid.admin_portal.disbursements.terms.spring", "Spring"), get_text("financial_aid.admin_portal.disbursements.terms.summer", "Summer")], width=38)
        fields['term'].set('Fall')
        fields['term'].pack(fill='x', pady=(0, 10))

        # Scheduled Date
        ttk.Label(form_frame, text=get_text("financial_aid.admin_portal.labels.scheduled_date", "Scheduled Date (YYYY-MM-DD):")).pack(anchor='w', pady=(5, 0))
        fields['date'] = ttk.Entry(form_frame, width=40)
        fields['date'].insert(0, date.today().strftime('%Y-%m-%d'))
        fields['date'].pack(fill='x', pady=(0, 10))

        # Payment Method
        ttk.Label(form_frame, text=get_text("financial_aid.admin_portal.labels.payment_method", "Payment Method:")).pack(anchor='w', pady=(5, 0))
        fields['method'] = ttk.Combobox(form_frame, values=[get_text("financial_aid.admin_portal.disbursements.methods.account_credit", "Account Credit"), get_text("financial_aid.admin_portal.disbursements.methods.direct_deposit", "Direct Deposit"), get_text("financial_aid.admin_portal.disbursements.methods.check", "Check"), get_text("financial_aid.admin_portal.disbursements.methods.wire_transfer", "Wire Transfer")], width=38)
        fields['method'].set('account_credit')
        fields['method'].pack(fill='x', pady=(0, 10))

        def create_disbursement():
            try:
                # Validate
                if not fields['student_id'].get().strip():
                    show_error(get_text("financial_aid.admin_portal.dialogs.validation_error", "Validation Error"), get_text("financial_aid.admin_portal.errors.student_id_required", "Student ID is required"))
                    return

                amount = float(fields['amount'].get())
                if amount <= 0:
                    show_error(get_text("financial_aid.admin_portal.dialogs.validation_error", "Validation Error"), get_text("financial_aid.admin_portal.errors.amount_must_be_positive", "Amount must be greater than 0"))
                    return

                # Create disbursement
                disb_id = self.aid_manager.create_disbursement(
                    student_id=fields['student_id'].get().strip(),
                    amount=amount,
                    disbursement_date=date.fromisoformat(fields['date'].get()),
                    disbursement_type=fields['type'].get(),
                    academic_term=fields['term'].get()
                )

                if disb_id:
                    # Update payment method
                    with transaction() as conn:
                        conn.execute("""
                            UPDATE disbursements
                            SET payment_method = ?, scheduled_date = ?
                            WHERE disbursement_id = ?
                        """, (fields['method'].get(), fields['date'].get(), disb_id))

                    log_activity('create', 'disbursement', disb_id, {
                        'student_id': fields['student_id'].get(),
                        'amount': amount
                    })

                    show_success(get_text("financial_aid.admin_portal.dialogs.success", "Success"), get_text("financial_aid.admin_portal.messages.disbursement_created", "Disbursement created successfully!\nDisbursement ID: {id}").format(id=disb_id))
                    dialog.destroy()
                    self.show_disbursements()  # Refresh
                else:
                    show_error(get_text("financial_aid.admin_portal.dialogs.error", "Error"), get_text("financial_aid.admin_portal.errors.failed_create_disbursement", "Failed to create disbursement"))

            except ValueError as e:
                show_error(get_text("financial_aid.admin_portal.dialogs.validation_error", "Validation Error"), get_text("financial_aid.admin_portal.errors.invalid_input", "Invalid input: {error}").format(error=str(e)))
            except Exception as e:
                logger.error(f"Error creating disbursement: {e}")
                show_error(get_text("financial_aid.admin_portal.dialogs.error", "Error"), get_text("financial_aid.admin_portal.errors.error_occurred", "An error occurred: {error}").format(error=str(e)))

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.create", "Create"), command=create_disbursement, style='Success.TButton').pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.cancel", "Cancel"), command=dialog.destroy).pack(side='left', padx=5)

    def _export_disbursement_report(self):
        """Export disbursement report to CSV"""
        try:
            with get_connection() as conn:
                # Get all disbursements
                disbursements = conn.execute("""
                    SELECT d.*, s.first_name, s.last_name, s.student_id as sid,
                           u.username as processor
                    FROM disbursements d
                    LEFT JOIN students s ON d.student_id = s.student_id
                    LEFT JOIN users u ON d.processed_by = u.id
                    ORDER BY d.disbursement_date DESC
                """).fetchall()

                data = []
                for disb in disbursements:
                    # Convert Row to dict
                    d = dict(disb)
                    data.append({
                        get_text("financial_aid.admin_portal.csv_headers.disbursement_id", "Disbursement ID"): d['disbursement_id'],
                        get_text("financial_aid.admin_portal.csv_headers.student_name", "Student Name"): f"{d.get('first_name', 'N/A')} {d.get('last_name', '')}",
                        get_text("financial_aid.admin_portal.csv_headers.student_id", "Student ID"): d.get('sid', d['student_id']),
                        get_text("financial_aid.admin_portal.csv_headers.type", "Type"): d.get('disbursement_type', 'N/A'),
                        get_text("financial_aid.admin_portal.csv_headers.amount", "Amount"): d['amount'],
                        get_text("financial_aid.admin_portal.csv_headers.status", "Status"): d['status'],
                        get_text("financial_aid.admin_portal.csv_headers.scheduled_date", "Scheduled Date"): d.get('scheduled_date', 'N/A'),
                        get_text("financial_aid.admin_portal.csv_headers.disbursement_date", "Disbursement Date"): d.get('disbursement_date', 'N/A'),
                        get_text("financial_aid.admin_portal.csv_headers.processed_date", "Processed Date"): d.get('processed_at', 'N/A'),
                        get_text("financial_aid.admin_portal.csv_headers.processed_by", "Processed By"): d.get('processor', 'N/A'),
                        get_text("financial_aid.admin_portal.csv_headers.term", "Term"): d.get('academic_term', 'N/A'),
                        get_text("financial_aid.admin_portal.csv_headers.payment_method", "Payment Method"): d.get('payment_method', 'N/A'),
                        get_text("financial_aid.admin_portal.csv_headers.transaction_id", "Transaction ID"): d.get('transaction_id', 'N/A')
                    })

                export_to_csv(data, f"disbursement_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

        except Exception as e:
            logger.error(f"Error exporting disbursement report: {e}")
            show_error(get_text("financial_aid.admin_portal.dialogs.export_error", "Export Error"), get_text("financial_aid.admin_portal.errors.failed_export_report", "Failed to export report: {error}").format(error=str(e)))

    # Toggle checkbox function (for Treeview)
    def _toggle_selection(self, tree, event):
        """Toggle selection checkbox on click"""
        region = tree.identify_region(event.x, event.y)
        if region == "cell":
            column = tree.identify_column(event.x)
            if column == '#1':  # First column (Select)
                item = tree.identify_row(event.y)
                if item:
                    values = list(tree.item(item)['values'])
                    values[0] = '\u2611' if values[0] == '\u2610' else '\u2610'
                    tree.item(item, values=values)
