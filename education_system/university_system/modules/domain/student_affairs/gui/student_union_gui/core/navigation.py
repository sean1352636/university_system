import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.university_system.infrastructure.email.template_utils import render_template
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from education_system.university_system.infrastructure.database.db import get_connection
    from education_system.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


def change_language(self):
    """Open language selector and refresh UI on change"""
    old_lang = get_current_language()
    show_gui_language_selector(self.root)
    new_lang = get_current_language()
    if old_lang != new_lang:
        self.refresh_ui_text()


def refresh_ui_text(self):
    """Refresh all UI text after language change"""
    self.root.title(_t("student_union.window_title"))
    # Rebuild the sidebar and menus
    self.setup_gui()
    self.show_main_dashboard()


def add_sidebar_header(self, text, icon=""):
    """Add a category header to sidebar"""
    header_text = f"{icon} {text}" if icon else text
    header = tk.Label(self.scrollable_sidebar, text=header_text,
                     bg='#34495e', fg='white', font=('Arial', 11, 'bold'),
                     anchor='w', padx=15, pady=8)
    header.pack(fill=tk.X, pady=(10, 0))


def add_sidebar_button(self, text, command, icon="", admin_only=False, staff_only=False):
    """Add a button to sidebar with role-based filtering"""
    # Check role permissions
    if admin_only and not self.is_admin():
        return
    if staff_only and not (self.is_admin() or self.is_staff()):
        return
    button_text = f"{icon} {text}" if icon else text
    btn = tk.Button(self.scrollable_sidebar, text=button_text,
                   command=command, bg='#34495e', fg='white',
                   activebackground='#1abc9c', activeforeground='white',
                   font=('Arial', 10), bd=0, padx=20, pady=12,
                   anchor='w', cursor='hand2')
    btn.pack(fill=tk.X, padx=5, pady=2)
    # Hover effects
    btn.bind('<Enter>', lambda e: btn.config(bg='#1abc9c'))
    btn.bind('<Leave>', lambda e: btn.config(bg='#34495e'))


def add_sidebar_separator(self):
    """Add a visual separator in sidebar"""
    sep = ttk.Separator(self.scrollable_sidebar, orient='horizontal')
    sep.pack(fill=tk.X, padx=10, pady=5)


def switch_to_cli(self):
    """Switch to Student Union CLI mode"""
    if not CLI_AVAILABLE:
        messagebox.showerror("Error", "CLI mode is not available")
        return
    response = messagebox.askyesno("Switch to CLI",
                                 "Switch to Student Union command-line interface?\nThe GUI will close.")
    if response:
        self.root.destroy()
        # Launch Student Union CLI mode
        try:
            from education_system.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import display_student_union_menu
            # Get current auth from GUI
            auth = get_auth()
            if auth:
                from education_system.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import set_auth
                set_auth(auth)
            display_student_union_menu()
        except ImportError as e:
            print(f"Error: Cannot import Student Union CLI system - {e}")
            messagebox.showerror("Error", f"Cannot import Student Union CLI system: {e}")


def return_to_homescreen(self):
    """Close this window and return to the main menu"""
    try:
        # Check if this is a child window (Toplevel) or standalone (Tk)
        if isinstance(self.root, tk.Toplevel):
            # Just close the child window
            self.root.destroy()
        else:
            # Running standalone - just close the window
            self.root.destroy()
    except Exception as e:
        print(f"Error returning to homescreen: {e}")
        self.root.destroy()


def setup_main_menu(self):
    """Setup the main menu bar with role-based filtering"""
    # Clear existing menu
    self.menu_bar.delete(0, 'end')
    # Get user role for filtering
    is_admin = self.is_admin()
    is_staff = self.is_staff()
    is_student = self.is_student()
    # Tools menu
    tools_menu = tk.Menu(self.menu_bar, tearoff=0)
    self.menu_bar.add_cascade(label="Tools", menu=tools_menu)
    if CLI_AVAILABLE:
        tools_menu.add_command(label="Switch to CLI", command=self.switch_to_cli)
    if is_admin or is_staff:
        tools_menu.add_command(label="Database Info", command=self.show_database_info)
    # Integrations menu
    integrations_menu = tk.Menu(self.menu_bar, tearoff=0)
    self.menu_bar.add_cascade(label="🔗 Integrations", menu=integrations_menu)
    # Club Payments
    integrations_menu.add_command(label="💰 Club Payments",
                                 command=lambda: self.show_club_payments_content())
    # Shop submenu
    integrations_menu.add_command(label="👕 Club Merchandise",
                                 command=lambda: self.open_shop_for_club_merchandise())
    integrations_menu.add_command(label="🛒 University Shop",
                                 command=lambda: self.open_shop_gui_direct())
    # Restaurant
    integrations_menu.add_command(label="🍽️ University Restaurant",
                                 command=lambda: self.open_restaurant_for_club_booking("General"))
    # Calendar and Trips
    integrations_menu.add_separator()
    integrations_menu.add_command(label="📅 Student Union Calendar",
                                 command=lambda: self.open_calendar_with_club_events())
    integrations_menu.add_command(label="🧳 Trip Management",
                                 command=lambda: self.open_trip_management_dialog())
    # New Features menu
    features_menu = tk.Menu(self.menu_bar, tearoff=0)
    self.menu_bar.add_cascade(label="🆕 New Features", menu=features_menu)
    features_menu.add_command(label="🗳️ Elections & Voting", command=self.open_elections_dialog)
    features_menu.add_command(label="🌱 Green Initiatives", command=self.open_green_initiatives_dialog)
    features_menu.add_command(label="🤝 Volunteer Opportunities", command=self.open_volunteer_opportunities_dialog)
    features_menu.add_command(label="📋 Community Service Hours", command=self.open_community_service_hours_dialog)
    # Admin/Staff only features
    if is_admin or is_staff:
        features_menu.add_separator()
        features_menu.add_command(label="📊 Advanced Analytics", command=self.open_advanced_analytics_dialog)
        features_menu.add_command(label="📡 Live Streaming", command=self.open_live_streaming_dialog)
        features_menu.add_command(label="🎓 Academic Conferences", command=self.open_academic_conferences_dialog)
    # Admin only features
    if is_admin:
        features_menu.add_separator()
        features_menu.add_command(label="⚙️ Setup Election (Admin)", command=self.open_setup_election_dialog)
    # Advanced Elections submenu
    advanced_elections_submenu = tk.Menu(features_menu, tearoff=0)
    features_menu.add_cascade(label="🗳️ Advanced Elections", menu=advanced_elections_submenu)
    advanced_elections_submenu.add_command(label="👤 View Candidate Profiles", command=self.open_candidate_profiles_dialog)
    advanced_elections_submenu.add_command(label="♿ Election Accessibility", command=self.open_election_accessibility_dialog)
    advanced_elections_submenu.add_command(label="🥇 Ranked Choice Voting", command=self.open_ranked_choice_voting_dialog)
    # Admin/Staff only election features
    if is_admin or is_staff:
        advanced_elections_submenu.add_separator()
        advanced_elections_submenu.add_command(label="💰 Track Campaign Expenses", command=self.open_campaign_expenses_dialog)
        advanced_elections_submenu.add_command(label="⚖️ Monitor Campaign Compliance", command=self.open_campaign_compliance_dialog)
        advanced_elections_submenu.add_command(label="🔒 Election Security Audit", command=self.open_election_security_dialog)
        advanced_elections_submenu.add_command(label="✅ Vote Integrity Check", command=self.open_vote_integrity_dialog)
    # Admin only voting configuration
    if is_admin:
        advanced_elections_submenu.add_separator()
        advanced_elections_submenu.add_command(label="🔧 Manage Enhanced Voting", command=self.open_manage_enhanced_voting_dialog)
        advanced_elections_submenu.add_command(label="⚙️ Configure Voting Methods", command=self.open_configure_voting_methods_dialog)
    # Additional Features menu
    additional_menu = tk.Menu(self.menu_bar, tearoff=0)
    self.menu_bar.add_cascade(label="🎯 More Features", menu=additional_menu)
    # Competitions submenu
    competitions_submenu = tk.Menu(additional_menu, tearoff=0)
    additional_menu.add_cascade(label="🏆 Competitions", menu=competitions_submenu)
    competitions_submenu.add_command(label="Inter-Club Competitions", command=self.open_interclub_competitions_dialog)
    # Community submenu
    community_submenu = tk.Menu(additional_menu, tearoff=0)
    additional_menu.add_cascade(label="🤝 Community", menu=community_submenu)
    community_submenu.add_command(label="Community Engagement", command=self.open_community_engagement_dialog)
    # Admin/Staff only community analytics
    if is_admin or is_staff:
        community_submenu.add_command(label="Engagement Trends", command=self.open_engagement_trends_dialog)
        community_submenu.add_command(label="Retention Insights", command=self.open_retention_insights_dialog)
    # Events submenu
    events_submenu = tk.Menu(additional_menu, tearoff=0)
    additional_menu.add_cascade(label="📅 Advanced Events", menu=events_submenu)
    events_submenu.add_command(label="Event Ticketing System", command=self.open_event_ticketing_dialog)
    events_submenu.add_command(label="Recurring Events", command=self.open_recurring_events_dialog)
    events_submenu.add_command(label="Event Attendance", command=self.open_event_attendance_dialog)
    events_submenu.add_separator()
    events_submenu.add_command(label="💻 Virtual Events", command=self.open_virtual_events_dialog)
    events_submenu.add_command(label="🎓 Knowledge Sharing Sessions", command=self.open_knowledge_sharing_dialog)
    # Admin/Staff only event features
    if is_admin or is_staff:
        events_submenu.add_separator()
        events_submenu.add_command(label="Event Financial Tracking", command=self.open_event_financial_tracking_dialog)
    # Facilities submenu (Part 3C)
    facilities_submenu = tk.Menu(additional_menu, tearoff=0)
    additional_menu.add_cascade(label="🏢 Facilities", menu=facilities_submenu)
    # Admin only facility approvals
    if is_admin:
        facilities_submenu.add_command(label="✅ Approve Bookings (Admin)", command=self.open_approve_facility_bookings_dialog)
    # Equipment Management submenu (Part 3C)
    equipment_submenu = tk.Menu(additional_menu, tearoff=0)
    additional_menu.add_cascade(label="📦 Equipment Management", menu=equipment_submenu)
    # Student functions - available to all
    equipment_submenu.add_command(label="📋 Browse Available Equipment", command=self.open_browse_available_equipment_dialog)
    equipment_submenu.add_command(label="🔍 Search Equipment", command=self.open_search_equipment_dialog)
    equipment_submenu.add_command(label="ℹ️ View Equipment Details", command=self.open_view_equipment_details_dialog)
    equipment_submenu.add_command(label="📤 Check Out Equipment", command=self.open_checkout_equipment_dialog)
    equipment_submenu.add_command(label="📥 Return Equipment", command=self.open_return_equipment_dialog)
    equipment_submenu.add_command(label="📜 My Equipment Checkouts", command=self.open_my_equipment_checkouts_dialog)
    # Admin only equipment management
    if is_admin:
        equipment_submenu.add_separator()
        equipment_submenu.add_command(label="🏠 Equipment System Hub", command=self.open_manage_equipment_system_dialog)
        equipment_submenu.add_command(label="➕ Add New Equipment (Admin)", command=self.open_add_new_equipment_dialog)
        equipment_submenu.add_command(label="🔧 Update Equipment Status (Admin)", command=self.open_update_equipment_status_dialog)
        equipment_submenu.add_command(label="🛠️ Maintenance Tracking (Admin)", command=self.open_equipment_maintenance_tracking_dialog)
        equipment_submenu.add_command(label="📊 Generate Reports (Admin)", command=self.open_generate_equipment_reports_dialog)
    # Peer Support & Wellness submenu
    peer_support_submenu = tk.Menu(additional_menu, tearoff=0)
    additional_menu.add_cascade(label="🤝 Peer Support & Wellness", menu=peer_support_submenu)
    peer_support_submenu.add_command(label="🏠 Peer Support Hub", command=self.open_peer_support_wellness_dialog)
    peer_support_submenu.add_separator()
    peer_support_submenu.add_command(label="📋 Browse Support Groups", command=lambda: self.open_peer_support_wellness_dialog())
    peer_support_submenu.add_command(label="👥 My Support Groups", command=lambda: self.open_peer_support_wellness_dialog())
    peer_support_submenu.add_command(label="➕ Create Support Group", command=lambda: self.open_peer_support_wellness_dialog())
    peer_support_submenu.add_command(label="🤝 Anonymous Peer Matching", command=lambda: self.open_peer_support_wellness_dialog())
    peer_support_submenu.add_separator()
    peer_support_submenu.add_command(label="📚 Wellness Resources", command=lambda: self.open_peer_support_wellness_dialog())
    peer_support_submenu.add_command(label="🆘 Crisis Resources", command=lambda: self.open_peer_support_wellness_dialog())
    # Academic Support submenu
    academic_support_submenu = tk.Menu(additional_menu, tearoff=0)
    additional_menu.add_cascade(label="🎓 Academic Support", menu=academic_support_submenu)
    academic_support_submenu.add_command(label="🏠 Academic Support Hub", command=self.open_academic_support_dialog)
    academic_support_submenu.add_separator()
    academic_support_submenu.add_command(label="📚 Study Groups", command=lambda: self.open_academic_support_dialog())
    academic_support_submenu.add_command(label="👨‍🏫 Peer Tutoring", command=lambda: self.open_academic_support_dialog())
    academic_support_submenu.add_command(label="📂 Shared Resources", command=lambda: self.open_academic_support_dialog())
    academic_support_submenu.add_command(label="📝 Exam Prep Groups", command=lambda: self.open_academic_support_dialog())
    academic_support_submenu.add_command(label="🎯 Academic Workshops", command=lambda: self.open_academic_support_dialog())
    # Help menu
    help_menu = tk.Menu(self.menu_bar, tearoff=0)
    self.menu_bar.add_cascade(label="Help", menu=help_menu)
    help_menu.add_command(label="About", command=self.show_about)
    self.create_main_menu_button()
# =========================================================================
# CLUB PAYMENT MANAGEMENT METHODS
# =========================================================================


def create_main_menu_button(self):
    """Ensure a top-right button exists for returning to the main menu"""
    try:
        if hasattr(self, "main_menu_button") and self.main_menu_button.winfo_exists():
            return
    except sqlite3.Error:
        pass
    self.main_menu_button = ttk.Button(
        self.root,
        text="🏠 Return to Main Menu",
        command=self.return_to_main_menu,
    )
    self.main_menu_button.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)


def return_to_main_menu(self):
    """Return to the main menu"""
    try:
        # Check if this is a child window (Toplevel) or standalone (Tk)
        if isinstance(self.root, tk.Toplevel):
            # Just close the child window
            self.root.destroy()
        else:
            # Running standalone, need to create main GUI
            self.root.destroy()
            from education_system.university_system.modules.shared.gui.main import UnifiedManagementGUI
            app = UnifiedManagementGUI(self.auth)
            app.run()
    except (tk.TclError, AttributeError) as e:
        print(f"Error returning to main menu: {e}")
        import traceback
        traceback.print_exc()
# Dialog Classes for More Complex GUI Interactions
# =========================================================================
# INTEGRATION HELPER METHODS
# =========================================================================


