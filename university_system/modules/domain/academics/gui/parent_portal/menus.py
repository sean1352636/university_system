from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, filedialog
from university_system.infrastructure.database.db import sqlite3
import datetime
import json
import threading
import csv
from typing import Optional, List, Dict, Any
import sys
import os
from university_system.infrastructure.auth import UserAuth
from university_system.infrastructure.shared_context import get_auth

# Import i18n for language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import email service for sending actual emails
try:
    from university_system.infrastructure.email.email_service import send_email, send_email_as_user
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available - emails will be stored locally only")

# Import the original parent portal functionality
try:
    from university_system.modules.domain.academics.services.parent_portal import ParentPortal
except ImportError:
    # If direct import fails, try to import from the document content
    print("Warning: Could not import parent_portal module directly. Using embedded functionality.")
    # We'll create a simplified version that maintains compatibility



from .base import ParentPortalGUI

def show_academic_menu(self):
    """Show academic records submenu"""
    self.clear_content()
    self.update_status(_t("parent_portal.academic.title"))

    title = ttk.Label(self.content_frame, text=_t("parent_portal.academic.title"), style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    menu_frame = ttk.Frame(self.content_frame)
    menu_frame.pack(fill=tk.BOTH, expand=True, padx=20)

    options = [
        (_t("parent_portal.academic.view_grades"), self.show_grades_interface),
        (_t("parent_portal.academic.instructor_reports"), self.show_reports_interface),
        (_t("parent_portal.academic.view_timetable"), self.show_timetable_interface),
        (_t("parent_portal.academic.grade_analytics"), self.show_analytics_interface),
    ]
    
    for i, (text, command) in enumerate(options):
        btn = ttk.Button(
            menu_frame,
            text=text,
            command=command,
            width=35
        )
        btn.pack(pady=10)
ParentPortalGUI.show_academic_menu = show_academic_menu

def show_attendance_menu(self):
    """Show attendance and behavior submenu"""
    self.clear_content()
    self.update_status(_t("parent_portal.attendance.title"))

    title = ttk.Label(self.content_frame, text=_t("parent_portal.attendance.title"), style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    menu_frame = ttk.Frame(self.content_frame)
    menu_frame.pack(fill=tk.BOTH, expand=True, padx=20)

    options = [
        (_t("parent_portal.attendance.view_attendance"), self.show_attendance_interface),
        (_t("parent_portal.attendance.conduct_reports"), self.show_behavior_interface),
        (_t("parent_portal.attendance.report_absence"), self.show_absence_interface),
    ]
    
    for text, command in options:
        btn = ttk.Button(
            menu_frame,
            text=text,
            command=command,
            width=35
        )
        btn.pack(pady=10)
ParentPortalGUI.show_attendance_menu = show_attendance_menu

def show_health_menu(self):
    """Show health and safety submenu"""
    self.clear_content()
    self.update_status(_t("parent_portal.health.title"))

    title = ttk.Label(self.content_frame, text=_t("parent_portal.health.title"), style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    menu_frame = ttk.Frame(self.content_frame)
    menu_frame.pack(fill=tk.BOTH, expand=True, padx=20)

    options = [
        (_t("parent_portal.health.medical_info"), self.show_medical_interface),
        (_t("parent_portal.health.transportation"), self.show_transport_interface),
        (_t("parent_portal.health.authorized_reps"), self.show_pickup_interface),
        (_t("parent_portal.health.photo_permissions"), self.show_photo_interface),
    ]
    
    for text, command in options:
        btn = ttk.Button(
            menu_frame,
            text=text,
            command=command,
            width=35
        )
        btn.pack(pady=10)
ParentPortalGUI.show_health_menu = show_health_menu

def show_communication_menu(self):
    """Show communication submenu"""
    self.clear_content()
    self.update_status(_t("parent_portal.communication.title"))

    title = ttk.Label(self.content_frame, text=_t("parent_portal.communication.title"), style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    menu_frame = ttk.Frame(self.content_frame)
    menu_frame.pack(fill=tk.BOTH, expand=True, padx=20)

    options = [
        (_t("parent_portal.communication.view_messages"), self.show_messages_interface),
        (_t("parent_portal.communication.send_message"), self.show_send_message_interface),
        (_t("parent_portal.communication.group_messages"), self.show_group_message_interface),
        (_t("parent_portal.communication.announcements"), self.show_announcements_interface),
        (_t("parent_portal.communication.schedule_meeting"), self.show_meeting_interface),
        (_t("parent_portal.communication.report_issue"), self.show_report_issue_interface),
    ]

    for text, command in options:
        btn = ttk.Button(
            menu_frame,
            text=text,
            command=command,
            width=35
        )
        btn.pack(pady=10)
ParentPortalGUI.show_communication_menu = show_communication_menu

def show_financial_menu(self):
    """Show financial submenu"""
    self.clear_content()
    self.update_status(_t("parent_portal.financial.title"))

    title = ttk.Label(self.content_frame, text=_t("parent_portal.financial.title"), style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    menu_frame = ttk.Frame(self.content_frame)
    menu_frame.pack(fill=tk.BOTH, expand=True, padx=20)

    options = [
        (_t("parent_portal.financial.fees_payments"), self.show_fees_interface),
        (_t("parent_portal.financial.meal_accounts"), self.show_meal_interface),
        (_t("parent_portal.financial.fundraising"), self.show_fundraising_interface),
        (_t("parent_portal.financial.make_donation"), self.donate_to_campaign),
        (_t("parent_portal.financial.my_donations"), self.show_donations_history),
    ]
    
    for text, command in options:
        btn = ttk.Button(
            menu_frame,
            text=text,
            command=command,
            width=35
        )
        btn.pack(pady=10)
ParentPortalGUI.show_financial_menu = show_financial_menu

def show_academic_support_menu(self):
    """Show academic support submenu"""
    self.clear_content()
    self.update_status(_t("parent_portal.support.title"))

    title = ttk.Label(self.content_frame, text=_t("parent_portal.support.title"), style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    menu_frame = ttk.Frame(self.content_frame)
    menu_frame.pack(fill=tk.BOTH, expand=True, padx=20)

    options = [
        (_t("parent_portal.support.homework"), self.show_homework_interface),
        (_t("parent_portal.support.academic_goals"), self.show_goals_interface),
        (_t("parent_portal.support.grade_analytics"), self.show_analytics_interface),
        (_t("parent_portal.support.library"), self.show_library_interface),
        (_t("parent_portal.support.activities"), self.show_activities_interface),
    ]
    
    for text, command in options:
        btn = ttk.Button(
            menu_frame,
            text=text,
            command=command,
            width=35
        )
        btn.pack(pady=10)
ParentPortalGUI.show_academic_support_menu = show_academic_support_menu

def show_settings_menu(self):
    """Show settings and tools submenu"""
    self.clear_content()
    self.update_status(_t("parent_portal.settings.title"))

    title = ttk.Label(self.content_frame, text=_t("parent_portal.settings.title"), style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    menu_frame = ttk.Frame(self.content_frame)
    menu_frame.pack(fill=tk.BOTH, expand=True, padx=20)

    options = [
        (_t("parent_portal.settings.notifications"), self.show_notifications_interface),
        (_t("parent_portal.settings.documents"), self.show_documents_interface),
        (_t("parent_portal.settings.calendar"), self.show_calendar_interface),
        (_t("parent_portal.settings.account"), self.show_account_interface),
        (_t("parent_portal.settings.activity_log"), self.view_activity_log),
        (_t("parent_portal.settings.two_factor"), self.enable_two_factor_auth),
        (_t("parent_portal.settings.profile_photo"), self.update_profile_photo),
        (_t("parent_portal.settings.export_data"), self.export_child_data),
        (_t("parent_portal.settings.qr_code"), self.generate_qr_code_interface),
        (_t("parent_portal.settings.mark_read"), self.mark_notifications_read),
    ]

    for text, command in options:
        btn = ttk.Button(
            menu_frame,
            text=text,
            command=command,
            width=35
        )
        btn.pack(pady=10)
ParentPortalGUI.show_settings_menu = show_settings_menu

def show_admin_menu(self):
    """Show administrator menu (admin only)"""
    self.clear_content()
    self.update_status(_t("parent_portal.admin.title"))

    # Verify admin access
    current_user = self.get_current_user()
    if not current_user or current_user.get('role') != 'admin':
        messagebox.showerror(_t("common.access_denied"), _t("parent_portal.admin.access_denied"))
        self.show_dashboard()
        return

    # Admin panel title
    title = ttk.Label(
        self.content_frame,
        text=_t("parent_portal.admin.title"),
        style='Title.TLabel',
        font=('Arial', 20, 'bold')
    )
    title.pack(pady=20)

    # Admin info banner
    admin_info = ttk.Frame(self.content_frame)
    admin_info.pack(fill=tk.X, padx=20, pady=10)

    ttk.Label(
        admin_info,
        text=f"Administrator: {current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip() or current_user.get('username', 'Admin'),
        font=('Arial', 11, 'italic'),
        foreground='#c0392b'
    ).pack(anchor='w')

    ttk.Label(
        admin_info,
        text=_t("parent_portal.admin.full_access"),
        font=('Arial', 9),
        foreground='#7f8c8d'
    ).pack(anchor='w')

    # Admin menu frame
    menu_frame = ttk.Frame(self.content_frame)
    menu_frame.pack(fill=tk.BOTH, expand=True, padx=20)

    # Admin options (matching CLI menu)
    admin_options = [
        (_t("parent_portal.admin.create_account"), self.show_create_parent_account_interface,
         _t("parent_portal.admin.create_account_desc"), "#e74c3c"),
        (_t("parent_portal.admin.view_all_accounts"), self.show_all_parent_accounts,
         _t("parent_portal.admin.view_all_desc"), "#9b59b6"),
        (_t("parent_portal.admin.link_student"), self.show_link_student_interface,
         _t("parent_portal.admin.link_student_desc"), "#3498db"),
        (_t("parent_portal.admin.view_dashboard"), self.show_view_parent_dashboard_interface,
         _t("parent_portal.admin.view_dashboard_desc"), "#27ae60"),
        (_t("parent_portal.admin.reports"), self.show_parent_reports_interface,
         _t("parent_portal.admin.reports_desc"), "#f39c12"),
    ]

    for text, command, description, color in admin_options:
        # Create card-style button with description using ttk to reduce X pixmap usage
        card_frame = ttk.LabelFrame(menu_frame, text=text, padding=10)
        card_frame.pack(fill=tk.X, pady=10)

        desc_label = ttk.Label(
            card_frame,
            text=description,
            font=('Arial', 9)
        )
        desc_label.pack(fill=tk.X, pady=(0, 5))

        btn = ttk.Button(
            card_frame,
            text=_t("parent_portal.admin.open"),
            command=command,
            width=15
        )
        btn.pack(anchor='w')
ParentPortalGUI.show_admin_menu = show_admin_menu
