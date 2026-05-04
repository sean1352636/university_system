"""Core IntegrationMarketplaceGUI class with initialization and main interface."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
import logging
import traceback

from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.infrastructure.database.schemas.research_integration_schemas import init_integration_marketplace_system_db
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
    get_current_language_name,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
)

from education_system.university_system.modules.services.gui.integration_marketplace_gui.tabs import TabsMixin
from education_system.university_system.modules.services.gui.integration_marketplace_gui.data_loading import DataLoadingMixin
from education_system.university_system.modules.services.gui.integration_marketplace_gui.catalog import CatalogMixin
from education_system.university_system.modules.services.gui.integration_marketplace_gui.installed import InstalledMixin
from education_system.university_system.modules.services.gui.integration_marketplace_gui.credentials import CredentialsMixin
from education_system.university_system.modules.services.gui.integration_marketplace_gui.sync_and_mappings import SyncAndMappingsMixin
from education_system.university_system.modules.services.gui.integration_marketplace_gui.search import SearchMixin
from education_system.university_system.modules.services.gui.integration_marketplace_gui.bulk_operations import BulkOperationsMixin
from education_system.university_system.modules.services.gui.integration_marketplace_gui.import_export import ImportExportMixin
from education_system.university_system.modules.services.gui.integration_marketplace_gui.analytics import AnalyticsMixin
from education_system.university_system.modules.services.gui.integration_marketplace_gui.scheduling import SchedulingMixin
from education_system.university_system.modules.services.gui.integration_marketplace_gui.testing import TestingMixin
from education_system.university_system.modules.services.gui.integration_marketplace_gui.mapping_tools import MappingToolsMixin
from education_system.university_system.modules.services.gui.integration_marketplace_gui.notifications import NotificationsMixin

logger = logging.getLogger(__name__)


class IntegrationMarketplaceGUI(
    TabsMixin,
    DataLoadingMixin,
    CatalogMixin,
    InstalledMixin,
    CredentialsMixin,
    SyncAndMappingsMixin,
    SearchMixin,
    BulkOperationsMixin,
    ImportExportMixin,
    AnalyticsMixin,
    SchedulingMixin,
    TestingMixin,
    MappingToolsMixin,
    NotificationsMixin,
):
    """Integration Marketplace Management GUI"""

    def __init__(self, parent: tk.Tk, auth_system: Optional[UserAuth] = None):
        # Create a new Toplevel window instead of modifying the parent
        self.root = tk.Toplevel(parent)
        self.parent = parent

        # Initialize i18n
        init_i18n()

        self.root.title(_t("integration_marketplace.window_title"))
        self.root.geometry("1400x900")

        # Initialize authentication
        if auth_system:
            self.auth = auth_system
        else:
            # Use centralized auth system
            self.auth = get_auth()
            if self.auth is None:
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
                _t("integration_marketplace.auth.required_title"),
                _t("integration_marketplace.auth.required_message")
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
            messagebox.showerror(_t("integration_marketplace.errors.database_error"), f"{_t('integration_marketplace.errors.init_failed')}: {e}")

    def setup_styles(self):
        """Configure ttk styles to match main_gui.py standards"""
        style = ttk.Style()

        # Header styling (matching main_gui.py)
        style.configure('Header.TLabel',
                       font=('Arial', 18, 'bold'))

        style.configure('Title.TLabel',
                       font=('Arial', 14, 'bold'))

        style.configure('Section.TLabel',
                       font=('Arial', 12, 'bold'))

        style.configure('Info.TLabel',
                       font=('Arial', 11))

        # Button styles matching main_gui.py
        style.configure('TButton',
                       font=('Arial', 10))

        style.configure('Accent.TButton',
                       font=('Arial', 10, 'bold'))

        # Treeview styling
        style.configure('Treeview',
                       font=('Arial', 10),
                       rowheight=25)

        style.configure('Treeview.Heading',
                       font=('Arial', 10, 'bold'))

        # LabelFrame styling
        style.configure('TLabelframe.Label',
                       font=('Arial', 11, 'bold'))

    def create_main_interface(self):
        """Create the main GUI interface"""
        # Clear existing widgets
        for widget in self.root.winfo_children():
            widget.destroy()

        # Main container frame with padding (matching main_gui.py)
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill='both', expand=True)

        # Header frame with LabelFrame style (matching main_gui.py)
        header_frame = ttk.LabelFrame(main_frame, text=_t("integration_marketplace.title"), padding="10")
        header_frame.pack(fill='x', pady=(0, 10))

        # Control buttons row
        button_frame = ttk.Frame(header_frame)
        button_frame.pack(fill='x', pady=(0, 10))

        # Return to homepage button
        ttk.Button(button_frame, text=_t("integration_marketplace.buttons.return_main"),
                  command=self.return_to_main_menu,
                  style='Accent.TButton').pack(side='left', padx=(0, 10))

        # Refresh all button
        ttk.Button(button_frame, text=_t("integration_marketplace.buttons.refresh_all"),
                  command=self.refresh_all_data).pack(side='left', padx=(0, 10))

        # Language selector button
        ttk.Button(button_frame, text=f"\U0001f310 {get_current_language_name()}",
                  command=self._on_language_change).pack(side='left', padx=(0, 10))

        # Status row
        status_frame = ttk.Frame(header_frame)
        status_frame.pack(fill='x')

        ttk.Label(status_frame, text=_t("integration_marketplace.status.label"), font=('Arial', 10, 'bold')).pack(side='left')
        ttk.Label(status_frame, text=_t("integration_marketplace.status.connected"), font=('Arial', 10)).pack(side='left', padx=(10, 20))

        # User info
        if self.auth.current_user:
            ttk.Label(status_frame, text=_t("integration_marketplace.status.current_user"), font=('Arial', 10, 'bold')).pack(side='left')
            user_info = f"{self.auth.current_user.get('username', 'User')} ({self.auth.current_user.get('role', 'user')})"
            ttk.Label(status_frame, text=user_info, font=('Arial', 10)).pack(side='left', padx=(10, 0))

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill='both', expand=True)

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

    def _on_language_change(self):
        """Handle language change request"""
        old_lang = get_current_language()
        show_gui_language_selector(self.root)
        new_lang = get_current_language()
        if old_lang != new_lang:
            messagebox.showinfo(
                _t("integration_marketplace.language.changed_title"),
                _t("integration_marketplace.language.changed_message")
            )
            self._refresh_ui_language()

    def _refresh_ui_language(self):
        """Refresh all UI elements with current language"""
        # Reinitialize i18n to ensure new translations are loaded
        init_i18n(get_current_language())
        # Update window title
        self.root.title(_t("integration_marketplace.window_title"))
        # Recreate the main interface with new language
        self.create_main_interface()

    def return_to_main_menu(self):
        """Return to main menu by closing the marketplace window"""
        if messagebox.askyesno(_t("integration_marketplace.dialogs.confirm"), _t("integration_marketplace.dialogs.return_confirm")):
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
