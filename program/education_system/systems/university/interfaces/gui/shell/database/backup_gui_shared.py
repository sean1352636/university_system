"""Shared imports and module state for the split implementation."""

import tkinter as tk

from tkinter import ttk, messagebox, filedialog, scrolledtext, simpledialog

import os

import re

import json

import queue

import datetime

import threading

import logging

import shutil

from pathlib import Path

import posixpath

from education_system.systems.university.interfaces.gui.shell.database.shared_imports import (
    DEFAULT_DB_PATH, logger, _t,
)

from education_system.systems.university.interfaces.gui.shell.database.config import (
    config, save_config, load_config, GUI_CONFIG,
    _backup_context_lock, _last_incremental_context, _last_differential_context,
)

from education_system.systems.university.interfaces.gui.shell.database.metadata import metadata_manager

from education_system.systems.university.interfaces.gui.shell.database.scheduling.scheduler import (
    start_scheduler, stop_scheduler, get_connection,
)

from education_system.systems.university.interfaces.gui.shell.database.scheduling.cron import parse_cron_schedule

import education_system.systems.university.interfaces.gui.shell.database.config as cfg

from education_system.systems.university.interfaces.gui.shell.database.operations.backup_ops import create_enhanced_backup, create_selective_backup, create_schema_only_backup, create_incremental_backup, create_differential_backup, calculate_file_hash, compress_file, encrypt_file, upload_to_aws_s3, upload_to_ftp, upload_to_sftp, cleanup_old_backups, notify_backup_result, get_database_tables, get_database_tables_from_connection, has_database_changed, ensure_backup_directory, list_available_backups, validate_backup, deduplicate_backups, send_email_notification

from education_system.systems.university.interfaces.gui.shell.database.operations.stats_ops import (
    generate_backup_statistics, get_log_file,
)

from education_system.systems.university.interfaces.gui.shell.database.operations.template_ops import (
    list_backup_templates, save_backup_template, load_backup_template,
)

from education_system.systems.university.interfaces.gui.shell.database.dialogs.integrity_check import (
    IntegrityCheckDialog, AdvancedSettingsDialog,
)

from education_system.systems.university.interfaces.gui.shell.database.dialogs.backup_options import (
    BackupOptionsDialog, BackupViewerDialog,
)

from education_system.systems.university.interfaces.gui.shell.database.dialogs.restore import (
    RestoreDialog, TableSelectionDialog,
)

from education_system.systems.university.interfaces.gui.shell.database.dialogs.validation import ValidationDialog

from education_system.systems.university.interfaces.gui.shell.database.dialogs.report import ReportDialog

from education_system.systems.university.interfaces.gui.shell.database.dialogs.notifications import (
    EmailConfigDialog, WebhookConfigDialog,
)

from education_system.systems.university.interfaces.gui.shell.database.dialogs.cloud import (
    UploadDialog, DownloadDialog,
)

from education_system.systems.university.interfaces.gui.shell.database.dialogs.export import ExportDialog

from education_system.systems.university.interfaces.gui.shell.database.dialogs.templates import (
    TemplateSelectionDialog, TemplateManagerDialog,
)

from education_system.systems.university.interfaces.gui.shell.database.dialogs.schedule import (
    ScheduleConfigDialog, ScheduleHistoryDialog,
)

from education_system.systems.university.interfaces.gui.shell.database.dialogs.storage import StorageUsageDialog

from education_system.systems.university.interfaces.gui.shell.database.dialogs.comparison import ComparisonDialog

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
