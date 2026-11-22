
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from education_system.systems.university.infrastructure.email.template_utils import render_template
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection as db_get_connection
from education_system import paths
from datetime import datetime, timedelta
from pathlib import Path
import threading
import shutil
from functools import partial

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Alumni service functions
from education_system.systems.university.domains.learners.interfaces.gui.alumni._service_imports import (
    init_alumni_db,
    view_events,
    create_enhanced_event,
    event_check_in_system,
    view_connection_requests,
    manage_business_directory,
    manage_alumni_forum,
    post_job_opportunity,
    view_job_board,
    schedule_career_counseling,
    view_engagement_leaderboard,
    view_my_badges,
    manage_photo_gallery,
    manage_class_reunions,
    generate_alumni_report,
    set_auth,
    setup_alumni_permissions,
    generate_engagement_recommendations,
    get_connection,
)



class ForumMixin:

        def preview_newsletter(self):
            """Preview the newsletter"""
            preview_window = tk.Toplevel(self.root)
            preview_window.title(f"Newsletter Preview - {self.newsletter_title.get()}")
            preview_window.geometry("600x500")

            preview_text = ScrolledText(preview_window, wrap=tk.WORD, padx=10, pady=10)
            preview_text.pack(fill=tk.BOTH, expand=True)

            preview_content = f"Title: {self.newsletter_title.get()}\n"
            preview_content += f"Audience: {self.newsletter_audience.get()}\n"
            preview_content += f"Send Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            preview_content += "=" * 50 + "\n\n"
            preview_content += self.newsletter_content.get(1.0, tk.END)

            preview_text.insert(tk.END, preview_content)
            preview_text.config(state=tk.DISABLED)

        def save_newsletter_draft(self):
            """Save newsletter as draft"""
            messagebox.showinfo(_t('gui.learners.alumni.forum.dialogs.draft_saved', default="Draft Saved"), _t('gui.learners.alumni.forum.dialogs.newsletter_saved_as_draft_successfully', default="Newsletter saved as draft successfully!"))
            self.update_status("Newsletter draft saved")

        def send_newsletter(self):
            """Send the newsletter"""
            if not self.newsletter_title.get().strip():
                messagebox.showerror(_t('gui.learners.alumni.forum.dialogs.validation_error', default="Validation Error"), _t('gui.learners.alumni.forum.dialogs.newsletter_title_is_required', default="Newsletter title is required!"))
                return

            if not self.newsletter_content.get(1.0, tk.END).strip():
                messagebox.showerror(_t('gui.learners.alumni.forum.dialogs.validation_error', default="Validation Error"), _t('gui.learners.alumni.forum.dialogs.newsletter_content_is_required', default="Newsletter content is required!"))
                return

            # Confirmation dialog
            if messagebox.askyesno(_t('gui.learners.alumni.forum.dialogs.confirm_send', default="Confirm Send"),
                                  f"Send newsletter '{self.newsletter_title.get()}' to {self.newsletter_audience.get()}?"):
                messagebox.showinfo(_t('gui.learners.alumni.forum.dialogs.newsletter_sent', default="Newsletter Sent"), _t('gui.learners.alumni.forum.dialogs.newsletter_has_been_sent_successfully', default="Newsletter has been sent successfully!"))
                self.update_status("Newsletter sent to recipients")

        def show_create_newsletter(self):
            """Show newsletter creation interface"""
            self.clear_content()
            self.update_status("Newsletter Creation")

            ttk.Label(self.content_frame, text=_t('gui.learners.alumni.forum.labels.create_alumni_newsletter', default="Create Alumni Newsletter"),
                     font=('Arial', 16, 'bold')).pack(pady=(0, 20))

            # Newsletter form
            form_frame = ttk.LabelFrame(self.content_frame, text=_t('gui.learners.alumni.forum.labels.newsletter_details', default="Newsletter Details"), padding=10)
            form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

            # Title
            title_frame = ttk.Frame(form_frame)
            title_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(title_frame, text=_t('gui.learners.alumni.forum.labels.newsletter_title', default="Newsletter Title:")).pack(side=tk.LEFT, padx=(0, 10))
            self.newsletter_title = tk.StringVar()
            ttk.Entry(title_frame, textvariable=self.newsletter_title).pack(side=tk.LEFT, fill=tk.X, expand=True)

            # Target audience
            audience_frame = ttk.Frame(form_frame)
            audience_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(audience_frame, text=_t('gui.learners.alumni.forum.labels.target_audience', default="Target Audience:")).pack(side=tk.LEFT, padx=(0, 10))
            self.newsletter_audience = tk.StringVar()
            audience_combo = ttk.Combobox(audience_frame, textvariable=self.newsletter_audience,
                                         values=["All Alumni", "By Graduation Year", "By Industry", "Donors Only", "Mentors Only"])
            audience_combo.pack(side=tk.LEFT, padx=(0, 10))
            audience_combo.set("All Alumni")

            # Content
            ttk.Label(form_frame, text=_t('gui.learners.alumni.forum.labels.newsletter_content', default="Newsletter Content:")).pack(anchor='w', pady=(10, 5))
            self.newsletter_content = ScrolledText(form_frame, height=15, wrap=tk.WORD)
            self.newsletter_content.pack(fill=tk.BOTH, expand=True)

            # Sample content
            sample_content = """Subject: Alumni Newsletter - August 2025

    Dear Alumni,

    We hope this newsletter finds you well! Here are the latest updates from our alumni community:

    🎓 ALUMNI SPOTLIGHT
    This month we feature Sarah Johnson (Class of 2015), who recently launched her tech startup...

    📅 UPCOMING EVENTS
    • Annual Alumni Gala - September 15, 2025
    • Tech Industry Networking - August 25, 2025
    • Class of 2020 Reunion - October 10, 2025

    💼 CAREER OPPORTUNITIES
    New job postings from our alumni network:
    • Senior Developer at Tech Corp
    • Financial Analyst at Finance Plus
    • Marketing Manager at StartupCo

    🤝 MENTORSHIP PROGRAM
    Join our expanding mentorship program! We currently have 50+ active mentor-mentee pairs...

    💝 GIVING BACK
    Thank you to our recent donors who contributed to the Annual Alumni Fund...

    Best regards,
    Alumni Relations Team
    """
            self.newsletter_content.insert(tk.END, sample_content)

            # Buttons
            button_frame = ttk.Frame(form_frame)
            button_frame.pack(fill=tk.X, pady=10)

            ttk.Button(button_frame, text=_t('gui.learners.alumni.forum.buttons.send_newsletter', default="Send Newsletter"),
                      command=self.send_newsletter).pack(side=tk.RIGHT, padx=(10, 0))
            ttk.Button(button_frame, text=_t('gui.learners.alumni.forum.buttons.save_as_draft', default="Save as Draft"),
                      command=self.save_newsletter_draft).pack(side=tk.RIGHT)
            ttk.Button(button_frame, text=_t('gui.learners.alumni.forum.buttons.preview', default="Preview"),
                      command=self.preview_newsletter).pack(side=tk.RIGHT, padx=(0, 10))

        # ── the forum, on alumni_community's rules (alumni_forum) ──
        # The old screens read a ``forum_posts`` table that does not exist and
        # showed hard-coded sample posts; these open the real screens.
        def show_forum(self):
            from education_system.systems.university.domains.learners.interfaces.gui.alumni import alumni_office_mentoring as screens
            screens.show_forum(self)

        def view_forum_posts(self):
            self.show_forum()

        def show_search_forum_posts(self):
            self.show_forum()

        def show_my_forum_posts(self):
            from education_system.systems.university.domains.learners.interfaces.gui.alumni import alumni_office_mentoring as screens
            screens.show_forum(self, mine=True)

        def show_moderate_forum_posts(self):
            from education_system.systems.university.domains.learners.interfaces.gui.alumni import alumni_office_mentoring as screens
            screens.show_moderation(self)
