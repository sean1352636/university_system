"""Methods notify_musicshop_finance_gui through export_refunds_to_csv."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import musicshop_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class MusicShopGUI:
    def notify_musicshop_finance_gui(self, transaction_id, amount, method, refund_ref, customer_id):
        """Notify finance GUI about the refund - already recorded in unified_refunds."""
        try:
            logger.info(f"[Music Shop] Refund {refund_ref} recorded in unified_refunds")
        except Exception as e:
            logger.error(f"Error notifying finance GUI: {e}")

    def view_refund_transaction_details(self):
        """View detailed information for selected transaction"""
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("musicshop.msg_titles.no_selection"), _t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_notify_musicshop_finance.dialogs.please_select_a_transaction_to_view_details', default="Please select a transaction to view details."))
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']

        if len(values) < 7:
            messagebox.showerror(_t("musicshop.msg_titles.error"), _t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_notify_musicshop_finance.dialogs.invalid_transaction_data', default="Invalid transaction data."))
            return

        transaction_id = values[0]
        order_id = values[1]

        try:
            with get_db_connection() as conn:
                # Get transaction details
                cursor = conn.execute('''
                    SELECT t.*, o.shipping_address, o.status as order_status
                    FROM transactions t
                    LEFT JOIN orders o ON t.reference_id = o.id AND t.reference_type = 'order' AND o.source_type = 'music_shop'
                    WHERE t.source_type = 'music_shop' AND t.transaction_id = ?
                ''', (transaction_id,))

                trans = cursor.fetchone()

                if not trans:
                    messagebox.showerror(_t("musicshop.msg_titles.error"), _t('gui.operations.commerce.musicshop.musicshop_gui_parts.musicshopgui_notify_musicshop_finance.dialogs.transaction_not_found', default="Transaction not found."))
                    return

                # Get order items
                cursor = conn.execute('''
                    SELECT oi.product_id, p.name, p.artist, p.genre, oi.quantity, oi.unit_price, oi.subtotal
                    FROM order_items oi
                    LEFT JOIN products p ON oi.product_id = p.id AND p.source_type = 'music_shop'
                    WHERE oi.order_id = ?
                ''', (order_id,))

                items = cursor.fetchall()

            # Create details window
            details_window = tk.Toplevel(self.root)
            details_window.title(f"Transaction Details - {transaction_id}")
            details_window.geometry("600x600")
            details_window.transient(self.root)

            main_frame = ttk.Frame(details_window, padding=20)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Transaction information
            from tkinter.scrolledtext import ScrolledText
            info_text = ScrolledText(main_frame, width=70, height=30, wrap=tk.WORD)
            info_text.pack(fill=tk.BOTH, expand=True)

            # Format order items
            items_text = ""
            if items:
                for item in items:
                    product_id, title, artist, genre, quantity, unit_price, subtotal = item
                    items_text += f"\n{title} - {artist}\n"
                    if genre:
                        items_text += f"  Genre: {genre}\n"
                    items_text += f"  Quantity: {quantity} x £{unit_price:.2f} = £{subtotal:.2f}\n"

            details = f"""TRANSACTION DETAILS
═══════════════════════════════════════════════════════

Transaction ID:     {trans[0]}
Order ID:           {trans[1]}
Customer ID:        {trans[2]}
Transaction Type:   {trans[3]}
Payment Method:     {trans[5] or 'N/A'}
Reference Number:   {trans[6] or 'N/A'}
Status:             {trans[7].upper()}
Processed By:       {trans[8] or 'System'}
Date:               {trans[9]}

Shipping Address:   {trans[10] if len(trans) > 10 and trans[10] else 'N/A'}
Order Status:       {trans[11].upper() if len(trans) > 11 and trans[11] else 'N/A'}

═══════════════════════════════════════════════════════
ORDER ITEMS
═══════════════════════════════════════════════════════
{items_text}

═══════════════════════════════════════════════════════
TOTAL:              £{trans[4]:.2f}
═══════════════════════════════════════════════════════
"""

            info_text.insert('1.0', details)
            info_text.config(state='disabled')

            ttk.Button(main_frame, text=_t("musicshop.btn.close"), command=details_window.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("musicshop.msg_titles.database_error"), f"Error loading transaction details: {e}")
            logger.error(f"Error loading transaction details: {e}")

    def export_refunds_to_csv(self):
        """Export refunds list to CSV file"""
        try:
            from tkinter import filedialog
            import csv

            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"musicshop_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )

            if not filename:
                return

            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow(['Transaction ID', 'Order ID', 'Date', 'Customer',
                               'Amount', 'Payment Method', 'Status'])

                # Write data
                for item in self.refunds_tree.get_children():
                    values = self.refunds_tree.item(item)['values']
                    writer.writerow(values)

            messagebox.showinfo(_t("musicshop.msg_titles.export_successful"), f"Data exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror(_t("musicshop.msg_titles.export_error"), f"Error exporting data: {e}")
            logger.error(f"Error exporting data: {e}")
