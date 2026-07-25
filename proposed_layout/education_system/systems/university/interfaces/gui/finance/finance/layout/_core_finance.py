"""Core finance tab mixin for LayoutManager."""

import tkinter as tk
from tkinter import messagebox

from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.i18n import get_text as _


class CoreFinanceMixin:
    """Core finance tab: stats, payments, invoices."""

    def create_core_finance_tab(self):
        """Create core finance tab"""
        core_frame = tk.Frame(self.content_frame, bg='white')
        self.tab_frames['core_finance'] = core_frame

        # Title
        title_label = tk.Label(core_frame, text=_("finance_gui.tabs.core_finance.title"),
                               font=('Arial', 18, 'bold'), bg='white')
        title_label.pack(pady=10)

        # Toolbar
        toolbar = tk.Frame(core_frame, bg='white')
        toolbar.pack(fill='x', padx=10, pady=10)

        tk.Button(toolbar, text=_("finance_gui.buttons.process_payment"), command=self._process_payment,
                 bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text="View All Refunds", command=self._view_all_refunds,
                 bg=self.colors['info'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.create_invoice"), command=self._create_invoice,
                 bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.manage_refunds"), command=self._manage_refunds,
                 bg=self.colors['warning'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(toolbar, text=_("finance_gui.buttons.financial_summary"), command=self._show_financial_summary,
                 bg=self.colors['primary'], fg='white', font=('Arial', 10, 'bold'), padx=15, pady=8).pack(side='left', padx=5)

        # Stats frame
        stats_frame = tk.LabelFrame(core_frame, text=_("finance_gui.labels.quick_statistics"), font=('Arial', 12, 'bold'), bg='white')
        stats_frame.pack(fill='x', padx=10, pady=10)

        # Create stat cards
        stats_container = tk.Frame(stats_frame, bg='white')
        stats_container.pack(fill='x', padx=10, pady=10)

        self._create_stat_card(stats_container, _("finance_gui.stats.total_revenue"), _("common.loading"), self.colors['success'], 0, 0)
        self._create_stat_card(stats_container, _("finance_gui.stats.pending_payments"), _("common.loading"), self.colors['warning'], 0, 1)
        self._create_stat_card(stats_container, _("finance_gui.stats.total_refunds"), _("common.loading"), self.colors['danger'], 0, 2)
        self._create_stat_card(stats_container, _("finance_gui.stats.active_students"), _("common.loading"), self.colors['secondary'], 0, 3)

        # Load initial data
        self.root.after(100, self._load_core_finance_stats)

    def _create_stat_card(self, parent, title, value, color, row, col):
        """Create a statistics card"""
        card = tk.Frame(parent, bg=color, relief='raised', bd=2)
        card.grid(row=row, column=col, padx=5, pady=5, sticky='ew')
        parent.grid_columnconfigure(col, weight=1)

        tk.Label(card, text=title, bg=color, fg='white', font=('Arial', 10, 'bold')).pack(pady=5)
        value_label = tk.Label(card, text=value, bg=color, fg='white', font=('Arial', 14, 'bold'))
        value_label.pack(pady=5)
        setattr(self, f"core_stat_{col}", value_label)

    def _load_core_finance_stats(self):
        """Load core finance statistics"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Total revenue from payments
            cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'completed'")
            total_revenue = cursor.fetchone()[0] or 0

            # Add club payments to total revenue (from payments table with source_type='club')
            try:
                cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE source_type = 'club' AND status = 'completed'")
                club_revenue = cursor.fetchone()[0] or 0
                total_revenue += club_revenue
            except Exception:
                pass  # Column may not exist

            # Add housing payments to total revenue
            try:
                cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE source_type = 'housing' AND status = 'completed'")
                housing_revenue = cursor.fetchone()[0] or 0
                total_revenue += housing_revenue
            except Exception:
                pass  # Table may not exist

            # Add butcher shop orders to total revenue
            try:
                cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE source_type = 'butcher' AND payment_status = 'paid'")
                butcher_revenue = cursor.fetchone()[0] or 0
                total_revenue += butcher_revenue
            except Exception:
                pass  # Table may not exist

            # Add gym payments to total revenue
            try:
                cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE source_type = 'gym' AND transaction_type IN ('membership', 'membership_renewal', 'pt_session')")
                gym_revenue = cursor.fetchone()[0] or 0
                total_revenue += gym_revenue
            except Exception:
                pass  # Table may not exist

            # Add dentist payments to total revenue
            try:
                cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE source_type = 'dentist' AND status = 'completed'")
                dentist_revenue = cursor.fetchone()[0] or 0
                total_revenue += dentist_revenue
            except Exception:
                pass  # Table may not exist

            # Pending payments
            cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
            pending = cursor.fetchone()[0]

            # Total refunds from unified_refunds table (includes all department refunds)
            try:
                cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM unified_refunds")
                refunds = cursor.fetchone()[0] or 0
            except Exception:
                # Fallback if unified_refunds doesn't exist
                cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE payment_method = 'refund'")
                refunds = cursor.fetchone()[0] or 0

            # Active students
            cursor.execute("SELECT COUNT(*) FROM students WHERE status = 'Active'")
            students = cursor.fetchone()[0]

            conn.close()

            # Update UI
            if hasattr(self, 'core_stat_0'):
                self.core_stat_0.config(text=f"\u00a3{total_revenue:,.2f}")
            if hasattr(self, 'core_stat_1'):
                self.core_stat_1.config(text=str(pending))
            if hasattr(self, 'core_stat_2'):
                self.core_stat_2.config(text=f"\u00a3{refunds:,.2f}")
            if hasattr(self, 'core_stat_3'):
                self.core_stat_3.config(text=str(students))
        except Exception as e:
            print(f"Error loading core finance stats: {e}")

    def _process_payment(self):
        """Process a payment"""
        try:
            # Call transaction manager's payment function if available
            if hasattr(self.gui, 'transactions') and hasattr(self.gui.transactions, 'gui_record_payment'):
                self.gui.transactions.gui_record_payment()
            else:
                messagebox.showinfo(_("finance_gui.buttons.process_payment"), _("finance_gui.messages.transaction_manager_unavailable"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("finance_gui.messages.failed_open_payment_dialog", error=str(e)))

    def _create_invoice(self):
        """Create an invoice"""
        try:
            # Call invoice manager if available (check both 'invoices' and 'invoice_manager')
            if hasattr(self.gui, 'invoices') and hasattr(self.gui.invoices, 'gui_generate_invoice'):
                self.gui.invoices.gui_generate_invoice()
            elif hasattr(self.gui, 'invoice_manager') and hasattr(self.gui.invoice_manager, 'gui_generate_invoice'):
                self.gui.invoice_manager.gui_generate_invoice()
            else:
                messagebox.showinfo(_("finance_gui.buttons.create_invoice"), _("finance_gui.messages.invoice_manager_unavailable"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("finance_gui.messages.failed_open_invoice_dialog", error=str(e)))
