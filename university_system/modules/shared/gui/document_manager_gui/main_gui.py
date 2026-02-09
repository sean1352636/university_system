from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from university_system.infrastructure.database.db import sqlite3
import os
import datetime
from datetime import datetime, timedelta
import shutil
import csv
import json
import hashlib
import zipfile
import threading
import time
import logging
from PIL import Image, ImageTk
import webbrowser
from university_system.modules.shared.constants import paths
from university_system.infrastructure.security.file_upload import (
    get_upload_handler,
    validate_upload,
    save_upload,
    secure_filename,
)

logger = logging.getLogger(__name__)

# Import internationalization (i18n) for multi-language support
try:
    from university_system.modules.shared.utils.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")
    get_current_language = lambda: "en"

# Import the original classes to maintain backwards compatibility
try:
    from university_system.infrastructure.database.db import DatabaseManager, get_connection
    from university_system.infrastructure.auth import UserAuth, get_current_user
except ImportError:
    # Fallback for backwards compatibility
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

    def get_current_user():
        return {'username': 'admin', 'role': 'admin'}

# Import all managers
from university_system.modules.shared.gui.document_manager_gui.database import DatabaseManager as DBManager
from university_system.modules.shared.gui.document_manager_gui.layout import LayoutManager
from university_system.modules.shared.gui.document_manager_gui.helpers import HelperManager
from university_system.modules.shared.gui.document_manager_gui.dashboard import DashboardManager
from university_system.modules.shared.gui.document_manager_gui.documents import DocumentsManager
from university_system.modules.shared.gui.document_manager_gui.students import StudentsManager
from university_system.modules.shared.gui.document_manager_gui.workflows import WorkflowManager
from university_system.modules.shared.gui.document_manager_gui.document_types import DocumentTypeManager
from university_system.modules.shared.gui.document_manager_gui.notifications import NotificationManager
from university_system.modules.shared.gui.document_manager_gui.reports import ReportsManager
from university_system.modules.shared.gui.document_manager_gui.search import SearchManager
from university_system.modules.shared.gui.document_manager_gui.bulk_operations import BulkOperationsManager
from university_system.modules.shared.gui.document_manager_gui.versions import VersionManager
from university_system.modules.shared.gui.document_manager_gui.ocr import OCRManager
from university_system.modules.shared.gui.document_manager_gui.settings import SettingsManager
from university_system.modules.shared.gui.document_manager_gui.users import UserManager
from university_system.modules.shared.gui.document_manager_gui.backup import BackupManager
from university_system.modules.shared.gui.document_manager_gui.exports import ExportManager
from university_system.modules.shared.gui.document_manager_gui.imports import ImportManager
from university_system.modules.shared.gui.document_manager_gui.api_web import APIWebManager
from university_system.modules.shared.gui.document_manager_gui.expiry import ExpiryManager
from university_system.modules.shared.gui.document_manager_gui.student_portal import StudentPortalManager
from university_system.modules.shared.gui.document_manager_gui.menus import MenuManager


class DocumentManagerGUI:
    def __init__(self, root, auth=None):
        self.root = root
        self.root.title(_t("docmanager.window_title", default="Enhanced Document Management System"))
        self.root.geometry("1400x900")
        self.root.configure(bg='#f0f0f0')

        # Store auth instance for return_to_main_menu
        self.auth = auth

        # Initialize variables first
        self.activity_tree = None
        self.docs_tree = None
        self.students_tree = None

        # Manager list for __getattr__ lookup (populated after instantiation)
        self._managers = []

        # Instantiate all managers
        self.db = DBManager(self)
        self.layout = LayoutManager(self)
        self.helpers = HelperManager(self)
        self.dashboard_mgr = DashboardManager(self)
        self.documents = DocumentsManager(self)
        self.students_mgr = StudentsManager(self)
        self.workflows = WorkflowManager(self)
        self.document_types = DocumentTypeManager(self)
        self.notifications_mgr = NotificationManager(self)
        self.reports = ReportsManager(self)
        self.search = SearchManager(self)
        self.bulk_operations = BulkOperationsManager(self)
        self.versions = VersionManager(self)
        self.ocr = OCRManager(self)
        self.settings_mgr = SettingsManager(self)
        self.users = UserManager(self)
        self.backup = BackupManager(self)
        self.exports = ExportManager(self)
        self.imports = ImportManager(self)
        self.api_web = APIWebManager(self)
        self.expiry = ExpiryManager(self)
        self.student_portal = StudentPortalManager(self)
        self.menus = MenuManager(self)

        # Register all managers for __getattr__ delegation
        self._managers = [
            self.db, self.layout, self.helpers, self.dashboard_mgr,
            self.documents, self.students_mgr, self.workflows,
            self.document_types, self.notifications_mgr, self.reports,
            self.search, self.bulk_operations, self.versions, self.ocr,
            self.settings_mgr, self.users, self.backup, self.exports,
            self.imports, self.api_web, self.expiry, self.student_portal,
            self.menus,
        ]

        # Initialize database
        if not self.db.init_enhanced_db():
            messagebox.showerror(
                _t("common.database_error", default="Database Error"),
                _t("docmanager.db_init_failed", default="Failed to initialize database. Exiting.")
            )
            root.destroy()
            return

        # Current user (for backwards compatibility)
        self.current_user = get_current_user()
        if self.current_user is None:
            self.current_user = {'username': 'admin', 'role': 'admin'}

        # Create main interface
        self.layout.create_main_interface()

        # Load initial data (do this last)
        self.root.after(100, self.dashboard_mgr.refresh_dashboard)

    def __getattr__(self, name):
        """Delegate method calls to the appropriate manager."""
        if name.startswith('_'):
            raise AttributeError(name)
        for mgr in self._managers:
            if hasattr(mgr, name):
                return getattr(mgr, name)
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")
