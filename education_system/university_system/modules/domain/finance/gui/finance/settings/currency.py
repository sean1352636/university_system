"""Currency management, exchange rates, and conversion."""

import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from education_system.university_system.core.i18n import get_text as _
from education_system.university_system.infrastructure.database.db import get_connection, sqlite3

SUPPORTED_CURRENCIES = ['GBP', 'USD', 'EUR', 'CAD', 'AUD']


class CurrencyMixin:
    """Currency tab, exchange-rate refresh, and conversion helpers."""

    def create_currency_tab(self):
        """Create multi-currency management tab"""
        tab = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['currency'] = tab

        main_frame = ttk.Frame(tab, padding=20)
        main_frame.pack(fill='both', expand=True)

        # Currency controls
        control_frame = ttk.LabelFrame(main_frame, text=_("finance_gui.settings.currency_management_frame"), padding=15)
        control_frame.pack(fill='x', pady=(0, 20))

        ttk.Button(control_frame, text=_("finance_gui.settings.btn_update_exchange_rates"),
                  command=self.gui_update_exchange_rates, width=25).grid(row=0, column=0, padx=10, pady=5)
        ttk.Button(control_frame, text=_("finance_gui.settings.btn_currency_converter"),
                  command=self.gui_currency_converter, width=25).grid(row=0, column=1, padx=10, pady=5)

        # Currency converter frame
        converter_frame = ttk.LabelFrame(main_frame, text=_("finance_gui.settings.quick_converter_frame"), padding=15)
        converter_frame.pack(fill='x', pady=(0, 20))

        # Converter inputs
        ttk.Label(converter_frame, text=_("finance_gui.settings.amount_label")).grid(row=0, column=0, padx=5, pady=5, sticky='e')
        self.amount_var = tk.StringVar()
        ttk.Entry(converter_frame, textvariable=self.amount_var, width=15).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(converter_frame, text=_("finance_gui.settings.from_label")).grid(row=0, column=2, padx=5, pady=5, sticky='e')
        self.from_currency_var = tk.StringVar(value='GBP')
        ttk.Combobox(converter_frame, textvariable=self.from_currency_var,
                    values=SUPPORTED_CURRENCIES, width=10, state='readonly').grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(converter_frame, text=_("finance_gui.settings.to_label")).grid(row=0, column=4, padx=5, pady=5, sticky='e')
        self.to_currency_var = tk.StringVar(value='USD')
        ttk.Combobox(converter_frame, textvariable=self.to_currency_var,
                    values=SUPPORTED_CURRENCIES, width=10, state='readonly').grid(row=0, column=5, padx=5, pady=5)

        ttk.Button(converter_frame, text=_("finance_gui.settings.btn_convert"),
                  command=self.quick_convert).grid(row=0, column=6, padx=10, pady=5)

        self.conversion_result = tk.StringVar(value=_("finance_gui.settings.result_placeholder"))
        ttk.Label(converter_frame, textvariable=self.conversion_result,
                 font=('Arial', 12, 'bold'), foreground='blue').grid(row=1, column=0, columnspan=7, pady=10)

        # Exchange rates display
        rates_frame = ttk.LabelFrame(main_frame, text=_("finance_gui.settings.current_rates_frame"), padding=15)
        rates_frame.pack(fill='both', expand=True)

        columns = (_("finance_gui.settings.column_from"), _("finance_gui.settings.column_to"), _("finance_gui.settings.column_rate"), _("finance_gui.settings.column_last_updated"), _("finance_gui.settings.column_source"))
        self.rates_tree = ttk.Treeview(rates_frame, columns=columns, show='headings', height=10)

        for col in columns:
            self.rates_tree.heading(col, text=col)
            self.rates_tree.column(col, width=120, anchor='center')

        # Scrollbars
        rates_v_scroll = ttk.Scrollbar(rates_frame, orient='vertical', command=self.rates_tree.yview)
        self.rates_tree.configure(yscrollcommand=rates_v_scroll.set)

        self.rates_tree.pack(side='left', fill='both', expand=True)
        rates_v_scroll.pack(side='right', fill='y')

        self.refresh_exchange_rates()


    def load_exchange_rates(self):
        """Load exchange rates data"""
        def load_thread():
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT from_currency, to_currency, exchange_rate, rate_date
                FROM exchange_rates
                ORDER BY from_currency, to_currency
                ''')

                rates = cursor.fetchall()
                conn.close()

                self.root.after(0, lambda: self.update_exchange_rates_table(rates))

            except Exception as e:
                print(f"Error loading exchange rates: {e}")

        threading.Thread(target=load_thread, daemon=True).start()


    def update_exchange_rates_table(self, rates):
        """Update exchange rates table"""
        try:
            for item in self.exchange_rates_tree.get_children():
                self.exchange_rates_tree.delete(item)

            for rate in rates:
                self.exchange_rates_tree.insert('', 'end', values=rate)
        except AttributeError:
            pass  # Table not created yet


    def gui_update_exchange_rates(self):
        """GUI for updating exchange rates"""
        if messagebox.askyesno(_("finance_gui.settings.confirm_title"), _("finance_gui.settings.confirm_update_rates")):
            try:
                self.update_status(_("finance_gui.settings.updating_rates"))

                def update_rates():
                    # Simulate API call with sample rates
                    sample_rates = {
                        'USD': 1.27,
                        'EUR': 1.17,
                        'CAD': 1.71,
                        'AUD': 1.91,
                        'JPY': 188.50,
                        'CHF': 1.14
                    }

                    conn = get_connection()
                    cursor = conn.cursor()

                    current_date = datetime.now().strftime('%Y-%m-%d')
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    base_currency = 'GBP'

                    rates_updated = 0

                    for currency, rate in sample_rates.items():
                        if currency != base_currency:
                            cursor.execute('''
                            INSERT OR REPLACE INTO exchange_rates
                            (from_currency, to_currency, exchange_rate, rate_date, source, created_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                            ''', (base_currency, currency, rate, current_date, 'api', current_time))
                            rates_updated += 1

                    # Update last update time
                    cursor.execute('''
                    UPDATE currency_settings
                    SET last_rate_update = ?, updated_at = ?
                    ''', (current_time, current_time))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo(_("finance_gui.settings.success_title"), _("finance_gui.settings.rates_updated", count=rates_updated))
                    self.refresh_exchange_rates()
                    self.update_status(_("finance_gui.settings.exchange_rates_updated"))

                thread = threading.Thread(target=update_rates)
                thread.daemon = True
                thread.start()

            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_update_rates", error=str(e)))


    def gui_currency_converter(self):
        """Open detailed currency converter dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.settings.currency_converter_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        # Converter frame
        converter_frame = ttk.LabelFrame(dialog, text=_("finance_gui.settings.conversion_frame"), padding=20)
        converter_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Amount input
        ttk.Label(converter_frame, text=_("finance_gui.settings.amount_label"), font=('Arial', 14)).grid(row=0, column=0, sticky='e', padx=10, pady=10)
        amount_var = tk.StringVar()
        amount_entry = ttk.Entry(converter_frame, textvariable=amount_var, font=('Arial', 14), width=15)
        amount_entry.grid(row=0, column=1, padx=10, pady=10)
        amount_entry.focus()

        # From currency
        ttk.Label(converter_frame, text=_("finance_gui.settings.from_label"), font=('Arial', 14)).grid(row=1, column=0, sticky='e', padx=10, pady=10)
        from_var = tk.StringVar(value='GBP')
        from_combo = ttk.Combobox(converter_frame, textvariable=from_var, values=SUPPORTED_CURRENCIES,
                                 state='readonly', font=('Arial', 14), width=10)
        from_combo.grid(row=1, column=1, padx=10, pady=10)

        # To currency
        ttk.Label(converter_frame, text=_("finance_gui.settings.to_label"), font=('Arial', 14)).grid(row=2, column=0, sticky='e', padx=10, pady=10)
        to_var = tk.StringVar(value='USD')
        to_combo = ttk.Combobox(converter_frame, textvariable=to_var, values=SUPPORTED_CURRENCIES,
                               state='readonly', font=('Arial', 14), width=10)
        to_combo.grid(row=2, column=1, padx=10, pady=10)

        # Result display
        result_frame = ttk.LabelFrame(converter_frame, text=_("finance_gui.settings.conversion_result_frame"), padding=15)
        result_frame.grid(row=4, column=0, columnspan=2, pady=20, sticky='ew')

        result_var = tk.StringVar(value=_("finance_gui.settings.enter_amount_prompt"))
        result_label = ttk.Label(result_frame, textvariable=result_var, font=('Arial', 16, 'bold'),
                                foreground='blue')
        result_label.pack()

        def convert_currency():
            try:
                amount = float(amount_var.get())
                from_currency = from_var.get()
                to_currency = to_var.get()

                if amount <= 0:
                    messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.amount_greater_zero"))
                    return

                if from_currency == to_currency:
                    result_var.set(f"{amount:.2f} {from_currency}")
                    return

                # Get exchange rate
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT exchange_rate FROM exchange_rates
                WHERE from_currency = ? AND to_currency = ?
                ORDER BY rate_date DESC, created_at DESC
                LIMIT 1
                ''', (from_currency, to_currency))

                result = cursor.fetchone()

                if result:
                    rate = result[0]
                    converted_amount = amount * rate
                    result_var.set(f"{amount:.2f} {from_currency} = {converted_amount:.2f} {to_currency}\nRate: 1 {from_currency} = {rate:.4f} {to_currency}")
                else:
                    # Try reverse conversion
                    cursor.execute('''
                    SELECT exchange_rate FROM exchange_rates
                    WHERE from_currency = ? AND to_currency = ?
                    ORDER BY rate_date DESC, created_at DESC
                    LIMIT 1
                    ''', (to_currency, from_currency))

                    result = cursor.fetchone()

                    if result:
                        rate = 1 / result[0]
                        converted_amount = amount * rate
                        result_var.set(f"{amount:.2f} {from_currency} = {converted_amount:.2f} {to_currency}\nRate: 1 {from_currency} = {rate:.4f} {to_currency}")
                    else:
                        result_var.set(_("finance_gui.settings.rate_not_found", **{"from": from_currency, "to": to_currency}))

                conn.close()

            except ValueError:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.please_enter_valid_amount"))
            except Exception as e:
                messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.conversion_failed", error=str(e)))

        # Convert button
        ttk.Button(converter_frame, text=_("finance_gui.settings.btn_convert"), command=convert_currency).grid(row=3, column=0, columnspan=2, pady=20)

        # Bind Enter key to convert
        dialog.bind('<Return>', lambda e: convert_currency())


    def quick_convert(self):
        """Quick currency conversion in main interface"""
        try:
            amount = float(self.amount_var.get())
            from_currency = self.from_currency_var.get()
            to_currency = self.to_currency_var.get()

            if amount <= 0:
                self.conversion_result.set("Amount must be greater than zero")
                return

            if from_currency == to_currency:
                self.conversion_result.set(f"{amount:.2f} {from_currency}")
                return

            converted = convert_currency(amount, from_currency, to_currency)
            self.conversion_result.set(f"{amount:.2f} {from_currency} = {converted:.2f} {to_currency}")

        except ValueError:
            self.conversion_result.set("Please enter a valid amount")
        except Exception as e:
            self.conversion_result.set(f"Conversion failed: {e}")


    def refresh_exchange_rates(self):
        """Refresh exchange rates display"""
        # Check if rates_tree exists before attempting to update
        if not hasattr(self, 'rates_tree') or self.rates_tree is None:
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT from_currency, to_currency, exchange_rate, rate_date, source
            FROM exchange_rates
            ORDER BY rate_date DESC, from_currency, to_currency
            ''')

            rates = cursor.fetchall()

            # Clear existing items
            for item in self.rates_tree.get_children():
                self.rates_tree.delete(item)

            # Add rate data
            for rate in rates:
                from_curr, to_curr, rate_value, rate_date, source = rate
                self.rates_tree.insert('', 'end', values=(
                    from_curr, to_curr, f"{rate_value:.4f}", rate_date, source
                ))

            conn.close()

        except Exception as e:
            messagebox.showerror(_("finance_gui.settings.error_title"), _("finance_gui.settings.failed_refresh_rates", error=str(e)))

    # Analytics and Dashboard Functions

    def convert_currency(amount, from_currency, to_currency):
        """Convert amount from one currency to another (original function)"""
        if from_currency == to_currency:
            return amount

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get latest exchange rate
            cursor.execute('''
            SELECT exchange_rate FROM exchange_rates
            WHERE from_currency = ? AND to_currency = ?
            ORDER BY rate_date DESC, created_at DESC
            LIMIT 1
            ''', (from_currency, to_currency))

            result = cursor.fetchone()

            if result:
                rate = result[0]
                converted_amount = amount * rate
                conn.close()
                return converted_amount
            else:
                # Try reverse conversion
                cursor.execute('''
                SELECT exchange_rate FROM exchange_rates
                WHERE from_currency = ? AND to_currency = ?
                ORDER BY rate_date DESC, created_at DESC
                LIMIT 1
                ''', (to_currency, from_currency))

                result = cursor.fetchone()

                if result:
                    rate = 1 / result[0]
                    converted_amount = amount * rate
                    conn.close()
                    return converted_amount
                else:
                    conn.close()
                    print(f"Exchange rate not found for {from_currency}/{to_currency}")
                    return amount

        except sqlite3.Error as e:
            print(f"Database error in currency conversion: {e}")
            return amount


# Module-level convenience alias used by quick_convert
convert_currency = CurrencyMixin.convert_currency
