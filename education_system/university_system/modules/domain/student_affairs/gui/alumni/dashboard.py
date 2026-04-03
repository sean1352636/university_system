import tkinter as tk
from education_system.university_system.infrastructure.email.template_utils import render_template
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection as db_get_connection
from education_system.university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
from pathlib import Path
import threading
import shutil
from functools import partial

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.modules.shared.utils.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Import the original functions - backward compatibility
try:
    from education_system.university_system.modules.domain.student_affairs.services.alumni_management import (
        init_alumni_db, register_alumni, view_alumni, update_alumni,
        view_events, create_enhanced_event, event_check_in_system,
        record_donation, view_donations, setup_mentorship, view_mentorships,
        search_alumni_directory, view_connection_requests, manage_business_directory,
        create_newsletter, manage_alumni_forum, post_job_opportunity, view_job_board,
        schedule_career_counseling, view_fundraising_campaigns, create_fundraising_campaign,
        view_engagement_leaderboard, view_my_badges, manage_photo_gallery,
        manage_class_reunions, manage_regional_chapters, setup_alumni_directory,
        generate_alumni_report, set_auth, setup_alumni_permissions,
        smart_mentorship_matching, generate_engagement_recommendations,
        create_alumni_story, view_alumni_stories, get_connection
    )
except ImportError as e:
    import_error_details = str(e)
    print(f"Warning: Could not import some functions: {e}")
    # Define fallback functions
    def placeholder_function(*args, **kwargs):
        func_name = kwargs.get('_func_name', 'Unknown function')
        messagebox.showerror(
            "Module Import Error",
            f"The alumni management module could not be loaded.\n\n"
            f"Function: {func_name}\n"
            f"Error: {import_error_details}\n\n"
            f"Please ensure all required dependencies are installed:\n"
            f"• university_system.alumni module\n"
            f"• All database schema requirements\n\n"
            f"Contact your system administrator for assistance."
        )

    # Assign placeholder to missing functions
    register_alumni = placeholder_function
    view_alumni = placeholder_function



class DashboardMixin:
        def show_dashboard(self):
            """Show the main dashboard"""
            self.clear_content()
            self.update_status(_t("alumni.dashboard_loaded", default="Dashboard loaded"))

            # Dashboard title
            title_frame = ttk.Frame(self.content_frame)
            title_frame.pack(fill=tk.X, pady=(0, 20))

            ttk.Label(title_frame, text=_t("alumni.dashboard_title", default="Alumni Management Dashboard"),
                     font=('Arial', 20, 'bold')).pack(side=tk.LEFT)

            # Quick stats
            stats_frame = ttk.LabelFrame(self.content_frame, text=_t("alumni.quick_statistics", default="Quick Statistics"), padding=10)
            stats_frame.pack(fill=tk.X, pady=(0, 20))

            # Create stats grid
            stats_grid = ttk.Frame(stats_frame)
            stats_grid.pack(fill=tk.X)

            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Get stats from database
                cursor.execute("SELECT COUNT(*) FROM alumni")
                result = cursor.fetchone()
                total_alumni = result[0] if result else 0

                cursor.execute("SELECT COUNT(*) FROM unified_events WHERE source_type = 'alumni' AND start_datetime > datetime('now')")
                result = cursor.fetchone()
                upcoming_events = result[0] if result else 0

                cursor.execute("SELECT COUNT(*) FROM alumni WHERE is_donor = 1")
                result = cursor.fetchone()
                total_donors = result[0] if result else 0

                total_donated = 0
                try:
                    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM donations")
                    total_donated = cursor.fetchone()[0]
                except Exception:
                    pass

                active_mentors = 0
                try:
                    cursor.execute("SELECT COUNT(*) FROM mentorships WHERE status = 'active'")
                    active_mentors = cursor.fetchone()[0]
                except Exception:
                    pass

                gift_aid_total = 0
                try:
                    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM donations WHERE is_gift_aided = 1")
                    gift_aid_total = cursor.fetchone()[0]
                except Exception:
                    pass

                conn.close()

                stats = [
                    (_t("alumni.stats.total_alumni", default="Total Alumni"), total_alumni, "👥"),
                    (_t("alumni.stats.upcoming_events", default="Upcoming Events"), upcoming_events, "📅"),
                    (_t("alumni.stats.active_donors", default="Active Donors"), total_donors, "💝"),
                    ("Total Donated", f"£{total_donated:,.2f}", "💰"),
                    ("Active Mentors", active_mentors, "🤝"),
                    ("Gift Aid Eligible", f"£{gift_aid_total:,.2f}", "🎁"),
                    (_t("alumni.stats.system_status", default="System Status"), _t("common.online", default="Online"), "✅"),
                ]
            except sqlite3.Error:
                stats = [
                    (_t("alumni.stats.total_alumni", default="Total Alumni"), _t("common.na", default="N/A"), "👥"),
                    (_t("alumni.stats.upcoming_events", default="Upcoming Events"), _t("common.na", default="N/A"), "📅"),
                    (_t("alumni.stats.active_donors", default="Active Donors"), _t("common.na", default="N/A"), "💝"),
                    (_t("alumni.stats.system_status", default="System Status"), _t("common.error", default="Error"), "❌")
                ]

            for i, (label, value, icon) in enumerate(stats):
                col = i % 4
                row = i // 4

                stat_frame = ttk.Frame(stats_grid, relief=tk.RIDGE, padding=10)
                stat_frame.grid(row=row, column=col, padx=5, pady=5, sticky='ew')

                ttk.Label(stat_frame, text=icon, font=('Arial', 16)).pack()
                ttk.Label(stat_frame, text=str(value), font=('Arial', 14, 'bold')).pack()
                ttk.Label(stat_frame, text=label, font=('Arial', 10)).pack()

                stats_grid.columnconfigure(col, weight=1)

            # Recent activity
            activity_frame = ttk.LabelFrame(self.content_frame, text=_t("alumni.recent_activity", default="Recent Activity"), padding=10)
            activity_frame.pack(fill=tk.BOTH, expand=True)

            activity_text = ScrolledText(activity_frame, height=10, wrap=tk.WORD)
            activity_text.pack(fill=tk.BOTH, expand=True)

            # Sample recent activity
            activity_text.insert(tk.END, _t("alumni.activity_header", default="Recent Alumni System Activity:") + "\n\n")
            activity_text.insert(tk.END, f"• {datetime.now().strftime('%Y-%m-%d %H:%M')} - {_t('alumni.activity_initialized', default='System initialized')}\n")
            activity_text.insert(tk.END, f"• {datetime.now().strftime('%Y-%m-%d %H:%M')} - {_t('alumni.activity_dashboard_loaded', default='Dashboard loaded')}\n")
            activity_text.insert(tk.END, f"• {_t('alumni.activity_db_connected', default='Database connection established')}\n")
            activity_text.config(state=tk.DISABLED)

