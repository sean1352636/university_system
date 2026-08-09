"""Shared imports and module state for the split implementation."""

from education_system.systems.university.infrastructure.sql_safety import escape_like

import tkinter as tk

from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog

import threading

import queue

from datetime import datetime

import os

import sys

import logging

from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)

from education_system.systems.university.infrastructure.utils.gui_language_selector import (
    show_gui_language_selector,
)

from education_system import paths as _paths

from education_system.systems.university.domains.academics.interfaces.gui.plagiarism_main_gui.config import GuiConfig

from education_system.systems.university.domains.academics.interfaces.gui.plagiarism_main_gui.common import (
    logger,
    get_authenticated_user_auth,
    download_nltk_data,
    PLAGIARISM_BACKEND_AVAILABLE,
    PLAGIARISM_IMPORT_ERROR,
    PlagiarismChecker,
    TEXTRACT_AVAILABLE,
    StatusBar,
    ScrollableFrame,
    ResultCard,
    SetupTestingDialog,
    get_safe_db_connection,
)

from education_system.systems.university.domains.academics.interfaces.gui.plagiarism_main_gui.dialogs.submission import DocumentSubmissionDialog

from education_system.systems.university.domains.academics.interfaces.gui.plagiarism_main_gui.dialogs.check import PlagiarismCheckDialog

from education_system.systems.university.domains.academics.interfaces.gui.plagiarism_main_gui.dialogs.search import RepositorySearchDialog

from education_system.systems.university.domains.academics.interfaces.gui.plagiarism_main_gui.dialogs.advanced_search import AdvancedRepositorySearchDialog

from education_system.systems.university.domains.academics.interfaces.gui.plagiarism_main_gui.dialogs.bulk_operations import BulkOperationsDialog

from education_system.systems.university.domains.academics.interfaces.gui.plagiarism_main_gui.dialogs.system_testing import SystemTestingDialog

from education_system.systems.university.domains.academics.interfaces.gui.plagiarism_main_gui.dialogs.comparison import DocumentComparisonDialog

from education_system.systems.university.domains.academics.interfaces.gui.plagiarism_main_gui.dialogs.converter import FileFormatConverterDialog

from education_system.systems.university.domains.academics.interfaces.gui.plagiarism_main_gui.dialogs.backup_restore import BackupRestoreDialog

from education_system.systems.university.domains.academics.interfaces.gui.plagiarism_main_gui.dialogs.workflow import DocumentWorkflowDialog

from education_system.systems.university.domains.academics.interfaces.gui.plagiarism_main_gui.dialogs.results import CheckResultDialog, ResultDetailsDialog

from education_system.systems.university.domains.academics.interfaces.gui.plagiarism_main_gui.dialogs.statistics import StatisticsDialog

from education_system.systems.university.domains.academics.interfaces.gui.plagiarism_main_gui.dialogs.document_details import DocumentDetailsDialog

try:
    import textract
except ImportError:
    pass

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
