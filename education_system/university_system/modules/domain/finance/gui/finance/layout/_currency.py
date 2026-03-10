"""Currency exchange rates mixin for LayoutManager."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.i18n import get_text as _


class CurrencyMixin:
    """Currency exchange rates: add, edit, delete, refresh."""

    def create_currency_tab(self):
        """Create currency exchange rates management tab"""
        currency_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['currency'] = currency_frame

        # Title
        title_label = tk.Label(currency_frame, text=_("finance_gui.tabs.currency.title"),
                               font=('Arial', 18, 'bold'), bg='white')
        title_label.pack(pady=10)

        # Toolbar
        toolbar = tk.Frame(currency_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Button(toolbar, text=_("finance_gui.buttons.add_rate"), command=self._add_exchange_rate,
                 bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.edit_rate"), command=self._edit_exchange_rate,
                 bg=self.colors['warning'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.delete_rate"), command=self._delete_exchange_rate,
                 bg=self.colors['danger'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.refresh"), command=self._refresh_exchange_rates,
                 bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='right', padx=5)

        # Exchange rates table
        table_frame = tk.Frame(currency_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)

        columns = ('rate_id', 'from_currency', 'to_currency', 'exchange_rate', 'rate_date', 'source')
        self.exchange_rates_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.exchange_rates_tree.heading(col, text=col.replace('_', ' ').title())
            self.exchange_rates_tree.column(col, width=120)

        # Scrollbars
        v_scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.exchange_rates_tree.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient='horizontal', command=self.exchange_rates_tree.xview)
        self.exchange_rates_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.exchange_rates_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Load data
        self.root.after(100, self._refresh_exchange_rates)

    def _add_exchange_rate(self):
        """Add a new exchange rate"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.dialogs.add_exchange_rate"))
        dialog.geometry("500x400")
        dialog.transient(self.root)

        tk.Label(dialog, text=_("finance_gui.dialogs.add_exchange_rate"), font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = tk.Frame(dialog)
        form_frame.pack(padx=20, pady=10, fill='both', expand=True)

        tk.Label(form_frame, text=_("finance_gui.labels.from_currency")).grid(row=0, column=0, sticky='w', pady=5)
        from_currency_var = tk.StringVar(value="GBP")
        from_currency_combo = ttk.Combobox(form_frame, textvariable=from_currency_var,
                                          values=['GBP', 'USD', 'EUR', 'CAD', 'AUD', 'JPY', 'CHF'],
                                          state='readonly', width=27)
        from_currency_combo.grid(row=0, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.to_currency")).grid(row=1, column=0, sticky='w', pady=5)
        to_currency_var = tk.StringVar(value="USD")
        to_currency_combo = ttk.Combobox(form_frame, textvariable=to_currency_var,
                                        values=['GBP', 'USD', 'EUR', 'CAD', 'AUD', 'JPY', 'CHF'],
                                        state='readonly', width=27)
        to_currency_combo.grid(row=1, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.exchange_rate")).grid(row=2, column=0, sticky='w', pady=5)
        rate_entry = tk.Entry(form_frame, width=30)
        rate_entry.grid(row=2, column=1, pady=5)

        tk.Label(form_frame, text=_("finance_gui.labels.source")).grid(row=3, column=0, sticky='w', pady=5)
        source_var = tk.StringVar(value="manual")
        source_combo = ttk.Combobox(form_frame, textvariable=source_var,
                                   values=['manual', 'api', 'bank'],
                                   state='readonly', width=27)
        source_combo.grid(row=3, column=1, pady=5)

        def save_rate():
            try:
                from_currency = from_currency_var.get()
                to_currency = to_currency_var.get()
                exchange_rate = float(rate_entry.get())
                source = source_var.get()

                if from_currency == to_currency:
                    messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.currencies_must_differ"))
                    return

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO exchange_rates
                    (from_currency, to_currency, exchange_rate, rate_date, source, created_at)
                    VALUES (?, ?, ?, date('now'), ?, datetime('now'))
                ''', (from_currency, to_currency, exchange_rate, source))

                conn.commit()
                conn.close()

                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.messages.exchange_rate_added"))
                dialog.destroy()
                self._refresh_exchange_rates()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.failed_add_exchange_rate", error=str(e)))

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text=_("finance_gui.buttons.save"), command=save_rate, bg=self.colors['success'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text=_("finance_gui.buttons.cancel"), command=dialog.destroy, bg=self.colors['danger'],
                 fg='white', padx=20, pady=5).pack(side='left', padx=5)

    def _edit_exchange_rate(self):
        """Edit selected exchange rate"""
        selection = self.exchange_rates_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.messages.select_rate_edit"))
            return
        messagebox.showinfo(_("finance_gui.dialogs.edit_rate"), _("finance_gui.messages.edit_functionality_coming"))

    def _delete_exchange_rate(self):
        """Delete selected exchange rate"""
        selection = self.exchange_rates_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.messages.select_rate_delete"))
            return

        if messagebox.askyesno(_("finance_gui.dialogs.confirm_delete"), _("finance_gui.messages.confirm_delete_rate")):
            try:
                rate_id = self.exchange_rates_tree.item(selection[0])['values'][0]
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM exchange_rates WHERE rate_id = ?", (rate_id,))
                conn.commit()
                conn.close()
                messagebox.showinfo(_("finance_gui.messages.success"), _("finance_gui.messages.exchange_rate_deleted"))
                self._refresh_exchange_rates()
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.messages.failed_delete_exchange_rate", error=str(e)))

    def _refresh_exchange_rates(self):
        """Refresh exchange rates list"""
        try:
            # Clear existing items
            for item in self.exchange_rates_tree.get_children():
                self.exchange_rates_tree.delete(item)

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT rate_id, from_currency, to_currency, exchange_rate, rate_date, source
                FROM exchange_rates
                ORDER BY rate_date DESC, from_currency, to_currency
                LIMIT 500
            ''')

            for row in cursor.fetchall():
                self.exchange_rates_tree.insert('', 'end', values=row)

            conn.close()
        except Exception as e:
            print(f"Error refreshing exchange rates: {e}")
