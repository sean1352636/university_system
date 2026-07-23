"""
Admissions & Recruitment CRM GUI

Comprehensive Tkinter interface for managing prospective students, applications,
reviews, communication campaigns, campus tours, and yield predictions.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from typing import Optional

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.infrastructure.shared_context import get_auth
from education_system.post_18.university_system.core.activity_logger import log_activity
from education_system.post_18.university_system.infrastructure.email.email_service import send_email
from education_system.post_18.university_system.core.i18n import (
    get_text as _t,
    init_i18n,
    get_current_language,
    get_current_language_name
)
from education_system.post_18.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector
from education_system.post_18.university_system.modules.domain.admissions.services.admissions_crm_core import (
    ProspectManager,
    ApplicationManager,
    ReviewWorkflowManager,
    CampaignManager,
    TourManager
)


class AdmissionsCRMGUI:
    """Admissions & Recruitment CRM GUI Application"""

    def __init__(self, root, auth):
        """Initialize the Admissions CRM GUI"""
        self.root = root
        self.auth = auth

        if not self.auth or not hasattr(self.auth, 'current_user') or not self.auth.current_user:
            messagebox.showerror(_t("common.error"), _t("admissions_crm.auth.login_required"))
            return

        # When ``root`` is a workspace tab Frame (passed by
        # ``open_in_workspace``), embed inside it. Frames have no
        # ``wm_title``; Tk/Toplevel do.
        if root is not None and not hasattr(root, "wm_title"):
            self.window = root
        else:
            self.window = tk.Toplevel(root)
            self.window.title(_t("admissions_crm.window_title"))
            self.window.geometry("1200x800")
            self.window.minsize(1000, 600)

        # Initialize database tables
        self._init_database()

        # Setup UI
        self._create_widgets()

        # Log activity
        log_activity('Accessed Admissions & Recruitment CRM', user=self.auth.current_user.get('username'))
        print("✅ Admissions & Recruitment CRM GUI opened successfully")

    def _init_database(self):
        """Initialize database tables if they don't exist"""
        try:
            from education_system.post_18.university_system.infrastructure.database.schemas.admissions_schemas import init_admissions_crm_system_db
            init_admissions_crm_system_db()
        except ImportError as e:
            print(f"⚠️  Warning: Could not import database schemas: {e}")
        except Exception as e:
            print(f"⚠️  Warning: Database initialization error: {e}")
            messagebox.showwarning(_t("common.warning"), f"Database initialization issue: {e}")

    def _create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            header_frame,
            text=_t("admissions_crm.title"),
            font=('Arial', 18, 'bold')
        ).pack(side=tk.LEFT)

        # Language button
        lang_btn = ttk.Button(
            header_frame,
            text=f"🌐 {get_current_language_name()}",
            command=self._on_language_change,
            width=15
        )
        lang_btn.pack(side=tk.RIGHT, padx=5)

        user_label = ttk.Label(
            header_frame,
            text=_t("admissions_crm.user_label", username=self.auth.current_user.get('username', 'Unknown')),
            font=('Arial', 10)
        )
        user_label.pack(side=tk.RIGHT, padx=10)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self._create_prospects_tab()
        self._create_applications_tab()
        self._create_reviews_tab()
        self._create_campaigns_tab()
        self._create_tours_tab()

        # Close button
        ttk.Button(
            main_frame,
            text=_t("admissions_crm.close"),
            command=self.window.destroy
        ).pack(pady=(10, 0))

    def _on_language_change(self):
        """Handle language change button click"""
        current_lang = get_current_language()
        show_gui_language_selector(self.window)
        new_lang = get_current_language()

        if new_lang != current_lang:
            messagebox.showinfo(
                _t("admissions_crm.language.changed_title"),
                _t("admissions_crm.language.changed_message")
            )
            self._refresh_ui_language()

    def _refresh_ui_language(self):
        """Refresh all UI elements with current language"""
        init_i18n(get_current_language())
        # `self.window` is a Toplevel when launched standalone, but a Frame
        # when embedded in a workspace tab. Frames have no .title().
        if hasattr(self.window, "wm_title"):
            self.window.title(_t("admissions_crm.window_title"))
        # Recreate the main interface
        for widget in self.window.winfo_children():
            widget.destroy()
        self._create_widgets()

    def _create_prospects_tab(self):
        """Create Prospects management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("admissions_crm.tabs.prospects"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_t("admissions_crm.prospects.add"), command=self._add_prospect).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admissions_crm.prospects.log_interaction"), command=self._log_interaction).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admissions_crm.prospects.refresh"), command=self._load_prospects).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Draft APL claim", command=self._draft_apl_for_prospect).pack(side=tk.LEFT, padx=5)

        # Prospects list
        list_frame = ttk.LabelFrame(tab, text=_t("admissions_crm.prospects.title"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('id', 'name', 'email', 'phone', 'intended_major', 'source', 'status', 'last_contact')
        column_labels = {
            'id': _t("admissions_crm.columns.id"),
            'name': _t("admissions_crm.columns.name"),
            'email': _t("admissions_crm.columns.email"),
            'phone': _t("admissions_crm.columns.phone"),
            'intended_major': _t("admissions_crm.columns.intended_major"),
            'source': _t("admissions_crm.columns.source"),
            'status': _t("admissions_crm.columns.status"),
            'last_contact': _t("admissions_crm.columns.last_contact")
        }
        self.prospects_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.prospects_tree.heading('#0', text='')
        self.prospects_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.prospects_tree.heading(col, text=column_labels[col])
            if col == 'id':
                self.prospects_tree.column(col, width=50)
            elif col in ['name', 'email']:
                self.prospects_tree.column(col, width=150)
            else:
                self.prospects_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.prospects_tree.yview)
        self.prospects_tree.configure(yscrollcommand=scrollbar.set)

        self.prospects_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_prospects()

    def _create_applications_tab(self):
        """Create Applications management tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("admissions_crm.tabs.applications"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_t("admissions_crm.applications.submit"), command=self._submit_application).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admissions_crm.applications.update_status"), command=self._update_application_status).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admissions_crm.applications.refresh"), command=self._load_applications).pack(side=tk.LEFT, padx=5)

        # Applications list
        list_frame = ttk.LabelFrame(tab, text=_t("admissions_crm.applications.title"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('id', 'prospect', 'type', 'program', 'year', 'semester', 'status', 'submitted')
        column_labels = {
            'id': _t("admissions_crm.columns.id"),
            'prospect': _t("admissions_crm.columns.prospect"),
            'type': _t("admissions_crm.columns.type"),
            'program': _t("admissions_crm.columns.program"),
            'year': _t("admissions_crm.columns.year"),
            'semester': _t("admissions_crm.columns.semester"),
            'status': _t("admissions_crm.columns.status"),
            'submitted': _t("admissions_crm.columns.submitted")
        }
        self.applications_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.applications_tree.heading('#0', text='')
        self.applications_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.applications_tree.heading(col, text=column_labels[col])
            if col == 'id':
                self.applications_tree.column(col, width=50)
            elif col in ['type', 'semester', 'status']:
                self.applications_tree.column(col, width=90)
            else:
                self.applications_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.applications_tree.yview)
        self.applications_tree.configure(yscrollcommand=scrollbar.set)

        self.applications_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_applications()

    def _create_reviews_tab(self):
        """Create Reviews workflow tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("admissions_crm.tabs.reviews"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_t("admissions_crm.reviews.create"), command=self._create_review).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admissions_crm.reviews.assign_reviewer"), command=self._assign_reviewer).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admissions_crm.reviews.submit_review"), command=self._submit_review).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admissions_crm.reviews.refresh"), command=self._load_reviews).pack(side=tk.LEFT, padx=5)

        # Reviews list
        list_frame = ttk.LabelFrame(tab, text=_t("admissions_crm.reviews.title"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('id', 'application', 'reviewer', 'rating', 'decision', 'reviewed', 'status')
        column_labels = {
            'id': _t("admissions_crm.columns.id"),
            'application': _t("admissions_crm.columns.application"),
            'reviewer': _t("admissions_crm.columns.reviewer"),
            'rating': _t("admissions_crm.columns.rating"),
            'decision': _t("admissions_crm.columns.decision"),
            'reviewed': _t("admissions_crm.columns.reviewed"),
            'status': _t("admissions_crm.columns.status")
        }
        self.reviews_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.reviews_tree.heading('#0', text='')
        self.reviews_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.reviews_tree.heading(col, text=column_labels[col])
            if col in ['id', 'rating']:
                self.reviews_tree.column(col, width=60)
            elif col in ['decision', 'status']:
                self.reviews_tree.column(col, width=100)
            else:
                self.reviews_tree.column(col, width=130)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.reviews_tree.yview)
        self.reviews_tree.configure(yscrollcommand=scrollbar.set)

        self.reviews_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_reviews()

    def _create_campaigns_tab(self):
        """Create Communication Campaigns tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("admissions_crm.tabs.campaigns"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_t("admissions_crm.campaigns.create"), command=self._create_campaign).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admissions_crm.campaigns.send"), command=self._send_communications).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admissions_crm.campaigns.refresh"), command=self._load_campaigns).pack(side=tk.LEFT, padx=5)

        # Campaigns list
        list_frame = ttk.LabelFrame(tab, text=_t("admissions_crm.campaigns.title"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('id', 'campaign_name', 'type', 'target', 'sent', 'opened', 'active')
        column_labels = {
            'id': _t("admissions_crm.columns.id"),
            'campaign_name': _t("admissions_crm.columns.campaign_name"),
            'type': _t("admissions_crm.columns.type"),
            'target': _t("admissions_crm.columns.target"),
            'sent': _t("admissions_crm.columns.sent"),
            'opened': _t("admissions_crm.columns.opened"),
            'active': _t("admissions_crm.columns.active")
        }
        self.campaigns_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.campaigns_tree.heading('#0', text='')
        self.campaigns_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.campaigns_tree.heading(col, text=column_labels[col])
            if col in ['id', 'sent', 'opened']:
                self.campaigns_tree.column(col, width=60)
            elif col in ['type', 'active']:
                self.campaigns_tree.column(col, width=80)
            else:
                self.campaigns_tree.column(col, width=180)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.campaigns_tree.yview)
        self.campaigns_tree.configure(yscrollcommand=scrollbar.set)

        self.campaigns_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_campaigns()

    def _create_tours_tab(self):
        """Create Campus Tours tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("admissions_crm.tabs.tours"))

        # Top buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text=_t("admissions_crm.tours.schedule"), command=self._schedule_tour).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admissions_crm.tours.register"), command=self._register_for_tour).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admissions_crm.tours.refresh"), command=self._load_tours).pack(side=tk.LEFT, padx=5)

        # Tours list
        list_frame = ttk.LabelFrame(tab, text=_t("admissions_crm.tours.title"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('id', 'tour_date', 'time', 'type', 'guide', 'capacity', 'registered', 'status')
        column_labels = {
            'id': _t("admissions_crm.columns.id"),
            'tour_date': _t("admissions_crm.columns.tour_date"),
            'time': _t("admissions_crm.columns.time"),
            'type': _t("admissions_crm.columns.type"),
            'guide': _t("admissions_crm.columns.guide"),
            'capacity': _t("admissions_crm.columns.capacity"),
            'registered': _t("admissions_crm.columns.registered"),
            'status': _t("admissions_crm.columns.status")
        }
        self.tours_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        self.tours_tree.heading('#0', text='')
        self.tours_tree.column('#0', width=0, stretch=False)

        for col in columns:
            self.tours_tree.heading(col, text=column_labels[col])
            if col in ['id', 'capacity', 'registered']:
                self.tours_tree.column(col, width=70)
            elif col in ['time', 'status']:
                self.tours_tree.column(col, width=90)
            else:
                self.tours_tree.column(col, width=130)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tours_tree.yview)
        self.tours_tree.configure(yscrollcommand=scrollbar.set)

        self.tours_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_tours()

    # Load methods
    def _load_prospects(self):
        """Load all prospects"""
        try:
            self.prospects_tree.delete(*self.prospects_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT prospect_id, first_name, last_name, email, phone,
                           intended_major, source, status, last_contact_date
                    FROM admission_prospects
                    ORDER BY created_at DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    name = f"{row['first_name']} {row['last_name']}"
                    values = (
                        row['prospect_id'],
                        name,
                        row['email'],
                        row['phone'] or _t("common.na"),
                        row['intended_major'] or _t("admissions_crm.prospects.undecided"),
                        row['source'] or _t("common.na"),
                        row['status'],
                        row['last_contact_date'][:10] if row['last_contact_date'] else _t("common.never")
                    )
                    self.prospects_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_t("common.error"), f"Failed to load prospects: {e}")

    def _load_applications(self):
        """Load all applications"""
        try:
            self.applications_tree.delete(*self.applications_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT a.application_id, p.first_name, p.last_name,
                           a.application_type, a.program_applied, a.academic_year,
                           a.semester, a.status, a.submission_date
                    FROM admission_applications a
                    JOIN admission_prospects p ON a.prospect_id = p.prospect_id
                    ORDER BY a.submission_date DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    prospect_name = f"{row['first_name']} {row['last_name']}"
                    values = (
                        row['application_id'],
                        prospect_name,
                        row['application_type'],
                        row['program_applied'],
                        row['academic_year'],
                        row['semester'],
                        row['status'],
                        row['submission_date'][:10] if row['submission_date'] else ''
                    )
                    self.applications_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_t("common.error"), f"Failed to load applications: {e}")

    def _load_reviews(self):
        """Load all reviews"""
        try:
            self.reviews_tree.delete(*self.reviews_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT review_id, application_id, reviewer_id, score,
                           recommendation, review_date
                    FROM application_reviews
                    ORDER BY review_date DESC
                    LIMIT 100
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['review_id'],
                        row['application_id'],
                        row['reviewer_id'] or _t("admissions_crm.reviews.unassigned"),
                        row['score'] if row['score'] else _t("common.na"),
                        row['recommendation'] or _t("admissions_crm.reviews.pending"),
                        row['review_date'][:10] if row['review_date'] else _t("admissions_crm.reviews.not_reviewed"),
                        _t("admissions_crm.reviews.completed")
                    )
                    self.reviews_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_t("common.error"), f"Failed to load reviews: {e}")

    def _load_campaigns(self):
        """Load all campaigns"""
        try:
            self.campaigns_tree.delete(*self.campaigns_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT campaign_id, campaign_name, campaign_type, target_audience,
                           sent_count, opened_count, status
                    FROM recruitment_campaigns
                    ORDER BY created_at DESC
                    LIMIT 50
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['campaign_id'],
                        row['campaign_name'],
                        row['campaign_type'],
                        row['target_audience'] or _t("admissions_crm.campaigns.all"),
                        row['sent_count'] or 0,
                        row['opened_count'] or 0,
                        '✓' if row['status'] == 'active' else '✗'
                    )
                    self.campaigns_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_t("common.error"), f"Failed to load campaigns: {e}")

    def _load_tours(self):
        """Load all tours"""
        try:
            self.tours_tree.delete(*self.tours_tree.get_children())

            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT tour_id, tour_date, tour_time, tour_guide,
                           max_attendees, current_attendees, status
                    FROM campus_tours
                    WHERE tour_date >= date('now')
                    ORDER BY tour_date, tour_time
                    LIMIT 50
                ''')

                for row in cursor.fetchall():
                    values = (
                        row['tour_id'],
                        row['tour_date'],
                        row['tour_time'],
                        _t("admissions_crm.tours.standard"),  # Default tour type since column doesn't exist in schema
                        row['tour_guide'] or _t("admissions_crm.tours.tbd"),
                        row['max_attendees'],
                        row['current_attendees'] or 0,
                        row['status']
                    )
                    self.tours_tree.insert('', tk.END, values=values)

        except Exception as e:
            messagebox.showerror(_t("common.error"), f"Failed to load tours: {e}")

    # Action methods
    def _add_prospect(self):
        """Add a new prospect"""
        AddProspectDialog(self.window, self.auth, self._load_prospects)

    def _log_interaction(self):
        """Log interaction with prospect"""
        selection = self.prospects_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("admissions_crm.prospects.select_prospect"))
            return

        item = self.prospects_tree.item(selection[0])
        prospect_id = item['values'][0]
        LogInteractionDialog(self.window, self.auth, prospect_id, self._load_prospects)

    def _draft_apl_for_prospect(self):
        """Seed a draft APL/RPL claim from the selected prospect.

        Pre-enrolment APL enquiries get recorded against
        ``prospect:<id>`` as the claimant — the canonical student id
        replaces it once the prospect converts to an applicant."""
        selection = self.prospects_tree.selection()
        if not selection:
            messagebox.showwarning(
                _t("common.warning"),
                _t("admissions_crm.prospects.select_prospect"),
            )
            return
        vals = self.prospects_tree.item(selection[0])['values']
        # columns: id, name, email, phone, intended_major, source, status, last_contact
        prospect_id = vals[0]
        name = vals[1]
        intended_major = vals[4] if len(vals) > 4 else None
        try:
            from education_system.post_18.university_system.modules.domain.academics.prior_learning_recognition.services.prior_learning_service import (
                PriorLearningService,
            )
            apl = PriorLearningService()
            cid = apl.create_draft_from_crm_prospect(
                int(prospect_id),
                prospect_name=str(name),
                intended_major=str(intended_major) if intended_major else None,
            )
        except Exception as e:
            messagebox.showerror(_t("common.error"), f"Failed to draft APL claim: {e}")
            return
        messagebox.showinfo(
            "APL claim drafted",
            f"Draft APL claim #{cid} created for prospect #{prospect_id} ({name}).\n"
            "Open Prior Learning (APL/RPL) from the navigation to review.",
        )

    def _submit_application(self):
        """Submit a new application"""
        SubmitApplicationDialog(self.window, self.auth, self._load_applications)

    def _update_application_status(self):
        """Update application status"""
        selection = self.applications_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("admissions_crm.applications.select_application"))
            return

        item = self.applications_tree.item(selection[0])
        application_id = item['values'][0]
        UpdateApplicationStatusDialog(self.window, self.auth, application_id, self._load_applications)

    def _create_review(self):
        """Create a new review for an application"""
        CreateReviewDialog(self.window, self.auth, self._load_reviews)

    def _assign_reviewer(self):
        """Assign reviewer to application"""
        selection = self.applications_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("admissions_crm.applications.select_application"))
            return

        item = self.applications_tree.item(selection[0])
        application_id = item['values'][0]
        AssignReviewerDialog(self.window, self.auth, application_id, self._load_reviews)

    def _submit_review(self):
        """Submit application review"""
        selection = self.reviews_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("admissions_crm.reviews.select_review"))
            return

        item = self.reviews_tree.item(selection[0])
        # Get application_id from the second column (index 1)
        application_id = item['values'][1]
        SubmitReviewDialog(self.window, self.auth, application_id, self._load_reviews)

    def _create_campaign(self):
        """Create communication campaign"""
        CreateCampaignDialog(self.window, self.auth, self._load_campaigns)

    def _send_communications(self):
        """Send campaign communications"""
        selection = self.campaigns_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("admissions_crm.campaigns.select_campaign"))
            return

        item = self.campaigns_tree.item(selection[0])
        campaign_id = item['values'][0]

        try:
            # Get campaign details
            with get_connection() as conn:
                campaign = conn.execute('''
                    SELECT campaign_name, campaign_type, target_audience, message_template
                    FROM recruitment_campaigns
                    WHERE campaign_id = ?
                ''', (campaign_id,)).fetchone()

                if not campaign:
                    messagebox.showerror(_t("common.error"), _t("admissions_crm.campaigns.not_found"))
                    return

                # Get recipients based on target audience
                if campaign['target_audience'] == 'All Prospects':
                    recipients = conn.execute('''
                        SELECT email, first_name, last_name FROM admission_prospects
                        WHERE email IS NOT NULL AND email != ''
                    ''').fetchall()
                elif campaign['target_audience'] == 'Applicants':
                    recipients = conn.execute('''
                        SELECT DISTINCT p.email, p.first_name, p.last_name
                        FROM admission_prospects p
                        JOIN admission_applications a ON p.prospect_id = a.prospect_id
                        WHERE p.email IS NOT NULL AND p.email != ''
                    ''').fetchall()
                elif campaign['target_audience'] == 'Accepted':
                    recipients = conn.execute('''
                        SELECT DISTINCT p.email, p.first_name, p.last_name
                        FROM admission_prospects p
                        JOIN admission_applications a ON p.prospect_id = a.prospect_id
                        WHERE a.status = 'accepted' AND p.email IS NOT NULL AND p.email != ''
                    ''').fetchall()
                else:
                    recipients = conn.execute('''
                        SELECT email, first_name, last_name FROM admission_prospects
                        WHERE email IS NOT NULL AND email != ''
                    ''').fetchall()

            # Send emails
            sent_count = 0
            for recipient in recipients:
                try:
                    # Personalize message
                    message = campaign['message_template'].replace('{first_name}', recipient['first_name'])
                    message = message.replace('{last_name}', recipient['last_name'])

                    # Send email
                    send_email(
                        recipient_email=recipient['email'],
                        subject=f"{campaign['campaign_name']}",
                        body=message
                    )
                    sent_count += 1

                    # Log in campaign messages
                    with transaction() as conn:
                        conn.execute('''
                            UPDATE recruitment_campaigns
                            SET sent_count = sent_count + 1
                            WHERE campaign_id = ?
                        ''', (campaign_id,))

                except Exception as e:
                    print(f"Failed to send to {recipient['email']}: {e}")

            messagebox.showinfo(_t("common.success"), _t("admissions_crm.campaigns.sent_to", count=sent_count))
            log_activity(f'Sent campaign communications (Campaign ID: {campaign_id}) to {sent_count} recipients',
                        user=self.auth.current_user.get('username'))
            self._load_campaigns()

        except Exception as e:
            messagebox.showerror(_t("common.error"), f"Failed to send communications: {e}")

    def _schedule_tour(self):
        """Schedule a campus tour"""
        ScheduleTourDialog(self.window, self.auth, self._load_tours)

    def _register_for_tour(self):
        """Register prospect for tour"""
        selection = self.tours_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning"), _t("admissions_crm.tours.select_tour"))
            return

        item = self.tours_tree.item(selection[0])
        tour_id = item['values'][0]
        RegisterForTourDialog(self.window, self.auth, tour_id, self._load_tours)


# Dialog Classes (simplified for space - expand as needed)

class AddProspectDialog:
    """Dialog for adding a new prospect"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("admissions_crm.dialogs.add_prospect.title"))
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("admissions_crm.dialogs.add_prospect.header"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Form
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Fields
        fields = [
            (_t("admissions_crm.dialogs.add_prospect.first_name"), "first_name"),
            (_t("admissions_crm.dialogs.add_prospect.last_name"), "last_name"),
            (_t("admissions_crm.dialogs.add_prospect.email"), "email"),
            (_t("admissions_crm.dialogs.add_prospect.phone"), "phone"),
            (_t("admissions_crm.dialogs.add_prospect.city"), "city"),
            (_t("admissions_crm.dialogs.add_prospect.state"), "state"),
            (_t("admissions_crm.dialogs.add_prospect.high_school"), "high_school"),
            (_t("admissions_crm.dialogs.add_prospect.intended_major"), "intended_major"),
            (_t("admissions_crm.dialogs.add_prospect.source"), "source"),
        ]

        self.entries = {}
        for i, (label, field) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=5)
            entry = ttk.Entry(form_frame, width=35)
            entry.grid(row=i, column=1, pady=5, padx=(10, 0))
            self.entries[field] = entry

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("admissions_crm.dialogs.add_prospect.btn_add"), command=self._add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admissions_crm.dialogs.add_prospect.btn_cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _add(self):
        try:
            first_name = self.entries['first_name'].get().strip()
            last_name = self.entries['last_name'].get().strip()
            email = self.entries['email'].get().strip()

            if not all([first_name, last_name, email]):
                messagebox.showerror(_t("common.error"), _t("admissions_crm.dialogs.add_prospect.required_fields"))
                return

            prospect_id = ProspectManager.create_prospect(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=self.entries['phone'].get().strip(),
                city=self.entries['city'].get().strip(),
                state=self.entries['state'].get().strip(),
                high_school=self.entries['high_school'].get().strip(),
                intended_major=self.entries['intended_major'].get().strip(),
                source=self.entries['source'].get().strip()
            )

            log_activity(f'Created prospect (ID: {prospect_id})',
                        user=self.auth.current_user.get('username'))

            messagebox.showinfo(_t("common.success"), _t("admissions_crm.messages.prospect_added", id=prospect_id))
            self.callback()
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("admissions_crm.errors.add_prospect", error=str(e)))


class LogInteractionDialog:
    """Dialog for logging prospect interaction"""

    def __init__(self, parent, auth, prospect_id, callback):
        self.auth = auth
        self.prospect_id = prospect_id
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("admissions_crm.dialogs.log_interaction.title"))
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("admissions_crm.dialogs.log_interaction.header", prospect_id=self.prospect_id),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.log_interaction.type")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.type_combo = ttk.Combobox(form_frame, width=32, values=[
            'Email', 'Phone Call', 'Campus Visit', 'Event', 'Meeting', 'Other'
        ])
        self.type_combo.set('Email')
        self.type_combo.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.log_interaction.notes")).grid(row=1, column=0, sticky=tk.NW, pady=5)
        self.notes_text = scrolledtext.ScrolledText(form_frame, width=33, height=10)
        self.notes_text.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.log_interaction.followup_date")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.followup_entry = ttk.Entry(form_frame, width=35)
        self.followup_entry.grid(row=2, column=1, pady=5, padx=(10, 0))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("admissions_crm.dialogs.log_interaction.btn_log"), command=self._log).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admissions_crm.dialogs.log_interaction.btn_cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _log(self):
        try:
            interaction_id = ProspectManager.log_interaction(
                prospect_id=self.prospect_id,
                interaction_type=self.type_combo.get(),
                notes=self.notes_text.get('1.0', tk.END).strip(),
                staff_member=self.auth.current_user.get('username', ''),
                next_followup_date=self.followup_entry.get().strip()
            )

            log_activity(f'Logged interaction (ID: {interaction_id}) for prospect {self.prospect_id}',
                        user=self.auth.current_user.get('username'))

            messagebox.showinfo(_t("common.success"), _t("admissions_crm.messages.interaction_logged"))
            self.callback()
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("admissions_crm.errors.log_interaction", error=str(e)))


class SubmitApplicationDialog:
    """Dialog for submitting application"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("admissions_crm.dialogs.submit_application.title"))
        self.dialog.geometry("500x450")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("admissions_crm.dialogs.submit_application.header"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.submit_application.prospect_id")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.prospect_entry = ttk.Entry(form_frame, width=35)
        self.prospect_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.submit_application.application_type")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.type_combo = ttk.Combobox(form_frame, width=32, values=['Undergraduate', 'Graduate', 'Transfer'])
        self.type_combo.set('Undergraduate')
        self.type_combo.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.submit_application.program")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.program_entry = ttk.Entry(form_frame, width=35)
        self.program_entry.grid(row=2, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.submit_application.academic_year")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.year_entry = ttk.Entry(form_frame, width=35)
        self.year_entry.insert(0, f"{datetime.now().year + 1}")
        self.year_entry.grid(row=3, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.submit_application.semester")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.semester_combo = ttk.Combobox(form_frame, width=32, values=['Fall', 'Spring', 'Summer'])
        self.semester_combo.set('Fall')
        self.semester_combo.grid(row=4, column=1, pady=5, padx=(10, 0))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("admissions_crm.dialogs.submit_application.btn_submit"), command=self._submit).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admissions_crm.dialogs.submit_application.btn_cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _submit(self):
        try:
            prospect_id = int(self.prospect_entry.get())
            program = self.program_entry.get().strip()

            if not program:
                messagebox.showerror(_t("common.error"), _t("admissions_crm.dialogs.submit_application.program_required"))
                return

            # Validate prospect exists before creating application
            with get_connection() as conn:
                cursor = conn.execute(
                    'SELECT prospect_id, first_name, last_name FROM admission_prospects WHERE prospect_id = ?',
                    (prospect_id,)
                )
                prospect = cursor.fetchone()

            if not prospect:
                messagebox.showerror(
                    _t("common.error"),
                    _t("admissions_crm.dialogs.submit_application.prospect_not_found", id=prospect_id)
                )
                return

            # Show confirmation with prospect name
            prospect_name = f"{prospect['first_name']} {prospect['last_name']}"
            if not messagebox.askyesno(
                _t("admissions_crm.dialogs.submit_application.confirm_title"),
                _t("admissions_crm.dialogs.submit_application.confirm_message", name=prospect_name, id=prospect_id)
            ):
                return

            application_id = ApplicationManager.submit_application(
                prospect_id=prospect_id,
                application_type=self.type_combo.get(),
                program_applied=program,
                academic_year=self.year_entry.get(),
                semester=self.semester_combo.get()
            )

            log_activity(f'Submitted application (ID: {application_id}) for prospect {prospect_id}',
                        user=self.auth.current_user.get('username'))

            messagebox.showinfo(_t("common.success"), _t("admissions_crm.messages.application_submitted", id=application_id, name=prospect_name))
            self.callback()
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("admissions_crm.errors.invalid_prospect_id"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("admissions_crm.errors.submit_application", error=str(e)))


class UpdateApplicationStatusDialog:
    """Dialog for updating application status"""

    def __init__(self, parent, auth, application_id, callback):
        self.auth = auth
        self.application_id = application_id
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("admissions_crm.dialogs.update_status.title"))
        self.dialog.geometry("500x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("admissions_crm.dialogs.update_status.header", application_id=self.application_id),
                 font=('Arial', 12, 'bold')).pack(pady=(0, 20))

        ttk.Label(main_frame, text=_t("admissions_crm.dialogs.update_status.new_status")).pack(pady=5)
        self.status_combo = ttk.Combobox(main_frame, width=30, values=[
            'submitted', 'under_review', 'interview_scheduled', 'accepted', 'rejected', 'waitlisted'
        ])
        self.status_combo.set('under_review')
        self.status_combo.pack(pady=10)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text=_t("admissions_crm.dialogs.update_status.btn_update"), command=self._update).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admissions_crm.dialogs.update_status.btn_cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _update(self):
        try:
            ApplicationManager.update_application_status(
                application_id=self.application_id,
                status=self.status_combo.get()
            )

            log_activity(f'Updated application status (ID: {self.application_id}) to {self.status_combo.get()}',
                        user=self.auth.current_user.get('username'))

            messagebox.showinfo(_t("common.success"), _t("admissions_crm.messages.status_updated"))
            self.callback()
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("admissions_crm.errors.update_status", error=str(e)))


class CreateReviewDialog:
    """Dialog for creating a new review"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("admissions_crm.dialogs.create_review.title"))
        self.dialog.geometry("500x550")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("admissions_crm.dialogs.create_review.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.create_review.application_id")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.app_id_entry = ttk.Entry(form_frame, width=35)
        self.app_id_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.create_review.review_stage")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.stage_combo = ttk.Combobox(form_frame, width=32, values=['initial', 'committee', 'final'])
        self.stage_combo.set('initial')
        self.stage_combo.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.create_review.score")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.score_entry = ttk.Entry(form_frame, width=35)
        self.score_entry.grid(row=2, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.create_review.recommendation")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.rec_combo = ttk.Combobox(form_frame, width=32, values=['accept', 'reject', 'waitlist', 'interview'])
        self.rec_combo.set('accept')
        self.rec_combo.grid(row=3, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.create_review.comments")).grid(row=4, column=0, sticky=tk.NW, pady=5)
        self.comments_text = scrolledtext.ScrolledText(form_frame, width=33, height=10)
        self.comments_text.grid(row=4, column=1, pady=5, padx=(10, 0))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("admissions_crm.dialogs.create_review.btn_create"), command=self._create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admissions_crm.dialogs.create_review.btn_cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _create(self):
        try:
            application_id = int(self.app_id_entry.get().strip())
            score = int(self.score_entry.get())

            if score < 1 or score > 100:
                messagebox.showerror(_t("common.error"), _t("admissions_crm.dialogs.create_review.score_range"))
                return

            # Verify application exists
            with get_connection() as conn:
                app_exists = conn.execute(
                    'SELECT application_id FROM admission_applications WHERE application_id = ?',
                    (application_id,)
                ).fetchone()

                if not app_exists:
                    messagebox.showerror(_t("common.error"), _t("admissions_crm.dialogs.create_review.app_not_found", id=application_id))
                    return

            reviewer_id = self.auth.current_user.get('username', 'unknown')

            review_id = ReviewWorkflowManager.create_review(
                application_id=application_id,
                reviewer_id=reviewer_id,
                review_stage=self.stage_combo.get(),
                score=score,
                recommendation=self.rec_combo.get(),
                comments=self.comments_text.get('1.0', tk.END).strip()
            )

            log_activity(f'Created review (ID: {review_id}) for application {application_id}',
                        user=reviewer_id)

            messagebox.showinfo(_t("common.success"), _t("admissions_crm.messages.review_created", id=review_id))
            self.callback()
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("admissions_crm.errors.invalid_app_id"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("admissions_crm.errors.create_review", error=str(e)))


class AssignReviewerDialog:
    """Dialog for assigning reviewer"""

    def __init__(self, parent, auth, application_id, callback):
        self.auth = auth
        self.application_id = application_id
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("admissions_crm.dialogs.assign_reviewer.title"))
        self.dialog.geometry("400x200")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("admissions_crm.dialogs.assign_reviewer.header", application_id=self.application_id),
                 font=('Arial', 12, 'bold')).pack(pady=(0, 20))

        ttk.Label(main_frame, text=_t("admissions_crm.dialogs.assign_reviewer.reviewer_id")).pack(pady=5)
        self.reviewer_entry = ttk.Entry(main_frame, width=30)
        self.reviewer_entry.pack(pady=10)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text=_t("admissions_crm.dialogs.assign_reviewer.btn_assign"), command=self._assign).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admissions_crm.dialogs.assign_reviewer.btn_cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _assign(self):
        try:
            reviewer_id = self.reviewer_entry.get().strip()
            if not reviewer_id:
                messagebox.showerror(_t("common.error"), _t("admissions_crm.dialogs.assign_reviewer.reviewer_required"))
                return

            review_id = ReviewWorkflowManager.assign_reviewer(
                application_id=self.application_id,
                reviewer_id=reviewer_id
            )

            log_activity(f'Assigned reviewer to application {self.application_id} (Review ID: {review_id})',
                        user=self.auth.current_user.get('username'))

            messagebox.showinfo(_t("common.success"), _t("admissions_crm.messages.reviewer_assigned", id=review_id))
            self.callback()
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("admissions_crm.errors.assign_reviewer", error=str(e)))


class SubmitReviewDialog:
    """Dialog for submitting review"""

    def __init__(self, parent, auth, application_id, callback):
        self.auth = auth
        self.application_id = application_id
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("admissions_crm.dialogs.submit_review.title"))
        self.dialog.geometry("500x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("admissions_crm.dialogs.submit_review.header", application_id=self.application_id),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.submit_review.review_stage")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.stage_combo = ttk.Combobox(form_frame, width=32, values=['initial', 'committee', 'final'])
        self.stage_combo.set('initial')
        self.stage_combo.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.submit_review.score")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.score_entry = ttk.Entry(form_frame, width=35)
        self.score_entry.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.submit_review.recommendation")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.rec_combo = ttk.Combobox(form_frame, width=32, values=['accept', 'reject', 'waitlist', 'interview'])
        self.rec_combo.set('accept')
        self.rec_combo.grid(row=2, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.submit_review.comments")).grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.comments_text = scrolledtext.ScrolledText(form_frame, width=33, height=10)
        self.comments_text.grid(row=3, column=1, pady=5, padx=(10, 0))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("admissions_crm.dialogs.submit_review.btn_submit"), command=self._submit).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admissions_crm.dialogs.submit_review.btn_cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _submit(self):
        try:
            score = int(self.score_entry.get())
            if score < 1 or score > 100:
                messagebox.showerror(_t("common.error"), _t("admissions_crm.dialogs.create_review.score_range"))
                return

            reviewer_id = self.auth.current_user.get('username', 'unknown')

            review_id = ReviewWorkflowManager.create_review(
                application_id=self.application_id,
                reviewer_id=reviewer_id,
                review_stage=self.stage_combo.get(),
                score=score,
                recommendation=self.rec_combo.get(),
                comments=self.comments_text.get('1.0', tk.END).strip()
            )

            log_activity(f'Submitted review (ID: {review_id}) for application {self.application_id}',
                        user=reviewer_id)

            messagebox.showinfo(_t("common.success"), _t("admissions_crm.messages.review_submitted", id=review_id))
            self.callback()
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("admissions_crm.dialogs.submit_review.invalid_score"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("admissions_crm.errors.submit_review", error=str(e)))


class CreateCampaignDialog:
    """Dialog for creating campaign"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("admissions_crm.dialogs.create_campaign.title"))
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("admissions_crm.dialogs.create_campaign.header"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.create_campaign.campaign_name")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(form_frame, width=35)
        self.name_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.create_campaign.type")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.type_combo = ttk.Combobox(form_frame, width=32, values=['Email', 'SMS', 'Mail', 'Multi-channel'])
        self.type_combo.set('Email')
        self.type_combo.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.create_campaign.target_audience")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.target_combo = ttk.Combobox(form_frame, width=32, values=[
            'All Prospects', 'Applicants', 'Accepted', 'Waitlisted', 'Custom'
        ])
        self.target_combo.set('All Prospects')
        self.target_combo.grid(row=2, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.create_campaign.message_template")).grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.template_text = scrolledtext.ScrolledText(form_frame, width=33, height=8)
        self.template_text.grid(row=3, column=1, pady=5, padx=(10, 0))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("admissions_crm.dialogs.create_campaign.btn_create"), command=self._create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admissions_crm.dialogs.create_campaign.btn_cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _create(self):
        try:
            name = self.name_entry.get().strip()
            if not name:
                messagebox.showerror(_t("common.error"), _t("admissions_crm.dialogs.create_campaign.name_required"))
                return

            # Set default dates (today to 30 days from now)
            start_date = datetime.now().strftime('%Y-%m-%d')
            end_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

            campaign_id = CampaignManager.create_campaign(
                campaign_name=name,
                campaign_type=self.type_combo.get(),
                target_audience=self.target_combo.get(),
                start_date=start_date,
                end_date=end_date,
                message_template=self.template_text.get('1.0', tk.END).strip()
            )

            log_activity(f'Created campaign (ID: {campaign_id}): {name}',
                        user=self.auth.current_user.get('username'))

            messagebox.showinfo(_t("common.success"), _t("admissions_crm.messages.campaign_created", id=campaign_id))
            self.callback()
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("admissions_crm.errors.create_campaign", error=str(e)))


class ScheduleTourDialog:
    """Dialog for scheduling tour"""

    def __init__(self, parent, auth, callback):
        self.auth = auth
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("admissions_crm.dialogs.schedule_tour.title"))
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("admissions_crm.dialogs.schedule_tour.header"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.schedule_tour.tour_date")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.date_entry = ttk.Entry(form_frame, width=35)
        self.date_entry.insert(0, (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'))
        self.date_entry.grid(row=0, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.schedule_tour.time")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.time_entry = ttk.Entry(form_frame, width=35)
        self.time_entry.insert(0, "10:00")
        self.time_entry.grid(row=1, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.schedule_tour.tour_type")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.type_combo = ttk.Combobox(form_frame, width=32, values=['General', 'Academic', 'Athletic', 'Special'])
        self.type_combo.set('General')
        self.type_combo.grid(row=2, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.schedule_tour.tour_guide")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.guide_entry = ttk.Entry(form_frame, width=35)
        self.guide_entry.grid(row=3, column=1, pady=5, padx=(10, 0))

        ttk.Label(form_frame, text=_t("admissions_crm.dialogs.schedule_tour.max_attendees")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.capacity_entry = ttk.Entry(form_frame, width=35)
        self.capacity_entry.insert(0, "20")
        self.capacity_entry.grid(row=4, column=1, pady=5, padx=(10, 0))

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(20, 0))

        ttk.Button(btn_frame, text=_t("admissions_crm.dialogs.schedule_tour.btn_schedule"), command=self._schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admissions_crm.dialogs.schedule_tour.btn_cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _schedule(self):
        try:
            tour_id = TourManager.create_tour(
                tour_date=self.date_entry.get(),
                tour_time=self.time_entry.get(),
                tour_guide=self.guide_entry.get().strip(),
                max_attendees=int(self.capacity_entry.get())
            )

            log_activity(f'Scheduled campus tour (ID: {tour_id}) for {self.date_entry.get()}',
                        user=self.auth.current_user.get('username'))

            messagebox.showinfo(_t("common.success"), _t("admissions_crm.messages.tour_scheduled", id=tour_id))
            self.callback()
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("admissions_crm.dialogs.schedule_tour.invalid_attendees"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("admissions_crm.errors.schedule_tour", error=str(e)))


class RegisterForTourDialog:
    """Dialog for registering for tour"""

    def __init__(self, parent, auth, tour_id, callback):
        self.auth = auth
        self.tour_id = tour_id
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("admissions_crm.dialogs.register_tour.title"))
        self.dialog.geometry("400x200")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("admissions_crm.dialogs.register_tour.header", tour_id=self.tour_id),
                 font=('Arial', 12, 'bold')).pack(pady=(0, 20))

        ttk.Label(main_frame, text=_t("admissions_crm.dialogs.register_tour.prospect_id")).pack(pady=5)
        self.prospect_entry = ttk.Entry(main_frame, width=30)
        self.prospect_entry.pack(pady=10)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text=_t("admissions_crm.dialogs.register_tour.btn_register"), command=self._register).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("admissions_crm.dialogs.register_tour.btn_cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _register(self):
        try:
            prospect_id = int(self.prospect_entry.get())

            registration_id = TourManager.register_for_tour(
                tour_id=self.tour_id,
                prospect_id=prospect_id
            )

            log_activity(f'Registered prospect {prospect_id} for tour {self.tour_id} (Registration ID: {registration_id})',
                        user=self.auth.current_user.get('username'))

            messagebox.showinfo(_t("common.success"), _t("admissions_crm.messages.registered", id=registration_id))
            self.callback()
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror(_t("common.error"), _t("admissions_crm.dialogs.register_tour.invalid_prospect"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("admissions_crm.errors.register_tour", error=str(e)))


# Launcher function
def launch_admissions_crm_gui(root, auth):
    """Launch the Admissions & Recruitment CRM GUI"""
    try:
        AdmissionsCRMGUI(root, auth)
    except Exception as e:
        messagebox.showerror(_t("common.error"), f"Failed to launch Admissions CRM GUI: {e}")
        print(f"❌ Admissions CRM GUI error: {e}")


__all__ = ['AdmissionsCRMGUI', 'launch_admissions_crm_gui']
