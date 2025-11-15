"""
Integration Marketplace GUI

Comprehensive GUI for browsing, installing, and managing third-party integrations.
Includes integration catalog, installation management, credential management,
sync logs, data mappings, webhooks, and usage analytics. Full authentication,
error handling, and email notifications.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog, simpledialog
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import json
import logging
import traceback
import secrets
import hashlib

# Core infrastructure
from university_system.infrastructure.auth.user_authentication import UserAuth
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.infrastructure.database.schemas import init_integration_marketplace_system_db
from university_system.modules.shared.constants import paths
from university_system.modules.shared.utils.activity_logger import log_activity

# Integration managers
try:
    from university_system.modules.shared.services.integrations.integration_marketplace_core import (
        IntegrationCatalogManager,
        InstallationManager,
        CredentialManager,
        SyncManager,
        DataMappingManager,
        WebhookManager
    )
    MANAGERS_AVAILABLE = True
except ImportError:
    MANAGERS_AVAILABLE = False

# Email service
try:
    from university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntegrationMarketplaceGUI:
    """Integration Marketplace Management GUI"""

    def __init__(self, parent: tk.Tk, auth_system: Optional[UserAuth] = None):
        # Create a new Toplevel window instead of modifying the parent
        self.root = tk.Toplevel(parent)
        self.parent = parent
        self.root.title("Integration Marketplace")
        self.root.geometry("1400x900")

        # Initialize authentication
        if auth_system:
            self.auth = auth_system
        else:
            self.auth = UserAuth()

        # Initialize database
        self.init_database()

        # Configure styles
        self.setup_styles()

        # Setup current user
        self.setup_current_user()

        # Check authentication - user must log in through main GUI
        if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
            self.create_main_interface()
        else:
            messagebox.showerror(
                "Authentication Required",
                "Please log in through the main University System GUI before accessing Integration Marketplace."
            )
            self.root.destroy()

    def setup_current_user(self):
        """Setup current user from authentication system"""
        try:
            if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                logger.info(f"Integration Marketplace GUI: Using authenticated user {self.auth.current_user.get('username', 'Unknown')}")
            else:
                logger.info("Integration Marketplace GUI: No authenticated user - will show login screen")
        except Exception as e:
            logger.error(f"Error setting up current user: {e}")

    def init_database(self):
        """Initialize database tables"""
        try:
            init_integration_marketplace_system_db()
            logger.info("Integration Marketplace database tables initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            logger.error(traceback.format_exc())
            messagebox.showerror("Database Error", f"Failed to initialize database: {e}")

    def setup_styles(self):
        """Configure ttk styles to match program standards"""
        style = ttk.Style()

        # Use default theme for consistency
        try:
            style.theme_use('default')
        except:
            pass

        # Standard header styling (consistent with other modules)
        style.configure('Header.TLabel',
                       font=('Arial', 16, 'bold'))

        style.configure('Title.TLabel',
                       font=('Arial', 12, 'bold'))

        style.configure('Section.TLabel',
                       font=('Arial', 11, 'bold'))

        style.configure('Action.TButton',
                       font=('Arial', 10))

        style.configure('Primary.TButton',
                       font=('Arial', 10, 'bold'))

        style.configure('Treeview',
                       font=('Arial', 9),
                       rowheight=25)

        style.configure('Treeview.Heading',
                       font=('Arial', 10, 'bold'))

    def create_main_interface(self):
        """Create the main GUI interface"""
        # Clear existing widgets
        for widget in self.root.winfo_children():
            widget.destroy()

        # Header frame
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill='x', padx=10, pady=(10, 5))

        # Title
        ttk.Label(header_frame, text="Integration Marketplace",
                 style='Header.TLabel').pack(side='left')

        # Return to homepage button
        ttk.Button(header_frame, text="← Return to Main Menu",
                  command=self.return_to_main_menu).pack(side='right', padx=5)

        # User info
        if self.auth.current_user:
            user_info = f"Logged in as: {self.auth.current_user.get('username', 'User')} ({self.auth.current_user.get('role', 'user')})"
            ttk.Label(header_frame, text=user_info,
                     font=('Arial', 10)).pack(side='right', padx=10)

        # Notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)

        # Create tabs
        self.create_catalog_tab()
        self.create_installed_tab()
        self.create_credentials_tab()
        self.create_sync_logs_tab()
        self.create_mappings_tab()
        self.create_webhooks_tab()
        self.create_analytics_tab()

        # Refresh data
        self.refresh_all_data()

    def create_catalog_tab(self):
        """Create integration catalog tab"""
        catalog_frame = ttk.Frame(self.notebook)
        self.notebook.add(catalog_frame, text="Catalog")

        # Controls
        controls_frame = ttk.Frame(catalog_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text="Add Integration",
                  command=self.add_integration, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Refresh",
                  command=self.load_catalog, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Install Selected",
                  command=self.install_integration, style='Primary.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="View Details",
                  command=self.view_integration_details, style='Action.TButton').pack(side='left', padx=5)

        # Category filter
        ttk.Label(controls_frame, text="Category:").pack(side='left', padx=5)
        self.catalog_category_var = tk.StringVar(value='')
        ttk.Combobox(controls_frame, textvariable=self.catalog_category_var,
                    values=['', 'LMS', 'SIS', 'CRM', 'Analytics', 'Communication', 'Storage'],
                    width=12, state='readonly').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Filter",
                  command=self.load_catalog, style='Action.TButton').pack(side='left', padx=5)

        # Catalog tree
        tree_frame = ttk.Frame(catalog_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('integration_id', 'integration_name', 'provider_name', 'category',
                  'integration_type', 'version', 'rating', 'install_count', 'is_official')
        self.catalog_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.catalog_tree.heading(col, text=col.replace('_', ' ').title())
            self.catalog_tree.column(col, width=100)

        self.catalog_tree.column('integration_name', width=200)
        self.catalog_tree.column('provider_name', width=150)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.catalog_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.catalog_tree.xview)
        self.catalog_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.catalog_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Description panel
        desc_frame = ttk.LabelFrame(catalog_frame, text="Description", padding=10)
        desc_frame.pack(fill='x', padx=10, pady=5)

        self.catalog_description = scrolledtext.ScrolledText(desc_frame, height=4, wrap=tk.WORD)
        self.catalog_description.pack(fill='both', expand=True)

        # Bind selection event
        self.catalog_tree.bind('<<TreeviewSelect>>', self.on_catalog_select)

    def create_installed_tab(self):
        """Create installed integrations tab"""
        installed_frame = ttk.Frame(self.notebook)
        self.notebook.add(installed_frame, text="Installed")

        # Controls
        controls_frame = ttk.Frame(installed_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text="Refresh",
                  command=self.load_installed, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Configure",
                  command=self.configure_integration, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Sync Now",
                  command=self.sync_integration, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Uninstall",
                  command=self.uninstall_integration, style='Action.TButton').pack(side='left', padx=5)

        # Status filter
        ttk.Label(controls_frame, text="Status:").pack(side='left', padx=5)
        self.installed_filter_var = tk.StringVar(value='active')
        ttk.Combobox(controls_frame, textvariable=self.installed_filter_var,
                    values=['all', 'active', 'inactive', 'error'],
                    width=10, state='readonly').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Filter",
                  command=self.load_installed, style='Action.TButton').pack(side='left', padx=5)

        # Installed tree
        tree_frame = ttk.Frame(installed_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('install_id', 'integration_name', 'version_installed', 'installation_date',
                  'status', 'last_sync_date', 'sync_frequency', 'is_enabled')
        self.installed_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.installed_tree.heading(col, text=col.replace('_', ' ').title())
            self.installed_tree.column(col, width=120)

        self.installed_tree.column('integration_name', width=200)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.installed_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.installed_tree.xview)
        self.installed_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.installed_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def create_credentials_tab(self):
        """Create credentials management tab"""
        cred_frame = ttk.Frame(self.notebook)
        self.notebook.add(cred_frame, text="Credentials")

        # Controls
        controls_frame = ttk.Frame(cred_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text="Add Credentials",
                  command=self.add_credentials, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Refresh",
                  command=self.load_credentials, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Edit Selected",
                  command=self.edit_credentials, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Delete",
                  command=self.delete_credentials, style='Action.TButton').pack(side='left', padx=5)

        # Credentials tree
        tree_frame = ttk.Frame(cred_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('credential_id', 'install_id', 'credential_type', 'endpoint_url',
                  'created_at', 'token_expiry')
        self.cred_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.cred_tree.heading(col, text=col.replace('_', ' ').title())
            self.cred_tree.column(col, width=120)

        self.cred_tree.column('endpoint_url', width=250)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.cred_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.cred_tree.xview)
        self.cred_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.cred_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def create_sync_logs_tab(self):
        """Create sync logs tab"""
        sync_frame = ttk.Frame(self.notebook)
        self.notebook.add(sync_frame, text="Sync Logs")

        # Controls
        controls_frame = ttk.Frame(sync_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text="Refresh",
                  command=self.load_sync_logs, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="View Details",
                  command=self.view_sync_details, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Export Logs",
                  command=self.export_sync_logs, style='Action.TButton').pack(side='left', padx=5)

        # Status filter
        ttk.Label(controls_frame, text="Status:").pack(side='left', padx=5)
        self.sync_filter_var = tk.StringVar(value='all')
        ttk.Combobox(controls_frame, textvariable=self.sync_filter_var,
                    values=['all', 'success', 'failed', 'running'],
                    width=10, state='readonly').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Filter",
                  command=self.load_sync_logs, style='Action.TButton').pack(side='left', padx=5)

        # Sync logs tree
        tree_frame = ttk.Frame(sync_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('log_id', 'install_id', 'sync_start_time', 'sync_end_time',
                  'sync_status', 'records_synced', 'errors_encountered')
        self.sync_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.sync_tree.heading(col, text=col.replace('_', ' ').title())
            self.sync_tree.column(col, width=120)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.sync_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.sync_tree.xview)
        self.sync_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.sync_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def create_mappings_tab(self):
        """Create data mappings tab"""
        mappings_frame = ttk.Frame(self.notebook)
        self.notebook.add(mappings_frame, text="Data Mappings")

        # Controls
        controls_frame = ttk.Frame(mappings_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text="Add Mapping",
                  command=self.add_mapping, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Refresh",
                  command=self.load_mappings, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Edit Selected",
                  command=self.edit_mapping, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Delete",
                  command=self.delete_mapping, style='Action.TButton').pack(side='left', padx=5)

        # Mappings tree
        tree_frame = ttk.Frame(mappings_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('mapping_id', 'install_id', 'source_field', 'target_field',
                  'transformation_rule', 'is_active')
        self.mappings_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.mappings_tree.heading(col, text=col.replace('_', ' ').title())
            self.mappings_tree.column(col, width=120)

        self.mappings_tree.column('source_field', width=150)
        self.mappings_tree.column('target_field', width=150)
        self.mappings_tree.column('transformation_rule', width=200)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.mappings_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.mappings_tree.xview)
        self.mappings_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.mappings_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def create_webhooks_tab(self):
        """Create webhooks tab"""
        webhooks_frame = ttk.Frame(self.notebook)
        self.notebook.add(webhooks_frame, text="Webhooks")

        # Controls
        controls_frame = ttk.Frame(webhooks_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text="Add Webhook",
                  command=self.add_webhook, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Refresh",
                  command=self.load_webhooks, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Edit Selected",
                  command=self.edit_webhook, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Delete",
                  command=self.delete_webhook, style='Action.TButton').pack(side='left', padx=5)

        # Webhooks tree
        tree_frame = ttk.Frame(webhooks_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('webhook_id', 'install_id', 'webhook_url', 'event_type',
                  'is_active', 'last_triggered_at', 'created_at')
        self.webhooks_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.webhooks_tree.heading(col, text=col.replace('_', ' ').title())
            self.webhooks_tree.column(col, width=120)

        self.webhooks_tree.column('webhook_url', width=300)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.webhooks_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.webhooks_tree.xview)
        self.webhooks_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.webhooks_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    def create_analytics_tab(self):
        """Create usage analytics tab"""
        analytics_frame = ttk.Frame(self.notebook)
        self.notebook.add(analytics_frame, text="Analytics")

        # Controls
        controls_frame = ttk.Frame(analytics_frame)
        controls_frame.pack(fill='x', padx=10, pady=5)

        ttk.Button(controls_frame, text="Refresh",
                  command=self.load_analytics, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="View Summary",
                  command=self.view_analytics_summary, style='Action.TButton').pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Export",
                  command=self.export_analytics, style='Action.TButton').pack(side='left', padx=5)

        # Date filter
        ttk.Label(controls_frame, text="Days:").pack(side='left', padx=5)
        self.analytics_days_var = tk.StringVar(value='30')
        ttk.Spinbox(controls_frame, from_=1, to=365, textvariable=self.analytics_days_var,
                   width=10).pack(side='left', padx=5)
        ttk.Button(controls_frame, text="Filter",
                  command=self.load_analytics, style='Action.TButton').pack(side='left', padx=5)

        # Analytics tree
        tree_frame = ttk.Frame(analytics_frame)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        columns = ('analytics_id', 'install_id', 'metric_name', 'metric_value',
                  'measurement_date')
        self.analytics_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            self.analytics_tree.heading(col, text=col.replace('_', ' ').title())
            self.analytics_tree.column(col, width=150)

        self.analytics_tree.column('metric_name', width=200)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.analytics_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.analytics_tree.xview)
        self.analytics_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.analytics_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

    # Data loading methods
    def refresh_all_data(self):
        """Refresh all tab data"""
        try:
            self.load_catalog()
            self.load_installed()
            self.load_credentials()
            self.load_sync_logs()
            self.load_mappings()
            self.load_webhooks()
            self.load_analytics()
        except Exception as e:
            logger.error(f"Error refreshing data: {e}")
            messagebox.showerror("Error", f"Failed to refresh data: {e}")

    def load_catalog(self):
        """Load integration catalog"""
        try:
            for item in self.catalog_tree.get_children():
                self.catalog_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()

                category = self.catalog_category_var.get()
                if category:
                    cursor.execute('''
                        SELECT integration_id, integration_name, provider_name, category,
                               integration_type, version, rating, install_count, is_official
                        FROM integration_catalog
                        WHERE category = ? AND is_active = 1
                        ORDER BY rating DESC, install_count DESC
                    ''', (category,))
                else:
                    cursor.execute('''
                        SELECT integration_id, integration_name, provider_name, category,
                               integration_type, version, rating, install_count, is_official
                        FROM integration_catalog
                        WHERE is_active = 1
                        ORDER BY rating DESC, install_count DESC
                        LIMIT 100
                    ''')

                integrations = cursor.fetchall()

                for integration in integrations:
                    is_official = 'Yes' if integration[8] else 'No'
                    self.catalog_tree.insert('', 'end', values=(
                        integration[0], integration[1], integration[2], integration[3],
                        integration[4], integration[5], integration[6] or 'N/A',
                        integration[7] or 0, is_official
                    ))

            logger.info(f"Loaded {len(integrations)} integrations from catalog")

        except Exception as e:
            logger.error(f"Error loading catalog: {e}\n{traceback.format_exc()}")
            messagebox.showerror("Error", f"Failed to load catalog: {e}")

    def load_installed(self):
        """Load installed integrations"""
        try:
            for item in self.installed_tree.get_children():
                self.installed_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()

                status_filter = self.installed_filter_var.get()
                if status_filter == 'all':
                    cursor.execute('''
                        SELECT ii.install_id, ic.integration_name, ii.version_installed,
                               ii.installation_date, ii.status, ii.last_sync_date,
                               ii.sync_frequency, ii.is_enabled
                        FROM installed_integrations ii
                        JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                        ORDER BY ii.installation_date DESC
                    ''')
                else:
                    cursor.execute('''
                        SELECT ii.install_id, ic.integration_name, ii.version_installed,
                               ii.installation_date, ii.status, ii.last_sync_date,
                               ii.sync_frequency, ii.is_enabled
                        FROM installed_integrations ii
                        JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                        WHERE ii.status = ?
                        ORDER BY ii.installation_date DESC
                    ''', (status_filter,))

                installed = cursor.fetchall()

                for install in installed:
                    enabled = 'Enabled' if install[7] else 'Disabled'
                    self.installed_tree.insert('', 'end', values=(
                        install[0], install[1], install[2], install[3],
                        install[4], install[5] or 'Never', install[6], enabled
                    ))

            logger.info(f"Loaded {len(installed)} installed integrations")

        except Exception as e:
            logger.error(f"Error loading installed integrations: {e}")
            messagebox.showerror("Error", f"Failed to load installed integrations: {e}")

    def load_credentials(self):
        """Load integration credentials"""
        try:
            for item in self.cred_tree.get_children():
                self.cred_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT credential_id, install_id, credential_type, endpoint_url,
                           created_at, token_expiry
                    FROM integration_credentials
                    ORDER BY created_at DESC
                    LIMIT 100
                ''')

                credentials = cursor.fetchall()

                for cred in credentials:
                    # Properly extract values from sqlite3.Row
                    self.cred_tree.insert('', 'end', values=(
                        cred[0],  # credential_id
                        cred[1],  # install_id
                        cred[2] or 'N/A',  # credential_type
                        cred[3] or 'N/A',  # endpoint_url
                        cred[4][:19] if cred[4] else 'N/A',  # created_at (trim timestamp)
                        cred[5][:19] if cred[5] else 'N/A'   # token_expiry (trim timestamp)
                    ))

            logger.info(f"Loaded {len(credentials)} credentials")

        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
            messagebox.showerror("Error", f"Failed to load credentials: {e}")

    def load_sync_logs(self):
        """Load integration sync logs"""
        try:
            for item in self.sync_tree.get_children():
                self.sync_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()

                status_filter = self.sync_filter_var.get()
                if status_filter == 'all':
                    cursor.execute('''
                        SELECT log_id, install_id, sync_start_time, sync_end_time,
                               sync_status, records_synced, errors_encountered
                        FROM integration_sync_logs
                        ORDER BY sync_start_time DESC
                        LIMIT 100
                    ''')
                else:
                    cursor.execute('''
                        SELECT log_id, install_id, sync_start_time, sync_end_time,
                               sync_status, records_synced, errors_encountered
                        FROM integration_sync_logs
                        WHERE sync_status = ?
                        ORDER BY sync_start_time DESC
                        LIMIT 100
                    ''', (status_filter,))

                logs = cursor.fetchall()

                for log in logs:
                    # Properly extract values from sqlite3.Row
                    self.sync_tree.insert('', 'end', values=(
                        log[0],  # log_id
                        log[1],  # install_id
                        log[2][:19] if log[2] else 'N/A',  # sync_start_time
                        log[3][:19] if log[3] else 'N/A',  # sync_end_time
                        log[4] or 'N/A',  # sync_status
                        log[5] if log[5] is not None else 0,  # records_synced
                        log[6] if log[6] is not None else 0   # errors_encountered
                    ))

            logger.info(f"Loaded {len(logs)} sync logs")

        except Exception as e:
            logger.error(f"Error loading sync logs: {e}")
            messagebox.showerror("Error", f"Failed to load sync logs: {e}")

    def load_mappings(self):
        """Load data mappings"""
        try:
            for item in self.mappings_tree.get_children():
                self.mappings_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT mapping_id, install_id, source_field, target_field,
                           transformation_rule, is_active
                    FROM integration_data_mappings
                    ORDER BY install_id
                    LIMIT 100
                ''')

                mappings = cursor.fetchall()

                for mapping in mappings:
                    status = 'Active' if mapping[5] else 'Inactive'
                    self.mappings_tree.insert('', 'end', values=(
                        mapping[0], mapping[1], mapping[2], mapping[3],
                        mapping[4] or 'None', status
                    ))

            logger.info(f"Loaded {len(mappings)} data mappings")

        except Exception as e:
            logger.error(f"Error loading mappings: {e}")
            messagebox.showerror("Error", f"Failed to load mappings: {e}")

    def load_webhooks(self):
        """Load webhooks"""
        try:
            for item in self.webhooks_tree.get_children():
                self.webhooks_tree.delete(item)

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT webhook_id, install_id, webhook_url, event_type,
                           is_active, last_triggered_at, created_at
                    FROM integration_webhooks
                    ORDER BY created_at DESC
                    LIMIT 100
                ''')

                webhooks = cursor.fetchall()

                for webhook in webhooks:
                    status = 'Active' if webhook[4] else 'Inactive'
                    self.webhooks_tree.insert('', 'end', values=(
                        webhook[0], webhook[1], webhook[2], webhook[3],
                        status, webhook[5] or 'Never', webhook[6]
                    ))

            logger.info(f"Loaded {len(webhooks)} webhooks")

        except Exception as e:
            logger.error(f"Error loading webhooks: {e}")
            messagebox.showerror("Error", f"Failed to load webhooks: {e}")

    def load_analytics(self):
        """Load usage analytics"""
        try:
            for item in self.analytics_tree.get_children():
                self.analytics_tree.delete(item)

            days = int(self.analytics_days_var.get())
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT analytics_id, install_id, metric_name, metric_value,
                           measurement_date
                    FROM integration_usage_analytics
                    WHERE measurement_date >= ?
                    ORDER BY measurement_date DESC
                    LIMIT 100
                ''', (cutoff_date,))

                analytics = cursor.fetchall()

                for item in analytics:
                    self.analytics_tree.insert('', 'end', values=item)

            logger.info(f"Loaded {len(analytics)} analytics records")

        except Exception as e:
            logger.error(f"Error loading analytics: {e}")
            messagebox.showerror("Error", f"Failed to load analytics: {e}")

    # Event handlers
    def on_catalog_select(self, event):
        """Handle catalog tree selection"""
        try:
            selected = self.catalog_tree.selection()
            if not selected:
                return

            integration_id = self.catalog_tree.item(selected[0])['values'][0]

            # Get integration details
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT description FROM integration_catalog
                    WHERE integration_id = ?
                ''', (integration_id,))

                result = cursor.fetchone()
                if result:
                    description = result[0] or "No description available."
                    self.catalog_description.delete('1.0', 'end')
                    self.catalog_description.insert('1.0', description)

        except Exception as e:
            logger.error(f"Error loading integration details: {e}")

    # Action methods
    def add_integration(self):
        """Add new integration to catalog"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Add Integration to Catalog")
            dialog.geometry("500x500")
            dialog.transient(self.root)  # Make dialog transient to parent
            dialog.grab_set()  # Make dialog modal

            # Form fields
            ttk.Label(dialog, text="Integration Name:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            name_var = tk.StringVar()
            name_entry = ttk.Entry(dialog, textvariable=name_var, width=35)
            name_entry.grid(row=0, column=1, padx=10, pady=5)
            name_entry.focus_set()  # Set initial focus

            ttk.Label(dialog, text="Provider Name:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            provider_var = tk.StringVar()
            provider_entry = ttk.Entry(dialog, textvariable=provider_var, width=35)
            provider_entry.grid(row=1, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Integration Type:").grid(row=2, column=0, padx=10, pady=5, sticky='w')
            type_var = tk.StringVar(value='API')
            ttk.Combobox(dialog, textvariable=type_var,
                        values=['API', 'OAuth', 'SAML', 'Database', 'Webhook'],
                        width=33, state='readonly').grid(row=2, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Category:").grid(row=3, column=0, padx=10, pady=5, sticky='w')
            category_var = tk.StringVar(value='LMS')
            ttk.Combobox(dialog, textvariable=category_var,
                        values=['LMS', 'SIS', 'CRM', 'Analytics', 'Communication', 'Storage'],
                        width=33, state='readonly').grid(row=3, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Version:").grid(row=4, column=0, padx=10, pady=5, sticky='w')
            version_var = tk.StringVar(value='1.0.0')
            ttk.Entry(dialog, textvariable=version_var, width=35).grid(row=4, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Description:").grid(row=5, column=0, padx=10, pady=5, sticky='nw')
            description_text = scrolledtext.ScrolledText(dialog, width=35, height=6)
            description_text.grid(row=5, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Official:").grid(row=6, column=0, padx=10, pady=5, sticky='w')
            is_official_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(dialog, variable=is_official_var).grid(row=6, column=1, padx=10, pady=5, sticky='w')

            def save_integration():
                try:
                    integration_name = name_var.get().strip()
                    provider_name = provider_var.get().strip()
                    integration_type = type_var.get()
                    category = category_var.get()
                    version = version_var.get().strip()
                    description = description_text.get('1.0', 'end-1c').strip()
                    is_official = int(is_official_var.get())

                    # Enhanced validation with specific error messages
                    if not integration_name:
                        messagebox.showerror("Validation Error", "Integration Name is required.\n\nPlease enter a name for the integration.")
                        name_entry.focus_set()
                        return

                    if not provider_name:
                        messagebox.showerror("Validation Error", "Provider Name is required.\n\nPlease enter the name of the integration provider.")
                        provider_entry.focus_set()
                        return

                    # Log for debugging
                    logger.info(f"Adding integration: name='{integration_name}', provider='{provider_name}', type='{integration_type}'")

                    if MANAGERS_AVAILABLE:
                        integration_id = IntegrationCatalogManager.add_integration(
                            integration_name, provider_name, integration_type,
                            category, description, version, bool(is_official)
                        )
                    else:
                        with transaction() as conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                INSERT INTO integration_catalog
                                (integration_name, provider_name, integration_type, category,
                                 description, version, is_official, is_active)
                                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                            ''', (integration_name, provider_name, integration_type, category,
                                  description, version, is_official))

                            integration_id = cursor.lastrowid

                    log_activity('create', 'integration_catalog', integration_id,
                                details={'integration_name': integration_name})

                    messagebox.showinfo("Success", f"Integration added successfully!\nIntegration ID: {integration_id}")
                    dialog.destroy()
                    self.load_catalog()

                except Exception as e:
                    logger.error(f"Error adding integration: {e}\n{traceback.format_exc()}")
                    messagebox.showerror("Error", f"Failed to add integration: {e}")

            ttk.Button(dialog, text="Add Integration", command=save_integration).grid(
                row=7, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error(f"Error opening add integration dialog: {e}")
            messagebox.showerror("Error", f"Failed to open dialog: {e}")

    def view_integration_details(self):
        """View detailed integration information"""
        try:
            selected = self.catalog_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select an integration to view details")
                return

            integration_id = self.catalog_tree.item(selected[0])['values'][0]

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT integration_name, provider_name, integration_type, category,
                           description, version, rating, install_count, pricing_model,
                           documentation_url
                    FROM integration_catalog
                    WHERE integration_id = ?
                ''', (integration_id,))

                integration = cursor.fetchone()

            if not integration:
                messagebox.showerror("Error", "Integration not found")
                return

            details = f"Integration Details\n\n"
            details += f"Name: {integration[0]}\n"
            details += f"Provider: {integration[1]}\n"
            details += f"Type: {integration[2]}\n"
            details += f"Category: {integration[3]}\n"
            details += f"Version: {integration[5]}\n"
            details += f"Rating: {integration[6] or 'Not rated'}\n"
            details += f"Installs: {integration[7] or 0}\n"
            details += f"Pricing: {integration[8] or 'Contact provider'}\n"
            details += f"Documentation: {integration[9] or 'N/A'}\n\n"
            details += f"Description:\n{integration[4] or 'No description available.'}"

            messagebox.showinfo("Integration Details", details)

        except Exception as e:
            logger.error(f"Error viewing integration details: {e}")
            messagebox.showerror("Error", f"Failed to view details: {e}")

    def install_integration(self):
        """Install selected integration"""
        try:
            selected = self.catalog_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select an integration to install")
                return

            values = self.catalog_tree.item(selected[0])['values']
            integration_id = values[0]
            integration_name = values[1]

            if messagebox.askyesno("Confirm Installation",
                                  f"Install '{integration_name}'?\n\nThis will add the integration to your system."):
                try:
                    installed_by = self.auth.current_user.get('username', 'Unknown')

                    if MANAGERS_AVAILABLE:
                        install_id = InstallationManager.install_integration(integration_id, installed_by)
                    else:
                        with transaction() as conn:
                            cursor = conn.cursor()

                            # Get version
                            cursor.execute('SELECT version FROM integration_catalog WHERE integration_id = ?',
                                          (integration_id,))
                            version = cursor.fetchone()[0]

                            cursor.execute('''
                                INSERT INTO installed_integrations
                                (integration_id, installed_by, version_installed, status, is_enabled)
                                VALUES (?, ?, ?, 'active', 1)
                            ''', (integration_id, installed_by, version))

                            install_id = cursor.lastrowid

                            # Update install count
                            cursor.execute('''
                                UPDATE integration_catalog
                                SET install_count = install_count + 1
                                WHERE integration_id = ?
                            ''', (integration_id,))

                    log_activity('create', 'installed_integration', install_id,
                                details={'integration_id': integration_id, 'integration_name': integration_name})

                    # Send notification
                    if EMAIL_AVAILABLE:
                        try:
                            send_email(
                                recipient_email=f"{installed_by}@university.edu",
                                subject=f"Integration Installed: {integration_name}",
                                body=f"The integration '{integration_name}' has been successfully installed.\n\n"
                                     f"Installation ID: {install_id}\n"
                                     f"Installed by: {installed_by}\n"
                                     f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                                     f"You can now configure and use this integration."
                            )
                        except Exception as e:
                            logger.warning(f"Failed to send notification: {e}")

                    messagebox.showinfo("Success",
                                      f"Integration installed successfully!\n\n"
                                      f"Installation ID: {install_id}\n\n"
                                      f"Go to the 'Installed' tab to configure it.")

                    self.load_catalog()
                    self.load_installed()

                except Exception as e:
                    logger.error(f"Error installing integration: {e}\n{traceback.format_exc()}")
                    messagebox.showerror("Error", f"Failed to install integration: {e}")

        except Exception as e:
            logger.error(f"Error in install_integration: {e}")
            messagebox.showerror("Error", f"Failed to process installation: {e}")

    def configure_integration(self):
        """Configure selected installed integration"""
        try:
            selected = self.installed_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select an integration to configure")
                return

            install_id = self.installed_tree.item(selected[0])['values'][0]

            # Get current configuration
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT ii.configuration, ii.sync_frequency, ic.integration_name
                    FROM installed_integrations ii
                    JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                    WHERE ii.install_id = ?
                ''', (install_id,))

                result = cursor.fetchone()

            if not result:
                messagebox.showerror("Error", "Installation not found")
                return

            current_config, sync_freq, integration_name = result

            dialog = tk.Toplevel(self.root)
            dialog.title(f"Configure: {integration_name}")
            dialog.geometry("500x400")

            ttk.Label(dialog, text="Sync Frequency:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            sync_freq_var = tk.StringVar(value=sync_freq or 'hourly')
            ttk.Combobox(dialog, textvariable=sync_freq_var,
                        values=['realtime', 'hourly', 'daily', 'weekly', 'manual'],
                        width=33, state='readonly').grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Configuration (JSON):").grid(row=1, column=0, padx=10, pady=5, sticky='nw')
            config_text = scrolledtext.ScrolledText(dialog, width=40, height=15)
            config_text.grid(row=1, column=1, padx=10, pady=5)
            config_text.insert('1.0', current_config or '{}')

            def save_config():
                try:
                    configuration = config_text.get('1.0', 'end-1c').strip()
                    sync_frequency = sync_freq_var.get()

                    # Validate JSON
                    try:
                        json.loads(configuration)
                    except json.JSONDecodeError:
                        messagebox.showerror("Error", "Invalid JSON configuration")
                        return

                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE installed_integrations
                            SET configuration = ?, sync_frequency = ?
                            WHERE install_id = ?
                        ''', (configuration, sync_frequency, install_id))

                    log_activity('update', 'installed_integration', install_id,
                                details={'action': 'configured'})

                    messagebox.showinfo("Success", "Configuration updated successfully")
                    dialog.destroy()
                    self.load_installed()

                except Exception as e:
                    logger.error(f"Error saving configuration: {e}")
                    messagebox.showerror("Error", f"Failed to save configuration: {e}")

            ttk.Button(dialog, text="Save Configuration", command=save_config).grid(
                row=2, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error(f"Error configuring integration: {e}")
            messagebox.showerror("Error", f"Failed to configure integration: {e}")

    def sync_integration(self):
        """Manually trigger sync for selected integration"""
        try:
            selected = self.installed_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select an integration to sync")
                return

            install_id = self.installed_tree.item(selected[0])['values'][0]

            if messagebox.askyesno("Confirm", "Start manual sync for this integration?"):
                # Start sync
                if MANAGERS_AVAILABLE:
                    log_id = SyncManager.start_sync(install_id)
                else:
                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO integration_sync_logs
                            (install_id, sync_status)
                            VALUES (?, 'running')
                        ''', (install_id,))

                        log_id = cursor.lastrowid

                # Simulate sync completion (in real implementation, this would be async)
                import time
                time.sleep(1)

                # Complete sync
                records_synced = 100  # Simulated
                if MANAGERS_AVAILABLE:
                    SyncManager.complete_sync(log_id, 'success', records_synced, 0)
                else:
                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE integration_sync_logs
                            SET sync_end_time = ?, sync_status = ?, records_synced = ?
                            WHERE log_id = ?
                        ''', (datetime.now().isoformat(), 'success', records_synced, log_id))

                        cursor.execute('''
                            UPDATE installed_integrations
                            SET last_sync_date = ?
                            WHERE install_id = ?
                        ''', (datetime.now().isoformat(), install_id))

                log_activity('sync', 'installed_integration', install_id,
                            details={'log_id': log_id, 'records_synced': records_synced})

                messagebox.showinfo("Success", f"Sync completed successfully!\n\nRecords synced: {records_synced}")
                self.load_installed()
                self.load_sync_logs()

        except Exception as e:
            logger.error(f"Error syncing integration: {e}")
            messagebox.showerror("Error", f"Failed to sync integration: {e}")

    def uninstall_integration(self):
        """Uninstall selected integration"""
        try:
            selected = self.installed_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select an integration to uninstall")
                return

            install_id = self.installed_tree.item(selected[0])['values'][0]
            integration_name = self.installed_tree.item(selected[0])['values'][1]

            if messagebox.askyesno("Confirm Uninstall",
                                  f"Uninstall '{integration_name}'?\n\n"
                                  f"This will deactivate the integration and remove its credentials."):
                if MANAGERS_AVAILABLE:
                    InstallationManager.uninstall_integration(install_id)
                else:
                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE installed_integrations
                            SET status = 'uninstalled', is_enabled = 0
                            WHERE install_id = ?
                        ''', (install_id,))

                log_activity('delete', 'installed_integration', install_id,
                            details={'action': 'uninstalled'})

                messagebox.showinfo("Success", "Integration uninstalled successfully")
                self.load_installed()

        except Exception as e:
            logger.error(f"Error uninstalling integration: {e}")
            messagebox.showerror("Error", f"Failed to uninstall integration: {e}")

    def add_credentials(self):
        """Add credentials for integration"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Add Integration Credentials")
            dialog.geometry("500x450")

            ttk.Label(dialog, text="Installation ID:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            install_id_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=install_id_var, width=35).grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Credential Type:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            cred_type_var = tk.StringVar(value='api_key')
            ttk.Combobox(dialog, textvariable=cred_type_var,
                        values=['api_key', 'oauth', 'basic_auth', 'bearer_token'],
                        width=33, state='readonly').grid(row=1, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="API Key:").grid(row=2, column=0, padx=10, pady=5, sticky='w')
            api_key_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=api_key_var, width=35, show='*').grid(row=2, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="API Secret (Optional):").grid(row=3, column=0, padx=10, pady=5, sticky='w')
            api_secret_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=api_secret_var, width=35, show='*').grid(row=3, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Endpoint URL:").grid(row=4, column=0, padx=10, pady=5, sticky='w')
            endpoint_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=endpoint_var, width=35).grid(row=4, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="OAuth Token (Optional):").grid(row=5, column=0, padx=10, pady=5, sticky='w')
            oauth_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=oauth_var, width=35, show='*').grid(row=5, column=1, padx=10, pady=5)

            def save_credentials():
                try:
                    install_id = install_id_var.get().strip()
                    cred_type = cred_type_var.get()
                    api_key = api_key_var.get().strip()
                    api_secret = api_secret_var.get().strip()
                    endpoint = endpoint_var.get().strip()
                    oauth_token = oauth_var.get().strip()

                    if not install_id:
                        messagebox.showerror("Error", "Installation ID is required")
                        return

                    if MANAGERS_AVAILABLE:
                        cred_id = CredentialManager.store_credentials(
                            int(install_id), cred_type, api_key, api_secret,
                            oauth_token, endpoint
                        )
                    else:
                        with transaction() as conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                INSERT INTO integration_credentials
                                (install_id, credential_type, api_key, api_secret,
                                 oauth_token, endpoint_url)
                                VALUES (?, ?, ?, ?, ?, ?)
                            ''', (install_id, cred_type, api_key, api_secret,
                                  oauth_token, endpoint))

                            cred_id = cursor.lastrowid

                    log_activity('create', 'integration_credentials', cred_id,
                                details={'install_id': install_id})

                    messagebox.showinfo("Success", "Credentials saved successfully")
                    dialog.destroy()
                    self.load_credentials()

                except Exception as e:
                    logger.error(f"Error saving credentials: {e}")
                    messagebox.showerror("Error", f"Failed to save credentials: {e}")

            ttk.Button(dialog, text="Save Credentials", command=save_credentials).grid(
                row=6, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error(f"Error opening credentials dialog: {e}")
            messagebox.showerror("Error", f"Failed to open dialog: {e}")

    def edit_credentials(self):
        """Edit selected credentials"""
        try:
            selected = self.cred_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select credentials to edit")
                return

            credential_id = self.cred_tree.item(selected[0])['values'][0]

            # Get current credentials
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT install_id, credential_type, endpoint_url
                    FROM integration_credentials
                    WHERE credential_id = ?
                ''', (credential_id,))

                cred = cursor.fetchone()

            if not cred:
                messagebox.showerror("Error", "Credentials not found")
                return

            dialog = tk.Toplevel(self.root)
            dialog.title("Edit Credentials")
            dialog.geometry("500x350")

            ttk.Label(dialog, text="Credential Type:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            cred_type_var = tk.StringVar(value=cred[1])
            ttk.Combobox(dialog, textvariable=cred_type_var,
                        values=['api_key', 'oauth', 'basic_auth', 'bearer_token'],
                        width=33, state='readonly').grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="New API Key (Optional):").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            api_key_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=api_key_var, width=35, show='*').grid(row=1, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Endpoint URL:").grid(row=2, column=0, padx=10, pady=5, sticky='w')
            endpoint_var = tk.StringVar(value=cred[2] or '')
            ttk.Entry(dialog, textvariable=endpoint_var, width=35).grid(row=2, column=1, padx=10, pady=5)

            def update_credentials():
                try:
                    api_key = api_key_var.get().strip()
                    endpoint = endpoint_var.get().strip()

                    with transaction() as conn:
                        cursor = conn.cursor()

                        # Update only non-empty fields
                        if api_key:
                            cursor.execute('''
                                UPDATE integration_credentials
                                SET credential_type = ?, api_key = ?, endpoint_url = ?
                                WHERE credential_id = ?
                            ''', (cred_type_var.get(), api_key, endpoint, credential_id))
                        else:
                            cursor.execute('''
                                UPDATE integration_credentials
                                SET credential_type = ?, endpoint_url = ?
                                WHERE credential_id = ?
                            ''', (cred_type_var.get(), endpoint, credential_id))

                    log_activity('update', 'integration_credentials', credential_id,
                                details={'action': 'updated'})

                    messagebox.showinfo("Success", "Credentials updated successfully")
                    dialog.destroy()
                    self.load_credentials()

                except Exception as e:
                    logger.error(f"Error updating credentials: {e}")
                    messagebox.showerror("Error", f"Failed to update credentials: {e}")

            ttk.Button(dialog, text="Update Credentials", command=update_credentials).grid(
                row=3, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error(f"Error editing credentials: {e}")
            messagebox.showerror("Error", f"Failed to edit credentials: {e}")

    def delete_credentials(self):
        """Delete selected credentials"""
        try:
            selected = self.cred_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select credentials to delete")
                return

            credential_id = self.cred_tree.item(selected[0])['values'][0]

            if messagebox.askyesno("Confirm Delete", "Delete these credentials?"):
                with transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        DELETE FROM integration_credentials
                        WHERE credential_id = ?
                    ''', (credential_id,))

                log_activity('delete', 'integration_credentials', credential_id,
                            details={'action': 'deleted'})

                messagebox.showinfo("Success", "Credentials deleted successfully")
                self.load_credentials()

        except Exception as e:
            logger.error(f"Error deleting credentials: {e}")
            messagebox.showerror("Error", f"Failed to delete credentials: {e}")

    def view_sync_details(self):
        """View sync log details"""
        try:
            selected = self.sync_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a sync log to view")
                return

            log_id = self.sync_tree.item(selected[0])['values'][0]

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT isl.*, ic.integration_name
                    FROM integration_sync_logs isl
                    JOIN installed_integrations ii ON isl.install_id = ii.install_id
                    JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                    WHERE isl.log_id = ?
                ''', (log_id,))

                log = cursor.fetchone()

            if not log:
                messagebox.showerror("Error", "Sync log not found")
                return

            details = f"Sync Log Details\n\n"
            details += f"Log ID: {log[0]}\n"
            details += f"Integration: {log[8]}\n"
            details += f"Start Time: {log[2]}\n"
            details += f"End Time: {log[3] or 'Still running'}\n"
            details += f"Status: {log[4]}\n"
            details += f"Records Synced: {log[5] or 0}\n"
            details += f"Errors: {log[6] or 0}\n"
            if log[7]:
                details += f"\nError Details:\n{log[7]}"

            messagebox.showinfo("Sync Log Details", details)

        except Exception as e:
            logger.error(f"Error viewing sync details: {e}")
            messagebox.showerror("Error", f"Failed to view sync details: {e}")

    def export_sync_logs(self):
        """Export sync logs to CSV"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )

            if not filename:
                return

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT log_id, install_id, sync_start_time, sync_end_time,
                           sync_status, records_synced, errors_encountered
                    FROM integration_sync_logs
                    ORDER BY sync_start_time DESC
                ''')

                logs = cursor.fetchall()

            import csv
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Log ID', 'Install ID', 'Start Time', 'End Time',
                               'Status', 'Records Synced', 'Errors'])
                writer.writerows(logs)

            messagebox.showinfo("Success", f"Sync logs exported to {filename}")
            log_activity('export', 'integration_sync_logs', None,
                        details={'filename': filename, 'record_count': len(logs)})

        except Exception as e:
            logger.error(f"Error exporting sync logs: {e}")
            messagebox.showerror("Error", f"Failed to export sync logs: {e}")

    def add_mapping(self):
        """Add data mapping"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Add Data Mapping")
            dialog.geometry("500x350")

            ttk.Label(dialog, text="Installation ID:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            install_id_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=install_id_var, width=35).grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Source Field:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            source_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=source_var, width=35).grid(row=1, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Target Field:").grid(row=2, column=0, padx=10, pady=5, sticky='w')
            target_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=target_var, width=35).grid(row=2, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Transformation Rule (Optional):").grid(row=3, column=0, padx=10, pady=5, sticky='nw')
            transform_text = scrolledtext.ScrolledText(dialog, width=35, height=5)
            transform_text.grid(row=3, column=1, padx=10, pady=5)

            def save_mapping():
                try:
                    install_id = install_id_var.get().strip()
                    source_field = source_var.get().strip()
                    target_field = target_var.get().strip()
                    transformation = transform_text.get('1.0', 'end-1c').strip()

                    if not install_id or not source_field or not target_field:
                        messagebox.showerror("Error", "Installation ID, source field, and target field are required")
                        return

                    if MANAGERS_AVAILABLE:
                        mapping_id = DataMappingManager.create_mapping(
                            int(install_id), source_field, target_field, transformation
                        )
                    else:
                        with transaction() as conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                INSERT INTO integration_data_mappings
                                (install_id, source_field, target_field, transformation_rule, is_active)
                                VALUES (?, ?, ?, ?, 1)
                            ''', (install_id, source_field, target_field, transformation))

                            mapping_id = cursor.lastrowid

                    log_activity('create', 'integration_data_mapping', mapping_id,
                                details={'install_id': install_id})

                    messagebox.showinfo("Success", "Data mapping created successfully")
                    dialog.destroy()
                    self.load_mappings()

                except Exception as e:
                    logger.error(f"Error creating mapping: {e}")
                    messagebox.showerror("Error", f"Failed to create mapping: {e}")

            ttk.Button(dialog, text="Create Mapping", command=save_mapping).grid(
                row=4, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error(f"Error opening mapping dialog: {e}")
            messagebox.showerror("Error", f"Failed to open dialog: {e}")

    def edit_mapping(self):
        """Edit selected mapping"""
        try:
            selected = self.mappings_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a mapping to edit")
                return

            mapping_id = self.mappings_tree.item(selected[0])['values'][0]

            # Fetch current mapping data
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT install_id, source_field, target_field, transformation_rule, is_active
                    FROM integration_data_mappings
                    WHERE mapping_id = ?
                ''', (mapping_id,))
                current_data = cursor.fetchone()

            if not current_data:
                messagebox.showerror("Error", "Mapping not found")
                return

            # Create edit dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Edit Data Mapping")
            dialog.geometry("500x400")

            ttk.Label(dialog, text="Installation ID:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            install_id_var = tk.StringVar(value=str(current_data[0]))
            ttk.Entry(dialog, textvariable=install_id_var, width=35).grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Source Field:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            source_var = tk.StringVar(value=current_data[1] or '')
            ttk.Entry(dialog, textvariable=source_var, width=35).grid(row=1, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Target Field:").grid(row=2, column=0, padx=10, pady=5, sticky='w')
            target_var = tk.StringVar(value=current_data[2] or '')
            ttk.Entry(dialog, textvariable=target_var, width=35).grid(row=2, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Transformation Rule (Optional):").grid(row=3, column=0, padx=10, pady=5, sticky='nw')
            transform_text = scrolledtext.ScrolledText(dialog, width=35, height=5)
            transform_text.grid(row=3, column=1, padx=10, pady=5)
            if current_data[3]:
                transform_text.insert('1.0', current_data[3])

            ttk.Label(dialog, text="Status:").grid(row=4, column=0, padx=10, pady=5, sticky='w')
            is_active_var = tk.BooleanVar(value=bool(current_data[4]))
            ttk.Checkbutton(dialog, text="Active", variable=is_active_var).grid(row=4, column=1, padx=10, pady=5, sticky='w')

            def save_changes():
                try:
                    install_id = install_id_var.get().strip()
                    source_field = source_var.get().strip()
                    target_field = target_var.get().strip()
                    transformation = transform_text.get('1.0', 'end-1c').strip()
                    is_active = 1 if is_active_var.get() else 0

                    if not install_id or not source_field or not target_field:
                        messagebox.showerror("Error", "Installation ID, source field, and target field are required")
                        return

                    if MANAGERS_AVAILABLE:
                        DataMappingManager.update_mapping(
                            mapping_id, int(install_id), source_field, target_field,
                            transformation, is_active
                        )
                    else:
                        with transaction() as conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                UPDATE integration_data_mappings
                                SET install_id = ?, source_field = ?, target_field = ?,
                                    transformation_rule = ?, is_active = ?
                                WHERE mapping_id = ?
                            ''', (install_id, source_field, target_field, transformation, is_active, mapping_id))

                    log_activity('update', 'integration_data_mapping', mapping_id,
                                details={'install_id': install_id, 'is_active': is_active})

                    messagebox.showinfo("Success", "Data mapping updated successfully")
                    dialog.destroy()
                    self.load_mappings()

                except Exception as e:
                    logger.error(f"Error updating mapping: {e}")
                    messagebox.showerror("Error", f"Failed to update mapping: {e}")

            button_frame = ttk.Frame(dialog)
            button_frame.grid(row=5, column=0, columnspan=2, pady=20)

            ttk.Button(button_frame, text="Save Changes", command=save_changes).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

        except Exception as e:
            logger.error(f"Error opening edit mapping dialog: {e}")
            messagebox.showerror("Error", f"Failed to open edit dialog: {e}")

    def delete_mapping(self):
        """Delete selected mapping"""
        try:
            selected = self.mappings_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a mapping to delete")
                return

            mapping_id = self.mappings_tree.item(selected[0])['values'][0]

            if messagebox.askyesno("Confirm Delete", "Delete this data mapping?"):
                with transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM integration_data_mappings WHERE mapping_id = ?',
                                  (mapping_id,))

                log_activity('delete', 'integration_data_mapping', mapping_id,
                            details={'action': 'deleted'})

                messagebox.showinfo("Success", "Data mapping deleted successfully")
                self.load_mappings()

        except Exception as e:
            logger.error(f"Error deleting mapping: {e}")
            messagebox.showerror("Error", f"Failed to delete mapping: {e}")

    def add_webhook(self):
        """Add webhook"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Add Webhook")
            dialog.geometry("500x300")

            ttk.Label(dialog, text="Installation ID:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            install_id_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=install_id_var, width=35).grid(row=0, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Webhook URL:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            url_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=url_var, width=35).grid(row=1, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Event Type:").grid(row=2, column=0, padx=10, pady=5, sticky='w')
            event_var = tk.StringVar(value='data_update')
            ttk.Combobox(dialog, textvariable=event_var,
                        values=['data_update', 'sync_complete', 'error', 'status_change'],
                        width=33, state='readonly').grid(row=2, column=1, padx=10, pady=5)

            ttk.Label(dialog, text="Secret Key (Optional):").grid(row=3, column=0, padx=10, pady=5, sticky='w')
            secret_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=secret_var, width=35, show='*').grid(row=3, column=1, padx=10, pady=5)

            def save_webhook():
                try:
                    install_id = install_id_var.get().strip()
                    webhook_url = url_var.get().strip()
                    event_type = event_var.get()
                    secret_key = secret_var.get().strip()

                    if not install_id or not webhook_url:
                        messagebox.showerror("Error", "Installation ID and webhook URL are required")
                        return

                    if MANAGERS_AVAILABLE:
                        webhook_id = WebhookManager.register_webhook(
                            int(install_id), webhook_url, event_type, secret_key
                        )
                    else:
                        with transaction() as conn:
                            cursor = conn.cursor()
                            cursor.execute('''
                                INSERT INTO integration_webhooks
                                (install_id, webhook_url, event_type, secret_key, is_active)
                                VALUES (?, ?, ?, ?, 1)
                            ''', (install_id, webhook_url, event_type, secret_key))

                            webhook_id = cursor.lastrowid

                    log_activity('create', 'integration_webhook', webhook_id,
                                details={'install_id': install_id})

                    messagebox.showinfo("Success", "Webhook registered successfully")
                    dialog.destroy()
                    self.load_webhooks()

                except Exception as e:
                    logger.error(f"Error registering webhook: {e}")
                    messagebox.showerror("Error", f"Failed to register webhook: {e}")

            ttk.Button(dialog, text="Register Webhook", command=save_webhook).grid(
                row=4, column=0, columnspan=2, pady=20)

        except Exception as e:
            logger.error(f"Error opening webhook dialog: {e}")
            messagebox.showerror("Error", f"Failed to open dialog: {e}")

    def edit_webhook(self):
        """Edit selected webhook"""
        messagebox.showinfo("Edit Webhook", "Edit webhook functionality - similar to add_webhook")

    def delete_webhook(self):
        """Delete selected webhook"""
        try:
            selected = self.webhooks_tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a webhook to delete")
                return

            webhook_id = self.webhooks_tree.item(selected[0])['values'][0]

            if messagebox.askyesno("Confirm Delete", "Delete this webhook?"):
                with transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM integration_webhooks WHERE webhook_id = ?',
                                  (webhook_id,))

                log_activity('delete', 'integration_webhook', webhook_id,
                            details={'action': 'deleted'})

                messagebox.showinfo("Success", "Webhook deleted successfully")
                self.load_webhooks()

        except Exception as e:
            logger.error(f"Error deleting webhook: {e}")
            messagebox.showerror("Error", f"Failed to delete webhook: {e}")

    def view_analytics_summary(self):
        """View analytics summary"""
        try:
            days = int(self.analytics_days_var.get())
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            with get_connection() as conn:
                cursor = conn.cursor()

                # Total metrics
                cursor.execute('''
                    SELECT COUNT(*) FROM integration_usage_analytics
                    WHERE measurement_date >= ?
                ''', (cutoff_date,))
                total_metrics = cursor.fetchone()[0]

                # Average metric value
                cursor.execute('''
                    SELECT AVG(metric_value) FROM integration_usage_analytics
                    WHERE measurement_date >= ?
                ''', (cutoff_date,))
                avg_value = cursor.fetchone()[0] or 0

                # Most tracked metric
                cursor.execute('''
                    SELECT metric_name, COUNT(*) as count
                    FROM integration_usage_analytics
                    WHERE measurement_date >= ?
                    GROUP BY metric_name
                    ORDER BY count DESC
                    LIMIT 1
                ''', (cutoff_date,))
                top_metric = cursor.fetchone()

            summary = f"Analytics Summary (Last {days} Days)\n\n"
            summary += f"Total Metrics Recorded: {total_metrics}\n"
            summary += f"Average Metric Value: {avg_value:.2f}\n"
            if top_metric:
                summary += f"Most Tracked Metric: {top_metric[0]} ({top_metric[1]} times)"

            messagebox.showinfo("Analytics Summary", summary)

        except Exception as e:
            logger.error(f"Error viewing analytics summary: {e}")
            messagebox.showerror("Error", f"Failed to view analytics summary: {e}")

    def export_analytics(self):
        """Export analytics to CSV"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )

            if not filename:
                return

            days = int(self.analytics_days_var.get())
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT analytics_id, install_id, metric_name, metric_value, measurement_date
                    FROM integration_usage_analytics
                    WHERE measurement_date >= ?
                    ORDER BY measurement_date DESC
                ''', (cutoff_date,))

                analytics = cursor.fetchall()

            import csv
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Analytics ID', 'Install ID', 'Metric Name',
                               'Metric Value', 'Measurement Date'])
                writer.writerows(analytics)

            messagebox.showinfo("Success", f"Analytics exported to {filename}")
            log_activity('export', 'integration_usage_analytics', None,
                        details={'filename': filename, 'record_count': len(analytics)})

        except Exception as e:
            logger.error(f"Error exporting analytics: {e}")
            messagebox.showerror("Error", f"Failed to export analytics: {e}")

    def return_to_main_menu(self):
        """Return to main menu by closing the marketplace window"""
        if messagebox.askyesno("Confirm", "Return to main menu?"):
            try:
                # Log the action
                if self.auth and self.auth.current_user:
                    log_activity('Closed Integration Marketplace',
                               user=self.auth.current_user.get('username', 'Unknown'))

                # Close the window
                self.root.destroy()
                logger.info("Integration Marketplace closed")
            except Exception as e:
                logger.error(f"Error closing Integration Marketplace: {e}")
                self.root.destroy()


def launch_integration_marketplace_gui(auth=None, parent=None):
    """Launch the Integration Marketplace GUI as a child window"""
    try:
        if parent:
            # Create as Toplevel (child window) if parent exists
            root = tk.Toplevel(parent)
        else:
            # Create as standalone root window if no parent (for testing)
            root = tk.Tk()
        app = IntegrationMarketplaceGUI(root, auth_system=auth)
        # Don't call mainloop() for Toplevel windows - parent handles it
        if not parent:
            root.mainloop()
    except Exception as e:
        logger.error(f"Error launching Integration Marketplace GUI: {e}\n{traceback.format_exc()}")
        raise


if __name__ == "__main__":
    launch_integration_marketplace_gui()
