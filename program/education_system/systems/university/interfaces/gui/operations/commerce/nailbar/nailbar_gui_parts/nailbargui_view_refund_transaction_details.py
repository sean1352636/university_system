"""Methods view_refund_transaction_details through export_refunds_to_csv."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import nailbar_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class NailBarGUI:
    def view_refund_transaction_details(self):
        """View detailed information for selected transaction"""
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("nailbar.msg_titles.no_selection"), _t('gui.operations.commerce.nailbar.nailbar_gui_parts.nailbargui_view_refund_transaction_details.dialogs.please_select_a_transaction_to_view_details', default="Please select a transaction to view details."))
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']

        if len(values) < 7:
            messagebox.showerror(_t("nailbar.msg_titles.error"), _t('gui.operations.commerce.nailbar.nailbar_gui_parts.nailbargui_view_refund_transaction_details.dialogs.invalid_transaction_data', default="Invalid transaction data."))
            return

        transaction_id = values[0]
        appointment_id = values[1]

        try:
            with get_db_connection() as conn:
                # Get transaction details
                cursor = conn.execute('''
                    SELECT t.*, a.appointment_date, a.appointment_time, a.technician_id, a.status as appt_status
                    FROM transactions t
                    LEFT JOIN nailbar_appointments a ON t.reference_id = a.appointment_id AND t.reference_type = 'appointment'
                    WHERE t.source_type = 'nail_bar' AND t.transaction_id = ?
                ''', (transaction_id,))

                trans = cursor.fetchone()

                if not trans:
                    messagebox.showerror(_t("nailbar.msg_titles.error"), _t('gui.operations.commerce.nailbar.nailbar_gui_parts.nailbargui_view_refund_transaction_details.dialogs.transaction_not_found', default="Transaction not found."))
                    return

                # Get appointment treatments if appointment exists
                treatments_text = ""
                if appointment_id and appointment_id != 'N/A':
                    cursor = conn.execute('''
                        SELECT at.treatment_id, t.name, t.category, t.duration_minutes, t.price
                        FROM nailbar_appointment_treatments at
                        LEFT JOIN nailbar_treatments t ON at.treatment_id = t.treatment_id
                        WHERE at.appointment_id = ?
                    ''', (appointment_id,))

                    treatments = cursor.fetchall()
                    if treatments:
                        for treatment in treatments:
                            treat_id, name, category, duration_minutes, price = treatment
                            treatments_text += f"\n{name} ({category})\n"
                            treatments_text += f"  Duration: {duration_minutes} mins | Price: £{price:.2f}\n"

            # Create details window
            details_window = tk.Toplevel(self.parent)
            details_window.title(f"Transaction Details - {transaction_id}")
            details_window.geometry("600x600")
            details_window.transient(self.parent)

            main_frame = ttk.Frame(details_window, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Transaction information
            from tkinter.scrolledtext import ScrolledText
            info_text = ScrolledText(main_frame, width=70, height=30, wrap=tk.WORD)
            info_text.pack(fill=tk.BOTH, expand=True)

            details = f"""TRANSACTION DETAILS
═══════════════════════════════════════════════════════

Transaction ID:     {trans[0]}
Appointment ID:     {trans[1] if trans[1] else 'N/A'}
Customer ID:        {trans[2]}
Payment Method:     {trans[4]}
Transaction Type:   {trans[5]}
Reference Number:   {trans[7] or 'N/A'}
Status:             {trans[8].upper()}
Processed By:       {trans[11] or 'System'}
Date:               {trans[10]}

Appointment Date:   {trans[12] if len(trans) > 12 and trans[12] else 'N/A'}
Appointment Time:   {trans[13] if len(trans) > 13 and trans[13] else 'N/A'}
Appointment Status: {trans[15].upper() if len(trans) > 15 and trans[15] else 'N/A'}

═══════════════════════════════════════════════════════
TREATMENTS/SERVICES
═══════════════════════════════════════════════════════
{treatments_text if treatments_text else 'No treatments recorded'}

═══════════════════════════════════════════════════════
PAYMENT BREAKDOWN
═══════════════════════════════════════════════════════

Service Amount:     £{trans[3]:.2f}
Tip Amount:         £{trans[6]:.2f}
───────────────────────────────────────────────────────
TOTAL:              £{(trans[3] + trans[6]):.2f}

═══════════════════════════════════════════════════════
"""

            info_text.insert('1.0', details)
            info_text.config(state='disabled')

            ttk.Button(main_frame, text=_t("nailbar.btn.close"), command=details_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("nailbar.msg_titles.database_error"), f"Error loading transaction details: {e}")
            logger.error(f"Error loading transaction details: {e}")

    def export_refunds_to_csv(self):
        """Export refunds list to CSV file"""
        try:
            from tkinter import filedialog
            import csv

            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"nailbar_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )

            if not filename:
                return

            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow(['Transaction ID', 'Appointment ID', 'Date', 'Customer',
                               'Amount', 'Payment Method', 'Status'])

                # Write data
                for item in self.refunds_tree.get_children():
                    values = self.refunds_tree.item(item)['values']
                    writer.writerow(values)

            messagebox.showinfo(_t("nailbar.msg_titles.export_successful"), f"Data exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror(_t("nailbar.msg_titles.export_error"), f"Error exporting data: {e}")
            logger.error(f"Error exporting data: {e}")
