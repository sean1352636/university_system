"""Financial statement generation and display"""

from education_system.systems.university.interfaces.gui.finance.finance.transaction_manager._imports import (
    tk, ttk, messagebox, filedialog, os, _, datetime, get_connection,
)
from tkinter.scrolledtext import ScrolledText


class FinancialStatementMixin:
    """Mixin for financial statement functionality"""

    def gui_view_student_financial_statement(self):
        """GUI wrapper for viewing student financial statement"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.financial_statement_title"))
        dialog.geometry("1000x700")
        dialog.transient(self.root)
        dialog.grab_set()

        # Student selection
        input_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.student_selection_frame"), padding=15)
        input_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(input_frame, text=_("finance_gui.transaction_manager.student_id_label"), font=('Arial', 12)).pack(side='left', padx=5)
        student_id_var = tk.StringVar()
        student_entry = ttk.Entry(input_frame, textvariable=student_id_var, font=('Arial', 12), width=15)
        student_entry.pack(side='left', padx=5)

        ttk.Button(input_frame, text=_("finance_gui.transaction_manager.btn_generate_statement"),
                  command=lambda: self.generate_financial_statement(student_id_var.get(), statement_text)).pack(side='left', padx=10)

        # Statement display
        statement_frame = ttk.LabelFrame(dialog, text=_("finance_gui.transaction_manager.financial_statement_frame"), padding=15)
        statement_frame.pack(fill='both', expand=True, padx=20, pady=10)

        statement_text = ScrolledText(statement_frame, height=25, width=100, font=('Courier', 10))
        statement_text.pack(fill='both', expand=True)

        # Export buttons
        export_frame = ttk.Frame(dialog)
        export_frame.pack(pady=10)

        def export_statement():
            if not statement_text.get("1.0", tk.END).strip():
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.no_statement_to_export"))
                return

            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"financial_statement_{student_id_var.get()}_{datetime.now().strftime('%Y%m%d')}.txt"
            )

            if filename:
                try:
                    with open(filename, 'w') as f:
                        f.write(statement_text.get("1.0", tk.END))
                    messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.statement_exported", filename=filename))
                except Exception as e:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.export_statement_failed", error=str(e)))

        def print_statement():
            """Print the financial statement"""
            if not statement_text.get("1.0", tk.END).strip():
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.no_statement_to_print"))
                return

            try:
                import tempfile
                import platform

                # Create temporary file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                    temp_file.write(statement_text.get("1.0", tk.END))
                    temp_path = temp_file.name

                # Print based on OS
                import subprocess
                if platform.system() == 'Windows':
                    os.startfile(temp_path, "print")
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.run(['lpr', temp_path], check=False)
                else:  # Linux
                    subprocess.run(['lpr', temp_path], check=False)

                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.statement_sent_to_printer"))

            except Exception as e:
                # Fallback: offer to save as PDF
                if messagebox.askyesno(_("finance_gui.transaction_manager.print_failed_title"),
                                      _("finance_gui.transaction_manager.print_failed_save_pdf", error=str(e))):
                    filename = filedialog.asksaveasfilename(
                        defaultextension=".pdf",
                        filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                        initialfile=f"financial_statement_{student_id_var.get()}.pdf"
                    )
                    if filename:
                        try:
                            # Simple text to PDF (fallback to text file if no PDF library)
                            filename = filename.replace('.pdf', '.txt')
                            with open(filename, 'w') as f:
                                f.write(statement_text.get("1.0", tk.END))
                            messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.transaction_manager.saved_as_text", filename=filename))
                        except Exception as save_error:
                            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.save_failed", error=str(save_error)))

        ttk.Button(export_frame, text=_("finance_gui.transaction_manager.btn_export_statement"), command=export_statement).pack(side='left', padx=10)
        ttk.Button(export_frame, text=_("finance_gui.transaction_manager.btn_print_statement"), command=print_statement).pack(side='left', padx=10)
        ttk.Button(export_frame, text=_("finance_gui.transaction_manager.btn_close"), command=dialog.destroy).pack(side='left', padx=10)


    def generate_financial_statement(self, student_id, text_widget):
        """Generate and display financial statement"""
        if not student_id:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.student_id_required"))
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get student details
            cursor.execute('''
            SELECT first_name, last_name, email_address, course, enrollment_date, status
            FROM students
            WHERE student_id = ?
            ''', (student_id,))

            student = cursor.fetchone()
            if not student:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.student_not_found_statement"))
                return

            first_name, last_name, email, course, enrollment_date, status = student

            # Build statement content
            statement = f"""
    {'=' * 80}
    FINANCIAL STATEMENT
    {'=' * 80}
    Student: {first_name} {last_name}
    Student ID: {student_id}
    Course: {course}
    Enrollment Date: {enrollment_date}
    Status: {status}
    Statement Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    {'=' * 80}

    """

            # Get all fees
            cursor.execute('''
            SELECT ft.fee_name, sf.amount, sf.due_date, sf.status, sf.created_at
            FROM student_fees sf
            JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
            WHERE sf.student_id = ?
            ORDER BY sf.created_at
            ''', (student_id,))

            fees = cursor.fetchall()

            statement += "FEES CHARGED:\n"
            statement += "-" * 80 + "\n"
            total_fees = 0
            for fee_name, amount, due_date, fee_status, created_at in fees:
                status_indicator = "\u2713" if fee_status == 'paid' else "\u25cb" if fee_status == 'partial' else "\u00d7"
                statement += f"{status_indicator} {fee_name:<30} \u00a3{amount:>10.2f}  Due: {due_date}\n"
                total_fees += amount

            statement += "-" * 80 + "\n"
            statement += f"Total Fees Charged: \u00a3{total_fees:>10.2f}\n\n"

            # Get all payments
            cursor.execute('''
            SELECT amount, payment_method, payment_date, transaction_id
            FROM payments
            WHERE student_id = ? AND status = 'completed'
            ORDER BY payment_date
            ''', (student_id,))

            payments = cursor.fetchall()

            statement += "PAYMENTS RECEIVED:\n"
            statement += "-" * 80 + "\n"
            total_payments = 0
            for amount, method, date, trans_id in payments:
                trans_display = trans_id if trans_id else "N/A"
                statement += f"{date} {method:<15} \u00a3{amount:>10.2f}  Ref: {trans_display}\n"
                total_payments += amount

            statement += "-" * 80 + "\n"
            statement += f"Total Payments: \u00a3{total_payments:>10.2f}\n\n"

            # Get credits
            cursor.execute('''
            SELECT credit_amount, remaining_amount, credit_source, created_at, status
            FROM student_credits
            WHERE student_id = ?
            ORDER BY created_at
            ''', (student_id,))

            credits = cursor.fetchall()

            if credits:
                statement += "CREDITS:\n"
                statement += "-" * 80 + "\n"
                total_credits = 0
                active_credits = 0
                for credit_amount, remaining, source, created_at, credit_status in credits:
                    status_display = credit_status.upper()
                    statement += f"{created_at} {source:<15} \u00a3{credit_amount:>10.2f}  Remaining: \u00a3{remaining:.2f} ({status_display})\n"
                    total_credits += credit_amount
                    if credit_status == 'active':
                        active_credits += remaining

                statement += "-" * 80 + "\n"
                statement += f"Total Credits Issued: \u00a3{total_credits:>10.2f}\n"
                statement += f"Active Credits Available: \u00a3{active_credits:>10.2f}\n\n"

            # Calculate balance
            balance = total_fees - total_payments

            statement += "=" * 80 + "\n"
            statement += "ACCOUNT SUMMARY:\n"
            statement += f"Total Fees: \u00a3{total_fees:>10.2f}\n"
            statement += f"Total Payments: \u00a3{total_payments:>10.2f}\n"
            if credits:
                active_credits = sum(c[1] for c in credits if c[4] == 'active')
                statement += f"Available Credits: \u00a3{active_credits:>10.2f}\n"
            statement += "-" * 30 + "\n"
            if balance > 0:
                statement += f"BALANCE DUE: \u00a3{balance:>10.2f}\n"
            elif balance < 0:
                statement += f"CREDIT BALANCE: \u00a3{abs(balance):>10.2f}\n"
            else:
                statement += "ACCOUNT BALANCE: \u00a30.00\n"
            statement += "=" * 80 + "\n"

            # Display in text widget
            text_widget.delete('1.0', tk.END)
            text_widget.insert('1.0', statement)

            conn.close()
            self.update_status(f"Financial statement generated for {student_id}")

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.generate_statement_failed", error=str(e)))
