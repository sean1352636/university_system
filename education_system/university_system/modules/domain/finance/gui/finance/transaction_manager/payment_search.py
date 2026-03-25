"""Payment search dialog with filters and export"""

from education_system.university_system.modules.domain.finance.gui.finance.transaction_manager._imports import (
    tk, ttk, messagebox, filedialog, csv, _, get_connection,
)
from education_system.university_system.core.sql_safety import escape_like


class PaymentSearchMixin:
    """Mixin for payment search functionality"""

    def search_payments(self):
        """Search payments with comprehensive search functionality"""
        # Create search dialog
        search_dialog = tk.Toplevel(self.root)
        search_dialog.title(_("finance_gui.transaction_manager.search_payments_title"))
        search_dialog.geometry("950x750")
        search_dialog.transient(self.root)
        search_dialog.grab_set()

        # Create main container with canvas for scrolling
        main_container = tk.Frame(search_dialog)
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

        # Search criteria frame
        criteria_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.transaction_manager.search_criteria_frame"), padding=15)
        criteria_frame.pack(fill='x', padx=10, pady=10)

        # Student ID
        ttk.Label(criteria_frame, text=_("finance_gui.transaction_manager.student_id_label")).grid(row=0, column=0, sticky='w', padx=5, pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=student_id_var, width=20).grid(row=0, column=1, sticky='w', padx=5, pady=5)

        # Payment method
        ttk.Label(criteria_frame, text=_("finance_gui.transaction_manager.payment_method_filter")).grid(row=0, column=2, sticky='w', padx=5, pady=5)
        method_var = tk.StringVar()
        method_combo = ttk.Combobox(criteria_frame, textvariable=method_var,
                                    values=["", "Card", "Cash", "Bank Transfer", "Cheque", "Online"],
                                    width=18)
        method_combo.grid(row=0, column=3, sticky='w', padx=5, pady=5)

        # Date range
        ttk.Label(criteria_frame, text=_("finance_gui.transaction_manager.from_date")).grid(row=1, column=0, sticky='w', padx=5, pady=5)
        from_date_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=from_date_var, width=20).grid(row=1, column=1, sticky='w', padx=5, pady=5)

        ttk.Label(criteria_frame, text=_("finance_gui.transaction_manager.to_date")).grid(row=1, column=2, sticky='w', padx=5, pady=5)
        to_date_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=to_date_var, width=18).grid(row=1, column=3, sticky='w', padx=5, pady=5)

        # Amount range
        ttk.Label(criteria_frame, text=_("finance_gui.transaction_manager.min_amount")).grid(row=2, column=0, sticky='w', padx=5, pady=5)
        min_amount_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=min_amount_var, width=20).grid(row=2, column=1, sticky='w', padx=5, pady=5)

        ttk.Label(criteria_frame, text=_("finance_gui.transaction_manager.max_amount")).grid(row=2, column=2, sticky='w', padx=5, pady=5)
        max_amount_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=max_amount_var, width=18).grid(row=2, column=3, sticky='w', padx=5, pady=5)

        # Transaction ID
        ttk.Label(criteria_frame, text=_("finance_gui.transaction_manager.transaction_id_filter")).grid(row=3, column=0, sticky='w', padx=5, pady=5)
        transaction_id_var = tk.StringVar()
        ttk.Entry(criteria_frame, textvariable=transaction_id_var, width=20).grid(row=3, column=1, sticky='w', padx=5, pady=5)

        # Status
        ttk.Label(criteria_frame, text=_("finance_gui.transaction_manager.status_filter")).grid(row=3, column=2, sticky='w', padx=5, pady=5)
        status_var = tk.StringVar()
        status_combo = ttk.Combobox(criteria_frame, textvariable=status_var,
                                    values=["", "completed", "pending", "failed", "refunded"],
                                    width=18)
        status_combo.grid(row=3, column=3, sticky='w', padx=5, pady=5)

        # Results frame
        results_frame = ttk.LabelFrame(scrollable_frame, text=_("finance_gui.transaction_manager.search_results_frame"), padding=15)
        results_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Results treeview
        columns = ('Payment ID', 'Student ID', 'Student Name', 'Amount', 'Method', 'Date', 'Transaction ID', 'Status')
        results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=15)

        for col in columns:
            results_tree.heading(col, text=col)
            results_tree.column(col, width=100, anchor='center')

        results_tree.pack(side='left', fill='both', expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(results_frame, orient='vertical', command=results_tree.yview)
        scrollbar.pack(side='right', fill='y')
        results_tree.configure(yscrollcommand=scrollbar.set)

        # Results label
        results_label = ttk.Label(scrollable_frame, text=_("finance_gui.transaction_manager.results_label", count=0))
        results_label.pack(pady=5)

        def perform_search():
            """Execute the search with given criteria"""
            try:
                # Clear previous results
                for item in results_tree.get_children():
                    results_tree.delete(item)

                # Build SQL query
                query = '''
                SELECT p.payment_id, p.student_id,
                       COALESCE(s.first_name || ' ' || s.last_name, 'Unknown') as student_name,
                       p.amount, p.payment_method, p.payment_date, p.transaction_id, p.status
                FROM payments p
                LEFT JOIN students s ON p.student_id = s.student_id
                WHERE 1=1
                '''
                params = []

                # Add criteria
                if student_id_var.get().strip():
                    query += " AND p.student_id LIKE ?"
                    params.append(f"%{escape_like(student_id_var.get().strip())}%")

                if method_var.get():
                    query += " AND p.payment_method = ?"
                    params.append(method_var.get())

                if from_date_var.get().strip():
                    query += " AND p.payment_date >= ?"
                    params.append(from_date_var.get().strip())

                if to_date_var.get().strip():
                    query += " AND p.payment_date <= ?"
                    params.append(to_date_var.get().strip())

                if min_amount_var.get().strip():
                    query += " AND p.amount >= ?"
                    params.append(float(min_amount_var.get().strip()))

                if max_amount_var.get().strip():
                    query += " AND p.amount <= ?"
                    params.append(float(max_amount_var.get().strip()))

                if transaction_id_var.get().strip():
                    query += " AND p.transaction_id LIKE ?"
                    params.append(f"%{escape_like(transaction_id_var.get().strip())}%")

                if status_var.get():
                    query += " AND p.status = ?"
                    params.append(status_var.get())

                query += " ORDER BY p.payment_date DESC LIMIT 1000"

                # Execute query
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute(query, params)
                results = cursor.fetchall()
                conn.close()

                # Display results
                for row in results:
                    payment_id, student_id, student_name, amount, method, date, trans_id, status = row
                    results_tree.insert('', 'end', values=(
                        payment_id,
                        student_id,
                        student_name,
                        f"\u00a3{amount:.2f}",
                        method,
                        date,
                        trans_id or 'N/A',
                        status
                    ))

                results_label.config(text=_("finance_gui.transaction_manager.results_label", count=len(results)))
                self.update_status(_("finance_gui.transaction_manager.search_completed", count=len(results)))

            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.invalid_amount_format"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.search_failed", error=str(e)))

        def export_results():
            """Export search results to CSV"""
            try:
                if not results_tree.get_children():
                    messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.transaction_manager.no_results_export"))
                    return

                filename = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    title=_("finance_gui.transaction_manager.export_search_results")
                )

                if filename:
                    with open(filename, 'w', newline='') as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow(['Payment ID', 'Student ID', 'Student Name', 'Amount', 'Method', 'Date', 'Transaction ID', 'Status'])

                        for item in results_tree.get_children():
                            values = results_tree.item(item)['values']
                            writer.writerow(values)

                    messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.results_exported", filename=filename))

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.export_failed", error=str(e)))

        def clear_filters():
            """Clear all search filters"""
            student_id_var.set("")
            method_var.set("")
            from_date_var.set("")
            to_date_var.set("")
            min_amount_var.set("")
            max_amount_var.set("")
            transaction_id_var.set("")
            status_var.set("")

            # Clear results
            for item in results_tree.get_children():
                results_tree.delete(item)
            results_label.config(text=_("finance_gui.transaction_manager.results_label", count=0))

        # Buttons frame
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_search"), command=perform_search).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_export_results"), command=export_results).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_clear_filters"), command=clear_filters).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_("finance_gui.transaction_manager.btn_close"), command=search_dialog.destroy).pack(side='left', padx=5)
