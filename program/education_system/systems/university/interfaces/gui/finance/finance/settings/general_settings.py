"""General settings tab and persistence."""

import json
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from pathlib import Path

from education_system.systems.university.infrastructure.i18n import get_text as _


class GeneralSettingsMixin:
    """Settings tab creation and general preference persistence."""

    def create_settings_tab(self):
        """Create settings and configuration tab"""
        settings_frame = tk.Frame(self.gui.layout.content_frame, bg='white')
        self.gui.layout.tab_frames['settings'] = settings_frame

        # Settings main frame
        main_frame = tk.Frame(settings_frame, bg='white')
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Title
        tk.Label(main_frame, text=_("finance_gui.settings.system_settings_title"), font=('Arial', 18, 'bold'), bg='white').pack(pady=10)

        # Settings notebook
        settings_notebook = ttk.Notebook(main_frame)
        settings_notebook.pack(fill='both', expand=True, pady=10)

        # General settings
        general_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(general_frame, text=_("finance_gui.settings.general_tab"))
        self.create_general_settings(general_frame)

        # Currency settings
        currency_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(currency_frame, text=_("finance_gui.settings.currency_tab"))
        self.create_currency_settings(currency_frame)

        # Notification settings
        notification_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(notification_frame, text=_("finance_gui.settings.notifications_tab"))
        self.create_notification_settings(notification_frame)

        # System maintenance
        maintenance_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(maintenance_frame, text=_("finance_gui.settings.maintenance_tab"))
        self.create_maintenance_settings(maintenance_frame)


    def create_general_settings(self, parent):
        """Create general settings interface"""
        # Academic year setting
        year_frame = tk.LabelFrame(parent, text=_("finance_gui.settings.academic_year_frame"), font=('Arial', 10, 'bold'))
        year_frame.pack(fill='x', padx=10, pady=10)

        tk.Label(year_frame, text=_("finance_gui.settings.current_academic_year")).grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.academic_year_var = tk.StringVar(value="2024-2025")
        tk.Entry(year_frame, textvariable=self.academic_year_var, width=15).grid(row=0, column=1, padx=5, pady=5)

        # Default settings
        defaults_frame = tk.LabelFrame(parent, text=_("finance_gui.settings.default_values_frame"), font=('Arial', 10, 'bold'))
        defaults_frame.pack(fill='x', padx=10, pady=10)

        tk.Label(defaults_frame, text=_("finance_gui.settings.grace_period_label")).grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.grace_period_var = tk.StringVar(value="7")
        tk.Entry(defaults_frame, textvariable=self.grace_period_var, width=10).grid(row=0, column=1, padx=5, pady=5)

        tk.Label(defaults_frame, text=_("finance_gui.settings.late_fee_amount_label")).grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.late_fee_var = tk.StringVar(value="50.00")
        tk.Entry(defaults_frame, textvariable=self.late_fee_var, width=10).grid(row=1, column=1, padx=5, pady=5)

        # Save button
        tk.Button(defaults_frame, text=_("finance_gui.settings.btn_save_settings"), command=self.save_general_settings,
                 bg=self.gui.layout.colors['success'], fg='white').grid(row=2, column=0, columnspan=2, pady=10)


    def save_general_settings(self):
        """Persist general finance settings for reuse."""
        settings = {
            'academic_year': self.academic_year_var.get().strip(),
            'grace_period_days': self.grace_period_var.get().strip(),
            'default_late_fee': self.late_fee_var.get().strip(),
            'updated_at': datetime.now().isoformat(),
        }

        settings_path = Path(__file__).resolve().parent.parent / 'finance_general_settings.json'

        try:
            with settings_path.open('w', encoding='utf-8') as fp:
                json.dump(settings, fp, indent=2)

            if hasattr(self.gui, 'layout') and hasattr(self.gui.layout, 'update_status'):
                self.gui.layout.update_status(_("finance_gui.settings.settings_saved"))
            messagebox.showinfo(_("finance_gui.settings.settings_saved_title"), _("finance_gui.settings.settings_saved_message"))
        except Exception as exc:
            if hasattr(self.gui, 'layout') and hasattr(self.gui.layout, 'update_status'):
                self.gui.layout.update_status(_("finance_gui.settings.failed_save_settings"))
            messagebox.showerror(_("finance_gui.settings.save_error_title"), _("finance_gui.settings.save_error_message", error=str(exc)))


    def create_currency_settings(self, parent):
        """Create currency settings interface"""
        # Base currency
        base_frame = tk.LabelFrame(parent, text=_("finance_gui.settings.base_currency_frame"), font=('Arial', 10, 'bold'))
        base_frame.pack(fill='x', padx=10, pady=10)

        tk.Label(base_frame, text=_("finance_gui.settings.base_currency_label")).grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.base_currency_var = tk.StringVar(value="GBP")
        currency_combo = ttk.Combobox(base_frame, textvariable=self.base_currency_var,
                                     values=['GBP', 'USD', 'EUR', 'CAD', 'AUD'])
        currency_combo.grid(row=0, column=1, padx=5, pady=5)

        # Exchange rates
        rates_frame = tk.LabelFrame(parent, text=_("finance_gui.settings.exchange_rates_frame"), font=('Arial', 10, 'bold'))
        rates_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Exchange rates table
        self.exchange_rates_tree = ttk.Treeview(rates_frame,
                                              columns=('from_curr', 'to_curr', 'rate', 'date'),
                                              show='headings')
        for col in self.exchange_rates_tree['columns']:
            self.exchange_rates_tree.heading(col, text=col.replace('_', ' ').title())
        self.exchange_rates_tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Update rates button
        tk.Button(rates_frame, text=_("finance_gui.settings.btn_update_rates"), command=self.gui_update_exchange_rates,
                 bg=self.gui.layout.colors['secondary'], fg='white').pack(pady=5)


    def create_notification_settings(self, parent):
        """Create notification settings interface"""
        # Email settings
        email_frame = tk.LabelFrame(parent, text=_("finance_gui.settings.email_settings_frame"), font=('Arial', 10, 'bold'))
        email_frame.pack(fill='x', padx=10, pady=10)

        tk.Label(email_frame, text=_("finance_gui.settings.smtp_server_label")).grid(row=0, column=0, sticky='w', padx=5, pady=2)
        self.smtp_server_var = tk.StringVar()
        tk.Entry(email_frame, textvariable=self.smtp_server_var, width=30).grid(row=0, column=1, padx=5, pady=2)

        tk.Label(email_frame, text=_("finance_gui.settings.smtp_port_label")).grid(row=1, column=0, sticky='w', padx=5, pady=2)
        self.smtp_port_var = tk.StringVar(value="587")
        tk.Entry(email_frame, textvariable=self.smtp_port_var, width=10).grid(row=1, column=1, padx=5, pady=2)

        tk.Button(email_frame, text=_("finance_gui.settings.btn_test_email"), command=self.gui_test_email_service,
                 bg=self.gui.layout.colors['warning'], fg='white').grid(row=2, column=0, columnspan=2, pady=5)

        # Notification templates
        templates_frame = tk.LabelFrame(parent, text=_("finance_gui.settings.notification_templates_frame"), font=('Arial', 10, 'bold'))
        templates_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.templates_tree = ttk.Treeview(templates_frame,
                                         columns=('template_id', 'name', 'type', 'active'),
                                         show='headings')
        for col in self.templates_tree['columns']:
            self.templates_tree.heading(col, text=col.replace('_', ' ').title())
        self.templates_tree.pack(fill='both', expand=True, padx=5, pady=5)


    def create_maintenance_settings(self, parent):
        """Create system maintenance interface"""
        # Database maintenance
        db_frame = tk.LabelFrame(parent, text=_("finance_gui.settings.db_maintenance_frame"), font=('Arial', 10, 'bold'))
        db_frame.pack(fill='x', padx=10, pady=10)

        tk.Button(db_frame, text=_("finance_gui.settings.btn_init_db"), command=self.initialize_database,
                 bg=self.gui.layout.colors['secondary'], fg='white', width=20).pack(pady=5)
        tk.Button(db_frame, text=_("finance_gui.settings.btn_clean_db"), command=self.clean_database,
                 bg=self.gui.layout.colors['warning'], fg='white', width=20).pack(pady=5)
        tk.Button(db_frame, text=_("finance_gui.settings.btn_backup_db"), command=self.backup_database,
                 bg=self.gui.layout.colors['success'], fg='white', width=20).pack(pady=5)
        tk.Button(db_frame, text=_("finance_gui.settings.btn_db_stats"), command=self.show_database_stats,
                 bg=self.gui.layout.colors['dark'], fg='white', width=20).pack(pady=5)

        # System information
        info_frame = tk.LabelFrame(parent, text=_("finance_gui.settings.system_info_frame"), font=('Arial', 10, 'bold'))
        info_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.system_info_text = ScrolledText(info_frame, height=10, font=('Courier', 9))
        self.system_info_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Load system info
        self.load_system_info()


# Needed for create_maintenance_settings
from tkinter.scrolledtext import ScrolledText  # noqa: E402
