"""Super Admin Dashboard for the Education System.

A comprehensive top-level tkinter window that provides superadmins with
a unified management console across all 5 education systems (Nursery,
Primary, Secondary, College, University).

This package replaced the single 4,400-line ``superadmin_dashboard.py``;
the public import path is unchanged.
"""

from education_system.platform.delivery.gui.superadmin_dashboard.app import SuperAdminDashboard
from education_system.platform.delivery.gui.superadmin_dashboard.i18n import _t, load_translations
from education_system.platform.delivery.gui.superadmin_dashboard.linked_sections import LINKED_SECTIONS, LinkedPlatformSectionsMixin
from education_system.platform.delivery.gui.superadmin_dashboard.theme import (
    SYSTEM_ORDER,
    SYSTEM_LABELS,
    DEFAULT_SYSTEM_COLOR,
    SYSTEM_COLORS,
    SYSTEM_BLURBS,
    LAUNCH_ONLY_SYSTEMS,
    SIDEBAR_BG,
    SIDEBAR_BTN,
    SIDEBAR_BTN_ACTIVE,
    HEADER_BG,
    CONTENT_BG,
    CARD_BG,
    TEXT_DARK,
    TEXT_LIGHT,
    TEXT_MUTED,
    ALERT_COLORS,
    ALERT_OK,
    _fmt_backup_age,
    COMPARISON_COLUMNS,
)

__all__ = [
    "SuperAdminDashboard",
    "load_translations",
    "_t",
    "SYSTEM_ORDER",
    "SYSTEM_LABELS",
    "DEFAULT_SYSTEM_COLOR",
    "SYSTEM_COLORS",
    "SYSTEM_BLURBS",
    "LAUNCH_ONLY_SYSTEMS",
    "SIDEBAR_BG",
    "SIDEBAR_BTN",
    "SIDEBAR_BTN_ACTIVE",
    "HEADER_BG",
    "CONTENT_BG",
    "CARD_BG",
    "TEXT_DARK",
    "TEXT_LIGHT",
    "TEXT_MUTED",
    "ALERT_COLORS",
    "ALERT_OK",
    "_fmt_backup_age",
    "COMPARISON_COLUMNS",
    "LINKED_SECTIONS",
    "LinkedPlatformSectionsMixin",
]
