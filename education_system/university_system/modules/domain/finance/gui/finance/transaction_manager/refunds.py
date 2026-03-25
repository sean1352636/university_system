"""Refund processing GUI"""

from education_system.university_system.modules.domain.finance.gui.finance.transaction_manager._imports import (
    tk, ttk, messagebox, _, datetime, get_connection, get_auth,
)


class RefundsMixin:
    """Mixin for refund processing"""

    def gui_process_refund(self):
        """GUI wrapper for process_refund"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.process_refund_title"))
        dialog.geometry("900x750")
        dialog.transient(self.root)
        dialog.grab_set()

        # Create main container with canvas for scrolling
        main_container = tk.Frame(dialog)
        main_container.pack(fill='both', expand=True)

        # Create canvas
        canvas = tk.Canvas(main_container, bg='white')
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='white')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling support
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # Student selection
        student_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.transaction_manager.student_info_frame"), padding=15)
        student_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(student_frame, text=_("finance_gui.transaction_manager.student_id_label"), font=('Arial', 12)).pack(anchor='w')
        student_id_var = tk.StringVar()
        student_entry = ttk.Entry(student_frame, textvariable=student_id_var, font=('Arial', 12), width=20)
        student_entry.pack(anchor='w', pady=5)

        ttk.Button(student_frame, text=_("finance_gui.transaction_manager.load_payment_history"),
                  command=lambda: self.load_payment_history(student_id_var.get(), payments_tree)).pack(anchor='w', pady=5)

        # Payment history display
        history_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.transaction_manager.payment_history_frame"), padding=15)
        history_frame.pack(fill='both', expand=True, padx=20, pady=10)

        columns = ('Payment ID', 'Amount', 'Method', 'Date', 'Transaction ID')
        payments_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=8)

        for col in columns:
            payments_tree.heading(col, text=col)
            payments_tree.column(col, width=120, anchor='center')

        payments_tree.pack(fill='both', expand=True)

        # Refund details
        refund_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.transaction_manager.refund_details_frame"), padding=15)
        refund_frame.pack(fill='x', padx=20, pady=10)

        # Refund type
        ttk.Label(refund_frame, text=_("finance_gui.transaction_manager.refund_type_label"), font=('Arial', 12)).pack(anchor='w')
        refund_type_var = tk.StringVar(value="partial")
        refund_type_combo = ttk.Combobox(refund_frame, textvariable=refund_type_var,
                                        values=["full", "partial", "withdrawal", "overpayment"],
                                        state='readonly', font=('Arial', 12))
        refund_type_combo.pack(anchor='w', pady=5)

        # Refund amount
        ttk.Label(refund_frame, text=_("finance_gui.transaction_manager.refund_amount_label"), font=('Arial', 12)).pack(anchor='w')
        refund_amount_var = tk.StringVar()
        ttk.Entry(refund_frame, textvariable=refund_amount_var, font=('Arial', 12), width=15).pack(anchor='w', pady=5)

        # Refund reason
        ttk.Label(refund_frame, text=_("finance_gui.transaction_manager.refund_reason_label"), font=('Arial', 12)).pack(anchor='w')
        reason_text = tk.Text(refund_frame, height=3, width=60, font=('Arial', 10))
        reason_text.pack(anchor='w', pady=5)

        # Refund method
        ttk.Label(refund_frame, text=_("finance_gui.transaction_manager.refund_method_label"), font=('Arial', 12)).pack(anchor='w')
        refund_method_var = tk.StringVar(value="bank_transfer")
        method_combo = ttk.Combobox(refund_frame, textvariable=refund_method_var,
                                   values=["bank_transfer", "original_payment_method", "check", "cash"],
                                   state='readonly', font=('Arial', 12))
        method_combo.pack(anchor='w', pady=5)

        def process_refund():
            try:
                student_id = student_id_var.get().strip()
                refund_amount = float(refund_amount_var.get())
                refund_type = refund_type_var.get()
                refund_method = refund_method_var.get()
                reason = reason_text.get("1.0", tk.END).strip()

                if not all([student_id, refund_amount > 0, refund_type, refund_method, reason]):
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.all_fields_required"))
                    return

                # Get authentication
                auth = get_auth()
                username = 'system'
                has_approve_permission = False

                if auth and hasattr(auth, 'is_logged_in') and auth.is_logged_in():
                    user = auth.get_current_user()
                    username = user.get('username', 'system') if user else 'system'
                    has_approve_permission = auth.has_permission('approve_refunds') if hasattr(auth, 'has_permission') else False

                # Get selected payment
                selected_item = payments_tree.selection()
                original_payment_id = None

                if selected_item:
                    payment_data = payments_tree.item(selected_item[0])['values']
                    original_payment_id = payment_data[0]
                    original_amount = float(payment_data[1].replace('\u00a3', ''))

                    if refund_amount > original_amount:
                        messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.refund_exceeds_original", amount=original_amount))
                        return

                # Create refund request
                conn = get_connection()
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                request_date = datetime.now().strftime('%Y-%m-%d')

                cursor.execute('''
                INSERT INTO unified_refunds
                (student_id, reference_id, reference_type, amount, reason, refund_type,
                 refund_method, status, requested_by, request_date, refund_date,
                 source_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id,
                      str(original_payment_id) if original_payment_id else None,
                      'payment' if original_payment_id else None,
                      refund_amount, reason, refund_type,
                      refund_method, 'pending', username, request_date, request_date,
                      'general', now))

                refund_id = cursor.lastrowid

                # Auto-approve if user has permissions (simplified)
                if has_approve_permission:
                    cursor.execute('''
                    UPDATE unified_refunds
                    SET status = 'approved', approved_by = ?, approval_date = ?
                    WHERE refund_id = ?
                    ''', (username, request_date, refund_id))
                    status_msg = _("finance_gui.transaction_manager.refund_approved")
                else:
                    status_msg = _("finance_gui.transaction_manager.refund_pending_approval")

                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.messages.success"),
                                   _("finance_gui.transaction_manager.refund_success") + "\n" +
                                   _("finance_gui.transaction_manager.refund_id_label") + f" {refund_id}\n" +
                                   _("finance_gui.transaction_manager.amount_label_display") + f" \u00a3{refund_amount:.2f}\n" +
                                   _("finance_gui.transaction_manager.status_label") + f" {status_msg}")

                dialog.destroy()
                self.update_status(f"Refund request created for \u00a3{refund_amount:.2f}")

            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_refund_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.failed_process_refund", error=str(e)))


        # Buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_process_refund"), command=process_refund).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_cancel"), command=dialog.destroy).pack(side='left', padx=10)
